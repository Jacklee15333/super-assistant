# -*- coding: utf-8 -*-
"""v78：嗅探 · 博主页的「搜索推荐」：输入想看的领域，让 AI 池联网找出最值得关注的前 N 个来源——
网站（官方博客、新闻页、行业媒体、研究机构）和视频平台 / 社交平台上的博主（YouTube、B站、抖音、X），
勾选后一键加进「关注的博主」。和「网站新动态」里的「按关键词找信息源」是同一套做法，各管各的。"""
import re
import json
import time
import datetime
import threading
import concurrent.futures

_lock = threading.Lock()
_state = {"running": False, "keyword": "", "stage": "", "results": [], "error": "",
          "note": "", "started": 0, "finished": 0}

DEFAULT_N = 10

PROMPT = """今天是 {today}。我想长期关注「{kw}」，请帮我推荐这个领域最值得关注的前 {n} 个内容来源。
可以是网站（官方网站 / 官方博客或新闻页、权威行业媒体、研究机构），也可以是视频平台和社交平台上的博主或官方账号（YouTube 频道、B站 UP 主、抖音号、X（推特）账号）。

要求：
1. 先联网搜索核实：真实存在、最近还在更新。绝对不要编造网址或账号。
2. 网址要这样给：网站给能看到最新文章 / 新闻列表的页面（比如 /blog、/news）；YouTube 给频道主页（https://www.youtube.com/@账号）；B站给 UP 主空间（https://space.bilibili.com/数字）；抖音给用户主页（https://www.douyin.com/user/...）；X 给 https://x.com/账号。
3. 国内、国外都要有；网站和博主都要有（博主大约占一半）。按对这个领域的重要程度从高到低排。

只输出一个 JSON 数组，不要任何其它文字、不要代码块。每一项的格式：
{{"name": "名称", "url": "https://...", "kind": "网站/YouTube/B站/抖音/X", "region": "国内/国外", "why": "一句话说明为什么值得关注（20 字以内）"}}
"""

_KIND = {"web": "网站", "youtube": "YouTube", "bilibili": "B站", "douyin": "抖音", "x": "X"}


def status():
    with _lock:
        return json.loads(json.dumps(_state, ensure_ascii=False))


def _set(**kw):
    with _lock:
        _state.update(kw)


def start(keyword, n=DEFAULT_N):
    keyword = (keyword or "").strip()
    if not keyword:
        return {"ok": False, "message": "先输入想看什么"}
    try:
        n = max(3, min(30, int(n or DEFAULT_N)))
    except Exception:
        n = DEFAULT_N
    with _lock:
        if _state["running"]:
            return {"ok": False, "message": "上一次搜索还没结束（%s）" % _state["keyword"]}
        _state.update(running=True, keyword=keyword, stage="准备中…", results=[], error="",
                      note="", started=time.time(), finished=0)
    threading.Thread(target=_run, args=(keyword, n), daemon=True, name="creator-discover").start()
    return {"ok": True}


def _ask_model(keyword, n):
    """先用网页 AI 池（会联网搜索）；不可用时退回本地模型（并提示可能过时）。"""
    import agent_core as core
    prompt = PROMPT.format(today=datetime.date.today().isoformat(), kw=keyword, n=n)
    msgs = [{"role": "user", "content": prompt}]
    try:
        _set(stage="让 AI 池联网搜索「%s」最值得关注的网站和博主（约 1~3 分钟）…" % keyword)
        client = core.make_client_for("web", False, on_progress=lambda m: _set(stage="AI 池：%s" % str(m)[:60]))
        resp = client.chat.completions.create(model="web", messages=msgs, expectsJson=True, timeout=600000)
        text = (resp.choices[0].message.content or "").strip()
        if _parse(text):
            return text, ""
        raise RuntimeError("AI 池的回复里没解析出清单")
    except Exception as e:
        web_err = str(e)[:80]
    try:
        _set(stage="AI 池不可用（%s），改用本地模型…" % web_err)
        ul, m = core.prefer_local_model(True, "qwen2.5")
        client = core.make_client(True) if ul else core.make_client_for(m, ul)
        resp = client.chat.completions.create(model=m, messages=msgs)
        return ((resp.choices[0].message.content or "").strip(),
                "这次是本地模型给的清单（AI 池不可用：%s），它不能联网，可能过时，网站已逐个检查过能否打开。" % web_err)
    except Exception as e2:
        raise RuntimeError("AI 池和本地模型都没成功：%s / %s" % (web_err, str(e2)[:80]))


def _norm(u):
    return re.sub(r"^https?://(www\.|m\.)?", "", (u or "").strip()).split("?")[0].rstrip("/").lower()


def _parse(text):
    """从回复里抠出 JSON 数组 → [{name, url, platform, kind, region, why}]。平台按网址自己认（比 AI 写的类型靠谱）。"""
    if not text:
        return []
    t = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\[.*\]", t, re.S)
    if not m:
        return []
    data = None
    for cand in (m.group(0), re.sub(r",\s*([\]}])", r"\1", m.group(0))):
        try:
            data = json.loads(cand)
            break
        except Exception:
            continue
    if not isinstance(data, list):
        return []
    try:
        import creator_watch
        detect = creator_watch._detect_platform
    except Exception:
        detect = lambda u: ""
    out, seen = [], set()
    for it in data:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        if not re.match(r"^https?://[^\s/]+\.[^\s]+", url):
            continue
        key = _norm(url)
        if key in seen:
            continue
        seen.add(key)
        plat = detect(url) or "web"
        out.append({"name": str(it.get("name") or "").strip()[:40] or key.split("/")[0], "url": url,
                    "platform": plat, "kind": _KIND.get(plat, "网站"),
                    "region": str(it.get("region") or "").strip()[:4], "why": str(it.get("why") or "").strip()[:60]})
    return out


def _run(keyword, n):
    try:
        text, note = _ask_model(keyword, n)
        items = _parse(text)[:n]
        if not items:
            raise RuntimeError("没解析出清单，换个说法再搜一次")
        try:
            import creator_watch
            existing = {_norm(c.get("url")) for c in creator_watch.list_creators()}
        except Exception:
            existing = set()
        for it in items:
            it["exists"] = _norm(it["url"]) in existing
            if it["platform"] in ("web", "youtube"):
                it["status"], it["detail"] = "checking", "检查中…"
            else:
                it["status"], it["detail"] = "skip", "博主账号，加进来时再识别"
        _set(results=items, note=note, stage="找到 %d 个，正在检查网站能不能打开…" % len(items))

        def one(idx):
            it = items[idx]
            if it["status"] != "checking":
                return True
            try:
                import source_discover
                ok, why = source_discover._check(it["url"])
            except Exception as e:
                ok, why = False, str(e)[:60]
            with _lock:
                it["status"], it["detail"] = ("ok" if ok else "fail"), why
                _state["results"] = items
            return ok

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            oks = list(ex.map(one, range(len(items))))
        _set(stage="完成：找到 %d 个，%d 个能用" % (len(items), sum(1 for x in oks if x)))
    except Exception as e:
        _set(error=str(e)[:200], stage="没搜成")
    finally:
        _set(running=False, finished=time.time())
