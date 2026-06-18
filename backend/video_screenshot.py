"""
video_screenshot.py — 给视频笔记「插图」+「跳转原片」

做两件事（都不依赖 ffmpeg 外部程序，沿用超能小助"免装 ffmpeg"的原则）：

1. 插图（截图）：
   AI 总结时会在合适的地方插入标记 `*Screenshot-[mm:ss]`。这里把每个标记解析出
   时间点，去**已下载的视频文件**里抓那一帧，存成 jpg，再把标记替换成图片引用
   `![](图片地址)`。抓帧优先用 PyAV（faster-whisper 自带的 av，无需 ffmpeg 程序），
   PyAV 不行再退 OpenCV（你已装 opencv-python），都不行就把标记安静删掉、不影响笔记。

2. 跳转原片：
   AI 也会插入 `*Content-[mm:ss]` 标记。这里把它替换成「[原片 @ mm:ss](带时间戳的链接)」，
   点一下跳到原视频对应时间。支持 B站 / YouTube / 抖音。

设计：所有函数都 try 包裹、失败安静降级，绝不让插图这步把整条笔记搞崩。
图片存到 MEMORY_DIR/video_notes/shots/<任务标识>/，由 server.py 起 HTTP 地址给前端显示。
"""

import re
import os
import uuid
from pathlib import Path


# ──────────────────────────── 标记解析 ────────────────────────────

def extract_screenshot_markers(markdown):
    """找出所有 Screenshot 标记，返回 [(原始标记文本, 秒数), ...]。
    兼容 *Screenshot-[mm:ss]、Screenshot-[mm:ss]、*Screenshot-mm:ss、Screenshot-mm:ss。"""
    pattern = r"(\*?Screenshot-(?:\[(\d{1,2}):(\d{2})\]|(\d{1,2}):(\d{2})))"
    out = []
    for m in re.finditer(pattern, markdown or ""):
        mm = m.group(2) or m.group(4)
        ss = m.group(3) or m.group(5)
        try:
            total = int(mm) * 60 + int(ss)
        except Exception:
            continue
        out.append((m.group(1), total))
    return out


# ──────────────────────────── 抽帧（免 ffmpeg）────────────────────────────

def _grab_frame_pyav(video_path, second, out_path):
    """用 PyAV 跳到 second 秒抓一帧存 jpg。成功返回 True。
    PyAV 来自 faster-whisper 依赖的 av，自带解码器，不需要系统 ffmpeg。"""
    try:
        import av
    except Exception:
        return False
    try:
        container = av.open(str(video_path))
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None:
            container.close()
            return False
        # seek 到目标时间（PyAV 用 stream.time_base 的时间戳）
        try:
            ts = int(second / stream.time_base)
            container.seek(ts, stream=stream, any_frame=False, backward=True)
        except Exception:
            pass  # seek 失败就从头解，慢但能出图
        target = None
        for frame in container.decode(stream):
            ft = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
            target = frame
            if ft >= second:
                break
        container.close()
        if target is None:
            return False
        img = target.to_image()  # PIL.Image
        img.save(str(out_path), "JPEG", quality=88)
        return True
    except Exception:
        try:
            container.close()
        except Exception:
            pass
        return False


