// renderer.js — 前端交互逻辑
// 通过本地 HTTP 和 Python 后端通信。

let BACKEND = "http://127.0.0.1:8756";
let messages = [];          // 喂给模型的完整历史
let busy = false;

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
});

// ---------- 视图切换 ----------
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "memory") loadMemoryTabs();
    if (btn.dataset.view === "dashboard") loadDashboard();
    if (btn.dataset.view === "video") { loadVideoNotes(); pollVideoProgress(); }
    if (btn.dataset.view === "settings") { refreshHeartbeatStatus(); loadModelsInfo(); }
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
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
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
  // 分隔线 ---
  s = s.replace(/^\s*---+\s*$/gm, "<hr>");
  // 粗体 **x**
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  // 斜体 *x*
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  // 链接 [text](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank">$1</a>');
  // 裸链接（行内直接出现的 http(s) 网址）也变成可点击
  s = s.replace(/(^|[\s>])(https?:\/\/[^\s<）)]+)/g,
    '$1<a href="$2" target="_blank">$2</a>');
  // 有序列表 1. 2. 3.
  s = s.replace(/^\d+\.\s+(.+)$/gm, "\u0003<oli>$1</oli>");
  s = s.replace(/(\u0003<oli>[\s\S]*?<\/oli>)(?:\n?\u0003<oli>[\s\S]*?<\/oli>)*/g,
    (m) => "<ol>" + m.replace(/\u0003/g, "").replace(/<oli>/g, "<li>")
      .replace(/<\/oli>/g, "</li>").replace(/\n/g, "") + "</ol>");
  s = s.replace(/\u0003/g, "").replace(/<\/?oli>/g, "");
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

function addToolCall(name, args, result) {
  const el = document.createElement("div");
  el.className = "tool-call";
  el.innerHTML = `🔧 <b>${name}</b>(${escapeHtml(JSON.stringify(args))})
    <div class="tc-result">→ ${escapeHtml(result)}</div>`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

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
  return "qwen2.5";
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
  const prog = addProgress([
    "🧠 正在思考…",
    "🔧 可能在调用工具处理…",
    "✍️ 正在整理回复…",
  ]);

  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, approvals, ...s }),
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

// 危险操作确认框
function askApproval(pending) {
  const el = document.createElement("div");
  el.className = "approval";
  const argsStr = escapeHtml(JSON.stringify(pending.args, null, 2));
  el.innerHTML =
    `<div class="approval-head">⚠️ 超能小助想执行一个危险操作，需要你批准</div>
     <div class="approval-tool">${escapeHtml(pending.name)}</div>
     <pre class="approval-args">${argsStr}</pre>
     <div class="approval-btns">
       <button class="approve-yes">批准执行</button>
       <button class="approve-no">拒绝</button>
     </div>`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  el.querySelector(".approve-yes").addEventListener("click", () => {
    el.querySelector(".approval-btns").innerHTML = "<span class='approved'>已批准 ✓</span>";
    runChatLoop({ [pending.tool_call_id]: true });
  });
  el.querySelector(".approve-no").addEventListener("click", () => {
    el.querySelector(".approval-btns").innerHTML = "<span class='denied'>已拒绝 ✕</span>";
    runChatLoop({ [pending.tool_call_id]: false });
  });
}

sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});

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
  // 固定名字的功能会话（情报简报等）保留原名；普通会话用首条用户消息做标题
  if (!c.fixedTitle) {
    const firstUser = messages.find((m) => m.role === "user");
    if (firstUser) c.title = firstUser.content.slice(0, 20);
  }
  // 存一份展示用的 HTML 快照
  c.displayHtml = messagesEl.innerHTML;
  renderConvoList();
}

