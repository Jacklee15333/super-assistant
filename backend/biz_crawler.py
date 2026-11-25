"""超能小助 · 商业 · 市场雷达（v156 新增）

「商业」里「市场实时」那一面的数据从这里来：小助的爬虫按一张信息源清单，定时去网上抓最新的内容——
  · 网站：财经商业媒体、大公司官网的新闻页、各行业头部媒体、政策和统计数据发布页。
    有 RSS 就读 RSS（带发布时间）；没有就从网页里挑「像文章」的链接（site_watch 的办法）；
    普通方式打不开、被拦、或只抓到空壳（动态网页）时，用 Scrapling 补救（快速模式 → 真浏览器模式），哪种管用记下来。
  · 关键词：公司名、行业、话题。去新闻搜索抓最新报道（Google 新闻 / 必应新闻的 RSS，都不行再用百度资讯）。
不用 AI：抓到的标题由 biz_intel 按行业分类表归类，所以可以一直开着、不占 AI 池。

数据都在 memory/biz/：
  radar_sources.json  信息源清单（第一次用时按推荐清单放进一批常用的）
  radar_feed.json     抓到的内容（留 45 天，最多 8000 条）
  radar_seen.json     抓过的链接（去重用）
  radar_config.json   {auto, every, last_run, sched_from}：自动更新开关、每隔几分钟（最短 5 分钟）
"""
from __future__ import annotations

import datetime
import email.utils
import hashlib
import html as _html
import json
import os
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import agent_core as _core
    MEM = Path(_core.MEMORY_DIR)
except Exception:
    MEM = Path(__file__).resolve().parent / "memory"

BIZ_DIR = MEM / "biz"
SRC_FILE = BIZ_DIR / "radar_sources.json"
FEED_FILE = BIZ_DIR / "radar_feed.json"
SEEN_FILE = BIZ_DIR / "radar_seen.json"
CFG_FILE = BIZ_DIR / "radar_config.json"
RUNS_FILE = BIZ_DIR / "radar_runs.json"      # v157：每一轮的抓取记录（结果报告用），留最近 40 轮
KEEP_DAYS = 45
MAX_ITEMS = 8000
PER_SOURCE = 40
WORKERS = 4
FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"

GROUPS = [
    ("news", "财经商业媒体", "综合报道各行各业的新闻和快讯"),
    ("corp", "大公司官网", "大公司自己发的新闻稿和博客"),
    ("corpkw", "大公司动态", "按公司名搜新闻：别人怎么报道它"),
    ("media", "行业头部媒体", "各个行业的专业媒体"),
    ("indkw", "行业热词", "按行业或话题搜最新新闻"),
    ("policy", "政策与数据", "政府政策和统计数据发布"),
    ("global", "海外科技商业", "国外的科技和商业新闻（多半要代理）"),
    ("mine", "我自己加的", "你自己加进来的网站和关键词"),
]
GROUP_NAME = {k: n for k, n, _d in GROUPS}

