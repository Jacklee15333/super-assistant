"""
graph_nodes.py — 知识云图的「统一节点」供给

把超能小助里各个板块的数据，都转成同一种「节点」形状，喂给前端星图。
这样星图就不只来自对话，还能来自嗅探、视频，甚至全部数据。

节点统一形状：
  {
    "id":        唯一 id（带 scope 前缀，避免跨源撞车），
    "title":     标题,
    "when":      ISO 时间串（排序/算近期用，可空）,
    "when_human":可读时间,
    "text":      用于关键词聚类的正文（已去 markdown/链接）,
    "scope":     "chat" | "video" | "sniff" | "insight" ...（「全部」时按它上色）,
    "scope_label": 中文来源名,
    "url":       原始链接（视频/嗅探有；点开可跳）,
    "open":      前端点开方式： "conversation"（回到对话） | "video_note"（看笔记） | "url"（开链接）,
    "ref":       open 需要的引用（对话/笔记的文件名等）,
  }

scope 取值：
  chat    对话存档
  video   视频笔记
  sniff   嗅探（关注博主扫到的视频 + 待办新视频）
  insight 洞察（主动研究/资讯摘要）—— 归到「嗅探」大类一起，也可单列
  all     以上全部
"""

import re
import json
import datetime
from pathlib import Path


# ──────────────────────────── 工具 ────────────────────────────
def _mem_dir():
    import agent_core
    return agent_core.MEMORY_DIR


