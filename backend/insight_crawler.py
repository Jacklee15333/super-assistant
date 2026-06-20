"""
insight_crawler.py — 「洞察」爬虫：逐篇深读成长库 → 形成学习数据 → 真正更懂使用者

和「📡 嗅探」相反：嗅探爬外部网站；「洞察」爬你**自己**积累在软件里的内容
（视频笔记 / 情报简报 / 嗅探简报 / 学习档案 / 对话存档 / 每日笔记 / 长期记忆）。

核心是两步深读管线（解决「文件太多，AI 只看标题导致演化不准」的问题）：
  ① 爬取：爬虫逐个定位文件，列出全部待读清单（带总数/进度）。
  ② 阅读学习：把每篇**单独通读一遍**，让 AI 提炼这篇讲什么、反映你关注什么，
     形成「每篇的学习数据」落盘缓存（memory/insight_digests.json）。
  ③ 汇总：把所有学习数据汇总成「对你的理解」，注入小助系统提示。
人格演化（lumi_features.evolve_personality）会优先使用这份深读数据，于是更准。

特性：
  · 进度：总共多少篇、已读多少篇、当前在读哪篇，实时显示。
  · 实时活动：正在爬哪篇 / 派给 AI 哪篇 / 已学习什么，逐条留痕。
  · 断点续传：进度持久化到 memory/insight_progress.json，关软件再开能接着跑。
  · 增量：已读且未改动的文件不重复读，下次只读新增/改过的，省时间。

设计原则：标准库优先、全本机、失败安静降级、绝不把主流程搞崩；定时线程复用心跳模式。
"""

import os
import json
import datetime
import threading

import agent_core as core


MEMORY_DIR = core.MEMORY_DIR
CONFIG_PATH = MEMORY_DIR / "insight_config.json"
RUNS_PATH = MEMORY_DIR / "insight_runs.json"
DIGESTS_PATH = MEMORY_DIR / "insight_digests.json"     # 每篇的学习数据（缓存）
PROGRESS_PATH = MEMORY_DIR / "insight_progress.json"   # 当前任务进度（断点续传）
REPORTS_DIR = MEMORY_DIR / "insight_reports"
LATEST_PATH = MEMORY_DIR / "INSIGHT_LATEST.md"         # 最近一次完整报告
DIGEST_PATH = MEMORY_DIR / "INSIGHT_DIGEST.md"         # 注入系统提示的精简理解
RESEARCH_DIR = MEMORY_DIR / "insight_research"         # 主动上网研究的成果（落进成长库）

MAX_RUNS = 50
MAX_REPORTS = 30
MAX_ACTIVITY = 40          # 实时活动最多留多少条
MAX_RESEARCH = 40          # 主动研究成果最多留多少篇
PER_FILE_READ_CHARS = 6000  # 每篇喂给 AI 的正文上限（够读完这些笔记）
RESEARCH_TOPICS_MAX = 4     # 每次洞察后最多主动研究几个话题


# ════════════════════════════════════════════════════════════════════
#  小工具
# ════════════════════════════════════════════════════════════════════

def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _now_clock():
    return datetime.datetime.now().strftime("%H:%M:%S")


def _now_stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return True
    except Exception:
        return False


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════
#  配置
# ════════════════════════════════════════════════════════════════════

# 爬取范围：键 → 中文名
SCOPE_LABELS = {
    "video":         "视频内容库",
    "info":          "情报简报",
    "sniff":         "嗅探简报",
    "learning":      "学习档案",
    "conversations": "对话存档",
    "notes":         "每日笔记",
    "memory":        "长期记忆",
    "research":      "主动研究",
}


def default_config():
    return {
        "auto": False,                 # 是否定时自动爬取分析
        "mode": "interval",            # interval=每隔几小时 / daily=每天固定时间
        "interval_hours": 24,
        "daily_at": "03:00",
        "scopes": {k: True for k in SCOPE_LABELS},
        "read_local": True,            # 逐篇精读用本地模型（快/免费/私密，推荐）
        "use_local": False,            # 汇总用本地还是云端
        "model": "",                   # 汇总模型，空=跟随软件默认
        "apply_to_agent": True,        # 是否把理解注入小助系统提示
        "auto_research": False,        # 洞察后是否主动上网搜相关内容，存进成长库（默认关）
    }


def get_config():
    cfg = default_config()
    saved = _read_json(CONFIG_PATH, {})
    if isinstance(saved, dict):
        cfg.update(saved)
        sc = default_config()["scopes"]
        sc.update(saved.get("scopes") or {})
        cfg["scopes"] = {k: bool(sc.get(k, True)) for k in SCOPE_LABELS}
    return _sanitize(cfg)


def save_config(patch):
    cfg = get_config()
    if isinstance(patch, dict):
        if "scopes" in patch and isinstance(patch["scopes"], dict):
            sc = cfg["scopes"]
            for k in SCOPE_LABELS:
                if k in patch["scopes"]:
                    sc[k] = bool(patch["scopes"][k])
            cfg["scopes"] = sc
        for k in ("auto", "mode", "interval_hours", "daily_at", "read_local",
                  "use_local", "model", "apply_to_agent", "auto_research"):
            if k in patch:
                cfg[k] = patch[k]
    cfg = _sanitize(cfg)
    _write_json(CONFIG_PATH, cfg)
    try:
        _reconcile_scheduler(cfg)
    except Exception:
        pass
    return get_config()


