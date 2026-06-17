"""
web_model_client.py — 把「伪模型」伪装成一个 OpenAI 兼容客户端。

目的：让 server / video_tools 里现成的
    client.chat.completions.create(model=..., messages=[...], tools=...)
这一行【完全不改】也能驱动网页 ChatGPT。

它做三件事：
  1. 忽略 tools（伪模型够不到本机工具，纯文本进出）。
  2. 把 messages 列表压成单段 prompt（system→【角色与要求】，user/assistant 依次拼，
     末尾补「请用中文按上面要求作答」）。
  3. 调 web_model.web_complete() 拿到回复，包装成 OpenAI 那样的返回对象：
       resp.choices[0].message.content  = 回复文本
       resp.choices[0].message.tool_calls = None   ← 关键：永远不返回工具调用
"""

import web_model

MAX_PROMPT_CHARS = 12000


def flatten_messages(messages):
    """messages -> 单段 prompt。长文截断留给上层分段（§7）。"""
    parts = []
    for m in messages or []:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):   # 兼容多模态结构，取其中文本块
            content = "".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text")
        content = (content or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append("【角色与要求】\n" + content)
        elif role == "assistant":
            parts.append("（你上一轮的回复）\n" + content)
        else:
            parts.append(content)
    prompt = "\n\n".join(parts)
    prompt += "\n\n请用中文按上面要求作答。"
    return prompt


# ── 仿 OpenAI 的返回对象（够用即可，只实现被读到的字段）──
class _Msg:
    def __init__(self, content):
        self.content = content
        self.role = "assistant"
        self.tool_calls = None      # ★ 永远 None：绝不让伪模型进工具循环

    def model_dump(self):
        return {"role": "assistant", "content": self.content, "tool_calls": None}


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)
        self.finish_reason = "stop"
        self.index = 0


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, on_progress=None):
        self._on_progress = on_progress

    def create(self, model=None, messages=None, tools=None,
               on_progress=None, **kwargs):
        prompt = flatten_messages(messages)
        cb = on_progress or self._on_progress
        # 把上层可能传入的答完判定提示（总结类）透传给 web_model
        wait_opts = {}
        for k in ("requiredMarkers", "minExpectedLength", "markersMinHits",
                  "acceptStableMarkers", "expectsJson", "timeout",
                  "disableCardSwitch", "shortReply"):
            if k in kwargs:
                wait_opts[k] = kwargs[k]
        text = web_model.web_complete(prompt, on_progress=cb, **wait_opts)
        return _Resp(text)


class _Chat:
    def __init__(self, on_progress=None):
        self.completions = _Completions(on_progress)


class WebModelClient:
    """与 OpenAI() 同形：client.chat.completions.create(...)。"""

    def __init__(self, on_progress=None):
        self.chat = _Chat(on_progress)
