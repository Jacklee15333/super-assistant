"""超能小助 · 推文拆成「博主原话 + 链接原文」（v94）

推文不像文章：有的只是一句话，内容在转发的原帖、引用的帖子、或者附带的链接文章里。
存成笔记时分成两部分：
  🗣 博主原话   —— 这个博主自己说的话（纯转发就写明「没说话，转发了谁」）
  🔗 链接原文   —— 转发的原帖、引用的帖子、X 长文、链接到的网页文章，各自的全文

数据从哪来（从稳到不稳）：
  1. 扫描博主时 X 时间线本来就带着：转发的原帖全文、引用的帖子、链接的真实地址（snapshot()，存进发现记录）；
  2. 只有一句推文文字时（老记录）：从文字里认出「RT @谁:」和 t.co 短链；
  3. 联网补全（后台做，不耽误存笔记）：按推文编号取完整推文（fxtwitter → X 官方嵌入接口），
     t.co 短链解开成真实地址，网页文章用 doc_import 读正文。
任何一步拿不到就跳过，写明「没抓到，原文见链接」，绝不卡住。
"""
from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ART_MAX = 20000          # 一篇链接文章最多放多少字
_TCO = re.compile(r"https?://t\.co/[A-Za-z0-9]+")
_STATUS = re.compile(r"https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+|i/web)/status(?:es)?/(\d+)", re.I)
_ARTICLE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/i/article/(\d+)", re.I)
_MEDIA = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/[^/\s]+/status/\d+/(?:photo|video)/\d+", re.I)


def _log(msg):
    try:
        print("[推文] " + msg, flush=True)
    except Exception:
        pass


# ════════════════ 1. 把各种来源的推文数据统一成一个样子 ════════════════
# X 时间线（老格式 legacy / syndication）、GraphQL、fxtwitter、官方嵌入接口，字段名都不一样。

