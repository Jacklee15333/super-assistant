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

from agent_core import MEMORY_DIR, make_client_for, is_web_model
import web_tools as W

SNIFF_REPORT_DIR = MEMORY_DIR / "sniff_reports"
try:
    SNIFF_REPORT_DIR.mkdir(exist_ok=True)
except Exception:
    pass

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
    cfg = {"auto": False, "every": 6, "engine": "follow"}  # engine: follow/web/claude
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
    if cfg.get("engine") not in ("follow", "web", "claude"):
        cfg["engine"] = "follow"
    return cfg


def save_config(patch):
    cfg = get_config()
    if "auto" in (patch or {}):
        cfg["auto"] = bool(patch["auto"])
    if "every" in (patch or {}):
        cfg["every"] = patch["every"]
    if "engine" in (patch or {}):
        cfg["engine"] = patch["engine"]
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


def _diff(old, new, max_len=4500):
    old_set = set(s.strip() for s in re.split(r"[。\n]", old) if s.strip())
    parts = [s.strip() for s in re.split(r"[。\n]", new)
             if s.strip() and s.strip() not in old_set]
    return "\n".join(parts)[:max_len]


# ---------------- 提炼 ----------------
_EXTRACT_PROMPT = """下面是「{title}」这个网站这次抓取**相比上次新增/变化**的内容片段（多数是新出现的标题/条目）。
你是中文科技情报分析助手。请挑出真正值得关注的「新东西」，把每条**用中文**整理成一条有信息量的情报，归到三类之一：
- 发布：新模型、新版本、新产品上线
- 功能：新能力、新特性、新工具、新基准/数据集
- 概念：新术语、新方法、新趋势（比如 Loop、Harness 这类）

只输出一个 JSON 数组（不要别的话、不要代码块包裹），每个元素：
{{"kind":"发布|功能|概念","title":"简短中文标题（英文专有名词可保留）","summary":"用中文写 2~3 句，把这条是什么、属于哪类技术、解决什么问题或有什么意义说清楚","importance":"高|中|低"}}

写 summary 的要求（重要）：
- 片段里常常只有一句标题，信息很少。请**结合你已掌握的领域背景知识**，把这条展开解释清楚——它大概是什么、属于什么方向、为什么值得关注，让没看过原文的人也能读懂。
- 但**不要编造具体的数字、跑分、日期或结论**：这些片段里没有就不要写死，可以用「据其标题/介绍」这类措辞。
- summary 必须是通顺的中文（专有名词如 GPT、Llama、Lean 可保留），不要照抄英文、不要只写半句。
- 没有值得报的就输出：[]；广告、导航、菜单、无意义改动一律忽略。最多 6 条。

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


def _humanize_err(e, url=None):
    """把 urllib 的报错翻成人话 + 给出怎么办。给了 url 时会说明这次走没走代理，避免误导。"""
    s = str(e)
    low = s.lower()
    used_proxy = ""
    if url:
        try:
            used_proxy = W.proxy_for(url)
        except Exception:
            used_proxy = ""
    if used_proxy and ("timed out" in low or "timeout" in low or "handshake" in low
                       or "10060" in low or "refused" in low or "10061" in low):
        if "refused" in low or "10061" in low:
            return "代理 %s 拒绝连接：代理软件没开，或端口不对" % used_proxy
        return "已经走代理（%s）还是连接超时：当前代理节点访问这个站太慢或不通，换个节点再试" % used_proxy
    if url and not used_proxy and ("timed out" in low or "timeout" in low or "10060" in low):
        try:
            foreign = W.needs_proxy(url)
        except Exception:
            foreign = True
        if not foreign:
            return "连接超时：这个网站响应太慢或暂时打不开，稍后再试"
    if "403" in s:
        return "被网站反爬拦截（403）：已经走代理、也换浏览器方式重试过，这个站（Cloudflare 保护）暂时抓不了"
    if "404" in s:
        return "页面不存在（404），检查下网址对不对"
    if "401" in s:
        return "需要登录（401），抓不了"
    if "certificate" in low or "cert_verify" in low:
        return "证书校验失败—网站证书链不完整或本机缺根证书（已自动用标准证书库重试）"
    if "timed out" in low or "timeout" in low or "handshake" in low or "ssl" in low:
        return "连接超时—境外站点通常要走代理（设置→联网与代理 填上加速器地址）"
    if "getaddrinfo" in low or "name or service" in low or "name resolution" in low:
        return "域名解析失败—多半也要走代理（设置→联网与代理）"
    if "refused" in low:
        return "连接被拒—检查网址或代理设置"
    return s[:70]


def _fetch_smart(url):
    """更聪明的抓取：配了代理就优先走代理（境外站多数需要），失败再直连兜底；
    没配代理就直连。给慢/不稳的站点一次重试机会。返回 (page, via, err)。"""
    # 代理按网址自动决定：境外站一律走代理（不再直连兜底——国内直连境外站只会失败，
    # 还会把真正的错误盖掉，比如 OpenAI 对国内 IP 直接回 403）；国内站一律直连。
    try:
        via_ok = "proxy" if W.proxy_for(url) else "direct"
    except Exception:
        via_ok = "direct"
    last_err = None
    for to in (25, 18):
        try:
            page = W._fetch(url, timeout=to)
            return page, via_ok, None
        except Exception as e:
            last_err = e
            if "404" in str(e) or "401" in str(e):
                break                      # 页面不存在/要登录：再试也没用
    # 被 Cloudflare 之类拦（403）或握手失败：换「真浏览器网络指纹」再试一次
    if last_err is not None and "404" not in str(last_err):
        try:
            page = W.fetch_browserlike(url, timeout=25)
            return page, via_ok, None
        except Exception as e:
            if "403" in str(last_err) and "403" not in str(e):
                pass                       # 保留更能说明问题的 403
            else:
                last_err = e
    # 主页面打不开：试一下这个站的备用地址（RSS / 国内镜像），能读到就用
    for key, alts in _ALT_URLS.items():
        if key in (url or ""):
            for alt in alts:
                try:
                    page = W._fetch(alt, timeout=20)
                    return page, "alt:" + alt, None
                except Exception as e:
                    last_err = e
    return None, None, last_err


# 个别站点主页面重/不稳时的备用地址
_ALT_URLS = {
    "huggingface.co/blog": ["https://huggingface.co/blog/feed.xml", "https://hf-mirror.com/blog"],
}


def _scan_one(client, model, src, report):
    """抓取+对比+提炼单个源。report(status, detail) 实时回报进度。返回 (items, log)。
    status: fetching/failed/empty/first/unchanged/nodiff/extracting/found/nonew
    """
    title = src.get("title") or src.get("url")
    url = src.get("url")

    report("fetching", "正在打开链接…")
    page, via, err = _fetch_smart(url)
    if err is not None:
        report("failed", "打不开：" + _humanize_err(err, url))
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


# ============================================================
#  情报简报式：让「网页模型 AI」一个个站点自己去搜+读+总结，
#  每段自带来源超链接；全部生成完，软件再拼成一份报告。
#  —— 工作模式与「生成情报简报」完全一致。
# ============================================================
SNIFF_WEB_PROMPT = (
    "今天是 {today}。请帮我盯一下「{title}」这个站点（{url}）的最新动态（重点看最近一两周）。\n"
    "**如果你现在能联网，请打开/搜索这个网站及其官方来源**，找出它**最近新发布、新更新**的内容"
    "（新模型 / 新版本 / 新功能 / 新基准 / 新概念 / 重要公告等），用中文整理成情报。\n"
    "【正文】\n"
    "- 列出最近最值得关注的 3~6 条，每条 2~3 句：说清是什么、属于什么方向、为什么值得关注；\n"
    "- 只挑真正『新』的，过滤导航、广告、过时内容；每条尽量标出大致时间。\n"
    "【来源】正文之后另起一段，写「来源：」，用 Markdown 列表给出你参考的原文链接，"
    "格式 `- [标题](完整网址)`，网址以 http 开头、指向官方或原文页面。\n"
    "【重要】如果此刻你**确实无法联网**，不要拒绝也不要空着——基于你已掌握的关于该站点/机构的可靠信息尽力整理，"
    "开头用一句话注明「（注：本次未能联网，以下为已知信息，时效以官方为准）」；"
    "来源处给出该站官方主页即可（拿不准的具体链接别编造）。开头不要重复站点名（我会自己加）。"
)

SNIFF_READ_PROMPT = (
    "下面是从「{title}」（{url}）这个网站抓取到的页面正文。请你用中文整理出这个站点**最近值得关注的新内容**"
    "（新模型 / 新版本 / 新功能 / 新概念等）：\n"
    "- 列出 3~6 条，每条 2~3 句，说清是什么、为什么值得关注；\n"
    "- 资料里只有标题时，结合你的背景知识把它说清楚，但不要编造具体数字/日期/结论；\n"
    "- 过滤导航、广告、无意义内容。直接输出正文，不用写来源（我会统一附上原文链接）。\n\n"
    "=== 页面正文 ===\n{material}\n"
)


def _clean_web_summary(t):
    """清理网页模型回复里常见的引用角标杂质（+1/+2 之类）。"""
    t = (t or "").replace("\u00a0", " ")
    t = re.sub(r"(?m)^[ \t]*[+＋﹢][ \t]*[\d０-９]+[ \t]*$", "", t)
    t = re.sub(r"[ \t]*[+＋﹢][ \t]*[\d０-９]+(?=[\s，。；、,\.\)\]）】]|$)", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def generate_sniff_report(use_local=False, model="web", verbose=False,
                          on_step=None, on_detail=None):
    """像「生成情报简报」一样：让网页模型 AI 一个个站点自己去搜索/读取/总结，
    每段自带来源超链接；全部生成完，再拼成一份中文报告返回。
    on_step：站点级里程碑；on_detail：当前站点的实时明细（网页模型活动）。"""
    def _step(m):
        if on_step:
            try: on_step(m)
            except Exception: pass
    def _detail(m):
        if on_detail:
            try: on_detail(m)
            except Exception: pass

    ensure_seeded()
    sources = [s for s in _load_sources() if s.get("enabled", True)]
    if not sources:
        return "（嗅探清单是空的，或都关掉了。先去左边添加你关心的网站。）"

    _step("准备开始，连接模型…")
    try:
        client = make_client_for(model, use_local, on_progress=_detail)
    except Exception as e:
        return f"连接模型出错：{e}"

    try:
        web = is_web_model(model)
    except Exception:
        web = (model == "web")

    ts = datetime.datetime.now()
    sections = []
    todo = sources[:12]          # 控制时间，最多 12 个站
    n = len(todo)
    offline_hits = 0             # 有多少个站点是「未能联网、用旧知识凑」的
    for i, src in enumerate(todo, 1):
        title = src.get("title") or src.get("url")
        url = src.get("url", "")
        _step(f"调研第 {i}/{n} 个网站：{title}")
        summary = ""
        try:
            if web:
                # 网页模型：让它自己联网搜该站最新动态并总结（来源由 AI 在文末自带）
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user",
                               "content": SNIFF_WEB_PROMPT.format(
                                   title=title, url=url,
                                   today=datetime.date.today().isoformat())}],
                )
                summary = _clean_web_summary(resp.choices[0].message.content or "")
            else:
                # 非网页模型兜底：软件抓正文再喂给模型
                _detail("抓取网页内容中…")
                page, via, err = _fetch_smart(url)
                text = _normalize(W._extract_text(page)) if page else ""
                if not text:
                    summary = f"（这个站点这次没抓到内容{('：' + _humanize_err(err, url)) if err else ''}。）"
                else:
                    _detail("模型提炼中…")
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user",
                                   "content": SNIFF_READ_PROMPT.format(
                                       title=title, url=url, material=text[:6000])}],
                    )
                    summary = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            summary = f"（这个站点生成出错：{e}）"

        # 网页模型若回了「本次未能联网」，说明它其实没在浏览 → 这条是旧知识、时效不可信
        if web and summary and ("未能联网" in summary or "无法联网" in summary):
            offline_hits += 1

        block = [f"## 📡 {title}", "", summary or "（暂无可报内容）"]
        # 非网页模型这边软件帮忙附上站点原文链接（网页模型会自己带来源）
        if (not web) and url:
            block += ["", f"- [打开 {title}]({url})"]
        block.append("\n---")
        sections.append("\n".join(block))

    _step("全部站点整理完成，正在拼合成报告…")
    body = "\n\n".join(sections).rstrip("-\n ")
    mode = "网页模型逐站搜集" if web else "软件抓取 + 模型提炼"
    header = (f"# 📡 AI 嗅探简报\n\n"
              f"> {ts.strftime('%Y-%m-%d %H:%M')} 生成 · {mode} · 共 {n} 个站点\n")
    # 关键告警：网页模型没真正联网 → 内容是旧训练知识，时效不可信，醒目提示用户去修
    if web and offline_hits:
        header += (
            f"\n> ⚠️ **注意：本次有 {offline_hits}/{n} 个站点未能真正联网**，"
            f"这些内容来自模型的旧知识（可能停留在过去年份），**不是最新动态**。\n"
            f"> 原因通常是网页模型没装好浏览器内核、或没开「联网搜索」开关。"
            f"修复办法：① 确认已安装 playwright 浏览器内核；"
            f"② 在「网页大模型」设置里**打开 enableSearch / 联网搜索**；"
            f"③ 去设置点「测试网页模型」确认能正常联网后再嗅探。\n"
            f"> 想立刻拿到真·最新信息，也可以把嗅探模型切到**软件抓取 + 本地模型**模式"
            f"（软件会真去抓网页原文）。\n")
    report = header + "\n" + body

    # 存档一份，方便回看
    try:
        fn = SNIFF_REPORT_DIR / f"sniff-report-{ts.strftime('%Y%m%d-%H%M%S')}.md"
        fn.write_text(report, encoding="utf-8")
    except Exception:
        pass
    return report


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

    # 嗅探用哪个模型：follow=跟随调用方；web=网页模型（更强，但慢）；claude=第一个 Claude 配置
    engine = get_config().get("engine", "follow")
    if engine == "web":
        model, use_local = "web", False
    elif engine == "claude":
        model, use_local = "claude", False
    else:
        # 「快速」就该快：本机有本地模型就用本地模型，不跟着聊天里的网页模型走
        # （网页模型要逐站换卡、排队，8 个站能拖上好几分钟）
        try:
            import agent_core as _ac
            use_local, model = _ac.prefer_local_model(use_local, model)
        except Exception:
            pass
    try:
        client = make_client_for(model, use_local)
    except Exception as e:
        # 选的模型连不上（比如没配网页模型/Claude）→ 退回本地默认，别让整轮失败
        _run_state["stage"] = f"所选模型不可用（{e}），改用默认模型"
        model, use_local = "qwen3:14b", True
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
        added_here = 0
        for it in items:
            key = _item_key(it.get("link", ""), it.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            it["key"] = key
            it["ts"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            feed.append(it)
            new_items.append(it)
            added_here += 1
        # 这个源有新内容就立刻落盘，前端下次轮询（约1.5秒）就能看到，不用等整轮跑完
        if added_here:
            _save_feed(feed)

    if new_items:
        _save_feed(feed)
        notable = [i for i in new_items if i.get("importance") in ("高", "中")]
        if notable:
            try:
                import push_serverchan
                body = "\n\n".join(
                    f"**[{i['kind']}] {i['title']}**\n{i.get('summary','')}\n"
                    f"[查看原文]({i.get('link','')}) · 来自 {i.get('source_title','')}"
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
