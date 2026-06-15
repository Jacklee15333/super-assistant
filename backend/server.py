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
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import agent_core as core

HOST = "127.0.0.1"
PORT = 8756  # 一个不常用的端口，避免和别的程序撞

_tg_started = False  # Telegram bot 是否已启动（避免重复启动）

# 视频提取：支持排队。前端轮询 /video_progress 看进度+队列。
import threading as _threading
_video_q = []                       # 待处理队列：[{url, level, use_local, model}]
_video_lock = _threading.Lock()
_video_worker_on = {"v": False}
_video_state = {"running": False, "stage": "", "detail": "", "elapsed": 0,
                "queue_len": 0, "result": None, "result_id": 0, "current_url": "",
                "current_label": "", "queue": []}


def _cx_video_dir():
    import agent_core
    d = agent_core.MEMORY_DIR / "video_notes"
    d.mkdir(exist_ok=True)
    return d


def _cx_analyze_transcript(transcript, title, use_local, model):
    prompt = (
        "下面是一段视频的文字稿（语音识别得到，可能有个别错别字）。"
        "请你帮我做一份**内容充实、有深度**的中文笔记。要求写得详细，不要只写一句话敷衍。\n\n"
        "请按下面结构输出（用 Markdown 小标题）：\n"
        "## 一句话概括\n用一句话说清楚这个视频到底在讲什么。\n\n"
        "## 背景与主题\n用 2-3 句交代视频的话题背景、作者站在什么角度讲。\n\n"
        "## 核心观点\n分点列出 5-8 条主要观点。**每条都要写 2-4 句**：先说观点，"
        "再结合视频里提到的具体例子、数据、故事或说法把它讲透，不要只写一个短语。\n\n"
        "## 金句摘录\n从文字稿里挑 2-4 句最有价值或最有意思的原话，照原话摘出来。\n\n"
        "## 值得记住的点 / 行动建议\n分点写作者给的具体建议或最有用的信息，越具体越好。\n\n"
        "## 我的点评\n用 3-5 句客观点评：这些观点有没有道理、哪里值得认同、"
        "哪里需要注意或保留，普通人可以怎么用。\n\n"
        "整体要条理清晰、信息密度高，是归纳不是照抄。\n\n"
        f"视频标题：{title}\n\n=== 文字稿 ===\n{transcript[:10000]}\n")
    try:
        client = core.make_client(use_local)
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}])
        return (resp.choices[0].message.content or "").strip() or "（没分析出内容）"
    except Exception as e:
        return f"（分析出错：{e}）"


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
                return
            job = _video_q.pop(0)
            _video_state["queue"] = [j["url"] for j in _video_q]
            _video_state["queue_len"] = len(_video_q)
        _video_state["running"] = True
        _video_state["current_url"] = job["url"]
        _video_state["current_label"] = job["url"]
        _video_state["stage"] = "准备"
        _video_state["detail"] = ""
        _video_state["elapsed"] = 0
        start = _time.time()
        tick = {"on": True}

        def _ticker():
            while tick["on"]:
                _video_state["elapsed"] = int(_time.time() - start)
                _time.sleep(1)
        _threading.Thread(target=_ticker, daemon=True).start()

        def cb(stage, detail=""):
            _video_state["stage"] = stage
            _video_state["detail"] = detail

        try:
            res = video_transcribe.extract(job["url"], level=job["level"],
                                           progress_cb=cb)
            if res.get("ok"):
                cb("AI 分析", "让模型把文字稿总结成笔记…")
                transcript = res["transcript"]
                title = res.get("title") or "（无标题）"
                uploader = res.get("uploader") or ""
                clean_url = res.get("url") or job["url"]
                analysis = _cx_analyze_transcript(transcript, title,
                                                  job["use_local"], job["model"])
                ts = datetime.datetime.now()
                safe = "".join(c for c in title[:20]
                               if c.isalnum() or c in " 　-_") or "video"
                fname = (f"{ts.strftime('%Y%m%d-%H%M%S')}-{safe}.md"
                         .replace(" ", "_"))
                doc = (f"# {title}\n\n"
                       f"- 来源链接：{clean_url}\n"
                       f"- 作者：{uploader}\n"
                       f"- 提取时间：{ts.strftime('%Y-%m-%d %H:%M')}\n\n"
                       f"## 🤖 AI 分析\n\n{analysis}\n\n"
                       f"---\n\n## 📝 完整文字稿\n\n{transcript}\n")
                try:
                    _cx_video_dir().joinpath(fname).write_text(doc, encoding="utf-8")
                except Exception:
                    pass
                res["analysis"] = analysis
                res["saved_as"] = fname
            _video_state["result"] = res
        except Exception as e:
            _video_state["result"] = {"ok": False, "error": str(e)}
        finally:
            tick["on"] = False
            _video_state["result_id"] += 1
        # 继续处理下一个


