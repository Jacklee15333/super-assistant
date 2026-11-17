"""
prompt_utils.py — 提示词精简 / 上下文裁剪的公共工具（agent_core 与 web_model_client 共用）。

为什么需要它（2026-11 提示词体检的结论）：
  · 系统提示把所有记忆文件原样拼进去，常常 7~13k 字：模板占位、重复记忆、与当前任务无关的
    技能小节、AI 自己写的泛泛分析报告……本地小模型（qwen3:14b 等）上下文有限，塞太多会把
    真正重要的设定和用户最新的话挤掉。
  · 对话历史无限增长，裁剪时又会把「用户刚说的话」或「上一条提问」丢掉，模型就答非所问。
这里的函数只做「取舍和压缩」，不改任何记忆文件本身。
"""

import re

# 请求里出现这些词，才带上 AGENTS.md 里对应的专项小节
INTEL_KW = re.compile(r"视频|链接|抖音|快手|小红书|b站|youtube|http|调研|评论|痛点|文案|广告|竞品|简报|情报|爬|抓取",
                      re.I)
ENGLISH_KW = re.compile(r"英语|英文|单词|学生|教材|语法|听写|作业|辅导|unit", re.I)
INSIGHT_KW = re.compile(r"洞察|成长|复盘|画像|我的(内容|视频|笔记|方向)|规划|方向|赚钱|副业|创业|建议我|了解我",
                        re.I)

_SECTION_RE = re.compile(r"(?m)^(===\s*.+?\s*===)\s*$")


def truncate(s, n, marker="…"):
    s = s or ""
    return s if len(s) <= n else s[:n] + marker


def strip_think(text):
    """去掉思考型模型（qwen3、deepseek-r1 等）输出里的 <think>…</think>。"""
    if not isinstance(text, str) or "<think" not in text:
        return text
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    t = re.sub(r"^.*?</think>", "", t, flags=re.S)       # 只有结束标记的情况
    return t.strip()


def split_sections(text):
    """按「=== 标题 ===」切块，返回 (前言, [(标题行, 正文), ...])。"""
    parts = _SECTION_RE.split(text or "")
    head = parts[0].strip()
    secs = [(parts[i].strip(), (parts[i + 1] if i + 1 < len(parts) else "").strip())
            for i in range(1, len(parts), 2)]
    return head, secs


def clean_soul(body):
    lines = [l for l in (body or "").splitlines()
             if "改这个文件" not in l and not re.match(r"^#\s", l)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)
                  .replace("（你可以改成任何你喜欢的名字）", "")).strip()


def compact_agents(body, request="", unattended=False):
    """AGENTS.md 按「## 小节」取舍。
    · 心跳小节只在无人值守（心跳/定时任务）时需要；
    · 市场情报、英语辅导这类专项小节，只在请求相关时带上（request 为空＝不知道，就都带）；
    · 「危险操作先告诉你、得到确认再做」和弹窗机制冲突，改成弹窗表述。"""
    req = request or ""
    out = []
    for sec in re.split(r"(?m)^(?=## )", body or ""):
        first = sec.split("\n", 1)[0]
        if not first.startswith("## "):
            sec = "\n".join(l for l in sec.splitlines()
                            if l.strip() and not l.startswith("#") and "随时编辑" not in l)
            if sec.strip():
                out.append(sec.strip())
            continue
        if "心跳" in first and not unattended:
            continue
        if req:
            if ("高级技能" in first or "红线" in first or "情报" in first) and not INTEL_KW.search(req):
                continue
            if "英语" in first and not ENGLISH_KW.search(req):
                continue
        if unattended:
            repl = "2. **危险操作不做**：现在没人能确认，这类操作会被自动拦下，在回复里说明即可。"
        else:
            repl = "2. **危险操作先确认**：直接调用工具，程序会弹窗让用户批准。"
        sec = re.sub(r"(?m)^.*危险操作先确认.*$", repl, sec)
        out.append(sec.strip())
    return "\n\n".join(out)


def strip_template(body):
    """去掉模板占位行（「（还不了解…）」「- 」「我会把…」），只剩标题时返回空。"""
    keep = []
    for l in (body or "").splitlines():
        t = l.strip()
        if not t or t == "-" or re.fullmatch(r"（[^）]*）", t) or t.startswith("我会把") \
                or t.startswith("> "):
            continue
        keep.append(l)
    return "\n".join(keep) if any(not l.lstrip().startswith("#") for l in keep) else ""