def _g(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _media_of(t, lg):
    """v153：推文里的图片地址、有没有视频（X 接口 / fxtwitter / 官方嵌入接口三种格式都认）。"""
    photos, seen, video = [], set(), False

    def addp(u):
        u = (u or "").strip()
        if u.startswith("http") and u.split("?")[0] not in seen:
            seen.add(u.split("?")[0])
            photos.append(u)
    for src in (_g(lg, "extended_entities", "media"), _g(lg, "entities", "media"), t.get("mediaDetails")):
        if isinstance(src, list):
            for m in src:
                if isinstance(m, dict):
                    if m.get("type") == "photo":
                        addp(m.get("media_url_https") or m.get("media_url"))
                    elif m.get("type") in ("video", "animated_gif"):
                        video = True
    md = t.get("media")
    if isinstance(md, dict):
        for p in md.get("photos") or []:
            if isinstance(p, dict):
                addp(p.get("url"))
        if md.get("videos"):
            video = True
        for m in md.get("all") or []:
            if isinstance(m, dict):
                if m.get("type") == "photo":
                    addp(m.get("url"))
                elif m.get("type") in ("video", "gif"):
                    video = True
    if isinstance(t.get("photos"), list):            # 官方嵌入接口
        for p in t["photos"]:
            if isinstance(p, dict):
                addp(p.get("url"))
    if isinstance(t.get("video"), dict):
        video = True
    return photos[:8], video


def _node(t, depth=0):
    """→ {id, name, handle, text, links:[真实地址], rt: 节点|None, quote: 节点|None, article: {title,text}|None}"""
    if not isinstance(t, dict) or depth > 3:
        return None
    if t.get("_c"):                                   # 自己压过的小字典（扫描时存下的），原样读回
        return {"id": t.get("id") or "", "name": t.get("name") or "", "handle": t.get("handle") or "",
                "text": t.get("text") or "", "links": list(t.get("links") or []),
                "rt": _node(t.get("rt"), depth + 1), "quote": _node(t.get("quote"), depth + 1),
                "article": t.get("article"), "photos": list(t.get("photos") or []), "video": bool(t.get("video"))}
    if t.get("__typename") == "TweetWithVisibilityResults" and isinstance(t.get("tweet"), dict):
        t = t["tweet"]
    gql = isinstance(t.get("legacy"), dict)
    lg = t["legacy"] if gql else t
    # 作者
    user = (_g(t, "core", "user_results", "result", "legacy") or _g(t, "core", "user_results", "result", "core")
            or t.get("user") or t.get("author") or {})
    name = user.get("name") or ""
    handle = user.get("screen_name") or ""
    # 正文：长推文（note tweet）优先
    note = _g(t, "note_tweet", "note_tweet_results", "result") or {}
    text = (note.get("text") or (t.get("text") if not gql else None) or lg.get("full_text")
            or lg.get("text") or t.get("full_text") or "")
    if isinstance(text, dict):                       # fxtwitter 的 raw_text 是个对象
        text = text.get("text") or ""
    # 链接：t.co → 真实地址
    links, repl = [], {}
    ents = []
    for src in (lg.get("entities"), note.get("entity_set"), t.get("entities")):
        if isinstance(src, dict):
            ents += [u for u in (src.get("urls") or []) if isinstance(u, dict)]
    for u in ents:
        exp = u.get("expanded_url") or u.get("expanded") or ""
        short = u.get("url") or ""
        if short and exp:
            repl[short] = exp
        if exp and exp not in links:
            links.append(exp)
    for short, exp in repl.items():
        text = text.replace(short, exp)
    tid = str(t.get("rest_id") or lg.get("id_str") or t.get("id_str") or t.get("id") or "")
    photos, video = _media_of(t, lg)
    out = {"id": tid, "name": name, "handle": handle, "text": (text or "").strip(), "links": links,
           "rt": None, "quote": None, "article": None, "photos": photos, "video": video}
    rt = (_g(lg, "retweeted_status_result", "result") or lg.get("retweeted_status")
          or t.get("retweeted_status") or t.get("retweeted_tweet"))
    if rt:
        out["rt"] = _node(rt, depth + 1)
    q = (_g(t, "quoted_status_result", "result") or lg.get("quoted_status") or t.get("quoted_status")
         or t.get("quoted_tweet") or t.get("quote"))
    if q:
        out["quote"] = _node(q, depth + 1)
    art = t.get("article")
    if isinstance(art, dict):
        body = ""
        blocks = _g(art, "content", "blocks")
        if isinstance(blocks, list):
            body = "\n\n".join((b.get("text") or "").strip() for b in blocks if isinstance(b, dict) and (b.get("text") or "").strip())
        out["article"] = {"title": art.get("title") or "", "text": body or art.get("preview_text") or ""}
    return out


def _compact(n):
    if not n:
        return None
    out = {k: n[k] for k in ("id", "name", "handle", "text", "links", "photos", "video") if n.get(k)}
    out["_c"] = 1
    for k in ("rt", "quote"):
        if n.get(k):
            out[k] = _compact(n[k])
    if n.get("article"):
        out["article"] = n["article"]
    return out


def snapshot(tweet_obj):
    """扫描时调用：把 X 返回的一条推文压成小字典，存进「发现」记录，提取时直接用（不用再联网）。"""
    try:
        return _compact(_node(tweet_obj))
    except Exception:
        return None


# ════════════════ 2. 联网补全 ════════════════

def _opener(url):
    handlers = []
    try:
        import web_tools
        handlers.append(urllib.request.HTTPSHandler(context=web_tools._ssl_ctx()))
        p = web_tools.proxy_for(url) or ""
    except Exception:
        p = ""
    handlers.append(urllib.request.ProxyHandler({"http": p, "https": p} if p else {}))
    return urllib.request.build_opener(*handlers)


def _get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with _opener(url).open(req, timeout=timeout) as r:
        return json.loads(r.read(3_000_000).decode("utf-8", "replace"))


def _syn_token(tid):
    """X 官方嵌入接口要的 token（和网页嵌入脚本一样的算法：id/1e15*π 转 36 进制）。"""
    x = (int(tid) / 1e15) * math.pi
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    ip, fp = int(x), x - int(x)
    s = ""
    while ip:
        ip, r = divmod(ip, 36)
        s = digits[r] + s
    s = (s or "0") + "."
    for _ in range(12):
        fp *= 36
        d = int(fp)
        s += digits[d]
        fp -= d
    return re.sub(r"(0+|\.)", "", s)


def fetch_tweet(tid, handle=""):
    """按推文编号取完整推文。依次试 fxtwitter、X 官方嵌入接口。拿不到返回 None。"""
    tid = str(tid or "").strip()
    if not tid.isdigit():
        return None
    tries = ["https://api.fxtwitter.com/%sstatus/%s" % ((handle + "/") if handle else "", tid),
             "https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=zh&token=%s" % (tid, _syn_token(tid))]
    for u in tries:
        try:
            d = _get_json(u)
            t = d.get("tweet") if isinstance(d.get("tweet"), dict) else d
            n = _node(t)
            if n and (n.get("text") or n.get("article")):
                return n
        except Exception as e:
            _log("取推文 %s 没成功（%s）：%s" % (tid, u.split("/")[2], str(e)[:80]))
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def resolve_tco(url):
    """t.co 短链 → 真实地址（只问 t.co 一下，不去下载目标网页）。失败原样返回。"""
    try:
        op = _opener(url)
        op.add_handler(_NoRedirect())
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "curl/8"})
        try:
            op.open(req, timeout=10)
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location") if e.headers else None
            if loc:
                return loc
    except Exception:
        pass
    return url


