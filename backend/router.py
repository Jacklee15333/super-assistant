"""
router.py — 智能模型路由：判任务类型（§3 R-A）+ 按任务取模型（§2 resolve_model）。

每条请求进来做两件事：
  1. classify(text)         -> "local_action" | "video" | "chat" | "quick_chat"
  2. resolve_model(task, …) -> (use_local, model)   # 该任务配了用配的，否则用兜底

先做 R-A 确定性触发（快、可控、覆盖 95%）：
  · T2 视频：正则匹配视频/音频链接
  · T1 本机动作：关键词命中，或显式前缀 /记住 /提醒 /笔记
  · T4 快速闲聊（可选）：很短、无链接无动作词
  · 其余 → T3（伪模型）

WEB_MODEL_ID = "web" 是伪模型在 /models 里的标识。
"""

import re

WEB_MODEL_ID = "web"

# 任务名（也是 task_models.json 里的 key）
T_LOCAL = "local_action"
T_VIDEO = "video"
T_CHAT = "chat"            # T3 高级分析/搜索/写作/总结
T_QUICK = "quick_chat"

# 视频/音频链接（T2）
_VIDEO_RE = re.compile(
    r"(douyin\.com|iesdouyin|kuaishou|bilibili\.com|b23\.tv|youtube\.com|youtu\.be|"
    r"xiaohongshu|xhslink|\.mp4\b|\.mp3\b|\.m4a\b|\.wav\b)",
    re.IGNORECASE)

# 本机动作关键词（T1）
_LOCAL_KW = [
    "记住", "记一下", "记下", "提醒我", "设个提醒", "设置提醒",
    "存到笔记", "记笔记", "存起来", "我的记忆", "更新记忆", "管理记忆",
    "读本地", "打开文件", "读取文件", "写入文件", "本地文件",
]
# 显式前缀兜底
_LOCAL_PREFIX = ("/记住", "/提醒", "/笔记", "/记忆")

# 快速闲聊判定上限（字符）
_QUICK_MAXLEN = 12
_QUICK_WORDS = ("你好", "在吗", "在不在", "hi", "hello", "嗨", "早", "晚安", "谢谢", "好的", "嗯")


def _last_user_text(messages):
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                c = "".join(b.get("text", "") for b in c
                            if isinstance(b, dict) and b.get("type") == "text")
            return (c or "").strip()
    return ""


def classify(text, enable_quick_chat=False):
    """返回任务类型。text 为最后一条用户消息。"""
    t = (text or "").strip()
    low = t.lower()

    # T1 显式前缀最优先（最可靠的兜底）
    if any(t.startswith(p) for p in _LOCAL_PREFIX):
        return T_LOCAL

    # T2 视频/音频链接
    if _VIDEO_RE.search(t):
        return T_VIDEO

    # T1 本机动作关键词
    if any(kw in t for kw in _LOCAL_KW):
        return T_LOCAL

    # T4 快速闲聊（可选）：很短 + 无链接 + 命中招呼词
    if enable_quick_chat and len(t) <= _QUICK_MAXLEN and "http" not in low:
        if any(w in low for w in _QUICK_WORDS):
            return T_QUICK

    # 其余 → T3
    return T_CHAT


def classify_messages(messages, enable_quick_chat=False):
    return classify(_last_user_text(messages), enable_quick_chat)


# ─────────────── task_models.json：各任务用哪个模型 ───────────────
# 形如：
# {
#   "default": {"use_local": false, "model": "web"},
#   "chat":          {"follow_default": true},
#   "video_summary": {"use_local": false, "model": "web"},
#   "local_action":  {"use_local": true,  "model": "qwen2.5"},
#   "quick_chat":    {"use_local": true,  "model": "qwen2.5"}
# }
# 「跟随默认」用 {"follow_default": true} 表示。

def resolve_model(task, task_models, fallback_use_local=True,
                  fallback_model="qwen2.5"):
    """
    返回 (use_local, model)。
    优先级：该任务的显式配置 > default 配置 > 调用方兜底。
    """
    tm = task_models or {}
    default = tm.get("default") or {}
    cfg = tm.get(task)

    def pick(entry):
        if not entry or entry.get("follow_default"):
            return None
        return (bool(entry.get("use_local", False)), entry.get("model") or fallback_model)

    chosen = pick(cfg)
    if chosen is None:
        chosen = pick(default)
    if chosen is None:
        chosen = (fallback_use_local, fallback_model)

    # 伪模型一律视为「非本地」
    use_local, model = chosen
    if model == WEB_MODEL_ID:
        use_local = False
    return use_local, model


def is_web_model(model):
    return model == WEB_MODEL_ID
