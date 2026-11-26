"""超能小助 · 商业（v155 新增）

左栏「商业」的后台：
  · 把你收进来的内容——笔记（加工好的）、嗅探到的网站动态、博主新内容——按行业、赛道、商业模式归类，
    算出行业热度、正在升温的话题、最新动向。归类不用 AI：按关键词 + 笔记已有的分类打分，快、不占 AI 池。
  · 需要时让 AI 写报告：市场动向简报、行业研究、商业模式拆解（含产业链上下游）、趋势与机会、课题研究。
    写之前先从你的资料里挑相关的，勾了「联网」还会自己上网搜、读网页（web_tools.gather）。
  · 报告里的「机会清单」自动收进机会看板；「产业链图」界面画成上游 → 中游 → 下游的图。

行业分类表在 biz_industries.py。写报告用哪个 AI 由 server.py 传进来（configure）：先排队用 AI 池，不行再用本地模型。
数据都在 memory/biz/：reports/*.md、reports.json、opportunities.json、topics.json。不改笔记文件。
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import json
import math
import os
import re
import threading
import time
from pathlib import Path

import biz_industries as BI

try:
    import agent_core as _core
    MEM = Path(_core.MEMORY_DIR)
except Exception:                                   # 单独测试时
    MEM = Path(__file__).resolve().parent / "memory"

NOTE_DIR = MEM / "video_notes"
BIZ_DIR = MEM / "biz"
REPORT_DIR = BIZ_DIR / "reports"
REPORTS_FILE = BIZ_DIR / "reports.json"
OPPS_FILE = BIZ_DIR / "opportunities.json"
TOPICS_FILE = BIZ_DIR / "topics.json"

KIND_NAMES = {"market": "市场动向简报", "industry": "行业研究", "model": "商业模式拆解",
              "trend": "趋势与机会", "research": "课题研究"}
STEPS = ["读你收进来的资料", "上网查资料", "AI 写报告", "存报告"]
OPP_STATUS = ("new", "watch", "testing", "doing", "dropped")

_hooks = {"llm": None, "log": None, "cancel": None}


def configure(llm=None, log=None, cancel=None):
    """server.py 传进来：llm(prompt, what, markers, on_stage, should_stop, on_hold) → (文字, 用的哪个 AI)；
    log(标签, 人话)；cancel() 停掉 AI 池正在写的这一条。"""
    if llm:
        _hooks["llm"] = llm
    if log:
        _hooks["log"] = log
    if cancel:
        _hooks["cancel"] = cancel


def _log(msg):
    f = _hooks.get("log")
    try:
        if f:
            f("商业", msg)
        else:
            print("[商业] " + msg, flush=True)
    except Exception:
        pass


def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(p))


def _day(ts):
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return ""


# ───────────────────────── 关键词匹配 ─────────────────────────
_ASCII = re.compile(r"^[A-Za-z0-9 .+\-]+$")


class _Matcher:
    """(编号, [关键词]) 一组 → 一段文字命中了哪些编号、哪些词。
    中文词按「包含」判断；纯英文 / 数字的词要求前后不是字母数字（AI 不会命中 said，PC 不会命中 PCB）。"""

    def __init__(self, groups):
        self.sub = []
        self.amap = {}
        for gid, kws in groups:
            for k in kws:
                k = (k or "").strip()
                if not k:
                    continue
                if _ASCII.match(k):
                    self.amap.setdefault(k.lower(), []).append((gid, k))
                elif len(k) >= 2:
                    self.sub.append((k.lower(), gid, k))
        alts = sorted((re.escape(k) for k in self.amap), key=len, reverse=True)
        self.rx = (re.compile(r"(?<![A-Za-z0-9])(" + "|".join(alts) + r")(?![A-Za-z0-9])", re.I)
                   if alts else None)

    def hits(self, text):
        out = {}
        if not text:
            return out
        t = text.lower()
        for k, gid, raw in self.sub:
            if k in t:
                out.setdefault(gid, set()).add(raw)
        if self.rx is not None:
            for m in self.rx.finditer(text):
                for gid, raw in self.amap.get(m.group(1).lower(), ()):
                    out.setdefault(gid, set()).add(raw)
        return out


_TX = {}
_TX_LOCK = threading.Lock()


def _tx():
    """分类表 → 查找表 + 三个匹配器（行业二级 / 赛道 / 商业模式）。只建一次。"""
    if _TX:
        return _TX
    with _TX_LOCK:
        if _TX:
            return _TX
        l1, l2, trk, sec = {}, {}, {}, {}
        ind_groups, trk_groups, mdl_groups = [], [], []
        for key, name, desc in BI.SECTORS:
            sec["sec:" + key] = {"name": name, "desc": desc, "l1": []}
        for n1, s, d1, subs in BI.INDUSTRIES:
            l1[n1] = {"name": n1, "sec": s, "desc": d1, "subs": []}
            sec["sec:" + s]["l1"].append(n1)
            for n2, d2, kw, co in subs:
                gid = n1 + "/" + n2
                l1[n1]["subs"].append(gid)
                cos = [c.strip() for c in re.split(r"[、，,]", co or "") if len(c.strip()) >= 2]
                l2[gid] = {"name": n2, "l1": n1, "desc": d2, "kw": kw.split(), "co": co}
                ind_groups.append((gid, kw.split() + cos))
        for i, n, d, kw, rel in BI.TRACKS:
            trk["t:" + i] = {"name": n, "desc": d, "kw": kw.split(), "rel": rel}
            trk_groups.append(("t:" + i, kw.split() + [n]))
        mdl = {}
        for i, n, d, kw in BI.MODELS:
            mdl["m:" + i] = {"name": n, "desc": d, "kw": kw.split()}
            mdl_groups.append(("m:" + i, kw.split()))
        _TX.update(l1=l1, l2=l2, trk=trk, sec=sec, mdl=mdl,
                   mi=_Matcher(ind_groups), mt=_Matcher(trk_groups), mm=_Matcher(mdl_groups),
                   mb=_Matcher([("b", BI.BIZ_WORDS)]))
        return _TX


def taxonomy():
    return BI.taxonomy()


def _score(strong, weak=""):
    """一段文字 → ({行业二级: 分}, {赛道: 分}, 命中的词)。标题、关键词这些「要紧的字」一个词 2 分，摘要里 1 分。"""
    tx = _tx()
    sc_i, sc_t, words = collections.Counter(), collections.Counter(), []
    for m, sc in ((tx["mi"], sc_i), (tx["mt"], sc_t)):
        hs = m.hits(strong)
        hw = m.hits(weak) if weak else {}
        for gid, ks in hs.items():
            sc[gid] += 2 * len(ks)
            words.extend(ks)
        for gid, ks in hw.items():
            extra = ks - hs.get(gid, set())
            sc[gid] += len(extra)
            words.extend(extra)
    return sc_i, sc_t, words


def _pick(sc, n=3, floor=2):
    return [g for g, s in sc.most_common() if s >= floor][:n]


def _models_of(strong):
    """商业模式：两个不同的词，或者一个够具体（3 个字以上）的词，才算。"""
    out = []
    for gid, ks in _tx()["mm"].hits(strong).items():
        if len(ks) >= 2 or any(len(k) >= 3 for k in ks):
            out.append(gid)
    return out[:3]


# ───────────────────────── 读笔记 ─────────────────────────
_IDX_LOCK = threading.Lock()
_NOTE_CACHE = {}                 # 文件名 → (签名, 记录)
_LAB = {"sig": None, "labels": {}, "tags": {}}
_SIG_CACHE = {}                  # 'sniff' / 'creator' → (签名, [记录])
_FN_TS = re.compile(r"^(\d{8})-(\d{6})-")


def _note_fields(text):
    """笔记 md → 标题、头部信息、一句话概括、核心观点的小标题。只看「完整文字稿」前面的部分。"""
    cut = re.search(r"^#{1,3}\s*(?:📝\s*)?完整文字稿\s*$", text, re.M)
    body = text[:cut.start()] if cut else text[:30000]
    lines = body.splitlines()
    title = ""
    for ln in lines[:6]:
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    meta = {}
    for ln in lines[:24]:
        m = re.match(r"^-\s*(来源链接|作者|提取时间|标签|状态)[：:]\s*(.*)$", ln.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    one, pts = "", []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if not one and re.match(r"^#{1,4}\s*\S{0,3}\s*一句话", s) and len(s) < 30:
            j, buf = i + 1, []
            while j < n:
                t = lines[j].strip()
                if t.startswith("#"):
                    break
                if t:
                    buf.append(t)
                elif buf:
                    break
                j += 1
            one = " ".join(buf)[:240]
            i = j
            continue
        if not pts and re.match(r"^#{1,3}\s*\S{0,3}\s*核心观点", s):
            j = i + 1
            while j < n and len(pts) < 8:
                t = lines[j].strip()
                if re.match(r"^#{1,2}\s", t):
                    break
                m = re.match(r"^#{3,4}\s*(?:\d+\s*[.、．]\s*)?(.+)$", t)
                if m:
                    pts.append(m.group(1).strip().strip("*")[:70])
                j += 1
            i = j
            continue
        i += 1
    return title, meta, one, pts


def _labels():
    """_labels.json（大类/子类/关键词）和 _tags.json（内容标签），按修改时间缓存。"""
    lf, tf = NOTE_DIR / "_labels.json", NOTE_DIR / "_tags.json"
    sig = tuple(int(p.stat().st_mtime) if p.exists() else 0 for p in (lf, tf))
    if _LAB["sig"] != sig:
        lb = _read_json(lf, {})
        tg = _read_json(tf, {})
        _LAB.update(sig=sig, labels=lb if isinstance(lb, dict) else {}, tags=tg if isinstance(tg, dict) else {})
    return _LAB["labels"], _LAB["tags"]


def _note_record(name, path, st):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    title, meta, one, pts = _note_fields(text)
    clean = re.sub(r"\s*#\S+", "", title).strip() or title.replace("#", " ").strip()
    if not clean:
        clean = re.sub(r"^\d{8}-\d{6}-", "", name)[:-3]
    m = _FN_TS.match(name)
    ts = st.st_mtime
    if m:
        try:
            ts = time.mktime(datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").timetuple())
        except Exception:
            pass
    return {"src": "note", "id": name, "title": clean[:90], "who": meta.get("作者", "")[:40],
            "url": meta.get("来源链接", ""), "ts": ts, "one": one, "pts": pts,
            "rawtags": meta.get("标签", "")[:200], "todo": meta.get("状态", "").startswith("未分析")}


def _enrich_note(rec, lab, tag):
    """笔记记录 + 它的分类和标签 → 行业、赛道、商业模式、商业味、关键词。"""
    tx = _tx()
    cat = "%s/%s" % (lab.get("cat", ""), lab.get("sub", "")) if lab.get("cat") else ""
    kw = [str(k) for k in (lab.get("kw") or [])][:6]
    tags = [str(t) for t in (tag.get("t") or [])][:6] if isinstance(tag, dict) else []
    strong = " ".join([rec["title"], " ".join(kw), " ".join(tags)])          # 标题和 AI 给的关键词：一个词 2 分
    weak = " ".join([rec["rawtags"], rec["one"], " ".join(rec["pts"])])     # 话题标签、一句话、要点：1 分
    sc_i, sc_t, words = _score(strong, weak)
    strong = strong + " " + weak
    for h in BI.LABEL_HINTS.get(cat, []):
        (sc_t if h.startswith("t:") else sc_i)[h] += 2
    biz = BI.BIZ_CAT_W.get(lab.get("cat", ""), 0) + BI.BIZ_SUB_W.get(cat, 0)
    biz += min(3, len(tx["mb"].hits(strong).get("b", ())))
    terms, seen = [], set()
    for k in kw + tags + sorted(set(words), key=len, reverse=True):
        k2 = k.strip()
        if 2 <= len(k2) <= 16 and k2.lower() not in seen:
            seen.add(k2.lower())
            terms.append(k2)
    r = dict(rec)
    r.update(cat=cat, kw=kw, tags=tags, ind=_pick(sc_i), trk=_pick(sc_t), mdl=_models_of(strong),
             biz=biz, terms=terms[:12],
             _text=(" ".join([rec["title"], rec["who"], strong])).lower())
    return r


def _notes():
    if not NOTE_DIR.exists():
        return []
    labels, tags = _labels()
    out = []
    with _IDX_LOCK:
        seen = set()
        try:
            ents = list(os.scandir(NOTE_DIR))
        except Exception:
            ents = []
        for e in ents:
            name = e.name
            if not name.endswith(".md") or name.startswith("_") or not e.is_file():
                continue
            seen.add(name)
            try:
                st = e.stat()
            except Exception:
                continue
            lab = labels.get(name) if isinstance(labels.get(name), dict) else {}
            tg = tags.get(name) if isinstance(tags.get(name), dict) else {}
            sig = (int(st.st_mtime), st.st_size, json.dumps([lab.get("cat"), lab.get("sub"), lab.get("kw"),
                                                             tg.get("t")], ensure_ascii=False))
            hit = _NOTE_CACHE.get(name)
            if hit and hit[0] == sig:
                out.append(hit[1])
                continue
            rec = _note_record(name, Path(e.path), st)
            if rec is None:
                continue
            rec = _enrich_note(rec, lab, tg)
            _NOTE_CACHE[name] = (sig, rec)
            out.append(rec)
        for k in [k for k in _NOTE_CACHE if k not in seen]:
            _NOTE_CACHE.pop(k, None)
    return out


def _parse_ts(s):
    s = str(s or "").strip()
    for fmt, n in (("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10), ("%Y%m%d", 8)):
        try:
            return time.mktime(datetime.datetime.strptime(s[:n], fmt).timetuple())
        except Exception:
            continue
    return 0


def _signal(src, key, title, summary, who, url, ts, extra=None, hints=None, hint_w=2):
    sc_i, sc_t, words = _score(title, summary)
    for h in hints or []:                       # v156：信息源本身属于哪个行业（比如盖世汽车→汽车），加分
        (sc_t if h.startswith("t:") else sc_i)[h] += hint_w
    terms, seen = [], set()
    for k in sorted(set(words), key=len, reverse=True):
        if k.lower() not in seen:
            seen.add(k.lower())
            terms.append(k)
    r = {"src": src, "id": key, "title": (title or "")[:120], "who": (who or "")[:40], "url": url or "", "ts": ts,
         "one": (summary or "")[:240], "pts": [], "cat": "", "kw": [], "tags": [],
         "ind": _pick(sc_i), "trk": _pick(sc_t), "mdl": _models_of(title + " " + summary), "biz": 2,
         "terms": terms[:10], "_text": " ".join([title or "", summary or "", who or ""]).lower()}
    if extra:
        r.update(extra)
    return r


def classify_radar(title, summary, hints=None, grp=""):
    """v178：给爬虫用——一条新闻归到哪些细分行业、赛道（和 _radar_items 同一套算法），抓到时就记进统计。"""
    it = _signal("radar", "", title or "", summary or "", "", "", 0, hints=hints or [],
                 hint_w=2 if grp in ("media", "corpkw", "indkw", "mine") else 1)
    return it["ind"], it["trk"]


def _round_since():
    try:
        import biz_crawler as BC
        return int(BC.round_started() or 0)
    except Exception:
        return 0


def _cached_file(key, path, build):
    try:
        sig = (int(path.stat().st_mtime), path.stat().st_size)
    except Exception:
        return []
    hit = _SIG_CACHE.get(key)
    if hit and hit[0] == sig:
        return hit[1]
    try:
        data = build(_read_json(path, None))
    except Exception:
        data = []
    _SIG_CACHE[key] = (sig, data)
    return data


def _sniff_items():
    def build(feed):
        out = []
        for it in (feed if isinstance(feed, list) else [])[:1500]:
            if not isinstance(it, dict) or not it.get("title"):
                continue
            key = it.get("key") or hashlib.md5((it.get("title", "") + it.get("link", "")).encode("utf-8")).hexdigest()[:16]
            out.append(_signal("sniff", "s:" + key, it.get("title", ""), it.get("summary", ""),
                               it.get("source_title", ""), it.get("link", ""), _parse_ts(it.get("ts")),
                               {"kind": it.get("kind", ""), "imp": it.get("importance", "")}))
        return out
    return _cached_file("sniff", MEM / "sniff_feed.json", build)


def _creator_items():
    def build(store):
        out = []
        fd = (store or {}).get("findings") if isinstance(store, dict) else None
        for it in (fd if isinstance(fd, list) else [])[-800:]:
            if not isinstance(it, dict):
                continue
            title = it.get("title_zh") or it.get("title") or (it.get("text") or "")[:80]
            if not title:
                continue
            ts = _parse_ts(it.get("when")) or _parse_ts(it.get("found_at"))
            key = "c:%s:%s" % (it.get("creator_id", ""), it.get("vid", ""))
            out.append(_signal("creator", key, title, (it.get("text") or "")[:200],
                               it.get("creator_title") or it.get("uploader") or "", it.get("url", ""), ts,
                               {"platform": it.get("platform", "")}))
        return out
    return _cached_file("creator", MEM / "creator_watch.json", build)


def _all_items():
    return _notes() + _sniff_items() + _creator_items()


_RADAR = {"ver": None, "list": [], "cache": {}}
_RADAR_LOCK = threading.Lock()


def _radar_items():
    """v156：市场雷达（biz_crawler）抓到的新闻 → 和别的资料一样的记录。只给新抓到的归类，旧的用缓存。"""
    try:
        import biz_crawler as BC
        ver, raw, srcs = BC.snapshot()
    except Exception:
        return []
    with _RADAR_LOCK:
        if _RADAR["ver"] == ver:
            return _RADAR["list"]
        cache, keep, out = _RADAR["cache"], {}, []
        for r in raw:
            s = srcs.get(r.get("sid")) or {}
            ck = "%s|%s" % (r.get("key"), ",".join(s.get("hint") or []))
            it = cache.get(ck)
            if it is None:
                it = _signal("radar", "r:" + str(r.get("key")), r.get("title", ""), r.get("summary", ""),
                             s.get("name") or r.get("sname", ""), r.get("url", ""), r.get("ts", 0),
                             {"grp": s.get("group") or r.get("grp", ""), "approx": not r.get("dated"),
                              "sid": r.get("sid", ""), "from": r.get("from", ""),
                              "seen": int(r.get("seen") or r.get("ts") or 0)}, hints=s.get("hint") or [],
                             hint_w=2 if (s.get("group") or r.get("grp")) in ("media", "corpkw", "indkw", "mine") else 1)
            keep[ck] = it
            out.append(it)
        _RADAR.update(ver=ver, list=out, cache=keep)
        return out


def _pub(it):
    """给界面的精简版（不带内部字段）。"""
    return {"src": it["src"], "id": it["id"], "title": it["title"], "text": (it.get("one") or "")[:180],
            "who": it.get("who", ""), "date": _day(it["ts"]) if it.get("ts") else "", "url": it.get("url", ""),
            "ind": it.get("ind", [])[:3], "trk": it.get("trk", [])[:2], "mdl": it.get("mdl", [])[:3],
            "cat": it.get("cat", ""), "kind": it.get("kind", ""), "imp": it.get("imp", ""), "todo": it.get("todo", False),
            "ts": int(it.get("ts") or 0), "grp": it.get("grp", ""), "from": it.get("from", ""),
            "approx": bool(it.get("approx")), "sid": it.get("sid", ""), "seen": int(it.get("seen") or 0)}


# ───────────────────────── 总览 / 查资料 ─────────────────────────
def _terms_stats(items, cut, hot_by="r"):
    tot = len(items) or 1
    rec_n = sum(1 for it in items if it["ts"] >= cut)
    base = rec_n / tot
    st = {}
    for it in items:
        r = 1 if it["ts"] >= cut else 0
        for k in it.get("terms", []):
            key = k.lower()
            d = st.get(key)
            if d is None:
                d = st[key] = {"k": k, "n": 0, "r": 0, "who": set()}
            d["n"] += 1
            d["r"] += r
            if it.get("who"):
                d["who"].add(it["who"])

    def fmt(d, lift=None):
        return {"k": d["k"], "n": d["n"], "r": d["r"], "src": len(d["who"]),
                "lift": round(lift, 2) if lift else None}
    hot = sorted((d for d in st.values() if d[hot_by] >= 2), key=lambda d: (-d[hot_by], -len(d["who"])))[:18]
    rising = []
    if rec_n and 0 < base < 0.92:
        for d in st.values():
            if d["r"] >= 3 and d["n"] >= 3:
                lift = (d["r"] / d["n"]) / base
                if lift >= 1.25:
                    rising.append((d, lift))
        rising.sort(key=lambda x: -(x[1] * math.log(2 + x[0]["r"])))
    return [fmt(d) for d in hot], [fmt(d, l) for d, l in rising[:16]], rec_n, base


def radar_run(rid):
    """v157：一轮抓取的结果报告：每个信息源用了哪个爬虫、过程、抓到几条；这一轮新抓到的内容按行业分。"""
    try:
        import biz_crawler as BC
        run = BC.get_run(rid)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not run:
        return {"ok": False, "error": "找不到这一轮的记录"}
    keys = set()
    for r in run.get("sources") or []:
        keys.update(r.get("keys") or [])
    got = [it for it in _radar_items() if it["id"][2:] in keys]
    got.sort(key=lambda x: -x["ts"])
    c = collections.Counter(g for it in got for g in it["ind"] + it["trk"])
    for r in run.get("sources") or []:
        r.pop("keys", None)
    return {"ok": True, "run": run, "items": [_pub(x) for x in got[:400]], "n_items": len(got),
            "by_ind": [[g, n] for g, n in c.most_common(16)]}


def radar_tops(days=1, n=6):
    """v168：雷达上每个行业、细分行业、赛道最新的几条新闻，一次算好给界面，点圆点马上就能看到，不用再等。"""
    days = int(days if days is not None else 1)             # v178：-1＝这一轮扫描，0＝累计
    win = _radar_items()
    if days < 0:
        since = _round_since()
        win = [it for it in win if since and int(it.get("seen") or 0) >= since]
    elif days > 0:
        cut = time.time() - days * 86400
        win = [it for it in win if it["ts"] >= cut]
    win.sort(key=lambda x: -x["ts"])
    out = {}
    for it in win:
        keys = set(it["trk"]) | set(it["ind"]) | {g.split("/")[0] for g in it["ind"]}
        for k in keys:
            lst = out.setdefault(k, [])
            if len(lst) < n:
                lst.append(it)
    return {"ok": True, "days": days, "tops": {k: [_pub(x) for x in v] for k, v in out.items()}}


def overview(days=30, lens="mine"):
    if lens == "market":
        return _overview_market(days)
    items = _all_items()
    now = time.time()
    days = int(days or 0)
    cut = now - days * 86400 if days > 0 else 0
    heat, l1h, mh = {}, {}, {}
    for it in items:
        r = 1 if it["ts"] >= cut else 0
        for g in it["ind"] + it["trk"]:
            h = heat.setdefault(g, [0, 0])
            h[0] += 1
            h[1] += r
        for g in {x.split("/")[0] for x in it["ind"]}:
            h = l1h.setdefault(g, [0, 0])
            h[0] += 1
            h[1] += r
        for g in it["mdl"]:
            if it["src"] == "note":
                h = mh.setdefault(g, [0, 0])
                h[0] += 1
                h[1] += r
    hot, rising, rec_n, base = _terms_stats(items, cut)
    feed = [it for it in items if it["src"] != "note" or it["biz"] >= 2]
    feed.sort(key=lambda x: -x["ts"])
    notes = [it for it in items if it["src"] == "note"]
    return {"ok": True, "days": days, "heat": heat, "l1": l1h, "models": mh, "hot": hot, "rising": rising,
            "latest": [_pub(x) for x in feed[:60]],
            "counts": {"note": len(notes), "biz_note": sum(1 for x in notes if x["biz"] >= 2),
                       "sniff": sum(1 for x in items if x["src"] == "sniff"),
                       "creator": sum(1 for x in items if x["src"] == "creator"),
                       "recent": rec_n, "base": round(base, 3),
                       "classified": sum(1 for x in items if x["ind"] or x["trk"])},
            "reports": len(_reports()), "opps": len(_read_json(OPPS_FILE, [])), "now": int(now)}


def _heat_of(win, cut24):
    heat, l1h = {}, {}
    for it in win:
        d = 1 if it["ts"] >= cut24 else 0
        for g in it["ind"] + it["trk"]:
            h = heat.setdefault(g, [0, 0])
            h[0] += 1
            h[1] += d
        for g in {x.split("/")[0] for x in it["ind"]}:
            h = l1h.setdefault(g, [0, 0])
            h[0] += 1
            h[1] += d
    return heat, l1h


def _overview_market(days=7):
    """v156：市场实时——只看市场雷达抓到的新闻。热度＝这段时间的条数；第二个数＝最近 24 小时。
    v178：days＝-1 这一轮扫描；0 累计（从开始到现在）；其它＝最近几天（2、3、7、30、365…）。
    条数用爬虫记的统计（内容库只留最新 8000 条，统计一直在），「正在升温」「提得最多」按还存着的新闻算。"""
    try:
        days = int(days)
    except Exception:
        days = 1
    now = time.time()
    cut24 = now - 86400
    allr = _radar_items()
    since, st = 0, None
    if days < 0:                                            # 这一轮扫描：这一轮抓到的
        since = _round_since()
        win = [it for it in allr if since and int(it.get("seen") or 0) >= since]
        span = max(1 / 24, (now - since) / 86400) if since else 1
    else:
        win = [it for it in allr if not days or it["ts"] >= now - days * 86400]
        try:
            import biz_crawler as BC
            st = BC.stats_window(days)
        except Exception as e:
            _log("统计读不到，先按还存着的新闻算：%s" % e)
        if st:
            since = st["since"]
        span = days if days > 0 else (max(1.0, (now - since) / 86400) if since else 1)
    if st:
        heat, l1h, n_win, n_cls, n24 = st["heat"], st["l1"], st["n"], st["cls"], st["n24"]
    else:
        heat, l1h = _heat_of(win, cut24)
        n_win, n_cls, n24 = len(win), sum(1 for x in win if x["ind"] or x["trk"]), sum(1 for x in win if x["ts"] >= cut24)
    hot, rising, rec_n, base = _terms_stats(win, now - (6 * 3600 if days in (-1, 1) else 86400), hot_by="n")
    win.sort(key=lambda x: -x["ts"])
    try:
        import biz_crawler as BC
        rs = BC.status()
    except Exception as e:
        rs = {"ok": False, "error": str(e)}
    return {"ok": True, "lens": "market", "days": days, "span": round(span, 3), "since": int(since or 0), "heat": heat, "l1": l1h,
            "models": {}, "hot": hot, "rising": rising, "latest": [_pub(x) for x in win[:80]],
            "counts": {"radar": len(allr), "window": n_win, "today": n24, "recent": rec_n, "base": round(base, 3), "classified": n_cls},
            "radar": rs, "reports": len(_reports()), "now": int(now)}


def items(ind="", trk="", mdl="", q="", src="all", days=0, limit=60, biz=False, lens="mine", sid="", grp="", offset=0,
          since=0):
    allit = _radar_items() if lens == "market" else _all_items()
    grps = {g for g in (grp or "").split(",") if g and g != "all"}
    days = int(days or 0)
    if days < 0 and lens == "market":                      # v178：这一轮扫描抓到的
        rs = _round_since()
        since = max(int(since or 0), rs) if rs else int(time.time()) + 1
        days = 0
    cut = time.time() - days * 86400 if days > 0 else 0
    ql = (q or "").strip().lower()
    out = []
    for it in allit:
        if src and src != "all" and it["src"] != src:
            continue
        if sid and it.get("sid") != sid:
            continue
        if grps and it.get("grp") not in grps:
            continue
        if cut and it["ts"] < cut:
            continue
        if since and int(it.get("seen") or 0) < since:        # v158：只看某一轮之后新抓到的
            continue
        if biz and it["src"] == "note" and it["biz"] < 2:
            continue
        if ind:
            if "/" in ind:
                if ind not in it["ind"]:
                    continue
            elif ind.startswith("sec:"):
                l1s = set((_tx()["sec"].get(ind) or {}).get("l1", []))
                if not any(g.split("/")[0] in l1s for g in it["ind"]):
                    continue
            elif not any(g.split("/")[0] == ind for g in it["ind"]):
                continue
        if trk and trk not in it["trk"]:
            continue
        if mdl and mdl not in it["mdl"]:
            continue
        if ql and ql not in it["_text"]:
            continue
        out.append(it)
    out.sort(key=lambda x: -x["ts"])
    c = collections.Counter(k for it in out for k in it.get("terms", []))
    off = max(0, int(offset or 0))                         # v158：分页
    return {"ok": True, "total": len(out), "offset": off, "items": [_pub(x) for x in out[off:off + max(1, int(limit))]],
            "top_kw": [k for k, _n in c.most_common(16)]}


# ───────────────────────── 报告 ─────────────────────────
_REP_LOCK = threading.Lock()


def _reports():
    data = _read_json(REPORTS_FILE, [])
    return data if isinstance(data, list) else []


def list_reports(kind=""):
    reps = [r for r in _reports() if not kind or r.get("kind") == kind]
    reps.sort(key=lambda r: -int(r.get("created") or 0))
    return {"ok": True, "items": reps, "dir": str(REPORT_DIR.resolve())}


def report_path(rid=""):
    """v158：报告文件在电脑上的完整路径；没给编号就是报告文件夹。"""
    if not rid:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        return REPORT_DIR.resolve()
    meta = next((r for r in _reports() if r.get("id") == rid), None)
    if not meta:
        return None
    return (REPORT_DIR / meta.get("file", "")).resolve()


def brief_struct():
    """v158：简报里会有哪些部分（给界面说明用）。"""
    return list(_STRUCT["market"])


def parse_chain(md):
    """报告里的「### 产业链图」→ {up, mid, down}：每个环节 {name, desc, me}。认不出返回 None。"""
    lines = (md or "").splitlines()
    a = next((i for i, ln in enumerate(lines) if re.match(r"^\s*#{2,5}\s*.*产业链图", ln)), -1)
    if a < 0:
        return None
    tiers = {"上游": [], "中游": [], "下游": []}
    for ln in lines[a + 1:a + 60]:
        s = ln.strip()
        if re.match(r"^#{1,5}\s", s):
            break
        s = s.strip("|").strip().lstrip("-*•·").strip()
        s = re.sub(r"^\**(上游|中游|下游)\**\s*[：:]\s*", r"\1｜", s)
        parts = [p.strip().strip("*").strip() for p in re.split(r"\s*[｜|]\s*", s)]
        if len(parts) < 2:
            continue
        tier = re.sub(r"[\s*：:]", "", parts[0])
        if tier not in tiers or not parts[1] or set(parts[1]) <= set("-:： "):
            continue
        name = parts[1]
        me = bool(re.search(r"[（(]\s*本(公司|行业|课题)\s*[）)]", name))
        name = re.sub(r"[（(]\s*本(公司|行业|课题)\s*[）)]", "", name).strip()
        desc = "｜".join(p for p in parts[2:] if p)
        tiers[tier].append({"name": name[:30], "desc": desc[:160], "me": me})
    if sum(len(v) for v in tiers.values()) < 2:
        return None
    return {"up": tiers["上游"][:6], "mid": tiers["中游"][:4], "down": tiers["下游"][:6]}


