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


# ════════════════════════════════════════════════════════════════════
# 知识云图用：列出/读取/保存对话存档（durable，本地永久）
# 存档就是 memory/conversations/conv-*.md（人类可读）。
# 「会话」在前端是内存里的，这里给它一个落盘的家，于是聊过的都能进云图。
# ════════════════════════════════════════════════════════════════════
import re as _re


def _strip_md(text):
    """把 markdown 记号去掉，留下干净文字（给关键词/摘要用）。"""
    t = text or ""
    t = _re.sub(r"```[\s\S]*?```", " ", t)            # 代码块
    t = _re.sub(r"`[^`]*`", " ", t)                    # 行内代码
    t = _re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", t)      # 图片/链接
    t = _re.sub(r"https?://\S+", " ", t)               # 裸链接
    t = _re.sub(r"[#*>`_~|>-]", " ", t)                 # 记号
    t = _re.sub(r"\s+", " ", t)
    return t.strip()


def _parse_conv_file(path):
    """读一个 conv-*.md，解析出 {id, title, when, when_human, turns, chars, preview, text}。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return None
    lines = raw.splitlines()
    title = ""
    when_human = ""
    # 第一行通常是 "# 对话存档 2026-06-18 12:04" 或自定义标题
    if lines and lines[0].startswith("#"):
        head = lines[0].lstrip("#").strip()
        m = _re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", head)
        if m:
            when_human = m.group(1)
            title = head.replace("对话存档", "").replace(when_human, "").strip()
        else:
            title = head
    # 从文件名取时间戳 conv-YYYYMMDD-HHMMSS
    stem = path.stem
    mt = _re.search(r"(\d{8})-(\d{6})", stem)
    when_iso = ""
    if mt:
        d, t = mt.group(1), mt.group(2)
        when_iso = "%s-%s-%sT%s:%s:%s" % (d[:4], d[4:6], d[6:8], t[:2], t[2:4], t[4:6])
        if not when_human:
            when_human = "%s-%s-%s %s:%s" % (d[:4], d[4:6], d[6:8], t[:2], t[2:4])
    # 正文（去掉首个标题行）
    body = raw
    if lines and lines[0].startswith("#"):
        body = "\n".join(lines[1:]).strip()
    clean = _strip_md(body)
    # 轮数：数 "**你**" 出现次数（user 轮）
    turns = body.count("**你**") or body.count("用户：") or 1
    # 标题兜底：取正文里第一句用户的话
    if not title:
        mu = _re.search(r"\*\*你\*\*[：:]\s*(.+)", body)
        first = mu.group(1).strip() if mu else clean[:24]
        title = (first[:24] or "未命名对话")
    title = _re.sub(r"[\s·\-—|]+$", "", title).strip() or "未命名对话"
    preview = clean[:120]
    starred = "<!-- starred -->" in raw
    return {
        "id": stem,                      # 用文件名做 id
        "title": title[:60],
        "when": when_iso,
        "when_human": when_human,
        "turns": turns,
        "chars": len(clean),
        "preview": preview,
        "starred": starred,
        "text": clean,                   # 给关键词提取用（已去 markdown）
    }


def list_conversations(limit=500, with_text=True):
    """列出所有对话存档（按时间倒序）。with_text=False 时不返回正文，省流量。"""
    items = []
    try:
        files = list(CONV_DIR.glob("conv-*.md")) + list(CONV_DIR.glob("sess-*.md"))
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        files = []
    for p in files[:max(1, int(limit))]:
        info = _parse_conv_file(p)
        if not info:
            continue
        if not with_text:
            info.pop("text", None)
        items.append(info)
    return items


def read_conversation(conv_id):
    """读一段对话存档的完整 markdown 正文（用于点开回看 / 回到那段对话继续）。"""
    cid = _re.sub(r"[^A-Za-z0-9_\-]", "", conv_id or "")
    if not cid:
        return None
    p = CONV_DIR / (cid + ".md")
    if not p.exists():
        return None
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        return None
    info = _parse_conv_file(p) or {}
    # 把正文解析回 messages（你/超能小助 交替），方便前端「回到那段对话」直接灌回去
    msgs = []
    for blk in _re.split(r"\n\s*\n", raw):
        blk = blk.strip()
        if blk.startswith("**你**"):
            msgs.append({"role": "user", "content": _re.sub(r"^\*\*你\*\*[：:]\s*", "", blk)})
        elif blk.startswith("**超能小助**"):
            msgs.append({"role": "assistant", "content": _re.sub(r"^\*\*超能小助\*\*[：:]\s*", "", blk)})
    return {"id": cid, "title": info.get("title", ""), "raw": raw,
            "when_human": info.get("when_human", ""), "messages": msgs}


def save_session(session_id, title, messages, starred=None):
    """把前端某个「会话」落盘成存档（聊过的就进云图，不只「结束并记住」的那种）。
    用 session_id 当稳定文件名：同一会话反复保存只更新同一个文件，不会越存越多。
    返回 {ok, id}。"""
    sid = _re.sub(r"[^A-Za-z0-9_\-]", "", str(session_id or "")) or \
        ("sess-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    fname = sid if sid.startswith(("conv-", "sess-")) else ("sess-" + sid)
    lines = []
    for m in (messages or []):
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "user" and content:
            lines.append(f"**你**：{content}")
        elif role == "assistant" and content:
            lines.append(f"**超能小助**：{content}")
    if not lines:
        return {"ok": False, "message": "空对话，不保存"}
    ts = datetime.datetime.now()
    ttl = (title or "").strip() or "对话存档"
    header = f"# {ttl} · {ts.strftime('%Y-%m-%d %H:%M')}\n"
    if starred:
        header += "<!-- starred -->\n"
    header += "\n"
    try:
        (CONV_DIR / (fname + ".md")).write_text(header + "\n\n".join(lines), encoding="utf-8")
    except Exception as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "id": fname}


def delete_conversation(conv_id):
    cid = _re.sub(r"[^A-Za-z0-9_\-]", "", conv_id or "")
    if not cid:
        return {"ok": False}
    p = CONV_DIR / (cid + ".md")
    try:
        if p.exists():
            p.unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "message": str(e)}
