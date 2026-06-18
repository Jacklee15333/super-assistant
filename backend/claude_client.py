"""
claude_client.py — 接入 Claude API（官方 + 第三方中转），支持多配置

设计目标：让超能小助能用 Claude 当成模型来用，
驱动和本地/网页模型完全一样的工具循环（含「电脑操作权限」那套工具）。

要点：
  · 支持多个配置（profiles）：每个配置有独立的 key、地址、模型名。
  · base_url 留空 → 走官方 api.anthropic.com，用原生 anthropic SDK。
  · base_url 填了第三方地址 → 自动切换为 OpenAI 兼容模式调用。
  · 对外伪装成 OpenAI 的 `client.chat.completions.create(...)` 形状。
  · 配置存在 backend/memory/claude_config.json。
  · 向后兼容旧的单配置格式（自动迁移）。

配置格式（新）：
  {"profiles": [
    {"name": "Claude Opus", "api_key": "sk-...", "base_url": "https://api.dakeai.cc", "model": "claude-opus-4-8", "max_tokens": 4096},
    {"name": "Claude Sonnet", "api_key": "sk-...", "base_url": "https://api.dakeai.cc", "model": "claude-sonnet-4-6", "max_tokens": 4096},
  ]}
"""

import json
from pathlib import Path

try:
    from agent_core import MEMORY_DIR
except Exception:
    MEMORY_DIR = Path(__file__).parent / "memory"
    MEMORY_DIR.mkdir(exist_ok=True)

CONFIG_PATH = MEMORY_DIR / "claude_config.json"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096


def _is_official(base_url):
    """判断是否走 Anthropic 官方端点。"""
    if not base_url or not base_url.strip():
        return True
    return "anthropic.com" in base_url.lower()


# ───────────────────────── 配置读写 ─────────────────────────

def _default_profile():
    return {"name": "", "api_key": "", "base_url": "", "model": DEFAULT_MODEL, "max_tokens": DEFAULT_MAX_TOKENS}


def _migrate_old_config(raw):
    """把旧的单配置格式迁移到新的 profiles 列表格式。"""
    if "profiles" in raw:
        return raw  # 已经是新格式
    # 旧格式：{api_key, base_url, model, max_tokens}
    p = _default_profile()
    p.update({k: v for k, v in raw.items() if k in ("api_key", "base_url", "model", "max_tokens") and v})
    if p.get("api_key"):
        p["name"] = p.get("model") or "Claude"
        return {"profiles": [p]}
    return {"profiles": []}


def load_config():
    """加载配置，返回 {"profiles": [...]}。"""
    try:
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            return _migrate_old_config(raw)
    except Exception:
        pass
    return {"profiles": []}


def save_config_raw(data):
    """直接写入整个配置。"""
    try:
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return data


def load_profiles():
    """返回配置列表。"""
    return load_config().get("profiles") or []


def save_profiles(profiles):
    """保存整个 profiles 列表。"""
    return save_config_raw({"profiles": profiles})


def get_profile(index):
    """按索引取一个配置。"""
    ps = load_profiles()
    if 0 <= index < len(ps):
        return ps[index]
    return None


def add_profile(profile):
    """添加一个配置，返回新索引。"""
    ps = load_profiles()
    p = _default_profile()
    p.update({k: v for k, v in (profile or {}).items() if v is not None})
    if not p.get("name"):
        p["name"] = p.get("model") or "Claude"
    ps.append(p)
    save_profiles(ps)
    return len(ps) - 1


def update_profile(index, incoming):
    """更新指定索引的配置。api_key 为空/占位符表示不修改。"""
    ps = load_profiles()
    if index < 0 or index >= len(ps):
        return None
    incoming = dict(incoming or {})
    if incoming.get("api_key") in (None, "", "***"):
        incoming.pop("api_key", None)
    ps[index].update({k: v for k, v in incoming.items() if v is not None})
    save_profiles(ps)
    return ps[index]


def delete_profile(index):
    """删除指定索引的配置。"""
    ps = load_profiles()
    if 0 <= index < len(ps):
        ps.pop(index)
        save_profiles(ps)
        return True
    return False


def is_configured():
    """至少有一个配好 key 的配置。"""
    return any(p.get("api_key") for p in load_profiles())


def sdk_available():
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def openai_sdk_available():
    try:
        from openai import OpenAI  # noqa: F401
        return True
    except Exception:
        return False


