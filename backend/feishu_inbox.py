"""超能小助 · 在外面也能发：飞书机器人收链接（v84）

你在手机飞书里把链接发给自己建的机器人 → 电脑上的超能小助收到 → 加进「视频内容提取」队列；
机器人马上回一句「收到了」，提取完再回一句「提取完了：标题」。

  - 用飞书「长连接」收消息：电脑不需要公网 IP、不用开端口、不用内网穿透；
  - 连接由单独的小进程 feishu_inbox_worker.py 维持（官方 SDK lark-oapi，缺了自动装）；
  - 电脑关机 / 软件没开时发的链接：下次连上后，按聊天记录「补收」（只补 7 天内的）；
  - 只处理「单聊里人发给机器人」的消息；同一条消息只处理一次。

配置在 memory/feishu_inbox.json：app_id、app_secret、enabled、chats（和机器人的单聊）、seen（处理过的消息）。
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_DIR, "memory", "feishu_inbox.json")
API = os.environ.get("CX_FEISHU_API") or "https://open.feishu.cn/open-apis"   # 环境变量只给测试用
SDK_PIN = "lark-oapi==1.7.5"
CATCHUP_DAYS = 7

_lock = threading.RLock()
_cfg = None
_log_fn = None
_backend = "http://127.0.0.1:8756"

_state = {"state": "off", "error": "", "since": 0, "installing": False, "install_log": "",
          "last_msg": 0, "catchup": ""}
_run = {"id": "", "proc": None}
_mgr = {"thread": None, "wake": threading.Event()}
_tok = {"v": "", "exp": 0, "key": ""}


def _log(msg):
    try:
        if _log_fn:
            _log_fn("飞书", msg)
        else:
            print("[飞书] " + msg, flush=True)
    except Exception:
        pass


# ════════════════ 配置 ════════════════

def _load():
    global _cfg
    if _cfg is not None:
        return _cfg
    try:
        with open(_CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
    except Exception:
        cfg = {}
    cfg.setdefault("enabled", False)
    cfg.setdefault("app_id", "")
    cfg.setdefault("app_secret", "")
    if not isinstance(cfg.get("chats"), dict):
        cfg["chats"] = {}             # chat_id -> 最后处理到的消息时间（毫秒）
    if not isinstance(cfg.get("seen"), list):
        cfg["seen"] = []
    _cfg = cfg
    return _cfg


def _save():
    try:
        os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
        tmp = _CFG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _CFG_PATH)
    except Exception as e:
        _log("保存设置失败：%s" % e)


def _configured(cfg=None):
    cfg = cfg or _load()
    return bool(cfg.get("app_id") and cfg.get("app_secret"))


def status():
    with _lock:
        cfg = _load()
        st = dict(_state)
        st.update({
            "enabled": bool(cfg["enabled"]), "configured": _configured(cfg),
            "app_id": cfg.get("app_id", ""),
            "secret_set": bool(cfg.get("app_secret")),
            "bound": bool(cfg["chats"]),
            "sdk": _sdk_ok(),
        })
        return st


def _set_state(state, error=""):
    with _lock:
        if _state["state"] != state or _state["error"] != error:
            _state["since"] = time.time()
        _state["state"] = state
        _state["error"] = error


# ════════════════ 飞书开放接口（标准库直连）════════════════

def _http(method, path, token=None, body=None, timeout=15):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return {"code": e.code, "msg": "HTTP %d" % e.code}


def _token(app_id=None, app_secret=None, force=False):
    """拿 tenant_access_token；返回 (token, 错误话术)。"""
    with _lock:
        cfg = _load()
        app_id = app_id or cfg.get("app_id")
        app_secret = app_secret or cfg.get("app_secret")
        key = app_id + ":" + app_secret
        if not force and _tok["v"] and _tok["key"] == key and time.time() < _tok["exp"] - 120:
            return _tok["v"], ""
    try:
        r = _http("POST", "/auth/v3/tenant_access_token/internal",
                  body={"app_id": app_id, "app_secret": app_secret})
    except Exception as e:
        return "", "连不上飞书服务器（%s）" % e
    if r.get("code") == 0 and r.get("tenant_access_token"):
        with _lock:
            _tok.update(v=r["tenant_access_token"], exp=time.time() + int(r.get("expire") or 3600), key=key)
        return r["tenant_access_token"], ""
    return "", "App ID 或 App Secret 不对（飞书说：%s）" % (r.get("msg") or r.get("code"))


def _hint(r, what):
    code = r.get("code")
    msg = r.get("msg") or ""
    if code in (99991672, 99991679) or "permission" in msg.lower() or "access denied" in msg.lower():
        return "%s失败：机器人缺权限（%s）。去飞书开放平台「权限管理」开通说明里那几项，再「发布版本」" % (what, msg)
    if code == 230002:
        return "%s失败：机器人不在这个会话里" % what
    return "%s失败（%s %s）" % (what, code, msg)


def reply(message_id, text):
    tok, err = _token()
    if not tok:
        _log("回消息失败：" + err)
        return False
    r = _http("POST", "/im/v1/messages/%s/reply" % urllib.parse.quote(message_id), tok,
              {"msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)})
    if r.get("code") != 0:
        _log(_hint(r, "回消息"))
        return False
    return True


# ════════════════ 收到消息 ════════════════

def _strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("image_key", "file_key", "user_id", "style"):
                continue
            _strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _strings(v, out)


def _message_text(msg_type, content):
    """飞书消息的 content 是 JSON 字符串：text 是 {"text":…}；富文本 post 是一层层的段落，链接在 href 里。"""
    try:
        c = json.loads(content or "{}")
    except Exception:
        return content or ""
    parts = []
    _strings(c, parts)
    return "\n".join(parts)


_URL_RE = re.compile(r"https?://[^\s<>\"'，。！？、；：（）()【】《》「」]+")

HELP = ("把文章或视频的链接（或整段分享文案）发给我，我就交给电脑上的超能小助提取保存。\n"
        "· 想顺便让 AI 分析：在链接后面加「分析」两个字\n"
        "· 不要 AI 分析：加「不分析」\n"
        "· 不加的话，按电脑上上次的设置来\n"
        "· 一次可以发好几个链接")


def _seen(mid):
    with _lock:
        cfg = _load()
        if mid in cfg["seen"]:
            return True
        cfg["seen"].append(mid)
        del cfg["seen"][:-500]
        return False


def handle_message(msg, sender_type="user", catchup=False):
    """处理一条消息（实时收到的，或补收的）。msg 是飞书的 message 对象（dict）。"""
    mid = msg.get("message_id") or ""
    if not mid or sender_type != "user":
        return
    if msg.get("chat_type") and msg.get("chat_type") != "p2p":
        return                                   # 只管单聊，不在群里乱回
    if _seen(mid):
        return
    chat = msg.get("chat_id") or ""
    try:
        ct = int(msg.get("create_time") or 0)
    except Exception:
        ct = 0
    with _lock:
        cfg = _load()
        if chat:
            cfg["chats"][chat] = max(int(cfg["chats"].get(chat) or 0), ct)
        _state["last_msg"] = time.time()
        _save()
    text = _message_text(msg.get("message_type") or msg.get("msg_type"), msg.get("content")
                         or (msg.get("body") or {}).get("content"))
    urls = []
    for u in _URL_RE.findall(text or ""):
        u = u.rstrip(".,;:!?)]}>'\"")
        if u not in urls:
            urls.append(u)
    pre = "（这是你在电脑没开时发的，现在补上）" if catchup else ""
    if not urls:
        if not catchup:
            reply(mid, HELP)
        return
    flag = None
    if re.search(r"不(要)?(用)?\s*(AI)?\s*分析", text or "", re.I):
        flag = False
    elif re.search(r"分析", re.sub(r"https?://\S+", "", text or "")):
        flag = True
    import phone_inbox
    clean = re.sub(r"(不(要)?(用)?\s*(AI)?\s*分析|(AI)?\s*分析(一下)?)\s*$", "", (text or "").strip(), flags=re.I)
    lines = []
    for i, u in enumerate(urls[:10]):
        one = clean if len(urls) == 1 else u
        r = phone_inbox.queue_text(one, flag, source="飞书",
                                   notify={"kind": "feishu", "message_id": mid})
        if r.get("ok"):
            lines.append("✓ %s%s" % ((r.get("title") + "：") if r.get("title") else "", r["msg"]))
        else:
            lines.append("✗ %s（%s）" % (r.get("error"), u[:60]))
    if len(urls) > 10:
        lines.append("一次最多 10 个，后面的请再发一次")
    tail = ""
    if any(l.startswith("✓") for l in lines):
        tail = "\n提取完了我再告诉你。"
    reply(mid, pre + "收到！\n" + "\n".join(lines) + tail)


def incoming(body):
    """worker 转来的实时消息。返回给 worker 的话（exit=换人了）。"""
    if body.get("run") != _run["id"]:
        return {"ok": False, "exit": True}
    ev = body.get("event") or {}
    msg = ev.get("message") or {}
    stype = (ev.get("sender") or {}).get("sender_type") or "user"
    threading.Thread(target=_safe_handle, args=(msg, stype, False), daemon=True).start()
    return {"ok": True}


def _safe_handle(msg, stype, catchup):
    try:
        handle_message(msg, stype, catchup)
    except Exception as e:
        _log("处理消息出错：%s" % e)


def alive(body):
    return {"ok": bool(body.get("run")) and body.get("run") == _run["id"]}


def job_done(job, res, requeued=False):
    """视频队列做完一条从飞书来的任务后调用：回一句结果。"""
    n = job.get("notify") or {}
    if n.get("kind") != "feishu" or not n.get("message_id"):
        return
    if requeued:
        return                                    # 还要自动重试，等最后结果再说

    def _go():
        title = (res.get("title") or job.get("title") or job.get("url") or "")[:60]
        if res.get("ok"):
            extra = "（AI 分析也做好了）" if (job.get("analyze") and not res.get("unanalyzed")) else ""
            txt = "✅ 提取完了：%s%s\n已存进超能小助的笔记里。" % (title, extra)
        elif res.get("cancelled"):
            txt = "🛑 这条在电脑上被取消了：%s" % title
        else:
            txt = "⚠ 这条没提取成功：%s\n原因：%s" % (title, (res.get("error") or "不明")[:150])
        reply(n["message_id"], txt)
    threading.Thread(target=_go, daemon=True).start()


# ════════════════ 补收：电脑没开时发的 ════════════════

def catch_up():
    tok, err = _token()
    if not tok:
        return
    with _lock:
        chats = dict(_load()["chats"])
    if not chats:
        return
    now = int(time.time())
    total = 0
    for chat, last_ms in chats.items():
        start = max(int(last_ms or 0) // 1000, now - CATCHUP_DAYS * 86400)
        page = ""
        for _ in range(10):
            q = {"container_id_type": "chat", "container_id": chat, "start_time": str(start),
                 "end_time": str(now + 60), "sort_type": "ByCreateTimeAsc", "page_size": "50"}
            if page:
                q["page_token"] = page
            r = _http("GET", "/im/v1/messages?" + urllib.parse.urlencode(q), tok)
            if r.get("code") != 0:
                with _lock:
                    _state["catchup"] = _hint(r, "补收没开机时的消息")
                _log(_state["catchup"])
                return
            d = r.get("data") or {}
            for it in d.get("items") or []:
                if (it.get("sender") or {}).get("sender_type") != "user" or it.get("deleted"):
                    continue
                with _lock:
                    done = it.get("message_id") in _load()["seen"]
                if done:
                    continue
                total += 1
                it = dict(it)
                it["chat_type"] = "p2p"
                it["content"] = (it.get("body") or {}).get("content") or ""
                _safe_handle(it, "user", True)
            if not d.get("has_more"):
                break
            page = d.get("page_token") or ""
    with _lock:
        _state["catchup"] = ("补收了 %d 条电脑没开时发的消息" % total) if total else ""
    if total:
        _log("补收了 %d 条电脑没开时发来的消息" % total)


# ════════════════ 飞书组件（lark-oapi）════════════════

def _sdk_ok():
    try:
        import importlib.util
        return importlib.util.find_spec("lark_oapi") is not None
    except Exception:
        return False


def _install_sdk():
    with _lock:
        if _state["installing"]:
            return False
        _state["installing"] = True
    _set_state("installing")
    _log("第一次用，正在安装飞书组件 lark-oapi（约 1 分钟）…")
    ok = False
    for extra in ([], ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                  ["-i", "https://mirrors.aliyun.com/pypi/simple/"]):
        try:
            kw = {}
            if os.name == "nt":
                kw["creationflags"] = 0x08000000
            p = subprocess.run([sys.executable, "-m", "pip", "install", SDK_PIN] + extra,
                               capture_output=True, text=True, timeout=600, **kw)
            with _lock:
                _state["install_log"] = (p.stdout + p.stderr)[-1500:]
            if p.returncode == 0:
                ok = True
                break
        except Exception as e:
            with _lock:
                _state["install_log"] = str(e)
    try:
        import importlib
        importlib.invalidate_caches()
    except Exception:
        pass
    with _lock:
        _state["installing"] = False
    if ok and _sdk_ok():
        _log("✓ 飞书组件装好了")
        return True
    _set_state("error", "飞书组件 lark-oapi 没装上：检查一下网络，或在命令行运行  %s -m pip install %s"
               % (sys.executable, SDK_PIN))
    _log(_state["error"])
    return False


# ════════════════ 连接管理 ════════════════

def _stop_proc():
    with _lock:
        p, _run["proc"] = _run["proc"], None
        _run["id"] = ""
    if p is not None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def _reader(p, run_id):
    first_conn = True
    for line in iter(p.stdout.readline, ""):
        line = (line or "").strip()
        if run_id != _run["id"]:
            break
        if line.startswith("STATE "):
            parts = line.split(" ", 2)
            st = parts[1] if len(parts) > 1 else ""
            info = parts[2] if len(parts) > 2 else ""
            if st == "connected":
                _set_state("connected")
                _log("✓ 已连上飞书：手机上把链接发给机器人就行")
                if first_conn:
                    first_conn = False
                    threading.Thread(target=catch_up, daemon=True).start()
            elif st == "connecting":
                _set_state("connecting", info)
            elif st == "error":
                low = info.lower()
                if "nameresolution" in low or "max retries" in low or "timed out" in low or "connection" in low:
                    info = "连不上飞书服务器（电脑没网，或网络不稳定）；软件会自己一直重试。原始信息：" + info[-120:]
                elif "1000040345" in info or "secret" in low or "auth" in low:
                    info = "飞书不认这组 App ID / App Secret：检查一下有没有复制错。原始信息：" + info[-120:]
                _set_state("error", info)
                _log("连接出错：" + info)
        elif line.startswith("LOG "):
            _log(line[4:])


def _manager():
    backoff = 10
    while True:
        with _lock:
            cfg = _load()
            want = cfg["enabled"] and _configured(cfg)
            p = _run["proc"]
        if not want:
            _stop_proc()
            _set_state("off" if not cfg["enabled"] else "error",
                       "" if not cfg["enabled"] else "还没填 App ID / App Secret")
            _mgr["wake"].wait(30)
            _mgr["wake"].clear()
            continue
        if p is not None and p.poll() is None:
            if _state["state"] == "connected":
                backoff = 10
            _mgr["wake"].wait(10)
            _mgr["wake"].clear()
            continue
        if p is not None:                          # 小进程退出了：等一会儿再起
            _stop_proc()
            _mgr["wake"].wait(backoff)
            _mgr["wake"].clear()
            backoff = min(backoff * 2, 300)
            continue
        if not _sdk_ok() and not _install_sdk():
            _mgr["wake"].wait(600)
            _mgr["wake"].clear()
            continue
        tok, err = _token(force=True)
        if not tok:
            _set_state("error", err)
            _mgr["wake"].wait(backoff)
            _mgr["wake"].clear()
            backoff = min(backoff * 2, 300)
            continue
        run_id = uuid.uuid4().hex
        env = dict(os.environ)
        env.update({"FEISHU_APP_ID": cfg["app_id"], "FEISHU_APP_SECRET": cfg["app_secret"],
                    "CX_BACKEND": _backend, "CX_RUN": run_id, "PYTHONIOENCODING": "utf-8",
                    "PYTHONUNBUFFERED": "1"})
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x08000000      # 不弹黑窗口
        try:
            proc = subprocess.Popen([sys.executable, os.path.join(_DIR, "feishu_inbox_worker.py")],
                                    cwd=_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                    errors="replace", **kw)
        except Exception as e:
            _set_state("error", "飞书连接小进程起不来：%s" % e)
            _mgr["wake"].wait(60)
            _mgr["wake"].clear()
            continue
        with _lock:
            _run.update(id=run_id, proc=proc)
        _set_state("connecting")
        threading.Thread(target=_reader, args=(proc, run_id), daemon=True).start()


def _ensure_manager():
    with _lock:
        t = _mgr["thread"]
        if t is None or not t.is_alive():
            t = threading.Thread(target=_manager, name="feishu-inbox", daemon=True)
            _mgr["thread"] = t
            t.start()
    _mgr["wake"].set()


def configure(app_id=None, app_secret=None, enabled=None):
    """界面上「保存并连接」/ 开关。先验证 App ID / Secret 对不对。"""
    with _lock:
        cfg = _load()
        new_id = (app_id if app_id is not None else cfg["app_id"]).strip()
        new_secret = (app_secret if app_secret else cfg["app_secret"]).strip()
    changed = new_id != cfg["app_id"] or new_secret != cfg["app_secret"]
    if (enabled or (enabled is None and cfg["enabled"])) and new_id and new_secret:
        tok, err = _token(new_id, new_secret, force=True)
        if not tok:
            st = status()
            st.update(ok=False, error=err)
            return st
    with _lock:
        cfg["app_id"], cfg["app_secret"] = new_id, new_secret
        if enabled is not None:
            cfg["enabled"] = bool(enabled)
        if changed:
            cfg["chats"] = {}
        _save()
    if changed or enabled is False:
        _stop_proc()
    _ensure_manager()
    st = status()
    st["ok"] = True
    return st


def boot(log=None, backend=None):
    global _log_fn, _backend
    _log_fn = log
    if backend:
        _backend = backend
    try:
        import atexit
        atexit.register(shutdown)
    except Exception:
        pass
    _ensure_manager()


def shutdown():
    _stop_proc()
