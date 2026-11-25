"""
kb.py —「知识库」（v162 新增）

做法参照 Karpathy 的「LLM Wiki」：AI 当图书管理员，把收进来的资料整理成一页页互相链接的主题页，并一直维护。
  · 原始资料：视频笔记、研究报告、新闻、粘贴的文字。原文只读，这里只存一份快照。
  · 主题页：公司 / 行业 / 人物 / 产品 / 概念 / 事件 / 其他。每页是一个 Markdown 文件，
            页面之间用 [[页面名]] 链接；每条事实后面带〔S数字〕，指向它出自哪份资料。
  · 收录：一份资料排进队列 → 交给 AI 池（只用 AI 池，不用本地模型）→ AI 读目录、相关的旧页面和这份资料，
          新建或更新最多 6 个主题页。改之前存一份旧版本，AI 删得太多或丢了出处标记就不采用。
数据都在 memory/kb/ 下：
  pages/<编号>.md       主题页正文
  pages.json            {编号: 页面信息}
  sources/<编号>.md     资料快照
  sources.json          {资料编号: 资料信息}
  history/<编号>/<时间>.md  旧版本
  queue.json / log.json / config.json / index.md（给人和 AI 看的总目录）
"""
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

try:
    import agent_core as _core
    MEM = Path(_core.MEMORY_DIR)
except Exception:                                       # 单独测试时
    MEM = Path(__file__).resolve().parent / "memory"

KB_DIR = MEM / "kb"
PAGE_DIR = KB_DIR / "pages"
SRC_DIR = KB_DIR / "sources"
HIST_DIR = KB_DIR / "history"
PAGES_FILE = KB_DIR / "pages.json"
SOURCES_FILE = KB_DIR / "sources.json"
QUEUE_FILE = KB_DIR / "queue.json"
LOG_FILE = KB_DIR / "log.json"
CFG_FILE = KB_DIR / "config.json"
INDEX_FILE = KB_DIR / "index.md"
NOTE_DIR = MEM / "video_notes"
REPORT_DIR = MEM / "biz" / "reports"
REPORTS_FILE = MEM / "biz" / "reports.json"

TYPES = [["company", "公司"], ["industry", "行业"], ["person", "人物"], ["product", "产品"],
         ["concept", "概念"], ["event", "事件"], ["other", "其他"]]
TYPE_NAME = dict(TYPES)
TYPE_BY_NAME = {v: k for k, v in TYPES}
KIND_NAME = {"note": "视频笔记", "report": "研究报告", "news": "新闻", "text": "粘贴的资料"}
MAX_PAGES_PER_SOURCE = 6
SRC_CHARS = 14000            # 一份资料最多给 AI 看多少字
PAGE_CHARS = 5000            # 一个旧页面最多给 AI 看多少字
INDEX_CHARS = 7000           # 目录最多给 AI 看多少字
END_MARK = "=====全部结束====="

_LOCK = threading.RLock()
_hooks = {"llm": None, "log": None, "cancel": None}
_state = {"running": None, "stop": False, "stage": "", "started": 0, "worker": False, "last_scan": 0}


def configure(llm=None, log=None, cancel=None):
    if llm:
        _hooks["llm"] = llm
    if log:
        _hooks["log"] = log
    if cancel:
        _hooks["cancel"] = cancel


def _log(msg):
    try:
        if _hooks["log"]:
            _hooks["log"]("知识库", msg)
            return
    except Exception:
        pass
    print("[知识库] " + msg, flush=True)


# ───────────────────────── 读写 ─────────────────────────
def _read_json(p, default):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _write_text(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)


def _pages():
    d = _read_json(PAGES_FILE, {})
    return d if isinstance(d, dict) else {}


def _sources():
    d = _read_json(SOURCES_FILE, {})
    return d if isinstance(d, dict) else {}


def _queue():
    d = _read_json(QUEUE_FILE, [])
    return d if isinstance(d, list) else []


def _logs():
    d = _read_json(LOG_FILE, [])
    return d if isinstance(d, list) else []


def get_config():
    c = _read_json(CFG_FILE, {})
    if not isinstance(c, dict):
        c = {}
    c.setdefault("auto_notes", True)       # 新的视频笔记分析好以后自动收录
    c.setdefault("auto_reports", True)     # 新写好的研究报告自动收录
    c.setdefault("paused", False)          # 暂停收录（队列留着）
    c.setdefault("since", 0)               # 自动收录只收这个时间以后的新资料（以前的要自己挑）
    return c


