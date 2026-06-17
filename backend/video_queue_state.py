"""
video_queue_state.py — 对话触发的视频任务的共享登记表

为什么单独一个模块：后端是用 `python server.py` 启动的，server 以 __main__ 运行。
如果在 video_tools.py 里 `import server`，Python 会把 server.py 当成另一个名叫
`server` 的模块再加载一遍，得到的是「第二份」对象——它的列表和 __main__ 里那份
不是同一个，登记进去 /video_progress 也读不到。

把这张登记表放在这个中立模块里，server.py 和 video_tools.py 都 `import
video_queue_state`，两边拿到的就是同一个对象，状态自然同步。
"""

import threading
import time

_lock = threading.Lock()
_tasks = []          # [{id, label, stage, detail, waiting(bool), start}]

# 对话视频任务完成后，把结果放这里，让「视频」板块的轮询渲染出来。
# server.py 会把它合并进 _video_state 并自增 result_id。
_pending_result = {"result": None, "result_id_bump": 0}


def register(label):
    """登记一条对话视频任务，返回它的 id。"""
    tid = "cv" + str(time.time())
    with _lock:
        _tasks.append({
            "id": tid, "label": label or "对话里的视频",
            "stage": "准备", "detail": "", "waiting": False,
            "start": time.time()})
    return tid


def update(tid, stage=None, detail=None, waiting=None, label=None):
    with _lock:
        for t in _tasks:
            if t["id"] == tid:
                if stage is not None: t["stage"] = stage
                if detail is not None: t["detail"] = detail
                if waiting is not None: t["waiting"] = waiting
                if label is not None: t["label"] = label
                break


def done(tid):
    with _lock:
        _tasks[:] = [t for t in _tasks if t["id"] != tid]


def publish_result(res):
    """对话视频任务完成 → 把结果挂起，等 server 合并进 _video_state。"""
    with _lock:
        _pending_result["result"] = res
        _pending_result["result_id_bump"] += 1


def take_result():
    """server 调用：取走待发布的结果（取一次就清空，返回 (result 或 None, bump 次数)）。"""
    with _lock:
        res = _pending_result["result"]
        bump = _pending_result["result_id_bump"]
        _pending_result["result"] = None
        _pending_result["result_id_bump"] = 0
    return res, bump


def snapshot():
    """返回 (running_tasks, waiting_tasks, all_tasks) 的拷贝。"""
    with _lock:
        tasks = [dict(t) for t in _tasks]
    running = [t for t in tasks if not t["waiting"]]
    waiting = [t for t in tasks if t["waiting"]]
    return running, waiting, tasks
