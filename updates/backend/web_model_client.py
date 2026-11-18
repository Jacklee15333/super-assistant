"""
web_model_client.py — 把「伪模型」（网页 ChatGPT）伪装成一个 OpenAI 兼容客户端。

目的：让 server / agent_core / video_tools 里现成的
    client.chat.completions.create(model=..., messages=[...], tools=...)
这一行【完全不改】也能驱动网页 ChatGPT。

两种工作模式，按 create() 收到的 tools 参数自动切换：

  ① 纯文本模式（tools 为空 / 不传）—— 老行为，原样保留。
  ② Agent 模式（收到非空 tools）—— 当「电脑操作权限」开、server 把网页模型引进
     run_agent() 工具循环时触发：把工具清单 + 文字标记协议写进 prompt，让纯文本的
     网页模型也能输出 <<<TOOL>>>{...}<<<END>>> 工具调用块；回复回来后解析出来，
     伪造成 OpenAI 的 tool_calls 返回，于是现成的 run_agent() 循环原样就能跑。

★ 2026-06 修订（防"复述脚手架"）：
  · 思考型网页模型容易把我们喂进去的【当前对话】/【工具执行结果】这类框架原样复述，
    导致内部脚手架文字泄漏到最终回答里（界面上看到一大坨）。
  · 对策一：续跑时只发"增量"（同一网页对话线程已有上文，只补新的工具结果 + 一句简短指令），
    用对话化、口语化的措辞，并明确要求"不要复述上面的格式/标记"，大幅降低复述概率。
  · 对策二：解析回复时再兜底剥掉任何残留的脚手架标记，只留真正的回答。
"""

import re
import json
import uuid
import base64

import web_model

MAX_PROMPT_CHARS = 16000          # 纯文本模式：对话总字数上限（超了只留最近的）
MAX_TOOL_RESULT_CHARS = 6000      # Agent 模式：单条工具结果回灌时的截断长度（够装下目录清单）
_MAX_CONVO_MSGS = 14              # Agent 模式：完整 prompt 里最多保留最近多少条对话
_MAX_CONVO_CHARS = 6000          # Agent 模式：对话渲染的总字数上限（超了从最旧的丢）
_MAX_TAIL_TOOL_CHARS = 2500       # 完整 prompt 里，最新请求之后的单条工具结果上限

# 网页对话线程状态（模块级：server 每个请求都会新建 client，状态必须跨请求保留）
#   sig   = 已发进网页线程的那段对话的指纹（不含 system，因为 system 里有实时时间）
#   sent  = 已发进去的 messages 条数
#   epoch = 发送时网页线程的编号（web_model 换卡/开新对话会变）
_THREAD = {"sig": None, "sent": 0, "epoch": None}

# Agent 模式：开局这一轮若碰到「轴卡」（死活用文字推辞、连命令都不肯写），
# 最多再换几张新卡重抽，直到碰到肯动手（肯写工具块或命令）的卡；都不行就用保底。
# 默认 3（按用户要求：换 3 张不行就保底）。可用环境变量 CX_MAX_CARD_RETRIES 覆盖。
try:
    import os as _os
    _MAX_CARD_RETRIES = max(0, int(_os.environ.get("CX_MAX_CARD_RETRIES", "3")))
except Exception:
    _MAX_CARD_RETRIES = 3

TOOL_OPEN = "<<<TOOL>>>"
TOOL_CLOSE = "<<<END>>>"
_TOOL_RE = re.compile(r"<<<\s*TOOL\s*>>>(.*?)<<<\s*END\s*>>>", re.DOTALL | re.IGNORECASE)

# 代码块 ```lang ... ```（lang 可为 json/JSON/tool/空）。网页模型最常把工具调用
# 误塞进 ```json 代码块里——这里把代码块内容抠出来，交给下面的 JSON 扫描。
_FENCE_RE = re.compile(r"```[ \t]*[a-zA-Z0-9_+-]*[ \t]*\r?\n?(.*?)```", re.DOTALL)
# 带语言标记一起捕获，供「命令块→sys_run」识别用：group(1)=语言，group(2)=正文
_FENCE_LANG_RE = re.compile(
    r"```[ \t]*([a-zA-Z0-9_+#-]*)[ \t]*\r?\n?(.*?)```", re.DOTALL)

# 占位名（协议示例里的假名字），万一被模型复述出来，解析时要忽略
_PLACEHOLDER_NAMES = {"工具名", "tool_name", "toolname", "name", "工具", "示例工具"}


# ════════════════════════ 公共：内容取文本 ════════════════════════
def _text_of(content):
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text")
    return content or ""


def _truncate(s, n):
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n] + ("\n…（输出太长，只显示了前一部分。要拿到完整内容，请改用更精简的命令"
                    "重新获取，例如只列名字 Get-ChildItem 路径 -Name；或把结果写进一个文件再读。"
                    "不要把“被截断”当成最终答案告诉用户。）")


# ════════════════════════ 纯文本模式（老逻辑，原样保留）════════════════════════
def flatten_messages(messages):
    """纯文本模式：把对话压成一段。系统设定精简成纯聊天版（不再让它调用不存在的工具），
    历史太长时只保留最近的（用户最新那条一定在）。"""
    msgs = list(messages or [])
    req = "\n".join(_text_of(m.get("content")) for m in msgs if m.get("role") == "user")[-2000:]
    msgs = _pu.fit_messages(
        [dict(m, content=_compact_system(_text_of(m.get("content")), req, plain=True))
         if m.get("role") == "system" else m for m in msgs],
        MAX_PROMPT_CHARS)
    parts = []
    for m in msgs:
        role = m.get("role", "user")
        content = _text_of(m.get("content", "")).strip()
        if not content or role == "tool":
            continue
        if role == "system":
            parts.append("【角色与要求】\n" + content)
        elif role == "assistant":
            parts.append("（你上一轮的回复）\n" + content)
        else:
            parts.append(content)
    prompt = "\n\n".join(parts)
    prompt += "\n\n请按上面要求作答（没有特别指定语言时用中文）。"
    return prompt


# ════════════════════════ Agent 模式：构造 prompt ════════════════════════
# 网页模型有自带搜索，这些联网工具不列给它（列了反而和「用自带搜索」冲突）
_WEB_HIDE_TOOLS = {"web_search", "research"}
# 电脑操作权限开着时，沙箱版工具和 fs_*/sys_run 重复，只列后者
_SANDBOX_DUP = {"read_file": "fs_read", "list_files": "fs_list", "search_files": "fs_search",
                "delete_file": "fs_trash", "shell": "sys_run"}


