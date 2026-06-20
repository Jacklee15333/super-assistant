"""
lumi_features.py — 「懂你」四件套（灵感来自 LumiOS，按超能小助的极简本地风格重写）

四个能力，全部纯本地、复用你现有的 memory 体系和模型，不引入任何重依赖：

  ① 人格演化 (evolve_personality)
     读你和小助的对话记忆 → 让模型总结你的语气/常用词/关注点/沟通风格
     → 写进 memory/OWNER_PROFILE.md（注入系统提示，让小助"越用越像、越懂你"）。
     每次演化记一笔到 memory/evolution_log.md，可回溯。
     不动你手写的 SOUL.md，单独一份"我观察到的你"，安全可控。

  ② 关系网络 (extract_relationships)
     对话后抽取你提到的人 → 累积到 memory/relationships.md
     （谁、和你什么关系、聊过什么）→ 注入系统提示，下次提到就"记得"。

  ③ 主动问候 / 返回摘要 (make_greeting / make_return_summary)
     结合时间 + 记忆 + 关系，生成一句个性化问候；离开回来给后台工作摘要。

  ④ 系统扫描 / 职业检测 (scan_environment)
     扫已装软件 → 推断职业/常用工具 → 写进 memory/ENVIRONMENT.md（注入系统提示），
     让回答更贴合你的真实环境。

设计原则（沿用超能小助）：标准库优先、全本机、失败安静降级、绝不让这些"锦上添花"
的功能把主流程搞崩。所有对外函数都 try 包裹。
"""

import os
import re
import json
import datetime
import threading
from pathlib import Path

import agent_core as core


# 注入系统提示用的几个文件名（都在 memory/ 下，纯文本，你随时能看能改能删）
OWNER_PROFILE = "OWNER_PROFILE.md"    # ① 人格演化产出：小助观察到的「你」
EVOLUTION_LOG = "evolution_log.md"    # ① 每次演化的留痕
RELATIONS = "relationships.md"        # ② 关系网络
ENVIRONMENT = "ENVIRONMENT.md"        # ④ 环境画像 / 职业

EVOLVE_PROGRESS = "evolve_progress.json"   # ① 人格演化的实时进度（让用户看见每一步）


def _mem(name):
    return core.MEMORY_DIR / name


def _read(name):
    try:
        return core.read_memory_file(name)
    except Exception:
        return ""


def _today():
    return datetime.date.today().isoformat()


def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _now_clock():
    return datetime.datetime.now().strftime("%H:%M:%S")


# ════════════════════════════════════════════════════════════════════
#  人格演化进度（后台线程跑 + 落盘 + 前端轮询，让你看见每一步）
# ════════════════════════════════════════════════════════════════════

_evolve_work = {"thread": None, "running": False}


def _model_label(use_local, model):
    """把 use_local + model 翻译成人话，告诉用户这步用的哪个模型。"""
    m = (model or "").strip()
    if not m:
        m = "qwen2.5"
    if m == "web":
        return "网页模型"
    if m == "claude" or m.startswith("claude::"):
        return "Claude 官方"
    # 「懂你」这类轻量提炼默认走本地，_ask 里会把非本地/网页回退成本地 qwen2.5
    try:
        if use_local and not core.is_web_model(m):
            return "本地 · " + m
    except Exception:
        pass
    return "本地 · qwen2.5"


def _default_evolve_progress():
    return {
        "active": False,
        "phase": "idle",       # idle/collecting/distilling/synthesizing/writing/done/error
        "step": 0,             # 当前第几步
        "total_steps": 5,
        "percent": 0,
        "model": "",           # 这次用的模型（人话）
        "activity": [],        # 实时活动日志（带时间戳）
        "sources": [],         # 本次参考的资料源（带可点击跳转目标），见 _ev_sources
        "started_at": "",
        "finished_at": "",
        "message": "",
        "ok": None,
    }


def _read_evolve_progress():
    try:
        p = _mem(EVOLVE_PROGRESS)
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            base = _default_evolve_progress()
            base.update(d if isinstance(d, dict) else {})
            return base
    except Exception:
        pass
    return _default_evolve_progress()


