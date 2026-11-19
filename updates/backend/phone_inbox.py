"""超能小助 · 手机发链接（v83）

手机和电脑连同一个 Wi-Fi 时，手机浏览器打开 http://电脑IP:8757 ，把文章 / 视频链接
（或整段分享文案）粘进去点「发给电脑」，电脑就把它加进「视频内容提取」的队列，和在电脑上
粘贴是同一套流程（文章先读正文，视频走字幕 / 听写）。

安全：
  - 默认关闭，要在电脑上「手机发链接」面板里打开；
  - 只接受局域网地址（192.168.x / 10.x / 172.16-31.x / 100.64-127.x 等）来的请求；
  - 每次都要带 6 位连接码（扫码打开的网址里已经带上了），码可以随时在电脑上换；
  - 只开放「发链接」「看最近发了什么」两件事，软件别的接口一个都不对手机开放。

server.py 启动时调 boot(Handler, log)；配置存在 memory/phone_inbox.json。
"""

import ipaddress
import json
import os
import random
import re
import socket
import threading
import time
import urllib.parse
from http.server import ThreadingHTTPServer

PORT = 8757
_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_DIR, "memory", "phone_inbox.json")

_lock = threading.Lock()
_cfg = None                 # {"enabled", "code", "defaults"}
_server = None
_thread = None
_err = ""                   # 最近一次开启失败的原因（给界面看）
_base_handler = None
_log_fn = None
_recent = []                # 最近收到的链接（新的在前）
_seq = 0                    # 收到过几条（界面靠它判断有没有新的）
_bad = {}                   # ip -> [失败时间...]

_DEFAULT_KEYS = ("level", "use_local", "model", "mode", "screenshot", "link", "analyze")


def _log(msg, tag="手机"):
    try:
        if _log_fn:
            _log_fn(tag, msg)
        else:
            print("[%s] %s" % (tag, msg), flush=True)
    except Exception:
        pass


def _new_code():
    return "%06d" % random.SystemRandom().randint(0, 999999)


def _load():
    global _cfg
    if _cfg is not None:
        return _cfg
    cfg = {}
    try:
        with open(_CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
    except Exception:
        cfg = {}
    if not re.fullmatch(r"\d{6}", str(cfg.get("code") or "")):
        cfg["code"] = _new_code()
    cfg["enabled"] = bool(cfg.get("enabled", False))
    if not isinstance(cfg.get("defaults"), dict):
        cfg["defaults"] = {}
    _cfg = cfg
    _save()
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


def remember_defaults(body):
    """电脑上点「提取并分析」时记下当时的选项（质量、模型、要不要 AI 分析…），手机发来的链接照这个办。"""
    try:
        with _lock:
            cfg = _load()
            d = {k: body.get(k) for k in _DEFAULT_KEYS if k in body}
            if d and d != cfg.get("defaults"):
                cfg["defaults"] = d
                _save()
    except Exception:
        pass


# ════════════════ 局域网地址 ════════════════

def _is_lan(ip):
    try:
        a = ipaddress.ip_address((ip or "").split("%")[0])
        if getattr(a, "ipv4_mapped", None):
            a = a.ipv4_mapped
        if a.is_loopback or a.is_link_local:
            return True
        if a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10"):
            return True          # 运营商内网 / Tailscale 这类组网工具
        return a.is_private
    except Exception:
        return False


def lan_ips():
    """电脑在局域网里的 IPv4 地址，常用的（能上网那块网卡）排第一个。"""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("223.5.5.5", 53))          # UDP 不真的发包，只是让系统选出口网卡
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except Exception:
        pass
    out = []
    for ip in ips:
        if ip and ip not in out and not ip.startswith("127.") and _is_lan(ip):
            out.append(ip)
    # 虚拟网卡（VMware / Hyper-V / WSL 常见 192.168.56.x、172.x）排到后面
    out.sort(key=lambda x: (x.startswith("172.") or x.startswith("192.168.56.") or x.startswith("192.168.137."),))
    return out


# ════════════════ 开 / 关 ════════════════

