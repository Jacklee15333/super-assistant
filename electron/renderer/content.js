// content.js — 在视频页面右下角放一个悬浮的"提取"按钮。
// 点一下，就把当前页面网址发给本机的超能小助（127.0.0.1:8756）提取。

(function () {
  if (window.__cxFloatInjected) return;
  window.__cxFloatInjected = true;

  // ---- 悬浮按钮 ----
  const btn = document.createElement("div");
  btn.id = "cx-float-btn";
  btn.innerHTML = "🦞 提取视频";
  Object.assign(btn.style, {
    position: "fixed", right: "22px", bottom: "100px", zIndex: 2147483647,
    background: "#d65a3a", color: "#fff", padding: "10px 14px",
    borderRadius: "22px", fontSize: "14px", fontFamily: "Microsoft YaHei, sans-serif",
    boxShadow: "0 6px 18px rgba(0,0,0,.35)", cursor: "pointer", userSelect: "none",
    lineHeight: "1", transition: "transform .1s",
  });
  btn.title = "把这个视频发给超能小助提取（需要超能小助正在运行）";

  // 可拖动，避免挡住页面内容
  let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0, moved = false;
  btn.addEventListener("mousedown", (e) => {
    dragging = true; moved = false;
    sx = e.clientX; sy = e.clientY;
    const r = btn.getBoundingClientRect(); ox = r.left; oy = r.top;
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
    btn.style.left = (ox + dx) + "px";
    btn.style.top = (oy + dy) + "px";
    btn.style.right = "auto"; btn.style.bottom = "auto";
  });
  window.addEventListener("mouseup", () => { dragging = false; });

  function toast(text, ok) {
    const t = document.createElement("div");
    t.textContent = text;
    Object.assign(t.style, {
      position: "fixed", right: "22px", bottom: "150px", zIndex: 2147483647,
      background: ok ? "#2e7d32" : "#444", color: "#fff", padding: "9px 13px",
      borderRadius: "8px", fontSize: "13px", fontFamily: "Microsoft YaHei, sans-serif",
      boxShadow: "0 4px 14px rgba(0,0,0,.3)", maxWidth: "320px",
    });
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  btn.addEventListener("click", () => {
    if (moved) return;  // 拖动时不触发
    const url = location.href;
    btn.style.transform = "scale(.94)";
    setTimeout(() => (btn.style.transform = ""), 120);
    // 通过后台脚本发给本机超能小助（避开页面 CSP 限制）
    chrome.runtime.sendMessage({ type: "cx-extract", url }, (resp) => {
      if (chrome.runtime.lastError || !resp) {
        toast("发送失败：请确认超能小助正在运行", false);
        return;
      }
      if (resp.ok) {
        const pos = resp.position || 1;
        toast(pos > 1 ? `已加入超能小助队列（第 ${pos} 个）` : "已发给超能小助，开始提取！", true);
      } else if (resp.need) {
        toast("超能小助里还没装语音工具，请先在软件里点一次提取装好", false);
      } else {
        toast("没成功：" + (resp.error || "未知问题"), false);
      }
    });
  });

  document.body.appendChild(btn);
})();
