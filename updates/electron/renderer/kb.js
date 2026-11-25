// kb.js —「资料库 → 知识库」（v162 新增）
// AI 当图书管理员：把收进来的资料整理成一页页互相链接的主题页（参照 Karpathy 的「LLM Wiki」）。
// 页面在 #view-kb，顶部标签由 renderer.js 的 NAV_GROUPS.data 画。后端是 backend/kb.py。
(function () {
  "use strict";
  const root = document.getElementById("view-kb");
  if (!root) return;

  const TYPE = { company: "公司", industry: "行业", person: "人物", product: "产品", concept: "概念", event: "事件", other: "其他" };
  const KIND = { note: "视频笔记", report: "研究报告", news: "新闻", text: "粘贴的资料" };
  const backend = () => { try { if (typeof BACKEND === "string" && BACKEND) return BACKEND; } catch (e) {} return "http://127.0.0.1:8756"; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById(id);
  const enc = encodeURIComponent;
  const pad = (n) => (n < 10 ? "0" : "") + n;
  const md = (s) => (typeof renderMarkdown === "function" ? renderMarkdown(s || "") : "<pre>" + esc(s) + "</pre>");
  const api = (path, body) => fetch(backend() + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined)
    .then((r) => r.json());
  const fmtTime = (ts) => { if (!ts) return ""; const d = new Date(ts * 1000); return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + pad(d.getHours()) + ":" + pad(d.getMinutes()); };
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

  const S = {
    ov: null, sel: "", page: null, q: "", type: "all", hits: null, view: "home",
    pick: { kind: "note", q: "", items: null, total: 0, chosen: {} }, src: null, hist: null,
  };

  // ───────── 外框 ─────────
  function buildShell() {
    root.innerHTML =
      '<div class="kb-scroll" id="kbScroll"><div class="kb-wrap">' +
        '<div class="kb-top">' +
          '<div class="kb-top-t"><h2>知识库</h2><p>AI 把你收进来的资料整理成一页页主题页（公司、行业、人物、概念…），页面互相链接，每句话都标着出自哪份资料。资料越多，知识库越完整。</p></div>' +
          '<button type="button" class="kb-btn lg" data-act="pick">收录资料</button>' +
        "</div>" +
        '<div class="kb-status" id="kbStatus" aria-live="polite"></div>' +
        '<div class="kb-cols">' +
          '<aside class="kb-list">' +
            '<input class="kb-input" id="kbQ" type="search" placeholder="在知识库里搜：比如 五粮液、库存" aria-label="搜索知识库">' +
            '<div class="kb-types" id="kbTypes" role="group" aria-label="按类型看"></div>' +
            '<div class="kb-pages" id="kbPages"></div>' +
          "</aside>" +
          '<main class="kb-main" id="kbMain"></main>' +
        "</div>" +
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

  // ───────── 读取 ─────────
  let pollT = null;
  async function refresh() {
    try { S.ov = await api("/kb/overview"); } catch (e) { S.ov = { ok: false, error: "连不上后台：" + e.message }; }
    renderStatus(); renderTypes(); renderPages();
    if (S.view === "home") renderHome();
    clearTimeout(pollT);
    if (root.classList.contains("active")) pollT = setTimeout(refresh, S.ov && S.ov.running ? 3000 : 12000);
  }

  function renderStatus() {
    const el = $("kbStatus"), o = S.ov;
    if (!o) { el.innerHTML = '<span>正在读取…</span>'; return; }
    if (o.ok === false) { el.innerHTML = '<span class="kb-bad">' + esc(o.error) + "</span>"; return; }
    const c = o.config || {};
    const parts = ["<span><b>" + o.pages.length + "</b> 个主题页 · 来自 <b>" + o.n_sources + "</b> 份资料</span>"];
    if (o.running) {
      parts.push('<span class="kb-run"><i class="kb-dot" aria-hidden="true"></i>正在收录「' + esc(o.running.title) + "」：" + esc(o.running.stage || "…") +
        "（" + mmss(o.now - o.running.started) + "）</span>" + '<button type="button" class="kb-link" data-act="stop">停止</button>');
    } else if (c.paused) {
      parts.push('<span class="kb-warn">收录暂停了' + (o.n_pending ? "，队列里还有 " + o.n_pending + " 份" : "") + '</span><button type="button" class="kb-link" data-act="resume">继续收录</button>');
    } else if (o.n_pending) {
      parts.push("<span>队列里还有 " + o.n_pending + " 份等着收录（一份一般 2～5 分钟，AI 池空了就开始）</span>");
    }
    if (o.n_failed) parts.push('<span class="kb-bad">' + o.n_failed + ' 份没收录成</span><button type="button" class="kb-link" data-act="home">看看</button>');
    el.innerHTML = parts.join("");
  }

  function renderTypes() {
    const o = S.ov;
    if (!o || !o.types) return;
    const all = o.pages.length;
    $("kbTypes").innerHTML = [["all", "全部", all]].concat(o.types.filter((t) => t[2])).map(([k, n, c]) =>
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
      el.innerHTML = '<p class="kb-empty">' + (S.q ? "没搜到。" : o.pages.length ? "这一类还没有页面。" : "还没有页面。点右上角「收录资料」开始。") + "</p>";
      return;
    }
    el.innerHTML = list.map((p) =>
      '<button type="button" class="kb-pi' + (p.id === S.sel ? " on" : "") + '" data-page="' + esc(p.id) + '"' + (p.id === S.sel ? ' aria-current="true"' : "") + ">" +
        '<span class="kb-pi-h"><b>' + esc(p.title) + '</b><span class="kb-ty t-' + esc(p.type) + '">' + esc(TYPE[p.type] || "其他") + "</span></span>" +
        '<span class="kb-pi-s">' + esc(p.snip || p.summary || "") + "</span>" +
        '<span class="kb-pi-m">' + (p.n_src ? p.n_src + " 份资料 · " : "") + ago(p.updated) + "更新</span>" +
      "</button>").join("");
  }

  // ───────── 首页：队列 + 最近的变化 ─────────
  function renderHome() {
    S.view = "home";
    const el = $("kbMain"), o = S.ov;
    if (!o) { el.innerHTML = '<p class="kb-empty">正在读取…</p>'; return; }
    if (o.ok === false) { el.innerHTML = '<p class="kb-empty">' + esc(o.error) + "</p>"; return; }
    const c = o.config || {};
    const q = o.queue || [];
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
    const logs = (o.log || []).map((l) => {
      if (l.manual) return '<li class="kb-log"><time>' + esc(ago(l.ts)) + "</time><div>" + esc(l.manual) + "</div></li>";
      const ch = (l.changes || []).map((x) => x.act === "rejected"
        ? '<span class="kb-ch rej" title="' + esc(x.why) + '">没采用：' + esc(x.title) + "</span>"
        : '<button type="button" class="kb-ch ' + x.act + '" data-page="' + esc(x.pid) + '">' + (x.act === "new" ? "新建" : "更新") + "「" + esc(x.title) + "」</button>").join("");
      return '<li class="kb-log' + (l.ok ? "" : " bad") + '"><time>' + esc(ago(l.ts)) + "</time><div>" +
        '<p><span class="kb-kind">' + esc(KIND[l.kind] || "") + "</span>" + esc(l.title) + "</p>" +
        (l.ok ? (l.summary ? '<p class="kb-dim">' + esc(l.summary) + "</p>" : "") + (ch ? '<p class="kb-chs">' + ch + "</p>" : '<p class="kb-dim">这份资料里没有值得记的内容，没改页面。</p>')
          : '<p class="kb-bad" title="' + esc(l.error || "") + '">' + esc((l.error || "没收录成").slice(0, 140)) + "</p>") +
        "</div></li>";
    }).join("");
    el.innerHTML =
      (o.pages.length ? "" :
        '<section class="kb-card kb-intro"><h3>怎么用</h3><ol>' +
          "<li>点右上角<b>「收录资料」</b>，挑几份视频笔记或研究报告；在「商业 → 市场雷达」看新闻时，也可以点「收进知识库」。</li>" +
          "<li>资料排进队列，AI 池空了就一份一份收录：读资料，再新建或更新相关的主题页。一份一般 2～5 分钟。</li>" +
          "<li>页面里每句话后面都有<b>〔S数字〕</b>，点一下能看到它出自哪份资料；<b>[[蓝色名字]]</b>可以跳到别的页面。</li>" +
          "<li>以后新分析好的视频笔记、新写的研究报告会自动收录（下面可以关）。</li>" +
        "</ol></section>") +
      '<section class="kb-card"><div class="kb-card-h"><h3>收录队列</h3>' +
        (o.n_failed ? '<button type="button" class="kb-link dim" data-act="clear-failed">清掉没收录成的</button>' : "") + "</div>" +
        (q.length ? '<ul class="kb-qs">' + qRows + "</ul>" : '<p class="kb-empty">队列是空的。</p>') +
        '<div class="kb-sets">' +
          sw("kbAutoNotes", c.auto_notes, "新的视频笔记分析好以后，自动收录") +
          sw("kbAutoReports", c.auto_reports, "新写好的研究报告，自动收录") +
          sw("kbPaused", c.paused, "暂停收录（队列留着，不占 AI 池）") +
        "</div>" +
        '<p class="kb-note">收录只用 AI 池，不用本地模型。AI 池这次没写成，资料会留在队列里，过一会儿自动再试，最多试 3 次。' +
          '知识库的文件都在 <button type="button" class="kb-link" data-act="folder">memory/kb 文件夹</button>，是普通的 Markdown，用别的软件也能打开。</p>' +
      "</section>" +
      '<section class="kb-card"><h3>最近的变化</h3>' + (logs ? '<ul class="kb-logs">' + logs + "</ul>" : '<p class="kb-empty">还没有。</p>') + "</section>";
  }
  const sw = (id, on, label) => '<label class="kb-sw-row"><span class="kb-sw"><input type="checkbox" id="' + id + '"' + (on ? " checked" : "") + '><i></i></span>' + esc(label) + "</label>";

  // ───────── 一个主题页 ─────────
  async function openPage(id, push) {
    S.sel = id;
    S.view = "page";
    renderPages();
    const el = $("kbMain");
    el.innerHTML = '<p class="kb-empty">正在打开…</p>';
    let r;
    try { r = await api("/kb/page?id=" + enc(id)); } catch (e) { r = { ok: false, error: e.message }; }
    if (S.sel !== id) return;
    S.page = r;
    if (!r.ok) { el.innerHTML = '<p class="kb-empty">' + esc(r.error) + '</p><button type="button" class="kb-link" data-act="home">回到首页</button>'; return; }
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
        '<div class="kb-page-bar"><button type="button" class="kb-link" data-act="home">‹ 知识库首页</button><span class="sp"></span>' +
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
  function closeModal() { $("kbModal").hidden = true; S.src = null; S.hist = null; }
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
  function openPick() {
    S.pick = { kind: S.pick.kind || "note", q: "", items: null, total: 0, chosen: {} };
    renderPick();
    if (S.pick.kind !== "text") loadPick();
  }
  async function loadPick() {
    const p = S.pick;
    p.items = null;
    renderPickList();
    let r;
    try { r = await api("/kb/candidates?kind=" + p.kind + "&q=" + enc(p.q) + "&limit=300"); } catch (e) { r = { ok: false, items: [] }; }
    if (r.kind !== p.kind) return;
    p.items = r.items || [];
    p.total = r.total || 0;
    renderPickList();
  }
  function renderPick() {
    const p = S.pick;
    const tabs = [["note", "视频笔记"], ["report", "研究报告"], ["text", "粘贴文字"]];
    openModal(head("收录资料", "选好的资料会排进队列，AI 池空了就一份一份收录。每份用一次 AI 池，一般 2～5 分钟。") +
      '<div class="kb-tabs" role="tablist">' + tabs.map(([k, t]) => '<button type="button" role="tab" data-pk="' + k + '" aria-selected="' + (p.kind === k) + '">' + t + "</button>").join("") + "</div>" +
      '<div class="kb-dlg-b" id="kbPickB"></div>' +
      '<div class="kb-dlg-f" id="kbPickF"></div>');
    renderPickList();
  }
  function renderPickList() {
    const p = S.pick, b = $("kbPickB"), f = $("kbPickF");
    if (!b) return;
    if (p.kind === "text") {
      b.innerHTML = '<label class="kb-fl">标题<input class="kb-input" id="kbTxtTitle" maxlength="120" placeholder="比如：某公司 2026 年报要点"></label>' +
        '<label class="kb-fl">原文链接（可以不填）<input class="kb-input" id="kbTxtUrl" maxlength="500" placeholder="https://…"></label>' +
        '<label class="kb-fl">内容<textarea class="kb-input" id="kbTxtBody" rows="12" placeholder="把文章、会议记录、研报摘要等粘贴到这里"></textarea></label>';
      f.innerHTML = '<span class="sp"></span><button type="button" class="kb-btn ghost" data-close>取消</button><button type="button" class="kb-btn" data-act="add-text">加入队列</button>';
      return;
    }
    const n = Object.keys(p.chosen).length;
    let list;
    if (!p.items) list = '<p class="kb-empty">正在读取…</p>';
    else if (!p.items.length) list = '<p class="kb-empty">' + (p.q ? "没找到。" : "没有还没收录的" + (p.kind === "note" ? "视频笔记" : "研究报告") + "。") + "</p>";
    else list = '<ul class="kb-picks">' + p.items.map((x) =>
      '<li><label><input type="checkbox" data-pick="' + esc(x.sid) + '"' + (p.chosen[x.sid] ? " checked" : "") + ">" +
      '<span class="kb-pk-t">' + esc(x.title) + "</span>" +
      '<span class="kb-dim">' + esc(x.who || "") + (x.who ? " · " : "") + esc(fmtTime(x.ts)) + "</span></label></li>").join("") + "</ul>";
    b.innerHTML = '<div class="kb-pick-bar"><input class="kb-input" id="kbPickQ" type="search" value="' + esc(p.q) + '" placeholder="按标题、作者找" aria-label="找资料">' +
      (p.items && p.items.length ? '<button type="button" class="kb-link" data-act="pick-all">全选这一页（' + p.items.length + "）</button>" : "") + "</div>" +
      (p.items ? '<p class="kb-dim">还没收录的一共 ' + p.total + " 份" + (p.total > p.items.length ? "，这里列出最新的 " + p.items.length + " 份，可以搜" : "") + "。</p>" : "") + list;
    const mins = n * 3.5;
    f.innerHTML = '<span class="kb-dim">' + (n ? "选了 " + n + " 份，大约要 " + (mins >= 60 ? (mins / 60).toFixed(1) + " 小时" : Math.round(mins) + " 分钟") + "（一份一份来，不用守着）" : "勾选要收录的资料") + "</span>" +
      '<span class="sp"></span><button type="button" class="kb-btn ghost" data-close>取消</button>' +
      '<button type="button" class="kb-btn" data-act="add-picked"' + (n ? "" : " disabled") + ">加入队列" + (n ? "（" + n + "）" : "") + "</button>";
  }

  // ───────── 事件 ─────────
  function bind() {
    root.addEventListener("click", async (e) => {
      const t = e.target;
      let b;
      if (t.id === "kbModal") { closeModal(); return; }
      if ((b = t.closest("[data-close]"))) { closeModal(); return; }
      if ((b = t.closest("[data-page]"))) {
        if (b.hasAttribute("data-close-after")) closeModal();
        openPage(b.dataset.page);
        return;
      }
      if ((b = t.closest("[data-src]"))) { openSource(b.dataset.src); return; }
      if ((b = t.closest("[data-type]"))) { S.type = b.dataset.type; renderTypes(); renderPages(); return; }
      if ((b = t.closest("[data-pk]"))) { S.pick.kind = b.dataset.pk; S.pick.q = ""; S.pick.chosen = {}; renderPick(); if (S.pick.kind !== "text") loadPick(); return; }
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
        refresh();
        return;
      }
      if (!(b = t.closest("[data-act]"))) return;
      const act = b.dataset.act;
      if (act === "home") { S.sel = ""; renderPages(); renderHome(); }
      else if (act === "pick") openPick();
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
        toast("删掉了。"); S.sel = ""; await refresh(); renderHome();
      }
      else if (act === "pick-all") { (S.pick.items || []).forEach((x) => { S.pick.chosen[x.sid] = true; }); renderPickList(); }
      else if (act === "add-picked") {
        const sids = Object.keys(S.pick.chosen);
        b.disabled = true;
        const r = await api("/kb/enqueue", { sids: sids }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error); b.disabled = false; return; }
        closeModal(); toast(r.msg); S.view = "home"; S.sel = ""; refresh();
      }
      else if (act === "add-text") {
        const body = { kind: $("kbTxtUrl").value.trim() ? "news" : "text", title: $("kbTxtTitle").value.trim(), url: $("kbTxtUrl").value.trim(), text: $("kbTxtBody").value };
        if (!body.title) { toast("先写个标题。"); $("kbTxtTitle").focus(); return; }
        const r = await api("/kb/enqueue", body).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error); return; }
        closeModal(); toast(r.msg); S.view = "home"; S.sel = ""; refresh();
      }
    });
    root.addEventListener("change", async (e) => {
      const t = e.target;
      if (t.matches("[data-pick]")) { if (t.checked) S.pick.chosen[t.dataset.pick] = true; else delete S.pick.chosen[t.dataset.pick]; renderPickList(); }
      else if (t.id === "kbAutoNotes" || t.id === "kbAutoReports" || t.id === "kbPaused") {
        const r = await api("/kb/config", { auto_notes: $("kbAutoNotes").checked, auto_reports: $("kbAutoReports").checked, paused: $("kbPaused").checked }).catch(() => ({}));
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
      } else if (t.id === "kbPickQ") {
        clearTimeout(qT);
        qT = setTimeout(() => { S.pick.q = t.value.trim(); loadPick(); }, 300);
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && root.classList.contains("active") && !$("kbModal").hidden) closeModal();
    });
  }

  function load() { refresh(); }

  window.loadKb = load;
  window.kbOpenPage = (id) => { openPage(id); };
  try {
    buildShell();
    bind();
  } catch (e) { /* 出错也不影响软件其它部分 */ }
  const navBtn = document.querySelector('.nav-item[data-view="kb"]');
  if (navBtn) navBtn.addEventListener("click", () => { setTimeout(load, 0); });
})();