def _short_desc(desc, n=48):
    d = re.sub(r"^【[^】]*】", "", (desc or "").strip().replace("\n", " "))
    d = re.sub(r"\*\*", "", d)
    d = re.split(r"[。！；]", d, 1)[0].strip()
    return d[:n] + ("…" if len(d) > n else "")


def _render_tool_catalog(tools):
    """紧凑工具清单：一行一个，描述只取第一句；⚠ = 会弹窗确认。"""
    names = {((t or {}).get("function") or {}).get("name") for t in tools or []}
    lines = []
    for t in tools or []:
        fn = (t or {}).get("function") or {}
        name = fn.get("name")
        if not name or name in _WEB_HIDE_TOOLS:
            continue
        if name in _SANDBOX_DUP and _SANDBOX_DUP[name] in names:
            continue
        raw = fn.get("description") or ""
        danger = "危险" in raw[:40]
        params = (fn.get("parameters") or {}).get("properties") or {}
        required = set((fn.get("parameters") or {}).get("required") or [])
        ps = []
        for pname, spec in params.items():
            spec = spec or {}
            p = pname + ("*" if pname in required else "")
            if spec.get("enum"):
                p += "=" + "/".join(str(x) for x in spec["enum"][:6])
            ps.append(p)
        lines.append("- %s%s(%s)：%s" % ("⚠" if danger else "", name, ", ".join(ps),
                                         _short_desc(raw)))
    return "【可用工具】（* 必填参数；⚠ 会先弹窗让用户批准）\n" + "\n".join(lines)


# ---------- 精简角色设定（只用于网页模型）----------
import prompt_utils as _pu

_PLAIN_NOTE = ("（现在是纯聊天模式：你没有任何工具可调用，直接回答即可；"
               "需要最新信息就用你自带的联网搜索。不要输出工具调用。）")


def _compact_system(system_txt, req="", plain=False):
    """网页模型用的角色设定：在 build_system_prompt 已精简的基础上再按网页场景取舍。
    · 「通用做事规则」换成网页协议里的【做事习惯】（Agent 模式）或一句纯聊天说明（plain）；
    · 分身设定等其它小节原样保留（旧版这里会把分身设定整段切掉）。
    兼容旧格式（尾部是「请严格按以上设定行事…」的老系统提示）。"""
    txt = system_txt or ""
    old_tail = txt.find("请严格按以上设定行事")
    if old_tail >= 0:                         # 老格式：删掉那段尾部规则，保留其后的分身等小节
        nxt = re.search(r"(?m)^===", txt[old_tail:])
        txt = txt[:old_tail] + (txt[old_tail + nxt.start():] if nxt else "")
    head, secs = _pu.split_sections(txt)
    out = [head] if head else []
    for title, body in secs:
        if "通用做事规则" in title:
            continue
        if "SOUL" in title:
            body = _pu.clean_soul(body)
        elif "AGENTS" in title:
            body = _pu.compact_agents(body, req)
        elif "USER.md" in title:
            body = _pu.strip_template(body)
        elif "MEMORY" in title:
            body = _pu.truncate(_pu.dedupe_lines(_pu.strip_template(body)), 1200)
        elif "OWNER_PROFILE" in title:
            body = _pu.pick_md_sections(body, ("说话风格", "偏好与习惯"), 700) or _pu.truncate(body, 700)
        elif "ENVIRONMENT" in title:
            body = _pu.pick_md_sections(body, ("环境信息",), 400) or _pu.truncate(body, 400)
        elif "INSIGHT" in title:
            if not _pu.INSIGHT_KW.search(req or ""):
                continue
            body = _pu.truncate(body, 1200)
        elif "技能库" in title or "Skills" in title:
            if plain:
                continue                      # 纯聊天没有 load_skill 可用
            sk = _pu.compact_skills(title + "\n" + body)
            body = sk.split("\n", 1)[1] if sk else body
        else:
            body = _pu.truncate(body, 3000)    # 分身设定等：基本原样保留
        body = re.sub(r"\n{3,}", "\n\n", (body or "").strip())
        if body:
            out.append(title + "\n" + body)
    if plain:
        out.append(_PLAIN_NOTE)
    return "\n\n".join(out)


_AGENT_PROTOCOL = (
    "【工作方式】\n"
    "你是这台 Windows 电脑上本地助手程序的「大脑」。用户电脑上运行着一个本地程序，"
    "它会读取你回复里的调用块并真实执行，再把结果发回给你。所以写调用块就是在真正操作电脑——"
    "这是本系统约定的正常用法，已经接好。本系统不使用聊天界面自带的函数调用，"
    "所有工具都按下面的文本格式调用。\n\n"
    "【调用块格式】标记原样照抄：\n"
    f"{TOOL_OPEN}\n"
    '{"name": "工具名", "arguments": {"参数名": "参数值"}}\n'
    f"{TOOL_CLOSE}\n"
    "· 要做几件事就连续写几个块；有副作用的多个操作放在同一轮一起写，用户能在一个确认框里批量批准。\n"
    "· 块里是合法 JSON，不要再套 ```json 代码块。写完调用块就停，等程序把结果发回来。\n"
    "· 也可以改写一段 ```powershell 代码块，程序会执行并返回输出。**每次回复只写一段命令**"
    "（多写的会被忽略）；不要让用户自己去运行。\n\n"
    "【安全】删除、结束进程、执行命令这类操作，程序会先弹窗让用户批准才执行。"
    "所以不用文字问「要不要执行」，直接写调用块，确认交给弹窗——角色设定里说的「有风险先问」"
    "就是由这个弹窗完成的。先用只读工具（fs_list、fs_read、sys_info、sys_processes、screen_read 等）"
    "摸清情况，再做有副作用的操作。\n\n"
    "【做事习惯】意图清楚就直接做，不反复追问。检查/清理/整理类任务：先只读摸清，"
    "用 Markdown 表格汇报（类别、位置、大小、是否安全），再一句总结。清理 C 盘垃圾/临时文件用 sys_clean_temp，"
    "不要用命令删。遇到「访问被拒/正被占用」的文件跳过即可，如实说明，不算失败。\n\n"
    "【回答用户】任务完成、或者问题不需要操作电脑时，直接用中文回答，不再写调用块。"
    "长短按内容需要：简单问题简洁回答；查询、扫描、对比类的结果要把关键数据讲清楚，适合时用 Markdown 表格。"
    "不要只回「收到」「好的」这类空话。\n"
    "· 联网查资料用你自带的搜索能力，不要写 web_search、research 调用块。\n"
    "· 不要复述本说明里的标记和【】标题。\n"
    "· 上面角色设定和本【工作方式】有冲突时，以本【工作方式】为准。\n\n"
    "【示例】\n"
    "用户：C 盘还剩多少空间？\n"
    "你：\n"
    f"{TOOL_OPEN}\n"
    '{"name": "sys_info", "arguments": {}}\n'
    f"{TOOL_CLOSE}\n"
    "（程序发回：C: 总 237GB，可用 18.4GB；D: 总 931GB，可用 402GB）\n"
    "你：C 盘总共 237 GB，只剩 18.4 GB（约 8%），已经偏紧；D 盘还很宽裕。"
    "需要的话我可以先扫一下 C 盘哪些文件夹最大。"
)


