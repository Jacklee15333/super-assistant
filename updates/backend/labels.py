"""超能小助 · 贴标签（v132 新增）

「加工 → 已加工」里给文章分类、给作者判断领域，方便以后分类、筛选。

  · 一套固定分类，作者和文章共用（DEFAULT_CATS）。你手动写的新分类会加进来，以后 AI 也会用。
  · 文章：按标题、标签和「一句话概括」，一批十几篇一起问 AI：分一个类，再配 2 个关键词。
  · 作者：读作者主页（简介 + 最近的作品标题），加上库里这位作者的笔记标题，判断主要领域，记一句理由。
    还没绑主页的，先根据笔记里的视频链接自动找主页；主页读不到就只用库里的笔记判断，并注明。
  · 结果存在 memory/video_notes/_labels.json（文章）和 memory/author_labels.json（作者），不改笔记文件。
  · 你手动改过的（by=you），AI 以后不会覆盖。
  · 用哪个 AI 由 server.py 传进来（configure）：本机有本地模型就用本地的（快、不占 AI 池），
    没有再排队用 AI 池。新加工好的文章只在有本地模型时自动贴，免得和批量加工抢 AI 池。
"""
from __future__ import annotations

import collections
import json
import os
import re
import threading
import time

OTHER = "其它"
# v134：两级分类——先分大类，再在大类里分子类（文章放进具体的子类）。
# 参考：IAB 内容分类标准（一级 + 二级）、B 站知识区分区、得到的课程门类，再按你库里的内容调整。
# 每项：(名字, 说明)；说明会写进给 AI 的提示里，帮它分清边界。
TAXONOMY = [
    ("AI", "人工智能相关的一切（哪怕是 AI 公司的商业新闻）", [
        ("模型动态", "新模型发布、能力评测和对比"), ("AI工具", "AI 产品和工具怎么用、测评、工作流、智能体"),
        ("AI编程", "用 AI 写代码、Agent / RAG 开发"), ("行业公司", "AI 公司动态、融资上市、算力、竞争"),
        ("AI搞钱", "用 AI 创业、做副业、变现"), ("安全监管", "AI 安全、伦理、监管、对就业和社会的影响"),
        ("前沿研究", "论文、科研进展、具身智能研究")]),
    ("商业", "创业、生意和公司经营", [
        ("创业", "创业方法、一人公司、需求验证、创业经历"), ("搞钱副业", "赚钱方法、副业、知识变现、信息差"),
        ("商业模式", "商业逻辑、商业模式、案例拆解"), ("营销品牌", "营销、品牌、获客、定价"),
        ("经营管理", "企业管理、组织、战略、运营"), ("行业观察", "某个行业或公司的分析（制造业、餐饮、消费品…）"),
        ("电商带货", "电商、直播带货、供应链")]),
    ("成长", "个人成长", [
        ("认知思维", "认知提升、思维模型、独立思考、逻辑"), ("学习方法", "学习方法、读书、知识管理、自学"),
        ("效率习惯", "时间管理、自律、行动力、习惯养成"), ("人生选择", "人生方向、长期主义、重大决定"),
        ("沟通表达", "说话、说服、表达、人情世故")]),
    ("财经", "经济、金融和钱", [
        ("宏观经济", "经济形势、经济政策、国际经济"), ("投资交易", "股票、基金、交易心理、资产配置"),
        ("金融常识", "银行、信用卡、保险、货币、金融规则"), ("财富认知", "财富思维、财务自由、现金流、家庭理财"),
        ("房产", "买房、房价、楼市")]),
    ("职场", "工作和职业", [
        ("求职", "找工作、面试、简历、校招"), ("工作方法", "做事方法、汇报、开会"),
        ("带团队", "管理者成长、新经理、团队管理"), ("职业发展", "升职加薪、职业规划、转行"),
        ("职场关系", "和领导同事相处、职场冲突")]),
    ("内容创作", "讲怎么做内容、做账号的（作者是自媒体博主不算，按文章讲的事分）", [
        ("短视频", "选题、脚本、拍摄、剪辑"), ("账号运营", "涨粉、流量、平台规则和算法"),
        ("写作文案", "写作、文案、表达技巧"), ("个人IP", "个人品牌、人设"),
        ("内容变现", "广告、带货、知识付费"), ("直播", "直播技巧、直播运营")]),
    ("科技", "AI 以外的科技", [
        ("汽车出行", "电动车、自动驾驶、飞行汽车"), ("航天", "火箭、卫星、太空探索"),
        ("手机数码", "手机、电脑、消费电子"), ("芯片硬件", "芯片、半导体、硬件"),
        ("机器人", "人形机器人、工业机器人"), ("互联网", "互联网产品、平台、软件"),
        ("科学科普", "物理、天文、生物等科学知识")]),
    # v137：子类都按「讲的是什么事」分，不按讲法分——「热点评法」「热点事件」「舆论观察」这种什么都能装的去掉了
    ("社会", "时事和社会话题", [
        ("政策民生", "政策解读、就业、养老、医疗、住房、补贴发钱"), ("国际局势", "国际关系、大国博弈、外国的社会和制度"),
        ("爱国与认同", "爱国话题、国家认同、民族情绪"), ("网红舆论", "网红、主播、明星的争议和塌房，网络舆论"),
        ("媒体与信息", "新闻报道、信息真假、谣言、数字话术"), ("社会现象", "代际、阶层、消费主义、内卷等社会现象"),
        ("公共安全", "事故、治安、公共事件"), ("性别议题", "性别、婚恋观念等社会讨论"), ("反诈防骗", "诈骗、骗局、防骗")]),
    ("法律", "核心在讲法律本身：法律知识、案件定性、怎么维权", [
        ("普法常识", "法律知识、法条解读"), ("刑事案件", "犯罪、刑事责任、寻衅滋事等"),
        ("民事纠纷", "合同、借贷、婚姻家庭、继承"), ("劳动权益", "劳动法、工资、加班、调休"),
        ("消费维权", "消费者权益、产品质量、平台纠纷"), ("知识产权", "版权、商标、专利"),
        ("网络与隐私", "网络言论、个人信息、平台规则")]),
    ("人文", "历史、思想和文化", [
        ("历史", "中国史、世界史、历史人物、文明比较"), ("哲学思想", "哲学、思想家、宗教"),
        ("国学经典", "国学、传统文化、经典名著"), ("文化艺术", "文学、艺术、文化现象")]),
    ("心理", "心理和情感", [
        ("情绪压力", "焦虑、情绪管理、抗压"), ("自我认知", "自尊、自信、心理成长"),
        ("人际关系", "社交、相处、家庭关系"), ("婚恋亲密", "恋爱、婚姻、亲密关系"),
        ("心理学知识", "心理学原理、效应、实验")]),
    ("教育", "学校和学科学习", [
        ("英语", "英语学习：语法、口语、词汇"), ("孩子教育", "家庭教育、亲子、学校教育"),
        ("考试升学", "高考、考研、留学、考证"), ("学科知识", "数理化等学科讲解")]),
    ("健康", "身体健康", [
        ("医学常识", "疾病、用药、就医"), ("饮食营养", "吃什么、营养、肠道"),
        ("运动健身", "锻炼、减肥、体态"), ("作息成瘾", "睡眠、作息、戒瘾、多巴胺")]),
    ("生活", "日常生活和娱乐", [
        ("消费购物", "买东西、测评、消费观"), ("影视娱乐", "电影、电视剧、综艺的剧情、人物、演技"),
        ("游戏", "电子游戏"), ("体育", "球赛、世界杯、体育赛事"),
        ("旅行美食", "旅游、美食"), ("日常生活", "生活技巧、日常记录、家居")]),
    (OTHER, "实在归不进上面任何一类的", []),
]
DEFAULT_CATS = [(n, d) for n, d, _s in TAXONOMY]
TAX_V = 2      # v137：分类表的版本。AI 按旧版分的（tv 比这个小）点「自动贴标签」时按新版重新分；你手动定的不动          # 大类（作者领域只用大类）
# v132 的一级分类 → v134 的大类（以前贴好的标签照样认）
OLD2NEW = {"商业创业": "商业", "财经投资": "财经", "个人成长": "成长", "自媒体": "内容创作", "时事社会": "社会",
           "历史人文": "人文", "心理情感": "心理", "教育学习": "教育", "生活娱乐": "生活"}
