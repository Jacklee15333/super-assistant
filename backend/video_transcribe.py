"""
video_transcribe.py — 把视频里"人说的话"提取成文字（语音识别）

用途：你看到一个不错的视频（抖音/B站/YouTube 等），没时间细看，
想把里面讲的内容提取成文字、让 AI 帮你总结、存起来以后再看。

原理（都在你本机完成，不上传到任何第三方）：
  1. 用 yt-dlp 把这个视频的音频下载到临时文件；
  2. 用 faster-whisper 在本机做语音识别（speech-to-text），转成文字；
  3. 文字交给 AI 总结、归纳，再存档。

依赖（都是纯 pip 安装，不用单独装 ffmpeg）：
  - yt-dlp        负责下载
  - faster-whisper 负责语音转文字（它依赖的 av 库自带解码器）

说明：这是给"你自己看过、想做笔记"的单个视频用的个人工具，
一次一个、你手动发起。请只用于个人学习记录，不要批量抓取或二次传播他人内容。
"""

import os
import re
import glob
import shutil
import tempfile
import threading
from pathlib import Path

# 关键：Hugging Face 在国内常连不上，语音模型下载会失败。
# 1) 用国内镜像 hf-mirror.com；
# 2) 关掉 Xet 大文件后端（它走 cas-bridge.xethub.hf.co，国内连不上、会超时），
#    关掉后大文件也走镜像，能正常下。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# 模型缓存，避免每次都重新加载
_model_cache = {}

# ★全局闸门：视频提取（下载+语音识别+总结）很吃 CPU/显存，
#   保证同一时间只有一个提取任务在跑——对话里发链接、和「视频」板块队列，
#   都共用这同一个闸门，避免互相抢资源、卡死。
# Semaphore(1) 等价于一把可重复 acquire/release 的锁，但 release 多了不会抛硬错。
extract_gate = threading.BoundedSemaphore(1)


def extract_busy():
    """当前是否有视频提取任务正在进行（闸门被占用）。
    用非阻塞方式探一下：能拿到就立刻还回去，说明空闲；拿不到说明在忙。"""
    got = extract_gate.acquire(blocking=False)
    if got:
        try:
            extract_gate.release()
        except (ValueError, RuntimeError):
            pass
        return False
    return True


def _models_dir():
    """放手动下载好的模型的文件夹。默认是项目同级的 “models and tools”。
    也可用环境变量 CX_MODELS_DIR 指定别的位置。"""
    env = os.environ.get("CX_MODELS_DIR")
    if env:
        return Path(env)
    # backend 在  .../超能小助/backend，往上两级再进 “models and tools”
    return Path(__file__).resolve().parent.parent.parent / "models and tools"


def _resolve_model(size):
    """本地若已下载好对应模型文件夹，就用本地的（不再联网）；否则返回模型名让它自动下载。"""
    base = _models_dir()
    for c in (base / f"faster-whisper-{size}", base / size,
              base / f"Systran--faster-whisper-{size}"):
        try:
            if (c / "model.bin").exists():
                return str(c)
        except Exception:
            pass
    return size


def _paragraphize(text):
    """把一长串识别文字切成自然段落。优先按句末标点；没有就按逗号；
    再没有就按长度硬切——保证再难看的无标点文本也能分段。"""
    if not text:
        return ""
    t = re.sub(r"[ \t]+", " ", text).strip()
    if "\n\n" in t:
        return t  # 已经分好段了
    if re.search(r"[。！？!?…；;]", t):
        units = re.findall(r"[^。！？!?…；;]*[。！？!?…；;]+", t)
        tail = re.sub(r"[^。！？!?…；;]*[。！？!?…；;]+", "", t).strip()
        if tail:
            units.append(tail)
    elif re.search(r"[，,、]", t):
        units = re.findall(r"[^，,、]*[，,、]+", t)
        tail = re.sub(r"[^，,、]*[，,、]+", "", t).strip()
        if tail:
            units.append(tail)
    else:
        units = [t[i:i + 40] for i in range(0, len(t), 40)]
    if not units:
        units = [t]
    paras, cur = [], ""
    for u in units:
        cur += u
        if len(cur) >= 110:
            paras.append(cur.strip())
            cur = ""
    if cur.strip():
        paras.append(cur.strip())
    return "\n\n".join(paras)


