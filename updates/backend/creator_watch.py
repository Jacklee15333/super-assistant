# -*- coding: utf-8 -*-
"""
creator_watch.py — 关注博主主页监控

做的事：
  1) 维护一份「关注的博主」清单（抖音 / B站 / YouTube，每个就是一个主页链接）；
  2) 定时（默认每天某个钟点）或手动「扫一遍」每个博主的主页，列出他最近发的视频；
  3) 和上次的「已见过」快照对比，只把**新出现**的视频攒成一份「本次新增」待办清单；
  4) 用户在界面里勾选要哪些 → 交给视频提取队列批量转写（入队这步在 server.py 做）。

设计取舍（和分析里说的一致）：
  · 列「某博主最近视频」按平台难度差别很大：
      - YouTube：最稳，用 yt-dlp 扁平列频道视频（要走代理，和单条提取同一回事）；
      - B站：稳，用 yt-dlp 扁平列 UP 主投稿；
      - 抖音：最难（作品列表要签名），这里**尽力而为**——先试 yt-dlp，
              拿不到就如实报错，让用户把视频链接手动贴到「视频」页，绝不假装成功。
  · 第一次扫某个博主：只记快照、不报新增（避免把历史作品一次性灌一屏），
    第二次起才报真正的新视频。和「嗅探」的快照逻辑一致。
  · 调度不依赖心跳进程：本模块自带一个轻量后台线程（boot_scheduler），
    server 启动时拉起，保证在打包后的桌面端也能每天自动扫。
"""

import os
import re
import json
import time
import threading
import datetime
from pathlib import Path

# 数据文件：和其它记忆放一起
_DIR = Path(__file__).resolve().parent / "memory"
_STORE = _DIR / "creator_watch.json"

_LOCK = threading.RLock()
_MAX_CREATORS = 50          # 最多盯多少个博主
_MAX_FINDINGS = 300         # 待办清单最多留多少条（超了丢最旧的）
_DEFAULT_PER_SCAN = 15      # 每个博主每次最多取最近多少条

# 扫描运行状态（给前端显示「扫描中…」）
# log: 批量扫描的逐博主明细，每条 {name, ok, new_count, error, ts}
_scan_state = {"running": False, "last": "", "started": 0.0, "progress": "", "current": "", "log": []}

# YouTube 较老视频（RSS 没覆盖）逐条精确补日期时，单次最多补多少条。
# RSS 覆盖最近 ~15 条；这个再往前多补一些，覆盖到「最近7/30天」筛选所需的范围。
# 设太大每次扫描会慢（每条要单独请求一次 yt-dlp）；25 条是速度与覆盖的平衡。
_YT_DATE_PROBE_MAX = 25


# ──────────────────────────── 工具 ────────────────────────────
def _now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _today():
    return datetime.date.today().isoformat()


def _new_id():
    return "cw" + str(int(time.time() * 1000)) + str(os.getpid() % 1000)


import re as _re_err

_ANSI_RE = _re_err.compile(r"\x1b\[[0-9;]*[A-Za-z]|\[[0-9;]{1,8}m")


def _clean_err(e):
    """把 yt-dlp 等返回的错误整理成人能看懂的一句话：
    去掉终端颜色码（之前界面上显示成「0[0;31…」）、ERROR 前缀，常见原因翻成中文提示。"""
    t = _ANSI_RE.sub("", str(e or "")).replace("\x1b", "").strip()
    t = _re_err.sub(r"^0?(ERROR|WARNING):\s*", "", t)
    low = t.lower()
    hint = ""
    if "sign in to confirm" in low or "not a bot" in low:
        hint = "YouTube 要求人机验证：当前代理/IP 被风控。换个代理节点，或点「视频」页「安装/更新依赖」升级 yt-dlp 再试"
    elif "429" in low or "too many requests" in low:
        hint = "请求太频繁被限流，过一会儿再扫"
    elif "timed out" in low or "timeout" in low or "unable to connect" in low or "connection" in low \
            or "getaddrinfo" in low or "proxy" in low:
        hint = "网络连不上（YouTube 需要在「设置 → 联网与代理」配好代理）"
    elif "unsupported url" in low:
        hint = "这个链接格式不支持，请填博主主页链接"
    elif "fresh cookies" in low or "cookies" in low:
        hint = "平台要求 Cookie / 登录，暂时列不到作品"
    elif "does not have a videos tab" in low or "no videos" in low:
        hint = "这个频道没有公开视频"
    elif "private" in low or "unavailable" in low or "removed" in low:
        hint = "主页不可访问（私密/已删除/地区限制）"
    t = t[:160]
    return ("%s（%s）" % (hint, t)) if hint else t


class _SilentLogger:
    """喂给 yt-dlp 的哑日志器：吞掉它往控制台刷的 ERROR/WARNING，
    避免「Unsupported URL」之类噪音刷屏。真正的失败我们靠异常/返回值判断。"""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _proxy():
    """读用户配置的代理（设置→联网与代理）。没配返回空。"""
    try:
        import web_tools
        return web_tools._read_proxy() or ""
    except Exception:
        return ""


# ──────────────────────────── 存取 ────────────────────────────
def _default_store():
    return {
        "config": {"auto": False, "hour": 9, "per_scan": _DEFAULT_PER_SCAN},
        "last_scan_date": "",
        "creators": [],
        "findings": [],
        # 改动4（秒开）：每个博主上一次成功列到的视频，持久化存这里。
        # 点开博主时先把这份缓存「秒回」给界面显示，再在后台联网刷新。
        # key = creator id，值 = {videos:[...], total, platform_label, title, ts(本地时间字符串)}
        "video_cache": {},
        # 标题译文表：英文原文 → 中文。翻译成功后回存，下次直接显示中文、不再重翻。
        "title_zh_map": {},
        # 已提取记录：哪些视频已经送进过「视频内容提取」队列。
        # key = "creator_id|vid"（creator_id 为空时退化成 "|vid"，再退化用 url）。
        # 值 = {"creator_id":..., "vid":..., "url":..., "title":..., "at": 本地时间字符串}。
        # 作用：嗅探/汇总里再次出现同一视频时，标「已提取」并跳过，不重复送队列。
        "extracted": {},
    }