_OPP_KEYS = {"机会": "title", "适合谁": "who", "怎么切入": "how", "启动成本": "cost", "风险": "risk", "依据": "basis"}


def parse_opps(md):
    """报告里「## 机会清单」→ [{title, who, how, cost, risk, basis}]。"""
    lines = (md or "").splitlines()
    a = next((i for i, ln in enumerate(lines) if re.match(r"^\s*#{1,4}\s*.*机会清单", ln)), -1)
    if a < 0:
        return []
    out, loose = [], []
    for ln in lines[a + 1:a + 80]:
        s = ln.strip()
        if re.match(r"^#{1,3}\s", s):
            break
        s = s.strip("|").strip()
        s = re.sub(r"^(?:[-*•·]|\d+\s*[.、．)])\s*", "", s).strip()
        if not s:
            continue
        d = {}
        for p in re.split(r"\s*[｜|]\s*", s):
            m = re.match(r"^\**\s*(机会|适合谁|怎么切入|启动成本|风险|依据)\s*\**\s*[：:]\s*\**\s*(.+?)\s*\**$", p.strip())
            if m:
                d[_OPP_KEYS[m.group(1)]] = m.group(2).strip()
        if d.get("title"):
            out.append(d)
        elif len(s) >= 6 and not s.startswith("（"):
            loose.append({"title": re.split(r"[：:。]", s.replace("**", ""), 1)[0][:60], "basis": "见报告"})
    return out if out else loose[:6]


