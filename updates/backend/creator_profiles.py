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

v59：还能「根据视频找博主主页」（find_home_from_video）——提取视频时不用自己去找主页链接：
  · 抖音：视频详情里本来就带作者的 sec_uid、昵称、头像 → www.douyin.com/user/<sec_uid>
  · B站：视频接口 x/web-interface/view 里的 UP 主 mid → space.bilibili.com/<mid>
  · YouTube 等：yt-dlp 读视频信息里的 channel_url / uploader_url
主页接口被风控取不到资料时，直接用视频里带的作者昵称和头像，博主板块照样能建起来。
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
    ctype = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif", ".ico": "image/x-icon",
             ".svg": "image/svg+xml"}.get(ext, "image/jpeg")
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
    if b[:4] == b"\x00\x00\x01\x00":            # v78：网站图标常见的 .ico
        return ".ico"
    if b"<svg" in b[:600].lower():                   # v78：网站图标也可能是 svg
        return ".svg"
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

def _resolve_x(url):
    raise RuntimeError("X（推特）的主页要登录才能看，取不到头像，可以手动上传一张")


_RESOLVERS = {"douyin": _resolve_douyin, "bilibili": _resolve_bilibili, "youtube": _resolve_youtube,
              "x": _resolve_x}


def _fetch(url):
    """认平台 + 取资料。返回 (平台, 资料)；取不到抛异常。"""
    plat = detect_platform(url)
    return plat, _RESOLVERS.get(plat, _resolve_generic)(url)


def _store(key, url, plat, info, hint=None, auto=False):
    """把取到的资料（和头像）存到 key 名下。hint = 视频里带的作者信息，用来补资料里缺的项。"""
    hint = dict(hint or {})
    info = dict(info or {})
    info.pop("_err", None)
    for k in ("name", "avatar", "uid", "followers", "works", "signature", "handle"):
        if info.get(k) in (None, "") and hint.get(k) not in (None, ""):
            info[k] = hint[k]
    with _lock:
        prof = dict(_load().get(key) or {})
    for k in ("error", "no_auto", "auto_fail_at", "auto_skip"):
        prof.pop(k, None)
    prof.update({"key": key, "url": url, "platform": plat, "updated": int(time.time())})
    if auto:
        prof["auto"] = True
        if hint.get("video"):
            prof["source_video"] = hint["video"]
        if hint.get("via"):
            prof["found_via"] = hint["via"]
    else:
        prof.pop("auto", None)
    av_url = info.pop("avatar", "") or ""
    for k, v in info.items():
        if v not in (None, ""):
            prof[k] = v
    prof["avatar_src"] = av_url
    msg_extra = ""
    keep_manual = auto and prof.get("avatar_manual") and _avatar_file(prof)
    if keep_manual:
        pass                                   # 自动找到的不覆盖用户自己上传的头像
    elif av_url:
        try:
            data = _download_avatar(av_url, plat, referer=prof.get("home") or "")
            if data:
                prof["avatar_file"] = _store_avatar(key, data)
                prof.pop("avatar_manual", None)
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
    return pub


def bind(key, url, hint=None, auto=False):
    """给博主 / 文件夹 key 绑定主页链接，取资料并存头像。返回 (ok, 资料或错误说明)。
    hint：从视频里拿到的作者信息（昵称、头像…）。主页接口被风控取不到时就用它，不至于失败。"""
    key = (key or "").strip()
    url = _find_url(url)
    if not key:
        return False, "缺少博主名"
    if not re.match(r"https?://", url or ""):
        return False, "请粘贴以 http 开头的主页链接"
    plat = detect_platform(url)
    if auto and plat == "douyin" and hint and hint.get("name") and hint.get("avatar"):
        # 视频里已经带了作者的昵称和头像：不再去请求抖音主页接口（改规则后多半也请求不到，还慢）
        return True, _store(key, url, plat, {"home": url}, hint=hint, auto=auto)
    try:
        plat, info = _fetch(url)
    except Exception as e:
        if hint and (hint.get("name") or hint.get("avatar")):
            info = {"home": hint.get("home") or url}
        else:
            with _lock:
                store = _load()
                prof = dict(store.get(key) or {})
                prof.update({"key": key, "url": url, "platform": plat, "updated": int(time.time()),
                             "error": str(e)[:200]})
                store[key] = prof
                _save(store)
            return False, prof["error"]
    return True, _store(key, url, plat, info, hint=hint, auto=auto)


