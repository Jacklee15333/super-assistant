// ============================================================
// ai-live.js —— v189：「AI 池」实时画面，全软件通用
//   AI 池（网页版 ChatGPT）在干活时——商业写报告 / 定制方案、知识库收录、加工分析、贴标签、整理原文、对话……
//   不管在哪一页，右下角都会出现一条「AI 池正在…」。点开就是实时画面：AI 池浏览器的截图、AI 正在写的字、
//   每一步做了什么、谁在排队；点「折叠」收成一条，做完了它自己消失。展开还是折叠会记住。
//   已经有自己实时画面的地方（加工页的「AI 实时画面」、找博主），这一条就不重复出现。
//   别的地方想放一个「看实时画面」按钮：调 window.cxAiLive.open()。
//   截图只在展开着的时候才截（/ai_live?watch=1），折叠时只问一句「在不在忙」，不费资源。
// ============================================================
(function () {
  "use strict";
  const backend = () => { try { if (typeof BACKEND === "string" && BACKEND) return BACKEND; } catch (e) {} return "http://127.0.0.1:8756"; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pad = (n) => (n < 10 ? "0" : "") + n;
  const dur = (s) => {
    s = Math.max(0, Math.round(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return (h ? h + ":" + pad(m) : pad(m)) + ":" + pad(s % 60);
  };
  const clock = (t) => { const d = new Date(t * 1000); return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()); };
  const store = {
    get(k, d) { try { const v = localStorage.getItem("cx.aiLive." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("cx.aiLive." + k, JSON.stringify(v)); } catch (e) {} },
  };
  const TABS = [["reply", "AI 正在写的"], ["steps", "步骤记录"], ["queue", "排队"]];

  const S = { open: !!store.get("open", false), tab: store.get("tab", "reply"), d: null, timer: null, idleAt: 0, lastWhat: "",
              shotTs: 0, failed: 0, hold: false, holdAt: 0 };
  let el = null;

  function build() {
    el = document.createElement("div");
    el.className = "cx-ail";
    el.id = "cxAiLive";
    el.hidden = true;
    el.innerHTML =
      '<button type="button" class="cx-ail-bar" data-ail="open" aria-expanded="false" title="点开看 AI 池的实时画面">' +
        '<i class="cx-ail-dot" aria-hidden="true"></i><span class="cx-ail-bt"></span><span class="cx-ail-bm"></span>' +
        '<span class="cx-ail-go">看实时画面</span></button>' +
      '<section class="cx-ail-panel" role="dialog" aria-label="AI 池实时画面" hidden>' +
        '<header class="cx-ail-h"><div class="cx-ail-ht"><b><i class="cx-ail-dot" aria-hidden="true"></i>AI 池实时画面</b>' +
          '<span class="cx-ail-what"></span></div>' +
          '<button type="button" class="cx-ail-fold" data-ail="fold" title="折叠成一条，不影响 AI 池干活">折叠</button></header>' +
        '<p class="cx-ail-stage" aria-live="polite"></p>' +
        '<div class="cx-ail-shot"><img alt="AI 池浏览器的实时画面" hidden><span class="cx-ail-note">等待画面…</span></div>' +
        '<div class="cx-ail-tabs" role="tablist">' + TABS.map(([k, t]) =>
          '<button type="button" role="tab" data-ail-tab="' + k + '">' + t + "</button>").join("") + "</div>" +
        '<pre class="cx-ail-reply" data-ail-pane="reply"></pre>' +
        '<div class="cx-ail-steps" data-ail-pane="steps" hidden></div>' +
        '<div class="cx-ail-queue" data-ail-pane="queue" hidden></div>' +
        '<footer class="cx-ail-f"><button type="button" class="cx-ail-btn" data-ail="browser" title="把 AI 池浏览器调到屏幕上 / 挪回屏幕外（挪走后照常工作）">显示浏览器</button>' +
          '<button type="button" class="cx-ail-btn" data-ail="term" title="在单独的窗口里看后台日志">显示终端</button>' +
          '<span class="cx-ail-msg" aria-live="polite"></span></footer>' +
      "</section>";
    document.body.appendChild(el);
    el.addEventListener("click", onClick);
    el.addEventListener("keydown", (e) => { if (e.key === "Escape" && S.open) { e.stopPropagation(); fold(); } });
  }

  function busyOf(d) {
    const p = (d && d.pool) || {}, g = (d && d.ai_gate) || {};
    return !!(p.busy || (g.busy || []).length || g.waiting);
  }
  // 这一页自己就有实时画面（加工页、找博主）：右下角这一条就不出来，免得两份
  function inlineShown() {
    return !!document.querySelector(".view.active #vnLive:not([hidden]), .view.active .cwf-live:not([hidden]) .ai-live-mini");
  }
  function whatOf(d) {
    const p = (d && d.pool) || {}, g = (d && d.ai_gate) || {};
    const names = (g.busy || []).map((x) => x.what).filter(Boolean);
    if (names.length) return names.join("、");
    return p.busy ? "AI 池正在工作" : "";
  }
  function sinceOf(d) {
    const p = (d && d.pool) || {}, g = (d && d.ai_gate) || {};
    const s = (g.busy || []).map((x) => x.since).filter(Boolean);
    return s.length ? Math.min.apply(null, s) : (p.busy ? p.started : 0);
  }

  function setTab(t) {
    S.tab = TABS.some((x) => x[0] === t) ? t : "reply";
    store.set("tab", S.tab);
    el.querySelectorAll("[data-ail-tab]").forEach((b) => { const on = b.dataset.ailTab === S.tab; b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); });
    el.querySelectorAll("[data-ail-pane]").forEach((x) => { x.hidden = x.dataset.ailPane !== S.tab; });
  }

  function render() {
    if (!el) return;
    const d = S.d, busy = busyOf(d), now = (d && d.now) || Date.now() / 1000;
    const recent = !busy && S.idleAt && Date.now() - S.idleAt < 10000;   // 刚做完：再留 10 秒说一声，然后自己收起来
    const held = !busy && S.open && S.hold && Date.now() - S.holdAt < 90000;   // 你点开的、AI 池这会儿还没轮到：开着等一会儿
    const show = !!d && (busy || recent || held) && !inlineShown();
    el.hidden = !show;
    document.body.classList.toggle("cx-ail-on", show);                    // 页面上的小提示往上让一让
    if (!show) return;
    const p = d.pool || {}, g = d.ai_gate || {};
    const what = busy ? whatOf(d) : "", since = busy ? sinceOf(d) : 0, waiting = g.waiting || 0;
    el.classList.toggle("busy", busy);
    el.classList.toggle("open", S.open);
    // 折叠时的一条
    const bar = el.querySelector(".cx-ail-bar");
    bar.hidden = S.open;
    bar.setAttribute("aria-expanded", String(S.open));
    el.querySelector(".cx-ail-bt").textContent = busy ? "AI 池正在做：" + what : "AI 池刚做完" + (S.lastWhat ? "：" + S.lastWhat : "");
    el.querySelector(".cx-ail-bm").textContent = busy ? dur(now - since) + (waiting ? " · 还有 " + waiting + " 个在排队" : "") : "";
    // 展开的面板
    const panel = el.querySelector(".cx-ail-panel");
    panel.hidden = !S.open;
    if (!S.open) return;
    el.querySelector(".cx-ail-what").textContent = busy ? "正在做：" + what + " · 已用 " + dur(now - since) + (waiting ? " · 还有 " + waiting + " 个在排队" : "")
      : recent ? "刚做完：" + (S.lastWhat || "AI 池的活") + "。结果在它自己的页面里。"
      : "AI 池这会儿没在写。任务如果还在读资料、联网查资料，交给 AI 池以后这里会自己动起来。";
    const stage = [];
    if (p.stage) stage.push("AI 池：" + p.stage);
    if (p.reply_len) stage.push("已经写了 " + p.reply_len + " 字");
    el.querySelector(".cx-ail-stage").textContent = stage.join(" · ");
    // 截图
    const img = el.querySelector(".cx-ail-shot img"), note = el.querySelector(".cx-ail-note");
    if (p.has_shot && p.shot_ts && (p.shot_ts !== S.shotTs || img.hidden)) {
      S.shotTs = p.shot_ts;
      img.src = backend() + "/ai_live_shot?t=" + encodeURIComponent(p.shot_ts);
      img.hidden = false;
    }
    if (!p.hasBrowser) note.textContent = p.headless ? "AI 池是后台模式（不显示浏览器），这里只有文字进度" : "AI 池浏览器还没打开（换卡 / 启动中）";
    else if (p.shot_err) note.textContent = "截图暂时失败，文字进度照常更新";
    else if (p.shot_ts) { const ago = Math.max(0, Math.round(now - p.shot_ts)); note.textContent = ago <= 3 ? "实时画面 · 点图片放大" : "画面更新于 " + ago + " 秒前"; }
    else note.textContent = "等待画面…";
    // AI 正在写的
    const rep = el.querySelector(".cx-ail-reply");
    const nearBottom = rep.scrollHeight - rep.scrollTop - rep.clientHeight < 40;
    let txt = p.reply_tail || "";
    if (p.reply_len > txt.length) txt = "…（前面还有 " + (p.reply_len - txt.length) + " 字）\n" + txt;
    if (!txt) txt = busy ? "AI 还没开始写（可能在排队、换卡、选模型、联网搜索、思考中…）" : "（现在没有在写的内容）";
    if (rep.textContent !== txt) { rep.textContent = txt; if (nearBottom) rep.scrollTop = rep.scrollHeight; }
    // 步骤记录
    const steps = el.querySelector(".cx-ail-steps");
    const html = (p.log || []).slice(-25).map((r) => '<div class="cx-ail-step"><span>' + clock(r[0]) + "</span>" + esc(r[1]) + "</div>").join("") ||
      '<p class="cx-ail-empty">还没有记录。</p>';
    if (steps.innerHTML !== html) { steps.innerHTML = html; steps.scrollTop = steps.scrollHeight; }
    // 排队
    const q = el.querySelector(".cx-ail-queue");
    const qh = (g.busy || []).map((x) => '<div class="cx-ail-qi on"><b>正在做</b>' + esc(x.what) + "<span>" + dur(now - x.since) + "</span></div>").join("") +
      (g.queue || []).map((x, i) => '<div class="cx-ail-qi"><b>第 ' + (i + 1) + " 个等</b>" + esc(x.what) + "<span>等了 " + dur(now - x.since) + "</span></div>").join("") +
      (!(g.queue || []).length && waiting ? '<p class="cx-ail-empty">还有 ' + waiting + " 个在排队。</p>" : "") ||
      '<p class="cx-ail-empty">' + (busy ? "没有别的在排队。" : "现在没有在排队的。") + "</p>";
    if (q.innerHTML !== qh) q.innerHTML = qh;
    const qt = el.querySelector('[data-ail-tab="queue"]');
    if (qt) qt.textContent = "排队" + (waiting ? "（" + waiting + "）" : "");
    // 显示 / 隐藏浏览器
    const bb = el.querySelector('[data-ail="browser"]');
    const vis = p.visible === true || (p.visible == null && p.hidden_pref === false);
    bb.dataset.visible = vis ? "1" : "0";
    bb.textContent = vis ? "隐藏浏览器" : "显示浏览器";
    bb.disabled = !!p.headless;
  }

  async function poll() {
    clearTimeout(S.timer);
    const watching = S.open && !document.hidden && !!el && !el.hidden;
    let d = null;
    try {
      const r = await fetch(backend() + "/ai_live?watch=" + (watching || (S.open && S.hold) ? "1" : "0"), { cache: "no-store" });
      d = await r.json();
      S.failed = 0;
    } catch (e) {
      S.failed++;
    }
    if (d) {
      const was = busyOf(S.d), busy = busyOf(d);
      if (busy) { S.idleAt = 0; S.lastWhat = whatOf(d); }
      else if (was) { S.idleAt = Date.now(); S.hold = false; }        // 做完了：说一声就收起来（展开 / 折叠的习惯照样记着）
      S.d = d;
    } else if (S.failed > 2) S.d = null;            // 连不上后台（刚启动 / 关了）：先藏起来
    if (S.d && !busyOf(S.d) && !S.open) S.hold = false;
    render();
    const busy = busyOf(S.d);
    const gap = document.hidden ? 8000 : S.open && el && !el.hidden ? 1500 : busy ? 3000 : S.failed ? 8000 : 3000;
    S.timer = setTimeout(poll, gap);
  }

  function open() {                                 // 别的地方的「看实时画面」按钮也调这个
    if (!el) build();
    S.open = true;
    S.hold = true;                                  // 是你点开的：就算这会儿 AI 池还没轮到也先开着（最多 90 秒）
    S.holdAt = Date.now();
    store.set("open", true);
    render();
    poll();
    setTimeout(() => { const f = el.querySelector(".cx-ail-fold"); if (f && !el.hidden) f.focus(); }, 60);
  }
  function fold() {
    S.open = false;
    S.hold = false;
    store.set("open", false);
    render();
    const b = el.querySelector(".cx-ail-bar");
    if (b && !el.hidden) b.focus();
  }

  async function onClick(e) {
    const t = e.target;
    let b;
    if ((b = t.closest("[data-ail-tab]"))) { setTab(b.dataset.ailTab); return; }
    if (t.closest(".cx-ail-shot img")) { zoom(t.closest(".cx-ail-shot img").src); return; }
    if (!(b = t.closest("[data-ail]"))) return;
    const a = b.dataset.ail;
    if (a === "open") open();
    else if (a === "fold") fold();
    else if (a === "term") { if (typeof openTerminalWindow === "function") openTerminalWindow(); }
    else if (a === "browser") {
      b.disabled = true;
      let r = null;
      try {
        r = await (await fetch(backend() + "/web_model/window", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: b.dataset.visible === "1" ? "hide" : "show" }) })).json();
      } catch (err) { r = { ok: false, message: "出错：" + err.message }; }
      msg((r && r.message) || (r && r.ok ? "好了" : "没做到"));
      b.disabled = false;
      setTimeout(poll, 300);
    }
  }
  function msg(text) {
    const m = el && el.querySelector(".cx-ail-msg");
    if (!m) return;
    m.textContent = text || "";
    clearTimeout(msg.t);
    if (text) msg.t = setTimeout(() => { m.textContent = ""; }, 6000);
  }
  function zoom(src) {
    if (typeof vnLiveZoom === "function") { vnLiveZoom(src); return; }
    const ov = document.createElement("div");
    ov.className = "cx-ail-zoom";
    ov.title = "点任意处关闭";
    ov.innerHTML = '<img alt="" src="' + esc(src) + '">';
    ov.addEventListener("click", () => ov.remove());
    document.body.appendChild(ov);
  }
  // 终端抽屉开着时，往上让一让
  function lift() {
    if (!el) return;
    const td = document.querySelector(".term-drawer:not([hidden])");
    el.style.bottom = td ? Math.round(td.getBoundingClientRect().height) + 12 + "px" : "";
  }

  function start() {
    build();
    setTab(S.tab);
    S.hold = false;
    poll();
    setInterval(() => { lift(); if (S.d) render(); }, 1000);      // 换页、开关终端、每秒的用时
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  }
  window.cxAiLive = { open, fold, toggle: () => (S.open ? fold() : open()) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
