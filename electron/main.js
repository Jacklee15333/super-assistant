// main.js — Electron 主进程
// 职责：开一个独立桌面窗口，并在后台自动启动 Python 后端，退出时关掉它。

const { app, BrowserWindow, ipcMain, shell, Menu, nativeImage, clipboard, screen, globalShortcut, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");
const fs = require("fs");

let mainWindow = null;
let backendProcess = null;

const BACKEND_PORT = 8756;
let lastBackendStatus = null;   // 最近一次后端就绪状态，供前端按需查询（修复冷启动卡「加载中…」）
const WAKE_ACCEL = "CommandOrControl+Shift+Space";   // 全局唤起热键

// 找到 backend 目录：开发时在 ../backend，打包后在 resources/backend
function backendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.join(__dirname, "..", "backend");
}

// 启动 Python 后端
function startBackend() {
  const dir = backendDir();
  // 优先用 python3，Windows 上回退到 python
  const pyCmd = process.platform === "win32" ? "python" : "python3";
  backendProcess = spawn(pyCmd, ["server.py"], {
    cwd: dir,
    stdio: "inherit",
  });
  backendProcess.on("error", (err) => {
    console.error("后端启动失败：", err);
  });
}

// 轮询等后端就绪，最多等 ~15 秒
function waitForBackend(retries = 30) {
  return new Promise((resolve) => {
    const tryPing = (left) => {
      const req = http.get(
        { host: "127.0.0.1", port: BACKEND_PORT, path: "/ping", timeout: 800 },
        (res) => { res.resume(); resolve(true); }
      );
      req.on("error", () => {
        if (left <= 0) return resolve(false);
        setTimeout(() => tryPing(left - 1), 500);
      });
      req.on("timeout", () => { req.destroy(); });
    };
    tryPing(retries);
  });
}

