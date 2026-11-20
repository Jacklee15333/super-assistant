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

import json
import os
import re
import threading
import time

OTHER = "其它"
DEFAULT_CATS = [
    ("AI", "大模型、AI 工具和应用、AI 编程、Agent、AI 公司和行业动态"),
    ("科技", "AI 以外的科技：手机数码、汽车、航天、芯片、机器人、互联网产品"),
    ("商业创业", "创业、做生意、商业模式、营销、经营管理、副业赚钱"),
    ("财经投资", "经济、金融、投资理财、股市、房产、消费和财富"),
    ("职场", "求职、工作方法、升职加薪、带团队、职业规划"),
    ("个人成长", "认知、思维方式、学习方法、效率、自律、读书、人生选择"),
    ("内容创作", "短视频、自媒体、写作、个人品牌、直播、做账号"),
    ("法律", "法律知识、法律案例、维权、律师说法"),
    ("时事社会", "新闻热点、社会现象、国际局势、政策"),
    ("历史人文", "历史、哲学、文化、文学艺术、社科"),
    ("心理情感", "心理学、情绪、人际关系、婚恋、家庭"),
    ("健康", "身体健康、医学、饮食营养、运动健身"),
    ("教育学习", "英语和外语、考试、孩子教育、某门课的知识讲解"),
    ("生活娱乐", "生活技巧、美食、旅行、搞笑、影视、游戏"),
    (OTHER, "实在归不进上面任何一类的"),
]
# 模型偶尔不按名字写：常见说法 → 分类名
_ALIAS = {
    "人工智能": "AI", "AI科技": "AI", "大模型": "AI", "AI工具": "AI", "AIGC": "AI",
    "数码": "科技", "科技数码": "科技", "互联网": "科技", "汽车": "科技", "航天": "科技",
    "商业": "商业创业", "创业": "商业创业", "营销": "商业创业", "经营": "商业创业", "副业": "商业创业",
    "财经": "财经投资", "金融": "财经投资", "投资": "财经投资", "理财": "财经投资", "经济": "财经投资",
    "成长": "个人成长", "认知": "个人成长", "自我提升": "个人成长", "效率": "个人成长", "思维": "个人成长",
    "自媒体": "内容创作", "短视频": "内容创作", "创作": "内容创作", "写作": "内容创作",
    "时事": "时事社会", "社会": "时事社会", "新闻": "时事社会", "国际": "时事社会", "政治": "时事社会",
    "历史": "历史人文", "人文": "历史人文", "哲学": "历史人文", "文化": "历史人文",
    "心理": "心理情感", "情感": "心理情感", "婚恋": "心理情感", "两性": "心理情感",
    "医学": "健康", "养生": "健康", "运动": "健康", "健身": "健康",
    "教育": "教育学习", "英语": "教育学习", "学习": "教育学习", "外语": "教育学习",
    "生活": "生活娱乐", "娱乐": "生活娱乐", "搞笑": "生活娱乐", "美食": "生活娱乐", "旅行": "生活娱乐",
    "法律常识": "法律", "法治": "法律", "职业": "职场", "其他": OTHER,
}
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
    """所有分类名（默认的 + 你自己写的），「其它」放最后。"""
    names = [n for n, _d in DEFAULT_CATS if n != OTHER]
    with _lock:
        custom = list(_read(_cfg_file()).get("custom") or [])
    for c in custom:
        c = _clean_cat(c)
        if c and c not in names and c != OTHER:
            names.append(c)
    names.append(OTHER)
    return names


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

def note_labels():
    with _lock:
        return _read(_note_file())


def author_labels():
    with _lock:
        return _read(_author_file())


def public_authors():
    """给界面用：判断出领域的作者 {名字: {dom, dir, why, src, by}}。"""
    out = {}
    for k, v in author_labels().items():
        if isinstance(v, dict) and v.get("dom"):
            out[k] = {x: v.get(x, "") for x in ("dom", "dir", "why", "src", "by")}
    return out


def set_note(name, cat, by="you", kw=None):
    """给一篇文章定分类。by="ai" 时不覆盖你手动定的。cat 为空 = 清掉。返回是否写了。"""
    name = (name or "").strip()
    if not name:
        return False
    cat = _clean_cat(cat)
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
            k = kw if kw is not None else old.get("kw")       # 关键词说的是内容，改分类时留着
            if k:
                e["kw"] = list(k)[:3]
            d[name] = e
        _write(_note_file(), d)
    if cat and by == "you":
        add_cat(cat)
    return True


def set_author(key, dom, by="you", **extra):
    """给作者定领域。by="ai" 时不覆盖你手动定的。dom 为空 = 清掉。"""
    key = (key or "").strip()
    if not key:
        return False
    dom = _clean_cat(dom)
    with _lock:
        d = dict(_read(_author_file()))
        old = d.get(key) or {}
        if by == "ai" and old.get("by") == "you":
            return False
        if not dom:
            d.pop(key, None)
        else:
            e = {"dom": dom, "by": by, "at": int(time.time())}
            if by == "ai":
                for k in ("dir", "why", "src"):
                    if extra.get(k):
                        e[k] = str(extra[k])[:120]
            d[key] = e
        _write(_author_file(), d)
    if dom and by == "you":
        add_cat(dom)
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
    return {"name": name, "title": title, "author": author, "url": url, "tags": tags,
            "analyzed": analyzed, "summary": _summary(txt) if analyzed else ""}


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


