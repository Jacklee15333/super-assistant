"""超能小助 · 商业 · 真实市场（v191 新增）

市场雷达看的是「新闻多不多」（大家在说什么）；这一块看的是「钱」：
  · 规模：一年卖了多少钱      · 客户：有多少人 / 多少企业在买
  · 购买力：每个客户肯花多少  · 利润：做这一行赚不赚钱
信息源和市场雷达是两套：
  自动取（不用 AI，按时更新）
    1. 国家统计局·社会消费品零售总额（月度）：16 类商品 + 餐饮 + 网上零售，消费者一年花了多少
    2. 国家统计局·规模以上工业企业利润（月度）：41 个工业行业的营业收入、利润总额
    3. 国家统计局·居民收入和消费支出（季度）：人均可支配收入、人均在 8 类消费上花多少（购买力）
       （统计局新版数据平台会挡掉程序访问，这里读的是 www.stats.gov.cn「数据发布」里的新闻稿表格）
    4. 东方财富·上市公司业绩报表（季度）：A 股公司的营收、净利润、毛利率，按申万二级行业汇总
  按需查（点「AI 核实」时联网）
    电商平台（淘宝天猫、京东、拼多多、抖音电商）的公开成交数据、交易 / 接单平台（1688、猪八戒）的报价、
    政府采购网的招标、行业协会和研究机构的报告。AI 只能用查到的数字，每个数字要写口径和出处，
    软件再拿数字回原文里对一遍：对上了标「原文有」，对不上的标「没对上」。

数据都在 memory/biz/real/：data.json（自动取的）、checks.json（核实过的方向）。
"""
from __future__ import annotations

import datetime
import hashlib
import html as _html
import json
import re
import statistics
import threading
import time
import urllib.parse

import biz_intel as BZ

REAL_DIR = BZ.BIZ_DIR / "real"
DATA_FILE = REAL_DIR / "data.json"
CHECKS_FILE = REAL_DIR / "checks.json"

NBS_LIST = "https://www.stats.gov.cn/sj/zxfb/"
EM_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
STALE_S = 12 * 3600            # 超过 12 小时没更新，打开这一页时自动更新一次

STEPS = ["读软件里的数据", "上网查交易和统计数据", "AI 整理体检卡", "核对数字、存结果"]
MARKERS = ["四把尺子", "还缺什么"]
DIMS = ["规模", "客户", "购买力", "利润", "交易"]
BASES = ["统计局", "上市公司", "电商平台", "交易平台", "招投标", "行业报告", "媒体报道", "估算"]

SOURCES = [
    {"key": "retail", "name": "国家统计局·社会消费品零售总额", "what": "规模：消费者一年在吃、穿、用、车、药等 16 类商品和餐饮上花了多少钱",
     "how": "自动，每月中旬发布", "url": NBS_LIST},
    {"key": "ind", "name": "国家统计局·规模以上工业企业利润", "what": "规模和利润：41 个工业行业的营业收入、利润总额、利润率",
     "how": "自动，每月 27 号左右发布", "url": NBS_LIST},
    {"key": "income", "name": "国家统计局·居民收入和消费支出", "what": "购买力：全国每人一年挣多少、在吃穿住行、教育、医疗上各花多少",
     "how": "自动，每季度发布", "url": NBS_LIST},
    {"key": "listed", "name": "东方财富·上市公司业绩报表", "what": "规模、增长、利润：每个行业 A 股公司的营收、净利润、毛利率（头部玩家的盘子）",
     "how": "自动，每季财报后更新", "url": "https://data.eastmoney.com/bbsj/yjbb.html"},
    {"key": "concept", "name": "东方财富·概念板块", "what": "新兴赛道（AI、低空经济、宠物经济…）的相关上市公司：板块里的公司财报加起来",
     "how": "自动，跟着上市公司业绩一起更新", "url": "https://quote.eastmoney.com/center/boardlist.html#concept_board"},
    {"key": "ecom", "name": "电商平台（淘宝天猫、京东、拼多多、抖音电商）", "what": "交易和购买力：卖了多少、什么价位卖得动",
     "how": "AI 核实时查平台和数据机构公开的数据（原始数据要登录，不直接抓）", "url": ""},
    {"key": "trade", "name": "交易 / 接单平台（1688、猪八戒、一品威客）", "what": "服务和批发的报价、有没有人下单",
     "how": "AI 核实时查", "url": ""},
    {"key": "bid", "name": "政府采购网、招投标平台", "what": "企业和政府真金白银的采购需求、预算金额",
     "how": "AI 核实时查", "url": "http://www.ccgp.gov.cn/"},
    {"key": "report", "name": "行业协会、研究机构报告", "what": "市场规模、用户数量、客单价",
     "how": "AI 核实时查，标明口径（报告之间常互相抄、口径不一）", "url": ""},
]

# ───────────────────────── 统计口径 → 行业地图上的格子 ─────────────────────────
# 一个统计行业常常对应好几个二级行业：数字是这一整类的合计，界面上会写清楚。
RETAIL_MAP = {
    "社会消费品零售总额": ["商贸零售/一般零售", "商贸零售"],
    "网上商品零售额": ["商贸零售/互联网电商", "t:livecom"],
    "餐饮收入": ["社会服务/酒店餐饮", "t:tea", "t:local"],
    "粮油、食品类": ["食品饮料/食品加工", "食品饮料/休闲食品", "食品饮料/调味发酵品", "农林牧渔/农产品加工", "t:discount", "食品饮料"],
    "饮料类": ["食品饮料/饮料乳品"],
    "烟酒类": ["食品饮料/白酒", "食品饮料/非白酒"],
    "服装、鞋帽、针纺织品类": ["纺织服饰/服装家纺", "纺织服饰/纺织制造", "纺织服饰"],
    "化妆品类": ["美容护理/化妆品", "美容护理"],
    "金银珠宝类": ["纺织服饰/饰品", "有色金属/贵金属"],
    "日用品类": ["美容护理/个护用品", "轻工制造/家居用品"],
    "体育、娱乐用品类": ["轻工制造/文娱用品", "社会服务/体育", "t:newcons"],
    "书报杂志类": ["传媒/出版"],
    "家用电器和音像器材类": ["家用电器/白色家电", "家用电器/黑色家电", "家用电器/小家电", "家用电器/厨卫电器", "家用电器"],
    "中西药品类": ["医药生物/医药商业", "医药生物/化学制药", "医药生物/中药"],
    "文化办公用品类": ["轻工制造/文娱用品", "计算机/计算机设备"],
    "家具类": ["轻工制造/家居用品"],
    "通讯器材类": ["电子/消费电子", "通信/通信设备"],
    "石油及制品类": ["石油石化/炼化及贸易"],
    "汽车类": ["汽车/乘用车", "汽车/汽车服务", "汽车", "t:ev"],
    "建筑及装潢材料类": ["建筑材料/装修建材", "建筑装饰/装修装饰"],
}
RETAIL_ROWS = ["社会消费品零售总额", "除汽车以外的消费品零售额", "网上商品零售额", "餐饮收入", "商品零售额"] + \
    [k for k in RETAIL_MAP if k not in ("社会消费品零售总额", "网上商品零售额", "餐饮收入")]