def _load():
    with _LOCK:
        try:
            if _STORE.exists():
                d = json.loads(_STORE.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    base = _default_store()
                    base.update(d)
                    base["config"] = {**_default_store()["config"],
                                      **(d.get("config") or {})}
                    return base
        except Exception:
            pass
        return _default_store()


def _save(store):
    with _LOCK:
        try:
            _DIR.mkdir(parents=True, exist_ok=True)
            _STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        except Exception:
            pass


# ──────────────────────────── 配置 ────────────────────────────
def get_config():
    return _load().get("config", _default_store()["config"])


def save_config(patch):
    store = _load()
    cfg = store.get("config") or {}
    patch = patch or {}
    if "auto" in patch:
        cfg["auto"] = bool(patch["auto"])
    if "hour" in patch:
        try:
            cfg["hour"] = max(0, min(23, int(patch["hour"])))
        except Exception:
            pass
    if "per_scan" in patch:
        try:
            cfg["per_scan"] = max(1, min(50, int(patch["per_scan"])))
        except Exception:
            pass
    store["config"] = cfg
    _save(store)
    return cfg


# ──────────────────────────── 博主清单 ────────────────────────────
def _detect_platform(url):
    u = (url or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "bilibili.com" in u or "b23.tv" in u or "space.bilibili" in u:
        return "bilibili"
    if "douyin.com" in u or "iesdouyin" in u or "v.douyin" in u:
        return "douyin"
    if "x.com/" in u or "twitter.com/" in u:
        return "x"
    return ""


_PLATFORM_LABEL = {"youtube": "YouTube", "bilibili": "B站", "douyin": "抖音", "x": "X"}

# 这些平台抓内容需要登录 Cookie；前端添加时应弹框让用户粘 Cookie。
_LOGIN_REQUIRED_PLATFORMS = {"x"}

# 这些是「还没识别出真实昵称」时用的占位名；之后一旦探到真名就替换掉。
_GENERIC_TITLES = {"", "YouTube博主", "B站博主", "抖音博主", "X博主", "博主"}


def _is_generic_title(t):
    return (t or "").strip() in _GENERIC_TITLES


def _public_creator(c):
    """给前端用的精简版（不带庞大的 known_ids）。"""
    return {
        "id": c.get("id"),
        "platform": c.get("platform"),
        "platform_label": _PLATFORM_LABEL.get(c.get("platform"), c.get("platform") or "?"),
        "title": c.get("title") or "",
        "url": c.get("url") or "",
        "enabled": bool(c.get("enabled", True)),
        "last_checked": c.get("last_checked") or "",
        "last_count": int(c.get("last_count") or 0),
        "known": len(c.get("known_ids") or []),
        "last_error": _clean_err(c.get("last_error")) if c.get("last_error") else "",
    }


def list_creators():
    store = _load()
    return [_public_creator(c) for c in store.get("creators", [])]


def add_creator(url, platform="auto", title=""):
    url = (url or "").strip()
    title = (title or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "message": "主页链接要以 http:// 或 https:// 开头"}
    plat = platform if platform in _PLATFORM_LABEL else _detect_platform(url)
    if not plat:
        return {"ok": False, "message": "认不出这是哪个平台的主页（支持抖音 / B站 / YouTube / X）"}
    store = _load()
    creators = store.get("creators", [])
    if any((c.get("url") or "").strip() == url for c in creators):
        return {"ok": False, "message": "这个主页已经在清单里了"}
    if len(creators) >= _MAX_CREATORS:
        return {"ok": False, "message": f"最多盯 {_MAX_CREATORS} 个博主"}
    detected = ""
    if not title:
        # 用户没填备注名 → 自动识别博主昵称（best-effort，识别不到再用占位名）
        try:
            detected = detect_name(plat, url)
        except Exception:
            detected = ""
        title = detected or (_PLATFORM_LABEL.get(plat, "") + "博主")
    creators.append({
        "id": _new_id(), "platform": plat, "title": title, "url": url,
        "enabled": True, "added": _now_iso(), "last_checked": "",
        "last_count": 0, "known_ids": [], "last_error": "",
    })
    store["creators"] = creators
    _save(store)
    return {"ok": True, "title": title, "detected": bool(detected)}


def delete_creator(cid):
    store = _load()
    store["creators"] = [c for c in store.get("creators", []) if c.get("id") != cid]
    # 一并清掉它名下还没处理的待办
    store["findings"] = [f for f in store.get("findings", []) if f.get("creator_id") != cid]
    _save(store)
    return {"ok": True}


def toggle_creator(cid, enabled):
    store = _load()
    for c in store.get("creators", []):
        if c.get("id") == cid:
            c["enabled"] = bool(enabled)
            break
    _save(store)
    return {"ok": True}


def rename_creator(cid, title):
    store = _load()
    for c in store.get("creators", []):
        if c.get("id") == cid:
            c["title"] = (title or "").strip() or c.get("title")
            break
    _save(store)
    return {"ok": True}


# ──────────────────────────── 列「最近视频」 ────────────────────────────
def _entry_when(e):
    """从 yt-dlp 扁平条目里尽量抠出发布日期，统一成 YYYYMMDD 字符串；抠不到返回空串。
    扁平列频道时 upload_date 经常缺失，这里再尝试 timestamp / release_timestamp。"""
    if not isinstance(e, dict):
        return ""
    ud = e.get("upload_date")
    if ud and re.match(r"^\d{8}$", str(ud)):
        return str(ud)
    for k in ("timestamp", "release_timestamp"):
        ts = e.get(k)
        if ts:
            try:
                return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y%m%d")
            except Exception:
                pass
    return ""


def _clean_channel_name(name, platform):
    """清理频道名里的常见后缀，得到干净的博主名。"""
    n = (name or "").strip()
    if not n:
        return ""
    n = re.sub(r"\s*[-–—]\s*(Videos|视频)\s*$", "", n, flags=re.I)
    n = re.sub(r"(的(投稿|视频|主页|个人空间))\s*$", "", n)
    n = re.sub(r"\s*[-–—]\s*(抖音|哔哩哔哩|bilibili|YouTube).*$", "", n, flags=re.I)
    return n.strip()


def _ytdlp_list(target_url, limit, use_proxy, platform=""):
    """用 yt-dlp 扁平列出频道/合集页（不下载）。
    返回 {name, channel_id, count, entries}。limit<=0 表示「全部」（内部封顶 1000 条）。"""
    import yt_dlp
    opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True, "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 30, "logger": _SilentLogger(),
        "no_color": True,
    }
    try:
        lim = int(limit)
    except Exception:
        lim = 0
    opts["playlistend"] = (1000 if lim <= 0 else min(1000, lim))
    if use_proxy:
        p = _proxy()
        if p:
            opts["proxy"] = p
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target_url, download=False)
    if not info:
        return {"name": "", "channel_id": "", "count": 0, "entries": []}
    name = (info.get("channel") or info.get("uploader")
            or info.get("playlist_uploader") or info.get("title") or "")
    cid = (info.get("channel_id") or info.get("uploader_id") or "")
    try:
        count = int(info.get("playlist_count") or 0)
    except Exception:
        count = 0
    return {"name": _clean_channel_name(name, platform), "channel_id": cid,
            "count": count, "entries": (info.get("entries") or [])}


def _norm_youtube_channel(url):
    """把各种 YouTube 频道写法都归一到 .../videos（拿最新上传）。"""
    u = url.strip().split("?")[0].rstrip("/")
    # 已经指向 videos / streams / shorts 就别再加
    if re.search(r"/(videos|streams|shorts|featured)$", u):
        return u
    m = re.search(r"(youtube\.com/(?:@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+))", u)
    if m:
        return "https://www." + m.group(1) + "/videos"
    return url  # watch 链接等交给 yt-dlp 自己处理