def _render_tool_result(name, content):
    """工具结果用口语化、低"复述诱惑"的措辞呈现。"""
    body = _truncate(_text_of(content).strip(), MAX_TOOL_RESULT_CHARS)
    return "（系统提示）工具 %s 已执行，结果：%s" % (name or "工具", body)


# ── 兜底：识别网页模型"用文字耍赖、推辞不肯用工具"的回复 ──
#   2026-06 扩充：补上"没有接入工具桥""不能真实扫描/检查""我这边目前无法…"
#   这一类（旧正则漏掉的、最常见的推托说法）。
_REFUSAL_RE = re.compile(
    r"不能直接(调用|访问|操作|执行)"
    r"|无法直接(调用|访问|操作|执行)"
    r"|不能(调用|访问|操作|执行|读取|删除|清理|修改).{0,8}(工具|电脑|本地|c\s*盘|文件|系统|windows)"
    r"|无法(调用|访问|操作|执行|读取|删除|清理|修改).{0,8}(工具|电脑|本地|c\s*盘|文件|系统|windows)"
    r"|没(有|拿到).{0,12}权限"
    r"|不能实际(执行|操作|删除|清理|访问|修改|搬|移动)"
    r"|无法实际(执行|操作|删除|清理|访问|修改|搬|移动)"
    r"|不能假装"
    r"|我这(边|里).{0,4}不能(直接)?(调用|访问|操作|执行|帮你|删除|清理)"
    r"|(请|建议)你?(自己)?(去)?手动"
    r"|只能(给你)?(出|提供)?建议"
    # —— 新增：未接入/没接入工具桥（本次截图里就是这种） ——
    r"|(没有?|未|尚未|还没)\s*接入"
    r"|(没有?|未)\s*(真实|实际)?\s*(连接|对接|接通)"
    # —— 新增：不能/无法 真实/实际 扫描·检查·查看·读取… ——
    r"|(不能|无法)\s*(真实|实际)?\s*(扫描|检查|查看|读取|访问|清理|删除|操作|查)"
    # —— 新增：我这边/目前/暂时 + 没有/无法/不能 + 工具/能力/接口/环境 ——
    r"|(我)?(这边|这里|目前|暂时|当前)\s*(没有?|无法|不能|尚未)\s*.{0,14}(工具|桥|能力|接口|环境|权限|连接|访问|操作|执行)"
    # —— 新增：叫用户自己在本机/本地执行（变相推辞） ——
    r"|你可以(在)?(本机|本地|这台|电脑上)?\s*.{0,6}(执行|运行)"
    r"|(请|建议)你?(在|去)?(本机|本地|这台电脑)?\s*(里)?(执行|运行|操作)"
    r"|没有?\s*(真实|实际)的?\s*(工具|权限|连接|接口|能力|环境|桥)"
    # —— 新增（2026-06·二轮）：模型这次实际用的几种"讲原则式"推辞 ——
    r"|不能伪造"                                   # “我不能伪造 <<<TOOL>>> 块”
    r"|没(有)?\s*.{0,6}注册"                       # “聊天环境里没有注册 xx 工具”
    r"|需要(先)?\s*接入"                            # “需要接入对应工具”
    r"|接入.{0,10}(才能|后才|之后才|才可以|我才能)\s*(调用|使用|操作)"
    r"|(才能|方可|后才|之后才)\s*(调用|使用|操作)\b"
    r"|只(能|可)\s*(基于|根据|靠)?.{0,12}(分析|结果|信息你?提供)"
    r"|只(能|可)\s*.{0,4}(分析|建议)"
    r"|(工具|功能)\s*只在.{0,12}(界面|列表|面板)"
    r"|当前\s*(界面|工具列表|工具面板).{0,10}(显示|里|中|的)"
    r"|工具列表里"
    # —— 新增（2026-06·三轮）：模型坚称“协议不会被执行 / 不当成真实操作 / 你把结果贴回来” ——
    r"|(协议|调用|这套|这个).{0,8}(不会|无法|不能).{0,4}(被)?执行"
    r"|不(会|能)\s*(被)?\s*(真实|实际)?\s*执行"
    r"|不能.{0,6}当成.{0,4}真实"
    r"|不(会|能).{0,4}当成.{0,6}(操作|执行|调用)"
    r"|(把|将).{0,16}(结果|返回|输出|内容).{0,6}(贴|发|粘).{0,4}(回来|给我|过来|上来)"
    r"|(贴|发|粘).{0,4}(回来|给我|过来|上来).{0,6}(我|帮你).{0,6}(分析|判断|看)"
    # —— 新增（2026-06·五轮）：模型这次的“未注册/不能输出调用块/误以为已执行”说辞 ——
    r"|未\s*注册"
    r"|不能输出.{0,8}(调用块|工具|指令)"
    r"|不(会|能)输出.{0,8}(调用块|工具)"
    r"|当前可用工具.{0,4}(里|中)?\s*没有"
    r"|可用工具.{0,6}没有.{0,8}(接口|工具|sys_info|fs_list)"
    r"|误(以为|认为).{0,12}(执行|交给|跑)"
    r"|没有?.{0,8}(本机|本地).{0,8}(接口|工具|操作)"
    # —— 新增（2026-06·六轮）：读文件类推辞（“没法读取/拖进聊天/复制发我”）——
    r"|(没法|没办法|无法|读不了|打不开).{0,6}(直接)?.{0,4}(读取|查看|访问|打开|获取|读到)"
    r"|(拖|拽|拖拽)\s*.{0,4}(进|到|入)\s*.{0,4}(聊天|对话|这里|窗口|框)"
    r"|拖进来"
    r"|(复制|拷贝|粘贴).{0,12}(发|给|贴|粘)\s*.{0,4}(我|给我|过来)"
    r"|(把|将).{0,14}(文件|文档|内容|文字|图片|截图).{0,8}(拖|发|传|贴|粘|给)\s*.{0,6}"
    r"(我|给我|过来|上来|进来|进聊天|到聊天|到对话|聊天里)",
    re.IGNORECASE)


