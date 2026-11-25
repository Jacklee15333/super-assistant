// ============================================================
// datadb.js —「🗄️ 数据库」：统一管理软件产生的所有数据
// 左侧类别列表（含条目数/占用），右侧文件表格（看/导出/删）。
// 安全分级：内容随便删；画像与记忆删前二次确认；配置默认只读，需解锁才删。
// 自己挂导航与按钮事件，不依赖修改 renderer.js 的核心逻辑。
// 复用全局：BACKEND / renderMarkdown / escapeHtml
// ============================================================

(function () {
  let _ddbData = null;     // overview
  let _ddbCat = null;      // 当前选中类别 key
  let _ddbList = null;     // 当前类别的条目列表
  let _ddbUnlockConfig = false;  // 是否解锁了「配置」类删除
  let _ddbPreview = null;  // {name, content, ext, is_dir}（旧的底部预览，保留给非内容类）
  let _ddbTagFilter = "";  // 当前标签过滤（""=全部）
  let _ddbTagsExpanded = false;  // 标签过滤条是否展开（默认折叠，省得挡内容）
  let _ddbPage = 1;        // 当前页码
  let _ddbPageSize = 20;   // 每页条数（用户可改）
  let _ddbExpanded = {};   // name -> {loading, content, ext} 就地展开阅读的文章

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return (typeof escapeHtml === "function")
      ? escapeHtml(s)
      : String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }
  function md(s) { return (typeof renderMarkdown === "function") ? renderMarkdown(s || "") : esc(s); }
  function setStatus(msg, kind) {
    const el = $("ddbStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.className = "ddb-status" + (kind ? " " + kind : "");
  }

  async function loadDataDb() {
    const body = $("ddbBody");
    if (!body) return;
    if (!_ddbData) body.innerHTML = '<div class="ddb-empty">加载中…</div>';
    try {
      const r = await fetch(BACKEND + "/datadb/overview");
      const d = await r.json();
      if (!d || !d.ok) { body.innerHTML = '<div class="ddb-empty">读取失败</div>'; return; }
      _ddbData = d;
      // 默认选第一个有内容的类别（没有就选第一个）
      if (!_ddbCat) {
        const firstNonEmpty = (d.categories || []).find((c) => c.count > 0);
        _ddbCat = (firstNonEmpty || (d.categories || [])[0] || {}).key || null;
      }
      await loadCategory(_ddbCat, false);
    } catch (e) {
      body.innerHTML = '<div class="ddb-empty">后端没连上：' + esc(e.message) + "</div>";
    }
  }

  async function loadCategory(key, refreshOverview) {
    if (key !== _ddbCat) { _ddbTagFilter = ""; _ddbPage = 1; _ddbExpanded = {}; _ddbTagsExpanded = false; }
    _ddbCat = key;
    _ddbPreview = null;
    if (refreshOverview) {
      try {
        const r = await fetch(BACKEND + "/datadb/overview");
        const d = await r.json();
        if (d && d.ok) _ddbData = d;
      } catch (e) {}
    }
    try {
      const r = await fetch(BACKEND + "/datadb/list?cat=" + encodeURIComponent(key));
      const d = await r.json();
      _ddbList = (d && d.ok) ? d : { items: [], label: key, safety: "content" };
    } catch (e) {
      _ddbList = { items: [], label: key, safety: "content" };
    }
    render();
  }

  function render() {
    const d = _ddbData || {};
    const cats = d.categories || [];

    let html = '<div class="ddb-overview">' +
      '<div class="ddb-ov-title"><button type="button" class="ghost-btn small" data-goto-view="settings" data-goto-tab="tab-data" title="回到设置">← 设置</button> 数据管理 · 软件自己的数据</div>' +
      '<div class="ddb-ov-sub">画像与记忆、配置与状态、视频截图、嗅探快照、学习档案。可以看、导出、删除；<b>配置类默认只读</b>，避免误删影响小助运行。' +
      '视频笔记、简报、对话存档这些资料在左栏<b>「知识库 → 原始资料」</b>里。</div>' +
      '<div class="ddb-ov-stats">' +
        '<span class="ddb-ov-stat"><b>' + (d.total_count || 0) + '</b> 个文件</span>' +
        '<span class="ddb-ov-stat"><b>' + esc(d.total_size_h || "0 B") + '</b> 占用</span>' +
      '</div></div>';

    html += '<div class="ddb-main">';

    // 左：类别
    html += '<div class="ddb-cats">';
    cats.forEach((c) => {
      const active = c.key === _ddbCat ? " active" : "";
      const lock = c.safety === "config" ? '<span class="ddb-cat-lock" title="配置类，默认只读">🔒</span>' : '';
      html += '<button class="ddb-cat' + active + '" data-cat="' + esc(c.key) + '">' +
        '<span class="ddb-cat-icon">' + esc(c.icon) + '</span>' +
        '<span class="ddb-cat-mid"><span class="ddb-cat-label">' + esc(c.label) + lock + '</span>' +
        '<span class="ddb-cat-meta">' + c.count + ' 项 · ' + esc(c.size_h) + '</span></span>' +
        '</button>';
    });
    html += '</div>';

    // 右：文件表格 + 预览
    html += '<div class="ddb-right">' + tableHtml() + previewHtml() + '</div>';

    html += '</div>'; // /main

    $("ddbBody").innerHTML = html;
    bind();
    mountVideoCards();   // 把展开的视频笔记挂成卡片视图（含思维导图）
  }

  // 把当前展开的「视频笔记」用 mountVideoResult 渲染成卡片视图（标题色块 + AI分析/思维导图/原文 标签）。
  // 占位容器是 .ddb-video-host[data-vname]，内容取自 _ddbExpanded[name].content。
  function mountVideoCards() {
    if (_ddbCat !== "video") return;
    if (typeof mountVideoResult !== "function" || typeof parseVideoNote !== "function") return;
    document.querySelectorAll("#ddbBody .ddb-video-host").forEach((host) => {
      const name = host.getAttribute("data-vname");
      const exp = _ddbExpanded[name];
      if (!exp || exp.loading || !exp.content) return;
      if (host.getAttribute("data-mounted") === "1") return;  // 防重复挂载
      try {
        const parsed = parseVideoNote(exp.content);
        // 注意：故意不设 _noteName/_noteCat —— 数据库这边每行已经有自己的 🏷 标签按钮，
        // 不让卡片内再出现「管理标签」（它走的是成长库接口，和数据库的标签接口不是一套）。
        mountVideoResult(parsed, host);
        host.setAttribute("data-mounted", "1");
      } catch (e) {
        host.innerHTML = '<div class="ddb-prev-md">' + md(exp.content || "（空）") + '</div>';
      }
    });
  }

  function safetyBadge(safety) {
    if (safety === "config") return '<span class="ddb-badge ddb-badge-config">配置 · 只读</span>';
    if (safety === "memory") return '<span class="ddb-badge ddb-badge-memory">核心记忆 · 慎删</span>';
    return '<span class="ddb-badge ddb-badge-content">内容数据</span>';
  }

  function tableHtml() {
    const L = _ddbList || {};
    const items = L.items || [];
    const safety = L.safety || "content";

    let html = '<div class="ddb-panel">' +
      '<div class="ddb-panel-head"><span class="ddb-panel-title">' + esc(L.icon || "") + ' ' +
        esc(L.label || "") + '（' + items.length + ' 项）</span>' + safetyBadge(safety) + '</div>';

    // 配置类：解锁开关
    if (safety === "config") {
      html += '<div class="ddb-unlock"><label class="crw-switch">' +
        '<input type="checkbox" id="ddbUnlock"' + (_ddbUnlockConfig ? " checked" : "") + '>' +
        '<span class="crw-switch-track"></span>' +
        '<span>我知道风险，允许删除配置文件</span></label>' +
        '<div class="ddb-unlock-hint">配置文件是软件运行状态（模型选择、登录会话、各功能开关等）。删错可能让某些功能失灵，' +
        '一般不用动。删了大多会在下次使用时按默认重建。</div></div>';
    }

    if (!items.length) {
      html += '<div class="ddb-empty">这个类别下还没有数据。</div></div>';
      return html;
    }

    const taggable = !!L.taggable;   // 内容类才有标签
    const allTags = L.all_tags || [];

    // 标签过滤条（默认折叠，省得挡内容；点「展开全部」才显示）
    if (taggable && allTags.length) {
      const FOLD_N = 8;   // 折叠时只露前 8 个
      const showAll = _ddbTagsExpanded || allTags.length <= FOLD_N;
      const visible = showAll ? allTags : allTags.slice(0, FOLD_N);
      html += '<div class="ddb-tagwrap"><div class="ddb-tagbar">' +
        '<button class="ddb-tagchip' + (_ddbTagFilter === "" ? " active" : "") + '" data-tagf="">全部</button>' +
        visible.map((t) => '<button class="ddb-tagchip' + (_ddbTagFilter === t ? " active" : "") +
          '" data-tagf="' + esc(t) + '">' + esc(t) + '</button>').join("");
      if (allTags.length > FOLD_N) {
        html += '<button class="ddb-tagtoggle" id="ddbTagToggle">' +
          (showAll ? '收起 ▲' : '展开全部 ' + allTags.length + ' 个 ▼') + '</button>';
      }
      html += '</div></div>';
    }

    // 应用标签过滤
    let shown = items;
    if (taggable && _ddbTagFilter) {
      shown = items.filter((it) => (it.tags || []).includes(_ddbTagFilter));
    }
    if (!shown.length) {
      html += '<div class="ddb-empty">没有带「' + esc(_ddbTagFilter) + '」标签的内容。</div></div>';
      return html;
    }

    // —— 分页 ——
    const total = shown.length;
    const pageSize = _ddbPageSize;
    const pageCount = Math.max(1, Math.ceil(total / pageSize));
    if (_ddbPage > pageCount) _ddbPage = pageCount;
    const start = (_ddbPage - 1) * pageSize;
    const pageItems = shown.slice(start, start + pageSize);

    // 分页工具条（顶部）：每页条数选择 + 翻页
    html += pagerHtml(total, pageCount, start, pageItems.length);

    const canDelete = (safety !== "config") || _ddbUnlockConfig;
    html += '<div class="ddb-cardlist">';
    pageItems.forEach((it) => {
      const delAttr = canDelete ? '' : ' disabled title="配置类已锁定，打开上面的开关才能删"';
      const tagsHtml = (taggable && (it.tags || []).length)
        ? '<span class="ddb-card-tags">' + it.tags.map((t) =>
            '<span class="ddb-tag">' + esc(t) + '</span>').join("") + '</span>'
        : (taggable ? '<span class="ddb-card-tags ddb-notag">未打标签</span>' : '');
      const exp = _ddbExpanded[it.name];
      const isOpen = !!exp;
      const authorHtml = it.author
        ? '<span class="ddb-card-author" style="color:#1a73e8;font-weight:600;background:rgba(26,115,232,0.10);border:1px solid rgba(26,115,232,0.30);border-radius:6px;padding:1px 8px;margin-right:8px">👤 ' + esc(it.author) + '</span>'
        : (_ddbCat === "video" && !it.is_dir
            ? '<span class="ddb-card-author" style="color:var(--text-dim,#999);margin-right:8px">（无作者）</span>'
            : '');
      html += '<div class="ddb-card' + (isOpen ? ' open' : '') + '">' +
        '<div class="ddb-card-row">' +
          '<div class="ddb-card-main"' + (it.is_dir ? '' : ' data-toggle="' + esc(it.name) + '"') + '>' +
            '<div class="ddb-card-title">' + (it.is_dir ? '📁 ' : (isOpen ? '📖 ' : '📄 ')) +
              esc(it.title || it.name) +
              (it.is_dir ? '' : '<span class="ddb-card-toggle">' + (isOpen ? '收起 ▲' : '阅读 ▼') + '</span>') +
            '</div>' +
            (isOpen ? '' : (it.preview ? '<div class="ddb-card-prev">' + esc(it.preview) + '</div>' : '')) +
            '<div class="ddb-card-meta">' + tagsHtml + authorHtml +
              '<span class="ddb-card-info">' + esc(it.date) + ' · ' + esc(it.size_h) + '</span></div>' +
          '</div>' +
          '<div class="ddb-card-acts">' +
            (taggable && !it.is_dir ? '<button class="ddb-icon-btn" data-act="tag" data-name="' + esc(it.name) +
              '" data-title="' + esc(it.title || it.name) + '" title="设置标签">🏷</button>' : '') +
            (it.is_dir ? '' : '<button class="ddb-icon-btn" data-act="export" data-name="' + esc(it.name) + '" title="导出/备份">⬇</button>') +
            '<button class="ddb-icon-btn ddb-del" data-act="delete" data-name="' + esc(it.name) +
              '" data-title="' + esc(it.title || it.name) + '"' + delAttr + '>🗑</button>' +
          '</div>' +
        '</div>';
      // 就地展开的正文（手风琴）
      if (isOpen) {
        let inner;
        if (exp.loading) {
          inner = '<div class="ddb-card-loading">读取中…</div>';
        } else if (_ddbCat === "video" && exp.ext === "md"
                   && typeof mountVideoResult === "function"
                   && typeof parseVideoNote === "function") {
          // 视频笔记：用和「视频」板块完全一样的卡片视图（含 🧠 思维导图标签）。
          // 这里先放一个占位容器，render() 之后再把内容挂进去（mountVideoResult 需要真实 DOM 节点）。
          inner = '<div class="ddb-video-host" data-vname="' + esc(it.name) + '"></div>';
        } else if (exp.ext === "md") {
          inner = '<div class="ddb-prev-md">' + md(exp.content || "（空）") + '</div>';
        } else {
          inner = '<pre class="ddb-prev-pre">' + esc(exp.content || "") + '</pre>';
        }
        html += '<div class="ddb-card-read">' + inner + '</div>';
      }
      html += '</div>';
    });
    html += '</div>';

    // 分页工具条（底部，方便长列表翻页）
    if (pageCount > 1) html += pagerHtml(total, pageCount, start, pageItems.length);

    html += '</div>';
    return html;
  }

  // 分页工具条
  function pagerHtml(total, pageCount, start, shownN) {
    const sizes = [10, 20, 50, 100];
    let opts = sizes.map((s) => '<option value="' + s + '"' +
      (s === _ddbPageSize ? ' selected' : '') + '>' + s + ' 条/页</option>').join("");
    let nums = '';
    // 页码：最多显示当前页附近 + 首尾
    const win = 2;
    for (let p = 1; p <= pageCount; p++) {
      if (p === 1 || p === pageCount || (p >= _ddbPage - win && p <= _ddbPage + win)) {
        nums += '<button class="ddb-pagenum' + (p === _ddbPage ? ' active' : '') +
          '" data-page="' + p + '">' + p + '</button>';
      } else if (p === _ddbPage - win - 1 || p === _ddbPage + win + 1) {
        nums += '<span class="ddb-page-ellip">…</span>';
      }
    }
    return '<div class="ddb-pager">' +
      '<span class="ddb-pager-info">共 ' + total + ' 篇 · 第 ' + (start + 1) + '–' + (start + shownN) + ' 篇</span>' +
      '<div class="ddb-pager-ctrl">' +
        '<select class="ddb-pagesize" id="ddbPageSize">' + opts + '</select>' +
        '<button class="ddb-pagebtn" data-page="' + (_ddbPage - 1) + '"' + (_ddbPage <= 1 ? ' disabled' : '') + '>‹ 上一页</button>' +
        '<span class="ddb-pagenums">' + nums + '</span>' +
        '<button class="ddb-pagebtn" data-page="' + (_ddbPage + 1) + '"' + (_ddbPage >= pageCount ? ' disabled' : '') + '>下一页 ›</button>' +
      '</div></div>';
  }

  function previewHtml() {
    if (!_ddbPreview) return '';
    const p = _ddbPreview;
    let inner;
    if (p.is_dir) {
      inner = '<div class="ddb-prev-plain">' + esc(p.content) + '</div>';
    } else if (p.ext === "md") {
      inner = '<div class="ddb-prev-md">' + md(p.content) + '</div>';
    } else {
      inner = '<pre class="ddb-prev-pre">' + esc(p.content) + '</pre>';
    }
    return '<div class="ddb-panel ddb-preview">' +
      '<div class="ddb-panel-head"><span class="ddb-panel-title">👁 预览：' + esc(p.name) + '</span>' +
      '<button class="ddb-icon-btn" id="ddbPrevClose" title="关闭预览">✕</button></div>' +
      inner + '</div>';
  }

  function bind() {
    document.querySelectorAll("#ddbBody [data-cat]").forEach((b) => {
      b.addEventListener("click", () => loadCategory(b.dataset.cat, false));
    });
    const unlock = $("ddbUnlock");
    if (unlock) unlock.addEventListener("change", () => { _ddbUnlockConfig = unlock.checked; render(); });
    const prevClose = $("ddbPrevClose");
    if (prevClose) prevClose.addEventListener("click", () => { _ddbPreview = null; render(); });

    // 标签过滤条
    document.querySelectorAll("#ddbBody [data-tagf]").forEach((b) => {
      b.addEventListener("click", () => { _ddbTagFilter = b.dataset.tagf || ""; _ddbPage = 1; render(); });
    });
    // 标签展开/收起
    const tagToggle = $("ddbTagToggle");
    if (tagToggle) tagToggle.addEventListener("click", () => { _ddbTagsExpanded = !_ddbTagsExpanded; render(); });

    // 就地展开阅读（点标题区）
    document.querySelectorAll("#ddbBody .ddb-card-main[data-toggle]").forEach((b) => {
      b.addEventListener("click", () => toggleRead(b.dataset.toggle));
    });

    // 分页：每页条数
    const ps = $("ddbPageSize");
    if (ps) ps.addEventListener("change", () => {
      _ddbPageSize = parseInt(ps.value, 10) || 20; _ddbPage = 1; render();
    });
    // 分页：翻页按钮 + 页码
    document.querySelectorAll("#ddbBody [data-page]").forEach((b) => {
      if (b.disabled) return;
      b.addEventListener("click", () => {
        const p = parseInt(b.dataset.page, 10);
        if (p >= 1) { _ddbPage = p; _ddbExpanded = {}; render();
          const top = document.querySelector("#ddbBody .ddb-cardlist");
          if (top) top.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });

    document.querySelectorAll("#ddbBody [data-act]").forEach((b) => {
      const act = b.dataset.act;
      if (act === "view") b.addEventListener("click", (e) => { e.stopPropagation(); viewItem(b.dataset.name); });
      else if (act === "export") b.addEventListener("click", (e) => { e.stopPropagation(); exportItem(b.dataset.name); });
      else if (act === "delete") b.addEventListener("click", (e) => { e.stopPropagation(); deleteItem(b.dataset.name, b.dataset.title); });
      else if (act === "tag") b.addEventListener("click", (e) => { e.stopPropagation(); openTagEditor(b.dataset.name, b.dataset.title); });
    });
  }

  // 就地展开/折叠阅读一篇文章（手风琴：同时只展开一篇，点开新的会自动折叠上一篇）
  async function toggleRead(name) {
    if (_ddbExpanded[name]) { _ddbExpanded = {}; render(); return; }
    _ddbExpanded = { [name]: { loading: true } };   // 清掉其它已展开的，只留这一篇
    render();
    try {
      const r = await fetch(BACKEND + "/datadb/item?cat=" + encodeURIComponent(_ddbCat) +
        "&name=" + encodeURIComponent(name));
      const d = await r.json();
      // 只有当前仍是这篇在等待时才写入（避免用户快速点了别的篇导致错位）
      if (_ddbExpanded[name] && _ddbExpanded[name].loading) {
        if (d && d.ok) _ddbExpanded = { [name]: { loading: false, content: d.content || "（空）", ext: d.ext || "" } };
        else { delete _ddbExpanded[name]; setStatus((d && d.message) || "读取失败", "warn"); }
      }
    } catch (e) {
      if (_ddbExpanded[name]) delete _ddbExpanded[name];
      setStatus("出错：" + e.message, "warn");
    }
    render();
  }

  async function viewItem(name) {
    setStatus("读取中…");
    try {
      const r = await fetch(BACKEND + "/datadb/item?cat=" + encodeURIComponent(_ddbCat) +
        "&name=" + encodeURIComponent(name));
      const d = await r.json();
      if (d && d.ok) {
        _ddbPreview = { name: name, content: d.content || "（空）", ext: d.ext || "", is_dir: !!d.is_dir };
        setStatus("");
        render();
        // 滚到预览区
        const pv = document.querySelector(".ddb-preview");
        if (pv) pv.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else setStatus((d && d.message) || "读取失败", "warn");
    } catch (e) { setStatus("出错：" + e.message, "warn"); }
  }

  function exportItem(name) {
    // 直接用浏览器下载后端的 export 流
    const url = BACKEND + "/datadb/export?cat=" + encodeURIComponent(_ddbCat) +
      "&name=" + encodeURIComponent(name);
    try {
      const a = document.createElement("a");
      a.href = url; a.download = name;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      setStatus("已开始导出：" + name, "ok");
    } catch (e) {
      window.open(url, "_blank");
    }
  }

  // 设置标签弹窗（和成长库一样：已选标签可删、可输入新标签、可点常用标签）
  function openTagEditor(name, title) {
    const L = _ddbList || {};
    const item = (L.items || []).find((x) => x.name === name) || {};
    let chosen = (item.tags || []).slice();
    const suggest = (L.all_tags || []).filter((t) => !chosen.includes(t));

    const mask = document.createElement("div");
    mask.className = "ddb-tag-modal-mask";
    mask.innerHTML =
      '<div class="ddb-tag-modal">' +
        '<div class="ddb-tag-modal-title">设置标签</div>' +
        '<div class="ddb-tag-modal-sub">' + esc(title || name) + '</div>' +
        '<div class="ddb-tag-chosen" id="ddbTagChosen"></div>' +
        '<div class="ddb-tag-inputrow">' +
          '<input id="ddbTagInput" class="ddb-tag-input" placeholder="输入新标签，回车添加（如 金融 / 逻辑 / AI）" maxlength="20">' +
        '</div>' +
        (suggest.length ? '<div class="ddb-tag-suggest-title">常用标签（点击添加）</div>' +
          '<div class="ddb-tag-suggest" id="ddbTagSuggest">' +
          suggest.map((t) => '<button class="ddb-tag-sug" data-sug="' + esc(t) + '">' + esc(t) + '</button>').join("") +
          '</div>' : '') +
        '<div class="ddb-tag-modal-acts">' +
          '<button class="ddb-tag-cancel" id="ddbTagCancel">取消</button>' +
          '<button class="ddb-tag-save" id="ddbTagSave">保存</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(mask);

    const renderChosen = () => {
      const box = $("ddbTagChosen");
      box.innerHTML = chosen.length
        ? chosen.map((t) => '<span class="ddb-tag-pick" data-del="' + esc(t) + '">' + esc(t) + ' ✕</span>').join("")
        : '<span class="ddb-tag-empty">还没有标签</span>';
      box.querySelectorAll("[data-del]").forEach((s) =>
        s.addEventListener("click", () => { chosen = chosen.filter((x) => x !== s.dataset.del); renderChosen(); }));
    };
    renderChosen();

    const addTag = (t) => {
      t = (t || "").trim().slice(0, 20);
      if (t && !chosen.includes(t)) { chosen.push(t); renderChosen(); }
    };
    const input = $("ddbTagInput");
    if (input) input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addTag(input.value); input.value = ""; }
    });
    mask.querySelectorAll("[data-sug]").forEach((b) =>
      b.addEventListener("click", () => { addTag(b.dataset.sug); b.remove(); }));
    const close = () => mask.remove();
    $("ddbTagCancel").onclick = close;
    mask.addEventListener("click", (e) => { if (e.target === mask) close(); });
    $("ddbTagSave").onclick = async () => {
      // 把输入框里没回车的也算上
      if (input && input.value.trim()) addTag(input.value);
      setStatus("保存标签中…");
      try {
        const r = await fetch(BACKEND + "/datadb/set_tags", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cat: _ddbCat, name: name, tags: chosen }),
        });
        const d = await r.json();
        if (d && d.ok) {
          setStatus("标签已保存", "ok");
          close();
          await loadCategory(_ddbCat, false);   // 刷新列表（标签条会更新）
        } else setStatus((d && d.message) || "保存失败", "warn");
      } catch (e) { setStatus("出错：" + e.message, "warn"); }
    };
  }

  async function deleteItem(name, title) {
    const L = _ddbList || {};
    const safety = L.safety || "content";
    let msg;
    if (safety === "memory") {
      msg = "删除核心记忆文件「" + (title || name) + "」？\n\n这是小助理解你的重要依据，删了会影响它对你的了解。确定删除？";
    } else if (safety === "config") {
      msg = "删除配置文件「" + name + "」？\n\n这是软件运行配置，删错可能让某些功能失灵（多数会在下次使用时按默认重建）。确定删除？";
    } else {
      msg = "删除「" + (title || name) + "」？此操作不可恢复。";
    }
    if (!window.confirm(msg)) return;
    setStatus("删除中…");
    try {
      const r = await fetch(BACKEND + "/datadb/delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cat: _ddbCat, name: name, force: _ddbUnlockConfig }),
      });
      const d = await r.json();
      if (d && d.ok) {
        setStatus("已删除：" + name, "ok");
        if (_ddbPreview && _ddbPreview.name === name) _ddbPreview = null;
        await loadCategory(_ddbCat, true);   // 刷新列表 + 概况
      } else {
        setStatus((d && d.message) || "删除失败", "warn");
      }
    } catch (e) { setStatus("出错：" + e.message, "warn"); }
  }

  // 顶栏刷新 + 导航
  function wire() {
    if ($("ddbRefreshBtn")) $("ddbRefreshBtn").addEventListener("click", () => { setStatus(""); loadDataDb(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();

  window.loadDataDb = loadDataDb;

  // 供其它页面（如人格演化的资料源链接）跳转到某个类别，并可选预览某个文件
  window.datadbOpenCategory = function (cat, name) {
    _ddbCat = cat;
    loadDataDb().then(() => {
      if (name) { try { viewItem(name); } catch (e) {} }
    });
  };
})();