IND_MAP = {
    "煤炭开采和洗选业": ["煤炭/煤炭开采", "煤炭"],
    "石油和天然气开采业": ["石油石化/油气开采"],
    "黑色金属矿采选业": ["钢铁/冶钢原料"],
    "有色金属矿采选业": ["有色金属/工业金属", "有色金属/小金属"],
    "非金属矿采选业": ["基础化工/非金属材料"],
    "开采专业及辅助性活动": ["石油石化/油服工程"],
    "农副食品加工业": ["农林牧渔/农产品加工", "农林牧渔/饲料", "食品饮料/食品加工"],
    "食品制造业": ["食品饮料/食品加工", "食品饮料/休闲食品", "食品饮料/调味发酵品", "食品饮料/饮料乳品"],
    "酒、饮料和精制茶制造业": ["食品饮料/白酒", "食品饮料/非白酒", "食品饮料/饮料乳品", "食品饮料"],
    "纺织业": ["纺织服饰/纺织制造"],
    "纺织服装、服饰业": ["纺织服饰/服装家纺", "纺织服饰"],
    "皮革、毛皮、羽毛及其制品和制鞋业": ["纺织服饰/服装家纺"],
    "家具制造业": ["轻工制造/家居用品"],
    "造纸和纸制品业": ["轻工制造/造纸"],
    "印刷和记录媒介复制业": ["轻工制造/包装印刷"],
    "文教、工美、体育和娱乐用品制造业": ["轻工制造/文娱用品", "t:newcons"],
    "石油、煤炭及其他燃料加工业": ["石油石化/炼化及贸易", "煤炭/焦炭", "石油石化"],
    "化学原料和化学制品制造业": ["基础化工/化学原料", "基础化工/化学制品", "基础化工/农化制品", "基础化工"],
    "医药制造业": ["医药生物/化学制药", "医药生物/中药", "医药生物/生物制品", "医药生物", "t:biotech"],
    "化学纤维制造业": ["基础化工/化学纤维"],
    "橡胶和塑料制品业": ["基础化工/塑料", "基础化工/橡胶"],
    "非金属矿物制品业": ["建筑材料/水泥", "建筑材料/玻璃玻纤", "建筑材料/装修建材", "建筑材料"],
    "黑色金属冶炼和压延加工业": ["钢铁/普钢", "钢铁/特钢", "钢铁"],
    "有色金属冶炼和压延加工业": ["有色金属/工业金属", "有色金属/贵金属", "有色金属/能源金属", "有色金属/金属新材料", "有色金属"],
    "通用设备制造业": ["机械设备/通用设备", "机械设备"],
    "专用设备制造业": ["机械设备/专用设备", "机械设备/工程机械"],
    "汽车制造业": ["汽车/乘用车", "汽车/商用车", "汽车/汽车零部件", "汽车", "t:ev"],
    "铁路、船舶、航空航天和其他运输设备制造业": ["机械设备/轨交设备", "国防军工/航空装备", "国防军工/航天装备",
                                                  "国防军工/航海装备", "汽车/摩托车及其他", "t:lowalt", "t:space"],
    "电气机械和器材制造业": ["电力设备/电池", "电力设备/光伏设备", "电力设备/风电设备", "电力设备/电网设备", "电力设备/电机",
                             "电力设备/其他电源设备", "电力设备", "家用电器", "t:energy"],
    "计算机、通信和其他电子设备制造业": ["电子/半导体", "电子/元件", "电子/光学光电子", "电子/消费电子", "电子/其他电子",
                                       "计算机/计算机设备", "通信/通信设备", "电子", "t:chip", "t:compute"],
    "仪器仪表制造业": ["机械设备/自动化设备"],
    "废弃资源综合利用业": ["环保/环境治理"],
    "电力、热力生产和供应业": ["公用事业/电力", "公用事业"],
    "燃气生产和供应业": ["公用事业/燃气"],
    "水的生产和供应业": ["环保/环境治理"],
}
IND_ROWS = ["总计"] + list(IND_MAP) + ["烟草制品业", "金属制品业", "木材加工和木、竹、藤、棕、草制品业", "其他制造业"]

SPEND_CATS = ["食品烟酒", "衣着", "居住", "生活用品及服务", "交通通信", "教育文化娱乐", "医疗保健", "其他用品及服务"]
SPEND_MAP = {
    "食品烟酒": ["食品饮料", "社会服务/酒店餐饮", "农林牧渔", "t:tea", "t:discount"],
    "衣着": ["纺织服饰"],
    "居住": ["房地产", "公用事业", "建筑装饰/装修装饰", "建筑材料/装修建材"],
    "生活用品及服务": ["家用电器", "轻工制造/家居用品", "美容护理/个护用品", "社会服务/本地生活服务", "t:local", "t:pet"],
    "交通通信": ["汽车", "通信/通信服务", "交通运输", "电子/消费电子", "t:ev"],
    "教育文化娱乐": ["社会服务/教育", "社会服务/旅游及景区", "社会服务/体育", "传媒", "t:edu", "t:creator"],
    "医疗保健": ["医药生物", "美容护理/医疗美容", "t:silver", "t:biotech"],
    "其他用品及服务": ["美容护理", "纺织服饰/饰品", "社会服务/专业服务"],
}

_lock = threading.Lock()
_upd = {"running": False, "stage": "", "started": 0, "log": []}


def _log(msg):
    _upd["log"] = (_upd.get("log") or [])[-30:] + [[int(time.time()), msg]]
    try:
        BZ._log("真实市场：" + msg)
    except Exception:
        pass


def _read(p, d):
    return BZ._read_json(p, d)


def _write(p, data):
    REAL_DIR.mkdir(parents=True, exist_ok=True)
    BZ._write_json(p, data)


def _data():
    d = _read(DATA_FILE, {})
    return d if isinstance(d, dict) else {}


# ───────────────────────── 网页 / 表格小工具 ─────────────────────────
def _get(url, timeout=20):
    import biz_crawler as BC
    b, _u = BC._get(url, timeout=timeout)
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", "replace")


def _norm(s):
    s = _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"[\s\u3000\xa0]+", "", s)


def _label(s):
    return re.sub(r"^(其中|其|中)[：:]", "", _norm(s)).lstrip("：:")


def _num(s):
    s = _norm(s).replace(",", "").replace("，", "")
    m = re.fullmatch(r"[-－]?\d+(?:\.\d+)?", s)
    return float(s.replace("－", "-")) if m else None


def _rows(page):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        cells = [c for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)]
        if cells:
            out.append(cells)
    return out


def _plain(page):
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"[\s\u3000\xa0]+", " ", t)


def table_values(page, labels, ncols):
    """表格里按第一格的名字找行，取后面 ncols 个数（拿不到的是 None）。表格认不出来时，退回按正文文字找。"""
    want, got = set(labels), {}
    tables = re.findall(r"<table\b.*?</table>", page, flags=re.S | re.I) or [page]
    tabs = [_rows(t) for t in tables]
    tabs.sort(key=lambda rs: -sum(1 for r in rs if _label(r[0]) in want))   # 同名的行（比如「总计」）先认对得上最多名字的那张表
    for r in [r for rs in tabs for r in rs]:
        lab = _label(r[0])
        if lab in want and lab not in got and len(r) >= ncols + 1:
            vals = [_num(c) for c in r[1:ncols + 1]]
            if sum(v is not None for v in vals) >= max(1, ncols // 2):
                got[lab] = vals
    if len(got) < len(want) // 2:                       # 兜底：按文字找「名字 数 数 数 …」
        text = _plain(page)
        tok = r"(-?\d+(?:\.\d+)?|[（(]注\d[)）]|-)"
        for lab in labels:
            if lab in got:
                continue
            m = re.search(r"(?<![\u4e00-\u9fff])" + re.escape(lab) + r"\s+" + r"\s+".join([tok] * ncols), text)
            if m:
                got[lab] = [_num(x) for x in m.groups()]
    return got


# ───────────────────────── 国家统计局 ─────────────────────────
NBS_KEYS = {"retail": "社会消费品零售总额", "ind": "规模以上工业企业利", "income": "居民收入和消费支出"}


def nbs_find(pages=5):
    """「数据发布」列表里找三份最新的新闻稿 → {key: (标题, 网址)}。"""
    found = {}
    for i in range(pages):
        url = NBS_LIST if i == 0 else NBS_LIST + "index_%d.html" % i
        try:
            page = _get(url)
        except Exception as e:
            _log("统计局列表第 %d 页打不开：%s" % (i + 1, str(e)[:60]))
            break
        for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']*t\d{8}_\d+\.html?)[\"'][^>]*>(.*?)</a>", page, flags=re.S | re.I):
            tag = m.group(0)
            tm = re.search(r"title=[\"']([^\"']+)[\"']", tag)
            title = _html.unescape(tm.group(1) if tm else re.sub(r"<[^>]+>", "", m.group(2))).strip()
            for k, kw in NBS_KEYS.items():
                if k not in found and kw in title and "解读" not in title:
                    found[k] = (title, urllib.parse.urljoin(url, m.group(1)))
        if len(found) == len(NBS_KEYS):
            break
    return found


def _period(title):
    m = re.search(r"(\d{4})年((?:\d+—|\d+-|\d+－)?\d+月份|一季度|上半年|前三季度|全年)?", title or "")
    if not m:
        return ""
    return m.group(1) + "年" + (m.group(2) or "").replace("月份", "月").replace("-", "—").replace("－", "—")


def parse_retail(page, title=""):
    vals = table_values(page, RETAIL_ROWS, 4)
    rows = {}
    for k, v in vals.items():
        rows[k] = {"m": v[0], "m_yoy": v[1], "ytd": v[2], "ytd_yoy": v[3]}
    pm = re.search(r"(\d{4})年(\d+)月份社会消费品零售总额", _plain(page))
    period = ("%s年1—%s月" % (pm.group(1), pm.group(2))) if pm else _period(title)
    return {"period": period, "rows": rows, "title": title}


def parse_ind(page, title=""):
    vals = table_values(page, IND_ROWS, 6)
    rows = {}
    for k, v in vals.items():
        rev, prof = v[0], v[4]
        rows[k] = {"rev": rev, "rev_yoy": v[1], "profit": prof, "profit_yoy": v[5],
                   "margin": round(prof / rev * 100, 2) if rev and prof is not None else None}
    return {"period": _period(title), "rows": rows, "title": title}