def dedupe_lines(body):
    """去掉重复的记忆条目（忽略日期、空白和标点的差异）。"""
    seen, out = set(), []
    for l in (body or "").splitlines():
        key = re.sub(r"[（(]\d{4}-\d{2}-\d{2}[）)]|\s|[，。、；,.;]", "", l)
        if key and not key.startswith("#") and key in seen:
            continue
        seen.add(key)
        out.append(l)
    return "\n".join(out)


def pick_md_sections(body, wanted, cap):
    """从 Markdown 里只挑标题含 wanted 关键词的「## 小节」。"""
    got = []
    for sec in re.split(r"(?m)^(?=## )", body or ""):
        first = sec.split("\n", 1)[0]
        if first.startswith("## ") and any(w in first for w in wanted):
            got.append(sec.strip())
    return truncate("\n\n".join(got), cap)


def compact_lumi(block, request=""):
    """「懂你」四件套精简：画像只留说话风格/偏好习惯（去掉 AI 写给自己的「主动做什么」清单），
    环境只留硬件系统信息，洞察报告只在相关话题时带上。"""
    _, secs = split_sections(block)
    out = []
    for title, body in secs:
        if "OWNER_PROFILE" in title:
            body = pick_md_sections(body, ("说话风格", "偏好与习惯"), 700)
        elif "ENVIRONMENT" in title:
            body = pick_md_sections(body, ("环境信息",), 400) or truncate(body, 400)
        elif "INSIGHT" in title:
            if not (request and INSIGHT_KW.search(request)):
                continue
            body = truncate(body, 1200)
        else:
            body = truncate(body, 800)
        if body.strip():
            out.append(title + "\n" + body.strip())
    return "\n\n".join(out)


def compact_skills(block):
    lines = []
    for l in (block or "").splitlines():
        m = re.match(r"^- 「(.+?)」\(slug: ([\w-]+)\)：(.*)$", l.strip())
        if m:
            desc = re.split(r"[。！；]", m.group(3), 1)[0]
            lines.append("- %s（%s）：%s" % (m.group(1), m.group(2), truncate(desc, 40)))
    if not lines:
        return ""
    return ("=== 你的技能库（Skills）===\n"
            "任务匹配某个技能时，先用 load_skill 读入它的完整步骤再做；不匹配就正常处理。\n"
            + "\n".join(lines))


# ───────────────────────── 对话历史裁剪 ─────────────────────────
def _content_len(m):
    c = m.get("content")
    if isinstance(c, list):
        c = "".join(b.get("text", "") for b in c if isinstance(b, dict))
    n = len(c or "")
    for tc in (m.get("tool_calls") or []):
        n += len(str(((tc or {}).get("function") or {}).get("arguments") or ""))
    return n


def _shrink_tool(m, cap):
    c = m.get("content")
    if m.get("role") == "tool" and isinstance(c, str) and len(c) > cap:
        m = dict(m)
        m["content"] = c[:cap] + "\n…（较早的工具输出已截短）"
    return m


def fit_messages(messages, max_chars, old_tool_cap=1500):
    """把对话裁到 max_chars 以内，规则：
      · system 保留；
      · 最新一条用户消息及其后的所有内容（本轮的工具调用和结果）必须保留；
      · 更早的按「一轮」为单位（assistant 的 tool_calls 和它的 tool 结果不拆开）从新往旧补，
        旧的工具输出先截短；装不下的才丢。
    不修改传入的列表；没超限就原样返回。"""
    msgs = list(messages or [])
    if sum(_content_len(m) for m in msgs) <= max_chars:
        return msgs
    sys = msgs[:1] if msgs and msgs[0].get("role") == "system" else []
    rest = msgs[len(sys):]
    units = []
    for m in rest:
        if m.get("role") == "tool" and units:
            units[-1].append(m)
        else:
            units.append([m])
    last_u = max((i for i, u in enumerate(units) if u[0].get("role") == "user"), default=len(units) - 1)
    keep = [m for u in units[last_u:] for m in u]
    budget = max_chars - sum(_content_len(m) for m in sys + keep)
    older = []
    for u in reversed(units[:last_u]):
        u2 = [_shrink_tool(m, old_tool_cap) for m in u]
        size = sum(_content_len(m) for m in u2)
        if size > budget:
            break
        older = u2 + older
        budget -= size
    out = sys + older + keep
    # 开头不能是孤立的 tool 消息
    while len(out) > len(sys) and out[len(sys)].get("role") == "tool":
        out.pop(len(sys))
    return out
