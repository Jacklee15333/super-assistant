"""超能小助 · 真实市场 · 交易平台专用的浏览器（v198 新增，v199 大改）

京东、淘宝、拼多多、1688 搜东西要登录。这里开一个专门给爬虫用的 Chrome（单独的资料夹，和你自己的 Chrome、AI 池都分开）：
  · 你点「登录」→ 这个 Chrome 出现在屏幕上、打开登录页 → 你扫码登录 → 软件发现登录好了，把窗口挪到屏幕外；
  · 之后爬虫就用这个已经登录的浏览器打开搜索页（窗口在屏幕外，照常工作）。
v199 改了这些（v198 登录两分钟就「过期」，原因是下面前两条）：
  · 用 Patchright（防检测版 Playwright）开浏览器：普通 Playwright 有几处能被网站认出「这是程序」，登录后照样被踢；
    没装会自动在后台装，装好之前先用普通的。
  · 登录信息另存一份：浏览器闲置关掉再打开时，淘宝 / 1688 的「会话 Cookie」会丢，等于退出登录；现在关之前存下来，开的时候放回去。
    存的文件用 Windows 自带的加密（只有你这台电脑、你这个账户能解开），而且放在本机 %LOCALAPPDATA%\\ChaoNengXiaoZhu，
    不在软件的 memory 文件夹里——以前的资料夹在 memory 里，会跟着你的提交传到 GitHub。
  · 网页自己去调的接口数据（商品列表 JSON）顺手收下来，交给取数的代码；比在网页文字里认价格准得多，也不用破解签名。
  · 像人一样慢慢搜：同一个平台两次搜索至少隔 15～28 秒，每个平台一天最多搜 100 次，免得账号被风控。
  · 平台弹滑块 / 验证码时不硬闯：标成「要过一下验证」，你点一下，窗口弹出来，自己拖一下就好。
v200：「一键登录全部」——没登录的平台一次全打开（一个窗口里几个标签页），登好一个自动关掉、跳到下一个；
      点「登录」前先清掉这个平台的旧登录信息（不然过期的旧 Cookie 还在，软件会误以为马上就登录好了）。
v201：加闲鱼、Shopee（东南亚）、Upwork（全球接单）三个要登录的平台；国外平台在这个 Chrome 里也能打开——
      国内网站直连，其余的走软件设置里的代理（用一个代理规则文件 PAC 分流，代理连不上时自动直连）。
v202：任何平台（不只要登录的）在爬虫 Chrome 里弹滑块 / 验证码，都记下来，表里那一行出「去验证」；
      付费解锁服务的钥匙也加密存在这里（secrets.bin），不进 memory、不会传到 GitHub。
所有页面操作都在一个专门的线程里做（Playwright 只能在一个线程里用）；闲置 5 分钟自动关掉浏览器，省内存。
"""
from __future__ import annotations

import json
import os
import queue
import random
import re
import shutil
import threading
import time
from pathlib import Path

import biz_intel as BZ


def _home():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    p = Path(base) / "ChaoNengXiaoZhu" / "trade_browser"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


HOME = _home()
PROFILE = HOME / "profile"
COOKIE_FILE = HOME / "cookies.bin"
SECRET_FILE = HOME / "secrets.bin"
OLD_PROFILE = BZ.BIZ_DIR / "real" / "browser_profile"      # v198 放在 memory 里（会被提交到 GitHub），v199 搬走
STATE_FILE = BZ.BIZ_DIR / "real" / "login_state.json"
OFFSCREEN = -12000
IDLE_CLOSE = 300
LOGIN_WAIT = 600            # 登录 / 验证窗口最多等 10 分钟
DAILY_CAP = 100             # 每个要登录的平台一天最多搜这么多次
GAP_LOGIN = (15, 28)        # 同一个要登录的平台，两次搜索至少隔这么多秒
GAP_OTHER = (4, 9)

