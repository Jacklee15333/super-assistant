"""
tools.py — 集中的工具定义，含安全分级

每个工具标注 danger 等级：
  "safe"   —— 只读/无副作用，直接执行（查时间、算数、搜索、读文件…）
  "danger" —— 有副作用，需用户确认（写文件、删文件、跑命令、发邮件…）

危险工具不在这里直接执行；run_agent 检测到危险工具会挂起，
等界面把用户的"批准/拒绝"传回来再执行。这样 AI 永远无法绕过你动危险操作。
"""

import os
import json
import glob
import datetime
import subprocess
from pathlib import Path

from agent_core import (
    MEMORY_DIR, read_memory_file, write_memory_file, append_note,
    tool_get_time, tool_calc, tool_read_memory, tool_write_memory,
    tool_append_note, tool_list_memory, tool_web_search,
)
from web_tools import (
    tool_read_webpage, tool_search_web, tool_research,
)
from video_tools import (
    tool_video_transcript,
)
from tutor import (
    tool_list_textbooks, tool_read_textbook,
    tool_get_student, tool_update_student,
)

# 工作区根：允许读写的本地目录边界（默认 memory 的上级，即 backend/）
WORKSPACE = MEMORY_DIR.parent
# 给"读写任意文件"工具一个更宽的边界：用户主目录下的一个专属文件夹
FILES_ROOT = Path(os.environ.get(
    "ASSISTANT_FILES_ROOT", str(Path.home() / "超能小助文件"))).resolve()
FILES_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_path(rel):
    """把相对路径限制在 FILES_ROOT 内，防止越界（../ 逃逸）。"""
    p = (FILES_ROOT / rel).resolve()
    if not str(p).startswith(str(FILES_ROOT)):
        raise ValueError("路径越界，拒绝访问。")
    return p


# ---------- 新增：本地文件读写（带边界） ----------
def tool_read_file(args):
    """读取工作区文件。"""
    try:
        p = _safe_path(args.get("path", ""))
        if not p.exists():
            return f"文件不存在：{args.get('path')}"
        if p.stat().st_size > 1_000_000:
            return "文件太大（>1MB），拒绝读取。"
        return p.read_text(encoding="utf-8", errors="replace")[:8000]
    except Exception as e:
        return f"读取出错：{e}"


