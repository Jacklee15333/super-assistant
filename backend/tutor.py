"""
tutor.py — 英语学习辅导

让助手像老师的助教一样，基于老师的真实教材辅导学生：
- 教材库：读 backend/教材/ 下的资料，出题/讲解都基于这些，不让 AI 瞎编
- 学生档案：记录进度、错题本、掌握度，实现因材施教
- 四种能力：出题批改、单词听写陪练、语法答疑、每日任务

定位：老师的助教 / 学生的陪练。能减轻重复劳动，但不能替代真正的老师，
也可能偶尔讲错（尤其本地小模型），关键处仍需老师把关。
"""

import re
import json
import datetime
from pathlib import Path

import agent_core

BACKEND_DIR = agent_core.MEMORY_DIR.parent
TEXTBOOK_DIR = BACKEND_DIR / "教材"
STUDENT_DIR = BACKEND_DIR / "学生档案"
TEXTBOOK_DIR.mkdir(exist_ok=True)
STUDENT_DIR.mkdir(exist_ok=True)


# ---------- 教材库 ----------
def list_textbooks():
    """列出教材文件。"""
    files = [p.name for p in sorted(TEXTBOOK_DIR.glob("*"))
             if p.suffix in (".md", ".txt") and p.name != "使用说明.md"]
    return files


def read_textbook(name):
    """读一份教材内容。"""
    # 安全：限定在教材目录内
    if "/" in name or "\\" in name or ".." in name:
        return ""
    p = TEXTBOOK_DIR / name
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def load_all_textbooks(max_chars=8000):
    """把所有教材拼起来（供出题/讲解用），控制长度。"""
    chunks = []
    for name in list_textbooks():
        content = read_textbook(name)
        if content:
            chunks.append(f"=== 教材：{name} ===\n{content}")
    return "\n\n".join(chunks)[:max_chars]


def tool_list_textbooks(_args=None):
    """工具：列出有哪些教材。"""
    files = list_textbooks()
    return "\n".join(files) if files else "（教材库还是空的，请老师往 教材/ 文件夹放资料）"


def tool_read_textbook(args):
    """工具：读某份教材。"""
    return read_textbook(args.get("name", "")) or "（找不到这份教材）"


# ---------- 学生档案 ----------
def _student_path(student):
    safe = re.sub(r"[^\w\u4e00-\u9fff-]", "_", student)[:40] or "default"
    return STUDENT_DIR / f"{safe}.json"


def load_student(student):
    """读学生档案，没有就建一个空的。"""
    p = _student_path(student)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": student, "created": datetime.date.today().isoformat(),
            "progress": "", "mastered_words": [], "weak_words": [],
            "wrong_questions": [], "notes": ""}


def save_student(data):
    p = _student_path(data.get("name", "default"))
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def tool_get_student(args):
    """工具：查学生档案（进度、错题、掌握度）。"""
    data = load_student(args.get("student", "default"))
    return json.dumps(data, ensure_ascii=False, indent=2)


def tool_update_student(args):
    """工具：更新学生档案。可更新进度、加错题、加生词等。"""
    student = args.get("student", "default")
    data = load_student(student)
    if args.get("progress"):
        data["progress"] = args["progress"]
    if args.get("add_wrong"):
        data["wrong_questions"].append({
            "q": args["add_wrong"],
            "date": datetime.date.today().isoformat()})
        data["wrong_questions"] = data["wrong_questions"][-50:]  # 最多存50
    if args.get("add_weak_word"):
        w = args["add_weak_word"]
        if w not in data["weak_words"]:
            data["weak_words"].append(w)
    if args.get("add_mastered_word"):
        w = args["add_mastered_word"]
        if w not in data["mastered_words"]:
            data["mastered_words"].append(w)
        if w in data["weak_words"]:
            data["weak_words"].remove(w)
    if args.get("note"):
        data["notes"] = (data.get("notes", "") + "\n" + args["note"]).strip()
    save_student(data)
    return f"已更新 {student} 的档案。"


# ---------- 每日任务 ----------
DAILY_PROMPT = (
    "你是英语老师的助教。请基于下面老师的真实教材，为学生「{student_name}」"
    "生成今天的学习任务。要求：\n"
    "1. 难度适中，量适当（约 15-20 分钟能完成）。\n"
    "2. 结合学生的薄弱点（见档案）有侧重。\n"
    "3. 任务包括：几个单词复习、一两个语法练习、一小段翻译或造句。\n"
    "4. 只用教材里出现的内容，不要超纲。\n"
    "5. 用鼓励的语气，中文说明，题目该用英文的用英文。\n\n"
    "=== 老师的教材 ===\n{textbooks}\n\n"
    "=== 学生档案（薄弱点重点照顾）===\n{student_data}\n"
)


def generate_daily_task(student="default", use_local=True, model="qwen2.5"):
    """生成今天的学习任务。"""
    textbooks = load_all_textbooks()
    if not textbooks.strip():
        return "（教材库是空的，请老师先往 教材/ 文件夹放资料。）"
    sdata = load_student(student)
    try:
        # ★ make_client_for：model=='web' → 网页大模型客户端（驱动网页 AI 卡片），
        #   避免把 'web' 当普通模型名发给本地/云端接口而报 model 'web' not found。
        client = agent_core.make_client_for(model, use_local)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": DAILY_PROMPT.format(
                student_name=student,
                textbooks=textbooks,
                student_data=json.dumps(sdata, ensure_ascii=False))}],
        )
        task = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"生成任务出错：{e}"

    # 存档今天的任务
    today = datetime.date.today().isoformat()
    task_file = STUDENT_DIR / f"{student}_task_{today}.md"
    task_file.write_text(f"# {student} 的今日任务 {today}\n\n{task}",
                         encoding="utf-8")

    # 推到手机
    try:
        import push_serverchan
        push_serverchan.push(f"今日英语任务（{student}）", task[:1800])
    except Exception:
        pass
    return task