def parse_income(page, title=""):
    t = _plain(page)
    sep = r"\s*[，,]\s*"

    def grab(rx, cast=float):
        m = re.search(rx, t)
        return cast(m.group(1)) if m else None

    def growth(name):
        m = re.search(name + r"\s*(\d+)\s*元" + sep + r"比上年(?:同期)?名义(增长|下降)\s*([\d.]+)%", t)
        if not m:
            return None, None
        return float(m.group(1)), float(m.group(3)) * (-1 if m.group(2) == "下降" else 1)
    inc, inc_yoy = growth("全国居民人均可支配收入")
    sp, sp_yoy = growth("全国居民人均消费支出")
    cats = {}
    for c in SPEND_CATS:
        m = re.search(r"人均" + re.escape(c) + r"支出\s*(\d+)\s*元" + sep + r"(增长|下降)\s*([\d.]+)%" + sep +
                      r"占人均消费支出的比重为\s*([\d.]+)%", t)
        if m:
            cats[c] = {"v": float(m.group(1)), "yoy": float(m.group(3)) * (-1 if m.group(2) == "下降" else 1), "share": float(m.group(4))}
    return {"period": (title or "").replace("居民收入和消费支出情况", "").strip() or _period(title), "title": title,
            "income": inc, "income_yoy": inc_yoy, "median": grab(r"全国居民人均可支配收入中位数\s*(\d+)\s*元"),
            "urban": grab(r"城镇居民人均可支配收入\s*(\d+)\s*元"), "rural": grab(r"农村居民人均可支配收入\s*(\d+)\s*元"),
            "spend": sp, "spend_yoy": sp_yoy, "urban_spend": grab(r"城镇居民人均消费支出\s*(\d+)\s*元"),
            "rural_spend": grab(r"农村居民人均消费支出\s*(\d+)\s*元"), "cats": cats}


PARSERS = {"retail": parse_retail, "ind": parse_ind, "income": parse_income}


def update_nbs(data, force=False):
    found = nbs_find()
    if not found:
        raise RuntimeError("统计局「数据发布」列表打不开或没找到新闻稿")
    for k in NBS_KEYS:
        st = data.setdefault("st", {}).setdefault(k, {})
        if k not in found:
            st.update(ok=False, err="列表前几页没找到这份新闻稿", at=int(time.time()))
            continue
        title, url = found[k]
        if not force and (data.get(k) or {}).get("url") == url and st.get("ok"):
            st["at"] = int(time.time())
            continue
        try:
            got = PARSERS[k](_get(url), title)
        except Exception as e:
            st.update(ok=False, err="打不开：%s" % str(e)[:80], at=int(time.time()))
            continue
        n = len(got.get("rows") or got.get("cats") or {})
        if not n:
            st.update(ok=False, err="页面打开了，但没认出表格（统计局可能改了版式）", at=int(time.time()), url=url)
            continue
        got["url"] = url
        data[k] = got
        st.update(ok=True, err="", at=int(time.time()), url=url, n=n, period=got.get("period", ""))
        _log("统计局：%s（%s，%d 项）" % (title, got.get("period", ""), n))


# ───────────────────────── 东方财富·上市公司业绩 ─────────────────────────
def _em_page(date, page):
    q = {"sortColumns": "UPDATE_DATE,SECURITY_CODE", "sortTypes": "-1,-1", "pageSize": "500", "pageNumber": str(page),
         "reportName": "RPT_LICO_FN_CPD", "columns": "ALL", "filter": "(REPORTDATE='%s')" % date,
         "source": "WEB", "client": "WEB"}
    raw = _get(EM_API + "?" + urllib.parse.urlencode(q), timeout=25)
    j = json.loads(raw)
    res = j.get("result") or {}
    return res.get("data") or [], int(res.get("pages") or 0), int(res.get("count") or 0)


def report_dates(today=None):
    d = today or datetime.date.today()
    out = []
    y = d.year
    for _ in range(3):
        for md in ("12-31", "09-30", "06-30", "03-31"):
            s = "%d-%s" % (y, md)
            if s <= d.isoformat():
                out.append(s)
        y -= 1
    return out


def period_name(date):
    y, m = date[:4], date[5:7]
    return y + "年" + {"03": "一季度", "06": "上半年", "09": "前三季度", "12": "全年"}.get(m, "")


_SW = {}


def _sw_names():
    """申万二级行业名 → 编号（行业地图里的「一级/二级」）。"""
    if not _SW:
        import biz_industries as BI
        for l1, _sec, _d, subs in BI.INDUSTRIES:
            for n, _d2, _kw, _co in subs:
                _SW[n] = l1 + "/" + n
            _SW.setdefault(l1, l1)
    return _SW


def sw_id(name, fuzzy=False):
    """申万二级行业名 → 行业地图编号。v193：默认只认名字完全对上的（去掉「Ⅱ」），
    v192 的「名字里含有」会把「上海证券交易所」这种字段也认成「证券」，大多数行业就空了。"""
    n = re.sub(r"[ⅡⅢⅠ]+$|(II|III)$", "", (name or "").strip())
    sw = _sw_names()
    if n in sw:
        return sw[n]
    if fuzzy and 2 <= len(n) <= 8:
        hits = [v for k, v in sw.items() if "/" in v and len(k) >= 2 and (k == n[:len(k)] or n == k[:len(n)])]
        return hits[0] if len(hits) == 1 else ""
    return ""


IND_KEYS = ["PUBLISHNAME", "INDUSTRY", "BOARD_NAME", "INDUSTRY_NAME", "SW_INDUSTRY", "HY"]
_NOT_A = re.compile(r"股转|三板|中小企业股份|新三板|NEEQ|B股|港股|美股", re.I)


def is_a_share(r):
    """只算沪深京 A 股：业绩报表里还混着新三板（六千多家）、B 股。"""
    for k in ("TRADE_MARKET", "SECURITY_TYPE", "TRADE_MARKET_ZJG"):
        v = r.get(k)
        if isinstance(v, str) and _NOT_A.search(v):
            return False
    code = str(r.get("SECURITY_CODE") or "")
    if code[:3] in ("200", "900"):                      # B 股
        return False
    return True


def _pick_key(rows, cands):
    for k in cands:
        if any(r.get(k) is not None for r in rows[:50]):
            return k
    return cands[0]


def _ind_key(rows):
    """哪个字段是「所处行业」：先看常见的几个字段名，按全部行里能完全对上申万二级行业名的多少挑；都对不上再看别的字段。"""
    def hits(k):
        return sum(1 for r in rows if isinstance(r.get(k), str) and sw_id(r[k]))
    best, bn = "PUBLISHNAME", 0
    for k in IND_KEYS:
        n = hits(k)
        if n > bn:
            best, bn = k, n
    if bn < len(rows) * 0.3:
        keys = set()
        for r in rows[:300]:
            keys |= {k for k, v in r.items() if isinstance(v, str)}
        for k in keys - set(IND_KEYS):
            n = hits(k)
            if n > bn:
                best, bn = k, n
    return best


def fetch_period(date):
    rows, page, pages = [], 1, 1
    while page <= pages and page <= 40:
        data, pages, _cnt = _em_page(date, page)
        rows += data
        page += 1
        time.sleep(0.25)
    return dedup(rows)


def dedup(rows):
    """v192：同一家公司会有好几行（更正过的报表等），只留一行：先要标了最新的（ISNEW=1），再按更新时间最新的。
    不去重的话营收会算重（v191 显示 11535 家，实际 A 股只有五千多家）。"""
    def k(r):
        d = "".join(ch for ch in str(r.get("UPDATE_DATE") or r.get("NOTICE_DATE") or "") if ch.isdigit())
        return (0 if str(r.get("ISNEW", "1")) in ("1", "True", "true") else 1, -int(d[:14] or 0))
    best = {}
    for r in sorted(rows, key=k):
        c = str(r.get("SECURITY_CODE") or r.get("SECUCODE") or "")[:6]
        if c and c not in best:
            best[c] = r
    return list(best.values())


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


_DIAG = {}


