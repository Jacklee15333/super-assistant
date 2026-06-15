"""
agent_core.py — 本地 agent 的核心引擎

负责三件事：
1. 读取"灵魂三件套"(AGENTS.md / SOUL.md / USER.md) 作为系统提示
2. 跑工具调用循环 (模型说要用工具 -> 程序执行 -> 结果回传 -> 模型继续)
3. 把记忆读写到本地 Markdown 文件

这一份是模型无关的：本地 (Ollama) 和云端 (OpenAI / DeepSeek 等) 都走同一套 OpenAI 兼容接口。
"""

import os
import json
import datetime
import subprocess
from pathlib import Path

# ---------- 路径 ----------
BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)


# ---------- 模型客户端 ----------
def make_client(use_local: bool):
    """根据开关返回一个 OpenAI 兼容客户端。"""
    from openai import OpenAI  # 延迟导入：没装 openai 时也能用工具/记忆逻辑
    if use_local:
        # Ollama 暴露的 OpenAI 兼容端点，key 随便填
        return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    else:
        # 云端：默认读环境变量 OPENAI_API_KEY；想用 DeepSeek 等改 base_url 即可
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


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


def append_note(text: str) -> str:
    """把一行追加到当天的笔记文件。"""
    today = datetime.date.today().isoformat()
    p = MEMORY_DIR / f"note-{today}.md"
    stamp = datetime.datetime.now().strftime("%H:%M")
    line = f"- {stamp} {text}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(line)
    return f"已记到 note-{today}.md"


def run_agent_autodeny(client, model, messages, on_tool=None, max_steps=8):
    """
    无人值守场景（心跳/手机渠道）用：危险操作一律自动拒绝，只跑安全工具。
    返回 (回复文本, messages)。更安全——没人在旁边时 AI 碰不了危险操作。
    """
    approvals = {}
    for _ in range(max_steps + 3):
        reply, messages, pending = run_agent(
            client, model, messages, on_tool=on_tool,
            max_steps=max_steps, approvals=approvals)
        if pending is None:
            return reply, messages
        # 自动拒绝这个危险调用，继续
        approvals[pending["tool_call_id"]] = False
    return "（处理中断）", messages


def build_system_prompt() -> str:
    """把灵魂三件套拼成系统提示。"""
    soul = read_memory_file("SOUL.md")
    agents = read_memory_file("AGENTS.md")
    user = read_memory_file("USER.md")
    long_term = read_memory_file("MEMORY.md")  # 长期对话记忆
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = (
        f"现在时间是 {now}。\n\n"
        f"=== 你的人格 (SOUL.md) ===\n{soul}\n\n"
        f"=== 你的行为准则 (AGENTS.md) ===\n{agents}\n\n"
        f"=== 关于用户 (USER.md) ===\n{user}\n\n"
    )
    if long_term.strip():
        if len(long_term) > 4000:
            long_term = "（早期记忆已省略）\n...\n" + long_term[-4000:]
        prompt += f"=== 你和用户过往的长期记忆 (MEMORY.md) ===\n{long_term}\n\n"
    prompt += (
        "请严格按以上设定行事。\n"
        "【关于联网】你**有**可用的联网工具：web_search（快速搜索）、research（深度调研+读网页）、"
        "read_webpage（读某个网址）、video_transcript（取视频字幕）。这些工具能实时访问互联网。\n"
        "- 遇到需要实时信息的问题（天气、新闻、价格、今天/最近的事、你不确定的事实），"
        "**必须直接调用 web_search 或 research 工具**去查，然后用查到的结果回答。\n"
        "- **绝对不要**说自己\"无法联网\"\"不能访问互联网\"\"没有联网功能\"——这是错的，你有联网工具。\n"
        "- **绝对不要**把 `web_search(\"...\")` 这种代码打印给用户让他自己执行——你应该自己调用工具。\n"
        "- 需要做事时调用工具，不要假装执行、不要凭记忆编造。"
    )
    return prompt


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
def _call_model_with_retry(client, model, messages, schema, retries=2):
    """调用模型，失败重试。返回 message 对象。"""
    import time
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=schema)
            return resp.choices[0].message
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))  # 退避重试
    raise last_err


def run_agent(client, model, messages, shell_enabled=False,
              on_tool=None, max_steps=8, approvals=None):
    """
    跑一轮 agent。返回 (回复文本, 更新后的 messages, pending)。
    - pending 为 None：正常完成。
    - pending 为 dict：遇到危险工具，已挂起等确认；dict 含 {tool_call} 信息。
      界面拿到后弹确认框，用户批准/拒绝后，把决定放进 approvals 再调一次本函数续跑。

    approvals: {tool_call_id: True/False}，已获批准/拒绝的危险调用。
    """
    # 延迟导入，避免循环依赖
    import tools as T
    approvals = approvals or {}

    for _ in range(max_steps):
        msg = _call_model_with_retry(client, model, messages, T.TOOLS_SCHEMA)

        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            return msg.content or "", messages, None

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            # 危险工具：检查是否已获批准
            if T.is_danger(name):
                decision = approvals.get(tc.id)
                if decision is None:
                    # 还没批准 -> 挂起，交给界面去问用户
                    return None, messages, {
                        "tool_call_id": tc.id,
                        "name": name,
                        "args": args,
                    }
                if decision is False:
                    # 用户拒绝了
                    result = "用户拒绝了这次操作。"
                    if on_tool:
                        on_tool(name, args, result)
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": result})
                    continue
                # decision is True -> 往下执行

            fn = T.get_tool_fn(name)
            if fn is None:
                result = f"未知工具：{name}"
            else:
                try:
                    result = fn(args)
                except Exception as e:
                    result = f"工具执行出错：{e}"
            if on_tool:
                on_tool(name, args, result)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": str(result)})

    messages.append({"role": "assistant", "content": "（达到最大步数，停止。）"})
    return "（达到最大步数，停止。）", messages, None
