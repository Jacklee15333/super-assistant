"""
sniffer.py — AI 嗅探（情报雷达）

「检查竞品变化」的升级版：盯一批你关心的网站（默认是各家 AI 官方博客/发布页），
定时抓取 → 和上次快照对比 → 只在有变化时，让模型把「新东西」提炼出来并分三类：
  🆕 发布（新模型/新版本）  🧩 功能（新能力）  💡 概念（新术语/新玩法，如 Loop、Harness）
每条带标题、一句话说明、原文链接、重要度。已报过的不重复打扰（去重）。

复用 competitor_watch 的「抓页面→快照对比→只处理变化」思路，复用 web_tools 抓取。
可手动「立即嗅探」，也可挂到心跳上自动跑（界面开关）。

数据都存本地：
  memory/sniff_sources.json   要嗅探的网站清单 [{id,title,url,enabled}]
  memory/sniff_feed.json      嗅探到的内容时间线 [{...}]
  memory/sniff_config.json    {auto: bool, every: int}  自动嗅探开关 + 每隔几次心跳跑一次
  memory/snapshots/sniff-*.txt 每个网站的上次快照
"""

import re
import json
import time
import hashlib
import datetime
from pathlib import Path

from agent_core import MEMORY_DIR, make_client_for
import web_tools as W

SNAP_DIR = MEMORY_DIR / "snapshots"
SNAP_DIR.mkdir(exist_ok=True)
SOURCES_PATH = MEMORY_DIR / "sniff_sources.json"
FEED_PATH = MEMORY_DIR / "sniff_feed.json"
CONFIG_PATH = MEMORY_DIR / "sniff_config.json"

MAX_FEED = 200       # 时间线最多留这么多条
MAX_SOURCES = 30     # 最多盯这么多站

# 默认内置的 AI 资讯源（首次运行写入；用户可增删）
_DEFAULT_SOURCES = [
    ("OpenAI 新闻", "https://openai.com/news/"),
    ("Anthropic 新闻", "https://www.anthropic.com/news"),
    ("Google DeepMind 博客", "https://deepmind.google/discover/blog/"),
    ("Hugging Face 博客", "https://huggingface.co/blog"),
    ("Qwen 博客", "https://qwenlm.github.io/blog/"),
    ("Meta AI 博客", "https://ai.meta.com/blog/"),
    ("Hacker News", "https://news.ycombinator.com/"),
    ("arXiv cs.AI 最新", "https://arxiv.org/list/cs.AI/recent"),
]


# ---------------- 配置 ----------------
def get_config():
    cfg = {"auto": False, "every": 6}  # 默认不自动；开了的话每 6 次心跳嗅探一次
    try:
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    try:
        cfg["every"] = max(1, min(int(cfg["every"]), 100))
    except Exception:
        cfg["every"] = 6
    cfg["auto"] = bool(cfg.get("auto", False))
    return cfg


def save_config(patch):
    cfg = get_config()
    if "auto" in (patch or {}):
        cfg["auto"] = bool(patch["auto"])
    if "every" in (patch or {}):
        cfg["every"] = patch["every"]
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return get_config()


def auto_enabled():
    return get_config().get("auto", False)


def should_run_now(beat_count):
    cfg = get_config()
    if not cfg.get("auto"):
        return False
    every = cfg.get("every", 6)
    return beat_count > 0 and (beat_count % every == 0)


# ---------------- 源清单 ----------------
def _new_id():
    return hashlib.md5((str(time.time()) + str(id(object()))).encode()).hexdigest()[:8]


def ensure_seeded():
    if SOURCES_PATH.exists():
        return
    seeded = [{"id": _new_id(), "title": t, "url": u, "enabled": True, "category": "AI动态"}
              for t, u in _DEFAULT_SOURCES]
    _save_sources(seeded)


def _load_sources():
    try:
        if SOURCES_PATH.exists():
            data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                # 兼容老数据：没有 category 的补一个默认类别
                for s in data:
                    if not s.get("category"):
                        s["category"] = "AI动态"
                return data
    except Exception:
        pass
    return []


def _save_sources(srcs):
    try:
        SOURCES_PATH.write_text(json.dumps(srcs[:MAX_SOURCES], ensure_ascii=False, indent=2),
                                encoding="utf-8")
    except Exception:
        pass