def _resolve_youtube_channel_id(url, flat_cid=""):
    """尽量拿到 YouTube 频道的真实 UC... ID（RSS 接口必须用这个）。
    顺序：① 扁平列表已给的就是 UC 开头 → 直接用；
         ② 否则抓频道页 HTML，从里面找 channelId/externalId/UC... ；抓不到返回空串。
    @handle、/c/、/user/ 这些写法 yt-dlp 给的 uploader_id 经常不是 UC 开头，
    导致原来 RSS 直接被跳过、整页视频都「日期未知」——这里把它补上。"""
    cid = (flat_cid or "").strip()
    if cid.startswith("UC"):
        return cid
    try:
        import web_tools
        page = web_tools._fetch(url, timeout=15, use_proxy=bool(_proxy()))
    except Exception:
        page = ""
    if page:
        for pat in (r'"channelId":"(UC[\w-]{20,})"',
                    r'"externalId":"(UC[\w-]{20,})"',
                    r'<meta itemprop="channelId" content="(UC[\w-]{20,})"',
                    r'channel_id=(UC[\w-]{20,})',
                    r'/channel/(UC[\w-]{20,})'):
            m = re.search(pat, page)
            if m:
                return m.group(1)
    return ""


def _youtube_rss_dates(channel_id, timeout=12):
    """用 YouTube 频道 RSS 拿最近 ~15 条视频的真实发布日期。返回 {video_id: 'YYYYMMDD'}。
    扁平列频道本身拿不到发布日期，RSS 能补上最近视频的日期，让「最近7/30天」筛选可用。"""
    cid = (channel_id or "").strip()
    if not cid.startswith("UC"):
        return {}
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + cid
    try:
        import web_tools
        xml = web_tools._fetch(url, timeout=timeout, use_proxy=bool(_proxy()))
    except Exception:
        return {}
    out = {}
    for m in re.finditer(r"<entry>(.*?)</entry>", xml or "", re.S):
        blk = m.group(1)
        vm = re.search(r"<yt:videoId>([\w-]+)</yt:videoId>", blk)
        dm = re.search(r"<published>(\d{4})-(\d{2})-(\d{2})", blk)
        if vm and dm:
            out[vm.group(1)] = dm.group(1) + dm.group(2) + dm.group(3)
    return out


def _youtube_video_date(vid_or_url, timeout=20):
    """单条视频精确取发布日期：yt-dlp 拿单视频 info 的 upload_date（YYYYMMDD）。
    用于 RSS 没覆盖到的较老视频。失败返回空串。"""
    try:
        import yt_dlp
        u = vid_or_url
        if not str(u).startswith("http"):
            u = "https://www.youtube.com/watch?v=" + str(u)
        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "nocheckcertificate": True, "socket_timeout": timeout,
            "logger": _SilentLogger(), "playlist_items": "0",
        }
        p = _proxy()
        if p:
            opts["proxy"] = p
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(u, download=False)
        if not info:
            return ""
        ud = info.get("upload_date") or info.get("release_date") or ""
        if ud and re.match(r"^\d{8}$", str(ud)):
            return str(ud)
        for k in ("timestamp", "release_timestamp"):
            ts = info.get(k)
            if ts:
                try:
                    return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y%m%d")
                except Exception:
                    pass
    except Exception:
        pass
    return ""


def _list_youtube(url, limit):
    target = _norm_youtube_channel(url)
    data = _ytdlp_list(target, limit, use_proxy=True, platform="youtube")
    entries = data["entries"]
    author = data.get("name", "")   # YouTube 作者就是频道名
    # 只有真在列视频时才去补日期；名字探测（limit=1）不必多打请求
    rss = {}
    real_cid = ""
    if len(entries) > 1:
        # ① 先把真实 UC 频道 ID 拿稳（uploader_id 经常是 @handle，不是 UC，会让 RSS 失效）
        real_cid = _resolve_youtube_channel_id(target, data.get("channel_id"))
        rss = _youtube_rss_dates(real_cid) if real_cid else {}

    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        vid = e.get("id") or ""
        link = e.get("url") or (("https://www.youtube.com/watch?v=" + vid) if vid else "")
        if not vid and link:
            mm = re.search(r"v=([\w-]{6,})", link)
            vid = mm.group(1) if mm else link
        if not vid:
            continue
        # 日期来源优先级：扁平条目自带 > RSS（最近~15条）
        when = _entry_when(e) or rss.get(str(vid), "")
        # 作者：条目自带 uploader/channel，没有就用频道名兜底
        up = (e.get("uploader") or e.get("channel") or "").strip() or author
        out.append({"vid": str(vid), "url": link,
                    "title": (e.get("title") or "").strip(),
                    "when": when, "uploader": up})

    # ② RSS 没覆盖到的视频（较老的）逐条精确补日期。为避免一次性打太多请求，
    #    最多补 _YT_DATE_PROBE_MAX 条（按列表顺序，通常就是最新那些用户最关心的）。
    need = [v for v in out if not v.get("when")]
    if need:
        probed = 0
        for v in need:
            if probed >= _YT_DATE_PROBE_MAX:
                break
            d = _youtube_video_date(v.get("url") or v.get("vid"))
            if d:
                v["when"] = d
            probed += 1

    return {"name": author, "videos": out,
            "total": data.get("count") or len(out)}


def _norm_bili_space(url):
    """B站：从主页链接抠出 UP 主 mid，归一到投稿列表页。"""
    m = re.search(r"space\.bilibili\.com/(\d+)", url)
    if m:
        return "https://space.bilibili.com/%s/video" % m.group(1)
    return url


def _list_bilibili(url, limit):
    target = _norm_bili_space(url)
    data = _ytdlp_list(target, limit, use_proxy=True, platform="bilibili")
    entries = data["entries"]
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        vid = e.get("id") or ""
        link = e.get("url") or ""
        if not link and vid:
            link = "https://www.bilibili.com/video/%s" % vid
        if not vid and link:
            mm = re.search(r"(BV[0-9A-Za-z]+)", link)
            vid = mm.group(1) if mm else link
        if not vid:
            continue
        out.append({"vid": str(vid), "url": link,
                    "title": (e.get("title") or "").strip(),
                    "when": _entry_when(e)})
    return {"name": data.get("name", ""), "videos": out,
            "total": data.get("count") or len(out)}