# 推荐清单：(编号, 名字, 类型 site/kw, 网址或关键词, 分组, 相关行业, 一句话, 第一次就放进清单)
CATALOG = [
    ("36kr", "36氪", "site", "https://36kr.com/", "news", [], "创投、科技公司和新经济，快讯多", True),
    ("wallstreetcn", "华尔街见闻", "site", "https://wallstreetcn.com/news/global", "news", [], "全球市场、宏观和公司要闻", True),
    ("cls", "财联社电报", "site", "https://www.cls.cn/telegraph", "news", [], "上市公司和产业快讯，更新最快", True),
    ("yicai", "第一财经", "site", "https://www.yicai.com/news/", "news", [], "宏观、产业和公司新闻", True),
    ("jiemian", "界面新闻", "site", "https://www.jiemian.com/", "news", [], "商业和公司报道", True),
    ("huxiu", "虎嗅", "site", "https://www.huxiu.com/", "news", [], "商业科技评论和公司深度稿", True),
    ("tmtpost", "钛媒体", "site", "https://www.tmtpost.com/", "news", [], "科技产业资讯", True),
    ("ithome", "IT之家", "site", "https://www.ithome.com/", "news", ["电子/消费电子"], "数码、互联网和科技快讯", True),
    ("thepaper", "澎湃新闻", "site", "https://www.thepaper.cn/", "news", [], "时政、财经综合新闻", False),
    ("21jingji", "21世纪经济报道", "site", "https://www.21jingji.com/", "news", [], "产业和区域经济", False),
    ("sinafin", "新浪财经", "site", "https://finance.sina.com.cn/", "news", [], "财经综合门户", False),
    ("stcn", "证券时报网", "site", "https://www.stcn.com/", "news", ["非银金融/证券"], "资本市场和上市公司", False),
    ("eeo", "经济观察网", "site", "https://www.eeo.com.cn/", "news", [], "商业深度报道", False),
    ("nbd", "每日经济新闻", "site", "https://www.nbd.com.cn/", "news", [], "财经和公司新闻", False),
    ("latepost", "晚点 LatePost", "site", "https://www.latepost.com/", "news", [], "大公司内幕和深度报道", False),

    ("huawei", "华为新闻", "site", "https://www.huawei.com/cn/news", "corp", ["通信/通信设备", "t:chip"], "华为官方发布", True),
    ("apple", "Apple Newsroom", "site", "https://www.apple.com/newsroom/", "corp", ["电子/消费电子"], "苹果官方新闻稿", True),
    ("nvidia", "NVIDIA 新闻", "site", "https://nvidianews.nvidia.com/", "corp", ["电子/半导体", "t:compute"], "英伟达官方新闻稿", True),
    ("microsoft", "微软新闻", "site", "https://news.microsoft.com/", "corp", ["计算机/软件开发"], "微软官方新闻", True),
    ("google", "Google 博客", "site", "https://blog.google/", "corp", ["t:ai"], "谷歌官方博客", True),
    ("openai", "OpenAI 新闻", "site", "https://openai.com/news/", "corp", ["t:ai"], "OpenAI 官方发布（要代理）", False),
    ("anthropic", "Anthropic 新闻", "site", "https://www.anthropic.com/news", "corp", ["t:ai"], "Anthropic 官方发布", False),
    ("meta", "Meta 新闻", "site", "https://about.fb.com/news/", "corp", ["传媒/社交"], "Meta 官方新闻", False),
    ("amazon", "亚马逊新闻", "site", "https://www.aboutamazon.com/news", "corp", ["商贸零售/互联网电商"], "亚马逊官方新闻", False),
    ("samsung", "三星新闻", "site", "https://news.samsung.com/global/", "corp", ["电子/消费电子", "电子/半导体"], "三星官方新闻", False),

    ("k-byd", "比亚迪", "kw", "比亚迪", "corpkw", ["汽车/乘用车", "t:ev"], "", True),
    ("k-catl", "宁德时代", "kw", "宁德时代", "corpkw", ["电力设备/电池"], "", True),
    ("k-xiaomi", "小米", "kw", "小米集团", "corpkw", ["电子/消费电子", "汽车/乘用车"], "", True),
    ("k-alibaba", "阿里巴巴", "kw", "阿里巴巴", "corpkw", ["商贸零售/互联网电商", "计算机/IT服务"], "", True),
    ("k-tencent", "腾讯", "kw", "腾讯", "corpkw", ["传媒/游戏", "传媒/社交"], "", True),
    ("k-bytedance", "字节跳动", "kw", "字节跳动", "corpkw", ["传媒/数字媒体"], "", True),
    ("k-meituan", "美团", "kw", "美团", "corpkw", ["社会服务/本地生活服务"], "", True),
    ("k-nvidia", "英伟达", "kw", "英伟达", "corpkw", ["电子/半导体", "t:compute"], "", True),
    ("k-huawei", "华为", "kw", "华为", "corpkw", ["通信/通信设备"], "", False),
    ("k-jd", "京东", "kw", "京东", "corpkw", ["商贸零售/互联网电商"], "", False),
    ("k-pdd", "拼多多", "kw", "拼多多 Temu", "corpkw", ["商贸零售/互联网电商"], "", False),
    ("k-baidu", "百度", "kw", "百度", "corpkw", ["t:ai"], "", False),
    ("k-apple", "苹果公司", "kw", "苹果公司", "corpkw", ["电子/消费电子"], "", False),
    ("k-tesla", "特斯拉", "kw", "特斯拉", "corpkw", ["汽车/乘用车", "t:ev"], "", False),
    ("k-tsmc", "台积电", "kw", "台积电", "corpkw", ["电子/半导体"], "", False),

    ("jiqizhixin", "机器之心", "site", "https://www.jiqizhixin.com/", "media", ["t:ai"], "AI 技术和产业", True),
    ("qbitai", "量子位", "site", "https://www.qbitai.com/", "media", ["t:ai"], "AI 新闻和前沿", True),
    ("leiphone", "雷峰网", "site", "https://www.leiphone.com/", "media", ["t:ai"], "AI、智能驾驶和硬科技", False),
    ("zhidx", "智东西", "site", "https://zhidx.com/", "media", ["t:ai", "电子/半导体"], "AI、芯片和智能硬件产业链", False),
    ("laoyaoba", "爱集微", "site", "https://www.laoyaoba.com/", "media", ["电子/半导体"], "半导体和芯片产业", True),
    ("eetchina", "电子工程专辑", "site", "https://www.eet-china.com/", "media", ["电子/半导体"], "电子和半导体技术产业", False),
    ("gasgoo", "盖世汽车", "site", "https://auto.gasgoo.com/", "media", ["汽车/汽车零部件", "汽车/乘用车"], "汽车产业链新闻", True),
    ("d1ev", "第一电动网", "site", "https://www.d1ev.com/", "media", ["t:ev"], "新能源汽车", False),
    ("bjx", "北极星电力网", "site", "https://news.bjx.com.cn/", "media", ["公用事业/电力", "t:energy"], "电力、光伏和储能", True),
    ("linkshop", "联商网", "site", "http://www.linkshop.com/news/", "media", ["商贸零售/一般零售"], "零售和消费", True),
    ("winshang", "赢商网", "site", "https://news.winshang.com/", "media", ["房地产/房地产服务", "商贸零售/一般零售"], "商业地产和连锁品牌", False),
    ("ebrun", "亿邦动力", "site", "https://www.ebrun.com/", "media", ["商贸零售/互联网电商"], "电商和品牌", True),
    ("cifnews", "雨果跨境", "site", "https://www.cifnews.com/", "media", ["t:crossborder"], "跨境电商", False),
    ("vcbeat", "动脉网", "site", "https://vcbeat.top/", "media", ["医药生物/医疗服务"], "医疗健康产业和投融资", True),
    ("cnhealthcare", "健康界", "site", "https://www.cn-healthcare.com/", "media", ["医药生物/医疗服务"], "医院和医药产业", False),
    ("youxiputao", "游戏葡萄", "site", "https://youxiputao.com/", "media", ["传媒/游戏"], "游戏产业", True),
    ("digitaling", "数英", "site", "https://www.digitaling.com/", "media", ["传媒/广告营销"], "广告、品牌和营销案例", False),
    ("ggrobot", "高工机器人", "site", "https://www.gg-robot.com/", "media", ["机械设备/自动化设备", "t:robot"], "机器人产业", False),
    ("duozhi", "多知", "site", "https://www.duozhi.com/", "media", ["社会服务/教育"], "教育行业", False),
    ("pedaily", "投资界", "site", "https://news.pedaily.cn/", "media", [], "创投和融资", False),
    ("guandian", "观点地产网", "site", "https://www.guandian.cn/", "media", ["房地产/房地产开发"], "房地产行业", False),
    ("cs", "中国证券报", "site", "https://www.cs.com.cn/", "media", ["非银金融/证券"], "证券和上市公司", False),

    ("k-canyin", "餐饮行业", "kw", "餐饮行业", "indkw", ["社会服务/酒店餐饮"], "", True),
    ("k-lowalt", "低空经济", "kw", "低空经济", "indkw", ["t:lowalt"], "", True),
    ("k-robot", "人形机器人", "kw", "人形机器人", "indkw", ["t:robot"], "", True),
    ("k-tea", "新茶饮", "kw", "新茶饮", "indkw", ["t:tea"], "", False),
    ("k-yuzhicai", "预制菜", "kw", "预制菜", "indkw", ["食品饮料/食品加工"], "", False),
    ("k-space", "商业航天", "kw", "商业航天", "indkw", ["t:space"], "", False),
    ("k-cross", "跨境电商", "kw", "跨境电商", "indkw", ["t:crossborder"], "", False),
    ("k-pet", "宠物经济", "kw", "宠物经济", "indkw", ["t:pet"], "", False),
    ("k-silver", "银发经济", "kw", "银发经济", "indkw", ["t:silver"], "", False),
    ("k-storage", "储能", "kw", "储能 行业", "indkw", ["t:energy"], "", False),
    ("k-drug", "创新药", "kw", "创新药", "indkw", ["t:biotech"], "", False),
    ("k-baijiu", "白酒行业", "kw", "白酒行业", "indkw", ["食品饮料/白酒"], "", False),
    ("k-house", "楼市", "kw", "楼市 房价", "indkw", ["房地产/房地产开发"], "", False),
    ("k-consume", "新消费", "kw", "新消费 品牌", "indkw", ["t:newcons"], "", False),

    ("gov", "中国政府网", "site", "https://www.gov.cn/", "policy", [], "国务院政策文件和要闻", True),
    ("stats", "国家统计局·最新发布", "site", "https://www.stats.gov.cn/sj/zxfb/", "policy", [], "宏观经济数据（CPI、GDP、工业、消费）", True),
    ("ndrc", "国家发展改革委", "site", "https://www.ndrc.gov.cn/", "policy", [], "产业政策和发展规划", False),
    ("miit", "工业和信息化部", "site", "https://www.miit.gov.cn/", "policy", [], "制造业、通信和 AI 产业政策", False),
    ("mofcom", "商务部", "site", "http://www.mofcom.gov.cn/", "policy", ["商贸零售/贸易"], "外贸、消费和商务政策", False),
    ("pbc", "中国人民银行", "site", "http://www.pbc.gov.cn/", "policy", ["银行/国有大型银行"], "货币政策和金融数据", False),
    ("csrc", "中国证监会", "site", "http://www.csrc.gov.cn/", "policy", ["非银金融/证券"], "资本市场监管", False),

    ("techcrunch", "TechCrunch", "site", "https://techcrunch.com/", "global", [], "创业融资和科技公司", False),
    ("theverge", "The Verge", "site", "https://www.theverge.com/", "global", [], "科技产品和平台", False),
    ("hn", "Hacker News", "site", "https://news.ycombinator.com/", "global", [], "硅谷工程师和创业者在讨论什么", False),
    ("cnbctech", "CNBC 科技", "site", "https://www.cnbc.com/technology/", "global", [], "美股科技公司新闻", False),
    ("arstechnica", "Ars Technica", "site", "https://arstechnica.com/", "global", [], "技术细节扎实的科技新闻", False),
]
_CAT_BY_ID = {c[0]: c for c in CATALOG}

_LOCK = threading.RLock()
_ST = {"sources": None, "feed": None, "seen": None, "ver": 0, "dirty": False, "flushed": 0.0, "sc": (0.0, False),
       "runs": None}
_run = {"running": False, "stop": False, "total": 0, "done": 0, "new": 0, "fail": 0, "current": [],
        "started": 0, "ended": 0, "trigger": "", "rid": "", "recs": [], "log": []}
_sched = {"started": False}
_wake = threading.Event()               # v159：改了自动更新设置时叫醒定时器


def next_run(c=None):
    """v159：下一次自动更新的时间（关着就是 0）：上一轮开始或改设置那一刻，取晚的，再加间隔。"""
    c = c or get_config()
    if not c.get("auto"):
        return 0
    return int(max(int(c.get("last_run") or 0), int(c.get("sched_from") or 0)) + int(c["every"]) * 60)


def _log(msg):
    print("[市场雷达] " + msg, flush=True)


def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=None, separators=(",", ":")), encoding="utf-8")
    os.replace(str(tmp), str(p))


def _from_catalog(c):
    cid, name, kind, target, group, hint, desc, _on = c
    s = {"id": cid, "name": name, "kind": kind, "group": group, "hint": list(hint), "desc": desc,
         "enabled": True, "added": int(time.time())}
    if kind == "kw":
        s["kw"] = target
    else:
        s["url"] = target
    return s