# 模型偶尔不按名字写：常见说法 → 大类
_ALIAS = dict(OLD2NEW, **{
    "人工智能": "AI", "AI科技": "AI", "大模型": "AI", "AI工具": "AI", "AIGC": "AI",
    "数码": "科技", "科技数码": "科技", "互联网": "科技", "汽车": "科技", "航天": "科技", "机器人": "科技",
    "创业": "商业", "营销": "商业", "经营": "商业", "副业": "商业", "电商": "商业",
    "金融": "财经", "投资": "财经", "理财": "财经", "经济": "财经",
    "个人成长": "成长", "认知": "成长", "自我提升": "成长", "效率": "成长", "思维": "成长",
    "自媒体": "内容创作", "短视频": "内容创作", "创作": "内容创作", "写作": "内容创作",
    "时事": "社会", "新闻": "社会", "国际": "社会", "政治": "社会",
    "历史": "人文", "哲学": "人文", "文化": "人文",
    "心理学": "心理", "情感": "心理", "婚恋": "心理", "两性": "心理",
    "英语": "教育", "学习": "教育", "外语": "教育",
    "医学": "健康", "养生": "健康", "运动": "健康", "健身": "健康",
    "娱乐": "生活", "影视": "生活", "体育": "生活", "游戏": "生活", "美食": "生活", "旅行": "生活",
    "法律常识": "法律", "法治": "法律", "职业": "职场", "其他": OTHER,
})
PLATFORM_LABEL = {"douyin": "抖音", "bilibili": "B站", "youtube": "YouTube", "x": "X", "web": "网站"}

_lock = threading.RLock()
_cache = {}
_hooks = {"llm": None, "mode": None, "log": None}
_configured = False


def configure(llm=None, mode=None, log=None):
    """server.py 传进来：llm(prompt) → 回复文字；mode() → "local" / "pool" / ""；log(标签, 人话)。"""
    global _configured
    if llm:
        _hooks["llm"] = llm
    if mode:
        _hooks["mode"] = mode
    if log:
        _hooks["log"] = log
    _configured = True


def _log(msg):
    f = _hooks.get("log")
    if f:
        try:
            f("贴标签", msg)
        except Exception:
            pass
    else:
        print("[贴标签] " + msg)


def _mode():
    f = _hooks.get("mode")
    try:
        return f() if f else ""
    except Exception:
        return ""


# ════════════════════ 存取 ════════════════════

def _mem():
    import agent_core
    return agent_core.MEMORY_DIR


def _note_dir():
    d = _mem() / "video_notes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _note_file():
    return _note_dir() / "_labels.json"


def _author_file():
    return _mem() / "author_labels.json"


def _cfg_file():
    return _mem() / "label_config.json"


def _read(path):
    """读 json（按修改时间缓存）。返回的字典别直接改，要改先 dict() 复制一份。"""
    try:
        mt = path.stat().st_mtime
    except Exception:
        return {}
    c = _cache.get(str(path))
    if c and c[0] == mt:
        return c[1]
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            d = {}
    except Exception:
        d = {}
    _cache[str(path)] = (mt, d)
    return d


def _write(path, d):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(str(tmp), str(path))
    _cache.pop(str(path), None)


# ════════════════════ 分类表 ════════════════════

def _clean_cat(s):
    s = re.sub(r"[\s*#＃“”\"'《》「」【】\[\]()（）:：。.,，、!！?？]+", "", str(s or ""))
    return s[:8]


def cats():
    """所有大类名（默认的 + 你自己写的），「其它」放最后。"""
    names = [n for n, _d in DEFAULT_CATS if n != OTHER]
    with _lock:
        custom = list(_read(_cfg_file()).get("custom") or [])
    for c in custom:
        c = _clean_cat(c)
        c = OLD2NEW.get(c, c)
        if c and c not in names and c != OTHER:
            names.append(c)
    names.append(OTHER)
    return names


def subs_of(big):
    """这个大类下面的子类（默认的 + 你自己加的）。没有子类的大类（「其它」、你自己写的大类）返回 []。"""
    base = next(([n for n, _d in sb] for b, _d0, sb in TAXONOMY if b == big), None)
    with _lock:
        extra = list(((_read(_cfg_file()).get("subs") or {}).get(big)) or [])
    out = list(base or [])
    for x in extra:
        x = _clean_cat(x)
        if x and x not in out and x != OTHER:
            out.append(x)
    return out


def has_subs(big):
    return bool(big) and bool(subs_of(big))


def tree():
    """给界面用：[{name: 大类, subs: [子类…]}]；有子类的大类，最后都能选「其它」。"""
    out = []
    for b in cats():
        sb = subs_of(b)
        out.append({"name": b, "subs": (sb + [OTHER]) if sb else []})
    return out


def add_sub(big, sub):
    """你在某个大类里自己写了一个新子类：记下来，以后 AI 也会用。"""
    sub = _clean_cat(sub)
    if not big or not sub or sub == OTHER or sub in subs_of(big):
        return
    with _lock:
        d = dict(_read(_cfg_file()))
        m = dict(d.get("subs") or {})
        m[big] = (list(m.get(big) or []) + [sub])[-20:]
        d["subs"] = m
        _write(_cfg_file(), d)


def _tree_lines():
    """给 AI 看的两级分类表：「- 大类（说明）：子类（说明）、子类（说明）…」。"""
    info = {b: (d, dict(sb)) for b, d, sb in TAXONOMY}
    out = []
    for b in cats():
        d, sd = info.get(b, ("", {}))
        head = "- %s%s" % (b, ("（%s）" % d) if d else "")
        sb = subs_of(b)
        out.append(head + ("：" + "、".join(("%s（%s）" % (x, sd[x])) if sd.get(x) else x for x in sb) if sb else ""))
    return "\n".join(out)


def add_cat(name):
    name = _clean_cat(name)
    if not name or name in cats():
        return
    with _lock:
        d = dict(_read(_cfg_file()))
        lst = [x for x in (d.get("custom") or []) if x and x != name]
        lst.append(name)
        d["custom"] = lst[-30:]
        _write(_cfg_file(), d)


def _cat_lines():
    desc = dict(DEFAULT_CATS)
    return "\n".join(("- %s：%s" % (n, desc[n])) if desc.get(n) else ("- %s" % n) for n in cats())


def normalize_cat(raw, names=None):
    """模型写的分类 → 分类表里的名字；认不出返回空串。"""
    names = names or cats()
    s = _clean_cat(raw)
    if not s:
        return ""
    if s in names:
        return s
    up = s.upper()
    for n in names:
        if n.upper() == up:
            return n
    a = _ALIAS.get(s) or _ALIAS.get(up)
    if a and a in names:
        return a
    for n in sorted(names, key=len, reverse=True):     # 「法律常识类」「AI 科技」→ 认出里面的分类名
        if len(n) >= 2 and n.upper() in up:
            return n
    for n in names:                                     # 「财经」→「财经投资」
        if len(s) >= 2 and s in n:
            return n
    for k, v in _ALIAS.items():
        if len(k) >= 2 and k in s and v in names:
            return v
    return ""


# ════════════════════ 标签读写 ════════════════════

