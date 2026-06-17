// main.js — Electron 主进程
// 职责：开一个独立桌面窗口，并在后台自动启动 Python 后端，退出时关掉它。

const { app, BrowserWindow, ipcMain, shell, Menu, nativeImage, clipboard, screen, globalShortcut } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

let mainWindow = null;
let backendProcess = null;

const BACKEND_PORT = 8756;
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
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 800,
    minHeight: 560,
    title: "超能小助",
    icon: appIcon.isEmpty() ? undefined : appIcon,
    backgroundColor: "#10100e",
    show: false,            // 先不显示，最大化后再显示，避免闪一下小窗
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 按默认窗口大小显示（不再自动最大化）
  mainWindow.show();

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));

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

  mainWindow.on("closed", () => { mainWindow = null; });
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

app.whenReady().then(async () => {
  // Windows 任务栏按这个 id 分组，配合窗口图标才能显示成自己的图标
  if (process.platform === "win32") {
    app.setAppUserModelId("com.you.crayfish");
  }
  buildChineseMenu();        // 把英文菜单换成中文
  startBackend();
  const ok = await waitForBackend();
  createWindow();
  registerHotkeys();         // 注册全局唤起热键
  startClipboardWatch();     // 监听剪贴板，复制视频链接时弹悬浮按钮
  // 把后端是否就绪告诉前端
  mainWindow.webContents.once("did-finish-load", () => {
    mainWindow.webContents.send("backend-status", ok);
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
app.on("before-quit", killBackend);
app.on("will-quit", () => { try { globalShortcut.unregisterAll(); } catch (_) {} });
app.on("window-all-closed", () => {
  killBackend();
  if (process.platform !== "darwin") app.quit();
});

// 暴露后端端口给前端
ipcMain.handle("get-backend-port", () => BACKEND_PORT);
