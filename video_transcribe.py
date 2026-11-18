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

# ════════════════════ 取消支持（「全部取消」按钮）════════════════════
# server.py 在用户点「全部取消」时把 CANCEL["on"] 置 True：
#   · 听写逐句循环里每句都会检查它 → 几秒内中断（已转进度早已随手落盘，可续传）；
#   · yt-dlp 下载的进度钩子里也会检查它 → 下载中途也能停；
#   · extract()/extract_local() 开跑时会先把它复位，所以取消只影响"当下这一个"任务，
#     之后新提交的任务不受旧取消标记影响。
CANCEL = {"on": False}


class ExtractCancelled(RuntimeError):
    """用户主动取消当前提取任务。"""
    pass


def _check_cancel():
    if CANCEL.get("on"):
        raise ExtractCancelled("已取消")


# ════════════════════ 转写进度续传（断点续传）支持 ════════════════════
# 目标：转写到一半时换代码/关软件，下次打开**从上次的秒数接着转**，不再从 0% 开始。
# 做法：按 URL 建一个持久目录，里面放下载好的音频 + progress.json（已转文字 + 已到秒数）。
#   · 音频持久化 → 重启不必重新下载。
#   · progress.json 边转边存 → 重启时把已转的文字读回来，从 last_end 秒处切片继续转。
#   · 成功完成或彻底失败后，这个目录会被清掉，不留垃圾。
_SR = 16000  # faster-whisper 固定 16k 采样


def _fallback_title(title, transcript):
    """标题兜底：当平台没给标题（抖音解析被拦时常见）时，从文稿首句截一个短标题，
    避免前端显示「(无标题)」。已有非空标题则原样返回。
    取法：拿文稿开头的一段，到第一个句末标点为止，最多 24 个字，干净利落。"""
    t = (title or "").strip()
    if t:
        return t
    body = (transcript or "").strip()
    if not body:
        return ""
    # 把换行和多余空白压平，方便截首句
    flat = re.sub(r"\s+", "", body)
    if not flat:
        return ""
    # 在前 40 个字里找第一个句末标点，作为首句切点
    head = flat[:40]
    m = re.search(r"[。！？!?；;，,、]", head)
    if m and m.start() >= 4:           # 太短（如开头一个语气词）就不在这切
        cut = head[:m.start()]
    else:
        cut = flat[:24]
    cut = cut.strip("，,、。！？!?；; ")
    if not cut:
        return ""
    return cut[:24] + ("…" if len(flat) > len(cut) else "")


def _resume_root():
    root = _models_dir() / "_video_resume"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return root


def _job_dir(url):
    import hashlib
    h = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:16]
    d = _resume_root() / h
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def _find_media(job_dir):
    """返回已下载完整的音频文件路径；只有 .part/.ytdl 半成品则返回 None。"""
    try:
        files = [f for f in glob.glob(os.path.join(str(job_dir), "media.*"))
                 if not f.endswith((".part", ".ytdl", ".tmp"))]
        return files[0] if files else None
    except Exception:
        return None


