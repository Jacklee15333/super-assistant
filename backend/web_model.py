"""
web_model.py — 「伪模型」核心：用 Playwright 操作 sorryios.ai/pastel 的网页 ChatGPT。

这是参考实现 ai/ai-runner.js（Node + Playwright）的 Python 移植，保留它全部
经过实战打磨的健壮性：
  · 单浏览器单例（任一时刻只有一个 Chromium）
  · storageState 登录态持久化（7 天 TTL）
  · 选卡进聊天页（按 空闲 > 正常 > 繁忙 优先级随机选一张 TEAM/PLUS 卡）
  · 发送 prompt（冷启动 hydration 兼容、读回校验、Shift+Enter 换行不误发）
  · ★命门 _wait_for_reply：思考型模型「先预声明→思考N秒→出真答案」的多层答完判定
  · 卡死恢复（STUCK → 换卡重试）、纯思考无输出保护、空回卷保护、总超时兜底

并发模型：后端是多线程 http.server，但 Playwright 同步 API 的对象绑定创建线程。
所以这里起一个【专用 worker 线程】独占浏览器，所有请求经 web_complete() 投递到任务
队列、阻塞等结果——一个 worker 一次只处理一个 job，这本身就是「串行单浏览器」锁。

对外只暴露：
  configure(cfg) / load_config() / save_config(cfg)
  web_complete(prompt, **opts) -> str        # 同步阻塞，返回回复纯文本
  test_login(on_progress=None) -> dict        # 「测试网页模型」用
  get_state() -> dict
  shutdown()
"""

import json
import time
import queue
import random
import threading
import traceback
from pathlib import Path

# —— 解决 Windows 控制台中文乱码（防御性，server.py 已设过；单独跑也安全）——
import sys as _sys
try:
    # line_buffering=True：每行立即刷新，避免日志卡在缓冲区里看不到（排错关键）
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

try:
    from playwright.sync_api import sync_playwright
    _PW_IMPORT_ERR = None
except Exception as _e:          # 没装 playwright 时不要让 import 崩掉整个后端
    sync_playwright = None
    _PW_IMPORT_ERR = _e

# ─────────────── 常量 ───────────────
LOGIN_URL = "https://sorryios.ai/pastel/#/login"
CARLIST_URL = "https://sorryios.ai/pastel/#/carlist"

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
CONFIG_PATH = MEMORY_DIR / "web_model.json"
SESSION_PATH = MEMORY_DIR / "web_session.json"
SESSION_TTL_DAYS = 7

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _default_config():
    return {
        "aiUsername": "",
        "aiPassword": "",
        "headless": False,        # 默认显示浏览器，便于排错；设 True 后台跑
        "cardName": "",           # 想指定的卡名（留空＝任意可用卡，全都是 ChatGPT）
        "enableSearch": True,     # 默认开联网搜索：软件要的就是最新信息，别让用户漏配
        "aiUrl": "https://sorryios.ai/",
    }


# ─────────────── 配置读写（人类可读、可手改）───────────────
def load_config():
    if CONFIG_PATH.exists():
        try:
            c = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = {**_default_config(), **c}
            # 迁移：老配置里 enableSearch 可能是 False（早期默认），且用户从没手动设过。
            # 软件目的就是拿最新信息，这里强制兜底为 True，省得用户不知道要去勾。
            # 仅当用户显式写了 enableSearchUserSet=true 才尊重其 False 选择。
            if not c.get("enableSearchUserSet") and merged.get("enableSearch") is not True:
                merged["enableSearch"] = True
            return merged
        except Exception:
            pass
    return _default_config()


def save_config(cfg):
    merged = {**load_config(), **(cfg or {})}
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    # 配置变了（尤其账号），让下次查询重新就位
    _worker().request_restart()
    return merged


# ─────────────── session（storageState）持久化 ───────────────
def _load_session():
    if not SESSION_PATH.exists():
        return None
    try:
        wrapper = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        if not wrapper or "savedAt" not in wrapper or "state" not in wrapper:
            return None
        age_ms = time.time() * 1000 - wrapper["savedAt"]
        if age_ms > SESSION_TTL_DAYS * 24 * 3600 * 1000:
            return None
        return wrapper["state"]
    except Exception:
        return None