def fetch_article(url):
    """网页文章 → (标题, 正文)。读不到返回 ("", "")。"""
    try:
        import doc_import
        r = doc_import.extract_url(url)
        if r and r.get("ok") and (r.get("transcript") or "").strip():
            return (r.get("title") or "").strip(), r["transcript"].strip()
    except Exception as e:
        _log("读网页没成功：%s（%s）" % (url[:60], str(e)[:80]))
    return "", ""


# ════════════════ 3. 拆成两部分 ════════════════

def _who(n):
    if not n:
        return ""
    h = ("@" + n["handle"]) if n.get("handle") else ""
    nm = n.get("name") or ""
    return (h + ("（%s）" % nm if nm and nm.lower() != (n.get("handle") or "").lower() else "")) or nm or "原作者"


def _status_url(n):
    if n and n.get("id"):
        return "https://x.com/%s/status/%s" % (n.get("handle") or "i/web", n["id"])
    return ""


def _strip_urls(text, urls):
    for u in urls:
        text = text.replace(u, "")
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text)).strip()


def build(url, text="", snap=None, author="", deep=True, progress=None):
    """把一条推文拆开。返回 {"own": 博主原话, "kind": 原创/转发/引用, "refs": [{label, who, url, title, text, note}]}。
    deep=True 时联网补全（取完整推文、解短链、读网页文章）；False 只用手头的数据，马上返回。"""
    say = (lambda m: progress(m)) if progress else (lambda m: None)
    m = _STATUS.search(url or "")
    tid = m.group(2) if m else ""
    handle = m.group(1) if m and m.group(1) != "i/web" else ""
    node = _node(snap) if snap else None
    text = (text or "").strip()
    # 手头只有文字：从文字里认出「RT @谁: …」
    if not node:
        node = {"id": tid, "handle": handle, "name": author, "text": text, "links": [], "rt": None, "quote": None, "article": None}
        mrt = re.match(r"^RT @([A-Za-z0-9_]+):\s*(.*)$", text, re.S)
        if mrt:
            node["rt"] = {"id": "", "handle": mrt.group(1), "name": "", "text": mrt.group(2).strip(), "links": [],
                          "rt": None, "quote": None, "article": None}
            node["text"] = ""
    # 联网取完整推文（文字被截断、短链没展开、引用的帖子没带上时有用）
    if deep and tid:
        say("取完整推文…")
        full = fetch_tweet(tid, handle)
        if full:
            if node.get("rt") and full.get("handle") and full["handle"].lower() != (handle or "").lower():
                node["rt"] = full                     # 接口直接给了被转发的原帖
            elif full.get("rt") or full.get("quote") or len(full.get("text") or "") >= len(node.get("text") or ""):
                keep_rt = node.get("rt")
                node = full
                if keep_rt and not node.get("rt"):
                    node["rt"] = keep_rt
    rt = node.get("rt")
    if rt and deep and rt.get("text", "").endswith(("…", "...")) and rt.get("id"):
        f2 = fetch_tweet(rt["id"], rt.get("handle") or "")
        if f2:
            rt.update({k: v for k, v in f2.items() if v})

    # ── 博主原话 ──
    own = (node.get("text") or "").strip()
    if rt:
        kind = "转发"
        own = ""
    elif node.get("quote"):
        kind = "引用"
    else:
        kind = "原创"
    refs, seen = [], set()

    def add(label, n=None, link="", title="", body="", note=""):
        key = (n or {}).get("id") or link
        if key and key in seen:
            return
        if key:
            seen.add(key)
        media = n and label != "X 长文"                 # v153：帖子带的图片、视频
        refs.append({"label": label, "who": _who(n) if n else "", "url": link or _status_url(n),
                     "title": title, "text": (body or "").strip(), "note": note,
                     "photos": list(n.get("photos") or [])[:8] if media else [],
                     "video": (_status_url(n) + "/video/1") if media and n.get("video") and _status_url(n) else ""})

    def walk_links(n, owner_text):
        """一条推文里的链接：X 帖子 → 取帖子；X 长文 → 取长文；别的 → 读网页文章。"""
        urls = list(n.get("links") or [])
        urls += [u for u in _TCO.findall(owner_text or "") if u not in urls]
        for u in urls:
            if _MEDIA.search(u):
                continue
            if "t.co/" in u and deep:
                u2 = resolve_tco(u)
                if u2 != u:
                    n["text"] = (n.get("text") or "").replace(u, u2)
                    u = u2
            ms, ma = _STATUS.search(u), _ARTICLE.search(u)
            if ms and ms.group(2) in (node.get("id"), (rt or {}).get("id"), (node.get("quote") or {}).get("id")):
                continue
            if ma:
                if n.get("article"):
                    add("X 长文", n, link=u, title=n["article"].get("title"), body=n["article"].get("text"))
                else:
                    add("X 长文", None, link=u, note="没抓到长文内容，原文见链接")
                continue
            if ms:
                sub = fetch_tweet(ms.group(2), ms.group(1) if ms.group(1) != "i/web" else "") if deep else None
                if sub:
                    add("链接里的帖子", sub, body=sub.get("text") or (sub.get("article") or {}).get("text"))
                else:
                    add("链接里的帖子", None, link=u, note="没抓到帖子内容，原文见链接")
                continue
            if "t.co/" in u:
                add("链接", None, link=u, note="没打开这个短链接，原文见链接")
                continue
            if deep:
                say("读链接里的文章…")
                t, body = fetch_article(u)
                if body:
                    if len(body) > ART_MAX:
                        body = body[:ART_MAX] + "\n\n（后面还有 %d 字，太长没全放进来，原文见链接）" % (len(body) - ART_MAX)
                    add("网页文章", None, link=u, title=t, body=body)
                else:
                    add("网页文章", None, link=u, note="没读到正文（可能要登录或是视频 / 图片），原文见链接")
            else:
                add("网页文章", None, link=u, note="正在读链接里的文章…")

    if rt:
        add("转发的原帖", rt, body=rt.get("text"))
        if rt.get("article"):
            add("X 长文", rt, title=rt["article"].get("title"), body=rt["article"].get("text"))
        if rt.get("quote"):
            add("原帖引用的帖子", rt["quote"], body=rt["quote"].get("text"))
        walk_links(rt, rt.get("text"))
    q = node.get("quote")
    if q:
        add("引用的帖子", q, body=q.get("text"))
        walk_links(q, q.get("text"))
    if node.get("article"):
        add("X 长文", node, title=node["article"].get("title"), body=node["article"].get("text"))
    walk_links(node, node.get("text"))
    if not rt:
        own = (node.get("text") or "").strip()
        # 博主原话里只剩一个指向引用帖子 / 长文的链接，删掉（内容已经在「链接原文」里了）
        drop = [u for u in (node.get("links") or []) if _STATUS.search(u) or _ARTICLE.search(u) or _MEDIA.search(u)]
        own = _strip_urls(own, drop) or own
    return {"own": own, "kind": kind, "who": _who(node) or author, "rt_who": _who(rt) if rt else "", "refs": refs,
            "photos": [] if rt else list(node.get("photos") or [])[:8],
            "video": "" if rt or not node.get("video") or not _status_url(node) else _status_url(node) + "/video/1"}