def _sanitize(cfg):
    cfg["auto"] = bool(cfg.get("auto", False))
    cfg["read_local"] = bool(cfg.get("read_local", True))
    cfg["apply_to_agent"] = bool(cfg.get("apply_to_agent", True))
    cfg["auto_research"] = bool(cfg.get("auto_research", False))
    try:
        cfg["interval_hours"] = max(1, int(cfg.get("interval_hours", 24)))
    except Exception:
        cfg["interval_hours"] = 24
    if cfg.get("mode") not in ("interval", "daily"):
        cfg["mode"] = "interval"
    at = str(cfg.get("daily_at", "03:00"))
    try:
        hh, mm = at.split(":")
        cfg["daily_at"] = "%02d:%02d" % (int(hh) % 24, int(mm) % 60)
    except Exception:
        cfg["daily_at"] = "03:00"
    return cfg


# ════════════════════════════════════════════════════════════════════
#  枚举目标文件（爬取清单）
# ════════════════════════════════════════════════════════════════════

def _scope_files(scope):
    """某个范围 → [文件路径]，按修改时间新→旧。"""
    MEM = MEMORY_DIR
    BACKEND = MEM.parent
    out = []
    try:
        if scope == "video":
            d = MEM / "video_notes"
            if d.exists():
                out = list(d.glob("*.md"))
        elif scope == "info":
            d = MEM / "briefings"
            if d.exists():
                out = list(d.glob("*.md"))
        elif scope == "sniff":
            d = MEM / "sniff_reports"
            if d.exists():
                out = list(d.glob("*.md"))
        elif scope == "learning":
            d = BACKEND / "学生档案"
            if d.exists():
                out = list(d.glob("*.md"))
        elif scope == "conversations":
            d = MEM / "conversations"
            if d.exists():
                out = list(d.glob("conv-*.md"))
        elif scope == "notes":
            out = list(MEM.glob("note-*.md"))
        elif scope == "memory":
            p = MEM / "MEMORY.md"
            if p.exists():
                out = [p]
        elif scope == "research":
            d = MEM / "insight_research"
            if d.exists():
                out = list(d.glob("research-*.md"))
        out = sorted(out, key=lambda x: x.stat().st_mtime, reverse=True)
    except Exception:
        pass
    return out


def _first_title(txt, fallback):
    for line in (txt or "").splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:60]
    return fallback


def _file_meta(path, scope):
    try:
        st = path.stat()
        mtime = int(st.st_mtime)
        size = st.st_size
    except Exception:
        mtime, size = 0, 0
    return {
        "key": str(path),
        "path": str(path),
        "scope": scope,
        "label": SCOPE_LABELS.get(scope, scope),
        "name": path.stem[:60],
        "mtime": mtime,
        "size": size,
    }


def enumerate_targets(scopes):
    targets = []
    for scope in SCOPE_LABELS:
        if not (scopes or {}).get(scope):
            continue
        for p in _scope_files(scope):
            targets.append(_file_meta(p, scope))
    return targets


def available_counts():
    counts = {}
    total = 0
    for scope in SCOPE_LABELS:
        n = len(_scope_files(scope))
        counts[scope] = n
        total += n
    return counts, total


# ════════════════════════════════════════════════════════════════════
#  每篇的学习数据（缓存）
# ════════════════════════════════════════════════════════════════════

def _load_digests():
    d = _read_json(DIGESTS_PATH, {})
    return d if isinstance(d, dict) else {}


def _save_digests(d):
    _write_json(DIGESTS_PATH, d)


def digests_count():
    return len(_load_digests())


def digests_corpus(limit_chars=4000, scopes=None):
    """把已学习的每篇精读结果拼成语料，供人格演化等使用（新→旧）。"""
    d = _load_digests()
    items = list(d.values())
    try:
        items.sort(key=lambda x: x.get("read_at", ""), reverse=True)
    except Exception:
        pass
    parts, total = [], 0
    for it in items:
        if scopes is not None and not scopes.get(it.get("scope")):
            continue
        blk = "【%s】%s\n%s" % (it.get("label", ""), it.get("title", ""),
                               (it.get("digest", "") or "").strip())
        parts.append(blk)
        total += len(blk)
        if total >= limit_chars:
            break
    return ("\n\n".join(parts))[:limit_chars]


# ════════════════════════════════════════════════════════════════════
#  进度（断点续传）
# ════════════════════════════════════════════════════════════════════