_SUB_ALIAS = {
    "AI": {"大模型": "模型动态", "模型": "模型动态", "评测": "模型动态", "工具": "AI工具", "智能体": "AI工具",
           "编程": "AI编程", "AGENT": "AI编程", "开发": "AI编程", "公司": "行业公司", "行业": "行业公司", "算力": "行业公司",
           "创业": "AI搞钱", "赚钱": "AI搞钱", "副业": "AI搞钱", "安全": "安全监管", "监管": "安全监管", "伦理": "安全监管",
           "研究": "前沿研究", "论文": "前沿研究", "科研": "前沿研究"},
    "商业": {"一人公司": "创业", "副业": "搞钱副业", "赚钱": "搞钱副业", "变现": "搞钱副业", "营销": "营销品牌", "品牌": "营销品牌",
           "管理": "经营管理", "企业管理": "经营管理", "电商": "电商带货", "带货": "电商带货", "行业": "行业观察"},
    "成长": {"认知": "认知思维", "思维": "认知思维", "学习": "学习方法", "读书": "学习方法", "时间管理": "效率习惯",
           "效率": "效率习惯", "自律": "效率习惯", "习惯": "效率习惯", "沟通": "沟通表达", "表达": "沟通表达"},
    "财经": {"经济": "宏观经济", "投资": "投资交易", "交易": "投资交易", "理财": "财富认知", "财富": "财富认知",
           "金融": "金融常识", "楼市": "房产"},
    "职场": {"面试": "求职", "管理": "带团队", "团队管理": "带团队", "升职": "职业发展", "职业规划": "职业发展"},
    "内容创作": {"拍摄": "短视频", "剪辑": "短视频", "运营": "账号运营", "涨粉": "账号运营", "写作": "写作文案", "文案": "写作文案",
            "IP": "个人IP", "个人品牌": "个人IP", "变现": "内容变现"},
    "科技": {"汽车": "汽车出行", "新能源": "汽车出行", "火箭": "航天", "卫星": "航天", "手机": "手机数码", "数码": "手机数码",
           "芯片": "芯片硬件", "科普": "科学科普", "科学": "科学科普"},
    "社会": {"国际": "国际局势", "政策": "政策民生", "民生": "政策民生", "爱国": "爱国与认同", "民族": "爱国与认同",
           "认同": "爱国与认同", "网红": "网红舆论", "舆论": "网红舆论", "明星": "网红舆论", "塌房": "网红舆论",
           "新闻": "媒体与信息", "报道": "媒体与信息", "谣言": "媒体与信息", "信息": "媒体与信息", "现象": "社会现象",
           "安全": "公共安全", "事故": "公共安全", "性别": "性别议题", "诈骗": "反诈防骗", "反诈": "反诈防骗"},
    "法律": {"普法": "普法常识", "刑事": "刑事案件", "民事": "民事纠纷", "劳动": "劳动权益", "维权": "消费维权",
           "版权": "知识产权", "专利": "知识产权", "商标": "知识产权", "隐私": "网络与隐私", "网络": "网络与隐私"},
    "人文": {"哲学": "哲学思想", "思想": "哲学思想", "国学": "国学经典", "文化": "文化艺术", "艺术": "文化艺术"},
    "心理": {"情绪": "情绪压力", "压力": "情绪压力", "人际": "人际关系", "婚恋": "婚恋亲密", "恋爱": "婚恋亲密", "心理学": "心理学知识"},
    "教育": {"英语学习": "英语", "语法": "英语", "家庭教育": "孩子教育", "考试": "考试升学", "留学": "考试升学"},
    "健康": {"医学": "医学常识", "饮食": "饮食营养", "营养": "饮食营养", "运动": "运动健身", "健身": "运动健身",
           "睡眠": "作息成瘾", "成瘾": "作息成瘾"},
    "生活": {"消费": "消费购物", "购物": "消费购物", "影视": "影视娱乐", "电影": "影视娱乐", "娱乐": "影视娱乐",
           "旅行": "旅行美食", "美食": "旅行美食", "日常": "日常生活"},
}


def normalize_sub(big, raw):
    """模型写的子类 → 这个大类下面的子类名；认不出返回空串。"""
    subs = subs_of(big)
    s = _clean_cat(raw)
    if not subs or not s:
        return ""
    if s in (OTHER, "其他"):
        return OTHER
    up = s.upper()
    for n in subs:
        if n.upper() == up:
            return n
    a = (_SUB_ALIAS.get(big) or {}).get(up) or (_SUB_ALIAS.get(big) or {}).get(s)
    if a in subs:
        return a
    for n in sorted(subs, key=len, reverse=True):
        if len(n) >= 2 and n.upper() in up:
            return n
    for n in subs:
        if len(s) >= 2 and up in n.upper():
            return n
    return ""


def _find_sub_anywhere(raw):
    """只写了子类名（或子类写到了别的大类下）：子类名只属于一个大类时，返回 (大类, 子类)。"""
    s = _clean_cat(raw)
    if not s or s in (OTHER, "其他"):
        return None
    hits = [(b, n) for b in cats() for n in subs_of(b) if n == s]
    return hits[0] if len(hits) == 1 else None


def _norm_note(e, valid=None):
    """v132 存的一级分类名 → 现在的大类名（子类还没定）；v137：子类已经不用了（比如「热点评法」）→ 先去掉，等重新分。"""
    if not isinstance(e, dict):
        return e
    c = e.get("cat") or ""
    if c in OLD2NEW:
        e = dict(e, cat=OLD2NEW[c])
        e.pop("sub", None)
    s = e.get("sub")
    if s and s != OTHER and valid is not None and s not in valid.get(e.get("cat") or "", ()):
        e = dict(e)
        e.pop("sub", None)
    return e


def note_labels():
    """所有文章的分类 {文件名: {cat 大类, sub 子类, kw, by, at, tv}}（以前的分类名、不用了的子类自动处理）。"""
    with _lock:
        raw = _read(_note_file())
    valid = {b: set(subs_of(b)) for b in cats()}
    return {k: _norm_note(v, valid) for k, v in raw.items()}


def author_labels():
    with _lock:
        return _read(_author_file())


def public_authors():
    """给界面用：判断出领域的作者 {名字: {dom, dir, why, src, by}}。"""
    out = {}
    for k, v in author_labels().items():
        if isinstance(v, dict) and v.get("dom"):
            out[k] = {x: v.get(x, "") for x in ("dom", "sub", "dir", "why", "src", "by")}
            out[k]["dom"] = OLD2NEW.get(out[k]["dom"], out[k]["dom"])      # v132 的分类名 → 现在的大类名
    return out


def set_note(name, cat, sub="", by="you", kw=None, eng=None):
    """给一篇文章定分类：大类 cat + 子类 sub。by="ai" 时不覆盖你手动定的。cat 为空 = 清掉。返回是否写了。"""
    name = (name or "").strip()
    if not name:
        return False
    cat = _clean_cat(cat)
    cat = OLD2NEW.get(cat, cat)
    sub = _clean_cat(sub) if cat else ""
    with _lock:
        d = dict(_read(_note_file()))
        old = d.get(name) or {}
        if by == "ai" and old.get("by") == "you":
            return False
        if not cat:
            if name not in d:
                return False
            d.pop(name, None)
        else:
            e = {"cat": cat, "by": by, "at": int(time.time())}
            if by == "ai":
                e["tv"] = TAX_V                       # v137：按哪一版分类表分的
                if eng:
                    e["eng"] = eng                    # v138：谁分的：web = 网页 AI，local = 本地模型
            if sub:
                e["sub"] = sub
            k = kw if kw is not None else old.get("kw")       # 关键词说的是内容，改分类时留着
            if k:
                e["kw"] = list(k)[:3]
            d[name] = e
        _write(_note_file(), d)
    if cat and by == "you":
        add_cat(cat)
        if sub:
            add_sub(cat, sub)
    return True


