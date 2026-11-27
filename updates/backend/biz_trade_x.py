"""超能小助 · 真实市场 · 交易平台：全世界的平台 + 通用的取数办法（v199 新增）

1. 通用取数：不再只靠「在网页文字里找 ¥ 符号」。按顺序认三种结构化数据：
   · 爬虫专用 Chrome 打开网页时，顺手把网页自己去调的接口数据（JSON）收下来——京东、淘宝、1688、拼多多的商品列表
     其实都是这样来的，拿到它就不怕网页改版、也不用破解签名（签名是网页自己算的）；
   · 网页里自带的结构化数据（__NEXT_DATA__、ld+json，沃尔玛这类网站都有）；
   · 都没有，才退回去在网页文字里认价格。
2. 搜索词翻译：内置词表（软件里所有行业）→ 翻过的记住 → 微软 → 谷歌 → MyMemory，哪个通用哪个。
3. 汇率：每天取一次（open.er-api.com），取不到用内置的大概数。
4. 全世界的平台：亚马逊多国站、沃尔玛、乐天、雅虎拍卖（已成交）、美客多、Flipkart、Lazada、Jumia、
   中国制造网、敦煌网、IndiaMART；官方公开接口：美国联邦采购（USAspending）、欧盟招标（TED）、
   苹果应用商店、Freelancer 接单、Kickstarter 众筹。
"""
from __future__ import annotations

import datetime
import html as _html
import json
import re
import statistics
import threading
import time
import urllib.parse

import biz_intel as BZ

TR_FILE = BZ.BIZ_DIR / "real" / "trade_tr.json"
FX_FILE = BZ.BIZ_DIR / "real" / "trade_fx.json"
_lock = threading.Lock()


def _read(p, d):
    v = BZ._read_json(p, d)
    return v if isinstance(v, type(d)) else d


def _write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    BZ._write_json(p, data)


_ERR = [(r"Errno 111|Connection refused|ECONNREFUSED", "连不上（被拒绝：多半是代理没开或网站拦了）"),
        (r"Errno -2|Errno 11001|getaddrinfo|Name or service not known|nodename nor servname|ERR_NAME_NOT_RESOLVED", "找不到这个网站（网络或代理有问题）"),
        (r"timed out|timeout|Timeout|ERR_TIMED_OUT", "等太久没回应（超时）"),
        (r"ERR_PROXY_CONNECTION_FAILED|ProxyError|Tunnel connection failed", "代理连不上（看看代理软件开着没有）"),
        (r"ERR_CONNECTION_RESET|Connection reset|RemoteDisconnected|10054", "连接被网站掐断了"),
        (r"SSL|CERTIFICATE|ERR_CERT", "加密连接出错（网络或代理问题）"),
        (r"HTTP Error 403|\b403\b", "被拒绝访问（403，可能被识别成爬虫）"), (r"HTTP Error 429|\b429\b", "访问太频繁（429）"),
        (r"HTTP Error 404|\b404\b", "网址不存在（404，平台可能改版了）"), (r"HTTP Error 5\d\d", "网站自己出错了（5xx），过会儿再试")]


def human(msg):
    """把网络报错翻成人话。"""
    m = str(msg or "")
    for rx, say in _ERR:
        if re.search(rx, m):
            return say
    return m


def _short(e):
    s = human(str(e).split("\n")[0])
    return s[:90] or e.__class__.__name__


def plain(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    return re.sub(r"[\s\u3000\xa0]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


# ───────────────────────── 数字 ─────────────────────────
_UNIT = {"万": 1e4, "w": 1e4, "W": 1e4, "千": 1e3, "k": 1e3, "K": 1e3, "mil": 1e3, "Tsd.": 1e3, "M": 1e6, "亿": 1e8}


def money(s, dec="."):
    """'1,299.00' / '1.299,00'（dec=','）/ '1 299,00' → 1299.0"""
    s = str(s or "").replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".") if dec == "," else s.replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", s)
    try:
        return float(m.group(0)) if m else None
    except Exception:
        return None


def count(s, dec="."):
    """'1万+' '10万+人付款' '2.3K' '1.000+'（德国写法）'5 mil' 1234 → 数"""
    if isinstance(s, bool) or s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s)
    m = re.search(r"(\d[\d.,\s\u202f\xa0]*\d|\d)\s*(万|千|亿|Tsd\.|mil\b|[kKwWM](?![a-zA-Z]))?", s)
    if not m:
        return None
    unit = m.group(2) or ""
    num = m.group(1)
    if unit and re.search(r"[.,]\d{1,2}$", num.strip()):      # 2.3万、1,2 mil：小数点
        v = money(num.replace(",", "."), ".")
    else:
        v = money(num, dec)
    return v * _UNIT.get(unit, 1) if v is not None else None


def band(prices):
    ps = sorted(p for p in prices if p and 0.01 <= p <= 1e8)
    if len(ps) < 3:
        return None
    q = statistics.quantiles(ps, n=4) if len(ps) >= 4 else [ps[0], statistics.median(ps), ps[-1]]
    r = lambda v: round(v, 2)
    return {"n": len(ps), "min": r(ps[0]), "p25": r(q[0]), "mid": r(statistics.median(ps)), "p75": r(q[-1]), "max": r(ps[-1])}