def _enqueue_video(job):
    """把一个视频任务加入队列，必要时启动后台 worker。返回它的排队位置。"""
    with _video_lock:
        _video_q.append(job)
        _video_state["queue"] = [j["url"] for j in _video_q]
        _video_state["queue_len"] = len(_video_q)
        running = _video_state["running"]
        pos = len(_video_q) + (1 if running else 0)
        if not _video_worker_on["v"]:
            _video_worker_on["v"] = True
            _threading.Thread(target=_video_worker, daemon=True).start()
    return pos


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

    def do_OPTIONS(self):
        self._send({}, 200)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/ping":
            return self._send({"ok": True})

        if path == "/heartbeat/status":
            return self._send({"running": _hb_state["running"],
                               "interval": _hb_state["interval"],
                               "last": _hb_state["last"]})

        if path == "/video_notes":
            return self._handle_video_notes_list()
        if path == "/video_progress":
            return self._send(_video_state)
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

        if path == "/models":
            try:
                import ollama_helper
                local = ollama_helper.list_models()
                cloud = ollama_helper.known_cloud_models()
                return self._send({"models": local, "cloud": cloud})
            except Exception as e:
                return self._send({"models": [], "cloud": [], "error": str(e)}, 200)

        if path == "/memory/list":
            return self._send({"files": core.tool_list_memory().split("\n")})

        if path == "/memory":
            name = qs.get("name", [""])[0]
            return self._send({"content": core.read_memory_file(name)})

        if path == "/wecom/callback":
            # 企业微信 URL 验证：返回解密后的 echostr（纯文本）
            try:
                import wecom_bot
                cfg = wecom_bot.load_config()
                echo = wecom_bot.handle_callback_get(cfg, qs)
                if echo is not None:
                    return self._send_text(echo)
            except Exception:
                pass
            return self._send_text("", 200)

        self._send({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        # 企业微信 / 飞书回调要原始 body，单独先处理
        if path == "/wecom/callback":
            return self._handle_wecom_post(qs)
        if path == "/feishu/callback":
            return self._handle_feishu_post()

        body = _json_body(self)

        if path == "/chat":
            return self._handle_chat(body)
        if path == "/heartbeat":
            return self._handle_heartbeat(body)
        if path == "/video_transcribe":
            return self._handle_video_transcribe(body)
        if path == "/video_install":
            return self._handle_video_install(body)
        if path == "/video_note_delete":
            return self._handle_video_note_delete(body)
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
        if path == "/env_check":
            use_local = body.get("use_local", True)
            model = body.get("model", "qwen2.5")
            try:
                import ollama_helper
                return self._send(ollama_helper.environment_check(use_local, model))
            except Exception as e:
                return self._send({"ok": False, "items": [
                    {"name": "环境检查", "ok": False, "detail": str(e)}]}, 200)
        if path == "/memory":
            name = body.get("name", "")
            content = body.get("content", "")
            result = core.write_memory_file(name, content)
            ok = not result.startswith("拒绝")
            return self._send({"ok": ok, "message": result})

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

    def _handle_briefing(self, body):
        """生成一次情报简报（搜+读+提炼+推送）。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        try:
            import briefing
            brief = briefing.generate_briefing(
                use_local=use_local, model=model, verbose=False)
            return self._send({"ok": True, "brief": brief})
        except Exception as e:
            return self._send({"ok": False, "brief": f"出错：{e}"})

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

    def _handle_chat(self, body):
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        shell_enabled = body.get("shell_enabled", False)
        messages = body.get("messages", [])
        # 让微信/飞书渠道也用同一套模型设置
        Handler._channel_cfg = {"use_local": use_local, "model": model}

        # 每次都用最新的记忆文件重建系统提示
        sys_prompt = core.build_system_prompt()
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = sys_prompt
        else:
            messages.insert(0, {"role": "system", "content": sys_prompt})

        tool_calls = []

        def on_tool(name, args, result):
            tool_calls.append({"name": name, "args": args,
                               "result": str(result)[:1000]})

        approvals = body.get("approvals", {})  # {tool_call_id: true/false}

        try:
            client = core.make_client(use_local)
            reply, messages, pending = core.run_agent(
                client, model, messages,
                shell_enabled=shell_enabled, on_tool=on_tool,
                approvals=approvals)
            if pending is not None:
                # 遇到危险操作，挂起等用户确认
                self._send({"pending": pending, "tool_calls": tool_calls,
                            "messages": messages})
            else:
                self._send({"reply": reply, "tool_calls": tool_calls,
                            "messages": messages})
        except Exception as e:
            self._send({"reply": f"出错了：{e}", "tool_calls": [],
                        "error": str(e)}, 200)

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

    def _handle_remember(self, body):
        """存档当前对话并更新长期记忆。"""
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        messages = body.get("messages", [])
        try:
            import conversation_memory as cm
            fname = cm.save_conversation(messages)
            client = core.make_client(use_local)
            summary = cm.update_long_term_memory(client, model, messages)
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

    def _handle_video_install(self, _body):
        """自动安装视频提取所需的依赖（yt-dlp / faster-whisper）。"""
        try:
            import video_transcribe
            ok, out = video_transcribe.install_deps()
            msg = ("依赖装好了，可以开始提取视频了。" if ok
                   else "安装没成功，可能是网络问题。可稍后重试，或手动在命令行运行："
                        "pip install yt-dlp faster-whisper")
            return self._send({"ok": ok, "message": msg, "log": out})
        except Exception as e:
            return self._send({"ok": False, "message": f"安装出错：{e}"})

    def _handle_video_transcribe(self, body):
        """把视频任务加入队列，后台逐个处理。前端轮询 /video_progress。"""
        url = body.get("url", "").strip()
        level = body.get("level", "balanced")
        use_local = body.get("use_local", True)
        model = body.get("model", "qwen2.5")
        if not url:
            return self._send({"ok": False, "error": "请先粘贴视频链接。"})
        try:
            import video_transcribe
        except Exception as e:
            return self._send({"ok": False, "error": f"模块加载失败：{e}"})

        missing = video_transcribe.check_deps()
        if missing:
            return self._send({"need": missing})

        pos = _enqueue_video({"url": url, "level": level,
                              "use_local": use_local, "model": model})
        return self._send({"queued": True, "position": pos})

    def _handle_video_move_models(self, _body):
        """把 C 盘缓存里已下载的模型搬到 D 盘。"""
        try:
            import video_transcribe
            r = video_transcribe.move_cached_models()
            if r.get("moved"):
                r["message"] = "已搬到 " + r.get("dest", "D 盘") + "：" + "、".join(r["moved"])
            else:
                r["message"] = "没在 C 盘缓存里找到已下载的模型（可能还没下过，或已经在 D 盘了）。"
            return self._send(r)
        except Exception as e:
            return self._send({"ok": False, "message": f"搬运出错：{e}"})

    def _handle_video_notes_list(self):
        try:
            d = self._video_dir()
            items = []
            for p in sorted(d.glob("*.md"), reverse=True):
                txt = p.read_text(encoding="utf-8", errors="replace")
                title = txt.splitlines()[0].lstrip("# ").strip() if txt else p.stem
                items.append({"name": p.name, "title": title})
            return self._send({"ok": True, "notes": items})
        except Exception as e:
            return self._send({"ok": False, "notes": [], "error": str(e)})

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
            return self._send({"ok": True})
        except Exception as e:
            return self._send({"ok": False, "error": str(e)})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[backend] running at http://{HOST}:{PORT} (local only)")
    print("[backend] close this window or press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[backend] stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
