// kb.js —「知识库」（v162 新增；v163 把原来的「资料库」整个改造成知识库）
// 参照 Karpathy 的「LLM Wiki」，分四块（顶部标签由 renderer.js 的 NAV_GROUPS.data 画，切换时调 window.cxPaneShow.kb）：
//   主题页：AI 整理出的一页页主题页（公司、行业、人物…），互相链接、句句标出处
//   原始资料：软件各处生成的资料（视频笔记、报告、简报、对话…）都在这一张表里，看得到收没收、改了哪几页
//   关系图：主题页之间的链接画成网
//   整理记录：收录队列、每份资料改了什么、自动收录的开关
// 后端是 backend/kb.py。
(function () {
  "use strict";
  const root = document.getElementById("view-kb");
  if (!root) return;

  const TYPE = { company: "公司", industry: "行业", person: "人物", product: "产品", concept: "概念", event: "事件", other: "其他" };
  const TYPE_COLOR = { company: "#3b6fd1", industry: "#c4613a", person: "#8a4fc2", product: "#2f8f5b", concept: "#7a7f8c", event: "#b07d12", other: "#9a958c" };
  const KIND = { note: "视频笔记", report: "研究报告", news: "新闻", text: "粘贴的资料", briefing: "情报简报", sniff: "嗅探简报",
    research: "主动研究", insight: "洞察报告", daily: "每日笔记", conv: "对话存档" };
  const STATUS = [["all", "全部"], ["new", "未收录"], ["queued", "排队中"], ["done", "已收录"], ["failed", "没收成"], ["todo", "还没分析"]];
  const AUTO_KINDS = [["note", "视频笔记", "分析好以后"], ["report", "研究报告", "写好以后"], ["research", "主动研究", ""], ["insight", "洞察报告", ""],
    ["briefing", "情报简报", "每天都有，量大"], ["sniff", "嗅探简报", "量大"], ["daily", "每日笔记", "一天里会一直写，收的是写到一半的"], ["conv", "对话存档", "闲聊多，容易把知识库弄乱"]];
  const backend = () => { try { if (typeof BACKEND === "string" && BACKEND) return BACKEND; } catch (e) {} return "http://127.0.0.1:8756"; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById(id);
  const enc = encodeURIComponent;
  const pad = (n) => (n < 10 ? "0" : "") + n;
  const md = (s) => (typeof renderMarkdown === "function" ? renderMarkdown(s || "") : "<pre>" + esc(s) + "</pre>");
  const api = (path, body) => fetch(backend() + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined)
    .then((r) => r.json());
  const fmtTime = (ts) => { if (!ts) return ""; const d = new Date(ts * 1000); return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + pad(d.getHours()) + ":" + pad(d.getMinutes()); };
  const fmtDay = (ts) => { if (!ts) return ""; const d = new Date(ts * 1000); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
  const ago = (ts) => {
    if (!ts) return "";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "刚刚";
    if (s < 3600) return Math.floor(s / 60) + " 分钟前";
    if (s < 86400) return Math.floor(s / 3600) + " 小时前";
    if (s < 86400 * 30) return Math.floor(s / 86400) + " 天前";
    return fmtTime(ts);
  };
  const mmss = (s) => { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + " 分 " + pad(s % 60) + " 秒"; };
  const PANE_OF = { kb: "pages", raw: "raw", graph: "graph", log: "log" };

  const S = {
    pane: "pages", ov: null, sel: "", page: null, q: "", type: "all", hits: null, view: "overview",
    raw: { kind: "all", status: "all", q: "", page: 1, size: 50, data: null, chosen: {}, sel: "", item: null, seq: 0 },
    g: { data: null, type: "all", focus: "", sel: "" }, src: null,
  };

  // ───────── 外框 ─────────
  function buildShell() {
    root.innerHTML =
      '<div class="kb-scroll" id="kbScroll"><div class="kb-wrap">' +
        '<div class="kb-status" id="kbStatus" aria-live="polite"></div>' +
        '<div class="cx-ail-slot kb-live" id="kbLive" hidden></div>' +
        '<div class="kb-pane" data-pane="pages"><div class="kb-cols">' +
          '<aside class="kb-list">' +
            '<input class="kb-input" id="kbQ" type="search" placeholder="在主题页里搜：比如 五粮液、库存" aria-label="搜索主题页">' +
            '<div class="kb-types" id="kbTypes" role="group" aria-label="按类型看"></div>' +
            '<div class="kb-pages" id="kbPages"></div>' +
          "</aside>" +
          '<main class="kb-main" id="kbMain"></main>' +
        "</div></div>" +
        '<div class="kb-pane" data-pane="raw" hidden>' +
          '<div class="kb-raw-top"><p>软件各处生成的资料都在这里。勾选后点「加入收录队列」，AI 池会把它们整理进主题页。已经收录的，能看到它改了哪几页。</p>' +
            '<button type="button" class="kb-btn ghost" data-act="paste">粘贴一段资料</button></div>' +
          '<div class="kb-raw-bar"><div class="kb-types" id="kbRawKinds" role="group" aria-label="资料类型"></div>' +
            '<div class="kb-raw-bar2"><div class="kb-seg" id="kbRawSt" role="group" aria-label="收录状态"></div>' +
            '<input class="kb-input" id="kbRawQ" type="search" placeholder="按标题、作者找" aria-label="找资料"></div></div>' +
          '<div class="kb-raw-cols"><div class="kb-raw-list"><div id="kbRawList"></div><nav class="kb-pager" id="kbRawPager" aria-label="翻页"></nav></div>' +
            '<aside class="kb-raw-prev" id="kbRawPrev"></aside></div>' +
          '<div class="kb-raw-act" id="kbRawAct" hidden></div>' +
        "</div>" +
        '<div class="kb-pane" data-pane="graph" hidden>' +
          '<div class="kb-g-bar"><div class="kb-types" id="kbGTypes" role="group" aria-label="按类型看"></div><span class="sp"></span><span class="kb-dim" id="kbGInfo"></span></div>' +
          '<div class="kb-g-wrap" id="kbGWrap"><canvas id="kbCanvas" aria-label="主题页关系图：每个点是一个主题页，线是页面之间的链接"></canvas>' +
            '<div class="kb-g-tip" id="kbGTip" hidden></div><div class="kb-g-card" id="kbGCard" hidden></div>' +
            '<p class="kb-g-help">拖动空白处移动，滚轮缩放，拖动圆点调整位置；点一个圆点看详情。</p></div>' +
        "</div>" +
        '<div class="kb-pane" data-pane="log" hidden><div class="kb-log-cols"><div id="kbLogMain"></div><aside id="kbLogSide"></aside></div></div>' +
      "</div></div>" +
      '<div class="kb-modal" id="kbModal" hidden><div class="kb-dlg" role="dialog" aria-modal="true" aria-labelledby="kbDlgT"><div id="kbDlgBody"></div></div></div>' +
      '<div class="kb-toast" id="kbToast" role="status" hidden></div>';
  }
  function toast(msg) {
    const t = $("kbToast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { t.hidden = true; }, 3200);
  }
  function goPane(key) {
    if (typeof navOpenGroup === "function") navOpenGroup("data", key);
    else showPane(key);
  }
  function showPane(key) {
    const p = PANE_OF[key] || key || "pages";
    S.pane = p;
    root.dataset.pane = p;
    root.querySelectorAll(".kb-pane").forEach((el) => { el.hidden = el.dataset.pane !== p; });
    const sc = $("kbScroll");
    if (sc) sc.scrollTop = 0;
    if (p === "raw") loadRaw(true);
    else if (p === "graph") loadGraph();
    else if (p === "log") renderLog();
    if (p !== "graph") stopSim();
  }

  // ───────── 读取 ─────────
  let pollT = null;
  async function refresh() {
    try { S.ov = await api("/kb/overview"); } catch (e) { S.ov = { ok: false, error: "连不上后台：" + e.message }; }
    renderStatus(); renderTypes(); renderPages();
    if (S.pane === "pages" && S.view === "overview") renderOverview();
    if (S.pane === "log") renderLog();
    clearTimeout(pollT);
    if (root.classList.contains("active")) pollT = setTimeout(refresh, S.ov && S.ov.running ? 3000 : 12000);
  }

  function renderStatus() {                                       // v190：画完把 AI 实时画面放到「正在收录」下面（没在收录就收走）
    renderStatus0();
    const o = S.ov;
    if (window.cxAiLive) window.cxAiLive.place("kb", o && o.ok !== false && o.running ? $("kbLive") : null);
  }
  function renderStatus0() {
    const el = $("kbStatus"), o = S.ov;
    if (!o) { el.innerHTML = "<span>正在读取…</span>"; return; }
    if (o.ok === false) { el.innerHTML = '<span class="kb-bad">' + esc(o.error) + "</span>"; return; }
    const c = o.config || {};
    const parts = ["<span><b>" + o.pages.length + "</b> 个主题页 · 来自 <b>" + o.n_sources + "</b> 份资料</span>"];
    if (o.running) {
      parts.push('<button type="button" class="kb-run cx-ail-tg" data-ail-toggle="kb"><i class="kb-dot" aria-hidden="true"></i>正在收录「' + esc(o.running.title) + "」：" + esc(o.running.stage || "…") +
        "（" + mmss(o.now - o.running.started) + '）<span class="cx-ail-caret">' + (window.cxAiLive ? window.cxAiLive.caret("kb") : "") + "</span></button>" +   // v190：点它在下面展开实时画面
        '<button type="button" class="kb-link" data-act="stop">停止</button>');
    } else if (c.paused) {
      parts.push('<span class="kb-warn">收录暂停了' + (o.n_pending ? "，队列里还有 " + o.n_pending + " 份" : "") + '</span><button type="button" class="kb-link" data-act="resume">继续收录</button>');
    } else if (o.n_pending) {
      parts.push("<span>队列里还有 " + o.n_pending + " 份等着收录（一份一般 2～5 分钟，AI 池空了就开始）</span>");
    }
    if (o.n_failed) parts.push('<span class="kb-bad">' + o.n_failed + ' 份没收录成</span><button type="button" class="kb-link" data-goto="log">看看</button>');
    el.innerHTML = parts.join("");
  }

  function renderTypes() {
    const o = S.ov;
    if (!o || !o.types) return;
    $("kbTypes").innerHTML = [["all", "全部", o.pages.length]].concat(o.types.filter((t) => t[2])).map(([k, n, c]) =>
      '<button type="button" data-type="' + k + '" aria-pressed="' + (S.type === k) + '">' + esc(n) + " <b>" + c + "</b></button>").join("");
  }

  function renderPages() {
    const el = $("kbPages"), o = S.ov;
    if (!o || o.ok === false) { el.innerHTML = ""; return; }
    let list;
    if (S.q) {
      if (!S.hits) { el.innerHTML = '<p class="kb-empty">正在搜…</p>'; return; }
      list = S.hits.map((h) => Object.assign({}, o.pages.find((p) => p.id === h.id) || {}, h));
    } else list = o.pages;
    if (S.type !== "all") list = list.filter((p) => p.type === S.type);
    if (!list.length) {
      el.innerHTML = '<p class="kb-empty">' + (S.q ? "没搜到。" : o.pages.length ? "这一类还没有页面。" : "还没有主题页。") + "</p>";
      return;
    }
    el.innerHTML = list.map((p) =>
      '<button type="button" class="kb-pi' + (p.id === S.sel ? " on" : "") + '" data-page="' + esc(p.id) + '"' + (p.id === S.sel ? ' aria-current="true"' : "") + ">" +
        '<span class="kb-pi-h"><b>' + esc(p.title) + '</b><span class="kb-ty t-' + esc(p.type) + '">' + esc(TYPE[p.type] || "其他") + "</span></span>" +
        '<span class="kb-pi-s">' + esc(p.snip || p.summary || "") + "</span>" +
        '<span class="kb-pi-m">' + (p.n_src ? p.n_src + " 份资料 · " : "") + ago(p.updated) + "更新</span>" +
      "</button>").join("");
  }

  // ───────── 主题页 → 概览 ─────────
  function renderOverview() {
    S.view = "overview";
    const el = $("kbMain"), o = S.ov;
    if (!o) { el.innerHTML = '<p class="kb-empty">正在读取…</p>'; return; }
    if (o.ok === false) { el.innerHTML = '<p class="kb-empty">' + esc(o.error) + "</p>"; return; }
    if (!o.pages.length) {
      el.innerHTML = '<section class="kb-card kb-intro"><h3>知识库还是空的</h3><ol>' +
        "<li>去<b>「原始资料」</b>，勾选几份视频笔记、研究报告或简报，点「加入收录队列」。建议先挑同一个方向的 5～10 份。</li>" +
        "<li>AI 池空了就一份一份收录：读资料，再新建或更新相关的主题页（公司、行业、人物、概念…）。一份一般 2～5 分钟。</li>" +
        "<li>页面里每句话后面都有<b>〔S数字〕</b>，点一下能看到出自哪份资料；<b>蓝色名字</b>可以跳到别的页面。</li>" +
        "<li>以后新的视频笔记、研究报告会自动收录（在「整理记录」里可以改）。</li></ol>" +
        '<p><button type="button" class="kb-btn" data-goto="raw">去挑资料</button></p></section>';
      return;
    }
    const recent = o.pages.slice(0, 12);
    el.innerHTML =
      '<section class="kb-card"><h3>概览</h3><div class="kb-stats">' +
        o.types.filter((t) => t[2]).map(([k, n, c]) => '<button type="button" class="kb-stat" data-type="' + k + '"><b>' + c + "</b><span>" + esc(n) + "</span></button>").join("") +
        '<div class="kb-stat plain"><b>' + o.n_sources + "</b><span>份资料</span></div></div></section>" +
      '<section class="kb-card"><div class="kb-card-h"><h3>最近更新的主题页</h3><button type="button" class="kb-link" data-goto="graph">看关系图</button></div><div class="kb-recent">' +
        recent.map((p) => '<button type="button" class="kb-rc" data-page="' + esc(p.id) + '"><span class="kb-pi-h"><b>' + esc(p.title) + '</b><span class="kb-ty t-' + esc(p.type) + '">' +
          esc(TYPE[p.type] || "其他") + '</span></span><span class="kb-pi-s">' + esc(p.summary || "") + '</span><span class="kb-pi-m">第 ' + (p.ver || 1) + " 版 · " + ago(p.updated) + "更新</span></button>").join("") +
      "</div></section>" +
      ((o.log || []).length ? '<section class="kb-card"><div class="kb-card-h"><h3>最近的变化</h3><button type="button" class="kb-link" data-goto="log">全部记录</button></div><ul class="kb-logs">' +
        o.log.slice(0, 5).map(logRow).join("") + "</ul></section>" : "");
  }

  async function openPage(id, push) {
    if (S.pane !== "pages") goPane("kb");
    S.sel = id;
    S.view = "page";
    renderPages();
    const el = $("kbMain");
    el.innerHTML = '<p class="kb-empty">正在打开…</p>';
    let r;
    try { r = await api("/kb/page?id=" + enc(id)); } catch (e) { r = { ok: false, error: e.message }; }
    if (S.sel !== id) return;
    S.page = r;
    if (!r.ok) { el.innerHTML = '<p class="kb-empty">' + esc(r.error) + '</p><button type="button" class="kb-link" data-act="overview">回到概览</button>'; return; }
    const m = r.meta;
    const srcByN = {};
    r.sources.forEach((s) => { srcByN[String(s.n)] = s; });
    // 标题和「一句话」自己画；正文里别的「> 引用」行去掉引号（渲染器不认）
    let bodySrc = r.body.replace(/^#\s+.+\n+/, "").replace(/^\s*>\s?(.+)\n*/, "");
    bodySrc = bodySrc.replace(/^>\s?/gm, "");
    let html = md(bodySrc);
    html = html.replace(/\[\[([^\[\]<>]{1,60})\]\]/g, (all, t) => {
      const pid = r.links[t] || r.links[t.trim()];
      return pid ? '<button type="button" class="kb-wl" data-page="' + esc(pid) + '">' + t + "</button>"
        : '<span class="kb-wl none" title="还没有这一页">' + t + "</span>";
    });
    html = html.replace(/〔S(\d+)〕/g, (all, n) => {
      const s = srcByN[n];
      return '<button type="button" class="kb-cite" data-src="' + n + '" title="' + esc(s ? (KIND[s.kind] || "") + "：" + s.title : "资料 S" + n) + '">S' + n + "</button>";
    });
    el.innerHTML =
      '<article class="kb-card kb-page">' +
        '<div class="kb-page-bar"><button type="button" class="kb-link" data-act="overview">‹ 概览</button><span class="sp"></span>' +
          (r.history.length ? '<button type="button" class="kb-btn ghost sm" data-act="hist">历史版本（' + r.history.length + "）</button>" : "") +
          '<button type="button" class="kb-btn ghost sm danger" data-act="del">删除这一页</button></div>' +
        '<h1 class="kb-page-t">' + esc(m.title) + ' <span class="kb-ty t-' + esc(m.type) + '">' + esc(TYPE[m.type] || "其他") + "</span></h1>" +
        (m.aliases && m.aliases.length ? '<p class="kb-alias">也叫：' + esc(m.aliases.join("、")) + "</p>" : "") +
        (m.summary ? '<p class="kb-lead">' + esc(m.summary) + "</p>" : "") +
        '<p class="kb-page-m">第 ' + (m.ver || 1) + " 版 · " + esc(fmtTime(m.updated)) + "更新 · 来自 " + r.sources.length + " 份资料</p>" +
        '<div class="kb-body">' + html + "</div>" +
        (r.backlinks.length ? '<h3 class="kb-sub">被这些页面提到</h3><p class="kb-backs">' + r.backlinks.map((b) =>
          '<button type="button" class="kb-wl" data-page="' + esc(b.id) + '">' + esc(b.title) + "</button>").join("") + "</p>" : "") +
        '<h3 class="kb-sub">出处</h3><ol class="kb-srcs">' + r.sources.map((s) =>
          '<li><button type="button" class="kb-cite" data-src="' + s.n + '">S' + s.n + "</button>" +
          '<span class="kb-kind">' + esc(KIND[s.kind] || "") + "</span>" +
          '<button type="button" class="kb-link" data-src="' + s.n + '">' + esc(s.title) + "</button>" +
          '<span class="kb-dim">' + esc(fmtTime(s.ingested)) + "收录</span>" +
          (s.url ? '<a class="kb-ext" href="' + esc(s.url) + '" target="_blank" rel="noopener">原文链接</a>' : "") + "</li>").join("") + "</ol>" +
      "</article>";
    if (push !== false) { const sc = $("kbScroll"); if (sc) sc.scrollTop = 0; }
  }

  // ───────── 弹窗 ─────────
  function openModal(html) {
    $("kbDlgBody").innerHTML = html;
    $("kbModal").hidden = false;
    setTimeout(() => { const f = $("kbModal").querySelector("[data-autofocus]") || $("kbModal").querySelector("button, input, textarea"); if (f) f.focus(); }, 30);
  }
  function closeModal() { $("kbModal").hidden = true; S.src = null; }
  const head = (t, sub) => '<div class="kb-dlg-h"><div><h2 id="kbDlgT">' + t + "</h2>" + (sub ? "<p>" + sub + "</p>" : "") + '</div><button type="button" class="kb-x" data-close aria-label="关闭">×</button></div>';

  async function openSource(n) {
    openModal(head("资料 S" + esc(n)) + '<div class="kb-dlg-b"><p class="kb-empty">正在读取…</p></div>');
    let r;
    try { r = await api("/kb/source?n=" + enc(n)); } catch (e) { r = { ok: false, error: e.message }; }
    if ($("kbModal").hidden) return;
    if (!r.ok) { $("kbDlgBody").innerHTML = head("资料 S" + esc(n)) + '<div class="kb-dlg-b"><p class="kb-empty">' + esc(r.error) + "</p></div>"; return; }
    const m = r.meta;
    $("kbDlgBody").innerHTML = head("S" + m.n + " · " + esc(m.title), esc(KIND[m.kind] || "") + (m.who ? " · " + esc(m.who) : "") + " · " + esc(fmtTime(m.ingested)) + "收录（" + esc(m.by || "AI 池") + "）") +
      '<div class="kb-dlg-b">' +
        (m.summary ? '<p class="kb-sum">' + esc(m.summary) + "</p>" : "") +
        (r.pages.length ? '<p class="kb-chs">这份资料改过：' + r.pages.map((p) => '<button type="button" class="kb-ch update" data-page="' + esc(p.id) + '" data-close-after>「' + esc(p.title) + "」</button>").join("") + "</p>" : "") +
        (m.url ? '<p class="kb-dim">原文链接：<a class="kb-ext" href="' + esc(m.url) + '" target="_blank" rel="noopener">' + esc(m.url) + "</a></p>" : "") +
        '<div class="kb-srctext">' + md(r.text) + "</div>" +
      "</div>";
  }

  function openHist() {
    const r = S.page;
    if (!r || !r.ok) return;
    openModal(head("「" + esc(r.meta.title) + "」的历史版本", "AI 每次改这一页之前都会存一份旧版本。看中哪一版可以恢复，恢复前的当前版本也会存下来。") +
      '<div class="kb-dlg-b kb-hist"><ul class="kb-hl">' + r.history.map((ts, i) =>
        '<li><button type="button" class="kb-link" data-hv="' + ts + '">' + esc(fmtTime(ts)) + " 之前的版本</button></li>").join("") + "</ul>" +
        '<div class="kb-hv" id="kbHv"><p class="kb-empty">点左边一个版本看内容。</p></div></div>');
  }
  async function showHist(ts) {
    const r = S.page;
    const el = $("kbHv");
    el.innerHTML = '<p class="kb-empty">正在读取…</p>';
    const x = await api("/kb/page_action", { id: r.meta.id, act: "history", ts: +ts }).catch((e) => ({ ok: false, error: e.message }));
    if (!x.ok) { el.innerHTML = '<p class="kb-empty">' + esc(x.error) + "</p>"; return; }
    el.innerHTML = '<div class="kb-hv-bar"><b>' + esc(fmtTime(+ts)) + ' 之前的版本</b><span class="sp"></span><button type="button" class="kb-btn sm" data-restore="' + ts + '">恢复成这一版</button></div>' +
      '<div class="kb-body">' + md(x.body) + "</div>";
  }

  // 收录资料

  // ───────── 原始资料 ─────────
  async function loadRaw(keepPage) {
    const R = S.raw;
    if (!keepPage) R.page = 1;
    const seq = ++R.seq;
    if (!R.data) $("kbRawList").innerHTML = '<p class="kb-empty">正在读取…（资料多的话第一次要几秒）</p>';
    let r;
    try { r = await api("/kb/raw?kind=" + R.kind + "&status=" + R.status + "&q=" + enc(R.q) + "&offset=" + (R.page - 1) * R.size + "&limit=" + R.size); }
    catch (e) { r = { ok: false, error: e.message }; }
    if (seq !== R.seq) return;
    R.data = r;
    renderRaw();
    if (!R.sel) renderRawPrev();
  }
  const pickable = (it) => it.status === "new" || it.status === "failed";
  function renderRaw() {
    const R = S.raw, d = R.data;
    if (!d || d.ok === false) { $("kbRawList").innerHTML = '<p class="kb-empty">' + esc((d && d.error) || "读不到") + "</p>"; return; }
    const tot = d.kinds.reduce((a, k) => a + k[2], 0);
    $("kbRawKinds").innerHTML = [["all", "全部", tot]].concat(d.kinds).map(([k, n, c]) =>
      '<button type="button" data-rk="' + k + '" aria-pressed="' + (R.kind === k) + '">' + esc(n) + " <b>" + c + "</b></button>").join("");
    $("kbRawSt").innerHTML = STATUS.filter(([k]) => k === "all" || k === R.status || (d.statuses || {})[k]).map(([k, n]) =>
      '<button type="button" data-rs="' + k + '" aria-pressed="' + (R.status === k) + '">' + esc(n) + (k !== "all" && (d.statuses || {})[k] ? " " + d.statuses[k] : "") + "</button>").join("");
    if (!d.items.length) {
      $("kbRawList").innerHTML = '<p class="kb-empty">' + (R.q ? "没找到。" : "这里没有资料。") + "</p>";
    } else {
      const can = d.items.filter(pickable);
      const allOn = can.length && can.every((it) => R.chosen[it.sid]);
      $("kbRawList").innerHTML =
        '<div class="kb-rr head"><label class="kb-ck" title="全选这一页能收录的"><input type="checkbox" data-act="raw-all"' + (allOn ? " checked" : "") +
          (can.length ? "" : " disabled") + ' aria-label="全选这一页"></label><span>资料</span><span>状态</span></div>' +
        d.items.map((it) => {
          const st = {
            done: '<span class="kb-st done">已收录' + (it.n ? " · S" + it.n : "") + "</span>",
            queued: '<span class="kb-st q">排队中</span>', running: '<span class="kb-st q"><i class="kb-dot"></i>正在收录</span>',
            failed: '<span class="kb-st bad" title="' + esc(it.error || "") + '">没收成</span>', todo: '<span class="kb-st dim" title="视频还没分析完，分析好才能收录">还没分析</span>',
            new: '<span class="kb-st dim">未收录</span>' }[it.status] || "";
          return '<div class="kb-rr' + (R.sel === it.sid ? " on" : "") + '">' +
            '<label class="kb-ck"><input type="checkbox" data-rpick="' + esc(it.sid) + '"' + (R.chosen[it.sid] ? " checked" : "") +
              (pickable(it) ? "" : " disabled") + ' aria-label="选这份"></label>' +
            '<button type="button" class="kb-rr-b" data-kbraw="' + esc(it.sid) + '"' + (R.sel === it.sid ? ' aria-current="true"' : "") + ">" +
              '<span class="kb-rr-t"><span class="kb-kind">' + esc(KIND[it.kind] || it.kind) + "</span>" + esc(it.title || "（没有标题）") + "</span>" +
              '<span class="kb-rr-m">' + esc(it.who || "") + (it.who ? " · " : "") + esc(fmtDay(it.ts)) +
                (it.pages && it.pages.length ? " · 改了 " + it.pages.map((p) => "「" + esc(p.title) + "」").join("") : "") + "</span>" +
            "</button>" + st + "</div>";
        }).join("");
    }
    const pages = Math.max(1, Math.ceil(d.total / R.size));
    $("kbRawPager").innerHTML = d.total > R.size ? '<button type="button" class="kb-pg" data-rpage="' + (R.page - 1) + '"' + (R.page <= 1 ? " disabled" : "") + ">上一页</button>" +
      "<span>第 " + R.page + " / " + pages + " 页 · 共 " + d.total + " 份</span>" +
      '<button type="button" class="kb-pg" data-rpage="' + (R.page + 1) + '"' + (R.page >= pages ? " disabled" : "") + ">下一页</button>"
      : (d.total ? "<span>共 " + d.total + " 份</span>" : "");
    renderRawAct();
  }
  function renderRawAct() {
    const n = Object.keys(S.raw.chosen).length, el = $("kbRawAct");
    el.hidden = !n;
    if (!n) return;
    const mins = n * 3.5;
    el.innerHTML = "<span>选了 <b>" + n + "</b> 份，大约要 " + (mins >= 60 ? (mins / 60).toFixed(1) + " 小时" : Math.round(mins) + " 分钟") + "（一份一份来，不用守着）</span>" +
      '<span class="sp"></span><button type="button" class="kb-link dim" data-act="raw-clear">取消选择</button>' +
      '<button type="button" class="kb-btn" data-act="raw-add">加入收录队列</button>';
  }
  async function openRaw(sid) {
    const R = S.raw;
    R.sel = sid;
    if (R.data) renderRaw();
    const el = $("kbRawPrev");
    el.innerHTML = '<div class="kb-card"><p class="kb-empty">正在读取…</p></div>';
    let r;
    try { r = await api("/kb/raw_item?sid=" + enc(sid)); } catch (e) { r = { ok: false, error: e.message }; }
    if (R.sel !== sid) return;
    R.item = r;
    renderRawPrev();
  }
  function renderRawPrev() {
    const el = $("kbRawPrev"), r = S.raw.item, R = S.raw;
    if (!R.sel || !r) {
      el.innerHTML = '<div class="kb-card kb-raw-help"><h3>原始资料</h3><p>点左边一份资料，在这里看全文、收录状态，以及它改了哪几个主题页。</p>' +
        "<p>没收录过的资料不会影响知识库；收录过的资料就算以后删了原文件，主题页里的出处照样能点开（收录时存了一份）。</p></div>";
      return;
    }
    if (!r.ok) { el.innerHTML = '<div class="kb-card"><p class="kb-empty">' + esc(r.error) + "</p></div>"; return; }
    const st = r.status === "done"
      ? '<div class="kb-rp-st done"><b>已收录</b>（S' + r.n + "，" + esc(fmtTime(r.ingested)) + "，" + esc(r.by || "AI 池") + "）" +
        (r.summary ? "<p>" + esc(r.summary) + "</p>" : "") +
        (r.pages.length ? '<p class="kb-chs">改过：' + r.pages.map((p) => '<button type="button" class="kb-ch update" data-page="' + esc(p.id) + '">「' + esc(p.title) + "」</button>").join("") + "</p>" : '<p class="kb-dim">这份资料里没有值得记的内容，没改页面。</p>') + "</div>"
      : r.status === "queued" ? '<div class="kb-rp-st q"><b>在收录队列里</b>，AI 池空了就收录。' + (r.q_error ? '<p class="kb-bad">上次没收成：' + esc(r.q_error.slice(0, 160)) + "</p>" : "") + "</div>"
      : r.status === "failed" ? '<div class="kb-rp-st bad"><b>没收录成</b><p>' + esc((r.q_error || "").slice(0, 200)) + '</p><button type="button" class="kb-btn sm" data-q="retry" data-sid="' + esc(r.sid) + '">再试一次</button></div>'
      : '<div class="kb-rp-st"><b>还没收录</b><button type="button" class="kb-btn sm" data-act="raw-one">收录这份</button></div>';
    el.innerHTML = '<div class="kb-card kb-raw-doc">' +
      '<div class="kb-raw-doc-h"><span class="kb-kind">' + esc(r.kind_name) + '</span><span class="sp"></span>' +
        (r.cat ? '<a class="kb-btn ghost sm" href="' + esc(backend() + "/datadb/export?cat=" + enc(r.cat) + "&name=" + enc(r.name)) + '" download>导出</a>' : "") +
        (r.can_delete ? '<button type="button" class="kb-btn ghost sm danger" data-act="raw-del">删除</button>' : "") +
        '<button type="button" class="kb-x" data-act="raw-close" aria-label="关闭预览">×</button></div>' +
      "<h2>" + esc(r.title) + "</h2>" +
      '<p class="kb-dim">' + esc(r.who || "") + (r.who ? " · " : "") + esc(fmtTime(r.ts)) + (r.url ? ' · <a class="kb-ext" href="' + esc(r.url) + '" target="_blank" rel="noopener">原文链接</a>' : "") + "</p>" +
      st +
      '<div class="kb-srctext">' + md((r.text || "").slice(0, 40000)) + ((r.text || "").length > 40000 ? '<p class="kb-dim">……后面还有，太长了没全显示。</p>' : "") + "</div>" +
    "</div>";
  }

  // ───────── 关系图 ─────────
  const G = { nodes: [], edges: [], byId: {}, sc: 1, ox: 0, oy: 0, raf: 0, ticks: 0, drag: null, hover: null, pan: null, w: 0, h: 0, dpr: 1 };
  async function loadGraph() {
    let r;
    try { r = await api("/kb/graph"); } catch (e) { r = { ok: false, error: e.message }; }
    S.g.data = r;
    buildGraph();
  }
  function visibleIds() {
    const d = S.g.data;
    if (!d || !d.ok) return new Set();
    let ids = new Set(d.nodes.filter((n) => S.g.type === "all" || n.type === S.g.type).map((n) => n.id));
    if (S.g.focus) {                         // 只看某一页周围两层
      const adj = {};
      d.edges.forEach(([a, b]) => { (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a); });
      const keep = new Set([S.g.focus]);
      let front = [S.g.focus];
      for (let k = 0; k < 2; k++) {
        const nx = [];
        front.forEach((x) => (adj[x] || []).forEach((y) => { if (!keep.has(y)) { keep.add(y); nx.push(y); } }));
        front = nx;
      }
      ids = new Set([...ids].filter((x) => keep.has(x)));
      ids.add(S.g.focus);
    }
    return ids;
  }
  function buildGraph() {
    const d = S.g.data, info = $("kbGInfo");
    if (!d || !d.ok) { info.textContent = (d && d.error) || ""; return; }
    const counts = {};
    d.nodes.forEach((n) => { counts[n.type] = (counts[n.type] || 0) + 1; });
    $("kbGTypes").innerHTML = [["all", "全部", d.nodes.length]].concat(Object.keys(TYPE).filter((k) => counts[k]).map((k) => [k, TYPE[k], counts[k]])).map(([k, n, c]) =>
      '<button type="button" data-gt="' + k + '" aria-pressed="' + (S.g.type === k) + '">' + (k !== "all" ? '<i class="kb-sw-c" style="background:' + TYPE_COLOR[k] + '"></i>' : "") + esc(n) + " <b>" + c + "</b></button>").join("");
    const ids = visibleIds();
    const old = G.byId;
    G.nodes = d.nodes.filter((n) => ids.has(n.id)).map((n) => {
      const o = old[n.id];
      return Object.assign({}, n, { x: o ? o.x : (Math.random() - 0.5) * 400, y: o ? o.y : (Math.random() - 0.5) * 300, vx: 0, vy: 0, r: 6 + Math.min(14, Math.sqrt(n.deg) * 3.2) });
    });
    G.byId = {};
    G.nodes.forEach((n) => { G.byId[n.id] = n; });
    G.edges = d.edges.filter(([a, b]) => G.byId[a] && G.byId[b]).map(([a, b]) => [G.byId[a], G.byId[b]]);
    info.textContent = G.nodes.length + " 个主题页 · " + G.edges.length + " 条关系" + (S.g.focus && G.byId[S.g.focus] ? " · 只看「" + G.byId[S.g.focus].title + "」周围" : "");
    $("kbGCard").hidden = true;
    S.g.sel = "";
    sizeCanvas();
    if (!G.nodes.length) { draw(); return; }
    G.ticks = 0;
    G.fit = true;
    startSim();
  }
  function fitView() {                      // 把整张图缩放到正好放得下
    if (!G.nodes.length) return;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    G.nodes.forEach((n) => { x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y); });
    G.sc = Math.max(0.3, Math.min(2.2, (G.w - 140) / Math.max(60, x1 - x0), (G.h - 120) / Math.max(60, y1 - y0)));
    G.ox = -(x0 + x1) / 2; G.oy = -(y0 + y1) / 2;
  }
  function sizeCanvas() {
    const cv = $("kbCanvas"), wrap = $("kbGWrap");
    G.dpr = window.devicePixelRatio || 1;
    G.w = wrap.clientWidth; G.h = wrap.clientHeight;
    cv.width = Math.max(1, G.w * G.dpr); cv.height = Math.max(1, G.h * G.dpr);
    cv.style.width = G.w + "px"; cv.style.height = G.h + "px";
  }
  function startSim() { cancelAnimationFrame(G.raf); G.raf = requestAnimationFrame(step); }
  function stopSim() { cancelAnimationFrame(G.raf); G.raf = 0; }
  function step() {
    const N = G.nodes, alpha = Math.max(0.02, 1 - G.ticks / 260);
    for (let i = 0; i < N.length; i++) {
      const a = N[i];
      for (let j = i + 1; j < N.length; j++) {
        const b = N[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        if (d2 > 250000) continue;
        const f = 2400 / d2, d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
      }
    }
    G.edges.forEach(([a, b]) => {
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 90) * 0.02;
      a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
    });
    N.forEach((n) => {
      n.vx -= n.x * 0.004; n.vy -= n.y * 0.004;
      if (G.drag && G.drag.n === n) { n.vx = n.vy = 0; return; }
      n.x += Math.max(-20, Math.min(20, n.vx * alpha)); n.y += Math.max(-20, Math.min(20, n.vy * alpha));
      n.vx *= 0.55; n.vy *= 0.55;
    });
    G.ticks++;
    if (G.fit && (G.ticks === 60 || G.ticks === 299)) fitView();
    draw();
    if (G.ticks < 300 || G.drag) G.raf = requestAnimationFrame(step); else G.raf = 0;
  }
  const toScreen = (n) => [G.w / 2 + (n.x + G.ox) * G.sc, G.h / 2 + (n.y + G.oy) * G.sc];
  const radius = (n) => n.r * Math.max(0.6, Math.min(1.6, G.sc));
  function draw() {
    const cv = $("kbCanvas"), ctx = cv.getContext("2d");
    const dark = document.body.classList.contains("dark");
    ctx.setTransform(G.dpr, 0, 0, G.dpr, 0, 0);
    ctx.clearRect(0, 0, G.w, G.h);
    if (!G.nodes.length) {
      ctx.fillStyle = dark ? "#aaa" : "#777"; ctx.font = "14px sans-serif"; ctx.textAlign = "center";
      ctx.fillText(S.g.data && S.g.data.nodes && S.g.data.nodes.length ? "这一类没有主题页" : "还没有主题页。先去「原始资料」收录几份资料。", G.w / 2, G.h / 2);
      return;
    }
    const hi = G.hover || (S.g.sel && G.byId[S.g.sel]);
    const near = new Set();
    if (hi) { near.add(hi.id); G.edges.forEach(([a, b]) => { if (a === hi) near.add(b.id); if (b === hi) near.add(a.id); }); }
    G.edges.forEach(([a, b]) => {
      const [x1, y1] = toScreen(a), [x2, y2] = toScreen(b);
      const on = hi && (a === hi || b === hi);
      ctx.strokeStyle = on ? (dark ? "rgba(255,255,255,.7)" : "rgba(40,40,40,.6)") : (dark ? "rgba(255,255,255,.14)" : "rgba(0,0,0,.13)");
      ctx.lineWidth = on ? 1.6 : 1;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    });
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    G.nodes.forEach((n) => {
      const [x, y] = toScreen(n), r = radius(n);
      ctx.globalAlpha = hi && !near.has(n.id) ? 0.25 : 1;
      ctx.fillStyle = TYPE_COLOR[n.type] || "#999";
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      if (n.id === S.g.sel || n.id === S.g.focus) { ctx.strokeStyle = dark ? "#fff" : "#222"; ctx.lineWidth = 2; ctx.stroke(); }
      if (n.deg >= 2 || G.sc > 1.3 || near.has(n.id) || G.nodes.length <= 40) {
        ctx.font = (hi && near.has(n.id) ? "600 " : "") + Math.round(12 * Math.max(0.85, Math.min(1.3, G.sc))) + "px sans-serif";
        ctx.fillStyle = dark ? "#e8e6e1" : "#2b2926";
        ctx.fillText(n.title.length > 12 ? n.title.slice(0, 12) + "…" : n.title, x, y + r + 3);
      }
      ctx.globalAlpha = 1;
    });
  }
  function hitNode(mx, my) {
    for (let i = G.nodes.length - 1; i >= 0; i--) {
      const n = G.nodes[i], [x, y] = toScreen(n), r = radius(n) + 3;
      if ((mx - x) * (mx - x) + (my - y) * (my - y) <= r * r) return n;
    }
    return null;
  }
  function showGCard(n) {
    S.g.sel = n.id;
    const c = $("kbGCard");
    c.hidden = false;
    c.innerHTML = '<div class="kb-pi-h"><b>' + esc(n.title) + '</b><span class="kb-ty t-' + esc(n.type) + '">' + esc(TYPE[n.type] || "其他") + "</span>" +
      '<button type="button" class="kb-x sm" data-act="g-card-close" aria-label="关闭">×</button></div>' +
      '<p class="kb-pi-s">' + esc(n.summary || "") + '</p><p class="kb-dim">' + n.deg + " 条关系 · " + n.n_src + " 份资料</p>" +
      '<div class="kb-g-acts"><button type="button" class="kb-btn sm" data-page="' + esc(n.id) + '">打开这一页</button>' +
      (S.g.focus === n.id ? '<button type="button" class="kb-btn ghost sm" data-act="g-all">看全部</button>' : '<button type="button" class="kb-btn ghost sm" data-gfocus="' + esc(n.id) + '">只看它周围</button>') + "</div>";
    draw();
  }
  function bindGraph() {
    const cv = $("kbCanvas"), tip = $("kbGTip");
    const pos = (e) => { const b = cv.getBoundingClientRect(); return [e.clientX - b.left, e.clientY - b.top]; };
    cv.addEventListener("mousedown", (e) => {
      const [mx, my] = pos(e), n = hitNode(mx, my);
      if (n) { G.drag = { n, moved: false }; if (!G.raf) startSim(); }
      else { G.pan = { x: mx, y: my, ox: G.ox, oy: G.oy, moved: false }; G.fit = false; }
    });
    window.addEventListener("mousemove", (e) => {
      if (S.pane !== "graph" || !root.classList.contains("active")) return;
      const [mx, my] = pos(e);
      if (G.drag) { G.drag.moved = true; G.drag.n.x = (mx - G.w / 2) / G.sc - G.ox; G.drag.n.y = (my - G.h / 2) / G.sc - G.oy; G.ticks = Math.min(G.ticks, 200); draw(); return; }
      if (G.pan) { G.pan.moved = true; G.ox = G.pan.ox + (mx - G.pan.x) / G.sc; G.oy = G.pan.oy + (my - G.pan.y) / G.sc; draw(); return; }
      if (mx < 0 || my < 0 || mx > G.w || my > G.h) { if (G.hover) { G.hover = null; tip.hidden = true; draw(); } return; }
      const n = hitNode(mx, my);
      if (n !== G.hover) { G.hover = n; draw(); }
      cv.style.cursor = n ? "pointer" : "grab";
      if (n) { tip.hidden = false; tip.textContent = n.title + (n.summary ? "：" + n.summary : ""); tip.style.left = Math.max(0, Math.min(G.w - 260, mx + 14)) + "px"; tip.style.top = (my + 14) + "px"; }
      else tip.hidden = true;
    });
    window.addEventListener("mouseup", (e) => {
      if (S.pane !== "graph") return;
      if (G.drag) { const n = G.drag.n, moved = G.drag.moved; G.drag = null; if (!moved) showGCard(n); }
      else if (G.pan) { const moved = G.pan.moved; G.pan = null; if (!moved && e.target === cv) { S.g.sel = ""; $("kbGCard").hidden = true; draw(); } }
    });
    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      G.fit = false;
      const [mx, my] = pos(e), k = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const wx = (mx - G.w / 2) / G.sc - G.ox, wy = (my - G.h / 2) / G.sc - G.oy;
      G.sc = Math.max(0.25, Math.min(4, G.sc * k));
      G.ox = (mx - G.w / 2) / G.sc - wx; G.oy = (my - G.h / 2) / G.sc - wy;
      draw();
    }, { passive: false });
    window.addEventListener("resize", () => { if (S.pane === "graph" && root.classList.contains("active")) { sizeCanvas(); draw(); } });
  }

  // ───────── 整理记录 ─────────
  function logRow(l) {
    if (l.manual) return '<li class="kb-log"><time>' + esc(ago(l.ts)) + "</time><div>" + esc(l.manual) + "</div></li>";
    const ch = (l.changes || []).map((x) => x.act === "rejected"
      ? '<span class="kb-ch rej" title="' + esc(x.why) + '">没采用：' + esc(x.title) + "</span>"
      : '<button type="button" class="kb-ch ' + x.act + '" data-page="' + esc(x.pid) + '">' + (x.act === "new" ? "新建" : "更新") + "「" + esc(x.title) + "」</button>").join("");
    return '<li class="kb-log' + (l.ok ? "" : " bad") + '"><time>' + esc(ago(l.ts)) + "</time><div>" +
      '<p><span class="kb-kind">' + esc(KIND[l.kind] || "") + '</span><button type="button" class="kb-link plain" data-kbraw-go="' + esc(l.sid || "") + '">' + esc(l.title) + "</button></p>" +
      (l.ok ? (l.summary ? '<p class="kb-dim">' + esc(l.summary) + "</p>" : "") + (ch ? '<p class="kb-chs">' + ch + "</p>" : '<p class="kb-dim">这份资料里没有值得记的内容，没改页面。</p>')
        : '<p class="kb-bad" title="' + esc(l.error || "") + '">' + esc((l.error || "没收录成").slice(0, 140)) + "</p>") +
      "</div></li>";
  }
  const sw = (id, on, label, hint, attr) => '<label class="kb-sw-row"><span class="kb-sw"><input type="checkbox" id="' + id + '"' + (attr || "") + (on ? " checked" : "") + '><i></i></span>' +
    "<span><b>" + esc(label) + "</b>" + (hint ? "<small>" + esc(hint) + "</small>" : "") + "</span></label>";
  function renderLog() {
    const o = S.ov, main = $("kbLogMain"), side = $("kbLogSide");
    if (!o || o.ok === false) { main.innerHTML = '<p class="kb-empty">' + esc((o && o.error) || "正在读取…") + "</p>"; side.innerHTML = ""; return; }
    const c = o.config || {}, q = o.queue || [], auto = c.auto || {};
    const qRows = q.map((x) => {
      const st = x.status === "running" ? '<span class="kb-run"><i class="kb-dot"></i>正在收录</span>'
        : x.status === "failed" ? '<span class="kb-bad">没收录成</span>'
        : (x.next_try && x.next_try > o.now ? '<span class="kb-dim">' + Math.max(1, Math.ceil((x.next_try - o.now) / 60)) + " 分钟后再试</span>" : '<span class="kb-dim">排队中</span>');
      return '<li class="kb-q"><span class="kb-kind">' + esc(KIND[x.kind] || "") + '</span><span class="kb-q-t">' + esc(x.title) +
        (x.error ? '<small class="kb-bad" title="' + esc(x.error) + '">' + esc(x.error.length > 90 ? x.error.slice(0, 90) + "…" : x.error) + "</small>" : "") + "</span>" + st +
        '<span class="kb-q-a">' +
          (x.status === "failed" ? '<button type="button" class="kb-link" data-q="retry" data-sid="' + esc(x.sid) + '">再试</button>' : "") +
          (x.status === "pending" ? '<button type="button" class="kb-link" data-q="top" data-sid="' + esc(x.sid) + '">先收这份</button>' : "") +
          (x.status !== "running" ? '<button type="button" class="kb-link dim" data-q="remove" data-sid="' + esc(x.sid) + '">移出</button>' : "") +
        "</span></li>";
    }).join("");
    main.innerHTML =
      '<section class="kb-card"><div class="kb-card-h"><h3>收录队列' + (q.length ? "（" + q.length + "）" : "") + "</h3>" +
        (o.n_failed ? '<button type="button" class="kb-link dim" data-act="clear-failed">清掉没收录成的</button>' : "") + "</div>" +
        (q.length ? '<ul class="kb-qs">' + qRows + "</ul>" : '<p class="kb-empty">队列是空的。要收录资料，去<button type="button" class="kb-link" data-goto="raw">原始资料</button>勾选。</p>') +
      "</section>" +
      '<section class="kb-card"><h3>每份资料改了什么</h3>' + ((o.log || []).length ? '<ul class="kb-logs">' + o.log.map(logRow).join("") + "</ul>" : '<p class="kb-empty">还没有。</p>') + "</section>";
    side.innerHTML =
      '<section class="kb-card"><h3>自动收录</h3><p class="kb-note flat">打开的类型，以后新生成的资料会自动排进队列（以前的要自己去「原始资料」挑）。</p><div class="kb-sets">' +
        AUTO_KINDS.map(([k, n, h]) => sw("kbAuto_" + k, auto[k], n, h, ' data-auto="' + k + '"')).join("") +
      "</div></section>" +
      '<section class="kb-card"><h3>收录</h3><div class="kb-sets">' + sw("kbPaused", c.paused, "暂停收录", "队列留着，不占 AI 池") + "</div>" +
        '<p class="kb-note">收录只用 AI 池，不用本地模型。AI 池这次没写成，资料会留在队列里，过一会儿自动再试，最多试 3 次。</p>' +
        '<p class="kb-note">知识库的文件都在 <button type="button" class="kb-link" data-act="folder">memory/kb 文件夹</button>，是普通的 Markdown，用别的软件也能打开。</p></section>';
  }

  function openPaste() {
    openModal(head("粘贴一段资料", "文章、会议记录、研报摘要都可以。加入队列后和别的资料一样由 AI 池收录。") +
      '<div class="kb-dlg-b"><label class="kb-fl">标题<input class="kb-input" id="kbTxtTitle" maxlength="120" placeholder="比如：某公司 2026 年报要点"></label>' +
      '<label class="kb-fl">原文链接（可以不填）<input class="kb-input" id="kbTxtUrl" maxlength="500" placeholder="https://…"></label>' +
      '<label class="kb-fl">内容<textarea class="kb-input" id="kbTxtBody" rows="12" placeholder="把内容粘贴到这里"></textarea></label></div>' +
      '<div class="kb-dlg-f"><span class="sp"></span><button type="button" class="kb-btn ghost" data-close>取消</button><button type="button" class="kb-btn" data-act="add-text">加入队列</button></div>');
  }

  // ───────── 事件 ─────────
  function bind() {
    bindGraph();
    root.addEventListener("click", async (e) => {
      const t = e.target;
      let b;
      if (t.id === "kbModal") { closeModal(); return; }
      if ((b = t.closest("[data-close]"))) { closeModal(); return; }
      if ((b = t.closest("[data-goto]"))) { goPane(b.dataset.goto); return; }
      if ((b = t.closest("[data-page]"))) {
        if (!$("kbModal").hidden) closeModal();
        openPage(b.dataset.page);
        return;
      }
      if ((b = t.closest("[data-src]"))) { openSource(b.dataset.src); return; }
      if ((b = t.closest("[data-type]"))) { S.type = b.dataset.type; renderTypes(); renderPages(); return; }
      if ((b = t.closest("[data-rk]"))) { S.raw.kind = b.dataset.rk; S.raw.chosen = {}; loadRaw(); return; }
      if ((b = t.closest("[data-rs]"))) { S.raw.status = b.dataset.rs; S.raw.chosen = {}; loadRaw(); return; }
      if ((b = t.closest("[data-rpage]"))) { if (!b.disabled) { S.raw.page = +b.dataset.rpage; loadRaw(true); $("kbScroll").scrollTop = 0; } return; }
      if ((b = t.closest("[data-kbraw]"))) { openRaw(b.dataset.kbraw); return; }
      if ((b = t.closest("[data-kbraw-go]"))) { if (b.dataset.kbrawGo) { goPane("raw"); openRaw(b.dataset.kbrawGo); } return; }
      if ((b = t.closest("[data-gt]"))) { S.g.type = b.dataset.gt; buildGraph(); return; }
      if ((b = t.closest("[data-gfocus]"))) { S.g.focus = b.dataset.gfocus; buildGraph(); return; }
      if ((b = t.closest("[data-hv]"))) { root.querySelectorAll("[data-hv]").forEach((x) => x.classList.toggle("on", x === b)); showHist(b.dataset.hv); return; }
      if ((b = t.closest("[data-restore]"))) {
        const r = await api("/kb/page_action", { id: S.page.meta.id, act: "restore", ts: +b.dataset.restore }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error); return; }
        closeModal(); toast("恢复好了。"); openPage(S.page.meta.id); refresh();
        return;
      }
      if ((b = t.closest("[data-q]"))) {
        const r = await api("/kb/queue", { sid: b.dataset.sid, act: b.dataset.q }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) toast(r.error);
        await refresh();
        if (S.pane === "raw") { loadRaw(true); if (S.raw.sel) openRaw(S.raw.sel); }
        return;
      }
      if (!(b = t.closest("[data-act]")) || b.tagName === "INPUT") return;
      const act = b.dataset.act;
      if (act === "overview") { S.sel = ""; renderPages(); renderOverview(); }
      else if (act === "paste") openPaste();
      else if (act === "ailive") { if (window.cxAiLive) window.cxAiLive.open("kb"); }     // v190
      else if (act === "stop") { const r = await api("/kb/stop", {}).catch(() => ({})); toast(r.ok ? "正在停。停下后收录会先暂停，要继续点「继续收录」。" : (r.error || "没停成")); refresh(); }
      else if (act === "resume") { await api("/kb/config", { paused: false }); refresh(); }
      else if (act === "clear-failed") { await api("/kb/clear_failed", {}); refresh(); }
      else if (act === "folder") { const r = await api("/kb/open_folder", {}).catch((e) => ({ ok: false, error: e.message })); if (!r.ok) toast(r.error || "打不开文件夹"); }
      else if (act === "hist") openHist();
      else if (act === "del") {
        const r = S.page;
        if (!r || !confirm("删除「" + r.meta.title + "」这一页？（删之前会存一份在历史版本里）")) return;
        const x = await api("/kb/page_action", { id: r.meta.id, act: "delete" }).catch((e) => ({ ok: false, error: e.message }));
        if (!x.ok) { toast(x.error); return; }
        toast("删掉了。"); S.sel = ""; await refresh(); renderOverview();
      }
      else if (act === "raw-close") { S.raw.sel = ""; S.raw.item = null; renderRaw(); renderRawPrev(); }
      else if (act === "raw-clear") { S.raw.chosen = {}; renderRaw(); }
      else if (act === "raw-add" || act === "raw-one") {
        const sids = act === "raw-one" ? [S.raw.sel] : Object.keys(S.raw.chosen);
        b.disabled = true;
        const r = await api("/kb/enqueue", { sids: sids }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error); b.disabled = false; return; }
        toast(r.msg);
        if (act === "raw-add") S.raw.chosen = {};
        await refresh(); loadRaw(true); if (S.raw.sel) openRaw(S.raw.sel);
      }
      else if (act === "raw-del") {
        const r = S.raw.item;
        if (!r || !confirm("删除「" + r.title + "」？" + (r.status === "done" ? "\n（已经收录过，主题页里的出处还能点开）" : ""))) return;
        const x = await api("/kb/raw_delete", { sid: r.sid }).catch((e) => ({ ok: false, error: e.message }));
        if (!x.ok) { toast(x.error); return; }
        toast("删掉了。"); S.raw.sel = ""; S.raw.item = null; loadRaw(true);
      }
      else if (act === "g-all") { S.g.focus = ""; buildGraph(); }
      else if (act === "g-card-close") { S.g.sel = ""; $("kbGCard").hidden = true; draw(); }
      else if (act === "add-text") {
        const body = { kind: $("kbTxtUrl").value.trim() ? "news" : "text", title: $("kbTxtTitle").value.trim(), url: $("kbTxtUrl").value.trim(), text: $("kbTxtBody").value };
        if (!body.title) { toast("先写个标题。"); $("kbTxtTitle").focus(); return; }
        const r = await api("/kb/enqueue", body).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error); return; }
        closeModal(); toast(r.msg); refresh(); if (S.pane === "raw") loadRaw(true);
      }
    });
    root.addEventListener("change", async (e) => {
      const t = e.target;
      if (t.matches("[data-rpick]")) { if (t.checked) S.raw.chosen[t.dataset.rpick] = true; else delete S.raw.chosen[t.dataset.rpick]; renderRaw(); }
      else if (t.dataset.act === "raw-all") {
        (S.raw.data.items || []).filter(pickable).forEach((it) => { if (t.checked) S.raw.chosen[it.sid] = true; else delete S.raw.chosen[it.sid]; });
        renderRaw();
      }
      else if (t.matches("[data-auto]") || t.id === "kbPaused") {
        const auto = {};
        root.querySelectorAll("[data-auto]").forEach((x) => { auto[x.dataset.auto] = x.checked; });
        const r = await api("/kb/config", { auto: auto, paused: $("kbPaused").checked }).catch(() => ({}));
        toast(r.ok ? "设置已保存。" : "没存上");
        refresh();
      }
    });
    let qT = null;
    root.addEventListener("input", (e) => {
      const t = e.target;
      if (t.id === "kbQ") {
        clearTimeout(qT);
        qT = setTimeout(async () => {
          S.q = t.value.trim();
          S.hits = null;
          renderPages();
          if (!S.q) return;
          const q = S.q;
          const r = await api("/kb/search?q=" + enc(q)).catch(() => ({ items: [] }));
          if (q !== S.q) return;
          S.hits = r.items || [];
          renderPages();
        }, 250);
      } else if (t.id === "kbRawQ") {
        clearTimeout(qT);
        qT = setTimeout(() => { S.raw.q = t.value.trim(); loadRaw(); }, 300);
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && root.classList.contains("active") && !$("kbModal").hidden) closeModal();
    });
  }

  function load() {
    refresh();
    if (S.pane === "raw") loadRaw(true);
    if (S.pane === "graph") loadGraph();
  }

  window.cxPaneShow = window.cxPaneShow || {};
  window.cxPaneShow.kb = showPane;
  window.loadKb = load;
  window.kbOpenPage = (id) => { openPage(id); };
  try {
    buildShell();
    bind();
    root.dataset.pane = S.pane;
  } catch (e) { /* 出错也不影响软件其它部分 */ }
  const navBtn = document.querySelector('.nav-item[data-view="kb"]');
  if (navBtn) navBtn.addEventListener("click", () => { setTimeout(load, 0); });
})();
