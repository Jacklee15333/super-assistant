"""
video_subtitle.py — 视频「字幕优先」：先抓平台现成字幕，能拿到就跳过下载+本地听写

为什么要它：
  你之前提取视频，固定走「yt-dlp 下音频 → faster-whisper 本地听写」。
  但 B 站、YouTube 很多视频本身就带字幕（人工或自动），平台 API 几秒就能拿到，
  而且字幕**自带每句的时间戳**——又快又省，还能给后面的「截图/跳转原片」打基础。

本模块做的事（都很轻，不引入新的重依赖）：
  · B 站：调官方 player API 直接拉字幕（参考 BiliNote 的做法），只用 requests。
  · YouTube：用 yt-dlp 取字幕轨（不下载视频），yt-dlp 你装视频功能时已经有了。
  · 统一返回一个带时间戳的结构，video_transcribe.extract() 命中就直接用。

返回结构（拿到字幕时）：
  {
    "ok": True,
    "source": "bilibili_subtitle" | "youtube_subtitle",
    "language": "zh-CN",
    "transcript": "分好段的整段文字（用于 AI 总结、和老逻辑兼容）",
    "segments": [ {"start": 0.0, "end": 2.3, "text": "这一句"}, ... ],
    "title": "视频标题（可能为空，拿不到就交给下载流程补）",
    "uploader": "作者（可能为空）",
  }
拿不到字幕时返回 None（让上层回退到「下载音频 + 本地听写」）。

设计原则沿用超能小助：标准库 + 已有依赖优先、全本机、失败要静默兜底、绝不硬崩。
"""

import re
import json
import urllib.request
import urllib.parse


# B 站 player API 要带个浏览器 UA + Referer，否则容易被拦
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ──────────────────────────── 通用小工具 ────────────────────────────

def _http_get_json(url, headers=None, timeout=12):
    """用标准库发 GET，返回解析后的 JSON（dict）。失败返回 None，绝不抛。
    优先用 requests（云端/企业微信那套已经间接带了），没有就退回 urllib。"""
    try:
        import requests  # openai / cryptography 链路通常已带，能用就用
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        return r.json()
    except Exception:
        pass
    # 退回标准库 urllib，确保没装 requests 也能跑
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except Exception:
        return None


def _paragraphize_segments(segments):
    """把带时间戳的字幕段，拼成自然段落文本（给 AI 总结用，风格和老的文字稿一致）。
    简单按「累积到一定长度就分段」，避免一大坨。"""
    paras, cur = [], ""
    for s in segments:
        t = (s.get("text") or "").strip()
        if not t:
            continue
        # 字幕之间补个空格/标点感，读起来不会糊在一起
        cur += t
        if not re.search(r"[。！？!?…；;，,、]$", cur):
            cur += "，"
        if len(cur) >= 110:
            paras.append(cur.strip("，"))
            cur = ""
    if cur.strip("，"):
        paras.append(cur.strip("，"))
    return "\n\n".join(paras)


def _detect_platform(url):
    """粗略判断链接属于哪个平台。只为决定先试哪种字幕，判断错也没关系（会兜底回听写）。"""
    u = (url or "").lower()
    if "bilibili.com" in u or "b23.tv" in u or "/bv" in u or "bvid=" in u:
        return "bilibili"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return ""


# ──────────────────────────── B 站字幕 ────────────────────────────

def _bili_resolve_short(url):
    """b23.tv 短链 → 真实链接（拿 BV 号要用）。失败返回原样。"""
    try:
        import requests
        r = requests.head(url, allow_redirects=True, timeout=10,
                          headers={"User-Agent": _UA})
        return r.url or url
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.geturl() or url
    except Exception:
        return url


def _bili_extract_bvid(url):
    """从各种 B 站链接里抠出 BV 号。"""
    if not url:
        return ""
    if "b23.tv" in url.lower():
        url = _bili_resolve_short(url)
    m = re.search(r"(BV[0-9A-Za-z]+)", url)
    return m.group(1) if m else ""


def _bili_headers(cookie=""):
    h = {"User-Agent": _UA, "Referer": "https://www.bilibili.com"}
    if cookie:
        h["Cookie"] = cookie
    return h


def _bili_get_cid_and_meta(bvid, cookie=""):
    """拿 cid（取字幕要用）顺带把标题/作者带回来。返回 (cid, title, uploader)。"""
    url = "https://api.bilibili.com/x/web-interface/view?bvid=" + bvid
    data = _http_get_json(url, headers=_bili_headers(cookie))
    if not data or data.get("code") != 0:
        return None, "", ""
    d = data.get("data") or {}
    cid = d.get("cid")
    title = (d.get("title") or "").strip()
    uploader = ((d.get("owner") or {}).get("name") or "").strip()
    try:
        return (int(cid) if cid else None), title, uploader
    except Exception:
        return None, title, uploader


