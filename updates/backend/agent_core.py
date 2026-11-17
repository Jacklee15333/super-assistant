"""
agent_core.py — 本地 agent 的核心引擎

负责三件事：
1. 读取"灵魂三件套"(AGENTS.md / SOUL.md / USER.md) 作为系统提示
2. 跑工具调用循环 (模型说要用工具 -> 程序执行 -> 结果回传 -> 模型继续)
3. 把记忆读写到本地 Markdown 文件

这一份是模型无关的：本地 (Ollama) 和云端 (OpenAI / DeepSeek 等) 都走同一套 OpenAI 兼容接口。
"""

import os
import re
import json
import datetime
import subprocess
from pathlib import Path

# ---------- 路径 ----------
BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)


# ---------- 模型客户端 ----------
_LOCAL_MODELS = {"t": 0.0, "names": []}


def installed_local_models():
    """Ollama 本机已装的模型名（缓存 60 秒）。拿不到返回 []。"""
    import time
    import urllib.request
    if time.time() - _LOCAL_MODELS["t"] < 60:
        return _LOCAL_MODELS["names"]
    names = []
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            names = [m.get("name") for m in json.loads(r.read().decode("utf-8")).get("models", [])
                     if m.get("name")]
    except Exception:
        names = []
    _LOCAL_MODELS.update(t=time.time(), names=names)
    return names


def resolve_local_model(name):
    """代码里很多地方写死了 "qwen2.5"。本机没装它时，换成用户配置的本地模型（如 qwen3:14b），
    而不是直接报错。装了、或查不到已装列表时原样返回。"""
    names = installed_local_models()
    if not names or not name or name in names or str(name).endswith("cloud"):
        return name
    fam = str(name).split(":")[0]
    for n in names:
        if n.split(":")[0] == fam:
            return n
    try:
        for task in ("local_action", "quick_chat", "default", "chat"):
            ul, m = resolve_model(task, fallback_use_local=True, fallback_model="")
            if ul and m in names:
                return m
    except Exception:
        pass
    return names[0]


class _LocalChatCompletions:
    def __init__(self, inner):
        self._inner = inner

    def create(self, model=None, **kwargs):
        import prompt_utils as pu
        resp = self._inner.create(model=resolve_local_model(model), **kwargs)
        try:
            msg = resp.choices[0].message
            if isinstance(msg.content, str) and "think>" in msg.content:
                msg.content = pu.strip_think(msg.content)   # qwen3 等思考型模型的推理段不外露
        except Exception:
            pass
        return resp


class _LocalClient:
    """包一层 Ollama 客户端：自动换成已装的模型名 + 去掉 <think> 段。其余行为与 OpenAI 客户端一致。"""
    _is_local = True

    def __init__(self, inner):
        self._inner = inner
        self.base_url = getattr(inner, "base_url", "http://localhost:11434/v1")
        self.chat = type("_Chat", (), {})()
        self.chat.completions = _LocalChatCompletions(inner.chat.completions)

    def __getattr__(self, item):
        return getattr(self._inner, item)