def _fill_sub(name, sub, kw=None):
    """大类是你手动定的、子类还空着：AI 只补子类（大类不动，还算你定的）。"""
    with _lock:
        d = dict(_read(_note_file()))
        e = dict(d.get(name) or {})
        if not e.get("cat") or e.get("sub") or not sub:
            return False
        e["cat"] = OLD2NEW.get(e["cat"], e["cat"])
        e["sub"] = _clean_cat(sub)
        if kw and not e.get("kw"):
            e["kw"] = list(kw)[:3]
        d[name] = e
        _write(_note_file(), d)
    return True


def set_author(key, dom, by="you", sub="", **extra):
    """给作者定领域。by="ai" 时不覆盖你手动定的。dom 为空 = 清掉。"""
    key = (key or "").strip()
    if not key:
        return False
    dom = _clean_cat(dom)
    dom = OLD2NEW.get(dom, dom)
    with _lock:
        d = dict(_read(_author_file()))
        old = d.get(key) or {}
        if by == "ai" and old.get("by") == "you":
            return False
        if not dom:
            d.pop(key, None)
        else:
            e = {"dom": dom, "by": by, "at": int(time.time())}
            if sub and by == "you":
                e["sub"] = _clean_cat(sub)
            if by == "ai":
                for k in ("dir", "why", "src"):
                    if extra.get(k):
                        e[k] = str(extra[k])[:120]
            d[key] = e
        _write(_author_file(), d)
    if dom and by == "you":
        add_cat(dom)
        if sub:
            add_sub(dom, sub)
    return True


def _author_fail(key, why):
    """这位作者这次没判断出来：记下时间和原因（自动贴时一天内不再试；点「自动贴标签」会再试）。"""
    with _lock:
        d = dict(_read(_author_file()))
        old = dict(d.get(key) or {})
        if old.get("dom"):
            return
        old.update({"tried_at": int(time.time()), "err": (why or "")[:120]})
        d[key] = old
        _write(_author_file(), d)


# ════════════════════ 读笔记 ════════════════════

_SUM_RE = re.compile(r"^#{2,4}\s*(?:\d+[\.、]\s*)?一句话(?:概括|总结)\s*$", re.M)


def _short(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:n]


def _summary(txt, n=140):
    """加工结果里的「一句话概括」；没有就取加工结果开头一段。"""
    m = _SUM_RE.search(txt)
    if m:
        para = []
        for ln in txt[m.end():].splitlines():
            s = ln.strip()
            if not s:
                if para:
                    break
                continue
            if s.startswith("#"):
                break
            para.append(s)
        if para:
            return _short(" ".join(para), n)
    i = txt.find("## 🤖 AI 分析")
    if i >= 0:
        body = txt[i + len("## 🤖 AI 分析"):]
        j = body.find("## 📝")
        if j > 0:
            body = body[:j]
        body = body.replace("ChatGPT 说：", " ")
        body = re.sub(r"[#>*`|]+", " ", body)
        return _short(body, n)
    return ""


def _parse_note(name, txt):
    lines = txt.splitlines()
    title = lines[0].lstrip("# ").strip() if lines else name[:-3]
    author = url = ""
    tags = []
    head = []
    for ln in lines[1:60]:                     # 元信息区：标题下面、第一个「## 」之前（标题可能有好几行）
        if ln.strip().startswith("## "):
            break
        head.append(ln)
    for ln in head:
        s = ln.strip().lstrip("-").strip()
        if not author and s.startswith(("作者：", "作者:")):
            c = s[3:].strip()
            if c and not c.isdigit():          # 纯数字是抖音没抓到昵称的兜底，界面上也不显示
                author = c[:40]
        elif not url and s.startswith(("来源链接：", "来源链接:")):
            url = s[5:].strip()
        elif not tags and s.startswith(("标签：", "标签:")):
            tags = [t.strip() for t in re.split(r"[、,，]", s[3:]) if t.strip()][:8]
    analyzed = not any(l.strip().lstrip("-").strip().startswith(("状态：未分析", "状态:未分析"))
                       for l in head)
    if analyzed and any("（分析出错" in ln for ln in lines[:120]):
        analyzed = False
    points = []                                # v138：「核心观点」的几个小标题（给网页 AI 判断用，信息多一点更准）
    if analyzed:
        mm = re.search(r"(?m)^#{2,3}\s*核心观点\s*$", txt)
        if mm:
            for h in re.findall(r"(?m)^###\s*(?:\d+[\.、]\s*)?(.+)$", txt[mm.end():mm.end() + 8000])[:5]:
                points.append(_short(h.replace("**", ""), 40))
    return {"name": name, "title": title, "author": author, "url": url, "tags": tags,
            "analyzed": analyzed, "summary": _summary(txt, 220) if analyzed else "", "points": points}


def scan_notes():
    """所有笔记（新的在前）。只读每个文件的开头一段（够拿标题、作者、标签和一句话概括），快。"""
    out = []
    for p in sorted(_note_dir().glob("*.md"), reverse=True):
        try:
            with open(p, "rb") as f:
                txt = f.read(12000).decode("utf-8", "ignore")
        except Exception:
            continue
        out.append(_parse_note(p.name, txt))
    return out


# ════════════════════ 问 AI ════════════════════

def _llm(prompt):
    f = _hooks.get("llm")
    if not f:
        raise RuntimeError("没有可用的 AI")
    return f(prompt) or ""


# v137/v138：分类规则（贴标签和「加工」写笔记时都用这一份）
_RULES = ("· 按这篇具体讲的是什么事来分，不按作者是谁，也不按讲法（评论、科普、吐槽）分\n"
          "· 律师、博主评热点，看他评的是什么事：评校招工资放「职场/求职」，评手机质量放「科技/手机数码」，"
          "评调休放「法律/劳动权益」，评主播塌房放「社会/网红舆论」；只有核心在讲法律知识、案件定性、怎么维权的才放「法律」\n"
          "· 作者是自媒体博主，不代表这篇就是「内容创作」——只有讲怎么做内容、做账号的才放那里\n"
          "· 和 AI 相关的都放 AI（哪怕是 AI 公司的新闻）；转发的推文按推文讲的事分\n"
          "· 讲电影电视剧的剧情、人物、演技放「生活/影视娱乐」；借剧情讲商业、做人道理的，按讲的道理分\n"
          "· 子类挑最贴近这篇主题的那个，不要把讲不同事情的文章都塞进同一个笼统的子类；"
          "子类都不合适写「大类/其它」，整张表都不合适才写「%s」\n" % OTHER)


def analysis_guide():
    """v138：给「加工」的提示词用：分类表 + 分类规则——写笔记的 AI 顺手在最后分好类、总结好标签。"""
    return ("分类表（每行「-」后面是大类，冒号后面是它的子类，括号里是说明；只写名字，不要写说明）：\n%s\n分类规则：\n%s"
            % (_tree_lines(), _RULES))