def _bili_list_subtitles(bvid, cid, cookie=""):
    """列出该视频的字幕轨。返回 subtitles 列表（可能为空）。"""
    url = ("https://api.bilibili.com/x/player/wbi/v2?bvid=%s&cid=%s"
           % (bvid, cid))
    data = _http_get_json(url, headers=_bili_headers(cookie))
    if not data or data.get("code") != 0:
        return []
    return (((data.get("data") or {}).get("subtitle") or {})
            .get("subtitles") or [])


def _bili_pick_subtitle(subtitles):
    """优先级：人工中文 > AI 中文 > 任意非空（和 BiliNote 一致）。"""
    if not subtitles:
        return None

    def is_zh(s):
        lan = (s.get("lan") or "").lower()
        return lan.startswith("zh") or lan == "ai-zh"

    for s in subtitles:                       # 人工中文（ai_type 为假/0 视为人工）
        if is_zh(s) and not s.get("ai_type"):
            return s
    for s in subtitles:                       # AI 中文
        if is_zh(s):
            return s
    return subtitles[0]                        # 实在不行取第一条


def _bili_fetch_body(subtitle_url, cookie=""):
    """下载某条字幕的 JSON 内容，返回 body 列表（[{from,to,content}, ...]）。"""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    data = _http_get_json(subtitle_url, headers=_bili_headers(cookie))
    if not data:
        return []
    return data.get("body") or []


def fetch_bilibili(url, cookie=""):
    """B 站字幕总入口。拿到返回统一结构，拿不到返回 None。
    cookie：B 站「AI 字幕」常需要登录态（SESSDATA），有就传，没有也先试。"""
    bvid = _bili_extract_bvid(url)
    if not bvid:
        return None
    cid, title, uploader = _bili_get_cid_and_meta(bvid, cookie)
    if not cid:
        return None
    subs = _bili_list_subtitles(bvid, cid, cookie)
    track = _bili_pick_subtitle(subs)
    if not track or not track.get("subtitle_url"):
        # 字幕轨可能存在但没 url（未登录/需要 SESSDATA）→ 交给听写兜底
        return None
    body = _bili_fetch_body(track["subtitle_url"], cookie)
    if not body:
        return None

    segments = []
    for it in body:
        text = (it.get("content") or "").strip()
        if not text:
            continue
        segments.append({
            "start": float(it.get("from", 0) or 0),
            "end": float(it.get("to", 0) or 0),
            "text": text,
        })
    if not segments:
        return None

    return {
        "ok": True,
        "source": "bilibili_subtitle",
        "language": track.get("lan") or "zh",
        "transcript": _paragraphize_segments(segments),
        "segments": segments,
        "title": title,
        "uploader": uploader,
    }


# ──────────────────────────── YouTube 字幕 ────────────────────────────
# 用 yt-dlp 取字幕轨（不下载视频本身）。yt-dlp 在你装视频功能时已经有了，
# 所以不引入 youtube-transcript-api 这种新依赖。

def _yt_parse_timed_json3(raw_text):
    """解析 yt-dlp 拿到的 json3 字幕（YouTube 的结构），返回带时间戳的段。"""
    try:
        data = json.loads(raw_text)
    except Exception:
        return []
    segments = []
    for ev in (data.get("events") or []):
        segs = ev.get("segs") or []
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if not text or text == "\n":
            continue
        start = float(ev.get("tStartMs", 0) or 0) / 1000.0
        dur = float(ev.get("dDurationMs", 0) or 0) / 1000.0
        segments.append({"start": start, "end": start + dur, "text": text})
    return segments


