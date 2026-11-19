# -*- coding: utf-8 -*-
"""
x_watch.py — X（推特）博主抓取

和视频平台（YouTube/B站/抖音）不一样：X 上绝大多数是**文字推文**，
没有音视频可听写。所以 X 的「内容」就是推文文字本身，直接抓文字、直接入库，
省掉了「下载音频 → 听写」那一步。

X 现在几乎全程要登录才能看时间线，因此需要用户从浏览器复制一份登录后的 Cookie：
  存放在  backend/memory/x_cookie.txt （一整串 k=v; k=v; … 直接粘进去即可）

抓取策略（从稳到次）：
  ① 用 X 的 GraphQL UserByScreenName + UserTweets 接口（带 Cookie + bearer + csrf）；
  ② 退回 yt-dlp 的 twitter 提取器（带 cookie 文件），能列到多少算多少。
任何一步失败都安静降级，最终返回 {name, videos:[...]}（沿用 creator_watch 的字段名，
其中 video 项的 "title" 放推文文字摘要、"text" 放全文、"when" 放 YYYYMMDD）。
"""

import os
import re
import json
import datetime
import urllib.parse


# X 网页端公开使用的 guest/web bearer（长期固定，公开可见，非密钥）。
# 这是 X 官方网页前端自己用的同一个值，配合用户 Cookie 才能访问已登录接口。
_X_BEARER = ("Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
             "=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")


def _memory_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")


def cookie_file():
    return os.path.join(_memory_dir(), "x_cookie.txt")


def has_cookie():
    """是否已配置 X Cookie。"""
    try:
        p = cookie_file()
        if os.path.exists(p):
            return bool(open(p, "r", encoding="utf-8").read().strip())
    except Exception:
        pass
    return False


def save_cookie(raw):
    """保存用户粘贴的 X Cookie 字符串。返回 {ok, message}。"""
    raw = (raw or "").strip()
    if not raw:
        # 空字符串视为「清除」
        try:
            p = cookie_file()
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        return {"ok": True, "message": "已清除 X Cookie"}
    ck = _parse_cookie_str(raw)
    # 基本校验：登录态至少要有 auth_token 和 ct0（csrf）
    if "auth_token" not in ck or "ct0" not in ck:
        return {"ok": False, "message": "这串 Cookie 里没找到 auth_token / ct0，"
                "可能没复制全或没登录。请在已登录的 x.com 页面，按 F12 → 应用/Application "
                "→ Cookie，把整页 Cookie 复制过来。"}
    try:
        os.makedirs(_memory_dir(), exist_ok=True)
        with open(cookie_file(), "w", encoding="utf-8") as f:
            f.write(raw)
        return {"ok": True, "message": "X Cookie 已保存"}
    except Exception as e:
        return {"ok": False, "message": "保存失败：%s" % e}


def _parse_cookie_str(raw):
    """浏览器复制的一整串 Cookie（k1=v1; k2=v2; …）解析成 dict。"""
    out = {}
    for part in (raw or "").replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k:
            out[k] = v
    return out


def _load_cookie():
    try:
        p = cookie_file()
        if os.path.exists(p):
            raw = open(p, "r", encoding="utf-8").read().strip()
            if raw:
                return _parse_cookie_str(raw)
    except Exception:
        pass
    return {}


def write_netscape_cookiefile():
    """把 x_cookie.txt 写成 yt-dlp 能用的 Netscape cookie 文件，返回路径或 None。"""
    ck = _load_cookie()
    if not ck:
        return None
    try:
        path = os.path.join(_memory_dir(), "x_cookies_netscape.txt")
        lines = ["# Netscape HTTP Cookie File", ""]
        for name, value in ck.items():
            if not name or value is None:
                continue
            lines.append("\t".join(
                [".x.com", "TRUE", "/", "TRUE", "0", str(name), str(value)]))
            lines.append("\t".join(
                [".twitter.com", "TRUE", "/", "TRUE", "0", str(name), str(value)]))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return path
    except Exception:
        return None


def detect_handle(url):
    """从 x.com / twitter.com 链接里抠出 @handle（不含 @）。抠不到返回空串。"""
    u = (url or "").strip()
    m = re.search(r"(?:x\.com|twitter\.com)/(@?[A-Za-z0-9_]{1,30})", u, re.I)
    if not m:
        return ""
    h = m.group(1).lstrip("@")
    # 排除 X 自己的功能路径，不是用户名
    if h.lower() in ("home", "explore", "notifications", "messages", "search",
                     "settings", "i", "compose", "hashtag", "intent"):
        return ""
    return h