SITES = {
    "jd": {"name": "京东", "login": "https://passport.jd.com/new/login.aspx?ReturnUrl=https%3A%2F%2Fwww.jd.com%2F", "home": "https://www.jd.com/",
           "domain": "jd.com", "domains": ("jd.com",), "cookies": ("thor", "pt_key", "pinId", "unick", "pin")},
    "tb": {"name": "淘宝 / 天猫", "login": "https://login.taobao.com/member/login.jhtml?redirectURL=https%3A%2F%2Fwww.taobao.com%2F",
           "home": "https://www.taobao.com/", "domain": "taobao.com", "domains": ("taobao.com", "tmall.com"), "cookies": ("unb", "_nk_", "cookie17", "lgc")},
    "pdd": {"name": "拼多多", "login": "https://mobile.yangkeduo.com/login.html", "home": "https://mobile.yangkeduo.com/",
            "domain": "yangkeduo.com", "domains": ("yangkeduo.com", "pinduoduo.com"), "cookies": ("PDDAccessToken", "pdd_user_id")},
    "b2b": {"name": "1688", "login": "https://login.1688.com/member/signin.htm?Done=https%3A%2F%2Fwww.1688.com%2F", "home": "https://www.1688.com/",
            "domain": "1688.com", "domains": ("1688.com",), "cookies": ("__cn_logon__", "unb", "cookie17", "__cn_logon_id__")},
    "xy": {"name": "闲鱼", "login": "https://www.goofish.com/", "home": "https://www.goofish.com/", "hint": "打开后点页面右上角的「登录」",
           "domain": "goofish.com", "domains": ("goofish.com",), "cookies": ("unb",)},
    "shopee": {"name": "Shopee", "login": "https://shopee.sg/buyer/login", "home": "https://shopee.sg/", "foreign": True,
               "domain": "shopee.sg", "domains": ("shopee.sg",), "cookies": ("SPC_U",)},
    "upwork": {"name": "Upwork", "login": "https://www.upwork.com/ab/account-security/login", "home": "https://www.upwork.com/", "foreign": True,
               "domain": "upwork.com", "domains": ("upwork.com",), "cookies": ("master_access_token", "oauth2_global_js_token", "user_uid")},
}
ORDER = ["jd", "tb", "pdd", "b2b", "xy", "shopee", "upwork"]
KEEP = ("jd.com", "taobao.com", "tmall.com", "1688.com", "yangkeduo.com", "pinduoduo.com", "alibaba.com", "goofish.com", "shopee.sg", "upwork.com")
# 国内网站：爬虫 Chrome 里直连；其余走代理（PAC 分流）
CN_DIRECT = ("jd.com", "360buyimg.com", "jdpay.com", "jd.hk", "3.cn", "taobao.com", "tmall.com", "alicdn.com", "alibaba.com", "1688.com",
             "mmstat.com", "tbcdn.cn", "alipay.com", "alipayobjects.com", "aliyun.com", "aliyuncs.com", "taobao.net", "tanx.com",
             "alibabausercontent.com", "yangkeduo.com", "pinduoduo.com", "pddpic.com", "pddugc.com", "goofish.com", "xianyu.com", "yiwugo.com",
             "suning.com", "smzdm.com", "zbj.com", "zbjimg.com", "baidu.com", "bdstatic.com", "qq.com", "gtimg.com", "weibo.com",
             "dianping.com", "meituan.com", "xiaohongshu.com", "xhscdn.com", "douyin.com", "bytedance.com", "amap.com")
LOGIN_URL = re.compile(r"(passport\.jd\.com|login\.taobao\.com|login\.tmall\.com|login\.1688\.com|yangkeduo\.com/login|passport\.alibaba|"
                       r"passport\.goofish|shopee\.sg/buyer/login|upwork\.com/ab/account-security/login)", re.I)
