"""超能小助 · 人声分离（v102）

识别前先把背景音乐、环境声、杂音去掉，只留人声，再交给语音识别——小声的、背景吵的地方认得更准、更少漏。
用的是 UVR 里常用的人声模型 Kim_Vocal_2（MDX-Net，约 66MB），跑在 onnxruntime 上
（软件本来就带着 onnxruntime，静音检测在用），不用另装大工具。有 NVIDIA 显卡、且装了 onnxruntime-gpu 时自动用显卡。

做法：
  · 边解码边处理（每次 30 秒、前后重叠 1 秒做淡入淡出），一小时的视频也不会吃光内存；
  · 输出 16kHz 单声道的人声 wav（识别就用这个），长度和原音频一模一样，时间一秒不差；
  · 结果按文件缓存（models and tools/vocal_cache），同一个文件再提取不用重新分离，只留最近 6 个。
"""
from __future__ import annotations

import hashlib
import os
import time
import wave
from pathlib import Path

import numpy as np

MODEL = {
    "name": "Kim_Vocal_2", "file": "Kim_Vocal_2.onnx", "size_mb": 66,
    "n_fft": 7680, "hop": 1024, "dim_f": 3072, "dim_t": 256, "compensate": 1.009,
}
_URLS = [
    ("GitHub（走代理）", "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx", True),
    ("GitHub 加速镜像", "https://ghfast.top/https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx", False),
    ("GitHub（直连）", "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx", False),
]
SR_IN = 44100
SR_OUT = 16000
BLOCK_S = 30
OVERLAP_S = 1.0
_sess = {}


def _log(msg):
    try:
        print("[人声分离] " + msg, flush=True)
    except Exception:
        pass


# ════════════════ 模型 ════════════════

def model_path(root):
    return Path(root) / "vocal_models" / MODEL["file"]


def ensure_model(root, progress=None, check=None):
    """没有就下载（约 66MB）。返回模型文件路径。"""
    import model_download as md
    p = model_path(root)
    if p.is_file() and p.stat().st_size > 30 * 1024 * 1024:
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    errs = []
    for label, url, via_proxy in _URLS:
        proxy = md._proxy() if via_proxy else ""
        if via_proxy and not proxy:
            continue
        t0 = [time.time(), 0.0]

        def report(have, total, _l=label):
            now = time.time()
            if progress and now - t0[1] >= 1.0:
                t0[1] = now
                progress("人声分离", "第一次用，下载人声模型（%s）：%.0f / %.0f MB" % (
                    _l, have / 1048576, (total or MODEL["size_mb"] * 1048576) / 1048576))
        try:
            md._fetch(md._opener(proxy), url, p, report=report, check=check)
            if p.stat().st_size > 30 * 1024 * 1024:
                return p
            p.unlink()
            raise RuntimeError("下载的文件不对（太小）")
        except Exception as e:
            if type(e).__name__ in ("ExtractCancelled", "KeyboardInterrupt"):
                raise
            errs.append("%s：%s" % (label, str(e)[:100]))
            _log("下载没成功（%s）：%s" % (label, e))
    raise RuntimeError("人声模型没下载下来——" + "；".join(errs))


def _session(path, want_gpu=True):
    key = str(path) + ("|gpu" if want_gpu else "|cpu")
    if key in _sess:
        return _sess[key]
    import onnxruntime as ort
    try:
        ort.preload_dlls()                    # onnxruntime-gpu 1.21+：从 pip 装的 nvidia 包里加载 CUDA / cuDNN
    except Exception:
        pass
    prov = ["CPUExecutionProvider"]
    if want_gpu and "CUDAExecutionProvider" in ort.get_available_providers():
        prov = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.enable_cpu_mem_arena = False           # 关掉内存池：峰值内存从 2.7GB 降到 1.3GB 左右
    so.enable_mem_pattern = False
    s = ort.InferenceSession(str(path), sess_options=so, providers=prov)
    dev = "显卡" if "CUDAExecutionProvider" in s.get_providers() else "CPU"
    _sess[key] = (s, dev)
    return _sess[key]


# ════════════════ MDX-Net 推理（numpy 版 STFT / iSTFT，和 torch.stft(center=True) 一致）════════════════

_N_FFT, _HOP, _DIM_F, _DIM_T = MODEL["n_fft"], MODEL["hop"], MODEL["dim_f"], MODEL["dim_t"]
_N_BINS = _N_FFT // 2 + 1
_CHUNK = _HOP * (_DIM_T - 1)
_TRIM = _N_FFT // 2
_GEN = _CHUNK - 2 * _TRIM
_WIN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(_N_FFT) / _N_FFT)).astype("float32")   # periodic Hann


