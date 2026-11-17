"""
source_discover.py — 嗅探「按关键词找信息源」。

用户输入一个关键词（如「AI 芯片」「新能源汽车」），让网页 AI 池（GPT，会联网搜索）
找出这个领域最值得长期跟踪的 N 个信息源网站（官方 / 权威媒体 / 研究机构 / 社区…），
再逐个实际打开检查能不能访问，标出哪些已经在嗅探清单里，交给界面勾选后一键加入。

在后台线程里跑，界面轮询 status() 看进度——不占着界面的连接（浏览器对同一地址最多 6 个连接）。
"""

import re
import json
import time
import threading
import datetime
import concurrent.futures

_lock = threading.Lock()
_state = {"running": False, "keyword": "", "stage": "", "results": [], "error": "",
          "note": "", "started": 0, "finished": 0}

DEFAULT_N = 15

PROMPT = """今天是 {today}。我要长期跟踪「{kw}」这个领域的最新动态，请帮我找出这个领域里最值得关注的 {n} 个信息源网站。

要求：
1. 请先联网搜索核实：网站真实存在、现在仍在更新。绝对不要编造网址。
2. 优先这几类：官方网站/官方博客或新闻页、权威行业媒体、研究机构或实验室、头部公司、高质量社区或行业周报。国内和国外都要覆盖。
3. 每个都给能直接看到「最新文章 / 新闻列表」的那个页面网址（比如 /news、/blog、/newsroom），不要只给首页；有 RSS 也可以给 RSS 地址。
4. 按对这个领域的重要程度从高到低排序。

只输出一个 JSON 数组，不要任何其它文字、不要代码块。每一项的格式：
{{"name": "网站名称", "url": "https://...", "type": "官方/媒体/研究/社区/数据/其他", "region": "国内/国外", "why": "一句话说明为什么值得关注（20 字以内）"}}
"""


def status():
    with _lock:
        return json.loads(json.dumps(_state, ensure_ascii=False))


def _set(**kw):
    with _lock:
        _state.update(kw)


def start(keyword, n=DEFAULT_N):
    """开始一次查找（后台线程）。已经在查就返回 False。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return {"ok": False, "message": "先输入一个关键词"}
    try:
        n = max(5, min(30, int(n or DEFAULT_N)))
    except Exception:
        n = DEFAULT_N
    with _lock:
        if _state["running"]:
            return {"ok": False, "message": "上一次查找还没结束（%s）" % _state["keyword"]}
        _state.update(running=True, keyword=keyword, stage="准备中…", results=[], error="",
                      note="", started=time.time(), finished=0)
    threading.Thread(target=_run, args=(keyword, n), daemon=True, name="source-discover").start()
    return {"ok": True}


# ───────────────────────── 实际流程 ─────────────────────────
def _ask_model(keyword, n):
    """先用网页 AI 池（会联网搜索，结果最靠谱）；不可用时退回本地模型（并提示可能过时）。"""
    import agent_core as core
    prompt = PROMPT.format(today=datetime.date.today().isoformat(), kw=keyword, n=n)
    msgs = [{"role": "user", "content": prompt}]
    try:
        _set(stage="让 AI 池联网搜索「%s」的行业信息源（约 1~3 分钟）…" % keyword)
        client = core.make_client_for("web", False,
                                      on_progress=lambda m: _set(stage="AI 池：%s" % str(m)[:60]))
        resp = client.chat.completions.create(model="web", messages=msgs,
                                              expectsJson=True, timeout=600000)
        text = (resp.choices[0].message.content or "").strip()
        if _parse(text):
            return text, ""
        raise RuntimeError("AI 池的回复里没解析出网站清单")
    except Exception as e:
        web_err = str(e)[:80]
    try:
        _set(stage="AI 池不可用（%s），改用本地模型…" % web_err)
        ul, m = core.prefer_local_model(True, "qwen2.5")
        client = core.make_client(True) if ul else core.make_client_for(m, ul)
        resp = client.chat.completions.create(model=m, messages=msgs)
        return ((resp.choices[0].message.content or "").strip(),
                "这次是本地模型给的清单（AI 池不可用：%s），它不能联网，网址可能过时，已逐个检查过能否打开。" % web_err)
    except Exception as e2:
        raise RuntimeError("AI 池和本地模型都没成功：%s / %s" % (web_err, str(e2)[:80]))


def _parse(text):
    """从回复里抠出 JSON 数组，整理成 [{name,url,type,region,why}]。"""
    if not text:
        return []
    t = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\[.*\]", t, re.S)
    if not m:
        return []
    raw = m.group(0)
    data = None
    for cand in (raw, re.sub(r",\s*([\]}])", r"\1", raw)):        # 容忍结尾多逗号
        try:
            data = json.loads(cand)
            break
        except Exception:
            continue
    if not isinstance(data, list):
        return []
    out, seen = [], set()
    for it in data:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        if not re.match(r"^https?://[^\s/]+\.[^\s]+", url):
            continue
        key = re.sub(r"^https?://(www\.)?", "", url).rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name": str(it.get("name") or "").strip()[:40] or key.split("/")[0],
            "url": url,
            "type": str(it.get("type") or "").strip()[:8],
            "region": str(it.get("region") or "").strip()[:4],
            "why": str(it.get("why") or "").strip()[:60],
        })
    return out


def _check(url):
    """实际打开一次，看能不能访问（境外站自动走代理）。返回 (ok, 说明)。"""
    import web_tools as W
    try:
        page = W._fetch(url, timeout=15)
        return (True, "可访问") if len(page or "") > 200 else (False, "页面几乎是空的（可能要登录或动态加载）")
    except Exception as e:
        first = e
    try:
        page = W.fetch_browserlike(url, timeout=20)
        return (True, "可访问（浏览器方式）") if len(page or "") > 200 else (False, "页面几乎是空的")
    except Exception:
        pass
    try:
        import sniffer
        return False, sniffer._humanize_err(first, url)
    except Exception:
        return False, str(first)[:60]


def _norm(u):
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip()).rstrip("/").lower()


def _run(keyword, n):
    try:
        text, note = _ask_model(keyword, n)
        items = _parse(text)[:n]
        if not items:
            raise RuntimeError("没解析出网站清单，换个说法的关键词再试一次")
        try:
            import sniffer
            existing = {_norm(s.get("url")) for s in (sniffer.list_sources() or [])}
        except Exception:
            existing = set()
        for it in items:
            it["exists"] = _norm(it["url"]) in existing
            it["status"], it["detail"] = "checking", "检查中…"
        _set(results=items, note=note, stage="找到 %d 个，正在逐个检查能不能打开…" % len(items))

        def one(idx):
            ok, why = _check(items[idx]["url"])
            with _lock:
                items[idx]["status"] = "ok" if ok else "fail"
                items[idx]["detail"] = why
                _state["results"] = items
            return ok

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            oks = list(ex.map(one, range(len(items))))
        _set(stage="完成：%d 个信息源，%d 个能打开" % (len(items), sum(1 for x in oks if x)))
    except Exception as e:
        _set(error=str(e)[:200], stage="没找成")
    finally:
        _set(running=False, finished=time.time())