def _strip(text):
    """去 markdown / 链接 / 多余空白，留干净文字给关键词用。"""
    t = text or ""
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[#*>`_~|>\-]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _iso_from_stamp(stem):
    """从 'xxx-YYYYMMDD-HHMMSS' 这种文件名里抠出 ISO 时间。"""
    m = re.search(r"(\d{8})-(\d{6})", stem)
    if not m:
        m2 = re.search(r"(\d{8})", stem)
        if m2:
            d = m2.group(1)
            return "%s-%s-%sT00:00:00" % (d[:4], d[4:6], d[6:8]), \
                   "%s-%s-%s" % (d[:4], d[4:6], d[6:8])
        return "", ""
    d, t = m.group(1), m.group(2)
    iso = "%s-%s-%sT%s:%s:%s" % (d[:4], d[4:6], d[6:8], t[:2], t[2:4], t[4:6])
    human = "%s-%s-%s %s:%s" % (d[:4], d[4:6], d[6:8], t[:2], t[2:4])
    return iso, human


# ──────────────────────────── 各 scope 的节点 ────────────────────────────
def _chat_nodes():
    """对话存档 → 节点。复用 conversation_memory 的解析。"""
    try:
        import conversation_memory as cm
        items = cm.list_conversations(limit=800, with_text=True)
    except Exception:
        return []
    out = []
    for it in items:
        out.append({
            "id": "chat:" + str(it.get("id")),
            "title": it.get("title") or "未命名对话",
            "when": it.get("when") or "",
            "when_human": it.get("when_human") or "",
            "text": it.get("text") or it.get("preview") or it.get("title") or "",
            "turns": it.get("turns") or 1,
            "chars": it.get("chars") or 0,
            "starred": bool(it.get("starred")),
            "scope": "chat",
            "scope_label": "对话",
            "url": "",
            "open": "conversation",
            "ref": str(it.get("id")),
        })
    return out


def _video_nodes():
    """视频笔记 → 节点。读 video_notes/*.md，标题 + AI 分析 + 文字稿当聚类正文。"""
    d = _mem_dir() / "video_notes"
    out = []
    if not d.exists():
        return out
    for p in sorted(d.glob("*.md"), reverse=True):
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = raw.splitlines()
        title = ""
        for ln in lines:
            s = ln.strip().lstrip("#").strip()
            if s:
                title = s[:60]
                break
        # 取链接 / 作者 / 时间
        url = ""
        when_human = ""
        muri = re.search(r"来源链接[:：]\s*(\S+)", raw)
        if muri:
            url = muri.group(1).strip()
        mtime = re.search(r"提取时间[:：]\s*([\d\-: ]+)", raw)
        if mtime:
            when_human = mtime.group(1).strip()
        iso, human2 = _iso_from_stamp(p.stem)
        if not when_human:
            when_human = human2
        # 聚类正文：去掉文字稿太长的尾巴，留标题 + 分析 + 文字稿前段，足够聚类又不臃肿
        body = _strip(raw)
        text = body[:1200]
        out.append({
            "id": "video:" + p.name,
            "title": title or p.stem,
            "when": iso,
            "when_human": when_human,
            "text": text,
            "chars": len(body),
            "starred": False,
            "scope": "video",
            "scope_label": "视频",
            "url": url,
            "open": "video_note",
            "ref": p.name,
        })
    return out


def _sniff_nodes():
    """嗅探 → 节点。来自 creator_watch.json：关注博主扫到/缓存的视频 + 待办新视频。
    每条视频是一颗星，正文用「博主名 + 视频标题」，按博主聚类很自然。"""
    store_path = _mem_dir() / "creator_watch.json"
    out = []
    if not store_path.exists():
        return out
    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
    except Exception:
        return out

    seen = set()

    def add(creator_title, v, is_new):
        vid = str(v.get("vid") or v.get("url") or "")
        key = (creator_title, vid)
        if not vid or key in seen:
            return
        seen.add(key)
        title = v.get("title") or v.get("url") or "(无标题)"
        when_human = v.get("when_human") or ""
        iso = ""
        if when_human and re.match(r"^\d{4}-\d{2}-\d{2}", when_human):
            iso = when_human.replace(" ", "T")
            if "T" not in iso:
                iso += "T00:00:00"
        # 正文带上博主名，让同博主/同主题的视频聚到一起
        text = (creator_title + " " + title)
        out.append({
            "id": "sniff:" + (creator_title or "") + "|" + vid,
            "title": title,
            "when": iso,
            "when_human": when_human,
            "text": text,
            "creator": creator_title,
            "starred": bool(is_new),     # 待办新视频高亮一下
            "scope": "sniff",
            "scope_label": "嗅探",
            "url": v.get("url") or "",
            "open": "url",
            "ref": v.get("url") or "",
        })

    # 1) 缓存里每个博主的视频
    vc = store.get("video_cache") or {}
    # 博主 id → 名字
    id2name = {}
    for c in store.get("creators", []):
        id2name[c.get("id")] = c.get("title") or ""
    for cid, cache in vc.items():
        cname = (cache.get("title") or id2name.get(cid) or "未知博主")
        for v in (cache.get("videos") or []):
            add(cname, v, False)
    # 2) 待办「本次新增」新视频（高亮）
    for f in store.get("findings", []):
        cname = f.get("creator_title") or id2name.get(f.get("creator_id")) or "未知博主"
        add(cname, {"vid": f.get("vid"), "url": f.get("url"),
                    "title": f.get("title"), "when_human": ""}, True)
    return out


def _insight_nodes():
    """洞察 → 节点。来自 insight_digests.json（主动研究/资讯摘要）。"""
    p = _mem_dir() / "insight_digests.json"
    out = []
    if not p.exists():
        return out
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return out
    # 结构可能是 list 或 dict；尽量兼容
    digests = []
    if isinstance(data, list):
        digests = data
    elif isinstance(data, dict):
        for key in ("digests", "items", "entries", "list"):
            if isinstance(data.get(key), list):
                digests = data[key]
                break
        if not digests:
            # dict of id->obj
            for k, v in data.items():
                if isinstance(v, dict):
                    digests.append(v)
    for i, dg in enumerate(digests[:400]):
        if not isinstance(dg, dict):
            continue
        title = (dg.get("title") or dg.get("headline") or dg.get("name")
                 or dg.get("summary") or "洞察")
        title = str(title)[:60]
        body = " ".join(str(dg.get(k, "")) for k in
                        ("title", "summary", "digest", "content", "text", "takeaway", "tags"))
        when = dg.get("date") or dg.get("when") or dg.get("ts") or dg.get("created_at") or ""
        when = str(when)
        iso = ""
        mh = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", when)
        when_human = ""
        if mh:
            iso = "%s-%s-%sT00:00:00" % (mh.group(1), mh.group(2), mh.group(3))
            when_human = "%s-%s-%s" % (mh.group(1), mh.group(2), mh.group(3))
        out.append({
            "id": "insight:" + str(dg.get("id") or i),
            "title": title,
            "when": iso,
            "when_human": when_human,
            "text": _strip(body) or title,
            "starred": False,
            "scope": "insight",
            "scope_label": "洞察",
            "url": dg.get("url") or "",
            "open": "url" if dg.get("url") else "none",
            "ref": dg.get("url") or "",
        })
    return out


# ──────────────────────────── 对外入口 ────────────────────────────
SCOPES = {
    "chat": _chat_nodes,
    "video": _video_nodes,
    "sniff": _sniff_nodes,
    "insight": _insight_nodes,
}

# 「嗅探」范围里把洞察也算进去（都是外部信息流）
SCOPE_GROUPS = {
    "sniff": ["sniff", "insight"],
}


def get_nodes(scope="all"):
    """按范围返回统一节点。scope: chat / video / sniff / insight / all。"""
    scope = (scope or "all").strip().lower()
    nodes = []
    counts = {}
    if scope == "all":
        srcs = list(SCOPES.keys())
    elif scope in SCOPE_GROUPS:
        srcs = SCOPE_GROUPS[scope]
    elif scope in SCOPES:
        srcs = [scope]
    else:
        srcs = list(SCOPES.keys())
    for s in srcs:
        fn = SCOPES.get(s)
        if not fn:
            continue
        try:
            got = fn() or []
        except Exception:
            got = []
        counts[s] = len(got)
        nodes.extend(got)
    return {"ok": True, "scope": scope, "items": nodes, "counts": counts,
            "total": len(nodes)}


def scope_overview():
    """各范围有多少条，给前端范围选择器显示数量。"""
    out = {}
    for s, fn in SCOPES.items():
        try:
            out[s] = len(fn() or [])
        except Exception:
            out[s] = 0
    return {"ok": True, "counts": out}
