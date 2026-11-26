"""超能小助 · 商业 · 真实市场 · 交易平台爬虫（v192 新增）

市场雷达抓的是新闻；这里去「真有人在买卖」的平台上抓一个方向的实际数据：
  · 中国政府采购网：近半年有多少条采购 / 中标公告，抽几条看预算和中标金额（企业和政府真金白银的需求）
  · 1688（阿里巴巴批发）：批发价格带、有多少货源、成交了多少（上游供货和进货成本）
  · 京东：零售价格带、评价数（消费者真买的东西，评价数≈销量的影子）
  · 什么值得买：消费者实际下单的到手价（价格带、大家觉得值不值）
  · 猪八戒网：服务接单的报价和成交（卖服务、接项目的生意）
抓法和市场雷达一样：先普通方式直连；被拦、要登录、只拿到空壳时，用 Scrapling 快速模式补救，再不行开真浏览器；
哪种管用记下来，下次先用。要登录才能看的就不硬闯，记成「要登录」。不用 AI。
结果存 memory/biz/real/trade.json，交给 AI 核实时当「资料③」，也显示在体检卡上。
"""
from __future__ import annotations

import datetime
import html as _html
import re
import statistics
import threading
import time
import urllib.parse

import biz_intel as BZ

TRADE_FILE = BZ.BIZ_DIR / "real" / "trade.json"
STATE_FILE = BZ.BIZ_DIR / "real" / "trade_state.json"
SC_NAME = {"direct": "普通方式", "fast": "Scrapling 快速", "browser": "Scrapling 浏览器"}

PLATFORMS = [
    {"key": "ccgp", "name": "中国政府采购网", "kind": "采购", "url": "http://www.ccgp.gov.cn/",
     "what": "政府、学校、医院、国企近半年的采购和中标公告有多少条，抽几条看预算和中标金额"},
    {"key": "b2b", "name": "1688（阿里巴巴批发）", "kind": "批发", "url": "https://www.1688.com/",
     "what": "批发价格带、货源多不多、成交件数：进货要多少钱、上游卖得动不动"},
    {"key": "ywg", "name": "义乌购（义乌小商品批发）", "kind": "批发", "url": "https://www.yiwugo.com/",
     "what": "不用登录的批发价：义乌商贸城几万家商户的出厂 / 批发价格带（1688 要登录时靠它）"},
    {"key": "jd", "name": "京东", "kind": "零售", "url": "https://www.jd.com/",
     "what": "零售价格带和评价数（评价数大致反映卖了多少）"},
    {"key": "sn", "name": "苏宁易购", "kind": "零售", "url": "https://www.suning.com/",
     "what": "不用登录的零售价：家电、数码、日用、食品的标价和评价数（京东要登录时靠它）"},
    {"key": "smzdm", "name": "什么值得买", "kind": "到手价", "url": "https://www.smzdm.com/",
     "what": "消费者实际下单的到手价、点「值」的人多不多"},
    {"key": "zbj", "name": "猪八戒网", "kind": "服务接单", "url": "https://www.zbj.com/",
     "what": "卖服务、接项目的报价和成交笔数"},
]
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
_BLOCK = re.compile(r"(请登录|登录后|扫码登录|密码登录|passport\.jd\.com|login\.taobao|login\.1688|punish|滑动验证|拖动下方滑块|安全验证|"
                    r"访问过于频繁|频繁访问|验证码|人机验证|captcha|访问受限|系统繁忙)", re.I)


def _direct(url, timeout=20):
    import biz_crawler as BC
    b, final = BC._get(url, timeout=timeout)
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc), final
        except Exception:
            continue
    return b.decode("utf-8", "replace"), final


def _sc(url, mode):
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
    """抓一个平台的一页。ok(html) 判断抓到的是不是真内容。返回 (html, 方法)；都不行抛错（带原因）。"""
    st = _read(STATE_FILE, {})
    pref = (st.get(pkey) or {}).get("pref", "")
    order = ["direct", "fast", "browser"]
    if pref in order:
        order.remove(pref)
        order.insert(0, pref)
    why = []
    for m in order:
        t0 = time.time()
        try:
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
            bm = _BLOCK.search(h[:200000]) or _BLOCK.search(str(final or ""))
            r = ("要登录或被拦（%s）" % bm.group(1)) if bm else ("页面是空壳（只有 %d 个字）" % len(txt)) if len(txt) < 300 else "没认出商品 / 公告列表"
        except Exception as e:
            r = str(e).split("\n")[0][:80]
        trace.append({"m": SC_NAME[m], "ok": False, "ms": int((time.time() - t0) * 1000), "why": r})
        why.append("%s：%s" % (SC_NAME[m], r))
        if "还没装好" in r:
            break
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


