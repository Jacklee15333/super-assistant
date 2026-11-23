"""
douyin_resolver.py — 不靠 yt-dlp 的网页解析，直接走抖音「分享页」拿无水印直链。

为什么要这条路：
  抖音的网页详情接口（yt-dlp 走的那条）现在强制要一个用 JavaScript 算出来的签名
  参数（a_bogus），yt-dlp 给不出来，取回的是空 JSON，于是报
  “Fresh cookies needed”。本模块换一条不需要那个 JS 签名的路：
    1) 把分享短链（v.douyin.com/xxx）跟随跳转，解析出视频 ID（aweme_id）；
    2) 请求移动端「分享页」https://www.iesdouyin.com/share/video/{id}/ ，
       这个页面把视频信息直接塞在 HTML 里的 window._ROUTER_DATA 里；
    3) 从里面取出 play_addr 的 CDN 直链（一般就是无水印），顺手做一次
       playwm→play 的去水印替换；
    4) 用 curl_cffi（模拟真实 Chrome 指纹）把直链下到本地文件。
  全程用 curl_cffi 的 impersonate，绕过抖音对「不像浏览器」的请求的拦截。

  任何一步失败都返回失败结果（ok=False），上层据此安静回退到原来的 yt-dlp 流程，
  所以这条路只会「锦上添花」，不会让现有功能变差。

只处理抖音；TikTok 与其它平台不走这里。
"""

import re
import json

# 移动端 UA：分享页对移动端 UA 更友好，返回的 _ROUTER_DATA 更全。
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 "
    "Mobile/15E148 Safari/604.1"
)
# 下载 CDN 直链时用的桌面 UA。
_PC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def available():
    """这条路能不能用（取决于 curl_cffi 在不在）。"""
    try:
        import curl_cffi  # noqa
        return True
    except Exception:
        return False


def _session():
    """带 Chrome 指纹的 curl_cffi 会话。
    impersonate=chrome 会自动带上一整套贴近真实 Chrome 的 TLS/HTTP 指纹和默认头，
    这是绕过抖音「不像浏览器就拦」的关键。再补一个访客 cookie 占位（ttwid 之类），
    部分分享页在完全无 cookie 时会返回精简/空的 _ROUTER_DATA。"""
    from curl_cffi import requests as creq
    s = creq.Session(impersonate="chrome")
    try:
        # 设一个无害的访客标识占位；真实值会在首次请求时被服务端 Set-Cookie 覆盖。
        # 有这一步时，分享页更倾向返回完整的视频信息块。
        s.headers.update({
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        })
    except Exception:
        pass
    return s