def _douyin_name_from_page(url):
    """从抖音用户主页 HTML 里尽量抠出昵称（作品列表取不到时也能拿到名字）。失败返回空。"""
    # 先走 douyin_resolver 的新逻辑（短链跟随 + sec_uid + 接口/HTML 多重兜底），更稳
    try:
        import douyin_resolver
        if hasattr(douyin_resolver, "user_name"):
            nm = douyin_resolver.user_name(url)
            if nm:
                return nm
    except Exception:
        pass
    # 退回老办法：直接爬一次主页 HTML 从 <title> / nickname 抠
    try:
        import douyin_resolver
        s = douyin_resolver._session()
        r = s.get(url, allow_redirects=True, timeout=8)
        html = getattr(r, "text", "") or ""
        # 优先用页面 <title>，形如「昵称 - 抖音」「昵称的主页 - 抖音」
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            t = _clean_channel_name(m.group(1), "douyin")
            if t and t.lower() not in ("抖音", "douyin"):
                return t
        # 退而求其次：从内嵌 JSON 里找 nickname
        m = re.search(r'"nickname"\s*:\s*"([^"]{1,40})"', html)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def _list_douyin(url, limit):
    """抖音作品列表：尽力而为，多重兜底。

    取数顺序（前一层失败/为空才走后一层）：
      ① douyin_resolver.list_user_posts —— 不需要 a_bogus 签名的两条老路
         （移动端 aweme/post 接口 + 用户主页 SSR 注水数据），现在的主力；
      ② yt-dlp 扁平列 —— 接口都挂了才用（抖音主页 yt-dlp 多半 Unsupported URL，
         但偶尔某些落地形态能解，保留着当最后一手）。
    全失败才抛一个**清楚的错误**，让上层提示用户改用手动贴链接，
    不假装成功、不返回空当作「没有新视频」。"""
    target = url.strip()

    # ── ① 主力：douyin_resolver 无签名两条路 ──
    try:
        import douyin_resolver
        if hasattr(douyin_resolver, "list_user_posts"):
            res = douyin_resolver.list_user_posts(target, limit=limit)
            if res.get("ok") and res.get("videos"):
                vids = res["videos"]
                # 名字：接口/HTML 拿到就用，否则再单独探一次主页昵称
                name = (res.get("name") or "").strip() or _douyin_name_from_page(target)
                return {"name": name, "videos": vids, "total": res.get("total") or len(vids)}
            # 接口/HTML 都没拿到作品 → 记下原因，继续往下试 yt-dlp
            _dy_reason = res.get("error") or "接口与主页都没解析到作品"
        else:
            _dy_reason = "douyin_resolver 版本过旧（没有 list_user_posts）"
    except Exception as e:
        _dy_reason = "解析用户作品出错：%s" % (str(e)[:80])

    # ── 短链先跟随跳转，尽量落到 www.douyin.com/user/{sec_uid}，给 yt-dlp 用 ──
    try:
        if "v.douyin" in target.lower() or "iesdouyin" in target.lower():
            import douyin_resolver
            s = douyin_resolver._session()
            r = s.get(target, allow_redirects=True, timeout=8)
            target = str(getattr(r, "url", "")) or target
    except Exception:
        pass

    # ── ② 兜底：yt-dlp 扁平列 ──
    name, entries = "", []
    try:
        data = _ytdlp_list(target, limit, use_proxy=False, platform="douyin")
        name, entries = data.get("name", ""), data["entries"]
    except Exception:
        raise RuntimeError("抖音作品列表取不到（%s）。抖音主页现在有风控，免登录不一定能列到作品。"
                           "最稳的办法：从浏览器复制一份抖音 Cookie，粘到 backend/memory/douyin_cookie.txt 后重试；"
                           "或先把想要的视频链接手动贴到「视频」页提取。" % str(_dy_reason)[:90])
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        vid = e.get("id") or ""
        link = e.get("url") or ""
        if not link and vid:
            link = "https://www.douyin.com/video/%s" % vid
        if not vid:
            continue
        out.append({"vid": str(vid), "url": link,
                    "title": (e.get("title") or "").strip(),
                    "when": _entry_when(e)})
    if not out:
        raise RuntimeError("抖音作品列表没解析到内容（%s）。最稳的办法：从浏览器复制一份抖音 Cookie，"
                           "粘到 backend/memory/douyin_cookie.txt 后重试；"
                           "或先把想要的视频链接手动贴到「视频」页提取。" % str(_dy_reason)[:90])
    return {"name": name, "videos": out, "total": len(out)}


def list_recent(platform, url, limit=_DEFAULT_PER_SCAN):
    """统一入口：返回 {name, videos:[{vid,url,title,when}]}，最新在前。"""
    plat = platform or _detect_platform(url)
    if plat == "youtube":
        return _list_youtube(url, limit)
    if plat == "bilibili":
        return _list_bilibili(url, limit)
    if plat == "douyin":
        return _list_douyin(url, limit)
    if plat == "x":
        import x_watch
        return x_watch.list_recent(url, limit)
    raise RuntimeError("不支持的平台：%s" % plat)


def detect_name(platform, url):
    """只为「自动识别博主名字」用：尽量快地拿到博主昵称。拿不到返回空串，绝不抛异常。"""
    plat = platform if platform in _PLATFORM_LABEL else _detect_platform(url)
    try:
        if plat == "x":
            import x_watch
            return x_watch.detect_name(url)
        if plat == "douyin":
            # 抖音作品列表常取不到，但主页 HTML 里通常有昵称
            n = _douyin_name_from_page(url)
            if n:
                return n
        data = list_recent(plat, url, 1)   # 只取 1 条，主要为拿频道名
        return (data.get("name") or "").strip()
    except Exception:
        return ""


def list_videos(cid, limit=40):
    """列出某个博主主页最近的视频（只读，不动「已见」快照），供界面挑选提取用。
    返回 {title, platform, platform_label, videos:[{vid,url,title,when,when_human,days_ago}]}。
    列不到（如抖音签名限制）会抛出带说明的异常，由上层 server 捕获并回给前端。"""
    store = _load()
    c = None
    for x in store.get("creators", []):
        if x.get("id") == cid:
            c = x
            break
    if not c:
        raise RuntimeError("找不到这个博主")
    try:
        limit = int(limit)
    except Exception:
        limit = 0
    limit = 0 if limit <= 0 else min(1000, limit)   # 0 = 全部
    data = list_recent(c.get("platform"), c.get("url"), limit)  # 可能抛异常
    vids = data.get("videos", [])
    scanned_name = (data.get("name") or "").strip()
    # 列视频时若发现真实昵称、而当前还是占位名，顺手更新存档
    title_now = c.get("title") or ""
    if scanned_name and _is_generic_title(title_now):
        title_now = scanned_name
        with _LOCK:
            st = _load()
            for x in st.get("creators", []):
                if x.get("id") == cid:
                    x["title"] = scanned_name
                    break
            _save(st)
    today = datetime.date.today()
    # 取全局译文表，给已知标题直接配上中文（免得每次都重翻）
    try:
        tmap = _load().get("title_zh_map") or {}
    except Exception:
        tmap = {}
    out = []
    for v in vids:
        w = (v.get("when") or "").strip()
        human, days = "", None
        if re.match(r"^\d{8}$", w):
            try:
                d = datetime.date(int(w[:4]), int(w[4:6]), int(w[6:8]))
                human = "%04d-%02d-%02d" % (d.year, d.month, d.day)
                days = (today - d).days
            except Exception:
                pass
        vv = dict(v)
        vv["when_human"] = human
        vv["days_ago"] = days
        if not vv.get("title_zh"):
            t = (vv.get("title") or "").strip()
            if t and t in tmap:
                vv["title_zh"] = tmap[t]
        out.append(vv)
    total = data.get("total") or len(out)
    result = {"title": title_now,
              "platform": c.get("platform"),
              "platform_label": _PLATFORM_LABEL.get(c.get("platform"), c.get("platform") or "?"),
              "videos": out, "total": total, "shown": len(out)}
    # X 等平台抓取失败时，把具体原因带回前端（而不是只显示「没列到」）
    if not out and data.get("error"):
        result["empty_reason"] = data.get("error")
    # 改动4（秒开）：联网成功后把这份结果落盘缓存，下次点开先用它秒显示。
    _save_video_cache(cid, result)
    return result