def _summary(md):
    lines = (md or "").splitlines()
    for key in ("一句话结论", "本期要点"):
        a = next((i for i, ln in enumerate(lines) if re.match(r"^\s*#{1,4}\s*" + key, ln)), -1)
        if a >= 0:
            for ln in lines[a + 1:a + 12]:
                s = ln.strip().lstrip("-*•0123456789.、 ").replace("**", "").strip()
                if s and not s.startswith("#"):
                    return s[:140]
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#"):
            return s.replace("**", "")[:140]
    return ""


def read_report(rid):
    meta = next((r for r in _reports() if r.get("id") == rid), None)
    if not meta:
        return {"ok": False, "error": "找不到这份报告（可能删掉了）"}
    p = REPORT_DIR / meta.get("file", "")
    try:
        content = p.read_text(encoding="utf-8")
    except Exception:
        return {"ok": False, "error": "报告文件读不出来：%s" % meta.get("file", "")}
    return {"ok": True, "meta": meta, "content": content, "chain": parse_chain(content), "path": str(p.resolve())}


def delete_report(rid):
    with _REP_LOCK:
        reps = _reports()
        hit = next((r for r in reps if r.get("id") == rid), None)
        if not hit:
            return {"ok": False, "error": "找不到这份报告"}
        try:
            (REPORT_DIR / hit.get("file", "")).unlink()
        except Exception:
            pass
        _write_json(REPORTS_FILE, [r for r in reps if r.get("id") != rid])
    return {"ok": True}