def _write_evolve_progress(prog):
    try:
        _mem(EVOLVE_PROGRESS).write_text(
            json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _ev_log(prog, text):
    prog.setdefault("activity", [])
    prog["activity"].append("%s  %s" % (_now_clock(), text))
    prog["activity"] = prog["activity"][-40:]


def _ev_step(prog, phase, step, text):
    prog["phase"] = phase
    prog["step"] = step
    prog["percent"] = int(round(step * 100.0 / max(1, prog.get("total_steps", 5))))
    if text:
        _ev_log(prog, text)
    _write_evolve_progress(prog)


def evolve_status():
    """给前端轮询：当前人格演化进度。"""
    prog = _read_evolve_progress()
    running = bool(_evolve_work.get("running"))
    # 自愈：进度文件说「还在跑」，但本进程里其实没有演化线程
    # （多半是上次演化中途关了软件，留下了孤儿状态）→ 标记为已结束，让前端解卡。
    if prog.get("active") and not running:
        prog["active"] = False
        if prog.get("phase") not in ("done", "error"):
            prog["phase"] = "error"
            prog["ok"] = False
            if not prog.get("message"):
                prog["message"] = "上次演化被中断了（软件中途关闭）。可以重新点「立即演化一次」。"
            _ev_log(prog, "⚠ 检测到上次演化未完成（软件中途关闭），已结束。")
        prog["finished_at"] = prog.get("finished_at") or _now_str()
        _write_evolve_progress(prog)
    prog["running"] = running
    return {"ok": True, "progress": prog}


def _local_client_and_model(use_local, model):
    """这些"懂你"的提炼任务属于轻量本机活：默认用本地小模型，快、私密、稳。
    若调用方传了本地模型就用它，否则回退 qwen2.5；网页模型这里不用（慢/会弹窗）。"""
    try:
        if use_local and not core.is_web_model(model):
            return core.make_client(True), model
    except Exception:
        pass
    try:
        return core.make_client(True), "qwen2.5"
    except Exception:
        return None, "qwen2.5"


def _ask(use_local, model, prompt, max_chars=4000):
    """问一次模型，返回纯文本回复。失败返回空串，绝不抛。"""
    client, real_model = _local_client_and_model(use_local, model)
    if client is None:
        return ""
    try:
        resp = client.chat.completions.create(
            model=real_model,
            messages=[{"role": "user", "content": prompt[:8000]}])
        return (resp.choices[0].message.content or "").strip()[:max_chars]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════════
#  共用：收集最近的对话语料（给 ① ② 用）
# ════════════════════════════════════════════════════════════════════

def _recent_conversation_corpus(limit_chars=6000, max_files=12):
    """把最近几段对话存档拼成一段语料，给演化/关系抽取分析用。
    读 memory/conversations/conv-*.md（你现有的对话存档），新的优先。"""
    conv_dir = core.MEMORY_DIR / "conversations"
    if not conv_dir.exists():
        return ""
    try:
        files = sorted(conv_dir.glob("conv-*.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    except Exception:
        return ""
    parts, total = [], 0
    for p in files:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        total += len(txt)
        parts.append(txt)
        if total >= limit_chars:
            break
    corpus = "\n\n---\n\n".join(parts)
    return corpus[:limit_chars]


def _growth_library_corpus(limit_chars=2500, max_files=8):
    """从成长库（video_notes 视频笔记 + briefings 情报简报）取一些内容，
    作为演化画像的补充语料——你看过/做过的内容也反映你关注什么。尽力而为。"""
    roots = [core.MEMORY_DIR / "video_notes", core.MEMORY_DIR / "briefings"]
    files = []
    for r in roots:
        if not r.exists():
            continue
        try:
            files += list(r.glob("*.md"))
        except Exception:
            continue
    if not files:
        return ""
    try:
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    except Exception:
        files = files[:max_files]
    parts, total = [], 0
    for p in files:
        try:
            # 只取每篇前面一部分（标题+开头），够反映"关注什么"即可，不灌满
            txt = p.read_text(encoding="utf-8", errors="replace")[:600]
        except Exception:
            continue
        total += len(txt)
        parts.append(txt)
        if total >= limit_chars:
            break
    return ("\n\n---\n\n".join(parts))[:limit_chars]


# ════════════════════════════════════════════════════════════════════
#  ① 人格演化
# ════════════════════════════════════════════════════════════════════

def _distill_person_clues(insight, growth, use_local, model, prog=None):
    """第一层抽象：把「视频/文章的内容摘要」转成「关于主人这个人的线索」。
    关键：输出的是对人的判断（关注什么、什么价值观、在学/在做什么），
    而不是复述这些内容讲了啥。弱模型若直接看内容容易跑偏成读后感，故先做这步。"""
    material = ""
    if insight and insight.strip():
        material += "=== 逐篇精读摘要 ===\n" + insight[:4000] + "\n\n"
    if growth and growth.strip():
        material += "=== 成长库内容片段 ===\n" + growth[:2000] + "\n\n"
    if not material.strip():
        if prog is not None:
            _ev_log(prog, "（没有成长库材料可蒸馏，跳过这步）")
        return ""
    if prog is not None:
        _ev_log(prog, "🧪 把 %d 字的内容材料蒸馏成「关于你这个人」的线索…" % len(material))
        _write_evolve_progress(prog)
    prompt = (
        "下面是主人在软件里积累的视频笔记 / 情报 / 文章的内容摘要。\n"
        "你的任务**不是**总结这些内容讲了什么，而是**透过这些内容，推断主人是个什么样的人**。\n\n"
        "请只输出「关于主人这个人」的线索，每条一行，越具体越好：\n"
        "- 他长期关注/感兴趣的领域或主题（从他反复看的内容推断）\n"
        "- 他可能的价值观、立场倾向、思维偏好\n"
        "- 他可能正在学习、研究或推进的事\n"
        "- 他的知识水平 / 身份角色的线索（如果能看出）\n\n"
        "严格要求：\n"
        "① 主语必须是「主人」，是对人的判断，不是对内容的复述。\n"
        "② 绝对不要出现「视频讲了」「作者指出」「本文认为」这类复述内容的句子。\n"
        "③ 绝对不要照抄视频标题或章节标题。\n"
        "④ 没把握的别编。\n\n"
        "错误示例（这是复述内容，不要这样）：『认知误区的根源：现代框架对历史的误读』\n"
        "正确示例（这是关于人的线索）：『主人对历史叙事与文明比较有浓厚兴趣，倾向批判西方中心主义视角』\n\n"
        + material + "直接输出关于主人的线索（每行一条）：")
    out = _ask(use_local, model, prompt, max_chars=2000)
    if prog is not None:
        if out and out.strip():
            n = len([x for x in out.splitlines() if x.strip()])
            _ev_log(prog, "✓ 蒸馏出 %d 条关于你的线索" % n)
        else:
            _ev_log(prog, "⚠ 这步没出结果（本地模型可能没启动），将仅凭对话演化")
        _write_evolve_progress(prog)
    return out


def evolve_personality(use_local=True, model="qwen2.5", prog=None):
    """
    读最近对话 + 成长库线索 → 让模型总结"你是个什么样的人、怎么说话、关注什么"
    → 覆盖写 OWNER_PROFILE.md（注入系统提示）+ 在 evolution_log.md 记一笔。

    两层抽象，避免画像跑偏成「视频读后感」：
      ① 先把视频/文章摘要蒸馏成「关于主人这个人的线索」（_distill_person_clues）。
      ② 再结合对话，写成关于人的画像（主语必须是「你/主人」）。

    传入 prog（进度字典）时，会把每一步实时写进 evolve_progress.json，供前端轮询显示。
    返回 {"ok": bool, "profile": str, "message": str}。
    """
    mlabel = _model_label(use_local, model)
    if prog is not None:
        prog["model"] = mlabel

    # —— 第 1 步：收集材料 ——
    if prog is not None:
        _ev_step(prog, "collecting", 1, "📥 正在收集材料：读你的对话存档、长期记忆、成长库…")
    corpus = _recent_conversation_corpus()
    long_term = _read("MEMORY.md")
    growth = _growth_library_corpus()
    insight = ""
    try:
        import insight_crawler
        insight = insight_crawler.digests_corpus(limit_chars=4500)
    except Exception:
        insight = ""

    if prog is not None:
        conv_n = (corpus or "").count("\n\n---\n\n") + (1 if corpus else 0)
        _ev_log(prog, "· 对话存档：约 %d 段、%d 字" % (conv_n, len(corpus or "")))
        _ev_log(prog, "· 长期记忆：%d 字" % len(long_term or ""))
        _ev_log(prog, "· 成长库精读线索：%d 字" % len(insight or ""))
        _ev_log(prog, "· 本次用模型：%s" % mlabel)
        # 结构化的「参考资料源」，前端渲染成可点击跳转的链接
        prog["sources"] = [
            {"label": "对话存档", "detail": "约 %d 段 · %d 字" % (conv_n, len(corpus or "")),
             "link": {"view": "datadb", "cat": "conversations"}},
            {"label": "长期记忆", "detail": "%d 字 · MEMORY.md" % len(long_term or ""),
             "link": {"view": "datadb", "cat": "memory", "name": "MEMORY.md"}},
            {"label": "成长库精读线索", "detail": "%d 字 · 洞察「每篇理解」" % len(insight or ""),
             "link": {"view": "insight", "tab": "detail"}},
            {"label": "成长库原文", "detail": "%d 字 · 最近视频/情报" % len(growth or ""),
             "link": {"view": "datadb", "cat": "video"}},
        ]
        _write_evolve_progress(prog)

    if (not corpus and not long_term.strip() and not growth.strip()
            and not insight.strip()):
        msg = "还没有足够的对话/成长库内容，多聊几次或多积累点内容再来演化。"
        if prog is not None:
            _ev_step(prog, "error", 1, "✗ " + msg)
        return {"ok": False, "message": msg}

    # —— 第 2 步：蒸馏「关于人的线索」（关键防跑偏步骤）——
    if prog is not None:
        _ev_step(prog, "distilling", 2, "🧪 第一层抽象：从你看过的内容里推断「你是个什么样的人」…")
    person_clues = ""
    if insight.strip() or growth.strip():
        try:
            person_clues = _distill_person_clues(insight, growth, use_local, model, prog)
        except Exception:
            person_clues = ""
    elif prog is not None:
        _ev_log(prog, "（没有成长库材料，跳过蒸馏，直接看对话）")
        _write_evolve_progress(prog)

    prev = _read(OWNER_PROFILE).strip()
    # —— 第 3 步：写画像。强约束：主语是「你」，是对人的判断，不许复述内容 ——
    if prog is not None:
        base = "📝 第二层：结合对话，总结成「关于你这个人」的画像…"
        if prev:
            base += "（在上次画像基础上演化）"
        _ev_step(prog, "synthesizing", 3, base)
    prompt = (
        "你是一个善于观察的私人助理。你的任务是写一份**关于主人本人**的画像，"
        "帮你今后更懂他、说话更对他的频道、并能主动为他找他会感兴趣的知识。\n\n"
        "⚠️ 最重要的规则：画像写的是**主人这个人**，不是他看过的内容。\n"
        "- 每一条的主语都应该是「你/主人」。\n"
        "- 绝对不要复述视频/文章讲了什么，不要出现「视频指出」「作者认为」之类。\n"
        "- 绝对不要把视频标题、章节标题当成画像内容。\n"
        "- 要做的是：从他聊的话题、看的内容里，**推断他是个什么样的人**。\n\n"
        "严格按下面结构输出 Markdown（每条简短、具体、是对人的判断，没把握的别编）：\n"
        "## 你是个什么样的人\n用 3-5 句描述主人：大概的身份/角色、性格或思维特点、"
        "处事风格。这是整份画像的核心。\n\n"
        "## 说话风格\n2-4 句：偏正式还是随意、直接还是委婉、话多还是话少、"
        "有没有口头禅或常用词。\n\n"
        "## 关注的领域\n列 3-6 条主人长期关注/感兴趣的领域或主题（每条几个字，"
        "是「他关注X」，不是某个视频的标题）。\n\n"
        "## 偏好与习惯\n3-6 条：喜欢怎样的回答（简洁/详细）、做事习惯、在意什么、讨厌什么。\n\n"
        "## 可以主动为他做什么\n2-4 条：基于以上，今后可以主动给他找哪类知识/资讯，"
        "用什么语气和详略跟他相处最合适。\n\n")
    if prev:
        prompt += ("下面是上次的画像，请在其基础上**结合新信息修订/补充**"
                   "（演化而非推翻重来）：\n=== 上次画像 ===\n" + prev[:2000] + "\n\n")
    # 对话最能反映「人」，放在最前、权重最高
    prompt += "=== 最近对话（最能反映主人这个人，重点参考）===\n" + (corpus or "（暂无）") + "\n\n"
    if long_term.strip():
        prompt += "=== 长期记忆 ===\n" + long_term[-2500:] + "\n\n"
    # 用蒸馏后的「关于人的线索」，而不是原始视频内容，避免跑偏
    if person_clues.strip():
        prompt += ("=== 从主人看过的内容里推断出的「关于他这个人」的线索 ===\n"
                   + person_clues + "\n\n")
    elif insight.strip():
        # 蒸馏失败的兜底：仍提供原料，但明确警告别复述
        prompt += ("=== 主人看过的内容（仅供推断他关注什么，切勿复述其内容、"
                   "切勿照抄标题）===\n" + insight[:2500] + "\n\n")
    prompt += "直接输出画像（记住：写的是主人这个人，不是内容）："

    profile = _ask(use_local, model, prompt, max_chars=4000)
    if not profile or len(profile) < 20:
        msg = "演化没成功（模型没给出有效画像），稍后再试。"
        if prog is not None:
            _ev_step(prog, "error", 3, "✗ " + msg)
        return {"ok": False, "message": msg}
    if prog is not None:
        _ev_log(prog, "✓ 画像已生成（%d 字）" % len(profile))
        _write_evolve_progress(prog)

    # —— 第 4 步：写入画像文件 ——
    if prog is not None:
        _ev_step(prog, "writing", 4, "💾 把画像写入 OWNER_PROFILE.md 并注入小助…")
    header = (f"# 关于你（小助观察到的）\n\n"
              f"> 这是超能小助从你历次对话和看过的内容里总结的「你的画像」，会注入到它的"
              f"系统提示里，让它越来越懂你、并能主动为你找你感兴趣的知识。你随时可以改这个"
              f"文件，或在「懂你」里重新演化。最近更新：{_now_str()}\n\n")
    try:
        _mem(OWNER_PROFILE).write_text(header + profile + "\n", encoding="utf-8")
    except Exception as e:
        msg = f"写画像文件失败：{e}"
        if prog is not None:
            _ev_step(prog, "error", 4, "✗ " + msg)
        return {"ok": False, "message": msg}

    # —— 第 5 步：留一份演化快照 ——
    if prog is not None:
        _ev_step(prog, "writing", 5, "🕒 在演化时间线留一份快照…")
    try:
        logp = _mem(EVOLUTION_LOG)
        if not logp.exists():
            logp.write_text("# 人格演化记录\n\n每次演化的留痕，方便你回看小助是怎么"
                            "一步步变得更懂你的。\n\n", encoding="utf-8")
        with logp.open("a", encoding="utf-8") as f:
            f.write(f"## {_now_str()}\n\n{profile}\n\n---\n\n")
    except Exception:
        pass

    if prog is not None:
        _ev_step(prog, "done", 5, "🎉 演化完成，小助更懂你了。")

    return {"ok": True, "profile": profile,
            "message": "演化完成，小助更懂你了。可在「懂你」里查看画像。"}


# —— 后台跑人格演化（立即返回，前端轮询 evolve_status 看进度）——

def _evolve_worker(use_local, model):
    prog = _default_evolve_progress()
    prog.update({
        "active": True, "phase": "collecting", "step": 0, "percent": 0,
        "started_at": _now_str(), "model": _model_label(use_local, model),
        "activity": [], "ok": None, "message": "",
    })
    _ev_log(prog, "🚀 开始人格演化")
    _write_evolve_progress(prog)
    try:
        res = evolve_personality(use_local=use_local, model=model, prog=prog)
        prog["ok"] = bool(res.get("ok"))
        prog["message"] = res.get("message", "")
        if res.get("ok"):
            prog["phase"] = "done"
            prog["percent"] = 100
        elif prog.get("phase") != "error":
            prog["phase"] = "error"
    except Exception as e:
        prog["phase"] = "error"
        prog["ok"] = False
        prog["message"] = "演化出错：%s" % e
        _ev_log(prog, "✗ 出错：%s" % e)
    finally:
        prog["active"] = False
        prog["finished_at"] = _now_str()
        _write_evolve_progress(prog)
        _evolve_work["running"] = False


def start_evolve(use_local=True, model="qwen2.5"):
    """启动后台人格演化。立即返回；前端轮询 evolve_status 看每一步。"""
    if _evolve_work.get("running"):
        return {"ok": True, "busy": True, "message": "正在演化中…"}
    _evolve_work["running"] = True
    t = threading.Thread(target=_evolve_worker, args=(use_local, model), daemon=True)
    _evolve_work["thread"] = t
    t.start()
    return {"ok": True, "started": True, "message": "已开始演化，进度实时显示。"}


# ════════════════════════════════════════════════════════════════════
#  ② 关系网络
# ════════════════════════════════════════════════════════════════════

def extract_relationships(messages=None, use_local=True, model="qwen2.5"):
    """
    从最近一轮对话（或传入的 messages）里抽取"提到的人"，累积到 relationships.md。
    形如：- 张三：同事，负责后端，上周帮忙改过 bug

    设计成"尽力而为"：抽不到就什么都不做，绝不影响主流程。
    返回 {"ok": bool, "added": [..], "message": str}。
    """
    # 取要分析的文本：优先传入的 messages 最后几轮，否则读最近对话语料
    text = ""
    if messages:
        try:
            tail = []
            for m in messages[-6:]:
                role = m.get("role")
                if role in ("user", "assistant"):
                    c = (m.get("content") or "").strip()
                    if c:
                        who = "用户" if role == "user" else "小助"
                        tail.append(f"{who}：{c[:500]}")
            text = "\n".join(tail)
        except Exception:
            text = ""
    if not text:
        text = _recent_conversation_corpus(limit_chars=3000, max_files=4)
    if not text or len(text) < 10:
        return {"ok": False, "added": [], "message": "没有可分析的对话。"}

    existing = _read(RELATIONS)
    # 把已知的人名提取出来，避免重复添加（简单按行首"- 名字："匹配）
    known = set()
    for line in existing.splitlines():
        m = re.match(r"^\s*-\s*([^:：]{1,20})[:：]", line)
        if m:
            known.add(m.group(1).strip())

    prompt = (
        "下面是一段对话。请找出其中**主人提到的、与主人有关系的具体的人**"
        "（同事、朋友、家人、客户、合作方等有名字或明确称呼的人），"
        "为每个人总结一条简短信息。\n"
        "严格要求：每行一个人，格式 `- 名字：关系，一句话说明（在对话里提到的关于他的事）`。\n"
        "只输出确实是「人」且和主人有关系的；泛指的、不确定的、虚构的、公众人物都不要。"
        "没有就只回复「无」。不要解释，不要编。\n\n"
        f"已经记过的人（不用重复，但若有新信息可补充）：{('、'.join(known)) or '（暂无）'}\n\n"
        "=== 对话 ===\n" + text + "\n\n直接输出：")

    raw = _ask(use_local, model, prompt, max_chars=1500)
    if not raw or raw.strip() in ("无", "无。", "（无）"):
        return {"ok": True, "added": [], "message": "这段对话没提到需要记的人。"}

    # 解析模型给的行，挑出 "- 名字：..." 形式的
    added = []
    new_lines = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^[-•]\s*([^:：]{1,20})[:：]\s*(.+)$", line)
        if not m:
            continue
        name = m.group(1).strip()
        info = m.group(2).strip()
        if not name or name in ("无", "无人", "用户", "主人", "小助"):
            continue
        if name in known:
            continue  # 已记过，这次先不重复（避免越长越乱）
        new_lines.append(f"- {name}：{info}")
        added.append(name)

    if not new_lines:
        return {"ok": True, "added": [], "message": "没有新的人需要记。"}

    try:
        p = _mem(RELATIONS)
        if not p.exists():
            p.write_text("# 关系网络\n\n超能小助从对话里记下的、和你有关系的人。"
                         "你随时能改。\n\n", encoding="utf-8")
        with p.open("a", encoding="utf-8") as f:
            for ln in new_lines:
                f.write(ln + "\n")
    except Exception as e:
        return {"ok": False, "added": [], "message": f"写关系文件失败：{e}"}

    return {"ok": True, "added": added,
            "message": "记下了：" + "、".join(added)}


# ════════════════════════════════════════════════════════════════════
#  ③ 主动问候 / 返回摘要
# ════════════════════════════════════════════════════════════════════

def _time_period():
    h = datetime.datetime.now().hour
    if h < 6:
        return "凌晨"
    if h < 11:
        return "早上"
    if h < 14:
        return "中午"
    if h < 18:
        return "下午"
    if h < 23:
        return "晚上"
    return "深夜"


def make_greeting(use_local=True, model="qwen2.5"):
    """生成一句结合时间+记忆的个性化问候。失败返回一句兜底问候。"""
    period = _time_period()
    profile = _read(OWNER_PROFILE)[:1200]
    long_term = _read("MEMORY.md")[-1200:]
    prompt = (
        f"现在是{period}。请用主人习惯的语气，对主人说一句简短自然的问候"
        f"（一句话，最多两句，别肉麻、别太正式）。如果下面的画像/记忆里有"
        f"合适的点（比如他在忙的事、最近关心的），可以自然带一句，但不要硬凑。\n\n"
        f"=== 主人画像 ===\n{profile or '（暂无）'}\n\n"
        f"=== 长期记忆 ===\n{long_term or '（暂无）'}\n\n直接输出问候：")
    out = _ask(use_local, model, prompt, max_chars=200)
    if not out:
        return {"ok": True, "greeting": f"{period}好，有什么要我做的？"}
    # 去掉模型可能加的引号
    out = out.strip().strip('“”"\'').splitlines()[0].strip()
    return {"ok": True, "greeting": out or f"{period}好。"}


def make_return_summary(notes_text="", use_local=True, model="qwen2.5"):
    """你离开回来时，把后台（心跳）干的事总结成一两句话。
    notes_text 可传当天笔记内容；不传就读当天的 note 文件。"""
    if not notes_text:
        today = _today()
        notes_text = _read(f"note-{today}.md")
    if not notes_text.strip():
        return {"ok": True, "summary": ""}
    prompt = (
        "下面是超能小助在主人离开期间，后台自动做的事的流水记录。"
        "请用一两句话向主人总结「你不在的时候我做了这些」，简洁、口语、"
        "只说有意义的，没价值的流水别提。\n\n=== 后台记录 ===\n"
        + notes_text[-2000:] + "\n\n直接输出总结：")
    out = _ask(use_local, model, prompt, max_chars=400)
    return {"ok": True, "summary": out}


# ════════════════════════════════════════════════════════════════════
#  ④ 系统扫描 / 职业检测
# ════════════════════════════════════════════════════════════════════

# 软件名关键词 → 职业线索（粗匹配，够用就行）
_PROFESSION_HINTS = {
    "设计师": ["photoshop", "illustrator", "figma", "sketch", "coreldraw",
               "premiere", "after effects", "indesign", "blender", "lightroom",
               "procreate", "affinity"],
    "程序员/工程师": ["visual studio", "vscode", "code", "pycharm", "intellij",
                       "android studio", "git", "docker", "node", "python",
                       "sublime", "webstorm", "goland", "xcode", "postman"],
    "视频创作者": ["premiere", "after effects", "davinci", "剪映", "capcut",
                   "obs", "vegas", "final cut"],
    "办公/文职": ["word", "excel", "powerpoint", "wps", "outlook", "onenote",
                  "teams", "钉钉", "飞书", "tableau"],
    "医生/医疗": ["his", "pacs", "病历", "dicom"],
    "律师/法务": ["威科先行", "北大法宝", "alpha", "合同", "案例库"],
    "教师/教育": ["希沃", "课件", "classin", "雨课堂", "智学网"],
    "音乐人": ["cubase", "fl studio", "logic", "ableton", "studio one", "audition"],
    "游戏开发": ["unity", "unreal", "godot", "gamemaker"],
    "数据/科研": ["matlab", "spss", "stata", "origin", "rstudio", "jupyter",
                  "anaconda", "tableau"],
}


def _list_installed_apps_windows():
    """扫 Windows 已装软件名（从开始菜单快捷方式 + Program Files 目录名）。
    只读、不动任何文件。返回小写软件名集合。"""
    names = set()
    # 1) 开始菜单快捷方式（.lnk 文件名最能反映"用户认知里的软件名"）
    roots = []
    for env in ("ProgramData", "APPDATA"):
        base = os.environ.get(env)
        if base:
            roots.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    for r in roots:
        try:
            if r.exists():
                for p in r.rglob("*.lnk"):
                    names.add(p.stem.lower())
        except Exception:
            continue
    # 2) Program Files 目录名兜底
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if not base:
            continue
        try:
            for p in Path(base).iterdir():
                if p.is_dir():
                    names.add(p.name.lower())
        except Exception:
            continue
    return names


def _detect_professions(app_names):
    """按软件名关键词推断职业，返回 [(职业, 命中数), ...] 按命中降序。"""
    blob = " ".join(app_names)
    scores = []
    for prof, kws in _PROFESSION_HINTS.items():
        hits = sum(1 for kw in kws if kw in blob)
        if hits:
            scores.append((prof, hits))
    scores.sort(key=lambda x: -x[1])
    return scores


def scan_environment(use_local=True, model="qwen2.5", write=True):
    """
    扫描本机环境（系统信息 + 已装软件 + 推断职业），写进 ENVIRONMENT.md（注入系统提示）。
    依赖「电脑操作权限」的扫描是只读的；没有 psutil 等也能降级跑。

    返回 {"ok": bool, "summary": str, "professions": [...], "message": str}。
    """
    import platform
    lines = []
    # 系统基础信息（标准库）
    try:
        lines.append(f"- 操作系统：{platform.platform()}")
        lines.append(f"- 主机名：{platform.node()}")
    except Exception:
        pass
    # 内存/CPU（有 psutil 就报）
    try:
        import psutil
        vm = psutil.virtual_memory()
        lines.append(f"- 内存：共 {round(vm.total/1024/1024/1024)} GB")
        lines.append(f"- CPU 逻辑核心：{psutil.cpu_count()}")
    except Exception:
        pass

    # 已装软件 + 职业推断（仅 Windows 扫得全；其它系统跳过软件扫描）
    apps = set()
    profs = []
    try:
        if platform.system() == "Windows":
            apps = _list_installed_apps_windows()
            profs = _detect_professions(apps)
    except Exception:
        apps, profs = set(), []

    if profs:
        prof_str = "、".join(f"{p}（线索 {n} 条）" for p, n in profs[:3])
        lines.append(f"- 推断职业方向：{prof_str}")

    # 挑一些"有代表性"的软件名给模型，让它写一句自然的环境画像
    notable = []
    blob = " ".join(apps)
    for prof, kws in _PROFESSION_HINTS.items():
        for kw in kws:
            if kw in blob and kw not in notable:
                notable.append(kw)
    notable = notable[:15]

    env_facts = "\n".join(lines)
    summary = env_facts
    # 让模型把这些事实润成一两句"环境画像"，更像人话（失败就用事实本身）
    if notable or profs:
        prompt = (
            "下面是主人电脑的环境信息和装的一些代表性软件。请用一两句话总结"
            "主人大概是做什么的、电脑上常用什么类型的工具，作为「了解主人环境」的"
            "备注。客观、简短，别夸张、别编没有的。\n\n"
            f"环境：\n{env_facts}\n\n代表性软件：{('、'.join(notable)) or '（未扫到）'}\n\n"
            "直接输出一两句话：")
        s = _ask(use_local, model, prompt, max_chars=400)
        if s:
            summary = s

    if write:
        try:
            header = (f"# 你的环境画像\n\n> 超能小助扫描本机得到的环境信息"
                      f"（已装软件、推断职业等），用来让回答更贴合你的真实情况。"
                      f"只读扫描、不上传。最近扫描：{_now_str()}\n\n")
            body = ""
            if summary and summary != env_facts:
                body += summary + "\n\n"
            body += "## 环境信息\n" + (env_facts or "（未扫到）") + "\n"
            _mem(ENVIRONMENT).write_text(header + body, encoding="utf-8")
        except Exception as e:
            return {"ok": False, "summary": summary,
                    "professions": [p for p, _ in profs],
                    "message": f"写环境文件失败：{e}"}

    return {"ok": True, "summary": summary,
            "professions": [p for p, _ in profs],
            "message": "扫描完成，已更新环境画像。"}


# ════════════════════════════════════════════════════════════════════
#  给 build_system_prompt 用：把"懂你"几块拼成一段可注入的文本
# ════════════════════════════════════════════════════════════════════

def build_context_block():
    """把 OWNER_PROFILE / relationships / ENVIRONMENT 三块拼成一段，
    供 agent_core.build_system_prompt() 注入。空的不注入，控制长度。"""
    blocks = []
    profile = _read(OWNER_PROFILE).strip()
    if profile:
        # 去掉文件顶部的说明引语，只留正文
        profile = re.sub(r"^#.*?\n+(> .*?\n+)?", "", profile, count=1, flags=re.S)
        blocks.append("=== 关于你（小助的观察 OWNER_PROFILE.md）===\n"
                      + profile[:2500])
    rel = _read(RELATIONS).strip()
    if rel:
        rel = re.sub(r"^#.*?\n+", "", rel, count=1, flags=re.S)
        blocks.append("=== 你的关系网络 (relationships.md) ===\n" + rel[:1800])
    env = _read(ENVIRONMENT).strip()
    if env:
        env = re.sub(r"^#.*?\n+(> .*?\n+)?", "", env, count=1, flags=re.S)
        blocks.append("=== 你的环境画像 (ENVIRONMENT.md) ===\n" + env[:1200])
    # 「洞察」爬虫对成长库的分析理解（有才注入，失败安静跳过）
    try:
        import insight_crawler
        ins = insight_crawler.build_context_block()
        if ins and ins.strip():
            blocks.append(ins)
    except Exception:
        pass
    return "\n\n".join(blocks)
