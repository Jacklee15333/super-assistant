"""
video_tools.py — 视频转文字（字幕）工具

原理：很多视频平台把"字幕/CC"作为公开内容提供，可以通过它们公开的字幕接口
直接取到文字，这属于读取公开内容，不是破解、不绕过登录、不抓取受保护数据。

目前支持：
  - YouTube：取公开的 CC 字幕（timedtext）
  - Bilibili：取公开的 AI/人工字幕（subtitle json）

不支持（如实说明，不假装）：
  - 抖音 / 快手：没有公开字幕接口，要文字只能靠语音识别+爬取，违反平台协议、
    有封号和法律风险，本工具不做。替代方案：用手机端"提取字幕/转文字"功能
    拿到文字后，直接发给助手让它总结。

拿到文字稿后，模型可以基于真实字幕内容做总结，而不是凭空编。
"""

import re
import json
import html
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")


def _fetch(url, timeout=20, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read(3_000_000)
    return raw.decode(charset, errors="replace")


# ---------- 平台识别 ----------
def detect_platform(url):
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "bilibili.com" in u or "b23.tv" in u:
        return "bilibili"
    if "douyin.com" in u or "tiktok.com" in u or "kuaishou.com" in u:
        return "douyin"
    return "unknown"


# ---------- YouTube 字幕 ----------
def _youtube_id(url):
    m = re.search(r"(?:v=|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def _youtube_transcript(url):
    vid = _youtube_id(url)
    if not vid:
        return None, "没认出 YouTube 视频 ID。"
    # 取视频页，里面有字幕轨道列表（captionTracks）
    try:
        page = _fetch("https://www.youtube.com/watch?v=" + vid)
    except Exception as e:
        return None, f"打开视频页出错：{e}"
    m = re.search(r'"captionTracks":(\[.*?\])', page)
    if not m:
        return None, "这个视频没有公开字幕（CC）。"
    try:
        tracks = json.loads(m.group(1))
    except Exception:
        return None, "字幕轨道解析失败。"
    if not tracks:
        return None, "这个视频没有公开字幕。"
    # 优先中文，其次英文，再次第一条
    def score(t):
        lang = (t.get("languageCode") or "").lower()
        if lang.startswith("zh"):
            return 0
        if lang.startswith("en"):
            return 1
        return 2
    tracks.sort(key=score)
    base = tracks[0].get("baseUrl")
    if not base:
        return None, "字幕地址缺失。"
    base = base.replace("\\u0026", "&")
    try:
        xml = _fetch(base)
    except Exception as e:
        return None, f"取字幕出错：{e}"
    # 字幕是 <text start=...>内容</text>
    # 注意：先解码 HTML 实体，再去标签——因为字幕里可能有 &lt;b&gt; 这种被转义的标签，
    # 解码后会变成真的 <b>，需要再清一遍。
    parts = re.findall(r"<text[^>]*>(.*?)</text>", xml, re.S)
    cleaned = []
    for p in parts:
        p = html.unescape(p)          # &amp; -> &  ，&lt;b&gt; -> <b>
        p = re.sub(r"<[^>]+>", "", p)  # 去掉所有标签
        cleaned.append(p)
    text = " ".join(cleaned)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None, "字幕内容为空。"
    return text, None


# ---------- Bilibili 字幕 ----------
def _bili_ids(url):
    bvid = None
    m = re.search(r"(BV[0-9A-Za-z]+)", url)
    if m:
        bvid = m.group(1)
    return bvid


def _bilibili_transcript(url):
    bvid = _bili_ids(url)
    if not bvid:
        return None, "没认出 B 站视频号（BV 号）。"
    api = "https://api.bilibili.com/x/web-interface/view?bvid=" + bvid
    try:
        info = json.loads(_fetch(api))
    except Exception as e:
        return None, f"取视频信息出错：{e}"
    data = info.get("data") or {}
    cid = data.get("cid")
    aid = data.get("aid")
    if not cid:
        return None, "没取到分集信息。"
    # 字幕列表
    sub_api = (f"https://api.bilibili.com/x/player/v2?aid={aid}"
               f"&bvid={bvid}&cid={cid}")
    try:
        player = json.loads(_fetch(sub_api))
    except Exception as e:
        return None, f"取字幕列表出错：{e}"
    subs = (((player.get("data") or {}).get("subtitle") or {})
            .get("subtitles") or [])
    if not subs:
        return None, ("这个视频没有公开字幕（B 站很多视频没开字幕）。"
                      "可以改用「读网页」读它的简介，或你手动拿到字幕再发我。")
    sub_url = subs[0].get("subtitle_url") or ""
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    try:
        sj = json.loads(_fetch(sub_url))
    except Exception as e:
        return None, f"取字幕内容出错：{e}"
    body = sj.get("body") or []
    text = " ".join(seg.get("content", "") for seg in body)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None, "字幕内容为空。"
    return text, None


# ---------- 对外的工具函数 ----------
def tool_video_transcript(args):
    """
    取一个视频的文字稿（字幕）。支持 YouTube、Bilibili 的公开字幕。
    拿到文字后，模型可据此总结视频主要内容。
    """
    url = (args.get("url", "") or "").strip()
    if not url:
        return "拒绝：视频链接为空。"
    if not url.startswith(("http://", "https://")):
        return "拒绝：只支持 http/https 链接。"

    plat = detect_platform(url)
    if plat == "youtube":
        text, err = _youtube_transcript(url)
    elif plat == "bilibili":
        text, err = _bilibili_transcript(url)
    elif plat == "douyin":
        return ("这是抖音/快手类链接。这些平台没有公开字幕接口，"
                "要拿到文字只能靠爬取+语音识别，违反平台协议、有封号和法律风险，"
                "我不做。\n替代办法：用手机端的「提取字幕 / 转文字」功能拿到文字后，"
                "直接把文字发我，我帮你总结要点。")
    else:
        return ("没认出这个视频平台。我目前能取 YouTube、Bilibili 的公开字幕。"
                "如果是普通网页，可用「读网页」工具读正文。")

    if err:
        return f"取字幕失败：{err}"
    # 控制长度，避免太长撑爆上下文
    note = ""
    if len(text) > 8000:
        text = text[:8000]
        note = "\n\n（字幕较长，以上为前一部分）"
    return f"【视频字幕原文】\n{text}{note}\n\n（以上是该视频的公开字幕，请据此总结主要内容。）"