CAPTCHA = re.compile(r"(滑动验证|拖动下方滑块|请拖动|安全验证|访问过于频繁|频繁访问|人机验证|请完成验证|验证一下|captcha|punish|x5sec|baxia-dialog|"
                     r"Robot Check|Robot or human|Pardon Our Interruption|unusual traffic|verify you are a human|Access Denied)", re.I)

_q = queue.Queue()
_st = {"thread": None, "pw": None, "ctx": None, "eng": "", "last": 0, "login": {}, "visible": False, "err": "", "saved": 0,
       "last_at": {}, "old_done": False, "tried_install": 0, "batch": None, "px": None}
_lock = threading.Lock()
_pace_lock = threading.Lock()


def _read():
    v = BZ._read_json(STATE_FILE, {})
    return v if isinstance(v, dict) else {}


def _write(d):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BZ._write_json(STATE_FILE, d)


def _log(msg):
    try:
        BZ._log("爬虫浏览器：" + msg)
    except Exception:
        pass


# ───────────────────────── Windows 自带加密（DPAPI）：只有这台电脑、这个账户能解开 ─────────────────────────
def _dpapi(data, enc):
    import ctypes
    import ctypes.wintypes as wt

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    inp = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if enc else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI 失败")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _protect(b):
    return (b"DPAPI" + _dpapi(b, True)) if os.name == "nt" else (b"PLAIN" + b)


def _unprotect(b):
    if b[:5] == b"DPAPI":
        return _dpapi(b[5:], False)
    if b[:5] == b"PLAIN" and os.name != "nt":
        return b[5:]
    raise ValueError("认不出的登录信息文件")


def get_secret(name):
    try:
        return json.loads(_unprotect(SECRET_FILE.read_bytes()).decode("utf-8")).get(name)
    except Exception:
        return None


def set_secret(name, value):
    try:
        d = json.loads(_unprotect(SECRET_FILE.read_bytes()).decode("utf-8"))
    except Exception:
        d = {}
    if value:
        d[name] = value
    else:
        d.pop(name, None)
    SECRET_FILE.write_bytes(_protect(json.dumps(d).encode("utf-8")))


def _nm(site):
    return SITES[site]["name"] if site in SITES else ((_read().get(site) or {}).get("name") or site)


def _save_cookies(force=False):
    ctx = _st["ctx"]
    if not ctx or (not force and time.time() - _st["saved"] < 60):
        return
    try:
        cs = [c for c in ctx.cookies() if any((c.get("domain") or "").lstrip(".").endswith(d) for d in KEEP)]
        if cs:
            COOKIE_FILE.write_bytes(_protect(json.dumps(cs).encode("utf-8")))
            _st["saved"] = time.time()
    except Exception as e:
        _log("登录信息没存上：%s" % str(e)[:80])


def _restore_cookies(ctx):
    try:
        cs = json.loads(_unprotect(COOKIE_FILE.read_bytes()).decode("utf-8"))
    except Exception:
        return 0
    try:
        have = {(c.get("name"), c.get("domain"), c.get("path")) for c in ctx.cookies()}
    except Exception:
        have = set()
    now, add = time.time(), []
    for c in cs:
        if (c.get("name"), c.get("domain"), c.get("path")) in have:
            continue
        e = c.get("expires")
        if e not in (None, -1) and e < now:
            continue
        x = {k: c[k] for k in ("name", "value", "domain", "path", "httpOnly", "secure") if k in c}
        if e not in (None, -1):
            x["expires"] = e
        if c.get("sameSite") in ("Strict", "Lax", "None"):
            x["sameSite"] = c["sameSite"]
        add.append(x)
    if add:
        try:
            ctx.add_cookies(add)
        except Exception:
            ok = 0
            for x in add:
                try:
                    ctx.add_cookies([x])
                    ok += 1
                except Exception:
                    pass
            return ok
    return len(add)