def aggregate(rows, groups=None):
    """一期财报 → 每个二级行业（和一级行业）的合计：家数、营收、上年营收、净利润、上年净利润、毛利率中位数、营收前五。
    v194：传了 groups（股票代码 → [新兴赛道编号…]）就按它分组——新兴赛道用东方财富概念板块的成分股。"""
    if not rows:
        return {}, ""
    rows = [r for r in rows if is_a_share(r)]
    ik = _ind_key(rows) if groups is None else ""
    if groups is None:
        _DIAG.clear()
    miss = {}
    yk = _pick_key(rows, ["YSTZ", "TOTAL_OPERATE_INCOME_YOY"])
    pk = _pick_key(rows, ["SJLTZ", "PARENT_NETPROFIT_YOY"])
    agg = {}
    for r in rows:
        if groups is not None:
            gs = groups.get(str(r.get("SECURITY_CODE") or "")[:6]) or []
            gid = "x" if gs else ""
            if not gs:
                continue
        else:
            gid = sw_id(r.get(ik), fuzzy=True)
            gs = [gid, gid.split("/")[0]] if gid else []
        rev, npf = _f(r.get("TOTAL_OPERATE_INCOME")), _f(r.get("PARENT_NETPROFIT"))
        if not gid:
            nm_ = str(r.get(ik) or "（空）")
            miss[nm_] = miss.get(nm_, 0) + 1
            continue
        if rev is None or rev <= 0:
            continue
        ry, py, gm = _f(r.get(yk)), _f(r.get(pk)), _f(r.get("XSMLL"))
        name = r.get("SECURITY_NAME_ABBR") or r.get("SECURITY_CODE") or ""
        for g in set(gs):
            a = agg.setdefault(g, {"n": 0, "rev": 0.0, "rev0": 0.0, "rev_b": 0.0, "np": 0.0, "np0": 0.0, "np_b": 0.0, "gm": [], "top": []})
            a["n"] += 1
            a["rev"] += rev
            a["np"] += npf or 0
            if ry is not None and ry > -99:
                a["rev_b"] += rev
                a["rev0"] += rev / (1 + ry / 100)
            if npf is not None and py is not None and py > -99 and npf > 0:
                a["np_b"] += npf
                a["np0"] += npf / (1 + py / 100)
            if gm is not None and -100 < gm < 100:
                a["gm"].append(gm)
            a["top"].append((rev, name, npf))
    if groups is None:
        _DIAG.update(key=ik, rows=len(rows), mapped=len(rows) - sum(miss.values()), miss=sorted(miss.items(), key=lambda x: -x[1])[:12])
    out = {}
    for g, a in agg.items():
        top = sorted(a["top"], key=lambda x: -x[0])[:6]
        out[g] = {"n": a["n"], "rev": round(a["rev"] / 1e8, 1), "np": round(a["np"] / 1e8, 1),
                  "rev_yoy": round((a["rev_b"] / a["rev0"] - 1) * 100, 1) if a["rev0"] > 0 else None,
                  "np_yoy": round((a["np_b"] / a["np0"] - 1) * 100, 1) if a["np0"] > 0 else None,
                  "nm": round(a["np"] / a["rev"] * 100, 1) if a["rev"] else None,
                  "gm": round(statistics.median(a["gm"]), 1) if len(a["gm"]) >= 2 else (round(a["gm"][0], 1) if a["gm"] else None),
                  "top": [[nm, round(rv / 1e8, 1), round((p or 0) / 1e8, 1)] for rv, nm, p in top]}
    return out, ik


# ───────────────────────── v194：新兴赛道 ← 东方财富概念板块 ─────────────────────────
# 新兴赛道（AI、低空经济、宠物经济…）在申万分类里没有自己的行业，所以拿东方财富的概念板块：板块里有哪些公司，就把这些公司的财报加起来。
# 注意：概念股不一定全靠这一块赚钱（比如做 AI 的大公司，大部分营收可能来自别的业务），界面上写明「相关上市公司」。
TRACK_BOARDS = {
    "t:ai": ["人工智能", "AIGC概念", "AI智能体"], "t:compute": ["算力概念", "东数西算", "液冷概念"],
    "t:robot": ["人形机器人", "具身智能"], "t:autodrive": ["无人驾驶", "汽车智能化"], "t:ev": ["新能源车"],
    "t:lowalt": ["低空经济", "飞行汽车"], "t:space": ["商业航天", "卫星互联网", "卫星导航"],
    "t:energy": ["储能", "光伏概念", "氢能源", "风能"], "t:chip": ["国产芯片", "半导体概念", "信创"],
    "t:biotech": ["创新药", "减肥药"], "t:silver": ["银发经济", "养老概念"], "t:pet": ["宠物经济"],
    "t:newcons": ["谷子经济", "IP经济", "新零售"], "t:discount": ["零售", "量贩零食", "新零售"], "t:tea": ["新茶饮", "咖啡", "食品概念"],
    "t:livecom": ["直播电商", "网红经济"], "t:crossborder": ["跨境电商"], "t:creator": ["短剧互动游戏", "网红经济", "文化传媒"],
    "t:edu": ["在线教育", "职业教育", "教育"], "t:local": ["外卖", "社区团购", "即时零售", "新零售"], "t:data": ["数据要素", "信创", "数据确权"],
    "t:future": ["量子技术", "可控核聚变", "脑机接口", "合成生物"],
}
PUSH2 = ["https://push2.eastmoney.com", "https://79.push2.eastmoney.com", "https://17.push2.eastmoney.com", "https://29.push2.eastmoney.com"]


def _push2_all(fs, fields="f12,f14"):
    """东方财富行情列表（分页拿全）→ [{f12: 代码, f14: 名字}, …]。几个服务器轮着试。"""
    import random
    last = None
    for host in PUSH2:
        out, pn, total = [], 1, None
        try:
            while True:
                q = {"pn": str(pn), "pz": "100", "po": "1", "np": "1", "ut": "bd1d9ddb04089700cf9c27f6f7426281", "fltt": "2",
                     "invt": "2", "fid": "f12", "fs": fs, "fields": fields}
                j = json.loads(_get(host + "/api/qt/clist/get?" + urllib.parse.urlencode(q), timeout=20))
                d = (j or {}).get("data") or {}
                diff = d.get("diff") or []
                if isinstance(diff, dict):
                    diff = list(diff.values())
                total = int(d.get("total") or 0)
                out += diff
                if not diff or len(out) >= total or pn >= 60:
                    return out
                pn += 1
                time.sleep(random.uniform(0.5, 1.2))
        except Exception as e:
            last = e
    raise RuntimeError("东方财富概念板块打不开：%s" % str(last)[:80])


def match_boards(boards, tid):
    """新兴赛道 → 用哪几个概念板块：先找名字一样的，再找名字里含着的。"""
    names = {b.get("f14", ""): b.get("f12", "") for b in boards if b.get("f14")}
    got = []
    for c in TRACK_BOARDS.get(tid, []):
        if c in names:
            got.append((c, names[c]))
        else:
            hit = [(n, code) for n, code in names.items() if c in n and len(n) <= len(c) + 8]
            if hit:
                got.append(sorted(hit, key=lambda x: len(x[0]))[0])
    return list(dict.fromkeys(got))[:3]


def update_tracks(data, a_rows, q_rows):
    """新兴赛道的上市公司数字：概念板块成分股 × 财报。失败不影响别的。"""
    st = data.setdefault("st", {}).setdefault("concept", {})
    _upd["stage"] = "东方财富：读概念板块（新兴赛道）…"
    boards = _push2_all("m:90 t:3 f:!50")
    groups, used = {}, {}
    for tid in TRACK_BOARDS:
        bs = match_boards(boards, tid)
        used[tid] = [n for n, _c in bs]
        for name, code in bs:
            _upd["stage"] = "东方财富：读「%s」板块的公司…" % name
            try:
                for x in _push2_all("b:%s f:!50" % code):
                    c = str(x.get("f12") or "")[:6]
                    if c:
                        groups.setdefault(c, set()).add(tid)
            except Exception as e:
                _log("概念板块「%s」没读到：%s" % (name, str(e)[:60]))
            time.sleep(0.6)
    groups = {c: list(v) for c, v in groups.items()}
    ta, _ = aggregate(a_rows, groups)
    tq, _ = aggregate(q_rows, groups) if q_rows else ({}, "")
    for tid in ta:
        ta[tid]["boards"] = used.get(tid, [])
    st.update(ok=True, err="", at=int(time.time()), n=len(ta), period="%d 个概念板块" % len(boards),
              n_trk=len(ta), miss=[t for t in TRACK_BOARDS if not used.get(t)])
    _log("东方财富概念板块：%d 个板块，%d 个新兴赛道对上了" % (len(boards), len(ta)))
    return ta, tq