def _default_progress():
    return {
        "active": False,        # 是否有任务在进行
        "phase": "idle",        # idle/reading/synthesizing/researching/done/stopped/error
        "total": 0,             # 本轮总篇数
        "done": 0,              # 已处理篇数
        "learned": 0,           # 本轮新读到的篇数
        "current": None,        # {name, scope, index}
        "queue": [],            # 还没读的文件元数据
        "activity": [],         # 实时活动日志
        # —— 文件级清单（供「研究详情页」报告：哪些已读/还剩/跳过）——
        "read_files": [],       # 已读：[{name, scope, label, chars, at}]
        "skipped_files": [],    # 跳过：[{name, scope, label, reason}]
        # —— 主动上网研究 ——
        "research": [],         # 本轮研究：[{topic, status, sources, saved, at}]
        "started_at": "",
        "finished_at": "",
        "source": "",
        "read_local": True,
        "use_local": False,
        "model": "",
        "auto_research": False,
        "scopes": {},
    }


def _load_progress():
    p = _read_json(PROGRESS_PATH, None)
    if not isinstance(p, dict):
        return _default_progress()
    base = _default_progress()
    base.update(p)
    return base


def _save_progress(prog):
    _write_json(PROGRESS_PATH, prog)


def _log(prog, text):
    prog.setdefault("activity", [])
    prog["activity"].append("%s  %s" % (_now_clock(), text))
    prog["activity"] = prog["activity"][-MAX_ACTIVITY:]


# ════════════════════════════════════════════════════════════════════
#  调模型
# ════════════════════════════════════════════════════════════════════

def _resolve_model(use_local, model):
    if model:
        return bool(use_local), model
    try:
        ul, m = core.resolve_model("default", fallback_use_local=True,
                                   fallback_model="qwen2.5")
        return ul, m
    except Exception:
        return True, "qwen2.5"


def _ask(use_local, model, prompt, max_chars=6000):
    try:
        client = core.make_client_for(model, use_local)
    except Exception:
        return ""
    if client is None:
        return ""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt[:16000]}])
        return (resp.choices[0].message.content or "").strip()[:max_chars]
    except Exception:
        return ""


def _read_file_with_ai(text, label, name, read_local):
    """让 AI 通读一篇，提炼 3-5 个要点（讲什么 + 反映主人关注什么）。"""
    if read_local:
        ul, m = True, "qwen2.5"
    else:
        ul, m = _resolve_model(get_config().get("use_local", False),
                               get_config().get("model", ""))
    prompt = (
        "下面是主人收藏或产生的一篇内容（来源：%s）。请你**通读全文**后，"
        "用 3-5 个简短要点提炼：这篇在讲什么、它反映出主人关注/在意/在学/在做什么。"
        "只基于原文，中文，不要寒暄、不要复述标题。\n\n"
        "标题：%s\n\n正文：\n%s\n\n直接输出要点："
        % (label, name, (text or "")[:PER_FILE_READ_CHARS]))
    return _ask(ul, m, prompt, max_chars=800)


def _synthesize(digests, prog):
    """把所有学习数据汇总成「对主人的理解」报告。"""
    items = list(digests.values())
    try:
        items.sort(key=lambda x: x.get("read_at", ""), reverse=True)
    except Exception:
        pass
    parts, total = [], 0
    for it in items:
        blk = "【%s】%s\n%s" % (it.get("label", ""), it.get("title", ""),
                               (it.get("digest", "") or "").strip())
        parts.append(blk)
        total += len(blk)
        if total >= 16000:
            break
    corpus = "\n\n".join(parts)
    if not corpus.strip():
        return ""

    import lumi_features as lf
    prev_profile = lf._read(lf.OWNER_PROFILE)

    n = len(items)
    prompt = (
        "你是一个善于观察的私人助理。下面是对主人积累在软件里的内容**逐篇精读后**"
        "得到的要点（共 %d 篇：视频笔记/情报/嗅探/学习/对话等）。请通读这些要点，"
        "真实地总结出「主人是个什么样的人、最近在关注/在做什么」。\n\n"
        "严格按下面结构输出 Markdown（每条都简短、具体，基于材料里真实出现的内容，"
        "没把握的别编）：\n"
        "## 最近在关注什么\n列 3-6 条主人近期最关注的主题/领域。\n\n"
        "## 在学 / 在做什么\n2-4 条，主人正在学习或推进的事。\n\n"
        "## 我对主人的理解（画像增量）\n3-6 条，从这些内容看出的、关于主人的判断。\n\n"
        "## 给小助的相处建议\n2-4 句，今后该用什么语气、详略、避免什么。\n\n"
        "## 一句话理解\n用一句话概括「主人是谁、要什么」。\n\n" % n)
    if (prev_profile or "").strip():
        prompt += ("=== 已有画像（OWNER_PROFILE.md，供对比，不要照抄）===\n"
                   + prev_profile[:1500] + "\n\n")
    prompt += "=== 逐篇精读要点 ===\n" + corpus + "\n\n直接输出分析："

    cfg = get_config()
    ul = prog.get("use_local", cfg.get("use_local", False))
    m = prog.get("model", cfg.get("model", ""))
    ul, m = _resolve_model(ul, m)
    return _ask(ul, m, prompt, max_chars=6000)


