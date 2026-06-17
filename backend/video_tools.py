"""
video_tools.py — 视频转文字工具（给 agent 自主调用）

两层策略，自动选最省的：
  1) 公开字幕（快、免费、零依赖）：
     - YouTube：取公开的 CC 字幕（timedtext）
     - Bilibili：取公开的 AI/人工字幕（subtitle json）
  2) 本地语音识别（兜底，抖音/快手/小红书/无字幕视频都能转）：
     - 调用 video_transcribe（yt-dlp 下载音频 + faster-whisper 本地识别）
     - 全程在本机跑，不上传、不联网（除了下载这个公开视频本身）

这样 agent 收到任何视频链接，调用本工具就能拿到文字稿，再据此总结/提炼/写文案。
拿到的是真实文字，不是凭空编。
"""

import re
import json
import html
import urllib.parse
import urllib.request
import datetime

try:
    from agent_core import MEMORY_DIR
except Exception:
    MEMORY_DIR = None

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


# ---------- 本地语音识别兜底（抖音/快手/无字幕视频） ----------
# 单段 prompt 上限：超过就分段（§7）。留余量给模板/标题。
_SUMMARY_MAX_CHARS = 9000
_CHUNK_CHARS = 7000

_SUMMARY_TEMPLATE = (
    "下面是一段视频的文字稿（语音识别得到，可能有个别错别字，请结合上下文理解）。"
    "请帮我做一份**尽量详细、有深度、信息密度高**的中文笔记——宁可写长一点、写透一点，"
    "也不要简略带过。把视频里讲到的具体事例、数字、人名/品牌名、原话、因果逻辑都尽量保留下来。\n\n"
    "【排版要求】用 Markdown，层次分明：每个大块用 `## 小标题`；"
    "「核心观点」「值得记住的点 / 行动建议」里的每一条，用 `### 序号. 小标题` 起头（序号连续），"
    "下面再写详细的正文段落。\n\n"
    "请按下面结构输出：\n"
    "## 一句话概括\n用一句话说清楚这个视频到底在讲什么。\n\n"
    "## 背景与主题\n用 3-5 句把事件/话题的来龙去脉讲清楚：是什么事、涉及谁、作者站在什么角度讲。\n\n"
    "## 核心观点\n列 6-10 条主要观点，**每一条都展开成一段详细说明（4-6 句）**："
    "先点出这条观点，再结合视频里的**具体例子、数字、人名、案例、原话**把它讲透，"
    "并说明背后的原因 / 逻辑 / 影响，不要只写一句话或一个短语。\n\n"
    "## 关键事实与数据\n把视频里出现的**具体事实、数字、名称、案例**单独分条罗列出来，"
    "比如金额、比例、时间、涉及的公司 / 品牌 / 人物、提到的类似事件等，方便日后查证和引用。\n\n"
    "## 金句摘录\n从文字稿里挑 4-6 句最有价值或最有意思的原话，**照原话摘出来**（用引号），"
    "可以稍微顺一下口语里明显的错别字。\n\n"
    "## 值得记住的点 / 行动建议\n用 `### 序号. 小标题` + 详细正文，分条写作者给的具体建议、"
    "可操作的做法或最有用的信息，越具体、越能落地越好。\n\n"
    "## 我的点评\n用 4-6 句客观点评：这些观点有没有道理、哪里值得认同、"
    "哪里需要注意或保留、可能的片面之处，普通人可以怎么用。\n\n"
    "整体要条理清晰、信息密度高、尽量详尽，是深度归纳不是照抄原文。\n\n")


