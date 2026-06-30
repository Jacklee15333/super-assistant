/* agents.js — 🎭 分身工坊
 *
 * 分身 = 一个记住了「我会怎么做某件事」的固定专员。它带着我的判断标准和语气替我做事，
 * 越用越懂我。这正是文章最值钱的机制：把隐性判断 → 显性化 → 固化成模块 → 让 AI 承接放大。
 *
 * 三条主线（都复用后端现有 /chat，只多带一个 agent_slug）：
 *   ① 创建（访谈式）：你说要个什么分身 → 它反过来采访你几个问题 → 自动整理成一张可编辑的
 *      「判断标准卡片」→ 你确认存盘。（关键：别让用户写提示词，让软件来采访。）
 *   ② 派活：点进分身的专属对话，发消息时带它的 slug，后端把它的标准拼进系统提示，于是它
 *      自动按你的方式做事。
 *   ③ 反馈进化：对话里点「📌 记进标准」，把这条反馈并进它的判断标准，下次就记住了。
 *
 * 纯前端，零依赖。复用 renderer.js 的全局：BACKEND / renderMarkdown / settings / escapeHtml。
 * 所有 UI 渲染进 index.html 里的 #agentsRoot。对外暴露：window.loadAgents()（切到该视图时由 renderer.js 调）。
 */