def _stft(x):
    """x: [n, chunk] → 复数谱 [n, n_bins, dim_t]"""
    xp = np.pad(x, ((0, 0), (_TRIM, _TRIM)), mode="reflect")
    idx = np.arange(_DIM_T)[:, None] * _HOP + np.arange(_N_FFT)[None, :]
    frames = xp[:, idx] * _WIN                                   # [n, dim_t, n_fft]
    return np.fft.rfft(frames, axis=-1).transpose(0, 2, 1)       # [n, n_bins, dim_t]


def _istft(spec):
    """复数谱 [n, n_bins, dim_t] → [n, chunk]"""
    frames = np.fft.irfft(spec.transpose(0, 2, 1), n=_N_FFT, axis=-1) * _WIN   # [n, dim_t, n_fft]
    n = spec.shape[0]
    L = _N_FFT + _HOP * (_DIM_T - 1)
    out = np.zeros((n, L), dtype="float64")
    wsum = np.zeros(L, dtype="float64")
    for t in range(_DIM_T):
        out[:, t * _HOP: t * _HOP + _N_FFT] += frames[:, t]
        wsum[t * _HOP: t * _HOP + _N_FFT] += _WIN ** 2
    out /= np.where(wsum > 1e-11, wsum, 1.0)
    return out[:, _TRIM: _TRIM + _CHUNK].astype("float32")


def _to_model(spec):
    """[2ch, n_bins, dim_t] 复数 → 模型输入 [4, dim_f, dim_t]（左实、左虚、右实、右虚）"""
    s = spec[:, :_DIM_F]
    return np.stack([s[0].real, s[0].imag, s[1].real, s[1].imag]).astype("float32")


def _from_model(y):
    """模型输出 [4, dim_f, dim_t] → [2ch, n_bins, dim_t] 复数（高频补 0）"""
    out = np.zeros((2, _N_BINS, _DIM_T), dtype="complex64")
    out[0, :_DIM_F] = y[0] + 1j * y[1]
    out[1, :_DIM_F] = y[2] + 1j * y[3]
    return out


def _demix(sess, mix, batch=1):
    """mix: [2, n] 44.1kHz → 人声 [2, n]"""
    n = mix.shape[1]
    pad = _GEN - n % _GEN
    mp = np.concatenate([np.zeros((2, _TRIM), "float32"), mix, np.zeros((2, pad), "float32"),
                         np.zeros((2, _TRIM), "float32")], axis=1)
    starts = list(range(0, n + pad, _GEN))
    outs = []
    name = sess.get_inputs()[0].name
    for k in range(0, len(starts), batch):
        waves = np.stack([mp[:, i:i + _CHUNK] for i in starts[k:k + batch]])          # [b, 2, chunk]
        spec = _stft(waves.reshape(-1, _CHUNK)).reshape(len(waves), 2, _N_BINS, _DIM_T)
        inp = np.stack([_to_model(s) for s in spec])
        y = sess.run(None, {name: inp})[0]
        spec_out = np.stack([_from_model(v) for v in y])                              # [b, 2, n_bins, dim_t]
        w = _istft(spec_out.reshape(-1, _N_BINS, _DIM_T)).reshape(len(waves), 2, _CHUNK)
        outs.append(w[:, :, _TRIM:-_TRIM])
    res = np.concatenate([o.transpose(1, 0, 2).reshape(2, -1) for o in outs], axis=1)
    return res[:, :n] * MODEL["compensate"]


# ════════════════ 解码 / 写出（边读边处理）════════════════

def _decode_stereo(path):
    """一段一段地吐出 44.1kHz 立体声 float32 [2, k]。"""
    import av
    with av.open(str(path)) as c:
        st = next(s for s in c.streams if s.type == "audio")
        rs = av.AudioResampler(format="s16", layout="stereo", rate=SR_IN)
        for frame in c.decode(st):
            frame.pts = None
            for f in rs.resample(frame):
                a = f.to_ndarray().reshape(-1, 2).T.astype("float32") / 32768.0
                yield a
        for f in rs.resample(None):
            yield f.to_ndarray().reshape(-1, 2).T.astype("float32") / 32768.0


class _Down:
    """44.1kHz 单声道 → 16kHz 单声道（用 av 的重采样，流式）。"""

    def __init__(self):
        import av
        self.av = av
        self.rs = av.AudioResampler(format="s16", layout="mono", rate=SR_OUT)

    def push(self, x):
        out = []
        if x is None:
            fr = self.rs.resample(None)
        else:
            f = self.av.AudioFrame.from_ndarray(np.clip(x, -1, 1).astype("float32")[None, :], format="flt", layout="mono")
            f.sample_rate = SR_IN
            fr = self.rs.resample(f)
        for f in fr:
            out.append(f.to_ndarray().reshape(-1))
        return np.concatenate(out) if out else np.zeros(0, "int16")


