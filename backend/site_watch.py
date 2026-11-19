# -*- coding: utf-8 -*-
"""v78：把普通网站（官方博客、新闻页、活动页……）当「博主」来盯，不用 AI：

  · site_info(url)   打开网址，认出网站名字、简介、图标（当头像）、RSS 地址；
  · list_items(url)  列出最新的文章：有 RSS / Atom 就读 RSS；没有就从网页里挑「像文章」的链接；
  · icon_bytes(url)  下载网站图标（优先大图标：apple-touch-icon / 大尺寸 icon，最后才用 favicon）；
  · save_profile()   把名字、主页、简介、图标存进博主资料（和视频页共用），嗅探页显示头像用。

联网：有代理（和 AI 池同一个）先走代理，不行再直连。
"""
import re
import time
import hashlib
import email.utils
import urllib.parse
import html as _html
import xml.etree.ElementTree as ET

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0 Safari/537.36",
       "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}


def _cpf():
    import creator_profiles
    return creator_profiles


def _raw(url, timeout=20, accept=None):
    """下载网址，返回 (字节, 最终网址)。有代理先走代理，不行再直连。"""
    P = _cpf()
    hdr = dict(_UA)
    if accept:
        hdr["Accept"] = accept
    proxy = ""
    try:
        proxy = P._proxy() or ""
    except Exception:
        pass
    errs = []
    for px in ([proxy, ""] if proxy else [""]):
        try:
            return P._http(url, headers=hdr, proxy=px, timeout=timeout)
        except Exception as e:
            errs.append(str(e).split("\n")[0][:80])
    raise RuntimeError("打不开 %s（%s）" % (url, "；".join(errs)))


def _attr(tag, name):
    m = re.search(r"\b%s\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]+))" % name, tag, re.I)
    if not m:
        return ""
    v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else (m.group(4) or ""))
    return _html.unescape(v).strip()


def _meta(h, *names):
    for tag in re.findall(r"<meta\b[^>]*>", h, re.I):
        key = (_attr(tag, "property") or _attr(tag, "name")).lower()
        if key in names:
            v = _attr(tag, "content")
            if v:
                return v
    return ""


def _clean_name(t, host):
    t = re.sub(r"\s+", " ", _html.unescape(t or "")).strip()
    if not t:
        return host
    parts = [p.strip() for p in re.split(r"\s+[|\-–—·:：]\s+", t) if p.strip()]
    return (parts[0] if parts else t)[:60]


def _icons(h, base):
    cands = []
    for tag in re.findall(r"<link\b[^>]*>", h, re.I):
        rel = _attr(tag, "rel").lower()
        if "icon" not in rel or "mask" in rel:
            continue
        href = _attr(tag, "href")
        if not href or href.startswith("data:"):
            continue
        m = re.search(r"(\d+)x(\d+)", _attr(tag, "sizes").lower())
        svg = "svg" in (_attr(tag, "type").lower() + href.lower())
        size = int(m.group(1)) if m else (180 if "apple-touch" in rel else (256 if svg else 32))
        cands.append((size + (1000 if "apple-touch" in rel else 0), urllib.parse.urljoin(base, href)))
    cands.sort(key=lambda x: -x[0])
    out = [u for _, u in cands] + [urllib.parse.urljoin(base, "/favicon.ico")]
    return list(dict.fromkeys(out))


def _feeds(h, base):
    out = []
    for tag in re.findall(r"<link\b[^>]*>", h, re.I):
        if "alternate" in _attr(tag, "rel").lower() and re.search(r"(rss|atom)\+xml", _attr(tag, "type"), re.I):
            href = _attr(tag, "href")
            if href:
                out.append(urllib.parse.urljoin(base, href))
    return list(dict.fromkeys(out))


def site_info(url):
    """打开网址，返回 {name, home, desc, icons, feeds, html}。打不开抛 RuntimeError（人话）。"""
    P = _cpf()
    b, final = _raw(url)
    h = P._text(b)
    home = final or url
    host = urllib.parse.urlparse(home).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    title = (re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S) or [None, ""])[1]
    name = _meta(h, "og:site_name") or _clean_name(_meta(h, "og:title") or title, host)
    return {"name": name.strip()[:60] or host, "home": home,
            "desc": (_meta(h, "og:description", "description", "twitter:description") or "")[:300],
            "icons": _icons(h, home), "feeds": _feeds(h, home), "html": h}


# ─────────────────────────── 最新文章 ───────────────────────────
def _when(s):
    s = (s or "").strip()
    if not s:
        return ""
    try:
        return email.utils.parsedate_to_datetime(s).strftime("%Y%m%d")
    except Exception:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return (m.group(1) + m.group(2) + m.group(3)) if m else ""


def _parse_feed(b):
    try:
        root = ET.fromstring(b)
    except Exception:
        return []
    tag = lambda e: (e.tag.split("}")[-1] if isinstance(e.tag, str) else "").lower()
    items = []
    for e in root.iter():
        if tag(e) not in ("item", "entry"):
            continue
        title = link = when = ""
        for c in e:
            ct = tag(c)
            if ct == "title":
                title = "".join(c.itertext()).strip()
            elif ct == "link":
                href = c.get("href")
                if href:
                    if (c.get("rel") or "alternate") == "alternate" or not link:
                        link = href
                elif (c.text or "").strip():
                    link = c.text.strip()
            elif ct in ("pubdate", "published", "updated", "date") and not when:
                when = _when("".join(c.itertext()))
            elif ct in ("guid", "id") and not link and (c.text or "").strip().startswith("http"):
                link = c.text.strip()
        title = _html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        if link and title:
            items.append({"title": title[:200], "url": link, "when": when})
    return items