def _split_chunks(text, size):
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def _analyze_transcript(transcript, title, use_local, model, on_progress=None):
    """
    把文字稿总结成一份有结构的中文笔记。
    模型由 resolve_model("video_summary") 决定（默认伪模型）；失败回退本地。
    超长文字稿走分段总结（§7）。
    """
    import agent_core
    transcript = transcript or ""

    # 取「视频总结」该用的模型；前端当前选择作兜底
    try:
        s_use_local, s_model = agent_core.resolve_model(
            "video_summary", fallback_use_local=use_local, fallback_model=model)
    except Exception:
        s_use_local, s_model = use_local, model

    # 视频总结的设计：原文已用本地提取，这一步默认交给「网页模型」分析总结。
    # 若解析到的是云端模型、但本机没配 OPENAI_API_KEY，直接调用会报 Missing credentials —
    # 这种情况下退回到网页模型（设计本意），避免硬失败。
    import os as _os
    if (not s_use_local) and (not agent_core.is_web_model(s_model)) \
            and not _os.environ.get("OPENAI_API_KEY") \
            and not _os.environ.get("OPENAI_ADMIN_KEY"):
        s_use_local, s_model = False, "web"

    def _prog(msg):
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    # 伪模型答完判定提示（总结类）：必含小标题 + 最小长度，大幅降低误判
    web_opts = dict(requiredMarkers=["一句话概括", "核心观点", "金句"],
                    minExpectedLength=900)

    def _complete(prompt, use_web_opts=True):
        client = agent_core.make_client_for(s_model, s_use_local, on_progress=_prog)
        kw = {}
        if agent_core.is_web_model(s_model) and use_web_opts:
            kw = web_opts
        resp = client.chat.completions.create(
            model=s_model, messages=[{"role": "user", "content": prompt}], **kw)
        return (resp.choices[0].message.content or "").strip()

    try:
        if len(transcript) <= _SUMMARY_MAX_CHARS:
            prompt = (_SUMMARY_TEMPLATE +
                      f"视频标题：{title}\n\n=== 文字稿 ===\n{transcript}\n")
            return _complete(prompt) or "（没分析出内容）"

        # ── 长文分段：每段出要点 → 合并出全局总结 ──
        chunks = _split_chunks(transcript, _CHUNK_CHARS)
        n = len(chunks)
        partials = []
        for i, ch in enumerate(chunks, 1):
            _prog(f"总结第 {i}/{n} 段…")
            p = ("下面是一段长视频文字稿的第 %d/%d 部分。请把这部分的【要点】"
                 "分条列出（只列要点，不要写引言结语，尽量具体）：\n\n%s\n" % (i, n, ch))
            partials.append(_complete(p, use_web_opts=False))
        _prog("整合全局总结…")
        merged = "\n\n".join("【第%d段要点】\n%s" % (i + 1, p)
                             for i, p in enumerate(partials))
        final_prompt = (_SUMMARY_TEMPLATE +
                        f"视频标题：{title}\n\n"
                        "下面是这段视频【分段提炼出的要点汇总】，请据此整合成上面结构的完整笔记"
                        "（不要遗漏各段要点，去重合并）：\n\n" + merged + "\n")
        return _complete(final_prompt) or "（没分析出内容）"
    except Exception as e:
        # ★铁律：总结模型失败 → 一律回退本地再试一次（不管它是网页模型还是云端模型，
        #   避免出现"分析出错：Missing credentials"这种直接抛出、不兜底的情况）。
        try:
            _prog("总结模型不可用，回退本地总结…")
            client = agent_core.make_client(True)
            prompt = (_SUMMARY_TEMPLATE +
                      f"视频标题：{title}\n\n=== 文字稿 ===\n{transcript[:10000]}\n")
            resp = client.chat.completions.create(
                model="qwen2.5", messages=[{"role": "user", "content": prompt}])
            return (resp.choices[0].message.content or "").strip() or f"（分析出错：{e}）"
        except Exception as e2:
            return f"（分析出错：{e2}）"


def _save_video_note(res, analysis="", tags=None):
    """把转写结果存一份到「视频」板块的笔记里，格式和视频板块完全一致。返回文件名或 ''。"""
    if MEMORY_DIR is None:
        return ""
    try:
        d = MEMORY_DIR / "video_notes"
        d.mkdir(exist_ok=True)
        title = res.get("title") or "（无标题）"
        uploader = res.get("uploader") or ""
        clean_url = res.get("url") or ""
        transcript = res.get("transcript") or ""
        ts = datetime.datetime.now()
        safe = "".join(c for c in title[:20]
                       if c.isalnum() or c in " 　-_") or "video"
        fname = (f"{ts.strftime('%Y%m%d-%H%M%S')}-{safe}.md").replace(" ", "_")
        analysis_block = analysis or "（无分析）"
        tag_line = ("- 标签：" + "、".join(tags) + "\n") if tags else ""
        doc = (f"# {title}\n\n"
               f"- 来源链接：{clean_url}\n"
               f"- 作者：{uploader}\n"
               f"- 提取时间：{ts.strftime('%Y-%m-%d %H:%M')}\n"
               f"{tag_line}"
               f"- 来源：对话里直接提取\n\n"
               f"## 🤖 AI 分析\n\n{analysis_block}\n\n"
               f"---\n\n## 📝 完整文字稿\n\n{transcript}\n")
        (d / fname).write_text(doc, encoding="utf-8")
        return fname
    except Exception:
        return ""


def _clean_ai_tags(raw):
    """把模型给的标签输出清洗成干净的标签列表，尽量抗各种啰嗦/编号/前缀。"""
    import re
    if not raw:
        return []
    text = raw.strip()
    m = re.search(r"(?:标签|tags?)\s*[:：]\s*(.+)", text, flags=re.I)
    if m:
        text = m.group(1)
    else:
        text = re.sub(r"^[^:：\n]{0,30}[:：]\s*", "", text)
    text = text.splitlines()[0] if text else ""
    parts = re.split(r"[、,，/|\s]+", text)
    seen, out = set(), []
    for p in parts:
        p = p.strip().strip("#＃“”\"'《》「」()（）[]【】.。·、-—:：").strip()
        p = re.sub(r"^[\d①-⑩]+[.\)、]?", "", p).strip()
        if not p:
            continue
        if len(p) > 8 or " " in p:
            continue
        if p in ("标签", "tags", "tag", "无", "暂无", "和", "以及", "等"):
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= 3:
            break
    return out