def save_config(**kw):
    with _LOCK:
        c = get_config()
        for k in ("auto_notes", "auto_reports", "paused"):
            if kw.get(k) is not None:
                c[k] = bool(kw[k])
        if not c.get("since"):
            c["since"] = int(time.time())
        _write_json(CFG_FILE, c)
    return {"ok": True, "config": c}


def _add_log(entry):
    with _LOCK:
        lg = _logs()
        entry.setdefault("ts", int(time.time()))
        lg.insert(0, entry)
        _write_json(LOG_FILE, lg[:600])


def _norm(s):
    return re.sub(r"[\s\-_·・.,，。:：()（）\[\]【】\"'“”‘’《》<>/\\|]+", "", (s or "").lower())


def _page_id(title):
    return "p" + hashlib.sha1(_norm(title).encode("utf-8")).hexdigest()[:10]


def _safe(sid):
    return re.sub(r"[^0-9A-Za-z_\-]+", "_", sid)[:80]


# ───────────────────────── 资料 ─────────────────────────
def _note_text(path):
    """视频笔记：只要「完整文字稿」前面的分析部分（文字稿太长，分析里已经有要点）。分析很短时再补一段文字稿。"""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    cut = re.search(r"^#{1,3}\s*(?:📝\s*)?完整文字稿\s*$", text, re.M)
    head = text[:cut.start()] if cut else text
    if cut and len(head) < 2500:
        head += "\n\n## 文字稿（节选）\n" + text[cut.end():cut.end() + 6000]
    return head.strip()


