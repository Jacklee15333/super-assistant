"""超能小助 · 商业 · 真实市场 · 交易平台爬虫（v192 新增）

市场雷达抓的是新闻；这里去「真有人在买卖」的平台上抓一个方向的实际数据：
  · 中国政府采购网：近半年有多少条采购 / 中标公告，抽几条看预算和中标金额（企业和政府真金白银的需求）
  · 1688（阿里巴巴批发）：批发价格带、有多少货源、成交了多少（上游供货和进货成本）
  · 京东：零售价格带、评价数（消费者真买的东西，评价数≈销量的影子）
  · 什么值得买：消费者实际下单的到手价（价格带、大家觉得值不值）
  · 猪八戒网：服务接单的报价和成交（卖服务、接项目的生意）
抓法和市场雷达一样：先普通方式直连；被拦、要登录、只拿到空壳时，用 Scrapling 快速模式补救，再不行开真浏览器；
哪种管用记下来，下次先用。要登录才能看的就不硬闯，记成「要登录」。不用 AI。
v199：① 加「爬虫专用 Chrome」这一档（真 Chrome + 防检测 + 顺手收下网页自己调的接口数据），国内平台前三档都不行时用它；
      ② 淘宝 / 天猫、拼多多也能登录后抓；③ 「请登录」只出现在页面顶上的不算被拦（苏宁就是被它误判的）；
      ④ 国外平台加到 30 个左右（亚马逊多国站、沃尔玛、乐天、美客多……），加官方公开接口（美国联邦采购、欧盟招标、
      苹果应用商店、Freelancer、Kickstarter），见 biz_trade_x.py；⑤ 几个平台同时抓，快很多。
结果存 memory/biz/real/trade.json，交给 AI 核实时当「资料③」，也显示在体检卡上。
"""
from __future__ import annotations

import datetime
import html as _html
import re
import statistics
import threading
import time
import json
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import biz_intel as BZ
import biz_trade_x as X

TRADE_FILE = BZ.BIZ_DIR / "real" / "trade.json"
STATE_FILE = BZ.BIZ_DIR / "real" / "trade_state.json"
SC_NAME = {"direct": "普通方式", "fast": "Scrapling 快速", "browser": "Scrapling 浏览器", "login": "已登录的浏览器",
           "chrome": "爬虫专用 Chrome", "api": "官方接口", "unlock": "付费解锁服务", "apify": "Apify 现成爬虫"}

PLATFORMS = [
    {"key": "ccgp", "name": "中国政府采购网", "kind": "采购", "url": "http://www.ccgp.gov.cn/",
     "what": "政府、学校、医院、国企近半年的采购和中标公告有多少条，抽几条看预算和中标金额"},
    {"key": "b2b", "name": "1688（阿里巴巴批发）", "kind": "批发", "url": "https://www.1688.com/", "login": True,
     "what": "批发价格带、货源多不多、成交件数：进货要多少钱、上游卖得动不动"},
    {"key": "ywg", "name": "义乌购（义乌小商品批发）", "kind": "批发", "url": "https://www.yiwugo.com/",
     "what": "不用登录的批发价：义乌商贸城几万家商户的出厂 / 批发价格带（1688 要登录时靠它）"},
    {"key": "jd", "name": "京东", "kind": "零售", "url": "https://www.jd.com/", "login": True,
     "what": "零售价格带和评价数（评价数大致反映卖了多少）"},
    {"key": "tb", "name": "淘宝 / 天猫", "kind": "零售", "url": "https://www.taobao.com/", "login": True,
     "what": "全国最大的网购平台：零售价格带、「多少人付款」"},
    {"key": "pdd", "name": "拼多多", "kind": "零售", "url": "https://www.pinduoduo.com/", "login": True,
     "what": "下沉市场的价格带、「已拼多少件」"},
    {"key": "xy", "name": "闲鱼", "kind": "二手成交", "url": "https://www.goofish.com/", "login": True,
     "what": "二手价、「多少人想要」：东西卖不卖得掉、旧货值多少"},
    {"key": "sn", "name": "苏宁易购", "kind": "零售", "url": "https://www.suning.com/",
     "what": "不用登录的零售价：家电、数码、日用、食品的标价和评价数（京东要登录时靠它）"},
    {"key": "smzdm", "name": "什么值得买", "kind": "到手价", "url": "https://www.smzdm.com/",
     "what": "消费者实际下单的到手价、点「值」的人多不多"},
    {"key": "zbj", "name": "猪八戒网", "kind": "服务接单", "url": "https://www.zbj.com/",
     "what": "卖服务、接项目的报价和成交笔数"},
    # v198：国外主流平台（要能上外网：走软件设置里的代理；搜索词自动翻成英文）
    {"key": "amazon", "name": "亚马逊 Amazon（美国站）", "kind": "国外零售", "url": "https://www.amazon.com/", "foreign": True, "region": "na",
     "what": "美国零售价格带、「上个月卖了多少」（亚马逊在搜索结果里直接写 1K+ bought in past month）"},
    {"key": "ebay", "name": "eBay（已成交的）", "kind": "国外成交", "url": "https://www.ebay.com/", "foreign": True, "region": "na",
     "what": "只看已经卖出去的：真实成交价和最近卖出了多少件"},
    {"key": "aliexpress", "name": "速卖通 AliExpress", "kind": "跨境零售", "url": "https://www.aliexpress.com/", "foreign": True, "region": "b2b",
     "what": "中国卖家卖到国外的零售价和销量（xxx sold）"},
    {"key": "alibaba", "name": "阿里巴巴国际站 Alibaba.com", "kind": "外贸批发", "url": "https://www.alibaba.com/", "foreign": True, "region": "b2b",
     "what": "外贸批发价（美元）和起订量：国外买家进货要多少钱"},
]
PLATFORMS.insert(next(i for i, p in enumerate(PLATFORMS) if p["key"] == "zbj") + 1,
                 {"key": X.APPSTORE_CN["key"], "name": X.APPSTORE_CN["name"], "kind": X.APPSTORE_CN["kind"], "url": X.APPSTORE_CN["home"],
                  "what": X.APPSTORE_CN["what"], "api": True})
PLATFORMS += [{"key": p["key"], "name": p["name"], "kind": p["kind"], "url": p["home"], "what": p["what"], "foreign": True,
               "region": p["region"], "api": bool(p.get("api")), "login": bool(p.get("login"))} for p in X.G]
for _p in PLATFORMS:
    _p.setdefault("region", "cn")
FOREIGN = {p["key"] for p in PLATFORMS if p.get("foreign")}
API_KEYS = {p["key"] for p in PLATFORMS if p.get("api")}
LOGIN_SITES = {p["key"] for p in PLATFORMS if p.get("login")}
CN_CHROME = {"ccgp", "b2b", "ywg", "jd", "tb", "pdd", "sn", "smzdm", "zbj", "xy"}     # 国内平台：前三档都不行时用爬虫专用 Chrome
USD = 7.1
P_NAME = {p["key"]: p["name"] for p in PLATFORMS}

# 哪些行业去哪些平台：卖货的去电商和批发，卖服务的去接单平台，政府采购网都查
GOODS_SECS = {"consumer", "health", "tech", "mfg", "cycle"}
SERVICE_L1 = {"社会服务", "传媒", "计算机", "非银金融", "建筑装饰", "环保", "交通运输"}
SERVICE_TRK = {"t:ai", "t:edu", "t:creator", "t:local", "t:silver", "t:data", "t:crossborder", "t:livecom"}
NO_RETAIL_L1 = {"银行", "非银金融", "房地产", "公用事业", "交通运输", "建筑装饰", "煤炭", "石油石化", "钢铁", "国防军工", "综合"}

_lock = threading.Lock()
_run = {"running": {}, "log": []}       # 正在抓的方向 → 开始时间


