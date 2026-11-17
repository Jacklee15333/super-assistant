"""
web_model.py — 「伪模型」核心：用 Playwright 操作 sorryios.ai 的网页 ChatGPT。

★ 2026-11 适配改版：站点从 /pastel 迁到 /laike，登录页新增「同意用户协议」勾选框，
  登录后不一定直接落在卡片列表。现在：站点路径可配置（sitePath）并自动回退，
  登录后自动寻找卡片列表并记住其地址，任何一步失败都会把截图+页面结构存到
  memory/web_model_diag/ 便于下次快速对照修复。

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
SITE_ORIGIN = "https://sorryios.ai"
DEFAULT_SITE_PATH = "laike"              # 2026-11 起的新路径；老路径 pastel 作为自动回退
KNOWN_SITE_PATHS = ["laike", "pastel"]


def _site_base(path):
    return "%s/%s" % (SITE_ORIGIN, (path or DEFAULT_SITE_PATH).strip("/"))


def _login_url_for(path):
    return _site_base(path) + "#/login"


def _carlist_url_for(path):
    return _site_base(path) + "#/carlist"


# 兼容旧代码的模块级常量（实际运行时用 worker 上的 self._login_url / self._carlist_url）
LOGIN_URL = _login_url_for(DEFAULT_SITE_PATH)
CARLIST_URL = _carlist_url_for(DEFAULT_SITE_PATH)

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
CONFIG_PATH = MEMORY_DIR / "web_model.json"
SESSION_PATH = MEMORY_DIR / "web_session.json"
SESSION_TTL_DAYS = 7
ROUTES_PATH = MEMORY_DIR / "web_model_routes.json"   # 自动学到的卡片列表地址
DIAG_DIR = MEMORY_DIR / "web_model_diag"             # 失败时的截图 + 页面结构
DIAG_KEEP = 10

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
        "sitePath": DEFAULT_SITE_PATH,   # 网站路径：sorryios.ai/<sitePath>#/login，改版时改这里
        "serviceName": "ChatGPT",        # 登录后若先进「选服务」页，点这个名字进入卡片列表
        # 每个新任务怎么开始：card＝回首页换一张新的 AI 卡（最干净，默认）；chat＝同一张卡上开新聊天（更快）
        "newTaskMode": "card",
        # 分析类任务（视频总结/思维导图）用哪个模型：留空＝自动选菜单里最高级的；
        # 也可以填模型名里的关键字固定下来，比如 "Pro"、"High"、"Thinking"
        "preferredModel": "",
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


def _load_routes():
    try:
        return json.loads(ROUTES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_routes(routes):
    try:
        ROUTES_PATH.write_text(json.dumps(routes, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    except Exception:
        pass


def _clear_session():
    try:
        if SESSION_PATH.exists():
            SESSION_PATH.unlink()
    except Exception:
        pass


# 不用鼠标、不需要窗口在前台，直接把文字写进输入框：
#   · textarea/input：用原生 setter 写值再发 input 事件（React 认得）；
#   · contenteditable（新版 ChatGPT 的 ProseMirror）：选中全部内容后派发一个「粘贴」事件，
#     编辑器自己会把文字插进去；编辑器没接住时再用 execCommand('insertText') 兜底。
_DOM_FILL_JS = r"""(el, text) => {
    try { el.focus({preventScroll: true}); } catch (e) { try { el.focus(); } catch (e2) {} }
    const tag = (el.tagName || '').toUpperCase();
    if (tag === 'TEXTAREA' || tag === 'INPUT') {
        const proto = tag === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        return 'value';
    }
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    sel.removeAllRanges(); sel.addRange(range);
    try {
        const dt = new DataTransfer();
        dt.setData('text/plain', text);
        const ev = new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true});
        el.dispatchEvent(ev);
        if (ev.defaultPrevented) return 'paste';
    } catch (e) {}
    return document.execCommand('insertText', false, text) ? 'insertText' : '';
}"""


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
        self._site_path = DEFAULT_SITE_PATH
        self._service_name = "ChatGPT"
        self._login_url = LOGIN_URL
        self._carlist_url = CARLIST_URL
        self._landing_url = ""
        self._chat_epoch = 0      # 每进入一个全新的网页对话线程 +1（客户端据此判断能否发增量）
        self._chat_used = True    # 当前对话里是否已经发过东西（刚换卡/开新聊天后为 False）
        self._best_epoch = -1     # 在哪个对话线程上已经切过最高级模型

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
                          # 窗口被别的程序挡住/最小化时也照常渲染，不然页面「冻住」，
                          # 点击和发送会一直等，非得把鼠标移回浏览器才继续
                          "--disable-background-timer-throttling",
                          "--disable-backgrounding-occluded-windows",
                          "--disable-renderer-backgrounding",
                          "--disable-features=CalculateNativeWinOcclusion",
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
        self._resolve_routes(cfg)
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
                    self._log("尝试复用 session → " + self._carlist_url)
                    self._page.goto(self._carlist_url, wait_until="domcontentloaded",
                                    timeout=20000)
                    if self._wait_for_cards(8):
                        self._log("✓ session 复用成功，跳过登录")
                        need_login = False
                    else:
                        self._log("session 已失效或卡片页地址变了 → 走完整登录")
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
        except Exception as e:
            self._state = "error"
            self._dump_diag("start", e)
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

    # ---- 站点路径 / 卡片列表地址 ----
    def _resolve_routes(self, cfg):
        self._site_path = (cfg.get("sitePath") or DEFAULT_SITE_PATH).strip("/")
        self._service_name = (cfg.get("serviceName") or "ChatGPT").strip()
        self._login_url = _login_url_for(self._site_path)
        routes = _load_routes()
        if routes.get("sitePath") == self._site_path and routes.get("carlistUrl"):
            self._carlist_url = routes["carlistUrl"]
        else:
            self._carlist_url = _carlist_url_for(self._site_path)
        self._log("站点路径=%s 登录页=%s 卡片页=%s"
                  % (self._site_path, self._login_url, self._carlist_url))

    def _learn_carlist(self, url):
        url = (url or "").strip()
        if not url or "login" in url:
            return
        if url != self._carlist_url:
            self._log("记住卡片列表地址: " + url)
        self._carlist_url = url
        _save_routes({"sitePath": self._site_path, "carlistUrl": url,
                      "learnedAt": time.strftime("%Y-%m-%d %H:%M:%S")})

    _PAGE_STATUS_JS = r"""() => {
        const url = window.location.href;
        const vis = el => { const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
        const hasPasswordInput = [...document.querySelectorAll('input[type="password"]')].some(vis);
        const bt = document.body ? (document.body.innerText || '') : '';
        const hasCardListMarkers =
            ((bt.includes('空闲') || bt.includes('繁忙') || bt.includes('正常')) &&
             (bt.includes('TEAM') || bt.includes('PLUS') || bt.includes('Plus') || bt.includes('PRO')))
            || /[A-Z]{2}\d{4}-\d{2}/.test(bt);
        return { url, hasPasswordInput, hasCardListMarkers,
                 isLoginPage: url.includes('/login') || hasPasswordInput };
    }"""

    def _page_status(self):
        return self._safe(lambda: self._page.evaluate(self._PAGE_STATUS_JS),
                          {"url": "", "hasPasswordInput": False,
                           "hasCardListMarkers": False, "isLoginPage": False})

    def _wait_for_cards(self, timeout_sec=8):
        end = time.time() + timeout_sec
        self._dismiss_popups(min(1.5, timeout_sec))   # 弹窗会挡住卡片点击，先关掉
        while True:
            st = self._page_status()
            if st.get("hasCardListMarkers") and not st.get("isLoginPage"):
                return True
            if time.time() >= end:
                return False
            time.sleep(0.8)

    def _adopt_new_page(self, before_count):
        """点击后如果弹出了新标签页，就切过去（很多聚合站点会新开标签进聊天）。"""
        try:
            pages = self._context.pages
            if len(pages) > before_count:
                newp = pages[-1]
                try:
                    newp.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                self._safe(lambda: newp.set_default_timeout(8000))
                self._page = newp
                self._log("检测到新标签页，已切换: " + (newp.url or ""))
                return True
        except Exception:
            pass
        return False

    def _click_text(self, text):
        """点击页面上包含 text 的、尽量小的可见可点元素。返回是否点到。"""
        coords = self._safe(lambda: self._page.evaluate(r"""(text) => {
            const cands = [];
            for (const el of document.querySelectorAll('a,button,[role="button"],[role="tab"],[role="menuitem"],li,div,span')) {
                const t = (el.innerText || '').trim();
                if (!t || !t.includes(text) || t.length > text.length + 40) continue;
                const r = el.getBoundingClientRect();
                if (r.width < 8 || r.height < 8 || r.bottom < 0 || r.top > window.innerHeight) continue;
                const clickable = el.matches('a,button,[role="button"],[role="tab"],[role="menuitem"]') ||
                                  getComputedStyle(el).cursor === 'pointer';
                cands.push({ area: r.width * r.height, clickable,
                             cx: Math.round(r.x + r.width / 2), cy: Math.round(r.y + r.height / 2) });
            }
            if (!cands.length) return null;
            cands.sort((a, b) => (b.clickable - a.clickable) || (a.area - b.area));
            return cands[0];
        }""", text), None)
        if not coords:
            return False
        self._page.mouse.click(coords["cx"], coords["cy"])
        return True

    # 公告/提示弹窗按钮：优先「今日不再提示」（当天不再弹），其次「知道了」等
    _POPUP_BTN_TEXTS = ["今日不再提示", "今天不再提示", "不再提示", "知道了", "我知道了",
                        "我已知晓", "关闭公告", "关闭"]
    _POPUP_JS = r"""(texts) => {
        const norm = s => (s || '').replace(/\s+/g, '');
        for (const want of texts) {
            for (const b of document.querySelectorAll('button,[role="button"],a,span,div')) {
                if (norm(b.innerText) !== want) continue;
                const r = b.getBoundingClientRect();
                if (r.width < 10 || r.height < 10 || r.bottom < 0 || r.top > window.innerHeight) continue;
                const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
                // 必须是最上层（真正浮在页面上的弹窗按钮，不是被遮住的普通元素）
                const top = document.elementFromPoint(cx, cy);
                if (!top || !(top === b || b.contains(top) || top.contains(b))) continue;
                return { text: want, cx: Math.round(cx), cy: Math.round(cy) };
            }
        }
        return null;
    }"""

    def _dismiss_popups(self, wait_sec=2.0):
        """关掉网页打开时弹出的公告提示框（如「注册即可免费试用…」→ 知道了）。
        会先等 wait_sec 秒让弹窗出现（多数有延迟/动画），最多连关 3 个。返回关掉的个数。"""
        closed = 0
        end = time.time() + wait_sec
        while closed < 3:
            hit = self._safe(lambda: self._page.evaluate(self._POPUP_JS,
                                                         self._POPUP_BTN_TEXTS), None)
            if not hit:
                if time.time() >= end:
                    break
                time.sleep(0.4)
                continue
            self._page.mouse.click(hit["cx"], hit["cy"])
            closed += 1
            self._log("关闭弹窗提示：点击「%s」" % hit["text"])
            time.sleep(0.8)
            end = time.time() + 0.8      # 关掉一个后再看一眼有没有下一个
        return closed

    def _goto_carlist(self):
        """去卡片列表页。依次尝试：当前页 → 记住的/默认地址 → 「选服务」页里点服务名。"""
        if self._wait_for_cards(1):
            self._learn_carlist(self._page.url)
            return True
        # 刚登录完落在「选服务」页：先在当前页找服务入口，省一次跳转
        if self._try_service_entry():
            return True
        tried = []
        for url in (self._carlist_url, _carlist_url_for(self._site_path)):
            if url in tried:
                continue
            tried.append(url)
            self._log("打开卡片列表 " + url)
            self._safe(lambda u=url: self._page.goto(u, wait_until="domcontentloaded",
                                                     timeout=30000))
            if self._wait_for_cards(10):
                self._learn_carlist(self._page.url)
                return True
            if self._page_status().get("isLoginPage"):
                return False      # 交给上层处理重新登录
        # 新平台是多服务聚合（ChatGPT/Claude/Gemini…），可能要先选服务
        seen = set()
        for url in (self._landing_url, _site_base(self._site_path) + "#/",
                    _site_base(self._site_path) + "/#/"):
            if not url or url in seen or "/login" in url:
                continue
            seen.add(url)
            self._safe(lambda u=url: self._page.goto(u, wait_until="domcontentloaded",
                                                     timeout=30000))
            time.sleep(2)
            if self._page_status().get("isLoginPage"):
                return False
            if self._wait_for_cards(1) or self._try_service_entry():
                self._learn_carlist(self._page.url)
                return True
        self._log("⚠ 没找到卡片列表页（当前 %s）" % self._page.url)
        return False

    def _try_service_entry(self):
        """在当前页点服务名（默认 ChatGPT）进入卡片列表。"""
        before = len(self._context.pages)
        if not self._click_text(self._service_name):
            return False
        self._log("点击服务入口「%s」" % self._service_name)
        time.sleep(2)
        self._adopt_new_page(before)
        if self._wait_for_cards(12):
            self._learn_carlist(self._page.url)
            return True
        return False

    # ---- 登录 ----
    _AGREE_JS = r"""() => {
        const kw = /(阅读|同意).{0,12}(协议|条款|政策|声明)|agree|terms/i;
        const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        const near = el => { let n = el;
            for (let i = 0; i < 5 && n; i++) { n = n.parentElement;
                if (n && kw.test(n.innerText || '')) return true; }
            return false; };
        // 1) 原生 checkbox（多数 UI 库会把它藏起来，要点它旁边的可视方框）
        for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
            if (!near(cb)) continue;
            let target = cb;
            const cs = getComputedStyle(cb);
            if (!vis(cb) || cs.opacity === '0' || cs.visibility === 'hidden')
                target = cb.nextElementSibling && vis(cb.nextElementSibling)
                         ? cb.nextElementSibling : cb.parentElement;
            const r = target.getBoundingClientRect();
            return { found: true, checked: cb.checked,
                     cx: Math.round(r.x + Math.min(r.width, 24) / 2), cy: Math.round(r.y + r.height / 2) };
        }
        // 2) 自绘 checkbox
        for (const el of document.querySelectorAll('[role="checkbox"],[class*="checkbox"]')) {
            if (!vis(el) || !near(el)) continue;
            const checked = el.getAttribute('aria-checked') === 'true' ||
                            /(^|\s|-)(is-)?checked(\s|$)/.test(el.className || '');
            const r = el.getBoundingClientRect();
            return { found: true, checked,
                     cx: Math.round(r.x + Math.min(r.width, 24) / 2), cy: Math.round(r.y + r.height / 2) };
        }
        return { found: false };
    }"""

    def _ensure_agreement_checked(self):
        """勾选「我已阅读并同意《用户服务协议》」。只点方框，避免点到协议链接弹窗。"""
        info = self._safe(lambda: self._page.evaluate(self._AGREE_JS), {"found": False})
        if not info.get("found"):
            self._log("未发现协议勾选框（可能不需要）")
            return
        if info.get("checked"):
            self._log("协议已勾选")
            return
        self._page.mouse.click(info["cx"], info["cy"])
        time.sleep(0.4)
        info = self._safe(lambda: self._page.evaluate(self._AGREE_JS), {"found": False})
        if not info.get("checked"):
            # 兜底：直接 check 原生 input
            self._safe(lambda: self._page.locator('input[type="checkbox"]').first.check(
                force=True, timeout=3000))
            time.sleep(0.3)
            info = self._safe(lambda: self._page.evaluate(self._AGREE_JS), {"found": False})
        self._dismiss_agreement_dialog()
        self._log("协议勾选" + ("成功" if info.get("checked") else "可能未成功（继续尝试登录）"))

    def _dismiss_agreement_dialog(self):
        """若弹出了协议/提示弹窗，点里面的「同意/确定」按钮。返回是否点了。"""
        return bool(self._safe(lambda: self._page.evaluate(r"""() => {
            const dlgs = document.querySelectorAll('[role="dialog"],[class*="modal"],[class*="dialog"],[class*="popup"]');
            for (const d of dlgs) {
                const r = d.getBoundingClientRect();
                if (r.width < 50 || r.height < 50) continue;
                for (const b of d.querySelectorAll('button,[role="button"],a')) {
                    const t = (b.innerText || '').trim();
                    const br = b.getBoundingClientRect();
                    if (br.width > 0 && /同意|确定|确认|我知道了|Agree|OK/i.test(t) && !/不同意|取消/.test(t)) {
                        b.click(); return true;
                    }
                }
            }
            return false;
        }"""), False))

    def _login_error_text(self):
        return self._safe(lambda: self._page.evaluate(r"""() => {
            const out = [];
            for (const el of document.querySelectorAll('[class*="message"],[class*="toast"],[class*="notification"],[class*="error"],[class*="alert"],[role="alert"]')) {
                const r = el.getBoundingClientRect();
                const t = (el.innerText || '').trim();
                if (r.width > 0 && r.height > 0 && t && t.length < 120 && !out.includes(t)) out.push(t);
            }
            return out.slice(0, 3).join(' / ');
        }"""), "") or ""

    def _open_login_page(self):
        paths = [self._site_path] + [p for p in KNOWN_SITE_PATHS if p != self._site_path]
        for p in paths:
            url = _login_url_for(p)
            self._log("打开登录页 " + url)
            self._safe(lambda u=url: self._page.goto(u, wait_until="domcontentloaded",
                                                     timeout=30000))
            try:
                self._page.wait_for_selector('input[type="password"]', state="visible",
                                             timeout=12000)
            except Exception:
                self._log("  该地址没有出现登录表单")
                continue
            if p != self._site_path:
                self._log("⚠ 配置的路径 /%s 不可用，自动改用 /%s（可在设置里改 sitePath）"
                          % (self._site_path, p))
                self._site_path = p
                self._carlist_url = _carlist_url_for(p)
            self._login_url = url
            return
        raise RuntimeError("打开登录页失败：%s 都没有出现密码框，sorryios.ai 可能又改版了"
                           % "、".join("/" + x for x in paths))

    def _do_login(self, cfg):
        self._open_login_page()
        time.sleep(0.5 + random.random() * 0.5)
        self._dismiss_popups(2.5)       # 登录页打开会弹「注册即可免费试用…」公告

        pwd = self._page.locator('input[type="password"]:visible').first
        user = self._page.locator(
            'input:not([type="password"]):not([type="checkbox"]):not([type="radio"])'
            ':not([type="hidden"]):not([type="submit"]):not([type="button"]):visible').first
        if not self._safe(lambda: user.count(), 0):
            raise RuntimeError("登录页找不到账号输入框，sorryios.ai 可能改版了")

        self._safe(lambda: user.focus()); time.sleep(0.3); user.fill("")
        self._human_type(user, cfg["aiUsername"])
        self._log("已输入账号")
        time.sleep(0.5)
        self._safe(lambda: pwd.focus()); time.sleep(0.3); pwd.fill("")
        self._human_type(pwd, cfg["aiPassword"])
        self._log("已输入密码")
        time.sleep(0.5)

        self._dismiss_popups(0.3)
        self._ensure_agreement_checked()
        time.sleep(0.3)

        btn = self._find_button_by_text("用户登录", "登录", "登 录", "Login", "Sign in")
        if btn:
            btn.click()
        else:
            pwd.press("Enter")
        self._log("已点击登录")

        deadline = time.time() + 20
        nudged = False
        while time.time() < deadline:
            time.sleep(1)
            st = self._page_status()
            if not st.get("isLoginPage"):
                self._log("✓ 登录成功，落地页 " + st.get("url", ""))
                self._landing_url = st.get("url", "")
                self._dismiss_popups(2.0)   # 登录后首页也可能弹公告
                break
            # 没勾协议时有的站会弹框「请先同意…」，点掉后再登一次
            if not nudged and time.time() > deadline - 16:
                nudged = True
                if self._dismiss_agreement_dialog():
                    self._log("点掉了协议提示弹窗，重新登录")
                    time.sleep(0.5)
                    self._ensure_agreement_checked()
                    btn = self._find_button_by_text("用户登录", "登录", "登 录", "Login", "Sign in")
                    if btn:
                        self._safe(lambda: btn.click())
        else:
            hint = self._login_error_text()
            raise RuntimeError("登录失败，仍停留在登录页" +
                               ("：" + hint if hint else "（账号密码错误，或页面又改版了）"))

        time.sleep(1.5)
        if not self._goto_carlist():
            raise RuntimeError("登录成功了，但找不到卡片列表页（页面结构可能变了，"
                               "诊断截图已保存到 memory/web_model_diag/）")

    # ════════════════════ 选卡 + 进聊天页 ════════════════════
    def _select_card_and_enter_chat(self):
        for attempt in range(3):
            try:
                self._select_random_card()
            except Exception as e:
                self._log("选卡异常: " + str(e))
            ready = self._wait_chat_page_ready(25)
            if ready is True:
                self._chat_epoch += 1
                self._chat_used = False
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
            self._safe(lambda: self._page.goto(self._carlist_url,
                       wait_until="domcontentloaded", timeout=30000))
            time.sleep(3)
        raise RuntimeError("选卡进入聊天页失败（已重试 3 次）")

    def _select_random_card(self):
        self._log("选 AI 卡片中...")
        if not self._goto_carlist():
            if self._page_status().get("isLoginPage"):
                return            # 交给 _wait_chat_page_ready 报 login_redirect → 重登
            raise RuntimeError("打不开卡片列表页")
        time.sleep(1.5 + random.random() * 1.5)
        self._dismiss_popups(0.5)

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
        before = len(self._context.pages)
        self._page.mouse.click(coords["cx"], coords["cy"])
        time.sleep(1.5)
        self._adopt_new_page(before)
        # ★ 鼠标停在原地，进了聊天页正好压在右下角的悬浮菜单上 → 菜单被悬停展开，
        #   它的半透明遮罩会挡住输入框（之前「卡住不发提示词」就是这个原因）。点完马上挪开。
        self._park_mouse()
        return True

    def _wait_chat_page_ready(self, timeout_sec=25):
        self._log("等聊天页就绪...")
        carlist_url = self._carlist_url
        start = time.time()
        last_log = 0
        while time.time() - start < timeout_sec:
            time.sleep(2)
            try:
                info = self._page.evaluate("""(carlistUrl) => {
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
                        isCarlist: url.includes('carlist') || url === carlistUrl,
                        isLoginPage: url.includes('/login') || hasPasswordInput,
                    };
                }""", carlist_url)
            except Exception:
                continue
            if info["isLoginPage"]:
                self._log("⚠ 选卡后被重定向到登录页，session 已失效")
                return "login_redirect"
            if (not info["isCarlist"]) and (info["inputCount"] > 0 or info["hasChatHint"]):
                self._log("✓ 聊天页就绪")
                time.sleep(4)     # 冷启动 hydration 缓冲
                self._park_mouse()
                self._close_overlays()
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
        if opts.get("newChat") and not opts.get("forceNewCard"):
            if not self._chat_used and not self._has_conversation():
                self._log("[新任务] 当前就是一个刚打开的空白对话，直接用")
            elif (load_config().get("newTaskMode") or "card") == "card":
                # 用户要求：每个新任务回首页换一张新的 AI，上一个任务的内容一点都带不进来
                self._log("[新任务] 回首页换一张新的 AI 卡")
                prog("新任务：回首页换一张新的 AI…")
                opts = dict(opts, forceNewCard=True)
            else:
                prog("开一个新对话…")
                if not self._new_chat():
                    self._log("[新对话] 页面上开不了新对话，改为回首页换卡")
                    opts = dict(opts, forceNewCard=True)

        if opts.get("forceNewCard"):
            self._log("[换卡] 回首页换一张新卡…")
            prog("换一张 AI 卡片…")
            self._safe(lambda: self._page.goto(self._carlist_url,
                       wait_until="domcontentloaded", timeout=30000))
            time.sleep(3)
            self._select_card_and_enter_chat()
            # 有的卡一进去是上次的对话：再开个新聊天，确保是空白的
            if self._has_conversation():
                self._new_chat()
            self._state = "ready"

        if opts.get("bestModel") and self._best_epoch != self._chat_epoch:
            prog("切换到最高级模型…")
            self._select_best_model()
            self._best_epoch = self._chat_epoch

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
                    self._safe(lambda: self._page.goto(self._carlist_url,
                               wait_until="domcontentloaded", timeout=30000))
                    time.sleep(3)
                    self._select_card_and_enter_chat()
                    continue
                raise
            except Exception as e:
                self._state = "ready"
                raise e
        raise last_err or RuntimeError("未知错误")

    _HAS_CONVO_JS = r"""() => {
        const sels = ['[data-message-author-role]', '[class*="markdown"]', '[class*="prose"]',
                      '[class*="message-content"]', '[class*="msg-content"]'];
        let n = 0;
        for (const s of sels) {
            for (const el of document.querySelectorAll(s)) {
                const r = el.getBoundingClientRect();
                if (r.width > 100 && r.height > 0 && (el.innerText || '').trim()) n++;
            }
        }
        return n;
    }"""

    def _has_conversation(self):
        return (self._safe(lambda: self._page.evaluate(self._HAS_CONVO_JS), 0) or 0) > 0

    def _new_chat(self):
        """在当前卡上开一个空白新对话，避免不同任务/请求的内容堆在同一个对话线程里互相干扰。
        成功返回 True（并让 chat_epoch +1）。"""
        if not self._page or self._page.is_closed():
            return False
        if not self._has_conversation():
            self._chat_epoch += 1          # 本来就是空对话
            return True

        def ok():
            for _ in range(10):
                time.sleep(0.6)
                if not self._has_conversation() and self._safe(lambda: self._page.evaluate(
                        "() => [...document.querySelectorAll('textarea,[contenteditable=\"true\"]')]"
                        ".some(e => e.getBoundingClientRect().width > 200)"), False):
                    self._chat_epoch += 1
                    self._chat_used = False
                    self._log("✓ 已开新对话")
                    time.sleep(1.0)
                    return True
            return False

        for sel in ('[data-testid="create-new-chat-button"]',
                    'a[aria-label*="New chat" i]', 'button[aria-label*="New chat" i]',
                    'a[aria-label*="新聊天"]', 'button[aria-label*="新聊天"]',
                    'a[aria-label*="新对话"]', 'button[aria-label*="新对话"]'):
            loc = self._page.locator(sel).first
            if self._safe(lambda: loc.count(), 0) and self._safe(lambda: loc.is_visible(), False):
                clicked = self._safe(lambda: (loc.evaluate("el => el.click()"), True)[1], False) \
                    or self._safe(lambda: (loc.click(timeout=3000), True)[1], False)
                if clicked and ok():
                    return True
        for txt in ("新聊天", "新对话", "New chat"):
            if self._click_text(txt) and ok():
                return True
        # ChatGPT 的「新聊天」快捷键
        self._safe(lambda: self._page.keyboard.press("Control+Shift+O"))
        if ok():
            return True
        self._log("⚠ 没能开新对话（找不到「新聊天」入口）")
        return False

    # ──────────── 切换到最高级模型（分析类任务用）────────────
    _MODEL_BTN_JS = r"""() => {
        const re = /(\b\d+(\.\d+)?\b|instant|mini|low|medium|high|pro|thinking|auto|heavy|extended|light|standard|即时|思考|专业|标准|进阶)/i;
        const ins = [...document.querySelectorAll('textarea,[contenteditable="true"]')]
            .filter(e => e.getBoundingClientRect().width > 200);
        let scope = ins.length ? (ins[ins.length - 1].closest('form') || ins[ins.length - 1].parentElement) : null;
        for (let i = 0; i < 5 && scope && scope.parentElement && scope.querySelectorAll('button').length < 3; i++)
            scope = scope.parentElement;
        const cands = [];
        const consider = (b, bonus) => {
            const r = b.getBoundingClientRect();
            const t = (b.innerText || '').trim().split('\n')[0];
            const al = b.getAttribute('aria-label') || '';
            if (r.width === 0 || r.height === 0) return;
            if (/发送|send|附件|attach|语音|voice|dictat|上传|upload|麦克风|mic/i.test(t + ' ' + al)) return;
            if (!(re.test(t) || /model|模型/i.test(al))) return;
            if (t.length > 30) return;
            const pop = b.hasAttribute('aria-haspopup') || b.hasAttribute('aria-expanded');
            cands.push({b, t, score: bonus + (pop ? 5 : 0) + (b.querySelector('svg') ? 1 : 0)});
        };
        document.querySelectorAll('[data-testid*="model-switcher"],[data-testid*="model-picker"],button[aria-label*="模型"],button[aria-label*="model" i]')
            .forEach(b => consider(b, 10));
        if (scope) scope.querySelectorAll('button,[role="button"]').forEach(b => consider(b, 3));
        document.querySelectorAll('[data-cx-model-btn]').forEach(e => e.removeAttribute('data-cx-model-btn'));
        if (!cands.length) return null;
        cands.sort((a, b) => b.score - a.score);
        cands[0].b.setAttribute('data-cx-model-btn', '1');
        return cands[0].t || (cands[0].b.getAttribute('aria-label') || '');
    }"""

    _MODEL_MENU_JS = r"""() => {
        const els = [...document.querySelectorAll('[role="menuitem"],[role="menuitemradio"],[role="option"]')]
            .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        return els.map((e, i) => {
            e.setAttribute('data-cx-mi', String(i));
            const full = (e.innerText || '').trim().replace(/\s+\n/g, '\n');
            return {i, label: full.split('\n')[0].trim().slice(0, 60), full: full.replace(/\s+/g, ' ').slice(0, 90),
                    disabled: e.getAttribute('aria-disabled') === 'true' || e.hasAttribute('data-disabled'),
                    checked: e.getAttribute('aria-checked') === 'true' || e.getAttribute('data-state') === 'checked'
                             || e.getAttribute('aria-selected') === 'true',
                    sub: e.getAttribute('aria-haspopup') === 'menu' || e.hasAttribute('data-has-submenu')};
        });
    }"""

    @staticmethod
    def _model_rank(label):
        """给菜单里的模型/思考强度打分，越高越强。只看第一行名称，不看说明文字。"""
        import re as _re
        t = (label or "").lower()
        if not t or _re.search(r"upgrade|升级|unavailable|不可用|legacy|旧版|temporary|临时", t):
            return -1
        tiers = [(r"\bpro\b|专业", 100), (r"extra.?high|xhigh|heavy|\bmax\b|extended|极高|超高|深度", 90),
                 (r"\bhigh\b|(?<!极|超)高", 80), (r"thinking|思考|reason|推理", 70),
                 (r"medium|standard|标准|中", 50), (r"\bauto\b|自动", 40),
                 (r"\blow\b|light|低|轻", 20), (r"instant|mini|fast|nano|即时|极速|快", 10)]
        score = 0
        for pat, sc in tiers:
            if _re.search(pat, t):
                score = max(score, sc)
        nums = [float(x) for x in _re.findall(r"(\d+(?:\.\d+)?)", t) if float(x) < 50]
        return score + (max(nums) if nums else 0) / 10.0       # 同档位里版本号大的优先

    _SLIDER_JS = r"""() => {
        const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        document.querySelectorAll('[data-cx-slider]').forEach(e => e.removeAttribute('data-cx-slider'));
        const out = [];
        for (const s of document.querySelectorAll('[role="slider"], input[type="range"]')) {
            if (!vis(s)) continue;
            const rg = s.tagName === 'INPUT';
            const num = (v, d) => { const x = parseFloat(v); return isNaN(x) ? d : x; };
            s.setAttribute('data-cx-slider', String(out.length));
            out.push({i: out.length, range: rg,
                      min: num(rg ? s.min : s.getAttribute('aria-valuemin'), 0),
                      max: num(rg ? s.max : s.getAttribute('aria-valuemax'), 100),
                      now: num(rg ? s.value : s.getAttribute('aria-valuenow'), 0),
                      step: num(rg ? s.step : null, 1),
                      text: s.getAttribute('aria-valuetext') || ''});
        }
        return out;
    }"""

    _DOM_CLICK_JS = r"""(sel) => {
        const b = document.querySelector(sel); if (!b) return false;
        for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'])
            b.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
                {bubbles: true, cancelable: true, button: 0, pointerType: 'mouse'}));
        return true;
    }"""

    def _menu_items(self):
        return self._safe(lambda: self._page.evaluate(self._MODEL_MENU_JS), []) or []

    def _sliders(self):
        return self._safe(lambda: self._page.evaluate(self._SLIDER_JS), []) or []

    def _dom_click(self, selector):
        """页面内触发一次完整点击（按下/抬起/click），不动你的真实鼠标、不需要窗口在前台。"""
        return bool(self._safe(lambda: self._page.evaluate(self._DOM_CLICK_JS, selector), False))

    def _open_model_menu(self):
        """打开聊天框里的模型 / 思考强度面板。先用页面内事件，不行再用虚拟鼠标点一下。"""
        for how in ("dom", "click"):
            if how == "dom":
                self._dom_click('[data-cx-model-btn="1"]')
            else:
                self._safe(lambda: self._page.locator('[data-cx-model-btn="1"]').first.click(timeout=4000))
            for _ in range(8):
                time.sleep(0.25)
                if self._menu_items() or self._sliders():
                    return True
        return False

    def _slider_now(self, i):
        return next((x for x in self._sliders() if x["i"] == i), None)

    def _slider_to_max(self, sl):
        """把「思考强度」滑块拉到最右（最强）。依次试：页面内 End 键 → 键盘 End/→ → 点轨道最右端。"""
        sel = '[data-cx-slider="%d"]' % sl["i"]
        if sl["range"]:
            self._safe(lambda: self._page.evaluate("""(sel) => {
                const s = document.querySelector(sel);
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(s, s.max);
                s.dispatchEvent(new Event('input', {bubbles: true}));
                s.dispatchEvent(new Event('change', {bubbles: true}));
            }""", sel))
        else:
            self._safe(lambda: self._page.evaluate("""(sel) => {
                const s = document.querySelector(sel); s.focus();
                s.dispatchEvent(new KeyboardEvent('keydown', {key: 'End', code: 'End', bubbles: true, cancelable: true}));
            }""", sel))
        time.sleep(0.3)
        cur = self._slider_now(sl["i"])
        if cur and cur["now"] >= cur["max"]:
            return cur
        loc = self._page.locator(sel).first
        self._safe(lambda: loc.press("End", timeout=3000))      # 键盘事件只发给这个页面
        time.sleep(0.3)
        cur = self._slider_now(sl["i"])
        if cur and cur["now"] >= cur["max"]:
            return cur
        steps = int(max(1, (sl["max"] - sl["now"]) / max(sl["step"] or 1, 1e-6))) + 1
        for _ in range(min(steps, 50)):
            self._safe(lambda: loc.press("ArrowRight", timeout=2000))
        time.sleep(0.3)
        cur = self._slider_now(sl["i"])
        if cur and cur["now"] >= cur["max"]:
            return cur
        # 最后一招：在滑轨最右端点一下（虚拟鼠标，不会移动你的真实鼠标）
        box = self._safe(lambda: self._page.evaluate("""(sel) => {
            const s = document.querySelector(sel);
            let t = s.closest('[data-orientation]') || s.parentElement;
            for (let k = 0; k < 3 && t && t.getBoundingClientRect().width < 80; k++) t = t.parentElement;
            const r = (t || s).getBoundingClientRect(); return {x: r.right - 3, y: r.top + r.height / 2};
        }""", sel))
        if box:
            self._safe(lambda: self._page.mouse.click(box["x"], box["y"]))
            time.sleep(0.3)
        return self._slider_now(sl["i"])

    @staticmethod
    def _has_effort(label):
        import re as _re
        return bool(_re.search(r"instant|mini|\blow\b|medium|\bhigh\b|\bpro\b|thinking|auto|heavy|extended|"
                               r"light|standard|即时|思考|专业|标准|极高|超高|高|中|低", (label or "").lower()))

    @staticmethod
    def _version(label):
        import re as _re
        nums = [float(x) for x in _re.findall(r"(\d+(?:\.\d+)?)", label or "") if float(x) < 50]
        return max(nums) if nums else None

    def _panel_head(self):
        """面板标题行，如「6 Medium」「6 High」：带版本号又带强度词的那一项。"""
        return next((it["label"] for it in self._menu_items()
                     if self._version(it["label"]) is not None and self._has_effort(it["label"])), "")

    def _select_best_model(self):
        """分析类任务开始前，把 AI 池切到最高级：
          ① 模型：选版本号最高的（或配置 preferredModel 指定的）；
          ② 思考强度：有滑块就拉到最右；是选项列表就选最强的一项。
        找不到就保持原样继续，不影响任务；每一步都写日志，方便对照修。"""
        try:
            self._close_overlays()
            btn = self._safe(lambda: self._page.evaluate(self._MODEL_BTN_JS), None)
            if not btn:
                self._log("[模型] 没找到聊天框里的模型/思考强度按钮，按页面默认继续")
                return False
            if not self._open_model_menu():
                self._log("[模型] 点了「%s」但没弹出面板，按默认继续" % btn)
                return False
            items = self._menu_items()
            head = self._panel_head()
            self._log("[模型] 按钮「%s」，当前「%s」，选项：%s，滑块：%d 个" % (
                btn, head or "-", " / ".join(("✓" if it["checked"] else "") + it["label"]
                                             for it in items if it["label"]) or "-", len(self._sliders())))
            want = (load_config().get("preferredModel") or "").strip().lower()

            # ① 模型：只看「不带强度词」的选项（如「6」「GPT-5.6 Sol」），默认挑版本号最高的
            models = [it for it in items if it["label"] and not it["disabled"]
                      and not self._has_effort(it["label"]) and self._model_rank(it["label"]) >= 0]
            pick = None
            if want:
                pick = next((it for it in models if want in it["label"].lower()), None)
            if not pick and models:
                pick = max(models, key=lambda it: (self._version(it["label"]) or 0, it["checked"]))
            if pick and not pick["checked"]:
                self._dom_click('[data-cx-mi="%d"]' % pick["i"])
                time.sleep(0.6)
                self._log("[模型] 选模型「%s」" % pick["label"])
                if not (self._menu_items() or self._sliders()):     # 选完面板关了：重新打开
                    self._open_model_menu()

            # ② 思考强度
            done = ""
            sliders = self._sliders()
            if sliders:
                sl = sliders[0]
                cur = self._slider_to_max(sl)
                if cur:
                    done = "思考强度滑块 %g→%g（最大 %g）%s" % (
                        sl["now"], cur["now"], cur["max"],
                        "，已拉满" if cur["now"] >= cur["max"] else "，⚠ 没能拉满")
            else:
                items = self._menu_items()
                efforts = [it for it in items if it["label"] and not it["disabled"]
                           and self._has_effort(it["label"]) and self._model_rank(it["label"]) >= 0]
                pure = [it for it in efforts if self._version(it["label"]) is None]
                combos = [it for it in efforts if self._version(it["label"]) is not None]
                cands = pure or (combos if len(combos) >= 2 else [])    # 只有一个「6 Medium」是标题，不算选项
                if want:
                    cands = [it for it in cands if want in it["label"].lower()] or cands
                if cands:
                    best = max(cands, key=lambda it: self._model_rank(it["label"]))
                    if not best["checked"]:
                        self._dom_click('[data-cx-mi="%d"]' % best["i"])
                        time.sleep(0.5)
                    done = "思考强度选「%s」" % best["label"]
            after = self._panel_head()
            if self._menu_items() or self._sliders():
                self._safe(lambda: self._page.keyboard.press("Escape"))
                time.sleep(0.2)
            self._log("[模型] 完成：%s；当前「%s」" % (done or "没有可调的思考强度", after or head or btn))
            return True
        except Exception as e:
            self._log("[模型] 切换出错（%s），按默认继续" % str(e)[:80])
            return False

    def _park_mouse(self):
        """把鼠标挪到页面左上方的空白处，免得悬停触发右下角的悬浮菜单。"""
        try:
            vp = self._page.viewport_size or {"width": 1280, "height": 900}
            self._page.mouse.move(int(vp["width"] * 0.45), 70)
        except Exception:
            pass

    _OVERLAY_OPEN_JS = r"""() => [...document.querySelectorAll(
        '.radial-menu-backdrop.open, #main-menu-backdrop.open')].filter(e => {
            const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }).length"""

    def _close_overlays(self):
        """关掉 AI 池页面上展开的悬浮菜单（右下角齿轮那一圈按钮）。它展开时会盖一层
        半透明遮罩，挡住输入框和发送键。返回是否处理过。"""
        if not (self._safe(lambda: self._page.evaluate(self._OVERLAY_OPEN_JS), 0) or 0):
            return False
        self._log("检测到悬浮菜单展开（遮挡输入框），正在关闭…")
        self._park_mouse()
        # 1) 点遮罩本身（一般就是「点空白处关闭」）
        self._safe(lambda: self._page.evaluate(r"""() => {
            for (const b of document.querySelectorAll('.radial-menu-backdrop.open, #main-menu-backdrop.open'))
                b.dispatchEvent(new MouseEvent('click', {bubbles: true}));
        }"""))
        time.sleep(0.4)
        # 2) 还开着就按 Esc
        if self._safe(lambda: self._page.evaluate(self._OVERLAY_OPEN_JS), 0):
            self._safe(lambda: self._page.keyboard.press("Escape"))
            time.sleep(0.4)
        # 3) 仍然开着：直接让遮罩失效（不影响页面其它功能）
        if self._safe(lambda: self._page.evaluate(self._OVERLAY_OPEN_JS), 0):
            self._safe(lambda: self._page.evaluate(r"""() => {
                for (const b of document.querySelectorAll('.radial-menu-backdrop, #main-menu-backdrop')) {
                    b.classList.remove('open'); b.style.pointerEvents = 'none';
                }
                for (const c of document.querySelectorAll('.radial-menu-container, #main-menu-container'))
                    c.classList.remove('open');
            }"""))
        return True

    def _focus_input(self, inp):
        """聚焦输入框：正常点击 → 关遮挡后再点 → 强制点击 → JS focus，一级级兜底。"""
        try:
            inp.click(timeout=3000)
            return
        except Exception as e:
            self._log("点输入框被挡住（%s），关遮挡后重试" % str(e).split("\n")[0][:80])
        self._close_overlays()
        try:
            inp.click(timeout=3000)
            return
        except Exception:
            pass
        try:
            inp.click(timeout=3000, force=True)
            return
        except Exception:
            pass
        inp.evaluate("el => { el.focus(); }")

    # 本次提问之后的那条助手回复（按页面顺序定位在「我刚发的提问气泡」后面），
    # 用来校验抓到的回复确实属于本次任务，而不是对话里更早的内容。
    _ANCHORED_REPLY_JS = r"""(head) => {
        const norm = s => (s || '').replace(/[\s\u00a0]+/g, '');
        const key = norm(head).slice(0, 30);
        const users = [...document.querySelectorAll('[data-message-author-role="user"]')];
        if (!users.length) return {found: false};
        let anchor = null;
        for (let i = users.length - 1; i >= 0; i--) {
            if (key && norm(users[i].innerText).includes(key)) { anchor = users[i]; break; }
        }
        if (!anchor) return {found: false};
        const outs = [];
        for (const a of document.querySelectorAll('[data-message-author-role="assistant"]')) {
            if (anchor.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING) {
                const t = (a.innerText || '').trim();
                if (t) outs.push(t);
            }
        }
        return {found: true, text: outs.join('\n\n')};
    }"""

    def _anchored_reply(self, prompt):
        return self._safe(lambda: self._page.evaluate(self._ANCHORED_REPLY_JS, prompt or ""),
                          {"found": False}) or {"found": False}

    def _wait_anchored_stable(self, prompt, timeout_sec, prog=None):
        """等「本次提问之后的回复」出现并且连续几秒不再变化，返回它的文字。"""
        end = time.time() + timeout_sec
        last, same_n = "", 0
        while time.time() < end:
            t = ((self._anchored_reply(prompt) or {}).get("text") or "").strip()
            if t and t == last:
                same_n += 1
                if same_n >= 3:
                    return t
            else:
                same_n = 0
                last = t
            time.sleep(1.5)
        return last

    @staticmethod
    def _same_reply(a, b):
        """两段文字是否像是同一条回复（去掉空白和 Markdown 符号后，开头一段互相包含）。"""
        import re as _re
        na = _re.sub(r"[\s\u00a0*_#`>|\-\[\]()!]+", "", a or "")
        nb = _re.sub(r"[\s\u00a0*_#`>|\-\[\]()!]+", "", b or "")
        if not na or not nb:
            return False
        k = min(40, len(na), len(nb))
        return na[:k] in nb or nb[:k] in na

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

        self._park_mouse()
        self._close_overlays()
        if self._safe(lambda: self._page.evaluate("() => document.visibilityState"), "visible") == "hidden":
            self._log("⚠ AI 池的浏览器窗口被最小化了。Chrome 会暂停最小化窗口里的页面，回复可能出不来。"
                      "让它待在别的窗口后面没关系，但别最小化；或者在「设置」里取消「显示浏览器窗口」改成后台运行。")
            prog("提示：AI 池窗口被最小化了，可能会变慢")
        baseline = self._capture_baseline()
        inp = self._find_input()
        self._log("已定位输入框，准备填入…")
        time.sleep(1.0)

        # ── 填入：新版 ChatGPT 是 ProseMirror contenteditable。依次试 insert_text / fill / type ──
        pre = ""
        filled = False
        # ① 首选：直接在页面里写入输入框（不用鼠标、不需要窗口在前台）
        how_dom = self._safe(lambda: inp.evaluate(_DOM_FILL_JS, prompt), "")
        if how_dom:
            time.sleep(0.5)
            pre = self._read_input_text(inp)
            if len(pre) >= min(int(len(prompt) * 0.8), 8):
                filled = True
                self._log("已填入（方式=页面直写/%s，框内 %d 字）" % (how_dom, len(pre)))
        for how in (() if filled else ("insert_text", "fill", "type")):
            try:
                self._focus_input(inp)
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
            ("发送按钮·页面直点", lambda: self._dom_click_send()),
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

        self._chat_used = True
        reply = self._wait_for_reply(timeout_ms, baseline, prompt, opts, prog)
        # ★ 校验：回复必须是「本次提问之后」的那条。对话里有旧内容时，按位置找最底部的块
        #   可能抓到上一个任务的回复（之前视频笔记里出现整篇新闻简报就是这样来的）。
        anc = self._anchored_reply(prompt)
        if anc.get("found"):
            atext = (anc.get("text") or "").strip()
            if not atext or not self._same_reply(reply, atext):
                # 本次提问之后还没有（完整的）回复：多等一会儿，等它写完再取
                atext = self._wait_anchored_stable(prompt, 180, prog) or atext
            if atext and not self._same_reply(reply, atext):
                self._log("⚠ 抓到的回复不是本次提问的（%d 字），改用本次提问之后的回复（%d 字）"
                          % (len(reply or ""), len(atext)))
                reply = atext
        # 把回复重新抓成 Markdown：把 <a href> 还原成可点击链接 [文字](网址)，
        # 并去掉 ChatGPT 的引用角标杂质（如 "OpenAI +1"、"Anthropic +2"）。
        # 仅当抓取结果可信（长度不大幅缩水）才采用，否则保留纯文本。
        md = self._safe(lambda: self._page.evaluate(_GRAB_MARKDOWN_JS, prompt), "") or ""
        # 只有和刚才确认过的回复是同一条时才用 Markdown 版（之前只比长度，旧的长消息会顶替掉正确回复）
        if md and len(md) >= max(40, int(len(reply or "") * 0.6)) and self._same_reply(md, reply):
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
        self._focus_input(inp)
        self._page.keyboard.press("Enter")
        return True

    def _dom_click_send(self):
        """在页面里直接触发发送按钮的 click（不动鼠标、不需要窗口在前台）。找不到/按钮不可用返回 False。"""
        return bool(self._safe(lambda: self._page.evaluate(r"""() => {
            const sels = ['button[data-testid="send-button"]', '#composer-submit-button',
                          'button[aria-label*="发送"]', 'button[aria-label*="Send" i]', 'button[type="submit"]'];
            for (const s of sels) {
                for (const b of document.querySelectorAll(s)) {
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && !b.disabled && b.getAttribute('aria-disabled') !== 'true') {
                        b.click(); return true;
                    }
                }
            }
            return false;
        }"""), False))

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
        STUCK_FATAL_MS = opts.get("stuckFatalMs") or 240000
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
                        markers_min_hits, accept_stable, short_reply,
                        stable_secs=stable * POLL)
                    if res["done"]:
                        # 给出明确的完成报告：检查并说明发送按钮状态，让用户/开发者
                        # 清楚知道「AI 已答完、识别完成」，而不是只看到一句模糊的"内容稳定"。
                        gs = (probe or {}).get("genState", "unknown")
                        if gs == "idle":
                            self._log("✓ AI 已生成完毕：发送按钮已恢复『可发送』，"
                                      "识别完成（共 %d 字），交付结果。" % len(current))
                        else:
                            self._log("✓ AI 已生成完毕：文本已稳定（共 %d 字），"
                                      "识别完成，交付结果。" % len(current))
                        return current
                    # 防误判：继续等（带 holdCap 上限）
                    if not first_hold_at:
                        first_hold_at = time.time()
                    held_ms = (time.time() - first_hold_at) * 1000
                    # ★逃生通道：按钮态识别可能因第三方站点的图标结构而失效（发送键被
                    #   误判成停止键 → genState 永远 generating → 死等）。所以只要回复
                    #   文本已经「持续稳定」足够久（默认 12 秒零增长），就判定 AI 答完，
                    #   不再 100% 依赖那个脆弱的按钮信号。短回复模式阈值更短（8 秒）。
                    escape_ms = 8000 if short_reply else 12000
                    if held_ms > escape_ms:
                        self._log("内容已持续稳定 %d 字 / %.0f 秒，按钮态未翻转，"
                                  "按『文本稳定』判定答完" % (len(current), held_ms / 1000))
                        return current
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
                          markers_min_hits, accept_stable, short_reply=False,
                          stable_secs=0):
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

    def _dump_diag(self, stage, err=None):
        """失败现场：整页截图 + 页面结构摘要（不含任何输入框的值）。"""
        try:
            page = self._page
            if not page or page.is_closed():
                return
            DIAG_DIR.mkdir(exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            self._safe(lambda: page.screenshot(path=str(DIAG_DIR / (ts + ".png")),
                                               full_page=True, timeout=10000))
            info = self._safe(lambda: page.evaluate(r"""() => {
                const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
                return {
                    url: location.href, title: document.title,
                    inputs: [...document.querySelectorAll('input,textarea')].map(i => ({
                        tag: i.tagName, type: i.type, name: i.name, placeholder: i.placeholder,
                        visible: vis(i), checked: i.type === 'checkbox' ? i.checked : undefined })),
                    buttons: [...document.querySelectorAll('button,[role="button"]')]
                        .filter(vis).map(b => (b.innerText || '').trim()).filter(Boolean).slice(0, 40),
                    text: (document.body ? document.body.innerText : '').slice(0, 5000),
                };
            }"""), {}) or {}
            info.update({"stage": stage, "error": str(err) if err else "",
                         "sitePath": self._site_path, "carlistUrl": self._carlist_url,
                         "time": ts})
            (DIAG_DIR / (ts + ".json")).write_text(
                json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
            files = sorted(DIAG_DIR.glob("*.*"))
            for f in files[:-DIAG_KEEP * 2]:
                self._safe(lambda f=f: f.unlink())
            self._log("诊断已保存: %s (.png/.json)" % (DIAG_DIR / ts))
        except Exception:
            pass

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
_GRAB_MARKDOWN_JS = r"""(anchorText) => {
    // 只看「本次提问气泡」之后的内容：找到最后一个包含提问开头的用户气泡，作为锚点
    let __cxAnchor = null;
    try {
        const __n = s => (s || '').replace(/[\s\u00a0]+/g, '');
        const __k = __n(anchorText || '').slice(0, 30);
        if (__k) {
            const __us = [...document.querySelectorAll('[data-message-author-role="user"]')];
            for (let i = __us.length - 1; i >= 0; i--) {
                if (__n(__us[i].innerText).includes(__k)) { __cxAnchor = __us[i]; break; }
            }
        }
    } catch (e) { __cxAnchor = null; }
    // 同一条回复常被网站拆成多个兄弟块（如正文段落 +（另起的）序号列表）。
    // 从最底部命中块向上爬到「整条回复」的容器，把被拆开的块合起来，但不跨越到上一条消息。
    const __cxClimb = (el) => {
        if(!el) return el;
        let container = el, cur = el;
        for(let i=0;i<8;i++){
            const p = cur.parentElement;
            if(!p || p===document.body || p===document.documentElement) break;
            const r = p.getBoundingClientRect();
            if(!r || r.width < 200) break;
            let roleCount = 0;
            try { roleCount = p.querySelectorAll('[data-message-author-role]').length; } catch(e){}
            if(roleCount > 1) break;                       // 跨越了多条消息 → 爬过头，停
            const cLen = (container.innerText||'').length;
            const pLen = (p.innerText||'').length;
            if(pLen <= cLen){ cur = p; continue; }         // 纯包裹层，继续往上看
            if(pLen > cLen*2.6) break;                     // 文本暴涨＝并入了别的轮次，停
            container = p; cur = p;
        }
        return container;
    };
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
    // 单元格内联文本（用于表格）：把竖线换成空格，避免撑破 Markdown 表格
    const cellText = (el) => {
        let t=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
        return t.replace(/\|/g,' ').trim();
    };
    // <table> -> Markdown 表格（首行作表头）。ChatGPT 的表格（含「写入/Canvas」里的）都是真实 <table>。
    const tableToMd = (table) => {
        const trs = [...table.querySelectorAll('tr')].filter(tr => tr.querySelector('th,td'));
        if(!trs.length) return '';
        let rows = trs.map(tr => [...tr.children]
            .filter(c => /^(td|th)$/i.test(c.tagName))
            .map(cellText)).filter(r => r.length);
        if(!rows.length) return '';
        const cols = Math.max(...rows.map(r => r.length));
        rows = rows.map(r => { while(r.length<cols) r.push(''); return r; });
        const head = rows[0];
        let md = '\n| ' + head.join(' | ') + ' |\n| ' + head.map(()=>'---').join(' | ') + ' |\n';
        for(const r of rows.slice(1)) md += '| ' + r.join(' | ') + ' |\n';
        return md + '\n';
    };
    const walk = (node) => {
        let out='';
        for(const child of node.childNodes){
            if(child.nodeType===3){ out += child.textContent; continue; }
            if(child.nodeType!==1) continue;
            const el=child, tag=el.tagName.toLowerCase();
            if(tag==='script'||tag==='style') continue;
            if(isCite(el)) continue;
            if(tag==='table'){ out += tableToMd(el); continue; }                   // ★表格整体转 Markdown
            if(/^(thead|tbody|tfoot|tr|td|th|colgroup|col)$/.test(tag)) continue;  // 已由 table 处理，跳过防重复
            if(tag==='img'){                                                       // ★图片
                const src=el.getAttribute('src')||el.currentSrc||'';
                const alt=(el.getAttribute('alt')||'图片').trim();
                if(src && !/^data:/.test(src)) out += '\n!['+alt+']('+src+')\n';
                continue;
            }
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
            const block=/^(p|div|blockquote|pre|section|article)$/.test(tag);
            out += walk(el);
            if(block) out+='\n';
        }
        return out;
    };
    const sels = ['[data-message-author-role="assistant"]','[class*="markdown"]',
        '[class*="prose"]','[class*="assistant"]','[class*="message-content"]'];
    let best=null, bestBottom=-1;
    for (const s of sels){
        let els; try{els=document.querySelectorAll(s)}catch(e){continue}
        for(const el of els){
            const r=el.getBoundingClientRect();
            const t=(el.innerText||'').trim();
            if(__cxAnchor && !(__cxAnchor.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
            if(r.width>200 && t.length>20 && r.bottom>bestBottom){ best=el; bestBottom=r.bottom; }
        }
    }
    if(!best) return '';
    const root = __cxClimb(best);
    let md = walk(root);

    // ★画布 / 侧栏：把「不在回复气泡里」的表格也补抓进来。
    //   ChatGPT 把表格放进「写入 / Canvas」面板时，它是独立的一块 DOM，不在助手气泡里，
    //   上面的 walk 扫不到。这里只补抓表格（最稳、几乎不会误抓别的东西），并按内容去重。
    try {
        const seen = md.replace(/[\s|*_#`-]+/g,'');
        const extra = [];
        for(const tb of document.querySelectorAll('table')){
            if(root.contains(tb)) continue;                 // 已在回复气泡里，跳过
            const r = tb.getBoundingClientRect();
            if(!r || r.width < 120) continue;
            const tmd = tableToMd(tb);
            if(!tmd) continue;
            const key = tmd.replace(/[\s|*_#`-]+/g,'');
            if(key.length < 12) continue;
            if(seen.indexOf(key.slice(0, Math.min(40, key.length))) >= 0) continue;   // 已包含，去重
            extra.push(tmd);
        }
        if(extra.length){
            md = (md.trim() ? md.trim()+'\n\n' : '') + '——— 画布内容 ———\n' + extra.join('\n');
        }
    } catch(e){}

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
    const __cxClimb = (el) => {
        if(!el) return el;
        let container = el, cur = el;
        for(let i=0;i<8;i++){
            const p = cur.parentElement;
            if(!p || p===document.body || p===document.documentElement) break;
            const r = p.getBoundingClientRect();
            if(!r || r.width < 200) break;
            let roleCount = 0;
            try { roleCount = p.querySelectorAll('[data-message-author-role]').length; } catch(e){}
            if(roleCount > 1) break;
            const cLen = (container.innerText||'').length;
            const pLen = (p.innerText||'').length;
            if(pLen <= cLen){ cur = p; continue; }
            if(pLen > cLen*2.6) break;
            container = p; cur = p;
        }
        return container;
    };
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
                const hasOnlyRect = hasRect && svg.querySelectorAll('path, line, polyline, polygon, circle').length === 0;
                // 加严：停止键的 ■ 是个接近正方形、居中的小方块。只有「整个 svg 仅含
                // 一个近正方形 rect」才算停止键，避免把「圆形背景(rect 圆角) + 箭头(实为
                // path)」或「rect 当背景的发送键」误判成停止键 —— 那会导致 AI 答完后
                // genState 一直卡在 generating、完成判定死等。
                let looksLikeStopSquare = false;
                if (hasOnlyRect) {
                    try {
                        const rc = svg.querySelector('rect');
                        const w = parseFloat(rc.getAttribute('width') || '0');
                        const h = parseFloat(rc.getAttribute('height') || '0');
                        // 近正方形（宽高比 0.7~1.4），且不是铺满整个 svg 的大背景块
                        const ratio = (w && h) ? (w / h) : 0;
                        const vb = (svg.getAttribute('viewBox') || '').split(/\s+/);
                        const vbw = vb.length === 4 ? parseFloat(vb[2]) : 0;
                        const fillsAll = vbw && w >= vbw * 0.9;   // 几乎铺满 → 更像背景，不是 ■
                        looksLikeStopSquare = (ratio >= 0.7 && ratio <= 1.4 && !fillsAll);
                        if (!w || !h) looksLikeStopSquare = true;  // 没标 width/height 的，保守仍当停止键
                    } catch (e) { looksLikeStopSquare = true; }
                }
                if (looksLikeStopSquare) { stopBtn = host; break; }
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
                candidates.push({ el, text: t, bottom: r.bottom, length: t.length, selector: sel });
        }
    }
    if (candidates.length > 0) {
        candidates.sort((a,b)=>b.bottom-a.bottom);
        const bottomEl = candidates[0].el;
        const topY = candidates[0].bottom;
        const near = candidates.filter(c => topY - c.bottom < 200);
        near.sort((a,b)=>b.length-a.length);
        let chosen = { text: near[0].text, bottom: near[0].bottom,
                       length: near[0].length, selector: near[0].selector };
        // 合并被拆成多个兄弟块的同一条回复（如序号列表），让「完成判定」和最终取文都拿到完整内容
        try {
            const cont = __cxClimb(bottomEl);
            const ct = (cont.innerText||'').trim();
            if (ct.length > chosen.text.length)
                chosen = { text: ct, bottom: cont.getBoundingClientRect().bottom,
                           length: ct.length, selector: 'climbed' };
        } catch(e) {}
        return { chosen, totalCandidates: candidates.length,
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


def chat_epoch():
    """当前网页对话线程的编号；变了就说明已经不是之前那个对话了。"""
    try:
        return _worker()._chat_epoch
    except Exception:
        return -1


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