def update_listed(data):
    st = data.setdefault("st", {}).setdefault("listed", {})
    dates = report_dates()
    annual, latest = None, None
    for dt in dates:
        try:
            _d, _p, cnt = _em_page(dt, 1)
        except Exception as e:
            st.update(ok=False, err="东方财富打不开：%s" % str(e)[:80], at=int(time.time()))
            raise RuntimeError("东方财富打不开：%s" % str(e)[:80])
        if cnt < 3000:                                  # 这一期公司还没报完
            continue
        if latest is None:
            latest = dt
        if dt.endswith("12-31"):
            annual = dt
            break
    if not annual:
        st.update(ok=False, err="没找到报完的年报", at=int(time.time()))
        return
    if (data.get("listed") or {}).get("annual") == annual and data["listed"].get("latest") == latest and st.get("ok") \
            and data["listed"].get("v") == 4 \
            and time.time() - st.get("full_at", 0) < 7 * 86400:
        st["at"] = int(time.time())
        return
    _upd["stage"] = "东方财富：读 %s 年报…" % annual[:4]
    a_rows = [r for r in fetch_period(annual) if is_a_share(r)]
    a_agg, ik = aggregate(a_rows)
    diag = dict(_DIAG)
    q_agg, q_rows = {}, []
    if latest != annual:
        _upd["stage"] = "东方财富：读 %s…" % period_name(latest)
        q_rows = fetch_period(latest)
        q_agg, _ = aggregate(q_rows)
    try:                                                # v194：新兴赛道
        ta, tq = update_tracks(data, a_rows, q_rows)
        a_agg.update(ta)
        q_agg.update(tq)
    except Exception as e:
        data.setdefault("st", {}).setdefault("concept", {}).update(ok=False, err=str(e)[:120], at=int(time.time()))
        _log("新兴赛道没取到：%s" % str(e)[:100])
    if not a_agg:
        st.update(ok=False, err="读到了 %d 家，但没认出所处行业（字段 %s）" % (len(a_rows), ik), at=int(time.time()))
        return
    data["listed"] = {"annual": annual, "latest": latest, "annual_name": period_name(annual), "latest_name": period_name(latest),
                      "companies": len(a_rows), "a": a_agg, "q": q_agg, "v": 4, "diag": diag}   # v3：只算 A 股、行业名完全对上；v4：新兴赛道（概念板块）
    st.update(ok=True, err="", at=int(time.time()), full_at=int(time.time()), n=len(a_rows),
              period=period_name(annual) + ("、" + period_name(latest) if latest != annual else ""),
              mapped=diag.get("mapped", 0), n_ind=len([g for g in a_agg if "/" in g]), field=ik,
              miss=diag.get("miss", [])[:6])
    if diag.get("rows") and diag.get("mapped", 0) < diag["rows"] * 0.6:
        st["warn"] = "只有 %d / %d 家认出了行业（字段 %s），没认出的多是：%s" % (
            diag.get("mapped", 0), diag["rows"], ik, "、".join("%s %d 家" % x for x in diag.get("miss", [])[:5]))
    _log("东方财富：%s %d 家公司，归到 %d 个行业" % (period_name(annual), len(a_rows), len(a_agg)))


# ───────────────────────── 更新 ─────────────────────────
SRC_SHORT = {"retail": "统计局·社会消费品零售", "ind": "统计局·工业企业利润", "income": "统计局·居民收入和消费支出", "listed": "东方财富·上市公司业绩",
             "concept": "东方财富·概念板块（新兴赛道）"}


def _do_update(force):
    data = _data()
    t0 = time.time()
    before = {k: dict((data.get("st") or {}).get(k) or {}) for k in SRC_SHORT}
    errs = {}
    for name, fn in (("统计局", lambda: update_nbs(data, force)), ("东方财富", lambda: update_listed(data))):
        _upd["stage"] = "正在读%s…" % name
        try:
            fn()
        except Exception as e:
            errs[name] = str(e)[:100]
            _log("%s没更新成：%s" % (name, str(e)[:100]))
        data["updated"] = int(time.time())
        _write(DATA_FILE, data)
    # v193：更新完写一份汇报——每个信息源取到哪一期、和上次比有没有新的
    lines, n_ok = [], 0
    for k, nm in SRC_SHORT.items():
        a, b = (data.get("st") or {}).get(k) or {}, before.get(k) or {}
        if a.get("ok"):
            n_ok += 1
            new = a.get("period") != b.get("period") or a.get("n") != b.get("n") or not b.get("ok")
            unit = " 家公司" if k == "listed" else " 个新兴赛道对上了" if k == "concept" else " 项"
            s = "%s：%s，%s%s" % (nm, a.get("period", ""), a.get("n", ""), unit)
            if k == "listed" and a.get("n_ind"):
                s += "，归到 %d 个二级行业（认出行业的 %s 家）" % (a["n_ind"], a.get("mapped", "?"))
            s += "——有新数据" if new else "——和上次一样（还没出新的一期）"
            lines.append({"ok": True, "new": new, "txt": s, "warn": a.get("warn", "")})
        else:
            lines.append({"ok": False, "txt": "%s：没取到（%s）" % (nm, a.get("err") or errs.get("东方财富" if k == "listed" else "统计局") or "原因不明")})
    data["last_report"] = {"at": int(time.time()), "secs": int(time.time() - t0), "lines": lines, "n_ok": n_ok, "n": len(SRC_SHORT)}
    _write(DATA_FILE, data)


def start_update(force=False):
    with _lock:
        if _upd["running"]:
            return {"ok": True, "running": True}
        _upd.update(running=True, started=int(time.time()), stage="准备中…")

    def run():
        try:
            _do_update(force)
        finally:
            _upd.update(running=False, stage="")
    threading.Thread(target=run, daemon=True, name="biz-real-update").start()
    return {"ok": True, "running": True}


def maybe_update():
    d = _data()
    if not _upd["running"] and (time.time() - d.get("updated", 0) > STALE_S or (d.get("listed") and d["listed"].get("v") != 4)):
        start_update()


# ───────────────────────── 给界面：每个格子的数 ─────────────────────────
def _tx():
    return BZ._tx()


def _nbs_links(data):
    """格子编号 → 和它有关的统计局数字。"""
    out = {}

    def add(gid, item):
        out.setdefault(gid, []).append(item)
    r = data.get("retail") or {}
    for k, ids in RETAIL_MAP.items():
        v = (r.get("rows") or {}).get(k)
        if v and v.get("ytd") is not None:
            for g in ids:
                add(g, {"src": "retail", "name": k, "v": v["ytd"], "yoy": v["ytd_yoy"], "unit": "亿元", "period": r.get("period", ""),
                        "txt": "限额以上单位「%s」零售额" % k if k not in ("社会消费品零售总额", "网上商品零售额", "餐饮收入") else k})
    i = data.get("ind") or {}
    for k, ids in IND_MAP.items():
        v = (i.get("rows") or {}).get(k)
        if v and v.get("rev") is not None:
            for g in ids:
                add(g, {"src": "ind", "name": k, "v": v["rev"], "yoy": v["rev_yoy"], "profit": v["profit"],
                        "profit_yoy": v["profit_yoy"], "margin": v["margin"], "unit": "亿元", "period": i.get("period", ""),
                        "txt": "规模以上「%s」营业收入" % k})
    inc = data.get("income") or {}
    for k, ids in SPEND_MAP.items():
        v = (inc.get("cats") or {}).get(k)
        if v:
            for g in ids:
                add(g, {"src": "income", "name": k, "v": v["v"], "yoy": v["yoy"], "share": v["share"], "unit": "元/人",
                        "period": inc.get("period", ""), "txt": "全国居民人均「%s」支出" % k})
    return out


def _checks():
    c = _read(CHECKS_FILE, [])
    return c if isinstance(c, list) else []


def _check_brief(c):
    return {"id": c["id"], "target": c["target"], "gid": c.get("gid", ""), "name": c.get("name") or c["target"],
            "created": c.get("created", 0), "report": c.get("report", ""), "summary": c.get("summary", ""),
            "n": len(c.get("facts") or []), "ok": sum(1 for f in c.get("facts") or [] if f.get("ok")),
            "dims": sorted({f["dim"] for f in c.get("facts") or []}, key=DIMS.index),
            "size": next((f["value"] for f in c.get("facts") or [] if f["dim"] == "规模"), "")}