def _save_report(report):
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    header = ("# 洞察报告 · %s\n\n> 小助逐篇精读你的成长库后，对「你」的理解。\n\n"
              % _now_str())
    full = header + (report or "").strip() + "\n"
    try:
        (REPORTS_DIR / ("insight-%s.md" % _now_stamp())).write_text(full, encoding="utf-8")
        _prune_reports()
    except Exception:
        pass
    try:
        LATEST_PATH.write_text(full, encoding="utf-8")
    except Exception:
        pass
    if get_config().get("apply_to_agent", True):
        try:
            DIGEST_PATH.write_text(
                "# 小助对你的洞察理解\n\n> 由「洞察」逐篇精读你的成长库得出，"
                "会注入小助的系统提示，让它更懂你。最近更新：%s\n\n" % _now_str()
                + (report or "").strip()[:2000] + "\n",
                encoding="utf-8")
        except Exception:
            pass


def _prune_reports():
    try:
        files = sorted(REPORTS_DIR.glob("insight-*.md"),
                       key=lambda x: x.stat().st_mtime, reverse=True)
        for p in files[MAX_REPORTS:]:
            try:
                p.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _extract_one_liner(report):
    grab = False
    for ln in (report or "").splitlines():
        s = ln.strip()
        if s.startswith("#") and "一句话" in s:
            grab = True
            continue
        if grab:
            if not s:
                continue
            if s.startswith("#"):
                break
            return s.lstrip("-•　 ").strip()[:80]
    return ""


def _record_run(ok, prog, report):
    runs = _read_json(RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []
    one = _extract_one_liner(report) if ok else ""
    entry = {
        "time": _now_str(), "ok": bool(ok), "source": prog.get("source", "manual"),
        "files": prog.get("total", 0), "learned": prog.get("learned", 0),
        "model": prog.get("model", "") or ("local" if prog.get("read_local") else ""),
        "summary": one or (report.strip()[:60] if (ok and report) else
                           "本轮没读到有效内容"),
    }
    runs.insert(0, entry)
    _write_json(RUNS_PATH, runs[:MAX_RUNS])


# ════════════════════════════════════════════════════════════════════
#  第四步：主动上网研究（根据画像找话题 → 搜 → 落进成长库）
# ════════════════════════════════════════════════════════════════════

def _derive_research_topics(report):
    """从汇总画像里让模型提炼 2-4 个「值得替主人上网搜一下」的具体话题。
    失败则降级用「最近在关注什么」里的条目。"""
    cfg = get_config()
    ul, m = _resolve_model(cfg.get("use_local", False), cfg.get("model", ""))
    prompt = (
        "下面是对主人的理解画像。请据此提出 %d 个**具体、可直接拿去搜索引擎搜**的话题"
        "（主人会感兴趣、能帮他了解最新动态或学到东西的）。每行一个，"
        "不要编号、不要解释、不要寒暄，只输出话题本身。\n\n"
        "=== 画像 ===\n%s\n\n直接输出话题（每行一个）："
        % (RESEARCH_TOPICS_MAX, (report or "")[:3000]))
    out = _ask(ul, m, prompt, max_chars=600)
    topics = []
    for ln in (out or "").splitlines():
        s = ln.strip().lstrip("-•·0123456789.、) 　").strip()
        if 2 <= len(s) <= 40:
            topics.append(s)
    # 降级：从画像「## 最近在关注什么」抓条目
    if not topics:
        grab = False
        for ln in (report or "").splitlines():
            s = ln.strip()
            if s.startswith("#"):
                grab = ("关注" in s)
                continue
            if grab and s:
                t = s.lstrip("-•·0123456789.、) 　").strip()
                if 2 <= len(t) <= 40:
                    topics.append(t)
    # 去重保序
    seen, uniq = set(), []
    for t in topics:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:RESEARCH_TOPICS_MAX]


def _save_research_file(topic, material, sources):
    """把一个话题的研究成果写成一篇成长库文档（memory/insight_research/*.md）。"""
    try:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    safe = "".join(c for c in topic if c.isalnum() or c in " 　-_（）()")[:30].strip() or "研究"
    fname = "research-%s-%s.md" % (_now_stamp(), safe.replace(" ", "_"))
    src_lines = "\n".join("- [%s](%s)" % (t, u) for t, u in (sources or []))
    body = ("# 🔎 主动研究：%s\n\n"
            "> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；"
            "下次洞察会读到它。生成时间：%s\n\n"
            "%s\n\n## 资料来源\n%s\n"
            % (topic, _now_str(), (material or "").strip()[:6000],
               src_lines or "（无）"))
    try:
        (RESEARCH_DIR / fname).write_text(body, encoding="utf-8")
        _prune_research()
        return str(RESEARCH_DIR / fname)
    except Exception:
        return ""