# ──────────────────────────── 视频缓存（秒开）────────────────────────────
def _save_video_cache(cid, result):
    """把某个博主「这次列到的视频」存进持久缓存，供下次点开秒显示。
    只存精简必要字段，避免缓存文件膨胀。
    会保留上一份缓存里已有的中文译文（title_zh），避免每次列视频把翻译冲掉。"""
    if not cid or not result:
        return
    try:
        with _LOCK:
            store = _load()
            cache = store.get("video_cache")
            if not isinstance(cache, dict):
                cache = {}
            # 取出旧缓存里「vid → 中文译文」，新数据沿用，避免翻译丢失
            old = cache.get(cid) or {}
            zh_by_vid = {}
            for v in (old.get("videos") or []):
                if v.get("vid") and v.get("title_zh"):
                    zh_by_vid[str(v.get("vid"))] = v.get("title_zh")
            # 也并入全局译文表（按标题原文存，跨博主复用）
            tmap = store.get("title_zh_map") or {}
            new_videos = []
            for v in (result.get("videos") or []):
                vv = dict(v)
                vid = str(vv.get("vid") or "")
                if not vv.get("title_zh"):
                    if vid and vid in zh_by_vid:
                        vv["title_zh"] = zh_by_vid[vid]
                    else:
                        t = (vv.get("title") or "").strip()
                        if t and t in tmap:
                            vv["title_zh"] = tmap[t]
                new_videos.append(vv)
            cache[cid] = {
                "videos": new_videos,
                "total": result.get("total") or len(new_videos),
                "platform_label": result.get("platform_label") or "",
                "title": result.get("title") or "",
                "ts": _now_iso(),
            }
            # 删掉已不存在博主的缓存，保持干净
            live_ids = {x.get("id") for x in store.get("creators", [])}
            for k in list(cache.keys()):
                if k not in live_ids:
                    cache.pop(k, None)
            store["video_cache"] = cache
            _save(store)
    except Exception:
        pass


def save_translations(pairs):
    """前端翻译成功后回存：把「英文标题 → 中文」存进全局译文表，
    并尽量回填到各博主的视频缓存 + 待办清单里，下次直接显示中文、不再重翻。
    pairs = [{title, zh}] 或 {title: zh}。返回 {ok, saved}。"""
    try:
        # 规整成 dict
        m = {}
        if isinstance(pairs, dict):
            for k, v in pairs.items():
                if k and v:
                    m[str(k).strip()] = str(v).strip()
        else:
            for p in (pairs or []):
                t = (p.get("title") or "").strip()
                z = (p.get("zh") or "").strip()
                if t and z:
                    m[t] = z
        if not m:
            return {"ok": True, "saved": 0}
        with _LOCK:
            store = _load()
            tmap = store.get("title_zh_map")
            if not isinstance(tmap, dict):
                tmap = {}
            tmap.update(m)
            # 控制体积：最多留 3000 条
            if len(tmap) > 3000:
                tmap = dict(list(tmap.items())[-3000:])
            store["title_zh_map"] = tmap
            # 回填视频缓存
            cache = store.get("video_cache") or {}
            for cid, item in cache.items():
                for v in (item.get("videos") or []):
                    if not v.get("title_zh"):
                        t = (v.get("title") or "").strip()
                        if t in m:
                            v["title_zh"] = m[t]
            store["video_cache"] = cache
            # 回填待办清单
            for f in store.get("findings", []):
                if not f.get("title_zh"):
                    t = (f.get("title") or "").strip()
                    if t in m:
                        f["title_zh"] = m[t]
            _save(store)
        return {"ok": True, "saved": len(m)}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def get_cached_videos(cid):
    """读某个博主的持久视频缓存；没有就返回 None。给「秒开」用。"""
    if not cid:
        return None
    try:
        store = _load()
        cache = store.get("video_cache") or {}
        item = cache.get(cid)
        if item and isinstance(item.get("videos"), list):
            return {
                "title": item.get("title") or "",
                "platform_label": item.get("platform_label") or "",
                "videos": item.get("videos") or [],
                "total": item.get("total") or len(item.get("videos") or []),
                "shown": len(item.get("videos") or []),
                "cached": True,
                "cached_at": item.get("ts") or "",
            }
    except Exception:
        pass
    return None


# ──────────────────────────── 扫描 / 去重 ────────────────────────────
def _trim_findings(store):
    f = store.get("findings", [])
    if len(f) > _MAX_FINDINGS:
        store["findings"] = f[-_MAX_FINDINGS:]