def status():
    with _lock:
        cfg = _load()
        running = _server is not None
        ips = lan_ips() if running else []
        return {
            "enabled": cfg["enabled"], "running": running, "error": _err,
            "port": PORT, "code": cfg["code"], "ips": ips,
            "urls": ["http://%s:%d/?k=%s" % (ip, PORT, cfg["code"]) for ip in ips],
            "seq": _seq, "recent": list(_recent[:20]),
            "analyze_default": bool(cfg["defaults"].get("analyze", False)),
        }


def set_enabled(on):
    with _lock:
        cfg = _load()
        cfg["enabled"] = bool(on)
        _save()
    if on:
        _start()
    else:
        _stop()
    return status()


def new_code():
    with _lock:
        cfg = _load()
        cfg["code"] = _new_code()
        _save()
    _log("连接码换成新的了（手机上要重新扫码）")
    return status()


def boot(base_handler, log=None):
    """server.py 启动时调用：记下 Handler，上次是开着的就接着开。"""
    global _base_handler, _log_fn
    _base_handler = base_handler
    _log_fn = log
    with _lock:
        on = _load()["enabled"]
    if on:
        _start()


def _start():
    global _server, _thread, _err
    with _lock:
        if _server is not None:
            return
        if _base_handler is None:
            _err = "后端还没准备好"
            return
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", PORT), _make_handler(_base_handler))
        except OSError as e:
            _err = "端口 %d 被占用或没权限（%s）" % (PORT, e)
            _log("开不起来：" + _err)
            return
        srv.daemon_threads = True
        _server = srv
        _err = ""
        _thread = threading.Thread(target=srv.serve_forever, name="phone-inbox", daemon=True)
        _thread.start()
    ips = lan_ips()
    _log("已打开：手机连同一个 Wi-Fi，浏览器打开 %s" %
         ("、".join("http://%s:%d" % (ip, PORT) for ip in ips) or "http://电脑IP:%d" % PORT))


def _stop():
    global _server, _thread
    with _lock:
        srv, _server, _thread = _server, None, None
    if srv is not None:
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass
        _log("已关闭")


# ════════════════ 收链接 ════════════════

def _first_url(text):
    try:
        import doc_import
        u = doc_import.first_url(text)
        if u:
            return u
    except Exception:
        pass
    m = re.search(r"https?://[^\s<>\"'，。！？、；：（）()【】《》「」]+", text or "")
    return m.group(0).rstrip(".,;:!?)]}>'\"") if m else ""


def _guess_title(text, url):
    """分享文案里链接前面那段一般就是标题（「【标题】https://…」「标题 https://…」）。"""
    t = (text or "").replace(url, " ")
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"复制(此|该)?链接.*|打开(抖音|Dou音|快手|小红书|微信).*|长按复制.*", " ", t)
    t = re.sub(r"[\s【】\[\]]+", " ", t).strip(" -—:：|")
    return t[:60]


def _record(item):
    global _seq
    with _lock:
        _seq += 1
        item["id"] = _seq
        _recent.insert(0, item)
        del _recent[30:]


def _check_code(ip, code):
    """连接码对不对；同一台设备 10 分钟内错 10 次就先锁住。返回 (ok, 错误话术)。"""
    now = time.time()
    with _lock:
        cfg = _load()
        fails = [t for t in _bad.get(ip, []) if now - t < 600]
        _bad[ip] = fails
        if len(fails) >= 10:
            return False, "连接码错太多次了，过 10 分钟再试"
        if str(code or "").strip() == cfg["code"]:
            return True, ""
        fails.append(now)
        return False, "连接码不对（看电脑上「手机发链接」面板里的 6 位数字）"