# ───────────────────────── 浏览器驱动：优先 Patchright（防检测版）─────────────────────────
def _install_patchright_bg():
    if time.time() - _st["tried_install"] < 6 * 3600:
        return
    _st["tried_install"] = time.time()

    def run():
        import subprocess
        import sys
        _log("在后台装防检测版浏览器驱动 Patchright（只装一次，装好前先用普通的 Playwright）…")
        for extra in ([], ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]):
            try:
                cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "patchright"] + extra
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                if r.returncode != 0 and "externally-managed" in ((r.stderr or "") + (r.stdout or "")):
                    r = subprocess.run(cmd + ["--break-system-packages"], capture_output=True, text=True, timeout=900)
                if r.returncode == 0:
                    _log("Patchright 装好了：下次打开爬虫浏览器时用它")
                    return
            except Exception:
                pass
        _log("Patchright 没装上（网络问题？），先用普通的 Playwright")
    threading.Thread(target=run, daemon=True, name="patchright-install").start()


def _engine():
    import importlib
    importlib.invalidate_caches()
    try:
        from patchright.sync_api import sync_playwright
        return sync_playwright, "Patchright"
    except Exception:
        _install_patchright_bg()
    from playwright.sync_api import sync_playwright
    return sync_playwright, "Playwright"


def engine_name():
    if _st["eng"]:
        return _st["eng"]
    try:
        import importlib.util
        return "Patchright" if importlib.util.find_spec("patchright") else "Playwright"
    except Exception:
        return "Playwright"


def _cleanup_old_profile():
    if _st["old_done"]:
        return
    _st["old_done"] = True
    try:
        if OLD_PROFILE.exists():
            shutil.rmtree(OLD_PROFILE, ignore_errors=True)
            _log("删掉了 v198 放在 memory 里的旧浏览器资料夹（会被提交到 GitHub）；现在放在本机 %s" % HOME)
    except Exception:
        pass


# ───────────────────────── 专门的线程 ─────────────────────────
def _loop():
    while True:
        try:
            job = _q.get(timeout=3)
        except queue.Empty:
            job = None
        if job:
            fn, args, ev, box = job
            try:
                box["r"] = fn(*args)
            except Exception as e:
                box["e"] = e
            ev.set()
            _st["last"] = time.time()
        try:
            _tick()
        except Exception as e:
            _st["err"] = str(e)[:120]


def _run(fn, *args, timeout=300):
    with _lock:
        if not (_st["thread"] and _st["thread"].is_alive()):
            _st["thread"] = threading.Thread(target=_loop, daemon=True, name="trade-browser")
            _st["thread"].start()
    ev, box = threading.Event(), {}
    _q.put((fn, args, ev, box))
    if not ev.wait(timeout):
        raise RuntimeError("爬虫浏览器没反应（超时）")
    if "e" in box:
        raise box["e"]
    return box.get("r")


def _proxy():
    """软件设置里的代理（国外网站用）；没配就是空。"""
    try:
        import web_tools as W
        return W.proxy_for("https://www.upwork.com/") or ""
    except Exception:
        return ""


def pac_url(px):
    """PAC 代理规则：本机、国内网站直连；其余走代理，代理连不上就直连。写成 data: 网址直接交给 Chrome。"""
    import base64
    m = re.match(r"^(\w+)://(?:[^@/]*@)?([^/]+)", px or "")
    if not m:
        return ""
    tok = ("SOCKS5 %s; SOCKS %s" % (m.group(2), m.group(2))) if m.group(1).lower().startswith("socks") else "PROXY %s" % m.group(2)
    js = ('function FindProxyForURL(url, host) {'
          ' if (isPlainHostName(host) || host == "localhost" || /^(127\\.|10\\.|192\\.168\\.|172\\.(1[6-9]|2\\d|3[01])\\.)/.test(host)) return "DIRECT";'
          ' if (/\\.cn$/.test(host)) return "DIRECT";'
          ' var cn = %s;'
          ' for (var i = 0; i < cn.length; i++) { var d = cn[i]; if (host == d || host.slice(-d.length - 1) == "." + d) return "DIRECT"; }'
          ' return "%s; DIRECT"; }') % (json.dumps(list(CN_DIRECT)), tok)
    return "data:application/x-ns-proxy-autoconfig;base64," + base64.b64encode(js.encode("utf-8")).decode("ascii")