def tool_write_file(args):
    """写入工作区文件（危险：会落盘）。"""
    try:
        p = _safe_path(args.get("path", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args.get("content", ""), encoding="utf-8")
        return f"已写入 {args.get('path')}（{len(args.get('content',''))} 字符）"
    except Exception as e:
        return f"写入出错：{e}"


def tool_list_files(args):
    """列出工作区某目录下的文件。"""
    try:
        sub = args.get("path", "")
        base = _safe_path(sub) if sub else FILES_ROOT
        if not base.exists():
            return "目录不存在。"
        items = []
        for p in sorted(base.iterdir()):
            tag = "/" if p.is_dir() else ""
            items.append(p.name + tag)
        return "\n".join(items) if items else "（空目录）"
    except Exception as e:
        return f"列目录出错：{e}"


def tool_search_files(args):
    """在工作区按文件名关键词搜索。"""
    try:
        kw = args.get("keyword", "").strip()
        if not kw:
            return "拒绝：关键词为空。"
        hits = []
        for p in FILES_ROOT.rglob("*"):
            if p.is_file() and kw.lower() in p.name.lower():
                hits.append(str(p.relative_to(FILES_ROOT)))
                if len(hits) >= 50:
                    break
        return "\n".join(hits) if hits else f"没找到含“{kw}”的文件。"
    except Exception as e:
        return f"搜索出错：{e}"


def tool_delete_file(args):
    """删除工作区文件（危险）。"""
    try:
        p = _safe_path(args.get("path", ""))
        if not p.exists():
            return "文件不存在。"
        if p.is_dir():
            return "拒绝：这是目录，本工具只删单个文件。"
        p.unlink()
        return f"已删除 {args.get('path')}"
    except Exception as e:
        return f"删除出错：{e}"


# ---------- 新增：定时任务 ----------
def tool_add_reminder(args):
    """添加一个定时提醒，写进 memory/reminders.md，由心跳检查触发。"""
    when = args.get("when", "").strip()
    what = args.get("what", "").strip()
    if not when or not what:
        return "拒绝：需要 when（如 '2026-06-14 09:00' 或 '每天 09:00'）和 what。"
    line = f"- [ ] {when} | {what}\n"
    p = MEMORY_DIR / "reminders.md"
    if not p.exists():
        p.write_text("# 定时提醒\n\n心跳会检查这里，到点的提醒会通知你。\n\n",
                     encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(line)
    return f"已添加提醒：{when} | {what}"


def tool_list_reminders(_args=None):
    return read_memory_file("reminders.md") or "（还没有提醒）"


# ---------- shell（危险） ----------
def tool_shell(args):
    cmd = args.get("command", "")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=30)
        out = (r.stdout or "") + (r.stderr or "")
        return out.strip()[:4000] or "（无输出）"
    except Exception as e:
        return f"执行出错：{e}"


# ---------- 工具表：函数 + 危险等级 ----------
# 每项：(函数, 危险等级)
TOOL_REGISTRY = {
    # 安全（直接执行）
    "get_time": (tool_get_time, "safe"),
    "calc": (tool_calc, "safe"),
    "read_memory": (tool_read_memory, "safe"),
    "list_memory": (tool_list_memory, "safe"),
    "web_search": (tool_web_search, "safe"),
    "search_web": (tool_search_web, "safe"),
    "read_webpage": (tool_read_webpage, "safe"),
    "research": (tool_research, "safe"),
    "video_transcript": (tool_video_transcript, "safe"),
    "list_textbooks": (tool_list_textbooks, "safe"),
    "read_textbook": (tool_read_textbook, "safe"),
    "get_student": (tool_get_student, "safe"),
    "update_student": (tool_update_student, "safe"),
    "read_file": (tool_read_file, "safe"),
    "list_files": (tool_list_files, "safe"),
    "search_files": (tool_search_files, "safe"),
    "list_reminders": (tool_list_reminders, "safe"),
    "append_note": (tool_append_note, "safe"),
    "add_reminder": (tool_add_reminder, "safe"),
    # 危险（需用户确认）
    "write_memory": (tool_write_memory, "danger"),
    "write_file": (tool_write_file, "danger"),
    "delete_file": (tool_delete_file, "danger"),
    "shell": (tool_shell, "danger"),
}

DANGER_TOOLS = {k for k, (_, lvl) in TOOL_REGISTRY.items() if lvl == "danger"}


def get_tool_fn(name):
    entry = TOOL_REGISTRY.get(name)
    return entry[0] if entry else None


def is_danger(name):
    return name in DANGER_TOOLS


# ---------- 给模型看的 schema ----------
TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "get_time", "description": "获取当前日期和时间",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "calc", "description": "计算一个数学表达式",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "read_memory", "description": "读取 memory 目录下的 Markdown 文件",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "list_memory", "description": "列出 memory 目录下所有文件",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "web_search", "description": "联网搜索实时信息（简单查询用）",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "search_web", "description": "联网搜索，返回多条结果的标题和链接（找资料用）",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "description": "返回几条，默认5"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_webpage", "description": "打开一个网址，读取它的正文内容",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "research", "description": "深度调研：搜索一个主题并自动读取前几个网页正文后汇总。找信息、做功课、研究痛点商机时用",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "调研主题/关键词"},
            "read_count": {"type": "integer", "description": "读取几个网页，默认3"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "video_transcript", "description": "取一个视频的文字稿（字幕），支持 YouTube、Bilibili 的公开字幕。用户发视频链接想要文字版或总结视频内容时用。抖音/快手没有公开字幕接口，会如实说明并给替代办法",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "视频链接"}},
            "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "list_textbooks", "description": "列出教材库里有哪些资料（英语辅导用）",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_textbook", "description": "读取某份教材的内容。出题、讲解前先读教材，基于真实教材而非凭空编",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "get_student", "description": "查学生档案：进度、错题本、薄弱单词、掌握的词",
        "parameters": {"type": "object", "properties": {
            "student": {"type": "string", "description": "学生名"}}}}},
    {"type": "function", "function": {
        "name": "update_student", "description": "更新学生档案：记录进度、加错题、标记生词或已掌握的词",
        "parameters": {"type": "object", "properties": {
            "student": {"type": "string"},
            "progress": {"type": "string", "description": "学习进度描述"},
            "add_wrong": {"type": "string", "description": "加一道错题"},
            "add_weak_word": {"type": "string", "description": "标记一个没掌握的词"},
            "add_mastered_word": {"type": "string", "description": "标记一个已掌握的词"},
            "note": {"type": "string", "description": "备注"}},
            "required": ["student"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "读取工作区文件（你的专属文件夹内）",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "相对路径"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "list_files", "description": "列出工作区目录内容",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "相对路径，留空为根"}}}}},
    {"type": "function", "function": {
        "name": "search_files", "description": "按文件名关键词搜索工作区",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"}}, "required": ["keyword"]}}},
    {"type": "function", "function": {
        "name": "append_note", "description": "把一句话追加到今天的笔记",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "add_reminder", "description": "添加定时提醒，到点由心跳通知",
        "parameters": {"type": "object", "properties": {
            "when": {"type": "string", "description": "时间，如 2026-06-14 09:00 或 每天 09:00"},
            "what": {"type": "string", "description": "提醒内容"}},
            "required": ["when", "what"]}}},
    {"type": "function", "function": {
        "name": "list_reminders", "description": "查看所有定时提醒",
        "parameters": {"type": "object", "properties": {}}}},
    # 危险工具（模型可调用，但执行前会被挂起等用户确认）
    {"type": "function", "function": {
        "name": "write_memory", "description": "写入/覆盖 memory 目录下的文件（危险，需确认）",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "content": {"type": "string"}},
            "required": ["name", "content"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "写入工作区文件（危险，需确认）",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "delete_file", "description": "删除工作区文件（危险，需确认）",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "shell", "description": "执行 shell 命令（危险，需确认）",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
]