# ───────────────────────── 清单 / 设置 ─────────────────────────
def _sources():
    """内存里的信息源清单（第一次用：按推荐清单放进一批常用的）。调用方要拿着 _LOCK。"""
    if _ST["sources"] is None:
        data = _read_json(SRC_FILE, None)
        if not isinstance(data, list):
            data = [_from_catalog(c) for c in CATALOG if c[7]]
            _write_json(SRC_FILE, data)
        _ST["sources"] = data
    return _ST["sources"]


def _save_sources():
    _write_json(SRC_FILE, _ST["sources"] or [])


def get_config():
    c = _read_json(CFG_FILE, {})
    c = c if isinstance(c, dict) else {}
    c.setdefault("auto", True)
    c.setdefault("every", 60)
    c.setdefault("last_run", 0)
    c.setdefault("workers", WORKERS)          # v158：同时抓几个
    c.setdefault("sc_fast", True)             # v158：被拦时用 Scrapling 快速模式补救
    c.setdefault("sc_browser", True)          # v158：还不行再用真浏览器（慢，但能抓动态网页）
    c.setdefault("scope", "all")              # v158：「现在更新」抓哪些：all 全部 / groups 选中的几类 / failed 上次没抓成的
    c.setdefault("groups", [])
    return c


def save_config(auto=None, every=None, workers=None, sc_fast=None, sc_browser=None, scope=None, groups=None):
    c = get_config()
    old = (c.get("auto"), c.get("every"))
    if auto is not None:
        c["auto"] = bool(auto)
    if every is not None:
        c["every"] = max(5, min(int(every), 24 * 60))           # v159：最短 5 分钟
    if (c["auto"], c["every"]) != old:
        c["sched_from"] = int(time.time())                     # v159：改了自动更新，从保存这一刻重新开始计时
        _wake.set()
    if workers is not None:
        c["workers"] = max(1, min(int(workers), 8))
    if sc_fast is not None:
        c["sc_fast"] = bool(sc_fast)
    if sc_browser is not None:
        c["sc_browser"] = bool(sc_browser)
    if scope is not None and scope in ("all", "groups", "failed"):
        c["scope"] = scope
    if groups is not None:
        c["groups"] = [g for g in groups if g in GROUP_NAME]
    _write_json(CFG_FILE, c)
    return {"ok": True, "config": c, "next_run": next_run(c), "now": int(time.time())}


def _pick_sources(scope, groups):
    """v158：「现在更新」按设置挑要抓的信息源（只挑打开的）。"""
    srcs = [s for s in _sources() if s.get("enabled")]
    if scope == "groups":
        gs = set(groups or [])
        srcs = [s for s in srcs if s.get("group") in gs]
    elif scope == "failed":
        srcs = [s for s in srcs if s.get("err")]
    return srcs


def plan():
    """v158：点「现在更新」之前给界面看的：会抓哪些、按什么顺序、上一轮花了多久、设置。"""
    c = get_config()
    with _LOCK:
        srcs = [s for s in _sources() if s.get("enabled")]
        by = {}
        for s in srcs:
            g = s.get("group") or "mine"
            d = by.setdefault(g, {"key": g, "name": GROUP_NAME.get(g, g), "n": 0, "site": 0, "kw": 0, "failing": 0})
            d["n"] += 1
            d["kw" if s.get("kind") == "kw" else "site"] += 1
            if s.get("err"):
                d["failing"] += 1
        failing = [{"name": s.get("name", ""), "err": s.get("err", "")} for s in srcs if s.get("err")]
        runs = [r for r in _runs() if r.get("trigger") != "single"]
    order = [k for k, _n, _d in GROUPS]
    groups = sorted(by.values(), key=lambda d: order.index(d["key"]) if d["key"] in order else 99)
    last = None
    if runs:
        r = runs[0]
        last = {k: r.get(k) for k in ("id", "started", "ended", "trigger", "total", "ok", "fail", "new", "via", "stopped")}
    n_scope = len(_pick_sources(c["scope"], c["groups"]))
    return {"ok": True, "config": c, "next_run": next_run(c), "now": int(time.time()), "groups": groups, "enabled": len(srcs), "failing": failing[:40],
            "n_scope": n_scope, "last": last, "scrapling": _scrapling_ok(),
            "group_names": [[k, n, d] for k, n, d in GROUPS]}


def _feed():
    if _ST["feed"] is None:
        d = _read_json(FEED_FILE, [])
        _ST["feed"] = d if isinstance(d, list) else []
        s = _read_json(SEEN_FILE, [])
        _ST["seen"] = set(s if isinstance(s, list) else [])
    return _ST["feed"]


def _flush(force=False):
    with _LOCK:
        if not _ST["dirty"] or (not force and time.time() - _ST["flushed"] < 8):
            return
        _write_json(FEED_FILE, _ST["feed"] or [])
        _write_json(SEEN_FILE, list(_ST["seen"] or [])[-30000:])
        _ST["dirty"] = False
        _ST["flushed"] = time.time()


def snapshot():
    """给 biz_intel：(版本号, 抓到的内容, {信息源编号: 信息源})。版本号变了才需要重新归类。"""
    with _LOCK:
        feed = list(_feed())
        srcs = {s["id"]: s for s in _sources()}
        return _ST["ver"], feed, srcs


def _scrapling_ok():
    t, v = _ST["sc"]
    if time.time() - t < 120:
        return v
    try:
        import scrapling_fetch as SF
        v = bool(SF.available())
    except Exception:
        v = False
    _ST["sc"] = (time.time(), v)
    return v


# ───────────────────────── 抓取 ─────────────────────────
def _P():
    import creator_profiles
    return creator_profiles


def _get(url, timeout=15, accept=None):
    """下载：境外站走代理、国内站直连；不行再换另一种。返回 (字节, 最终网址)。"""
    P = _P()
    hdr = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36")}
    if accept:
        hdr["Accept"] = accept
    px = ""
    try:
        import web_tools as W
        px = W.proxy_for(url) or ""
    except Exception:
        pass
    any_px = ""
    try:
        any_px = P._proxy() or ""
    except Exception:
        pass
    tries = [px] if px else [""]
    for t in ("", any_px):
        if t not in tries and (t or not px):
            tries.append(t)
    errs = []
    for p in tries:
        try:
            return P._http(url, headers=hdr, proxy=p, timeout=timeout)
        except Exception as e:
            errs.append(str(e).split("\n")[0][:90])
    raise RuntimeError("；".join(errs) or "打不开")


def _clean(s):
    s = _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _ts_of(s):
    s = (s or "").strip()
    if not s:
        return 0
    try:
        return email.utils.parsedate_to_datetime(s).timestamp()
    except Exception:
        pass
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")[:32]).timestamp()
    except Exception:
        pass
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?", s)
    if m:
        try:
            return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                     int(m.group(4) or 12), int(m.group(5) or 0)).timestamp()
        except Exception:
            return 0
    return 0


def _looks_feed(b):
    head = (b or b"")[:2000].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    return head.startswith(b"<?xml") and (b"<rss" in head or b"<feed" in head or b"<rdf" in head) \
        or head.startswith(b"<rss") or head.startswith(b"<feed")


def _parse_feed(b):
    """RSS / Atom → [{title, url, ts, summary, source}]。"""
    try:
        root = ET.fromstring((b or b"").lstrip(b"\xef\xbb\xbf \r\n\t"))
    except Exception:
        return []
    tag = lambda e: (e.tag.split("}")[-1] if isinstance(e.tag, str) else "").lower()
    out = []
    for e in root.iter():
        if tag(e) not in ("item", "entry"):
            continue
        d = {"title": "", "url": "", "ts": 0, "summary": "", "source": ""}
        for c in e:
            ct = tag(c)
            if ct == "title":
                d["title"] = "".join(c.itertext())
            elif ct == "link":
                href = c.get("href")
                if href:
                    if (c.get("rel") or "alternate") == "alternate" or not d["url"]:
                        d["url"] = href
                elif (c.text or "").strip():
                    d["url"] = c.text.strip()
            elif ct in ("pubdate", "published", "updated", "date", "issued") and not d["ts"]:
                d["ts"] = _ts_of("".join(c.itertext()))
            elif ct in ("description", "summary", "content", "encoded") and not d["summary"]:
                d["summary"] = _clean("".join(c.itertext()))[:300]
            elif ct == "source" and not d["source"]:
                d["source"] = _clean("".join(c.itertext()))[:40]
            elif ct in ("guid", "id") and not d["url"] and (c.text or "").strip().startswith("http"):
                d["url"] = c.text.strip()
        d["title"] = _clean(d["title"])
        if d["source"] and d["title"].endswith(" - " + d["source"]):
            d["title"] = d["title"][:-len(" - " + d["source"])].strip()
        if d["url"].startswith("http") and len(d["title"]) >= 4:
            out.append(d)
    return out