def is_x_url(url):
    u = (url or "").lower()
    return ("x.com/" in u or "twitter.com/" in u)


def _proxy():
    try:
        import web_tools
        return web_tools._read_proxy() or ""
    except Exception:
        return ""


# ───────────────────────── GraphQL 抓取（首选）─────────────────────────
def _gql_headers(ck):
    return {
        "authorization": _X_BEARER,
        "x-csrf-token": ck.get("ct0", ""),
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "content-type": "application/json",
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0 Safari/537.36"),
        "referer": "https://x.com/",
        "x-twitter-client-language": "en",
    }


def _http_get_json(url, headers, timeout=20):
    import urllib.request
    proxy = _proxy()
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(4_000_000)
    return json.loads(raw.decode("utf-8", errors="replace"))


def _gql_user_id(handle, ck):
    """UserByScreenName → rest_id（用户数字 ID）。失败返回空串。"""
    var = {"screen_name": handle, "withSafetyModeUserFields": True}
    feat = {"hidden_profile_likes_enabled": True, "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True, "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True}
    q = urllib.parse.urlencode({"variables": json.dumps(var), "features": json.dumps(feat)})
    url = "https://x.com/i/api/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName?" + q
    try:
        data = _http_get_json(url, _gql_headers(ck))
        u = (((data.get("data") or {}).get("user") or {}).get("result") or {})
        return u.get("rest_id") or "", (((u.get("legacy") or {}).get("name")) or "")
    except Exception:
        return "", ""