def _ctx():
    if _st["ctx"]:
        try:
            _st["ctx"].pages          # 还活着
            if _st["px"] == _proxy() or _st["login"]:
                return _st["ctx"]
            _log("代理设置变了，重开一下爬虫浏览器")
            _save_cookies(force=True)
            _st["ctx"].close()
            _st["ctx"] = None
        except Exception:
            _st["ctx"] = None
    _cleanup_old_profile()
    sp, eng = _engine()
    if not _st["pw"] or _st["eng"] != eng:
        try:
            if _st["pw"]:
                _st["pw"].stop()
        except Exception:
            pass
        _st["pw"], _st["eng"] = sp().start(), eng
    PROFILE.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}
    px = _proxy()
    pac = pac_url(px)
    args = ["--window-position=%d,0" % OFFSCREEN, ("--proxy-pac-url=" + pac) if pac else "--no-proxy-server", "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding", "--disable-features=CalculateNativeWinOcclusion"]
    patched = eng == "Patchright"
    if not patched:
        args.append("--disable-blink-features=AutomationControlled")
    last = None
    for ch in ("chrome", "msedge", None):
        try:
            kw = dict(headless=False, args=args, env=env, no_viewport=True)       # Patchright 建议：真 Chrome、有界面、不改 UA / 请求头
            if not patched:
                kw["ignore_default_args"] = ["--enable-automation"]
            if ch:
                kw["channel"] = ch
            _st["ctx"] = _st["pw"].chromium.launch_persistent_context(str(PROFILE), **kw)
            _st["visible"], _st["px"] = False, px
            n = _restore_cookies(_st["ctx"])
            _log("打开了（%s · %s%s）" % (eng, ch or "自带 Chromium", "，放回了 %d 条登录信息" % n if n else ""))
            return _st["ctx"]
        except Exception as e:
            last = e
    raise RuntimeError("打不开浏览器：%s" % str(last)[:120])


def _show(page, on):
    try:
        cdp = page.context.new_cdp_session(page)
        wid = cdp.send("Browser.getWindowForTarget")["windowId"]
        cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "normal"}})
        b = {"left": 120, "top": 60, "width": 1180, "height": 860} if on else {"left": OFFSCREEN, "top": 0}
        cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": b})
        if on:
            page.bring_to_front()
        _st["visible"] = on
    except Exception as e:
        _log("窗口挪不动：%s" % str(e)[:80])


def _logged(site):
    s = SITES[site]
    try:
        cs = _ctx().cookies()
    except Exception:
        return False
    for c in cs:
        if s["domain"] in (c.get("domain") or "") and c.get("name") in s["cookies"] and c.get("value") and c.get("value") not in ("false", "-", "0"):
            return True
    return False


def block_of(html, url):
    """这一页是不是被要求登录 / 弹了验证。"""
    if LOGIN_URL.search(str(url or "")):
        return "login"
    if CAPTCHA.search((html or "")[:200000]) and len(re.sub(r"<[^>]+>", "", html or "")) < 20000:
        return "captcha"
    return ""


def _tick():
    """登录 / 验证窗口开着时：隔几秒看一眼好了没有；好了就收起窗口。闲置太久关浏览器。"""
    now = time.time()
    for site, L in list(_st["login"].items()):
        if now - L.get("checked", 0) < 3:
            continue
        L["checked"] = now
        if L.get("mode") == "verify":
            try:
                pg = L["page"]
                done = not block_of(pg.content(), pg.url)
            except Exception:
                done = False
            if done and now - L["started"] > 4:
                _done_login(site, True)
            elif now - L["started"] > L.get("wait", LOGIN_WAIT):
                _done_login(site, False)
        elif _logged(site):
            _done_login(site, True)
        elif now - L["started"] > L.get("wait", LOGIN_WAIT):
            _done_login(site, False)
    if _st["ctx"] and not _st["login"] and now - _st["last"] > IDLE_CLOSE:
        _save_cookies(force=True)
        try:
            _st["ctx"].close()
        except Exception:
            pass
        _st["ctx"] = None
        _log("闲着，先关掉（登录信息存好了，要用时再开）")