def _from_links(h, base):
    import site_watch as SW
    out = []
    for it in SW._links(h or "", base, 0):
        w = it.get("when") or ""
        ts = 0
        if len(w) == 8:
            try:
                ts = datetime.datetime.strptime(w, "%Y%m%d").replace(hour=12).timestamp()
            except Exception:
                ts = 0
        out.append({"title": it["title"], "url": it["url"], "ts": ts, "summary": "", "source": ""})
    return out


def _step(trace, m, t0, ok, n=0, why=""):
    """记一步：用了哪个爬虫、成没成、抓到几条、花了多久、为什么。结果报告里一步一步列出来。"""
    trace.append({"m": m, "ok": bool(ok), "n": int(n or 0), "ms": int((time.time() - t0) * 1000), "why": str(why or "")[:140]})


def _runlog(msg):
    with _LOCK:
        _run["log"].append([int(time.time()), msg[:200]])
        del _run["log"][:-300]


SC_NAME = {"fast": "Scrapling 快速", "browser": "Scrapling 浏览器"}


def _fetch_site(src, trace):
    """一个网站 → (内容, 用的哪个爬虫)。顺序：RSS → 网页解析 → Scrapling 快速 → Scrapling 浏览器；管用的记住，下次先用。"""
    import site_watch as SW
    url = src["url"]
    name = src.get("name", "")
    pref = src.get("pref") if src.get("pref") in ("fast", "browser") else ""
    use_sc = _scrapling_ok()
    cfg = _run.get("cfg") or {}
    modes = [m for m in ("fast", "browser") if cfg.get("sc_" + m, True)]   # v158：设置里关掉的补救方式不用
    if pref not in modes:
        pref = ""
    if not modes:
        use_sc = False

    def via_sc(mode):
        import scrapling_fetch as SF
        px = None
        try:
            import web_tools as W
            px = W.proxy_for(url) or None
        except Exception:
            pass
        h = SF.fetch(url, mode=mode, proxy=px)
        for f in SW._feeds(h, url)[:1]:
            try:
                fb, _u = _get(f, timeout=12, accept=FEED_ACCEPT)
                items = _parse_feed(fb)
                if items:
                    return items
            except Exception:
                pass
        return _from_links(h, url)

    def try_sc(mode, why=""):
        t0 = time.time()
        _runlog("%s：%s换用 %s…" % (name, why, SC_NAME[mode]))
        try:
            items = via_sc(mode)
            if len(items) >= 3:
                _step(trace, SC_NAME[mode], t0, True, len(items))
                return items
            _step(trace, SC_NAME[mode], t0, False, len(items), "只找到 %d 条，太少" % len(items))
        except Exception as e:
            _step(trace, SC_NAME[mode], t0, False, 0, _human(e))
        return None

    if pref and use_sc:
        items = try_sc(pref, "上次是它管用，")
        if items:
            return items, SC_NAME[pref]
    t0 = time.time()
    try:
        b, final = _get(url, timeout=18)
        base = final or url
        if _looks_feed(b):
            items = _parse_feed(b)
            if items:
                _step(trace, "RSS", t0, True, len(items))
                src.pop("pref", None)
                return items, "RSS"
        h = _P()._text(b)
        for f in SW._feeds(h, base)[:2]:
            t1 = time.time()
            try:
                fb, _u = _get(f, timeout=12, accept=FEED_ACCEPT)
                items = _parse_feed(fb)
                if items:
                    _step(trace, "RSS", t1, True, len(items), "网页里找到的订阅地址")
                    src.pop("pref", None)
                    return items, "RSS"
                _step(trace, "RSS", t1, False, 0, "订阅地址里是空的")
            except Exception as e:
                _step(trace, "RSS", t1, False, 0, _human(e))
        items = _from_links(h, base)
        if len(items) >= 5:
            _step(trace, "网页解析", t0, True, len(items))
            src.pop("pref", None)
            return items, "网页解析"
        _step(trace, "网页解析", t0, False, len(items), "网页里只找到 %d 条文章链接（多半是动态网页）" % len(items))
    except Exception as e:
        _step(trace, "网页解析", t0, False, 0, _human(e))
    if use_sc:
        for mode in modes:
            if mode == pref:
                continue
            items = try_sc(mode)
            if items:
                src["pref"] = mode
                return items, SC_NAME[mode]
    elif not modes:
        trace.append({"m": "Scrapling", "ok": False, "n": 0, "ms": 0, "why": "设置里关掉了 Scrapling 补救"})
    else:
        trace.append({"m": "Scrapling", "ok": False, "n": 0, "ms": 0, "why": "网页抓取增强还没装好，没法补救"})
    bad = [x for x in trace if not x["ok"]]
    raise RuntimeError("；".join("%s：%s" % (x["m"], x["why"]) for x in bad[-2:]) or "没抓到")


def _baidu_news(h):
    out = []
    for m in re.finditer(r"<h3[^>]*>\s*<a\b([^>]*)>(.*?)</a>", h or "", re.S | re.I):
        hm = re.search(r'href\s*=\s*"([^"]+)"', m.group(1))
        t = _clean(m.group(2))
        if hm and len(t) >= 6:
            out.append({"title": t[:200], "url": _html.unescape(hm.group(1)), "ts": 0, "summary": "", "source": ""})
    return out


def _fetch_kw(src, trace):
    """一个关键词 → 新闻搜索的最新报道。Google 新闻（有代理时）→ 必应新闻 → 百度资讯。"""
    kw = src.get("kw") or src.get("name") or ""
    q = urllib.parse.quote(kw)
    tries = []
    try:
        if _P()._proxy():
            tries.append(("Google 新闻", "https://news.google.com/rss/search?q=%s&hl=zh-CN&gl=CN&ceid=CN:zh-Hans" % q))
    except Exception:
        pass
    if not tries:
        trace.append({"m": "Google 新闻", "ok": False, "n": 0, "ms": 0, "why": "没配代理，跳过"})
    tries.append(("必应新闻", "https://www.bing.com/news/search?q=%s&format=rss&setlang=zh-Hans&cc=CN" % q))
    for name, u in tries:
        t0 = time.time()
        try:
            b, _f = _get(u, timeout=15, accept=FEED_ACCEPT)
            items = _parse_feed(b)
            if items:
                _step(trace, name, t0, True, len(items))
                return items, name
            _step(trace, name, t0, False, 0, "没搜到")
        except Exception as e:
            _step(trace, name, t0, False, 0, _human(e, "site"))
    t0 = time.time()
    try:
        b, _f = _get("https://www.baidu.com/s?tn=news&rtt=4&bsst=1&cl=2&wd=" + q, timeout=15)
        items = _baidu_news(_P()._text(b))
        if items:
            _step(trace, "百度资讯", t0, True, len(items))
            return items, "百度资讯"
        _step(trace, "百度资讯", t0, False, 0, "没搜到（可能要人工验证）")
    except Exception as e:
        _step(trace, "百度资讯", t0, False, 0, _human(e, "site"))
    bad = [x for x in trace if not x["ok"]]
    if bad and all(re.search(r"连不上|找不到这个网站|超时|没配代理|SSL", x["why"]) for x in bad):
        raise RuntimeError("新闻搜索都连不上：Google 新闻要代理（看代理软件开没开），必应、百度连不上多半是网络问题")
    raise RuntimeError("；".join("%s：%s" % (x["m"], x["why"]) for x in bad[-2:]))


