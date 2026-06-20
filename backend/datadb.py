"""
datadb.py — 「🗄️ 数据库」：统一管理超能小助产生的所有数据

软件跑起来会在 memory/ 下攒下各种数据：视频笔记、情报简报、对话存档、画像记忆、
各种配置 json……以前散落在各处、只能去文件夹翻。这个模块把它们按类别归拢，
给前端一个「文件管理器」式的界面：看、预览、导出、删除。

安全分级（很重要，别让用户误删把软件搞坏）：
  · content（内容数据）  : 可看可删，随便操作。
  · memory （画像与记忆）: 可看可删，但删除前端会二次确认（核心记忆）。
  · config （配置与状态）: 默认只读；除非前端显式带 force=True，否则拒绝删除。

设计原则沿用全项目：标准库优先、全本机、失败安静降级、绝不把主流程搞崩。
所有路径操作都校验「解析后仍在允许目录内」，杜绝越权删除。
"""

import os
import json
import shutil
import datetime
from pathlib import Path

import agent_core as core


MEM = core.MEMORY_DIR
BACKEND = MEM.parent


# ════════════════════════════════════════════════════════════════════
#  数据源定义：每个「类别」→ 若干数据集（目录 glob 或单文件清单）
# ════════════════════════════════════════════════════════════════════
# safety: content / memory / config —— 决定能不能删、删前要不要警告。

def _groups():
    return [
        # ——— 内容数据（放心删）———
        {"key": "video",    "label": "视频笔记",   "icon": "🎬", "safety": "content",
         "dir": MEM / "video_notes",   "glob": "*.md"},
        {"key": "briefing", "label": "情报简报",   "icon": "📰", "safety": "content",
         "dir": MEM / "briefings",     "glob": "*.md"},
        {"key": "sniff",    "label": "嗅探简报",   "icon": "📡", "safety": "content",
         "dir": MEM / "sniff_reports", "glob": "*.md"},
        {"key": "research", "label": "主动研究",   "icon": "🌐", "safety": "content",
         "dir": MEM / "insight_research", "glob": "research-*.md"},
        {"key": "insight_report", "label": "洞察报告", "icon": "🔍", "safety": "content",
         "dir": MEM / "insight_reports", "glob": "insight-*.md"},
        {"key": "conversations", "label": "对话存档", "icon": "💬", "safety": "content",
         "dir": MEM / "conversations", "glob": "conv-*.md"},
        {"key": "notes",    "label": "每日笔记",   "icon": "📝", "safety": "content",
         "dir": MEM,                   "glob": "note-*.md"},
        {"key": "learning", "label": "学习档案",   "icon": "📚", "safety": "content",
         "dir": BACKEND / "学生档案",   "glob": "*"},
        {"key": "snapshots", "label": "嗅探快照",  "icon": "📸", "safety": "content",
         "dir": MEM / "snapshots",     "glob": "*"},
        {"key": "shots",    "label": "视频截图",   "icon": "🖼️", "safety": "content",
         "dir": MEM / "video_notes" / "shots", "glob": "*", "dirs_as_items": True},

        # ——— 画像与记忆（可删，但前端会二次确认）———
        {"key": "memory",   "label": "画像与记忆", "icon": "🧠", "safety": "memory",
         "dir": MEM, "files": [
             "OWNER_PROFILE.md", "MEMORY.md", "SOUL.md", "USER.md", "AGENTS.md",
             "ENVIRONMENT.md", "relationships.md", "evolution_log.md",
             "INSIGHT_DIGEST.md", "INSIGHT_LATEST.md", "watchlist.md",
             "competitors.md", "heartbeat.md"]},

        # ——— 配置与状态（默认只读，删除需 force）———
        {"key": "config",   "label": "配置与状态", "icon": "⚙️", "safety": "config",
         "dir": MEM, "glob": "*.json"},
    ]


def _group_by_key(key):
    for g in _groups():
        if g["key"] == key:
            return g
    return None


# ════════════════════════════════════════════════════════════════════
#  小工具
# ════════════════════════════════════════════════════════════════════