def _done_login(site, ok):
    L = _st["login"].pop(site, {})
    d = _read()
    s = d.setdefault(site, {})
    now = int(time.time())
    if L.get("mode") == "verify":
        s.update(verify=False, checked=now) if ok else s.update(checked=now)
        _log("%s 验证%s" % (_nm(site), "过了" if ok else "窗口等太久，先收起来了"))
    elif ok:
        s.update(logged=True, at=now, checked=now, expired=False, verify=False)
        _log("%s 登录好了" % SITES[site]["name"])
    else:
        s.update(checked=now)
        _log("%s 登录窗口等太久，先收起来了" % SITES[site]["name"])
    _write(d)
    if ok:
        _save_cookies(force=True)
    pg = L.get("page")
    try:
        if pg and not _st["login"]:
            _show(pg, False)
        if pg:
            pg.close()
    except Exception:
        pass
    _next_tab()


def _next_tab():
    """一键登录：登好一个，跳到下一个还没登录的标签页（二维码放久了会失效，顺手刷新一下）。"""
    left = [x for x in ORDER if x in _st["login"]]
    if not left:
        _st["batch"] = None
        return
    L = _st["login"][left[0]]
    try:
        pg = L["page"]
        if L.get("batch") and time.time() - L.get("shown", L["started"]) > 60:
            pg.reload(wait_until="domcontentloaded", timeout=30000)
        L["shown"] = time.time()
        _show(pg, True)
    except Exception as e:
        _log("切到下一个登录页没成功：%s" % str(e)[:80])


# ───────────────────────── 对外 ─────────────────────────
def _clear_site(site):
    """只清这一个平台的登录信息（别的平台不动）。"""
    ctx = _ctx()
    doms = SITES[site].get("domains") or (SITES[site]["domain"],)
    try:
        ctx.clear_cookies(domain=re.compile(r"(^|\.)(%s)$" % "|".join(re.escape(d) for d in doms)))
        return
    except Exception:
        pass
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    cdp = ctx.new_cdp_session(pg)
    for c in ctx.cookies():
        if any((c.get("domain") or "").lstrip(".").endswith(d) for d in doms):
            try:
                cdp.send("Network.deleteCookies", {"name": c["name"], "domain": c["domain"], "path": c.get("path") or "/"})
            except Exception:
                pass


def _open_login(site, mode="login"):
    ctx = _ctx()
    if mode == "login":
        _clear_site(site)              # 旧的（多半过期了）先清掉，免得一打开就被当成「登录好了」
    pg = ctx.new_page()
    if mode == "verify":
        url = (_read().get(site) or {}).get("verify_url") or SITES.get(site, {}).get("home") or "about:blank"
    else:
        url = SITES[site]["login"]
    pg.goto(url, wait_until="domcontentloaded", timeout=40000)
    _show(pg, True)
    _st["login"][site] = {"started": time.time(), "page": pg, "checked": 0, "mode": mode, "shown": time.time()}
    return True