# ───────────────────────── 机会看板 / 常用课题 ─────────────────────────
_OPP_LOCK = threading.Lock()


def _norm(s):
    return re.sub(r"[\s，,。.、：:；;！!？?“”\"'（）()]+", "", s or "").lower()


def list_opps():
    data = _read_json(OPPS_FILE, [])
    return {"ok": True, "items": data if isinstance(data, list) else []}


def _harvest_opps(text, rid, scope_name):
    found = parse_opps(text)
    if not found:
        return 0
    n = 0
    with _OPP_LOCK:
        cur = _read_json(OPPS_FILE, [])
        cur = cur if isinstance(cur, list) else []
        seen = {_norm(o.get("title", "")) for o in cur}
        new = []
        for d in found[:10]:
            t = (d.get("title") or "").strip()
            if len(t) < 4 or _norm(t) in seen:
                continue
            seen.add(_norm(t))
            new.append({"id": "o" + hashlib.md5((t + rid).encode("utf-8")).hexdigest()[:10], "title": t[:140],
                        "who": d.get("who", "")[:120], "how": d.get("how", "")[:200], "cost": d.get("cost", "")[:20],
                        "risk": d.get("risk", "")[:160], "basis": d.get("basis", "")[:200], "scope": scope_name,
                        "report": rid, "created": int(time.time()), "status": "new", "note": "", "by": "ai"})
            n += 1
        _write_json(OPPS_FILE, (new + cur)[:500])
    return n


