// ============================================================
// evolution.js —「🌱 人格演化」看板（「懂你」下的子页，和「你的画像」同一级）
// 讲清演化是怎么工作的 + 历次演化时间线 + 当前画像来源。
// 自己处理子菜单第 4 项的显隐（renderer.js 的 switchLumiSub 只认 profile/relations/env），
// 不需要修改 renderer.js。复用全局：BACKEND / renderMarkdown / escapeHtml / settings()
// ============================================================

(function () {
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

  const KNOWN_PAGES = ["lumiPageProfile", "lumiPageRelations", "lumiPageEnv", "lumiPageInsight"];

  function hideEvoPage() {
    const p = $("lumiPageEvolution");
    if (p) p.style.display = "none";
  }
  function showEvoPage() {
    KNOWN_PAGES.forEach((id) => { const e = $(id); if (e) e.style.display = "none"; });
    const p = $("lumiPageEvolution");
    if (p) p.style.display = "";
    // 顶栏按钮显隐由 renderer.js 的 setLumiTopbarButtons 统一管理
  }

  // ---------- 解析 evolution_log.md → 时间线 ----------
  function parseLog(text) {
    const out = [];
    if (!text) return out;
    const lines = text.split(/\r?\n/);
    const hdr = /^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*$/;
    let cur = null;
    lines.forEach((ln) => {
      const m = ln.match(hdr);
      if (m) {
        if (cur) out.push(cur);
        cur = { time: m[1], body: [] };
      } else if (cur) {
        if (ln.trim() === "---") return;
        cur.body.push(ln);
      }
    });
    if (cur) out.push(cur);
    out.forEach((e) => { e.body = e.body.join("\n").trim(); });
    // 文件里是旧→新追加的，这里反转成新→旧
    return out.reverse();
  }

  function setEvoStatus(msg, kind) {
    const el = $("evoStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.className = "evo-status" + (kind ? " " + kind : "");
  }

  // ---------- 渲染 ----------
  async function loadEvolution() {
    const body = $("lumiEvolutionBody");
    if (!body) return;
    body.innerHTML = '<div class="evo-empty">加载中…</div>';
    let d = {};
    try {
      const r = await fetch(BACKEND + "/lumi/status");
      d = await r.json();
    } catch (e) {
      body.innerHTML = '<div class="evo-empty">后端没连上：' + esc(e.message) + "</div>";
      return;
    }
    const entries = parseLog((d && d.evolution_log) || "");
    const profile = (d && d.profile) || "";
    const lastTime = entries.length ? entries[0].time : "—";

    // 原理说明
    let html = '<div class="evo-explain">' +
      '<div class="evo-explain-title">🌱 人格演化是怎么工作的</div>' +
      '<div class="evo-explain-body">点「✨ 人格演化」时，小助会读你<b>最近的对话存档</b>、' +
      '<b>长期记忆</b>，以及<b>「🔍 洞察」逐篇精读成长库后形成的学习数据</b>，' +
      '让 AI 总结出「你是个什么样的人、怎么说话、关注什么」，把结果写进画像' +
      '（OWNER_PROFILE.md）<b>注入到它的系统提示</b>里，于是它说话越来越对你的频道。' +
      '每演化一次都会在这里留一份快照，可对比着看它怎么一步步变懂你。' +
      '<div class="evo-flow">' +
        '<span class="evo-flow-step">洞察逐篇精读成长库</span>' +
        '<span class="evo-flow-arrow">→</span>' +
        '<span class="evo-flow-step">读对话 + 记忆 + 深读数据</span>' +
        '<span class="evo-flow-arrow">→</span>' +
        '<span class="evo-flow-step">AI 总结你的画像</span>' +
        '<span class="evo-flow-arrow">→</span>' +
        '<span class="evo-flow-step">写入画像并注入小助</span>' +
      '</div></div></div>';

    // 统计
    html += '<div class="evo-stats">' +
      '<div><div class="evo-stat-num">' + entries.length + '</div><div class="evo-stat-label">已演化次数</div></div>' +
      '<div><div class="evo-stat-num" style="font-size:15px;padding-top:7px">' + esc(lastTime) + '</div><div class="evo-stat-label">最近一次演化</div></div>' +
      '<div><div class="evo-stat-num">' + (profile.trim() ? "已生成" : "未生成") + '</div><div class="evo-stat-label">当前画像</div></div>' +
      '</div>';

    // 操作：立即演化
    html += '<div class="evo-actions">' +
      '<button class="crw-save-btn" id="evoRunBtn">✨ 立即演化一次</button>' +
      '<span class="evo-status" id="evoStatus"></span></div>';

    // 实时进度面板宿主（演化进行时显示每一步）
    html += '<div id="evoProgressHost"></div>';

    // 演化准不准的小提示
    html += '<div class="evo-explain-body" style="margin-bottom:18px;color:var(--text-dim);font-size:12.5px">' +
      '💡 觉得演化得不太准？多半是 AI 没真正读懂你的文件。先去「<b>🔍 洞察与研究</b>」点「立即分析」，' +
      '让它把成长库<b>逐篇精读</b>一遍，再回来演化，画像会准很多。' +
      '想换更强的模型，也在「洞察与研究 → 设置」里选「研究/汇总模型」。' +
      '你也可以去「🧠 记忆」里直接手改 OWNER_PROFILE.md。</div>';

    // 时间线
    html += '<div class="evo-section-title">🕒 演化时间线（新 → 旧）</div>';
    if (!entries.length) {
      html += '<div class="evo-empty">还没有演化记录。点上面「✨ 立即演化一次」，' +
        '小助会从你的对话和成长库里总结出你的画像，并在这里留下第一份快照。</div>';
    } else {
      html += '<div class="evo-timeline">';
      entries.forEach((e, i) => {
        const latest = i === 0;
        const collapsed = i === 0 ? "" : " collapsed";
        html += '<div class="evo-entry' + (latest ? "" : " dim") + collapsed + '">' +
          '<div class="evo-entry-card">' +
            '<div class="evo-entry-head">' +
              '<span class="evo-entry-time">' + esc(e.time) +
                (latest ? '<span class="evo-latest">最新</span>' : '') + '</span>' +
              '<span class="evo-entry-toggle">' + (latest ? "收起 ▲" : "展开 ▼") + '</span>' +
            '</div>' +
            '<div class="evo-entry-body">' + md(e.body) + '</div>' +
          '</div></div>';
      });
      html += '</div>';
    }

    body.innerHTML = html;
    bindEvolution();

    // 进页面时若后台正在演化，恢复实时进度；若上次有结果/被中断，也显示出来（可折叠）
    try {
      const r = await fetch(BACKEND + "/lumi/evolve_status");
      const d = await r.json();
      const prog = (d && d.progress) || {};
      if (prog.active || prog.running) {
        renderEvoProgress(prog);
        setEvoBtnState(true);
        startEvoPoll();
      } else if (prog.phase === "done" || prog.phase === "error") {
        // 上次的结果（含「被中断」）默认折叠显示，按钮恢复可用
        _evoProgCollapsed = true;
        renderEvoProgress(prog);
        setEvoBtnState(false);
        if (prog.phase === "error" && prog.message) setEvoStatus(prog.message, "warn");
      }
    } catch (e) {}
  }

  function bindEvolution() {
    // 展开/收起每条快照
    document.querySelectorAll("#lumiEvolutionBody .evo-entry").forEach((card) => {
      const head = card.querySelector(".evo-entry-head");
      const tog = card.querySelector(".evo-entry-toggle");
      if (head) head.addEventListener("click", () => {
        const collapsed = card.classList.toggle("collapsed");
        if (tog) tog.textContent = collapsed ? "展开 ▼" : "收起 ▲";
      });
    });
    // 立即演化
    const btn = $("evoRunBtn");
    if (btn) btn.addEventListener("click", runEvolve);
  }

  let _evoPoll = null;

  // 把模型选择读出来（跟随软件默认 settings，与洞察一致）
  function _settings() {
    return (typeof settings === "function") ? settings() : { use_local: true, model: "qwen2.5" };
  }

  let _evoProgCollapsed = false;   // 完成后的进度面板是否折叠

  // 在演化页顶部插入/更新一个「实时进度面板」（完成后保留，可折叠）
  function renderEvoProgress(prog) {
    const host = $("evoProgressHost");
    if (!host) return;
    if (!prog || (!prog.active && prog.phase === "idle")) { host.innerHTML = ""; return; }

    const phaseText = {
      idle: "准备中", collecting: "收集材料", distilling: "蒸馏「关于你」的线索",
      synthesizing: "总结画像", writing: "写入与留档", done: "完成", error: "出错",
    }[prog.phase] || prog.phase || "";

    const percent = prog.percent || 0;
    const stepLine = (prog.total_steps)
      ? ('第 ' + (prog.step || 0) + ' / ' + prog.total_steps + ' 步')
      : '';
    const finished = !prog.active;
    // 跑的时候始终展开；完成后允许折叠
    const collapsed = finished && _evoProgCollapsed;

    let h = '<div class="evo-prog' + (finished ? ' done' : '') + (collapsed ? ' collapsed' : '') + '">' +
      '<div class="evo-prog-head" id="evoProgHead"' + (finished ? ' style="cursor:pointer"' : '') + '>' +
        '<span class="evo-prog-title">' +
          (prog.active ? '⏳ 正在演化…' : (prog.ok ? '✅ 演化完成' : '⚠ 演化结束')) +
        '</span>' +
        '<span class="evo-prog-headright">' +
          '<span class="evo-prog-model">模型：<b>' + esc(prog.model || "默认") + '</b></span>' +
          (finished ? '<span class="evo-prog-toggle">' + (collapsed ? '展开 ▼' : '收起 ▲') + '</span>' : '') +
        '</span>' +
      '</div>';

    if (!collapsed) {
      h += '<div class="evo-prog-body">' +
        '<div class="evo-prog-phase">当前：' + esc(phaseText) + (stepLine ? ' · ' + stepLine : '') + '</div>' +
        '<div class="evo-prog-bar"><div class="evo-prog-fill" style="width:' + percent + '%"></div></div>';

      // 实时活动日志
      const act = prog.activity || [];
      h += '<div class="evo-prog-actwrap"><div class="evo-prog-act" id="evoActLog">';
      if (!act.length) h += '<div class="evo-prog-line dim">准备中…</div>';
      else act.forEach((l) => { h += '<div class="evo-prog-line">' + esc(l) + '</div>'; });
      h += '</div></div>';

      if (!prog.active && prog.message) {
        h += '<div class="evo-prog-msg ' + (prog.ok ? 'ok' : 'warn') + '">' + esc(prog.message) + '</div>';
      }

      // —— 参考资料（放在最下方；点击弹悬浮窗查看内容）——
      const srcs = prog.sources || [];
      if (srcs.length) {
        h += '<div class="evo-ref"><div class="evo-ref-title">📎 本次参考资料（点击在悬浮窗查看）</div>' +
          '<div class="evo-ref-list">';
        srcs.forEach((s, i) => {
          h += '<button class="evo-ref-item" data-evoref="' + i + '">' +
            '<span class="evo-ref-name">' + esc(s.label) + '</span>' +
            '<span class="evo-ref-detail">' + esc(s.detail || "") + '</span>' +
            '<span class="evo-ref-go">查看 ›</span></button>';
        });
        h += '</div></div>';
      }
      h += '</div>'; // /body
    }
    h += '</div>';
    host.innerHTML = h;

    // 折叠开关（完成后点标题栏切换）
    const head = $("evoProgHead");
    if (head && finished) {
      head.addEventListener("click", () => { _evoProgCollapsed = !_evoProgCollapsed; renderEvoProgress(prog); });
    }
    // 参考资料 → 弹悬浮窗
    host.querySelectorAll("[data-evoref]").forEach((b) => {
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const s = (prog.sources || [])[parseInt(b.dataset.evoref, 10)];
        if (s) openSourceFloat(s);
      });
    });
    const log = $("evoActLog");
    if (log) log.scrollTop = log.scrollHeight;
  }

  // 悬浮窗查看某个参考资料的实际内容（从数据库/洞察取，就地显示，不跳走）
  async function openSourceFloat(src) {
    const link = src.link || {};
    let overlay = document.getElementById("evoSrcFloat");
    if (overlay) overlay.remove();
    overlay = document.createElement("div");
    overlay.id = "evoSrcFloat";
    overlay.className = "evo-float-overlay";
    overlay.innerHTML = '<div class="evo-float-card">' +
      '<div class="evo-float-head"><span class="evo-float-title">📎 ' + esc(src.label) +
        '<span class="evo-float-sub">' + esc(src.detail || "") + '</span></span>' +
        '<div class="evo-float-actions">' +
          '<button class="evo-float-open" id="evoFloatOpen">在对应板块打开 ↗</button>' +
          '<button class="evo-float-close" id="evoFloatClose">✕</button>' +
        '</div></div>' +
      '<div class="evo-float-body" id="evoFloatBody"><div class="evo-float-loading">读取中…</div></div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    document.getElementById("evoFloatClose").onclick = () => overlay.remove();
    document.getElementById("evoFloatOpen").onclick = () => { overlay.remove(); navigateToSource(link); };

    // 取内容
    const bodyEl = document.getElementById("evoFloatBody");
    try {
      // 多文件来源（成长库原文 = 视频笔记+情报）：直接在悬浮窗里列出文件清单
      if (link.view === "datadb" && (link.cat === "video" || link.cat === "briefing") && !link.name) {
        await renderSourceFileList(bodyEl, link.cat);
        return;
      }
      const content = await fetchSourceContent(link);
      bodyEl.innerHTML = content
        ? '<div class="evo-float-md">' + md(content) + '</div>'
        : '<div class="evo-float-loading">这个来源包含多个文件，点右上角「在对应板块打开」查看完整列表。</div>';
    } catch (e) {
      bodyEl.innerHTML = '<div class="evo-float-loading">读不出内容，点右上角「在对应板块打开」查看。</div>';
    }
  }

  // 在悬浮窗里渲染某个数据库类别的文件清单（成长库原文用），点某篇可就地展开内容
  async function renderSourceFileList(bodyEl, cat) {
    bodyEl.innerHTML = '<div class="evo-float-loading">读取文件列表…</div>';
    let items = [];
    // 成长库原文 = 视频笔记 + 情报简报，合并两类
    const cats = cat === "video" ? ["video", "briefing"] : [cat];
    for (const c of cats) {
      try {
        const r = await fetch(BACKEND + "/datadb/list?cat=" + encodeURIComponent(c));
        const d = await r.json();
        (d && d.items || []).forEach((it) => { it._cat = c; items.push(it); });
      } catch (e) {}
    }
    if (!items.length) { bodyEl.innerHTML = '<div class="evo-float-loading">这个来源暂时没有文件。</div>'; return; }
    items.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
    let h = '<div class="evo-srclist-hint">本次参考的成长库原文（视频笔记 / 情报，共 ' + items.length + ' 篇，新→旧）。点任意一篇看内容：</div>' +
      '<div class="evo-srclist">';
    items.forEach((it, i) => {
      h += '<div class="evo-srcitem">' +
        '<div class="evo-srcitem-head" data-srcidx="' + i + '">' +
          '<span class="evo-srcitem-title">📄 ' + esc(it.title || it.name) + '</span>' +
          '<span class="evo-srcitem-meta">' + esc(it.date || "") + ' · ' + esc(it.size_h || "") + ' ▼</span>' +
        '</div><div class="evo-srcitem-body" id="evoSrcBody' + i + '"></div></div>';
    });
    h += '</div>';
    bodyEl.innerHTML = h;
    bodyEl.querySelectorAll("[data-srcidx]").forEach((head) => {
      head.addEventListener("click", async () => {
        const idx = parseInt(head.dataset.srcidx, 10);
        const it = items[idx];
        const bodyDiv = document.getElementById("evoSrcBody" + idx);
        if (!bodyDiv) return;
        if (bodyDiv.dataset.open === "1") { bodyDiv.innerHTML = ""; bodyDiv.dataset.open = "0"; return; }
        bodyDiv.innerHTML = '<div class="evo-float-loading">读取中…</div>';
        try {
          const r = await fetch(BACKEND + "/datadb/item?cat=" + encodeURIComponent(it._cat) +
            "&name=" + encodeURIComponent(it.name));
          const d = await r.json();
          bodyDiv.innerHTML = (d && d.ok)
            ? '<div class="evo-float-md">' + md(d.content || "（空）") + '</div>'
            : '<div class="evo-float-loading">读不出内容。</div>';
          bodyDiv.dataset.open = "1";
        } catch (e) {
          bodyDiv.innerHTML = '<div class="evo-float-loading">读取出错。</div>';
        }
      });
    });
  }

  // 按 link 目标取该来源的文本内容（用于悬浮窗就地预览）
  async function fetchSourceContent(link) {
    try {
      if (link.view === "datadb" && link.cat === "memory" && link.name) {
        const r = await fetch(BACKEND + "/datadb/item?cat=memory&name=" + encodeURIComponent(link.name));
        const d = await r.json();
        return (d && d.ok) ? d.content : "";
      }
      if (link.view === "datadb" && link.cat === "conversations") {
        // 取对话存档的第一条预览
        const r = await fetch(BACKEND + "/datadb/list?cat=conversations");
        const d = await r.json();
        const items = (d && d.items) || [];
        if (!items.length) return "（暂无对话存档）";
        const r2 = await fetch(BACKEND + "/datadb/item?cat=conversations&name=" + encodeURIComponent(items[0].name));
        const d2 = await r2.json();
        return (d2 && d2.ok) ? d2.content : "";
      }
      if (link.view === "insight") {
        // 取洞察精读线索的汇总预览（每篇理解的前几条）
        const r = await fetch(BACKEND + "/insight/analyzable");
        const d = await r.json();
        const read = ((d && d.items) || []).filter((x) => x.read && x.digest).slice(0, 6);
        if (!read.length) return "";
        return read.map((x) => "### " + (x.title || x.name) + "\n" + x.digest).join("\n\n");
      }
    } catch (e) {}
    return "";   // 多文件来源（如视频原文）→ 返回空，引导去板块看列表
  }

  // 点资料源 → 跳到对应界面（数据库某类别 / 洞察研究详情），并放一个「返回人格演化」浮钮
  function navigateToSource(link) {
    try {
      if (link.view === "datadb") {
        const nav = document.querySelector('.nav-item[data-view="datadb"]');
        if (nav) nav.click();
        setTimeout(() => {
          if (link.cat && typeof window.datadbOpenCategory === "function") {
            window.datadbOpenCategory(link.cat, link.name || null);
          }
        }, 250);
      } else if (link.view === "insight") {
        const sub = document.querySelector('#lumiSubNav .nav-subitem[data-lumi="insight"]');
        if (sub) sub.click();
        setTimeout(() => {
          if (typeof window.insightOpenTab === "function") window.insightOpenTab(link.tab || "detail");
        }, 250);
      }
      showBackToEvolution();
    } catch (e) { /* 静默 */ }
  }

  // 一个固定在右下角的「← 返回人格演化」按钮，点了回到演化页（看完资料能原路返回）
  function showBackToEvolution() {
    let btn = document.getElementById("backToEvoBtn");
    if (btn) btn.remove();
    btn = document.createElement("button");
    btn.id = "backToEvoBtn";
    btn.className = "back-to-evo";
    btn.textContent = "← 返回人格演化";
    btn.addEventListener("click", () => {
      const sub = document.querySelector('#lumiSubNav .nav-subitem[data-lumi="evolution"]');
      if (sub) sub.click();
      btn.remove();
    });
    document.body.appendChild(btn);
  }

  async function pollEvoProgress() {
    try {
      const r = await fetch(BACKEND + "/lumi/evolve_status");
      const d = await r.json();
      const prog = (d && d.progress) || {};
      renderEvoProgress(prog);
      if (!prog.active && !prog.running) {
        stopEvoPoll();
        setEvoBtnState(false);
        if (prog.ok) {
          setEvoStatus("演化完成，画像已更新。", "ok");
          await loadEvolution();   // 重渲染时间线（会重新放进度面板宿主）
          renderEvoProgress(prog); // loadEvolution 重建了 DOM，重画一次进度结果
          if (typeof loadLumi === "function") { try { loadLumi(); } catch (_) {} }
        } else {
          setEvoStatus(prog.message || "演化没成功", "warn");
        }
      }
    } catch (e) { /* 继续等 */ }
  }

  function startEvoPoll() {
    if (_evoPoll) return;
    _evoPoll = setInterval(pollEvoProgress, 1200);
  }
  function stopEvoPoll() { if (_evoPoll) { clearInterval(_evoPoll); _evoPoll = null; } }

  // 「立即演化一次」按钮外观：busy 时变「正在演化…」并禁用
  function setEvoBtnState(busy) {
    const btn = $("evoRunBtn");
    if (!btn) return;
    if (!btn.dataset.label) btn.dataset.label = btn.textContent || "✨ 立即演化一次";
    if (busy) { btn.disabled = true; btn.classList.add("busy"); btn.textContent = "⏳ 正在演化…"; }
    else { btn.disabled = false; btn.classList.remove("busy"); btn.textContent = btn.dataset.label; }
  }

  async function runEvolve() {
    const s = _settings();
    setEvoBtnState(true);
    setEvoStatus("正在启动演化…");
    try {
      const r = await fetch(BACKEND + "/lumi/evolve", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_local: s.use_local, model: s.model }),
      });
      const d = await r.json();
      if (d && d.ok) {
        setEvoStatus("演化进行中…每一步实时显示在下面。");
        startEvoPoll();
        pollEvoProgress();   // 立刻拉一次，别等 1.2s
      } else {
        setEvoStatus((d && d.message) || "没能启动", "warn");
        setEvoBtnState(false);
      }
    } catch (e) {
      setEvoStatus("出错：" + e.message, "warn");
      setEvoBtnState(false);
    }
  }

  // 供 renderer.js 顶栏「✨ 人格演化」按钮调用：切到演化页并直接开跑
  window.runEvolveFromTopbar = function () {
    if (typeof window.loadEvolution === "function") {
      // 确保演化页可见（renderer 的子菜单点击已处理显隐，这里只管开跑）
    }
    runEvolve();
  };

  // ---------- 子菜单显隐（处理第 4 项 evolution）----------
  function wire() {
    // 子菜单各项：点 evolution 显示本页并加载；点其它项隐藏本页
    document.querySelectorAll('#lumiSubNav .nav-subitem').forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.lumi === "evolution") {
          showEvoPage();
          loadEvolution();
        } else {
          hideEvoPage();
        }
      });
    });
    // 点主导航「懂你」：若上次停在演化页，回到「你的画像」默认页
    const lnav = document.querySelector('.nav-item[data-view="lumi"]');
    if (lnav) lnav.addEventListener("click", () => {
      const evoItem = document.querySelector('#lumiSubNav .nav-subitem[data-lumi="evolution"]');
      hideEvoPage();
      if (evoItem && evoItem.classList.contains("active")) {
        document.querySelectorAll('#lumiSubNav .nav-subitem').forEach((x) =>
          x.classList.toggle("active", x.dataset.lumi === "profile"));
        const pp = $("lumiPageProfile");
        if (pp) pp.style.display = "";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }

  window.loadEvolution = loadEvolution;
})();