def _prune_research():
    try:
        files = sorted(RESEARCH_DIR.glob("research-*.md"),
                       key=lambda x: x.stat().st_mtime, reverse=True)
        for p in files[MAX_RESEARCH:]:
            try:
                p.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _do_research(prog, report):
    """根据画像挑话题 → 用 web_tools.gather 搜 → 每个话题落一篇进成长库。"""
    prog["phase"] = "researching"
    _log(prog, "🌐 开始根据你的画像主动上网搜相关内容…")
    _save_progress(prog)

    topics = _derive_research_topics(report)
    if not topics:
        _log(prog, "没提炼出可研究的话题，跳过主动研究。")
        return

    try:
        import web_tools
    except Exception:
        _log(prog, "联网研究模块没加载，跳过。")
        return

    stop = _work.get("stop")
    prog["research"] = []
    for topic in topics:
        if stop is not None and stop.is_set():
            _log(prog, "⏸ 主动研究被停止。")
            break
        _log(prog, "🔍 正在研究：%s" % topic)
        prog["current"] = {"name": topic, "scope": "主动研究", "index": 0}
        rec = {"topic": topic, "status": "searching", "sources": [],
               "saved": "", "at": _now_clock()}
        prog["research"].append(rec)
        _save_progress(prog)
        try:
            material, sources = web_tools.gather(topic, read_count=4)
        except Exception as e:
            rec["status"] = "failed"
            _log(prog, "× 这个话题没搜成：%s（%s）" % (topic, e))
            _save_progress(prog)
            continue
        if not sources:
            rec["status"] = "empty"
            _log(prog, "× 没搜到有用资料：%s" % topic)
            _save_progress(prog)
            continue
        path = _save_research_file(topic, material, sources)
        rec["status"] = "saved" if path else "failed"
        rec["sources"] = [{"title": t, "url": u} for t, u in sources]
        rec["saved"] = path
        _log(prog, "✓ 已存进成长库：%s（%d 个来源）" % (topic, len(sources)))
        _save_progress(prog)

    prog["current"] = None
    saved_n = sum(1 for r in prog.get("research", []) if r.get("status") == "saved")
    _log(prog, "🌐 主动研究完成，新增 %d 篇进成长库（下次洞察会读到）。" % saved_n)
    _save_progress(prog)


def research_list(limit=MAX_RESEARCH):
    """列出已存的主动研究成果（给前端研究详情页）。"""
    out = []
    try:
        files = sorted(RESEARCH_DIR.glob("research-*.md"),
                       key=lambda x: x.stat().st_mtime, reverse=True)[:limit]
        for p in files:
            txt = _read_text(p) or ""
            title = _first_title(txt, p.stem)
            out.append({
                "name": p.stem,
                "title": title.lstrip("🔎 ").strip(),
                "mtime": _now_from_mtime(p),
                "path": str(p),
            })
    except Exception:
        pass
    return out


def _now_from_mtime(p):
    try:
        return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════════
#  每篇理解摘要（给研究详情页：每篇读出来的理解）
# ════════════════════════════════════════════════════════════════════

def digests_list(scopes=None, limit=300):
    """把已学习的每篇精读结果列出来（新→旧），给前端「每篇理解摘要」用。"""
    d = _load_digests()
    items = list(d.values())
    try:
        items.sort(key=lambda x: x.get("read_at", ""), reverse=True)
    except Exception:
        pass
    out = []
    for it in items:
        if scopes is not None and not scopes.get(it.get("scope")):
            continue
        out.append({
            "title": it.get("title", ""),
            "scope": it.get("scope", ""),
            "label": it.get("label", ""),
            "digest": (it.get("digest", "") or "").strip(),
            "read_at": it.get("read_at", ""),
        })
        if len(out) >= limit:
            break
    return out


def analyzable_list():
    """枚举「全部可分析文件」，每个标注已读/未读 + 已读的话带它的精读摘要。
    供前端把「可分析篇数 / 已深读篇数」做成可点开的详细清单：
    哪些文件、每篇怎么总结、还有哪些没读。

    返回：
      {
        "total": 全部可分析篇数,
        "read": 已读篇数, "unread": 未读篇数,
        "by_scope": [{scope,label,total,read,unread}, ...],  # 各来源类别小计
        "items": [{name,title,scope,label,read(bool),digest,read_at,changed(bool)}, ...]
      }
    其中 changed=True 表示这篇读过但文件后来改动了，下次会重读。
    """
    cfg = get_config()
    scopes = cfg.get("scopes")
    digests = _load_digests()
    targets = enumerate_targets(scopes)  # 全部当前可分析文件（按各 scope）
    items = []
    read_n = 0
    scope_stat = {}
    for t in targets:
        key = t["key"]
        old = digests.get(key)
        is_read = bool(old)
        changed = bool(old and (old.get("mtime") != t["mtime"]
                                or old.get("size") != t["size"]))
        if is_read:
            read_n += 1
        sc = t["scope"]
        st = scope_stat.setdefault(sc, {"scope": sc, "label": t["label"],
                                        "total": 0, "read": 0, "unread": 0})
        st["total"] += 1
        st["read" if is_read else "unread"] += 1
        items.append({
            "name": t["name"],
            "title": (old.get("title") if old else t["name"]) or t["name"],
            "scope": sc,
            "label": t["label"],
            "read": is_read,
            "changed": changed,
            "digest": (old.get("digest", "").strip() if old else ""),
            "read_at": (old.get("read_at", "") if old else ""),
            "mtime": t["mtime"],
        })
    # 排序：未读优先（提醒还没读的），其次按修改时间新→旧
    items.sort(key=lambda x: (x["read"], -x.get("mtime", 0)))
    total = len(targets)
    return {
        "ok": True,
        "total": total,
        "read": read_n,
        "unread": total - read_n,
        "by_scope": sorted(scope_stat.values(), key=lambda x: -x["total"]),
        "items": items,
    }


