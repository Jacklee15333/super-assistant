"""
harness.py — 运行台（Harness）

把视频里讲的 Harness 落地：Agent = 模型 + Harness。模型只是「大脑」，
Harness 是「模型之外」那层工程系统——负责状态、工具调度、错误恢复、上下文管理、
日志、安全、评估。本模块提供两块「能操作、能看见」的东西：

1. 运行设置（壳的旋钮）：用户能调、且真正生效的几个工程参数——
   · context_budget：注入多少长期记忆（防「上下文腐烂」：塞太多模型反而忘了原始目标）
   · max_steps：单次最多工具步数（防「工具死循环」：到顶就停）
   · safety：危险操作策略（安全控制：每次问 / 只读自动 / 全自动）—— 主要给「目标循环」当默认
   · keep_log：是否记录运行日志

2. 运行日志（可观测 + 评估）：把每次对话/循环跑了什么记下来——用了哪些工具、几步、
   有没有出错、耗时、是否达标。让原本黑盒的 agent 变得「可观测、可复盘、可评估」，
   对应 Harness 七大功能里的「日志记录」和「评估与度量」。

全部存本地 memory 目录，纯文本/JSON，随时可看可删。
"""

import json
import datetime
from pathlib import Path

from agent_core import MEMORY_DIR

CONFIG_PATH = MEMORY_DIR / "harness_config.json"
RUNS_PATH = MEMORY_DIR / "harness_runs.json"
MAX_RUNS = 50  # 日志最多留这么多条，超了丢最早的

_DEFAULT = {
    "context_budget": 4000,   # 注入长期记忆的字符上限
    "max_steps": 8,           # 单次最多工具步数
    "safety": "ask",          # ask=危险操作每次问；readonly_auto=只读自动+危险问；auto=全自动(危险)
    "keep_log": True,
}


def get_config():
    cfg = dict(_DEFAULT)
    try:
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    # 兜底范围，防止被填成离谱的值
    try:
        cfg["context_budget"] = max(500, min(int(cfg["context_budget"]), 20000))
    except Exception:
        cfg["context_budget"] = _DEFAULT["context_budget"]
    try:
        cfg["max_steps"] = max(2, min(int(cfg["max_steps"]), 20))
    except Exception:
        cfg["max_steps"] = _DEFAULT["max_steps"]
    if cfg.get("safety") not in ("ask", "readonly_auto", "auto"):
        cfg["safety"] = "ask"
    cfg["keep_log"] = bool(cfg.get("keep_log", True))
    return cfg


def save_config(patch: dict):
    cfg = get_config()
    for k in ("context_budget", "max_steps", "safety", "keep_log"):
        if k in (patch or {}):
            cfg[k] = patch[k]
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return get_config()


# —— 给别的模块取单个参数用的小helper ——
def context_budget():
    return get_config()["context_budget"]


def max_steps():
    return get_config()["max_steps"]


def keep_log():
    return get_config()["keep_log"]


# ====================== 运行日志 ======================