def make_client(use_local: bool):
    """根据开关返回一个 OpenAI 兼容客户端。"""
    from openai import OpenAI  # 延迟导入：没装 openai 时也能用工具/记忆逻辑
    if use_local:
        # Ollama 暴露的 OpenAI 兼容端点，key 随便填
        return _LocalClient(OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"))
    else:
        # 云端：默认读环境变量 OPENAI_API_KEY；想用 DeepSeek 等改 base_url 即可
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def is_web_model(model):
    """是不是「伪模型」（网页大模型）。"""
    try:
        import router
        return router.is_web_model(model)
    except Exception:
        return model == "web"


def make_client_for(model, use_local, on_progress=None):
    """
    按模型返回客户端。
      · 伪模型(model=='web') → WebModelClient（伪装 OpenAI，忽略 tools、纯文本进出）
      · Claude(model=='claude' / 'claude::N') → ClaudeClient
      · 其它 → 原 make_client(use_local)
    on_progress 只对伪模型有意义（用于播报「登录/思考中/接收回复」等进度）。
    """
    if is_web_model(model):
        from web_model_client import WebModelClient
        return WebModelClient(on_progress=on_progress)
    if model == "claude" or str(model).startswith("claude::"):
        import claude_client
        idx = None
        if str(model).startswith("claude::"):
            try:
                idx = int(str(model).split("::")[1])
            except (ValueError, IndexError):
                idx = None
        return claude_client.make(profile_index=idx)
    return make_client(use_local)


# ---------- 各任务用哪个模型（task_models.json）----------
TASK_MODELS_PATH = MEMORY_DIR / "task_models.json"


def _default_task_models():
    # 默认就是用户要的：高级分析→伪模型；视频总结→伪模型；本机动作→本地
    return {
        "default": {"use_local": False, "model": "web"},
        "chat": {"follow_default": True},
        "video_summary": {"use_local": False, "model": "web"},
        "local_action": {"use_local": True, "model": "qwen2.5"},
        "quick_chat": {"use_local": True, "model": "qwen2.5"},
    }


def load_task_models():
    if TASK_MODELS_PATH.exists():
        try:
            data = json.loads(TASK_MODELS_PATH.read_text(encoding="utf-8"))
            base = _default_task_models()
            base.update(data or {})
            return base
        except Exception:
            pass
    return _default_task_models()


def save_task_models(tm):
    merged = load_task_models()
    merged.update(tm or {})
    TASK_MODELS_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def resolve_model(task, fallback_use_local=True, fallback_model="qwen2.5"):
    """便捷封装：读 task_models.json 后调 router.resolve_model。
    若解析结果是「网页模型」，但用户开了「用 Claude 替代网页模型」且配了 Claude，
    则自动改用第一个 Claude 配置（claude::0）——避免老去触发不稳定的网页模型。"""
    import router
    use_local, model = router.resolve_model(
        task, load_task_models(), fallback_use_local, fallback_model)
    if is_web_model(model):
        try:
            import claude_client
            cfg = claude_client.load_config()
            profiles = cfg.get("profiles") or []
            prefer = cfg.get("prefer_over_web", False)
            # 找第一个配好 key 的 Claude 配置
            idx = next((i for i, p in enumerate(profiles) if p.get("api_key")), None)
            if prefer and idx is not None:
                return False, "claude::%d" % idx
        except Exception:
            pass
    return use_local, model


# ---------- 记忆读写 ----------
def read_memory_file(name: str) -> str:
    p = MEMORY_DIR / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def write_memory_file(name: str, content: str) -> str:
    # 安全：只允许操作 memory/ 目录下、.md 结尾的文件，防止越界写盘
    if "/" in name or "\\" in name or ".." in name:
        return "拒绝：文件名不合法。"
    if not name.endswith(".md"):
        name = name + ".md"
    p = MEMORY_DIR / name
    p.write_text(content, encoding="utf-8")
    return f"已写入 {name}（{len(content)} 字符）"


def remember(text: str) -> str:
    """把一条值得长期记住的信息追加进 MEMORY.md。新对话开始会自动加载，于是"越用越懂你"。"""
    text = (text or "").strip()
    if not text:
        return "拒绝：要记的内容为空。"
    p = MEMORY_DIR / "MEMORY.md"
    if not p.exists():
        p.write_text("# 长期记忆\n\n超能小助从历次对话里记下的、关于你的要点。\n\n",
                     encoding="utf-8")
    today = datetime.date.today().isoformat()
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- （{today}）{text}\n")
    return f"好的，记住了：{text}"


def append_note(text: str) -> str:
    """把一行追加到当天的笔记文件。"""
    today = datetime.date.today().isoformat()
    p = MEMORY_DIR / f"note-{today}.md"
    stamp = datetime.datetime.now().strftime("%H:%M")
    line = f"- {stamp} {text}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(line)
    return (f"已追加到当天笔记 note-{today}.md（在 memory 目录下）。"
            f"如果要查看这份笔记，请用 read_memory 工具（name=\"note-{today}.md\"），"
            f"不要用 read_file 去猜路径。")


_UNATTENDED_DENY = ("这一步需要用户在电脑前确认，现在是无人值守（定时任务/手机渠道），已自动跳过。"
                    "不要再尝试这个操作；在回复里说明需要用户回到电脑前处理什么。")


def run_agent_autodeny(client, model, messages, on_tool=None, max_steps=8):
    """
    无人值守场景（心跳/手机渠道）用：危险操作一律自动拒绝，只跑安全工具。
    返回 (回复文本, messages)。更安全——没人在旁边时 AI 碰不了危险操作。
    """
    approvals = {}
    for _ in range(max_steps + 3):
        reply, messages, pending = run_agent(
            client, model, messages, on_tool=on_tool,
            max_steps=max_steps, approvals=approvals,
            deny_message=_UNATTENDED_DENY)
        if pending is None:
            return reply, messages
        # 自动拒绝这个危险调用，继续
        approvals[pending["tool_call_id"]] = False
    return "（处理中断）", messages


_RULES_INTERACTIVE = (
    "=== 通用做事规则 ===\n"
    "- 需要实时信息（新闻、价格、天气、最近的事、拿不准的事实）时，调用 web_search 或 research 去查，"
    "再根据结果回答；不要说自己不能联网，也不要把工具调用写成文字让用户去执行。"
    "视频链接用 video_transcript，普通网页用 read_webpage。\n"
    "- 需要做事就调用工具，不假装执行、不凭记忆编造结果。意图清楚就直接做，不反复确认；"
    "真正缺关键信息时才问一句。\n"
    "- 删除、清理、执行命令这类有风险的操作：直接调用对应工具，程序会弹出「批准/拒绝」让用户点。"
    "不要用文字让用户回复「是/否」——人格和准则里说的「先问你/先确认」指的就是这个弹窗。\n"
    "- 检查/清理/整理类任务：先用只读工具摸清情况，用 Markdown 表格汇报（类别、位置、大小/数量、是否安全），"
    "再给一句总结；接下来要做的多个有风险操作在同一轮一起发起，让用户在一个确认框里批量批准。\n"
    "- 清理 C 盘垃圾/临时文件用 sys_clean_temp，不要用命令删；遇到「访问被拒/正被占用」的文件跳过即可，"
    "如实说明，不算失败。\n"
    "- 回答长短按需要：简单问题简洁回答；查询、分析类结果把关键数据讲清楚。"
)

_RULES_UNATTENDED = (
    "=== 通用做事规则（无人值守）===\n"
    "- 现在用户不在电脑前（定时任务或手机消息渠道），没有人能点确认。删除、清理、执行命令、"
    "写文件这类需要确认的操作都会被自动拦下——不要尝试；只做查询、搜索、读取、记笔记这类安全操作。\n"
    "- 如果完成任务确实需要这类操作，就在回复里说清楚打算做什么、为什么，让用户回到电脑前再处理。\n"
    "- 需要实时信息时调用 web_search 或 research 去查；不凭记忆编造结果。\n"
    "- 回复简洁清楚，适合在手机上看。"
)


def build_system_prompt(request: str = "", unattended: bool = False) -> str:
    """把人格/准则/记忆/画像/技能拼成系统提示（2026-11 精简版）。

    request：用户这次说的话（可选）。给了就按相关性取舍 AGENTS.md 的专项小节、洞察报告；
             不给就保守地都带上。
    unattended：无人值守（心跳、定时任务、手机渠道）。这时没人能点确认弹窗，
             规则改成「危险操作不要做，在回复里说明」。
    """
    import prompt_utils as pu
    now = datetime.datetime.now()
    parts = ["现在时间是 %s（星期%s）。" % (now.strftime("%Y-%m-%d %H:%M"), "一二三四五六日"[now.weekday()])]

    soul = pu.clean_soul(read_memory_file("SOUL.md"))
    if soul:
        parts.append("=== 你的人格 (SOUL.md) ===\n" + soul)
    agents = pu.compact_agents(read_memory_file("AGENTS.md"), request, unattended)
    if agents:
        parts.append("=== 你的行为准则 (AGENTS.md) ===\n" + agents)
    user = pu.strip_template(read_memory_file("USER.md"))
    if user:
        parts.append("=== 关于用户 (USER.md) ===\n" + user)

    long_term = pu.dedupe_lines(pu.strip_template(read_memory_file("MEMORY.md")))
    if long_term.strip():
        # 上下文预算（Harness 设置）：注入多少长期记忆。塞太多会「上下文腐烂」，让模型忘了原始目标。
        try:
            import harness
            _budget = harness.context_budget()
        except Exception:
            _budget = 4000
        if len(long_term) > _budget:
            long_term = "（早期记忆已省略）\n...\n" + long_term[-_budget:]
        parts.append("=== 你和用户过往的长期记忆 (MEMORY.md) ===\n" + long_term)

    # 「懂你」四件套：画像 / 关系网络 / 环境 / 洞察（精简后注入，失败安静跳过）
    try:
        import lumi_features
        ctx = pu.compact_lumi(lumi_features.build_context_block(), request)
        if ctx.strip():
            parts.append(ctx)
    except Exception:
        pass
    # 技能库：只放名字+一句用途，要用时模型自己 load_skill
    try:
        import skills_store
        sk = pu.compact_skills(skills_store.build_skills_index())
        if sk.strip():
            parts.append(sk)
    except Exception:
        pass

    parts.append(_RULES_UNATTENDED if unattended else _RULES_INTERACTIVE)
    return "\n\n".join(parts)


# ---------- 工具定义 ----------
def tool_get_time(_args=None):
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def tool_calc(args):
    expr = args.get("expression", "")
    # 安全：只允许数字和基本运算符，杜绝任意代码执行
    allowed = set("0123456789+-*/(). ")
    if not set(expr) <= allowed:
        return "拒绝：表达式含非法字符。"
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算出错：{e}"


def tool_read_memory(args):
    return read_memory_file(args.get("name", "")) or "（文件为空或不存在）"


def tool_write_memory(args):
    return write_memory_file(args.get("name", ""), args.get("content", ""))


def tool_append_note(args):
    return append_note(args.get("text", ""))


def tool_remember(args):
    return remember(args.get("text", ""))


def tool_list_memory(_args=None):
    files = sorted(p.name for p in MEMORY_DIR.glob("*.md"))
    return "\n".join(files) if files else "（memory 目录为空）"


def tool_web_search(args):
    """联网搜索。统一走 web_tools 的多引擎搜索（Bing/百度/搜狗，国外需代理）。"""
    query = args.get("query", "").strip()
    if not query:
        return "拒绝：搜索词为空。"
    try:
        import web_tools
        results, note = web_tools._search(query, 6)
        if not results:
            return note or f"没搜到“{query}”。换个更通用的关键词再试。"
        lines = [f"- {t}\n  {u}" for t, u in results]
        out = "搜到这些结果（如需详情可用 research 或 read_webpage 读正文）：\n" + "\n".join(lines)
        if note:
            out += "\n\n" + note
        return out[:3000]
    except Exception as e:
        return f"搜索出错：{e}（请确认电脑能正常上网）"


def make_shell_tool(enabled: bool):
    """shell 工具是否可用由界面开关控制。默认关闭。"""
    def tool_shell(args):
        if not enabled:
            return "拒绝：shell 执行未开启。请在界面里打开开关。"
        cmd = args.get("command", "")
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip()[:4000] or "（无输出）"
        except Exception as e:
            return f"执行出错：{e}"
    return tool_shell


# 工具的 JSON Schema 描述（告诉模型有哪些工具、怎么调用）
TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "get_time", "description": "获取当前日期和时间",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "calc", "description": "计算一个数学表达式",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "如 (128*9)/4"}},
            "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "read_memory", "description": "读取 memory 目录下的某个 Markdown 文件",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "文件名，如 USER.md"}},
            "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "write_memory", "description": "写入/覆盖 memory 目录下的某个 Markdown 文件",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "content": {"type": "string"}},
            "required": ["name", "content"]}}},
    {"type": "function", "function": {
        "name": "append_note", "description": "把一句话追加到今天的笔记里",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "list_memory", "description": "列出 memory 目录下所有文件",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "web_search", "description": "联网搜索，获取实时信息或你不知道的知识",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "shell", "description": "执行一条 shell 命令（需在界面开启，有风险）",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
]


def build_tools(shell_enabled: bool):
    """返回 名字->函数 的映射。"""
    return {
        "get_time": tool_get_time,
        "calc": tool_calc,
        "read_memory": tool_read_memory,
        "write_memory": tool_write_memory,
        "append_note": tool_append_note,
        "list_memory": tool_list_memory,
        "web_search": tool_web_search,
        "shell": make_shell_tool(shell_enabled),
    }


# ---------- 核心循环 ----------
def _context_budget(client, model):
    """发给模型的对话总字数上限：本地小模型上下文有限，云端/Claude 宽松；网页模型自己管理。"""
    if is_web_model(model):
        return None
    base = str(getattr(client, "base_url", "") or "")
    if "11434" in base or getattr(client, "_is_local", False):
        return 14000
    return 60000


def _call_model_with_retry(client, model, messages, schema, retries=2):
    """调用模型，失败重试。返回 message 对象。
    ★ 超出上下文预算时只裁「发给模型的那份」（保留 system + 用户最新请求及本轮工具结果），
      原 messages 不动——前端的聊天记录照样完整。"""
    import time
    import prompt_utils as pu
    budget = _context_budget(client, model)
    if budget:
        messages = pu.fit_messages(messages, budget)
    last_err = None
    for attempt in range(retries + 1):
        try:
            try:
                # 带上 tool_choice=auto：能促使部分本地模型（Ollama）真正去调用工具，
                # 而不是只用文字\"叙述\"它打算做什么。
                resp = client.chat.completions.create(
                    model=model, messages=messages, tools=schema,
                    tool_choice="auto")
            except TypeError:
                # 个别旧版 SDK 不认 tool_choice 参数，退回不带
                resp = client.chat.completions.create(
                    model=model, messages=messages, tools=schema)
            return resp.choices[0].message
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))  # 退避重试
    raise last_err