_NUM = "①②③④⑤⑥⑦⑧⑨⑩"


def _media_md(photos, video):
    """v153：图片写成 ![图片N](地址)，视频写一行「🎬 视频：地址」（加工时会提取视频的文字）。"""
    out = []
    for i, u in enumerate(photos or []):
        out += ["![图片%d](%s)" % (i + 1, u), ""]
    if video:
        out += ["🎬 视频：" + video, ""]
    return out


def to_markdown(p):
    """拆好的结果 → 笔记里「完整文字稿」那一节的内容。"""
    lines = ["### 🗣 博主原话", ""]
    if p["kind"] == "转发":
        lines.append("（这条是转发：博主自己没说话，转发了 %s 的帖子，内容在下面「链接原文」里）" % (p.get("rt_who") or "别人"))
    else:
        lines.append(p["own"] or ("（只有图片 / 视频，没有文字）" if p.get("photos") or p.get("video") else "（只有链接，没有文字）"))
    lines += [""] + _media_md(p.get("photos"), p.get("video"))
    lines += ["### 🔗 链接原文", ""]
    if not p["refs"]:
        lines.append("（这条推文里没有转发、引用或链接）")
    for i, r in enumerate(p["refs"]):
        head = "#### %s %s" % (_NUM[i] if i < len(_NUM) else "%d." % (i + 1), r["label"])
        if r.get("who"):
            head += " · " + r["who"]
        if r.get("title"):
            head += " ·《%s》" % r["title"].strip()[:60]
        lines += [head, ""]
        if r.get("url"):
            lines += ["原文：" + r["url"], ""]
        if r.get("text"):
            lines += [r["text"], ""]
        elif r.get("note"):
            lines += ["（%s）" % r["note"], ""]
        lines += _media_md(r.get("photos"), r.get("video"))
    return "\n".join(lines).strip()


def is_tweet_note(md_text):
    head = (md_text or "")[:1500]
    return "平台：X" in head or bool(re.search(r"来源链接：https?://(?:www\.)?(?:x|twitter)\.com/", head))
