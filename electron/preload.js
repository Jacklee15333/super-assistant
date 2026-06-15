// preload.js — 安全桥接层
// contextIsolation 开启时，渲染进程不能直接碰 Node。
// 这里只暴露一个最小的、安全的接口给前端。

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("crayfish", {
  getBackendPort: () => ipcRenderer.invoke("get-backend-port"),
  onBackendStatus: (cb) =>
    ipcRenderer.on("backend-status", (_e, ok) => cb(ok)),
});