# ───────────────────────── 通用取数：结构化数据 ─────────────────────────
_JSONP = re.compile(r"^\s*[\w$.]+\s*\(\s*([\[{].*[\]}])\s*\)\s*;?\s*$", re.S)
_SCRIPT_JSON = re.compile(r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>', re.S | re.I)


def loads_loose(t):
    """JSON 或 JSONP（xxx({...})）→ 对象；不是就返回 None。"""
    t = (t or "").strip()
    if not t:
        return None
    if t[0] in "[{":
        try:
            return json.loads(t)
        except Exception:
            pass
    if re.match(r"[\w$.]+\s*\(", t[:120]):
        m = _JSONP.match(t[:12_000_000])
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None


def jsons_in(h):
    """整页本身是 JSON / 抓包抓到的接口数据（data-cap）/ __NEXT_DATA__ / ld+json。"""
    out = []
    t = (h or "").lstrip()
    if t[:1] in "[{" or re.match(r"[\w$.]+\s*\(", t[:120]):
        o = loads_loose(t)
        if o is not None:
            return [o]
    for m in _SCRIPT_JSON.finditer(h or ""):
        o = loads_loose(m.group(1).replace("<\\/", "</"))
        if o is not None:
            out.append(o)
        if len(out) >= 60:
            break
    return out


_TITLE = ("title", "name", "skuName", "wareName", "wname", "subject", "offerTitle", "itemName", "productName", "goodsName",
          "goods_name", "raw_title", "item_title", "displayName", "itemTitle", "shortName", "trackName", "product_name")
_PRICE = ("price", "salePrice", "jdPrice", "finalPrice", "promotionPrice", "priceShow", "reservePrice", "zkFinalPrice",
          "discountPrice", "minPrice", "min_group_price", "normal_price", "current_price", "currentPrice", "displayPrice",
          "sellingPrice", "offerPrice", "priceText", "realPrice", "showPrice", "lowPrice", "linePrice", "salePriceU", "priceU",
          "price_info", "priceInfo", "amount", "value")
_SOLD = ("realSales", "sales", "sold", "saleQuantity", "sales_tip", "salesTip", "soldCount", "volume", "monthSales", "tradeQuantity",
         "bookedCount", "saleCount", "inOrderCount30Days", "totalSold", "buyCount", "sale_num", "soldQuantity", "goodsSales",
         "itemSoldCntShow", "soldNum", "sellCount", "saleNum", "boughtCount", "quantitySumMonth", "historical_sold", "wantNum")
_CMT = ("commentCount", "comments", "comment_count", "reviewCount", "reviews", "review", "feedbacks", "ratingCount",
        "userRatingCount", "rating_count", "evaluateCount", "commentNum", "commentFuzzy", "numberOfReviews", "reviewsCount",
        "ratingsTotal", "totalReviews")


def _flat(d, depth=0, out=None):
    """把一个商品的数据摊平（最多往里看 3 层），浅的键优先。"""
    if out is None:
        out = {}
    if depth > 3 or not isinstance(d, dict):
        return out
    for k, v in d.items():
        if not isinstance(v, (dict, list)):
            out.setdefault(k, v)
    for k, v in d.items():
        if isinstance(v, dict):
            inner = next((v[x] for x in ("number", "value", "count", "text", "num") if isinstance(v.get(x), (str, int, float))), None)
            if inner is not None:
                out.setdefault(k, inner)                   # 1688：tradeQuantity: {number: "900+"}
            _flat(v, depth + 1, out)
        elif isinstance(v, list) and v and isinstance(v[0], dict) and len(v) <= 3:
            _flat(v[0], depth + 1, out)
    return out


def _price_val(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return money(re.sub(r"[^\d.,\-]", " ", v).strip().split(" ")[0] if re.search(r"\d", v) else "", ".")
    return None


def _item(d, int_div=1.0):
    f = _flat(d)
    title = next((f[k] for k in _TITLE if isinstance(f.get(k), str) and len(f[k].strip()) >= 2), None)
    if not title:
        return None
    price = None
    for k in _PRICE:
        v = f.get(k)
        if v in (None, "", 0, "0"):
            continue
        p = _price_val(v)
        if p:
            if k.endswith("U"):                                   # 俄罗斯 Wildberries 这类：以「分」为单位
                p /= 100.0
            elif isinstance(v, int) and int_div != 1:            # 拼多多这类：整数「分」
                p /= int_div
            price = p
            break
    if not price or not (0.01 <= price <= 1e8):
        return None
    sold = next((x for x in (count(f[k]) for k in _SOLD if k in f) if x), None)
    cmt = next((x for x in (count(f[k]) for k in _CMT if k in f and not isinstance(f[k], (dict, list))) if x), None)
    return {"t": re.sub(r"<[^>]+>", "", title).strip()[:80], "p": price, "s": sold, "c": cmt}


def items_from(obj, int_div=1.0):
    """在一大坨 JSON 里找「商品列表」：一个列表里多数元素既有名字又有价格。返回最大的那个。"""
    best, stack, seen = [], [obj], 0
    while stack and seen < 30000:
        o = stack.pop()
        seen += 1
        if isinstance(o, dict):
            stack.extend(v for v in o.values() if isinstance(v, (dict, list)))
        elif isinstance(o, list):
            dicts = [x for x in o[:300] if isinstance(x, dict)]
            if len(dicts) >= 3:
                its = [i for i in (_item(x, int_div) for x in dicts) if i]
                if len(its) >= 3 and len(its) >= 0.4 * len(dicts) and len(its) > len(best):
                    best = its
            stack.extend(x for x in o[:300] if isinstance(x, (dict, list)))
    return best


def goods_json(h, int_div=1.0):
    """网页 + 抓包数据里的商品（去重）。"""
    out, seen = [], set()
    for o in jsons_in(h):
        for it in items_from(o, int_div):
            k = (it["t"], round(it["p"], 2))
            if k in seen:
                continue
            seen.add(k)
            out.append(it)
            if len(out) >= 300:
                return out
    return out


def goods_from_page(h, p):
    """按平台设置（价格写法、销量写法）认一页商品：先认结构化数据，再认网页文字。"""
    dec = p.get("dec", ".")
    its = goods_json(h, p.get("int_div", 1.0))
    text = plain(h)
    sold, cmts = [], []
    if len(its) >= 3:
        prices, src = [i["p"] for i in its], "接口数据"
        sold = [i["s"] for i in its if i.get("s")]
        cmts = [i["c"] for i in its if i.get("c")]
    else:
        prices, src = [], "网页文字"
        for rx in p.get("price") or []:
            for x in re.findall(rx, h)[:300]:
                x = next((g for g in x if g), "") if isinstance(x, tuple) else x
                v = money(x, dec)
                if v:
                    prices.append(v)
            if len(prices) >= 8:
                break
    if not sold:
        for rx in p.get("sold") or []:
            sold += [count(x if isinstance(x, str) else next((g for g in x if g), ""), dec) for x in re.findall(rx, text)[:100]]
        sold = [x for x in sold if x]
    if not cmts:
        for rx in p.get("cmt") or []:
            cmts += [count(x, dec) for x in re.findall(rx, text)[:100]]
        cmts = [x for x in cmts if x]
    total = None
    for rx in p.get("total") or []:
        m = re.search(rx, text, re.I)
        if m:
            total = int(count(next(g for g in m.groups() if g), dec) or 0) or None
            break
    return {"band": band(prices), "sold": int(sum(sold)) if sold else None, "sold_n": len(sold),
            "comments": int(sum(cmts)) if cmts else None, "total": total, "n_items": len(its), "src": src}


# ───────────────────────── 搜索词翻译 ─────────────────────────
LANG_NAME = {"en": "英文", "ja": "日文", "de": "德文", "fr": "法文", "es": "西班牙文", "pt": "葡萄牙文"}


def _tr_ms(kw, lang):
    import biz_crawler as BC
    for px in BC._proxies("https://edge.microsoft.com/"):
        try:
            tok = BC._req_json("https://edge.microsoft.com/translate/auth", proxy=px, timeout=10)
            r = BC._req_json("https://api-edge.cognitive.microsofttranslator.com/translate?from=zh-Hans&to=%s&api-version=3.0" % lang,
                             data=[{"Text": kw}], headers={"Authorization": "Bearer " + str(tok).strip()}, proxy=px, timeout=15)
            t = ((r[0].get("translations") or [{}])[0].get("text") or "").strip()
            if t:
                return t
        except Exception:
            continue
    return ""


def _tr_google(kw, lang):
    import biz_crawler as BC
    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh-CN&tl=%s&dt=t&q=%s" % (lang, urllib.parse.quote(kw))
    for px in BC._proxies(url):
        try:
            r = BC._req_json(url, proxy=px, timeout=12)
            t = "".join(seg[0] for seg in (r[0] or []) if seg and seg[0]).strip()
            if t:
                return t
        except Exception:
            continue
    return ""


def _tr_mymemory(kw, lang):
    import biz_crawler as BC
    url = "https://api.mymemory.translated.net/get?q=%s&langpair=zh-CN|%s" % (urllib.parse.quote(kw), lang)
    for px in BC._proxies(url):
        try:
            r = BC._req_json(url, proxy=px, timeout=12)
            t = ((r.get("responseData") or {}).get("translatedText") or "").strip()
            if t and "MYMEMORY WARNING" not in t.upper():
                return t
        except Exception:
            continue
    return ""


def translate(kw, lang="en"):
    """中文搜索词 → 外文。内置词表 → 记住的 → 微软 → 谷歌 → MyMemory；非英文翻不了就退回英文。"""
    kw = (kw or "").strip()
    if not kw:
        raise RuntimeError("没有搜索词")
    if not re.search(r"[\u4e00-\u9fff]", kw):
        return kw
    if lang == "en":
        try:
            from biz_trade_en import EN
            if kw in EN:
                return EN[kw]
        except Exception:
            pass
    cache = _read(TR_FILE, {})
    hit = (cache.get(lang) or {}).get(kw)
    if hit:
        return hit
    if lang == "en":
        old = ((BZ._read_json(BZ.BIZ_DIR / "real" / "trade_state.json", {}) or {}).get("_en") or {}).get(kw)   # v198 翻过的
        if old:
            return old
    bad = []
    for name, fn in (("微软", _tr_ms), ("谷歌", _tr_google), ("MyMemory", _tr_mymemory)):
        try:
            t = fn(kw, lang)
        except Exception:
            t = ""
        t = re.sub(r"[^\w\s&'\-]", " ", t or "")
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            with _lock:
                c = _read(TR_FILE, {})
                c.setdefault(lang, {})[kw] = t
                _write(TR_FILE, c)
            return t
        bad.append(name)
    if lang != "en":
        return translate(kw, "en")
    raise RuntimeError("搜索词翻不成英文（%s翻译都连不上，内置词表里也没有「%s」）" % ("、".join(bad), kw))


# ───────────────────────── 汇率（每天取一次）─────────────────────────
FX_STATIC = {"CNY": 1.0, "USD": 7.1, "EUR": 8.0, "GBP": 9.3, "JPY": 0.047, "INR": 0.083, "BRL": 1.3, "MXN": 0.38, "SGD": 5.4,
             "NGN": 0.0047, "AED": 1.93, "CAD": 5.1, "AUD": 4.6}
_fx_busy = {"on": False}


def _fx_refresh():
    import biz_crawler as BC
    url = "https://open.er-api.com/v6/latest/USD"
    for px in BC._proxies(url):
        try:
            r = BC._req_json(url, proxy=px, timeout=10)
            rates = r.get("rates") or {}
            if r.get("result") == "success" and rates.get("CNY"):
                cny = float(rates["CNY"])
                _write(FX_FILE, {"at": int(time.time()), "src": "open.er-api.com", "cny": {c: cny / float(v) for c, v in rates.items() if v}})
                return True
        except Exception:
            continue
    d = _read(FX_FILE, {})
    d["at"] = int(time.time()) - 86400 + 3600                   # 一小时后再试
    _write(FX_FILE, d)
    return False


def fx(cur):
    """1 个外币 ≈ 多少人民币。"""
    if not cur or cur == "CNY":
        return 1.0
    d = _read(FX_FILE, {})
    if time.time() - d.get("at", 0) > 86400 and not _fx_busy["on"]:
        _fx_busy["on"] = True
        try:
            _fx_refresh()
        finally:
            _fx_busy["on"] = False
        d = _read(FX_FILE, {})
    return (d.get("cny") or {}).get(cur) or FX_STATIC.get(cur)


SYM = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "JP¥", "INR": "₹", "BRL": "R$", "MXN": "MX$", "SGD": "S$", "NGN": "₦",
       "AED": "AED ", "CNY": "¥", "CAD": "C$", "AUD": "A$"}


def _n(v):
    if v is None:
        return "?"
    return ("{:,.0f}".format(v)) if abs(v) >= 100 else ("%.2f" % v).rstrip("0").rstrip(".")


def _yi(yuan):
    if yuan is None:
        return "?"
    if yuan >= 1e8:
        return "%.1f 亿元" % (yuan / 1e8)
    if yuan >= 1e4:
        return "%.0f 万元" % (yuan / 1e4)
    return "%s 元" % _n(yuan)


# ───────────────────────── 全世界的平台 ─────────────────────────
REGIONS = [("na", "北美"), ("eu", "欧洲"), ("jp", "日本"), ("sa", "印度"), ("sea", "东南亚"), ("latam", "拉美"),
           ("mea", "中东非洲"), ("b2b", "全球批发 / 跨境"), ("svc", "全球接单、App、众筹"), ("gov", "国外政府采购")]
R_NAME = dict(REGIONS, cn="国内")

AMZ_SOLD = [r"([\d.,]+\s*[KkM]?)\+?\s*bought in past month", r"過去1か月で([\d,.]+(?:万)?)\s*点以上購入",
            r"(?:Mehr als\s*)?([\d.,]+)\s*\+?\s*Mal im letzten Monat gekauft",
            r"(?:Plus de\s*)?([\d\s.,]+[kK]?)\s*\+?\s*achet\S* au cours du mois dernier",
            r"(?:Mais de\s*)?([\d.,]+\s*(?:mil)?)\s*\+?\s*compras? no m[êe]s passado"]
AMZ_TOTAL = [r"of\s+(?:over\s+)?([\d,]+)\s+results", r"([\d,]+)\s*以上の結果", r"([\d,]+)\s*件の結果"]


def _amz(key, name, tld, cur, lang, prx, dec=".", region="", what=""):
    return {"key": key, "name": name, "region": region, "kind": "国外零售", "home": "https://www.amazon.%s/" % tld, "cur": cur, "lang": lang,
            "dec": dec, "url": "https://www.amazon.%s/s?k={q}" % tld, "price": [prx], "sold": AMZ_SOLD, "total": AMZ_TOTAL, "fit": "goods",
            "what": what or "零售价格带，搜索结果里写着的「上个月卖了多少」"}


G = [
    {"key": "walmart", "name": "沃尔玛 Walmart（美国）", "region": "na", "kind": "国外零售", "home": "https://www.walmart.com/", "cur": "USD", "lang": "en",
     "url": "https://www.walmart.com/search?q={q}", "price": [r'"price"\s*:\s*([\d.]+)\s*[,}]', r'\$\s*([\d,]+\.\d{2})'],
     "sold": [r"([\d,.]+\s*[Kk]?)\+?\s*bought since yesterday"], "fit": "goods", "what": "美国第二大零售商：零售价格带、评价数"},
    _amz("amz_uk", "亚马逊 英国站", "co.uk", "GBP", "en", r'a-offscreen">\s*£\s*([\d,]+\.\d{2})', region="eu"),
    _amz("amz_de", "亚马逊 德国站", "de", "EUR", "de", r'a-offscreen">\s*([\d.]+,\d{2})', dec=",", region="eu"),
    _amz("amz_fr", "亚马逊 法国站", "fr", "EUR", "fr", r'a-offscreen">\s*([\d\s\u202f\xa0.]+,\d{2})', dec=",", region="eu"),
    _amz("amz_jp", "亚马逊 日本站", "co.jp", "JPY", "ja", r'a-offscreen">\s*[￥¥]\s*([\d,]+)', region="jp"),
    {"key": "rakuten", "name": "乐天市场 Rakuten（日本）", "region": "jp", "kind": "国外零售", "home": "https://www.rakuten.co.jp/", "cur": "JPY", "lang": "ja",
     "url": "https://search.rakuten.co.jp/search/mall/{qp}/", "price": [r'([\d,]{2,})\s*(?:<[^>]+>\s*)*円'], "cmt": [r"\(([\d,]+)件\)"],
     "fit": "goods", "what": "日本最大的综合网购平台：零售价格带、评价数"},
    {"key": "yja", "name": "雅虎拍卖 已成交（日本）", "region": "jp", "kind": "国外成交", "home": "https://auctions.yahoo.co.jp/", "cur": "JPY", "lang": "ja",
     "url": "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={q}&va={q}&b=1&n=100", "price": [r'([\d,]{3,})\s*円'],
     "total": [r"([\d,]+)\s*件"], "fit": "goods", "what": "只看已经拍出去的：日本二手 / 闲置的真实成交价"},
    _amz("amz_in", "亚马逊 印度站", "in", "INR", "en", r'a-offscreen">\s*₹\s*([\d,]+(?:\.\d{2})?)', region="sa"),
    {"key": "flipkart", "name": "Flipkart（印度）", "region": "sa", "kind": "国外零售", "home": "https://www.flipkart.com/", "cur": "INR", "lang": "en",
     "url": "https://www.flipkart.com/search?q={q}", "price": [r'₹\s*([\d,]+)'], "cmt": [r"\(([\d,]+)\)"], "fit": "goods",
     "what": "印度最大的本土电商：零售价格带、评分人数"},
    {"key": "indiamart", "name": "IndiaMART（印度批发）", "region": "sa", "kind": "国外批发", "home": "https://www.indiamart.com/", "cur": "INR", "lang": "en",
     "url": "https://dir.indiamart.com/search.mp?ss={q}", "price": [r'₹\s*([\d,]+(?:\.\d+)?)'], "fit": "goods",
     "what": "印度最大的 B2B 平台：工厂和批发商的报价"},
    {"key": "lazada", "name": "Lazada（东南亚·新加坡站）", "region": "sea", "kind": "国外零售", "home": "https://www.lazada.sg/", "cur": "SGD", "lang": "en",
     "url": "https://www.lazada.sg/catalog/?ajax=true&q={q}", "price": [r'"price"\s*:\s*"([\d.]+)"'], "fit": "goods",
     "what": "东南亚主流电商：零售价格带、「已售多少」"},
    {"key": "meli_mx", "name": "美客多 Mercado Libre（墨西哥）", "region": "latam", "kind": "国外零售", "home": "https://www.mercadolibre.com.mx/", "cur": "MXN",
     "lang": "es", "url": "https://listado.mercadolibre.com.mx/{qd}", "price": [r'andes-money-amount__fraction[^>]*>\s*([\d.,]+)\s*<'],
     "sold": [r"\+?\s*([\d.,]+\s*(?:mil)?)\s*vendidos"], "fit": "goods", "what": "拉美最大的电商：零售价格带、「卖出多少」"},
    {"key": "meli_br", "name": "美客多 Mercado Livre（巴西）", "region": "latam", "kind": "国外零售", "home": "https://www.mercadolivre.com.br/", "cur": "BRL",
     "lang": "pt", "dec": ",", "url": "https://lista.mercadolivre.com.br/{qd}", "price": [r'andes-money-amount__fraction[^>]*>\s*([\d.,]+)\s*<'],
     "sold": [r"\+?\s*([\d.,]+\s*(?:mil)?)\s*vendidos"], "fit": "goods", "what": "巴西的零售价格带、「卖出多少」"},
    _amz("amz_br", "亚马逊 巴西站", "com.br", "BRL", "pt", r'a-offscreen">\s*R\$\s*([\d.]+,\d{2})', dec=",", region="latam"),
    _amz("amz_ae", "亚马逊 阿联酋站", "ae", "AED", "en", r'a-offscreen">\s*AED\s*([\d,]+(?:\.\d{2})?)', region="mea",
         what="中东（迪拜）零售价格带、「上个月卖了多少」"),
    {"key": "jumia", "name": "Jumia（非洲·尼日利亚站）", "region": "mea", "kind": "国外零售", "home": "https://www.jumia.com.ng/", "cur": "NGN", "lang": "en",
     "url": "https://www.jumia.com.ng/catalog/?q={q}", "price": [r'₦\s*([\d,]+)'], "cmt": [r"\(([\d,]+)\)"], "fit": "goods",
     "what": "非洲最大的电商：零售价格带"},
    {"key": "mic", "name": "中国制造网 Made-in-China", "region": "b2b", "kind": "外贸批发", "home": "https://www.made-in-china.com/", "cur": "USD", "lang": "en",
     "url": "https://www.made-in-china.com/multi-search/{qplus}/F1/1.html", "price": [r'US\$\s*([\d,]+(?:\.\d+)?)'], "fit": "goods",
     "what": "外贸 B2B：中国工厂给国外买家的报价（美元）"},
    {"key": "dhgate", "name": "敦煌网 DHgate", "region": "b2b", "kind": "跨境批发", "home": "https://www.dhgate.com/", "cur": "USD", "lang": "en",
     "url": "https://www.dhgate.com/wholesale/search.do?act=search&searchkey={q}", "price": [r'US\s*\$\s*([\d,]+(?:\.\d+)?)'],
     "sold": [r"([\d,]+)\s*[Ss]old"], "fit": "goods", "what": "跨境小额批发：国外小商家进货价、卖出多少"},
    # ── v201：要登录的国外平台（用登录好的爬虫 Chrome 抓，国外网站自动走代理）──
    {"key": "shopee", "name": "Shopee（东南亚·新加坡站）", "region": "sea", "kind": "国外零售", "home": "https://shopee.sg/", "cur": "SGD", "lang": "en",
     "login": True, "int_div": 100000.0, "url": "https://shopee.sg/search?keyword={q}", "price": [r'\$\s*([\d,]+\.\d{2})'],
     "sold": [r"([\d.,]+\s*[kK]?)\+?\s*sold"], "fit": "goods", "what": "东南亚第一的电商：零售价格带、「已售多少」（搜索要登录）"},
    {"key": "upwork", "name": "Upwork（全球接单）", "region": "svc", "kind": "国外服务接单", "home": "https://www.upwork.com/", "cur": "USD", "lang": "en",
     "login": True, "url": "https://www.upwork.com/nx/search/jobs/?q={q}", "price": [r'(?:budget|Budget)[^$]{0,40}\$\s*([\d,]+(?:\.\d{2})?)', r'\$\s*([\d,]+(?:\.\d{2})?)'],
     "fit": "svc", "what": "全球最大的自由职业平台：正在招人的项目预算（要登录）"},
    # ── 官方公开接口（不用登录、不用钥匙）──
    {"key": "freelancer", "name": "Freelancer（全球接单）", "region": "svc", "kind": "国外服务接单", "home": "https://www.freelancer.com/", "api": "freelancer",
     "fit": "svc", "what": "全世界的人正在花钱找人做的项目：预算多少、多少人抢"},
    {"key": "appstore_us", "name": "苹果应用商店（美国区）", "region": "svc", "kind": "App", "home": "https://apps.apple.com/us/", "api": "appstore_us",
     "fit": "app", "what": "同类 App 有多少、收不收费、卖多少钱、评价人数（≈ 用户多少）"},
    {"key": "kickstarter", "name": "Kickstarter（众筹）", "region": "svc", "kind": "众筹", "home": "https://www.kickstarter.com/", "api": "kickstarter",
     "fit": "crowd", "what": "新产品还没上市就有人掏钱预订：筹到多少钱、多少人支持"},
    {"key": "usaspending", "name": "美国联邦政府采购（USAspending）", "region": "gov", "kind": "国外政府采购", "home": "https://www.usaspending.gov/",
     "api": "usaspending", "fit": "gov", "what": "美国联邦政府过去一年签的合同：多少份、金额多大、谁在买"},
    {"key": "ted", "name": "欧盟招标 TED", "region": "gov", "kind": "国外政府采购", "home": "https://ted.europa.eu/", "api": "ted",
     "fit": "gov", "what": "欧盟各国政府、医院、学校近半年的招标和中标公告"},
]
# 国内也走官方接口的：苹果应用商店中国区
APPSTORE_CN = {"key": "appstore_cn", "name": "苹果应用商店（中国区）", "region": "cn", "kind": "App", "home": "https://apps.apple.com/cn/", "api": "appstore_cn",
               "fit": "app", "what": "同类 App 有多少、收不收费、卖多少钱、评价人数（≈ 用户多少）"}
BY_KEY = {p["key"]: p for p in G + [APPSTORE_CN]}
KEYS = set(BY_KEY)


def build_url(p, q):
    return p["url"].format(q=urllib.parse.quote_plus(q), qp=urllib.parse.quote(q, safe=""), qplus=urllib.parse.quote_plus(q),
                           qd=urllib.parse.quote(re.sub(r"\s+", "-", q.strip())))


def probe_html(key, kw, trace, fetch):
    p = BY_KEY[key]
    q = translate(kw, p["lang"]) if p.get("lang") != "zh" else kw
    url = build_url(p, q)
    h, m = fetch(key, url, lambda x: bool(goods_from_page(x, p)["band"]), trace)
    g = goods_from_page(h, p)
    g.update(url=url, via=m, q=q, cur=p["cur"], fx=fx(p["cur"]))
    return g


# ───────────────────────── 官方公开接口 ─────────────────────────
def _api(url, data=None, headers=None, timeout=25):
    import biz_crawler as BC
    errs = []
    for px in BC._proxies(url):
        try:
            r = BC._req_json(url, data=data, headers=headers, proxy=px, timeout=timeout)
            if isinstance(r, (dict, list)):
                return r
            o = loads_loose(r) if isinstance(r, str) else None
            if o is not None:
                return o
            errs.append("返回的不是数据")
        except Exception as e:
            errs.append(_short(e))
    raise RuntimeError("；".join(errs[-2:]) or "连不上")


def _timed(trace, fn):
    t0 = time.time()
    try:
        r = fn()
    except Exception as e:
        trace.append({"m": "官方接口", "ok": False, "ms": int((time.time() - t0) * 1000), "why": _short(e)})
        raise RuntimeError("官方接口：" + _short(e))
    trace.append({"m": "官方接口", "ok": True, "ms": int((time.time() - t0) * 1000)})
    return r


def _ml(v):
    """TED 的多语言字段 → 一句英文（没有英文就随便一种）。"""
    if isinstance(v, dict):
        v = v.get("eng") or v.get("ENG") or next(iter(v.values()), "")
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v or "")