def _read(p, d):
    v = BZ._read_json(p, d)
    return v if isinstance(v, type(d)) else d


def _write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    BZ._write_json(p, data)


def _log(msg):
    _run["log"] = _run["log"][-40:] + [[int(time.time()), msg]]
    try:
        BZ._log("交易平台：" + msg)
    except Exception:
        pass


def _plain(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    return re.sub(r"[\s\u3000\xa0]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


# ───────────────────────── 抓网页：直连 → Scrapling 快速 → 浏览器 ─────────────────────────
# v199：分成三种。「请登录」很多网站页面顶上本来就有（苏宁：您好，请登录），只在页面几乎没内容时才算被要求登录
_LOGIN_URL = re.compile(r"(passport\.jd\.com|login\.taobao\.com|login\.tmall\.com|login\.1688\.com|yangkeduo\.com/login|passport\.alibaba|signin\.ebay|ap/signin|"
                        r"passport\.goofish|shopee\.sg/buyer/login|upwork\.com/ab/account-security/login)", re.I)
_CAPTCHA = re.compile(r"(punish|滑动验证|拖动下方滑块|请拖动|安全验证|访问过于频繁|频繁访问|人机验证|请完成验证|验证一下|captcha|访问受限|系统繁忙|"
                      r"Robot Check|Robot or human|Pardon Our Interruption|unusual traffic|Access Denied|verify you are a human)", re.I)
_SOFT = re.compile(r"(请登录|登录后|扫码登录|密码登录)")
_BLOCK = _CAPTCHA


def _why(h, final, txt):
    m = _LOGIN_URL.search(str(final or ""))
    if m:
        return "要登录（%s）" % m.group(1).replace("\\", "")
    c = _CAPTCHA.search((h or "")[:200000])
    if c:
        return "被拦了（%s）" % c.group(1)
    if len(txt) < 300:
        s = _SOFT.search((h or "")[:20000])
        return ("要登录或被拦（%s）" % s.group(1)) if s else ("页面是空壳（只有 %d 个字）" % len(txt))
    return "没认出商品 / 公告列表"


def _direct(url, timeout=20):
    import biz_crawler as BC
    b, final = BC._get(url, timeout=timeout)
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc), final
        except Exception:
            continue
    return b.decode("utf-8", "replace"), final


def _tbmod():
    try:
        import trade_browser
        return trade_browser
    except Exception:
        return None


_SEM = {"browser": threading.Semaphore(1), "fast": threading.Semaphore(3)}


def _sc(url, mode):
    with _SEM.get(mode) or threading.Semaphore(9):
        return _sc0(url, mode)


def _sc0(url, mode):
    import scrapling_fetch as SF
    if not SF.available():
        raise RuntimeError("网页抓取增强（Scrapling）还没装好")
    px = None
    try:
        import web_tools as W
        px = W.proxy_for(url) or None
    except Exception:
        pass
    return SF.fetch(url, mode=mode, proxy=px), url


def fetch(pkey, url, ok, trace):
    """抓一个平台的一页。ok(html) 判断抓到的是不是真内容。返回 (html, 方法)；都不行抛错（带原因）。
    顺序：普通方式 → Scrapling 快速 → Scrapling 浏览器 →（国内平台）爬虫专用 Chrome；登录过的平台先用登录好的 Chrome。"""
    st = _read(STATE_FILE, {})
    pref = (st.get(pkey) or {}).get("pref", "")
    order = ["direct", "fast", "browser"]
    TB = _tbmod()
    if TB and (pkey in CN_CHROME or pkey in FOREIGN):        # v202：国外平台也用爬虫 Chrome（走代理）
        order.append("chrome")
    if pkey in FOREIGN and pkey not in LOGIN_SITES and unlock_cfg().get("provider"):
        order.append("unlock")                             # v202：都不行，才用付费解锁服务（要你填钥匙）
    if TB and pkey in TB.SITES and TB.logged_in(pkey):     # v198：你登录过：先用登录好的浏览器（v199：只用它，免得没登录的方式把账号连累了）
        order, pref = ["login"], "login"
        if apify_can(pkey):
            order.append("apify")
    elif pkey in LOGIN_SITES:                              # v203：没登录的，只能交给 Apify（不用你的账号）
        order, pref = ["apify"], ""
    elif apify_can(pkey):
        order.append("apify")                              # v203：免费办法都不行，交给 Apify 现成爬虫（按结果付费）
    if "apify" in order and "unlock" in order:            # v203：Apify 按结果付费、给的是整理好的数据，排在解锁服务前面
        order.remove("apify")
        order.insert(order.index("unlock"), "apify")
    if pref in order:
        order.remove(pref)
        order.insert(0, pref)
    why = []
    for m in order:
        t0 = time.time()
        try:
            if m in ("login", "chrome"):
                r = TB.fetch_ex(url, site=pkey if m == "login" else None, login=(m == "login"), vkey=pkey, vname=P_NAME.get(pkey, pkey))
                h, final = r["html"], r["url"]
            elif m == "unlock":
                h, final = _unlock(url, pkey)
            elif m == "apify":
                h, final = _apify(url, pkey)
            else:
                h, final = _direct(url) if m == "direct" else _sc(url, m)
            txt = _plain(h)
            if ok(h):
                trace.append({"m": SC_NAME[m], "ok": True, "ms": int((time.time() - t0) * 1000)})
                if pref != m:
                    with _lock:
                        st = _read(STATE_FILE, {})
                        st.setdefault(pkey, {})["pref"] = m
                        _write(STATE_FILE, st)
                return h, m
            r = _why(h, final, txt)
        except Exception as e:
            r = X.human(str(e).split("\n")[0])[:90]
        trace.append({"m": SC_NAME[m], "ok": False, "ms": int((time.time() - t0) * 1000), "why": r})
        why.append("%s：%s" % (SC_NAME[m], r))
        if m == "unlock":
            why[-1] = "%s：%s" % (unlock_name(), r)
        if "还没装好" in r or "今天在" in r:
            if "今天在" in r:
                break
            continue
    raise RuntimeError("；".join(why[-2:]) or "没抓到")


# ───────────────────────── 解析 ─────────────────────────
def _num(s):
    s = (s or "").replace(",", "").replace("，", "")
    m = re.match(r"([\d.]+)\s*(万|亿)?", s)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except Exception:
        return None
    return v * (10000 if m.group(2) == "万" else 1e8 if m.group(2) == "亿" else 1)


def _band(prices):
    ps = sorted(p for p in prices if p and 0.1 <= p <= 5e6)
    if len(ps) < 3:
        return None
    q = statistics.quantiles(ps, n=4) if len(ps) >= 4 else [ps[0], statistics.median(ps), ps[-1]]
    return {"n": len(ps), "min": round(ps[0], 2), "p25": round(q[0], 2), "mid": round(statistics.median(ps), 2),
            "p75": round(q[-1], 2), "max": round(ps[-1], 2)}


def _total(text):
    for rx in (r"共\s*([\d,]+)\s*(?:件|个|条|款)", r"找到\s*([\d,]+)\s*(?:件|个|条|款|相关)", r"([\d,]+)\s*件(?:相关)?商品"):
        m = re.search(rx, text)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


SOLD_RX = re.compile(r"(?:已售|销量|成交|月销|付款|已拼|售出)\s*[:：]?\s*([\d.]+\s*万?)\s*\+?\s*(?:件|笔|单|人|个)?")
SOLD_RX2 = re.compile(r"([\d.]+\s*万?)\s*\+?\s*(?:人付款|人收货|人已买|人买过|件已售|人已拼|人购买|人想要)")      # v199：淘宝「1万+人付款」这种数字在前的


def parse_goods(h, price_rx=None, int_div=1.0):
    """商品列表页 → 价格带、销量 / 评价数、商品数（不同网站写法不一样，先认结构化数据，再认页面文字）。
    v199：先认接口数据（爬虫专用 Chrome 收下来的 JSON、网页自带的 __NEXT_DATA__ / ld+json），认到 3 个以上商品就用它。"""
    its = X.goods_json(h, int_div)
    if len(its) >= 3:
        text = _plain(h)
        sold = [i["s"] for i in its if i.get("s")] or [x for x in (_num(y) for y in (SOLD_RX.findall(text)[:80] + SOLD_RX2.findall(text)[:80])) if x]
        cmt = [i["c"] for i in its if i.get("c")]
        return {"band": _band([i["p"] for i in its]), "sold": int(sum(sold)) if sold else None, "sold_n": len(sold),
                "comments": int(sum(cmt)) if cmt else None, "total": _total(text), "src": "接口数据", "n_items": len(its)}
    prices = []
    for rx in ([price_rx] if price_rx else []) + [r'"(?:price|priceInfo|salePrice|jdPrice|p)"\s*:\s*"?(\d+(?:\.\d+)?)"?',
                                                   r"[¥￥]\s*(\d+(?:\.\d+)?)", r"价格\s*[:：]?\s*[¥￥]?\s*(\d+(?:\.\d+)?)"]:
        prices += [float(x) for x in re.findall(rx, h)[:200]]
        if len(prices) >= 8:
            break
    text = _plain(h)
    sold = [_num(x) for x in (SOLD_RX.findall(text)[:80] + SOLD_RX2.findall(text)[:80])]
    sold = [x for x in sold if x]
    cmt = [_num(x) for x in re.findall(r"([\d.]+万?)\+?\s*条评价", text)[:80]]
    cmt = [x for x in cmt if x]
    return {"band": _band(prices), "sold": int(sum(sold)) if sold else None, "sold_n": len(sold),
            "comments": int(sum(cmt)) if cmt else None, "total": _total(text), "src": "网页文字"}


def _good_goods(h, price_rx=None, int_div=1.0):
    return bool(parse_goods(h, price_rx, int_div)["band"])


# 中国政府采购网
def ccgp_url(kw, days=180, bid=0):
    end = datetime.date.today()
    st = end - datetime.timedelta(days=days)
    q = {"searchtype": "1", "page_index": "1", "bidSort": "0", "buyerName": "", "projectId": "", "pinMu": "0", "bidType": str(bid),
         "dbselect": "bidx", "kw": kw, "start_time": st.strftime("%Y:%m:%d"), "end_time": end.strftime("%Y:%m:%d"), "timeType": "6",
         "displayZone": "", "zoneId": "", "pppStatus": "0", "agentName": ""}
    return "http://search.ccgp.gov.cn/bxsearch?" + urllib.parse.urlencode(q)


def parse_ccgp(h):
    t = _plain(h)
    m = re.search(r"共找到\s*([\d,]+)\s*条", t)
    total = int(m.group(1).replace(",", "")) if m else None
    items = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", h, flags=re.S | re.I):
        a = re.search(r"<a[^>]+href=[\"']([^\"']+\.s?html?)[\"'][^>]*>(.*?)</a>", li, flags=re.S | re.I)
        if not a or "ccgp.gov.cn" not in a.group(1):
            continue
        rest = _plain(li)
        d = re.search(r"(20\d\d)[.\-/年](\d{1,2})[.\-/月](\d{1,2})", rest)
        buyer = re.search(r"采购人[：:]\s*([^|｜]+)", rest)
        kind = re.search(r"(公开招标|竞争性磋商|竞争性谈判|询价|单一来源|中标|成交|更正|废标|终止|合同)\S*公告", rest)
        items.append({"t": _plain(a.group(2))[:80], "u": a.group(1), "d": "%s-%02d-%02d" % (d.group(1), int(d.group(2)), int(d.group(3))) if d else "",
                      "buyer": buyer.group(1).strip()[:40] if buyer else "", "kind": kind.group(0) if kind else ""})
    return total, items[:20]


AMT_RX = re.compile(r"(预算金额|最高限价|中标[（(]成交[)）]?金额|中标金额|成交金额|合同金额|总中标金额)[^\d]{0,12}([\d,]+(?:\.\d+)?)\s*(万元|元)")


def parse_amount(h):
    t = _plain(h)
    for m in AMT_RX.finditer(t):
        v = float(m.group(2).replace(",", ""))
        v = v if m.group(3) == "万元" else v / 10000
        if 0.01 <= v <= 5e6:
            return m.group(1), round(v, 2)
    return None


def probe_ccgp(kw, trace):
    h, m = fetch("ccgp", ccgp_url(kw), lambda x: "共找到" in _plain(x), trace)
    total, items = parse_ccgp(h)
    win = None
    try:
        hw, _m = fetch("ccgp", ccgp_url(kw, bid=7), lambda x: "共找到" in _plain(x), [])
        win, _ = parse_ccgp(hw)
    except Exception:
        pass
    amts = []
    for it in items[:4]:
        try:
            hd, _m = _direct(it["u"], timeout=15)
            a = parse_amount(hd)
            if a:
                it["amt"] = a[1]
                it["amt_k"] = a[0]
                amts.append(a[1])
        except Exception:
            pass
        time.sleep(0.6)
    return {"total": total, "win": win, "items": items[:8], "amt_mid": round(statistics.median(amts), 1) if amts else None,
            "amt_n": len(amts), "url": ccgp_url(kw), "via": m, "days": 180}


def probe_goods(key, url, kw, trace, price_rx=None, int_div=1.0):
    h, m = fetch(key, url, lambda x: _good_goods(x, price_rx, int_div), trace)
    g = parse_goods(h, price_rx, int_div)
    g.update(url=url, via=m)
    return g


def b2b_url(kw):
    return "https://s.1688.com/selloffer/offer_search.htm?keywords=" + urllib.parse.quote(kw.encode("gbk", "ignore"))


def ywg_url(kw):
    return "https://www.yiwugo.com/search/s.htm?q=" + urllib.parse.quote(kw)


def sn_url(kw):
    return "https://search.suning.com/" + urllib.parse.quote(kw) + "/"


def tb_url(kw):
    return "https://s.taobao.com/search?q=" + urllib.parse.quote(kw)


def pdd_url(kw):
    return "https://mobile.yangkeduo.com/search_result.html?search_key=" + urllib.parse.quote(kw)


def jd_url(kw):
    return "https://search.jd.com/Search?enc=utf-8&keyword=" + urllib.parse.quote(kw)


def smzdm_url(kw):
    return "https://search.smzdm.com/?c=faxian&v=b&s=" + urllib.parse.quote(kw)


def zbj_url(kw):
    return "https://www.zbj.com/fw/?k=" + urllib.parse.quote(kw)


# ───────────────────────── v198：国外平台 ─────────────────────────
def cfg():
    return _read(STATE_FILE, {}).get("_cfg") or {}


def set_cfg(**kw):
    with _lock:
        st = _read(STATE_FILE, {})
        c = st.setdefault("_cfg", {})
        if isinstance(kw.get("regions"), dict):
            r = c.setdefault("regions", {})
            r.update({k: bool(v) for k, v in kw.pop("regions").items() if k in dict(X.REGIONS)})
        kw.pop("regions", None)
        if isinstance(kw.get("off"), list):
            c["off"] = sorted({str(x) for x in kw.pop("off") if str(x) in P_NAME})
        kw.pop("off", None)
        c.update({k: v for k, v in kw.items() if v is not None})
        _write(STATE_FILE, st)
    return {"ok": True, "cfg": cfg()}


def english(kw):
    """搜索词翻成英文。v199：先查内置词表（软件里全部行业），再联网翻（微软 → 谷歌 → MyMemory），见 biz_trade_x.translate。"""
    return X.translate(kw, "en")


def _k(x):
    x = (x or "").replace(",", "").strip().upper()
    mul = 1000 if x.endswith("K") else 1000000 if x.endswith("M") else 1
    try:
        return float(x.rstrip("KM+").strip()) * mul
    except Exception:
        return None


def parse_foreign(h, price_rx, sold_rx=None, total_rx=r"([\d,]+)\+?\s*results"):
    prices = []
    for x in re.findall(price_rx, h)[:200]:
        try:
            prices.append(float(str(x).replace(",", "")))
        except Exception:
            pass
    text = _plain(h)
    sold = [_k(x) for x in re.findall(sold_rx, text)[:80]] if sold_rx else []
    sold = [x for x in sold if x]
    tm = re.search(total_rx, text, re.I) if total_rx else None
    return {"band": _band(prices), "cur": "$", "sold": int(sum(sold)) if sold else None, "sold_n": len(sold),
            "total": int(tm.group(1).replace(",", "")) if tm else None}


FOREIGN_RX = {
    "amazon": (r'a-offscreen">\s*\$([\d,]+(?:\.\d{2})?)', r"([\d.,]+K?)\+?\s*bought in past month"),
    "ebay": (r'(?:s-item__price|s-card__price)[^>]*>\s*(?:<[^>]+>\s*)*\$([\d,]+(?:\.\d{2})?)', None),
    "aliexpress": (r'(?:US\s*)?\$\s*([\d,]+(?:\.\d{1,2})?)', r"([\d.,]+K?)\+?\s*sold"),
    "alibaba": (r'\$\s*([\d,]+(?:\.\d{1,2})?)', r"([\d.,]+K?)\+?\s*(?:sold|orders)"),
}
FOREIGN_URL = {
    "amazon": lambda en: "https://www.amazon.com/s?k=" + urllib.parse.quote_plus(en),
    "ebay": lambda en: "https://www.ebay.com/sch/i.html?_nkw=" + urllib.parse.quote_plus(en) + "&LH_Sold=1&LH_Complete=1",
    "aliexpress": lambda en: "https://www.aliexpress.com/w/wholesale-" + urllib.parse.quote(re.sub(r"\s+", "-", en.strip())) + ".html",
    "alibaba": lambda en: "https://www.alibaba.com/trade/search?SearchText=" + urllib.parse.quote_plus(en),
}


def probe_foreign(key, kw, trace):
    en = english(kw)
    url = FOREIGN_URL[key](en)
    prx, srx = FOREIGN_RX[key]
    def ok(x):
        return bool(parse_foreign(x, prx)["band"]) or len(X.goods_json(x)) >= 3
    h, m = fetch(key, url, ok, trace)
    its = X.goods_json(h)
    g = parse_foreign(h, prx, srx)
    if len(its) >= 3:                                     # v203：接口数据 / Apify 给的商品更准
        sold = [i["s"] for i in its if i.get("s")]
        g.update(band=_band([i["p"] for i in its]), sold=int(sum(sold)) if sold else g.get("sold"), sold_n=len(sold) or g.get("sold_n"), src="接口数据")
    g.update(url=url, via=m, en=en)
    return g


PROBES = {
    "ccgp": lambda kw, tr: probe_ccgp(kw, tr),
    "b2b": lambda kw, tr: probe_goods("b2b", b2b_url(kw), kw, tr),
    "jd": lambda kw, tr: probe_goods("jd", jd_url(kw), kw, tr, r'<i[^>]*>\s*(\d+(?:\.\d+)?)\s*</i>'),
    "smzdm": lambda kw, tr: probe_goods("smzdm", smzdm_url(kw), kw, tr, r'z-highlight[^>]*>\s*(?:<[^>]+>\s*)*(\d+(?:\.\d+)?)\s*元'),
    "zbj": lambda kw, tr: probe_goods("zbj", zbj_url(kw), kw, tr),
    "ywg": lambda kw, tr: probe_goods("ywg", ywg_url(kw), kw, tr),
    "sn": lambda kw, tr: probe_goods("sn", sn_url(kw), kw, tr),
    "amazon": lambda kw, tr: probe_foreign("amazon", kw, tr),
    "ebay": lambda kw, tr: probe_foreign("ebay", kw, tr),
    "aliexpress": lambda kw, tr: probe_foreign("aliexpress", kw, tr),
    "alibaba": lambda kw, tr: probe_foreign("alibaba", kw, tr),
    "tb": lambda kw, tr: probe_goods("tb", tb_url(kw), kw, tr),
    "pdd": lambda kw, tr: probe_goods("pdd", pdd_url(kw), kw, tr, int_div=100.0),
    "xy": lambda kw, tr: probe_goods("xy", "https://www.goofish.com/search?q=" + urllib.parse.quote(kw), kw, tr),
}
PROBES.update(X.probes(fetch))             # v199：全世界的平台 + 官方公开接口
FAIL_SKIP_N = 6            # 连着 6 次被拦 / 空壳（不是要登录）→ 先跳过 1 天

LOGIN_SKIP_N = 3            # 连着 3 次都要登录 → 先跳过 7 天（省时间），用不用登录的平台顶上
LOGIN_SKIP_DAYS = 7


# ───────────────────────── 一个方向去哪些平台、用什么词搜 ─────────────────────────
APP_L2 = {"游戏", "软件开发", "IT服务", "社交", "数字媒体", "教育", "出版", "影视院线", "互联网电商", "本地生活服务"}
APP_TRK = {"t:ai", "t:edu", "t:creator", "t:local", "t:livecom", "t:data", "t:silver"}
CROWD_L2 = {"消费电子", "小家电", "文娱用品", "家居用品", "饰品", "体育", "其他电子", "照明设备", "个护用品", "厨卫电器", "其他家电"}
CROWD_TRK = {"t:newcons", "t:pet", "t:robot", "t:lowalt", "t:silver"}
NO_GOV_L1 = {"银行", "非银金融", "房地产"}
FOREIGN_TRK = {"t:crossborder", "t:pet", "t:newcons", "t:ev", "t:energy", "t:robot", "t:lowalt"}
CN_GOODS = ["b2b", "ywg", "jd", "tb", "pdd", "xy", "sn", "smzdm"]


def regions_on():
    """v201：不再按地区开关（界面改成一张总表，每个平台单独勾选）。"""
    return {k for k, _n in X.REGIONS}


def off_set():
    return set(cfg().get("off") or [])


def plan(target):
    """方向 → (搜索词, 平台列表)。v199：国内平台 + 按「卖货 / 卖服务 / App / 众筹 / 政府采购」配国外平台（只配开着的地区）。"""
    tx = BZ._tx()
    t = (target or "").strip()
    kw, l1, l2n, sec, trk = t, "", "", "", ""
    if t in tx.get("l3", {}):
        kw = tx["l3"][t]["name"]
        l2 = tx["l2"].get(tx["l3"][t]["l2"], {})
        l1, l2n = l2.get("l1", ""), l2.get("name", "")
    elif t in tx["l2"]:
        kw, l1, l2n = tx["l2"][t]["name"], tx["l2"][t]["l1"], tx["l2"][t]["name"]
    elif t in tx["l1"]:
        kw, l1 = t, t
    elif t in tx["trk"]:
        d = tx["trk"][t]
        kw, trk = (d["kw"][0] if d.get("kw") else d["name"]), t
    if l1:
        sec = next((k.replace("sec:", "") for k, v in tx["sec"].items() if l1 in v["l1"]), "")
    kw = re.sub(r"^其他|Ⅱ$", "", kw).strip() or t
    plats, fits = ["ccgp"], set()
    custom = not (trk or l1)
    if trk:
        if trk in SERVICE_TRK:
            plats.append("zbj")
            fits.add("svc")
        if trk not in ("t:ai", "t:data", "t:edu", "t:creator", "t:local"):
            plats += CN_GOODS
            if trk in FOREIGN_TRK:
                fits.add("goods")
        if trk in APP_TRK:
            fits.add("app")
        if trk in CROWD_TRK:
            fits.add("crowd")
        fits.add("gov")
    elif l1:
        if l1 not in NO_RETAIL_L1 and sec in GOODS_SECS and l1 not in SERVICE_L1:
            plats += CN_GOODS
            fits.add("goods")
        if l1 in SERVICE_L1 or kw in ("IT服务", "软件开发", "专业服务", "教育", "广告营销"):
            plats.append("zbj")
            fits.add("svc")
        if l2n in APP_L2:
            fits.add("app")
        if l2n in CROWD_L2:
            fits.add("crowd")
        if l1 not in NO_GOV_L1:
            fits.add("gov")
    else:                                                 # 自己写的方向：都查一遍
        plats += CN_GOODS + ["zbj"]
        fits = {"goods", "svc", "app", "crowd", "gov"}
    if "app" in fits:
        plats.append("appstore_cn")
    on = regions_on()
    old_foreign = {"goods": ["amazon", "ebay", "aliexpress", "alibaba"]}
    for f in ("goods", "svc", "app", "crowd", "gov"):
        if f not in fits:
            continue
        for k in old_foreign.get(f, []):
            if PREG.get(k) in on:
                plats.append(k)
        for p in X.G:
            if p["fit"] == f and p["region"] in on:
                plats.append(p["key"])
    off = off_set()                                       # v201：表里取消勾选的平台不去抓
    return kw, [p for p in dict.fromkeys(plats) if p not in off]


def probe(target, only=None):
    """去各个平台抓一遍（不用 AI）。返回结果并存下来。"""
    kw, plats = plan(target)
    if only:
        plats = [p for p in plats if p in only]
    key = (target or "").strip()
    with _lock:
        if key in _run["running"]:
            return {"ok": False, "error": "这个方向正在抓"}
        _run["running"][key] = int(time.time())
    res = {}

    live = _live["now"].setdefault(key, {"kw": kw, "started": int(time.time()), "plats": {p: "wait" for p in plats},
                                         "urls": {p: search_url(p, kw) for p in plats}})

    def one(p):
        trace, t0 = [], time.time()
        sk = _skip_why(p)
        if sk:
            live["plats"][p] = "skip"
            return p, {"ok": False, "skipped": True, "error": sk, "trace": [], "ms": 0}
        live["plats"][p] = "run"
        try:
            r = PROBES[p](kw, trace)
            r.update(ok=True, trace=trace, ms=int((time.time() - t0) * 1000))
        except Exception as e:
            r = {"ok": False, "error": str(e)[:200], "trace": trace, "ms": int((time.time() - t0) * 1000)}
        _note(p, r)
        live["plats"][p] = "ok" if r.get("ok") else "bad"
        _feed(kw, p, r)
        return p, r
    try:
        with ThreadPoolExecutor(max_workers=4) as ex:        # v199：几个平台同时抓（同一个平台还是一个一个来）
            for p, r in ex.map(one, plats):
                res[p] = r
    finally:
        with _lock:
            _run["running"].pop(key, None)
            _live["now"].pop(key, None)
    rec = {"target": key, "kw": kw, "at": int(time.time()), "res": res}
    with _lock:
        all_ = _read(TRADE_FILE, {})
        if only and key in all_:                          # v201：只补几个平台时，和以前抓到的合在一起
            merged = dict((all_[key] or {}).get("res") or {})
            merged.update(res)
            rec["res"] = merged
        all_[key] = rec
        if len(all_) > 400:
            for k in sorted(all_, key=lambda k: all_[k].get("at", 0))[:len(all_) - 400]:
                all_.pop(k, None)
        _write(TRADE_FILE, all_)
    n_ok = sum(1 for r in res.values() if r.get("ok"))
    _log("「%s」抓了 %d 个平台，%d 个抓到了" % (kw, len(res), n_ok))
    return {"ok": True, "rec": rec}


def probe_async(target):
    threading.Thread(target=probe, args=(target,), daemon=True, name="biz-trade").start()
    return {"ok": True, "running": True}


def _skip_why(p):
    TB = _tbmod()
    if TB and p in TB.SITES and TB.logged_in(p):
        return ""
    if p in FOREIGN and not cfg().get("foreign", True):
        return "国外平台在设置里关掉了"
    if p in LOGIN_SITES and TB and p in TB.SITES and not apify_can(p):
        return "要先登录（在「交易平台抓取」的表里点「登录%s」，或点上面「一键登录全部」）" % TB.SITES[p]["name"]
    s = _read(STATE_FILE, {}).get(p) or {}
    if s.get("fail_streak", 0) >= FAIL_SKIP_N and time.time() - s.get("fail_at", 0) < 86400:
        return "连着 %d 次被拦或没认出，先跳过，明天再试" % s["fail_streak"]
    if s.get("login_streak", 0) >= LOGIN_SKIP_N:
        left = s.get("login_at", 0) + LOGIN_SKIP_DAYS * 86400 - time.time()
        if left > 0:
            return "连着 %d 次都要登录才给看，先跳过（%d 天后再试）" % (s["login_streak"], max(1, int(left / 86400) + 1))
    return ""


def _note(p, r):
    with _lock:
        st = _read(STATE_FILE, {})
        s = st.setdefault(p, {})
        if r.get("skipped"):
            return
        err = str(r.get("error", ""))
        if r.get("ok"):
            s["login_streak"] = s["fail_streak"] = 0
        elif "要登录" in err:
            s["login_streak"] = s.get("login_streak", 0) + 1
            s["login_at"] = int(time.time())
        elif "今天在" not in err:
            s["fail_streak"] = s.get("fail_streak", 0) + 1
            s["fail_at"] = int(time.time())
        s["at"] = int(time.time())
        s["n_ok" if r.get("ok") else "n_bad"] = s.get("n_ok" if r.get("ok") else "n_bad", 0) + 1
        if r.get("ok"):
            s["last_ok"] = int(time.time())
            s["via"] = SC_NAME.get(r.get("via"), "")
            s["err"] = ""
        else:
            s["err"] = r.get("error", "")[:160]
        _write(STATE_FILE, st)


def get(target):
    return _read(TRADE_FILE, {}).get((target or "").strip())


def running(target):
    return (target or "").strip() in _run["running"]


def status():
    st = _read(STATE_FILE, {})
    out = []
    for p in PLATFORMS:
        x = dict(p)
        x.update(st.get(p["key"]) or {})
        x["skip"] = _skip_why(p["key"])
        x["err"] = "；".join(X.human(e) for e in str(x.get("err") or "").split("；") if e)        # v201：旧记录里的报错也翻成人话
        x["foreign"] = bool(p.get("foreign"))
        x["rname"] = X.R_NAME.get(p.get("region", "cn"), "")
        out.append(x)
    order = ["cn"] + [k for k, _n in X.REGIONS]
    out.sort(key=lambda x: order.index(x.get("region", "cn")) if x.get("region", "cn") in order else 99)
    return out


def regions_info():
    """给界面：每个地区有哪些平台、开没开。"""
    on = regions_on()
    names = {}
    for p in PLATFORMS:
        if p.get("foreign"):
            names.setdefault(p["region"], []).append(re.sub(r"（.*?）|\s*Amazon|\s*Walmart", "", p["name"]).strip())
    return [{"key": k, "name": n, "on": k in on, "plats": "、".join(names.get(k, []))} for k, n in X.REGIONS]


# ───────────────────────── 给人看、给 AI 看 ─────────────────────────
def _yuan(v):
    if v is None:
        return "?"
    return ("%.0f" % v) if v >= 100 else ("%.1f" % v).rstrip("0").rstrip(".")


def lines(rec):
    """一条抓取结果 → 几句话（每个平台一句）。"""
    if not rec:
        return []
    out = []
    for p, r in (rec.get("res") or {}).items():
        nm = P_NAME.get(p, p)
        if not r.get("ok"):
            out.append({"p": p, "ok": False, "txt": "%s：%s（%s）" % (nm, "跳过" if r.get("skipped") else "没抓到", r.get("error", "")[:80])})
            continue
        if p in X.KEYS:
            out.append({"p": p, "ok": True, "txt": X.line(p, r, rec["kw"], nm), "url": r.get("url", ""), "via": SC_NAME.get(r.get("via"), "")})
            continue
        if p == "ccgp":
            s = "%s：近半年搜「%s」有 %s 条采购公告" % (nm, rec["kw"], r["total"] if r.get("total") is not None else "?")
            if r.get("win") is not None:
                s += "，其中中标公告 %d 条" % r["win"]
            if r.get("amt_mid"):
                s += "；抽了 %d 条，预算 / 中标金额中位数约 %s 万元" % (r["amt_n"], _yuan(r["amt_mid"]))
        elif r.get("cur") == "$":
            b = r.get("band") or {}
            s = "%s：搜「%s」" % (nm, r.get("en") or rec["kw"])
            if r.get("total"):
                s += "共 %d 个结果，" % r["total"]
            s += "%s %d 个价格，中间一半在 $%s～$%s（约 ¥%s～¥%s，中位数 $%s）" % (
                "已成交的" if p == "ebay" else "首页", b.get("n", 0), _yuan(b.get("p25")), _yuan(b.get("p75")),
                _yuan((b.get("p25") or 0) * USD), _yuan((b.get("p75") or 0) * USD), _yuan(b.get("mid")))
            if r.get("sold"):
                s += "；%s合计约 %d" % ("上个月卖出" if p == "amazon" else "写着的销量", r["sold"])
        else:
            b = r.get("band") or {}
            s = "%s：搜「%s」" % (nm, rec["kw"])
            if r.get("total"):
                s += "共 %d 个结果，" % r["total"]
            s += "首页 %d 个价格，中间一半在 %s～%s 元（中位数 %s 元，最低 %s、最高 %s）" % (
                b.get("n", 0), _yuan(b.get("p25")), _yuan(b.get("p75")), _yuan(b.get("mid")), _yuan(b.get("min")), _yuan(b.get("max")))
            if r.get("sold"):
                s += "；首页写着的成交 / 销量合计约 %d" % r["sold"]
            if r.get("comments"):
                s += "；评价数合计约 %d" % r["comments"]
            if r.get("src") == "接口数据":
                s += "（取自网页的接口数据，%d 个商品）" % (r.get("n_items") or b.get("n", 0))
        out.append({"p": p, "ok": True, "txt": s, "url": r.get("url", ""), "via": SC_NAME.get(r.get("via"), "")})
    return out


def prompt_text(rec):
    if not rec:
        return ""
    d = datetime.datetime.fromtimestamp(rec["at"]).strftime("%Y-%m-%d %H:%M")
    ls = lines(rec)
    body = "\n".join("- " + x["txt"] + ("（%s）" % x["url"] if x.get("url") else "") for x in ls)
    items = (rec.get("res") or {}).get("ccgp", {}).get("items") or []
    if items:
        body += "\n  政府采购网最近的几条：" + "；".join("%s %s%s%s" % (it.get("d", ""), it["t"], ("（%s）" % it["buyer"]) if it.get("buyer") else "",
                                                       "，%s %s 万元" % (it.get("amt_k", "金额"), _yuan(it["amt"])) if it.get("amt") else "") for it in items[:5])
    return "（%s 爬虫在平台上直接抓的，口径写「交易平台」「电商平台」或「招投标」；国外平台的价格按当天汇率换算成人民币，是大概数；政府采购的「份数 / 条数」是关键词搜出来的，可能混进不相关的）\n%s" % (d, body)


# ───────────────────────── v193：全部抓一遍（不用 AI，只跑爬虫）─────────────────────────
_tb = {"running": False, "stop": False, "ids": [], "i": 0, "ok": 0, "bad": 0, "cur": "", "started": 0, "ended": 0, "name": "", "skipped": 0}


def batch_start(scope="all", fresh_days=3):
    with _lock:
        if _tb["running"]:
            return {"ok": False, "error": "已经在一个个抓了"}
        tx = BZ._tx()
        l2, trk = list(tx["l2"]), list(tx["trk"])
        if scope.startswith("sec:") and scope in tx["sec"]:
            ids, name = [g for g in l2 if tx["l2"][g]["l1"] in tx["sec"][scope]["l1"]], tx["sec"][scope]["name"] + "板块"
        elif scope == "trk":
            ids, name = trk, "新兴赛道"
        else:
            ids, name = trk + l2, "全部（新兴赛道 + 二级行业）"
        old = _read(TRADE_FILE, {})
        cut = time.time() - fresh_days * 86400
        keep, n_fill = [], 0
        for g in ids:                                      # v201：3 天内抓过的，只补还没抓过的平台（新加的、之前没登录跳过的）
            rec = old.get(g) or {}
            if rec.get("at", 0) < cut:
                keep.append((g, None))
                continue
            got = rec.get("res") or {}
            miss = [p for p in plan(g)[1] if p not in got or got[p].get("skipped")]
            if miss:
                keep.append((g, miss))
                n_fill += 1
        _tb.update(running=bool(keep), stop=False, ids=keep, i=0, ok=0, bad=0, cur="", started=int(time.time()), ended=0 if keep else int(time.time()),
                   name=name, skipped=len(ids) - len(keep), fill=n_fill)
    if not keep:
        _log("一个个抓交易平台：%s 都是 %d 天内抓过的，而且每个平台都抓过了，这次没有要抓的" % (name, fresh_days))
        return {"ok": True, "n": 0, "skipped": len(ids), "fill": 0}
    threading.Thread(target=_tb_loop, daemon=True, name="biz-trade-batch").start()
    _log("开始一个个抓交易平台：%s，%d 个（其中 %d 个只补新平台；%d 天内全抓过的 %d 个跳过）" % (name, len(keep), n_fill, fresh_days, len(ids) - len(keep)))
    return {"ok": True, "n": len(keep), "skipped": len(ids) - len(keep), "fill": n_fill}


def batch_stop():
    _tb["stop"] = True
    return {"ok": True}


def _tb_loop():
    try:
        for i, (g, only) in enumerate(list(_tb["ids"])):
            if _tb["stop"]:
                break
            _tb.update(i=i, cur=g)
            try:
                r = probe(g, only)
                rec = (r or {}).get("rec") or {}
                if any(x.get("ok") for x in (rec.get("res") or {}).values()):
                    _tb["ok"] += 1
                else:
                    _tb["bad"] += 1
            except Exception:
                _tb["bad"] += 1
            _tb["i"] = i + 1
    finally:
        _tb.update(running=False, cur="", ended=int(time.time()))
        _log("一个个抓交易平台结束：抓到 %d 个，没抓到 %d 个" % (_tb["ok"], _tb["bad"]))


def batch_status():
    if not _tb["started"]:
        return None
    d = {k: _tb.get(k) for k in ("running", "stop", "i", "ok", "bad", "started", "ended", "name", "skipped", "fill")}
    d["n"] = len(_tb["ids"])
    d["cur_name"] = BZ._resolve(_tb["cur"])[0] if _tb["cur"] else ""
    done = _tb["ok"] + _tb["bad"]
    d["eta"] = int((time.time() - _tb["started"]) / done * (d["n"] - done)) if done else d["n"] * 25
    return d


def coverage():
    """每个平台：适用的行业有多少个、抓过的有多少个（给信息源表格说明「哪些会去抓」）。"""
    tx = BZ._tx()
    ids = list(tx["trk"]) + list(tx["l2"])
    data = _read(TRADE_FILE, {})
    out = {p["key"]: {"fit": 0, "done": 0} for p in PLATFORMS}
    for g in ids:
        _kw, plats = plan(g)
        for p in plats:
            out[p]["fit"] += 1
            if p in ((data.get(g) or {}).get("res") or {}):
                out[p]["done"] += 1
    return out


PREG = {p["key"]: p.get("region", "cn") for p in PLATFORMS}


def _migrate():
    """v199 第一次跑：v198 及以前「连着 3 次要登录 → 跳过 7 天」的记录清掉，让新办法（爬虫专用 Chrome、登录、内置词表）都试一遍。"""
    try:
        with _lock:
            st = _read(STATE_FILE, {})
            c = st.setdefault("_cfg", {})
            if c.get("mig199"):
                return
            for k, v in st.items():
                if not k.startswith("_") and isinstance(v, dict):
                    for f in ("login_streak", "login_at", "pref"):
                        v.pop(f, None)
            c["mig199"] = 1
            _write(STATE_FILE, st)
    except Exception:
        pass


_migrate()


# ───────────────────────── v201：抓取时界面上实时看得到（正在抓哪个平台、刚抓到什么）；单个平台「试抓」─────────────────────────
_live = {"now": {}, "feed": []}
_try = {}


def _one_line(p, r, kw):
    try:
        return (lines({"kw": kw, "at": int(time.time()), "res": {p: r}}) or [{}])[0].get("txt", "")
    except Exception:
        return ""


def _feed(kw, p, r):
    txt = _one_line(p, r, kw)
    last = _live["feed"][-1] if _live["feed"] else {}
    if last.get("p") == p and last.get("txt") == txt[:160]:          # 同一条连着出现只记一次
        last["at"] = int(time.time())
        return
    _live["feed"] = (_live["feed"] + [{"at": int(time.time()), "kw": kw, "p": p, "name": P_NAME.get(p, p), "ok": bool(r.get("ok")), "txt": txt[:160],
                                        "url": r.get("url") or search_url(p, kw)}])[-30:]


def live():
    now = []
    for k, v in list(_live["now"].items()):
        now.append({"target": k, "name": BZ._resolve(k)[0] if k else "", "kw": v["kw"], "started": v["started"],
                    "plats": [[p, st, P_NAME.get(p, p), (v.get("urls") or {}).get(p, "")] for p, st in v["plats"].items()]})
    return {"now": now, "feed": _live["feed"][-12:][::-1]}


def try_one(key, kw):
    """在表里点「试抓」：只抓这一个平台、用你写的词，几十秒内出结果。"""
    kw = (kw or "").strip()[:30] or "宠物"
    if key not in PROBES:
        return {"ok": False, "error": "不认识的平台"}
    if (_try.get(key) or {}).get("running"):
        return {"ok": False, "error": "这个平台正在试抓"}
    sk = _skip_why(key)
    if sk and "要先登录" in sk:
        return {"ok": False, "error": sk}
    _try[key] = {"running": True, "kw": kw, "started": int(time.time()), "url": search_url(key, kw)}

    def go():
        trace, t0 = [], time.time()
        try:
            r = PROBES[key](kw, trace)
            r.update(ok=True, trace=trace, ms=int((time.time() - t0) * 1000))
        except Exception as e:
            r = {"ok": False, "error": str(e)[:200], "trace": trace, "ms": int((time.time() - t0) * 1000)}
        _note(key, r)
        _feed(kw, key, r)
        _try[key] = {"running": False, "kw": kw, "at": int(time.time()), "ok": bool(r.get("ok")), "txt": _one_line(key, r, kw),
                     "url": r.get("url") or search_url(key, kw),
                     "ms": r.get("ms", 0), "steps": [("%s %s" % (t.get("m"), "✓" if t.get("ok") else "✗ " + str(t.get("why", ""))[:40])) for t in r.get("trace") or []]}
    threading.Thread(target=go, daemon=True, name="biz-trade-try").start()
    return {"ok": True, "running": True, "kw": kw}


def try_status():
    cut = time.time() - 3600
    return {k: v for k, v in _try.items() if v.get("running") or v.get("at", 0) > cut}


# ───────────────────────── v202：付费解锁服务（可选）─────────────────────────
# 国外平台用免费办法（直连、Scrapling、爬虫 Chrome）都抓不到时，交给它：它用真人家宽 IP + 自动过验证去打开网页，把网页内容还回来。
# 钥匙加密存在本机（trade_browser.SECRET_FILE），不进 memory、不会传到 GitHub。每天最多用 UNLOCK_CAP 次，免得把额度用光。
UNLOCKERS = {
    "scrapfly": {"name": "Scrapfly", "site": "https://scrapfly.io/", "free": "注册送 1000 点，打开难站一次约 25 点"},
    "scraperapi": {"name": "ScraperAPI", "site": "https://www.scraperapi.com/", "free": "注册送 5000 点，打开难站一次约 10～25 点"},
    "zenrows": {"name": "ZenRows", "site": "https://www.zenrows.com/", "free": "注册有免费试用额度，打开难站一次约 25 点"},
    "scrapedo": {"name": "Scrape.do", "site": "https://scrape.do/", "free": "注册有免费试用额度"},
}
UNLOCK_CAP = 100
CC = {"amazon": "us", "ebay": "us", "aliexpress": "us", "alibaba": "us", "walmart": "us", "amz_uk": "gb", "amz_de": "de", "amz_fr": "fr",
      "amz_jp": "jp", "rakuten": "jp", "yja": "jp", "amz_in": "in", "flipkart": "in", "indiamart": "in", "lazada": "sg", "meli_mx": "mx",
      "meli_br": "br", "amz_br": "br", "amz_ae": "ae", "jumia": "ng", "mic": "us", "dhgate": "us", "kickstarter": "us"}


def unlock_cfg():
    TB = _tbmod()
    try:
        c = (TB.get_secret("unlock") if TB else None) or {}
    except Exception:
        c = {}
    return c if c.get("provider") in UNLOCKERS and c.get("key") else {}


def unlock_name():
    return UNLOCKERS.get(unlock_cfg().get("provider"), {}).get("name", "付费解锁服务")


def unlock_info():
    """给界面：用的哪家、钥匙尾号、今天用了几次（不给钥匙本身）。"""
    c = unlock_cfg()
    u = _read(STATE_FILE, {}).get("_unlock") or {}
    today = time.strftime("%Y-%m-%d")
    return {"provider": c.get("provider", ""), "tail": (c.get("key") or "")[-4:], "today": u.get("n", 0) if u.get("day") == today else 0,
            "cap": UNLOCK_CAP, "list": [{"k": k, "name": v["name"], "site": v["site"], "free": v["free"]} for k, v in UNLOCKERS.items()]}


def set_unlock(provider, key):
    TB = _tbmod()
    if not TB:
        return {"ok": False, "error": "存不了"}
    if not provider:
        TB.set_secret("unlock", None)
        return {"ok": True, "unlock": unlock_info()}
    if provider not in UNLOCKERS:
        return {"ok": False, "error": "不认识的服务"}
    key = (key or "").strip() or (unlock_cfg().get("key") if unlock_cfg().get("provider") == provider else "")
    if not key:
        return {"ok": False, "error": "要填钥匙（API Key）"}
    TB.set_secret("unlock", {"provider": provider, "key": key})
    return {"ok": True, "unlock": unlock_info()}


def unlock_url(provider, key, url, cc):
    q = urllib.parse.quote(url, safe="")
    if provider == "scrapfly":
        return "https://api.scrapfly.io/scrape?key=%s&url=%s&asp=true&render_js=true%s" % (key, q, "&country=" + cc if cc else "")
    if provider == "scraperapi":
        return "https://api.scraperapi.com/?api_key=%s&url=%s&render=true%s" % (key, q, "&country_code=" + cc if cc else "")
    if provider == "zenrows":
        return "https://api.zenrows.com/v1/?apikey=%s&url=%s&js_render=true&premium_proxy=true%s" % (key, q, "&proxy_country=" + cc if cc else "")
    return "https://api.scrape.do/?token=%s&url=%s&render=true&super=true%s" % (key, q, "&geoCode=" + cc if cc else "")


def _unlock(url, pkey):
    c = unlock_cfg()
    if not c:
        raise RuntimeError("没设置付费解锁服务")
    today = time.strftime("%Y-%m-%d")
    with _lock:
        st = _read(STATE_FILE, {})
        u = st.get("_unlock") or {}
        if u.get("day") != today:
            u = {"day": today, "n": 0}
        if u["n"] >= UNLOCK_CAP:
            raise RuntimeError("今天已经用了 %d 次，先停一停（免得把额度用光），明天接着用" % UNLOCK_CAP)
        u["n"] += 1
        st["_unlock"] = u
        _write(STATE_FILE, st)
    api = unlock_url(c["provider"], c["key"], url, CC.get(pkey, ""))
    import biz_crawler as BC
    last = ""
    for px in BC._proxies(api):
        try:
            r = BC._req_json(api, proxy=px, timeout=120)
            if isinstance(r, dict):                       # Scrapfly 返回 JSON：result.content 才是网页
                res = r.get("result") or {}
                if res.get("content"):
                    return res["content"], res.get("url") or url
                last = str(r.get("message") or r.get("error") or r.get("code") or "返回的不是网页")[:80]
                continue
            if isinstance(r, str) and len(r) > 200:
                return r, url
            last = "返回的内容太少"
        except Exception as e:
            m = str(e)
            last = ("钥匙不对或额度用完了（%s）" % m[:40]) if re.search(r"\b(401|402|403)\b", m) else X.human(m)[:80]
    raise RuntimeError(last or "连不上")


# ───────────────────────── v202：点平台就能跳到它的搜索页 ─────────────────────────
DOMESTIC_URL = {"ccgp": ccgp_url, "b2b": b2b_url, "ywg": ywg_url, "jd": jd_url, "tb": tb_url, "pdd": pdd_url, "sn": sn_url, "smzdm": smzdm_url,
                "zbj": zbj_url, "xy": lambda kw: "https://www.goofish.com/search?q=" + urllib.parse.quote(kw)}


def search_url(p, kw):
    """这个平台搜这个词的网址（不联网：翻译只用内置词表和翻过的）；拼不出就给首页。"""
    home = next((x["url"] for x in PLATFORMS if x["key"] == p), "")
    try:
        if p in DOMESTIC_URL:
            return DOMESTIC_URL[p](kw)
        if p in FOREIGN_URL:
            en = X.cached_tr(kw, "en")
            return FOREIGN_URL[p](en) if en else home
        xp = X.BY_KEY.get(p)
        if xp and xp.get("url"):
            q = X.cached_tr(kw, xp.get("lang", "en"))
            return X.build_url(xp, q) if q else home
        if p == "freelancer":
            en = X.cached_tr(kw, "en")
            return "https://www.freelancer.com/search/projects?q=" + urllib.parse.quote(en) if en else home
        if p == "kickstarter":
            en = X.cached_tr(kw, "en")
            return "https://www.kickstarter.com/discover/advanced?term=" + urllib.parse.quote(en) if en else home
    except Exception:
        pass
    return home


# ───────────────────────── v203：Apify 现成爬虫（可选，按结果付费）─────────────────────────
# Apify 上别人写好、一直在维护的爬虫：被封、改版都由他们处理，我们只按拿到的商品付钱（抓不到不收钱）。
# 免费套餐每月送 5 美元额度；Lazada 这个爬虫约 2 美元 / 1000 个商品。令牌加密存在本机，不进 memory、不传 GitHub。
APIFY_CAP = 150           # 每天最多跑这么多次，免得把额度用光
APIFY_ITEMS = 40          # 每次最多要 40 个商品（够算价格带，也省钱）
AMZ_ACTOR = "santamaria-automations/amazon-search-scraper"
APIFY = {
    "lazada": {"actor": "lergassy/lazada-scraper", "q": "q", "input": lambda q, url: {"country": "SG", "searchTerms": [q], "maxItems": APIFY_ITEMS}},
    "shopee": {"actor": "lergassy/shopee-scraper", "q": "keyword", "input": lambda q, url: {"country": "SG", "searchTerms": [q], "maxItems": APIFY_ITEMS}},
}
for _k in ("amazon", "amz_uk", "amz_de", "amz_fr", "amz_jp", "amz_in", "amz_br", "amz_ae"):
    APIFY[_k] = {"actor": AMZ_ACTOR, "q": "k", "input": lambda q, url: {"startUrls": [{"url": url}]}}


def apify_cfg():
    TB = _tbmod()
    try:
        c = (TB.get_secret("apify") if TB else None) or {}
    except Exception:
        c = {}
    return c if c.get("token") else {}


def apify_can(p):
    return p in APIFY and bool(apify_cfg())


def apify_info():
    c = apify_cfg()
    u = _read(STATE_FILE, {}).get("_apify") or {}
    today = time.strftime("%Y-%m-%d")
    return {"on": bool(c), "tail": (c.get("token") or "")[-4:], "today": u.get("n", 0) if u.get("day") == today else 0, "cap": APIFY_CAP,
            "plats": [P_NAME.get(k, k) for k in APIFY], "keys": list(APIFY), "site": "https://console.apify.com/sign-up",
            "token_url": "https://console.apify.com/settings/integrations"}


def set_apify(token):
    TB = _tbmod()
    if not TB:
        return {"ok": False, "error": "存不了"}
    token = (token or "").strip()
    TB.set_secret("apify", {"token": token} if token else None)
    return {"ok": True, "apify": apify_info()}


def _apify(url, pkey):
    c, a = apify_cfg(), APIFY.get(pkey)
    if not c or not a:
        raise RuntimeError("没设置 Apify")
    q = (urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get(a["q"]) or [""])[0]
    today = time.strftime("%Y-%m-%d")
    with _lock:
        st = _read(STATE_FILE, {})
        u = st.get("_apify") or {}
        if u.get("day") != today:
            u = {"day": today, "n": 0}
        if u["n"] >= APIFY_CAP:
            raise RuntimeError("Apify 今天已经跑了 %d 次，先停一停（免得把额度用光），明天接着用" % APIFY_CAP)
        u["n"] += 1
        st["_apify"] = u
        _write(STATE_FILE, st)
    api = ("https://api.apify.com/v2/acts/%s/run-sync-get-dataset-items?token=%s&timeout=240&maxItems=%d"
           % (a["actor"].replace("/", "~"), urllib.parse.quote(c["token"]), APIFY_ITEMS))
    import biz_crawler as BC
    last = ""
    for px in BC._proxies(api):
        try:
            r = BC._req_json(api, data=a["input"](q, url), proxy=px, timeout=300)
            if isinstance(r, list):
                rows = [x for x in r if isinstance(x, dict) and x.get("type") != "error"]
                if not rows:
                    last = "Apify 跑完了，但没拿到商品" + ("（%s）" % str((r[0] or {}).get("error") or "")[:60] if r and isinstance(r[0], dict) else "")
                    continue
                return '<script type="application/json" data-apify="1">%s</script>' % json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"), url
            last = str(((r or {}).get("error") or {}).get("message") if isinstance(r, dict) else r)[:90] or "返回的不是数据"
        except Exception as e:
            m = str(e)
            last = ("令牌不对（401）" if "401" in m else "额度用完了或要付费（402）" if "402" in m else "Apify 跑太久没回来（超时）" if "timed out" in m.lower()
                    else X.human(m)[:90])
    raise RuntimeError(last or "连不上 Apify")