def overview():
    maybe_update()
    d = _data()
    L = d.get("listed") or {}
    by = {}
    for g, a in (L.get("a") or {}).items():
        q = (L.get("q") or {}).get(g) or {}
        by[g] = {"n": a["n"], "rev": a["rev"], "np": a["np"], "rev_yoy": a["rev_yoy"], "nm": a["nm"], "gm": a["gm"],
                 "q_rev": q.get("rev"), "q_yoy": q.get("rev_yoy"), "q_np_yoy": q.get("np_yoy")}
    links = _nbs_links(d)
    for g, items in links.items():
        by.setdefault(g, {})["nbs"] = len(items)
        sz = max((x["v"] for x in items if x["src"] in ("retail", "ind")), default=None)
        if sz is not None:
            by[g]["nbs_v"] = sz
    chk = {}
    for c in _checks():
        if c.get("gid") and c["gid"] not in chk:
            chk[c["gid"]] = c["id"]
    for g, cid in chk.items():
        by.setdefault(g, {})["chk"] = cid
    st = d.get("st") or {}
    srcs = []
    for s in SOURCES:
        x = dict(s)
        x.update(st.get(s["key"]) or {})
        x["auto"] = s["key"] in ("retail", "ind", "income", "listed", "concept")
        srcs.append(x)
    try:
        import biz_trade as BT
        cov = BT.coverage()
        for p in BT.status():
            c = cov.get(p["key"]) or {}
            srcs.append({"fit": c.get("fit", 0), "done": c.get("done", 0), "key": "tp_" + p["key"], "name": p["name"], "what": p["what"], "url": p["url"], "auto": False, "crawl": True,
                         "how": "爬虫抓（直连 → Scrapling 快速 → 真浏览器，管用的记住）；核实时自动抓，也可以在体检卡里点「去平台抓」，或点上面「交易平台全部抓一遍」",
                         "n_ok": p.get("n_ok", 0), "n_bad": p.get("n_bad", 0), "last_ok": p.get("last_ok", 0), "at": p.get("at", 0),
                         "via": p.get("via", ""), "err": p.get("err", "")})
        srcs = [x for x in srcs if x["key"] not in ("ecom", "trade", "bid")]
        srcs.sort(key=lambda x: x["key"] == "report")
    except Exception:
        pass
    r, inc, i = d.get("retail") or {}, d.get("income") or {}, d.get("ind") or {}
    rr, ir = r.get("rows") or {}, i.get("rows") or {}
    kpi = []
    if rr.get("社会消费品零售总额"):
        kpi.append({"k": "社会消费品零售总额", "v": rr["社会消费品零售总额"]["ytd"], "unit": "亿元", "yoy": rr["社会消费品零售总额"]["ytd_yoy"], "period": r.get("period", "")})
    if rr.get("网上商品零售额"):
        kpi.append({"k": "网上商品零售额", "v": rr["网上商品零售额"]["ytd"], "unit": "亿元", "yoy": rr["网上商品零售额"]["ytd_yoy"], "period": r.get("period", "")})
    if inc.get("spend"):
        kpi.append({"k": "人均消费支出", "v": inc["spend"], "unit": "元", "yoy": inc.get("spend_yoy"), "period": inc.get("period", "")})
    if inc.get("income"):
        kpi.append({"k": "人均可支配收入", "v": inc["income"], "unit": "元", "yoy": inc.get("income_yoy"), "period": inc.get("period", "")})
    if ir.get("总计"):
        kpi.append({"k": "规上工业营业收入", "v": ir["总计"]["rev"], "unit": "亿元", "yoy": ir["总计"]["rev_yoy"], "period": i.get("period", ""),
                    "extra": "利润率 %s%%" % ir["总计"]["margin"] if ir["总计"].get("margin") is not None else ""})
    return {"ok": True, "updated": d.get("updated", 0), "updating": dict(_upd), "report": d.get("last_report"), "sources": srcs, "kpi": kpi, "by": by,
            "listed": {k: L.get(k) for k in ("annual", "latest", "annual_name", "latest_name", "companies")},
            "checks": [_check_brief(c) for c in _checks()[:300]], "batch": batch_status(), "tbatch": _tbatch(), "now": int(time.time())}


def item(gid):
    d = _data()
    L = d.get("listed") or {}
    a, q = (L.get("a") or {}).get(gid), (L.get("q") or {}).get(gid)
    links = _nbs_links(d)
    nbs = list(links.get(gid, []))
    if "/" in gid:                                      # 二级行业哪一类没直接对上，就带上它所在一级行业的（标明是一级行业的）
        have = {x["src"] for x in nbs}
        nbs += [dict(x, up=True) for x in links.get(gid.split("/")[0], []) if x["src"] not in have]
    inc = d.get("income") or {}
    chk = next((c for c in _checks() if c.get("gid") == gid), None)
    try:
        import biz_trade as BT
        trec = BT.get(gid)
        trade = {"at": trec["at"], "kw": trec["kw"], "lines": BT.lines(trec),
                 "ccgp": (trec["res"].get("ccgp") or {}).get("items", [])[:5]} if trec else None
        trade_run = BT.running(gid)
        trade_plan = BT.plan(gid)
    except Exception:
        trade, trade_run, trade_plan = None, False, ("", [])
    return {"ok": True, "id": gid, "trade": trade, "trade_running": trade_run,
            "trade_plan": {"kw": trade_plan[0], "plats": trade_plan[1]}, "listed": a, "listed_q": q, "annual_name": L.get("annual_name", ""), "latest_name": L.get("latest_name", ""),
            "nbs": nbs, "income": {k: inc.get(k) for k in ("period", "income", "income_yoy", "median", "spend", "spend_yoy", "urban", "rural")},
            "check": chk}


def check_get(cid):
    c = next((x for x in _checks() if x["id"] == cid), None)
    return {"ok": bool(c), "check": c, "error": "" if c else "找不到这条核实记录"}


def check_delete(cid):
    with _lock:
        cs = _checks()
        n = len(cs)
        cs = [c for c in cs if c["id"] != cid]
        _write(CHECKS_FILE, cs)
    return {"ok": n != len(cs)}


# ───────────────────────── AI 核实：要查什么、给 AI 什么 ─────────────────────────
def resolve(target):
    """格子编号或随便写的方向 → (显示的名字, 对上的格子编号, 相关的二级行业 [最多 3 个])。"""
    t = (target or "").strip()
    tx = _tx()
    for kind in ("l2", "l1", "trk", "l3"):
        if t in tx.get(kind, {}):
            d = tx[kind][t]
            if kind == "l3":
                return d["name"], t, [d["l2"]]
            if kind == "trk":
                return d["name"], t, [r for r in d.get("rel") or [] if r in tx["l2"]][:3] or [t]
            if kind == "l1":
                return d.get("name", t), t, [t]
            return d["name"], t, [t]
    try:
        sc_i, sc_t, _w = BZ._score(t)
        rel = BZ._pick(sc_i, 3, 2)
    except Exception:
        rel = []
    return t, "", rel


def _fmt_yi(v):
    if v is None:
        return "?"
    return ("%.2f 万亿" % (v / 10000)) if abs(v) >= 10000 else ("%s 亿" % (("%.0f" if abs(v) >= 100 else "%.1f") % v))


def _pct(v):
    return "?" if v is None else ("%+.1f%%" % v)


def local_text(gids, radar=True):
    d = _data()
    L = d.get("listed") or {}
    out = []
    links = _nbs_links(d)
    seen = set()
    for g in gids:
        a, q = (L.get("a") or {}).get(g), (L.get("q") or {}).get(g)
        nm = BZ._resolve(g)[0] if g else g
        if a:
            s = "[上市公司] 申万「%s」A 股 %d 家：%s营收合计 %s元（同比 %s），归母净利润 %s元（净利率 %s%%%s）" % (
                nm, a["n"], L.get("annual_name", ""), _fmt_yi(a["rev"]), _pct(a["rev_yoy"]), _fmt_yi(a["np"]), a["nm"],
                "，毛利率中位数 %s%%" % a["gm"] if a.get("gm") is not None else "")
            if q:
                s += "；%s营收 %s元（同比 %s），净利润同比 %s" % (L.get("latest_name", ""), _fmt_yi(q["rev"]), _pct(q["rev_yoy"]), _pct(q["np_yoy"]))
            s += "。营收最多的：" + "、".join("%s %s元" % (t[0], _fmt_yi(t[1])) for t in a["top"][:5])
            out.append(s)
        for x in links.get(g, []) + (links.get(g.split("/")[0], []) if "/" in g else []):
            key = (x["src"], x["name"])
            if key in seen:
                continue
            seen.add(key)
            if x["src"] == "ind":
                out.append("[统计局] %s %s %s元（同比 %s），利润总额 %s元（同比 %s），营收利润率 %s%%" % (
                    x["period"], x["txt"], _fmt_yi(x["v"]), _pct(x["yoy"]), _fmt_yi(x["profit"]), _pct(x["profit_yoy"]), x["margin"]))
            elif x["src"] == "retail":
                out.append("[统计局] %s %s %s元（同比 %s）" % (x["period"], x["txt"], _fmt_yi(x["v"]), _pct(x["yoy"])))
            else:
                out.append("[统计局] %s %s %.0f 元（同比 %s，占人均消费支出 %s%%）" % (x["period"], x["txt"], x["v"], _pct(x["yoy"]), x["share"]))
    inc = d.get("income") or {}
    if inc.get("income"):
        out.append("[统计局] %s 全国居民人均可支配收入 %.0f 元（同比 %s，中位数 %s 元），人均消费支出 %s 元（同比 %s）" % (
            inc.get("period", ""), inc["income"], _pct(inc.get("income_yoy")), "%.0f" % inc["median"] if inc.get("median") else "?",
            "%.0f" % inc["spend"] if inc.get("spend") else "?", _pct(inc.get("spend_yoy"))))
    if radar and gids:
        try:
            ov = BZ.overview(7, "market")
            for g in gids[:3]:
                h = (ov.get("l1") or {}).get(g) if "/" not in g and not g.startswith("t:") else (ov.get("heat") or {}).get(g)
                h = h or [0, 0]
                out.append("[市场雷达] 「%s」最近 7 天相关新闻 %d 条，最近 24 小时 %d 条（只说明大家在不在说，不代表钱多钱少）" % (
                    BZ._resolve(g)[0], h[0], h[1]))
        except Exception:
            pass
    return "\n".join(out)


