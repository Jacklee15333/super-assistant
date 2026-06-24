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
_scan_state = {"running": False, "last": "", "started": 0.0}


# ──────────────────────────── 工具 ────────────────────────────
def _now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _today():
    return datetime.date.today().isoformat()


def _new_id():
    return "cw" + str(int(time.time() * 1000)) + str(os.getpid() % 1000)


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
    return ""


_PLATFORM_LABEL = {"youtube": "YouTube", "bilibili": "B站", "douyin": "抖音"}

# 这些是「还没识别出真实昵称」时用的占位名；之后一旦探到真名就替换掉。
_GENERIC_TITLES = {"", "YouTube博主", "B站博主", "抖音博主", "博主"}


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
        "last_error": c.get("last_error") or "",
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
        return {"ok": False, "message": "认不出这是哪个平台的主页（支持抖音 / B站 / YouTube）"}
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
    """用 yt-dlp 扁平列出频道/合集页（不下载）。返回 (频道名, entries)。
    limit<=0 表示「全部」（内部封顶 1000 条，防止异常巨型频道把界面拖垮）。"""
    import yt_dlp
    opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True, "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 30, "logger": _SilentLogger(),
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
        return "", []
    name = (info.get("channel") or info.get("uploader")
            or info.get("playlist_uploader") or info.get("title") or "")
    return _clean_channel_name(name, platform), (info.get("entries") or [])


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


def _list_youtube(url, limit):
    target = _norm_youtube_channel(url)
    name, entries = _ytdlp_list(target, limit, use_proxy=True, platform="youtube")
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
        out.append({"vid": str(vid), "url": link,
                    "title": (e.get("title") or "").strip(),
                    "when": _entry_when(e)})
    return {"name": name, "videos": out}


def _norm_bili_space(url):
    """B站：从主页链接抠出 UP 主 mid，归一到投稿列表页。"""
    m = re.search(r"space\.bilibili\.com/(\d+)", url)
    if m:
        return "https://space.bilibili.com/%s/video" % m.group(1)
    return url


def _list_bilibili(url, limit):
    target = _norm_bili_space(url)
    name, entries = _ytdlp_list(target, limit, use_proxy=True, platform="bilibili")
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
    return {"name": name, "videos": out}


def _douyin_name_from_page(url):
    """从抖音用户主页 HTML 里尽量抠出昵称（作品列表取不到时也能拿到名字）。失败返回空。"""
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
    """抖音作品列表：尽力而为。
    抖音主页作品列表需要带签名的接口，yt-dlp 多数情况下也解不动（要登录 cookie）。
    这里先试 yt-dlp，拿到就用；拿不到就抛一个**清楚的错误**，让上层提示用户改用手动贴链接，
    不假装成功、不返回空当作「没有新视频」。"""
    target = url.strip()
    # 短链先跟随跳转，尽量落到 www.douyin.com/user/{sec_uid}
    try:
        if "v.douyin" in target.lower() or "iesdouyin" in target.lower():
            import douyin_resolver
            s = douyin_resolver._session()
            r = s.get(target, allow_redirects=True, timeout=8)
            target = str(getattr(r, "url", "")) or target
    except Exception:
        pass
    name, entries = "", []
    try:
        name, entries = _ytdlp_list(target, limit, use_proxy=False, platform="douyin")
    except Exception as e:
        raise RuntimeError("抖音作品列表取不到（%s）。抖音主页要签名/登录才能列作品，"
                           "建议先把想要的视频链接手动贴到「视频」页提取。" % str(e)[:80])
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
        raise RuntimeError("抖音作品列表没解析到内容（多半是签名/登录限制）。"
                           "建议先把想要的视频链接手动贴到「视频」页提取。")
    return {"name": name, "videos": out}


def list_recent(platform, url, limit=_DEFAULT_PER_SCAN):
    """统一入口：返回 {name, videos:[{vid,url,title,when}]}，最新在前。"""
    plat = platform or _detect_platform(url)
    if plat == "youtube":
        return _list_youtube(url, limit)
    if plat == "bilibili":
        return _list_bilibili(url, limit)
    if plat == "douyin":
        return _list_douyin(url, limit)
    raise RuntimeError("不支持的平台：%s" % plat)


def detect_name(platform, url):
    """只为「自动识别博主名字」用：尽量快地拿到博主昵称。拿不到返回空串，绝不抛异常。"""
    plat = platform if platform in _PLATFORM_LABEL else _detect_platform(url)
    try:
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
        out.append(vv)
    return {"title": title_now,
            "platform": c.get("platform"),
            "platform_label": _PLATFORM_LABEL.get(c.get("platform"), c.get("platform") or "?"),
            "videos": out}


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
                    c["last_error"] = str(e)[:200]
                    break
            _save(store)
        res["error"] = str(e)[:200]
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

    res["new_count"] = new_count
    res["first_time"] = bool(first_time)
    return res


def scan_all(only_enabled=True):
    """扫所有（启用的）博主。返回 {ok, scanned:[...], total_new, total_err}。"""
    store = _load()
    creators = store.get("creators", [])
    scanned, total_new, total_err = [], 0, 0
    for c in creators:
        if only_enabled and not c.get("enabled", True):
            continue
        r = scan_one(c.get("id"))
        scanned.append(r)
        total_new += int(r.get("new_count") or 0)
        if r.get("error"):
            total_err += 1
    return {"ok": True, "scanned": scanned,
            "total_new": total_new, "total_err": total_err}


def scan_all_async():
    """后台扫所有博主，立即返回。前端轮询 get_scan_state。"""
    with _LOCK:
        if _scan_state["running"]:
            return {"ok": False, "message": "正在扫描中，稍候…"}
        _scan_state["running"] = True
        _scan_state["started"] = time.time()
        _scan_state["last"] = "正在扫描所有博主…"

    def _run():
        try:
            r = scan_all(only_enabled=True)
            stamp = datetime.datetime.now().strftime("%H:%M")
            if r.get("total_new"):
                _scan_state["last"] = "%s 扫完：发现 %d 条新视频%s" % (
                    stamp, r["total_new"],
                    ("，%d 个源出错" % r["total_err"]) if r.get("total_err") else "")
            else:
                _scan_state["last"] = "%s 扫完：暂无新视频%s" % (
                    stamp, ("，%d 个源出错" % r["total_err"]) if r.get("total_err") else "")
        except Exception as e:
            _scan_state["last"] = "扫描出错：%s" % str(e)[:120]
        finally:
            _scan_state["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True}


def get_scan_state():
    return dict(_scan_state)


# ──────────────────────────── 待办清单 ────────────────────────────
def get_findings():
    store = _load()
    f = list(store.get("findings", []))
    f.sort(key=lambda x: x.get("found_at") or "", reverse=True)
    return f


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