def opp_action(body):
    act = (body or {}).get("action", "")
    with _OPP_LOCK:
        cur = _read_json(OPPS_FILE, [])
        cur = cur if isinstance(cur, list) else []
        if act == "add":
            t = str(body.get("title") or "").strip()
            if len(t) < 2:
                return {"ok": False, "error": "先写一句话说清这个机会"}
            o = {"id": "o" + hashlib.md5((t + str(time.time())).encode("utf-8")).hexdigest()[:10], "title": t[:140],
                 "who": str(body.get("who") or "")[:120], "how": str(body.get("how") or "")[:200],
                 "cost": str(body.get("cost") or "")[:20], "risk": str(body.get("risk") or "")[:160],
                 "basis": "我自己记的", "scope": str(body.get("scope") or ""), "report": "",
                 "created": int(time.time()), "status": "watch", "note": "", "by": "you"}
            cur.insert(0, o)
        elif act == "update":
            o = next((x for x in cur if x.get("id") == body.get("id")), None)
            if not o:
                return {"ok": False, "error": "找不到这条机会"}
            if body.get("status") in OPP_STATUS:
                o["status"] = body["status"]
            if "note" in body:
                o["note"] = str(body.get("note") or "")[:500]
        elif act == "delete":
            cur = [x for x in cur if x.get("id") != body.get("id")]
        else:
            return {"ok": False, "error": "不认识的操作"}
        _write_json(OPPS_FILE, cur)
    return {"ok": True, "items": cur}


def get_topics():
    t = _read_json(TOPICS_FILE, [])
    return {"ok": True, "topics": t if isinstance(t, list) else []}


def save_topics(topics):
    out, seen = [], set()
    for t in topics or []:
        t = str(t).strip()[:40]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    _write_json(TOPICS_FILE, out[:30])
    return {"ok": True, "topics": out[:30]}


# ───────────────────────── 写报告（后台任务）─────────────────────────
_job = {"running": False, "id": 0, "kind": "", "title": "", "stage": "", "step": 0, "started": 0, "ended": 0,
        "ok": None, "error": "", "report": "", "opps": 0, "web": False, "stop": False, "holding": False, "log": []}
_job_lock = threading.Lock()


class _Stop(Exception):
    pass


def _set(**kw):
    with _job_lock:
        _job.update(kw)


def _stage(step, msg):
    with _job_lock:
        _job["step"] = step
        _job["stage"] = msg
        _job["log"] = (_job.get("log") or [])[-40:] + [[int(time.time()), msg]]


def _stopping():
    return bool(_job.get("stop"))


def job_status():
    with _job_lock:
        d = {k: v for k, v in _job.items() if k != "stop"}
        d["log"] = list(d.get("log") or [])[-8:]
    d["now"] = int(time.time())
    d["steps"] = STEPS
    return d


def _resolve(sid):
    """行业 / 赛道 / 板块编号 → (名字, 说明, 编号集合, 关键词, 代表企业)。不认识就当普通文字。"""
    tx = _tx()
    sid = (sid or "").strip()
    if not sid:
        return "全部行业", "", set(), [], ""
    if sid in tx["l2"]:
        d = tx["l2"][sid]
        return d["l1"] + "·" + d["name"], d["desc"], {sid}, d["kw"][:10] + [d["name"]], d["co"]
    if sid in tx["l1"]:
        d = tx["l1"][sid]
        kws = [tx["l2"][g]["name"] for g in d["subs"]]
        return sid, d["desc"], set(d["subs"]), kws + [sid], "、".join(
            tx["l2"][g]["co"].split("、")[0] for g in d["subs"] if tx["l2"][g]["co"])
    if sid in tx["trk"]:
        d = tx["trk"][sid]
        return d["name"], d["desc"], {sid}, d["kw"][:12] + [d["name"]], ""
    if sid in tx["sec"]:
        d = tx["sec"][sid]
        g = set()
        for n1 in d["l1"]:
            g |= set(tx["l1"][n1]["subs"])
        return d["name"] + "板块", d["desc"], g, list(d["l1"]), ""
    return sid, "", set(), [sid], ""