def list_sources():
    ensure_seeded()
    return _load_sources()


def list_categories():
    """返回各类别及其统计：[{name, total, enabled}]，按出现顺序。"""
    srcs = list_sources()
    order, stat = [], {}
    for s in srcs:
        c = s.get("category") or "AI动态"
        if c not in stat:
            stat[c] = {"name": c, "total": 0, "enabled": 0}
            order.append(c)
        stat[c]["total"] += 1
        if s.get("enabled", True):
            stat[c]["enabled"] += 1
    return [stat[c] for c in order]


def add_source(title, url, category="AI动态"):
    title = (title or "").strip()
    url = (url or "").strip()
    category = (category or "").strip() or "AI动态"
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "message": "网址要以 http:// 或 https:// 开头"}
    if not title:
        title = re.sub(r"^https?://", "", url).split("/")[0]
    srcs = _load_sources()
    if any(s.get("url") == url for s in srcs):
        return {"ok": False, "message": "这个网址已经在清单里了"}
    if len(srcs) >= MAX_SOURCES:
        return {"ok": False, "message": f"最多盯 {MAX_SOURCES} 个站"}
    srcs.append({"id": _new_id(), "title": title, "url": url,
                 "enabled": True, "category": category})
    _save_sources(srcs)
    return {"ok": True}


def set_category(sid, category):
    category = (category or "").strip() or "AI动态"
    srcs = _load_sources()
    for s in srcs:
        if s.get("id") == sid:
            s["category"] = category
    _save_sources(srcs)
    return {"ok": True}


def toggle_category(category, enabled):
    """整类启用/停用。"""
    srcs = _load_sources()
    for s in srcs:
        if (s.get("category") or "AI动态") == category:
            s["enabled"] = bool(enabled)
    _save_sources(srcs)
    return {"ok": True}


def delete_source(sid):
    srcs = [s for s in _load_sources() if s.get("id") != sid]
    _save_sources(srcs)
    return {"ok": True}


def toggle_source(sid, enabled):
    srcs = _load_sources()
    for s in srcs:
        if s.get("id") == sid:
            s["enabled"] = bool(enabled)
    _save_sources(srcs)
    return {"ok": True}


# ---------------- 快照 + 抓取 ----------------
def _snap_path(url):
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
    return SNAP_DIR / f"sniff-{h}.txt"


def _normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _diff(old, new, max_len=2500):
    old_set = set(s.strip() for s in re.split(r"[。\n]", old) if s.strip())
    parts = [s.strip() for s in re.split(r"[。\n]", new)
             if s.strip() and s.strip() not in old_set]
    return "\n".join(parts)[:max_len]


# ---------------- 提炼 ----------------
_EXTRACT_PROMPT = """下面是「{title}」这个 AI 相关网站这次抓取**相比上次新增/变化**的内容片段。
请从中挑出真正值得关注的「新东西」，每条归到三类之一：
- 发布：新模型、新版本、新产品上线
- 功能：新能力、新特性、新工具
- 概念：新术语、新方法、新趋势（比如 Loop、Harness 这类）

只输出一个 JSON 数组（不要别的话、不要代码块包裹），每个元素：
{{"kind":"发布|功能|概念","title":"简短标题","summary":"一句话说清是什么","importance":"高|中|低"}}
没有值得报的就输出：[]
只挑 AI 相关、确实是新出现的；广告、导航、无意义改动一律忽略。最多 6 条。

=== 变化片段 ===
{diff}
"""


def _extract_items(client, model, title, diff):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": _EXTRACT_PROMPT.format(title=title, diff=diff)}],
        )
        out = (resp.choices[0].message.content or "").strip()
    except Exception:
        return []
    m = re.search(r"\[[\s\S]*\]", out)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    items = []
    if isinstance(arr, list):
        for it in arr:
            if not isinstance(it, dict):
                continue
            kind = it.get("kind", "概念")
            if kind not in ("发布", "功能", "概念"):
                kind = "概念"
            imp = it.get("importance", "中")
            if imp not in ("高", "中", "低"):
                imp = "中"
            items.append({
                "kind": kind,
                "title": (it.get("title") or "").strip()[:120],
                "summary": (it.get("summary") or "").strip()[:300],
                "importance": imp,
            })
    return [i for i in items if i["title"]]


