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

def _console_hwnd():
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        return int(ctypes.windll.kernel32.GetConsoleWindow() or 0)
    except Exception:
        return 0


def console_window(action):
    """action: minimize | show | status。返回 (是否做到, 说明)。"""
    hwnd = _console_hwnd()
    if not hwnd:
        return False, "没有找到启动时的黑窗口（可能不是用 start.bat 启动的）"
    if action == "status":
        return True, "找到了黑窗口"
    try:
        import ctypes
        user32 = ctypes.windll.user32
        if action == "minimize":
            user32.ShowWindow(hwnd, 6)            # SW_MINIMIZE
            return True, "已把黑窗口最小化（在任务栏里还能点开）"
        if action == "show":
            user32.ShowWindow(hwnd, 9)            # SW_RESTORE
            try:
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            return True, "已显示黑窗口"
    except Exception as e:
        return False, "操作黑窗口失败：%s" % e
    return False, "不认识的操作：%s" % action