def api_usaspending(kw, trace, fetch=None):
    en = translate(kw, "en")
    end = datetime.date.today()
    flt = {"keywords": [en if len(en) >= 3 else en + " us"], "award_type_codes": ["A", "B", "C", "D"],
           "time_period": [{"start_date": (end - datetime.timedelta(days=365)).isoformat(), "end_date": end.isoformat()}]}
    base = "https://api.usaspending.gov/api/v2/search/"

    def go():
        c = _api(base + "spending_by_award_count/", data={"filters": flt, "subawards": False})
        r = _api(base + "spending_by_award/", data={"filters": flt, "subawards": False, "limit": 50, "page": 1, "sort": "Award Amount",
                                                    "order": "desc", "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
                                                                                "Description", "Start Date"]})
        return c, r
    c, r = _timed(trace, go)
    rows = (r.get("results") if isinstance(r, dict) else None) or []
    amts = [float(x.get("Award Amount") or 0) for x in rows if float(x.get("Award Amount") or 0) > 0]
    total = ((c.get("results") or {}).get("contracts") if isinstance(c, dict) else None)
    items = [{"t": (x.get("Description") or "")[:90], "buyer": x.get("Awarding Agency") or "", "who": x.get("Recipient Name") or "",
              "amt": x.get("Award Amount"), "d": x.get("Start Date") or ""} for x in rows[:6]]
    return {"kind2": "gov", "total": total, "amt_mid": statistics.median(amts) if amts else None, "amt_sum": sum(amts), "amt_n": len(amts),
            "items": items, "cur": "USD", "fx": fx("USD"), "q": en, "url": "https://www.usaspending.gov/search", "via": "api", "days": 365}