def _norm_url(u):
    try:
        p = urllib.parse.urlsplit(u.strip())
        q = "&".join(x for x in p.query.split("&") if x and not x.lower().startswith(("utm_", "spm=", "from=", "source=")))
        return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), q, ""))
    except Exception:
        return u


def _merge(src, items, first):
    """去重后放进内容库，返回 (新的条数, 新内容的编号)。"""
    now = time.time()
    new = []
    with _LOCK:
        feed = _feed()
        seen = _ST["seen"]
        for it in items[:PER_SOURCE]:
            key = hashlib.sha1(_norm_url(it["url"]).encode("utf-8")).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            ts = it.get("ts") or 0
            dated = bool(ts)
            if dated and ts < now - KEEP_DAYS * 86400:
                continue
            if ts > now:
                ts = now
            if not dated:
                ts = now - 3 * 86400 if first else now       # 第一次抓到的旧文章不算「刚发生」
            new.append({"key": key, "sid": src["id"], "sname": src.get("name", ""), "grp": src.get("group", ""),
                        "title": it["title"][:200], "url": it["url"], "summary": (it.get("summary") or "")[:300],
                        "from": it.get("source", ""), "ts": int(ts), "seen": int(now), "dated": dated})
        if new:
            feed.extend(new)
            feed.sort(key=lambda x: -x.get("ts", 0))
            cut = now - KEEP_DAYS * 86400
            del feed[MAX_ITEMS:]
            while feed and feed[-1].get("ts", 0) < cut:
                feed.pop()
            _ST["ver"] += 1
            _ST["dirty"] = True
    return len(new), [x["key"] for x in new]


def _human(e, kind="site"):
    """把出错原因翻成人话。"""
    s = str(e)
    net = re.search(r"Errno 111|Connection refused|actively refused|10061", s, re.I)
    dns = re.search(r"Name or service not known|getaddrinfo|Errno -2|Errno 11001|nodename nor servname", s, re.I)
    if kind == "kw" and (net or dns or re.search(r"timed? ?out|超时", s, re.I)):
        return "新闻搜索都连不上：Google 新闻要代理（看代理软件开没开），必应、百度连不上多半是网络问题"
    if re.search(r"timed? ?out|超时|Timeout", s, re.I):
        return "打不开（超时）：网站很慢，或者要代理"
    if net:
        return "连不上：代理软件没开，或者网络不通"
    if dns:
        return "找不到这个网站：网络没连上，或者网址写错了"
    if "403" in s:
        return "被网站拦了（403）"
    if "404" in s:
        return "网址不对（404），换成它的新闻页网址试试"
    if re.search(r"SSL|certificate|handshake", s, re.I):
        return "安全连接失败（SSL），可能要代理"
    return s[:160]


def _crawl_src(src):
    if _run["stop"]:
        return
    name = src.get("name", "")
    with _LOCK:
        _run["current"].append(name)
    _runlog("开始抓：%s" % name)
    first = not src.get("ok_at")
    trace, t0 = [], time.time()
    rec = {"id": src["id"], "name": name, "kind": src.get("kind", "site"), "group": src.get("group", ""),
           "target": src.get("kw") if src.get("kind") == "kw" else src.get("url", "")}
    try:
        items, via = _fetch_kw(src, trace) if src.get("kind") == "kw" else _fetch_site(src, trace)
        n, keys = _merge(src, items, first)
        now = int(time.time())
        with _LOCK:
            src.update(at=now, ok_at=now, n=len(items), new=n, err="", via=via, fails=0, trace=trace)
            _run["new"] += n
        rec.update(ok=True, via=via, n=len(items), new=n, keys=keys[:120])
        _runlog("%s：用「%s」抓到 %d 条，新的 %d 条（%.1f 秒）" % (name, via, len(items), n, time.time() - t0))
    except Exception as e:
        err = _human(e, src.get("kind"))
        with _LOCK:
            src.update(at=int(time.time()), err=err, fails=int(src.get("fails") or 0) + 1, trace=trace)
            _run["fail"] += 1
        rec.update(ok=False, err=err, n=0, new=0)
        _runlog("%s：没抓成（%s）" % (name, err[:80]))
    finally:
        rec.update(ms=int((time.time() - t0) * 1000), trace=trace)
        with _LOCK:
            try:
                _run["current"].remove(name)
            except ValueError:
                pass
            _run["done"] += 1
            _run["recs"].append(rec)
        _flush()


def _runs():
    if _ST["runs"] is None:
        d = _read_json(RUNS_FILE, [])
        _ST["runs"] = d if isinstance(d, list) else []
    return _ST["runs"]


def _crawl_all(srcs):
    try:
        with ThreadPoolExecutor(max_workers=int((_run.get("cfg") or {}).get("workers") or WORKERS)) as ex:
            list(ex.map(_crawl_src, srcs))
    except Exception as e:
        _runlog("这一轮出错：%s" % e)
    finally:
        _flush(force=True)
        with _LOCK:
            _save_sources()
            now = int(time.time())
            _run.update(running=False, ended=now, current=[])
            recs = list(_run["recs"])
            via = {}
            for r in recs:
                if r.get("ok"):
                    via[r["via"]] = via.get(r["via"], 0) + 1
            msg = "这一轮抓完：%d 个信息源，成功 %d 个，新抓到 %d 条%s" % (
                _run["total"], sum(1 for r in recs if r.get("ok")), _run["new"], "（中途停止）" if _run["stop"] else "")
            _run["log"].append([now, msg])
            rec = {"id": _run["rid"], "started": _run["started"], "ended": now, "trigger": _run["trigger"],
                   "total": _run["total"], "done": len(recs), "ok": sum(1 for r in recs if r.get("ok")),
                   "fail": sum(1 for r in recs if not r.get("ok")), "new": _run["new"], "stopped": bool(_run["stop"]),
                   "via": via, "sources": recs, "log": list(_run["log"])[-300:]}
            runs = _runs()
            runs.insert(0, rec)
            del runs[40:]
            _write_json(RUNS_FILE, runs)
        _log(msg)


def start(sids=None, trigger="manual", scope=None, groups=None):
    cfg = get_config()
    with _LOCK:
        if _run["running"]:
            return {"ok": False, "error": "正在抓，等这一轮抓完再说"}
        if sids:
            srcs = [s for s in _sources() if s["id"] in sids]
            trigger = "single" if trigger == "manual" else trigger
        elif trigger == "auto":
            srcs = [s for s in _sources() if s.get("enabled")]          # 自动更新一直抓全部
        else:
            sc = scope or cfg.get("scope") or "all"
            srcs = _pick_sources(sc, groups if groups is not None else cfg.get("groups"))
            if not srcs:
                return {"ok": False, "error": {"groups": "选中的这几类里没有打开的信息源", "failed": "上一轮没有没抓成的信息源"}.get(sc, "清单里没有打开的信息源")}
        if not srcs:
            return {"ok": False, "error": "清单里没有打开的信息源"}
        _run["cfg"] = dict(cfg)
        now = int(time.time())
        _run.update(running=True, stop=False, total=len(srcs), done=0, new=0, fail=0, current=[], started=now,
                    ended=0, trigger=trigger, rid=datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), recs=[],
                    log=[[now, "开始抓（%s）：%d 个信息源" % ({"auto": "自动", "single": "单个"}.get(trigger, "手动"), len(srcs))]])
    if not sids:
        c = get_config()
        c["last_run"] = int(time.time())
        _write_json(CFG_FILE, c)
    threading.Thread(target=_crawl_all, args=(srcs,), daemon=True, name="biz-radar-run").start()
    _log("开始抓（%s）：%d 个信息源" % ({"auto": "自动", "single": "单个"}.get(trigger, "手动"), len(srcs)))
    return {"ok": True, "total": len(srcs), "rid": _run["rid"]}


def stop():
    with _LOCK:
        if _run["running"]:
            _run["stop"] = True
            _run["log"].append([int(time.time()), "你点了停止：正在抓的这几个抓完就停"])
    return {"ok": True}