def parse_path(path, fixed="", lenient=False):
    """「大类/子类」→ (大类, 子类)。认不出返回 ("", "")；大类认出了、子类没写对：lenient 时子类放「其它」，否则子类留空。"""
    names = cats()
    path = re.sub(r"^(?:分类|大类)\s*[:：]?", "", (path or "").replace("**", "").strip()).strip()
    bits = [x for x in re.split(r"\s*[/／·>＞→\-－—]+\s*", path, maxsplit=1) if x.strip()]
    if not bits:
        return "", ""
    one = _find_sub_anywhere(bits[0]) if len(bits) == 1 else None      # 只写了子类名（「投资交易」）
    cat = one[0] if one else normalize_cat(bits[0], names)
    sub = one[1] if one else (normalize_sub(cat, bits[1]) if (cat and len(bits) > 1) else "")
    if len(bits) > 1 and not sub:                 # 子类写到了别的大类下：按子类认大类
        hit = _find_sub_anywhere(bits[1])
        if hit:
            cat, sub = hit
    if not cat:
        hit = _find_sub_anywhere(bits[0])
        if hit:
            cat, sub = hit
    if fixed:                                     # 大类是你定的：只要子类
        sub = normalize_sub(fixed, bits[-1])
        if not sub and lenient:
            sub = OTHER
        return (fixed, sub) if sub else ("", "")
    if not cat and lenient and _clean_cat(bits[0]):
        cat = OTHER
    if not cat:
        return "", ""
    if has_subs(cat) and not sub and lenient:
        sub = OTHER
    return cat, sub


_SEC_RE = re.compile(r"(?m)^#{1,4}\s*(?:\d+[\.、]\s*)?分类(?:与)?标签\s*[:：]?\s*$")


def split_from_analysis(text):
    """v138：「加工」结果最后 AI 写的「## 分类标签」一节：拆出来，从笔记正文里去掉。
    返回 (正文, 大类, 子类, 标签列表)；没有这一节返回 (原文, "", "", [])。"""
    t = text or ""
    ms = list(_SEC_RE.finditer(t))
    if not ms:
        return t, "", "", []
    m = ms[-1]
    rest = t[m.end():]
    nxt = re.search(r"(?m)^#{1,4}\s", rest)
    sec = rest[:nxt.start()] if nxt else rest
    body = (t[:m.start()].rstrip() + ("\n\n" + rest[nxt.start():] if nxt else "")).rstrip()
    tags, path = [], ""
    for ln in sec.splitlines():
        x = ln.strip().lstrip("-*•· ").replace("**", "").strip()
        mm = re.match(r"^(?:标签|关键词)\s*[:：]\s*(.+)$", x)
        if mm:
            tags = _clean_kws(mm.group(1), n=5)
            continue
        mm = re.match(r"^(?:分类|大类/子类|大类／子类|类别)\s*[:：]\s*(.+)$", x)
        if mm:
            path = mm.group(1)
    cat, sub = parse_path(path) if path else ("", "")
    if cat:
        tags = [k for k in tags if k not in (cat, sub)]
    return body, cat, sub, tags


def _note_prompt(batch, rich=False):
    rows = []
    for i, n in enumerate(batch, 1):
        parts = ["标题：" + _short(n["title"], 90)]
        if n.get("tags"):
            parts.append("原标签：" + "、".join(n["tags"][:6]))
        if n.get("summary"):
            parts.append("概括：" + (n["summary"] if rich else _short(n["summary"], 140)))
        if rich and n.get("points"):
            parts.append("要点：" + "；".join(n["points"]))
        if n.get("fixed"):
            parts.append("大类已定：" + n["fixed"])
        rows.append("%d. %s" % (i, "｜".join(parts)))
    return ("你是内容分类助手。下面是我收藏的 %d 篇笔记。请先给每篇总结 3～5 个标签，再根据这些标签和内容分类："
            "先选一个大类，再选这个大类下面的一个子类。\n\n"
            "分类表（每行「-」后面是大类，冒号后面是它的子类，括号里是说明；只写名字，不要写说明）：\n%s\n\n"
            "分类规则：\n%s\n"
            "输出要求：\n"
            "① 每篇只输出一行，格式：编号. 标签1、标签2、标签3｜大类/子类\n"
            "② 标签 2～6 个字，说清楚这篇具体讲的什么；不要写作者名、账号名、平台活动名（比如“抖音精选”“抖来学法”）\n"
            "③ 标了「大类已定」的，大类照写，只在那个大类里选子类\n"
            "④ 不要解释，不要输出别的内容\n\n"
            "示例输出：\n1. 信用卡、消费陷阱、分期｜财经/金融常识\n2. Claude Code、Agent、写代码｜AI/AI编程\n"
            "3. 调休、加班、假期制度｜法律/劳动权益\n4. 校招、起薪、应届生｜职场/求职\n\n"
            "笔记：\n%s\n" % (len(batch), _tree_lines(), _RULES, "\n".join(rows)))


# v139：每行开头的编号。「1.」「1、」「1)」之外，也认「【1】」「(1)」「第1篇」；「3.5 Sonnet」这种不算编号
_LINE_RE = re.compile(r"^\s*(?:[\[【(（]\s*(\d{1,3})\s*[\]】)）]|第\s*(\d{1,3})\s*篇|(\d{1,3})\s*[\.\)）．](?!\d)|(\d{1,3})\s*[、:：])"
                      r"\s*[\.、:：．]?\s*(.+?)\s*$")
# 好几篇挤在一行里时（换行没读到），在下一篇的编号前面断开
_JOIN_RE = re.compile(r"\s+(?=(?:[\[【]\d{1,3}[\]】]|第\d{1,3}篇|\d{1,3}[\.\)）．]\s|\d{1,3}、)\s*\S)")


def _num_line(ln):
    """一行 →（编号, 后面的内容）；不是编号开头的 →（None, 这一行）。"""
    m = _LINE_RE.match(ln)
    if not m:
        return None, ln
    return int(next(g for g in m.groups()[:4] if g)), m.group(5)


