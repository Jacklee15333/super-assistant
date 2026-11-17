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

  // ---- 侧栏分组折叠（记住每组的展开/折叠状态）----
  const NAV_KEY = "cx.navCollapsed";
  let navState = null;
  try { navState = JSON.parse(localStorage.getItem(NAV_KEY) || "null"); } catch (e) { navState = null; }
  if (!navState) navState = { you: true, auto: true };   // 默认：常用的两组展开，其余折叠
  document.querySelectorAll(".nav-group").forEach((g) => {
    const key = g.dataset.group;
    const label = g.querySelector(".nav-group-label");
    const apply = (collapsed) => {
      g.classList.toggle("collapsed", collapsed);
      if (label) label.setAttribute("aria-expanded", String(!collapsed));
    };
    apply(!!navState[key]);
    if (label) label.addEventListener("click", () => {
      const collapsed = !g.classList.contains("collapsed");
      apply(collapsed);
      navState[key] = collapsed;
      try { localStorage.setItem(NAV_KEY, JSON.stringify(navState)); } catch (e) {}
    });
  });
  // 跳到的页面所在分组是折叠的（比如从别处一键跳过去），自动展开那一组
  const navEl = document.querySelector(".nav");
  if (navEl) new MutationObserver(() => {
    const act = document.querySelector(".nav-group.collapsed .nav-item.active");
    if (act) {
      const g = act.closest(".nav-group");
      g.classList.remove("collapsed");
      const l = g.querySelector(".nav-group-label");
      if (l) l.setAttribute("aria-expanded", "true");
    }
  }).observe(navEl, { subtree: true, attributes: true, attributeFilter: ["class"] });

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
