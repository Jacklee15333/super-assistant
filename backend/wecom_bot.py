"""
wecom_bot.py — 企业微信双向对话（合规、稳定、免费）

腾讯官方接口，不违规、不封号。你在「企业微信」App 里和超能小助聊天。

准备（一次，都在 work.weixin.qq.com 后台）：
1. 注册企业微信（个人也能注册，免费）
2. 「应用管理」->「自建」一个应用，记下 AgentId 和 Secret
3. 「我的企业」里记下 CorpID
4. 应用的「接收消息」里设置 API 接收：填你的回调 URL、随机生成 Token 和 EncodingAESKey
5. 把 corp_id / agent_id / secret / token / aes_key 填进 memory/wecom.md

回调 URL 需要公网能访问（你电脑在路由器后面够不着），
用内网穿透（cpolar/natapp/frp）把本机 8756 端口映射出公网地址即可。详见 README。

安全：消息收发都经腾讯官方加密通道；只在你自己的企业内可见。
"""

import os
import time
import hashlib
import base64
import struct
import socket
import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

from agent_core import (
    read_memory_file, make_client, build_system_prompt, run_agent_autodeny,
)

# ---------- 配置读取 ----------
def load_config():
    cfg = {"corp_id": "", "agent_id": "", "secret": "",
           "token": "", "aes_key": ""}
    raw = read_memory_file("wecom.md")
    for line in raw.splitlines():
        line = line.strip()
        for k in cfg:
            if line.startswith(k + ":"):
                cfg[k] = line.split(":", 1)[1].strip()
    # 环境变量兜底
    cfg["corp_id"] = cfg["corp_id"] or os.environ.get("WECOM_CORP_ID", "")
    cfg["secret"] = cfg["secret"] or os.environ.get("WECOM_SECRET", "")
    return cfg


# ---------- 回调 URL 验证用的加解密（企业微信标准算法） ----------
def _sha1_signature(token, timestamp, nonce, encrypt):
    arr = sorted([token, timestamp, nonce, encrypt])
    return hashlib.sha1("".join(arr).encode("utf-8")).hexdigest()


def _aes_key_bytes(aes_key):
    return base64.b64decode(aes_key + "=")


def _pkcs7_unpad(data):
    pad = data[-1]
    if pad < 1 or pad > 32:
        return data
    return data[:-pad]


def _pkcs7_pad(data):
    block = 32
    pad = block - (len(data) % block)
    return data + bytes([pad]) * pad


def _aes_cbc_decrypt(key, data):
    """AES-CBC 解密。优先用 cryptography，回退 pycryptodome。"""
    try:
        from cryptography.hazmat.primitives.ciphers import (
            Cipher, algorithms, modes)
        c = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
        d = c.decryptor()
        return d.update(data) + d.finalize()
    except ImportError:
        from Crypto.Cipher import AES
        return AES.new(key, AES.MODE_CBC, key[:16]).decrypt(data)


def _aes_cbc_encrypt(key, data):
    """AES-CBC 加密。优先用 cryptography，回退 pycryptodome。"""
    try:
        from cryptography.hazmat.primitives.ciphers import (
            Cipher, algorithms, modes)
        c = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
        e = c.encryptor()
        return e.update(data) + e.finalize()
    except ImportError:
        from Crypto.Cipher import AES
        return AES.new(key, AES.MODE_CBC, key[:16]).encrypt(data)


def decrypt_msg(aes_key, encrypt_b64, corp_id):
    """解密企业微信回调密文，返回明文 XML。"""
    key = _aes_key_bytes(aes_key)
    plain = _aes_cbc_decrypt(key, base64.b64decode(encrypt_b64))
    plain = _pkcs7_unpad(plain)
    content = plain[16:]
    msg_len = struct.unpack(">I", content[:4])[0]
    msg = content[4:4 + msg_len].decode("utf-8")
    return msg


def encrypt_msg(aes_key, plain, corp_id):
    """加密回复（企业微信要求被动回复也加密）。"""
    key = _aes_key_bytes(aes_key)
    rand = os.urandom(16)
    text = plain.encode("utf-8")
    payload = rand + struct.pack(">I", len(text)) + text + corp_id.encode("utf-8")
    enc = _aes_cbc_encrypt(key, _pkcs7_pad(payload))
    return base64.b64encode(enc).decode("utf-8")