def _spec(kind, target, scope, days, web, depth, lens="mine", grp="", q="", size="", notes=True, focus=""):
    days = max(1, min(int(days or 30), 365))
    sname, sdesc, sgids, sterms, sco = _resolve(scope)
    spec = {"kind": kind, "target": target, "scope": scope, "days": days, "web": bool(web),
            "depth": "deep" if depth == "deep" else "quick", "scope_name": sname, "desc": sdesc, "co": sco,
            "gids": set(sgids), "terms": list(sterms), "lens": "market" if lens == "market" else "mine",
            "grp": [g for g in (grp or "").split(",") if g and g != "all"], "q": (q or "").strip()[:40],
            "size": size if size in ("short", "detail") else "normal", "use_notes": bool(notes),
            "focus": re.sub(r"\s+", " ", focus or "").strip()[:80]}
    if kind in ("model", "research") or (kind == "industry" and target and not scope):
        # 自由文字：按分类表扩展出相关行业 / 赛道（比如「蜜雪冰城」→ 新茶饮、酒店餐饮），用来多挑资料
        tname, tdesc, tg, tt, tco = _resolve(target)
        if tg:
            spec.update(scope_name=tname, desc=tdesc, co=tco, gids=set(tg), terms=list(tt))
        else:
            sc_i, sc_t, _w = _score(target)
            spec["gids"] = set(_pick(sc_i, 2, 2) + _pick(sc_t, 2, 2))
            spec["terms"] = [target] + [w for w in re.split(r"[\s,，、/]+", target) if len(w) >= 2 and w != target]
            spec["scope_name"] = target
    if kind == "market":
        rng = "最近 24 小时" if days <= 1 else "最近 %d 天" % days
        bits = [sname]
        if spec["grp"]:
            bits = [_GRP_NAMES.get(spec["grp"][0], "") or sname]
        if spec["q"]:
            bits.append("「%s」" % spec["q"])
        spec["title"] = "市场动向简报%s · %s · %s" % ("（实时）" if spec["lens"] == "market" else "", " ".join(b for b in bits if b), rng)
    elif kind == "industry":
        spec["title"] = "行业研究：%s" % spec["scope_name"]
    elif kind == "model":
        spec["title"] = "商业模式拆解：%s" % target
    elif kind == "trend":
        spec["title"] = "趋势与机会：%s" % sname
    else:
        spec["title"] = "课题研究：%s" % target
    return spec


_GRP_NAMES = {"news": "财经媒体", "corp": "大公司", "corpkw": "大公司动态", "media": "行业媒体", "indkw": "行业热词",
              "policy": "政策数据", "global": "海外", "mine": "我加的"}


def start(kind, target="", scope="", days=30, web=True, depth="quick", lens="mine", grp="", q="", size="", notes=True,
          focus=""):
    if kind not in KIND_NAMES:
        return {"ok": False, "error": "不认识的分析类型：%s" % kind}
    target = re.sub(r"\s+", " ", str(target or "")).strip()[:60]
    scope = str(scope or "").strip()[:60]
    if kind in ("model", "research") and len(target) < 2:
        return {"ok": False, "error": "先写上要分析的公司、产品或课题"}
    if kind == "industry" and not (target or scope):
        return {"ok": False, "error": "先选一个行业"}
    spec = _spec(kind, target, scope, days, web, depth, lens, grp, q, size, notes, focus)
    with _job_lock:
        if _job.get("running"):
            return {"ok": False, "error": "「%s」还在做，等它做完或者先点停止" % _job.get("title", "")}
        _job.update(running=True, id=int(_job.get("id") or 0) + 1, kind=kind, title=spec["title"], stage="准备中…",
                    step=0, started=int(time.time()), ended=0, ok=None, error="", report="", opps=0,
                    web=spec["web"], stop=False, holding=False, log=[])
        jid = _job["id"]
    threading.Thread(target=_run, args=(spec,), daemon=True, name="biz-job").start()
    _log("开始：%s%s" % (spec["title"], "（联网）" if spec["web"] else ""))
    return {"ok": True, "job_id": jid, "title": spec["title"]}


def stop():
    with _job_lock:
        if not _job.get("running"):
            return {"ok": True, "idle": True}
        _job["stop"] = True
        holding = _job.get("holding")
    if holding and _hooks.get("cancel"):
        try:
            _hooks["cancel"]()
        except Exception:
            pass
    return {"ok": True}


def _fulltext(term, limit=200):
    """在笔记全文（含文字稿）里找提到这个词的笔记，返回文件名集合。写报告时才用（要读所有笔记，约 1 秒）。"""
    term = (term or "").strip().lower()
    found = set()
    if len(term) < 2 or not NOTE_DIR.exists():
        return found
    for e in os.scandir(NOTE_DIR):
        if not e.name.endswith(".md") or e.name.startswith("_"):
            continue
        try:
            with open(e.path, encoding="utf-8", errors="replace") as fh:
                if term in fh.read().lower():
                    found.add(e.name)
        except Exception:
            continue
        if len(found) >= limit:
            break
    return found


def _select_local(spec, n_notes, n_sigs):
    """从你的资料里挑和这次分析相关的：行业 / 赛道对得上的、提到关键词的；没限定范围就挑商业味浓的。"""
    gids = spec["gids"]
    terms = [t.lower() for t in spec["terms"] if t and len(t) >= 2]
    full = _fulltext(spec["target"]) if spec["kind"] in ("model", "research") or (
        spec["kind"] == "industry" and spec["target"] and not spec["gids"]) else set()
    cut = time.time() - spec["days"] * 86400 if spec["kind"] == "market" else 0
    scored = []
    for it in _all_items():
        if cut and it["ts"] < cut:
            continue
        s = 0.0
        if gids:
            s += 4 * len(gids & (set(it["ind"]) | set(it["trk"])))
        if terms:
            s += 3 * min(4, sum(1 for t in terms if t in it["_text"]))
        if full and it["src"] == "note" and it["id"] in full:
            s += 3
        if not gids and not terms:
            if it["src"] == "note" and it["biz"] < 2:
                continue
            s += 1
        if s <= 0:
            continue
        if it["src"] == "note":
            s += 0.5 * min(it["biz"], 4) - (2 if it.get("todo") else 0)
        scored.append((s, it["ts"], it))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    notes = [it for _s, _t, it in scored if it["src"] == "note"][:n_notes]
    sigs = [it for _s, _t, it in scored if it["src"] != "note"][:n_sigs]
    return notes, sigs


def _select_radar(spec, n):
    """v156：市场雷达抓到的新闻里，和这次分析相关的（新的优先）。没限定范围就按时间取最新的。"""
    gids = spec["gids"]
    terms = [t.lower() for t in spec["terms"] if t and len(t) >= 2]
    cut = time.time() - (spec["days"] if spec["kind"] == "market" else 30) * 86400
    grps = set(spec.get("grp") or [])
    ql = (spec.get("q") or "").lower()
    scored = []
    for it in _radar_items():
        if it["ts"] < cut:
            continue
        if grps and it.get("grp") not in grps:             # v158：简报只用界面上筛出来的那些新闻
            continue
        if ql and ql not in it["_text"]:
            continue
        s = 0
        if gids:
            s += 4 * len(gids & (set(it["ind"]) | set(it["trk"])))
        if terms:
            s += 3 * min(3, sum(1 for t in terms if t in it["_text"]))
        if not gids and not terms:
            s = 1
        if s > 0:
            scored.append((s, it["ts"], it))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [it for _s, _t, it in scored[:n]]


