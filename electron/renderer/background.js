// background.js — 把内容脚本发来的网址，POST 给本机超能小助的后端。
// 后端监听 127.0.0.1:8756，已开启跨域，所以这里能直接调用。

const BACKEND = "http://127.0.0.1:8756";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "cx-extract" && msg.url) {
    fetch(BACKEND + "/video_transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: msg.url }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.need) {
          sendResponse({ ok: false, need: data.need });
        } else if (data.queued) {
          sendResponse({ ok: true, position: data.position });
        } else {
          sendResponse({ ok: false, error: data.error || "未知问题" });
        }
      })
      .catch((e) => sendResponse({ ok: false, error: e.message }));
    return true; // 异步响应
  }
});
