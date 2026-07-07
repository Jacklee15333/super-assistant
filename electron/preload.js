// preload.js — 安全桥接层
// contextIsolation 开启时，渲染进程不能直接碰 Node。
// 这里只暴露一个最小的、安全的接口给前端。

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("crayfish", {
  getBackendPort: () => ipcRenderer.invoke("get-backend-port"),
  onBackendStatus: (cb) =>
    ipcRenderer.on("backend-status", (_e, ok) => cb(ok)),

  // 导入本地音/视频文件：弹原生选择框，返回选中文件的绝对路径数组
  pickMediaFiles: () => ipcRenderer.invoke("pick-media-files"),

  // 导入本地文件夹：弹目录选择框，自动递归找出里面所有音/视频文件
  // 返回 { name, folder, files } 或 null（用户取消）
  pickMediaFolder: () => ipcRenderer.invoke("pick-media-folder"),

  // 主窗里也能控制桌宠（设置面板用）：改形象 / 开关 / 让它说话 / 切换显示
  petApplyConfig: (patch) => ipcRenderer.invoke("pet-apply-config", patch),
  petToggle: () => ipcRenderer.invoke("pet-toggle"),
  petSay: (text) => ipcRenderer.invoke("pet-say", text),
  petBusy: (busy) => ipcRenderer.invoke("pet-busy", busy),
  petGetConfig: () => ipcRenderer.invoke("pet-get-config"),
});

// 桌宠窗口专用桥接（pet.html 用）
contextBridge.exposeInMainWorld("petBridge", {
  ready: () => ipcRenderer.invoke("pet-ready"),
  getWorkArea: () => ipcRenderer.invoke("pet-get-workarea"),
  getBounds: () => ipcRenderer.invoke("pet-get-bounds"),
  moveTo: (x, y) => ipcRenderer.invoke("pet-move-to", x, y),
  openMain: () => ipcRenderer.invoke("pet-open-main"),
  hidePet: () => ipcRenderer.invoke("pet-hide"),
  getConfig: () => ipcRenderer.invoke("pet-get-config"),
  setConfig: (patch) => ipcRenderer.invoke("pet-set-config", patch),
  feedFiles: (paths) => ipcRenderer.invoke("pet-feed-files", paths),
  feedText: (text) => ipcRenderer.invoke("pet-feed-text", text),
  onBusy: (cb) => ipcRenderer.on("pet-busy", (_e, busy) => cb(busy)),
  onConfig: (cb) => ipcRenderer.on("pet-config", (_e, cfg) => cb(cfg)),
  onSay: (cb) => ipcRenderer.on("pet-say", (_e, text) => cb(text)),
});
