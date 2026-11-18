"""超能小助 · 语音识别 GPU 加速（v54 新增）

作用：让 faster-whisper 优先用 NVIDIA 显卡做「语音转文字」，比 CPU 快很多。

流程：
  1. 看电脑有没有 NVIDIA 显卡（nvidia-smi / ctranslate2 能不能看到 CUDA 设备）；
  2. faster-whisper 底层的 CTranslate2 在 Windows 上不自带 CUDA 运行库，
     需要 cuBLAS + cuDNN。没有的话，自动 pip 安装 nvidia-cublas / nvidia-cudnn
     （先走清华、阿里镜像，失败再走默认源），只装一次；
  3. 把这些运行库所在的文件夹加进 DLL 搜索路径；
  4. 用 GPU 加载模型后，先跑一小段静音做「自检」——真正调用到 cuBLAS/cuDNN
     才算数，避免「模型加载成功、一转写就报找不到 DLL」；
  5. 任何一步不行都自动退回 CPU，原因记下来，在设置页和日志里能看到。

环境变量：
  CX_WHISPER_DEVICE=cpu   强制用 CPU（不想用显卡时）
  CX_WHISPER_DEVICE=cuda  只用 GPU（不做自动安装以外的回退判断，仍会在失败时退回 CPU）
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

# ── 状态（给设置页 / 日志看） ──
_state = {
    "checked": False,        # 是否检测过
    "has_nvidia": False,     # 是否有 NVIDIA 显卡
    "gpu_name": "",          # 显卡型号
    "gpu_mem_gb": 0,         # 显存（GB）
    "libs_ok": None,         # CUDA 运行库是否就绪（None=还没确认）
    "installing": False,     # 正在安装运行库
    "install_msg": "",       # 安装过程/结果说明
    "gpu_works": None,       # GPU 自检是否通过（None=还没试过）
    "device": "",            # 当前语音模型实际用的设备：cuda / cpu
    "compute_type": "",      # 实际用的精度
    "reason": "",            # 没用上 GPU 的原因（给用户看）
}
_lock = threading.RLock()
_install_done = threading.Event()
_dll_handles = []            # os.add_dll_directory 返回的句柄要留着，否则会失效
_dll_dirs_added = set()

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # 不弹黑窗口


def _log(msg):
    try:
        print("[gpu] " + msg, flush=True)
    except Exception:
        pass


# ════════════════════ 1. 检测显卡 ════════════════════

def _nvidia_smi_name():
    """用 nvidia-smi 读显卡型号。没有 NVIDIA 驱动时返回 ""。"""
    exe = shutil.which("nvidia-smi")
    if not exe and sys.platform == "win32":
        for c in (r"C:\Windows\System32\nvidia-smi.exe",
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
            if os.path.exists(c):
                exe = c
                break
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=15,
                           creationflags=_NO_WINDOW)
        line = (r.stdout or "").strip().splitlines()
        if r.returncode != 0 or not line:
            return ""
        # 输出形如 "NVIDIA GeForce RTX 5060 Ti, 16311 MiB"：名字和显存分开存
        parts = [x.strip() for x in line[0].split(",")]
        if len(parts) >= 2 and "MiB" in parts[-1]:
            try:
                _state["gpu_mem_gb"] = round(int(parts[-1].split()[0]) / 1024, 1)
            except Exception:
                pass
            return ", ".join(parts[:-1])
        return line[0].strip()
    except Exception:
        return ""


def _ct2_cuda_count():
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def detect():
    """检测一次显卡。返回 has_nvidia。"""
    with _lock:
        if _state["checked"]:
            return _state["has_nvidia"]
        name = _nvidia_smi_name()
        cnt = _ct2_cuda_count()
        _state["has_nvidia"] = bool(name) or cnt > 0
        _state["gpu_name"] = name or ("NVIDIA 显卡" if cnt > 0 else "")
        _state["checked"] = True
        if _state["has_nvidia"]:
            _log("检测到显卡：%s" % _state["gpu_name"])
        else:
            _state["reason"] = "没有检测到 NVIDIA 显卡（或显卡驱动没装好）"
            _log("没有检测到 NVIDIA 显卡，语音识别用 CPU")
        return _state["has_nvidia"]


# ════════════════════ 2. CUDA 运行库：找路径 / 自动安装 ════════════════════

def _site_dirs():
    dirs = []
    try:
        import site
        dirs += list(site.getsitepackages() or [])
        u = site.getusersitepackages()
        if u:
            dirs.append(u)
    except Exception:
        pass
    dirs.append(str(Path(sys.prefix) / "Lib" / "site-packages"))
    for p in sys.path:
        if p and p.endswith("site-packages"):
            dirs.append(p)
    out, seen = [], set()
    for d in dirs:
        k = os.path.normcase(os.path.abspath(d))
        if k not in seen and os.path.isdir(d):
            seen.add(k)
            out.append(d)
    return out


def _nvidia_lib_dirs():
    """pip 装的 nvidia-* 包把 DLL 放在 site-packages/nvidia/<库>/bin（Windows）或 lib（Linux）。"""
    roots = []
    for sp in _site_dirs():
        roots.append(Path(sp) / "nvidia")
    try:
        import nvidia  # 命名空间包
        roots += [Path(p) for p in getattr(nvidia, "__path__", [])]
    except Exception:
        pass
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for sub in root.iterdir():
            for leaf in ("bin", "lib"):
                d = sub / leaf
                if d.is_dir():
                    found.append(str(d))
    out, seen = [], set()
    for d in found:
        k = os.path.normcase(d)
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


def add_dll_dirs():
    """把 CUDA 运行库目录加进 DLL 搜索路径（PATH + add_dll_directory）。可重复调用。"""
    dirs = _nvidia_lib_dirs()
    for d in dirs:
        k = os.path.normcase(d)
        if k in _dll_dirs_added:
            continue
        _dll_dirs_added.add(k)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                _dll_handles.append(os.add_dll_directory(d))
            except Exception:
                pass
    return dirs


def _ct2_version():
    try:
        import ctranslate2
        v = getattr(ctranslate2, "__version__", "0")
        m = re.match(r"(\d+)\.(\d+)", v)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    except Exception:
        return (0, 0)


def _needed_packages():
    """按 CTranslate2 的版本决定要哪一版 CUDA 运行库：
       ≥4.5 → CUDA 12 + cuDNN 9；4.0~4.4 → CUDA 12 + cuDNN 8；3.x → CUDA 11 + cuDNN 8。
    版本钉死在「有 Windows 安装包、用的人多、稳定」的版本上：
      · 最新的 nvidia-cublas-cu12 12.9.3 没有 Windows 包；
      · 最新的 cuDNN 刚发布不久，不拿用户的电脑去试。
    cuBLAS 12.x 之间、cuDNN 9.x 之间都是兼容的，所以钉在这些版本没问题。"""
    major, minor = _ct2_version()
    cublas12 = "nvidia-cublas-cu12==12.8.4.1"
    if major >= 5 or (major == 4 and minor >= 5):
        return [cublas12, "nvidia-cudnn-cu12==9.10.2.21"]
    if major == 4:
        return [cublas12, "nvidia-cudnn-cu12==8.9.7.29"]
    if major == 3:
        return ["nvidia-cublas-cu11", "nvidia-cudnn-cu11>=8,<9"]
    return [cublas12, "nvidia-cudnn-cu12==9.10.2.21"]


def _libs_present():
    """看 cuBLAS / cuDNN 的 DLL 是否已经在某个 nvidia 包目录里。"""
    names = []
    for d in _nvidia_lib_dirs():
        try:
            names += [n.lower() for n in os.listdir(d)]
        except Exception:
            pass
    major, minor = _ct2_version()
    if major == 3:
        cub, cud = ("cublas64_11", "libcublas.so.11"), ("cudnn64_8", "libcudnn.so.8")
    elif major == 4 and minor < 5:
        cub, cud = ("cublas64_12", "libcublas.so.12"), ("cudnn64_8", "libcudnn.so.8")
    else:
        cub, cud = ("cublas64_12", "libcublas.so.12"), ("cudnn64_9", "libcudnn.so.9")
    has_cublas = any(n.startswith(cub) for n in names)
    has_cudnn = any(n.startswith(cud) for n in names)
    return has_cublas and has_cudnn


_MIRRORS = [
    ("清华镜像", ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                 "--trusted-host", "pypi.tuna.tsinghua.edu.cn"]),
    ("阿里镜像", ["-i", "https://mirrors.aliyun.com/pypi/simple/",
                 "--trusted-host", "mirrors.aliyun.com"]),
    ("默认源", []),
]


def _pip_install(pkgs):
    base = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-input", "--prefer-binary"] + pkgs
    last = ""
    for label, extra in _MIRRORS:
        with _lock:
            _state["install_msg"] = "正在通过%s下载 GPU 运行库（约 1GB，只需一次）…" % label
        _log(_state["install_msg"])
        try:
            r = subprocess.run(base + extra, capture_output=True, text=True,
                               timeout=1800, creationflags=_NO_WINDOW)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0 and "externally-managed" in out:
                r = subprocess.run(base + extra + ["--break-system-packages"],
                                   capture_output=True, text=True, timeout=1800,
                                   creationflags=_NO_WINDOW)
                out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                return True, label
            last = out[-600:]
            _log("%s 安装失败，换下一个源。%s" % (label, last.strip().splitlines()[-1:] or ""))
        except Exception as e:
            last = str(e)
            _log("%s 安装出错：%s" % (label, e))
    return False, last


def ensure_libs():
    """确保 CUDA 运行库可用（缺了就自动装）。返回 True/False。会阻塞直到装完。"""
    if not detect():
        return False
    with _lock:
        if _state["libs_ok"] is not None and not _state["installing"]:
            return _state["libs_ok"]
        if _state["installing"]:
            wait = True
        else:
            wait = False
            _state["installing"] = True
            _install_done.clear()
    if wait:
        _install_done.wait(timeout=1900)
        return bool(_state["libs_ok"])
    try:
        if _libs_present():
            add_dll_dirs()
            ok = True
            msg = "GPU 运行库已就绪"
        else:
            ok, how = _pip_install(_needed_packages())
            if ok:
                add_dll_dirs()
                ok = _libs_present()
                msg = ("GPU 运行库安装完成（%s）" % how) if ok else "GPU 运行库安装后没找到 DLL"
            else:
                msg = "GPU 运行库下载失败（可能是网络问题），本次先用 CPU；下次启动会再试"
        with _lock:
            _state["libs_ok"] = ok
            _state["install_msg"] = msg
            if not ok:
                _state["reason"] = msg
        _log(msg)
        return ok
    finally:
        with _lock:
            _state["installing"] = False
        _install_done.set()


def prepare_async():
    """后端启动时调用：后台检测显卡 + 准备运行库，不阻塞启动。"""
    if os.environ.get("CX_WHISPER_DEVICE", "").lower() == "cpu":
        with _lock:
            _state["checked"] = True
            _state["reason"] = "已用环境变量 CX_WHISPER_DEVICE=cpu 强制使用 CPU"
        return

    def _run():
        try:
            if detect():
                ensure_libs()
        except Exception as e:
            _log("后台准备 GPU 出错：%s" % e)
    threading.Thread(target=_run, name="gpu-prepare", daemon=True).start()


# ════════════════════ 3. 加载模型（GPU 优先 + 自检 + 退回 CPU） ════════════════════

def _cuda_compute_types():
    """按显卡能力挑精度：优先 float16（最快），老显卡退 int8_float16 / int8 / float32。"""
    try:
        import ctranslate2
        sup = set(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        sup = set()
    order = ["float16", "int8_float16", "int8", "float32"]
    picked = [c for c in order if c in sup]
    return picked or ["float16", "float32"]


def _self_test(model):
    """跑 1 秒的微弱噪声，关掉 VAD，确保真正走一遍编码+解码（会加载 cuBLAS/cuDNN）。"""
    import numpy as np
    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(16000) * 0.01).astype("float32")
    segs, _info = model.transcribe(audio, language="zh", vad_filter=False,
                                   beam_size=1, without_timestamps=True,
                                   condition_on_previous_text=False)
    for _ in segs:
        pass


def is_gpu_error(e):
    """判断一个异常是不是显卡/CUDA 相关（用于转写中途出错时自动换 CPU 重来）。"""
    s = ("%s %s" % (type(e).__name__, e)).lower()
    keys = ("cuda", "cublas", "cudnn", "cufft", "gpu", "out of memory",
            "dll", "libcublas", "libcudnn", "device")
    return any(k in s for k in keys)


def mark_gpu_broken(reason):
    with _lock:
        _state["gpu_works"] = False
        _state["device"] = "cpu"
        _state["reason"] = reason
    _log("GPU 不可用，改用 CPU：%s" % reason)


def load_model(model_ref, download_root=None, progress_cb=None):
    """优先用 GPU 加载 faster-whisper 模型，失败自动退回 CPU。
    返回 (model, device, compute_type)。"""
    from faster_whisper import WhisperModel

    base_kwargs = {}
    if download_root:
        base_kwargs["download_root"] = download_root

    forced = os.environ.get("CX_WHISPER_DEVICE", "").lower()
    want_gpu = forced != "cpu" and _state.get("gpu_works") is not False

    if want_gpu and detect():
        # 运行库还在下载就等它（会在进度条里提示）
        if _state["installing"] and progress_cb:
            progress_cb("准备 GPU 加速", _state.get("install_msg") or "正在准备 GPU 运行库…")
        if ensure_libs():
            add_dll_dirs()
            errs = []
            for ct in _cuda_compute_types():
                m = None
                try:
                    if progress_cb:
                        progress_cb("加载语音模型", "用显卡（%s）加载模型…" % (_state["gpu_name"] or "GPU"))
                    m = WhisperModel(model_ref, device="cuda", compute_type=ct, **base_kwargs)
                    _self_test(m)
                    with _lock:
                        _state["gpu_works"] = True
                        _state["device"] = "cuda"
                        _state["compute_type"] = ct
                        _state["reason"] = ""
                    _log("语音模型已用 GPU 加载（%s，%s）" % (_state["gpu_name"], ct))
                    return m, "cuda", ct
                except Exception as e:
                    errs.append("%s: %s" % (ct, str(e)[:200]))
                    _log("GPU 精度 %s 加载/自检失败：%s" % (ct, e))
                    if "compute type" not in str(e).lower():
                        break   # 不是「精度不支持」（比如缺 DLL / 驱动问题），换精度也没用
                    m = None
                    try:
                        import gc
                        gc.collect()
                    except Exception:
                        pass
            mark_gpu_broken("显卡加载失败：" + (errs[-1] if errs else "未知原因"))
    m = WhisperModel(model_ref, device="cpu", compute_type="int8", **base_kwargs)
    with _lock:
        _state["device"] = "cpu"
        _state["compute_type"] = "int8"
    return m, "cpu", "int8"


def status():
    """给设置页 / 接口用的状态快照（含一句人话总结）。"""
    with _lock:
        s = dict(_state)
    if s["device"] == "cuda":
        s["summary"] = "正在用显卡加速：%s（%s）" % (s["gpu_name"] or "NVIDIA", s["compute_type"])
    elif s["installing"]:
        s["summary"] = s["install_msg"] or "正在准备 GPU 运行库…"
    elif s["has_nvidia"] and s["gpu_works"] is None and s["libs_ok"]:
        s["summary"] = "已准备好显卡加速：%s（下次提取视频时生效）" % (s["gpu_name"] or "NVIDIA")
    elif s["reason"]:
        s["summary"] = "使用 CPU：" + s["reason"]
    elif not s["checked"]:
        s["summary"] = "正在检测显卡…"
    else:
        s["summary"] = "使用 CPU"
    return s