def parse_goods(h, price_rx=None):
    """商品列表页 → 价格带、销量 / 评价数、商品数（不同网站写法不一样，先认结构化数据，再认页面文字）。"""
    prices = []
    for rx in ([price_rx] if price_rx else []) + [r'"(?:price|priceInfo|salePrice|jdPrice|p)"\s*:\s*"?(\d+(?:\.\d+)?)"?',
                                                   r"[¥￥]\s*(\d+(?:\.\d+)?)", r"价格\s*[:：]?\s*[¥￥]?\s*(\d+(?:\.\d+)?)"]:
        prices += [float(x) for x in re.findall(rx, h)[:200]]
        if len(prices) >= 8:
            break
    text = _plain(h)
    sold = [_num(x) for x in SOLD_RX.findall(text)[:80]]
    sold = [x for x in sold if x]
    cmt = [_num(x) for x in re.findall(r"([\d.]+万?)\+?\s*条评价", text)[:80]]
    cmt = [x for x in cmt if x]
    return {"band": _band(prices), "sold": int(sum(sold)) if sold else None, "sold_n": len(sold),
            "comments": int(sum(cmt)) if cmt else None, "total": _total(text)}


def _good_goods(h, price_rx=None):
    g = parse_goods(h, price_rx)
    return bool(g["band"]) and not _BLOCK.search(h[:5000])


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


def probe_goods(key, url, kw, trace, price_rx=None):
    h, m = fetch(key, url, lambda x: _good_goods(x, price_rx), trace)
    g = parse_goods(h, price_rx)
    g.update(url=url, via=m)
    return g


def b2b_url(kw):
    return "https://s.1688.com/selloffer/offer_search.htm?keywords=" + urllib.parse.quote(kw.encode("gbk", "ignore"))


def ywg_url(kw):
    return "https://www.yiwugo.com/search/s.htm?q=" + urllib.parse.quote(kw)


def sn_url(kw):
    return "https://search.suning.com/" + urllib.parse.quote(kw) + "/"


def jd_url(kw):
    return "https://search.jd.com/Search?enc=utf-8&keyword=" + urllib.parse.quote(kw)


def smzdm_url(kw):
    return "https://search.smzdm.com/?c=faxian&v=b&s=" + urllib.parse.quote(kw)


def zbj_url(kw):
    return "https://www.zbj.com/fw/?k=" + urllib.parse.quote(kw)


PROBES = {
    "ccgp": lambda kw, tr: probe_ccgp(kw, tr),
    "b2b": lambda kw, tr: probe_goods("b2b", b2b_url(kw), kw, tr),
    "jd": lambda kw, tr: probe_goods("jd", jd_url(kw), kw, tr, r'<i[^>]*>\s*(\d+(?:\.\d+)?)\s*</i>'),
    "smzdm": lambda kw, tr: probe_goods("smzdm", smzdm_url(kw), kw, tr, r'z-highlight[^>]*>\s*(?:<[^>]+>\s*)*(\d+(?:\.\d+)?)\s*元'),
    "zbj": lambda kw, tr: probe_goods("zbj", zbj_url(kw), kw, tr),
    "ywg": lambda kw, tr: probe_goods("ywg", ywg_url(kw), kw, tr),
    "sn": lambda kw, tr: probe_goods("sn", sn_url(kw), kw, tr),
}
LOGIN_SKIP_N = 3            # 连着 3 次都要登录 → 先跳过 7 天（省时间），用不用登录的平台顶上
LOGIN_SKIP_DAYS = 7