function switchConversation(id) {
  saveCurrentConversation();
  const c = conversations.find((x) => x.id === id);
  if (!c) return;
  activeConvoId = id;
  messages = c.messages || [];
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
      c.fixedTitle = c.title;
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

document.getElementById("clearBtn").addEventListener("click", () => {
  messages = [];
  messagesEl.innerHTML = "";
  saveCurrentConversation();
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
      用本地模型不花钱，但会占用电脑算力，大概要一两分钟。
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
  // 用真实的关键词拼出更具体的进度，而不是笼统的"正在搜索"
  let kws = [];
  try {
    const r = await fetch(BACKEND + "/memory?name=watchlist.md");
    const d = await r.json();
    kws = (d.content || "").split("\n").map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && !l.startsWith(">"))
      .map((l) => l.replace(/^-\s*/, ""));
  } catch (_) {}
  const stages = [];
  stages.push(`读取到 ${kws.length} 个关键词：${kws.join("、") || "（空）"}`);
  kws.slice(0, 8).forEach((k, i) => {
    stages.push(`第 ${i + 1}/${kws.length} 个「${k}」：多引擎搜索 → 读网页 → 单独提炼…`);
  });
  stages.push("各关键词都提炼好了，正在拼合排版…");
  const prog = addProgress(stages, 1800);
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/briefing", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    prog.done();
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
  el.className = "tool-call";
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
  btn.disabled = true; btn.textContent = "搬运中…";
  if (msg) msg.textContent = "正在把 C 盘已下载的模型搬到 D 盘…";
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
    const resp = await fetch(BACKEND + "/video_transcribe", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, level, use_local: s.use_local, model: s.model }),
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

      if (p.running || p.queue_len > 0) {
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

function mountVideoResult(data) {
  _currentVideo = data;
  const resultEl = document.getElementById("videoResult");
  const head =
    (data.title ? "<h2>" + escapeHtml(data.title) + "</h2>" : "") +
    (data.uploader ? "<p style='color:var(--text-dim);margin-top:-6px'>作者：" +
      escapeHtml(data.uploader) + "</p>" : "");
  resultEl.innerHTML =
    '<div class="video-toolbar">' +
      '<button class="vtab active" data-tab="analysis">🤖 AI 分析</button>' +
      '<button class="vtab" data-tab="transcript">📝 完整原文</button>' +
      '<span class="vspacer"></span>' +
      '<button class="vbtn" id="vCopyBtn">复制本页</button>' +
      '<button class="vbtn" id="vExportBtn">导出 Markdown</button>' +
    '</div>' +
    head +
    '<div class="vtab-body" id="vAnalysis">' + renderMarkdown(data.analysis || "（无分析）") + '</div>' +
    '<div class="vtab-body" id="vTranscript" style="display:none">' +
      renderMarkdown(paragraphizeCN(data.transcript || "（无文字稿）")) +
    '</div>';

  const tabs = resultEl.querySelectorAll(".vtab");
  tabs.forEach((t) => t.addEventListener("click", () => {
    tabs.forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const which = t.dataset.tab;
    document.getElementById("vAnalysis").style.display = which === "analysis" ? "" : "none";
    document.getElementById("vTranscript").style.display = which === "transcript" ? "" : "none";
  }));
  document.getElementById("vCopyBtn").addEventListener("click", () => {
    const active = resultEl.querySelector(".vtab.active").dataset.tab;
    const text = active === "analysis" ? (data.analysis || "") : (data.transcript || "");
    copyText(text);
    const b = document.getElementById("vCopyBtn");
    b.textContent = "已复制 ✓"; setTimeout(() => (b.textContent = "复制本页"), 1500);
  });
  document.getElementById("vExportBtn").addEventListener("click", () => exportVideoMd(data));
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
    mountVideoResult(parseVideoNote(data.content || ""));
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    resultEl.innerHTML = "<div class='dash-empty'>出错：" + escapeHtml(e.message) + "</div>";
  }
}

// 把存档的 markdown 拆回 标题/作者/链接/分析/原文，喂给标签页视图
function parseVideoNote(md) {
  const out = { title: "", uploader: "", url: "", analysis: "", transcript: "" };
  const lines = md.split("\n");
  if (lines[0]) out.title = lines[0].replace(/^#\s*/, "").trim();
  const mu = md.match(/作者：(.*)/); if (mu) out.uploader = mu[1].trim();
  const ml = md.match(/来源链接：(.*)/); if (ml) out.url = ml[1].trim();
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

  if (meta.type === "text") {
    // 自由文本：隐藏 body，显示常驻的 textarea（占满高度）
    body.innerHTML = "";
    body.style.display = "none";
    editor.value = content;
    editor.style.display = "";
  } else if (meta.type === "list") {
    body.style.display = "";
    renderListEditor(body, name, content, meta);
  } else if (meta.type === "config") {
    body.style.display = "";
    renderConfigEditor(body, name, content, meta);
  }
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
    return document.getElementById("memoryEditor").value;
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
document.getElementById("rememberBtn").addEventListener("click", async () => {
  if (messages.length === 0) { addSystemNote("还没聊什么可记的。"); return; }
  const btn = document.getElementById("rememberBtn");
  btn.textContent = "记忆中…";
  try {
    const s = settings();
    const resp = await fetch(BACKEND + "/remember", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, use_local: s.use_local, model: s.model }),
    });
    const data = await resp.json();
    if (data.ok) {
      addSystemNote("🧠 已记住这段。摘要：\n" + (data.summary || ""));
      messages = [];
      messagesEl.querySelectorAll(".msg").forEach((n) => n.remove());
    } else {
      addSystemNote("记忆失败：" + (data.error || "未知"));
    }
  } catch (e) {
    addSystemNote("记忆出错：" + e.message);
  } finally {
    btn.textContent = "结束并记住";
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
  document.getElementById("modelHint").textContent =
    (s.use_local ? "本地 · " : "云端 · ") + s.model;
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
    sel.innerHTML = "";

    const addOpt = (group, m, label) => {
      const opt = document.createElement("option");
      opt.value = m; opt.textContent = label || m;
      if (m === want || m.split(":")[0] === want.split(":")[0]) opt.selected = true;
      group.appendChild(opt);
    };

    if (models.length === 0 && cloud.length === 0) {
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
    }
    updateModelHint();
  } catch (e) {
    // 连不上后端时静默，保留手动输入
  }
}

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
  loadModels();
  // 等后端起来再检查环境（延迟一下，给 Ollama 自启动留时间）
  setTimeout(() => runEnvCheck(false), 2000);
});
newConversation();  // 开一个初始会话
