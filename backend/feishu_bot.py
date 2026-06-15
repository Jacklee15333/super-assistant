"""
feishu_bot.py — 飞书双向对话（官方接口，体验最顺）

准备（一次，都在 open.feishu.cn 开发者后台）：
1. 创建一个「企业自建应用」，记下 App ID 和 App Secret
2. 开启「机器人」能力
3. 「事件订阅」里填回调 URL（需公网，见 README 的内网穿透），
   订阅 im.message.receive_v1 事件
4. 给应用开通发消息权限：im:message
5. 把 app_id / app_secret / verification_token 填进 memory/feishu.md

回调 URL 同样需要公网可访问，用内网穿透打通。
"""

import os
import json
import time
import urllib.request

from agent_core import (
    read_memory_file, make_client, build_system_prompt, run_agent_autodeny,
)


def load_config():
    cfg = {"app_id": "", "app_secret": "", "verification_token": ""}
    raw = read_memory_file("feishu.md")
    for line in raw.splitlines():
        line = line.strip()
        for k in cfg:
            if line.startswith(k + ":"):
                cfg[k] = line.split(":", 1)[1].strip()
    cfg["app_id"] = cfg["app_id"] or os.environ.get("FEISHU_APP_ID", "")
    cfg["app_secret"] = cfg["app_secret"] or os.environ.get("FEISHU_APP_SECRET", "")
    return cfg


_token_cache = {"token": "", "expire": 0}


def _get_tenant_token(cfg):
    now = time.time()
    if _token_cache["token"] and _token_cache["expire"] > now + 60:
        return _token_cache["token"]
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": cfg["app_id"],
                       "app_secret": cfg["app_secret"]}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        r = json.loads(resp.read().decode("utf-8"))
    _token_cache["token"] = r.get("tenant_access_token", "")
    _token_cache["expire"] = now + r.get("expire", 7000)
    return _token_cache["token"]


def send_message(cfg, open_id, text):
    """给某个用户发消息。"""
    token = _get_tenant_token(cfg)
    url = ("https://open.feishu.cn/open-apis/im/v1/messages"
           "?receive_id_type=open_id")
    body = json.dumps({
        "receive_id": open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


_histories = {}
_seen_msg_ids = set()  # 飞书可能重发事件，去重


def handle_event(cfg, body, use_local, model):
    """
    处理飞书事件回调。返回要响应给飞书的 dict。
    - URL 验证：返回 {challenge}
    - 消息事件：跑 agent，主动发回复，返回 {}
    """
    try:
        data = json.loads(body)
    except Exception:
        return {}

    # URL 验证握手
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge", "")}

    # 校验 token（防伪造）
    header = data.get("header", {})
    if cfg.get("verification_token"):
        token = header.get("token") or data.get("token")
        if token and token != cfg["verification_token"]:
            return {}

    event = data.get("event", {})
    msg = event.get("message", {})
    msg_id = msg.get("message_id", "")
    if msg_id and msg_id in _seen_msg_ids:
        return {}  # 重复事件，忽略
    if msg_id:
        _seen_msg_ids.add(msg_id)
        if len(_seen_msg_ids) > 1000:
            _seen_msg_ids.clear()

    # 取文本内容
    try:
        content = json.loads(msg.get("content", "{}")).get("text", "").strip()
    except Exception:
        content = ""
    sender = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
    if not content or not sender:
        return {}

    # 跑 agent
    hist = _histories.setdefault(sender, [])
    if not hist:
        hist.append({"role": "system", "content": build_system_prompt()})
    else:
        hist[0] = {"role": "system", "content": build_system_prompt()}
    hist.append({"role": "user", "content": content})
    try:
        client = make_client(use_local)
        reply, hist = run_agent_autodeny(client, model, hist)
        _histories[sender] = hist
    except Exception as e:
        reply = f"出错了：{e}"

    try:
        send_message(cfg, sender, reply or "（无回复）")
    except Exception:
        pass
    return {}
