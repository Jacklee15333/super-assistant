"""超能小助 · 真实市场 · 交易平台登录用的浏览器（v198 新增）

京东、1688 现在搜东西要登录才给看。这里开一个专门给爬虫用的 Chrome（单独的资料夹，和你自己的 Chrome、AI 池都分开）：
  · 你点「登录」→ 这个 Chrome 出现在屏幕上、打开登录页 → 你扫码或输密码登录 → 软件发现登录好了，把窗口挪到屏幕外；
  · 之后爬虫抓京东 / 1688 时就用这个已经登录的浏览器打开搜索页（窗口在屏幕外，照常工作）；
  · 登录信息存在 memory/biz/real/browser_profile 里，关了软件也在；过期了界面上会提示重新登录。
所有页面操作都在一个专门的线程里做（Playwright 只能在一个线程里用）；闲置 5 分钟自动关掉浏览器，省内存。
"""
from __future__ import annotations

import queue
import threading
import time

import biz_intel as BZ

PROFILE = BZ.BIZ_DIR / "real" / "browser_profile"
STATE_FILE = BZ.BIZ_DIR / "real" / "login_state.json"
OFFSCREEN = -12000
IDLE_CLOSE = 300
LOGIN_WAIT = 600            # 登录窗口最多等 10 分钟

SITES = {
    "jd": {"name": "京东", "login": "https://passport.jd.com/new/login.aspx?ReturnUrl=https%3A%2F%2Fwww.jd.com%2F",
           "domain": "jd.com", "cookies": ("thor", "pt_key", "pinId", "unick")},
    "b2b": {"name": "1688", "login": "https://login.1688.com/member/signin.htm?Done=https%3A%2F%2Fwww.1688.com%2F",
            "domain": "1688.com", "cookies": ("__cn_logon__", "unb", "cookie17", "__cn_logon_id__")},
}

_q = queue.Queue()
_st = {"thread": None, "pw": None, "ctx": None, "last": 0, "login": {}, "visible": False, "err": ""}
_lock = threading.Lock()


def _read():
    v = BZ._read_json(STATE_FILE, {})
    return v if isinstance(v, dict) else {}


def _write(d):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BZ._write_json(STATE_FILE, d)


def _log(msg):
    try:
        BZ._log("登录浏览器：" + msg)
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


def _run(fn, *args, timeout=90):
    with _lock:
        if not (_st["thread"] and _st["thread"].is_alive()):
            _st["thread"] = threading.Thread(target=_loop, daemon=True, name="trade-browser")
            _st["thread"].start()
    ev, box = threading.Event(), {}
    _q.put((fn, args, ev, box))
    if not ev.wait(timeout):
        raise RuntimeError("登录浏览器没反应（超时）")
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
    from playwright.sync_api import sync_playwright
    if not _st["pw"]:
        _st["pw"] = sync_playwright().start()
    PROFILE.mkdir(parents=True, exist_ok=True)
    import os
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}
    args = ["--window-position=%d,0" % OFFSCREEN, "--disable-blink-features=AutomationControlled", "--no-proxy-server",
            "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion"]
    last = None
    for ch in ("chrome", "msedge", None):
        try:
            kw = dict(headless=False, args=args, env=env, viewport=None, locale="zh-CN")
            if ch:
                kw["channel"] = ch
            _st["ctx"] = _st["pw"].chromium.launch_persistent_context(str(PROFILE), **kw)
            _st["visible"] = False
            _log("打开了（%s）" % (ch or "自带 Chromium"))
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


def _tick():
    """登录窗口开着时：隔几秒看一眼登录好了没有；好了就收起窗口。闲置太久关浏览器。"""
    now = time.time()
    for site, L in list(_st["login"].items()):
        if now - L.get("checked", 0) < 3:
            continue
        L["checked"] = now
        if _logged(site):
            _done_login(site, True)
        elif now - L["started"] > LOGIN_WAIT:
            _done_login(site, False)
    if _st["ctx"] and not _st["login"] and now - _st["last"] > IDLE_CLOSE:
        try:
            _st["ctx"].close()
        except Exception:
            pass
        _st["ctx"] = None
        _log("闲着，先关掉（要用时再开）")


def _done_login(site, ok):
    L = _st["login"].pop(site, {})
    d = _read()
    s = d.setdefault(site, {})
    if ok:
        s.update(logged=True, at=int(time.time()), checked=int(time.time()), expired=False)
        _log("%s 登录好了" % SITES[site]["name"])
    else:
        s.update(checked=int(time.time()))
        _log("%s 登录窗口等太久，先收起来了" % SITES[site]["name"])
    _write(d)
    pg = L.get("page")
    try:
        if pg and not _st["login"]:
            _show(pg, False)
        if pg:
            pg.close()
    except Exception:
        pass


# ───────────────────────── 对外 ─────────────────────────
def _open_login(site):
    ctx = _ctx()
    pg = ctx.new_page()
    pg.goto(SITES[site]["login"], wait_until="domcontentloaded", timeout=40000)
    _show(pg, True)
    _st["login"][site] = {"started": time.time(), "page": pg, "checked": 0}
    return True


def open_login(site):
    if site not in SITES:
        return {"ok": False, "error": "不认识的网站"}
    try:
        _run(_open_login, site, timeout=60)
    except Exception as e:
        return {"ok": False, "error": "登录窗口没打开：%s" % str(e)[:150]}
    return {"ok": True}


def _logout(site):
    ctx = _ctx()
    try:
        ctx.clear_cookies(domain=SITES[site]["domain"])
    except TypeError:                       # 老版本 Playwright 不能按网站清：全清
        ctx.clear_cookies()
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


def _fetch(url, wait_ms):
    ctx = _ctx()
    pg = ctx.new_page()
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(wait_ms)
        for _ in range(3):                  # 往下滚几下，让懒加载的商品出来
            pg.mouse.wheel(0, 2200)
            pg.wait_for_timeout(700)
        return pg.content(), pg.url
    finally:
        try:
            pg.close()
        except Exception:
            pass


def fetch(url, wait_ms=2500):
    return _run(_fetch, url, wait_ms, timeout=120)


def status():
    d = _read()
    out = {}
    for site, s in SITES.items():
        x = dict(d.get(site) or {})
        x["name"] = s["name"]
        x["waiting"] = site in _st["login"]
        if x["waiting"]:
            x["since"] = int(_st["login"][site]["started"])
        out[site] = x
    return {"sites": out, "open": bool(_st["ctx"]), "err": _st["err"]}
