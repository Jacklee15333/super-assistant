"""
tools.py — 集中的工具定义，含安全分级

每个工具标注 danger 等级：
  "safe"   —— 只读/无副作用，直接执行（查时间、算数、搜索、读文件…）
  "danger" —— 有副作用，需用户确认（写文件、删文件、跑命令、发邮件…）

危险工具不在这里直接执行；run_agent 检测到危险工具会挂起，
等界面把用户的"批准/拒绝"传回来再执行。这样 AI 永远无法绕过你动危险操作。

★ 2026-06 新增「电脑操作权限」总开关（system_tools）：
  · 开关关闭（默认）：下面的文件读写被锁回沙箱 FILES_ROOT；system_tools 里的
    真实文件系统 / 系统设置 / GUI / 看屏幕等工具一律拒绝。shell 也被冻结。
  · 开关开启：read_file/write_file 等可访问任意路径；system_tools 全部解冻；
    破坏性操作仍逐次弹窗确认。开关由界面右上角按钮控制。
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
    tool_remember,
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

# ★ 电脑操作权限 + 全套电脑操作工具
import system_tools

# 工作区根：允许读写的本地目录边界（默认 memory 的上级，即 backend/）
WORKSPACE = MEMORY_DIR.parent
# 给"读写任意文件"工具一个更宽的边界：用户主目录下的一个专属文件夹
FILES_ROOT = Path(os.environ.get(
    "ASSISTANT_FILES_ROOT", str(Path.home() / "超能小助文件"))).resolve()
FILES_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_path(rel):
    """
    解析路径，边界由「电脑操作权限」开关决定：
      · 权限开启 → 允许任意绝对路径 / ~ / 相对 FILES_ROOT（可动真实桌面、下载、D盘）。
      · 权限关闭 → 死锁在 FILES_ROOT 沙箱内，越界即拒绝。
    """
    rel = rel or ""
    if system_tools.is_enabled():
        p = Path(os.path.expanduser(os.path.expandvars(rel)))
        if not p.is_absolute():
            p = FILES_ROOT / rel
        return p.resolve()
    # 权限关闭：锁回沙箱
    p = (FILES_ROOT / rel).resolve()
    if not str(p).startswith(str(FILES_ROOT)):
        raise ValueError("路径越界，拒绝访问。要操作沙箱外的真实文件，"
                         "请先在界面右上角打开「电脑操作权限」开关。")
    return p


# ---------- 本地文件读写（边界随开关变化） ----------
def tool_read_file(args):
    """读取文件。权限关→只能读沙箱；权限开→可读任意路径。"""
    try:
        p = _safe_path(args.get("path", ""))
        if not p.exists():
            return f"文件不存在：{args.get('path')}"
        if p.is_dir():
            return "这是目录。权限开启后可用 fs_list 列目录。"
        if p.stat().st_size > 1_000_000:
            return "文件太大（>1MB），拒绝读取。"
        return p.read_text(encoding="utf-8", errors="replace")[:8000]
    except Exception as e:
        return f"读取出错：{e}"


def tool_write_file(args):
    """写入文件（危险：会落盘）。权限关→只能写沙箱；权限开→可写任意路径。"""
    try:
        p = _safe_path(args.get("path", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args.get("content", ""), encoding="utf-8")
        return f"已写入 {p}（{len(args.get('content',''))} 字符）"
    except Exception as e:
        return f"写入出错：{e}"


def tool_list_files(args):
    """列出某目录下的文件。权限关→沙箱内；权限开→任意目录。"""
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
    """在沙箱内按文件名关键词搜索（要搜真实任意目录，权限开后用 fs_search）。"""
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
    """删除文件（危险）。权限关→沙箱内；权限开→任意路径（建议优先用 fs_trash 进回收站）。"""
    try:
        p = _safe_path(args.get("path", ""))
        if not p.exists():
            return "文件不存在。"
        if p.is_dir():
            return "拒绝：这是目录，本工具只删单个文件。"
        p.unlink()
        return f"已删除 {p}"
    except Exception as e:
        return f"删除出错：{e}"


# ---------- 定时任务 ----------
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


# ---------- 技能：加载某个技能的完整方法（渐进式披露）----------
def tool_load_skill(args):
    """按名字/slug 把某个技能的完整正文读进来。系统提示里已列出有哪些技能，
    模型判断当前任务匹配某技能时调它，拿到完整步骤后照着做。"""
    name = (args or {}).get("name") or (args or {}).get("slug") or ""
    try:
        import skills_store
        return skills_store.load_skill_body(name)
    except Exception as e:
        return f"加载技能失败：{e}"


# ---------- shell（危险 + 受电脑操作权限闸门）----------
def tool_shell(args):
    if not system_tools.is_enabled():
        return ("拒绝：电脑操作权限未开启，shell 已冻结。"
                "请点界面右上角的「电脑操作权限」开关打开后再用。")
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
    "remember": (tool_remember, "safe"),
    "add_reminder": (tool_add_reminder, "safe"),
    "load_skill": (tool_load_skill, "safe"),
    # 危险（需用户确认）
    "write_memory": (tool_write_memory, "danger"),
    "write_file": (tool_write_file, "danger"),
    "delete_file": (tool_delete_file, "danger"),
    "shell": (tool_shell, "danger"),
}

# ★ 合并「电脑操作权限」下的全套电脑操作工具（真实文件系统 / 系统 / GUI / 看屏幕）
TOOL_REGISTRY.update(system_tools.SYSTEM_TOOLS)

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
        "name": "video_transcript", "description": "取一个视频的完整文字稿。YouTube/B站优先取公开字幕；抖音、快手、小红书等没有字幕的视频，会自动用本机的语音识别（faster-whisper）把音频转成文字。**只要用户发来视频链接（哪怕是抖音整段分享文案），或想要某个视频的文字版/总结/文案/讲了什么，就直接调用这个工具**。不要用 web_search 去搜视频链接——那样取不到内容。",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "视频链接，或包含链接的整段分享文案"}},
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
        "name": "read_file", "description": "读取文件。电脑操作权限开启后可读任意路径（桌面/下载/D盘），关闭时只能读沙箱",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "权限开后可写绝对路径，如 C:\\\\Users\\\\me\\\\Desktop\\\\a.txt"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "list_files", "description": "列出目录内容。权限开后可列任意目录",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "路径，留空为沙箱根"}}}}},
    {"type": "function", "function": {
        "name": "search_files", "description": "在沙箱内按文件名搜索（搜真实任意目录用 fs_search）",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"}}, "required": ["keyword"]}}},
    {"type": "function", "function": {
        "name": "append_note", "description": "把一句话追加到今天的笔记",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "remember", "description": "记住一条关于用户的长期信息（他的偏好、习惯、正在做的项目、重要决定、希望你怎么跟他相处等）。当你在对话中了解到值得长期记住的事，就主动调用——记下后以后每次对话都会自动想起，越用越懂他。只记真正持久有用的，不要记一次性的琐事。",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description": "要长期记住的那条信息，一句话说清"}},
            "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "add_reminder", "description": "添加定时提醒，到点由心跳通知",
        "parameters": {"type": "object", "properties": {
            "when": {"type": "string", "description": "时间，如 2026-06-14 09:00 或 每天 09:00"},
            "what": {"type": "string", "description": "提醒内容"}},
            "required": ["when", "what"]}}},
    {"type": "function", "function": {
        "name": "list_reminders", "description": "查看所有定时提醒",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "load_skill", "description": "加载一个「技能」的完整方法步骤。系统提示的「技能库」里列出了你掌握哪些技能及各自适用场景。当用户的任务匹配某个技能时，先调用本工具把该技能的完整步骤读进来，再照着做（不要凭记忆瞎做）。一次只加载当前真正用得上的那一个。",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "要加载的技能名或 slug（取自系统提示「技能库」清单里的名字）"}},
            "required": ["name"]}}},
    # 危险工具（模型可调用，但执行前会被挂起等用户确认）
    {"type": "function", "function": {
        "name": "write_memory", "description": "写入/覆盖 memory 目录下的文件（危险，需确认）",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "content": {"type": "string"}},
            "required": ["name", "content"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "写入文件（危险，需确认）。权限开后可写任意路径",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "delete_file", "description": "删除文件（危险，需确认）。权限开后可删任意路径，建议优先用 fs_trash 进回收站",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "shell", "description": "执行 shell 命令（危险，需确认，且需电脑操作权限开启）",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
]

# ★ 把「电脑操作权限」下的工具 schema 合并进来（真实文件系统/系统/GUI/看屏幕）
TOOLS_SCHEMA += system_tools.SYSTEM_SCHEMA

# ★ 智能路由：T3（高级分析/搜索/写作/总结）改走「伪模型」（网页 ChatGPT 自带联网搜索），
#   这些本地搜索类工具被取代，从模型可见的 schema 里移除，避免与伪模型的原生联网重复。
#   （函数本体保留；想恢复本地搜索，把名字从这里删掉即可。）
DISABLED_TOOLS = {"web_search", "search_web", "read_webpage", "research"}

TOOLS_SCHEMA = [t for t in TOOLS_SCHEMA
                if t.get("function", {}).get("name") not in DISABLED_TOOLS]