def _load_runs():
    try:
        if RUNS_PATH.exists():
            data = json.loads(RUNS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_runs(runs):
    try:
        RUNS_PATH.write_text(json.dumps(runs[-MAX_RUNS:], ensure_ascii=False, indent=2),
                             encoding="utf-8")
    except Exception:
        pass


def record_run(kind, title="", tools=None, steps=0, error="",
               outcome="", tokens_est=0, seconds=0):
    """记一条运行日志。kind: 'chat' / 'loop'。失败安静跳过，绝不影响主流程。"""
    try:
        if not keep_log():
            return
        tools = tools or []
        # 工具用量统计：{名字: 次数}
        tool_count = {}
        for t in tools:
            tool_count[t] = tool_count.get(t, 0) + 1
        rec = {
            "ts": datetime.datetime.now().strftime("%m-%d %H:%M:%S"),
            "kind": kind,
            "title": (title or "")[:120],
            "tools": tools,
            "tool_count": tool_count,
            "steps": int(steps or len(tools)),
            "error": (error or "")[:300],
            "outcome": outcome,            # loop: 'done'/'stopped'/'maxed'；chat: ''
            "tokens_est": int(tokens_est or 0),
            "seconds": int(seconds or 0),
        }
        runs = _load_runs()
        runs.append(rec)
        _save_runs(runs)
    except Exception:
        pass


def list_runs(limit=30):
    runs = _load_runs()
    return list(reversed(runs[-limit:]))  # 最新在前


# ====================== 进行中任务（实时记录） ======================
# 让运行台在任务「正在跑」时就能看到，而不是等结束。做法：begin_run 先写一条
# status=running 的占位记录并返回 run_id；任务每进一步可 update_run 更新步骤；
# 结束时 finish_run 按 id 把它更新成最终结果（达标/已停 + 耗时 + 错误）。
import time as _time_mod


def begin_run(kind, title="", tools=None):
    """写一条「进行中」记录，返回 run_id（失败返回 ""，调用方据此决定要不要 finish）。"""
    try:
        if not keep_log():
            return ""
        rid = "%s-%d" % (kind, int(_time_mod.time() * 1000))
        tools = list(tools or [])
        tool_count = {}
        for t in tools:
            tool_count[t] = tool_count.get(t, 0) + 1
        rec = {
            "id": rid,
            "ts": datetime.datetime.now().strftime("%m-%d %H:%M:%S"),
            "kind": kind,
            "title": (title or "")[:120],
            "tools": tools,
            "tool_count": tool_count,
            "steps": len(tools),
            "error": "",
            "outcome": "",
            "status": "running",      # ← 运行台据此显示「⏳ 进行中」
            "tokens_est": 0,
            "seconds": 0,
            "_start": _time_mod.time(),
        }
        runs = _load_runs()
        runs.append(rec)
        _save_runs(runs)
        return rid
    except Exception:
        return ""


def update_run(run_id, tools=None, title=None):
    """更新一条进行中记录的步骤/标题（任务每进一步时调，可选）。"""
    try:
        if not run_id:
            return
        runs = _load_runs()
        for rec in runs:
            if rec.get("id") == run_id:
                if tools is not None:
                    rec["tools"] = list(tools)
                    tc = {}
                    for t in rec["tools"]:
                        tc[t] = tc.get(t, 0) + 1
                    rec["tool_count"] = tc
                    rec["steps"] = len(rec["tools"])
                if title is not None:
                    rec["title"] = (title or "")[:120]
                _save_runs(runs)
                return
    except Exception:
        pass


def finish_run(run_id, tools=None, error="", outcome="", title=None, note=""):
    """把进行中记录更新成最终结果。run_id 为空则退化成普通 record_run（不丢记录）。
    note：一句叙述性的完成提示（如「已完成《X》，继续下一个」），运行台会显示。"""
    try:
        if not run_id:
            return
        runs = _load_runs()
        for rec in runs:
            if rec.get("id") == run_id:
                if tools is not None:
                    rec["tools"] = list(tools)
                    tc = {}
                    for t in rec["tools"]:
                        tc[t] = tc.get(t, 0) + 1
                    rec["tool_count"] = tc
                    rec["steps"] = len(rec["tools"])
                if title is not None:
                    rec["title"] = (title or "")[:120]
                rec["error"] = (error or "")[:300]
                rec["outcome"] = outcome
                rec["status"] = "done"
                if note:
                    rec["note"] = note[:200]
                start = rec.pop("_start", None)
                if start:
                    rec["seconds"] = int(_time_mod.time() - start)
                _save_runs(runs)
                return
    except Exception:
        pass


def clear_runs():
    _save_runs([])
    return True


def metrics_summary():
    """把日志聚成几个评估指标（成功率、平均步数、出错率、估算 token、近 N 次工具用量）。"""
    runs = _load_runs()
    n = len(runs)
    if n == 0:
        return {"count": 0}
    errs = sum(1 for r in runs if r.get("error"))
    loops = [r for r in runs if r.get("kind") == "loop"]
    done = sum(1 for r in loops if r.get("outcome") == "done")
    steps = [r.get("steps", 0) for r in runs]
    toks = sum(r.get("tokens_est", 0) for r in runs)
    tool_total = {}
    for r in runs:
        for k, v in (r.get("tool_count") or {}).items():
            tool_total[k] = tool_total.get(k, 0) + v
    top_tools = sorted(tool_total.items(), key=lambda x: -x[1])[:5]
    return {
        "count": n,
        "loop_count": len(loops),
        "loop_done": done,
        "loop_success_rate": round(done / len(loops) * 100) if loops else None,
        "error_rate": round(errs / n * 100),
        "avg_steps": round(sum(steps) / n, 1) if steps else 0,
        "tokens_est_total": toks,
        "top_tools": top_tools,
    }


def estimate_tokens(messages):
    """非常粗略地估 token 数：按字符 / 3（中文偏多时更接近）。只用于成本感知，不精确。"""
    try:
        total = 0
        for m in messages or []:
            c = m.get("content")
            if isinstance(c, str):
                total += len(c)
        return total // 3
    except Exception:
        return 0