def scan_one(cid):
    """扫一个博主：列最近视频，和已见快照对比，新视频进待办清单。
    返回 {id, title, platform, new_count, error}。第一次只记快照、不报新增。"""
    store = _load()
    target = None
    for c in store.get("creators", []):
        if c.get("id") == cid:
            target = c
            break
    if not target:
        return {"id": cid, "error": "找不到这个博主"}

    per = int(get_config().get("per_scan", _DEFAULT_PER_SCAN))
    res = {"id": cid, "title": target.get("title") or "",
           "platform": target.get("platform"), "new_count": 0, "error": ""}
    try:
        data = list_recent(target.get("platform"), target.get("url"), per)
        vids = data.get("videos", [])
        scanned_name = (data.get("name") or "").strip()
    except Exception as e:
        # 出错：只记错误，不动快照（下次还能再试）
        with _LOCK:
            store = _load()
            for c in store.get("creators", []):
                if c.get("id") == cid:
                    c["last_checked"] = _now_iso()
                    c["last_error"] = _clean_err(e)
                    break
            _save(store)
        res["error"] = _clean_err(e)
        return res

    with _LOCK:
        store = _load()
        c = None
        for x in store.get("creators", []):
            if x.get("id") == cid:
                c = x
                break
        if c is None:
            res["error"] = "博主已被删除"
            return res
        # 顺手把真实昵称补上（之前可能是「YouTube博主」这种占位名）
        if scanned_name and _is_generic_title(c.get("title")):
            c["title"] = scanned_name
            res["title"] = scanned_name
        known = set(c.get("known_ids") or [])
        first_time = (not c.get("last_checked")) and (not known)
        cur_ids = [v["vid"] for v in vids]
        new_count = 0
        if not first_time:
            existing_keys = {(f.get("creator_id"), f.get("vid"))
                             for f in store.get("findings", [])}
            for v in vids:
                if v["vid"] in known:
                    continue
                if (cid, v["vid"]) in existing_keys:
                    continue
                store.setdefault("findings", []).append({
                    "creator_id": cid,
                    "creator_title": c.get("title") or "",
                    "platform": c.get("platform"),
                    "vid": v["vid"], "url": v["url"],
                    "title": v.get("title") or "", "when": v.get("when") or "",
                    "uploader": v.get("uploader") or "",
                    "text": v.get("text") or "",   # X 推文全文（视频平台为空）
                    "found_at": _now_iso(),
                })
                new_count += 1
        # 把这次看到的都并进「已见」（首次也并，这样下次只报真正的新）
        merged = list(known) + [i for i in cur_ids if i not in known]
        c["known_ids"] = merged[-400:]      # 防止无限增长
        c["last_checked"] = _now_iso()
        c["last_count"] = len(cur_ids)
        c["last_error"] = ""
        _trim_findings(store)
        _save(store)
        # 取出这个博主的当前名字/平台，给下面写缓存用（用 c["title"]＝博主列表里的备注名）
        _cache_title = c.get("title") or ""
        _cache_plat = c.get("platform")

    # ── 关键修复：扫描时也把列到的视频写进 video_cache ──
    # 原先只有 list_videos（点开某个博主）才落盘缓存，scan_one 不落盘；
    # 导致「批量扫描/扫一遍」发现的新视频，进不了「按时间看全部」(gather_recent 默认只读缓存)。
    # 这里把刚 list_recent 到的 vids 也存一份，扫完即可在「按时间看全部」看到。
    try:
        today = datetime.date.today()
        cache_videos = []
        for v in vids:
            w = (v.get("when") or "").strip()
            human, da = "", None
            if re.match(r"^\d{8}$", w):
                try:
                    d = datetime.date(int(w[:4]), int(w[4:6]), int(w[6:8]))
                    human = "%04d-%02d-%02d" % (d.year, d.month, d.day)
                    da = (today - d).days
                except Exception:
                    pass
            vv = dict(v)
            vv["when_human"] = human
            vv["days_ago"] = da
            cache_videos.append(vv)
        _save_video_cache(cid, {
            "title": _cache_title,
            "platform": _cache_plat,
            "platform_label": _PLATFORM_LABEL.get(_cache_plat, _cache_plat or "?"),
            "videos": cache_videos,
            "total": len(cache_videos),
            "shown": len(cache_videos),
        })
    except Exception:
        pass  # 缓存只是加速用，写失败不影响扫描结果

    res["new_count"] = new_count
    res["first_time"] = bool(first_time)
    return res


def scan_all(only_enabled=True):
    """扫所有（启用的）博主。返回 {ok, scanned:[...], total_new, total_err}。
    扫的过程中把「第几个/共几个/当前是谁」写进 _scan_state，给界面显示批量进度。"""
    store = _load()
    creators = [c for c in store.get("creators", [])
                if (not only_enabled) or c.get("enabled", True)]
    total = len(creators)
    scanned, total_new, total_err = [], 0, 0
    for i, c in enumerate(creators):
        nm = c.get("title") or "博主"
        _scan_state["progress"] = "%d/%d" % (i + 1, total)
        _scan_state["current"] = nm
        _scan_state["last"] = "正在批量扫描 %d/%d：%s…" % (i + 1, total, nm)
        r = scan_one(c.get("id"))
        scanned.append(r)
        total_new += int(r.get("new_count") or 0)
        if r.get("error"):
            total_err += 1
        # 记一条逐博主明细，供前端「批量扫描」明细列表实时展示
        _scan_state["log"].append({
            "name": nm,
            "ok": not r.get("error"),
            "new_count": int(r.get("new_count") or 0),
            "first_time": bool(r.get("first_time")),
            "error": r.get("error") or "",
            "ts": time.time(),
        })
    _scan_state["progress"] = "%d/%d" % (total, total)
    _scan_state["current"] = ""
    return {"ok": True, "scanned": scanned,
            "total_new": total_new, "total_err": total_err}


def scan_all_async():
    """后台扫所有博主，立即返回。前端轮询 get_scan_state（含 progress 进度）。"""
    with _LOCK:
        if _scan_state["running"]:
            return {"ok": False, "message": "正在扫描中，稍候…"}
        _scan_state["running"] = True
        _scan_state["started"] = time.time()
        _scan_state["progress"] = ""
        _scan_state["current"] = ""
        _scan_state["log"] = []
        _scan_state["last"] = "正在批量扫描所有博主…"

    def _run():
        try:
            r = scan_all(only_enabled=True)
            stamp = datetime.datetime.now().strftime("%H:%M")
            if r.get("total_new"):
                _scan_state["last"] = "%s 批量扫描完成：发现 %d 条新视频%s" % (
                    stamp, r["total_new"],
                    ("，%d 个源出错" % r["total_err"]) if r.get("total_err") else "")
            else:
                _scan_state["last"] = "%s 批量扫描完成：暂无新视频%s" % (
                    stamp, ("，%d 个源出错" % r["total_err"]) if r.get("total_err") else "")
        except Exception as e:
            _scan_state["last"] = "扫描出错：%s" % str(e)[:120]
        finally:
            _scan_state["running"] = False
            _scan_state["current"] = ""

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True}


def get_scan_state():
    return dict(_scan_state)


# ──────────────────────────── 待办清单 ────────────────────────────
def get_findings():
    store = _load()
    f = list(store.get("findings", []))
    f.sort(key=lambda x: x.get("found_at") or "", reverse=True)
    # 给已知英文标题配上中文（来自全局译文表），下次打开直接是中文
    tmap = store.get("title_zh_map") or {}
    if tmap:
        for it in f:
            if not it.get("title_zh"):
                t = (it.get("title") or "").strip()
                if t and t in tmap:
                    it["title_zh"] = tmap[t]
    # 标注「已提取」：界面据此显示「已提取」并禁用提取按钮
    _annotate_extracted(f)
    return f


def get_finding_meta(creator_id=None, vid=None, url=""):
    """按 creator_id+vid 或 url 找回一条待办的附加信息（text/platform/uploader/title）。
    供 X 推文「直接存笔记」时取回推文全文用。找不到返回 {}。"""
    store = _load()
    url = (url or "").strip()
    for f in store.get("findings", []):
        if vid is not None and f.get("vid") == vid and (
                creator_id is None or f.get("creator_id") == creator_id):
            return {"text": f.get("text") or "", "platform": f.get("platform") or "",
                    "uploader": f.get("uploader") or "", "title": f.get("title") or ""}
        if url and (f.get("url") or "").strip() == url:
            return {"text": f.get("text") or "", "platform": f.get("platform") or "",
                    "uploader": f.get("uploader") or "", "title": f.get("title") or ""}
    return {}


def remove_findings(keys):
    """从待办里移除若干条（已处理/已忽略）。keys = [{creator_id, vid}] 或 [url,...]。"""
    store = _load()
    rm_pairs, rm_urls = set(), set()
    for k in (keys or []):
        if isinstance(k, dict):
            if k.get("vid") is not None:
                rm_pairs.add((k.get("creator_id"), str(k.get("vid"))))
            if k.get("url"):
                rm_urls.add(k["url"])
        elif isinstance(k, str):
            rm_urls.add(k)
    kept = []
    for f in store.get("findings", []):
        pair = (f.get("creator_id"), str(f.get("vid")))
        if pair in rm_pairs or f.get("url") in rm_urls:
            continue
        kept.append(f)
    store["findings"] = kept
    _save(store)
    return {"ok": True, "remaining": len(kept)}