def models_info():
    """返回模型下载位置 + 已下载的模型清单，给设置页显示。"""
    d = _models_dir()
    found = []
    try:
        if d.exists():
            for p in sorted(d.iterdir()):
                n = p.name
                if p.is_dir() and "faster-whisper" in n:
                    # 友好显示：精准/均衡/快速
                    label = n
                    if "medium" in n:
                        label = "精准模型 (medium)"
                    elif "small" in n:
                        label = "均衡模型 (small)"
                    elif "base" in n:
                        label = "快速模型 (base)"
                    found.append(label)
    except Exception:
        pass
    return {"dir": str(d), "models": found}

# 友好的模型档位：speed=快但糙，balanced=均衡(默认)，accurate=慢但准
MODEL_MAP = {
    "speed": "base",
    "balanced": "small",
    "accurate": "medium",
}


def _find_url(text):
    """从用户粘贴的一大段分享文案里，揪出真正的视频链接。
    抖音分享出来是『标题+表情+一句话+链接+复制此链接…』，要把链接抠出来。"""
    if not text:
        return ""
    text = text.strip()
    # 抓第一个 http(s) 链接，到空白或常见中文标点为止
    m = re.search(r"https?://[^\s，。！？、）)\]】]+", text)
    if m:
        return m.group(0).rstrip(".,，。")
    return text  # 没找到链接就原样返回（可能用户就是贴了纯链接）


def _clean_err(s):
    """去掉 yt-dlp 报错里的 ANSI 颜色码等噪音，让提示更干净。"""
    s = re.sub(r"\x1b\[[0-9;]*m", "", str(s))
    s = re.sub(r"\[[0-9;]*m", "", s)
    return s.strip()


def check_deps():
    """检查依赖是否就绪。返回缺失的包名列表（空表示都装好了）。"""
    missing = []
    try:
        import yt_dlp  # noqa
    except Exception:
        missing.append("yt-dlp")
    try:
        import faster_whisper  # noqa
    except Exception:
        missing.append("faster-whisper")
    return missing