_SKIP = re.compile(r"/(about|privacy|terms|legal|login|log-in|signin|sign-in|signup|sign-up|register|contact|careers|jobs|"
                   r"search|tags?|category|categories|topics?|authors?|page/\d+|feed|rss|subscribe|newsletter|cookies?|"
                   r"help|support|faq|sitemap|press-kit|account|cart|shop)(/|$)", re.I)


def _links(h, base, limit):
    """没有 RSS 时：从网页里挑「像文章」的链接（同一个网站、链接文字够长、不是导航 / 登录 / 关于我们）。"""
    bp = urllib.parse.urlparse(base)
    host = bp.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    bpath = bp.path.rstrip("/")
    seen, out = {}, []
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", h, re.I | re.S):
        href = _attr(m.group(1), "href")
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        u = urllib.parse.urljoin(base, href).split("#")[0]
        pu = urllib.parse.urlparse(u)
        if pu.scheme not in ("http", "https"):
            continue
        h2 = pu.netloc.lower()
        h2 = h2[4:] if h2.startswith("www.") else h2
        if not (h2 == host or h2.endswith("." + host) or host.endswith("." + h2)):
            continue
        path = pu.path.rstrip("/")
        if not path or path == bpath or _SKIP.search(path + "/"):
            continue
        if re.search(r"\.(jpe?g|png|gif|svg|webp|css|js|zip|mp4|mp3|ico)$", path, re.I):
            continue
        text = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if len(text) < 8:
            alt = _attr(m.group(1), "aria-label") or _attr(m.group(1), "title")
            text = alt if len(alt) >= 8 else ""
        if not text:
            continue
        d = re.search(r"(20\d{2})[/-]?(0[1-9]|1[0-2])[/-]?(0[1-9]|[12]\d|3[01])", path)
        if u in seen:
            o = out[seen[u]]
            if len(o["title"]) < len(text) <= 200:
                o["title"] = text
            continue
        seen[u] = len(out)
        out.append({"title": text[:200], "url": u, "when": (d.group(1) + d.group(2) + d.group(3)) if d else "",
                    "_depth": len([x for x in path.split("/") if x])})
    base_depth = len([x for x in bpath.split("/") if x])
    deep = [x for x in out if x["_depth"] >= max(2, base_depth + 1) or x["when"]]
    pick = deep if len(deep) >= 5 else out
    for x in pick:
        x.pop("_depth", None)
    return pick[:limit] if limit else pick


def _finish(items, limit):
    out = []
    for it in (items[:limit] if limit else items):
        out.append({"vid": hashlib.sha1(it["url"].encode("utf-8")).hexdigest()[:16], "url": it["url"],
                    "title": it["title"], "when": it.get("when") or ""})
    return out


def list_items(url, limit=15):
    """返回 {name, videos:[{vid,url,title,when}], total, via}，最新的在前（按网站自己的顺序）。"""
    info = site_info(url)
    feeds, guessed = info["feeds"], False
    if not feeds:
        p = urllib.parse.urlparse(info["home"])
        root = "%s://%s" % (p.scheme, p.netloc)
        path = p.path.rstrip("/")
        feeds = list(dict.fromkeys([root + path + "/rss/", root + path + "/feed/", root + "/rss.xml",
                                    root + "/feed.xml", root + "/atom.xml"]))[:4]
        guessed = True
    for f in feeds[:4]:
        try:
            b, _ = _raw(f, timeout=8 if guessed else 15,
                        accept="application/rss+xml, application/atom+xml, application/xml, text/xml, */*")
            items = _parse_feed(b)
            if items:
                return {"name": info["name"], "videos": _finish(items, limit), "total": len(items), "via": "RSS"}
        except Exception:
            continue
    items = _links(info["html"], info["home"], 0)
    if not items:
        raise RuntimeError("这个网页里没找到文章列表（也没有 RSS）。可以换成它的「新闻 / 博客」页面网址再试")
    return {"name": info["name"], "videos": _finish(items, limit), "total": len(items), "via": "网页"}


# ─────────────────────────── 图标 = 头像 ───────────────────────────
def icon_bytes(url, info=None):
    """下载网站图标。返回 (字节, 图标网址)；没有能用的返回 (b"", "")。"""
    P = _cpf()
    info = info or site_info(url)
    host = urllib.parse.urlparse(info["home"]).netloc
    cands = info["icons"][:6] + ["https://www.google.com/s2/favicons?domain=%s&sz=128" % host,
                                 "https://icons.duckduckgo.com/ip3/%s.ico" % host]
    for u in cands:
        try:
            b, _ = _raw(u, timeout=12, accept="image/avif,image/webp,image/*,*/*;q=0.8")
            if P._img_ext(b) and len(b) > 100:
                return b, u
        except Exception:
            continue
    return b"", ""


def save_profile(key, info, data=None):
    """把网站的名字 / 主页 / 简介 / 图标存进博主资料（自动取的，不算手动上传）。"""
    P = _cpf()
    fn = P._store_avatar(key, data) if data else ""
    with P._lock:
        st = P._load()
        p = dict(st.get(key) or {"key": key})
        p.update({"platform": "web", "home": info["home"], "name": info.get("name") or p.get("name") or key,
                  "updated": int(time.time())})
        p.setdefault("url", info["home"])
        if info.get("desc"):
            p["signature"] = info["desc"][:300]
        if fn:
            p["avatar_file"] = fn
        p.pop("error", None)
        st[key] = p
        P._save(st)
    return True