def clear_findings():
    store = _load()
    store["findings"] = []
    _save(store)
    return {"ok": True}


# ──────────────────────── 已提取记录（去重，避免重复送队列）────────────────────────
def _extract_key(creator_id, vid, url=""):
    """生成「已提取」表的统一键：优先 creator_id|vid；没有 vid 就退用 url。"""
    v = ("" if vid is None else str(vid)).strip()
    if v:
        return (("" if creator_id is None else str(creator_id)) + "|" + v)
    u = (url or "").strip()
    return ("url|" + u) if u else ""


def get_extracted_map():
    """返回 {key: record} 的已提取表（只读副本）。"""
    store = _load()
    m = store.get("extracted")
    return dict(m) if isinstance(m, dict) else {}


def is_extracted(creator_id, vid, url=""):
    """这条视频是否已经送过提取队列。creator_id|vid 命中，或同 url 命中，都算已提取。"""
    m = get_extracted_map()
    if not m:
        return False
    k = _extract_key(creator_id, vid, url)
    if k and k in m:
        return True
    # 兜底：有时同一视频换了渠道拿到的 creator_id 不同，但 url 一样 → 也认为已提取
    u = (url or "").strip()
    if u:
        for rec in m.values():
            if (rec or {}).get("url") == u:
                return True
    return False


def mark_extracted(items):
    """把若干视频记进「已提取」表。items = [{creator_id, vid, url, title?}]。
    返回 {ok, added, total}。同一条重复调用只会更新时间，不会重复占位。"""
    store = _load()
    m = store.get("extracted")
    if not isinstance(m, dict):
        m = {}
    added = 0
    for it in (items or []):
        if not isinstance(it, dict):
            # 允许直接传 url 字符串
            it = {"url": str(it)}
        cid = it.get("creator_id")
        vid = it.get("vid")
        url = (it.get("url") or "").strip()
        k = _extract_key(cid, vid, url)
        if not k:
            continue
        if k not in m:
            added += 1
        m[k] = {
            "creator_id": cid,
            "vid": ("" if vid is None else str(vid)),
            "url": url,
            "title": it.get("title") or "",
            "at": _now_iso(),
        }
    store["extracted"] = m
    _save(store)
    return {"ok": True, "added": added, "total": len(m)}


def unmark_extracted(items):
    """从「已提取」表里删除若干条（想重新提取某些视频时用）。
    items = [{creator_id, vid, url}] 或 [url,...]；items 为空/None 时清空整张表。"""
    store = _load()
    m = store.get("extracted")
    if not isinstance(m, dict):
        return {"ok": True, "removed": 0, "total": 0}
    if not items:
        n = len(m)
        store["extracted"] = {}
        _save(store)
        return {"ok": True, "removed": n, "total": 0}
    rm_keys, rm_urls = set(), set()
    for it in items:
        if isinstance(it, str):
            rm_urls.add(it.strip())
            continue
        if not isinstance(it, dict):
            continue
        k = _extract_key(it.get("creator_id"), it.get("vid"), it.get("url") or "")
        if k:
            rm_keys.add(k)
        if it.get("url"):
            rm_urls.add((it.get("url") or "").strip())
    removed = 0
    for k in list(m.keys()):
        rec = m.get(k) or {}
        if k in rm_keys or (rec.get("url") and rec.get("url") in rm_urls):
            del m[k]
            removed += 1
    store["extracted"] = m
    _save(store)
    return {"ok": True, "removed": removed, "total": len(m)}


def _annotate_extracted(items):
    """给一批 dict（含 creator_id/vid/url）逐条加上 extracted 布尔字段。原地改并返回。"""
    m = get_extracted_map()
    if not items:
        return items
    # 预备一个 url 集合，加速 url 兜底匹配
    url_set = set()
    for rec in m.values():
        u = (rec or {}).get("url")
        if u:
            url_set.add(u)
    for it in items:
        if not isinstance(it, dict):
            continue
        k = _extract_key(it.get("creator_id"), it.get("vid"), it.get("url") or "")
        hit = bool(k and k in m)
        if not hit:
            u = (it.get("url") or "").strip()
            hit = bool(u and u in url_set)
        it["extracted"] = hit
    return items


# ──────────────────────── 多博主近 N 天汇总（新版块）────────────────────────
def _video_days_ago(when):
    """把 yt-dlp 的 when（YYYYMMDD 或空）换算成「距今天数」；算不出返回 None。"""
    w = (when or "").strip()
    if not re.match(r"^\d{8}$", w):
        return None
    try:
        d = datetime.date(int(w[:4]), int(w[4:6]), int(w[6:8]))
        return (datetime.date.today() - d).days
    except Exception:
        return None


def _enrich_dates(vids):
    """给 list_recent 出来的精简视频补 when_human / days_ago（和 list_videos 一致）。"""
    today = datetime.date.today()
    out = []
    for v in (vids or []):
        w = (v.get("when") or "").strip()
        human, da = "", None
        if re.match(r"^\d{8}$", w):
            try:
                d = datetime.date(int(w[:4]), int(w[4:6]), int(w[6:8]))
                human = "%04d-%02d-%02d" % (d.year, d.month, d.day)
                da = (today - d).days
            except Exception:
                pass
        vv = dict(v)
        vv["when_human"] = human
        vv["days_ago"] = da
        out.append(vv)
    return out


def _live_list_one(c, per_creator):
    """只联网列一个博主的视频（纯网络，不碰 store），返回 (cid, result_dict_or_None, error_str)。
    供并发补全 / 联网刷新用。result 形如 list_videos 的精简版（够写缓存 + 汇总）。"""
    cid = c.get("id")
    plat = c.get("platform")
    try:
        data = list_recent(plat, c.get("url"), per_creator)   # 纯网络
        vids = _enrich_dates(data.get("videos") or [])
        result = {
            "title": c.get("title") or "",   # 名字一律用博主列表里的备注名
            "platform": plat,
            "platform_label": _PLATFORM_LABEL.get(plat, plat or "?"),
            "videos": vids,
            "total": data.get("total") or len(vids),
            "shown": len(vids),
        }
        return (cid, result, "")
    except Exception as e:
        return (cid, None, str(e)[:160])