# ───────────────────────── 一个方向去哪些平台、用什么词搜 ─────────────────────────
def plan(target):
    """方向 → (搜索词, 平台列表)。"""
    tx = BZ._tx()
    t = (target or "").strip()
    kw, l1, sec, trk = t, "", "", ""
    if t in tx.get("l3", {}):
        kw = tx["l3"][t]["name"]
        l1 = tx["l2"].get(tx["l3"][t]["l2"], {}).get("l1", "")
    elif t in tx["l2"]:
        kw, l1 = tx["l2"][t]["name"], tx["l2"][t]["l1"]
    elif t in tx["l1"]:
        kw, l1 = t, t
    elif t in tx["trk"]:
        d = tx["trk"][t]
        kw, trk = (d["kw"][0] if d.get("kw") else d["name"]), t
    if l1:
        sec = next((k.replace("sec:", "") for k, v in tx["sec"].items() if l1 in v["l1"]), "")
    kw = re.sub(r"^其他|Ⅱ$", "", kw).strip() or t
    plats = ["ccgp"]
    if trk:
        plats += ["zbj"] if trk in SERVICE_TRK else []
        plats += ["b2b", "ywg", "jd", "sn", "smzdm"] if trk not in ("t:ai", "t:data", "t:edu", "t:creator", "t:local") else []
    elif l1:
        if l1 not in NO_RETAIL_L1 and sec in GOODS_SECS and l1 not in SERVICE_L1:
            plats += ["b2b", "ywg", "jd", "sn", "smzdm"]
        if l1 in SERVICE_L1 or kw in ("IT服务", "软件开发", "专业服务", "教育", "广告营销"):
            plats += ["zbj"]
    else:                                                 # 自己写的方向：都查一遍
        plats += ["b2b", "ywg", "jd", "sn", "smzdm", "zbj"]
    return kw, list(dict.fromkeys(plats))


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
    try:
        for p in plats:
            trace = []
            t0 = time.time()
            sk = _skip_why(p)
            if sk:
                res[p] = {"ok": False, "skipped": True, "error": sk, "trace": [], "ms": 0}
                continue
            try:
                r = PROBES[p](kw, trace)
                r.update(ok=True, trace=trace, ms=int((time.time() - t0) * 1000))
            except Exception as e:
                r = {"ok": False, "error": str(e)[:200], "trace": trace, "ms": int((time.time() - t0) * 1000)}
            res[p] = r
            _note(p, r)
            time.sleep(1.0)
    finally:
        with _lock:
            _run["running"].pop(key, None)
    rec = {"target": key, "kw": kw, "at": int(time.time()), "res": res}
    with _lock:
        all_ = _read(TRADE_FILE, {})
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
    s = _read(STATE_FILE, {}).get(p) or {}
    if s.get("login_streak", 0) >= LOGIN_SKIP_N:
        left = s.get("login_at", 0) + LOGIN_SKIP_DAYS * 86400 - time.time()
        if left > 0:
            return "连着 %d 次都要登录才给看，先跳过（%d 天后再试）" % (s["login_streak"], max(1, int(left / 86400) + 1))
    return ""


def _note(p, r):
    with _lock:
        st = _read(STATE_FILE, {})
        s = st.setdefault(p, {})
        if r.get("ok"):
            s["login_streak"] = 0
        elif "登录" in str(r.get("error", "")) or "空壳" in str(r.get("error", "")):
            s["login_streak"] = s.get("login_streak", 0) + 1
            s["login_at"] = int(time.time())
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
        out.append(x)
    return out


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
        if p == "ccgp":
            s = "%s：近半年搜「%s」有 %s 条采购公告" % (nm, rec["kw"], r["total"] if r.get("total") is not None else "?")
            if r.get("win") is not None:
                s += "，其中中标公告 %d 条" % r["win"]
            if r.get("amt_mid"):
                s += "；抽了 %d 条，预算 / 中标金额中位数约 %s 万元" % (r["amt_n"], _yuan(r["amt_mid"]))
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
    return "（%s 爬虫在平台上直接抓的，口径写「交易平台」「电商平台」或「招投标」）\n%s" % (d, body)


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
        keep = [g for g in ids if (old.get(g) or {}).get("at", 0) < cut]
        _tb.update(running=True, stop=False, ids=keep, i=0, ok=0, bad=0, cur="", started=int(time.time()), ended=0, name=name,
                   skipped=len(ids) - len(keep))
    threading.Thread(target=_tb_loop, daemon=True, name="biz-trade-batch").start()
    _log("开始一个个抓交易平台：%s，%d 个（%d 天内抓过的 %d 个跳过）" % (name, len(keep), fresh_days, len(ids) - len(keep)))
    return {"ok": True, "n": len(keep), "skipped": len(ids) - len(keep)}


def batch_stop():
    _tb["stop"] = True
    return {"ok": True}


def _tb_loop():
    try:
        for i, g in enumerate(list(_tb["ids"])):
            if _tb["stop"]:
                break
            _tb.update(i=i, cur=g)
            try:
                r = probe(g)
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
    d = {k: _tb[k] for k in ("running", "stop", "i", "ok", "bad", "started", "ended", "name", "skipped")}
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
