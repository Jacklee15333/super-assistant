"""
loop_engine.py — 目标循环（Loop）

把「Loop Engineering」落到本软件里：本质就三件事——
  1. 定一个【目标】(goal)
  2. 定一组【验收标准】(criteria)：什么叫「干完了」，每条都应当是能判断成/没成的
  3. 让小助【自己一圈一圈地跑】：每轮推进目标 → 自检对照验收标准 → 没达标就继续修，
     直到全部达标，或到达最多轮数（防止无限烧 token）。

设计要点：
  · 后台线程跑，前端轮询 /loop/status 看实时进度（沿用本项目「视频队列」那套后台+轮询模式）。
  · 复用 agent_core.run_agent 做每一轮的实际执行（能调工具）。
  · allow_actions：是否允许循环里自动执行「需确认的危险操作」。默认关——只跑安全/只读操作，
    更稳；真要让它动电脑，用户在界面勾选，并且仍受右上角「电脑操作权限」总闸约束。
  · 有最多轮数上限（成本闸）。视频里强调 Loop 很烧 token，所以这里默认轮数不大。

注意：网页模型不支持工具，循环会退化成「纯文本推理循环」，仍可用于规划类目标；
带工具的本地模型或 Claude 才能真正「动手做」。
"""

import json
import re
import threading
import datetime

import agent_core as core

_lock = threading.Lock()
_state = {
    "running": False,
    "done": False,
    "stopped": False,
    "error": "",
    "goal": "",
    "criteria": [],          # [{"text": str, "met": bool}]
    "rounds": [],            # [{"n": int, "summary": str, "tools": [str], "ts": str}]
    "max_rounds": 0,
    "stage": "",             # 当前在干嘛（给前端显示）
    "started_at": "",
    "finished_at": "",
}
_stop_flag = {"v": False}
_worker = {"t": None}

# 最多轮数硬上限（再防一道，避免前端传个超大值把 token 烧光）
HARD_MAX_ROUNDS = 12


def get_status():
    with _lock:
        # 返回一份拷贝，避免并发改动
        return json.loads(json.dumps(_state, ensure_ascii=False))


def stop_loop():
    _stop_flag["v"] = True
    with _lock:
        _state["stage"] = "正在停止…（这一轮跑完就停）"
    return {"ok": True}


def start_loop(use_local, model, goal, criteria, max_rounds=5, allow_actions=False):
    goal = (goal or "").strip()
    crit = [c.strip() for c in (criteria or []) if c and c.strip()]
    if not goal:
        return {"ok": False, "message": "请先填写目标。"}
    if not crit:
        return {"ok": False, "message": "请至少写一条验收标准——Loop 的关键就是「怎样算干完」。"}
    with _lock:
        if _state["running"]:
            return {"ok": False, "message": "已经有一个循环在跑了，先停止或等它结束。"}
        try:
            mr = int(max_rounds)
        except (ValueError, TypeError):
            mr = 5
        mr = max(1, min(mr, HARD_MAX_ROUNDS))
        _stop_flag["v"] = False
        _state.update({
            "running": True, "done": False, "stopped": False, "error": "",
            "goal": goal,
            "criteria": [{"text": t, "met": False} for t in crit],
            "rounds": [], "max_rounds": mr, "stage": "准备开始…",
            "started_at": datetime.datetime.now().strftime("%H:%M:%S"),
            "finished_at": "",
        })
    t = threading.Thread(
        target=_run,
        kwargs={"use_local": use_local, "model": model, "goal": goal,
                "criteria": crit, "max_rounds": mr, "allow_actions": bool(allow_actions)},
        daemon=True)
    _worker["t"] = t
    t.start()
    return {"ok": True}


def _set_stage(s):
    with _lock:
        _state["stage"] = s


def _criteria_block(crit):
    return "\n".join(f"{i+1}. {c}" for i, c in enumerate(crit))


def _self_check(client, model, goal, crit, messages):
    """让模型对照验收标准给当前进展打分。返回 (met_list[bool], done[bool], summary[str])。"""
    ask = (
        "现在请你**严格对照验收标准**，评估目标到目前为止完成得怎么样。\n"
        f"目标：{goal}\n"
        f"验收标准（按顺序）：\n{_criteria_block(crit)}\n\n"
        "只输出一个 JSON 对象，不要别的话、不要代码块包裹，格式：\n"
        '{"summary":"一句话说这轮做了什么/现在到哪了","criteria":[true,false,...],"done":true或false}\n'
        "其中 criteria 数组按验收标准的顺序，每项 true=已达标 false=还没。"
        "全部达标时 done 为 true。请如实评估，没做到就写 false，不要凑数。"
    )
    msgs = list(messages) + [{"role": "user", "content": ask}]
    try:
        resp = client.chat.completions.create(model=model, messages=msgs)
        out = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return [False] * len(crit), False, f"自检调用出错：{e}"
    # 抽出 JSON
    m = re.search(r"\{[\s\S]*\}", out)
    data = {}
    if m:
        try:
            data = json.loads(m.group(0))
        except Exception:
            data = {}
    met = data.get("criteria")
    if not isinstance(met, list):
        met = [False] * len(crit)
    # 对齐长度
    met = [bool(x) for x in met][:len(crit)]
    while len(met) < len(crit):
        met.append(False)
    done = bool(data.get("done")) or all(met)
    summary = (data.get("summary") or out[:160] or "（无小结）").strip()
    return met, done, summary