def _set_user_env(name, value):
    """Windows 上持久设置用户环境变量（setx），让新启动的 Ollama 能读到。返回是否成功。"""
    import sys
    import subprocess
    try:
        os.environ[name] = value
        if sys.platform != "win32":
            return False
        r = subprocess.run(["setx", name, value],
                           capture_output=True, text=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def _dir_size_gb(p):
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1024 / 1024 / 1024
    except Exception:
        return 0.0


def _file_count(p):
    try:
        return sum(1 for f in p.rglob("*") if f.is_file())
    except Exception:
        return 0


def _move_ollama_models(dest):
    """把 C 盘的 Ollama 大模型安全搬到 D 盘：先复制 → 校验完整 → 删源释放，
    并设置 OLLAMA_MODELS 指向新位置。过程中任何一步出错都不会破坏 C 盘原文件。"""
    moved, notes = [], []
    src_env = (os.environ.get("OLLAMA_MODELS") or "").strip()
    src = Path(src_env) if src_env else (Path.home() / ".ollama" / "models")

    if not src.exists():
        notes.append("没找到 Ollama 模型文件夹（可能没装 Ollama，或模型已不在默认位置）。")
        return {"moved": moved, "notes": notes}

    try:
        on_c = str(src.resolve()).lower().startswith("c:")
    except Exception:
        on_c = True
    if not on_c:
        notes.append(f"Ollama 模型已经不在 C 盘了（{src}），无需搬运。")
        return {"moved": moved, "notes": notes}

    target = dest / "ollama-models"
    src_gb = _dir_size_gb(src)

    # ① 复制（源只读，最安全）
    if target.exists() and _file_count(target) > 0:
        notes.append(f"D 盘已有 Ollama 模型夹（{target}），跳过复制；将直接校验后清理 C 盘。")
    else:
        try:
            shutil.copytree(str(src), str(target), dirs_exist_ok=True)
        except Exception as e:
            notes.append("复制 Ollama 模型失败——如果 Ollama 正在运行，请先在右下角托盘"
                         f"退出 Ollama 再点一次按钮。详情：{e}")
            return {"moved": moved, "notes": notes}

    # ② 校验：D 盘文件数不少于 C 盘，才认为复制完整
    if _file_count(target) < _file_count(src):
        notes.append("复制后文件数不一致，为安全起见【没有删除 C 盘原文件】。"
                     "请退出 Ollama 后再点一次按钮重试。")
        return {"moved": moved, "notes": notes}

    # ③ 设置 OLLAMA_MODELS（用户级，持久）
    set_ok = _set_user_env("OLLAMA_MODELS", str(target))

    # ④ 删源，释放 C 盘
    leftover = False
    try:
        shutil.rmtree(str(src), ignore_errors=True)
        if src.exists() and _file_count(src) > 0:
            leftover = True
    except Exception:
        leftover = True

    moved.append(f"Ollama 模型 → {target}（约 {src_gb:.1f} GB）")
    if set_ok:
        notes.append("✅ 已把 OLLAMA_MODELS 指向 D 盘。请【退出并重新打开 Ollama】，"
                     "再重启本软件即可生效。")
    else:
        notes.append(f"模型已搬到 {target}，但没能自动写环境变量。请手动新建系统环境变量 "
                     f"OLLAMA_MODELS = {target}，再重启 Ollama。")
    if leftover:
        notes.append(f"⚠ C 盘还有少量残留（Ollama 可能仍占用）：退出 Ollama 后手动删除 {src} 即可。")
    return {"moved": moved, "notes": notes}


def move_cached_models():
    """把 C 盘上已下载的模型搬到 D 盘的 models 文件夹（省 C 盘空间）：
       ① faster-whisper 的 HuggingFace 缓存；② Ollama 的大模型（通常才是 C 盘爆满主因）。
       返回搬了哪些。"""
    dest = _models_dir()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "moved": [], "error": f"建目标文件夹失败：{e}"}
    moved = []
    notes = []
    # ① faster-whisper / HuggingFace 缓存
    hubs = []
    if os.environ.get("HF_HOME"):
        hubs.append(Path(os.environ["HF_HOME"]) / "hub")
    hubs.append(Path.home() / ".cache" / "huggingface" / "hub")
    for hub in hubs:
        try:
            if not hub.exists():
                continue
            for d in list(hub.glob("models--Systran--faster-whisper-*")):
                target = dest / d.name
                if target.exists():
                    moved.append(f"{d.name}（D盘已存在，跳过）")
                    continue
                try:
                    shutil.move(str(d), str(target))  # 跨盘会自动复制+删除
                    moved.append(d.name)
                except Exception as e:
                    moved.append(f"{d.name} 搬运失败：{e}")
        except Exception:
            continue
    # ② Ollama 大模型
    try:
        ores = _move_ollama_models(dest)
        moved.extend(ores.get("moved", []))
        notes.extend(ores.get("notes", []))
    except Exception as e:
        notes.append(f"Ollama 模型处理出错：{e}")
    return {"ok": bool([m for m in moved if "失败" not in m]) or bool(moved),
            "moved": moved, "notes": notes, "dest": str(dest)}


