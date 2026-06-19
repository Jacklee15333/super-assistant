// renderer.js — 前端交互逻辑
// 通过本地 HTTP 和 Python 后端通信。

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

window.crayfish?.onBackendStatus((ok) => {
  const line = document.getElementById("statusLine");
  line.textContent = ok ? "已就绪" : "后端未连接";
  line.style.color = ok ? "var(--text-dim)" : "var(--accent)";
  if (!ok) setStatusDot(false);  // 后端都没连上，模型必然不正常
  if (ok) maybeGreetOnce();
});

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
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "memory") { loadMemoryTabs(); }
    if (btn.dataset.view === "dashboard") loadDashboard();
    if (btn.dataset.view === "video") { loadVideoNotes(); pollVideoProgress(); }
    if (btn.dataset.view === "library") loadLibrary();
    if (btn.dataset.view === "lumi") { loadLumi(); }
    if (btn.dataset.view === "skills") { loadSkills(); }
    if (btn.dataset.view === "loop") { loadLoop(); }
    if (btn.dataset.view === "harness") { loadHarness(); }
    if (btn.dataset.view === "sniff") { loadSniff(); }
    if (btn.dataset.view === "settings") { refreshHeartbeatStatus(); loadModelsInfo(); loadWebModelConfig(); loadTaskModels(); loadProxySetting(); }
    // 懂你子菜单只在懂你视图下显示
    const subNav = document.getElementById("lumiSubNav");
    if (subNav) subNav.style.display = (btn.dataset.view === "lumi") ? "" : "none";
  });
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
    wrap.appendChild(makeSpeakRow());
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

// 助手气泡下方的「语音播报」按钮。用事件委托处理点击，所以会话快照/恢复后依然可用。
function makeSpeakRow() {
  const row = document.createElement("div");
  row.className = "msg-actions";
  row.innerHTML = '<button type="button" class="speak-btn" title="语音播报这段">'
    + '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a9 9 0 0 1 0 14"/></svg>'
    + '<span class="speak-label">朗读</span></button>';
  return row;
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
}