def _suggest_tags_for_note(title, analysis, use_local, model):
    """让模型给这条视频总结 1-3 个二级标签；失败返回 []。"""
    base = (analysis or "")[:1200]
    prompt = (
        "请根据下面这条视频笔记的标题和内容，总结 1 到 3 个最贴切的中文二级标签，"
        "用来给它归类（例如：金融、逻辑、AI、创业、心理、职场、健康 等）。\n"
        "严格要求：直接输出标签，多个标签用顿号、分隔；每个标签 2-4 个字；"
        "不要写“标签：”，不要编号，不要解释，不要任何多余的字。\n"
        "示例输出：创业、经营管理、认知\n\n"
        f"标题：{title}\n\n内容节选：\n{base}\n\n直接输出标签：")
    try:
        import agent_core as _core
        client = _core.make_client(True)
        resp = client.chat.completions.create(
            model="qwen2.5", messages=[{"role": "user", "content": prompt}])
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:
        return []
    return _clean_ai_tags(raw)


def _whisper_transcript(url):
    """用本地语音识别把视频转文字（抖音/快手/无字幕都能转）。"""
    try:
        import video_transcribe
    except Exception as e:
        return f"想用本地语音识别转这个视频，但模块加载失败：{e}"

    try:
        missing = video_transcribe.check_deps()
    except Exception:
        missing = None
    if missing:
        return ("这个视频没有公开字幕，要靠本地语音识别来转文字，"
                "但本机还没装好依赖（" + "、".join(missing) + "）。\n"
                "请点左边「视频」板块，按提示点一下「安装依赖」，"
                "装好之后再把链接发我就行。")

    # 把语音识别的实时进度报给「对话」的进度通道（如果是对话触发的）
    try:
        import chat_progress as _cp
    except Exception:
        _cp = None

    _seen = {"stage": ""}

    def _cb(stage, detail=""):
        if _cp is None:
            return
        # 从 detail 里抠出百分比（如 "已识别 42%（38 秒 / 共 90 秒）"）
        pct = None
        m = re.search(r'(\d{1,3})\s*%', detail or "")
        if m:
            pct = int(m.group(1))
        nice = {
            "解析链接": "解析视频链接",
            "下载音频": "下载视频音频",
            "加载语音模型": "加载语音模型",
            "语音转文字": "语音识别中",
        }.get(stage, stage)
        if stage != _seen["stage"]:
            # 进入新阶段：新增一步
            _seen["stage"] = stage
            _cp.push_for_thread(nice + "…", pct=pct, detail=detail or "")
        else:
            # 同一阶段：只更新百分比/说明
            _cp.set_pct_for_thread(pct, detail or "")

    # ★把这条对话视频任务登记到「视频」板块，让它在那边也能看到（排队中/处理中）
    # 用中立模块 video_queue_state（不能 import server，__main__ 双重加载会拿到两份状态）
    _srv = None
    _cv_id = None
    try:
        import video_queue_state as _srv
        _cv_id = _srv.register(url[:60])
    except Exception:
        _srv = None
        _cv_id = None

    # ★和「视频」板块队列共用同一把全局闸门：同一时间只跑一个视频提取，避免抢资源。
    if video_transcribe.extract_busy():
        if _cp is not None:
            try:
                _cp.push_for_thread("前面有视频提取任务在进行，排队等待…")
            except Exception:
                pass
        if _srv and _cv_id:
            _srv.update(_cv_id, stage="排队等待",
                        detail="前面有视频提取任务在进行…", waiting=True)
    video_transcribe.extract_gate.acquire()
    if _srv and _cv_id:
        _srv.update(_cv_id, stage="处理中", detail="", waiting=False)
    try:
        def _cb2(stage, detail=""):
            _cb(stage, detail)
            if _srv and _cv_id:
                try:
                    _srv.update(_cv_id, stage=stage, detail=detail)
                except Exception:
                    pass
        res = video_transcribe.extract(url, level="balanced", progress_cb=_cb2)
    finally:
        try:
            video_transcribe.extract_gate.release()
        except (ValueError, RuntimeError):
            pass
    if not res.get("ok"):
        if _srv and _cv_id:
            try: _srv.done(_cv_id)
            except Exception: pass
        if res.get("need"):
            return ("需要先到「视频」板块点「安装依赖」装好（"
                    + "、".join(res["need"]) + "）再试。")
        return ("这个视频没取到文字：" + str(res.get("error", "")) +
                "\n可能是链接失效、视频已删，或平台临时限制。")

    transcript = res.get("transcript") or ""
    title = res.get("title") or ""

    # 拿到标题后，把「视频」板块里这条任务的名字更新成视频标题，并标记进入总结阶段
    if _srv and _cv_id:
        try:
            _srv.update(_cv_id, stage="AI 分析",
                        detail="总结成视频笔记…",
                        label=(title or url)[:60])
        except Exception:
            pass

    # 用和「视频」板块同一套提示，把文字稿总结成一份完整笔记，再存进「视频」板块
    if _cp is not None:
        _cp.push_for_thread("总结成视频笔记…")
    st = (_cp.current_settings() if _cp else None) or {}
    use_local = st.get("use_local", True)
    model = st.get("model", "qwen2.5")

    def _sum_prog(msg):
        if _cp is not None:
            try:
                _cp.push_for_thread(msg)
            except Exception:
                pass
    analysis = _analyze_transcript(transcript, title, use_local, model,
                                   on_progress=_sum_prog)
    # ★顺手让模型总结二级标签，写进笔记（用户之后可在界面修改）
    if _cp is not None:
        try: _cp.push_for_thread("归纳标签…")
        except Exception: pass
    try:
        tags = _suggest_tags_for_note(title, analysis, use_local, model)
    except Exception:
        tags = []
    saved = _save_video_note(res, analysis, tags=tags)

    # 任务完成：把它从「视频」板块的进行列表里移除，并把结果推给视频板块刷新出来
    if _srv and _cv_id:
        try:
            _srv.publish_result({
                "ok": True, "title": title, "uploader": res.get("uploader") or "",
                "url": res.get("url") or url, "analysis": analysis,
                "transcript": transcript, "saved_as": saved})
        except Exception:
            pass
        try: _srv.done(_cv_id)
        except Exception: pass

    # 返回给对话模型：既给要点（已生成的笔记），也给一段文字稿，让它据此回答用户
    t_show = transcript
    note = ""
    if len(t_show) > 4000:
        t_show = t_show[:4000]
        note = "\n\n（文字稿较长，以上为前一部分，完整版已存到「视频」板块）"
    head = f"【已提取并生成笔记】视频标题：{title}\n\n" if title else "【已提取并生成笔记】\n\n"
    body_txt = (f"=== AI 笔记 ===\n{analysis}\n\n"
                f"=== 文字稿（节选）===\n{t_show}{note}")
    tail = ("\n\n（这条视频笔记已自动存到「视频」板块"
            + (f"：{saved}" if saved else "") + "。"
            "请据此完成用户的要求：总结要点 / 提炼文案 / 回答他的问题等。）")
    return head + body_txt + tail