def bind_for_note(key, url):
    """提取卡片里填的「博主主页」：绑到这条笔记的作者名下。笔记没有作者（多见于本地文件）时，
    用主页上的昵称当作者名。返回 (ok, 资料或错误说明, 实际用的博主名)。"""
    key = (key or "").strip()
    if key:
        ok, r = bind(key, url)
        return ok, r, key
    url = _find_url(url)
    if not re.match(r"https?://", url or ""):
        return False, "博主主页要以 http 开头", ""
    try:
        plat, info = _fetch(url)
    except Exception as e:
        return False, str(e)[:200], ""
    name = re.sub(r"\s+", " ", (info.get("name") or "")).strip()[:40]
    if not name:
        return False, "主页上没取到博主昵称", ""
    return True, _store(name, url, plat, info), name


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
    """解除绑定：删掉主页和头像。留一个「别再自动找」的记号——用户自己解除的，提取新视频时不再自动绑回去
    （以后手动绑定或点「自动找主页」会清掉这个记号）。"""
    with _lock:
        store = _load()
        p = store.pop(key, None)
        if key:
            store[key] = {"key": key, "no_auto": True, "updated": int(time.time())}
        _save(store)
    fp = _avatar_file(p)
    if fp:
        try:
            fp.unlink()
        except Exception:
            pass
    return True, "已解除绑定"


# ════════════════════ v59：根据视频链接找博主主页 ════════════════════

def list_raw():
    with _lock:
        return {k: dict(v) for k, v in _load().items()}


def rename_key(old, new):
    """v63：博主改名了——把 old 名下的资料挪到 new 名下（new 下已经有主页的，就保留 new 的那份）。"""
    old, new = (old or "").strip(), (new or "").strip()
    if not old or not new or old == new:
        return False
    with _lock:
        store = _load()
        p = store.pop(old, None)
        if p is None:
            return False
        q = store.get(new) or {}
        if not (q.get("url") or q.get("avatar_file")):
            if p.get("url") or p.get("avatar_file"):
                p["key"] = new
                p["renamed_from"] = old
                store[new] = p
            elif p.get("no_auto") and not q:
                # v64：old 只有「用户解除过绑定」的记号 → 新名字也别自动绑
                store[new] = {"key": new, "no_auto": True, "renamed_from": old, "updated": int(time.time())}
            # v64：old 只有「自动找没成功」之类的记号（没主页也没头像）→ 不挪过去，
            # 免得 new 的资料卡上显示 old 的失败原因（合并记录里留着原样，撤销时会放回去）
        _save(store)
    return True


def restore_after_unmerge(src, dst, src_before, dst_before, moved):
    """v64：撤销合并——src 的资料放回去；dst 那份如果是合并时从 src 挪过来的，恢复成 dst 原来的样子。
    （合并后 dst 又重新绑定 / 刷新过的，就保留 dst 现在的。）"""
    src, dst = (src or "").strip(), (dst or "").strip()
    if not src or not dst:
        return
    with _lock:
        store = _load()
        cur = store.get(dst) or {}
        if moved and cur.get("renamed_from") == src:
            if dst_before:
                store[dst] = dict(dst_before)
            else:
                store.pop(dst, None)
        if src_before and src not in store:
            p = dict(src_before)
            p["key"] = src
            store[src] = p
        _save(store)


def profile_state(key):
    """这个博主现在存着的资料（原样，没有返回空字典）。"""
    with _lock:
        return dict(_load().get((key or "").strip()) or {})


def should_auto_bind(key):
    """这个博主要不要自动找主页：没绑过主页、用户没手动解除过、一天内没自动找失败过，才找。"""
    with _lock:
        p = _load().get((key or "").strip()) or {}
    if p.get("url") or p.get("no_auto"):
        return False
    if p.get("auto_fail_at") and time.time() - p["auto_fail_at"] < 86400:
        return False
    return True


def mark_skip(key, why):
    """v60：一键识别时这个没法自动找（比如按主题建的文件夹、全是本地导入的）——记下来，
    下次一键识别不再把它算进「还没主页」。点它自己的「自动找主页」按钮仍然可以试。"""
    with _lock:
        store = _load()
        p = dict(store.get(key) or {"key": key})
        if p.get("url"):
            return
        p["auto_skip"] = (why or "")[:120]
        store[key] = p
        _save(store)


def _mark_auto_fail(key, msg):
    with _lock:
        store = _load()
        p = dict(store.get(key) or {"key": key})
        p["auto_fail_at"] = int(time.time())
        p["error"] = ("自动找主页没成功：%s" % msg)[:200]
        store[key] = p
        _save(store)


def _bili_owner(url):
    """B站视频 → UP 主（mid、昵称、头像）。"""
    u = url
    if "b23.tv" in u:
        try:
            _b, u = _http(u, timeout=12)
        except Exception:
            pass
    m = re.search(r"(BV[0-9A-Za-z]{10})", u)
    q = ("bvid=%s" % m.group(1)) if m else ""
    if not q:
        m = re.search(r"/av(\d+)", u, re.I)
        q = ("aid=%s" % m.group(1)) if m else ""
    if not q:
        raise RuntimeError("没认出 B站视频编号")
    b, _u = _http("https://api.bilibili.com/x/web-interface/view?" + q,
                  headers={"Referer": "https://www.bilibili.com/", "Accept": "application/json"}, timeout=12)
    j = json.loads(_text(b))
    ow = ((j.get("data") or {}).get("owner") or {}) if j.get("code") == 0 else {}
    if not ow.get("mid"):
        raise RuntimeError("B站没返回 UP 主信息（%s）" % (j.get("message") or j.get("code")))
    return {"platform": "bilibili", "home": "https://space.bilibili.com/%s" % ow["mid"],
            "uid": str(ow["mid"]), "name": ow.get("name") or "", "avatar": ow.get("face") or ""}