# ---------- 主动发消息（拿 access_token 调 send 接口） ----------
_token_cache = {"token": "", "expire": 0}


def _get_access_token(cfg):
    now = time.time()
    if _token_cache["token"] and _token_cache["expire"] > now + 60:
        return _token_cache["token"]
    url = ("https://qyapi.weixin.qq.com/cgi-bin/gettoken"
           f"?corpid={cfg['corp_id']}&corpsecret={cfg['secret']}")
    with urllib.request.urlopen(url, timeout=15) as resp:
        r = json.loads(resp.read().decode("utf-8"))
    if r.get("errcode", 0) != 0:
        raise RuntimeError(f"获取 token 失败：{r}")
    _token_cache["token"] = r["access_token"]
    _token_cache["expire"] = now + r.get("expires_in", 7200)
    return r["access_token"]


def send_to_user(cfg, user_id, text):
    """主动给某个成员发消息（供心跳推送用）。"""
    token = _get_access_token(cfg)
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    body = json.dumps({
        "touser": user_id or "@all",
        "msgtype": "text",
        "agentid": int(cfg["agent_id"]),
        "text": {"content": text},
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------- 处理回调消息（被 server.py 调用） ----------
_histories = {}


def handle_callback_get(cfg, qs):
    """URL 验证：企业微信首次配置会发 GET，要求原样返回解密后的 echostr。"""
    msg_sig = qs.get("msg_signature", [""])[0]
    ts = qs.get("timestamp", [""])[0]
    nonce = qs.get("nonce", [""])[0]
    echostr = qs.get("echostr", [""])[0]
    sig = _sha1_signature(cfg["token"], ts, nonce, echostr)
    if sig != msg_sig:
        return None
    try:
        return decrypt_msg(cfg["aes_key"], echostr, cfg["corp_id"])
    except Exception:
        return None


def handle_callback_post(cfg, qs, body_xml, use_local, model):
    """收到用户消息：解密 -> 跑 agent -> 加密回复。"""
    msg_sig = qs.get("msg_signature", [""])[0]
    ts = qs.get("timestamp", [""])[0]
    nonce = qs.get("nonce", [""])[0]
    try:
        root = ET.fromstring(body_xml)
        encrypt = root.find("Encrypt").text
    except Exception:
        return ""
    if _sha1_signature(cfg["token"], ts, nonce, encrypt) != msg_sig:
        return ""

    try:
        plain = decrypt_msg(cfg["aes_key"], encrypt, cfg["corp_id"])
        msg = ET.fromstring(plain)
        content = (msg.find("Content").text or "").strip()
        from_user = msg.find("FromUserName").text
    except Exception:
        return ""

    if not content:
        return ""

    # 跑 agent（带历史）
    hist = _histories.setdefault(from_user, [])
    if not hist:
        hist.append({"role": "system", "content": build_system_prompt()})
    else:
        hist[0] = {"role": "system", "content": build_system_prompt()}
    hist.append({"role": "user", "content": content})
    try:
        client = make_client(use_local)
        reply, hist = run_agent_autodeny(client, model, hist)
        _histories[from_user] = hist
    except Exception as e:
        reply = f"出错了：{e}"

    # 被动回复（加密的 XML）
    enc = encrypt_msg(cfg["aes_key"], _build_reply_xml(from_user, msg, reply),
                      cfg["corp_id"])
    new_ts = str(int(time.time()))
    new_nonce = str(int(time.time() * 1000) % 1000000)
    sig = _sha1_signature(cfg["token"], new_ts, new_nonce, enc)
    return (f"<xml><Encrypt><![CDATA[{enc}]]></Encrypt>"
            f"<MsgSignature><![CDATA[{sig}]]></MsgSignature>"
            f"<TimeStamp>{new_ts}</TimeStamp>"
            f"<Nonce><![CDATA[{new_nonce}]]></Nonce></xml>")


def _build_reply_xml(to_user, in_msg, content):
    from_user = in_msg.find("ToUserName").text
    return (f"<xml><ToUserName><![CDATA[{to_user}]]></ToUserName>"
            f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            f"<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{content}]]></Content></xml>")
