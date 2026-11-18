// logview.js — 终端日志查看器（v55 新增）
// 软件里的「终端」抽屉、独立的终端窗口都用它：从后端 /logs 增量读日志，像黑窗口一样滚动显示。
// 用法：const v = CxLogView.mount(容器元素, { backend: () => "http://127.0.0.1:8756" }); v.start();
(function () {
  "use strict";

  const MAX_DOM_LINES = 4000;          // 页面上最多留多少行，太多会卡
  const API_RE = /^\[\d{2}:\d{2}:\d{2}\]\s+操作\s+/;   // 「操作 GET /xxx」这类接口请求日志

  function lineClass(s) {
    if (/Traceback|Error|ERROR|错误|出错|失败|✖|✗|\[error\]|异常/.test(s)) return "lv-err";
    if (/⚠|\[warn\]|警告|超时|卡死|看门狗/.test(s)) return "lv-warn";
    if (/✓|✔|\[ok\]|成功|已就绪|完成/.test(s)) return "lv-ok";
    if (/^\[web_model\]/.test(s)) return "lv-ai";
    if (API_RE.test(s)) return "lv-api";
    if (/^\[(gpu|backend|video|agents|insight|creator)\]|^\[\d{2}:\d{2}:\d{2}\]/.test(s)) return "lv-sys";
    return "";
  }

  function mount(root, opts) {
    opts = opts || {};
    const getBackend = opts.backend || (() => "http://127.0.0.1:8756");
    root.classList.add("lv-root");
    root.innerHTML =
      '<div class="lv-bar">' +
        '<input class="lv-filter" type="search" placeholder="筛选（输入关键字，只看包含它的行）" />' +
        '<label class="lv-opt"><input type="checkbox" class="lv-hide-api" checked /> 隐藏接口请求</label>' +
        '<label class="lv-opt"><input type="checkbox" class="lv-only-ai" /> 只看 AI 池</label>' +
        '<span class="lv-spacer"></span>' +
        '<button class="lv-btn lv-copy" title="把当前显示的日志复制到剪贴板">复制</button>' +
        '<button class="lv-btn lv-clear" title="只是清空这里的显示，不影响软件">清屏</button>' +
      "</div>" +
      '<div class="lv-out" tabindex="0"></div>' +
      '<button class="lv-tobottom" hidden>↓ 回到最新</button>' +
      '<div class="lv-status"></div>';
    const out = root.querySelector(".lv-out");
    const filterEl = root.querySelector(".lv-filter");
    const hideApiEl = root.querySelector(".lv-hide-api");
    const onlyAiEl = root.querySelector(".lv-only-ai");
    const toBottom = root.querySelector(".lv-tobottom");
    const status = root.querySelector(".lv-status");

    // 记住筛选开关
    try {
      const saved = JSON.parse(localStorage.getItem("cxLogViewOpts") || "{}");
      if (typeof saved.hideApi === "boolean") hideApiEl.checked = saved.hideApi;
      if (typeof saved.onlyAi === "boolean") onlyAiEl.checked = saved.onlyAi;
    } catch (_) {}
    const saveOpts = () => {
      try {
        localStorage.setItem("cxLogViewOpts", JSON.stringify({ hideApi: hideApiEl.checked, onlyAi: onlyAiEl.checked }));
      } catch (_) {}
    };

    let since = 0;
    let all = [];              // 全部收到的行 {n, t, s}
    let clearedAt = 0;         // 清屏时的序号：之前的行不再显示
    let timer = null;
    let running = false;
    let stick = true;          // 是否跟着最新一行自动滚动
    let failCount = 0;

    function visible(row) {
      if (row.n <= clearedAt) return false;
      const s = row.s;
      if (hideApiEl.checked && API_RE.test(s)) return false;
      if (onlyAiEl.checked && !/^\[web_model\]|AI池|AI 池|批量|分析/.test(s)) return false;
      const f = filterEl.value.trim();
      if (f && s.toLowerCase().indexOf(f.toLowerCase()) < 0) return false;
      return true;
    }

    function fmtTime(t) {
      const d = new Date(t * 1000);
      return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0") + ":" +
        String(d.getSeconds()).padStart(2, "0");
    }

    function makeLine(row) {
      const div = document.createElement("div");
      div.className = "lv-line " + lineClass(row.s);
      // 后端自己带 [时:分:秒] 的行不再重复加时间
      if (!/^\[\d{2}:\d{2}:\d{2}\]/.test(row.s)) {
        const ts = document.createElement("span");
        ts.className = "lv-ts";
        ts.textContent = fmtTime(row.t) + " ";
        div.appendChild(ts);
      }
      div.appendChild(document.createTextNode(row.s || " "));
      return div;
    }

    function trimDom() {
      while (out.childElementCount > MAX_DOM_LINES) out.removeChild(out.firstElementChild);
    }

    function rerender() {
      out.innerHTML = "";
      const frag = document.createDocumentFragment();
      const rows = all.filter(visible).slice(-MAX_DOM_LINES);
      rows.forEach((r) => frag.appendChild(makeLine(r)));
      out.appendChild(frag);
      if (stick) out.scrollTop = out.scrollHeight;
    }

    function append(rows) {
      if (!rows.length) return;
      const frag = document.createDocumentFragment();
      rows.filter(visible).forEach((r) => frag.appendChild(makeLine(r)));
      out.appendChild(frag);
      trimDom();
      if (stick) out.scrollTop = out.scrollHeight;
    }

    out.addEventListener("scroll", () => {
      const nearBottom = out.scrollHeight - out.scrollTop - out.clientHeight < 40;
      stick = nearBottom;
      toBottom.hidden = nearBottom;
    });
    toBottom.addEventListener("click", () => {
      stick = true; toBottom.hidden = true; out.scrollTop = out.scrollHeight;
    });
    let ft = null;
    filterEl.addEventListener("input", () => { clearTimeout(ft); ft = setTimeout(rerender, 200); });
    hideApiEl.addEventListener("change", () => { saveOpts(); rerender(); });
    onlyAiEl.addEventListener("change", () => { saveOpts(); rerender(); });
    root.querySelector(".lv-clear").addEventListener("click", () => {
      clearedAt = since; out.innerHTML = "";
    });
    root.querySelector(".lv-copy").addEventListener("click", async (e) => {
      const text = all.filter(visible).map((r) => r.s).join("\n");
      const btn = e.currentTarget;
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = "已复制";
      } catch (_) {
        btn.textContent = "复制失败";
      }
      setTimeout(() => { btn.textContent = "复制"; }, 1500);
    });

    async function tick() {
      if (!running) return;
      try {
        const url = getBackend() + "/logs?since=" + since + (since ? "" : "&limit=2500");
        const d = await (await fetch(url, { cache: "no-store" })).json();
        failCount = 0;
        const rows = d.lines || [];
        if (d.gap) {
          all.push({ n: since + 0.5, t: Date.now() / 1000, s: "…（中间有一部分日志太旧，已经滚出去了）" });
        }
        if (rows.length) {
          since = rows[rows.length - 1].n;
          all = all.concat(rows);
          if (all.length > 8000) all = all.slice(-6000);
          append(rows);
        } else if (d.last && d.last < since) {
          // 后端重启过（序号从头开始了）
          since = 0; all = []; clearedAt = 0; out.innerHTML = "";
        }
        status.textContent = "";
        status.hidden = true;
      } catch (e) {
        failCount++;
        if (failCount >= 2) {
          status.hidden = false;
          status.textContent = "后端没连上（软件可能正在启动或已关闭），会自动重连…";
        }
      }
      if (running) timer = setTimeout(tick, document.hidden ? 3000 : 1000);
    }

    return {
      start() { if (running) return; running = true; tick(); },
      stop() { running = false; clearTimeout(timer); },
      focusFilter() { filterEl.focus(); },
    };
  }

  window.CxLogView = { mount };
})();