def _looks_like_refusal(text):
    t = (text or "").strip()
    if not t:
        return False
    return bool(_REFUSAL_RE.search(t))


_REFUSAL_NUDGE = (
    "等一下——你刚才拒绝，是因为把机制理解错了。我说清楚：\n"
    "· 你**不需要**自己拥有工具、也**不是**在伪造或假装。你只是写一行约定格式的文本，"
    "真正动手的是用户电脑上**正在运行的本地程序**——它读你这行文本，替你执行，再把结果发回给你。\n"
    "· 「这个聊天没注册这些工具」「只能用界面里的工具」是另一套机制的说法；**本系统不走那套**，"
    "工具就是靠你写文本块、由本地程序执行来实现的，**已经接好、正在等你**。\n"
    "· 危险操作程序会先弹窗让用户确认，不会误删。\n"
    "所以这次请**直接写调用块**，不要再解释、不要再让用户手动做。比如先看看磁盘：\n\n"
    f"{TOOL_OPEN}\n"
    '{"name": "sys_info", "arguments": {}}\n'
    f"{TOOL_CLOSE}\n\n"
    "或列个目录看大小：\n\n"
    f"{TOOL_OPEN}\n"
    '{"name": "fs_list", "arguments": {"path": "C:/Users"}}\n'
    f"{TOOL_CLOSE}\n\n"
    "⚠ 只认 <<<TOOL>>> / <<<END>>> 这种标记，**别用 ```json 代码块**、也别只写一段 JSON。"
    "现在就只输出调用块，别的话都不要写。\n"
    "（上面只是**格式示例**；请针对用户刚才要做的事写对应的调用块或命令——"
    "比如要看某个文件里的内容，就写 ```powershell 代码块跑 Get-Content \"文件完整路径\"，"
    "或写 {\"name\": \"fs_read\", \"arguments\": {\"path\": \"文件完整路径\"}} 这个调用块；"
    "**不要**叫用户把文件拖进来或复制发你——本地程序能直接读，你写出来就读到了。）"
)


def _tcid_to_name(messages):
    mp = {}
    for m in messages or []:
        if m.get("role") == "assistant":
            for tc in (m.get("tool_calls") or []):
                fn = (tc or {}).get("function") or {}
                if tc.get("id"):
                    mp[tc.get("id")] = fn.get("name") or "工具"
    return mp


def _build_full_prompt(messages, tools):
    """新线程首发：角色 + 工作方式 + 工具清单 + 对话（保证最新的用户请求一定在）+ 明确的收尾指令。"""
    msgs = messages or []
    mp = _tcid_to_name(msgs)
    system_txt = "\n\n".join(
        _text_of(m.get("content")).strip()
        for m in msgs if m.get("role") == "system" and _text_of(m.get("content")).strip())

    items = []          # (kind, text)
    for m in msgs:
        role = m.get("role")
        if role == "user":
            t = _text_of(m.get("content")).strip()
            if t:
                items.append(("user", "用户：" + t))
        elif role == "assistant":
            t = _text_of(m.get("content")).strip()
            if t:
                items.append(("assistant", "你：" + t))
        elif role == "tool":
            name = mp.get(m.get("tool_call_id"), "工具")
            items.append(("tool", _render_tool_result(name, m.get("content"))))

    # ★ 最新一条用户请求及其后的工具结果必须保留（旧逻辑会因为一条长工具结果把请求本身挤掉）
    last_u = max((i for i, (k, _) in enumerate(items) if k == "user"), default=None)
    head = items[:last_u] if last_u is not None else items[:-1]
    tail = items[last_u:] if last_u is not None else items[-1:]
    tail = [(k, _truncate(t, _MAX_TAIL_TOOL_CHARS) if k == "tool" else t) for k, t in tail]
    budget = max(0, _MAX_CONVO_CHARS - sum(len(t) for _, t in tail))
    kept = []
    for k, t in reversed(head):
        if len(kept) + len(tail) >= _MAX_CONVO_MSGS:
            break
        if len(t) > budget:
            if not kept:
                # ★ 紧挨着最新请求的那条（常是「要我执行吗？」）再长也要留，截取结尾部分——
                #   否则用户只回一个「是」，模型就不知道在确认什么
                room = max(budget, 800)
                kept.insert(0, (k, t[:2] + "…" + t[-room:] if len(t) > room else t))
            break
        kept.insert(0, (k, t))
        budget -= len(t)
    # 被挤掉的部分里如果有用户之前的请求，至少把最近那条带上（让模型知道任务的来龙去脉）
    if len(kept) < len(head) and not any(k == "user" for k, _ in kept):
        prev_u = next(((k, t) for k, t in reversed(head[:len(head) - len(kept)]) if k == "user"), None)
        if prev_u:
            kept.insert(0, (prev_u[0], _pu.truncate(prev_u[1], 400)))
    convo = [t for _, t in kept + tail]
    if len(kept) < len(head):
        convo.insert(0, "（更早的对话已省略，只保留最近的上下文）")

    latest = tail[0][1][len("用户："):] if tail and tail[0][0] == "user" else ""
    if latest and any(k == "tool" for k, _ in tail):
        final = ("【现在】上面是针对用户最新请求已经执行的工具结果。请据此继续："
                 "还需要操作就写调用块；做完了就用中文把结果告诉用户。")
    elif latest and len(latest) <= 12 and kept and kept[-1][0] == "assistant":
        final = ("【现在】用户回复「%s」——这是在回应你上一条消息里的提问/提议。"
                 "请按你上一条说的去做（需要操作就直接写调用块）。" % latest)
    elif latest:
        final = "【现在】请处理用户最新的这条消息：" + _truncate(latest, 600)
    else:
        final = "【现在】请接着处理上面的对话。"

    chunks = ["（这是一条合并消息：前面是你的设定和工具说明，最后是对话和你现在要做的事。）"]
    req = "\n".join(_text_of(m.get("content")) for m in msgs if m.get("role") == "user")[-2000:]
    system_txt = _compact_system(system_txt, req)
    if system_txt.strip():
        chunks.append("【你的角色】\n" + system_txt)
    chunks.append(_AGENT_PROTOCOL)
    chunks.append(_render_tool_catalog(tools))
    chunks.append("【对话】\n" + "\n".join(convo))
    chunks.append(final)
    return "\n\n".join(chunks)