# ════════════════════════════════════════════════════════════════════
#  逐篇深读 worker（带断点续传）
# ════════════════════════════════════════════════════════════════════

_work = {"thread": None, "stop": None, "running": False}
_work_lock = threading.Lock()


def _build_queue(scopes, digests):
    """枚举目标 → 已读且未改动的算「已完成」，其余进队列。返回 (queue, total, done)。"""
    targets = enumerate_targets(scopes)
    queue, done = [], 0
    for t in targets:
        old = digests.get(t["key"])
        if old and old.get("mtime") == t["mtime"] and old.get("size") == t["size"]:
            done += 1
        else:
            queue.append(t)
    return queue, len(targets), done


def _worker():
    prog = _load_progress()
    stop = _work["stop"]
    try:
        prog["active"] = True
        if prog.get("phase") not in ("reading", "synthesizing"):
            prog["phase"] = "reading"
        _save_progress(prog)
        digests = _load_digests()
        empty_streak = 0

        # —— 第二步：逐篇阅读学习 ——
        while prog.get("queue"):
            if stop is not None and stop.is_set():
                prog["phase"] = "stopped"
                prog["active"] = False
                _log(prog, "⏸ 已暂停，进度已保存（已读 %d/%d 篇），可随时继续。"
                     % (prog["done"], prog["total"]))
                _save_progress(prog)
                _work["running"] = False
                return

            item = prog["queue"][0]
            idx = prog["done"] + 1
            prog["current"] = {"name": item["name"], "scope": item["label"], "index": idx}
            _log(prog, "📂 爬取 %s《%s》（第 %d/%d 篇）"
                 % (item["label"], item["name"], idx, prog["total"]))
            _save_progress(prog)

            text = _read_text(__import__("pathlib").Path(item["path"]))
            if text is None:
                _log(prog, "⚠ 读不到这篇，跳过：%s" % item["name"])
                prog.setdefault("skipped_files", []).append({
                    "name": item["name"], "scope": item["scope"],
                    "label": item["label"], "reason": "读不到文件"})
            else:
                _log(prog, "🤖 派给 AI 通读这篇…")
                _save_progress(prog)
                digest = _read_file_with_ai(text, item["label"], item["name"],
                                            prog.get("read_local", True))
                if digest:
                    digests[item["key"]] = {
                        "scope": item["scope"], "label": item["label"],
                        "title": item["name"], "mtime": item["mtime"],
                        "size": item["size"], "digest": digest, "read_at": _now_str()}
                    _save_digests(digests)
                    prog["learned"] = prog.get("learned", 0) + 1
                    prog.setdefault("read_files", []).append({
                        "name": item["name"], "scope": item["scope"],
                        "label": item["label"], "chars": len(text),
                        "at": _now_clock()})
                    first = (digest.splitlines() or [""])[0].lstrip("-•　 ")[:42]
                    _log(prog, "✓ 已学习：%s" % first)
                    empty_streak = 0
                else:
                    empty_streak += 1
                    _log(prog, "… 这篇没读出内容，跳过")
                    prog.setdefault("skipped_files", []).append({
                        "name": item["name"], "scope": item["scope"],
                        "label": item["label"], "reason": "模型没读出内容"})
                    if empty_streak == 3 and prog.get("read_local", True):
                        _log(prog, "⚠ 连续几篇都没读出来——本地模型(qwen2.5/Ollama)"
                             "可能没启动。可去设置里改用云端模型逐篇读。")

            prog["queue"].pop(0)
            prog["done"] = prog.get("done", 0) + 1
            prog["current"] = None
            _save_progress(prog)

        # —— 第三步：汇总成对你的理解 ——
        if stop is not None and stop.is_set():
            prog["phase"] = "stopped"
            prog["active"] = False
            _save_progress(prog)
            _work["running"] = False
            return

        prog["phase"] = "synthesizing"
        _log(prog, "🧩 读完了，正在把 %d 篇的学习数据汇总成对你的理解…"
             % digests_count())
        _save_progress(prog)
        report = _synthesize(digests, prog)
        if report and len(report) >= 20:
            _save_report(report)
            _log(prog, "🎉 分析完成，小助更懂你了。")
            _record_run(True, prog, report)
        else:
            _log(prog, "汇总没成功（模型没给出有效结果）。")
            _record_run(False, prog, "")

        # —— 第四步：主动上网研究（可选）——
        # 根据刚汇总出的画像，挑几个你最关注的话题去网上搜，成果落进成长库，
        # 下次洞察会再读到它们，于是「越用越懂你」形成闭环。
        if prog.get("auto_research") and report and len(report) >= 20:
            if stop is not None and stop.is_set():
                pass
            else:
                try:
                    _do_research(prog, report)
                except Exception as e:
                    _log(prog, "主动研究出错（已忽略）：%s" % e)

        prog["phase"] = "done"
        prog["active"] = False
        prog["current"] = None
        prog["finished_at"] = _now_str()
        _save_progress(prog)
    except Exception as e:
        prog["phase"] = "error"
        prog["active"] = False
        _log(prog, "出错（已忽略）：%s" % e)
        _save_progress(prog)
    finally:
        _work["running"] = False