def api_ted(kw, trace, fetch=None):
    en = translate(kw, "en").replace('"', " ")
    d = (datetime.date.today() - datetime.timedelta(days=180)).strftime("%Y%m%d")
    qs = ['FT~"%s" AND PD>=%s' % (en, d), "FT~(%s) AND PD>=%s" % (en, d), 'notice-title~"%s" AND publication-date>=%s' % (en, d)]

    def go():
        last = ""
        for q in qs:
            try:
                r = _api("https://api.ted.europa.eu/v3/notices/search",
                         data={"query": q, "fields": ["publication-number", "notice-title", "buyer-name", "publication-date"], "limit": 20, "page": 1,
                               "scope": "ALL", "paginationMode": "PAGE_NUMBER", "checkQuerySyntax": False})
                if isinstance(r, dict) and "totalNoticeCount" in r:
                    return r
                last = "返回的格式不对"
            except Exception as e:
                last = _short(e)
        raise RuntimeError(last)
    r = _timed(trace, go)
    items = [{"t": _ml(x.get("notice-title"))[:90], "buyer": _ml(x.get("buyer-name"))[:50], "d": str(x.get("publication-date") or "")[:10],
              "u": "https://ted.europa.eu/en/notice/-/detail/" + str(x.get("publication-number") or "")} for x in (r.get("notices") or [])[:6]]
    return {"kind2": "gov", "total": r.get("totalNoticeCount"), "items": items, "cur": "EUR", "fx": fx("EUR"), "q": en,
            "url": "https://ted.europa.eu/en/search/result?FT=" + urllib.parse.quote(en), "via": "api", "days": 180}


