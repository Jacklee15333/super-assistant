// ============================================================
// ai-live.js —— v190：「AI 池」实时画面，嵌在各处的进度标题下面（和「加工」的 AI 分析一样）
//   商业（顶上的进度条、商业定制的「正在写：…」）、知识库（「正在收录…」）：标题后面有「▸ 实时画面」，
//   点标题就在它下面展开 AI 池的实时画面——浏览器截图、AI 正在写的字、步骤记录、排队；再点「▾ 收起」折叠。
//   每一处展开还是收起分别记住。v189 那个右下角单独弹出的窗口不要了。
//   用法：标题写成 <button data-ail-toggle="名字">…<span class="cx-ail-caret"></span></button>，
//         下面放一个 <div class="cx-ail-slot"></div>，画完调 cxAiLive.place("名字", 这个 div)；不在跑了调 place("名字", null)。
//   只有展开着、看得见的时候才去问、才截图（/ai_live?watch=1），收起时不费资源。
// ============================================================
(function () {
  "use strict";
  const backend = () => { try { if (typeof BACKEND === "string" && BACKEND) return BACKEND; } catch (e) {} return "http://127.0.0.1:8756"; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pad = (n) => (n < 10 ? "0" : "") + n;
  const dur = (s) => { s = Math.max(0, Math.round(s || 0)); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return (h ? h + ":" + pad(m) : pad(m)) + ":" + pad(s % 60); };
  const clock = (t) => { const d = new Date(t * 1000); return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()); };
  const get = (k, d) => { try { const v = localStorage.getItem("cx.aiLive." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
  const put = (k, v) => { try { localStorage.setItem("cx.aiLive." + k, JSON.stringify(v)); } catch (e) {} };

  const boxes = {};          // 名字 → 实时画面那一块（一直留着，标题重画时挪回新的位置，画面不闪）
  const slots = {};          // 名字 → 现在放在哪个格子里
  let timer = null, tab = get("tab", "reply");

  const isOpen = (key) => !!get("open." + key, false);
  const caret = (key) => (isOpen(key) ? "▾ 收起" : "▸ 实时画面");

  function build(key) {
    const b = document.createElement("div");
    b.className = "vn-live cx-ail-in";
    b.dataset.ailKey = key;
    b.innerHTML =
      '<div class="vn-live-body">' +
        '<div class="vn-live-stage cx-ail-stage" aria-live="polite"></div>' +
        '<div class="vn-live-grid">' +
          '<div class="vn-live-shotbox"><img class="cx-ail-shot" alt="AI 池浏览器的实时画面" hidden />' +
            '<div class="vn-live-shotnote cx-ail-note">等待画面…</div></div>' +
          '<div class="vn-live-side">' +
            '<div class="vn-live-tabs"><button type="button" class="vn-live-tab" data-ail-tab="reply">AI 回复（实时）</button>' +
              '<button type="button" class="vn-live-tab" data-ail-tab="steps">步骤记录</button>' +
              '<button type="button" class="vn-live-tab" data-ail-tab="queue">排队</button></div>' +
            '<pre class="vn-live-reply cx-ail-reply" data-ail-pane="reply"></pre>' +
            '<div class="vn-live-steps cx-ail-steps" data-ail-pane="steps" hidden></div>' +
            '<div class="vn-live-steps cx-ail-queue" data-ail-pane="queue" hidden></div>' +
          "</div>" +
        "</div>" +
        '<div class="vn-live-actions"><button type="button" class="vn-batch-stop" data-ail="browser" title="把 AI 池浏览器调到屏幕上 / 挪回屏幕外（挪走后照常工作）">显示浏览器</button>' +
          '<button type="button" class="vn-batch-stop" data-ail="term" title="在单独的窗口里看后台日志">显示终端</button>' +
          '<span class="vn-live-msg cx-ail-msg"></span></div>' +
      "</div>";
    b.addEventListener("click", onBoxClick);
    boxes[key] = b;
    setTab(b, tab);
    return b;
  }
  function setTab(b, t) {
    b.querySelectorAll("[data-ail-tab]").forEach((x) => x.classList.toggle("active", x.dataset.ailTab === t));
    b.querySelectorAll("[data-ail-pane]").forEach((x) => { x.hidden = x.dataset.ailPane !== t; });
  }
  // 各处的标题（可能有好几个指向同一块，比如商业的进度条和「正在写」）一起更新
  function syncLabels(key) {
    document.querySelectorAll('[data-ail-toggle="' + key + '"]').forEach((t) => {
      t.setAttribute("aria-expanded", String(isOpen(key)));
      t.title = isOpen(key) ? "点一下收起 AI 实时画面" : "点一下看 AI 池的实时画面";
      const c = t.querySelector(".cx-ail-caret");
      if (c) c.textContent = caret(key);
    });
  }
  function place(key, slot) {
    const b = boxes[key] || build(key);
    if (slots[key] && slots[key] !== slot && slots[key].isConnected) slots[key].hidden = true;
    slots[key] = slot || null;
    if (!slot) { if (b.parentNode) b.parentNode.removeChild(b); syncLabels(key); return; }
    if (b.parentNode !== slot) slot.appendChild(b);
    slot.hidden = !isOpen(key);
    syncLabels(key);
    if (isOpen(key)) kick();
  }
  function toggle(key, force) {
    put("open." + key, typeof force === "boolean" ? force : !isOpen(key));
    const s = slots[key];
    if (s && s.isConnected) s.hidden = !isOpen(key);
    syncLabels(key);
    kick();
    return isOpen(key);
  }

  function update(b, d) {
    const p = d.pool || {}, g = d.ai_gate || {}, now = d.now || Date.now() / 1000;
    const holders = g.busy || [], waiting = g.waiting || 0;
    const st = [];
    if (holders.length) st.push("AI 池正在做：" + holders.map((x) => x.what).join("、") + "（" + dur(now - Math.min.apply(null, holders.map((x) => x.since))) + "）");
    if (p.stage) st.push("AI 池：" + p.stage + (p.busy ? "" : "（空闲）"));
    if (p.reply_len) st.push("已经写了 " + p.reply_len + " 字");
    if (waiting) st.push("还有 " + waiting + " 个在排队");
    if (!holders.length && !p.busy) st.unshift("AI 池这会儿没在写：任务如果还在读资料、联网查资料，交给 AI 池后这里会自己动起来");
    b.querySelector(".cx-ail-stage").textContent = st.join(" · ");
    const img = b.querySelector(".cx-ail-shot"), note = b.querySelector(".cx-ail-note");
    if (p.has_shot && p.shot_ts && (p.shot_ts !== b._ts || img.hidden)) {
      b._ts = p.shot_ts;
      img.src = backend() + "/ai_live_shot?t=" + encodeURIComponent(p.shot_ts);
      img.hidden = false;
    }
    if (!p.hasBrowser) note.textContent = p.headless ? "AI 池是后台模式（不显示浏览器），这里只有文字进度" : "AI 池浏览器还没打开（换卡 / 启动中）";
    else if (p.shot_err) note.textContent = "截图暂时失败，文字进度照常更新";
    else if (p.shot_ts) { const ago = Math.max(0, Math.round(now - p.shot_ts)); note.textContent = ago <= 3 ? "实时画面 · 点图片放大" : "画面更新于 " + ago + " 秒前"; }
    else note.textContent = "等待画面…";
    const rep = b.querySelector(".cx-ail-reply");
    const nearBottom = rep.scrollHeight - rep.scrollTop - rep.clientHeight < 40;
    let txt = p.reply_tail || "";
    if (p.reply_len > txt.length) txt = "…（前面还有 " + (p.reply_len - txt.length) + " 字）\n" + txt;
    if (!txt) txt = p.busy ? "AI 还没开始写（可能在换卡、选模型、联网搜索、思考中…）" : "（现在没有在写的内容）";
    if (rep.textContent !== txt) { rep.textContent = txt; if (nearBottom) rep.scrollTop = rep.scrollHeight; }
    const steps = b.querySelector(".cx-ail-steps");
    const sh = (p.log || []).slice(-25).map((r) => '<div class="vn-live-step"><span class="vn-live-step-t">' + clock(r[0]) + "</span>" + esc(r[1]) + "</div>").join("") || "还没有记录。";
    if (steps.innerHTML !== sh) { steps.innerHTML = sh; steps.scrollTop = steps.scrollHeight; }
    const q = b.querySelector(".cx-ail-queue");
    const qh = holders.map((x) => '<div class="vn-live-step"><span class="vn-live-step-t">正在做</span>' + esc(x.what) + "（" + dur(now - x.since) + "）</div>").join("") +
      (g.queue || []).map((x, i) => '<div class="vn-live-step"><span class="vn-live-step-t">第 ' + (i + 1) + " 个等</span>" + esc(x.what) + "（等了 " + dur(now - x.since) + "）</div>").join("") ||
      (p.busy ? "AI 池在忙，没有别的在排队。" : "现在没有在排队的。");
    if (q.innerHTML !== qh) q.innerHTML = qh;
    const qt = b.querySelector('[data-ail-tab="queue"]');
    if (qt) qt.textContent = "排队" + (waiting ? "（" + waiting + "）" : "");
    const bb = b.querySelector('[data-ail="browser"]');
    const vis = p.visible === true || (p.visible == null && p.hidden_pref === false);
    bb.dataset.visible = vis ? "1" : "0";
    bb.textContent = vis ? "隐藏浏览器" : "显示浏览器";
    bb.disabled = !!p.headless;
  }

  function kick() { clearTimeout(timer); timer = setTimeout(tick, 30); }
  async function tick() {
    clearTimeout(timer);
    const live = Object.keys(boxes).filter((k) => isOpen(k) && boxes[k].isConnected && boxes[k].offsetParent !== null);
    if (!live.length || document.hidden) { timer = setTimeout(tick, 2500); return; }
    let d = null;
    try { d = await (await fetch(backend() + "/ai_live?watch=1", { cache: "no-store" })).json(); } catch (e) {}
    if (d) live.forEach((k) => { if (boxes[k].isConnected) update(boxes[k], d); });
    timer = setTimeout(tick, d ? 1500 : 4000);
  }

  async function onBoxClick(e) {
    const t = e.target, b = e.currentTarget;
    let x;
    if ((x = t.closest("[data-ail-tab]"))) { tab = x.dataset.ailTab; put("tab", tab); Object.values(boxes).forEach((y) => setTab(y, tab)); return; }
    if (t.closest(".cx-ail-shot")) { zoom(t.closest(".cx-ail-shot").src); return; }
    if (!(x = t.closest("[data-ail]"))) return;
    if (x.dataset.ail === "term") { if (typeof openTerminalWindow === "function") openTerminalWindow(); return; }
    if (x.dataset.ail === "browser") {
      x.disabled = true;
      let r = null;
      try {
        r = await (await fetch(backend() + "/web_model/window", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: x.dataset.visible === "1" ? "hide" : "show" }) })).json();
      } catch (err) { r = { ok: false, message: "出错：" + err.message }; }
      const m = b.querySelector(".cx-ail-msg");
      if (m) { m.textContent = (r && r.message) || (r && r.ok ? "好了" : "没做到"); setTimeout(() => { m.textContent = ""; }, 6000); }
      x.disabled = false;
      kick();
    }
  }
  function zoom(src) {
    if (typeof vnLiveZoom === "function") { vnLiveZoom(src); return; }
    const ov = document.createElement("div");
    ov.className = "vn-live-zoom";
    ov.innerHTML = '<img alt="" src="' + esc(src) + '">';
    ov.addEventListener("click", () => ov.remove());
    document.body.appendChild(ov);
  }
  // 点标题（任何一处带 data-ail-toggle 的）就展开 / 收起它下面的实时画面
  document.addEventListener("click", (e) => {
    const t = e.target.closest && e.target.closest("[data-ail-toggle]");
    if (!t) return;
    e.preventDefault();
    toggle(t.dataset.ailToggle);
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) kick(); });

  window.cxAiLive = { place, toggle, isOpen, caret, open: (key) => toggle(key || "biz", true) };
  kick();
})();
