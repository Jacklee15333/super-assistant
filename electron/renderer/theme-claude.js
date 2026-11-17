// theme-claude.js — 配合 theme-claude.css 的几件小事（不碰任何业务逻辑）：
//   1) 左上角 ☰ 按钮：弹出原来的应用菜单（隐藏系统标题栏后菜单栏不再显示）
//   2) 右上角窗口按钮占位：给顶栏右侧留出空间，避免内容被最小化/关闭按钮盖住
//   3) 深浅色切换时，同步窗口按钮区域的底色
(function () {
  const api = window.crayfish || {};

  // ---- 1) ☰ 菜单 ----
  const menuBtn = document.getElementById("appMenuBtn");
  if (menuBtn) {
    menuBtn.addEventListener("click", () => {
      const r = menuBtn.getBoundingClientRect();
      if (api.popupAppMenu) {
        api.popupAppMenu({ x: r.left, y: r.bottom + 4 }).catch(() => {});
      }
    });
  }

  // 底部快捷操作只显示图标：把文字放进悬停提示
  document.querySelectorAll(".sidebar-foot .ghost-btn").forEach((b) => {
    if (!b.title) b.title = (b.textContent || "").trim();
  });

  // ---- 2) 窗口按钮占位 ----
  const wco = navigator.windowControlsOverlay;
  function layoutWco() {
    let w = 0;
    try {
      if (wco && wco.visible) {
        const rect = wco.getTitlebarAreaRect();
        w = Math.max(0, Math.round(window.innerWidth - (rect.x + rect.width)));
      }
    } catch (e) { w = 0; }
    if (!w && /Windows/i.test(navigator.userAgent) && api.popupAppMenu) w = 140;
    document.body.classList.toggle("wco", w > 0);
    document.body.style.setProperty("--wco-w", w + "px");   // 写在 body 上，优先于 CSS 里的默认值
  }
  layoutWco();
  if (wco && wco.addEventListener) wco.addEventListener("geometrychange", layoutWco);
  window.addEventListener("resize", layoutWco);

  // ---- 3) 标题栏底色跟随深浅色 ----
  let lastDark = null;
  function syncTitlebar() {
    const dark = document.body.classList.contains("dark");
    if (dark === lastDark) return;
    lastDark = dark;
    if (api.setTitlebarTheme) api.setTitlebarTheme(dark).catch(() => {});
  }
  syncTitlebar();
  new MutationObserver(syncTitlebar).observe(document.body, { attributes: true, attributeFilter: ["class"] });
})();