# ---------------- 时间线（feed）+ 去重 ----------------
def _load_feed():
    try:
        if FEED_PATH.exists():
            data = json.loads(FEED_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_feed(feed):
    try:
        FEED_PATH.write_text(json.dumps(feed[-MAX_FEED:], ensure_ascii=False, indent=2),
                             encoding="utf-8")
    except Exception:
        pass


def _item_key(source_url, title):
    return hashlib.md5((source_url + "|" + title).encode("utf-8")).hexdigest()[:16]


def get_feed(limit=60):
    feed = _load_feed()
    return list(reversed(feed[-limit:]))  # 最新在前


def clear_feed():
    _save_feed([])
    return True


# ---------------- 主流程（带实时逐源进度）----------------
import threading as _threading
_run_state = {"running": False, "last_log": "", "last_new": 0, "stage": "", "progress": []}


def is_running():
    return _run_state["running"]


def get_run_state():
    # 浅拷贝 + progress 列表拷贝，避免并发读写同一引用
    st = dict(_run_state)
    st["progress"] = list(_run_state.get("progress", []))
    return st


def _host_of(url):
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url
    except Exception:
        return url


def _humanize_err(e):
    """把 urllib 的报错翻成人话 + 给出怎么办。"""
    s = str(e)
    low = s.lower()
    if "403" in s:
        return "被网站反爬拦截（403）—这类站点（如 Cloudflare 保护）普通抓取打不开"
    if "404" in s:
        return "页面不存在（404），检查下网址对不对"
    if "401" in s:
        return "需要登录（401），抓不了"
    if "timed out" in low or "timeout" in low or "handshake" in low or "ssl" in low:
        return "连接超时—境外站点通常要走代理（设置→联网与代理 填上加速器地址）"
    if "getaddrinfo" in low or "name or service" in low or "name resolution" in low:
        return "域名解析失败—多半也要走代理（设置→联网与代理）"
    if "refused" in low:
        return "连接被拒—检查网址或代理设置"
    return s[:70]


def _fetch_smart(url):
    """更聪明的抓取：配了代理就优先走代理（境外站多数需要），失败再直连兜底；
    没配代理就直连。返回 (page, via, err)。via ∈ {'proxy','direct'}。"""
    try:
        has_proxy = bool(W._read_proxy())
    except Exception:
        has_proxy = False
    # 配了代理 → 先代理后直连；没配 → 只直连
    attempts = [(True, 18), (False, 10)] if has_proxy else [(False, 15)]
    last_err = None
    for use_proxy, to in attempts:
        try:
            page = W._fetch(url, timeout=to, use_proxy=use_proxy)
            return page, ("proxy" if use_proxy else "direct"), None
        except Exception as e:
            last_err = e
    return None, None, last_err


def _scan_one(client, model, src, report):
    """抓取+对比+提炼单个源。report(status, detail) 实时回报进度。返回 (items, log)。
    status: fetching/failed/empty/first/unchanged/nodiff/extracting/found/nonew
    """
    title = src.get("title") or src.get("url")
    url = src.get("url")

    report("fetching", "正在打开链接…")
    page, via, err = _fetch_smart(url)
    if err is not None:
        report("failed", "打不开：" + _humanize_err(err))
        return [], f"[{title}] 抓取失败：{err}"
    text = _normalize(W._extract_text(page))
    via_note = "（经代理）" if via == "proxy" else ""

    nchar = len(text)
    if not text:
        report("empty", f"连上了{via_note}，但抓不到正文（可能是动态加载页面）")
        return [], f"[{title}] 读不到正文（可能是动态页面），跳过。"

    snap = _snap_path(url)
    if not snap.exists():
        snap.write_text(text, encoding="utf-8")
        report("first", f"首次访问{via_note} · 读到 {nchar} 字 · 记录快照（下次起对比）")
        return [], f"[{title}] 首次记录快照，下次起对比。"

    old = snap.read_text(encoding="utf-8", errors="replace")
    if old == text:
        report("unchanged", f"读到 {nchar} 字{via_note} · 和上次一样，无变化")
        return [], f"[{title}] 无变化。"
    diff = _diff(old, text)
    snap.write_text(text, encoding="utf-8")
    if not diff:
        report("nodiff", f"读到 {nchar} 字{via_note} · 有细微改动但无实质内容")
        return [], f"[{title}] 有细微变动但无实质内容。"

    report("extracting", f"读到 {nchar} 字{via_note} · 发现变化，正在提炼…")
    items = _extract_items(client, model, title, diff)
    if not items:
        report("nonew", "有变化，但没提炼出值得报的新内容")
        return [], f"[{title}] 有变化但没提炼出值得报的新内容。"
    cat = src.get("category") or "AI动态"
    for it in items:
        it["source_title"] = title
        it["link"] = url
        it["category"] = cat
    report("found", f"提炼到 {len(items)} 条新内容")
    return items, f"[{title}] 发现 {len(items)} 条新内容。"


def run_sniff(use_local=True, model="qwen2.5", verbose=False):
    """嗅探所有启用的源。返回 (新增条目列表, 日志文本)。新增高/中重要度的会推送。
    过程中实时写 _run_state['progress']，前端轮询 /sniff/feed 拿到。"""
    ensure_seeded()
    sources = [s for s in _load_sources() if s.get("enabled", True)]
    # 初始化进度列表：每个源一行，先都排队
    prog = [{"title": s.get("title") or s.get("url"),
             "host": _host_of(s.get("url")),
             "category": s.get("category") or "AI动态",
             "status": "queued", "detail": "排队中…"} for s in sources]
    _run_state["progress"] = prog
    if not sources:
        return [], "（嗅探清单是空的，或都关掉了）"

    client = make_client_for(model, use_local)
    feed = _load_feed()
    seen = set(it.get("key") for it in feed)
    new_items, logs = [], []

    for idx, src in enumerate(sources[:MAX_SOURCES]):
        if verbose:
            print(f"  嗅探：{src.get('title')}")

        def report(status, detail, _i=idx):
            try:
                _run_state["progress"][_i]["status"] = status
                _run_state["progress"][_i]["detail"] = detail
            except Exception:
                pass

        _run_state["stage"] = f"正在嗅探（{idx + 1}/{len(sources)}）：{src.get('title')}"
        items, msg = _scan_one(client, model, src, report)
        logs.append(msg)
        for it in items:
            key = _item_key(it.get("link", ""), it.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            it["key"] = key
            it["ts"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            feed.append(it)
            new_items.append(it)

    if new_items:
        _save_feed(feed)
        notable = [i for i in new_items if i.get("importance") in ("高", "中")]
        if notable:
            try:
                import push_serverchan
                body = "\n\n".join(
                    f"[{i['kind']}] {i['title']}\n{i.get('summary','')}\n{i.get('link','')}"
                    for i in notable[:10])
                push_serverchan.push(f"AI 嗅探到 {len(notable)} 条新动态", body[:2000])
            except Exception:
                pass

    return new_items, "\n".join(logs)


def start_async(use_local=True, model="qwen2.5"):
    """后台跑一次嗅探，立即返回。前端轮询 /sniff/feed 看实时逐源进度。"""
    if _run_state["running"]:
        return {"ok": False, "message": "正在嗅探中，稍等。"}
    _run_state.update({"running": True, "stage": "准备开始…", "last_new": 0, "progress": []})

    def _job():
        try:
            new_items, logs = run_sniff(use_local=use_local, model=model)
            _run_state["last_log"] = logs
            _run_state["last_new"] = len(new_items)
            _run_state["stage"] = (f"完成 · 发现 {len(new_items)} 条新内容"
                                   if new_items else "完成 · 这次没有新内容")
        except Exception as e:
            _run_state["stage"] = f"出错：{e}"
            _run_state["last_log"] = str(e)
        finally:
            _run_state["running"] = False

    t = _threading.Thread(target=_job, daemon=True)
    t.start()
    return {"ok": True}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", action="store_true")
    ap.add_argument("--model", default="qwen2.5")
    args = ap.parse_args()
    items, logs = run_sniff(use_local=not args.cloud, model=args.model, verbose=True)
    print("\n--- 日志 ---\n" + logs)
    print(f"\n--- {len(items)} 条新内容 ---")
    for i in items:
        print(f"[{i['kind']}/{i['importance']}] {i['title']} — {i.get('summary','')}")