def _run(use_local, model, goal, criteria, max_rounds, allow_actions):
    import time as _time
    _t0 = _time.time()
    try:
        import tools as T
        client = core.make_client_for(model, use_local)
        # 安全策略来自运行台（Harness）；界面勾了「允许自动执行操作」也算放行
        try:
            import harness
            _hcfg = harness.get_config()
        except Exception:
            _hcfg = {"safety": "ask", "max_steps": 6}
        if allow_actions or _hcfg.get("safety") == "auto":
            auto_set = list(T.DANGER_TOOLS)
        else:
            auto_set = []
        per_round_steps = max(2, min(int(_hcfg.get("max_steps", 6)), 12))

        sys_prompt = (
            "你正在执行一个【目标循环（Loop）】任务。规则：\n"
            "- 你有一个明确的目标，和一组验收标准（怎样算干完）。\n"
            "- 你要一轮一轮地推进：每一轮尽量往目标前进一步，能用工具就用工具去真正做事，"
            "不要只是空谈或假装完成。\n"
            "- 每轮结束后系统会让你对照验收标准自检，没达标的会进入下一轮继续。\n"
            "- 始终盯着验收标准，把劲用在「让那些标准变成已达标」上。\n"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content":
                f"【目标】{goal}\n\n【验收标准】\n{_criteria_block(criteria)}\n\n"
                "现在开始第一轮，请推进这个目标。"},
        ]

        for rnd in range(1, max_rounds + 1):
            if _stop_flag["v"]:
                break
            _set_stage(f"第 {rnd}/{max_rounds} 轮：执行中…")
            round_tools = []

            def on_tool(name, args, result):
                round_tools.append(name)

            try:
                reply, messages, pending = core.run_agent(
                    client, model, messages,
                    shell_enabled=allow_actions,
                    on_tool=on_tool,
                    max_steps=per_round_steps,
                    auto_approve_tools=auto_set,
                )
            except Exception as e:
                with _lock:
                    _state["error"] = f"第 {rnd} 轮执行出错：{e}"
                break

            # 遇到需确认的危险操作但没授权 → 停在这里，提示用户
            if pending is not None:
                with _lock:
                    _state["rounds"].append({
                        "n": rnd,
                        "summary": "这一步需要执行一个「需确认的操作」，但你没勾选「允许自动执行操作」，"
                                   "已停下。勾选后再跑，或换一个不需要动电脑的目标。",
                        "tools": round_tools,
                        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
                    })
                    _state["stopped"] = True
                break

            if _stop_flag["v"]:
                # 执行完这一轮但用户已请求停止：记录这轮就收尾
                pass

            _set_stage(f"第 {rnd}/{max_rounds} 轮：对照验收标准自检…")
            met, done, summary = _self_check(client, model, goal, criteria, messages)

            with _lock:
                for i, c in enumerate(_state["criteria"]):
                    if i < len(met):
                        c["met"] = met[i]
                _state["rounds"].append({
                    "n": rnd,
                    "summary": summary,
                    "tools": round_tools,
                    "ts": datetime.datetime.now().strftime("%H:%M:%S"),
                })

            if done:
                with _lock:
                    _state["done"] = True
                break

            if _stop_flag["v"]:
                break

            # 没达标 → 进入下一轮，把「还差哪些」喂回去
            not_met = [criteria[i] for i in range(len(criteria)) if i < len(met) and not met[i]]
            messages.append({
                "role": "user",
                "content": "还没全部达标。还差这些验收标准：\n"
                           + _criteria_block(not_met)
                           + "\n请进入下一轮，专门把这些做到。",
            })

        with _lock:
            _state["running"] = False
            _state["stopped"] = _state["stopped"] or _stop_flag["v"]
            _state["finished_at"] = datetime.datetime.now().strftime("%H:%M:%S")
            if _state["done"]:
                _state["stage"] = "✅ 全部验收标准达标，循环完成。"
            elif _state["stopped"]:
                _state["stage"] = "⏹ 已停止。"
            elif _state["error"]:
                _state["stage"] = "出错停止。"
            else:
                _state["stage"] = "已到达最多轮数，停止（可能还没全部达标）。"
            _rounds_snapshot = list(_state["rounds"])
            _done = _state["done"]; _stopped = _state["stopped"]; _err = _state["error"]
        # 记一条运行日志（Harness 可观测 / 评估）
        try:
            import harness
            all_tools = []
            for rd in _rounds_snapshot:
                all_tools.extend(rd.get("tools") or [])
            outcome = "done" if _done else ("stopped" if _stopped else "maxed")
            harness.record_run(
                "loop", title=goal, tools=all_tools,
                steps=len(_rounds_snapshot), error=_err, outcome=outcome,
                seconds=int(_time.time() - _t0))
        except Exception:
            pass
    except Exception as e:
        with _lock:
            _state["running"] = False
            _state["error"] = str(e)
            _state["stage"] = "出错停止。"
            _state["finished_at"] = datetime.datetime.now().strftime("%H:%M:%S")