def web_queries(name, deep):
    y = datetime.date.today().year
    qs = ["%s 市场规模 亿元 %d" % (name, y), "%s 用户规模 客户数量 %d" % (name, y),
          "%s 客单价 价格 销量 天猫 京东 %d" % (name, y), "%s 毛利率 净利率 利润 %d" % (name, y)]
    if deep:
        qs += ["%s 抖音电商 GMV 销售额 %d" % (name, y), "%s 行业报告 白皮书 %d" % (name, y - 1),
               "%s 招标 采购 中标金额" % name, "%s 报价 多少钱 接单 平台" % name]
    return qs


_HEAD = ("今天是 {today}。你是一位做市场调研的分析师，专门核实「一个方向的真实市场有多大」，写给一位想做小生意的普通人看，说人话。\n"
         "任务：核实「{name}」的真实市场：① 规模（一年成交多少钱）② 客户（有多少人 / 多少企业在买）"
         "③ 购买力（每个客户一年或一次肯花多少、价格带）④ 利润（做这一行赚不赚钱：毛利率、净利率）；"
         "再补充 ⑤ 交易（电商平台、交易 / 接单平台、招投标里能看到的成交额、销量、报价、采购金额）。\n"
         "资料③是爬虫在交易平台上直接抓的真实成交、报价和采购公告，是最贴近「钱」的证据，优先用它说交易和购买力，但它只是搜索结果首页的样本，要说明。\n"
         "规矩：只用下面资料里出现过的数字，或你联网查到、能给出网址的数字；每个数字写清楚口径、时间和出处；"
         "查不到就写「待核实」，绝对不要编。行业报告和媒体的数字常互相抄、口径不一，要指出来。"
         "资料①里上市公司的数字只是头部公司的盘子，不等于整个市场；统计局的数字是一整个统计大类的合计。"
         "市场雷达的新闻条数只说明大家在不在说，不代表钱多钱少。\n"
         "格式：全文 Markdown；第一行写「# {title}」；下面只用这些二级标题，按顺序写，不要开场白：\n"
         "## 一句话结论（两三句：多大、谁在买、肯花多少、赚不赚钱）\n"
         "## 四把尺子\n"
         "这一节只写下面格式的行，每行一个数字，至少 6 行；规模、客户、购买力、利润每种至少 1 行（实在查不到的写一行，数值写「待核实」）：\n"
         "- 尺子｜指标｜数值｜时间｜口径｜出处｜网址\n"
         "例：- 规模｜中国宠物食品市场规模｜1585亿元｜2024年｜行业报告｜某某《中国宠物行业白皮书》｜https://…\n"
         "尺子只能写：规模、客户、购买力、利润、交易；口径只能写：" + "、".join(BASES) + "；数值写数字和单位；没有网址写「无」。\n"
         "## 热度和真钱对比（市场雷达的热度和上面的数字对不对得上：是「钱多话少」还是「话多钱少」）\n"
         "## 对小生意意味着什么（钱集中在哪一环、普通人能分到哪一块、客单价大概多少、要多少个客户才能一个月赚 1 万）\n"
         "## 还缺什么数据（哪些待核实，自己可以去哪里查：比如 1688 / 淘宝看同类价格和销量、猪八戒看报价、政府采购网搜招标）\n"
         "## 信息来源\n\n")


def prompt(spec, local, web_txt):
    return (_HEAD.format(today=datetime.date.today().isoformat(), name=spec["rname"], title=spec["title"]) +
            "=== 资料①：超能小助自动取到的硬数据（统计局、上市公司、市场雷达）===\n%s\n\n" % (local or "（这个方向没有直接对上的统计和上市公司数据）") +
            ("相关的行业（比这个方向宽得多，它们的数字只能当背景，不能当成这个方向的规模）：%s\n\n" % "、".join(BZ._resolve(g)[0] for g in spec.get("rel") or []) if spec.get("rel") else "") +
            "=== 资料③：爬虫刚在交易平台上直接抓到的（政府采购网的公告条数和金额、1688 / 京东 / 什么值得买的价格带和销量、猪八戒的服务报价）===\n%s\n\n"
            % (spec.get("trade_txt") or "（这次没抓到）") +
            "=== 资料②：小助刚从网上搜到的网页摘录 ===\n%s\n\n请开始写，第一行是「# %s」。" % ((web_txt or "").strip() or "（这次没有联网或没搜到）", spec["title"]))


_FACT_RX = re.compile(r"^\s*[-*•·]\s*\**\s*(规模|客户|购买力|利润|交易)\s*\**\s*[｜|](.+)$")


def parse_facts(md):
    facts = []
    for ln in (md or "").splitlines():
        m = _FACT_RX.match(ln)
        if not m:
            continue
        parts = [p.strip().strip("*").strip() for p in re.split(r"[｜|]", m.group(2))]
        parts += [""] * (6 - len(parts))
        metric, value, when, basis, src, url = parts[:6]
        um = re.search(r"https?://[^\s)）>\]]+", url or "") or re.search(r"https?://[^\s)）>\]]+", ln)
        basis = next((b for b in BASES if b in basis), basis[:8] or "")
        if not metric and not value:
            continue
        facts.append({"dim": m.group(1), "metric": metric[:60], "value": value[:40], "when": when[:20], "basis": basis,
                      "src": src[:80], "url": um.group(0) if um else ""})
    return facts[:30]


def _digits(s):
    return re.sub(r"(?<=\d)[,，](?=\d{3})", "", s or "")


def verify(facts, material):
    """数字回原文里对一遍：数值里最像样的那个数，在给 AI 的资料里出现过就算「原文有」。"""
    mat = _digits(material)
    for f in facts:
        v = _digits(f["value"])
        if "待核实" in v or not re.search(r"\d", v):
            f["ok"], f["chk"] = False, "待核实"
            continue
        nums = [n for n in re.findall(r"\d+(?:\.\d+)?", v) if not (len(n) == 4 and n.startswith(("19", "20")))]
        nums = sorted(nums, key=lambda n: (-len(n.replace(".", "")), n))
        ok = False
        for n in nums[:2]:
            if len(n.replace(".", "").lstrip("0")) < 2 and "." not in n:
                continue
            if re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", mat):
                ok = True
                break
        f["ok"], f["chk"] = ok, "原文有" if ok else "没对上"
    return facts


def _summary(md):
    m = re.search(r"##\s*一句话结论[^\n]*\n+(.+?)(?:\n##|\Z)", md or "", flags=re.S)
    s = re.sub(r"\s+", " ", re.sub(r"[#*>`]", "", m.group(1))).strip() if m else ""
    return s[:220]


def spec_extra(target):
    name, gid, rel = resolve(target)
    return {"rname": name, "gid": gid, "rel": rel, "title": "真实市场核实：%s" % name, "scope_name": name}


def run_check(spec):
    deep = spec["depth"] == "deep"
    BZ._stage(1, "读软件里的数据：统计局、上市公司、市场雷达…")
    gids = ([spec["gid"]] if spec.get("gid") else []) + [g for g in spec.get("rel") or [] if g != spec.get("gid")]
    local = local_text(gids[:3])
    BZ._stage(1, "资料：%d 条硬数据" % (local.count("\n") + 1 if local else 0))
    if BZ._stopping():
        raise BZ._Stop()
    trade_txt = ""
    try:                                                # v192：先去交易平台抓（政府采购网、1688、京东、什么值得买、猪八戒）
        import biz_trade as BT
        key = spec.get("gid") or spec["rname"]
        rec = BT.get(key)
        if not rec or time.time() - rec.get("at", 0) > 3 * 86400:
            kw, plats = BT.plan(key)
            BZ._stage(2, "上交易平台抓「%s」：%s…" % (kw, "、".join(BT.P_NAME[p] for p in plats)))
            rec = (BT.probe(key) or {}).get("rec") or BT.get(key)
        if rec:
            trade_txt = BT.prompt_text(rec)
            n_ok = sum(1 for r in rec["res"].values() if r.get("ok"))
            BZ._stage(2, "交易平台抓到 %d / %d 个" % (n_ok, len(rec["res"])))
    except Exception as e:
        BZ._stage(2, "交易平台没抓成（%s），接着查网上资料" % str(e)[:50])
    if BZ._stopping():
        raise BZ._Stop()
    spec["trade_txt"] = trade_txt
    web_txt, web_src = "", []
    if spec["web"]:
        web_txt, web_src = BZ._web(spec, deep, qs=web_queries(spec["rname"], deep))
    else:
        BZ._stage(2, "没勾联网，只用软件里的数据")
    if BZ._stopping():
        raise BZ._Stop()
    BZ._stage(3, "交给 AI 整理成体检卡…")
    text, engine = BZ._ask(prompt(spec, local, web_txt), spec)
    BZ._stage(4, "核对数字、存结果…")
    facts = verify(parse_facts(text), local + "\n" + trade_txt + "\n" + (web_txt or ""))
    rid, _n = BZ._save(spec, text, [], [], web_src, engine)
    now = int(time.time())
    key = spec.get("gid") or spec["rname"]
    rec = {"id": "rc" + hashlib.md5((key + str(now)).encode("utf-8")).hexdigest()[:10], "target": key, "gid": spec.get("gid", ""),
           "name": spec["rname"], "created": now, "report": rid, "engine": engine, "depth": spec["depth"],
           "facts": facts, "summary": _summary(text), "web": len(web_src)}
    with _lock:
        cs = [c for c in _checks() if c.get("target") != key]
        cs.insert(0, rec)
        _write(CHECKS_FILE, cs[:200])
    ok = sum(1 for f in facts if f.get("ok"))
    BZ._set(running=False, ok=True, ended=now, report=rid, opps=0, stage="写好了：%d 个数字，%d 个在原文里对上了" % (len(facts), ok))
    BZ._log("真实市场核实写好了：%s（%s，%d 个数字）" % (spec["rname"], engine, len(facts)))