def _open_all(force):
    """一键登录：没登录的平台（force＝全部）各开一个标签页，先把第一个放到前面。"""
    d = _read()
    todo = [x for x in ORDER if x not in _st["login"] and (force or not (d.get(x) or {}).get("logged"))]
    if not todo:
        return []
    ctx = _ctx()
    opened, now = [], time.time()
    for i, site in enumerate(todo):
        try:
            _clear_site(site)
            pg = ctx.new_page()
            pg.goto(SITES[site]["login"], wait_until="domcontentloaded", timeout=40000)
            _st["login"][site] = {"started": now, "page": pg, "checked": 0, "mode": "login", "batch": True,
                                  "wait": LOGIN_WAIT + 300 * i, "shown": now}
            opened.append(site)
        except Exception as e:
            _log("%s 的登录页没打开：%s" % (SITES[site]["name"], str(e)[:80]))
    if opened:
        _st["batch"] = {"sites": opened, "started": int(now)}
        first = _st["login"][opened[0]]["page"]
        _show(first, True)
        _log("一键登录：开了 %s 的登录页" % "、".join(SITES[x]["name"] for x in opened))
    return opened


def open_login_all(force=False):
    try:
        opened = _run(_open_all, bool(force), timeout=240)
    except Exception as e:
        return {"ok": False, "error": "登录窗口没打开：%s" % str(e)[:150]}
    if not opened:
        return {"ok": True, "n": 0, "msg": "都已经登录了"}
    return {"ok": True, "n": len(opened), "sites": opened, "names": [SITES[x]["name"] for x in opened]}


def open_login(site, mode="login"):
    if site not in SITES and not (mode == "verify" and (_read().get(site) or {}).get("verify_url")):
        return {"ok": False, "error": "不认识的网站"}
    try:
        _run(_open_login, site, mode, timeout=60)
    except Exception as e:
        return {"ok": False, "error": "窗口没打开：%s" % str(e)[:150]}
    return {"ok": True}


def open_verify(site):
    return open_login(site, "verify")


def _logout(site):
    _clear_site(site)
    _save_cookies(force=True)
    return True


def logout(site):
    try:
        _run(_logout, site, timeout=60)
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}
    d = _read()
    d[site] = {"logged": False, "checked": int(time.time())}
    _write(d)
    return {"ok": True}


def logged_in(site):
    return bool((_read().get(site) or {}).get("logged"))


def mark_expired(site):
    d = _read()
    s = d.setdefault(site, {})
    if s.get("logged"):
        s.update(logged=False, expired=True, checked=int(time.time()))
        _write(d)
        _log("%s 的登录过期了" % SITES[site]["name"])


def need_verify(site, url, name=None):
    d = _read()
    s = d.setdefault(site, {})
    s.update(verify=True, verify_url=url, verify_at=int(time.time()))
    if name and site not in SITES:
        s["name"] = name
    _write(d)
    _log("%s 弹了验证，等你点「去验证」" % _nm(site))


def _count(site):
    d = _read()
    s = d.setdefault(site, {})
    today = time.strftime("%Y-%m-%d")
    if s.get("day") != today:
        s["day"], s["n_today"] = today, 0
    if s.get("n_today", 0) >= DAILY_CAP:
        raise RuntimeError("今天在%s上已经搜了 %d 次，先停一停（搜太多账号容易被风控），明天接着抓" % (SITES[site]["name"], DAILY_CAP))
    s["n_today"] = s.get("n_today", 0) + 1
    _write(d)


def _pace(key, login):
    gap = random.uniform(*(GAP_LOGIN if login else GAP_OTHER))
    with _pace_lock:
        last = _st["last_at"].get(key, 0)
        wait = last + gap - time.time()
        _st["last_at"][key] = max(time.time(), last + gap)
    if wait > 0:
        time.sleep(wait)