function renderConvoList() {
  const list = document.getElementById("convoList");
  list.innerHTML = "";
  conversations.forEach((c) => {
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

document.getElementById("newConvoBtn").addEventListener("click", newConversation);

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
    btn.textContent = "🔍 检查竞品变化";
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
    : '<span class="task-empty">（还没设关键词，去“记忆 → watchlist.md”里加，一行一个）</span>';
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
    document.querySelector('.nav-item[data-view="memory"]').click();
    currentMemoryFile = "watchlist.md";
    setTimeout(() => loadMemoryTabs(), 100);
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
    btn.textContent = "📊 生成情报简报";
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
    btn.textContent = "💓 触发一次心跳";
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
  "SOUL.md":      { label: "🦞 性格设定", type: "text",
                    desc: "改这里能改变超能小助的说话风格和性格。" },
  "AGENTS.md":    { label: "📋 行为准则", type: "text",
                    desc: "它做事的规则。一般不用动，进阶用户可微调。" },
  "USER.md":      { label: "👤 关于你", type: "text",
                    desc: "记录你的情况和偏好，它会参考这些来更懂你。" },
  "MEMORY.md":    { label: "🧠 长期记忆", type: "text",
                    desc: "它从历次对话里提炼的要点，跨对话还记得你。" },
  "heartbeat.md": { label: "💓 心跳待办", type: "text",
                    desc: "心跳醒来时会看这里有没有要做的事。" },
  "watchlist.md": { label: "📊 情报关键词", type: "list",
                    itemLabel: "关键词", placeholder: "如：预制菜 行业趋势",
                    desc: "情报简报会按这些关键词联网搜集、提炼。一行一个。" },
  "competitors.md": { label: "🔍 竞品网址", type: "list", hasNote: true,
                    itemLabel: "网址", placeholder: "https://竞品官网/products",
                    notePlaceholder: "备注（如：竞品A 产品页）",
                    desc: "竞品监控会定时抓这些公开页面，有变化就提醒。" },
  "reminders.md": { label: "⏰ 定时提醒", type: "list", hasNote: true,
                    itemLabel: "时间", placeholder: "如：每天 09:00",
                    notePlaceholder: "提醒内容（如：交日报）",
                    sep: "|", bullet: "- [ ] ",
                    desc: "心跳到点会提醒你。时间写「每天 09:00」或「2026-06-20 14:00」。" },
  "push.md":      { label: "📱 Server酱推送", type: "config",
                    desc: "配好后，心跳干完活能把消息推到你的微信（单向）。",
                    fields: [
                      { key: "serverchan_key", label: "SendKey",
                        help: "去 sct.ftqq.com 微信扫码登录，复制 SendKey（形如 SCTxxxx）" },
                    ] },
  "wecom.md":     { label: "💬 企业微信", type: "config",
                    desc: "在企业微信 App 里和它双向聊天（合规免费，需公网回调）。",
                    fields: [
                      { key: "corp_id", label: "企业 CorpID", help: "「我的企业」里能看到" },
                      { key: "agent_id", label: "应用 AgentId", help: "自建应用页面" },
                      { key: "secret", label: "应用 Secret", help: "自建应用页面" },
                      { key: "token", label: "Token", help: "接收消息设置里，点随机生成" },
                      { key: "aes_key", label: "EncodingAESKey", help: "接收消息设置里，点随机生成" },
                    ] },
  "feishu.md":    { label: "🐦 飞书", type: "config",
                    desc: "在飞书里和它双向聊天（体验顺，需公网回调）。",
                    fields: [
                      { key: "app_id", label: "App ID", help: "企业自建应用页面" },
                      { key: "app_secret", label: "App Secret", help: "企业自建应用页面" },
                      { key: "verification_token", label: "Verification Token",
                        help: "事件订阅页面" },
                    ] },
  "telegram.md":  { label: "✈️ Telegram", type: "config",
                    desc: "海外可用。找 @BotFather 拿 token，@userinfobot 拿你的 chat id。",
                    fields: [
                      { key: "token", label: "Bot Token", help: "找 @BotFather 用 /newbot 获取" },
                      { key: "allowed_chat_id", label: "你的 Chat ID",
                        help: "找 @userinfobot 获取，只服务你一人" },
                    ] },
  "proxy.md":     { label: "🌐 联网与代理", type: "config",
                    desc: "国内直接搜 Bing；要搜国外源（DuckDuckGo/Google）需填代理。不填只搜国内。",
                    fields: [
                      { key: "proxy", label: "代理地址",
                        help: "如 http://127.0.0.1:7890（Clash默认7890）。不用代理就留空" },
                    ] },
};
const MEMORY_FILES = Object.keys(MEMORY_META);
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
  if (e.key === "Enter") { e.preventDefault(); runVideoExtract(); }
});

function setVideoStatus(text, kind) {
  const el = document.getElementById("videoStatus");
  if (!el) return;
  el.textContent = text || "";
  el.className = "video-status" + (kind ? " " + kind : "");
}

async function runVideoExtract() {
  const url = (document.getElementById("videoUrl").value || "").trim();
  if (!url) { setVideoStatus("先粘贴一个视频链接（整段分享文案也行）。", "warn"); return; }
  const level = document.getElementById("videoLevel").value;
  startVideoJob(url, level);
}