def _ytdlp_uploader(url, proxy=""):
    """yt-dlp 只读视频信息（不下载），拿频道 / 作者主页。"""
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
            "socket_timeout": 20}
    if proxy:
        opts["proxy"] = proxy
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False, process=False) or {}
    return {"home": info.get("channel_url") or info.get("uploader_url") or "",
            "uid": info.get("channel_id") or info.get("uploader_id") or "",
            "name": info.get("channel") or info.get("uploader") or ""}


def find_home_from_video(url, expect=""):
    """根据一条视频链接找博主主页。返回 {platform, home, uid, name, avatar, via, …}；找不到抛 RuntimeError（人话）。
    expect：笔记里记的博主名（抖音从页面上认作者链接时用来核对）。"""
    url = _find_url(url)
    plat = detect_platform(url)
    if plat == "douyin":
        import douyin_resolver as dr
        a, how = dr.find_author(url, expect=expect)
        sec, uid = a.get("sec_uid") or "", a.get("uid") or ""
        if not (sec or uid):
            raise RuntimeError("抖音没找到作者：" + how)
        out = {"platform": "douyin", "via": how,
               "home": ("https://www.douyin.com/user/%s" % sec) if sec
               else ("https://www.iesdouyin.com/share/user/%s" % uid),
               "uid": sec or uid, "name": a.get("nickname") or expect or "",
               "avatar": a.get("avatar") or "", "signature": a.get("signature") or "",
               "handle": a.get("unique_id") or ""}
        for k in ("followers", "works"):
            if _num(a.get(k)):
                out[k] = _num(a.get(k))
        return out
    if plat == "bilibili":
        try:
            return _bili_owner(url)
        except Exception as e:
            err = str(e)
        try:
            r = _ytdlp_uploader(url)
            if not r.get("home") and r.get("uid"):
                r["home"] = "https://space.bilibili.com/%s" % r["uid"]
            if r.get("home"):
                r["platform"] = "bilibili"
                return r
        except Exception:
            pass
        raise RuntimeError(err)
    if plat == "x":
        # X（推特）：主页就在链接里（x.com/<账号>/status/…），不用联网
        m = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:[/?#]|$)", url)
        if m and m.group(1).lower() not in ("i", "home", "search", "intent", "share", "status", "hashtag"):
            h = m.group(1)
            return {"platform": "x", "home": "https://x.com/%s" % h, "uid": h, "name": "@" + h, "handle": h}
    proxy = _proxy() if plat in ("youtube", "tiktok", "x") else ""
    try:
        r = _ytdlp_uploader(url, proxy)
    except Exception as e:
        raise RuntimeError("读不到这条视频的作者信息（%s）" % str(e).split("\n")[0][:80])
    if not r.get("home"):
        raise RuntimeError("这条视频里没有博主主页信息，可以手动粘贴主页链接")
    r["platform"] = detect_platform(r["home"])
    return r


def auto_bind_from_videos(key, video_urls, force=False):
    """根据这个博主的几条视频（新的在前）自动找主页并绑到 key 名下：第一条找不到（比如视频被删了）
    就试下一条，最多试 3 条。返回 (ok, 资料或错误说明, key)。
    force=False（提取时自动做）：已经绑过 / 用户解除过 / 一天内失败过的都跳过；force=True（用户点按钮）：照做。"""
    key = (key or "").strip()
    if not key:
        return False, "缺少博主名", key
    if not force and not should_auto_bind(key):
        return False, "已经有主页了", key
    errs = []
    tried = [x for x in (video_urls or []) if x][:3]
    for u in tried:
        try:
            found = find_home_from_video(u, expect=key)
        except Exception as e:
            errs.append(str(e)[:220])
            continue
        found["video"] = _find_url(u)
        ok, r = bind(key, found["home"], hint=found, auto=True)
        if not ok:
            _mark_auto_fail(key, r)
        return ok, r, key
    msg = errs[0] if errs else "没有可用的视频链接"
    if len(tried) > 1:
        msg = "试了 %d 条视频都没找到。第一条：%s" % (len(tried), msg)
    _mark_auto_fail(key, msg)
    return False, msg[:300], key


def auto_bind_from_video(key, video_url, force=False):
    return auto_bind_from_videos(key, [video_url], force=force)

