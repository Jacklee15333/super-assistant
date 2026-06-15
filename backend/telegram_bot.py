"""
telegram_bot.py — 让你在手机 Telegram 上指挥超能小助

用 Telegram 官方 HTTP API，标准库即可，不引入第三方库。

准备工作（一次）：
1. 在 Telegram 里找 @BotFather，发 /newbot，按提示拿到一个 token
2. 找 @userinfobot 拿到你自己的数字 user id（chat id）
3. 把它们填进 memory/telegram.md，或用环境变量 TELEGRAM_TOKEN / TELEGRAM_CHAT_ID

安全：只响应 telegram.md 里 allowed_chat_id 指定的那个人，别人一律忽略。
"""

import os
import json
import time
import urllib.parse
import urllib.request

from agent_core import (
    make_client, build_system_prompt, run_agent_autodeny, read_memory_file,
)

API = "https://api.telegram.org/bot{token}/{method}"


def _load_config():
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    raw = read_memory_file("telegram.md")
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("token:"):
            token = line.split(":", 1)[1].strip() or token
        elif line.startswith("allowed_chat_id:"):
            chat_id = line.split(":", 1)[1].strip() or chat_id
    return token.strip(), chat_id.strip()


def _api(token, method, params):
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=70) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _send_message(token, chat_id, text):
    for i in range(0, len(text), 4000):
        _api(token, "sendMessage", {"chat_id": chat_id, "text": text[i:i + 4000]})


def run_bot(use_local=True, model="qwen2.5", stop_flag=None):
    token, allowed = _load_config()
    if not token:
        print("没配置 Telegram token。")
        return
    if not allowed:
        print("没设 allowed_chat_id，为安全拒绝服务任何人。")
        return

    print(f"Telegram bot 已启动，只服务 chat_id={allowed}。")
    client = make_client(use_local)
    offset = None
    histories = {}

    while True:
        if stop_flag and stop_flag():
            return
        try:
            params = {"timeout": 60}
            if offset is not None:
                params["offset"] = offset
            resp = _api(token, "getUpdates", params)
        except Exception as e:
            print(f"拉取消息出错：{e}")
            time.sleep(3)
            continue

        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            if chat_id != allowed:
                print(f"忽略陌生 chat_id={chat_id}")
                continue
            if text in ("/start", "/help"):
                _send_message(token, chat_id, "我是超能小助。直接发消息就行。")
                continue

            hist = histories.setdefault(chat_id, [])
            if not hist:
                hist.append({"role": "system", "content": build_system_prompt()})
            else:
                hist[0] = {"role": "system", "content": build_system_prompt()}
            hist.append({"role": "user", "content": text})
            try:
                reply, hist = run_agent_autodeny(client, model, hist)
                histories[chat_id] = hist
            except Exception as e:
                reply = f"出错了：{e}"
            _send_message(token, chat_id, reply or "（无回复）")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", action="store_true")
    ap.add_argument("--model", default="qwen2.5")
    args = ap.parse_args()
    run_bot(use_local=not args.cloud, model=args.model)