(function () {
  "use strict";

  // ---- 复用主程序的全局（都有兜底，单独打开也不炸）----
  function backend() {
    return (typeof BACKEND !== "undefined" && BACKEND) ? BACKEND : "http://127.0.0.1:8756";
  }
  function md(t) {
    try { if (typeof renderMarkdown === "function") return renderMarkdown(t || ""); } catch (e) {}
    return esc(t || "").replace(/\n/g, "<br>");
  }
  function esc(s) {
    try { if (typeof escapeHtml === "function") return escapeHtml(s); } catch (e) {}
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function chatSettings() {
    try { if (typeof settings === "function") return settings(); } catch (e) {}
    return { use_local: true, model: "qwen2.5", shell_enabled: false };
  }

  var INTERVIEW_SLUG = "__interview__";

  // ---- 模块状态 ----
  var state = {
    agents: [],
    screen: "list",          // list | create | chat
    cur: null,               // 当前派活的分身（chat 态）
    chat: { messages: [], busy: false },
    convos: [],              // 当前分身的历史会话列表
    iv: { messages: [], busy: false },   // 访谈对话
    editingSlug: null,       // 编辑已有分身的标准时记下 slug（草稿卡片走"覆盖保存"）
  };

  function root() { return document.getElementById("agentsRoot"); }

  // ====================== 样式（只注入一次，不动 styles.css）======================
  function ensureStyle() {
    if (document.getElementById("agents-style")) return;
    var css = `
    .agents-root{display:flex;flex-direction:column;height:100%;min-height:0;}
    .ag-top{display:flex;align-items:center;justify-content:space-between;gap:10px;
      padding:14px 18px;border-bottom:1px solid var(--border,#e7e7e7);flex:0 0 auto;}
    .ag-top h2{font-size:15px;font-weight:600;margin:0;color:var(--text,#222);}
    .ag-top .sub{font-size:12px;color:var(--muted,#888);font-weight:400;margin-left:8px;}
    .ag-top-actions{display:flex;gap:8px;}
    .ag-btn{font-size:13px;padding:6px 12px;border-radius:8px;border:1px solid var(--border,#ddd);
      background:var(--card,#fff);color:var(--text,#333);cursor:pointer;white-space:nowrap;}
    .ag-btn:hover{background:var(--hover,#f4f4f4);}
    .ag-btn.primary{background:#2b6cff;border-color:#2b6cff;color:#fff;}
    .ag-btn.primary:hover{background:#1f5be0;}
    .ag-btn.ghost{background:transparent;}
    .ag-btn.danger{color:#c23b3b;border-color:#e7c3c3;}
    .ag-btn:disabled{opacity:.5;cursor:default;}
    .ag-body{flex:1 1 auto;min-height:0;overflow:auto;padding:18px;}

    .ag-intro{font-size:13px;line-height:1.7;color:var(--muted,#777);
      background:var(--card,#fafafa);border:1px solid var(--border,#eee);
      border-radius:10px;padding:12px 14px;margin-bottom:16px;}
    .ag-intro b{color:var(--text,#444);}
    .ag-intro code{background:rgba(127,127,127,.12);padding:1px 5px;border-radius:4px;}

    .ag-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;}
    .ag-card{border:1px solid var(--border,#e6e6e6);border-radius:12px;padding:14px;
      background:var(--card,#fff);cursor:pointer;transition:box-shadow .15s,transform .15s;
      display:flex;flex-direction:column;gap:8px;}
    .ag-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);transform:translateY(-1px);}
    .ag-card-head{display:flex;align-items:center;gap:8px;}
    .ag-card-emoji{font-size:22px;line-height:1;}
    .ag-card-name{font-size:14px;font-weight:600;color:var(--text,#222);}
    .ag-card-role{font-size:12px;color:var(--muted,#888);line-height:1.5;
      display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:34px;}
    .ag-card-foot{display:flex;align-items:center;justify-content:space-between;
      margin-top:2px;padding-top:8px;border-top:1px dashed var(--border,#eee);}
    .ag-card-runs{font-size:11px;color:var(--muted,#aaa);}
    .ag-card-acts{display:flex;gap:6px;}
    .ag-mini{font-size:11px;padding:3px 8px;border-radius:6px;border:1px solid var(--border,#ddd);
      background:transparent;color:var(--muted,#666);cursor:pointer;}
    .ag-mini:hover{background:var(--hover,#f2f2f2);color:var(--text,#333);}
    .ag-mini.danger:hover{color:#c23b3b;border-color:#e7c3c3;}
    .ag-empty{color:var(--muted,#999);font-size:13px;padding:30px 4px;text-align:center;}

    /* 访谈 / 派活 共用的对话外壳 */
    .ag-screen{display:flex;flex-direction:column;height:100%;min-height:0;}

    /* 派活工作区：左侧会话栏 + 右侧对话（像主软件那样，每个分身一套自己的历史）*/
    .ag-ws{display:flex;height:100%;min-height:0;}
    .ag-rail{flex:0 0 224px;border-right:1px solid var(--border,#eee);display:flex;
      flex-direction:column;min-height:0;background:var(--bg,#fafafa);}
    .ag-rail-head{display:flex;align-items:center;gap:8px;padding:12px;border-bottom:1px solid var(--border,#eee);}
    .ag-rail-head .emoji{font-size:18px;line-height:1;}
    .ag-rail-head .nm{font-size:13px;font-weight:600;color:var(--text,#222);flex:1;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .ag-rail-new{margin:10px 12px 6px;width:calc(100% - 24px);}
    .ag-rail-label{font-size:11px;color:var(--muted,#aaa);padding:6px 14px 4px;}
    .ag-rail-list{flex:1;overflow:auto;padding:0 8px 12px;}
    .ag-convo{padding:8px 10px;border-radius:8px;cursor:pointer;margin-bottom:3px;position:relative;}
    .ag-convo:hover{background:var(--hover,#ececec);}
    .ag-convo.active{background:#e9f1ff;}
    .ag-convo .ct{font-size:13px;color:var(--text,#333);overflow:hidden;
      text-overflow:ellipsis;white-space:nowrap;padding-right:16px;}
    .ag-convo .cm{font-size:11px;color:var(--muted,#aaa);margin-top:2px;}
    .ag-convo-del{position:absolute;top:7px;right:6px;border:none;background:transparent;
      color:var(--muted,#bbb);cursor:pointer;font-size:12px;opacity:0;line-height:1;}
    .ag-convo:hover .ag-convo-del{opacity:1;}
    .ag-convo-del:hover{color:#c23b3b;}
    .ag-rail-empty{font-size:12px;color:var(--muted,#aaa);padding:14px 10px;text-align:center;line-height:1.6;}
    .ag-ws-main{flex:1;display:flex;flex-direction:column;min-height:0;}
    .ag-screen-head{display:flex;align-items:center;gap:10px;padding:12px 18px;
      border-bottom:1px solid var(--border,#eee);flex:0 0 auto;}
    .ag-screen-head .emoji{font-size:20px;}
    .ag-screen-head .ttl{font-size:14px;font-weight:600;color:var(--text,#222);}
    .ag-screen-head .role{font-size:12px;color:var(--muted,#999);}
    .ag-screen-head .spacer{flex:1;}
    .ag-model-sel{font-size:12px;padding:5px 8px;border:1px solid var(--border,#ddd);
      border-radius:8px;background:var(--card,#fff);color:var(--text,#333);
      max-width:200px;cursor:pointer;font-family:inherit;}
    .ag-mode-btn{font-size:12px;padding:5px 10px;border:1px solid var(--border,#ddd);
      border-radius:8px;background:var(--card,#fff);color:var(--text,#555);cursor:pointer;
      white-space:nowrap;font-family:inherit;}
    .ag-mode-btn:hover{background:var(--hover,#f2f2f2);}
    .ag-mode-btn.smart{background:#eef4ff;border-color:#cfe0ff;color:#2b6cff;}
    .ag-msgs{flex:1 1 auto;min-height:0;overflow:auto;padding:16px 18px;}
    .ag-inputbar{flex:0 0 auto;display:flex;gap:8px;padding:12px 16px;
      border-top:1px solid var(--border,#eee);align-items:flex-end;}
    .ag-input{flex:1;resize:none;min-height:40px;max-height:160px;padding:9px 12px;
      border:1px solid var(--border,#ddd);border-radius:10px;font-size:14px;
      font-family:inherit;line-height:1.5;background:var(--card,#fff);color:var(--text,#222);}
    .ag-hint{font-size:12px;color:var(--muted,#aaa);padding:0 18px 8px;flex:0 0 auto;}

    /* 草稿卡片（判断标准） */
    .ag-draft{max-width:680px;margin:0 auto;border:1px solid var(--border,#e6e6e6);
      border-radius:14px;padding:18px;background:var(--card,#fff);}
    .ag-draft h3{margin:0 0 4px;font-size:15px;color:var(--text,#222);}
    .ag-draft .tip{font-size:12px;color:var(--muted,#999);margin-bottom:14px;}
    .ag-field{display:flex;flex-direction:column;gap:5px;margin-bottom:12px;}
    .ag-field label{font-size:12px;color:var(--muted,#777);font-weight:600;}
    .ag-field input,.ag-field textarea{padding:9px 11px;border:1px solid var(--border,#ddd);
      border-radius:8px;font-size:14px;font-family:inherit;line-height:1.6;
      background:var(--bg,#fcfcfc);color:var(--text,#222);}
    .ag-field textarea{resize:vertical;}
    .ag-row2{display:flex;gap:10px;}
    .ag-row2 .ag-field.emoji{flex:0 0 90px;}
    .ag-row2 .ag-field.grow{flex:1;}
    .ag-samples-row{display:flex;flex-direction:column;gap:6px;border:1px dashed var(--border,#e0e0e0);
      border-radius:8px;padding:10px;margin-bottom:8px;position:relative;}
    .ag-samples-row input{font-size:13px;}
    .ag-samples-row textarea{font-size:13px;min-height:54px;}
    .ag-sample-del{position:absolute;top:6px;right:6px;border:none;background:transparent;
      color:var(--muted,#bbb);cursor:pointer;font-size:14px;}
    .ag-sample-del:hover{color:#c23b3b;}
    .ag-draft-acts{display:flex;gap:10px;margin-top:6px;}

    /* 派活里的「记进标准」内联面板 */
    .ag-feedback{max-width:680px;margin:8px auto;border:1px solid #cfe0ff;background:#f3f8ff;
      border-radius:10px;padding:12px;}
    .ag-feedback textarea{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid #cfe0ff;
      border-radius:8px;font-size:13px;font-family:inherit;resize:vertical;min-height:48px;background:#fff;}
    .ag-feedback .acts{display:flex;gap:8px;margin-top:8px;}

    /* 自动化设置面板 */
    .ag-auto{max-width:720px;margin:8px auto;border:1px solid #d7e3c5;background:#f6faf0;
      border-radius:12px;padding:16px;}
    .ag-auto h4{margin:0 0 4px;font-size:14px;color:var(--text,#2b3a1c);}
    .ag-auto .tip{font-size:12px;color:var(--muted,#7a8a64);line-height:1.6;margin-bottom:12px;}
    .ag-auto .acts{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}
    .ag-auto .status{font-size:12px;color:#3a7a1e;margin-top:8px;}
    .ag-noauto{font-size:13px;color:#8a9a74;padding:10px 0;}
    .ag-tasks{display:flex;flex-direction:column;gap:10px;}
    .ag-task{border:1px solid #dce6cc;background:#fff;border-radius:10px;padding:10px 12px;}
    .ag-task .trow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px;}
    .ag-task .trow .lbl{font-size:12px;color:#667;}
    .ag-task .trow .spc{flex:1;}
    .ag-task label.sw{display:flex;align-items:center;gap:6px;font-size:13px;color:#333;cursor:pointer;}
    .ag-task input[type=time]{padding:4px 7px;border:1px solid var(--border,#cdd8bd);border-radius:7px;
      font-size:13px;font-family:inherit;background:#fff;}
    .ag-task input.tName{width:100%;box-sizing:border-box;padding:6px 9px;border:1px solid #e2e8d6;
      border-radius:7px;font-size:12px;font-family:inherit;background:#fafdf5;margin-bottom:6px;}
    .ag-task textarea.tPrompt{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--border,#cdd8bd);
      border-radius:8px;font-size:13px;font-family:inherit;line-height:1.6;resize:vertical;min-height:60px;background:#fff;}
    .ag-btn.mini{padding:3px 9px;font-size:12px;}
    .ag-btn.danger{color:#c0392b;border-color:#e7b9b3;}
    .ag-btn.danger:hover{background:#fdecea;}

    /* 「已保存」可折叠区（任务保存后收进这里）*/
    .ag-saved{margin-top:12px;border:1px solid #e0e8d4;border-radius:10px;overflow:hidden;background:#fafdf5;}
    .ag-saved-head{display:flex;align-items:center;gap:8px;padding:9px 12px;cursor:pointer;
      font-size:13px;color:#3a4a26;background:#f0f6e6;user-select:none;}
    .ag-saved-head .chev{width:14px;display:inline-block;color:#7a8a64;font-size:12px;text-align:center;}
    .ag-saved-head .cnt{background:#cfe0b6;color:#3a4a26;border-radius:10px;padding:0 8px;font-size:11px;}
    .ag-saved-head .hint{margin-left:auto;font-size:11px;color:#9aa884;font-weight:400;}
    .ag-saved-list{display:flex;flex-direction:column;}
    .ag-saved-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:9px 12px;
      border-top:1px solid #e8efdd;background:#fff;}
    .ag-saved-row .sv-main{display:flex;align-items:center;gap:8px;min-width:150px;flex:1;}
    .ag-saved-row .sv-name{font-size:13px;font-weight:600;color:#2b3a1c;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px;}
    .ag-saved-row .sv-meta{font-size:11.5px;color:#8a9a74;flex:1;min-width:150px;}
    .ag-saved-row .sv-acts{display:flex;gap:6px;flex-wrap:wrap;}
    .ag-pill.saved{font-size:11px;color:#6b7a52;background:#e7efd9;border:1px solid #d4e0c0;
      border-radius:6px;padding:2px 7px;white-space:nowrap;}
    .ag-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#c4ccb4;
      margin-right:5px;vertical-align:middle;}
    .ag-dot.on{background:#5aa61e;}

    /* 自动化结果弹窗（任意界面都能弹，挂在 body 上）*/
    .ag-modal-ov{position:fixed;inset:0;background:rgba(20,24,16,.42);z-index:99999;
      display:flex;align-items:center;justify-content:center;padding:24px;}
    .ag-modal{background:#fff;border-radius:14px;max-width:640px;width:100%;max-height:82vh;
      display:flex;flex-direction:column;box-shadow:0 18px 60px rgba(0,0,0,.3);overflow:hidden;
      font-family:inherit;}
    .ag-modal-head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid #eee;
      background:#f6faf0;}
    .ag-modal-head .em{font-size:28px;line-height:1;}
    .ag-modal-head .t1{font-size:15px;font-weight:700;color:#2b3a1c;}
    .ag-modal-head .t2{font-size:12px;color:#7a8a64;margin-top:2px;}
    .ag-modal-body{padding:16px 18px;overflow-y:auto;font-size:14px;line-height:1.7;color:#222;}
    .ag-modal-body p{margin:0 0 10px;}
    .ag-modal-foot{display:flex;gap:8px;justify-content:flex-end;padding:12px 18px;border-top:1px solid #eee;}

    /* 内联确认（危险操作）—— 复用主对话气泡区里的风格但更克制 */
    .ag-approval{max-width:680px;margin:8px auto;border:1px solid #ffd9a8;background:#fff8ef;
      border-radius:10px;padding:12px;font-size:13px;color:#7a5a1e;}
    .ag-approval .ttl{font-weight:600;margin-bottom:6px;}
    .ag-approval .acts{display:flex;gap:8px;margin-top:8px;}

    .ag-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
      background:#222;color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;
      z-index:9999;opacity:0;transition:opacity .2s;pointer-events:none;}
    .ag-toast.show{opacity:.94;}
    `;
    // 去掉上面变量里不小心混入的零宽字符（保险），再写入
    css = css.replace(/\u200b/g, "");
    var st = document.createElement("style");
    st.id = "agents-style";
    st.textContent = css;
    document.head.appendChild(st);
  }

  function toast(msg) {
    var t = document.createElement("div");
    t.className = "ag-toast";
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("show"); });
    setTimeout(function () {
      t.classList.remove("show");
      setTimeout(function () { t.remove(); }, 250);
    }, 1800);
  }

  // 通用气泡（复用主对话的 .msg/.bubble 样式，外观与主对话一致）
  function bubble(container, role, text) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + role;
    var b = document.createElement("div");
    b.className = "bubble";
    if (role === "assistant") b.innerHTML = md(text);
    else b.textContent = text;
    wrap.appendChild(b);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
    return b;
  }
  function typing(container) {
    var wrap = document.createElement("div");
    wrap.className = "msg assistant ag-typing";
    wrap.innerHTML = '<div class="bubble" style="opacity:.6">思考中…</div>';
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
    return wrap;
  }

  function autoGrow(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  // ---- 模型选择器（复用主对话探测到的模型列表 + 全局切换函数，单一数据源）----
  // 主程序在 renderer.js 里有：_modelEntries（全部 {value,label}）、currentComposerValue()、
  // applyComposerModel(value)（把选择写回全局 use_local/model）。分身对话与主对话共用这套设置。
  function modelOptionsHTML(selectedValue) {
    var entries = [];
    try { if (typeof _modelEntries !== "undefined" && _modelEntries && _modelEntries.length) entries = _modelEntries; } catch (e) {}
    var cur = (selectedValue != null && selectedValue !== "") ? selectedValue : "";
    if (!cur) { try { if (typeof currentComposerValue === "function") cur = currentComposerValue(); } catch (e) {} }
    if (!entries.length) {
      // 兜底：模型列表还没加载好时，至少把当前模型名显示出来
      var s = chatSettings();
      var val = cur || ((s.use_local ? "local::" : "cloud::") + (s.model || ""));
      return '<option value="' + esc(val) + '" selected>' + esc(s.model || "默认模型") + "</option>";
    }
    return entries.map(function (e) {
      return '<option value="' + esc(e.value) + '"' + (e.value === cur ? " selected" : "") + ">" + esc(e.label) + "</option>";
    }).join("");
  }
  function modelSelectorHTML() {
    return '<select class="ag-model-sel" id="agModelSel" title="这段对话用哪个 AI 模型（和主对话共用同一个选择）"></select>';
  }
  function wireModelSelector() {
    var sel = document.getElementById("agModelSel");
    if (!sel) return;
    sel.innerHTML = modelOptionsHTML();
    sel.addEventListener("change", function () {
      try { if (typeof applyComposerModel === "function") applyComposerModel(sel.value); } catch (e) {}
      try { if (typeof updateModelPickerLabel === "function") updateModelPickerLabel(); } catch (e) {}
    });
  }

  // ---- 智能/常规 模式（和主对话共用同一个全局 smartRouting）----
  // 智能：软件按任务自动选模型，可来回切换；常规：只用你在右边选的那个模型，不自动切换。
  function curSmart() {
    try { if (typeof smartRouting !== "undefined") return !!smartRouting; } catch (e) {}
    return false;
  }
  function modeToggleHTML() {
    return '<button class="ag-mode-btn" id="agModeBtn" title="智能：按任务自动选模型，可来回切换；常规：只用你选的模型，不自动切换"></button>';
  }
  function updateAgModeBtn() {
    var b = document.getElementById("agModeBtn");
    if (!b) return;
    var on = curSmart();
    b.textContent = on ? "🧠 智能" : "🎯 常规";
    b.classList.toggle("smart", on);
  }
  function wireModeToggle() {
    var b = document.getElementById("agModeBtn");
    if (!b) return;
    updateAgModeBtn();
    b.addEventListener("click", function () {
      try {
        if (typeof smartRouting !== "undefined") {
          smartRouting = !smartRouting;   // 改的是同一个全局，主对话也跟着变
          try { localStorage.setItem("cx_smart_routing", smartRouting ? "1" : "0"); } catch (e) {}
          if (typeof updateRouteModeBtn === "function") updateRouteModeBtn();  // 同步主对话顶栏的按钮
        }
      } catch (e) {}
      updateAgModeBtn();
    });
  }

  // ---- 每个分身【自己的】模型/模式（独立保存，互不影响、也不动主软件）----
  function agentModelValue() {
    if (state.cur && state.cur.model) {
      try { if (typeof _entryToValue === "function") return _entryToValue({ use_local: !!state.cur.use_local, model: state.cur.model }); } catch (e) {}
    }
    try { if (typeof currentComposerValue === "function") return currentComposerValue(); } catch (e) {}
    return "";
  }
  function saveAgentModel() {
    if (!state.cur) return;
    fetch(backend() + "/agents/model_save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: state.cur.slug, use_local: !!state.cur.use_local,
        model: state.cur.model || "", smart_routing: !!state.cur.smart_routing,
      }),
    }).catch(function () {});
  }
  function wireAgentModelSelector() {
    var sel = document.getElementById("agModelSel");
    if (!sel) return;
    sel.innerHTML = modelOptionsHTML(agentModelValue());
    sel.addEventListener("change", function () {
      var entry = {};
      try { if (typeof _valueToEntry === "function") entry = _valueToEntry(sel.value); } catch (e) {}
      if (!entry || entry.follow_default) return;
      state.cur.use_local = !!entry.use_local;
      state.cur.model = entry.model || "";
      saveAgentModel();
    });
  }
  function updateAgentModeBtn() {
    var b = document.getElementById("agModeBtn");
    if (!b || !state.cur) return;
    var on = !!state.cur.smart_routing;
    b.textContent = on ? "🧠 智能" : "🎯 常规";
    b.classList.toggle("smart", on);
  }
  function wireAgentModeToggle() {
    var b = document.getElementById("agModeBtn");
    if (!b) return;
    updateAgentModeBtn();
    b.addEventListener("click", function () {
      if (!state.cur) return;
      state.cur.smart_routing = !state.cur.smart_routing;
      updateAgentModeBtn();
      saveAgentModel();
    });
  }
  // 派活用分身自己的模型/模式；没存过（老分身）就回退到全局当前设置
  function agentChatParams() {
    var s = chatSettings();
    var hasOwn = !!(state.cur && state.cur.model);
    return {
      use_local: hasOwn ? !!state.cur.use_local : s.use_local,
      model: hasOwn ? state.cur.model : s.model,
      shell_enabled: s.shell_enabled,
      smart_routing: (state.cur && typeof state.cur.smart_routing === "boolean") ? state.cur.smart_routing : curSmart(),
    };
  }

  // ============================ 列表态 ============================
  // 左侧导航点「分身」时由 renderer.js 调。聪明入口：
  //   · 如果刚才正在某个分身的对话里 → 恢复回那段对话（内容不丢，不再被重置成列表）
  //   · 否则 → 显示分身卡片列表
  window.loadAgents = function () {
    ensureStyle();
    if (state.screen === "chat" && state.cur) {
      reopenCurrentChat();
      return;
    }
    goAgentsList();
  };

  // 显式回到分身卡片列表（「← 分身 / ← 返回」按钮、建好/删除分身后都走这里）
  function goAgentsList() {
    ensureStyle();
    state.screen = "list";
    var r = root();
    if (!r) return;
    r.innerHTML = '<div class="ag-empty">加载中…</div>';
    fetch(backend() + "/agents/list")
      .then(function (res) { return res.json(); })
      .then(function (d) {
        state.agents = (d && d.agents) || [];
        renderList();
      })
      .catch(function (e) {
        r.innerHTML = '<div class="ag-empty">加载失败：' + esc(e.message) + "</div>";
      });
  }

  // 切走再切回来时，把刚才那段对话原样恢复出来（用内存里的当前会话重绘，内容一字不丢）
  function reopenCurrentChat() {
    if (!state.cur) { goAgentsList(); return; }
    state.screen = "chat";
    renderWorkspace();
    loadConvos();        // 刷新左边的历史会话栏
    paintCurrentChat();  // 把当前这段对话重新画回右边
  }

  // 把内存里 state.chat.messages 画进对话区（跳过 system/tool；空对话则显示开场白）
  function paintCurrentChat() {
    var msgs = document.getElementById("agMsgs");
    if (!msgs) return;
    msgs.innerHTML = "";
    var shown = 0;
    (state.chat.messages || []).forEach(function (m) {
      var c = (m.content || "").trim();
      if (m.role === "user" && c) { bubble(msgs, "user", c); shown++; }
      else if (m.role === "assistant" && c) { bubble(msgs, "assistant", c); shown++; }
    });
    if (!shown) {
      state.chat.started = false;
      bubble(msgs, "assistant",
        "我是你的「" + (state.cur.name || "分身") + "」。我已经记住了你的判断标准，直接吩咐就行。");
    } else {
      state.chat.started = true;
    }
  }

  function renderList() {
    var r = root();
    if (!r) return;
    var cards = state.agents.map(function (a) {
      var runs = (a.stats && a.stats.runs) || 0;
      return (
        '<div class="ag-card" data-slug="' + esc(a.slug) + '">' +
          '<div class="ag-card-head">' +
            '<span class="ag-card-emoji">' + esc(a.emoji || "🎭") + "</span>" +
            '<span class="ag-card-name">' + esc(a.name || a.slug) + "</span>" +
          "</div>" +
          '<div class="ag-card-role">' + esc(a.role || "（还没写职责）") + "</div>" +
          '<div class="ag-card-foot">' +
            '<span class="ag-card-runs">用了 ' + runs + " 次</span>" +
            '<span class="ag-card-acts">' +
              '<button class="ag-mini ag-edit" data-slug="' + esc(a.slug) + '">改标准</button>' +
              '<button class="ag-mini danger ag-del" data-slug="' + esc(a.slug) + '">删</button>' +
            "</span>" +
          "</div>" +
        "</div>"
      );
    }).join("");

    var grid = state.agents.length
      ? '<div class="ag-grid">' + cards + "</div>"
      : '<div class="ag-empty">还没有分身。点右上角「＋ 创建分身」，说一句你想要个帮你做什么的分身，<br>它会反过来采访你几句，把你的判断学下来。</div>';

    r.innerHTML =
      '<div class="ag-top">' +
        '<h2>🎭 分身<span class="sub">把你的判断教给它，它替你做事，越用越懂你</span></h2>' +
        '<div class="ag-top-actions">' +
          '<button class="ag-btn primary" id="agNewBtn">＋ 创建分身</button>' +
          '<button class="ag-btn ghost" id="agRefreshBtn">🔄 刷新</button>' +
        "</div>" +
      "</div>" +
      '<div class="ag-body">' +
        '<div class="ag-intro">分身和普通「对话」的区别：普通对话每次都要重新交代背景、产出"正确但平均"；' +
        "<b>分身记得你是谁、这件事你的标准和风格</b>，不用每次重教。例如 📧 邮件管家（替你起草回信）、" +
        "🔍 选题官（按你的标准从洞察里挑题）、📊 周报助理、🛒 比价参谋…… 不限于做内容。" +
        "档案都存在本地 <code>backend/memory/agents/</code> 里。</div>" +
        grid +
      "</div>";

    document.getElementById("agNewBtn").addEventListener("click", screenCreateStart);
    document.getElementById("agRefreshBtn").addEventListener("click", goAgentsList);
    r.querySelectorAll(".ag-card").forEach(function (card) {
      card.addEventListener("click", function (e) {
        if (e.target.closest(".ag-card-acts")) return;  // 点按钮不进对话
        openChat(card.dataset.slug);
      });
    });
    r.querySelectorAll(".ag-edit").forEach(function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); editStandard(b.dataset.slug); });
    });
    r.querySelectorAll(".ag-del").forEach(function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); delAgent(b.dataset.slug); });
    });
  }

  function delAgent(slug) {
    var a = state.agents.find(function (x) { return x.slug === slug; });
    var nm = a ? (a.name || slug) : slug;
    if (!confirm("删除分身「" + nm + "」？它记住的判断标准会一起删掉，且不可恢复。")) return;
    fetch(backend() + "/agents/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: slug }),
    }).then(function () { goAgentsList(); })
      .catch(function (e) { alert("删除失败：" + e.message); });
  }

  // ============================ 创建态（访谈式）============================
  function screenCreateStart() {
    ensureStyle();
    state.screen = "create";
    state.iv = { messages: [], busy: false };
    state.editingSlug = null;
    var r = root();
    r.innerHTML =
      '<div class="ag-screen">' +
        '<div class="ag-screen-head">' +
          '<span class="emoji">🎭</span>' +
          '<span class="ttl">创建一个分身</span>' +
          '<span class="spacer"></span>' +
          modeToggleHTML() +
          modelSelectorHTML() +
          '<button class="ag-btn ghost" id="agBackBtn">← 返回</button>' +
        "</div>" +
        '<div class="ag-msgs" id="agMsgs"></div>' +
        '<div class="ag-hint">先告诉它你想要个帮你做什么的分身，它会反过来问你几个问题，把你的做事方式学下来。</div>' +
        '<div class="ag-inputbar">' +
          '<textarea class="ag-input" id="agInput" rows="1" placeholder="例如：我想要个帮我回邮件的分身"></textarea>' +
          '<button class="ag-btn primary" id="agSendBtn">开始</button>' +
        "</div>" +
      "</div>";

    document.getElementById("agBackBtn").addEventListener("click", goAgentsList);
    wireModelSelector();
    wireModeToggle();
    var input = document.getElementById("agInput");
    var sendBtn = document.getElementById("agSendBtn");
    input.addEventListener("input", function () { autoGrow(input); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
    });
    sendBtn.addEventListener("click", onSend);
    input.focus();

    function onSend() {
      var txt = input.value.trim();
      if (!txt || state.iv.busy) return;
      input.value = ""; autoGrow(input);
      var msgs = document.getElementById("agMsgs");
      bubble(msgs, "user", txt);
      state.iv.messages.push({ role: "user", content: txt });
      ivTurn();
    }
  }

  function ivTurn() {
    state.iv.busy = true;
    var msgs = document.getElementById("agMsgs");
    var sendBtn = document.getElementById("agSendBtn");
    if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = "…"; }
    var tp = typing(msgs);

    var s = chatSettings();
    fetch(backend() + "/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: state.iv.messages,
        agent_slug: INTERVIEW_SLUG,
        chat_id: "agiv" + Date.now(),
        use_local: s.use_local, model: s.model,
        shell_enabled: false,   // 访谈不需要动电脑
        smart_routing: curSmart(),   // 跟随“智能/常规”模式：常规=用你选的模型；智能=软件按任务自动选
      }),
    }).then(function (res) { return res.json(); })
      .then(function (data) {
        tp.remove();
        if (data.messages) state.iv.messages = data.messages;
        var reply = data.reply || "（无回复）";
        // 模型可能把分身草稿用 ```json``` 包裹吐出来；先尝试抠出草稿
        var draft = extractDraft(reply);
        if (draft) {
          // 把 JSON 那段从展示文本里去掉，留下它前面说的话（如果有）
          var pretext = stripJsonBlock(reply).trim();
          if (pretext) bubble(msgs, "assistant", pretext);
          renderDraft(draft);
        } else {
          bubble(msgs, "assistant", reply);
          // 把对话回写（带上助手这条），继续访谈
          state.iv.messages.push({ role: "assistant", content: reply });
        }
        state.iv.busy = false;
        if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = "发送"; }
        var input = document.getElementById("agInput");
        if (input) { input.placeholder = "回答它，或直接贴个例子…"; input.focus(); }
      })
      .catch(function (e) {
        tp.remove();
        bubble(msgs, "assistant", "连不上后端：" + e.message + "\n确认 Python 后端在运行、模型已就绪。");
        state.iv.busy = false;
        if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = "发送"; }
      });
  }

  // 从模型输出里抠出分身草稿 JSON：优先 ```json``` 代码块，其次第一个看起来完整的 {...}
  function extractDraft(text) {
    if (!text) return null;
    var obj = null;
    var m = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (m && m[1]) obj = tryParse(m[1]);
    if (!obj) {
      var i = text.indexOf("{"); var j = text.lastIndexOf("}");
      if (i >= 0 && j > i) obj = tryParse(text.slice(i, j + 1));
    }
    if (!obj || typeof obj !== "object") return null;
    // 至少要像个分身草稿（有 name 或 standard 才认）
    if (!obj.name && !obj.standard) return null;
    return {
      name: obj.name || "",
      emoji: obj.emoji || "🎭",
      slug: obj.slug || "",
      role: obj.role || "",
      standard: obj.standard || "",
      samples: Array.isArray(obj.samples) ? obj.samples : [],
    };
  }
  function tryParse(s) { try { return JSON.parse(s.trim()); } catch (e) { return null; } }
  function stripJsonBlock(text) {
    return (text || "").replace(/```(?:json)?\s*[\s\S]*?```/i, "").replace(/\{[\s\S]*\}/, "");
  }

  // ============================ 草稿卡片（新建确认 / 编辑已有）============================
  function renderDraft(draft) {
    var msgs = document.getElementById("agMsgs");
    var host = msgs || root();
    var editing = !!state.editingSlug;

    var card = document.createElement("div");
    card.className = "ag-draft";
    card.innerHTML =
      "<h3>" + (editing ? "✏️ 编辑判断标准" : "✅ 这是我整理出来的你的判断标准") + "</h3>" +
      '<div class="tip">' + (editing
        ? "改完保存即可生效。"
        : "看看对不对、按需要改，确认后这个分身就建好了。以后它做事都会照着这份标准。") + "</div>" +
      '<div class="ag-row2">' +
        '<div class="ag-field emoji"><label>图标</label><input id="dfEmoji" value="' + esc(draft.emoji || "🎭") + '" maxlength="4"></div>' +
        '<div class="ag-field grow"><label>名字</label><input id="dfName" value="' + esc(draft.name || "") + '" placeholder="如 邮件管家"></div>' +
      "</div>" +
      '<div class="ag-field"><label>职责（一句话）</label><input id="dfRole" value="' + esc(draft.role || "") + '" placeholder="如 帮我起草和回复邮件"></div>' +
      '<div class="ag-field"><label>判断标准（★最关键，它就照这个做事）</label>' +
        '<textarea id="dfStandard" rows="7" placeholder="把你的语气、底线、各种情况怎么处理写清楚">' + esc(draft.standard || "") + "</textarea></div>" +
      '<div class="ag-field"><label>风格样本（可选，让它学你的味儿）</label><div id="dfSamples"></div>' +
        '<button class="ag-btn ghost" id="dfAddSample" style="align-self:flex-start;margin-top:4px;">＋ 添加样本</button></div>' +
      '<div class="ag-draft-acts">' +
        '<button class="ag-btn primary" id="dfSave">' + (editing ? "保存修改" : "建好这个分身") + "</button>" +
        (editing
          ? '<button class="ag-btn ghost" id="dfCancel">取消</button>'
          : '<button class="ag-btn ghost" id="dfRedo">重新访谈</button>') +
      "</div>";
    host.appendChild(card);
    if (msgs) msgs.scrollTop = msgs.scrollHeight;

    // 样本编辑器
    var samplesBox = card.querySelector("#dfSamples");
    function addSampleRow(s) {
      s = s || { title: "", content: "" };
      var row = document.createElement("div");
      row.className = "ag-samples-row";
      row.innerHTML =
        '<button class="ag-sample-del" title="删除">✕</button>' +
        '<input class="s-title" placeholder="样本简述（如 回供应商催款）" value="' + esc(s.title || "") + '">' +
        '<textarea class="s-content" placeholder="把这个满意的例子原文贴进来">' + esc(s.content || "") + "</textarea>";
      row.querySelector(".ag-sample-del").addEventListener("click", function () { row.remove(); });
      samplesBox.appendChild(row);
    }
    (draft.samples || []).forEach(addSampleRow);
    card.querySelector("#dfAddSample").addEventListener("click", function () { addSampleRow(); });

    card.querySelector("#dfSave").addEventListener("click", function () {
      var name = card.querySelector("#dfName").value.trim();
      var standard = card.querySelector("#dfStandard").value.trim();
      if (!name) { alert("给分身起个名字吧。"); return; }
      if (!standard) { alert("判断标准是分身的灵魂，至少写一两条吧。"); return; }
      var samples = [];
      samplesBox.querySelectorAll(".ag-samples-row").forEach(function (row) {
        var t = row.querySelector(".s-title").value.trim();
        var c = row.querySelector(".s-content").value.trim();
        if (c) samples.push({ title: t, content: c });
      });
      var payload = {
        name: name,
        emoji: card.querySelector("#dfEmoji").value.trim() || "🎭",
        role: card.querySelector("#dfRole").value.trim(),
        standard: standard,
        samples: samples,
      };
      if (state.editingSlug) payload.slug = state.editingSlug;
      else if (draft.slug) payload.slug = draft.slug;   // 用模型给的英文 slug
      // 新建分身时，把"创建它时用的模型/模式"作为它独立的初始设置（之后可在它自己的工作区里改）
      if (!state.editingSlug) {
        var s = chatSettings();
        payload.use_local = s.use_local;
        payload.model = s.model || "";
        try { payload.smart_routing = (typeof smartRouting !== "undefined") ? !!smartRouting : true; } catch (e) { payload.smart_routing = true; }
      }

      var btn = card.querySelector("#dfSave");
      btn.disabled = true; btn.textContent = "保存中…";
      fetch(backend() + "/agents/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(function (res) { return res.json(); })
        .then(function (d) {
          if (d && d.ok) {
            toast(state.editingSlug ? "已保存修改" : "分身「" + name + "」建好了");
            goAgentsList();
          } else {
            btn.disabled = false; btn.textContent = "保存";
            alert("保存失败：" + ((d && d.message) || "未知错误"));
          }
        })
        .catch(function (e) {
          btn.disabled = false; btn.textContent = "保存";
          alert("保存失败：" + e.message);
        });
    });

    var redo = card.querySelector("#dfRedo");
    if (redo) redo.addEventListener("click", screenCreateStart);
    var cancel = card.querySelector("#dfCancel");
    if (cancel) cancel.addEventListener("click", goAgentsList);
  }

  // 编辑已有分身的标准：直接复用草稿卡片（编辑态）
  function editStandard(slug) {
    ensureStyle();
    fetch(backend() + "/agents/get?slug=" + encodeURIComponent(slug))
      .then(function (res) { return res.json(); })
      .then(function (d) {
        if (!d || !d.agent) { alert("读取失败"); return; }
        state.screen = "create";
        state.editingSlug = slug;
        var r = root();
        r.innerHTML =
          '<div class="ag-screen">' +
            '<div class="ag-screen-head">' +
              '<span class="emoji">' + esc(d.agent.emoji || "🎭") + "</span>" +
              '<span class="ttl">' + esc(d.agent.name || slug) + "</span>" +
              '<span class="spacer"></span>' +
              '<button class="ag-btn ghost" id="agBackBtn">← 返回</button>' +
            "</div>" +
            '<div class="ag-msgs" id="agMsgs"></div>' +
          "</div>";
        document.getElementById("agBackBtn").addEventListener("click", goAgentsList);
        renderDraft(d.agent);
      })
      .catch(function (e) { alert("读取失败：" + e.message); });
  }

  // ============================ 派活态（专属对话）============================
  // ============================ 派活态（专属工作区：会话栏 + 对话）============================
  function newConvoId() {
    return "c-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6);
  }

  function openChat(slug, targetCid) {
    ensureStyle();
    fetch(backend() + "/agents/get?slug=" + encodeURIComponent(slug))
      .then(function (res) { return res.json(); })
      .then(function (d) {
        if (!d || !d.agent) { alert("读取失败"); return; }
        state.screen = "chat";
        state.cur = d.agent;
        // 老分身没存过自己的模型时，用主软件当前模型作为初始显示（用户在这里改了就会存进这个分身）
        if (!state.cur.model) {
          var s0 = chatSettings();
          state.cur.model = s0.model || "";
          state.cur.use_local = s0.use_local;
        }
        state.convos = [];
        state.chat = { id: newConvoId(), title: "", messages: [], busy: false, started: false };
        renderWorkspace();
        // 拉这个分身的历史会话：指定了就打开指定那段；否则默认打开最近一段，没有就停在新对话
        loadConvos(function () {
          if (targetCid) loadConvo(targetCid);
          else if (state.convos.length) loadConvo(state.convos[0].id);
          else startBlankChat();
        });
      })
      .catch(function (e) { alert("读取失败：" + e.message); });
  }

  function renderWorkspace() {
    var a = state.cur;
    var r = root();
    r.innerHTML =
      '<div class="ag-ws">' +
        '<div class="ag-rail">' +
          '<div class="ag-rail-head">' +
            '<span class="emoji">' + esc(a.emoji || "🎭") + "</span>" +
            '<span class="nm">' + esc(a.name || a.slug) + "</span>" +
            '<button class="ag-mini" id="agBackBtn" title="回到分身列表">← 分身</button>' +
          "</div>" +
          '<button class="ag-btn primary ag-rail-new" id="agNewConvoBtn">＋ 新对话</button>' +
          '<div class="ag-rail-label">历史对话</div>' +
          '<div class="ag-rail-list" id="agRailList"></div>' +
        "</div>" +
          '<div class="ag-ws-main">' +
          '<div class="ag-screen-head">' +
            '<span class="role">' + esc(a.role || "") + "</span>" +
            '<span class="spacer"></span>' +
            modeToggleHTML() +
            modelSelectorHTML() +
            '<button class="ag-btn ghost" id="agAutoBtn" title="让它每天定时自动干一件事">⚙️ 自动化</button>' +
            '<button class="ag-btn ghost" id="agStdBtn" title="看它现在的判断标准">📋 它的标准</button>' +
          "</div>" +
          '<div class="ag-msgs" id="agMsgs"></div>' +
          '<div class="ag-inputbar">' +
            '<textarea class="ag-input" id="agInput" rows="1" placeholder="直接吩咐 ' + esc(a.name || "它") + ' 做事，它会按你的标准来…"></textarea>' +
            '<button class="ag-btn ghost" id="agFbBtn" title="把刚才的修正记进它的标准，下次就记住">📌 记进标准</button>' +
            '<button class="ag-btn primary" id="agSendBtn">发送</button>' +
          "</div>" +
        "</div>" +
      "</div>";

    document.getElementById("agBackBtn").addEventListener("click", goAgentsList);
    document.getElementById("agNewConvoBtn").addEventListener("click", function () { startBlankChat(); });
    document.getElementById("agStdBtn").addEventListener("click", function () { showStandardPeek(); });
    document.getElementById("agFbBtn").addEventListener("click", function () { openFeedback(); });
    document.getElementById("agAutoBtn").addEventListener("click", function () { openAutomation(); });
    wireAgentModelSelector();   // 这个分身自己的模型（独立）
    wireAgentModeToggle();      // 这个分身自己的智能/常规模式（独立）

    var input = document.getElementById("agInput");
    var sendBtn = document.getElementById("agSendBtn");
    input.addEventListener("input", function () { autoGrow(input); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
    });
    sendBtn.addEventListener("click", onSend);

    function onSend() {
      var txt = input.value.trim();
      if (!txt || state.chat.busy) return;
      input.value = ""; autoGrow(input);
      var msgs = document.getElementById("agMsgs");
      if (!state.chat.started) { msgs.innerHTML = ""; state.chat.started = true; }  // 清掉开场白
      bubble(msgs, "user", txt);
      state.chat.messages.push({ role: "user", content: txt });
      chatLoop({});
    }
  }

  // 开一段空白新对话
  function startBlankChat() {
    state.chat = { id: newConvoId(), title: "", messages: [], busy: false, started: false };
    var msgs = document.getElementById("agMsgs");
    if (msgs) {
      msgs.innerHTML = "";
      bubble(msgs, "assistant",
        "我是你的「" + (state.cur.name || "分身") + "」。我已经记住了你的判断标准，直接吩咐就行。");
    }
    var input = document.getElementById("agInput");
    if (input) input.focus();
    renderRail();
  }

  // 拉这个分身的历史会话列表
  function loadConvos(done) {
    fetch(backend() + "/agents/convos?slug=" + encodeURIComponent(state.cur.slug))
      .then(function (res) { return res.json(); })
      .then(function (d) {
        state.convos = (d && d.convos) || [];
        renderRail();
        if (typeof done === "function") done();
      })
      .catch(function () { state.convos = []; renderRail(); if (typeof done === "function") done(); });
  }

  function renderRail() {
    var list = document.getElementById("agRailList");
    if (!list) return;
    var items = state.convos.slice();
    var hasCur = items.some(function (c) { return c.id === state.chat.id; });
    var rows = "";
    // 还没存盘的新对话：顶部给个临时条，给即时反馈
    if (!hasCur && state.chat.started === false) {
      rows += '<div class="ag-convo active"><div class="ct">新对话</div><div class="cm">还没说话</div></div>';
    }
    rows += items.map(function (c) {
      var act = (c.id === state.chat.id) ? " active" : "";
      var when = (c.updated_at || "").replace("T", " ").slice(5, 16);
      return '<div class="ag-convo' + act + '" data-id="' + esc(c.id) + '">' +
        '<button class="ag-convo-del" data-id="' + esc(c.id) + '" title="删除">✕</button>' +
        '<div class="ct">' + esc(c.title || "新对话") + "</div>" +
        '<div class="cm">' + esc(when) + " · " + (c.turns || 0) + " 轮</div>" +
      "</div>";
    }).join("");
    list.innerHTML = rows || '<div class="ag-rail-empty">还没有历史对话。<br>直接在右边吩咐它做第一件事吧。</div>';

    list.querySelectorAll(".ag-convo[data-id]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        if (e.target.closest(".ag-convo-del")) return;
        loadConvo(el.dataset.id);
      });
    });
    list.querySelectorAll(".ag-convo-del").forEach(function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); delConvo(b.dataset.id); });
    });
  }

  // 点开一段历史会话，灌回对话区接着聊
  function loadConvo(cid) {
    fetch(backend() + "/agents/convo?slug=" + encodeURIComponent(state.cur.slug) + "&id=" + encodeURIComponent(cid))
      .then(function (res) { return res.json(); })
      .then(function (d) {
        if (!d || !d.convo) { alert("读取失败"); return; }
        var c = d.convo;
        state.chat = { id: c.id, title: c.title || "", messages: (c.messages || []).slice(), busy: false, started: true };
        var msgs = document.getElementById("agMsgs");
        msgs.innerHTML = "";
        (c.messages || []).forEach(function (m) {
          var content = (m.content || "").trim();
          if (m.role === "user" && content) bubble(msgs, "user", content);
          else if (m.role === "assistant" && content) bubble(msgs, "assistant", content);
          // system / tool / 空内容 不渲染
        });
        renderRail();
        var input = document.getElementById("agInput");
        if (input) input.focus();
      })
      .catch(function (e) { alert("读取失败：" + e.message); });
  }

  // 删一段历史会话
  function delConvo(cid) {
    var c = state.convos.find(function (x) { return x.id === cid; });
    if (!confirm("删除会话「" + ((c && c.title) || "这段对话") + "」？不可恢复。")) return;
    fetch(backend() + "/agents/convo_delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: state.cur.slug, id: cid }),
    }).then(function () {
      var wasOpen = (state.chat.id === cid);
      loadConvos(function () { if (wasOpen) startBlankChat(); });
    }).catch(function (e) { alert("删除失败：" + e.message); });
  }

  // 自动落盘当前会话（每轮回复后调）。失败静默，不打断对话。
  function saveConvo() {
    if (!state.cur || !state.chat || !state.chat.messages.length) return;
    fetch(backend() + "/agents/convo_save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: state.cur.slug, id: state.chat.id,
        title: state.chat.title || "", messages: state.chat.messages,
      }),
    }).then(function (res) { return res.json(); })
      .then(function (d) {
        if (d && d.ok) {
          state.chat.title = d.title || state.chat.title;
          loadConvos();
          maybeAITitle();   // 第一轮回复后，用 AI 起个更贴切的中文标题
        }
      })
      .catch(function () {});
  }

  // 用软件自带的 /summarize_title 给这段对话起个简短中文标题（只在第一轮回复后做一次）
  function maybeAITitle() {
    if (!state.cur || !state.chat || state.chat._titled) return;
    var hasAsst = (state.chat.messages || []).some(function (m) {
      return m.role === "assistant" && (m.content || "").trim();
    });
    if (!hasAsst) return;
    state.chat._titled = true;   // 立刻标记，避免重复请求
    var convoId = state.chat.id;
    var p = agentChatParams();
    fetch(backend() + "/summarize_title", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: state.chat.messages, use_local: p.use_local, model: p.model }),
    }).then(function (res) { return res.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.title) return;
        // 只有用户没切到别的会话时才应用
        if (state.chat.id !== convoId) return;
        state.chat.title = d.title;
        fetch(backend() + "/agents/convo_save", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slug: state.cur.slug, id: convoId, title: d.title, messages: state.chat.messages }),
        }).then(function () { loadConvos(); }).catch(function () {});
      })
      .catch(function () {});
  }

  function chatLoop(approvals) {
    state.chat.busy = true;
    var msgs = document.getElementById("agMsgs");
    var sendBtn = document.getElementById("agSendBtn");
    if (sendBtn) sendBtn.disabled = true;
    var tp = typing(msgs);

    var s = agentChatParams();   // 用这个分身自己的模型/模式（独立于主软件和其它分身）
    fetch(backend() + "/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: state.chat.messages,
        agent_slug: state.cur.slug,
        approvals: approvals || {},
        chat_id: "agchat" + Date.now(),
        use_local: s.use_local, model: s.model,
        shell_enabled: s.shell_enabled,
        smart_routing: s.smart_routing,
      }),
    }).then(function (res) { return res.json(); })
      .then(function (data) {
        tp.remove();
        if (data.messages) state.chat.messages = data.messages;
        if (data.pending) {
          // 分身想动电脑（写文件/执行命令等危险操作），内联确认
          chatApproval(data.pending);
          state.chat.busy = false;
          if (sendBtn) sendBtn.disabled = false;
          return;
        }
        bubble(msgs, "assistant", data.reply || "（无回复）");
        state.chat.busy = false;
        if (sendBtn) sendBtn.disabled = false;
        var input = document.getElementById("agInput");
        if (input) input.focus();
        saveConvo();   // 自动存这段对话，重开还在
      })
      .catch(function (e) {
        tp.remove();
        bubble(msgs, "assistant", "连不上后端：" + e.message + "\n确认 Python 后端在运行、模型已就绪。");
        state.chat.busy = false;
        if (sendBtn) sendBtn.disabled = false;
      });
  }

  // 内联危险操作确认（最小版：全部批准 / 全部拒绝）
  function chatApproval(pending) {
    var msgs = document.getElementById("agMsgs");
    var items = (pending.batch && pending.batch.length) ? pending.batch : [{
      tool_call_id: pending.tool_call_id, name: pending.name, args: pending.args,
      title: pending.title || ("执行操作：" + pending.name), detail: pending.detail || "",
    }];
    var box = document.createElement("div");
    box.className = "ag-approval";
    box.innerHTML =
      '<div class="ttl">⚠️ 分身想执行 ' + items.length + " 个操作，需要你确认</div>" +
      items.map(function (it) {
        return "<div>· " + esc(it.title) + (it.detail ? '<div style="opacity:.7;font-size:12px;margin-left:10px">' + esc(it.detail) + "</div>" : "") + "</div>";
      }).join("") +
      '<div class="acts">' +
        '<button class="ag-btn primary" id="apYes">批准执行</button>' +
        '<button class="ag-btn ghost" id="apNo">拒绝</button>' +
      "</div>";
    msgs.appendChild(box);
    msgs.scrollTop = msgs.scrollHeight;

    function decide(ok) {
      var m = {};
      items.forEach(function (it) { m[it.tool_call_id] = ok; });
      box.querySelector(".acts").innerHTML = '<span style="opacity:.7">' + (ok ? "已批准 ✓" : "已拒绝 ✕") + "</span>";
      chatLoop(m);
    }
    box.querySelector("#apYes").addEventListener("click", function () { decide(true); });
    box.querySelector("#apNo").addEventListener("click", function () { decide(false); });
  }

  // 「📌 记进标准」内联面板：默认填上最后一条用户消息（通常就是那句修正），可编辑后保存
  function openFeedback() {
    if (!state.cur) return;
    var msgs = document.getElementById("agMsgs");
    if (msgs.querySelector(".ag-feedback")) return;  // 已经开着了
    var lastUser = "";
    for (var i = state.chat.messages.length - 1; i >= 0; i--) {
      if (state.chat.messages[i].role === "user") { lastUser = state.chat.messages[i].content; break; }
    }
    var box = document.createElement("div");
    box.className = "ag-feedback";
    box.innerHTML =
      '<div style="font-size:12px;color:#2b6cff;font-weight:600;margin-bottom:6px;">📌 把这条修正记进它的判断标准（下次它就记住）</div>' +
      '<textarea id="fbText" placeholder="例如：回复别超过三句话 / 报价类一律先反问我">' + esc(lastUser) + "</textarea>" +
      '<div class="acts"><button class="ag-btn primary" id="fbSave">记进标准</button>' +
      '<button class="ag-btn ghost" id="fbCancel">取消</button></div>';
    msgs.appendChild(box);
    msgs.scrollTop = msgs.scrollHeight;
    box.querySelector("#fbText").focus();

    box.querySelector("#fbCancel").addEventListener("click", function () { box.remove(); });
    box.querySelector("#fbSave").addEventListener("click", function () {
      var fb = box.querySelector("#fbText").value.trim();
      if (!fb) { box.remove(); return; }
      var btn = box.querySelector("#fbSave");
      btn.disabled = true; btn.textContent = "保存中…";
      fetch(backend() + "/agents/update_standard", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: state.cur.slug, feedback: fb }),
      }).then(function (res) { return res.json(); })
        .then(function (d) {
          if (d && d.ok) {
            state.cur.standard = d.standard;   // 更新内存，后续这轮对话也会带上新标准
            box.remove();
            bubble(msgs, "assistant", "收到，我把「" + fb + "」加进我的标准了，以后照办。");
            toast("已记进标准");
          } else {
            btn.disabled = false; btn.textContent = "记进标准";
            alert("保存失败：" + ((d && d.message) || "未知错误"));
          }
        })
        .catch(function (e) {
          btn.disabled = false; btn.textContent = "记进标准";
          alert("保存失败：" + e.message);
        });
    });
  }

  // ⚙️ 自动化设置面板：多任务。点某个任务的「保存」后，它会收进下面的「已保存」(可折叠)，
  // 保存键置灰并出现「编辑」；点「编辑」该任务回到可编辑、保存键重新激活。每个任务各自设
  // 时间和模型，到点这个分身自动跑、结果存进历史对话并在桌面右下角弹窗提醒。
  var _AUTO_COLLAPSE_KEY = "ag_auto_saved_collapsed";

  function openAutomation() {
    if (!state.cur) return;
    var msgs = document.getElementById("agMsgs");
    if (msgs.querySelector(".ag-auto")) { msgs.querySelector(".ag-auto").scrollIntoView({ block: "center" }); return; }

    // working copy；给每个任务打一个本地状态：editing（可编辑）/ saved（已保存）。这个状态只在前端用，不写回后端。
    var tasks = (((state.cur.automation || {}).tasks) || []).map(function (t) {
      var nt = Object.assign({}, t); nt._status = "saved"; return nt;
    });
    var collapsed = false;
    try { collapsed = localStorage.getItem(_AUTO_COLLAPSE_KEY) === "1"; } catch (e) {}

    var box = document.createElement("div");
    box.className = "ag-auto";
    msgs.appendChild(box);

    function newTask() {
      return {
        id: "t-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6),
        name: "", enabled: true, prompt: "", time: "09:00",
        use_local: !!state.cur.use_local, model: state.cur.model || "",
        _status: "editing",
      };
    }
    function findTask(id) { for (var i = 0; i < tasks.length; i++) if (tasks[i].id === id) return tasks[i]; return null; }
    function taskModelValue(t) {
      if (t && t.model) { try { if (typeof _entryToValue === "function") return _entryToValue({ use_local: !!t.use_local, model: t.model }); } catch (e) {} }
      try { if (typeof currentComposerValue === "function") return currentComposerValue(); } catch (e) {}
      return "";
    }
    function modelLabel(t) { return (t && t.model) ? t.model : "（沿用当前模型）"; }

    // 把「编辑中」卡片里的输入值收回 tasks（按 id 匹配；已保存的行没有输入框，不收）
    function collectFromDOM() {
      box.querySelectorAll(".ag-task[data-id]").forEach(function (card) {
        var t = findTask(card.getAttribute("data-id"));
        if (!t) return;
        var en = card.querySelector(".tEnabled"); if (en) t.enabled = en.checked;
        var tm = card.querySelector(".tTime"); if (tm) t.time = tm.value || "09:00";
        var pr = card.querySelector(".tPrompt"); if (pr) t.prompt = pr.value.trim();
        var nm = card.querySelector(".tName"); if (nm) t.name = nm.value.trim();
        var sel = card.querySelector(".tModel");
        if (sel) {
          var entry = {};
          try { if (typeof _valueToEntry === "function") entry = _valueToEntry(sel.value); } catch (e) {}
          if (entry && !entry.follow_default) { t.use_local = !!entry.use_local; t.model = entry.model || ""; }
        }
      });
    }

    // —— 编辑中的任务：完整可编辑卡片（含激活的「保存」键）——
    function editCardHTML(t) {
      return '<div class="ag-task" data-id="' + esc(t.id) + '">' +
        '<div class="trow">' +
          '<label class="sw"><input type="checkbox" class="tEnabled"' + (t.enabled ? " checked" : "") + "> 启用</label>" +
          '<span class="lbl">每天</span><input type="time" class="tTime" value="' + esc(t.time || "09:00") + '">' +
          '<span class="lbl">用模型</span><select class="ag-model-sel tModel"></select>' +
          '<span class="spc"></span>' +
          '<button class="ag-btn mini primary tSave" data-id="' + esc(t.id) + '">保存</button>' +
          '<button class="ag-btn mini tRun" data-id="' + esc(t.id) + '">▶ 跑一次</button>' +
          '<button class="ag-btn mini danger tDel" data-id="' + esc(t.id) + '">删</button>' +
        "</div>" +
        '<input type="text" class="tName" placeholder="任务名（选填，如：早间AI简报）" value="' + esc(t.name || "") + '">' +
        '<textarea class="tPrompt" placeholder="要它自动做什么…例如：查今天 OpenAI / Anthropic / NVIDIA / GitHub Trending 的 AI 动态，每条带来源链接、机会、风险，最后列出今天值得做的 3 件事。">' + esc(t.prompt || "") + "</textarea>" +
      "</div>";
    }

    // —— 已保存的任务：紧凑只读行（置灰「已保存」标 + 「编辑」键）——
    function savedRowHTML(t) {
      var nm = (t.name || "").trim() || "(未命名任务)";
      var stateTxt = t.enabled ? '<span class="ag-dot on"></span>已启用' : '<span class="ag-dot"></span>未启用';
      return '<div class="ag-saved-row" data-id="' + esc(t.id) + '">' +
        '<div class="sv-main">' +
          '<span class="ag-pill saved">✓ 已保存</span>' +
          '<span class="sv-name" title="' + esc(nm) + '">' + esc(nm) + "</span>" +
        "</div>" +
        '<div class="sv-meta">' + stateTxt + " · 每天 " + esc(t.time || "09:00") + " · " + esc(modelLabel(t)) + "</div>" +
        '<div class="sv-acts">' +
          '<button class="ag-btn mini tEdit" data-id="' + esc(t.id) + '">编辑</button>' +
          '<button class="ag-btn mini tRun" data-id="' + esc(t.id) + '">▶ 跑一次</button>' +
          '<button class="ag-btn mini danger tDel" data-id="' + esc(t.id) + '">删</button>' +
        "</div>" +
      "</div>";
    }

    function renderAuto() {
      var editing = tasks.filter(function (t) { return t._status !== "saved"; });
      var saved = tasks.filter(function (t) { return t._status === "saved"; });

      var editHTML = editing.map(editCardHTML).join("");
      var emptyHint = (!editing.length && !saved.length) ? '<div class="ag-noauto">还没有任务，点下面「＋ 添加任务」。</div>' : "";

      var savedBlock = "";
      if (saved.length) {
        savedBlock =
          '<div class="ag-saved">' +
            '<div class="ag-saved-head" id="agSavedHead">' +
              '<span class="chev">' + (collapsed ? "▸" : "▾") + "</span>" +
              "<b>已保存</b><span class=\"cnt\">" + saved.length + "</span>" +
              '<span class="hint">' + (collapsed ? "点击展开" : "点击折叠") + "</span>" +
            "</div>" +
            '<div class="ag-saved-list" style="' + (collapsed ? "display:none;" : "") + '">' + saved.map(savedRowHTML).join("") + "</div>" +
          "</div>";
      }

      box.innerHTML =
        "<h4>⚙️ 自动化 · 让「" + esc(state.cur.name || "它") + "」按时自己干活</h4>" +
        '<div class="tip">可以加<b>多个任务</b>，每个任务各自设<b>时间</b>和<b>模型</b>。点某个任务的<b>保存</b>后，' +
        "它会收进下面的<b>「已保存」</b>(可折叠)，保存键置灰并出现<b>「编辑」</b>；想改再点编辑即可。" +
        "到点这个分身会用对应模型自动做，结果存进历史对话（标题带 🤖）并<b>在桌面右下角弹窗提醒</b>。" +
        "只做查资料这类安全操作，不动你的文件。软件没开的时段不跑；当天开机后若过了时间还没跑过，会补跑一次。</div>" +
        '<div class="ag-tasks">' + editHTML + "</div>" +
        emptyHint +
        savedBlock +
        '<div class="acts">' +
          '<button class="ag-btn ghost" id="agAutoAdd">＋ 添加任务</button>' +
          '<button class="ag-btn ghost" id="agAutoClose">关闭</button>' +
        "</div>" +
        '<div class="status" id="agAutoStatus"></div>';

      // 填充每个「编辑中」任务的模型下拉
      box.querySelectorAll(".ag-task[data-id]").forEach(function (card) {
        var t = findTask(card.getAttribute("data-id"));
        var sel = card.querySelector(".tModel");
        if (t && sel) sel.innerHTML = modelOptionsHTML(taskModelValue(t));
      });

      // 顶部按钮
      box.querySelector("#agAutoAdd").addEventListener("click", function () {
        collectFromDOM(); tasks.push(newTask()); renderAuto();
      });
      box.querySelector("#agAutoClose").addEventListener("click", function () { box.remove(); });

      // 折叠 / 展开「已保存」
      var head = box.querySelector("#agSavedHead");
      if (head) head.addEventListener("click", function () {
        collapsed = !collapsed;
        try { localStorage.setItem(_AUTO_COLLAPSE_KEY, collapsed ? "1" : "0"); } catch (e) {}
        renderAuto();
      });

      // 保存（单个任务）
      box.querySelectorAll(".tSave").forEach(function (btn) {
        btn.addEventListener("click", function () { saveTask(btn.getAttribute("data-id"), btn); });
      });
      // 编辑（把已保存任务调回可编辑）
      box.querySelectorAll(".tEdit").forEach(function (btn) {
        btn.addEventListener("click", function () {
          collectFromDOM();
          var t = findTask(btn.getAttribute("data-id"));
          if (t) { t._status = "editing"; renderAuto(); }
        });
      });
      // 删除（移除并持久化）
      box.querySelectorAll(".tDel").forEach(function (btn) {
        btn.addEventListener("click", function () {
          collectFromDOM();
          var id = btn.getAttribute("data-id");
          tasks = tasks.filter(function (t) { return t.id !== id; });
          persist(function () { renderAuto(); var st = box.querySelector("#agAutoStatus"); if (st) st.textContent = "已删除"; });
        });
      });
      // 跑一次
      box.querySelectorAll(".tRun").forEach(function (btn) {
        btn.addEventListener("click", function () { runTask(btn.getAttribute("data-id"), btn); });
      });
    }

    // 持久化当前 tasks 到后端（整体替换）。成功后用后端回填（带回 last_run 等），并保留每个任务的本地 _status。
    function persist(cb, onErr) {
      var payload = tasks.map(function (t) {
        return { id: t.id, name: t.name, enabled: t.enabled, prompt: t.prompt,
                 time: t.time, use_local: t.use_local, model: t.model };
      });
      fetch(backend() + "/agents/automation_save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: state.cur.slug, tasks: payload }),
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok) {
            state.cur.automation = d.automation;
            var statusById = {};
            tasks.forEach(function (t) { statusById[t.id] = t._status; });
            tasks = (d.automation.tasks || []).map(function (t) {
              var nt = Object.assign({}, t);
              nt._status = statusById[t.id] || "saved";
              return nt;
            });
            if (cb) cb();
          } else { alert("保存失败：" + ((d && d.message) || "未知错误")); if (onErr) onErr(); }
        }).catch(function (e) { alert("保存失败：" + e.message); if (onErr) onErr(); });
    }

    function saveTask(id, btn) {
      collectFromDOM();
      var t = findTask(id);
      if (!t) return;
      if (t.enabled && !t.prompt) { alert("这个任务开了「启用」但还没写要做什么。"); return; }
      if (btn) { btn.disabled = true; btn.textContent = "保存中…"; }
      persist(function () {
        var nt = findTask(id);
        if (nt) nt._status = "saved";
        collapsed = false;                 // 展开已保存区，让用户看到刚收进去的
        try { localStorage.setItem(_AUTO_COLLAPSE_KEY, "0"); } catch (e) {}
        renderAuto();
        var st = box.querySelector("#agAutoStatus");
        if (st) st.textContent = "✓ 已保存";
        toast("已保存");
      }, function () {
        if (btn) { btn.disabled = false; btn.textContent = "保存"; }
      });
    }

    function runTask(id, btn) {
      collectFromDOM();
      // 先确保已保存（跑的是后端存着的版本），再触发运行
      persist(function () {
        var t = findTask(id); if (!t) return;
        var old = btn ? btn.textContent : "";
        if (btn) { btn.disabled = true; btn.textContent = "运行中…"; }
        fetch(backend() + "/agents/automation_run", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slug: state.cur.slug, task_id: id }),
        }).then(function (r) { return r.json(); })
          .then(function (d) {
            var st = box.querySelector("#agAutoStatus");
            if (st) st.textContent = (d && d.ok) ? "🤖 已在后台运行，完成后会在桌面右下角弹窗提醒，并出现在左边历史里。" : ("出错：" + ((d && d.message) || ""));
            toast(d && d.ok ? "已触发运行" : "运行失败");
            setTimeout(function () { loadConvos(); }, 4000);
            setTimeout(function () { loadConvos(); if (btn) { btn.disabled = false; btn.textContent = old; } }, 12000);
          }).catch(function (e) {
            var st = box.querySelector("#agAutoStatus"); if (st) st.textContent = "运行失败：" + e.message;
            if (btn) { btn.disabled = false; btn.textContent = old; }
          });
      });
    }

    renderAuto();
    box.scrollIntoView({ block: "center" });
  }

  // 看它当前的判断标准（只读弹层）
  function showStandardPeek() {
    if (!state.cur) return;
    var msgs = document.getElementById("agMsgs");
    bubble(msgs, "assistant",
      "**我现在的判断标准：**\n\n" + (state.cur.standard || "（还没有，去「改标准」里补充）"));
  }

  // ============================ 自动化结果弹窗（全局，任意界面都能弹）============================
  var _notifTimer = null;
  var _notifShowing = false;

  function startNotifPoller() {
    if (_notifTimer) return;
    function check() {
      var b; try { b = backend(); } catch (e) { return; }
      if (!b) return;
      fetch(b + "/agents/notifications").then(function (r) { return r.json(); })
        .then(function (d) { if (d && d.ok && d.items && d.items.length) showNotifs(d.items); })
        .catch(function () {});
    }
    _notifTimer = setInterval(check, 20000);
    setTimeout(check, 6000);   // 启动几秒后先查一次
  }

  function showNotifs(items) {
    if (_notifShowing || !items || !items.length) return;
    _notifShowing = true;
    showOneNotif(items, 0);
  }

  function markSeen(id) {
    var b; try { b = backend(); } catch (e) { return; }
    fetch(b + "/agents/notifications/seen", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [id] }),
    }).catch(function () {});
  }

  function showOneNotif(items, idx) {
    if (idx >= items.length) { _notifShowing = false; return; }
    var n = items[idx];
    function next() { markSeen(n.id); showOneNotif(items, idx + 1); }
    // 取这条结果的正文，连同"哪个分身、什么报告"一起显示
    fetch(backend() + "/agents/convo?slug=" + encodeURIComponent(n.slug) + "&id=" + encodeURIComponent(n.conversation_id))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var content = "";
        if (d && d.ok && d.convo && d.convo.messages) {
          var asst = d.convo.messages.filter(function (m) { return m.role === "assistant" && (m.content || "").trim(); });
          if (asst.length) content = asst[asst.length - 1].content;
        }
        buildNotifModal(n, content, next);
      })
      .catch(function () { buildNotifModal(n, "", next); });
  }

  function buildNotifModal(n, content, onClose) {
    ensureStyle();
    var ov = document.createElement("div");
    ov.className = "ag-modal-ov";
    var rendered;
    try { rendered = (typeof renderMarkdown === "function") ? renderMarkdown(content || "（无内容）") : esc(content || "（无内容）"); }
    catch (e) { rendered = esc(content || "（无内容）"); }
    ov.innerHTML =
      '<div class="ag-modal">' +
        '<div class="ag-modal-head">' +
          '<span class="em">' + esc(n.agent_emoji || "🤖") + "</span>" +
          "<div><div class=\"t1\">" + esc(n.agent_name || "分身") + " 完成了一个自动任务</div>" +
          '<div class="t2">' + esc(n.title || "") + "</div></div>" +
        "</div>" +
        '<div class="ag-modal-body">' + rendered + "</div>" +
        '<div class="ag-modal-foot">' +
          '<button class="ag-btn ghost" id="agNOpen">去这个分身查看</button>' +
          '<button class="ag-btn primary" id="agNOk">知道了</button>' +
        "</div>" +
      "</div>";
    document.body.appendChild(ov);
    function close() { if (ov.parentNode) ov.parentNode.removeChild(ov); if (onClose) onClose(); }
    ov.querySelector("#agNOk").addEventListener("click", close);
    ov.querySelector("#agNOpen").addEventListener("click", function () {
      var slug = n.slug, cid = n.conversation_id;
      close();
      try { var nb = document.querySelector('.nav-item[data-view="agents"]'); if (nb) nb.click(); } catch (e) {}
      setTimeout(function () { openChat(slug, cid); }, 60);
    });
    ov.addEventListener("click", function (e) { if (e.target === ov) close(); });
  }

  // 任务完成通知改由主进程在桌面右下角弹小浮窗（见 main.js），这里不再弹软件内大弹层。
  // 只暴露一个全局：点浮窗「查看」时切到分身页并打开那条自动结果对话。
  window.openAgentConvoFromNotif = function (slug, cid) {
    try {
      var nb = document.querySelector('.nav-item[data-view="agents"]');
      if (nb) nb.click();
    } catch (e) {}
    setTimeout(function () { try { openChat(slug, cid); } catch (e) {} }, 80);
  };

})();
