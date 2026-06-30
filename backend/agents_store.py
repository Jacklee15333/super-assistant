"""
agents_store.py — 「分身」(Agents) 存取与管理

一个「分身」= 一份记住了用户判断标准、按用户方式做事的本地档案。
它对应文章里最值钱的机制：把隐性判断 → 显性化 → 固化成可复用模块 → 让 AI 承接放大。

跟「技能(skills)」的关系：
  - 技能 = 一套"遇到某类任务该怎么做"的通用方法论（谁用都一样）。
  - 分身 = 一个"记住了【我】会怎么做这件事"的固定专员（带着我的语气、底线、偏好）。
  两者存储模式一致（每项一个文件夹 + 一个 json/md），本模块照抄 skills_store.py 的结构。

目录结构（每个分身一个文件夹）：
    backend/memory/agents/<slug>/agent.json

本模块不依赖任何第三方库，保持依赖最小。被 server.py 的 /agents/* 接口与 _handle_chat 调用。
"""

import json
import re
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = BASE_DIR / "memory" / "agents"

# slug 只允许小写字母数字和连字符，杜绝 ../ 之类的路径穿越（与 skills_store 一致）
_SLUG_RE = re.compile(r"[^a-z0-9\-]+")

# 访谈式创建分身时用的特殊 slug：带上它走 /chat，后端注入"访谈引导"提示，
# 让模型来采访用户、最后吐出一份分身草稿（而不是把"写提示词"丢给用户）。
INTERVIEW_SLUG = "__interview__"


def _now_iso() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _slugify(name: str) -> str:
    """把分身名转成安全的文件夹名。中文等非 ascii 会被去掉，所以中文名通常落到 'agent'，
    再由 save_agent 兜底加时间戳保证唯一。"""
    s = (name or "").strip().lower().replace(" ", "-")
    s = _SLUG_RE.sub("", s)
    s = s.strip("-")
    return s or "agent"


def _safe_slug(slug: str) -> str:
    """对外部传入的 slug 做一次清洗。"""
    s = (slug or "").strip().lower()
    s = _SLUG_RE.sub("", s.replace(" ", "-"))
    return s.strip("-")


def _agent_json_path(slug: str) -> Path:
    return AGENTS_DIR / slug / "agent.json"


def _read_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    return None