def _fmt_size(n):
    try:
        n = float(n)
    except Exception:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (int(n), unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024
    return "%.1f GB" % n


def _fmt_time(ts):
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def _dir_size(path):
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total


def _title_of(path):
    """从 md 文件首个非空标题行取标题；json/其它用文件名。"""
    try:
        if path.suffix.lower() == ".md":
            txt = path.read_text(encoding="utf-8", errors="replace")
            for line in txt.splitlines():
                s = line.strip().lstrip("#").strip().lstrip("*").strip()
                if s:
                    return s[:70]
    except Exception:
        pass
    return path.stem[:70]


def _tags_of(path):
    """解析 md 文件里用户自定义的二级标签（'- 标签：金融、逻辑' 这一行）。
    与成长库共用同一份文件里的标签，所以两边看到的标签一致。"""
    try:
        if path.suffix.lower() != ".md":
            return []
        txt = path.read_text(encoding="utf-8", errors="replace")
        import re as _re
        for line in txt.splitlines():
            s = line.strip().lstrip("-").strip()
            for key in ("标签：", "标签:"):
                if s.startswith(key):
                    raw = s[len(key):].strip()
                    parts = _re.split(r"[、，,\s]+", raw)
                    return [t.strip() for t in parts if t.strip()]
    except Exception:
        pass
    return []


def _preview_of(path):
    """取正文前一小段做预览（跳过标题/标签/分隔等元数据行）。"""
    try:
        if path.suffix.lower() != ".md":
            return ""
        txt = path.read_text(encoding="utf-8", errors="replace")
        body = []
        for line in txt.splitlines():
            s = line.strip()
            if (not s or s.startswith("#") or s.startswith("-")
                    or s.startswith("=") or s.startswith("---")
                    or s.startswith("**") or s.startswith(">") or s.startswith("|")):
                continue
            body.append(s)
            if sum(len(x) for x in body) > 80:
                break
        return (" ".join(body))[:100]
    except Exception:
        return ""


def _list_items(g):
    """列出一个数据集下的所有条目（文件或目录）。"""
    items = []
    d = g.get("dir")
    if not d or not Path(d).exists():
        return items
    paths = []
    try:
        if g.get("files"):
            for name in g["files"]:
                p = Path(d) / name
                if p.exists():
                    paths.append(p)
        elif g.get("dirs_as_items"):
            paths = [p for p in Path(d).iterdir() if p.is_dir()]
        else:
            paths = list(Path(d).glob(g.get("glob", "*")))
            paths = [p for p in paths if p.is_file()]
    except Exception:
        return items
    is_content = g.get("safety") == "content"
    for p in paths:
        try:
            st = p.stat()
            is_dir = p.is_dir()
            size = _dir_size(p) if is_dir else st.st_size
            item = {
                "name": p.name,
                "title": (p.name if is_dir else _title_of(p)),
                "is_dir": is_dir,
                "size": size,
                "size_h": _fmt_size(size),
                "mtime": st.st_mtime,
                "date": _fmt_time(st.st_mtime),
                "ext": p.suffix.lower().lstrip("."),
            }
            # 内容类（成长库那些）：附上标签 + 预览，做成像成长库一样能读、有标签
            if is_content and not is_dir and p.suffix.lower() == ".md":
                item["tags"] = _tags_of(p)
                item["preview"] = _preview_of(p)
            else:
                item["tags"] = []
                item["preview"] = ""
            items.append(item)
        except Exception:
            continue
    items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return items


def _safe_target(g, name):
    """解析 name 在该数据集目录下的真实路径，并确保没越权（防 ../ 逃逸）。"""
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    d = Path(g.get("dir"))
    target = (d / name).resolve()
    try:
        if not str(target).startswith(str(d.resolve())):
            return None
    except Exception:
        return None
    # 若该数据集有 files 白名单，name 必须在内
    if g.get("files") and name not in g["files"]:
        return None
    return target


# ════════════════════════════════════════════════════════════════════
#  对外 API
# ════════════════════════════════════════════════════════════════════

def overview():
    """各类别的概况：条目数 + 占用空间。给前端左侧类别列表。"""
    cats = []
    grand_n, grand_size = 0, 0
    for g in _groups():
        items = _list_items(g)
        size = sum(it["size"] for it in items)
        grand_n += len(items)
        grand_size += size
        cats.append({
            "key": g["key"], "label": g["label"], "icon": g["icon"],
            "safety": g["safety"], "count": len(items),
            "size": size, "size_h": _fmt_size(size),
        })
    return {
        "ok": True,
        "categories": cats,
        "total_count": grand_n,
        "total_size": grand_size,
        "total_size_h": _fmt_size(grand_size),
    }


def list_category(key):
    """某个类别下的全部条目（给右侧文件表格）。"""
    g = _group_by_key(key)
    if not g:
        return {"ok": False, "message": "未知类别"}
    items = _list_items(g)
    # 汇总该类别下所有用过的标签（按频次降序），给标签过滤条用
    counts = {}
    for it in items:
        for t in it.get("tags", []):
            counts[t] = counts.get(t, 0) + 1
    all_tags = [t for t, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    # 还没打标签的篇数（用于「AI 一键补标签」提示）
    untagged = sum(1 for it in items
                   if not it.get("is_dir") and it.get("ext") == "md" and not it.get("tags"))
    return {
        "ok": True, "key": key, "label": g["label"], "icon": g["icon"],
        "safety": g["safety"], "items": items, "count": len(items),
        "all_tags": all_tags, "untagged": untagged,
        "taggable": (g["safety"] == "content"),   # 内容类才支持标签
    }


def read_item(key, name):
    """读一个条目的正文（文本类才有内容；json 美化输出；目录返回提示）。"""
    g = _group_by_key(key)
    if not g:
        return {"ok": False, "message": "未知类别"}
    target = _safe_target(g, name)
    if not target or not target.exists():
        return {"ok": False, "message": "找不到该文件"}
    if target.is_dir():
        n = 0
        try:
            n = sum(1 for _ in target.rglob("*") if _.is_file())
        except Exception:
            pass
        return {"ok": True, "name": name, "is_dir": True,
                "content": "（这是一个文件夹，含 %d 个文件，可整体删除）" % n}
    try:
        txt = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "message": "读不出内容：%s" % e}
    if target.suffix.lower() == ".json":
        try:
            txt = json.dumps(json.loads(txt), ensure_ascii=False, indent=2)
        except Exception:
            pass
    return {"ok": True, "name": name, "is_dir": False,
            "ext": target.suffix.lower().lstrip("."), "content": txt[:200000]}


def export_item(key, name):
    """返回某条目的原始内容（给前端下载）。目录不支持，返回 None。"""
    g = _group_by_key(key)
    if not g:
        return None
    target = _safe_target(g, name)
    if not target or not target.exists() or target.is_dir():
        return None
    try:
        return target.read_bytes(), target.name
    except Exception:
        return None


def delete_item(key, name, force=False):
    """删除一个条目。config 类（运行配置）必须 force=True 才删，防误删搞坏软件。"""
    g = _group_by_key(key)
    if not g:
        return {"ok": False, "message": "未知类别"}
    if g["safety"] == "config" and not force:
        return {"ok": False, "locked": True,
                "message": "这是软件运行配置，删除可能影响小助。确认要删请解锁后再试。"}
    target = _safe_target(g, name)
    if not target or not target.exists():
        return {"ok": False, "message": "找不到该文件"}
    try:
        if target.is_dir():
            shutil.rmtree(str(target), ignore_errors=True)
        else:
            target.unlink()
        # 视频笔记：一并清掉它的截图子目录
        if key == "video" and name.endswith(".md"):
            stem = name[:-3]
            shots = MEM / "video_notes" / "shots" / stem
            if shots.exists():
                shutil.rmtree(str(shots), ignore_errors=True)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "message": "删除失败：%s" % e}