// 给悬浮按钮用：从剪贴板检测到的链接，填进输入框（不自动开始，等用户点提取）
window.startVideoFromFloat = function (url) {
  document.querySelector('.nav-item[data-view="video"]').click();
  const box = document.getElementById("videoUrl");
  if (box) box.value = url;
  setVideoStatus("已把链接填好，点右边的「提取并分析」就开始。");
  const btn = document.getElementById("videoGoBtn");
  if (btn) { btn.classList.add("pulse"); setTimeout(() => btn.classList.remove("pulse"), 2400); }
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
    const screenshot = !!(shotEl && shotEl.checked);
    const link = !!(linkEl && linkEl.checked);
    // 读字幕模式（auto / subtitle_only / transcribe），默认 auto
    const modeEl = document.getElementById("videoSubMode");
    const mode = (modeEl && modeEl.value) || "auto";

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
            hintEl.innerHTML = "✅ 检测到" + srcName +
              "，已按「自动」直接用字幕（最快）。想更准更全，可在上方「字幕模式」改选" +
              "『字幕+视频听写』后重新提取。";
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
                             screenshot, link, mode }),
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
      if (box) box.value = "";   // 已进队列，清空输入框，避免用户分不清这链接干嘛的
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

function parseVideoPercent(detail) {
  const m = (detail || "").match(/(\d+)\s*%/);
  return m ? Math.max(0, Math.min(100, parseInt(m[1]))) : null;
}

function shortLabel(u) {
  if (!u) return "";
  return u.length > 48 ? u.slice(0, 46) + "…" : u;
}

function renderVideoTasks(p) {
  const el = document.getElementById("videoTasks");
  if (!el) return;
  let h = "";
  if (p.running) {
    const pct = parseVideoPercent(p.detail);
    const stage = p.stage || "处理中";
    const detail = p.detail ? "：" + p.detail : "";
    const bar = pct != null
      ? '<div class="vbar"><div class="vbar-fill" style="width:' + pct + '%"></div></div>'
      : '<div class="vbar"><div class="vbar-fill indet"></div></div>';
    h += '<div class="vtask running">' +
      '<div class="vtask-top"><span class="vt-badge">生成中</span> ' +
      escapeHtml(stage + detail) +
      ' <span class="vt-time">已用时 ' + (p.elapsed || 0) + ' 秒</span></div>' +
      bar +
      '<div class="vt-url">' + escapeHtml(shortLabel(p.current_label)) + '</div></div>';
  }
  (p.queue || []).forEach((u, i) => {
    h += '<div class="vtask queued">' +
      '<div class="vtask-top"><span class="vt-badge q">排队中</span> 第 ' + (i + 1) + ' 个</div>' +
      '<div class="vbar"><div class="vbar-fill q"></div></div>' +
      '<div class="vt-url">' + escapeHtml(shortLabel(u)) + '</div></div>';
  });
  el.innerHTML = h;
}