def describe_tool(name, args):
    """把工具调用翻译成普通用户看得懂的中文说明。返回 (标题, 详情)。
    标题是一句话概括「要做什么」；详情是补充的具体信息（路径/命令摘要等）。"""
    args = args or {}

    def _short(v, n=120):
        s = str(v or "")
        return s if len(s) <= n else s[:n] + "…"

    # 文件类
    if name == "write_file":
        return ("写入文件", "路径：%s" % _short(args.get("path", "")))
    if name == "delete_file":
        return ("删除文件", "路径：%s" % _short(args.get("path", "")))
    if name == "write_memory":
        return ("写入记忆笔记", "文件：%s" % _short(args.get("name", "")))
    if name == "fs_open":
        return ("用默认程序打开", "%s" % _short(args.get("path", "")))
    if name == "fs_move":
        return ("移动 / 重命名", "从 %s\n到 %s" % (_short(args.get("src", "")), _short(args.get("dst", ""))))
    if name == "fs_copy":
        return ("复制文件", "从 %s\n到 %s" % (_short(args.get("src", "")), _short(args.get("dst", ""))))
    if name == "fs_mkdir":
        return ("新建文件夹", "%s" % _short(args.get("path", "")))
    if name == "fs_trash":
        return ("移到回收站（可恢复）", "%s" % _short(args.get("path", "")))
    if name == "fs_organize":
        return ("整理文件夹（按类型归类）", "目标：%s" % _short(args.get("path", "") or "桌面"))

    # 系统类
    if name == "sys_kill":
        return ("结束一个进程", "目标：%s" % _short(args.get("target", "")))
    if name == "sys_clean_temp":
        return ("清理系统临时文件，释放磁盘空间", "")
    if name == "empty_recycle_bin":
        return ("清空回收站（彻底删除回收站里的所有文件）", "")
    if name == "sys_volume":
        return ("调整系统音量", "设为：%s" % _short(args.get("level", "")))
    if name == "sys_brightness":
        return ("调整屏幕亮度", "设为：%s" % _short(args.get("level", "")))
    if name == "sys_open_settings":
        return ("打开 Windows 系统设置", "页面：%s" % _short(args.get("which", "") or "设置主页"))
    if name == "sys_run":
        # 若带了 _script（网页模型写的原始 PowerShell/命令，command 里其实是编码后的可执行形式），
        # 弹给用户看的应是这段可读脚本，而不是 base64。
        raw = args.get("_script") or args.get("command", "")
        lang = args.get("_lang")
        cmd = _short(raw, 600)
        guess = _guess_command_intent(raw)
        head = ("将运行这段 %s 命令：\n" % lang) if lang else "命令："
        detail = (guess + "\n\n" if guess else "") + head + cmd
        return ("在电脑上执行一条命令", detail)
    if name == "shell":
        raw = args.get("_script") or args.get("command", "")
        lang = args.get("_lang")
        cmd = _short(raw, 600)
        guess = _guess_command_intent(raw)
        head = ("将运行这段 %s 命令：\n" % lang) if lang else "命令："
        detail = (guess + "\n\n" if guess else "") + head + cmd
        return ("执行一条命令", detail)

    # GUI 类
    if name == "gui_open_app":
        return ("打开一个应用程序", "%s" % _short(args.get("name", "")))
    if name == "gui_click":
        return ("在屏幕上点击鼠标", "坐标：(%s, %s)" % (args.get("x", "?"), args.get("y", "?")))
    if name == "gui_type":
        return ("在当前位置输入文字", "内容：%s" % _short(args.get("text", "")))
    if name == "gui_press":
        return ("按下按键", "%s" % _short(args.get("keys", "")))
    if name == "gui_scroll":
        return ("滚动鼠标滚轮", "幅度：%s" % _short(args.get("amount", "")))

    # 兜底：用工具名 + 简短参数
    extra = ""
    try:
        kv = [f"{k}={_short(v, 40)}" for k, v in args.items() if v]
        extra = "、".join(kv[:3])
    except Exception:
        pass
    return ("执行操作：%s" % name, extra)