// 中文菜单（替换默认的 File/Edit/View… 英文菜单）
function buildChineseMenu() {
  const runInPage = (js) => {
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.executeJavaScript(js).catch(() => {});
    }
  };
  const template = [
    {
      label: "设置",
      submenu: [
        {
          label: "打开设置页",
          click: () => runInPage(
            "document.querySelector('.nav-item[data-view=\"settings\"]').click()"),
        },
        {
          label: "切换皮肤（深色/浅色）",
          click: () => runInPage("window.toggleTheme && window.toggleTheme()"),
        },
        { type: "separator" },
        { label: "关于超能小助", click: () => runInPage(
            "alert('超能小助 · 你自己的本地 AI 助手\\n环境就绪')") },
        { role: "reload", label: "刷新界面" },
        { role: "toggleDevTools", label: "开发者工具" },
        { type: "separator" },
        { role: "quit", label: "退出" },
      ],
    },
    {
      label: "编辑",
      submenu: [
        { role: "undo", label: "撤销" },
        { role: "redo", label: "重做" },
        { type: "separator" },
        { role: "cut", label: "剪切" },
        { role: "copy", label: "复制" },
        { role: "paste", label: "粘贴" },
        { role: "selectAll", label: "全选" },
      ],
    },
    {
      label: "视图",
      submenu: [
        { role: "resetZoom", label: "实际大小" },
        { role: "zoomIn", label: "放大" },
        { role: "zoomOut", label: "缩小" },
        { type: "separator" },
        { label: "显示 / 隐藏桌宠 🦊", click: () => togglePet() },
        { type: "separator" },
        { role: "togglefullscreen", label: "全屏" },
      ],
    },
    {
      label: "窗口",
      submenu: [
        { role: "minimize", label: "最小化" },
        { role: "close", label: "关闭" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  const iconPath = path.join(__dirname, "assets",
    process.platform === "win32" ? "icon.ico" : "icon.png");
  const appIcon = nativeImage.createFromPath(iconPath);

  // 按当前屏幕「可用工作区」算窗口大小：不要超过屏幕高度，否则底部按钮会被挤到屏幕外。
  // 取工作区的 ~92%，并限制在合理上限内，再居中。这样无论屏幕多大都能完整显示所有按钮。
  let winW = 1280, winH = 860;
  let winX, winY;
  try {
    const wa = screen.getPrimaryDisplay().workAreaSize;   // 已扣掉任务栏的可用区域
    winW = Math.min(1440, Math.max(960, Math.round(wa.width * 0.92)));
    winH = Math.min(1040, Math.max(640, Math.round(wa.height * 0.96)));
    const waPos = screen.getPrimaryDisplay().workArea;     // 含左上角坐标，用于居中
    winX = waPos.x + Math.round((waPos.width - winW) / 2);
    winY = waPos.y + Math.round((waPos.height - winH) / 2);
  } catch (e) { /* 拿不到屏幕信息就用默认 1280x860 */ }

  mainWindow = new BrowserWindow({
    width: winW,
    height: winH,
    x: winX,
    y: winY,
    minWidth: 800,
    minHeight: 520,
    title: "超能小助",
    icon: appIcon.isEmpty() ? undefined : appIcon,
    backgroundColor: "#faf9f5",
    // 仿 Claude 桌面端：隐藏系统标题栏，窗口按钮（最小化/最大化/关闭）浮在页面右上角；
    // 菜单改由侧栏左上角的 ☰ 按钮弹出（快捷键照常可用）。
    ...(process.platform === "win32" ? {
      titleBarStyle: "hidden",
      titleBarOverlay: { color: "#faf9f5", symbolColor: "#3d3c38", height: 44 },
    } : {}),
    show: false,            // 先不显示，定好大小后再显示，避免闪一下
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 已按屏幕工作区算好大小并居中，直接显示
  mainWindow.show();

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));

  // ☰ 按钮：弹出应用菜单（标题栏隐藏后菜单栏不再显示）
  ipcMain.removeHandler("app-menu-popup");
  ipcMain.handle("app-menu-popup", (_e, pos) => {
    const m = Menu.getApplicationMenu();
    if (m && mainWindow) {
      const opt = { window: mainWindow };
      if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
        opt.x = Math.round(pos.x); opt.y = Math.round(pos.y);
      }
      m.popup(opt);
    }
    return true;
  });
  // 深浅色切换时，同步右上角窗口按钮区域的颜色
  ipcMain.removeHandler("titlebar-theme");
  ipcMain.handle("titlebar-theme", (_e, dark) => {
    try {
      if (mainWindow && process.platform === "win32" && mainWindow.setTitleBarOverlay) {
        mainWindow.setTitleBarOverlay(dark
          ? { color: "#262624", symbolColor: "#d6d4cc" }
          : { color: "#faf9f5", symbolColor: "#3d3c38" });
      }
    } catch (e) { /* 老版本 Electron 不支持就算了 */ }
    return true;
  });

  // 外部链接用系统浏览器打开，不在应用内乱跳
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  // 防止点链接时应用本体被导航走；http(s) 链接一律丢给系统浏览器
  mainWindow.webContents.on("will-navigate", (e, url) => {
    if (/^https?:\/\//.test(url)) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
    // 关闭主窗即退出整个程序（含桌宠 + 后端），避免只剩桌宠时用户找不到入口、
    // 也避免后端变成孤儿进程。桌宠的「显示/隐藏」请用菜单或设置里的开关。
    try { if (petWin && !petWin.isDestroyed()) petWin.destroy(); } catch (e) {}
    petWin = null;
    if (process.platform !== "darwin") app.quit();
  });
}

// 注册全局唤起热键：一键把窗口拉到最前并聚焦输入框（Marvis 式「动动嘴」前置）
function registerHotkeys() {
  try {
    globalShortcut.register(WAKE_ACCEL, () => {
      if (!mainWindow) { createWindow(); return; }
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents
        .executeJavaScript("var i=document.getElementById('input'); if(i){i.focus();}")
        .catch(() => {});
    });
  } catch (e) {
    console.error("注册全局热键失败：", e);
  }
}

// ---------- 剪贴板监听 + 悬浮"提取"按钮 ----------
// 你在抖音等地方点"复制链接"后，这里检测到视频链接，就在屏幕右下角弹一个
// 小圆按钮，点一下就把视频加入提取队列，省得你手动粘贴。
let floatWin = null;
let lastClipText = "";
let pendingVideoUrl = "";
let clipWatchOn = true;
const VIDEO_URL_RE = /(https?:\/\/[^\s]*(douyin\.com|iesdouyin\.com|kuaishou\.com|bilibili\.com|b23\.tv|youtube\.com|youtu\.be|xiaohongshu\.com|xhslink\.com)[^\s]*)/i;

function extractVideoUrl(text) {
  if (!text) return "";
  const m = text.match(VIDEO_URL_RE);
  return m ? m[1].replace(/[，。！、）)]+$/, "") : "";
}

function buildFloatWindow() {
  const pt = screen.getCursorScreenPoint();
  const disp = screen.getDisplayNearestPoint(pt);
  const wa = disp.workArea;
  const W = 260, H = 92, GAP = 22;
  // 放在鼠标光标的右上方，离一点点距离；并夹在屏幕可视区域内
  let x = pt.x + GAP;
  let y = pt.y - H - GAP;
  x = Math.min(x, wa.x + wa.width - W - 10);
  x = Math.max(wa.x, x);
  y = Math.max(wa.y, y);                       // 顶部不超出
  y = Math.min(y, wa.y + wa.height - H);        // 底部兜底
  floatWin = new BrowserWindow({
    width: W, height: H, x: Math.round(x), y: Math.round(y),
    frame: false, transparent: true, resizable: false, movable: true,
    alwaysOnTop: true, skipTaskbar: true, show: false, focusable: true,
    webPreferences: { contextIsolation: true },
  });
  floatWin.setAlwaysOnTop(true, "screen-saver");
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{margin:0;padding:0;background:transparent;font-family:"Microsoft YaHei",sans-serif;}
    .card{margin:8px;background:#232119;border:1px solid #d65a3a;border-radius:14px;
      box-shadow:0 6px 20px rgba(0,0,0,.4);padding:10px 12px;display:flex;align-items:center;gap:10px;}
    .ico{width:34px;height:34px;border-radius:9px;background:#d65a3a;color:#fff;font-size:18px;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;}
    .txt{color:#ece7da;font-size:12.5px;line-height:1.35;flex:1;}
    .txt b{color:#ffb59c;}
    .btn{background:#d65a3a;color:#fff;border:none;border-radius:8px;padding:6px 10px;
      font-size:12.5px;cursor:pointer;white-space:nowrap;}
    .x{position:absolute;top:2px;right:8px;color:#8f897a;cursor:pointer;font-size:13px;}
  </style></head><body>
    <span class="x" onclick="location.href='https://cx.local/close'">✕</span>
    <div class="card">
      <div class="ico">🦞</div>
      <div class="txt">检测到视频链接<br><b>超能小助</b> 帮你提取？</div>
      <button class="btn" onclick="location.href='https://cx.local/extract'">提取</button>
    </div>
  </body></html>`;
  floatWin.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));
  // 用导航拦截当作"按钮点击"信号，避免依赖 IPC/preload
  floatWin.webContents.on("will-navigate", (e, url) => {
    e.preventDefault();
    if (url.includes("/extract")) {
      const u = pendingVideoUrl;
      if (floatWin && !floatWin.isDestroyed()) floatWin.destroy();
      floatWin = null;
      if (mainWindow && u) {
        mainWindow.show();
        mainWindow.focus();
        mainWindow.webContents.executeJavaScript(
          `window.startVideoFromFloat && window.startVideoFromFloat(${JSON.stringify(u)})`)
          .catch(() => {});
      }
    } else if (url.includes("/close")) {
      if (floatWin && !floatWin.isDestroyed()) floatWin.destroy();
      floatWin = null;
    }
  });
  floatWin.on("closed", () => { floatWin = null; });
}

function showFloatButton(url) {
  pendingVideoUrl = url;
  // 每次都重建一个新的悬浮窗（最稳，避免隐藏后再显示不出来的问题），并定位到光标附近
  if (floatWin && !floatWin.isDestroyed()) floatWin.destroy();
  floatWin = null;
  buildFloatWindow();
  floatWin.showInactive();   // 显示但不抢焦点，不打断你看视频
}

function startClipboardWatch() {
  lastClipText = clipboard.readText() || "";
  setInterval(() => {
    if (!clipWatchOn) return;
    let t = "";
    try { t = clipboard.readText() || ""; } catch (_) { return; }
    if (t && t !== lastClipText) {
      lastClipText = t;
      const url = extractVideoUrl(t);
      // 检测到新的视频链接就弹按钮；若悬浮窗已经显示着，则更新它的链接
      if (url) showFloatButton(url);
    }
  }, 1200);
}

// ════════════════════════════════════════════════════════════════════
// 🦊 桌宠系统（HermesPet 风格，但纯 Electron / Windows 原生实现）
// 一个透明、无边框、永远置顶的小窗，里面住着会溜达的桌宠。
// 配置（选了哪只 / 开没开 / 自定义形象）存到磁盘，重开还在。
// ════════════════════════════════════════════════════════════════════
let petWin = null;
let petReady = false;

// 配置文件：放到 backend/memory 下，跟其它本地数据在一起（人类可读、可手改）
function petConfigPath() {
  return path.join(backendDir(), "memory", "pet_config.json");
}
function loadPetConfig() {
  const def = { enabled: true, character: "fox", custom: null };
  try {
    const p = petConfigPath();
    if (fs.existsSync(p)) {
      const d = JSON.parse(fs.readFileSync(p, "utf-8"));
      return Object.assign(def, d || {});
    }
  } catch (e) { /* 用默认 */ }
  return def;
}
function savePetConfig(patch) {
  const cur = loadPetConfig();
  const next = Object.assign(cur, patch || {});
  try {
    const p = petConfigPath();
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, JSON.stringify(next, null, 2), "utf-8");
  } catch (e) { /* 写失败不致命 */ }
  return next;
}

function createPetWindow() {
  if (petWin && !petWin.isDestroyed()) { petWin.show(); return; }
  const W = 160, H = 190;
  let x = 200, y = 200;
  try {
    const wa = screen.getPrimaryDisplay().workArea;
    x = wa.x + wa.width - W - 60;          // 默认蹲在右下角
    y = wa.y + wa.height - H - 20;
  } catch (e) {}
  petWin = new BrowserWindow({
    width: W, height: H, x, y,
    frame: false, transparent: true, resizable: false, movable: true,
    alwaysOnTop: true, skipTaskbar: true, show: false, focusable: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  petWin.setAlwaysOnTop(true, "screen-saver");
  // 让桌宠在所有工作区可见（多桌面）
  try { petWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true }); } catch (e) {}
  petWin.loadFile(path.join(__dirname, "renderer", "pet.html"));
  petWin.once("ready-to-show", () => petWin.showInactive());
  petWin.on("closed", () => { petWin = null; petReady = false; });
}

function showPet() {
  const cfg = savePetConfig({ enabled: true });
  if (petWin && !petWin.isDestroyed()) petWin.show();
  else createPetWindow();
  return cfg;
}
function hidePet() {
  savePetConfig({ enabled: false });
  if (petWin && !petWin.isDestroyed()) petWin.destroy();
  petWin = null; petReady = false;
}
function togglePet() {
  const cfg = loadPetConfig();
  if (cfg.enabled && petWin && !petWin.isDestroyed()) hidePet();
  else showPet();
}

// 把消息推给桌宠（任务忙/闲、让它说句话、配置变了）
function petSend(channel, payload) {
  if (petWin && !petWin.isDestroyed()) {
    try { petWin.webContents.send(channel, payload); } catch (e) {}
  }
}

// 把拖到桌宠身上的文件/文本路由到主窗（视频去提取，其它进对话）
function routeFedItem(item) {
  if (!mainWindow) return;
  const isVideo = VIDEO_URL_RE.test(item) ||
    /\.(mp4|mov|mkv|avi|flv|webm|m4v)$/i.test(item);
  mainWindow.show();
  mainWindow.focus();
  if (isVideo) {
    const u = extractVideoUrl(item) || item;
    mainWindow.webContents.executeJavaScript(
      `window.startVideoFromFloat && window.startVideoFromFloat(${JSON.stringify(u)})`
    ).catch(() => {});
  } else {
    // 其它文件/文本：交给前端的「桌宠投喂」处理器（附到对话输入）
    mainWindow.webContents.executeJavaScript(
      `window.petFeed && window.petFeed(${JSON.stringify(item)})`
    ).catch(() => {});
  }
}

// ── 桌宠相关 IPC ──
ipcMain.handle("pet-get-workarea", () => {
  try { return screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea; }
  catch (e) { try { return screen.getPrimaryDisplay().workArea; } catch (_) { return null; } }
});
ipcMain.handle("pet-get-bounds", () => {
  if (petWin && !petWin.isDestroyed()) return petWin.getBounds();
  return null;
});
ipcMain.handle("pet-move-to", (_e, x, y) => {
  if (petWin && !petWin.isDestroyed()) {
    try { petWin.setPosition(Math.round(x), Math.round(y)); } catch (e) {}
  }
});
ipcMain.handle("pet-open-main", () => {
  if (!mainWindow) { createWindow(); return; }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show(); mainWindow.focus();
});
ipcMain.handle("pet-hide", () => { hidePet(); });
ipcMain.handle("pet-get-config", () => loadPetConfig());
ipcMain.handle("pet-set-config", (_e, patch) => {
  const next = savePetConfig(patch || {});
  // 同步给主窗里的「桌宠设置」面板（如果开着）
  if (mainWindow) {
    mainWindow.webContents.executeJavaScript(
      `window.onPetConfigChanged && window.onPetConfigChanged(${JSON.stringify(next)})`
    ).catch(() => {});
  }
  return next;
});
ipcMain.handle("pet-ready", () => { petReady = true; });
ipcMain.handle("pet-feed-files", (_e, paths) => {
  (paths || []).forEach(routeFedItem);
});
ipcMain.handle("pet-feed-text", (_e, text) => {
  if (text) routeFedItem(text);
});
// 主窗 → 桌宠：在设置面板里改了形象/开关，或想让桌宠说话
ipcMain.handle("pet-apply-config", (_e, patch) => {
  const next = savePetConfig(patch || {});
  if (patch && patch.enabled === false) hidePet();
  else if (patch && patch.enabled === true) showPet();
  petSend("pet-config", next);
  return next;
});
ipcMain.handle("pet-say", (_e, text) => { petSend("pet-say", text); });
ipcMain.handle("pet-busy", (_e, busy) => { petSend("pet-busy", !!busy); });
ipcMain.handle("pet-toggle", () => { togglePet(); return loadPetConfig(); });

// ════════════════════════════════════════════════════════════════════
// 🔔 分身自动任务「完成提醒」——无论软件在前台还是最小化/后台，都只在桌面右下角
// 弹一个小长方形浮窗（不再用软件内的大弹层）。由主进程自己轮询后端
// /agents/notifications（最小化时也不受渲染层定时器限流影响），有新结果就弹；
// 点「查看」唤起主窗并跳到那条自动结果对话；约 10 秒自动消失。
// ════════════════════════════════════════════════════════════════════
let notifWin = null;
let notifQueue = [];
let notifShowing = false;
let notifAutoTimer = null;
let notifPollTimer = null;
const notifHandled = new Set();   // 本次会话已处理过的通知 id（双保险，防重复弹）

function _esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// 简单的后端 GET / POST（127.0.0.1:BACKEND_PORT），解析 JSON；失败返回 null / false。
function notifGet(p) {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: BACKEND_PORT, path: p, timeout: 4000 },
      (res) => {
        let buf = ""; res.setEncoding("utf8");
        res.on("data", (c) => (buf += c));
        res.on("end", () => { try { resolve(JSON.parse(buf)); } catch (e) { resolve(null); } });
      });
    req.on("error", () => resolve(null));
    req.on("timeout", () => { req.destroy(); resolve(null); });
  });
}
function notifPost(p, obj) {
  return new Promise((resolve) => {
    const data = Buffer.from(JSON.stringify(obj || {}), "utf8");
    const req = http.request({
      host: "127.0.0.1", port: BACKEND_PORT, path: p, method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": data.length },
      timeout: 4000,
    }, (res) => { res.resume(); res.on("end", () => resolve(true)); });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
    req.write(data); req.end();
  });
}
function markNotifSeen(id) { if (id) notifPost("/agents/notifications/seen", { ids: [id] }); }

// 取一个干净的「任务名」：优先 task_name；为空时从 title 里剥掉 "🤖 自动 · " 前缀和结尾时间。
function notifTaskName(n) {
  let name = (n && n.task_name ? String(n.task_name) : "").trim();
  if (name) return name;
  let t = (n && n.title ? String(n.title) : "").trim();
  t = t.replace(/^🤖\s*自动\s*[·.\-]?\s*/, "");
  t = t.replace(/\s*[·.\-]\s*\d{1,2}-\d{1,2}.*$/, "");
  t = t.trim();
  return t || "自动任务";
}

function closeNotifFloat() {
  if (notifAutoTimer) { clearTimeout(notifAutoTimer); notifAutoTimer = null; }
  if (notifWin && !notifWin.isDestroyed()) { try { notifWin.destroy(); } catch (e) {} }
  notifWin = null;
  notifShowing = false;
  setTimeout(pumpNotifQueue, 350);   // 接着弹下一条（如果排着）
}

function buildNotifFloat(n) {
  let wa;
  try { wa = screen.getPrimaryDisplay().workArea; }
  catch (e) { wa = { x: 0, y: 0, width: 1280, height: 800 }; }
  const W = 360, H = 96, MARGIN = 24;
  const x = Math.round(wa.x + wa.width - W - MARGIN);   // 右
  const y = Math.round(wa.y + wa.height - H - MARGIN);  // 下

  notifWin = new BrowserWindow({
    width: W, height: H, x, y,
    frame: false, transparent: true, resizable: false, movable: true,
    alwaysOnTop: true, skipTaskbar: true, show: false, focusable: true, hasShadow: false,
    webPreferences: { contextIsolation: true },
  });
  notifWin.setAlwaysOnTop(true, "screen-saver");
  try { notifWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true }); } catch (e) {}

  const emoji = _esc(n.agent_emoji || "🤖");
  const agent = _esc(n.agent_name || "分身");
  const task = _esc(notifTaskName(n));
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{margin:0;padding:0;background:transparent;
      font-family:"Microsoft YaHei","PingFang SC",sans-serif;overflow:hidden;}
    .card{margin:8px;height:72px;box-sizing:border-box;background:#232119;
      border:1px solid #d65a3a;border-radius:14px;box-shadow:0 6px 22px rgba(0,0,0,.45);
      padding:0 12px;display:flex;align-items:center;gap:11px;position:relative;}
    .ico{width:38px;height:38px;border-radius:10px;background:#d65a3a;color:#fff;font-size:20px;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;}
    .txt{flex:1;min-width:0;}
    .t1{font-size:12px;color:#bdb6a6;line-height:1.3;}
    .t2{font-size:13.5px;font-weight:700;color:#ffd9c9;line-height:1.35;margin-top:2px;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .btn{background:#d65a3a;color:#fff;border:none;border-radius:8px;padding:7px 12px;
      font-size:12.5px;cursor:pointer;white-space:nowrap;flex-shrink:0;}
    .btn:hover{background:#e36a48;}
    .x{position:absolute;top:4px;right:8px;color:#7d7768;cursor:pointer;font-size:13px;line-height:1;}
    .x:hover{color:#cfc8b8;}
  </style></head><body>
    <div class="card">
      <span class="x" onclick="location.href='https://cx.local/close'">✕</span>
      <div class="ico">${emoji}</div>
      <div class="txt">
        <div class="t1">${agent} 完成了任务</div>
        <div class="t2" title="${task}">【${task}】</div>
      </div>
      <button class="btn" onclick="location.href='https://cx.local/open'">查看</button>
    </div>
  </body></html>`;
  notifWin.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));

  // 用导航拦截当按钮信号（与视频悬浮窗一致，不依赖 IPC/preload）
  notifWin.webContents.on("will-navigate", (e, url) => {
    e.preventDefault();
    if (url.includes("/open")) {
      const slug = n.slug, cid = n.conversation_id;
      closeNotifFloat();
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show(); mainWindow.focus();
        mainWindow.webContents.executeJavaScript(
          `window.openAgentConvoFromNotif && window.openAgentConvoFromNotif(${JSON.stringify(slug)}, ${JSON.stringify(cid)})`
        ).catch(() => {});
      }
    } else if (url.includes("/close")) {
      closeNotifFloat();
    }
  });
  notifWin.on("closed", () => { notifWin = null; });
  notifWin.showInactive();   // 显示但不抢焦点，不打断当前操作
}

function pumpNotifQueue() {
  if (notifShowing) return;
  const n = notifQueue.shift();
  if (!n) return;
  notifShowing = true;
  markNotifSeen(n.id);                 // 一弹出就标记已读，避免下次轮询重复弹
  try { buildNotifFloat(n); }
  catch (e) { notifShowing = false; return; }
  notifAutoTimer = setTimeout(closeNotifFloat, 10000);   // 10 秒后自动消失
}

async function pollNotifications() {
  const d = await notifGet("/agents/notifications");
  if (!d || !d.ok || !Array.isArray(d.items) || !d.items.length) return;
  d.items.forEach((n) => {
    if (n && n.id && !notifHandled.has(n.id)) {
      notifHandled.add(n.id);
      notifQueue.push(n);
    }
  });
  pumpNotifQueue();
}

function startNotifPoller() {
  if (notifPollTimer) return;
  notifPollTimer = setInterval(() => { pollNotifications().catch(() => {}); }, 15000);
  setTimeout(() => { pollNotifications().catch(() => {}); }, 6000);   // 启动几秒后先查一次
}

app.whenReady().then(async () => {
  // Windows 任务栏按这个 id 分组，配合窗口图标才能显示成自己的图标
  buildChineseMenu();        // 把英文菜单换成中文
  startBackend();
  // 先把窗口建出来（秒开，不再等后端 /ping 跑完 30 次重试），
  // 后端就绪状态在后台轮询，等通了再推给前端——避免「控制台早好了、界面要等很久」。
  createWindow();
  registerHotkeys();         // 注册全局唤起热键
  startClipboardWatch();     // 监听剪贴板，复制视频链接时弹悬浮按钮
  startNotifPoller();        // 监听分身自动任务完成，在桌面右下角弹小浮窗（前台/后台都弹）
  // 🦊 桌宠：按上次保存的开关决定要不要请它出场（默认开）
  try { if (loadPetConfig().enabled) createPetWindow(); } catch (e) {}
  // 后台等待后端就绪，再把状态告诉前端（不阻塞窗口显示）
  // 修复：老逻辑只 send 一次，若前端此刻还没挂上监听就彻底丢了 → 各页永久卡「加载中…」。
  // 现在：记下最近状态，并在页面加载完成后「连推几次」，确保前端一定收得到；
  // 同时前端自己也会探活兜底（见 renderer.js），双保险。
  waitForBackend().then((ok) => {
    lastBackendStatus = ok;
    const send = () => { try { mainWindow.webContents.send("backend-status", ok); } catch (e) {} };
    const sendBurst = () => {
      // 立刻发，然后 300ms / 1.5s / 4s 各补一发，覆盖前端不同的就绪时机
      send();
      [300, 1500, 4000].forEach((ms) => setTimeout(send, ms));
    };
    if (mainWindow.webContents.isLoading()) {
      mainWindow.webContents.once("did-finish-load", sendBurst);
    } else {
      sendBurst();
    }
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// 退出时务必关掉后端，别留孤儿进程
function killBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
    backendProcess = null;
  }
}
app.on("before-quit", () => {
  killBackend();
  try { if (petWin && !petWin.isDestroyed()) petWin.destroy(); } catch (e) {}
  petWin = null;
});
app.on("will-quit", () => { try { globalShortcut.unregisterAll(); } catch (_) {} });
app.on("window-all-closed", () => {
  killBackend();
  if (process.platform !== "darwin") app.quit();
});

// 暴露后端端口给前端
ipcMain.handle("get-backend-port", () => BACKEND_PORT);

// v55：独立的「终端」窗口 —— 和启动时黑窗口里的内容一样（从后端 /logs 读），可以单独摆在一边看
let termWin = null;
ipcMain.handle("open-terminal-window", () => {
  if (termWin && !termWin.isDestroyed()) {
    if (termWin.isMinimized()) termWin.restore();
    termWin.show();
    termWin.focus();
    return true;
  }
  termWin = new BrowserWindow({
    width: 1000,
    height: 640,
    minWidth: 520,
    minHeight: 300,
    title: "超能小助 · 终端",
    backgroundColor: "#141414",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  try { termWin.setMenuBarVisibility(false); } catch (e) {}
  termWin.loadFile(path.join(__dirname, "renderer", "terminal.html"));
  termWin.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  termWin.on("closed", () => { termWin = null; });
  return true;
});

// 前端可主动查询当前后端状态（万一推送的 backend-status 没收到，用这个补救）
ipcMain.handle("get-backend-status", () => lastBackendStatus);

// 「导入本地文件」：弹原生文件选择框，返回用户选中的音/视频文件绝对路径数组（取消则空数组）
ipcMain.handle("pick-media-files", async () => {
  try {
    const r = await dialog.showOpenDialog(mainWindow, {
      title: "选择本地音频 / 视频文件",
      properties: ["openFile", "multiSelections"],
      filters: [
        { name: "音频 / 视频",
          extensions: ["mp4", "mov", "mkv", "avi", "flv", "webm", "wmv", "m4v", "ts",
                       "mp3", "wav", "m4a", "aac", "flac", "ogg", "opus", "wma", "amr"] },
        { name: "所有文件", extensions: ["*"] },
      ],
    });
    if (r.canceled) return [];
    return r.filePaths || [];
  } catch (e) {
    return [];
  }
});

// 导入整个文件夹：弹目录选择框，递归扫描里面的音/视频文件后返回列表。
// 下载的视频经常是「一个视频一个子文件夹」，所以必须往下钻子目录（最多 4 层），
// 上限 500 个文件防失控。返回 { name: 文件夹名, folder: 绝对路径, files: [绝对路径…] }，
// 用户取消则返回 null。
ipcMain.handle("pick-media-folder", async () => {
  const MEDIA_EXTS = new Set([
    ".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".wmv", ".m4v", ".ts",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".amr",
  ]);
  try {
    const r = await dialog.showOpenDialog(mainWindow, {
      title: "选择一个文件夹（会自动找出里面所有音/视频，包括子文件夹）",
      properties: ["openDirectory"],
    });
    if (r.canceled || !r.filePaths || !r.filePaths.length) return null;
    const root = r.filePaths[0];
    const files = [];
    const walk = (dir, depth) => {
      if (depth > 4 || files.length >= 500) return;
      let ents = [];
      try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return; }
      for (const ent of ents) {
        if (files.length >= 500) return;
        const p = path.join(dir, ent.name);
        if (ent.isDirectory()) {
          walk(p, depth + 1);
        } else if (ent.isFile()
                   && MEDIA_EXTS.has(path.extname(ent.name).toLowerCase())) {
          files.push(p);
        }
      }
    };
    walk(root, 0);
    files.sort();
    return { name: path.basename(root), folder: root, files };
  } catch (e) {
    return null;
  }
});