def _build_incremental_prompt(new_messages):
    """续跑：网页对话线程里已有上文，只补"新发生的事"+ 一句简短指令。"""
    mp_local = {}  # 这批里如果有 assistant tool_calls，给结果配名字
    for m in new_messages:
        if m.get("role") == "assistant":
            for tc in (m.get("tool_calls") or []):
                fn = (tc or {}).get("function") or {}
                if tc.get("id"):
                    mp_local[tc.get("id")] = fn.get("name") or "工具"

    lines = []
    for m in new_messages:
        role = m.get("role")
        if role == "tool":
            name = mp_local.get(m.get("tool_call_id"), "工具")
            lines.append(_render_tool_result(name, m.get("content")))
        elif role == "user":
            t = _text_of(m.get("content")).strip()
            if t:
                lines.append("用户又说：" + t)
        # assistant 的内容/工具请求不回灌（同线程它自己刚说过）
    body = "\n".join(lines) if lines else "（无新增信息）"
    if any(m.get("role") == "user" for m in new_messages):
        tail = "\n\n请处理用户这条新消息（需要操作电脑就写调用块，否则直接用中文回答）。"
    else:
        tail = ("\n\n请据此继续：还需要操作就写调用块；做完了就用中文把结果告诉用户，"
                "关键数据讲清楚，长短按需要。")
    return body + tail


# ════════════════════════ Agent 模式：解析回复 ════════════════════════
def _fix_json(s):
    return re.sub(r",\s*([}\]])", r"\1", s or "")


