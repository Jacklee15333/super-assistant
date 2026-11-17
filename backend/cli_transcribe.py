#!/usr/bin/env python3
"""超能小助 · 视频转写命令行入口（复用 backend 里现成的整套能力）

用法:
    python cli_transcribe.py "<抖音分享链接或整段分享文案>"
    python cli_transcribe.py <链接> --level accurate
    python cli_transcribe.py <本地音视频文件>

产物写到 backend/转写结果/：
    <标题>.txt    原文
    <标题>.srt    字幕，可拖进 PotPlayer / VLC 对照原片
    <标题>.json   分段与元信息
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT_DIR = HERE / "转写结果"


def _setup_cuda_dlls() -> None:
    """CTranslate2 的 Windows 包不自带 CUDA 运行库，从 nvidia-*-cu12 包里借。"""
    base = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    dirs = [p for p in (base / "cublas" / "bin", base / "cudnn" / "bin") if p.is_dir()]
    for d in dirs:
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(str(d))
        except (AttributeError, OSError):
            pass


def warm_gpu(level: str) -> None:
    """提前把模型以 CUDA 方式塞进 video_transcribe 的模型缓存。
    它自己的 _transcribe 发现缓存里已有就直接用，于是命令行走 GPU，
    而 App 那边不经过这里，仍然保持原来的 CPU 行为。"""
    import video_transcribe as vt

    size = vt.MODEL_MAP.get(level, "small")
    if size in vt._model_cache:
        return
    from faster_whisper import WhisperModel

    _setup_cuda_dlls()
    ref = vt._resolve_model(size)
    kwargs = {"device": "cuda", "compute_type": "float16"}
    if ref == size:  # 本地没有这个模型，走它自己的镜像下载目录
        mdir = vt._models_dir()
        mdir.mkdir(parents=True, exist_ok=True)
        kwargs["download_root"] = str(mdir)
    try:
        vt._model_cache[size] = WhisperModel(ref, **kwargs)
        print(f"[GPU] {size} 模型已加载 (float16)", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[!] GPU 不可用（{type(e).__name__}: {e}），本次回退 CPU", flush=True)


def srt_ts(t: float) -> str:
    h, rem = divmod(float(t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def safe_name(title: str, url: str) -> str:
    t = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", (title or "").strip())[:40].strip() or "未命名"
    return f"{t}_{hashlib.md5(url.encode('utf-8')).hexdigest()[:6]}"


def write_outputs(res: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = OUT_DIR / safe_name(res.get("title", ""), res.get("url", "") or str(res.get("title")))
    text = res.get("transcript") or ""
    segs = res.get("segments") or []

    (base.with_suffix(".txt")).write_text(
        f"{res.get('title', '')}\n\n{text}\n", encoding="utf-8")

    with base.with_suffix(".srt").open("w", encoding="utf-8") as f:
        for i, s in enumerate(segs, 1):
            f.write(f"{i}\n{srt_ts(s.get('start', 0))} --> {srt_ts(s.get('end', 0))}\n"
                    f"{s.get('text', '')}\n\n")

    base.with_suffix(".json").write_text(json.dumps({
        "title": res.get("title"),
        "uploader": res.get("uploader"),
        "url": res.get("url"),
        "source": res.get("source"),
        "chars": len(text),
        "segments": segs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return base


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="链接、整段分享文案，或本地音视频文件路径")
    ap.add_argument("--level", default="accurate", choices=["speed", "balanced", "accurate"],
                    help="speed=base / balanced=small / accurate=medium(默认)")
    ap.add_argument("--open", action="store_true", help="完成后打开输出文件夹")
    ap.add_argument("--cpu", action="store_true", help="强制用 CPU（默认尝试 GPU）")
    a = ap.parse_args()

    import video_transcribe as vt

    missing = vt.check_deps()
    if missing:
        sys.exit(f"缺依赖：{', '.join(missing)}\n  安装：pip install {' '.join(missing)}")

    if not a.cpu:
        warm_gpu(a.level)

    raw = a.input.strip().strip('"')
    local = Path(raw)
    is_file = local.is_file()

    # 本地文件走 extract_local（不需要下载）；其余一律当链接处理
    if is_file:
        print(f"[本地文件] {local}", flush=True)
        res = vt.extract_local(str(local), level=a.level,
                               progress_cb=lambda s, d="": print(f"  {s} {d}", flush=True))
    else:
        res = vt.extract(raw, level=a.level,
                         progress_cb=lambda s, d="": print(f"  {s} {d}", flush=True))

    if not res.get("ok"):
        if res.get("cancelled"):
            sys.exit("已取消。")
        sys.exit(f"失败：{res.get('error', '未知错误')}")

    base = write_outputs(res)
    chars = len(res.get("transcript") or "")
    print(f"\n完成｜{res.get('title', '')}")
    print(f"  {chars} 字  来源 {res.get('source')}")
    print(f"  原文 -> {base.with_suffix('.txt')}")
    print(f"  字幕 -> {base.with_suffix('.srt')}")
    if a.open:
        os.startfile(str(OUT_DIR))  # noqa: S606


if __name__ == "__main__":
    main()
