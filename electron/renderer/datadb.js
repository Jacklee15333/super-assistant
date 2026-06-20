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
  let _ddbPreview = null;  // {name, content, ext, is_dir}

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
      '<div class="ddb-ov-title">软件产生的所有数据都在这里</div>' +
      '<div class="ddb-ov-sub">视频笔记、情报、对话、画像记忆、配置……按类别归拢，可查看、导出、删除。' +
      '<b>配置类默认只读</b>，避免误删影响小助运行。</div>' +
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

    html += '<div class="ddb-table"><div class="ddb-tr ddb-th">' +
      '<span class="ddb-c-name">名称</span>' +
      '<span class="ddb-c-size">大小</span>' +
      '<span class="ddb-c-date">修改时间</span>' +
      '<span class="ddb-c-act">操作</span></div>';

    const canDelete = (safety !== "config") || _ddbUnlockConfig;
    items.forEach((it) => {
      const delAttr = canDelete ? '' : ' disabled title="配置类已锁定，打开上面的开关才能删"';
      html += '<div class="ddb-tr">' +
        '<span class="ddb-c-name" title="' + esc(it.name) + '">' +
          (it.is_dir ? '📁 ' : '📄 ') + esc(it.title || it.name) +
          '<span class="ddb-c-fname">' + esc(it.name) + '</span></span>' +
        '<span class="ddb-c-size">' + esc(it.size_h) + '</span>' +
        '<span class="ddb-c-date">' + esc(it.date) + '</span>' +
        '<span class="ddb-c-act">' +
          (it.is_dir ? '' : '<button class="ddb-icon-btn" data-act="view" data-name="' + esc(it.name) + '" title="预览">👁</button>') +
          (it.is_dir ? '' : '<button class="ddb-icon-btn" data-act="export" data-name="' + esc(it.name) + '" title="导出/备份">⬇</button>') +
          '<button class="ddb-icon-btn ddb-del" data-act="delete" data-name="' + esc(it.name) +
            '" data-title="' + esc(it.title || it.name) + '"' + delAttr + '>🗑</button>' +
        '</span></div>';
    });
    html += '</div></div>';
    return html;
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

    document.querySelectorAll("#ddbBody [data-act]").forEach((b) => {
      const act = b.dataset.act;
      if (act === "view") b.addEventListener("click", () => viewItem(b.dataset.name));
      else if (act === "export") b.addEventListener("click", () => exportItem(b.dataset.name));
      else if (act === "delete") b.addEventListener("click", () => deleteItem(b.dataset.name, b.dataset.title));
    });
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