def _unique_slug(base: str) -> str:
    """若 base 文件夹已存在，则 base-2 / base-3 … 直到不冲突。"""
    base = base or "agent"
    slug = base
    i = 2
    while (AGENTS_DIR / slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


# ---------- 对外 API ----------

def list_agents() -> list:
    """列出所有分身（读各 agent.json）。返回 list[dict]，按创建时间升序。
    每项含：slug/name/emoji/role/standard/enabled/stats/created_at/updated_at。"""
    out = []
    if not AGENTS_DIR.exists():
        return out
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        data = _read_json(d / "agent.json")
        if not isinstance(data, dict):
            continue
        data.setdefault("slug", d.name)
        data.setdefault("name", d.name)
        data.setdefault("emoji", "🎭")
        data.setdefault("role", "")
        data.setdefault("standard", "")
        data.setdefault("samples", [])
        data.setdefault("enabled", True)
        data.setdefault("stats", {"runs": 0, "last_used": ""})
        out.append(data)
    out.sort(key=lambda a: a.get("created_at", ""))
    return out


def get_agent(slug: str):
    """读一个分身的完整档案。返回 dict 或 None。"""
    slug = _safe_slug(slug)
    if not slug:
        return None
    data = _read_json(_agent_json_path(slug))
    if not isinstance(data, dict):
        return None
    data.setdefault("slug", slug)
    data.setdefault("emoji", "🎭")
    data.setdefault("samples", [])
    data.setdefault("tools", [])
    data.setdefault("enabled", True)
    data.setdefault("stats", {"runs": 0, "last_used": ""})
    # 每个分身独立的「模型/模式」偏好（互不影响、也不动主软件）
    data.setdefault("use_local", True)
    data.setdefault("model", "")          # 空＝沿用主软件当前选择；非空＝这个分身固定用它
    data.setdefault("smart_routing", True)
    data["automation"] = _normalize_automation(data.get("automation"), data)
    return data


def save_agent(data: dict) -> dict:
    """新建或覆盖一个分身。
    - 传了 slug 且已存在 → 视为编辑，覆盖（保留 created_at / stats）。
    - 没传 slug → 用 name 生成；中文名落到 'agent' 时加时间戳并保证唯一。
    返回保存后的完整档案（含 slug）。"""
    data = dict(data or {})
    provided = _safe_slug(data.get("slug") or "")

    if provided:
        slug = provided
        existing = get_agent(slug)
    else:
        base = _slugify(data.get("name") or "")
        if base == "agent":
            base = "agent-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = _unique_slug(base)
        existing = None

    now = _now_iso()
    record = {
        "slug": slug,
        "name": (data.get("name") or slug).strip(),
        "emoji": (data.get("emoji") or "🎭").strip() or "🎭",
        "role": (data.get("role") or "").strip(),
        "standard": (data.get("standard") or "").strip(),
        "samples": data.get("samples") if isinstance(data.get("samples"), list) else [],
        "tools": data.get("tools") if isinstance(data.get("tools"), list) else [],
        "enabled": bool(data.get("enabled", True)),
        # 每个分身独立的模型/模式偏好 + 自动化任务：编辑分身时若没传就沿用已有，别覆盖丢失
        "use_local": bool(data.get("use_local", (existing or {}).get("use_local", True))),
        "model": (data.get("model") if data.get("model") is not None else (existing or {}).get("model", "")) or "",
        "smart_routing": bool(data.get("smart_routing", (existing or {}).get("smart_routing", True))),
        "automation": data.get("automation") if isinstance(data.get("automation"), dict)
                      else ((existing or {}).get("automation") or _default_automation()),
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
        "stats": (existing or {}).get("stats") or {"runs": 0, "last_used": ""},
    }

    p = _agent_json_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def delete_agent(slug: str) -> bool:
    """删除一个分身（连同它的文件夹）。返回是否成功。"""
    slug = _safe_slug(slug)
    d = AGENTS_DIR / slug
    if not slug or not d.exists() or not d.is_dir():
        return False
    try:
        for f in sorted(d.rglob("*"), reverse=True):
            try:
                f.unlink()
            except Exception:
                try:
                    f.rmdir()
                except Exception:
                    pass
        d.rmdir()
        return True
    except Exception:
        return False


def update_standard(slug: str, feedback: str) -> dict:
    """把一条用户反馈并进分身的判断标准（第一版：结构化追加，确定性、不依赖模型）。
    返回 {ok, standard}。反馈会作为新的一条"补充规则"加到标准末尾，越用越懂就靠它累积。"""
    slug = _safe_slug(slug)
    a = get_agent(slug)
    if not a:
        return {"ok": False, "message": "分身不存在", "standard": ""}
    fb = (feedback or "").strip()
    if not fb:
        return {"ok": False, "message": "反馈为空", "standard": a.get("standard", "")}

    std = (a.get("standard") or "").strip()
    # 第一次追加时，给补充内容起个小标题，之后的反馈续在同一段下面。
    marker = "补充规则（你后来教我的）："
    if marker in std:
        std = std.rstrip() + "\n- " + fb
    else:
        if std:
            std = std.rstrip() + "\n\n" + marker + "\n- " + fb
        else:
            std = marker + "\n- " + fb

    a["standard"] = std
    save_agent(a)
    return {"ok": True, "standard": std}


def bump_usage(slug: str):
    """派活时计一次数（runs +1，更新 last_used）。失败静默，绝不影响对话主流程。"""
    try:
        slug = _safe_slug(slug)
        a = get_agent(slug)
        if not a:
            return
        stats = a.get("stats") or {"runs": 0, "last_used": ""}
        stats["runs"] = int(stats.get("runs", 0)) + 1
        stats["last_used"] = _now_iso()
        a["stats"] = stats
        p = _agent_json_path(slug)
        if p.exists():
            p.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _patch_agent(slug: str, patch: dict):
    """读-改-写：只更新 agent.json 里指定的字段，其余保持不变。"""
    slug = _safe_slug(slug)
    a = get_agent(slug)
    if not a:
        return None
    a.update(patch or {})
    a["updated_at"] = _now_iso()
    p = _agent_json_path(slug)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return None
    return a


def set_agent_model(slug: str, use_local, model, smart_routing) -> dict:
    """保存某分身【自己的】模型/模式偏好（与主软件、其它分身互不影响）。"""
    a = _patch_agent(slug, {
        "use_local": bool(use_local),
        "model": (model or "").strip(),
        "smart_routing": bool(smart_routing),
    })
    if not a:
        return {"ok": False, "message": "分身不存在"}
    return {"ok": True, "use_local": a["use_local"], "model": a["model"],
            "smart_routing": a["smart_routing"]}


# ====================================================================
# 分身自动化（SOP / 定时任务）——让分身不只是聊天框，而能「按你的方式」定时自己干活。
# 每个分身把任务存在自己的 agent.json 里（互相独立）；后端有个调度线程到点就跑，
# 跑完把结果存成这个分身的一段「🤖 自动」历史对话。
# ====================================================================

_TIME_RE = re.compile(r"^\s*(\d{1,2})\s*:\s*(\d{1,2})\s*$")


def _write_json(path: Path, obj) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _gen_task_id() -> str:
    import random
    return "t-" + datetime.datetime.now().strftime("%H%M%S") + "-" + ("%04x" % random.randint(0, 0xffff))


def _default_automation() -> dict:
    # 新结构：多任务。每个任务有自己的时间和模型。
    return {"tasks": []}


def _safe_time(s: str) -> str:
    m = _TIME_RE.match(s or "")
    if m:
        h, mm = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mm <= 59:
            return "%02d:%02d" % (h, mm)
    return "09:00"


def _normalize_task(t: dict, agent: dict) -> dict:
    agent = agent or {}
    return {
        "id": t.get("id") or _gen_task_id(),
        "name": (t.get("name") or "").strip(),
        "enabled": bool(t.get("enabled", False)),
        "prompt": (t.get("prompt") or "").strip(),
        "time": _safe_time(t.get("time")),
        # 每个任务自己的模型；为空则运行时回退到分身自己的模型
        "use_local": bool(t.get("use_local", agent.get("use_local", True))),
        "model": (t.get("model") or "").strip(),
        "last_run_date": t.get("last_run_date", ""),
        "last_result_id": t.get("last_result_id", ""),
    }


def _normalize_automation(auto, agent) -> dict:
    """统一成新结构 {tasks:[...]}；兼容旧的单任务结构（自动迁移）。"""
    agent = agent or {}
    if not isinstance(auto, dict):
        return {"tasks": []}
    if isinstance(auto.get("tasks"), list):
        return {"tasks": [_normalize_task(t, agent) for t in auto["tasks"] if isinstance(t, dict)]}
    # 旧的单任务结构 -> 包成一个任务
    if (auto.get("prompt") or "").strip() or auto.get("enabled"):
        return {"tasks": [_normalize_task({
            "id": auto.get("id") or _gen_task_id(),
            "enabled": auto.get("enabled", False),
            "prompt": auto.get("prompt", ""),
            "time": auto.get("time", "09:00"),
            "use_local": agent.get("use_local", True),
            "model": agent.get("model", ""),
            "last_run_date": auto.get("last_run_date", ""),
            "last_result_id": auto.get("last_result_id", ""),
        }, agent)]}
    return {"tasks": []}


def get_automation(slug: str) -> dict:
    a = get_agent(slug)
    if not a:
        return {"tasks": []}
    return _normalize_automation(a.get("automation"), a)


def get_automation_task(slug: str, task_id: str):
    for t in get_automation(slug).get("tasks", []):
        if t.get("id") == task_id:
            return t
    return None


def set_automation(slug: str, cfg: dict) -> dict:
    """保存某分身的多任务设置。按任务 id 保留各自的 last_run_date/last_result_id（运行历史不丢）。"""
    cfg = cfg or {}
    a = get_agent(slug)
    if not a:
        return {"ok": False, "message": "分身不存在"}
    incoming = cfg.get("tasks") if isinstance(cfg.get("tasks"), list) else []
    cur_by_id = {t.get("id"): t for t in _normalize_automation(a.get("automation"), a)["tasks"]}
    tasks = []
    for t in incoming:
        if not isinstance(t, dict):
            continue
        nt = _normalize_task(t, a)
        prev = cur_by_id.get(nt["id"], {})
        nt["last_run_date"] = prev.get("last_run_date", "")
        nt["last_result_id"] = prev.get("last_result_id", "")
        tasks.append(nt)
    out = {"tasks": tasks}
    if not _patch_agent(slug, {"automation": out}):
        return {"ok": False, "message": "保存失败"}
    return {"ok": True, "automation": out}


def mark_automation_ran(slug: str, task_id: str, date_str: str, result_id: str):
    """记某个任务跑过一次（一天只跑一次靠它）。"""
    a = get_agent(slug)
    if not a:
        return
    auto = _normalize_automation(a.get("automation"), a)
    for t in auto["tasks"]:
        if t.get("id") == task_id:
            t["last_run_date"] = date_str or ""
            t["last_result_id"] = result_id or ""
            break
    _patch_agent(slug, {"automation": auto})


def due_automations(now_dt) -> list:
    """返回此刻应当运行的 (slug, task_id) 列表：任务已启用、有内容、今天还没跑过、且已过设定时刻。
    （若到点时软件没开，当天再打开、时刻已过且今天没跑过时会补跑一次。）"""
    out = []
    today = now_dt.strftime("%Y-%m-%d")
    cur_hm = now_dt.strftime("%H:%M")
    for a in list_agents():
        for t in _normalize_automation(a.get("automation"), a)["tasks"]:
            if not t.get("enabled"):
                continue
            if not (t.get("prompt") or "").strip():
                continue
            if t.get("last_run_date") == today:
                continue
            if cur_hm >= _safe_time(t.get("time")):
                out.append((a.get("slug"), t.get("id")))
    return out


# ============================ 自动化结果通知 ============================
# 后台任务跑完后写一条通知；前端定时来取，弹窗给用户看（哪个分身、什么报告）。

def _notif_path() -> Path:
    # 放在 agents 根目录下的一个文件（list_agents 只遍历子目录，不会当成分身）
    return AGENTS_DIR / "_notifications.json"


def add_notification(slug, agent_name, agent_emoji, task_id, conversation_id, title, task_name=""):
    try:
        data = _read_json(_notif_path()) or {}
        items = data.get("items") if isinstance(data.get("items"), list) else []
        items.append({
            "id": "n-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "slug": slug, "agent_name": agent_name or "", "agent_emoji": agent_emoji or "🎭",
            "task_id": task_id or "", "conversation_id": conversation_id or "",
            "task_name": task_name or "",
            "title": title or "", "created_at": _now_iso(), "seen": False,
        })
        _write_json(_notif_path(), {"items": items[-100:]})
    except Exception:
        pass


def list_notifications(unseen_only: bool = True) -> list:
    data = _read_json(_notif_path()) or {}
    items = data.get("items") if isinstance(data.get("items"), list) else []
    if unseen_only:
        items = [i for i in items if not i.get("seen")]
    return items


def mark_notifications_seen(ids):
    try:
        data = _read_json(_notif_path()) or {}
        items = data.get("items") if isinstance(data.get("items"), list) else []
        idset = set(ids or [])
        for i in items:
            if i.get("id") in idset:
                i["seen"] = True
        _write_json(_notif_path(), {"items": items})
    except Exception:
        pass


# ====================================================================
# 每个分身自己的「会话历史」——像给每个分身开了一个独立的工作区/用户。
# 存在 backend/memory/agents/<slug>/conversations/<cid>.json，与主对话、知识云图互不干扰。
# 用 JSON 存完整 messages（无损，能原样接着聊）；保存时剥掉 system（它每轮由后端按 slug 重建）。
# ====================================================================

_CID_RE = re.compile(r"[^a-z0-9_\-]+")


def _convos_dir(slug: str) -> Path:
    return AGENTS_DIR / _safe_slug(slug) / "conversations"


def _safe_cid(cid: str) -> str:
    return _CID_RE.sub("", (cid or "").lower()).strip("-") or ""


def list_agent_convos(slug: str) -> list:
    """列出某分身的所有会话（按最近使用倒序），不含正文。每项：id/title/created_at/updated_at/turns。"""
    d = _convos_dir(slug)
    out = []
    if not d.exists():
        return out
    # 按文件修改时间排序（亚秒级，比字符串时间戳更可靠，避免同一秒内多次保存排序错乱）
    try:
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        files = list(d.glob("*.json"))
    for p in files:
        data = _read_json(p)
        if not isinstance(data, dict):
            continue
        msgs = data.get("messages") or []
        turns = sum(1 for m in msgs if isinstance(m, dict) and m.get("role") == "user")
        out.append({
            "id": data.get("id") or p.stem,
            "title": data.get("title") or "新对话",
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "turns": turns,
        })
    return out


def get_agent_convo(slug: str, cid: str):
    """读某分身的一段会话完整内容（含 messages）。返回 dict 或 None。"""
    cid = _safe_cid(cid)
    if not cid:
        return None
    data = _read_json(_convos_dir(slug) / (cid + ".json"))
    return data if isinstance(data, dict) else None


def save_agent_convo(slug: str, cid: str, title: str, messages: list) -> dict:
    """保存/更新某分身的一段会话。用 cid 当稳定文件名，反复保存只更新同一个文件。
    会剥掉 system 消息（后端每轮按 slug 重建，存它没意义还占地方）。标题没给就取首条用户消息。
    返回 {ok, id, title, updated_at}。"""
    slug = _safe_slug(slug)
    if not slug or not get_agent(slug):
        return {"ok": False, "message": "分身不存在"}
    cid = _safe_cid(cid) or ("c-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    msgs = []
    for m in (messages or []):
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "system":
            continue   # 不存 system（每轮后端重建）
        if role in ("user", "assistant", "tool"):
            msgs.append(m)
    if not any(isinstance(m, dict) and m.get("role") == "user" for m in msgs):
        return {"ok": False, "message": "空对话，不保存"}

    ttl = (title or "").strip()
    if not ttl:
        for m in msgs:
            if m.get("role") == "user" and (m.get("content") or "").strip():
                ttl = (m.get("content") or "").strip()[:24]
                break
    ttl = ttl or "新对话"

    now = _now_iso()
    existing = get_agent_convo(slug, cid) or {}
    rec = {
        "id": cid,
        "title": ttl,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "messages": msgs,
    }
    d = _convos_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    try:
        (d / (cid + ".json")).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "id": cid, "title": ttl, "updated_at": now}


def delete_agent_convo(slug: str, cid: str) -> dict:
    """删除某分身的一段会话。"""
    cid = _safe_cid(cid)
    if not cid:
        return {"ok": False}
    p = _convos_dir(_safe_slug(slug)) / (cid + ".json")
    try:
        if p.exists():
            p.unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def build_agent_system_prompt(slug: str) -> str:
    """生成"分身人设" system 片段，供 /chat 注入（拼在 core.build_system_prompt() 之后）。

    两种用途：
      1) slug == INTERVIEW_SLUG → 返回"访谈引导"提示：让模型采访用户、最后吐出分身草稿 JSON。
      2) 普通 slug → 返回该分身的判断标准 + 风格样本，让它带着用户的判断做事。
    找不到分身返回空串（注入端会跳过，相当于普通对话）。"""
    if (slug or "").strip() == INTERVIEW_SLUG:
        return _INTERVIEW_PROMPT

    a = get_agent(slug)
    if not a:
        return ""

    name = a.get("name") or "分身"
    emoji = a.get("emoji") or ""
    role = (a.get("role") or "").strip()
    standard = (a.get("standard") or "").strip()
    samples = a.get("samples") or []

    lines = [f"=== 你现在的身份：用户的专属分身「{name}」{emoji} ==="]
    if role:
        lines.append(f"你的职责：{role}。")
    if standard:
        lines.append(
            "你必须严格遵循下面这份用户亲自沉淀的【判断标准】——这是用户教你的做事方式，"
            "优先级高于任何通用习惯。拿不准时按它判断，必要时反问用户：")
        lines.append(standard)
    if samples:
        lines.append("以下是用户满意的风格样本，模仿其语气、分寸与详略（不要照抄内容，学的是味儿）：")
        for s in samples[:5]:
            if not isinstance(s, dict):
                continue
            t = (s.get("title") or "样本").strip()
            c = (s.get("content") or "").strip()
            if c:
                lines.append(f"【{t}】\n{c}")
    lines.append(
        "按用户的方式做事，直接给可用的结果，不要产出平均、安全、套话式的内容。"
        "这是用户的专属分身对话，做完一件事可以顺手问一句要不要调整。")
    return "\n".join(lines)


# ====================================================================
# 访谈引导提示：创建分身时注入。核心理念——别让用户写提示词，让软件反过来采访用户，
# 把他对某件事的"判断标准"（隐性知识）一点点套出来，最后整理成一份可编辑的草稿。
# 模型最终必须用 ```json``` 代码块吐出草稿，前端正则抠出来再 JSON.parse（解析失败有兜底）。
# ====================================================================

_INTERVIEW_PROMPT = """=== 现在的任务：访谈用户，帮他创建一个 AI 分身 ===
用户想要一个能替他做某件事的「分身」。你的目标是：通过自然的提问，把用户对这件事的【判断标准】套出来——也就是"用户会怎么做这件事"，而不只是"这件事一般怎么做"。

规则：
1. 一次只问 1~2 个**具体、好回答**的问题，别问空泛的。
   - 不好：「你有什么要求？」
   - 好：「你回邮件一般用什么语气，简洁干脆还是客气周到？」
   问完就**停下，等用户回答**，再问下一个。不要一次抛一长串。
2. 围绕这几样去套（够用即可，3~5 个问题）：
   - 用户的身份/处境（他是以什么角色做这件事）；
   - 语气或风格偏好；
   - 哪些情况要特别处理、哪些是绝对底线/绝对不能做；
   - 有没有满意的例子可以发你参考（让他贴一两个）。
3. 当你收集得差不多了（能写出一份**具体到能照着执行**的标准），就停止提问，输出一段总结。
   总结必须、且只能用下面这个 JSON 代码块包裹，**JSON 之外不要再写任何话**：

```json
{
  "name": "给这个分身起的中文名，如 邮件管家",
  "emoji": "一个贴切的 emoji，如 📧",
  "slug": "一个英文短横线小写 slug，如 email-keeper",
  "role": "一句话职责，如 帮我起草和回复邮件",
  "standard": "把用户的判断标准写成第二人称、可执行的规则，分条用换行列清楚。这是最关键的部分，越具体越好。",
  "samples": [{"title": "样本简述", "content": "用户给的满意例子原文"}]
}
```

4. standard 要把用户提到的语气、底线、各种情况怎么处理都写进去；用户没给例子时 samples 就给空数组 []。
5. 全程用中文，语气像在**认真采访**用户，而不是在让他填表。第一句先简短回应你要当他的什么分身，然后开始问第一个问题。
"""