def _spawn_worker():
    with _work_lock:
        if _work["running"]:
            return False
        _work["stop"] = threading.Event()
        _work["running"] = True
        t = threading.Thread(target=_worker, daemon=True)
        _work["thread"] = t
        t.start()
        return True


# ════════════════════════════════════════════════════════════════════
#  对外：开始 / 停止 / 续跑
# ════════════════════════════════════════════════════════════════════

def start_run(use_local=None, model=None, scopes=None, source="manual"):
    """开始一次洞察（若上次有没读完的，自动接着读）。"""
    if _work["running"]:
        return {"ok": False, "busy": True, "message": "正在分析中，请稍候…"}

    cfg = get_config()
    prog = _load_progress()

    # 上次被暂停/没读完 → 直接续跑（接着之前的队列）
    if prog.get("queue") and prog.get("phase") in ("reading", "stopped", "synthesizing"):
        prog["active"] = True
        prog["phase"] = "reading"
        if source:
            prog["source"] = source
        _log(prog, "▶ 接着上次的进度继续读（已读 %d/%d 篇）。"
             % (prog.get("done", 0), prog.get("total", 0)))
        _save_progress(prog)
        _spawn_worker()
        return {"ok": True, "busy": True, "resumed": True,
                "message": "接着上次进度继续读…"}

    # 否则开新一轮
    if scopes is None:
        scopes = cfg.get("scopes")
    if use_local is None:
        use_local = cfg.get("use_local", False)
    if model is None:
        model = cfg.get("model", "")

    digests = _load_digests()
    queue, total, done = _build_queue(scopes, digests)

    new_prog = _default_progress()
    new_prog.update({
        "active": True, "phase": "reading",
        "total": total, "done": done, "learned": 0,
        "queue": queue, "started_at": _now_str(), "source": source,
        "read_local": bool(cfg.get("read_local", True)),
        "use_local": bool(use_local), "model": model or "",
        "auto_research": bool(cfg.get("auto_research", False)),
        "read_files": [], "skipped_files": [], "research": [],
        "scopes": scopes,
    })
    if total == 0:
        new_prog["phase"] = "done"
        new_prog["active"] = False
        _log(new_prog, "成长库里还没有可分析的内容。")
        _save_progress(new_prog)
        _record_run(False, new_prog, "")
        return {"ok": False, "message": "成长库里还没有可分析的内容，"
                "多看几个视频、攒点情报/对话再来。"}

    if not queue:
        _log(new_prog, "✅ 所有 %d 篇都已学习过且没改动，直接汇总。" % total)
    else:
        _log(new_prog, "🚀 开始逐篇精读：共 %d 篇，其中 %d 篇已学过、本轮要读 %d 篇。"
             % (total, done, len(queue)))
    _save_progress(new_prog)
    _spawn_worker()
    return {"ok": True, "busy": True, "message": "开始逐篇深读成长库…"}


def stop_run():
    """暂停当前任务（进度已保存，可续跑）。"""
    if _work.get("stop"):
        try:
            _work["stop"].set()
        except Exception:
            pass
    prog = _load_progress()
    if not _work["running"]:
        # worker 没在跑，直接标记为可续跑的 stopped
        if prog.get("queue"):
            prog["phase"] = "stopped"
        prog["active"] = False
        _save_progress(prog)
    return {"ok": True, "message": "已暂停，进度已保存。"}


def is_busy():
    return bool(_work["running"]) or bool(_load_progress().get("active"))


def clear_runs():
    _write_json(RUNS_PATH, [])
    return {"ok": True}


def reset_learned():
    """清空已学习的缓存与进度（下次从头重读）。"""
    try:
        if DIGESTS_PATH.exists():
            DIGESTS_PATH.unlink()
    except Exception:
        pass
    _save_progress(_default_progress())
    return {"ok": True}


# ════════════════════════════════════════════════════════════════════
#  注入系统提示（供 lumi_features.build_context_block 调用）
# ════════════════════════════════════════════════════════════════════

def build_context_block():
    try:
        if not DIGEST_PATH.exists():
            return ""
        txt = DIGEST_PATH.read_text(encoding="utf-8", errors="replace").strip()
        if not txt:
            return ""
        import re
        body = re.sub(r"^#.*?\n+(> .*?\n+)?", "", txt, count=1, flags=re.S).strip()
        if not body:
            return ""
        return "=== 小助对你的洞察理解（成长库逐篇精读 INSIGHT_DIGEST.md）===\n" + body[:2000]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════════
#  状态查询（给前端）
# ════════════════════════════════════════════════════════════════════