def _live_list_many(creators, per_creator=30, per_timeout=30, max_workers=8):
    """并发联网列多个博主，每个博主最多等 per_timeout 秒；超时/出错就跳过并记错。
    成功的结果会写进 video_cache（串行、加锁，避免并发写冲突）。
    返回 {ok_ids:set, errors:[{title,error}]}。整体耗时≈最慢的一个（受 per_timeout 封顶）。"""
    import concurrent.futures as _cf
    ok_ids = set()
    errors = []
    if not creators:
        return {"ok_ids": ok_ids, "errors": errors}
    results = []   # [(cid, result, err)]
    workers = max(1, min(max_workers, len(creators)))
    with _cf.ThreadPoolExecutor(max_workers=workers) as ex:
        fut_map = {ex.submit(_live_list_one, c, per_creator): c for c in creators}
        for fut in fut_map:
            c = fut_map[fut]
            try:
                cid, result, err = fut.result(timeout=per_timeout)
            except _cf.TimeoutError:
                cid, result, err = c.get("id"), None, "联网超时（>%ds）" % per_timeout
            except Exception as e:
                cid, result, err = c.get("id"), None, str(e)[:160]
            if result is not None:
                results.append((cid, result))
                ok_ids.add(cid)
            else:
                errors.append({"title": c.get("title") or "(未命名)", "error": err})
    # 串行写缓存（_save_video_cache 自己会加锁）
    for cid, result in results:
        try:
            _save_video_cache(cid, result)
        except Exception:
            pass
    return {"ok_ids": ok_ids, "errors": errors}


def gather_recent(days=7, refresh=False, per_creator=30, only_enabled=True,
                  backfill=False, per_timeout=120):
    """把「所有关注博主」近 days 天内发布的视频汇总到一起，按时间倒序返回。

    取数策略（恢复成以前的「直接加载」，更稳）：
      · 默认：每个博主先吃缓存；缓存没有的，**当场直接联网列一次**（直接加载出来）。
        给每个博主的联网加 per_timeout 秒超时上限，防止某个频道卡死整个列表。
      · refresh=True：所有博主都重新联网列一遍（最新）。
    返回里仍带 uncached（这次联网超时/失败、没列到的博主），供前端提示。
    """
    try:
        days = int(days)
    except Exception:
        days = 7
    days = max(1, min(365, days))
    try:
        per_timeout = int(per_timeout)
    except Exception:
        per_timeout = 120
    per_timeout = max(10, min(300, per_timeout))

    store = _load()
    creators = [c for c in store.get("creators", [])
                if (not only_enabled) or c.get("enabled", True)]

    import concurrent.futures as _cf

    def _list_one_timed(c):
        """联网列一个博主，最多等 per_timeout 秒。返回 (videos_or_None, error_str)。"""
        cid = c.get("id")
        plat = c.get("platform")
        ex = _cf.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(list_recent, plat, c.get("url"), per_creator)
        try:
            data = fut.result(timeout=per_timeout)
        except _cf.TimeoutError:
            # 不等它了：shutdown(wait=False) 让超时真正生效（线程在后台自生自灭）
            ex.shutdown(wait=False)
            return None, "联网超时（>%ds）" % per_timeout
        except Exception as e:
            ex.shutdown(wait=False)
            return None, str(e)[:160]
        ex.shutdown(wait=False)
        vids = _enrich_dates(data.get("videos") or [])
        # 顺手写缓存，下次秒开
        try:
            _save_video_cache(cid, {
                "title": c.get("title") or "",
                "platform": plat,
                "platform_label": _PLATFORM_LABEL.get(plat, plat or "?"),
                "videos": vids, "total": data.get("total") or len(vids),
                "shown": len(vids),
            })
        except Exception:
            pass
        return vids, ""

    items = []
    errors = []
    creators_ok = 0
    uncached = []
    seen = set()  # 去重：同一 (creator_id, vid) 只留一条

    for c in creators:
        cid = c.get("id")
        title = c.get("title") or "(未命名)"   # 一律用博主列表里的备注名
        platform = c.get("platform")
        plabel = _PLATFORM_LABEL.get(platform, platform or "?")

        vids = None
        # 1) 默认优先吃缓存
        if not refresh:
            cached = get_cached_videos(cid)
            if cached is not None:
                vids = cached.get("videos") or []
        # 2) 缓存没有、或要求强刷 → 当场直接联网列一次（带超时）
        if vids is None:
            v, err = _list_one_timed(c)
            if v is None:
                errors.append({"title": title, "error": err})
                uncached.append({"id": cid, "title": title})
                continue
            vids = v

        creators_ok += 1
        for v in vids:
            vid = str(v.get("vid") or "")
            key = (cid, vid)
            if vid and key in seen:
                continue
            seen.add(key)
            # days_ago 用「发布日期」当场算（缓存里那份可能是几天前算的、已过时）
            da = _video_days_ago(v.get("when"))
            wh = v.get("when_human") or ""
            if da is None and wh:
                da = _video_days_ago(wh.replace("-", ""))
            items.append({
                "creator_id": cid,
                "creator_title": title,
                "platform": platform,
                "platform_label": plabel,
                "vid": vid,
                "url": v.get("url") or "",
                "title": v.get("title") or v.get("url") or "(无标题)",
                "title_zh": v.get("title_zh") or "",
                "when_human": v.get("when_human") or "",
                "days_ago": da,
            })

    dated = [it for it in items if it.get("days_ago") is not None]
    # 在 days 窗口内的（带日期的）
    in_window = [it for it in dated if it["days_ago"] <= days]
    # 无日期的单独归一拨（前端可选择是否一并显示）
    undated = [it for it in items if it.get("days_ago") is None]

    # 排序：窗口内按天数升序（越新越靠前），无日期的排最后
    in_window.sort(key=lambda x: (x["days_ago"], x["creator_title"]))

    # 标注「已提取」：让「按时间看全部」/汇总里，已送过队列的视频显示「已提取」并禁用按钮
    _annotate_extracted(in_window)
    _annotate_extracted(undated)

    return {
        "ok": True,
        "days": days,
        "items": in_window,
        "undated": undated,
        "creators_total": len(creators),
        "creators_ok": creators_ok,
        "creators_err": len(errors),
        "total_videos": len(items),
        "dated_videos": len(dated),
        "in_window": len(in_window),
        "undated_count": len(undated),
        "uncached": uncached,
        "errors": errors,
        "generated_at": _now_iso(),
    }


# ──────────────────────────── 每日定时 ────────────────────────────
def should_run_now():
    """到点且今天还没扫过 → True。供后台调度线程判断。"""
    cfg = get_config()
    if not cfg.get("auto"):
        return False
    now = datetime.datetime.now()
    if now.hour != int(cfg.get("hour", 9)):
        return False
    return _load().get("last_scan_date") != _today()


def _mark_ran_today():
    store = _load()
    store["last_scan_date"] = _today()
    _save(store)


_scheduler_started = {"v": False}


def boot_scheduler():
    """启动一个轻量后台线程：每 ~10 分钟看一眼，到了配置的钟点且今天没扫过就自动扫一遍。
    幂等：重复调用只会启动一次。"""
    if _scheduler_started["v"]:
        return
    _scheduler_started["v"] = True

    def _loop():
        # 启动后先睡一会，避开冷启动
        time.sleep(60)
        while True:
            try:
                if should_run_now():
                    _mark_ran_today()
                    scan_all(only_enabled=True)
            except Exception:
                pass
            time.sleep(600)  # 10 分钟一查

    threading.Thread(target=_loop, daemon=True).start()