def _tolerant_json(raw):
    s = (raw or "").strip()
    s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    i, j = s.find("{"), s.rfind("}")
    if i != -1 and j != -1 and j > i:
        s = s[i:j + 1]
    for cand in (s, _fix_json(s)):
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def _iter_json_objects(text):
    """在任意文本里扫描出一段段「括号配平」的 {...} JSON 对象，按出现顺序产出
    (start, end, 子串)。能正确跳过字符串内部的引号和花括号。
    用来兜底：模型没用标记、也没用代码块，只甩了一段（或几段）JSON 时也能捞出来。"""
    s = text or ""
    n = len(s)
    i = 0
    while i < n:
        if s[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        quote = ""
        j = i
        while j < n:
            ch = s[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    in_str = False
            else:
                if ch == '"' or ch == "'":
                    in_str = True
                    quote = ch
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        yield (i, j + 1, s[i:j + 1])
                        break
            j += 1
        i = (j + 1) if j > i else (i + 1)


def _as_tool_call(data, known_names, require_known):
    """把一个 dict 尝试解释成工具调用；不像就返回 None。
    require_known=True 时，只有 name 在「真实工具名单」里才认（防止把回答里
    顺手写的示例 JSON 误当成调用）。<<<TOOL>>> 块内是明确意图，可放宽。"""
    if not isinstance(data, dict):
        return None
    name = data.get("name") or data.get("tool") or data.get("tool_name")
    if not name or not isinstance(name, str):
        return None
    name = name.strip()
    if not name or name in _PLACEHOLDER_NAMES:
        return None
    if require_known and known_names is not None and name not in known_names:
        return None
    args = data.get("arguments")
    if args is None:
        args = data.get("args")
    if args is None:
        args = data.get("parameters")
    if isinstance(args, str):
        parsed = _tolerant_json(args)
        args = parsed if isinstance(parsed, dict) else {}
    if not isinstance(args, dict):
        args = {}
    return _ToolCall(name, args)


# 续跑/首发提示里可能出现、若被模型复述需要剥掉的脚手架标记（按行匹配）
_SCAFFOLD_LINE_PATTERNS = [
    r"^【你的角色】", r"^【角色与要求】", r"^【当前对话】", r"^【用户】",
    r"^【工具",                                   # 【工具「xxx」的执行结果】
    r"^可用工具(清单)?(（.*?）)?[:：]?$",
    r"^- \w+\(.*?\)[:：]",                       # 工具清单的条目
    r"^你现在是一个能操作", r"^你前面看到的任何", r"^你操作电脑的",
    r"^规则[:：]?$", r"^\d+\.\s",                  # 协议里的编号规则
    r"^⚠", r"^非常重要", r"^绝对不要复述",
    r"^（系统提示）", r"^（系统）", r"^（你上一步",
    r"^下面是你和用户的对话", r"^如果任务已", r"^如果还需要",
    r"^请接着", r"^请继续", r"^请根据",
    r"^用户又说[:：]", r"^用户[:：]", r"^你[:：]",
    r"^<<<\s*(TOOL|END)\s*>>>",
    r"^={3,}", r"^━{3,}", r"^-{3,}$",
]
_SCAFFOLD_RE = re.compile("|".join("(?:%s)" % p for p in _SCAFFOLD_LINE_PATTERNS))


def _strip_scaffold_echo(text):
    """兜底：剥掉模型可能复述出来的脚手架标记行，只留真正的回答。"""
    t = (text or "").strip()
    if not t:
        return t
    lines = t.splitlines()
    kept = [ln for ln in lines if not _SCAFFOLD_RE.search(ln.strip())]
    out = "\n".join(kept).strip()
    # 收掉多余空行
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


# ════════════════════════ 命令块 → sys_run（顺着模型脾气来）════════════════════════
# 现实：有的网页模型死活不肯写 <<<TOOL>>> 块（觉得是“伪造工具”），却很乐意写
# PowerShell / cmd 命令。于是这里把它写的命令块抠出来，包装成 sys_run 调用，由本地
# 执行器真正在用户机器上跑（仍走危险确认框）。这样“它愿意写命令”就等于“它能动手”。

# 一眼能认出是 PowerShell 的特征（cmdlet / 变量 / 语法）
_PS_HINT_RE = re.compile(
    r"\$env:|\$[A-Za-z_]\w*\s*=|\[math\]::|\bGet-ChildItem\b|\bMeasure-Object\b"
    r"|\bTest-Path\b|\bSort-Object\b|\bSelect-Object\b|\bFormat-Table\b"
    r"|\bGet-Item\b|\bRemove-Item\b|\bGet-Process\b|\bStop-Process\b"
    r"|\bNew-Item\b|\bForEach-Object\b|\bWhere-Object\b|\[PSCustomObject\]"
    r"|\bPS\s*[A-Z]:\\|\bClear-RecycleBin\b|\bGet-CimInstance\b",
    re.IGNORECASE)
# 一眼能认出是 cmd/bat 的特征（行首命令）
_CMD_HINT_RE = re.compile(
    r"(?im)^\s*(dir|del|erase|rmdir|rd|copy|xcopy|move|cd|echo|set|"
    r"tasklist|taskkill|ipconfig|systeminfo|cleanmgr|forfiles|robocopy)\b")

_PS_LANGS = {"powershell", "pwsh", "ps", "ps1", "posh"}
_CMD_LANGS = {"cmd", "bat", "batch", "dos", "console", "shell", "sh", "bash"}

# 一行「看起来就是一条命令」的判定：以常见 PowerShell 动词-名词 cmdlet 开头，或以 $var= 开头。
# 用来兜底抓「夹在文字里的单行/内联命令」（如 `Get-ChildItem C:\ | Select-Object ...`）。
_PS_CMDLET_LINE_RE = re.compile(
    r"^\s*(?:\$\w+\s*=|"
    r"(?:Get|Set|New|Remove|Clear|Test|Measure|Select|Sort|Where|ForEach|Format"
    r"|Out|Write|Add|Copy|Move|Rename|Start|Stop|Import|Export|ConvertTo|ConvertFrom"
    r"|Invoke|Resolve|Split|Join|Compress|Expand|Compare|Group|Tee|Enable|Disable"
    r"|Get-PSDrive|Get-ChildItem|Get-CimInstance|Get-WmiObject)-?\w*"
    r"|gci|gc|ls|dir|cat|type|del|rmdir|rd)\b",
    re.IGNORECASE)
# 续行：以管道/括号/续行符开头，或缩进（属于上一条命令的一部分）
_PS_CONT_LINE_RE = re.compile(r"^\s*[|`)\]}]|^\s{2,}\S")
# 含中文 —— 真实命令一般不含中文（含中文多半是解释性文字），用来排除误伤
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(s):
    return bool(_CJK_RE.search(s or ""))


def _looks_powershell(body):
    b = body or ""
    return len(_PS_HINT_RE.findall(b)) >= 1


def _looks_cmd(body):
    return bool(_CMD_HINT_RE.search(body or ""))


def _ps_encoded_command(script):
    """把多行 PowerShell 脚本编码成 -EncodedCommand 用的 base64（UTF-16LE）。
    这样多行、引号、中文全都稳，cmd.exe 也能照样拉起 powershell 执行。"""
    b16 = (script or "").encode("utf-16-le")
    return base64.b64encode(b16).decode("ascii")


def _shell_call_from_block(lang, body, prefer_name):
    """把一个命令块包装成 sys_run/shell 调用。command 用可执行形式，
    另带 _script（原始可读脚本）+ _lang，供确认框展示给用户看真实命令。"""
    body = (body or "").strip()
    if not body:
        return None
    lang = (lang or "").strip().lower()
    is_ps = lang in _PS_LANGS or (lang not in _CMD_LANGS and _looks_powershell(body))
    if is_ps:
        # 关键修复（2026-06）：
        #  · 强制 UTF-8 输出 → 配合 _run 的 UTF-8 解码，根治中文乱码（C盘→C鐩樼）。
        #  · 关进度流 + 纯文本渲染 → 去掉 "#< CLIXML ... Preparing modules" 噪音。
        #  · 用 Out-String -Width 200 → 重定向(无控制台)时 Format-Table/默认表格也能
        #    渲染出真正的表格（解决"（无输出）"）；宽度取 200 而非 4096，避免把表格
        #    撑出一大片空格、几行就把回灌长度上限吃满导致"已截断"。
        preamble = (
            "$ErrorActionPreference='SilentlyContinue';"
            "$ProgressPreference='SilentlyContinue';"
            "try{[Console]::OutputEncoding=[System.Text.Encoding]::UTF8}catch{};"
            "try{$OutputEncoding=[System.Text.Encoding]::UTF8}catch{};"
            "try{$PSStyle.OutputRendering='PlainText'}catch{};"
        )
        wrapped = preamble + "\n& {\n" + body + "\n} | Out-String -Width 200"
        enc = _ps_encoded_command(wrapped)
        command = ("powershell -NoProfile -ExecutionPolicy Bypass "
                   "-EncodedCommand " + enc)
        disp_lang = "powershell"
    else:
        # cmd/bat：多行用 && 串起来（cmd.exe 直接能跑）
        lines = [ln for ln in body.splitlines() if ln.strip()
                 and not ln.strip().startswith("::") and not ln.strip().startswith("rem ")]
        command = " && ".join(lines) if lines else body
        disp_lang = "cmd"
    args = {"command": command, "_script": body, "_lang": disp_lang}
    return _ToolCall(prefer_name, args)


def _extract_shell_calls(text, known_names):
    """从回复里抠出「命令块」并转成 sys_run/shell 调用。只在没解析到正经工具块时兜底用。
    为安全与可控：只取**第一个**像命令的块（通常模型就写一段；先扫再删的节奏也更稳）。"""
    known = set(known_names or [])
    # 决定落到哪个工具：优先 sys_run（仅需电脑操作权限）；否则 shell（需另开开关）
    target = "sys_run" if "sys_run" in known else ("shell" if "shell" in known else None)
    if not target:
        return []

    # 1) 优先找带语言标记或内容像命令的「围栏代码块」
    for m in _FENCE_LANG_RE.finditer(text or ""):
        lang = (m.group(1) or "").strip().lower()
        body = m.group(2) or ""
        if lang in _PS_LANGS or lang in _CMD_LANGS or _looks_powershell(body) or _looks_cmd(body):
            tc = _shell_call_from_block(lang, body, target)
            if tc is not None:
                return [tc]

    # 2) 围栏被剥掉 / 模型把命令夹在文字里 —— 兜底：找一段连续的「命令行」。
    #    命令行 = 以 cmdlet 或 $var= 开头、且**不含中文**（含中文多半是解释文字，排除）。
    #    续行（管道/缩进）跟随上一条命令。能抓单行内联命令（如 Get-ChildItem C:\ | ...）。
    lines = (text or "").splitlines()
    best_start = best_end = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _PS_CMDLET_LINE_RE.search(ln) and not _has_cjk(ln):
            j = i + 1
            # 继续吞并属于这条命令的续行（管道/缩进/又一条命令行），同样不含中文
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                if _has_cjk(nxt):
                    break
                if (_PS_CMDLET_LINE_RE.search(nxt) or _PS_CONT_LINE_RE.search(nxt)
                        or nxt.rstrip().endswith("|") or nxt.rstrip().endswith("`")):
                    j += 1
                    continue
                break
            best_start, best_end = i, j
            break
        i += 1
    if best_start is not None:
        body = "\n".join(lines[best_start:best_end]).strip()
        # 至少得像条命令（有 cmdlet/管道/变量），太短的单个词不算
        if len(body) >= 6:
            tc = _shell_call_from_block("powershell", body, target)
            if tc is not None:
                return [tc]
    return []


def extract_tool_calls(text, known_names=None):
    """
    从网页模型回复里抠出工具调用。三层兜底，从严到宽：
      ① <<<TOOL>>>{...}<<<END>>> 标记块  —— 明确意图，name 不限。
      ② ```json / ``` 代码块里的 JSON   —— 仅当 name 是真实工具名才认。
      ③ 正文里光秃秃的 {...} JSON       —— 仅当 name 是真实工具名才认。
    这样不管那张网页 AI 卡片用哪种格式（甚至先推辞再贴 JSON），只要它吐出的
    调用 name 是我们真有的工具，就能被执行；纯聊天回答里的示例 JSON 不会误触发。

    返回 (content, tool_calls)：
      · tool_calls None  -> 最终答复，content = 清理后的全文。
      · tool_calls list  -> 有工具调用，content = 去掉工具块后的说明文字。

    known_names: 真实工具名集合（由 create() 从 tools 参数提取后传入）。
    """
    text = text or ""
    known = set(known_names or [])
    calls = []
    seen = set()  # 去重：同名同参只留一次

    def _add(tc):
        if tc is None:
            return
        key = (tc.function.name, tc.function.arguments)
        if key in seen:
            return
        seen.add(key)
        calls.append(tc)

    # ① <<<TOOL>>> … <<<END>>>：抠出来并从正文移除（name 不限）
    def _strip_marker(m):
        _add(_as_tool_call(_tolerant_json(m.group(1)), known, require_known=False))
        return ""
    remaining = _TOOL_RE.sub(_strip_marker, text)

    # ② ```代码块：块内可能有一个或多个 JSON；命中真实工具名的才认，认了就从正文移除
    def _strip_fence(m):
        inner = m.group(1)
        hit = False
        for _, _, obj in _iter_json_objects(inner):
            tc = _as_tool_call(_tolerant_json(obj), known, require_known=True)
            if tc is not None:
                _add(tc)
                hit = True
        if not hit:  # 整块当一个对象再试一次（容错）
            tc = _as_tool_call(_tolerant_json(inner), known, require_known=True)
            if tc is not None:
                _add(tc)
                hit = True
        return "" if hit else m.group(0)
    remaining = _FENCE_RE.sub(_strip_fence, remaining)

    # ③ 正文里裸 JSON：命中真实工具名才认；把命中的那段抹成空格（不当作答复文字）
    blanks = []
    count = 0
    for st, en, obj in _iter_json_objects(remaining):
        if count >= 8:  # 防止模型把整张工具表当 JSON 甩出来时爆量
            break
        tc = _as_tool_call(_tolerant_json(obj), known, require_known=True)
        if tc is not None:
            _add(tc)
            blanks.append((st, en))
            count += 1
    if blanks:
        ch = list(remaining)
        for st, en in blanks:
            for k in range(st, en):
                ch[k] = " "
        remaining = "".join(ch)

    # ④ 都没抠到正经工具块？那就看模型是不是“写了命令让人跑”——把命令块转成 sys_run。
    #    （这个模型常常拒绝写 <<<TOOL>>> 块，却乐意写 PowerShell；顺着它来，把命令真正跑掉。）
    if not calls:
        shell_calls = _extract_shell_calls(text, known)
        for tc in shell_calls:
            _add(tc)

    if not calls:
        # 没有工具调用 = 最终答复：兜底剥掉可能复述的脚手架
        return _strip_scaffold_echo(text), None
    return _strip_scaffold_echo(remaining), calls


# ── 仿 OpenAI 的返回对象 ──
class _FnObj:
    def __init__(self, name, args):
        self.name = name
        self.arguments = json.dumps(args, ensure_ascii=False)

    def model_dump(self):
        return {"name": self.name, "arguments": self.arguments}


class _ToolCall:
    def __init__(self, name, args):
        self.id = "webcall_" + uuid.uuid4().hex[:12]
        self.type = "function"
        self.function = _FnObj(name, args)

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": self.function.model_dump()}


class _Msg:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.role = "assistant"
        self.tool_calls = tool_calls or None

    def model_dump(self):
        return {"role": "assistant", "content": self.content,
                "tool_calls": ([tc.model_dump() for tc in self.tool_calls]
                               if self.tool_calls else None)}


class _Choice:
    def __init__(self, content, tool_calls=None):
        self.message = _Msg(content, tool_calls)
        self.finish_reason = "tool_calls" if tool_calls else "stop"
        self.index = 0


class _Resp:
    def __init__(self, content, tool_calls=None):
        self.choices = [_Choice(content, tool_calls)]


def _msg_sig(msgs, n):
    """前 n 条 messages（去掉 system）的指纹。"""
    import hashlib
    h = hashlib.sha1()
    for m in (msgs or [])[:n]:
        if m.get("role") == "system":
            continue
        ids = ",".join((tc or {}).get("id") or "" for tc in (m.get("tool_calls") or []))
        h.update(("%s|%s|%s|%s\n" % (m.get("role"), _text_of(m.get("content")),
                                      ids, m.get("tool_call_id") or "")).encode("utf-8", "ignore"))
    return h.hexdigest()


def _tools_ran_since_last_user(msgs):
    """最新的用户消息之后是否已经执行过工具（执行过的话，模型的文字回复多半是总结，不是推辞）。"""
    for m in reversed(msgs or []):
        if m.get("role") == "tool":
            return True
        if m.get("role") == "user":
            return False
    return False


class _Completions:
    def __init__(self, on_progress=None):
        self._on_progress = on_progress
        self._sent_count = 0     # Agent 模式：已经"喂进"网页对话线程的 messages 条数

    @staticmethod
    def _safe_cb(cb, msg):
        """安全地推一条进度消息：回调出错也不打断主流程。"""
        if not cb:
            return
        try:
            cb(msg)
        except Exception:
            pass

    def create(self, model=None, messages=None, tools=None,
               on_progress=None, **kwargs):
        cb = on_progress or self._on_progress

        # ── Agent 模式：收到非空 tools（run_agent 工具循环触发）──
        if tools:
            msgs = messages or []
            n = len(msgs)
            # 真实工具名单：用于安全地把"代码块/裸 JSON"形式的调用也认出来
            known = set()
            for t in tools:
                fn = (t or {}).get("function") or {}
                nm = fn.get("name")
                if nm:
                    known.add(nm)
            # 能接着上次的网页对话线程发增量吗？条件：线程没换过，且上次发过的那段对话原样还在。
            st = _THREAD
            can_continue = (st["sent"] > 0 and st["sent"] < n
                            and st["epoch"] == web_model.chat_epoch()
                            and _msg_sig(msgs, st["sent"]) == st["sig"])
            # 工具循环期间不换卡（保持同一对话线程，增量才有意义）；给足超时。
            wait_opts = {"disableCardSwitch": True, "timeout": 600000}
            if can_continue:
                prompt = _build_incremental_prompt(msgs[st["sent"]:])
                text = web_model.web_complete(prompt, on_progress=cb, **wait_opts)
            else:
                # 新任务/对话被改过/线程换了 → 开个空白新对话，发完整自包含 prompt，
                # 免得旧任务的内容混进来（之前「你确认的是哪项操作？」就是这么来的）
                prompt = _build_full_prompt(msgs, tools)
                text = web_model.web_complete(prompt, on_progress=cb, newChat=True,
                                              newChatStrict=True, **wait_opts)
            _THREAD.update(sig=_msg_sig(msgs, n), sent=n, epoch=web_model.chat_epoch())
            content, tool_calls = extract_tool_calls(text, known_names=known)
            if tool_calls is not None:
                return _Resp(content, tool_calls)

            # ── 没有解析到工具块。若是「文字推辞」，分两步抢救 ──
            if not _tools_ran_since_last_user(msgs) and _looks_like_refusal(content):
                # 第一步：同一张卡上更强地催一次（对“软推辞”的卡常常就够了）
                if cb:
                    self._safe_cb(cb, "网页模型在用文字推托，正在更强地要求它直接动手…")
                text2 = web_model.web_complete(
                    _REFUSAL_NUDGE, on_progress=cb, **wait_opts)
                content2, tool_calls2 = extract_tool_calls(text2, known_names=known)
                if tool_calls2:
                    return _Resp(content2, tool_calls2)
                if content2 and not _looks_like_refusal(content2):
                    # 它改口给了一个正常（非推辞）的答复，比如反问澄清 → 照原样返回
                    return _Resp(content2, None)

                # 第二步：还在推辞。这多半是「轴卡」（模型本身不肯配合）。
                #   换一张新卡重抽，直到碰到肯写工具块/命令的卡；都不行就用保底。
                #   关键：换卡时**重发完整自包含 prompt**（含全部对话+工具），
                #   这样即使是在对话中途换卡，新卡也有完整上下文、不会断片。
                best = content2 or content
                if _MAX_CARD_RETRIES > 0:
                    retry_prompt = _build_full_prompt(msgs, tools)
                    for i in range(1, _MAX_CARD_RETRIES + 1):
                        if cb:
                            self._safe_cb(cb, "这张卡不肯动手，换第 %d 张卡重试…" % i)
                        try:
                            text3 = web_model.web_complete(
                                retry_prompt, on_progress=cb,
                                forceNewCard=True, **wait_opts)
                        except Exception:
                            break  # 换卡/查询异常就别死磕了，交给上层兜底
                        content3, tool_calls3 = extract_tool_calls(
                            text3, known_names=known)
                        _THREAD.update(sig=_msg_sig(msgs, n), sent=n,
                                       epoch=web_model.chat_epoch())
                        if tool_calls3:
                            return _Resp(content3, tool_calls3)
                        if content3 and not _looks_like_refusal(content3):
                            return _Resp(content3, None)
                        if content3:
                            best = content3  # 记下最新的一条，循环结束兜底用
                return _Resp(best, None)

            # 不是推辞、也没有工具块 = 正常的最终答复
            return _Resp(content, None)

        # ── 纯文本模式：老行为，原样保留 ──
        prompt = flatten_messages(messages)
        wait_opts = {}
        for k in ("requiredMarkers", "minExpectedLength", "markersMinHits",
                  "acceptStableMarkers", "expectsJson", "timeout",
                  "disableCardSwitch", "shortReply",
                  "bestModel", "thinkNoOutputMs", "stuckFatalMs", "newTaskCard",
                  "saveImages", "imageWaitMs"):
            if k in kwargs:
                wait_opts[k] = kwargs[k]
        # 纯文本模式每次都带着完整历史，开新对话发送，避免和别的任务混在一个线程里
        text = web_model.web_complete(prompt, on_progress=cb, newChat=True, **wait_opts)
        _THREAD.update(sig=None, sent=0, epoch=None)
        return _Resp(text, None)


class _Chat:
    def __init__(self, on_progress=None):
        self.completions = _Completions(on_progress)


class WebModelClient:
    """与 OpenAI() 同形：client.chat.completions.create(...)。"""

    def __init__(self, on_progress=None):
        self.chat = _Chat(on_progress)
