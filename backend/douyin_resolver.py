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


def _api_get_json(session, api_url):
    """GET 一个抖音 JSON 接口，返回解析后的 dict（失败返回 None）。
    超时设得短（8 秒）：接口正常时 1~2 秒就回，迟迟不回基本就是被拦/接口已废，
    早点放手去走下一个候选/兜底，免得一条失败的视频把用户晾上好几分钟。"""
    try:
        r = session.get(api_url, headers={
            "User-Agent": _MOBILE_UA,
            "Referer": "https://www.iesdouyin.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }, timeout=8)
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

    urls = _urls_from_item(item)
    if not urls:
        return {"ok": False, "error": "没拿到可下载的视频直链",
                "title": title, "uploader": uploader, "tags": tags,
                "aweme_id": aid}
    return {"ok": True, "urls": urls, "title": title,
            "uploader": uploader, "tags": tags, "aweme_id": aid}


def resolve(url):
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
        info = resolve(url)
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