def _extract_aweme_id(url):
    """从一个抖音网址里抠出视频 ID（aweme_id）。抠不到返回 None。"""
    if not url:
        return None
    m = re.search(r"/(?:video|note|share/video|share/slides)/(\d{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"(?:modal_id|aweme_id|item_ids?)=(\d{6,})", url)
    if m:
        return m.group(1)
    return None


def _resolve_id(url):
    """短链 → 跟随跳转 → 拿到 aweme_id。已经是长链就直接抠。"""
    aid = _extract_aweme_id(url)
    if aid:
        return aid
    try:
        s = _session()
        r = s.get(url, headers={"User-Agent": _MOBILE_UA},
                  allow_redirects=True, timeout=8)
        # 最终落地址
        aid = _extract_aweme_id(str(getattr(r, "url", "")))
        if aid:
            return aid
        # 跳转链路里也找一遍
        for h in (getattr(r, "history", None) or []):
            aid = _extract_aweme_id(str(getattr(h, "url", "")))
            if aid:
                return aid
        # 实在不行，从落地页 HTML 里再抠一次
        aid = _extract_aweme_id(getattr(r, "text", "") or "")
        if aid:
            return aid
    except Exception:
        pass
    return None


def _find_item(data):
    """从 _ROUTER_DATA 里把那条视频 item 找出来（结构多变，挨个兜底）。"""
    if not isinstance(data, dict):
        return None
    loader = data.get("loaderData")
    if isinstance(loader, dict):
        for _k, v in loader.items():
            if not isinstance(v, dict):
                continue
            vir = v.get("videoInfoRes")
            if isinstance(vir, dict):
                il = vir.get("item_list")
                if isinstance(il, list) and il:
                    return il[0]
            # 个别版本直接把 item_list 放在这一层
            il = v.get("item_list")
            if isinstance(il, list) and il:
                return il[0]
    # 再兜底：全局找一个带 video.play_addr 的 dict
    found = []

    def walk(o):
        if found:
            return
        if isinstance(o, dict):
            vid = o.get("video")
            if isinstance(vid, dict) and (vid.get("play_addr") or vid.get("playApi")):
                found.append(o)
                return
            for vv in o.values():
                walk(vv)
        elif isinstance(o, list):
            for vv in o:
                walk(vv)

    try:
        walk(data)
    except Exception:
        pass
    return found[0] if found else None


def _parse_share_page(html):
    """从分享页 HTML 里取出 window._ROUTER_DATA 并定位到视频 item。"""
    if not html:
        return None
    data = None
    for pat in (
        r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*;?\s*</script>",
        r"window\._ROUTER_DATA\s*=\s*(\{.*\})\s*</script>",
        r"_ROUTER_DATA\s*=\s*(\{.*?\})\s*;",
        r"id=\"RENDER_DATA\"[^>]*>(\{.*?\})</script>",
        r"id=\"RENDER_DATA\"[^>]*>([^<]+)</script>",
        # 新版有时把数据塞进 __pace_f / SSR 注水脚本，这里宽松兜一手
        r"self\.__pace_f\.push\(\[\d+,\s*\"(.*?play_addr.*?)\"\]\)",
    ):
        m = re.search(pat, html, re.S)
        if not m:
            continue
        raw = m.group(1)
        # 依次尝试：直接解析 → URL 解码后解析 → 反转义后解析
        import urllib.parse as _up
        for transform in (
            lambda x: x,
            lambda x: _up.unquote(x),
            lambda x: x.encode("utf-8").decode("unicode_escape"),
        ):
            try:
                data = json.loads(transform(raw))
                break
            except Exception:
                data = None
        if data is not None:
            break
    if data is None:
        return None
    return _find_item(data)


def _urls_from_item(item):
    """从 item 里取出可下载的 CDN 直链列表（去重、附带去水印变体）。"""
    raw = []
    try:
        v = item.get("video") or {}
        for key in ("play_addr", "playApi", "download_addr", "play_addr_h264"):
            pa = v.get(key)
            if isinstance(pa, dict):
                for u in (pa.get("url_list") or []):
                    if u:
                        raw.append(u)
            elif isinstance(pa, str) and pa:
                raw.append(pa)
        # 不同码率里也常有可用直链
        for br in (v.get("bit_rate") or []):
            try:
                for u in ((br.get("play_addr") or {}).get("url_list") or []):
                    if u:
                        raw.append(u)
            except Exception:
                pass
    except Exception:
        pass

    out = []
    for u in raw:
        u = u.replace("\\u002F", "/").replace("\\/", "/")
        if u.startswith("//"):
            u = "https:" + u
        out.append(u)
        if "playwm" in u:  # 去水印：playwm → play
            out.append(u.replace("playwm", "play"))

    seen, ded = set(), []
    for u in out:
        if u and u not in seen:
            seen.add(u)
            ded.append(u)
    return ded


# ════════════════════ 移动端 JSON 接口（主力） ════════════════════
# 背景：抖音的「分享页」(iesdouyin.com/share/video/{id}/) 现在经常不再把视频数据
#   塞进 window._ROUTER_DATA，于是旧的「爬 HTML」那条路解析不到 item，整条链路
#   就垮到 yt-dlp，再被「Fresh cookies needed」挡住。
#   这里改走抖音移动端的 JSON 接口 iteminfo —— 它直接吐结构化 JSON，**不需要**
#   那个用 JS 算的 a_bogus 签名，curl_cffi 带上访客 cookie 就能拿到，最稳。
#   拿不到再退回下面的「分享页 HTML」老办法，老办法再不行才由上层退到 yt-dlp。
#
# 接口候选（逐个试，命中即用）：
#   1) https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={id}
#      —— 最经典，返回 {"item_list":[{...}]}，play_addr 多为无水印。
#   2) https://www.iesdouyin.com/aweme/v1/web/aweme/detail/?aweme_id={id}
#      —— 返回 {"aweme_detail":{...}}。
#   3) https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={id}
#      —— 主站同名接口，带访客 cookie 有时也能拿到。
#   抖音时常调整这些接口的可用性，所以多备几个、逐个试，谁通用谁。
_API_CANDIDATES = (
    "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids=%s",
    "https://www.iesdouyin.com/aweme/v1/web/aweme/detail/?aweme_id=%s",
    "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=%s",
)
# 兼容旧引用（health_check 等处历史用过这两个名字）
_ITEMINFO_API = _API_CANDIDATES[0]
_DETAIL_API = _API_CANDIDATES[1]


def _api_get_json(session, api_url, referer=None, user_agent=None, timeout=10):
    """GET 一个抖音 JSON 接口，返回解析后的 dict（失败返回 None）。
    超时默认 10 秒：接口正常时 1~2 秒就回，迟迟不回基本就是被拦/接口已废，
    早点放手去走下一个候选/兜底，免得一条失败的请求把用户晾上好几分钟。
    referer/user_agent 可覆盖：作品列表接口要用桌面 UA + 主页 Referer（和签名一致）。"""
    try:
        r = session.get(api_url, headers={
            "User-Agent": user_agent or _MOBILE_UA,
            "Referer": referer or "https://www.iesdouyin.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }, timeout=timeout)
        if getattr(r, "status_code", 0) >= 400:
            return None
        txt = getattr(r, "text", "") or ""
        if not txt.strip():
            return None
        try:
            return json.loads(txt)
        except Exception:
            # 个别情况返回里有 BOM / 前后噪声，截一段大括号再试
            i, j = txt.find("{"), txt.rfind("}")
            if 0 <= i < j:
                try:
                    return json.loads(txt[i:j + 1])
                except Exception:
                    return None
            return None
    except Exception:
        return None


def _api_get_json_ex(session, api_url, referer=None, user_agent=None,
                     timeout=12, extra_headers=None):
    """像 _api_get_json，但额外返回 (data, http_status, raw_text)，并支持自定义请求头
    （作品列表接口要带 Cookie 头）。data 解析失败为 None，但 status / raw 仍会带回，
    便于诊断到底是被拦（空 200 / 4xx）还是结构变了（非 JSON）。"""
    headers = {
        "User-Agent": user_agent or _SIGN_UA,
        "Referer": referer or "https://www.douyin.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if extra_headers:
        headers.update({k: v for k, v in extra_headers.items() if v})
    try:
        r = session.get(api_url, headers=headers, timeout=timeout)
    except Exception as e:
        return None, "exc:%s" % (str(e)[:60]), ""
    status = getattr(r, "status_code", 0)
    txt = getattr(r, "text", "") or ""
    if status >= 400:
        return None, status, txt[:300]
    if not txt.strip():
        return None, status, ""        # 空 200：典型风控信号
    try:
        return json.loads(txt), status, txt[:300]
    except Exception:
        i, j = txt.find("{"), txt.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(txt[i:j + 1]), status, txt[:300]
            except Exception:
                pass
    return None, status, txt[:300]


def _item_from_api(data):
    """从 iteminfo / detail 接口的返回里取出那条视频 item。取不到返回 None。"""
    if not isinstance(data, dict):
        return None
    # iteminfo：{"item_list":[{...}]}
    il = data.get("item_list")
    if isinstance(il, list) and il and isinstance(il[0], dict):
        return il[0]
    # detail：{"aweme_detail":{...}}
    ad = data.get("aweme_detail")
    if isinstance(ad, dict) and ad:
        return ad
    # 兜底：全局找一个带 video.play_addr 的 dict（复用 _find_item 的扫描）
    return _find_item(data)


def _resolve_via_api(session, aid):
    """走移动端 JSON 接口拿 item。逐个候选接口尝试，命中即返回 item，全空返回 None。"""
    for tmpl in _API_CANDIDATES:
        data = _api_get_json(session, tmpl % aid)
        if not data:
            continue
        item = _item_from_api(data)
        if item:
            return item
    return None


def _author_from_item(item):
    """v59：从视频数据里取作者信息（sec_uid、昵称、头像、简介…），供「根据视频找博主主页」用。"""
    try:
        a = item.get("author") or {}
        if not isinstance(a, dict):
            return {}

        def first(x):
            try:
                return ((x or {}).get("url_list") or [""])[0] or ""
            except Exception:
                return ""
        out = {"sec_uid": a.get("sec_uid") or "", "uid": str(a.get("uid") or ""),
               "nickname": (a.get("nickname") or "").strip(),
               "avatar": first(a.get("avatar_larger")) or first(a.get("avatar_medium"))
               or first(a.get("avatar_thumb")) or first(a.get("avatar_168x168")),
               "signature": (a.get("signature") or "").strip(),
               "unique_id": a.get("unique_id") or a.get("short_id") or "",
               "followers": a.get("follower_count"), "works": a.get("aweme_count")}
        return {k: v for k, v in out.items() if v not in (None, "", "0")}
    except Exception:
        return {}


def _build_result_from_item(item, aid):
    """从一条 item 抽出 {urls,title,uploader,tags}，组装成 resolve() 的返回结构。
    没拿到直链时返回 ok=False 但仍带 meta（标题/作者/标签），交上层决定怎么用。"""
    title = ""
    uploader = ""
    tags = []
    try:
        title = (item.get("desc") or "").strip()
    except Exception:
        pass
    try:
        uploader = ((item.get("author") or {}).get("nickname") or "").strip()
    except Exception:
        pass
    try:
        for te in (item.get("text_extra") or []):
            nm = (te.get("hashtag_name") or "").strip()
            if nm and nm not in tags:
                tags.append(nm)
    except Exception:
        pass

    author = _author_from_item(item)
    _remember_author(aid, author)          # v61：记下来，找博主主页时直接用
    urls = _urls_from_item(item)
    if not urls:
        return {"ok": False, "error": "没拿到可下载的视频直链",
                "title": title, "uploader": uploader, "tags": tags,
                "aweme_id": aid, "author": author}
    return {"ok": True, "urls": urls, "title": title,
            "uploader": uploader, "tags": tags, "aweme_id": aid, "author": author}


def resolve(url, allow_browser=True):
    """解析抖音链接：先走下面的 HTTP 两层（快）；都拿不到直链时，再用真浏览器兜底（慢但最稳）。
    返回结构同 _resolve_http。"""
    res = _resolve_http(url)
    if res.get("ok") or not allow_browser:
        return res
    aid = res.get("aweme_id") or _resolve_id(url)
    if not aid:
        return res
    br = _resolve_via_browser(aid)
    if br.get("ok"):
        for k in ("title", "uploader", "tags"):          # 浏览器没拿到的标题等，用 HTTP 那份补上
            if not br.get(k) and res.get(k):
                br[k] = res.get(k)
        return br
    res = dict(res)
    res["error"] = "%s；浏览器兜底：%s" % (res.get("error") or "HTTP 解析失败", br.get("error"))
    return res


def _resolve_via_browser(aid, timeout_s=30):
    """③ 真浏览器兜底（2026-11 抖音又改规则后加的）：用本机 Chrome 在后台（无界面）打开视频页，
    让页面自己算签名、自己请求详情接口，我们只在旁边「听」接口返回的 JSON 和视频请求，
    从里面拿直链。抖音怎么改签名算法都不影响这条路。
    只处理用户自己发来的这一条视频，不做批量。"""
    import time as _t
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"ok": False, "error": "没装 Playwright（%s）" % str(e)[:60]}
    page_url = _BROWSER_PAGE % aid
    responses, media = [], []

    def on_resp(r):                       # 事件回调里只记录，解析放到外面做（同步 API 更稳）
        try:
            u = r.url
            if "aweme/detail" in u or "iteminfo" in u:
                responses.append(r)
            elif r.request.resource_type == "media" or "douyinvod.com" in u or "mime_type=video" in u:
                media.append(u)
        except Exception:
            pass

    item, title = None, ""
    try:
        with sync_playwright() as pw:
            browser = None
            for ch in ("chrome", "msedge", None):
                try:
                    kw = dict(headless=True, args=["--disable-blink-features=AutomationControlled",
                                                   "--mute-audio", "--autoplay-policy=no-user-gesture-required",
                                                   "--no-proxy-server"])      # 抖音是国内站：直连，不走系统代理
                    if ch:
                        kw["channel"] = ch
                    browser = pw.chromium.launch(**kw)
                    break
                except Exception:
                    continue
            if browser is None:
                return {"ok": False, "error": "没有可用的浏览器（Chrome/Edge）"}
            try:
                ctx = browser.new_context(user_agent=_PC_UA, locale="zh-CN",
                                          viewport={"width": 1280, "height": 800})
                ck = _load_user_cookie()
                if ck:
                    ctx.add_cookies([{"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
                                     for k, v in ck.items() if k and v])
                page = ctx.new_page()
                page.on("response", on_resp)
                page.goto(page_url, wait_until="domcontentloaded", timeout=25000)
                end = _t.time() + timeout_s
                media_since = None
                while _t.time() < end and not item:
                    page.wait_for_timeout(600)
                    while responses and not item:
                        r = responses.pop(0)
                        try:
                            it = _item_from_api(r.json())
                            if it and _urls_from_item(it):
                                item = it
                        except Exception:
                            pass
                    if not media:
                        try:
                            media.extend(page.evaluate(
                                "() => [...document.querySelectorAll('video, video source')]"
                                ".map(v => v.currentSrc || v.src).filter(s => s && s.startsWith('http'))") or [])
                        except Exception:
                            pass
                    if media and media_since is None:
                        media_since = _t.time()
                    if media_since and _t.time() - media_since > 6:   # 已有视频地址，再给接口 6 秒机会补标题
                        break
                try:
                    title = (page.title() or "").replace(" - 抖音", "").strip()
                except Exception:
                    title = ""
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        return {"ok": False, "error": "浏览器打开视频页出错：%s" % str(e).split("\n")[0][:100]}
    if item:
        return _build_result_from_item(item, aid)
    urls = []
    for u in media:
        if u not in urls and not u.startswith("blob:"):
            urls.append(u)
    if urls:
        return {"ok": True, "urls": urls, "title": title, "uploader": "", "tags": [], "aweme_id": aid}
    return {"ok": False, "error": "浏览器也没拿到视频（可能要登录或出现了验证码，可在 memory/douyin_cookie.txt 填入登录 Cookie）",
            "aweme_id": aid}


_BROWSER_PAGE = "https://www.douyin.com/video/%s"


# ════════════════════ v61：根据视频找作者（博主主页用）════════════════════
# 2026-11 抖音改规则后，不开浏览器的「快速通道」（移动端接口 + 分享页）基本拿不到视频信息了，
# 提取视频靠的是上面的「浏览器兜底」。找博主主页也走同一条路：
#   ① 缓存：这条视频之前解析时拿到过作者（比如刚提取完），直接用；
#   ② 快速通道（不开浏览器，1 秒左右）；
#   ③ 后台浏览器：打开视频页，听页面自己请求的详情数据（里面有作者 sec_uid、昵称、头像）；
#      没听到时，再从页面上找作者主页链接——只认名字对得上的，防止认成评论区或推荐里的别人。
# 一键识别时整批共用一个浏览器（browser_session），不用每个博主都重新开一次 Chrome。
import threading as _thr

_AUTHOR_CACHE = {}
_tl = _thr.local()


def _remember_author(aid, author):
    try:
        if aid and author and (author.get("sec_uid") or author.get("uid")):
            if len(_AUTHOR_CACHE) > 500:
                _AUTHOR_CACHE.clear()
            _AUTHOR_CACHE[str(aid)] = dict(author)
    except Exception:
        pass


class _BrowserSession:
    """一个后台浏览器（第一次要用时才打开）。只能在打开它的那个线程里用。"""

    def __init__(self):
        self.pw = self.browser = self.ctx = None

    def context(self):
        if self.ctx is not None:
            return self.ctx
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        for ch in ("chrome", "msedge", None):
            try:
                kw = dict(headless=True, args=["--disable-blink-features=AutomationControlled",
                                               "--mute-audio", "--no-proxy-server"])   # 抖音是国内站：直连
                if ch:
                    kw["channel"] = ch
                self.browser = self.pw.chromium.launch(**kw)
                break
            except Exception:
                continue
        if self.browser is None:
            self.close()
            raise RuntimeError("没有可用的浏览器（Chrome/Edge）")
        self.ctx = self.browser.new_context(user_agent=_PC_UA, locale="zh-CN",
                                            viewport={"width": 1280, "height": 800})
        ck = _load_user_cookie()
        if ck:
            try:
                self.ctx.add_cookies([{"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
                                      for k, v in ck.items() if k and v])
            except Exception:
                pass
        return self.ctx

    def close(self):
        for obj, meth in ((self.ctx, "close"), (self.browser, "close"), (self.pw, "stop")):
            try:
                if obj is not None:
                    getattr(obj, meth)()
            except Exception:
                pass
        self.pw = self.browser = self.ctx = None


class browser_session:
    """with douyin_resolver.browser_session(): …  —— 这段时间里（同一线程）找作者共用一个后台浏览器。"""

    def __enter__(self):
        self.s = _BrowserSession()
        self.prev = getattr(_tl, "session", None)
        _tl.session = self.s
        return self.s

    def __exit__(self, *a):
        _tl.session = self.prev
        self.s.close()
        return False


_JS_USER_LINKS = r"""() => [...document.querySelectorAll('a[href*="/user/"]')].map(a => {
  const m = (a.getAttribute('href') || '').match(/\/user\/(MS4w[\w-]+)/);
  const img = a.querySelector('img');
  return m ? {sec_uid: m[1], text: (a.innerText || a.getAttribute('title') || '').trim().slice(0, 80),
              avatar: img ? (img.currentSrc || img.src || '') : ''} : null;
}).filter(Boolean)"""


# v62：有的视频页不另外请求详情，而是把数据直接写在页面里（RENDER_DATA）——从里面按视频编号找作者
_JS_SSR_AUTHOR = r"""(aid) => {
  const el = document.getElementById('RENDER_DATA');
  if (!el) return null;
  let data;
  try { data = JSON.parse(decodeURIComponent(el.textContent)); } catch (e) { return null; }
  const seen = new Set();
  let found = null;
  const walk = (o, depth) => {
    if (!o || typeof o !== 'object' || found || depth > 14 || seen.has(o)) return;
    seen.add(o);
    const id = String(o.awemeId || o.aweme_id || o.itemId || '');
    if (id === aid) {
      const a = o.authorInfo || o.author;
      if (a && (a.secUid || a.sec_uid)) {
        const av = a.avatarThumb || a.avatar_thumb || a.avatarMedium || a.avatar_medium || {};
        found = {sec_uid: a.secUid || a.sec_uid, nickname: a.nickname || '',
                 avatar: (av.urlList || av.url_list || [])[0] || '', signature: a.signature || '',
                 followers: a.followerCount || a.follower_count || null};
        return;
      }
    }
    for (const k in o) { try { walk(o[k], depth + 1); } catch (e) {} }
  };
  walk(data, 0);
  return found;
}"""

# 视频没了时页面上会写的话（出现就不用再干等 25 秒）
_GONE_WORDS = ("视频不存在", "作品不存在", "内容不存在", "该作品已删除", "作品已删除", "已被删除", "已删除",
               "视频已失效", "作品已失效", "暂时无法观看", "仅作者自己可见", "私密作品", "该内容无法", "你要观看的视频不存在")


def _norm_name(s):
    """名字比较前统一一下：去掉表情、空格、标点，字母转小写。"""
    return re.sub(r"[^\w]+", "", (s or "").lower()).replace("_", "")


def _name_match(seen, expect):
    a, b = _norm_name(seen), _norm_name(expect)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 2 and short in long_ and len(long_) - len(short) <= 4


def _author_via_browser(aid, expect="", timeout_s=25):
    """后台浏览器打开视频页找作者。返回 (author 或 {}, 说明)。
    依次看：页面请求的详情数据 → 页面里直接写着的数据（RENDER_DATA）→ 页面上名字对得上的作者链接。"""
    import time as _t
    try:
        import playwright  # noqa: F401
    except Exception:
        return {}, "没装 Playwright"
    sess = getattr(_tl, "session", None)
    own = sess is None
    if own:
        sess = _BrowserSession()
    page = None
    found, links, n_this, n_other, gone, title = {}, [], 0, 0, "", ""
    exp = (expect or "").strip().lstrip("@")
    try:
        ctx = sess.context()
        page = ctx.new_page()
        responses = []

        def on_resp(r):                    # 回调里只记录，解析放到外面做
            try:
                if "aweme/detail" in r.url or "iteminfo" in r.url:
                    responses.append(r)
            except Exception:
                pass
        page.on("response", on_resp)
        page.goto(_BROWSER_PAGE % aid, wait_until="domcontentloaded", timeout=25000)
        t0 = _t.time()
        end = t0 + timeout_s
        while _t.time() < end and not found:
            page.wait_for_timeout(700)
            while responses and not found:
                r = responses.pop(0)
                try:
                    it = _item_from_api(r.json())
                except Exception:
                    it = None
                if not it:
                    continue
                if str(it.get("aweme_id") or aid) != str(aid):
                    n_other += 1             # 推荐区别的视频的数据，不要
                    continue
                n_this += 1
                a = _author_from_item(it)
                if a.get("sec_uid") or a.get("uid"):
                    found = a
            if found:
                break
            try:
                ssr = page.evaluate(_JS_SSR_AUTHOR, str(aid))
            except Exception:
                ssr = None
            if ssr and ssr.get("sec_uid"):
                found = {k: v for k, v in ssr.items() if v not in (None, "")}
                break
            try:
                txt = page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 3000)") or ""
            except Exception:
                txt = ""
            gone = next((w for w in _GONE_WORDS if w in txt), "")
            if gone and _t.time() - t0 > 5:
                break                        # 页面已经说视频没了，不用再等
            try:
                links = page.evaluate(_JS_USER_LINKS) or []
            except Exception:
                links = []
            if not exp:
                continue
            for ln in links:
                first = (ln.get("text") or "").split("\n")[0].replace("@", "").strip()
                if first and _name_match(first, exp):
                    av = ln.get("avatar") or next((x.get("avatar") for x in links
                                                   if x.get("sec_uid") == ln["sec_uid"] and x.get("avatar")), "")
                    found = {"sec_uid": ln["sec_uid"], "nickname": first, "avatar": av}
                    break
        try:
            title = (page.title() or "").strip()
        except Exception:
            title = ""
    except Exception as e:
        return {}, "打开视频页出错（%s）" % str(e).split("\n")[0][:90]
    finally:
        try:
            if page is not None:
                page.close()
        except Exception:
            pass
        if own:
            sess.close()
    if found:
        _remember_author(aid, found)
        return found, "浏览器"
    if gone:
        return {}, "这条视频已经删了或设成私密了（页面上写着「%s」）" % gone
    if n_this:
        return {}, "这条视频的数据里没有作者信息"
    names = []
    for ln in links:
        first = (ln.get("text") or "").split("\n")[0].replace("@", "").strip()
        if first and first not in names:
            names.append(first[:16])
    if names:
        return {}, "页面上没有叫「%s」的作者（页面上看到的是：%s%s）。博主可能改名了，或者这条视频已经没了" % (
            exp, "、".join(names[:5]), "…" if len(names) > 5 else "")
    if n_other:
        return {}, "页面只加载了推荐区别的视频，没加载这条（多半已删除）"
    return {}, "等了 %d 秒没拿到视频信息（页面标题「%s」；可能要登录或出现了验证码）" % (timeout_s, title[:30])


def find_author(url, expect=""):
    """根据一条抖音视频找作者。返回 (author 或 {}, 说明)：成功时说明是用哪条路找到的，
    失败时写清楚每一步卡在哪。expect = 笔记里记的作者名，用来核对页面上的链接。"""
    try:
        aid = _resolve_id(url)
    except Exception:
        aid = None
    if not aid:
        return {}, "没认出视频编号（链接可能失效了）"
    aid = str(aid)
    if aid in _AUTHOR_CACHE:
        return dict(_AUTHOR_CACHE[aid]), "缓存"
    steps = []
    try:
        r = _resolve_http(_BROWSER_PAGE % aid)
        a = r.get("author") or {}
        if a.get("sec_uid") or a.get("uid"):
            _remember_author(aid, a)
            return a, "快速通道"
    except Exception:
        pass
    a, why = _author_via_browser(aid, expect=expect)
    if a:
        return a, why
    return {}, why


def _resolve_http(url):
    """把抖音链接解析成 {ok, urls:[...], title, uploader, aweme_id}。
    失败返回 {ok: False, error: 原因}。

    取数顺序（逐层兜底，前一层失败才走后一层）：
      ① 移动端 JSON 接口 iteminfo / detail —— 最稳，不要 a_bogus 签名；
      ② 分享页 HTML 里的 window._ROUTER_DATA —— 老办法，接口都挂了才用；
    两层都拿不到直链时，会把能抓到的标题/作者/标签带回去（ok=False + meta），
    让上层既能退到 yt-dlp 下载，又能把标题用起来。"""
    if not available():
        return {"ok": False, "error": "curl_cffi 不可用，跳过分享页解析"}
    aid = _resolve_id(url)
    if not aid:
        return {"ok": False, "error": "没解析到视频 ID"}

    s = _session()

    # ── ① 主力：移动端 JSON 接口 ──
    meta_fallback = None     # 接口虽没给直链、但给了标题/作者，先存着，最后兜底用
    try:
        item = _resolve_via_api(s, aid)
        if item:
            res = _build_result_from_item(item, aid)
            if res.get("ok"):
                return res
            # 接口拿到了 item 但没抽到直链 → 记下 meta，继续往下试分享页
            meta_fallback = res
    except Exception:
        pass

    # ── ② 兜底：分享页 HTML ──
    share = "https://www.iesdouyin.com/share/video/%s/" % aid
    html = ""
    try:
        r = s.get(share, headers={
            "User-Agent": _MOBILE_UA,
            "Referer": "https://www.douyin.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }, timeout=8)
        html = getattr(r, "text", "") or ""
    except Exception as e:
        # 分享页也请求不到：若接口至少给过 meta，就带 meta 返回；否则报错
        if meta_fallback:
            return meta_fallback
        return {"ok": False, "error": "分享页请求失败：%s" % e}

    item = _parse_share_page(html)
    if not item:
        # 分享页也没解析到 item：若接口此前给过 meta（标题/作者），带它返回，
        # 让上层至少能拿到标题、并据 ok=False 退到 yt-dlp 下载。
        if meta_fallback:
            return meta_fallback
        return {"ok": False, "error": "分享页没解析到视频信息（接口与页面都未给出，结构可能又变了）",
                "aweme_id": aid}

    res = _build_result_from_item(item, aid)
    # 分享页拿到了直链 → 直接用；没拿到但接口此前给过更全的 meta，则优先用接口那份 meta。
    if (not res.get("ok")) and meta_fallback:
        # 合并：标题/作者/标签哪份非空用哪份（接口优先），都标 ok=False
        merged = dict(meta_fallback)
        for k in ("title", "uploader"):
            if not merged.get(k) and res.get(k):
                merged[k] = res.get(k)
        if not merged.get("tags") and res.get("tags"):
            merged["tags"] = res.get("tags")
        if not merged.get("author") and res.get("author"):
            merged["author"] = res.get("author")
        return merged
    return res


def _compose_display_title(title, tags, uploader):
    """给「排队/正在处理」列表用的展示标题，保证尽量非空。
    抖音很多视频本身没有文案（desc 为空），这时退而用话题标签拼，
    再不行用「作者 的视频」，避免列表永远停在「获取名称中…」。"""
    t = (title or "").strip()
    if t:
        return t
    # desc 为空 → 用话题标签拼一个（# 开头，用户一眼能认）
    tl = [s.strip() for s in (tags or []) if s and s.strip()]
    if tl:
        return " ".join(("#" + s if not s.startswith("#") else s) for s in tl[:6])
    # 标签也没有 → 用作者名
    up = (uploader or "").strip()
    if up:
        return "%s 的视频" % up
    return ""


def fetch_meta(url):
    """只爬这条抖音视频的元信息（标题/作者/话题标签），不下载视频本身。
    供「排队列表显示视频名」「下载走了兜底但标题没拿到」时单独补抓用。
    返回 {ok, title, display_title, uploader, tags}；任何失败都返回 ok=False，不抛异常。

      · title         —— 抖音原始文案 desc（可能为空，给「视频笔记真正标题」用，
                          为空时上层会回退到「文稿首句」，行为和以前一致）；
      · display_title —— 给「排队/正在处理」列表显示用的标题，保证尽量非空：
                          desc 为空时用 话题标签 / 「作者 的视频」 合成，
                          这样列表不会永远停在「获取名称中…」。

    要点：抖音不少视频 desc 本就是空的。这种情况下，旧逻辑回一个空 title，
    调用方（_quick_title）见标题为空就误以为「没拿到」，转去走 yt-dlp 兜底——
    而 yt-dlp 对抖音根本解不动，只会刷一屏 Unsupported URL，列表还是停在
    「获取名称中…」。现在分成两个字段：原始 title 保持原样（不污染笔记标题的
    「文稿首句」兜底），另给一个非空的 display_title 让列表直接有名字。"""
    try:
        info = resolve(url, allow_browser=False)      # 只要标题，不值得开浏览器
        # resolve 即便 ok=False（下不了直链）也会带回 title/uploader/tags
        title = (info.get("title") or "").strip()
        uploader = (info.get("uploader") or "").strip()
        tags = info.get("tags") or []
        # display_title：只用真实信息合成（话题标签 / 「作者 的视频」），不含裸 ID。
        display = _compose_display_title(title, tags, uploader)
        # fallback_title：连标题/标签/作者都没有时的最后占位，单独放一个字段，
        # 绝不让它冒充真实标题去抢在 yt-dlp 兜底之前（否则真实标题会被占位符截断）。
        aid = (info.get("aweme_id") or "").strip() or (_resolve_id(url) or "")
        fallback = ("抖音视频 …%s" % aid[-6:]) if aid else ""
        ok = bool(title or display or fallback)
        return {"ok": ok, "title": title, "display_title": display,
                "uploader": uploader, "tags": tags, "fallback_title": fallback}
    except Exception as e:
        return {"ok": False, "title": "", "display_title": "",
                "uploader": "", "tags": [], "fallback_title": "", "error": str(e)}




def download(url, dest_path, referer="https://www.douyin.com/"):
    """用 curl_cffi（Chrome 指纹）把直链下到 dest_path。成功返回 True。
    抖音短视频通常几 MB，直接整段拿下来写文件，省得跟流式 API 较劲。"""
    if not available():
        return False
    try:
        s = _session()
        r = s.get(url, headers={
            "User-Agent": _PC_UA,
            "Referer": referer,
            "Accept": "*/*",
        }, timeout=90)
        if getattr(r, "status_code", 0) >= 400:
            return False
        data = getattr(r, "content", b"") or b""
        if len(data) < 2048:  # 太小八成是错误页/空响应，不算成功
            return False
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def fetch_to(url, dest_path):
    """解析 + 下载一条龙：把抖音链接的视频下到 dest_path。
    成功返回 {ok: True, path, title, uploader}；失败返回 {ok: False, error}。
    供 video_transcribe 调用——拿到 mp4 后交给现有听写流程即可。"""
    info = resolve(url)
    if not info.get("ok"):
        return {"ok": False, "error": info.get("error") or "解析失败"}
    for u in info["urls"]:
        if download(u, dest_path):
            return {"ok": True, "path": dest_path,
                    "title": info.get("title") or "",
                    "uploader": info.get("uploader") or "",
                    "tags": info.get("tags") or []}
    return {"ok": False, "error": "直链都下载失败（可能 CDN 拒绝或链接过期）"}


# ════════════════════ 用户主页作品列表（带 a_bogus/X-Bogus 签名） ════════════════════
# 背景：抖音用户主页作品列表接口 www.douyin.com/aweme/v1/web/aweme/post/ 现在强制要一个
#   用 JS 算出来的签名参数（a_bogus）。以前那些不用签名的老接口（iesdouyin 系）已基本作废，
#   yt-dlp 也给不出签名，于是只能 “Unsupported URL / 取不到作品”。
#
#   这里引入两份**纯 Python 实现的签名算法**（从开源项目移植，见 dy_abogus.py / dy_xbogus.py），
#   在本地把 a_bogus 算出来，再带访客 cookie（ttwid + 本地造的 msToken）去请求正式接口，
#   就能像浏览器那样列出公开博主的作品——**无需登录**（私密账号 / 收藏夹才需要登录 cookie）。
#
#   取数顺序（前一层失败/为空才走后一层）：
#     ① 正式接口 aweme/post + a_bogus 签名（gmssl 在时）——主力，最稳；
#     ② 同接口改用 X-Bogus 签名（纯标准库，gmssl 不在时自动走这条）——兜底；
#     ③ 用户主页 HTML 里的 SSR 注水数据（RENDER_DATA / _ROUTER_DATA / __pace_f）——最后一手。
#   全失败返回 {ok: False, error}，由上层 creator_watch 再退回 yt-dlp（基本也列不到，
#   于是给用户那句“手动贴链接”的提示）。整条链路只会“锦上添花”，不会让现有逻辑变差。

# 正式 web 接口域名 & 路径
_POST_API_HOST = "https://www.douyin.com"
_POST_API_PATH = "/aweme/v1/web/aweme/post/"
# 桌面 Chrome UA（和签名里用的 UA 必须一致，否则签名校验不过）
_SIGN_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
)


def _gen_ms_token(n=182):
    """本地造一个长度合规的随机 msToken（接口要这个参数在，但不强校验真伪）。"""
    import random, string
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n)) + "=="


def _gen_webid():
    """造一个 19 位的 webid（抖音接口现在要这个参数；纯数字，长度对即可）。"""
    import random
    return str(random.randint(7000000000000000000, 7499999999999999999))


def _gen_verify_fp():
    """造一个 verifyFp / s_v_web_id 值，格式照抓包里真实的：
    verify_<8位时间戳样>_<4>_<4>_<4>_<4>_<12>。抖音只校验格式像，不校验真伪。"""
    import random, string
    def seg(n):
        return "".join(random.choices(string.ascii_letters + string.digits, k=n))
    return "verify_%s_%s_%s_%s_%s_%s" % (
        seg(8).lower(), seg(8), seg(4), seg(4), seg(4), seg(12))


# 用户可手动粘贴的抖音 Cookie（从浏览器复制）。放这个文件里就会被优先使用，
# 能彻底绕过「访客 cookie 被风控拦」的问题——这是稳定列作品最可靠的办法。
def _cookie_file():
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "douyin_cookie.txt")


def _parse_cookie_str(raw):
    """把浏览器复制的一整串 Cookie（k1=v1; k2=v2; ...）解析成 dict。"""
    out = {}
    for part in (raw or "").replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def _load_user_cookie():
    """读抖音 Cookie。没有返回 {}。
    v146：先读这台电脑上的私密文件夹（「登录抖音」存在那里，不在项目里、不会被 GitHub 备份），
    没有再读老位置 backend/memory/douyin_cookie.txt。"""
    try:
        import os as _os
        pp = _private_cookie_file()
        if _os.path.exists(pp):
            with open(pp, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if raw:
                return _parse_cookie_str(raw)
    except Exception:
        pass
    try:
        p = _cookie_file()
        import os
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if raw:
                return _parse_cookie_str(raw)
    except Exception:
        pass
    return {}


def _apply_cookies(session, cookies):
    """把一组 cookie 塞进会话（curl_cffi）。尽力而为。"""
    if not cookies:
        return
    try:
        jar = getattr(session, "cookies", None)
        for k, v in cookies.items():
            try:
                if jar is not None and hasattr(jar, "set"):
                    jar.set(k, v, domain=".douyin.com")
                elif jar is not None:
                    jar[k] = v
            except Exception:
                try:
                    session.cookies.update({k: v})
                except Exception:
                    pass
    except Exception:
        pass


def _ensure_ttwid(session, sec_uid=None):
    """确保会话里有访客 cookie（公开作品列表尽量用访客 cookie；用户填了真 cookie 更稳）。
    顺序：① 用户手填 cookie（最稳，绕风控）→ ② 主动访问抖音首页 + 目标用户主页拿访客
    ttwid / s_v_web_id / __ac_nonce（用户主页能下发后两个，post 接口会校验）。
    返回收集到的 cookie dict（尽力而为，失败也不致命）。"""
    # ① 用户手填 cookie 优先
    user_ck = _load_user_cookie()
    if user_ck:
        _apply_cookies(session, user_ck)

    # ② 访客 cookie 预热：先首页，再目标用户主页（用户页能拿到 s_v_web_id / __ac_nonce）
    warm_urls = ["https://www.douyin.com/"]
    if sec_uid:
        warm_urls.append("https://www.douyin.com/user/%s" % sec_uid)
    else:
        warm_urls.append("https://www.douyin.com/discover")
    try:
        jar = getattr(session, "cookies", None)
        have = False
        if jar is not None:
            try:
                have = bool(jar.get("ttwid")) and bool(jar.get("s_v_web_id"))
            except Exception:
                have = False
        if not have:
            for warm in warm_urls:
                try:
                    session.get(warm, headers={
                        "User-Agent": _SIGN_UA,
                        "Referer": "https://www.douyin.com/",
                        "Accept": ("text/html,application/xhtml+xml,application/xml;"
                                   "q=0.9,image/avif,image/webp,*/*;q=0.8"),
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Upgrade-Insecure-Requests": "1",
                    }, timeout=10)
                except Exception:
                    pass
    except Exception:
        pass

    cookies = dict(user_ck) if user_ck else {}
    try:
        jar = getattr(session, "cookies", None)
        if jar is not None:
            for k in ("ttwid", "odin_tt", "passport_csrf_token", "msToken",
                      "s_v_web_id", "__ac_nonce", "sessionid", "sid_guard"):
                try:
                    v = jar.get(k)
                    if v and k not in cookies:
                        cookies[k] = v
                except Exception:
                    pass
    except Exception:
        pass

    # ③ 没拿到 ttwid → 去 ttwid 注册接口主动要一个（抖音公开的访客标识下发接口）
    if not cookies.get("ttwid"):
        tt = _register_ttwid(session)
        if tt:
            cookies["ttwid"] = tt
            _apply_cookies(session, {"ttwid": tt})

    # ④ 还缺 s_v_web_id → 自己造一个格式合法的（抖音只校验「存在且格式像」，不校验真伪）。
    #    这一步是关键：诊断显示访客只有 __ac_nonce、缺 s_v_web_id 时会被风控返回空。
    if not cookies.get("s_v_web_id"):
        try:
            import random, string
            rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            tail = "".join(random.choices(string.ascii_letters + string.digits, k=44))
            svw = "verify_%s_%s" % (rnd, tail)
            cookies["s_v_web_id"] = svw
            _apply_cookies(session, {"s_v_web_id": svw})
        except Exception:
            pass

    return cookies


def _register_ttwid(session):
    """主动向抖音 ttwid 注册接口要一个访客 ttwid。拿不到返回 ''。
    这是公开的访客标识下发接口，不需要登录。"""
    try:
        import json as _json
        body = _json.dumps({
            "region": "cn", "aid": 1768, "needFid": False,
            "service": "www.ixigua.com", "migrate_info": {"ticket": "", "source": "node"},
            "cbUrlProtocol": "https", "union": True,
        })
        r = session.post("https://ttwid.bytedance.com/ttwid/union/register/",
                         data=body,
                         headers={"User-Agent": _SIGN_UA,
                                  "Content-Type": "application/json"},
                         timeout=8)
        # 优先从 Set-Cookie 拿
        try:
            jar = getattr(session, "cookies", None)
            if jar is not None:
                v = jar.get("ttwid")
                if v:
                    return v
        except Exception:
            pass
        # 退一步：从响应体里抠
        txt = getattr(r, "text", "") or ""
        m = re.search(r'"ttwid"\s*:\s*"([^"]+)"', txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


# 一份签名器缓存（造指纹 / 算签名有点开销，复用即可；线程不安全无所谓，最坏多造几个）
_ABOGUS_OK = None       # None=未探测；True/False=能否用 a_bogus（取决于 gmssl）
_ABOGUS_SIGNER = None


def _abogus_available():
    global _ABOGUS_OK, _ABOGUS_SIGNER
    if _ABOGUS_OK is not None:
        return _ABOGUS_OK
    for _try in (0, 1):
        try:
            import dy_abogus  # 需要 gmssl
            fp = dy_abogus.BrowserFingerprintGenerator.generate_fingerprint("Edge")
            _ABOGUS_SIGNER = dy_abogus.ABogus(fp=fp, user_agent=_SIGN_UA)
            _ABOGUS_OK = True
            return True
        except ImportError as e:
            # v147：没有 gmssl 就算不出 a_bogus，抖音的作品接口直接 403（Signature Not Found）→ 自动装一次
            if _try == 0 and "gmssl" in str(e) and _pip_install_gmssl():
                import importlib
                import sys as _sys
                importlib.invalidate_caches()
                _sys.modules.pop("dy_abogus", None)
                continue
            break
        except Exception:
            break
    _ABOGUS_OK = False
    _ABOGUS_SIGNER = None
    return _ABOGUS_OK


def _pip_install_gmssl():
    """v147：列抖音作品要 a_bogus 签名，签名要 gmssl（一个很小的纯 Python 包）：没装就自动装一次。"""
    import subprocess
    import sys as _sys
    print("[抖音] 列作品要用 gmssl（算 a_bogus 签名），自动装一下（只装一次）…", flush=True)
    for extra in ([], ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]):
        try:
            cmd = [_sys.executable, "-m", "pip", "install", "gmssl"] + extra
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if r.returncode != 0 and "externally-managed" in ((r.stderr or "") + (r.stdout or "")):
                r = subprocess.run(cmd + ["--break-system-packages"], capture_output=True, text=True, timeout=240)
            if r.returncode == 0:
                print("[抖音] gmssl 装好了", flush=True)
                return True
        except Exception:
            pass
    print("[抖音] gmssl 没装上（网络问题？），这次先用浏览器列", flush=True)
    return False


def _build_post_query(sec_uid, max_cursor, count, ms_token, webid="", verify_fp="", uifid=""):
    """拼一份和浏览器一致的 aweme/post 查询参数（未签名）。
    verify_fp / fp / uifid 是抖音风控现在校验的关键字段（从真实抓包确认）。"""
    from urllib.parse import urlencode
    vfp = verify_fp or _gen_verify_fp()
    params = {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "sec_user_id": sec_uid,
        "max_cursor": max_cursor,
        "locate_query": "false",
        "show_live_replay_strategy": "1",
        "need_time_list": "1",
        "time_list_query": "0",
        "whale_cut_token": "",
        "cut_version": "1",
        "count": count,
        "publish_video_strategy_type": "2",
        "from_user_page": "1",
        "update_version_code": "170400",
        "pc_client_type": "1",
        "pc_libra_divert": "Windows",
        "support_h265": "1",
        "support_dash": "1",
        "version_code": "170400",
        "version_name": "17.4.0",
        "cookie_enabled": "true",
        "screen_width": "1920",
        "screen_height": "1080",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Chrome",
        "browser_version": "130.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "engine_version": "130.0.0.0",
        "os_name": "Windows",
        "os_version": "10",
        "cpu_core_num": "12",
        "device_memory": "8",
        "platform": "PC",
        "downlink": "10",
        "effective_type": "4g",
        "round_trip_time": "50",
        "uifid": uifid or "",
        "webid": webid or _gen_webid(),
        "verifyFp": vfp,
        "fp": vfp,
        "msToken": ms_token,
    }
    return urlencode(params)


def _sign_post_query(query):
    """给查询串加签名，返回带签名的完整 query。优先 a_bogus，不行用 X-Bogus。"""
    # ① a_bogus（gmssl 在时）
    if _abogus_available():
        try:
            signed, _ab, _ua, _body = _ABOGUS_SIGNER.generate_abogus(query, "")
            return signed
        except Exception:
            pass
    # ② X-Bogus（纯标准库兜底）
    try:
        import dy_xbogus
        full = "%s%s?%s" % (_POST_API_HOST, _POST_API_PATH, query)
        signed_url, _xb, _ua = dy_xbogus.XBogus(_SIGN_UA).build(full)
        # 只取 query 部分（含 &X-Bogus=...）
        return signed_url.split("?", 1)[1]
    except Exception:
        return query


def _norm_post_item(aw):
    """把 aweme/post 接口或 SSR 里的一条作品，规整成 creator_watch 要的
    {vid, url, title, when}（when 为 YYYYMMDD 或空串）。不是有效作品返回 None。"""
    if not isinstance(aw, dict):
        return None
    vid = (aw.get("aweme_id") or aw.get("awemeId") or aw.get("id") or "")
    vid = str(vid).strip()
    if not vid or not vid.isdigit():
        return None
    title = (aw.get("desc") or aw.get("title") or "").strip()
    when = ""
    ct = aw.get("create_time") or aw.get("createTime")
    if ct:
        try:
            import datetime as _dt
            when = _dt.datetime.fromtimestamp(int(ct)).strftime("%Y%m%d")
        except Exception:
            when = ""
    return {"vid": vid, "url": "https://www.douyin.com/video/%s" % vid,
            "title": title, "when": when}


def _extract_sec_uid(text):
    """从一段文本（URL 或 HTML）里抠出 sec_uid（MS4w... 那一长串）。抠不到返回 None。"""
    if not text:
        return None
    m = re.search(r'(?:sec_uid["\']?\s*[=:]\s*["\']?|sec_user_id["\']?\s*[=:]\s*["\']?|/user/|share/user/)(MS4w[\w\-]+)', text)
    if m:
        return m.group(1)
    m = re.search(r'(MS4w[\w\-]{20,})', text)
    if m:
        return m.group(1)
    return None


def _resolve_sec_uid(url):
    """把用户主页链接（含 v.douyin.com 短链）解析成 sec_uid。
    先直接从链接抠；抠不到就跟随跳转，从落地址 / 跳转链路 / 落地页 HTML 里再抠。
    顺手把落地页 HTML 一并返回（供 HTML 兜底复用，省一次请求）。
    返回 (sec_uid 或 None, html 或 '')。"""
    sec = _extract_sec_uid(url)
    html = ""
    if sec:
        return sec, html
    if not available():
        return None, html
    try:
        s = _session()
        r = s.get(url, headers={"User-Agent": _MOBILE_UA},
                  allow_redirects=True, timeout=10)
        final_url = str(getattr(r, "url", "")) or ""
        html = getattr(r, "text", "") or ""
        sec = _extract_sec_uid(final_url)
        if not sec:
            for h in (getattr(r, "history", None) or []):
                sec = _extract_sec_uid(str(getattr(h, "url", "")))
                if sec:
                    break
        if not sec:
            sec = _extract_sec_uid(html)
    except Exception:
        pass
    return sec, html


def _cookie_header(cookies):
    """把 cookie dict 拼成 Cookie 请求头字符串。"""
    return "; ".join("%s=%s" % (k, v) for k, v in (cookies or {}).items() if v)


def _posts_from_api(session, sec_uid, limit, diag=None):
    """走正式 aweme/post 接口（带签名）拿作品列表，max_cursor 翻页直到够数 / 没有更多。
    返回 (videos, name)；拿不到返回 ([], '')。
    diag：可选的诊断 dict，把每一页的请求结果写进去，便于失败时定位。"""
    try:
        want = int(limit)
    except Exception:
        want = 0
    cap = 1000 if want <= 0 else min(1000, want)
    per = 18 if cap > 18 else cap        # 浏览器一页 18 条
    cookies = _ensure_ttwid(session, sec_uid=sec_uid)
    ms_token = (cookies.get("msToken") or "").strip() or _gen_ms_token()
    webid = (cookies.get("webid") or "").strip() or _gen_webid()
    # verifyFp / fp 用 cookie 里的 s_v_web_id（两者同源）；没有就造一个格式合法的
    verify_fp = (cookies.get("s_v_web_id") or cookies.get("verifyFp") or "").strip() or _gen_verify_fp()
    uifid = (cookies.get("UIFID") or cookies.get("uifid") or "").strip()
    cookie_hdr = _cookie_header(cookies)
    if diag is not None:
        diag["cookies_keys"] = sorted(cookies.keys())
        diag["has_user_cookie"] = bool(_load_user_cookie())
        diag["sign"] = "a_bogus" if _abogus_available() else "X-Bogus"
        diag["has_verify_fp"] = bool(verify_fp)
        diag["pages"] = []

    out, name = [], ""
    cursor = "0"
    seen = set()
    for _page in range(80):              # 80 页 × 18 ≈ 1440，封顶防死循环
        query = _build_post_query(sec_uid, cursor, per, ms_token,
                                  webid=webid, verify_fp=verify_fp, uifid=uifid)
        signed_query = _sign_post_query(query)
        api = "%s%s?%s" % (_POST_API_HOST, _POST_API_PATH, signed_query)
        extra = {"Cookie": cookie_hdr} if cookie_hdr else None
        data, status, raw = _api_get_json_ex(
            session, api,
            referer="https://www.douyin.com/user/%s" % sec_uid,
            user_agent=_SIGN_UA, extra_headers=extra)
        if diag is not None:
            pg = {"cursor": cursor, "http_status": status}
            if isinstance(data, dict):
                pg["status_code"] = data.get("status_code")
                pg["status_msg"] = str(data.get("status_msg") or "")[:120]
                pg["has_more"] = data.get("has_more")
                pg["aweme_list_len"] = len(data.get("aweme_list") or []) if isinstance(data.get("aweme_list"), list) else None
                pg["keys"] = sorted(list(data.keys()))[:20]
            else:
                pg["raw_head"] = (raw or "")[:200]
            diag["pages"].append(pg)
        if not isinstance(data, dict) or not data:
            if diag is not None:
                diag["stop"] = "fail" if out else "none"      # v146：翻页中途没拿到 = 断了
            break
        lst = data.get("aweme_list")
        if not isinstance(lst, list):
            lst = []
        if not lst:
            # 没有作品列表：首页就停（交给上层兜底），翻页途中则正常结束
            if diag is not None:
                diag["stop"] = "fail" if out else "none"
            break
        for aw in lst:
            it = _norm_post_item(aw)
            if not it or it["vid"] in seen:
                continue
            seen.add(it["vid"])
            out.append(it)
            if not name:
                try:
                    name = ((aw.get("author") or {}).get("nickname") or "").strip()
                except Exception:
                    pass
            if diag is not None and not diag.get("aweme_count"):
                try:
                    diag["aweme_count"] = int((aw.get("author") or {}).get("aweme_count") or 0)   # v147
                except Exception:
                    pass
        if cap and len(out) >= cap:
            out = out[:cap]
            if diag is not None:
                diag["stop"] = "cap"
            break
        if not data.get("has_more"):
            if diag is not None:
                diag["stop"] = "end"
            break
        nxt = data.get("max_cursor")
        if nxt in (None, "", 0, "0") or str(nxt) == str(cursor):
            if diag is not None:
                diag["stop"] = "fail"
            break
        cursor = str(nxt)
    return out, name


def _posts_from_html(html, limit):
    """从用户主页 HTML 里的 SSR 注水数据中扒作品列表（接口都挂时的兜底）。
    返回 (videos, name)。结构多变，挨个兜底；扒不到返回 ([], '')。"""
    if not html:
        return [], ""
    try:
        want = int(limit)
    except Exception:
        want = 0
    cap = 1000 if want <= 0 else min(1000, want)

    blobs = []
    import urllib.parse as _up
    for pat in (
        r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*;?\s*</script>",
        r"id=\"RENDER_DATA\"[^>]*>([^<]+)</script>",
        r"<script[^>]*>\s*self\.__pace_f\.push\(\[\d+,\s*\"(.*?)\"\]\)\s*</script>",
    ):
        for m in re.finditer(pat, html, re.S):
            blobs.append(m.group(1))

    name = ""
    out, seen = [], set()

    def _harvest(node):
        if cap and len(out) >= cap:
            return
        if isinstance(node, dict):
            it = _norm_post_item(node)
            if it and it["vid"] not in seen:
                if ("desc" in node) or ("video" in node) or ("statistics" in node) or ("create_time" in node):
                    seen.add(it["vid"])
                    out.append(it)
            for v in node.values():
                _harvest(v)
        elif isinstance(node, list):
            for v in node:
                _harvest(v)

    for raw in blobs:
        data = None
        for transform in (
            lambda x: x,
            lambda x: _up.unquote(x),
            lambda x: x.encode("utf-8").decode("unicode_escape"),
        ):
            try:
                data = json.loads(transform(raw))
                break
            except Exception:
                data = None
        if data is None:
            continue
        if not name:
            mm = re.search(r'"nickname"\s*:\s*"([^"]{1,40})"', raw)
            if mm:
                name = mm.group(1).strip()
        try:
            _harvest(data)
        except Exception:
            pass
        if cap and len(out) >= cap:
            break

    return (out[:cap] if cap else out), name


def _write_list_diag(diag):
    """把列作品失败的诊断写到 backend/memory/douyin_list_diag.txt，方便发给开发者定位。"""
    try:
        import os, json as _json, datetime as _dt
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "memory", "douyin_list_diag.txt")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        diag = dict(diag or {})
        diag["time"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(p, "w", encoding="utf-8") as f:
            f.write(_json.dumps(diag, ensure_ascii=False, indent=2))
    except Exception:
        pass


def list_user_posts(url, limit=40):
    """列一个抖音用户主页的作品。带 a_bogus/X-Bogus 签名走正式接口，逐层兜底。
    返回 {ok, videos:[{vid,url,title,when}], name, total, sec_uid, source}；失败 {ok: False, error}。

      url   —— 用户主页链接，支持 v.douyin.com 短链 / www.douyin.com/user/{sec_uid}
                / iesdouyin.com/share/user/...；
      limit —— 想要的条数（<=0 表示尽量全部，内部封顶 ~1000）。

    供 creator_watch._list_douyin 优先调用；这里失败时它再退回 yt-dlp。
    失败时会把诊断写到 memory/douyin_list_diag.txt。"""
    diag = {"url": url, "curl_cffi": available(),
            "abogus": _abogus_available(), "gmssl": _abogus_available()}
    if not available():
        diag["fail"] = "curl_cffi 不可用"
        _write_list_diag(diag)
        return {"ok": False, "error": "curl_cffi 不可用，无法列抖音作品。请点「安装/更新视频依赖」。"}
    sec, html = _resolve_sec_uid(url)
    diag["sec_uid"] = sec or ""
    if not sec:
        diag["fail"] = "没解析到 sec_uid"
        _write_list_diag(diag)
        return {"ok": False, "error": "没解析到用户 sec_uid（主页链接可能失效或被拦）"}

    s = _session()
    # ①②：正式接口（a_bogus 优先，X-Bogus 兜底，都在 _sign_post_query 里处理）
    try:
        videos, name = _posts_from_api(s, sec, limit, diag=diag)
        _short = diag.get("stop") == "fail" or (diag.get("aweme_count") or 0) > len(videos) + 3     # v147
        if videos and _short and cookie_status().get("state") == "ok":
            try:                                   # v146：后面几页没拿到：浏览器（带登录）往下滚着再列一遍
                v2, n2, _why = _posts_via_browser(sec, limit, timeout_s=60, diag=diag)
                diag["browser_retry"] = _why or ("ok:%d" % len(v2))
                if len(v2) > len(videos):
                    return _list_ok(diag, {"ok": True, "videos": v2, "name": name or n2, "total": len(v2),
                                           "sec_uid": sec, "source": "browser"})
            except Exception as e:
                diag["browser_retry_exc"] = str(e)[:120]
        if videos:
            src = "api+abogus" if _abogus_available() else "api+xbogus"
            return _list_ok(diag, {"ok": True, "videos": videos, "name": name, "total": len(videos),
                                   "sec_uid": sec, "source": src})
    except Exception as e:
        diag["api_exc"] = str(e)[:120]

    # ③：用户主页 HTML 注水数据
    if not html:
        try:
            r = s.get("https://www.douyin.com/user/%s" % sec, headers={
                "User-Agent": _SIGN_UA,
                "Referer": "https://www.douyin.com/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }, timeout=12)
            html = getattr(r, "text", "") or ""
        except Exception:
            html = ""
    diag["html_len"] = len(html or "")
    diag["html_has_render"] = bool(html and ("RENDER_DATA" in html or "_ROUTER_DATA" in html or "__pace_f" in html))
    try:
        videos, name = _posts_from_html(html, limit)
        if videos:
            return _list_ok(diag, {"ok": True, "videos": videos, "name": name, "total": len(videos),
                                   "sec_uid": sec, "source": "html"})
    except Exception as e:
        diag["html_exc"] = str(e)[:120]

    # ④：真浏览器兜底（2026-11 抖音给作品列表接口加签名后加的）：后台打开博主主页，
    #    让页面自己请求作品列表，我们只「听」返回的数据
    try:
        videos, name, why = _posts_via_browser(sec, limit, diag=diag)
        diag["browser"] = why or ("ok:%d" % len(videos))
        if videos:
            return _list_ok(diag, {"ok": True, "videos": videos, "name": name, "total": len(videos),
                                   "sec_uid": sec, "source": "browser"})
    except Exception as e:
        diag["browser_exc"] = str(e)[:120]

    diag["fail"] = "接口与主页都没解析到作品"
    _write_list_diag(diag)
    return {"ok": False, "error": "接口与主页都没解析到作品（多半是私密账号 / 风控拦截 / 结构又变了）。"
                                  "可在 backend/memory/douyin_cookie.txt 里粘贴浏览器抖音 Cookie 后重试。",
            "sec_uid": sec}


_BROWSER_USER_PAGE = "https://www.douyin.com/user/%s"


_BROWSER_LIST_LOCK = _thr.Lock()        # v147：登录用的浏览器资料同一时间只能开一个


def _list_ok(diag, res):
    """v147：列成功了也记一份诊断（memory/douyin_list_diag.txt），列少了好查原因；只记 Cookie 的名字，不记内容。"""
    try:
        diag["result"] = "%s:%d" % (res.get("source"), len(res.get("videos") or []))
        if diag.get("browser_note"):
            res["note"] = diag["browser_note"]
        _write_list_diag(diag)
    except Exception:
        pass
    return res


def _posts_via_browser(sec, limit=40, timeout_s=40, diag=None):
    """用本机 Chrome（后台、无界面）打开博主主页，截获页面自己发出的作品列表请求
    （/aweme/v1/web/aweme/post/，页面自己签好名），往下滚动加载更多，直到够数或没有更多。
    v147：登录过（「登录抖音」那个浏览器）就直接用那个浏览器的资料，和你自己在浏览器里看一模一样；
          抖音加载下一页常常要等好几秒，没新作品时多等一会儿、换着法子往下滚（最多 5 分钟）。
    返回 (videos, name, 失败原因)。"""
    import time as _t
    import os as _os
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return [], "", "没装 Playwright（%s）" % str(e)[:40]
    want = 1000 if (not limit or int(limit) <= 0) else int(limit)
    pending, videos, seen = [], [], set()
    name, has_more, stop, rounds, resp_n, captcha, mode = "", True, "", 0, 0, False, ""
    use_prof = False
    try:
        use_prof = (cookie_status().get("state") == "ok" and _os.path.isdir(_login_profile_dir())
                    and _BROWSER_LIST_LOCK.acquire(timeout=1))
    except Exception:
        use_prof = False
    args = ["--disable-blink-features=AutomationControlled", "--mute-audio", "--no-proxy-server"]
    try:
        with sync_playwright() as pw:
            browser, ctx = None, None
            if use_prof:
                for ch in ("chrome", "msedge", None):
                    try:
                        kw = dict(headless=True, args=args, ignore_default_args=["--enable-automation"],
                                  user_agent=_PC_UA, locale="zh-CN", viewport={"width": 1280, "height": 900})
                        if ch:
                            kw["channel"] = ch
                        ctx = pw.chromium.launch_persistent_context(_login_profile_dir(), **kw)
                        mode = "登录用的浏览器"
                        break
                    except Exception:
                        ctx = None
            if ctx is None:
                for ch in ("chrome", "msedge", None):
                    try:
                        kw = dict(headless=True, args=args)
                        if ch:
                            kw["channel"] = ch
                        browser = pw.chromium.launch(**kw)
                        break
                    except Exception:
                        continue
                if browser is None:
                    return [], "", "没有可用的浏览器（Chrome/Edge）"
                ctx = browser.new_context(user_agent=_PC_UA, locale="zh-CN", viewport={"width": 1280, "height": 900})
                ck = _load_user_cookie()
                if ck:
                    ctx.add_cookies([{"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
                                     for k, v in ck.items() if k and v])
                mode = "带 Cookie 的新浏览器" if ck else "没登录的新浏览器"
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.on("response", lambda r: pending.append(r) if "aweme/post" in r.url else None)
                page.goto(_BROWSER_USER_PAGE % sec, wait_until="domcontentloaded", timeout=25000)
                t0 = _t.time()
                end = t0 + timeout_s
                hard_end = t0 + (max(timeout_s, 300) if want > 200 else timeout_s)
                idle = 0
                while len(videos) < want:
                    if _t.time() >= end:
                        stop = "time"
                        break
                    page.wait_for_timeout(1500)
                    rounds += 1
                    got_new = False
                    while pending:
                        r = pending.pop(0)
                        try:
                            data = r.json()
                        except Exception:
                            continue
                        resp_n += 1
                        for aw in (data.get("aweme_list") or []):
                            it = _norm_post_item(aw)
                            if it and it["vid"] not in seen:
                                seen.add(it["vid"])
                                videos.append(it)
                                got_new = True
                                if not name:
                                    name = ((aw.get("author") or {}).get("nickname") or "").strip()
                        if "has_more" in data:
                            has_more = bool(data.get("has_more"))
                    if not has_more:
                        stop = "end"
                        break
                    if got_new:
                        idle = 0
                        end = min(hard_end, max(end, _t.time() + 25))     # 还在出新作品：再多等一会儿
                    else:
                        idle += 1
                    if videos and idle >= 14:                      # 二十来秒都没新的：抖音不给了
                        stop = "stall"
                        break
                    try:                                           # 往下滚，触发加载下一页（几种办法轮着来）
                        if idle and idle % 3 == 0:
                            page.evaluate("() => window.scrollBy(0, -900)")
                            page.wait_for_timeout(400)
                        page.evaluate("""() => {
                            const items = document.querySelectorAll('[data-e2e="user-post-list"] li, [data-e2e="scroll-list"] li');
                            const last = items[items.length - 1];
                            if (last) last.scrollIntoView({block: 'end'});
                            window.scrollTo(0, document.documentElement.scrollHeight);
                        }""")
                        page.mouse.wheel(0, 2400)
                        page.keyboard.press("End")
                    except Exception:
                        pass
                if len(videos) >= want:
                    stop = stop or "want"
                try:
                    captcha = bool(page.evaluate("""() => !!document.querySelector('#captcha_container, .captcha_verify_container, [class*="captcha-verify"], iframe[src*="verify"]')"""))
                except Exception:
                    pass
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass
    finally:
        if use_prof:
            try:
                _BROWSER_LIST_LOCK.release()
            except Exception:
                pass
    if diag is not None:
        diag["browser_run"] = {"mode": mode, "stop": stop, "rounds": rounds, "responses": resp_n,
                               "got": len(videos), "has_more_last": has_more, "captcha": captcha}
        if stop in ("stall", "time") and has_more and videos:
            diag["browser_note"] = ("抖音列到第 %d 个就不再给了%s。可以过一会儿点「刷新」再试；"
                                    "还不行的话，点「登录抖音」重新扫一次码" % (len(videos), "（出现了验证码）" if captcha else ""))
    if not videos:
        return [], name, "浏览器打开主页也没等到作品列表（可能要登录/出验证码；点「登录抖音」扫码登录后再试）"
    return videos[:want], name, ""


def user_name(url):
    """只取这个抖音主页的昵称（作品列不到时也能拿到名字）。失败返回空。"""
    try:
        sec, html = _resolve_sec_uid(url)
        if html:
            mm = re.search(r'"nickname"\s*:\s*"([^"]{1,40})"', html)
            if mm:
                return mm.group(1).strip()
            mm = re.search(r"<title>(.*?)</title>", html, re.S)
            if mm:
                t = re.sub(r"\s*[-–—]\s*抖音.*$", "", mm.group(1)).strip()
                if t and t.lower() not in ("抖音", "douyin"):
                    return t
        if sec:
            s = _session()
            videos, name = _posts_from_api(s, sec, 1)
            if name:
                return name
    except Exception:
        pass
    return ""


# ════════════════════ 自检 / 版本 ════════════════════
# 一条用于自检的公开测试视频。注：任何固定视频都可能被作者删；所以自检会区分
# 「视频没了 / 结构变了 / 网络不通」三种情况，不会把"视频删了"误报成"软件坏了"。
_HEALTH_TEST_URL = "https://www.douyin.com/video/7372484719365164328"


def _has_router_token(html):
    return bool(html) and ("_ROUTER_DATA" in html or "RENDER_DATA" in html)


def health_check(test_url=None):
    """自检抖音提取链路是否正常。返回 {status, detail, title?}。
    status：ok / dep_missing / network_fail / structure_changed / blocked_or_changed。"""
    if not available():
        return {"status": "dep_missing",
                "detail": "没装 curl_cffi，分享页解析用不了。点「安装/更新依赖」即可。"}
    url = test_url or _HEALTH_TEST_URL
    info = resolve(url)
    if info.get("ok"):
        return {"status": "ok", "detail": "解析成功，抖音提取功能正常。",
                "title": info.get("title") or ""}

    # 失败 → 再探一层，区分原因
    aid = _resolve_id(url)
    if not aid:
        return {"status": "network_fail",
                "detail": "连短链跳转都拿不到视频ID，多半是网络不通或被拦。" +
                          ("（%s）" % info.get("error") if info.get("error") else "")}

    # 先探移动端 JSON 接口（现在的主力）：拿到 item 即说明链路其实是通的
    try:
        s = _session()
        item = _resolve_via_api(s, aid)
        if item:
            res = _build_result_from_item(item, aid)
            if res.get("ok"):
                return {"status": "ok", "detail": "解析成功（走接口），抖音提取功能正常。",
                        "title": res.get("title") or ""}
            # 接口给了 item 但没直链 → 八成是这条视频本身被限制
            return {"status": "blocked_or_changed",
                    "detail": "接口能拿到这条视频的信息、但没有可下载直链，"
                              "多半是这条视频被限制（仅粉丝可见/已删/地区限制）。换一条再试。"}
    except Exception:
        pass

    share = "https://www.iesdouyin.com/share/video/%s/" % aid
    try:
        s = _session()
        r = s.get(share, headers={"User-Agent": _MOBILE_UA,
                                  "Referer": "https://www.douyin.com/"}, timeout=20)
        html = getattr(r, "text", "") or ""
        code = getattr(r, "status_code", 0)
    except Exception as e:
        return {"status": "network_fail", "detail": "连不上抖音（接口与分享页都失败）：%s" % e}
    if not html or code >= 400:
        return {"status": "network_fail", "detail": "接口与分享页都返回异常（HTTP %s）。" % code}
    if not _has_router_token(html):
        return {"status": "blocked_or_changed",
                "detail": "接口没数据、分享页里也没有数据块，可能被验证拦截、或结构大改，需要更新解析代码。"}
    return {"status": "structure_changed",
            "detail": "接口取不到、分享页结构也变了，解析逻辑需要更新（把诊断信息发给开发者即可修）。"}


def versions():
    """返回 {curl_cffi, yt_dlp} 当前版本（读不到为 None）。"""
    out = {"curl_cffi": None, "yt_dlp": None}
    try:
        import curl_cffi
        out["curl_cffi"] = getattr(curl_cffi, "__version__", "?")
    except Exception:
        pass
    try:
        import yt_dlp
        out["yt_dlp"] = yt_dlp.version.__version__
    except Exception:
        pass
    return out



# ════════════════ v146：抖音登录（列出博主的全部作品要用）════════════════
# 抖音不登录，只给看主页最新的 18 个左右（主页上「看更多最新作品 → 登录」）。
# 「登录抖音」：弹出一个真的浏览器窗口，你用抖音 App 扫码登录；软件看到登录成功，就把 Cookie 存好、自动关掉窗口。
# Cookie 和这个浏览器的资料都存在这台电脑的私密文件夹里（Windows：%LOCALAPPDATA%\SuperAssistant），
# 不在项目文件夹里，所以不会被 GitHub 备份上传。登录一般 60 天有效，快到期 / 过期了界面会提醒。
import os as _os146
import time as _time146
import shutil as _shutil146
import threading as _th146

_LOGIN = {"state": "idle", "msg": "", "started": 0, "finished": 0, "stop": False}
_LOGIN_URL = "https://www.douyin.com/"
_login_hook = {"setup": None, "headless": False, "timeout": 360}     # 测试用


def _private_dir():
    base = _os146.environ.get("LOCALAPPDATA") or _os146.path.join(_os146.path.expanduser("~"), ".local", "share")
    d = _os146.path.join(base, "SuperAssistant")
    _os146.makedirs(d, exist_ok=True)
    return d


def _private_cookie_file():
    return _os146.path.join(_private_dir(), "douyin_cookie.txt")


def _login_profile_dir():
    return _os146.path.join(_private_dir(), "douyin_login_browser")


def cookie_status(cookies=None):
    """抖音登录 Cookie 的状态：{state: none（没有）/ guest（没登录）/ expired（过期了）/ ok，login_at, expire_at, days_left, where}。"""
    import urllib.parse as _up
    ck = _load_user_cookie() if cookies is None else cookies
    out = {"state": "none", "login_at": "", "expire_at": "", "days_left": None, "where": ""}
    if cookies is None:
        try:
            pp = _private_cookie_file()
            out["where"] = "private" if (_os146.path.exists(pp) and open(pp, encoding="utf-8").read().strip()) else ("project" if ck else "")
        except Exception:
            pass
    if not ck:
        return out
    if not (ck.get("sessionid") or ck.get("sessionid_ss") or ck.get("sid_tt")):
        out["state"] = "guest"
        return out
    out["state"] = "ok"
    try:
        parts = _up.unquote(ck.get("sid_guard") or "").split("|")
        ts, age = int(parts[1]), int(parts[2])
        exp = ts + age
        out["login_at"] = _time146.strftime("%Y-%m-%d", _time146.localtime(ts))
        out["expire_at"] = _time146.strftime("%Y-%m-%d", _time146.localtime(exp))
        out["days_left"] = int((exp - _time146.time()) // 86400)
        if exp < _time146.time():
            out["state"] = "expired"
    except Exception:
        pass
    return out


def _write_private_cookie(ck):
    p = _private_cookie_file()
    if _os146.path.exists(p):
        try:
            _shutil146.copyfile(p, p[:-4] + ".bak.txt")
        except Exception:
            pass
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("; ".join("%s=%s" % (k, v) for k, v in ck.items() if k and v))
    _os146.replace(tmp, p)


def save_cookie_text(raw):
    """你粘贴的 Cookie（浏览器里请求头「Cookie:」后面那一长串）。要带登录信息（sessionid）、没过期才收。"""
    raw = (raw or "").strip()
    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()
    ck = _parse_cookie_str(raw)
    st = cookie_status(ck)
    if st["state"] in ("none", "guest"):
        return {"ok": False, "error": "这串里没有登录信息（sessionid）：要先在浏览器里登录抖音，再复制 Cookie"}
    if st["state"] == "expired":
        return {"ok": False, "error": "这串 Cookie 已经过期了（%s 到期），在浏览器里重新登录一次再复制" % st["expire_at"]}
    _write_private_cookie(ck)
    r = cookie_status()
    r["ok"] = True
    return r


def login_state():
    d = dict(_LOGIN)
    d.pop("stop", None)
    return d


def login_start():
    """打开浏览器窗口让你扫码登录（后台线程，马上返回）。"""
    if _LOGIN["state"] == "running":
        return login_state()
    _LOGIN.update(state="running", msg="正在打开浏览器窗口…", started=_time146.time(), finished=0, stop=False)
    _th146.Thread(target=_login_worker, daemon=True, name="douyin-login").start()
    return login_state()


def login_cancel():
    if _LOGIN["state"] == "running":
        _LOGIN["stop"] = True
    return login_state()


def _login_done(state, msg):
    _LOGIN.update(state=state, msg=msg, finished=_time146.time())
    print("[抖音] " + msg, flush=True)


def _login_worker():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return _login_done("fail", "没装 Playwright，打不开浏览器（%s）" % str(e)[:60])
    urls = ["https://www.douyin.com", "https://douyin.com"]
    try:
        with sync_playwright() as pw:
            ctx, err = None, ""
            for ch in ("chrome", "msedge", None):
                try:
                    kw = dict(headless=bool(_login_hook["headless"]), locale="zh-CN", viewport={"width": 1180, "height": 820},
                              args=["--disable-blink-features=AutomationControlled", "--no-proxy-server"],
                              ignore_default_args=["--enable-automation"])
                    if ch:
                        kw["channel"] = ch
                    ctx = pw.chromium.launch_persistent_context(_login_profile_dir(), **kw)
                    break
                except Exception as e:
                    err = str(e)[:80]
            if ctx is None:
                return _login_done("fail", "没有可用的浏览器（Chrome / Edge）：%s" % err)
            try:
                if _login_hook["setup"]:
                    _login_hook["setup"](ctx)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    page.goto(_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
                _LOGIN["msg"] = "浏览器窗口打开了：在窗口右上角点「登录」，用抖音 App 扫码。登录好这个窗口会自己关掉"
                end, got = _time146.time() + int(_login_hook["timeout"]), None
                while _time146.time() < end:
                    if _LOGIN["stop"]:
                        return _login_done("cancel", "你取消了登录")
                    try:
                        if not ctx.pages:
                            raise RuntimeError("closed")
                        m = {c["name"]: c["value"] for c in ctx.cookies(urls) if c.get("value")}
                    except Exception:
                        return _login_done("closed", "浏览器窗口被关掉了，没登录上")
                    if cookie_status(m)["state"] == "ok":
                        got = m
                        break
                    _time146.sleep(2)
                if not got:
                    return _login_done("timeout", "等了 %d 分钟还没登录上，窗口先关了，可以再点一次「登录抖音」" % (int(_login_hook["timeout"]) // 60))
                _time146.sleep(2.5)                  # 登录后页面还会再写几个 Cookie，等一下再一起存
                try:
                    got = {c["name"]: c["value"] for c in ctx.cookies(urls) if c.get("value")} or got
                except Exception:
                    pass
                _write_private_cookie(got)
                st = cookie_status()
                return _login_done("ok", "抖音登录好了" + ("（有效期到 %s）" % st["expire_at"] if st.get("expire_at") else ""))
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception as e:
        return _login_done("fail", "打开浏览器出错：%s" % str(e)[:100])
