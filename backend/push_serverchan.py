"""
push_serverchan.py — Server酱单向推送（超能小助 -> 你的微信）

最简单的一条路：不需要公网，超能小助主动往外发，你电脑能上网就行。
只能单向（超能小助通知你），你没法回。适合心跳干完活给你发个微信提醒。

准备（一次）：
1. 打开 https://sct.ftqq.com/ ，用微信扫码登录
2. 拿到一个 SendKey（形如 SCTxxxxxx）
3. 填进 memory/push.md 的 serverchan_key，或设环境变量 SERVERCHAN_KEY
"""

import os
import json
import urllib.parse
import urllib.request

from agent_core import read_memory_file


def _get_key():
    key = os.environ.get("SERVERCHAN_KEY", "")
    raw = read_memory_file("push.md")
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("serverchan_key:"):
            key = line.split(":", 1)[1].strip() or key
    return key.strip()


def push(title, content=""):
    """给微信推一条消息。返回 (成功?, 说明)。"""
    key = _get_key()
    if not key or "这里" in key or "填" in key:
        return False, "没配置 Server酱 key，请编辑 memory/push.md。"
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = urllib.parse.urlencode(
            {"title": title[:100], "desp": content}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        if r.get("code") == 0:
            return True, "已推送到微信。"
        return False, f"推送失败：{r.get('message', r)}"
    except Exception as e:
        return False, f"推送出错：{e}"


if __name__ == "__main__":
    ok, msg = push("超能小助测试", "这是一条来自超能小助的测试推送。")
    print(msg)
