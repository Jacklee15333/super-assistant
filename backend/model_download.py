"""超能小助 · 语音模型下载（v89 新增）

以前是让 faster-whisper 自己去 Hugging Face 下模型，问题有三个：
  1. 它先调一个「查仓库信息」的接口，镜像站这个接口偶尔不通，一不通就直接报
     「An error happened while trying to locate the files on the Hub…」，真正原因被藏起来了；
  2. 下载没有进度，3GB 的大模型下几分钟，界面上一点动静都没有；
  3. 下载失败被 gpu_accel 当成「显卡坏了」，之后整个运行期间都退回 CPU。

现在改成自己下：直接按文件地址下载（不调查询接口），
  · 先走国内镜像 hf-mirror.com（直连）→ 不行再走 Hugging Face 官网（经「设置 → 联网与代理」的代理）
    → 再不行用代理连镜像；
  · 每个文件断点续传（.part），下完核对大小、json 能不能解析，最后整个文件夹一次性改名到位；
  · 进度每秒报一次：「已下 1.20 / 3.09 GB · 5.3 MB/s · 还要约 6 分钟」；
  · 下到 models and tools\\faster-whisper-<型号>\\，以后加载完全不联网。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "kotoba-v2": "kotoba-tech/kotoba-whisper-v2.0-faster",     # v97：日语专用
}
APPROX_GB = {"anime": 1.6, "kotoba-v2": 1.5, "tiny": 0.08, "base": 0.15, "small": 0.48, "medium": 1.5, "large-v2": 3.1, "large-v3": 3.1}

# 小文件先下（坏了马上知道），最后下 model.bin
SMALL_REQUIRED = ["config.json", "tokenizer.json"]
VOCAB = ["vocabulary.json", "vocabulary.txt"]          # 两种写法有一个就行
PREPROC = "preprocessor_config.json"                    # large-v3 必须有（128 维特征），别的型号没有这个文件
NEED_PREPROC = {"large-v3", "kotoba-v2", "anime"}
# kotoba-whisper 是在 large-v3 上训练的（128 维特征）。仓库里万一没放特征配置，就按 large-v3 的写一份
_DEFAULT_PREPROC = {"chunk_length": 30, "feature_extractor_type": "WhisperFeatureExtractor", "feature_size": 128,
                    "hop_length": 160, "n_fft": 400, "n_samples": 480000, "nb_max_frames": 3000,
                    "padding_side": "right", "padding_value": 0.0, "processor_class": "WhisperProcessor",
                    "return_attention_mask": False, "sampling_rate": 16000}
BIG = "model.bin"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) chaoneng-assistant/model-download"

_locks = {}
_locks_guard = threading.Lock()


class _NotFound(Exception):
    pass


def _log(msg):
    try:
        print("[model] " + msg, flush=True)
    except Exception:
        pass


def _gb(n):
    return "%.2f GB" % (n / 1024 ** 3) if n >= 1024 ** 3 * 0.1 else "%.0f MB" % (n / 1024 ** 2)


def approx_gb(size):
    return APPROX_GB.get(size, 1.0)


# ════════════════ 本机已经有了吗 ════════════════

def _complete(d, size):
    """这个文件夹里的模型能不能直接用：model.bin（像样的大小）+ config.json；large-v3 还要特征配置。"""
    try:
        d = Path(d)
        mb = d / BIG
        if not (mb.is_file() and mb.stat().st_size > 10 * 1024 * 1024):
            return False
        if not (d / "config.json").is_file():
            return False
        if size in NEED_PREPROC and not (d / PREPROC).is_file():
            return False
        return True
    except Exception:
        return False


def find_local(size, root):
    """本机已下载好的模型文件夹（手动放的、或以前自动下载进缓存的都算）。没有返回空串。"""
    root = Path(root)
    cands = [root / ("faster-whisper-%s" % size), root / size, root / ("Systran--faster-whisper-%s" % size)]
    for repo_dir in (root / ("models--Systran--faster-whisper-%s" % size),
                     root / ("models--mobiuslabsgmbh--faster-whisper-%s" % size)):
        snap = repo_dir / "snapshots"
        try:
            if snap.is_dir():
                cands += sorted(snap.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:
            pass
    for c in cands:
        if _complete(c, size):
            return str(c)
    return ""


# ════════════════ 下载 ════════════════

def _proxy():
    try:
        import web_tools
        return web_tools.apply_proxy_env() or web_tools._read_proxy() or ""
    except Exception:
        return ""


def _opener(proxy):
    handlers = []
    try:
        import web_tools
        handlers.append(urllib.request.HTTPSHandler(context=web_tools._ssl_ctx()))
    except Exception:
        pass
    handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {}))
    return urllib.request.build_opener(*handlers)


def _sources():
    """(说明, 地址, 代理)。国内镜像先直连；有代理再试官网和「代理连镜像」。"""
    p = _proxy()
    out = [("国内镜像", "https://hf-mirror.com", "")]
    if p:
        out.append(("Hugging Face 官网（走代理）", "https://huggingface.co", p))
        out.append(("国内镜像（走代理）", "https://hf-mirror.com", p))
    return out


def _fetch(opener, url, dest, report=None, check=None):
    """下载一个文件到 dest（先写 dest.part，支持断点续传）。404 抛 _NotFound。返回字节数。"""
    tmp = dest.with_name(dest.name + ".part")
    have = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": UA}
    if have:
        headers["Range"] = "bytes=%d-" % have
    try:
        resp = opener.open(urllib.request.Request(url, headers=headers), timeout=30)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise _NotFound(url)
        if e.code == 416 and have:                 # 上次其实已经下完了
            tmp.replace(dest)
            return have
        raise RuntimeError("服务器返回 %s %s" % (e.code, (e.reason or "")))
    with resp:
        code = resp.getcode()
        if have and code != 206:                   # 服务器不支持续传 → 从头来
            have = 0
        total = 0
        cr = resp.headers.get("Content-Range") or ""
        cl = resp.headers.get("Content-Length") or ""
        if code == 206 and "/" in cr and cr.rsplit("/", 1)[1].strip().isdigit():
            total = int(cr.rsplit("/", 1)[1])
        elif cl.isdigit():
            total = int(cl) + (have if code == 206 else 0)
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if dest.name == BIG and "text/html" in ctype:
            raise RuntimeError("拿到的是网页不是模型文件（可能被拦了）")
        with open(tmp, "ab" if have else "wb") as f:
            while True:
                if check:
                    check()
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                have += len(chunk)
                if report:
                    report(have, total)
    if total and have < total:
        raise RuntimeError("下载中断了（%s / %s），下次会接着下" % (_gb(have), _gb(total)))
    if dest.suffix == ".json":
        try:
            json.loads(tmp.read_text(encoding="utf-8"))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("%s 内容不对（不是正常的 json）" % dest.name)
    tmp.replace(dest)
    return have


def _fetch_all(opener, ep, repo, size, part, label, progress, check):
    base = "%s/%s/resolve/main/" % (ep, repo)
    # ① 小文件
    for fn in SMALL_REQUIRED:
        if not (part / fn).is_file():
            _fetch(opener, base + fn, part / fn, check=check)
    if not any((part / v).is_file() for v in VOCAB):
        got = False
        for v in VOCAB:
            try:
                _fetch(opener, base + v, part / v, check=check)
                got = True
                break
            except _NotFound:
                continue
        if not got:
            raise RuntimeError("仓库里没找到词表文件")
    if not (part / PREPROC).is_file():
        try:
            _fetch(opener, base + PREPROC, part / PREPROC, check=check)
        except _NotFound:
            if size.startswith("kotoba"):
                (part / PREPROC).write_text(json.dumps(_DEFAULT_PREPROC), encoding="utf-8")
            elif size in NEED_PREPROC:
                raise RuntimeError("仓库里没找到 %s" % PREPROC)
    # ② 大文件，带进度
    if (part / BIG).is_file():
        return
    st = {"t0": time.time(), "last": 0.0, "b0": None}

    def report(have, total):
        now = time.time()
        if st["b0"] is None:
            st["b0"] = have
        if now - st["last"] < 1.0:
            return
        st["last"] = now
        el = max(0.5, now - st["t0"])
        speed = max(0, have - st["b0"]) / el
        tot = total or int(approx_gb(size) * 1024 ** 3)
        msg = "%s：已下 %s / %s" % (label, _gb(have), _gb(tot))
        if speed > 0:
            msg += " · %.1f MB/s" % (speed / 1024 ** 2)
            left = max(0, tot - have) / speed
            if left >= 1:
                msg += " · 还要约 %s" % ("%d 分钟" % max(1, round(left / 60)) if left >= 60 else "%d 秒" % left)
        if progress:
            try:
                progress(msg)
            except Exception:
                pass

    _fetch(opener, base + BIG, part / BIG, report=report, check=check)


def _is_cancel(e):
    return type(e).__name__ in ("ExtractCancelled", "KeyboardInterrupt")


# ════════════════ v98：要「转格式」的模型（Anime-Whisper）════════════════
# Anime-Whisper 只发布了原始格式（PyTorch / transformers），软件的识别引擎用的是 CTranslate2 格式。
# 做法：第一次用时 ① 下载原始模型 ② 装转换工具（transformers + PyTorch 的 CPU 版，只装一次）
# ③ 在这台电脑上转成 CTranslate2 格式（float16，显卡照样加速）④ 删掉原始文件省空间。以后直接用转好的。
CONVERT = {"anime": "litagin/anime-whisper"}
_HF_SKIP = re.compile(r"(\.md$|\.gitattributes$|\.png$|\.jpg$|\.gif$|^\.|/|optimizer|training_args|\.bin\.index|"
                      r"pytorch_model.*\.bin$|tf_model|flax_model|\.msgpack$|\.h5$|\.onnx)")
_HF_FALLBACK = ["config.json", "generation_config.json", "model.safetensors", "preprocessor_config.json",
                "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "added_tokens.json",
                "special_tokens_map.json", "normalizer.json"]


def _hf_files(opener, ep, repo):
    """仓库里有哪些文件（镜像的查询接口不通就用常见的文件名单）。"""
    try:
        req = urllib.request.Request("%s/api/models/%s" % (ep, repo), headers={"User-Agent": UA})
        with opener.open(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        names = [x.get("rfilename") for x in d.get("siblings") or [] if x.get("rfilename")]
        names = [n for n in names if not _HF_SKIP.search(n)]
        if any(n.endswith(".safetensors") for n in names):
            return names
    except Exception:
        pass
    return list(_HF_FALLBACK)


def _py_ok(code):
    import subprocess
    import sys
    flags = 0x08000000 if sys.platform == "win32" else 0
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300, creationflags=flags)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or ""))[-1500:]
    except Exception as e:
        return False, str(e)


def _ensure_converter(progress):
    ok, _ = _py_ok("import transformers, torch, ctranslate2")
    if ok:
        return
    if progress:
        progress("第一次用要装转换工具（transformers + PyTorch CPU 版，约 300MB，只装一次）…")
    import gpu_accel
    pk = ["transformers>=4.40", "torch"]
    ok, how = gpu_accel._pip_install(pk)
    if not ok:
        tail = (str(how or "").strip().splitlines() or ["网络问题"])[-1]
        raise RuntimeError("转换工具没装上（%s）" % tail[:200])
    ok, out = _py_ok("import transformers, torch")
    if not ok:
        raise RuntimeError("转换工具装了但用不了：%s" % ((out or "").strip().splitlines() or ["原因不明"])[-1][:200])


def _download_convert(size, root, progress=None, check=None):
    repo = CONVERT[size]
    root = Path(root)
    final = root / ("faster-whisper-%s" % size)
    raw = root / ("%s-原始文件" % size)
    raw.mkdir(parents=True, exist_ok=True)
    say = (lambda m: progress(m)) if progress else (lambda m: None)
    errs = []
    got = False
    for label, ep, proxy in _sources():
        op = _opener(proxy)
        say("%s：查模型文件清单…" % label)
        try:
            names = _hf_files(op, ep, repo)
            big = [n for n in names if n.endswith(".safetensors")]
            for n in names:
                if n in big or (raw / n).is_file():
                    continue
                try:
                    _fetch(op, "%s/%s/resolve/main/%s" % (ep, repo, n), raw / n, check=check)
                except _NotFound:
                    if n == "config.json":
                        raise RuntimeError("仓库里没找到 config.json")
            for n in big:
                if (raw / n).is_file():
                    continue
                st = {"t0": time.time(), "last": 0.0, "b0": None}

                def report(have, total, _n=n, _st=st, _label=label):
                    now = time.time()
                    if _st["b0"] is None:
                        _st["b0"] = have
                    if now - _st["last"] < 1.0:
                        return
                    _st["last"] = now
                    sp = max(0, have - _st["b0"]) / max(0.5, now - _st["t0"])
                    tot = total or int(approx_gb(size) * 1024 ** 3)
                    m = "%s：下载 Anime-Whisper %s / %s" % (_label, _gb(have), _gb(tot))
                    if sp > 0:
                        left = max(0, tot - have) / sp
                        m += " · %.1f MB/s · 还要约 %s" % (sp / 1024 ** 2, ("%d 分钟" % max(1, round(left / 60))) if left >= 60 else "%d 秒" % left)
                    say(m)
                _fetch(op, "%s/%s/resolve/main/%s" % (ep, repo, n), raw / n, report=report, check=check)
            if not any(raw.glob("*.safetensors")):
                raise RuntimeError("没下到模型权重文件")
            got = True
            break
        except Exception as e:
            if _is_cancel(e):
                raise
            errs.append("%s：%s" % (label, (str(e) or type(e).__name__)[:160]))
            _log("✗ %s 没下成：%s" % (label, e))
    if not got:
        raise RuntimeError("Anime-Whisper 没下载下来（下好的部分留着，下次接着下）——" + "；".join(errs))
    # 分词表 / 特征配置：原始仓库没带的话，用 large-v3 的（Anime-Whisper 是在它这一系上训练的，分词表一样）
    if not (raw / "preprocessor_config.json").is_file():
        (raw / "preprocessor_config.json").write_text(json.dumps(_DEFAULT_PREPROC), encoding="utf-8")
    if not (raw / "tokenizer.json").is_file():
        say("补一个分词表文件…")
        for label, ep, proxy in _sources():
            try:
                _fetch(_opener(proxy), "%s/Systran/faster-whisper-large-v3/resolve/main/tokenizer.json" % ep,
                       raw / "tokenizer.json", check=check)
                break
            except Exception as e:
                if _is_cancel(e):
                    raise
    if check:
        check()
    _ensure_converter(progress)
    say("把模型转成软件能用的格式（几分钟，只做这一次）…")
    tmp = root / ("faster-whisper-%s.converting" % size)
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    copy = [f for f in ("tokenizer.json", "preprocessor_config.json") if (raw / f).is_file()]
    code = ("import sys; from ctranslate2.converters.transformers import main; "
            "sys.argv=['ct2', '--model', %r, '--output_dir', %r, '--quantization', 'float16', '--copy_files'] + %r; main()"
            % (str(raw), str(tmp), copy))
    ok, out = _py_ok(code)
    if not ok or not _complete(tmp, "large-v3"):
        raise RuntimeError("转格式没成功：%s" % (out.strip().splitlines()[-1] if out.strip() else "原因不明"))
    if final.exists():
        shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    shutil.rmtree(raw, ignore_errors=True)
    _log("✓ Anime-Whisper 准备好了：%s" % final)
    return str(final)


def download(size, root, progress=None, check=None):
    """把 size 型号的模型下载到 root/faster-whisper-<size>/，返回文件夹路径。
    progress(说明) 报进度；check() 用来取消（抛异常即中断，下好的部分留着下次续传）。
    所有来源都失败时抛 RuntimeError，说明里带每个来源的真实原因。"""
    if size in CONVERT:
        with _locks_guard:
            lk = _locks.setdefault(size, threading.Lock())
        with lk:
            have = find_local(size, root)
            return have or _download_convert(size, root, progress, check)
    repo = REPOS.get(size)
    if not repo:
        raise RuntimeError("不认识的模型型号：%s" % size)
    with _locks_guard:
        lk = _locks.setdefault(size, threading.Lock())
    with lk:
        root = Path(root)
        have = find_local(size, root)
        if have:
            return have
        root.mkdir(parents=True, exist_ok=True)
        final = root / ("faster-whisper-%s" % size)
        part = root / ("faster-whisper-%s.downloading" % size)
        part.mkdir(parents=True, exist_ok=True)
        errs = []
        for label, ep, proxy in _sources():
            if progress:
                try:
                    progress("%s：连接中…（约 %.1f GB，只下这一次）" % (label, approx_gb(size)))
                except Exception:
                    pass
            _log("下载 %s 模型：试 %s（%s）" % (size, label, ep))
            try:
                _fetch_all(_opener(proxy), ep, repo, size, part, label, progress, check)
                if not _complete(part, size):
                    raise RuntimeError("下完了但文件不全")
                if final.exists():                       # 以前手动放过、但不完整的：挪开备份
                    bak = root / ("faster-whisper-%s.bak-%d" % (size, int(time.time())))
                    try:
                        final.rename(bak)
                    except Exception:
                        shutil.rmtree(final, ignore_errors=True)
                part.rename(final)
                _log("✓ %s 模型下载好了：%s（%s）" % (size, final, label))
                return str(final)
            except Exception as e:
                if _is_cancel(e):
                    raise
                why = str(e) or type(e).__name__
                if isinstance(e, _NotFound):
                    why = "找不到文件"
                elif isinstance(e, urllib.error.URLError):
                    why = "连不上（%s）" % (getattr(e, "reason", "") or e)
                errs.append("%s：%s" % (label, why[:160]))
                _log("✗ %s 没下成：%s" % (label, why[:300]))
        tip = "" if len(errs) > 1 else "；在「设置 → 联网与代理」填上代理后，还会自动试 Hugging Face 官网"
        raise RuntimeError("%s 模型没下载下来（已下好的部分留着，下次接着下）——%s%s" % (
            size, "；".join(errs), tip))
