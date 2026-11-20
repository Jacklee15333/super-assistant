"""
scrapling_fetch.py — 嗅探的「网页抓取增强」（v108）

基于开源项目 Scrapling（https://github.com/D4Vinci/Scrapling，BSD-3 许可）：
  · 快速模式：模拟真 Chrome 的网络指纹 + 真实浏览器请求头，过一般的反爬拦截；
  · 浏览器模式：用电脑上的 Chrome 真正打开网页（隐身、不弹窗口），等动态内容加载完，
    遇到 Cloudflare 验证页会自动过——适合「普通方式只抓到空壳」或「被拦截（403）」的网站。

怎么装：第一次启动后台时，自动在「独立环境」里安装（约 200MB，只需一次）：
  Windows：%LOCALAPPDATA%\\ChaonengXiaozhu\\scrapling-env
  不装进软件自己的 Python：Scrapling 依赖较新的 playwright 等，混装可能弄坏「AI 池」。
怎么用：每抓一个网页，就用独立环境里的 python 跑一次 scrapling_worker.py（单独进程），
  超时会连同它打开的浏览器一起结束，卡不住后台。

对外接口：
  available()        能不能用（装好且自检通过）
  status()           给界面看的状态
  prepare_async()    后台启动时调用：没装就在后台装
  start_install()    界面「重试安装」
  fetch(url, mode, proxy, timeout)  返回 HTML；失败抛 RuntimeError（带原因）
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

PIN = "scrapling[fetchers]==0.5.1"
WORKER = Path(__file__).with_name("scrapling_worker.py")
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _env_dir():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ChaonengXiaozhu" / "scrapling-env"
    return Path.home() / ".cache" / "chaoneng" / "scrapling-env"


ENV_DIR = Path(os.environ.get("CX_SCRAPLING_ENV") or _env_dir())
STATE_PATH = ENV_DIR.parent / "scrapling_install_state.json"


def _env_python():
    return ENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


_lock = threading.Lock()
_check_lock = threading.Lock()
_state = {"ready": None, "installing": False, "msg": "", "error": "", "version": "", "checked_at": 0.0}
_browser_sem = threading.Semaphore(2)    # 同时最多开 2 个浏览器，省内存
_fast_sem = threading.Semaphore(6)

_MIRRORS = [
    ("清华镜像", ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "--trusted-host", "pypi.tuna.tsinghua.edu.cn"]),
    ("阿里镜像", ["-i", "https://mirrors.aliyun.com/pypi/simple/", "--trusted-host", "mirrors.aliyun.com"]),
    ("默认源", []),
]


def _log(m):
    try:
        print("[scrapling] " + m, flush=True)
    except Exception:
        pass


def _set(**kw):
    with _lock:
        _state.update(kw)


def _kill_tree(p):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True,
                           timeout=15, creationflags=_NO_WINDOW)
        else:
            import signal
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def _run(cmd, timeout, input_text=None):
    """跑一个命令，返回 (退出码, 标准输出, 标准错误)。超时会连同子进程（比如浏览器）一起结束，再抛 TimeoutExpired。"""
    kw = dict(stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.name == "nt":
        kw["creationflags"] = _NO_WINDOW
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(cmd, **kw)
    try:
        out, err = p.communicate(input=input_text.encode("utf-8") if input_text is not None else None,
                                 timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(p)
        try:
            p.communicate(timeout=5)
        except Exception:
            pass
        raise
    return p.returncode, (out or b"").decode("utf-8", "replace"), (err or b"").decode("utf-8", "replace")


def _last_json(out):
    for line in reversed((out or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    return None


def _selftest():
    py = _env_python()
    if not py.exists():
        return False, "", "还没安装"
    try:
        rc, out, err = _run([str(py), str(WORKER), "--selftest"], timeout=120)
    except subprocess.TimeoutExpired:
        return False, "", "自检超时"
    except Exception as e:
        return False, "", str(e)[:300]
    d = _last_json(out)
    if d and d.get("ok"):
        return True, d.get("version", ""), ""
    return False, "", ((d or {}).get("error") or err or out or "自检没通过")[-300:]


def _check(force=False):
    with _check_lock:
        with _lock:
            fresh = _state["ready"] is not None and (
                _state["ready"] or time.time() - _state["checked_at"] < 600)
            if not force and fresh:
                return bool(_state["ready"])
        ok, ver, err = _selftest()
        with _lock:
            _state.update(ready=ok, version=ver, checked_at=time.time())
            if ok:
                _state.update(error="", msg="已就绪")
        return ok


def available():
    """装好且自检通过才算能用；正在安装时返回 False（嗅探照常用原来的方式）。"""
    with _lock:
        if _state["installing"]:
            return False
    return _check()


def status():
    with _lock:
        st = dict(_state)
    return {
        "ready": bool(st["ready"]),
        "installing": bool(st["installing"]),
        "msg": st["msg"],
        "error": st["error"],
        "version": st["version"],
        "python_ok": sys.version_info >= (3, 10),
        "env_dir": str(ENV_DIR),
    }


def _load_install_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_install_state(d):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _install():
    """在独立环境里装 Scrapling。会阻塞，几分钟。"""
    if sys.version_info < (3, 10):
        raise RuntimeError("Scrapling 需要 Python 3.10 以上，你电脑上的是 %d.%d" % sys.version_info[:2])
    if not _env_python().exists():
        _set(msg="正在创建独立的 Python 环境…")
        _log("正在创建独立的 Python 环境：%s" % ENV_DIR)
        ENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        rc, out, err = _run([sys.executable, "-m", "venv", str(ENV_DIR)], timeout=600)
        if rc != 0 or not _env_python().exists():
            raise RuntimeError("创建独立环境失败：" + (err or out).strip()[-300:])
    py = str(_env_python())
    last = ""
    for label, extra in _MIRRORS:
        msg = "正在通过%s安装 Scrapling（约 200MB，只需一次）…" % label
        _set(msg=msg)
        _log(msg)
        try:
            rc, out, err = _run([py, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                                 "--prefer-binary", PIN] + extra, timeout=1800)
        except subprocess.TimeoutExpired:
            last = "下载超时"
            _log("%s 下载超时，换下一个源" % label)
            continue
        if rc == 0:
            break
        last = (err or out).strip()[-400:]
        _log("%s 没装上，换下一个源：%s" % (label, (last.splitlines() or [""])[-1][:160]))
    else:
        raise RuntimeError("三个下载源都没装上，检查一下网络。最后的报错：" + (last.splitlines() or [""])[-1][:160])
    ok, ver, e = _selftest()
    if not ok:
        raise RuntimeError("装好了但自检没通过：" + e)
    return ver


def _install_job():
    try:
        ver = _install()
        _set(ready=True, version=ver, checked_at=time.time(), error="", msg="已就绪")
        _save_install_state({"ok": True, "at": time.time(), "version": ver})
        _log("✓ 抓取增强装好了（Scrapling %s）。嗅探遇到打不开或动态加载的网站，会自动换真浏览器抓。" % ver)
    except Exception as e:
        _set(ready=False, checked_at=time.time(), error=str(e)[:300], msg="")
        _save_install_state({"ok": False, "at": time.time(), "error": str(e)[:300]})
        _log("抓取增强没装上：%s（嗅探照常用原来的方式；可以在「趋势瞭望台」里点重试）" % e)
    finally:
        _set(installing=False)


def start_install():
    """界面点「安装 / 重试」。立即返回。"""
    with _lock:
        if _state["installing"]:
            return {"ok": False, "message": "正在安装中，稍等"}
        _state.update(installing=True, error="", msg="准备安装…")
    threading.Thread(target=_install_job, name="scrapling-install", daemon=True).start()
    return {"ok": True}


def prepare_async(delay=20):
    """后台启动时调用：等一会儿（别和启动抢资源），检查装好没有；没装就在后台装。
    上次自动安装失败不到 6 小时就不再自动试（免得每次启动都下载），可以在界面里手动重试。
    设置环境变量 CX_NO_SCRAPLING=1 可以完全关掉。"""
    if os.environ.get("CX_NO_SCRAPLING") == "1":
        _set(ready=False, error="已按设置关闭（CX_NO_SCRAPLING=1）", checked_at=time.time())
        return

    def _job():
        time.sleep(delay)
        if _check(force=True):
            _log("抓取增强已就绪（Scrapling %s）" % _state.get("version", ""))
            return
        last = _load_install_state()
        if last and not last.get("ok") and time.time() - float(last.get("at", 0)) < 6 * 3600:
            _set(error=last.get("error", "上次没装上"))
            _log("上次没装上，这次先不自动重试：%s" % last.get("error", ""))
            return
        if start_install().get("ok"):
            _log("第一次使用：在后台安装网页抓取增强（Scrapling），装好前嗅探照常用原来的方式")

    threading.Thread(target=_job, name="scrapling-prepare", daemon=True).start()


def fetch(url, mode="fast", proxy=None, timeout=None):
    """用 Scrapling 抓一个网页，返回 HTML。mode: fast（快速）/ browser（真浏览器）。失败抛 RuntimeError。"""
    if not available():
        raise RuntimeError("网页抓取增强（Scrapling）还没装好")
    timeout = float(timeout or (45 if mode == "browser" else 25))
    req = json.dumps({"url": url, "mode": mode, "proxy": proxy or "", "timeout": timeout}, ensure_ascii=False)
    sem = _browser_sem if mode == "browser" else _fast_sem
    with sem:
        try:
            rc, out, err = _run([str(_env_python()), str(WORKER)], timeout=timeout + 45, input_text=req)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Scrapling %s超时（timeout）" % ("浏览器打开" if mode == "browser" else "抓取"))
    d = _last_json(out)
    if not d:
        raise RuntimeError("Scrapling 没返回结果：" + (err or out or "").strip()[-200:])
    if not d.get("ok"):
        raise RuntimeError(d.get("error") or "Scrapling 抓取失败")
    return d.get("html") or ""