def status():
    cfg = get_config()
    now = time.time()
    with _LOCK:
        r = {k: (list(v) if isinstance(v, list) else v) for k, v in _run.items() if k not in ("recs", "log")}
        r["log"] = list(_run["log"])[-16:]
        srcs = _sources()
        feed = _feed()
        n24 = sum(1 for x in feed if x.get("ts", 0) >= now - 86400)
        n7 = sum(1 for x in feed if x.get("ts", 0) >= now - 7 * 86400)
        en = sum(1 for s in srcs if s.get("enabled"))
        bad = sum(1 for s in srcs if s.get("enabled") and s.get("err"))
    nxt = next_run(cfg)
    r.update(ok=True, auto=cfg["auto"], every=cfg["every"], last_run=cfg["last_run"], next_run=int(nxt),
             sources=len(srcs), enabled=en, failing=bad, items=len(feed), items_24h=n24, items_7d=n7,
             scrapling=_scrapling_ok(), now=int(now))
    return r


def engines():
    """v157：用的是哪些爬虫、能不能用、上一轮各抓成了几个信息源。"""
    import importlib.util
    try:
        import scrapling_fetch as SF
        st = SF.status() or {}
    except Exception as e:
        st = {"error": str(e)}
    sc_ok = _scrapling_ok()
    curl = importlib.util.find_spec("curl_cffi") is not None
    try:
        px = bool(_P()._proxy())
    except Exception:
        px = False
    with _LOCK:
        runs = _runs()
        last = runs[0] if runs else None
        srcs = list(_sources())
    used = dict((last or {}).get("via") or {})
    now_use = {}
    for s in srcs:
        if s.get("enabled") and s.get("via") and not s.get("err"):
            now_use[s["via"]] = now_use.get(s["via"], 0) + 1
    sc_state = ("已装好" + ("（Scrapling %s）" % st.get("version") if st.get("version") else "") if sc_ok
                else "正在安装…" if st.get("installing") else "还没装好" + ("：" + str(st.get("error"))[:60] if st.get("error") else "（后台第一次启动时会自动装）"))
    rows = [
        ("rss", "RSS 订阅读取", ["RSS"], True, "内置，一直能用", "网站自己提供的订阅源。最准，带发布时间。"),
        ("page", "网页解析", ["网页解析", "网页"], True, "用 curl_cffi 模拟浏览器的网络指纹" if curl else "普通方式（没装 curl_cffi，容易被拦）",
         "打开网页，挑出像文章的链接；日期从网址里认。没有 RSS 的网站靠它。"),
        ("sc_fast", "Scrapling 快速模式", ["Scrapling 快速"], sc_ok, sc_state,
         "开源爬虫 Scrapling：模拟真 Chrome 的网络指纹和请求头，过一般的反爬拦截。普通方式被拦时用它。"),
        ("sc_browser", "Scrapling 浏览器模式", ["Scrapling 浏览器"], sc_ok, sc_state,
         "用电脑上的 Chrome 真正打开网页（不弹窗口），等动态内容加载完，能过 Cloudflare 验证。最慢，但最能打。"),
        ("news", "新闻搜索", ["Google 新闻", "必应新闻", "百度资讯"], True,
         "代理已配置：先用 Google 新闻" if px else "没配代理：用必应新闻，再不行用百度资讯",
         "「关键词」类信息源用它：拿公司名、行业名去新闻搜索里找各家媒体的最新报道。"),
    ]
    out = []
    for key, name, vias, ok, state, desc in rows:
        out.append({"key": key, "name": name, "ok": bool(ok), "state": state, "desc": desc,
                    "last": sum(used.get(v, 0) for v in vias), "now": sum(now_use.get(v, 0) for v in vias)})
    return {"ok": True, "engines": out, "order": "网站：先试 RSS，没有就网页解析；打不开、被拦或者是动态网页，换 Scrapling 快速，再不行用浏览器模式。"
            "关键词：Google 新闻 → 必应新闻 → 百度资讯。哪种管用会记住，下次直接用。",
            "last_run": (last or {}).get("id", "")}


def list_runs():
    with _LOCK:
        runs = list(_runs())
    keep = ("id", "started", "ended", "trigger", "total", "done", "ok", "fail", "new", "stopped", "via")
    return {"ok": True, "runs": [{k: r.get(k) for k in keep} for r in runs]}


def get_run(rid):
    with _LOCK:
        if _run["running"] and rid == _run["rid"]:
            return {"id": rid, "started": _run["started"], "ended": 0, "trigger": _run["trigger"], "total": _run["total"],
                    "done": _run["done"], "ok": sum(1 for r in _run["recs"] if r.get("ok")), "running": True,
                    "fail": sum(1 for r in _run["recs"] if not r.get("ok")), "new": _run["new"], "via": {},
                    "sources": list(_run["recs"]), "log": list(_run["log"])}
        return next((dict(r) for r in _runs() if r.get("id") == rid), None)


def list_sources():
    now = time.time()
    with _LOCK:
        srcs = [dict(s) for s in _sources()]
        cnt = {}
        for x in _feed():
            if x.get("ts", 0) >= now - 7 * 86400:
                cnt[x.get("sid")] = cnt.get(x.get("sid"), 0) + 1
    have = {s["id"] for s in srcs}
    have_t = {(s.get("url") or s.get("kw") or "").strip().lower() for s in srcs}
    for s in srcs:
        s["n7"] = cnt.get(s["id"], 0)
    cat = []
    for key, name, desc in GROUPS:
        if key == "mine":
            continue
        rows = []
        for c in CATALOG:
            if c[4] != key:
                continue
            rows.append({"id": c[0], "name": c[1], "kind": c[2], "target": c[3], "hint": c[5], "desc": c[6],
                         "added": c[0] in have or c[3].strip().lower() in have_t})
        cat.append({"key": key, "name": name, "desc": desc, "items": rows})
    return {"ok": True, "sources": srcs, "catalog": cat, "groups": [{"key": k, "name": n} for k, n, _d in GROUPS],
            "config": get_config(), "status": status()}


def source_action(body):
    body = body or {}
    act = body.get("action", "")
    with _LOCK:
        srcs = _sources()
        if act == "add":
            kind = "kw" if body.get("kind") == "kw" else "site"
            hint = [str(h)[:40] for h in (body.get("hint") or []) if h][:3]
            if kind == "kw":
                kw = re.sub(r"\s+", " ", str(body.get("kw") or "")).strip()[:30]
                if len(kw) < 2:
                    return {"ok": False, "error": "关键词至少两个字"}
                if any((s.get("kw") or "").lower() == kw.lower() for s in srcs):
                    return {"ok": False, "error": "「%s」已经在清单里了" % kw}
                s = {"id": "k" + hashlib.md5(kw.encode("utf-8")).hexdigest()[:8], "kind": "kw", "kw": kw,
                     "name": str(body.get("name") or kw).strip()[:30]}
            else:
                url = str(body.get("url") or "").strip()
                if not re.match(r"^https?://[^\s/]+\.[^\s]+", url):
                    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", url, re.I):
                        url = "https://" + url
                    else:
                        return {"ok": False, "error": "网址要像 https://www.example.com/news 这样"}
                if any((s.get("url") or "").rstrip("/").lower() == url.rstrip("/").lower() for s in srcs):
                    return {"ok": False, "error": "这个网址已经在清单里了"}
                host = urllib.parse.urlsplit(url).netloc.lower()
                s = {"id": "u" + hashlib.md5(url.encode("utf-8")).hexdigest()[:8], "kind": "site", "url": url,
                     "name": str(body.get("name") or "").strip()[:30] or (host[4:] if host.startswith("www.") else host)}
            s.update(group="mine", hint=hint, desc="", enabled=True, added=int(time.time()))
            srcs.insert(0, s)
            _save_sources()
            return {"ok": True, "id": s["id"]}
        if act == "add_catalog":
            ids = [i for i in (body.get("ids") or []) if i in _CAT_BY_ID]
            have = {s["id"] for s in srcs}
            n = 0
            for i in ids:
                if i not in have:
                    srcs.append(_from_catalog(_CAT_BY_ID[i]))
                    n += 1
            _save_sources()
            return {"ok": True, "added": n}
        s = next((x for x in srcs if x["id"] == body.get("id")), None)
        if not s:
            return {"ok": False, "error": "找不到这个信息源"}
        if act == "toggle":
            s["enabled"] = bool(body.get("enabled"))
        elif act == "delete":
            srcs.remove(s)
        elif act == "hint":
            s["hint"] = [str(h)[:40] for h in (body.get("hint") or []) if h][:3]
            _ST["ver"] += 1
        else:
            return {"ok": False, "error": "不认识的操作"}
        _save_sources()
    return {"ok": True}


