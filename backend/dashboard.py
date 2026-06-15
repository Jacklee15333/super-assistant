"""
dashboard.py — 情报看板数据汇总

从已有的存档文件里读出看板要展示的内容：
- 最新一份情报简报
- 历史简报列表
- 竞品监控状态（监控了哪些、上次抓取概况）
- 待办提醒清单
- 今日笔记

只读，不改任何东西。
"""

import datetime
from pathlib import Path

from agent_core import MEMORY_DIR, read_memory_file

BRIEF_DIR = MEMORY_DIR / "briefings"
SNAP_DIR = MEMORY_DIR / "snapshots"


def _latest_briefing():
    """取最新一份简报的内容和时间。"""
    if not BRIEF_DIR.exists():
        return None
    files = sorted(BRIEF_DIR.glob("brief-*.md"), reverse=True)
    if not files:
        return None
    f = files[0]
    return {
        "filename": f.name,
        "content": f.read_text(encoding="utf-8", errors="replace"),
        "time": datetime.datetime.fromtimestamp(
            f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        "count": len(files),
    }


def _competitor_status():
    """竞品监控概况：监控目标 + 已有快照数。"""
    raw = read_memory_file("competitors.md")
    targets = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if "|" in line:
            url, note = line.split("|", 1)
            url, note = url.strip(), note.strip()
        else:
            url, note = line, ""
        if url.startswith(("http://", "https://")):
            targets.append({"url": url, "note": note})
    snap_count = len(list(SNAP_DIR.glob("snap-*.txt"))) if SNAP_DIR.exists() else 0
    return {"targets": targets, "snapshot_count": snap_count}


def _reminders():
    return read_memory_file("reminders.md") or "（还没有提醒）"


def _today_note():
    today = datetime.date.today().isoformat()
    return read_memory_file(f"note-{today}.md") or "（今天还没有笔记）"


def _watchlist():
    """情报关注的关键词。"""
    raw = read_memory_file("watchlist.md")
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if line:
            items.append(line)
    return items


def get_dashboard():
    """汇总看板所有数据。"""
    return {
        "latest_briefing": _latest_briefing(),
        "competitors": _competitor_status(),
        "watchlist": _watchlist(),
        "reminders": _reminders(),
        "today_note": _today_note(),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
