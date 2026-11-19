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


def warm_gpu(level: str) -> None:
    """v54：App 本身已经默认走显卡（gpu_accel），这里只是提前加载模型并打印用的设备。"""
    import video_transcribe as vt
    import gpu_accel

    if gpu_accel.detect():
        print("[GPU] 检测到显卡：%s，准备 CUDA 运行库…" % gpu_accel.status().get("gpu_name"), flush=True)
    _model, dev = vt._get_model(level, lambda st, d: print(f"[{st}] {d}", flush=True))
    if dev == "cuda":
        print("[GPU] 模型已用显卡加载（%s）" % gpu_accel.status().get("compute_type"), flush=True)
    else:
        print("[!] 本次用 CPU：%s" % (gpu_accel.status().get("reason") or "无可用显卡"), flush=True)


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
    ap.add_argument("--level", default="accurate", choices=["speed", "balanced", "accurate", "ultra"],
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