_QUERIES = {
    "industry": ["{t} 行业 市场规模 {y}", "{t} 产业链 上游 下游 龙头企业", "{t} 行业 竞争格局 商业模式",
                 "{t} 行业 趋势 政策 机会 {y}"],
    "model": ["{t} 商业模式 盈利模式", "{t} 营收 利润 财报 {y}", "{t} 供应链 上游 供应商 产业链", "{t} 竞争对手 护城河"],
    "research": ["{t} 市场规模 现状 {y}", "{t} 产业链 主要玩家", "{t} 商业模式 怎么赚钱", "{t} 趋势 机会 风险 {y}"],
    "trend": ["{t} 趋势 {y} {y1}", "{t} 新机会 创业 {y}", "{t} 政策 变化 {y}"],
    "market": ["{t} 最新动态 {y}年{m}月", "{t} 行业 新闻 本周", "{t} 融资 新品 {y}年{m}月"],
}


def _web(spec, deep):
    try:
        import web_tools
    except Exception:
        _stage(2, "联网模块没加载，跳过联网")
        return "", []
    now = datetime.date.today()
    t = spec["target"] if spec["kind"] in ("model", "research") else spec["scope_name"]
    if spec["kind"] == "industry":
        t = spec["scope_name"].split("·")[-1]
    if t == "全部行业":
        t = "中国 商业 市场"
    qs = [q.format(t=t, y=now.year, y1=now.year + 1, m=now.month) for q in _QUERIES[spec["kind"]]]
    qs = qs if deep else qs[:(3 if spec["kind"] in ("industry", "model", "research") else 2)]
    budget = 18000 if deep else 13000
    per = budget // max(1, len(qs))
    chunks, srcs, seen = [], [], set()
    for i, q in enumerate(qs, 1):
        if _stopping():
            raise _Stop()
        _stage(2, "上网查（%d/%d）：%s" % (i, len(qs), q))
        try:
            material, sources = web_tools.gather(q, read_count=5 if deep else 3)
        except Exception as e:
            _stage(2, "这一条没查成（%s），接着查下一条" % str(e)[:40])
            continue
        if sources:
            chunks.append((material or "")[:per])
            for st, su in sources:
                if su and su not in seen:
                    seen.add(su)
                    srcs.append((st or su, su))
    _stage(2, "网上读到 %d 个网页" % len(srcs) if srcs else "网上没读到有用的网页（网络或搜索引擎的问题），只用你的资料")
    return "\n\n".join(chunks), srcs


_HEAD = ("今天是 {today}。你是一位资深的商业分析师，正在给一位关注商业机会的中文用户写分析报告。\n"
         "写法：说人话、具体、少空话；关键数字写清楚是多少、出自哪里；拿不准的写「待核实」，不要编造数据和来源；"
         "引用下面的资料时，标上【笔记N】或网页的名字。你如果能联网搜索，请再搜一搜，补充最新的数据和动态，"
         "并把网址写进「信息来源」。\n"
         "格式：全文用 Markdown；第一行写「# {title}」；下面只用我列出的二级标题（「## 」开头，括号里的说明不要写进标题），"
         "按顺序写；不要开场白，不要寒暄，不要反问我。\n\n")

_CHAIN = ("「## 产业链上下游」这一节的最后，单独写一个三级标题「### 产业链图」，下面严格按这个格式，每行一个环节，"
          "上游至少 2 行、中游 1～2 行、下游至少 2 行，环节名称要短（2～10 个字），用全角竖线「｜」分隔：\n"
          "- 上游｜环节名称｜这一环提供什么、代表企业、对中游的议价能力强/中/弱\n"
          "- 中游｜环节名称（{me}）｜……\n"
          "- 下游｜环节名称｜……\n"
          "{who}所在的那一环，环节名称后面加「（{me}）」。\n\n")

_OPP = ("「## 机会清单」里写 {n} 个具体的机会，每个机会一行，严格按这个格式（全角竖线「｜」分隔，六项都要有）：\n"
        "- 机会：一句话说清做什么｜适合谁：……｜怎么切入：……｜启动成本：低/中/高｜风险：……｜依据：引用的资料或数据\n"
        "机会要具体到普通人或小团队能动手的程度，不要写「布局 AI」「抓住风口」这种空话。\n\n")

_STRUCT = {
    "market": ["本期要点（3～5 条，每条一句话）", "主要动向（按行业分组；每条写发生了什么、意味着什么、出处）",
               "值得注意的信号（数据变化、新玩家、新打法、政策）", "商业模式的变化", "机会清单", "风险提示",
               "接下来观察什么（3～5 个可以持续跟踪的指标或信号）", "信息来源"],
    "industry": ["一句话结论", "行业概况（是什么、市场规模、增速、处在什么阶段）",
                 "产业链上下游（上游供应什么、下游卖给谁、利润集中在哪一环、谁说了算）", "主要玩家和竞争格局",
                 "主流商业模式（这个行业靠什么赚钱，哪种模式利润高）", "最近的动向",
                 "未来 1～3 年的趋势（每条写趋势、依据、确定性高/中/低）", "机会清单", "风险",
                 "接下来观察什么（3～5 个指标或信号）", "信息来源"],
    "model": ["一句话结论", "它是做什么的", "客户是谁（客户细分）", "给客户的价值（价值主张）",
              "收入从哪来（每种收入、大概占比、怎么定价）", "成本结构和单位经济（主要成本、毛利率、一单 / 一店 / 一个用户赚多少）",
              "产业链上下游（上游是谁、下游是谁、钱在哪一环最多、它在链条里的位置和议价能力）",
              "护城河（别人为什么很难抄）", "增长打法", "风险和隐患",
              "可借鉴的地方（普通人或小团队能学什么、怎么用到自己的生意上，写 3～5 条具体做法）", "信息来源"],
    "trend": ["一句话结论", "现在的格局", "趋势（5～8 条，每条写趋势是什么、依据（引用资料）、大概什么时候、确定性高/中/低）",
              "机会清单", "不建议碰的方向", "接下来观察什么", "信息来源"],
    "research": ["一句话结论", "现状（市场规模、增速、用户、发展阶段，带数字和出处）", "产业链上下游", "主要玩家",
                 "商业模式（谁在赚钱、怎么赚）", "趋势", "机会清单", "风险", "接下来观察什么", "信息来源"],
}
_MARKERS = {"market": ["主要动向", "接下来观察"], "industry": ["产业链图", "机会清单"], "model": ["产业链图", "可借鉴"],
            "trend": ["趋势", "机会清单"], "research": ["产业链", "机会清单"]}


def _task_line(spec):
    k = spec["kind"]
    if k == "market":
        line = "任务：根据下面的资料，写一份「%s」的市场动向简报，覆盖%s。" % (
            spec["scope_name"], "最近 24 小时" if spec["days"] <= 1 else "最近 %d 天" % spec["days"])
        if spec.get("grp"):
            line += "新闻只来自这几类信息源：%s。" % "、".join(_GRP_NAMES.get(g, g) for g in spec["grp"])
        if spec.get("q"):
            line += "新闻都是提到「%s」的，简报围绕它来写。" % spec["q"]
        if spec.get("focus"):
            line += "用户特别想知道：%s，这部分要写充分。" % spec["focus"]
        line += {"short": "篇幅要短：全文 800 字以内，每部分只写最重要的两三条。",
                 "detail": "写详细：全文 3000～5000 字，每条动向都写清来龙去脉、影响和出处。"}.get(spec.get("size"), "篇幅适中：全文 1500～2500 字。")
        return line
    if k == "industry":
        extra = "；".join(x for x in (spec["desc"], ("代表企业举例：" + spec["co"]) if spec["co"] else "") if x)
        return "任务：研究「%s」这个行业%s。" % (spec["scope_name"], "（%s）" % extra if extra else "")
    if k == "model":
        return "任务：拆解「%s」的商业模式，重点讲清楚它的上下游产业链和它在链条里的位置。" % spec["target"]
    if k == "trend":
        return "任务：分析「%s」未来 1～3 年的趋势，并找出具体的机会。" % spec["scope_name"]
    return ("任务：研究「%s」这个课题。如果它谈不上完整的产业链，就写清楚相关的上下游角色（谁供应、谁付钱、谁赚钱）。"
            % spec["target"])


