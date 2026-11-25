// ============================================================
// biz.js —「商业」（v155 新增）：市场动向 · 行业 · 商业模式 · 趋势与机会 · 研究报告
//   · 资料来自你收进来的内容：笔记（加工好的）、嗅探到的网站动态、博主新内容；后台（biz_intel.py）按行业、赛道、商业模式归好类。
//   · 行业：申万 31 个一级行业 + 二级行业 + 新兴赛道，「地图」「列表」两种看法；每个行业都能网上查看、让小助联网研究。
//   · 商业模式：输入公司 / 产品 / 生意 → 小助联网查资料 + 结合笔记拆解，报告里画上下游产业链图。
//   · 写报告在后台跑（排队用 AI 池），页面顶上一条进度；写好的都在「研究报告」。
// 顶部五个标签由 renderer.js 的 NAV_GROUPS.biz 画，切换时调 window.cxPaneShow.biz(标签)。
// 复用全局：BACKEND、renderMarkdown、navOpenGroup、openVideoNote（都可能不存在，判断了再用）。
// ============================================================
(function () {
  "use strict";
  const root = document.getElementById("view-biz");
  if (!root) return;

  const PANES = ["market", "industry", "model", "opps", "reports"];
  const KIND = { market: "市场动向", industry: "行业研究", model: "商业模式", trend: "趋势与机会", research: "课题研究" };
  const SRC = { note: "笔记", sniff: "网站动态", creator: "博主新内容" };
  const OPP_ST = [["new", "新发现"], ["watch", "关注"], ["testing", "验证中"], ["doing", "在做"], ["dropped", "放弃"]];
  const EG_MODEL = ["蜜雪冰城", "胖东来", "泡泡玛特", "瑞幸咖啡", "名创优品", "社区团购"];
  const EG_RESEARCH = ["低空经济", "AI 一人公司", "宠物殡葬", "银发旅游", "AI 陪伴硬件"];

  const backend = () => { try { if (typeof BACKEND === "string" && BACKEND) return BACKEND; } catch (e) {} return "http://127.0.0.1:8756"; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById(id);
  const md = (s) => (typeof renderMarkdown === "function" ? renderMarkdown(s || "") : "<pre>" + esc(s) + "</pre>");
  const enc = encodeURIComponent;
  const pad = (n) => (n < 10 ? "0" : "") + n;
  const store = {
    get(k, d) { try { const v = localStorage.getItem("biz." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("biz." + k, JSON.stringify(v)); } catch (e) {} },
  };
  const api = (path, body) => fetch(backend() + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined)
    .then((r) => r.json());
  const fmtTime = (ts) => { if (!ts) return ""; const d = new Date(ts * 1000); return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + pad(d.getHours()) + ":" + pad(d.getMinutes()); };
  const loading = (t) => '<p class="bz-empty">' + esc(t || "正在读取…") + "</p>";
  const empty = (t) => '<p class="bz-empty">' + t + "</p>";

  const S = {
    pane: PANES.includes(store.get("pane", "market")) ? store.get("pane", "market") : "market",
    tax: null, byId: {}, ov: null, ovErr: "", days: store.get("days", 30),
    feed: null, feedSrc: "all", feedQ: "",
    indView: store.get("indView", "map"), indSel: store.get("indSel", ""), indQ: "", indItems: null, openL1: {},
    mdl: "", mdCases: null, mdDepth: "quick", rsDepth: "quick",
    opps: null, oppSt: "all", reports: [], repKind: "all", repQ: "", topics: [],
    job: null, jobTimer: null, readerRep: null,
  };

  // ───────── 分类表 ─────────
  function indexTax() {
    const t = S.tax, by = {};
    t.sectors.forEach((s) => { by["sec:" + s.key] = { type: "sec", id: "sec:" + s.key, name: s.name, desc: s.desc, l1: s.l1 }; });
    t.industries.forEach((i) => {
      by[i.id] = { type: "l1", id: i.id, name: i.name, desc: i.desc, sec: i.sec, subs: i.subs.map((x) => x.id) };
      i.subs.forEach((x) => { by[x.id] = { type: "l2", id: x.id, name: x.name, desc: x.desc, kw: x.kw, co: x.co, l1: i.id, sec: i.sec }; });
    });
    t.tracks.forEach((x) => { by[x.id] = { type: "trk", id: x.id, name: x.name, desc: x.desc, kw: x.kw, rel: x.rel }; });
    t.models.forEach((x) => { by[x.id] = { type: "mdl", id: x.id, name: x.name, desc: x.desc }; });
    S.byId = by;
  }
  const nameOf = (id) => (S.byId[id] ? S.byId[id].name : String(id || "").split("/").pop());
  const secName = (key) => (S.byId["sec:" + key] || {}).name || "";
  const lvl = (n) => (!n ? 0 : n <= 2 ? 1 : n <= 5 ? 2 : n <= 12 ? 3 : n <= 30 ? 4 : 5);
  const heatOf = (id) => {
    const d = S.byId[id], o = S.ov;
    if (!o) return [0, 0];
    return (d && d.type === "l1" ? o.l1[id] : o.heat[id]) || [0, 0];
  };
  function matchQ(d) {
    const q = S.indQ.trim().toLowerCase();
    if (!q || !d) return true;
    return [d.name, d.desc, d.kw, d.co].some((x) => x && String(x).toLowerCase().includes(q));
  }
  function searchWords(id) {
    const d = S.byId[id];
    if (!d) return id;
    if (d.type === "trk") return d.name + " 产业链 市场规模 趋势";
    if (d.type === "l1") return d.name + "行业 细分领域 产业链";
    return d.name + " 行业 产业链 市场规模";
  }

  // ───────── 页面骨架 ─────────
  const seg = (name, opts) => '<div class="bz-seg" role="group" data-seg="' + name + '">' +
    opts.map(([v, t]) => '<button type="button" data-v="' + v + '" aria-pressed="false">' + t + "</button>").join("") + "</div>";

  function buildShell() {
    root.innerHTML =
      '<header class="topbar"><span>商业</span></header>' +
      '<div class="bz-job" id="bzJob" hidden></div>' +
      '<div class="bz-scroll" id="bzScroll">' +

      // ===== 市场动向 =====
      '<div class="bz-pane" data-pane="market">' +
        '<div class="bz-bar">' +
          seg("days", [["7", "7 天"], ["30", "30 天"], ["90", "90 天"], ["0", "全部"]]) +
          '<span class="sp"></span>' +
          '<select class="bz-select" id="bzMkScope" aria-label="简报范围"><option value="">全部行业</option></select>' +
          '<label class="bz-chk"><input type="checkbox" id="bzMkWeb" checked>联网补充最新消息</label>' +
          '<button type="button" class="bz-btn" id="bzMkRun">生成市场动向简报</button>' +
        "</div>" +
        '<div class="bz-cols">' +
          '<div class="bz-main">' +
            '<section class="bz-card"><div class="bz-card-h"><h3>正在升温的话题</h3></div>' +
              '<p class="bz-hint" id="bzRisingHint"></p><div class="bz-terms" id="bzRising"></div></section>' +
            '<section class="bz-card" id="bzFeedCard"><div class="bz-card-h"><h3>最新动向</h3>' +
              seg("feedsrc", [["all", "全部"], ["note", "笔记"], ["sniff", "网站动态"], ["creator", "博主新内容"]]) + "</div>" +
              '<p class="bz-filter" id="bzFeedFilter" hidden></p><div class="bz-feed" id="bzFeed"></div></section>' +
          "</div>" +
          '<aside class="bz-side">' +
            '<section class="bz-card"><div class="bz-card-h"><h3>提得最多</h3></div><div class="bz-chips" id="bzHot"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>市场动向简报</h3></div><div class="bz-reps" id="bzMkReports"></div></section>' +
            '<p class="bz-note" id="bzCounts"></p>' +
          "</aside>" +
        "</div>" +
      "</div>" +

      // ===== 行业 =====
      '<div class="bz-pane" data-pane="industry">' +
        '<div class="bz-bar">' +
          seg("indview", [["map", "地图"], ["list", "列表"]]) +
          '<input type="search" class="bz-input" id="bzIndQ" placeholder="找行业：芯片、餐饮、储能、宠物…" aria-label="找行业">' +
          '<span class="sp"></span>' +
          '<span class="bz-legend" aria-hidden="true"><i class="h1"></i><i class="h2"></i><i class="h3"></i><i class="h4"></i><i class="h5"></i></span>' +
          '<span class="bz-note">颜色越深，你收进来的相关内容越多</span>' +
        "</div>" +
        '<p class="bz-source" id="bzIndSource"></p>' +
        '<div class="bz-ind"><div class="bz-ind-main" id="bzIndMain"></div><aside class="bz-ind-detail" id="bzIndDetail"></aside></div>' +
      "</div>" +

      // ===== 商业模式 =====
      '<div class="bz-pane" data-pane="model">' +
        '<section class="bz-hero">' +
          "<h2>拆解一个商业模式</h2>" +
          "<p>输入一家公司、一个产品或一门生意。小助会联网查资料，再结合你的笔记，拆出它的客户、收入、成本、上下游产业链、护城河和可借鉴的地方。</p>" +
          '<div class="bz-form"><input class="bz-input big" id="bzMdTarget" maxlength="60" placeholder="比如：蜜雪冰城、胖东来、一家社区面包店" aria-label="要拆解的公司、产品或生意">' +
            seg("mddepth", [["quick", "快速"], ["deep", "深入"]]) +
            '<label class="bz-chk"><input type="checkbox" id="bzMdWeb" checked>联网查资料</label>' +
            '<button type="button" class="bz-btn" id="bzMdRun">开始拆解</button></div>' +
          '<div class="bz-eg">试试：' + EG_MODEL.map((x) => '<button type="button" class="bz-link" data-eg-model="' + esc(x) + '">' + esc(x) + "</button>").join("") + "</div>" +
          '<p class="bz-note">快速：上网读 9 篇左右；深入：读 20 篇左右，慢一些。报告会单独画一张「上游 → 中游 → 下游」的产业链图。</p>' +
        "</section>" +
        '<div class="bz-cols">' +
          '<div class="bz-main"><section class="bz-card"><div class="bz-card-h"><h3>你笔记里的商业模式案例</h3></div>' +
            '<div class="bz-chips" id="bzMdTypes"></div><div class="bz-feed" id="bzMdCases"></div></section></div>' +
          '<aside class="bz-side"><section class="bz-card"><div class="bz-card-h"><h3>拆解过的</h3></div><div class="bz-reps" id="bzMdReports"></div></section></aside>' +
        "</div>" +
      "</div>" +

      // ===== 趋势与机会 =====
      '<div class="bz-pane" data-pane="opps">' +
        '<div class="bz-bar">' +
          '<select class="bz-select" id="bzOpScope" aria-label="分析范围"><option value="">全部行业</option></select>' +
          '<label class="bz-chk"><input type="checkbox" id="bzOpWeb" checked>联网补充</label>' +
          '<button type="button" class="bz-btn" id="bzOpRun">分析趋势和机会</button>' +
          '<span class="sp"></span><button type="button" class="bz-btn ghost" id="bzOpAddBtn">记下我的点子</button>' +
        "</div>" +
        '<section class="bz-card bz-opadd" id="bzOpAdd" hidden><div class="bz-card-h"><h3>记下一个点子</h3></div>' +
          '<div class="bz-grid2"><label>这个机会是什么<input class="bz-input" id="bzOaTitle" maxlength="140" placeholder="一句话说清做什么"></label>' +
          '<label>适合谁<input class="bz-input" id="bzOaWho" maxlength="120" placeholder="比如：有本地资源的宝妈"></label>' +
          '<label>怎么切入<input class="bz-input" id="bzOaHow" maxlength="200" placeholder="第一步打算怎么做"></label>' +
          '<label>启动成本<select class="bz-select" id="bzOaCost"><option value="">不确定</option><option>低</option><option>中</option><option>高</option></select></label></div>' +
          '<div class="bz-btns"><button type="button" class="bz-btn" data-act="oppadd-save">保存</button><button type="button" class="bz-btn ghost" data-act="oppadd-cancel">取消</button></div></section>' +
        '<div class="bz-opbar">' + seg("oppst", [["all", "全部"]].concat(OPP_ST)) + "</div>" +
        '<div class="bz-opps" id="bzOpps"></div>' +
        '<section class="bz-card"><div class="bz-card-h"><h3>趋势与机会分析</h3></div><div class="bz-reps" id="bzOpReports"></div></section>' +
      "</div>" +

      // ===== 研究报告 =====
      '<div class="bz-pane" data-pane="reports">' +
        '<section class="bz-hero">' +
          "<h2>研究一个课题</h2>" +
          "<p>输入任何想弄明白的方向。小助会自己上网搜、读网页，再结合你的笔记，写成一份研究报告：现状、产业链、主要玩家、商业模式、趋势、机会和风险。</p>" +
          '<div class="bz-form"><input class="bz-input big" id="bzRsTarget" maxlength="60" placeholder="比如：低空经济、AI 一人公司、宠物殡葬" aria-label="研究课题">' +
            seg("rsdepth", [["quick", "快速"], ["deep", "深入"]]) +
            '<button type="button" class="bz-btn" id="bzRsRun">开始研究</button>' +
            '<button type="button" class="bz-link" id="bzRsSave">存成常用课题</button></div>' +
          '<div class="bz-eg" id="bzTopics"></div>' +
        "</section>" +
        '<section class="bz-card"><div class="bz-card-h"><h3>报告库</h3>' +
          seg("repkind", [["all", "全部"], ["market", "市场动向"], ["industry", "行业研究"], ["model", "商业模式"], ["trend", "趋势与机会"], ["research", "课题研究"]]) +
          '<input type="search" class="bz-input" id="bzRepQ" placeholder="搜报告" aria-label="搜报告"></div>' +
          '<div class="bz-reps wide" id="bzReports"></div></section>' +
      "</div>" +

      "</div>" +   // bz-scroll

      '<div class="bz-reader" id="bzReader" hidden>' +
        '<div class="bz-reader-bar"><button type="button" class="bz-back" data-act="back" title="回到刚才的位置（也可以按 Esc）">← 返回</button>' +
          '<span class="bz-reader-title"></span><span class="bz-reader-acts"></span></div>' +
        '<div class="bz-reader-body"><div class="bz-reader-inner"><div class="bz-reader-meta"></div><div class="bz-reader-content"></div></div></div>' +
      "</div>" +
      '<div class="bz-toast" id="bzToast" role="status" hidden></div>';
  }

  function segSync(name, val) {
    root.querySelectorAll('.bz-seg[data-seg="' + name + '"] button').forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === String(val))));
  }

  let toastTimer = null;
  function toast(msg) {
    const t = $("bzToast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 4200);
  }

  function fillScopes() {
    if (!S.tax) return;
    const html = '<option value="">全部行业</option><optgroup label="新兴赛道">' +
      S.tax.tracks.map((t) => '<option value="' + esc(t.id) + '">' + esc(t.name) + "</option>").join("") + "</optgroup>" +
      S.tax.sectors.map((s) => '<optgroup label="' + esc(s.name) + '"><option value="sec:' + s.key + '">整个' + esc(s.name) + "板块</option>" +
        s.l1.map((n) => '<option value="' + esc(n) + '">' + esc(n) + "</option>").join("") + "</optgroup>").join("");
    ["bzMkScope", "bzOpScope"].forEach((id) => {
      const el = $(id), keep = store.get(id, "");
      el.innerHTML = html;
      el.value = keep;
      if (el.value !== keep) el.value = "";
    });
    $("bzIndSource").innerHTML = "分类参考：" + esc(S.tax.source) + "。共 " + S.tax.counts.l1 + " 个一级行业、" + S.tax.counts.l2 +
      " 个二级行业、" + S.tax.counts.tracks + " 个新兴赛道。" + '<a href="https://www.baidu.com/s?wd=' + enc("申万行业分类 2021版 一级 二级") +
      '" target="_blank" rel="noopener">在网上看分类原文</a>';
  }

  // ───────── 公共小块 ─────────
  function itemRow(it) {
    const tags = it.ind.concat(it.trk).slice(0, 3).map((id) => '<span class="bz-tag">' + esc(nameOf(id)) + "</span>").join("");
    const t = it.src === "note"
      ? '<button type="button" class="bz-item-t" data-note="' + esc(it.id) + '">' + esc(it.title) + "</button>"
      : (it.url ? '<a class="bz-item-t" href="' + esc(it.url) + '" target="_blank" rel="noopener">' + esc(it.title) + "</a>"
        : '<span class="bz-item-t">' + esc(it.title) + "</span>");
    return '<div class="bz-item"><span class="bz-src s-' + it.src + '">' + SRC[it.src] + '</span><div class="bz-item-b">' + t +
      (it.text ? "<p>" + esc(it.text) + "</p>" : "") +
      '<div class="bz-item-m">' + (it.who ? "<span>" + esc(it.who) + "</span>" : "") + (it.date ? "<span>" + esc(it.date) + "</span>" : "") +
      (it.todo ? '<span class="bz-warn">还没加工</span>' : "") + tags + "</div></div></div>";
  }

  function repRow(r) {
    return '<button type="button" class="bz-rep" data-rep="' + esc(r.id) + '"><span class="bz-rep-top"><span class="bz-kind k-' + esc(r.kind) + '">' +
      esc(KIND[r.kind] || r.kind) + '</span><span class="bz-rep-time">' + esc(fmtTime(r.created)) + "</span></span>" +
      '<span class="bz-rep-t">' + esc(r.title) + "</span>" + (r.summary ? '<span class="bz-rep-s">' + esc(r.summary) + "</span>" : "") + "</button>";
  }
  function renderRepList(elId, kind, emptyText) {
    const el = $(elId);
    if (!el) return;
    const list = S.reports.filter((r) => r.kind === kind).slice(0, 8);
    el.innerHTML = list.length ? list.map(repRow).join("") : empty(emptyText);
  }

  // ───────── 市场动向 ─────────
  function renderMarket() {
    segSync("days", String(S.days));
    segSync("feedsrc", S.feedSrc);
    const ov = S.ov;
    if (!ov) {
      const t = S.ovErr ? "读不到资料：" + esc(S.ovErr) : "正在把你收进来的内容按行业归类…第一次要几秒。";
      $("bzRising").innerHTML = empty(t); $("bzHot").innerHTML = ""; $("bzFeed").innerHTML = "";
      renderRepList("bzMkReports", "market", "还没有简报。");
      return;
    }
    const win = S.days ? "最近 " + S.days + " 天" : "全部时间";
    $("bzRisingHint").textContent = S.days
      ? "按你收进来的内容算：" + win + "提到它的比例，明显高于平时。条越长，越集中在最近。点一下看相关内容。"
      : "选了「全部」就看不出升温了，换成 7 天或 30 天看看。";
    $("bzRising").innerHTML = (S.days && ov.rising.length) ? ov.rising.slice(0, 12).map((d) =>
      '<button type="button" class="bz-term" data-term="' + esc(d.k) + '" title="' + esc(win + " " + d.r + " 条，一共 " + d.n + " 条，来自 " + d.src + " 个作者或网站") + '">' +
      '<span class="k">' + esc(d.k) + '</span><span class="bar"><i style="width:' + Math.max(6, Math.round((d.r / d.n) * 100)) + '%"></i></span>' +
      '<span class="n">' + d.r + "<small> / " + d.n + "</small></span></button>").join("")
      : (S.days ? empty("还看不出哪个话题在升温：这段时间收进来的内容太少，或者都差不多。") : "");
    $("bzHot").innerHTML = ov.hot.length ? ov.hot.slice(0, 16).map((d) => '<button type="button" class="bz-chip" data-term="' + esc(d.k) + '">' + esc(d.k) + " <b>" + d.r + "</b></button>").join("")
      : empty("这段时间没有收进来新内容。");
    const c = ov.counts;
    $("bzCounts").textContent = "资料：笔记 " + c.note + " 篇（商业相关 " + c.biz_note + " 篇），网站动态 " + c.sniff + " 条，博主新内容 " + c.creator + " 条；归到行业或赛道的 " + c.classified + " 条。";
    renderFeed();
    renderRepList("bzMkReports", "market", "还没有简报。点上面的「生成市场动向简报」，小助会把最近的动向整理成一份。");
  }
  function renderFeed() {
    const f = $("bzFeedFilter");
    f.hidden = !S.feedQ;
    f.innerHTML = S.feedQ ? "只看提到「" + esc(S.feedQ) + "」的 " + '<button type="button" class="bz-link" data-act="clearterm">看全部</button>' : "";
    const el = $("bzFeed");
    if (!S.feed) { el.innerHTML = loading(); return; }
    el.innerHTML = S.feed.length ? S.feed.map(itemRow).join("") : empty("没有找到相关的内容。");
  }
  async function loadFeed() {
    if (S.feedSrc === "all" && !S.feedQ) { S.feed = S.ov ? S.ov.latest : null; renderFeed(); return; }
    S.feed = null; renderFeed();
    try {
      const r = await api("/biz/items?src=" + S.feedSrc + "&q=" + enc(S.feedQ) + "&biz=1&limit=60");
      S.feed = r.items || [];
    } catch (e) { S.feed = []; }
    renderFeed();
  }

  // ───────── 行业 ─────────
  function tile(id) {
    const d = S.byId[id];
    if (!d) return "";
    const h = heatOf(id);
    const tip = d.name + "：" + d.desc + (d.co ? "\n代表企业：" + d.co : "") + "\n你收进来的相关内容：" + (h[0] || 0) + " 条";
    return '<button type="button" class="bz-tile h' + lvl(h[0]) + (S.indSel === id ? " sel" : "") + (matchQ(d) ? "" : " dim") +
      '" data-ind="' + esc(id) + '" title="' + esc(tip) + '"><span class="nm">' + esc(d.name) + "</span>" +
      (h[0] ? '<span class="ct">' + h[0] + "</span>" : "") + "</button>";
  }
  function mapHTML() {
    let html = '<section class="bz-band trk"><header><h4>新兴赛道</h4><span>横跨好几个行业的热门方向</span></header><div class="bz-tiles">' +
      S.tax.tracks.map((t) => tile(t.id)).join("") + "</div></section>";
    S.tax.sectors.forEach((sec) => {
      html += '<section class="bz-band"><header><h4>' + esc(sec.name) + "</h4><span>" + esc(sec.desc) + '</span></header><div class="bz-l1s">' +
        sec.l1.map((n) => {
          const d = S.byId[n], h = heatOf(n);
          const hit = matchQ(d) || d.subs.some((x) => matchQ(S.byId[x]));
          return '<div class="bz-l1' + (hit ? "" : " dim") + '" style="flex-grow:' + d.subs.length + '"><button type="button" class="bz-l1-h' + (S.indSel === n ? " sel" : "") +
            '" data-ind="' + esc(n) + '" title="' + esc(d.name + "：" + d.desc) + '"><span>' + esc(n) + "</span>" + (h[0] ? "<em>" + h[0] + "</em>" : "") + "</button>" +
            '<div class="bz-tiles">' + d.subs.map(tile).join("") + "</div></div>";
        }).join("") + "</div></section>";
    });
    return '<div class="bz-map">' + html + "</div>";
  }
  function lrow(id) {
    const d = S.byId[id], h = heatOf(id);
    return '<tr data-row="' + esc(id) + '"' + (S.indSel === id ? ' class="sel"' : "") + '><td class="nm"><button type="button" class="bz-link strong" data-ind="' + esc(id) + '">' + esc(d.name) + "</button></td>" +
      '<td class="ds">' + esc(d.desc) + (d.co ? '<span class="co">代表企业：' + esc(d.co) + "</span>" : "") + "</td>" +
      '<td class="num">' + (h[0] || "–") + "</td>" +
      '<td class="acts"><a class="bz-link" href="https://www.baidu.com/s?wd=' + enc(searchWords(id)) + '" target="_blank" rel="noopener">网上查看</a>' +
      '<button type="button" class="bz-link" data-run-ind="' + esc(id) + '">联网研究</button></td></tr>';
  }
  function listHTML() {
    const qq = S.indQ.trim();
    const head = '<thead><tr><th>行业</th><th>做什么</th><th class="num">相关内容</th><th></th></tr></thead>';
    let html = "";
    const trs = S.tax.tracks.filter((t) => matchQ(S.byId[t.id]));
    if (trs.length) html += '<section class="bz-lsec"><h4>新兴赛道</h4><table class="bz-ltab">' + head + "<tbody>" + trs.map((t) => lrow(t.id)).join("") + "</tbody></table></section>";
    S.tax.sectors.forEach((sec) => {
      const l1s = sec.l1.map((n) => S.byId[n]).filter((d) => matchQ(d) || d.subs.some((x) => matchQ(S.byId[x])));
      if (!l1s.length) return;
      html += '<section class="bz-lsec"><h4>' + esc(sec.name) + "</h4>" + l1s.map((d) => {
        const subs = d.subs.filter((x) => matchQ(d) || matchQ(S.byId[x]));
        const h = heatOf(d.id);
        const sel = S.byId[S.indSel];
        const open = qq || S.openL1[d.id] || (sel && (sel.l1 === d.id || sel.id === d.id));
        return '<details class="bz-l1row" data-l1="' + esc(d.id) + '"' + (open ? " open" : "") + "><summary>" +
          "<b>" + esc(d.name) + '</b><span class="ds">' + esc(d.desc) + '</span><span class="num">' + d.subs.length + " 个二级行业</span>" +
          '<span class="num">相关 ' + (h[0] || 0) + " 条</span>" +
          '<button type="button" class="bz-link" data-ind="' + esc(d.id) + '">看详情</button></summary>' +
          '<table class="bz-ltab">' + head + "<tbody>" + subs.map(lrow).join("") + "</tbody></table></details>";
      }).join("") + "</section>";
    });
    return '<div class="bz-list">' + (html || empty("没有找到「" + esc(qq) + "」相关的行业。换个说法试试，比如「芯片」「餐饮」「储能」。")) + "</div>";
  }
  function renderIndustry() {
    segSync("indview", S.indView);
    const main = $("bzIndMain");
    if (!S.tax) { main.innerHTML = loading(S.taxErr ? "读不到行业分类表：" + S.taxErr : ""); $("bzIndDetail").innerHTML = ""; return; }
    const sc = $("bzScroll").scrollTop;
    main.innerHTML = S.indView === "list" ? listHTML() : mapHTML();
    $("bzScroll").scrollTop = sc;
    renderIndDetail();
  }
  function relatedTracks(id) {
    return S.tax.tracks.filter((t) => (t.rel || []).includes(id) || (S.byId[id] && S.byId[id].type === "l1" && (t.rel || []).some((r) => r.split("/")[0] === id))).map((t) => t.id);
  }
  function renderIndDetail() {
    const el = $("bzIndDetail");
    const d = S.byId[S.indSel];
    if (!S.tax) return;
    if (!d || !["l1", "l2", "trk"].includes(d.type)) {
      const hotL2 = S.ov ? Object.keys(S.ov.heat).filter((k) => S.byId[k]).sort((a, b) => S.ov.heat[b][0] - S.ov.heat[a][0]).slice(0, 8) : [];
      el.innerHTML = '<div class="bz-dt"><h3>选一个行业</h3><p class="bz-dim">点地图上的任意一格（或列表里的名字），右边会显示这个行业做什么、代表企业、你收进来的相关内容，还能让小助联网研究它、分析它的趋势和机会。</p>' +
        (hotL2.length ? '<h4>你最常看的</h4><div class="bz-chips">' + hotL2.map((k) => '<button type="button" class="bz-chip" data-ind="' + esc(k) + '">' + esc(nameOf(k)) + " <b>" + S.ov.heat[k][0] + "</b></button>").join("") + "</div>" : "") + "</div>";
      return;
    }
    const h = heatOf(d.id);
    const path = d.type === "l2" ? secName(d.sec) + " › " + d.l1 : d.type === "l1" ? secName(d.sec) + "板块" : "新兴赛道";
    let rel = [];
    if (d.type === "l1") rel = d.subs;
    else if (d.type === "trk") rel = d.rel || [];
    else rel = relatedTracks(d.id);
    const relT = d.type === "l1" ? "下面的二级行业" : d.type === "trk" ? "主要涉及的行业" : "相关的新兴赛道";
    const items = S.indItems && S.indItems._id === d.id ? S.indItems : null;
    const reps = S.reports.filter((r) => r.target === d.id || r.scope === d.id).slice(0, 5);
    el.innerHTML = '<div class="bz-dt">' +
      '<p class="bz-dt-path">' + esc(path) + "</p><h3>" + esc(d.name) + "</h3><p>" + esc(d.desc) + "</p>" +
      (d.co ? '<p class="bz-dt-co"><span>代表企业（举例）</span>' + esc(d.co) + "</p>" : "") +
      '<p class="bz-dt-stat"><b>' + (h[0] || 0) + "</b> 条相关内容" + (S.days && h[1] ? "，最近 " + S.days + " 天 " + h[1] + " 条" : "") + "</p>" +
      '<div class="bz-btns">' +
        '<button type="button" class="bz-btn" data-act="ind-research">联网研究这个行业</button>' +
        '<button type="button" class="bz-btn ghost" data-act="ind-trend">分析趋势和机会</button>' +
        '<a class="bz-btn ghost" href="https://www.baidu.com/s?wd=' + enc(searchWords(d.id)) + '" target="_blank" rel="noopener">网上查看</a>' +
      "</div>" +
      '<button type="button" class="bz-link" data-act="ind-sniff">找这个行业的信息源，让小助以后替你盯着</button>' +
      (rel.length ? "<h4>" + relT + '</h4><div class="bz-chips">' + rel.filter((x) => S.byId[x]).map((x) => '<button type="button" class="bz-chip" data-ind="' + esc(x) + '">' + esc(nameOf(x)) + (heatOf(x)[0] ? " <b>" + heatOf(x)[0] + "</b>" : "") + "</button>").join("") + "</div>" : "") +
      (items && items.top_kw && items.top_kw.length ? '<h4>相关内容里提得多的</h4><div class="bz-chips">' + items.top_kw.slice(0, 12).map((k) => '<span class="bz-chip static">' + esc(k) + "</span>").join("") + "</div>" : "") +
      (reps.length ? '<h4>这个行业的报告</h4><div class="bz-reps">' + reps.map(repRow).join("") + "</div>" : "") +
      "<h4>相关内容" + (items ? "（" + items.total + "）" : "") + '</h4><div class="bz-feed compact">' +
      (items ? (items.items.length ? items.items.map(itemRow).join("") : empty("你收进来的内容里还没有和它相关的。可以点「联网研究这个行业」，让小助上网查。")) : loading()) +
      "</div></div>";
  }
  async function selectInd(id) {
    if (!S.byId[id]) return;
    S.indSel = id;
    store.set("indSel", id);
    root.querySelectorAll("#bzIndMain .sel").forEach((e) => e.classList.remove("sel"));
    root.querySelectorAll("#bzIndMain [data-ind], #bzIndMain tr[data-row]").forEach((e) => {
      if ((e.dataset.ind || e.dataset.row) === id) (e.tagName === "TR" ? e : (e.closest("tr") || e)).classList.add("sel");
    });
    renderIndDetail();
    const det = $("bzIndDetail");
    if (det && window.innerWidth < 1100) det.scrollIntoView({ block: "start", behavior: "smooth" });
    try {
      const d = S.byId[id];
      const r = await api("/biz/items?" + (d.type === "trk" ? "trk=" : "ind=") + enc(id) + "&limit=40");
      r._id = id;
      if (S.indSel === id) { S.indItems = r; renderIndDetail(); }
    } catch (e) { /* 读不到就算了 */ }
  }

  // ───────── 商业模式 ─────────
  function renderModel() {
    segSync("mddepth", S.mdDepth);
    if (!S.tax) { $("bzMdTypes").innerHTML = loading(); return; }
    $("bzMdTypes").innerHTML = S.tax.models.map((m) => {
      const h = (S.ov && S.ov.models[m.id]) || [0, 0];
      return '<button type="button" class="bz-chip' + (S.mdl === m.id ? " on" : "") + '" data-mdl="' + esc(m.id) + '" title="' + esc(m.desc) + '">' + esc(m.name) + (h[0] ? " <b>" + h[0] + "</b>" : "") + "</button>";
    }).join("");
    const el = $("bzMdCases");
    if (!S.mdl) el.innerHTML = empty("点上面的一种模式，看看你的笔记里有哪些在讲这种赚钱方式。");
    else if (!S.mdCases) el.innerHTML = loading();
    else {
      const m = S.byId[S.mdl];
      el.innerHTML = '<p class="bz-hint">' + esc(m ? m.name + "：" + m.desc : "") + "</p>" +
        (S.mdCases.length ? S.mdCases.map(itemRow).join("") : empty("你的笔记里还没有讲这种模式的。"));
    }
    renderRepList("bzMdReports", "model", "还没有拆解过。在上面输入一家公司或一门生意试试。");
  }
  async function loadCases(id) {
    S.mdl = S.mdl === id ? "" : id;
    S.mdCases = null;
    renderModel();
    if (!S.mdl) return;
    try {
      const r = await api("/biz/items?mdl=" + enc(S.mdl) + "&src=note&limit=40");
      if (S.mdl === id) { S.mdCases = r.items || []; renderModel(); }
    } catch (e) { S.mdCases = []; renderModel(); }
  }

  // ───────── 趋势与机会 ─────────
  function oppCard(o) {
    const rows = [["适合谁", o.who], ["怎么切入", o.how], ["风险", o.risk], ["依据", o.basis]].filter((x) => x[1]);
    const cost = /低/.test(o.cost) ? "low" : /高/.test(o.cost) ? "high" : /中/.test(o.cost) ? "mid" : "";
    return '<article class="bz-opp st-' + esc(o.status) + '">' +
      '<header><h4>' + esc(o.title) + "</h4>" + (o.cost ? '<span class="bz-cost ' + cost + '">启动成本' + esc(o.cost) + "</span>" : "") + "</header>" +
      (rows.length ? "<dl>" + rows.map((r) => "<dt>" + r[0] + "</dt><dd>" + esc(r[1]) + "</dd>").join("") + "</dl>" : "") +
      '<footer><select class="bz-select sm" data-opp-st="' + esc(o.id) + '" aria-label="这个机会现在的状态">' +
        OPP_ST.map(([k, n]) => '<option value="' + k + '"' + (o.status === k ? " selected" : "") + ">" + n + "</option>").join("") + "</select>" +
        '<button type="button" class="bz-link" data-opp-research="' + esc(o.id) + '">深入研究</button>' +
        (o.report ? '<button type="button" class="bz-link" data-rep="' + esc(o.report) + '">来源报告</button>' : "") +
        '<span class="sp"></span>' + (o.scope ? '<span class="bz-dim">' + esc(o.scope) + "</span>" : (o.by === "you" ? '<span class="bz-dim">我记的</span>' : "")) +
        '<button type="button" class="bz-link danger" data-opp-del="' + esc(o.id) + '">删除</button></footer></article>';
  }
  function renderOpps() {
    const list = S.opps;
    const cnt = { all: list ? list.length : 0 };
    (list || []).forEach((o) => { cnt[o.status] = (cnt[o.status] || 0) + 1; });
    root.querySelectorAll('.bz-seg[data-seg="oppst"] button').forEach((b) => {
      const n = cnt[b.dataset.v] || 0;
      b.innerHTML = esc(b.dataset.v === "all" ? "全部" : (OPP_ST.find((x) => x[0] === b.dataset.v) || [, b.dataset.v])[1]) + (n ? " <small>" + n + "</small>" : "");
    });
    segSync("oppst", S.oppSt);
    const el = $("bzOpps");
    if (!list) { el.innerHTML = loading(); }
    else {
      const show = list.filter((o) => S.oppSt === "all" || o.status === S.oppSt);
      el.innerHTML = show.length ? show.map(oppCard).join("")
        : empty(list.length ? "这一栏还没有。" : "机会看板还是空的。点上面的「分析趋势和机会」，小助会把找到的机会一条条放进来；也可以「记下我的点子」。");
    }
    renderRepList("bzOpReports", "trend", "还没有分析过。");
  }

  // ───────── 研究报告 ─────────
  function renderReports() {
    segSync("rsdepth", S.rsDepth);
    segSync("repkind", S.repKind);
    const tp = $("bzTopics");
    tp.innerHTML = S.topics.length
      ? "常用课题：" + S.topics.map((t) => '<span class="bz-topic"><button type="button" class="bz-link" data-topic="' + esc(t) + '">' + esc(t) + '</button><button type="button" class="bz-x" data-topic-del="' + esc(t) + '" aria-label="删掉常用课题 ' + esc(t) + '">×</button></span>').join("")
      : "试试：" + EG_RESEARCH.map((t) => '<button type="button" class="bz-link" data-topic="' + esc(t) + '">' + esc(t) + "</button>").join("");
    const q = S.repQ.trim().toLowerCase();
    const list = S.reports.filter((r) => (S.repKind === "all" || r.kind === S.repKind) && (!q || (r.title + " " + (r.summary || "")).toLowerCase().includes(q)));
    $("bzReports").innerHTML = list.length ? list.map(repRow).join("")
      : empty(S.reports.length ? "没有符合的报告。" : "报告库还是空的。在上面研究一个课题，或者去「行业」「商业模式」让小助写一份。");
  }

  function renderPane(p) {
    if (p === "market") renderMarket();
    else if (p === "industry") renderIndustry();
    else if (p === "model") renderModel();
    else if (p === "opps") renderOpps();
    else if (p === "reports") renderReports();
  }

  // ───────── 后台任务（写报告）─────────
  const mmss = (s) => { s = Math.max(0, s | 0); return pad((s / 60) | 0) + ":" + pad(s % 60); };
  function renderJob() {
    const j = S.job, el = $("bzJob");
    if (!j || (!j.running && (!j.ended || store.get("jobSeen", 0) >= j.id))) { el.hidden = true; return; }
    el.hidden = false;
    if (j.running) {
      el.className = "bz-job running";
      el.innerHTML = '<div class="bz-job-t"><b>' + esc(j.title) + "</b><span>" + esc(j.stage || "") + "</span></div>" +
        '<ol class="bz-steps">' + (j.steps || []).map((s, i) => {
          const n = i + 1, cls = n < j.step ? "done" : n === j.step ? "on" : "";
          return '<li class="' + cls + (n === 2 && !j.web ? " skip" : "") + '">' + esc(s) + "</li>";
        }).join("") + "</ol>" +
        '<span class="bz-job-time" title="已经用了多久">' + mmss(j.now - j.started) + "</span>" +
        '<button type="button" class="bz-btn ghost sm" data-act="stopjob">停止</button>';
    } else if (j.ok) {
      el.className = "bz-job done";
      el.innerHTML = '<div class="bz-job-t"><b>写好了：' + esc(j.title) + "</b><span>" +
        (j.opps ? "报告里的 " + j.opps + " 个机会已经放进「趋势与机会」的看板" : "用了 " + mmss(j.ended - j.started)) + "</span></div>" +
        '<button type="button" class="bz-btn sm" data-rep="' + esc(j.report) + '">打开报告</button>' +
        '<button type="button" class="bz-link" data-act="jobseen">知道了</button>';
    } else {
      el.className = "bz-job fail";
      el.innerHTML = '<div class="bz-job-t"><b>没写完：' + esc(j.title) + "</b><span>" + esc(j.error || "") + "</span></div>" +
        '<button type="button" class="bz-link" data-act="jobseen">知道了</button>';
    }
  }
  async function pollJob() {
    clearTimeout(S.jobTimer);
    try {
      const j = await api("/biz/job");
      const was = S.job && S.job.running;
      S.job = j;
      renderJob();
      if (was && !j.running) { refreshReports(); refreshOpps(); refreshOverview(); }
      if (j.running) S.jobTimer = setTimeout(pollJob, 2000);
    } catch (e) {
      if (S.job && S.job.running) S.jobTimer = setTimeout(pollJob, 5000);
    }
  }
  async function runJob(kind, opts) {
    if (S.job && S.job.running) { toast("「" + S.job.title + "」还在写，等它写完或者先点停止。"); return; }
    let r;
    try { r = await api("/biz/run", Object.assign({ kind: kind }, opts)); }
    catch (e) { r = { ok: false, error: "连不上后台（" + e.message + "）" }; }
    if (!r || !r.ok) { toast((r && r.error) || "没开始"); return; }
    toast("开始了：" + r.title + "。要几分钟，进度在页面顶上，可以先去做别的。");
    store.set("jobSeen", Math.max(0, (r.job_id || 1) - 1));
    pollJob();
  }

  // ───────── 阅读：报告 / 笔记 ─────────
  let readerBack = 0;
  function openReader(title, meta, body, acts) {
    const rd = $("bzReader"), sc = $("bzScroll");
    if (rd.hidden) readerBack = sc.scrollTop;
    sc.hidden = true;
    rd.hidden = false;
    rd.querySelector(".bz-reader-title").textContent = title;
    rd.querySelector(".bz-reader-acts").innerHTML = acts || "";
    rd.querySelector(".bz-reader-meta").innerHTML = meta || "";
    rd.querySelector(".bz-reader-content").innerHTML = body;
    rd.querySelector(".bz-reader-body").scrollTop = 0;
  }
  function closeReader() {
    const rd = $("bzReader");
    if (rd.hidden) return;
    rd.hidden = true;
    rd.querySelector(".bz-reader-content").innerHTML = "";
    const sc = $("bzScroll");
    sc.hidden = false;
    sc.scrollTop = readerBack;
    S.readerRep = null;
  }
  function chainHTML(c) {
    const col = (cls, label, arr) => '<div class="bz-ch-col ' + cls + '"><div class="bz-ch-h">' + label + "</div>" +
      (arr.length ? arr : [{ name: "报告里没写", desc: "", me: false }]).map((n) =>
        '<div class="bz-ch-node' + (n.me ? " me" : "") + '">' + (n.me ? '<span class="bz-ch-me">在这一环</span>' : "") +
        "<b>" + esc(n.name) + "</b>" + (n.desc ? "<span>" + esc(n.desc) + "</span>" : "") + "</div>").join("") + "</div>";
    const arrow = '<div class="bz-ch-arrow" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 12h15M13 6l6 6-6 6"/></svg></div>';
    return '<figure class="bz-chain"><figcaption>产业链图</figcaption><div class="bz-ch-row">' +
      col("up", "上游", c.up) + arrow + col("mid", "中游", c.mid) + arrow + col("down", "下游", c.down) + "</div>" +
      '<p class="bz-note">箭头是货和服务流动的方向；标着「在这一环」的，就是这次分析的对象所在的位置。</p></figure>';
  }
  function reportBody(text, chain) {
    const t = String(text || "").replace(/^\s*#\s+[^\n]*\n/, "");
    const lines = t.split("\n");
    const a = lines.findIndex((l) => /^\s*#{2,5}\s*.*产业链图/.test(l));
    if (a < 0 || !chain) return '<div class="md bz-md">' + md(t) + "</div>";
    let b = lines.length;
    for (let j = a + 1; j < lines.length; j++) { if (/^\s*#{1,5}\s/.test(lines[j])) { b = j; break; } }
    return '<div class="md bz-md">' + md(lines.slice(0, a).join("\n")) + "</div>" + chainHTML(chain) +
      '<div class="md bz-md">' + md(lines.slice(b).join("\n")) + "</div>";
  }
  async function openReport(id) {
    openReader("读取中…", "", loading(), "");
    let r;
    try { r = await api("/biz/report?id=" + enc(id)); } catch (e) { r = { ok: false, error: e.message }; }
    if (!r.ok) { openReader("打不开", "", empty(esc(r.error || "读取失败")), ""); return; }
    S.readerRep = r;
    const m = r.meta;
    const meta = '<span class="bz-kind k-' + esc(m.kind) + '">' + esc(KIND[m.kind] || m.kind) + "</span><span>" + esc(fmtTime(m.created)) + "</span>" +
      "<span>" + esc(m.engine || "AI") + "写的</span><span>用了你的笔记 " + (m.notes || 0) + " 篇" + (m.web ? "、网页 " + m.web + " 个" : "") + "</span>" +
      (m.opps ? '<button type="button" class="bz-link" data-goto="opps">新增 ' + m.opps + " 个机会，去看板</button>" : "");
    let body = reportBody(r.content, r.chain);
    if (m.note_ids && m.note_ids.length) {
      body += '<section class="bz-used"><h4>用到的笔记</h4><div class="bz-chips">' + m.note_ids.map((n) =>
        '<button type="button" class="bz-chip" data-note="' + esc(n) + '">' + esc(n.replace(/^\d{8}-\d{6}-/, "").replace(/\.md$/, "").slice(0, 24)) + "</button>").join("") + "</div></section>";
    }
    openReader(m.title, meta, body,
      '<button type="button" class="bz-btn ghost sm" data-act="copyrep">复制全文</button>' +
      '<button type="button" class="bz-btn ghost sm" data-act="rerun">重新写一份</button>' +
      '<button type="button" class="bz-btn ghost sm danger" data-act="delrep">删除</button>');
  }
  async function openNote(name) {
    openReader("读取中…", "", loading(), "");
    let r;
    try { r = await api("/video_note?name=" + enc(name)); } catch (e) { r = { ok: false, error: e.message }; }
    if (!r || !r.ok) { openReader("打不开", "", empty(esc((r && r.error) || "读取失败")), ""); return; }
    let t = r.content || "";
    const cut = t.search(/^#{1,3}\s*(?:📝\s*)?完整文字稿\s*$/m);
    if (cut > 0) t = t.slice(0, cut);
    const title = ((t.match(/^#\s+(.+)$/m) || [])[1] || name).replace(/\s#\S+/g, "").trim();
    t = t.replace(/^\s*#\s+[^\n]*\n/, "").replace(/^#{1,6}\s*ChatGPT\s*说[：:]?\s*$/gm, "");
    openReader(title, '<span class="bz-src s-note">笔记</span><span>只显示 AI 分析部分</span>', '<div class="md bz-md">' + md(t) + "</div>",
      '<button type="button" class="bz-btn ghost sm" data-act="opennote" data-name="' + esc(name) + '">到笔记页看完整内容</button>');
  }

  // ───────── 读数据 ─────────
  async function refreshOverview() {
    try {
      S.ov = await api("/biz/overview?days=" + S.days);
      S.ovErr = S.ov && S.ov.ok === false ? (S.ov.error || "出错") : "";
      if (S.ovErr) S.ov = null;
    } catch (e) { S.ovErr = "连不上后台（" + e.message + "）"; }
    if (S.feedSrc === "all" && !S.feedQ) S.feed = S.ov ? S.ov.latest : null;
    renderPane(S.pane);
  }
  async function refreshReports() {
    try { const r = await api("/biz/reports"); S.reports = r.items || []; } catch (e) {}
    renderPane(S.pane);
  }
  async function refreshOpps() {
    try { const r = await api("/biz/opps"); S.opps = r.items || []; } catch (e) { S.opps = S.opps || []; }
    if (S.pane === "opps") renderOpps();
  }
  async function refreshTopics() {
    try { const r = await api("/biz/topics"); S.topics = r.topics || []; } catch (e) {}
    if (S.pane === "reports") renderReports();
  }

  let lastLoad = 0;
  async function load() {
    if (!S.tax) {
      try { S.tax = await api("/biz/taxonomy"); indexTax(); fillScopes(); S.taxErr = ""; }
      catch (e) { S.tax = null; S.taxErr = e.message; }
    }
    const now = Date.now();
    if (now - lastLoad > 15000) {
      lastLoad = now;
      refreshOverview(); refreshReports(); refreshOpps(); refreshTopics();
      if (S.indSel && S.byId[S.indSel] && !(S.indItems && S.indItems._id === S.indSel)) selectInd(S.indSel);
    }
    pollJob();
    renderPane(S.pane);
  }

  function showPane(p) {
    if (!PANES.includes(p)) p = "market";
    S.pane = p;
    store.set("pane", p);
    root.dataset.pane = p;
    root.querySelectorAll(".bz-pane").forEach((el) => { el.hidden = el.dataset.pane !== p; });
    closeReader();
    renderPane(p);
  }
  function goPane(p) {
    if (typeof navOpenGroup === "function") navOpenGroup("biz", p);
    else showPane(p);
  }

  // ───────── 事件 ─────────
  function onSeg(name, v) {
    if (name === "days") { S.days = +v; store.set("days", S.days); S.ov = null; renderMarket(); refreshOverview(); }
    else if (name === "feedsrc") { S.feedSrc = v; loadFeed(); segSync("feedsrc", v); }
    else if (name === "indview") { S.indView = v; store.set("indView", v); renderIndustry(); }
    else if (name === "mddepth") { S.mdDepth = v; segSync(name, v); }
    else if (name === "rsdepth") { S.rsDepth = v; segSync(name, v); }
    else if (name === "oppst") { S.oppSt = v; renderOpps(); }
    else if (name === "repkind") { S.repKind = v; renderReports(); }
  }
  function startModel() {
    const t = $("bzMdTarget").value.trim();
    if (t.length < 2) { toast("先写上要拆解的公司、产品或生意。"); $("bzMdTarget").focus(); return; }
    runJob("model", { target: t, web: $("bzMdWeb").checked, depth: S.mdDepth });
  }
  function startResearch(topic) {
    const t = (topic || $("bzRsTarget").value).trim();
    if (t.length < 2) { toast("先写上要研究的课题。"); $("bzRsTarget").focus(); return; }
    runJob("research", { target: t, web: true, depth: S.rsDepth });
  }

  function bind() {
    root.addEventListener("click", async (e) => {
      const t = e.target;
      let b;
      if ((b = t.closest(".bz-seg button[data-v]"))) { onSeg(b.parentNode.dataset.seg, b.dataset.v); return; }
      if ((b = t.closest("[data-act]"))) {
        const act = b.dataset.act;
        if (act === "back") closeReader();
        else if (act === "clearterm") { S.feedQ = ""; loadFeed(); }
        else if (act === "stopjob") { b.disabled = true; await api("/biz/stop", {}).catch(() => {}); toast("正在停下…"); pollJob(); }
        else if (act === "jobseen") { store.set("jobSeen", S.job ? S.job.id : 0); renderJob(); }
        else if (act === "ind-research") runJob("industry", { target: S.indSel, web: true, depth: "quick" });
        else if (act === "ind-trend") runJob("trend", { scope: S.indSel, web: true });
        else if (act === "ind-sniff") {
          const name = nameOf(S.indSel);
          if (typeof navOpenGroup === "function") navOpenGroup("sniff", "web");
          setTimeout(() => {
            const kw = document.getElementById("sniffKw");
            if (kw) { kw.value = name; kw.focus(); }
            if (typeof window.cxToast === "function") window.cxToast("已经填好「" + name + "」，点「查找」就开始找信息源");
          }, 120);
        }
        else if (act === "oppadd-save") {
          const title = $("bzOaTitle").value.trim();
          if (title.length < 2) { toast("先写一句话说清这个机会。"); $("bzOaTitle").focus(); return; }
          const r = await api("/biz/opp", { action: "add", title: title, who: $("bzOaWho").value.trim(), how: $("bzOaHow").value.trim(), cost: $("bzOaCost").value });
          if (r.ok) { S.opps = r.items; ["bzOaTitle", "bzOaWho", "bzOaHow"].forEach((id) => { $(id).value = ""; }); $("bzOpAdd").hidden = true; S.oppSt = "all"; renderOpps(); toast("记下了，放在「关注」里。"); }
          else toast(r.error || "没记上");
        }
        else if (act === "oppadd-cancel") $("bzOpAdd").hidden = true;
        else if (act === "copyrep" && S.readerRep) {
          const txt = S.readerRep.content || "";
          try { await navigator.clipboard.writeText(txt); toast("已复制全文（Markdown 格式）。"); }
          catch (err) { toast("复制没成功，可以在报告里选中文字手动复制。"); }
        }
        else if (act === "delrep" && S.readerRep) {
          if (!confirm("删掉这份报告？删了找不回来（从它收进看板的机会会留着）。")) return;
          const r = await api("/biz/report_delete", { id: S.readerRep.meta.id });
          if (r.ok) { closeReader(); refreshReports(); toast("删掉了。"); } else toast(r.error || "没删掉");
        }
        else if (act === "rerun" && S.readerRep) {
          const m = S.readerRep.meta;
          runJob(m.kind, { target: m.target, scope: m.scope, days: m.days || 30, web: m.web_on !== false, depth: m.depth || "quick" });
        }
        else if (act === "opennote") {
          const name = b.dataset.name;
          const nb = document.querySelector('.nav-item[data-view="video"][data-video-mode="notes"]');
          if (nb) nb.click();
          setTimeout(() => { if (typeof openVideoNote === "function") openVideoNote(name); }, 80);
        }
        return;
      }
      if ((b = t.closest("[data-rep]"))) {
        if (b.closest("#bzJob")) store.set("jobSeen", S.job ? S.job.id : 0);
        openReport(b.dataset.rep);
        if (b.closest("#bzJob")) renderJob();
        return;
      }
      if ((b = t.closest("[data-note]"))) { openNote(b.dataset.note); return; }
      if ((b = t.closest("[data-goto]"))) { goPane(b.dataset.goto); return; }
      if ((b = t.closest("[data-term]"))) {
        S.feedQ = b.dataset.term;
        loadFeed();
        const card = $("bzFeedCard");
        if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
        return;
      }
      if ((b = t.closest("[data-run-ind]"))) { runJob("industry", { target: b.dataset.runInd, web: true, depth: "quick" }); return; }
      if ((b = t.closest("[data-ind]"))) { if (b.closest("summary")) e.preventDefault(); selectInd(b.dataset.ind); return; }
      if ((b = t.closest("tr[data-row]")) && !t.closest("a,button")) { selectInd(b.dataset.row); return; }
      if ((b = t.closest("[data-mdl]"))) { loadCases(b.dataset.mdl); return; }
      if ((b = t.closest("[data-eg-model]"))) { $("bzMdTarget").value = b.dataset.egModel; $("bzMdTarget").focus(); return; }
      if ((b = t.closest("[data-topic-del]"))) {
        const r = await api("/biz/topics", { topics: S.topics.filter((x) => x !== b.dataset.topicDel) });
        S.topics = r.topics || []; renderReports(); return;
      }
      if ((b = t.closest("[data-topic]"))) { $("bzRsTarget").value = b.dataset.topic; $("bzRsTarget").focus(); return; }
      if ((b = t.closest("[data-opp-research]"))) {
        const o = (S.opps || []).find((x) => x.id === b.dataset.oppResearch);
        if (o) runJob("research", { target: o.title.slice(0, 60), web: true, depth: "quick" });
        return;
      }
      if ((b = t.closest("[data-opp-del]"))) {
        if (!confirm("从看板上删掉这个机会？")) return;
        const r = await api("/biz/opp", { action: "delete", id: b.dataset.oppDel });
        if (r.ok) { S.opps = r.items; renderOpps(); }
        return;
      }
      if (t.closest("#bzMkRun")) { runJob("market", { scope: $("bzMkScope").value, days: S.days || 30, web: $("bzMkWeb").checked }); return; }
      if (t.closest("#bzMdRun")) { startModel(); return; }
      if (t.closest("#bzRsRun")) { startResearch(); return; }
      if (t.closest("#bzRsSave")) {
        const v = $("bzRsTarget").value.trim();
        if (v.length < 2) { toast("先在输入框里写上课题。"); return; }
        const r = await api("/biz/topics", { topics: [v].concat(S.topics) });
        S.topics = r.topics || []; renderReports(); toast("存好了，以后点一下就能填进去。"); return;
      }
      if (t.closest("#bzOpRun")) { runJob("trend", { scope: $("bzOpScope").value, web: $("bzOpWeb").checked }); return; }
      if (t.closest("#bzOpAddBtn")) { $("bzOpAdd").hidden = !$("bzOpAdd").hidden; if (!$("bzOpAdd").hidden) $("bzOaTitle").focus(); return; }
    });
    root.addEventListener("change", async (e) => {
      const t = e.target;
      if (t.matches("[data-opp-st]")) {
        const r = await api("/biz/opp", { action: "update", id: t.dataset.oppSt, status: t.value });
        if (r.ok) { S.opps = r.items; renderOpps(); }
      } else if (t.id === "bzMkScope" || t.id === "bzOpScope") store.set(t.id, t.value);
    });
    let qTimer = null;
    root.addEventListener("input", (e) => {
      const t = e.target;
      if (t.id === "bzIndQ") { S.indQ = t.value; clearTimeout(qTimer); qTimer = setTimeout(renderIndustry, 160); }
      else if (t.id === "bzRepQ") { S.repQ = t.value; renderReports(); }
    });
    root.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || e.isComposing) return;
      if (e.target.id === "bzMdTarget") { e.preventDefault(); startModel(); }
      else if (e.target.id === "bzRsTarget") { e.preventDefault(); startResearch(); }
    });
    root.addEventListener("toggle", (e) => {
      const d = e.target;
      if (d && d.matches && d.matches("details[data-l1]")) S.openL1[d.dataset.l1] = d.open;
    }, true);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && root.classList.contains("active") && !$("bzReader").hidden) closeReader();
    });
  }

  // ───────── 入口 ─────────
  window.cxPaneShow = window.cxPaneShow || {};
  window.cxPaneShow.biz = showPane;
  window.loadBiz = load;
  try {
    buildShell();
    bind();
    root.dataset.pane = S.pane;
    showPane(S.pane);
  } catch (e) { /* 出错也不影响软件其它部分 */ }
  const navBtn = document.querySelector('.nav-item[data-view="biz"]');
  if (navBtn) navBtn.addEventListener("click", () => { load(); });
})();