def _save_session(state):
    try:
        SESSION_PATH.write_text(
            json.dumps({"savedAt": time.time() * 1000, "state": state},
                       ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def _clear_session():
    try:
        if SESSION_PATH.exists():
            SESSION_PATH.unlink()
    except Exception:
        pass


def is_available():
    return sync_playwright is not None


def playwright_import_error():
    return str(_PW_IMPORT_ERR) if _PW_IMPORT_ERR else ""


# ════════════════════════════════════════════════════════════════
# Worker：独占浏览器的专用线程。所有浏览器操作只在这个线程里跑。
# ════════════════════════════════════════════════════════════════
class _WebWorker:
    def __init__(self):
        self._jobs = queue.Queue()
        self._thread = None
        self._lock = threading.Lock()
        self._want_restart = False
        # 以下都只在 worker 线程内访问
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._state = "idle"   # idle | ready | error | closed
        self._logger = print

    # ---- 公共：投递一个 job，阻塞等结果 ----
    def submit(self, fn_name, kwargs, timeout=720):
        self._ensure_thread()
        result_box = {}
        done = threading.Event()
        self._jobs.put((fn_name, kwargs, result_box, done))
        if not done.wait(timeout):
            raise TimeoutError("web_model job 超时未返回")
        if "error" in result_box:
            raise result_box["error"]
        return result_box.get("value")

    def request_restart(self):
        self._want_restart = True

    def _ensure_thread(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, name="web-model-worker", daemon=True)
            self._thread.start()

    def set_logger(self, fn):
        self._logger = fn or print

    def _log(self, msg):
        try:
            self._logger("[web_model] " + str(msg))
            try:
                _sys.stdout.flush()
            except Exception:
                pass
        except Exception:
            pass

    # ---- worker 主循环：一次处理一个 job（＝串行单浏览器）----
    def _run(self):
        if sync_playwright is None:
            return
        with sync_playwright() as pw:
            self._pw = pw
            while True:
                fn_name, kwargs, box, done = self._jobs.get()
                try:
                    fn = getattr(self, fn_name)
                    box["value"] = fn(**(kwargs or {}))
                except Exception as e:        # noqa
                    box["error"] = e
                    self._log("job 出错: " + repr(e))
                    self._log(traceback.format_exc())
                finally:
                    done.set()

    # ════════════════════ 浏览器生命周期 ════════════════════
    def _launch_browser(self, headless):
        tries = [
            ("Google Chrome", "chrome"),
            ("Microsoft Edge", "msedge"),
            ("Playwright bundled Chromium", None),
        ]
        last_err = None
        for name, channel in tries:
            try:
                opts = dict(
                    headless=bool(headless),
                    args=["--disable-blink-features=AutomationControlled",
                          "--no-sandbox", "--disable-dev-shm-usage"],
                )
                if channel:
                    opts["channel"] = channel
                b = self._pw.chromium.launch(**opts)
                self._log("launched via " + name)
                return b
            except Exception as e:
                last_err = e
                self._log("try %s failed: %s" % (name, str(e).split(chr(10))[0]))
        raise RuntimeError("没有可用浏览器，最后错误: %s" % last_err)

    def _destroy_browser(self, browser):
        if not browser:
            return
        try:
            for c in list(browser.contexts):
                try:
                    c.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

    def _close(self):
        b = self._browser
        self._page = self._context = self._browser = None
        self._state = "closed"
        self._destroy_browser(b)

    def _ensure_started(self):
        """启动 + 登录 + 选卡 + 进聊天页。已就绪则直接返回。"""
        if (self._state == "ready" and self._page and not self._page.is_closed()
                and not self._want_restart):
            return
        # 残留句柄先收掉，保证单浏览器
        if self._browser or self._want_restart:
            self._close()
        self._want_restart = False

        cfg = load_config()
        if not cfg.get("aiUsername") or not cfg.get("aiPassword"):
            self._state = "error"
            raise RuntimeError("请先在「网页大模型」设置里填写 sorryios.ai 账号和密码")

        headless = cfg.get("headless") is True
        self._state = "starting"
        self._log("starting (headless=%s)..." % headless)
        try:
            self._browser = self._launch_browser(headless)
            saved = _load_session()
            self._context = self._browser.new_context(
                storage_state=saved or None,
                viewport={"width": 1280, "height": 900},
                user_agent=UA,
            )
            self._page = self._context.new_page()
            # 全局默认超时调短：任何 click/fill 卡住最多 8 秒就抛错，便于快速换方法/诊断
            try:
                self._page.set_default_timeout(8000)
            except Exception:
                pass
            self._log("context ready, savedState=%s" % ("YES" if saved else "NO"))

            need_login = True
            if saved:
                try:
                    self._page.goto(CARLIST_URL, wait_until="domcontentloaded",
                                    timeout=20000)
                    time.sleep(2.5)
                    status = self._page.evaluate("""() => {
                        const url = window.location.href;
                        const hasPasswordInput = !!document.querySelector('input[type="password"]');
                        const bt = (document.body.innerText || '');
                        const hasLoginText = bt.includes('用户登录') || /密\\s*码/.test(bt) || /账\\s*号/.test(bt);
                        const hasCardListMarkers = bt.includes('TEAM') || bt.includes('PRO') || bt.includes('PLUS') ||
                            bt.includes('空闲') || bt.includes('繁忙') || bt.includes('正常') || /[A-Z]{2}\\d{4}-\\d{2}/.test(bt);
                        return { url, hasPasswordInput, hasLoginText, hasCardListMarkers };
                    }""")
                    if (("carlist" in status["url"]) and not status["hasPasswordInput"]
                            and not status["hasLoginText"] and status["hasCardListMarkers"]):
                        self._log("✓ session 复用成功，跳过登录")
                        need_login = False
                    else:
                        _clear_session()
                except Exception as e:
                    self._log("session 复用出错: %s → 走完整登录" % e)
                    _clear_session()

            if need_login:
                self._do_login(cfg)
                try:
                    _save_session(self._context.storage_state())
                    self._log("✓ session 已保存，下次免登录")
                except Exception as e:
                    self._log("session 保存失败: %s" % e)

            self._select_card_and_enter_chat()
            self._state = "ready"
            self._log("✓ 就绪")
        except Exception:
            self._state = "error"
            self._close()
            raise

    # ════════════════════ 登录 ════════════════════
    def _human_type(self, locator, text):
        for ch in text:
            delay = 30 + random.randint(0, 49)
            if ch == "\n":
                locator.press("Shift+Enter")     # 换行不触发发送
                time.sleep(delay / 1000)
            elif ch == "\r":
                continue
            else:
                locator.type(ch, delay=delay)

    def _find_button_by_text(self, *keywords):
        for kw in keywords:
            for b in self._page.locator("button").all():
                try:
                    t = ((b.inner_text(timeout=1000) or "").strip().lower())
                    if kw.lower() in t and b.is_visible():
                        return b
                except Exception:
                    pass
        return None

    def _do_login(self, cfg):
        self._log("打开登录页 " + LOGIN_URL)
        try:
            self._page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        except Exception:
            pass
        time.sleep(2 + random.random())

        visible = [i for i in self._page.locator("input").all()
                   if self._safe(lambda i=i: i.is_visible(), False)]
        if len(visible) < 2:
            raise RuntimeError("登录页找不到 2 个可见输入框，sorryios.ai 可能改版了")

        visible[0].click(); time.sleep(0.3); visible[0].fill("")
        self._human_type(visible[0], cfg["aiUsername"])
        self._log("已输入账号")
        time.sleep(0.5)
        visible[1].click(); time.sleep(0.3); visible[1].fill("")
        self._human_type(visible[1], cfg["aiPassword"])
        self._log("已输入密码")
        time.sleep(0.5)

        btn = self._find_button_by_text("用户登录", "登录", "Login")
        if btn:
            btn.click()
        else:
            self._page.keyboard.press("Enter")

        try:
            self._page.wait_for_url("**/carlist**", timeout=15000)
            self._log("✓ 登录成功")
        except Exception:
            time.sleep(3)
            if "carlist" not in self._page.url:
                raise RuntimeError("登录后没跳到卡片列表页 — 账号或密码可能错了")
            self._log("✓ 登录成功（延迟跳转）")

    # ════════════════════ 选卡 + 进聊天页 ════════════════════
    def _select_card_and_enter_chat(self):
        for attempt in range(3):
            try:
                self._select_random_card()
            except Exception as e:
                self._log("选卡异常: " + str(e))
            ready = self._wait_chat_page_ready(25)
            if ready is True:
                return True
            if ready == "login_redirect":
                self._log("↻ session 失效，重新登录...")
                _clear_session()
                self._do_login(load_config())
                try:
                    _save_session(self._context.storage_state())
                except Exception:
                    pass
                continue   # 不消耗 attempt（与参考一致：重登后重选）
            self._log("进入聊天页失败，第 %d 次重试" % (attempt + 1))
            self._safe(lambda: self._page.goto(CARLIST_URL, wait_until="networkidle",
                                               timeout=30000))
            time.sleep(3)
        raise RuntimeError("选卡进入聊天页失败（已重试 3 次）")

    def _select_random_card(self):
        self._log("选 AI 卡片中...")
        if "carlist" not in self._page.url:
            self._safe(lambda: self._page.goto(CARLIST_URL, wait_until="networkidle",
                                               timeout=30000))
        time.sleep(3 + random.random() * 2)

        # 在【当前视口】里扫所有 Plus/Team 卡，返回 [{name, status}]。
        scan_js = """() => {
            const R = [];
            for (const el of document.querySelectorAll('*')) {
                const r = el.getBoundingClientRect();
                if (r.bottom < 0 || r.top > window.innerHeight ||
                    r.width < 150 || r.width > 460 || r.height < 70 || r.height > 280) continue;
                const t = el.innerText || '';
                const m = t.match(/[A-Z]{2}\\d{4}-\\d{2}/);
                const hasTeamOrPlus = t.includes('TEAM') || t.includes('PLUS') ||
                                      t.includes('Plus') || t.includes('PRO') || !!m;
                if (!hasTeamOrPlus) continue;
                let status = '';
                if (t.includes('空闲')) status = '空闲';
                else if (t.includes('繁忙')) status = '繁忙';
                else if (t.includes('正常')) status = '正常';
                else continue;
                if (m) R.push({ name: m[0], status });
            }
            return R;
        }"""

        # 一次滚动整页，收齐所有卡（按卡名去重，保留最优状态）
        buckets = {"空闲": set(), "正常": set(), "繁忙": set()}
        seen = {}
        self._safe(lambda: self._page.evaluate("window.scrollTo(0, 0)"))
        time.sleep(0.6)
        total = self._safe(lambda: self._page.evaluate(
            "() => document.body.scrollHeight"), 3000) or 3000
        vh = self._safe(lambda: self._page.evaluate(
            "() => window.innerHeight"), 800) or 800
        step = int(vh * 0.85) or 600
        y = 0
        for _ in range(50):     # 最多翻 50 屏，覆盖几百张卡
            got = self._safe(lambda: self._page.evaluate(scan_js), []) or []
            for c in got:
                nm, st = c.get("name"), c.get("status")
                if nm and st in buckets:
                    if nm not in seen:
                        seen[nm] = st
                        buckets[st].add(nm)
            if y >= total:
                break
            y += step
            self._safe(lambda yy=y: self._page.evaluate("window.scrollTo(0, %d)" % yy))
            time.sleep(0.3)

        # 优先 Plus/Team 空闲；没有空闲再用正常；都没有再兜底繁忙
        picked, names = "空闲", list(buckets["空闲"])
        if not names:
            picked, names = "正常", list(buckets["正常"])
        if not names:
            picked, names = "繁忙", list(buckets["繁忙"])
        if not names:
            raise RuntimeError("页面上找不到任何 Plus/Team 卡（空闲/正常/繁忙都没有）")

        random.shuffle(names)
        chosen = names[0]
        tag = "【繁忙·兜底】" if picked == "繁忙" else "【%s】" % picked
        self._log("空闲%d/正常%d/繁忙%d 张 → 随机选中%s: %s" % (
            len(buckets["空闲"]), len(buckets["正常"]), len(buckets["繁忙"]), tag, chosen))

        # 按卡名把它滚到视口中央再点
        if not self._click_card_by_name(chosen):
            raise RuntimeError("选中卡 %s 但点击失败（页面结构可能变了）" % chosen)
        time.sleep(2)

    def _click_card_by_name(self, name):
        coords = self._safe(lambda: self._page.evaluate("""(name) => {
            for (const el of document.querySelectorAll('*')) {
                const r = el.getBoundingClientRect();
                if (r.width < 150 || r.width > 460 || r.height < 70 || r.height > 280) continue;
                if ((el.innerText || '').includes(name)) {
                    el.scrollIntoView({block: 'center'});
                    const rr = el.getBoundingClientRect();
                    return { cx: Math.round(rr.x + rr.width/2), cy: Math.round(rr.y + rr.height/2) };
                }
            }
            return null;
        }""", name), None)
        if not coords:
            return False
        time.sleep(0.4)
        self._page.mouse.click(coords["cx"], coords["cy"])
        return True

    def _wait_chat_page_ready(self, timeout_sec=25):
        self._log("等聊天页就绪...")
        start = time.time()
        last_log = 0
        while time.time() - start < timeout_sec:
            time.sleep(2)
            try:
                info = self._page.evaluate("""() => {
                    const url = window.location.href;
                    let inputCount = 0;
                    const inputs = [...document.querySelectorAll('textarea'),
                                    ...document.querySelectorAll('[contenteditable="true"]')];
                    for (const el of inputs) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 200 && r.height > 0) inputCount++;
                    }
                    const bt = document.body.innerText || '';
                    const hasPasswordInput = !!document.querySelector('input[type="password"]');
                    return {
                        url, inputCount,
                        hasChatHint: bt.includes('询问任何问题') || bt.includes('有什么可以帮') ||
                                     bt.includes('开始使用') || bt.includes('Send a message'),
                        isCarlist: url.includes('carlist'),
                        isLoginPage: url.includes('login') || hasPasswordInput,
                    };
                }""")
            except Exception:
                continue
            if info["isLoginPage"]:
                self._log("⚠ 选卡后被重定向到登录页，session 已失效")
                return "login_redirect"
            if (not info["isCarlist"]) and (info["inputCount"] > 0 or info["hasChatHint"]):
                self._log("✓ 聊天页就绪")
                time.sleep(4)     # 冷启动 hydration 缓冲
                return True
            if time.time() - last_log > 6:
                self._log("还在等聊天页... inputCount=%s isCarlist=%s"
                          % (info["inputCount"], info["isCarlist"]))
                last_log = time.time()
        return False

    # ════════════════════ 查询 ════════════════════
    def web_complete(self, prompt, on_progress=None, **opts):
        """对外主入口（在 worker 线程内执行）。返回 AI 回复纯文本。"""
        def prog(msg):
            if on_progress:
                self._safe(lambda: on_progress(msg))
        prog("打开网页 / 就位中…")
        self._ensure_started()

        # ★ 2026-06 新增：forceNewCard —— 主动换一张新卡再问。
        #   用于 agent 工具循环里碰到「轴卡」（死活不肯输出工具块、一直用文字推辞）时，
        #   由上层（web_model_client）请求换一张卡重抽，直到碰到肯配合的卡。
        if opts.get("forceNewCard"):
            self._log("[换卡] 上层请求换一张新卡重试…")
            prog("换一张 AI 卡片重试…")
            self._safe(lambda: self._page.goto(CARLIST_URL,
                       wait_until="networkidle", timeout=30000))
            time.sleep(3)
            self._select_card_and_enter_chat()
            self._state = "ready"

        disable_switch = bool(opts.get("disableCardSwitch"))
        max_attempts = 1 if disable_switch else 2
        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._query_once(prompt, opts, attempt, prog)
            except _Stuck as e:
                last_err = e
                self._state = "ready"
                if attempt < max_attempts and not disable_switch:
                    self._log("[恢复] 卡死，换张卡重试...")
                    prog("上一张卡卡住，换卡重试…")
                    self._safe(lambda: self._page.goto(CARLIST_URL,
                               wait_until="networkidle", timeout=30000))
                    time.sleep(3)
                    self._select_card_and_enter_chat()
                    continue
                raise
            except Exception as e:
                self._state = "ready"
                raise e
        raise last_err or RuntimeError("未知错误")

    def _capture_baseline(self):
        js = """() => {
            const selectors = ['[class*="markdown"]','[class*="prose"]','[class*="message-content"]',
                '[class*="msg-content"]','[class*="assistant"]','[class*="response"]',
                '[class*="reply-content"]','[class*="answer"]','[data-message-author-role="assistant"]'];
            const c = [];
            for (const sel of selectors) {
                let els; try { els = document.querySelectorAll(sel); } catch(e) { continue; }
                for (const el of els) {
                    const r = el.getBoundingClientRect();
                    const t = (el.innerText || '').trim();
                    if (r.width > 200 && t.length > 30) c.push({text:t, bottom:r.bottom, length:t.length});
                }
            }
            if (!c.length) return null;
            c.sort((a,b)=>b.bottom-a.bottom);
            const topY = c[0].bottom;
            const near = c.filter(x=>topY-x.bottom<200);
            near.sort((a,b)=>b.length-a.length);
            return { text: near[0].text, count: c.length };
        }"""
        return self._safe(lambda: self._page.evaluate(js), None)

    def _find_input(self):
        """
        找 AI 输入框。
        ★修复：Playwright Python 的 is_visible() 不接受 timeout 参数（JS 版接受），
          原来写 is_visible(timeout=1000) 会抛 TypeError 被吞掉 → 全部失配。
        做法：先用一组选择器试可见元素；找不到再用 JS 在页面下半部选出最大的
          可编辑元素打标记，回拿 locator。带 ~8 秒重试，兼容冷启动 hydration。
        """
        selectors = [
            'textarea[placeholder*="问" i]', 'textarea[placeholder*="消息" i]',
            'textarea[placeholder*="message" i]', 'textarea[placeholder*="ask" i]',
            '#prompt-textarea', 'div[contenteditable="true"]',
            '[contenteditable="true"]', '[role="textbox"]',
            'textarea:not([readonly])', 'textarea',
        ]
        deadline = time.time() + 8
        while time.time() < deadline:
            # 1) 直接用选择器（注意：is_visible 不传 timeout）
            for sel in selectors:
                try:
                    loc = self._page.locator(sel).last
                    if loc.count() and loc.is_visible():
                        # 打标记，供 _MARK_SEND_JS 按这一行定位发送键
                        self._safe(lambda l=loc: l.evaluate(
                            "el => { document.querySelectorAll('[data-cx-input]')"
                            ".forEach(e=>e.removeAttribute('data-cx-input'));"
                            " el.setAttribute('data-cx-input','1'); }"))
                        return loc
                except Exception:
                    pass
            # 2) JS 兜底：在页面下半部选出面积最大的可编辑框，打标记后回拿
            marked = self._safe(lambda: self._page.evaluate(_FIND_INPUT_JS), None)
            if marked:
                try:
                    loc = self._page.locator('[data-cx-input="1"]').last
                    if loc.count():
                        return loc
                except Exception:
                    pass
            time.sleep(0.5)
        raise RuntimeError("找不到 AI 输入框 — sorryios.ai 页面结构可能变了")

    def _query_once(self, prompt, opts, attempt, prog):
        self._state = "busy"
        timeout_ms = opts.get("timeout") or 600000
        self._log("发送 prompt (len=%d, 第%d次)..." % (len(prompt), attempt))

        baseline = self._capture_baseline()
        inp = self._find_input()
        self._log("已定位输入框，准备填入…")
        time.sleep(1.0)

        # ── 填入：新版 ChatGPT 是 ProseMirror contenteditable。依次试 insert_text / fill / type ──
        pre = ""
        filled = False
        for how in ("insert_text", "fill", "type"):
            try:
                inp.click(timeout=5000)
                self._page.keyboard.press("Control+A")
                self._page.keyboard.press("Delete")
                if how == "insert_text":
                    self._page.keyboard.insert_text(prompt)
                elif how == "fill":
                    inp.fill(prompt, timeout=5000)
                else:
                    self._page.keyboard.type(prompt, delay=0)
                time.sleep(0.4)
                pre = self._read_input_text(inp)
                if len(pre) >= min(int(len(prompt) * 0.8), 8):
                    filled = True
                    self._log("已填入（方式=%s，框内 %d 字）" % (how, len(pre)))
                    break
                self._log("填入[%s]后框内只有 %d 字，换方式…" % (how, len(pre)))
            except Exception as e:
                self._log("填入[%s]异常：%s" % (how, e))
        if not filled:
            raise RuntimeError("prompt 没填进输入框（换卡重试）")

        # ── 发送 ──
        # ★核心修复★ 发送成功的判定【不再只看输入框是否清空】：
        #   新版 ChatGPT 5.5 的输入区是 ProseMirror contenteditable，发出去后清空有延迟、
        #   还会重建 DOM 节点 —— 于是 _read_input_text 常常读到“旧的 12 个字”，让程序
        #   误判“没发出去”，接着重复点/重复 Enter（这时 UI 已经在生成了），最后抛“发送未触发”。
        #   这正是之前一直发不出去的真凶（交接报告 §6.a）。
        # 现在改成【看页面状态】判断是否真的发出去了（交接报告 §6.4 的首选方案）：
        #   ① 出现“停止■”按钮（genState=generating）＝AI 已收到、正在生成；或
        #   ② 整页文字明显变长（页面上多了你的提问气泡 / 开始出现回复）；或
        #   ③ 输入框确实清空（保留为辅助信号，但不再是唯一依据）。
        #   任一成立即视为发送成功。
        # 发送动作本身优先用“可操作点击”按钮（Playwright 自动滚动入视、等可点、避开悬浮遮挡层，
        #   比裸坐标点击稳得多，对应参考实现 ai-runner.js 的做法），找不到再退到
        #   Enter / 坐标点击 / 指针事件兜底。
        prog("已填好，点击发送…")
        pre_page_len = self._page_text_len()
        self._log("发送前页面文字 %d 字，开始发送…" % pre_page_len)
        sent = False
        for label, action in (
            ("发送按钮·可操作点击", lambda: self._click_send_btn()),
            ("Enter", lambda: self._press_send_key(inp)),
            ("发送键·坐标兜底", lambda: self._click_send(mechanism="mouse")),
            ("发送键·指针事件兜底", lambda: self._click_send(mechanism="js_events")),
        ):
            self._log("尝试发送方式：%s" % label)
            self._safe(action)
            if self._wait_send_committed(pre_page_len, inp, pre, label):
                sent = True
                break
        if not sent:
            # 抛 _Stuck，让上层 web_complete 自动换一张卡重试（比直接失败更稳）
            raise _Stuck("发送未触发：按钮/Enter/坐标/指针事件都没把消息发出去（换卡重试）")

        reply = self._wait_for_reply(timeout_ms, baseline, prompt, opts, prog)
        # 把回复重新抓成 Markdown：把 <a href> 还原成可点击链接 [文字](网址)，
        # 并去掉 ChatGPT 的引用角标杂质（如 "OpenAI +1"、"Anthropic +2"）。
        # 仅当抓取结果可信（长度不大幅缩水）才采用，否则保留纯文本。
        md = self._safe(lambda: self._page.evaluate(_GRAB_MARKDOWN_JS), "") or ""
        if md and len(md) >= max(40, int(len(reply or "") * 0.6)):
            reply = md
        self._state = "ready"
        return reply

    # ──────────── 发送相关小工具（本次修复新增）────────────
    def _page_text_len(self):
        """整页可见文字长度。发送后它会因为多出『提问气泡 + 回复』而变长——用来判断发出去没。"""
        return self._safe(
            lambda: self._page.evaluate("() => (document.body.innerText || '').length"), 0) or 0

    def _press_send_key(self, inp):
        """聚焦输入框后按 Enter 发送（标准 ChatGPT：Enter=发送，Shift+Enter=换行）。"""
        inp.click(timeout=4000)
        self._page.keyboard.press("Enter")
        return True

    def _click_send_btn(self):
        """
        【首选发送方式】用 Playwright 的『可操作点击』点发送按钮 —— 它会自动把按钮滚动到
        可见、等待其可点、并避开悬浮遮挡层（紫色气泡/右侧竖排工具条），比裸坐标点击稳得多。
        选择器同时覆盖参考实现 ai-runner.js 里验证可用的那几个（button[type=submit] /
        button:has(svg[class*=send]) / 文案『发送』『Send』）和新版可能的语义选择器。
        命中不到再用启发式 _MARK_SEND_JS 标出那颗 ↑ 键，仍用可操作点击点它。
        """
        sel = ('button[data-testid="send-button"], #composer-submit-button, '
               'button[type="submit"], button[aria-label*="发送" i], '
               'button[aria-label*="send" i], button:has-text("发送"), '
               'button:has-text("Send"), button:has(svg[class*="send" i])')
        try:
            loc = self._page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                loc.click(timeout=4000)
                self._log("  已点击发送按钮（可操作点击，选择器命中）")
                return True
        except Exception as e:
            self._log("  发送按钮可操作点击异常：%s" % e)

        # 选择器没命中 → 启发式定位那颗 ↑ 键，再可操作点击
        res = self._safe(lambda: self._page.evaluate(_MARK_SEND_JS), None)
        if res and res.get("ok"):
            self._log("  发送键候选: %s ｜ 附近按钮: %s"
                      % (res.get("pick") or "", res.get("desc") or ""))
            try:
                loc2 = self._page.locator('[data-cx-send="1"]').last
                if loc2.count() and loc2.is_visible():
                    loc2.click(timeout=4000)
                    self._log("  已点击发送键（启发式定位 + 可操作点击）")
                    return True
            except Exception as e:
                self._log("  启发式发送键点击异常：%s" % e)
        else:
            self._log("  未命中发送按钮选择器。附近按钮: " + ((res or {}).get("desc") or "(无)"))
        return False

    def _wait_send_committed(self, pre_page_len, inp, pre_text, label, max_wait=3.5):
        """
        判断消息是否【真的发出去了】。不再只看输入框清空（ProseMirror 清空有延迟还会重建节点，
        会误判），而是轮询 1~3.5 秒，命中任一即算成功：
          ① genState=generating（出现『停止■』按钮，AI 已收到正在生成）；
          ② 整页文字明显变长（页面多了提问气泡 / 开始出现回复）；
          ③ 输入框确实清空（保留为辅助信号）。
        """
        deadline = time.time() + max_wait
        pre_len = len(pre_text or "")
        clear_thresh = max(3, int(pre_len * 0.4))
        grow_thresh = max(30, pre_len)        # 至少要多出『提问气泡』那么多字
        while time.time() < deadline:
            time.sleep(0.5)
            probe = self._safe(lambda: self._page.evaluate(_PROBE_JS), None)
            if (probe or {}).get("genState") == "generating":
                self._log("✓ 发送成功（方式：%s）：检测到『停止■』，AI 已开始生成" % label)
                return True
            grew = self._page_text_len() - pre_page_len
            if grew > grow_thresh:
                self._log("✓ 发送成功（方式：%s）：页面新增 %d 字（出现提问气泡/回复）"
                          % (label, grew))
                return True
            post = self._read_input_text(inp)
            if pre_len and len(post) < clear_thresh:
                self._log("✓ 发送成功（方式：%s）：输入框已清空（剩 %d 字）" % (label, len(post)))
                return True
        self._log("  方式[%s]发送后无明显变化（停止键/页面增长/清空都没出现），换下一种…" % label)
        return False

    def _read_input_text(self, inp):
        try:
            return inp.evaluate(
                "el => (el.value !== undefined && el.value !== null ? el.value : (el.innerText || '')) || ''") or ""
        except Exception:
            return ""

    def _click_send(self, mechanism="mouse"):
        """
        识别并点击发送按钮（输入框右侧圆形 ↑）。mechanism:
          'mouse'     → 坐标鼠标点击（默认，最不易被拦截）
          'js_events' → 在按钮上派发完整指针事件序列（pointerdown/up+click，兼容挑剔的 React 按钮）
        始终把 composer 附近按钮清单打到日志，便于排错。
        """
        # 已知语义选择器先试（命中即点）
        for sel in ('button[data-testid="send-button"]', '#composer-submit-button',
                    'button[aria-label*="发送" i]', 'button[aria-label*="send" i]'):
            try:
                loc = self._page.locator(sel).last
                if loc.count() and loc.is_visible() and loc.is_enabled():
                    loc.click(timeout=3000)
                    self._log("  点击发送键（选择器 %s）" % sel)
                    return True
            except Exception:
                pass

        res = self._safe(lambda: self._page.evaluate(_MARK_SEND_JS), None)
        if not res or not res.get("ok"):
            self._log("  未识别到发送键。附近按钮: " + ((res or {}).get("desc") or "(无)"))
            return False
        self._log("  发送键候选: %s ｜ 附近按钮: %s"
                  % (res.get("pick") or "", res.get("desc") or ""))

        if mechanism == "js_events":
            ok = self._safe(lambda: self._page.evaluate(_DISPATCH_SEND_JS), False)
            self._log("  已派发指针事件到发送键" if ok else "  指针事件派发失败")
            return bool(ok)

        # mouse：坐标点击 → locator 点击 → JS 原生 click
        cx, cy = res.get("cx"), res.get("cy")
        if cx and cy:
            try:
                self._page.mouse.click(cx, cy)
                self._log("  已坐标点击发送键 (%s,%s)" % (cx, cy))
                return True
            except Exception as e:
                self._log("  坐标点击失败: %s" % e)
        try:
            loc = self._page.locator('[data-cx-send="1"]').last
            if loc.count():
                loc.click(timeout=3000)
                self._log("  已 locator 点击发送键")
                return True
        except Exception as e:
            self._log("  locator 点击失败: %s" % e)
        try:
            self._page.evaluate(
                "() => { const e=document.querySelector('[data-cx-send=\"1\"]'); if(e) e.click(); }")
            self._log("  已 JS 原生点击发送键")
            return True
        except Exception:
            return False

    # ════════════════════ ★命门：答完判定 ════════════════════
    def _wait_for_reply(self, timeout_ms, baseline, prompt_text, opts, prog):
        start = time.time()
        expects_json = bool(opts.get("expectsJson"))
        min_expected = opts.get("minExpectedLength") or (300 if expects_json else 0)
        required_markers = [m for m in (opts.get("requiredMarkers") or [])
                            if isinstance(m, str) and m]
        markers_min_hits = opts.get("markersMinHits") or min(2, len(required_markers))
        hold_cap_ms = opts.get("holdCapMs") or 180000
        accept_stable = [m for m in (opts.get("acceptStableMarkers") or [])
                         if isinstance(m, str) and m]
        think_noout_fatal_ms = opts.get("thinkNoOutputMs") or 300000
        # ★短回复模式：调用方明确这是个简短的确定性回复（如"起标题"），
        #   答完判定以「发送按钮恢复可发送」为准，按钮一稳定恢复就算完，不强求长时间空闲。
        short_reply = bool(opts.get("shortReply"))

        first_hold_at = 0
        td_baseline = -1
        td_last_text = ""
        td_since = 0
        EMPTY_ANSWER_GRACE_MS = 25000
        think_since = 0
        idle_confirm = 0
        IDLE_CONFIRM_REPS = 4

        last_text = ""
        last_change = time.time()
        stable = 0
        SETTLE_INTERVAL = 1.5
        SETTLE_REPS = 4
        POLL = 0.5
        STUCK_WARN_MS = 60000
        STUCK_FATAL_MS = 240000
        warned = False
        last_log = time.time()
        last_full_len = 0
        saw_new = baseline is None
        skip_log = 0
        hold_log = 0
        last_prog = 0

        while (time.time() - start) * 1000 < timeout_ms:
            time.sleep(POLL)

            # 卡死信号：整页 innerText 长度
            full_len = self._safe(
                lambda: self._page.evaluate("() => (document.body.innerText || '').length"), 0) or 0
            if full_len != last_full_len and full_len > 0:
                last_full_len = full_len
                last_change = time.time()
                warned = False
            else:
                idle_ms = (time.time() - last_change) * 1000
                if idle_ms > STUCK_FATAL_MS:
                    self._log("[STUCK] AI 已 %ds 无任何响应" % round(idle_ms / 1000))
                    raise _Stuck("AI 卡死")
                if idle_ms > STUCK_WARN_MS and not warned:
                    self._log("[警告] AI 似乎卡住（%ds 无响应），继续等..." % round(idle_ms / 1000))
                    warned = True

            probe = self._safe(lambda: self._page.evaluate(_PROBE_JS), None)

            # AI 还在思考：跳过本轮，但累计「纯思考无输出」时长
            if probe and probe.get("status") == "thinking":
                last_change = time.time()
                warned = False
                if not last_text:
                    if not think_since:
                        think_since = time.time()
                    if (time.time() - think_since) * 1000 > think_noout_fatal_ms:
                        self._log("[STUCK] 一直思考但无输出，判思考卡死")
                        raise _Stuck("AI 一直思考但无输出")
                if time.time() - skip_log > 5:
                    self._log("AI 正在思考中，等待回复出现...")
                    if time.time() - last_prog > 4:
                        prog("思考中…")
                        last_prog = time.time()
                    skip_log = time.time()
                continue

            if probe:
                if probe.get("genState") == "generating" or probe.get("status") == "thinking":
                    idle_confirm = 0
                elif probe.get("genState") == "idle":
                    idle_confirm += 1

            # 「思考结束但交白卷」检测
            if probe and td_baseline < 0:
                td_baseline = probe.get("thinkingDoneCount") or 0
            if probe and (not last_text) and (probe.get("thinkingDoneCount") or 0) > td_baseline:
                td_text = probe.get("thinkingDoneText") or ""
                if td_text != td_last_text:
                    td_last_text = td_text
                    td_since = time.time()
                elif td_since and (time.time() - td_since) * 1000 > EMPTY_ANSWER_GRACE_MS:
                    self._log("⚠ 思考结束但无输出（偷懒），换卡重试")
                    raise _Stuck("AI 思考结束但没有输出任何回答")
            elif last_text and td_since:
                td_since = 0
                td_last_text = ""

            if not probe or not probe.get("chosen"):
                continue
            current = probe["chosen"].get("text") or ""

            # 防 prompt 回显
            if prompt_text and current and len(prompt_text) > 100:
                head = prompt_text.replace(" ", "").replace("\n", "")[:80]
                cur_head = current.replace(" ", "").replace("\n", "")[:200]
                if head and head in cur_head:
                    last_change = time.time()
                    warned = False
                    if time.time() - skip_log > 5:
                        self._log("抓到的是 prompt 回显，等真实 AI 回复...")
                        skip_log = time.time()
                    continue

            # 防模板标记
            if any(mark in current for mark in
                   ("═══ 范例", "严格输出", "【判定口诀】", "═══ 演变史格式")):
                last_change = time.time()
                warned = False
                continue

            # 与基线相同＝本轮还没开始
            if baseline and not saw_new and current == baseline.get("text"):
                if time.time() - skip_log > 5:
                    self._log("等待 AI 开始回复中（底部还是上一轮回复）")
                    skip_log = time.time()
                continue
            if not saw_new:
                saw_new = True
                self._log("✓ AI 开始产生本轮回复（%d 字）" % len(current))
                prog("接收回复中…")
            think_since = 0

            if current != last_text:
                stable = 0
                last_text = current
                first_hold_at = 0
                if time.time() - last_log > 3:
                    self._log("内容增长中... %d 字" % len(current))
                    if time.time() - last_prog > 4:
                        prog("接收回复中…（%d 字）" % len(current))
                        last_prog = time.time()
                    last_log = time.time()
            elif len(current) >= 1:
                # 短回复（如"起标题"只有十几个字）也要进入完成判定。
                # 之前这里写 len>50，导致短答案永远进不来、卡死到超时。
                # 真正的防误判由 _finalize_if_done 里的「按钮恢复可发送 + 持续空闲」来把关。
                stable += 1
                # 短回复模式下，文本稳定要求放宽到约 2 秒即可进入判定（再由按钮态最终确认）
                settle_need = (SETTLE_INTERVAL * 1.3) if short_reply else (SETTLE_INTERVAL * SETTLE_REPS)
                if stable * POLL >= settle_need:
                    res = self._finalize_if_done(
                        current, probe, idle_confirm, IDLE_CONFIRM_REPS,
                        expects_json, min_expected, required_markers,
                        markers_min_hits, accept_stable, short_reply)
                    if res["done"]:
                        self._log("内容稳定，长度=%d" % len(current))
                        return current
                    # 防误判：继续等（带 holdCap 上限）
                    if not first_hold_at:
                        first_hold_at = time.time()
                    held_ms = (time.time() - first_hold_at) * 1000
                    if held_ms > hold_cap_ms:
                        self._log("⚠ 防误判等待达上限，接受现有 %d 字返回" % len(current))
                        return current
                    last_change = time.time()
                    warned = False
                    stable = 0
                    if time.time() - hold_log > 10:
                        self._log("内容已稳定 %d 字，但 %s，继续等真答案..."
                                  % (len(current), res["reason"]))
                        hold_log = time.time()

        if len(last_text) > 4:
            self._log("[警告] 等待超时，但已有部分内容（%d 字），返回" % len(last_text))
            return last_text
        raise RuntimeError("等待 AI 回复超时")

    @staticmethod
    def _finalize_if_done(current, probe, idle_confirm, idle_reps,
                          expects_json, min_expected, required_markers,
                          markers_min_hits, accept_stable, short_reply=False):
        import re
        has_json_fence = bool(re.search(r"```json[\s\S]*?```", current))
        first_b = current.find("{")
        last_b = current.rfind("}")
        opens = current.count("{")
        closes = current.count("}")
        has_braces = (first_b >= 0 and last_b > first_b and opens >= 2
                      and abs(opens - closes) <= 1)
        has_json = has_json_fence or has_braces

        norm = current.replace("：", ":")
        marker_hits = sum(1 for m in required_markers if m in norm) if required_markers else 0
        markers_ok = (not required_markers) or marker_hits >= markers_min_hits

        # ★短回复特别容易被误判★：联网/思考模型常先抛一句"我会先去查…"的开场白，
        #   按钮也会短暂恢复成"可发送"，导致把开场白当成最终答案（就像漏掉新闻联播正文那次）。
        #   所以默认短回复（< SHORT 字）要求"持续空闲更久"才算真答完，跨过开场白与真答案之间的空档。
        #   但若调用方明确这是「短回复任务」(short_reply=True，如起标题)，则信任按钮态：
        #   按钮恢复可发送、稳定约 3 秒即可判完成，不再死等。
        SHORT = 250
        if short_reply:
            need_idle = max(idle_reps, 6)   # ≈ 持续 3s 空闲（按钮恢复）即算完成
        else:
            need_idle = idle_reps if len(current) >= SHORT else max(idle_reps, 14)

        # 按钮已变回「可发送」且持续稳定 ＝ 最可靠的完成信号
        if idle_confirm >= need_idle and markers_ok:
            return {"done": True, "reason": ""}

        # 短答案即完成标记（显式标记优先）
        for m in accept_stable:
            if m in norm:
                return {"done": True, "reason": ""}

        # ★短回复任务：完成判定【只】认"发送按钮恢复可发送"这一个信号。
        #   上面 idle_confirm>=need_idle 没满足 → 说明按钮还在「停止■」（AI 还在生成），
        #   一律继续等，绝不靠"文本稳定"提前收尾，避免把流式中途的停顿当成答完。
        if short_reply:
            return {"done": False, "reason": "等发送按钮恢复可发送"}

        loose_think = bool(probe.get("hasLooseThinking") or probe.get("hasThinkingIndicator"))
        if expects_json and not has_json:
            return {"done": False, "reason": "缺 JSON 块"}
        if len(current) < min_expected:
            return {"done": False, "reason": "低于最小预期 %d 字" % min_expected}
        if not markers_ok:
            return {"done": False, "reason": "必含标记只命中 %d/%d" % (marker_hits, markers_min_hits)}
        if loose_think and len(current) < 500 and (not has_json or expects_json is False):
            return {"done": False, "reason": "AI 仍在思考"}
        # 兜底保险：回复偏短、又没拿到"持续空闲"的确认，多半是开场白/半截话，别急着收尾
        if len(current) < SHORT and idle_confirm < need_idle:
            return {"done": False, "reason": "回复偏短、答完信号不足"}
        return {"done": True, "reason": ""}

    # ════════════════════ 工具 ════════════════════
    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def get_state(self):
        return {"state": self._state, "hasBrowser": bool(self._browser),
                "hasPage": bool(self._page), "available": is_available()}

    def test_login(self, on_progress=None):
        """「测试网页模型」：就位 + 发一句测试，验证选择器与答完判定，并把 AI 回复带回前端展示。"""
        def prog(m):
            if on_progress:
                self._safe(lambda: on_progress(m))
        self._ensure_started()
        # 用一句简短的问题（比回复短），让 AI 给出一两句话的回答——这样回复块足够长、
        # 能被答完判定正常抓到，前端就能显示 AI 的真实回复内容。
        test_prompt = "你好，请用一两句话简单介绍一下你能帮我做什么。"
        reply = ""
        try:
            reply = self._query_once(test_prompt, {"timeout": 120000}, 1, prog)
        except Exception as e:
            # 即使「答完判定」超时/异常，只要页面上 AI 已经显示了回复，也尽量抓回来给用户看
            self._log("答完判定异常（%s），尝试直接抓取页面上的回复…" % e)
            reply = self._grab_latest_reply(exclude_text=test_prompt)
            if not (reply or "").strip():
                raise
        if not (reply or "").strip():
            reply = self._grab_latest_reply(exclude_text=test_prompt)
        return {"ok": True, "reply": (reply or "").strip()[:500]}

    def _grab_latest_reply(self, exclude_text=""):
        """
        宽松地抓「页面上最新那条 AI 回复」的文字（最底部、足够宽的文本块＝最新回复气泡），
        容忍很短的回复（如『测试成功。』）。用于测试展示 / 答完判定抓不到时的兜底。
        exclude_text：要排除的文字（通常是刚发出去的提问，避免把自己的提问当成回复）。
        """
        js = r"""(exclude) => {
            const sels = ['[data-message-author-role="assistant"]','[class*="markdown"]',
                '[class*="prose"]','[class*="assistant"]','[class*="answer"]',
                '[class*="response"]','[class*="reply-content"]','[class*="message-content"]',
                '[class*="msg-content"]'];
            const norm = s => (s||'').replace(/\s+/g,'');
            const ex = norm(exclude);
            const items = [];
            const seen = new Set();
            for (const s of sels){
                let els; try{els=document.querySelectorAll(s)}catch(e){continue}
                for(const el of els){
                    const r=el.getBoundingClientRect();
                    const t=(el.innerText||'').trim();
                    if(r.width>180 && t.length>0){
                        const n=norm(t);
                        if(!n || seen.has(n)) continue;
                        if(ex && n===ex) continue;          // 跳过＝刚发的提问
                        seen.add(n);
                        items.push({t, bottom:r.bottom, len:t.length});
                    }
                }
            }
            if(!items.length) return '';
            // 最底部的块＝最新回复；同样靠底时取更长的
            items.sort((a,b)=> (b.bottom-a.bottom) || (b.len-a.len));
            return items[0].t;
        }"""
        return self._safe(lambda: self._page.evaluate(js, exclude_text), "") or ""


# 把"最新一条 AI 回复"抓成 Markdown：保留 <a href> 为可点击链接 [文字](网址)，
# 去掉 ChatGPT 的引用角标/来源芯片（"+1""+2"、citation/footnote 之类）这些杂质。
_GRAB_MARKDOWN_JS = r"""() => {
    const sels = ['[data-message-author-role="assistant"]','[class*="markdown"]',
        '[class*="prose"]','[class*="assistant"]','[class*="message-content"]'];
    let best=null, bestBottom=-1;
    for (const s of sels){
        let els; try{els=document.querySelectorAll(s)}catch(e){continue}
        for(const el of els){
            const r=el.getBoundingClientRect();
            const t=(el.innerText||'').trim();
            if(r.width>200 && t.length>20 && r.bottom>bestBottom){ best=el; bestBottom=r.bottom; }
        }
    }
    if(!best) return '';
    const clsOf = (el) => {
        try { return (el.className && el.className.baseVal!==undefined) ? el.className.baseVal : (el.className||''); }
        catch(e){ return ''; }
    };
    const isCite = (el) => {
        const c = (clsOf(el)+'').toLowerCase();
        if(/citation|footnote|sources?-|cite|reference|annotation/.test(c)) return true;
        const t=(el.innerText||el.textContent||'').replace(/[\s\u00a0]+/g,'');
        if(/^[+＋﹢][\d０-９]+$/.test(t)) return true;   // "+1" "+2"（含全角＋/全角数字/带空格）
        return false;
    };
    const walk = (node) => {
        let out='';
        for(const child of node.childNodes){
            if(child.nodeType===3){ out += child.textContent; continue; }
            if(child.nodeType!==1) continue;
            const el=child, tag=el.tagName.toLowerCase();
            if(tag==='script'||tag==='style') continue;
            if(isCite(el)) continue;
            if(tag==='a'){
                const href=el.getAttribute('href')||'';
                let txt=(el.innerText||el.textContent||'').trim().replace(/\s*↗\s*$/,'').trim();
                if(/^[+＋﹢][\d０-９]+$/.test(txt.replace(/[\s\u00a0]+/g,'')) || !txt) continue;
                if(/^https?:\/\//i.test(href)) out += '['+txt+']('+href+')';
                else out += txt;
                continue;
            }
            if(tag==='strong'||tag==='b'){ const t=walk(el).trim(); if(t) out+='**'+t+'**'; continue; }
            if(tag==='em'||tag==='i'){ const t=walk(el).trim(); if(t) out+='*'+t+'*'; continue; }
            if(tag==='code'){ const t=(el.innerText||el.textContent||''); if(t) out+='`'+t+'`'; continue; }
            if(tag==='br'){ out+='\n'; continue; }
            if(/^h([1-6])$/.test(tag)){
                const n=parseInt(tag[1],10);
                out += '\n'+'#'.repeat(n)+' '+walk(el).trim()+'\n';
                continue;
            }
            if(tag==='ol'){
                let i=1;
                for(const li of el.children){
                    if(li.tagName && li.tagName.toLowerCase()==='li')
                        out += (i++)+'. '+walk(li).trim()+'\n';
                }
                out+='\n'; continue;
            }
            if(tag==='ul'){
                for(const li of el.children){
                    if(li.tagName && li.tagName.toLowerCase()==='li')
                        out += '- '+walk(li).trim()+'\n';
                }
                out+='\n'; continue;
            }
            if(tag==='li'){ out += '- '+walk(el).trim()+'\n'; continue; }
            const block=/^(p|div|tr|blockquote|pre|section|article)$/.test(tag);
            out += walk(el);
            if(block) out+='\n';
        }
        return out;
    };
    let md = walk(best);
    md = md.replace(/[ \t]+\n/g,'\n').replace(/\n{3,}/g,'\n\n').replace(/[ \t]{2,}/g,' ').trim();
    return md;
}"""


# 找输入框的 JS 兜底：在页面下半部挑最可能的可编辑框，打 data-cx-input 标记
_FIND_INPUT_JS = r"""() => {
    const cands = [...document.querySelectorAll(
        'textarea, [contenteditable="true"], div[contenteditable], [role="textbox"]')];
    let best = null;
    for (const el of cands) {
        const r = el.getBoundingClientRect();
        if (r.width < 150 || r.height < 10 || r.height > 400) continue;
        // 输入框在底部：优先 bottom 最大的那个
        if (!best || r.bottom > best.bottom) best = { el, bottom: r.bottom };
    }
    if (!best) return false;
    document.querySelectorAll('[data-cx-input]').forEach(e => e.removeAttribute('data-cx-input'));
    best.el.setAttribute('data-cx-input', '1');
    return true;
}"""


# 找发送按钮的 JS 兜底：在输入区右下角挑「可点、非停止■方块」的图标键，打 data-cx-send 标记。
# 与 _PROBE_JS 的 SENDBTN1 同源：停止键=SVG 仅含 <rect>（■）；发送键=箭头(path)/语音。
_MARK_SEND_JS = r"""() => {
    const STOP_RE = /(停止|停止生成|中止|stop|stop generating|abort)/i;
    const SEND_RE = /(发送|send|提交|submit|send prompt)/i;
    const input = document.querySelector('[data-cx-input="1"]') ||
                  document.querySelector('textarea, [contenteditable="true"], [role="textbox"], .ProseMirror');
    const inRect = input ? input.getBoundingClientRect() : null;

    const desc = [];
    const cands = [];
    for (const b of document.querySelectorAll('button, [role="button"]')) {
        const r = b.getBoundingClientRect();
        if (r.width < 10 || r.height < 10) continue;
        // 只看输入框那一行附近（垂直接近 input），排除页面右侧那条竖排悬浮工具条
        const nearRow = inRect
            ? (r.top >= inRect.top - 24 && r.top <= inRect.bottom + 100)
            : (r.bottom > window.innerHeight * 0.55);
        if (!nearRow) continue;
        const lab = ((b.getAttribute('aria-label')||'') + ' ' + (b.getAttribute('title')||'') + ' ' +
                     (b.getAttribute('data-testid')||'')).trim();
        const svg = b.querySelector('svg');
        const onlyRect = svg && svg.querySelector('rect') &&
                         svg.querySelectorAll('path, line, polyline, polygon, circle').length === 0;
        const shape = svg ? (onlyRect ? 'rect■' : 'icon') : 'txt';
        const disabled = b.disabled || b.getAttribute('aria-disabled') === 'true';
        desc.push('[' + (lab || '无') + '|' + shape + '|' + (disabled ? '禁' : '可') +
                  '|x' + Math.round(r.right) + ']');
        if (disabled) continue;
        if (STOP_RE.test(lab) || onlyRect) continue;        // 停止键，跳过
        cands.push({ el: b, right: r.right,
                     cx: Math.round(r.x + r.width / 2), cy: Math.round(r.y + r.height / 2),
                     isSend: SEND_RE.test(lab), lab: lab || ('icon@x' + Math.round(r.right)) });
    }
    if (!cands.length) return { ok: false, desc: desc.join(' ') };
    // 语义 send 优先；否则取最靠右的（发送键在最右，+ / 麦克风在其左）
    cands.sort((a, b) => (b.isSend - a.isSend) || (b.right - a.right));
    const pick = cands[0];
    document.querySelectorAll('[data-cx-send]').forEach(e => e.removeAttribute('data-cx-send'));
    pick.el.setAttribute('data-cx-send', '1');
    return { ok: true, desc: desc.join(' '), pick: pick.lab, cx: pick.cx, cy: pick.cy };
}"""


# 在发送键上派发完整指针/鼠标事件序列（兼容只监听 pointerdown/onClick 的 React 按钮）
_DISPATCH_SEND_JS = r"""() => {
    const e = document.querySelector('[data-cx-send="1"]');
    if (!e) return false;
    const r = e.getBoundingClientRect();
    const x = r.x + r.width / 2, y = r.y + r.height / 2;
    const base = { bubbles: true, cancelable: true, composed: true, view: window,
                   clientX: x, clientY: y, button: 0 };
    const seq = ['pointerover','pointerenter','pointerdown','mousedown','pointerup','mouseup','click'];
    for (const t of seq) {
        let ev;
        try {
            ev = t.startsWith('pointer')
                ? new PointerEvent(t, { ...base, pointerId: 1, isPrimary: true })
                : new MouseEvent(t, base);
        } catch (_) {
            ev = new MouseEvent(t === 'pointerdown' ? 'mousedown'
                              : t === 'pointerup' ? 'mouseup' : t, base);
        }
        e.dispatchEvent(ev);
    }
    if (typeof e.click === 'function') { try { e.click(); } catch (_) {} }
    return true;
}"""


# 探测 JS（_wait_for_reply 每轮调用）——思考态识别 + 发送/停止按钮态 + 回复块抓取
_PROBE_JS = r"""() => {
    const bodyText = (document.body.innerText || '').slice(0, 4000);
    const thinkingPatterns = [
        /^\s*正在思考[\s.…]*$/im, /^\s*思考中[\s.…]*$/im,
        /^\s*Thinking[\s.…]*$/im, /^\s*已思考\s*\d*\s*秒?\s*$/im,
    ];
    const hasThinkingIndicator = thinkingPatterns.some(p => p.test(bodyText));
    const looseThinkingPatterns = [
        /已思考\s*\d+\s*秒/, /Thought\s+for\s+\d+\s*[ms]/i, /Thinking\.\.\./,
        /Reasoning\b/i, /正在思考|思考中|正在推理|推理中/, /Working on it/i,
        /正在搜索|搜索中/, /Searching\b/i,
    ];
    const hasLooseThinking = looseThinkingPatterns.some(p => p.test(bodyText));
    const bodyTail = (document.body.innerText || '').slice(-4000);
    let thinkingDoneAll = [];
    try {
        thinkingDoneAll = bodyTail.match(/已思考\s*\d+\s*(?:秒|分钟|[sm]\b)|Thought\s+for\s+\d+\s*(?:seconds?|minutes?|[smh]\b)/gi) || [];
    } catch (e) { thinkingDoneAll = []; }
    const thinkingDoneCount = thinkingDoneAll.length;
    const thinkingDoneText = thinkingDoneAll.join('|');

    let genState = 'unknown';
    try {
        const STOP_RE = /(停止|停止生成|中止|stop|stop generating|abort)/i;
        const SEND_RE = /(发送|send|语音|voice|continue|继续)/i;
        let stopBtn = null, sendBtn = null;
        const btns = document.querySelectorAll('button, [role="button"], [data-testid]');
        for (const b of btns) {
            const r = b.getBoundingClientRect();
            if (r.width < 8 || r.height < 8) continue;
            if (r.bottom < window.innerHeight * 0.45) continue;
            const lab = ((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('title')||'')
                +' '+(b.getAttribute('data-testid')||'')+' '+(b.getAttribute('data-state')||'')).trim();
            if (STOP_RE.test(lab)) { stopBtn = b; break; }
            if (!sendBtn && SEND_RE.test(lab)) sendBtn = b;
        }
        if (!stopBtn) {
            const cands = document.querySelectorAll('button svg, [role="button"] svg');
            for (const svg of cands) {
                const host = svg.closest('button, [role="button"]');
                if (!host) continue;
                const r = host.getBoundingClientRect();
                if (r.width < 8 || r.height < 8) continue;
                if (r.bottom < window.innerHeight * 0.45) continue;
                if (r.right < window.innerWidth * 0.5) continue;
                const hasRect = svg.querySelector('rect');
                const hasOnlyRect = hasRect && svg.querySelectorAll('path, line, polyline, polygon').length === 0;
                if (hasOnlyRect) { stopBtn = host; break; }
            }
        }
        if (stopBtn) { genState = 'generating'; }
        else {
            const ta = document.querySelector('textarea, [contenteditable="true"], [role="textbox"]');
            const taVisible = ta && ta.getBoundingClientRect && ta.getBoundingClientRect().height > 0;
            if (sendBtn || taVisible) genState = 'idle';
        }
    } catch (e) { genState = 'unknown'; }

    const selectors = ['[class*="markdown"]','[class*="prose"]','[class*="message-content"]',
        '[class*="msg-content"]','[class*="assistant"]','[class*="response"]',
        '[class*="reply-content"]','[class*="answer"]','[data-message-author-role="assistant"]'];
    const candidates = [];
    for (const sel of selectors) {
        let els; try { els = document.querySelectorAll(sel); } catch(e) { continue; }
        for (const el of els) {
            const r = el.getBoundingClientRect();
            const t = (el.innerText || '').trim();
            if (r.width > 200 && t.length > 30)
                candidates.push({ text: t, bottom: r.bottom, length: t.length, selector: sel });
        }
    }
    if (candidates.length > 0) {
        candidates.sort((a,b)=>b.bottom-a.bottom);
        const topY = candidates[0].bottom;
        const near = candidates.filter(c => topY - c.bottom < 200);
        near.sort((a,b)=>b.length-a.length);
        return { chosen: near[0], totalCandidates: candidates.length,
                 hasThinkingIndicator, hasLooseThinking, thinkingDoneCount, thinkingDoneText, genState };
    }
    if (hasThinkingIndicator || hasLooseThinking) {
        return { chosen: null, hasThinkingIndicator: true, hasLooseThinking,
                 thinkingDoneCount, thinkingDoneText, genState, status: 'thinking' };
    }
    let best = null;
    for (const el of document.querySelectorAll('div, article, section')) {
        const r = el.getBoundingClientRect();
        if (r.height < 50 || r.width < 200) continue;
        if (r.x < window.innerWidth * 0.15 || r.x > window.innerWidth * 0.85) continue;
        const t = (el.innerText || '').trim();
        if (t.length > 100 && (!best || r.bottom > best.bottom))
            best = { text: t, bottom: r.bottom, length: t.length, selector: 'fallback-div' };
    }
    return { chosen: best, hasThinkingIndicator, hasLooseThinking,
             thinkingDoneCount, thinkingDoneText, genState };
}"""


class _Stuck(Exception):
    """对应参考代码里 e.code === 'STUCK'：卡死，可换卡重试。"""
    pass


# ─────────────── 单例 worker + 对外薄封装 ───────────────
_WORKER = None
_WORKER_LOCK = threading.Lock()


def _worker():
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is None:
            _WORKER = _WebWorker()
        return _WORKER


def set_logger(fn):
    _worker().set_logger(fn)


def web_complete(prompt, on_progress=None, **opts):
    """同步阻塞：把 prompt 发给网页 ChatGPT，返回回复纯文本。"""
    if not is_available():
        raise RuntimeError("Playwright 未安装：pip install playwright && python -m playwright install chromium")
    return _worker().submit("web_complete",
                            {"prompt": prompt, "on_progress": on_progress, **opts})


def test_login(on_progress=None):
    if not is_available():
        return {"ok": False, "error": "Playwright 未安装"}
    return _worker().submit("test_login", {"on_progress": on_progress}, timeout=180)


def get_state():
    try:
        return _worker().get_state()
    except Exception as e:
        return {"state": "idle", "available": is_available(), "error": str(e)}
