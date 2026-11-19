"""超能小助 · 飞书机器人长连接小进程（v84）

由 feishu_inbox.py 启动（单独一个进程：飞书官方 SDK 用的是全局事件循环，放在后端进程里没法干净地重启）。
它只做一件事：连上飞书，收到「用户发给机器人的消息」就原样转给本机后端 /feishu_inbox/incoming，
怎么处理（找链接、排队、回复）全在后端。不需要公网 IP，也不用开端口。

环境变量：FEISHU_APP_ID、FEISHU_APP_SECRET、CX_BACKEND（http://127.0.0.1:8756）、CX_RUN（这次运行的编号）
往 stdout 打 "STATE xxx" 行告诉后端现在的状态：connecting / connected / error <原因>。
后端没了、或者后端说「你是旧的」（换了账号 / 关掉了），自己退出。
"""

import json
import logging
import os
import sys
import threading
import time
import urllib.request

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
BACKEND = os.environ.get("CX_BACKEND", "http://127.0.0.1:8756")
RUN = os.environ.get("CX_RUN", "")


def say(line):
    try:
        sys.stdout.write(line.replace("\n", " ") + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def post(path, obj, timeout=10):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BACKEND + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def watchdog():
    """每 15 秒问一下后端：我还该不该活着。后端连不上 4 次（1 分钟）或者说不要了，就退出。"""
    miss = 0
    while True:
        time.sleep(15)
        try:
            r = post("/feishu_inbox/alive", {"run": RUN}, timeout=5)
            miss = 0
            if not r.get("ok"):
                say("STATE exit 后端说这个连接不用了")
                os._exit(0)
        except Exception:
            miss += 1
            if miss >= 4:
                say("STATE exit 后端不在了")
                os._exit(0)


class _StateLog(logging.Handler):
    """把 SDK 的日志翻成状态行。"""

    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return
        low = msg.lower()
        if "connected to" in low and "disconnected" not in low:
            say("STATE connected")
        elif "disconnected" in low or "receive message loop exit" in low:
            say("STATE connecting 连接断了，正在重连")
        elif "connect failed" in low:
            say("STATE error " + msg[-300:])


def main():
    if not (APP_ID and APP_SECRET and RUN):
        say("STATE error 缺 App ID / App Secret")
        return 2
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
    except Exception as e:
        say("STATE error 没装飞书组件 lark-oapi（%s）" % e)
        return 3

    lg = logging.getLogger("Lark")
    lg.addHandler(_StateLog())

    def on_message(data: P2ImMessageReceiveV1) -> None:
        try:
            ev = json.loads(lark.JSON.marshal(data.event) or "{}")
        except Exception as e:
            say("LOG 读消息出错：%s" % e)
            return
        try:
            r = post("/feishu_inbox/incoming", {"run": RUN, "event": ev})
            if r.get("exit"):
                say("STATE exit 后端说这个连接不用了")
                os._exit(0)
        except Exception as e:
            say("LOG 转给软件失败：%s" % e)

    def on_other(_data) -> None:     # 别的事件（比如「进入和机器人的单聊」）不处理
        return

    builder = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message)
    for name in ("register_p2_im_chat_access_event_bot_p2p_chat_entered_v1",
                 "register_p2_im_message_message_read_v1"):
        try:
            builder = getattr(builder, name)(on_other)
        except Exception:
            pass
    handler = builder.build()

    threading.Thread(target=watchdog, daemon=True).start()
    say("STATE connecting")
    cli = lark.ws.Client(APP_ID, APP_SECRET, event_handler=handler, log_level=lark.LogLevel.INFO)
    try:
        cli.start()               # 一直跑；断了 SDK 自己重连
    except Exception as e:
        txt = str(e)
        if "1000040345" in txt or "app" in txt.lower() and "secret" in txt.lower():
            txt = "App ID 或 App Secret 不对（%s）" % txt
        say("STATE error " + txt[-300:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
