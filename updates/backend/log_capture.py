"""超能小助 · 终端日志收集（v55 新增）

作用：
  1. 把后端打印到黑窗口（终端）里的每一行，同时存一份在内存里（最近 6000 行），
     软件里的「终端」面板 / 独立终端窗口通过 /logs 接口读，不用再盯着黑窗口；
     原来的黑窗口照常输出，什么都不少。
  2. 控制启动时的黑窗口：最小化 / 重新显示（只在 Windows 上有效，做不到就什么都不做）。
"""
from __future__ import annotations

import collections
import sys
import threading
import time

_MAX_LINES = 6000
_lines = collections.deque(maxlen=_MAX_LINES)   # (序号, 时间戳, 文字)
_seq = 0
_lock = threading.Lock()
_partial = {}          # 每个线程还没凑够一整行的半截文字
_installed = False


def _add_line(text):
    global _seq
    with _lock:
        _seq += 1
        _lines.append((_seq, time.time(), text))


def _feed(chunk):
    """把一段输出拆成整行存起来。处理 \\r（进度条原地刷新）：只留最后一次的内容。"""
    if not chunk:
        return
    tid = threading.get_ident()
    buf = _partial.get(tid, "") + chunk
    parts = buf.split("\n")
    for ln in parts[:-1]:
        if "\r" in ln:
            ln = ln.rstrip("\r").split("\r")[-1]
        _add_line(ln)
    rest = parts[-1]
    if "\r" in rest:
        rest = rest.split("\r")[-1]
    if len(rest) > 4000:           # 一直不换行的超长输出，先存一截，别无限攒着
        _add_line(rest)
        rest = ""
    if rest:
        _partial[tid] = rest
    else:
        _partial.pop(tid, None)


class _Tee:
    """套在 sys.stdout / sys.stderr 外面：照常写进原来的黑窗口，同时抄一份。"""

    def __init__(self, orig):
        self._orig = orig

    def write(self, s):
        try:
            if isinstance(s, bytes):
                s = s.decode("utf-8", "replace")
            _feed(s)
        except Exception:
            pass
        if self._orig is not None:
            return self._orig.write(s)
        return len(s or "")

    def writelines(self, lines):
        for ln in lines:
            self.write(ln)

    def flush(self):
        if self._orig is not None:
            try:
                self._orig.flush()
            except Exception:
                pass

    def isatty(self):
        try:
            return bool(self._orig and self._orig.isatty())
        except Exception:
            return False

    def __getattr__(self, name):           # reconfigure / encoding / fileno / buffer … 都交给原来的
        if self._orig is None:
            raise AttributeError(name)
        return getattr(self._orig, name)


def install():
    """在后端启动时调用一次。重复调用无害。"""
    global _installed
    if _installed:
        return
    _installed = True
    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout)
    if not isinstance(sys.stderr, _Tee):
        sys.stderr = _Tee(sys.stderr)


def get_lines(since=0, limit=2000):
    """返回序号大于 since 的行（最多 limit 行，取最新的）。"""
    with _lock:
        if since <= 0:
            rows = list(_lines)[-limit:]
        else:
            rows = [r for r in _lines if r[0] > since][-limit:]
        last = _seq
        first = _lines[0][0] if _lines else 0
    return {
        "lines": [{"n": n, "t": round(t, 3), "s": s} for (n, t, s) in rows],
        "last": last,
        "first": first,
        # 前端拿到的 since 比我们最老的还旧 → 中间有行被挤掉了
        "gap": bool(since and first and since < first - 1),
    }


# ════════════════════ 启动时的黑窗口（只在 Windows 上） ════════════════════
# v56：v55 只对 GetConsoleWindow() 拿到的窗口操作。用户用的是 Windows Terminal（带标签页的那种），
# 这时拿到的是一个看不见的「替身窗口」，对它最小化没反应。现在改成找到真正显示出来的那个窗口：
#   ① 替身窗口的「主人」（Windows Terminal 会把自己设成替身窗口的 owner）；
#   ② 把这个标签页的标题改成一个独一无二的名字，再按标题找窗口；
#   ③ 老式控制台（conhost）就是 GetConsoleWindow() 本身。
# 后端如果没挂在黑窗口上，就顺着父进程（powershell / cmd）临时挂过去找。
CONSOLE_TITLE = "超能小助 · 后台日志（软件左下角「终端」里也能看）"