def status():
    cfg = get_config()
    runs = _read_json(RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []
    latest = ""
    try:
        if LATEST_PATH.exists():
            latest = LATEST_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    counts, total_avail = available_counts()
    prog = _load_progress()
    total = prog.get("total", 0)
    done = prog.get("done", 0)
    percent = int(round(done * 100.0 / total)) if total else 0
    # 还剩哪些没读（从队列取，带范围标签）
    pending = [{"name": q.get("name"), "scope": q.get("scope"),
                "label": q.get("label")} for q in prog.get("queue", [])]
    progress = {
        "active": bool(prog.get("active")),
        "phase": prog.get("phase", "idle"),
        "total": total, "done": done, "percent": percent,
        "learned": prog.get("learned", 0),
        "current": prog.get("current"),
        "activity": prog.get("activity", [])[-30:],
        "remaining": len(prog.get("queue", [])),
        # —— 研究详情页用：文件级三张清单 ——
        "read_files": prog.get("read_files", []),
        "skipped_files": prog.get("skipped_files", []),
        "pending_files": pending,
        "research": prog.get("research", []),
        "auto_research": bool(prog.get("auto_research", False)),
        "started_at": prog.get("started_at", ""),
        "finished_at": prog.get("finished_at", ""),
        "source": prog.get("source", ""),
        "scopes": prog.get("scopes", {}),
    }
    return {
        "ok": True,
        "config": cfg,
        "scope_labels": SCOPE_LABELS,
        "available": counts,
        "total_available": total_avail,
        "learned_total": digests_count(),
        "runs": runs[:20],
        "last_run": runs[0] if runs else None,
        "latest_report": latest,
        "progress": progress,
        "digests": digests_list(limit=300),         # 每篇理解摘要
        "research_saved": research_list(),           # 已落库的主动研究成果
        "scheduler": {"running": _sched["running"], "next_due": _sched["next_due"]},
        "busy": is_busy(),
    }


# ════════════════════════════════════════════════════════════════════
#  定时调度（自动跑）
# ════════════════════════════════════════════════════════════════════

_sched = {"running": False, "thread": None, "stop": None, "next_due": "", "last_daily": ""}


def _compute_next_due(cfg, after=None):
    after = after or datetime.datetime.now()
    if cfg.get("mode") == "daily":
        try:
            hh, mm = map(int, str(cfg.get("daily_at", "03:00")).split(":"))
        except Exception:
            hh, mm = 3, 0
        nxt = after.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if nxt <= after:
            nxt += datetime.timedelta(days=1)
        return nxt
    hours = max(1, int(cfg.get("interval_hours", 24)))
    return after + datetime.timedelta(hours=hours)


def _sched_loop():
    stop = _sched["stop"]
    cfg = get_config()
    nxt = _compute_next_due(cfg)
    _sched["next_due"] = nxt.strftime("%Y-%m-%d %H:%M")
    while not stop.is_set():
        if stop.wait(60):
            break
        cfg = get_config()
        if not cfg.get("auto"):
            break
        now = datetime.datetime.now()
        due = False
        if cfg.get("mode") == "daily":
            target = str(cfg.get("daily_at", "03:00"))
            today = now.strftime("%Y-%m-%d")
            if now.strftime("%H:%M") >= target and _sched["last_daily"] != today:
                due = True
                _sched["last_daily"] = today
        else:
            try:
                nd = datetime.datetime.strptime(_sched["next_due"], "%Y-%m-%d %H:%M")
            except Exception:
                nd = now
            if now >= nd:
                due = True
        if due and not _work["running"]:
            try:
                start_run(source="auto")
            except Exception:
                pass
            nxt = _compute_next_due(get_config(), after=datetime.datetime.now())
            _sched["next_due"] = nxt.strftime("%Y-%m-%d %H:%M")
    _sched["running"] = False
    _sched["next_due"] = ""


def start_scheduler():
    stop_scheduler()
    cfg = get_config()
    if not cfg.get("auto"):
        return {"ok": True, "running": False, "message": "自动爬取未开启"}
    _sched["stop"] = threading.Event()
    _sched["running"] = True
    _sched["last_daily"] = ""
    t = threading.Thread(target=_sched_loop, daemon=True)
    _sched["thread"] = t
    t.start()
    return {"ok": True, "running": True, "next_due": _sched["next_due"]}


def stop_scheduler():
    if _sched.get("stop"):
        try:
            _sched["stop"].set()
        except Exception:
            pass
    _sched["running"] = False
    _sched["thread"] = None
    return {"ok": True, "running": False}


def _reconcile_scheduler(cfg):
    if cfg.get("auto"):
        start_scheduler()
    else:
        stop_scheduler()


def resume_if_needed():
    """启动时：若上次有没读完的任务，自动接着跑（断点续传）。"""
    try:
        prog = _load_progress()
        if prog.get("queue") and prog.get("phase") in ("reading", "stopped"):
            _log(prog, "🔁 软件重启，自动接着上次没读完的进度继续。")
            prog["active"] = True
            prog["phase"] = "reading"
            _save_progress(prog)
            _spawn_worker()
            return True
    except Exception:
        pass
    return False


def boot_scheduler():
    """服务启动时调用：恢复未完成任务 + 按配置拉起定时线程。"""
    try:
        resume_if_needed()
    except Exception:
        pass
    try:
        if get_config().get("auto"):
            start_scheduler()
    except Exception:
        pass