def _fmt_notes(notes, budget):
    out, used = [], 0
    for i, it in enumerate(notes, 1):
        s = "【笔记%d】%s｜%s｜收进来：%s%s\n" % (i, it["title"], it.get("who") or "作者不详", _day(it["ts"]),
                                          "｜" + it["cat"] if it.get("cat") else "")
        if it.get("one"):
            s += "一句话：%s\n" % it["one"]
        if it.get("pts"):
            s += "要点：%s\n" % "；".join(it["pts"][:6])
        if used + len(s) > budget:
            break
        out.append(s)
        used += len(s)
    return "\n".join(out)


def _fmt_radar(items, budget):
    out, used = [], 0
    for it in items:
        s = "- [%s] %s：%s%s\n" % (_day(it["ts"]) or "日期不详", it.get("who") or "", it["title"],
                                 (" —— " + it["one"][:100]) if it.get("one") else "")
        if used + len(s) > budget:
            break
        out.append(s)
        used += len(s)
    return "".join(out)


def _fmt_sigs(sigs, budget):
    out, used = [], 0
    for it in sigs:
        src = {"sniff": "网站", "creator": "博主"}.get(it["src"], "")
        s = "- [%s] %s「%s」：%s%s\n" % (_day(it["ts"]) or "日期不详", src, it.get("who") or "", it["title"],
                                     (" —— " + it["one"][:120]) if it.get("one") else "")
        if used + len(s) > budget:
            break
        out.append(s)
        used += len(s)
    return "".join(out)


def _prompt(spec, notes, sigs, web_txt, radar=None):
    k = spec["kind"]
    head = _HEAD.format(today=datetime.date.today().isoformat(), title=spec["title"])
    parts = [head, _task_line(spec), "\n\n二级标题（按顺序）：\n" + "\n".join("## " + s for s in _STRUCT[k]) + "\n\n"]
    if k in ("industry", "model", "research"):
        me = {"industry": "本行业", "model": "本公司", "research": "本课题"}[k]
        who = {"industry": "这个行业", "model": "「%s」" % spec["target"], "research": "这个课题"}[k]
        parts.append(_CHAIN.format(me=me, who=who))
    if k != "model":
        parts.append(_OPP.format(n={"market": "3～5", "trend": "5～8"}.get(k, "4～6")))
    nb = 13000 if spec["depth"] == "deep" else 10000
    if spec.get("lens") == "market":
        nb = 4000
    parts.append("=== 资料①：用户自己收藏、整理过的笔记（%d 篇，按相关度排；日期是收进来的日期，不一定是发布日期）===\n%s\n"
                 % (len(notes), _fmt_notes(notes, nb) or "（没有相关的笔记）"))
    parts.append("=== 资料②：网站和博主的最新动态（%d 条）===\n%s\n" % (len(sigs), _fmt_sigs(sigs, 4500) or "（没有）"))
    parts.append("=== 资料③：小助刚从网上搜到的网页摘录 ===\n%s\n" % ((web_txt or "").strip() or "（这次没有联网或没搜到）"))
    parts.append("=== 资料④：市场实时新闻（小助的爬虫定时从财经媒体、大公司官网、行业媒体抓来的，新的在前）===\n%s\n"
                 % (_fmt_radar(radar or [], 9000 if spec.get("lens") == "market" else 5000) or "（还没有抓到相关的）"))
    parts.append("\n请开始写，第一行是「# %s」。" % spec["title"])
    return "".join(parts)


def _ask(prompt, spec):
    f = _hooks.get("llm")
    if not f:
        raise RuntimeError("没有可用的 AI（后台没接上 AI 池）")
    text, engine = f(prompt, what=spec["title"], markers=_MARKERS[spec["kind"]],
                     on_stage=lambda m: _stage(3, str(m)[:120]), should_stop=_stopping,
                     on_hold=lambda v: _set(holding=bool(v)))
    text = (text or "").strip()
    if _stopping():
        raise _Stop()
    if len(text) < 200:
        raise RuntimeError("AI 的回复太短，没写成报告")
    return text, engine or "AI"


def _save(spec, text, notes, sigs, web_src, engine):
    now = datetime.datetime.now()
    rid = now.strftime("%Y%m%d-%H%M%S") + "-" + spec["kind"]
    slug = re.sub(r"[\\/:*?\"<>|\s·：]+", "_", spec["title"]).strip("_")[:40]
    fname = rid + "-" + slug + ".md"
    body = text.strip()
    if not body.lstrip().startswith("# "):
        body = "# %s\n\n%s" % (spec["title"], body)
    tail = ["", "## 这份报告用到的资料", ""]
    tail.append("- 你的笔记 %d 篇、最新动态 %d 条、市场实时新闻 %d 条%s" % (len(notes), len(sigs), spec.get("n_radar", 0),
                                                         "、网页 %d 个" % len(web_src) if web_src else ""))
    for t, u in web_src[:30]:
        tail.append("- [%s](%s)" % (re.sub(r"[\[\]]", "", t)[:80] or u, u))
    tail += ["", "（%s · %s写 · 超能小助「商业」）" % (now.strftime("%Y-%m-%d %H:%M"), engine)]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / fname).write_text(body + "\n" + "\n".join(tail) + "\n", encoding="utf-8")
    n_opps = _harvest_opps(body, rid, spec["scope_name"]) if spec["kind"] != "model" else 0
    meta = {"id": rid, "kind": spec["kind"], "title": spec["title"], "target": spec["target"], "scope": spec["scope"],
            "scope_name": spec["scope_name"], "created": int(time.time()), "file": fname, "engine": engine,
            "notes": len(notes), "sigs": len(sigs), "web": len(web_src), "summary": _summary(body),
            "chain": bool(parse_chain(body)), "opps": n_opps, "note_ids": [it["id"] for it in notes[:30]],
            "days": spec["days"], "web_on": spec["web"], "depth": spec["depth"], "lens": spec.get("lens", "mine"),
            "radar": spec.get("n_radar", 0), "size": spec.get("size", ""), "grp": spec.get("grp", []), "q": spec.get("q", ""),
            "focus": spec.get("focus", "")}
    with _REP_LOCK:
        reps = _reports()
        reps.insert(0, meta)
        _write_json(REPORTS_FILE, reps[:400])
    return rid, n_opps


def _run(spec):
    try:
        deep = spec["depth"] == "deep"
        _stage(1, "从你收进来的资料里挑相关的…")
        notes, sigs = _select_local(spec, 34 if deep else 24, 40 if spec["kind"] == "market" else 24)
        if spec["kind"] == "market" and not spec.get("use_notes", True):
            notes, sigs = [], []                            # v158：简报设置里没勾「加上我的笔记」
        n_r = {"short": 40, "detail": 90}.get(spec.get("size"), 60) if spec["kind"] == "market" else 30
        radar = _select_radar(spec, n_r if spec.get("lens") == "market" else 30)
        _stage(1, "挑出 %d 篇笔记、%d 条动态、%d 条市场新闻" % (len(notes), len(sigs), len(radar)))
        if _stopping():
            raise _Stop()
        web_txt, web_src = "", []
        if spec["web"]:
            web_txt, web_src = _web(spec, deep)
        else:
            _stage(2, "没勾联网，这一步跳过")
        if _stopping():
            raise _Stop()
        _stage(3, "交给 AI 写报告…")
        text, engine = _ask(_prompt(spec, notes, sigs, web_txt, radar), spec)
        _stage(4, "存报告…")
        spec["n_radar"] = len(radar)
        rid, n_opps = _save(spec, text, notes, sigs, web_src, engine)
        _set(running=False, ok=True, ended=int(time.time()), report=rid, opps=n_opps, stage="写好了")
        _log("写好了：%s（%s%s）" % (spec["title"], engine, "，新增 %d 个机会" % n_opps if n_opps else ""))
    except _Stop:
        _set(running=False, ok=False, ended=int(time.time()), error="已按你的要求停止", stage="")
        _log("已停止：%s" % spec["title"])
    except Exception as e:
        msg = str(e)[:300] or e.__class__.__name__
        if "停止" in msg:
            msg = "已按你的要求停止"
        _set(running=False, ok=False, ended=int(time.time()), error=msg, stage="")
        _log("没做完：%s（%s）" % (spec["title"], msg))
    finally:
        _set(holding=False)