def _yt_parse_vtt(raw_text):
    """兜底解析 WebVTT 字幕（拿不到 json3 时）。返回带时间戳的段。"""
    segments = []
    blocks = re.split(r"\n\n+", raw_text)
    ts_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")
    for b in blocks:
        m = ts_re.search(b)
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        # 时间行之后的才是文字；去掉 VTT 行内标签
        lines = b.splitlines()
        text_lines = []
        seen_ts = False
        for ln in lines:
            if ts_re.search(ln):
                seen_ts = True
                continue
            if seen_ts:
                clean = re.sub(r"<[^>]+>", "", ln).strip()
                if clean:
                    text_lines.append(clean)
        text = " ".join(text_lines).strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def fetch_youtube(url):
    """YouTube 字幕总入口（用 yt-dlp 取轨，不下载视频）。拿不到返回 None。"""
    try:
        import yt_dlp
    except Exception:
        return None  # 没装 yt-dlp，交给听写流程（其实也需要它，统一在那边报）

    # 优先中文，其次英文/日文；人工和自动都接受
    want_langs = ["zh-Hans", "zh-CN", "zh", "zh-TW", "en", "en-US", "ja"]
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": want_langs,
        "nocheckcertificate": True,
        "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    title = (info.get("title") or "").strip()
    uploader = (info.get("uploader") or info.get("channel") or "").strip()

    # 字幕轨：人工(subtitles) 优先，没有再用自动(automatic_captions)
    subs = info.get("subtitles") or {}
    autos = info.get("automatic_captions") or {}

    def pick_lang(track_map):
        for lang in want_langs:
            if lang in track_map and track_map[lang]:
                return lang, track_map[lang]
        # 想要的语言都没有，取任意一条
        for lang, tracks in track_map.items():
            if tracks:
                return lang, tracks
        return None, None

    lang, tracks = pick_lang(subs)
    if not tracks:
        lang, tracks = pick_lang(autos)
    if not tracks:
        return None

    # 在该语言的多种格式里，挑 json3（带时间戳最稳），没有再挑 vtt
    chosen = None
    for fmt_pref in ("json3", "srv3", "vtt"):
        for t in tracks:
            if t.get("ext") == fmt_pref and t.get("url"):
                chosen = (fmt_pref, t["url"])
                break
        if chosen:
            break
    if not chosen:
        # 实在没有偏好格式，拿第一条带 url 的
        for t in tracks:
            if t.get("url"):
                chosen = (t.get("ext") or "vtt", t["url"])
                break
    if not chosen:
        return None

    fmt, sub_url = chosen
    # 下载这条字幕的原文（标准库即可）
    raw_text = ""
    try:
        import requests
        raw_text = requests.get(sub_url, timeout=20,
                                headers={"User-Agent": _UA}).text
    except Exception:
        try:
            req = urllib.request.Request(sub_url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw_text = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return None
    if not raw_text:
        return None

    if fmt in ("json3", "srv3"):
        segments = _yt_parse_timed_json3(raw_text)
        if not segments:                      # 偶尔 srv3 不是 json，退 VTT 试试
            segments = _yt_parse_vtt(raw_text)
    else:
        segments = _yt_parse_vtt(raw_text)
    if not segments:
        return None

    return {
        "ok": True,
        "source": "youtube_subtitle",
        "language": lang or "zh",
        "transcript": _paragraphize_segments(segments),
        "segments": segments,
        "title": title,
        "uploader": uploader,
    }


# ──────────────────────────── 总入口 ────────────────────────────

def try_fetch_subtitle(url, bili_cookie=""):
    """
    统一入口：根据链接平台，先试平台字幕。
    拿到 → 返回带时间戳的统一结构；拿不到/不支持 → 返回 None（上层回退到本地听写）。

    全程 try 包裹，任何异常都安静返回 None，绝不影响主流程。
    bili_cookie：可选，B 站登录态（SESSDATA），用于拿「AI 字幕」。
    """
    try:
        platform = _detect_platform(url)
        if platform == "bilibili":
            return fetch_bilibili(url, cookie=bili_cookie)
        if platform == "youtube":
            return fetch_youtube(url)
        # 其它平台（抖音/快手等）暂不抓字幕，直接交给听写流程
        return None
    except Exception:
        return None


def detect_subtitle(url, bili_cookie=""):
    """
    轻量检测：这个链接有没有平台字幕。**只判断有没有，不下载字幕正文**，尽量快。
    给前端「提取前先问用户」用：有字幕才弹「只用字幕 / 字幕+听写」选择。

    返回 {"has": bool, "platform": str, "source": str, "lang": str}。
    任何异常都返回 has=False（当作没字幕，回退听写），绝不抛。
    """
    result = {"has": False, "platform": "", "source": "", "lang": ""}
    try:
        platform = _detect_platform(url)
        result["platform"] = platform
        if platform == "bilibili":
            bvid = _bili_extract_bvid(url)
            if not bvid:
                return result
            cid, _title, _up = _bili_get_cid_and_meta(bvid, bili_cookie)
            if not cid:
                return result
            subs = _bili_list_subtitles(bvid, cid, bili_cookie)
            track = _bili_pick_subtitle(subs)
            # 有轨且带 subtitle_url 才算「真能拿到」
            if track and track.get("subtitle_url"):
                result["has"] = True
                result["source"] = "bilibili_subtitle"
                result["lang"] = track.get("lan") or "zh"
            return result
        if platform == "youtube":
            # 用 yt-dlp 只取元信息（skip_download），看有没有字幕轨，不下正文
            try:
                import yt_dlp
            except Exception:
                return result
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
                    "skip_download": True, "nocheckcertificate": True,
                    "socket_timeout": 30}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception:
                return result
            subs = info.get("subtitles") or {}
            autos = info.get("automatic_captions") or {}
            if subs or autos:
                result["has"] = True
                result["source"] = "youtube_subtitle"
                # 报个语言（优先人工轨的第一个）
                pool = subs or autos
                for lang in ("zh-Hans", "zh-CN", "zh", "en"):
                    if lang in pool:
                        result["lang"] = lang
                        break
                if not result["lang"] and pool:
                    result["lang"] = next(iter(pool.keys()), "")
            return result
        # 其它平台不检测字幕
        return result
    except Exception:
        return result