def _win_api():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    H = wintypes.HWND
    kernel32.GetConsoleWindow.restype = H
    user32.GetWindow.restype = H
    user32.GetWindow.argtypes = [H, ctypes.c_uint]
    user32.GetAncestor.restype = H
    user32.GetAncestor.argtypes = [H, ctypes.c_uint]
    user32.FindWindowW.restype = H
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.IsWindowVisible.argtypes = [H]
    user32.IsIconic.argtypes = [H]
    user32.ShowWindow.argtypes = [H, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [H]
    user32.GetClassNameW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
    kernel32.SetConsoleTitleW.argtypes = [wintypes.LPCWSTR]
    kernel32.AttachConsole.argtypes = [wintypes.DWORD]
    return ctypes, user32, kernel32


def _class_name(ctypes, user32, h):
    buf = ctypes.create_unicode_buffer(256)
    try:
        user32.GetClassNameW(h, buf, 256)
    except Exception:
        return ""
    return buf.value


def _attach_parent_console(kernel32):
    """后端自己没挂在黑窗口上时：顺着父进程找 powershell / cmd，临时挂到它的黑窗口上。"""
    try:
        import psutil
        p = psutil.Process()
        for _ in range(8):
            p = p.parent()
            if p is None:
                return False
            if (p.name() or "").lower() in ("powershell.exe", "pwsh.exe", "cmd.exe"):
                return bool(kernel32.AttachConsole(p.pid))
    except Exception:
        return False
    return False


def _find_console_windows():
    """返回 (要操作的窗口列表, 说明)。"""
    import time as _t
    ctypes, user32, kernel32 = _win_api()
    hwnd = kernel32.GetConsoleWindow()
    attached = False
    if not hwnd and _attach_parent_console(kernel32):
        attached = True
        hwnd = kernel32.GetConsoleWindow()
    if not hwnd:
        return [], "没有找到启动时的黑窗口（可能不是用 start.bat 启动的）", None
    cands = []

    def add(h):
        if h and h not in cands and user32.IsWindowVisible(h):
            cands.append(h)

    add(user32.GetWindow(hwnd, 4))          # GW_OWNER：Windows Terminal 的真窗口
    add(user32.GetAncestor(hwnd, 3))        # GA_ROOTOWNER
    try:
        kernel32.SetConsoleTitleW(CONSOLE_TITLE)
        for _ in range(12):                 # Windows Terminal 改标题有一点点延迟
            h = user32.FindWindowW(None, CONSOLE_TITLE)
            if h:
                if h != hwnd:
                    add(h)
                break
            _t.sleep(0.1)
    except Exception:
        pass
    kind = "Windows Terminal" if any(
        "CASCADIA" in _class_name(ctypes, user32, h).upper() for h in cands) else "控制台"
    if not cands:
        cands = [hwnd]                      # 老式控制台：它本身就是真窗口
    return cands, kind, (kernel32 if attached else None)


def console_window(action):
    """action: minimize | show | status。返回 (是否做到, 说明)。"""
    if sys.platform != "win32":
        return False, "不是 Windows，没有黑窗口可控制"
    try:
        cands, kind, detach = _find_console_windows()
    except Exception as e:
        return False, "找黑窗口出错：%s" % e
    if not cands:
        return False, kind
    try:
        _ctypes, user32, _k = _win_api()
        if action == "status":
            return True, "找到了黑窗口（%s）" % kind
        if action == "minimize":
            for h in cands:
                user32.ShowWindow(h, 6)            # SW_MINIMIZE
            return True, "已把黑窗口最小化（%s，在任务栏里还能点开）" % kind
        if action == "show":
            for h in cands:
                user32.ShowWindow(h, 9)            # SW_RESTORE
                try:
                    user32.SetForegroundWindow(h)
                except Exception:
                    pass
            return True, "已显示黑窗口（%s）" % kind
        return False, "不认识的操作：%s" % action
    except Exception as e:
        return False, "操作黑窗口失败：%s" % e
    finally:
        if detach is not None:
            try:
                detach.FreeConsole()
            except Exception:
                pass
