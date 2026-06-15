"""
conversation_memory.py — 长期对话记忆

解决的问题：大模型本身没记忆，关掉对话就忘。
做法：
1. 每段对话存档为 memory/conversations/conv-<时间>.md（人类可读的纯文本）
2. 维护一份 memory/MEMORY.md —— 用模型把对话压成几条要点，累积成"长期记忆"
3. 每次新对话开始，把 MEMORY.md 注入系统提示，于是超能小助"记得"之前

全部纯文本存本地，你随时能看、能删、能改。
"""

import datetime
from pathlib import Path

from agent_core import MEMORY_DIR, read_memory_file

CONV_DIR = MEMORY_DIR / "conversations"
CONV_DIR.mkdir(exist_ok=True)
MEMORY_FILE = "MEMORY.md"


def save_conversation(messages):
    """把一段对话存档为 Markdown。"""
    lines = []
    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "user" and content:
            lines.append(f"**你**：{content}")
        elif role == "assistant" and content:
            lines.append(f"**超能小助**：{content}")
    if not lines:
        return None

    ts = datetime.datetime.now()
    fname = f"conv-{ts.strftime('%Y%m%d-%H%M%S')}.md"
    header = f"# 对话存档 {ts.strftime('%Y-%m-%d %H:%M')}\n\n"
    (CONV_DIR / fname).write_text(header + "\n\n".join(lines), encoding="utf-8")
    return fname


def _conversation_text(messages):
    parts = []
    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "user" and content:
            parts.append(f"用户：{content}")
        elif role == "assistant" and content:
            parts.append(f"助手：{content}")
    return "\n".join(parts)


SUMMARY_PROMPT = (
    "下面是一段你和用户的对话。请提炼出值得长期记住的要点，"
    "比如：用户的偏好、习惯、正在做的事、做过的决定、需要后续跟进的事。\n"
    "用简短的中文 bullet（每条一行，以 - 开头）输出，不要寒暄、不要复述全文。"
    "如果这段对话没什么值得长期记的，只回复一个词：无。\n\n"
    "=== 对话 ===\n{conv}\n"
)


def update_long_term_memory(client, model, messages):
    """用模型把对话压成要点，追加进 MEMORY.md。失败不影响主流程。"""
    conv = _conversation_text(messages)
    if not conv.strip():
        return None
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": SUMMARY_PROMPT.format(conv=conv)}],
        )
        summary = (resp.choices[0].message.content or "").strip()
    except Exception:
        return None

    if not summary or summary.strip() == "无":
        return None

    today = datetime.date.today().isoformat()
    block = f"\n## {today}\n{summary}\n"
    p = MEMORY_DIR / MEMORY_FILE
    if not p.exists():
        p.write_text("# 长期记忆\n\n我会把跨对话值得记住的事累积在这里。\n",
                     encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(block)
    return summary


def get_memory_for_prompt():
    text = read_memory_file(MEMORY_FILE)
    if not text:
        return ""
    if len(text) > 4000:
        text = "（早期记忆已省略）\n...\n" + text[-4000:]
    return text