def _guess_command_intent(command):
    """对命令行做粗略意图猜测，给个白话说明（尽力而为，猜不出就返回空）。"""
    c = str(command or "").lower()
    if not c:
        return ""
    if "measure-object" in c or ("get-childitem" in c and "sum" in c):
        return "（这条命令是在统计某些文件夹占用了多少磁盘空间，只读不删）"
    if "remove-item" in c or "del " in c or "rmdir" in c or "rm -" in c:
        return "（⚠️ 这条命令会删除文件，请仔细确认）"
    if "test-path" in c and "remove" not in c:
        return "（这条命令只是检查文件/文件夹是否存在，不会改动任何东西）"
    if "get-process" in c or "tasklist" in c:
        return "（这条命令是在查看正在运行的程序，只读）"
    if "stop-process" in c or "taskkill" in c:
        return "（⚠️ 这条命令会结束某个程序）"
    if "clear-recyclebin" in c:
        return "（⚠️ 这条命令会清空回收站）"
    return ""


def _has_tool_result(messages, tool_call_id):
    """判断某个 tool_call 是否已经有对应的 tool 结果消息（续跑去重用）。"""
    if not tool_call_id:
        return False
    for m in messages:
        if m.get("role") == "tool" and m.get("tool_call_id") == tool_call_id:
            return True
    return False


