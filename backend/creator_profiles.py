"""超能小助 · 博主主页资料（v58 新增）

视频笔记「图标」视图里，每个博主 / 文件夹显示成一个头像。给它绑一个主页链接
（抖音 / B站 / YouTube / 其它），这里负责：认出平台 → 取昵称、头像、粉丝数、简介 →
把头像存到本地（memory/creator_avatars/），以后不联网也能显示。

取资料的办法（每个平台都有兜底，前一个不行就试下一个）：
  · 抖音：主页链接 / 短链 → sec_uid（复用 douyin_resolver）→ 用户信息接口 → 主页 HTML 里的数据
  · B站：space.bilibili.com/<mid>（b23.tv 短链先跳转）→ 名片接口 x/web-interface/card
  · YouTube：yt-dlp 读频道信息（头像、订阅数、简介），走「设置」里的代理
  · 其它网站：网页里的 og:image / og:title
都不行时，用户还可以手动上传一张图片当头像（set_avatar_data）。
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
MEM = BASE / "memory"
STORE = MEM / "creator_profiles.json"
AV_DIR = MEM / "creator_avatars"
_lock = threading.Lock()

UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
PLATFORM_LABEL = {"douyin": "抖音", "bilibili": "B站", "youtube": "YouTube", "kuaishou": "快手",
                  "xiaohongshu": "小红书", "tiktok": "TikTok", "x": "X", "weibo": "微博", "web": "网站"}


# ════════════════════ 存取 ════════════════════

def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d):
    MEM.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE)


def _avatar_file(p):
    f = (p or {}).get("avatar_file") or ""
    if not f:
        return None
    fp = AV_DIR / f
    return fp if fp.exists() else None


def _public(p):
    d = {k: v for k, v in (p or {}).items() if k != "avatar_file"}
    fp = _avatar_file(p)
    d["has_avatar"] = bool(fp)
    d["v"] = int(fp.stat().st_mtime) if fp else 0
    d["platform_label"] = PLATFORM_LABEL.get(d.get("platform") or "", "")
    return d


def list_profiles():
    with _lock:
        return {k: _public(v) for k, v in _load().items()}


def get_avatar(key):
    """返回 (图片字节, content-type) 或 (None, None)。"""
    with _lock:
        p = _load().get(key)
    fp = _avatar_file(p)
    if not fp:
        return None, None
    ext = fp.suffix.lower()
    ctype = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
    return fp.read_bytes(), ctype


# ════════════════════ 网络小工具 ════════════════════

def _proxy():
    try:
        import creator_watch
        return creator_watch._proxy() or ""
    except Exception:
        return ""


def _opener(proxy=""):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def _http(url, headers=None, proxy="", timeout=15, limit=6 * 1024 * 1024):
    """GET，返回 (bytes, 最终地址)。优先用 curl_cffi（像真浏览器，少被拦），没有再用 urllib。"""
    h = {"User-Agent": UA_PC, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    h.update(headers or {})
    try:
        from curl_cffi import requests as creq
        kw = {"headers": h, "timeout": timeout, "impersonate": "chrome", "allow_redirects": True}
        if proxy:
            kw["proxies"] = {"http": proxy, "https": proxy}
        r = creq.get(url, **kw)
        if r.status_code >= 400:
            raise RuntimeError("HTTP %s" % r.status_code)
        return r.content[:limit], str(r.url)
    except ImportError:
        pass
    req = urllib.request.Request(url, headers=h)
    with _opener(proxy).open(req, timeout=timeout) as r:
        return r.read(limit), r.geturl()


def _text(b):
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", "replace")


def _og(html, prop):
    for pat in (r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)["\']' % re.escape(prop),
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(prop)):
        m = re.search(pat, html, re.I)
        if m:
            import html as _h
            return _h.unescape(m.group(1)).strip()
    return ""


def _num(v):
    try:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip().replace(",", "")
        m = re.match(r"([\d.]+)\s*([万亿KkMm]?)", s)
        if not m:
            return None
        n = float(m.group(1))
        mul = {"万": 1e4, "亿": 1e8, "K": 1e3, "k": 1e3, "M": 1e6, "m": 1e6}.get(m.group(2), 1)
        return int(n * mul)
    except Exception:
        return None


def detect_platform(url):
    u = (url or "").lower()
    if "douyin.com" in u or "iesdouyin" in u:
        return "douyin"
    if "bilibili.com" in u or "b23.tv" in u:
        return "bilibili"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "kuaishou.com" in u or "gifshow" in u:
        return "kuaishou"
    if "xiaohongshu.com" in u or "xhslink" in u:
        return "xiaohongshu"
    if "tiktok.com" in u:
        return "tiktok"
    if "x.com/" in u or "twitter.com/" in u:
        return "x"
    if "weibo.com" in u or "weibo.cn" in u:
        return "weibo"
    return "web"


def _find_url(text):
    m = re.search(r"https?://[^\s，。！？、）)\]】\"']+", text or "")
    return m.group(0).rstrip(".,，。") if m else (text or "").strip()


# ════════════════════ 各平台 ════════════════════

def _resolve_douyin(url):
    import douyin_resolver as dr
    sec, html = dr._resolve_sec_uid(url)
    if not sec:
        raise RuntimeError("没认出抖音主页（链接里没有用户 ID）。请打开博主主页 → 分享 → 复制链接")
    home = "https://www.douyin.com/user/%s" % sec
    out = {"home": home, "uid": sec}
    s = dr._session()
    # ① 用户信息接口（不需要签名）
    for api in ("https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid=%s" % sec,
                "https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid=%s&reflow_source=reflow_page" % sec):
        data = dr._api_get_json(s, api, referer="https://www.iesdouyin.com/", user_agent=UA_M, timeout=10) or {}
        ui = data.get("user_info") or {}
        if ui.get("nickname"):
            av = ((ui.get("avatar_larger") or ui.get("avatar_medium") or ui.get("avatar_thumb") or {})
                  .get("url_list") or [""])[0]
            out.update(name=ui.get("nickname"), avatar=av, followers=_num(ui.get("follower_count")),
                       signature=(ui.get("signature") or "").strip(), works=_num(ui.get("aweme_count")),
                       handle=ui.get("unique_id") or ui.get("short_id") or "")
            return out
    # ② 主页 HTML 里的数据
    if not html:
        try:
            b, _u = _http(home, headers={"Referer": "https://www.douyin.com/"}, timeout=15)
            html = _text(b)
        except Exception:
            html = ""
    if html:
        t = urllib.parse.unquote(html) if "%22" in html else html
        t = t.replace('\\"', '"').replace("\\u002F", "/")
        name = (re.search(r'"nickname"\s*:\s*"([^"]{1,60})"', t) or [None, ""])[1]
        av = ""
        for key in ("avatarLarger", "avatar_larger", "avatarMedium", "avatarUrl", "avatarThumb", "avatar_thumb"):
            m = re.search(r'"%s"\s*:\s*(?:\{[^}]*?"url_list"\s*:\s*\[\s*)?"(https?:[^"]+)"' % key, t)
            if m:
                av = m.group(1)
                break
        fans = re.search(r'"(?:followerCount|follower_count|mplatformFollowersCount)"\s*:\s*(\d+)', t)
        sign = re.search(r'"(?:signature|desc)"\s*:\s*"([^"]{0,200})"', t)
        if name or av:
            out.update(name=name, avatar=av or _og(html, "og:image"), followers=_num(fans.group(1)) if fans else None,
                       signature=(sign.group(1) if sign else "").strip())
            return out
        title = _og(html, "og:title") or ""
        img = _og(html, "og:image")
        if title or img:
            out.update(name=re.sub(r"的抖音.*$", "", title), avatar=img)
            return out
    raise RuntimeError("抖音没返回博主资料（可能被风控了）。可以稍后点「刷新资料」再试，或者手动上传一张头像")


def _resolve_bilibili(url):
    u = url
    if "b23.tv" in u:
        try:
            _b, u = _http(u, timeout=12)
        except Exception:
            pass
    m = re.search(r"space\.bilibili\.com/(\d+)", u) or re.search(r"[?&](?:mid|vmid)=(\d+)", u)
    if not m:
        raise RuntimeError("没认出 B站主页（需要 space.bilibili.com/数字 这样的链接）")
    mid = m.group(1)
    home = "https://space.bilibili.com/%s" % mid
    out = {"home": home, "uid": mid}
    try:
        b, _u = _http("https://api.bilibili.com/x/web-interface/card?mid=%s&photo=false" % mid,
                      headers={"Referer": home, "Accept": "application/json"}, timeout=12)
        j = json.loads(_text(b))
        if j.get("code") == 0:
            d = j.get("data") or {}
            card = d.get("card") or {}
            out.update(name=card.get("name") or "", avatar=card.get("face") or "",
                       followers=_num(d.get("follower") if d.get("follower") is not None else card.get("fans")),
                       signature=(card.get("sign") or "").strip(), works=_num(d.get("archive_count")))
            if out.get("name"):
                return out
    except Exception:
        pass
    b, _u = _http(home, headers={"Referer": "https://www.bilibili.com/"}, timeout=12)
    html = _text(b)
    title = _og(html, "og:title") or (re.search(r"<title>([^<]+)</title>", html) or [None, ""])[1]
    out.update(name=re.sub(r"的个人空间.*$", "", title or "").strip(), avatar=_og(html, "og:image"))
    if out.get("name") or out.get("avatar"):
        return out
    raise RuntimeError("B站没返回博主资料，稍后再试，或者手动上传一张头像")


def _resolve_youtube(url):
    proxy = _proxy()
    home = url.strip().split("?")[0].rstrip("/")
    home = re.sub(r"/(videos|streams|shorts|featured|about)$", "", home)
    out = {"home": home}
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True,
                "playlistend": 1, "socket_timeout": 20}
        if proxy:
            opts["proxy"] = proxy
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(home + "/videos" if "/@" in home or "/channel/" in home else home,
                                    download=False) or {}
        thumbs = info.get("thumbnails") or []
        av = ""
        for t in thumbs:
            if "avatar" in str(t.get("id", "")):
                av = t.get("url") or ""
                break
        out.update(name=info.get("channel") or info.get("uploader") or info.get("title") or "",
                   avatar=av, followers=_num(info.get("channel_follower_count")),
                   signature=(info.get("description") or "").strip()[:300],
                   uid=info.get("channel_id") or "")
        if info.get("channel_url"):
            out["home"] = info["channel_url"]
        if out.get("name") and out.get("avatar"):
            return out
    except Exception as e:
        out["_err"] = str(e).split("\n")[0][:120]
    try:
        b, _u = _http(home, proxy=proxy, timeout=20)
        html = _text(b)
        out["name"] = out.get("name") or _og(html, "og:title")
        out["avatar"] = out.get("avatar") or _og(html, "og:image")
        out["signature"] = out.get("signature") or _og(html, "og:description")
        if out.get("name") or out.get("avatar"):
            return out
    except Exception as e:
        out["_err"] = out.get("_err") or str(e)[:120]
    raise RuntimeError("YouTube 没连上（%s）。看看「设置 → 联网与代理」里的代理是否可用" % (out.get("_err") or "无返回"))


def _resolve_generic(url):
    proxy = _proxy() if detect_platform(url) in ("tiktok", "x") else ""
    try:
        b, final = _http(url, proxy=proxy, timeout=20)
    except Exception as e:
        raise RuntimeError("打不开这个主页（%s）。检查一下链接，或者手动上传一张头像" % str(e).split("\n")[0][:80])
    html = _text(b)
    name = _og(html, "og:title") or (re.search(r"<title>([^<]+)</title>", html, re.I) or [None, ""])[1]
    av = _og(html, "og:image") or _og(html, "twitter:image")
    if not (name or av):
        raise RuntimeError("这个网页里没找到头像和名字，可以手动上传一张头像")
    return {"home": final or url, "name": (name or "").strip()[:60], "avatar": av,
            "signature": _og(html, "og:description")[:300]}


# ════════════════════ 头像 ════════════════════

def _img_ext(b):
    if b[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return ".webp"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return ""


def _store_avatar(key, data):
    ext = _img_ext(data)
    if not ext:
        raise RuntimeError("这不是一张能用的图片（支持 jpg / png / webp / gif）")
    AV_DIR.mkdir(parents=True, exist_ok=True)
    stem = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    for old in AV_DIR.glob(stem + ".*"):
        try:
            old.unlink()
        except Exception:
            pass
    fn = stem + ext
    (AV_DIR / fn).write_bytes(data)
    return fn


def _download_avatar(url, platform, referer=""):
    if not url:
        return b""
    if url.startswith("//"):
        url = "https:" + url
    proxy = _proxy() if platform in ("youtube", "tiktok", "x") else ""
    hdr = {"Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}
    if referer:
        hdr["Referer"] = referer
    data, _u = _http(url, headers=hdr, proxy=proxy, timeout=20)
    return data if _img_ext(data) else b""


# ════════════════════ 对外 ════════════════════

def bind(key, url):
    """给博主 / 文件夹 key 绑定主页链接，取资料并存头像。返回 (ok, 资料或错误说明)。"""
    key = (key or "").strip()
    url = _find_url(url)
    if not key:
        return False, "缺少博主名"
    if not re.match(r"https?://", url or ""):
        return False, "请粘贴以 http 开头的主页链接"
    plat = detect_platform(url)
    fn = {"douyin": _resolve_douyin, "bilibili": _resolve_bilibili, "youtube": _resolve_youtube}.get(plat, _resolve_generic)
    with _lock:
        store = _load()
        prof = dict(store.get(key) or {})
    prof.update({"key": key, "url": url, "platform": plat, "updated": int(time.time())})
    try:
        info = fn(url)
    except Exception as e:
        prof["error"] = str(e)[:200]
        with _lock:
            store = _load()
            store[key] = prof
            _save(store)
        return False, prof["error"]
    info.pop("_err", None)
    av_url = info.pop("avatar", "") or ""
    for k, v in info.items():
        if v not in (None, ""):
            prof[k] = v
    prof["avatar_src"] = av_url
    prof.pop("error", None)
    msg_extra = ""
    if av_url:
        try:
            data = _download_avatar(av_url, plat, referer=prof.get("home") or "")
            if data:
                prof["avatar_file"] = _store_avatar(key, data)
            else:
                msg_extra = "（头像图片没下载下来，可以手动上传）"
        except Exception as e:
            msg_extra = "（头像下载失败：%s，可以手动上传）" % str(e)[:60]
    else:
        msg_extra = "（没找到头像，可以手动上传）"
    with _lock:
        store = _load()
        store[key] = prof
        _save(store)
    pub = _public(prof)
    pub["note"] = msg_extra
    return True, pub


def refresh(key):
    with _lock:
        p = _load().get(key) or {}
    if not p.get("url"):
        return False, "这个博主还没绑定主页链接"
    return bind(key, p["url"])


def set_avatar_data(key, data_url):
    """手动上传头像：data_url 形如 data:image/png;base64,xxxx。"""
    key = (key or "").strip()
    try:
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        data = base64.b64decode(b64)
    except Exception:
        return False, "图片数据不对"
    if len(data) > 8 * 1024 * 1024:
        return False, "图片太大了（超过 8MB）"
    try:
        fn = _store_avatar(key, data)
    except Exception as e:
        return False, str(e)
    with _lock:
        store = _load()
        p = dict(store.get(key) or {"key": key})
        p["avatar_file"] = fn
        p["avatar_manual"] = True
        p["updated"] = int(time.time())
        store[key] = p
        _save(store)
    return True, _public(p)


def remove(key):
    with _lock:
        store = _load()
        p = store.pop(key, None)
        _save(store)
    fp = _avatar_file(p)
    if fp:
        try:
            fp.unlink()
        except Exception:
            pass
    return True, "已解除绑定"