def queue_text(text, analyze, source="手机", notify=None, title=""):
    """把一段文字里的第一个链接加进「视频内容提取」队列（和电脑上点「提取并分析」同一套流程）。
    source：从哪来的（「手机」「飞书」），写进最近列表和日志；notify：做完要不要回消息（飞书用）。
    返回 {"ok", "msg"|"error", "url", "title"}。"""
    text = (text or "").strip()[:4000]
    url = _first_url(text)
    if not url:
        return {"ok": False, "error": "没找到链接：把文章或视频的链接（或整段分享文案）发过来", "url": ""}
    Base = _base_handler
    if Base is None:
        return {"ok": False, "error": "软件后端还没准备好，过一会儿再发", "url": url}
    with _lock:
        d = dict(_load().get("defaults") or {})
    body = {"level": "balanced", "use_local": True, "model": "qwen2.5", "mode": "auto",
            "screenshot": False, "link": False}
    body.update({k: v for k, v in d.items() if v is not None})
    if analyze is None:
        analyze = bool(d.get("analyze", False))
    body.update({"url": url, "analyze": bool(analyze), "creator_url": "", "_from_phone": True})
    if notify:
        body["notify"] = notify
    got = {}
    dummy = Base.__new__(Base)                     # 不连网络的「假请求」，只为复用入队逻辑
    dummy._send = lambda obj, status=200: got.update(obj=obj)
    try:
        Base._handle_video_transcribe(dummy, body)
    except Exception as e:
        got["obj"] = {"ok": False, "error": "电脑这边出错了：%s" % e}
    r = got.get("obj") or {}
    title = title or _guess_title(text, url)
    if r.get("queued"):
        pos = int(r.get("position") or 1)
        msg = "已加进电脑的提取队列，%s" % ("马上开始处理" if pos <= 1 else "排在第 %d 个" % pos)
        _record({"t": time.strftime("%H:%M"), "url": url, "title": title, "src": source,
                 "ok": True, "msg": msg, "analyze": bool(analyze)})
        _log("收到%s发来的%s：%s%s" % (source, "文章" if r.get("article") else "链接",
                                     (title + " ") if title else "", url), tag=source)
        return {"ok": True, "msg": msg, "url": url, "title": title, "article": bool(r.get("article"))}
    if r.get("need"):
        err = "电脑上还没装视频提取的小工具（%s）。先在电脑上提取一次视频，按提示装好；文章链接不受影响" \
              % "、".join(r.get("need") or [])
    else:
        err = r.get("error") or "没加进队列（原因不明）"
    _record({"t": time.strftime("%H:%M"), "url": url, "title": title, "src": source,
             "ok": False, "msg": err, "analyze": bool(analyze)})
    _log("%s发来的链接没加进去：%s（%s）" % (source, err, url), tag=source)
    return {"ok": False, "error": err, "url": url, "title": title}


def _make_handler(Base):
    class PhoneHandler(Base):
        """只开放手机要用的几个地址，别的一律 404。复用 Base 的 _handle_video_transcribe 入队。"""

        def log_message(self, *args):
            pass

        def _reply(self, status, ctype, data):
            body = data.encode("utf-8") if isinstance(data, str) else data
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._reply(status, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False))

        def _guard(self):
            ip = self.client_address[0] if self.client_address else ""
            if not _is_lan(ip):
                self._reply(403, "text/plain; charset=utf-8", "只接受同一个局域网里的设备")
                return False
            return True

        def _queue(self, text, analyze):
            return queue_text(text, analyze, source="手机")

        def do_GET(self):
            if not self._guard():
                return
            u = urllib.parse.urlparse(self.path)
            qs = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            ip = self.client_address[0]
            if u.path in ("/", "/m", "/index.html"):
                return self._reply(200, "text/html; charset=utf-8", PAGE)
            if u.path == "/favicon.ico":
                return self._reply(204, "text/plain", b"")
            if u.path == "/m/recent":
                ok, err = _check_code(ip, qs.get("k"))
                if not ok:
                    return self._json({"ok": False, "error": err, "bad_code": True}, 401)
                st = status()
                return self._json({"ok": True, "recent": st["recent"][:10],
                                   "analyze_default": st["analyze_default"]})
            if u.path == "/m/add":
                # 给手机「快捷指令」用：GET /m/add?k=连接码&u=链接[&analyze=1][&fmt=text]
                ok, err = _check_code(ip, qs.get("k"))
                if ok:
                    an = qs.get("analyze")
                    if an is None:
                        with _lock:
                            an = _load()["defaults"].get("analyze", False)
                    r = self._queue(qs.get("u") or qs.get("url") or "", str(an).lower() in ("1", "true", "yes", "on"))
                    ok, err = r.get("ok"), r.get("error") or ""
                    msg = r.get("msg", "")
                text = ("✓ " + msg) if ok else ("✗ " + err)
                if qs.get("fmt") == "text":
                    return self._reply(200 if ok else 400, "text/plain; charset=utf-8", text)
                return self._reply(200 if ok else 400, "text/html; charset=utf-8",
                                   '<!doctype html><meta charset="utf-8"><meta name="viewport" '
                                   'content="width=device-width,initial-scale=1"><body style="font:18px/1.6 '
                                   'sans-serif;padding:32px">%s</body>' % _esc(text))
            return self._reply(404, "text/plain; charset=utf-8", "not found")

        def do_POST(self):
            if not self._guard():
                return
            u = urllib.parse.urlparse(self.path)
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 64 * 1024)
                body = json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}
            except Exception:
                body = {}
            if u.path == "/m/send":
                ok, err = _check_code(self.client_address[0], body.get("k"))
                if not ok:
                    return self._json({"ok": False, "error": err, "bad_code": True}, 401)
                return self._json(self._queue(body.get("text") or "", body.get("analyze")))
            return self._reply(404, "text/plain; charset=utf-8", "not found")

        def do_PUT(self):
            self._reply(405, "text/plain", b"")

        do_DELETE = do_PATCH = do_PUT

        def do_OPTIONS(self):
            self._reply(405, "text/plain", b"")

    return PhoneHandler


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ════════════════ 手机上看到的页面 ════════════════