# 命令类工具即使用户选了「这类不再询问」，碰到这些破坏性命令也要单独确认
_DESTRUCTIVE_CMD_RE = re.compile(
    r"Remove-Item|\b(rm|del|erase|rd|rmdir|ri)\b|Clear-RecycleBin|Clear-Content|Clear-Item"
    r"|Format-Volume|\bformat\s+[a-z]:|diskpart|cipher\s+/w|Stop-Process|\btaskkill\b|\bkill\b"
    r"|reg(\.exe)?\s+(delete|add)|Remove-ItemProperty|Set-ItemProperty|New-ItemProperty"
    r"|Move-Item|\bmove\b|Rename-Item|\bren(ame)?\b|Set-Content|Out-File|Add-Content"
    r"|shutdown|Restart-Computer|Stop-Computer|Stop-Service|Set-Service|Uninstall-|\bsc\s+delete"
    r"|Invoke-WebRequest|\biwr\b|Invoke-Expression|\biex\b|Start-Process|bcdedit|vssadmin",
    re.IGNORECASE)


def _auto_approved(name, args, auto_set):
    """该调用能否按「本次对话已授权这类操作」直接放行。"""
    if name not in auto_set:
        return False
    if name in ("sys_run", "shell"):
        cmd = str((args or {}).get("_script") or (args or {}).get("command") or "")
        if _DESTRUCTIVE_CMD_RE.search(cmd):
            return False
    return True