def _appstore(cc):
    def f(kw, trace, fetch=None):
        q = kw if cc == "cn" else translate(kw, "en")
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": q, "entity": "software", "country": cc, "limit": 50})
        r = _timed(trace, lambda: _api(url))
        res = (r.get("results") if isinstance(r, dict) else None) or []
        if not res:
            raise RuntimeError("应用商店里没搜到相关的 App")
        paid = [float(x.get("price") or 0) for x in res if float(x.get("price") or 0) > 0]
        top = sorted(res, key=lambda x: -(x.get("userRatingCount") or 0))[:3]
        return {"kind2": "app", "total": len(res), "paid_n": len(paid), "band": band(paid), "ratings": sum(int(x.get("userRatingCount") or 0) for x in res),
                "top": [{"n": (x.get("trackName") or "")[:30], "r": x.get("userRatingCount") or 0} for x in top], "cur": "CNY" if cc == "cn" else "USD",
                "fx": fx("CNY" if cc == "cn" else "USD"), "q": q, "url": "https://apps.apple.com/%s/" % cc, "via": "api"}
    return f


def api_freelancer(kw, trace, fetch=None):
    en = translate(kw, "en")
    url = ("https://www.freelancer.com/api/projects/0.1/projects/active/?" +
           urllib.parse.urlencode({"query": en, "limit": 50, "full_description": "false", "job_details": "false", "user_details": "false"}))
    r = _timed(trace, lambda: _api(url, headers={"Accept": "application/json"}))
    res = (r.get("result") if isinstance(r, dict) else None) or {}
    ps = res.get("projects") or []
    fixed, hourly, bids = [], [], []
    for x in ps:
        b = x.get("budget") or {}
        rate = float((x.get("currency") or {}).get("exchange_rate") or 1)
        lo, hi = b.get("minimum"), b.get("maximum")
        if lo is None and hi is None:
            continue
        mid = (float(lo or hi) + float(hi or lo)) / 2 * rate
        (hourly if x.get("type") == "hourly" else fixed).append(mid)
        bc = (x.get("bid_stats") or {}).get("bid_count")
        if bc is not None:
            bids.append(bc)
    return {"kind2": "svc", "total": res.get("total_count"), "band": band(fixed), "hourly": band(hourly), "n": len(ps),
            "bids_avg": round(statistics.mean(bids), 1) if bids else None, "cur": "USD", "fx": fx("USD"), "q": en,
            "url": "https://www.freelancer.com/search/projects?q=" + urllib.parse.quote(en), "via": "api"}