def _reply_lines(raw):
    """v139：AI 的回复 → 一行行：去掉代码块标记、引用符号、标题井号；Markdown 表格「| 1 | 标签 | 大类/子类 |」
    换成「1. 标签｜大类/子类」；好几篇挤在一行的拆开。"""
    out = []
    for ln in (raw or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("```"):
            continue
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 3:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue                                             # 表头下面那行 | --- | --- |
            if cells and re.fullmatch(r"\d{1,3}", cells[0]):
                s = cells[0] + ". " + "｜".join(c for c in cells[1:] if c)
            else:
                s = "｜".join(c for c in cells if c)
        s = re.sub(r"^[-•·+]\s+", "", s.lstrip(">#").strip()).strip("*").strip()
        if not s:
            continue
        if len(re.findall(r"[｜|]", s)) >= 2:
            out += [x.strip() for x in _JOIN_RE.split(s) if x.strip()]
        else:
            out.append(s)
    return out


def _is_item(ln):
    """像不像「标签…｜大类/子类」这样的一篇（提示词里的格式说明、表头不算）。"""
    return bool(re.search(r"[｜|]", ln)) and not re.search(r"大类\s*[/／]\s*子类|标签1|编号", ln)


def _clean_kws(s, avoid=(), n=2):
    out = []
    for k in re.split(r"[、,，/;；]+", s or ""):
        k = k.strip().strip("#＃“”\"'《》「」()（）[]【】.。·:：*").strip()
        if not k or len(k) > (20 if k.isascii() else 10) or k in out:      # 英文词（Claude Code）可以长一点
            continue
        if any(a and (k == a or k in a) for a in avoid):
            continue
        out.append(k)
        if len(out) >= n:
            break
    return out


def _parse_note_reply(raw, batch, lenient=False, info=None):
    """每行「编号. 标签…｜大类/子类」（老格式「编号. 大类/子类｜关键词」也认）→ {序号: (大类, 子类, 标签)}。
    lenient=True（第二遍）：子类认不出就放「大类/其它」，大类也认不出就放「其它」。
    v139：网页 AI 回成有序列表时，网页上的「1.」「2.」是画出来的，读回来常常没有编号 →
          这时只要「标签｜分类」的行数正好等于篇数，就按顺序一行对一篇（行数对不上就不猜，算格式不对）。
          info（可选的 dict）里写这次是按编号（num）还是按顺序（order）对的。"""
    lines = _reply_lines(raw)
    numbered = []
    for ln in lines:
        k, body = _num_line(ln)
        if k is not None:
            numbered.append((k - 1, body))
    items = [ln for ln in lines if _is_item(ln)]
    if len(numbered) >= max(2, len(items) // 2) or (len(batch) == 1 and numbered):
        pairs, how = numbered, "num"
    elif items and len(items) == len(batch):
        pairs, how = list(enumerate(items)), "order"
    else:
        pairs, how = [], ""                   # 编号没几个（多半只是碰巧像编号）、行数又对不上：不猜
    if isinstance(info, dict):
        info["how"] = how
    out = {}
    for idx, body in pairs:
        if not (0 <= idx < len(batch)) or idx in out:
            continue
        parts = [x.strip() for x in re.split(r"[｜|]", body) if x.strip()]
        if not parts:
            continue
        ci = max((i for i, x in enumerate(parts) if re.search(r"[/／]", x)), default=len(parts) - 1)   # 带「/」的是分类
        fixed = batch[idx].get("fixed") or ""
        cat, sub = parse_path(parts[ci], fixed=fixed, lenient=lenient)
        if not cat or (has_subs(cat) and not sub):
            continue                              # 没认出来：最后再单独问一次（第二遍放宽）
        kws = "、".join(re.sub(r"^(?:标签|关键词)\s*[:：]", "", x) for i, x in enumerate(parts) if i != ci)
        out[idx] = (cat, sub, _clean_kws(kws, avoid=(cat, sub, batch[idx].get("author") or ""), n=4))
    return out


def _preview(s, n=120):
    """v139：日志里给人看的 AI 原话：换行显示成「⏎」，看得出 AI 是一行一篇还是挤成了一行。"""
    s = re.sub(r"[ \t\u00a0]+", " ", str(s or "")).strip()
    return re.sub(r"\s*\n\s*", " ⏎ ", s)[:n]


def _why_bad(raw, batch):
    """v139：这一批为什么一篇都没认出来（说人话）。"""
    if not (raw or "").strip():
        return "AI 回的是空的"
    lines = _reply_lines(raw)
    items = [ln for ln in lines if _is_item(ln)]
    if not items and not any(_num_line(ln)[0] is not None for ln in lines):
        return "没看到「标签｜大类/子类」这样的行"
    if items and not any(_num_line(ln)[0] is not None for ln in items) and len(items) != len(batch):
        return "读到 %d 行、问的是 %d 篇，又没有编号，对不上是哪篇" % (len(items), len(batch))
    return "分类名认不出来"


def _dump_bad(raw, batch, why):
    """v139：格式不对时把 AI 的原话存一份到 memory/web_model_diag/labels-时间.txt（推送到 GitHub 后能帮忙看原因），只留最近 5 份。"""
    try:
        d = _mem() / "web_model_diag"
        d.mkdir(parents=True, exist_ok=True)
        head = ["原因：%s" % why, "这一批 %d 篇：" % len(batch)]
        head += ["  %d. %s" % (i, _short(n.get("title"), 40)) for i, n in enumerate(batch, 1)]
        (d / ("labels-%s-%03d.txt" % (time.strftime("%Y%m%d-%H%M%S"), int(time.time() * 1000) % 1000))).write_text(
            "\n".join(head) + "\n\n—— AI 原话 ——\n" + str(raw or ""), encoding="utf-8")
        for old in sorted(d.glob("labels-*.txt"))[:-5]:
            old.unlink()
    except Exception:
        pass


def _author_prompt(ev):
    lines = ["作者：%s%s" % (ev["name"], ("（%s）" % ev["meta"]) if ev.get("meta") else "")]
    if ev.get("bio"):
        lines.append("主页简介：" + _short(ev["bio"], 200))
    if ev.get("home_titles"):
        lines.append("主页上最近的作品：")
        lines += ["%d. %s" % (i, _short(t, 70)) for i, t in enumerate(ev["home_titles"][:30], 1)]
    if ev.get("local_titles"):
        lines.append("我收藏的这位作者的笔记：")
        lines += ["%d. %s" % (i, _short(t, 70)) for i, t in enumerate(ev["local_titles"][:15], 1)]
    return ("你是内容分类助手。根据下面这位内容作者的资料，判断他主要做哪个领域的内容。\n\n"
            "领域只能从下面选一个（只写名字，不要写说明）：\n%s\n\n"
            "只输出一行，格式：领域｜细分方向｜理由\n"
            "· 细分方向 2～10 个字，比如“律师说法、时事评论”“AI 工具测评”\n"
            "· 理由 30 字以内，说依据（简介写了什么、作品主要讲什么）\n"
            "不要解释，不要输出别的内容。\n\n"
            "示例输出：法律｜律师说法、时事评论｜简介写着执业律师，作品多用法律视角评热点\n\n"
            "%s\n" % (_cat_lines(), "\n".join(lines)))


def _parse_author_reply(raw):
    names = cats()
    for ln in (raw or "").splitlines():
        ln = ln.strip().strip("*").strip()
        if not ln:
            continue
        ln = re.sub(r"^(?:输出|答案|结果)\s*[:：]\s*", "", ln)
        parts = [p.strip() for p in re.split(r"[｜|]", ln)]
        if len(parts) < 2 and len(ln) > 12:
            continue
        dom = normalize_cat(re.sub(r"^领域\s*[:：]?", "", parts[0]), names)
        if dom:
            d = re.sub(r"^细分方向\s*[:：]?", "", parts[1]).strip()[:20] if len(parts) > 1 else ""
            why = re.sub(r"^理由\s*[:：]?", "", "｜".join(parts[2:])).strip()[:60] if len(parts) > 2 else ""
            return {"dom": dom, "dir": d, "why": why}
    hits = [n for n in names if n in (raw or "")]                  # 兜底：整段话里只提到一个分类名
    if len(hits) == 1:
        return {"dom": hits[0], "dir": "", "why": ""}
    return None


# ════════════════════ 读作者主页 ════════════════════

def _with_timeout(fn, timeout):
    """在后台线程里跑 fn()，最多等 timeout 秒（读主页偶尔会卡住，不能让整个贴标签停在那）。
    返回 (结果, 错误说明)。"""
    box = {}

    def run():
        try:
            box["r"] = fn()
        except Exception as e:
            box["e"] = str(e)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        return None, "超过 %d 秒没读完" % timeout
    if "e" in box:
        return None, box["e"]
    return box.get("r"), ""


def _brief_err(e):
    s = re.split(r"[。\n]", str(e or "").strip())[0]
    return _short(s, 40)


def author_evidence(key, notes_of_author, fetch=True, force_find=False, skip_plats=()):
    """收集判断作者领域的材料：主页简介 + 主页最近作品标题 + 库里这位作者的笔记标题。
    skip_plats：这一轮连着读不到的平台，先不读（只用简介和库里的笔记）。"""
    ev = {"name": key, "meta": "", "bio": "", "home_titles": [], "home": "", "net": False, "read_plat": "",
          "local_titles": [_short(n["title"], 90) for n in notes_of_author if n.get("title")][:15],
          "n_local": len(notes_of_author), "home_err": ""}
    try:
        import creator_profiles as cp
        prof = cp.profile_state(key)
    except Exception:
        cp, prof = None, {}
    home = prof.get("url") or prof.get("home") or ""
    if fetch and cp is not None and not home:
        urls = [n["url"] for n in notes_of_author if (n.get("url") or "").startswith("http")][:3]
        if urls and not force_find and not cp.should_auto_bind(key):
            ev["home_err"] = ("你解除过这位作者的主页" if prof.get("no_auto")
                              else "之前自动找主页没成功（%s）" % _brief_err(prof.get("error") or "原因不明"))
        elif urls:
            with _lock:
                _job["a_stage"] = "找主页"
            ev["net"] = True
            r, err = _with_timeout(lambda: cp.auto_bind_from_videos(key, urls, force=force_find), 120)
            if r and r[0]:
                prof = cp.profile_state(key)
                home = prof.get("url") or prof.get("home") or ""
            elif not home:
                ev["home_err"] = "没找到主页：" + _brief_err(err or (r[1] if r else ""))
        else:
            ev["home_err"] = "笔记里没有视频链接，找不到主页"
    plat = prof.get("platform") or ""
    ev["home"] = home
    ev["bio"] = _short(prof.get("signature") or "", 200)
    meta = []
    if plat:
        meta.append(PLATFORM_LABEL.get(plat, plat))
    try:
        fans = int(prof.get("followers") or 0)
        if fans:
            meta.append("粉丝 %s" % (("%.1f 万" % (fans / 10000.0)) if fans >= 10000 else fans))
    except Exception:
        pass
    ev["meta"] = "，".join(meta)
    if fetch and home and plat in skip_plats:
        ev["home_err"] = "这一轮先不读%s主页：前面连着几位都没读到" % PLATFORM_LABEL.get(plat, plat)
    elif fetch and home and plat in PLATFORM_LABEL:
        ev["read_plat"] = plat
        with _lock:
            _job["a_stage"] = "读主页"
        ev["net"] = True

        def _list():
            import creator_watch as cw
            return cw.list_recent(plat, home, 20)
        data, err = _with_timeout(_list, 90)
        titles = []
        for v in ((data or {}).get("videos") or []):
            t = _short((v or {}).get("title") or "", 90)
            if t and t not in titles:
                titles.append(t)
        ev["home_titles"] = titles[:30]
        if not titles:
            ev["home_err"] = "主页没读到作品：" + _brief_err(err or "列表是空的")
    elif home and not fetch:
        ev["home_err"] = "这次没读主页"
    src = []
    if ev["home_titles"]:
        src.append("主页 %d 条作品" % len(ev["home_titles"]))
    if ev["bio"]:
        src.append("主页简介")
    if ev["local_titles"]:
        src.append("库里 %d 篇笔记" % ev["n_local"])
    ev["src"] = " + ".join(src) + (("（%s）" % ev["home_err"]) if ev["home_err"] and not ev["home_titles"] else "")
    return ev


# ════════════════════ 后台任务 ════════════════════

_job = {"running": False, "stop": False, "auto": False, "phase": "", "mode": "",
        "n_total": 0, "n_done": 0, "n_ok": 0, "n_fail": 0,
        "a_total": 0, "a_done": 0, "a_ok": 0, "a_fail": 0, "a_local": 0, "a_cur": "", "a_stage": "",
        "started": 0, "finished": 0, "summary": "", "err": ""}
_want = {"full": False, "notes": [], "authors": []}
_NOTE_BATCH = {"local": 12, "pool": 30}
_HOME_OFF_AFTER = 5            # 连着这么多位作者的主页都读不到 → 这一轮后面的只用库里的笔记判断
_NET_PAUSE = 3                 # 读完一位作者的主页，歇几秒再读下一位（免得被平台风控）
AUTHOR_FROM_NOTES = 5          # v135：库里分好类的文章有这么多篇的作者，领域直接按这些文章算（界面上算），不用读主页


def _flag_file():
    return _mem() / "label_job.json"


def _flag(on):
    """v136：你点了「自动贴标签」还没贴完就关了软件 → 下次开软件接着贴。"""
    try:
        p = _flag_file()
        if on:
            p.write_text(json.dumps({"at": int(time.time())}), encoding="utf-8")
        elif p.exists():
            p.unlink()
    except Exception:
        pass


def resume_on_start():
    try:
        if _flag_file().exists():
            _log("接着上次没贴完的标签")
            start(full=True)
    except Exception:
        pass


def job_state():
    with _lock:
        d = dict(_job)
    d["now"] = time.time()
    return d


def stopping():
    return bool(_job.get("stop"))


def stop():
    with _lock:
        _want.update(full=False, notes=[], authors=[])
        if _job["running"]:
            _job["stop"] = True
    return True


def start(full=True, notes=None, authors=None, auto=False):
    """开始（或给正在跑的追加）贴标签。full=True：所有还没贴的；notes/authors：只做这几个。
    auto=True：新加工好的自动贴，界面上不显示进度。"""
    with _lock:
        if full:
            _want["full"] = True
        for n in notes or []:
            if n and n not in _want["notes"]:
                _want["notes"].append(n)
        for a in authors or []:
            if a and a not in _want["authors"]:
                _want["authors"].append(a)
        if _job["running"]:
            if not auto:
                _job["auto"] = False           # 你点的：接着跑，界面上显示进度
                if full:
                    _flag(True)
            return True
        _job.update({"running": True, "stop": False, "auto": bool(auto), "phase": "", "mode": "",
                     "n_total": 0, "n_done": 0, "n_ok": 0, "n_fail": 0,
                     "a_total": 0, "a_done": 0, "a_ok": 0, "a_fail": 0, "a_local": 0, "a_cur": "", "a_stage": "",
                     "started": time.time(), "finished": 0, "summary": "", "err": "", "order_noted": False})
    if full and not auto:
        _flag(True)
    threading.Thread(target=_run, daemon=True, name="labels").start()
    return True


def enqueue_notes(names):
    """新加工好的文章：有本地模型就自动贴（分类 + 作者还没领域的顺手判断）；
    只有 AI 池时先不贴（不和批量加工抢 AI 池），等你点「自动贴标签」。"""
    names = [n for n in (names or []) if n]
    if not names or _mode() != "local":
        return False
    return start(full=False, notes=names, auto=True)


def redo(kind, key):
    """你点了「让 AI 重新判断」：先清掉原来的，再单独判断这一个（作者会重新读主页）。"""
    key = (key or "").strip()
    if not key:
        return False
    if kind == "note":
        set_note(key, "", by="you")
        return start(full=False, notes=[key])
    if kind == "author":
        set_author(key, "", by="you")
        return start(full=False, authors=[key])
    return False


def _label_ok(e):
    """v138：这篇已经按最新分类表分好了，而且是网页 AI 分的（或你手动定的）。"""
    if not e or not e.get("cat"):
        return False
    if has_subs(e["cat"]) and not e.get("sub"):
        return False
    return e.get("by") == "you" or (int(e.get("tv") or 1) >= TAX_V and e.get("eng") == "web")


def _do_notes(todo, bs):
    """一批一批分类。AI 连着 3 次没回话 / 格式不对 → 抛异常停下。"""
    pending, second, consec = list(todo), [], 0
    retried, lenient = set(), False
    while (pending or second) and not _job["stop"]:
        if not pending:
            pending, second = second, []
            bs, lenient = max(4, bs // 2), True
        batch, pending = pending[:bs], pending[bs:]
        info = {}
        try:
            raw = _llm(_note_prompt(batch, rich=_job.get("mode") == "pool"))
            got = _parse_note_reply(raw, batch, lenient=lenient, info=info)
        except Exception as e:
            if _job["stop"]:
                break
            consec += 1
            _log("文章分类这一批没成功（%s）" % str(e)[:100])
            if consec >= 3:
                raise RuntimeError("AI 连着 3 次没回话：%s" % _brief_err(e))
            pending = batch + pending
            time.sleep(5)
            continue
        if not got:
            consec += 1
            why = _why_bad(raw, batch)
            _log("文章分类这一批 AI 回的格式不对（%s）：%s" % (why, _preview(raw)))
            _dump_bad(raw, batch, why)
            if consec >= 3:
                raise RuntimeError("AI 连着 3 次回的格式不对，认不出分类（%s）" % why)
            pending = batch + pending
            continue
        consec = 0
        if info.get("how") == "order" and not _job.get("order_noted"):
            with _lock:
                _job["order_noted"] = True
            _log("AI 的回复里没读到编号（网页上的序号是画出来的），行数和篇数对得上，按顺序一行对一篇")
        for i, n in enumerate(batch):
            if i in got:
                cat, sub, kw = got[i]
                if n.get("fixed"):
                    _fill_sub(n["name"], sub, kw)
                else:
                    set_note(n["name"], cat, sub=sub, by="ai", kw=kw,
                             eng="web" if _job.get("mode") == "pool" else "local")
                with _lock:
                    _job["n_done"] += 1
                    _job["n_ok"] += 1
            elif n["name"] not in retried:
                retried.add(n["name"])          # 这一篇 AI 漏了：最后再单独问一次
                second.append(n)
            else:
                with _lock:
                    _job["n_done"] += 1
                    _job["n_fail"] += 1


def _do_authors(cand, by_author, forced):
    streak, off, consec = {}, set(), 0          # 按平台数：连着读不到主页的次数 / 这一轮先不读的平台
    for a in cand:
        if _job["stop"]:
            break
        with _lock:
            _job.update(phase="authors", a_cur=a, a_stage="")
        ev = author_evidence(a, by_author.get(a) or [], force_find=(a in forced), skip_plats=off)
        p = ev["read_plat"]
        if p:                                    # 只数「主页找到了却读不到」，找不到主页是这位作者自己的事
            streak[p] = 0 if ev["home_titles"] else streak.get(p, 0) + 1
            if streak[p] >= _HOME_OFF_AFTER and p not in off:
                off.add(p)
                _log("连着 %d 位作者的%s主页都没读到（%s），这一轮后面的%s作者先只用简介和库里的笔记判断"
                     % (streak[p], PLATFORM_LABEL.get(p, p), ev["home_err"] or "原因不明", PLATFORM_LABEL.get(p, p)))
        ok = False
        if ev["home_titles"] or ev["local_titles"] or ev["bio"]:
            with _lock:
                _job["a_stage"] = "判断领域"
            try:
                r = _parse_author_reply(_llm(_author_prompt(ev)))
                consec = 0
            except Exception as e:
                if _job["stop"]:
                    break
                consec += 1
                r = None
                _log("作者「%s」没判断出来（%s）" % (a, str(e)[:100]))
                if consec >= 3:
                    raise RuntimeError("AI 连着 3 次没回话：%s" % _brief_err(e))
            if r:
                ok = set_author(a, r["dom"], by="ai", dir=r["dir"], why=r["why"], src=ev["src"])
                if ok and not ev["home_titles"]:
                    with _lock:
                        _job["a_local"] += 1
            else:
                _author_fail(a, "AI 没给出领域")
        else:
            _author_fail(a, "没有能用来判断的材料")
        with _lock:
            _job["a_done"] += 1
            _job["a_ok" if ok else "a_fail"] += 1
        if ev["net"] and not _job["stop"]:
            time.sleep(_NET_PAUSE)              # 别连着请求作者主页，免得被平台风控


def _run():
    try:
        mode = _mode()
        with _lock:
            _job["mode"] = mode
        if not mode:
            raise RuntimeError("没有可用的 AI（本地模型没开，AI 池也用不了）")
        while not _job["stop"]:
            with _lock:
                full = _want["full"]
                q_notes, q_auth = list(_want["notes"]), list(_want["authors"])
                _want.update(full=False, notes=[], authors=[])
            if not (full or q_notes or q_auth):
                break
            notes = scan_notes()
            # ① 文章分类
            lab = note_labels()
            qs = set(q_notes)
            todo = []
            for n in notes:
                if not n["analyzed"] or (not full and n["name"] not in qs):
                    continue
                e = lab.get(n["name"]) or {}
                if _label_ok(e):
                    continue                          # 已经按最新分类表、由网页 AI（或你手动）分好了
                if e.get("by") == "you":
                    if e.get("sub") or not has_subs(e.get("cat") or ""):
                        continue                      # 你手动定好的不动
                    n = dict(n, fixed=e["cat"])       # v134：大类你定了，子类让 AI 在里面选
                todo.append(n)
            if todo:
                with _lock:
                    _job["n_total"] += len(todo)
                    _job["phase"] = "notes"
                eng = "local" if (_job.get("auto") and mode == "local") else "pool"   # v138：你点的用网页 AI；新加工的自动补用本地模型
                with _lock:
                    _job["mode"] = eng
                _log("开始给 %d 篇文章分类（%s）" % (len(todo), "本地模型" if eng == "local" else "网页 AI"))
                _do_notes(todo, _NOTE_BATCH.get(eng, 12))
            if _job["stop"]:
                break
            # ② 作者领域
            by_author = {}
            for n in notes:
                if n["author"]:
                    by_author.setdefault(n["author"], []).append(n)
            alab = author_labels()
            now = time.time()
            lab2 = note_labels()
            nlab = collections.Counter(n["author"] for n in notes
                                       if n["author"] and n["analyzed"] and (lab2.get(n["name"]) or {}).get("cat"))
            cand = []
            if full:
                cand = [a for a in by_author if not (alab.get(a) or {}).get("dom") and nlab[a] < AUTHOR_FROM_NOTES]
            for a in q_auth:
                if a in by_author and a not in cand:
                    cand.append(a)
            for n in notes:
                a = n["author"]
                if n["name"] in qs and a and a not in cand:
                    e = alab.get(a) or {}
                    if (not e.get("dom") and not (e.get("tried_at") and now - e["tried_at"] < 86400)
                            and nlab[a] < AUTHOR_FROM_NOTES):
                        cand.append(a)
            cand.sort(key=lambda a: -len(by_author.get(a) or []))   # 笔记多的作者先判断
            if cand:
                with _lock:
                    _job["a_total"] += len(cand)
                    _job["phase"] = "authors"
                    _job["mode"] = mode               # 作者（库里文章不到 5 篇的）按主页判断：本机有本地模型就用本地的，快
                _log("开始判断 %d 位作者的领域（读主页 + 库里的笔记）" % len(cand))
                _do_authors(cand, by_author, set(q_auth))
    except Exception as e:
        with _lock:
            _job["err"] = _short(str(e), 120)
        _log("没贴完：%s" % e)
    finally:
        with _lock:
            j = _job
            done_bits = []
            if j["n_ok"]:
                done_bits.append("文章 %d 篇" % j["n_ok"])
            if j["a_ok"]:
                done_bits.append("作者 %d 位" % j["a_ok"])
            if j["stop"]:
                s = "已停止" + ("，贴好了" + "、".join(done_bits) if done_bits else "") + "。下次点「自动贴标签」接着贴"
            elif j["err"]:
                s = ""
            elif done_bits:
                s = "贴好了：" + "、".join(done_bits)
                if j["a_local"]:
                    s += "（%d 位作者主页没读到，用库里的笔记判断的）" % j["a_local"]
                if j["n_fail"] or j["a_fail"]:
                    s += "；没贴上：" + "、".join(x for x in (
                        ("文章 %d 篇" % j["n_fail"]) if j["n_fail"] else "",
                        ("作者 %d 位" % j["a_fail"]) if j["a_fail"] else "") if x)
            else:
                s = "都贴好了，没有要贴的" if not (j["n_fail"] or j["a_fail"]) else "这次没贴上"
            j.update({"running": False, "stop": False, "phase": "", "a_cur": "", "a_stage": "",
                      "finished": time.time(), "summary": s})
        _flag(False)                           # 贴完 / 你点了停止 / 出错停下：都不用再接着贴
        if not _job["auto"] and s:              # v139：出错停下的，上面已经打过「没贴完：…」，不再打第二遍
            _log(s)