let _videoPollTimer = null;
let _lastVideoResultId = 0;
function pollVideoProgress() {
  if (_videoPollTimer) return;  // 已经在轮询了
  const tick = async () => {
    try {
      const r = await fetch(BACKEND + "/video_progress");
      const p = await r.json();
      renderVideoTasks(p);

      // 有新完成的结果就渲染出来
      if (p.result_id && p.result_id > _lastVideoResultId && p.result) {
        _lastVideoResultId = p.result_id;
        const res = p.result;
        if (res.ok) {
          mountVideoResult(res);
          loadVideoNotes();
        }
      }

      if (p.running || p.queue_len > 0 || p.has_chat_tasks) {
        setVideoStatus("");   // 状态都在下面的任务卡片里显示
      } else {
        // 全部处理完，停止轮询
        clearInterval(_videoPollTimer); _videoPollTimer = null;
        renderVideoTasks({ running: false, queue: [] });
        const res = p.result || {};
        if (res.ok) {
          setVideoStatus("✓ 全部完成，已自动存档", "ok");
        } else if (res.error) {
          setVideoStatus("最后一个没成功：" + res.error, "warn");
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
      setVideoStatus("依赖装好了，再点一次「提取并分析」即可。", "ok");
      if (btn) btn.textContent = "已安装 ✓";
    } else if (btn) {
      btn.disabled = false; btn.textContent = "重试安装";
    }
  } catch (e) {
    if (log) log.textContent = "安装出错：" + e.message;
    if (btn) { btn.disabled = false; btn.textContent = "重试安装"; }
  }
}

let _currentVideo = null;  // 当前展示的视频数据（用于复制/导出）

function mountVideoResult(data, target) {
  const resultEl = target || document.getElementById("videoResult");
  if (!target) _currentVideo = data;  // 只有视频标签页才更新全局当前视频
  const head =
    (data.title ? "<h2>" + escapeHtml(data.title) + "</h2>" : "") +
    (data.uploader ? "<p style='color:var(--text-dim);margin-top:-6px'>作者：" +
      escapeHtml(data.uploader) + "</p>" : "");
  // 页面内的二级标签行：显示当前标签 + 一个「管理标签」按钮（仅对已存档、知道文件名的视频可编辑）
  const canEditTags = !!(data._noteName && data._noteCat === "video");
  const tagRowHtml = '<div class="vtag-row" id="vTagRow"></div>';
  resultEl.innerHTML =
    '<div class="video-toolbar">' +
      '<button class="vtab active" data-tab="analysis">🤖 AI 分析</button>' +
      '<button class="vtab" data-tab="transcript">📝 完整原文</button>' +
      '<span class="vdetail" id="vDetailToggle">' +
        '<button class="vd active" data-d="full">详细</button>' +
        '<button class="vd" data-d="brief">简洁</button>' +
      '</span>' +
      '<span class="vspacer"></span>' +
      '<button class="vbtn vbtn-speak" id="vSpeakBtn">🔊 朗读</button>' +
      '<button class="vbtn" id="vCopyBtn">复制本页</button>' +
      '<button class="vbtn" id="vExportBtn">导出 Markdown</button>' +
    '</div>' +
    head +
    tagRowHtml +
    '<div class="vtab-body" id="vAnalysis">' + renderMarkdown(data.analysis || "（无分析）") + '</div>' +
    '<div class="vtab-body" id="vTranscript" style="display:none">' +
      renderMarkdown(paragraphizeCN(data.transcript || "（无文字稿）")) +
    '</div>';

  // 容器内查询（不用 getElementById），这样同一个视图可以在多处复用而不冲突
  const $ = (sel) => resultEl.querySelector(sel);

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

  const tabs = resultEl.querySelectorAll(".vtab");
  tabs.forEach((t) => t.addEventListener("click", () => {
    tabs.forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const which = t.dataset.tab;
    $("#vAnalysis").style.display = which === "analysis" ? "" : "none";
    $("#vTranscript").style.display = which === "transcript" ? "" : "none";
    detailToggle.style.display = which === "analysis" ? "" : "none";  // 只在 AI 分析时显示开关
  }));
  $("#vCopyBtn").addEventListener("click", () => {
    const active = resultEl.querySelector(".vtab.active").dataset.tab;
    let text;
    if (active === "transcript") text = data.transcript || "";
    else text = detailMode === "brief" ? conciseMarkdown(data.analysis || "") : (data.analysis || "");
    copyText(text);
    const b = $("#vCopyBtn");
    b.textContent = "已复制 ✓"; setTimeout(() => (b.textContent = "复制本页"), 1500);
  });
  $("#vExportBtn").addEventListener("click", () => exportVideoMd(data));
  $("#vSpeakBtn").addEventListener("click", () => {
    const active = resultEl.querySelector(".vtab.active").dataset.tab;
    const text = active === "transcript"
      ? (data.transcript || "")
      : (detailMode === "brief" ? conciseMarkdown(data.analysis || "") : (data.analysis || ""));
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
  list.innerHTML = "<div class='dash-loading'>加载中…</div>";
  try {
    const resp = await fetch(BACKEND + "/video_notes");
    const data = await resp.json();
    const notes = data.notes || [];
    if (notes.length === 0) {
      list.innerHTML = "<div class='dash-empty'>还没有视频笔记。在上面粘个链接试试。</div>";
      return;
    }
    list.innerHTML = "";
    notes.forEach((n) => {
      const item = document.createElement("div");
      item.className = "video-note-item";
      const name = document.createElement("span");
      name.className = "vn-name";
      name.textContent = n.title || n.name;
      name.addEventListener("click", () => openVideoNote(n.name));
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
      item.appendChild(name);
      item.appendChild(del);
      list.appendChild(item);
    });
  } catch (e) {
    list.innerHTML = "<div class='dash-empty'>加载失败：" + escapeHtml(e.message) + "</div>";
  }
}

async function openVideoNote(name) {
  const resultEl = document.getElementById("videoResult");
  resultEl.innerHTML = "<div class='dash-loading'>读取中…</div>";
  setVideoStatus("");
  try {
    const resp = await fetch(BACKEND + "/video_note?name=" + encodeURIComponent(name));
    const data = await resp.json();
    if (!data.ok) { resultEl.innerHTML = "<div class='dash-empty'>" +
      escapeHtml(data.error || "读取失败") + "</div>"; return; }
    const parsed = parseVideoNote(data.content || "");
    parsed._noteName = name;     // 视频板块的笔记，归类为 video，可在页面内加标签
    parsed._noteCat = "video";
    mountVideoResult(parsed);
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    resultEl.innerHTML = "<div class='dash-empty'>出错：" + escapeHtml(e.message) + "</div>";
  }
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
  const tMark = md.indexOf("完整文字稿");
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
let _libData = { video: [], learning: [], info: [], all_tags: {} };
let _libCat = "video";
let _libTagFilter = "";   // 当前选中的二级标签过滤；"" = 全部

async function loadLibrary() {
  try {
    const r = await fetch(BACKEND + "/library");
    _libData = await r.json();
  } catch (e) {
    _libData = { video: [], learning: [], info: [], all_tags: {} };
  }
  const setCount = (id, n) => { const el = document.getElementById(id); if (el) el.textContent = n; };
  setCount("libCntVideo", (_libData.video || []).length);
  setCount("libCntLearning", (_libData.learning || []).length);
  setCount("libCntInfo", (_libData.info || []).length);
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
         '记得先在记忆里的 watchlist.md 配好关键词。</div>';
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
    h += '<div class="dash-empty">还没有监控目标。去记忆里的 competitors.md ' +
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
  const tabs = document.getElementById("memoryTabs");
  tabs.innerHTML = "";
  MEMORY_FILES.forEach((f) => {
    const t = document.createElement("button");
    t.className = "memory-tab" + (f === currentMemoryFile ? " active" : "");
    t.textContent = (MEMORY_META[f] && MEMORY_META[f].label) || f;
    t.addEventListener("click", () => { currentMemoryFile = f; loadMemoryTabs(); });
    tabs.appendChild(t);
  });
  loadMemoryContent(currentMemoryFile);
}

async function loadMemoryContent(name) {
  const body = document.getElementById("memoryBody");
  const descEl = document.getElementById("memoryDesc");
  const editor = document.getElementById("memoryEditor");
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

  const modeBar = document.getElementById("memoryModeBar");
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
  const editor = document.getElementById("memoryEditor");
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
  add.onclick = () => {
    const h = prompt("新分节的小标题（如：我的偏好）");
    if (!h) return;
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
      return document.getElementById("memoryEditor").value;
    }
    // 结构化模式：把各分区块拼回 markdown
    const body = document.getElementById("memoryBody");
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
    const rows = document.querySelectorAll("#memoryBody .kv-row");
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
    document.querySelectorAll("#memoryBody .cfg-input").forEach((inp) => {
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
  const body = document.getElementById("memoryBody");
  renderTextEditor(body, currentMemoryFile, cur, meta);
}
document.getElementById("memModeStruct")?.addEventListener("click", () => setMemMode("struct"));
document.getElementById("memModeRaw")?.addEventListener("click", () => setMemMode("raw"));

document.getElementById("saveMemoryBtn").addEventListener("click", async () => {
  const content = collectMemoryContent();
  const hint = document.getElementById("saveHint");
  try {
    const resp = await fetch(BACKEND + "/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: currentMemoryFile, content }),
    });
    const data = await resp.json();
    hint.textContent = data.ok ? "已保存 ✓" : ("保存失败：" + data.message);
    setTimeout(() => (hint.textContent = ""), 2500);
  } catch (e) {
    hint.textContent = "保存出错：" + e.message;
  }
});

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

// ---------- 皮肤（深色/浅色）----------
function applyTheme(theme) {
  const t = theme === "light" ? "light" : "dark";
  document.body.classList.toggle("light", t === "light");
  try { localStorage.setItem("cx_theme", t); } catch (_) {}
  const sel = document.getElementById("themeSelect");
  if (sel) sel.value = t;
}
// 给顶部菜单"切换皮肤"用
window.toggleTheme = function () {
  const now = document.body.classList.contains("light") ? "light" : "dark";
  applyTheme(now === "light" ? "dark" : "light");
};
// 启动时读取上次的选择（默认深色）
(function initTheme() {
  let saved = "dark";
  try { saved = localStorage.getItem("cx_theme") || "dark"; } catch (_) {}
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
  try {
    const r = await fetch(BACKEND + "/lumi/status");
    const d = await r.json();
    if (!d || !d.ok) return;
    _lumiData = d;
    const profEl = document.getElementById("lumiProfile");
    if (profEl) profEl.innerHTML = (d.profile || "").trim()
      ? renderProfileRich(d.profile)
      : '<div class="lumi-empty">还没演化。点右上角「✨ 人格演化」，小助会从你的对话里总结出你的说话风格、关注点和偏好。</div>';
    const relEl = document.getElementById("lumiRelations");
    if (relEl) relEl.innerHTML = (d.relationships || "").trim()
      ? renderRelationsRich(d.relationships)
      : '<div class="lumi-empty">还没记录到人。聊天时提到具体的人（同事、朋友、客户…），小助会自动记下来。</div>';
    const envEl = document.getElementById("lumiEnv");
    if (envEl) envEl.innerHTML = (d.environment || "").trim()
      ? renderMarkdown(d.environment)
      : '<div class="lumi-empty">还没扫描。点右上角「🖥️ 扫描环境」，小助会看你装了什么软件、推断你的职业方向。</div>';
  } catch (e) { /* 静默 */ }
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

// 把画像 OWNER_PROFILE.md 渲染成漂亮的分区卡片（带图标），比纯 markdown 好看
function renderProfileRich(md) {
  // 去掉顶部 # 标题和说明引语
  let body = (md || "").replace(/^#\s+.*$/m, "").replace(/^>.*$/gm, "").trim();
  const iconFor = (title) => {
    if (/风格|说话|语气/.test(title)) return "🗣️";
    if (/关注|在意|话题|领域/.test(title)) return "🎯";
    if (/偏好|习惯/.test(title)) return "⭐";
    if (/怎么|建议|对他/.test(title)) return "💡";
    return "📌";
  };
  // 解析 ## 分区
  const sections = [];
  let cur = null;
  body.split("\n").forEach((ln) => {
    const m = ln.match(/^#{2,3}\s+(.+)$/);
    if (m) { if (cur) sections.push(cur); cur = { title: m[1].trim(), lines: [] }; }
    else if (cur) cur.lines.push(ln);
    else if (ln.trim()) { cur = { title: "", lines: [ln] }; }
  });
  if (cur) sections.push(cur);
  if (!sections.length) return renderMarkdown(md);

  let h = '<div class="profile-grid">';
  sections.forEach((sec) => {
    const inner = renderMarkdown(sec.lines.join("\n").trim());
    h += '<div class="profile-card">' +
      (sec.title ? '<div class="profile-card-head"><span class="profile-icon">' +
        iconFor(sec.title) + '</span>' + escapeHtml(sec.title) + "</div>" : "") +
      '<div class="profile-card-body">' + inner + "</div>" +
      "</div>";
  });
  h += "</div>";
  return h;
}

// 懂你子菜单：切换画像/关系/环境三个子页
function switchLumiSub(which) {
  const map = { profile: "lumiPageProfile", relations: "lumiPageRelations", env: "lumiPageEnv" };
  Object.entries(map).forEach(([k, id]) => {
    const pg = document.getElementById(id);
    if (pg) pg.style.display = (k === which) ? "" : "none";
  });
  document.querySelectorAll("#lumiSubNav .nav-subitem").forEach((b) =>
    b.classList.toggle("active", b.dataset.lumi === which));
}
document.querySelectorAll("#lumiSubNav .nav-subitem").forEach((b) => {
  b.addEventListener("click", () => {
    // 点子菜单时确保主视图切到懂你
    document.querySelectorAll(".nav-item").forEach((x) => x.classList.remove("active"));
    document.querySelector('.nav-item[data-view="lumi"]')?.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-lumi")?.classList.add("active");
    switchLumiSub(b.dataset.lumi);
    loadLumi();
  });
});

function setLumiStatus(msg, kind) {
  const el = document.getElementById("lumiStatus");
  if (!el) return;
  el.textContent = msg || "";
  el.className = "lumi-status" + (kind ? " " + kind : "");
}

document.getElementById("lumiEvolveBtn")?.addEventListener("click", async () => {
  const btn = document.getElementById("lumiEvolveBtn");
  const s = settings();
  btn.disabled = true; setLumiStatus("正在读对话、总结你的画像…（可能要十几秒）");
  try {
    const r = await fetch(BACKEND + "/lumi/evolve", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    setLumiStatus(d.message || (d.ok ? "演化完成" : "演化没成功"), d.ok ? "ok" : "warn");
    if (d.ok) { loadLumi(); switchLumiSub("profile"); }
  } catch (e) { setLumiStatus("出错：" + e.message, "warn"); }
  finally { btn.disabled = false; }
});

document.getElementById("lumiScanBtn")?.addEventListener("click", async () => {
  const btn = document.getElementById("lumiScanBtn");
  const s = settings();
  btn.disabled = true; setLumiStatus("正在扫描本机环境…");
  try {
    const r = await fetch(BACKEND + "/lumi/scan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const d = await r.json();
    let msg = d.message || (d.ok ? "扫描完成" : "扫描没成功");
    if (d.ok && d.professions && d.professions.length) msg += "（推断：" + d.professions.join("、") + "）";
    setLumiStatus(msg, d.ok ? "ok" : "warn");
    if (d.ok) { loadLumi(); switchLumiSub("env"); }
  } catch (e) { setLumiStatus("出错：" + e.message, "warn"); }
  finally { btn.disabled = false; }
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
function loadHarness() {
  loadHarnessConfig();
  loadHarnessRuns();
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
    box.innerHTML = '<div class="harness-empty">还没有运行记录。去「目标循环」跑一个任务，这里就会出数据。</div>';
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
    box.innerHTML = '<div class="harness-empty">暂无记录。目前记录「目标循环」的运行。</div>';
    return;
  }
  box.innerHTML = runs.map((r) => {
    const kindTag = r.kind === "loop" ? "🔁 循环" : "💬 对话";
    const out = r.outcome === "done" ? '<span class="harness-out done">达标</span>'
      : r.outcome === "stopped" ? '<span class="harness-out">已停</span>'
      : r.outcome === "maxed" ? '<span class="harness-out warn">未达标</span>' : "";
    const tools = (r.tools && r.tools.length)
      ? '<div class="harness-run-tools">工具：' +
        Object.entries(r.tool_count || {}).map(([k, v]) => escapeHtml(k) + "×" + v).join("、") + "</div>"
      : '<div class="harness-run-tools">没调工具</div>';
    const err = r.error ? '<div class="harness-run-err">⚠ ' + escapeHtml(r.error) + "</div>" : "";
    const secs = r.seconds ? " · " + r.seconds + "s" : "";
    return (
      '<div class="harness-run">' +
        '<div class="harness-run-head">' +
          '<span class="harness-run-kind">' + kindTag + "</span>" + out +
          '<span class="harness-run-ts">' + escapeHtml(r.ts || "") + secs + "</span>" +
        "</div>" +
        '<div class="harness-run-title">' + escapeHtml(r.title || "（无标题）") + "</div>" +
        tools + err +
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

function loadSniff() {
  loadSniffSources();
  loadSniffFeed();
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
        '<div class="sniff-source' + (s.enabled ? "" : " off") + '" data-id="' + escapeHtml(s.id) + '">' +
          _sniffAvatar(s.title, s.url) +
          '<a class="sniff-src-main" href="' + escapeHtml(s.url) + '" target="_blank" title="' + escapeHtml(s.url) + '">' +
            '<span class="sniff-src-title">' + escapeHtml(s.title || host) + "</span>" +
            '<span class="sniff-src-url">' + escapeHtml(host) + "</span>" +
          "</a>" +
          '<label class="sniff-switch sniff-switch-sm" title="开启/暂停这个源">' +
            '<input type="checkbox" class="sniff-src-cb"' + (s.enabled ? " checked" : "") + " />" +
            '<span class="sniff-switch-track"></span></label>' +
          '<button class="sniff-src-del" title="删除">✕</button>' +
        "</div>"
      );
    }).join("");
    return (
      '<div class="sniff-cat-group">' +
        '<div class="sniff-cat-head">' +
          '<span class="sniff-cat-name">📁 ' + escapeHtml(g.cat) + "</span>" +
          '<span class="sniff-cat-cnt">' + onCount + "/" + g.items.length + "</span>" +
          '<label class="sniff-switch sniff-switch-sm sniff-cat-toggle" title="开启/暂停整个类别" data-cat="' + escapeHtml(g.cat) + '">' +
            '<input type="checkbox" class="sniff-cat-cb"' + (allOn ? " checked" : "") + " />" +
            '<span class="sniff-switch-track"></span></label>' +
        "</div>" + rows +
      "</div>"
    );
  }).join("");

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
  try {
    await fetch(BACKEND + "/sniff/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto, every }),
    });
    const st = document.getElementById("sniffAutoSave");
    const old = st.textContent; st.textContent = "✓"; setTimeout(() => { st.textContent = old; }, 1500);
  } catch (e) {}
});

document.getElementById("sniffRefreshBtn")?.addEventListener("click", () => { loadSniffSources(); loadSniffFeed(); });
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
        '<div class="sniff-empty-desc">点右上角「立即嗅探」扫一遍。<b>第一次只记录快照</b>，从第二次起才会报新内容。</div>' +
        '<div class="sniff-legend">' +
          '<div class="sniff-legend-item"><span class="sniff-legend-ic">🆕</span><div><b>发布</b><span>新模型、新版本上线</span></div></div>' +
          '<div class="sniff-legend-item"><span class="sniff-legend-ic">🧩</span><div><b>功能</b><span>新能力、新特性</span></div></div>' +
          '<div class="sniff-legend-item"><span class="sniff-legend-ic">💡</span><div><b>概念</b><span>新术语、新玩法</span></div></div>' +
        "</div>" +
      "</div>";
    return;
  }
  if (!feed.length) {
    box.innerHTML = '<div class="sniff-empty">这个分类下还没有动向。</div>';
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