def api_kickstarter(kw, trace, fetch=None):
    en = translate(kw, "en")
    url = "https://www.kickstarter.com/discover/advanced?" + urllib.parse.urlencode({"term": en, "sort": "magic", "format": "json"})
    hdr = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    try:
        r = _timed(trace, lambda: _api(url, headers=hdr))
    except Exception:
        if not fetch:
            raise
        h, _m = fetch("kickstarter", url, lambda x: isinstance(loads_loose(plain(x) if x.lstrip()[:1] == "<" else x), dict), trace)
        r = loads_loose(h) or loads_loose(plain(h)) or {}
    ps = (r.get("projects") if isinstance(r, dict) else None) or []
    if not ps and not (isinstance(r, dict) and r.get("total_hits") is not None):
        raise RuntimeError("Kickstarter 没返回项目")
    pledged = [float(x.get("usd_pledged") or x.get("converted_pledged_amount") or 0) for x in ps]
    pledged = [x for x in pledged if x > 0]
    won = sum(1 for x in ps if x.get("state") == "successful" or (float(x.get("pledged") or 0) >= float(x.get("goal") or 1e18)))
    return {"kind2": "crowd", "total": r.get("total_hits"), "band": band(pledged), "sum": sum(pledged), "n": len(ps), "won": won,
            "backers": sum(int(x.get("backers_count") or 0) for x in ps), "cur": "USD", "fx": fx("USD"), "q": en,
            "url": "https://www.kickstarter.com/discover/advanced?term=" + urllib.parse.quote(en), "via": "api"}


