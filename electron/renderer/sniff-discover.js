// sniff-discover.js — 嗅探「按关键词找信息源」：输入关键词 → 后台让 AI 池找行业前 N 个信息源 →
// 逐个检查能否打开 → 勾选后一键加入嗅探清单。依赖 renderer.js 里的 BACKEND / escapeHtml / loadSniffSources。
(function () {
  const $ = (id) => document.getElementById(id);
  const kwInput = $("sniffKw"), btn = $("sniffKwBtn");
  if (!kwInput || !btn) return;
  const stateEl = $("sniffKwState"), listEl = $("sniffKwList"), actEl = $("sniffKwActions");
  const esc = (s) => (typeof escapeHtml === "function" ? escapeHtml(s) : String(s || ""));
  let timer = null, results = [];

  function setState(text, kind) {
    stateEl.hidden = !text;
    stateEl.className = "kw-state" + (kind ? " " + kind : "");
    stateEl.textContent = text || "";
  }

  function render() {
    listEl.hidden = !results.length;
    actEl.hidden = !results.length;
    listEl.innerHTML = results.map((r, i) => {
      const st = r.exists ? "exists" : (r.status || "checking");
      const badge = r.exists ? "已在清单" : (st === "ok" ? "可访问" : st === "fail" ? "打不开" : "检查中…");
      const canPick = !r.exists && st !== "fail";
      const checked = canPick && st === "ok" && r._picked !== false;
      const tags = [r.type, r.region].filter(Boolean).map((t) => '<span class="kw-tag">' + esc(t) + "</span>").join("");
      return (
        '<label class="kw-item ' + st + '" title="' + esc(r.detail || "") + '">' +
          '<input type="checkbox" class="kw-cb" data-i="' + i + '"' + (checked ? " checked" : "") + (canPick ? "" : " disabled") + " />" +
          '<span class="kw-rank">' + (i + 1) + "</span>" +
          '<span class="kw-main">' +
            '<span class="kw-name">' + esc(r.name) + tags + "</span>" +
            '<span class="kw-url">' + esc(r.url) + "</span>" +
            (r.why ? '<span class="kw-why">' + esc(r.why) + "</span>" : "") +
            (st === "fail" && r.detail ? '<span class="kw-err">' + esc(r.detail) + "</span>" : "") +
          "</span>" +
          '<span class="kw-badge ' + st + '">' + badge + "</span>" +
        "</label>"
      );
    }).join("");
    listEl.querySelectorAll(".kw-cb").forEach((cb) =>
      cb.addEventListener("change", () => { results[+cb.dataset.i]._picked = cb.checked; }));
  }

  async function poll() {
    try {
      const d = await (await fetch(BACKEND + "/sniff/discover")).json();
      results = (d.results || []).map((r, i) => Object.assign({}, r, { _picked: (results[i] || {})._picked }));
      render();
      if (d.error) setState("没找成：" + d.error, "bad");
      else setState((d.stage || "") + (d.note ? "　" + d.note : ""), d.running ? "busy" : "done");
      if (!d.running) {
        clearInterval(timer); timer = null;
        btn.disabled = false; btn.textContent = "查找";
      }
    } catch (e) { /* 后台忙时偶尔失败，下次再查 */ }
  }

  btn.addEventListener("click", async () => {
    const kw = kwInput.value.trim();
    if (!kw) { kwInput.focus(); return; }
    btn.disabled = true; btn.textContent = "查找中…";
    results = []; render();
    $("sniffKwCat").value = kw;
    setState("正在提交…", "busy");
    try {
      const d = await (await fetch(BACKEND + "/sniff/discover", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: kw, n: +$("sniffKwN").value || 15 }),
      })).json();
      if (!d.ok) { setState(d.message || "没能开始", "bad"); btn.disabled = false; btn.textContent = "查找"; return; }
      if (timer) clearInterval(timer);
      timer = setInterval(poll, 1500);
      poll();
    } catch (e) {
      setState("提交出错：" + e.message, "bad"); btn.disabled = false; btn.textContent = "查找";
    }
  });
  kwInput.addEventListener("keydown", (e) => { if (e.key === "Enter") btn.click(); });

  $("sniffKwAll").addEventListener("change", (e) => {
    results.forEach((r) => { if (!r.exists && r.status === "ok") r._picked = e.target.checked; });
    render();
  });

  $("sniffKwAdd").addEventListener("click", async () => {
    const picked = [...listEl.querySelectorAll(".kw-cb:checked")].map((cb) => results[+cb.dataset.i]);
    if (!picked.length) { setState("先勾选要加入的网站", "bad"); return; }
    const cat = $("sniffKwCat").value.trim() || kwInput.value.trim() || "AI动态";
    const add = $("sniffKwAdd"); add.disabled = true;
    let ok = 0; const fails = [];
    for (const r of picked) {
      try {
        const d = await (await fetch(BACKEND + "/sniff/source/add", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: r.name, url: r.url, category: cat }),
        })).json();
        if (d.ok) { ok++; r.exists = true; } else fails.push(r.name + "：" + (d.message || "失败"));
      } catch (e) { fails.push(r.name + "：" + e.message); }
    }
    add.disabled = false;
    render();
    setState("已加入 " + ok + " 个到「" + cat + "」类别" + (fails.length ? "；没加上：" + fails.join("；") : "") +
             "。点上面「快速嗅探」开始盯它们（第一次只记快照）。", fails.length ? "bad" : "done");
    if (typeof loadSniffSources === "function") loadSniffSources();
  });
})();