def status():
    """给前端看的状态（不回传明文 key）。"""
    profiles = load_profiles()
    items = []
    for i, p in enumerate(profiles):
        official = _is_official(p.get("base_url", ""))
        items.append({
            "index": i,
            "name": p.get("name") or p.get("model") or "Claude",
            "configured": bool(p.get("api_key")),
            "base_url": p.get("base_url", ""),
            "model": p.get("model", DEFAULT_MODEL),
            "max_tokens": p.get("max_tokens", DEFAULT_MAX_TOKENS),
            "sdk": sdk_available() if official else openai_sdk_available(),
            "mode": "official" if official else "relay",
        })
    return {
        "configured": any(it["configured"] for it in items),
        "profiles": items,
        # 向后兼容：保留旧字段（取第一个配置）
        "base_url": items[0]["base_url"] if items else "",
        "model": items[0]["model"] if items else DEFAULT_MODEL,
        "sdk": items[0]["sdk"] if items else sdk_available(),
    }


# ─── 旧接口兼容：save_config（前端旧的保存逻辑可能还会调） ───
def save_config(incoming):
    """兼容旧的单配置保存。如果已有 profiles 就更新第一个，没有就新建。"""
    ps = load_profiles()
    incoming = dict(incoming or {})
    if incoming.get("api_key") in (None, "", "***"):
        incoming.pop("api_key", None)
    if ps:
        ps[0].update({k: v for k, v in incoming.items() if v is not None})
    else:
        p = _default_profile()
        p.update({k: v for k, v in incoming.items() if v is not None})
        if not p.get("name"):
            p["name"] = p.get("model") or "Claude"
        ps.append(p)
    save_profiles(ps)
    return ps[0]


# ───────────────── OpenAI ↔ Anthropic 形状转换 ─────────────────
def _to_anthropic_messages(messages):
    system_parts, out = [], []
    i, n = 0, len(messages or [])
    while i < n:
        m = messages[i] or {}
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                system_parts.append(str(m.get("content")))
            i += 1
            continue
        if role == "tool":
            blocks = []
            while i < n and (messages[i] or {}).get("role") == "tool":
                tm = messages[i]
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tm.get("tool_call_id"),
                    "content": str(tm.get("content", "")),
                })
                i += 1
            out.append({"role": "user", "content": blocks})
            continue
        if role == "assistant":
            content = m.get("content") or ""
            tcs = m.get("tool_calls")
            if tcs:
                blocks = []
                if str(content).strip():
                    blocks.append({"type": "text", "text": content})
                for tc in tcs:
                    fn = (tc or {}).get("function", {}) or {}
                    try:
                        inp = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        inp = {}
                    blocks.append({"type": "tool_use", "id": tc.get("id"),
                                   "name": fn.get("name"), "input": inp})
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": "assistant", "content": str(content) or "（空）"})
            i += 1
            continue
        out.append({"role": "user", "content": str(m.get("content") or "")})
        i += 1
    return ("\n\n".join(p for p in system_parts if p), out)


def _to_anthropic_tools(tools):
    out = []
    for t in (tools or []):
        f = (t or {}).get("function", {}) or {}
        out.append({
            "name": f.get("name"),
            "description": f.get("description", "") or "",
            "input_schema": f.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


# ─────────── 伪装成 OpenAI 响应的小对象 ───────────
class _Func:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.type = "function"
        self.function = _Func(name, arguments)

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name,
                             "arguments": self.function.arguments}}


class _Msg:
    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls or None


class _Choice:
    def __init__(self, msg):
        self.message = msg


class _Resp:
    def __init__(self, msg):
        self.choices = [_Choice(msg)]


class _Completions:
    def __init__(self, outer):
        self._o = outer

    def create(self, **kw):
        return self._o._create(**kw)


class _Chat:
    def __init__(self, outer):
        self.completions = _Completions(outer)


def _friendly_error(e, base_url, model):
    msg = str(e)
    low = msg.lower()
    if "401" in msg or "invalid_api_key" in low or "invalid api key" in low or "unauthorized" in low:
        hints = []
        hints.append("API Key 认证失败，可能的原因：")
        hints.append("1. Key 不正确或已过期 → 去中转站后台重新复制 key")
        hints.append("2. Key 的「分组」不支持当前模型「%s」" % model)
        hints.append("   → 去中转站创建「默认分组」或与模型匹配的分组的 key")
        hints.append("3. 地址填错了 → 当前地址：%s" % (base_url or "（官方 api.anthropic.com）"))
        return "\n".join(hints)
    if "404" in msg or "not found" in low:
        return "模型「%s」不存在或当前分组不支持。请确认模型名称。\n当前地址：%s" % (model, base_url or "官方")
    if "429" in msg or "rate_limit" in low or "quota" in low:
        return "请求太频繁或余额不足，请稍后再试或到中转站充值。"
    if "connection" in low or "timeout" in low or "refused" in low:
        return "无法连接到 API 服务器：%s\n请检查网络或地址是否正确。" % (base_url or "api.anthropic.com")
    return msg