def _note_prompt(batch):
    rows = []
    for i, n in enumerate(batch, 1):
        parts = ["标题：" + _short(n["title"], 90)]
        if n.get("tags"):
            parts.append("标签：" + "、".join(n["tags"][:6]))
        if n.get("summary"):
            parts.append("概括：" + n["summary"])
        rows.append("%d. %s" % (i, "｜".join(parts)))
    return ("你是内容分类助手。下面是我收藏的 %d 篇笔记，请给每篇分一个类，再写 2 个关键词。\n\n"
            "分类只能从下面选一个（只写分类名，不要写说明）：\n%s\n\n"
            "要求：\n"
            "① 每篇只输出一行，格式：编号. 分类｜关键词1、关键词2\n"
            "② 关键词 2～6 个字，说清楚这篇具体讲什么；不要写作者名、账号名、平台活动名（比如“抖音精选”“抖来学法”）\n"
            "③ 按这篇的内容本身分类，不按作者分类；实在归不进任何一类才写“%s”\n"
            "④ 不要解释，不要输出别的内容\n\n"
            "示例输出：\n1. 财经投资｜信用卡、消费陷阱\n2. AI｜AI 编程、Agent\n\n"
            "笔记：\n%s\n" % (len(batch), _cat_lines(), OTHER, "\n".join(rows)))


_LINE_RE = re.compile(r"^\s*(\d{1,3})\s*[\.\)、:：．]\s*(.+?)\s*$")


def _clean_kws(s, avoid=()):
    out = []
    for k in re.split(r"[、,，/;；]+", s or ""):
        k = k.strip().strip("#＃“”\"'《》「」()（）[]【】.。·:：*").strip()
        if not k or len(k) > 10 or k in out:
            continue
        if any(a and (k == a or k in a) for a in avoid):
            continue
        out.append(k)
        if len(out) >= 2:
            break
    return out


def _parse_note_reply(raw, batch, lenient=False):
    """lenient=True（第二遍）：AI 坚持写了分类表里没有的类，就归到「其它」。"""
    names = cats()
    out = {}
    for ln in (raw or "").splitlines():
        ln = ln.strip().strip("*").strip()
        m = _LINE_RE.match(ln)
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if not (0 <= idx < len(batch)) or idx in out:
            continue
        parts = re.split(r"[｜|]", m.group(2), maxsplit=1)
        cat = normalize_cat(re.sub(r"^分类\s*[:：]?", "", parts[0]), names)
        if not cat and lenient and _clean_cat(parts[0]):
            cat = OTHER
        if not cat:
            continue
        kw = _clean_kws(parts[1] if len(parts) > 1 else "", avoid=(cat, batch[idx].get("author") or ""))
        out[idx] = (cat, kw)
    return out


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
_NOTE_BATCH = {"local": 12, "pool": 40}
_HOME_OFF_AFTER = 5            # 连着这么多位作者的主页都读不到 → 这一轮后面的只用库里的笔记判断
_NET_PAUSE = 3                 # 读完一位作者的主页，歇几秒再读下一位（免得被平台风控）


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
            return True
        _job.update({"running": True, "stop": False, "auto": bool(auto), "phase": "", "mode": "",
                     "n_total": 0, "n_done": 0, "n_ok": 0, "n_fail": 0,
                     "a_total": 0, "a_done": 0, "a_ok": 0, "a_fail": 0, "a_local": 0, "a_cur": "", "a_stage": "",
                     "started": time.time(), "finished": 0, "summary": "", "err": ""})
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


def _do_notes(todo, bs):
    """一批一批分类。AI 连着 3 次没回话 / 格式不对 → 抛异常停下。"""
    pending, second, consec = list(todo), [], 0
    retried, lenient = set(), False
    while (pending or second) and not _job["stop"]:
        if not pending:
            pending, second = second, []
            bs, lenient = max(4, bs // 2), True
        batch, pending = pending[:bs], pending[bs:]
        try:
            raw = _llm(_note_prompt(batch))
            got = _parse_note_reply(raw, batch, lenient=lenient)
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
            _log("文章分类这一批 AI 回的格式不对：%s" % _short(raw, 80))
            if consec >= 3:
                raise RuntimeError("AI 连着 3 次回的格式不对，认不出分类")
            pending = batch + pending
            continue
        consec = 0
        for i, n in enumerate(batch):
            if i in got:
                cat, kw = got[i]
                set_note(n["name"], cat, by="ai", kw=kw)
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
            if full:
                todo = [n for n in notes if n["analyzed"] and not (lab.get(n["name"]) or {}).get("cat")]
            else:
                todo = [n for n in notes if n["name"] in qs and n["analyzed"]
                        and (lab.get(n["name"]) or {}).get("by") != "you"]
            if todo:
                with _lock:
                    _job["n_total"] += len(todo)
                    _job["phase"] = "notes"
                _log("开始给 %d 篇文章分类（%s）" % (len(todo), "本地模型" if mode == "local" else "AI 池"))
                _do_notes(todo, _NOTE_BATCH.get(mode, 12))
            if _job["stop"]:
                break
            # ② 作者领域
            by_author = {}
            for n in notes:
                if n["author"]:
                    by_author.setdefault(n["author"], []).append(n)
            alab = author_labels()
            now = time.time()
            cand = []
            if full:
                cand = [a for a in by_author if not (alab.get(a) or {}).get("dom")]
            for a in q_auth:
                if a in by_author and a not in cand:
                    cand.append(a)
            for n in notes:
                a = n["author"]
                if n["name"] in qs and a and a not in cand:
                    e = alab.get(a) or {}
                    if not e.get("dom") and not (e.get("tried_at") and now - e["tried_at"] < 86400):
                        cand.append(a)
            cand.sort(key=lambda a: -len(by_author.get(a) or []))   # 笔记多的作者先判断
            if cand:
                with _lock:
                    _job["a_total"] += len(cand)
                    _job["phase"] = "authors"
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
        if not _job["auto"]:
            _log(s or ("没贴完：" + _job["err"]))
