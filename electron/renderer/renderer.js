// renderer.js — 前端交互逻辑
// 通过本地 HTTP 和 Python 后端通信。

// 注入「正在处理 / 排队中」视频名的折叠/展开样式：默认截断，悬停展开全部，移开折叠；
// 也可点击切换（点击逻辑在 renderVideoTasks 里）。
(function injectVtNameStyle() {
  try {
    if (document.getElementById("vt-name-style")) return;
    const s = document.createElement("style");
    s.id = "vt-name-style";
    s.textContent =
      ".vt-namewrap{font-size:13px;color:var(--text-dim,#8a8a93);margin-top:4px;" +
      "word-break:break-all;line-height:1.5}" +
      ".vt-name{cursor:pointer;border-bottom:1px dashed var(--border,#c9c9d0);" +
      "color:var(--text,#444);transition:color .15s}" +
      ".vt-name:hover{color:var(--accent,#2f6fed)}" +
      ".vt-name.expanded{border-bottom-style:solid}";
    (document.head || document.documentElement).appendChild(s);
  } catch (e) {}
})();

let BACKEND = "http://127.0.0.1:8756";
let messages = [];          // 喂给模型的完整历史
let busy = false;
// 本次对话里用户已授权「这类操作不用再问」的工具名集合（换对话时清空）
let sessionAllowedTools = new Set();
// 智能模式开关：true=按任务自动选模型；false=常规模式，只用所选模型。默认智能。
let smartRouting = (function () {
  try {
    const v = localStorage.getItem("cx_smart_routing");
    return v === null ? true : v === "1";
  } catch (_) { return true; }
})();

// 取后端端口（主进程提供）
async function initBackend() {
  try {
    const port = await window.crayfish.getBackendPort();
    BACKEND = `http://127.0.0.1:${port}`;
  } catch (_) {}
}

// 设置右上角模型状态亮点：true=绿，false=红，null=灰(未知)
function setStatusDot(state) {
  const dot = document.getElementById("statusDot");
  if (!dot) return;
  dot.classList.remove("ok", "bad");
  if (state === true) dot.classList.add("ok");
  else if (state === false) dot.classList.add("bad");
}

// ============================================================
//  后端就绪 → 自动恢复所有页面（冷启动「加载中…」永久卡死的修复）
//  问题背景：窗口先于后端出现，各页第一次 fetch 全部失败，停在「加载中…」。
//  老逻辑只重点「当前激活页」，别的页一直卡；而且 backend-status 只推一次，
//  若推送时前端还没挂上监听就彻底丢了 → 全部卡死。
//  现在：①后端一好就刷新「全部」页；②前端自己持续探活兜底，不依赖那一次推送。
// ============================================================

// 把所有数据页都重新加载一遍（每个都包在 try 里，单个失败不影响其它）
function reloadAllPanels() {
  const tries = [
    () => (typeof loadDashboard === "function") && document.getElementById("dashPane") && loadDashboard(),
    () => (typeof loadLibrary === "function") && document.getElementById("libBody") && loadLibrary(),
    () => (typeof loadLumi === "function") && document.getElementById("lumiProfile") && loadLumi(),
    () => (typeof loadDataDb === "function") && document.getElementById("ddbBody") && loadDataDb(),
    () => (typeof loadVideoNotes === "function") && document.getElementById("cwVideos") && loadVideoNotes(),
    () => (typeof loadSkills === "function") && document.getElementById("skillsGrid") && loadSkills(),
    () => (typeof loadAgents === "function") && document.getElementById("agentsRoot") && loadAgents(),
    () => (typeof loadSniff === "function") && document.getElementById("sniffSources") && loadSniff(),
    () => (typeof loadModelsInfo === "function") && document.getElementById("modelsDirText") && loadModelsInfo(),
    () => (typeof loadMemoryTabs === "function") && loadMemoryTabs(),
  ];
  tries.forEach((fn) => { try { fn(); } catch (e) {} });
  // 兜底：再把当前激活页触发一次，确保用户正看着的那页一定刷新
  try { document.querySelector(".nav-item.active")?.click(); } catch (e) {}
}

// v54：左上角显示版本号，方便确认更新是否成功加载
let _appVersion = "";
async function showAppVersion() {
  try {
    if (!_appVersion) {
      const r = await fetch(BACKEND + "/version", { cache: "no-store" });
      const d = await r.json();
      _appVersion = d.version || "";
      if (_appVersion) console.log("[超能小助] 版本 " + _appVersion + (d.note ? "：" + d.note : ""));
    }
    const line = document.getElementById("statusLine");
    if (line && _appVersion && line.textContent.startsWith("已就绪")) {
      line.textContent = "已就绪 · " + _appVersion;
      line.title = "当前版本 " + _appVersion;
    }
  } catch (_) {}
}

let _backendReadyOnce = false;
function onBackendReady() {
  const line = document.getElementById("statusLine");
  if (line) {
    line.textContent = "已就绪";
    line.style.color = "var(--text-dim)";
  }
  showAppVersion();
  setStatusDot(true);
  maybeGreetOnce();
  if (!_backendReadyOnce) {
    _backendReadyOnce = true;
    reloadAllPanels();   // ← 关键：刷新「全部」页，而不只是当前页
    try { termAfterBackendReady(); } catch (e) {}
  }
}

// 主进程推来的状态（可能因时序问题收不到，所以下面还有前端自己的轮询兜底）
window.crayfish?.onBackendStatus((ok) => {
  if (ok) {
    onBackendReady();
  } else {
    const line = document.getElementById("statusLine");
    if (line) { line.textContent = "后端未连接"; line.style.color = "var(--accent)"; }
    setStatusDot(false);
  }
});

// 前端自助探活：不依赖主进程那一次性的推送。每 1.5 秒 ping 一次后端，
// 一通就走 onBackendReady()（内部有 _backendReadyOnce 去重，不会重复刷）。
// 通了之后降速到每 15 秒做一次健康检查（断了能把状态点变红）。
(function startBackendHealthLoop() {
  let connected = false;
  async function tick() {
    let ok = false;
    try {
      const r = await fetch(BACKEND + "/ping", { cache: "no-store" });
      ok = r && r.ok;
    } catch (_) { ok = false; }

    if (ok && !connected) {
      connected = true;
      onBackendReady();
    } else if (!ok && connected) {
      connected = false;
      const line = document.getElementById("statusLine");
      if (line) { line.textContent = "后端未连接"; line.style.color = "var(--accent)"; }
      setStatusDot(false);
    } else if (!ok && !connected) {
      const line = document.getElementById("statusLine");
      if (line && !line.textContent) line.textContent = "正在连接后端…";
    }
    setTimeout(tick, connected ? 15000 : 1500);
  }
  // initBackend() 先把端口拿到，再开始探活，避免一开始 ping 错端口
  if (typeof initBackend === "function") {
    initBackend().then(() => setTimeout(tick, 300)).catch(() => setTimeout(tick, 300));
  } else {
    setTimeout(tick, 300);
  }
})();

// 后端首次就绪时，显示一句个性化问候（只显示一次；没画像/记忆时后端会给通用问候）
let _greeted = false;
async function maybeGreetOnce() {
  if (_greeted) return;
  _greeted = true;
  try {
    const s = (typeof settings === "function") ? settings() : { use_local: true, model: "qwen3:14b" };
    const r = await fetch(BACKEND + "/lumi/greeting", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (d && d.greeting && typeof addBubble === "function") {
      // 只在对话还空着的时候打个招呼，不打断已有对话
      const msgs = document.getElementById("messages");
      if (msgs && msgs.children.length === 0) addBubble("assistant", d.greeting);
    }
  } catch (e) { /* 静默 */ }
}

// ---------- 视图切换 ----------
// v110：左栏只放常用入口。同类的几页合成一组（页面顶部用标签切换），不常用的收进「待开发」。
// 每一页原来的入口（.nav-item[data-view=...]）都还在左栏里，只是藏起来了：别处代码 .click() 它来跳页，
// 照旧切页；切完由 navSync() 把左栏高亮落到对应的组上，并在页面顶部画出组名和标签。
const NAV_GROUPS = {
  sniff: { title: "嗅探", tabs: [
    { key: "creators", label: "博主新视频", view: "sniff", sn: "creators" },
    { key: "web", label: "网站新动态", view: "sniff", sn: "web" },
    { key: "trend", label: "信息源推荐", view: "trendwatch" },
  ] },
  data: { title: "资料库", tabs: [
    { key: "list", label: "列表", view: "datadb" },
    { key: "cloud", label: "云图", view: "knowledge" },
  ] },
  you: { title: "懂你", parkedIn: "lab", tabs: [
    { key: "profile", label: "画像", view: "lumi", sub: "profile" },
    { key: "insight", label: "洞察", view: "lumi", sub: "insight" },
    { key: "memory", label: "记忆", view: "memory" },
  ] },
  crew: { title: "分身与技能", parkedIn: "lab", tabs: [
    { key: "agents", label: "分身", view: "agents" },
    { key: "skills", label: "技能", view: "skills" },
  ] },
  // 待开发：没有标签；从这里打开的页面，左上角有「待开发 /」可以点回来
  lab: { title: "待开发", home: "lab", parked: ["loop", "harness", "pet", "study", "dashboard", "library"] },
};

// 这一页属于哪一组、哪个标签（不属于任何组就返回 null，比如对话、视频、设置）
function navFind(view, sub) {
  for (const g of Object.keys(NAV_GROUPS)) {
    const G = NAV_GROUPS[g];
    if (G.tabs) {
      const cands = G.tabs.filter((t) => t.view === view);
      if (!cands.length) continue;
      if (view === "sniff") {
        const cur = (document.querySelector("#snTabs .sn-tab.active") || {}).dataset?.sntab || "creators";
        return { g, tab: cands.find((t) => t.sn === cur) || cands[0] };
      }
      if (view === "lumi") {
        const want = sub === "insight" ? "insight" : "profile";   // 人格演化并进了画像
        return { g, tab: cands.find((t) => t.sub === want) || cands[0] };
      }
      return { g, tab: cands[0] };
    }
    if (view === G.home || (G.parked || []).includes(view)) return { g, tab: null };
  }
  return null;
}

// 跳到某一页（点它原来的入口，各页自己的加载逻辑照常跑）
function navGo(view, sub) {
  const b = document.querySelector('.nav-item[data-view="' + view + '"]' + (sub ? '[data-lumi-sub="' + sub + '"]' : ""));
  if (b) b.click();
}

// 打开一组：指定了标签就去那个标签，否则回到上次看的标签
function navOpenGroup(g, key) {
  const G = NAV_GROUPS[g];
  if (!G) return;
  if (!G.tabs) { navGo(G.home); return; }
  let t = key ? G.tabs.find((x) => x.key === key) : null;
  if (!t) {
    let saved = null;
    try { saved = localStorage.getItem("cx.navTab." + g); } catch (e) {}
    t = G.tabs.find((x) => x.key === saved) || G.tabs[0];
  }
  navGo(t.view, t.sub);
  if (t.sn) {
    const b = document.querySelector('#snTabs .sn-tab[data-sntab="' + t.sn + '"]');
    if (b && !b.classList.contains("active")) b.click();
    navSync("sniff");
  }
}

// 左栏高亮 + 记住这一组上次看的标签 + 画页面顶部的组名和标签
function navSync(view, sub) {
  const hit = navFind(view, sub);
  document.querySelectorAll(".sidebar .nav-item").forEach((b) => b.classList.remove("active"));
  const vis = hit
    ? document.querySelector('.sidebar .nav-item[data-nav-group="' + (NAV_GROUPS[hit.g].parkedIn || hit.g) + '"]')
    : Array.from(document.querySelectorAll('.sidebar .nav-item[data-view="' + view + '"]')).find((b) => !b.closest(".nav-legacy") &&
        (view !== "video" || (b.dataset.videoMode || "extract") === (document.getElementById("view-video")?.dataset.mode || "extract")));
  if (vis) vis.classList.add("active");
  document.body.classList.toggle("on-chat", view === "chat");
  if (hit && hit.tab) { try { localStorage.setItem("cx.navTab." + hit.g, hit.tab.key); } catch (e) {} }
  pgMount(view, hit);
}

function pgMount(view, hit) {
  if (!hit) return;
  const G = NAV_GROUPS[hit.g];
  const sec = document.getElementById("view-" + view);
  if (!sec || (!G.tabs && view === G.home)) return;
  let hdr = sec.querySelector(":scope > header.topbar");
  if (!hdr) {   // 分身、知识云图这几页原来没有顶栏：补一条
    hdr = document.createElement("header");
    hdr.className = "topbar pg-made";
    sec.insertBefore(hdr, sec.firstChild);
    sec.classList.add("pg-has-top");
  }
  let head = hdr.querySelector(":scope > .pg-head");
  if (!head) {
    head = document.createElement("div");
    head.className = "pg-head";
    hdr.insertBefore(head, hdr.firstChild);
  }
  if (G.tabs) {
    hdr.classList.add("pg-has-head");
    head.innerHTML = (G.parkedIn ? '<button type="button" class="pg-back" title="回到待开发">待开发</button><span class="pg-sep">/</span>' : "") +
      '<span class="pg-title">' + G.title + '</span><span class="pg-tabs" role="tablist">' +
      G.tabs.map((t) => {
        const on = t.key === hit.tab.key;
        return '<button type="button" role="tab" class="pg-tab' + (on ? " active" : "") + '" aria-selected="' + on +
          '" data-pg-group="' + hit.g + '" data-pg-tab="' + t.key + '">' + t.label + "</button>";
      }).join("") + "</span>";
  } else {
    hdr.classList.add("pg-has-back");
    head.innerHTML = '<button type="button" class="pg-back" title="回到待开发">待开发</button><span class="pg-sep">/</span>';
  }
}

document.addEventListener("click", (e) => {
  const t = e.target.closest && e.target.closest(".pg-tab, .pg-back");
  if (!t) return;
  if (t.classList.contains("pg-back")) navOpenGroup("lab");
  else navOpenGroup(t.dataset.pgGroup, t.dataset.pgTab);
});

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.navGroup) { navOpenGroup(btn.dataset.navGroup); return; }
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "memory") { loadMemoryTabs(); }
    if (btn.dataset.view === "dashboard") loadDashboard();
    if (btn.dataset.view === "video") { setVideoMode(btn.dataset.videoMode || "extract"); loadVideoNotes(); pollVideoProgress(); }
    if (btn.dataset.view === "datadb") { if (typeof loadDataDb === "function") loadDataDb(); }
    if (btn.dataset.view === "library") loadLibrary();
    if (btn.dataset.view === "lumi") { loadLumi(); }
    if (btn.dataset.view === "skills") { loadSkills(); }
    if (btn.dataset.view === "agents") { if (typeof loadAgents === "function") loadAgents(); }
    if (btn.dataset.view === "loop") { loadLoop(); }
    if (btn.dataset.view === "harness") { loadHarness(); }
    if (btn.dataset.view === "sniff") { loadSniff(); }
    if (btn.dataset.view === "pet") { if (typeof loadPetSettings === "function") loadPetSettings(); }
    if (btn.dataset.view === "knowledge") { if (typeof window.loadKnowledge === "function") window.loadKnowledge(); }
    else { if (typeof window.pauseKnowledge === "function") window.pauseKnowledge(); }
    if (btn.dataset.view === "settings") { refreshHeartbeatStatus(); loadModelsInfo(); loadWebModelConfig(); loadTaskModels(); loadProxySetting(); }
    // 懂你的三个子项（画像/洞察/人格）：切到 lumi 视图后，触发对应的隐藏子菜单项，
    // 复用 crawler.js / evolution.js 已有的切页逻辑。
    if (btn.dataset.view === "lumi") {
      const sub = btn.dataset.lumiSub || "profile";
      const hidden = document.querySelector('#lumiSubNav .nav-subitem[data-lumi="' + sub + '"]');
      if (hidden) hidden.click();   // 驱动各模块的显隐 + setLumiTopbarButtons
    } else {
      // 离开懂你：把这几个懂你专属按钮都藏起来，免得别的视图顶栏残留
      ["lumiScanBtn", "crwRunBtn"].forEach((id) => {
        const el = document.getElementById(id); if (el) el.style.display = "none";
      });
    }
    navSync(btn.dataset.view, btn.dataset.lumiSub || "");
  });
});

// 嗅探页里切「博主新视频 / 网站新动态」时，顶部标签跟着变
document.getElementById("snTabs")?.addEventListener("click", () => {
  setTimeout(() => {
    if (document.getElementById("view-sniff")?.classList.contains("active")) navSync("sniff");
  }, 0);
});

// ── v116：提取 → 加工 → 笔记，是同一页的三种样子 ──
// 提取：放进来、处理进度、提取失败、历史（提取出来的半成品）；加工：批量 AI 分析（总结、打标签分类）；
// 笔记：分析好的成品（博主、文件夹）。几块内容还是在笔记列表里画，画完搬到各自的页。
const VIDEO_MODE_TITLE = { extract: "", process: "加工", notes: "笔记" };   // v117：提取页顶上不写标题
function setVideoMode(mode) {
  const v = document.getElementById("view-video");
  if (!v) return;
  if (!(mode in VIDEO_MODE_TITLE)) mode = "extract";
  if (v.dataset.mode && v.dataset.mode !== mode && typeof vnReaderIsOpen === "function" && vnReaderIsOpen()) {
    try { vnReaderClose(); } catch (e) {}
  }
  v.dataset.mode = mode;
  Object.keys(VIDEO_MODE_TITLE).forEach((k) => v.classList.toggle("vmode-" + k, k === mode));
  const t = document.getElementById("videoPageTitle");
  if (t) t.textContent = VIDEO_MODE_TITLE[mode];
  if (mode === "process") {   // 加工页：批量 AI 分析默认展开
    try { localStorage.setItem("vnBatchOpen", "1"); } catch (e) {}
    const body = document.getElementById("vnBatchBody");
    if (body && body.hidden) document.querySelector("#vnBatchBar .vn-batch-head")?.click();
  }
}
setVideoMode("extract");

// ── v117：工具卡片里的「视频设置」：收起时标题行写着现在选的是什么 ──
function viSecSum() {
  const sum = document.getElementById("viVideoSum");
  if (!sum) return;
  const txt = (id) => { const s = document.getElementById(id); return s && s.selectedOptions && s.selectedOptions[0] ? s.selectedOptions[0].textContent.trim() : ""; };
  const parts = [txt("videoLevel"), txt("videoLang")].filter(Boolean);
  const dep = document.getElementById("videoDepBadge");   // v118：维护工具也在「设置」里：有新版 / 缺组件时标题行就能看到
  if (dep && !dep.hidden && dep.textContent.trim()) parts.push(dep.textContent.trim());
  if (document.getElementById("videoTidyAuto")?.checked) parts.push("整理原文");
  if (document.getElementById("videoVocal")?.checked) parts.push("分离人声");
  if ((document.getElementById("videoCreatorUrl")?.value || "").trim()) parts.push("填了博主主页");
  sum.textContent = parts.join(" · ");
  const gear = document.getElementById("viGearBtn");
  if (gear) {
    gear.title = "设置：" + parts.join(" · ");
    const d = document.getElementById("videoDepBadge");
    gear.classList.toggle("has-alert", !!(d && !d.hidden && d.textContent.trim() && !/已是最新/.test(d.textContent)));
  }
}
(function () {
  const sec = document.getElementById("viVideoSec");
  if (!sec) return;
  const head = sec.querySelector(".vi-sec-head"), body = sec.querySelector(".vi-sec-body"), caret = sec.querySelector(".vi-sec-caret");
  const apply = (open) => { body.hidden = !open; caret.textContent = open ? "▾" : "▸"; sec.classList.toggle("open", open); };
  let open0 = false;
  try { open0 = localStorage.getItem("viVideoSecOpen") === "1"; } catch (e) {}
  apply(open0);
  const toggle = () => { const o = body.hidden; apply(o); try { localStorage.setItem("viVideoSecOpen", o ? "1" : "0"); } catch (e) {} };
  head.addEventListener("click", toggle);
  head.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  // v119：设置改成「提取」标题右边的齿轮（点了不要顺带把整张卡片收起来）
  const gear = document.getElementById("viGearBtn");
  if (gear) {
    gear.addEventListener("click", (e) => {
      e.stopPropagation();
      const card = gear.closest(".v-card-extract");
      if (card && card.classList.contains("v-collapsed") && typeof vExtractSetCollapsed === "function") vExtractSetCollapsed(false);
      toggle();
    });
    new MutationObserver(() => gear.setAttribute("aria-expanded", String(!body.hidden))).observe(body, { attributes: true, attributeFilter: ["hidden"] });
  }
  sec.addEventListener("change", viSecSum);
  sec.addEventListener("input", viSecSum);
  [300, 1500, 4000].forEach((ms) => setTimeout(viSecSum, ms));   // 语言、整理原文这几项是后加进来的
  const dep = document.getElementById("videoDepBadge");
  if (dep) new MutationObserver(viSecSum).observe(dep, { childList: true, characterData: true, subtree: true, attributes: true });
  // 缺组件提醒里的「打开维护工具」：先把「设置」展开
  document.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("#videoNoticeOpen") && body.hidden) apply(true);
  }, true);
})();
(function () {
  const list = document.getElementById("videoNotesList");
  if (!list) return;
  const PLACE = [["vnFailBar", "viExtractExtras"], ["vnRecent", "viExtractExtras"], ["vnBatchBar", "viProcessBars"]];
  new MutationObserver(() => {
    PLACE.forEach(([id, to]) => {
      const el = list.querySelector(":scope > #" + id), dest = document.getElementById(to);
      if (!el || !dest) return;
      const old = dest.querySelector(":scope > #" + id);
      if (old) old.remove();
      dest.appendChild(el);
    });
    const lv = document.querySelector("#viProcessBars #vnLive"), lslot = document.getElementById("viAnLive");   // v120
    if (lv && lslot) { const o = lslot.querySelector(":scope > #vnLive"); if (o && o !== lv) o.remove(); lslot.appendChild(lv); }
    const ex = document.getElementById("viExtractExtras"), f = ex && ex.querySelector(":scope > #vnFailBar");
    if (f && f !== ex.firstElementChild) ex.insertBefore(f, ex.firstElementChild);   // 提取失败放在历史上面
  }).observe(list, { childList: true });
})();
document.addEventListener("click", (e) => {
  const g = e.target.closest && e.target.closest("[data-video-goto]");
  if (!g) return;
  document.querySelector('.sidebar .nav-item[data-view="video"][data-video-mode="' + g.dataset.videoGoto + '"]')?.click();
});

// 打开「设置 → 配置」里的某个文件（待开发、通知页上的按钮用）
function openConfigFile(name) {
  navGo("settings");
  if (MEMORY_FILES_CFG.includes(name)) _cfgCurrentFile = name;
  document.querySelector('#settingsTabs .settings-tab-btn[data-tab="tab-config"]')?.click();
}

// 待开发页：打开某页 / 去改配置 / 展开收起
document.addEventListener("click", (e) => {
  const sc = e.target.closest && e.target.closest("#lumiScanInline");
  if (sc) {   // 扫描环境时把结果那一栏展开，免得扫完看不见
    const row = sc.closest(".lab-row");
    const bd = row && row.querySelector(".lab-body");
    if (bd && bd.hidden) { bd.hidden = false; const tg = row.querySelector("[data-lab-toggle]"); if (tg) tg.textContent = "收起"; }
    return;
  }
  const o = e.target.closest && e.target.closest("[data-lab-open], [data-lab-group], [data-open-cfg], [data-lab-toggle]");
  if (!o) return;
  if (o.dataset.labGroup) { navOpenGroup(o.dataset.labGroup); return; }
  if (o.dataset.labOpen) { navGo(o.dataset.labOpen); return; }
  if (o.dataset.openCfg) { openConfigFile(o.dataset.openCfg); return; }
  const bd = o.closest(".lab-row") && o.closest(".lab-row").querySelector(".lab-body");
  if (!bd) return;
  bd.hidden = !bd.hidden;
  o.textContent = bd.hidden ? "展开" : "收起";
  if (!bd.hidden && typeof loadLumi === "function") loadLumi();
});

// ---------- 聊天 ----------
const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");

function addBubble(role, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(text);  // 助手消息渲染 Markdown
  } else {
    bubble.textContent = text;  // 用户消息保持纯文本，防注入
  }
  bubble.dataset.raw = text || "";            // 朗读用的原文
  wrap.appendChild(bubble);
  if (role === "assistant") {
    // 喇叭直接跟在这段话末尾（塞进最后一个文字块里，而不是另起一行）
    const sp = makeSpeakBtn();
    const blocks = bubble.querySelectorAll("p, li, h1, h2, h3, h4, blockquote");
    const last = blocks.length ? blocks[blocks.length - 1] : null;
    if (last && !last.querySelector("pre, img")) last.appendChild(sp);
    else bubble.appendChild(sp);
    // 如果助手在问「是/否」之类的问题，给出可点击的快捷回复按钮，省得用户打字
    const quick = makeQuickReplies(text);
    if (quick) wrap.appendChild(quick);
  }
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

// 这一轮（从最后一条用户消息往后）有没有真正执行过工具 / 操作过电脑。
// 用来判断是不是"任务型"对话——是的话跑完给一个明确的"已完成"反馈。
function turnUsedTools(msgs) {
  if (!msgs || !msgs.length) return false;
  let lastUser = -1;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i] && msgs[i].role === "user") { lastUser = i; break; }
  }
  for (let i = lastUser + 1; i < msgs.length; i++) {
    if (msgs[i] && msgs[i].role === "tool") return true;
  }
  return false;
}

// 任务完成的明确反馈条："✓ 已完成"（网页模型当 agent 时尤其有用，能一眼看出它收工了）。
function addCompletionMarker() {
  const wrap = document.createElement("div");
  wrap.className = "msg assistant task-done";
  wrap.innerHTML =
    '<div class="task-done-chip" style="display:inline-flex;align-items:center;' +
    'gap:6px;padding:5px 14px;border-radius:14px;background:#e7f6ec;' +
    'color:#1b873f;font-size:13px;font-weight:600;border:1px solid #bfe6cb;">' +
    '<span style="font-size:14px;">✓</span><span>已完成</span></div>';
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 根据助手回复里的提问，生成可点击的快捷回复按钮（点了直接当成用户输入发出去）。
// 目的：工作流程里尽量让用户「点」而不是「打字」。
function makeQuickReplies(text) {
  const t = (text || "").trim();
  if (!t) return null;
  // 只看结尾部分（问题通常在最后一句）
  const tail = t.slice(-60);
  let options = null;

  // 明确的「是/否」信号（避免对开放式提问也弹是否）
  const yesNoPat = /(是否|要不要|需不需要|确认.*吗|继续吗|可以吗|好吗|对吗|要我.*吗|帮你.*吗|是或否|确定吗|开始吗|执行吗|清空吗|删除吗)/;
  if (yesNoPat.test(tail)) {
    options = ["是", "否"];
  }
  // 「请回复 是 或 否」这种显式提示
  if (/请回复\s*[“"']?\s*是\s*[”"']?\s*(或|还是|\/|、)\s*[“"']?\s*否/.test(t)) {
    options = ["是", "否"];
  }

  if (!options) return null;

  const row = document.createElement("div");
  row.className = "quick-replies";
  options.forEach((opt) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "quick-reply-btn";
    b.textContent = opt;
    b.addEventListener("click", () => {
      if (busy) return;
      // 点击后禁用这一组按钮，避免重复点
      row.querySelectorAll(".quick-reply-btn").forEach((x) => { x.disabled = true; });
      b.classList.add("chosen");
      // 直接当成用户输入发送
      inputEl.value = opt;
      send();
    });
    row.appendChild(b);
  });
  return row;
}

// 行内喇叭按钮：直接跟在助手这段话的末尾，只有图标、没有「朗读」二字。
// 仍用 .speak-btn 类，点击交给下面的事件委托。
function makeSpeakBtn() {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "speak-btn speak-inline";
  btn.title = "朗读这段";
  btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a9 9 0 0 1 0 14"/></svg>';
  return btn;
}

// 轻量 Markdown 渲染：标题/粗体/斜体/行内代码/代码块/列表/链接。
// 先转义 HTML 再套规则，避免 XSS。不引入外部库。
function renderMarkdown(src) {
  let s = escapeHtml(src || "");
  // 代码块 ```
  s = s.replace(/```([\s\S]*?)```/g, (_, code) =>
    `\u0002<pre class="code-block">${code.replace(/^\n/, "")}</pre>\u0002`);
  // 行内代码 `x`
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  // 标题 #### ##### ###### 先处理多级，再到少级，避免误伤
  s = s.replace(/^###### (.+)$/gm, "<h6>$1</h6>");
  s = s.replace(/^##### (.+)$/gm, "<h5>$1</h5>");
  s = s.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  s = s.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  s = s.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  s = s.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  // 分隔线 --- ：界面从简，不画横线（模型偶尔会输出 ---，渲染成横线显得乱）
  s = s.replace(/^\s*---+\s*$/gm, "");
  // 粗体 **x**
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  // 斜体 *x*
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  // 图片 ![alt](url) —— 必须在「链接」规则之前处理（否则 ![]() 里的 []() 会先被当成链接）。
  // 只允许 http(s) 图片地址（含本机 127.0.0.1 的截图地址），避免注入。
  s = s.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g,
    '<img class="md-img" src="$2" alt="$1" loading="lazy">');
  // 链接 [text](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank">$1</a>');
  // 裸链接（行内直接出现的 http(s) 网址）也变成可点击
  s = s.replace(/(^|[\s>])(https?:\/\/[^\s<）)]+)/g,
    '$1<a href="$2" target="_blank">$2</a>');
  // 表格 | a | b |\n| --- | --- |\n| 1 | 2 |
  // 识别连续的表格行（含表头分隔行），渲染成 <table>
  s = s.replace(
    /(^\|.+\|[ \t]*\n)(\|[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|[ \t]*\n)((?:\|.*\|[ \t]*\n?)*)/gm,
    (m, header, _sep, body) => {
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(header);
      const rows = body.trim().split("\n").filter((r) => r.trim()).map(cells);
      let html = '\u0002<table class="md-table"><thead><tr>';
      head.forEach((h) => { html += "<th>" + h + "</th>"; });
      html += "</tr></thead><tbody>";
      rows.forEach((r) => {
        html += "<tr>";
        head.forEach((_, i) => { html += "<td>" + (r[i] || "") + "</td>"; });
        html += "</tr>";
      });
      html += "</tbody></table>\u0002";
      return html;
    });
  // 有序列表 1. 2. 3.（保留真实序号：项与项之间夹了解释段落时，也不会都从 1 开始）
  s = s.replace(/^(\d+)\.\s+(.+)$/gm, "\u0003<oli data-n=\"$1\">$2</oli>");
  s = s.replace(/(\u0003<oli[\s\S]*?<\/oli>)(?:\n?\u0003<oli[\s\S]*?<\/oli>)*/g,
    (m) => {
      const first = (m.match(/data-n="(\d+)"/) || [, "1"])[1];
      const inner = m.replace(/\u0003/g, "").replace(/\n/g, "")
        .replace(/<oli data-n="\d+">/g, "<li>").replace(/<\/oli>/g, "</li>");
      return '<ol start="' + first + '">' + inner + "</ol>";
    });
  s = s.replace(/\u0003/g, "").replace(/<\/?oli[^>]*>/g, "");
  // 无序列表：先把连续的 - / * 行标成 li，再把相邻 li 包进一个 ul
  s = s.replace(/^[\-\*] (.+)$/gm, "\u0001<li>$1</li>");
  s = s.replace(/(\u0001<li>[\s\S]*?<\/li>)(?:\n?\u0001<li>[\s\S]*?<\/li>)*/g,
    (m) => "<ul>" + m.replace(/\u0001/g, "").replace(/\n/g, "") + "</ul>");
  s = s.replace(/\u0001/g, "");
  // 段落：用双换行分段，包成 <p>；单换行变 <br>
  const blocks = s.split(/\n{2,}/).map((blk) => {
    const t = blk.trim();
    if (!t) return "";
    // 已经是块级元素就不再包 <p>
    if (/^<(h[1-6]|ul|ol|pre|hr|blockquote)/.test(t) || t.includes("\u0002")) {
      return t.replace(/\n/g, "<br>");
    }
    return "<p>" + t.replace(/\n/g, "<br>") + "</p>";
  });
  s = blocks.join("\n");
  s = s.replace(/\u0002/g, "");
  // 清掉块级标签周围多余的 <br>
  s = s.replace(/<br>\s*(<(h[1-6]|ul|ol|pre|hr|p))/g, "$1");
  s = s.replace(/(<\/(h[1-6]|ul|ol|pre|p)>|<hr>)\s*<br>/g, "$1");
  return s;
}

// 工具中文名（让折叠条的标题像人话，而不是 sys_run 这种）
const _TOOL_LABEL_CN = {
  shell: "执行命令", sys_run: "执行命令",
  write_file: "写入文件", delete_file: "删除文件", write_memory: "写入记忆",
  fs_open: "打开文件", fs_move: "移动/重命名", fs_copy: "复制文件",
  fs_mkdir: "新建文件夹", fs_trash: "移到回收站", fs_organize: "整理文件夹",
  fs_list: "查看目录", fs_read: "读取文件", fs_search: "搜索文件",
  sys_info: "查看系统信息", sys_processes: "查看进程", sys_kill: "结束进程",
  sys_clean_temp: "清理临时文件", empty_recycle_bin: "清空回收站", sys_volume: "调整音量", sys_brightness: "调整亮度",
  sys_open_settings: "打开系统设置",
  gui_screenshot: "屏幕截图", screen_read: "识别屏幕文字", gui_open_app: "打开程序",
  gui_click: "点击鼠标", gui_type: "输入文字", gui_press: "按键", gui_scroll: "滚动",
  web_search: "联网搜索", search_web: "联网搜索", research: "深度调研",
  read_webpage: "读取网页", video_transcript: "提取视频文字",
  read_memory: "读取记忆", list_memory: "翻看记忆", append_note: "记笔记",
  remember: "记住", add_reminder: "设置提醒", list_reminders: "查看提醒",
  read_file: "读取文件", list_files: "浏览文件", search_files: "搜索文件",
  get_time: "查询时间", calc: "计算",
};

function addToolCall(name, args, result) {
  const el = document.createElement("div");
  el.className = "tool-call collapsed";

  const label = _TOOL_LABEL_CN[name] || name;
  const resStr = String(result == null ? "" : result);
  // 结果首行做预览（去掉换行，截断）
  const firstLine = (resStr.split("\n").find((l) => l.trim()) || "").trim();
  const preview = firstLine.length > 40 ? firstLine.slice(0, 40) + "…" : firstLine;

  // 折叠条：图标 + 中文名 + 一句结果预览 + 展开箭头
  const header = document.createElement("div");
  header.className = "tc-header";
  header.innerHTML =
    `<span class="tc-icon">🔧</span>` +
    `<span class="tc-label">${escapeHtml(label)}</span>` +
    (preview ? `<span class="tc-preview">${escapeHtml(preview)}</span>` : "") +
    `<span class="tc-chevron">▾</span>`;

  // 展开后的详情：完整参数 + 完整结果
  const body = document.createElement("div");
  body.className = "tc-body";
  let detailHtml = "";
  try {
    const argStr = JSON.stringify(args, null, 2);
    if (argStr && argStr !== "{}") {
      detailHtml += `<div class="tc-section-label">参数</div><pre class="tc-pre">${escapeHtml(argStr)}</pre>`;
    }
  } catch (_) {}
  if (resStr) {
    detailHtml += `<div class="tc-section-label">结果</div><pre class="tc-pre">${escapeHtml(resStr)}</pre>`;
  }
  body.innerHTML = detailHtml || '<div class="tc-empty">（无输出）</div>';

  el.appendChild(header);
  el.appendChild(body);
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 事件委托：让折叠条在「切换/恢复对话后」(innerHTML 重建、监听器丢失) 仍能点击展开
messagesEl.addEventListener("click", (e) => {
  const header = e.target.closest && e.target.closest(".tc-header");
  if (header) {
    const card = header.closest(".tool-call");
    if (card) card.classList.toggle("collapsed");
  }
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function currentModel() {
  // 手动输入框可见时用它，否则用下拉选中的值
  const manual = document.getElementById("modelName");
  const sel = document.getElementById("modelSelect");
  if (manual && manual.style.display !== "none" && manual.value.trim()) {
    return manual.value.trim();
  }
  if (sel && sel.value) return sel.value;
  if (manual && manual.value.trim()) return manual.value.trim();
  return "qwen3:14b";  // 启动默认本地模型
}

function settings() {
  return {
    use_local: document.getElementById("useLocal").checked,
    model: currentModel(),
    shell_enabled: document.getElementById("shellEnabled").checked,
  };
}

async function send() {
  const text = inputEl.value.trim();
  if (!text || busy) return;
  busy = true;
  sendBtn.disabled = true;

  addBubble("user", text);
  messages.push({ role: "user", content: text });
  inputEl.value = "";
  autoGrow();

  await runChatLoop({});
}

// 跑一轮对话，处理危险操作确认的挂起/续跑
async function runChatLoop(approvals) {
  // 给这次对话发一个唯一 id，后端按它播报实时进度，前端轮询显示
  const chatId = "chat" + Date.now() + "-" +
                 Math.random().toString(36).slice(2, 7);
  const prog = addLiveProgress(chatId);

  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages, approvals, chat_id: chatId,
        auto_approve_tools: Array.from(sessionAllowedTools),
        smart_routing: smartRouting,
        ...s,
      }),
    });
    const data = await resp.json();
    prog.done();

    (data.tool_calls || []).forEach((tc) =>
      addToolCall(tc.name, tc.args, tc.result));
    if (data.messages) messages = data.messages;

    if (data.pending) {
      // 遇到危险操作，弹确认框
      askApproval(data.pending);
      return;  // 等用户点完再续跑
    }

    addBubble("assistant", data.reply || "（无回复）");
    // 任务型对话（用到了工具 / 操作了电脑）跑完时，给一个明确的"✓ 已完成"反馈，
    // 让用户一眼看出 AI 已收工（网页模型偏慢，这点尤其重要）。
    if (turnUsedTools(messages)) addCompletionMarker();
    saveCurrentConversation();
    busy = false;
    sendBtn.disabled = false;
    inputEl.focus();
  } catch (e) {
    prog.done();
    addBubble("assistant", "连不上后端：" + e.message +
      "\n确认 Python 后端在运行，模型已就绪。");
    busy = false;
    sendBtn.disabled = false;
  }
}

// 危险操作确认框（支持批量 + 友好说明 + 本次免问）
function askApproval(pending) {
  // 兼容：新后端给 batch 列表；老后端只给单条
  const items = (pending.batch && pending.batch.length)
    ? pending.batch
    : [{
        tool_call_id: pending.tool_call_id,
        name: pending.name,
        args: pending.args,
        title: pending.title || ("执行操作：" + pending.name),
        detail: pending.detail || "",
      }];

  const el = document.createElement("div");
  el.className = "approval";

  const multi = items.length > 1;
  const head = multi
    ? `⚠️ 超能小助想执行 ${items.length} 个操作，需要你确认`
    : `⚠️ 超能小助想执行一个操作，需要你确认`;

  const rows = items.map((it) => `
    <label class="approval-item">
      <input type="checkbox" class="approval-check" data-id="${escapeHtml(it.tool_call_id)}" checked />
      <span class="approval-item-body">
        <span class="approval-item-title">${escapeHtml(it.title)}</span>
        ${it.detail ? `<span class="approval-item-detail">${escapeHtml(it.detail)}</span>` : ""}
      </span>
    </label>`).join("");

  el.innerHTML =
    `<div class="approval-head">${head}</div>
     <div class="approval-list">${rows}</div>
     <label class="approval-trust">
       <input type="checkbox" class="approval-trust-chk" />
       <span>批准后，本次对话里这类操作不用再问我（适合人不在电脑旁的批量任务）</span>
     </label>
     <div class="approval-btns">
       ${multi ? `<button class="approve-all">全部批准</button>
                  <button class="approve-selected">只批准勾选的</button>
                  <button class="approve-none">全部拒绝</button>`
               : `<button class="approve-all">批准执行</button>
                  <button class="approve-none">拒绝</button>`}
     </div>`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // 把一组操作涉及的工具类别加入「本次免问」
  function trustTheseTools(itemList) {
    const trustChk = el.querySelector(".approval-trust-chk");
    if (trustChk && trustChk.checked) {
      itemList.forEach((it) => { if (it.name) sessionAllowedTools.add(it.name); });
    }
  }

  function finish(decisionMap, label) {
    el.querySelector(".approval-btns").innerHTML =
      `<span class="approved">${label}</span>`;
    el.querySelectorAll(".approval-check").forEach((c) => { c.disabled = true; });
    const tc = el.querySelector(".approval-trust");
    if (tc) tc.style.display = "none";
    runChatLoop(decisionMap);
  }

  // 全部批准
  el.querySelector(".approve-all").addEventListener("click", () => {
    trustTheseTools(items);
    const m = {};
    items.forEach((it) => { m[it.tool_call_id] = true; });
    finish(m, multi ? "已全部批准 ✓" : "已批准 ✓");
  });

  // 全部拒绝
  el.querySelector(".approve-none").addEventListener("click", () => {
    const m = {};
    items.forEach((it) => { m[it.tool_call_id] = false; });
    finish(m, multi ? "已全部拒绝 ✕" : "已拒绝 ✕");
  });

  // 只批准勾选的（仅多条时有这个按钮）
  const selBtn = el.querySelector(".approve-selected");
  if (selBtn) {
    selBtn.addEventListener("click", () => {
      const approvedItems = items.filter((it) => {
        const c = el.querySelector(`.approval-check[data-id="${CSS.escape(it.tool_call_id)}"]`);
        return c && c.checked;
      });
      trustTheseTools(approvedItems);
      const m = {};
      el.querySelectorAll(".approval-check").forEach((c) => {
        m[c.dataset.id] = c.checked;
      });
      finish(m, "已按勾选执行 ✓");
    });
  }
}

sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});

// ---------- 智能模式 / 常规模式 切换 ----------
function updateRouteModeBtn() {
  const btn = document.getElementById("routeModeBtn");
  const lab = document.getElementById("routeModeLabel");
  if (!btn || !lab) return;
  lab.textContent = smartRouting ? "智能" : "常规";
  btn.classList.toggle("route-smart", smartRouting);
  btn.classList.toggle("route-normal", !smartRouting);
  btn.title = smartRouting
    ? "智能模式：按任务自动分配最合适的模型（点一下切到常规）"
    : "常规模式：只用你在右边选的模型，不自动切换（点一下切到智能）";
}
(function initRouteMode() {
  const btn = document.getElementById("routeModeBtn");
  if (!btn) return;
  updateRouteModeBtn();
  btn.addEventListener("click", () => {
    smartRouting = !smartRouting;
    try { localStorage.setItem("cx_smart_routing", smartRouting ? "1" : "0"); } catch (_) {}
    updateRouteModeBtn();
  });
})();

function autoGrow() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
}
inputEl.addEventListener("input", autoGrow);

// ---------- 多会话管理 ----------
// 每个会话：{id, title, messages:[], display:[]}
let conversations = [];
let activeConvoId = null;

function newConversation() {
  const id = "c" + Date.now();
  conversations.unshift({ id, title: "新会话", messages: [], display: [] });
  activeConvoId = id;
  messages = [];
  sessionAllowedTools = new Set();   // 新对话：清空已授权的操作类别
  messagesEl.innerHTML = "";
  renderConvoList();
}

// 找到或新建一个有固定名字的会话（情报简报/竞品监控/心跳/英语辅导各自独立）
// 切过去后把它作为当前会话，功能的输出就落在这个专属会话里。
function goToNamedConvo(title) {
  saveCurrentConversation();
  let c = conversations.find((x) => x.fixedTitle === title);
  if (!c) {
    const id = "c" + Date.now();
    c = { id, title, fixedTitle: title, messages: [], display: [], displayHtml: "" };
    conversations.unshift(c);
  }
  activeConvoId = c.id;
  messages = c.messages || [];
  messagesEl.innerHTML = c.displayHtml || "";
  renderConvoList();
  // 切到对话视图
  document.querySelector('.nav-item[data-view="chat"]').click();
  return c;
}

function saveCurrentConversation() {
  const c = conversations.find((x) => x.id === activeConvoId);
  if (!c) return;
  c.messages = messages;
  c.allowedTools = Array.from(sessionAllowedTools);   // 记住本对话已授权的操作类别
  // 固定名字的功能会话（情报简报等）保留原名；用户手动改过名的也不动
  if (!c.fixedTitle && !c.userRenamed) {
    // 先给一个干净的兜底标题（不再是生硬截前20字、避免乱码）
    if (!c.title || c.title === "新会话" || c.autoTitle) {
      c.title = fallbackTitle(messages) || "新会话";
      c.autoTitle = true;
    }
    // 有了至少一轮问答后，异步让模型起一个更贴切的标题
    maybeAutoTitle(c);
  }
  // 存一份展示用的 HTML 快照
  c.displayHtml = messagesEl.innerHTML;
  renderConvoList();
  // 🌌 让「聊过的」进知识云图：静默落盘到后端存档（失败不打扰）
  if (typeof window.persistSessionToArchive === "function") {
    window.persistSessionToArchive(c);
  }
}

// 从首条用户消息提取一个干净的兜底标题：去掉 markdown 记号 / 链接 / 多余空白
function fallbackTitle(msgs) {
  const firstUser = (msgs || []).find((m) => m.role === "user");
  if (!firstUser) return "";
  let t = (firstUser.content || "");
  // 取第一行非空内容
  const line = t.split("\n").map((s) => s.trim()).find((s) => s) || "";
  t = line
    .replace(/https?:\/\/\S+/g, "")          // 去链接
    .replace(/[#*>`_~|]/g, "")                // 去 markdown 记号
    .replace(/^[-\d.\s、．]+/, "")            // 去开头的序号/符号
    .replace(/\s+/g, " ")
    .trim();
  return t.slice(0, 18);
}

// 异步：让后端模型根据会话内容总结一个标题，回填到侧边栏
async function maybeAutoTitle(c) {
  if (!c || c.fixedTitle || c.userRenamed) return;
  if (c._titling) return;                              // 防重复
  const hasAssistant = (c.messages || []).some((m) => m.role === "assistant");
  if (!hasAssistant) return;                           // 至少有一轮回复才起名
  // 已经有过一次 AI 标题就不反复刷（除非内容明显变长，这里保持简单：只做一次）
  if (c.aiTitled) return;
  c._titling = true;
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/summarize_title", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: c.messages, ...s }),
    });
    const data = await resp.json();
    if (data && data.ok && data.title && !c.userRenamed) {
      c.title = data.title;
      c.autoTitle = false;
      c.aiTitled = true;
      renderConvoList();
    }
  } catch (_) {
    // 起名失败就保持兜底标题，不打扰用户
  } finally {
    c._titling = false;
  }
}

function switchConversation(id) {
  saveCurrentConversation();
  const c = conversations.find((x) => x.id === id);
  if (!c) return;
  activeConvoId = id;
  messages = c.messages || [];
  sessionAllowedTools = new Set(c.allowedTools || []);   // 恢复该对话已授权的操作类别
  messagesEl.innerHTML = c.displayHtml || "";
  renderConvoList();
  document.querySelector('.nav-item[data-view="chat"]')?.click();
}

function renderConvoList() {
  const list = document.getElementById("convoList");
  list.innerHTML = "";
  conversations.forEach((c) => {
    // 跳过「还没说过话的空白新会话」——上方已有 ＋ 号，不必再占一行。
    // 一旦它有了消息（或被自动命名/手动改名），就正常显示。
    const isEmptyPlaceholder = (!c.messages || c.messages.length === 0)
      && (!c.title || c.title === "新会话");
    if (isEmptyPlaceholder) return;
    // 跳过功能任务产生的固定会话（心跳/竞品监控/情报简报等）——它们是任务输出，
    // 不是真正的聊天，列在「会话」里反而让人困惑。点对应按钮时仍会显示其内容。
    if (c.fixedTitle) return;

    const item = document.createElement("div");
    item.className = "convo-item" + (c.id === activeConvoId ? " active" : "");

    const name = document.createElement("span");
    name.className = "convo-name";
    name.textContent = c.title || "新会话";
    name.addEventListener("click", () => switchConversation(c.id));
    item.appendChild(name);

    const actions = document.createElement("span");
    actions.className = "convo-actions";
    // 重命名
    const ren = document.createElement("button");
    ren.className = "convo-act"; ren.title = "重命名"; ren.textContent = "✎";
    ren.addEventListener("click", (e) => { e.stopPropagation(); renameConversation(c.id); });
    // 删除
    const del = document.createElement("button");
    del.className = "convo-act"; del.title = "删除"; del.textContent = "🗑";
    del.addEventListener("click", (e) => { e.stopPropagation(); deleteConversation(c.id); });
    actions.appendChild(ren);
    actions.appendChild(del);
    item.appendChild(actions);

    list.appendChild(item);
  });
  const sec = list.closest(".convo-section");
  if (sec) sec.hidden = !list.children.length;   // v113：没有聊过的对话就整块不显示
}

function renameConversation(id) {
  const c = conversations.find((x) => x.id === id);
  if (!c) return;
  // Electron 不支持 window.prompt，所以用内联输入框来改名
  const list = document.getElementById("convoList");
  const items = Array.from(list.children);
  const idx = conversations.indexOf(c);
  const item = items[idx];
  if (!item) return;
  const nameEl = item.querySelector(".convo-name");
  const input = document.createElement("input");
  input.className = "convo-rename-input";
  input.value = c.title || "";
  item.insertBefore(input, nameEl);
  nameEl.style.display = "none";
  input.focus();
  input.select();
  const commit = (save) => {
    if (save && input.value.trim()) {
      c.title = input.value.trim().slice(0, 30);
      c.userRenamed = true;   // 用户手动改名后，不再被自动起名覆盖
      c.autoTitle = false;
    }
    renderConvoList();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); commit(true); }
    if (e.key === "Escape") { commit(false); }
  });
  input.addEventListener("blur", () => commit(true));
  input.addEventListener("click", (e) => e.stopPropagation());
}

function deleteConversation(id) {
  const c = conversations.find((x) => x.id === id);
  if (!c) return;
  if (!confirm(`删除会话「${c.title || "新会话"}」？此操作不可恢复。`)) return;
  const wasActive = id === activeConvoId;
  conversations = conversations.filter((x) => x.id !== id);
  if (conversations.length === 0) {
    newConversation();  // 删光了就开一个新的
    return;
  }
  if (wasActive) {
    // 切到列表里第一个
    const first = conversations[0];
    activeConvoId = first.id;
    messages = first.messages || [];
    messagesEl.innerHTML = first.displayHtml || "";
  }
  renderConvoList();
}

// v111：左栏不再有单独的「对话」入口（和「新对话」重复，仿 Claude 的侧栏）：
// 点「新对话」= 开一个新对话并进对话页；当前已经是空白对话就直接用它。
function startNewChat() {
  const cur = conversations.find((x) => x.id === activeConvoId);
  const curEmpty = cur && !cur.fixedTitle && (!messages || messages.length === 0);
  if (!curEmpty) {
    saveCurrentConversation();
    newConversation();
  }
  document.querySelector('.nav-item[data-view="chat"]')?.click();
  try { inputEl.focus(); } catch (e) {}
}
document.getElementById("newConvoBtn").addEventListener("click", startNewChat);

// ---------- 结束对话（弹框：清空并保存 / 结束并记住 / 取消）----------
function openEndDialog() {
  const dlg = document.getElementById("endDialog");
  const st = document.getElementById("endDialogStatus");
  if (st) st.textContent = "";
  if (messages.length === 0) {
    // 没内容时也允许，但提示一下
    if (st) st.textContent = "当前对话还是空的，没什么要保存或记住的。";
  }
  if (dlg) dlg.hidden = false;
}
function closeEndDialog() {
  const dlg = document.getElementById("endDialog");
  if (dlg) dlg.hidden = true;
}
document.getElementById("endConvoBtn")?.addEventListener("click", openEndDialog);
document.getElementById("endOptCancel")?.addEventListener("click", closeEndDialog);
document.getElementById("endDialog")?.addEventListener("click", (e) => {
  if (e.target.id === "endDialog") closeEndDialog();
});

// 清空并保存：把当前对话存进侧边栏历史，然后开新对话（不提炼长期记忆）
document.getElementById("endOptSave")?.addEventListener("click", () => {
  saveCurrentConversation();   // 落进历史会话
  newConversation();           // 开一个干净的新会话
  closeEndDialog();
});

// 结束并记住：先存历史，再提炼要点进长期记忆，然后开新对话
document.getElementById("endOptRemember")?.addEventListener("click", async () => {
  const st = document.getElementById("endDialogStatus");
  if (messages.length === 0) {
    if (st) st.textContent = "当前对话是空的，先聊几句再记住吧。";
    return;
  }
  const btn = document.getElementById("endOptRemember");
  btn.disabled = true;
  if (st) st.textContent = "正在提炼这段对话的要点…（可能要十几秒）";
  try {
    saveCurrentConversation();   // 先存历史
    const s = settings();
    const resp = await fetch(BACKEND + "/remember", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    if (data.ok) {
      newConversation();
      addSystemNote(
        "🧠 已把上一段对话的要点存入长期记忆，并保留为历史会话。提炼出的要点：\n"
        + (data.summary || "（这段没什么特别要记的）"));
      closeEndDialog();
    } else {
      if (st) st.textContent = "记忆失败：" + (data.error || "未知");
    }
  } catch (e) {
    if (st) st.textContent = "记忆出错：" + e.message;
  } finally {
    btn.disabled = false;
  }
});

// 提炼成技能：把这段对话解析成一个可复用技能，打开编辑器让用户确认后保存
document.getElementById("endOptSkill")?.addEventListener("click", async () => {
  const st = document.getElementById("endDialogStatus");
  if (messages.length === 0) {
    if (st) st.textContent = "当前对话是空的，先做点事再提炼技能吧。";
    return;
  }
  const btn = document.getElementById("endOptSkill");
  btn.disabled = true;
  if (st) st.textContent = "正在解析这段对话、提炼技能…（可能要十几秒）";
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/skills/from_conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    if (!data.ok) { if (st) st.textContent = "提炼失败：" + (data.message || "未知"); return; }
    if (!data.skill) {
      if (st) st.textContent = data.message || "这段对话没提炼出可复用的技能。";
      return;
    }
    // 跳到技能页，打开编辑器（预填草稿），让用户确认/修改后保存
    closeEndDialog();
    document.querySelector('.nav-item[data-view="skills"]')?.click();
    setTimeout(() => fillSkillEditor(data.skill, { draft: true }), 60);
  } catch (e) {
    if (st) st.textContent = "提炼出错：" + e.message;
  } finally {
    btn.disabled = false;
  }
});

// ---------- 竞品监控 ----------
document.getElementById("watchBtn").addEventListener("click", async () => {
  goToNamedConvo("🔍 竞品监控");
  const btn = document.getElementById("watchBtn");
  btn.textContent = "抓取对比中…";
  btn.disabled = true;
  const prog = addProgress([
    "🔍 正在逐个抓取竞品页面…",
    "📄 正在对比和上次的快照…",
    "🧠 正在判断有没有值得提醒的变化…",
  ]);
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/competitors", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    prog.done();
    if (data.alerts && data.alerts.length) {
      addBubble("assistant", "🔔 竞品有动静：\n\n" + data.alerts.join("\n\n"));
    } else {
      addBubble("assistant", "检查完成，没有值得提醒的变化。\n\n详细日志：\n" +
        (data.logs || ""));
    }
    saveCurrentConversation();
  } catch (e) {
    prog.done();
    addSystemNote("竞品检查出错：" + e.message);
  } finally {
    btn.textContent = "立即检查";
    btn.disabled = false;
  }
});

// ---------- 情报简报 ----------
document.getElementById("briefingBtn").addEventListener("click", async () => {
  // 先别急着跑——先告诉用户这要干什么、用哪些关键词，让他确认或去调整
  let keywords = [];
  try {
    const r = await fetch(BACKEND + "/memory?name=watchlist.md");
    const d = await r.json();
    keywords = (d.content || "")
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && !l.startsWith(">"));
  } catch (_) {}

  showBriefingConfirm(keywords);
});

// 情报简报的"开始前确认"框：说明它要做什么、用哪些关键词，可确认/调整/取消
function showBriefingConfirm(keywords) {
  document.querySelector('.nav-item[data-view="chat"]').click();
  const box = document.createElement("div");
  box.className = "task-confirm";
  const kw = keywords.length
    ? keywords.map((k) => `<span class="task-kw">${escapeHtml(k)}</span>`).join("")
    : '<span class="task-empty">（还没设关键词，点下面「去调整关键词」加，一行一个）</span>';
  box.innerHTML = `
    <div class="task-head">📊 生成情报简报 · 开始前确认</div>
    <div class="task-body">
      它会做这几步：<b>① 按下面的关键词联网搜索 → ② 打开搜到的网页读正文 →
      ③ 让模型提炼成一份简报 → ④ 显示出来（配了 Server酱会推到你微信）</b>。
      默认用<b>网页模型</b>来搜和总结（效果更好、自带最新来源）；
      若网页模型不可用会自动回退到你当前所选的模型。大概要一两分钟。
      <div class="task-kw-wrap">关注关键词：${kw}</div>
    </div>
    <div class="task-btns">
      <button class="approve-yes" id="briefGo">开始</button>
      <button class="approve-no" id="briefEdit">去调整关键词</button>
      <button class="approve-no" id="briefCancel">取消</button>
    </div>`;
  messagesEl.appendChild(box);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  box.querySelector("#briefCancel").onclick = () => box.remove();
  box.querySelector("#briefEdit").onclick = () => {
    box.remove();
    openConfigFile("watchlist.md");
  };
  box.querySelector("#briefGo").onclick = () => {
    box.remove();
    runBriefing();
  };
}

async function runBriefing() {
  goToNamedConvo("📊 情报简报");
  const btn = document.getElementById("briefingBtn");
  btn.textContent = "搜集+提炼中…";
  btn.disabled = true;
  // 真实进度：给这次简报一个 id，后端逐步播报"调研第 i 个关键词 + 网页模型实时活动"，
  // 前端用可展开的进度框显示（点"详情"看每一步）。
  const chatId = "brief-" + Date.now();
  const prog = addLiveProgress(chatId);
  // 记下用户原来选的模型，作为 web 不可用时的兜底
  const s = settings();
  // 情报简报默认用「网页模型」：先把聊天框 + 右上角同步成网页模型，避免显示不一致
  syncComposerModel(false, "web");
  try {
    const resp = await fetch(BACKEND + "/briefing", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        use_local: false, model: "web",
        fallback_use_local: s.use_local, fallback_model: s.model,
        chat_id: chatId }),
    });
    const data = await resp.json();
    prog.done();
    // 后端会回报「实际用的模型」（web 不可用时会回退）。按实际用的同步 UI，保证不误导。
    if (data && data.used_model) {
      syncComposerModel(!!data.used_use_local, data.used_model);
    }
    addBubble("assistant", data.brief || "（没有内容）");
    saveCurrentConversation();
  } catch (e) {
    prog.done();
    addSystemNote("情报简报出错：" + e.message);
  } finally {
    btn.textContent = "生成一份简报";
    btn.disabled = false;
  }
}

// ---------- 心跳 ----------
document.getElementById("heartbeatBtn").addEventListener("click", async () => {
  goToNamedConvo("💓 心跳");
  const btn = document.getElementById("heartbeatBtn");
  btn.textContent = "心跳醒来中…";
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    const reply = (data.reply || "").trim();
    if (reply.toUpperCase().startsWith("SLEEP")) {
      addSystemNote("💓 心跳：看了一眼，没事，继续休眠。");
    } else {
      addSystemNote("💓 心跳干活了：" + reply);
    }
    saveCurrentConversation();
  } catch (e) {
    addSystemNote("💓 心跳出错：" + e.message);
  } finally {
    btn.textContent = "现在触发一次";
  }
});

// ---------- 自动心跳开关（软件内，跟着软件活）----------
async function refreshHeartbeatStatus() {
  try {
    const r = await fetch(BACKEND + "/heartbeat/status");
    const d = await r.json();
    const tog = document.getElementById("heartbeatToggle");
    const sel = document.getElementById("hbInterval");
    const hint = document.getElementById("hbHint");
    if (tog) tog.checked = !!d.running;
    if (sel && d.interval) sel.value = String(d.interval);
    if (hint) {
      hint.textContent = d.running
        ? ("自动心跳运行中。" + (d.last ? "最近：" + d.last : ""))
        : "自动心跳已关闭。";
    }
  } catch (_) {}
}

document.getElementById("heartbeatToggle")?.addEventListener("change", async (e) => {
  const on = e.target.checked;
  const hint = document.getElementById("hbHint");
  const interval = parseInt(document.getElementById("hbInterval").value, 10) || 300;
  const s = settings();
  try {
    if (on) {
      const r = await fetch(BACKEND + "/heartbeat/start", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interval, use_local: s.use_local, model: s.model }),
      });
      const d = await r.json();
      if (hint) hint.textContent = d.message || "已开启";
    } else {
      const r = await fetch(BACKEND + "/heartbeat/stop", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const d = await r.json();
      if (hint) hint.textContent = d.message || "已关闭";
    }
  } catch (err) {
    if (hint) hint.textContent = "出错：" + err.message;
    e.target.checked = !on;  // 失败时还原开关
  }
});

// 改间隔时，如果正在运行，重启一下让新间隔生效
document.getElementById("hbInterval")?.addEventListener("change", async () => {
  const tog = document.getElementById("heartbeatToggle");
  if (tog && tog.checked) {
    await fetch(BACKEND + "/heartbeat/stop", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    tog.checked = false;
    tog.dispatchEvent(new Event("change"));
    tog.checked = true;
    tog.dispatchEvent(new Event("change"));
  }
});

function addSystemNote(text) {
  // 切到对话视图并显示一条提示
  document.querySelector('.nav-item[data-view="chat"]').click();
  const el = document.createElement("div");
  el.className = "tool-call tc-note";
  el.style.alignSelf = "center";
  el.style.maxWidth = "90%";
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 动态进度提示：显示一个会动的小框，循环播放几条阶段文字。
// 返回 { update(text), done() }，done 会移除它。
function addProgress(stages, stepMs) {
  document.querySelector('.nav-item[data-view="chat"]').click();
  const el = document.createElement("div");
  el.className = "progress-box";
  const dot = document.createElement("span");
  dot.className = "progress-dot";
  const txt = document.createElement("span");
  txt.className = "progress-text";
  el.appendChild(dot);
  el.appendChild(txt);
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  let i = 0;
  const list = Array.isArray(stages) ? stages : [stages];
  txt.textContent = list[0];
  const interval = stepMs || 2500;
  const timer = setInterval(() => {
    if (i < list.length - 1) {
      i++;
      txt.textContent = list[i];
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }, interval);

  return {
    update(t) { txt.textContent = t; },
    done() { clearInterval(timer); el.remove(); },
  };
}

// 实时进度：轮询后端 /chat_progress?id=xxx，把"每一步在干什么 + 进度条"显示出来。
// 像样地一步步亮出来，而不是一个固定的"正在整理回复…"。
function addLiveProgress(chatId) {
  document.querySelector('.nav-item[data-view="chat"]').click();

  const el = document.createElement("div");
  el.className = "progress-box live";
  el.innerHTML =
    `<div class="lp-current">
       <span class="progress-dot"></span>
       <span class="lp-current-text">正在思考…</span>
       <button class="lp-toggle" hidden>详情 ⌄</button>
     </div>
     <div class="lp-steps" hidden></div>
     <div class="lp-bar" style="display:none"><div class="lp-bar-fill"></div></div>
     <div class="lp-detail"></div>`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  const stepsEl   = el.querySelector(".lp-steps");
  const curText   = el.querySelector(".lp-current-text");
  const toggleBtn = el.querySelector(".lp-toggle");
  const barWrap   = el.querySelector(".lp-bar");
  const barFill   = el.querySelector(".lp-bar-fill");
  const detailEl  = el.querySelector(".lp-detail");

  // 点"详情 ⌄"展开/收起详细步骤（像 Claude 那样）
  let expanded = false;
  toggleBtn.addEventListener("click", () => {
    expanded = !expanded;
    stepsEl.hidden = !expanded;
    toggleBtn.textContent = expanded ? "收起 ⌃" : "详情 ⌄";
    if (expanded) messagesEl.scrollTop = messagesEl.scrollHeight;
  });

  let stopped = false;
  let lastStepCount = -1;

  function render(snap) {
    const steps = snap.steps || [];
    // 已完成的步骤：每条带一个 ✓（折叠在"详情"里）
    if (steps.length !== lastStepCount) {
      lastStepCount = steps.length;
      stepsEl.innerHTML = steps
        .map((s) => `<div class="lp-step">✓ ${escapeHtml(s)}</div>`)
        .join("");
      toggleBtn.hidden = steps.length === 0;   // 有步骤才显示"详情"按钮
    }
    // 当前正在做的这步（始终作为标题行显示）
    if (snap.current) curText.textContent = snap.current;
    // 进度条（有百分比才显示）
    if (snap.pct !== null && snap.pct !== undefined) {
      barWrap.style.display = "block";
      barFill.style.width = snap.pct + "%";
    } else {
      barWrap.style.display = "none";
    }
    // 当前步骤的实时明细（如网页模型"接收回复中…（N字）"）
    detailEl.textContent = snap.detail || "";
    if (expanded) messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function poll() {
    while (!stopped) {
      try {
        const r = await fetch(BACKEND + "/chat_progress?id=" +
                              encodeURIComponent(chatId));
        const snap = await r.json();
        if (!stopped) render(snap);
        if (snap.done) break;
      } catch (e) { /* 网络抖动忽略，继续轮询 */ }
      await new Promise((res) => setTimeout(res, 600));
    }
  }
  poll();

  return {
    done() { stopped = true; el.remove(); },
  };
}


// ---------- 记忆编辑 ----------
// 每个记忆/配置文件：友好中文名 + 编辑方式（list 列表 / config 表单 / text 自由文本）
const MEMORY_META = {
  "SOUL.md":      { label: "🦞 性格设定", type: "text", group: "memory",
                    desc: "改这里能改变超能小助的说话风格和性格。" },
  "AGENTS.md":    { label: "📋 行为准则", type: "text", group: "memory",
                    desc: "它做事的规则。一般不用动，进阶用户可微调。" },
  "USER.md":      { label: "👤 关于你", type: "text", group: "memory",
                    desc: "记录你的情况和偏好，它会参考这些来更懂你。" },
  "MEMORY.md":    { label: "🧠 长期记忆", type: "text", group: "memory",
                    desc: "它从历次对话里提炼的要点，跨对话还记得你。" },
  "heartbeat.md": { label: "💓 心跳待办", type: "text", group: "config",
                    desc: "心跳醒来时会看这里有没有要做的事。" },
  "watchlist.md": { label: "📊 情报关键词", type: "list", group: "config",
                    itemLabel: "关键词", placeholder: "如：预制菜 行业趋势",
                    desc: "情报简报会按这些关键词联网搜集、提炼。一行一个。" },
  "competitors.md": { label: "🔍 竞品网址", type: "list", hasNote: true, group: "config",
                    itemLabel: "网址", placeholder: "https://竞品官网/products",
                    notePlaceholder: "备注（如：竞品A 产品页）",
                    desc: "竞品监控会定时抓这些公开页面，有变化就提醒。" },
  "reminders.md": { label: "⏰ 定时提醒", type: "list", hasNote: true, group: "config",
                    itemLabel: "时间", placeholder: "如：每天 09:00",
                    notePlaceholder: "提醒内容（如：交日报）",
                    sep: "|", bullet: "- [ ] ",
                    desc: "心跳到点会提醒你。时间写「每天 09:00」或「2026-06-20 14:00」。" },
  "push.md":      { label: "📱 Server酱推送", type: "config", group: "config",
                    desc: "配好后，心跳干完活能把消息推到你的微信（单向）。",
                    fields: [
                      { key: "serverchan_key", label: "SendKey",
                        help: "去 sct.ftqq.com 微信扫码登录，复制 SendKey（形如 SCTxxxx）" },
                    ] },
  "wecom.md":     { label: "💬 企业微信", type: "config", group: "config",
                    desc: "在企业微信 App 里和它双向聊天（合规免费，需公网回调）。",
                    fields: [
                      { key: "corp_id", label: "企业 CorpID", help: "「我的企业」里能看到" },
                      { key: "agent_id", label: "应用 AgentId", help: "自建应用页面" },
                      { key: "secret", label: "应用 Secret", help: "自建应用页面" },
                      { key: "token", label: "Token", help: "接收消息设置里，点随机生成" },
                      { key: "aes_key", label: "EncodingAESKey", help: "接收消息设置里，点随机生成" },
                    ] },
  "feishu.md":    { label: "🐦 飞书", type: "config", group: "config",
                    desc: "在飞书里和它双向聊天（体验顺，需公网回调）。",
                    fields: [
                      { key: "app_id", label: "App ID", help: "企业自建应用页面" },
                      { key: "app_secret", label: "App Secret", help: "企业自建应用页面" },
                      { key: "verification_token", label: "Verification Token",
                        help: "事件订阅页面" },
                    ] },
  "telegram.md":  { label: "✈️ Telegram", type: "config", group: "form",   // 在「设置 → 通知」里填
                    desc: "海外可用。找 @BotFather 拿 token，@userinfobot 拿你的 chat id。",
                    fields: [
                      { key: "token", label: "Bot Token", help: "找 @BotFather 用 /newbot 获取" },
                      { key: "allowed_chat_id", label: "你的 Chat ID",
                        help: "找 @userinfobot 获取，只服务你一人" },
                    ] },
  "proxy.md":     { label: "🌐 联网与代理", type: "config", group: "form",   // 在「设置 → 联网与代理」里填
                    desc: "国内直接搜 Bing；要搜国外源（DuckDuckGo/Google）需填代理。不填只搜国内。",
                    fields: [
                      { key: "proxy", label: "代理地址",
                        help: "如 http://127.0.0.1:7890（Clash默认7890）。不用代理就留空" },
                    ] },
};
const MEMORY_FILES = Object.keys(MEMORY_META);
// 记忆文件页只显示「AI对你的记忆/性格」这一类；配置类挪到设置里
const MEMORY_FILES_MEM = MEMORY_FILES.filter((f) => MEMORY_META[f].group === "memory");
const MEMORY_FILES_CFG = MEMORY_FILES.filter((f) => MEMORY_META[f].group === "config");
let currentMemoryFile = "SOUL.md";
let _rawHeader = "";   // 保存文件顶部的说明行（# 和 > 开头），保存时原样写回

// ---------- 英语学习 ----------
function getStudent() {
  return (document.getElementById("studentName").value || "default").trim();
}

document.getElementById("dailyTaskBtn").addEventListener("click", async () => {
  const btn = document.getElementById("dailyTaskBtn");
  const out = document.getElementById("studyOutput");
  btn.textContent = "出题中…";
  btn.disabled = true;
  out.innerHTML = '<div class="study-hint">正在根据教材生成今日任务…</div>';
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/daily_task", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student: getStudent(),
                             use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    out.innerHTML = '<div class="study-task">' +
      renderMarkdown(data.task || "（没有内容）") + "</div>";
  } catch (e) {
    out.innerHTML = '<div class="study-hint">出错：' + escapeHtml(e.message) + "</div>";
  } finally {
    btn.textContent = "📋 生成今日任务";
    btn.disabled = false;
  }
});

document.getElementById("startTutorBtn").addEventListener("click", () => {
  const student = getStudent();
  // 进入英语辅导专属会话，注入学习模式开场
  goToNamedConvo("📚 英语辅导");
  inputEl.value = `我是学生${student !== "default" ? "「" + student + "」" : ""}，` +
    "现在开始英语学习。请你当我的英语老师助教，基于老师的教材辅导我。" +
    "先看看有哪些教材，然后问我今天想练什么（背单词/做题/学语法）。";
  send();
});

document.getElementById("viewStudentBtn").addEventListener("click", async () => {
  const out = document.getElementById("studyOutput");
  out.innerHTML = '<div class="study-hint">读取档案中…</div>';
  try {
    const resp = await fetch(BACKEND + "/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user",
          content: `用 get_student 查学生「${getStudent()}」的档案，` +
                   "用中文友好地总结他的学习进度、薄弱点、错题情况。" }],
        ...settings(),
      }),
    });
    const data = await resp.json();
    out.innerHTML = '<div class="study-task">' +
      renderMarkdown(data.reply || "（没有档案）") + "</div>";
  } catch (e) {
    out.innerHTML = '<div class="study-hint">出错：' + escapeHtml(e.message) + "</div>";
  }
});

// ---------- 情报看板 ----------
// ---------- 视频内容提取 ----------
document.getElementById("videoInfoBtn")?.addEventListener("click", () => {
  const intro = document.getElementById("videoIntro");
  if (intro) intro.style.display = intro.style.display === "none" ? "" : "none";
});

// 设置页：显示模型下载位置 + 已下载清单
async function loadModelsInfo() {
  try {
    const r = await fetch(BACKEND + "/models_info");
    const d = await r.json();
    const dirEl = document.getElementById("modelsDirText");
    const listEl = document.getElementById("modelsListText");
    if (dirEl) dirEl.textContent = d.dir || "（未知）";
    if (listEl) listEl.textContent = (d.models && d.models.length)
      ? d.models.join("、") : "暂无（用一次视频提取会自动下载）";
    const gpuEl = document.getElementById("gpuStatusText");
    if (gpuEl) {
      const g = d.gpu || {};
      gpuEl.textContent = g.summary || "（未知）";
      gpuEl.style.color = g.device === "cuda" ? "#5fa463" : "";
      // 还在检测 / 下载运行库时，过几秒再刷新一次
      if (g.installing || g.checked === false) setTimeout(loadModelsInfo, 5000);
    }
  } catch (_) {}
}

document.getElementById("moveModelsBtn")?.addEventListener("click", async () => {
  const btn = document.getElementById("moveModelsBtn");
  const msg = document.getElementById("moveModelsMsg");
  const go = confirm(
    "这会把 C 盘已下载的模型（语音模型 + Ollama 大模型）安全搬到 D 盘。\n\n"
    + "做法是「先复制到 D 盘 → 校验无误 → 再删 C 盘」，过程中不会弄坏原文件。\n\n"
    + "👉 建议先退出 Ollama（屏幕右下角托盘图标 → Quit）再搬，避免文件被占用。\n"
    + "模型较大时可能要几分钟。确定现在搬吗？");
  if (!go) return;
  btn.disabled = true; btn.textContent = "搬运中…（请耐心等）";
  if (msg) { msg.style.whiteSpace = "pre-line"; msg.textContent = "正在复制并搬运，请勿关闭软件…"; }
  try {
    const r = await fetch(BACKEND + "/video_move_models", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const d = await r.json();
    if (msg) msg.textContent = d.message || (d.ok ? "搬好了" : "没搬到");
    loadModelsInfo();
  } catch (e) {
    if (msg) msg.textContent = "出错：" + e.message;
  } finally {
    btn.disabled = false; btn.textContent = "把 C 盘已下载模型搬到 D 盘";
  }
});
document.getElementById("videoGoBtn")?.addEventListener("click", runVideoExtract);
document.getElementById("videoUrl")?.addEventListener("keydown", (e) => {
  // v112：输入框能放多行文字了：Enter 开始提取，Shift+Enter 换行（输入法选字时的回车不算）
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); runVideoExtract(); }
});

// ── v112：加工——认出放进来的是什么（输入框下面那行），只有视频才显示「博主主页」──
let _viKindTimer = null, _viKindSeq = 0;
function viAutoGrow() {
  const el = document.getElementById("videoUrl");
  if (!el || el.tagName !== "TEXTAREA") return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight + 2, 168) + "px";
}
async function viDetectKind() {
  const el = document.getElementById("videoUrl"), out = document.getElementById("viKind");
  if (!el || !out) return;
  const text = (el.value || "").trim();
  const creatorRow = document.querySelector("#view-video .video-creator-row");
  const seq = ++_viKindSeq;
  if (!text) { out.hidden = true; if (creatorRow) creatorRow.style.display = ""; return; }
  try {
    const r = await fetch(BACKEND + "/intake_kind", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    const d = await r.json();
    if (seq !== _viKindSeq) return;   // 又改过了，以最新的为准
    if (!d || !d.kind) { out.hidden = true; return; }
    out.innerHTML = '<span class="vi-kind-tag k-' + escapeHtml(d.kind) + '">' + escapeHtml(d.label) + "</span>" +
      '<span class="vi-kind-hint">' + escapeHtml(d.hint || "") + "</span>" +
      // 一小段文字也可能是想搜某个领域：给个改成搜索推荐的按钮
      ((d.kind === "text" && text.length <= 30 && text.indexOf("\n") < 0)
        ? '<button type="button" class="vi-kind-alt" data-vi-search="1">改成搜索推荐</button>' +
          '<button type="button" class="vi-kind-alt" data-vi-chat="1">发给小助聊</button>' : "") +
      (d.kind === "chat" ? '<button type="button" class="vi-kind-alt" data-vi-note="1">改成存为笔记</button>' : "");
    out.hidden = false;
    if (creatorRow) creatorRow.style.display = (d.kind === "video") ? "" : "none";
  } catch (e) { out.hidden = true; }
}
function viOnInputChanged() {
  viAutoGrow();
  clearTimeout(_viKindTimer);
  _viKindTimer = setTimeout(viDetectKind, 250);
}
document.getElementById("videoUrl")?.addEventListener("input", viOnInputChanged);

// ── v118：拖进来 / 粘进来的文件和文件夹：找出能提取的文件 → 导入设置 → 逐个入队 ──
async function viImportPaths(paths) {
  try {
    const r = await fetch(BACKEND + "/intake_scan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paths }) });
    const d = await r.json();
    if (!d || !d.files || !d.files.length) {
      setVideoStatus("里面没找到能提取的文件（音视频、PDF、Word、Excel、TXT…，子文件夹也找过了）。", "warn");
      return;
    }
    const o = await askImportOptions({ count: d.files.length, source: d.name || "", targetFolder: "" });
    if (!o) return;
    if (o.noteFolder) vnSetFolderOpen(o.noteFolder, true);
    for (const p of d.files) await startLocalVideoJob(p, o.author, o.noteFolder, o);
    setVideoStatus("已提交 " + d.files.length + " 个文件进队列，将逐个提取" +
      (o.noteFolder ? "，完成的会归进「" + o.noteFolder + "」" : "") + "。", "ok", { priority: true, holdMs: 6000 });
  } catch (e) {
    setVideoStatus("导入出错：" + (e && e.message ? e.message : e), "warn");
  }
}
// ── v120：加工页的处理进度 ──
const VI_AN_IDLE = "现在没有在分析的内容。点下面「批量 AI 分析」，或者单条的「AI 分析」开始。";
let _viAnIdleTimer = null;
function setAnStatus(msg, kind, holdMs) {
  const el = document.getElementById("viAnStatus");
  if (!el) return;
  el.textContent = msg;
  el.className = "vi-an-status" + (kind ? " " + kind : " busy");
  clearTimeout(_viAnIdleTimer);
  if (holdMs) _viAnIdleTimer = setTimeout(() => {
    if (!_noteAnRunning) { el.textContent = VI_AN_IDLE; el.className = "vi-an-status"; }
  }, holdMs);
}
function viNoteTitle(name) {
  const n = String(name || "");
  const row = n && Array.from(document.querySelectorAll(".video-note-item")).find((x) => x.dataset.name === n);
  const t = row && row.querySelector(".vn-name");
  return (t && t.textContent.trim()) || n.replace(/\.md$/, "").replace(/^\d{8}-\d{6}-/, "");
}
// ── v120：一个框里打的是聊天 → 发到对话里（不存笔记）──
let _viForceNote = false;
function viSendToChat(text) {
  if (typeof startNewChat === "function") startNewChat();
  else document.querySelector('.nav-item[data-view="chat"]')?.click();
  const box = document.getElementById("input");
  if (!box) return;
  box.value = text;
  try { autoGrow(); } catch (e) {}
  setTimeout(() => document.getElementById("sendBtn")?.click(), 60);
}
document.addEventListener("click", (e) => {
  const t = e.target.closest && e.target.closest("[data-vi-chat], [data-vi-note]");
  if (!t) return;
  const box = document.getElementById("videoUrl");
  const q = (box && box.value || "").trim();
  if (!q) return;
  if (t.dataset.viChat) { box.value = ""; viOnInputChanged(); viSendToChat(q); return; }
  _viForceNote = true;   // 存成笔记：跳过「认出是聊天」那一步
  runVideoExtract();
});

// 搜索推荐：用工具卡片里原来的那套搜索（结果显示在输入框下面）
function viRunSearch(q) {
  const vf = document.getElementById("vFind");
  if (!vf || !q) { setVideoStatus("搜索推荐还没准备好，过几秒再试。", "warn"); return; }
  const body = vf.querySelector(".vfind-body"), kw = vf.querySelector(".cwf-kw");
  if (body && body.hidden) vf.querySelector(".vfind-head")?.click();
  if (kw) kw.value = q;
  vf.querySelector(".cwf-btn")?.click();
  try { vf.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (e) {}
}
document.addEventListener("click", (e) => {
  const t = e.target;
  if (t.closest && t.closest("[data-vi-search]")) {
    const box = document.getElementById("videoUrl");
    const q = (box && box.value || "").trim();
    if (box) { box.value = ""; viOnInputChanged(); }
    viRunSearch(q);
    return;
  }
  const menu = document.getElementById("viAttachMenu");
  if (!menu) return;
  if (t.closest && t.closest("#viAttachBtn")) { menu.hidden = !menu.hidden; return; }
  if (t.closest && t.closest(".vi-attach-item")) { menu.hidden = true; return; }   // 选文件 / 选文件夹：按钮自己的处理照常跑
  if (!menu.hidden && !(t.closest && t.closest("#viAttachMenu"))) menu.hidden = true;
});
// 拖进来：文件、文件夹（Electron 里能拿到完整路径）、链接或文字都行
(function () {
  const card = document.querySelector("#view-video .v-card-extract");
  if (!card) return;
  const on = (v) => card.classList.toggle("vi-drag", v);
  card.addEventListener("dragover", (e) => { e.preventDefault(); on(true); });
  card.addEventListener("dragleave", (e) => { if (!card.contains(e.relatedTarget)) on(false); });
  card.addEventListener("drop", (e) => {
    e.preventDefault(); on(false);
    const dt = e.dataTransfer;
    const paths = Array.from((dt && dt.files) || []).map((f) => {
      try { return (window.crayfish && window.crayfish.pathForFile && window.crayfish.pathForFile(f)) || f.path || ""; } catch (_) { return f.path || ""; }
    }).filter(Boolean);
    if (paths.length) { viImportPaths(paths); return; }
    const txt = (dt && (dt.getData("text/uri-list") || dt.getData("text/plain")) || "").trim();
    const box = document.getElementById("videoUrl");
    if (txt && box) { box.value = txt; viOnInputChanged(); box.focus(); }
  });
})();

// GitHub 项目笔记：一键让小助帮你装（去对话页，把要说的话填好，你看过再发）
function vnGhInstall(n) {
  const m = String((n && n.title) || "").match(/^([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)/);
  const repo = m ? m[1] : "";
  if (typeof startNewChat === "function") startNewChat();
  else document.querySelector('.nav-item[data-view="chat"]')?.click();
  const box = document.getElementById("input");
  if (!box) return;
  box.value = "帮我在这台电脑上装 GitHub 项目 " + (repo ? "https://github.com/" + repo : (n.title || "")) +
    "。先看它 README 里的安装说明（加工好的笔记里也摘了一份：" + (n.title || "") + "），" +
    "告诉我要装到哪、打算执行哪些命令，等我确认了再动手。";
  try { autoGrow(); box.focus(); } catch (e) {}
}
function vnGhInstallBtn(n) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "vn-gh-btn";
  b.textContent = "让小助装";
  b.title = "去对话里让小助按 README 帮你装（先告诉你要执行什么，你确认了才动手）";
  b.addEventListener("click", (e) => { e.stopPropagation(); vnGhInstall(n); });
  return b;
}
// 分析进行中又粘进/输入了新链接 → 自动弹「加入队列」（不用等用户点按钮）
document.getElementById("videoUrl")?.addEventListener("input", (e) => {
  const v = (e.target.value || "").trim();
  // 看起来像个链接，且当前正忙，且没在提交中
  if (_videoBusyNow() && !_videoSubmitting && /https?:\/\/\S+/.test(v)) {
    promptQueueNewLink(v);
  } else if (!_videoBusyNow()) {
    // 不忙了就把残留的排队提示条收掉
    const bar = document.getElementById("videoQueuePrompt");
    if (bar) bar.remove();
  }
});

// ── 「提取后自动 AI 分析」开关（高级选项）：记住上次选择 + 联动禁用「插图」──
// 取消勾选 = 只提取并保存文字稿、完全不调 AI（适合 AI 正被别的软件占用时）；
// 此时「插图」置灰（视频画面用完即删，事后补不了图），「跳转原片」不受影响。
(function initVideoAnalyzeOpt() {
  const an = document.getElementById("videoAnalyze");
  if (!an) return;
  const shot = document.getElementById("videoShot");
  try {
    const v = localStorage.getItem("videoAutoAnalyze");
    if (v !== null) an.checked = (v === "1");
  } catch (_) {}
  function sync() {
    try { localStorage.setItem("videoAutoAnalyze", an.checked ? "1" : "0"); } catch (_) {}
    if (shot) {
      if (!an.checked) {
        shot.checked = false;
        shot.disabled = true;
        if (shot.parentElement) {
          shot.parentElement.style.opacity = "0.45";
          shot.parentElement.title =
            "「仅提取文字稿」模式下插图不可用（视频画面用完即删，事后补不了图）";
        }
      } else {
        shot.disabled = false;
        if (shot.parentElement) {
          shot.parentElement.style.opacity = "";
          shot.parentElement.title = "";
        }
      }
    }
  }
  an.addEventListener("change", sync);
  sync();
})();

let _statusLockUntil = 0;   // 在此时间戳前，低优先级状态更新（如轮询）不覆盖横幅
function setVideoStatus(text, kind, opts) {
  opts = opts || {};
  const now = Date.now();
  // 高优先级提示（如"链接已填好"）会锁定横幅一段时间，期间轮询的普通状态不覆盖它
  if (opts.priority) {
    _statusLockUntil = now + (opts.holdMs || 5000);
  } else if (now < _statusLockUntil) {
    return;  // 横幅被锁定中，跳过这次低优先级更新
  }
  const el = document.getElementById("videoStatus");
  if (!el) return;
  el.textContent = text || "";
  el.className = "video-status" + (kind ? " " + kind : "");
  if (!text) {
    el.style.cssText = "";
    return;
  }
  let bg = "rgba(120,120,130,.12)", fg = "var(--text,#333)";
  if (kind === "ok") { bg = "rgba(46,160,90,.14)"; fg = "#2ea05a"; }
  else if (kind === "warn") { bg = "rgba(210,120,30,.14)"; fg = "#c8781e"; }
  el.style.cssText =
    "display:block;margin:0 0 12px;padding:9px 13px;border-radius:9px;" +
    "font-size:13px;font-weight:500;line-height:1.5;background:" + bg + ";color:" + fg + ";";
  // v72：提示文字过一会儿自己消失（一直留着，「处理进度」那块就一直占着）：普通提示 15 秒、警告 60 秒。
  //      有任务在跑时先不清（进度会自己更新），过 5 秒再看。
  const tok = (setVideoStatus._tok = (setVideoStatus._tok || 0) + 1);
  clearTimeout(setVideoStatus._t);
  const clear = () => {
    if (tok !== setVideoStatus._tok) return;
    if (typeof _videoBusyNow === "function" && _videoBusyNow()) { setVideoStatus._t = setTimeout(clear, 5000); return; }
    const e2 = document.getElementById("videoStatus");
    if (e2) { e2.textContent = ""; e2.className = "video-status"; e2.style.cssText = ""; }
  };
  setVideoStatus._t = setTimeout(clear, kind === "warn" ? 60000 : 15000);
}

let _videoSubmitting = false;   // 防止「开始提取」被重复点 / 重复入队

// 设置「开始提取」按钮的外观：idle / submitting / running
// running 时按钮不禁用，而是变成「＋ 加入队列」——这样有新链接能直接点它排队。
function setVideoBtnState(state) {
  const btn = document.getElementById("videoGoBtn");
  if (!btn) return;
  if (!btn.dataset.label) btn.dataset.label = btn.textContent || "开始提取";
  if (state === "submitting") {
    btn.disabled = true; btn.classList.add("busy"); btn.classList.remove("queue");
    btn.textContent = "提交中…";
  } else if (state === "running") {
    btn.disabled = false; btn.classList.remove("busy"); btn.classList.add("queue");
    btn.textContent = "＋ 加入队列";
  } else {
    btn.disabled = false; btn.classList.remove("busy"); btn.classList.remove("queue");
    btn.textContent = btn.dataset.label;
  }
}

async function runVideoExtract() {
  if (_videoSubmitting) return;   // 正在提交，忽略重复点击
  const url = (document.getElementById("videoUrl").value || "").trim();
  if (!url) { setVideoStatus("先放点东西进来：一段文字、链接、GitHub 项目、文件或文件夹都行。", "warn"); return; }
  // v118：一个框做所有事：文件 / 文件夹 → 导入；「搜：领域」→ 搜索推荐；聊天 → 对话（v120）；其它照常提取
  if (_viForceNote) { _viForceNote = false; } else
  try {
    const kr = await fetch(BACKEND + "/intake_kind", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: url }) });
    const kd = await kr.json();
    const box0 = document.getElementById("videoUrl");
    if (kd && (kd.kind === "file" || kd.kind === "paths")) {
      if (box0) { box0.value = ""; viOnInputChanged(); }
      await viImportPaths(url.split(/\r?\n/).map((x) => x.trim()).filter(Boolean));
      return;
    }
    if (kd && kd.kind === "chat" && !_viForceNote) {
      if (box0) { box0.value = ""; viOnInputChanged(); }
      viSendToChat(url);
      return;
    }
    if (kd && kd.kind === "search") {
      if (box0) { box0.value = ""; viOnInputChanged(); }
      viRunSearch(kd.query || url);
      return;
    }
  } catch (e) { /* 认不出来就照常提取 */ }
  // 若当前已有任务在跑：这次点击 = 把这个链接加入队列（后端自动排队尾）
  if (_videoBusyNow()) {
    _videoSubmitting = true;
    setVideoStatus("正在加入队列…");
    try {
      await startVideoJob(url, document.getElementById("videoLevel").value);
      const box = document.getElementById("videoUrl");
      if (box) box.value = "";
      const bar = document.getElementById("videoQueuePrompt");
      if (bar) bar.remove();
    } finally { _videoSubmitting = false; }
    return;
  }
  const level = document.getElementById("videoLevel").value;
  _videoSubmitting = true;
  setVideoBtnState("submitting");
  try {
    await startVideoJob(url, level);
  } finally {
    _videoSubmitting = false;
    // 提交完成后按钮状态交给轮询根据 running 决定（pollVideoProgress 会刷新）
  }
}

// 当前是否有视频任务在跑（轮询会更新 _videoBusyFlag）
let _videoBusyFlag = false;
function _videoBusyNow() { return _videoBusyFlag; }

// 检测到新链接、且当前正忙 → 弹一个「加入队列」确认
function promptQueueNewLink(url) {
  const box = document.getElementById("videoUrl");
  setVideoStatus("当前有视频正在分析中。这个新链接要加入队列排队处理吗？", "warn");
  const resultEl = document.getElementById("videoResult");
  // 在状态区下方放一个临时操作条
  let bar = document.getElementById("videoQueuePrompt");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "videoQueuePrompt";
    bar.className = "video-queue-prompt";
    const statusEl = document.getElementById("videoStatus");
    if (statusEl && statusEl.parentNode) statusEl.parentNode.insertBefore(bar, statusEl.nextSibling);
  }
  bar.innerHTML = '<span class="vqp-text">🔗 新链接：' + escapeHtml(shortLabel(url)) + '</span>' +
    '<button class="vqp-add" id="vqpAdd">＋ 加入队列</button>' +
    '<button class="vqp-cancel" id="vqpCancel">忽略</button>';
  document.getElementById("vqpAdd").onclick = async () => {
    bar.remove();
    const level = document.getElementById("videoLevel").value;
    await startVideoJob(url, level);   // 后端会自动排到队尾
    if (box) box.value = "";
  };
  document.getElementById("vqpCancel").onclick = () => { bar.remove(); setVideoStatus(""); };
}

// 🦊 桌宠投喂：把拖到桌宠身上的「非视频」文件/文本，落到对话输入框里，
// 让你可以直接发给 AI（AI 会用自己的工具按需读这个路径）。视频类由
// startVideoFromFloat 接管去「视频」页提取。
window.petFeed = function (item) {
  if (!item) return;
  // v112：所有收进来的东西都先到「加工」：放进输入框、认出种类，你点「开始提取」
  try {
    document.querySelector('.nav-item[data-view="video"]').click();
    const vb = document.getElementById("videoUrl");
    if (vb) {
      vb.value = String(item).trim();
      viOnInputChanged();
      vb.focus();
      setVideoStatus("放进来了，确认一下按回车开始。", "ok", { holdMs: 6000 });
      return;
    }
  } catch (e) {}
  try { document.querySelector('.nav-item[data-view="chat"]').click(); } catch (e) {}
  var box = document.getElementById("input");
  if (box) {
    var prefix = box.value && box.value.trim() ? box.value.trim() + "\n" : "";
    var looksPath = /[\\/]/.test(item) && !/^https?:/i.test(item);
    box.value = prefix + (looksPath ? ("请看这个文件：" + item) : item);
    try { box.focus(); box.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
    try {
      box.style.transition = "box-shadow .2s, border-color .2s";
      box.style.boxShadow = "0 0 0 3px rgba(255,138,76,.45)";
      box.style.borderColor = "#ff8a4c";
      setTimeout(function () { box.style.boxShadow = ""; box.style.borderColor = ""; }, 1400);
    } catch (e) {}
  }
};

// 给悬浮按钮用：从剪贴板检测到的链接，填进输入框（不自动开始，等用户点提取）
window.startVideoFromFloat = function (url) {
  document.querySelector('.nav-item[data-view="video"]').click();
  const box = document.getElementById("videoUrl");
  if (box) {
    vExtractSetCollapsed(false);   // v72：卡片收起着也要让人看到填进来的链接
    box.value = url;
    // 滚动到可见、聚焦、并加一圈醒目高亮动画
    try { box.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
    box.focus();
    box.style.transition = "box-shadow .2s, border-color .2s";
    let flashes = 0;
    const flash = () => {
      const on = flashes % 2 === 0;
      box.style.boxShadow = on ? "0 0 0 3px rgba(47,111,237,.45)" : "0 0 0 3px rgba(47,111,237,0)";
      box.style.borderColor = on ? "#2f6fed" : "";
      flashes++;
      if (flashes < 6) setTimeout(flash, 350);
      else { box.style.boxShadow = ""; box.style.borderColor = ""; }
    };
    flash();
  }
  // 醒目状态横幅：明确告诉用户链接已到、下一步该点哪
  const busy = _videoBusyNow();
  const btnText = busy ? "＋ 加入队列" : "开始提取";
  setVideoStatus("🔗 链接已填好！在输入框里按回车就" + (busy ? "排进队列。" : "开始提取。"), "ok", { priority: true, holdMs: 6000 });   // v119：没有按钮了
  // 按钮强脉冲（不依赖 styles.css，直接内联动画）
  const btn = document.getElementById("videoGoBtn");
  if (btn) {
    btn.classList.add("pulse");
    btn.style.transition = "transform .25s, box-shadow .25s";
    let p = 0;
    const pulse = () => {
      const big = p % 2 === 0;
      btn.style.transform = big ? "scale(1.08)" : "scale(1)";
      btn.style.boxShadow = big ? "0 0 0 4px rgba(47,111,237,.35)" : "0 0 0 4px rgba(47,111,237,0)";
      p++;
      if (p < 8) setTimeout(pulse, 300);
      else { btn.style.transform = ""; btn.style.boxShadow = ""; btn.classList.remove("pulse"); }
    };
    pulse();
  }
};

// 把没有分段的整块文字，按标点/逗号/长度切成段落（老笔记也能变好看）
function paragraphizeCN(text) {
  if (!text) return "";
  if (text.indexOf("\n\n") >= 0) return text;  // 已分段
  const t = text.trim();
  let units;
  if (/[。！？!?…；;]/.test(t)) {
    units = t.match(/[^。！？!?…；;]*[。！？!?…；;]+/g) || [t];
    const tail = t.replace(/[^。！？!?…；;]*[。！？!?…；;]+/g, "");
    if (tail) units.push(tail);
  } else if (/[，,、]/.test(t)) {
    units = t.match(/[^，,、]*[，,、]+/g) || [t];
    const tail = t.replace(/[^，,、]*[，,、]+/g, "");
    if (tail) units.push(tail);
  } else {
    units = [];
    for (let i = 0; i < t.length; i += 40) units.push(t.slice(i, i + 40));
  }
  const paras = []; let cur = "";
  for (const u of units) { cur += u; if (cur.length >= 110) { paras.push(cur); cur = ""; } }
  if (cur) paras.push(cur);
  return paras.join("\n\n");
}

async function startVideoJob(url, level) {
  const resultEl = document.getElementById("videoResult");
  setVideoStatus("正在提交…");
  try {
    const s = settings();
    // 读「插图 / 跳转原片」开关（不存在就当未勾选）
    const shotEl = document.getElementById("videoShot");
    const linkEl = document.getElementById("videoLink");
    // 读「提取后自动 AI 分析」开关（不存在就当勾选=老行为）；
    // 不勾时只提取文字稿、完全不调 AI，插图也随之不可用。
    const anEl = document.getElementById("videoAnalyze");
    const analyze = !!(anEl && anEl.checked);      // v66：默认只提取原文，需要时再点「AI 分析」
    const screenshot = analyze && !!(shotEl && shotEl.checked);
    const link = !!(linkEl && linkEl.checked);
    // 读字幕模式（auto / subtitle_only / transcribe），默认 auto
    const modeEl = document.getElementById("videoSubMode");
    const mode = (modeEl && modeEl.value) || "auto";
    // v59：博主主页（选填）
    const creator_url = (document.getElementById("videoCreatorUrl")?.value || "").trim();

    // 先轻量检测有没有平台字幕（秒级，不下载正文）。失败/超时就当没字幕，照常提交。
    const hintEl = document.getElementById("videoSubHint");
    if (hintEl) { hintEl.style.display = "none"; hintEl.innerHTML = ""; }
    if (mode !== "transcribe") {
      try {
        setVideoStatus("正在检测字幕…");
        const dr = await fetch(BACKEND + "/video_detect_subtitle", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        const dd = await dr.json();
        if (dd && dd.has && hintEl) {
          const srcName = dd.source === "bilibili_subtitle" ? "B站字幕"
            : (dd.source === "youtube_subtitle" ? "YouTube 字幕" : "字幕");
          if (mode === "auto") {
            hintEl.innerHTML = "✅ 检测到" + srcName + "，直接用字幕（最快）。";
          } else {
            hintEl.innerHTML = "✅ 检测到" + srcName + "，将优先使用字幕。";
          }
          hintEl.style.display = "";
        } else if (hintEl && mode === "subtitle_only") {
          hintEl.innerHTML = "ℹ️ 没检测到平台字幕，将自动回退到视频听写。";
          hintEl.style.display = "";
        }
      } catch (e) { /* 检测失败：静默，照常提交 */ }
    }

    setVideoStatus("正在提交…");
    const resp = await fetch(BACKEND + "/video_transcribe", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, level, use_local: s.use_local, model: s.model,
                             screenshot, link, mode, analyze, creator_url }),
    });
    const data = await resp.json();

    if (data.need) {
      setVideoStatus("");
      resultEl.innerHTML =
        '<div class="video-need">第一次使用，需要先装一个语音转文字的小工具（' +
        data.need.join("、") + '）。<br>点下面按钮自动安装（要联网，约一两分钟）：' +
        '<br><br><button id="videoInstallBtn" class="send-btn">一键安装</button>' +
        '<div class="video-install-log" id="videoInstallLog"></div></div>';
      document.getElementById("videoInstallBtn").addEventListener("click", runVideoInstall);
      return;
    }
    if (data.error) { setVideoStatus("没成功：" + data.error, "warn"); return; }
    if (data.queued) {
      const box = document.getElementById("videoUrl");
      if (box) box.value = "";
      const crBox = document.getElementById("videoCreatorUrl");
      if (crBox) crBox.value = "";   // 已进队列，清空输入框，避免用户分不清这链接干嘛的
      if (data.position > 1) {
        setVideoStatus("已加入队列，前面还有 " + (data.position - 1) + " 个，排队处理中…");
      } else {
        setVideoStatus("已开始处理…");
      }
      pollVideoProgress();
    }
  } catch (e) {
    setVideoStatus("出错：" + e.message, "warn");
  }
}

// ── 本地文件导入：从电脑里选音/视频文件，直接提取文字（无需链接、无需下载）──
// author：本地文件没有作者信息，导入时用户可统一填一个（可空）；
// noteFolder：提取出的笔记自动归进这个笔记文件夹（可空 = 不归组）；
// opts：{level, analyze, screenshot, link} 覆盖面板设置（导入设置弹层传入，只对这批生效）。
async function startLocalVideoJob(filePath, author, noteFolder, opts) {
  opts = opts || {};
  const resultEl = document.getElementById("videoResult");
  setVideoStatus("正在提交本地文件…");
  try {
    const s = settings();
    const level = opts.level ||
      (document.getElementById("videoLevel") || {}).value || "balanced";
    const shotEl = document.getElementById("videoShot");
    const linkEl = document.getElementById("videoLink");
    const anEl = document.getElementById("videoAnalyze");
    const analyze = (typeof opts.analyze === "boolean")
      ? opts.analyze : !!(anEl && anEl.checked);      // v66：默认只提取原文
    const screenshot = analyze && ((typeof opts.screenshot === "boolean")
      ? opts.screenshot : !!(shotEl && shotEl.checked));
    const link = (typeof opts.link === "boolean")
      ? opts.link : !!(linkEl && linkEl.checked);
    // v59：博主主页（选填）。导入文件夹会一个个调用这里，第一次读到后记在 opts 里，后面的文件接着用
    if (typeof opts.creator_url !== "string") {
      const crBox = document.getElementById("videoCreatorUrl");
      opts.creator_url = ((crBox && crBox.value) || "").trim();
      if (crBox) crBox.value = "";
    }

    const resp = await fetch(BACKEND + "/video_transcribe", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ local_path: filePath, level,
                             use_local: s.use_local, model: s.model,
                             screenshot, link, analyze,
                             author: (author || "").trim(),
                             note_folder: (noteFolder || "").trim(),
                             creator_url: opts.creator_url || "" }),
    });
    const data = await resp.json();

    if (data.need) {
      setVideoStatus("");
      resultEl.innerHTML =
        '<div class="video-need">第一次使用，需要先装一个语音转文字的小工具（' +
        data.need.join("、") + '）。<br>点下面按钮自动安装（要联网，约一两分钟）：' +
        '<br><br><button id="videoInstallBtn" class="send-btn">一键安装</button>' +
        '<div class="video-install-log" id="videoInstallLog"></div></div>';
      document.getElementById("videoInstallBtn").addEventListener("click", runVideoInstall);
      return;
    }
    if (data.error) { setVideoStatus("没成功：" + data.error, "warn"); return; }
    if (data.queued) {
      if (data.position > 1) {
        setVideoStatus("已加入队列，前面还有 " + (data.position - 1) + " 个，排队处理中…");
      } else {
        setVideoStatus("已开始处理本地文件…");
      }
      pollVideoProgress();
    }
  } catch (e) {
    setVideoStatus("出错：" + e.message, "warn");
  }
}

// ── 页面内输入弹层 ──
// Electron 里 window.prompt() 被禁用（confirm/alert 可用，prompt 不行），
// 所以自己做一个。返回 Promise：点确定 → 输入的字符串（可为空串）；
// 点取消 / Esc / 点遮罩 → null。用法和 prompt 一致，只是要 await。
function askText(opts) {
  opts = opts || {};
  return new Promise((resolve) => {
    const old = document.getElementById("cxAskText");
    if (old) old.remove();
    const wrap = document.createElement("div");
    wrap.id = "cxAskText";
    wrap.style.cssText =
      "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.35);" +
      "display:flex;align-items:center;justify-content:center";
    const box = document.createElement("div");
    box.style.cssText =
      "background:var(--surface-2,#fff);color:var(--text,#222);" +
      "border:0.5px solid var(--border,#3a3a3a);border-radius:12px;" +
      "box-shadow:0 12px 40px rgba(0,0,0,.25);padding:16px 18px;" +
      "width:min(420px,86vw)";
    const title = document.createElement("div");
    title.style.cssText = "font-size:14px;font-weight:600;margin:0 0 6px";
    title.textContent = opts.title || "请输入";
    box.appendChild(title);
    if (opts.desc) {
      const desc = document.createElement("div");
      desc.style.cssText =
        "font-size:12.5px;color:var(--text-dim,#9aa);line-height:1.6;" +
        "margin:0 0 10px;white-space:pre-line";
      desc.textContent = opts.desc;
      box.appendChild(desc);
    }
    const input = document.createElement("input");
    input.type = "text";
    input.className = "text-input";
    input.style.cssText = "width:100%;box-sizing:border-box";
    input.value = opts.value || "";
    input.placeholder = opts.placeholder || "";
    box.appendChild(input);
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:flex-end;gap:8px;margin-top:12px";
    const cancel = document.createElement("button");
    cancel.textContent = opts.cancelText || "取消";
    cancel.style.cssText =
      "border:0.5px solid var(--border,#3a3a3a);background:transparent;" +
      "color:var(--text,#222);border-radius:8px;padding:6px 14px;" +
      "font-size:13px;cursor:pointer";
    const ok = document.createElement("button");
    ok.className = "send-btn";
    ok.textContent = opts.okText || "确定";
    row.appendChild(cancel); row.appendChild(ok);
    box.appendChild(row);
    wrap.appendChild(box);
    const done = (val) => { try { wrap.remove(); } catch (_) {} resolve(val); };
    cancel.addEventListener("click", () => done(null));
    ok.addEventListener("click", () => done(input.value));
    wrap.addEventListener("click", (e) => { if (e.target === wrap) done(null); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); done(input.value); }
      else if (e.key === "Escape") { e.preventDefault(); done(null); }
    });
    document.body.appendChild(wrap);
    setTimeout(() => { input.focus(); input.select(); }, 0);
  });
}

// ── 导入设置弹层 ──
// 选好文件/文件夹后先弹这个设置界面：作者、归档文件夹、质量、是否自动 AI 分析、插图，
// 都确认好了点「开始提取」才真正开工。默认值取自面板里的高级选项，
// 但这里改的只对这一批导入生效，不会动面板设置。
// 返回 Promise：确定 → {author, noteFolder, level, analyze, screenshot}；取消 → null。
function askImportOptions(cfg) {
  cfg = cfg || {};
  return new Promise((resolve) => {
    const old = document.getElementById("cxImportOpts");
    if (old) old.remove();
    const wrap = document.createElement("div");
    wrap.id = "cxImportOpts";
    wrap.style.cssText =
      "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.35);" +
      "display:flex;align-items:center;justify-content:center";
    const box = document.createElement("div");
    box.style.cssText =
      "background:var(--surface-2,#fff);color:var(--text,#222);" +
      "border:0.5px solid var(--border,#3a3a3a);border-radius:12px;" +
      "box-shadow:0 12px 40px rgba(0,0,0,.25);padding:16px 18px;" +
      "width:min(470px,88vw)";
    const h = document.createElement("div");
    h.style.cssText = "font-size:14px;font-weight:600;margin:0 0 6px";
    h.textContent = "导入设置 · 共 " + (cfg.count || 0) + " 个文件";
    box.appendChild(h);
    const d = document.createElement("div");
    d.style.cssText =
      "font-size:12.5px;color:var(--text-dim,#9aa);line-height:1.6;" +
      "margin:0 0 12px;white-space:pre-line";
    d.textContent =
      (cfg.source ? ("来自文件夹「" + cfg.source + "」（含子文件夹）。\n") : "") +
      "确认下面的设置后点「开始提取」。这些设置只对这一批生效，不会改动面板里的高级选项。";
    box.appendChild(d);

    const row = (label, ctrl) => {
      const r = document.createElement("div");
      r.style.cssText = "display:flex;align-items:center;gap:10px;margin:0 0 10px";
      const l = document.createElement("span");
      l.style.cssText = "flex:0 0 96px;font-size:13px;color:var(--text-dim,#9aa)";
      l.textContent = label;
      r.appendChild(l); r.appendChild(ctrl);
      box.appendChild(r);
    };
    const mkInput = (val, ph) => {
      const i = document.createElement("input");
      i.type = "text"; i.className = "text-input";
      i.style.cssText = "flex:1 1 auto;min-width:0;box-sizing:border-box";
      i.value = val || ""; i.placeholder = ph || "";
      return i;
    };
    const authorIn = mkInput(cfg.targetFolder || cfg.source || "", "作者名（可留空）");
    row("👤 作者", authorIn);
    const folderIn = mkInput(cfg.targetFolder || cfg.source || "",
                             "笔记文件夹（留空 = 不归组）");
    row("📂 归入文件夹", folderIn);

    const levelSel = document.createElement("select");
    levelSel.className = "text-input";
    levelSel.style.cssText = "flex:1 1 auto";
    [["speed", "快速（糙）"], ["balanced", "均衡（推荐）"],
     ["accurate", "精准（慢）"], ["ultra", "超精准（大模型）"], ["ja", "日语专用（kotoba）"], ["anime", "日语·情绪/小声（Anime）"]].forEach(([v, t]) => {
      const o = document.createElement("option");
      o.value = v; o.textContent = t; levelSel.appendChild(o);
    });
    levelSel.value = (document.getElementById("videoLevel") || {}).value || "accurate";
    row("🎚 质量", levelSel);

    const mkCheck = (label, checked) => {
      const lab = document.createElement("label");
      lab.style.cssText =
        "display:flex;align-items:center;gap:7px;font-size:13px;cursor:pointer;flex:1 1 auto";
      const c = document.createElement("input");
      c.type = "checkbox"; c.checked = !!checked;
      const sp = document.createElement("span");
      sp.textContent = label;
      lab.appendChild(c); lab.appendChild(sp);
      return { lab, c };
    };
    const anEl0 = document.getElementById("videoAnalyze");
    const an = mkCheck("提取完马上 AI 分析（不勾 = 只存原文，需要时再点「🤖 AI 分析」）",
                       !!(anEl0 && anEl0.checked));     // v66：默认不勾
    row("🤖 AI 分析", an.lab);
    const shotEl0 = document.getElementById("videoShot");
    const shot = mkCheck("插图（自动截取关键画面，稍慢）", !!(shotEl0 && shotEl0.checked));
    row("🖼 插图", shot.lab);
    const syncShot = () => {
      if (!an.c.checked) {
        shot.c.checked = false; shot.c.disabled = true; shot.lab.style.opacity = "0.45";
        shot.lab.title = "不做 AI 分析就没有截图标记，插图不可用";
      } else {
        shot.c.disabled = false; shot.lab.style.opacity = ""; shot.lab.title = "";
      }
    };
    an.c.addEventListener("change", syncShot);
    syncShot();

    const btns = document.createElement("div");
    btns.style.cssText = "display:flex;justify-content:flex-end;gap:8px;margin-top:14px";
    const cancel = document.createElement("button");
    cancel.textContent = "取消";
    cancel.style.cssText =
      "border:0.5px solid var(--border,#3a3a3a);background:transparent;" +
      "color:var(--text,#222);border-radius:8px;padding:6px 14px;" +
      "font-size:13px;cursor:pointer";
    const ok = document.createElement("button");
    ok.className = "send-btn"; ok.textContent = "开始提取";
    btns.appendChild(cancel); btns.appendChild(ok);
    box.appendChild(btns);
    wrap.appendChild(box);
    const done = (val) => { try { wrap.remove(); } catch (_) {} resolve(val); };
    cancel.addEventListener("click", () => done(null));
    wrap.addEventListener("click", (e) => { if (e.target === wrap) done(null); });
    ok.addEventListener("click", () => done({
      author: (authorIn.value || "").trim().slice(0, 40),
      noteFolder: (folderIn.value || "").trim().slice(0, 30),
      level: levelSel.value || "balanced",
      analyze: !!an.c.checked,
      screenshot: !!(an.c.checked && shot.c.checked),
    }));
    document.body.appendChild(wrap);
    setTimeout(() => { authorIn.focus(); authorIn.select(); }, 0);
  });
}

// 点「📁 导入本地文件」：弹原生文件选择框 → 导入设置弹层 → 确认后逐个入队。
// targetFolder：从某个笔记文件夹的 📥 进来时传入，归档文件夹默认填它。
async function pickAndImportLocal(targetFolder) {
  try {
    if (!window.crayfish || typeof window.crayfish.pickMediaFiles !== "function") {
      setVideoStatus("当前版本不支持本地导入（请更新 main.js / preload.js 后重启）。", "warn");
      return;
    }
    const paths = await window.crayfish.pickMediaFiles();
    if (!paths || !paths.length) return;   // 用户取消
    const o = await askImportOptions({
      count: paths.length, source: "", targetFolder: targetFolder || "" });
    if (!o) return;   // 取消 = 不导入
    if (o.noteFolder) vnSetFolderOpen(o.noteFolder, true);   // 展开，方便看到成品进来
    for (const p of paths) {
      await startLocalVideoJob(p, o.author, o.noteFolder, o);
    }
    setVideoStatus("📁 已提交 " + paths.length + " 个文件进队列，将逐个提取"
                   + (o.noteFolder ? ("，完成的笔记会自动归进「" + o.noteFolder + "」") : "")
                   + (o.analyze ? "，提取完会马上 AI 分析" : "（只提取原文，需要时再点「🤖 AI 分析」）") + "。",
                   "ok", { priority: true, holdMs: 6000 });
  } catch (e) {
    setVideoStatus("选文件出错：" + (e && e.message ? e.message : e), "warn");
  }
}
document.getElementById("videoLocalBtn")?.addEventListener("click", () => pickAndImportLocal());

// 点「📂 导入文件夹」：选磁盘文件夹 → 自动递归找出所有音/视频（含子文件夹，
// 抖音下载工具常常一个视频一个子文件夹）→ 导入设置弹层 → 确认后逐个入队。
// targetFolder：从某个笔记文件夹的 📥 进来时传入，归档文件夹默认填它。
async function pickAndImportFolder(targetFolder) {
  try {
    if (!window.crayfish || typeof window.crayfish.pickMediaFolder !== "function") {
      setVideoStatus("当前版本不支持导入文件夹（请更新 main.js / preload.js 后重启软件）。", "warn");
      return;
    }
    const r = await window.crayfish.pickMediaFolder();
    if (!r) return;   // 用户取消
    if (!r.files || !r.files.length) {
      setVideoStatus("「" + (r.name || "这个文件夹") + "」里没找到能导入的文件（音视频、PDF、Word、Excel、TXT…，已自动搜过子文件夹）。", "warn");
      return;
    }
    const o = await askImportOptions({
      count: r.files.length, source: r.name || "",
      targetFolder: targetFolder || "" });
    if (!o) return;   // 取消 = 整个不导入
    if (o.noteFolder) vnSetFolderOpen(o.noteFolder, true);   // 展开，方便看到成品进来
    let n = 0;
    for (const p of r.files) {
      await startLocalVideoJob(p, o.author, o.noteFolder, o);
      n++;
    }
    setVideoStatus("📂 已提交 " + n + " 个文件进队列，将逐个提取"
                   + (o.noteFolder ? ("，完成的笔记会自动归进「" + o.noteFolder + "」") : "")
                   + (o.analyze ? "，提取完会马上 AI 分析" : "（只提取原文，需要时再点「🤖 AI 分析」）") + "。",
                   "ok", { priority: true, holdMs: 6000 });
  } catch (e) {
    setVideoStatus("导入文件夹出错：" + (e && e.message ? e.message : e), "warn");
  }
}
document.getElementById("videoFolderBtn")?.addEventListener("click", () => pickAndImportFolder());

function parseVideoPercent(detail) {
  const m = (detail || "").match(/(\d+)\s*%/);
  return m ? Math.max(0, Math.min(100, parseInt(m[1]))) : null;
}

function shortLabel(u) {
  if (!u) return "";
  return u.length > 48 ? u.slice(0, 46) + "…" : u;
}

// 可展开的「视频名」标签：默认截断显示一部分，鼠标悬停或点击展开全部，移开/再点折叠。
// full=完整文本（标题或链接），limit=折叠时显示多少字。
function expandableLabel(full, limit) {
  full = (full || "").trim();
  if (!full) return '<span class="vt-url">（未知）</span>';
  limit = limit || 32;
  const isLong = full.length > limit;
  const shortText = isLong ? full.slice(0, limit) + "…" : full;
  const safeFull = escapeHtml(full);
  const safeShort = escapeHtml(shortText);
  if (!isLong) {
    return '<span class="vt-url" title="' + safeFull + '">' + safeShort + "</span>";
  }
  // data-full 存完整文本；CSS class vt-name 控制展开/折叠；点击切换 expanded
  return '<span class="vt-name" data-full="' + safeFull + '" data-short="' + safeShort +
    '" title="点击展开/折叠完整名称，或鼠标悬停查看">' + safeShort + "</span>";
}

let _videoQueueExpanded = false;   // 排队列表是否展开（默认折叠，只显示前几个）
let _lastVideoTasksP = null;       // 最近一次进度数据：点展开/收起时立即用它重绘
const VQ_SHOW_N = 3;               // 折叠状态下显示的排队条数

function renderVideoTasks(p) {
  const el = document.getElementById("videoTasks");
  if (!el) return;
  _lastVideoTasksP = p;
  // 内容指纹：任务状态/进度/队列没变化时跳过重渲染，避免每 1.2 秒重建 DOM、
  // 把用户正在悬停或点开的视频名重置掉。注意：不含 elapsed（它每秒变），
  // 已用时秒数改为单独更新那个 span，不重建整块。
  try {
    const sig = JSON.stringify({
      r: !!p.running, s: p.stage, d: p.detail,
      c: p.current_label || p.current_url,
      e: _videoQueueExpanded,
      q: (p.queue || []).map((x) => (x && typeof x === "object") ? (x.title || x.url) : x),
    });
    if (el.dataset.sig === sig) {
      // 内容没变，只刷新「已用时」秒数（不重建 DOM，不打断展开/悬停）
      const tEl = el.querySelector(".vt-time");
      if (tEl && p.running) tEl.textContent = "已用时 " + (p.elapsed || 0) + " 秒";
      return;
    }
    el.dataset.sig = sig;
  } catch (e) {}
  let h = "";
  if (p.running) {
    const pct = parseVideoPercent(p.detail);
    const stage = p.stage || "处理中";
    const detail = p.detail ? "：" + p.detail : "";
    const bar = pct != null
      ? '<div class="vbar"><div class="vbar-fill" style="width:' + pct + '%"></div></div>'
      : '<div class="vbar"><div class="vbar-fill indet"></div></div>';
    // 正在处理：current_label 可能是标题（爬到了）或链接（还没爬到）
    const curName = p.current_label || p.current_url || "";
    h += '<div class="vtask running">' +
      '<div class="vtask-top"><span class="vt-badge">生成中</span> ' +
      escapeHtml(stage + detail) +
      ' <span class="vt-time">已用时 ' + (p.elapsed || 0) + ' 秒</span>' +
      '<button class="vt-cancel" id="vtCancelBtn" title="停止正在进行的任务并清空全部排队（几秒内生效；已识别的进度会保留，同一链接下次可续传）">✕ 全部取消</button>' +
      '</div>' +
      bar +
      '<div class="vt-namewrap">🎬 ' + expandableLabel(curName, 40) + '</div></div>';
  }
  // ── 排队列表：条数多时默认折叠（只显示前 VQ_SHOW_N 个），点一行提示展开/收起，
  //    免得导入一个文件夹进来几十条，把下面「已存的视频笔记」顶到看不见。──
  const queue = p.queue || [];
  if (queue.length === 0) _videoQueueExpanded = false;   // 队列清空 → 下一批默认折叠
  const collapsible = queue.length > VQ_SHOW_N;
  const collapsedNow = collapsible && !_videoQueueExpanded;
  const shown = collapsedNow ? queue.slice(0, VQ_SHOW_N) : queue;
  const toggleRow = (label) =>
    '<div class="vq-toggle" style="text-align:center;padding:7px 10px;margin:2px 0 6px;' +
    'border:0.5px dashed var(--border,#3a3a3a);border-radius:9px;' +
    'color:var(--text-dim,#9aa);font-size:12.5px;cursor:pointer;user-select:none">' +
    label + '</div>';
  if (collapsible && _videoQueueExpanded) {
    // 展开状态：顶部先给一个收起入口（几十条时不用拖到最底下才能收）
    h += toggleRow("▴ 收起排队列表（只显示前 " + VQ_SHOW_N + " 个）");
  }
  shown.forEach((item, i) => {
    // 队列项现在是 {url, title} 对象；兼容老格式（纯字符串）
    let name = "", hasTitle = false;
    if (item && typeof item === "object") {
      hasTitle = !!item.title;
      name = item.title || item.url || "";
    } else {
      name = item || "";
    }
    // 还没爬到标题（只有链接）时，给个「获取名称中…」的小提示，让用户知道在努力，
    // 而不是以为坏了。爬到后下次轮询就会换成真标题。
    const tip = (!hasTitle && name)
      ? '<span style="color:var(--text-dim,#9aa);font-size:12px;margin-left:6px">（获取名称中…）</span>'
      : "";
    h += '<div class="vtask queued">' +
      '<div class="vtask-top"><span class="vt-badge q">排队中</span> 第 ' + (i + 1) + ' 个</div>' +
      '<div class="vbar"><div class="vbar-fill q"></div></div>' +
      '<div class="vt-namewrap">🎬 ' + expandableLabel(name, 36) + tip + '</div></div>';
  });
  if (collapsedNow) {
    h += toggleRow("▾ 还有 " + (queue.length - VQ_SHOW_N) + " 个在排队，点击展开全部");
  } else if (collapsible) {
    h += toggleRow("▴ 收起");
  }
  el.innerHTML = h;
  const cancelBtn = document.getElementById("vtCancelBtn");
  if (cancelBtn) cancelBtn.addEventListener("click", cancelVideoJobs);
  // 排队列表的展开/收起：点提示行切换，并立刻用最近一次数据重绘
  el.querySelectorAll(".vq-toggle").forEach((t) => {
    t.addEventListener("click", () => {
      _videoQueueExpanded = !_videoQueueExpanded;
      el.dataset.sig = "";
      renderVideoTasks(_lastVideoTasksP || p);
    });
  });
  // 给可展开的视频名绑定交互：
  //  · 点击 = 锁定展开/折叠（再点取消锁定）
  //  · 悬停 = 临时展开；移开 = 折叠回去（但若已点击锁定展开，则保持）
  el.querySelectorAll(".vt-name").forEach((sp) => {
    sp.addEventListener("click", () => {
      const locked = sp.classList.toggle("expanded");
      sp.dataset.locked = locked ? "1" : "";
      sp.textContent = locked ? sp.dataset.full : sp.dataset.short;
    });
    sp.addEventListener("mouseenter", () => {
      sp.textContent = sp.dataset.full;
    });
    sp.addEventListener("mouseleave", () => {
      // 没被点击锁定才折叠回去
      if (sp.dataset.locked !== "1") sp.textContent = sp.dataset.short;
    });
  });
}

// 全部取消：中断当前正在跑的任务 + 清空排队
async function cancelVideoJobs() {
  const btn = document.getElementById("vtCancelBtn");
  if (btn) { btn.disabled = true; btn.textContent = "取消中…"; }
  try {
    await fetch(BACKEND + "/video_cancel", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: "{}" });
    setVideoStatus("🛑 已请求全部取消：排队已清空，正在中断当前任务（几秒内生效）…", "warn",
                   { priority: true, holdMs: 5000 });
  } catch (e) {
    setVideoStatus("取消出错：" + e.message, "warn");
  }
}

let _videoPollTimer = null;
let _lastVideoResultId = 0;
let _lastDoneTitle = "";        // 最近一个完成并存档的标题，用于状态横幅
let _lastRunningUrl = "";       // 上一轮正在处理的链接，用于检测「切到下一个」
function pollVideoProgress() {
  if (_videoPollTimer) return;  // 已经在轮询了
  const tick = async () => {
    try {
      const r = await fetch(BACKEND + "/video_progress");
      const p = await r.json();
      renderVideoTasks(p);

      // 有新完成的结果就渲染出来，并记下它的标题用于状态横幅
      if (p.result_id && p.result_id > _lastVideoResultId && p.result) {
        _lastVideoResultId = p.result_id;
        const res = p.result;
        if (res.ok) {
          mountVideoDone(res);              // v59：只显示一行「完成」，详情去「最新提取」看
          loadVideoNotes();
          _lastDoneTitle = (res.title || "").trim();
        } else if (res.cancelled) {
          // 用户主动取消的：不当成失败吓人
          _lastDoneTitle = "";
          setVideoStatus("🛑 已全部取消（已识别的进度会保留，同一链接下次可续传）。", "ok",
                         { priority: true, holdMs: 6000 });
        } else if (res.error) {
          // 失败的也要让用户知道，而不是悄无声息
          _lastDoneTitle = "";
          setVideoStatus("⚠ 有一个没成功：" + res.error + "（已记到下面「提取失败」里，以后可以点「重新提取」）", "warn");
          setTimeout(vnFailRefresh, 1500);   // v90：后端记好了再刷新清单
        }
      }

      if (p.running || p.queue_len > 0 || p.has_chat_tasks) {
        _videoBusyFlag = true;
        if (!_videoSubmitting) setVideoBtnState("running");
        // ── 关键：始终给出清晰的状态报告，而不是清空 ──
        // 队列里还有多少（含正在跑的这一个）
        const qlen = p.queue_len || 0;
        const curUrl = p.current_url || p.current_label || "";
        // 检测「切到下一个任务」：正在处理的链接变了
        if (curUrl && curUrl !== _lastRunningUrl) {
          _lastRunningUrl = curUrl;
        }
        let banner = "";
        if (p.running) {
          // 有正在跑的任务：报告「正在处理第几个 / 共几个」+ 上一个是否已存档
          const totalLeft = qlen + 1;  // 正在跑的 + 排队的
          const pos = totalLeft > 1 ? `（还剩 ${totalLeft} 个）` : "";
          banner = `⏳ 正在处理${pos}…`;
          if (_lastDoneTitle && !document.querySelector("#videoResult .vdone")) {   // v59：完成那一行已经写了，不重复
            banner = `✅ 上一个已完成并存档：《${_lastDoneTitle.slice(0, 24)}》　|　` + banner;
          }
        } else if (qlen > 0) {
          banner = `⏳ 排队中，还有 ${qlen} 个待处理…`;
        }
        setVideoStatus(banner, "ok");
      } else {
        // 全部处理完，停止轮询
        _videoBusyFlag = false;
        if (!_videoSubmitting) setVideoBtnState("idle");
        clearInterval(_videoPollTimer); _videoPollTimer = null;
        renderVideoTasks({ running: false, queue: [] });
        _lastRunningUrl = "";
        const res = p.result || {};
        if (res.cancelled) {
          setVideoStatus("🛑 已全部取消（已识别的进度会保留，同一链接下次可续传）。", "ok");
        } else if (res.ok || _lastDoneTitle) {
          if (document.querySelector("#videoResult .vdone")) {
            setVideoStatus("");      // v59：下面「✅ 提取完成」那一行已经说清楚了，不再多一条横幅
          } else {
            const t = _lastDoneTitle ? `：《${_lastDoneTitle.slice(0, 24)}》` : "";
            setVideoStatus(`🎉 全部完成，已自动存档${t}`, "ok");
          }
        } else if (res.error) {
          setVideoStatus("⚠ 最后一个没成功：" + res.error + "（已记到下面「提取失败」里，以后可以点「重新提取」）", "warn");
          setTimeout(vnFailRefresh, 1500);
        } else {
          setVideoStatus("");
        }
      }
    } catch (e) {
      clearInterval(_videoPollTimer); _videoPollTimer = null;
      setVideoStatus("查询进度出错：" + e.message, "warn");
    }
  };
  tick();
  _videoPollTimer = setInterval(tick, 1200);
}

async function runVideoInstall() {
  const btn = document.getElementById("videoInstallBtn");
  const log = document.getElementById("videoInstallLog");
  if (btn) { btn.disabled = true; btn.textContent = "安装中…（请稍候）"; }
  if (log) log.textContent = "正在下载并安装，期间请勿关闭软件…";
  try {
    const resp = await fetch(BACKEND + "/video_install", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await resp.json();
    if (log) log.textContent = data.message || "";
    if (data.ok) {
      setVideoStatus("依赖装好了，在输入框里再按一次回车即可。", "ok");
      if (btn) btn.textContent = "已安装 ✓";
    } else if (btn) {
      btn.disabled = false; btn.textContent = "重试安装";
    }
  } catch (e) {
    if (log) log.textContent = "安装出错：" + e.message;
    if (btn) { btn.disabled = false; btn.textContent = "重试安装"; }
  }
}

// ────────── v59：维护工具 · 依赖版本 ──────────
// 每个依赖显示「已装版本 + 是不是最新」。已是最新时「更新」按钮变灰点不了；查到新版才亮起来。
// 有没有新版由后端让 pip 试装一下来判断（和真正更新走同一个源），结果记 6 小时，可点「↻ 重新检查」。
let _vdepTimer = null;
let _vdepInstalling = false;

function renderVideoDeps(st) {
  if (!st) return;
  const box = document.getElementById("videoDepStatus");
  const btn = document.getElementById("videoDepBtn");
  const badge = document.getElementById("videoDepBadge");
  const n = st.updates || 0;
  if (box) {
    let html = '<div class="vdep-list">';
    (st.items || []).forEach((it) => {
      let txt, cls;
      if (it.missing) { txt = "未安装" + (st.known && it.latest ? "，可装 " + it.latest : ""); cls = "warn"; }
      else if (it.update) { txt = "⬆ 有新版 " + it.latest; cls = "up"; }
      else if (st.known) { txt = "✓ 已是最新"; cls = "ok"; }
      else { txt = st.checking ? "检查中…" : "—"; cls = "dim"; }
      if (it.restart) txt += "（关掉软件再打开才生效）";
      html += '<div class="vdep-row"><span class="vdep-name">' + escapeHtml(it.name) + "</span>" +
        '<span class="vdep-ver">' + escapeHtml(it.installed || "—") + "</span>" +
        '<span class="vdep-st ' + cls + '">' + escapeHtml(txt) + "</span></div>";
    });
    html += "</div>";
    let foot = "";
    if (st.installing) foot = "正在更新…";
    else if (st.checking) foot = "正在检查有没有新版本…（十几秒）";
    else if (st.error) foot = "⚠ " + st.error;
    else if (st.known) foot = "上次检查：" + vnFmtWhen(st.checked_at * 1000) + (st.source ? "（" + st.source + "）" : "");
    html += '<div class="vdep-foot"><span>' + escapeHtml(foot) + "</span>" +
      (st.checking || st.installing ? "" : '<a href="#" id="videoDepRecheck">↻ 重新检查</a>') + "</div>";
    box.innerHTML = html;
    const re = document.getElementById("videoDepRecheck");
    if (re) re.addEventListener("click", (e) => { e.preventDefault(); loadVideoDeps(true); });
  }
  if (btn && !_vdepInstalling) {
    if (st.installing) { btn.disabled = true; btn.textContent = "更新中…"; btn.title = ""; }
    else if (st.checking) { btn.disabled = true; btn.textContent = "正在检查新版本…"; btn.title = ""; }
    else if (n > 0) {
      btn.disabled = false; btn.textContent = "⬇ 更新依赖（" + n + " 个有新版）";
      btn.title = "联网把有新版的依赖更新到最新（约一两分钟）";
    } else if (st.up_to_date) {
      btn.disabled = true; btn.textContent = "✓ 已是最新";
      btn.title = "所有依赖都是最新版本；查到新版时这个按钮会亮起来";
    } else {
      btn.disabled = false; btn.textContent = "🔧 安装/更新依赖";
      btn.title = "没查到新版本信息（可能没网），也可以直接点更新";
    }
  }
  if (badge) {
    if (n > 0) { badge.hidden = false; badge.className = "vdep-badge up"; badge.textContent = "⬆ " + n + " 个依赖有新版"; }
    else if (st.up_to_date) { badge.hidden = false; badge.className = "vdep-badge ok"; badge.textContent = "✓ 依赖已是最新"; }
    else badge.hidden = true;
  }
}

async function loadVideoDeps(refresh) {
  clearTimeout(_vdepTimer);
  let st;
  try {
    st = await (await fetch(BACKEND + "/video_deps" + (refresh ? "?refresh=1" : ""), { cache: "no-store" })).json();
  } catch (e) { return; }
  renderVideoDeps(st);
  if (st.checking || st.installing) _vdepTimer = setTimeout(() => loadVideoDeps(false), 2000);
}

async function runVideoDepInstall() {
  const btn = document.getElementById("videoDepBtn");
  const log = document.getElementById("videoDepLog");
  _vdepInstalling = true;
  if (btn) { btn.disabled = true; btn.textContent = "更新中…（约一两分钟，别关软件）"; }
  if (log) {
    log.style.display = ""; log.classList.remove("ok", "bad");
    log.textContent = "正在联网更新 yt-dlp、faster-whisper、curl_cffi、gmssl（先走清华镜像，不通会自动换源）…";
  }
  try {
    const data = await (await fetch(BACKEND + "/video_install", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).json();
    _vdepInstalling = false;
    if (log) {
      let t = data.message || (data.ok ? "依赖已就绪。" : "更新没完成。");
      if (!data.ok && data.log) t += "\n\n" + String(data.log).slice(-1200);
      log.textContent = t;
      log.classList.add(data.ok ? "ok" : "bad");
    }
    if (data.deps) renderVideoDeps(data.deps); else loadVideoDeps(false);
    if (!data.ok && btn) { btn.disabled = false; btn.textContent = "重试更新"; }
  } catch (e) {
    _vdepInstalling = false;
    if (log) { log.style.display = ""; log.textContent = "更新出错：" + e.message; log.classList.add("bad"); }
    if (btn) { btn.disabled = false; btn.textContent = "重试更新"; }
  }
}
document.getElementById("videoDepBtn")?.addEventListener("click", runVideoDepInstall);

// ────────── 维护工具抽屉 + 抖音自检 / 诊断 / yt-dlp 新版 ──────────

// 维护工具抽屉：默认收起，点标题行展开/收起
function setVideoToolsOpen(open) {
  const body = document.getElementById("videoToolsBody");
  const caret = document.getElementById("videoToolsCaret");
  if (!body) return;
  body.style.display = open ? "" : "none";
  if (caret) caret.textContent = open ? "▾" : "▸";
  if (open) loadVideoDeps(false);          // v59：展开时刷新依赖版本
}
function toggleVideoTools() {
  const body = document.getElementById("videoToolsBody");
  if (body) setVideoToolsOpen(body.style.display === "none");
}
function openVideoTools() {
  setVideoToolsOpen(true);
  // 展开后顺手把详细结果填进抽屉里的横幅
  try { runVideoHealthCheck(true); } catch (_) {}
}
document.getElementById("videoToolsHead")?.addEventListener("click", toggleVideoTools);
document.getElementById("videoToolsHead")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleVideoTools(); }
});

// 主区上的「细提示条」：出问题时才显示，带一个「打开维护工具」链接（不自动展开抽屉）
function _setNotice(html, kind) {
  const el = document.getElementById("videoNotice");
  if (!el) return;
  const palette = {
    warn: { bg: "rgba(255,170,0,.12)", bd: "rgba(255,170,0,.55)" },
    bad:  { bg: "rgba(220,53,69,.12)", bd: "rgba(220,53,69,.55)" },
  }[kind] || { bg: "rgba(127,127,127,.12)", bd: "rgba(127,127,127,.5)" };
  el.style.display = "";
  el.style.background = palette.bg;
  el.style.border = "1px solid " + palette.bd;
  el.innerHTML = html +
    ' <a href="#" id="videoNoticeOpen" style="margin-left:6px;white-space:nowrap">打开维护工具 ›</a>';
  const a = document.getElementById("videoNoticeOpen");
  if (a) a.addEventListener("click", (e) => { e.preventDefault(); openVideoTools(); });
}
function _hideNotice() {
  const el = document.getElementById("videoNotice");
  if (el) el.style.display = "none";
}

function _setHealthBanner(html, kind) {
  const el = document.getElementById("videoHealthBanner");
  if (!el) return;
  const palette = {
    ok:   { bg: "rgba(40,167,69,.12)",  bd: "rgba(40,167,69,.5)" },
    warn: { bg: "rgba(255,170,0,.12)",  bd: "rgba(255,170,0,.55)" },
    bad:  { bg: "rgba(220,53,69,.12)",  bd: "rgba(220,53,69,.55)" },
  }[kind] || { bg: "rgba(127,127,127,.12)", bd: "rgba(127,127,127,.5)" };
  el.style.display = "";
  el.style.background = palette.bg;
  el.style.border = "1px solid " + palette.bd;
  el.innerHTML = html;
  const copyBtn = document.getElementById("videoDiagCopyBtn");
  if (copyBtn) copyBtn.addEventListener("click", copyVideoDiag);
}

async function copyVideoDiag() {
  try {
    const r = await fetch(BACKEND + "/video_diag");
    const d = await r.json();
    if (d && d.text) {
      await navigator.clipboard.writeText(d.text);
      ["videoDiagCopyBtn", "videoDiagCopyBtn2"].forEach((id) => {
        const b = document.getElementById(id);
        if (b) { const t = b.textContent; b.textContent = "已复制 ✓";
                 setTimeout(() => { b.textContent = t; }, 2500); }
      });
    } else {
      alert("还没有诊断文件。等下次提取失败后会自动生成。" + (d && d.path ? "\n位置：" + d.path : ""));
    }
  } catch (e) { alert("复制诊断出错：" + e.message); }
}
document.getElementById("videoDiagCopyBtn2")?.addEventListener("click", copyVideoDiag);

// manual=true：手动点（抽屉已展开），正常也把结果写进抽屉横幅。
// manual=false：启动悄悄查，只在「真出问题」时弹主区细提示条，不自动展开抽屉。
async function runVideoHealthCheck(manual) {
  const btn = document.getElementById("videoHealthBtn");
  const orig = (btn && btn.textContent) || "🩺 检测抖音是否正常";
  if (manual && btn) { btn.disabled = true; btn.textContent = "检测中…（约几秒）"; }
  if (manual) _setHealthBanner("正在用一条测试视频跑一遍解析，请稍候…", "warn");
  try {
    const r = await fetch(BACKEND + "/video_health");
    const d = await r.json();
    const dy = (d && d.douyin) || {};
    const yt = (d && d.ytdlp) || {};
    const diag = (d && d.diag) || {};

    let ytLine = "";
    if (yt.update_available) {
      ytLine = '<br>🆕 yt-dlp 有新版（当前 ' + (yt.current || "?") +
               '，最新 ' + (yt.latest || "?") +
               '）。可在下面点「⬇ 更新依赖」升级——抖音的问题有时升级后就好了。';
    }
    const diagBtn = diag && diag.exists
      ? ' <button id="videoDiagCopyBtn" class="send-btn" style="font-size:12px;padding:3px 8px;margin-left:6px">复制诊断信息</button>'
      : "";

    // —— 抽屉里的详细横幅（手动时一定写；自动时也写好，等用户点开能看到）——
    if (dy.status === "ok") {
      _setHealthBanner("✅ 抖音提取功能正常。" + ytLine, ytLine ? "warn" : "ok");
    } else if (dy.status === "dep_missing") {
      _setHealthBanner("⚠ " + escapeHtml(dy.detail || "缺少 curl_cffi") +
        "<br>点「安装/更新依赖」装上即可。" + ytLine, "warn");
    } else if (dy.status === "network_fail") {
      _setHealthBanner("⚠ 这次没连上抖音（多半是网络/临时波动，也可能是测试视频被删），" +
        "不一定是软件坏了。真要确认，直接拿一条你的抖音链接去提取最准。<br>" +
        escapeHtml(dy.detail || "") + ytLine, "warn");
    } else if (dy.status === "structure_changed" || dy.status === "blocked_or_changed") {
      _setHealthBanner("⚠ 自检的测试视频没解析成功。可能是抖音改版/拦截，也可能只是这条测试视频被删了。<br>" +
        "以你自己的抖音链接能不能提取为准；若也失败，软件会自动留诊断信息，发给开发者即可修。" +
        diagBtn + ytLine, "warn");
    } else {
      _setHealthBanner("⚠ 自检结果：" + escapeHtml(dy.detail || dy.status || "未知") + ytLine, "warn");
    }

    // —— 主区细提示条：只在「真出问题」时弹（缺依赖 / 真发生过提取失败）——
    // 像"测试视频被删/网络波动"这种自检自身的问题，不再误报。
    if (!manual) {
      if (dy.status === "dep_missing") {
        _setNotice("⚠ 视频功能缺少组件（curl_cffi），抖音可能用不了。", "warn");
      } else if (diag && diag.exists) {
        _setNotice("⚠ 上次有视频没提取成功，已生成诊断信息。", "bad");
      } else {
        _hideNotice();  // 没真问题就不打扰
      }
    }
  } catch (e) {
    if (manual) _setHealthBanner("检测出错：" + escapeHtml(e.message), "warn");
  } finally {
    if (manual && btn) { btn.disabled = false; btn.textContent = orig; }
  }
}
document.getElementById("videoHealthBtn")?.addEventListener("click", () => runVideoHealthCheck(true));

// 启动后悄悄自检一次（延迟几秒，不抢占启动；只有真出问题才弹主区细提示条）
setTimeout(() => { try { runVideoHealthCheck(false); } catch (_) {} }, 4000);
// v59：顺便看看依赖有没有新版（维护工具标题行会显示「有新版 / 已是最新」，不用点开）
setTimeout(() => { try { loadVideoDeps(false); } catch (_) {} }, 6000);

let _currentVideo = null;  // 当前展示的视频数据（用于复制/导出）

/* =======================================================================
 *  轻量思维导图渲染器（纯 SVG，无第三方库，离线可用）
 *  - 输入：{ data:{text, note?, color?}, children:[...] } 递归树
 *  - 布局：横向（中心在左，逐层向右展开），自动按子树高度排布，不重叠
 *  - 交互：点节点折叠/展开、拖拽平移、滚轮缩放、工具条（适应/放大/缩小/重新生成/导出PNG）
 *  - 主题：用页面 CSS 变量取色，跟随明暗主题
 * ===================================================================== */

// 把思维导图树转成「缩进大纲」文本（复制/朗读/导出用）
function mindmapToOutline(root, depth, lines) {
  lines = lines || [];
  if (!root) return "";
  if (depth === undefined) depth = 0;
  const d = root.data || {};
  const text = (d.text || "").trim();
  if (text) {
    const prefix = depth === 0 ? "" : ("  ".repeat(depth - 1) + "- ");
    lines.push(prefix + text + (d.note ? "（" + d.note + "）" : ""));
  }
  const kids = Array.isArray(root.children) ? root.children : [];
  for (const k of kids) mindmapToOutline(k, depth + 1, lines);
  return lines.join("\n");
}

// 读取一个 CSS 变量（取不到给兜底值）
function _cssVar(name, fallback) {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) ? v.trim() : fallback;
  } catch (_) { return fallback; }
}

// 估算文本像素宽度（粗略：中文按 ~fontSize，英文/数字按 ~0.6*fontSize）
function _measureText(text, fontSize) {
  let w = 0;
  for (const ch of String(text || "")) {
    w += /[\u4e00-\u9fff\uff00-\uffef]/.test(ch) ? fontSize : fontSize * 0.6;
  }
  return Math.max(w, fontSize); // 至少一个字宽
}

// 把节点文本按最大宽度折行，返回行数组
function _wrapLines(text, fontSize, maxWidth) {
  const words = String(text || "").split("");
  const lines = [];
  let cur = "", curW = 0;
  for (const ch of words) {
    const cw = /[\u4e00-\u9fff\uff00-\uffef]/.test(ch) ? fontSize : fontSize * 0.6;
    if (ch === "\n") { lines.push(cur); cur = ""; curW = 0; continue; }
    if (curW + cw > maxWidth && cur) { lines.push(cur); cur = ch; curW = cw; }
    else { cur += ch; curW += cw; }
  }
  if (cur) lines.push(cur);
  return lines.length ? lines : [""];
}

function renderMindmapInto(container, root, onRegen) {
  if (!container) return;
  container.innerHTML = "";

  // —— 配置 ——
  const FONT = 15;                 // 基础字号（调大一点，更清晰）
  const MAX_TEXT_W = 220;          // 单节点文本最大宽度（超出折行）
  const PAD_X = 13, PAD_Y = 8;     // 节点内边距
  const GAP_X = 56;                // 层与层水平间距
  const GAP_Y = 14;                // 同层兄弟垂直间距
  const LINE_H = FONT * 1.35;      // 行高
  const MIN_FIT_SCALE = 0.55;      // 「适应」时的最小缩放：低于它就不再缩，改用滚动看（保证字够大）

  const colText = _cssVar("--text", "#1f2329");
  const colDim = _cssVar("--text-dim", "#8a8a93");
  const colLine = _cssVar("--line", "#e3e3e8");
  const colAccent = _cssVar("--accent", "#3b6cff");
  const colAccentSoft = _cssVar("--accent-soft", "rgba(59,108,255,.12)");
  const colCardBg = _cssVar("--card", _cssVar("--bg", "#ffffff"));

  // 深浅主题判断（用于根节点文字反白）：简单看强调色亮度
  function _isDark(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec((hex || "").trim());
    if (!m) return false;
    const n = parseInt(m[1], 16);
    const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    return (0.299 * r + 0.587 * g + 0.114 * b) < 140;
  }

  // —— 给每个节点建立内部布局对象 ——
  let _uid = 0;
  function build(node, depth) {
    const d = node.data || {};
    const text = (d.text || "·").toString();
    const lines = _wrapLines(text, FONT, MAX_TEXT_W);
    let textW = 0;
    for (const ln of lines) textW = Math.max(textW, _measureText(ln, FONT));
    const w = Math.min(textW, MAX_TEXT_W) + PAD_X * 2;
    const h = lines.length * LINE_H + PAD_Y * 2;
    const kids = Array.isArray(node.children) ? node.children : [];
    const item = {
      id: ++_uid,
      depth,
      text,
      note: (d.note || "").toString(),
      color: (typeof d.color === "string" && d.color.trim().startsWith("#")) ? d.color.trim() : "",
      lines,
      w, h,
      // 默认只展开到一级分支：深度>=1 且有子节点的，初始折叠起来（点开看细节）
      collapsed: depth >= 1 && kids.length > 0,
      children: [],
      x: 0, y: 0,          // 节点左上角坐标
      subTop: 0, subBot: 0 // 子树纵向范围（布局用）
    };
    for (const k of kids) item.children.push(build(k, depth + 1));
    return item;
  }
  const tree = build(root, 0);

  // —— 纵向布局：后序遍历，叶子按顺序堆叠，父节点居中于子树 ——
  let _cursorY = 0;
  function layoutV(item) {
    if (item.collapsed || !item.children.length) {
      item.subTop = _cursorY;
      item.cy = _cursorY + item.h / 2;
      _cursorY += item.h + GAP_Y;
      item.subBot = _cursorY;
      return;
    }
    const top = _cursorY;
    for (const c of item.children) layoutV(c);
    const first = item.children[0], last = item.children[item.children.length - 1];
    item.cy = (first.cy + last.cy) / 2;        // 居中于第一个和最后一个子节点
    item.subTop = top;
    item.subBot = _cursorY;
  }

  // —— 横向布局：x 按深度累加（按每层最大宽度对齐更整齐，这里用累进） ——
  function layoutH(item, x) {
    item.x = x;
    const nextX = x + item.w + GAP_X;
    if (!item.collapsed) for (const c of item.children) layoutH(c, nextX);
  }

  // —— SVG 容器 ——
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "mm-svg");
  svg.style.width = "100%";
  svg.style.height = "100%";       // 高度交给外层 .mm-stage 控制（默认 70vh，可全屏）
  svg.style.display = "block";
  svg.style.cursor = "grab";
  const gRoot = document.createElementNS(NS, "g");   // 总变换组（平移/缩放）
  svg.appendChild(gRoot);

  // 一键展开全部 / 收起到一级（总览 ↔ 细节）
  function setCollapsedAll(collapsed) {
    (function walk(item) {
      if (item.depth >= 1 && item.children.length) item.collapsed = collapsed;
      item.children.forEach(walk);
    })(tree);
    draw();
    requestAnimationFrame(() => { try { fitView(); } catch (_) {} });
  }

  // 视图变换状态
  let scale = 1, tx = 0, ty = 0;
  function applyTransform() {
    gRoot.setAttribute("transform", "translate(" + tx + "," + ty + ") scale(" + scale + ")");
  }

  // —— 真正画图：清空 gRoot，重新计算布局并绘制 ——
  function draw() {
    while (gRoot.firstChild) gRoot.removeChild(gRoot.firstChild);
    _cursorY = 0;
    layoutV(tree);
    layoutH(tree, 0);

    // 先画连线（在节点下层）
    const gLines = document.createElementNS(NS, "g");
    const gNodes = document.createElementNS(NS, "g");
    gRoot.appendChild(gLines);
    gRoot.appendChild(gNodes);

    function nodeColor(item) {
      if (item.depth === 0) return colAccent;
      // 一级分支用模型给的颜色；更深层继承最近祖先的颜色（视觉成组）
      return item.color || item._inherit || colAccent;
    }

    function drawNode(item, parent) {
      // 继承色：把最近的彩色祖先色往下传
      if (item.depth >= 1) item._inherit = item.color || (parent ? parent._inherit || parent.color : "") || colAccent;
      const c = nodeColor(item);

      // 连线：父右中 → 子左中，三次贝塞尔
      if (parent) {
        const x1 = parent.x + parent.w, y1 = parent.cy;
        const x2 = item.x, y2 = item.cy;
        const mx = (x1 + x2) / 2;
        const path = document.createElementNS(NS, "path");
        path.setAttribute("d", "M" + x1 + "," + y1 + " C" + mx + "," + y1 + " " + mx + "," + y2 + " " + x2 + "," + y2);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", item.color || (parent._inherit || colLine));
        path.setAttribute("stroke-width", item.depth <= 1 ? "2" : "1.5");
        path.setAttribute("opacity", "0.55");
        gLines.appendChild(path);
      }

      // 节点组
      const g = document.createElementNS(NS, "g");
      g.setAttribute("class", "mm-node");
      g.setAttribute("transform", "translate(" + item.x + "," + (item.cy - item.h / 2) + ")");
      g.style.cursor = item.children.length ? "pointer" : "default";

      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("width", item.w);
      rect.setAttribute("height", item.h);
      rect.setAttribute("rx", "9");
      rect.setAttribute("ry", "9");
      if (item.depth === 0) {
        rect.setAttribute("fill", colAccent);
        rect.setAttribute("stroke", colAccent);
      } else {
        rect.setAttribute("fill", colCardBg);
        rect.setAttribute("stroke", c);
        rect.setAttribute("stroke-width", "1.5");
      }
      g.appendChild(rect);

      // 文本（多行）
      const txt = document.createElementNS(NS, "text");
      txt.setAttribute("x", PAD_X);
      txt.setAttribute("y", PAD_Y + FONT);
      txt.setAttribute("font-size", FONT);
      txt.setAttribute("font-family", "inherit");
      const rootDark = _isDark(colAccent);
      txt.setAttribute("fill", item.depth === 0 ? (rootDark ? "#fff" : "#fff") : colText);
      if (item.depth <= 1) txt.setAttribute("font-weight", "600");
      item.lines.forEach((ln, i) => {
        const tspan = document.createElementNS(NS, "tspan");
        tspan.setAttribute("x", PAD_X);
        tspan.setAttribute("dy", i === 0 ? 0 : LINE_H);
        tspan.textContent = ln;
        txt.appendChild(tspan);
      });
      g.appendChild(txt);

      // note：作为原生悬停提示
      if (item.note) {
        const title = document.createElementNS(NS, "title");
        title.textContent = item.note;
        g.appendChild(title);
      }

      // 折叠指示点（有子节点时，画在右侧）
      if (item.children.length) {
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", item.w);
        dot.setAttribute("cy", item.h / 2);
        dot.setAttribute("r", "5.5");
        dot.setAttribute("fill", item.collapsed ? c : colCardBg);
        dot.setAttribute("stroke", c);
        dot.setAttribute("stroke-width", "1.5");
        g.appendChild(dot);
        if (item.collapsed) {
          // 折叠时显示子节点个数
          const cnt = document.createElementNS(NS, "text");
          cnt.setAttribute("x", item.w + 11);
          cnt.setAttribute("y", item.h / 2 + 4);
          cnt.setAttribute("font-size", "11");
          cnt.setAttribute("fill", colDim);
          cnt.textContent = _countLeaves(item);
          g.appendChild(cnt);
        }
      }

      // 点击折叠/展开
      g.addEventListener("click", (e) => {
        e.stopPropagation();
        if (!item.children.length) return;
        item.collapsed = !item.collapsed;
        draw();
      });

      gNodes.appendChild(g);

      if (!item.collapsed) for (const c2 of item.children) drawNode(c2, item);
    }
    drawNode(tree, null);

    // 记录内容包围盒，供「适应窗口」用
    _bbox = { w: _maxRight(tree), h: _cursorY };
  }

  function _countLeaves(item) {
    if (!item.children.length) return 1;
    let n = 0;
    const walk = (it) => { if (!it.children.length) n++; else it.children.forEach(walk); };
    item.children.forEach(walk);
    return n;
  }
  function _maxRight(item) {
    let m = item.x + item.w;
    if (!item.collapsed) for (const c of item.children) m = Math.max(m, _maxRight(c));
    return m;
  }

  let _bbox = { w: 100, h: 100 };

  // —— 适应窗口：算缩放使整张图放进可视区；但有「最小缩放」下限，
  //    图太大时不再继续缩小（那样字会看不清），而是保证字够大、超出部分靠拖拽/滚动看。——
  function fitView() {
    const rect = svg.getBoundingClientRect();
    const vw = rect.width || 800, vh = rect.height || 520;
    const pad = 28;
    const sx = (vw - pad * 2) / Math.max(_bbox.w, 1);
    const sy = (vh - pad * 2) / Math.max(_bbox.h, 1);
    let s = Math.min(sx, sy, 1.5);
    if (!isFinite(s) || s <= 0) s = 1;
    // 关键：不让缩放低于下限。低于下限说明图很大 → 保持可读字号，改用平移看全。
    const floored = s < MIN_FIT_SCALE;
    scale = floored ? MIN_FIT_SCALE : s;
    tx = pad;
    // 没触底就纵向居中；触底了就顶部对齐，方便从上往下拖着看
    ty = floored ? pad : Math.max(pad, (vh - _bbox.h * scale) / 2);
    applyTransform();
    // 触底时给个轻提示：可以拖动查看
    _setHint(floored
      ? "图较大，已保证文字清晰；可拖动画布或用「全屏」查看全部"
      : "");
  }

  // —— 缩放（以视图中心为锚点）——
  function zoomBy(factor) {
    const rect = svg.getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 2;
    const ns = Math.min(Math.max(scale * factor, 0.2), 3);
    // 保持中心点不动
    tx = cx - (cx - tx) * (ns / scale);
    ty = cy - (cy - ty) * (ns / scale);
    scale = ns;
    applyTransform();
  }

  // —— 拖拽平移 ——
  let dragging = false, lastX = 0, lastY = 0;
  svg.addEventListener("mousedown", (e) => {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
    svg.style.cursor = "grabbing";
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    tx += e.clientX - lastX; ty += e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    applyTransform();
  });
  window.addEventListener("mouseup", () => {
    if (dragging) { dragging = false; svg.style.cursor = "grab"; }
  });
  // 滚轮缩放（按指针位置锚定）
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const px = e.clientX - rect.left, py = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const ns = Math.min(Math.max(scale * factor, 0.2), 3);
    tx = px - (px - tx) * (ns / scale);
    ty = py - (py - ty) * (ns / scale);
    scale = ns;
    applyTransform();
  }, { passive: false });

  // —— 导出 PNG ——
  function exportPng() {
    try {
      const pad = 24;
      const w = Math.ceil(_bbox.w + pad * 2), h = Math.ceil(_bbox.h + pad * 2);
      // 克隆 gRoot，套一个干净的 svg，平移 pad，背景填充
      const clone = svg.cloneNode(true);
      clone.setAttribute("width", w);
      clone.setAttribute("height", h);
      clone.setAttribute("viewBox", "0 0 " + w + " " + h);
      const inner = clone.querySelector("g");
      if (inner) inner.setAttribute("transform", "translate(" + pad + "," + pad + ") scale(1)");
      // 背景矩形
      const bg = document.createElementNS(NS, "rect");
      bg.setAttribute("x", 0); bg.setAttribute("y", 0);
      bg.setAttribute("width", w); bg.setAttribute("height", h);
      bg.setAttribute("fill", colCardBg);
      clone.insertBefore(bg, clone.firstChild);

      const xml = new XMLSerializer().serializeToString(clone);
      const svg64 = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));
      const img = new Image();
      img.onload = () => {
        const ratio = window.devicePixelRatio || 2;
        const canvas = document.createElement("canvas");
        canvas.width = w * ratio; canvas.height = h * ratio;
        const ctx = canvas.getContext("2d");
        ctx.scale(ratio, ratio);
        ctx.drawImage(img, 0, 0);
        canvas.toBlob((blob) => {
          if (!blob) return;
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "思维导图.png";
          document.body.appendChild(a); a.click();
          setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        }, "image/png");
      };
      img.src = svg64;
    } catch (e) {
      alert("导出图片失败：" + e);
    }
  }

  // —— 工具条 ——
  const bar = document.createElement("div");
  bar.className = "mm-bar";
  bar.innerHTML =
    '<button class="mm-tool" data-act="expand" title="展开所有分支">⊞ 展开全部</button>' +
    '<button class="mm-tool" data-act="collapse" title="只看一级分支（总览）">⊟ 收起到一级</button>' +
    '<span class="mm-bar-div"></span>' +
    '<button class="mm-tool" data-act="fit" title="适应窗口（保证文字清晰）">⤢ 适应</button>' +
    '<button class="mm-tool" data-act="in" title="放大">＋</button>' +
    '<button class="mm-tool" data-act="out" title="缩小">－</button>' +
    '<span class="mm-bar-sp"></span>' +
    '<span class="mm-hint" id="mmHint"></span>' +
    '<button class="mm-tool" data-act="full" title="全屏查看">⛶ 全屏</button>' +
    '<button class="mm-tool" data-act="png" title="导出为图片">🖼 导出图片</button>' +
    (onRegen ? '<button class="mm-tool" data-act="regen" title="让 AI 重新生成">↻ 重新生成</button>' : "");

  // 提示文字（适应触底时显示）
  function _setHint(msg) {
    const h = bar.querySelector("#mmHint");
    if (h) h.textContent = msg || "";
  }

  // —— 全屏：优先用浏览器原生全屏；失败则降级为覆盖整窗的固定层 ——
  let _isFull = false;
  function _fullBtn() { return bar.querySelector('[data-act="full"]'); }
  function _syncFullBtn() {
    const b = _fullBtn();
    if (b) { b.textContent = _isFull ? "⛶ 退出全屏" : "⛶ 全屏"; b.title = _isFull ? "退出全屏 (Esc)" : "全屏查看"; }
  }
  function enterFull() {
    wrap.classList.add("mm-fullscreen");
    _isFull = true;
    _syncFullBtn();
    // 原生全屏（拿不到也没关系，CSS 固定层已经铺满）
    try { if (wrap.requestFullscreen) wrap.requestFullscreen({ navigationUI: "hide" }).catch(() => {}); } catch (_) {}
    // 等布局生效后重新适应，用满大屏
    setTimeout(() => { try { fitView(); } catch (_) {} }, 60);
  }
  function exitFull() {
    wrap.classList.remove("mm-fullscreen");
    _isFull = false;
    _syncFullBtn();
    try { if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {}); } catch (_) {}
    setTimeout(() => { try { fitView(); } catch (_) {} }, 60);
  }
  function toggleFull() { _isFull ? exitFull() : enterFull(); }
  // Esc 退出（原生全屏会自动退；这里兜底处理降级层）
  const _onKey = (e) => { if (e.key === "Escape" && _isFull) exitFull(); };
  document.addEventListener("keydown", _onKey);
  // 原生全屏被用户/系统退出时，同步样式
  const _onFsChange = () => { if (!document.fullscreenElement && _isFull) { wrap.classList.remove("mm-fullscreen"); _isFull = false; _syncFullBtn(); setTimeout(() => { try { fitView(); } catch (_) {} }, 60); } };
  document.addEventListener("fullscreenchange", _onFsChange);

  bar.addEventListener("click", (e) => {
    const b = e.target.closest(".mm-tool"); if (!b) return;
    const act = b.dataset.act;
    if (act === "expand") setCollapsedAll(false);
    else if (act === "collapse") setCollapsedAll(true);
    else if (act === "fit") fitView();
    else if (act === "in") zoomBy(1.18);
    else if (act === "out") zoomBy(0.85);
    else if (act === "full") toggleFull();
    else if (act === "png") exportPng();
    else if (act === "regen" && onRegen) onRegen();
  });

  const wrap = document.createElement("div");
  wrap.className = "mm-wrap";
  const stage = document.createElement("div");   // 舞台：放 svg，固定/全屏高度都由它控制
  stage.className = "mm-stage";
  stage.appendChild(svg);
  wrap.appendChild(bar);
  wrap.appendChild(stage);
  container.appendChild(wrap);

  _syncFullBtn();

  // 首绘 + 适应
  draw();
  applyTransform();
  // 等容器拿到真实宽度后再适应一次
  requestAnimationFrame(() => { try { fitView(); } catch (_) {} });
}

// v59：提取完成只显示一行「✅ 提取完成《标题》」，不再把整篇笔记铺开（画面太花）。
// 详细内容去「已存的视频笔记 → 最新提取」里点开看。
function mountVideoDone(res) {
  const el = document.getElementById("videoResult");
  if (!el) return;
  const title = (res.title || "").trim() || "（无标题）";
  const cr = res.creator || {};
  const au = (res.uploader || cr.key || "").trim();
  let crTxt = "";
  if (cr.status === "bound") crTxt = cr.auto ? "已自动识别博主主页" : "已绑定博主主页";
  else if (cr.status === "pending") crTxt = "博主主页还在识别";
  else if (cr.status === "fail") crTxt = "没找到博主主页";
  el.innerHTML = "";
  const box = document.createElement("div");
  box.className = "vdone";
  const isDoc = res.source === "doc" || res.source === "article";
  box.innerHTML = '<span class="vdone-ok">✅ ' + (isDoc ? "导入完成" : "提取完成") + "</span>" +
    '<span class="vdone-title">《' + escapeHtml(title) + "》</span>" +
    (au ? '<span class="vdone-who">👤 ' + escapeHtml(au) + (crTxt ? " · " + escapeHtml(crTxt) : "") + "</span>" : "");
  box.querySelector(".vdone-title").title = title;
  if (cr.status === "fail" && cr.message) box.querySelector(".vdone-who").title = cr.message + "（可以在图标视图里点博主头像手动绑定）";
  const go = document.createElement("button");
  go.type = "button"; go.className = "vdone-go"; go.textContent = "去「已提取」看 ›";
  go.title = "在下面的「已提取」里找到这一条（点标题就能看完整笔记）";
  go.addEventListener("click", () => vnRevealRecent(res.saved_as));
  if (res.unanalyzed && res.saved_as) {          // v66：默认只提取原文；需要时点这里分析
    const ab = vnAnButton(res.saved_as, "🤖 AI 分析", "vdone-go vdone-an", false);
    box.appendChild(ab);
  }
  box.appendChild(go);
  const pv = (res.page_videos || []).filter(Boolean);      // v65：文章页面里还有视频
  if (pv.length) {
    const vb = document.createElement("button");
    vb.type = "button"; vb.className = "vdone-go vdone-videos";
    vb.textContent = "🎬 页面里还有 " + pv.length + " 个视频，接着提取";
    vb.title = pv.join("\n");
    vb.addEventListener("click", async () => {
      vb.disabled = true; vb.textContent = "正在加入队列…";
      const level = (document.getElementById("videoLevel") || {}).value || "balanced";
      let n = 0;
      for (const u of pv) { try { await startVideoJob(u, level); n++; } catch (_) {} }
      vb.textContent = "✓ " + n + " 个视频已加入队列";
    });
    box.appendChild(vb);
  }
  vnDoneAutoHide(box);            // v72：处理完一会儿就自己消失，不一直占着
  if (isDoc && res.truncated) {
    const tr = document.createElement("span");
    tr.className = "vdone-who"; tr.textContent = "（原文太长，只导入了前 40 万字）";
    box.appendChild(tr);
  }
  el.appendChild(box);
}

// v72：「处理进度」里的完成那一行，15 秒后自己淡出消失（整张卡片随之收起）。
// 鼠标停在上面、或者点了「AI 分析」正在分析时先不消失；分析完再等 15 秒。
function vnDoneAutoHide(box) {
  clearTimeout(vnDoneAutoHide._t);
  let waitUntil = Date.now() + 15000;
  const tick = () => {
    if (!box.isConnected) return;
    const analyzing = !!box.querySelector('[data-an-state="running"]');
    if (analyzing) waitUntil = Date.now() + 15000;
    if (analyzing || box.matches(":hover") || Date.now() < waitUntil) {
      vnDoneAutoHide._t = setTimeout(tick, 1000);
      return;
    }
    box.classList.add("vdone-fade");
    setTimeout(() => { try { box.remove(); } catch (_) {} }, 600);
  };
  vnDoneAutoHide._t = setTimeout(tick, 1000);
}

// v72：「开始提取」卡片可以收起（点标题行），记住上次的选择
function vExtractSetCollapsed(c) {
  const card = document.querySelector(".v-card-extract");
  if (!card) return;
  card.classList.toggle("v-collapsed", !!c);
  const caret = card.querySelector(".v-extract-caret");
  if (caret) caret.textContent = c ? "▸" : "▾";
  try { localStorage.setItem("vExtractCollapsed", c ? "1" : "0"); } catch (_) {}
}
(function vExtractInit() {
  const card = document.querySelector(".v-card-extract");
  const head = card && card.querySelector(".v-card-head");
  if (!head) return;
  const caret = document.createElement("span");
  caret.className = "v-extract-caret"; caret.textContent = "▾";
  head.insertBefore(caret, head.firstChild);
  const hint = document.createElement("span");
  hint.className = "v-extract-hint"; hint.textContent = "已收起，点这里展开";
  head.appendChild(hint);
  head.title = "点击收起 / 展开";
  head.addEventListener("click", (e) => {
    if (e.target.closest("button, input, select, a")) return;
    vExtractSetCollapsed(!card.classList.contains("v-collapsed"));
  });
  card.addEventListener("click", (e) => {            // 收起时点卡片任何地方都能展开
    if (card.classList.contains("v-collapsed") && !e.target.closest(".v-card-head")) vExtractSetCollapsed(false);
  });
  let c = false;
  try { c = localStorage.getItem("vExtractCollapsed") === "1"; } catch (_) {}
  vExtractSetCollapsed(c);
})();

// ════════════════ v65：导入的文档 / 网页文章的类型标签 ════════════════
function vnKindInfo(kind) {
  const s = String(kind || "");
  if (/PDF/i.test(s)) return { short: "PDF", cls: "k-pdf", color: "#c0392b" };
  if (/Word|WPS 文字|RTF/.test(s)) return { short: /RTF/.test(s) ? "RTF" : "Word", cls: "k-word", color: "#2b5797" };
  if (/Excel|表格/.test(s)) return { short: /CSV/.test(s) ? "CSV" : "Excel", cls: "k-excel", color: "#1e7145" };
  if (/PPT|演示/.test(s)) return { short: "PPT", cls: "k-ppt", color: "#d24726" };
  if (/公众号/.test(s)) return { short: "公众号", cls: "k-wx", color: "#07a35a" };
  if (/文章|网页/.test(s)) return { short: "文章", cls: "k-web", color: "#3b6fd8" };
  if (/GitHub/.test(s)) return { short: "GitHub", cls: "k-gh", color: "#24292f" };   // v112
  if (s === "文字") return { short: "文字", cls: "k-text", color: "#555c66" };
  if (/Markdown/.test(s)) return { short: "MD", cls: "k-text", color: "#555c66" };
  if (/电子书/.test(s)) return { short: "电子书", cls: "k-book", color: "#8e44ad" };
  return { short: "文本", cls: "k-text", color: "#555c66" };
}

function vnKindBadge(kind) {
  const k = vnKindInfo(kind);
  const b = document.createElement("span");
  b.className = "vn-kind " + k.cls;
  b.textContent = k.short;
  b.title = "导入的" + kind;
  return b;
}

function vnDocIcon(kind) {
  const k = vnKindInfo(kind);
  return '<svg viewBox="0 0 48 60" aria-hidden="true"><path d="M7 2h25l13 13v41a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#fff" stroke="#c8c8c8" stroke-width="2"/>' +
    '<path d="M32 2v11a2 2 0 0 0 2 2h11" fill="#f1f1f1" stroke="#c8c8c8" stroke-width="2"/>' +
    '<path d="M12 22h24M12 28h24M12 34h15" stroke="#a9b3c1" stroke-width="2.6" stroke-linecap="round"/>' +
    '<rect x="5" y="41" width="40" height="13" rx="2" fill="' + k.color + '"/>' +
    '<text x="25" y="50.6" text-anchor="middle" font-size="' + (k.short.length > 3 ? 7.5 : 9.5) +
    '" font-weight="700" fill="#fff" font-family="Segoe UI, Microsoft YaHei, sans-serif">' + escapeHtml(k.short) + "</text></svg>";
}

// 滚到「最新提取」，展开它、回到第一页，把刚提取的那条闪一下
async function vnRevealRecent(name) {
  const prefs = vnRecentPrefs();
  prefs.open = true; vnRecentSave(prefs);
  _vnRecentPage = 1;
  _vnIconPath = null;
  await loadVideoNotes();
  const rec = document.getElementById("vnRecent");
  if (!rec) return;
  rec.scrollIntoView({ block: "start", behavior: "smooth" });
  if (name) {
    const row = Array.from(rec.querySelectorAll(".video-note-item")).find((x) => x.dataset.name === name);
    if (row) { row.classList.add("vn-flash"); setTimeout(() => row.classList.remove("vn-flash"), 2600); }
  }
}

function mountVideoResult(data, target) {
  const resultEl = target || document.getElementById("videoResult");
  if (!target) _currentVideo = data;  // 只有视频标签页才更新全局当前视频
  // 只有在「视频面板进度卡」里展示完成结果时（target 为空）才加这条完成标头；
  // 在成长库点开历史笔记（target 不为空）不需要，避免重复。
  const doneBadge = !target
    ? '<div style="display:flex;align-items:center;gap:8px;margin:0 0 10px;' +
      'padding:7px 12px;border-radius:9px;background:rgba(46,160,90,.12);' +
      'color:#2ea05a;font-size:13px;font-weight:500;">' +
      '<span>✅ 这条已提取完成并自动存档</span>' +
      '<span style="color:var(--text-dim,#8a8a93);font-weight:400">' +
      '（下面是结果，新任务的进度看上方进度条）</span></div>'
    : "";
  const head =
    (data.title ? "<h2>" + escapeHtml(data.title) + "</h2>" : "") +
    (data.uploader ? "<p style='color:var(--text-dim);margin-top:-6px'>作者：" +
      escapeHtml(data.uploader) + "</p>" : "");
  // 页面内的二级标签行：显示当前标签 + 一个「管理标签」按钮（仅对已存档、知道文件名的视频可编辑）
  const canEditTags = !!(data._noteName && data._noteCat === "video");
  const tagRowHtml = '<div class="vtag-row" id="vTagRow"></div>';
  resultEl.innerHTML =
    doneBadge +
    '<div class="video-toolbar">' +
      '<button class="vtab active" data-tab="analysis">🤖 AI 分析</button>' +
      '<button class="vtab" data-tab="mindmap">🧠 思维导图</button>' +
      '<button class="vtab" data-tab="transcript">📝 完整原文</button>' +
      '<span class="vdetail" id="vDetailToggle">' +
        '<button class="vd active" data-d="full">详细</button>' +
        '<button class="vd" data-d="brief">简洁</button>' +
      '</span>' +
      '<span class="vspacer"></span>' +
      '<button class="vbtn vbtn-speak" id="vSpeakBtn">🔊 朗读</button>' +
      '<button class="vbtn" id="vCopyBtn">复制本页</button>' +
      '<button class="vbtn" id="vExportBtn">导出 Markdown</button>' +
      '<button class="vbtn" id="vCollapseBtn" title="折叠正文，方便看下面的内容">▾ 折叠</button>' +
    '</div>' +
    head +
    tagRowHtml +
    '<div class="vtab-body" id="vAnalysis">' + renderMarkdown(data.analysis || "（无分析）") + '</div>' +
    '<div class="vtab-body" id="vMindmap" style="display:none"></div>' +
    '<div class="vtab-body" id="vTranscript" style="display:none">' +
      renderMarkdown(paragraphizeCN(data.transcript || "（无文字稿）")) +
    '</div>';

  // 容器内查询（不用 getElementById），这样同一个视图可以在多处复用而不冲突
  const $ = (sel) => resultEl.querySelector(sel);
  if (data._noteName) {
    const isTweet = /https?:\/\/(www\.)?(x|twitter)\.com\//i.test(data.url || "");
    try { if (isTweet) _vtXBar(resultEl, data); else _vtTidyBar(resultEl, data); } catch (e) {}   // v88 整理原文 / v94 推文重新整理
    if (!isTweet) { try { _vtSubBar(resultEl, data); } catch (e) {} }                               // v95 字幕 / 翻译
  }

  // ---- 页面内二级标签：展示 + 编辑 ----
  let curTags = Array.isArray(data.tags) ? data.tags.slice() : [];
  function renderTagRow() {
    const row = $("#vTagRow");
    if (!row) return;
    let h = '<span class="vtag-label">🏷 标签：</span>';
    if (curTags.length) {
      h += curTags.map((t) => '<span class="vtag-pill">' + escapeHtml(t) + "</span>").join("");
    } else {
      h += '<span class="vtag-empty">暂无标签</span>';
    }
    if (canEditTags) {
      h += '<button class="vtag-edit" id="vTagEdit">' +
           (curTags.length ? "管理标签" : "+ 添加标签") + "</button>";
    }
    row.innerHTML = h;
    const eb = $("#vTagEdit");
    if (eb) eb.addEventListener("click", () => {
      openInPageTagEditor(data._noteCat, data._noteName, curTags, (saved) => {
        curTags = saved;
        if (data._noteName) { /* 同步给列表缓存（若已加载） */ }
        renderTagRow();
      });
    });
  }
  renderTagRow();

  // 「详细 / 简洁」切换：同一份笔记，简洁版只抽出一句话概括 + 要点标题 + 金句（即时、不重新生成）
  let detailMode = "full";
  const detailToggle = $("#vDetailToggle");
  const renderAnalysis = () => {
    const md = detailMode === "brief"
      ? conciseMarkdown(data.analysis || "")
      : (data.analysis || "（无分析）");
    $("#vAnalysis").innerHTML = renderMarkdown(md);
  };
  detailToggle.querySelectorAll(".vd").forEach((b) => b.addEventListener("click", () => {
    detailMode = b.dataset.d;
    detailToggle.querySelectorAll(".vd").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    renderAnalysis();
  }));

  let _collapsed = false;  // 折叠状态：供下方折叠按钮与标签切换共用
  const tabs = resultEl.querySelectorAll(".vtab");
  tabs.forEach((t) => t.addEventListener("click", () => {
    tabs.forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const which = t.dataset.tab;
    if (_collapsed) return;  // 折叠状态下只切换高亮，不展开正文
    $("#vAnalysis").style.display = which === "analysis" ? "" : "none";
    $("#vMindmap").style.display = which === "mindmap" ? "" : "none";
    $("#vTranscript").style.display = which === "transcript" ? "" : "none";
    detailToggle.style.display = which === "analysis" ? "" : "none";  // 只在 AI 分析时显示开关
    if (which === "mindmap") ensureMindmap();  // 首次切到思维导图时再生成
  }));

  // ——— 思维导图：首次进入时调后端用网页模型生成结构，再用本地渲染器画图 ———
  // 生成结果缓存在 data._mindmapRoot 上，再次切换不重复请求。
  let _mmRendered = false;     // 是否已经把图画进容器（避免重复 mount）
  let _mmLoading = false;      // 防止并发点击重复请求
  function ensureMindmap() {
    const box = $("#vMindmap");
    if (!box) return;
    if (_mmRendered) return;                 // 已经画过
    if (data._mindmapRoot) {                 // 有缓存的结构，直接画
      renderMindmapInto(box, data._mindmapRoot, () => regenMindmap(box));
      _mmRendered = true;
      return;
    }
    if (_mmLoading) return;
    generateMindmap(box);
  }
  function generateMindmap(box) {
    const analysisMd = data.analysis || "";
    if (!analysisMd.trim()) {
      box.innerHTML = '<div class="mm-empty">没有可用于生成思维导图的分析内容。</div>';
      return;
    }
    _mmLoading = true;
    box.innerHTML =
      '<div class="mm-loading"><span class="mm-spin"></span>' +
      '正在用 AI 把这篇笔记整理成思维导图…</div>';
    fetch(BACKEND + "/video_mindmap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analysis: analysisMd,
        title: data.title || "",
        use_local: false,          // 设计：交给网页模型；后端会自行回退
        model: "web",
      }),
    })
      .then((r) => r.json())
      .then((res) => {
        _mmLoading = false;
        if (res && res.ok && res.root) {
          data._mindmapRoot = res.root;     // 缓存，供再次切换/重渲染
          renderMindmapInto(box, res.root, () => regenMindmap(box));
          _mmRendered = true;
        } else {
          const msg = (res && res.error) ? res.error : "生成失败";
          box.innerHTML =
            '<div class="mm-empty">思维导图生成失败：' + escapeHtml(msg) +
            '<br><button class="vbtn mm-retry">重试</button></div>';
          const rb = box.querySelector(".mm-retry");
          if (rb) rb.addEventListener("click", () => generateMindmap(box));
        }
      })
      .catch((e) => {
        _mmLoading = false;
        box.innerHTML =
          '<div class="mm-empty">思维导图请求出错：' + escapeHtml(String(e)) +
          '<br><button class="vbtn mm-retry">重试</button></div>';
        const rb = box.querySelector(".mm-retry");
        if (rb) rb.addEventListener("click", () => generateMindmap(box));
      });
  }
  function regenMindmap(box) {
    // 「重新生成」：清掉缓存，重新向模型要一份
    data._mindmapRoot = null;
    _mmRendered = false;
    generateMindmap(box);
  }

  $("#vCopyBtn").addEventListener("click", () => {
    const active = resultEl.querySelector(".vtab.active").dataset.tab;
    let text;
    if (active === "transcript") text = data.transcript || "";
    else if (active === "mindmap")
      text = data._mindmapRoot ? mindmapToOutline(data._mindmapRoot) : "";
    else text = detailMode === "brief" ? conciseMarkdown(data.analysis || "") : (data.analysis || "");
    copyText(text);
    const b = $("#vCopyBtn");
    b.textContent = "已复制 ✓"; setTimeout(() => (b.textContent = "复制本页"), 1500);
  });
  $("#vExportBtn").addEventListener("click", () => exportVideoMd(data));

  // 折叠 / 展开：把标题以下的正文（标签 + AI分析/原文 + 详细简洁开关）整块收起，
  // 方便往下看「已存的视频笔记」等内容。只折叠正文，标题和工具条保留可见。
  const collapseBtn = $("#vCollapseBtn");
  if (collapseBtn) {
    collapseBtn.addEventListener("click", () => {
      _collapsed = !_collapsed;
      const tagRow = $("#vTagRow");
      const ana = $("#vAnalysis");
      const mm = $("#vMindmap");
      const tr = $("#vTranscript");
      const dt = $("#vDetailToggle");
      // 折叠时全部隐藏；展开时按当前所在标签恢复（分析/导图/原文 三选一）
      if (tagRow) tagRow.style.display = _collapsed ? "none" : "";
      if (dt) dt.style.display = _collapsed ? "none" : "";
      if (_collapsed) {
        if (ana) ana.style.display = "none";
        if (mm) mm.style.display = "none";
        if (tr) tr.style.display = "none";
      } else {
        const activeTab = resultEl.querySelector(".vtab.active");
        const which = activeTab ? activeTab.dataset.tab : "analysis";
        if (ana) ana.style.display = which === "analysis" ? "" : "none";
        if (mm) mm.style.display = which === "mindmap" ? "" : "none";
        if (tr) tr.style.display = which === "transcript" ? "" : "none";
        if (dt) dt.style.display = which === "analysis" ? "" : "none";
        if (which === "mindmap") ensureMindmap();
      }
      collapseBtn.textContent = _collapsed ? "▸ 展开" : "▾ 折叠";
      collapseBtn.title = _collapsed ? "展开正文" : "折叠正文，方便看下面的内容";
    });
  }
  $("#vSpeakBtn").addEventListener("click", () => {
    const active = resultEl.querySelector(".vtab.active").dataset.tab;
    let text;
    if (active === "transcript") text = data.transcript || "";
    else if (active === "mindmap")
      text = data._mindmapRoot ? mindmapToOutline(data._mindmapRoot) : "";
    else text = detailMode === "brief" ? conciseMarkdown(data.analysis || "") : (data.analysis || "");
    if (window.cxSpeak) window.cxSpeak(text, $("#vSpeakBtn"));
  });
}

// 信息简报 / 学习档案的详情：套用和视频笔记一样舒展的排版（标题色块 + 工具条 + 朗读/复制/导出），
// 但只有一个正文面板（没有 AI分析/原文 两个标签）。解决信息库展示"挤"的问题。
function mountSimpleDoc(content, target, opts) {
  opts = opts || {};
  const md = content || "";
  // 抽出首个 # 标题当大标题，其余作为正文
  const lines = md.split("\n");
  let title = opts.title || "";
  let bodyStart = 0;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^#\s+(.+)$/);
    if (m) { if (!title) title = m[1].trim(); bodyStart = i + 1; break; }
    if (lines[i].trim()) break;   // 第一行非空又不是标题，就不剥离
  }
  const body = bodyStart ? lines.slice(bodyStart).join("\n") : md;

  const head = title ? "<h2>" + escapeHtml(title) + "</h2>" : "";
  target.innerHTML =
    '<div class="video-toolbar">' +
      '<span class="vspacer"></span>' +
      '<button class="vbtn vbtn-speak" id="sdSpeakBtn">🔊 朗读</button>' +
      '<button class="vbtn" id="sdCopyBtn">复制本页</button>' +
      '<button class="vbtn" id="sdExportBtn">导出 Markdown</button>' +
    '</div>' +
    head +
    '<div class="vtab-body">' + renderMarkdown(body) + '</div>';

  const $ = (sel) => target.querySelector(sel);
  $("#sdCopyBtn").addEventListener("click", () => {
    copyText(md);
    const b = $("#sdCopyBtn");
    b.textContent = "已复制 ✓"; setTimeout(() => (b.textContent = "复制本页"), 1500);
  });
  $("#sdExportBtn").addEventListener("click", () => {
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = ((title || "笔记").slice(0, 30).replace(/[\\/:*?"<>|]/g, "_")) + ".md";
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  });
  $("#sdSpeakBtn").addEventListener("click", () => {
    if (window.cxSpeak) window.cxSpeak(body, $("#sdSpeakBtn"));
  });
}

// 从详细笔记里抽出"简洁版"：一句话概括 + 核心观点的小标题 + 金句摘录（不重新调用模型）
function conciseMarkdown(md) {
  md = md || "";
  const lines = md.split("\n");
  let sec = "", summary = [], points = [], quotes = [];
  for (const ln of lines) {
    const h2 = ln.match(/^##\s+(.+)$/);
    if (h2) { sec = h2[1].trim(); continue; }
    const h3 = ln.match(/^###\s+(.+)$/);
    if (h3) { if (/核心观点|主要观点|要点/.test(sec)) points.push(h3[1].trim()); continue; }
    if (/一句话概括|概括/.test(sec) && ln.trim()) summary.push(ln.trim());
    if (/金句/.test(sec) && ln.trim() && !/^#/.test(ln)) quotes.push(ln.trim());
  }
  if (!points.length && !summary.length) return md;  // 结构不符就退回完整版，避免空白
  const out = [];
  if (summary.length) out.push("## 一句话概括", "", summary.join(" "), "");
  if (points.length) {
    out.push("## 要点速览", "");
    points.forEach((p) => out.push("**" + p.replace(/^[*\s]+|[*\s]+$/g, "") + "**", ""));
  }
  if (quotes.length) out.push("## 金句摘录", "", ...quotes, "");
  return out.join("\n");
}

function copyText(text) {
  try {
    navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
  }
}

function exportVideoMd(data) {
  const md =
    "# " + (data.title || "视频笔记") + "\n\n" +
    (data.uploader ? "- 作者：" + data.uploader + "\n" : "") +
    (data.url ? "- 链接：" + data.url + "\n" : "") +
    "\n## 🤖 AI 分析\n\n" + (data.analysis || "") +
    "\n\n---\n\n## 📝 完整原文\n\n" + (data.transcript || "") + "\n";
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = ((data.title || "视频笔记").slice(0, 30).replace(/[\\/:*?"<>|]/g, "_")) + ".md";
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

async function loadVideoNotes() {
  const list = document.getElementById("videoNotesList");
  if (!list) return;
  if (!list.children.length) list.innerHTML = "<div class='dash-loading'>加载中…</div>";   // v69：已有内容就先留着，新的到了再换（页面不跳）
  try {
    const resp = await fetch(BACKEND + "/video_notes");
    const data = await resp.json();
    const notes = data.notes || [];
    const folders = data.folders || [];
    if (data.tidy && data.tidy.length) _vnTidyMsgs = _vnTidyMsgs.concat(data.tidy).slice(-6);   // v64
    list.innerHTML = "";
    ["viExtractExtras", "viProcessBars", "viAnLive"].forEach((id) => { const x = document.getElementById(id); if (x) x.innerHTML = ""; });   // v116：搬到提取 / 加工页的几块也一起重画

    // 顶部小工具条：新建文件夹（把同一作者/同一主题的笔记归到一起）
    const bar = document.createElement("div");
    bar.style.cssText = "display:flex;justify-content:flex-end;margin:0 0 8px";
    const nf = document.createElement("button");
    nf.textContent = "＋ 新建文件夹";
    nf.title = "建一个文件夹，把同一作者 / 同一主题的笔记归到一起（笔记右侧的 📂 可移入）";
    nf.style.cssText =
      "border:0.5px solid var(--border,#3a3a3a);background:transparent;" +
      "color:var(--text-dim,#9aa);border-radius:7px;padding:3px 10px;" +
      "font-size:12px;cursor:pointer";
    nf.addEventListener("click", async () => {
      const v = await askText({
        title: "新建文件夹",
        desc: "给新文件夹起个名字（比如作者名 / 主题）。建好后点笔记右侧的 📂 就能把笔记移进来。",
        placeholder: "文件夹名",
        okText: "创建",
      });
      if (v === null) return;
      const name = v.trim();
      if (!name) return;
      const d = await vnFolderOp({ op: "create", name });
      if (d && d.ok) { vnSetFolderOpen(name, true); loadVideoNotes(); }
    });
    bar.appendChild(nf);
    bar.insertBefore(vnViewToggle(), nf);   // v57：列表 / 图标 切换
    list.appendChild(bar);
    vnRenderTidyTip(list);                  // v64：自动合并了同名博主时提示一下

    if (notes.length === 0 && folders.length === 0) {
      const em = document.createElement("div");
      em.className = "dash-empty";
      em.textContent = "还没有视频笔记。在上面粘个链接试试。";
      list.appendChild(em);
      return;
    }

    // 按文件夹分组：mapping 指向的文件夹必须真实存在，否则算未分组
    const byFolder = {};
    const ungrouped = [];
    notes.forEach((n) => {
      if (n.folder && folders.indexOf(n.folder) >= 0) {
        (byFolder[n.folder] = byFolder[n.folder] || []).push(n);
      } else {
        ungrouped.push(n);
      }
    });

    // v57：图标视图（像电脑文件夹那样一格一格显示）
    if (vnViewMode() === "icon") {
      await vnLoadProfiles();
      try { vnRenderRecent(list, notes, folders); } catch (e) { console.error(e); }   // v116：「历史」在提取页，进了文件夹也要画
      vnRenderFailBar(list);           // v90：提取失败清单（没有就不显示）
      vnRenderBatchBar(list, notes);   // v59：和列表视图一样放在「最新提取」下面
      vnRenderIconView(list, notes, folders, byFolder, ungrouped);
      return;
    }

    // v56：置顶的「最新提取」（按提取时间筛选、分页）
    try { vnRenderRecent(list, notes, folders); } catch (e) { console.error(e); }

    // 先渲染各文件夹（可折叠，默认收起，记住展开状态），再渲染未分组的散笔记
    vnRenderFailBar(list);           // v90：提取失败清单（没有就不显示）
    vnRenderBatchBar(list, notes);

    folders.forEach((f) => {
      const items = byFolder[f] || [];
      const open = vnFolderIsOpen(f);

      const box = document.createElement("div");
      box.style.cssText = "margin:2px 0 6px 16px" + (open ? "" : ";display:none");

      const head = document.createElement("div");
      head.className = "video-note-item";
      head.style.cssText = "cursor:pointer;background:rgba(120,120,130,.07);font-weight:600";
      const caret = document.createElement("span");
      caret.textContent = open ? "▾" : "▸";
      caret.style.cssText = "flex:0 0 auto;color:var(--text-dim,#9aa)";
      const fn = document.createElement("span");
      fn.className = "vn-name";
      fn.textContent = "📂 " + f;
      fn.title = "点击展开 / 收起";
      const cnt = document.createElement("span");
      cnt.style.cssText = "flex:0 0 auto;color:var(--text-dim,#9aa);font-weight:400;font-size:12px";
      cnt.textContent = "（" + items.length + " 条）";
      const im = document.createElement("button");
      im.className = "vn-del"; im.textContent = "📥";
      im.title = "导入到这个文件夹：选文件或选整个文件夹，提取出的笔记自动归进「" + f + "」";
      im.addEventListener("click", (e) => {
        e.stopPropagation();
        showVnImportMenu(im, f);
      });
      const rn = document.createElement("button");
      rn.className = "vn-del"; rn.textContent = "✎"; rn.title = "重命名文件夹";
      rn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const v = await askText({
          title: "重命名文件夹",
          value: f,
          placeholder: "新名字",
          okText: "改名",
        });
        if (v === null) return;
        const nn = v.trim();
        if (!nn || nn === f) return;
        const d = await vnFolderOp({ op: "rename", name: f, new_name: nn });
        if (d && d.ok) { vnRenameOpenState(f, nn); loadVideoNotes(); }
      });
      const fd = document.createElement("button");
      fd.className = "vn-del"; fd.textContent = "🗑";
      fd.title = "删除文件夹（里面的笔记不会被删，只是回到外面的列表）";
      fd.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("删除文件夹「" + f + "」？\n里面的 " + items.length +
                     " 条笔记不会被删，只是回到外面的列表。")) return;
        await vnFolderOp({ op: "delete", name: f });
        loadVideoNotes();
      });
      head.appendChild(caret); head.appendChild(fn); head.appendChild(cnt);
      vnAddGroupBatchBtn(head, items);
      head.appendChild(im); head.appendChild(rn); head.appendChild(fd);
      head.addEventListener("click", () => {
        const nowOpen = box.style.display === "none";
        box.style.display = nowOpen ? "" : "none";
        caret.textContent = nowOpen ? "▾" : "▸";
        vnSetFolderOpen(f, nowOpen);
      });

      vnAppendItems(box, items, folders);
      if (!items.length) {
        const em = document.createElement("div");
        em.className = "dash-empty";
        em.style.cssText = "padding:6px 10px;font-size:12px";
        em.textContent = "（空文件夹：点上方的 📥 可以直接导入视频到这里，"
          + "或点笔记右侧的 📂 把已有笔记移进来）";
        box.appendChild(em);
      }
      list.appendChild(head);
      list.appendChild(box);
    });

    vnRenderUngrouped(list, ungrouped, folders);
  } catch (e) {
    list.innerHTML = "<div class='dash-empty'>加载失败：" + escapeHtml(e.message) + "</div>";
  }
}

// ───────── 长列表整理：分页 / 按作者自动分组 / 批量 AI 分析（2026-11）─────────
const VN_PAGE = 30;

// 往容器里放笔记：先放 30 条，剩下的点「再显示」才渲染（几百条一次性铺开又慢又乱）
function vnAppendItems(box, items, folders) {
  let shown = 0;
  const more = document.createElement("button");
  more.className = "vn-more";
  const step = () => {
    items.slice(shown, shown + VN_PAGE).forEach((n) => box.insertBefore(makeVideoNoteItem(n, folders), more));
    shown = Math.min(items.length, shown + VN_PAGE);
    const left = items.length - shown;
    more.hidden = left <= 0;
    more.textContent = "再显示 " + Math.min(VN_PAGE, left) + " 条（还剩 " + left + " 条）";
  };
  more.addEventListener("click", (e) => { e.stopPropagation(); step(); });
  box.appendChild(more);
  step();
}

function vnUnanalyzed(items) { return (items || []).filter((n) => n.analyzed === false); }

// 分组标题上的「分析本组 N 条」
function vnAddGroupBatchBtn(head, items) {
  const todo = vnUnanalyzed(items);
  if (!todo.length) return;
  const b = document.createElement("button");
  b.className = "vn-group-batch";
  b.textContent = "分析本组 " + todo.length + " 条";
  b.title = "把这一组里还没做 AI 分析的笔记排队，一条一条分析（每条换一张新的 AI 卡）";
  b.addEventListener("click", (e) => { e.stopPropagation(); vnStartBatch(todo); });
  head.appendChild(b);
}

// 文件夹外的笔记：不多就平铺；多了就按作者自动分组，组可折叠（默认收起，记住展开状态）
function vnRenderUngrouped(list, ungrouped, folders) {
  if (ungrouped.length <= 12) { vnAppendItems(list, ungrouped, folders); return; }
  const groups = {};
  ungrouped.forEach((n) => { const k = (n.author || "").trim() || "未填作者"; (groups[k] = groups[k] || []).push(n); });
  const keys = Object.keys(groups).sort((a, b) =>
    (a === "未填作者") - (b === "未填作者") || groups[b].length - groups[a].length);
  const tip = document.createElement("div");
  tip.className = "vn-auto-tip";
  tip.textContent = "下面是还没放进文件夹的笔记，按作者自动分组（点组名展开 / 收起）";
  list.appendChild(tip);
  let openState = {};
  try { openState = JSON.parse(localStorage.getItem("vnAuthorOpen") || "{}"); } catch (e) {}
  keys.forEach((k) => {
    const items = groups[k];
    const head = document.createElement("div");
    head.className = "video-note-item vn-group-head";
    const caret = document.createElement("span"); caret.className = "vn-caret";
    const nm = document.createElement("span"); nm.className = "vn-name"; nm.textContent = k;
    const cnt = document.createElement("span"); cnt.className = "vn-count"; cnt.textContent = "（" + items.length + " 条）";
    head.appendChild(caret); head.appendChild(nm); head.appendChild(cnt);
    vnAddGroupBatchBtn(head, items);
    const box = document.createElement("div"); box.className = "vn-group-box";
    let filled = false;
    const apply = (open) => {
      box.style.display = open ? "" : "none"; caret.textContent = open ? "▾" : "▸";
      if (open && !filled) { vnAppendItems(box, items, folders); filled = true; }
    };
    apply(!!openState[k]);
    head.addEventListener("click", () => {
      const open = box.style.display === "none";
      apply(open);
      openState[k] = open;
      try { localStorage.setItem("vnAuthorOpen", JSON.stringify(openState)); } catch (e) {}
    });
    list.appendChild(head); list.appendChild(box);
  });
}

// 顶部的批量分析条
// v59：批量 AI 分析做成可折叠的一组（像「最新提取」）。折叠时标题行照样显示进度、正在分析哪篇、在做哪一步。
function vnBatchIsOpen() {
  try { return localStorage.getItem("vnBatchOpen") === "1"; } catch (_) { return false; }
}

function vnRenderBatchBar(list, notes) {
  const todo = vnUnanalyzed(notes);
  const bar = document.createElement("div");
  bar.className = "vn-batch-bar vn-batch-group"; bar.id = "vnBatchBar";
  bar.dataset.todo = String(todo.length);
  const head = document.createElement("div");
  head.className = "video-note-item vn-group-head vn-batch-head";
  head.title = "点击展开 / 收起（收起时这一行也会显示进度）";
  const caret = document.createElement("span"); caret.className = "vn-caret";
  const nm = document.createElement("span"); nm.className = "vn-name"; nm.textContent = "批量 AI 分析";
  const mini = document.createElement("span"); mini.className = "vn-batch-mini"; mini.id = "vnBatchMini"; mini.hidden = true;
  mini.appendChild(document.createElement("i"));
  const sum = document.createElement("span"); sum.className = "vn-batch-sum"; sum.id = "vnBatchSum";
  sum.textContent = todo.length ? todo.length + " 条笔记还没做 AI 分析" : "所有笔记都已做过 AI 分析";
  const acts = document.createElement("span"); acts.className = "vn-batch-hacts"; acts.id = "vnBatchHActs";
  if (todo.length) {
    const b = document.createElement("button");
    b.className = "send-btn vn-batch-btn"; b.textContent = "批量 AI 分析";
    b.title = "按列表顺序一条一条分析；每条都会在 AI 池换一张新的 AI 卡、开新对话";
    b.addEventListener("click", (e) => { e.stopPropagation(); vnStartBatch(todo); });
    acts.appendChild(b);
  }
  head.appendChild(caret); head.appendChild(nm); head.appendChild(mini); head.appendChild(sum); head.appendChild(acts);
  const body = document.createElement("div"); body.className = "vn-batch-body"; body.id = "vnBatchBody";
  const idle = document.createElement("div"); idle.className = "vn-batch-idle"; idle.id = "vnBatchIdle";
  idle.textContent = todo.length
    ? "点上面的「批量 AI 分析」开始。分析时这里会显示进度、AI 的实时画面和它正在写的回复。"
    : "现在没有要分析的笔记。以后有「只提取了文字稿」的笔记，可以在这里一键批量分析。";
  const prog = document.createElement("div"); prog.className = "vn-batch-prog"; prog.id = "vnBatchProg"; prog.hidden = true;
  body.appendChild(idle); body.appendChild(prog);
  body.appendChild(vnBuildLive());   // v55：可展开的「AI 实时画面」
  body.appendChild(vnBuildUnList(todo));   // v68：还没分析的笔记清单
  bar.appendChild(head); bar.appendChild(body);
  const apply = (open) => { body.hidden = !open; caret.textContent = open ? "▾" : "▸"; bar.classList.toggle("open", open); };
  apply(vnBatchIsOpen());
  head.addEventListener("click", () => {
    const open = body.hidden;
    apply(open);
    try { localStorage.setItem("vnBatchOpen", open ? "1" : "0"); } catch (_) {}
    vnLivePoll();                   // v64：实时画面不再单独折叠——点开「批量 AI 分析」就直接看得到
  });
  list.appendChild(bar);
  vnPollBatch();          // 页面刷新时如果有批量在跑，接着显示进度
  vnLivePoll();
}

// ════════════════ v68：「批量 AI 分析」里的「还没分析的笔记」清单 ════════════════
// 显示还有多少条没分析、是哪几条（按批量分析的顺序），点一条就打开它；
// 批量在跑时，正在分析的那条、上次没成功的会标出来。分析完的会自己从清单里消失。
const VN_UN_PAGE = 20;
let _vnUnShown = VN_UN_PAGE;

function vnUnIsOpen() {
  try { return localStorage.getItem("vnUnOpen") !== "0"; } catch (_) { return true; }
}

let _vnUnTodo = [], _vnUnRender = null, _vnUnTitle = null;
function vnBuildUnList(todo) {
  todo = (todo || []).slice();
  _vnUnTodo = todo;
  const box = document.createElement("div");
  box.className = "vn-un"; box.id = "vnUnList";
  const head = document.createElement("div");
  head.className = "vn-un-head";
  head.title = "点击展开 / 收起";
  const caret = document.createElement("span"); caret.className = "vn-caret";
  const ttl = document.createElement("span"); ttl.className = "vn-un-title";
  ttl.textContent = todo.length ? "还没分析的笔记（" + todo.length + " 条）" : "所有笔记都分析过了";
  _vnUnTitle = ttl;
  const tip = document.createElement("span"); tip.className = "vn-un-tip";
  tip.textContent = todo.length ? "按批量分析的顺序排列，点一条就能打开看原文" : "";
  head.appendChild(caret); head.appendChild(ttl); head.appendChild(tip);
  box.appendChild(head);
  const rows = document.createElement("div"); rows.className = "vn-un-rows";
  box.appendChild(rows);
  if (!todo.length) { caret.textContent = ""; return box; }
  const render = () => {
    todo = _vnUnTodo;
    rows.innerHTML = "";
    todo.slice(0, _vnUnShown).forEach((n, i) => rows.appendChild(vnUnRow(n, i + 1)));
    const left = todo.length - Math.min(_vnUnShown, todo.length);
    if (left > 0) {
      const more = document.createElement("button");
      more.type = "button"; more.className = "vn-more";
      more.textContent = "再显示 " + Math.min(VN_UN_PAGE, left) + " 条（还剩 " + left + " 条）";
      more.addEventListener("click", (e) => { e.stopPropagation(); _vnUnShown += VN_UN_PAGE; render(); vnUnMark(_vnUnLast || {}); });
      rows.appendChild(more);
    }
  };
  const apply = (open) => { rows.hidden = !open; caret.textContent = open ? "▾" : "▸"; };
  _vnUnRender = render;
  render();
  apply(vnUnIsOpen());
  head.addEventListener("click", () => {
    const open = rows.hidden;
    apply(open);
    try { localStorage.setItem("vnUnOpen", open ? "1" : "0"); } catch (_) {}
  });
  return box;
}

function vnUnRow(n, idx) {
  const r = document.createElement("div");
  r.className = "vn-un-row"; r.dataset.name = n.name || "";
  r.title = "点击打开这条笔记，看原文";
  const no = document.createElement("span"); no.className = "vn-un-no"; no.textContent = idx + ".";
  r.appendChild(no);
  const when = vnNoteTime(n);
  const tm = document.createElement("span"); tm.className = "vn-un-time";
  tm.textContent = when ? vnFmtWhen(when) : "";
  r.appendChild(tm);
  if (n.kind) r.appendChild(vnKindBadge(n.kind));
  const nm = document.createElement("span"); nm.className = "vn-un-name";
  nm.textContent = n.title || (n.name || "").replace(/\.md$/, "");
  r.appendChild(nm);
  if (n.author) {
    const au = document.createElement("span"); au.className = "vn-un-author";
    au.appendChild(vnAvatarEl({ key: n.author, name: n.author, kind: "author" }, "mini"));   // v81
    au.appendChild(document.createTextNode(n.author));
    r.appendChild(au);
  }
  const st = document.createElement("span"); st.className = "vn-un-state";
  r.appendChild(st);
  const an = vnAnButton(n.name, "🤖 AI 分析", "vn-analyze vn-un-an", false);
  an.title = "只分析这一条（批量在跑的时候不能单独点）";
  r.appendChild(an);
  r.appendChild(vnDelNoteBtn(n, () => { r.remove(); vnUnDrop([n.name]); }));   // v90：测试用的、重复的可以删掉
  r.addEventListener("click", () => openVideoNote(n.name));
  return r;
}

// v69：分析完的笔记马上从清单里拿掉，标题上的条数跟着少一个（不用整页刷新）
function vnUnDrop(names) {
  if (!names || !names.length || !_vnUnTodo.length) return;
  const gone = new Set(names);
  const left = _vnUnTodo.filter((n) => !gone.has(n.name));
  if (left.length === _vnUnTodo.length) return;
  _vnUnTodo = left;
  if (_vnUnTitle && document.body.contains(_vnUnTitle)) {
    _vnUnTitle.textContent = left.length ? "还没分析的笔记（" + left.length + " 条）" : "所有笔记都分析过了";
  }
  const bar = document.getElementById("vnBatchBar");
  if (bar) bar.dataset.todo = String(left.length);
  if (_vnUnRender) { _vnUnRender(); }
}

let _vnUnLast = null;
function vnUnMark(d) {
  _vnUnLast = d;
  if (d && d.ok_names && d.ok_names.length) vnUnDrop(d.ok_names);
  const box = document.getElementById("vnUnList");
  if (!box) return;
  const errs = {};
  (d.errors || []).forEach((x) => { if (x && x.name) errs[x.name] = x.error || x.msg || x.reason || "没成功"; });
  box.querySelectorAll(".vn-un-row").forEach((r) => {
    const st = r.querySelector(".vn-un-state");
    const name = r.dataset.name;
    let cls = "", txt = "", tip = "";
    if (d.running && name === d.current) { cls = "cur"; txt = "⏳ 正在分析"; }
    else if (errs[name]) { cls = "err"; txt = "⚠ 上次没成功"; tip = errs[name]; }
    r.classList.toggle("cur", cls === "cur");
    r.classList.toggle("err", cls === "err");
    if (st) { st.textContent = txt; st.title = tip; }
  });
}

// 标题行：折叠时也看得到——进度条、第几篇、哪一篇、在做哪一步、这篇用了多久；还有「停止」「现在就继续」
let _vnBatchStopping = false;
function vnBatchHead(d) {
  const sum = document.getElementById("vnBatchSum");
  if (!sum) return;
  const bar = document.getElementById("vnBatchBar");
  const todo = bar ? +(bar.dataset.todo || 0) : 0;
  let txt;
  if (d.running) {
    const idx = Math.min(d.total || 0, (d.done || 0) + 1);
    const t = (d.cur_title || (d.current || "").replace(/\.md$/, "").replace(/^\d{8}-\d{6}-?/, "")).trim();
    if (d.waiting) {
      txt = "⏸ 暂停中 " + d.done + " / " + d.total + " · " + d.waiting +
        (d.resume_in ? "，" + _vnFmtDur(d.resume_in) + "后自动接着跑" : "");
    } else {
      txt = "分析中 " + d.done + " / " + d.total + (t ? " · 第 " + idx + " 篇《" + t + "》" : "") +
        (d.stage ? " · " + d.stage : "") +
        (d.cur_started && d.now ? " · 已用 " + _vnFmtDur(d.now - d.cur_started) : "") +
        (d.round > 1 ? " · 第 " + d.round + " 遍补漏" : "");
    }
  } else if (d.finished) {
    txt = "已结束 " + d.done + " / " + d.total + "（成功 " + d.ok + "，失败 " + d.fail + "）" +
      (todo ? " · 还有 " + todo + " 条没分析" : "");
  } else {
    txt = todo ? todo + " 条笔记还没做 AI 分析" : "所有笔记都已做过 AI 分析";
  }
  sum.textContent = txt; sum.title = txt;
  sum.classList.toggle("run", !!d.running);
  const mini = document.getElementById("vnBatchMini");
  if (mini) {
    const show = !!((d.running || d.finished) && d.total);
    mini.hidden = !show;
    if (show) mini.firstChild.style.width = Math.round((d.done || 0) * 100 / d.total) + "%";
  }
  const acts = document.getElementById("vnBatchHActs");
  if (!acts) return;
  let stop = acts.querySelector(".vn-bh-stop"), go = acts.querySelector(".vn-bh-go");
  if (!d.running) {
    _vnBatchStopping = false;
    if (stop) stop.remove();
    if (go) go.remove();
    return;
  }
  if (!stop) {
    stop = document.createElement("button");
    stop.type = "button"; stop.className = "vn-batch-stop vn-bh-stop"; stop.title = "分析完当前这一条后停止";
    stop.addEventListener("click", async (e) => {
      e.stopPropagation();
      _vnBatchStopping = true; stop.disabled = true; stop.textContent = "停止中…";
      try {
        await fetch(BACKEND + "/video_note_analyze_batch", { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stop: true }) });
      } catch (_) {}
    });
    acts.appendChild(stop);
  }
  stop.disabled = _vnBatchStopping; stop.textContent = _vnBatchStopping ? "停止中…" : "停止";
  if (d.waiting && !go) {
    go = document.createElement("button");
    go.type = "button"; go.className = "vn-batch-stop vn-bh-go"; go.textContent = "现在就继续";
    go.title = "不等了，马上接着分析";
    go.addEventListener("click", async (e) => {
      e.stopPropagation(); go.disabled = true;
      try {
        await fetch(BACKEND + "/video_note_analyze_batch", { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_now: true }) });
      } catch (_) {}
      setTimeout(vnPollBatch, 800);
    });
    acts.insertBefore(go, stop);
  } else if (!d.waiting && go) {
    go.remove();
  }
}

let _vnBatchTimer = null;
async function vnStartBatch(items) {
  if (!items || !items.length) return;
  if (!confirm("批量分析 " + items.length + " 条笔记？\n\n" +
               "· 一条接一条分析，每条都会在 AI 池换一张新的 AI 卡、开新对话，互不串内容；\n" +
               "· 用最高级模型，单条可能要几分钟，整批会比较久，可以随时点「停止」；\n" +
               "· 分析期间可以正常用软件的其他功能；\n" +
               "· 挂机也没关系：AI 池出问题会自动等一会儿再接着跑，每条最多试 4 次，最后再把没成功的补一遍。")) return;
  const s = (typeof settings === "function") ? settings() : {};
  try {
    const d = await (await fetch(BACKEND + "/video_note_analyze_batch", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ names: items.map((n) => n.name), use_local: s.use_local, model: s.model }),
    })).json();
    if (!d.ok) { alert(d.error || "没能开始"); return; }
    vnPollBatch();
  } catch (e) { alert("提交出错：" + e.message); }
}

async function vnPollBatch() {
  let d;
  try { d = await (await fetch(BACKEND + "/video_note_analyze_batch")).json(); } catch (e) { return; }
  const prog = document.getElementById("vnBatchProg");
  if (!prog) return;
  // 正在批量分析时，隐藏「批量 AI 分析」和各组的「分析本组」按钮，避免重复提交
  document.querySelectorAll(".vn-batch-btn, .vn-group-batch, .vn-un-an").forEach((b) => { b.hidden = !!d.running; });
  vnBatchHead(d);                 // v59：标题行（折叠时也能看到进度和当前在做什么）
  vnUnMark(d);                    // v68：清单里标出「正在分析」「上次没成功」
  const idle = document.getElementById("vnBatchIdle");
  if (idle) idle.hidden = !!(d.running || d.finished);
  if (!d.running && !d.finished) { prog.hidden = true; return; }
  prog.hidden = false;
  const pct = d.total ? Math.round(d.done * 100 / d.total) : 0;
  prog.innerHTML =
    '<div class="vn-batch-line">' +
      (d.running ? (d.waiting ? "批量分析等待中 " : "批量分析中 ") : "批量分析结束 ") + d.done + " / " + d.total +
      "（成功 " + d.ok + "，失败 " + d.fail + "）" +
      (d.running && d.round > 1 ? '<span class="vn-batch-cur">第 ' + d.round + " 遍：补之前没成功的</span>" : "") +

    "</div>" +
    '<div class="vn-batch-track"><div class="vn-batch-fill" style="width:' + pct + '%"></div></div>' +
    (d.running && d.waiting ? '<div class="vn-batch-errs vn-batch-wait">⏸ ' + escapeHtml(d.waiting) +
      (d.resume_in ? "（还有 " + Math.floor(d.resume_in / 60) + " 分 " + (d.resume_in % 60) + " 秒）" : "") +
      "。不用管它，到时间会先测一下 AI 池能不能连上，再自动接着跑。</div>" : "") +
    (d.paused && !d.running ? '<div class="vn-batch-errs">⏸ ' + escapeHtml(d.paused) +
      "。处理好后再点一次「批量 AI 分析」，会接着补没分析的。</div>" : "") +
    (d.errors && d.errors.length && !d.running
      ? '<div class="vn-batch-errs">没成功的：' + d.errors.map((x) => escapeHtml(x.name.replace(/\.md$/, ""))).join("、") +
        "（可以稍后再点一次批量分析，只会补没成功的）</div>" : "");
  if (d.running) {
    // 「停止」「现在就继续」挪到了标题行（折叠时也能点），见 vnBatchHead
    if (!_vnBatchTimer) _vnBatchTimer = setInterval(vnPollBatch, 2500);
    if (d.done !== vnPollBatch._lastDone) { vnPollBatch._lastDone = d.done; if (d.done) _vnRefreshSoon(); }
  } else if (_vnBatchTimer) {
    clearInterval(_vnBatchTimer); _vnBatchTimer = null;
    loadVideoNotes();
  }
}
// 每分析完一条，稍后刷新列表（那条的「AI 分析」按钮会消失）；不在刷新时打断阅读
let _vnRefreshT = null;
function _vnRefreshSoon() { clearTimeout(_vnRefreshT); _vnRefreshT = setTimeout(() => loadVideoNotes(), 1500); }

// 生成一条视频笔记行（标题 + 作者 + 未分析补做 + 移动到文件夹 + 改作者 + 删除）
function makeVideoNoteItem(n, folders) {
  const item = document.createElement("div");
  item.className = "video-note-item";
  item.dataset.name = n.name || "";
  const name = document.createElement("span");
  name.className = "vn-name";
  name.textContent = n.title || n.name;
  name.title = n.title || n.name;   // 鼠标悬停看完整标题
  name.addEventListener("click", () => openVideoNote(n.name));
  if (n.kind) item.appendChild(vnKindBadge(n.kind));     // v65：PDF / Word / 文章…
  item.appendChild(name);
  if (n.kind && /GitHub/.test(n.kind)) item.appendChild(vnGhInstallBtn(n));   // v112
  // 作者名（蓝色醒目，和标题平级、永不被截断；有真实昵称才显示，纯数字 ID/空 后端已过滤）
  if (n.author) {
    const au = document.createElement("span");
    au.className = "vn-author";
    au.appendChild(vnAvatarEl({ key: n.author, name: n.author, kind: "author" }, "mini"));   // v81：博主 mini 头像
    const aun = document.createElement("span");
    aun.className = "vn-au-name"; aun.textContent = n.author;
    au.appendChild(aun);
    au.title = "作者：" + n.author + "（点右侧 ✎ 可修改）";
    au.addEventListener("click", () => openVideoNote(n.name));
    item.appendChild(au);
  } else {
    // 没存到作者（本地导入的常见）：占位改成可点击的「＋ 填写作者」
    const au = document.createElement("span");
    au.className = "vn-author vn-author-none";
    au.textContent = "＋ 填写作者";
    au.title = "这条笔记没有作者（本地导入的常见），点这里填一个";
    au.style.cursor = "pointer";
    au.addEventListener("click", (e) => { e.stopPropagation(); editNoteAuthor(n); });
    item.appendChild(au);
  }
  // 「仅提取」模式存的未分析笔记：右侧给一个「AI 分析」补做按钮
  if (n.analyzed === false) {
    const an = vnAnButton(n.name, "🤖 AI 分析", "vn-analyze", false);
    an.title = "这条只提取了原文，点这里让 AI 写分析笔记（分析中再点一下可以停止）";
    an.style.cssText =
      "flex:0 0 auto;border:0.5px solid var(--accent,#1a73e8);" +
      "background:transparent;color:var(--accent,#1a73e8);border-radius:7px;" +
      "padding:2px 9px;font-size:12px;cursor:pointer;white-space:nowrap";
    item.appendChild(an);
  }
  // 移动到文件夹
  const mv = document.createElement("button");
  mv.className = "vn-del"; mv.textContent = "📂"; mv.title = "移动到文件夹";
  mv.addEventListener("click", (e) => {
    e.stopPropagation();
    showVnFolderMenu(mv, n, folders);
  });
  item.appendChild(mv);
  // 填写 / 修改作者
  const ed = document.createElement("button");
  ed.className = "vn-del"; ed.textContent = "✎"; ed.title = "填写 / 修改作者";
  ed.addEventListener("click", (e) => { e.stopPropagation(); editNoteAuthor(n); });
  item.appendChild(ed);
  // 删除
  const del = document.createElement("button");
  del.className = "vn-del"; del.textContent = "🗑"; del.title = "删除这条笔记";
  del.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!confirm("删除这条视频笔记？")) return;
    try {
      await fetch(BACKEND + "/video_note_delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: n.name }),
      });
      loadVideoNotes();
    } catch (_) {}
  });
  item.appendChild(del);
  return item;
}

// 填写 / 修改一条笔记的作者（本地导入的笔记通常没有作者）
async function editNoteAuthor(n) {
  const v = await askText({
    title: "填写 / 修改作者",
    desc: (n.title || n.name || "").slice(0, 40),
    value: n.author || "",
    placeholder: "作者名（留空可清除）",
    okText: "保存",
  });
  if (v === null) return;
  const author = v.trim().slice(0, 40);
  try {
    const r = await fetch(BACKEND + "/video_note_set_author", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: n.name, author }),
    });
    const d = await r.json();
    if (!d.ok) { setVideoStatus("作者没改成：" + (d.error || "未知原因"), "warn"); return; }
    loadVideoNotes();
  } catch (e) {
    setVideoStatus("改作者出错：" + e.message, "warn");
  }
}

// ── 笔记文件夹：操作请求 + 展开状态记忆 + 「移动到…」小菜单 ──
async function vnFolderOp(payload) {
  try {
    const r = await fetch(BACKEND + "/video_folder", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const d = await r.json();
    if (!d.ok) setVideoStatus("文件夹操作没成功：" + (d.error || "未知原因"), "warn");
    return d;
  } catch (e) {
    setVideoStatus("文件夹操作出错：" + e.message, "warn");
    return { ok: false };
  }
}

function vnFolderIsOpen(f) {
  try {
    const s = JSON.parse(localStorage.getItem("vnFolderOpen") || "{}");
    return !!s[f];
  } catch (_) { return false; }
}
function vnSetFolderOpen(f, open) {
  try {
    const s = JSON.parse(localStorage.getItem("vnFolderOpen") || "{}");
    if (open) s[f] = 1; else delete s[f];
    localStorage.setItem("vnFolderOpen", JSON.stringify(s));
  } catch (_) {}
}
function vnRenameOpenState(oldName, newName) {
  try {
    const s = JSON.parse(localStorage.getItem("vnFolderOpen") || "{}");
    if (s[oldName]) { s[newName] = 1; delete s[oldName];
      localStorage.setItem("vnFolderOpen", JSON.stringify(s)); }
  } catch (_) {}
}

function closeVnFolderMenu() {
  const m = document.getElementById("vnFolderMenu");
  if (m) m.remove();
}

// 点文件夹标题行的 📥：弹小菜单选择「导入文件」还是「导入整个文件夹」，
// 提取出的笔记都会自动归进这个笔记文件夹。
function showVnImportMenu(anchor, folderName) {
  closeVnFolderMenu();
  const m = document.createElement("div");
  m.id = "vnFolderMenu";
  m.style.cssText =
    "position:fixed;z-index:9999;background:var(--surface-2,#fff);" +
    "border:0.5px solid var(--border,#3a3a3a);border-radius:9px;" +
    "box-shadow:0 6px 24px rgba(0,0,0,.18);padding:6px;min-width:220px;" +
    "max-height:280px;overflow:auto";
  const mk = (label, fn) => {
    const b = document.createElement("div");
    b.textContent = label;
    b.style.cssText = "padding:6px 10px;border-radius:6px;cursor:pointer;font-size:13px";
    b.addEventListener("mouseenter", () => { b.style.background = "rgba(26,115,232,.10)"; });
    b.addEventListener("mouseleave", () => { b.style.background = ""; });
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      closeVnFolderMenu();
      await fn();
    });
    m.appendChild(b);
  };
  mk("📁 导入本地文件 → 归入「" + folderName + "」",
     () => pickAndImportLocal(folderName));
  mk("📂 导入整个文件夹 → 归入「" + folderName + "」",
     () => pickAndImportFolder(folderName));
  document.body.appendChild(m);
  const r = anchor.getBoundingClientRect();
  m.style.left = Math.max(8, Math.min(window.innerWidth - 250, r.left - 160)) + "px";
  m.style.top = Math.max(8, Math.min(window.innerHeight - m.offsetHeight - 8, r.bottom + 4)) + "px";
  setTimeout(() => {
    document.addEventListener("click", closeVnFolderMenu, { once: true });
  }, 0);
}
// 点笔记行的 📂：弹一个小菜单选择目标文件夹（或移出 / 新建）
function showVnFolderMenu(anchor, note, folders) {
  closeVnFolderMenu();
  const m = document.createElement("div");
  m.id = "vnFolderMenu";
  m.style.cssText =
    "position:fixed;z-index:9999;background:var(--surface-2,#fff);" +
    "border:0.5px solid var(--border,#3a3a3a);border-radius:9px;" +
    "box-shadow:0 6px 24px rgba(0,0,0,.18);padding:6px;min-width:170px;" +
    "max-height:280px;overflow:auto";
  const mk = (label, fn, dim) => {
    const b = document.createElement("div");
    b.textContent = label;
    b.style.cssText = "padding:6px 10px;border-radius:6px;cursor:pointer;font-size:13px;" +
      (dim ? "color:var(--text-dim,#9aa);" : "");
    b.addEventListener("mouseenter", () => { b.style.background = "rgba(26,115,232,.10)"; });
    b.addEventListener("mouseleave", () => { b.style.background = ""; });
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      closeVnFolderMenu();
      await fn();
    });
    m.appendChild(b);
  };
  (folders || []).forEach((f) => {
    if (f === note.folder) return;
    mk("📂 " + f, async () => {
      const d = await vnFolderOp({ op: "move", note: note.name, name: f });
      if (d && d.ok) loadVideoNotes();
    });
  });
  if (note.folder) {
    mk("↩ 移出文件夹", async () => {
      const d = await vnFolderOp({ op: "move", note: note.name, name: "" });
      if (d && d.ok) loadVideoNotes();
    });
  }
  mk("＋ 新建文件夹并移入…", async () => {
    const v = await askText({
      title: "新建文件夹并移入",
      desc: "这条笔记会移进新建的文件夹里。",
      placeholder: "新文件夹的名字",
      okText: "创建并移入",
    });
    if (v === null) return;
    const name = v.trim();
    if (!name) return;
    const d = await vnFolderOp({ op: "move", note: note.name, name });
    if (d && d.ok) { vnSetFolderOpen(name, true); loadVideoNotes(); }
  }, true);
  document.body.appendChild(m);
  const r = anchor.getBoundingClientRect();
  m.style.left = Math.max(8, Math.min(window.innerWidth - 200, r.left - 130)) + "px";
  m.style.top = Math.max(8, Math.min(window.innerHeight - m.offsetHeight - 8, r.bottom + 4)) + "px";
  // 点菜单外任意处关闭
  setTimeout(() => {
    document.addEventListener("click", closeVnFolderMenu, { once: true });
  }, 0);
}

async function openVideoNote(name) {
  // v91：笔记在单独的「阅读页」里打开（左上角「← 返回」回到列表原来的位置），不再塞进「处理进度」
  const resultEl = vnReaderShow(name);
  resultEl.innerHTML = "<div class='dash-loading'>读取中…</div>";
  try {
    const resp = await fetch(BACKEND + "/video_note?name=" + encodeURIComponent(name));
    const data = await resp.json();
    if (!data.ok) { resultEl.innerHTML = "<div class='dash-empty'>" +
      escapeHtml(data.error || "读取失败") + "</div>"; return; }
    const parsed = parseVideoNote(data.content || "");
    parsed._noteName = name;     // 视频板块的笔记，归类为 video，可在页面内加标签
    parsed._noteCat = "video";
    if (_vnReaderName !== name) return;          // 读取时已经换了别的笔记 / 已经返回了
    mountVideoResult(parsed, resultEl);
    _currentVideo = parsed;                      // 朗读、复制、导出用的「当前这篇」
    vnReaderSetTitle(parsed.title || name.replace(/\.md$/, ""));
    // 「仅提取」模式存的未分析笔记：在「AI 分析」页里给一个就地补做的按钮
    if (/-\s*状态[：:]\s*未分析/.test(data.content || "")) {
      const pane = resultEl.querySelector("#vAnalysis");
      if (pane) {
        const b = vnAnButton(name, "🤖 立即 AI 分析这条笔记", "send-btn", true);   // v66：分析中再点一下 = 停止
        b.style.cssText = "display:block;margin:12px 0 4px";
        pane.appendChild(b);
      }
    }
    const rd = document.getElementById("vnReader");
    if (rd) rd.scrollTop = 0;
  } catch (e) {
    resultEl.innerHTML = "<div class='dash-empty'>出错：" + escapeHtml(e.message) + "</div>";
  }
}

// ── 给「未分析」的已存笔记补做 AI 分析（后台跑，这里轮询进度）──
let _noteAnPollTimer = null;
let _noteAnRunning = "";      // v66：正在分析哪一条
let _noteAnStopReq = false;   // v66：用户点了停止

// v66：「🤖 AI 分析」按钮（完成那一行、笔记列表、打开的笔记里都用它）：
// 点一下开始分析；分析中再点一下 = 停止（AI 池卡住时用）；分析好了点它打开笔记。
function vnAnButton(name, label, cls, reopen) {
  const b = document.createElement("button");
  b.type = "button"; b.className = cls || "vdone-go";
  b.dataset.anFor = name; b.dataset.anLabel = label || "🤖 AI 分析";
  b.textContent = b.dataset.anLabel;
  b.title = "让 AI 写分析笔记（原文已经存好了，AI 池卡住也不影响；分析中再点一下可以停止）";
  b.addEventListener("click", (e) => {
    e.stopPropagation();
    if (b.dataset.anState === "done") { openVideoNote(name); return; }
    if (b.dataset.anState === "running") { stopNoteAnalyze(name); return; }
    b.dataset.anState = "running"; b.textContent = "已提交…";
    startNoteAnalyze(name, { reopen: !!reopen });
  });
  if (_noteAnRunning === name) setTimeout(() => vnAnState(name, "running", ""), 0);
  return b;
}

function vnAnState(name, st, text) {
  document.querySelectorAll("[data-an-for]").forEach((b) => {
    if (b.dataset.anFor !== name) return;
    b.dataset.anState = st; b.disabled = false;
    if (st === "running") {
      b.textContent = _noteAnStopReq ? "正在停止…" : "⏹ 分析中…点这里停止";
      b.title = (text ? "现在：" + text + "\n" : "") + "AI 池卡住了就点这里，马上放下这条（原文不受影响）";
      if (_noteAnStopReq) b.disabled = true;
    } else if (st === "done") {
      b.textContent = "✓ 分析好了，点开看";
      setTimeout(() => vnUnDrop([name]), 0);
    } else {
      b.textContent = st === "stopped" ? "🤖 AI 分析（已停止，可以再点）"
        : st === "fail" ? "🤖 AI 分析（没成功，再试一次）" : (b.dataset.anLabel || "🤖 AI 分析");
    }
  });
}

async function stopNoteAnalyze(name) {
  _noteAnStopReq = true;
  vnAnState(name, "running", "");
  try {
    const d = await (await fetch(BACKEND + "/video_note_analyze_stop", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).json();
    if (!d.ok) {
      _noteAnStopReq = false;
      vnAnState(name, "running", "");
      setVideoStatus(d.message || "没停下来", "warn", { priority: true, holdMs: 6000 });
    } else {
      setVideoStatus("⏹ 正在停止分析…（一两秒）", "", { priority: true, holdMs: 3000 });
    }
  } catch (e) {
    _noteAnStopReq = false;
    setVideoStatus("停止出错：" + e.message, "warn", { priority: true, holdMs: 6000 });
  }
}
async function startNoteAnalyze(name, opts) {
  opts = opts || {};
  try {
    const s = settings();
    const r = await fetch(BACKEND + "/video_note_analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (!d.ok) {
      setAnStatus("没开始分析：" + (d.error || "未知原因"), "warn", 10000);
      vnAnState(name, "idle");
      loadVideoNotes();   // 把按钮的「已提交…」状态恢复回来
      return;
    }
    _noteAnRunning = name; _noteAnStopReq = false;
    vnAnState(name, "running", "已提交");
    setAnStatus("🤖 正在分析《" + viNoteTitle(name) + "》…（可能要一两分钟，完成后自动刷新）");
    if (document.getElementById("view-video")?.dataset.mode !== "process") {
      setVideoStatus("🤖 已交给「加工」做 AI 分析，进度和实时画面在加工页。", "ok", { priority: true, holdMs: 5000 });
    }
    pollNoteAnalyze(name, !!opts.reopen);
  } catch (e) {
    setAnStatus("分析出错：" + e.message, "warn", 10000);
  }
}

function pollNoteAnalyze(name, reopen) {
  if (_noteAnPollTimer) return;   // 已经在轮询了
  _noteAnPollTimer = setInterval(async () => {
    try {
      const r = await fetch(BACKEND + "/video_note_analyze_progress");
      const p = await r.json();
      if (p.running) {
        setAnStatus("🤖 正在分析《" + viNoteTitle(name) + "》：" + (p.stage || "处理中…") + "（卡住了可以点「分析中…」停止）");
        vnAnState(name, "running", p.stage || "");
        return;
      }
      clearInterval(_noteAnPollTimer); _noteAnPollTimer = null;
      const stopped = _noteAnStopReq;
      _noteAnRunning = ""; _noteAnStopReq = false;
      vnAnState(name, p.ok ? "done" : (stopped ? "stopped" : "fail"));
      if (!p.ok && stopped) {
        setAnStatus("⏹ 已停止分析。原文还在，需要时再点「AI 分析」。", "ok", 10000);
        loadVideoNotes();
      } else if (p.ok) {
        setAnStatus("✅《" + viNoteTitle(name) + "》分析好了，成品在「笔记」里。", "ok", 12000);
        loadVideoNotes();
        if (reopen && name && vnReaderIsOpen() && _vnReaderName === name) openVideoNote(name);
      } else {
        setAnStatus("⚠《" + viNoteTitle(name) + "》没分析成功：" + (p.error || "未知原因"), "warn", 12000);
        loadVideoNotes();
      }
    } catch (e) {
      clearInterval(_noteAnPollTimer); _noteAnPollTimer = null;
      setAnStatus("分析进度查询出错：" + e.message, "warn", 10000);
    }
  }, 1500);
}

// 把存档的 markdown 拆回 标题/作者/链接/标签/分析/原文，喂给标签页视图
function parseVideoNote(md) {
  const out = { title: "", uploader: "", url: "", tags: [], analysis: "", transcript: "" };
  const lines = md.split("\n");
  if (lines[0]) out.title = lines[0].replace(/^#\s*/, "").trim();
  const mu = md.match(/作者：(.*)/); if (mu) out.uploader = mu[1].trim();
  const ml = md.match(/来源链接：(.*)/); if (ml) out.url = ml[1].trim();
  // 解析标签行：- 标签：金融、逻辑、AI
  const mt = md.match(/标签[：:]\s*(.+)/);
  if (mt) {
    out.tags = mt[1].split(/[、,，\s]+/).map((s) => s.trim()).filter(Boolean);
  }
  // 分析在 "## 🤖 AI 分析" 和 "## 📝 完整文字稿" 之间
  const aMark = md.indexOf("AI 分析");
  // v94：认标题行「## 📝 完整文字稿」（最后一个），别认 AI 分析正文里随口提到的「完整文字稿」
  let tMark = -1;
  { const re = /^#{1,3}\s*(?:📝\s*)?完整文字稿\s*$/gm; let m; while ((m = re.exec(md))) tMark = m.index; }
  if (tMark < 0) tMark = md.indexOf("完整文字稿");
  if (aMark >= 0) {
    const aStart = md.indexOf("\n", aMark);
    const aEnd = tMark >= 0 ? md.lastIndexOf("\n", tMark) : md.length;
    out.analysis = md.slice(aStart, aEnd).replace(/^\s*-+\s*$/m, "").trim();
  }
  if (tMark >= 0) {
    const tStart = md.indexOf("\n", tMark);
    out.transcript = md.slice(tStart).trim();
  }
  if (!out.analysis && !out.transcript) out.analysis = md; // 兜底
  return out;
}

// ---------- 成长库（汇总各工具产出，按类别归档）----------
let _libData = { video: [], learning: [], info: [], sniff: [], all_tags: {} };
let _libCat = "video";
let _libTagFilter = "";   // 当前选中的二级标签过滤；"" = 全部

async function loadLibrary() {
  try {
    const r = await fetch(BACKEND + "/library");
    _libData = await r.json();
  } catch (e) {
    _libData = { video: [], learning: [], info: [], sniff: [], all_tags: {} };
  }
  const setCount = (id, n) => { const el = document.getElementById(id); if (el) el.textContent = n; };
  setCount("libCntVideo", (_libData.video || []).length);
  setCount("libCntLearning", (_libData.learning || []).length);
  setCount("libCntInfo", (_libData.info || []).length);
  setCount("libCntSniff", (_libData.sniff || []).length);
  renderLibList(_libCat);
}

function renderLibList(cat) {
  if (cat !== _libCat) _libTagFilter = "";   // 切换类别时清掉标签过滤
  _libCat = cat;
  document.querySelectorAll(".lib-tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.cat === cat));
  const body = document.getElementById("libBody");
  if (!body) return;
  let items = _libData[cat] || [];
  const allTags = (_libData.all_tags && _libData.all_tags[cat]) || [];

  // 标签过滤条（只要这个类别里有人用过标签就显示）
  let filterBar = "";
  if (allTags.length) {
    filterBar = '<div class="lib-tagbar">' +
      '<button class="lib-tagchip' + (_libTagFilter === "" ? " active" : "") +
        '" data-tag="">全部</button>' +
      allTags.map((t) =>
        '<button class="lib-tagchip' + (_libTagFilter === t ? " active" : "") +
          '" data-tag="' + escapeHtml(t) + '">' + escapeHtml(t) + "</button>").join("") +
      "</div>";
  }

  // 视频类：顶部给一个「AI 一键补标签」按钮，给还没标签的旧视频自动补上
  let actionBar = "";
  if (cat === "video") {
    const noTagCount = (_libData.video || []).filter(
      (it) => !(it.tags && it.tags.length)).length;
    actionBar = '<div class="lib-actionbar">' +
      '<button class="lib-autotag-btn" id="libAutotagBtn"' +
        (noTagCount ? "" : " disabled") + '>🏷 AI 一键补标签' +
        (noTagCount ? '（' + noTagCount + ' 条待补）' : '（都已有标签）') +
      "</button>" +
      '<span class="lib-autotag-tip" id="libAutotagTip"></span>' +
      "</div>";
  }

  // 应用过滤
  if (_libTagFilter) {
    items = items.filter((it) => (it.tags || []).includes(_libTagFilter));
  }

  if (!items.length) {
    const tip = _libTagFilter ? ("没有带「" + _libTagFilter + "」标签的内容。") : {
      video: "还没有视频内容。去「视频」板块，或在对话里发个视频链接提取，结果会自动归到这里。",
      learning: "还没有学习内容。去「学习」板块用一用，生成的学习档案和每日任务会归到这里。",
      info: "还没有信息内容。点左下角「生成情报简报」，结果会自动归到这里。",
      sniff: "还没有嗅探简报。去「嗅探」板块点「📄 深度嗅探」生成一份，结果会自动归到这里。",
    }[cat] || "这个类别还是空的。";
    body.innerHTML = actionBar + filterBar + '<div class="lib-empty">' + escapeHtml(tip) + "</div>";
    bindLibTagbar(body);
    bindLibAutotag(body);
    return;
  }

  // 视频类只支持标签（视频里全是视频，来源标签没意义）；其它类别保留来源标签
  const supportsTags = (cat === "video");

  body.innerHTML = actionBar + filterBar + '<div class="lib-list">' + items.map((it) => {
    const tags = it.tags || [];
    // 二级标签优先显示；视频类不再显示「视频笔记」来源块
    let lead = "";
    if (supportsTags) {
      if (tags.length) {
        lead = tags.map((t) =>
          '<span class="lib-row-tag">' + escapeHtml(t) + "</span>").join("");
      } else {
        lead = '<span class="lib-row-tag lib-row-tag-empty">+ 加标签</span>';
      }
    } else {
      lead = '<span class="lib-row-src">' + escapeHtml(it.source || "") + "</span>";
    }
    return '<div class="lib-row" data-cat="' + escapeHtml(it.cat || cat) +
      '" data-name="' + escapeHtml(it.name) + '">' +
      '<div class="lib-row-main">' +
        '<span class="lib-row-lead">' + lead + "</span>" +
        '<span class="lib-row-title">' + escapeHtml(it.title || it.name) + "</span>" +
      "</div>" +
      (supportsTags ? '<button class="lib-row-edit" title="设置二级标签">🏷</button>' : "") +
      '<span class="lib-row-date">' + escapeHtml(it.date || "") + "</span>" +
    "</div>";
  }).join("") + "</div>";

  bindLibTagbar(body);
  bindLibAutotag(body);

  body.querySelectorAll(".lib-row").forEach((c) => {
    // 点标签编辑按钮 / 空标签占位 → 打开标签编辑器，不进详情
    const openEditor = (e) => {
      e.stopPropagation();
      editLibTags(c.dataset.cat, c.dataset.name);
    };
    const editBtn = c.querySelector(".lib-row-edit");
    if (editBtn) editBtn.addEventListener("click", openEditor);
    const emptyTag = c.querySelector(".lib-row-tag-empty");
    if (emptyTag) emptyTag.addEventListener("click", openEditor);
    c.addEventListener("click", () => openLibItem(c.dataset.cat, c.dataset.name));
  });
}

function bindLibTagbar(scope) {
  scope.querySelectorAll(".lib-tagchip").forEach((b) =>
    b.addEventListener("click", () => {
      _libTagFilter = b.dataset.tag || "";
      renderLibList(_libCat);
    }));
}

// 「AI 一键补标签」：给还没标签的旧视频批量补上 AI 标签
function bindLibAutotag(scope) {
  const btn = scope.querySelector("#libAutotagBtn");
  if (!btn) return;
  const tip = scope.querySelector("#libAutotagTip");
  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    const old = btn.textContent;
    btn.textContent = "AI 正在补标签…（可能要一会儿）";
    if (tip) tip.textContent = "";
    try {
      const s = settings();
      const r = await fetch(BACKEND + "/library_autotag", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_local: s.use_local, model: s.model, limit: 30 }),
      });
      const d = await r.json();
      if (d && d.ok) {
        if (tip) tip.textContent = "✓ 已补 " + d.done + " 条" +
          (d.failed ? "，" + d.failed + " 条没成功" : "") + "。";
        await loadLibrary();          // 刷新列表和过滤条
      } else {
        if (tip) tip.textContent = "没成功：" + ((d && d.error) || "未知错误");
        btn.disabled = false; btn.textContent = old;
      }
    } catch (e) {
      if (tip) tip.textContent = "出错：" + e.message;
      btn.disabled = false; btn.textContent = old;
    }
  });
}

// 找到某条内容当前的标签
function _libFindItem(cat, name) {
  return (_libData[cat] || []).find((x) => x.name === name);
}

// 弹出一个轻量的标签编辑器（自定义二级标签：可输入新标签 / 点已有标签）
// title：弹窗副标题；initial：初始标签；onSaved(savedTags)：保存成功回调
function openTagEditor(cat, name, title, initial, onSaved) {
  const current = (initial || []).slice();
  const suggest = (_libData.all_tags && _libData.all_tags[cat]) || [];

  const mask = document.createElement("div");
  mask.className = "lib-tag-modal-mask";
  mask.innerHTML =
    '<div class="lib-tag-modal">' +
      '<div class="lib-tag-modal-title">设置二级标签</div>' +
      '<div class="lib-tag-modal-sub">' + escapeHtml(title || name) + "</div>" +
      '<div class="lib-tag-chosen" id="tagChosen"></div>' +
      '<div class="lib-tag-inputrow">' +
        '<input id="tagInput" class="lib-tag-input" placeholder="输入新标签，回车添加（如 金融 / 逻辑 / AI）" maxlength="20">' +
        '<button id="tagAdd" class="lib-tag-add">添加</button>' +
      "</div>" +
      (suggest.length ? '<div class="lib-tag-suglabel">已用过的标签（点一下加上）</div>' +
        '<div class="lib-tag-suggest" id="tagSuggest"></div>' : "") +
      '<div class="lib-tag-actions">' +
        '<button id="tagCancel" class="lib-tag-btn">取消</button>' +
        '<button id="tagSave" class="lib-tag-btn primary">保存</button>' +
      "</div>" +
    "</div>";
  document.body.appendChild(mask);

  const chosenEl = mask.querySelector("#tagChosen");
  const inputEl = mask.querySelector("#tagInput");
  const sugEl = mask.querySelector("#tagSuggest");

  function renderChosen() {
    chosenEl.innerHTML = current.length
      ? current.map((t, i) =>
          '<span class="lib-tag-pill">' + escapeHtml(t) +
            '<button data-i="' + i + '">×</button></span>').join("")
      : '<span class="lib-tag-none">还没有标签</span>';
    chosenEl.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        current.splice(+b.dataset.i, 1); renderChosen();
      }));
  }
  function addTag(raw) {
    const t = (raw || "").trim().replace(/[、,，]/g, "");
    if (t && !current.includes(t) && current.length < 8) current.push(t);
    inputEl.value = "";
    renderChosen();
  }
  renderChosen();

  if (sugEl) {
    sugEl.innerHTML = suggest.map((t) =>
      '<button class="lib-tag-sug" data-t="' + escapeHtml(t) + '">' + escapeHtml(t) + "</button>").join("");
    sugEl.querySelectorAll(".lib-tag-sug").forEach((b) =>
      b.addEventListener("click", () => addTag(b.dataset.t)));
  }

  mask.querySelector("#tagAdd").addEventListener("click", () => addTag(inputEl.value));
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); addTag(inputEl.value); }
  });
  const close = () => mask.remove();
  mask.querySelector("#tagCancel").addEventListener("click", close);
  mask.addEventListener("click", (e) => { if (e.target === mask) close(); });
  mask.querySelector("#tagSave").addEventListener("click", async () => {
    addTag(inputEl.value);   // 输入框里没回车的也一并算上
    let savedTags = current.slice();
    try {
      const r = await fetch(BACKEND + "/library_set_tags", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cat, name, tags: current }),
      });
      const d = await r.json();
      if (d && d.ok && Array.isArray(d.tags)) savedTags = d.tags;
    } catch (_) {}
    // 同步更新内存里的库数据（如果已加载），让列表/过滤条即时一致
    const it = _libFindItem(cat, name);
    if (it) it.tags = savedTags.slice();
    close();
    if (onSaved) onSaved(savedTags);
  });
  setTimeout(() => inputEl.focus(), 30);
}

// 列表行上的标签编辑：保存后整库刷新（更新过滤条、计数）
function editLibTags(cat, name) {
  const item = _libFindItem(cat, name);
  const current = (item && item.tags) ? item.tags.slice() : [];
  openTagEditor(cat, name, (item && item.title) || name, current,
    async () => { await loadLibrary(); });
}

// 详情页内的标签编辑：保存后只回调刷新当前页那一行（必要时也刷新内存库数据）
function openInPageTagEditor(cat, name, current, onSaved) {
  // 确保 _libData 里有可供「已用标签」提示的数据；没有就静默拉一次
  if (!_libData.all_tags) { try { loadLibrary(); } catch (_) {} }
  openTagEditor(cat, name, name, current || [], (saved) => {
    if (onSaved) onSaved(saved);
  });
}

async function openLibItem(cat, name) {
  const body = document.getElementById("libBody");
  body.innerHTML = '<button class="lib-back" id="libBack">← 返回列表</button>' +
    '<div class="dash-content video-result" id="libDetailHost">' +
      '<div class="dash-loading">读取中…</div></div>';
  document.getElementById("libBack").addEventListener("click", () => renderLibList(_libCat));
  const host = document.getElementById("libDetailHost");
  try {
    const r = await fetch(BACKEND + "/library_item?cat=" + encodeURIComponent(cat) +
                          "&name=" + encodeURIComponent(name));
    const d = await r.json();
    if (!d.ok) { host.innerHTML = '<div class="dash-empty">打开失败：' + escapeHtml(d.error || "未知") + "</div>"; return; }
    if (cat === "video") {
      // 视频条目：复用「视频」标签页那套完全一样的视图（标签 + 详细/简洁开关 + 色块标题）
      const parsed = parseVideoNote(d.content || "");
      parsed._noteName = name;
      parsed._noteCat = "video";
      mountVideoResult(parsed, host);
    } else {
      // 学习 / 信息条目：套用和视频一样舒展的排版（标题色块 + 工具条），不再是挤巴巴的纯 markdown
      mountSimpleDoc(d.content || "（空）", host);
    }
  } catch (e) {
    host.innerHTML = '<div class="dash-empty">打开出错：' + escapeHtml(e.message) + "</div>";
  }
}

document.querySelectorAll(".lib-tab").forEach((t) =>
  t.addEventListener("click", () => renderLibList(t.dataset.cat)));

async function loadDashboard() {
  const pane = document.getElementById("dashPane");
  pane.innerHTML = '<div class="dash-loading">加载中…</div>';
  try {
    const resp = await fetch(BACKEND + "/dashboard");
    const d = await resp.json();
    pane.innerHTML = renderDashboard(d);
  } catch (e) {
    pane.innerHTML = '<div class="dash-loading">加载失败：' +
      escapeHtml(e.message) + "</div>";
  }
}

function renderDashboard(d) {
  let h = "";

  // 最新简报
  h += '<div class="dash-card"><div class="dash-card-title">📊 最新情报简报</div>';
  if (d.latest_briefing) {
    h += `<div class="dash-meta">${escapeHtml(d.latest_briefing.time)} ·
          共 ${d.latest_briefing.count} 份历史简报</div>`;
    h += `<div class="dash-content">${renderMarkdown(d.latest_briefing.content)}</div>`;
  } else {
    h += '<div class="dash-empty">还没有简报。去左侧点「📊 生成情报简报」，' +
         '记得先在「设置 → 配置」的情报关键词里 配好关键词。</div>';
  }
  h += "</div>";

  // 竞品监控
  h += '<div class="dash-card"><div class="dash-card-title">🔍 竞品监控</div>';
  const c = d.competitors || {};
  if (c.targets && c.targets.length) {
    h += `<div class="dash-meta">监控 ${c.targets.length} 个页面 ·
          已存 ${c.snapshot_count} 份快照</div><div class="dash-list">`;
    c.targets.forEach((t) => {
      h += `<div class="dash-item"><b>${escapeHtml(t.note || "（无备注）")}</b>
            <span class="dash-url">${escapeHtml(t.url)}</span></div>`;
    });
    h += "</div>";
  } else {
    h += '<div class="dash-empty">还没有监控目标。去「设置 → 配置」的竞品网址里 ' +
         '加竞品网址。</div>';
  }
  h += "</div>";

  // 关注关键词
  h += '<div class="dash-card"><div class="dash-card-title">👀 情报关注</div>';
  if (d.watchlist && d.watchlist.length) {
    h += '<div class="dash-tags">';
    d.watchlist.forEach((w) => { h += `<span class="dash-tag">${escapeHtml(w)}</span>`; });
    h += "</div>";
  } else {
    h += '<div class="dash-empty">还没有关注关键词。</div>';
  }
  h += "</div>";

  // 提醒 + 今日笔记
  h += '<div class="dash-card"><div class="dash-card-title">⏰ 待办提醒</div>' +
       `<div class="dash-content">${renderMarkdown(d.reminders || "")}</div></div>`;
  h += '<div class="dash-card"><div class="dash-card-title">📝 今日笔记</div>' +
       `<div class="dash-content">${renderMarkdown(d.today_note || "")}</div></div>`;

  h += `<div class="dash-foot">更新于 ${escapeHtml(d.generated_at || "")}</div>`;
  return h;
}

document.getElementById("refreshDashBtn").addEventListener("click", loadDashboard);

function loadMemoryTabs() {
  _memScope = "mem";
  const tabs = document.getElementById("memoryTabs");
  tabs.innerHTML = "";
  // 记忆页只显示「AI 对你的理解」这一类；配置类已挪到「设置 → 配置」
  if (!MEMORY_FILES_MEM.includes(currentMemoryFile)) currentMemoryFile = MEMORY_FILES_MEM[0];
  MEMORY_FILES_MEM.forEach((f) => {
    const t = document.createElement("button");
    t.className = "memory-tab" + (f === currentMemoryFile ? " active" : "");
    t.textContent = (MEMORY_META[f] && MEMORY_META[f].label) || f;
    t.addEventListener("click", () => { currentMemoryFile = f; loadMemoryTabs(); });
    tabs.appendChild(t);
  });
  loadMemoryContent(currentMemoryFile);
}

// 设置 → 配置 tab：用同一套编辑器，但宿主是 setMemXxx 容器
let _cfgCurrentFile = null;
function loadConfigTabs() {
  _memScope = "set";
  const tabs = document.getElementById("setMemTabs");
  if (!tabs) return;
  tabs.innerHTML = "";
  if (!_cfgCurrentFile || !MEMORY_FILES_CFG.includes(_cfgCurrentFile)) _cfgCurrentFile = MEMORY_FILES_CFG[0];
  currentMemoryFile = _cfgCurrentFile;
  MEMORY_FILES_CFG.forEach((f) => {
    const t = document.createElement("button");
    t.className = "memory-tab" + (f === _cfgCurrentFile ? " active" : "");
    t.textContent = (MEMORY_META[f] && MEMORY_META[f].label) || f;
    t.addEventListener("click", () => { _cfgCurrentFile = f; loadConfigTabs(); });
    tabs.appendChild(t);
  });
  currentMemoryFile = _cfgCurrentFile;
  loadMemoryContent(_cfgCurrentFile);
}

// 记忆编辑器的「宿主作用域」：记忆视图用 memXxx，设置·配置 tab 用 setMemXxx。
// 这样同一套编辑器既能在「记忆」页用，也能在「设置→配置」里用，互不打架。
let _memScope = "mem";   // "mem" | "set"
function mEl(suffix) {
  const prefix = _memScope === "set" ? "setMem" : "memory";
  // memory 视图的 id：memoryBody/memoryDesc/memoryEditor/memoryModeBar/memoryTabs
  // 设置配置 tab 的 id：setMemBody/setMemDesc/setMemEditor/setMemModeBar/setMemTabs
  const map = _memScope === "set"
    ? { Body: "setMemBody", Desc: "setMemDesc", Editor: "setMemEditor",
        ModeBar: "setMemModeBar", Tabs: "setMemTabs" }
    : { Body: "memoryBody", Desc: "memoryDesc", Editor: "memoryEditor",
        ModeBar: "memoryModeBar", Tabs: "memoryTabs" };
  return document.getElementById(map[suffix]);
}

async function loadMemoryContent(name) {
  const body = mEl("Body");
  const descEl = mEl("Desc");
  const editor = mEl("Editor");
  const meta = MEMORY_META[name] || { type: "text" };
  descEl.textContent = meta.desc || "";
  // 每次切文件，文本型默认回到「结构化」模式
  _memTextMode = "struct";
  document.getElementById("memModeStruct")?.classList.add("active");
  document.getElementById("memModeRaw")?.classList.remove("active");
  const _tip = document.getElementById("memModeTip");
  if (_tip) _tip.textContent = "按小标题分区编辑，更清晰";
  // 默认先把自由文本框藏起来、清空 body
  editor.style.display = "none";
  body.innerHTML = "<div class='dash-loading'>加载中…</div>";
  let content = "";
  try {
    const resp = await fetch(BACKEND + "/memory?name=" + encodeURIComponent(name));
    const data = await resp.json();
    content = data.content || "";
  } catch (e) {
    body.innerHTML = "<div class='dash-empty'>读取失败：" + escapeHtml(e.message) + "</div>";
    return;
  }

  const modeBar = mEl("ModeBar");
  if (meta.type === "text") {
    // 自由文本（SOUL/USER/MEMORY…）：默认结构化分区编辑，可切原始文本
    if (modeBar) modeBar.style.display = "";
    body.style.display = "";
    _memTextRaw = content;            // 缓存原始内容，供两种模式互转
    renderTextEditor(body, name, content, meta);
  } else if (meta.type === "list") {
    if (modeBar) modeBar.style.display = "none";
    body.style.display = "";
    renderListEditor(body, name, content, meta);
  } else if (meta.type === "config") {
    if (modeBar) modeBar.style.display = "none";
    body.style.display = "";
    renderConfigEditor(body, name, content, meta);
  }
}

// ---- 文本型结构化编辑器：把 ## 小标题解析成可编辑的分区块 ----
let _memTextRaw = "";           // 当前文本文件的原始内容
let _memTextMode = "struct";    // struct | raw

function parseTextSections(content) {
  // 返回 { preamble, sections:[{heading, level, text}] }
  const lines = (content || "").split("\n");
  const sections = [];
  let preamble = [];
  let cur = null;
  for (const ln of lines) {
    const m = ln.match(/^(#{1,3})\s+(.+)$/);
    if (m) {
      if (cur) sections.push(cur);
      else if (preamble.join("\n").trim() === "" && sections.length === 0) preamble = [];
      cur = { level: m[1].length, heading: m[2].trim(), body: [] };
    } else if (cur) {
      cur.body.push(ln);
    } else {
      preamble.push(ln);
    }
  }
  if (cur) sections.push(cur);
  return { preamble: preamble.join("\n").trim(), sections };
}

function renderTextEditor(body, name, content, meta) {
  const editor = mEl("Editor");
  if (_memTextMode === "raw") {
    // 原始文本模式：用常驻 textarea
    body.style.display = "none";
    editor.value = content;
    editor.style.display = "";
    return;
  }
  // 结构化模式（阅读态为主，点笔才进编辑）
  editor.style.display = "none";
  body.style.display = "";
  body.innerHTML = "";
  const { preamble, sections } = parseTextSections(content);

  if (preamble) {
    const pre = document.createElement("div");
    pre.className = "mem-preamble";
    pre.textContent = preamble.replace(/^#\s+.*$/m, "").trim() || preamble;
    if (pre.textContent.trim()) body.appendChild(pre);
  }

  // 造一个分区块：默认显示「阅读卡片」，点笔切换成编辑框
  function makeBlock(heading, level, text) {
    const blk = document.createElement("div");
    blk.className = "mem-section";

    const head = document.createElement("div");
    head.className = "mem-section-head";
    const htext = document.createElement("span");
    htext.textContent = (level >= 3 ? "› " : "") + (heading || "（无标题）");
    head.appendChild(htext);
    const pen = document.createElement("button");
    pen.className = "mem-edit-btn"; pen.title = "编辑这一节"; pen.textContent = "✏️";
    head.appendChild(pen);
    blk.appendChild(head);

    // 阅读视图（渲染 markdown，好看）
    const read = document.createElement("div");
    read.className = "mem-section-read";
    const renderRead = (t) => {
      read.innerHTML = (t || "").trim()
        ? renderMarkdown(t)
        : '<span class="mem-section-empty">（空，点 ✏️ 添加内容）</span>';
    };
    renderRead(text);
    blk.appendChild(read);

    // 编辑视图（textarea，默认隐藏）
    const ta = document.createElement("textarea");
    ta.className = "mem-section-text";
    ta.value = text;
    ta.dataset.heading = heading || "";
    ta.dataset.level = level;
    ta.style.display = "none";
    blk.appendChild(ta);

    let editing = false;
    pen.onclick = () => {
      editing = !editing;
      if (editing) {
        read.style.display = "none";
        ta.style.display = "";
        pen.textContent = "✓"; pen.title = "完成";
        autoGrowArea(ta); ta.focus();
      } else {
        renderRead(ta.value);
        read.style.display = "";
        ta.style.display = "none";
        pen.textContent = "✏️"; pen.title = "编辑这一节";
      }
    };
    return blk;
  }

  if (!sections.length) {
    body.appendChild(makeBlock("", 2, content));
    return;
  }
  sections.forEach((sec) => {
    body.appendChild(makeBlock(sec.heading, sec.level,
      sec.body.join("\n").replace(/^\n+|\n+$/g, "")));
  });

  // 末尾「+ 添加一节」
  const add = document.createElement("button");
  add.className = "ghost-btn mem-add-section";
  add.textContent = "＋ 添加一节";
  add.onclick = async () => {
    const h = await _cwPromptModal({
      title: "添加分节",
      desc: "给新分节起个小标题。",
      placeholder: "如：我的偏好",
      okText: "添加",
    });
    if (!h || !h.trim()) return;
    const blk = makeBlock(h.trim(), 2, "");
    body.insertBefore(blk, add);
    blk.querySelector(".mem-edit-btn")?.click();   // 新节直接进编辑态
  };
  body.appendChild(add);
}

function autoGrowArea(ta) {
  const fit = () => { ta.style.height = "auto"; ta.style.height = Math.max(44, ta.scrollHeight) + "px"; };
  ta.addEventListener("input", fit);
  setTimeout(fit, 0);
}

// 把文件顶部的说明行（# 或 > 开头、空行）抽出来，保存时原样写回
function splitHeader(content) {
  const lines = content.split("\n");
  const header = [];
  let i = 0;
  for (; i < lines.length; i++) {
    const t = lines[i].trim();
    if (t === "" || t.startsWith("#") || t.startsWith(">")) header.push(lines[i]);
    else break;
  }
  return { header: header.join("\n"), rest: lines.slice(i).join("\n") };
}

// ---- 列表型编辑器（关键词 / 网址 / 提醒）----
function renderListEditor(body, name, content, meta) {
  const { header } = splitHeader(content);
  _rawHeader = header;
  const sep = meta.sep || "|";
  // 解析已有条目（- 开头的行）
  const items = [];
  content.split("\n").forEach((line) => {
    let t = line.trim();
    if (!t.startsWith("-")) return;
    t = t.replace(/^-\s*(\[.\]\s*)?/, "");  // 去掉 - 和可能的 [ ]
    if (!t) return;
    if (meta.hasNote && t.includes(sep)) {
      const idx = t.indexOf(sep);
      items.push({ val: t.slice(0, idx).trim(), note: t.slice(idx + 1).trim() });
    } else {
      items.push({ val: t, note: "" });
    }
  });

  body.innerHTML = "";
  const list = document.createElement("div");
  list.className = "kv-list";
  body.appendChild(list);

  function addRow(val = "", note = "") {
    const row = document.createElement("div");
    row.className = "kv-row";
    const v = document.createElement("input");
    v.className = "text-input kv-val"; v.placeholder = meta.placeholder || "";
    v.value = val; v.style.width = "auto"; v.style.flex = "1";
    row.appendChild(v);
    let n = null;
    if (meta.hasNote) {
      n = document.createElement("input");
      n.className = "text-input kv-note"; n.placeholder = meta.notePlaceholder || "备注";
      n.value = note; n.style.width = "auto"; n.style.flex = "1";
      row.appendChild(n);
    }
    const del = document.createElement("button");
    del.className = "kv-del"; del.textContent = "✕"; del.title = "删除这行";
    del.onclick = () => row.remove();
    row.appendChild(del);
    list.appendChild(row);

    // 回车：确定本行，自动新增下一行并聚焦
    const onEnter = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        // 如果这是最后一行，就新增一行；否则跳到下一行
        const rows = Array.from(list.querySelectorAll(".kv-row"));
        const idx = rows.indexOf(row);
        if (idx === rows.length - 1) {
          const nv = addRow();
          if (nv) nv.focus();
        } else {
          const nextVal = rows[idx + 1].querySelector(".kv-val");
          if (nextVal) nextVal.focus();
        }
      }
    };
    v.addEventListener("keydown", onEnter);
    if (n) n.addEventListener("keydown", onEnter);
    return v;
  }

  items.forEach((it) => addRow(it.val, it.note));
  if (items.length === 0) addRow();

  const add = document.createElement("button");
  add.className = "ghost-btn kv-add";
  add.textContent = "＋ 添加一行 " + (meta.itemLabel || "");
  add.onclick = () => { const nv = addRow(); if (nv) nv.focus(); };
  body.appendChild(add);
}

// ---- 配置型编辑器（key: value 表单）----
function renderConfigEditor(body, name, content, meta) {
  const { header } = splitHeader(content);
  _rawHeader = header;
  // 解析已有的 key: value
  const vals = {};
  content.split("\n").forEach((line) => {
    const m = line.match(/^([a-zA-Z_]+)\s*:\s*(.*)$/);
    if (m) vals[m[1]] = m[2].trim();
  });

  body.innerHTML = "";
  const form = document.createElement("div");
  form.className = "cfg-form";
  meta.fields.forEach((f) => {
    const wrap = document.createElement("div");
    wrap.className = "cfg-field";
    const lab = document.createElement("label");
    lab.className = "cfg-label"; lab.textContent = f.label;
    const inp = document.createElement("input");
    inp.className = "text-input cfg-input";
    inp.dataset.key = f.key;
    inp.style.width = "100%";
    let cur = vals[f.key] || "";
    // 模板里的占位（"这里填..."）当成空
    if (cur.includes("这里填") || cur.includes("填你的")) cur = "";
    inp.value = cur;
    inp.placeholder = f.help || "";
    const help = document.createElement("div");
    help.className = "cfg-help"; help.textContent = f.help || "";
    wrap.appendChild(lab); wrap.appendChild(inp); wrap.appendChild(help);
    form.appendChild(wrap);
  });
  body.appendChild(form);
}

// 把当前编辑器的内容序列化回 .md 文本
function collectMemoryContent() {
  const name = currentMemoryFile;
  const meta = MEMORY_META[name] || { type: "text" };
  if (meta.type === "text") {
    if (_memTextMode === "raw") {
      return mEl("Editor").value;
    }
    // 结构化模式：把各分区块拼回 markdown
    const body = mEl("Body");
    const blocks = body.querySelectorAll(".mem-section");
    if (!blocks.length) return _memTextRaw;   // 没解析出分区，原样返回
    const out = [];
    const pre = body.querySelector(".mem-preamble");
    if (pre && pre.textContent.trim()) { out.push(pre.textContent.trim(), ""); }
    blocks.forEach((blk) => {
      const ta = blk.querySelector(".mem-section-text");
      const heading = ta.dataset.heading || "";
      const level = parseInt(ta.dataset.level || "2", 10);
      if (heading) out.push("#".repeat(level) + " " + heading);
      const txt = (ta.value || "").replace(/\n+$/g, "");
      if (txt.trim()) out.push("", txt);
      out.push("");
    });
    return out.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
  }
  const head = _rawHeader ? _rawHeader.replace(/\s+$/, "") + "\n\n" : "";
  if (meta.type === "list") {
    const bullet = meta.bullet || "- ";
    const sep = meta.sep || "|";
    const rows = mEl("Body").querySelectorAll(".kv-row");
    const lines = [];
    rows.forEach((r) => {
      const val = r.querySelector(".kv-val").value.trim();
      if (!val) return;
      if (meta.hasNote) {
        const note = (r.querySelector(".kv-note") || {}).value || "";
        lines.push(bullet + val + (note.trim() ? `  ${sep} ${note.trim()}` : ""));
      } else {
        lines.push(bullet + val);
      }
    });
    return head + lines.join("\n") + "\n";
  }
  if (meta.type === "config") {
    const lines = [];
    mEl("Body").querySelectorAll(".cfg-input").forEach((inp) => {
      lines.push(`${inp.dataset.key}: ${inp.value.trim()}`);
    });
    return head + lines.join("\n") + "\n";
  }
  return "";
}

// ---- 记忆：结构化 / 原始文本 切换 ----
function setMemMode(mode) {
  if (mode === _memTextMode) return;
  // 切换前先把当前编辑序列化，保留改动
  const cur = collectMemoryContent();
  _memTextRaw = cur;
  _memTextMode = mode;
  document.getElementById("memModeStruct")?.classList.toggle("active", mode === "struct");
  document.getElementById("memModeRaw")?.classList.toggle("active", mode === "raw");
  const tip = document.getElementById("memModeTip");
  if (tip) tip.textContent = mode === "raw"
    ? "高级模式：直接编辑原始 .md 文本"
    : "按小标题分区编辑，更清晰";
  const meta = MEMORY_META[currentMemoryFile] || { type: "text" };
  const body = mEl("Body");
  renderTextEditor(body, currentMemoryFile, cur, meta);
}
document.getElementById("memModeStruct")?.addEventListener("click", () => setMemMode("struct"));
document.getElementById("memModeRaw")?.addEventListener("click", () => setMemMode("raw"));

async function saveMemoryFile(hintId) {
  const content = collectMemoryContent();
  const hint = document.getElementById(hintId || "saveHint");
  try {
    const resp = await fetch(BACKEND + "/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: currentMemoryFile, content }),
    });
    const data = await resp.json();
    if (hint) hint.textContent = data.ok ? "已保存 ✓" : ("保存失败：" + data.message);
    if (hint) setTimeout(() => (hint.textContent = ""), 2500);
  } catch (e) {
    if (hint) hint.textContent = "保存出错：" + e.message;
  }
}
document.getElementById("saveMemoryBtn")?.addEventListener("click", () => saveMemoryFile("saveHint"));
document.getElementById("setMemSaveBtn")?.addEventListener("click", () => saveMemoryFile("setMemSaveHint"));

// ---------- 结束并记住（长期记忆） ----------
// 作用：把当前这段对话里"值得长期记住"的要点（你的偏好/背景/结论等）提炼出来，
// 存进长期记忆 MEMORY.md，并清空当前对话；下次开新对话会自动加载，于是"越用越懂你"。
document.getElementById("rememberBtn").addEventListener("click", async () => {
  if (messages.length === 0) {
    addSystemNote(
      "「结束并记住」是做什么的：它会把当前这段对话里值得长期记住的要点"
      + "（你的偏好、背景、习惯、重要结论等）提炼出来，存进长期记忆，"
      + "并清空当前对话——下次再聊我就还记得这些。\n\n"
      + "现在还没有可记的内容，先聊几句再点我吧。");
    return;
  }
  const btn = document.getElementById("rememberBtn");
  btn.textContent = "记忆中…";
  btn.disabled = true;
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/remember", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    if (data.ok) {
      addSystemNote(
        "🧠 已把这段对话的要点存入长期记忆，下次对话我会记得。提炼出的要点：\n"
        + (data.summary || "（这段没什么特别要记的）")
        + "\n\n（当前对话已清空，可以开始新的话题了。）");
      messages = [];
      messagesEl.querySelectorAll(".msg").forEach((n) => n.remove());
    } else {
      addSystemNote("记忆失败：" + (data.error || "未知"));
    }
  } catch (e) {
    addSystemNote("记忆出错：" + e.message);
  } finally {
    btn.textContent = "结束并记住";
    btn.disabled = false;
  }
});

// ---------- Server酱测试推送 ----------
document.getElementById("pushTestBtn")?.addEventListener("click", async () => {
  const hint = document.getElementById("pushHint");
  hint.textContent = "推送中…";
  try {
    const resp = await fetch(BACKEND + "/push/test", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await resp.json();
    hint.textContent = data.message || (data.ok ? "已推送" : "失败");
  } catch (e) {
    hint.textContent = "出错：" + e.message;
  }
});

// ---------- Telegram 启动 ----------
document.getElementById("tgStartBtn")?.addEventListener("click", async () => {
  const hint = document.getElementById("tgHint");
  const token = document.getElementById("tgToken").value.trim();
  const chatId = document.getElementById("tgChatId").value.trim();
  if (token && chatId) {
    const content =
      `# telegram.md\n\ntoken: ${token}\nallowed_chat_id: ${chatId}\n`;
    await fetch(BACKEND + "/memory", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "telegram.md", content }),
    });
  }
  hint.textContent = "启动中…";
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/telegram/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    hint.textContent = data.message || (data.ok ? "已启动" : "启动失败");
  } catch (e) {
    hint.textContent = "出错：" + e.message;
  }
});

// ---------- 皮肤（浅色/深色）----------
// 新方案：浅色为默认（不加 class），深色加 body.dark
function applyTheme(theme) {
  const t = theme === "dark" ? "dark" : "light";
  document.body.classList.toggle("dark", t === "dark");
  document.body.classList.remove("light");   // 兼容旧 class，清掉
  try { localStorage.setItem("cx_theme_v2", t); } catch (_) {}
  const sel = document.getElementById("themeSelect");
  if (sel) sel.value = t;
}
// 给顶部菜单"切换皮肤"用
window.toggleTheme = function () {
  const now = document.body.classList.contains("dark") ? "dark" : "light";
  applyTheme(now === "dark" ? "light" : "dark");
};
// 启动时读取上次的选择（默认浅色，Win11 风格）
// 用新 key（v2）：旧用户存的 "dark" 不再生效，一律先给清爽的浅色
(function initTheme() {
  let saved = "light";
  try { saved = localStorage.getItem("cx_theme_v2") || "light"; } catch (_) {}
  applyTheme(saved);
})();
document.getElementById("themeSelect")?.addEventListener("change", (e) => {
  applyTheme(e.target.value);
});

// 模型提示
function updateModelHint() {
  const s = settings();
  const el = document.getElementById("modelHint");
  if (el) {
    // 网页大模型（伪模型）：它不是本地也不是普通云端，单独显示，避免「本地 · web」的误导
    if (s.model === "web") el.textContent = "🌐 网页模型";
    else if (s.model === "claude" || s.model.startsWith("claude::")) {
      const ent = _modelEntries.find((e) => e.value === s.model);
      el.textContent = ent ? ent.label : "✦ Claude";
    }
    else el.textContent = (s.use_local ? "本地 · " : "云端 · ") + s.model;
  }
  // 让输入框里的模型选择器跟随当前模型（在设置里改了模型时也保持一致）
  if (typeof updateModelPickerLabel === "function") updateModelPickerLabel();
  const menu = document.getElementById("modelPickerMenu");
  if (menu) {
    const v = currentComposerValue();
    menu.querySelectorAll(".mp-item").forEach((it) => {
      it.classList.toggle("active", it.dataset.value === v);
    });
  }
}
["useLocal", "modelName", "modelSelect"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("change", () => { updateModelHint(); scheduleEnvRecheck(); });
  if (el) el.addEventListener("input", updateModelHint);
});

// 切换模型/本地云端后，过一会儿重新检查环境，让右上角亮点跟着更新
let _envTimer = null;
function scheduleEnvRecheck() {
  if (_envTimer) clearTimeout(_envTimer);
  _envTimer = setTimeout(() => runEnvCheck(true), 600);
}

// ---------- 模型下拉 ----------
async function loadModels(preferred) {
  const sel = document.getElementById("modelSelect");
  if (!sel) return;
  const want = preferred || currentModel();
  try {
    const resp = await fetch(BACKEND + "/models");
    const data = await resp.json();
    const models = data.models || [];
    const cloud = data.cloud || [];
    const web = data.web || [];
    const claude = data.claude || [];
    sel.innerHTML = "";

    const addOpt = (group, m, label) => {
      const opt = document.createElement("option");
      opt.value = m; opt.textContent = label || m;
      if (m === want || m.split(":")[0] === want.split(":")[0]) opt.selected = true;
      group.appendChild(opt);
    };

    if (models.length === 0 && cloud.length === 0 && web.length === 0) {
      const opt = document.createElement("option");
      opt.value = ""; opt.textContent = "（没检测到模型，点手动输入）";
      sel.appendChild(opt);
    } else {
      if (models.length) {
        const g = document.createElement("optgroup");
        g.label = "本地模型";
        models.forEach((m) => addOpt(g, m));
        sel.appendChild(g);
      }
      if (cloud.length) {
        const g = document.createElement("optgroup");
        g.label = "☁ 云端模型（需先 ollama signin）";
        cloud.forEach((m) => addOpt(g, m, "☁ " + m));
        sel.appendChild(g);
      }
      if (web.length) {
        const g = document.createElement("optgroup");
        g.label = "☁☁ 网页模型";
        web.forEach((m) => addOpt(g, m.id || "web", "☁☁ " + (m.name || "网页模型")));
        sel.appendChild(g);
      }
      if (claude.length) {
        const g = document.createElement("optgroup");
        g.label = "✦ Claude 官方";
        claude.forEach((m) => addOpt(g, m.id || "claude", "✦ " + (m.name || "Claude")));
        sel.appendChild(g);
      }
    }
    buildComposerModel(models, cloud, web, claude);
    populateDefaultModelSelect(models, cloud, web, claude);
    updateModelHint();
  } catch (e) {
    // 连不上后端时静默，保留手动输入
  }
}

// ---------- 默认启动模型 ----------
function getDefaultModelPref() {
  try { return JSON.parse(localStorage.getItem("cx_default_model") || "null"); }
  catch (_) { return null; }
}
function setDefaultModelPref(pref) {
  try { localStorage.setItem("cx_default_model", JSON.stringify(pref)); } catch (_) {}
}
function populateDefaultModelSelect(models, cloud, web, claude) {
  const sel = document.getElementById("defaultModelSelect");
  if (!sel) return;
  const pref = getDefaultModelPref();
  const wantVal = pref ? (pref.use_local ? "local::" + pref.model
    : (pref.model === "web" ? "web" : "cloud::" + pref.model)) : "__follow__";
  sel.innerHTML = "";
  const addOpt = (group, value, label, selected) => {
    const opt = document.createElement("option");
    opt.value = value; opt.textContent = label;
    if (selected) opt.selected = true;
    (group || sel).appendChild(opt);
  };
  addOpt(sel, "__follow__", "跟随上次（不固定）", wantVal === "__follow__");
  if ((models || []).length) {
    const g = document.createElement("optgroup"); g.label = "本地模型";
    models.forEach((m) => addOpt(g, "local::" + m, m, wantVal === "local::" + m));
    sel.appendChild(g);
  }
  if ((cloud || []).length) {
    const g = document.createElement("optgroup"); g.label = "☁ 云端模型";
    cloud.forEach((m) => addOpt(g, "cloud::" + m, "☁ " + m, wantVal === "cloud::" + m));
    sel.appendChild(g);
  }
  if ((web || []).length) {
    const g = document.createElement("optgroup"); g.label = "☁☁ 网页模型";
    web.forEach((m) => addOpt(g, "web", "☁☁ " + (m.name || "网页模型"), wantVal === "web"));
    sel.appendChild(g);
  }
}
// 把默认模型选择应用到当前（启动时调用一次）
function applyDefaultModelOnStartup() {
  const pref = getDefaultModelPref();
  if (!pref) return;   // 没设默认就跟随上次
  try {
    const useLocalEl = document.getElementById("useLocal");
    if (useLocalEl) useLocalEl.checked = !!pref.use_local;
    // 通过自绘 composer 下拉同步（如果可用），否则直接设 select
    if (typeof syncComposerModel === "function" && pref.model) {
      syncComposerModel(!!pref.use_local, pref.model);
    }
    const sel = document.getElementById("modelSelect");
    if (sel && pref.model && pref.model !== "web") {
      for (const o of sel.options) { if (o.value === pref.model) { o.selected = true; break; } }
    }
    if (typeof updateModelHint === "function") updateModelHint();
  } catch (_) {}
}
document.getElementById("defaultModelSelect")?.addEventListener("change", (e) => {
  const v = e.target.value;
  if (v === "__follow__") { setDefaultModelPref(null); return; }
  if (v === "web") { setDefaultModelPref({ use_local: false, model: "web" }); return; }
  if (v.startsWith("local::")) { setDefaultModelPref({ use_local: true, model: v.slice(7) }); return; }
  if (v.startsWith("cloud::")) { setDefaultModelPref({ use_local: false, model: v.slice(7) }); return; }
});
document.getElementById("setDefaultNowBtn")?.addEventListener("click", () => {
  const s = settings();
  setDefaultModelPref({ use_local: s.use_local, model: s.model });
  // 刷新默认下拉的选中态
  const sel = document.getElementById("defaultModelSelect");
  if (sel) {
    const wantVal = s.use_local ? "local::" + s.model : (s.model === "web" ? "web" : "cloud::" + s.model);
    for (const o of sel.options) { if (o.value === wantVal) { o.selected = true; break; } }
  }
  const st = document.getElementById("defaultModelSelect");
  if (st) { const old = st.title; st.title = "已设为默认"; setTimeout(() => st.title = old, 1500); }
});

// ===== 输入框里的「随时切换模型」自绘下拉（仿 Claude） =====
function currentComposerValue() {
  // web -> "web"；本地 -> "local::模型名"；云端 -> "cloud::模型名"
  return _entryToValue(settings());
}

// 哪些算"常用/最厉害"——按这个优先级把模型排到第一层，其余收进「更多模型」
const _PREFERRED = ["deepseek", "qwen", "llama", "gemma", "mistral", "qwq", "phi", "yi", "glm", "command"];
function _rank(name) {
  const base = String(name || "").split(":")[0].toLowerCase();
  for (let i = 0; i < _PREFERRED.length; i++) if (base.includes(_PREFERRED[i])) return i;
  return 99;
}

let _modelEntries = [];   // 全部 {value,label} 备用（用来显示当前模型名）

function buildComposerModel(models, cloud, web, claude) {
  const menu = document.getElementById("modelPickerMenu");
  if (!menu) return;
  const local = (models || []).map((m) => ({ value: "local::" + m, label: m, rank: _rank(m) }));
  const cld = (cloud || []).map((m) => ({ value: "cloud::" + m, label: "☁ " + m, rank: _rank(m) + 20 }));
  const webItems = (web || []).map((m) => ({ value: "web", label: "🌐 " + (m.name || "网页模型"), rank: -1 }));
  const claudeItems = (claude || []).map((m) => ({ value: m.id || "claude", label: "✦ " + (m.name || "Claude"), rank: -2 }));
  _modelEntries = [...claudeItems, ...webItems, ...local, ...cld];

  // 第一层：Claude + 网页大模型 + 最多 4 个最优先的本地/云端模型；其余进「更多模型」
  const ranked = [...local, ...cld].sort((a, b) => a.rank - b.rank);
  const top = [...claudeItems, ...webItems, ...ranked.slice(0, 4)];
  const more = ranked.slice(4);

  menu.innerHTML = "";
  const want = currentComposerValue();

  const makeItem = (e) => {
    const it = document.createElement("div");
    it.className = "mp-item" + (e.value === want ? " active" : "");
    it.dataset.value = e.value;
    const name = document.createElement("span");
    name.className = "mp-name"; name.textContent = e.label;
    const ck = document.createElement("span");
    ck.className = "mp-check"; ck.textContent = "✓";
    it.appendChild(name); it.appendChild(ck);
    it.addEventListener("click", () => { applyComposerModel(e.value); closeModelMenu(); });
    return it;
  };

  if (!_modelEntries.length) {
    const empty = document.createElement("div");
    empty.className = "mp-group-label"; empty.textContent = "（没检测到模型，去设置里看看）";
    menu.appendChild(empty);
  } else {
    const lab = document.createElement("div");
    lab.className = "mp-group-label"; lab.textContent = "常用模型";
    menu.appendChild(lab);
    top.forEach((e) => menu.appendChild(makeItem(e)));

    if (more.length) {
      const toggle = document.createElement("div");
      toggle.className = "mp-more-toggle";
      const collapsed = () => "更多模型 (" + more.length + ") ▾";
      toggle.textContent = collapsed();
      const moreBox = document.createElement("div");
      moreBox.className = "mp-more"; moreBox.hidden = true;
      more.forEach((e) => moreBox.appendChild(makeItem(e)));
      toggle.addEventListener("click", () => {
        moreBox.hidden = !moreBox.hidden;
        toggle.textContent = moreBox.hidden ? collapsed() : "收起 ▴";
      });
      menu.appendChild(toggle);
      menu.appendChild(moreBox);
    }
  }
  updateModelPickerLabel();
}

function updateModelPickerLabel() {
  const lab = document.getElementById("modelPickerLabel");
  if (!lab) return;
  const want = currentComposerValue();
  const found = _modelEntries.find((e) => e.value === want);
  lab.textContent = found ? found.label : (settings().model || "选择模型");
}

function openModelMenu() {
  const menu = document.getElementById("modelPickerMenu");
  if (!menu) return;
  const want = currentComposerValue();
  menu.querySelectorAll(".mp-item").forEach((it) => {
    it.classList.toggle("active", it.dataset.value === want);
  });
  menu.hidden = false;
}
function closeModelMenu() {
  const menu = document.getElementById("modelPickerMenu");
  if (menu) menu.hidden = true;
}
function toggleModelMenu() {
  const menu = document.getElementById("modelPickerMenu");
  if (!menu) return;
  if (menu.hidden) openModelMenu(); else closeModelMenu();
}

// 程序化地把聊天框 + 右上角的「当前模型」同步成指定模型（用于功能强制用某个模型时）
function syncComposerModel(use_local, model) {
  try {
    const value = _entryToValue({ use_local: !!use_local, model: model || "" });
    applyComposerModel(value);
  } catch (_) {}
}

// 从下拉切换模型：写回设置里的「本地/云端开关 + 模型」，让全局都用上
function applyComposerModel(value) {
  const entry = _valueToEntry(value);
  if (entry.follow_default) return;
  const useLocal = document.getElementById("useLocal");
  const sel = document.getElementById("modelSelect");
  const manual = document.getElementById("modelName");
  if (useLocal) useLocal.checked = !!entry.use_local;
  let inSelect = false;
  if (sel) for (const opt of sel.options) if (opt.value === entry.model) { inSelect = true; break; }
  if (inSelect) {
    if (manual) manual.style.display = "none";
    sel.style.display = ""; sel.value = entry.model;
  } else if (manual) {
    manual.value = entry.model; manual.style.display = "";
    if (sel) sel.style.display = "none";
  }
  updateModelHint();
  scheduleEnvRecheck();
}

document.getElementById("modelPickerBtn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleModelMenu();
});
document.addEventListener("click", (e) => {
  const picker = document.getElementById("modelPicker");
  if (picker && !picker.contains(e.target)) closeModelMenu();
});

document.getElementById("refreshModelsBtn")?.addEventListener("click", () => loadModels());

document.getElementById("manualModelBtn")?.addEventListener("click", () => {
  const manual = document.getElementById("modelName");
  const sel = document.getElementById("modelSelect");
  const btn = document.getElementById("manualModelBtn");
  if (manual.style.display === "none") {
    manual.style.display = "";
    sel.style.display = "none";
    btn.textContent = "用下拉";
    manual.focus();
  } else {
    manual.style.display = "none";
    sel.style.display = "";
    btn.textContent = "手动输入";
  }
  updateModelHint();
});

// ---------- 网页大模型（伪模型）配置 ----------
async function loadWebModelConfig() {
  try {
    const r = await fetch(BACKEND + "/web_model/config");
    const data = await r.json();
    const c = data.config || {};
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ""; };
    set("wmUser", c.aiUsername);
    set("wmPass", c.aiPassword === "***" ? "" : "");   // 已设密码留空，占位提示
    const pass = document.getElementById("wmPass");
    if (pass) pass.placeholder = c.aiPassword === "***" ? "已保存（留空＝不修改）" : "密码";
    const hf = document.getElementById("wmHeadful");
    if (hf) hf.checked = c.headless === false;          // headless=false ⇒ 显示窗口
    const sw = document.getElementById("wmSearch");
    if (sw) sw.checked = !!c.enableSearch;
    const hint = document.getElementById("wmHint");
    if (hint && !data.available) {
      hint.textContent = "⚠ 未检测到 Playwright，请先安装：pip install playwright && python -m playwright install chromium";
      hint.style.color = "var(--accent)";
    } else if (hint) {
      hint.textContent = "";
    }
  } catch (e) { /* 后端没起来时静默 */ }
}

async function saveWebModelConfig() {
  const hint = document.getElementById("wmHint");
  const body = {
    aiUsername: document.getElementById("wmUser").value.trim(),
    headless: !document.getElementById("wmHeadful").checked,   // 不显示窗口 ⇒ headless=true
    enableSearch: document.getElementById("wmSearch").checked,
  };
  const pass = document.getElementById("wmPass").value;
  if (pass) body.aiPassword = pass;     // 留空＝不修改
  try {
    const r = await fetch(BACKEND + "/web_model/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (hint) {
      hint.textContent = data.ok ? "✓ 已保存网页模型配置" : ("保存失败：" + (data.error || ""));
      hint.style.color = data.ok ? "var(--text-dim)" : "var(--accent)";
    }
    const p = document.getElementById("wmPass");
    if (p) { p.value = ""; p.placeholder = "已保存（留空＝不修改）"; }
  } catch (e) {
    if (hint) { hint.textContent = "保存失败：" + e.message; hint.style.color = "var(--accent)"; }
  }
}

async function testWebModel() {
  const hint = document.getElementById("wmHint");
  const btn = document.getElementById("wmTestBtn");
  if (hint) { hint.textContent = "正在测试：弹出浏览器→登录→选卡→发送测试…（首次较慢，请稍候）"; hint.style.color = "var(--text-dim)"; }
  if (btn) btn.disabled = true;
  try {
    await saveWebModelConfig();   // 先存一遍，确保用最新账号测
    const r = await fetch(BACKEND + "/web_model/test", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: "wmtest" + Date.now() }),
    });
    const data = await r.json();
    if (hint) {
      if (data.ok) {
        hint.textContent = "✓ 测试成功，网页模型已就绪。AI 回复：" + (data.reply || "");
        hint.style.color = "var(--text-dim)";
      } else {
        hint.textContent = "✗ 测试失败：" + (data.error || "未知问题");
        hint.style.color = "var(--accent)";
      }
    }
  } catch (e) {
    if (hint) { hint.textContent = "✗ 测试失败：" + e.message; hint.style.color = "var(--accent)"; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

document.getElementById("wmSaveBtn")?.addEventListener("click", saveWebModelConfig);
document.getElementById("wmTestBtn")?.addEventListener("click", testWebModel);

// ---------- 各任务用哪个模型 ----------
const _TASK_IDS = ["chat", "video_summary", "local_action", "quick_chat"];

// 把一个 task_models 条目编码成下拉的 value
function _entryToValue(entry) {
  if (!entry || entry.follow_default) return "follow";
  if (entry.model === "web") return "web";
  if (entry.model === "claude" || (entry.model && entry.model.startsWith("claude::"))) return entry.model;
  return (entry.use_local ? "local::" : "cloud::") + (entry.model || "");
}
// 把下拉 value 解码回 task_models 条目
function _valueToEntry(v) {
  if (v === "follow") return { follow_default: true };
  if (v === "web") return { use_local: false, model: "web" };
  if (v === "claude" || v.startsWith("claude::")) return { use_local: false, model: v };
  if (v.startsWith("local::")) return { use_local: true, model: v.slice(7) };
  if (v.startsWith("cloud::")) return { use_local: false, model: v.slice(7) };
  return { follow_default: true };
}

function _fillTaskSelect(sel, modelsData, opts) {
  const includeFollow = opts.includeFollow !== false;
  const localOnly = !!opts.localOnly;
  const selected = opts.selectedValue || "follow";
  sel.innerHTML = "";
  const add = (val, label) => {
    const o = document.createElement("option");
    o.value = val; o.textContent = label;
    if (val === selected) o.selected = true;
    sel.appendChild(o);
  };
  if (includeFollow) add("follow", "跟随默认");
  (modelsData.models || []).forEach((m) => add("local::" + m, m));
  if (!localOnly) {
    (modelsData.cloud || []).forEach((m) => add("cloud::" + m, "☁ " + m));
    (modelsData.web || []).forEach((m) => add("web", "☁☁ " + (m.name || "网页模型")));
  }
}

async function loadTaskModels() {
  try {
    const [mr, tr] = await Promise.all([
      fetch(BACKEND + "/models").then((r) => r.json()),
      fetch(BACKEND + "/task_models").then((r) => r.json()),
    ]);
    const tm = tr.task_models || {};
    const def = document.getElementById("tmDefault");
    if (def) _fillTaskSelect(def, mr, {
      includeFollow: false, selectedValue: _entryToValue(tm.default || { use_local: false, model: "web" }),
    });
    _TASK_IDS.forEach((t) => {
      const sel = document.getElementById("tm_" + t);
      if (!sel) return;
      _fillTaskSelect(sel, mr, {
        includeFollow: true,
        localOnly: t === "local_action",
        selectedValue: _entryToValue(tm[t]),
      });
    });
  } catch (e) { /* 静默 */ }
}

async function saveTaskModels() {
  const hint = document.getElementById("tmHint");
  const out = {};
  const def = document.getElementById("tmDefault");
  if (def) out.default = _valueToEntry(def.value);
  _TASK_IDS.forEach((t) => {
    const sel = document.getElementById("tm_" + t);
    if (sel) out[t] = _valueToEntry(sel.value);
  });
  try {
    const r = await fetch(BACKEND + "/task_models", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_models: out }),
    });
    const data = await r.json();
    if (hint) {
      hint.textContent = data.ok ? "✓ 已保存任务配置" : ("保存失败：" + (data.error || ""));
      hint.style.color = data.ok ? "var(--text-dim)" : "var(--accent)";
    }
  } catch (e) {
    if (hint) { hint.textContent = "保存失败：" + e.message; hint.style.color = "var(--accent)"; }
  }
}

document.getElementById("tmSaveBtn")?.addEventListener("click", saveTaskModels);

// ---------- 环境检查（启动时自动跑一次）----------
async function runEnvCheck(silent) {
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/env_check", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    if (!data.ok && !silent) {
      // 有问题时在对话区提示
      const bad = (data.items || []).filter((i) => !i.ok);
      const msg = "⚠️ 运行环境检查发现问题：\n" +
        bad.map((i) => `· ${i.name}：${i.detail}`).join("\n");
      addSystemNote(msg);
    }
    // 状态行也更新一下
    const line = document.getElementById("statusLine");
    if (line) {
      line.textContent = data.ok ? "环境就绪" : "环境有问题（看对话提示）";
      line.style.color = data.ok ? "var(--text-dim)" : "var(--accent)";
    }
    setStatusDot(!!data.ok);   // 右上角亮点：绿=正常，红=不正常
    return data.ok;
  } catch (e) {
    setStatusDot(false);
    return false;
  }
}

// 启动
initBackend().then(() => {
  updateModelHint();
  loadModels("qwen3:14b").then(() => { applyDefaultModelOnStartup(); });
  // 等后端起来再检查环境（延迟一下，给 Ollama 自启动留时间）
  setTimeout(() => runEnvCheck(false), 2000);
});
newConversation();  // 开一个初始会话

// ============================================================
//  电脑操作权限开关 · 语音输入 · 语音播报 · + 菜单（2026-06 新增）
// ============================================================
(function () {
  // ---------- 「+」更多菜单（结束并记住挪进来）----------
  const plusBtn = document.getElementById("plusBtn");
  const plusPop = document.getElementById("plusPop");
  if (plusBtn && plusPop) {
    plusBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      plusPop.hidden = !plusPop.hidden;
    });
    document.addEventListener("click", (e) => {
      if (!plusPop.hidden && !e.target.closest("#plusMenu")) plusPop.hidden = true;
    });
    // 点菜单里的项后顺手收起菜单（rememberBtn 自己的处理逻辑仍在原处生效）
    plusPop.addEventListener("click", () => { plusPop.hidden = true; });
  }

  // ---------- 语音输入（麦克风，Claude 风格图标已在 HTML 里）----------
  const micBtn = document.getElementById("micBtn");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (micBtn) {
    if (!SR) {
      micBtn.title = "当前环境不支持语音输入";
      micBtn.disabled = true;
    } else {
      let rec = null, on = false;
      micBtn.addEventListener("click", () => {
        if (on && rec) { rec.stop(); return; }
        try {
          rec = new SR();
          rec.lang = "zh-CN";
          rec.interimResults = false;
          rec.continuous = false;
          rec.onresult = (e) => {
            let s = "";
            for (let i = 0; i < e.results.length; i++) s += e.results[i][0].transcript;
            inputEl.value = (inputEl.value ? inputEl.value + " " : "") + s;
            inputEl.dispatchEvent(new Event("input", { bubbles: true }));
            inputEl.focus();
          };
          rec.onerror = () => { /* 安静失败 */ };
          rec.onend = () => { on = false; micBtn.classList.remove("recording"); };
          rec.start();
          on = true;
          micBtn.classList.add("recording");
        } catch (_) { /* ignore */ }
      });
    }
  }

  // ---------- 语音播报（神经网络 TTS，分段边读边取，可随时打断）----------
  // 关键设计：
  //  · cxGen 代号：每次开始/停止都自增；任何“在飞”的请求或排队回调发现代号变了就作废，
  //    彻底杜绝“点两次 → 两个声音一起读”。
  //  · 长文章按句子切成小段，第一段很短 → 秒出声；播放当前段的同时预取下一段。
  //  · 停止/换一段会 abort 在途请求并暂停当前音频，反应即时。
  let cxGen = 0;            // 当前播放代号
  let cxAbort = null;       // 在途 fetch 控制器
  let cxAudioEl = null;     // 当前 Audio
  let cxBtn = null;         // 当前朗读按钮（用于高亮/再点停止）

  function cxStop() {
    cxGen++;                                   // 让所有旧回调失效
    if (cxAbort) { try { cxAbort.abort(); } catch (_) {} cxAbort = null; }
    if (cxAudioEl) { try { cxAudioEl.pause(); } catch (_) {} cxAudioEl = null; }
    try { window.speechSynthesis && speechSynthesis.cancel(); } catch (_) {}
    if (cxBtn) { cxBtn.classList.remove("speaking", "loading"); cxBtn = null; }
  }
  function curVoice() {
    try { return localStorage.getItem("cx_tts_voice") || "zh-CN-YunxiNeural"; }
    catch (_) { return "zh-CN-YunxiNeural"; }
  }
  function curEngine() {
    try { return localStorage.getItem("cx_tts_engine") || "online"; }
    catch (_) { return "online"; }
  }

  // 把长文本按句子/标点切成 ≤180 字的小段，便于快速合成、即时开口
  function splitForTTS(text) {
    const clean = (text || "").replace(/\s+/g, " ").trim();
    if (!clean) return [];
    // 关键提速：把「第一段」切得很短（首句、最多 ~40 字），
    // 这样 edge-tts 几乎瞬间就能合成出第一段、声音 1 秒内就响；
    // 后面的内容在播第一段时已经在后台预取，听感上几乎无延迟。
    const chunks = [];
    let rest = clean;
    // 先尽量按句末标点取出"第一句"
    let firstCut = -1;
    const m = rest.slice(0, 60).match(/[。！？!?；;，,、]/);
    if (m) firstCut = m.index + 1;
    if (firstCut < 0) firstCut = Math.min(40, rest.length);   // 没标点就硬切 40 字
    if (firstCut > 45) firstCut = 45;                          // 第一段别超 45 字
    chunks.push(rest.slice(0, firstCut).trim());
    rest = rest.slice(firstCut).trim();
    if (!rest) return chunks;
    // 剩下的按原逻辑分段（每段 ~180 字，句末优先）
    const parts = rest.split(/(?<=[。！？!?；;])/);
    let cur = "";
    for (let p of parts) {
      while (p.length > 220) { if (cur) { chunks.push(cur); cur = ""; } chunks.push(p.slice(0, 220)); p = p.slice(220); }
      if ((cur + p).length > 180) { if (cur) chunks.push(cur); cur = p; }
      else cur += p;
    }
    if (cur.trim()) chunks.push(cur);
    return chunks.slice(0, 80);   // 极长文章兜底，最多 80 段
  }

  async function ttsFetch(text, gen) {
    cxAbort = new AbortController();
    const resp = await fetch(BACKEND + "/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: curVoice() }),
      signal: cxAbort.signal,
    });
    if (gen !== cxGen) return null;            // 已被新播放/停止取代
    const ct = resp.headers.get("Content-Type") || "";
    if (!resp.ok || ct.indexOf("audio") < 0) throw new Error("no-audio");
    return await resp.blob();
  }

  function playBlob(blob, gen, btn) {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      cxAudioEl = a;
      if (btn) { btn.classList.remove("loading"); btn.classList.add("speaking"); }
      const done = () => { URL.revokeObjectURL(url); resolve(); };
      a.onended = done;
      a.onerror = done;
      a.play().catch(done);
    });
  }

  function fallbackSpeak(text, btn) {
    try {
      if (!window.speechSynthesis) { cxStop(); return; }
      const u = new SpeechSynthesisUtterance(text);
      const isEn = /^en-/.test(curVoice());
      u.lang = isEn ? "en-US" : "zh-CN";
      const vs = speechSynthesis.getVoices() || [];
      const want = vs.find((v) => (isEn ? /en/i : /zh|cn|chinese/i).test(v.lang + v.name));
      if (want) u.voice = want;
      u.onend = () => cxStop();
      u.onerror = () => cxStop();
      if (btn) { btn.classList.remove("loading"); btn.classList.add("speaking"); }
      speechSynthesis.speak(u);
    } catch (_) { cxStop(); }
  }

  async function cxSpeak(text, btn) {
    text = (text || "").trim();
    if (cxBtn === btn) { cxStop(); return; }   // 对同一个按钮再点一次＝停止
    cxStop();                                  // 先把上一段彻底停掉（含在途请求）
    if (!text) return;
    const gen = ++cxGen;                        // 本次播放的代号
    cxBtn = btn || null;
    if (cxBtn) cxBtn.classList.add("loading");
    // 本地·极速：直接用浏览器/系统语音，瞬间出声、不连网
    if (curEngine() === "local") { fallbackSpeak(text, btn); return; }
    const chunks = splitForTTS(text);
    try {
      let nextP = ttsFetch(chunks[0], gen);     // 预取第一段
      for (let i = 0; i < chunks.length; i++) {
        const blob = await nextP;
        if (gen !== cxGen) return;              // 被打断
        if (!blob) return;                      // 代号失效
        nextP = (i + 1 < chunks.length) ? ttsFetch(chunks[i + 1], gen).catch(() => null) : null;  // 边播边预取下一段（自吞中断）
        await playBlob(blob, gen, btn);
        if (gen !== cxGen) return;
      }
      if (gen === cxGen) cxStop();              // 全部读完，复位
    } catch (e) {
      if (gen === cxGen) fallbackSpeak(text, btn);  // 后端不可用/离线 → 退浏览器语音（整段）
    }
  }
  window.cxSpeak = cxSpeak;

  // 事件委托：任何 .speak-btn（含会话快照恢复出来的）点击都朗读其所在气泡
  messagesEl.addEventListener("click", (e) => {
    const b = e.target.closest(".speak-btn");
    if (!b) return;
    const bub = b.closest(".msg") && b.closest(".msg").querySelector(".bubble");
    const txt = bub ? (bub.dataset.raw || bub.textContent || "") : "";
    cxSpeak(txt, b);
  });

  // ---------- 语音音色选择 + 试听 ----------
  const voiceSel = document.getElementById("ttsVoice");
  if (voiceSel) {
    try {
      const saved = localStorage.getItem("cx_tts_voice");
      if (saved) voiceSel.value = saved;
    } catch (_) {}
    voiceSel.addEventListener("change", () => {
      try { localStorage.setItem("cx_tts_voice", voiceSel.value); } catch (_) {}
    });
  }
  const engineSel = document.getElementById("ttsEngine");
  if (engineSel) {
    try { const s = localStorage.getItem("cx_tts_engine"); if (s) engineSel.value = s; } catch (_) {}
    engineSel.addEventListener("change", () => {
      try { localStorage.setItem("cx_tts_engine", engineSel.value); } catch (_) {}
    });
  }
  const ttsTest = document.getElementById("ttsTestBtn");
  if (ttsTest) {
    ttsTest.addEventListener("click", () =>
      cxSpeak("你好，我是超能小助，这是当前选择的语音音色。", ttsTest));
  }

  // ---------- 电脑操作权限开关（设置页）----------
  const accessChk = document.getElementById("systemAccess");
  async function loadAccess() {
    if (!accessChk) return;
    try {
      const r = await fetch(BACKEND + "/system_access");
      const d = await r.json();
      accessChk.checked = !!d.enabled;
    } catch (_) {}
  }
  if (accessChk) {
    loadAccess();
    accessChk.addEventListener("change", async () => {
      const want = accessChk.checked;
      if (want) {
        const ok = window.confirm(
          "开启「电脑操作权限」后，超能小助将能：\n"
          + "· 读写 / 移动 / 删除你真实的桌面、下载、任意目录文件\n"
          + "· 调系统设置、看进程、清理磁盘、调音量亮度\n"
          + "· 打开并操作其它程序、看你的屏幕\n\n"
          + "每个破坏性动作执行前仍会单独弹窗让你确认。确定开启？");
        if (!ok) { accessChk.checked = false; return; }
      }
      try {
        await fetch(BACKEND + "/system_access", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: want }),
        });
      } catch (_) {}
    });
  }
  // 每次切到「设置」页时同步一次开关真实状态
  document.querySelectorAll('.nav-item[data-view="settings"]').forEach((b) =>
    b.addEventListener("click", loadAccess));

  // ---------- 「电脑操作权限」说明弹窗（ⓘ）----------
  const accessInfo = document.getElementById("accessInfoBtn");
  if (accessInfo) {
    accessInfo.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      showAccessModal();
    });
  }
  function showAccessModal() {
    if (document.getElementById("cxAccessModal")) return;
    const mask = document.createElement("div");
    mask.id = "cxAccessModal";
    mask.className = "cx-modal-mask";
    mask.innerHTML =
      '<div class="cx-modal">' +
      '  <div class="cx-modal-head">🖥️ 电脑操作权限是干什么的？</div>' +
      '  <div class="cx-modal-body">' +
      '    <p>这是一个总开关。<b>开启后</b>，超能小助就从“只会聊天的助手”变成能真正帮你动手操作电脑的管家：</p>' +
      '    <ul>' +
      '      <li><b>整理文件</b>：打开 / 移动 / 重命名 / 删到回收站 / 一键归类乱糟糟的桌面、下载、任意目录。</li>' +
      '      <li><b>系统操作</b>：查看进程并结束卡死程序、清理临时文件释放磁盘、调音量亮度、打开系统设置。</li>' +
      '      <li><b>操作其它程序</b>：打开某个软件，并在里面点按钮、输入文字、按快捷键。</li>' +
      '      <li><b>看屏幕</b>：截屏并识别屏幕上的文字，看懂你当前在做什么再帮你操作。</li>' +
      '    </ul>' +
      '    <p><b>关闭后</b>（默认）：以上能力全部冻结，它只能在自己的沙箱目录里活动，碰不到你真实的文件和系统——安全第一。</p>' +
      '    <p class="cx-modal-tip">🔐 即使开着，每个有破坏性的动作（移动/删除/结束进程/清磁盘/点鼠标等）执行前，都会单独弹窗让你确认，AI 绕不过去。</p>' +
      '  </div>' +
      '  <div class="cx-modal-foot"><button class="send-btn" id="cxAccessClose">我知道了</button></div>' +
      '</div>';
    document.body.appendChild(mask);
    const close = () => mask.remove();
    mask.addEventListener("click", (ev) => { if (ev.target === mask) close(); });
    mask.querySelector("#cxAccessClose").addEventListener("click", close);
  }
})();

// ============================================================
//  Claude 模型管理（多配置）—— 每个配置有独立的 key、地址、模型名
// ============================================================
(function () {
  const listEl = document.getElementById("claudeProfileList");
  const hintEl = document.getElementById("claudeHint");
  const addBtn = document.getElementById("claudeAddBtn");
  const preferChk = document.getElementById("claudePreferWeb");
  if (!listEl) return;

  function renderProfiles(profiles) {
    listEl.innerHTML = "";
    if (!profiles || !profiles.length) {
      listEl.innerHTML = '<div style="color:var(--text-secondary);padding:12px 0">还没有配置，点击下方「添加」按钮创建。</div>';
      return;
    }
    profiles.forEach((p, i) => {
      const card = document.createElement("div");
      card.className = "claude-profile-card";
      card.innerHTML = `
        <div class="cpf-header">
          <span class="cpf-name">${_esc(p.name || "未命名")}</span>
          <span class="cpf-model">${_esc(p.model)}</span>
          <span class="cpf-status">${p.configured ? "✓ 已配置" : "✗ 未配置 key"}</span>
        </div>
        <div class="cpf-details" hidden>
          <div class="cpf-row"><label>名称</label><input type="text" class="text-input cpf-input" data-field="name" value="${_esc(p.name || "")}" placeholder="如：Claude Opus" /></div>
          <div class="cpf-row"><label>地址</label><input type="text" class="text-input cpf-input" data-field="base_url" value="${_esc(p.base_url || "")}" placeholder="如 https://api.dakeai.cc" /></div>
          <div class="cpf-row"><label>密钥</label><input type="password" class="text-input cpf-input" data-field="api_key" value="" placeholder="${p.configured ? "已保存（留空＝不修改）" : "粘贴你的 API Key"}" /></div>
          <div class="cpf-row"><label>模型</label><input type="text" class="text-input cpf-input" data-field="model" value="${_esc(p.model || "")}" placeholder="如 claude-opus-4-8" /></div>
          <div class="cpf-actions">
            <button class="send-btn cpf-save" data-idx="${i}">保存</button>
            <button class="send-btn cpf-delete" data-idx="${i}" style="background:var(--accent)">删除</button>
          </div>
        </div>`;
      card.querySelector(".cpf-header").addEventListener("click", () => {
        const det = card.querySelector(".cpf-details");
        det.hidden = !det.hidden;
      });
      card.querySelector(".cpf-save").addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const idx = parseInt(ev.target.dataset.idx);
        const profile = {};
        card.querySelectorAll(".cpf-input").forEach((inp) => {
          const f = inp.dataset.field;
          const v = inp.value.trim();
          if (f === "api_key" && !v) return;
          profile[f] = v;
        });
        await claudeAction("update", { index: idx, profile });
      });
      card.querySelector(".cpf-delete").addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!confirm("确定删除这个配置吗？")) return;
        await claudeAction("delete", { index: parseInt(ev.target.dataset.idx) });
      });
      listEl.appendChild(card);
    });
  }

  function _esc(s) { return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

  async function claudeAction(action, extra) {
    if (hintEl) hintEl.textContent = "处理中…";
    try {
      const r = await fetch(BACKEND + "/claude_config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...extra }),
      });
      const d = await r.json();
      if (d.ok) {
        if (hintEl) hintEl.textContent = "操作成功";
        renderProfiles(d.profiles || []);
        if (typeof loadModels === "function") loadModels();
      } else {
        if (hintEl) hintEl.textContent = "失败：" + (d.error || "未知");
      }
    } catch (e) {
      if (hintEl) hintEl.textContent = "出错：" + e.message;
    }
  }

  async function loadClaudeConfig() {
    try {
      const r = await fetch(BACKEND + "/claude_config");
      const d = await r.json();
      renderProfiles(d.profiles || []);
      if (preferChk) preferChk.checked = !!d.prefer_over_web;
    } catch (_) {}
  }

  if (preferChk) preferChk.addEventListener("change", async () => {
    if (hintEl) hintEl.textContent = "保存中…";
    try {
      const r = await fetch(BACKEND + "/claude_config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set_pref", prefer_over_web: preferChk.checked }),
      });
      const d = await r.json();
      if (hintEl) hintEl.textContent = d.ok
        ? (preferChk.checked
            ? "已开启：分析/搜索/总结等任务将改用 Claude，不再走网页模型。"
            : "已关闭：这些任务会按原设置（可能用网页模型）。")
        : "保存失败：" + (d.error || "未知");
    } catch (e) {
      if (hintEl) hintEl.textContent = "出错：" + e.message;
    }
  });

  if (addBtn) addBtn.addEventListener("click", async () => {
    await claudeAction("add", { profile: { name: "", base_url: "", api_key: "", model: "" } });
  });

  document.querySelectorAll('.nav-item[data-view="settings"]').forEach((b) =>
    b.addEventListener("click", loadClaudeConfig));
  loadClaudeConfig();
})();

// ===== 笔记截图：点击放大查看（轻量灯箱，事件委托，动态渲染也生效）=====
(function setupImgLightbox() {
  let overlay = null;
  function close() {
    if (overlay) { overlay.remove(); overlay = null; }
  }
  document.addEventListener("click", (e) => {
    const img = e.target.closest && e.target.closest("img.md-img");
    if (!img) return;
    e.preventDefault();
    close();
    overlay = document.createElement("div");
    overlay.className = "img-lightbox";
    const big = document.createElement("img");
    big.src = img.src;
    overlay.appendChild(big);
    overlay.addEventListener("click", close);
    document.body.appendChild(overlay);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
})();

// ===== 「懂你」面板（lumi_features）=====
let _lumiData = { profile: "", relationships: "", environment: "", evolution_log: "" };
async function loadLumi() {
  const profEl0 = document.getElementById("lumiProfile");
  const relEl0  = document.getElementById("lumiRelations");
  const envEl0  = document.getElementById("lumiEnv");
  // 失败/异常时用它把「加载中…」换成可重试提示，绝不留死占位
  const showFail = (msg) => {
    const html = '<div class="lumi-empty">' + escapeHtml(msg) +
      ' <a href="#" onclick="loadLumi();return false;" style="color:var(--accent)">点此重试</a></div>';
    [profEl0, relEl0, envEl0].forEach((el) => {
      if (el && /加载中/.test(el.textContent || "")) el.innerHTML = html;
    });
  };
  try {
    const r = await fetch(BACKEND + "/lumi/status");
    const d = await r.json();
    if (!d || !d.ok) { showFail("洞察数据暂时取不到。"); return; }
    _lumiData = d;
    const profEl = document.getElementById("lumiProfile");
    if (profEl) profEl.innerHTML = (d.profile || "").trim()
      ? renderProfileRich(d.profile)
      : '<div class="lumi-empty">还没生成。点下面「人格演化」里的「立即演化一次」，小助会从你的对话里总结出你的说话风格、关注点和偏好。</div>';
    const relEl = document.getElementById("lumiRelations");
    if (relEl) relEl.innerHTML = (d.relationships || "").trim()
      ? renderRelationsRich(d.relationships)
      : '<div class="lumi-empty">还没记录到人。聊天时提到具体的人（同事、朋友、客户…），小助会自动记下来。</div>';
    const envEl = document.getElementById("lumiEnv");
    if (envEl) envEl.innerHTML = (d.environment || "").trim()
      ? renderMarkdown(d.environment)
      : '<div class="lumi-empty">还没扫描。点本节右上角「🖥️ 扫描环境」，小助会看你装了什么软件、推断你的职业方向。</div>';
  } catch (e) {
    // 后端没起来/网络错：把「加载中…」换成可重试提示（后端就绪后探活也会自动再拉一次）
    showFail("洞察加载失败：" + (e && e.message ? e.message : "后端未就绪") + "。");
  }
}

// 把 relationships.md 解析成一组「人卡片」，比纯文本更直观
function renderRelationsRich(md) {
  const people = [];
  (md || "").split("\n").forEach((line) => {
    const m = line.trim().match(/^[-•]\s*([^:：]{1,20})[:：]\s*(.+)$/);
    if (m) people.push({ name: m[1].trim(), info: m[2].trim() });
  });
  if (!people.length) return renderMarkdown(md || "（还没记录到人）");
  let h = '<div class="rel-grid">';
  people.forEach((p) => {
    const initial = (p.name[0] || "?");
    h += '<div class="rel-card">' +
      '<div class="rel-avatar">' + escapeHtml(initial) + "</div>" +
      '<div class="rel-info">' +
        '<div class="rel-name">' + escapeHtml(p.name) + "</div>" +
        '<div class="rel-desc">' + escapeHtml(p.info) + "</div>" +
      "</div></div>";
  });
  h += "</div>";
  return h;
}

// 把画像 OWNER_PROFILE.md 渲染成 dashboard：左边大类目录、右边显示选中那类的详情。
// 长文（含表格、多级标题）也能顺读，不再是高低不齐的拼贴墙。
function renderProfileRich(md) {
  // 去掉顶部 # 标题和说明引语
  let body = (md || "").replace(/^#\s+.*$/m, "").replace(/^>.*$/gm, "").trim();
  // 解析 ##/### 分区
  const sections = [];
  let cur = null;
  let preface = [];   // 第一个标题之前的内容（如有）
  body.split("\n").forEach((ln) => {
    const m = ln.match(/^#{2,3}\s+(.+)$/);
    if (m) {
      if (cur) sections.push(cur);
      cur = { title: m[1].replace(/\*+/g, "").trim(), lines: [] };
    } else if (cur) {
      cur.lines.push(ln);
    } else if (ln.trim()) {
      preface.push(ln);
    }
  });
  if (cur) sections.push(cur);
  // 把开头无标题内容并成一项「概述」
  if (preface.join("").trim()) {
    sections.unshift({ title: "概述", lines: preface });
  }
  if (!sections.length) return '<div class="profile-dash-plain">' + renderMarkdown(md) + "</div>";

  // 给每项算一段预览（取正文第一句，作为左侧副标题）
  const preview = (lines) => {
    const txt = lines.join(" ").replace(/[#*>\-•|]/g, " ").replace(/\s+/g, " ").trim();
    return txt.slice(0, 32);
  };

  let nav = '<div class="profile-dash-nav">';
  let panes = '<div class="profile-dash-content">';
  sections.forEach((sec, i) => {
    const active = i === 0 ? " active" : "";
    nav += '<button class="profile-dash-item' + active + '" data-pidx="' + i + '">' +
      '<span class="profile-dash-texts"><span class="profile-dash-title">' + escapeHtml(sec.title) + '</span>' +
      '<span class="profile-dash-prev">' + escapeHtml(preview(sec.lines)) + '</span></span>' +
      '</button>';
    panes += '<div class="profile-dash-pane' + active + '" data-pidx="' + i + '">' +
      '<div class="profile-dash-pane-head">' + escapeHtml(sec.title) + '</div>' +
      '<div class="profile-dash-pane-body">' + renderMarkdown(sec.lines.join("\n").trim()) + '</div>' +
      '</div>';
  });
  nav += "</div>";
  panes += "</div>";
  return '<div class="profile-dash">' + nav + panes + "</div>";
}

// 画像 dashboard：左侧目录点击 → 右侧切换详情（事件委托，重渲染后依然有效）
document.addEventListener("click", (e) => {
  const item = e.target.closest && e.target.closest(".profile-dash-item");
  if (!item) return;
  const dash = item.closest(".profile-dash");
  if (!dash) return;
  const idx = item.dataset.pidx;
  dash.querySelectorAll(".profile-dash-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.pidx === idx));
  dash.querySelectorAll(".profile-dash-pane").forEach((p) =>
    p.classList.toggle("active", p.dataset.pidx === idx));
});

// 懂你顶栏按钮：按当前子页只显示用得上的那个（+ 通用刷新一直在）
function setLumiTopbarButtons(which) {
  const show = (id, on) => { const el = document.getElementById(id); if (el) el.style.display = on ? "" : "none"; };
  // 你的画像（含关系/环境）→ 扫描环境；洞察 → 立即分析；人格演化 → 无（页内自带按钮）
  show("lumiScanBtn", false);   // v110：环境画像挪到了「待开发」，扫描按钮跟着过去了
  show("crwRunBtn", which === "insight");
  show("lumiRefreshBtn", true);
}

// 懂你子菜单：切换各子页。关系/环境已并入「你的画像」，不再是独立页。
// renderer 只直接管 profile 页；洞察/演化由各自模块（crawler.js/evolution.js）补充显隐。
function switchLumiSub(which) {
  const sub = which;
  if (which === "evolution") which = "profile";   // v110：人格演化并进了画像页（画像下面接着显示）
  const map = { profile: "lumiPageProfile" };
  Object.entries(map).forEach(([k, id]) => {
    const pg = document.getElementById(id);
    if (pg) pg.style.display = (k === which) ? "" : "none";
  });
  // 切到非 profile 时，确保 profile 页隐藏（洞察/演化模块会显示自己的页）
  if (which !== "profile") {
    const pp = document.getElementById("lumiPageProfile");
    if (pp) pp.style.display = "none";
  }
  document.querySelectorAll("#lumiSubNav .nav-subitem").forEach((b) =>
    b.classList.toggle("active", b.dataset.lumi === sub));
  setLumiTopbarButtons(which);
}
document.querySelectorAll("#lumiSubNav .nav-subitem").forEach((b) => {
  b.addEventListener("click", () => {
    // 点（隐藏的）子菜单时：切到懂你视图，并高亮对应的那个一级懂你项（画像/洞察/人格）
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-lumi")?.classList.add("active");
    switchLumiSub(b.dataset.lumi);
    loadLumi();
    navSync("lumi", b.dataset.lumi);
  });
});

function setLumiStatus(msg, kind) {
  const el = document.getElementById("lumiStatus");
  if (!el) return;
  el.textContent = msg || "";
  el.className = "lumi-status" + (kind ? " " + kind : "");
}

// 「扫描环境」：顶栏按钮和画像页内联按钮共用这一套
async function runLumiScan(btnEl) {
  const s = settings();
  if (btnEl) btnEl.disabled = true;
  setLumiStatus("正在扫描本机环境…");
  try {
    const r = await fetch(BACKEND + "/lumi/scan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    let msg = d.message || (d.ok ? "扫描完成" : "扫描没成功");
    if (d.ok && d.professions && d.professions.length) msg += "（推断：" + d.professions.join("、") + "）";
    setLumiStatus(msg, d.ok ? "ok" : "warn");
    if (d.ok) { loadLumi(); switchLumiSub("profile"); }  // 环境画像现在在「你的画像」页内
  } catch (e) { setLumiStatus("出错：" + e.message, "warn"); }
  finally { if (btnEl) btnEl.disabled = false; }
}
document.getElementById("lumiScanBtn")?.addEventListener("click", (e) => runLumiScan(e.currentTarget));
// 画像页内的「扫描环境」内联按钮（事件委托，重渲染也有效）
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("#lumiScanInline");
  if (b) runLumiScan(b);
});

document.getElementById("lumiRefreshBtn")?.addEventListener("click", () => { setLumiStatus(""); loadLumi(); });

// ============================================================
// 技能（Skills）—— 工具区
// ============================================================
let _skillsCache = [];

async function loadSkills() {
  const grid = document.getElementById("skillsGrid");
  if (!grid) return;
  grid.innerHTML = '<div class="skills-empty">加载中…</div>';
  try {
    const r = await fetch(BACKEND + "/skills/list");
    const d = await r.json();
    _skillsCache = d.skills || [];
    renderSkillsGrid();
  } catch (e) {
    grid.innerHTML = '<div class="skills-empty">加载失败：' + escapeHtml(e.message) + "</div>";
  }
}

function renderSkillsGrid() {
  const grid = document.getElementById("skillsGrid");
  if (!grid) return;
  if (!_skillsCache.length) {
    grid.innerHTML = '<div class="skills-empty">还没有技能。点右上角「✏️ 新建技能」写一个，或保留内置的几课。</div>';
    return;
  }
  grid.innerHTML = _skillsCache.map((s) => {
    const on = s.enabled;
    const tag = s.builtin
      ? '<span class="skill-tag builtin">内置</span>'
      : '<span class="skill-tag custom">自建</span>';
    return (
      '<div class="skill-card' + (on ? "" : " off") + '" data-slug="' + escapeHtml(s.slug) + '">' +
        '<div class="skill-card-head">' +
          '<span class="skill-card-name">🧩 ' + escapeHtml(s.name) + "</span>" + tag +
        "</div>" +
        '<div class="skill-card-desc">' + escapeHtml(s.description || "（没写用途说明）") + "</div>" +
        '<div class="skill-card-foot">' +
          '<label class="skill-toggle" title="开启后，小助遇到匹配任务会自动用这个技能">' +
            '<input type="checkbox" class="skill-toggle-input"' + (on ? " checked" : "") + " /> " +
            "<span>" + (on ? "已开启" : "已关闭") + "</span>" +
          "</label>" +
          '<span class="skill-card-actions">' +
            '<button class="skill-mini-btn skill-open" title="查看/编辑">查看</button>' +
            (s.builtin ? "" : '<button class="skill-mini-btn skill-del" title="删除">删除</button>') +
          "</span>" +
        "</div>" +
      "</div>"
    );
  }).join("");

  grid.querySelectorAll(".skill-card").forEach((card) => {
    const slug = card.dataset.slug;
    card.querySelector(".skill-toggle-input")?.addEventListener("change", async (e) => {
      await toggleSkill(slug, e.target.checked);
    });
    card.querySelector(".skill-open")?.addEventListener("click", () => openSkillView(slug));
    card.querySelector(".skill-del")?.addEventListener("click", () => deleteSkill(slug));
  });
}

async function toggleSkill(slug, enabled) {
  try {
    await fetch(BACKEND + "/skills/toggle", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, enabled }),
    });
    const it = _skillsCache.find((x) => x.slug === slug);
    if (it) it.enabled = enabled;
    renderSkillsGrid();
  } catch (e) { /* 忽略 */ }
}

async function deleteSkill(slug) {
  if (!confirm("确定删除这个技能吗？删了就没了（内置技能删掉后，删对应文件夹再重启可恢复）。")) return;
  try {
    await fetch(BACKEND + "/skills/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug }),
    });
    loadSkills();
  } catch (e) { alert("删除失败：" + e.message); }
}

// —— 弹层：查看 / 编辑 / 新建 / 指南 ——
function openSkillModal(mode) {
  document.getElementById("skillModal").style.display = "flex";
  document.getElementById("skillEdit").style.display = mode === "edit" ? "" : "none";
  document.getElementById("skillView").style.display = mode === "view" ? "" : "none";
  document.getElementById("skillGuide").style.display = mode === "guide" ? "" : "none";
}
function closeSkillModal() {
  document.getElementById("skillModal").style.display = "none";
}

async function openSkillView(slug) {
  try {
    const r = await fetch(BACKEND + "/skills/get?slug=" + encodeURIComponent(slug));
    const d = await r.json();
    if (!d.skill) { alert("读取失败"); return; }
    const s = d.skill;
    document.getElementById("skillModalTitle").textContent = "🧩 " + (s.name || s.slug);
    const view = document.getElementById("skillView");
    view.innerHTML =
      '<div class="skill-view-desc"><b>什么时候用：</b>' + escapeHtml(s.description || "（未写）") + "</div>" +
      '<div class="skill-view-body">' + renderMarkdown(s.body || "") + "</div>" +
      '<div class="skill-view-actions">' +
        '<button class="send-btn" id="skillEditNowBtn">✏️ 编辑这个技能</button>' +
      "</div>";
    openSkillModal("view");
    document.getElementById("skillEditNowBtn")?.addEventListener("click", () => fillSkillEditor(s));
  } catch (e) { alert("读取失败：" + e.message); }
}

function fillSkillEditor(s, opts) {
  // s 为空表示新建；opts.draft 表示是从对话提炼来的草稿（slug 仍可改）
  opts = opts || {};
  const isExisting = !!s && !opts.draft;
  document.getElementById("skillModalTitle").textContent =
    opts.draft ? "✏️ 确认新技能（从对话提炼）" : (s ? "✏️ 编辑技能" : "✏️ 新建技能");
  document.getElementById("skillName").value = s ? (s.name || "") : "";
  document.getElementById("skillSlug").value = s ? (s.slug || "") : "";
  document.getElementById("skillSlug").readOnly = isExisting; // 已存在的不改 slug；草稿/新建可改
  document.getElementById("skillDesc").value = s ? (s.description || "") : "";
  document.getElementById("skillBody").value = s ? (s.body || "") : "";
  openSkillModal("edit");
}

async function saveSkillFromEditor() {
  const name = document.getElementById("skillName").value.trim();
  const slug = document.getElementById("skillSlug").value.trim();
  const description = document.getElementById("skillDesc").value.trim();
  const body = document.getElementById("skillBody").value;
  if (!name) { alert("先给技能起个名字"); return; }
  if (!slug) { alert("填一个英文 slug（小写字母/数字/连字符），作为文件夹名"); return; }
  if (!description) { alert("「什么时候用」很关键，必须写——小助靠它判断何时用这个技能"); return; }
  try {
    const r = await fetch(BACKEND + "/skills/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, name, description, content: body }),
    });
    const d = await r.json();
    if (!d.ok) { alert("保存失败：" + (d.message || "")); return; }
    closeSkillModal();
    loadSkills();
  } catch (e) { alert("保存失败：" + e.message); }
}

function openSkillGuide() {
  document.getElementById("skillModalTitle").textContent = "📖 怎么写一个技能";
  document.getElementById("skillGuide").innerHTML = renderMarkdown(SKILL_GUIDE_MD);
  openSkillModal("guide");
}

const SKILL_GUIDE_MD = [
  "「技能」就是教小助**一套做事的方法**。写好后，遇到匹配的任务它会自动按你的步骤来，而不是随便发挥。",
  "",
  "## 一个技能由两部分组成",
  "1. **什么时候用**（最重要）：写清「遇到哪类任务就用它」。小助就是靠这句话判断要不要用这个技能。写具体的触发场景，最好再写一句「不适用：……」。",
  "2. **具体步骤**（正文）：一步步写清楚遇到这类任务该怎么做。",
  "",
  "## 关键诀窍",
  "- **描述写「场景」，不要写「是什么」**。",
  "  - 别写：「这是一个写周报的技能」。",
  "  - 要写：「当用户想把这周做的零散事项整理成条理清楚的周报时用」。",
  "- **正文写成可执行的清单**，分步骤（## 第一步 / ## 第二步），每步告诉它具体做什么、注意什么。越具体越好，少讲大道理。",
  "- **加一条「红线」**：列几个「绝对不要这么做」，能让小助更稳。",
  "- **短小精悍**：一个技能聚焦一类任务。任务差别大就拆成两个技能。",
  "",
  "## 一个最简模板（照着填）",
  "```",
  "什么时候用：当用户想 ___ 的时候用。不适用：___。",
  "",
  "## 第一步：___",
  "（这一步具体做什么）",
  "## 第二步：___",
  "（这一步具体做什么）",
  "## 红线",
  "- 不要 ___",
  "- 不要 ___",
  "```",
  "",
  "## 写完之后",
  "保存后这个技能默认就开启了。回到技能页能看到它，遇到匹配的活儿小助会自己调用。想临时不用，把它的开关关掉即可。",
  "",
  "> 小提示：技能都存在本地 `backend/skills/` 文件夹里，每个技能一个子文件夹。你也可以把别处下载的技能文件夹直接拷进去，重启后就能用。",
].join("\n");

// —— 事件绑定 ——
document.getElementById("skillRefreshBtn")?.addEventListener("click", loadSkills);
document.getElementById("skillNewBtn")?.addEventListener("click", () => fillSkillEditor(null));
document.getElementById("skillGuideBtn")?.addEventListener("click", openSkillGuide);
document.getElementById("skillModalClose")?.addEventListener("click", closeSkillModal);
document.getElementById("skillCancelBtn")?.addEventListener("click", closeSkillModal);
document.getElementById("skillSaveBtn")?.addEventListener("click", saveSkillFromEditor);
document.getElementById("skillModal")?.addEventListener("click", (e) => {
  if (e.target.id === "skillModal") closeSkillModal();
});

// ============================================================
// 目标循环（Loop）—— 工具区
// ============================================================
let _loopTimer = null;

// 现成的循环模板：目标 + 验收标准。挑一个点一下就填进表单，再改成自己的。
const LOOP_PRESETS = [
  {
    label: "📊 文件夹整理成报告",
    needAction: true,
    goal: "把指定文件夹里这段时间的零散记录/文档，整理成一份结构清晰的报告，存成一个 .md 文件。",
    criteria: [
      "报告 .md 文件已生成在指定位置",
      "包含「概况 / 关键内容 / 结论或下一步」等清晰分段",
      "每个要点都来自原始文件里的真实内容，没有编造",
      "通读一遍语句通顺、没有明显错别字",
    ],
  },
  {
    label: "🔎 深度调研一个主题",
    needAction: false,
    goal: "围绕某个主题做一次深度网络调研，产出一份有条理、可直接读的调研简报。",
    criteria: [
      "至少查阅了 3 个不同来源（用 research / 搜索 / 读网页）",
      "简报分「背景 / 现状与关键事实 / 不同观点或争议 / 我的判断」几部分",
      "关键事实都标注了来源链接",
      "结尾给出一段可执行的结论或建议",
    ],
  },
  {
    label: "⚖️ 几个产品/方案对比",
    needAction: false,
    goal: "调研并对比几个同类产品（或方案），帮我判断该选哪个，输出一张对比表 + 推荐。",
    criteria: [
      "覆盖了我列出的全部对比对象，没有遗漏",
      "用 Markdown 表格列出：价格 / 核心功能 / 优点 / 缺点 / 适合谁",
      "每项信息尽量来自官网或可靠来源",
      "最后给出明确推荐，并说明在什么情况下选哪个",
    ],
  },
  {
    label: "🎬 视频转成可发布文案",
    needAction: false,
    goal: "把一个视频链接转成文字稿，再整理成一篇可直接发布的文案。",
    criteria: [
      "已取得视频完整文字稿（video_transcript）",
      "文案分成「开头钩子 / 主体要点 / 结尾」结构",
      "把口语整理成通顺书面语，但不改变原意、不添加视频里没有的事实",
      "结尾附 3 条可用的标题备选",
    ],
  },
  {
    label: "🗓️ 制定一个学习/执行计划",
    needAction: false,
    goal: "针对我要达成的某个目标，制定一份可执行的分阶段计划。",
    criteria: [
      "计划拆成有先后顺序的阶段，每阶段有明确产出",
      "每个阶段列出具体可做的任务（不是空泛口号）",
      "标出每阶段大概要花的时间",
      "结尾有一个「怎样算完成」的总验收清单",
    ],
  },
];

function renderLoopPresets() {
  const box = document.getElementById("loopPresetBtns");
  if (!box || box.dataset.done) return;
  box.innerHTML = LOOP_PRESETS.map((p, i) =>
    '<button class="loop-preset-btn" data-i="' + i + '" title="' +
    (p.needAction ? "可能需要勾选「允许自动执行操作」" : "只读/联网即可") + '">' +
    escapeHtml(p.label) + "</button>"
  ).join("");
  box.querySelectorAll(".loop-preset-btn").forEach((b) => {
    b.addEventListener("click", () => {
      const p = LOOP_PRESETS[+b.dataset.i];
      document.getElementById("loopGoal").value = p.goal;
      document.getElementById("loopCriteria").value = p.criteria.join("\n");
      if (p.needAction) document.getElementById("loopAllowActions").checked = true;
      document.getElementById("loopGoal").focus();
    });
  });
  box.dataset.done = "1";
}

function loadLoop() {
  renderLoopPresets();
  // 进入页面时，如果后台正有循环在跑，恢复显示；否则显示表单
  pollLoopOnce();
}

document.getElementById("loopStartBtn")?.addEventListener("click", async () => {
  const goal = document.getElementById("loopGoal").value.trim();
  const criteria = document.getElementById("loopCriteria").value
    .split("\n").map((x) => x.trim()).filter(Boolean);
  const max_rounds = parseInt(document.getElementById("loopMaxRounds").value, 10) || 5;
  const allow_actions = document.getElementById("loopAllowActions").checked;
  if (!goal) { alert("先写一个目标"); return; }
  if (!criteria.length) { alert("至少写一条验收标准——Loop 的关键就是「怎样算干完」"); return; }
  const s = settings();
  try {
    const r = await fetch(BACKEND + "/loop/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, criteria, max_rounds, allow_actions,
                             use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (!d.ok) { alert(d.message || "启动失败"); return; }
    document.getElementById("loopRun").style.display = "";
    document.getElementById("loopStartBtn").style.display = "none";
    document.getElementById("loopStopBtn").style.display = "";
    startLoopPolling();
  } catch (e) { alert("启动出错：" + e.message); }
});

document.getElementById("loopStopBtn")?.addEventListener("click", async () => {
  try { await fetch(BACKEND + "/loop/stop", { method: "POST" }); } catch (e) {}
  document.getElementById("loopStage").textContent = "正在停止…（这一轮跑完就停）";
});

function startLoopPolling() {
  if (_loopTimer) clearInterval(_loopTimer);
  _loopTimer = setInterval(pollLoopOnce, 1600);
}

async function pollLoopOnce() {
  try {
    const r = await fetch(BACKEND + "/loop/status");
    const st = await r.json();
    renderLoop(st);
    if (!st.running && _loopTimer) {
      clearInterval(_loopTimer); _loopTimer = null;
      document.getElementById("loopStartBtn").style.display = "";
      document.getElementById("loopStopBtn").style.display = "none";
    }
    // 若有正在跑的循环但本地没在轮询（比如刚切回页面），补上轮询
    if (st.running && !_loopTimer) {
      document.getElementById("loopRun").style.display = "";
      document.getElementById("loopStartBtn").style.display = "none";
      document.getElementById("loopStopBtn").style.display = "";
      startLoopPolling();
    }
  } catch (e) { /* 忽略一次轮询失败 */ }
}

function renderLoop(st) {
  if (!st || (!st.goal && !(st.rounds || []).length)) return;
  const stage = document.getElementById("loopStage");
  if (stage) stage.textContent = st.stage || (st.running ? "运行中…" : "");

  // 验收标准勾选状态
  const cs = document.getElementById("loopCriteriaStatus");
  if (cs) {
    const crit = st.criteria || [];
    cs.innerHTML =
      '<div class="loop-section-title">验收标准</div>' +
      crit.map((c) =>
        '<div class="loop-crit' + (c.met ? " met" : "") + '">' +
          '<span class="loop-crit-box">' + (c.met ? "✅" : "⬜") + "</span>" +
          '<span class="loop-crit-text">' + escapeHtml(c.text) + "</span>" +
        "</div>"
      ).join("");
  }

  // 每轮日志
  const rr = document.getElementById("loopRounds");
  if (rr) {
    const rounds = st.rounds || [];
    let html = '<div class="loop-section-title">过程</div>';
    if (!rounds.length) {
      html += '<div class="loop-round-empty">' + (st.running ? "第一轮进行中…" : "（暂无）") + "</div>";
    } else {
      html += rounds.map((rd) => {
        const tools = (rd.tools && rd.tools.length)
          ? '<div class="loop-round-tools">用到：' + rd.tools.map(escapeHtml).join("、") + "</div>"
          : "";
        return (
          '<div class="loop-round">' +
            '<div class="loop-round-head"><b>第 ' + rd.n + " 轮</b>" +
              '<span class="loop-round-ts">' + escapeHtml(rd.ts || "") + "</span></div>" +
            '<div class="loop-round-summary">' + renderMarkdown(rd.summary || "") + "</div>" +
            tools +
          "</div>"
        );
      }).join("");
    }
    if (st.error) html += '<div class="loop-error">出错：' + escapeHtml(st.error) + "</div>";
    rr.innerHTML = html;
  }
}

// ============================================================
// 运行台（Harness）—— 工具区
// ============================================================
let _harnessTimer = null;
function loadHarness() {
  loadHarnessConfig();
  loadHarnessRuns();
  // 启动轮询：每 3 秒刷新一次运行记录，让「进行中」的任务步骤实时更新。
  if (_harnessTimer) clearInterval(_harnessTimer);
  _harnessTimer = setInterval(() => {
    // 只在运行台可见时刷新，离开页面就停，省资源
    const view = document.getElementById("view-harness");
    const visible = view && view.offsetParent !== null;
    if (!visible) { clearInterval(_harnessTimer); _harnessTimer = null; return; }
    loadHarnessRuns();
  }, 3000);
}

async function loadHarnessConfig() {
  try {
    const r = await fetch(BACKEND + "/harness/config");
    const d = await r.json();
    const c = d.config || {};
    const ctx = document.getElementById("hCtxBudget");
    const steps = document.getElementById("hMaxSteps");
    if (ctx) { ctx.value = c.context_budget || 4000; document.getElementById("hCtxVal").textContent = (c.context_budget || 4000) + " 字"; }
    if (steps) { steps.value = c.max_steps || 8; document.getElementById("hStepsVal").textContent = (c.max_steps || 8) + " 步"; }
    if (document.getElementById("hSafety")) document.getElementById("hSafety").value = c.safety || "ask";
    if (document.getElementById("hKeepLog")) document.getElementById("hKeepLog").checked = c.keep_log !== false;
  } catch (e) { /* 忽略 */ }
}

document.getElementById("hCtxBudget")?.addEventListener("input", (e) => {
  document.getElementById("hCtxVal").textContent = e.target.value + " 字";
});
document.getElementById("hMaxSteps")?.addEventListener("input", (e) => {
  document.getElementById("hStepsVal").textContent = e.target.value + " 步";
});

document.getElementById("hSaveBtn")?.addEventListener("click", async () => {
  const patch = {
    context_budget: parseInt(document.getElementById("hCtxBudget").value, 10),
    max_steps: parseInt(document.getElementById("hMaxSteps").value, 10),
    safety: document.getElementById("hSafety").value,
    keep_log: document.getElementById("hKeepLog").checked,
  };
  const st = document.getElementById("hSaveStatus");
  try {
    const r = await fetch(BACKEND + "/harness/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    const d = await r.json();
    if (st) { st.textContent = d.ok ? "✓ 已保存" : "保存失败"; setTimeout(() => { st.textContent = ""; }, 2000); }
  } catch (e) { if (st) st.textContent = "保存出错"; }
});

document.getElementById("hRefreshBtn")?.addEventListener("click", loadHarnessRuns);
document.getElementById("hClearBtn")?.addEventListener("click", async () => {
  if (!confirm("清空所有运行日志？")) return;
  try { await fetch(BACKEND + "/harness/runs/clear", { method: "POST" }); loadHarnessRuns(); } catch (e) {}
});

async function loadHarnessRuns() {
  try {
    const r = await fetch(BACKEND + "/harness/runs");
    const d = await r.json();
    renderHarnessMetrics(d.metrics || {});
    renderHarnessRuns(d.runs || []);
  } catch (e) { /* 忽略 */ }
}

function renderHarnessMetrics(m) {
  const box = document.getElementById("hMetrics");
  if (!box) return;
  if (!m || !m.count) {
    box.innerHTML = '<div class="harness-empty">还没有运行记录。去跑一个视频提取、目标循环或洞察任务，这里就会出数据。</div>';
    return;
  }
  const card = (label, val, sub) =>
    '<div class="harness-metric"><div class="harness-metric-val">' + val + "</div>" +
    '<div class="harness-metric-label">' + label + "</div>" +
    (sub ? '<div class="harness-metric-sub">' + sub + "</div>" : "") + "</div>";
  let html = "";
  html += card("总运行次数", m.count, "对话/循环合计");
  if (m.loop_success_rate !== null && m.loop_success_rate !== undefined)
    html += card("循环达标率", m.loop_success_rate + "%", "成功 " + m.loop_done + "/" + m.loop_count + " 次");
  html += card("出错率", m.error_rate + "%", "鲁棒性");
  html += card("平均步数", m.avg_steps, "效率");
  html += card("估算 token", (m.tokens_est_total || 0).toLocaleString(), "成本（粗略）");
  box.innerHTML = '<div class="harness-metrics-grid">' + html + "</div>" +
    ((m.top_tools && m.top_tools.length)
      ? '<div class="harness-toptools">最常用工具：' +
        m.top_tools.map((t) => escapeHtml(t[0]) + " ×" + t[1]).join("、") + "</div>"
      : "");
}

function renderHarnessRuns(runs) {
  const box = document.getElementById("hRuns");
  if (!box) return;
  if (!runs.length) {
    box.innerHTML = '<div class="harness-empty">暂无记录。现在会记录视频提取、目标循环、洞察等任务的运行。</div>';
    return;
  }
  box.innerHTML = runs.map((r) => {
    const kindMap = {
      loop: "🔁 循环", chat: "💬 对话", video: "🎬 视频",
      insight: "🔍 洞察", sniff: "📡 嗅探",
    };
    const kindTag = kindMap[r.kind] || ("⚙ " + (r.kind || "任务"));
    const running = r.status === "running";
    const out = running ? '<span class="harness-out warn">⏳ 进行中</span>'
      : r.outcome === "done" ? '<span class="harness-out done">达标</span>'
      : r.outcome === "stopped" ? '<span class="harness-out">已停</span>'
      : r.outcome === "maxed" ? '<span class="harness-out warn">未达标</span>' : "";
    const tools = (r.tools && r.tools.length)
      ? '<div class="harness-run-tools">步骤：' +
        Object.entries(r.tool_count || {}).map(([k, v]) => escapeHtml(k) + (v > 1 ? "×" + v : "")).join(" → ") +
        (running ? " …" : "") + "</div>"
      : '<div class="harness-run-tools">没调工具</div>';
    const err = r.error ? '<div class="harness-run-err">⚠ ' + escapeHtml(r.error) + "</div>" : "";
    const note = r.note ? '<div class="harness-run-note" style="margin-top:4px;font-size:12px;' +
      'color:var(--text-dim,#8a8a93)">' + escapeHtml(r.note) + "</div>" : "";
    const secs = r.seconds ? " · " + r.seconds + "s" : "";
    return (
      '<div class="harness-run">' +
        '<div class="harness-run-head">' +
          '<span class="harness-run-kind">' + kindTag + "</span>" + out +
          '<span class="harness-run-ts">' + escapeHtml(r.ts || "") + secs + "</span>" +
        "</div>" +
        '<div class="harness-run-title">' + escapeHtml(r.title || "（无标题）") + "</div>" +
        tools + note + err +
      "</div>"
    );
  }).join("");
}

// ============================================================
// 嗅探（AI 雷达）—— 工具区
// ============================================================
let _sniffTimer = null;

let _sniffSources = [];
let _sniffCategories = [];
let _sniffCat = "all";   // 当前选中的类别筛选
let _sniffCollapsed = {};  // 源列表里每个类别是否折叠

function loadSniff() {
  loadSniffSources();
  loadSniffFeed();
  loadCreators();
  loadCreatorFindings();
}

async function loadSniffSources() {
  try {
    const r = await fetch(BACKEND + "/sniff/sources");
    const d = await r.json();
    _sniffSources = d.sources || [];
    _sniffCategories = d.categories || [];
    renderSniffSources(_sniffSources);
    renderSniffCatTiles(_sniffCategories);
    // 类别下拉补全
    const dl = document.getElementById("sniffCatList");
    if (dl) dl.innerHTML = _sniffCategories.map((c) => '<option value="' + escapeHtml(c.name) + '">').join("");
    const c = d.config || {};
    if (document.getElementById("sniffAuto")) document.getElementById("sniffAuto").checked = !!c.auto;
    if (document.getElementById("sniffEvery")) document.getElementById("sniffEvery").value = c.every || 6;
    if (document.getElementById("sniffEngine")) document.getElementById("sniffEngine").value = c.engine || "follow";
  } catch (e) { /* 忽略 */ }
}

function _sniffAvatar(title, url) {
  let ch = (title || url || "?").trim().replace(/^https?:\/\//, "").replace(/^www\./, "");
  ch = (ch[0] || "?").toUpperCase();
  let host = "";
  try { host = new URL(url).hostname; } catch (e) { host = url || title || ""; }
  let h = 0;
  for (let i = 0; i < host.length; i++) h = (h * 31 + host.charCodeAt(i)) % 360;
  return '<span class="sniff-src-avatar" style="--h:' + h + '">' + escapeHtml(ch) + "</span>";
}

function renderSniffSources(srcs) {
  const box = document.getElementById("sniffSources");
  if (!box) return;
  const cnt = document.getElementById("sniffSrcCount");
  if (cnt) cnt.textContent = srcs.length;
  updateSniffStats();
  if (!srcs.length) {
    box.innerHTML = '<div class="sniff-empty">还没有嗅探源。在上面填名称、链接、类别，点「添加」。</div>';
    return;
  }
  // 按类别分组（保持出现顺序）
  const groups = [];
  const idx = {};
  srcs.forEach((s) => {
    const cat = s.category || "AI动态";
    if (!(cat in idx)) { idx[cat] = groups.length; groups.push({ cat, items: [] }); }
    groups[idx[cat]].items.push(s);
  });

  box.innerHTML = groups.map((g) => {
    const onCount = g.items.filter((s) => s.enabled).length;
    const allOn = onCount === g.items.length;
    const rows = g.items.map((s) => {
      let host = "";
      try { host = new URL(s.url).hostname.replace(/^www\./, ""); } catch (e) { host = s.url; }
      return (
        '<div class="sniff-source' + (s.enabled ? "" : " off") + '" data-id="' + escapeHtml(s.id) + '" data-cat="' + escapeHtml(s.category || "AI动态") + '">' +
          _sniffAvatar(s.title, s.url) +
          '<a class="sniff-src-main" href="' + escapeHtml(s.url) + '" target="_blank" title="' + escapeHtml(s.url) + '">' +
            '<span class="sniff-src-title">' + escapeHtml(s.title || host) + "</span>" +
            '<span class="sniff-src-url">' + escapeHtml(host) + "</span>" +
          "</a>" +
          '<button class="sniff-src-cat" title="改类别 / 归类">🏷</button>' +
          '<label class="sniff-switch sniff-switch-sm" title="开启/暂停这个源">' +
            '<input type="checkbox" class="sniff-src-cb"' + (s.enabled ? " checked" : "") + " />" +
            '<span class="sniff-switch-track"></span></label>' +
          '<button class="sniff-src-del" title="删除">✕</button>' +
        "</div>"
      );
    }).join("");
    return (
      '<div class="sniff-cat-group' + (_sniffCollapsed[g.cat] ? " collapsed" : "") + '" data-cat="' + escapeHtml(g.cat) + '">' +
        '<div class="sniff-cat-head" data-cat="' + escapeHtml(g.cat) + '" title="点这里收起/展开这一类">' +
          '<span class="sniff-cat-caret">▾</span>' +
          '<span class="sniff-cat-name">📁 ' + escapeHtml(g.cat) + "</span>" +
          '<span class="sniff-cat-cnt">' + onCount + "/" + g.items.length + "</span>" +
          '<label class="sniff-switch sniff-switch-sm sniff-cat-toggle" title="开启/暂停整个类别" data-cat="' + escapeHtml(g.cat) + '">' +
            '<input type="checkbox" class="sniff-cat-cb"' + (allOn ? " checked" : "") + " />" +
            '<span class="sniff-switch-track"></span></label>' +
        "</div>" +
        '<div class="sniff-cat-body">' + rows + "</div>" +
      "</div>"
    );
  }).join("");

  // 折叠/展开：点类别标题栏切换（点开关本身不触发折叠）
  box.querySelectorAll(".sniff-cat-head").forEach((head) => {
    head.addEventListener("click", (e) => {
      if (e.target.closest(".sniff-cat-toggle")) return;   // 点的是开关，别折叠
      const cat = head.dataset.cat;
      _sniffCollapsed[cat] = !_sniffCollapsed[cat];
      head.closest(".sniff-cat-group").classList.toggle("collapsed", !!_sniffCollapsed[cat]);
    });
  });

  box.querySelectorAll(".sniff-source").forEach((el) => {
    const id = el.dataset.id;
    el.querySelector(".sniff-src-cb")?.addEventListener("change", async (e) => {
      await fetch(BACKEND + "/sniff/source/toggle", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, enabled: e.target.checked }),
      });
      loadSniffSources();
    });
    el.querySelector(".sniff-src-del")?.addEventListener("click", async () => {
      await fetch(BACKEND + "/sniff/source/delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      loadSniffSources();
    });
    // 改类别 / 归类：内联输入框，输已有类别或直接打个新名字＝新建类别
    el.querySelector(".sniff-src-cat")?.addEventListener("click", () => {
      box.querySelectorAll(".sniff-cat-edit").forEach((n) => n.remove());  // 同时只开一个
      const cur = el.dataset.cat || "AI动态";
      const bar = document.createElement("div");
      bar.className = "sniff-cat-edit";
      bar.innerHTML =
        '<span class="sniff-cat-edit-tip">归到类别（打个新名字就是新建）</span>' +
        '<div class="sniff-cat-edit-row">' +
          '<input class="sniff-cat-edit-input sniff-input" list="sniffCatList" placeholder="如 AI动态 / 竞品 / 技术社区" />' +
          '<button class="sniff-cat-edit-ok sniff-add-btn">确定</button>' +
          '<button class="sniff-cat-edit-cancel sniff-mini-btn">取消</button>' +
        "</div>";
      el.after(bar);
      const input = bar.querySelector(".sniff-cat-edit-input");
      input.value = cur; input.focus(); input.select();
      const close = () => bar.remove();
      const submit = async () => {
        const category = input.value.trim();
        if (!category) { input.focus(); return; }
        try {
          await fetch(BACKEND + "/sniff/source/category", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, category }),
          });
          loadSniffSources();
        } catch (e) { alert("改类别出错：" + e.message); }
      };
      bar.querySelector(".sniff-cat-edit-ok").onclick = submit;
      bar.querySelector(".sniff-cat-edit-cancel").onclick = close;
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") submit();
        else if (ev.key === "Escape") close();
      });
    });
  });
  box.querySelectorAll(".sniff-cat-cb").forEach((cb) => {
    cb.addEventListener("change", async (e) => {
      const cat = e.target.closest(".sniff-cat-toggle").dataset.cat;
      await fetch(BACKEND + "/sniff/category/toggle", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat, enabled: e.target.checked }),
      });
      loadSniffSources();
    });
  });
}

// 右侧 dashboard：类别概览卡片（点一下按类别筛选动向）
function renderSniffCatTiles(categories) {
  const box = document.getElementById("sniffCatTiles");
  if (!box) return;
  const counts = {};
  _sniffFeedCache.forEach((it) => {
    const c = it.category || "AI动态";
    counts[c] = (counts[c] || 0) + 1;
  });
  let tiles = '<button class="sniff-tile' + (_sniffCat === "all" ? " active" : "") + '" data-cat="all">' +
    '<span class="sniff-tile-name">全部类别</span>' +
    '<span class="sniff-tile-stat">' + (_sniffSources.length) + " 源 · " + _sniffFeedCache.length + " 条</span></button>";
  tiles += categories.map((c) =>
    '<button class="sniff-tile' + (_sniffCat === c.name ? " active" : "") + '" data-cat="' + escapeHtml(c.name) + '">' +
      '<span class="sniff-tile-name">📁 ' + escapeHtml(c.name) + "</span>" +
      '<span class="sniff-tile-stat">' + c.total + " 源 · " + (counts[c.name] || 0) + " 条</span>" +
    "</button>"
  ).join("");
  box.innerHTML = tiles;
  box.querySelectorAll(".sniff-tile").forEach((t) => {
    t.addEventListener("click", () => {
      _sniffCat = t.dataset.cat;
      box.querySelectorAll(".sniff-tile").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const lbl = document.getElementById("sniffCatActive");
      if (lbl) lbl.textContent = _sniffCat === "all" ? "" : "· " + _sniffCat;
      paintSniffFeed();
    });
  });
}

document.getElementById("sniffAddBtn")?.addEventListener("click", async () => {
  const title = document.getElementById("sniffAddTitle").value.trim();
  const url = document.getElementById("sniffAddUrl").value.trim();
  const category = (document.getElementById("sniffAddCat").value.trim() || "AI动态");
  if (!url) { alert("填一个链接"); return; }
  try {
    const r = await fetch(BACKEND + "/sniff/source/add", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, url, category }),
    });
    const d = await r.json();
    if (!d.ok) { alert(d.message || "添加失败"); return; }
    document.getElementById("sniffAddTitle").value = "";
    document.getElementById("sniffAddUrl").value = "";
    loadSniffSources();
  } catch (e) { alert("添加出错：" + e.message); }
});

document.getElementById("sniffAutoSave")?.addEventListener("click", async () => {
  const auto = document.getElementById("sniffAuto").checked;
  const every = parseInt(document.getElementById("sniffEvery").value, 10) || 6;
  const engine = document.getElementById("sniffEngine") ? document.getElementById("sniffEngine").value : "follow";
  try {
    await fetch(BACKEND + "/sniff/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto, every, engine }),
    });
    const st = document.getElementById("sniffAutoSave");
    const old = st.textContent; st.textContent = "✓"; setTimeout(() => { st.textContent = old; }, 1500);
  } catch (e) {}
});

document.getElementById("sniffRefreshBtn")?.addEventListener("click", () => { loadSniffSources(); loadSniffFeed(); });

// ════════════════════ 嗅探页：标签切换 + 关注的博主（视频更新监控）════════════════════
let _cwFindings = [];
let _cwScanTimer = null;
let _cwVideos = [];
let _cwEmptyReason = "";   // X 等平台抓取失败时的具体原因，渲染空列表时显示
let _cwCurrentCreator = { id: null, title: "" };

// 改动1：博主视频前端缓存。key=creator id，值 {videos,total,platform_label,title,ts}
// 命中即立即渲染，再后台静默刷新，二次点开秒开、不再卡 2 秒。
const _cwVideoCache = {};
// 改动4：分页 + 跨页选择。选中用 Set（key=vid），覆盖所有页，不依赖当前 DOM。
let _cwPage = 1;
let _cwPageSize = 20;
let _cwSelectedVids = new Set();
// 批量扫描按钮原文案（改动2：扫描中切换文案/禁用后用于恢复）
let _cwScanAllLabel = "";

const _CW_PLAT_ICON = { youtube: "▶️", bilibili: "📺", douyin: "🎵", x: "𝕏" };

// 安全取「当前模型设置」：settings() 在设置面板还没初始化时可能抛错，
// 这里兜底，保证翻译/提取请求不会因为读不到设置而静默失败。
function _cwSafeSettings() {
  try {
    if (typeof settings === "function") {
      const s = settings();
      if (s && (s.model || s.use_local != null)) return s;
    }
  } catch (e) {}
  // 兜底：优先本地 qwen2.5；后端自己还会做本地→网页的兜底
  return { use_local: true, model: "qwen2.5" };
}

// 统一的「页内状态提示」——取代弹窗。写到左卡头部状态行（这个标签页里始终可见），
// 几秒后自动淡出（被新的扫描状态覆盖时不清，交给轮询自己更新）。
let _cwStatusTimer = null;
function _cwSetStatus(msg) {
  const el = document.getElementById("cwScanState");
  if (!el) return;
  el.textContent = msg || "";
  if (_cwStatusTimer) { clearTimeout(_cwStatusTimer); _cwStatusTimer = null; }
  if (msg) {
    _cwStatusTimer = setTimeout(() => {
      // 只在不是「扫描中」状态时清，避免把进行中的提示抹掉
      if (el.textContent === msg && !/扫描中|正在扫/.test(el.textContent)) el.textContent = "";
    }, 8000);
  }
}

// 顶部并列标签：🎯 博主更新 / 📡 网站动态
document.getElementById("snTabs")?.addEventListener("click", (e) => {
  const t = e.target.closest(".sn-tab");
  if (!t) return;
  const name = t.dataset.sntab;
  document.querySelectorAll("#view-sniff .sn-tab").forEach((b) => b.classList.toggle("active", b === t));
  document.querySelectorAll("#view-sniff .sn-tabpane").forEach((p) => { p.hidden = (p.dataset.pane !== name); });
});

// ⓘ / ? 浮动说明气泡：点按钮弹出绝对定位的气泡，点别处或 × 关闭（不挤占布局）
function _snBindPop(btnId, popId) {
  const btn = document.getElementById(btnId);
  const pop = document.getElementById(popId);
  if (!btn || !pop) return;
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const show = pop.hasAttribute("hidden");
    // 先关掉本视图里其它已打开的气泡
    document.querySelectorAll("#view-sniff .sn-pop").forEach((p) => { if (p !== pop) p.setAttribute("hidden", ""); });
    document.querySelectorAll("#view-sniff .sn-info.on, #view-sniff .sn-q.on").forEach((b) => { if (b !== btn) b.classList.remove("on"); });
    if (show) { pop.removeAttribute("hidden"); btn.classList.add("on"); }
    else { pop.setAttribute("hidden", ""); btn.classList.remove("on"); }
  });
  // 气泡内部点击不冒泡（避免被「点别处关闭」误关），但 × 按钮要能关
  pop.addEventListener("click", (e) => {
    if (e.target.closest("[data-popclose]")) {
      pop.setAttribute("hidden", ""); btn.classList.remove("on");
    }
    e.stopPropagation();
  });
}
_snBindPop("cwInfoBtn", "cwInfoPanel");        // 我关注的博主 ⓘ
_snBindPop("cwPerScanQ", "cwPerScanPanel");    // 「每次最多 N 条」?
_snBindPop("cwNewInfoBtn", "cwNewInfoPanel");  // 扫出来的新视频 ⓘ
_snBindPop("dgInfoBtn", "dgInfoPanel");        // 按时间看全部 ⓘ
// 点视图内任意空白处，关闭所有气泡
document.getElementById("view-sniff")?.addEventListener("click", () => {
  document.querySelectorAll("#view-sniff .sn-pop").forEach((p) => p.setAttribute("hidden", ""));
  document.querySelectorAll("#view-sniff .sn-info.on, #view-sniff .sn-q.on").forEach((b) => b.classList.remove("on"));
});

// 右侧工作区两个子标签：① 扫出来的新视频 ② 按时间看全部
document.getElementById("cwWorkTabs")?.addEventListener("click", (e) => {
  // 点子标签里的 ⓘ 按钮不切换标签（它自己 stopPropagation 了，这里兜底）
  if (e.target.closest(".sn-info") || e.target.closest(".sn-pop")) return;
  const t = e.target.closest(".cw-subtab");
  if (!t) return;
  const name = t.dataset.worktab;
  document.querySelectorAll("#cwWorkTabs .cw-subtab").forEach((b) => b.classList.toggle("active", b === t));
  document.querySelectorAll('#view-sniff .cw-worktab-pane').forEach((p) => { p.hidden = (p.dataset.workpane !== name); });
  // 切到「按时间看全部」时首次加载（默认用缓存，秒出）
  if (name === "digest" && !_dgLoadedOnce) { _dgLoadedOnce = true; loadDigest(false); }
});

// 「博主列表」可折叠（保留）
(function () {
  const head = document.getElementById("cwListToggle");
  const body = document.getElementById("cwListBody");
  if (!head || !body) return;
  const setOpen = (open) => {
    head.classList.toggle("collapsed", !open);
    body.classList.toggle("collapsed", !open);
    if (open) body.style.maxHeight = body.scrollHeight + 40 + "px";
    else body.style.maxHeight = "0px";
  };
  body.style.maxHeight = "none";
  head.addEventListener("click", () => {
    const isOpen = !head.classList.contains("collapsed");
    if (isOpen) {
      body.style.maxHeight = body.scrollHeight + "px";
      requestAnimationFrame(() => setOpen(false));
    } else {
      setOpen(true);
      setTimeout(() => { if (!head.classList.contains("collapsed")) body.style.maxHeight = "none"; }, 240);
    }
  });
  window._cwRelaxListHeight = () => {
    if (!head.classList.contains("collapsed")) body.style.maxHeight = "none";
  };
})();

async function loadCreators() {
  try {
    const r = await fetch(BACKEND + "/creator/list");
    const d = await r.json();
    renderCreators(d.creators || []);
    const c = d.config || {};
    const a = document.getElementById("cwAuto"); if (a) a.checked = !!c.auto;
    const h = document.getElementById("cwHour"); if (h) h.value = (c.hour != null ? c.hour : 9);
    const p = document.getElementById("cwPerScan"); if (p) p.value = (c.per_scan || 15);
  } catch (e) {}
}

function renderCreators(list) {
  const box = document.getElementById("cwList");
  const cnt = document.getElementById("cwCount");
  if (cnt) cnt.textContent = list.length;
  const cnt2 = document.getElementById("cwListCount");   // 改动2：折叠头里的计数
  if (cnt2) cnt2.textContent = list.length;
  if (!box) { if (window._cwRelaxListHeight) window._cwRelaxListHeight(); return; }
  if (!list.length) {
    box.innerHTML = '<div class="cw-empty">还没有博主。上面填主页链接，点「添加博主」。</div>';
    return;
  }
  box.innerHTML = (_cwViewMode === "avatar" ? list.map(_cwTileHtml) : list.map((c) => {   // v74：头像 / 列表
    const ic = _CW_PLAT_ICON[c.platform] || "🔗";
    let sub = (c.platform_label || "") + " · ";
    sub += c.last_checked ? ("上次 " + escapeHtml(c.last_checked) + "，最近 " + c.last_count + " 条") : "还没扫过";
    const err = c.last_error ? ('<div class="cw-c-err" title="' + escapeHtml(c.last_error) + '">⚠ ' + escapeHtml(c.last_error) + "</div>") : "";
    const sel = (_cwCurrentCreator.id === c.id) ? " sel" : "";
    return '' +
      '<div class="cw-creator' + (c.enabled ? "" : " off") + sel + '" data-id="' + escapeHtml(c.id) + '">' +
        '<div class="cw-ava">' + ic + "</div>" +
        '<div class="cw-c-main" title="点这里查看该博主的视频清单">' +
          '<div class="cw-c-title">' + escapeHtml(c.title || "(未命名)") + "</div>" +
          '<span class="cw-c-sub">' + escapeHtml(sub) + "</span>" +
          err +
        "</div>" +
        '<button class="sn-btn sm cw-scan-one" title="扫一遍找新视频（攒到本次新增）">扫一遍</button>' +
        '<button class="cw-iconbtn cw-edit" title="改名 / 备注">✎</button>' +
        '<label class="sniff-switch sniff-switch-sm" title="开启/暂停（暂停后不参与每天自动扫）"><input type="checkbox" class="cw-tog"' + (c.enabled ? " checked" : "") + ' /><span class="sniff-switch-track"></span></label>' +
        '<button class="cw-iconbtn cw-del" title="删除">✕</button>' +
      "</div>";
  })).join("");
  box.classList.toggle("cw-wall", _cwViewMode === "avatar");

  box.querySelectorAll(".cw-creator").forEach((el) => {
    const id = el.dataset.id;
    const c = list.find((x) => x.id === id) || {};
    el.querySelector(".cw-c-main")?.addEventListener("click", () => openCreatorVideos(id, c.title || ""));
    el.querySelector(".cw-scan-one")?.addEventListener("click", async (e) => {
      const btn = e.currentTarget; const old = btn.textContent;
      const nm = (c.title || "这个博主");
      btn.textContent = "扫描中…"; btn.disabled = true;
      _cwSetStatus("正在扫「" + nm + "」…");
      try {
        const r = await fetch(BACKEND + "/creator/scan", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id }),
        });
        const d = await r.json();
        const res = d.result || {};
        _cwOneResult[id] = { res, ts: Date.now() };     // v74：头像左上角显示这次扫描的结果
        if (res.error) { _cwSetStatus("「" + nm + "」扫描失败：" + res.error); }
        else if (res.first_time) { _cwSetStatus("「" + nm + "」已记录当前作品（首次只记录，下次起才报新视频）"); }
        else { _cwSetStatus(res.new_count ? ("「" + nm + "」发现 " + res.new_count + " 条新视频，已加到右侧「本次新增」") : ("「" + nm + "」没有新视频")); }
        loadCreators(); loadCreatorFindings();
      } catch (err) { _cwSetStatus("扫描出错：" + err.message); }
      finally { btn.textContent = old; btn.disabled = false; }
    });
    el.querySelector(".cw-tog")?.addEventListener("change", async (e) => {
      try {
        await fetch(BACKEND + "/creator/toggle", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, enabled: e.target.checked }),
        });
        loadCreators();
      } catch (err) {}
    });
    el.querySelector(".cw-edit")?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const main = el.querySelector(".cw-c-main");
      if (!main || main.querySelector(".cw-edit-input")) return;
      const cur = (c.title || "").trim();
      main.innerHTML = '<input class="cw-edit-input sn-input" style="width:100%;font-size:13px" />';
      const inp = main.querySelector(".cw-edit-input");
      inp.value = cur; inp.focus(); inp.select();
      inp.addEventListener("click", (e) => e.stopPropagation());
      let done = false;
      const finish = async (commit) => {
        if (done) return; done = true;
        const v = commit ? inp.value.trim() : "";
        if (!commit || !v || v === cur) { loadCreators(); return; }
        try {
          await fetch(BACKEND + "/creator/rename", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, title: v }),
          });
          if (_cwCurrentCreator.id === id) {
            _cwCurrentCreator.title = v;
            const tt = document.getElementById("cwVideoTitle");
            if (tt) tt.textContent = "📹 " + v;
          }
          _cwSetStatus("已改名为「" + v + "」");
          loadCreators();
        } catch (err) { _cwSetStatus("改名出错：" + err.message); loadCreators(); }
      };
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); finish(true); }
        else if (e.key === "Escape") { e.preventDefault(); finish(false); }
      });
      inp.addEventListener("blur", () => finish(true));
    });
    el.querySelector(".cw-del")?.addEventListener("click", async () => {
      if (!confirm("删除这个博主？（它名下还没处理的新视频也会一并清掉）")) return;
      try {
        await fetch(BACKEND + "/creator/delete", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id }),
        });
        if (_cwCurrentCreator.id === id) backToDigest();
        loadCreators(); loadCreatorFindings();
      } catch (err) {}
    });
  });
  // 改动2：列表内容更新后，若处于展开态放开高度限制（避免被旧固定值裁剪）
  if (window._cwRelaxListHeight) window._cwRelaxListHeight();
}

// ─── 本次新增（自动扫攒下的新视频）───
async function loadCreatorFindings() {
  try {
    const r = await fetch(BACKEND + "/creator/findings");
    const d = await r.json();
    _cwFindings = d.findings || [];
    renderFindings(_cwFindings);
    const st = document.getElementById("cwScanState");
    const scan = d.scan || {};
    _cwRenderScanLog(scan);   // 改动2：逐博主明细
    if (scan.running) {
      _cwSetScanAllBusy(true);   // 改动2：按钮变「扫描中…」并禁用
      const prog = scan.progress ? (" " + scan.progress) : "";
      const cur = scan.current ? ("：" + scan.current) : "";
      if (st) st.textContent = scan.last || ("⏳ 批量扫描中…" + prog + cur);
      if (!_cwScanTimer) _cwScanTimer = setInterval(loadCreatorFindings, 1500);
    } else if (_cwScanTimer) {
      // 刚从「扫描全部」结束 → 显示一次结果再停轮询
      clearInterval(_cwScanTimer); _cwScanTimer = null;
      _cwSetScanAllBusy(false);   // 改动2：恢复按钮
      if (st && scan.last) st.textContent = scan.last;
      loadCreators();
      // 扫描刚结束：把「按时间看全部」也刷新一遍，让它和「扫出来的新视频」保持同步。
      // 扫描已经把各博主最新视频写进同一份缓存，这里默认吃缓存即可拿到最新（含刚扫到的新视频）。
      // 只有用户已经打开过「按时间看全部」才刷，避免无谓联网。
      if (_dgLoadedOnce) { try { loadDigest(false); } catch (e) {} }
    } else {
      _cwSetScanAllBusy(false);   // 保险：非扫描态确保按钮可用
    }
    // 非扫描中：不主动改状态行，免得把单次扫描 / 改名 / 提取的页内提示覆盖掉
  } catch (e) {}
}

// 改动2：批量扫描按钮忙/闲切换（存原文案，闲时恢复）
function _cwSetScanAllBusy(busy) {
  const b = document.getElementById("cwScanAll");
  if (!b) return;
  if (busy) {
    if (!_cwScanAllLabel) _cwScanAllLabel = b.textContent;
    if (!b.disabled) { b.disabled = true; b.textContent = "扫描中…"; }
  } else if (b.disabled || _cwScanAllLabel) {
    b.disabled = false;
    b.textContent = _cwScanAllLabel || "⚡ 批量扫描";
    _cwScanAllLabel = "";
  }
}

// 改动2：渲染逐博主扫描明细（进度 + 当前是谁 + 各自结果/出错）
function _cwRenderScanLog(scan) {
  _cwScanInfo = scan || {};                      // v74：正在扫谁 → 头像动画；每个博主的结果 → 左上角
  try { _cwTilesMark(); } catch (_) {}
  const box = document.getElementById("cwScanLog");
  if (!box) return;
  const log = Array.isArray(scan.log) ? scan.log : [];
  if (!scan.running && !log.length) { box.hidden = true; box.innerHTML = ""; return; }
  box.hidden = false;
  let html = "";
  if (scan.running && scan.current) {
    html += '<div class="cw-scanlog-cur">⏳ ' +
      (scan.progress ? (escapeHtml(scan.progress) + " ") : "") +
      "正在扫：" + escapeHtml(scan.current) + "…</div>";
  }
  html += log.map((it) => {
    const ok = !!it.ok;
    let res, cls;
    if (!ok) { res = "失败" + (it.error ? ("：" + escapeHtml(String(it.error).slice(0, 40))) : ""); cls = "err"; }
    else if (it.first_time) { res = "首次记录"; cls = "ok"; }
    else if (it.new_count > 0) { res = "新增 " + it.new_count + " 条"; cls = "ok"; }
    else { res = "无新增"; cls = ""; }
    const ico = !ok ? "❌" : "✅";
    return '<div class="cw-scanlog-row">' +
      '<span class="cw-scanlog-ico">' + ico + "</span>" +
      '<span class="cw-scanlog-name">' + escapeHtml(it.name || "博主") + "</span>" +
      '<span class="cw-scanlog-res ' + cls + '">' + res + "</span>" +
      "</div>";
  }).join("");
  box.innerHTML = html;
}

// v89：「扫出来的新视频」的勾选单独记着——列表每 1.5 秒（扫描时）或换头像时会整个重画，
// 以前一重画勾选就全没了，再点「提取选中」就是「先勾选要提取的视频」，看着像没反应
var _cwFindSel = new Set();
function _cwFindKey(f) {
  return String(f.creator_id == null ? "" : f.creator_id) + "|" + String(f.vid == null ? "" : f.vid) + "|" + (f.url || "");
}
function _cwFindSelSync() {
  const list = Array.isArray(_cwFindings) ? _cwFindings : [];
  const keys = new Set(list.map(_cwFindKey));
  _cwFindSel.forEach((k) => { if (!keys.has(k)) _cwFindSel.delete(k); });
  const sa = document.getElementById("cwSelAll");
  if (sa) sa.checked = list.length > 0 && _cwFindSel.size === list.length;
  const b = document.getElementById("cwExtractBtn");
  if (b && !b.disabled) b.textContent = _cwFindSel.size ? "提取选中（" + _cwFindSel.size + "）" : "提取选中";
}

function renderFindings(list) {
  const box = document.getElementById("cwFindings");
  const cnt = document.getElementById("cwFindCount");
  if (cnt) cnt.textContent = list.length;
  if (!box) return;
  if (!list.length) {
    box.innerHTML = '<div class="cw-empty">暂无新视频。点左边某个博主「查看视频」，或点「批量扫描」。</div>';
    _cwFindSel.clear();
    _cwFindSelSync();
    return;
  }
  box.innerHTML = list.map((f, i) => {
    const ic = _CW_PLAT_ICON[f.platform] || "🔗";
    const title = f.title || f.url || "(无标题)";
    // 这一列里的每条都是「扫描发现的新视频」，统一打「新」角标
    const zhText = (f.title_zh && f.title_zh !== f.title) ? ("🌐 " + escapeHtml(f.title_zh)) : "";
    return '' +
      '<div class="cw-video">' +
        '<input type="checkbox" class="cw-fcb" data-i="' + i + '"' + (_cwFindSel.has(_cwFindKey(f)) ? " checked" : "") + ' />' +
        '<div class="cw-v-main">' +
          '<div class="cw-v-title"><span class="cw-new-badge">新</span>' + ic + " " + escapeHtml(title) + "</div>" +
          '<div class="cw-v-zh">' + zhText + "</div>" +
          '<div class="cw-v-meta"><span class="cw-tag cw-tag-au">' + _cwMiniAv(f.creator_id, f.creator_title) + escapeHtml(f.creator_title || "") + "</span>" +
            '<a class="cw-vlink" href="' + escapeHtml(f.url) + '" target="_blank">原视频↗</a><span>' + escapeHtml(f.found_at || "") + "</span></div>" +
        "</div>" +
      "</div>";
  }).join("");
  box.querySelectorAll(".cw-fcb").forEach((cb) => {
    cb.addEventListener("change", () => {
      const f = _cwFindings[parseInt(cb.dataset.i, 10)];
      if (f) { if (cb.checked) _cwFindSel.add(_cwFindKey(f)); else _cwFindSel.delete(_cwFindKey(f)); }
      _cwFindSelSync();
    });
  });
  _cwFindSelSync();
  _cwTranslateFindings();   // 把英文标题翻成中文，填进预留的占位
}

// 翻译「扫出来的新视频」里的英文标题（和视频清单同一套后端接口）
// 翻译标题请求「同一时间只发一个」：列表每次刷新都会触发翻译，以前会堆起很多个慢请求，
// 占满界面到后端的连接（浏览器对同一地址最多 6 个），别的页面（如视频笔记列表）就一直「加载中」。
// 正在翻译时再来的请求直接放弃（下次刷新列表会再补翻）。
let _cxTrInflight = null;
function _cxTranslateOnce(url, opts) {
  if (_cxTrInflight) return Promise.reject(new Error("translate busy"));
  _cxTrInflight = fetch(url, opts).finally(() => { _cxTrInflight = null; });
  return _cxTrInflight;
}

async function _cwTranslateFindings() {
  const box = document.getElementById("cwFindings");
  if (!box || !Array.isArray(_cwFindings)) return;
  const idxs = [], titles = [];
  _cwFindings.forEach((f, i) => {
    const t = (f.title || "").trim();
    if (!t || f.title_zh || /[\u4e00-\u9fff]/.test(t)) return;  // 已翻/含中文跳过
    idxs.push(i); titles.push(t);
  });
  if (!titles.length) return;
  const s = _cwSafeSettings();
  try {
    const r = await _cxTranslateOnce(BACKEND + "/creator/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titles, use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (!d.ok || !Array.isArray(d.translations)) return;
    d.translations.forEach((zh, k) => {
      const i = idxs[k];
      const z = (zh || "").trim();
      if (!z || !_cwFindings[i] || z === (_cwFindings[i].title || "").trim()) return;
      _cwFindings[i].title_zh = z;
      const cb = box.querySelector('.cw-fcb[data-i="' + i + '"]');
      const main = cb ? cb.closest(".cw-video").querySelector(".cw-v-main") : null;
      const zhEl = main ? main.querySelector(".cw-v-zh") : null;
      if (zhEl) zhEl.textContent = "🌐 " + z;
    });
  } catch (e) {}
}

function _cwSelectedItems() {
  const out = [];
  (Array.isArray(_cwFindings) ? _cwFindings : []).forEach((f) => {
    if (_cwFindSel.has(_cwFindKey(f))) out.push({ creator_id: f.creator_id, vid: f.vid, url: f.url });
  });
  return out;
}

// ─── 单个博主的视频清单（点博主名进入）───
function openCreatorVideos(cid, title) {
  _cwCurrentCreator = { id: cid, title: title };
  _cwPage = 1;                       // 改动4：每次进入回到第 1 页
  _cwSelectedVids = new Set();       // 改动4：换博主清空跨页选择
  // 点博主看视频 → 确保切回「扫出来的新视频」子标签（视频清单在这个子页里）
  document.querySelectorAll("#cwWorkTabs .cw-subtab").forEach((b) => b.classList.toggle("active", b.dataset.worktab === "new"));
  document.querySelectorAll('#view-sniff .cw-worktab-pane').forEach((p) => { p.hidden = (p.dataset.workpane !== "new"); });
  document.getElementById("cwDigestView").hidden = true;
  document.getElementById("cwVideoView").hidden = false;
  const tt = document.getElementById("cwVideoTitle");
  if (tt) tt.textContent = "📹 " + (title || "视频清单");
  document.querySelectorAll("#cwList .cw-creator").forEach((el) => el.classList.toggle("sel", el.dataset.id === cid));
  // 改动4（秒开）：分三层，越靠前越快——
  // 1) 内存缓存命中（同一次会话里点过）→ 立刻渲染
  // 2) 否则问后端「持久缓存」（上次列到的，落盘了）→ 几十毫秒返回，立刻渲染
  // 3) 两者都没有，才显示骨架并联网列（首次添加的博主才会走到这）
  // 不论走 1 还是 2，都接着后台 loadCreatorVideos(true) 联网刷新一遍。
  const mem = _cwVideoCache[cid];
  if (mem && Array.isArray(mem.videos)) {
    _cwVideos = mem.videos;
    const st = document.getElementById("cwVideoState");
    if (st) st.textContent = (mem.platform_label || "") + " · 共 " + (mem.total || _cwVideos.length) + " 条（刷新中…）";
    renderVideos();
    _cwTranslateTitles();
    loadCreatorVideos(true);
    return;
  }
  // 先放骨架占位（保持高度稳定），同时去问持久缓存
  const box = document.getElementById("cwVideos");
  if (box) box.innerHTML = _cwSkeletonRows(Math.min(_cwPageSize || 8, 8));
  const st0 = document.getElementById("cwVideoState");
  if (st0) st0.textContent = "读取中…";
  _cwTryCachedThenLive(cid);
}

// 改动4（秒开）：先打「只读缓存」接口，命中就秒渲染再后台刷新；没命中直接联网列
async function _cwTryCachedThenLive(cid) {
  try {
    const r = await fetch(BACKEND + "/creator/videos_cached", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: cid }),
    });
    const d = await r.json();
    // 用户可能在等待时已切走/换了博主，要校验仍是当前博主
    if (_cwCurrentCreator.id !== cid) return;
    if (d && d.ok && Array.isArray(d.videos) && d.videos.length) {
      _cwVideos = d.videos;
      // 同步进内存缓存
      _cwVideoCache[cid] = { videos: d.videos, total: d.total || d.videos.length,
                             platform_label: d.platform_label || "", title: d.title || _cwCurrentCreator.title, ts: Date.now() };
      if (d.title && d.title !== _cwCurrentCreator.title) {
        _cwCurrentCreator.title = d.title;
        const tt = document.getElementById("cwVideoTitle");
        if (tt) tt.textContent = "📹 " + d.title;
        _cwUpdateCreatorTitle(cid, d.title);
      }
      const st = document.getElementById("cwVideoState");
      if (st) st.textContent = (d.platform_label || "") + " · 共 " + (d.total || d.videos.length) + " 条" +
        (d.cached_at ? ("（缓存于 " + d.cached_at + "，刷新中…）") : "（刷新中…）");
      _cwClampPage();
      renderVideos();
      _cwTranslateTitles();
      loadCreatorVideos(true);   // 后台联网刷新
      return;
    }
  } catch (e) {}
  // 没有缓存（或为空）→ 正常联网列
  if (_cwCurrentCreator.id === cid) loadCreatorVideos(false);
}

function backToDigest() {
  const vv = document.getElementById("cwVideoView"); if (vv) vv.hidden = true;
  const dv = document.getElementById("cwDigestView"); if (dv) dv.hidden = false;
  _cwCurrentCreator = { id: null, title: "" };
  document.querySelectorAll("#cwList .cw-creator").forEach((el) => el.classList.remove("sel"));
}

async function loadCreatorVideos(silent) {
  const cid = _cwCurrentCreator.id;
  if (!cid) return;
  const raw = (document.getElementById("cwVideoLimit").value || "").trim();
  const limit = raw === "" ? 0 : (parseInt(raw, 10) || 0);   // 空 / 0 = 全部
  const box = document.getElementById("cwVideos");
  const st = document.getElementById("cwVideoState");
  if (!silent) {
    // 改动1：用骨架行代替单行「加载中」，保持高度稳定、不跳
    if (box) box.innerHTML = _cwSkeletonRows(Math.min(_cwPageSize || 8, 8));
    if (st && !st.textContent) st.textContent = "加载中…（在列这个博主的视频，列「全部」或走代理可能要一会儿）";
  }
  try {
    const r = await fetch(BACKEND + "/creator/videos", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: cid, limit }),
    });
    const d = await r.json();
    if (!d.ok) {
      if (silent) return;   // 静默刷新失败：保留已显示的缓存内容，不打扰
      _cwVideos = [];
      if (box) box.innerHTML = '<div class="cw-empty">取不到视频：' + escapeHtml(d.message || "未知错误") + "</div>";
      _cwRenderPager();
      updateExtractVLabel();
      return;
    }
    const fresh = d.videos || [];
    // 改动1：静默刷新时，数据没变就别重渲染（避免无谓闪动 + 丢翻译）
    if (silent && _cwSameVideos(_cwVideos, fresh)) {
      // 仅更新「刷新中…」状态行为正常计数
      const shown0 = fresh.length, total0 = d.total || shown0;
      if (st) st.textContent = (d.platform_label || "") + " · 共 " + total0 + " 条";
      _cwVideoCache[cid] = { videos: fresh, total: total0, platform_label: d.platform_label || "", title: d.title || _cwCurrentCreator.title, ts: Date.now() };
      return;
    }
    _cwVideos = fresh;
    _cwEmptyReason = (fresh.length ? "" : (d.empty_reason || ""));
    // 若服务端这次识别到了真实昵称，只改这一个左列节点 + 右侧标题（改动1：不整列重渲染）
    if (d.title && d.title !== _cwCurrentCreator.title) {
      _cwCurrentCreator.title = d.title;
      const tt = document.getElementById("cwVideoTitle");
      if (tt) tt.textContent = "📹 " + d.title;
      _cwUpdateCreatorTitle(cid, d.title);
    }
    const hasDate = _cwVideos.some((v) => v.days_ago != null);
    const shown = (d.shown != null) ? d.shown : _cwVideos.length;
    const total = d.total || shown;
    const cntTxt = (total && total > shown)
      ? ("显示最新 " + shown + " / 共 " + total + " 条（点「重置」看全部）")
      : ("共 " + shown + " 条");
    if (st) st.textContent = (d.platform_label || "") + " · " + cntTxt +
      (hasDate ? "" : "（旧视频无发布日期，按天数筛选只对最近的有效，可用「全选」或手动勾选）");
    // 改动1：写前端缓存，下次点开秒出
    _cwVideoCache[cid] = { videos: _cwVideos, total: total, platform_label: d.platform_label || "", title: d.title || _cwCurrentCreator.title, ts: Date.now() };
    // 数据变了：把页码夹到合法范围再渲染当前页
    _cwClampPage();
    renderVideos();
    _cwTranslateTitles();   // 翻译当前页可见的、未翻的标题（改动5）
  } catch (e) {
    if (silent) return;
    if (box) box.innerHTML = '<div class="cw-empty">出错：' + escapeHtml(e.message) + "</div>";
  }
}

// 改动1：骨架行（占位，保持列表高度稳定）
function _cwSkeletonRows(n) {
  let s = "";
  for (let i = 0; i < n; i++) {
    s += '<div class="cw-skel"><div class="cw-skel-box"></div>' +
      '<div class="cw-skel-main"><div class="cw-skel-line"></div>' +
      '<div class="cw-skel-line short"></div></div></div>';
  }
  return s;
}

// 改动1：只更新某一个左列博主节点的标题文本，避免 loadCreators() 整列重渲染导致跳动
function _cwUpdateCreatorTitle(cid, title) {
  const el = document.querySelector('#cwList .cw-creator[data-id="' + (window.CSS && CSS.escape ? CSS.escape(cid) : cid) + '"]');
  const t = el ? el.querySelector(".cw-c-title") : null;
  if (t) t.textContent = title;
}

// 比较两批视频是否「实质相同」（按 vid 序列），用于静默刷新去抖
function _cwSameVideos(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if ((a[i] && a[i].vid) !== (b[i] && b[i].vid)) return false;
  }
  return true;
}

// 把当前页里「非中文」的标题批量翻成中文（异步，不阻塞列表显示）。
// 改动5：只翻当前页可见、未翻的；本地优先、网页兜底由后端处理；翻不动给轻提示。
async function _cwTranslateTitles() {
  const page = _cwPageItems();           // 只取当前页
  const idxs = [], titles = [];
  for (const { v, i } of page) {
    const t = (v.title || "").trim();
    if (!t || v.title_zh || /[\u4e00-\u9fff]/.test(t)) continue;  // 已翻/含中文则跳过
    idxs.push(i); titles.push(t);
  }
  if (!titles.length) return;
  const s = _cwSafeSettings();
  try {
    const r = await _cxTranslateOnce(BACKEND + "/creator/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titles, use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (!d.ok || !Array.isArray(d.translations)) {
      if (d && d.message) _cwSetVideoNote("翻译出错：" + d.message);
      return;
    }
    const box = document.getElementById("cwVideos");
    let filled = 0;
    d.translations.forEach((zh, k) => {
      const i = idxs[k];
      const z = (zh || "").trim();
      if (!z || !_cwVideos[i] || z === (_cwVideos[i].title || "").trim()) return;
      _cwVideos[i].title_zh = z;   // 存下来，翻页/重渲染也在
      filled++;
      // 改动1：填进预留的占位 .cw-v-zh，而不是新插一行（不再把下面顶下去）
      if (box) {
        const cb = box.querySelector('.cw-vcb[data-i="' + i + '"]');
        const main = cb ? cb.closest(".cw-video").querySelector(".cw-v-main") : null;
        const zhEl = main ? main.querySelector(".cw-v-zh") : null;
        if (zhEl) zhEl.textContent = "🌐 " + z;
      }
    });
    // 后端明确说翻不动（本地没起 + 网页不可用）→ 轻提示
    if (filled === 0 && d.note) _cwSetVideoNote(d.note);
  } catch (e) {}
}

// 改动5：视频区轻状态（翻译进度/失败提示），写到 #cwVideoState 末尾，几秒淡出
let _cwVideoNoteTimer = null;
function _cwSetVideoNote(msg) {
  const st = document.getElementById("cwVideoState");
  if (!st || !msg) return;
  const base = st.dataset.base != null ? st.dataset.base : st.textContent;
  st.dataset.base = base;
  st.textContent = base + "　·　🌐 " + msg;
  if (_cwVideoNoteTimer) { clearTimeout(_cwVideoNoteTimer); }
  _cwVideoNoteTimer = setTimeout(() => {
    if (st.dataset.base != null) { st.textContent = st.dataset.base; delete st.dataset.base; }
  }, 8000);
}

// ─── 改动4：分页 + 跨页选择（用 _cwSelectedVids Set，覆盖所有页）───

// CSS 选择器里安全转义 vid（vid 里可能有特殊字符）
function _cwCssEsc(s) {
  s = String(s == null ? "" : s);
  return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/["\\\]\[]/g, "\\$&");
}

// 当前每页条数（读输入框，至少 1）
function _cwGetPageSize() {
  const el = document.getElementById("cwPageSize");
  let n = parseInt((el && el.value) || _cwPageSize, 10);
  if (!n || n < 1) n = _cwPageSize || 20;
  _cwPageSize = n;
  return n;
}

function _cwPageCount() {
  const size = _cwGetPageSize();
  return Math.max(1, Math.ceil((_cwVideos.length || 0) / size));
}

// 把 _cwPage 夹到 [1, 总页数]
function _cwClampPage() {
  const tp = _cwPageCount();
  if (_cwPage > tp) _cwPage = tp;
  if (_cwPage < 1) _cwPage = 1;
}

// 当前页的 {v, i}（i 是它在 _cwVideos 里的全局下标）
function _cwPageItems() {
  const size = _cwGetPageSize();
  const start = (_cwPage - 1) * size;
  const out = [];
  for (let i = start; i < Math.min(start + size, _cwVideos.length); i++) {
    out.push({ v: _cwVideos[i], i });
  }
  return out;
}

function renderVideos() {
  const box = document.getElementById("cwVideos");
  if (!box) return;
  try { _cwApplySort(); _cwSortBar(); } catch (_) {}   // v74：按时间 / 热度 / 标题排
  if (!_cwVideos.length) {
    const reason = _cwEmptyReason
      ? ('这个博主没抓到内容。<br><span style="color:var(--text-dim,#888);font-size:12px">原因：' +
         escapeHtml(_cwEmptyReason) + '</span>')
      : "这个博主没列到视频。";
    box.innerHTML = '<div class="cw-empty">' + reason + "</div>";
    _cwRenderPager();
    updateExtractVLabel();
    return;
  }
  _cwClampPage();
  const items = _cwPageItems();
  box.innerHTML = items.map(({ v, i }) => {
    const date = v.when_human ? ('<span class="cw-date">' + escapeHtml(v.when_human) + "</span>")
                              : '<span class="cw-date">日期未知</span>';
    const ago = (v.days_ago != null) ? (v.days_ago + " 天前") : "";
    // 作者（蓝色小标签，醒目）；YouTube 作者即频道名，后端已带上 uploader
    const author = v.uploader
      ? ('<span class="cw-author" style="color:#1a73e8;font-weight:600;background:rgba(26,115,232,0.10);border:1px solid rgba(26,115,232,0.30);border-radius:6px;padding:0 6px;margin-right:6px">👤 ' + escapeHtml(v.uploader) + "</span>")
      : "";
    // 改动1：中文行始终预留占位（空着也占位），翻译回来填进去，不再新插一行
    const zhText = (v.title_zh && v.title_zh !== v.title) ? ("🌐 " + escapeHtml(v.title_zh)) : "";
    const checked = _cwSelectedVids.has(v.vid) ? " checked" : "";   // 改动4：按 Set 回填勾选态
    // 已提取：绿色「已提取」角标 + 置灰禁用的提取按钮
    const done = !!v.extracted;
    const doneBadge = done ? '<span class="cw-done-badge">已提取</span>' : "";
    const getBtn = done
      ? '<button class="sn-btn sm cw-vget is-done" data-i="' + i + '" disabled>已提取</button>'
      : '<button class="sn-btn sm cw-vget" data-i="' + i + '">提取</button>';
    return '' +
      '<div class="cw-video' + (done ? ' is-extracted' : '') + '">' +
        '<input type="checkbox" class="cw-vcb" data-vid="' + escapeHtml(v.vid) + '" data-i="' + i + '"' + checked + " />" +
        '<div class="cw-v-main">' +
          '<div class="cw-v-title">' + doneBadge + escapeHtml(v.title || v.url || "(无标题)") + "</div>" +
          '<div class="cw-v-zh">' + zhText + "</div>" +
          '<div class="cw-v-meta">' + author + date + (ago ? ('<span>' + escapeHtml(ago) + "</span>") : "") +
            '<a class="cw-vlink" href="' + escapeHtml(v.url) + '" target="_blank">原视频↗</a></div>' +
        "</div>" +
        getBtn +
      "</div>";
  }).join("");
  // 勾选 → 更新 Set（跨页保持）
  box.querySelectorAll(".cw-vcb").forEach((cb) => cb.addEventListener("change", (e) => {
    const vid = e.currentTarget.dataset.vid;
    if (e.currentTarget.checked) _cwSelectedVids.add(vid);
    else _cwSelectedVids.delete(vid);
    updateExtractVLabel();
  }));
  box.querySelectorAll(".cw-vget").forEach((b) => b.addEventListener("click", (e) => {
    const v = _cwVideos[parseInt(e.currentTarget.dataset.i, 10)];
    if (!v) return;
    if (v.extracted) { _cwSetStatus("这条之前已经提取过了，无需重复提取。"); return; }
    _cwExtract([{ creator_id: _cwCurrentCreator.id, vid: v.vid, url: v.url, title: v.title }]);
  }));
  _cwRenderPager();
  updateExtractVLabel();
}

// 渲染分页条
function _cwRenderPager() {
  const pager = document.getElementById("cwPager");
  if (!pager) return;
  const total = _cwVideos.length;
  const tp = _cwPageCount();
  if (total <= _cwGetPageSize()) { pager.hidden = true; }   // 一页装得下就不显示
  else { pager.hidden = false; }
  const cur = document.getElementById("cwPageCur"); if (cur) cur.textContent = _cwPage;
  const tot = document.getElementById("cwPageTotal"); if (tot) tot.textContent = tp;
  const prev = document.getElementById("cwPagePrev"); if (prev) prev.disabled = (_cwPage <= 1);
  const next = document.getElementById("cwPageNext"); if (next) next.disabled = (_cwPage >= tp);
  const c = document.getElementById("cwPagerCount");
  if (c) c.textContent = "共 " + total + " 条，已选 " + _cwSelectedVids.size + " 条";
}

// 翻页：只重渲染 + 翻译当前页，不重新 fetch（改动4）
function _cwGotoPage(p) {
  _cwPage = p;
  _cwClampPage();
  renderVideos();
  _cwTranslateTitles();
}

function updateExtractVLabel() {
  const n = _cwSelectedVids.size;   // 改动4：基于 Set（所有页），不读 DOM
  const b = document.getElementById("cwExtractV");
  if (b) b.textContent = "提取选中（" + n + "）";
  _cwRenderPager();   // 同步分页条里的已选计数
}

// 改动4：选中项基于 Set，覆盖所有页（而非只当前 DOM）
function _cwVideoSelected() {
  const out = [];
  const byVid = {};
  for (const v of _cwVideos) byVid[v.vid] = v;
  _cwSelectedVids.forEach((vid) => {
    const v = byVid[vid];
    if (v) out.push({ creator_id: _cwCurrentCreator.id, vid: v.vid, url: v.url });
  });
  return out;
}

// 改动4：按天数筛选对「所有页」生效——直接改 Set，再重渲染回填勾选
function _cwPickByDays(days) {
  let matched = 0;
  for (const v of _cwVideos) {
    if (v && v.days_ago != null && v.days_ago <= days) { _cwSelectedVids.add(v.vid); matched++; }
  }
  renderVideos();
  if (matched === 0) _cwSetStatus("没有「最近 " + days + " 天」内、且带日期的视频（该平台可能没提供发布日期，可改用「全选」或手动勾选）");
  else _cwSetStatus("已选中最近 " + days + " 天内的 " + matched + " 条（所有页）");
}

// 改动4：全选/清空也作用于所有页
function _cwSelectAllVideos() {
  for (const v of _cwVideos) _cwSelectedVids.add(v.vid);
  renderVideos();
}
function _cwClearSelVideos() {
  _cwSelectedVids.clear();
  renderVideos();
}

// 提取入口（单条 / 批量 / 本次新增 共用）
// v89：提示写在按钮旁边（以前只写在页面最上面的「扫描进度」里，往下翻着的时候看不到，像是没反应）
function _cwInlineMsg(btn, msg, cls) {
  if (!btn || !btn.parentNode) return;
  const row = btn.parentNode;
  let el = row.querySelector(":scope > .cw-inline-msg");
  if (!el) {
    el = document.createElement("span");
    row.insertBefore(el, row.querySelector(":scope > .sn-spacer") || null);
  }
  el.className = "cw-inline-msg" + (cls ? " " + cls : "");
  el.textContent = msg || "";
  clearTimeout(el._t);
  if (msg && cls !== "busy") el._t = setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, cls === "warn" ? 10000 : 20000);
}

// 视频页当前选的识别质量（精准 / 超精准…），嗅探里提取的视频也照这个来（以前固定用「均衡」）
function _cwLevel() {
  const el = document.getElementById("videoLevel");
  let v = el && el.value ? el.value : "";
  if (!v) { try { v = localStorage.getItem("videoLevelPick") || ""; } catch (_) {} }
  return v;
}

async function _cwExtract(items, btn, fromFindings) {
  const say = (msg, cls) => { _cwSetStatus(msg); _cwInlineMsg(btn, msg, cls); };
  if (!items || !items.length) { say("先勾选要提取的视频（点每条左边的小方框，或打开「全选」）", "warn"); return; }
  const s = _cwSafeSettings();
  const oldText = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = "提取中…"; }
  say("正在提交 " + items.length + " 条…", "busy");
  try {
    const r = await fetch(BACKEND + "/creator/extract", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items, use_local: s.use_local, model: s.model, mode: "auto", level: _cwLevel() }),
    });
    const d = await r.json();
    if (!d.ok) { say(d.message || "提取失败", "warn"); return; }
    // 后端会跳过「已提取过」的；带上跳过提示，并把成功提取的标记到本地缓存
    const goSee = d.queued ? "，去「视频」页看进度" : (d.x_saved ? "，在「视频」页的笔记里能看到" : "");
    if (d.message) say("✓ " + d.message + goSee, "ok");
    else say("✓ 已把 " + (d.queued || items.length) + " 个视频加入提取队列，去「视频」页看进度", "ok");
    _markItemsExtractedLocal(items);
    if (fromFindings) items.forEach((it) => _cwFindSel.delete(_cwFindKey(it)));
    loadCreatorFindings();
  } catch (e) { say("提取出错：" + e.message, "warn"); }
  finally {
    if (btn) { btn.disabled = false; btn.textContent = oldText; }
    if (fromFindings) _cwFindSelSync();
    else if (typeof updateExtractVLabel === "function") { try { updateExtractVLabel(); } catch (_) {} }
  }
}

// 把刚送队列的视频，在本地几份列表里就地标成「已提取」，界面立刻更新，不必等重新拉取
function _markItemsExtractedLocal(items) {
  const keys = new Set();
  const urls = new Set();
  (items || []).forEach((it) => {
    const cid = (it.creator_id == null ? "" : String(it.creator_id));
    const vid = (it.vid == null ? "" : String(it.vid));
    if (vid) keys.add(cid + "|" + vid);
    if (it.url) urls.add(it.url);
  });
  const hit = (x) => {
    if (!x) return false;
    const cid = (x.creator_id == null ? "" : String(x.creator_id));
    const vid = (x.vid == null ? "" : String(x.vid));
    if (vid && keys.has(cid + "|" + vid)) return true;
    if (x.url && urls.has(x.url)) return true;
    return false;
  };
  [_dgItems, _dgUndated, _cwVideos, _cwFindings].forEach((arr) => {
    if (Array.isArray(arr)) arr.forEach((x) => { if (hit(x)) x.extracted = true; });
  });
}

// 「按时间看全部」里单条提取：成功后就地标已提取并刷新该行
async function _cwExtractSingle(it, btn) {
  if (!it) return;
  const s = _cwSafeSettings();
  if (btn) { btn.disabled = true; btn.textContent = "提取中…"; }
  try {
    const r = await fetch(BACKEND + "/creator/extract", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: [{ creator_id: it.creator_id, vid: it.vid, url: it.url, title: it.title }],
        use_local: s.use_local, model: s.model, mode: "auto",
      }),
    });
    const d = await r.json();
    if (!d.ok) {
      _dgSetStat('<span style="color:#dc2626">✗ ' + escapeHtml(d.message || "提取失败") + "</span>");
      if (btn) { btn.disabled = false; btn.textContent = "提取"; }
      return;
    }
    if (d.skipped && !d.queued) {
      _dgSetStat('<span style="color:#16a34a">这条之前已经提取过了，无需重复提取。</span>');
    } else {
      _dgSetStat('<span style="color:#16a34a">✓ ' + escapeHtml(d.message || "已加入提取队列") + "，去「视频」页看进度</span>");
    }
    _markItemsExtractedLocal([{ creator_id: it.creator_id, vid: it.vid, url: it.url }]);
    _dgSelected.delete(it.vid);
    // 刚在这个博主下操作过，保持它展开（不要因为新视频数变 0 就自动折叠）
    if (it.creator_id != null) _dgExpandedGroups.add(String(it.creator_id));
    renderDigest([]);
    loadCreatorFindings();
  } catch (e) {
    _dgSetStat('<span style="color:#dc2626">✗ 提取出错：' + escapeHtml(e.message) + "</span>");
    if (btn) { btn.disabled = false; btn.textContent = "提取"; }
  }
}

// ════════════════════════════════════════════════════════════
// 新版块：近期汇总（所有关注博主近 N 天发的视频，汇总在一起）
// ════════════════════════════════════════════════════════════
let _dgLoadedOnce = false;          // 首次切到该 tab 才自动加载
let _dgDays = 3;                    // 当前天数窗口
let _dgItems = [];                  // 当前窗口内（带日期）的视频
let _dgUndated = [];               // 无日期的视频（可选显示）
let _dgSelected = new Set();        // 选中的 vid（跨博主）
let _dgShowUndated = false;
let _dgCollapsedGroups = new Set();  // 用户手动「折叠」的博主分组 key
let _dgExpandedGroups = new Set();    // 用户手动「展开」的博主分组 key（覆盖默认折叠）

// 数字状态行
function _dgSetStat(html) {
  const el = document.getElementById("dgStat");
  if (el) el.innerHTML = html || "";
}

// 拉取汇总数据（恢复成以前的「直接加载」）：
//  · 默认：每个博主先吃缓存、缓存没有的当场直接联网列出来（后端每个博主有 120s 超时上限）。
//  · refresh=true：所有博主重新联网列一遍。
// 加载时显示「正在加载，请稍候…」，不再做秒出+后台补全那套。
async function loadDigest(refresh) {
  const box = document.getElementById("dgList");
  const rb = document.getElementById("dgRefreshBtn");
  const note = document.getElementById("dgInlineNote");
  if (box) box.innerHTML = _cwSkeletonRows(6);
  _dgSetStat(refresh ? "正在联网刷新，请稍候…" : "正在加载视频列表，请稍候…");
  if (note) { note.textContent = refresh ? "正在联网刷新，请稍候…" : "正在加载视频列表，请稍候…（首次或没缓存的博主要联网，会慢一点）"; note.hidden = false; note.classList.add("loading"); }
  if (rb) { rb.disabled = true; rb.textContent = "刷新中…"; }
  // 先确保「本次新增」清单已拉到（给汇总里属于新视频的条目打「新」角标）
  try {
    if (!Array.isArray(_cwFindings) || !_cwFindings.length) {
      const fr = await fetch(BACKEND + "/creator/findings");
      const fd = await fr.json();
      if (fd && Array.isArray(fd.findings)) _cwFindings = fd.findings;
    }
  } catch (e) {}
  try {
    const r = await fetch(BACKEND + "/creator/gather", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days: _dgDays, refresh: !!refresh, per_timeout: 120 }),
    });
    const d = await r.json();
    if (!d.ok) {
      _dgItems = []; _dgUndated = [];
      if (box) box.innerHTML = '<div class="dg-empty">汇总失败：' + escapeHtml(d.message || "后端没有响应这个功能") +
        '<br><br>如果刚更新过文件，请<b>完全退出并重新打开</b>超能小助（后端 Python 要重启才会加载新接口）。</div>';
      _dgSetStat("");
      if (note) { note.classList.remove("loading"); note.hidden = true; }
      return;
    }
    _dgItems = d.items || [];
    _dgUndated = d.undated || [];
    // 清理选中集里已不存在的项
    const live = new Set([..._dgItems, ..._dgUndated].map((x) => x.vid));
    _dgSelected.forEach((v) => { if (!live.has(v)) _dgSelected.delete(v); });
    // 顶部数字总览
    let stat = "近 <b>" + d.days + "</b> 天 · <b>" + (d.in_window || 0) + "</b> 条新视频 · 来自 <b>" +
               (d.creators_ok || 0) + "/" + (d.creators_total || 0) + "</b> 位博主";
    if (d.undated_count) stat += " · 另有 " + d.undated_count + " 条无日期";
    if (d.generated_at) stat += "　·　" + escapeHtml(d.generated_at);
    _dgSetStat(stat);
    // 有博主这次没列到（超时/被限流）→ 给个轻提示，不挡内容
    const miss = Array.isArray(d.uncached) ? d.uncached.length : 0;
    if (note) {
      note.classList.remove("loading");
      if (miss) { note.textContent = miss + " 位博主这次没列到（超时/被限流），点「🔄 联网刷新」可再试。"; note.hidden = false; }
      else { note.hidden = true; }
    }
    renderDigest(d.errors || []);
    _dgTranslate();
  } catch (e) {
    if (box) box.innerHTML = '<div class="dg-empty">出错：' + escapeHtml(e.message) + "</div>";
    _dgSetStat("");
    if (note) { note.classList.remove("loading"); note.hidden = true; }
  } finally {
    if (rb) { rb.disabled = false; rb.textContent = "🔄 联网刷新"; }
  }
}

// 渲染：按博主分组，组内按时间倒序
function renderDigest(errors) {
  const box = document.getElementById("dgList");
  if (!box) return;
  const list = _dgShowUndated ? _dgItems.concat(_dgUndated) : _dgItems;

  let html = "";
  // 出错的博主（联网刷新时某些列不到）提示在最上面
  (errors || []).forEach((er) => {
    html += '<div class="dg-err">⚠ <b>' + escapeHtml(er.title || "某博主") + '</b>：' + escapeHtml(er.error || "列不到") + "</div>";
  });

  if (!list.length) {
    box.innerHTML = html + '<div class="dg-empty">这 ' + _dgDays + ' 天，关注的博主没有发布带日期的新视频。' +
      (_dgUndated.length && !_dgShowUndated ? '<br>（有 ' + _dgUndated.length + ' 条无发布日期的视频，可勾选右上「显示无日期」查看）' : '') +
      '<br><br>想要最新的可点右上「🔄 联网刷新」。</div>';
    _dgUpdateExtractLabel();
    return;
  }

  // 分组
  const groups = [];
  const idx = {};
  for (const it of list) {
    const key = it.creator_id || it.creator_title;
    if (idx[key] == null) { idx[key] = groups.length; groups.push({ key, title: it.creator_title, platform: it.platform, plabel: it.platform_label, items: [] }); }
    groups[idx[key]].items.push(it);
  }
  // 组内排序：有日期的按天数升序，无日期排后
  groups.forEach((g) => g.items.sort((a, b) => {
    const da = a.days_ago == null ? 1e9 : a.days_ago;
    const db = b.days_ago == null ? 1e9 : b.days_ago;
    return da - db;
  }));

  // 「新视频」的定义：在时间窗口内（已经过滤过）+ 还没被提取过。
  // 已提取的不再算作「新」，但仍保留在列表里（标「已提取」）。
  for (const g of groups) {
    // 这个博主有几条「未提取」的——这才是真正的新视频数
    g._newCount = g.items.filter((it) => !it.extracted).length;
  }

  for (const g of groups) {
    // 博主头像：用名字首字做「字母头像」（清楚表示这是博主/频道，不再用 ▶ 播放图标，免得被当成视频）
    const gname = (g.title || "未命名").trim();
    const letter = escapeHtml((gname[0] || "?").toUpperCase());
    // 平台放到名字下方那行（YouTube / B站 / 抖音），头像只表示「这是个博主」
    const platTxt = escapeHtml(g.plabel || "");
    const gkey = String(g.key);
    const newCount = g._newCount || 0;
    // 默认折叠规则：有未提取的新视频→默认展开；没有（全已提取/无新）→默认折叠。
    // 用户手动点过的以 _dgCollapsedGroups / _dgExpandedGroups 记忆为准。
    let collapsed;
    if (_dgExpandedGroups.has(gkey)) collapsed = false;
    else if (_dgCollapsedGroups.has(gkey)) collapsed = true;
    else collapsed = (newCount === 0);   // 没手动操作过 → 看有没有新视频
    // 角标：只在有未提取新视频时显示「X 条新视频」；否则不显示
    const cntHtml = newCount > 0
      ? '<span class="dg-group-cnt">' + newCount + " 条新视频</span>"
      : '<span class="dg-group-cnt dg-group-cnt-none">已全部提取</span>';
    html += '<div class="dg-group' + (collapsed ? ' collapsed' : '') +
            '" data-gkey="' + escapeHtml(gkey) + '">';
    html += '<div class="dg-group-head" data-gtoggle="' + escapeHtml(gkey) + '">' +
      '<div class="dg-group-ava dg-creator-ava">' + letter + "</div>" +
      '<div class="dg-group-info">' +
        '<div class="dg-group-name"><span class="dg-creator-tag">博主</span>' + escapeHtml(gname) + "</div>" +
        '<div class="dg-group-meta">' + platTxt + "</div></div>" +
      cntHtml +
      '<span class="dg-group-caret">▼</span>' +
      "</div>";
    html += '<div class="dg-group-body">';
    html += g.items.map((it) => {
      const checked = _dgSelected.has(it.vid) ? " checked" : "";
      const when = it.when_human ? ('<span class="cw-date">' + escapeHtml(it.when_human) + "</span>")
                                 : '<span class="cw-date">无日期</span>';
      const ago = (it.days_ago != null) ? ('<span>' + it.days_ago + " 天前</span>") : "";
      // 中文标题：有就显示，没有先占位（翻译回来填）
      const zh = (it.title_zh && it.title_zh !== it.title)
        ? ('<div class="cw-v-zh">🌐 ' + escapeHtml(it.title_zh) + "</div>")
        : '<div class="cw-v-zh"></div>';
      // 已提取：标绿色「已提取」角标 + 把「提取」按钮置灰、改文案、禁用
      const done = !!it.extracted;
      // 「新」标签：只有「未提取」的才算新（已提取的不再标新）
      const newBadge = !done ? '<span class="cw-new-badge">新</span>' : "";
      const doneBadge = done ? '<span class="cw-done-badge">已提取</span>' : "";
      const getBtn = done
        ? '<button class="sn-btn sm dg-get is-done" data-vid="' + escapeHtml(it.vid) + '" disabled>已提取</button>'
        : '<button class="sn-btn sm dg-get" data-vid="' + escapeHtml(it.vid) + '">提取</button>';
      const platIcon = _CW_PLAT_ICON[it.platform] || "🔗";
      // 每条都自带：平台图标 + 博主名 tag，信息更全（和「扫出来的新视频」一致）
      return '' +
        '<div class="cw-video' + (done ? ' is-extracted' : '') + '">' +
          '<input type="checkbox" class="dg-cb" data-vid="' + escapeHtml(it.vid) + '"' + checked + " />" +
          '<div class="cw-v-main">' +
            '<div class="cw-v-title">' + newBadge + doneBadge + platIcon + " " + escapeHtml(it.title || it.url || "(无标题)") + "</div>" +
            zh +
            '<div class="cw-v-meta">' +
              '<span class="cw-tag cw-tag-au">' + _cwMiniAv(it.creator_id, it.creator_title || g.title) + escapeHtml(it.creator_title || g.title || "") + "</span>" +
              when + ago +
              '<a class="cw-vlink" href="' + escapeHtml(it.url) + '" target="_blank">原视频↗</a></div>' +
          "</div>" +
          getBtn +
        "</div>";
    }).join("");
    html += "</div>";   // /dg-group-body
    html += "</div>";   // /dg-group
  }
  box.innerHTML = html;

  // 点博主头：折叠/展开这一组（并记住用户的手动选择，覆盖默认规则）
  box.querySelectorAll(".dg-group-head[data-gtoggle]").forEach((head) => {
    head.addEventListener("click", (e) => {
      // 点头部里的链接/按钮不触发折叠
      if (e.target.closest("a,button,input")) return;
      const k = head.dataset.gtoggle;
      const grp = head.closest(".dg-group");
      const willCollapse = !grp.classList.contains("collapsed");
      grp.classList.toggle("collapsed", willCollapse);
      // 记住手动选择：折叠则进 collapsed 集、展开则进 expanded 集（互斥）
      if (willCollapse) { _dgCollapsedGroups.add(k); _dgExpandedGroups.delete(k); }
      else { _dgExpandedGroups.add(k); _dgCollapsedGroups.delete(k); }
    });
  });

  // 勾选 → Set
  box.querySelectorAll(".dg-cb").forEach((cb) => cb.addEventListener("change", (e) => {
    const vid = e.currentTarget.dataset.vid;
    if (e.currentTarget.checked) _dgSelected.add(vid); else _dgSelected.delete(vid);
    _dgSyncSelAll();
    _dgUpdateExtractLabel();
  }));
  // 单条提取
  box.querySelectorAll(".dg-get").forEach((b) => b.addEventListener("click", (e) => {
    const it = _dgFind(e.currentTarget.dataset.vid);
    if (!it) return;
    if (it.extracted) {
      _dgSetStat('<span style="color:#16a34a">这条之前已经提取过了，无需重复提取。</span>');
      return;
    }
    _cwExtractSingle(it, e.currentTarget);
  }));
  _dgSyncSelAll();
  _dgUpdateExtractLabel();
}

function _dgFind(vid) {
  return _dgItems.concat(_dgUndated).find((x) => x.vid === vid) || null;
}

function _dgSelectedItems() {
  const all = _dgItems.concat(_dgUndated);
  const out = [];
  _dgSelected.forEach((vid) => {
    const it = all.find((x) => x.vid === vid);
    if (it) out.push({ creator_id: it.creator_id, vid: it.vid, url: it.url,
                       title: it.title, extracted: !!it.extracted });
  });
  return out;
}

function _dgUpdateExtractLabel() {
  const b = document.getElementById("dgExtractBtn");
  if (!b) return;
  // 正在提取 / 刚提取完的反馈期间，不要被这个函数把文字覆盖回去
  if (b.dataset.busy === "1" || b.dataset.flash === "1") return;
  b.textContent = "提取选中（" + _dgSelected.size + "）";
  b.disabled = _dgSelected.size === 0;   // 没勾选时置灰，避免空点没反应
}

// 「按时间看全部」里的「提取选中」专用提取：带明确的按钮反馈
// （原来直接调 _cwExtract，状态提示写在左侧「博主更新」面板里，这边看不到，
//   用户点了像没反应。这里把反馈做在按钮本身 + 按钮上方的 dgStat 行。）
async function _dgExtractSelected() {
  const b = document.getElementById("dgExtractBtn");
  const items = _dgSelectedItems();
  if (!items.length) {
    // 没勾选：按钮抖一下 + 上方提示，而不是悄无声息
    if (b) {
      const old = b.textContent;
      b.textContent = "先勾选视频";
      b.dataset.flash = "1";
      setTimeout(() => { b.dataset.flash = ""; _dgUpdateExtractLabel(); }, 1500);
    }
    _dgSetStat('<span style="color:var(--accent)">请先勾选要提取的视频（或点「全选」）。</span>');
    return;
  }

  const n = items.length;
  // —— 进入「提取中」：禁用 + 改字 + 防重复点 ——
  if (b) {
    b.dataset.busy = "1";
    b.disabled = true;
    b.textContent = "提取中…（" + n + "）";
  }
  _dgSetStat('正在把 ' + n + ' 个视频加入提取队列…');

  let okMsg = "", errMsg = "", allSkipped = false;
  try {
    const s = _cwSafeSettings();
    const r = await fetch(BACKEND + "/creator/extract", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items, use_local: s.use_local, model: s.model, mode: "auto" }),
    });
    const d = await r.json();
    if (!d.ok) { errMsg = d.message || "提取失败"; }
    else {
      const q = (d.queued != null) ? d.queued : n;
      allSkipped = (q === 0 && (d.skipped || 0) > 0);
      // 后端的 message 已经把「提取 X 个 / 跳过 Y 个」写清楚了，直接用
      okMsg = (d.message ? d.message : ("已把 " + q + " 个视频加入提取队列")) + "，去「视频」页看进度";
      // 把这次选中的都就地标成「已提取」（含本来就跳过的），并清掉勾选避免重复提交
      _markItemsExtractedLocal(items);
      _dgSelected.clear();
      loadCreatorFindings();
    }
  } catch (e) {
    errMsg = "提取出错：" + e.message;
  }

  // —— 退出「提取中」，进入短暂的「结果反馈」态 ——
  if (b) b.dataset.busy = "";
  if (okMsg) {
    if (b) {
      b.dataset.flash = "1";
      b.textContent = allSkipped ? "✓ 都提取过了" : "✓ 已加入队列";
      b.style.background = "#16a34a";
      b.style.borderColor = "#16a34a";
      b.style.color = "#fff";
      setTimeout(() => {
        b.dataset.flash = "";
        b.style.background = "";
        b.style.borderColor = "";
        b.style.color = "";
        _dgUpdateExtractLabel();
      }, 2600);
    }
    _dgSetStat('<span style="color:#16a34a">✓ ' + escapeHtml(okMsg) + '</span>');
    // 刚提取过的那些博主，保持展开（别因为新视频数变 0 就自动折叠）
    (items || []).forEach((it) => {
      if (it && it.creator_id != null) _dgExpandedGroups.add(String(it.creator_id));
    });
    // 同步刷新视图里的勾选态（已清空）+ 重渲染让「已提取」角标显示出来
    _dgSyncSelAll();
    renderDigest([]);
  } else {
    if (b) {
      b.dataset.flash = "1";
      b.textContent = "✗ 提取失败";
      b.style.background = "#dc2626";
      b.style.borderColor = "#dc2626";
      b.style.color = "#fff";
      setTimeout(() => {
        b.dataset.flash = "";
        b.style.background = "";
        b.style.borderColor = "";
        b.style.color = "";
        _dgUpdateExtractLabel();
      }, 2600);
    }
    _dgSetStat('<span style="color:#dc2626">✗ ' + escapeHtml(errMsg || "提取失败") + '</span>');
  }
}

// 同步「全选」勾选态
function _dgSyncSelAll() {
  const list = _dgShowUndated ? _dgItems.concat(_dgUndated) : _dgItems;
  const sa = document.getElementById("dgSelAll");
  if (!sa) return;
  const selectedInView = list.filter((x) => _dgSelected.has(x.vid)).length;
  sa.checked = list.length > 0 && selectedInView === list.length;
}

// 翻译当前可见、未翻的英文标题（复用 /creator/translate）
async function _dgTranslate() {
  const box = document.getElementById("dgList");
  if (!box) return;
  const list = _dgShowUndated ? _dgItems.concat(_dgUndated) : _dgItems;
  const todo = [];
  for (const it of list) {
    const t = (it.title || "").trim();
    if (!t || it.title_zh || /[\u4e00-\u9fff]/.test(t)) continue;
    todo.push(it);
  }
  if (!todo.length) return;
  const s = _cwSafeSettings();
  try {
    const r = await _cxTranslateOnce(BACKEND + "/creator/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titles: todo.map((x) => x.title), use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (!d.ok || !Array.isArray(d.translations)) return;
    d.translations.forEach((zh, k) => {
      const it = todo[k];
      const z = (zh || "").trim();
      if (!z || !it || z === (it.title || "").trim()) return;
      it.title_zh = z;
      const cb = box.querySelector('.dg-cb[data-vid="' + _cwCssEsc(it.vid) + '"]');
      const zhEl = cb ? cb.closest(".cw-video").querySelector(".cw-v-zh") : null;
      if (zhEl) zhEl.textContent = "🌐 " + z;
    });
  } catch (e) {}
}

// ─ 近期汇总：事件绑定 ─
document.getElementById("dgSeg")?.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-days]");
  if (!b) return;
  document.querySelectorAll("#dgSeg button").forEach((x) => x.classList.toggle("active", x === b));
  _dgDays = parseInt(b.dataset.days, 10) || 7;
  const inp = document.getElementById("dgDaysInput"); if (inp) inp.value = _dgDays;
  loadDigest(false);
});
document.getElementById("dgDaysGo")?.addEventListener("click", () => {
  const inp = document.getElementById("dgDaysInput");
  let v = parseInt((inp && inp.value) || "7", 10);
  if (!v || v < 1) v = 7; if (v > 365) v = 365;
  _dgDays = v;
  // 自定义天数 → 取消段选中的高亮（除非正好等于预设）
  document.querySelectorAll("#dgSeg button").forEach((x) => x.classList.toggle("active", parseInt(x.dataset.days, 10) === v));
  loadDigest(false);
});
document.getElementById("dgDaysInput")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("dgDaysGo")?.click(); }
});
document.getElementById("dgRefreshBtn")?.addEventListener("click", () => loadDigest(true));
document.getElementById("dgShowUndated")?.addEventListener("change", (e) => {
  _dgShowUndated = e.target.checked;
  renderDigest([]);
  _dgTranslate();
});
document.getElementById("dgSelAll")?.addEventListener("change", (e) => {
  const list = _dgShowUndated ? _dgItems.concat(_dgUndated) : _dgItems;
  if (e.target.checked) list.forEach((x) => _dgSelected.add(x.vid));
  else list.forEach((x) => _dgSelected.delete(x.vid));
  renderDigest([]);
});
document.getElementById("dgExtractBtn")?.addEventListener("click", () => _dgExtractSelected());

// ─── 事件绑定 ───
// 一个简易的输入弹层（Electron 不支持原生 prompt，所以自己做一个）。
// 返回 Promise<string|null>：用户点确定返回输入内容，点取消/关闭返回 null。
function _cwPromptModal(opts) {
  opts = opts || {};
  return new Promise((resolve) => {
    const ov = document.createElement("div");
    ov.style.cssText =
      "position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.45);" +
      "display:flex;align-items:center;justify-content:center;padding:24px";
    const box = document.createElement("div");
    box.style.cssText =
      "background:var(--bg-elev,#fff);color:var(--text,#1a1a1a);border-radius:12px;" +
      "max-width:560px;width:100%;box-shadow:0 12px 40px rgba(0,0,0,0.3);" +
      "padding:20px 22px;font-size:14px;line-height:1.6";
    const h = document.createElement("div");
    h.style.cssText = "font-weight:700;font-size:16px;margin-bottom:10px";
    h.textContent = opts.title || "请输入";
    const desc = document.createElement("div");
    desc.style.cssText =
      "white-space:pre-wrap;color:var(--text-dim,#666);font-size:13px;margin-bottom:12px";
    desc.textContent = opts.desc || "";
    const ta = document.createElement("textarea");
    ta.placeholder = opts.placeholder || "";
    ta.style.cssText =
      "width:100%;min-height:96px;resize:vertical;box-sizing:border-box;" +
      "border:1px solid var(--line,#ccc);border-radius:8px;padding:9px 11px;" +
      "font-size:13px;font-family:inherit;background:var(--bg,#fafafa);color:var(--text,#1a1a1a)";
    const btns = document.createElement("div");
    btns.style.cssText = "display:flex;justify-content:flex-end;gap:10px;margin-top:14px";
    const cancel = document.createElement("button");
    cancel.textContent = "取消";
    cancel.style.cssText =
      "padding:7px 16px;border-radius:7px;border:1px solid var(--line,#ccc);" +
      "background:transparent;color:var(--text,#333);cursor:pointer;font-size:13px";
    const ok = document.createElement("button");
    ok.textContent = opts.okText || "确定";
    ok.style.cssText =
      "padding:7px 16px;border-radius:7px;border:none;background:#1a73e8;" +
      "color:#fff;cursor:pointer;font-size:13px;font-weight:600";
    function close(val) {
      try { document.body.removeChild(ov); } catch (_) {}
      resolve(val);
    }
    cancel.addEventListener("click", () => close(null));
    ok.addEventListener("click", () => close(ta.value));
    ov.addEventListener("click", (e) => { if (e.target === ov) close(null); });
    btns.appendChild(cancel); btns.appendChild(ok);
    box.appendChild(h); box.appendChild(desc); box.appendChild(ta); box.appendChild(btns);
    ov.appendChild(box);
    document.body.appendChild(ov);
    setTimeout(() => ta.focus(), 30);
  });
}

// 判断一个链接/平台是不是 X
function _cwIsX(url, platform) {
  if (platform === "x") return true;
  const u = (url || "").toLowerCase();
  return u.includes("x.com/") || u.includes("twitter.com/");
}

// X 需要登录 Cookie：没配过就弹框让用户粘。返回 true=可以继续添加，false=用户取消
async function _cwEnsureXCookie() {
  try {
    const r = await fetch(BACKEND + "/creator/x_cookie_status");
    const d = await r.json();
    if (d && d.has_cookie) return true;   // 已配置过，直接继续
  } catch (_) { /* 查不到就当没配，往下弹框 */ }

  const desc =
    "添加 X（推特）博主需要你的登录 Cookie（X 现在不登录看不了主页）。\n\n" +
    "怎么拿：在浏览器里打开并登录 x.com → 按 F12 打开开发者工具 → 顶部选「应用 / Application」→ " +
    "左侧「Cookie」→ 点 https://x.com → 把整页 Cookie 复制过来。\n\n" +
    "把整串 Cookie 粘到下面（必须包含 auth_token 和 ct0）。Cookie 只需粘一次，之后所有 X 博主共用。";
  const ck = await _cwPromptModal({
    title: "粘贴 X（推特）登录 Cookie",
    desc: desc,
    placeholder: "auth_token=...; ct0=...; guest_id=...",
    okText: "保存并继续",
  });
  if (ck === null) return false;          // 用户取消
  if (!ck.trim()) { alert("没粘到 Cookie，已取消。"); return false; }
  try {
    const sr = await fetch(BACKEND + "/creator/x_cookie_save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie: ck.trim() }),
    });
    const sd = await sr.json();
    if (!sd.ok) { alert(sd.message || "Cookie 保存失败"); return false; }
    return true;
  } catch (e) {
    alert("保存 Cookie 出错：" + e.message);
    return false;
  }
}

document.getElementById("cwAddBtn")?.addEventListener("click", async () => {
  const url = document.getElementById("cwAddUrl").value.trim();
  const platform = document.getElementById("cwAddPlatform").value;
  const title = document.getElementById("cwAddTitle").value.trim();
  if (!url) { alert("填一个博主主页链接"); return; }
  // X 平台：先确保有登录 Cookie（没有就弹框让用户粘），用户取消则不添加
  if (_cwIsX(url, platform)) {
    const ok = await _cwEnsureXCookie();
    if (!ok) return;
  }
  const btn = document.getElementById("cwAddBtn");
  const old = btn ? btn.textContent : "";
  if (btn && !title) { btn.textContent = "识别中…"; btn.disabled = true; }
  try {
    const r = await fetch(BACKEND + "/creator/add", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, platform, title }),
    });
    const d = await r.json();
    if (!d.ok) { alert(d.message || "添加失败"); return; }
    document.getElementById("cwAddUrl").value = "";
    document.getElementById("cwAddTitle").value = "";
    if (d.title && !d.detected && !title) {
      // 没识别出真名，用了占位名 —— 友好提示一下
      // （点这个博主「查看视频」时还会再尝试识别一次并自动改名）
    }
    loadCreators();
  } catch (e) { alert("添加出错：" + e.message); }
  finally { if (btn) { btn.textContent = old; btn.disabled = false; } }
});

document.getElementById("cwScanAll")?.addEventListener("click", async () => {
  _cwSetScanAllBusy(true);   // 改动2：点击即按钮禁用 + 文案改「扫描中…」
  // 先把上一轮明细清掉，展开容器等本轮进度
  const logBox = document.getElementById("cwScanLog");
  if (logBox) { logBox.hidden = false; logBox.innerHTML = '<div class="cw-scanlog-cur">⏳ 批量扫描启动中…</div>'; }
  try {
    const r = await fetch(BACKEND + "/creator/scan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const d = await r.json();
    if (!d.ok) { _cwSetScanAllBusy(false); _cwSetStatus(d.message || "启动失败"); return; }
    const st = document.getElementById("cwScanState");
    if (st) st.textContent = "⏳ 批量扫描启动中…";
    loadCreatorFindings();   // 进入轮询，loadCreatorFindings 会接管按钮恢复 + 明细渲染
  } catch (e) { _cwSetScanAllBusy(false); _cwSetStatus("出错：" + e.message); }
});

document.getElementById("cwCfgSave")?.addEventListener("click", async () => {
  const auto = document.getElementById("cwAuto").checked;
  const hour = parseInt(document.getElementById("cwHour").value, 10);
  const per_scan = parseInt(document.getElementById("cwPerScan").value, 10);
  try {
    await fetch(BACKEND + "/creator/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto, hour, per_scan }),
    });
    const b = document.getElementById("cwCfgSave");
    const old = b.textContent; b.textContent = "✓"; setTimeout(() => { b.textContent = old; }, 1500);
  } catch (e) {}
});

document.getElementById("cwSelAll")?.addEventListener("change", (e) => {
  const on = e.target.checked;
  _cwFindSel = new Set(on ? (Array.isArray(_cwFindings) ? _cwFindings : []).map(_cwFindKey) : []);
  const box = document.getElementById("cwFindings");
  if (box) box.querySelectorAll(".cw-fcb").forEach((cb) => { cb.checked = on; });
  _cwFindSelSync();
});

document.getElementById("cwExtractBtn")?.addEventListener("click", (e) =>
  _cwExtract(_cwSelectedItems(), e.currentTarget, true));

document.getElementById("cwDismissBtn")?.addEventListener("click", async () => {
  const items = _cwSelectedItems();
  if (!items.length) { _cwSetStatus("先勾选要忽略的视频"); return; }
  try {
    await fetch(BACKEND + "/creator/dismiss", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });
    loadCreatorFindings();
  } catch (e) {}
});

document.getElementById("cwClearBtn")?.addEventListener("click", async () => {
  if (!confirm("清空「本次新增」列表？（清空后这些视频不会再被当作新视频报出来）")) return;
  try {
    await fetch(BACKEND + "/creator/clear", { method: "POST" });
    loadCreatorFindings();
  } catch (e) {}
});

// 视频清单工具条
document.getElementById("cwBack")?.addEventListener("click", backToDigest);
document.getElementById("cwVideoRefresh")?.addEventListener("click", () => loadCreatorVideos(false));
document.getElementById("cwShowAll")?.addEventListener("click", () => {
  const inp = document.getElementById("cwVideoLimit");
  if (inp) inp.value = "";   // 空 = 全部（「重置」抓取条数为全部）
  _cwPage = 1;
  loadCreatorVideos(false);
});
// 改动4：全选/清空对「所有页」生效（基于 Set）
document.getElementById("cwSelAllV")?.addEventListener("click", _cwSelectAllVideos);
document.getElementById("cwClearSelV")?.addEventListener("click", _cwClearSelVideos);
document.getElementById("cwPick7")?.addEventListener("click", () => _cwPickByDays(7));
document.getElementById("cwPick30")?.addEventListener("click", () => _cwPickByDays(30));
document.getElementById("cwExtractV")?.addEventListener("click", (e) => _cwExtract(_cwVideoSelected(), e.currentTarget));
// 改动4：分页控制——翻页只重渲染当前页 + 翻当前页，不重新 fetch
document.getElementById("cwPagePrev")?.addEventListener("click", () => _cwGotoPage(_cwPage - 1));
document.getElementById("cwPageNext")?.addEventListener("click", () => _cwGotoPage(_cwPage + 1));
document.getElementById("cwPageSize")?.addEventListener("change", () => { _cwPage = 1; renderVideos(); _cwTranslateTitles(); });
// 改「抓取条数」后回车 / 失焦 → 重新抓取（条数变了必须重新 fetch）
(function () {
  const inp = document.getElementById("cwVideoLimit");
  if (!inp) return;
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { _cwPage = 1; loadCreatorVideos(false); } });
  inp.addEventListener("change", () => { _cwPage = 1; loadCreatorVideos(false); });
})();
document.getElementById("sniffClearBtn")?.addEventListener("click", async () => {
  if (!confirm("清空时间线？（嗅探源和快照保留）")) return;
  try { await fetch(BACKEND + "/sniff/feed/clear", { method: "POST" }); loadSniffFeed(); } catch (e) {}
});

document.getElementById("sniffRunBtn")?.addEventListener("click", async () => {
  const s = settings();
  try {
    const r = await fetch(BACKEND + "/sniff/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    if (!d.ok) { alert(d.message || "启动失败"); return; }
    const panel = document.getElementById("sniffProgress");
    if (panel) panel.hidden = false;
    document.getElementById("sniffProgStage").textContent = "准备开始…";
    document.getElementById("sniffProgList").innerHTML = "";
    startSniffPolling();
  } catch (e) { alert("出错：" + e.message); }
});

function startSniffPolling() {
  if (_sniffTimer) clearInterval(_sniffTimer);
  _sniffTimer = setInterval(loadSniffFeed, 1500);
}

// 逐源状态 → 图标 + 样式
const _SNIFF_PROG = {
  queued:     { ic: "○", cls: "wait" },
  fetching:   { ic: "◌", cls: "run" },
  failed:     { ic: "✕", cls: "fail" },
  empty:      { ic: "⚠", cls: "warn" },
  first:      { ic: "◍", cls: "info" },
  unchanged:  { ic: "=", cls: "dim" },
  nodiff:     { ic: "=", cls: "dim" },
  extracting: { ic: "◌", cls: "run" },
  found:      { ic: "★", cls: "hit" },
  nonew:      { ic: "–", cls: "dim" },
};

function renderSniffProgress(status) {
  const panel = document.getElementById("sniffProgress");
  if (!panel) return;
  const prog = status.progress || [];
  const stageEl = document.getElementById("sniffProgStage");
  const cntEl = document.getElementById("sniffProgCount");
  if (stageEl) stageEl.textContent = status.stage || "正在嗅探…";
  const done = prog.filter((p) => !["queued", "fetching", "extracting"].includes(p.status)).length;
  if (cntEl) cntEl.textContent = prog.length ? done + "/" + prog.length : "";
  const list = document.getElementById("sniffProgList");
  if (list) {
    list.innerHTML = prog.map((p) => {
      const m = _SNIFF_PROG[p.status] || { ic: "·", cls: "dim" };
      return (
        '<div class="sniff-prog-row ' + m.cls + '">' +
          '<span class="sniff-prog-ic">' + m.ic + "</span>" +
          '<span class="sniff-prog-name">' + escapeHtml(p.title || p.host || "") + "</span>" +
          '<span class="sniff-prog-detail">' + escapeHtml(p.detail || "") + "</span>" +
        "</div>"
      );
    }).join("");
  }
}

async function loadSniffFeed() {
  try {
    const r = await fetch(BACKEND + "/sniff/feed");
    const d = await r.json();
    renderSniffFeed(d.feed || []);
    const stt = d.status || {};
    const panel = document.getElementById("sniffProgress");
    if (stt.running) {
      if (panel) panel.hidden = false;
      renderSniffProgress(stt);
      if (!_sniffTimer) startSniffPolling();
    } else {
      if (_sniffTimer) { clearInterval(_sniffTimer); _sniffTimer = null; }
      if ((stt.progress || []).length) {
        // 跑完了：把最终状态再渲一次，几秒后收起，并刷新源统计
        renderSniffProgress(stt);
        loadSniffSources();
        setTimeout(() => { if (panel) panel.hidden = true; }, 8000);
      } else if (panel) {
        panel.hidden = true;
      }
    }
  } catch (e) { /* 忽略一次失败 */ }
}

let _sniffFeedCache = [];
let _sniffFilter = "all";

function updateSniffStats() {
  const box = document.getElementById("sniffStats");
  if (!box) return;
  const n = _sniffFeedCache.length;
  const cntEl = document.getElementById("sniffSrcCount");
  const srcN = cntEl ? (cntEl.textContent || "·") : "·";
  const last = n ? (_sniffFeedCache[0].ts || "") : "";
  box.innerHTML =
    '<div class="sniff-stat"><span class="sniff-stat-num">' + srcN + '</span><span class="sniff-stat-label">个源</span></div>' +
    '<div class="sniff-stat"><span class="sniff-stat-num">' + n + '</span><span class="sniff-stat-label">条动向</span></div>' +
    (last ? '<div class="sniff-stat"><span class="sniff-stat-num sniff-stat-time">' + escapeHtml(last) + '</span><span class="sniff-stat-label">最近一条</span></div>' : "");
}

function renderSniffFeed(feed) {
  _sniffFeedCache = feed || [];
  updateSniffStats();
  renderSniffCatTiles(_sniffCategories);
  paintSniffFeed();
}

function paintSniffFeed() {
  const box = document.getElementById("sniffFeed");
  if (!box) return;
  const feed = _sniffFeedCache.filter((it) =>
    (_sniffFilter === "all" || it.kind === _sniffFilter) &&
    (_sniffCat === "all" || (it.category || "AI动态") === _sniffCat));

  if (!_sniffFeedCache.length) {
    box.innerHTML =
      '<div class="sniff-empty-rich">' +
        '<div class="sniff-empty-icon">📡</div>' +
        '<div class="sniff-empty-title">还没有动向</div>' +
        '<div class="sniff-empty-desc">点右上角「快速嗅探」扫一遍。<b>第一次只记录快照</b>，从第二次起才会报新内容。</div>' +
        '<div class="sniff-legend">' +
          '<div class="sniff-legend-item"><span class="sniff-legend-ic">🆕</span><div><b>发布</b><span>新模型、新版本上线</span></div></div>' +
          '<div class="sniff-legend-item"><span class="sniff-legend-ic">🧩</span><div><b>功能</b><span>新能力、新特性</span></div></div>' +
          '<div class="sniff-legend-item"><span class="sniff-legend-ic">💡</span><div><b>概念</b><span>新术语、新玩法</span></div></div>' +
        "</div>" +
      "</div>";
    return;
  }
  if (!feed.length) {
    const kindName = _sniffFilter === "all" ? "" : "「" + _sniffFilter + "」";
    const catName = _sniffCat === "all" ? "" : "「" + _sniffCat + "」";
    const cond = [catName, kindName].filter(Boolean).join("·");
    box.innerHTML = '<div class="sniff-empty">当前筛选' + (cond ? "（" + cond + "）" : "") +
      '下没有动向，但一共有 <b>' + _sniffFeedCache.length + '</b> 条。' +
      '<br>点上面的<b>「全部」</b>（类别和类型各一个）看全部内容。</div>';
    return;
  }
  const kindIcon = { "发布": "🆕", "功能": "🧩", "概念": "💡" };
  const impCls = { "高": "high", "中": "mid", "低": "low" };
  box.innerHTML = feed.map((it) => {
    let host = "";
    try { host = new URL(it.link).hostname.replace(/^www\./, ""); } catch (e) { host = ""; }
    return (
      '<div class="sniff-item">' +
        '<div class="sniff-item-kind k-' + (impCls[it.importance] || "mid") + '">' + (kindIcon[it.kind] || "•") + "</div>" +
        '<div class="sniff-item-body">' +
          '<div class="sniff-item-title">' + escapeHtml(it.title || "") + "</div>" +
          (it.summary ? '<div class="sniff-item-summary">' + escapeHtml(it.summary) + "</div>" : "") +
          '<div class="sniff-item-foot">' +
            '<span class="sniff-item-tag">' + escapeHtml(it.kind || "") + "</span>" +
            (it.importance ? '<span class="sniff-item-imp ' + (impCls[it.importance] || "mid") + '">' + escapeHtml(it.importance) + "度</span>" : "") +
            '<span class="sniff-item-src">' + escapeHtml(it.source_title || host) + "</span>" +
            '<span class="sniff-item-ts">' + escapeHtml(it.ts || "") + "</span>" +
            (it.link ? '<a class="sniff-item-link" href="' + escapeHtml(it.link) + '" target="_blank">查看原文 →</a>' : "") +
          "</div>" +
        "</div>" +
      "</div>"
    );
  }).join("");
}

// 分类筛选
document.getElementById("sniffFilters")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".sniff-chip");
  if (!btn) return;
  document.querySelectorAll("#sniffFilters .sniff-chip").forEach((c) => c.classList.remove("active"));
  btn.classList.add("active");
  _sniffFilter = btn.dataset.k;
  paintSniffFeed();
});

// ============================================================
// 设置页 · 分页签 + 代理设置
// ============================================================
document.getElementById("settingsTabs")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".settings-tab-btn");
  if (!btn) return;
  const tab = btn.dataset.tab;
  document.querySelectorAll("#settingsTabs .settings-tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
  document.querySelectorAll("#view-settings .settings-tab").forEach((p) => p.classList.toggle("active", p.id === tab));
  // 打开「配置」tab 时，加载配置类编辑器（情报关键词/竞品/提醒/推送/代理）
  if (tab === "tab-config" && typeof loadConfigTabs === "function") loadConfigTabs();
});

async function loadProxySetting() {
  try {
    const r = await fetch(BACKEND + "/memory?name=proxy.md");
    const d = await r.json();
    const m = (d.content || "").match(/^\s*proxy:\s*(.*)$/im);
    const el = document.getElementById("proxyInput");
    if (el) el.value = m ? m[1].trim() : "";
  } catch (e) { /* 忽略 */ }
}

async function _saveProxy() {
  const val = document.getElementById("proxyInput").value.trim();
  let txt = "";
  try { const r = await fetch(BACKEND + "/memory?name=proxy.md"); txt = (await r.json()).content || ""; } catch (e) {}
  if (/^\s*proxy:/im.test(txt)) {
    txt = txt.replace(/^\s*proxy:.*$/im, "proxy: " + val);
  } else {
    if (!txt) txt = "# 联网与代理\n> 软件访问境外网站用的代理，填科学上网工具的本地端口。不用就留空。\n";
    if (!txt.endsWith("\n")) txt += "\n";
    txt += "proxy: " + val + "\n";
  }
  await fetch(BACKEND + "/memory", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "proxy.md", content: txt }),
  });
}

document.getElementById("proxySaveBtn")?.addEventListener("click", async () => {
  await _saveProxy();
  const h = document.getElementById("proxyHint");
  if (h) { h.textContent = "✓ 已保存"; setTimeout(() => { if (h) h.textContent = ""; }, 2500); }
});

document.getElementById("proxyTestBtn")?.addEventListener("click", async () => {
  const h = document.getElementById("proxyHint");
  await _saveProxy();
  if (h) h.textContent = "正在测试（用代理打开 huggingface.co）…";
  try {
    const r = await fetch(BACKEND + "/proxy/test", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const d = await r.json();
    if (h) h.textContent = d.message || (d.ok ? "代理可用" : "测试失败");
  } catch (e) { if (h) h.textContent = "测试出错：" + e.message; }
});

// ============================================================
// 嗅探 · 生成中文简报（把已嗅到的动向汇编成可读报告）
// ============================================================
function buildSniffBriefMarkdown() {
  const items = _sniffFeedCache || [];
  const d = new Date();
  const p2 = (n) => String(n).padStart(2, "0");
  const stamp = d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate()) +
                " " + p2(d.getHours()) + ":" + p2(d.getMinutes());
  if (!items.length) return "# 📡 AI 嗅探简报\n\n暂时还没有新动向。先点「快速嗅探」扫一遍，第二次起就会有内容。";
  const icon = { "发布": "🆕", "功能": "🧩", "概念": "💡" };
  const groups = []; const idx = {};
  items.forEach((it) => {
    const c = it.category || "AI动态";
    if (!(c in idx)) { idx[c] = groups.length; groups.push({ c, list: [] }); }
    groups[idx[c]].list.push(it);
  });
  let md = "# 📡 AI 嗅探简报\n\n> " + stamp + " 生成 · 共 " + items.length + " 条新动向\n";
  groups.forEach((g) => {
    md += "\n## 📁 " + g.c + "（" + g.list.length + " 条）\n\n";
    g.list.forEach((it) => {
      md += "**" + (icon[it.kind] || "•") + " " + (it.kind || "") + " · " +
            (it.importance || "") + "度 · " + (it.title || "") + "**\n\n";
      if (it.summary) md += it.summary + "\n\n";
      const src = it.source_title || "";
      md += (it.link ? "[查看原文](" + it.link + ")" : "") +
            (src ? " · 来自 " + src : "") + (it.ts ? " · " + it.ts : "") + "\n\n";
    });
  });
  return md.trim();
}

let _sniffBriefRaw = "";
// 「生成简报」：和「生成情报简报」完全一致的工作模式——
// 开一个命名会话、显示实时进度，让网页模型 AI 一个个站点去搜+读+总结（每段自带来源链接），
// 全部生成完后软件拼成报告显示出来。
document.getElementById("sniffBriefBtn")?.addEventListener("click", () => runSniffReport());

async function runSniffReport() {
  goToNamedConvo("📡 嗅探简报");
  const btn = document.getElementById("sniffBriefBtn");
  const old = btn ? btn.textContent : "";
  if (btn) { btn.textContent = "逐站搜集中…"; btn.disabled = true; }
  const chatId = "sniff-" + Date.now();
  const prog = addLiveProgress(chatId);
  const s = settings();
  syncComposerModel(false, "web");          // 默认用网页模型，同步聊天框 + 右上角
  try {
    const resp = await fetch(BACKEND + "/sniff/report", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        use_local: false, model: "web",
        fallback_use_local: s.use_local, fallback_model: s.model,
        chat_id: chatId }),
    });
    const data = await resp.json();
    prog.done();
    if (data && data.used_model) syncComposerModel(!!data.used_use_local, data.used_model);
    addBubble("assistant", data.brief || "（没有内容）");
    saveCurrentConversation();
  } catch (e) {
    prog.done();
    addSystemNote("嗅探简报出错：" + e.message);
  } finally {
    if (btn) { btn.textContent = old || "📄 深度嗅探"; btn.disabled = false; }
  }
}
document.getElementById("sniffBriefClose")?.addEventListener("click", () => {
  const m = document.getElementById("sniffBriefMask"); if (m) m.hidden = true;
});
document.getElementById("sniffBriefMask")?.addEventListener("click", (e) => {
  if (e.target.id === "sniffBriefMask") e.target.hidden = true;
});
document.getElementById("sniffBriefCopy")?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(_sniffBriefRaw);
    const b = document.getElementById("sniffBriefCopy"); const o = b.textContent;
    b.textContent = "✓ 已复制"; setTimeout(() => { b.textContent = o; }, 1500);
  } catch (e) { alert("复制失败，可手动选中复制。"); }
});

// ════════════════════════════════════════════════════════════════════
// 🦊 桌宠设置面板（主窗里）：开关 + 选形象。改完即时同步到桌宠窗口。
// 通过 window.crayfish.petApplyConfig（preload 暴露）跟主进程通信。
// ════════════════════════════════════════════════════════════════════
async function loadPetSettings() {
  const grid = document.getElementById("petSkinGrid");
  const toggle = document.getElementById("petEnabled");
  if (!grid || !window.PetCharacters) return;

  // 读当前配置（开关 + 选了哪只）
  let cfg = { enabled: true, character: "fox" };
  try {
    if (window.crayfish && window.crayfish.petGetConfig) {
      cfg = (await window.crayfish.petGetConfig()) || cfg;
    }
  } catch (e) {}

  if (toggle) {
    toggle.checked = !!cfg.enabled;
    toggle.onchange = async () => {
      try { await window.crayfish.petApplyConfig({ enabled: toggle.checked }); } catch (e) {}
    };
  }

  // 渲染形象卡片（用角色库里的 SVG 预览）
  const list = window.PetCharacters.listCharacters();
  grid.innerHTML = list.map((c) => {
    const active = (c.id === cfg.character);
    return '' +
      '<div class="pet-skin-chip" data-id="' + c.id + '" style="' +
        'width:104px;border:2px solid ' + (active ? c.accent : 'transparent') + ';' +
        'border-radius:14px;padding:12px 8px;cursor:pointer;text-align:center;' +
        'background:rgba(127,127,127,.06);transition:all .15s;">' +
        '<div class="psc-prev" style="width:64px;height:64px;margin:0 auto 6px;"></div>' +
        '<div style="font-size:13px;font-weight:600;">' + c.emoji + ' ' + c.name + '</div>' +
        (active ? '<div style="font-size:11px;color:' + c.accent + ';margin-top:2px;">当前</div>'
                : '<div style="font-size:11px;color:transparent;margin-top:2px;">·</div>') +
      '</div>';
  }).join("");

  // 给每张卡片画上静态预览 + 绑定点击切换
  grid.querySelectorAll(".pet-skin-chip").forEach((chip) => {
    const id = chip.dataset.id;
    const prev = chip.querySelector(".psc-prev");
    try {
      const ch = window.PetCharacters.getCharacter(id);
      prev.innerHTML = ch.svg({ pose: "idle", facing: 1, frame: 8, blink: false });
    } catch (e) {}
    chip.addEventListener("click", async () => {
      try { await window.crayfish.petApplyConfig({ character: id, enabled: true }); } catch (e) {}
      if (toggle) toggle.checked = true;
      loadPetSettings();  // 重渲染高亮
    });
  });
}

// 桌宠窗口改了形象 → 主进程回调这里，让设置面板高亮跟着变
window.onPetConfigChanged = function (cfg) {
  try {
    const v = document.getElementById("view-pet");
    if (v && v.classList.contains("active")) loadPetSettings();
  } catch (e) {}
};

// ════════════════════════════════════════════════════════════════════
// 🌌 知识云图 → 回到那段对话
// 点云图里的一颗星，把那段存档的消息灌回一个会话，切到对话视图继续聊。
// ════════════════════════════════════════════════════════════════════
window.openConversationFromGraph = function (data) {
  if (!data || !Array.isArray(data.messages)) return;
  try {
    // 新开一个会话承载这段历史（不覆盖当前正在聊的）
    var id = "kg" + Date.now();
    var disp = [];
    var html = "";
    conversations.unshift({
      id: id,
      title: data.title || "历史对话",
      userRenamed: true,            // 用存档标题，别被自动改名覆盖
      messages: data.messages.slice(),
      display: disp,
      _fromArchive: data.id || "",
    });
    activeConvoId = id;
    messages = data.messages.slice();
    sessionAllowedTools = new Set();
    // 渲染这段历史到聊天区
    messagesEl.innerHTML = "";
    data.messages.forEach(function (m) {
      if (!m || !m.content) return;
      if (typeof addBubble === "function") {
        addBubble(m.role === "user" ? "user" : "assistant", m.content);
      } else {
        var div = document.createElement("div");
        div.className = "msg " + (m.role === "user" ? "user" : "assistant");
        div.textContent = m.content;
        messagesEl.appendChild(div);
      }
    });
    // 存一份展示快照，切走再回来还在
    var c = conversations.find(function (x) { return x.id === id; });
    if (c) c.displayHtml = messagesEl.innerHTML;
    renderConvoList();
    document.querySelector('.nav-item[data-view="chat"]').click();
    try { messagesEl.scrollTop = messagesEl.scrollHeight; } catch (e) {}
  } catch (e) {
    console.error("回到对话失败", e);
  }
};

// ════════════════════════════════════════════════════════════════════
// 让「聊过的」都进知识云图：把会话静默落盘到后端存档。
// 在 saveCurrentConversation 之后调用（包一层），失败不打扰用户。
// ════════════════════════════════════════════════════════════════════
window.persistSessionToArchive = function (c) {
  try {
    if (!c || !Array.isArray(c.messages)) return;
    // 至少有一来一回才值得存（避免一堆空白会话刷屏）
    var hasU = c.messages.some(function (m) { return m.role === "user" && (m.content || "").trim(); });
    var hasA = c.messages.some(function (m) { return m.role === "assistant" && (m.content || "").trim(); });
    if (!hasU || !hasA) return;
    // 固定任务会话（心跳/简报等）不进云图，避免噪音
    if (c.fixedTitle) return;
    fetch(BACKEND + "/conversations/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: c.id,
        title: c.title || "",
        messages: c.messages.map(function (m) { return { role: m.role, content: m.content }; }),
        starred: !!c.starred,
      }),
    }).catch(function () {});
  } catch (e) {}
};

// 🌌 知识云图 → 打开视频笔记：切到「视频」板块并展开这条笔记
window.openVideoNoteFromGraph = function (name, title) {
  try { document.querySelector('.nav-item[data-view="video"]').click(); } catch (e) {}
  if (typeof openVideoNote === "function" && name) {
    // 切视图后稍等一拍再打开，确保视频页已渲染
    setTimeout(function () { try { openVideoNote(name); } catch (e) {} }, 120);
  }
};


// ════════════════════ v55：终端抽屉（后台日志嵌进软件） ════════════════════
// 启动时的黑窗口里打印的每一行，后端都会存一份；这里从 /logs 读出来显示，不用再盯着黑窗口。
let _termView = null;

function termDrawerPlace() {
  const d = document.getElementById("termDrawer");
  const main = document.querySelector(".main");
  if (!d || d.hidden || !main) return;
  const r = main.getBoundingClientRect();
  d.style.left = r.left + "px";
  d.style.width = r.width + "px";
}

function termDrawerSetOpen(open) {
  const d = document.getElementById("termDrawer");
  const main = document.querySelector(".main");
  if (!d || !main) return;
  d.hidden = !open;
  main.classList.toggle("term-open", !!open);
  document.getElementById("termToggleBtn")?.classList.toggle("active", !!open);
  if (open) {
    if (!_termView && window.CxLogView) {
      _termView = CxLogView.mount(document.getElementById("termDrawerBody"), { backend: () => BACKEND });
    }
    if (_termView) _termView.start();
    termDrawerPlace();
  } else if (_termView) {
    _termView.stop();
  }
  try { localStorage.setItem("cxTermOpen", open ? "1" : "0"); } catch (_) {}
}

function termDrawerMsg(text) {
  const m = document.getElementById("termDrawerMsg");
  if (!m) return;
  m.textContent = text || "";
  clearTimeout(termDrawerMsg._t);
  if (text) termDrawerMsg._t = setTimeout(() => { m.textContent = ""; }, 5000);
}

function termConsoleBtnLabel(hidden) {
  const b = document.getElementById("termConsoleBtn");
  if (b) b.textContent = hidden === false ? "隐藏原来的黑窗口" : "显示原来的黑窗口";
}

async function consoleWindow(action) {
  try {
    const d = await (await fetch(BACKEND + "/console", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }) })).json();
    return d;
  } catch (e) {
    return { ok: false, message: "出错：" + e.message };
  }
}

// 「显示终端」：单独开一个终端窗口；老版本主进程没有这个功能时，退回到软件里的终端抽屉
async function openTerminalWindow() {
  try {
    if (window.crayfish && window.crayfish.openTerminalWindow) {
      await window.crayfish.openTerminalWindow();
      return;
    }
  } catch (e) {}
  termDrawerSetOpen(true);
}

(function initTermDrawer() {
  const d = document.getElementById("termDrawer");
  if (!d) return;
  // 高度：上次拖到多高就是多高
  let h = 0;
  try { h = parseInt(localStorage.getItem("cxTermH") || "0", 10) || 0; } catch (_) {}
  if (h) document.documentElement.style.setProperty("--term-h", h + "px");

  document.getElementById("termToggleBtn")?.addEventListener("click", () => termDrawerSetOpen(d.hidden));
  document.getElementById("termCloseBtn")?.addEventListener("click", () => termDrawerSetOpen(false));
  document.getElementById("termPopBtn")?.addEventListener("click", () => openTerminalWindow());
  document.getElementById("termConsoleBtn")?.addEventListener("click", async () => {
    const r = await consoleWindow("toggle");
    termDrawerMsg(r.message || (r.ok ? "好了" : "没做到"));
    termConsoleBtnLabel(r && r.hidden);
  });

  // 拖动顶边调整高度
  const handle = document.getElementById("termDrawerResize");
  handle?.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const move = (ev) => {
      const nh = Math.max(120, Math.min(window.innerHeight - 160, window.innerHeight - ev.clientY));
      document.documentElement.style.setProperty("--term-h", nh + "px");
      try { localStorage.setItem("cxTermH", String(Math.round(nh))); } catch (_) {}
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.body.classList.remove("term-resizing");
    };
    document.body.classList.add("term-resizing");
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });

  const main = document.querySelector(".main");
  if (main && window.ResizeObserver) new ResizeObserver(() => termDrawerPlace()).observe(main);
  window.addEventListener("resize", termDrawerPlace);

  // 设置页：启动后自动最小化黑窗口
  const cb = document.getElementById("autoMinConsole");
  if (cb) {
    try { cb.checked = localStorage.getItem("cxAutoMinConsole") !== "0"; } catch (_) {}
    cb.addEventListener("change", () => {
      try { localStorage.setItem("cxAutoMinConsole", cb.checked ? "1" : "0"); } catch (_) {}
    });
  }
})();

// 后端第一次连上之后：按设置把启动时的黑窗口最小化；上次开着终端抽屉就接着开
function termAfterBackendReady() {
  let autoMin = true;
  try { autoMin = localStorage.getItem("cxAutoMinConsole") !== "0"; } catch (_) {}
  if (autoMin) consoleWindow("hide").then((r) => termConsoleBtnLabel(r && r.ok ? r.hidden : true));
  let wasOpen = false;
  try { wasOpen = localStorage.getItem("cxTermOpen") === "1"; } catch (_) {}
  if (wasOpen) termDrawerSetOpen(true);
}

// ════════════════════ v55：批量分析 ·「AI 实时画面」 ════════════════════
// v64：不再单独折叠——点开「批量 AI 分析」这一组就直接看得到（以前还得再点一下「AI 实时画面」）。
// 展开后能看到：正在分析哪一篇、AI 池浏览器的实时截图、AI 正在写的回复、每一步做了什么；
// 不用再去看浏览器和黑窗口。「显示浏览器」「显示终端」可以把它们单独调出来。
let _vnLiveTimer = null;
let _vnLiveShotTs = 0;
let _vnLiveTab = "reply";

function vnLiveIsOpen() {
  return true;          // v64：实时画面跟着「批量 AI 分析」这一组一起开 / 关，自己不再折叠
}

function vnBuildLive() {
  const box = document.createElement("div");
  box.className = "vn-live"; box.id = "vnLive"; box.hidden = true;
  box.innerHTML =
    '<div class="vn-live-head" id="vnLiveHead">' +
      '<span class="vn-live-title">AI 实时画面</span>' +
      '<span class="vn-live-sum" id="vnLiveSum"></span>' +
    "</div>" +
    '<div class="vn-live-body" id="vnLiveBody">' +
      '<div class="vn-live-article" id="vnLiveArticle"></div>' +
      '<div class="vn-live-stage" id="vnLiveStage"></div>' +
      '<div class="vn-live-grid">' +
        '<div class="vn-live-shotbox">' +
          '<img id="vnLiveShot" alt="" hidden />' +
          '<div class="vn-live-shotnote" id="vnLiveShotNote">等待画面…</div>' +
        "</div>" +
        '<div class="vn-live-side">' +
          '<div class="vn-live-tabs">' +
            '<button class="vn-live-tab" data-tab="reply">AI 回复（实时）</button>' +
            '<button class="vn-live-tab" data-tab="steps">步骤记录</button>' +
          "</div>" +
          '<pre class="vn-live-reply" id="vnLiveReply"></pre>' +
          '<div class="vn-live-steps" id="vnLiveSteps" hidden></div>' +
        "</div>" +
      "</div>" +
      '<div class="vn-live-actions">' +
        '<button class="vn-batch-stop" id="vnLiveBrowserBtn" title="把 AI 池浏览器调到屏幕上 / 挪回屏幕外（挪走后照常工作）">显示浏览器</button>' +
        '<button class="vn-batch-stop" id="vnLiveTermBtn" title="在单独的窗口里看终端（后台日志）">显示终端</button>' +
        '<span class="vn-live-msg" id="vnLiveMsg"></span>' +
      "</div>" +
    "</div>";

  const setTab = (t) => {
    _vnLiveTab = t;
    box.querySelectorAll(".vn-live-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
    box.querySelector("#vnLiveReply").hidden = t !== "reply";
    box.querySelector("#vnLiveSteps").hidden = t !== "steps";
  };
  box.querySelectorAll(".vn-live-tab").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
  setTab(_vnLiveTab);

  box.querySelector("#vnLiveBrowserBtn").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const action = btn.dataset.visible === "1" ? "hide" : "show";
    btn.disabled = true;
    try {
      const d = await (await fetch(BACKEND + "/web_model/window", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }) })).json();
      vnLiveMsg(d.message || (d.ok ? "好了" : "没做到"));
    } catch (err) {
      vnLiveMsg("出错：" + err.message);
    }
    btn.disabled = false;
    setTimeout(vnLivePoll, 300);
  });
  box.querySelector("#vnLiveTermBtn").addEventListener("click", () => openTerminalWindow());
  return box;
}

function vnLiveMsg(text) {
  const m = document.getElementById("vnLiveMsg");
  if (!m) return;
  m.textContent = text || "";
  clearTimeout(vnLiveMsg._t);
  if (text) vnLiveMsg._t = setTimeout(() => { m.textContent = ""; }, 6000);
}

function vnLiveZoom(src) {
  const ov = document.createElement("div");
  ov.className = "vn-live-zoom";
  ov.title = "点击任意处关闭";
  const img = document.createElement("img");
  img.src = src;
  ov.appendChild(img);
  ov.addEventListener("click", () => ov.remove());
  document.body.appendChild(ov);
}

function _vnFmtDur(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const m = Math.floor(sec / 60), s = sec % 60;
  return m ? m + " 分 " + s + " 秒" : s + " 秒";
}

function _vnClock(t) {
  const d = new Date(t * 1000);
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0") + ":" +
    String(d.getSeconds()).padStart(2, "0");
}

async function vnLivePoll() {
  clearTimeout(_vnLiveTimer);
  const box = document.getElementById("vnLive");
  if (!box) { _vnLiveTimer = null; return; }          // 列表重画时会重新启动
  const viewOn = document.getElementById("view-video")?.classList.contains("active") && !document.hidden;
  if (!viewOn) { _vnLiveTimer = setTimeout(vnLivePoll, 3000); return; }
  const open = vnLiveIsOpen() && document.getElementById("view-video")?.dataset.mode === "process";   // v120：在加工页才截图
  let d = null;
  try {
    d = await (await fetch(BACKEND + "/ai_live?watch=" + (open ? "1" : "0"), { cache: "no-store" })).json();
  } catch (e) {
    _vnLiveTimer = setTimeout(vnLivePoll, 4000);
    return;
  }
  if (document.getElementById("vnLive") !== box) return;   // 期间列表重画了，新的那个会自己轮询
  const b = d.batch || {}, p = d.pool || {};
  const single = !b.running && !!_noteAnRunning;   // v120：单条 AI 分析也显示实时画面
  if (!b.running && !single) {
    box.hidden = true;
    _vnLiveTimer = setTimeout(vnLivePoll, 4000);
    return;
  }
  box.hidden = false;
  const name = ((b.running ? b.current : _noteAnRunning) || "").replace(/\.md$/, "");
  const title = b.running ? (b.title || name) : viNoteTitle(_noteAnRunning);
  const idx = Math.min(b.total || 0, (b.done || 0) + 1);
  const sum = box.querySelector("#vnLiveSum");
  if (single) {
    sum.textContent = "· 单条分析：" + title;
  } else if (b.waiting) {
    sum.textContent = "· 暂停中，到时间会自动接着跑";
  } else if (title) {
    sum.textContent = "· 第 " + idx + " / " + b.total + " 篇：" + title;
  } else {
    sum.textContent = "";
  }
  sum.title = title;

  if (open) {
    // 正在分析哪一篇
    const art = box.querySelector("#vnLiveArticle");
    art.innerHTML = "";
    if (title && !b.waiting) {
      const t = document.createElement("a");
      t.className = "vn-live-art-title"; t.textContent = "《" + title + "》"; t.href = "#";
      t.title = "打开这篇笔记";
      t.addEventListener("click", (e) => { e.preventDefault(); const nm = b.running ? b.current : _noteAnRunning; if (nm) openVideoNote(nm); });
      const meta = document.createElement("span");
      meta.className = "vn-live-art-meta";
      meta.textContent = single ? "单条分析" : "第 " + idx + " / " + b.total + " 篇" + (b.author ? " · 作者：" + b.author : "") +
        (b.note_started ? " · 这篇已用时 " + _vnFmtDur(d.now - b.note_started) : "") +
        (b.round > 1 ? " · 第 " + b.round + " 遍（补之前没成功的）" : "");
      art.appendChild(t); art.appendChild(meta);
    } else if (b.waiting) {
      art.textContent = "⏸ " + b.waiting;
    }
    // 现在在干什么
    const stage = box.querySelector("#vnLiveStage");
    const parts = [];
    if (b.stage) parts.push(b.stage);
    if (p.stage && (!b.stage || b.stage.indexOf(p.stage) < 0)) {
      parts.push("AI 池：" + p.stage + (p.busy ? "" : "（空闲）"));
    }
    stage.textContent = parts.join(" · ");

    // 实时截图
    const img = box.querySelector("#vnLiveShot");
    const note = box.querySelector("#vnLiveShotNote");
    if (p.has_shot && p.shot_ts && p.shot_ts !== _vnLiveShotTs) {
      _vnLiveShotTs = p.shot_ts;
      img.src = BACKEND + "/ai_live_shot?t=" + encodeURIComponent(p.shot_ts);
      img.hidden = false;
    } else if (p.has_shot && img.hidden && p.shot_ts) {
      img.src = BACKEND + "/ai_live_shot?t=" + encodeURIComponent(p.shot_ts);
      img.hidden = false;
    }
    if (!p.hasBrowser) {
      note.textContent = p.headless ? "AI 池是后台模式（不显示浏览器），这里只有文字进度"
        : "AI 池浏览器还没打开（换卡 / 启动中）";
    } else if (p.shot_err) {
      note.textContent = "截图暂时失败，文字进度照常更新";
    } else if (p.shot_ts) {
      const ago = Math.max(0, Math.round(d.now - p.shot_ts));
      note.textContent = ago <= 3 ? "实时画面" : "画面更新于 " + ago + " 秒前";
    } else {
      note.textContent = "等待画面…";
    }

    // AI 正在写的回复
    const rep = box.querySelector("#vnLiveReply");
    const nearBottom = rep.scrollHeight - rep.scrollTop - rep.clientHeight < 40;
    let txt = p.reply_tail || "";
    if (p.reply_len > txt.length) txt = "…（前面还有 " + (p.reply_len - txt.length) + " 字）\n" + txt;
    if (!txt) txt = p.busy ? "AI 还没开始写回复（可能在换卡、选模型、思考中…）" : "（暂无回复内容）";
    if (rep.textContent !== txt) {
      rep.textContent = txt;
      if (nearBottom) rep.scrollTop = rep.scrollHeight;
    }
    // 步骤记录
    const steps = box.querySelector("#vnLiveSteps");
    const rows = (p.log || []).slice(-25);
    const html = rows.map((r) => '<div class="vn-live-step"><span class="vn-live-step-t">' + _vnClock(r[0]) +
      "</span>" + escapeHtml(r[1]) + "</div>").join("");
    if (steps.innerHTML !== html) {
      steps.innerHTML = html;
      steps.scrollTop = steps.scrollHeight;
    }
    // 显示 / 隐藏浏览器按钮
    const bb = box.querySelector("#vnLiveBrowserBtn");
    const vis = p.visible === true || (p.visible == null && p.hidden_pref === false);
    bb.dataset.visible = vis ? "1" : "0";
    bb.textContent = vis ? "隐藏浏览器" : "显示浏览器";
    bb.disabled = !!p.headless;
  }
  _vnLiveTimer = setTimeout(vnLivePoll, open ? 1500 : 4000);
}


// ════════════════════ v56：视频笔记 · 置顶的「最新提取」 ════════════════════
// 按提取时间筛：最近一天 / 七天 / 1 个月 / 3 个月 / 半年 / 一年；新的在前，每页 50 条。
const VN_RECENT_RANGES = [
  ["1d", "最近一天", 1], ["7d", "最近七天", 7], ["30d", "1 个月", 30],
  ["90d", "3 个月", 90], ["180d", "半年", 182], ["365d", "一年", 365],
];
const VN_RECENT_PAGE_SIZE = 50;
let _vnRecentPage = 1;

function vnRecentPrefs() {
  const def = { open: true, range: "7d" };
  try { return Object.assign(def, JSON.parse(localStorage.getItem("vnRecent") || "{}")); } catch (_) { return def; }
}
function vnRecentSave(p) { try { localStorage.setItem("vnRecent", JSON.stringify(p)); } catch (_) {} }

// 提取时间（毫秒）：后端给的 ts，没有就从文件名开头的 20260708-095408 解析
function vnNoteTime(n) {
  if (n && n.ts) return n.ts * 1000;
  const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec((n && n.name) || "");
  return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]).getTime() : 0;
}

function vnFmtWhen(ms) {
  const d = new Date(ms), now = new Date();
  const p2 = (x) => String(x).padStart(2, "0");
  const hm = p2(d.getHours()) + ":" + p2(d.getMinutes());
  const day0 = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (ms >= day0) return "今天 " + hm;
  if (ms >= day0 - 86400000) return "昨天 " + hm;
  if (d.getFullYear() === now.getFullYear()) return p2(d.getMonth() + 1) + "-" + p2(d.getDate()) + " " + hm;
  return d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate());
}

function vnRenderRecent(list, notes, folders) {
  const prefs = vnRecentPrefs();
  const now = Date.now();
  const timed = (notes || []).map((n) => [vnNoteTime(n), n]).filter((x) => x[0] > 0)
    .sort((a, b) => b[0] - a[0]);
  const inRange = (days) => timed.filter((x) => now - x[0] <= days * 86400000);

  const wrap = document.createElement("div");
  wrap.className = "vn-recent"; wrap.id = "vnRecent";
  const head = document.createElement("div");
  head.className = "video-note-item vn-group-head vn-recent-head";
  head.title = "按提取时间列出最近的视频笔记（点击展开 / 收起）";
  const caret = document.createElement("span"); caret.className = "vn-caret";
  const nm = document.createElement("span"); nm.className = "vn-name"; nm.textContent = "已提取";
  const pin = document.createElement("span"); pin.className = "vn-recent-pin"; pin.textContent = "置顶";
  const cnt = document.createElement("span"); cnt.className = "vn-count";
  head.appendChild(caret); head.appendChild(nm); head.appendChild(pin); head.appendChild(cnt);

  const box = document.createElement("div"); box.className = "vn-recent-box";
  const chips = document.createElement("div"); chips.className = "vn-recent-ranges";
  const itemsBox = document.createElement("div"); itemsBox.className = "vn-recent-items";
  const pager = document.createElement("div"); pager.className = "vn-recent-pager";
  box.appendChild(chips); box.appendChild(itemsBox); box.appendChild(pager);

  VN_RECENT_RANGES.forEach(([key, label, days]) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "vn-recent-chip"; b.dataset.key = key;
    b.innerHTML = escapeHtml(label) + "<b>" + inRange(days).length + "</b>";
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      prefs.range = key; _vnRecentPage = 1; vnRecentSave(prefs); draw();
    });
    chips.appendChild(b);
  });

  function pagerBtn(text, page, disabled) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = text; b.disabled = disabled;
    b.addEventListener("click", () => {
      _vnRecentPage = page; draw();
      head.scrollIntoView({ block: "start", behavior: "smooth" });
    });
    return b;
  }

  function draw() {
    const r = VN_RECENT_RANGES.find((x) => x[0] === prefs.range) || VN_RECENT_RANGES[1];
    const sel = inRange(r[2]);
    cnt.textContent = "（" + r[1] + " " + sel.length + " 条）";
    chips.querySelectorAll(".vn-recent-chip").forEach((b) => b.classList.toggle("active", b.dataset.key === r[0]));
    const pages = Math.max(1, Math.ceil(sel.length / VN_RECENT_PAGE_SIZE));
    if (_vnRecentPage > pages) _vnRecentPage = pages;
    if (_vnRecentPage < 1) _vnRecentPage = 1;
    itemsBox.innerHTML = "";
    if (!sel.length) {
      const em = document.createElement("div");
      em.className = "vn-recent-empty";
      em.textContent = r[1] + "里没有提取过视频，点上面换一个更长的时间看看。";
      itemsBox.appendChild(em);
    }
    const start = (_vnRecentPage - 1) * VN_RECENT_PAGE_SIZE;
    sel.slice(start, start + VN_RECENT_PAGE_SIZE).forEach(([t, n]) => {
      const it = makeVideoNoteItem(n, folders);
      const tm = document.createElement("span");
      tm.className = "vn-recent-time"; tm.textContent = vnFmtWhen(t);
      tm.title = "提取时间：" + new Date(t).toLocaleString();
      it.insertBefore(tm, it.firstChild);
      itemsBox.appendChild(it);
    });
    pager.innerHTML = "";
    pager.hidden = pages <= 1;
    if (pages > 1) {
      const p = _vnRecentPage;
      pager.appendChild(pagerBtn("首页", 1, p === 1));
      pager.appendChild(pagerBtn("上一页", p - 1, p === 1));
      const info = document.createElement("span");
      info.textContent = "第 " + p + " / " + pages + " 页（共 " + sel.length + " 条，每页 " + VN_RECENT_PAGE_SIZE + " 条）";
      pager.appendChild(info);
      pager.appendChild(pagerBtn("下一页", p + 1, p === pages));
      pager.appendChild(pagerBtn("末页", pages, p === pages));
    }
  }

  const applyOpen = (open) => { box.style.display = open ? "" : "none"; caret.textContent = open ? "▾" : "▸"; };
  applyOpen(prefs.open !== false);
  head.addEventListener("click", () => {
    prefs.open = box.style.display === "none";
    applyOpen(prefs.open); vnRecentSave(prefs);
  });
  wrap.appendChild(head); wrap.appendChild(box);
  list.appendChild(wrap);
  draw();
}

// ════════════════════ v56：左侧栏折叠 / 展开 ════════════════════
// 折叠后只留一列图标（鼠标停在图标上会显示名字），再点一次展开。状态会记住。
(function initSidebarCollapse() {
  const btn = document.getElementById("sbCollapseBtn");
  const app = document.querySelector(".app");
  if (!btn || !app) return;
  const apply = (c) => {
    app.classList.toggle("sb-collapsed", !!c);
    btn.title = c ? "展开侧栏" : "折叠侧栏";
    if (c) {
      document.querySelectorAll(".sidebar .nav-item, .sidebar .nav-action, .sidebar .sb-new").forEach((el) => {
        if (el.title) return;
        const sp = el.querySelector("span");
        if (sp && sp.textContent.trim()) el.title = sp.textContent.trim();
      });
    }
    setTimeout(() => {
      try { termDrawerPlace(); } catch (e) {}
      window.dispatchEvent(new Event("resize"));
    }, 220);
  };
  let c = false;
  try { c = localStorage.getItem("cxSidebarCollapsed") === "1"; } catch (_) {}
  apply(c);
  btn.addEventListener("click", () => {
    const nc = !app.classList.contains("sb-collapsed");
    apply(nc);
    try { localStorage.setItem("cxSidebarCollapsed", nc ? "1" : "0"); } catch (_) {}
  });
})();


// ════════════════════ v57 / v58：视频笔记 · 列表 / 图标 两种显示方式 ════════════════════
// 图标视图（v58）：最上面单独一块「最新提取」；下面是博主头像墙（自己建的文件夹是圆角方形，
// 按作者自动分的组是圆形），可以按 最近提取 / 近期新增 / 笔记最多 / 新加入 / 名称 排序。
// 给头像绑定博主主页（抖音 / B站 / YouTube…），软件自动取头像、粉丝数、简介。
let _vnIconPath = null;   // null＝最上层；{kind: "folder" | "author", name}
let _vnIconPage = 1;
const VN_ICON_PAGE_SIZE = 50;
let _vnProfiles = {};
const VN_SORTS = [["last", "最近提取"], ["hot", "近期新增"], ["total", "笔记最多"], ["new", "新加入"], ["name", "名称"]];

function vnViewMode() {
  try { return localStorage.getItem("vnViewMode") === "icon" ? "icon" : "list"; } catch (_) { return "list"; }
}

function vnViewToggle() {
  const wrap = document.createElement("span");
  wrap.className = "vn-view-toggle";
  const mk = (mode, label, svg, tip) => {
    const b = document.createElement("button");
    b.type = "button"; b.title = tip;
    b.className = vnViewMode() === mode ? "active" : "";
    b.innerHTML = svg + "<span>" + label + "</span>";
    b.addEventListener("click", () => {
      if (vnViewMode() === mode) return;
      try { localStorage.setItem("vnViewMode", mode); } catch (_) {}
      loadVideoNotes();
    });
    return b;
  };
  wrap.appendChild(mk("list", "列表",
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg>',
    "列表显示：一行一条，能直接移动、改作者、删除"));
  wrap.appendChild(mk("icon", "图标",
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></svg>',
    "图标显示：博主头像墙，点头像进去看"));
  return wrap;
}

async function vnLoadProfiles() {
  try {
    const d = await (await fetch(BACKEND + "/creator_profiles", { cache: "no-store" })).json();
    _vnProfiles = d.profiles || {};
    _vnMerges = d.merges || [];
  } catch (_) { _vnProfiles = {}; }
}

function vnSortKey() {
  try { return localStorage.getItem("vnCreatorSort") || "last"; } catch (_) { return "last"; }
}

function vnHue(str) {
  let h = 0;
  for (const ch of String(str || "")) h = (h * 31 + ch.codePointAt(0)) % 360;
  return h;
}

function vnFmtNum(n) {
  if (n == null || n === "") return "";
  n = Number(n);
  if (n >= 1e8) return (n / 1e8).toFixed(n >= 1e9 ? 0 : 1).replace(/\.0$/, "") + " 亿";
  if (n >= 1e4) return (n / 1e4).toFixed(n >= 1e5 ? 0 : 1).replace(/\.0$/, "") + " 万";
  return String(n);
}

// 头像：绑定过就用博主头像，没有就用名字首字 + 固定配色
function vnAvatarEl(g, size) {
  const p = _vnProfiles[g.key] || {};
  const av = document.createElement("div");
  av.className = "vn-av" + (g.kind === "author" ? " round" : "") + (size === "big" ? " big" : size === "mini" ? " mini" : "");
  if (p.has_avatar) {
    const img = document.createElement("img");
    img.alt = "";
    img.src = BACKEND + "/creator_avatar?key=" + encodeURIComponent(g.key) + "&v=" + (p.v || 0);
    img.onerror = () => { img.remove(); av.appendChild(vnInitials(g)); };
    av.appendChild(img);
  } else {
    av.appendChild(vnInitials(g));
  }
  if (p.platform_label) {
    const tag = document.createElement("span");
    tag.className = "vn-av-plat plat-" + (p.platform || "web");
    tag.textContent = { douyin: "抖", bilibili: "B", youtube: "▶", kuaishou: "快", xiaohongshu: "红", tiktok: "T", x: "X", weibo: "微" }[p.platform] || "🔗";
    tag.title = p.platform_label;
    av.appendChild(tag);
  }
  return av;
}

function vnInitials(g) {
  const sp = document.createElement("span");
  sp.className = "vn-av-txt";
  const h = vnHue(g.name);
  sp.style.background = "hsl(" + h + ", 55%, 86%)";
  sp.style.color = "hsl(" + h + ", 45%, 30%)";
  const nm = (g.name || "?").replace(/^[\s@#]+/, "");
  sp.textContent = g.kind === "folder" && !nm ? "📁" : Array.from(nm)[0].toUpperCase();
  return sp;
}

function vnGroupStats(items) {
  const now = Date.now();
  let last = 0, first = 0, recent = 0;
  items.forEach((n) => {
    const t = vnNoteTime(n);
    if (!t) return;
    if (t > last) last = t;
    if (!first || t < first) first = t;
    if (now - t <= 30 * 86400000) recent++;
  });
  return { total: items.length, last, first, recent };
}

// ════════════════════ v60：一键识别博主主页 ════════════════════
// 头像墙上方一行「一键识别博主主页（N 个还没主页）」。后台一个个找（每个之间歇几秒，防平台限流），
// 找到一个，墙上对应的头像马上换成真头像（原地换，不重画整面墙）；可以随时停止，下次接着找剩下的。
let _vnCpbTimer = null;
let _vnCpbSeen = -1;
let _vnCpbRenamed = -1;     // v63：有博主改了名 → 整面墙按新名字重画

function vnTileAvatar(g) {
  const st = g.stats;
  const av = vnAvatarEl(g);
  const pill = document.createElement("span");
  pill.className = "vn-av-pill"; pill.textContent = st.total;
  av.appendChild(pill);
  if (st.recent) {
    const nw = document.createElement("span");
    nw.className = "vn-av-new"; nw.textContent = "+" + st.recent;
    nw.title = "近30天新增 " + st.recent + " 条";
    av.appendChild(nw);
  }
  return av;
}

function vnAvMarker(key) {
  const p = _vnProfiles[key] || {};
  return [p.v || 0, p.has_avatar ? 1 : 0, p.platform || "", p.url || ""].join("|");
}

function vnRefreshTileAvatars() {
  document.querySelectorAll(".vn-ctile").forEach((t) => {
    const g = t._g;
    if (!g) return;
    const m = vnAvMarker(g.key);
    if (m === t.dataset.avm) return;
    t.dataset.avm = m;
    const old = t.querySelector(".vn-av");
    if (old) old.replaceWith(vnTileAvatar(g));
    t.classList.remove("vn-av-pop"); void t.offsetWidth; t.classList.add("vn-av-pop");
  });
}

// 还没主页的博主（未填作者、已经绑过的、你解除过绑定的都不算）
function vnCpbTodo(groups) {
  const seen = new Set(), out = [];
  (groups || []).forEach((g) => {
    if (g.name === "未填作者" || seen.has(g.key)) return;
    const p = _vnProfiles[g.key] || {};
    if (p.url || p.no_auto || p.auto_skip) return;     // auto_skip：上次一键识别时发现没法自动找
    seen.add(g.key); out.push(g.key);
  });
  return out;
}

function vnCpbBar(groups) {
  const bar = document.createElement("div");
  bar.className = "vn-cpb"; bar.id = "vnCpb";
  bar._groups = groups;
  vnCpbRender(bar, null);
  _vnCpbSeen = -1;
  setTimeout(vnCpbPoll, 30);
  return bar;
}

function vnCpbRender(bar, d) {
  if (!bar) return;
  if (d) bar._last = d;
  const running = !!(d && d.running);
  const mode = running ? "run" : "idle";
  if (bar.dataset.mode !== mode) {
    bar.dataset.mode = mode;
    bar.innerHTML = "";
    if (running) {
      bar.innerHTML = '<span class="vn-cpb-track"><i></i></span><span class="vn-cpb-txt"></span>';
      const stop = document.createElement("button");
      stop.type = "button"; stop.className = "vn-batch-stop vn-cpb-stop"; stop.textContent = "停止";
      stop.title = "找完当前这个就停；下次点「一键识别」会接着找剩下的";
      stop.addEventListener("click", async () => {
        stop.disabled = true; stop.textContent = "停止中…";
        try {
          await fetch(BACKEND + "/creator_profiles_batch", { method: "POST",
            headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stop: true }) });
        } catch (_) {}
      });
      bar.appendChild(stop);
      const note = document.createElement("div"); note.className = "vn-cpb-note"; note.hidden = true;
      bar.appendChild(note);
    } else {
      const btn = document.createElement("button");
      btn.type = "button"; btn.className = "vn-cpb-btn";
      btn.title = "根据每个博主最近的视频，自动找到他的主页，取头像、昵称、粉丝数和简介";
      btn.addEventListener("click", () => { const todo = vnCpbTodo(bar._groups); if (todo.length) vnCpbStart(todo); });
      const sum = document.createElement("span"); sum.className = "vn-cpb-sum";
      bar.appendChild(btn); bar.appendChild(sum);
    }
  }
  if (running) {
    const pct = d.total ? Math.round(d.done * 100 / d.total) : 0;
    bar.querySelector(".vn-cpb-track > i").style.width = pct + "%";
    const txt = "正在识别博主主页 " + d.done + " / " + d.total +
      (d.current ? " · 正在找「" + d.current + "」" : "") +
      " · 成功 " + (d.ok + d.noav) + (d.fail ? " · 没找到 " + d.fail : "") +
      (d.eta ? " · 预计还要 " + _vnFmtDur(d.eta) : "");
    const el = bar.querySelector(".vn-cpb-txt"); el.textContent = txt; el.title = txt;
    const note = bar.querySelector(".vn-cpb-note");
    note.hidden = !d.note; note.textContent = d.note ? "⏸ " + d.note : "";
    const ws = document.getElementById("vnWallSum");
    if (ws) ws.textContent = "正在识别博主主页 " + d.done + " / " + d.total + " · 成功 " + (d.ok + d.noav);
    vnCpbIcon(bar, true, 0);
    bar.hidden = false;
    return;
  }
  const todo = vnCpbTodo(bar._groups);
  vnCpbIcon(bar, false, todo.length);
  const btn = bar.querySelector(".vn-cpb-btn"), sum = bar.querySelector(".vn-cpb-sum");
  btn.disabled = !todo.length;
  btn.textContent = todo.length ? "🔍 一键识别博主主页（" + todo.length + " 个还没主页）" : "✓ 博主都有主页了";
  sum.innerHTML = "";
  bar.querySelectorAll(".vn-cpb-list").forEach((x) => x.remove());
  const ws = document.getElementById("vnWallSum");
  if (ws) {
    const gs = bar._groups || [];
    const haveN = gs.filter((g) => (_vnProfiles[g.key] || {}).url).length;
    ws.textContent = "已有主页 " + haveN + " 个" + (todo.length ? " · 还有 " + todo.length + " 个没主页" : "");
  }
  const ren = (d && d.renamed) || [];
  if (d && d.finished && d.total) {
    let s = "上次识别了 " + d.done + " 个：成功 " + (d.ok + d.noav) +
      (d.noav ? "（其中 " + d.noav + " 个没取到头像）" : "") +
      (d.fail ? "，没找到 " + d.fail : "") + (d.skip ? "，跳过 " + d.skip : "") + "。" +
      (ren.length ? "其中 " + ren.length + " 个博主改了名，软件里已换成新名字。" : "");
    if (d.note) s += d.note;
    sum.appendChild(document.createTextNode(s));
    const bad = (d.results || []).filter((r) => r.status !== "ok");
    if (bad.length || ren.length) {
      const more = document.createElement("a");
      more.href = "#"; more.className = "vn-cpb-more"; more.textContent = "看看详情 ›";
      const listEl = document.createElement("div"); listEl.className = "vn-cpb-list"; listEl.hidden = true;
      ren.forEach((t) => { const row = document.createElement("div"); row.textContent = "✎ 博主改名：" + t; listEl.appendChild(row); });
      bad.forEach((r) => {
        const row = document.createElement("div");
        row.textContent = r.status === "noav" ? "△ " + r.key + "：找到了主页（" + (r.msg || "") + "），但没取到头像，可以进去上传一张"
          : (r.status === "fail" ? "✗ " : "－ ") + r.key + "：" + (r.msg || "");
        listEl.appendChild(row);
      });
      more.addEventListener("click", (e) => {
        e.preventDefault(); listEl.hidden = !listEl.hidden;
        more.textContent = listEl.hidden ? "看看详情 ›" : "收起";
      });
      sum.appendChild(more);
      bar.appendChild(listEl);
    }
  } else {
    sum.textContent = "";
  }
  bar.hidden = !(d && d.finished && d.total);      // v79：平时不占地方；识别时显示进度，识别完显示结果
}

// v79：「一键识别博主主页」→ 博主标题行里的小图标（🔍 + 还没主页的个数）；识别时图标转圈，进度在下面
function vnCpbIcon(bar, running, todoN) {
  const head = bar._head || document.querySelector(".vn-wall-head");
  if (!head) return;
  let ic = head.querySelector(".vn-cpb-icon");
  if (!ic) {
    ic = document.createElement("button");
    ic.type = "button"; ic.className = "vn-cpb-icon";
    ic.innerHTML = '<span class="vn-cpb-ico">🔍</span><span class="vn-cpb-n"></span>';
    ic.addEventListener("click", (e) => {
      e.stopPropagation();
      if (ic.dataset.running === "1") return;
      const todo = vnCpbTodo(bar._groups);
      if (todo.length) vnCpbStart(todo);
    });
    const ws = head.querySelector("#vnWallSum");
    const ttl = head.querySelector(".vn-chead-title");
    if (ws) ws.after(ic); else if (ttl) ttl.after(ic); else head.appendChild(ic);
  }
  const ws2 = head.querySelector("#vnWallSum");            // 「还有 N 个没主页」那行字后加上来的：图标挪到它后面
  if (ws2 && ic.previousElementSibling !== ws2) ws2.after(ic);
  ic.dataset.running = running ? "1" : "0";
  ic.classList.toggle("busy", !!running);
  ic.disabled = !running && !todoN;
  const n = ic.querySelector(".vn-cpb-n");
  n.textContent = todoN ? String(todoN) : "";
  n.hidden = !todoN || !!running;
  ic.title = running ? "正在识别博主主页…（进度在下面，可以随时点「停止」）"
    : todoN ? "一键识别博主主页：还有 " + todoN + " 个博主没主页。根据每个博主最近的视频自动找到他的主页，取头像、昵称、粉丝数和简介"
    : "博主都有主页了";
}

async function vnCpbStart(keys) {
  const mins = Math.max(1, Math.round(keys.length * 13 / 60));   // v61：抖音要开后台浏览器找，每个十几秒
  if (!confirm("给 " + keys.length + " 个博主自动识别主页？\n\n" +
    "· 根据每个博主最近的视频找到他的主页，取头像、昵称、粉丝数和简介；\n" +
    "· 抖音要在后台开浏览器打开视频页去找，每个十几秒，大约要 " + mins + " 分钟，找到一个就换上一个头像；\n" +
    "· 可以随时点「停止」，下次接着找剩下的；\n" +
    "· 已经绑过主页的、你解除过绑定的都不会动。")) return;
  try {
    const d = await (await fetch(BACKEND + "/creator_profiles_batch", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keys }) })).json();
    if (!d.ok) { alert(d.message || "没能开始"); return; }
  } catch (e) { alert("出错：" + e.message); return; }
  vnCpbPoll();
}

async function vnCpbPoll() {
  clearTimeout(_vnCpbTimer); _vnCpbTimer = null;
  if (!document.getElementById("vnCpb")) return;
  let d;
  try {
    d = await (await fetch(BACKEND + "/creator_profiles_batch", { cache: "no-store" })).json();
  } catch (e) { _vnCpbTimer = setTimeout(vnCpbPoll, 4000); return; }
  if (!document.getElementById("vnCpb")) return;
  const rn = (d.renamed || []).length;
  if (_vnCpbRenamed !== -1 && rn !== _vnCpbRenamed) {
    _vnCpbRenamed = rn; _vnCpbSeen = d.done;
    await vnLoadProfiles();
    loadVideoNotes();                     // 名字变了，图标要重新分组；重画后会自己接着轮询
    return;
  }
  _vnCpbRenamed = rn;
  if (d.done !== _vnCpbSeen) {
    if (_vnCpbSeen !== -1) { await vnLoadProfiles(); vnRefreshTileAvatars(); }
    _vnCpbSeen = d.done;
  }
  vnCpbRender(document.getElementById("vnCpb"), d);
  if (d.running) _vnCpbTimer = setTimeout(vnCpbPoll, 2000);
}

function vnCreatorTile(g, sortKey) {
  const p = _vnProfiles[g.key] || {};
  const st = g.stats;
  const t = document.createElement("div");
  t.className = "vn-ctile";
  t.title = (p.name && p.name !== g.name ? g.name + "（" + p.name + "）" : g.name) +
    "\n笔记 " + st.total + " 条" + (st.recent ? "，近30天新增 " + st.recent + " 条" : "") +
    (st.last ? "\n最近提取：" + new Date(st.last).toLocaleString() : "") +
    (p.followers ? "\n粉丝：" + vnFmtNum(p.followers) : "") + "\n\n点击进去看" + (p.url ? "" : "；点右上角 🔗 绑定博主主页，自动换成真头像");
  t.appendChild(vnTileAvatar(g));
  t._g = g; t.dataset.avm = vnAvMarker(g.key);     // v60：资料变了能原地换头像
  const nm = document.createElement("div");
  nm.className = "vn-cname"; nm.textContent = g.name;
  t.appendChild(nm);
  const sub = document.createElement("div");
  sub.className = "vn-csub";
  sub.textContent = sortKey === "hot" ? (st.recent ? "近30天 +" + st.recent : "近30天没新增")
    : sortKey === "new" ? (st.first ? "首次 " + vnFmtWhen(st.first) : "")
    : sortKey === "total" || sortKey === "name" ? st.total + " 条"
    : (st.last ? vnFmtWhen(st.last) : st.total + " 条");
  t.appendChild(sub);
  const link = document.createElement("button");
  link.type = "button"; link.className = "vn-clink";
  link.textContent = "🔗"; link.title = p.url ? "更换博主主页链接" : "绑定博主主页（抖音 / B站 / YouTube…），自动取头像和资料";
  link.addEventListener("click", (e) => { e.stopPropagation(); vnBindProfile(g.key); });
  t.appendChild(link);
  t.addEventListener("click", () => vnIconGo({ kind: g.kind, name: g.name }));
  try { vnTileDrag(t, g); } catch (_) {}            // v89：长按拖到别的头像上 = 合并博主
  return t;
}

async function vnProfileAction(body, msgEl) {
  if (msgEl) msgEl.textContent = body.action === "auto" ? "正在根据这个博主的视频找主页，取头像和资料…（最多半分钟）"
    : body.action === "bind" || body.action === "refresh" ? "正在识别博主主页，取头像和资料…（最多半分钟）" : "处理中…";
  try {
    const d = await (await fetch(BACKEND + "/creator_profile", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();
    if (!d.ok) {
      if (msgEl) msgEl.textContent = "没成功：" + (d.message || "未知原因");
      else alert("没成功：" + (d.message || "未知原因"));
      await vnLoadProfiles();
      return false;
    }
    if (d.message && msgEl) msgEl.textContent = d.message;
    await vnLoadProfiles();
    loadVideoNotes();
    return true;
  } catch (e) {
    if (msgEl) msgEl.textContent = "出错：" + e.message; else alert("出错：" + e.message);
    return false;
  }
}

async function vnBindProfile(key, msgEl) {
  const p = _vnProfiles[key] || {};
  const v = await askText({
    title: (p.url ? "更换" : "绑定") + "「" + key + "」的主页",
    desc: "粘贴博主主页链接（抖音、B站、YouTube 等都行；抖音可以在博主主页点「分享 → 复制链接」，整段分享文字粘进来也行）。" +
      "软件会自动取头像、昵称、粉丝数和简介。\n不知道主页链接？留空直接点「绑定」，软件会根据这个博主的视频自动找。" +
      (p.url ? "\n现在绑的是：" + p.url : ""),
    placeholder: "https://…",
    okText: "绑定",
  });
  if (v === null) return;
  if (!v.trim()) { await vnProfileAction({ action: "auto", key }, msgEl); return; }
  await vnProfileAction({ action: "bind", key, url: v.trim() }, msgEl);
}

function vnUploadAvatar(key, msgEl) {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "image/*";
  inp.addEventListener("change", () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => vnProfileAction({ action: "avatar", key, data: r.result }, msgEl);
    r.readAsDataURL(f);
  });
  inp.click();
}

function vnProfileCard(g) {
  const p = _vnProfiles[g.key] || {};
  const st = g.stats;
  const card = document.createElement("div");
  card.className = "vn-cprof";
  card.appendChild(vnAvatarEl(g, "big"));
  const main = document.createElement("div");
  main.className = "vn-cprof-main";
  const nm = document.createElement("div");
  nm.className = "vn-cprof-name";
  nm.textContent = g.name;
  if (p.name && p.name !== g.name) {
    const real = document.createElement("span"); real.className = "vn-cprof-real"; real.textContent = p.name;
    nm.appendChild(real);
  }
  if (p.platform_label) {
    const pl = document.createElement("span"); pl.className = "vn-cprof-plat"; pl.textContent = p.platform_label;
    nm.appendChild(pl);
  }
  main.appendChild(nm);
  const meta = document.createElement("div");
  meta.className = "vn-cprof-meta";
  const parts = [];
  if (p.followers != null) parts.push("粉丝 " + vnFmtNum(p.followers));
  if (p.works != null) parts.push("作品 " + vnFmtNum(p.works));
  parts.push("笔记 " + st.total + " 条");
  if (st.recent) parts.push("近30天新增 " + st.recent + " 条");
  if (st.last) parts.push("最近提取 " + vnFmtWhen(st.last));
  meta.textContent = parts.join(" · ");
  main.appendChild(meta);
  if (p.signature) {
    const sg = document.createElement("div"); sg.className = "vn-cprof-sign"; sg.textContent = p.signature;
    main.appendChild(sg);
  }
  const acts = document.createElement("div");
  acts.className = "vn-cprof-acts";
  const msg = document.createElement("div");
  msg.className = "vn-cprof-msg";
  if (p.error) msg.textContent = "上次识别没成功：" + p.error;
  const btn = (text, tip, fn) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "vn-batch-stop"; b.textContent = text; b.title = tip;
    b.addEventListener("click", fn);
    acts.appendChild(b);
  };
  if (p.home || p.url) {
    const a = document.createElement("a");
    a.className = "vn-batch-stop vn-cprof-open"; a.textContent = "打开主页"; a.href = p.home || p.url; a.target = "_blank";
    a.title = p.home || p.url;
    acts.appendChild(a);
  }
  btn(p.url ? "更换主页链接" : "绑定博主主页", "粘贴抖音 / B站 / YouTube 等主页链接，自动取头像和资料", () => vnBindProfile(g.key, msg));
  if (!p.url) btn("🔍 自动找主页", "根据这个博主最新一条视频，自动找到他的主页，取头像和资料", () => vnProfileAction({ action: "auto", key: g.key }, msg));
  if (p.url) btn("刷新资料", "重新去主页取一次头像、粉丝数、简介", () => vnProfileAction({ action: "refresh", key: g.key }, msg));
  btn("上传头像", "用电脑里的一张图片当头像", () => vnUploadAvatar(g.key, msg));
  if (g.name !== "未填作者") {
    btn("🔗 合并…", "大小号、改过名的同一个人：合并成一个博主，笔记都算到一个名字下", () => vnMergeFlow(g, msg));
  }
  if (p.url || p.has_avatar) {
    btn("解除绑定", "删掉绑定的主页和头像", () => {
      if (confirm("解除「" + g.key + "」的主页绑定和头像？笔记不受影响。")) vnProfileAction({ action: "remove", key: g.key }, msg);
    });
  }
  main.appendChild(acts);
  const mine = (_vnMerges || []).filter((m) => m.dst === g.key);
  if (mine.length) {                           // v64：合并过谁，随时可以撤销
    const ml = document.createElement("div");
    ml.className = "vn-cprof-merged";
    ml.appendChild(document.createTextNode("已合并："));
    mine.forEach((m, i) => {
      if (i) ml.appendChild(document.createTextNode("、"));
      const nm2 = document.createElement("b"); nm2.textContent = m.src;
      nm2.title = (m.n || 0) + " 条笔记" + (m.at ? "，" + new Date(m.at * 1000).toLocaleString() + " 合并" : "");
      ml.appendChild(nm2);
      const u = document.createElement("button");
      u.type = "button"; u.className = "vn-cprof-undo"; u.textContent = "撤销";
      u.title = "把「" + m.src + "」分出来，笔记恢复成合并前的样子";
      u.addEventListener("click", () => vnUnmerge(m, msg));
      ml.appendChild(u);
    });
    main.appendChild(ml);
  }
  main.appendChild(msg);
  card.appendChild(main);
  return card;
}

// ════════════════════ v64：合并博主（大小号 / 同一个人用过两个名字） ════════════════════
// 同名的文件夹和作者、只差表情空格的名字，后台加载列表时会自动合并（见 _vnTidyMsgs 的提示）；
// 名字不一样的大小号，在博主资料卡上点「🔗 合并…」手动合并，合并后随时可以撤销。
let _vnMerges = [];
let _vnIconGroups = [];
let _vnTidyMsgs = [];

function vnRenderTidyTip(list) {
  if (!_vnTidyMsgs.length) return;
  const box = document.createElement("div");
  box.className = "vn-tidy-tip";
  const txt = document.createElement("div");
  txt.className = "vn-tidy-text";
  txt.textContent = _vnTidyMsgs.map((t) => "🔗 " + t).join("\n");
  const x = document.createElement("button");
  x.type = "button"; x.className = "vn-tidy-x"; x.textContent = "×"; x.title = "知道了";
  x.addEventListener("click", () => { _vnTidyMsgs = []; box.remove(); });
  box.appendChild(txt); box.appendChild(x);
  list.appendChild(box);
}

function vnNormName(s) {
  return String(s || "").normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

// 两个名字有多像：去掉表情、空格、标点后，最长的一段相同文字有多重——汉字等算 2，字母数字算 1
// （两个汉字一样就值得推荐；两个英文字母一样不算数）
function vnNameW(ch) { return /[\u0000-\u007f]/.test(ch) ? 1 : 2; }
function vnNameLike(a, b) {
  const x = [...vnNormName(a)], y = [...vnNormName(b)];
  if (!x.length || !y.length) return 0;
  let best = 0;
  for (let i = 0; i < x.length; i++) {
    for (let j = 0; j < y.length; j++) {
      let k = 0, w = 0;
      while (i + k < x.length && j + k < y.length && x[i + k] === y[j + k]) { w += vnNameW(x[i + k]); k++; }
      if (w > best) best = w;
    }
  }
  return best;
}

// 弹框：和谁合并、合并后用哪个名字。返回 {src, dst, other} 或 null（取消）
function vnAskMerge(g) {
  return new Promise((resolve) => {
    const seen = new Set([g.name]);
    const others = [];
    (_vnIconGroups || []).forEach((x) => {
      if (x.name === "未填作者" || seen.has(x.name)) return;
      seen.add(x.name);
      others.push(x);
    });
    const wOf = (n) => [...vnNormName(n)].reduce((t, ch) => t + vnNameW(ch), 0);
    const myW = wOf(g.name);
    const like = others.map((x) => ({ x, s: vnNameLike(g.name, x.name) }))
      .filter((o) => o.s >= 2 && o.s >= Math.min(4, myW, wOf(o.x.name)))   // 短名字整个包含在里面也算
      .sort((a, b) => b.s - a.s || b.x.items.length - a.x.items.length)
      .slice(0, 8).map((o) => o.x);
    const old = document.getElementById("vnMergeAsk");
    if (old) old.remove();
    const wrap = document.createElement("div");
    wrap.id = "vnMergeAsk"; wrap.className = "vn-merge-mask";
    const box = document.createElement("div");
    box.className = "vn-merge-box";
    box.innerHTML =
      '<div class="vn-merge-title"></div>' +
      '<div class="vn-merge-desc">大小号、改过名的同一个人，可以合并成一个博主：笔记都算到一个名字下，' +
      "以后这个号的新视频也会自动归进来。合并后在资料卡上随时可以撤销。</div>" +
      '<div class="vn-merge-lab">和谁合并？</div>' +
      '<input type="text" class="text-input vn-merge-input" list="vnMergeList" placeholder="输入名字搜索，或点下面推荐的" />' +
      '<datalist id="vnMergeList"></datalist>' +
      '<div class="vn-merge-like"></div>' +
      '<div class="vn-merge-lab">合并后用哪个名字？</div>' +
      '<div class="vn-merge-picks"><button type="button" class="send-btn vn-merge-keep" data-keep="me"></button>' +
      '<button type="button" class="send-btn vn-merge-keep" data-keep="other" disabled>先选上面要合并的博主</button></div>' +
      '<div class="vn-merge-row"><span class="vn-merge-note"></span><button type="button" class="vn-merge-cancel">取消</button></div>';
    box.querySelector(".vn-merge-title").textContent = "合并博主「" + g.name + "」";
    const dl = box.querySelector("#vnMergeList");
    others.forEach((x) => {
      const o = document.createElement("option");
      o.value = x.name; o.label = x.items.length + " 条" + (x.kind === "folder" ? " · 文件夹" : "");
      dl.appendChild(o);
    });
    const input = box.querySelector(".vn-merge-input");
    const likeBox = box.querySelector(".vn-merge-like");
    if (like.length) {
      const lab = document.createElement("span"); lab.className = "vn-merge-likelab"; lab.textContent = "名字相近的：";
      likeBox.appendChild(lab);
      like.forEach((x) => {
        const c = document.createElement("button");
        c.type = "button"; c.className = "vn-recent-chip";
        c.textContent = x.name;
        const b = document.createElement("b"); b.textContent = x.items.length + " 条"; c.appendChild(b);
        c.addEventListener("click", () => { input.value = x.name; sync(); });
        likeBox.appendChild(c);
      });
    } else {
      likeBox.textContent = "没找到名字相近的博主，在上面输入名字找。";
      likeBox.classList.add("empty");
    }
    const keepMe = box.querySelector('[data-keep="me"]'), keepOther = box.querySelector('[data-keep="other"]');
    const note = box.querySelector(".vn-merge-note");
    keepMe.disabled = true;
    keepMe.textContent = "用「" + g.name + "」（" + g.items.length + " 条）";
    let target = null;
    const sync = () => {
      const v = input.value.trim();
      target = others.find((x) => x.name === v) || null;
      likeBox.querySelectorAll(".vn-recent-chip").forEach((c) => c.classList.toggle("active", !!target && c.firstChild.textContent === target.name));
      keepMe.disabled = keepOther.disabled = !target;
      keepOther.textContent = target ? "用「" + target.name + "」（" + target.items.length + " 条）" : "先选上面要合并的博主";
      note.textContent = v && !target ? "没有叫「" + v + "」的博主" : "";
    };
    input.addEventListener("input", sync);
    const done = (val) => { try { wrap.remove(); } catch (_) {} resolve(val); };
    keepMe.addEventListener("click", () => target && done({ src: target.name, dst: g.name, other: target }));
    keepOther.addEventListener("click", () => target && done({ src: g.name, dst: target.name, other: target }));
    box.querySelector(".vn-merge-cancel").addEventListener("click", () => done(null));
    wrap.addEventListener("click", (e) => { if (e.target === wrap) done(null); });
    input.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); done(null); } });
    wrap.appendChild(box);
    document.body.appendChild(wrap);
    setTimeout(() => input.focus(), 0);
  });
}

async function vnMergeFlow(g, msgEl) {
  const r = await vnAskMerge(g);
  if (!r) return;
  const srcN = r.src === g.name ? g.items.length : r.other.items.length;
  if (!confirm("把「" + r.src + "」（" + srcN + " 条笔记）合并到「" + r.dst + "」名下？\n\n" +
      "· 「" + r.src + "」的笔记都会算到「" + r.dst + "」名下；\n" +
      "· 以后「" + r.src + "」的新视频也会自动归到「" + r.dst + "」；\n" +
      "· 合并后在「" + r.dst + "」的资料卡上随时可以撤销。")) return;
  if (msgEl) msgEl.textContent = "正在合并…";
  try {
    const d = await (await fetch(BACKEND + "/creator_merge", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ src: r.src, dst: r.dst }) })).json();
    if (!d.ok) { if (msgEl) msgEl.textContent = "没合并成：" + (d.message || "未知原因"); return; }
    _vnTidyMsgs = _vnTidyMsgs.concat([d.message || "合并好了"]).slice(-6);
    const kind = (g.kind === "folder" || r.other.kind === "folder") ? "folder" : "author";
    _vnIconPath = { kind, name: r.dst }; _vnIconPage = 1;
    await vnLoadProfiles();
    loadVideoNotes();
  } catch (e) {
    if (msgEl) msgEl.textContent = "出错：" + e.message;
  }
}

async function vnUnmerge(m, msgEl) {
  if (!confirm("撤销这次合并？\n\n「" + m.src + "」会重新分出来，它的笔记恢复成合并前的样子。")) return;
  if (msgEl) msgEl.textContent = "正在撤销…";
  try {
    const d = await (await fetch(BACKEND + "/creator_merge", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "undo", id: m.id }) })).json();
    if (!d.ok) { if (msgEl) msgEl.textContent = "没撤销成：" + (d.message || "未知原因"); return; }
    _vnTidyMsgs = _vnTidyMsgs.concat([d.message || "已撤销"]).slice(-6);
    await vnLoadProfiles();
    loadVideoNotes();
  } catch (e) {
    if (msgEl) msgEl.textContent = "出错：" + e.message;
  }
}

const VN_ICO_NOTE = '<svg viewBox="0 0 48 60" aria-hidden="true"><path d="M7 2h25l13 13v41a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#fff" stroke="#c8c8c8" stroke-width="2"/>' +
  '<path d="M32 2v11a2 2 0 0 0 2 2h11" fill="#f1f1f1" stroke="#c8c8c8" stroke-width="2"/>' +
  '<path d="M12 27h24M12 34h24M12 41h15" stroke="#a9b3c1" stroke-width="2.6" stroke-linecap="round"/>' +
  '<circle cx="35" cy="47" r="8" fill="#e25b3c"/><path d="M32.5 43.5v7l6-3.5z" fill="#fff"/></svg>';

function vnNoteTile(n) {
  const t = document.createElement("div");
  t.className = "vn-tile note";
  const when = vnNoteTime(n);
  const title = n.title || (n.name || "").replace(/\.md$/, "");
  t.title = title + (n.author ? "\n作者：" + n.author : "") + (when ? "\n提取时间：" + new Date(when).toLocaleString() : "") +
    "\n\n点击打开。移动、改作者、删除等操作请切到「列表」。";
  t.innerHTML = '<div class="vn-tile-ico">' + (n.kind ? vnDocIcon(n.kind) : VN_ICO_NOTE) + "</div>" +
    '<div class="vn-tile-name"></div><div class="vn-tile-sub"></div>' +
    (n.analyzed === false ? '<span class="vn-tile-tag">未分析</span>' : "");
  t.querySelector(".vn-tile-name").textContent = title;
  t.querySelector(".vn-tile-sub").textContent = (when ? vnFmtWhen(when) : "") + (n.author ? " · " + n.author : "");
  t.addEventListener("click", () => openVideoNote(n.name));
  return t;
}

function vnIconGo(path) {
  _vnIconPath = path; _vnIconPage = 1;
  loadVideoNotes();
}

function vnRenderIconView(list, notes, folders, byFolder, ungrouped) {
  const wrap = document.createElement("div");
  wrap.className = "vn-icons"; wrap.id = "vnIcons";
  // 和列表视图一样：没放进文件夹的笔记超过 12 条就按作者分组，否则直接平铺
  const authors = {};
  const groupAuthors = ungrouped.length > 12;
  if (groupAuthors) {
    ungrouped.forEach((n) => { const k = (n.author || "").trim() || "未填作者"; (authors[k] = authors[k] || []).push(n); });
  }
  const groups = [];
  folders.forEach((f) => groups.push({ kind: "folder", name: f, key: f, items: byFolder[f] || [] }));
  Object.keys(authors).forEach((k) => groups.push({ kind: "author", name: k, key: k, items: authors[k] }));
  groups.forEach((g) => { g.stats = vnGroupStats(g.items); });
  _vnIconGroups = groups;            // v64：「合并博主」选人用

  const p = _vnIconPath;
  const cur = p ? groups.find((g) => g.kind === p.kind && g.name === p.name) : null;
  if (p && !cur) _vnIconPath = null;

  if (!_vnIconPath) {
    // ── 最上层：博主头像墙 ──
    const sortKey = vnSortKey();
    const cmp = {
      last: (a, b) => b.stats.last - a.stats.last,
      hot: (a, b) => b.stats.recent - a.stats.recent || b.stats.last - a.stats.last,
      total: (a, b) => b.stats.total - a.stats.total,
      new: (a, b) => b.stats.first - a.stats.first,
      name: (a, b) => a.name.localeCompare(b.name, "zh"),
    }[sortKey] || ((a, b) => b.stats.last - a.stats.last);
    groups.sort((a, b) => (a.name === "未填作者") - (b.name === "未填作者") || cmp(a, b));

    const head = document.createElement("div");
    head.className = "vn-chead vn-wall-head";                // v63：整面墙可以折叠（像「最新提取」）
    head.title = "点击展开 / 收起";
    const wcaret = document.createElement("span"); wcaret.className = "vn-caret";
    head.appendChild(wcaret);
    const ttl = document.createElement("span");
    ttl.className = "vn-chead-title";
    ttl.textContent = "博主（" + groups.length + "）";
    head.appendChild(ttl);
    const sorts = document.createElement("div");
    sorts.className = "vn-csorts";
    const lab = document.createElement("span"); lab.textContent = "排序："; sorts.appendChild(lab);
    VN_SORTS.forEach(([k, label]) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "vn-recent-chip" + (k === sortKey ? " active" : "");
      b.textContent = label;
      b.title = { last: "最近提取过视频的排前面", hot: "最近 30 天新增笔记多的排前面", total: "笔记总数多的排前面",
        new: "最近才开始提取的博主排前面", name: "按名字排" }[k];
      b.addEventListener("click", () => { try { localStorage.setItem("vnCreatorSort", k); } catch (_) {} loadVideoNotes(); });
      sorts.appendChild(b);
    });
    head.appendChild(sorts);
    wrap.appendChild(head);
    const wbody = document.createElement("div"); wbody.className = "vn-wall-body";
    const cpb = vnCpbBar(groups);             // v60：一键识别博主主页（v79：按钮变成标题行里的小图标 🔍）
    cpb._head = head;
    vnCpbRender(cpb, cpb._last || null);
    wbody.appendChild(cpb);
    const tip = document.createElement("div");
    tip.className = "vn-auto-tip";
    tip.textContent = "圆角方形是你建的文件夹，圆形是按作者自动分的组。点头像进去看笔记。个别没找到主页的，" +
      "鼠标移到头像上点 🔗 粘贴主页链接（抖音 / B站 / YouTube…），或者点进去上传一张头像。" +
      "大小号：按住一个头像不放，拖到另一个头像上松开，就合并成一个博主（笔记放到一起）；拖到文件夹上就放进文件夹。";
    wbody.appendChild(tip);
    const grid = document.createElement("div");
    grid.className = "vn-cgrid";
    groups.forEach((g) => grid.appendChild(vnCreatorTile(g, sortKey)));
    wbody.appendChild(grid);
    if (!groupAuthors && ungrouped.length) {
      const t2 = document.createElement("div");
      t2.className = "vn-auto-tip"; t2.textContent = "还没放进文件夹的笔记";
      wbody.appendChild(t2);
      const g2 = document.createElement("div");
      g2.className = "vn-icon-grid notes";
      ungrouped.forEach((n) => g2.appendChild(vnNoteTile(n)));
      wbody.appendChild(g2);
    }
    const wsum = document.createElement("span"); wsum.className = "vn-wall-sum"; wsum.id = "vnWallSum";
    const haveN = groups.filter((g) => (_vnProfiles[g.key] || {}).url).length, todoN = vnCpbTodo(groups).length;
    wsum.textContent = "已有主页 " + haveN + " 个" + (todoN ? " · 还有 " + todoN + " 个没主页" : "");
    head.insertBefore(wsum, sorts);
    const applyW = (o) => { wbody.hidden = !o; sorts.hidden = !o; wcaret.textContent = o ? "▾" : "▸"; };
    let wOpen = true;
    try { wOpen = localStorage.getItem("vnWallOpen") !== "0"; } catch (_) {}
    applyW(wOpen);
    head.addEventListener("click", (e) => {
      if (e.target.closest(".vn-csorts")) return;            // 点排序按钮不折叠
      const o = wbody.hidden; applyW(o);
      try { localStorage.setItem("vnWallOpen", o ? "1" : "0"); } catch (_) {}
    });
    wrap.appendChild(wbody);
    list.appendChild(wrap);
    return;
  }

  // ── 进到某个博主 / 文件夹里 ──
  const crumb = document.createElement("div");
  crumb.className = "vn-crumb";
  const home = document.createElement("a");
  home.textContent = "全部"; home.href = "#";
  home.addEventListener("click", (e) => { e.preventDefault(); vnIconGo(null); });
  const sep = document.createElement("span"); sep.textContent = "›"; sep.className = "vn-crumb-sep";
  const here = document.createElement("span"); here.className = "vn-crumb-here";
  here.textContent = (cur.kind === "author" ? "作者：" : "") + cur.name + "（" + cur.items.length + " 条）";
  crumb.appendChild(home); crumb.appendChild(sep); crumb.appendChild(here);
  wrap.appendChild(crumb);
  wrap.appendChild(vnProfileCard(cur));

  const items = cur.items.slice().sort((a, b) => vnNoteTime(b) - vnNoteTime(a));
  const pages = Math.max(1, Math.ceil(items.length / VN_ICON_PAGE_SIZE));
  if (_vnIconPage > pages) _vnIconPage = pages;
  const grid = document.createElement("div");
  grid.className = "vn-icon-grid notes";
  const start = (_vnIconPage - 1) * VN_ICON_PAGE_SIZE;
  items.slice(start, start + VN_ICON_PAGE_SIZE).forEach((n) => grid.appendChild(vnNoteTile(n)));
  if (!items.length) {
    const em = document.createElement("div");
    em.className = "vn-recent-empty"; em.textContent = "这个文件夹是空的。";
    wrap.appendChild(em);
  }
  wrap.appendChild(grid);
  if (pages > 1) {
    const pager = document.createElement("div");
    pager.className = "vn-recent-pager";
    const btn = (text, page, disabled) => {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = text; b.disabled = disabled;
      b.addEventListener("click", () => {
        _vnIconPage = page; loadVideoNotes();
        setTimeout(() => document.getElementById("vnIcons")?.scrollIntoView({ block: "start" }), 120);
      });
      return b;
    };
    const pg = _vnIconPage;
    pager.appendChild(btn("首页", 1, pg === 1));
    pager.appendChild(btn("上一页", pg - 1, pg === 1));
    const info = document.createElement("span");
    info.textContent = "第 " + pg + " / " + pages + " 页（共 " + items.length + " 条，每页 " + VN_ICON_PAGE_SIZE + " 个）";
    pager.appendChild(info);
    pager.appendChild(btn("下一页", pg + 1, pg === pages));
    pager.appendChild(btn("末页", pages, pg === pages));
    wrap.appendChild(pager);
  }
  list.appendChild(wrap);
}


// ════════════════════ v73：嗅探页改成和视频页一样的结构 ════════════════════
// 一列从上往下：① 要做什么（标题骑在边框线上，可以收起）→ ② 进度（只在扫描 / 嗅探时出现）→ ③ 结果。
// 只是把原来的元素挪进新的卡片（按钮、列表、开关的功能都不变）；找不到要挪的元素就什么都不动，保持原样。
function vMakeCollapsible(card, key) {
  const head = card.querySelector(":scope > .v-card-head");
  if (!head || card.classList.contains("v-collapsible")) return;
  card.classList.add("v-collapsible");
  const caret = document.createElement("span"); caret.className = "v-col-caret";
  head.insertBefore(caret, head.firstChild);
  const hint = document.createElement("span"); hint.className = "v-col-hint"; hint.textContent = "已收起，点这里展开";
  head.appendChild(hint);
  head.title = "点击收起 / 展开";
  const set = (c) => {
    card.classList.toggle("v-collapsed", !!c);
    caret.textContent = c ? "▸" : "▾";
    try { localStorage.setItem(key, c ? "1" : "0"); } catch (_) {}
  };
  head.addEventListener("click", (e) => {
    if (e.target.closest("button, input, select, a")) return;
    set(!card.classList.contains("v-collapsed"));
  });
  card.addEventListener("click", (e) => {           // 收起时点卡片任何地方都能展开
    if (card.classList.contains("v-collapsed") && !e.target.closest(".v-card-head")) set(false);
  });
  card._vSetCollapsed = set;                       // v75：别处要打开它时用（比如点了博主头像）
  let c = false;
  try { c = localStorage.getItem(key) === "1"; } catch (_) {}
  set(c);
}

function snVHead(title) {
  const h = document.createElement("div"); h.className = "v-card-head";
  const t = document.createElement("span"); t.className = "v-card-title"; t.textContent = title;
  h.appendChild(t);
  return h;
}

// 原来的 sn-card → 视频页那样「标题骑在边框线上」的卡片；原来标题行里的按钮留在卡片里当工具条
function snAsVCard(card, title, titleExtras) {
  card.classList.add("v-card", "sn-vcard");
  const vh = snVHead(title);
  (titleExtras || []).forEach((el) => { if (el) vh.querySelector(".v-card-title").appendChild(el); });
  const old = card.querySelector(":scope > .sn-card-head");
  if (old) {
    const t = old.querySelector(":scope > .sn-card-title");
    if (t) t.remove();
    old.classList.add("sn-vcard-bar");
    if (!old.textContent.trim() && !old.querySelector("button, input, select")) old.remove();
  }
  card.insertBefore(vh, card.firstChild);
  return card;
}

// 进度卡片：里面有内容（正在扫描 / 嗅探）才出现，没有就收起来，不占地方（和视频页的「处理进度」一样）
function snProgressCard(title, els) {
  const card = document.createElement("div");
  card.className = "v-card sn-vcard sn-progress-card";
  card.appendChild(snVHead(title));
  els.forEach((el) => card.appendChild(el));
  const sync = () => {
    card.hidden = !els.some((el) => !el.hidden && getComputedStyle(el).display !== "none" && (el.textContent || "").trim());
  };
  const mo = new MutationObserver(sync);
  els.forEach((el) => mo.observe(el, { childList: true, subtree: true, characterData: true,
                                       attributes: true, attributeFilter: ["hidden", "style", "class"] }));
  setInterval(sync, 1500);
  sync();
  return card;
}

(function snRestructure() {
  try {
    // ── 博主新视频 ──
    const cp = document.querySelector('#view-sniff .sn-tabpane[data-pane="creators"]');
    const cg = cp && cp.querySelector(":scope > .sn-grid");
    const right = cg && cg.querySelector(".cw-rightcard");
    const left = cg && [...cg.querySelectorAll(".sn-card")].find((c) => c !== right && c.contains(document.getElementById("cwListBody")));
    const st = document.getElementById("cwScanState"), log = document.getElementById("cwScanLog");
    if (cg && left && right && st && log) {
      const stack = document.createElement("div"); stack.className = "sn-stack";
      snAsVCard(left, "👤 关注的博主", [document.getElementById("cwCount")]);
      const prog = snProgressCard("⏳ 扫描进度", [st, log]);
      snAsVCard(right, "新视频", []);
      stack.append(left, prog, right);
      cg.replaceWith(stack);
      vMakeCollapsible(left, "snCreatorsCollapsed");
      vMakeCollapsible(right, "snCreatorsNewCollapsed");     // v75：「新视频」也能收起
    }
    // ── 网站新动态 ──
    const wp = document.querySelector('#view-sniff .sn-tabpane[data-pane="web"]');
    const ov = wp && wp.querySelector(":scope > .sniff-overview");
    const tb = wp && wp.querySelector(":scope > .sn-toolbar");
    const guide = wp && wp.querySelector(":scope > .sn-fold-guide");
    const pr = document.getElementById("sniffProgress");
    const wg = wp && wp.querySelector(":scope > .sn-grid");
    const srcCard = wg && [...wg.querySelectorAll(".sn-card")].find((c) => c.contains(document.getElementById("sniffSources")));
    const feedCard = wg && [...wg.querySelectorAll(".sn-card")].find((c) => c.contains(document.getElementById("sniffFeed")));
    const tiles = document.getElementById("sniffCatTiles");
    if (ov && tb && pr && wg && srcCard && feedCard && tiles) {
      const start = document.createElement("div");
      start.className = "v-card sn-vcard";
      start.appendChild(snVHead("🌐 开始嗅探"));
      start.append(ov, tb);
      if (guide) start.appendChild(guide);
      const prog = snProgressCard("⏳ 嗅探进度", [pr]);
      snAsVCard(srcCard, "📌 盯着的网站", [document.getElementById("sniffSrcCount")]);
      snAsVCard(feedCard, "新动向", [document.getElementById("sniffCatActive")]);
      const fh = feedCard.querySelector(":scope > .v-card-head");
      fh.after(tiles);
      const stack = document.createElement("div"); stack.className = "sn-stack";
      stack.append(start, prog, srcCard, feedCard);
      wg.replaceWith(stack);
      vMakeCollapsible(start, "snWebStartCollapsed");
      vMakeCollapsible(srcCard, "snWebSrcCollapsed");
      vMakeCollapsible(feedCard, "snWebFeedCollapsed");      // v75：「新动向」也能收起
    }
  } catch (e) {
    console.warn("嗅探页换新结构没成功，保留原来的样子：", e);
  }
})();


// ════════════════════ v74：嗅探 · 博主列表做成头像墙 ════════════════════
// 头像墙：点头像看他的视频 / 文章（可以按 最新 / 最早 / 最热 / 标题 排）；批量扫描时，正在扫的那个博主
// 头像上有一道从左到右扫过的光，扫完换下一个；每个博主这次扫到多少条新的，显示在头像左上角。
// 头像上的按钮（扫一遍 / 改名 / 开关 / 删除）和原来列表里的是同一套，功能不变。
var _cwViewMode = (function () { try { return localStorage.getItem("cwViewMode") || "avatar"; } catch (_) { return "avatar"; } })();
var _cwLastList = [];
var _cwScanInfo = null;
var _cwOneResult = {};
var _cwVideoSort = (function () { try { return localStorage.getItem("cwVideoSort") || "new"; } catch (_) { return "new"; } })();
var _cwAvRetry = 0;

function _cwTileHtml(c) {
  const ic = _CW_PLAT_ICON[c.platform] || "🔗";
  const nm = c.title || "(未命名)";
  const ch = [...nm.replace(/^[@＠]/, "").trim()][0] || "?";
  const hue = typeof vnHue === "function" ? vnHue(nm) : 200;
  const av = c.avatar ? '<img src="' + BACKEND + "/creator_avatar?key=" + encodeURIComponent(c.avatar.key) +
    "&v=" + (c.avatar.v || 0) + '" alt="">' : "";
  const when = c.last_checked ? String(c.last_checked).replace(/^\d{4}-/, "").slice(0, 11) : "还没扫过";
  const sel = (_cwCurrentCreator.id === c.id) ? " sel" : "";
  return '<div class="cw-creator cw-tile' + (c.enabled ? "" : " off") + sel + '" data-id="' + escapeHtml(c.id) + '">' +
    '<div class="cw-c-main" title="点头像看「' + escapeHtml(nm) + '」的视频 / 文章">' +
      '<div class="cw-tava" style="--h:' + hue + '"><span class="cw-tletter">' + escapeHtml(ch) + "</span>" + av +
        '<span class="cw-tplat">' + ic + '</span><span class="cw-badge" hidden></span><span class="cw-sweep"></span></div>' +
      '<div class="cw-tname">' + escapeHtml(nm) + "</div>" +
      '<div class="cw-tsub">' + escapeHtml((c.platform_label || "") + " · " + when) + "</div>" +
      (c.last_error ? '<div class="cw-terr" title="' + escapeHtml(c.last_error) + '">⚠ 上次没扫成</div>' : "") +
    "</div>" +
    '<div class="cw-tacts">' +
      '<button class="cw-iconbtn cw-scan-one" title="扫一遍找新视频">↻</button>' +
      '<button class="cw-iconbtn cw-parse-one" title="解析他的主页：头像、昵称、粉丝数、简介">🔍</button>' +
      '<button class="cw-iconbtn cw-edit" title="改名 / 备注">✎</button>' +
      '<label class="sniff-switch sniff-switch-sm" title="开启 / 暂停（暂停后不参与每天自动扫）"><input type="checkbox" class="cw-tog"' +
        (c.enabled ? " checked" : "") + ' /><span class="sniff-switch-track"></span></label>' +
      '<button class="cw-iconbtn cw-del" title="删除">✕</button>' +
    "</div></div>";
}

function _cwTilesMark() {
  const box = document.getElementById("cwList");
  if (!box) return;
  const scan = _cwScanInfo || {};
  const log = Array.isArray(scan.log) ? scan.log : [];
  const byId = {}, byName = {};
  log.forEach((x) => { if (x.id) byId[x.id] = x; if (x.name) byName[x.name] = x; });
  const fcount = {};
  (typeof _cwFindings !== "undefined" ? _cwFindings : []).forEach((f) => {
    const k = String(f.creator_id == null ? "" : f.creator_id);
    if (k) fcount[k] = (fcount[k] || 0) + 1;
  });
  box.querySelectorAll(".cw-tile").forEach((t) => {
    const id = t.dataset.id;
    const c = _cwLastList.find((x) => x.id === id) || {};
    const now = !!scan.running && (scan.current_id ? scan.current_id === id : (!!scan.current && scan.current === c.title));
    t.classList.toggle("scanning", now || t.classList.contains("scanning-one"));
    let r = byId[id] || (c.title ? byName[c.title] : null) || null;
    const one = _cwOneResult[id];
    if (one && (!r || one.ts > (r.ts || 0) * 1000)) {
      r = { new_count: one.res.new_count, first_time: one.res.first_time, error: one.res.error };
    }
    const b = t.querySelector(".cw-badge");
    if (!b) return;
    let txt = "", cls = "", tip = "";
    if (r) {
      if (r.error) { txt = "⚠"; cls = "err"; tip = "这次没扫成：" + r.error; }
      else if (r.first_time) { txt = "首次"; cls = "first"; tip = "第一次扫：只记录现状，下次起才报新视频"; }
      else if (r.new_count) { txt = "+" + r.new_count; cls = "new"; tip = "这次扫到 " + r.new_count + " 条新的"; }
      else { txt = "0"; cls = "zero"; tip = "这次没有新的"; }
    } else if (fcount[id]) {
      txt = "+" + fcount[id]; cls = "new"; tip = "「扫出来的新视频」里有 " + fcount[id] + " 条是他的";
    }
    b.hidden = !txt; b.textContent = txt; b.className = "cw-badge " + cls; b.title = tip;
  });
}

function _cwModeChips() {
  const head = document.getElementById("cwListToggle");
  if (!head || head.querySelector(".cw-mode")) return;
  const w = document.createElement("span");
  w.className = "cw-mode";
  [["avatar", "头像"], ["list", "列表"]].forEach(([m, label]) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = label; b.dataset.m = m;
    b.className = "vn-recent-chip" + (m === _cwViewMode ? " active" : "");
    b.title = m === "avatar" ? "头像墙：点头像看他的视频 / 文章" : "列表：一行一个博主";
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      _cwViewMode = m;
      try { localStorage.setItem("cwViewMode", m); } catch (_) {}
      w.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x.dataset.m === m));
      renderCreators(_cwLastList);
    });
    w.appendChild(b);
  });
  head.appendChild(w);
}

var _cwRenderCreatorsOrig = renderCreators;
renderCreators = function (list) {
  _cwLastList = list || [];
  _cwRenderCreatorsOrig(list);
  try {
    _cwModeChips();
    const box = document.getElementById("cwList");
    if (box) {
      box.querySelectorAll(".cw-tava img").forEach((img) => img.addEventListener("error", () => img.remove()));
      box.querySelectorAll(".cw-tile .cw-c-main").forEach((m) => m.addEventListener("click", () => {
        setTimeout(() => document.getElementById("cwVideoView")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
      }));
    }
    _cwTilesMark();
    const avSig = _cwLastList.filter((c) => c.avatar).map((c) => c.id + ":" + c.avatar.v).join(",");
    if (avSig !== _cwAvSig) {                      // v81：头像有变化 → 「扫出来的新视频」重画，换上 mini 头像
      _cwAvSig = avSig;
      if (typeof renderFindings === "function" && Array.isArray(_cwFindings) && _cwFindings.length) {
        try { renderFindings(_cwFindings); } catch (_) {}
      }
    }
    if (box) box.querySelectorAll(".cw-tile .cw-parse-one").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      const t = b.closest(".cw-tile");
      t.classList.add("parsing");
      _cwParseStart([t.dataset.id], true);
    }));
    _cwParseBarUpdate(); _cwParseMark();
    if (!_cwParsePolled) { _cwParsePolled = true; _cwParsePoll(); }
    if (_cwCurrentCreator.id && !document.getElementById("cwVideoView")?.hidden) _cwProfileLine(_cwCurrentCreator.id);
    // 有博主还没头像：后台在取，过一会儿再刷新一次列表把头像换上（最多 3 次）
    if (_cwViewMode === "avatar" && _cwAvRetry < 3 &&
        _cwLastList.some((c) => !c.avatar && ["youtube", "douyin", "bilibili", "x", "web"].includes(c.platform))) {
      _cwAvRetry++;
      setTimeout(() => { try { loadCreators(); } catch (_) {} }, 45000);
    }
  } catch (_) {}
};

// 单个「扫一遍」：点下去那一刻这个头像就开始扫光，扫完列表会重画
document.getElementById("cwList")?.addEventListener("click", (e) => {
  const b = e.target.closest(".cw-tile .cw-scan-one");
  if (b) b.closest(".cw-tile").classList.add("scanning-one", "scanning");
}, true);

// ── 他的视频 / 文章：按 最新 / 最早 / 最热 / 标题 排 ──
function _cwApplySort() {
  if (!Array.isArray(_cwVideos) || !_cwVideos.length) return;
  _cwVideos.forEach((v, i) => { if (v._o == null) v._o = i; });
  const d = (v) => (/^\d{8}$/.test(v.when || "") ? +v.when : null);
  const cmp = {
    new: (a, b) => ((d(b) ?? -1) - (d(a) ?? -1)) || (a._o - b._o),
    old: (a, b) => ((d(a) ?? 0) - (d(b) ?? 0)) || (b._o - a._o),
    hot: (a, b) => ((b.views ?? -1) - (a.views ?? -1)) || (a._o - b._o),
    title: (a, b) => String(a.title_zh || a.title || "").localeCompare(String(b.title_zh || b.title || ""), "zh") || (a._o - b._o),
  }[_cwVideoSort] || ((a, b) => a._o - b._o);
  _cwVideos.sort(cmp);
}

function _cwSortBar() {
  const list = document.getElementById("cwVideos");
  if (!list) return;
  let bar = document.getElementById("cwSortBar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "cwSortBar"; bar.className = "cw-sortbar";
    const lab = document.createElement("span"); lab.textContent = "排序：";
    bar.appendChild(lab);
    [["new", "最新"], ["old", "最早"], ["hot", "最热"], ["title", "标题"]].forEach(([k, label]) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "vn-recent-chip"; b.dataset.k = k; b.textContent = label;
      b.addEventListener("click", () => {
        if (b.disabled) return;
        _cwVideoSort = k;
        try { localStorage.setItem("cwVideoSort", k); } catch (_) {}
        _cwPage = 1;
        renderVideos();
      });
      bar.appendChild(b);
    });
    list.parentNode.insertBefore(bar, list);
  }
  const hasHot = (_cwVideos || []).some((v) => v.views != null);
  bar.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.k === _cwVideoSort);
    if (b.dataset.k === "hot") {
      b.disabled = !hasHot;
      b.title = hasHot ? "按播放量 / 点赞量从高到低" : "这个平台没给播放量 / 点赞量（点「刷新」重新列一次试试）";
    }
  });
  bar.hidden = !(_cwVideos || []).length;
}

// v75：点博主（头像或列表里的）看他的视频时，「新视频」卡片收起着就先展开，不然看不到
var _cwOpenCreatorVideosOrig = openCreatorVideos;
openCreatorVideos = function (cid, title) {
  try {
    const card = document.getElementById("cwVideoView")?.closest(".v-collapsible");
    if (card && card.classList.contains("v-collapsed") && card._vSetCollapsed) card._vSetCollapsed(false);
  } catch (_) {}
  const r = _cwOpenCreatorVideosOrig(cid, title);
  try { _cwProfileLine(cid); } catch (_) {}         // v76：他的主页资料
  return r;
};


// ════════════════════ v76：嗅探 · 一键解析博主主页（头像 + 昵称 + 粉丝数 + 简介） ════════════════════
// 和视频页的「一键识别博主主页」一样：博主列表上面一个按钮 + 进度；每个头像上还有 🔍 单独解析（有头像的也能重新解析）。
// 正在解析的那个头像有扫光（蓝圈），解析到一个就马上换上；点头像时，视频列表上面显示他的主页资料。
var _cwParseState = null, _cwParseTimer = null, _cwParseDone = -1, _cwParseErrOpen = false, _cwParsePolled = false;

function _cwParseNeed() {
  return _cwLastList.filter((c) => !c.avatar && ["youtube", "douyin", "bilibili", "x", "web"].includes(c.platform)).length;
}

function _cwParseBar() {
  const body = document.getElementById("cwListBody"), list = document.getElementById("cwList");
  if (!body || !list) return null;
  let bar = document.getElementById("cwParseBar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "cwParseBar"; bar.className = "cw-parsebar";
    bar.innerHTML = '<button type="button" class="sn-btn sm cw-parse-all"></button><span class="cw-parse-msg"></span>' +
      '<button type="button" class="sn-btn sm cw-parse-stop" hidden>停止</button>' +
      '<button type="button" class="cw-parse-errbtn" hidden></button><div class="cw-parse-errs" hidden></div>';
    body.insertBefore(bar, list);
    bar.querySelector(".cw-parse-all").addEventListener("click", () => _cwParseStart([], false));
    bar.querySelector(".cw-parse-stop").addEventListener("click", async (e) => {
      e.currentTarget.disabled = true; e.currentTarget.textContent = "正在停止…";
      try { await fetch(BACKEND + "/creator/avatars", { method: "POST", headers: { "Content-Type": "application/json" },
                                                         body: JSON.stringify({ action: "stop" }) }); } catch (_) {}
      _cwParsePoll();
    });
    bar.querySelector(".cw-parse-errbtn").addEventListener("click", () => { _cwParseErrOpen = !_cwParseErrOpen; _cwParseBarUpdate(); });
  }
  return bar;
}

function _cwParseBarUpdate() {
  const bar = _cwParseBar();
  if (!bar) return;
  const st = _cwParseState || {};
  const need = _cwParseNeed();
  const all = bar.querySelector(".cw-parse-all"), msg = bar.querySelector(".cw-parse-msg");
  const stop = bar.querySelector(".cw-parse-stop"), eb = bar.querySelector(".cw-parse-errbtn"), errs = bar.querySelector(".cw-parse-errs");
  all.hidden = !!st.running;
  all.textContent = "🔍 一键解析博主主页" + (need ? "（" + need + " 个还没头像）" : "");
  all.title = "去每个还没头像的博主主页取头像、昵称、粉丝数和简介（X 用你存的 X Cookie；YouTube 搜索链接会从他的频道 / 视频找主页）。" +
    "已经有头像的想重新取，鼠标移到头像上点 🔍";
  if (stop.hidden === !!st.running) { stop.disabled = false; stop.textContent = "停止"; }
  stop.hidden = !st.running;
  if (st.running) {
    msg.textContent = (st.manual ? "正在解析 " : "正在自动解析 ") + Math.min(st.total, st.done + 1) + " / " + st.total +
      (st.current ? " · 正在找「" + st.current + "」" : "") + " · 成功 " + (st.ok || 0) + (st.fail ? " · 没成功 " + st.fail : "");
  } else if (st.finished && st.total) {
    msg.textContent = "上次解析：成功 " + (st.ok || 0) + (st.fail ? "，没成功 " + st.fail : "") + (st.manual ? "" : "（自动）");
  } else {
    msg.textContent = need ? "" : "所有博主都有头像了";
  }
  const e = st.errors || [];
  eb.hidden = !e.length || !!st.running;
  eb.textContent = _cwParseErrOpen ? "收起" : "看看没成功的（" + e.length + "）";
  errs.hidden = !_cwParseErrOpen || !e.length || !!st.running;
  errs.innerHTML = e.map((x) => "<div><b>" + escapeHtml(x.name) + "</b>：" + escapeHtml(x.why) + "</div>").join("");
}

function _cwParseMark() {
  const st = _cwParseState || {};
  document.querySelectorAll("#cwList .cw-tile").forEach((t) => {
    t.classList.toggle("parsing", !!st.running && st.current_id === t.dataset.id);
  });
}

async function _cwParseStart(ids, force) {
  try {
    const d = await (await fetch(BACKEND + "/creator/avatars", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start", ids: ids || [], force: !!force }) })).json();
    if (typeof _cwSetStatus === "function") _cwSetStatus(d.message || (d.ok ? "开始解析" : "没开始"));
    if (!d.ok) document.querySelectorAll("#cwList .cw-tile.parsing").forEach((t) => t.classList.remove("parsing"));
  } catch (e) {
    if (typeof _cwSetStatus === "function") _cwSetStatus("出错：" + e.message);
  }
  _cwParsePoll();
}

async function _cwParsePoll() {
  clearTimeout(_cwParseTimer);
  let st;
  try { st = await (await fetch(BACKEND + "/creator/avatars_status", { cache: "no-store" })).json(); }
  catch (_) { _cwParseTimer = setTimeout(_cwParsePoll, 4000); return; }
  const was = !!(_cwParseState && _cwParseState.running);
  _cwParseState = st;
  const changed = _cwParseDone !== -1 && st.done !== _cwParseDone;
  _cwParseDone = st.done;
  if (changed || (was && !st.running)) loadCreators();     // 解析到一个就刷新，头像马上换上
  _cwParseBarUpdate(); _cwParseMark();
  if (st.running) _cwParseTimer = setTimeout(_cwParsePoll, 1500);
}

// 点头像后，视频列表上面：他的主页资料（头像、昵称、平台、粉丝数、作品数、简介、打开主页、重新解析）
function _cwProfileLine(cid) {
  const list = document.getElementById("cwVideos");
  if (!list) return;
  let box = document.getElementById("cwProfLine");
  if (!box) {
    box = document.createElement("div");
    box.id = "cwProfLine"; box.className = "cw-profline";
    list.parentNode.insertBefore(box, document.getElementById("cwSortBar") || list);
  }
  const c = _cwLastList.find((x) => x.id === cid);
  if (!c) { box.hidden = true; return; }
  box.hidden = false;
  const p = c.profile || {};
  const nm = c.title || "(未命名)";
  const ch = [...nm.replace(/^[@＠]/, "").trim()][0] || "?";
  const hue = typeof vnHue === "function" ? vnHue(nm) : 200;
  const fmt = (n) => (typeof vnFmtNum === "function" ? vnFmtNum(n) : String(n));
  const meta = [];
  if (p.platform_label || c.platform_label) meta.push(p.platform_label || c.platform_label);
  if (p.followers != null) meta.push("粉丝 " + fmt(p.followers));
  if (p.works != null) meta.push("作品 " + fmt(p.works));
  const home = p.home || p.url || (/^https?:/.test(c.url || "") && !/results\?search_query/.test(c.url) ? c.url : "");
  box.innerHTML =
    '<div class="cw-tava cw-pava" style="--h:' + hue + '"><span class="cw-tletter">' + escapeHtml(ch) + "</span>" +
      (c.avatar ? '<img src="' + BACKEND + "/creator_avatar?key=" + encodeURIComponent(c.avatar.key) + "&v=" + (c.avatar.v || 0) + '" alt="">' : "") +
    "</div>" +
    '<div class="cw-pmain">' +
      '<div class="cw-pname">' + escapeHtml(nm) +
        (p.name && p.name !== nm ? "<small>主页上叫「" + escapeHtml(p.name) + "」</small>" : "") + "</div>" +
      '<div class="cw-pmeta">' + escapeHtml(meta.join(" · ") || "还没解析过他的主页") + "</div>" +
      (p.signature ? '<div class="cw-psign"></div>' : "") +
      (p.error && !c.avatar ? '<div class="cw-perr"></div>' : "") +
      '<div class="cw-pacts">' + (home ? '<a class="sn-btn sm" target="_blank" href="' + escapeHtml(home) + '">打开主页</a>' : "") +
        '<button type="button" class="sn-btn sm cw-preparse">🔍 ' + (c.avatar || p.followers != null ? "重新解析" : "解析主页") + "</button></div>" +
    "</div>";
  if (p.signature) box.querySelector(".cw-psign").textContent = p.signature;
  if (p.error && !c.avatar) box.querySelector(".cw-perr").textContent = "上次没解析成：" + p.error;
  box.querySelector(".cw-pava img")?.addEventListener("error", (e) => e.target.remove());
  box.querySelector(".cw-preparse").addEventListener("click", () => {
    document.querySelector('#cwList .cw-tile[data-id="' + cid + '"]')?.classList.add("parsing");
    _cwParseStart([cid], true);
  });
}


// ════════════════════ v78 / v79：嗅探 · 网站也能当「博主」盯 + 搜索推荐 ════════════════════
// 「添加博主」：不是视频平台的链接（官方博客、新闻页……）按「网站」加进来，网站图标当头像，扫描时读 RSS / 网页里的新文章。
// 「搜索推荐」：输入想看的领域 → AI 池联网找出前 N 个网站和博主 → 勾选 → 一键加进「关注的博主」。
// v79：嗅探页、视频页各有一个搜索面板（.cwf-panel），共用后台同一次搜索；搜索时面板里显示 AI 实时画面。
_CW_PLAT_ICON.web = "🌐";
var _cwFindTimer = null, _cwFindRes = [], _cwFindAdded = {}, _cwFindLast = {};
var _cwFindGone = new Set();        // v80：已经加好的，从推荐清单里拿掉

function _cwfPanels() { return [...document.querySelectorAll(".cwf-panel")]; }
function _cwfShown(root) { const k = root.querySelector(".cwf-kw"); return !!(k && k.offsetParent !== null); }

function _cwfRenderPanel(root, st) {
  const stage = root.querySelector(".cwf-stage"), list = root.querySelector(".cwf-list");
  const acts = root.querySelector(".cwf-acts"), btn = root.querySelector(".cwf-btn");
  if (!list || !stage) return;
  st = st || {};
  if (btn) { btn.disabled = !!st.running; btn.textContent = st.running ? "搜索中…" : "搜索"; }
  const kw = root.querySelector(".cwf-kw");
  if (kw && st.keyword && !kw.value && st.running) kw.value = st.keyword;
  const msg = st.error ? "没搜成：" + st.error : (st.stage || "");
  stage.hidden = !msg && !st.note;
  stage.classList.toggle("err", !!st.error);
  stage.innerHTML = escapeHtml(msg) + (st.note ? '<div class="cw-find-note">' + escapeHtml(st.note) + "</div>" : "");
  const res = st.results || [];
  _cwFindRes = res;
  const checked = new Set([...list.querySelectorAll(".cw-find-row input:checked")].map((i) => i.dataset.u));
  list.innerHTML = res.map((it, i) => {
    if (_cwFindGone.has(it.url)) return "";
    const added = _cwFindAdded[it.url];
    const dis = !!it.exists || added === true || it.status === "fail";
    const txt = added === true ? "✓ 已加入" : typeof added === "string" ? "✗ " + added
      : it.exists ? "已在关注的博主里" : it.status === "ok" ? "✓ " + (it.detail || "能打开")
      : it.status === "fail" ? "✗ " + (it.detail || "打不开") : it.status === "checking" ? "检查中…" : (it.detail || "");
    const cls = (added === true || it.status === "ok") ? "ok" : (typeof added === "string" || it.status === "fail") ? "fail" : "";
    return '<label class="cw-find-row' + (dis ? " off" : "") + '">' +
      '<input type="checkbox" data-i="' + i + '" data-u="' + escapeHtml(it.url) + '"' +
        (dis ? " disabled" : (checked.has(it.url) ? " checked" : "")) + ">" +
      '<span class="cw-find-ico">' + (_CW_PLAT_ICON[it.platform] || "🌐") + "</span>" +
      '<div class="cw-find-main"><div class="cw-find-name">' + escapeHtml(it.name || "") +
        '<span class="cw-find-kind">' + escapeHtml(it.kind || "") + (it.region ? " · " + escapeHtml(it.region) : "") + "</span></div>" +
        '<a class="cw-find-url" href="' + escapeHtml(it.url) + '" target="_blank">' + escapeHtml(it.url) + "</a>" +
        (it.why ? '<div class="cw-find-why">' + escapeHtml(it.why) + "</div>" : "") + "</div>" +
      '<span class="cw-find-st ' + cls + '">' + escapeHtml(txt) + "</span></label>";
  }).join("");
  if (acts) acts.hidden = !res.some((it) => !_cwFindGone.has(it.url)) || !!st.running;
}

function _cwFindRender(st) { _cwfPanels().forEach((r) => _cwfRenderPanel(r, st)); }

// AI 实时画面（小号）：AI 池浏览器的实时截图 + 它正在写的回复，样子和「批量 AI 分析」里的一样
function aiLiveBuild() {
  const box = document.createElement("div");
  box.className = "vn-live ai-live-mini";
  box.innerHTML =
    '<div class="vn-live-head"><span class="vn-live-title">AI 实时画面</span><span class="vn-live-sum ai-live-sum"></span></div>' +
    '<div class="vn-live-body">' +
      '<div class="vn-live-stage ai-live-stage"></div>' +
      '<div class="vn-live-grid">' +
        '<div class="vn-live-shotbox"><img class="ai-live-shot" alt="" hidden />' +
          '<div class="vn-live-shotnote ai-live-note">等待画面…</div></div>' +
        '<div class="vn-live-side"><pre class="vn-live-reply ai-live-reply"></pre></div>' +
      "</div>" +
    "</div>";
  return box;
}

function aiLiveUpdate(box, d) {
  const p = (d && d.pool) || {};
  box.querySelector(".ai-live-stage").textContent = p.stage ? "AI 池：" + p.stage + (p.busy ? "" : "（空闲）") : "";
  const img = box.querySelector(".ai-live-shot"), note = box.querySelector(".ai-live-note");
  if (p.has_shot && p.shot_ts && (p.shot_ts !== box._ts || img.hidden)) {
    box._ts = p.shot_ts;
    img.src = BACKEND + "/ai_live_shot?t=" + encodeURIComponent(p.shot_ts);
    img.hidden = false;
  }
  if (!p.hasBrowser) note.textContent = p.headless ? "AI 池是后台模式（不显示浏览器），这里只有文字进度" : "AI 池浏览器还没打开（换卡 / 启动中）";
  else if (p.shot_err) note.textContent = "截图暂时失败，文字进度照常更新";
  else if (p.shot_ts) {
    const ago = Math.max(0, Math.round((d.now || 0) - p.shot_ts));
    note.textContent = ago <= 3 ? "实时画面" : "画面更新于 " + ago + " 秒前";
  } else note.textContent = "等待画面…";
  const rep = box.querySelector(".ai-live-reply");
  const nearBottom = rep.scrollHeight - rep.scrollTop - rep.clientHeight < 40;
  let txt = p.reply_tail || "";
  if (p.reply_len > txt.length) txt = "…（前面还有 " + (p.reply_len - txt.length) + " 字）\n" + txt;
  if (!txt) txt = p.busy ? "AI 还没开始写回复（可能在换卡、选模型、联网搜索中…）" : "（AI 池在排队或空闲，马上开始）";
  if (rep.textContent !== txt) { rep.textContent = txt; if (nearBottom) rep.scrollTop = rep.scrollHeight; }
}

async function _cwFindPoll() {
  clearTimeout(_cwFindTimer);
  let st;
  try { st = await (await fetch(BACKEND + "/creator/discover", { cache: "no-store" })).json(); }
  catch (_) { _cwFindTimer = setTimeout(_cwFindPoll, 4000); return; }
  _cwFindLast = st;
  _cwFindRender(st);
  const panels = _cwfPanels();
  const watch = !!st.running && panels.some(_cwfShown) && !document.hidden;
  let live = null;
  if (watch) { try { live = await (await fetch(BACKEND + "/ai_live?watch=1", { cache: "no-store" })).json(); } catch (_) {} }
  panels.forEach((r) => {
    const slot = r.querySelector(".cwf-live");
    if (!slot) return;
    slot.hidden = !st.running;
    if (!st.running) return;
    let box = slot.querySelector(".ai-live-mini");
    if (!box) { box = aiLiveBuild(); slot.appendChild(box); }
    if (live && _cwfShown(r)) aiLiveUpdate(box, live);
  });
  if (st.running) _cwFindTimer = setTimeout(_cwFindPoll, watch ? 1500 : 3000);
}

async function _cwfStart(root) {
  const box = root.querySelector(".cwf-kw");
  const kw = (box?.value || "").trim();
  if (!kw) { box?.focus(); return; }
  _cwFindAdded = {};
  _cwFindGone = new Set();
  _cwfPanels().forEach((r) => { const k = r.querySelector(".cwf-kw"); if (k && r !== root) k.value = kw; });
  const n = parseInt(root.querySelector(".cwf-n")?.value || "10", 10);
  try {
    const d = await (await fetch(BACKEND + "/creator/discover", { method: "POST", headers: { "Content-Type": "application/json" },
                                                                body: JSON.stringify({ keyword: kw, n }) })).json();
    if (!d.ok) { _cwFindRender(Object.assign({}, _cwFindLast, { error: d.message || "没开始", running: false })); return; }
  } catch (e) { _cwFindRender({ error: e.message }); return; }
  _cwFindPoll();
}

async function _cwfAdd(root, btn) {
  const picks = [...root.querySelectorAll(".cwf-list .cw-find-row input:checked")].map((i) => _cwFindRes[+i.dataset.i]).filter(Boolean);
  const say = (m) => { if (typeof _cwSetStatus === "function") _cwSetStatus(m); const sg = root.querySelector(".cwf-stage"); if (sg) { sg.hidden = false; sg.textContent = m; } };
  if (!picks.length) { say("先勾选要加的"); return; }
  btn.disabled = true;
  let n = 0;
  for (const it of picks) {
    btn.textContent = "正在加 " + (++n) + " / " + picks.length + "…";
    try {
      const d = await (await fetch(BACKEND + "/creator/add", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: it.url, platform: "auto", title: it.name || "" }) })).json();
      _cwFindAdded[it.url] = d.ok ? true : (d.message || "没加成");
    } catch (err) {
      _cwFindAdded[it.url] = err.message;
    }
    _cwFindRender(Object.assign({}, _cwFindLast, { results: _cwFindRes }));
  }
  btn.disabled = false; btn.textContent = "加入关注的博主";
  const cb = root.querySelector(".cwf-all"); if (cb) cb.checked = false;
  const okList = picks.filter((it) => _cwFindAdded[it.url] === true);
  const okN = okList.length, bad = picks.length - okN;
  okList.forEach((it) => _cwFindGone.add(it.url));       // v80：加好的从清单里拿掉，只留没加成的（看原因）
  _cwFindRender(Object.assign({}, _cwFindLast, { results: _cwFindRes }));
  try { await loadCreators(); } catch (_) {}
  const msg = okN ? "✓ 加好了 " + okN + " 个，在「嗅探 · 关注的博主」里" + (bad ? "；" + bad + " 个没加成，原因写在推荐清单里" : "") +
                    "。头像会在后台自动取，下次扫描起报新内容"
                  : bad + " 个都没加成，原因写在每行右边";
  say(msg);
  if (!okN || bad) return;                                // 有没加成的：留在这里，方便看原因
  // v80：全都加好了 → 搜索面板自己收起，跳到「博主列表」，新加的头像闪两下
  const det = root.closest("details");
  if (det) {
    det.open = false;
    const lh = document.getElementById("cwListToggle");
    if (lh && lh.classList.contains("collapsed")) lh.click();
    const ids = new Set(_cwLastList.filter((c) => okList.some((it) => it.url === c.url)).map((c) => c.id));
    const tiles = [...document.querySelectorAll("#cwList .cw-creator")].filter((t) => ids.has(t.dataset.id));
    tiles.forEach((t) => { t.classList.remove("cw-justadded"); void t.offsetWidth; t.classList.add("cw-justadded"); });
    setTimeout(() => (tiles[0] || document.getElementById("cwListBody"))?.scrollIntoView({ behavior: "smooth", block: "center" }), 300);
    setTimeout(() => tiles.forEach((t) => t.classList.remove("cw-justadded")), 5200);
  } else {
    const body = root.closest(".vfind")?.querySelector(".vfind-head");
    if (body && !root.hidden) body.click();               // 视频页：面板收起
    if (typeof setVideoStatus === "function") setVideoStatus(msg + "（去嗅探页就能看到）", "ok");
  }
}

function _cwfBind(root) {
  if (!root || root._cwfBound) return;
  root._cwfBound = true;
  root.querySelector(".cwf-btn")?.addEventListener("click", () => _cwfStart(root));
  root.querySelector(".cwf-kw")?.addEventListener("keydown", (e) => { if (e.key === "Enter") _cwfStart(root); });
  root.querySelector(".cwf-all")?.addEventListener("change", (e) => {
    root.querySelectorAll(".cwf-list .cw-find-row input:not(:disabled)").forEach((i) => { i.checked = e.target.checked; });
  });
  root.querySelector(".cwf-add")?.addEventListener("click", (e) => _cwfAdd(root, e.currentTarget));
  root.closest("details")?.addEventListener("toggle", () => _cwFindPoll());
}

// 视频页的搜索面板：放在「开始提取」卡片里、「维护工具」上面，样子和「维护工具」一样能折叠
function vFindBuild() {
  const card = document.querySelector(".v-card-extract");
  const tools = card && (card.querySelector(":scope > #viVideoSec") || card.querySelector(":scope > .video-tools"));   // v119：结果放在输入框下面、设置上面
  if (!card || !tools || document.getElementById("vFind")) return null;
  const wrap = document.createElement("div");
  wrap.id = "vFind"; wrap.className = "vfind";
  wrap.innerHTML =
    '<div class="vfind-head" role="button" tabindex="0">' +
      '<span class="vfind-caret">▸</span><span>🔎 搜索推荐</span>' +
      '<span class="vfind-sub">（想看什么 → 找出这个领域最值得关注的博主和网站）</span></div>' +
    '<div class="vfind-body cwf-panel" hidden>' +
      '<div class="cw-find-tip" style="margin-top:0">输入你想看的领域，AI 池联网找出最值得关注的博主和网站（YouTube、B站、抖音、X、官方博客、新闻页都有）。' +
        "勾选后加进「嗅探 · 关注的博主」：以后他们有新视频 / 新文章，在嗅探页一扫就出来，再挑着提取。</div>" +
      '<div class="vfind-row">' +
        '<input type="text" class="text-input cwf-kw" placeholder="想看什么？比如：AI 芯片、跨境电商、新能源汽车" />' +
        '<select class="text-input cwf-n"><option value="5">前 5 个</option><option value="10" selected>前 10 个</option>' +
          '<option value="15">前 15 个</option><option value="20">前 20 个</option></select>' +
        '<button type="button" class="send-btn cwf-btn">搜索</button></div>' +
      '<div class="cw-find-stage cwf-stage" hidden></div><div class="cwf-live" hidden></div><div class="cw-find-list cwf-list"></div>' +
      '<div class="cw-find-acts cwf-acts" hidden><label class="cw-find-all"><input type="checkbox" class="cwf-all" /> 全选能用的</label>' +
        '<span style="flex:1"></span><button type="button" class="send-btn cwf-add">加入关注的博主</button></div>' +
    "</div>";
  card.insertBefore(wrap, tools);
  const head = wrap.querySelector(".vfind-head"), body = wrap.querySelector(".vfind-body"), caret = wrap.querySelector(".vfind-caret");
  const apply = (open) => { body.hidden = !open; caret.textContent = open ? "▾" : "▸"; };
  let open = false;
  try { open = localStorage.getItem("vFindOpen") === "1"; } catch (_) {}
  apply(open);
  head.addEventListener("click", () => {
    open = body.hidden;
    apply(open);
    try { localStorage.setItem("vFindOpen", open ? "1" : "0"); } catch (_) {}
    _cwFindPoll();
  });
  return body;
}

vFindBuild();
_cwfPanels().forEach(_cwfBind);
_cwFindPoll();


// ════════════════════ v81：列表里的博主 mini 头像 ════════════════════
// 视频页的笔记列表（最新提取、文件夹、博主里、还没分析的）作者前面一个小圆头像，名字小一号；
// 嗅探页「扫出来的新视频」「按时间看全部」里的博主名前面也一样。没有头像的用名字首字 + 固定配色。
var _cwAvSig = "";
function _cwMiniAv(cid, title) {
  const list = (typeof _cwLastList !== "undefined" && _cwLastList) || [];
  const c = list.find((x) => String(x.id) === String(cid)) || list.find((x) => title && x.title === title) || {};
  const nm = String(title || c.title || "?");
  const ch = Array.from(nm.replace(/^[\s@＠#]+/, ""))[0] || "?";
  const hue = typeof vnHue === "function" ? vnHue(nm) : 200;
  const img = c.avatar ? '<img src="' + BACKEND + "/creator_avatar?key=" + encodeURIComponent(c.avatar.key) +
    "&v=" + (c.avatar.v || 0) + '" alt="">' : "";
  return '<span class="cw-mini-av" style="--h:' + hue + '"><span>' + escapeHtml(ch.toUpperCase()) + "</span>" + img + "</span>";
}
document.addEventListener("error", (e) => {           // 头像图片打不开 → 显示首字
  const t = e.target;
  if (t && t.tagName === "IMG" && t.parentElement && t.parentElement.classList.contains("cw-mini-av")) t.remove();
}, true);


// ════════════════════ v83：手机发链接 ════════════════════
// 手机和电脑连同一个 Wi-Fi，手机浏览器扫码打开一个小网页，把文章 / 视频链接粘进去，
// 电脑就自动加进「开始提取」的队列（和在电脑上粘贴一样）。后端见 backend/phone_inbox.py。
var _phSeq = -1, _phTimer = null, _phModalTimer = null;

function _phLoadQr() {
  return new Promise((resolve) => {
    if (typeof qrcode === "function") return resolve(true);
    const sc = document.createElement("script");
    sc.src = "qrcode-gen.js";
    sc.onload = () => resolve(typeof qrcode === "function");
    sc.onerror = () => resolve(false);
    document.head.appendChild(sc);
  });
}

function _phQrSvg(text) {
  try {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    return qr.createSvgTag({ cellSize: 5, margin: 2, scalable: true });
  } catch (e) { return ""; }
}

async function _phFetch(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
  };
  const r = await fetch(BACKEND + path, opt);
  return r.json();
}

function _phToast(text) {
  let el = document.getElementById("phToast");
  if (!el) {
    el = document.createElement("div");
    el.id = "phToast";
    el.className = "ph-toast";
    el.addEventListener("click", () => { el.classList.remove("show"); openPhoneInbox(); });
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 6000);
}

// 开着「手机发链接」时，每 6 秒看一眼有没有手机发来的新链接，有就在右下角提示一下
async function _phPoll() {
  clearTimeout(_phTimer);
  let next = 6000;
  try {
    const st = await _phFetch("/phone_inbox/status");
    if (!st.running && !_phFeishuOn) next = 30000;
    if (_phSeq >= 0 && st.seq > _phSeq && st.recent && st.recent.length) {
      const x = st.recent[0];
      _phToast((x.src === "飞书" ? "💬 飞书发来：" : "📱 手机发来：") + (x.title || x.url).slice(0, 40) + (x.ok ? "（已加进队列）" : "（没加进去，点开看原因）"));
      // v85：手机 / 飞书发来的任务，和在电脑上点「开始提取」一样：开始盯进度条，做完自动刷新「最新提取」
      if (x.ok) {
        try { if (typeof pollVideoProgress === "function") pollVideoProgress(); } catch (e) {}
        try { if (typeof setVideoStatus === "function")
          setVideoStatus((x.src === "飞书" ? "💬 飞书" : "📱 手机") + "发来一个链接，已开始处理…", "ok"); } catch (e) {}
      }
    }
    _phSeq = st.seq;
    const m = document.getElementById("phModal");
    if (m) _phRender(st);
  } catch (e) { next = 15000; }
  _phTimer = setTimeout(_phPoll, next);
}

function _phRender(st) {
  const box = document.getElementById("phModalBody");
  if (!box) return;
  const sig = JSON.stringify([st.running, st.error, st.code, st.urls, st.seq]);
  if (box._sig === sig) return;
  box._sig = sig;
  const tog = document.getElementById("phToggle");
  if (tog) tog.checked = !!st.enabled;
  let html = "";
  if (!st.enabled) {
    html += '<p>打开后，手机和电脑连<b>同一个 Wi-Fi</b>，用手机扫码打开一个小网页，把看到的好文章（公众号、知乎、头条、小红书…）' +
      '或视频的链接粘进去点「发给电脑」，电脑就自动提取保存，和在这里粘贴一样。</p>' +
      '<p class="ph-dim">只有同一个局域网里、知道 6 位连接码的手机才能发；软件别的功能不会对手机开放。</p>';
  } else if (!st.running) {
    html += '<p class="ph-bad">没打开成功：' + escapeHtml(st.error || "原因不明") + '</p>';
  } else if (!st.urls || !st.urls.length) {
    html += '<p class="ph-bad">已打开，但没找到这台电脑的局域网地址——电脑连上 Wi-Fi 或网线后再打开这个面板。</p>';
  } else {
    html += '<div class="ph-qr-wrap"><div class="ph-qr" id="phQr"></div><div class="ph-qr-side">' +
      '<div class="ph-step">① 手机连上和电脑<b>同一个 Wi-Fi</b></div>' +
      '<div class="ph-step">② 用手机相机或微信「扫一扫」扫左边的码</div>' +
      '<div class="ph-step">③ 把链接粘进去，点「发给电脑」</div>' +
      '<div class="ph-addr">或者在手机浏览器里输入：<br><b>' + escapeHtml(st.urls[0].replace(/\?k=.*$/, "")) + '</b><br>' +
      '连接码：<b class="ph-code">' + escapeHtml(st.code) + '</b> <button class="ph-link" id="phNewCode">换一个</button></div>' +
      '</div></div>';
    if (st.urls.length > 1) {
      html += '<p class="ph-dim">扫不开的话试试这台电脑的其它地址：' +
        st.urls.slice(1).map((u) => escapeHtml(u.replace(/\?k=.*$/, ""))).join("、") + '</p>';
    }
    html += '<p class="ph-tip">💡 手机上打不开？多半是 Windows 防火墙拦住了：第一次打开时如果弹出「Windows 安全中心警报」，' +
      '要勾上「专用网络」点「允许访问」。用微信扫码后，建议点右上角「…」→「在浏览器打开」，再「添加到主屏幕」，以后点图标就能发。</p>';
  }
  const rec = st.recent || [];
  html += '<div class="ph-rec-title">最近手机发来的（在家 + 飞书）</div>';
  html += rec.length ? rec.slice(0, 8).map((x) =>
    '<div class="ph-rec"><span class="ph-dim">' + escapeHtml(x.t) + (x.src === "飞书" ? " · 飞书" : "") + '</span> ' +
    '<span class="' + (x.ok ? "ph-ok" : "ph-bad") + '">' + (x.ok ? "✓" : "✗") + '</span> ' +
    escapeHtml(x.title || x.url) + (x.ok ? "" : '<div class="ph-bad ph-small">' + escapeHtml(x.msg) + '</div>') + '</div>'
  ).join("") : '<div class="ph-dim ph-small">还没有</div>';
  box.innerHTML = html;
  const nc = document.getElementById("phNewCode");
  if (nc) nc.onclick = async () => {
    if (!confirm("换一个新的连接码？换了以后，手机上要重新扫码。")) return;
    _phRender(await _phFetch("/phone_inbox/new_code", {}));
  };
  const qrBox = document.getElementById("phQr");
  if (qrBox && st.urls && st.urls[0]) {
    _phLoadQr().then((ok) => {
      const svg = ok ? _phQrSvg(st.urls[0]) : "";
      qrBox.innerHTML = svg || '<div class="ph-dim ph-small">二维码没生成出来，请在手机浏览器里输入右边的地址</div>';
    });
  }
}

// ── v84：面板分两页：「在家（同一个 Wi-Fi）」和「在外面（飞书机器人）」──
var _phTab = "home", _phFeishuOn = false;
try { _phTab = localStorage.getItem("phTab") || ""; } catch (e) {}

function _phSetTab(t) {
  _phTab = t;
  try { localStorage.setItem("phTab", t); } catch (e) {}
  document.querySelectorAll(".ph-tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === t));
  const h = document.getElementById("phModalBody"), f = document.getElementById("phFeishuBody");
  if (h) h.hidden = t !== "home";
  if (f) f.hidden = t !== "away";
  const sw = document.getElementById("phHomeSwitch");
  if (sw) sw.hidden = t !== "home";
}

const _FS_GUIDE = [
  ["注册 / 登录飞书", "手机或电脑装好飞书（免费），用手机号注册。电脑浏览器打开 <b>open.feishu.cn</b>，右上角登录。"],
  ["建一个机器人应用", "点「开发者后台」→「创建企业自建应用」，名字填「超能小助」（随便起），图标随便选 →「创建」。"],
  ["加上机器人能力", "进到应用里，左边「添加应用能力」→ 找到「机器人」点「添加」。"],
  ["开 3 个权限", "左边「权限管理」，在搜索框里依次搜下面 3 个，都点「开通权限」：<br>" +
    "<code>im:message.p2p_msg:readonly</code>（读取用户发给机器人的单聊消息）<br>" +
    "<code>im:message:send_as_bot</code>（以应用的身份发消息）<br>" +
    "<code>im:message:readonly</code>（获取单聊、群组消息——电脑没开时发的，开机后靠它补收）"],
  ["把钥匙填到这里", "左边「凭证与基础信息」，复制 <b>App ID</b> 和 <b>App Secret</b>，粘到下面两个框里，点「保存并连接」，等上面显示「✓ 已连上飞书」。<br><b>一定要先做这一步再做下一步</b>（飞书要看到连接才让保存）。"],
  ["订阅「接收消息」", "左边「事件与回调」→「事件配置」→ 订阅方式点编辑，选「<b>使用长连接接收事件</b>」→ 保存。然后点「添加事件」，搜「接收消息」（im.message.receive_v1），勾上 → 确认添加。"],
  ["发布", "左边「版本管理与发布」→「创建版本」，版本号填 1.0.0，可用范围选你自己（或所有员工）→ 保存 →「申请线上发布」。你自己是管理员的话会直接通过（如果要审核，到飞书「管理后台」里点通过）。"],
  ["手机上试一下", "手机飞书顶部搜索「超能小助」（你起的名字），点进机器人的聊天，发一个文章链接。机器人回「收到！」就成了，提取完它还会再告诉你。"],
];

function _fsStateText(st) {
  if (!st.enabled) return ['<span class="ph-dot"></span>没打开', ""];
  switch (st.state) {
    case "connected": return ['<span class="ph-dot ok"></span>已连上飞书', "ok"];
    case "installing": return ['<span class="ph-dot run"></span>第一次用，正在安装飞书组件（约 1 分钟）…', ""];
    case "connecting": return ['<span class="ph-dot run"></span>正在连接飞书…', ""];
    case "error": return ['<span class="ph-dot bad"></span>' + escapeHtml(st.error || "出错了"), "bad"];
    default: return ['<span class="ph-dot run"></span>准备中…', ""];
  }
}

function _fsRender(st) {
  const box = document.getElementById("phFeishuBody");
  if (!box) return;
  _phFeishuOn = !!st.enabled;
  const sig = JSON.stringify([st.enabled, st.state, st.error, st.configured, st.bound, st.catchup, st.app_id, st.secret_set]);
  if (box._sig === sig) return;
  const typing = box.contains(document.activeElement) && /INPUT/.test(document.activeElement.tagName);
  if (box._sig && typing) return;                    // 正在填框，别把输入冲掉
  box._sig = sig;
  const [stTxt, stCls] = _fsStateText(st);
  let html = '<p>在外面不和电脑同一个 Wi-Fi 时，在<b>手机飞书</b>里把链接发给你自己的机器人，电脑上的超能小助就会收到、自动提取，' +
    '机器人回你「收到了」，提取完再告诉你。电脑关着时发的，下次开机自动补上（7 天内）。</p>';
  html += '<div class="fs-status ' + stCls + '">' + stTxt + '</div>';
  if (st.enabled && st.state === "connected") {
    html += st.bound
      ? '<p class="ph-dim ph-small">✓ 已经和机器人聊过了，手机上直接发链接就行。</p>'
      : '<p class="fs-next">连上了！如果第 6、7 步还没做，现在做；做完在手机飞书里给机器人发一个链接试试。</p>';
  }
  if (st.catchup) html += '<p class="ph-dim ph-small">' + escapeHtml(st.catchup) + '</p>';
  html += '<div class="fs-form">' +
    '<label>App ID<input id="fsAppId" class="text-input" placeholder="cli_ 开头的一串" value="' + escapeHtml(st.app_id || "") + '"></label>' +
    '<label>App Secret<input id="fsSecret" class="text-input" type="password" placeholder="' +
      (st.secret_set ? "已保存（不改就留空）" : "一长串字母数字") + '"></label>' +
    '<div class="fs-btns"><button class="send-btn" id="fsSave">保存并连接</button>' +
    (st.enabled ? '<button class="send-btn fs-off" id="fsOff">断开</button>' : '') +
    '<span id="fsMsg" class="ph-small"></span></div></div>';
  html += '<details class="fs-guide"' + (st.configured && st.bound ? "" : " open") + '><summary>第一次用：怎么建飞书机器人（一步步来，约 10 分钟）</summary><ol>' +
    _FS_GUIDE.map((g) => '<li><b>' + g[0] + '</b><div>' + g[1] + '</div></li>').join("") + '</ol>' +
    '<p class="ph-dim ph-small">发链接的小技巧：链接后面加「分析」两个字 = 顺便让 AI 分析；加「不分析」= 只提取原文；不加就按电脑上上次的设置。一次可以发好几个链接。</p></details>';
  box.innerHTML = html;
  document.getElementById("fsSave").onclick = async () => {
    const id = document.getElementById("fsAppId").value.trim();
    const sec = document.getElementById("fsSecret").value.trim();
    const msg = document.getElementById("fsMsg");
    if (!id || (!sec && !st.secret_set)) { msg.textContent = "App ID 和 App Secret 都要填"; msg.className = "ph-small ph-bad"; return; }
    msg.textContent = "正在验证…"; msg.className = "ph-small ph-dim";
    try {
      const r = await _phFetch("/feishu_inbox/config", { app_id: id, app_secret: sec, enabled: true });
      if (r.ok === false) { msg.textContent = r.error || "没成功"; msg.className = "ph-small ph-bad"; return; }
      box._sig = ""; _fsRender(r); _phPoll();
    } catch (e) { msg.textContent = "后端没连上"; msg.className = "ph-small ph-bad"; }
  };
  const off = document.getElementById("fsOff");
  if (off) off.onclick = async () => { box._sig = ""; _fsRender(await _phFetch("/feishu_inbox/config", { enabled: false })); };
}

async function openPhoneInbox() {
  if (document.getElementById("phModal")) return;
  const mask = document.createElement("div");
  mask.className = "cx-modal-mask";
  mask.id = "phModal";
  mask.innerHTML =
    '<div class="cx-modal ph-modal">' +
    '  <div class="cx-modal-head ph-head">📱 手机发链接给电脑' +
    '    <label class="ph-switch" id="phHomeSwitch"><input type="checkbox" id="phToggle"> 打开</label></div>' +
    '  <div class="ph-tabs"><button class="ph-tab" data-tab="home">🏠 在家（同一个 Wi-Fi）</button>' +
    '<button class="ph-tab" data-tab="away">🚶 在外面（飞书机器人）</button></div>' +
    '  <div class="cx-modal-body" id="phModalBody"><p class="ph-dim">正在读取…</p></div>' +
    '  <div class="cx-modal-body" id="phFeishuBody" hidden><p class="ph-dim">正在读取…</p></div>' +
    '  <div class="cx-modal-foot"><button class="send-btn" id="phClose">关闭</button></div>' +
    '</div>';
  document.body.appendChild(mask);
  const close = () => { mask.remove(); clearInterval(_phModalTimer); };
  mask.addEventListener("click", (e) => { if (e.target === mask) close(); });
  document.getElementById("phClose").onclick = close;
  mask.querySelectorAll(".ph-tab").forEach((b) => { b.onclick = () => _phSetTab(b.dataset.tab); });
  document.getElementById("phToggle").onchange = async (e) => {
    const on = e.target.checked;
    e.target.disabled = true;
    try {
      const st = await _phFetch("/phone_inbox/enable", { on });
      _phSeq = st.seq;
      _phRender(st);
      _phPoll();
    } catch (err) {
      document.getElementById("phModalBody").innerHTML = '<p class="ph-bad">后端没连上：' + escapeHtml(String(err)) + '</p>';
    }
    e.target.disabled = false;
  };
  let fs = null;
  try { fs = await _phFetch("/feishu_inbox/status"); _fsRender(fs); } catch (e) {
    document.getElementById("phFeishuBody").innerHTML = '<p class="ph-bad">后端没连上，等软件显示「已就绪」后再打开。</p>';
  }
  if (_phTab !== "home" && _phTab !== "away") _phTab = fs && fs.configured ? "away" : "home";
  _phSetTab(_phTab);
  try { _phRender(await _phFetch("/phone_inbox/status")); }
  catch (e) { document.getElementById("phModalBody").innerHTML = '<p class="ph-bad">后端没连上，等软件显示「已就绪」后再打开。</p>'; }
  clearInterval(_phModalTimer);
  _phModalTimer = setInterval(async () => {
    if (!document.getElementById("phModal")) return clearInterval(_phModalTimer);
    try { _phRender(await _phFetch("/phone_inbox/status")); } catch (e) {}
    try { _fsRender(await _phFetch("/feishu_inbox/status")); } catch (e) {}
  }, 3000);
}

// 「开始提取」卡片标题栏右边加一个「📱 手机发链接」按钮（不改 index.html）
function _phInjectButton() {
  if (document.getElementById("phOpenBtn")) return true;
  const head = document.querySelector("#view-video .vi-phone-row") || document.querySelector("#view-video .v-card-extract > .v-card-head");   // v118：单独一行
  if (!head) return false;
  const b = document.createElement("button");
  b.type = "button";
  b.id = "phOpenBtn";
  b.className = "ph-open-btn";
  b.title = "手机上看到好文章 / 视频，把链接发给电脑自动提取（手机和电脑连同一个 Wi-Fi）";
  b.textContent = "📱 手机发链接";
  b.addEventListener("click", (e) => { e.stopPropagation(); openPhoneInbox(); });
  head.appendChild(b);
  return true;
}
// v86：把电脑上当前选的质量（精准 / 均衡 / 快速）和 AI 模型告诉后端，手机 / 飞书发来的链接照同样的设置提取
function _phSyncDefaults() {
  try {
    const lv = document.getElementById("videoLevel");
    const body = {};
    if (lv && lv.value) body.level = lv.value;
    try {
      const s = typeof settings === "function" ? settings() : null;
      if (s) { body.use_local = s.use_local; body.model = s.model; }
    } catch (e) {}
    if (!Object.keys(body).length) return;
    fetch(BACKEND + "/phone_inbox/defaults", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }).catch(() => {});
  } catch (e) {}
}
// v87：质量下拉框加「超精准（大模型）」：large-v3，方言 / 快语速认得更准；第一次用要下载约 3GB 模型
(function _addUltraLevel() {
  const sel = document.getElementById("videoLevel");
  if (!sel || sel.querySelector('option[value="ultra"]')) return;
  const o = document.createElement("option");
  o.value = "ultra";
  o.textContent = "超精准（大模型）";
  o.title = "用 large-v3 大模型，方言、语速快的也认得准；需要显卡，第一次用要下载约 3GB 模型";
  sel.appendChild(o);
  try {
    const saved = localStorage.getItem("videoLevelPick");
    if (saved && sel.querySelector('option[value="' + saved + '"]')) sel.value = saved;
  } catch (e) {}
  sel.addEventListener("change", () => { try { localStorage.setItem("videoLevelPick", sel.value); } catch (e) {} });
})();
(function _phBoot() {
  setTimeout(_phSyncDefaults, 5000);
  const lv = document.getElementById("videoLevel");
  if (lv) lv.addEventListener("change", () => setTimeout(_phSyncDefaults, 300));
  let tries = 0;
  const t = setInterval(() => { if (_phInjectButton() || ++tries > 40) clearInterval(t); }, 500);
  setTimeout(async () => {
    try { _phFeishuOn = !!(await _phFetch("/feishu_inbox/status")).enabled; } catch (e) {}
    _phPoll();
  }, 4000);
})();


// ════════════════════ v88：整理原文（AI 加标点、按意思分段）════════════════════
// ① 「开始提取」卡片里一个开关：提取完自动整理（默认开，存在后端，手机 / 飞书发来的也照这个办）
// ② 打开一条笔记，「完整原文」上方一个按钮：给以前提取的笔记补整理
function _vtTidyBar(resultEl, data) {
  const box = resultEl.querySelector("#vTranscript");
  if (!box || box.querySelector(".vt-tidy-bar")) return;
  const bar = document.createElement("div");
  bar.className = "vt-tidy-bar";
  bar.innerHTML = '<button class="vbtn" type="button">✨ 整理原文</button>' +
    '<span class="vt-tidy-msg">让 AI 加标点、按意思分段（只加标点和换行，不删改内容）</span>';
  box.insertBefore(bar, box.firstChild);
  const btn = bar.querySelector("button"), msg = bar.querySelector(".vt-tidy-msg");
  const render = (t) => {
    Array.from(box.children).forEach((c) => { if (c !== bar) c.remove(); });
    const div = document.createElement("div");
    div.innerHTML = renderMarkdown(paragraphizeCN(t || "（无文字稿）"));
    box.appendChild(div);
  };
  let timer = null;
  const poll = async () => {
    try {
      const r = await fetch(BACKEND + "/video_note_tidy_status?name=" + encodeURIComponent(data._noteName));
      const st = await r.json();
      msg.textContent = st.msg || "";
      if (st.running) { timer = setTimeout(poll, 2000); return; }
      btn.disabled = false; btn.textContent = "✨ 整理原文";
      msg.className = "vt-tidy-msg " + (st.ok ? "ok" : "");
      if (st.ok && st.transcript) { data.transcript = st.transcript; render(st.transcript); }
    } catch (e) { btn.disabled = false; btn.textContent = "✨ 整理原文"; msg.textContent = "后端没连上"; }
  };
  btn.addEventListener("click", async () => {
    btn.disabled = true; btn.textContent = "整理中…"; msg.className = "vt-tidy-msg"; msg.textContent = "准备整理…";
    try {
      const r = await fetch(BACKEND + "/video_note_tidy", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: data._noteName }) });
      const d = await r.json();
      if (!d.ok) { btn.disabled = false; btn.textContent = "✨ 整理原文"; msg.textContent = d.error || "没成功"; return; }
      clearTimeout(timer); timer = setTimeout(poll, 1500);
    } catch (e) { btn.disabled = false; btn.textContent = "✨ 整理原文"; msg.textContent = "后端没连上"; }
  });
}

(function _vtTidyAutoToggle() {
  const anchor = document.querySelector("#view-video .video-creator-row");
  if (!anchor || document.getElementById("videoTidyAuto")) return;
  const row = document.createElement("label");
  row.className = "vt-tidy-auto";
  row.title = "语音识别出来的文字没标点、不分段；开着这个，提取完会让 AI 加标点、按意思分段（只加标点和换行，不删改内容）。手机 / 飞书发来的也一样";
  row.innerHTML = '<input type="checkbox" id="videoTidyAuto" checked> ✨ 提取完自动整理原文（AI 加标点、按意思分段）';
  anchor.parentNode.insertBefore(row, anchor.nextSibling);
  const cb = row.querySelector("input");
  setTimeout(async () => {
    try { const r = await fetch(BACKEND + "/transcript_tidy/config"); cb.checked = !!(await r.json()).auto; } catch (e) {}
  }, 3000);
  cb.addEventListener("change", () => {
    fetch(BACKEND + "/transcript_tidy/config", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto: cb.checked }) }).catch(() => {});
  });
})();


// ════════════════════ v89：长按头像拖动 → 合并博主（大小号）════════════════════
// 按住一个圆形头像约 0.4 秒，头像会「浮起来」跟着鼠标走：
//   · 拖到另一个圆形头像上松开 → 两个合成一个博主（选用哪个名字），笔记都放到一起；
//     以后小号的新视频也自动归进来；合并后在博主资料卡上随时可以撤销（v64 那套）；
//   · 拖到圆角方形的文件夹上松开 → 把他的笔记都放进这个文件夹（作者名不变）；
//   · 拖到空白处松开 / 按 Esc → 取消。
var _vnDragEndAt = 0;
window.addEventListener("click", (e) => {            // 拖完松手那一下不要当成「点开头像」
  if (Date.now() - _vnDragEndAt < 450) { e.stopPropagation(); e.preventDefault(); }
}, true);

function vnTileDrag(t, g) {
  if (!g || g.kind !== "author" || g.name === "未填作者") return;   // 文件夹、未填作者只能当「放上去的目标」
  t.addEventListener("dragstart", (e) => e.preventDefault());       // 别让浏览器拖头像图片
  t.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || e.target.closest(".vn-clink, button, a, input")) return;
    const sx = e.clientX, sy = e.clientY;
    let lx = sx, ly = sy;
    t.classList.add("vn-press");
    const off = () => {
      clearTimeout(timer);
      t.classList.remove("vn-press");
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", off);
      window.removeEventListener("pointercancel", off);
    };
    const mv = (ev) => {
      lx = ev.clientX; ly = ev.clientY;
      if (Math.hypot(lx - sx, ly - sy) > 8) off();                    // 按住时挪动了 → 不算长按
    };
    const timer = setTimeout(() => { off(); vnDragStart(t, g, lx, ly); }, 400);
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", off);
    window.addEventListener("pointercancel", off);
  });
}

function vnScrollParent(el) {
  for (let p = el && el.parentElement; p; p = p.parentElement) {
    const oy = getComputedStyle(p).overflowY;
    if ((oy === "auto" || oy === "scroll") && p.scrollHeight > p.clientHeight + 4) return p;
  }
  return document.scrollingElement || document.documentElement;
}

function vnDragStart(t, g, x, y) {
  const r = t.getBoundingClientRect();
  const ghost = t.cloneNode(true);
  ghost.classList.add("vn-drag-ghost");
  ghost.classList.remove("vn-press");
  ghost.style.width = r.width + "px";
  // 浮起的头像放在鼠标左上方，别挡住下面要放上去的那个头像（它会高亮）
  const place = (px, py) => { ghost.style.left = (px - r.width * 0.95) + "px"; ghost.style.top = (py - r.height * 0.95) + "px"; };
  place(x, y);
  document.body.appendChild(ghost);
  const hint = document.createElement("div");
  hint.className = "vn-drag-hint";
  const idle = "拖到另一个头像上松开 = 合并成一个博主；拖到文件夹上 = 放进文件夹；空白处松开或按 Esc 取消";
  hint.textContent = idle;
  document.body.appendChild(hint);
  t.classList.add("vn-drag-src");
  document.body.classList.add("vn-dragging");
  const sc = vnScrollParent(t);
  let over = null, vy = 0, lastY = y;
  const scrollTimer = setInterval(() => { if (vy) sc.scrollTop += vy; }, 16);   // 拖到上下边缘自动滚
  const pick = (px, py) => {
    const el = document.elementFromPoint(px, py);
    let tgt = el && el.closest(".vn-ctile");
    if (tgt && (tgt === t || !tgt._g || tgt._g.name === "未填作者" || tgt._g.name === g.name)) tgt = null;
    if (over && over !== tgt) over.classList.remove("vn-drop-over");
    over = tgt;
    if (over) {
      over.classList.add("vn-drop-over");
      hint.textContent = over._g.kind === "folder"
        ? "松开：把「" + g.name + "」的 " + g.items.length + " 条笔记放进文件夹「" + over._g.name + "」"
        : "松开：把「" + g.name + "」和「" + over._g.name + "」合并成一个博主";
    } else hint.textContent = idle;
  };
  const mv = (e) => {
    place(e.clientX, e.clientY);
    lastY = e.clientY;
    const b = sc === document.scrollingElement || sc === document.documentElement
      ? { top: 0, bottom: window.innerHeight } : sc.getBoundingClientRect();
    vy = lastY < b.top + 60 ? -14 : lastY > b.bottom - 60 ? 14 : 0;
    pick(e.clientX, e.clientY);
  };
  const finish = (ok) => {
    clearInterval(scrollTimer);
    window.removeEventListener("pointermove", mv);
    window.removeEventListener("pointerup", up);
    window.removeEventListener("pointercancel", cancel);
    window.removeEventListener("keydown", esc, true);
    ghost.remove(); hint.remove();
    t.classList.remove("vn-drag-src");
    document.body.classList.remove("vn-dragging");
    _vnDragEndAt = Date.now();
    const dst = over && over._g;
    if (over) over.classList.remove("vn-drop-over");
    if (ok && dst) vnDropOn(g, dst);
  };
  const up = () => finish(true);
  const cancel = () => finish(false);
  const esc = (e) => { if (e.key === "Escape") { e.preventDefault(); finish(false); over = null; } };
  window.addEventListener("pointermove", mv);
  window.addEventListener("pointerup", up);
  window.addEventListener("pointercancel", cancel);
  window.addEventListener("keydown", esc, true);
}

// 合并成哪个名字：默认用「放上去的那个」（一般是大号）的名字
function vnAskMergeName(a, b) {
  return new Promise((resolve) => {
    const old = document.getElementById("vnMergeAsk");
    if (old) old.remove();
    const wrap = document.createElement("div");
    wrap.id = "vnMergeAsk"; wrap.className = "vn-merge-mask";
    const box = document.createElement("div");
    box.className = "vn-merge-box";
    box.innerHTML = '<div class="vn-merge-title">合并博主</div><div class="vn-merge-desc"></div>' +
      '<div class="vn-merge-lab">合并后用哪个名字？</div>' +
      '<div class="vn-merge-picks"><button type="button" class="send-btn" data-k="b"></button>' +
      '<button type="button" class="send-btn vn-merge-alt" data-k="a"></button></div>' +
      '<div class="vn-merge-row"><span class="vn-merge-note"></span><button type="button" class="vn-merge-cancel">取消</button></div>';
    box.querySelector(".vn-merge-desc").textContent = "把「" + a.name + "」（" + a.items.length + " 条笔记）和「" + b.name +
      "」（" + b.items.length + " 条笔记）合成一个博主：笔记都放到一起看，以后这两个号的新视频也会自动归到一起。" +
      "合并后在博主资料卡上随时可以撤销。";
    box.querySelector('[data-k="b"]').textContent = "用「" + b.name + "」";
    box.querySelector('[data-k="a"]').textContent = "用「" + a.name + "」";
    const done = (v) => { try { wrap.remove(); } catch (_) {} document.removeEventListener("keydown", key, true); resolve(v); };
    const key = (e) => { if (e.key === "Escape") { e.preventDefault(); done(null); } };
    box.querySelector('[data-k="b"]').addEventListener("click", () => done({ src: a.name, dst: b.name }));
    box.querySelector('[data-k="a"]').addEventListener("click", () => done({ src: b.name, dst: a.name }));
    box.querySelector(".vn-merge-cancel").addEventListener("click", () => done(null));
    wrap.addEventListener("click", (e) => { if (e.target === wrap) done(null); });
    document.addEventListener("keydown", key, true);
    wrap.appendChild(box);
    document.body.appendChild(wrap);
  });
}

async function vnDropOn(src, dst) {
  if (dst.kind === "folder") {
    const notes = (src.items || []).map((n) => n.name).filter(Boolean);
    if (!notes.length) return;
    if (!confirm("把「" + src.name + "」的 " + notes.length + " 条笔记放进文件夹「" + dst.name + "」？\n\n" +
        "只是放进文件夹，作者名不变；以后在「列表」里可以再移出来。")) return;
    setVideoStatus("正在把「" + src.name + "」的笔记放进「" + dst.name + "」…");
    let ok = 0;
    for (const nm of notes) {
      const d = await vnFolderOp({ op: "move", note: nm, name: dst.name });
      if (d && d.ok) ok++;
    }
    setVideoStatus("✓ 已把 " + ok + " 条笔记放进文件夹「" + dst.name + "」", ok === notes.length ? "" : "warn");
    loadVideoNotes();
    return;
  }
  const r = await vnAskMergeName(src, dst);
  if (!r) return;
  setVideoStatus("正在合并「" + r.src + "」→「" + r.dst + "」…");
  try {
    const d = await (await fetch(BACKEND + "/creator_merge", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ src: r.src, dst: r.dst }) })).json();
    if (!d.ok) { setVideoStatus("没合并成：" + (d.message || "未知原因"), "warn"); return; }
    _vnTidyMsgs = _vnTidyMsgs.concat([(d.message || "合并好了") + "（点进「" + r.dst + "」，资料卡上可以撤销）"]).slice(-6);
    setVideoStatus("✓ " + (d.message || "合并好了"));
    await vnLoadProfiles();
    loadVideoNotes();
  } catch (e) {
    setVideoStatus("合并出错：" + e.message, "warn");
  }
}


// ════════════════════ v90：删除笔记的小按钮（「还没分析的笔记」清单里用）════════════════════
function vnDelNoteBtn(n, onGone) {
  const del = document.createElement("button");
  del.type = "button"; del.className = "vn-un-del"; del.textContent = "🗑";
  del.title = "删除这条笔记（测试用的、重复的可以删掉）";
  del.addEventListener("click", async (e) => {
    e.stopPropagation();
    const t = n.title || (n.name || "").replace(/\.md$/, "");
    if (!confirm("删除这条笔记？\n\n《" + t + "》\n\n删掉就找不回来了。")) return;
    del.disabled = true;
    try {
      const d = await (await fetch(BACKEND + "/video_note_delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: n.name }) })).json();
      if (d && d.ok === false) { del.disabled = false; setVideoStatus("没删成：" + (d.error || "未知原因"), "warn"); return; }
      if (onGone) onGone();
      setVideoStatus("🗑 已删除《" + t.slice(0, 30) + "》", "ok");
      setTimeout(loadVideoNotes, 300);
    } catch (err) { del.disabled = false; setVideoStatus("删除出错：" + err.message, "warn"); }
  });
  return del;
}

// ════════════════════ v90：提取失败清单 ════════════════════
// 自动重试也没用的、卡住被自动取消的、软件重启时发现总是崩的，都记在这里（存在后端，关软件也不丢）。
// 每条显示原因，可以「重新提取」（用视频页当前选的识别质量）或删掉；提取成功了会自动从清单里消失。
function vnFailIsOpen() {
  try { return localStorage.getItem("vnFailOpen") !== "0"; } catch (_) { return true; }
}
function vnCurLevel() {
  const el = document.getElementById("videoLevel");
  let v = el && el.value ? el.value : "";
  if (!v) { try { v = localStorage.getItem("videoLevelPick") || ""; } catch (_) {} }
  return v;
}

function vnRenderFailBar(list) {
  const bar = document.createElement("div");
  bar.className = "vn-batch-bar vn-batch-group vn-fail-group"; bar.id = "vnFailBar";
  bar.hidden = true;
  list.appendChild(bar);
  vnFailRefresh();
}

async function vnFailRefresh() {
  const bar = document.getElementById("vnFailBar");
  if (!bar) return;
  let items;
  try { items = (await (await fetch(BACKEND + "/video_failed")).json()).items || []; } catch (_) { return; }
  vnFailFill(bar, items);
}

function vnFailFill(bar, items) {
  bar.innerHTML = "";
  bar.hidden = !items.length;
  if (!items.length) return;
  const head = document.createElement("div");
  head.className = "video-note-item vn-group-head vn-batch-head";
  head.title = "点击展开 / 收起";
  const caret = document.createElement("span"); caret.className = "vn-caret";
  const nm = document.createElement("span"); nm.className = "vn-name"; nm.textContent = "提取失败（" + items.length + "）";
  const sum = document.createElement("span"); sum.className = "vn-batch-sum";
  sum.textContent = "没提取成功的都在这里，原因写在每一条后面";
  const acts = document.createElement("span"); acts.className = "vn-batch-hacts";
  const all = document.createElement("button");
  all.type = "button"; all.className = "send-btn vn-batch-btn"; all.textContent = "全部重新提取";
  all.title = "把清单里的都重新放进提取队列（用视频页现在选的识别质量）";
  all.addEventListener("click", (e) => { e.stopPropagation(); vnFailAct("retry", null, true, all); });
  const clr = document.createElement("button");
  clr.type = "button"; clr.className = "vn-fail-clear"; clr.textContent = "清空";
  clr.title = "清空这个清单（只是不再显示，不影响已存的笔记）";
  clr.addEventListener("click", (e) => { e.stopPropagation(); vnFailAct("delete", null, true, clr); });
  acts.appendChild(all); acts.appendChild(clr);
  head.appendChild(caret); head.appendChild(nm); head.appendChild(sum); head.appendChild(acts);
  const body = document.createElement("div"); body.className = "vn-un-rows vn-fail-rows";
  items.forEach((x, i) => body.appendChild(vnFailRow(x, i + 1)));
  bar.appendChild(head); bar.appendChild(body);
  const apply = (open) => { body.hidden = !open; caret.textContent = open ? "▾" : "▸"; bar.classList.toggle("open", open); };
  apply(vnFailIsOpen());
  head.addEventListener("click", () => {
    const open = body.hidden;
    apply(open);
    try { localStorage.setItem("vnFailOpen", open ? "1" : "0"); } catch (_) {}
  });
}

function vnFailRow(x, idx) {
  const r = document.createElement("div");
  r.className = "vn-un-row vn-fail-row";
  const no = document.createElement("span"); no.className = "vn-un-no"; no.textContent = idx + ".";
  const tm = document.createElement("span"); tm.className = "vn-un-time"; tm.textContent = (x.at || "").slice(5);
  const nm = document.createElement("span"); nm.className = "vn-un-name";
  nm.textContent = x.title || x.url || x.local_path || "（没有标题）";
  nm.title = (x.title ? x.title + "\n" : "") + (x.url || x.local_path || "");
  r.appendChild(no); r.appendChild(tm); r.appendChild(nm);
  if (x.url && /^https?:/.test(x.url)) {
    const a = document.createElement("a");
    a.className = "vn-fail-link"; a.href = x.url; a.target = "_blank"; a.textContent = "原链接↗";
    a.addEventListener("click", (e) => e.stopPropagation());
    r.appendChild(a);
  }
  const why = document.createElement("span"); why.className = "vn-fail-why";
  why.textContent = "✗ " + (x.error || "原因不明");
  why.title = "没成功的原因：\n" + (x.error || "原因不明") + (x.tries > 1 ? "\n\n已经没成功 " + x.tries + " 次" : "");
  r.appendChild(why);
  if (x.tries > 1) {
    const tr = document.createElement("span"); tr.className = "vn-fail-tries"; tr.textContent = x.tries + " 次";
    tr.title = "已经没成功 " + x.tries + " 次";
    r.appendChild(tr);
  }
  const re = document.createElement("button");
  re.type = "button"; re.className = "vn-analyze vn-fail-retry"; re.textContent = "↻ 重新提取";
  re.title = "重新放进提取队列（用视频页现在选的识别质量）";
  re.addEventListener("click", (e) => { e.stopPropagation(); vnFailAct("retry", [x.id], false, re); });
  const del = document.createElement("button");
  del.type = "button"; del.className = "vn-un-del"; del.textContent = "🗑"; del.title = "从清单里删掉这一条";
  del.addEventListener("click", (e) => { e.stopPropagation(); vnFailAct("delete", [x.id], false, del); });
  r.appendChild(re); r.appendChild(del);
  r.title = "没成功的原因：" + (x.error || "原因不明");
  return r;
}

async function vnFailAct(action, ids, all, btn) {
  if (action === "delete" && all && !confirm("清空「提取失败」清单？\n\n只是不再显示这些失败记录，不影响已存的笔记。")) return;
  if (btn) btn.disabled = true;
  try {
    const d = await (await fetch(BACKEND + "/video_failed", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ids: ids || [], all: !!all, level: vnCurLevel() }) })).json();
    if (!d.ok) setVideoStatus("没成功：" + (d.error || "未知原因"), "warn");
    else if (action === "retry") {
      setVideoStatus("✓ " + (d.message || "已重新放进提取队列") + "，上面能看到进度", "ok");
      try { pollVideoProgress(); } catch (_) {}
    }
  } catch (e) { setVideoStatus("出错：" + e.message, "warn"); }
  if (btn) btn.disabled = false;
  vnFailRefresh();
}


// ════════════════════ v91：笔记阅读页 ════════════════════
// 点笔记标题 → 整个视频页换成这篇笔记的阅读页；左上角「← 返回」（或按 Esc、鼠标侧键「后退」）
// 回到列表，而且回到刚才的位置——列表滚到哪儿还是哪儿，刚看的那条闪一下，不用再往下翻找。
let _vnReaderName = "";
let _vnReaderBack = null;      // {el: 滚动的那一层, top: 滚到哪儿}

function vnReaderIsOpen() {
  const rd = document.getElementById("vnReader");
  return !!(rd && !rd.hidden);
}

function vnReaderEnsure() {
  let rd = document.getElementById("vnReader");
  if (rd) return rd;
  const view = document.getElementById("view-video");
  rd = document.createElement("div");
  rd.id = "vnReader"; rd.className = "vn-reader"; rd.hidden = true;
  rd.innerHTML = '<div class="vn-reader-bar">' +
    '<button type="button" class="vn-reader-back" title="回到列表刚才的位置（也可以按 Esc）">← 返回</button>' +
    '<span class="vn-reader-title"></span></div>' +
    '<div class="vn-reader-body"><div class="dash-content video-result vn-reader-content"></div></div>';
  rd.querySelector(".vn-reader-back").addEventListener("click", vnReaderClose);
  (view || document.body).appendChild(rd);
  return rd;
}

function vnReaderSetTitle(t) {
  const el = document.querySelector("#vnReader .vn-reader-title");
  if (el) { el.textContent = t || ""; el.title = t || ""; }
}

// 打开阅读页，返回放笔记内容的那一格。已经开着（比如在阅读页里又点开了别的）就不重记返回位置
function vnReaderShow(name) {
  const rd = vnReaderEnsure();
  const pane = document.querySelector("#view-video .video-pane");
  if (!vnReaderIsOpen()) {
    const list = document.getElementById("videoNotesList") || pane;
    const sc = (typeof vnScrollParent === "function" && list) ? vnScrollParent(list) : pane;
    _vnReaderBack = { el: sc, top: sc ? sc.scrollTop : 0 };
    // 进度卡里如果正摆着一篇笔记（老版本打开的），先收起来，免得两篇的按钮 id 撞在一起
    const vr = document.getElementById("videoResult");
    if (vr && vr.querySelector("[id]")) { vr._vnStash = document.createDocumentFragment(); while (vr.firstChild) vr._vnStash.appendChild(vr.firstChild); }
    if (pane) pane.style.display = "none";
    rd.hidden = false;
  }
  _vnReaderName = name;
  vnReaderSetTitle((name || "").replace(/\.md$/, "").replace(/^\d{8}-\d{6}-/, ""));
  return rd.querySelector(".vn-reader-content");
}

function vnReaderClose() {
  const rd = document.getElementById("vnReader");
  if (!rd || rd.hidden) return;
  const name = _vnReaderName;
  rd.hidden = true;
  rd.querySelector(".vn-reader-content").innerHTML = "";    // 清掉，免得按钮 id 和别处重复
  _vnReaderName = "";
  const vr = document.getElementById("videoResult");
  if (vr && vr._vnStash) { if (!vr.firstChild) vr.appendChild(vr._vnStash); vr._vnStash = null; }
  const pane = document.querySelector("#view-video .video-pane");
  if (pane) pane.style.display = "";
  const back = _vnReaderBack;
  _vnReaderBack = null;
  const restore = () => {
    if (back && back.el) back.el.scrollTop = back.top;
    // 列表在这期间刷新过、那条挪了位置：按名字找到它，不在眼前就滚过去；闪一下
    const list = document.getElementById("videoNotesList");
    const row = list && name ? Array.from(list.querySelectorAll("[data-name]")).find((x) => x.dataset.name === name && x.offsetParent) : null;
    if (row) {
      const r = row.getBoundingClientRect();
      if (r.bottom < 60 || r.top > window.innerHeight - 40) row.scrollIntoView({ block: "center" });
      row.classList.remove("vn-flash", "vn-back-flash"); void row.offsetWidth;
      row.classList.add("vn-back-flash");
      setTimeout(() => row.classList.remove("vn-back-flash"), 2600);
    }
  };
  restore();
  requestAnimationFrame(restore);          // 等页面排好版再对一次位置
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !vnReaderIsOpen()) return;
  const t = e.target;
  if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
  if (document.querySelector(".vn-merge-mask, .modal.open, .ask-mask")) return;     // 有弹框时 Esc 先关弹框
  const v = document.getElementById("view-video");
  if (v && !v.classList.contains("active")) return;
  e.preventDefault();
  vnReaderClose();
});
window.addEventListener("mouseup", (e) => {          // 鼠标侧键「后退」
  if (e.button === 3 && vnReaderIsOpen()) { e.preventDefault(); vnReaderClose(); }
});


// ════════════════════ v92：列表刷新后停在原来的位置 ════════════════════
// 删除、改作者、移到文件夹、新笔记到了……都会整个重画笔记列表。以前重画时列表先被清空、页面变短，
// 一下子弹回顶部，要再往下翻。现在：刷新前记下眼前看得到的那几条，刷新后把第一条还在的放回原来的高度
// （删掉的那条没了，就由它下面那条接上）；重画期间先撑住列表高度，页面不会塌下去。
// 进出某个博主 / 文件夹、切换「列表 / 图标」时不管（那是换了一页）。
var _vnLoadNotesKeepPos = loadVideoNotes;
loadVideoNotes = async function () {
  const list = document.getElementById("videoNotesList");
  const pane = document.querySelector("#view-video .video-pane");
  if (!list || !pane || pane.style.display === "none" || !list.offsetParent || typeof vnScrollParent !== "function") {
    return _vnLoadNotesKeepPos.apply(this, arguments);
  }
  const sc = vnScrollParent(list);
  const top0 = sc.scrollTop;
  const pathOf = () => { try { return JSON.stringify(_vnIconPath || null) + "|" + vnViewMode(); } catch (_) { return ""; } };
  const path0 = pathOf();
  const box = sc === document.scrollingElement || sc === document.documentElement
    ? { top: 0, bottom: window.innerHeight } : sc.getBoundingClientRect();
  const keyOf = (el) => {
    const sec = el.closest("#vnRecent, #vnUnList, #vnFailBar, #vnIcons, #vnBatchBar");
    return el.dataset.name + "|" + (sec ? sec.id : "") + "|" + (el.className || "").split(" ")[0];
  };
  const anchors = [];
  for (const el of list.querySelectorAll("[data-name]")) {
    const r = el.getBoundingClientRect();
    if (!r.height || r.bottom <= box.top || r.top >= box.bottom) continue;
    anchors.push({ key: keyOf(el), y: r.top });
    if (anchors.length >= 30) break;
  }
  list.style.minHeight = list.offsetHeight + "px";          // 重画期间撑住高度，页面不塌
  try {
    return await _vnLoadNotesKeepPos.apply(this, arguments);
  } finally {
    list.style.minHeight = "";
    if (pathOf() === path0 && pane.style.display !== "none") {
      sc.scrollTop = top0;
      if (anchors.length) {
        const now = {};
        list.querySelectorAll("[data-name]").forEach((el) => { const k = keyOf(el); if (!(k in now) && el.offsetParent) now[k] = el; });
        for (const a of anchors) {
          const el = now[a.key];
          if (el) { sc.scrollTop += el.getBoundingClientRect().top - a.y; break; }
        }
      }
    }
  }
};


// ════════════════════ v93：删除时的「撤除」动画（全软件通用）════════════════════
// 点了删除（🗑 / ✕ / 删除 / 忽略…），等删除请求真正发出去时，那一行先往右滑、闪一下淡红、
// 慢慢变透明，高度收起来、下面的顶上来（头像这种格子是缩小淡出），然后列表才刷新——
// 一眼就知道「这条删掉了」。删除没成功（后端说不行 / 出错）就弹回原样。
// 做法：记住刚点的是哪个删除按钮 → 包一层 fetch，看到删除类的请求就先播动画，播完再把结果交回去。
// 这样不用一个个改各处的删除代码，以后新加的删除按钮也自动有这个效果。
var _cxDelPending = null;
const _CX_DEL_WORD = /删除|移除|删掉|忽略|🗑|✕|×/;
const _CX_DEL_SKIP = /清空|全部|取消|撤销/;
const _CX_ROW_SEL = ".video-note-item, .vn-un-row, .vn-fail-row, .cw-video, .cw-tile, .cw-creator, .vn-ctile, .vn-tile, " +
  ".dg-item, .sniff-item, .sniff-src, .sn-src, [data-name], [data-id], li, tr";

function _cxDelRows(btn) {
  const label = (btn.getAttribute("title") || "") + " " + (btn.textContent || "");
  if (/选中/.test(label)) {               // 「删除选中 / 忽略选中」：勾了哪些就动哪些
    const card = btn.closest(".v-card, .sn-card, .cw-rightcard, section") || document;
    return Array.from(card.querySelectorAll("input[type=checkbox]:checked"))
      .filter((cb) => !cb.closest(".sniff-switch, label.sniff-switch, .sn-toolbar"))
      .map((cb) => cb.closest(_CX_ROW_SEL)).filter((r, i, a) => r && a.indexOf(r) === i && !r.contains(btn));
  }
  const row = btn.closest(_CX_ROW_SEL);
  return row && row !== document.body ? [row] : [];
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest && e.target.closest("button, [role=button], .vn-del, .cw-del");
  if (!btn) return;
  const label = (btn.getAttribute("title") || "") + " " + (btn.textContent || "").trim();
  if (!_CX_DEL_WORD.test(label) || _CX_DEL_SKIP.test(label)) return;
  const rows = _cxDelRows(btn);
  _cxDelPending = rows.length ? { rows, t: Date.now() } : null;
}, true);

function cxAnimateOut(el) {
  if (!el || !el.isConnected || !el.animate) return { done: Promise.resolve(), undo() {} };
  const cs = getComputedStyle(el);
  const pd = el.parentElement ? getComputedStyle(el.parentElement) : null;
  const tile = pd && (/grid/.test(pd.display) || pd.flexWrap === "wrap");
  const h = el.offsetHeight;
  el.style.pointerEvents = "none";
  const prevOverflow = el.style.overflow;
  if (!tile) el.style.overflow = "hidden";
  const frames = tile
    ? [{ opacity: 1, transform: "scale(1)" },
       { opacity: .55, transform: "scale(1.06)", filter: "saturate(.4)", offset: .3 },
       { opacity: 0, transform: "scale(.3)" }]
    : [{ opacity: 1, transform: "translateX(0)", height: h + "px", marginTop: cs.marginTop, marginBottom: cs.marginBottom,
         paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, backgroundColor: cs.backgroundColor },
       { opacity: .6, transform: "translateX(26px)", height: h + "px", backgroundColor: "rgba(220,38,38,.14)", offset: .4 },
       { opacity: 0, transform: "translateX(90px)", height: "0px", marginTop: "0px", marginBottom: "0px",
         paddingTop: "0px", paddingBottom: "0px", borderTopWidth: "0px", borderBottomWidth: "0px", backgroundColor: "rgba(220,38,38,.08)" }];
  const a = el.animate(frames, { duration: tile ? 420 : 650, easing: "cubic-bezier(.45,0,.55,1)", fill: "forwards" });
  return {
    done: a.finished.catch(() => {}),
    undo() { try { a.cancel(); } catch (_) {} el.style.pointerEvents = ""; el.style.overflow = prevOverflow; },
  };
}

(function _cxWrapFetch() {
  if (window._cxFetchWrapped) return;
  window._cxFetchWrapped = true;
  const orig = window.fetch.bind(window);
  window.fetch = async function (url, opts) {
    const p = _cxDelPending;
    const method = ((opts && opts.method) || "GET").toUpperCase();
    const body = (opts && typeof opts.body === "string") ? opts.body : "";
    const isDel = p && Date.now() - p.t < 20000 && (method === "POST" || method === "DELETE") &&
      (/delete|dismiss|remove|_del\b|\/del\b/i.test(String(url)) || /"(action|op)"\s*:\s*"(delete|remove|dismiss)"/.test(body));
    if (!isDel) return orig(url, opts);
    _cxDelPending = null;
    const anims = p.rows.filter((r) => r.isConnected).map(cxAnimateOut);
    let resp;
    try {
      resp = await orig(url, opts);
    } catch (e) {
      anims.forEach((a) => a.undo());
      throw e;
    }
    try {
      const j = await resp.clone().json();
      if (j && j.ok === false) { anims.forEach((a) => a.undo()); return resp; }
    } catch (_) {}
    if (!resp.ok) { anims.forEach((a) => a.undo()); return resp; }
    await Promise.all(anims.map((a) => a.done));     // 动画播完，再让列表刷新
    return resp;
  };
})();


// ════════════════════ v94：推文笔记 =「🗣 博主原话」+「🔗 链接原文」════════════════════
// 打开一条推文笔记，「完整原文」上方一个按钮：重新抓完整推文、转发的原帖、引用的帖子、链接里的文章，
// 整理成两部分（AI 分析那部分不动）。旁边还能把所有推文笔记都整理一遍。
function _vtXBar(resultEl, data) {
  const box = resultEl.querySelector("#vTranscript");
  if (!box || box.querySelector(".vt-tidy-bar")) return;
  const bar = document.createElement("div");
  bar.className = "vt-tidy-bar";
  bar.innerHTML = '<button class="vbtn" type="button">🔄 重新抓取并整理</button>' +
    '<span class="vt-tidy-msg">推文分成「🗣 博主原话」和「🔗 链接原文」：转发的原帖、引用的帖子、链接里的文章都抓全文放进来</span>' +
    '<a href="#" class="vt-x-all" title="把所有推文笔记都按这个样子整理一遍（AI 分析不动）">全部推文笔记都整理一遍</a>';
  box.insertBefore(bar, box.firstChild);
  const btn = bar.querySelector("button"), msg = bar.querySelector(".vt-tidy-msg"), all = bar.querySelector(".vt-x-all");
  let timer = null, batch = false;
  const poll = async () => {
    try {
      const st = await (await fetch(BACKEND + "/x_note_rebuild_status?name=" + encodeURIComponent(data._noteName))).json();
      if (batch && st.running) {
        msg.textContent = "正在整理全部推文笔记：" + (st.done || 0) + " / " + (st.total || 0) + (st.msg ? "（" + st.msg + "）" : "");
      } else if (st.queued) {
        msg.textContent = st.msg || "正在抓…";
      }
      if (st.queued || (batch && st.running)) { timer = setTimeout(poll, 1500); return; }
      btn.disabled = false; btn.textContent = "🔄 重新抓取并整理";
      const mine = st.mine;
      msg.className = "vt-tidy-msg " + (mine && mine.ok ? "ok" : "");
      msg.textContent = batch ? ("全部整理完了：成功 " + (st.ok || 0) + " 条" + (st.fail ? "，没成功 " + st.fail + " 条" : ""))
        : (mine ? mine.msg : "整理完了");
      if (mine && mine.ok && typeof vnReaderIsOpen === "function" && vnReaderIsOpen() && _vnReaderName === data._noteName) {
        const keep = msg.textContent;
        await openVideoNote(data._noteName);           // 原地刷新这篇
        const b2 = document.querySelector("#vnReader .vt-tidy-bar .vt-tidy-msg");
        if (b2) { b2.textContent = keep; b2.className = "vt-tidy-msg ok"; }
        const t = document.querySelector('#vnReader .vtab[data-tab="transcript"]');
        if (t) t.click();
      }
    } catch (e) { btn.disabled = false; btn.textContent = "🔄 重新抓取并整理"; msg.textContent = "后端没连上"; }
  };
  const go = async (body) => {
    btn.disabled = true; btn.textContent = "抓取中…"; msg.className = "vt-tidy-msg"; msg.textContent = "准备抓取…";
    try {
      const d = await (await fetch(BACKEND + "/x_note_rebuild", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();
      if (!d.ok) { btn.disabled = false; btn.textContent = "🔄 重新抓取并整理"; msg.textContent = d.error || "没成功"; return; }
      if (body.all) msg.textContent = "一共 " + d.total + " 条推文笔记，开始整理…";
      clearTimeout(timer); timer = setTimeout(poll, 1200);
    } catch (e) { btn.disabled = false; btn.textContent = "🔄 重新抓取并整理"; msg.textContent = "后端没连上"; }
  };
  btn.addEventListener("click", () => { batch = false; go({ name: data._noteName }); });
  all.addEventListener("click", (e) => {
    e.preventDefault();
    if (!confirm("把所有推文笔记都整理成「博主原话 + 链接原文」？\n\n要联网抓原帖和链接文章，条数多会花几分钟（后台慢慢做，可以先干别的）。AI 分析那部分不动。")) return;
    batch = true; go({ all: true });
  });
}


// ════════════════════ v95：视频语言 + 字幕模式 + 翻译成中文 + 导出字幕 ════════════════════
const VT_LANGS = [["zh", "中文（普通话）"], ["ja", "日语"], ["en", "英语"], ["ko", "韩语"], ["yue", "粤语"], ["auto", "自动识别语言"]];
function vnCurLang() {
  const el = document.getElementById("videoLang");
  let v = el && el.value ? el.value : "";
  if (!v) { try { v = localStorage.getItem("videoLangPick") || ""; } catch (_) {} }
  return v || "zh";
}

// ① 「开始提取」里，质量下拉框旁边加一个「语言」下拉框（记住上次选的）
(function _vtLangPicker() {
  const lv = document.getElementById("videoLevel");
  if (!lv || document.getElementById("videoLang")) return;
  const sel = document.createElement("select");
  sel.id = "videoLang"; sel.className = lv.className || "text-input";
  sel.title = "视频里说的是什么话。选对了识别才准：日语视频选「日语」，识别出日语原文，" +
    "之后在笔记的「完整原文」里可以一键翻译成中文、看双语字幕、导出字幕文件。导入本地文件也照这个来。";
  VT_LANGS.forEach(([v, t]) => { const o = document.createElement("option"); o.value = v; o.textContent = t; sel.appendChild(o); });
  try { const sv = localStorage.getItem("videoLangPick"); if (sv) sel.value = sv; } catch (_) {}
  sel.addEventListener("change", () => { try { localStorage.setItem("videoLangPick", sel.value); } catch (_) {} });
  sel.style.cssText = "width:auto;min-width:118px;flex:0 0 auto";
  lv.parentNode.insertBefore(sel, lv.nextSibling);
})();

// ② 所有提交视频任务的请求（粘链接、导入本地文件、导入文件夹…）都带上选的语言
(function _vtLangInject() {
  const f0 = window.fetch;
  window.fetch = function (url, opts) {
    try {
      if (/\/video_transcribe(\?|$)/.test(String(url)) && opts && typeof opts.body === "string" && opts.body.charAt(0) === "{") {
        const b = JSON.parse(opts.body);
        let changed = false;
        if (!b.lang) { b.lang = vnCurLang(); changed = true; }
        if (b.vocal === undefined) { b.vocal = vnCurVocal(); changed = true; }      // v102：先分离人声
        if (changed) opts = Object.assign({}, opts, { body: JSON.stringify(b) });
      }
    } catch (_) {}
    return f0.call(this, url, opts);
  };
})();

function _vtFmtT(t) {
  t = Math.max(0, Math.floor(t || 0));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : String(m).padStart(2, "0")) + ":" + String(s).padStart(2, "0");
}

// ③ 笔记「完整原文」上方：📄 原文 / 🎬 字幕 / 🀄 中文 三种看法 + 翻译 + 导出字幕
async function _vtSubBar(resultEl, data) {
  const box = resultEl.querySelector("#vTranscript");
  if (!box || !data._noteName || box.querySelector(".vt-sub-bar")) return;
  let d;
  try { d = await (await fetch(BACKEND + "/video_note_subs?name=" + encodeURIComponent(data._noteName))).json(); } catch (_) { return; }
  if (!d || !d.ok || !(d.segments || []).length || !box.isConnected || box.querySelector(".vt-sub-bar")) return;
  if (d.lang && d.lang !== "zh") { const tb = box.querySelector(".vt-tidy-bar"); if (tb) tb.remove(); }   // 整理原文是按中文做的
  const foreign = d.lang && d.lang !== "zh";
  const bar = document.createElement("div");
  bar.className = "vt-sub-bar";
  bar.innerHTML =
    '<span class="vt-sub-seg"><button type="button" data-v="text" class="on">📄 原文</button>' +
    '<button type="button" data-v="subs">🎬 字幕</button><button type="button" data-v="zh">🀄 中文</button></span>' +
    '<span class="vt-sub-lang"></span>' +
    '<select class="vt-sub-eng" title="用哪个模型翻译：本地模型最快（在你自己的显卡上跑、不排队）；AI 池是网页版，慢一些"></select>' +
    '<button type="button" class="vbtn vt-sub-tr"></button>' +
    '<select class="vt-sub-exp" title="导出 .srt 字幕文件，拖进播放器（PotPlayer、VLC…）就能看">' +
    '<option value="">⬇ 导出字幕…</option><option value="orig">原文字幕</option>' +
    '<option value="zh">中文字幕</option><option value="both">双语字幕（原文 + 中文）</option></select>' +
    '<button type="button" class="vbtn vt-sub-save" hidden>💾 存到视频旁边</button>' +
    '<span class="vt-tidy-msg vt-sub-msg"></span>';
  const tidy = box.querySelector(".vt-tidy-bar");
  box.insertBefore(bar, tidy ? tidy.nextSibling : box.firstChild);
  const subBox = document.createElement("div"); subBox.className = "vt-subs"; subBox.hidden = true;
  box.appendChild(subBox);
  const msg = bar.querySelector(".vt-sub-msg"), trBtn = bar.querySelector(".vt-sub-tr"),
        exp = bar.querySelector(".vt-sub-exp"), save = bar.querySelector(".vt-sub-save");
  bar.querySelector(".vt-sub-lang").textContent = "语言：" + (d.lang_label || "中文");
  let view = "text", timer = null;
  // v96：翻译用哪个模型——默认本地模型（快），也可以选别的本地模型或 AI 池
  const eng = bar.querySelector(".vt-sub-eng");
  (async () => {
    let e = { local: [], default: "" };
    try { e = await (await fetch(BACKEND + "/translate_engines")).json(); } catch (_) {}
    const add = (v, t) => { const o = document.createElement("option"); o.value = v; o.textContent = t; eng.appendChild(o); };
    (e.local || []).forEach((m) => add("local:" + m, "翻译用：本地 " + m + (m === e.default ? "（默认）" : "")));
    if (!(e.local || []).length) add("local", "翻译用：本地模型（没找到，会先试着拉起 Ollama）");
    add("pool", "翻译用：AI 池（网页版，慢）");
    let pick = "";
    try { pick = localStorage.getItem("trEngine") || ""; } catch (_) {}
    if (pick && eng.querySelector('option[value="' + pick.replace(/"/g, "") + '"]')) eng.value = pick;
    else if (e.default) eng.value = "local:" + e.default;
  })();
  eng.addEventListener("change", () => { try { localStorage.setItem("trEngine", eng.value); } catch (_) {} });
  const textNodes = () => Array.from(box.children).filter((c) => c !== bar && c !== subBox && !c.classList.contains("vt-tidy-bar"));
  const zhProse = () => {
    const paras = []; let cur = "", n = 0;
    d.segments.forEach((sg, i) => {
      const z = (sg.zh || "").trim(); if (!z) return;
      cur += z; n++;
      const nx = d.segments[i + 1];
      const gap = nx ? nx.start - sg.end : 9;
      if (!/[。！？!?…]$/.test(z)) cur += (gap > 0.6 || n >= 3) ? "。" : "，";
      if ((n >= 5 && gap > 1.2) || n >= 8) { paras.push(cur); cur = ""; n = 0; }
    });
    if (cur) paras.push(cur);
    return paras;
  };
  const render = () => {
    bar.querySelectorAll(".vt-sub-seg button").forEach((b) => b.classList.toggle("on", b.dataset.v === view));
    const zhBtn = bar.querySelector('[data-v="zh"]');
    zhBtn.hidden = !d.has_zh;
    zhBtn.title = "只看中文译文";
    const showText = view === "text";
    textNodes().forEach((c) => { c.style.display = showText ? "" : "none"; });
    subBox.hidden = showText;
    if (view === "subs") {
      subBox.className = "vt-subs";
      subBox.innerHTML = "";
      d.segments.forEach((sg) => {
        const r = document.createElement("div"); r.className = "vt-sub-row";
        const t = document.createElement("span"); t.className = "vt-sub-t"; t.textContent = _vtFmtT(sg.start);
        t.title = _vtFmtT(sg.start) + " → " + _vtFmtT(sg.end);
        const c = document.createElement("div"); c.className = "vt-sub-c";
        const o = document.createElement("div"); o.className = "vt-sub-o"; o.textContent = sg.text;
        c.appendChild(o);
        if (sg.zh) { const z = document.createElement("div"); z.className = "vt-sub-z"; z.textContent = sg.zh; c.appendChild(z); }
        r.appendChild(t); r.appendChild(c); subBox.appendChild(r);
      });
    } else if (view === "zh") {
      subBox.className = "vt-subs vt-subs-prose";
      subBox.innerHTML = "";
      zhProse().forEach((p) => { const e = document.createElement("p"); e.textContent = p; subBox.appendChild(e); });
    }
    trBtn.hidden = !foreign;
    eng.hidden = !foreign;
    trBtn.textContent = d.has_zh ? "🔁 重新翻译" : "🌐 翻译成中文";
    trBtn.title = d.has_zh ? "全部重新翻译一遍（AI 翻得不好时用）" : "让 AI 一句一句翻译成中文，时间对得上，能做双语字幕";
    exp.querySelector('[value="zh"]').disabled = exp.querySelector('[value="both"]').disabled = !d.has_zh;
    save.hidden = !d.local_ok;
    save.title = "把字幕存成和视频同名的 .srt 放在视频旁边，播放器打开视频会自动加载" +
      (d.has_zh ? "（存中文字幕和双语字幕两份）" : "（还没翻译，先存原文字幕）");
  };
  bar.querySelectorAll(".vt-sub-seg button").forEach((b) => b.addEventListener("click", () => { view = b.dataset.v; render(); }));
  const reload = async () => {
    try {
      const nd = await (await fetch(BACKEND + "/video_note_subs?name=" + encodeURIComponent(data._noteName))).json();
      if (nd && nd.ok) d = nd;
    } catch (_) {}
  };
  const poll = async () => {
    await reload();
    const tr = d.translate || {};
    msg.className = "vt-tidy-msg vt-sub-msg";
    if (tr.running) {
      msg.textContent = tr.msg || "翻译中…";
      if (d.has_zh && view === "subs") render();               // 翻好的段先显示出来
      timer = setTimeout(poll, 2500); return;
    }
    trBtn.disabled = false;
    msg.textContent = tr.msg || "";
    if (tr.ok) { msg.className = "vt-tidy-msg vt-sub-msg ok"; view = "subs"; }
    render();
  };
  trBtn.addEventListener("click", async () => {
    if (d.has_zh && !confirm("把整条重新翻译一遍？（现在的中文译文会被替换）")) return;
    trBtn.disabled = true; msg.className = "vt-tidy-msg vt-sub-msg"; msg.textContent = "准备翻译…";
    try {
      const r = await (await fetch(BACKEND + "/video_note_translate", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: data._noteName, redo: !!d.has_zh, engine: eng.value || "local" }) })).json();
      if (!r.ok) { trBtn.disabled = false; msg.textContent = r.error || "没成功"; return; }
      clearTimeout(timer); timer = setTimeout(poll, 1500);
    } catch (e) { trBtn.disabled = false; msg.textContent = "后端没连上"; }
  });
  exp.addEventListener("change", async () => {
    const mode = exp.value; exp.value = "";
    if (!mode) return;
    try {
      const txt = await (await fetch(BACKEND + "/video_note_srt?mode=" + mode + "&name=" + encodeURIComponent(data._noteName))).text();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([txt], { type: "text/plain;charset=utf-8" }));
      const base = (data.title || data._noteName.replace(/\.md$/, "")).replace(/[\\/:*?"<>|\r\n]+/g, "_").slice(0, 60);
      a.download = base + { orig: "." + (d.lang || "orig"), zh: ".zh", both: ".双语" }[mode] + ".srt";
      document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
      msg.className = "vt-tidy-msg vt-sub-msg ok"; msg.textContent = "✓ 已导出 " + a.download;
    } catch (e) { msg.textContent = "导出出错：" + e.message; }
  });
  save.addEventListener("click", async () => {
    const modes = d.has_zh ? ["zh", "both"] : ["orig"];
    const done = [];
    for (const m of modes) {
      try {
        const r = await (await fetch(BACKEND + "/video_note_srt_save", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: data._noteName, mode: m }) })).json();
        if (r.ok) done.push(r.path.split(/[\\/]/).pop()); else { msg.textContent = r.error || "没存成"; return; }
      } catch (e) { msg.textContent = "出错：" + e.message; return; }
    }
    msg.className = "vt-tidy-msg vt-sub-msg ok"; msg.textContent = "✓ 已存到视频旁边：" + done.join("、") + "（用播放器打开视频会自动加载）";
  });
  render();
  if ((d.translate || {}).running) { trBtn.disabled = true; poll(); }
}


// ════════════════════ v97：日语专用模型 ════════════════════
// 质量下拉框加「日语专用（kotoba-whisper）」：日本团队用几万小时日语训练的，日语比 large-v3 准、还快；
// 第一次用要下载约 1.5GB。选它时，语言自动切到「日语」（日语模式：小声的放大、静音检测放宽、漏的段补得更细）。
(function _vtJaLevel() {
  const sel = document.getElementById("videoLevel");
  if (!sel || sel.querySelector('option[value="ja"]')) return;
  const o = document.createElement("option");
  o.value = "ja"; o.textContent = "日语专用（kotoba-whisper）";
  o.title = "专门识别日语的模型，日语比「超精准」更准、更快；第一次用要下载约 1.5GB";
  sel.appendChild(o);
  // v98：日语·情绪 / 小声（Anime-Whisper）——带情绪、小声、喘息、语气夸张的说话认得更准
  const o2 = document.createElement("option");
  o2.value = "anime"; o2.textContent = "日语·情绪 / 小声（Anime-Whisper）";
  o2.title = "用动漫、游戏配音训练的日语模型：带情绪、小声、喘息、语气夸张的说话认得更准；" +
    "第一次用要下载约 1.6GB，再在你电脑上转一次格式（几分钟，只做一次）";
  sel.appendChild(o2);
  try {
    const saved = localStorage.getItem("videoLevelPick");
    if (saved === "ja" || saved === "anime") sel.value = saved;
  } catch (e) {}
  const sync = () => {
    const lang = document.getElementById("videoLang");
    if ((sel.value === "ja" || sel.value === "anime") && lang && lang.value !== "ja") {
      lang.value = "ja";
      try { localStorage.setItem("videoLangPick", "ja"); } catch (_) {}
    }
  };
  sel.addEventListener("change", sync);
  sync();
})();


// ════════════════════ v102：先分离人声 ════════════════════
// 「开始提取」里一个开关：识别前先把背景音乐、环境声、杂音去掉，只留人声——小声的、背景吵的地方认得更准、更少漏。
// 第一次用要下载人声模型（约 66MB）；有显卡的还会装一套显卡运行库（约 1～2GB，只装一次），没显卡就用 CPU（慢一些）。
function vnCurVocal() {
  const el = document.getElementById("videoVocal");
  if (el) return !!el.checked;
  try { return localStorage.getItem("videoVocalPick") === "1"; } catch (_) { return false; }
}
(function _vtVocalToggle() {
  const anchor = document.querySelector("#view-video .vt-tidy-auto") || document.querySelector("#view-video .video-creator-row");
  if (!anchor || document.getElementById("videoVocal")) return;
  const row = document.createElement("label");
  row.className = "vt-tidy-auto";
  row.title = "识别前先把背景音乐、环境声、杂音去掉，只留人声，再交给语音识别：小声的、背景吵的地方认得更准、更少漏。\n" +
    "代价是多花时间：有显卡很快；没显卡用 CPU，一小时的视频可能要多 10～20 分钟。同一个文件分离过一次就会记住，再提取不用重来。\n" +
    "第一次用要下载人声模型（约 66MB）；有显卡的还会装一套显卡运行库（约 1～2GB，只装一次）。";
  row.innerHTML = '<input type="checkbox" id="videoVocal"> 🎤 先分离人声（去掉背景音乐和杂音再识别，更准，多花点时间）';
  anchor.parentNode.insertBefore(row, anchor.nextSibling);
  const cb = row.querySelector("input");
  try { cb.checked = localStorage.getItem("videoVocalPick") === "1"; } catch (_) {}
  cb.addEventListener("change", () => { try { localStorage.setItem("videoVocalPick", cb.checked ? "1" : "0"); } catch (_) {} });
})();