def boot_scheduler():
    """后台启动时调用：每分钟看一眼，打开了「自动更新」且到点了就抓一轮。重复调用只启动一次。"""
    if _sched["started"]:
        return
    _sched["started"] = True

    def _loop():
        time.sleep(150)                      # 启动后先等两分半，别和开机抢资源
        while True:
            try:
                c = get_config()
                if c["auto"] and not _run["running"] and time.time() >= next_run(c):
                    start(trigger="auto")
            except Exception as e:
                _log("自动更新出错（忽略）：%s" % e)
            _wake.wait(20)
            _wake.clear()

    threading.Thread(target=_loop, name="biz-radar-auto", daemon=True).start()


# ───────────────────────── v160：点开一条新闻，在软件里看正文 ─────────────────────────
_ART = {}                       # 网址 → 结果（只放在内存里，最多 300 篇）
_ART_LOCK = threading.Lock()
_BLOCK_TAGS = {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "td", "pre", "br", "tr"}
_SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "button", "select", "iframe", "svg",
              "template", "figure", "figcaption"}
_VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
_NOISE = re.compile(r"(comment|footer|share|related|recommend|sidebar|nav|menu|breadcrumb|copyright|advert|banner|login|"
                    r"subscribe|hot-?list|rank|tags?$|toolbar|评论|推荐)", re.I)
_JUNK_LINE = re.compile(r"^(责任编辑|编辑|来源|作者|校对|审核|本文来源|原标题|声明|免责声明|版权|分享到|扫一扫|点击|关注|相关阅读|"
                        r"推荐阅读|更多|举报|返回|上一篇|下一篇|打开.{0,6}APP|下载.{0,6}APP|©|Copyright)", re.I)


def _main_text(h):
    """从网页里挑出正文（v161：完整版）。
    1) 每段文字记下它所在的容器和全部上层容器；
    2) 先找段落文字最多的那个容器；
    3) 再一层层往上看：上一层多出来的也是正文样子的段落、链接又不多，就把它也算进来——
       百家号这类「每段一个小盒子」的网页，这样才不会只取到第一段。只用标准库。"""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []          # [(标签, 编号, 是否跳过)]
            self.skip = 0
            self.nid = 0
            self.paras = []          # [(所在容器编号, 上层容器编号元组, 文字, 是不是在链接里)]
            self.buf = []
            self.link = 0
            self.parent = {}

        def _flush(self):
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            self.buf = []
            if t and self.stack:
                chain = tuple(n for _t, n, _s in self.stack)
                own = chain[-1]
                # 段落标签（p/li…）的文字算到它的上一层容器
                if self.stack[-1][0] in ("p", "li", "blockquote", "pre", "span", "strong", "b", "em", "font") and len(chain) > 1:
                    k = len(self.stack) - 1
                    while k > 0 and self.stack[k][0] not in ("div", "section", "article", "td", "main", "body"):
                        k -= 1
                    own = self.stack[k][1]
                self.paras.append((own, chain, t, self.link > 0))

        def handle_starttag(self, tag, attrs):
            if tag in _VOID:
                if tag == "br":
                    self._flush()
                return
            a = dict(attrs)
            noisy = tag in _SKIP_TAGS or bool(_NOISE.search((a.get("class") or "") + " " + (a.get("id") or "")))
            if tag in _BLOCK_TAGS:
                self._flush()
            self.nid += 1
            if self.stack:
                self.parent[self.nid] = self.stack[-1][1]
            self.stack.append((tag, self.nid, noisy))
            if noisy:
                self.skip += 1
            if tag == "a":
                self.link += 1

        def handle_endtag(self, tag):
            if tag in _VOID:
                return
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    if tag in _BLOCK_TAGS:
                        self._flush()
                    for t, _n, noisy in self.stack[i:]:
                        if noisy:
                            self.skip -= 1
                        if t == "a":
                            self.link = max(0, self.link - 1)
                    del self.stack[i:]
                    break

        def handle_data(self, d):
            if not self.skip:
                self.buf.append(d)

    p = P()
    try:
        p.feed(h)
        p._flush()
    except Exception:
        pass
    if not p.paras:
        return []

    def is_body(t):
        return len(t) >= 8 and not _JUNK_LINE.match(t)

    score = {}
    for own, _c, t, inlink in p.paras:
        if inlink or not is_body(t):
            continue
        score[own] = score.get(own, 0) + len(t) + (40 if re.search(r"[。！？.!?」”\"]$", t) else 0)
    if not score:
        return []
    best = max(score, key=score.get)

    def stats(node):
        good = link = n_good = long_good = 0
        for _o, chain, t, inlink in p.paras:
            if node not in chain:
                continue
            if inlink:
                link += len(t)
            elif is_body(t):
                good += len(t)
                n_good += 1
                if len(t) >= 25:
                    long_good += len(t)
        return good, link, n_good, long_good

    cur = best
    g0, l0, n0, lg0 = stats(cur)
    node = p.parent.get(cur)
    while node:
        g, l, n, lg = stats(node)
        add, add_long = g - g0, lg - lg0
        dens = l / float(g + l or 1)
        if add <= 0:
            cur, node = node, p.parent.get(node)            # 多一层但没多文字：照样往上
            continue
        # 多出来的大部分是长段落、链接也不多 → 也是正文
        if dens < 0.3 and add_long >= add * 0.6:
            cur, (g0, l0, n0, lg0) = node, (g, l, n, lg)
            node = p.parent.get(node)
            continue
        break
    out, seen = [], set()
    for _o, chain, t, inlink in p.paras:
        if cur not in chain or inlink or t in seen or _JUNK_LINE.match(t):
            continue
        if len(t) < 2:
            continue
        seen.add(t)
        out.append(t)
    # 开头结尾的零碎短句（日期、作者、标签）去掉
    while out and len(out[0]) < 8 and not re.search(r"[。！？]", out[0]):
        out.pop(0)
    while out and len(out[-1]) < 8 and not re.search(r"[。！？]", out[-1]):
        out.pop()
    return out


def _meta_of(h, *names):
    for n in names:
        for pat in (r'<meta[^>]+(?:property|name|itemprop)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(n),
                    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name|itemprop)=["\']%s["\']' % re.escape(n)):
            m = re.search(pat, h, re.I)
            if m and m.group(1).strip():
                return _html.unescape(m.group(1)).strip()
    return ""


def article(url):
    """v160：读一条新闻的正文（软件里展开看，不用跳网页）。读不到正文就返回网页自己的简介。"""
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        return {"ok": False, "error": "网址不对"}
    with _ART_LOCK:
        hit = _ART.get(url)
    if hit:
        return hit
    item = None
    with _LOCK:
        for x in _feed():
            if x.get("url") == url:
                item = x
                break
    t0 = time.time()
    h, via, err = "", "", ""
    try:
        b, _final = _get(url, timeout=15)
        h, via = _P()._text(b), "直接打开"
    except Exception as e:
        err = _human(e)
    paras = _main_text(h) if h else []
    if sum(len(x) for x in paras) < 300 and _scrapling_ok() and (get_config().get("sc_fast", True)):
        try:                                            # 动态网页：换 Scrapling 再读一次
            import scrapling_fetch as SF
            px = None
            try:
                import web_tools as W
                px = W.proxy_for(url) or None
            except Exception:
                pass
            h2 = SF.fetch(url, mode="fast", proxy=px, timeout=20)
            p2 = _main_text(h2)
            if sum(len(x) for x in p2) > sum(len(x) for x in paras):
                h, paras, via, err = h2, p2, "Scrapling", ""
        except Exception as e:
            err = err or _human(e)
    desc = _meta_of(h, "og:description", "description", "twitter:description") if h else ""
    pub = _meta_of(h, "article:published_time", "og:release_date", "pubdate", "publishdate", "datePublished") if h else ""
    total = sum(len(x) for x in paras)
    if total > 40000:                                   # 特别长的（几万字）只留前面
        keep, n = [], 0
        for x in paras:
            keep.append(x)
            n += len(x)
            if n > 40000:
                break
        paras = keep
    title = (item or {}).get("title", "") or _meta_of(h, "og:title") if h else (item or {}).get("title", "")
    res = {"ok": True, "url": url, "paras": paras if total >= 80 else [], "desc": desc[:400], "title": title,
           "foreign": _foreign(" ".join([title or ""] + (paras[:6] if total >= 80 else [desc]))),
           "summary": (item or {}).get("summary", ""), "pub": pub[:40], "via": via, "chars": total,
           "ms": int((time.time() - t0) * 1000),
           "error": "" if (total >= 80 or desc) else (err or "这个网页没读出正文（可能要登录，或者是图片、视频）")}
    if total >= 80 or desc:
        with _ART_LOCK:
            _ART[url] = res
            if len(_ART) > 300:
                _ART.pop(next(iter(_ART)))
    return res