def _load_progress(job_dir):
    import json as _json
    p = Path(job_dir) / "progress.json"
    if not p.exists():
        return {}
    try:
        return _json.loads(p.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:
        return {}


def _save_progress(job_dir, data):
    import json as _json
    try:
        p = Path(job_dir) / "progress.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(p))
    except Exception:
        pass


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
    gpu = {}
    try:
        import gpu_accel
        gpu = gpu_accel.status()
    except Exception as e:
        gpu = {"summary": "GPU 状态读取失败：%s" % e}
    return {"dir": str(d), "models": found, "gpu": gpu}

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


# ════════════════════ 抖音/TikTok「访客 cookie」自动获取 ════════════════════
# 背景：抖音网页接口现在要求请求里带一个叫 s_v_web_id（配合 ttwid）的「访客标识」
#   cookie，否则接口返回空、yt-dlp 解析 JSON 失败，就报
#   “Fresh cookies (not necessarily logged in) are needed”。
#   这个 cookie **不需要登录**——它是抖音给任何第一次访问网页的访客自动种下的。
# 做法：在调用 yt-dlp 之前，先用 requests 访问一次抖音首页，把服务器 Set-Cookie 下来的
#   访客 cookie（含 ttwid / s_v_web_id 等）抓到，写成一个临时 Netscape cookie 文件，
#   再把这个文件 + 匹配的浏览器 UA 一起交给 yt-dlp。只对抖音/TikTok 链接启用，
#   其它平台（B站/YouTube/快手…）完全不碰，保持原行为。任何一步失败都安静回退。

# 给抖音用的浏览器 UA（要和「拿 cookie 时」用的一致，否则抖音可能不认）
_DOUYIN_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 进程内缓存：(cookie文件路径, 生成时间戳)。抖音访客 cookie 几十分钟内有效，
# 避免每条视频都重新去抓一遍。超过 _DOUYIN_COOKIE_TTL 秒就重新拿。
_douyin_cookie_cache = {"path": None, "ts": 0.0}
_DOUYIN_COOKIE_TTL = 20 * 60  # 20 分钟


def _is_douyin(url):
    """这个链接是不是抖音/TikTok（共用同一套提取器、同样要访客 cookie）。"""
    u = (url or "").lower()
    return any(k in u for k in (
        "douyin.com", "iesdouyin.com", "v.douyin", "tiktok.com"))


# ════════════════════ 代理 / 境外可达性（YouTube 等需要） ════════════════════
# 背景：用户在国内，YouTube 直连会「Connection timed out」。软件设置里已有代理
#   （设置→联网与代理），但视频这条 yt-dlp 链路之前没把代理传进去，所以一直超时。
#   这里统一：① 给 yt-dlp 配代理（仅境外平台，抖音/B站等国内站保持直连）；
#   ② 提取 YouTube 前先探一下代理通不通，不通就早早给用户一句清楚的提示，
#      而不是干等三五十秒超时。

class _SilentLogger:
    """喂给 yt-dlp 的哑日志器：吞掉它往控制台刷的 ERROR/WARNING（比如抖音的
    『Unsupported URL』），避免刷屏。真正成败我们靠异常/文件判断，不靠它打印。"""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _read_proxy():
    """读用户在「设置→联网与代理」里填的代理地址。没配返回空串。"""
    try:
        import web_tools
        return web_tools._read_proxy() or ""
    except Exception:
        return ""


def _is_youtube(url):
    u = (url or "").lower()
    return ("youtube.com" in u) or ("youtu.be" in u)


def _needs_proxy(url):
    """这个平台是不是境外站、需要走代理才能访问。抖音/B站/快手等国内站返回 False。"""
    u = (url or "").lower()
    return any(k in u for k in ("youtube.com", "youtu.be", "tiktok.com",
                                "vimeo.com"))


def _proxy_opts(url):
    """给 yt-dlp 的代理参数：境外站且配了代理才加 {'proxy': ...}；否则空字典（直连）。
    抖音/B站等国内站永远直连，不受代理影响。"""
    if not _needs_proxy(url):
        return {}
    p = _read_proxy()
    return {"proxy": p} if p else {}


def check_foreign_reachable(url, timeout=12):
    """提取境外视频（YouTube 等）前的预检。返回 (ok, message)。
    · 没配代理 → ok=False，提示去设置填代理；
    · 配了代理但连不上境外站 → ok=False，提示连上加速器/检查端口；
    · 能连上 → ok=True。
    只对境外平台做预检；国内平台一律 ok=True，不拦。"""
    if not _needs_proxy(url):
        return True, ""
    p = _read_proxy()
    if not p:
        return (False,
                "提取 YouTube 需要走代理。请先到「设置 → 联网与代理」填上你的加速器"
                "本地地址（如 http://127.0.0.1:7897），连上后再试。")
    # 用配置的代理探一下 YouTube 首页能不能打开
    try:
        import web_tools
        page = web_tools._fetch("https://www.youtube.com/", timeout=timeout, use_proxy=True)
        if (page or "").strip():
            return True, ""
        return (False,
                "代理连上了但没读到 YouTube 内容，换个端口或在加速器里切个节点再试。")
    except Exception as e:
        reason = str(e)
        try:
            import sniffer
            reason = sniffer._humanize_err(e)
        except Exception:
            pass
        return (False,
                "检测不到可用代理 / 上不了外网（%s）。请确认你的加速器（如小麦加速）已连接，"
                "且本地端口和「设置→联网与代理」里填的一致（你的是 7897）。" % reason)


def _write_netscape_cookies(cookies, path):
    """把 {名:值} 写成 yt-dlp 能读的 Netscape cookie 文件。成功返回 True。"""
    try:
        lines = ["# Netscape HTTP Cookie File", ""]
        for name, value in cookies.items():
            if not name or value is None:
                continue
            # domain  include_subdomains  path  secure  expiry  name  value
            lines.append("\t".join([
                ".douyin.com", "TRUE", "/", "FALSE", "0", str(name), str(value)]))
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _fetch_douyin_cookiefile():
    """访问一次抖音，拿到访客 cookie，写成临时 cookie 文件并返回其路径。
    拿不到/出任何问题都返回 None（上层据此回退到不带 cookie 的老方式）。"""
    import time as _time
    # 命中缓存且没过期 → 直接复用
    cached = _douyin_cookie_cache.get("path")
    if cached and Path(cached).exists() \
            and (_time.time() - _douyin_cookie_cache.get("ts", 0)) < _DOUYIN_COOKIE_TTL:
        return cached

    try:
        import requests
    except Exception:
        return None  # 没有 requests 就放弃自动拿 cookie，回退老方式

    headers = {
        "User-Agent": _DOUYIN_UA,
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,*/*;q=0.8"),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    jar = {}
    try:
        sess = requests.Session()
        # 访问抖音首页，让服务器把访客 cookie（ttwid 等）种下来
        sess.get("https://www.douyin.com/", headers=headers, timeout=15)
        # 再访问一次发现页，s_v_web_id 这类前端 cookie 这一步更容易补齐
        try:
            sess.get("https://www.douyin.com/discover", headers=headers, timeout=15)
        except Exception:
            pass
        for c in sess.cookies:
            if c.name and c.value:
                jar[c.name] = c.value
    except Exception:
        return None

    if not jar:
        return None

    # 若服务器没给 s_v_web_id（有时它由前端 JS 生成），就用 ttwid 的常见格式
    # 自己补一个——抖音只校验「这个 cookie 存在且格式像」，不校验是否登录。
    if "s_v_web_id" not in jar:
        try:
            import random
            import string
            rnd = "".join(random.choices(
                string.ascii_letters + string.digits, k=44))
            jar["s_v_web_id"] = "verify_" + rnd.lower()
        except Exception:
            pass

    try:
        fd, tmp_path = tempfile.mkstemp(prefix="dy_cookies_", suffix=".txt")
        os.close(fd)
    except Exception:
        return None

    if not _write_netscape_cookies(jar, tmp_path):
        return None

    # 清掉上一份旧 cookie 文件，缓存新的
    old = _douyin_cookie_cache.get("path")
    if old and old != tmp_path:
        try:
            os.remove(old)
        except Exception:
            pass
    _douyin_cookie_cache["path"] = tmp_path
    _douyin_cookie_cache["ts"] = _time.time()
    return tmp_path


def _apply_douyin_opts(url, opts):
    """若是抖音/TikTok 链接，给 yt-dlp 的 opts 补上访客 cookie 文件 + 匹配 UA。
    返回处理后的 opts（同一个 dict）。非抖音链接原样返回，不做任何改动。"""
    try:
        if not _is_douyin(url):
            return opts
        cookiefile = _fetch_douyin_cookiefile()
        if cookiefile:
            opts["cookiefile"] = cookiefile
        # UA 要和拿 cookie 时一致；http_headers 不覆盖已有的其它头
        hdrs = dict(opts.get("http_headers") or {})
        hdrs.setdefault("User-Agent", _DOUYIN_UA)
        hdrs.setdefault("Referer", "https://www.douyin.com/")
        opts["http_headers"] = hdrs
    except Exception:
        # 出任何问题都不动 opts，保持老行为
        pass
    return opts


# ════════════════════ 抖音/TikTok 提取（yt-dlp 兜底层）═══════════════════════════
# 背景：抖音网页接口现在要一个用 JS 算出来的签名（a_bogus），yt-dlp 给不出来，
#   取回来是空 JSON，就报 “Fresh cookies needed”。带 cookie、装 curl_cffi 模拟指纹
#   都救不了——因为缺的是 JS 签名，不是 cookie。
# 所以**主力**改走另一条路：douyin_resolver 直接解析抖音「分享页」拿无水印直链
#   （在 _download_audio / _download_video 里优先调用，不需要 JS 签名）。
# 这里的 yt-dlp 只作为分享页失败后的**兜底**，且只保留两套安静的方案：
#   1) impersonate（模拟 Chrome 指纹，需要 curl_cffi）+ 自抓访客 cookie
#   2) 只带访客 cookie 文件（= 最早的老行为，不退化）
# 不再尝试「从浏览器读 cookie」：Windows 上基本读不出来还刷一屏报错（见 yt-dlp #10927）。
# 只对抖音/TikTok 启用；其它平台（B站/YouTube/网页…）一律单次执行、完全不碰，保持原样。


def _curl_cffi_available():
    """有没有装 curl_cffi —— 它是 impersonate（模拟浏览器指纹）能用的前提。"""
    try:
        import curl_cffi  # noqa
        return True
    except Exception:
        return False


def _impersonate_value(target="chrome"):
    """生成可传给 yt-dlp opts['impersonate'] 的值。
    新版 yt-dlp 要 ImpersonateTarget 对象；构造不出来就退回字符串，再不行返回 None。"""
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str(target)
    except Exception:
        try:
            # 老一点的版本直接吃字符串
            return target
        except Exception:
            return None


def _douyin_attempts(url, base_opts):
    """yt-dlp 兜底层（分享页直链失败后才用）：给抖音/TikTok 生成几套 opts 尝试方案。
    注意：实测在 Windows 上「从浏览器读 cookie」基本读不出来（Chrome 新版 cookie 用
    DPAPI/应用绑定加密，yt-dlp 解不开；见 yt-dlp #10927），而且每次都刷一屏报错，
    所以这里**不再尝试浏览器 cookie**，只保留 impersonate + 自抓访客 cookie 两种，
    安静、干净，也不比以前差。"""
    have_cc = _curl_cffi_available()

    # 自抓的访客 cookie 文件（拿不到就 None，不影响别的方案）
    try:
        cookiefile = _fetch_douyin_cookiefile()
    except Exception:
        cookiefile = None

    base_hdrs = dict(base_opts.get("http_headers") or {})
    base_hdrs.setdefault("User-Agent", _DOUYIN_UA)
    base_hdrs.setdefault("Referer", "https://www.douyin.com/")

    def mk(**extra):
        o = dict(base_opts)
        o["http_headers"] = dict(base_hdrs)
        # 哑日志：抖音 yt-dlp 兜底失败时本会刷一屏「Unsupported URL」，这里吞掉，
        # 真正成败靠返回值/异常判断。
        o.setdefault("logger", _SilentLogger())
        o.update(extra)
        return o

    imper = _impersonate_value("chrome") if have_cc else None
    attempts = []

    # 1) impersonate + 自抓访客 cookie 文件
    if have_cc and imper is not None:
        o = mk(impersonate=imper)
        if cookiefile:
            o["cookiefile"] = cookiefile
        attempts.append(o)

    # 2) 老办法：只带访客 cookie 文件（最终兜底，等于最早的行为，不退化）
    o = mk()
    if cookiefile:
        o["cookiefile"] = cookiefile
    attempts.append(o)

    return attempts


def _run_extract(url, base_opts, download):
    """统一的 yt-dlp 提取入口。返回 info dict。
    · 抖音/TikTok：走上面的「重试阶梯」，逐个方案试，全失败才抛最后一个错误。
    · 其它平台：单次执行，行为和以前完全一样。
    注：抖音这类「Fresh cookies / 空 JSON」错误都发生在「取信息」阶段、在真正下载之前，
        所以失败的尝试不会留下半成品文件，逐个重试是安全的。"""
    import yt_dlp

    # ★取消支持：真正要下载时，挂一个进度钩子——用户点了「全部取消」，
    #   钩子在下一次进度回调时抛 ExtractCancelled，yt-dlp 会立即中止下载。
    #   （只取信息 download=False 的探测秒级完成，不需要挂）
    if download:
        def _cancel_hook(_d):
            if CANCEL.get("on"):
                raise ExtractCancelled("已取消")
        base_opts = dict(base_opts)
        _hooks = list(base_opts.get("progress_hooks") or [])
        _hooks.append(_cancel_hook)
        base_opts["progress_hooks"] = _hooks

    # ★从最底层堵住「Unsupported URL」：iesdouyin.com/share/video/{id}/?一堆参数
    #   是抖音分享页地址，yt-dlp 不认。统一转成它认识的 douyin.com/video/{id}。
    #   不管上层哪条路径传进来的脏长链，到了这里都会被规范化。
    url = _normalize_ytdlp_url(url)

    if not _is_douyin(url):
        # 非抖音：保持原行为（_apply_douyin_opts 对非抖音是原样返回，等于没动）
        opts = _apply_douyin_opts(url, dict(base_opts))
        # 境外站（YouTube 等）走代理；国内站直连。哑日志避免刷屏。
        opts.update(_proxy_opts(url))
        opts.setdefault("logger", _SilentLogger())
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)

    attempts = _douyin_attempts(url, base_opts)
    last_err = None
    for opts in attempts:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except ExtractCancelled:
            raise          # 用户取消：直接往外抛，不再试下一个方案
        except Exception as e:
            # 抖音这边：任何方案失败都安静退到下一个方案，绝不中途抛错，
            # 这样一定能走到最后那层「老办法」兜底，不会比改之前更差。
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    raise RuntimeError("抖音提取失败（没有可用的提取方案）。")


def _normalize_ytdlp_url(url):
    """把 yt-dlp 不认的抖音分享页长链/短链转成标准 douyin.com/video/{id}。其它链接原样返回。
    关键修复：v.douyin.com/xxx 短链在字符串里看不出 iesdouyin，但 yt-dlp 跟随跳转后会落到
    iesdouyin.com/share/video/{id} → 报 Unsupported URL。所以这里对短链也先用 resolver 解析出
    aweme_id，提前改写成 yt-dlp 认识的标准链接，从源头避免那串刷屏的错误。"""
    try:
        u = (url or "").strip()
        if not u:
            return url
        # ① 长链里直接含 id 的，先抠出来
        if "iesdouyin.com" in u.lower():
            m = re.search(r"/share/video/(\d{6,})", u) or re.search(r"/video/(\d{6,})", u)
            if m:
                return "https://www.douyin.com/video/%s" % m.group(1)
        # ② 抖音短链 / 其它抖音链接：交给 resolver 跟随跳转拿 aweme_id（best-effort）
        low = u.lower()
        if ("v.douyin" in low or "iesdouyin" in low) or \
           ("douyin.com" in low and "/video/" not in low):
            try:
                import douyin_resolver
                aid = douyin_resolver._resolve_id(u)
                if aid:
                    return "https://www.douyin.com/video/%s" % aid
            except Exception:
                pass
        return u
    except Exception:
        return url


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
    # curl_cffi：让 impersonate（模拟真实 Chrome 指纹）可用，抖音提取大幅更稳。
    # gmssl：抖音「作品列表」签名 a_bogus 用得到（列博主作品更稳）；不装也能用，会退回 X-Bogus。
    # yt-dlp 用 --upgrade 升到最新，跟上抖音接口变化。
    pkgs = ["yt-dlp", "faster-whisper", "curl_cffi", "gmssl"]
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


# ════════════════════ 诊断 / 自检 / 版本检查 ════════════════════
# 目标：抖音哪天又坏了，能（1）一键自检知道坏没坏、坏在哪；（2）出错自动把现场
#   存成一个小文件，方便直接发给开发者定位；（3）查 yt-dlp 有没有新版可升。

def _diag_path():
    """诊断文件就放在 backend 目录下，名字固定，方便用户找到后发出来。"""
    return Path(__file__).resolve().parent / "_video_diag.txt"


def write_diag(url, stage, detail):
    """把一次失败的现场写成易读的小文件（覆盖上一份）。任何异常都不抛。"""
    try:
        import platform
        import time as _t
        try:
            import yt_dlp
            vt = yt_dlp.version.__version__
        except Exception:
            vt = "(未装/读不到)"
        try:
            import curl_cffi
            cc = getattr(curl_cffi, "__version__", "?")
        except Exception:
            cc = "(未装)"
        lines = [
            "超能小助 · 视频提取诊断",
            "==============================",
            "时间：%s" % _t.strftime("%Y-%m-%d %H:%M:%S"),
            "链接：%s" % (url or ""),
            "失败阶段：%s" % (stage or ""),
            "yt-dlp 版本：%s" % vt,
            "curl_cffi 版本：%s" % cc,
            "系统：%s" % platform.platform(),
            "",
            "详细错误：",
            str(detail or ""),
        ]
        _diag_path().write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


def read_diag():
    """读回最近一次诊断。返回 {exists, path, text?}。"""
    try:
        p = _diag_path()
        if p.exists():
            return {"exists": True, "path": str(p),
                    "text": p.read_text(encoding="utf-8", errors="replace")}
    except Exception:
        pass
    return {"exists": False, "path": str(_diag_path())}


def clear_diag():
    """删除诊断文件（提取成功后调用，免得旧的失败提示一直挂着）。"""
    try:
        p = _diag_path()
        if p.exists():
            p.unlink()
    except Exception:
        pass


def check_ytdlp_update():
    """查 PyPI 上 yt-dlp 最新版，跟本地装的比。返回 {current, latest, update_available}。
    用标准库联网，超时短；查不到 latest 返回 None（不报错）。"""
    cur = None
    try:
        import yt_dlp
        cur = yt_dlp.version.__version__
    except Exception:
        cur = None
    latest = None
    try:
        import json as _json
        import urllib.request
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"User-Agent": "chaoneng-xiaozhu"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = _json.loads(r.read().decode("utf-8", "replace"))
        latest = ((data.get("info") or {}).get("version")) or None
    except Exception:
        latest = None
    return {"current": cur, "latest": latest,
            "update_available": bool(cur and latest and cur != latest)}


def health():
    """综合自检：抖音链路 + 版本 + yt-dlp 新版 + 诊断文件状态。供前端一次拿全。"""
    out = {}
    try:
        import douyin_resolver
        out["douyin"] = douyin_resolver.health_check()
        out["versions"] = douyin_resolver.versions()
    except Exception as e:
        out["douyin"] = {"status": "error", "detail": "自检模块出错：%s" % e}
        out["versions"] = {}
    try:
        out["ytdlp"] = check_ytdlp_update()
    except Exception:
        out["ytdlp"] = {"current": None, "latest": None, "update_available": False}
    try:
        d = read_diag()
        out["diag"] = {"exists": bool(d.get("exists")), "path": d.get("path")}
    except Exception:
        out["diag"] = {"exists": False, "path": ""}
    return out


def _download_audio(url, outdir):
    """用 yt-dlp / 抖音直链下载音频到 outdir，返回 (文件路径, 标题, 作者, 话题标签列表)。
    话题标签只有抖音分享页直链这条路能顺带拿到；yt-dlp 兜底拿不到就是空列表。"""
    # 进门先规范化：iesdouyin 分享页长链 → 标准抖音链接，避免任何子路径把它喂给
    # yt-dlp 触发 Unsupported URL。
    url = _normalize_ytdlp_url(url)
    # 抖音：先走「分享页直链」这条不需要 JS 签名的路（最稳）。成了就直接用，
    # 拿到的是 mp4，faster-whisper 能直接解出音频。解析/下载失败再回退到 yt-dlp。
    if _is_douyin(url):
        try:
            import douyin_resolver
            dest = os.path.join(outdir, "media.mp4")
            r = douyin_resolver.fetch_to(url, dest)
            if r.get("ok") and os.path.exists(dest) and os.path.getsize(dest) > 2048:
                # ★顺手把抖音话题标签也带回去（之前这里漏带，导致数据库标签不同步）
                return (dest, (r.get("title") or "").strip(),
                        (r.get("uploader") or "").strip(), r.get("tags") or [])
        except Exception:
            pass  # 任何问题都安静回退到下面的 yt-dlp 流程

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
    # 抖音/TikTok：走 impersonate + 访客 cookie 重试阶梯（兜底）。其它平台单次执行、保持原样。
    info = _run_extract(url, opts, download=True)
    files = glob.glob(os.path.join(outdir, "media.*"))
    if not files:
        raise RuntimeError("没下载到媒体文件（可能链接失效或平台限制）。")
    title = (info.get("title") or info.get("description") or "").strip()
    uploader = (info.get("uploader") or info.get("creator") or "").strip()
    return files[0], title, uploader, []


def _find_video(outdir):
    """返回已下载完整的视频文件路径（vid.* 命名），半成品忽略。没有返回 None。"""
    try:
        files = [f for f in glob.glob(os.path.join(str(outdir), "vid.*"))
                 if not f.endswith((".part", ".ytdl", ".tmp"))]
        return files[0] if files else None
    except Exception:
        return None


def _download_video(url, outdir, progress_cb=None):
    """
    截图用：下载**视频画面文件**（只为抓帧，不求高清）。返回 (视频路径, 标题, 作者) 或 None。

    关键取舍——避开 ffmpeg：
      · 优先选「单文件就带画面的渐进式 mp4」（worst[ext=mp4] 等），体积小、下得快，
        而且不需要 ffmpeg 把视频流+音频流合并（合并才依赖 ffmpeg 程序）。
      · 截图只要看得清画面即可，所以挑较小清晰度，省流量省时间。
      · 任何失败都返回 None（让上层照常出文字笔记，只是没图）。
    """
    import yt_dlp
    # 抖音：截图也优先走「分享页直链」。拿到 mp4 直接当画面文件用，抓帧没问题。
    if _is_douyin(url):
        try:
            import douyin_resolver
            dest = os.path.join(outdir, "vid.mp4")
            if progress_cb:
                progress_cb("下载视频画面", "为插图下载视频画面…")
            r = douyin_resolver.fetch_to(url, dest)
            if r.get("ok") and os.path.exists(dest) and os.path.getsize(dest) > 2048:
                return dest, (r.get("title") or "").strip(), (r.get("uploader") or "").strip()
        except Exception:
            pass  # 失败就回退到下面的 yt-dlp 流程
    # 这些 format 都尽量落到「单一渐进式文件」，避免 yt-dlp 触发 ffmpeg 合并：
    #   worst[ext=mp4][vcodec!=none] —— 最小的、带画面的 mp4 单文件
    #   退而求其次给几个兜底，最后 best 也只是尽力，多数平台短视频本就是单文件
    fmt = ("worst[ext=mp4][vcodec!=none]/"
           "worstvideo[ext=mp4]/"
           "best[ext=mp4][vcodec!=none]/best")
    opts = {
        "format": fmt,
        "outtmpl": os.path.join(outdir, "vid.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 3,
        "socket_timeout": 30,
        # 不让 yt-dlp 因找不到 ffmpeg 而报错中断：不加任何 postprocessor
    }
    # 抖音/TikTok：同样走 impersonate + cookie 重试阶梯（截图也要下视频画面）。
    # 其它平台单次执行、保持原样。
    try:
        if progress_cb:
            progress_cb("下载视频画面", "为插图下载视频画面（挑小清晰度，省时间）…")
        info = _run_extract(url, opts, download=True)
        path = _find_video(outdir)
        if not path:
            return None
        title = (info.get("title") or info.get("description") or "").strip()
        uploader = (info.get("uploader") or info.get("creator") or "").strip()
        return path, title, uploader
    except Exception:
        # 下视频失败不致命：返回 None，上层照常出无图笔记
        return None



def _get_model(level, progress_cb=None):
    """取（必要时加载）语音模型。v54：优先用 NVIDIA 显卡（gpu_accel），不行自动退回 CPU。
    缓存里存的是 (模型, 设备)；之前因为 GPU 运行库还没装好而用了 CPU 的，
    等运行库就绪后下次会自动换成 GPU 版本。"""
    import gpu_accel
    size = MODEL_MAP.get(level, "small")
    cached = _model_cache.get(size)
    if cached is not None and not isinstance(cached, tuple):
        cached = (cached, "?")          # 兼容旧写法（命令行工具直接塞模型进来）
        _model_cache[size] = cached
    if cached is not None:
        model, dev = cached
        st = gpu_accel.status()
        upgrade = (dev == "cpu" and st.get("has_nvidia") and st.get("libs_ok")
                   and st.get("gpu_works") is not False
                   and os.environ.get("CX_WHISPER_DEVICE", "").lower() != "cpu")
        if not upgrade:
            return model, dev
        _model_cache.pop(size, None)    # 显卡运行库刚装好 → 丢掉 CPU 版，重新用 GPU 加载
        del model
    model_ref = _resolve_model(size)
    is_local = model_ref != size
    download_root = None
    if not is_local:
        mdir = _models_dir()
        try:
            mdir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        download_root = str(mdir)
    # 自动下载过的模型存在 download_root 下的 models--Systran--faster-whisper-<size> 里，
    # 这种也算「已经下好了」，别再提示「首次使用要下载」
    cached_dl = False
    if download_root:
        try:
            cached_dl = any((Path(download_root) / n).is_dir() for n in (
                f"models--Systran--faster-whisper-{size}",
                f"models--mobiuslabsgmbh--faster-whisper-{size}"))
        except Exception:
            cached_dl = False
    if progress_cb:
        if is_local or cached_dl:
            progress_cb("加载语音模型", f"用本地已下载的 {size} 模型，无需联网")
        else:
            progress_cb("加载语音模型",
                        f"首次使用要下载 {size} 模型到 {_models_dir()}（经国内镜像），"
                        "可能要等几分钟，只这一次")
    model, dev, ct = gpu_accel.load_model(model_ref, download_root=download_root,
                                          progress_cb=progress_cb)
    _model_cache[size] = (model, dev)
    return model, dev


def _drop_gpu_models():
    """GPU 中途出错后，把缓存里的 GPU 模型全部丢掉（下次按 CPU 重新加载）。"""
    for k in list(_model_cache.keys()):
        v = _model_cache.get(k)
        if not isinstance(v, tuple) or v[1] != "cpu":
            _model_cache.pop(k, None)
    try:
        import gc
        gc.collect()
    except Exception:
        pass


def _transcribe(path, level="balanced", progress_cb=None, job_dir=None):
    """语音转文字（入口）。v54：先用显卡；如果显卡中途出错（找不到 CUDA 库 / 显存不够等），
    自动标记显卡不可用、换 CPU 重来。在线任务有断点进度，重来时会从出错前的位置接着转。"""
    import gpu_accel
    try:
        return _transcribe_once(path, level, progress_cb, job_dir)
    except ExtractCancelled:
        raise
    except Exception as e:
        cached = _model_cache.get(MODEL_MAP.get(level, "small"))
        used_gpu = isinstance(cached, tuple) and cached[1] == "cuda"
        if not (used_gpu and gpu_accel.is_gpu_error(e)):
            raise
        gpu_accel.mark_gpu_broken("转写时显卡出错：%s" % str(e)[:200])
        _drop_gpu_models()
        if progress_cb:
            progress_cb("语音转文字", "显卡出错，自动改用 CPU 接着转…")
        return _transcribe_once(path, level, progress_cb, job_dir)


def _transcribe_once(path, level="balanced", progress_cb=None, job_dir=None):
    """用 faster-whisper 把音频转成中文文字。progress_cb(stage, detail) 报告进度。
    若给了 job_dir，则支持断点续传：读回已转文字、从上次的秒数处切片接着转，
    并边转边把进度写进 job_dir/progress.json（换代码/关软件后重启能接着跑）。

    返回 (文字稿, 分段列表)：
      · 文字稿：分好段的整段中文（和以前一样，给 AI 总结用）；
      · 分段列表：[{"start":秒, "end":秒, "text":"这一句"}, ...]，带时间戳，
        给后面的「截图插入 / 跳转原片」用。续传时这份分段也会一起恢复，时间戳连续不串。"""
    size = MODEL_MAP.get(level, "small")
    model, _device = _get_model(level, progress_cb)

    # ── 读回断点续传进度 ──
    # parts：已转的纯文字片段（老逻辑）；seg_list：已转的带时间戳分段（新增，给截图/跳转用）
    parts, offset = [], 0.0
    seg_list = []
    if job_dir is not None:
        prog = _load_progress(job_dir)
        # 只有同一个模型档位的半成品才接着用；档位变了就从头转（音频仍复用、不重下）
        if prog and prog.get("level") == level:
            parts = list(prog.get("parts") or [])
            seg_list = list(prog.get("segments") or [])
            try:
                offset = float(prog.get("last_end") or 0)
            except Exception:
                offset = 0.0

    # ── 尝试用「切片续转」：解码整段音频，从 offset 秒处切片，时间戳整体加 offset ──
    audio_input = path
    total = 0.0
    can_resume = False
    _resume_offset_kept = offset   # 记下从 progress.json 读回的进度，decode 失败时别丢
    try:
        from faster_whisper.audio import decode_audio
        full = decode_audio(path, sampling_rate=_SR)
        total = round(len(full) / _SR, 2)
        can_resume = True
        if offset > 0 and offset < total:
            audio_input = full[int(offset * _SR):]
            if progress_cb:
                pct = min(99, int(offset / total * 100)) if total else 0
                progress_cb("语音转文字",
                            f"接着上次进度继续（已完成 {pct}%，{int(offset)} 秒 / 共 {int(total)} 秒）…")
        else:
            audio_input = full
            offset = 0.0
            parts = []  # offset=0 → 从头转，旧 parts 作废
            seg_list = []  # 同上，旧的带时间戳分段也作废
    except Exception:
        # 没有 decode_audio（或这次解码失败）→ 无法做「切片续转」，但仍要尽量支持续传：
        #   · 让 whisper 直接吃文件，用它自报的段时间戳来存盘（offset=0 从头转）；
        #   · 关键：**不要**抹掉 progress.json 里已读回的进度。decode 可能只是这次偶发
        #     失败，下次启动若能 decode 成功，就还能从 _resume_offset_kept 处接着切片续转。
        #     若这次就从头转完了，收尾存盘会用新的完整结果覆盖，也不冲突。
        audio_input = path
        offset = 0.0
        parts = []
        seg_list = []
        can_resume = True   # 允许按段时间戳存盘（从头转，但中途关软件也能落盘进度）
        if _resume_offset_kept and progress_cb:
            progress_cb("语音转文字",
                        "这次无法从中间切片续转，将从头识别（已转进度仍保留在磁盘上）…")

    if progress_cb and offset == 0:
        progress_cb("语音转文字", "模型就绪（%s），开始逐句识别…"
                    % ("显卡加速" if _device == "cuda" else "CPU"))

    # vad_filter 会跳过静音，能省不少时间；但它让 whisper 上报的时间戳基于「去静音后」
    # 的位置，导致进度百分比相对真实音频忽快忽慢。这里把静音判定阈值调大一点
    # （只把较长的停顿当静音切掉），减少碎片化、让进度更线性，也略微提速。
    segments, info = model.transcribe(
        audio_input, language="zh", vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 800,
                        "speech_pad_ms": 200})
    # ── 进度分母 total：优先用我们自己解码出来的真实音频秒数（最准），
    #    没有再退回 whisper 报告的 duration。这一份是「整段」时长，和下面
    #    加了 offset 的 seg_end 同基准，百分比才不会偏。
    if not total:
        total = getattr(info, "duration", 0) or 0

    n = 0
    last_end = offset
    import time as _t_save
    _last_save_at = _t_save.time()   # 上次存盘时刻，用于按时间间隔落盘

    def _save_guarded(new_last_end, new_parts, new_seg_list):
        """带保护的存盘：只有当『这次要写的进度 new_last_end』不落后于磁盘上
        已有进度时才覆盖。防止 decode 失败、从头重转的场景把磁盘上已有的好进度
        （比如上次已转到 90%）覆盖成更差的（从 0 重转的部分）。"""
        if job_dir is None or not can_resume:
            return
        try:
            existed = _load_progress(job_dir)
            old_end = float(existed.get("last_end") or 0) if existed.get("level") == level else 0.0
        except Exception:
            old_end = 0.0
        # 续传切片场景 new_last_end 本就 ≥ old_end；从头重转时只有追上才覆盖
        if new_last_end + 0.01 >= old_end:
            _save_progress(job_dir, {
                "url": None, "level": level, "total": total,
                "last_end": new_last_end, "parts": new_parts,
                "segments": new_seg_list})

    for seg in segments:
        # ★取消检查：用户点了「全部取消」→ 立刻中断听写。
        #   已识别的进度上面每隔几秒就落盘了一次，下次同一个链接/文件再提取会自动续传。
        _check_cancel()
        t = (seg.text or "").strip()
        seg_start = (getattr(seg, "start", 0) or 0) + offset
        seg_end = (getattr(seg, "end", 0) or 0) + offset
        if t:
            parts.append(t)
            # 记录带时间戳的分段（截图/跳转原片要用）；时间戳已整体加 offset，连续不串
            seg_list.append({
                "start": round(float(seg_start), 2),
                "end": round(float(seg_end), 2),
                "text": t,
            })
        if seg_end > last_end:
            last_end = seg_end
        n += 1
        # 存盘条件放宽：每 6 段 **或** 距上次存盘已过 4 秒就存一次。
        # 原来「固定每 6 段」在「精准档 + 长停顿视频」里，可能很久才攒够 6 段，
        # 期间关软件 → 这一大截没落盘 → 重启又从上次落盘点（甚至 0）开始。
        # 改成按时间兜底后，最多丢约 4 秒的进度。
        _due_by_time = (_t_save.time() - _last_save_at) >= 4
        if n % 6 == 0 or _due_by_time:
            if job_dir is not None and can_resume:
                _save_guarded(last_end, parts, seg_list)
                _last_save_at = _t_save.time()
            if progress_cb:
                # 防御：万一某些段的时间戳超过了估算的 total（vad/续传边界误差），
                # 用 last_end 把分母顶上去，避免出现 “160 秒 / 共 150 秒” 这种倒挂，
                # 也避免百分比卡在某个值不动。
                denom = max(total, last_end) if total else last_end
                if denom:
                    pct = min(99, int(last_end / denom * 100))
                    progress_cb("语音转文字",
                                f"已识别 {pct}%（{int(last_end)} 秒 / 共 {int(denom)} 秒）")
                else:
                    progress_cb("语音转文字", f"已识别到第 {int(last_end)} 秒…")

    # 收尾再存一次（让进度落到接近 100%）。此刻是整段转写完成，last_end 已到末尾，
    # 是最靠后的进度，直接写完整结果（不走保护，确保最终文字稿完整落盘）。
    if job_dir is not None and can_resume:
        _save_progress(job_dir, {
            "url": None, "level": level, "total": total,
            "last_end": total or last_end, "parts": parts,
            "segments": seg_list})
    raw = "".join(parts).strip()
    # 返回 (分好段的文字稿, 带时间戳的分段列表)
    return _paragraphize(raw), seg_list


def _video_file_dir(url):
    """截图用视频文件的存放目录（按 URL 哈希，独立于会被清掉的 job 目录）。
    放在断点根目录下的 _video_frames/<hash>/，worker 抓完帧后由 server.py 清理。"""
    import hashlib
    h = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:16]
    d = _resume_root() / "_video_frames" / h
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def extract(url, level="balanced", progress_cb=None, need_video=False, mode="auto"):
    """
    主流程：解析链接 -> 下载音频 -> 语音识别 -> 返回文字稿。
    progress_cb(stage, detail) 用来实时报告"现在在干什么"。

    need_video=True 时（用户勾了「插图」）：额外下载一份**视频画面文件**用于截图，
    路径放在结果的 "video_path" 里，交给上层抓完帧后自行清理。下视频失败不致命，
    只是这次没图，文字笔记照常产出。

    mode 控制字幕/听写策略：
      · "auto"          —— 有字幕用字幕、没有就听写（默认，省时间）；
      · "subtitle_only" —— 优先字幕；万一拿不到，仍回退听写保证有结果；
      · "transcribe"    —— 跳过字幕，直接下视频听写（字幕可能不全/有错时更准更全）。
    """
    def step(s, d=""):
        if progress_cb:
            progress_cb(s, d)

    # 新任务开跑：复位取消标记（取消只作用于"点取消那一刻正在跑的任务"）
    CANCEL["on"] = False

    raw = (url or "").strip()
    if not raw:
        return {"ok": False, "error": "链接为空。"}
    step("解析链接", "从你粘贴的内容里找出视频地址…")
    url = _find_url(raw)
    # ★总入口规范化：把 iesdouyin 分享页长链转成标准抖音链接，确保下面所有路径
    #   （字幕探测 / 下载音频 / 下载画面 / 爬标题）都用 yt-dlp 认识的地址，
    #   彻底消除 Unsupported URL。
    url = _normalize_ytdlp_url(url)
    if not url.startswith("http"):
        return {"ok": False,
                "error": "没在你粘贴的内容里找到视频链接。请确认里面有 http(s):// 开头的网址。"}

    def _grab_video_for_shots():
        """需要插图时下载视频画面，返回路径或 None（失败/不需要都返回 None）。"""
        if not need_video:
            return None
        try:
            vdir = _video_file_dir(url)
            existing = _find_video(vdir)         # 上次下过就复用，不重下
            if existing:
                return existing
            r = _download_video(url, str(vdir), progress_cb=progress_cb)
            return r[0] if r else None
        except Exception:
            return None

    # ★字幕优先：B 站 / YouTube 很多视频自带字幕，平台 API 几秒就能拿到，
    #   且自带每句时间戳——能拿到就直接用，跳过「下载音频 + 本地听写」，又快又省。
    #   任何异常都安静跳过，回退到原本的听写流程，绝不影响主流程。
    #   mode="transcribe" 时用户明确要听写覆盖，这里整段跳过、直接走下面的听写。
    if mode != "transcribe":
        try:
            import video_subtitle
            step("获取字幕", "先看看这个平台有没有现成字幕（有就免下载、免听写）…")
            sub = video_subtitle.try_fetch_subtitle(url)
            if sub and sub.get("ok") and sub.get("transcript"):
                src_label = ("B站字幕" if sub.get("source") == "bilibili_subtitle"
                             else "YouTube 字幕")
                step("获取字幕", f"已直接拿到{src_label}，跳过下载和听写。")
                # 命中字幕：清掉可能存在的断点目录（这次用不到音频），不留垃圾
                try:
                    shutil.rmtree(str(_job_dir(url)), ignore_errors=True)
                except Exception:
                    pass
                # 即便走了字幕，要插图仍需视频画面 → 单独下一份（失败就没图，不影响笔记）
                video_path = _grab_video_for_shots()
                return {
                    "ok": True,
                    "title": _fallback_title(sub.get("title") or "",
                                             sub["transcript"]),
                    "uploader": sub.get("uploader") or "",
                    "url": url,
                    "transcript": sub["transcript"],
                    "segments": sub.get("segments") or [],
                    "source": sub.get("source"),
                    "video_path": video_path,
                }
        except Exception:
            # 字幕这条路出任何问题，都安静回退到下载+听写
            pass
    else:
        step("视频听写", "按你的选择跳过字幕，直接下载视频听写（更准更全）…")

    missing = check_deps()
    if missing:
        return {"ok": False, "need": missing}
    job = _job_dir(url)
    try:
        media = _find_media(job)
        dy_tags = []   # 抖音话题标签，下面补抓标题时可能填上
        if media:
            # 上次已下载过音频 → 直接复用，不重下（断点续传的关键之一）
            step("下载音频", "发现上次下载的音频，跳过下载，继续转写…")
            title = ""
            uploader = ""
            meta = _load_progress(job)
            title = meta.get("title") or ""
            uploader = meta.get("uploader") or ""
            # 续传时把上次存过的话题标签也恢复回来（下面若仍为空会再补抓一次）
            dy_tags = meta.get("platform_tags") or []
            if not title:
                # 没存过标题就再探一下（不下载，只取信息）；失败也无所谓
                try:
                    _probe_opts = {"quiet": True, "no_warnings": True,
                                   "noplaylist": True, "skip_download": True,
                                   "nocheckcertificate": True}
                    info = _run_extract(url, _probe_opts, download=False)
                    title = (info.get("title") or info.get("description") or "").strip()
                    uploader = (info.get("uploader") or info.get("creator") or "").strip()
                except Exception:
                    pass
        else:
            step("下载音频", "正在从平台下载视频的音频…")
            _check_cancel()   # 下载开始前看一眼是否已被取消
            media, title, uploader, _dl_tags = _download_audio(url, str(job))
            step("下载音频", f"下载完成：{(title or '')[:30]}")
            # 下载这步若已顺带拿到抖音话题标签，先收下（这是最常见、最可靠的来源）
            if _dl_tags:
                dy_tags = list(_dl_tags)

        # ★抖音元信息补抓：把视频的「真正标题 + 作者 + 话题标签」补齐。
        #   注意：话题标签的补抓**不再绑定在「标题缺失」这个条件上**——
        #   以前只有 title/uploader 缺了才会去 fetch_meta，可视频自带标题（desc）时
        #   就跳过了，于是 dy_tags 一直是空、数据库里的标签同步不到抖音话题。
        #   现在：只要标签还没拿到，就单独补抓一次标签；标题/作者缺了也顺带补。
        if _is_douyin(url):
            # ① 先走抖音分享页/接口解析（最稳，desc 就是抖音原标题，text_extra 即话题）
            try:
                import douyin_resolver
                if (not title) or (not uploader) or (not dy_tags):
                    step("获取标题", "正在抓取抖音视频的标题和话题…")
                    meta = douyin_resolver.fetch_meta(url)
                    if meta.get("ok"):
                        if not title:
                            title = (meta.get("title") or "").strip()
                        if not uploader:
                            uploader = (meta.get("uploader") or "").strip()
                        if not dy_tags:
                            dy_tags = meta.get("tags") or []
            except Exception:
                pass
            # ② 分享页没拿到标题 → 用 yt-dlp 兜底取（URL 已在 _run_extract 里规范化，
            #    不会再 Unsupported）。yt-dlp 的 title 也是抖音原标题。
            if not title:
                try:
                    step("获取标题", "用备用方式抓取抖音原标题…")
                    _pi = _run_extract(url, {
                        "quiet": True, "no_warnings": True, "noplaylist": True,
                        "skip_download": True, "nocheckcertificate": True},
                        download=False)
                    title = (_pi.get("title") or _pi.get("description") or "").strip()
                    if not uploader:
                        uploader = (_pi.get("uploader") or _pi.get("creator") or "").strip()
                except Exception:
                    pass

        # 把标题/作者/话题标签也记进进度文件，方便续传时直接用（保留已转的 parts/last_end）
        prog = _load_progress(job)
        prog.update({"url": url, "title": title, "uploader": uploader,
                     "platform_tags": dy_tags})
        _save_progress(job, prog)

        # 要插图：在听写之前/之后下一份视频画面（独立目录，不会被 job 清理误删）
        video_path = _grab_video_for_shots()

        # _transcribe 现在返回 (文字稿, 带时间戳的分段列表)
        _check_cancel()   # 听写开始前再看一眼是否已被取消
        transcript, segments = _transcribe(
            media, level, progress_cb=progress_cb, job_dir=job)

        if not transcript:
            shutil.rmtree(str(job), ignore_errors=True)  # 没识别出东西，清掉别占地方
            return {"ok": False,
                    "error": "下载成功但没识别出文字（可能是纯音乐/无人声，或音频太短）。"}
        # ★成功：清掉断点目录（音频 + 进度），不留垃圾
        shutil.rmtree(str(job), ignore_errors=True)
        # 成功了就清掉上一次的诊断文件，免得"上次失败"的提示一直挂着
        try:
            clear_diag()
        except Exception:
            pass
        return {"ok": True, "title": _fallback_title(title, transcript),
                "uploader": uploader,
                "url": url, "transcript": transcript,
                "segments": segments, "source": "local_whisper",
                "video_path": video_path, "platform_tags": dy_tags}
    except ExtractCancelled:
        # 用户主动取消：不算失败、不写诊断。job 目录（音频 + 已转进度）保留，
        # 下次同一个链接再提取会自动续传，前面识别的功夫不白费。
        return {"ok": False, "cancelled": True, "error": "已取消"}
    except Exception as e:
        # 注意：这里**不删** job 目录——很可能是被中途打断/出错，
        # 保留音频和已转进度，下次打开能接着转。只有彻底识别不出/成功才清理。
        msg = _clean_err(e)
        # 抖音「Fresh cookies」这类错误：多半是 yt-dlp 版本旧、跟不上抖音接口变化。
        # 给一句能直接照做的提示（已自动带访客 cookie，仍失败基本就是版本问题）。
        low = msg.lower()
        if _is_douyin(url) and ("fresh cookies" in low
                                or "render data" in low
                                or "parse json" in low
                                or "无法" in msg):
            tip = ("\n\n提示：本软件已先尝试「抖音分享页直链解析」、再用 yt-dlp 兜底，仍未成功。"
                   "通常是这条视频被限制、链接已过期，或抖音又改了分享页结构。可以：\n"
                   "  1) 回抖音客户端重新「分享 → 复制链接」，拿一条最新短链再试；\n"
                   "  2) 在「视频」板块点一次「安装/更新依赖」把 yt-dlp 升到最新；\n"
                   "  3) 换一条抖音视频试试，确认是不是这条本身的问题。")
            msg += tip
        # 不管哪个平台，失败都留一份诊断现场，方便用户发给开发者定位
        try:
            write_diag(url, "extract", msg)
        except Exception:
            pass
        return {"ok": False, "error": f"提取失败：{msg}"}

# ════════════════════ 本地文件提取（导入本地音/视频文件）════════════════════════
# 背景：原本只支持「粘贴链接 → yt-dlp 下载 → 听写」。这里新增本地文件直转：
#   用户从电脑里选好一个音频/视频文件，跳过「找链接 + 下载」两步，
#   直接把这个文件喂给 faster-whisper 听写。
# 关键点：faster_whisper 的 decode_audio() 内部用 PyAV(ffmpeg) 解码，
#   能直接读 mp4/mov/mkv/avi/flv/m4a/mp3/wav/aac… 几乎所有常见音视频格式，
#   所以本地文件**不需要 yt-dlp，也不需要单独下载**，只要装了 faster-whisper 即可。

# 常见可处理的本地音/视频后缀（仅用于前端友好提示与基本校验，不是硬限制）
LOCAL_MEDIA_EXTS = (
    ".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".wmv", ".m4v", ".ts",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".amr",
)


def check_deps_local():
    """本地文件提取只需要 faster-whisper（解码靠它内置的 ffmpeg/PyAV）。
    返回缺失列表（空=就绪）。不要求 yt-dlp。"""
    missing = []
    try:
        import faster_whisper  # noqa
    except Exception:
        missing.append("faster-whisper")
    return missing


def extract_local(file_path, level="balanced", progress_cb=None):
    """把本地音/视频文件直接听写成文字稿。
    跳过链接解析与下载，直接走 faster-whisper。

    返回结构与 extract() 完全一致（ok/title/uploader/url/transcript/segments/source…），
    这样上层 worker 的后续处理（AI 分析、存笔记、插图）可以原样复用。
    标题默认用文件名（不含扩展名），交给 AI 分析时若识别出更好的标题会覆盖。"""
    def step(s, d=""):
        if progress_cb:
            progress_cb(s, d)

    p = (file_path or "").strip().strip('"').strip("'")
    if not p:
        return {"ok": False, "error": "没有提供文件路径。"}
    if not os.path.exists(p):
        return {"ok": False, "error": f"找不到这个文件（可能被移动或删除了）：{p}"}
    if not os.path.isfile(p):
        return {"ok": False, "error": f"这不是一个文件：{p}"}

    ext = os.path.splitext(p)[1].lower()
    if ext and ext not in LOCAL_MEDIA_EXTS:
        # 不是已知音视频后缀也允许试（ffmpeg 可能照样能解），但先给个提示日志
        step("解析文件", f"后缀 {ext} 不在常见音视频列表里，仍尝试解码…")

    missing = check_deps_local()
    if missing:
        return {"ok": False, "need": missing}

    base = os.path.basename(p)
    title = os.path.splitext(base)[0] or "本地文件"

    step("读取文件", f"准备听写本地文件：{base[:40]}")
    # 新任务开跑：复位取消标记（取消只作用于"点取消那一刻正在跑的任务"）
    CANCEL["on"] = False
    try:
        # 本地文件没有断点续传目录（不像在线任务按 url 建 job 目录），
        # 直接整段听写即可；文件通常已在本地，重跑成本低。
        transcript, segments = _transcribe(
            p, level, progress_cb=progress_cb, job_dir=None)
        if not transcript:
            return {"ok": False,
                    "error": "文件读到了，但没识别出文字（可能是纯音乐/无人声，或时长太短）。"}
        try:
            clear_diag()
        except Exception:
            pass
        return {
            "ok": True,
            "title": _fallback_title(title, transcript),
            "uploader": "",
            "url": "（本地文件）" + base,   # 笔记里「来源链接」一栏显示文件名，便于追溯
            "transcript": transcript,
            "segments": segments,
            "source": "local_file",
            "video_path": p,               # 本地文件本身即可用于截图（插图功能复用）
            "platform_tags": [],
            "local_path": p,
        }
    except ExtractCancelled:
        # 用户主动取消：不算失败、不写诊断（本地文件重跑成本低，无需续传）
        return {"ok": False, "cancelled": True, "error": "已取消"}
    except Exception as e:
        msg = _clean_err(e)
        try:
            write_diag(p, "extract_local", msg)
        except Exception:
            pass
        return {"ok": False, "error": f"本地文件提取失败：{msg}"}
