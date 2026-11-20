"""
server.py — 本地 HTTP 服务，把 Electron 窗口和 Python agent 连起来

只监听 127.0.0.1（本机），不对外网开放，数据不出本机。
用标准库 http.server，不引入额外 web 框架，依赖越少越安全。

接口：
  POST /chat      {messages:[...], use_local, model, shell_enabled} -> {reply, tool_calls}
  POST /heartbeat {use_local, model}                                -> {reply}
  GET  /memory?name=SOUL.md                                         -> {content}
  POST /memory    {name, content}                                  -> {ok}
  GET  /memory/list                                                 -> {files}
  GET  /ping                                                        -> {ok:true}
"""

import json
import os
import re

# ★ 软件不跟随系统代理（Clash 等的「系统代理」）：requests / httpx / curl / yt-dlp 默认都会读系统代理，
#   这里统一关掉；需要代理的地方（境外站）由代码显式传入「设置 → 联网与代理」里的地址（智能局部代理）。
try:
    import web_tools as _wt_proxy
    _wt_proxy.apply_proxy_env(force=True)   # 境外站走「设置」里的代理、国内站和本机直连
except Exception:
    pass
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# —— 解决 Windows 控制台中文乱码 ——
# main.js 用 stdio:"inherit"，Python 直接写控制台；中文版 Windows 控制台默认 GBK(936)，
# 而 Python 默认输出 UTF-8 → 乱码。这里把控制台切到 UTF-8(65001) 并让 stdout 用 UTF-8，两边对齐。
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass
try:
    if _sys.platform == "win32":
        import ctypes as _ctypes
        _ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass

# v55：黑窗口里打印的每一行，同时存一份在内存里，软件里的「终端」面板通过 /logs 读
try:
    import log_capture as _log_capture
    _log_capture.install()
except Exception:
    _log_capture = None

import agent_core as core
try:
    import chat_progress as cp
except Exception:
    cp = None  # 进度模块缺失也不影响对话本身

HOST = "127.0.0.1"
PORT = 8756  # 一个不常用的端口，避免和别的程序撞

# ════════════════════ 控制台操作日志 ════════════════════
# 之前控制台太安静（log_message 被置空、各处也很少 print），用户在界面上操作时
# 看不到任何反馈，会以为软件卡死/没工作。这里加一个统一的日志函数：
#   · 带时间戳 + 统一前缀，和现有的 [video]/[backend] 风格一致；
#   · line_buffering 已开（见上面 reconfigure），flush=True 双保险，实时可见；
#   · 出错绝不影响主流程（打印日志本身不该让请求失败）。
import time as _time_log


def _clog(tag, msg):
    """往控制台打一行带时间戳的日志。tag 如 'video'/'chat'/'api'，msg 是人话描述。"""
    try:
        ts = _time_log.strftime("%H:%M:%S")
        print("[%s] %s  %s" % (ts, tag, msg), flush=True)
    except Exception:
        pass


# 这些接口是前端**定时高频轮询**或页面加载时被动拉取的（查状态/进度/列表/配置），
# 一旦打印就会把控制台刷爆、淹没真正有用的操作日志，所以一律静音、不记。
_LOG_QUIET_PATHS = {"/intake_kind", 
    "/ping", "/video_note_subs", "/x_note_rebuild_status", "/video_failed", "/video_note_tidy_status", "/phone_inbox/status", "/feishu_inbox/status", "/feishu_inbox/alive", "/feishu_inbox/incoming", "/video_progress", "/video_health", "/video_deps", "/video_notes", "/creator_profiles_batch", "/creator/avatars_status", "/creator/discover",
    "/video_note_analyze_progress", "/sniff/feed", "/sniff/discover", "/video_note_analyze_batch",
    "/chat_progress", "/heartbeat/status", "/lumi/status", "/lumi/evolve_status",
    "/web_model/state", "/web_model/config", "/loop/status", "/insight/status",
    "/insight/config", "/system_access", "/claude_config", "/harness/config",
    "/sniff/config", "/skills/list", "/agents/list", "/agents/convos", "/agents/notifications", "/datadb/list", "/memory/list",
    "/creator/list", "/creator/findings", "/creator/videos_cached",
    "/creator/x_cookie_status",
    "/logs", "/ai_live", "/ai_live_shot", "/version", "/gpu_status", "/creator_profiles", "/creator_avatar",
    "/scrapling/status", "/sniff/sources",
}

# 给少数关键路径配一句「人话」描述，让日志一眼能看懂用户在干嘛。
# 没列到的路径会回退显示原始 path，也能看，只是不那么直白。
_LOG_PATH_LABEL = {
    "/video_transcribe": "发起视频提取",
    "/video_cancel": "取消视频任务",
    "/video_detect_subtitle": "检测视频字幕",
    "/video_diag": "查看视频诊断",
    "/video_install": "安装/更新视频依赖",
    "/video_move_models": "迁移语音模型",
    "/video_note_delete": "删除视频笔记",
    "/video_note_analyze": "补做笔记 AI 分析",
    "/video_note_analyze_stop": "停止补做 AI 分析",
    "/video_note_set_author": "修改笔记作者",
    "/video_folder": "视频笔记文件夹操作",
    "/creator_merge": "合并 / 拆开博主",
    "/video_shot": "抓取视频截图",
    "/chat": "发送对话消息",
    "/tts": "语音播报",
    "/memory": "读写记忆文件",
    "/heartbeat": "触发一次心跳",
    "/heartbeat/start": "开启自动心跳",
    "/heartbeat/stop": "关闭自动心跳",
    "/briefing": "生成情报简报",
    "/competitors": "检查竞品变化",
    "/loop/start": "启动目标循环",
    "/loop/stop": "停止目标循环",
    "/insight/run": "运行洞察爬取",
    "/insight/stop": "停止洞察爬取",
    "/insight/research_item": "深入研究某条洞察",
}


def _log_request(method, path):
    """记录一次「用户操作」到控制台。高频轮询路径自动跳过。"""
    try:
        if path in _LOG_QUIET_PATHS:
            return
        label = _LOG_PATH_LABEL.get(path)
        if label:
            _clog("操作", "%s （%s %s）" % (label, method, path))
        else:
            _clog("操作", "%s %s" % (method, path))
    except Exception:
        pass


_tg_started = False  # Telegram bot 是否已启动（避免重复启动）

# 视频提取：支持排队。前端轮询 /video_progress 看进度+队列。
import threading as _threading
_video_q = []                       # 待处理队列：[{id, url, level, use_local, model}]
_video_lock = _threading.Lock()
_video_worker_on = {"v": False}
_video_state = {"running": False, "stage": "", "detail": "", "elapsed": 0,
                "queue_len": 0, "result": None, "result_id": 0, "current_url": "",
                "current_label": "", "queue": []}
_video_current = {"job": None}      # 当前正在处理的任务（崩溃恢复用）
_video_cancel = {"all": False}      # 取消标记：worker 在阶段间检查，True 则放弃当前并清空队列


def _video_queue_path():
    """持久化队列文件：软件关掉/崩溃后重启能接着跑。"""
    import agent_core
    return agent_core.MEMORY_DIR / "video_queue.json"