# ---------- 对外的工具函数 ----------
def tool_video_transcript(args):
    """
    取一个视频的文字稿。
    - YouTube / Bilibili：先取公开字幕（快、免费）；取不到再走本地语音识别。
    - 抖音 / 快手 / 小红书 / 其它：直接用本地语音识别（yt-dlp + faster-whisper）转文字。
    拿到文字后，模型据此总结/提炼/写文案/回答问题。
    """
    url = (args.get("url", "") or "").strip()
    if not url:
        return "拒绝：视频链接为空。"
    # 用户可能粘的是抖音整段分享文案，先从里面抠出真正的链接
    m = re.search(r'https?://[^\s，。、）)】\]"\'<>　]+', url)
    if m:
        url = m.group(0).rstrip("/.,；;")
    if not url.startswith(("http://", "https://")):
        return "拒绝：没找到 http/https 视频链接。"

    plat = detect_platform(url)

    # 1) YouTube / Bilibili 先试公开字幕
    if plat == "youtube":
        text, err = _youtube_transcript(url)
        if text:
            note = ""
            if len(text) > 8000:
                text = text[:8000]
                note = "\n\n（字幕较长，以上为前一部分）"
            return (f"【视频字幕原文（公开CC字幕）】\n{text}{note}\n\n"
                    "（请据此总结/回答用户。）")
        # 没字幕 -> 落到本地语音识别
        return _whisper_transcript(url)

    if plat == "bilibili":
        text, err = _bilibili_transcript(url)
        if text:
            note = ""
            if len(text) > 8000:
                text = text[:8000]
                note = "\n\n（字幕较长，以上为前一部分）"
            return (f"【视频字幕原文（公开字幕）】\n{text}{note}\n\n"
                    "（请据此总结/回答用户。）")
        return _whisper_transcript(url)

    # 2) 抖音/快手/小红书/未知平台 -> 直接本地语音识别
    return _whisper_transcript(url)
