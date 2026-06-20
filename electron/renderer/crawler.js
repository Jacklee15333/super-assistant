// ============================================================
// crawler.js —「🔍 洞察与研究」（「懂你」下的子页，和画像/演化同一级）
// 逐篇深读成长库：爬虫定位文件 → AI 一篇篇通读 → 形成学习数据 → 汇总 → 可主动上网研究。
// 带进度（总数/已读）、研究详情（已读/待读/跳过三张清单 + 每篇理解 + 主动研究成果）、
// 实时活动、断点续传（重启接着跑）。
// 作为「懂你」子页运行：自己处理 #lumiSubNav 里 data-lumi="insight" 的显隐，
// 不依赖修改 renderer.js。复用全局：BACKEND / renderMarkdown / escapeHtml / settings()
// ============================================================

(function () {
  let _crwData = null;
  let _crwPoll = null;
  let _crwTab = "summary";    // summary（看懂你） | detail（研究详情） | settings（设置）
  let _expandedResearch = {}; // name -> content（点开的研究文档）
  let _ovDetail = null;       // 详情浮层：null | {filter:"all"|"read"|"unread", data, expanded:{}}

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return (typeof escapeHtml === "function")
      ? escapeHtml(s)
      : String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }
  function md(s) {
    return (typeof renderMarkdown === "function") ? renderMarkdown(s || "") : esc(s);
  }
  function setStatus(msg, kind) {
    const el = $("crwStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.className = "crw-status" + (kind ? " " + kind : "");
  }

  // ---------- 子页显隐（处理 data-lumi="insight"）----------
  const OTHER_LUMI_PAGES = ["lumiPageProfile", "lumiPageRelations", "lumiPageEnv", "lumiPageEvolution"];
  function showInsightPage() {
    OTHER_LUMI_PAGES.forEach((id) => { const e = $(id); if (e) e.style.display = "none"; });
    const p = $("lumiPageInsight");
    if (p) p.style.display = "";
    // 顶栏「立即分析」按钮的显隐由 renderer.js 的 setLumiTopbarButtons 统一管理
  }
  function hideInsightPage() {
    const p = $("lumiPageInsight");
    if (p) p.style.display = "none";
  }

  // ---------- 拉状态 ----------
  async function loadCrawler() {
    const body = $("crwBody");
    if (!body) return;
    if (!_crwData) body.innerHTML = '<div class="crw-runs-empty">加载中…</div>';
    try {
      const r = await fetch(BACKEND + "/insight/status");
      const d = await r.json();
      if (!d || !d.ok) { body.innerHTML = '<div class="crw-runs-empty">读取失败</div>'; return; }
      _crwData = d;
      render();
      const p = d.progress || {};
      if (p.active) startPoll(); else stopPoll();
    } catch (e) {
      body.innerHTML = '<div class="crw-runs-empty">后端没连上：' + esc(e.message) + "</div>";
    }
  }

  // ---------- 渲染 ----------
  function render() {
    const d = _crwData || {};
    const prog = d.progress || {};
    const running = !!prog.active;
    const stoppedResumable = (prog.phase === "stopped" && (prog.remaining || 0) > 0);

    let html = overviewHtml(d);
    html += tabsHtml(d);

    if (_crwTab === "detail") {
      html += '<div class="crw-tab-intro">这里是<b>过程明细</b>：分析进行到哪了、每篇文件读了没、AI 从每篇读出了什么、以及主动上网研究的成果。想知道「它到底在干什么」就看这页。</div>';
      // 运行中 / 可续跑：先显示进度面板
      if (running || stoppedResumable) html += progressHtml(d);
      html += detailHtml(d);      // 文件清单 + 每篇理解 + 主动研究（合并）
    } else if (_crwTab === "settings") {
      html += '<div class="crw-tab-intro">在这里设定<b>多久自动分析一次、爬哪些内容、用哪个模型</b>，以及要不要让它分析完主动上网研究。下面还有历史运行记录。</div>';
      html += settingsHtml(d);
    } else {
      // summary（看懂你）：最该先看到的「成果」
      html += '<div class="crw-tab-intro">小助逐篇精读你的成长库后，<b>对「你」的整体理解</b>就在下面。' +
        '点右上角「<b>立即分析</b>」会让它把成长库里<b>还没读的文章逐篇通读一遍</b>、再汇总更新这份理解。' +
        '想看读了哪些、怎么总结的，去「研究详情」或点上面的数字；想调参数去「设置」。</div>';
      if (running || stoppedResumable) {
        // 正在跑：给个轻量提示条引导去详情页看进度
        html += '<div class="crw-running-tip">⏳ 正在分析中…想看实时进度，点上面「研究详情」。</div>';
      }
      html += summaryHtml(d);
    }

    if (_ovDetail) html += ovDetailHtml();

    $("crwBody").innerHTML = html;
    bind(d);

    const runBtn = $("crwRunBtn");
    if (runBtn) {
      runBtn.disabled = running;
      runBtn.classList.toggle("running", running);
    }
    const log = $("crwActivity");
    if (log) log.scrollTop = log.scrollHeight;
  }

  function overviewHtml(d) {
    const okRuns = (d.runs || []).filter((x) => x.ok).length;
    return '<div class="crw-overview">' +
      '<div><div class="crw-ov-title">爬你自己的成长库，让小助真的懂你</div>' +
      '<div class="crw-ov-sub">把你的视频笔记、情报、对话等逐个找出来，让 AI <b>一篇篇通读</b>、' +
      '汇总成对你的理解并注入小助；还能<b>主动上网</b>替你搜相关内容存进成长库，越用越懂你。' +
      '<br><span class="crw-ov-run-hint">▶ 右上角「立即分析」= 把成长库里<b>没读过的文章逐篇读一遍</b> → 更新对你的理解（也是人格演化的底料）。</span></div></div>' +
      '<div class="crw-ov-stats">' +
        '<button class="crw-ov-stat crw-ov-clickable" data-ovdetail="all" title="点开看是哪些文章">' +
          '<div class="crw-ov-num">' + (d.total_available || 0) + '</div>' +
          '<div class="crw-ov-label">可分析篇数 ›</div></button>' +
        '<button class="crw-ov-stat crw-ov-clickable" data-ovdetail="read" title="点开看读了哪些、怎么总结的">' +
          '<div class="crw-ov-num">' + (d.learned_total || 0) + '</div>' +
          '<div class="crw-ov-label">已深读篇数 ›</div></button>' +
        '<div class="crw-ov-stat"><div class="crw-ov-num">' + okRuns + '</div><div class="crw-ov-label">汇总次数</div></div>' +
      '</div></div>';
  }

  // —— 「可分析/已深读」点开后的详情浮层 ——
  function ovDetailHtml() {
    const ov = _ovDetail || {};
    const data = ov.data;
    const filter = ov.filter || "all";
    let body;
    if (!data) {
      body = '<div class="crw-runs-empty">加载中…</div>';
    } else {
      let items = data.items || [];
      if (filter === "read") items = items.filter((x) => x.read);
      else if (filter === "unread") items = items.filter((x) => !x.read);

      // 顶部小计
      let head = '<div class="ovd-summary">' +
        '<span class="ovd-sum-item">共 <b>' + (data.total || 0) + '</b> 篇可分析</span>' +
        '<span class="ovd-sum-item ovd-read">已读 <b>' + (data.read || 0) + '</b></span>' +
        '<span class="ovd-sum-item ovd-unread">未读 <b>' + (data.unread || 0) + '</b></span>' +
        '</div>';
      // 来源分布
      if ((data.by_scope || []).length) {
        head += '<div class="ovd-scopes">';
        data.by_scope.forEach((s) => {
          head += '<span class="ovd-scope-chip">' + esc(s.label) + ' ' +
            s.read + '/' + s.total + '</span>';
        });
        head += '</div>';
      }
      // 过滤切换
      const fbtn = (key, label) => '<button class="ovd-fbtn' + (filter === key ? ' active' : '') +
        '" data-ovfilter="' + key + '">' + label + '</button>';
      head += '<div class="ovd-filters">' +
        fbtn("all", "全部 " + (data.total || 0)) +
        fbtn("read", "✅ 已读 " + (data.read || 0)) +
        fbtn("unread", "⬜ 未读 " + (data.unread || 0)) + '</div>';

      // 列表
      let list = '';
      if (!items.length) {
        list = '<div class="crw-runs-empty">这个筛选下没有文章。</div>';
      } else {
        list = '<div class="ovd-list">';
        items.forEach((it) => {
          const expanded = ov.expanded && ov.expanded[it.name];
          const flag = it.read
            ? '<span class="ovd-flag ovd-flag-read">✅ 已读</span>'
            : '<span class="ovd-flag ovd-flag-unread">⬜ 未读</span>';
          const changed = it.changed ? '<span class="ovd-flag ovd-flag-changed">↻ 已改动·将重读</span>' : '';
          const canExpand = it.read && it.digest;
          list += '<div class="ovd-row' + (expanded ? ' open' : '') + '">' +
            '<div class="ovd-row-head"' + (canExpand ? ' data-ovrow="' + esc(it.name) + '"' : '') + '>' +
              '<span class="ovd-row-title">' + esc(it.title || it.name) + '</span>' +
              '<span class="ovd-row-tags">' +
                '<span class="ovd-scope-tag">' + esc(it.label) + '</span>' + flag + changed +
                (canExpand ? '<span class="ovd-row-toggle">' + (expanded ? "收起 ▲" : "看总结 ▼") + '</span>' : '') +
              '</span>' +
            '</div>';
          if (canExpand && expanded) {
            list += '<div class="ovd-row-body">' + md(it.digest) +
              (it.read_at ? '<div class="crw-digest-at">读于 ' + esc(it.read_at) + '</div>' : '') + '</div>';
          } else if (!it.read) {
            list += '<div class="ovd-row-body ovd-unread-hint">这篇还没读。点上方「立即分析」会把未读的逐篇读一遍。</div>';
          }
          list += '</div>';
        });
        list += '</div>';
      }
      body = head + list;
    }

    return '<div class="ovd-overlay" id="ovdOverlay">' +
      '<div class="ovd-card">' +
        '<div class="ovd-card-head">' +
          '<span class="ovd-card-title">📄 可分析文章明细（哪些读了 · 怎么总结的 · 还剩哪些）</span>' +
          '<button class="ddb-icon-btn" id="ovdClose" title="关闭">✕</button>' +
        '</div>' +
        '<div class="ovd-card-body">' + body + '</div>' +
      '</div></div>';
  }

  async function openOvDetail(filter) {
    _ovDetail = { filter: filter === "read" ? "read" : "all", data: null, expanded: {} };
    render();
    try {
      const r = await fetch(BACKEND + "/insight/analyzable");
      const d = await r.json();
      _ovDetail.data = (d && d.ok) ? d : { total: 0, read: 0, unread: 0, items: [], by_scope: [] };
    } catch (e) {
      _ovDetail.data = { total: 0, read: 0, unread: 0, items: [], by_scope: [] };
    }
    render();
  }

  // —— 顶部标签：3 步流程（看懂你 → 研究详情 → 设置）——
  function tabsHtml(d) {
    const prog = d.progress || {};
    const dot = prog.active ? ' <span class="crw-tab-dot"></span>' : '';
    const tab = (key, label, num) =>
      '<button class="crw-tab' + (_crwTab === key ? ' active' : '') + '" data-crwtab="' + key + '">' +
      '<span class="crw-tab-num">' + num + '</span>' + label + '</button>';
    return '<div class="crw-tabs">' +
      tab("summary", "看懂你", "①") +
      tab("detail", "研究详情" + dot, "②") +
      tab("settings", "设置", "③") +
      '</div>';
  }

  // —— ① 看懂你：最近的洞察报告（成果）——
  function summaryHtml(d) {
    const report = (d.latest_report || "").trim();
    if (!report) {
      return '<div class="crw-panel"><div class="crw-empty-big">' +
        '<div class="crw-empty-icon">🔍</div>' +
        '<div class="crw-empty-title">还没有对你的理解</div>' +
        '<div class="crw-empty-sub">点右上角「立即分析」，小助会逐篇精读你的成长库，' +
        '几分钟后这里就会出现「你是个什么样的人、最近在关注什么」。</div>' +
        '</div></div>';
    }
    return '<div class="crw-report crw-report-solo">' +
      '<div class="crw-report-head"><span>🧠</span><span class="crw-report-title">小助对你的理解</span></div>' +
      '<div class="crw-report-body">' + md(d.latest_report) + '</div></div>';
  }

  // —— 进度面板（运行中 / 可续跑）——
  function progressHtml(d) {
    const p = d.progress || {};
    const phase = p.phase;
    const percent = p.percent || 0;
    let title, sub;
    if (phase === "synthesizing") {
      title = "🧩 正在汇总成对你的理解…";
      sub = "已读完，正把每篇的学习数据汇总成画像，马上好。";
    } else if (phase === "researching") {
      title = "🌐 正在主动上网研究…";
      sub = "根据刚汇总出的画像，替你搜相关内容并存进成长库（下次洞察会读到）。";
    } else if (phase === "stopped") {
      title = "⏸ 已暂停（进度已保存）";
      sub = "上次读到一半。点「继续」接着读，关软件再开也不会丢进度。";
    } else {
      title = "📖 正在逐篇深读你的成长库…";
      sub = "爬虫逐篇定位文件 → 派给 AI 通读 → 形成学习数据。可随时停止，进度会保存。";
    }
    const cur = p.current;
    let curLine = "";
    if (cur) {
      curLine = '<div class="crw-cur">📂 当前：' +
        (cur.index ? '第 ' + esc(cur.index) + ' 篇 ·' : '') + '《' +
        esc(cur.name) + '》<span class="crw-cur-scope">' + esc(cur.scope) + '</span></div>';
    }
    let html = '<div class="crw-panel crw-progress">' +
      '<div class="crw-panel-head"><span>⏳</span><span class="crw-panel-title">' + title + '</span></div>' +
      '<div class="crw-panel-hint">' + sub + '</div>' +
      '<div class="crw-bar"><div class="crw-bar-fill" style="width:' + percent + '%"></div></div>' +
      '<div class="crw-bar-meta"><span>已读 <b>' + (p.done || 0) + '</b> / ' + (p.total || 0) +
        ' 篇（' + percent + '%）</span>' +
        (p.learned ? '<span>本轮新学 ' + p.learned + ' 篇</span>' : '') + '</div>' +
      curLine;

    html += '<div class="crw-act-title">实时活动</div><div class="crw-activity" id="crwActivity">';
    const act = p.activity || [];
    if (!act.length) html += '<div class="crw-act-line dim">准备中…</div>';
    else act.forEach((line) => { html += '<div class="crw-act-line">' + esc(line) + '</div>'; });
    html += '</div>';

    html += '<div class="crw-save-row" style="margin-top:14px">';
    if (phase === "stopped") {
      html += '<button class="crw-save-btn" id="crwResumeBtn">▶ 继续读</button>';
    } else {
      html += '<button class="crw-ghost-btn" id="crwStopBtn">⏸ 停止（保存进度）</button>';
    }
    html += '<span class="crw-save-hint">停止后进度会保存，下次点「立即分析」接着读。</span>';
    html += '</div></div>';
    return html;
  }

  // —— 研究详情页（本轮概况 / 当前在做 / 三张文件清单 / 本轮主动研究）——
  function detailHtml(d) {
    const p = d.progress || {};
    const labels = d.scope_labels || {};
    const phaseText = {
      idle: "空闲", reading: "正在逐篇精读", synthesizing: "正在汇总画像",
      researching: "正在主动上网研究", done: "已完成", stopped: "已暂停", error: "出错",
    }[p.phase] || p.phase || "—";

    // 本轮概况
    let html = '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>📋</span><span class="crw-panel-title">本轮研究概况</span></div>' +
      '<div class="crw-detail-meta">' +
        metaItem("何时开始", p.started_at || "—") +
        metaItem("来源", p.source === "auto" ? "定时自动" : (p.source === "manual" ? "手动触发" : (p.source || "—"))) +
        metaItem("当前状态", phaseText) +
        metaItem("共多少篇", (p.total || 0) + " 篇") +
        metaItem("已读", (p.done || 0) + " 篇") +
        metaItem("本轮新学", (p.learned || 0) + " 篇") +
        (p.finished_at ? metaItem("完成于", p.finished_at) : "") +
      '</div>';

    // 爬了什么（本轮范围）
    const scopes = p.scopes || {};
    const scopeChips = Object.keys(scopes).filter((k) => scopes[k])
      .map((k) => '<span class="crw-chip">' + esc(labels[k] || k) + '</span>').join("");
    if (scopeChips) html += '<div class="crw-detail-sub">爬取范围：' + scopeChips + '</div>';
    html += '</div>';

    // 当前正在做什么（实时）
    const cur = p.current;
    html += '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>🎯</span><span class="crw-panel-title">当前正在做什么</span></div>';
    if (p.active && cur) {
      html += '<div class="crw-cur">📂 ' +
        (cur.index ? '第 ' + esc(cur.index) + ' 篇 ·' : '') + '《' + esc(cur.name) + '》' +
        '<span class="crw-cur-scope">' + esc(cur.scope) + '</span></div>';
    } else if (p.active) {
      html += '<div class="crw-detail-idle">' + esc(phaseText) + '…</div>';
    } else {
      html += '<div class="crw-detail-idle">现在空闲，没有正在进行的任务。点右上角「立即分析」开始。</div>';
    }
    const act = (p.activity || []).slice(-12);
    if (act.length) {
      html += '<div class="crw-act-title" style="margin-top:12px">最近动作</div>' +
        '<div class="crw-activity" id="crwActivity">' +
        act.map((l) => '<div class="crw-act-line">' + esc(l) + '</div>').join("") + '</div>';
    }
    html += '</div>';

    // 三张文件清单：已读 / 待读 / 跳过
    const readF = p.read_files || [];
    const pendF = p.pending_files || [];
    const skipF = p.skipped_files || [];
    html += '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>🗂️</span><span class="crw-panel-title">文件清单（哪些已读 · 还剩哪些 · 跳过了哪些）</span></div>' +
      '<div class="crw-lists">';

    html += '<div class="crw-list-col"><div class="crw-list-h crw-list-h-ok">✅ 已读 (' + readF.length + ')</div>';
    if (!readF.length) html += '<div class="crw-list-empty">还没读到</div>';
    else html += readF.slice().reverse().map((f) =>
      '<div class="crw-file-row"><span class="crw-file-name">' + esc(f.name) + '</span>' +
      '<span class="crw-file-meta">' + esc(f.label || f.scope || "") +
      (f.chars ? ' · ' + f.chars + ' 字' : '') + (f.at ? ' · ' + esc(f.at) : '') + '</span></div>').join("");
    html += '</div>';

    html += '<div class="crw-list-col"><div class="crw-list-h crw-list-h-wait">⏳ 还剩 (' + pendF.length + ')</div>';
    if (!pendF.length) html += '<div class="crw-list-empty">没有待读的了</div>';
    else html += pendF.slice(0, 60).map((f) =>
      '<div class="crw-file-row"><span class="crw-file-name">' + esc(f.name) + '</span>' +
      '<span class="crw-file-meta">' + esc(f.label || f.scope || "") + '</span></div>').join("") +
      (pendF.length > 60 ? '<div class="crw-list-empty">…还有 ' + (pendF.length - 60) + ' 篇</div>' : "");
    html += '</div>';

    html += '<div class="crw-list-col"><div class="crw-list-h crw-list-h-skip">⏭ 跳过 (' + skipF.length + ')</div>';
    if (!skipF.length) html += '<div class="crw-list-empty">没有跳过的</div>';
    else html += skipF.slice().reverse().map((f) =>
      '<div class="crw-file-row"><span class="crw-file-name">' + esc(f.name) + '</span>' +
      '<span class="crw-file-meta">' + esc(f.reason || "") + '</span></div>').join("");
    html += '</div>';

    html += '</div></div>'; // /lists /panel

    // 本轮主动研究
    const research = p.research || [];
    if (p.auto_research || research.length) {
      html += '<div class="crw-panel">' +
        '<div class="crw-panel-head"><span>🌐</span><span class="crw-panel-title">本轮主动研究</span></div>';
      if (!research.length) {
        html += '<div class="crw-detail-idle">本轮还没开始主动研究（汇总完成后才会进行）。</div>';
      } else {
        html += '<div class="crw-research-list">';
        research.forEach((r) => {
          const st = { searching: "搜索中…", saved: "已存库", empty: "没搜到", failed: "失败" }[r.status] || r.status;
          const cls = r.status === "saved" ? "ok" : (r.status === "searching" ? "" : "fail");
          html += '<div class="crw-research-row"><span class="crw-research-badge ' + cls + '"></span>' +
            '<div class="crw-research-main"><div class="crw-research-topic">' + esc(r.topic) +
            ' <span class="crw-research-st">' + esc(st) + '</span></div>' +
            (r.sources && r.sources.length
              ? '<div class="crw-research-srcs">' + r.sources.map((s) =>
                  '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.title || s.url) + '</a>').join(" · ") + '</div>'
              : '') +
            '</div></div>';
        });
        html += '</div>';
      }
      html += '</div>';
    }

    // —— 每篇读出来的理解（合并自原「每篇理解」tab）——
    const digests = d.digests || [];
    html += '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>📖</span><span class="crw-panel-title">每篇读出来的理解（共 ' + digests.length + ' 篇）</span></div>' +
      '<div class="crw-panel-hint">每篇文件被 AI 通读后提炼的要点：讲了什么、反映你关注/在意什么。新 → 旧。</div>';
    if (!digests.length) {
      html += '<div class="crw-runs-empty">还没有精读结果。点右上角「立即分析」让它逐篇读一遍。</div>';
    } else {
      html += '<div class="crw-digests">';
      digests.forEach((it, i) => {
        html += '<div class="crw-digest' + (i === 0 ? '' : ' collapsed') + '">' +
          '<div class="crw-digest-head">' +
            '<span class="crw-digest-title">' + esc(it.title || "（无题）") +
              '<span class="crw-digest-scope">' + esc(it.label || it.scope || "") + '</span></span>' +
            '<span class="crw-digest-toggle">' + (i === 0 ? "收起 ▲" : "展开 ▼") + '</span>' +
          '</div>' +
          '<div class="crw-digest-body">' + md(it.digest || "") +
            (it.read_at ? '<div class="crw-digest-at">读于 ' + esc(it.read_at) + '</div>' : '') +
          '</div></div>';
      });
      html += '</div>';
    }
    html += '</div>';

    // —— 主动研究成果（已落库的文档，合并自原「主动研究」tab）——
    const rsaved = d.research_saved || [];
    const cfg = d.config || {};
    html += '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>🌐</span><span class="crw-panel-title">主动研究成果（共 ' + rsaved.length + ' 篇）</span></div>' +
      '<div class="crw-panel-hint">小助根据「对你的理解」主动上网搜来、存进成长库的资料。这些会被下一轮洞察再读到，于是越用越懂你。' +
      (cfg.auto_research ? '' : '<b>（当前未开启自动研究，可去「设置」打开）</b>') + '</div>';
    if (!rsaved.length) {
      html += '<div class="crw-runs-empty">还没有主动研究成果。去「设置」打开「洞察后主动上网研究」，下次分析完就会生成。</div>';
    } else {
      html += '<div class="crw-research-docs">';
      rsaved.forEach((it) => {
        const open = !!_expandedResearch[it.name];
        html += '<div class="crw-rdoc">' +
          '<div class="crw-rdoc-head" data-rdoc="' + esc(it.name) + '">' +
            '<span class="crw-rdoc-title">🔎 ' + esc(it.title || it.name) + '</span>' +
            '<span class="crw-rdoc-meta">' + esc(it.mtime || "") + ' · ' + (open ? "收起 ▲" : "展开 ▼") + '</span>' +
          '</div>' +
          (open ? '<div class="crw-rdoc-body">' + md(_expandedResearch[it.name]) + '</div>' : '') +
          '</div>';
      });
      html += '</div>';
    }
    html += '</div>';

    return html;
  }

  function metaItem(label, val) {
    return '<div class="crw-meta-item"><span class="crw-meta-label">' + esc(label) +
      '</span><span class="crw-meta-val">' + esc(val) + '</span></div>';
  }

  // —— 设置 + 运行信息（概览空闲）——
  function settingsHtml(d) {
    const cfg = d.config || {};
    const labels = d.scope_labels || {};
    const avail = d.available || {};
    const runs = d.runs || [];
    const sched = d.scheduler || {};
    const last = d.last_run;

    let html = '<div class="crw-grid">';

    // 左：设置
    html += '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>⚙️</span><span class="crw-panel-title">爬取设置</span></div>' +
      '<div class="crw-panel-hint">设定多久自动深读一次、爬哪些内容。也可随时点右上角「立即分析」手动跑。</div>';

    html += '<div class="crw-field"><label class="crw-switch">' +
      '<input type="checkbox" id="crwAuto"' + (cfg.auto ? " checked" : "") + '>' +
      '<span class="crw-switch-track"></span><span>定时自动爬取分析</span></label></div>';

    html += '<div class="crw-field"><span class="crw-field-label">什么时候跑</span>' +
      '<div class="crw-row" style="margin-bottom:9px"><div class="crw-seg" id="crwModeSeg">' +
        '<button data-mode="interval"' + (cfg.mode !== "daily" ? ' class="active"' : '') + '>每隔一段时间</button>' +
        '<button data-mode="daily"' + (cfg.mode === "daily" ? ' class="active"' : '') + '>每天固定时间</button>' +
      '</div></div>' +
      '<div class="crw-row" id="crwIntervalRow"' + (cfg.mode === "daily" ? ' style="display:none"' : '') + '>' +
        '每隔 <input type="number" min="1" max="720" class="crw-input num" id="crwInterval" value="' + (cfg.interval_hours || 24) + '"> 小时跑一次</div>' +
      '<div class="crw-row" id="crwDailyRow"' + (cfg.mode === "daily" ? '' : ' style="display:none"') + '>' +
        '每天 <input type="time" class="crw-input" id="crwDailyAt" value="' + esc(cfg.daily_at || "03:00") + '"> 跑一次</div></div>';

    html += '<div class="crw-field"><span class="crw-field-label">爬取范围</span><div class="crw-scopes">';
    Object.keys(labels).forEach((k) => {
      const on = (cfg.scopes || {})[k] !== false;
      html += '<label class="crw-scope"><input type="checkbox" data-scope="' + esc(k) + '"' + (on ? " checked" : "") + '>' +
        '<span>' + esc(labels[k]) + '</span><span class="crw-scope-n">' + (avail[k] || 0) + '</span></label>';
    });
    html += '</div></div>';

    html += '<div class="crw-field"><label class="crw-switch">' +
      '<input type="checkbox" id="crwReadLocal"' + (cfg.read_local !== false ? " checked" : "") + '>' +
      '<span class="crw-switch-track"></span><span>逐篇精读用本地模型（快/免费/私密，推荐）</span></label>' +
      '<div class="crw-panel-hint" style="margin:6px 0 0">关掉则用软件默认模型逐篇读——质量更高但篇数多时慢、且网页模型可能弹窗。</div></div>';

    html += '<div class="crw-field"><label class="crw-switch">' +
      '<input type="checkbox" id="crwApply"' + (cfg.apply_to_agent !== false ? " checked" : "") + '>' +
      '<span class="crw-switch-track"></span><span>把分析出的理解注入小助（对话时更懂你）</span></label></div>';

    // 主动研究开关
    html += '<div class="crw-field"><label class="crw-switch">' +
      '<input type="checkbox" id="crwAutoResearch"' + (cfg.auto_research ? " checked" : "") + '>' +
      '<span class="crw-switch-track"></span><span>洞察后主动上网研究（把相关内容存进成长库）</span></label>' +
      '<div class="crw-panel-hint" style="margin:6px 0 0">每次分析完，小助会根据「对你的理解」挑几个话题上网搜，' +
      '成果存进成长库、下次洞察再读到，于是越用越懂你。<b>会自动联网</b>，按需开启；走你设置里的代理。</div></div>';

    // 研究 / 汇总用哪个模型（挑话题 + 汇总画像；上网抓正文那步不调模型）
    html += '<div class="crw-field"><span class="crw-field-label">研究 / 汇总模型</span>' +
      '<div class="crw-row"><select class="crw-select" id="crwModelSelect" style="min-width:200px">' +
        '<option value="">加载中…</option></select></div>' +
      '<div class="crw-panel-hint" style="margin:6px 0 0">用于「挑研究话题」和「把每篇理解汇总成画像」。' +
      '选「跟随软件默认」就用你聊天用的默认模型；本地模型快又私密，网页/Claude 质量更高但可能慢或弹窗。' +
      '（逐篇精读另由上面的「本地模型」开关控制）</div></div>';

    html += '<div class="crw-save-row"><button class="crw-save-btn" id="crwSaveBtn">保存设置</button>' +
      '<button class="crw-ghost-btn" id="crwResetBtn" title="清空已学习缓存，下次从头重读全部">重读全部</button>' +
      '<span class="crw-save-hint" id="crwSaveHint"></span></div>';
    html += '</div>'; // /左

    // 右：运行信息
    html += '<div class="crw-panel">' +
      '<div class="crw-panel-head"><span>📈</span><span class="crw-panel-title">运行信息</span></div>' +
      '<div class="crw-runmeta">' +
        '<span class="crw-runmeta-item">上次分析：<b>' + (last ? esc(last.time) : "还没跑过") + '</b></span>' +
        '<span class="crw-runmeta-item">已深读：<b>' + (d.learned_total || 0) + ' 篇</b></span>' +
        '<span class="crw-runmeta-item">自动状态：<b>' + (sched.running ? "运行中" : (cfg.auto ? "待启动" : "已关闭")) + '</b></span>' +
        (sched.next_due ? '<span class="crw-runmeta-item">下次预计：<b>' + esc(sched.next_due) + '</b></span>' : '') +
      '</div>';

    if (!runs.length) {
      html += '<div class="crw-runs-empty">还没有运行记录。点右上角「立即分析」跑第一次（篇数多时会逐篇读，给它点时间）。</div>';
    } else {
      html += '<div class="crw-runs">';
      runs.forEach((it) => {
        const tag = it.source === "auto" ? "自动" : "手动";
        html += '<div class="crw-run"><span class="crw-run-badge' + (it.ok ? "" : " fail") + '"></span>' +
          '<div class="crw-run-main"><div class="crw-run-time">' + esc(it.time || "") +
            '<span class="crw-tag">' + tag + '</span>' +
            (it.files != null ? ' · 共 ' + it.files + ' 篇' : '') +
            (it.learned != null ? ' · 新读 ' + it.learned : '') + '</div>' +
            '<div class="crw-run-sum">' + esc(it.summary || (it.ok ? "完成" : "未成功")) + '</div>' +
          '</div></div>';
      });
      html += '</div><div class="crw-save-row" style="margin-top:12px"><button class="crw-ghost-btn" id="crwClearRunsBtn">清空运行记录</button></div>';
    }
    html += '</div></div>'; // /右 /grid
    return html;
  }

  // ---------- 绑定 ----------
  function bind(d) {
    document.querySelectorAll("#crwBody [data-crwtab]").forEach((b) => {
      b.addEventListener("click", () => { _crwTab = b.dataset.crwtab; render(); });
    });
    // 概况数字点开详情
    document.querySelectorAll("#crwBody [data-ovdetail]").forEach((b) => {
      b.addEventListener("click", () => openOvDetail(b.dataset.ovdetail));
    });
    // 详情浮层：关闭 / 点背景关闭 / 切换过滤 / 展开某篇总结
    const ovClose = $("ovdClose");
    if (ovClose) ovClose.addEventListener("click", () => { _ovDetail = null; render(); });
    const ovOverlay = $("ovdOverlay");
    if (ovOverlay) ovOverlay.addEventListener("click", (e) => {
      if (e.target === ovOverlay) { _ovDetail = null; render(); }
    });
    document.querySelectorAll("#crwBody [data-ovfilter]").forEach((b) => {
      b.addEventListener("click", () => { if (_ovDetail) { _ovDetail.filter = b.dataset.ovfilter; render(); } });
    });
    document.querySelectorAll("#crwBody [data-ovrow]").forEach((h) => {
      h.addEventListener("click", () => {
        if (!_ovDetail) return;
        const nm = h.dataset.ovrow;
        _ovDetail.expanded = _ovDetail.expanded || {};
        _ovDetail.expanded[nm] = !_ovDetail.expanded[nm];
        render();
      });
    });
    document.querySelectorAll("#crwBody .crw-digest-head").forEach((h) => {
      h.addEventListener("click", () => {
        const card = h.closest(".crw-digest");
        const tog = h.querySelector(".crw-digest-toggle");
        const collapsed = card.classList.toggle("collapsed");
        if (tog) tog.textContent = collapsed ? "展开 ▼" : "收起 ▲";
      });
    });
    document.querySelectorAll("#crwBody [data-rdoc]").forEach((h) => {
      h.addEventListener("click", () => toggleResearchDoc(h.dataset.rdoc));
    });

    const seg = $("crwModeSeg");
    if (seg) seg.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        seg.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        const daily = b.dataset.mode === "daily";
        if ($("crwIntervalRow")) $("crwIntervalRow").style.display = daily ? "none" : "";
        if ($("crwDailyRow")) $("crwDailyRow").style.display = daily ? "" : "none";
      });
    });
    if ($("crwSaveBtn")) $("crwSaveBtn").addEventListener("click", saveConfig);
    if ($("crwClearRunsBtn")) $("crwClearRunsBtn").addEventListener("click", clearRuns);
    if ($("crwResetBtn")) $("crwResetBtn").addEventListener("click", resetLearned);
    if ($("crwStopBtn")) $("crwStopBtn").addEventListener("click", stopRun);
    if ($("crwResumeBtn")) $("crwResumeBtn").addEventListener("click", runNow);

    // 研究模型下拉框：从 /models 拉列表填充，选中 config 里存的
    if ($("crwModelSelect")) populateModelSelect((d.config || {}).model || "");
  }

  // 本地模型集合（用来判断选中项的 use_local）
  let _localModelSet = null;

  async function populateModelSelect(want) {
    const sel = $("crwModelSelect");
    if (!sel) return;
    try {
      const r = await fetch(BACKEND + "/models");
      const data = await r.json();
      const models = data.models || [];   // 本地（纯字符串）
      const cloud = data.cloud || [];     // 云端（纯字符串）
      const web = data.web || [];         // [{id,name}]
      const claude = data.claude || [];   // [{id,name}]
      _localModelSet = new Set(models);
      sel.innerHTML = "";

      // 跟随软件默认
      const def = document.createElement("option");
      def.value = ""; def.textContent = "跟随软件默认模型";
      if (!want) def.selected = true;
      sel.appendChild(def);

      const addOpt = (group, value, label) => {
        const opt = document.createElement("option");
        opt.value = value; opt.textContent = label || value;
        if (value === want) opt.selected = true;
        group.appendChild(opt);
      };
      if (models.length) {
        const g = document.createElement("optgroup"); g.label = "本地模型";
        models.forEach((m) => addOpt(g, m, m)); sel.appendChild(g);
      }
      if (cloud.length) {
        const g = document.createElement("optgroup"); g.label = "☁ 云端模型";
        cloud.forEach((m) => addOpt(g, m, "☁ " + m)); sel.appendChild(g);
      }
      if (web.length) {
        const g = document.createElement("optgroup"); g.label = "☁☁ 网页模型";
        web.forEach((m) => addOpt(g, m.id || "web", "☁☁ " + (m.name || "网页模型"))); sel.appendChild(g);
      }
      if (claude.length) {
        const g = document.createElement("optgroup"); g.label = "✦ Claude 官方";
        claude.forEach((m) => addOpt(g, m.id || "claude", "✦ " + (m.name || "Claude"))); sel.appendChild(g);
      }
    } catch (e) {
      sel.innerHTML = '<option value="">跟随软件默认模型</option>';
    }
  }

  // 由选中的模型 id 推出 use_local（本地集合里的才算本地；web/claude/cloud 都非本地）
  function modelUseLocal(modelId) {
    if (!modelId) return false;
    if (_localModelSet && _localModelSet.has(modelId)) return true;
    return false;
  }

  async function toggleResearchDoc(name) {
    if (_expandedResearch[name]) {
      delete _expandedResearch[name];
      render();
      return;
    }
    try {
      const r = await fetch(BACKEND + "/insight/research_item?name=" + encodeURIComponent(name));
      const d = await r.json();
      _expandedResearch[name] = (d && d.ok) ? (d.content || "（空）") : ((d && d.message) || "读取失败");
    } catch (e) {
      _expandedResearch[name] = "出错：" + e.message;
    }
    render();
  }

  function collectConfig() {
    const scopes = {};
    document.querySelectorAll("#crwBody [data-scope]").forEach((el) => { scopes[el.dataset.scope] = el.checked; });
    const am = document.querySelector("#crwModeSeg button.active");
    const modelId = ($("crwModelSelect") || {}).value || "";
    return {
      auto: !!($("crwAuto") && $("crwAuto").checked),
      mode: (am && am.dataset.mode) || "interval",
      interval_hours: parseInt(($("crwInterval") || {}).value, 10) || 24,
      daily_at: ($("crwDailyAt") || {}).value || "03:00",
      read_local: !!($("crwReadLocal") && $("crwReadLocal").checked),
      apply_to_agent: !!($("crwApply") && $("crwApply").checked),
      auto_research: !!($("crwAutoResearch") && $("crwAutoResearch").checked),
      model: modelId,
      use_local: modelUseLocal(modelId),
      scopes: scopes,
    };
  }

  async function saveConfig() {
    const hint = $("crwSaveHint");
    if (hint) hint.textContent = "保存中…";
    try {
      const r = await fetch(BACKEND + "/insight/config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectConfig()),
      });
      const d = await r.json();
      if (d && d.ok) {
        if (hint) hint.textContent = "已保存 ✓";
        setTimeout(() => { if (hint) hint.textContent = ""; }, 2000);
        loadCrawler();
      } else if (hint) hint.textContent = "保存失败：" + ((d && d.message) || "未知错误");
    } catch (e) { if (hint) hint.textContent = "出错：" + e.message; }
  }

  async function clearRuns() {
    try { await fetch(BACKEND + "/insight/clear_runs", { method: "POST" }); loadCrawler(); } catch (e) {}
  }

  async function resetLearned() {
    if (!window.confirm("清空已学习的缓存？下次「立即分析」会把所有篇从头重读一遍（较慢）。")) return;
    try { await fetch(BACKEND + "/insight/reset", { method: "POST" }); setStatus("已清空学习缓存，下次将从头重读。", "ok"); loadCrawler(); } catch (e) {}
  }

  // ---------- 立即分析 / 继续 ----------
  async function runNow() {
    const s = (typeof settings === "function") ? settings() : { use_local: false, model: "" };
    setStatus("正在逐篇深读成长库…（篇数多时会读很久，可随时停止，进度会保存）");
    if (_crwTab !== "detail") { _crwTab = "detail"; }   // 一跑就切到研究详情看进度
    try {
      const r = await fetch(BACKEND + "/insight/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_local: s.use_local, model: s.model }),
      });
      const d = await r.json();
      if (d && (d.ok || d.busy)) { loadCrawler(); startPoll(); }
      else setStatus((d && d.message) || "没能开始", "warn");
    } catch (e) { setStatus("出错：" + e.message, "warn"); }
  }

  async function stopRun() {
    try {
      await fetch(BACKEND + "/insight/stop", { method: "POST" });
      setStatus("正在停止…（这一篇读完就停，进度已保存）");
      setTimeout(loadCrawler, 800);
    } catch (e) { setStatus("出错：" + e.message, "warn"); }
  }

  // ---------- 运行中轮询 ----------
  function startPoll() {
    if (_crwPoll) return;
    _crwPoll = setInterval(async () => {
      try {
        const r = await fetch(BACKEND + "/insight/status");
        const d = await r.json();
        if (!d || !d.ok) return;
        _crwData = d;
        render();
        const p = d.progress || {};
        if (!p.active) {
          stopPoll();
          if (p.phase === "done") {
            const lr = d.last_run;
            if (lr && lr.ok) setStatus("分析完成，小助更懂你了。", "ok");
            else setStatus("这轮没读到有效内容——看看本地模型是否启动。", "warn");
          } else if (p.phase === "stopped") {
            setStatus("已暂停，进度已保存。", "ok");
          }
        }
      } catch (e) { /* 继续等 */ }
    }, 1500);
  }
  function stopPoll() { if (_crwPoll) { clearInterval(_crwPoll); _crwPoll = null; } }

  // ---------- 顶栏 + 子菜单 ----------
  function wire() {
    if ($("crwRunBtn")) $("crwRunBtn").addEventListener("click", runNow);

    // 子菜单：点 insight 显示本子页并加载；点其它项隐藏本子页 + 隐藏「立即分析」按钮
    document.querySelectorAll('#lumiSubNav .nav-subitem').forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.lumi === "insight") {
          showInsightPage();
          loadCrawler();
        } else {
          hideInsightPage();
        }
      });
    });
    // 点主导航「懂你」：若上次停在洞察子页，回到「你的画像」默认页
    const lnav = document.querySelector('.nav-item[data-view="lumi"]');
    if (lnav) lnav.addEventListener("click", () => {
      const insItem = document.querySelector('#lumiSubNav .nav-subitem[data-lumi="insight"]');
      hideInsightPage();
      if (insItem && insItem.classList.contains("active")) {
        document.querySelectorAll('#lumiSubNav .nav-subitem').forEach((x) =>
          x.classList.toggle("active", x.dataset.lumi === "profile"));
        const pp = $("lumiPageProfile");
        if (pp) pp.style.display = "";
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();

  window.loadCrawler = loadCrawler;

  // 供其它页面（如人格演化资料源链接）跳到洞察某个 tab
  window.insightOpenTab = function (tab) {
    _crwTab = (tab === "detail" || tab === "settings" || tab === "summary") ? tab : "detail";
    loadCrawler();
  };
})();