def user_avatar(url):
    """v75：X 博主的头像地址（400×400 的大图）。先用你存的 X Cookie 问 X（和扫推文是同一个接口），
    不行再用两个不用登录的公开服务。拿不到返回空串。"""
    handle = detect_handle(url) if "/" in (url or "") else (url or "").strip().lstrip("@")
    if not handle:
        return ""
    big = lambda u: re.sub(r"_normal(\.\w+)$", r"_400x400\1", u or "")
    ck = _load_cookie()
    if ck:
        var = {"screen_name": handle, "withSafetyModeUserFields": True}
        feat = {"hidden_profile_likes_enabled": True, "hidden_profile_subscriptions_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True, "verified_phone_label_enabled": False,
                "subscriptions_verification_info_is_identity_verified_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "highlights_tweets_tab_ui_enabled": True, "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True}
        q = urllib.parse.urlencode({"variables": json.dumps(var), "features": json.dumps(feat)})
        try:
            data = _http_get_json("https://x.com/i/api/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName?" + q,
                                  _gql_headers(ck))
            u = (((data.get("data") or {}).get("user") or {}).get("result") or {})
            img = ((u.get("legacy") or {}).get("profile_image_url_https")
                   or (u.get("avatar") or {}).get("image_url") or "")
            if img:
                return big(img)
        except Exception:
            pass
    try:
        data = _http_get_json("https://api.fxtwitter.com/" + urllib.parse.quote(handle),
                              {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"})
        img = ((data or {}).get("user") or {}).get("avatar_url") or ""
        if img:
            return big(img)
    except Exception:
        pass
    return "https://unavatar.io/x/%s?fallback=false" % urllib.parse.quote(handle)


def _gql_user_tweets(user_id, ck, count=20):
    """UserTweets → 推文列表。返回原始 instructions（调用方再解析）。失败返回 None。"""
    var = {"userId": user_id, "count": count, "includePromotedContent": False,
           "withQuickPromoteEligibilityTweetFields": False, "withVoice": False, "withV2Timeline": True}
    feat = {"responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False, "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "c9s_tweet_anatomy_moderator_badge_enabled": True, "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True, "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True, "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True, "tweet_awards_web_tipping_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True, "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "rweb_video_timestamps_enabled": True, "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True, "responsive_web_enhance_cards_enabled": False}
    q = urllib.parse.urlencode({"variables": json.dumps(var), "features": json.dumps(feat)})
    url = "https://x.com/i/api/graphql/E3opETHurmVJflFsUBVuUQ/UserTweets?" + q
    try:
        return _http_get_json(url, _gql_headers(ck))
    except Exception:
        return None


def _ymd_from_twitter_date(s):
    """'Wed Oct 10 20:19:24 +0000 2018' → 'YYYYMMDD'。失败返回空串。"""
    try:
        dt = datetime.datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y%m%d")
    except Exception:
        return ""


def _walk_tweets(data):
    """从 UserTweets 返回里把每条推文的 {id, text, when, name} 抠出来。"""
    out = []
    try:
        insts = (((data.get("data") or {}).get("user") or {}).get("result") or {})
        tl = (insts.get("timeline_v2") or insts.get("timeline") or {}).get("timeline") or {}
        instructions = tl.get("instructions") or []
    except Exception:
        return out
    for ins in instructions:
        for ent in (ins.get("entries") or []):
            content = ent.get("content") or {}
            item = content.get("itemContent") or {}
            tr = (item.get("tweet_results") or {}).get("result") or {}
            if tr.get("__typename") == "TweetWithVisibilityResults":
                tr = tr.get("tweet") or {}
            legacy = tr.get("legacy") or {}
            if not legacy:
                continue
            tid = tr.get("rest_id") or legacy.get("id_str") or ""
            # 长推文（note tweet）取全文，否则取 full_text
            note = (((tr.get("note_tweet") or {}).get("note_tweet_results") or {})
                    .get("result") or {})
            text = (note.get("text") or legacy.get("full_text") or "").strip()
            when = _ymd_from_twitter_date(legacy.get("created_at") or "")
            # 作者名
            uname = ""
            try:
                ur = ((tr.get("core") or {}).get("user_results") or {}).get("result") or {}
                uname = ((ur.get("legacy") or {}).get("name")) or ""
            except Exception:
                pass
            if tid and text:
                out.append({"id": str(tid), "text": text, "when": when, "name": uname})
    return out


def _clean_tweet_title(text):
    """把推文做成一行标题：去换行、压空格、截断。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t[:80]


# ───────────────────────── yt-dlp 兜底 ─────────────────────────
def _ytdlp_list(handle, limit):
    """yt-dlp 兜底列 X 用户（主要能拿到带媒体的推文）。返回 [{id,text,when,name}]。"""
    try:
        import yt_dlp
    except Exception:
        return []
    cookiefile = write_netscape_cookiefile()
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "skip_download": True, "nocheckcertificate": True,
            "playlistend": max(1, min(50, int(limit or 20)))}
    if cookiefile:
        opts["cookiefile"] = cookiefile
    p = _proxy()
    if p:
        opts["proxy"] = p
    url = "https://x.com/%s" % handle
    out = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        for e in (info.get("entries") or []):
            if not isinstance(e, dict):
                continue
            tid = e.get("id") or ""
            text = (e.get("title") or e.get("description") or "").strip()
            if tid:
                out.append({"id": str(tid), "text": text, "when": "",
                            "name": e.get("uploader") or ""})
    except Exception:
        pass
    return out


# ───────────────── 同步接口（Syndication，首选，最稳）─────────────────
# X 嵌入式小组件用的公开接口，不依赖会变的 GraphQL queryId，比 GraphQL 稳得多。
#   https://syndication.twitter.com/srv/timeline-profile/screen-name/<用户名>
# 返回一个内嵌 __NEXT_DATA__ JSON 的 HTML 页，里头有时间线推文。
# 带上 cookie（guest_id/auth_token/ct0/kdt）能拿到完整时间线。

def _cookie_header_str(ck):
    parts = []
    for k in ("guest_id", "auth_token", "ct0", "kdt", "twid", "dnt"):
        if ck.get(k):
            parts.append("%s=%s" % (k, ck[k]))
    if "dnt" not in ck:
        parts.append("dnt=1")
    return "; ".join(parts)


def _http_get_text(url, headers, timeout=20):
    import urllib.request
    proxy = _proxy()
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(8_000_000)
    return raw.decode("utf-8", errors="replace")


def _syndication_timeline(handle, ck, timeout=20):
    """用 Syndication 接口抓时间线。返回 (tweets, name, err)。
    tweets=[{id,text,when,name}]；err 非空表示失败原因。"""
    url = ("https://syndication.twitter.com/srv/timeline-profile/screen-name/%s"
           "?showReplies=false" % handle)
    headers = {
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "referer": "https://platform.twitter.com/",
    }
    ch = _cookie_header_str(ck)
    if ch:
        headers["cookie"] = ch
    try:
        html = _http_get_text(url, headers, timeout=timeout)
    except Exception as e:
        return [], "", "同步接口请求失败：%s（可能是代理没开或网络不通）" % _short_err(e)

    # 抠出 __NEXT_DATA__ 里的 JSON
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        if "Tweets aren" in html or "protected" in html.lower():
            return [], "", "这个账号可能受保护或无法公开访问。"
        return [], "", "没解析到时间线数据（X 可能改版，或 Cookie 失效需重新粘）。"
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return [], "", "时间线数据解析失败：%s" % _short_err(e)

    # 在 JSON 里递归找 entries / tweet 节点
    tweets, name = _parse_syndication_json(data)
    if not tweets:
        return [], name, "Cookie 可能已失效或没拿到推文（X 时间线需要有效登录态）。"
    return tweets, name, ""


def _parse_syndication_json(data):
    """从 syndication 的 __NEXT_DATA__ 里抠推文。返回 (tweets, name)。"""
    tweets, name = [], ""
    try:
        props = (((data.get("props") or {}).get("pageProps")) or {})
        timeline = props.get("timeline") or {}
        entries = timeline.get("entries") or []
        # 有些结构把推文放在 props.tweets 或 contextProvider 里，做个兜底
        if not entries:
            ctx = props.get("contextProvider") or {}
            entries = (ctx.get("timeline") or {}).get("entries") or []
        for ent in entries:
            content = ent.get("content") or {}
            tw = content.get("tweet") or ent.get("tweet") or {}
            if not tw:
                # 新结构：entry 直接就是 tweet
                tw = ent if ent.get("id_str") or ent.get("full_text") else {}
            if not tw:
                continue
            tid = tw.get("id_str") or str(tw.get("id") or "")
            text = (tw.get("full_text") or tw.get("text") or "").strip()
            when = _ymd_from_twitter_date(tw.get("created_at") or "")
            u = tw.get("user") or {}
            if u and not name:
                name = u.get("name") or ""
            if tid and text:
                tweets.append({"id": tid, "text": text, "when": when,
                               "name": (u.get("name") or "")})
    except Exception:
        pass
    return tweets, name


def _short_err(e):
    s = str(e)
    return s[:120] if s else e.__class__.__name__


# 最近一次抓取的失败原因（给前端「没扫到」时显示更具体的提示）
_last_error = ""


def last_error():
    return _last_error


# ───────────────────────── 对外主入口 ─────────────────────────
def list_recent(url, limit=20):
    """列某个 X 博主最近的推文。返回 {name, videos:[...], total, error}。
    抓取顺序：① Syndication（最稳）② GraphQL ③ yt-dlp。"""
    global _last_error
    _last_error = ""
    handle = detect_handle(url)
    if not handle:
        raise RuntimeError("认不出这是哪个 X 用户的主页（应形如 https://x.com/用户名）")
    ck = _load_cookie()
    name = ""
    tweets = []
    errs = []

    if not ck or not ck.get("auth_token") or not ck.get("ct0"):
        _last_error = "还没配置 X 登录 Cookie（或缺 auth_token / ct0）。请在添加 X 博主时粘贴。"
        # 没 cookie 也试一下匿名同步接口，多半拿不到，但不至于直接报错
    # ① Syndication
    s_tweets, s_name, s_err = _syndication_timeline(handle, ck)
    if s_tweets:
        tweets, name = s_tweets, (s_name or name)
    elif s_err:
        errs.append("同步接口：" + s_err)

    # ② GraphQL 兜底
    if not tweets and ck.get("auth_token") and ck.get("ct0"):
        try:
            uid, uname = _gql_user_id(handle, ck)
            name = name or uname
            if uid:
                data = _gql_user_tweets(uid, ck, count=max(5, min(40, limit * 2)))
                if data:
                    tweets = _walk_tweets(data)
            if not tweets:
                errs.append("GraphQL：没取到推文（X 接口可能临时变动）。")
        except Exception as e:
            errs.append("GraphQL：" + _short_err(e))

    # ③ yt-dlp 兜底（主要是带媒体的推文）
    if not tweets:
        yt = _ytdlp_list(handle, limit)
        if yt:
            tweets = yt
            if not name:
                name = next((t.get("name") for t in yt if t.get("name")), "")
        else:
            errs.append("yt-dlp：也没列到内容。")

    if not name:
        name = "@" + handle

    if not tweets:
        _last_error = "；".join(errs) or "没抓到推文（X 限制较多，可能需要重新粘 Cookie 或开代理）。"

    videos = []
    for t in tweets[: (limit if limit and limit > 0 else 40)]:
        tid = t["id"]
        videos.append({
            "vid": tid,
            "url": "https://x.com/%s/status/%s" % (handle, tid),
            "title": _clean_tweet_title(t.get("text")),
            "text": t.get("text") or "",
            "when": t.get("when") or "",
            "uploader": t.get("name") or name,
        })
    return {"name": name, "videos": videos, "total": len(videos),
            "error": _last_error}


def detect_name(url):
    """只为「自动识别博主名字」用。拿不到返回空串，不抛异常。"""
    try:
        d = list_recent(url, 1)
        return (d.get("name") or "").strip()
    except Exception:
        return ""