# ───────────────────────── 给商业定制用 ─────────────────────────
def context_for(ids, budget=3500):
    """商业定制写方案时：候选方向的真实市场数据（硬数据 + 核实过的数字）。"""
    out = []
    try:
        t = local_text([i for i in ids if i][:6], radar=False)
        if t:
            out.append(t)
    except Exception:
        pass
    cs = {c.get("gid"): c for c in _checks() if c.get("gid")}
    for g in ids:
        c = cs.get(g)
        if c:
            out.append("[AI 核实·%s] " % c["name"] + "；".join("%s %s %s（%s，%s%s）" % (
                f["dim"], f["metric"], f["value"], f["when"], f["basis"], "，原文有" if f.get("ok") else "，没对上原文")
                for f in c["facts"][:8]))
    s = "\n".join(out)
    return s[:budget]


# ───────────────────────── v192：全部核实（排队一个个来）─────────────────────────
BATCH_FILE = REAL_DIR / "batch.json"
_bt = {"thread": None}
FRESH_DAYS = 30


def batch_ids(scope, todo):
    tx = _tx()
    l2, trk = list(tx["l2"]), list(tx["trk"])
    if scope.startswith("sec:") and scope in tx["sec"]:
        ids = [g for g in l2 if tx["l2"][g]["l1"] in tx["sec"][scope]["l1"]]
        name = tx["sec"][scope]["name"] + "板块"
    elif scope.startswith("l1:") and scope[3:] in tx["l1"]:
        ids, name = list(tx["l1"][scope[3:]]["subs"]), scope[3:]
    elif scope == "trk":
        ids, name = trk, "新兴赛道"
    elif scope == "l2":
        ids, name = l2, "全部二级行业"
    else:
        ids, name = trk + l2, "全部（新兴赛道 + 二级行业）"
    if todo:
        cut = time.time() - FRESH_DAYS * 86400
        done = {c.get("gid") for c in _checks() if c.get("created", 0) >= cut}
        ids = [g for g in ids if g not in done]
        name += "里还没核实过的"
    return ids, name


def _tbatch():
    try:
        import biz_trade as BT
        return BT.batch_status()
    except Exception:
        return None


def batch_status():
    b = _read(BATCH_FILE, {})
    if not isinstance(b, dict) or not b.get("ids"):
        return None
    alive = bool(_bt["thread"] and _bt["thread"].is_alive())
    n = len(b["ids"])
    left = n - b.get("i", 0)
    avg = (b.get("spent", 0) / max(1, b.get("ok", 0) + b.get("bad", 0))) if (b.get("ok", 0) + b.get("bad", 0)) else (240 if b.get("depth") != "deep" else 420)
    cur = b["ids"][b["i"]] if b.get("i", 0) < n else ""
    return {"name": b.get("name", ""), "n": n, "i": b.get("i", 0), "ok": b.get("ok", 0), "bad": b.get("bad", 0), "depth": b.get("depth", "quick"),
            "cur": cur, "cur_name": BZ._resolve(cur)[0] if cur else "", "running": alive and left > 0 and not b.get("stop"),
            "stopping": alive and bool(b.get("stop")), "paused": (not alive) and left > 0, "done": left <= 0, "started": b.get("started", 0),
            "eta": int(avg * left), "errs": (b.get("errs") or [])[-5:], "waiting": b.get("waiting", "")}


def batch_start(scope="all", depth="quick", todo=True):
    with _lock:
        if _bt["thread"] and _bt["thread"].is_alive():
            return {"ok": False, "error": "已经在一个个核实了，先等它做完或者点停止"}
        ids, name = batch_ids(scope or "all", bool(todo))
        if not ids:
            return {"ok": False, "error": "这个范围里都核实过了（%d 天内），不用再跑。要重新核实，把「跳过核实过的」取消勾选。" % FRESH_DAYS}
        _write(BATCH_FILE, {"ids": ids, "i": 0, "depth": "deep" if depth == "deep" else "quick", "name": name, "scope": scope,
                            "started": int(time.time()), "ok": 0, "bad": 0, "spent": 0, "errs": [], "stop": False})
    return batch_resume()


def batch_resume():
    with _lock:
        if _bt["thread"] and _bt["thread"].is_alive():
            return {"ok": True, "running": True}
        b = _read(BATCH_FILE, {})
        if not b.get("ids") or b.get("i", 0) >= len(b["ids"]):
            return {"ok": False, "error": "没有要接着做的"}
        b["stop"] = False
        _write(BATCH_FILE, b)
        _bt["thread"] = threading.Thread(target=_batch_loop, daemon=True, name="biz-real-batch")
        _bt["thread"].start()
    _log("开始一个个核实：%s，共 %d 个，从第 %d 个开始" % (b.get("name", ""), len(b["ids"]), b.get("i", 0) + 1))
    return {"ok": True, "running": True}


def batch_stop():
    with _lock:
        b = _read(BATCH_FILE, {})
        if not b:
            return {"ok": True}
        b["stop"] = True
        _write(BATCH_FILE, b)
    j = BZ.job_status()
    if j.get("running") and j.get("kind") == "real" and b.get("cur_job") == j.get("id"):
        BZ.stop()
    return {"ok": True}


def batch_clear():
    batch_stop()
    with _lock:
        _write(BATCH_FILE, {})
    return {"ok": True}


def _bset(**kw):
    with _lock:
        b = _read(BATCH_FILE, {})
        b.update(kw)
        _write(BATCH_FILE, b)
        return b


def _batch_loop():
    while True:
        b = _read(BATCH_FILE, {})
        if not b.get("ids") or b.get("stop") or b.get("i", 0) >= len(b["ids"]):
            if b.get("ids") and b.get("i", 0) >= len(b["ids"]):
                _log("一个个核实做完了：%s，成功 %d 个，没做成 %d 个" % (b.get("name", ""), b.get("ok", 0), b.get("bad", 0)))
            _bset(waiting="")
            return
        gid = b["ids"][b["i"]]
        if BZ.job_status().get("running"):                 # 别的报告在写：等它写完
            _bset(waiting="等「%s」写完…" % BZ.job_status().get("title", ""))
            time.sleep(5)
            continue
        t0 = time.time()
        r = BZ.start("real", scope=gid, web=True, depth=b.get("depth", "quick"))
        if not r.get("ok"):
            if "还在做" in str(r.get("error", "")):
                time.sleep(5)
                continue
            b = _bset(i=b["i"] + 1, bad=b.get("bad", 0) + 1, errs=(b.get("errs") or [])[-20:] + [[gid, r.get("error", "")[:100]]])
            continue
        _bset(cur_job=r.get("job_id"), waiting="")
        while True:
            time.sleep(3)
            j = BZ.job_status()
            if not j.get("running") or j.get("id") != r.get("job_id"):
                break
        j = BZ.job_status()
        ok = bool(j.get("ok"))
        b = _read(BATCH_FILE, {})
        if b.get("stop") and not ok:                        # 是你点了停止：这一个不算，下次从它接着做
            return
        upd = {"i": b["i"] + 1, "spent": b.get("spent", 0) + int(time.time() - t0)}
        if ok:
            upd["ok"] = b.get("ok", 0) + 1
        else:
            upd["bad"] = b.get("bad", 0) + 1
            upd["errs"] = (b.get("errs") or [])[-20:] + [[gid, str(j.get("error", ""))[:100]]]
        _bset(**upd)
        time.sleep(4)                                       # 让 AI 池喘口气