def _cache_key(path):
    st = os.stat(path)
    h = hashlib.sha1(("%s|%d|%d|%s" % (os.path.abspath(path), st.st_size, int(st.st_mtime), MODEL["name"])).encode("utf-8"))
    return h.hexdigest()[:16]


def _clean_cache(d, keep=6):
    try:
        fs = sorted(Path(d).glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in fs[keep:]:
            p.unlink()
    except Exception:
        pass


def _probe_total(path):
    try:
        import av
        with av.open(str(path)) as c:
            st = next(x for x in c.streams if x.type == "audio")
            return float((st.duration * st.time_base) if st.duration else (c.duration or 0) / 1e6) or 0.0
    except Exception:
        return 0.0


def _separate_core(path, out_path, sess, report, check=None):
    """分离 path 的人声，写成 16kHz 单声道 wav 到 out_path。report(已处理秒数) 报进度。"""
    B = int(BLOCK_S * SR_IN)
    OV = int(OVERLAP_S * SR_IN)
    fade_in = np.linspace(0, 1, OV, dtype="float32")
    st = {"buf": np.zeros((2, 0), "float32"), "tail": None, "done": 0.0}
    down = _Down()
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR_OUT)

        def emit(mono):
            if mono.size:
                w.writeframes(down.push(mono).astype("<i2").tobytes())

        def run_block(blk, last):
            if check:
                check()
            v = _demix(sess, blk).mean(axis=0)
            if st["tail"] is not None:                      # 和上一块重叠的 1 秒：淡入淡出接起来
                k = min(OV, v.size, st["tail"].size)
                v[:k] = v[:k] * fade_in[:k] + st["tail"][:k] * (1 - fade_in[:k])
            if last:
                emit(v)
                st["tail"] = None
            else:
                emit(v[:-OV])
                st["tail"] = v[-OV:].copy()
            st["done"] += (blk.shape[1] - (0 if last else OV)) / SR_IN
            report(st["done"])

        for chunk in _decode_stereo(path):
            st["buf"] = np.concatenate([st["buf"], chunk], axis=1)
            while st["buf"].shape[1] >= B + OV:
                run_block(st["buf"][:, :B + OV], False)
                st["buf"] = st["buf"][:, B:]
        if st["buf"].shape[1]:
            run_block(st["buf"], True)
        elif st["tail"] is not None:
            emit(st["tail"])
        w.writeframes(down.push(None).astype("<i2").tobytes())


# ════════════════ 显卡：单独的环境 + 子进程（不和软件自己的组件打架）════════════════
_GPU_FAIL = {"at": 0.0, "why": ""}


def _gpu_env(root, progress):
    """显卡版人声分离用的单独 Python 环境（models and tools/vocal-gpu-env）：
    onnxruntime-gpu（带 CUDA、cuDNN 运行库，约 1～2GB，只装一次）+ numpy + av。返回这个环境的 python。"""
    import sys
    import model_download as md
    env = Path(root) / "vocal-gpu-env"
    py = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    say = (lambda m: progress("人声分离", m)) if progress else (lambda m: None)
    code = "import onnxruntime as o, numpy, av; print('CUDAExecutionProvider' in o.get_available_providers())"
    if py.exists():
        ok, out = md._py_ok(code, py=str(py))
        if ok and "True" in out:
            return str(py)
    else:
        say("第一次用显卡分离人声：准备单独的环境…")
        ok, out = md._run([sys.executable, "-m", "venv", str(env)], 600)
        if not ok or not py.exists():
            raise RuntimeError("单独环境没建起来：%s" % ((out or "").strip().splitlines() or ["?"])[-1][:150])
    import gpu_accel
    last = ""
    for label, extra in gpu_accel._MIRRORS:
        say("第一次用显卡分离人声：装显卡运行库（约 1～2GB，只装一次）· %s…" % label)
        ok, out = md._run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--prefer-binary",
                           "onnxruntime-gpu[cuda,cudnn]", "numpy", "av"] + extra, 3600)
        if ok:
            break
        last = ((out or "").strip().splitlines() or ["网络问题"])[-1]
    ok, out = md._py_ok(code, py=str(py))
    if not (ok and "True" in out):
        raise RuntimeError("显卡运行库没装好（%s）" % (last or ((out or "").strip().splitlines() or ["?"])[-1])[:150])
    return str(py)