def _grab_frame_opencv(video_path, second, out_path):
    """退路：用 OpenCV 抓帧（你已装 opencv-python）。成功返回 True。"""
    try:
        import cv2
    except Exception:
        return False
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return False
        cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            # 再试一次：按帧号定位
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(second * fps))
            ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return False
        cv2.imwrite(str(out_path), frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return True
    except Exception:
        return False


def grab_frame(video_path, second, out_path):
    """抓一帧：先 PyAV（免 ffmpeg），不行退 OpenCV。两者都失败返回 False。"""
    if _grab_frame_pyav(video_path, second, out_path):
        return True
    return _grab_frame_opencv(video_path, second, out_path)


def screenshot_available():
    """当前环境能不能抓帧（PyAV 或 OpenCV 至少有一个）。给前端/提示用。"""
    try:
        import av  # noqa
        return True
    except Exception:
        pass
    try:
        import cv2  # noqa
        return True
    except Exception:
        return False


# ──────────────────────────── 插图：标记 → 图片 ────────────────────────────

def insert_screenshots(markdown, video_path, shots_dir, image_url_base):
    """
    把 markdown 里的 Screenshot 标记替换成真实截图的图片引用。

    :param markdown:       含标记的笔记文本
    :param video_path:     已下载的视频文件路径（没有就直接清掉标记）
    :param shots_dir:      存截图的本地目录（Path）
    :param image_url_base: 前端访问图片的 URL 前缀，如 "http://127.0.0.1:8756/video_shot?f="
                           最终图片地址 = image_url_base + 文件名
    :return: (替换后的 markdown, 生成的图片文件名列表)
    """
    markers = extract_screenshot_markers(markdown)
    if not markers:
        return markdown, []

    saved = []
    if not video_path or not Path(video_path).exists():
        # 没视频文件（比如走了字幕、或下载失败）→ 安静删掉标记，不留半截记号
        for marker, _sec in markers:
            markdown = markdown.replace(marker, "", 1)
        return markdown, saved

    try:
        Path(shots_dir).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    for idx, (marker, sec) in enumerate(markers):
        try:
            fname = "shot_%03d_%s.jpg" % (idx, uuid.uuid4().hex[:8])
            out_path = Path(shots_dir) / fname
            if grab_frame(video_path, sec, out_path):
                img_url = image_url_base + fname
                # 替换成图片；保留时间小标注，方便对照原片
                mm, ss = sec // 60, sec % 60
                repl = "\n\n![截图 %02d:%02d](%s)\n\n" % (mm, ss, img_url)
                markdown = markdown.replace(marker, repl, 1)
                saved.append(fname)
            else:
                markdown = markdown.replace(marker, "", 1)  # 抓不到就删标记
        except Exception:
            markdown = markdown.replace(marker, "", 1)
    return markdown, saved


# ──────────────────────────── 跳转原片：标记 → 链接 ────────────────────────────

def _detect_platform_and_id(url):
    """从链接判断平台 + 提取视频 id（跳转链接要用）。返回 (platform, video_id)。"""
    u = (url or "")
    low = u.lower()
    if "bilibili.com" in low or "b23.tv" in low or "bvid=" in low or "/bv" in low:
        m = re.search(r"(BV[0-9A-Za-z]+)", u)
        return "bilibili", (m.group(1) if m else "")
    if "youtube.com" in low or "youtu.be" in low:
        m = re.search(r"(?:v=|youtu\.be/)([0-9A-Za-z_-]{11})", u)
        return "youtube", (m.group(1) if m else "")
    if "douyin.com" in low:
        m = re.search(r"/video/(\d+)", u)
        return "douyin", (m.group(1) if m else "")
    return "", ""


def replace_content_markers(markdown, url):
    """
    把 *Content-[mm:ss] / Content-[mm:ss] / Content-mm:ss 替换成「跳转原片对应时间」的链接。
    认不出平台或没 id 时，退化成纯时间文字 (mm:ss)，不留奇怪标记。
    """
    platform, vid = _detect_platform_and_id(url)
    pattern = r"(?:\*?)Content-(?:\[(\d{1,2}):(\d{2})\]|(\d{1,2}):(\d{2}))"

    def repl(m):
        mm = m.group(1) or m.group(3)
        ss = m.group(2) or m.group(4)
        try:
            total = int(mm) * 60 + int(ss)
        except Exception:
            return "(%s:%s)" % (mm, ss)
        if platform == "bilibili" and vid:
            link = "https://www.bilibili.com/video/%s?t=%d" % (vid, total)
        elif platform == "youtube" and vid:
            link = "https://www.youtube.com/watch?v=%s&t=%ds" % (vid, total)
        elif platform == "douyin" and vid:
            link = "https://www.douyin.com/video/%s" % vid
        else:
            return "(%s:%s)" % (mm, ss)
        return "[原片 @ %s:%s](%s)" % (mm, ss, link)

    return re.sub(pattern, repl, markdown or "")


# ──────────────────────────── 总入口 ────────────────────────────

def post_process(markdown, *, url, video_path=None, shots_dir=None,
                 image_url_base="", do_screenshot=False, do_link=False):
    """
    笔记生成后的统一后处理：按开关插图 / 加跳转链接。
    任何一步失败都安静跳过，返回当前 markdown，绝不抛。

    :return: (处理后的 markdown, 生成的截图文件名列表)
    """
    saved = []
    md = markdown or ""
    if do_screenshot:
        try:
            md, saved = insert_screenshots(md, video_path, shots_dir, image_url_base)
        except Exception:
            # 出错就把残留的 Screenshot 标记清掉，别留半截
            try:
                for marker, _ in extract_screenshot_markers(md):
                    md = md.replace(marker, "", 1)
            except Exception:
                pass
    else:
        # 没开插图：把可能误生成的 Screenshot 标记清掉
        try:
            for marker, _ in extract_screenshot_markers(md):
                md = md.replace(marker, "", 1)
        except Exception:
            pass

    if do_link:
        try:
            md = replace_content_markers(md, url)
        except Exception:
            pass
    else:
        # 没开跳转：把可能误生成的 Content 标记清掉（替换成纯时间）
        try:
            md = replace_content_markers(md, "")  # 无 url → 退化成 (mm:ss)
        except Exception:
            pass
    return md, saved