def _note_meta(name):
    p = NOTE_DIR / name
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:4000]
    except Exception:
        return None
    title = ""
    for ln in text.splitlines()[:6]:
        if ln.startswith("# "):
            title = re.sub(r"\s*#\S+", "", ln[2:]).strip() or ln[2:].strip()
            break
    meta = {}
    for ln in text.splitlines()[:24]:
        m = re.match(r"^-\s*(来源链接|作者|状态)[：:]\s*(.*)$", ln.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    m = re.match(r"^(\d{8})-(\d{6})-", name)
    ts = p.stat().st_mtime
    if m:
        try:
            ts = time.mktime(time.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"))
        except Exception:
            pass
    return {"title": (title or re.sub(r"^\d{8}-\d{6}-", "", name)[:-3])[:100], "url": meta.get("来源链接", ""),
            "who": meta.get("作者", "")[:40], "ts": int(ts), "todo": meta.get("状态", "").startswith("未分析")}


def _reports_list():
    d = _read_json(REPORTS_FILE, [])
    return d if isinstance(d, list) else []


def _source_text(sid, ref=None):
    """按资料编号读原文（视频笔记、研究报告从原文件读；新闻、粘贴的文字读快照）。"""
    kind, _, key = sid.partition(":")
    if kind == "note":
        return _note_text(NOTE_DIR / key)
    if kind == "report":
        meta = next((r for r in _reports_list() if r.get("id") == key), None)
        if not meta:
            return ""
        try:
            return (REPORT_DIR / meta.get("file", "")).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    p = SRC_DIR / (_safe(sid) + ".md")
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return (ref or {}).get("text", "")


def candidates(kind="note", q="", limit=200):
    """还没收进知识库的资料（给「收录资料」窗口挑）。"""
    with _LOCK:
        done = set(_sources().keys()) | {x["sid"] for x in _queue()}
    ql = (q or "").strip().lower()
    out = []
    if kind == "note" and NOTE_DIR.exists():
        try:
            names = [e.name for e in os.scandir(NOTE_DIR) if e.name.endswith(".md") and not e.name.startswith("_")]
        except Exception:
            names = []
        for name in names:
            sid = "note:" + name
            if sid in done:
                continue
            m = _note_meta(name)
            if not m or m["todo"]:
                continue
            if ql and ql not in (m["title"] + " " + m["who"]).lower():
                continue
            out.append({"sid": sid, "kind": "note", "title": m["title"], "who": m["who"], "ts": m["ts"]})
    elif kind == "report":
        for r in _reports_list():
            sid = "report:" + str(r.get("id", ""))
            if sid in done or not r.get("id"):
                continue
            if ql and ql not in (r.get("title", "")).lower():
                continue
            out.append({"sid": sid, "kind": "report", "title": r.get("title", ""), "who": r.get("model", ""),
                        "ts": int(r.get("created") or 0)})
    out.sort(key=lambda x: -x["ts"])
    return {"ok": True, "kind": kind, "total": len(out), "items": out[:max(1, int(limit))]}


def enqueue(sids=None, kind="", title="", url="", text="", top=False):
    """排进收录队列。sids：视频笔记 / 研究报告；或者直接给 kind=news/text 加标题、正文。"""
    added, skipped = [], 0
    now = int(time.time())
    with _LOCK:
        srcs, q = _sources(), _queue()
        have = set(srcs.keys()) | {x["sid"] for x in q}
        items = []
        for sid in sids or []:
            k = sid.split(":", 1)[0]
            if k not in ("note", "report"):
                continue
            if k == "note":
                m = _note_meta(sid.split(":", 1)[1])
                if not m:
                    skipped += 1
                    continue
                items.append({"sid": sid, "kind": "note", "title": m["title"], "url": m["url"], "who": m["who"]})
            else:
                r = next((x for x in _reports_list() if "report:" + str(x.get("id")) == sid), None)
                if not r:
                    skipped += 1
                    continue
                items.append({"sid": sid, "kind": "report", "title": r.get("title", ""), "url": "", "who": ""})
        if kind in ("news", "text"):
            text = (text or "").strip()
            if len(text) < 40:
                return {"ok": False, "error": "内容太短了，至少要几句话"}
            key = url if (kind == "news" and url) else (title + text[:200])
            sid = kind + ":" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
            body = ("# " + title.strip() + "\n\n" if title.strip() else "") + (("原文链接：" + url + "\n\n") if url else "") + text
            _write_text(SRC_DIR / (_safe(sid) + ".md"), body[:60000])
            items.append({"sid": sid, "kind": kind, "title": (title or text[:30]).strip()[:120], "url": url, "who": ""})
        for it in items:
            if it["sid"] in have:
                skipped += 1
                continue
            have.add(it["sid"])
            it.update(added=now, status="pending", tries=0, error="", next_try=0)
            (q.insert(0, it) if top else q.append(it))
            added.append(it["sid"])
        _write_json(QUEUE_FILE, q)
    if added:
        _log("排进队列 %d 份资料" % len(added))
        _wake.set()
    return {"ok": True, "added": len(added), "skipped": skipped,
            "msg": ("已排进队列 %d 份" % len(added)) + (("，%d 份已经收过或在队列里" % skipped) if skipped else "")}


def queue_action(sid, act):
    with _LOCK:
        q = _queue()
        it = next((x for x in q if x["sid"] == sid), None)
        if not it:
            return {"ok": False, "error": "队列里没有这份资料"}
        if act == "remove":
            if _state["running"] == sid:
                return {"ok": False, "error": "正在收录这份，先点「停止」"}
            q = [x for x in q if x["sid"] != sid]
        elif act == "retry":
            it.update(status="pending", tries=0, error="", next_try=0)
        elif act == "top":
            q = [it] + [x for x in q if x["sid"] != sid]
        else:
            return {"ok": False, "error": "不认识的操作"}
        _write_json(QUEUE_FILE, q)
    _wake.set()
    return {"ok": True}


def clear_failed():
    with _LOCK:
        q = [x for x in _queue() if x.get("status") != "failed"]
        _write_json(QUEUE_FILE, q)
    return {"ok": True}


# ───────────────────────── 自动发现新资料 ─────────────────────────
def _scan_new():
    c = get_config()
    since = int(c.get("since") or 0)
    if not since or c.get("paused"):
        return
    sids = []
    if c.get("auto_notes") and NOTE_DIR.exists():
        try:
            ents = [e for e in os.scandir(NOTE_DIR) if e.name.endswith(".md") and not e.name.startswith("_")]
        except Exception:
            ents = []
        for e in ents:
            # 只认文件名里的创建时间（重新打标签、改分类会改文件的修改时间，不能当成新笔记）
            mt = re.match(r"^(\d{8})-(\d{6})-", e.name)
            if not mt:
                continue
            try:
                ts = time.mktime(time.strptime(mt.group(1) + mt.group(2), "%Y%m%d%H%M%S"))
            except Exception:
                continue
            if ts < since:
                continue
            m = _note_meta(e.name)
            if m and not m["todo"]:
                sids.append("note:" + e.name)
    if c.get("auto_reports"):
        for r in _reports_list():
            if int(r.get("created") or 0) >= since and r.get("id"):
                sids.append("report:" + str(r["id"]))
    if sids:
        with _LOCK:
            have = set(_sources().keys()) | {x["sid"] for x in _queue()}
        new = [s for s in sids if s not in have]
        if new:
            enqueue(new)


# ───────────────────────── 收录（交给 AI 池） ─────────────────────────
_RULES = """你是这个知识库的管理员。知识库由一页页「主题页」组成，每页讲清楚一个主题：一家公司、一个行业、一个人、一个产品、一个概念或一件事。
你的任务：读下面这份新资料，把里面有价值的信息整理进知识库——更新已有的主题页，或者新建主题页。

规则：
1. 只给资料里真正重要、讲得比较充分的主题建页。顺带提一句的公司、人名不要建页。一份资料最多改或建 {maxp} 个页面，通常 2～4 个就够。
2. 更新已有页面时：先完整保留原有内容（包括每一条〔S数字〕出处标记），再把新信息合并进去。可以调整结构、合并重复的话，但不能删掉原有事实。新旧说法冲突时，两种都留下，写进「不同说法」一节并分别标出处。
3. 这份资料的编号是 {mark}。从这份资料里得到的每条事实，句末都要加〔{mark}〕。不要编造资料里没有的事实、数字和日期。
4. 页面之间互相提到时，用 [[页面名]] 链接，页面名用目录里已有的名字；还没有的页面也可以先链接。
5. 每页用这个结构（某一节没有内容就省略）：
   # 页面名
   > 一句话说清楚它是什么
   ## 要点
   ## 时间线（「- 2026-11：发生了什么〔S数字〕」，按时间排）
   ## 关联（「- [[别的页面]]：是什么关系」）
   ## 不同说法
   ## 待跟进（值得以后留意的问题）
6. 用简体中文写，平实、具体，多写事实和数字，少写空话。不要写「出处」一节，程序会自动加。

输出格式（严格照着写，不要输出别的内容）：
=====页面=====
动作：新建 或 更新
页面名：……（更新时必须和目录里的名字一模一样）
类型：公司 / 行业 / 人物 / 产品 / 概念 / 事件 / 其他（选一个）
别名：其他叫法，用顿号隔开，没有就写「无」
一句话：……
正文：
（完整的页面 Markdown，从「# 页面名」开始）
=====页面结束=====
（每个页面一段，可以有多段）
=====资料摘要=====
用两三句话概括这份资料讲了什么
""" + END_MARK


def _index_lines(pages, prefer=()):
    """给 AI 看的目录：先列可能相关的，再列最近更新的，字数有上限。"""
    order = list(prefer) + [pid for pid, _m in sorted(pages.items(), key=lambda kv: -int(kv[1].get("updated") or 0))
                            if pid not in prefer]
    out, n = [], 0
    for pid in order:
        m = pages.get(pid)
        if not m:
            continue
        ln = "- %s【%s】%s%s" % (m["title"], TYPE_NAME.get(m.get("type"), "其他"),
                                 ("（也叫：%s）" % "、".join(m.get("aliases") or [])) if m.get("aliases") else "",
                                 "：" + (m.get("summary") or "")[:60])
        n += len(ln)
        if n > INDEX_CHARS:
            out.append("- ……（还有 %d 页没列出）" % (len(order) - len(out)))
            break
        out.append(ln)
    return out


def _related(pages, text, limit=5):
    """资料里提到了哪些已有页面（按提到的次数排）。"""
    tl = text.lower()
    hits = []
    for pid, m in pages.items():
        n = 0
        for name in [m["title"]] + list(m.get("aliases") or []):
            name = (name or "").strip().lower()
            if len(name) >= 2:
                n += tl.count(name)
        if n:
            hits.append((n, pid))
    hits.sort(reverse=True)
    return [pid for _n, pid in hits[:limit]]


def _page_body(pid):
    try:
        return (PAGE_DIR / (pid + ".md")).read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse(raw):
    pages, summary = [], ""
    for blk in re.findall(r"=====页面=====\s*(.*?)\s*=====页面结束=====", raw, re.S):
        head, _, body = blk.partition("正文：")
        f = {}
        for ln in head.splitlines():
            m = re.match(r"^\s*(动作|页面名|类型|别名|一句话)[：:]\s*(.*)$", ln)
            if m:
                f[m.group(1)] = m.group(2).strip()
        body = body.strip()
        body = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", body).strip()
        title = re.sub(r"^\[\[|\]\]$", "", f.get("页面名", "")).strip()
        if not title:
            m = re.search(r"^#\s+(.+)$", body, re.M)
            title = m.group(1).strip() if m else ""
        if not title or len(body) < 40:
            continue
        al = [a.strip() for a in re.split(r"[、,，/;；]", f.get("别名", "")) if a.strip() and a.strip() not in ("无", "没有")]
        pages.append({"act": "update" if "更新" in f.get("动作", "") else "new", "title": title[:60],
                      "type": TYPE_BY_NAME.get(f.get("类型", "").strip(), "other"), "aliases": al[:8],
                      "summary": f.get("一句话", "")[:160], "body": body})
    m = re.search(r"=====资料摘要=====\s*(.*?)\s*(?:" + re.escape(END_MARK) + r"|$)", raw, re.S)
    if m:
        summary = m.group(1).strip()[:600]
    return pages, summary


def _find_page(pages, title, aliases=()):
    n = _norm(title)
    for pid, m in pages.items():
        if _norm(m["title"]) == n:
            return pid
    for pid, m in pages.items():
        if n and n in {_norm(a) for a in (m.get("aliases") or [])}:
            return pid
    for a in aliases or []:
        na = _norm(a)
        for pid, m in pages.items():
            if na and (na == _norm(m["title"]) or na in {_norm(x) for x in (m.get("aliases") or [])}):
                return pid
    return None


_MARK_RE = re.compile(r"〔S(\d+)〕")


def _links(body):
    return list(dict.fromkeys(x.strip() for x in re.findall(r"\[\[([^\[\]]{1,60})\]\]", body)))


def _rebuild_index():
    pages = _pages()
    lines = ["# 知识库目录", "", "共 %d 页，更新于 %s。" % (len(pages), time.strftime("%Y-%m-%d %H:%M")), ""]
    for t, tn in TYPES:
        ps = sorted([m for m in pages.values() if m.get("type") == t], key=lambda m: m["title"])
        if not ps:
            continue
        lines.append("## %s（%d）" % (tn, len(ps)))
        for m in ps:
            lines.append("- [[%s]]：%s" % (m["title"], m.get("summary", "")))
        lines.append("")
    _write_text(INDEX_FILE, "\n".join(lines))


def _stage(msg):
    _state["stage"] = msg


def _ingest(item):
    """收录一份资料。成功返回 (改动列表, 资料摘要)；失败抛错。"""
    sid = item["sid"]
    text = _source_text(sid, item)
    if len(text.strip()) < 40:
        raise RuntimeError("读不到这份资料的内容（文件可能删了）")
    with _LOCK:
        srcs = _sources()
        num = (srcs.get(sid) or {}).get("n") or (max([int(s.get("n") or 0) for s in srcs.values()] + [0]) + 1)
        pages = _pages()
    mark = "S%d" % num
    rel = _related(pages, item.get("title", "") + "\n" + text)
    idx = _index_lines(pages, rel)
    old_blocks = []
    for pid in rel:
        b = _page_body(pid)
        if b:
            old_blocks.append("----- 已有页面：%s -----\n%s" % (pages[pid]["title"], b[:PAGE_CHARS]
                                                              + ("\n（后面还有，没给你看，更新时保留原样就行）" if len(b) > PAGE_CHARS else "")))
    prompt = (_RULES.format(maxp=MAX_PAGES_PER_SOURCE, mark=mark) +
              "\n\n【知识库目录（共 %d 页）】\n%s\n" % (len(pages), "\n".join(idx) if idx else "（还没有页面，这是第一份资料）") +
              ("\n【可能要更新的已有页面（完整内容）】\n" + "\n\n".join(old_blocks) + "\n" if old_blocks else "") +
              "\n【新资料 %s：%s（%s）】\n%s\n" % (mark, item.get("title", ""), KIND_NAME.get(item.get("kind"), ""),
                                                 text[:SRC_CHARS] + ("\n……（后面省略）" if len(text) > SRC_CHARS else "")) +
              "\n现在按要求输出。")
    if not _hooks["llm"]:
        raise RuntimeError("AI 池还没准备好")
    _stage("排队等 AI 池…")
    raw, by = _hooks["llm"](prompt, what="知识库收录：" + item.get("title", "")[:20], markers=[END_MARK],
                             on_stage=_stage, should_stop=lambda: _state["stop"])
    if _state["stop"]:
        raise RuntimeError("已按你的要求停止")
    got, summary = _parse(raw or "")
    if not got:
        raise RuntimeError("AI 池的回复里没找到页面（格式不对），稍后会再试")
    _stage("保存页面…")
    changes = []
    now = int(time.time())
    with _LOCK:
        pages = _pages()
        for g in got[:MAX_PAGES_PER_SOURCE]:
            pid = _find_page(pages, g["title"], g["aliases"])
            body = g["body"]
            body = re.sub(r"\n##\s*出处[\s\S]*$", "", body).strip()      # 出处由程序画
            if not body.startswith("# "):
                body = "# %s\n\n%s" % (g["title"], body)
            if pid:
                m = pages[pid]
                old = _page_body(pid)
                old_marks = set(_MARK_RE.findall(old))
                new_marks = set(_MARK_RE.findall(body))
                lost = old_marks - new_marks
                if len(old) > 400 and len(body) < len(old) * 0.6:
                    changes.append({"pid": pid, "title": m["title"], "act": "rejected",
                                    "why": "AI 改完的页面比原来短了很多（%d → %d 字），可能删了内容，没采用" % (len(old), len(body))})
                    continue
                if old_marks and len(lost) >= max(1, len(old_marks) * 0.3):
                    changes.append({"pid": pid, "title": m["title"], "act": "rejected",
                                    "why": "AI 改完的页面丢了 %d 处出处标记，没采用" % len(lost)})
                    continue
                hd = HIST_DIR / pid
                _write_text(hd / ("%d.md" % now), old)
                _write_text(PAGE_DIR / (pid + ".md"), body)
                m["aliases"] = list(dict.fromkeys((m.get("aliases") or []) + [a for a in g["aliases"] if _norm(a) != _norm(m["title"])]))[:10]
                if g["summary"]:
                    m["summary"] = g["summary"]
                if g["type"] != "other" or not m.get("type"):
                    m["type"] = g["type"]
                m["updated"] = now
                m["ver"] = int(m.get("ver") or 1) + 1
                m["sources"] = list(dict.fromkeys((m.get("sources") or []) + [sid]))
                m["links"] = _links(body)
                m["chars"] = len(body)
                changes.append({"pid": pid, "title": m["title"], "act": "update", "delta": len(body) - len(old)})
            else:
                pid = _page_id(g["title"])
                while pid in pages:
                    pid = pid + "x"
                _write_text(PAGE_DIR / (pid + ".md"), body)
                pages[pid] = {"id": pid, "title": g["title"], "type": g["type"],
                              "aliases": [a for a in g["aliases"] if _norm(a) != _norm(g["title"])],
                              "summary": g["summary"], "created": now, "updated": now, "ver": 1,
                              "sources": [sid], "links": _links(body), "chars": len(body)}
                changes.append({"pid": pid, "title": g["title"], "act": "new", "delta": len(body)})
        _write_json(PAGES_FILE, pages)
        srcs = _sources()
        srcs[sid] = {"sid": sid, "n": num, "kind": item.get("kind"), "title": item.get("title", ""),
                     "url": item.get("url", ""), "who": item.get("who", ""), "ingested": now, "by": by,
                     "summary": summary, "pages": [c["pid"] for c in changes if c["act"] in ("new", "update")]}
        if sid.split(":", 1)[0] in ("note", "report"):                 # 视频笔记、报告也留一份快照，原文件删了也能看
            _write_text(SRC_DIR / (_safe(sid) + ".md"), text[:60000])
        _write_json(SOURCES_FILE, srcs)
        _rebuild_index()
    return changes, summary, by


_wake = threading.Event()


def _worker():
    time.sleep(20)
    while True:
        try:
            now = time.time()
            if now - _state["last_scan"] > 600:
                _state["last_scan"] = now
                try:
                    _scan_new()
                except Exception as e:
                    _log("找新资料出错：%s" % e)
            c = get_config()
            item = None
            if not c.get("paused") and _hooks["llm"]:
                with _LOCK:
                    q = _queue()
                    item = next((x for x in q if x.get("status") == "pending" and x.get("next_try", 0) <= now), None)
                    if item:
                        item["status"] = "running"
                        _write_json(QUEUE_FILE, q)
            if item:
                ok = _run_one(item)
                if not ok:                  # 没收录成（多半 AI 池打不开）：歇一分钟，别一口气把整个队列都试失败
                    _wake.wait(60)
                    _wake.clear()
                continue
        except Exception as e:
            _log("收录线程出错：%s" % e)
        _wake.wait(30)
        _wake.clear()


def _run_one(item):
    sid = item["sid"]
    _state.update(running=sid, stop=False, stage="准备…", started=int(time.time()), title=item.get("title", ""))
    _log("开始收录：%s" % item.get("title", sid))
    err = ""
    try:
        changes, summary, by = _ingest(item)
    except Exception as e:
        err = str(e)[:300]
        changes, summary, by = [], "", ""
    stopped = _state["stop"]
    with _LOCK:
        q = _queue()
        it = next((x for x in q if x["sid"] == sid), None)
        if err:
            if it:
                it["tries"] = int(it.get("tries") or 0) + 1
                it["error"] = err
                if stopped:
                    it.update(status="pending", tries=it["tries"] - 1, next_try=int(time.time()) + 3600)
                    _get_config_pause()
                elif it["tries"] >= 3:
                    it["status"] = "failed"
                else:
                    it.update(status="pending", next_try=int(time.time()) + 600 * it["tries"])
            _write_json(QUEUE_FILE, q)
        else:
            _write_json(QUEUE_FILE, [x for x in q if x["sid"] != sid])
    if err:
        _log("没收录成：%s（%s）" % (item.get("title", sid), err))
        _add_log({"sid": sid, "title": item.get("title", ""), "kind": item.get("kind"), "ok": False, "error": err})
    else:
        _log("收录好了：%s，改了 %d 页" % (item.get("title", sid), len(changes)))
        _add_log({"sid": sid, "title": item.get("title", ""), "kind": item.get("kind"), "ok": True, "by": by,
                  "summary": summary, "changes": changes, "ms": int(time.time()) - _state["started"]})
    _state.update(running=None, stop=False, stage="", started=0, title="")
    return not err


def _get_config_pause():
    """点了停止：顺手把收录暂停，免得马上又开始下一份。"""
    c = get_config()
    c["paused"] = True
    _write_json(CFG_FILE, c)


def stop():
    if not _state["running"]:
        return {"ok": False, "error": "现在没在收录"}
    _state["stop"] = True
    try:
        if _hooks["cancel"]:
            _hooks["cancel"]()
    except Exception:
        pass
    return {"ok": True}


def boot():
    if _state["worker"]:
        return
    _state["worker"] = True
    c = get_config()
    if not c.get("since"):
        save_config()
    with _LOCK:                                         # 上次关软件时正在收录的，放回队列
        q = _queue()
        for x in q:
            if x.get("status") == "running":
                x["status"] = "pending"
        _write_json(QUEUE_FILE, q)
    threading.Thread(target=_worker, daemon=True, name="kb-worker").start()


# ───────────────────────── 给界面的 ─────────────────────────
def overview():
    with _LOCK:
        pages, srcs, q = _pages(), _sources(), _queue()
        lg = _logs()[:40]
    by_type = {}
    for m in pages.values():
        by_type[m.get("type", "other")] = by_type.get(m.get("type", "other"), 0) + 1
    plist = sorted(pages.values(), key=lambda m: -int(m.get("updated") or 0))
    pend = [x for x in q if x.get("status") in ("pending", "running")]
    return {"ok": True, "pages": [dict({k: m.get(k) for k in ("id", "title", "type", "aliases", "summary", "updated", "created",
                                                                "ver", "chars")}, n_src=len(m.get("sources") or []))
                                  for m in plist],
            "types": [[k, n, by_type.get(k, 0)] for k, n in TYPES],
            "n_sources": len(srcs), "queue": q[:200], "n_pending": len(pend),
            "n_failed": len([x for x in q if x.get("status") == "failed"]),
            "running": ({"sid": _state["running"], "title": _state.get("title", ""), "stage": _state["stage"],
                         "started": _state["started"]} if _state["running"] else None),
            "config": get_config(), "log": lg, "now": int(time.time()),
            "llm_ready": bool(_hooks["llm"]), "dir": str(KB_DIR.resolve())}


def page(pid):
    with _LOCK:
        pages, srcs = _pages(), _sources()
    m = pages.get(pid)
    if not m:
        return {"ok": False, "error": "这一页不存在（可能删掉了）"}
    body = _page_body(pid)
    by_n = {str(s.get("n")): s for s in srcs.values()}
    used = []
    for n in dict.fromkeys(_MARK_RE.findall(body)):
        s = by_n.get(n)
        if s:
            used.append(s)
    for sid in m.get("sources") or []:
        s = srcs.get(sid)
        if s and s not in used:
            used.append(s)
    titles = {_norm(x["title"]): x["id"] for x in pages.values()}
    for x in pages.values():
        for a in x.get("aliases") or []:
            titles.setdefault(_norm(a), x["id"])
    links = {t: titles.get(_norm(t), "") for t in _links(body)}
    back = []
    keys = {_norm(m["title"])} | {_norm(a) for a in (m.get("aliases") or [])}
    for x in pages.values():
        if x["id"] != pid and any(_norm(l) in keys for l in (x.get("links") or [])):
            back.append({"id": x["id"], "title": x["title"], "type": x.get("type")})
    hist = []
    hd = HIST_DIR / pid
    if hd.exists():
        hist = sorted([int(p.stem) for p in hd.glob("*.md") if p.stem.isdigit()], reverse=True)[:30]
    return {"ok": True, "meta": m, "body": body, "links": links, "backlinks": back,
            "sources": [{k: s.get(k) for k in ("sid", "n", "kind", "title", "url", "who", "ingested", "summary")} for s in used],
            "history": hist}


def source(sid="", n=""):
    with _LOCK:
        srcs = _sources()
    s = srcs.get(sid) if sid else next((x for x in srcs.values() if str(x.get("n")) == str(n)), None)
    if not s:
        return {"ok": False, "error": "找不到这份资料"}
    text = ""
    try:
        text = (SRC_DIR / (_safe(s["sid"]) + ".md")).read_text(encoding="utf-8")
    except Exception:
        text = _source_text(s["sid"])
    pages = _pages()
    return {"ok": True, "meta": s, "text": text[:60000],
            "pages": [{"id": p, "title": pages[p]["title"]} for p in (s.get("pages") or []) if p in pages]}


def search(q, limit=40):
    ql = (q or "").strip().lower()
    if not ql:
        return {"ok": True, "items": []}
    with _LOCK:
        pages = _pages()
    out = []
    for pid, m in pages.items():
        body = _page_body(pid)
        hay = " ".join([m["title"], " ".join(m.get("aliases") or []), m.get("summary", "")]).lower()
        i = body.lower().find(ql)
        score = (10 if ql in hay else 0) + body.lower().count(ql)
        if not score:
            continue
        snip = ""
        if i >= 0:
            snip = re.sub(r"\s+", " ", body[max(0, i - 40): i + 80])
        out.append((score, {"id": pid, "title": m["title"], "type": m.get("type"), "summary": m.get("summary", ""), "snip": snip}))
    out.sort(key=lambda x: -x[0])
    return {"ok": True, "items": [x[1] for x in out[:limit]]}


def page_action(pid, act, ts=0):
    with _LOCK:
        pages = _pages()
        m = pages.get(pid)
        if not m:
            return {"ok": False, "error": "这一页不存在"}
        now = int(time.time())
        if act == "delete":
            old = _page_body(pid)
            _write_text(HIST_DIR / pid / ("%d.md" % now), old)
            try:
                (PAGE_DIR / (pid + ".md")).unlink()
            except Exception:
                pass
            pages.pop(pid, None)
            _write_json(PAGES_FILE, pages)
            _rebuild_index()
            _add_log({"title": m["title"], "ok": True, "manual": "删除了页面「%s」" % m["title"]})
            return {"ok": True}
        if act == "restore":
            p = HIST_DIR / pid / ("%d.md" % int(ts))
            if not p.exists():
                return {"ok": False, "error": "找不到这个旧版本"}
            cur = _page_body(pid)
            _write_text(HIST_DIR / pid / ("%d.md" % now), cur)
            body = p.read_text(encoding="utf-8")
            _write_text(PAGE_DIR / (pid + ".md"), body)
            m.update(updated=now, ver=int(m.get("ver") or 1) + 1, links=_links(body), chars=len(body))
            _write_json(PAGES_FILE, pages)
            _rebuild_index()
            _add_log({"title": m["title"], "ok": True, "manual": "把「%s」恢复到 %s 的版本" % (m["title"], time.strftime("%m-%d %H:%M", time.localtime(int(ts))))})
            return {"ok": True}
        if act == "history":
            p = HIST_DIR / pid / ("%d.md" % int(ts))
            if not p.exists():
                return {"ok": False, "error": "找不到这个旧版本"}
            return {"ok": True, "body": p.read_text(encoding="utf-8")}
    return {"ok": False, "error": "不认识的操作"}


def source_status(sids):
    """这些资料收进知识库了没有（给别的页面显示「已收录 / 排队中」）。"""
    with _LOCK:
        srcs, q = _sources(), _queue()
    qm = {x["sid"]: x.get("status") for x in q}
    out = {}
    for sid in sids or []:
        out[sid] = "done" if sid in srcs else (qm.get(sid) or "")
    return {"ok": True, "items": out}


def news_sid(url):
    return "news:" + hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:12]