# ───────────────────────── v161：外文新闻翻译成中文 ─────────────────────────
_TR = {}                         # 网址 → 译文结果


def _foreign(text):
    """是不是外文：中文字很少（日文有假名、韩文有谚文也算外文）。"""
    t = re.sub(r"\s+", "", text or "")[:3000]
    if len(t) < 6:
        return False
    if re.search(r"[\u3040-\u30ff\uac00-\ud7af]", t):
        return True
    han = len(re.findall(r"[\u4e00-\u9fff]", t))
    other = len(re.findall(r"[^\W\d_]", t)) - han             # 拉丁、西里尔等字母
    return other >= 6 and han < other * 0.1


def _req_json(url, data=None, headers=None, proxy=None, timeout=20):
    import json as _json
    import urllib.request
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
    h.update(headers or {})
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else _json.dumps(data, ensure_ascii=False).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=h)
    hs = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    with urllib.request.build_opener(*hs).open(req, timeout=timeout) as r:
        raw = r.read(8 * 1024 * 1024).decode("utf-8", "replace")
    try:
        return _json.loads(raw)
    except Exception:
        return raw


def _proxies(url):
    """先试直连还是先试代理：境外站先代理。"""
    px = ""
    try:
        import web_tools as W
        px = W.proxy_for(url) or ""
    except Exception:
        pass
    anyp = ""
    try:
        anyp = _P()._proxy() or ""
    except Exception:
        pass
    out = [px] if px else []
    for t in ("", anyp):
        if t not in out:
            out.append(t)
    return out


def _chunks(lines, limit):
    cur, n = [], 0
    for x in lines:
        if cur and n + len(x) > limit:
            yield cur
            cur, n = [], 0
        cur.append(x)
        n += len(x)
    if cur:
        yield cur


def _tr_microsoft(lines):
    """微软翻译（Edge 浏览器自带的那个，国内一般能直连，不用钥匙）。"""
    last = None
    for px in _proxies("https://edge.microsoft.com/"):
        try:
            tok = _req_json("https://edge.microsoft.com/translate/auth", proxy=px, timeout=10)
            if not isinstance(tok, str) or len(tok) < 20:
                raise RuntimeError("拿不到翻译凭证")
            out = []
            for part in _chunks(lines, 9000):
                r = _req_json("https://api-edge.cognitive.microsofttranslator.com/translate?to=zh-Hans&api-version=3.0",
                              data=[{"Text": x} for x in part], headers={"Authorization": "Bearer " + tok.strip()},
                              proxy=px, timeout=25)
                if not isinstance(r, list) or len(r) != len(part):
                    raise RuntimeError("翻译结果不对")
                out += [((x.get("translations") or [{}])[0].get("text") or "") for x in r]
            return out
        except Exception as e:
            last = e
    raise RuntimeError("微软翻译：%s" % _human(last or "失败"))


def _tr_google(lines):
    """谷歌翻译（一般要开代理）。"""
    import urllib.parse
    last = None
    for px in _proxies("https://translate.googleapis.com/"):
        try:
            out = []
            for part in _chunks(lines, 3500):
                q = "\n".join(x.replace("\n", " ") for x in part)
                body = urllib.parse.urlencode({"q": q}).encode("utf-8")
                r = _req_json("https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t",
                              data=body, headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
                              proxy=px, timeout=25)
                txt = "".join(seg[0] for seg in (r[0] or []) if seg and seg[0])
                got = txt.split("\n")
                if len(got) != len(part):
                    raise RuntimeError("段落对不上")
                out += got
            return out
        except Exception as e:
            last = e
    raise RuntimeError("谷歌翻译：%s" % _human(last or "失败"))


def _tr_local(lines):
    """本地模型（Ollama）翻译：慢一些，前两种都不行时才用。"""
    import agent_core as core
    ul, model = core.prefer_local_model(True, "qwen2.5")
    if not ul:
        raise RuntimeError("本地模型没开")
    client = core.make_client(True)
    out = []
    for part in _chunks(lines, 2500):
        numbered = "\n".join("[%d] %s" % (i + 1, x) for i, x in enumerate(part))
        resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content":
            "把下面每一段翻译成通顺的简体中文。每段输出「[编号] 译文」，编号一一对应，不要解释、不要输出原文。人名、公司名、产品名第一次出现时可在括号里保留原文。\n\n" + numbered}])
        raw = re.sub(r"(?s)<think>.*?</think>", "", resp.choices[0].message.content or "")
        got = {}
        for m in re.finditer(r"^\s*\[(\d+)\]\s*(.+)$", raw, re.M):
            got[int(m.group(1)) - 1] = m.group(2).strip()
        if not got:
            raise RuntimeError("本地模型没返回译文")
        out += [got.get(i, "") for i in range(len(part))]
    return out


def translate_article(url):
    """v161：把一条外文新闻（标题 + 正文）翻成中文。依次试：微软翻译 → 谷歌翻译 → 本地模型。结果记在内存里。"""
    with _ART_LOCK:
        hit = _TR.get(url)
    if hit:
        return hit
    a = article(url)
    if not a.get("ok"):
        return a
    lines = [a.get("title") or ""] + (a.get("paras") or ([a["desc"]] if a.get("desc") else []))
    idx = [i for i, x in enumerate(lines) if x and x.strip()]
    src = [lines[i] for i in idx]
    if not src:
        return {"ok": False, "error": "没有可翻译的内容"}
    errs, got, via = [], None, ""
    for name, f in (("微软翻译", _tr_microsoft), ("谷歌翻译", _tr_google), ("本地模型", _tr_local)):
        try:
            got = f(src)
            if got and sum(1 for x in got if x) >= max(1, len(src) // 2):
                via = name
                break
            errs.append("%s：没翻出来" % name)
        except Exception as e:
            errs.append(str(e)[:120])
        got = None
    if not got:
        return {"ok": False, "error": "翻译没成功（" + "；".join(errs) + "）"}
    out = list(lines)
    for i, t in zip(idx, got):
        out[i] = t or lines[i]
    res = {"ok": True, "url": url, "title": out[0], "paras": out[1:] if a.get("paras") else [],
           "desc": out[1] if not a.get("paras") and a.get("desc") else "", "via": via}
    with _ART_LOCK:
        _TR[url] = res
        if len(_TR) > 200:
            _TR.pop(next(iter(_TR)))
    return res


_TRL = {}                        # 原文 → 译文（新闻标题）


def translate_lines(lines):
    """v161：把列表里的外文标题翻成中文（只用微软 / 谷歌翻译，快；翻不了就原样返回空）。"""
    lines = [str(x or "")[:500] for x in (lines or [])][:100]
    with _ART_LOCK:
        todo = [x for x in dict.fromkeys(lines) if x and x not in _TRL and _foreign(x)]
    via, err = "", ""
    if todo:
        for name, f in (("微软翻译", _tr_microsoft), ("谷歌翻译", _tr_google)):
            try:
                got = f(todo)
                with _ART_LOCK:
                    for a, b in zip(todo, got):
                        if b:
                            _TRL[a] = b
                    while len(_TRL) > 3000:
                        _TRL.pop(next(iter(_TRL)))
                via = name
                break
            except Exception as e:
                err = str(e)[:120]
    with _ART_LOCK:
        out = [_TRL.get(x, "") for x in lines]
    return {"ok": True, "items": out, "via": via, "error": "" if via or not todo else err}