class ClaudeClient:
    """对外形状 == OpenAI client：client.chat.completions.create(...)。"""

    def __init__(self, api_key, model, max_tokens=DEFAULT_MAX_TOKENS, base_url=""):
        self._model = model or DEFAULT_MODEL
        self._max_tokens = int(max_tokens or DEFAULT_MAX_TOKENS)
        self._official = _is_official(base_url)
        self._base_url = base_url or ""

        if self._official:
            import anthropic
            kwargs = {"api_key": api_key}
            if base_url and base_url.strip():
                kwargs["base_url"] = base_url
            self._client = anthropic.Anthropic(**kwargs)
            self._mode = "anthropic"
        else:
            from openai import OpenAI
            url = base_url.rstrip("/")
            if not url.endswith("/v1"):
                url = url + "/v1"
            self._client = OpenAI(api_key=api_key, base_url=url)
            self._mode = "openai"

        self.chat = _Chat(self)

    def _create(self, model=None, messages=None, tools=None, **kw):
        try:
            if self._mode == "anthropic":
                return self._create_anthropic(messages, tools)
            else:
                return self._create_openai(messages, tools)
        except Exception as e:
            friendly = _friendly_error(e, self._base_url, self._model)
            raise RuntimeError(friendly) from e

    def _create_anthropic(self, messages, tools):
        system, conv = _to_anthropic_messages(messages or [])
        atools = _to_anthropic_tools(tools or [])
        kwargs = {"model": self._model, "messages": conv, "max_tokens": self._max_tokens}
        if system:
            kwargs["system"] = system
        if atools:
            kwargs["tools"] = atools
        resp = self._client.messages.create(**kwargs)
        text_parts, tcs = [], []
        for blk in (resp.content or []):
            btype = getattr(blk, "type", None)
            if btype == "text":
                text_parts.append(getattr(blk, "text", "") or "")
            elif btype == "tool_use":
                tcs.append(_ToolCall(
                    getattr(blk, "id", None), getattr(blk, "name", None),
                    json.dumps(getattr(blk, "input", {}) or {}, ensure_ascii=False)))
        return _Resp(_Msg("".join(text_parts), tcs))

    def _create_openai(self, messages, tools):
        kwargs = {"model": self._model, "messages": messages or [], "max_tokens": self._max_tokens}
        if tools:
            kwargs["tools"] = tools
            # 显式声明 auto：部分中转站不带这个参数时不会触发函数调用，
            # 只回一句「我去看一下…」的纯文本。带上能让它正常调用工具。
            kwargs["tool_choice"] = "auto"
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        content = msg.content or ""
        tcs = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                tcs.append(_ToolCall(tc.id, fn.name, fn.arguments))
        return _Resp(_Msg(content, tcs))


def make(profile_index=None):
    """按配置造客户端。可指定 profile_index，不指定则用第一个。"""
    profiles = load_profiles()
    if not profiles:
        raise RuntimeError("还没配置 Claude API Key。请到「设置 → Claude 模型管理」添加。")
    if profile_index is not None:
        if profile_index < 0 or profile_index >= len(profiles):
            raise RuntimeError("Claude 配置 #%d 不存在。" % profile_index)
        p = profiles[profile_index]
    else:
        p = profiles[0]
    if not p.get("api_key"):
        raise RuntimeError("Claude 配置「%s」还没填 API Key。" % (p.get("name") or "未命名"))
    base_url = p.get("base_url", "")
    official = _is_official(base_url)
    if official and not sdk_available():
        raise RuntimeError("缺少 anthropic 库。重跑一次启动脚本会自动安装，"
                           "或在 backend 目录执行：pip install anthropic")
    if not official and not openai_sdk_available():
        raise RuntimeError("缺少 openai 库。在 backend 目录执行：pip install openai")
    return ClaudeClient(p["api_key"], p.get("model", DEFAULT_MODEL),
                        p.get("max_tokens", DEFAULT_MAX_TOKENS), base_url=base_url)