def set_tags(key, name, tags):
    """给某个内容类文件设置二级标签（写进文件里的「- 标签：」行）。
    与成长库共用同一份文件，所以两边标签实时一致。只允许 content 类、md 文件。"""
    g = _group_by_key(key)
    if not g:
        return {"ok": False, "message": "未知类别"}
    if g["safety"] != "content":
        return {"ok": False, "message": "这个类别不支持标签"}
    target = _safe_target(g, name)
    if not target or not target.exists() or target.suffix.lower() != ".md":
        return {"ok": False, "message": "找不到该文件或不是 md"}
    # 清洗标签：去重、去空、限长
    clean, seen = [], set()
    for t in (tags or []):
        t = str(t).strip()[:20]
        if t and t not in seen:
            seen.add(t)
            clean.append(t)
    clean = clean[:8]
    try:
        txt = target.read_text(encoding="utf-8", errors="replace")
        nl = "\r\n" if "\r\n" in txt else "\n"
        lines = txt.split(nl)
        tag_line = ("- 标签：" + "、".join(clean)) if clean else None
        idx = None
        for i, ln in enumerate(lines):
            s = ln.strip().lstrip("-").strip()
            if s.startswith("标签：") or s.startswith("标签:"):
                idx = i
                break
        if idx is not None:
            if tag_line:
                lines[idx] = tag_line
            else:
                lines.pop(idx)
        elif tag_line:
            # 插到元数据区（首个 ## 之前的最后一个「- 」行之后；否则插到标题后）
            insert_at = 1
            for i in range(1, len(lines)):
                if lines[i].strip().startswith("-"):
                    insert_at = i + 1
                elif lines[i].strip().startswith("##"):
                    break
            lines.insert(insert_at, tag_line)
        target.write_text(nl.join(lines), encoding="utf-8")
        return {"ok": True, "tags": clean}
    except Exception as e:
        return {"ok": False, "message": "写标签失败：%s" % e}