def _separate_gpu(path, out_path, root, model_file, total, say, check):
    """在单独环境的子进程里用显卡分离。显卡用不了返回 False（上层改用 CPU）。"""
    import subprocess
    import sys
    py = _gpu_env(root, lambda s, m: say(m))
    flags = 0x08000000 if sys.platform == "win32" else 0
    cmd = [py, os.path.abspath(__file__), "--in", str(path), "--out", str(out_path), "--model", str(model_file)]
    if os.environ.get("CX_VOCAL_ALLOW_CPU_CHILD"):            # 只给测试用
        cmd.append("--allow-cpu")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", creationflags=flags)
    tail = []
    t0 = time.time()
    try:
        for line in p.stdout:
            if check:
                check()
            line = line.strip()
            if line.startswith("PROG "):
                done = float(line.split()[1])
                el = time.time() - t0
                left = el / max(done, 1e-3) * max(0.0, total - done) if total else 0
                say("人声分离（显卡）：%d / %d 分钟%s" % (done // 60, max(1, total // 60),
                                                    "，还要约 %d 秒" % left if total and left < 60 else
                                                    ("，还要约 %d 分钟" % (left // 60 + 1) if total else "")))
            elif line:
                tail.append(line)
                tail = tail[-5:]
        p.wait()
    except BaseException:
        p.kill()
        raise
    if p.returncode == 3:
        return False
    if p.returncode != 0:
        raise RuntimeError("显卡分离出错：%s" % (tail[-1] if tail else "原因不明")[:200])
    return True


def separate(path, root, progress=None, check=None):
    """把 path 的人声分离出来，返回 16kHz 单声道人声 wav 的路径（有缓存就直接用）。
    有 NVIDIA 显卡就用显卡（单独环境的子进程）；显卡用不了自动改用 CPU（慢一些，但一定能用）。"""
    say = (lambda m: progress("人声分离", m)) if progress else (lambda m: None)
    cache = Path(root) / "vocal_cache"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / (_cache_key(path) + ".wav")
    if out.is_file() and out.stat().st_size > 1000:
        say("用上次分离好的人声（同一个文件不用再分离）")
        os.utime(out, None)
        return str(out)
    mp = ensure_model(root, progress, check)
    total = _probe_total(path)
    tmp = out.with_suffix(".part.wav")
    t0 = time.time()
    dev = ""
    want_gpu = False
    try:
        import gpu_accel
        want_gpu = gpu_accel.detect() and os.environ.get("CX_WHISPER_DEVICE", "").lower() != "cpu" \
            and time.time() - _GPU_FAIL["at"] > 3600
    except Exception:
        want_gpu = False
    if want_gpu:
        try:
            say("先把背景音乐、杂音去掉，只留人声（显卡）…")
            if _separate_gpu(path, tmp, root, mp, total, say, check):
                dev = "显卡"
            else:
                _GPU_FAIL.update(at=time.time(), why="显卡没用上")
                say("显卡没用上，改用 CPU 分离（慢一些）…")
        except Exception as e:
            if type(e).__name__ in ("ExtractCancelled", "KeyboardInterrupt"):
                raise
            _GPU_FAIL.update(at=time.time(), why=str(e)[:200])
            _log("显卡分离没成功，改用 CPU：%s" % e)
            say("显卡分离没成功（%s），改用 CPU（慢一些）…" % str(e)[:60])
    if not dev:
        sess, _d = _session(mp, want_gpu=False)
        dev = "CPU"
        say("先把背景音乐、杂音去掉，只留人声（CPU，长视频要多等一会儿）…")

        def report(done):
            el = time.time() - t0
            if total:
                left = el / max(done, 1e-3) * max(0.0, total - done)
                say("人声分离（CPU）：%d / %d 分钟，还要约 %s" % (done // 60, max(1, total // 60),
                                                         "%d 分钟" % (left // 60 + 1) if left >= 60 else "%d 秒" % left))
            else:
                say("人声分离（CPU）：已处理 %d 分钟" % (done // 60))
        _separate_core(path, tmp, sess, report, check)
    os.replace(tmp, out)
    _clean_cache(cache)
    _log("✓ 分离好了：%s → %s（%s，%d 秒）" % (os.path.basename(str(path))[:40], out.name, dev, time.time() - t0))
    return str(out)


# ════════════════ 子进程入口（显卡版，在单独环境里跑）════════════════
if __name__ == "__main__":
    import argparse
    import sys as _sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--allow-cpu", action="store_true")
    a = ap.parse_args()
    try:
        sess, dev = _session(a.model, want_gpu=True)
        if dev != "显卡" and not a.allow_cpu:
            print("NOGPU", flush=True)
            _sys.exit(3)
        print("DEV " + dev, flush=True)
        _separate_core(a.inp, a.out, sess, lambda d: print("PROG %.1f" % d, flush=True))
    except SystemExit:
        raise
    except Exception as e:
        print("ERR %s" % e, flush=True)
        _sys.exit(1)
