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
           "domain": "jd.com", "cookies": ("thor", "pt_key", "pinId", "unick", "pin")},
    "tb": {"name": "淘宝 / 天猫", "login": "https://login.taobao.com/member/login.jhtml?redirectURL=https%3A%2F%2Fwww.taobao.com%2F",
           "home": "https://www.taobao.com/", "domain": "taobao.com", "cookies": ("unb", "_nk_", "cookie17", "lgc")},
    "pdd": {"name": "拼多多", "login": "https://mobile.yangkeduo.com/login.html", "home": "https://mobile.yangkeduo.com/",
            "domain": "yangkeduo.com", "cookies": ("PDDAccessToken", "pdd_user_id")},
    "b2b": {"name": "1688", "login": "https://login.1688.com/member/signin.htm?Done=https%3A%2F%2Fwww.1688.com%2F", "home": "https://www.1688.com/",
            "domain": "1688.com", "cookies": ("__cn_logon__", "unb", "cookie17", "__cn_logon_id__")},
}
ORDER = ["jd", "tb", "pdd", "b2b"]
KEEP = ("jd.com", "taobao.com", "tmall.com", "1688.com", "yangkeduo.com", "pinduoduo.com", "alibaba.com")
LOGIN_URL = re.compile(r"(passport\.jd\.com|login\.taobao\.com|login\.tmall\.com|login\.1688\.com|yangkeduo\.com/login|passport\.alibaba)", re.I)
CAPTCHA = re.compile(r"(滑动验证|拖动下方滑块|请拖动|安全验证|访问过于频繁|频繁访问|人机验证|请完成验证|验证一下|captcha|punish|x5sec|baxia-dialog|"
                     r"Robot Check|Robot or human|Pardon Our Interruption|unusual traffic|verify you are a human|Access Denied)", re.I)

_q = queue.Queue()
_st = {"thread": None, "pw": None, "ctx": None, "eng": "", "last": 0, "login": {}, "visible": False, "err": "", "saved": 0,
       "last_at": {}, "old_done": False, "tried_install": 0}
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


def _ctx():
    if _st["ctx"]:
        try:
            _st["ctx"].pages          # 还活着
            return _st["ctx"]
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
    args = ["--window-position=%d,0" % OFFSCREEN, "--no-proxy-server", "--disable-background-timer-throttling",
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
            _st["visible"] = False
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
        if s["domain"] in (c.get("domain") or "") and c.get("name") in s["cookies"] and c.get("value") and c.get("value") != "false":
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
            elif now - L["started"] > LOGIN_WAIT:
                _done_login(site, False)
        elif _logged(site):
            _done_login(site, True)
        elif now - L["started"] > LOGIN_WAIT:
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
        _log("%s 验证%s" % (SITES[site]["name"], "过了" if ok else "窗口等太久，先收起来了"))
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


# ───────────────────────── 对外 ─────────────────────────
def _open_login(site, mode="login"):
    ctx = _ctx()
    pg = ctx.new_page()
    url = SITES[site]["login"]
    if mode == "verify":
        url = (_read().get(site) or {}).get("verify_url") or SITES[site]["home"]
    pg.goto(url, wait_until="domcontentloaded", timeout=40000)
    _show(pg, True)
    _st["login"][site] = {"started": time.time(), "page": pg, "checked": 0, "mode": mode}
    return True


def open_login(site, mode="login"):
    if site not in SITES:
        return {"ok": False, "error": "不认识的网站"}
    try:
        _run(_open_login, site, mode, timeout=60)
    except Exception as e:
        return {"ok": False, "error": "窗口没打开：%s" % str(e)[:150]}
    return {"ok": True}


def open_verify(site):
    return open_login(site, "verify")


def _logout(site):
    ctx = _ctx()
    try:
        ctx.clear_cookies(domain=SITES[site]["domain"])
    except TypeError:                       # 老版本 Playwright 不能按网站清：全清
        ctx.clear_cookies()
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


def need_verify(site, url):
    d = _read()
    s = d.setdefault(site, {})
    s.update(verify=True, verify_url=url, verify_at=int(time.time()))
    _write(d)
    _log("%s 弹了验证，等你点「去验证」" % SITES[site]["name"])


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


def fetch_ex(url, site=None, login=False, wait_ms=2500, scrolls=3):
    """用爬虫专用 Chrome 打开一页。login=True 时 site 是要登录的平台（算次数、慢慢搜、过期 / 验证会记下来）。"""
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
        out[site] = x
    return {"sites": out, "order": ORDER, "open": bool(_st["ctx"]), "err": _st["err"], "engine": engine_name(), "home": str(HOME)}