def _save_video_queue():
    """把「正在处理的任务 + 待处理队列」原子写盘。须在持锁状态下调用。"""
    import json as _json, os as _os
    try:
        cur = _video_current.get("job")
        data = {"current": cur, "pending": list(_video_q)}
        p = _video_queue_path()
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(_json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        _os.replace(str(tmp), str(p))   # 原子替换，避免写一半被读到
    except Exception:
        pass


def _load_video_queue():
    """读回持久化的队列。返回 [job, ...]：current（若有）排最前，再接 pending。
    加载时顺手把每个 job 的 URL 规范化——历史持久化里可能存了 iesdouyin 分享页
    长链（yt-dlp 报 Unsupported URL），在这里转成标准抖音链接，从源头根除。"""
    import json as _json
    try:
        p = _video_queue_path()
        if not p.exists():
            return []
        data = _json.loads(p.read_text(encoding="utf-8", errors="replace")) or {}
        jobs = []
        cur = data.get("current")
        if cur and cur.get("url"):
            cur["url"] = _normalize_video_url(cur.get("url"))
            if "iesdouyin.com/share" not in (cur.get("url") or ""):  # 规范化没成功的畸形链接直接丢
                jobs.append(cur)
        for j in (data.get("pending") or []):
            if j and j.get("url"):
                j["url"] = _normalize_video_url(j.get("url"))
                if "iesdouyin.com/share" not in (j.get("url") or ""):
                    jobs.append(j)
        return jobs
    except Exception:
        return []

# 对话里触发的视频提取任务，登记在中立模块 video_queue_state 里
# （必须用同一个模块对象，不能 import server，否则 __main__ 双重加载会拿到两份状态）。
import video_queue_state as _cvq


def _chat_video_snapshot():
    """把对话视频任务整理成 /video_progress 能直接用的片段。"""
    return _cvq.snapshot()


def _cx_video_dir():
    import agent_core
    d = agent_core.MEMORY_DIR / "video_notes"
    d.mkdir(exist_ok=True)
    return d


def _cx_segments_dir():
    """「仅提取文字稿」笔记的时间戳分段侧车目录：video_notes/segments/。
    每条未分析笔记存一个 <笔记名>.json（含 segments/url/是否要跳转原片），
    等以后补做 AI 分析时用它打「跳转原片」时间标记，补完即删。"""
    d = _cx_video_dir() / "segments"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def _cx_shots_dir():
    """视频笔记截图的根目录：video_notes/shots/。每条笔记一个子目录（按笔记名）。"""
    d = _cx_video_dir() / "shots"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


# ════════════════ 视频笔记「文件夹」（虚拟分组）════════════════
# 用户可以建文件夹，把同一作者/同一主题的笔记归到一起。
# 笔记文件本身仍然平铺在 video_notes/ 里不动，分组关系单独存
# video_notes/_folders.json：{"folders":[名字…], "map":{笔记文件名: 文件夹名}}。
# 好处：列表/打开/删除/截图等所有按文件名找笔记的逻辑都不用动，分组坏了也不伤笔记。
_vn_lock = _threading.Lock()


def _vn_folders_path():
    return _cx_video_dir() / "_folders.json"


def _vn_load_folders():
    """读分组表 → (文件夹名列表, {笔记文件名: 文件夹名})。文件不存在/坏了就当空。"""
    try:
        d = json.loads(_vn_folders_path().read_text(
            encoding="utf-8", errors="replace"))
        folders = [str(f).strip() for f in (d.get("folders") or [])
                   if str(f).strip()]
        mapping = {str(k): str(v) for k, v in (d.get("map") or {}).items()}
        return folders, mapping
    except Exception:
        return [], {}


def _vn_save_folders(folders, mapping):
    try:
        _vn_folders_path().write_text(
            json.dumps({"folders": folders, "map": mapping}, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def _vn_ok_folder_name(name):
    """文件夹名合法性：非空、不超过 30 字、不含路径字符。合法返回清理后的名字，否则空串。"""
    name = (name or "").strip()
    if not name or len(name) > 30:
        return ""
    if ("/" in name) or ("\\" in name) or (".." in name):
        return ""
    return name


def _vn_assign_folder(note_name, folder):
    """把一条笔记归进某个文件夹（文件夹不存在就顺手创建）。folder 为空 = 移出分组。"""
    with _vn_lock:
        folders, mapping = _vn_load_folders()
        folder = _vn_ok_folder_name(folder)
        if folder:
            if folder not in folders:
                folders.append(folder)
            mapping[note_name] = folder
        else:
            mapping.pop(note_name, None)
        _vn_save_folders(folders, mapping)


def _vn_set_note_author(note_name, author):
    """v59：把笔记 md 里的「- 作者：」改成 author（本地文件没作者，填了博主主页后用博主昵称补上）。"""
    try:
        p = _cx_video_dir() / note_name
        lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
        for i in range(1, min(14, len(lines))):
            t = lines[i].strip().lstrip("-").strip()
            if t.startswith("作者：") or t.startswith("作者:"):
                lines[i] = "- 作者：" + author
                p.write_text("\n".join(lines), encoding="utf-8")
                return True
    except Exception:
        pass
    return False


def _vn_note_index():
    """v60：把所有笔记的「来源链接 / 作者 / 所在文件夹」读一遍（新的在前）。批量找主页时只读一次。
    作者的认法和笔记列表一样（第一条「作者：」，最多 40 字，纯数字 ID 不算），这样和头像墙上的名字对得上。"""
    try:
        folders, mapping = _vn_load_folders()
    except Exception:
        folders, mapping = [], {}
    rows = []
    try:
        files = sorted(_cx_video_dir().glob("*.md"), key=lambda p: p.name, reverse=True)
    except Exception:
        files = []
    for p in files:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.read(2500).split("\n")
        except Exception:
            continue
        url = au = ""
        for ln in lines[1:16]:
            t = ln.strip().lstrip("-").strip()
            if not url and t.startswith(("来源链接：", "来源链接:")):
                url = t[5:].strip()
        for ln in lines[1:8]:
            t = ln.strip().lstrip("-").strip()
            if t.startswith(("作者：", "作者:")):
                cand = t[3:].strip()
                au = cand[:40] if cand and not cand.isdigit() else ""
                break
        fold = mapping.get(p.name, "")
        rows.append({"url": url, "author": au, "folder": fold if fold in folders else ""})
    return {"rows": rows, "folders": list(folders)}


def _vn_pick_sources(key, index=None, limit=3):
    """v60：找这个博主（或文件夹）的在线视频链接，新的在前，最多 limit 条。
    文件夹里如果是好几个博主的笔记（比如按主题建的「英语」），就不算一个博主，不去绑。
    返回 (链接列表, 找不到时的原因)。"""
    from collections import Counter
    key = (key or "").strip()
    idx = index or _vn_note_index()
    rows = idx["rows"]
    mine = [r for r in rows if r["author"] and r["author"] == key]
    if not mine and key in idx["folders"]:
        inf = [r for r in rows if r["folder"] == key]
        authors = Counter(r["author"] for r in inf if r["author"])
        if not inf:
            return [], "这个文件夹是空的"
        if not authors:
            return [], "文件夹里的笔记都没填作者"
        top, n = authors.most_common(1)[0]
        if n < 0.8 * sum(authors.values()):
            return [], "文件夹里是好几个博主的笔记，不是同一个博主"
        mine = [r for r in inf if r["author"] == top]
    if not mine:
        return [], "没找到这个博主的笔记"
    urls = []
    for r in mine:
        u = r["url"]
        if u.startswith("http") and u not in urls:
            urls.append(u)
            if len(urls) >= limit:
                break
    if not urls:
        return [], "这个博主的笔记都是本地导入的，没有视频链接"
    return urls, ""


# ════════ v60：一键识别博主主页（给还没主页的博主一个个找主页、取头像和资料）════════
_cpb_lock = _threading.Lock()
_cpb = {"running": False, "stop": False, "total": 0, "done": 0, "ok": 0, "noav": 0, "fail": 0,
        "skip": 0, "current": "", "started": 0, "finished": 0, "results": [], "note": "", "renamed": []}
_CPB_GAP = (3.0, 2.0)         # 每个博主之间歇 3~5 秒，别被抖音等平台限流
_CPB_PAUSE_AFTER = 6          # 连续这么多个没找到 → 歇一分钟
_CPB_STOP_AFTER = 12          # 连续这么多个没找到 → 先停下（多半没网或被限流）


def _cpb_sleep(sec):
    """可被「停止」打断的等待。被停止返回 True。"""
    import time as _t
    end = _t.time() + sec
    while _t.time() < end:
        if _cpb["stop"]:
            return True
        _t.sleep(0.3)
    return False


def _cpb_worker(keys):
    import time as _t
    import random as _r
    import creator_profiles as _cpf
    idx = _vn_note_index()
    streak = 0
    sess = None
    try:
        try:
            import douyin_resolver as _dr       # v61：整批共用一个后台浏览器（抖音找作者要用）
            sess = _dr.browser_session()
            sess.__enter__()
        except Exception:
            sess = None
        for key in keys:
            if _cpb["stop"]:
                break
            _cpb["current"] = key
            st = _cpf.profile_state(key)
            res = {"key": key}
            networked = False
            if st.get("url") or st.get("no_auto"):
                res.update(status="skip", msg="已经有主页了" if st.get("url") else "你解除过绑定")
            else:
                urls, why = _vn_pick_sources(key, idx)
                if not urls:
                    res.update(status="skip", msg=why)
                    try:
                        _cpf.mark_skip(key, why)
                    except Exception:
                        pass
                else:
                    networked = True
                    try:
                        ok, info, _k = _cpf.auto_bind_from_videos(key, urls, force=True)
                    except Exception as e:
                        ok, info = False, "出错：%s" % e
                    if ok and isinstance(info, dict):
                        try:
                            _nk, rn = _vn_after_bind(key, info)      # v63：博主改名了 → 软件里也改
                        except Exception:
                            rn = ""
                        if rn:
                            with _cpb_lock:
                                _cpb["renamed"].append(rn)
                        res.update(status="ok" if info.get("has_avatar") else "noav",
                                   msg=(info.get("platform_label") or "") +
                                   ("（%s）" % info["found_via"] if info.get("found_via") else ""),
                                   name=info.get("name") or "")
                    else:
                        res.update(status="fail", msg=str(info)[:300])
                    streak = streak + 1 if res["status"] == "fail" else 0
            with _cpb_lock:
                _cpb["done"] += 1
                _cpb[res["status"]] += 1
                _cpb["results"].append(res)
            _clog("博主", {"ok": "✓", "noav": "✓（没头像）", "fail": "✗", "skip": "－"}[res["status"]] +
                  " %s %s" % (key, res.get("msg") or ""))
            if not networked:
                continue
            if streak >= _CPB_STOP_AFTER:
                _cpb["note"] = ("连续 %d 个都没找到，可能是网络有问题或被平台限流了，先停下。"
                                "过一会儿再点「一键识别」，会接着找剩下的。" % streak)
                break
            if streak and streak % _CPB_PAUSE_AFTER == 0:
                _cpb["note"] = "连续几个没找到，先歇一分钟再接着找（防止被平台限流）"
                if _cpb_sleep(60):
                    break
                _cpb["note"] = ""
            if _cpb_sleep(_CPB_GAP[0] + _r.random() * _CPB_GAP[1]):
                break
    finally:
        if sess is not None:
            try:
                sess.__exit__(None, None, None)
            except Exception:
                pass
        with _cpb_lock:
            _cpb["running"] = False
            _cpb["current"] = ""
            _cpb["finished"] = _t.time()
        _clog("博主", "一键识别结束：成功 %d（没头像 %d），没找到 %d，跳过 %d" % (
            _cpb["ok"] + _cpb["noav"], _cpb["noav"], _cpb["fail"], _cpb["skip"]))


def _vn_find_source_url(key):
    """v59：在这个博主（或同名文件夹）的笔记里找一条在线视频链接，新的优先。找不到返回空。"""
    key = (key or "").strip()
    try:
        _folders, mapping = _vn_load_folders()
    except Exception:
        mapping = {}
    try:
        files = sorted(_cx_video_dir().glob("*.md"), key=lambda p: p.name, reverse=True)
    except Exception:
        return ""
    for p in files:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                head = f.read(2000).split("\n")[:16]
        except Exception:
            continue
        url = au = ""
        for ln in head:
            t = ln.strip().lstrip("-").strip()
            if t.startswith(("来源链接：", "来源链接:")):
                url = t[5:].strip()
            elif t.startswith(("作者：", "作者:")):
                au = t[3:].strip()
        if url.startswith("http") and (au == key or mapping.get(p.name) == key):
            return url
    return ""


def _vn_rename_blogger(old, new):
    """v63：博主改名了 → 软件里也改成新名字：作者是 old 的笔记都改成 new；同名的文件夹也改名；
    博主资料挪到 new 名下。返回改了几条笔记。（v64：和「合并博主」共用 _vn_move_blogger）"""
    old, new = (old or "").strip(), (new or "").strip()[:40]
    if not old or not new or old == new:
        return 0
    n, _nf = _vn_move_blogger(old, new)
    _clog("博主", "✎ 博主改名：%s → %s（已更新 %d 条笔记）" % (old, new, n))
    return n


# ════════════════ v64：合并博主（大小号 / 同名的文件夹和作者 / 只差表情空格的名字） ════════════════
# video_notes/_merged.json：
#   alias    {小号名: 大号名}        合并过的名字，以后这个名字的新视频自动算到大号名下
#   keep_out {笔记文件名: 文件夹名}  用户自己从同名文件夹里移出来的笔记，不再自动放回去
#   history  [合并记录]              手动合并的记录（撤销用，最多留 50 条）
_vn_merge_lock = _threading.Lock()


def _vn_merged_path():
    return _cx_video_dir() / "_merged.json"


def _vn_load_merged():
    try:
        d = json.loads(_vn_merged_path().read_text(encoding="utf-8", errors="replace"))
        if not isinstance(d, dict):
            d = {}
    except Exception:
        d = {}
    d["alias"] = {str(k).strip(): str(v).strip() for k, v in (d.get("alias") or {}).items()
                  if str(k).strip() and str(v).strip() and str(k).strip() != str(v).strip()}
    d["keep_out"] = {str(k): str(v) for k, v in (d.get("keep_out") or {}).items()}
    d["history"] = [h for h in (d.get("history") or []) if isinstance(h, dict) and h.get("id")]
    return d


def _vn_save_merged(d):
    try:
        _vn_merged_path().write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _vn_norm(s):
    """比较名字用：全角转半角，去掉表情、空格、标点，字母转小写。"""
    import unicodedata as _ud
    s = _ud.normalize("NFKC", s or "")
    return re.sub(r"[^\w]+", "", s.lower()).replace("_", "")


def _vn_alias_of(name, alias):
    """合并过的小号名 → 现在用的大号名（顺着找，最多 6 层，防止绕圈）。"""
    cur, seen = name, {name}
    for _ in range(6):
        nxt = alias.get(cur)
        if not nxt or nxt in seen:
            break
        seen.add(nxt)
        cur = nxt
    return cur


def _vn_note_author(name):
    """读一条笔记的作者（和列表的认法一样：第一条「作者：」，最多 40 字）。读不到返回空串。"""
    try:
        with open(_cx_video_dir() / name, encoding="utf-8", errors="replace") as f:
            lines = f.read(2500).split("\n")
    except Exception:
        return ""
    for ln in lines[1:8]:
        t = ln.strip().lstrip("-").strip()
        if t.startswith(("作者：", "作者:")):
            return t[3:].strip()[:40]
    return ""


def _vn_move_blogger(old, new, record=None):
    """把 old 名下的一切挪到 new 名下（v63 博主改名、v64 合并博主共用）：
      · 作者是 old 的笔记 → 作者改成 new；
      · old 是文件夹：new 还没有文件夹 → old 直接改名成 new；new 已经有文件夹 → 笔记都挪进 new，删掉 old；
      · new 是文件夹 → 没进文件夹、作者是 new 的笔记也归进去（不然又会多出一个同名的圆头像）；
      · 博主资料（头像、主页）挪到 new 下；new 已经有主页 / 头像的，保留 new 的。
    record 是 dict 时，把每条笔记原来的作者 / 文件夹记到 record["notes"]（撤销用）。
    返回 (改了作者的笔记数, 挪了文件夹的笔记数)。"""
    old, new = (old or "").strip(), (new or "").strip()[:40]
    if not old or not new or old == new:
        return 0, 0
    log = {}                      # 笔记 → [原作者或 None, 原文件夹或 None, 是不是新归进文件夹的]
    authors = {}
    n_author = 0
    try:
        files = list(_cx_video_dir().glob("*.md"))
    except Exception:
        files = []
    for p in files:
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
        except Exception:
            continue
        for i in range(1, min(8, len(lines))):
            t = lines[i].strip().lstrip("-").strip()
            if t.startswith(("作者：", "作者:")):
                cur = t[3:].strip()
                authors[p.name] = cur[:40]
                if cur[:40] == old:
                    lines[i] = "- 作者：" + new
                    try:
                        p.write_text("\n".join(lines), encoding="utf-8")
                        n_author += 1
                        authors[p.name] = new
                        log.setdefault(p.name, [None, None, False])[0] = cur
                    except Exception:
                        pass
                break
    n_folder = 0
    try:
        with _vn_lock:
            folders, mapping = _vn_load_folders()
            changed = False
            if old in folders:
                if new in folders:
                    folders.remove(old)
                else:
                    folders[folders.index(old)] = new
                for k, v in list(mapping.items()):
                    if v == old:
                        mapping[k] = new
                        log.setdefault(k, [None, None, False])[1] = old
                        n_folder += 1
                changed = True
            if new in folders:
                for k, a in authors.items():
                    if a == new and mapping.get(k) not in folders:
                        mapping[k] = new
                        e = log.setdefault(k, [None, None, False])
                        if e[1] is None:
                            e[2] = True
                        n_folder += 1
                        changed = True
            if changed:
                _vn_save_folders(folders, mapping)
    except Exception:
        pass
    try:
        import creator_profiles as _cpf
        _cpf.rename_key(old, new)
    except Exception:
        pass
    if isinstance(record, dict):
        record["notes"] = log
    return n_author, n_folder


def _vn_merge_bloggers(src, dst):
    """v64：把博主 src 合并到 dst 名下（大小号、同一个人用过两个名字）。
    src 的笔记都算到 dst 名下；以后 src 这个名字的新视频也自动算到 dst。可以撤销。
    返回 (ok, 说明)。"""
    src, dst = (src or "").strip(), (dst or "").strip()[:40]
    if not src or not dst:
        return False, "缺少要合并的博主"
    if src == dst:
        return False, "是同一个名字，不用合并"
    if "未填作者" in (src, dst):
        return False, "「未填作者」不是一个博主，不能合并"
    import creator_profiles as _cpf
    folders, _mp = _vn_load_folders()
    rec = {"id": "%x%04x" % (int(_time_now() * 1000), os.getpid() % 65536), "src": src, "dst": dst,
           "at": int(_time_now()), "src_folder": src in folders, "dst_folder": dst in folders,
           "src_profile": _cpf.profile_state(src) or None, "dst_profile": _cpf.profile_state(dst) or None}
    _vn_move_blogger(src, dst, record=rec)
    after = _cpf.profile_state(dst) or {}
    rec["moved_profile"] = bool(rec["src_profile"]) and after.get("renamed_from") == src and \
        after != (rec["dst_profile"] or {})
    rec["n"] = len(rec.get("notes") or {})
    with _vn_merge_lock:
        m = _vn_load_merged()
        al = m["alias"]
        al.pop(dst, None)                       # 防止绕圈：dst 自己不能再指向别人
        for k, v in list(al.items()):
            if v == src:
                al[k] = dst                     # 以前并到 src 的，现在也跟着到 dst
        al[src] = dst
        m["history"] = ([rec] + m["history"])[:50]
        _vn_save_merged(m)
    _clog("博主", "🔗 合并博主：%s → %s（%d 条笔记）" % (src, dst, rec["n"]))
    return True, "已把「%s」合并到「%s」名下（%d 条笔记）" % (src, dst, rec["n"])


def _vn_unmerge(hid):
    """v64：撤销一次合并：笔记的作者、文件夹、博主资料都恢复成合并前的样子。返回 (ok, 说明)。"""
    with _vn_merge_lock:
        m = _vn_load_merged()
        rec = next((h for h in m["history"] if h.get("id") == hid), None)
    if not rec:
        return False, "找不到这次合并的记录（可能已经撤销过了）"
    src, dst = rec.get("src") or "", rec.get("dst") or ""
    notes = rec.get("notes") or {}
    for name, e in notes.items():
        if isinstance(e, list) and e and e[0] is not None:
            _vn_set_note_author(name, e[0])
    try:
        with _vn_lock:
            folders, mapping = _vn_load_folders()
            if rec.get("src_folder") and src not in folders:
                folders.append(src)
            for name, e in notes.items():
                if not isinstance(e, list) or len(e) < 3:
                    continue
                if e[1]:
                    mapping[name] = e[1]
                elif e[2] and mapping.get(name) == dst:
                    mapping.pop(name, None)
            if not rec.get("dst_folder") and dst in folders and dst not in mapping.values():
                folders.remove(dst)
            _vn_save_folders(folders, mapping)
    except Exception:
        pass
    try:
        import creator_profiles as _cpf
        _cpf.restore_after_unmerge(src, dst, rec.get("src_profile"), rec.get("dst_profile"),
                                   bool(rec.get("moved_profile")))
    except Exception:
        pass
    with _vn_merge_lock:
        m = _vn_load_merged()
        if m["alias"].get(src) == dst:
            m["alias"].pop(src, None)
        m["history"] = [h for h in m["history"] if h.get("id") != hid]
        _vn_save_merged(m)
    _clog("博主", "↶ 撤销合并：「%s」又从「%s」里分出来了" % (src, dst))
    return True, "已撤销：「%s」又分出来了" % src


def _vn_canon_name(author, folders):
    """新笔记的作者 → 软件里已经在用的名字：合并过的小号 → 大号；和已有的文件夹 / 绑了主页的博主
    只差表情、空格、标点、全半角 → 用已有的那个写法。都不是就原样返回。"""
    a = (author or "").strip()
    if not a:
        return a
    try:
        alias = _vn_load_merged()["alias"]
    except Exception:
        alias = {}
    if a in alias:
        return _vn_alias_of(a, alias)
    n = _vn_norm(a)
    if not n:
        return a
    for k, v in alias.items():
        if _vn_norm(k) == n:
            return _vn_alias_of(k, alias)
    for f in folders:
        if _vn_norm(f) == n:
            return f
    try:
        import creator_profiles as _cpf
        for k, p in _cpf.list_raw().items():
            if k != a and _vn_norm(k) == n and (p.get("url") or p.get("avatar_file")):
                return k
    except Exception:
        pass
    return a


def _vn_canon_new_note(job, res):
    """v64：新笔记存好后（在找博主主页之前）整理一下博主名：
      · 作者是合并过的小号 / 只差表情空格 → 改成软件里已经在用的名字；
      · 作者和某个文件夹同名 → 直接归进那个文件夹（任务自己指定了文件夹的不动）。
    这样「姜胡说」文件夹以后不会再多出一个同名的圆头像。"""
    fname = res.get("saved_as") or ""
    au = (res.get("uploader") or job.get("author") or "").strip()
    if not fname or not au:
        return
    folders, mapping = _vn_load_folders()
    canon = _vn_canon_name(au, folders)
    if canon and canon != au and _vn_set_note_author(fname, canon):
        res["uploader"] = canon
        _clog("博主", "「%s」记到「%s」名下（合并过 / 同一个名字）" % (au, canon))
    if (canon in folders and not (job.get("note_folder") or "").strip()
            and mapping.get(fname) not in folders):
        _vn_assign_folder(fname, canon)
        _clog("视频", "📁 这条笔记归进了「%s」文件夹（作者和文件夹同名）" % canon)


def _vn_tidy_same_name(items, folders):
    """v64：笔记列表每次加载时顺手整理一下（items 原地更新），让头像墙上不出现重名的博主：
      ① 作者是合并过的小号 → 改成大号名；
      ② 没进文件夹的笔记，作者和某个文件夹同名（不管表情、空格、标点）→ 归进那个文件夹
         （用户自己从文件夹里移出来的不动）；
      ③ 没进文件夹的作者里，只差表情 / 空格 / 标点 / 全半角的几个名字 → 统一成一个
         （优先用绑了主页的那个，其次用最新一条视频里的写法）。
    返回做了什么（每件事一句话），什么都没做返回空列表。"""
    done = []
    try:
        mg = _vn_load_merged()
    except Exception:
        return done
    alias, keep_out = mg["alias"], mg["keep_out"]
    fset = set(folders)
    # ① 合并过的小号名
    if alias:
        hit = {}
        for it in items:
            a = it.get("author") or ""
            if a in alias:
                c = _vn_alias_of(a, alias)
                if c != a and _vn_set_note_author(it["name"], c):
                    it["author"] = c
                    hit.setdefault((a, c), 0)
                    hit[(a, c)] += 1
        for (a, c), k in hit.items():
            done.append("「%s」的 %d 条新笔记算到了「%s」名下（合并过）" % (a, k, c))
    # ② 作者和文件夹同名 → 归进文件夹
    fnorm = {}
    for f in folders:
        nf = _vn_norm(f)
        if nf and nf not in fnorm:
            fnorm[nf] = f
    to_file = {}
    for it in items:
        if it.get("folder") in fset or it["name"] in keep_out:
            continue
        f = fnorm.get(_vn_norm(it.get("author") or ""))
        if f:
            to_file[it["name"]] = f
    if to_file:
        try:
            with _vn_lock:
                fs, mp = _vn_load_folders()
                for k, f in list(to_file.items()):
                    if f in fs and mp.get(k) not in fs:
                        mp[k] = f
                    else:
                        to_file.pop(k)
                if to_file:
                    _vn_save_folders(fs, mp)
        except Exception:
            to_file = {}
        cnt = {}
        for it in items:
            f = to_file.get(it["name"])
            if f:
                it["folder"] = f
                cnt[f] = cnt.get(f, 0) + 1
        for f, k in cnt.items():
            done.append("「%s」有 %d 条笔记没在同名文件夹里，已归进「%s」文件夹" % (f, k, f))
    # ③ 只差表情 / 空格 / 标点的作者名 → 统一成一个
    groups = {}
    for it in items:
        a = it.get("author") or ""
        if not a or it.get("folder") in fset:
            continue
        na = _vn_norm(a)
        if na:
            groups.setdefault(na, []).append(it)
    multi = {na: its for na, its in groups.items() if len({x["author"] for x in its}) > 1}
    if multi:
        try:
            import creator_profiles as _cpf
            raw = _cpf.list_raw()
        except Exception:
            _cpf, raw = None, {}
        for na, its in multi.items():
            names = []
            for x in sorted(its, key=lambda x: -(x.get("ts") or 0)):     # 新的在前
                if x["author"] not in names:
                    names.append(x["author"])
            bound = [nm for nm in names if (raw.get(nm) or {}).get("url")]
            canon = bound[0] if bound else names[0]
            for nm in names:
                if nm == canon:
                    continue
                k = 0
                for x in its:
                    if x["author"] == nm and _vn_set_note_author(x["name"], canon):
                        x["author"] = canon
                        k += 1
                if _cpf is not None:
                    try:
                        _cpf.rename_key(nm, canon)
                    except Exception:
                        pass
                done.append("「%s」和「%s」只差表情 / 空格 / 标点，统一成了「%s」（%d 条笔记）" % (nm, canon, canon, k))
    for line in done:
        _clog("博主", "🔗 " + line)
    return done


def _vn_after_bind(key, info):
    """v63：绑定成功后看看博主是不是改名了。返回 (现在用的名字, 改名说明或空)。
      ① 视频数据里的名字和软件里的不一样（抖音 / B站）→ 软件里改成新名字；
      ② 同一个主页之前绑在别的名字（旧名字）下 → 那些笔记也改成现在的名字。"""
    if not isinstance(info, dict):
        return key, ""
    plat = info.get("platform") or ""
    if plat not in ("douyin", "bilibili"):
        return key, ""
    import douyin_resolver as _dr
    import creator_profiles as _cpf
    notes = []
    new = re.sub(r"\s+", " ", (info.get("name") or "")).strip()
    if (new and len(new) <= 40 and not new.isdigit() and not _dr._name_match(new, key)
            and not new.startswith(key) and not key.startswith(new)):
        n = _vn_rename_blogger(key, new)
        notes.append("%s → %s（%d 条笔记）" % (key, new, n))
        key = new
    uid = info.get("uid") or ""
    if uid:
        for k, p in _cpf.list_raw().items():
            if k != key and p.get("uid") == uid and p.get("platform") == plat:
                n = _vn_rename_blogger(k, key)
                notes.append("%s → %s（%d 条笔记）" % (k, key, n))
    return key, "；".join(notes)


def _vn_doc_meta(res):
    """v65：文档 / 网页文章的笔记开头多写几行：类型、发布时间、页面里的视频。"""
    if not isinstance(res, dict) or res.get("source") not in ("doc", "article"):
        return ""
    out = "- 类型：%s\n" % (res.get("doc_kind") or "文档")
    if res.get("published"):
        out += "- 发布时间：%s\n" % res["published"]
    pv = [u for u in (res.get("page_videos") or []) if u and " " not in u][:8]
    if pv:
        out += "- 页面视频：%s\n" % " ".join(pv)
    return out


def _vn_src_noun_of_file(name):
    """v65：笔记是导入的文档 / 文章 → 返回「文档」「文章」「表格」…；视频笔记返回 None。"""
    try:
        with open(_cx_video_dir() / name, encoding="utf-8", errors="replace") as f:
            head = f.read(3000).split("\n")[:16]
    except Exception:
        return None
    for ln in head:
        t = ln.strip().lstrip("-").strip()
        if t.startswith(("类型：", "类型:")):
            try:
                import doc_import
                return doc_import.noun_of(t[3:].strip())
            except Exception:
                return "文档"
    return None


# ════════════════ v74 / v75：嗅探的博主头像 ════════════════
# 和视频页的「博主资料」共用（按名字）：已经有头像的直接用；没有的在后台一个一个去取：
#   · X：用你存的 X Cookie 问 X 要头像（和扫推文同一个接口），不行再用公开服务；
#   · YouTube / 抖音 / B站：链接是主页就按主页取；不是主页（比如 YouTube 搜索链接）或者主页取不到，
#     就从他的视频找到主页再取。取不到的在终端里写明原因，30 分钟后再试。用户手动解除过的不碰。
_cw_av = {"running": False, "tried": {}, "stop": False, "manual": False, "total": 0, "done": 0, "ok": 0, "fail": 0,
          "current_id": "", "current": "", "errors": [], "started": 0, "finished": 0}   # v76：一键解析的进度


def _cw_attach_avatars(creators):
    try:
        import creator_profiles as _cpf
        raw = _cpf.list_raw()
    except Exception:
        return
    todo, now = [], _time_now()
    for c in creators or []:
        key = (c.get("title") or "").strip()
        p = raw.get(key) or {}
        fp = _cpf._avatar_file(p) if p else None
        if p:                                            # v76：主页资料（点头像时显示）
            c["profile"] = {k: p.get(k) for k in ("name", "followers", "works", "signature", "home", "url", "error")
                            if p.get(k) not in (None, "")}
            c["profile"]["platform_label"] = getattr(_cpf, "PLATFORM_LABEL", {}).get(p.get("platform") or "", "")
        if fp:
            try:
                c["avatar"] = {"key": key, "v": int(fp.stat().st_mtime)}
            except Exception:
                pass
        elif (key and c.get("platform") in ("youtube", "douyin", "bilibili", "x", "web") and not p.get("no_auto")
              and now - _cw_av["tried"].get(c.get("id"), 0) > 1800):
            todo.append(dict(c))
    if todo and not _cw_av["running"]:
        _cw_av_begin(todo, manual=False)
        _threading.Thread(target=_cw_fill_avatars, args=(todo,), daemon=True).start()


def _cw_av_begin(todo, manual):
    _cw_av.update({"running": True, "stop": False, "manual": manual, "total": len(todo), "done": 0, "ok": 0,
                   "fail": 0, "current_id": "", "current": "", "errors": [], "started": _time_now(), "finished": 0})


def _cw_avatar_start(ids=None, force=False):
    """v76：「一键解析博主主页」/ 单个博主的 🔍。ids 为空 = 所有还没头像的博主；
    force = 已经有头像的也重新解析一遍（刷新头像、粉丝数、简介）。返回 (ok, 说明)。"""
    if _cw_av["running"]:
        return False, "正在解析，等这一轮做完（或者先点「停止」）"
    import creator_watch
    import creator_profiles as _cpf
    raw = _cpf.list_raw()
    ids = [str(i) for i in (ids or []) if i]
    todo = []
    for c in creator_watch.list_creators():
        if ids and str(c.get("id")) not in ids:
            continue
        if c.get("platform") not in ("youtube", "douyin", "bilibili", "x", "web"):
            continue
        p = raw.get((c.get("title") or "").strip()) or {}
        if not force and _cpf._avatar_file(p):
            continue
        if p.get("no_auto") and not ids:
            continue                                 # 你手动解除过的：一键解析不碰；单独点 🔍 的照做
        todo.append(dict(c))
    if not todo:
        return False, ("这个平台的主页解析不了" if ids else "所有博主都有头像了")
    _cw_av_begin(todo, manual=True)
    _threading.Thread(target=_cw_fill_avatars, args=(todo, force), daemon=True).start()
    return True, "开始解析 %d 个博主的主页" % len(todo)


def _cw_video_urls(cw, cid, limit=3):
    urls = []
    try:
        for v in ((cw.get_cached_videos(cid) or {}).get("videos") or []):
            u = (v.get("url") or "").strip()
            if u.startswith("http") and u not in urls:
                urls.append(u)
    except Exception:
        pass
    try:
        for f in (cw.get_findings() or []):
            if str(f.get("creator_id")) == str(cid):
                u = (f.get("url") or "").strip()
                if u.startswith("http") and u not in urls:
                    urls.append(u)
    except Exception:
        pass
    return urls[:limit]


def _cw_one_avatar(_cpf, cw, c, force=False):
    """给一个博主取头像（和主页资料）。返回 (怎么取到的, 没取到的原因)。"""
    key, url, plat = (c.get("title") or "").strip(), (c.get("url") or "").strip(), c.get("platform")
    has = lambda: bool(_cpf._avatar_file(_cpf.profile_state(key)))
    errs = []
    if plat == "web":                                 # v78：网站：网站图标当头像，顺便存名字和简介
        try:
            import site_watch
            info = site_watch.site_info(url)
            data, _src = site_watch.icon_bytes(url, info)
            site_watch.save_profile(key, info, data or None)
            if data and has():
                return "网站图标", ""
            errs.append("网站上没找到能用的图标" if not data else "图标存不进去")
        except Exception as e:
            errs.append(str(e)[:80])
        return "", "；".join(errs)
    if force and plat not in ("x", "web") and _cpf.profile_state(key).get("url"):
        try:
            ok, info = _cpf.refresh(key)[:2]          # v76：已经绑过主页 → 按主页重新取一遍
            if ok and has():
                return "刷新了主页资料", ""
            errs.append("主页：" + str(info)[:60])
        except Exception as e:
            errs.append("主页：" + str(e)[:60])
    if plat == "x":
        try:
            import x_watch
            import base64
            img = x_watch.user_avatar(url)
            data = _cpf._download_avatar(img, "x") if img else b""
            if data:
                ok, msg = _cpf.set_avatar_data(key, "data:image/jpeg;base64," + base64.b64encode(data).decode())
                if ok and has():
                    return "X 头像", ""
                errs.append(str(msg)[:80])
            else:
                errs.append("X 没给头像（X 的 Cookie 过期了的话，在嗅探页重新粘一次 Cookie）")
        except Exception as e:
            errs.append(str(e)[:80])
        return "", "；".join(errs)
    p = _cpf.profile_state(key)
    is_home = plat in ("douyin", "bilibili") or bool(re.search(r"youtube\.com/(@|channel/|c/|user/)", url))
    if is_home and not p.get("url"):
        try:
            ok, info = _cpf.bind(key, url)[:2]
            if has():
                return "主页", ""
            errs.append("主页：" + (str(info)[:60] if not ok else "主页上没找到头像"))
        except Exception as e:
            errs.append("主页：" + str(e)[:60])
    vurls = _cw_video_urls(cw, c.get("id"), limit=8)
    # YouTube 搜索链接列出来的东西里，常常第一条就是他的频道本身 → 直接当主页用（最准）
    chans = [u for u in vurls if re.search(r"youtube\.com/(@|channel/|c/|user/)", u)]
    if plat == "youtube" and chans and not _cpf.profile_state(key).get("url"):
        try:
            ok, info = _cpf.bind(key, chans[0])[:2]
            if has():
                return "他的频道", ""
            errs.append("频道：" + (str(info)[:60] if not ok else "频道页上没找到头像"))
        except Exception as e:
            errs.append("频道：" + str(e)[:60])
    vurls = [u for u in vurls if u not in chans][:3]
    if vurls:
        try:
            ok, info, _k = _cpf.auto_bind_from_videos(key, vurls, force=True)
            if has():
                return "从他的视频找到主页", ""
            errs.append("视频：" + str(info)[:80])
        except Exception as e:
            errs.append("视频：" + str(e)[:60])
    elif not is_home:
        errs.append("链接不是主页，也还没有他的视频（先扫一遍）")
    return "", "；".join(errs) or "没取到"


def _cw_fill_avatars(todo, force=False):
    try:
        import creator_profiles as _cpf
        import creator_watch as _cw
        for c in todo:
            if _cw_av["stop"]:
                _clog("嗅探", "解析博主主页：你点了停止")
                break
            _cw_av["current_id"], _cw_av["current"] = str(c.get("id") or ""), c.get("title") or ""
            _cw_av["tried"][c.get("id")] = _time_now()
            try:
                how, why = _cw_one_avatar(_cpf, _cw, c, force)
            except Exception as e:
                how, why = "", str(e)[:80]
            _cw_av["done"] += 1
            if how:
                _cw_av["ok"] += 1
                _clog("嗅探", "✓ 给「%s」取到了头像（%s）" % (c.get("title"), how))
            else:
                _cw_av["fail"] += 1
                _cw_av["errors"] = (_cw_av["errors"] + [{"id": str(c.get("id") or ""), "name": c.get("title") or "",
                                                         "why": why}])[-40:]
                _clog("嗅探", "✗「%s」的头像没取到：%s（30 分钟后再试）" % (c.get("title"), why))
            _time_log.sleep(1.0)
    finally:
        _cw_av.update({"running": False, "current_id": "", "current": "", "finished": _time_now()})


def _vn_creator_after_save(job, res, cb=None):
    """v59：提取完成、笔记存好后，给这条笔记的博主建「博主板块」资料（头像、昵称、粉丝数、简介）。
      · 提取卡片里填了「博主主页」→ 按它绑定（笔记没有作者时，顺便把作者填成博主昵称）；
      · 没填 → 根据视频链接自动找博主主页（抖音作者 / B站 UP 主 / YouTube 频道）。
    已经有资料的博主不重复找；最多等 25 秒，超时就让它在后台接着做，不耽误下一个视频。
    返回给前端显示的一小段信息；什么都没做返回 None。"""
    import creator_profiles as _cpf
    creator_url = (job.get("creator_url") or "").strip()
    video_url = (res.get("url") or job.get("url") or "").strip()
    key = (res.get("uploader") or job.get("author") or "").strip()
    fname = res.get("saved_as") or ""
    if not creator_url:
        if not key or not video_url.startswith("http"):
            return None
        if not _cpf.should_auto_bind(key):
            return {"key": key, "status": "exists"}
    box = {}

    def work():
        try:
            if creator_url:
                ok, info, k = _cpf.bind_for_note(key, creator_url)
            else:
                ok, info, k = _cpf.auto_bind_from_video(key, video_url)
            box.update(ok=ok, info=info, key=k)
        except Exception as e:
            box.update(ok=False, info=str(e), key=key)

    if cb:
        cb("博主主页", "正在识别博主主页，取头像和资料…")
    t = _threading.Thread(target=work, daemon=True)
    t.start()
    t.join(40)            # v61：抖音可能要开后台浏览器找，多等一会儿；还没好就让它在后台接着做
    if t.is_alive():
        _clog("博主", "「%s」的主页还在识别，后台接着做" % (key or "博主"))
        return {"key": key, "status": "pending"}
    ok, info, k = box.get("ok"), box.get("info"), (box.get("key") or key)
    if ok and isinstance(info, dict):
        if not key and k and fname and _vn_set_note_author(fname, k):
            res["uploader"] = k
        _clog("博主", "✓ 已识别「%s」的主页：%s" % (k, info.get("home") or info.get("url") or ""))
        try:
            k2, _rn = _vn_after_bind(k, info)     # v63：同一个主页以前绑在旧名字下 → 统一成现在的名字
            if k2 != k:
                k = k2
                res["uploader"] = k2
        except Exception:
            pass
        return {"key": k, "status": "bound", "name": info.get("name") or k,
                "platform": info.get("platform_label") or "", "auto": not creator_url}
    _clog("博主", "✗「%s」的主页没识别出来：%s" % (key or "博主", str(info)[:120]))
    return {"key": key, "status": "fail", "message": str(info)[:120], "auto": not creator_url}


def _bold_point_titles(md):
    """把"序号. 小标题"这种要点标题行加粗（重点更醒目）。
    只处理较短、像小标题的编号行；已经加粗的、太长的（像整段正文）不动。"""
    import re
    out = []
    for ln in (md or "").split("\n"):
        m = re.match(r"^(\s*)(\d+)\.\s+(\S.*)$", ln)
        if m and "**" not in ln:
            indent, num, title = m.group(1), m.group(2), m.group(3).strip()
            # 去掉可能的行尾冒号，标题不太长才当小标题加粗
            if len(title) <= 80:
                out.append(f"{indent}**{num}. {title}**")
                continue
        out.append(ln)
    return "\n".join(out)


def _fmt_mmss(sec):
    """秒 → mm:ss（给带时间戳文字稿和标记示例用）。"""
    try:
        sec = int(float(sec))
    except Exception:
        sec = 0
    return "%02d:%02d" % (sec // 60, sec % 60)


def _build_timestamped_transcript(segments, limit=10000):
    """把带时间戳的分段拼成「[mm:ss] 这句话」的文字稿，让模型知道每段话在第几分秒，
    才能把 Screenshot/Content 标记的时间打准。控制总长，避免超出上下文。"""
    lines = []
    total = 0
    for s in segments or []:
        t = (s.get("text") or "").strip()
        if not t:
            continue
        line = "[%s] %s" % (_fmt_mmss(s.get("start", 0)), t)
        total += len(line)
        if total > limit:
            break
        lines.append(line)
    return "\n".join(lines)


def _cx_analyze_transcript(transcript, title, use_local, model, on_progress=None,
                           segments=None, do_screenshot=False, do_link=False, src_noun=None):
    # 要插图或跳转时，给模型「带时间戳的文字稿」，它才能把标记时间打准；
    # 否则维持原样（纯文字稿），行为和以前完全一致。
    want_markers = bool(do_screenshot or do_link) and bool(segments)
    # 文字稿上限：网页模型 / Claude 能吃长文，给 30000 字；本地小模型 10000 字。
    try:
        _ul, _m = core.video_model(use_local, model)
    except Exception:
        _ul, _m = use_local, model
    _limit = 12000 if _ul else 30000   # 本地模型会自动放大上下文窗口（agent_core._ollama_native_chat）
    if want_markers:
        body_text = _build_timestamped_transcript(segments, limit=_limit)
        if not body_text:
            body_text = (transcript or "")[:_limit]
    else:
        body_text = (transcript or "")[:_limit]
    _full_len = len(transcript or "")
    _cut_note = ""
    if _full_len > len(body_text) + 200:
        _cut_note = ("（注意：文字稿太长，下面只给出了前 %d%% 的内容。请只总结给出的部分，"
                     "并在「一句话概括」后面注明「本笔记只覆盖视频前 %d%% 的内容」。）\n"
                     % (len(body_text) * 100 // _full_len, len(body_text) * 100 // _full_len))

    prompt = (
        "下面是一段视频的文字稿（语音识别得到，可能有个别错别字，请结合上下文理解）。"
        "请帮我做一份**尽量详细、有深度、信息密度高、排版清晰**的中文笔记——宁可写长一点、"
        "写透一点，也不要简略带过。把视频里讲到的具体事例、数字、人名/品牌名、原话、因果逻辑"
        "都尽量保留下来。\n\n"
        "【第一步 · 翻译标题】在笔记最开头，**单独输出一行**，把这个视频标题翻译成自然、简洁的"
        "简体中文，格式严格为：`中文标题：<译文>`。如果标题本身已经是中文，就原样照抄；"
        "人名、产品名、公司名、专有名词可保留英文。这一行之后再开始正式笔记。\n\n"
        "【语言要求】不论原视频是中文还是英文/其它语言，这份笔记一律用**简体中文**输出。"
        "若原文是英文等外语，请把内容**准确翻译、用流畅的中文**讲清楚，不要整段照抄外语原文；"
        "但**专有名词、人名、产品/公司/项目名、关键技术术语**，以及「金句摘录」里引用的原话，"
        "请保留原文并在括号里附上中文（中英对照），方便对照查证。\n\n"
        "【排版要求】用 Markdown，层次分明、重点突出：每个大块用 `## 小标题`；"
        "「核心观点」「值得记住的点 / 行动建议」里的每一条，用 `### 序号. 小标题` 起头（序号连续），"
        "下面再写详细的正文段落；善用分段，让人一眼看到重点。\n\n"
        "请按下面结构输出（注意：先输出上面的「中文标题：」那一行，然后才是下面这些）：\n"
        "## 一句话概括\n用一句话说清楚这个视频到底在讲什么。\n\n"
        "## 背景与主题\n用 3-5 句把事件/话题的来龙去脉讲清楚：是什么事、涉及谁、作者站在什么角度讲。\n\n"
        "## 核心观点\n列 6-10 条主要观点，**每一条都展开成一段详细说明（4-6 句）**："
        "先点出观点，再结合视频里的**具体例子、数字、人名、案例、原话**把它讲透，"
        "并说明背后的原因 / 逻辑 / 影响，不要只写一句话或短语。\n\n"
        "## 关键事实与数据\n把视频里出现的**具体事实、数字、名称、案例**单独分条罗列，"
        "比如金额、比例、时间、涉及的公司/品牌/人物、提到的类似事件等，方便日后查证和引用。\n\n"
        "## 金句摘录\n从文字稿里挑 4-6 句最有价值或最有意思的原话，照原话摘出来（用引号），"
        "可稍微顺一下口语里明显的错别字；若原话是英文等外语，引用原话后**紧跟一行中文翻译**。\n\n"
        "## 值得记住的点 / 行动建议\n用 `### 序号. 小标题` + 详细正文，分条写作者给的具体建议、"
        "可操作的做法或最有用的信息，越具体、越能落地越好。\n\n"
        "## 我的点评\n用 4-6 句客观点评：这些观点有没有道理、哪里值得认同、"
        "哪里需要注意或保留、可能的片面之处，普通人可以怎么用。\n\n"
        "整体要条理清晰、信息密度高、尽量详尽，是深度归纳不是照抄原文。\n")

    # 按开关追加「插图 / 跳转原片」标记要求。文字稿带 [mm:ss]，模型据此打准时间。
    if want_markers:
        prompt += (
            "\n【特别要求 · 时间标记】下面的文字稿每行开头都有 [mm:ss] 时间，"
            "请据此在笔记里恰当位置插入下面的标记（标记单独成行、原样输出，不要改写、不要加代码块）：\n")
        if do_screenshot:
            prompt += (
                "- 当某段内容涉及**画面演示、操作步骤、图表、关键场景**等"
                "「看一眼图更好懂」的地方，在该段末尾**单独一行**插入截图标记："
                "`*Screenshot-[mm:ss]`，时间取该内容对应的时刻。"
                "只在真正有助于理解时插，全篇控制在 3-8 个，别滥用。\n")
        if do_link:
            prompt += (
                "- 每个 `## 小标题` 这种大块的**标题行末尾**，追加一个跳转标记 "
                "`*Content-[mm:ss]`，时间取该大块开始讲的时刻，方便点回原片对应位置。\n")
        prompt += (
            "标记里的时间一定要用文字稿里真实出现的 [mm:ss]，不要瞎编。\n")

    if src_noun:     # v65：导入的文档 / 网页文章：提示词里的「视频」「文字稿」换成对应的说法（只换提示词，不动原文）
        prompt = prompt.replace(
            "下面是一段视频的文字稿（语音识别得到，可能有个别错别字，请结合上下文理解）。",
            "下面是一篇%s的原文（从网页或文件里提取出来的文字，可能带一点排版残留，请结合上下文理解）。" % src_noun)
        prompt = prompt.replace("文字稿", "原文").replace("视频", src_noun)
        _cut_note = _cut_note.replace("文字稿", "原文").replace("视频", src_noun)
        prompt += f"\n{src_noun}标题：{title}\n\n{_cut_note}=== 原文 ===\n{body_text}\n"
    else:
        prompt += f"\n视频标题：{title}\n\n{_cut_note}=== 文字稿 ===\n{body_text}\n"

    # 视频总结的设计：原文已用本地听写提取，这一步默认交给「网页模型」分析总结。
    try:
        s_use_local, s_model = core.video_model(use_local, model)
    except Exception:
        s_use_local, s_model = use_local, model
    # 若解析成"没配 OPENAI_API_KEY 的云端模型"，直接调用会报 Missing credentials，
    # 改用网页模型（设计本意），避免硬失败。Claude 模型有自己的 key，不在此列。
    _is_claude_m = (s_model == "claude") or str(s_model).startswith("claude::")
    if (not s_use_local) and (not core.is_web_model(s_model)) and (not _is_claude_m) \
            and not os.environ.get("OPENAI_API_KEY") \
            and not os.environ.get("OPENAI_ADMIN_KEY"):
        s_use_local, s_model = False, "web"

    _web_kw = dict(core.VIDEO_ANALYSIS_WEB_OPTS, saveImages=True) if core.is_web_model(s_model) else {}
    try:
        client = core.make_client_for(s_model, s_use_local, on_progress=on_progress)
        resp = client.chat.completions.create(
            model=s_model, messages=[{"role": "user", "content": prompt}], **_web_kw)
        out = (resp.choices[0].message.content or "").strip()
        if out:
            return _bold_point_titles(out)
        raise RuntimeError("空回复")
    except Exception as e:
        # v62：是你点了「停止」才中断的 → 不再换卡重试
        try:
            import web_model as _wm
            if _wm.was_cancelled():
                return "（分析出错：已按你的要求停止）"
        except Exception:
            pass
        # ★ 分析只用网页 AI 池（用户要求：本地模型分析不到位）。失败就换一张卡再试一次，不退回本地。
        try:
            if on_progress:
                try: on_progress("AI 池这次没成功（%s），换一张卡重试…" % str(e)[:40])
                except Exception: pass
            client = core.make_client_for("web", False, on_progress=on_progress)
            resp = client.chat.completions.create(
                model="web", messages=[{"role": "user", "content": prompt}],
                **dict(core.VIDEO_ANALYSIS_WEB_OPTS, saveImages=True))
            out = (resp.choices[0].message.content or "").strip()
            if out:
                return _bold_point_titles(out)
            raise RuntimeError("空回复")
        except Exception as e2:
            return f"（分析出错：AI 池两次都没成功（{e2}）。请稍后在这条笔记上点「AI 分析」重试）"


def _cx_adopt_web_images(analysis, note_stem):
    """AI 池回复里生成的示意图：web_model 先存在 memory/web_model_images/<批次>/，
    正文里写成 ![说明](cx-webimg:<批次>/<文件>)。这里把图片移进这条笔记自己的图片目录
    （video_notes/shots/<笔记名>/，删笔记时一起删），并把地址换成 /video_shot 的本地地址。
    图片找不到就把那行去掉，不留坏图。"""
    if not analysis or "cx-webimg:" not in analysis:
        return analysis
    import shutil as _shutil
    try:
        import web_model as _wm
        src_root = _wm.IMG_DIR
    except Exception:
        import agent_core
        src_root = agent_core.MEMORY_DIR / "web_model_images"
    dst = _cx_shots_dir() / note_stem
    base = "http://127.0.0.1:%d/video_shot?n=%s&f=" % (PORT, urllib.parse.quote(note_stem))
    used_batches = set()

    def _sub(m):
        alt, rel = m.group(1), m.group(2)
        if ".." in rel or "\\" in rel or rel.count("/") != 1:
            return ""
        batch, fn = rel.split("/")
        sp = src_root / batch / fn
        if not sp.exists():
            return ""
        try:
            dst.mkdir(parents=True, exist_ok=True)
            out = fn
            k = 2
            while (dst / out).exists():
                stem, ext = os.path.splitext(fn)
                out = "%s-%d%s" % (stem, k, ext)
                k += 1
            _shutil.move(str(sp), str(dst / out))
            used_batches.add(batch)
            return "![%s](%s%s)" % (alt or "示意图", base, urllib.parse.quote(out))
        except Exception:
            return ""
    out = re.sub(r"!\[([^\]]*)\]\(cx-webimg:([^)\s]+)\)", _sub, analysis)
    for b in used_batches:
        try:
            (src_root / b).rmdir()            # 批次目录空了就删掉
        except Exception:
            pass
    return out


def _split_title_from_analysis(text):
    """从分析正文里抽出开头那行「中文标题：xxx」，返回 (中文标题, 去掉该行后的正文)。
    模型可能写成「中文标题：」「中文标题:」，前面也可能带 # 或 **。找不到就返回 ("", 原文)。
    只在正文最前面的若干行里找，避免误伤后文。"""
    if not text:
        return "", text
    lines = text.split("\n")
    title = ""
    hit_idx = -1
    # 只在前 6 行里找（标题应该在最前面）
    for i in range(min(6, len(lines))):
        ln = lines[i].strip()
        if not ln:
            continue
        # 去掉可能的 markdown 前缀：#、**、-、>
        bare = re.sub(r"^[#>\-\*\s]+", "", ln).strip()
        m = re.match(r"^中文标题\s*[:：]\s*(.+)$", bare)
        if m:
            cand = m.group(1).strip().strip("：:").strip()
            # 去掉可能包裹的 ** 或引号
            cand = re.sub(r"^\*+|\*+$", "", cand).strip()
            cand = cand.strip('"').strip("“”").strip()
            if cand:
                title = cand
                hit_idx = i
            break
        # 第一行非空又不是标题行，就别再往下找了（防误伤）
        if i == 0 and not bare.startswith("中文标题"):
            # 允许标题不在第 0 行（前面可能有空行/代码块），继续找几行
            continue
    if hit_idx >= 0:
        # 删掉标题行，并把它前面残留的空行也清掉
        del lines[hit_idx]
        while lines and not lines[0].strip():
            lines.pop(0)
        return title, "\n".join(lines)
    return "", text


def _mm_extract_json(raw):
    """从模型返回里抠出思维导图 JSON（树或数组）。
    兼容三种常见情况：① 直接是 JSON；② 包了 ```json ... ``` 代码块；
    ③ 前后有多余说明文字。再不行就从第一个 { 或 [ 截到最后一个 } 或 ]。
    解析失败抛异常，交给上层兜底。"""
    import json as _json
    s = str(raw or "").strip()
    if not s:
        raise ValueError("空回复")
    # 去掉 ```json / ``` 围栏
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    # 先直接试
    try:
        return _json.loads(s)
    except Exception:
        pass
    # 再从首个 { 或 [ 截到末个 } 或 ]
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    ends = [i for i in (s.rfind("}"), s.rfind("]")) if i >= 0]
    if starts and ends:
        seg = s[min(starts):max(ends) + 1]
        return _json.loads(seg)
    raise ValueError("无法从回复中解析出 JSON")


def _mm_normalize(node, depth=0):
    """把模型给的结构规整成 simple-mind-map 风格的节点：
    { "data": {"text": "...", "note": "...", "color": "..."}, "children": [...] }
    兼容模型可能输出的简写（直接 {text, children} 或字符串）。深度限制 6 层防失控。"""
    if depth > 6:
        return None
    if node is None:
        return None
    # 字符串 → 叶子节点
    if isinstance(node, str):
        t = node.strip()
        return {"data": {"text": t}, "children": []} if t else None
    if not isinstance(node, dict):
        return None

    data_in = node.get("data")
    if isinstance(data_in, dict):
        text = data_in.get("text") or data_in.get("title") or data_in.get("name") or ""
        note = data_in.get("note") or data_in.get("desc") or ""
        color = data_in.get("color") or ""
    else:
        # 简写形态：{text:..., children:[...]}
        text = node.get("text") or node.get("title") or node.get("name") or ""
        note = node.get("note") or node.get("desc") or ""
        color = node.get("color") or ""

    text = str(text).strip()
    data_out = {"text": text or "·"}
    if note:
        data_out["note"] = str(note).strip()
    if color and isinstance(color, str) and color.strip().startswith("#"):
        data_out["color"] = color.strip()

    kids_in = node.get("children")
    kids_out = []
    if isinstance(kids_in, list):
        for k in kids_in:
            nk = _mm_normalize(k, depth + 1)
            if nk:
                kids_out.append(nk)
    return {"data": data_out, "children": kids_out}


def _cx_mindmap_from_text(analysis, title, use_local, model, on_progress=None):
    """让「网页模型」把一篇详细笔记(analysis) 归纳成思维导图结构(JSON 树)。
    返回 simple-mind-map 风格的根节点：{data:{text}, children:[...]}。
    设计与视频总结一致：默认交给网页模型；失败回退本地小模型。"""
    body_text = (analysis or "").strip()
    if not body_text:
        raise ValueError("没有可用于生成思维导图的内容")
    body_text = body_text[:12000]

    root_text = (title or "思维导图").strip()[:40]

    prompt = (
        "下面是一篇关于某个视频的中文笔记。请你把它的内容**提炼、归纳成一张思维导图的结构**，"
        "并以**严格的 JSON** 输出，方便程序渲染。\n\n"
        "【输出格式】只输出一个 JSON 对象（不要任何解释文字、不要 Markdown、不要代码块围栏），"
        "结构如下（节点可递归嵌套）：\n"
        "{\n"
        '  "data": { "text": "中心主题（一句话，6-16字）", "note": "可选，简短说明" },\n'
        '  "children": [\n'
        '    { "data": { "text": "分支主题", "note": "这个分支的简短说明", "color": "#8B0A50" },\n'
        '      "children": [\n'
        '        { "data": { "text": "更细的要点" }, "children": [] }\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "【内容要求】\n"
        "- 中心主题用这篇笔记的核心，最好结合标题。\n"
        "- 第一层分支 4-7 个，对应笔记里的几大块（如：背景、核心观点、关键事实、金句、建议、点评等，"
        "按实际内容来，不要硬凑）。\n"
        "- 每个一级分支下再展开 2-5 个子要点；重要的子要点可以再往下分一层。整体控制在 2-4 层。\n"
        '- "text" 要精炼（一般 4-20 字），是概括而不是照抄整句。\n'
        '- "note" 可选，用一句话补充，便于鼠标悬停查看；不需要就省略。\n'
        '- "color" 只在一级分支上给，用深色十六进制（每个 RGB 分量 < 200，避免浅色），不同分支颜色不同；'
        "子节点不用给颜色。\n"
        "- 不要输出空文本节点；不要把 JSON 包在 ```里。\n\n"
        f"【中心主题参考】{root_text}\n\n"
        f"=== 笔记正文 ===\n{body_text}\n"
    )

    def _ask(_client, _model):
        _kw = dict(core.VIDEO_ANALYSIS_WEB_OPTS) if core.is_web_model(_model) else {}
        resp = _client.chat.completions.create(
            model=_model, messages=[{"role": "user", "content": prompt}], **_kw)
        return (resp.choices[0].message.content or "").strip()

    # 与 video_summary 相同的模型解析逻辑：默认网页模型
    try:
        s_use_local, s_model = core.video_model(use_local, model)
    except Exception:
        s_use_local, s_model = use_local, model
    _is_claude_m = (s_model == "claude") or str(s_model).startswith("claude::")
    if (not s_use_local) and (not core.is_web_model(s_model)) and (not _is_claude_m) \
            and not os.environ.get("OPENAI_API_KEY") \
            and not os.environ.get("OPENAI_ADMIN_KEY"):
        s_use_local, s_model = False, "web"

    raw = None
    try:
        client = core.make_client_for(s_model, s_use_local, on_progress=on_progress)
        raw = _ask(client, s_model)
        tree = _mm_extract_json(raw)
    except Exception as e:
        # 网页 AI 池换一张卡再试一次（分析类任务不退回本地）
        try:
            if on_progress:
                try: on_progress("AI 池这次没成功，换一张卡重试思维导图…")
                except Exception: pass
            client = core.make_client_for("web", False, on_progress=on_progress)
            raw = _ask(client, "web")
            tree = _mm_extract_json(raw)
        except Exception as e2:
            raise RuntimeError(f"生成思维导图失败：{e2}") from e2

    # 规整：模型可能直接返回数组（多个一级分支），这时自动包一个中心节点
    if isinstance(tree, list):
        children = []
        for k in tree:
            nk = _mm_normalize(k, 1)
            if nk:
                children.append(nk)
        root = {"data": {"text": root_text or "思维导图"}, "children": children}
    else:
        root = _mm_normalize(tree, 0)
        if not root:
            raise RuntimeError("思维导图结构为空")
        # 中心节点文本兜底
        if not (root.get("data", {}).get("text") or "").strip():
            root["data"]["text"] = root_text or "思维导图"

    if not root.get("children"):
        raise RuntimeError("思维导图没有任何分支，请重试")
    return root


def _strip_think(raw):
    """去掉「思考型」本地模型（如 qwen3）输出里的 <think>…</think> 推理段，
    避免它把后面的「编号. 译文」逐行解析搅乱。
    处理三种常见形态：成对 <think></think>、被截断的未闭合 <think>、
    以及个别模型用的全角 ◁think▷…◁/think▷。"""
    if not raw:
        return ""
    s = str(raw)
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S | re.I)   # 成对
    s = re.sub(r"◁think▷.*?◁/think▷", "", s, flags=re.S | re.I)  # 个别模型的变体
    s = re.sub(r"<think>.*$", "", s, flags=re.S | re.I)          # 未闭合（被截断）
    return s.strip()


def _looks_english(s):
    """判断一段标题是不是「英文/非中文」内容（用来决定要不要把标题也翻成中文）。
    规则：含中文字符 → 视为中文，不翻；否则只要有英文字母就视为英文，翻。
    （纯数字 / 纯符号既无中文也无字母，返回 False，不去折腾。）"""
    s = (s or "").strip()
    if not s:
        return False
    if re.search(r"[\u4e00-\u9fff]", s):   # 已含中文 → 不翻
        return False
    return bool(re.search(r"[A-Za-z]", s))  # 有英文字母才翻


def _translate_lines(texts, use_local=True, model="qwen2.5"):
    """（2026-11）翻译标题是轻任务：本机有本地模型就一律用本地模型，不占用网页 AI 池。
    之前跟着聊天模型走网页 AI 池，几百条英文标题的翻译请求排队，把界面的连接全占满，
    导致「视频」页笔记列表一直「加载中」。"""
    try:
        _ul, _m = core.prefer_local_model(use_local, model)
        if _ul:
            use_local, model = True, _m
    except Exception:
        pass
    return _translate_lines_impl(texts, use_local, model)


def _translate_lines_impl(texts, use_local=True, model="qwen2.5"):
    """把多行短文本（如视频标题）批量翻译成简体中文。
    返回 (译文列表, 提示语)：列表与输入等长，翻不动的那条回退为空串（前端保持原文）；
    提示语为空表示一切正常，非空时前端可给个轻状态。

    策略（**严格用对话框里选的那个模型**，绝不背着用户偷偷改用网页模型）：
      · 用户选「本地模型」(如 qwen3:14b) → 只用这个本地模型；它没翻出来时，
        最多再用本地 qwen2.5 兜一次（仍是本地）。任何情况都不会去开网页浏览器。
      · 用户选「网页模型」(web) → 用网页模型一次性批量翻。
      · 用户选「Claude」 → 用 Claude 翻。
      · 思考型模型(qwen3)会先吐 <think> 推理，这里统一剥掉再解析，避免「解析为空 → 误判失败」。
      · 最终仍翻不出，返回空串 + 提示语，由前端提示用户（标题保持原文，不弹网页）。
    """
    items = [(t or "").replace("\n", " ").strip() for t in (texts or [])]
    if not any(items):
        return ["" for _ in items], ""
    # 防御性上限：一次最多翻 80 条，超出的保持空（前端通常已先行截断）
    n_all = len(items)
    capped = items[:80]
    numbered = "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(capped))
    prompt = (
        "你是翻译助手。把下面每一行视频标题翻译成**简洁、自然的简体中文**。\n"
        "要求：① 每行只输出「编号. 中文译文」，编号和原文一一对应；"
        "② 不要解释、不要输出原文、不要加多余的行；"
        "③ 人名、产品名、专有名词可保留英文。\n\n"
        "标题列表：\n" + numbered + "\n")

    def _run(_use_local, _model):
        client = core.make_client_for(_model, _use_local) if not _use_local else core.make_client(True)
        resp = client.chat.completions.create(
            model=_model, messages=[{"role": "user", "content": prompt}])
        raw = (resp.choices[0].message.content or "").strip()
        return _strip_think(raw)   # 先剥掉思考段，再交给 _parse

    def _parse(raw):
        """把「编号. 译文」逐行解析成 {idx: 译文}；解析不到算空。"""
        m_out = {}
        for line in (raw or "").splitlines():
            m = re.match(r"^\s*(\d+)[\.\)、:：]\s*(.+)$", line.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(capped):
                    m_out[idx] = m.group(2).strip()
        return m_out

    # —— 判断用户在对话框里选的是哪一类模型 ——
    m = (model or "").strip()
    is_claude = (m == "claude" or m.startswith("claude::"))
    try:
        is_web = core.is_web_model(m)
    except Exception:
        is_web = (m == "web")
    want_web = is_web and (not use_local)
    want_claude = is_claude and (not use_local)
    # 本地用哪个名字：空 / 误传成网页或 claude 时，本地兜底用 qwen2.5
    local_model = m if (m and not is_web and not is_claude) else "qwen2.5"

    out_map = {}
    note = ""

    if want_web:
        # 用户明确选了网页模型 → 用网页模型翻
        try:
            out_map = _parse(_run(False, m))
        except Exception:
            out_map = {}
    elif want_claude:
        # 用户选了 Claude → 用 Claude 翻
        try:
            out_map = _parse(_run(False, m))
        except Exception:
            out_map = {}
    else:
        # 本地：就用用户在对话框里选的那个本地模型（如 qwen3:14b）
        try:
            out_map = _parse(_run(True, local_model))
        except Exception:
            out_map = {}
        # 选的本地模型没翻出来、且不是 qwen2.5 → 用本地 qwen2.5 再兜一次（仍是本地，绝不开网页）
        if not out_map and local_model != "qwen2.5":
            try:
                out_map = _parse(_run(True, "qwen2.5"))
            except Exception:
                out_map = {}

    # 最终仍空：给个提示语（绝不背着用户改用网页模型）
    if not out_map:
        if want_web:
            note = "翻译没成功：网页模型这次没返回可用结果，稍后重试。"
        elif want_claude:
            note = "翻译没成功：Claude 这次没返回可用结果，检查 Claude 配置后重试。"
        else:
            note = ("翻译没成功：本地模型（%s）没返回可用结果。"
                    "请确认已启动 Ollama 且该模型已安装可用。" % (local_model,))

    return [out_map.get(i, "") for i in range(n_all)], note


def _clean_ai_tags(raw):
    """把模型给的标签输出清洗成干净的标签列表，尽量抗各种啰嗦/编号/前缀。"""
    import re
    if not raw:
        return []
    text = raw.strip()
    # 1) 若有「标签：xxx」「tags: xxx」这种，优先只取冒号后面那段
    m = re.search(r"(?:标签|tags?)\s*[:：]\s*(.+)", text, flags=re.I)
    if m:
        text = m.group(1)
    else:
        # 否则去掉任何以冒号结尾的解释性前缀（如“这条视频的标签是：”）
        text = re.sub(r"^[^:：\n]{0,30}[:：]\s*", "", text)
    # 2) 只看第一行（标签通常一行给完；多行多半是模型在解释）
    text = text.splitlines()[0] if text else ""
    # 3) 按常见分隔符切开
    parts = re.split(r"[、,，/|\s]+", text)
    seen, out = set(), []
    for p in parts:
        p = p.strip().strip("#＃“”\"'《》「」()（）[]【】.。·、-—:：").strip()
        # 去掉编号残留（如 "1." / "2、" / "①"）
        p = re.sub(r"^[\d①-⑩]+[.\)、]?", "", p).strip()
        if not p:
            continue
        # 过滤掉明显不是标签的词（太长、带空格、是解释性词语）
        if len(p) > 8 or " " in p:
            continue
        if p in ("标签", "tags", "tag", "无", "暂无", "和", "以及", "等"):
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= 3:
            break
    return out


def _cx_suggest_tag(title, analysis, use_local=True, model="qwen2.5"):
    """根据视频标题+分析，让模型总结 1-3 个二级标签（如 金融 / 逻辑 / AI）。
    失败返回 []，不影响主流程。"""
    base = (analysis or "")[:1200]
    prompt = (
        "请根据下面这条视频笔记的标题和内容，总结 1 到 3 个最贴切的中文二级标签，"
        "用来给它归类（例如：金融、逻辑、AI、创业、心理、职场、健康 等）。\n"
        "严格要求：直接输出标签，多个标签用顿号、分隔；每个标签 2-4 个字；"
        "不要写“标签：”，不要编号，不要解释，不要任何多余的字。\n"
        "示例输出：创业、经营管理、认知\n\n"
        f"标题：{title}\n\n内容节选：\n{base}\n\n直接输出标签：")
    raw = ""
    try:
        # 标签是轻量任务：本地小模型即可，快且稳；网页模型太慢这里不用
        client = core.make_client(True)
        resp = client.chat.completions.create(
            model="qwen2.5", messages=[{"role": "user", "content": prompt}])
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:
        # 本地不行再按调用方设置兜底试一次
        try:
            if core.is_web_model(model):
                raise RuntimeError("skip web for tag")
            client = core.make_client(use_local)
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}])
            raw = (resp.choices[0].message.content or "").strip()
        except Exception:
            return []
    return _clean_ai_tags(raw)


# 提取队列里「AI 分析没成功」的笔记：队列跑完后自动交给批量补分析
_video_failed_notes = []          # [(笔记文件名, use_local, model)]
_VIDEO_AUTO_RETRY = 1             # v90：只有像「网络抽风」的错才自动再试 1 次；别的错直接进「提取失败」清单，不再原样重跑两遍
# v90：像是网络一时不通的错误，值得自动再试一次
_VIDEO_TRANSIENT = ("timed out", "timeout", "Timeout", "超时", "Connection", "connection", "连接", "网络",
                    "reset", "HTTP Error 5", "502", "503", "504", "Temporary", "temporarily", "SSL", "EOF")
_VIDEO_STUCK_SEC = 600            # v90：一条任务这么久（秒）没有任何进展 → 自动取消，放进「提取失败」


# ════════════════ v90：提取失败清单（memory/video_failed.json）════════════════
# 最终没成功的任务（自动重试也没用 / 卡住被自动取消 / 重启时发现总是崩的）记在这里，
# 「已存的视频笔记」上面会显示「提取失败（N）」，每条可以「重新提取」或删掉。
# 同一个链接只记一条（再失败就更新原因和次数）；以后提取成功了自动从清单里拿掉。
_vf_lock = _threading.Lock()
_VF_KEEP = ("url", "local_path", "title", "level", "lang", "vocal", "mode", "use_local", "model", "screenshot", "link",
            "analyze", "author", "note_folder", "creator_url")


def _vf_path():
    import agent_core
    return agent_core.MEMORY_DIR / "video_failed.json"


def _vf_load():
    try:
        d = json.loads(_vf_path().read_text(encoding="utf-8"))
        return [x for x in (d.get("items") if isinstance(d, dict) else d) or [] if isinstance(x, dict) and x.get("id")]
    except Exception:
        return []


def _vf_save(items):
    try:
        p = _vf_path()
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"items": items[-300:]}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(str(tmp), str(p))
    except Exception as e:
        _clog("视频", "记录提取失败清单出错：%s" % e)


def _vf_key(job):
    return ((job or {}).get("local_path") or (job or {}).get("url") or "").strip()


def _vf_add(job, error):
    import time as _t
    k = _vf_key(job)
    if not k:
        return
    with _vf_lock:
        items = _vf_load()
        old = next((x for x in items if _vf_key(x) == k), None)
        rec = old or {"id": "%x" % int(_t.time() * 1000), "tries": int(job.get("_vf_tries") or 0)}
        rec.update({f: job.get(f) for f in _VF_KEEP if job.get(f) not in (None, "")})
        rec["title"] = (job.get("title") or rec.get("title") or "").strip()
        rec["error"] = (str(error or "") or "原因不明").strip()[:400]
        rec["at"] = _t.strftime("%Y-%m-%d %H:%M")
        rec["tries"] = int(rec.get("tries") or 0) + 1
        if old:
            items.remove(old)
        items.append(rec)
        _vf_save(items)
    _clog("视频", "📌 已放进「提取失败」清单（第 %d 次没成功），以后可以点「重新提取」" % rec["tries"])


def _vf_remove(key=None, ids=None):
    with _vf_lock:
        items = _vf_load()
        keep = [x for x in items if not ((key and _vf_key(x) == key) or (ids is not None and x.get("id") in ids))]
        if len(keep) != len(items):
            _vf_save(keep)
        return [x for x in items if x not in keep]
# 明显重试也没用的错误（链接本身不对 / 视频没了 / 用户取消），不自动重排
_VIDEO_NO_RETRY = ("Unsupported URL", "已取消", "不存在", "已删除", "已被删除", "私密", "Private video",
                   "This video is unavailable", "Video unavailable", "非法", "找不到文件", "文件不存在")


def _video_flush_failed_notes():
    """队列空了：把分析没成功的笔记交给批量补分析（挂机时不用人去点）。"""
    if not _video_failed_notes:
        return
    items = list(_video_failed_notes)
    del _video_failed_notes[:]
    names = []
    for nm, _ul, _m in items:
        if nm not in names:
            names.append(nm)
    try:
        _note_batch_enqueue(names, items[-1][1], items[-1][2], "视频队列里分析没成功的笔记")
    except Exception as e:
        _clog("视频", "⚠ 自动补分析没能开始：%s" % e)


def _video_worker():
    """逐个处理队列里的视频，一次一个。"""
    import time as _time
    import datetime
    import video_transcribe
    while True:
        with _video_lock:
            if not _video_q:
                _video_worker_on["v"] = False
                _video_state["running"] = False
                _video_state["queue_len"] = 0
                _video_state["queue"] = []
                _video_state["current_label"] = ""
                _video_state["stage"] = ""
                _video_state["detail"] = ""
                _video_current["job"] = None
                _save_video_queue()          # 队列清空，写盘（之后重启不会再有残留任务）
                _threading.Thread(target=_video_flush_failed_notes, daemon=True).start()
                return
            job = _video_q.pop(0)
            # 规范化 URL：历史持久化里可能存了 iesdouyin 分享页长链（yt-dlp 不认，
            # 会报 Unsupported URL）。这里统一转回标准抖音链接，后续下载/爬标题都用它。
            try:
                _nu = _normalize_video_url(job.get("url") or "")
                if _nu and _nu != job.get("url"):
                    job["url"] = _nu
            except Exception:
                pass
            # 取消标记：放弃这条 + 后面的都已被清空，直接收尾退出
            if _video_cancel.get("all"):
                _video_cancel["all"] = False
                _video_worker_on["v"] = False
                _video_state["running"] = False
                _video_state["queue_len"] = 0
                _video_state["queue"] = []
                _video_state["current_label"] = ""
                _video_state["stage"] = ""
                _video_state["detail"] = ""
                _video_current["job"] = None
                _save_video_queue()
                return
            job.pop("_stuck", None)          # v90：上次的「卡住」标记不带到这一次
            _video_current["job"] = job      # 标记正在处理（崩溃/关闭后重启能续上这条）
            # 失败计数 +1 并存盘：若这条任务反复失败/崩溃，计数会累加，
            # 下次启动 _restore_video_queue 看到 fail_count>=2 就丢弃它，不再卡住后面。
            # 任务成功结束时会整条删除（_video_current["job"]=None + 存盘），计数自然清零。
            try:
                job["fail_count"] = int(job.get("fail_count") or 0) + 1
            except Exception:
                job["fail_count"] = 1
            _save_video_queue()              # 持久化：current=这条（含计数）, pending=剩下的
            _video_state["queue"] = [{"url": j["url"], "title": j.get("title") or ""}
                                     for j in _video_q]
            _video_state["queue_len"] = len(_video_q)
        _video_state["running"] = True
        _video_state["current_url"] = job["url"]
        # 任务开始：往控制台打一行，让用户知道「现在开始处理这条了」
        _clog("视频", "▶ 开始处理：%s（队列还剩 %d 个）"
              % ((job.get("title") or job["url"])[:40], len(_video_q)))
        # 正在处理的任务：优先显示标题（入队时可能已爬到），否则先显示链接，
        # 同时异步补爬一次标题，爬到就更新显示——让用户知道现在提取的是哪个视频。
        _video_state["current_label"] = job.get("title") or job["url"]
        if not job.get("title"):
            def _fill_cur_title(_u=job["url"], _job=job):
                try:
                    t = _quick_title(_u)
                    if t and _video_state.get("current_url") == _u:
                        _job["title"] = t
                        _video_state["current_label"] = t
                except Exception:
                    pass
            _threading.Thread(target=_fill_cur_title, daemon=True).start()

        # 后台预爬「所有排队任务」的标题并回填，让排队列表也显示视频名而非链接。
        # 逐个爬（不并发，免得抢网络/被抖音限流），爬到就写进 _video_q 对应项 +
        # 刷新 _video_state["queue"]，前端轮询即可看到标题。
        def _prefetch_queue_titles():
            try:
                import time as _pt
                with _video_lock:
                    pending = list(_video_q)
                for j in pending:
                    if j.get("title"):
                        continue
                    u = (j.get("url") or "").strip()
                    if not u:
                        continue
                    # 最多试 2 次，每次之间隔一下，降低抖音对密集请求的限流概率
                    t = ""
                    for attempt in range(2):
                        t = _quick_title(u)
                        if t:
                            break
                        _pt.sleep(2)
                    if not t:
                        continue
                    with _video_lock:
                        j["title"] = t
                        _video_state["queue"] = [
                            {"url": k["url"], "title": k.get("title") or ""}
                            for k in _video_q]
                        _save_video_queue()
                    _pt.sleep(1)   # 相邻两个之间也歇一下，别太密
            except Exception:
                pass
        _threading.Thread(target=_prefetch_queue_titles, daemon=True).start()
        _video_state["stage"] = "准备"
        _video_state["detail"] = ""
        _video_state["elapsed"] = 0
        start = _time.time()
        tick = {"on": True}

        # ── 运行台记录：收集这条视频任务经历的每个阶段，结束时写进 harness 运行台 ──
        run_steps = []          # [阶段名]，给运行台展示「每一步」
        _last_stage = {"name": ""}
        # 任务一开始就在运行台写一条「进行中」记录，让你立刻看到它在跑、走到哪步。
        _run_id = ""
        try:
            import harness as _hn
            _vtitle0 = "视频提取：" + (job.get("url") or "")[-40:]
            _run_id = _hn.begin_run(kind="video", title=_vtitle0, tools=["准备"])
        except Exception:
            _run_id = ""

        def _ticker():
            last_sig, last_at = None, _time.time()
            while tick["on"]:
                _video_state["elapsed"] = int(_time.time() - start)
                # v90：看门狗——阶段和进度文字 10 分钟都没变过，多半卡死了：取消这一条，记进「提取失败」
                sig = (_video_state.get("stage"), _video_state.get("detail"))
                if sig != last_sig:
                    last_sig, last_at = sig, _time.time()
                elif (not job.get("_stuck") and _time.time() - last_at > _VIDEO_STUCK_SEC
                      and sig[0] != "排队等待"):
                    job["_stuck"] = "「%s」这一步 %d 分钟没有任何进展" % (sig[0] or "处理", _VIDEO_STUCK_SEC // 60)
                    _clog("视频", "⏱ %s，自动取消这一条（后面排队的照常处理）" % job["_stuck"])
                    try:
                        video_transcribe.CANCEL["on"] = True
                    except Exception:
                        pass
                _time.sleep(1)
        _threading.Thread(target=_ticker, daemon=True).start()

        def cb(stage, detail=""):
            _video_state["stage"] = stage
            _video_state["detail"] = detail
            # 阶段名变化时，记一步，并实时更新运行台里这条「进行中」记录
            try:
                if stage and stage != _last_stage["name"]:
                    _last_stage["name"] = stage
                    run_steps.append(stage)
                    # 阶段变化时往控制台打一行，让用户实时看到「软件在做哪一步」
                    _clog("视频", "%s%s" % (stage, ("：" + detail) if detail else ""))
                    if _run_id:
                        import harness as _hn2
                        _hn2.update_run(_run_id, tools=list(run_steps))
            except Exception:
                pass

        # 取消标记：开跑前再检查一次（用户可能在准备阶段点了取消）
        if _video_cancel.get("all"):
            tick["on"] = False
            with _video_lock:
                _video_cancel["all"] = False
                _video_q.clear()
                _video_state["running"] = False
                _video_state["queue"] = []
                _video_state["queue_len"] = 0
                _video_state["current_label"] = ""
                _video_state["stage"] = ""
                _video_state["detail"] = ""
                _video_current["job"] = None
                _video_worker_on["v"] = False
                _save_video_queue()
            return

        # ★全局闸门：与对话里的视频提取共用，确保同一时间只有一个提取+总结任务在跑。
        if video_transcribe.extract_busy():
            _video_state["stage"] = "排队等待"
            _video_state["detail"] = "前面有视频提取任务在进行，排队等待…"
        video_transcribe.extract_gate.acquire()
        try:
            do_screenshot = bool(job.get("screenshot"))
            do_link = bool(job.get("link"))
            sub_mode = job.get("mode") or "auto"   # auto / subtitle_only / transcribe
            local_path = (job.get("local_path") or "").strip()
            _dimp = None
            try:
                import doc_import as _dimp
            except Exception as _e:
                _clog("视频", "文档导入模块加载失败：%s" % _e)
            if local_path and _dimp is not None and _dimp.is_doc_path(local_path):
                # v65：本地文档（PDF / Word / Excel / PPT / TXT / Markdown…）：直接读出全文
                res = _dimp.extract_file(local_path, progress_cb=cb)
            elif local_path:
                # 本地文件任务：跳过链接解析与下载，直接听写本地文件
                res = video_transcribe.extract_local(
                    local_path, level=job["level"], progress_cb=cb, lang=job.get("lang") or "zh",
                    vocal=bool(job.get("vocal")))
            elif job.get("intake") == "github":
                # v112：GitHub 项目——读项目信息和 README，摘出安装方法
                import intake as _ik
                res = _ik.research_github_url(job["url"], progress_cb=cb)
            elif job.get("intake") == "text":
                # v112：一段文字——直接存成笔记
                import intake as _ik
                res = _ik.text_note(job.get("text") or "")
            elif _dimp is not None and _dimp.article_url(job["url"]):
                # v65：不是视频网站的链接 → 先当文章读；读不到正文，再当视频试一次（和以前一样）
                res = _dimp.extract_url(job["url"], progress_cb=cb)
                if (not res.get("ok")) and res.get("try_video") and not _video_cancel.get("all"):
                    cb("解析链接", "没读到文章正文，试试当视频提取…")
                    _r2 = video_transcribe.extract(job["url"], level=job["level"], progress_cb=cb,
                                                   need_video=do_screenshot, mode=sub_mode,
                                                   lang=job.get("lang") or "zh", vocal=bool(job.get("vocal")))
                    if isinstance(_r2, dict) and (_r2.get("ok") or _r2.get("cancelled")):
                        res = _r2
                    else:
                        res = {"ok": False, "error": "没读到文章正文（%s）；当视频提取也没成功（%s）" % (
                            (res.get("error") or "")[:150], ((_r2 or {}).get("error") or "")[:150])}
            else:
                res = video_transcribe.extract(job["url"], level=job["level"],
                                               progress_cb=cb,
                                               need_video=do_screenshot,
                                               mode=sub_mode, lang=job.get("lang") or "zh",
                                               vocal=bool(job.get("vocal")))
            if isinstance(res, dict) and res.get("source") in ("doc", "article"):
                do_screenshot = do_link = False      # v65：文档 / 文章没有画面，也没有时间轴
                if res.get("ok"):
                    _clog("视频", "📄 读到%s《%s》：%d 字" % (res.get("doc_kind") or "文档",
                                                          (res.get("title") or "")[:30], len(res.get("transcript") or "")))
            # ★用户点了「全部取消」：提取被中断（或恰好刚结束）→ 不再做
            #   AI 分析和保存，直接把结果标记为"已取消"。
            if _video_cancel.get("all") or (isinstance(res, dict) and res.get("cancelled")):
                res = {"ok": False, "cancelled": True, "error": "已取消"}
            # v88：语音识别出来的原文先整理一下（AI 加标点、按意思分段）；文章 / 文档本来就有标点，不用
            if (isinstance(res, dict) and res.get("ok") and res.get("transcript")
                    and res.get("source") not in ("doc", "article") and not _video_cancel.get("all")):
                try:
                    import transcript_tidy as _tt
                    if _tt.auto_on() and (job.get("lang") or "zh") == "zh" and len(_tt._bare(res["transcript"])) >= 60:
                        cb("整理原文", "让 AI 加标点、按意思分段…")
                        _new, _msg = _tidy_text(res["transcript"], progress=lambda m: cb("整理原文", m),
                                                force=True, wait_pool=False)
                        res["transcript"] = _new
                        _clog("整理原文", _msg)
                except Exception as _e:
                    _clog("整理原文", "跳过（%s）" % _e)
            if res.get("ok") and not job.get("analyze", False):     # v66：没说要分析的任务，一律只提取原文
                # ★「仅提取文字稿」模式（新增）：完全不调用 AI——分析、补标签、
                #   翻标题三处 AI 全部跳过（避免和别的软件抢占同一个 AI），只保存
                #   文字稿；带时间戳的分段另存 video_notes/segments/<笔记名>.json
                #   侧车文件，等以后在笔记列表点「AI 分析」补做时，仍能照常生成
                #   「跳转原片」时间标记（插图补不了：视频画面下面就清掉了）。
                cb("保存", "只提取原文，不做 AI 分析（需要时点「🤖 AI 分析」）…")
                transcript = res["transcript"]
                segments = res.get("segments") or []
                title = res.get("title") or "（无标题）"
                # 作者：平台抓到的优先；本地文件没有作者 → 用导入时用户填的
                uploader = (res.get("uploader") or job.get("author") or "").strip()
                clean_url = res.get("url") or job["url"]
                video_path = res.get("video_path")
                # 标签：只保留平台自带的话题标签（爬取所得，不走 AI）
                tags = []
                for _t in (res.get("platform_tags") or []):
                    _t = (_t or "").strip().lstrip("#").strip()
                    if _t and _t not in tags:
                        tags.append(_t)
                tags = tags[:6]
                ts = datetime.datetime.now()
                safe = "".join(c for c in title[:20]
                               if c.isalnum() or c in " 　-_") or "video"
                fname = (f"{ts.strftime('%Y%m%d-%H%M%S')}-{safe}.md"
                         .replace(" ", "_"))
                note_stem = fname[:-3]
                # segments 侧车：补分析时打「跳转原片」标记要靠它（方案 B）
                try:
                    if segments:
                        _payload = {
                            "url": clean_url,
                            "link": bool(job.get("link")), "lang": job.get("lang") or "zh", "local_path": job.get("local_path") or "",
                            "segments": [
                                dict({"start": s.get("start", 0),
                                      "text": (s.get("text") or "")},
                                     **({"end": s.get("end")} if s.get("end") is not None else {}))
                                for s in segments],
                        }
                        _cx_segments_dir().joinpath(note_stem + ".json").write_text(
                            json.dumps(_payload, ensure_ascii=False),
                            encoding="utf-8")
                except Exception:
                    pass
                # 用完即清：与正常流程一致，删掉为提取下载的视频文件（本地文件除外）
                try:
                    is_local_job = bool(res.get("local_path")) or bool(job.get("local_path"))
                    if video_path and not is_local_job:
                        import shutil as _shutil
                        _vp = video_transcribe._video_file_dir(clean_url)
                        _shutil.rmtree(str(_vp), ignore_errors=True)
                except Exception:
                    pass
                placeholder = ("（这条只提取了原文，还没做 AI 分析。需要的时候点「🤖 AI 分析」就行："
                               "提取完成那一行、笔记列表里这一条的右边、或者打开笔记后的按钮都可以。）")
                tag_line = ("- 标签：" + "、".join(tags) + "\n") if tags else ""
                doc = (f"# {title}\n\n"
                       f"- 来源链接：{clean_url}\n"
                       f"- 作者：{uploader}\n"
                       f"- 提取时间：{ts.strftime('%Y-%m-%d %H:%M')}\n"
                       f"- 状态：未分析\n"
                       f"{_vn_doc_meta(res)}"
                       f"{tag_line}\n"
                       f"## 🤖 AI 分析\n\n{placeholder}\n\n"
                       f"---\n\n## 📝 完整文字稿\n\n{transcript}\n")
                try:
                    _cx_video_dir().joinpath(fname).write_text(doc, encoding="utf-8")
                except Exception:
                    pass
                res["analysis"] = placeholder
                res["saved_as"] = fname
                res["title_original"] = title
                res["unanalyzed"] = True
                # 若任务指定了归档文件夹（导入文件夹时可选），这条笔记自动归进去
                try:
                    if (job.get("note_folder") or "").strip():
                        _vn_assign_folder(fname, job.get("note_folder"))
                except Exception:
                    pass
            elif res.get("ok"):
                cb("AI 分析", "让模型把文字稿总结成笔记…")
                transcript = res["transcript"]
                segments = res.get("segments") or []
                title = res.get("title") or "（无标题）"
                uploader = (res.get("uploader") or job.get("author") or "").strip()
                clean_url = res.get("url") or job["url"]
                video_path = res.get("video_path")
                _ai_t = _ai_gate.acquire("视频提取《%s》的 AI 分析" % (title or "")[:24],      # v67：排队等 AI 池
                                         on_wait=lambda b: cb("排队等 AI", b),
                                         should_stop=lambda: bool(_video_cancel.get("all")))
                if _ai_t is None:
                    analysis = "（分析出错：已取消）"
                else:
                    analysis = _cx_analyze_transcript(
                        transcript, title, job["use_local"], job["model"],
                        on_progress=lambda m: cb("AI 分析", m),
                        segments=segments,
                        do_screenshot=do_screenshot, do_link=do_link,
                        src_noun=res.get("src_noun"))
                # ★标题翻译（随分析一起完成）：分析模型已被要求在开头输出「中文标题：xxx」，
                #   这里把它抽出来当中文标题，并从正文里删掉这行（避免笔记里重复出现）。
                title_from_ai, analysis = _split_title_from_analysis(analysis)
                # ★标签：优先用平台自带的话题标签（抖音 #话题，最准），不够再让 AI 补。
                cb("AI 分析", "归纳标签…")
                platform_tags = res.get("platform_tags") or []
                try:
                    ai_tags = _cx_suggest_tag(title, analysis,
                                              job["use_local"], job["model"])
                except Exception:
                    ai_tags = []
                # 平台标签在前、AI 标签在后，去重，最多取 6 个
                tags = []
                for _t in list(platform_tags) + list(ai_tags):
                    _t = (_t or "").strip().lstrip("#").strip()
                    if _t and _t not in tags:
                        tags.append(_t)
                tags = tags[:6]
                ts = datetime.datetime.now()
                safe = "".join(c for c in title[:20]
                               if c.isalnum() or c in " 　-_") or "video"
                fname = (f"{ts.strftime('%Y%m%d-%H%M%S')}-{safe}.md"
                         .replace(" ", "_"))
                # AI 池回复里的示意图：移进这条笔记的图片目录
                try:
                    analysis = _cx_adopt_web_images(analysis, fname[:-3])
                except Exception:
                    pass

                # ★插图 / 跳转原片后处理：把 AI 插的标记替换成真截图 / 跳转链接。
                #   截图存到 video_notes/shots/<笔记stem>/，前端通过 /video_shot 取。
                if do_screenshot or do_link:
                    try:
                        import video_screenshot
                        note_stem = fname[:-3] if fname.endswith(".md") else fname
                        shots_dir = _cx_shots_dir() / note_stem
                        img_base = ("http://127.0.0.1:%d/video_shot?n=%s&f="
                                    % (PORT, urllib.parse.quote(note_stem)))
                        if do_screenshot:
                            cb("AI 分析", "正在按标记抓取视频截图…")
                        analysis, _shots = video_screenshot.post_process(
                            analysis, url=clean_url, video_path=video_path,
                            shots_dir=shots_dir, image_url_base=img_base,
                            do_screenshot=do_screenshot, do_link=do_link)
                    except Exception:
                        pass  # 插图/跳转失败不影响笔记本体

                # 用完即清：删掉为截图下载的视频画面文件，省空间
                #   注意：本地文件任务的 video_path 就是用户自己的源文件，绝不能删！
                try:
                    is_local_job = bool(res.get("local_path")) or bool(job.get("local_path"))
                    if video_path and not is_local_job:
                        import shutil as _shutil
                        _vp = video_transcribe._video_file_dir(clean_url)
                        _shutil.rmtree(str(_vp), ignore_errors=True)
                except Exception:
                    pass

                tag_line = ("- 标签：" + "、".join(tags) + "\n") if tags else ""
                # ★中文标题：优先用分析模型随手翻好的「中文标题：xxx」（最可靠，和正文同一次调用）；
                #   万一分析里没给（模型没照格式输出），且原标题是英文，再退回单独翻一次。
                title_zh = ""
                if title_from_ai and title_from_ai.strip() and title_from_ai.strip() != title.strip():
                    title_zh = title_from_ai.strip()
                elif _looks_english(title):
                    try:
                        cb("AI 分析", "翻译标题…")
                        _zh_list, _ = _translate_lines(
                            [title], use_local=job["use_local"], model=job["model"])
                        _cand = (_zh_list[0] if _zh_list else "").strip()
                        if _cand and _cand != title:
                            title_zh = _cand
                    except Exception:
                        title_zh = ""
                display_title = title_zh or title
                _ai_gate.release(_ai_t)          # v67：AI 用完了，让给排队的下一件事
                _ai_t = None
                orig_line = (f"- 原标题：{title}\n" if title_zh else "")
                doc = (f"# {display_title}\n\n"
                       f"- 来源链接：{clean_url}\n"
                       f"- 作者：{uploader}\n"
                       f"- 提取时间：{ts.strftime('%Y-%m-%d %H:%M')}\n"
                       f"{orig_line}"
                       f"{_vn_doc_meta(res)}"
                       f"{tag_line}\n"
                       f"## 🤖 AI 分析\n\n{analysis}\n\n"
                       f"---\n\n## 📝 完整文字稿\n\n{transcript}\n")
                try:
                    _cx_video_dir().joinpath(fname).write_text(doc, encoding="utf-8")
                except Exception:
                    pass
                res["analysis"] = analysis
                res["saved_as"] = fname
                if (analysis or "").lstrip().startswith("（分析出错"):
                    # 文字稿已存好，只是 AI 分析没成功：队列跑完后自动补
                    _video_failed_notes.append((fname, job.get("use_local", True), job.get("model", "qwen2.5")))
                    _clog("视频", "⚠ 《%s》文字稿已保存，但 AI 分析没成功，队列跑完后会自动补分析" % title[:20])
                # 让「提取完成」的结果卡 / 视频列表也直接显示中文标题（原标题另存一份备查）
                res["title_original"] = title
                res["title"] = display_title
                # 若任务指定了归档文件夹（导入文件夹时可选），这条笔记自动归进去
                try:
                    if (job.get("note_folder") or "").strip():
                        _vn_assign_folder(fname, job.get("note_folder"))
                except Exception:
                    pass
            # v59：博主板块——填了博主主页就按它绑；没填就根据视频链接自动找博主主页（头像、昵称、粉丝数）
            if isinstance(res, dict) and res.get("ok") and res.get("saved_as"):
                try:
                    _vn_canon_new_note(job, res)       # v64：合并过的小号 → 大号名；作者和文件夹同名 → 归进去
                except Exception as _e:
                    _clog("博主", "整理新笔记的博主名出错：%s" % _e)
                try:
                    _cr = (None if res.get("source") in ("doc", "article")
                           else _vn_creator_after_save(job, res, cb))
                    if _cr:
                        res["creator"] = _cr
                except Exception as _e:
                    _clog("博主", "识别博主主页出错：%s" % _e)
            _video_state["result"] = res
        except Exception as e:
            _video_state["result"] = {"ok": False, "error": str(e)}
        finally:
            tick["on"] = False
            if job.get("_stuck") and not (_video_state.get("result") or {}).get("ok"):   # v90：看门狗取消的——算失败
                _video_state["result"] = {"ok": False, "error": "卡住了：%s，已自动取消" % job["_stuck"]}
                try:
                    video_transcribe.CANCEL["on"] = False
                except Exception:
                    pass
            _ai_gate.release_thread()        # v67：保险，万一出错没还 AI 池
            _video_state["result_id"] += 1
            try:
                video_transcribe.extract_gate.release()
            except (RuntimeError, ValueError):
                pass
            # ── 更新运行台记录：把开头那条「进行中」更新成最终结果（成败+步骤+耗时+标题）──
            try:
                import harness
                _res = _video_state.get("result") or {}
                _ok = bool(_res.get("ok"))
                _vtitle = (_res.get("title") or "").strip()
                if not _vtitle:
                    _u = job.get("url") or ""
                    _vtitle = "视频提取：" + (_u[-40:] if _u else "（未知链接）")
                _stages = list(run_steps) or ["视频提取"]
                # 叙述性完成提示：看队列里还有没有下一个，给运行台一句话说明任务流转
                with _video_lock:
                    _remain = len(_video_q)
                if _ok:
                    if _remain > 0:
                        _note = "✅ 已完成《%s》，继续处理下一个（还剩 %d 个）" % (_vtitle[:20], _remain)
                    else:
                        _note = "✅ 已完成《%s》，队列已清空，等待新任务" % (_vtitle[:20])
                else:
                    if isinstance(_res, dict) and _res.get("cancelled"):
                        _note = "🛑 已按你的要求取消（队列已清空）"
                    elif _remain > 0:
                        _note = "⚠ 这条没成功，继续处理下一个（还剩 %d 个）" % _remain
                    else:
                        _note = "⚠ 这条没成功，队列已清空，等待新任务"
                if _run_id:
                    harness.finish_run(
                        _run_id, tools=_stages,
                        error=("" if _ok else (_res.get("error") or "提取未成功")),
                        outcome=("done" if _ok else "stopped"),
                        title=_vtitle, note=_note)
                else:
                    # begin_run 当时没拿到 id（极少见）→ 退化成补记一条完整记录，不丢
                    harness.record_run(
                        kind="video", title=_vtitle, tools=_stages,
                        steps=len(_stages),
                        error=("" if _ok else (_res.get("error") or "提取未成功")),
                        outcome=("done" if _ok else "stopped"),
                        seconds=int(_time.time() - start))
            except Exception:
                pass  # 运行台记录失败绝不影响主流程
            # 往控制台也打一条明确的完成报告，让用户看日志就知道任务流转。
            try:
                _secs = int(_time.time() - start)
                _msg = locals().get("_note") or "✅ 这条已处理完"
                # 失败时把原因也带上，省得用户对着「没成功」一头雾水
                if not _ok:
                    _err = (_res.get("error") or "").strip() if isinstance(_res, dict) else ""
                    if _err:
                        _msg = _msg + "　原因：" + _err[:120]
                _clog("视频", "%s（用时 %d 秒）" % (_msg, _secs))
            except Exception:
                pass
            # 这条处理完（成功或失败都算处理过），从持久化里移除，避免重启又跑一遍
            with _video_lock:
                _video_current["job"] = None
                # 失败的任务自动排到队尾再试（最多再试 _VIDEO_AUTO_RETRY 次），挂机时不用人管
                try:
                    _r = _video_state.get("result") or {}
                    _err = str(_r.get("error") or "")
                    if (not _r.get("ok") and not _r.get("cancelled") and not _video_cancel.get("all")
                            and not job.get("_stuck")
                            and not any(k in _err for k in _VIDEO_NO_RETRY)
                            and any(k in _err for k in _VIDEO_TRANSIENT)
                            and int(job.get("auto_retry") or 0) < _VIDEO_AUTO_RETRY):
                        job["auto_retry"] = int(job.get("auto_retry") or 0) + 1
                        job["fail_count"] = 0
                        _video_q.append(job)
                        _video_state["queue"] = [{"url": j["url"], "title": j.get("title") or ""}
                                                 for j in _video_q]
                        _video_state["queue_len"] = len(_video_q)
                        _clog("视频", "🔁 这条没成功，已排到队尾自动重试（第 %d / %d 次）"
                              % (job["auto_retry"], _VIDEO_AUTO_RETRY))
                except Exception:
                    pass
                _save_video_queue()
                _requeued = any(j is job for j in _video_q)
            # v90：最终没成功（不是你点的取消、也不会再自动重试）→ 放进「提取失败」清单；成功了 → 从清单拿掉
            try:
                _r = _video_state.get("result") or {}
                if _r.get("ok"):
                    _vf_remove(key=_vf_key(job))
                elif not _requeued and not (_r.get("cancelled") and not job.get("_stuck")):
                    _vf_add(job, _r.get("error") or "提取没成功")
                    _r["failed_saved"] = True
            except Exception as _e:
                _clog("视频", "记录提取失败出错：%s" % _e)
            # v84：从飞书发来的任务，做完在飞书里回一句
            if job.get("notify"):
                try:
                    import feishu_inbox
                    feishu_inbox.job_done(job, _video_state.get("result") or {}, requeued=_requeued)
                except Exception as _e:
                    _clog("飞书", "回提取结果失败：%s" % _e)
        # 继续处理下一个


# ════════════════ 已存笔记「补做 AI 分析」（仅提取模式的后半程）════════════════
# 「仅提取文字稿」存下来的笔记（md 里带「- 状态：未分析」），可以随时在笔记列表
# 点「AI 分析」补做。补做在后台线程跑，前端轮询 /video_note_analyze_progress 看进度。
_note_an_lock = _threading.Lock()
_note_an_state = {"running": False, "name": "", "stage": "",
                  "error": "", "ok": False, "done_id": 0}

# 批量补分析：一条一条地分析（每条都会在 AI 池换一张新卡、开新对话，互不串）
_note_batch = {"running": False, "total": 0, "done": 0, "ok": 0, "fail": 0,
               "current": "", "stop": False, "errors": [], "started": 0, "finished": 0}


def _time_now():
    import time as _t
    return _t.time()


_BATCH_BACKOFF_MIN = [3, 5, 10, 20, 30]     # 连续失败后自动等多久再接着跑（分钟），之后都按 30 分钟
_BATCH_MAX_TRIES = 4                       # 每条笔记最多试几次


def _batch_sleep(seconds, why):
    """批量分析里的「等一会儿再接着跑」：可被「停止」/「现在就继续」打断。返回是否被停止。"""
    import time as _time
    _note_batch["waiting"] = why
    _note_batch["resume_at"] = _time.time() + seconds
    _note_batch["resume_now"] = False
    try:
        while _time.time() < _note_batch["resume_at"]:
            if _note_batch["stop"]:
                return True
            if _note_batch.get("resume_now"):
                break
            _time.sleep(1)
        return bool(_note_batch["stop"])
    finally:
        _note_batch["waiting"] = ""
        _note_batch["resume_at"] = 0


def _pool_ready_for_batch():
    """接着跑之前先测一下 AI 池网站能不能连上。返回 (能否连上, 说明)。"""
    try:
        import web_model
        if hasattr(web_model, "probe_pool"):
            return web_model.probe_pool()
    except Exception as e:
        return False, str(e)[:120]
    return True, ""


def _note_batch_worker(names, use_local, model):
    """一条一条补分析。挂机友好：
    · 连续 2 条失败不再永久暂停，而是等 3 / 5 / 10 / 20 / 30 分钟后自动接着跑，接着跑之前先测 AI 池能不能连上；
    · 每条最多试 4 次；整批跑完后，把失败的再补一遍；
    · 跑的过程中新加进来的笔记（视频队列里分析失败的）也会接着补。"""
    import time as _time
    tries = {}
    pending = list(names)
    backoff_i = 0
    try:
        while not _note_batch["stop"]:
            extra = _note_batch.get("extra") or []
            if extra:
                _note_batch["extra"] = []
                for nm in extra:
                    if nm not in pending:
                        pending.append(nm)
                        _note_batch["total"] += 1
            if not pending:
                # 第一遍跑完：失败但还没试满的，再补一遍
                again = [n for n in _note_batch.get("failed_names", [])
                         if tries.get(n, 0) < _BATCH_MAX_TRIES and (_cx_video_dir() / n).exists()]
                if not again:
                    break
                _note_batch["failed_names"] = []
                _clog("视频", "🔁 批量补分析：第一遍跑完，再补一遍没成功的 %d 条" % len(again))
                _note_batch["round"] = _note_batch.get("round", 1) + 1
                pending = again
                continue
            name = pending.pop(0)
            if not (_cx_video_dir() / name).exists():
                continue                          # 期间被删掉了
            # 等单条补分析（如果有人在点单条）先结束，再占用
            while True:
                with _note_an_lock:
                    if not _note_an_state["running"]:
                        _note_an_state.update({"running": True, "name": name, "stage": "准备",
                                               "error": "", "ok": False, "title": "",
                                               "author": "", "started_at": _time.time()})
                        break
                if _note_batch["stop"]:
                    break
                _time.sleep(1.5)
            if _note_batch["stop"]:
                break
            _note_batch["current"] = name
            tries[name] = tries.get(name, 0) + 1
            _note_analyze_worker(name, use_local, model)     # 同步跑完这一条
            with _note_an_lock:
                ok = bool(_note_an_state.get("ok"))
                err = _note_an_state.get("error") or ""
            if not ok and _note_batch["stop"]:
                tries[name] -= 1          # v62：是你点了停止才中断的，不算这条失败，下次接着分析它
                break
            if ok:
                _note_batch["done"] += 1
                _note_batch["ok"] += 1
                _note_batch["ok_names"] = (list(_note_batch.get("ok_names") or []) + [name])[-2000:]   # v69：清单里马上去掉
                _note_batch["streak"] = 0
                backoff_i = 0
                _note_batch["paused"] = ""
                if name in _note_batch.get("failed_names", []):
                    _note_batch["failed_names"].remove(name)
                _note_batch["errors"] = [x for x in _note_batch["errors"] if x.get("name") != name]
            else:
                _note_batch["streak"] = _note_batch.get("streak", 0) + 1
                _note_batch["errors"] = ([x for x in _note_batch["errors"] if x.get("name") != name]
                                         + [{"name": name, "error": err[:160]}])[-20:]
                if tries[name] < _BATCH_MAX_TRIES:
                    fl = _note_batch.setdefault("failed_names", [])
                    if name not in fl:
                        fl.append(name)
                else:
                    _note_batch["done"] += 1
                    _note_batch["fail"] += 1
                    _clog("视频", "✖ %s 已试 %d 次都没成功，先跳过：%s" % (name[:40], tries[name], err[:80]))
                if _note_batch["streak"] >= 2:
                    # 连着两条都失败，多半是 AI 池本身出了问题：等一会儿再自动接着跑（不再永久暂停）
                    mins = _BATCH_BACKOFF_MIN[min(backoff_i, len(_BATCH_BACKOFF_MIN) - 1)]
                    backoff_i += 1
                    _note_batch["paused"] = ("连续 %d 条没成功（%s），%d 分钟后自动接着跑"
                                             % (_note_batch["streak"], err[:120], mins))
                    _clog("视频", "⏸ 批量补分析：%s" % _note_batch["paused"])
                    if _batch_sleep(mins * 60, _note_batch["paused"]):
                        break
                    # 接着跑之前先测 AI 池能不能连上；连不上就继续等下一档
                    while not _note_batch["stop"]:
                        okp, why = _pool_ready_for_batch()
                        if okp:
                            _clog("视频", "▶ AI 池能连上了（%s），批量补分析接着跑" % (why or "测通"))
                            break
                        mins = _BATCH_BACKOFF_MIN[min(backoff_i, len(_BATCH_BACKOFF_MIN) - 1)]
                        backoff_i += 1
                        _note_batch["paused"] = "AI 池还是连不上（%s），%d 分钟后再试" % (why[:100], mins)
                        _clog("视频", "⏸ 批量补分析：%s" % _note_batch["paused"])
                        if _batch_sleep(mins * 60, _note_batch["paused"]):
                            break
                    _note_batch["streak"] = 0
                    _note_batch["paused"] = ""
                    # 刚才失败的这条，恢复后先重试它
                    fl = _note_batch.get("failed_names", [])
                    if tries[name] < _BATCH_MAX_TRIES and name in fl:
                        fl.remove(name)
                        pending.insert(0, name)
            _time.sleep(1)
    finally:
        # 没试满就被停掉的，计成失败，方便看
        for n in _note_batch.get("failed_names", []):
            _note_batch["done"] += 1
            _note_batch["fail"] += 1
        _note_batch["failed_names"] = []
        _note_batch["running"] = False
        _note_batch["current"] = ""
        _note_batch["waiting"] = ""
        _note_batch["finished"] = _time.time()
        _clog("视频", "📦 批量补分析结束：完成 %d / %d（成功 %d，失败 %d）%s" % (
            _note_batch["done"], _note_batch["total"], _note_batch["ok"], _note_batch["fail"],
            "，已手动停止" if _note_batch["stop"] else ""))


def _note_batch_enqueue(names, use_local=True, model="qwen2.5", why=""):
    """把笔记交给批量补分析：正在跑就追加进去，没在跑就开一批。返回加入的条数。"""
    d = _cx_video_dir()
    names = [n for n in names if n and (d / n).exists()]
    if not names:
        return 0
    if _note_batch["running"]:
        ex = _note_batch.setdefault("extra", [])
        for n in names:
            if n not in ex:
                ex.append(n)
        _clog("视频", "📦 %s：%d 条加进正在跑的批量补分析" % (why or "补分析", len(names)))
        return len(names)
    _note_batch.update({"running": True, "total": len(names), "done": 0, "ok": 0, "fail": 0, "ok_names": [],
                        "current": "", "stop": False, "errors": [], "started": _time_now(), "finished": 0,
                        "streak": 0, "paused": "", "waiting": "", "resume_at": 0, "extra": [],
                        "failed_names": [], "round": 1})
    _clog("视频", "📦 %s：开始批量补分析 %d 条（每条换一张新的 AI 卡）" % (why or "补分析", len(names)))
    _threading.Thread(target=_note_batch_worker, args=(names, use_local, model),
                      daemon=True, name="note-batch").start()
    return len(names)


def _parse_saved_note(text):
    """从已存档的笔记 md 里拆出（标题, 元信息行列表, 文字稿, 已有标签列表）。
    元信息行 = 开头那些 '- 来源链接/作者/提取时间…'；
    「- 状态：未分析」这行会被剔除（补完分析它就不成立了）；
    「- 标签：…」单独抽成列表（补分析后要和 AI 标签合并重写）。"""
    lines = (text or "").split("\n")
    title = lines[0].lstrip("# ").strip() if lines else ""
    meta, tags = [], []
    for ln in lines[1:15]:
        s = ln.strip()
        if not s:
            continue
        if not s.startswith("-"):
            break
        bare = s.lstrip("-").strip()
        if bare.startswith("状态：") or bare.startswith("状态:"):
            continue
        m = re.match(r"^标签[：:]\s*(.+)$", bare)
        if m:
            tags = [t.strip() for t in re.split(r"[、，,\s]+", m.group(1))
                    if t.strip()]
            continue
        meta.append("- " + bare)
    # 文字稿：'## 📝 完整文字稿' 之后的所有内容
    tmark = _tmark((text or ""))
    transcript = ""
    if tmark >= 0:
        tstart = text.find("\n", tmark)
        if tstart >= 0:
            transcript = text[tstart:].strip()
    return title, meta, transcript, tags


# ════════════════ v67：AI 池一次只做一件事（先来先做，排队时看得到前面在做什么） ════════════════
def _ai_slots():
    """AI 池同时能做几件事。现在只有一个网站（一个浏览器、一个干活的线程），所以是 1。
    以后加了第二个网站（各自一个浏览器）就改成网站个数，那时视频分析和批量分析可以同时进行。"""
    return 1


class _AIGate:
    def __init__(self):
        self._cv = _threading.Condition()
        self._queue = []              # 排队的（先来先做）
        self._holders = {}            # 正在用 AI 池的：票 → (说明, 开始时间, 线程号)

    def _busy_locked(self):
        if not self._holders:
            return "马上就轮到"
        return "、".join("「%s」" % w for w, _t, _i in self._holders.values()) + " 正在用 AI 池，做完就轮到这一条"

    def acquire(self, what, on_wait=None, should_stop=None):
        """排队等 AI 池。轮到了返回一张票（用完要 release）；等的时候被停止了返回 None。
        on_wait(说明)：前面在做的事情变了才调用一次（不会刷屏）。"""
        t = object()
        last = None
        with self._cv:
            self._queue.append(t)
        try:
            while True:
                with self._cv:
                    if self._queue and self._queue[0] is t and len(self._holders) < max(1, _ai_slots()):
                        self._queue.pop(0)
                        self._holders[t] = (what, _time_now(), _threading.get_ident())
                        if last is not None:
                            _clog("AI池", "▶ 轮到「%s」" % what)
                        return t
                    busy = self._busy_locked()
                if should_stop is not None and should_stop():
                    with self._cv:
                        if t in self._queue:
                            self._queue.remove(t)
                        self._cv.notify_all()
                    return None
                if busy != last:
                    if last is None:
                        _clog("AI池", "⏳「%s」排队等 AI 池：%s" % (what, busy))
                    last = busy
                    if on_wait is not None:
                        try:
                            on_wait(busy)
                        except Exception:
                            pass
                with self._cv:
                    self._cv.wait(1.0)
        except BaseException:
            with self._cv:
                if t in self._queue:
                    self._queue.remove(t)
                self._cv.notify_all()
            raise

    def release(self, t):
        if t is None:
            return
        with self._cv:
            self._holders.pop(t, None)
            self._cv.notify_all()

    def release_thread(self):
        """保险：这个线程还拿着的票全部还回去（出错没走到 release 时用）。"""
        me = _threading.get_ident()
        with self._cv:
            for t in [t for t, v in self._holders.items() if v[2] == me]:
                self._holders.pop(t, None)
            self._cv.notify_all()

    def status(self):
        with self._cv:
            return {"slots": max(1, _ai_slots()), "waiting": len(self._queue),
                    "busy": [{"what": w, "since": int(t0)} for w, t0, _i in self._holders.values()]}


_ai_gate = _AIGate()


def _tmark(text):
    """v94：「完整文字稿」那一节从哪开始——认标题行「## 📝 完整文字稿」（取最后一个），
    不认正文里随口提到的「完整文字稿」四个字（以前 AI 分析里写了这几个字，原文就被切错了）。找不到返回 -1。"""
    text = text or ""
    ms = list(re.finditer(r"^#{1,3}\s*(?:📝\s*)?完整文字稿\s*$", text, re.M))
    if ms:
        return ms[-1].start()
    return text.find("完整文字稿")


# ════════════════ v95：字幕模式 + 翻译成中文 + 导出字幕 ════════════════
# 时间轴（video_notes/segments/<笔记>.json）里每句有开始 / 结束时间和原文；翻译后每句多一个 zh。
# 翻译是「一行对一行」地让 AI 翻（带编号），所以中文和时间一一对上，能直接做成双语字幕。
_tr_state = {}            # 笔记名 -> {running, msg, ok, done, total}
_tr_lock = _threading.Lock()
TR_CHUNK = 30
TR_PARALLEL = 2           # v96：同时翻几段（本地模型显存够，两段一起快将近一倍）


def _subs_path(name):
    return _cx_segments_dir() / (name[:-3] + ".json")


def _subs_load(name):
    try:
        d = json.loads(_subs_path(name).read_text(encoding="utf-8", errors="replace"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _subs_fix(segs):
    """补结束时间（老时间轴只有开始时间）：到下一句开始为止，最长按每秒 4 个字估。"""
    out = []
    for i, sg in enumerate(segs):
        t = (sg.get("text") or "").strip()
        if not t:
            continue
        st = float(sg.get("start") or 0)
        en = sg.get("end")
        nxt = float(segs[i + 1].get("start") or 0) if i + 1 < len(segs) else None
        if en is None:
            en = st + max(1.2, len(t) / 4.0)
            if nxt is not None and nxt > st:
                en = min(en, nxt)
        out.append(dict(sg, start=round(st, 2), end=round(max(float(en), st + 0.3), 2), text=t))
    return out


def _srt_ts(t):
    t = max(0.0, float(t))
    h, r = divmod(t, 3600)
    m, sec = divmod(r, 60)
    return "%02d:%02d:%02d,%03d" % (h, m, int(sec), int(round((sec - int(sec)) * 1000)) % 1000)


def _make_srt(segs, mode):
    lines, n = [], 0
    for sg in segs:
        o, z = sg.get("text") or "", (sg.get("zh") or "").strip()
        body = z if mode == "zh" else (o + ("\n" + z if z else "") if mode == "both" else o)
        if not body.strip():
            continue
        n += 1
        lines.append("%d\n%s --> %s\n%s\n" % (n, _srt_ts(sg["start"]), _srt_ts(sg["end"]), body))
    return "\n".join(lines)


def _tr_llm(prompt, engine):
    """翻译用哪个模型。engine：'local'（默认，本机默认模型）/ 'local:模型名' / 'pool'（AI 池网页版，慢）。"""
    if engine == "pool":
        return _tidy_llm(prompt, wait_pool=True)
    model = engine.split(":", 1)[1] if engine.startswith("local:") else ""
    return _local_chat(prompt, model=model)


def _tr_worker(name, engine="local"):
    st = _tr_state[name]
    try:
        d = _subs_load(name)
        segs = d.get("segments") or []
        if not segs:
            raise RuntimeError("这条笔记没有时间轴（太早以前提取的，或者是文章 / 文档），没法逐句翻译")
        import video_transcribe as _vt
        lab = _vt.lang_label(d.get("lang") or "auto")
        who = "AI 池" if engine == "pool" else "本地模型 %s" % (engine.split(":", 1)[1] if engine.startswith("local:")
                                                             else (_local_default_model() or "?"))
        todo = [i for i, sg in enumerate(segs) if (sg.get("text") or "").strip() and not (sg.get("zh") or "").strip()]
        chunks = [todo[i:i + TR_CHUNK] for i in range(0, len(todo), TR_CHUNK)]
        st.update(total=len(chunks), done=0, engine=who)
        _clog("翻译", "▶ 开始：%s（%d 句，分 %d 段，用%s）" % (name[:40], len(todo), len(chunks), who))
        t0 = _time_now()
        wlock = _threading.Lock()
        err = {"e": None}

        def one(idx):
            for attempt in range(2):
                want = [i for i in idx if not (segs[i].get("zh") or "").strip()]
                if not want:
                    return
                body = "\n".join("%d|%s" % (k + 1, segs[i]["text"].replace("\n", " ")) for k, i in enumerate(want))
                prompt = ("下面是一段%s视频的字幕，每行一句，行首是编号。请把每一行翻译成自然、通顺的简体中文。\n"
                          "要求：\n1. 一行对一行，编号不变，不要合并、拆分或漏掉任何一行；\n"
                          "2. 只输出「编号|译文」，每行一条，不要任何解释、标题或多余的话；\n"
                          "3. 人名、地名、专有名词用常见的中文译法，没有通行译法的保留原文；\n"
                          "4. 口语就译成口语，语气词可以意译。\n\n=== 字幕 ===\n%s" % (
                              lab if lab not in ("自动识别",) else "外语", body))
                reply = _tr_llm(prompt, engine)
                got = {}
                for ln in (reply or "").splitlines():
                    m = re.match(r"^\s*(\d+)\s*[|｜]\s*(.+?)\s*$", ln)
                    if m:
                        got[int(m.group(1))] = m.group(2)
                with wlock:
                    for k, i in enumerate(want):
                        if got.get(k + 1):
                            segs[i]["zh"] = got[k + 1]

        def runner(q):
            while True:
                with wlock:
                    if not q or err["e"]:
                        return
                    idx = q.pop(0)
                try:
                    one(idx)
                except Exception as e:
                    err["e"] = e
                    return
                with wlock:
                    st["done"] += 1
                    d["segments"] = segs
                    _subs_path(name).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")   # 每段都存，断了下次接着翻
                    sec = _time_now() - t0
                    left = (st["total"] - st["done"]) * sec / max(1, st["done"])
                    st["msg"] = "%s 翻译中：%d / %d 段%s" % (who, st["done"], st["total"],
                                                         "，还要约 %d 秒" % left if st["done"] < st["total"] else "")

        q = list(chunks)
        st["msg"] = "%s 翻译中：0 / %d 段…" % (who, len(chunks))
        ths = [_threading.Thread(target=runner, args=(q,), daemon=True) for _ in range(min(TR_PARALLEL, len(chunks)) or 1)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        if err["e"]:
            raise err["e"]
        miss = sum(1 for i in todo if not (segs[i].get("zh") or "").strip())
        msg = "翻译好了（%d 句，用%s，%d 秒）" % (len(todo), who, int(_time_now() - t0)) + (
            "，有 %d 句没给译文，可以再点一次补上" % miss if miss else "")
        st.update(running=False, ok=True, msg=msg)
        _clog("翻译", "✓ %s：%s" % (name[:40], msg))
    except Exception as e:
        hint = "；可以在「翻译用」里换个模型，或者选 AI 池" if engine != "pool" else ""
        st.update(running=False, ok=False, msg="没翻译成：%s%s" % (str(e)[:200], hint))
        _clog("翻译", "没翻译成：%s" % e)


# ════════════════ v94：推文笔记 =「🗣 博主原话」+「🔗 链接原文」════════════════
# 存的时候先用手头的数据拆好（马上存），再在后台联网补全：取完整推文、解开短链、读链接里的文章，
# 写回笔记的「完整文字稿」那一节（AI 分析那部分不动）。老的推文笔记可以在阅读页点按钮重新整理。
_xr_lock = _threading.Lock()
_xr_state = {"running": False, "total": 0, "done": 0, "current": "", "msg": "", "ok": 0, "fail": 0, "last": {}}
_xr_queue = []


def _xsrc_dir():
    d = _cx_video_dir() / "xsrc"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _xsrc_save(name, url, text, snap, author):
    try:
        (_xsrc_dir() / (name[:-3] + ".json")).write_text(json.dumps(
            {"url": url, "text": text, "x": snap, "author": author}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _x_parts_md(url, text, snap, author, deep=False, progress=None):
    import tweet_parts as _tp
    try:
        return _tp.to_markdown(_tp.build(url, text, snap, author, deep=deep, progress=progress))
    except Exception as e:
        _clog("推文", "拆「博主原话 / 链接原文」出错，先存原文：%s" % e)
        return text


def _x_note_rebuild(name, progress=None):
    """重新整理一条推文笔记的「完整文字稿」：联网取完整推文、链接原文。返回说明文字。"""
    import tweet_parts as _tp
    p = _cx_video_dir() / name
    md = p.read_text(encoding="utf-8", errors="replace")
    if not _tp.is_tweet_note(md):
        raise RuntimeError("这条不是推文笔记")
    url = (re.search(r"来源链接：\s*(\S+)", md) or [None, ""])[1]
    author = (re.search(r"作者：\s*(.+)", md) or [None, ""])[1].strip()
    src = {}
    try:
        src = json.loads((_xsrc_dir() / (name[:-3] + ".json")).read_text(encoding="utf-8"))
    except Exception:
        src = {}
    # 文字稿那一节从哪开始：新的「完整文字稿」或老的「推文原文」
    m = re.search(r"^##\s*📝\s*(完整文字稿|推文原文)\s*$", md, re.M)
    if not m:
        raise RuntimeError("这条笔记里没找到推文原文")
    old_body = md[m.end():].strip()
    text = src.get("text") or ""
    if not text:
        if "### 🗣 博主原话" in old_body:          # 已经是新格式、又没有原始数据：拿「博主原话」那段
            seg = old_body.split("### 🗣 博主原话", 1)[1].split("### 🔗 链接原文", 1)[0].strip()
            text = "" if seg.startswith("（这条是转发") else seg
        else:
            text = old_body
    new_body = _x_parts_md(url, text, src.get("x"), author or src.get("author") or "", deep=True, progress=progress)
    cur = p.read_text(encoding="utf-8", errors="replace")       # 写回前再读一次，别盖掉别人刚写的分析
    m2 = re.search(r"^##\s*📝\s*(完整文字稿|推文原文)\s*$", cur, re.M)
    if not m2:
        raise RuntimeError("这条笔记刚被改过，请再点一次")
    head = cur[:m2.start()].rstrip()
    if "## 🤖 AI 分析" in head and not head.endswith("---"):
        head += "\n\n---"
    p.write_text(head + "\n\n## 📝 完整文字稿\n\n" + new_body.strip() + "\n", encoding="utf-8")
    if not src:
        _xsrc_save(name, url, text, None, author)
    n_ref = new_body.count("\n#### ")
    return "整理好了：博主原话 + %d 条链接原文" % n_ref if n_ref else "整理好了（这条没有转发、引用或链接）"


def _xr_worker():
    while True:
        with _xr_lock:
            if not _xr_queue:
                _xr_state.update(running=False, current="")
                return
            name = _xr_queue.pop(0)
            _xr_state["current"] = name
        try:
            msg = _x_note_rebuild(name, progress=lambda m: _xr_state.update(msg=m))
            with _xr_lock:
                _xr_state["ok"] += 1
                _xr_state["last"][name] = {"ok": True, "msg": msg}
            _clog("推文", "✓ %s：%s" % (name[16:46], msg))
        except Exception as e:
            with _xr_lock:
                _xr_state["fail"] += 1
                _xr_state["last"][name] = {"ok": False, "msg": str(e)[:200]}
            _clog("推文", "没整理成 %s：%s" % (name[16:46], e))
        with _xr_lock:
            _xr_state["done"] += 1


def _xr_enqueue(names):
    with _xr_lock:
        add = [n for n in names if n not in _xr_queue and n != _xr_state.get("current")]
        if not add:
            return 0
        if not _xr_state["running"]:
            _xr_state.update(running=True, total=0, done=0, ok=0, fail=0, msg="")
        _xr_queue.extend(add)
        _xr_state["total"] += len(add)
        for n in add:
            _xr_state["last"].pop(n, None)
        start = not any(t.name == "x-rebuild" for t in _threading.enumerate())
    if start:
        _threading.Thread(target=_xr_worker, name="x-rebuild", daemon=True).start()
    return len(add)


# ════════════════ v88：整理原文（AI 加标点、按意思分段）════════════════
_tidy_state = {}          # 笔记名 -> {"running", "msg", "ok", "transcript"}
_tidy_lock = _threading.Lock()


def _local_default_model():
    """本机默认用哪个本地模型（设置里「本地动作 / 快速对话」配的，比如 qwen3:14b）。没有返回空串。"""
    try:
        names = core.installed_local_models()
    except Exception:
        names = []
    if not names:
        return ""
    try:
        ul, m = core.prefer_local_model(True, "qwen2.5")
        if ul and m and m in names:
            return m
    except Exception:
        pass
    return names[0]


def _local_chat(prompt, model="", num_ctx=8192, timeout=600):
    """v96：直接调本机 Ollama（原生 /api/chat）——关掉「思考」（qwen3 默认会先想很久）、
    模型在显存里留 30 分钟（一段一段翻译时不用每次重新加载）。返回回复文字；不行就抛异常。"""
    import urllib.request
    import ollama_helper as _oh
    if not _oh.is_running():
        _oh.try_start()
    if not _oh.is_running():
        raise RuntimeError("本地模型没开（Ollama 没在运行，也没自动拉起来）")
    model = model or _local_default_model()
    if not model:
        raise RuntimeError("本机还没装本地模型（Ollama 里一个模型都没有）")
    content = prompt + ("\n/no_think" if model.lower().startswith("qwen3") else "")
    last = None
    for extra in ({"think": False}, {}):                  # 老版本 Ollama 不认 think 参数，就去掉再试
        body = dict({"model": model, "messages": [{"role": "user", "content": content}], "stream": False,
                     "keep_alive": "30m", "options": {"temperature": 0.3, "num_ctx": num_ctx}}, **extra)
        req = urllib.request.Request(_oh.OLLAMA_API + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            out = ((d.get("message") or {}).get("content") or "")
            out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
            if out:
                return out
            last = RuntimeError("本地模型没回话")
        except Exception as e:
            last = e
            if not extra:
                break
    raise RuntimeError("本地模型 %s 没回话：%s" % (model, str(last)[:150]))


def _tidy_llm(prompt, wait_pool=True):
    """整理原文用哪个 AI：本机装了 Ollama 模型就用本地的（快、不占 AI 池）；没有或失败再用 AI 池。
    wait_pool=False：AI 池正忙（比如在批量分析）就不排队了，直接报错（提取流水线用，别把队列卡住）。"""
    try:
        names = core.installed_local_models()
    except Exception:
        names = []
    if names:
        try:
            out = _local_chat(prompt)                     # v96：本地模型走快的那条路（不思考、常驻显存）
            if out:
                return out
        except Exception as e:
            _clog("整理原文", "本地模型快速通道没成功（%s），换普通方式" % str(e)[:80])
        try:
            ul, m = core.prefer_local_model(True, "qwen2.5")
            if ul and m:
                client = core.make_client(True)
                resp = client.chat.completions.create(model=m, messages=[{"role": "user", "content": prompt}])
                out = (resp.choices[0].message.content or "").strip()
                if out:
                    return out
        except Exception as e:
            _clog("整理原文", "本地模型没成功（%s），改用 AI 池" % str(e)[:80])
    if not wait_pool and (_ai_gate.status().get("busy") or _ai_gate.status().get("waiting")):
        raise RuntimeError("AI 池正忙，这次先按停顿分句；等它空了，在笔记「完整原文」里点「✨ 整理原文」")
    t = _ai_gate.acquire("整理原文（加标点、分段）")
    try:
        client = core.make_client_for("web", False)
        resp = client.chat.completions.create(model="web", messages=[{"role": "user", "content": prompt}])
        return (resp.choices[0].message.content or "").strip()
    finally:
        _ai_gate.release(t)


def _tidy_text(text, progress=None, force=False, wait_pool=True):
    """返回 (整理后的文字, 说明)。不需要整理 / 出错时原样返回。"""
    import transcript_tidy as _tt
    if not force and not _tt.needs_tidy(text):
        return text, "原文已经有标点和分段了，不用整理"
    try:
        return _tt.tidy(text, lambda p: _tidy_llm(p, wait_pool=wait_pool), progress=progress)
    except Exception as e:
        return text, "没整理成：%s" % e


def _note_tidy_worker(name):
    """给一条已存的笔记整理原文：读 md → 整理「完整文字稿」那一节 → 原地写回。"""
    st = _tidy_state[name]
    try:
        p = _cx_video_dir() / name
        text = p.read_text(encoding="utf-8", errors="replace")
        tmark = _tmark(text)
        tstart = text.find("\n", tmark) if tmark >= 0 else -1
        if tstart < 0:
            raise RuntimeError("这条笔记里没找到文字稿")
        old = text[tstart:].strip()
        _clog("整理原文", "▶ 开始：%s" % name[:50])
        # v89：有存下来的分句时间轴的，先按说话停顿加标点、分段（不用 AI，一定成功），再让 AI 细调；
        #      AI 不在 / 没整理成，也至少是按停顿分好的样子，不再是一整块
        base = old
        try:
            import transcript_tidy as _tt
            import video_transcribe as _vt
            sp = _cx_segments_dir() / (name[:-3] + ".json")
            if _tt.needs_tidy(old) and sp.exists():
                _segs = (json.loads(sp.read_text(encoding="utf-8", errors="replace")) or {}).get("segments") or []
                comp = _vt._compose_from_segments(_segs) if _segs else ""
                if comp and _tt.check(old, comp)[0]:
                    base = comp
                    st.update(msg="先按说话停顿加了标点、分了段，再让 AI 细调…")
        except Exception as _e:
            _clog("整理原文", "按停顿分句跳过（%s）" % _e)
        new, msg = _tidy_text(base, progress=lambda m: st.update(msg=m), force=True)
        if base != old and new.strip() == base.strip():
            msg = "按说话停顿加了标点、分了段（AI 这次没整理成：%s）" % msg.replace("没整理成：", "")
        if new.strip() != old:
            cur = p.read_text(encoding="utf-8", errors="replace")     # 写回前再读一次，别盖掉别人刚写的
            if cur[_tmark(cur):].find(old[:50]) < 0:
                raise RuntimeError("这条笔记刚被别的操作改过，请再点一次")
            k = cur.find("\n", _tmark(cur))
            p.write_text(cur[:k] + "\n\n" + new.strip() + "\n", encoding="utf-8")
        st.update(running=False, ok=new.strip() != old, msg=msg, transcript=new.strip())
        _clog("整理原文", "%s：%s" % ("✓" if new.strip() != old else "—", msg))
    except Exception as e:
        st.update(running=False, ok=False, msg=str(e)[:200])
        _clog("整理原文", "没成功：%s" % e)


def _note_analyze_worker(name, use_local, model):
    """v67：批量分析的每一篇、单条「AI 分析」都走这里：先排队等 AI 池（一次只做一件事），轮到了再分析。"""
    in_batch = bool(_note_batch.get("running")) and _note_batch.get("current") == name
    short = re.sub(r"^\d{8}-\d{6}-", "", name or "")[:-3][:24]
    if in_batch:
        what = "批量分析 第 %d / %d 篇《%s》" % (min(_note_batch.get("total", 0), _note_batch.get("done", 0) + 1),
                                           _note_batch.get("total", 0), short)
    else:
        what = "分析《%s》" % short

    def on_wait(busy):
        with _note_an_lock:
            _note_an_state.update({"running": True, "name": name, "stage": "排队等 AI 池：" + busy})

    def should_stop():
        return bool(_note_batch.get("stop")) if in_batch else bool(_note_an_state.get("stop_req"))
    t = _ai_gate.acquire(what, on_wait=on_wait, should_stop=should_stop)
    if t is None:
        with _note_an_lock:
            _note_an_state.update({"running": False, "stage": "", "ok": False,
                                   "error": "分析出错：已按你的要求停止（还没轮到 AI 池）"})
            _note_an_state["done_id"] = _note_an_state.get("done_id", 0) + 1
        return
    try:
        return _note_analyze_worker_inner(name, use_local, model)
    finally:
        _ai_gate.release(t)


def _note_analyze_worker_inner(name, use_local, model):
    """后台线程：读一条「未分析」笔记 → AI 分析 / 补标签 / 翻标题 → 原地重写 md。
    与提取流水线里的 AI 分析共用同一套函数，产出格式完全一致；
    若存在 segments 侧车文件、且当初勾了「跳转原片」，会照常打时间标记（方案 B）。
    插图无法补做（视频画面在提取时就已清理）。"""
    import time as _time
    start = _time.time()

    def stage(s, detail=""):
        _note_an_state["stage"] = s + (("：" + detail) if detail else "")

    ok, err = False, ""
    try:
        p = _cx_video_dir() / name
        text = p.read_text(encoding="utf-8", errors="replace")
        title, meta_lines, transcript, old_tags = _parse_saved_note(text)
        # v55：「实时画面」面板显示正在分析哪一篇（标题 + 作者）
        try:
            _au = ""
            for ln in meta_lines:
                _m = re.search(r"作者[：:]\s*(.+)", ln)
                if _m:
                    _au = _m.group(1).strip()
                    break
            _note_an_state.update({"title": title or "", "author": _au, "started_at": start})
        except Exception:
            pass
        if not transcript:
            raise RuntimeError("这条笔记里没找到文字稿，补不了分析")
        title = title or "（无标题）"
        note_stem = name[:-3] if name.endswith(".md") else name

        # segments 侧车：有就读出来，「跳转原片」标记照常可用
        segments, want_link, clean_url = [], False, ""
        try:
            sp = _cx_segments_dir() / (note_stem + ".json")
            if sp.exists():
                _d = json.loads(sp.read_text(encoding="utf-8", errors="replace"))
                segments = _d.get("segments") or []
                want_link = bool(_d.get("link"))
                clean_url = (_d.get("url") or "").strip()
        except Exception:
            segments, want_link = [], False
        if not clean_url:
            for ln in meta_lines:
                m = re.search(r"来源链接[：:]\s*(\S+)", ln)
                if m:
                    clean_url = m.group(1).strip()
                    break

        _clog("视频", "▶ 开始补做 AI 分析：%s" % name[:50])
        stage("AI 分析", "让模型把文字稿总结成笔记…")
        analysis = _cx_analyze_transcript(
            transcript, title, use_local, model,
            on_progress=lambda m: stage("AI 分析", m),
            segments=segments, do_screenshot=False,
            do_link=bool(want_link and segments),
            src_noun=_vn_src_noun_of_file(name))
        if (analysis or "").lstrip().startswith("（分析出错"):
            # AI 池没成功：不把报错当分析结果存进笔记（保持「未分析」，以后还能再补）
            raise RuntimeError((analysis or "").strip().strip("（）")[:200])
        title_from_ai, analysis = _split_title_from_analysis(analysis)
        try:
            analysis = _cx_adopt_web_images(analysis, note_stem)    # AI 池生成的示意图存进笔记
        except Exception:
            pass

        stage("AI 分析", "归纳标签…")
        try:
            ai_tags = _cx_suggest_tag(title, analysis, use_local, model)
        except Exception:
            ai_tags = []
        # 已有标签（平台话题标签/用户手动加的）在前，AI 标签在后，去重取 6 个
        tags = []
        for _t in list(old_tags) + list(ai_tags):
            _t = (_t or "").strip().lstrip("#").strip()
            if _t and _t not in tags:
                tags.append(_t)
        tags = tags[:6]

        # 跳转原片标记 → 真实跳转链接（不截图：视频画面早已清理）
        if want_link and segments and clean_url:
            try:
                import video_screenshot
                shots_dir = _cx_shots_dir() / note_stem
                img_base = ("http://127.0.0.1:%d/video_shot?n=%s&f="
                            % (PORT, urllib.parse.quote(note_stem)))
                analysis, _ = video_screenshot.post_process(
                    analysis, url=clean_url, video_path=None,
                    shots_dir=shots_dir, image_url_base=img_base,
                    do_screenshot=False, do_link=True)
            except Exception:
                pass

        # 中文标题：优先用分析里顺手翻好的；没有且原标题像英文，再单独翻一次
        title_zh = ""
        if title_from_ai and title_from_ai.strip() and title_from_ai.strip() != title.strip():
            title_zh = title_from_ai.strip()
        elif _looks_english(title):
            try:
                stage("AI 分析", "翻译标题…")
                _zh_list, _ = _translate_lines(
                    [title], use_local=use_local, model=model)
                _cand = (_zh_list[0] if _zh_list else "").strip()
                if _cand and _cand != title:
                    title_zh = _cand
            except Exception:
                title_zh = ""
        display_title = title_zh or title

        stage("保存", "写回笔记文件…")
        meta = "\n".join(meta_lines)
        orig_line = (f"\n- 原标题：{title}" if title_zh else "")
        tag_line = ("\n- 标签：" + "、".join(tags)) if tags else ""
        doc = (f"# {display_title}\n\n"
               f"{meta}{orig_line}{tag_line}\n\n"
               f"## 🤖 AI 分析\n\n{analysis}\n\n"
               f"---\n\n## 📝 完整文字稿\n\n{transcript}\n")
        p.write_text(doc, encoding="utf-8")
        # 侧车文件用完即删
        try:
            sp = _cx_segments_dir() / (note_stem + ".json")
            if sp.exists():
                sp.unlink()
        except Exception:
            pass
        ok = True
        _clog("视频", "✅ 补分析完成：《%s》（用时 %d 秒）"
              % (display_title[:24], int(_time.time() - start)))
    except Exception as e:
        err = str(e)
        _clog("视频", "⚠ 补分析没成功：%s" % err[:120])
    finally:
        with _note_an_lock:
            _note_an_state["running"] = False
            _note_an_state["stage"] = ""
            _note_an_state["ok"] = ok
            _note_an_state["error"] = "" if ok else (err or "补分析未成功")
            _note_an_state["done_id"] += 1


def _normalize_video_url(url):
    """规范化视频链接，避免把 yt-dlp 不认的地址喂给它。
    典型问题：iesdouyin.com/share/video/{id}/?一堆参数 —— yt-dlp 报 Unsupported URL。
    这里把它转成标准的 douyin.com/video/{id}（yt-dlp 认识），其它链接原样返回。"""
    try:
        u = (url or "").strip()
        if "iesdouyin.com" in u.lower():
            import re as _re
            m = _re.search(r"/share/video/(\d{6,})", u)
            if not m:
                m = _re.search(r"/video/(\d{6,})", u)
            if m:
                return "https://www.douyin.com/video/%s" % m.group(1)
        return u
    except Exception:
        return url


def _quick_title(url, timeout=8):
    """快速爬一个视频的标题（只为「正在处理 / 排队中」显示视频名用），带超时。
    抖音优先走分享页元信息（几秒）；失败再用 yt-dlp 兜底取标题。
    拿不到就返回空串——调用方退回显示链接，绝不阻塞主流程。"""
    try:
        import video_transcribe as _vt
        _dy_composed = ""   # 抖音：话题标签 /「作者 的视频」合成名（次选）
        _dy_fallback = ""   # 抖音：「抖音视频 …ID」占位（最后兜底，避免一直「获取名称中…」）
        if _vt._is_douyin(url):
            # ① 先走抖音分享页/接口解析，拿「真实文案 desc」当标题（最佳）
            try:
                import douyin_resolver
                meta = douyin_resolver.fetch_meta(url) or {}
                t = (meta.get("title") or "").strip()   # 真实 desc
                if t:
                    return t
                # 暂存次选/占位，等 yt-dlp 兜底失败后才用
                _dy_composed = (meta.get("display_title") or "").strip()
                _dy_fallback = (meta.get("fallback_title") or "").strip()
            except Exception:
                pass
            # ② 没拿到真实文案 → 继续往下走 yt-dlp 兜底取真实标题。
            #    关键修复：以前占位符会在这里直接 return，把能拿到真实标题的 yt-dlp 这步截断了。
        # 通用 / 抖音兜底：yt-dlp 只取 info（skip_download），放线程里跑并设超时
        import threading as _th
        probe_url = _normalize_video_url(url)
        box = {"t": ""}

        def _probe():
            try:
                info = _vt._run_extract(probe_url, {
                    "quiet": True, "no_warnings": True, "noplaylist": True,
                    "skip_download": True, "nocheckcertificate": True},
                    download=False)
                box["t"] = (info.get("title") or info.get("description") or "").strip()
            except Exception:
                box["t"] = ""
        th = _th.Thread(target=_probe, daemon=True)
        th.start()
        th.join(timeout)
        if box["t"]:
            return box["t"]
        # yt-dlp 也没拿到 → 抖音退到「标签/作者」合成名，再退到「抖音视频…ID」占位
        if _dy_composed:
            return _dy_composed
        if _dy_fallback:
            return _dy_fallback
        return box["t"]
    except Exception:
        return ""


def _enqueue_video(job):
    """把一个视频任务加入队列，必要时启动后台 worker。返回它的排队位置。
    会去重：同一个 url 如果正在处理、或已在待处理队列里，就不再重复入队，
    直接返回它现有的位置——避免「悬浮按钮 / 加入队列 / 手动点击」多个入口
    把同一个链接排进去两三遍。"""
    import time as _t
    if not job.get("id"):
        job["id"] = "vj" + str(_t.time()) + "-" + str(_t.monotonic_ns() % 100000)
    # 入队即规范化 URL：iesdouyin 长链 → 标准抖音链接，从入口杜绝 Unsupported URL。
    job["url"] = _normalize_video_url(job.get("url") or "")
    url = (job.get("url") or "").strip()
    with _video_lock:
        _video_cancel["all"] = False  # 新任务进来，清掉旧的取消标记

        # ── 去重 ──
        # 1) 正在处理的就是这条 → 直接返回「第 1 个（正在处理）」
        cur = _video_current.get("job")
        running = _video_state["running"]
        if running and cur and (cur.get("url") or "").strip() == url:
            return 1
        # 2) 待处理队列里已有这条 → 返回它现有位置，不重复 append
        for idx, j in enumerate(_video_q):
            if (j.get("url") or "").strip() == url:
                return idx + 1 + (1 if running else 0)

        # ── 没重复，正常入队 ──
        _video_q.append(job)
        _save_video_queue()          # 入队即写盘：关掉软件也不会丢
        # _video_state["queue"] 统一只放「待处理」任务（不含正在跑的那条），
        # 和 worker 里的设值口径一致，避免前端「第 N 个」忽多忽少。
        # 队列项现在带上标题（title 先用已有的，没有则为空，稍后异步爬好回填），
        # 让前端能显示「排队中的是哪个视频」而不是光秃秃的链接。
        _video_state["queue"] = [{"url": j["url"], "title": j.get("title") or ""}
                                 for j in _video_q]
        _video_state["queue_len"] = len(_video_q)
        # 这条任务的排队位置 = 它在待处理队列里的序号 +（有任务在跑则再 +1）
        pos = len(_video_q) + (1 if running else 0)
        _clog("视频", "＋ 已加入队列（第 %d 个）：%s" % (pos, (job.get("title") or url)[:50]))
        if not _video_worker_on["v"]:
            _video_worker_on["v"] = True
            _threading.Thread(target=_video_worker, daemon=True).start()

    # 入队后异步爬一次标题（不阻塞入队返回），爬到就回填进 job 和队列显示，
    # 这样排队中的任务也能显示视频名。失败/超时就保持显示链接，不影响处理。
    def _fill_title():
        try:
            if job.get("title"):
                return
            t = _quick_title(url)
            if not t:
                return
            with _video_lock:
                job["title"] = t
                # 回填到 _video_state["queue"] 里对应项（按 url 匹配）
                for q in (_video_state.get("queue") or []):
                    if isinstance(q, dict) and (q.get("url") or "") == url:
                        q["title"] = t
                _save_video_queue()
        except Exception:
            pass
    try:
        _threading.Thread(target=_fill_title, daemon=True).start()
    except Exception:
        pass
    return pos


def _cancel_video_jobs():
    """全部取消：清空待处理队列 + 给当前任务打取消标记。
    正在跑的下载/听写会在几秒内被中断（video_transcribe 的逐句循环和下载钩子
    都会检查 CANCEL 标记）；已识别的进度早已落盘，下次同链接可续传。"""
    with _video_lock:
        _video_q.clear()
        _video_cancel["all"] = True
        _video_state["queue"] = []
        _video_state["queue_len"] = 0
        cur = _video_current.get("job")
        try:
            _save_video_queue()
        except Exception:
            pass
    # ★让正在进行的下载/听写立刻停下（不只等阶段之间才检查）
    try:
        import video_transcribe as _vtc
        _vtc.CANCEL["on"] = True
    except Exception:
        pass
    _clog("视频", "🛑 收到「全部取消」：队列已清空，正在中断当前任务…")
    return {"ok": True, "cancelled_current": bool(cur)}


def _restore_video_queue():
    """软件启动时调用：把上次没跑完的视频任务读回来，自动继续处理。
    连续失败多次的任务（fail_count>=2）直接丢弃，不再恢复——避免一条始终失败的
    坏任务（如失效链接）每次重启都卡在队列头部，导致软件像「无法工作」。"""
    jobs = _load_video_queue()
    if not jobs:
        return
    dropped = 0
    with _video_lock:
        # 去重（按 url），避免 current 和 pending 里有重复
        seen = set()
        for j in jobs:
            u = (j.get("url") or "").strip()
            if not u or u in seen:
                continue
            # 连续失败太多次 → 放弃这条，不再无限重试卡住后面的任务
            if int(j.get("fail_count") or 0) >= 2:
                dropped += 1
                try:                     # v90：别悄悄丢掉，放进「提取失败」清单，以后能重新提取
                    _vf_add(j, "软件处理这条时关掉 / 崩溃了好几次，自动跳过了")
                except Exception:
                    pass
                continue
            seen.add(u)
            if not j.get("id"):
                import time as _t
                j["id"] = "vj" + str(_t.time()) + "-" + str(len(_video_q))
            _video_q.append(j)
        if _video_q:
            _save_video_queue()
            _video_state["queue"] = []
            _video_state["queue_len"] = 0
            if not _video_worker_on["v"]:
                _video_worker_on["v"] = True
                _threading.Thread(target=_video_worker, daemon=True).start()
    try:
        msg = "[video] 恢复了 %d 个未完成的视频任务，继续处理…" % len(seen)
        if dropped:
            msg += "（丢弃了 %d 个总是失败的坏任务）" % dropped
        print(msg)
    except Exception:
        pass


# 应用内心跳：后台线程，跟着软件一起活，开关由界面控制
import threading as _threading
_hb_state = {
    "running": False,
    "interval": 300,          # 秒
    "last": "",               # 上次心跳结果摘要
    "thread": None,
    "stop": None,             # threading.Event
    "use_local": True,
    "model": "qwen2.5",
}


def _heartbeat_loop():
    """后台心跳循环：每隔 interval 秒醒一次，直到 stop 事件被设置。"""
    import datetime as _dt
    stop = _hb_state["stop"]
    # 启动后先等一个间隔再跑第一次，避免刚开就打扰
    while not stop.is_set():
        if stop.wait(_hb_state["interval"]):
            break
        try:
            import heartbeat
            reply = heartbeat.run_one_beat(
                use_local=_hb_state["use_local"],
                model=_hb_state["model"], verbose=False)
            stamp = _dt.datetime.now().strftime("%H:%M")
            r = (reply or "").strip()
            if r.upper().startswith("SLEEP"):
                _hb_state["last"] = f"{stamp} 看了一眼，没事"
            else:
                _hb_state["last"] = f"{stamp} 干活了：{r[:60]}"
        except Exception as e:
            _hb_state["last"] = f"出错（已忽略）：{e}"
    _hb_state["running"] = False


# ════════════════════ 分身自动化调度（每个分身独立的定时任务）════════════════════
_auto_state = {"running": False, "thread": None, "stop": None}


def _automation_client(use_local, model):
    """按分身自己存的模型，造一个对应的 client（本地 / 云端 / 网页 / Claude）。"""
    if model == "claude" or str(model).startswith("claude::"):
        return core.make_client_for(model, use_local)
    if core.is_web_model(model):
        return core.make_client_for("web", use_local=False)
    return core.make_client(use_local)


def _run_one_automation(slug, task_id):
    """跑某分身的某个自动化任务：用【该任务自己的模型】（为空回退到分身的模型），安全工具可用、
    危险操作自动拒绝，结果存成「🤖 自动」历史对话，并写一条通知让前端弹窗。"""
    import datetime as _dt
    try:
        import agents_store
    except Exception:
        return
    a = agents_store.get_agent(slug)
    if not a:
        return
    task = agents_store.get_automation_task(slug, task_id)
    if not task:
        return
    prompt = (task.get("prompt") or "").strip()
    if not prompt:
        return
    use_local = bool(task.get("use_local", a.get("use_local", True)))
    model = (task.get("model") or a.get("model") or "").strip()
    if not model:
        model = "qwen2.5" if use_local else "web"   # 任务和分身都没指定时的兜底
    now = _dt.datetime.now()
    try:
        sys_prompt = core.build_system_prompt(request=prompt, unattended=True) + "\n\n" + \
            agents_store.build_agent_system_prompt(slug)
        messages = [{"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}]
        client = _automation_client(use_local, model)
        reply, _ = core.run_agent_autodeny(client, model, messages)
        reply = (reply or "").strip() or "（没有产出内容）"
    except Exception as e:
        reply = "（自动运行出错：%s）" % e
    cid = "auto-" + now.strftime("%Y%m%d-%H%M%S")
    if task_id:
        cid += "-" + str(task_id)[-4:]
    tname = (task.get("name") or "").strip()
    title = "🤖 自动 · " + (tname + " · " if tname else "") + now.strftime("%m-%d %H:%M")
    try:
        agents_store.save_agent_convo(slug, cid, title, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": reply}])
        agents_store.mark_automation_ran(slug, task_id, now.strftime("%Y-%m-%d"), cid)
        agents_store.bump_usage(slug)
        agents_store.add_notification(slug, a.get("name", ""), a.get("emoji", "🎭"),
                                      task_id, cid, title, task_name=tname)
    except Exception:
        pass


def _automation_loop():
    """后台循环：每 60 秒看一遍所有分身，到点的就跑（每个分身一天只跑一次）。"""
    import datetime as _dt
    stop = _auto_state["stop"]
    while not stop.is_set():
        try:
            import agents_store
            for slug, task_id in agents_store.due_automations(_dt.datetime.now()):
                if stop.is_set():
                    break
                _run_one_automation(slug, task_id)
        except Exception:
            pass
        if stop.wait(60):
            break
    _auto_state["running"] = False


def _boot_automation_scheduler():
    """随软件启动：拉起分身自动化调度线程（跟着软件活，关软件即停）。"""
    if _auto_state["running"]:
        return
    _auto_state["stop"] = _threading.Event()
    _auto_state["running"] = True
    t = _threading.Thread(target=_automation_loop, daemon=True)
    _auto_state["thread"] = t
    t.start()


def _json_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 安静，不刷屏

    def _ai_live(self, watch=False):
        """v55：「实时画面」面板要的数据：AI 池在干什么 + 批量分析正在分析哪一篇。"""
        try:
            import web_model
            pool = web_model.live_state(watch=watch)
        except Exception as e:
            pool = {"error": str(e)}
        b = _note_batch
        with _note_an_lock:
            an = dict(_note_an_state)
        cur = b.get("current") or ""
        same = bool(cur) and an.get("name") == cur
        batch = {
            "running": bool(b.get("running")), "total": b.get("total", 0), "done": b.get("done", 0),
            "ok": b.get("ok", 0), "fail": b.get("fail", 0), "round": b.get("round", 1),
            "waiting": b.get("waiting") or "", "current": cur,
            "title": (an.get("title") or "") if same else "",
            "author": (an.get("author") or "") if same else "",
            "stage": (an.get("stage") or "") if same else "",
            "note_started": (an.get("started_at") or 0) if same else 0,
        }
        return {"pool": pool, "batch": batch, "ai_gate": _ai_gate.status(), "now": _time_now()}

    def _send(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200):
        """纯文本/XML 响应，供企业微信、飞书回调用。"""
        body = (text or "").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data, ctype="application/octet-stream", status=200):
        """二进制响应（如语音播报返回的 MP3 音频）。"""
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send({}, 200)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        _log_request("GET", path)

        if path == "/ping":
            return self._send({"ok": True, "version": _cx_app_version()})

        if path == "/version":
            try:
                import app_version as _av
                note = getattr(_av, "VERSION_NOTE", "")
            except Exception:
                note = ""
            return self._send({"version": _cx_app_version(), "note": note})

        if path == "/gpu_status":
            try:
                import gpu_accel
                return self._send(gpu_accel.status())
            except Exception as e:
                return self._send({"summary": "GPU 状态读取失败：%s" % e})

        if path == "/system_access":
            try:
                import system_tools
                return self._send({"enabled": system_tools.is_enabled()})
            except Exception as e:
                return self._send({"enabled": False, "error": str(e)}, 200)

        if path == "/claude_config":
            try:
                import claude_client
                st = claude_client.status()
                try:
                    st["prefer_over_web"] = bool(claude_client.load_config().get("prefer_over_web", False))
                except Exception:
                    st["prefer_over_web"] = False
                return self._send(st)
            except Exception as e:
                return self._send({"configured": False, "sdk": False, "error": str(e)}, 200)

        if path == "/heartbeat/status":
            return self._send({"running": _hb_state["running"],
                               "interval": _hb_state["interval"],
                               "last": _hb_state["last"]})

        if path == "/video_notes":
            return self._handle_video_notes_list()
        if path == "/video_note_analyze_batch":
            b = dict(_note_batch)
            b["resume_in"] = max(0, int((b.get("resume_at") or 0) - _time_now())) if b.get("resume_at") else 0
            with _note_an_lock:
                b["stage"] = _note_an_state.get("stage", "")
                if b.get("running"):
                    b["cur_title"] = _note_an_state.get("title", "")
                    b["cur_author"] = _note_an_state.get("author", "")
                    b["cur_started"] = _note_an_state.get("started_at", 0)
            b["now"] = _time_now()
            return self._send(b)
        if path == "/video_note_analyze_progress":
            with _note_an_lock:
                return self._send(dict(_note_an_state))
        if path == "/video_note_tidy_status":        # v88
            nm = (qs.get("name") or [""])[0]
            with _tidy_lock:
                return self._send(dict(_tidy_state.get(nm) or {"running": False, "msg": ""}))
        if path == "/transcript_tidy/config":         # v88
            import transcript_tidy as _tt
            return self._send(_tt.config())
        if path == "/logs":
            # v55：软件里的「终端」面板 / 独立终端窗口，增量读后端日志
            try:
                since = int((qs.get("since") or ["0"])[0] or 0)
                limit = max(1, min(5000, int((qs.get("limit") or ["2000"])[0] or 2000)))
            except Exception:
                since, limit = 0, 2000
            if _log_capture is None:
                return self._send({"lines": [], "last": 0, "first": 0, "gap": False,
                                   "error": "日志收集没启用"})
            return self._send(_log_capture.get_lines(since, limit))
        if path == "/ai_live":
            return self._send(self._ai_live((qs.get("watch") or ["0"])[0] == "1"))
        if path == "/creator_profiles":
            try:
                import creator_profiles as _cpf
                try:                                  # v64：合并记录（博主资料卡上显示「合并了谁 · 撤销」）
                    merges = [{"id": h.get("id"), "src": h.get("src"), "dst": h.get("dst"),
                               "at": h.get("at"), "n": h.get("n", 0)} for h in _vn_load_merged()["history"]]
                except Exception:
                    merges = []
                return self._send({"profiles": _cpf.list_profiles(), "merges": merges})
            except Exception as e:
                return self._send({"profiles": {}, "error": str(e)})
        if path == "/creator_avatar":
            try:
                import creator_profiles as _cpf
                data, ctype = _cpf.get_avatar((qs.get("key") or [""])[0])
            except Exception:
                data, ctype = None, None
            if not data:
                return self._send({"error": "没有头像"}, 404)
            return self._send_bytes(data, ctype)
        if path == "/ai_live_shot":
            try:
                import web_model
                data, _ts = web_model.live_shot()
            except Exception:
                data = b""
            if not data:
                return self._send({"error": "还没有画面"}, 404)
            return self._send_bytes(data, "image/jpeg")
        if path == "/video_note_subs":                # v95：字幕（时间轴 + 原文 + 中文）
            nm = os.path.basename((qs.get("name") or [""])[0])
            d = _subs_load(nm)
            segs = _subs_fix(d.get("segments") or [])
            import video_transcribe as _vt
            lang = d.get("lang") or "zh"
            lp = d.get("local_path") or ""
            with _tr_lock:
                tr = dict(_tr_state.get(nm) or {})
            return self._send({"ok": bool(segs), "lang": lang, "lang_label": _vt.lang_label(lang),
                               "segments": segs, "has_zh": any(x.get("zh") for x in segs),
                               "local_path": lp, "local_ok": bool(lp and os.path.isfile(lp)), "translate": tr})
        if path == "/translate_engines":              # v96：翻译能用哪些模型
            try:
                names = core.installed_local_models()
            except Exception:
                names = []
            return self._send({"ok": True, "local": names, "default": _local_default_model()})
        if path == "/video_note_srt":                 # v95：导出字幕文件
            nm = os.path.basename((qs.get("name") or [""])[0])
            mode = (qs.get("mode") or ["orig"])[0]
            srt = _make_srt(_subs_fix(_subs_load(nm).get("segments") or []), mode)
            return self._send_bytes(("\ufeff" + srt).encode("utf-8"), "text/plain; charset=utf-8")
        if path == "/x_note_rebuild_status":          # v94
            with _xr_lock:
                st = dict(_xr_state)
                nm = (qs.get("name") or [""])[0]
                st["mine"] = _xr_state["last"].get(nm) if nm else None
                st["queued"] = nm in _xr_queue or nm == _xr_state.get("current")
                st.pop("last", None)
            return self._send(st)
        if path == "/video_failed":                   # v90：提取失败清单
            items = _vf_load()
            items.reverse()                            # 最近失败的在上面
            return self._send({"ok": True, "items": items})
        if path == "/video_progress":
            return self._send(self._video_progress_merged())
        if path == "/video_shot":
            return self._handle_video_shot(qs)
        if path == "/video_health":
            try:
                import video_transcribe
                return self._send(video_transcribe.health())
            except Exception as e:
                return self._send({"douyin": {"status": "error", "detail": str(e)},
                                   "versions": {}, "ytdlp": {}, "diag": {}}, 200)
        if path == "/creator_profiles_batch":
            # v60：一键识别博主主页的进度
            with _cpb_lock:
                b = {k: (list(v) if isinstance(v, list) else v) for k, v in _cpb.items()}
            now = _time_now()
            b["now"] = now
            left = max(0, b["total"] - b["done"])
            b["eta"] = int((now - b["started"]) / b["done"] * left) if b["running"] and b["done"] else 0
            return self._send(b)
        if path == "/video_deps":
            # v59：维护工具——每个依赖的已装版本、有没有新版（refresh=1 立刻重查）
            try:
                import video_transcribe
                return self._send(video_transcribe.deps_status(
                    refresh=(qs.get("refresh") or ["0"])[0] == "1"))
            except Exception as e:
                return self._send({"items": [], "error": "检查出错：%s" % e, "known": False})
        if path == "/video_diag":
            try:
                import video_transcribe
                return self._send(video_transcribe.read_diag())
            except Exception as e:
                return self._send({"exists": False, "path": "", "error": str(e)}, 200)

        if path == "/library":
            return self._handle_library()
        if path == "/library_item":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self._handle_library_item(qs.get("cat", [""])[0],
                                             qs.get("name", [""])[0])

        if path == "/conversations/list":
            # 知识云图：列出所有对话存档（带正文，供前端做关键词聚类）
            try:
                import conversation_memory as cm
                qs2 = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                with_text = qs2.get("text", ["1"])[0] != "0"
                items = cm.list_conversations(limit=800, with_text=with_text)
                return self._send({"ok": True, "items": items})
            except Exception as e:
                return self._send({"ok": False, "items": [], "message": str(e)})
        if path == "/conversations/get":
            try:
                import conversation_memory as cm
                qs2 = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                data = cm.read_conversation(qs2.get("id", [""])[0])
                if not data:
                    return self._send({"ok": False, "message": "没找到这段对话"})
                return self._send({"ok": True, **data})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)})

        if path == "/graph/overview":
            # 知识云图：各范围（对话/视频/嗅探/洞察）各有多少条，给范围选择器显示数量
            try:
                import graph_nodes
                return self._send(graph_nodes.scope_overview())
            except Exception as e:
                return self._send({"ok": False, "counts": {}, "message": str(e)})
        if path == "/graph/nodes":
            # 知识云图：按范围返回统一节点。?scope=chat|video|sniff|insight|all
            try:
                import graph_nodes
                qs2 = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                scope = qs2.get("scope", ["all"])[0]
                return self._send(graph_nodes.get_nodes(scope))
            except Exception as e:
                return self._send({"ok": False, "items": [], "message": str(e)})

        if path == "/chat_progress":
            qs = urllib.parse.urlparse(self.path).query
            cid = urllib.parse.parse_qs(qs).get("id", [""])[0]
            if cp is None:
                return self._send({"steps": [], "current": "", "pct": None,
                                   "detail": "", "done": True})
            return self._send(cp.get(cid))
        if path == "/models_info":
            try:
                import video_transcribe
                return self._send(video_transcribe.models_info())
            except Exception as e:
                return self._send({"dir": "", "models": [], "error": str(e)})
        if path.startswith("/video_note"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            return self._handle_video_note_get(q.get("name", [""])[0])

        if path == "/dashboard":
            try:
                import dashboard
                return self._send(dashboard.get_dashboard())
            except Exception as e:
                return self._send({"error": str(e)}, 200)

        if path == "/lumi/status":
            # 「懂你」面板：返回画像 / 关系 / 环境 / 演化记录 的当前内容
            try:
                import lumi_features as lf
                return self._send({
                    "ok": True,
                    "profile": lf._read(lf.OWNER_PROFILE),
                    "relationships": lf._read(lf.RELATIONS),
                    "environment": lf._read(lf.ENVIRONMENT),
                    "evolution_log": lf._read(lf.EVOLUTION_LOG),
                })
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)

        if path == "/lumi/evolve_status":
            # 人格演化实时进度（前端轮询，看到每一步在做什么、用哪个模型）
            try:
                import lumi_features as lf
                return self._send(lf.evolve_status())
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)

        if path == "/models":
            try:
                import ollama_helper
                local = ollama_helper.list_models()
                cloud = ollama_helper.known_cloud_models()
                # 伪模型（网页大模型）作为一个特殊模型项 id=web
                web = [{"id": "web", "name": "网页模型"}]
                # Claude 模型：支持多配置，每个配置一个模型选项
                claude = []
                try:
                    import claude_client
                    profiles = claude_client.load_profiles()
                    for i, p in enumerate(profiles):
                        if p.get("api_key"):
                            _cname = (p.get("name") or p.get("model") or "Claude").strip()
                            claude.append({"id": "claude::%d" % i, "name": _cname})
                except Exception:
                    pass
                return self._send({"models": local, "cloud": cloud, "web": web,
                                   "claude": claude})
            except Exception as e:
                return self._send({"models": [], "cloud": [],
                                   "web": [{"id": "web", "name": "网页模型"}],
                                   "error": str(e)}, 200)

        if path == "/task_models":
            return self._send({"task_models": core.load_task_models()})

        if path == "/web_model/config":
            try:
                import web_model
                cfg = dict(web_model.load_config())
                # 不回传明文密码，只标记是否已设置
                cfg["aiPassword"] = "***" if cfg.get("aiPassword") else ""
                return self._send({"config": cfg,
                                   "available": web_model.is_available(),
                                   "import_error": web_model.playwright_import_error()})
            except Exception as e:
                return self._send({"config": {}, "available": False, "error": str(e)}, 200)

        if path == "/web_model/state":
            try:
                import web_model
                return self._send(web_model.get_state())
            except Exception as e:
                return self._send({"state": "idle", "available": False, "error": str(e)}, 200)

        if path == "/memory/list":
            return self._send({"files": core.tool_list_memory().split("\n")})

        if path == "/memory":
            name = qs.get("name", [""])[0]
            return self._send({"content": core.read_memory_file(name)})

        if path == "/skills/list":
            try:
                import skills_store
                return self._send({"skills": skills_store.list_skills()})
            except Exception as e:
                return self._send({"skills": [], "error": str(e)}, 200)

        if path == "/skills/get":
            slug = qs.get("slug", [""])[0]
            try:
                import skills_store
                s = skills_store.get_skill(slug)
                if not s:
                    return self._send({"error": "not found"}, 404)
                return self._send({"skill": s})
            except Exception as e:
                return self._send({"error": str(e)}, 200)

        # ── 分身（Agents）：列表 / 取单个 ──
        if path == "/agents/list":
            try:
                import agents_store
                return self._send({"ok": True, "agents": agents_store.list_agents()})
            except Exception as e:
                return self._send({"ok": False, "agents": [], "error": str(e)}, 200)

        if path == "/agents/get":
            slug = qs.get("slug", [""])[0]
            try:
                import agents_store
                a = agents_store.get_agent(slug)
                if not a:
                    return self._send({"ok": False, "error": "not found"}, 404)
                return self._send({"ok": True, "agent": a})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)

        # ── 分身的会话历史：列表 / 取单段（每个分身独立工作区）──
        if path == "/agents/convos":
            try:
                import agents_store
                return self._send({"ok": True,
                                   "convos": agents_store.list_agent_convos(qs.get("slug", [""])[0])})
            except Exception as e:
                return self._send({"ok": False, "convos": [], "error": str(e)}, 200)

        if path == "/agents/convo":
            try:
                import agents_store
                c = agents_store.get_agent_convo(qs.get("slug", [""])[0], qs.get("id", [""])[0])
                if not c:
                    return self._send({"ok": False, "error": "not found"}, 404)
                return self._send({"ok": True, "convo": c})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)

        if path == "/agents/notifications":
            # 前端定时来取未读的自动化结果通知（用于弹窗提醒）
            try:
                import agents_store
                return self._send({"ok": True, "items": agents_store.list_notifications(True)})
            except Exception as e:
                return self._send({"ok": False, "items": [], "error": str(e)}, 200)

        if path == "/loop/status":
            try:
                import loop_engine
                return self._send(loop_engine.get_status())
            except Exception as e:
                return self._send({"running": False, "error": str(e)}, 200)

        if path == "/harness/config":
            try:
                import harness
                return self._send({"config": harness.get_config()})
            except Exception as e:
                return self._send({"error": str(e)}, 200)

        if path == "/harness/runs":
            try:
                import harness
                return self._send({"runs": harness.list_runs(), "metrics": harness.metrics_summary()})
            except Exception as e:
                return self._send({"runs": [], "metrics": {"count": 0}, "error": str(e)}, 200)

        if path == "/sniff/discover":
            # 「按关键词找信息源」的进度和结果（前端轮询）
            try:
                import source_discover
                return self._send(source_discover.status())
            except Exception as e:
                return self._send({"running": False, "error": str(e), "results": []})
        if path == "/scrapling/status":
            # v108：网页抓取增强（Scrapling）装好了没有
            try:
                import scrapling_fetch
                return self._send(scrapling_fetch.status())
            except Exception as e:
                return self._send({"ready": False, "installing": False, "error": str(e)}, 200)
        if path == "/sniff/sources":
            try:
                import sniffer
                return self._send({"sources": sniffer.list_sources(),
                                   "categories": sniffer.list_categories(),
                                   "config": sniffer.get_config()})
            except Exception as e:
                return self._send({"sources": [], "categories": [], "error": str(e)}, 200)

        if path == "/sniff/feed":
            try:
                import sniffer
                return self._send({"feed": sniffer.get_feed(), "status": sniffer.get_run_state()})
            except Exception as e:
                return self._send({"feed": [], "error": str(e)}, 200)

        if path == "/creator/discover":
            # v78：博主页「搜索推荐」的进度和结果（前端轮询）
            try:
                import creator_discover
                return self._send(creator_discover.status())
            except Exception as e:
                return self._send({"running": False, "error": str(e), "results": []})
        if path == "/creator/avatars_status":
            # v76：「一键解析博主主页」的进度
            st = {k: v for k, v in _cw_av.items() if k != "tried"}
            st["now"] = _time_now()
            return self._send(st)
        if path == "/creator/list":
            # 博主监控：清单 + 配置（每天几点自动扫等）
            try:
                import creator_watch
                cl = creator_watch.list_creators()
                _cw_attach_avatars(cl)                    # v74：博主头像（和视频页共用博主资料）
                return self._send({"ok": True,
                                   "creators": cl,
                                   "config": creator_watch.get_config()})
            except Exception as e:
                return self._send({"ok": False, "creators": [], "error": str(e)}, 200)

        if path == "/creator/x_cookie_status":
            # 查询 X Cookie 是否已配置（前端添加 X 博主时用来决定要不要弹框）
            try:
                import x_watch
                return self._send({"ok": True, "has_cookie": x_watch.has_cookie()})
            except Exception as e:
                return self._send({"ok": False, "has_cookie": False, "error": str(e)}, 200)

        if path == "/creator/findings":
            # 博主监控：「本次新增」待办清单 + 扫描运行状态
            try:
                import creator_watch
                return self._send({"ok": True,
                                   "findings": creator_watch.get_findings(),
                                   "scan": creator_watch.get_scan_state()})
            except Exception as e:
                return self._send({"ok": False, "findings": [], "error": str(e)}, 200)

        if path == "/insight/status":
            # 「洞察」爬虫：返回配置 / 可分析篇数 / 运行日志 / 最近报告 / 调度状态
            try:
                import insight_crawler
                return self._send(insight_crawler.status())
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)

        if path == "/insight/analyzable":
            # 全部可分析文件的详细清单（已读/未读 + 每篇摘要），供数字点开看明细
            try:
                import insight_crawler
                return self._send(insight_crawler.analyzable_list())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/insight/research_item":
            # 读一篇「主动研究」成果的正文（限定在 insight_research 目录内，安全）
            try:
                import insight_crawler
                from pathlib import Path
                name = qs.get("name", [""])[0]
                rdir = insight_crawler.RESEARCH_DIR.resolve()
                target = (rdir / (name + ".md")).resolve()
                if str(target).startswith(str(rdir)) and target.exists():
                    return self._send({"ok": True,
                                       "content": target.read_text(
                                           encoding="utf-8", errors="replace")})
                return self._send({"ok": False, "message": "找不到该研究文档"}, 200)
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/datadb/overview":
            try:
                import datadb
                return self._send(datadb.overview())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/datadb/list":
            try:
                import datadb
                return self._send(datadb.list_category(qs.get("cat", [""])[0]))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/datadb/item":
            try:
                import datadb
                return self._send(datadb.read_item(qs.get("cat", [""])[0],
                                                   qs.get("name", [""])[0]))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/datadb/export":
            try:
                import datadb
                res = datadb.export_item(qs.get("cat", [""])[0], qs.get("name", [""])[0])
                if not res:
                    return self._send({"ok": False, "message": "无法导出该项"}, 200)
                data, fname = res
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                try:
                    import urllib.parse as _up
                    self.send_header("Content-Disposition",
                                     "attachment; filename*=UTF-8''" + _up.quote(fname))
                except Exception:
                    self.send_header("Content-Disposition", "attachment")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/wecom/callback":
            try:
                import wecom_bot
                cfg = wecom_bot.load_config()
                echo = wecom_bot.handle_callback_get(cfg, qs)
                if echo is not None:
                    return self._send_text(echo)
            except Exception:
                pass
            return self._send_text("", 200)

        if path == "/feishu_inbox/status":         # v84：飞书机器人收链接
            try:
                import feishu_inbox
                return self._send(feishu_inbox.status())
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})

        if path == "/phone_inbox/status":          # v83：手机发链接面板
            try:
                import phone_inbox
                return self._send(phone_inbox.status())
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})

        self._send({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _log_request("POST", path)

        # 企业微信 / 飞书回调要原始 body，单独先处理
        if path == "/wecom/callback":
            return self._handle_wecom_post(qs)
        if path == "/feishu/callback":
            return self._handle_feishu_post()

        body = _json_body(self)

        if path in ("/feishu_inbox/incoming", "/feishu_inbox/alive", "/feishu_inbox/config"):   # v84：飞书
            try:
                import feishu_inbox
                if path == "/feishu_inbox/incoming":
                    return self._send(feishu_inbox.incoming(body))
                if path == "/feishu_inbox/alive":
                    return self._send(feishu_inbox.alive(body))
                return self._send(feishu_inbox.configure(
                    body.get("app_id"), body.get("app_secret"),
                    None if body.get("enabled") is None else bool(body.get("enabled"))))
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})

        if path in ("/phone_inbox/enable", "/phone_inbox/new_code", "/phone_inbox/defaults"):   # v83：手机发链接
            try:
                import phone_inbox
                if path == "/phone_inbox/defaults":       # v86：电脑上当前的质量 / 模型选项，手机和飞书发来的照这个办
                    phone_inbox.remember_defaults(body)
                    return self._send({"ok": True})
                if path == "/phone_inbox/new_code":
                    return self._send(phone_inbox.new_code())
                return self._send(phone_inbox.set_enabled(bool(body.get("on"))))
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})

        if path == "/chat":
            return self._handle_chat(body)
        if path == "/tts":
            return self._handle_tts(body)
        if path == "/system_access":
            return self._handle_system_access(body)
        if path == "/claude_config":
            try:
                import claude_client
                action = (body or {}).get("action", "save")
                if action == "add":
                    idx = claude_client.add_profile(body.get("profile") or body)
                    return self._send({"ok": True, "index": idx, **claude_client.status()})
                elif action == "update":
                    idx = int(body.get("index", 0))
                    claude_client.update_profile(idx, body.get("profile") or body)
                    return self._send({"ok": True, **claude_client.status()})
                elif action == "delete":
                    idx = int(body.get("index", -1))
                    claude_client.delete_profile(idx)
                    return self._send({"ok": True, **claude_client.status()})
                elif action == "set_pref":
                    # 设置「用 Claude 替代网页模型」开关
                    cfg = claude_client.load_config()
                    cfg["prefer_over_web"] = bool(body.get("prefer_over_web", False))
                    claude_client.save_config_raw(cfg)
                    st = claude_client.status()
                    st["prefer_over_web"] = cfg["prefer_over_web"]
                    return self._send({"ok": True, **st})
                else:
                    # 向后兼容旧的 save 逻辑
                    claude_client.save_config(body or {})
                    return self._send({"ok": True, **claude_client.status()})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)
        if path == "/task_models":
            try:
                tm = core.save_task_models(body.get("task_models") or body)
                return self._send({"ok": True, "task_models": tm})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)
        if path == "/web_model/config":
            try:
                import web_model
                incoming = dict(body or {})
                # 密码占位符 *** 表示不修改
                if incoming.get("aiPassword") in ("***", None):
                    incoming.pop("aiPassword", None)
                # 用户在设置里显式动过「联网搜索」开关 → 记一笔，尊重其选择（不再被默认兜底覆盖）
                if "enableSearch" in incoming:
                    incoming["enableSearchUserSet"] = True
                cfg = web_model.save_config(incoming)
                cfg["aiPassword"] = "***" if cfg.get("aiPassword") else ""
                return self._send({"ok": True, "config": cfg})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)
        if path == "/web_model/test":
            return self._handle_web_model_test(body)
        if path == "/heartbeat":
            return self._handle_heartbeat(body)
        if path == "/intake_scan":                    # v118：拖进来 / 粘进来的文件和文件夹 → 能提取的文件清单
            try:
                import intake as _ik
                return self._send(_ik.scan_paths(body.get("paths") or []))
            except Exception as e:
                return self._send({"files": [], "error": str(e)[:200]})
        if path == "/intake_kind":                    # v112：加工——认一认放进来的是什么
            try:
                import intake as _ik
                return self._send(_ik.describe(body.get("text") or ""))
            except Exception as e:
                return self._send({"kind": "", "error": str(e)[:200]})
        if path == "/video_transcribe":
            return self._handle_video_transcribe(body)
        if path == "/video_cancel":
            try:
                return self._send(_cancel_video_jobs())
            except Exception as e:
                return self._send({"ok": False, "error": str(e)}, 200)
        if path == "/video_detect_subtitle":
            return self._handle_video_detect_subtitle(body)
        if path == "/video_install":
            return self._handle_video_install(body)
        if path == "/video_note_translate":           # v95：逐句翻译成中文（后台做）
            nm = os.path.basename((body.get("name") or "").strip())
            if not nm.endswith(".md") or not (_cx_video_dir() / nm).exists():
                return self._send({"ok": False, "error": "找不到这条笔记"})
            if not (_subs_load(nm).get("segments")):
                return self._send({"ok": False, "error": "这条笔记没有时间轴（太早以前提取的，或者是文章 / 文档），没法逐句翻译"})
            with _tr_lock:
                cur = _tr_state.get(nm)
                if cur and cur.get("running"):
                    return self._send({"ok": True, "running": True})
                if body.get("redo"):
                    d = _subs_load(nm)
                    for sg in d.get("segments") or []:
                        sg.pop("zh", None)
                    _subs_path(nm).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
                _tr_state[nm] = {"running": True, "msg": "准备翻译…", "ok": False, "done": 0, "total": 0}
            eng = (body.get("engine") or "local").strip()
            _threading.Thread(target=_tr_worker, args=(nm, eng), daemon=True).start()
            return self._send({"ok": True, "running": True})
        if path == "/video_note_srt_save":            # v95：字幕存到本地视频旁边（播放器自动加载）
            nm = os.path.basename((body.get("name") or "").strip())
            mode = body.get("mode") or "zh"
            d = _subs_load(nm)
            lp = d.get("local_path") or ""
            if not (lp and os.path.isfile(lp)):
                return self._send({"ok": False, "error": "找不到原来的视频文件（只有「导入本地文件」的视频能存到旁边）"})
            import video_transcribe as _vt
            suf = {"zh": ".zh", "both": ".双语", "orig": "." + (d.get("lang") or "orig")}.get(mode, ".zh")
            out = os.path.splitext(lp)[0] + suf + ".srt"
            try:
                with open(out, "w", encoding="utf-8-sig") as fh:
                    fh.write(_make_srt(_subs_fix(d.get("segments") or []), mode))
            except Exception as e:
                return self._send({"ok": False, "error": "存不进去：%s" % e})
            return self._send({"ok": True, "path": out})
        if path == "/x_note_rebuild":                 # v94：推文笔记重新整理成「博主原话 + 链接原文」
            import tweet_parts as _tp
            if body.get("all"):
                names = []
                for fp in sorted(_cx_video_dir().glob("*.md")):
                    try:
                        with open(fp, encoding="utf-8", errors="replace") as fh:
                            if _tp.is_tweet_note(fh.read(1500)):
                                names.append(fp.name)
                    except Exception:
                        pass
            else:
                nm = os.path.basename((body.get("name") or "").strip())
                if not nm.endswith(".md") or not (_cx_video_dir() / nm).exists():
                    return self._send({"ok": False, "error": "找不到这条笔记"})
                names = [nm]
            n = _xr_enqueue(names)
            return self._send({"ok": True, "queued": n, "total": len(names)})
        if path == "/video_failed":                   # v90：重新提取 / 删掉失败的任务
            action = (body.get("action") or "").strip()
            items = _vf_load()
            ids = None if body.get("all") else set(body.get("ids") or [])
            picked = [x for x in items if ids is None or x.get("id") in ids]
            if action == "delete":
                _vf_remove(ids={x["id"] for x in picked})
                return self._send({"ok": True, "deleted": len(picked)})
            if action == "retry":
                lv = body.get("level") or ""
                n = 0
                for rec in picked:
                    job = {f: rec.get(f) for f in _VF_KEEP if rec.get(f) not in (None, "")}
                    job.setdefault("url", rec.get("local_path") or "")
                    if lv in ("speed", "balanced", "accurate", "ultra", "ja", "anime"):
                        job["level"] = lv
                    job.setdefault("level", "balanced")
                    job.setdefault("use_local", True)
                    job.setdefault("model", "qwen2.5")
                    job.setdefault("mode", "auto")
                    job["_vf_tries"] = int(rec.get("tries") or 0)     # 再失败时次数接着算
                    if not job.get("url"):
                        continue
                    _enqueue_video(job)
                    n += 1
                # 送回队列的先从清单拿掉；这次还没成功会再放回来（次数累加）
                _vf_remove(ids={x["id"] for x in picked})
                return self._send({"ok": True, "queued": n,
                                   "message": "已把 %d 个重新放进提取队列" % n if n else "没有可重新提取的"})
            return self._send({"ok": False, "error": "不认识的操作"})
        if path == "/video_note_delete":
            return self._handle_video_note_delete(body)
        if path == "/video_note_analyze_batch":
            return self._handle_video_note_analyze_batch(body)
        if path == "/web_model/window":
            # v55：显示 / 隐藏 AI 池浏览器（隐藏＝挪到屏幕外，照常工作）
            try:
                import web_model
                ok, msg = web_model.request_window((body or {}).get("action", ""))
            except Exception as e:
                ok, msg = False, "出错：%s" % e
            _clog("AI池", msg)
            return self._send({"ok": ok, "message": msg})
        if path == "/console":
            # v55：启动时的黑窗口：最小化 / 显示
            if _log_capture is None:
                return self._send({"ok": False, "message": "日志收集没启用"})
            _act = (body or {}).get("action") or (qs.get("action") or ["status"])[0]
            ok, msg = _log_capture.console_window(_act)
            if _act != "status":
                _clog("黑窗口", ("✓ " if ok else "✗ ") + msg)
            return self._send({"ok": ok, "message": msg, "hidden": _log_capture.console_hidden()})
        if path == "/creator_profiles_batch":
            # v60：一键识别博主主页：{keys:[…]} 开始；{stop:true} 停止
            b = body or {}
            if b.get("stop"):
                _cpb["stop"] = True
                return self._send({"ok": True, "stopping": True})
            seen, keys = set(), []
            for k in b.get("keys") or []:
                k = str(k or "").strip()
                if k and k != "未填作者" and k not in seen:
                    seen.add(k)
                    keys.append(k)
            if not keys:
                return self._send({"ok": False, "message": "没有要识别的博主"})
            with _cpb_lock:
                if _cpb["running"]:
                    return self._send({"ok": False, "message": "已经在识别了（%d/%d），等它结束或先点「停止」"
                                       % (_cpb["done"], _cpb["total"])})
                _cpb.update(running=True, stop=False, total=len(keys), done=0, ok=0, noav=0, fail=0,
                            skip=0, current="", started=_time_now(), finished=0, results=[], note="", renamed=[])
            _clog("博主", "开始一键识别博主主页：%d 个" % len(keys))
            _threading.Thread(target=_cpb_worker, args=(keys,), daemon=True).start()
            return self._send({"ok": True, "total": len(keys)})
        if path == "/creator_profile":
            # v58：博主主页（绑定链接取头像 / 刷新 / 手动上传头像 / 解除绑定）
            try:
                import creator_profiles as _cpf
                b = body or {}
                act = b.get("action", "bind")
                key = (b.get("key") or "").strip()
                if act == "bind":
                    ok, res = _cpf.bind(key, b.get("url") or "")
                elif act == "refresh":
                    ok, res = _cpf.refresh(key)
                elif act == "avatar":
                    ok, res = _cpf.set_avatar_data(key, b.get("data") or "")
                elif act == "remove":
                    ok, res = _cpf.remove(key)
                elif act == "auto":
                    # 根据这个博主的视频自动找主页（新的视频在前，找不到会再试两条）
                    urls, why = _vn_pick_sources(key)
                    if not urls:
                        ok, res = False, why + "，没法自动找，可以粘贴主页链接"
                    else:
                        ok, res, _k = _cpf.auto_bind_from_videos(key, urls, force=True)
                        if ok and isinstance(res, dict):
                            try:
                                _nk, rn = _vn_after_bind(key, res)
                                if rn:
                                    res["note"] = (res.get("note") or "") + "（博主改名了：%s，软件里已改成新名字）" % rn
                            except Exception:
                                pass
                else:
                    ok, res = False, "不认识的操作"
            except Exception as e:
                ok, res = False, "出错：%s" % e
            _clog("博主", "%s %s：%s" % ("✓" if ok else "✗", (body or {}).get("key", ""),
                                       res.get("name", "好了") if isinstance(res, dict) else res))
            if ok:
                return self._send({"ok": True, "profile": res if isinstance(res, dict) else None,
                                   "message": (res.get("note") if isinstance(res, dict) else res) or ""})
            return self._send({"ok": False, "message": res})
        if path == "/video_note_analyze":
            return self._handle_video_note_analyze(body)
        if path == "/transcript_tidy/config":         # v88：提取后自动整理原文 开 / 关
            import transcript_tidy as _tt
            return self._send(_tt.set_config(body.get("auto")))
        if path == "/video_note_tidy":                # v88：给已存的笔记整理原文
            nm = os.path.basename((body.get("name") or "").strip())
            if not nm.endswith(".md") or not (_cx_video_dir() / nm).exists():
                return self._send({"ok": False, "error": "找不到这条笔记"})
            with _tidy_lock:
                cur = _tidy_state.get(nm)
                if cur and cur.get("running"):
                    return self._send({"ok": True, "running": True})
                _tidy_state[nm] = {"running": True, "msg": "准备整理…", "ok": False}
            _threading.Thread(target=_note_tidy_worker, args=(nm,), daemon=True).start()
            return self._send({"ok": True, "running": True})
        if path == "/video_note_analyze_stop":
            # v66：停止正在做的这一条 AI 分析（AI 池卡住时用）；原文不受影响
            if _note_batch.get("running"):
                return self._send({"ok": False, "message": "现在是批量分析在跑，请点「批量 AI 分析」那一行的「停止」"})
            with _note_an_lock:
                running = bool(_note_an_state.get("running"))
                if running:
                    _note_an_state["stage"] = "正在停止…"
                    _note_an_state["stop_req"] = True          # v67：还在排队的也能停
            if not running:
                return self._send({"ok": True, "message": "现在没有在分析"})
            try:
                import web_model
                web_model.cancel_current("你点了停止")
            except Exception:
                pass
            _clog("视频", "⏹ 你点了停止：放下正在做的 AI 分析（原文不受影响）")
            return self._send({"ok": True, "message": "正在停止…"})
        if path == "/video_note_set_author":
            return self._handle_video_note_set_author(body)
        if path == "/video_folder":
            return self._handle_video_folder(body)
        if path == "/creator/discover":
            # v78：搜索推荐：输入想看的领域，AI 池联网找前 N 个网站 / 博主
            try:
                import creator_discover
                return self._send(creator_discover.start(body.get("keyword", ""), body.get("n", 10)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/creator/avatars":
            # v76：一键解析博主主页 {action: start, ids?: [...], force?: bool} / {action: stop}
            if (body.get("action") or "start") == "stop":
                _cw_av["stop"] = True
                return self._send({"ok": True, "message": "正在停止…"})
            try:
                ok, msg = _cw_avatar_start(body.get("ids") or [], bool(body.get("force")))
            except Exception as e:
                ok, msg = False, "出错：%s" % e
            return self._send({"ok": ok, "message": msg})
        if path == "/creator_merge":
            # v64：合并博主 {src, dst}；撤销 {action: "undo", id}
            try:
                if (body.get("action") or "") == "undo":
                    ok, msg = _vn_unmerge((body.get("id") or "").strip())
                else:
                    ok, msg = _vn_merge_bloggers(body.get("src"), body.get("dst"))
                return self._send({"ok": ok, "message": msg})
            except Exception as e:
                return self._send({"ok": False, "message": "出错：%s" % e})
        if path == "/library_set_tags":
            return self._handle_library_set_tags(body)
        if path == "/library_autotag":
            return self._handle_library_autotag(body)
        if path == "/summarize_title":
            return self._handle_summarize_title(body)
        if path == "/video_mindmap":
            return self._handle_video_mindmap(body)
        if path == "/video_move_models":
            return self._handle_video_move_models(body)
        if path == "/heartbeat/start":
            return self._handle_heartbeat_start(body)
        if path == "/heartbeat/stop":
            return self._handle_heartbeat_stop(body)
        if path == "/remember":
            return self._handle_remember(body)
        if path == "/telegram/start":
            return self._handle_telegram_start(body)
        if path == "/push/test":
            return self._handle_push_test(body)
        if path == "/briefing":
            return self._handle_briefing(body)
        if path == "/competitors":
            return self._handle_competitors(body)
        if path == "/daily_task":
            return self._handle_daily_task(body)
        if path == "/lumi/evolve":
            return self._handle_lumi_evolve(body)
        if path == "/lumi/scan":
            return self._handle_lumi_scan(body)
        if path == "/lumi/greeting":
            return self._handle_lumi_greeting(body)
        if path == "/insight/config":
            try:
                import insight_crawler
                return self._send({"ok": True,
                                   "config": insight_crawler.save_config(body)})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/insight/run":
            try:
                import insight_crawler
                return self._send(insight_crawler.start_run(
                    use_local=body.get("use_local"),
                    model=body.get("model"),
                    scopes=body.get("scopes"),
                    source="manual"))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/insight/stop":
            try:
                import insight_crawler
                return self._send(insight_crawler.stop_run())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/insight/reset":
            try:
                import insight_crawler
                return self._send(insight_crawler.reset_learned())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/insight/clear_runs":
            try:
                import insight_crawler
                return self._send(insight_crawler.clear_runs())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/datadb/delete":
            try:
                import datadb
                return self._send(datadb.delete_item(
                    body.get("cat", ""), body.get("name", ""),
                    force=bool(body.get("force", False))))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/datadb/set_tags":
            try:
                import datadb
                return self._send(datadb.set_tags(
                    body.get("cat", ""), body.get("name", ""),
                    body.get("tags") or []))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)
        if path == "/env_check":
            use_local = body.get("use_local", True)
            model = body.get("model", "qwen2.5")
            try:
                import ollama_helper
                return self._send(ollama_helper.environment_check(use_local, model))
            except Exception as e:
                return self._send({"ok": False, "items": [
                    {"name": "环境检查", "ok": False, "detail": str(e)}]}, 200)
        if path == "/skills/save":
            try:
                import skills_store
                slug = skills_store.save_skill(
                    body.get("slug", ""), body.get("content", ""),
                    name=body.get("name", ""), description=body.get("description", ""))
                return self._send({"ok": True, "slug": slug})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/skills/delete":
            try:
                import skills_store
                ok = skills_store.delete_skill(body.get("slug", ""))
                return self._send({"ok": ok})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/skills/toggle":
            try:
                import skills_store
                skills_store.set_enabled(body.get("slug", ""), bool(body.get("enabled", True)))
                return self._send({"ok": True})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/skills/from_conversation":
            return self._handle_skill_from_conversation(body)

        # ── 分身（Agents）：保存（新建/编辑）/ 删除 / 把反馈并进判断标准 ──
        if path == "/agents/save":
            try:
                import agents_store
                rec = agents_store.save_agent(body or {})
                return self._send({"ok": True, "slug": rec["slug"], "agent": rec})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/agents/delete":
            try:
                import agents_store
                ok = agents_store.delete_agent(body.get("slug", ""))
                return self._send({"ok": ok})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/agents/update_standard":
            try:
                import agents_store
                res = agents_store.update_standard(
                    body.get("slug", ""), body.get("feedback", ""))
                return self._send(res)
            except Exception as e:
                return self._send({"ok": False, "message": str(e), "standard": ""}, 200)

        # ── 分身会话历史：保存（自动落盘）/ 删除 ──
        if path == "/agents/convo_save":
            try:
                import agents_store
                return self._send(agents_store.save_agent_convo(
                    body.get("slug", ""), body.get("id", ""),
                    body.get("title", ""), body.get("messages") or []))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/agents/convo_delete":
            try:
                import agents_store
                return self._send(agents_store.delete_agent_convo(
                    body.get("slug", ""), body.get("id", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        # ── 分身：保存它【自己的】模型/模式偏好（各分身独立）──
        if path == "/agents/model_save":
            try:
                import agents_store
                return self._send(agents_store.set_agent_model(
                    body.get("slug", ""), body.get("use_local", True),
                    body.get("model", ""), body.get("smart_routing", True)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        # ── 分身自动化（SOP/定时任务）：保存多任务设置 / 立即手动跑某个任务 ──
        if path == "/agents/automation_save":
            try:
                import agents_store
                return self._send(agents_store.set_automation(
                    body.get("slug", ""), {"tasks": body.get("tasks", [])}))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/agents/automation_run":
            # 立即在后台跑一次该分身的某个任务（不阻塞；结果完成后出现在历史对话里，并弹窗提醒）
            try:
                slug = body.get("slug", "")
                task_id = body.get("task_id", "")
                import agents_store
                if not agents_store.get_agent(slug):
                    return self._send({"ok": False, "message": "分身不存在"}, 200)
                if not agents_store.get_automation_task(slug, task_id):
                    return self._send({"ok": False, "message": "任务不存在，请先保存设置"}, 200)
                t = _threading.Thread(target=_run_one_automation, args=(slug, task_id), daemon=True)
                t.start()
                return self._send({"ok": True, "message": "已在后台开始运行，完成后会弹窗提醒并出现在历史对话里。"})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/agents/notifications/seen":
            try:
                import agents_store
                agents_store.mark_notifications_seen(body.get("ids", []))
                return self._send({"ok": True})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/loop/start":
            try:
                import loop_engine
                return self._send(loop_engine.start_loop(
                    body.get("use_local", True), body.get("model", "qwen2.5"),
                    body.get("goal", ""), body.get("criteria", []),
                    body.get("max_rounds", 5), body.get("allow_actions", False)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/loop/stop":
            try:
                import loop_engine
                return self._send(loop_engine.stop_loop())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/harness/config":
            try:
                import harness
                return self._send({"ok": True, "config": harness.save_config(body)})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/harness/runs/clear":
            try:
                import harness
                harness.clear_runs()
                return self._send({"ok": True})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/discover":
            # 按关键词找行业信息源：后台开始查找，前端用 GET /sniff/discover 轮询
            try:
                import source_discover
                return self._send(source_discover.start(body.get("keyword", ""), body.get("n", 15)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/source/add_many":
            # v108：一次加入多个网站（趋势瞭望台「批量加入嗅探」）
            try:
                import sniffer
                return self._send(sniffer.add_sources(body.get("items") or [],
                                                      category=body.get("category", "AI动态")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/scrapling/install":
            try:
                import scrapling_fetch
                return self._send(scrapling_fetch.start_install())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/source/add":
            try:
                import sniffer
                return self._send(sniffer.add_source(
                    body.get("title", ""), body.get("url", ""),
                    category=body.get("category", "AI动态")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/source/category":
            try:
                import sniffer
                return self._send(sniffer.set_category(body.get("id", ""), body.get("category", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/category/toggle":
            try:
                import sniffer
                return self._send(sniffer.toggle_category(
                    body.get("category", ""), body.get("enabled", True)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/source/delete":
            try:
                import sniffer
                return self._send(sniffer.delete_source(body.get("id", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/source/toggle":
            try:
                import sniffer
                return self._send(sniffer.toggle_source(body.get("id", ""), body.get("enabled", True)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/run":
            try:
                import sniffer
                return self._send(sniffer.start_async(
                    body.get("use_local", True), body.get("model", "qwen2.5")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/report":
            return self._handle_sniff_report(body)

        if path == "/sniff/config":
            try:
                import sniffer
                return self._send({"ok": True, "config": sniffer.save_config(body)})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/sniff/feed/clear":
            try:
                import sniffer
                sniffer.clear_feed()
                return self._send({"ok": True})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        # ───────────── 博主监控（关注的博主主页 → 列新视频 → 勾选批量提取）─────────────
        if path == "/creator/add":
            try:
                import creator_watch
                return self._send(creator_watch.add_creator(
                    body.get("url", ""),
                    platform=body.get("platform", "auto"),
                    title=body.get("title", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/delete":
            try:
                import creator_watch
                return self._send(creator_watch.delete_creator(body.get("id", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/toggle":
            try:
                import creator_watch
                return self._send(creator_watch.toggle_creator(
                    body.get("id", ""), body.get("enabled", True)))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/rename":
            try:
                import creator_watch
                return self._send(creator_watch.rename_creator(
                    body.get("id", ""), body.get("title", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/translate":
            # 把若干视频标题批量翻译成中文（前端列视频后调用，给英文标题配中文）
            try:
                titles = body.get("titles") or []
                zh, note = _translate_lines(titles,
                                            use_local=body.get("use_local", True),
                                            model=body.get("model", "qwen2.5"))
                # 翻译成功的，回存到全局译文表，下次直接显示中文、不再重翻
                try:
                    import creator_watch
                    pairs = []
                    for t, z in zip(titles, zh):
                        if t and z and z.strip():
                            pairs.append({"title": t, "zh": z})
                    if pairs:
                        creator_watch.save_translations(pairs)
                except Exception:
                    pass
                return self._send({"ok": True, "translations": zh, "note": note})
            except Exception as e:
                return self._send({"ok": False, "translations": [], "message": str(e)}, 200)

        if path == "/creator/save_translations":
            # 前端把已翻好的「原文→中文」回存（持久化，跨重启复用）
            try:
                import creator_watch
                return self._send(creator_watch.save_translations(body.get("pairs") or []))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/x_cookie_save":
            # 保存用户粘贴的 X（推特）登录 Cookie
            try:
                import x_watch
                return self._send(x_watch.save_cookie(body.get("cookie") or ""))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/videos_cached":
            # 改动4（秒开）：只读「上次列到的视频」持久缓存，不联网，立刻返回。
            # 前端点开博主时先调它把缓存秒显示，再调 /creator/videos 后台刷新。
            try:
                import creator_watch
                cid = body.get("id", "")
                data = creator_watch.get_cached_videos(cid)
                if data is None:
                    return self._send({"ok": False, "cached": False}, 200)
                # 给每条视频补 creator_id 并标注「已提取」，界面据此显示角标/禁用按钮
                for v in (data.get("videos") or []):
                    if isinstance(v, dict):
                        v.setdefault("creator_id", cid)
                creator_watch._annotate_extracted(data.get("videos") or [])
                return self._send({"ok": True, **data})
            except Exception as e:
                return self._send({"ok": False, "cached": False, "message": str(e)}, 200)

        if path == "/creator/videos":
            # 列出某博主主页最近的视频（只读，不动快照），给界面挑选/批量提取用
            try:
                import creator_watch
                cid = body.get("id", "")
                data = creator_watch.list_videos(cid, body.get("limit", 0))
                for v in (data.get("videos") or []):
                    if isinstance(v, dict):
                        v.setdefault("creator_id", cid)
                creator_watch._annotate_extracted(data.get("videos") or [])
                return self._send({"ok": True, **data})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/scan":
            # 带 id：同步扫这一个（前端等结果）；不带 id：后台扫全部（前端轮询状态）
            try:
                import creator_watch
                cid = (body.get("id") or "").strip()
                if cid:
                    return self._send({"ok": True, "result": creator_watch.scan_one(cid)})
                return self._send(creator_watch.scan_all_async())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/extract":
            # 把勾选的视频灌进视频提取队列，并从待办里移除。
            # 已提取过的（在 extracted 记录里）直接跳过，不重复送队列。
            try:
                import creator_watch
                items = body.get("items") or []
                # v89：识别质量用前端传来的（视频页当前选的）；老界面没传 → 用电脑上最近一次提取时的选择
                level = body.get("level") or ""
                if level not in ("speed", "balanced", "accurate", "ultra", "ja", "anime"):
                    level = ""
                    try:
                        import phone_inbox as _pi
                        level = ((_pi._load() or {}).get("defaults") or {}).get("level") or ""
                    except Exception:
                        level = ""
                    if level not in ("speed", "balanced", "accurate", "ultra", "ja", "anime"):
                        level = "balanced"
                _cw_store = None
                try:
                    _cw_store = creator_watch._load()        # v89：读一次，后面每条都用它（以前每条读一遍）
                except Exception:
                    _cw_store = None
                use_local = body.get("use_local", True)
                model = body.get("model", "qwen2.5")
                mode = body.get("mode") or "auto"
                # force=True 时无视「已提取」记录，强制重新提取（前端可不传，默认 False）
                force = bool(body.get("force", False))
                if mode not in ("auto", "subtitle_only", "transcribe"):
                    mode = "auto"
                queued, skipped = 0, 0
                done_keys, new_marks, skipped_items = [], [], []
                x_saved = 0   # X 推文直接存成笔记的条数（不走视频队列）
                for it in items:
                    u = (it.get("url") or "").strip()
                    if not u:
                        continue
                    cid = it.get("creator_id")
                    vid = it.get("vid")
                    # 已提取过 → 跳过（除非强制）
                    if (not force) and creator_watch.is_extracted(cid, vid, u):
                        skipped += 1
                        skipped_items.append({"creator_id": cid, "vid": vid, "url": u})
                        # 跳过的也从「本次新增」待办里清掉，免得一直挂着
                        done_keys.append({"creator_id": cid, "vid": vid, "url": u})
                        continue
                    # ── X 推文：文字内容，直接存成笔记，不进视频听写队列 ──
                    # 前端 item 可能没带 platform/text，从待办记录里补回来
                    meta = {}
                    if (not it.get("text")) or (not it.get("platform")) or (not it.get("title_zh")):
                        try:
                            meta = creator_watch.get_finding_meta(cid, vid, u, store=_cw_store) or {}
                        except Exception:
                            meta = {}
                    plat = it.get("platform") or meta.get("platform") or ""
                    is_x = (plat == "x") or ("x.com/" in u) or ("twitter.com/" in u)
                    tweet_text = (it.get("text") or meta.get("text") or "").strip()
                    if is_x and tweet_text:
                        if not it.get("uploader"):
                            it["uploader"] = meta.get("uploader") or ""
                        if not it.get("title"):
                            it["title"] = meta.get("title") or ""
                        if not it.get("title_zh"):
                            it["title_zh"] = meta.get("title_zh") or ""
                        if not it.get("x"):
                            it["x"] = meta.get("x")
                        try:
                            # v89：马上存成笔记，不在这里等 AI（以前每条推文要排队调两次 AI，点了半天没反应）；
                            #      需要时在笔记上点「🤖 AI 分析」，和视频笔记一样
                            _xfn = self._save_x_note(it, tweet_text, use_local, model, analyze=False)
                            x_saved += 1
                            if _xfn:
                                _xr_enqueue([_xfn])     # v94：后台抓链接里的原帖 / 文章，补全「链接原文」
                        except Exception as _xe:
                            _clog("嗅探", "推文存笔记没成功：%s" % _xe)
                        new_marks.append({"creator_id": cid, "vid": vid, "url": u,
                                          "title": it.get("title") or ""})
                        done_keys.append({"creator_id": cid, "vid": vid, "url": u})
                        continue
                    _enqueue_video({"url": u, "level": level, "use_local": use_local,
                                    "model": model, "screenshot": False, "link": False,
                                    "mode": mode})
                    queued += 1
                    done_keys.append({"creator_id": cid, "vid": vid, "url": u})
                    new_marks.append({"creator_id": cid, "vid": vid, "url": u,
                                      "title": it.get("title") or ""})
                # 记下这次真正送队列的，下次就不会再重复提取
                if new_marks:
                    creator_watch.mark_extracted(new_marks)
                if done_keys:
                    creator_watch.remove_findings(done_keys)
                # 组织一句给界面看的提示
                parts = []
                if queued:
                    parts.append("已把 %d 个视频加入提取队列" % queued)
                if x_saved:
                    parts.append("已把 %d 条推文存成笔记（还没做 AI 分析，需要时在笔记上点「🤖 AI 分析」）" % x_saved)
                if skipped:
                    parts.append("%d 个之前提取过，已跳过" % skipped)
                msg = "；".join(parts) if parts else "没有可提取的内容"
                return self._send({"ok": True, "queued": queued, "skipped": skipped,
                                   "x_saved": x_saved, "message": msg})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/unextract":
            # 把若干视频移出「已提取」记录，使其可以重新提取。
            # body: {items:[{creator_id,vid,url}]} 或 {items:[url,...]}；items 省略=清空整表
            try:
                import creator_watch
                return self._send(creator_watch.unmark_extracted(body.get("items")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/dismiss":
            try:
                import creator_watch
                return self._send(creator_watch.remove_findings(body.get("items") or []))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/clear":
            try:
                import creator_watch
                return self._send(creator_watch.clear_findings())
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/config":
            try:
                import creator_watch
                return self._send({"ok": True, "config": creator_watch.save_config(body)})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/creator/gather":
            # 新版块：把所有关注博主近 N 天的视频汇总到一起，给「这几天大家发了啥」总览用。
            # body: {days:7, refresh:false}
            try:
                import creator_watch
                days = body.get("days", 7)
                refresh = bool(body.get("refresh", False))
                backfill = bool(body.get("backfill", False))
                per_timeout = body.get("per_timeout", 30)
                data = creator_watch.gather_recent(
                    days=days, refresh=refresh,
                    backfill=backfill, per_timeout=per_timeout)
                return self._send(data)
            except Exception as e:
                return self._send({"ok": False, "message": str(e), "items": []}, 200)

        if path == "/proxy/test":
            try:
                import web_tools as W
                p = W._read_proxy()
                if not p:
                    return self._send({"ok": False, "message": "还没填代理地址，先填上再测。"})
                try:
                    page = W._fetch("https://huggingface.co/", timeout=15, use_proxy=True)
                    n = len((page or "").strip())
                    if n > 0:
                        return self._send({"ok": True,
                                           "message": f"代理可用 ✓ 经 {p} 读到 {n} 字（境外站点能访问了）"})
                    return self._send({"ok": False, "message": "连上了但没读到内容，换个端口或工具试试。"})
                except Exception as fe:
                    msg = str(fe)
                    try:
                        import sniffer
                        msg = sniffer._humanize_err(fe)
                    except Exception:
                        pass
                    return self._send({"ok": False, "message": f"测试失败：{msg}"})
            except Exception as e:
                return self._send({"ok": False, "message": str(e)}, 200)

        if path == "/memory":
            name = body.get("name", "")
            content = body.get("content", "")
            result = core.write_memory_file(name, content)
            ok = not result.startswith("拒绝")
            return self._send({"ok": ok, "message": result})

        if path == "/conversations/save":
            # 知识云图：把前端某个会话落盘成存档（聊过的就进云图）。
            # body: {id, title, messages:[{role,content}], starred?}
            try:
                import conversation_memory as cm
                return self._send(cm.save_session(
                    body.get("id"), body.get("title"),
                    body.get("messages") or [], body.get("starred")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)})
        if path == "/conversations/delete":
            try:
                import conversation_memory as cm
                return self._send(cm.delete_conversation(body.get("id", "")))
            except Exception as e:
                return self._send({"ok": False, "message": str(e)})

        self._send({"error": "not found"}, 404)

    def _read_raw_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return ""
        return self.rfile.read(length).decode("utf-8")

    # 渠道设置：用最近一次界面设置的模型；默认本地
    _channel_cfg = {"use_local": True, "model": "qwen2.5"}

    def _handle_wecom_post(self, qs):
        try:
            import wecom_bot
            cfg = wecom_bot.load_config()
            raw = self._read_raw_body()
            c = Handler._channel_cfg
            xml = wecom_bot.handle_callback_post(
                cfg, qs, raw, c["use_local"], c["model"])
            return self._send_text(xml or "")
        except Exception:
            return self._send_text("")

    def _handle_feishu_post(self):
        try:
            import feishu_bot
            cfg = feishu_bot.load_config()
            raw = self._read_raw_body()
            c = Handler._channel_cfg
            result = feishu_bot.handle_event(
                cfg, raw, c["use_local"], c["model"])
            return self._send(result)
        except Exception:
            return self._send({})

    def _handle_push_test(self, body):
        try:
            import push_serverchan
            ok, msg = push_serverchan.push(
                "超能小助测试", "这是一条来自超能小助的测试推送。")
            return self._send({"ok": ok, "message": msg})
        except Exception as e:
            return self._send({"ok": False, "message": str(e)})

    def _handle_sniff_report(self, body):
        """像情报简报一样，让网页模型逐个站点搜+读+总结，生成一份嗅探简报。
        默认走网页模型；网页模型不可用则回退到调用方给的 fallback 模型。"""
        use_local = body.get("use_local", False)
        model = body.get("model", "web")
        chat_id = body.get("chat_id") or ""

        if (not use_local) and model == "web":
            web_ok = True
            try:
                import web_model
                web_ok = web_model.is_available()
            except Exception:
                web_ok = False
            if not web_ok:
                use_local = body.get("fallback_use_local", True)
                model = body.get("fallback_model", "qwen2.5")
                if cp is not None and chat_id:
                    try:
                        cp.push(chat_id, "网页模型不可用，改用当前所选模型生成…")
                    except Exception:
                        pass

        on_step = on_detail = None
        if cp is not None and chat_id:
            cp.start(chat_id)
            on_step = lambda m: cp.push(chat_id, m)
            on_detail = lambda m: cp.set_pct(chat_id, None, m)
        try:
            import sniffer
            report = sniffer.generate_sniff_report(
                use_local=use_local, model=model, verbose=False,
                on_step=on_step, on_detail=on_detail)
            if cp is not None and chat_id:
                cp.finish(chat_id)
            return self._send({"ok": True, "brief": report,
                               "used_model": model, "used_use_local": use_local})
        except Exception as e:
            if cp is not None and chat_id:
                try: cp.finish(chat_id)
                except Exception: pass
            return self._send({"ok": False, "brief": f"出错：{e}",
                               "used_model": model, "used_use_local": use_local})

    def _handle_briefing(self, body):
        """生成一次情报简报（搜+读+提炼+推送）。
        默认走网页模型；若网页模型不可用，则回退到调用方给的 fallback 模型。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        chat_id = body.get("chat_id") or ""

        # 前端默认请求 web 模型；这里做个安全网：web 不可用就回退，避免硬失败。
        if (not use_local) and model == "web":
            web_ok = True
            try:
                import web_model
                web_ok = web_model.is_available()
            except Exception:
                web_ok = False
            if not web_ok:
                use_local = body.get("fallback_use_local", True)
                model = body.get("fallback_model", "qwen2.5")
                if cp is not None and chat_id:
                    try:
                        cp.push(chat_id, "网页模型不可用，改用当前所选模型生成…")
                    except Exception:
                        pass

        on_step = on_detail = None
        if cp is not None and chat_id:
            cp.start(chat_id)
            on_step = lambda m: cp.push(chat_id, m)            # 关键词级里程碑 → 新增一步
            on_detail = lambda m: cp.set_pct(chat_id, None, m)  # 网页模型实时活动 → 当前步明细
        try:
            import briefing
            brief = briefing.generate_briefing(
                use_local=use_local, model=model, verbose=False,
                on_step=on_step, on_detail=on_detail)
            if cp is not None and chat_id:
                cp.finish(chat_id)
            # 把这次「实际用的模型」回给前端，让聊天框 + 右上角同步显示，避免误导
            return self._send({"ok": True, "brief": brief,
                               "used_model": model, "used_use_local": use_local})
        except Exception as e:
            if cp is not None and chat_id:
                try: cp.finish(chat_id)
                except Exception: pass
            return self._send({"ok": False, "brief": f"出错：{e}",
                               "used_model": model, "used_use_local": use_local})

    def _handle_competitors(self, body):
        """检查竞品页面变化。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        try:
            import competitor_watch
            alerts, logs = competitor_watch.run_check(
                use_local=use_local, model=model, verbose=False)
            return self._send({"ok": True, "alerts": alerts, "logs": logs})
        except Exception as e:
            return self._send({"ok": False, "logs": f"出错：{e}"})

    def _handle_daily_task(self, body):
        """为学生生成今日英语任务。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        student = body.get("student", "default")
        try:
            import tutor
            task = tutor.generate_daily_task(
                student=student, use_local=use_local, model=model)
            return self._send({"ok": True, "task": task})
        except Exception as e:
            return self._send({"ok": False, "task": f"出错：{e}"})

    # ────────────────── 「懂你」四件套（lumi_features）──────────────────
    def _handle_lumi_evolve(self, body):
        """人格演化：后台跑（读对话→蒸馏→总结→写画像），立即返回，前端轮询进度。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        try:
            import lumi_features
            return self._send(lumi_features.start_evolve(
                use_local=use_local, model=model))
        except Exception as e:
            return self._send({"ok": False, "message": f"演化出错：{e}"}, 200)

    def _handle_lumi_scan(self, body):
        """系统扫描 / 职业检测 → 写 ENVIRONMENT.md。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        try:
            import lumi_features
            return self._send(lumi_features.scan_environment(
                use_local=use_local, model=model, write=True))
        except Exception as e:
            return self._send({"ok": False, "message": f"扫描出错：{e}"}, 200)

    def _handle_lumi_greeting(self, body):
        """生成一句个性化问候（结合时间+画像+记忆）。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        try:
            import lumi_features
            return self._send(lumi_features.make_greeting(
                use_local=use_local, model=model))
        except Exception as e:
            return self._send({"ok": False, "greeting": "", "error": str(e)}, 200)


    # ────────────────── 会话智能起标题 ──────────────────
    def _handle_video_mindmap(self, body):
        """根据一篇详细笔记(analysis) 生成思维导图结构(JSON 树)，交给前端渲染。
        入参: { analysis: str, title?: str, use_local?: bool, model?: str }
        出参: { ok: True, root: {data:{text,note,color}, children:[...]} }
              失败 { ok: False, error: str }"""
        analysis = (body.get("analysis") or "").strip()
        title = (body.get("title") or "").strip()
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        if not analysis:
            return self._send({"ok": False, "error": "没有可用于生成思维导图的内容"})
        try:
            root = _cx_mindmap_from_text(analysis, title, use_local, model)
            return self._send({"ok": True, "root": root})
        except Exception as e:
            return self._send({"ok": False, "error": str(e)}, 200)

    def _handle_summarize_title(self, body):
        """根据会话前几条消息，用模型总结一个简短中文标题（4-12字）。
        失败时返回 ok:False，前端用兜底逻辑。"""
        import re
        msgs = body.get("messages", []) or []
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")

        # 取前几条真正的对话内容（跳过 system），拼成一小段语料，控制长度
        convo = []
        for m in msgs:
            role = m.get("role")
            if role not in ("user", "assistant"):
                continue
            c = (m.get("content") or "").strip()
            if not c:
                continue
            who = "用户" if role == "user" else "助手"
            convo.append(f"{who}：{c[:400]}")
            if len(convo) >= 4:
                break
        corpus = "\n".join(convo)[:1500]
        if not corpus:
            return self._send({"ok": False, "error": "没有可用于总结的内容"})

        prompt = (
            "请根据下面这段对话，起一个简短的中文标题，用来在会话列表里显示。\n"
            "要求：4到12个字，准确概括主题；只输出标题本身，不要引号、"
            "不要标点符号、不要任何解释。\n\n"
            "对话内容：\n" + corpus + "\n\n标题：")

        try:
            # 起标题是轻量纯文本任务：本地模型直接用；其它情况退回 make_client
            real_model = model
            if core.is_web_model(model):
                # 伪模型(网页大模型)较慢/不稳定，标题改用本地小模型更快
                client = core.make_client(True)
                real_model = "qwen2.5"
            else:
                client = core.make_client(use_local)
            resp = client.chat.completions.create(
                model=real_model,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            return self._send({"ok": False, "error": str(e)})

        title = self._clean_title(raw)
        if not title:
            return self._send({"ok": False, "error": "模型没给出有效标题"})
        return self._send({"ok": True, "title": title})

    @staticmethod
    def _clean_title(raw):
        """把模型输出清洗成干净的短标题。"""
        import re
        t = (raw or "").strip()
        # 只取第一行
        t = t.splitlines()[0] if t else ""
        # 去掉常见前缀（标题：/ Title: 等）
        t = re.sub(r"^(标题|题目|title)\s*[:：]\s*", "", t, flags=re.I)
        # 去掉首尾引号和多余标点
        t = t.strip().strip('“”\"\'《》「」').strip()
        # 去掉结尾的句号等标点
        t = re.sub(r"[。.!！?？,，、;；\s]+$", "", t)
        return t[:24]

    def _handle_system_access(self, body):
        """读/写「电脑操作权限」总开关。前端设置页的开关走这里。"""
        try:
            import system_tools
            if "enabled" in (body or {}):
                want = bool(body.get("enabled"))
                system_tools.set_enabled(want)
                # ★开启时在后台线程预热那些较重的依赖（pyautogui / mss / pytesseract 等），
                #  避免第一次真正用到时在对话中途卡几秒。预热失败无所谓，用到时再说。
                if want:
                    def _warm():
                        try:
                            import importlib
                            for _m in ("psutil", "mss", "PIL", "pyautogui"):
                                try:
                                    importlib.import_module(_m)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    _threading.Thread(target=_warm, daemon=True).start()
            return self._send({"ok": True, "enabled": system_tools.is_enabled()})
        except Exception as e:
            return self._send({"ok": False, "error": str(e)}, 200)

    @staticmethod
    def _strip_md_for_tts(text):
        """朗读前把 Markdown 记号、链接、表情等清掉，让语音更自然。"""
        import re
        t = text or ""
        t = re.sub(r"```[\s\S]*?```", "，", t)          # 代码块整段略读
        t = re.sub(r"`([^`]*)`", r"\1", t)
        t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)        # 图片
        t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)    # 链接保留文字
        t = re.sub(r"https?://\S+", "", t)
        t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
        t = re.sub(r"[*_>~#|]", "", t)
        t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
        t = re.sub(r"\n{2,}", "\n", t)
        return t.strip()

    def _handle_tts(self, body):
        """语音播报：用 edge-tts（微软神经网络音色，免费）把文本合成 MP3 返回。"""
        text = self._strip_md_for_tts((body or {}).get("text", ""))
        voice = (body or {}).get("voice") or "zh-CN-YunxiNeural"
        rate = (body or {}).get("rate") or "+0%"
        if not text:
            return self._send({"error": "空文本"}, 200)
        text = text[:5000]   # 太长截断，避免超时
        try:
            import edge_tts
            import asyncio

            # 国内直连微软 TTS 端点常常很慢（10秒+）。若配了代理（设置→联网与代理），
            # 让 edge-tts 也走代理，通常能从十几秒降到一两秒。没配就直连。
            try:
                import web_tools as W
                _proxy = W._read_proxy()
            except Exception:
                _proxy = ""

            async def _synth(use_proxy):
                buf = bytearray()
                kw = {"rate": rate}
                if use_proxy and _proxy:
                    kw["proxy"] = _proxy
                communicate = edge_tts.Communicate(text, voice, **kw)
                async for chunk in communicate.stream():
                    if chunk.get("type") == "audio":
                        buf += chunk["data"]
                return bytes(buf)

            if _proxy:
                try:
                    audio = asyncio.run(_synth(True))      # 先走代理（快）
                except Exception:
                    audio = asyncio.run(_synth(False))     # 代理不行再直连兜底
            else:
                audio = asyncio.run(_synth(False))
            if not audio:
                return self._send({"error": "合成为空"}, 200)
            return self._send_bytes(audio, "audio/mpeg")
        except ModuleNotFoundError:
            # 依赖没装好：让前端回退到浏览器内置语音
            return self._send({"error": "edge-tts 未安装，已回退浏览器语音",
                               "fallback": True}, 200)
        except Exception as e:
            return self._send({"error": str(e), "fallback": True}, 200)

    def _handle_chat(self, body):
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        shell_enabled = body.get("shell_enabled", False)
        messages = body.get("messages", [])
        # 让微信/飞书渠道也用同一套模型设置
        Handler._channel_cfg = {"use_local": use_local, "model": model}

        # 每次都用最新的记忆文件重建系统提示；带上用户最近说的话，按相关性取舍专项设定
        _req = "\n".join(
            (m.get("content") if isinstance(m.get("content"), str) else "")
            for m in messages[-6:] if m.get("role") == "user")
        sys_prompt = core.build_system_prompt(request=_req)
        # ── 分身：若本次带了 agent_slug，把这个分身的「判断标准/风格样本」拼到系统提示之后 ──
        #    （只增不改：原 prompt 带着软件的记忆/人格，分身片段追加在末尾，让它带着用户的判断做事）
        #    特殊 slug "__interview__" 走的是"访谈引导"提示——让模型采访用户、最后吐出分身草稿。
        _agent_slug = (body.get("agent_slug") or "").strip()
        if _agent_slug:
            try:
                import agents_store
                _frag = agents_store.build_agent_system_prompt(_agent_slug)
                if _frag:
                    sys_prompt = sys_prompt + "\n\n" + _frag
                # 真·分身（非访谈）每派一次活计一次数；失败静默，不影响对话
                if _agent_slug != agents_store.INTERVIEW_SLUG:
                    agents_store.bump_usage(_agent_slug)
            except Exception:
                pass
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = sys_prompt
        else:
            messages.insert(0, {"role": "system", "content": sys_prompt})

        tool_calls = []

        # ---- 实时进度：每一步都播报给前端（前端轮询 /chat_progress 显示）----
        chat_id = body.get("chat_id") or ""
        if cp is not None and chat_id:
            cp.start(chat_id)
            cp.bind_thread(chat_id)
            cp.bind_settings(use_local, model)

        # 工具名 -> 友好中文，进度里显示得让人看得懂（保持克制，不加花哨图标）
        _TOOL_LABEL = {
            "video_transcript": "提取视频文字",
            "web_search": "联网搜索",
            "search_web": "联网搜索",
            "read_webpage": "读取网页",
            "research": "深度调研",
            "calc": "计算",
            "get_time": "查询时间",
            "read_memory": "读取记忆",
            "list_memory": "翻看记忆",
            "write_memory": "写入记忆",
            "append_note": "记笔记",
            "add_reminder": "设置提醒",
            "list_reminders": "查看提醒",
            "read_file": "读取文件",
            "write_file": "写入文件",
            "list_files": "浏览文件",
            "search_files": "搜索文件",
            "list_textbooks": "翻看教材",
            "read_textbook": "读取教材",
            "get_student": "查学生档案",
            "update_student": "更新学生档案",
            "shell": "执行命令",
        }
        _state = {"used_tool": False}

        def on_think():
            if cp is None or not chat_id:
                return
            cp.push(chat_id,
                    "正在整理回复…" if _state["used_tool"] else "正在思考…")

        def on_tool_start(name, args):
            _state["used_tool"] = True
            if cp is None or not chat_id:
                return
            label = _TOOL_LABEL.get(name, name)
            extra = ""
            # 给几个常见工具补一句"在搜什么/读哪个链接"，更具体
            if name in ("web_search", "search_web", "research"):
                q = (args.get("query") or "")[:30]
                if q:
                    extra = "：" + q
            elif name in ("read_webpage", "video_transcript"):
                u = (args.get("url") or "")[:40]
                if u:
                    extra = "：" + u
            cp.push(chat_id, label + extra + "…")

        def on_tool(name, args, result):
            tool_calls.append({"name": name, "args": args,
                               "result": str(result)[:1000]})

        approvals = body.get("approvals", {})  # {tool_call_id: true/false}
        auto_approve_tools = body.get("auto_approve_tools", [])  # 本次对话已授权的工具类别

        # ════════ 网页模型 Agent：电脑操作权限开启时，让网页模型也能进工具循环 ════════
        # 复用右上角「电脑操作权限」总开关：开 → 网页模型当 agent 大脑（能操作电脑）；
        # 关 → 网页模型保持纯文本直出（老行为，快）。
        try:
            import system_tools as _systools
            web_agent_enabled = _systools.is_enabled()
        except Exception:
            web_agent_enabled = False

        def _web_prog(msg):
            if cp is not None and chat_id:
                cp.push(chat_id, msg)

        def _run_web_agent():
            """网页模型走工具循环（电脑操作权限开启时）。返回 (reply, messages, pending)。
            消息/pending 形态与本地·Claude 模型完全一致，前端的确认框/续跑无需改动。"""
            client = core.make_client_for("web", use_local=False, on_progress=_web_prog)
            return core.run_agent(
                client, "web", messages,
                shell_enabled=shell_enabled, on_tool=on_tool,
                approvals=approvals, on_think=on_think,
                on_tool_start=on_tool_start,
                auto_approve_tools=auto_approve_tools)

        # ════════ 显式选择 Claude 模型：直接用 Claude 跑工具循环（绕过智能路由）════════
        # 支持 "claude"（旧，取第一个配置）和 "claude::N"（新，取第 N 个配置）。
        if (not use_local) and (model == "claude" or model.startswith("claude::")):
            try:
                import claude_client
                # 解析配置索引
                _claude_idx = None
                if model.startswith("claude::"):
                    try:
                        _claude_idx = int(model.split("::")[1])
                    except (ValueError, IndexError):
                        _claude_idx = 0
                if not claude_client.is_configured():
                    return self._send({"reply": "还没配置 Claude API Key。请到「设置 → "
                                       "Claude 模型管理」添加配置。",
                                       "tool_calls": [], "messages": messages})
                client = claude_client.make(profile_index=_claude_idx)
                reply, messages, pending = core.run_agent(
                    client, model, messages,
                    shell_enabled=shell_enabled, on_tool=on_tool,
                    approvals=approvals, on_think=on_think,
                    on_tool_start=on_tool_start,
                    auto_approve_tools=auto_approve_tools)
                if pending is not None:
                    return self._send({"pending": pending, "tool_calls": tool_calls,
                                       "messages": messages})
                return self._send({"reply": reply, "tool_calls": tool_calls,
                                   "messages": messages})
            except Exception as e:
                return self._send({"reply": f"Claude 调用出错：{e}",
                                   "tool_calls": tool_calls, "error": str(e)}, 200)
            finally:
                if cp is not None and chat_id:
                    cp.finish(chat_id)

        # ════════ 常规模式：关掉智能路由 → 选哪个模型就用哪个，不自动切换 ════════
        smart_routing = body.get("smart_routing", True)
        if not smart_routing:
            try:
                if (not use_local) and core.is_web_model(model):
                    # 网页模型：电脑操作权限开 → 进工具循环当 agent；否则纯文本直出（老行为）。
                    if web_agent_enabled:
                        try:
                            reply, messages, pending = _run_web_agent()
                            if pending is not None:
                                return self._send({"pending": pending,
                                                   "tool_calls": tool_calls,
                                                   "messages": messages})
                            return self._send({"reply": reply, "tool_calls": tool_calls,
                                               "messages": messages})
                        except Exception as web_err:
                            return self._send({"reply": "网页模型不可用：%s" % web_err,
                                               "tool_calls": tool_calls,
                                               "error": str(web_err)}, 200)
                    def _wp(msg):
                        if cp is not None and chat_id:
                            cp.push(chat_id, msg)
                    try:
                        client = core.make_client_for("web", use_local=False, on_progress=_wp)
                        resp = client.chat.completions.create(model="web", messages=messages)
                        reply = resp.choices[0].message.content
                        messages = messages + [{"role": "assistant", "content": reply}]
                        return self._send({"reply": reply, "tool_calls": tool_calls,
                                           "messages": messages})
                    except Exception as web_err:
                        return self._send({"reply": "网页模型不可用：%s" % web_err,
                                           "tool_calls": tool_calls, "error": str(web_err)}, 200)
                else:
                    # 本地 / 云端模型：直接用它跑工具循环
                    client = core.make_client(use_local)
                    reply, messages, pending = core.run_agent(
                        client, model, messages,
                        shell_enabled=shell_enabled, on_tool=on_tool,
                        approvals=approvals, on_think=on_think,
                        on_tool_start=on_tool_start,
                        auto_approve_tools=auto_approve_tools)
                    if pending is not None:
                        return self._send({"pending": pending, "tool_calls": tool_calls,
                                           "messages": messages})
                    return self._send({"reply": reply, "tool_calls": tool_calls,
                                       "messages": messages})
            except Exception as e:
                return self._send({"reply": f"出错了：{e}", "tool_calls": tool_calls,
                                   "error": str(e)}, 200)
            finally:
                if cp is not None and chat_id:
                    cp.finish(chat_id)

        # ════════ 智能路由（§2/§3）════════
        import router
        task = router.classify_messages(messages, enable_quick_chat=True)
        # 该任务该用哪个模型（用户在设置里配的优先；否则用前端当前选择兜底）
        r_use_local, r_model = core.resolve_model(
            task, fallback_use_local=use_local, fallback_model=model)
        if cp is not None and chat_id:
            cp.push(chat_id, "判断任务类型：%s …" % task)

        def _web_progress(msg):
            if cp is not None and chat_id:
                cp.push(chat_id, msg)

        def _run_local(_model, _use_local):
            """本地/云端/Claude 工具循环（T1/T2 或回退用）。"""
            if _model == "claude" or str(_model).startswith("claude::"):
                client = core.make_client_for(_model, _use_local)
            else:
                client = core.make_client(_use_local)
            return core.run_agent(
                client, _model, messages,
                shell_enabled=shell_enabled, on_tool=on_tool,
                approvals=approvals,
                on_think=on_think, on_tool_start=on_tool_start,
                auto_approve_tools=auto_approve_tools)

        try:
            if task in (router.T_CHAT, router.T_QUICK) and core.is_web_model(r_model):
                # T3/T4 走伪模型：电脑操作权限开 → 进工具循环当 agent；否则纯文本直出（老行为）。
                try:
                    if web_agent_enabled:
                        reply, messages, pending = _run_web_agent()
                        if pending is not None:
                            self._send({"pending": pending, "tool_calls": tool_calls,
                                        "messages": messages})
                        else:
                            self._send({"reply": reply, "tool_calls": tool_calls,
                                        "messages": messages})
                            # 「懂你」不依赖伪模型：回答后本地轻量记忆后处理（§6，尽力而为）
                            self._maybe_remember_after(messages)
                    else:
                        client = core.make_client_for(
                            "web", use_local=False, on_progress=_web_progress)
                        resp = client.chat.completions.create(model="web", messages=messages)
                        reply = resp.choices[0].message.content
                        messages = messages + [{"role": "assistant", "content": reply}]
                        self._send({"reply": reply, "tool_calls": tool_calls,
                                    "messages": messages})
                        # 「懂你」不依赖伪模型：回答后本地轻量记忆后处理（§6，尽力而为）
                        self._maybe_remember_after(messages)
                except Exception as web_err:
                    # ★铁律：伪模型任何一步失败 → 优雅回退本地，主流程不中断
                    if cp is not None and chat_id:
                        cp.push(chat_id, "网页模型不可用，回退本地…")
                    reply, messages, pending = _run_local(model, use_local)
                    if pending is not None:
                        self._send({"pending": pending, "tool_calls": tool_calls,
                                    "messages": messages})
                    else:
                        self._send({"reply": reply, "tool_calls": tool_calls,
                                    "messages": messages,
                                    "fallback": "web→local", "web_error": str(web_err)})
            else:
                # T1 本机动作 / T2 视频 / 或该任务被配成本地·云端模型：走工具循环。
                # ★工具循环需要"能调用工具"的模型；网页模型够不到工具、没钥匙的云端模型会报
                #   Missing credentials —— 这两种情况都改用本地模型来跑工具循环
                #   （视频的"总结"那步在工具内部仍会用网页模型）。
                loop_use_local, loop_model = r_use_local, r_model
                need_local = core.is_web_model(loop_model) or (
                    (not loop_use_local)
                    and not os.environ.get("OPENAI_API_KEY")
                    and not os.environ.get("OPENAI_ADMIN_KEY"))
                if need_local:
                    if use_local and not core.is_web_model(model):
                        loop_use_local, loop_model = True, model
                    else:
                        loop_use_local, loop_model = True, "qwen2.5"
                reply, messages, pending = _run_local(loop_model, loop_use_local)
                if pending is not None:
                    self._send({"pending": pending, "tool_calls": tool_calls,
                                "messages": messages})
                else:
                    self._send({"reply": reply, "tool_calls": tool_calls,
                                "messages": messages})
        except Exception as e:
            self._send({"reply": f"出错了：{e}", "tool_calls": [],
                        "error": str(e)}, 200)
        finally:
            if cp is not None and chat_id:
                cp.finish(chat_id)

    def _maybe_remember_after(self, messages):
        """回答后用本地小模型轻量判断有没有值得长期记的（§6）。失败静默。"""
        try:
            import threading

            def _bg():
                try:
                    # 取最后一轮用户+助手内容，问本地模型要不要记
                    last_user = ""
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            last_user = m.get("content", "")
                            break
                    if not last_user or len(str(last_user)) < 6:
                        return
                    client = core.make_client(True)
                    q = ("下面是用户说的话。如果其中包含值得长期记住的、关于用户本人的"
                         "持久信息（偏好/习惯/正在做的项目/重要决定），用一句话概括要记什么；"
                         "如果没有，只回复\"无\"。\n\n用户：" + str(last_user))
                    resp = client.chat.completions.create(
                        model="qwen2.5",
                        messages=[{"role": "user", "content": q}])
                    out = (resp.choices[0].message.content or "").strip()
                    if out and out != "无" and "无" != out[:1]:
                        core.remember(out)
                    # 顺手抽取「关系网络」：这段对话提到的人记一笔（尽力而为，失败静默）
                    try:
                        import lumi_features
                        lumi_features.extract_relationships(
                            messages=messages, use_local=True, model="qwen2.5")
                    except Exception:
                        pass
                except Exception:
                    pass
            threading.Thread(target=_bg, daemon=True).start()
        except Exception:
            pass

    def _handle_web_model_test(self, body):
        """「测试网页模型」：弹浏览器→登录→存登录态→跑一句测试。"""
        try:
            import web_model
            if not web_model.is_available():
                return self._send({"ok": False,
                                   "error": "Playwright 未安装：pip install playwright "
                                            "&& python -m playwright install chromium"}, 200)
            chat_id = body.get("chat_id") or ""

            def _prog(msg):
                if cp is not None and chat_id:
                    cp.push(chat_id, msg)
            res = web_model.test_login(on_progress=_prog)
            return self._send(res)
        except Exception as e:
            return self._send({"ok": False, "error": str(e)}, 200)

    def _handle_heartbeat(self, body):
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        try:
            from heartbeat import run_one_beat
            reply = run_one_beat(use_local=use_local, model=model,
                                 verbose=False)
            self._send({"reply": reply})
        except Exception as e:
            self._send({"reply": f"心跳出错：{e}", "error": str(e)}, 200)

    def _handle_skill_from_conversation(self, body):
        """读这段对话，提炼出一个可复用的技能草稿（不保存，返回给界面让用户确认编辑）。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        messages = body.get("messages", [])
        try:
            import skills_store
            # 提炼属于本机动作：优先用本地模型，快、私密、稳；
            # 当前若用的是网页/云端模型，这一步也退回本地，避免缺凭据。
            ex_model = model if use_local else "qwen2.5"
            client = core.make_client(True)
            draft = skills_store.extract_skill_from_conversation(client, ex_model, messages)
            if not draft:
                return self._send({"ok": True, "skill": None,
                                   "message": "这段对话没提炼出可复用的技能（可能只是闲聊或一次性问答）。"})
            return self._send({"ok": True, "skill": draft})
        except Exception as e:
            return self._send({"ok": False, "message": str(e)}, 200)

    def _handle_remember(self, body):
        """存档当前对话并更新长期记忆。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        messages = body.get("messages", [])
        try:
            import conversation_memory as cm
            fname = cm.save_conversation(messages)
            # 「长期记忆」的提炼属于本机动作（T1），用本地模型：快、私密、稳。
            # 即使当前对话用的是网页/云端模型，这一步也走本地，避免 Missing credentials。
            mem_model = model if use_local else "qwen2.5"
            client = core.make_client(True)
            summary = cm.update_long_term_memory(client, mem_model, messages)
            self._send({"ok": True, "archived": fname,
                        "summary": summary or "（这段没什么需要长期记的）"})
        except Exception as e:
            self._send({"ok": False, "error": str(e)}, 200)

    def _handle_telegram_start(self, body):
        """在后台线程启动 Telegram bot。"""
        global _tg_started
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        if _tg_started:
            return self._send({"ok": True, "message": "Telegram 已在运行。"})
        try:
            import threading
            from telegram_bot import run_bot, _load_config
            token, allowed = _load_config()
            if not token or "粘贴" in token or "这里" in token:
                return self._send({"ok": False,
                    "message": "还没填好 token，请到记忆里编辑 telegram.md。"})
            if not allowed or "这里" in allowed:
                return self._send({"ok": False,
                    "message": "还没填 chat id，为安全起见不启动。"})
            t = threading.Thread(
                target=run_bot,
                kwargs={"use_local": use_local, "model": model},
                daemon=True)
            t.start()
            _tg_started = True
            self._send({"ok": True,
                        "message": f"Telegram 已启动，只服务 chat_id={allowed}。"})
        except Exception as e:
            self._send({"ok": False, "message": f"启动失败：{e}"})

    def _handle_heartbeat_start(self, body):
        """在软件内开启自动心跳（后台线程，跟着软件活）。"""
        if _hb_state["running"]:
            return self._send({"ok": True, "running": True,
                               "message": "心跳已经在运行了。"})
        try:
            interval = int(body.get("interval", 300))
        except (TypeError, ValueError):
            interval = 300
        if interval < 30:
            interval = 30  # 别太频繁，最少 30 秒
        _hb_state["interval"] = interval
        _hb_state["use_local"] = body.get("use_local", True)
        _hb_state["model"] = body.get("model", "qwen2.5")
        _hb_state["stop"] = _threading.Event()
        _hb_state["running"] = True
        t = _threading.Thread(target=_heartbeat_loop, daemon=True)
        _hb_state["thread"] = t
        t.start()
        mins = round(interval / 60, 1)
        return self._send({"ok": True, "running": True,
                           "interval": interval,
                           "message": f"自动心跳已开启，每 {mins} 分钟醒一次。"})

    def _handle_heartbeat_stop(self, _body):
        """关闭自动心跳。"""
        if not _hb_state["running"]:
            return self._send({"ok": True, "running": False,
                               "message": "心跳本来就没开。"})
        try:
            if _hb_state["stop"]:
                _hb_state["stop"].set()
        except Exception:
            pass
        _hb_state["running"] = False
        return self._send({"ok": True, "running": False,
                           "message": "自动心跳已关闭。"})

    # ---------- 视频内容提取 ----------
    def _video_dir(self):
        import agent_core
        d = agent_core.MEMORY_DIR / "video_notes"
        d.mkdir(exist_ok=True)
        return d

    def _video_progress_merged(self):
        """把「视频」板块队列状态 + 对话里触发的视频任务合并，统一给前端显示。"""
        import time as _t
        # 先把对话任务完成后挂起的结果取过来，挂到 _video_state 上让前端渲染
        try:
            res, bump = _cvq.take_result()
            if res is not None and bump:
                _video_state["result"] = res
                _video_state["result_id"] += bump
        except Exception:
            pass
        st = dict(_video_state)
        run_tasks, wait_tasks, all_tasks = _chat_video_snapshot()

        # 对话任务：正在跑的合进顶部「生成中」卡片；等待中的并进排队列表。
        # 若「视频」板块自己没有在跑，但有对话任务在跑，就用对话任务点亮顶部卡片。
        if not st.get("running") and run_tasks:
            t = run_tasks[0]
            st["running"] = True
            st["stage"] = t.get("stage") or "处理中"
            st["detail"] = t.get("detail") or ""
            st["current_label"] = t.get("label") or "对话里的视频"
            st["elapsed"] = int(_t.time() - t.get("start", _t.time()))
            extra_running = run_tasks[1:]
        else:
            extra_running = run_tasks if st.get("running") else []

        # 组装排队列表：原队列（已是 {url,title} 对象）+ 对话里等待/额外在跑的。
        # 对话任务统一也包成 {url, title} 形式，保证前端拿到的队列项格式一致。
        queue = list(st.get("queue") or [])
        for t in wait_tasks:
            queue.append({"url": "", "title": (t.get("label") or "对话里的视频") + "（对话）"})
        for t in extra_running:
            queue.append({"url": "", "title": (t.get("label") or "对话里的视频") + "（对话·处理中）"})
        st["queue"] = queue
        st["queue_len"] = len(queue)
        # 只要有任何对话任务在，就保持前端继续轮询
        if all_tasks:
            st["has_chat_tasks"] = True
        return st

    def _handle_video_install(self, _body):
        """自动安装视频提取所需的依赖（yt-dlp / faster-whisper）。"""
        try:
            import video_transcribe
            ok, out = video_transcribe.install_deps()
            st = video_transcribe.deps_status()
            li = st.get("last_install") or {}
            if ok:
                ch = li.get("changes") or []
                if ch:
                    msg = "✓ 更新成功：" + "；".join(
                        "%s %s → %s" % (c["name"], c.get("from") or "未安装", c.get("to") or "?") for c in ch)
                else:
                    msg = "✓ 检查完毕：所有依赖都已是最新版本，不需要更新。"
                if li.get("restart"):
                    msg += "\n（%s 要关掉软件再打开才生效）" % "、".join(li["restart"])
                _clog("视频", msg.replace("\n", " "))
            else:
                msg = ("安装没成功，多半是网络问题（清华、阿里镜像和默认源都试过了）。"
                       "可以稍后重试，或者把下面的日志发给我。")
            return self._send({"ok": ok, "message": msg, "log": out, "deps": st})
        except Exception as e:
            return self._send({"ok": False, "message": f"安装出错：{e}"})

    def _handle_video_detect_subtitle(self, body):
        """轻量检测：这个链接有没有平台字幕（不下载正文，秒级返回）。
        前端在用户点「提取并分析」后先调它：有字幕才提醒用户可选「只用字幕/字幕+听写」。"""
        url = (body or {}).get("url", "").strip()
        if not url:
            return self._send({"ok": False, "has": False, "error": "请先粘贴视频链接。"})
        try:
            import doc_import as _dimp
            if _dimp.article_url(url):
                return self._send({"ok": True, "has": False, "article": True})   # v65：文章链接没有字幕
        except Exception:
            pass
        try:
            import video_subtitle
            info = video_subtitle.detect_subtitle(url)
            return self._send({"ok": True, **info})
        except Exception as e:
            # 检测失败就当没字幕，前端照常按「自动」提交，不卡用户
            return self._send({"ok": True, "has": False, "error": str(e)})

    def _save_x_note(self, item, tweet_text, use_local, model, analyze=True):
        """把一条 X 推文直接存成笔记（文字内容，不走视频听写）。
        格式与视频笔记一致，能直接在「视频笔记 / 数据库」里看到。
        v89：analyze=False 时不调 AI，马上存好（状态「未分析」，需要时再点「🤖 AI 分析」）。"""
        import datetime as _dt
        url = (item.get("url") or "").strip()
        uploader = (item.get("uploader") or "").strip()
        raw_title = (item.get("title") or tweet_text[:40] or "X 推文").strip()
        if not analyze:
            ts = _dt.datetime.now()
            title_zh = (item.get("title_zh") or "").strip()
            display_title = (title_zh if title_zh and title_zh != raw_title else raw_title).replace("\n", " ")[:120]
            orig_line = f"- 原文标题：{raw_title}\n" if display_title != raw_title else ""
            safe = "".join(c for c in display_title[:20] if c.isalnum() or c in " 　-_") or "x_post"
            stem = (f"{ts.strftime('%Y%m%d-%H%M%S')}-{safe}").replace(" ", "_")
            d = _cx_video_dir()
            fname, k = stem + ".md", 2
            while (d / fname).exists():                  # 同一秒存好几条、标题开头又一样：别互相盖掉
                fname, k = "%s-%d.md" % (stem, k), k + 1
            placeholder = ("（这条只存了推文原文，还没做 AI 分析。需要的时候点「🤖 AI 分析」就行：笔记列表里这一条的右边、"
                           "或者打开笔记后的按钮都可以。）")
            doc = (f"# {display_title}\n\n"
                   f"- 来源链接：{url}\n"
                   f"- 作者：{uploader}\n"
                   f"- 平台：X（推特）\n"
                   f"- 提取时间：{ts.strftime('%Y-%m-%d %H:%M')}\n"
                   f"- 状态：未分析\n"
                   f"{orig_line}\n"
                   f"## 🤖 AI 分析\n\n{placeholder}\n\n"
                   f"---\n\n## 📝 完整文字稿\n\n{_x_parts_md(url, tweet_text, item.get('x'), uploader)}\n")
            (d / fname).write_text(doc, encoding="utf-8")
            _xsrc_save(fname, url, tweet_text, item.get("x"), uploader)
            return fname
        # 让模型把推文整理成中文笔记（推文可能是英文）。失败就退回原文。
        analysis = ""
        title_zh = ""
        try:
            analysis = _cx_analyze_transcript(
                tweet_text, raw_title, use_local, model)
            title_zh, analysis = _split_title_from_analysis(analysis)
        except Exception:
            analysis = tweet_text
        # 标签：让 AI 归纳几个（失败就空）
        try:
            tags = _cx_suggest_tag(raw_title, analysis or tweet_text, use_local, model)
        except Exception:
            tags = []
        tags = [(_t or "").strip().lstrip("#").strip() for _t in (tags or [])]
        tags = [t for t in tags if t][:6]
        tag_line = ("- 标签：" + "、".join(tags) + "\n") if tags else ""

        display_title = (title_zh or "").strip() or raw_title
        orig_line = (f"- 原文标题：{raw_title}\n"
                     if (title_zh and title_zh.strip() != raw_title) else "")
        ts = _dt.datetime.now()
        safe = "".join(c for c in display_title[:20]
                       if c.isalnum() or c in " 　-_") or "x_post"
        fname = (f"{ts.strftime('%Y%m%d-%H%M%S')}-{safe}.md").replace(" ", "_")
        doc = (f"# {display_title}\n\n"
               f"- 来源链接：{url}\n"
               f"- 作者：{uploader}\n"
               f"- 平台：X（推特）\n"
               f"- 提取时间：{ts.strftime('%Y-%m-%d %H:%M')}\n"
               f"{orig_line}"
               f"{tag_line}\n"
               f"## 🤖 AI 分析\n\n{analysis or '（无）'}\n\n"
               f"---\n\n## 📝 推文原文\n\n{tweet_text}\n")
        try:
            _cx_video_dir().joinpath(fname).write_text(doc, encoding="utf-8")
        except Exception:
            pass
        return fname

    def _handle_video_transcribe(self, body):
        """把视频任务加入队列，后台逐个处理。前端轮询 /video_progress。
        支持两种来源：① url=在线链接；② local_path=本地音/视频文件（新增）。"""
        url = body.get("url", "").strip()
        local_path = (body.get("local_path") or "").strip()
        # v112：加工——先认出放进来的是什么（见 intake.py）。电脑上的文件路径 → 按本地文件处理；
        #        GitHub 项目、没有链接的一段文字 → 下面走各自的流程；视频 / 文章链接照旧。
        _intake = ""
        if url and not local_path:
            try:
                import intake as _ik
                _intake = _ik.classify(url)
                if _intake in ("search", "paths", "chat"):     # v118/v120：这几种前端自己处理；万一直接发到这里，就当一段文字存
                    _intake = "text"
                if _intake == "file":
                    local_path, url = (_ik.local_path(url) or (_ik.paths_in(url) or [""])[0]), ""
            except Exception:
                _intake = ""
        level = body.get("level", "balanced")
        lang = (body.get("lang") or "zh").strip()          # v95：视频里说的是什么话（日语、英语…）
        vocal = bool(body.get("vocal"))                    # v102：识别前先分离人声
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        # 新增：插图 / 跳转原片开关（前端「视频」面板的两个勾选）
        do_screenshot = bool(body.get("screenshot", False))
        do_link = bool(body.get("link", False))
        # 新增：字幕模式 auto / subtitle_only / transcribe（默认 auto）
        mode = body.get("mode") or "auto"
        if mode not in ("auto", "subtitle_only", "transcribe"):
            mode = "auto"
        # 新增：提取后是否自动 AI 分析（默认 True = 和以前一样）。
        # False = 仅提取并保存文字稿，完全不调 AI；之后可在笔记列表补做分析。
        do_analyze = bool(body.get("analyze", False))     # v66：默认只提取原文，需要时再点「AI 分析」
        if not do_analyze:
            do_screenshot = False   # 不分析就没有截图标记，插图无从谈起（防御性关掉）
        # 新增：自定义作者名（本地文件没有作者信息，导入时可由用户统一填一个）
        author = (body.get("author") or "").strip()[:40]
        # 新增：自动归档文件夹（导入文件夹时可选）——提取完的笔记自动归进这个笔记文件夹
        note_folder = (body.get("note_folder") or "").strip()[:30]
        # v59：提取卡片里的「博主主页」（选填）。填了就按它建博主板块；不填就根据视频自动找
        creator_url = (body.get("creator_url") or "").strip()[:500]
        # v83：电脑上提交链接时记下这次的选项，手机发来的链接照同样的选项处理
        if url and not body.get("_from_phone"):
            try:
                import phone_inbox
                phone_inbox.remember_defaults(body)
            except Exception:
                pass

        try:
            import video_transcribe
        except Exception as e:
            return self._send({"ok": False, "error": f"模块加载失败：{e}"})

        # ── 分支一：本地文件 ──
        if local_path:
            import os as _os
            if not _os.path.exists(local_path):
                return self._send({"ok": False,
                                   "error": "找不到这个文件（可能被移动或删除了）。"})
            _is_doc = False
            try:
                import doc_import as _dimp
                _is_doc = _dimp.is_doc_path(local_path)
            except Exception:
                pass
            if not _is_doc:
                # 本地文件只需要 faster-whisper（不需要 yt-dlp）；v65：文档（PDF / Word…）什么都不用装
                missing = video_transcribe.check_deps_local()
                if missing:
                    return self._send({"need": missing})
            base = _os.path.basename(local_path)
            title = _os.path.splitext(base)[0] or "本地文件"
            # 入队：用 local_path 标记这是本地任务；url 放一个占位名只为显示/去重
            pos = _enqueue_video({
                "url": "local://" + local_path,   # 占位，仅用于去重/显示，不会真的去下载
                "local_path": local_path,
                "title": title,
                "level": level, "lang": lang, "vocal": vocal, "use_local": use_local, "model": model,
                "screenshot": do_screenshot, "link": do_link, "mode": mode,
                "analyze": do_analyze,
                "author": author, "note_folder": note_folder,
                "creator_url": creator_url,
            })
            return self._send({"queued": True, "position": pos})

        # ── 分支二：在线链接（原逻辑）──
        if not url:
            return self._send({"ok": False, "error": "请先粘贴视频或文章链接，或导入本地文件。"})

        # v112：GitHub 项目 / 一段文字：不用视频组件，直接排队，分别放进「GitHub 项目」「随手记」文件夹
        if _intake in ("github", "text"):
            import intake as _ik
            if _intake == "github":
                _o, _r = _ik.github_repo(url)
                _job = {"url": "https://github.com/%s/%s" % (_o, _r), "intake": "github",
                        "title": "%s/%s" % (_o, _r), "note_folder": note_folder or _ik.GH_FOLDER}
            else:
                import time as _tm
                _job = {"url": "text://%d" % int(_tm.time() * 1000), "intake": "text", "text": url[:200000],
                        "title": _ik.text_title(url), "note_folder": note_folder or _ik.TEXT_FOLDER}
            _job.update({"level": level, "lang": lang, "vocal": False, "use_local": use_local, "model": model,
                         "screenshot": False, "link": False, "mode": mode, "analyze": do_analyze,
                         "author": author, "creator_url": "", "notify": body.get("notify")})
            pos = _enqueue_video(_job)
            return self._send({"queued": True, "position": pos, "intake": _intake})

        # v65：不是视频网站的链接（文章、网页、PDF 链接…）：不用检查视频组件，直接排队；worker 先当文章读
        try:
            import doc_import as _dimp
            _art = _dimp.article_url(url)
        except Exception:
            _art = ""
        if _art:
            pos = _enqueue_video({"url": url, "level": level, "lang": lang, "vocal": vocal,
                                  "use_local": use_local, "model": model,
                                  "screenshot": False, "link": False,
                                  "mode": mode, "analyze": do_analyze,
                                  "author": author, "note_folder": note_folder,
                                  "creator_url": "", "notify": body.get("notify")})
            return self._send({"queued": True, "position": pos, "article": True})

        # ★境外视频（YouTube 等）预检：先看代理通不通、上不上得了外网。
        #   不通就早早给一句清楚的提示，而不是让用户干等三五十秒超时。
        #   国内平台（抖音/B站/快手…）不受影响，不会被拦。
        try:
            ok_reach, reach_msg = video_transcribe.check_foreign_reachable(url)
            if not ok_reach:
                return self._send({"ok": False, "error": reach_msg})
        except Exception:
            pass  # 预检本身出错就不拦，照常往下走

        missing = video_transcribe.check_deps()
        if missing:
            # 依赖没装齐，但如果这个链接能直接拿到平台字幕、且用户没强制要听写，
            # 那这次根本用不到下载+本地听写，放行入队即可（字幕优先）。
            # mode="transcribe" 是用户明确要听写覆盖 → 不绕过，照常提示装依赖。
            has_subtitle = False
            if mode != "transcribe":
                try:
                    import video_subtitle
                    _probe = video_subtitle.try_fetch_subtitle(url)
                    has_subtitle = bool(_probe and _probe.get("ok")
                                        and _probe.get("transcript"))
                except Exception:
                    has_subtitle = False
            if not has_subtitle:
                return self._send({"need": missing})

        pos = _enqueue_video({"url": url, "level": level, "lang": lang, "vocal": vocal,
                              "use_local": use_local, "model": model,
                              "screenshot": do_screenshot, "link": do_link,
                              "mode": mode, "analyze": do_analyze,
                              "author": author, "note_folder": note_folder,
                              "creator_url": creator_url, "notify": body.get("notify")})
        return self._send({"queued": True, "position": pos})

    def _handle_video_move_models(self, _body):
        """把 C 盘已下载的模型（语音模型 + Ollama 大模型）搬到 D 盘。"""
        try:
            import video_transcribe
            r = video_transcribe.move_cached_models()
            parts = []
            if r.get("moved"):
                parts.append("已搬运：" + "、".join(r["moved"]))
            else:
                parts.append("没在 C 盘找到可搬的模型（可能还没下过，或已经在 D 盘了）。")
            if r.get("notes"):
                parts.append("\n".join(r["notes"]))
            r["message"] = "\n".join(parts)
            return self._send(r)
        except Exception as e:
            return self._send({"ok": False, "message": f"搬运出错：{e}"})

    def _handle_video_shot(self, qs):
        """提供视频笔记的本地截图给前端显示。
        参数：n=笔记目录名（笔记 stem），f=图片文件名。两者都做防穿越校验。"""
        n = (qs.get("n", [""])[0] or "").strip()
        f = (qs.get("f", [""])[0] or "").strip()
        # 只允许干净的文件名/目录名，挡掉 / \ .. 等穿越
        bad = lambda s: (not s) or ("/" in s) or ("\\" in s) or (".." in s)
        if bad(n) or bad(f):
            return self._send({"error": "非法路径"}, 400)
        try:
            p = _cx_shots_dir() / n / f
            if not p.exists() or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                return self._send({"error": "找不到截图"}, 404)
            data = p.read_bytes()
            ctype = {".png": "image/png", ".webp": "image/webp",
                     ".gif": "image/gif"}.get(p.suffix.lower(), "image/jpeg")
            return self._send_bytes(data, ctype)
        except Exception as e:
            return self._send({"error": str(e)}, 200)

    def _handle_video_notes_list(self):
        try:
            d = self._video_dir()
            with _vn_lock:
                folders, mapping = _vn_load_folders()
            existing = set()
            items = []
            for p in sorted(d.glob("*.md"), reverse=True):
                existing.add(p.name)
                txt = p.read_text(encoding="utf-8", errors="replace")
                lines = txt.splitlines()
                title = lines[0].lstrip("# ").strip() if lines else p.stem
                # 解析「- 作者：xxx」。纯数字 ID（抖音没抓到昵称的兜底）不展示，
                # 只把有意义的昵称返给前端，避免列表上一堆看不懂的数字。
                author = ""
                for ln in lines[1:8]:
                    s = ln.strip().lstrip("-").strip()
                    hit = False
                    for key in ("作者：", "作者:"):
                        if s.startswith(key):
                            cand = s[len(key):].strip()
                            if cand and not cand.isdigit():
                                author = cand[:40]
                            hit = True
                            break
                    if hit:
                        break
                # 「仅提取」模式存的笔记带「- 状态：未分析」标记 → 前端据此
                # 显示「AI 分析」补做按钮
                analyzed = True
                for ln in lines[1:10]:
                    s = ln.strip().lstrip("-").strip()
                    if s.startswith("状态：未分析") or s.startswith("状态:未分析"):
                        analyzed = False
                        break
                if analyzed and any("（分析出错" in ln for ln in lines[:120]):
                    analyzed = False      # 以前 AI 失败时把报错存成了分析：当作未分析，可重新补
                # v56：提取时间（「最新提取」按它筛）：优先用文件名开头的时间，没有就用文件修改时间
                _ts = 0
                _m = re.match(r"(\d{8})-(\d{6})", p.name)
                if _m:
                    try:
                        import datetime as _dt_ts
                        _ts = _dt_ts.datetime.strptime(_m.group(1) + _m.group(2), "%Y%m%d%H%M%S").timestamp()
                    except Exception:
                        _ts = 0
                if not _ts:
                    try:
                        _ts = p.stat().st_mtime
                    except Exception:
                        _ts = 0
                kind = ""                                   # v65：导入的文档 / 文章
                for ln in lines[1:14]:
                    s = ln.strip().lstrip("-").strip()
                    if s.startswith(("类型：", "类型:")):
                        kind = s[3:].strip()[:20]
                        break
                items.append({"name": p.name, "title": title, "author": author, "ts": _ts, "kind": kind,
                              "analyzed": analyzed,
                              "folder": mapping.get(p.name, "")})
            # 顺手清理：分组表里指向已删除笔记的残留条目
            stale = [k for k in mapping if k not in existing]
            if stale:
                with _vn_lock:
                    _f2, _m2 = _vn_load_folders()
                    for k in stale:
                        _m2.pop(k, None)
                    _vn_save_folders(_f2, _m2)
            tidy = []
            try:
                tidy = _vn_tidy_same_name(items, folders)     # v64：头像墙上不出现重名的博主
            except Exception as _e:
                _clog("博主", "整理同名博主出错：%s" % _e)
            return self._send({"ok": True, "notes": items, "folders": folders, "tidy": tidy})
        except Exception as e:
            return self._send({"ok": False, "notes": [], "folders": [],
                               "error": str(e)})

    def _handle_video_folder(self, body):
        """视频笔记「文件夹」操作：create / rename / delete / move。
        文件夹是虚拟分组（存 video_notes/_folders.json），删除文件夹不会删笔记，
        里面的笔记只是回到未分组列表。"""
        op = (body.get("op") or "").strip()
        with _vn_lock:
            folders, mapping = _vn_load_folders()
            if op == "create":
                name = _vn_ok_folder_name(body.get("name"))
                if not name:
                    return self._send({"ok": False,
                                       "error": "文件夹名不能为空、太长（>30字）或含 / \\ .. 字符"})
                if name not in folders:
                    folders.append(name)
                    _vn_save_folders(folders, mapping)
                return self._send({"ok": True, "folders": folders})
            if op == "rename":
                old = (body.get("name") or "").strip()
                new = _vn_ok_folder_name(body.get("new_name"))
                if old not in folders:
                    return self._send({"ok": False, "error": "找不到这个文件夹"})
                if not new:
                    return self._send({"ok": False,
                                       "error": "新名字不能为空、太长（>30字）或含 / \\ .. 字符"})
                if new != old and new in folders:
                    return self._send({"ok": False, "error": "已有同名文件夹"})
                folders[folders.index(old)] = new
                for k, v in list(mapping.items()):
                    if v == old:
                        mapping[k] = new
                _vn_save_folders(folders, mapping)
                return self._send({"ok": True, "folders": folders})
            if op == "delete":
                name = (body.get("name") or "").strip()
                if name in folders:
                    folders.remove(name)
                    for k, v in list(mapping.items()):
                        if v == name:
                            mapping.pop(k, None)
                    _vn_save_folders(folders, mapping)
                return self._send({"ok": True, "folders": folders})
            if op == "move":
                note = (body.get("note") or "").strip()
                if not note or "/" in note or "\\" in note or ".." in note:
                    return self._send({"ok": False, "error": "非法文件名"})
                if not (self._video_dir() / note).exists():
                    return self._send({"ok": False, "error": "找不到这条笔记"})
                target = _vn_ok_folder_name(body.get("name"))
                prev = mapping.get(note, "")
                if target:
                    if target not in folders:
                        folders.append(target)
                    mapping[note] = target
                else:
                    mapping.pop(note, None)
                _vn_save_folders(folders, mapping)
                try:                                 # v64：从同名文件夹里移出来的，别再自动放回去
                    with _vn_merge_lock:
                        mg = _vn_load_merged()
                        ko = mg["keep_out"]
                        before = dict(ko)
                        if target:
                            ko.pop(note, None)
                        elif prev in folders:
                            na = _vn_norm(_vn_note_author(note))
                            if na and any(_vn_norm(f) == na for f in folders):
                                ko[note] = prev
                        if ko != before:
                            _vn_save_merged(mg)
                except Exception:
                    pass
                return self._send({"ok": True})
            return self._send({"ok": False, "error": "未知操作：" + op})

    def _handle_video_note_set_author(self, body):
        """填写 / 修改一条笔记的作者（本地导入的笔记通常没有作者）。
        直接改写 md 里的「- 作者：」行；没有这行就在开头元信息区补一行。"""
        name = (body.get("name") or "").strip()
        if not name or "/" in name or "\\" in name or ".." in name:
            return self._send({"ok": False, "error": "非法文件名"})
        p = self._video_dir() / name
        if not p.exists():
            return self._send({"ok": False, "error": "找不到这条笔记"})
        author = (body.get("author") or "").strip()[:40]
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
            done = False
            for i in range(1, min(12, len(lines))):
                s = lines[i].strip().lstrip("-").strip()
                if s.startswith("作者：") or s.startswith("作者:"):
                    lines[i] = "- 作者：" + author
                    done = True
                    break
            if not done:
                # 没有作者行：插到开头元信息区（第一段以 - 开头的行）的末尾
                idx = None
                for i in range(1, min(12, len(lines))):
                    if lines[i].strip().startswith("-"):
                        idx = i
                    elif idx is not None:
                        break
                if idx is not None:
                    lines.insert(idx + 1, "- 作者：" + author)
                else:
                    lines.insert(1, "")
                    lines.insert(2, "- 作者：" + author)
            p.write_text("\n".join(lines), encoding="utf-8")
            return self._send({"ok": True, "author": author})
        except Exception as e:
            return self._send({"ok": False, "error": str(e)})

    def _handle_video_note_analyze(self, body):
        """给一条「未分析」的视频笔记补做 AI 分析。分析在后台线程跑（可能要
        一两分钟），这里立刻返回；前端轮询 /video_note_analyze_progress 看进度。
        同一时间只允许一条笔记在补分析（AI 一次也只干得动一件事）。"""
        name = (body.get("name") or "").strip()
        if not name or "/" in name or "\\" in name or ".." in name:
            return self._send({"ok": False, "error": "非法文件名"})
        p = self._video_dir() / name
        if not p.exists():
            return self._send({"ok": False, "error": "找不到这条笔记"})
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        with _note_an_lock:
            if _note_an_state["running"]:
                return self._send({"ok": False,
                                   "error": "已有一条笔记正在补分析，请等它完成后再点。"})
            if _note_batch.get("running"):
                return self._send({"ok": False, "error": "批量 AI 分析正在进行（AI 池一次只做一件事）。"
                                   "这一条等批量做完再点，或者先点批量那一行的「停止」。"})
            _note_an_state.update({"running": True, "name": name, "stop_req": False,
                                   "stage": "准备", "error": "", "ok": False})
        if not _note_batch.get("running"):
            try:
                import web_model
                web_model._CANCEL_EVT.clear()        # v66：以前点过的「停止」不算到这一条头上
            except Exception:
                pass
        _threading.Thread(target=_note_analyze_worker,
                          args=(name, use_local, model), daemon=True).start()
        return self._send({"ok": True, "started": True})

    def _handle_video_note_analyze_batch(self, body):
        """批量补分析：前端传要分析的笔记文件名列表（一般是「全部未分析」或某个分组里未分析的）。
        后台一条接一条跑；每条都是一个新任务，AI 池会换一张新卡、开新对话（不串上一条的内容）。"""
        if body.get("stop"):
            _note_batch["stop"] = True
            # v62：正在等 AI 回复的这一条也马上放下（以前要等它答完或超时才停，看起来像点了没反应）
            try:
                with _note_an_lock:
                    busy = bool(_note_an_state.get("running"))
                if busy and _note_batch.get("running"):
                    import web_model as _wm
                    _wm.cancel_current("你点了停止")
                    _clog("视频", "⏹ 批量补分析：你点了停止，正在分析的这条马上放下")
            except Exception:
                pass
            return self._send({"ok": True, "stopping": True})
        if body.get("resume_now"):
            _note_batch["resume_now"] = True
            return self._send({"ok": True})
        if _note_batch["running"]:
            return self._send({"ok": False, "error": "已经有一批在分析了（%d/%d），等它结束或先点「停止」"
                                                    % (_note_batch["done"], _note_batch["total"])})
        d = self._video_dir()
        names = []
        for nm in body.get("names") or []:
            nm = str(nm).strip()
            if nm and "/" not in nm and "\\" not in nm and ".." not in nm and (d / nm).exists() and nm not in names:
                names.append(nm)
        if not names:
            return self._send({"ok": False, "error": "没有可分析的笔记"})
        _note_batch_enqueue(names, body.get("use_local", True), body.get("model", "qwen2.5"), "手动批量")
        return self._send({"ok": True, "total": len(names)})

    def _handle_video_note_get(self, name):
        try:
            if not name or "/" in name or "\\" in name:
                return self._send({"ok": False, "error": "非法文件名"})
            p = self._video_dir() / name
            if not p.exists():
                return self._send({"ok": False, "error": "找不到这条笔记"})
            return self._send({"ok": True, "name": name,
                               "content": p.read_text(encoding="utf-8", errors="replace")})
        except Exception as e:
            return self._send({"ok": False, "error": str(e)})

    def _handle_video_note_delete(self, body):
        name = body.get("name", "")
        try:
            if not name or "/" in name or "\\" in name:
                return self._send({"ok": False, "error": "非法文件名"})
            p = self._video_dir() / name
            if p.exists():
                p.unlink()
            # 分组表里也把这条移除（不然文件夹里会留个"幽灵"计数）
            try:
                _vn_assign_folder(name, "")
            except Exception:
                pass
            # 一并清掉这条笔记的截图子目录（video_notes/shots/<笔记stem>/）
            # 以及「仅提取」模式留下的 segments 侧车文件
            try:
                import shutil as _shutil
                stem = name[:-3] if name.endswith(".md") else name
                if stem and "/" not in stem and "\\" not in stem and ".." not in stem:
                    _shutil.rmtree(str(_cx_shots_dir() / stem), ignore_errors=True)
                    sp = _cx_segments_dir() / (stem + ".json")
                    if sp.exists():
                        sp.unlink()
            except Exception:
                pass
            return self._send({"ok": True})
        except Exception as e:
            return self._send({"ok": False, "error": str(e)})

    # ────────────────── 成长库（汇总各工具的产出）──────────────────
    def _lib_roots(self):
        """各类别 → [(目录, 来源标签)]。视频笔记 / 情报简报 / 学习档案。"""
        import agent_core
        MEM = agent_core.MEMORY_DIR
        BACKEND = MEM.parent
        return {
            "video":    [(MEM / "video_notes", "视频笔记")],
            "info":     [(MEM / "briefings", "情报简报")],
            "sniff":    [(MEM / "sniff_reports", "嗅探简报")],
            "learning": [(BACKEND / "学生档案", "学习")],
        }

    def _handle_library(self):
        import datetime
        import json as _json
        import re

        def title_of(txt, stem):
            for line in (txt or "").splitlines():
                s = line.strip().lstrip("#").strip()
                if s:
                    return s[:60]
            return stem

        def tags_of(txt):
            """从文件里解析用户自定义二级标签：'- 标签：金融、逻辑' 这一行。"""
            for line in (txt or "").splitlines():
                s = line.strip().lstrip("-").strip()
                for key in ("标签：", "标签:"):
                    if s.startswith(key):
                        raw = s[len(key):].strip()
                        parts = re.split(r"[、，,\s]+", raw)
                        return [t.strip() for t in parts if t.strip()]
            return []

        def preview_of(txt):
            body = []
            for line in (txt or "").splitlines():
                s = line.strip()
                if (not s or s.startswith("#") or s.startswith("-")
                        or s.startswith("=") or s.startswith("---")
                        or s.startswith("**") or s.startswith(">")):
                    continue
                body.append(s)
                if sum(len(x) for x in body) > 70:
                    break
            return (" ".join(body))[:90]

        def mtime(p):
            return datetime.datetime.fromtimestamp(
                p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

        out = {"video": [], "learning": [], "info": [], "sniff": []}
        try:
            for cat, dirs in self._lib_roots().items():
                for d, source in dirs:
                    if not d.exists():
                        continue
                    for p in sorted(d.glob("*.md"),
                                    key=lambda x: x.stat().st_mtime, reverse=True):
                        try:
                            txt = p.read_text(encoding="utf-8", errors="replace")
                        except Exception:
                            txt = ""
                        src = "每日任务" if (cat == "learning" and "_task_" in p.name) else source
                        out[cat].append({
                            "name": p.name, "cat": cat, "source": src,
                            "title": title_of(txt, p.stem),
                            "tags": tags_of(txt),
                            "date": mtime(p), "preview": preview_of(txt)})
                    if cat == "learning":
                        for p in sorted(d.glob("*.json"),
                                        key=lambda x: x.stat().st_mtime, reverse=True):
                            try:
                                data = _json.loads(
                                    p.read_text(encoding="utf-8", errors="replace"))
                            except Exception:
                                data = {}
                            nm = data.get("name", p.stem)
                            out[cat].append({
                                "name": p.name, "cat": cat, "source": "学习档案",
                                "title": "📋 " + str(nm) + " 的学习档案",
                                "tags": [],
                                "date": mtime(p),
                                "preview": "进度：" + (str(data.get("progress", "")) or "（暂无）")[:60]})
            for cat in out:
                out[cat].sort(key=lambda x: x["date"], reverse=True)
            # 汇总每个类别下用户用过的所有二级标签（按出现频次降序）
            all_tags = {}
            for cat, items in out.items():
                counts = {}
                for it in items:
                    for t in it.get("tags", []):
                        counts[t] = counts.get(t, 0) + 1
                all_tags[cat] = [t for t, _ in sorted(
                    counts.items(), key=lambda kv: (-kv[1], kv[0]))]
            out["all_tags"] = all_tags
        except Exception as e:
            return self._send({"video": [], "learning": [], "info": [], "sniff": [], "error": str(e)})
        return self._send(out)

    def _handle_library_item(self, cat, name):
        import json as _json
        if not name or "/" in name or "\\" in name or ".." in name:
            return self._send({"ok": False, "error": "非法文件名"})
        roots = self._lib_roots()
        if cat not in roots:
            return self._send({"ok": False, "error": "未知类别"})
        for d, _src in roots[cat]:
            p = d / name
            if p.exists():
                txt = p.read_text(encoding="utf-8", errors="replace")
                if p.suffix == ".json":
                    try:
                        txt = self._student_to_md(_json.loads(txt))
                    except Exception:
                        pass
                return self._send({"ok": True, "name": name, "content": txt})
        return self._send({"ok": False, "error": "找不到这条内容"})

    @staticmethod
    def _write_tags_into_file(p, clean):
        """把 clean(list) 写进笔记 p 的「- 标签：」行（已存在则替换，没有则插到元数据区）。"""
        txt = p.read_text(encoding="utf-8", errors="replace")
        nl = "\r\n" if "\r\n" in txt else "\n"
        lines = txt.split(nl)
        tag_line = ("- 标签：" + "、".join(clean)) if clean else None
        idx = None
        for i, ln in enumerate(lines):
            s = ln.strip().lstrip("-").strip()
            if s.startswith("标签：") or s.startswith("标签:"):
                idx = i
                break
        if idx is not None:
            if tag_line:
                lines[idx] = tag_line
            else:
                lines.pop(idx)
        elif tag_line:
            insert_at = 1
            for i in range(1, len(lines)):
                if lines[i].strip().startswith("-"):
                    insert_at = i + 1
                elif lines[i].strip().startswith("##"):
                    break
            lines.insert(insert_at, tag_line)
        p.write_text(nl.join(lines), encoding="utf-8")

    def _handle_library_autotag(self, body):
        """给「视频内容库」里还没有标签的笔记，用 AI 批量补上二级标签。
        只处理 video 类、且当前没有标签的；已有标签的不动。
        body 可带 use_local/model（兜底用），limit（一次最多处理多少条）。"""
        import re
        use_local = (body or {}).get("use_local", True)
        model = (body or {}).get("model", "qwen2.5")
        limit = int((body or {}).get("limit", 20) or 20)

        roots = self._lib_roots()
        dirs = roots.get("video", [])
        done, skipped, failed = 0, 0, 0
        results = []
        try:
            for d, _src in dirs:
                if not d.exists():
                    continue
                for p in sorted(d.glob("*.md"),
                                key=lambda x: x.stat().st_mtime, reverse=True):
                    if done >= limit:
                        break
                    txt = p.read_text(encoding="utf-8", errors="replace")
                    # 已有标签的跳过
                    has_tag = any(
                        ln.strip().lstrip("-").strip().startswith(("标签：", "标签:"))
                        for ln in txt.splitlines())
                    if has_tag:
                        skipped += 1
                        continue
                    # 拆出标题和分析喂给模型
                    title = ""
                    for ln in txt.splitlines():
                        s = ln.strip().lstrip("#").strip()
                        if s:
                            title = s[:60]
                            break
                    aMark = txt.find("AI 分析")
                    tMark = _tmark(txt)
                    analysis = ""
                    if aMark >= 0:
                        a0 = txt.find("\n", aMark)
                        a1 = tMark if tMark > aMark else len(txt)
                        analysis = txt[a0:a1].strip()
                    if not analysis:
                        analysis = txt[:1200]
                    try:
                        tags = _cx_suggest_tag(title, analysis, use_local, model)
                    except Exception:
                        tags = []
                    if tags:
                        try:
                            self._write_tags_into_file(p, tags)
                            done += 1
                            results.append({"name": p.name, "tags": tags})
                        except Exception:
                            failed += 1
                    else:
                        failed += 1
        except Exception as e:
            return self._send({"ok": False, "error": str(e),
                               "done": done, "skipped": skipped, "failed": failed})
        return self._send({"ok": True, "done": done, "skipped": skipped,
                           "failed": failed, "results": results})

    def _handle_library_set_tags(self, body):
        """给一条内容写入/更新用户自定义二级标签。"""
        import re
        cat = (body or {}).get("cat", "")
        name = (body or {}).get("name", "")
        tags = (body or {}).get("tags", [])
        if not isinstance(tags, list):
            tags = []
        # 清洗标签：去空白、去重、限长
        seen, clean = set(), []
        for t in tags:
            t = str(t).strip().replace("、", "").replace(",", "").replace("，", "")
            if t and t not in seen:
                seen.add(t)
                clean.append(t[:20])
            if len(clean) >= 8:
                break
        if not name or "/" in name or "\\" in name or ".." in name:
            return self._send({"ok": False, "error": "非法文件名"})
        roots = self._lib_roots()
        if cat not in roots:
            return self._send({"ok": False, "error": "未知类别"})
        for d, _src in roots[cat]:
            p = d / name
            if not p.exists() or p.suffix != ".md":
                continue
            try:
                self._write_tags_into_file(p, clean)
                return self._send({"ok": True, "tags": clean})
            except Exception as e:
                return self._send({"ok": False, "error": str(e)})
        return self._send({"ok": False, "error": "找不到这条内容"})

    def _student_to_md(self, d):
        nm = d.get("name", "学生")
        lines = ["# 📋 " + str(nm) + " 的学习档案", ""]
        if d.get("created"):
            lines.append("- 建档日期：" + str(d["created"]))
        if d.get("progress"):
            lines += ["", "## 学习进度", "", str(d["progress"])]
        mw = d.get("mastered_words") or []
        ww = d.get("weak_words") or []
        if mw:
            lines += ["", "## 已掌握的词（%d）" % len(mw), "", "、".join(map(str, mw))]
        if ww:
            lines += ["", "## 薄弱词（%d）" % len(ww), "", "、".join(map(str, ww))]
        wq = d.get("wrong_questions") or []
        if wq:
            lines += ["", "## 错题本（共 %d 条，显示最近 20 条）" % len(wq), ""]
            for it in wq[-20:]:
                if isinstance(it, dict):
                    lines.append("- [%s] %s" % (it.get("date", ""), it.get("q", "")))
                else:
                    lines.append("- " + str(it))
        if d.get("notes"):
            lines += ["", "## 备注", "", str(d["notes"])]
        return "\n".join(lines)


def _cx_app_version():
    try:
        import app_version as _av
        return getattr(_av, "APP_VERSION", "")
    except Exception:
        return ""


def main():
    print("[backend] 超能小助 %s" % (_cx_app_version() or "(未知版本)"), flush=True)
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        # 最常见：端口 8756 被上一次没退干净的 python server.py 占用 → bind 失败。
        # 原来这里没 try，会直接抛异常退出、控制台一闪而过、前端永远「后端未连接」。
        # 这里给一条看得懂的提示，方便排查（Windows: netstat -ano | findstr :8756 然后 taskkill）。
        print("=" * 60)
        print("[backend] 启动失败：无法绑定 127.0.0.1:%d" % PORT)
        print("[backend] 原因：%s" % e)
        print("[backend] 多半是上一次的后端没退干净，端口还被占着。")
        print("[backend] Windows 处理：在新终端跑")
        print("[backend]   netstat -ano | findstr :%d" % PORT)
        print("[backend]   taskkill /PID <最后一列的数字> /F")
        print("[backend] 然后重新打开软件。")
        print("=" * 60)
        import sys
        sys.stdout.flush()
        # 多停一会，别让控制台窗口瞬间关掉，留时间看清提示
        try:
            import time as _t_wait
            _t_wait.sleep(30)
        except Exception:
            pass
        return
    print(f"[backend] running at http://{HOST}:{PORT} (local only)")
    print("[backend] close this window or press Ctrl+C to stop.")
    # v54：后台检测 NVIDIA 显卡、准备 GPU 运行库（缺了自动装），语音转文字走显卡
    try:
        import gpu_accel
        gpu_accel.prepare_async()
    except Exception as e:
        print("[gpu] 准备显卡加速失败：%s" % e)
    # v108：嗅探的网页抓取增强（Scrapling）——没装就在后台装到独立环境，不影响软件自己的依赖
    try:
        import scrapling_fetch
        scrapling_fetch.prepare_async()
    except Exception as e:
        print("[scrapling] 准备抓取增强失败：%s" % e)
    # v109：网站嗅探的「自动嗅探」在软件里也会定时跑了（以前只有单独运行 heartbeat.py 才跑）
    try:
        import sniffer
        sniffer.boot_scheduler()
    except Exception as e:
        print("[sniff] 启动自动嗅探计时失败：%s" % e)
    # 启动时恢复上次没跑完的视频任务，自动接着处理
    try:
        _restore_video_queue()
    except Exception as e:
        print("[video] 恢复队列失败：%s" % e)
    # 启动时若开了「洞察」自动爬取，把定时线程拉起来
    try:
        import insight_crawler
        insight_crawler.boot_scheduler()
    except Exception as e:
        print("[insight] 调度启动失败：%s" % e)
    # 博主监控：拉起每日定时扫描线程（不依赖心跳进程，打包后也能跑）
    try:
        import creator_watch
        creator_watch.boot_scheduler()
    except Exception as e:
        print("[creator] 调度启动失败：%s" % e)
    # 分身自动化：拉起定时调度（每个分身独立的定时任务）
    try:
        _boot_automation_scheduler()
        print("[agents] 分身自动化调度已启动")
    except Exception as e:
        print("[agents] 自动化调度启动失败：%s" % e)
    # v83：手机发链接（局域网小网页，默认关；上次开着就接着开）
    try:
        import phone_inbox
        phone_inbox.boot(Handler, _clog)
    except Exception as e:
        print("[手机] 启动失败：%s" % e)
    # v84：飞书机器人收链接（在外面也能发；没设置就什么都不做）
    try:
        import feishu_inbox
        feishu_inbox.boot(_clog, "http://127.0.0.1:%d" % PORT)
    except Exception as e:
        print("[飞书] 启动失败：%s" % e)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[backend] stopped.")
        server.shutdown()


def _startup_repair_taskbar():
    """v67：以前的版本把你最小化着的 Chrome 也从任务栏拿掉了（变成左下角的小条）——启动时放回去。"""
    try:
        import time as _t
        _t.sleep(3)
        import web_model
        n = web_model.repair_taskbar()
        if n:
            _clog("AI池", "✓ 修好了 %d 个被以前版本误藏的浏览器窗口（放回任务栏了）" % n)
    except Exception:
        return
    # v71：每 30 秒看一眼屏幕左下角有没有「小条」（最小化着、没有标题栏或任务栏按钮的窗口），
    #      有就在终端里写一次是哪个程序的，方便找原因（不会去动别的软件的窗口）
    seen = set()
    import os as _os
    me = {_os.getpid()}
    try:
        me.add(_os.getppid())
    except Exception:
        pass
    while True:
        try:
            _t.sleep(30)
            for b in web_model.find_stray_bars():
                if b["hwnd"] in seen:
                    continue
                seen.add(b["hwnd"])
                who = "本软件自己的小窗（这版起会自动放回去）" if b["pid"] in me else (b["name"] or "未知程序")
                _clog("窗口", "左下角有个小条：%s 「%s」（%s）" % (who, b["title"][:30], b["cls"][:40]))
        except Exception:
            _t.sleep(60)


if __name__ == "__main__":
    _threading.Thread(target=_startup_repair_taskbar, daemon=True).start()
    main()
