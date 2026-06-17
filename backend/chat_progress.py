"""
chat_progress.py — 对话实时进度通道（配合 backend 的 http.server 对话接口使用）

作用：让「对话」在干活时能像样地一步步显示"现在在做什么 + 进度"，
而不是只有一个固定的"正在整理回复…"。

设计很简单、零第三方依赖：
- 一个内存字典 _store：chat_id -> 当前进度快照 {steps, current, pct, detail, done}
- server 在跑对话时，每经历一步就调用 push()/set_pct() 更新这里；
  前端轮询 /chat_progress?id=xxx 读这里，渲染步骤清单和进度条。
- 还维护"线程 -> chat_id"的绑定：因为每个 /chat 请求在自己的线程里跑，
  这样深层的工具（比如视频语音识别）不用层层传参，也能找到"我属于哪次对话"，
  把自己的百分比报上来。

注：纯内存、单机自用，重启即清空，足够了。
"""

import time
import threading

_lock = threading.RLock()   # ★必须用 RLock(可重入)：push() 在持锁时会调用 start()，
                            #   而 start() 也要拿同一把锁。普通 Lock 不可重入 → 同一线程
                            #   二次加锁会永久死锁（表现为「测试网页模型」卡在『已填入』之后、
                            #   迟迟不发送）。RLock 允许同线程重入，彻底解决。
_store = {}          # chat_id -> snapshot dict
_thread_chat = {}    # thread ident -> chat_id
_thread_settings = {}  # thread ident -> {"use_local":bool, "model":str}

# 最多保留多少条历史 chat 的进度，避免内存无限涨
_MAX_KEEP = 40


def _trim():
    if len(_store) <= _MAX_KEEP:
        return
    # 按最后更新时间排序，丢掉最旧的
    items = sorted(_store.items(), key=lambda kv: kv[1].get("ts", 0))
    for cid, _ in items[:len(_store) - _MAX_KEEP]:
        _store.pop(cid, None)


def start(chat_id):
    """开一次新对话的进度。"""
    if not chat_id:
        return
    with _lock:
        _store[chat_id] = {
            "steps": [],        # 已完成/进行中的步骤文字列表
            "current": "正在思考…",
            "pct": None,        # 当前步骤百分比（0-100），None 表示不显示进度条
            "detail": "",       # 当前步骤的补充说明（如"第38秒/共90秒"）
            "done": False,
            "ts": time.time(),
        }
        _trim()


def bind_thread(chat_id):
    """把当前线程和某次对话绑定，方便深层工具回报进度。"""
    if chat_id:
        _thread_chat[threading.get_ident()] = chat_id


def unbind_thread():
    _thread_chat.pop(threading.get_ident(), None)
    _thread_settings.pop(threading.get_ident(), None)


def current_chat_id():
    """当前线程属于哪次对话（深层工具用）。"""
    return _thread_chat.get(threading.get_ident())


def bind_settings(use_local, model):
    """记下当前线程这次对话用的模型设置，方便深层工具（如视频分析）复用同一个模型。"""
    _thread_settings[threading.get_ident()] = {
        "use_local": use_local, "model": model}


def current_settings():
    """当前线程这次对话的模型设置（深层工具用）。没有则返回 None。"""
    return _thread_settings.get(threading.get_ident())


def push(chat_id, text, pct=None, detail=""):
    """
    进入新的一步。会把上一步收尾（追加到 steps），把这步设为 current。
    text: 这步在干什么，如 "🔧 正在提取视频…"
    """
    if not chat_id:
        return
    with _lock:
        st = _store.get(chat_id)
        if st is None:
            start(chat_id)
            st = _store.get(chat_id)
        # 上一条 current 收尾进历史（去掉末尾的省略号，显得"已完成"）
        prev = (st.get("current") or "").strip()
        if prev:
            st["steps"].append(prev)
        st["current"] = text
        st["pct"] = pct
        st["detail"] = detail
        st["ts"] = time.time()


def set_pct(chat_id, pct, detail=""):
    """只更新当前这步的进度百分比，不新增步骤。"""
    if not chat_id:
        return
    with _lock:
        st = _store.get(chat_id)
        if st is None:
            return
        if pct is not None:
            st["pct"] = max(0, min(100, int(pct)))
        if detail:
            st["detail"] = detail
        st["ts"] = time.time()


def push_for_thread(text, pct=None, detail=""):
    """深层工具用：按线程找到 chat_id 再 push。"""
    push(current_chat_id(), text, pct, detail)


def set_pct_for_thread(pct, detail=""):
    set_pct(current_chat_id(), pct, detail)


def finish(chat_id):
    """对话结束，标记 done（前端看到 done 就停止轮询）。"""
    if not chat_id:
        return
    with _lock:
        st = _store.get(chat_id)
        if st is not None:
            prev = (st.get("current") or "").strip()
            if prev and (not st["steps"] or st["steps"][-1] != prev):
                st["steps"].append(prev)
            st["current"] = ""
            st["pct"] = None
            st["detail"] = ""
            st["done"] = True
            st["ts"] = time.time()
    unbind_thread()


def get(chat_id):
    """取某次对话的进度快照（前端轮询用）。"""
    with _lock:
        st = _store.get(chat_id)
        if st is None:
            return {"steps": [], "current": "", "pct": None,
                    "detail": "", "done": False, "unknown": True}
        # 返回浅拷贝，避免外部改到内部状态
        return {
            "steps": list(st["steps"]),
            "current": st["current"],
            "pct": st["pct"],
            "detail": st["detail"],
            "done": st["done"],
        }