def install_deps():
    """尝试自动 pip 安装依赖。返回 (是否成功, 输出文本)。"""
    import sys
    import subprocess
    pkgs = ["yt-dlp", "faster-whisper"]
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs
    # 某些环境需要 --break-system-packages，加上不影响普通环境
    try:
        r = subprocess.run(cmd + ["--break-system-packages"],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            # 再试一次不带该参数
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        ok = r.returncode == 0 and not check_deps()
        out = (r.stdout or "") + (r.stderr or "")
        return ok, out[-3000:]
    except Exception as e:
        return False, f"安装出错：{e}"


def _download_audio(url, outdir):
    """用 yt-dlp 下载音频到 outdir，返回 (文件路径, 标题/描述)。"""
    import yt_dlp
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(outdir, "media.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 3,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    files = glob.glob(os.path.join(outdir, "media.*"))
    if not files:
        raise RuntimeError("没下载到媒体文件（可能链接失效或平台限制）。")
    title = (info.get("title") or info.get("description") or "").strip()
    uploader = (info.get("uploader") or info.get("creator") or "").strip()
    return files[0], title, uploader


def _transcribe(path, level="balanced", progress_cb=None):
    """用 faster-whisper 把音频转成中文文字。progress_cb(stage, detail) 报告进度。"""
    from faster_whisper import WhisperModel
    size = MODEL_MAP.get(level, "small")
    if size not in _model_cache:
        model_ref = _resolve_model(size)
        is_local = model_ref != size
        kwargs = {"device": "cpu", "compute_type": "int8"}
        if not is_local:
            # 把模型下载/缓存到 D 盘的 models 文件夹，别占 C 盘
            mdir = _models_dir()
            try:
                mdir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            kwargs["download_root"] = str(mdir)
        if progress_cb:
            if is_local:
                progress_cb("加载语音模型", f"用本地已下载的 {size} 模型，无需联网")
            else:
                progress_cb("加载语音模型",
                            f"首次使用要下载 {size} 模型到 {_models_dir()}（经国内镜像），"
                            "可能要等几分钟，只这一次")
        _model_cache[size] = WhisperModel(model_ref, **kwargs)
    model = _model_cache[size]
    if progress_cb:
        progress_cb("语音转文字", "模型就绪，开始逐句识别…")
    segments, info = model.transcribe(
        path, language="zh", vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500})
    total = getattr(info, "duration", 0) or 0
    parts = []
    n = 0
    for seg in segments:
        t = (seg.text or "").strip()
        if t:
            parts.append(t)
        n += 1
        if progress_cb and n % 4 == 0:
            end = getattr(seg, "end", 0) or 0
            if total:
                pct = min(99, int(end / total * 100))
                progress_cb("语音转文字", f"已识别 {pct}%（{int(end)} 秒 / 共 {int(total)} 秒）")
            else:
                progress_cb("语音转文字", f"已识别到第 {int(end)} 秒…")
    raw = "".join(parts).strip()
    return _paragraphize(raw)


def extract(url, level="balanced", progress_cb=None):
    """
    主流程：解析链接 -> 下载音频 -> 语音识别 -> 返回文字稿。
    progress_cb(stage, detail) 用来实时报告"现在在干什么"。
    """
    def step(s, d=""):
        if progress_cb:
            progress_cb(s, d)

    raw = (url or "").strip()
    if not raw:
        return {"ok": False, "error": "链接为空。"}
    step("解析链接", "从你粘贴的内容里找出视频地址…")
    url = _find_url(raw)
    if not url.startswith("http"):
        return {"ok": False,
                "error": "没在你粘贴的内容里找到视频链接。请确认里面有 http(s):// 开头的网址。"}
    missing = check_deps()
    if missing:
        return {"ok": False, "need": missing}
    try:
        cache = _models_dir() / "_video_cache"
        try:
            cache.mkdir(parents=True, exist_ok=True)
        except Exception:
            cache = None
        td = tempfile.mkdtemp(dir=str(cache) if cache else None)
        try:
            step("下载音频", "正在从平台下载视频的音频…")
            media, title, uploader = _download_audio(url, td)
            step("下载音频", f"下载完成：{(title or '')[:30]}")
            transcript = _transcribe(media, level, progress_cb=progress_cb)
        finally:
            shutil.rmtree(td, ignore_errors=True)  # 用完就删，不占地方
        if not transcript:
            return {"ok": False,
                    "error": "下载成功但没识别出文字（可能是纯音乐/无人声，或音频太短）。"}
        return {"ok": True, "title": title, "uploader": uploader,
                "url": url, "transcript": transcript}
    except Exception as e:
        return {"ok": False, "error": f"提取失败：{_clean_err(e)}"}