PAGE = r"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="发给小助">
<meta name="theme-color" content="#f6f3ee">
<title>发给超能小助</title>
<style>
:root{--bg:#f6f3ee;--card:#fff;--text:#2b2621;--dim:#8a8178;--line:#e6dfd5;--accent:#c96442;--ok:#2f8a4c;--bad:#c0392b}
@media (prefers-color-scheme:dark){:root{--bg:#1d1b19;--card:#292623;--text:#eee8e1;--dim:#a39a90;--line:#3a3632;--accent:#e07a55;--ok:#5cc07c;--bad:#ef6b5b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
 padding:calc(14px + env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom))}
h1{font-size:20px;margin:6px 2px 4px}
.sub{color:var(--dim);font-size:13.5px;margin:0 2px 14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px}
textarea,input{width:100%;font:inherit;color:var(--text);background:transparent;border:1px solid var(--line);border-radius:12px;padding:12px}
textarea{min-height:120px;resize:vertical}
textarea:focus,input:focus{outline:2px solid var(--accent);border-color:transparent}
.row{display:flex;align-items:center;gap:10px;margin-top:12px}
.sw{display:flex;align-items:center;gap:8px;font-size:15px;flex:1}
.sw input{width:22px;height:22px;accent-color:var(--accent)}
button{font:inherit;font-weight:600;border:0;border-radius:12px;padding:13px 18px;background:var(--accent);color:#fff;min-width:120px}
button:disabled{opacity:.55}
.ghost{background:transparent;color:var(--dim);border:1px solid var(--line);min-width:0;padding:8px 12px;font-weight:500;font-size:14px}
#msg{margin:12px 2px 0;font-size:15px;min-height:1.5em}
#msg.ok{color:var(--ok)} #msg.bad{color:var(--bad)}
h2{font-size:15px;color:var(--dim);margin:22px 2px 8px;font-weight:600}
.item{padding:10px 2px;border-bottom:1px solid var(--line);font-size:14px}
.item:last-child{border-bottom:0}
.item .t{color:var(--dim);font-size:12.5px}
.item .u{word-break:break-all;color:var(--dim);font-size:12.5px}
.item .m.ok{color:var(--ok)} .item .m.bad{color:var(--bad)}
.tip{color:var(--dim);font-size:13px;margin:18px 2px 0;line-height:1.7}
#codeBox{display:none}
</style></head><body>
<h1>📱 发给超能小助</h1>
<p class="sub">把文章或视频的链接（整段分享文案也行）粘进来，电脑会自动提取保存。</p>

<div class="card" id="codeBox">
  <div style="margin-bottom:10px">输入电脑上「手机发链接」面板里的 6 位连接码：</div>
  <input id="code" inputmode="numeric" maxlength="6" placeholder="6 位数字" autocomplete="off">
  <div class="row"><button id="codeOk" style="flex:1">确定</button></div>
</div>

<div class="card" id="sendBox">
  <textarea id="text" placeholder="长按这里 →「粘贴」&#10;例如：公众号文章链接、知乎 / 头条 / 小红书 / 抖音的分享文案"></textarea>
  <div class="row">
    <label class="sw"><input type="checkbox" id="an"> 顺便让 AI 分析</label>
    <button id="go">发给电脑</button>
  </div>
  <div id="msg"></div>
</div>

<h2>最近发过的</h2>
<div class="card" id="list"><div class="item t">还没有</div></div>

<p class="tip">💡 小技巧：在浏览器菜单里选「添加到主屏幕」，以后点桌面图标就能直接打开这一页。<br>
手机要和电脑连<b>同一个 Wi-Fi</b>；电脑要开着超能小助。</p>

<script>
(function(){
  var qs = new URLSearchParams(location.search);
  var K = qs.get("k") || "";
  try { if (K) localStorage.setItem("cx_k", K); else K = localStorage.getItem("cx_k") || ""; } catch(e){}
  if (qs.get("k")) { try { history.replaceState(null, "", location.pathname); } catch(e){} }
  var $ = function(id){ return document.getElementById(id); };
  var anTouched = false;
  try { var s = localStorage.getItem("cx_an"); if (s !== null) { $("an").checked = s === "1"; anTouched = true; } } catch(e){}
  $("an").addEventListener("change", function(){ anTouched = true; try { localStorage.setItem("cx_an", $("an").checked ? "1" : "0"); } catch(e){} });

  function esc(s){ return String(s||"").replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  function needCode(on){ $("codeBox").style.display = on ? "block" : "none"; $("sendBox").style.display = on ? "none" : "block"; if (on) $("code").focus(); }
  function say(t, cls){ var m = $("msg"); m.textContent = t; m.className = cls || ""; }

  function render(list){
    if (!list || !list.length) { $("list").innerHTML = '<div class="item t">还没有</div>'; return; }
    $("list").innerHTML = list.map(function(x){
      return '<div class="item"><div class="t">' + esc(x.t) + (x.analyze ? " · 带 AI 分析" : "") + '</div>' +
        (x.title ? '<div>' + esc(x.title) + '</div>' : '') +
        '<div class="u">' + esc(x.url) + '</div>' +
        '<div class="m ' + (x.ok ? "ok" : "bad") + '">' + (x.ok ? "✓ " : "✗ ") + esc(x.msg) + '</div></div>';
    }).join("");
  }
  function refresh(){
    if (!K) { needCode(true); return; }
    fetch("/m/recent?k=" + encodeURIComponent(K), {cache:"no-store"}).then(function(r){ return r.json(); }).then(function(d){
      if (d.bad_code) { needCode(true); return; }
      needCode(false);
      if (!anTouched) $("an").checked = !!d.analyze_default;
      render(d.recent);
    }).catch(function(){ say("连不上电脑：确认电脑开着超能小助、手机和电脑在同一个 Wi-Fi", "bad"); });
  }
  $("codeOk").onclick = function(){
    K = ($("code").value || "").trim();
    try { localStorage.setItem("cx_k", K); } catch(e){}
    refresh();
  };
  $("go").onclick = function(){
    var text = $("text").value.trim();
    if (!text) { say("先把链接粘进上面的框里", "bad"); return; }
    $("go").disabled = true; say("正在发送…");
    fetch("/m/send", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({k:K, text:text, analyze:$("an").checked})})
    .then(function(r){ return r.json(); }).then(function(d){
      if (d.bad_code) { say(d.error, "bad"); needCode(true); return; }
      if (d.ok) { say("✓ " + d.msg, "ok"); $("text").value = ""; }
      else say("✗ " + (d.error || "没成功"), "bad");
      refresh();
    }).catch(function(){ say("连不上电脑：确认电脑开着超能小助、手机和电脑在同一个 Wi-Fi", "bad"); })
    .then(function(){ $("go").disabled = false; });
  };
  refresh();
  setInterval(refresh, 15000);
})();
</script>
</body></html>
"""