API = {"usaspending": api_usaspending, "ted": api_ted, "appstore_us": _appstore("us"), "appstore_cn": _appstore("cn"),
       "freelancer": api_freelancer, "kickstarter": api_kickstarter}


def probes(fetch):
    """平台 key → probe(kw, trace)。"""
    out = {}
    for p in G + [APPSTORE_CN]:
        k = p["key"]
        if p.get("api"):
            out[k] = (lambda f: (lambda kw, tr: f(kw, tr, fetch)))(API[p["api"]])
        else:
            out[k] = (lambda kk: (lambda kw, tr: probe_html(kk, kw, tr, fetch)))(k)
    return out


# ───────────────────────── 给人看的一句话 ─────────────────────────
def line(key, r, kw, nm):
    k2, cur = r.get("kind2"), r.get("cur") or "USD"
    rate = r.get("fx") or fx(cur) or 0
    sym = SYM.get(cur, cur + " ")
    cny = lambda v: ("约 ¥" + _n(v * rate)) if (rate and v is not None and cur != "CNY") else ""
    q = r.get("q") or kw
    if k2 == "gov":
        unit = "份合同" if key == "usaspending" else "条招标 / 中标公告"
        s = "%s：过去%s搜「%s」有 %s %s" % (nm, "一年" if r.get("days") == 365 else "半年", q, _n(r["total"]) if r.get("total") is not None else "?", unit)
        if r.get("amt_mid"):
            s += "；金额最大的 %d 份，中位数 %s%s（约 %s），合计 %s%s（约 %s）" % (
                r["amt_n"], sym, _n(r["amt_mid"]), _yi(r["amt_mid"] * rate), sym, _n(r["amt_sum"]), _yi(r["amt_sum"] * rate))
        it = (r.get("items") or [{}])[0]
        if it.get("buyer"):
            s += "；比如 %s 买的「%s」" % (it["buyer"][:40], (it.get("t") or "")[:50])
        return s
    if k2 == "app":
        s = "%s：搜「%s」前 %d 个 App" % (nm, q, r.get("total") or 0)
        b = r.get("band")
        s += "，收费的 %d 个" % (r.get("paid_n") or 0)
        if b:
            s += "（价格中间一半 %s%s～%s%s%s）" % (sym, _n(b["p25"]), sym, _n(b["p75"]), "，" + cny(b["p25"]) + "～" + _n(b["p75"] * rate) if cur != "CNY" else "")
        s += "；评价人数合计约 %s（评价越多用户越多）" % _n(r.get("ratings") or 0)
        if r.get("top"):
            s += "，最多的是 " + "、".join("%s（%s）" % (t["n"], _n(t["r"])) for t in r["top"] if t.get("n"))
        return s
    if k2 == "svc":
        s = "%s：搜「%s」正在招人的项目 %s 个" % (nm, q, _n(r["total"]) if r.get("total") is not None else "?")
        b = r.get("band")
        if b:
            s += "；固定价项目预算中间一半 $%s～$%s（%s～%s 元），中位数 $%s" % (_n(b["p25"]), _n(b["p75"]), cny(b["p25"]).replace("约 ¥", "约 "),
                                                                    _n(b["p75"] * rate), _n(b["mid"]))
        if r.get("hourly"):
            s += "；按小时的中位数 $%s/小时" % _n(r["hourly"]["mid"])
        if r.get("bids_avg"):
            s += "；平均每个项目 %s 人抢" % r["bids_avg"]
        return s
    if k2 == "crowd":
        s = "%s：搜「%s」共 %s 个项目" % (nm, q, _n(r["total"]) if r.get("total") is not None else "?")
        b = r.get("band")
        if b:
            s += "；前 %d 个里筹到的钱中位数 $%s（%s），合计 $%s（约 %s），支持者合计 %s 人，成功的 %d 个" % (
                r.get("n") or 0, _n(b["mid"]), cny(b["mid"]), _n(r.get("sum")), _yi((r.get("sum") or 0) * rate), _n(r.get("backers") or 0), r.get("won") or 0)
        return s
    b = r.get("band") or {}
    if key == "upwork":
        return "%s：搜「%s」正在招人的项目里 %d 个写了预算，中间一半 $%s～$%s（约 ¥%s～¥%s），中位数 $%s" % (
            nm, q, b.get("n", 0), _n(b.get("p25")), _n(b.get("p75")), _n((b.get("p25") or 0) * rate), _n((b.get("p75") or 0) * rate), _n(b.get("mid")))
    s = "%s：搜「%s」" % (nm, q)
    if r.get("total"):
        s += "共 %s 个结果，" % _n(r["total"])
    s += "%s %d 个价格，中间一半在 %s%s～%s%s" % ("已成交的" if key == "yja" else "首页", b.get("n", 0), sym, _n(b.get("p25")), sym, _n(b.get("p75")))
    if rate and cur != "CNY" and b.get("p25") is not None:
        s += "（约 ¥%s～¥%s）" % (_n(b["p25"] * rate), _n(b["p75"] * rate))
    s += "，中位数 %s%s" % (sym, _n(b.get("mid")))
    if r.get("sold"):
        s += "；%s合计约 %s" % ("上个月卖出" if key.startswith("amz") else "写着的销量", _n(r["sold"]))
    if r.get("comments"):
        s += "；评价数合计约 %s" % _n(r["comments"])
    return s