def run_agent(client, model, messages, shell_enabled=False,
              on_tool=None, max_steps=8, approvals=None,
              on_think=None, on_tool_start=None, auto_approve_tools=None,
              deny_message=None):
    """
    跑一轮 agent。返回 (回复文本, 更新后的 messages, pending)。
    - pending 为 None：正常完成。
    - pending 为 dict：遇到危险工具，已挂起等确认；dict 含 {tool_call} 信息。
      界面拿到后弹确认框，用户批准/拒绝后，把决定放进 approvals 再调一次本函数续跑。

    approvals: {tool_call_id: True/False}，已获批准/拒绝的危险调用。
    auto_approve_tools: 一组工具名，本次对话已被用户授权「这类操作不用再问」，
      遇到这些工具直接放行，不再弹确认。
    """
    # 延迟导入，避免循环依赖
    import tools as T
    approvals = approvals or {}
    auto_set = set(auto_approve_tools or [])

    for _ in range(max_steps):
        # ── 续跑判断：如果 messages 末尾已经是一条「带 tool_calls 但还没有 tool 结果」的
        #    assistant 消息，说明这是用户批准/拒绝后回来续跑，直接执行那批工具，
        #    不要再调一次模型（否则会重复生成、消息错乱）。
        resume_msg = None
        if messages and messages[-1].get("role") == "assistant" and messages[-1].get("tool_calls"):
            resume_msg = messages[-1]

        if resume_msg is None:
            if on_think:
                on_think()
            msg = _call_model_with_retry(client, model, messages, T.TOOLS_SCHEMA)

            if not msg.tool_calls:
                messages.append({"role": "assistant", "content": msg.content or ""})
                return msg.content or "", messages, None

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            tool_calls_data = [tc.model_dump() for tc in msg.tool_calls]
        else:
            # 续跑：直接用末尾那条 assistant 消息里的 tool_calls
            tool_calls_data = resume_msg.get("tool_calls") or []

        # ── 先扫一遍这一批工具调用，把还没决定的危险操作收集起来 ──
        #    一次性打包给界面批量确认，而不是一个一个弹窗。
        pending_list = []
        for tcd in tool_calls_data:
            fn_d = tcd.get("function", {}) or {}
            name = fn_d.get("name")
            tcid = tcd.get("id")
            try:
                args = json.loads(fn_d.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            if (T.is_danger(name) and approvals.get(tcid) is None
                    and not _auto_approved(name, args, auto_set)):
                title, detail = describe_tool(name, args)
                pending_list.append({
                    "tool_call_id": tcid,
                    "name": name,
                    "args": args,
                    "title": title,
                    "detail": detail,
                })
        if pending_list:
            return None, messages, {
                "tool_call_id": pending_list[0]["tool_call_id"],
                "name": pending_list[0]["name"],
                "args": pending_list[0]["args"],
                "title": pending_list[0]["title"],
                "detail": pending_list[0]["detail"],
                "batch": pending_list,
            }

        # ── 执行这一批工具（已全部有决定）──
        for tcd in tool_calls_data:
            fn_d = tcd.get("function", {}) or {}
            name = fn_d.get("name")
            tcid = tcd.get("id")
            try:
                args = json.loads(fn_d.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}

            # 已经有结果的工具（续跑时上一轮已执行过的）跳过，避免重复执行
            if _has_tool_result(messages, tcid):
                continue

            # 危险工具：检查是否已获批准（或属于本次对话已授权的类别）
            if T.is_danger(name) and not _auto_approved(name, args, auto_set):
                decision = approvals.get(tcid)
                if decision is False:
                    result = deny_message or "用户拒绝了这次操作。"
                    if on_tool:
                        on_tool(name, args, result)
                    messages.append({"role": "tool", "tool_call_id": tcid,
                                     "content": result})
                    continue
                # decision is True -> 往下执行

            fn = T.get_tool_fn(name)
            if on_tool_start:
                on_tool_start(name, args)
            if fn is None:
                result = f"未知工具：{name}"
            else:
                try:
                    result = fn(args)
                except Exception as e:
                    result = f"工具执行出错：{e}"
            if on_tool:
                on_tool(name, args, result)
            messages.append({"role": "tool", "tool_call_id": tcid,
                             "content": str(result)})

    messages.append({"role": "assistant", "content": "（达到最大步数，停止。）"})
    return "（达到最大步数，停止。）", messages, None