def _fetch2(url, wait_ms, scrolls):
    ctx = _ctx()
    pg = ctx.new_page()
    caps = []

    def on_resp(resp):
        try:
            if len(caps) >= 40:
                return
            rt = resp.request.resource_type
            if rt not in ("xhr", "fetch", "script"):
                return
            ct = ((resp.headers or {}).get("content-type") or "").lower()
            if rt == "script" and not re.search(r"(callback|jsonp|mtop|/api|search)", resp.url, re.I):
                return
            if "json" in ct or "javascript" in ct or "text/plain" in ct:
                caps.append(resp)
        except Exception:
            pass
    pg.on("response", on_resp)
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(wait_ms)
        for _ in range(scrolls):                  # 往下滚几下，让懒加载的商品出来
            pg.mouse.wheel(0, random.randint(1500, 2600))
            pg.wait_for_timeout(random.randint(600, 1100))
        try:
            pg.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        html, final = pg.content(), pg.url
        blobs, total = [], 0
        for resp in caps:
            try:
                b = resp.body()
            except Exception:
                continue
            if not b or len(b) > 4_000_000:
                continue
            import biz_trade_x as X
            o = X.loads_loose(b.decode("utf-8", "replace"))
            if o is None:
                continue
            s = json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
            if total + len(s) > 8_000_000:
                break
            total += len(s)
            blobs.append(s)
        extra = "".join('<script type="application/json" data-cap="1">%s</script>' % s for s in blobs)
        return {"html": html + extra, "url": final, "json_n": len(blobs), "block": block_of(html, final)}
    finally:
        try:
            pg.close()
        except Exception:
            pass


def fetch_ex(url, site=None, login=False, wait_ms=2500, scrolls=3, vkey=None, vname=None):
    """用爬虫专用 Chrome 打开一页。login=True 时 site 是要登录的平台（算次数、慢慢搜、过期 / 验证会记下来）。
    v202：vkey＝哪个平台在抓（不用登录的也算）：弹验证就记下来，界面那一行出「去验证」。"""
    if login and site in SITES:
        _count(site)
    key = site or re.sub(r"^https?://([^/]+).*$", r"\1", url)
    _pace(key, bool(login))
    r = _run(_fetch2, url, wait_ms, scrolls, timeout=300)
    if login and site in SITES:
        if r["block"] == "login":
            mark_expired(site)
        elif r["block"] == "captcha":
            need_verify(site, url)
        else:
            d = _read()
            if (d.get(site) or {}).get("verify"):
                d[site]["verify"] = False
                _write(d)
            try:
                _run(_save_cookies, timeout=60)
            except Exception:
                pass
    elif vkey:
        if r["block"] == "captcha":
            need_verify(vkey, url, vname)
        elif not r["block"]:
            d = _read()
            if (d.get(vkey) or {}).get("verify"):
                d[vkey]["verify"] = False
                _write(d)
    return r


def fetch(url, wait_ms=2500):
    r = fetch_ex(url, wait_ms=wait_ms)
    return r["html"], r["url"]


def status():
    d = _read()
    today = time.strftime("%Y-%m-%d")
    out = {}
    for site in ORDER:
        s = SITES[site]
        x = dict(d.get(site) or {})
        x.pop("verify_url", None)
        x["name"] = s["name"]
        x["waiting"] = site in _st["login"]
        if x["waiting"]:
            x["since"] = int(_st["login"][site]["started"])
            x["mode"] = _st["login"][site].get("mode", "login")
        x["today"] = x.get("n_today", 0) if x.get("day") == today else 0
        x["cap"] = DAILY_CAP
        x["foreign"] = bool(s.get("foreign"))
        x["hint"] = s.get("hint", "")
        out[site] = x
    verify = {}                                            # v202：不用登录的平台弹了验证
    for k, v in d.items():
        if k in SITES or not isinstance(v, dict):
            continue
        if v.get("verify") or k in _st["login"]:
            verify[k] = {"name": v.get("name") or k, "waiting": k in _st["login"], "verify": bool(v.get("verify"))}
    b = _st["batch"]
    batch = None
    if b:
        left = [x for x in b["sites"] if x in _st["login"]]
        batch = {"n": len(b["sites"]), "left": left, "left_names": [SITES[x]["name"] for x in left],
                 "cur": SITES[left[0]]["name"] if left else "", "done": len(b["sites"]) - len(left)}
    return {"sites": out, "order": ORDER, "open": bool(_st["ctx"]), "err": _st["err"], "engine": engine_name(), "home": str(HOME),
            "batch": batch, "proxy": bool(_proxy()), "verify": verify}
