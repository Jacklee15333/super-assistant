// ============================================================
// biz.js —「商业」（v155 新增，v157 重新整理成五块；v158 新闻分页、「现在更新」「整理成简报」改成带说明和设置的面板；v159 去掉大按钮图标、改名「生成简报」、自动更新最短 5 分钟可自己填）
//   市场雷达：爬虫抓来的最新新闻——市场上正在发生什么（升温话题、提得最多、一键整理成简报）
//   行业地图：申万 31 个一级行业 + 二级行业 + 新兴赛道，「市场实时 / 我关注的」两种看法，地图和列表两种摆法
//   真实市场（v191）：看钱——统计局、上市公司财报（自动）+ AI 联网核实（电商、交易平台、招投标、报告）；热度 × 真钱四象限
//   研究分析：挑一件事让 AI 写报告——拆解商业模式（含产业链图）、研究课题、找趋势和机会、市场动向简报；报告库
//   机会看板：报告里找到的机会 + 自己记的点子
//   商业定制（v187）：填你的年龄、阅历、技能、兴趣、资金……先按市场雷达的热度配出适合你的方向，再让 AI 写定制方案
//   爬虫管理：用的是哪些爬虫、现在在干什么、每一轮的抓取记录和结果报告、信息源清单
// 顶部五个标签由 renderer.js 的 NAV_GROUPS.biz 画，切换时调 window.cxPaneShow.biz(标签)。
// 复用全局：BACKEND、renderMarkdown、navOpenGroup、openVideoNote（都可能不存在，判断了再用）。
// ============================================================
(function () {
  "use strict";
  const root = document.getElementById("view-biz");
  if (!root) return;

  const PANES = ["radar", "industry", "real", "analysis", "opps", "custom", "crawler"];   // v187：加「商业定制」；v191：行业地图右边加「真实市场」
  const OLD_PANE = { market: "radar", model: "analysis", reports: "analysis" };
  const KIND = { market: "市场动向简报", industry: "行业研究", model: "商业模式", trend: "趋势与机会", research: "课题研究", custom: "商业定制", real: "真实市场核实" };
  const SRC = { note: "笔记", sniff: "网站动态", creator: "博主新内容", radar: "市场新闻" };
  const GRP = { news: "财经媒体", corp: "大公司官网", firm: "企业官网", govmedia: "官方媒体", corpkw: "大公司动态", media: "行业媒体", indkw: "行业热词", policy: "政策数据", global: "海外", mine: "我加的" };
  const OPP_ST = [["new", "新发现"], ["watch", "关注"], ["testing", "验证中"], ["doing", "在做"], ["dropped", "放弃"]];
  const TRIG = { auto: "自动", manual: "手动", single: "单个信息源" };
  const TASKS = [
    ["model", "拆解商业模式", "一家公司、一个产品或一门生意"],
    ["research", "研究一个课题", "任何想弄明白的方向"],
    ["trend", "找趋势和机会", "选一个行业或板块"],
    ["market", "市场动向简报", "把抓到的新闻整理成一份"],
  ];
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
  // v164：新闻的发布时间（不是今年的带上年份）
  const fmtPub = (ts) => { const d = new Date(ts * 1000); return (d.getFullYear() !== new Date().getFullYear() ? d.getFullYear() + "年" : "") + fmtTime(ts); };
  const hhmm = (ts) => { const d = new Date(ts * 1000); return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()); };
  const loading = (t) => '<p class="bz-empty">' + esc(t || "正在读取…") + "</p>";
  const empty = (t) => '<p class="bz-empty">' + t + "</p>";
  const ago = (ts) => {
    if (!ts) return "";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "刚刚";
    if (s < 3600) return Math.floor(s / 60) + " 分钟前";
    if (s < 86400) return Math.floor(s / 3600) + " 小时前";
    if (s < 86400 * 7) return Math.floor(s / 86400) + " 天前";
    const d = new Date(ts * 1000);
    return (d.getMonth() + 1) + "月" + d.getDate() + "日";
  };
  const until = (ts) => {
    const s = ts - Date.now() / 1000;
    if (s <= 60) return "马上";
    if (s < 3600) return Math.ceil(s / 60) + " 分钟后";
    return (s / 3600).toFixed(1).replace(/\.0$/, "") + " 小时后";
  };
  const dur = (s) => { s = Math.max(0, Math.round(s || 0)); return s < 60 ? s + " 秒" : Math.floor(s / 60) + " 分 " + (s % 60) + " 秒"; };
  const viaText = (via) => Object.entries(via || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + " " + v + " 个").join("，");

  const pane0 = store.get("pane", "radar");
  const S = {
    pane: PANES.includes(pane0) ? pane0 : (OLD_PANE[pane0] || "radar"),
    tax: null, byId: {}, taxErr: "",
    ovm: null, ovmErr: "", ov: null, ovErr: "", mdays: store.get("mdays", 3),
    rfeed: null, rgrp: "all", rq: "", rlimit: 80, rpage: 1, rsize: store.get("rsize", 20), rtotal: 0, rsince: 0, rseq: 0,
    rview: store.get("rview", "radar"), rind: "", radSel: "", radNews: {},   // v165：雷达扫描 / 新闻列表
    artSel: "", art: {}, artTr: {}, artMedia: {}, artLang: "zh", artItems: {}, trTitle: {}, kbSent: {},
    read: new Set(store.get("read", [])),       // v164：点开看过的新闻（标题变淡、不再标「新」）
    plan: null, updOpen: false, updDone: "", updRes: null, briefOpen: false, bf: null, briefInfo: null,
    lens: store.get("lens", "market") === "mine" ? "mine" : "market", days: 30,
    indView: store.get("indView", "map"), indSel: "", indQ: "", indItems: null, openL1: {},
    task: store.get("task", "model"), depth: "quick",
    mdl: "", mdCases: null, opps: null, oppSt: "all", reports: [], repKind: "all", repQ: "", topics: [],
    job: null, jobTimer: null, readerRep: null, readerRun: "",
    radar: null, radarTimer: null, radarSrc: null, engines: null, runs: null,
    rdKind: "site", rdSid: "", rdItems: null, rdOpen: {},
    cu: { loaded: false, ready: false, pv: null, err: "", seq: 0, timer: null, dirty: false, updated: 0, at: 0, news: {}, peek: "",
          pick: null, optLoading: false, open: store.get("cuOpen", null) || { exp: true }, b: { ind: "", role: "", years: "", lead: "" },   // v188：选项面板
          saved: [], savedOpen: false, undoId: "", undoT: null,          // v189：存过的、撤销清空
          web: store.get("cuWeb", true) !== false, depth: store.get("cuDepth", "quick") === "deep" ? "deep" : "quick" },   // v187：商业定制
    rm: { data: null, err: "", at: 0, timer: null, sel: store.get("rmSel", ""), item: null, q: "",                 // v191：真实市场
          updWait: false, showReport: false, tab: ["map", "data", "check", "trade"].includes(store.get("rmTab", "map")) ? store.get("rmTab", "map") : "map",                                   // v195：三个标签                                                                    // v193：更新汇报
          pick: "", batchOpen: false, bscope: "all", btodo: true, allChecks: false, ttimer: null,                     // v192：下拉框、全部核实
          metric: ["size", "growth", "margin", "quad"].includes(store.get("rmMetric", "size")) ? store.get("rmMetric", "size") : "size",
          view: store.get("rmView", "map") === "list" ? "list" : "map", depth: store.get("rmDepth", "quick") === "deep" ? "deep" : "quick" },
  };

  // ───────── 分类表 ─────────
  function indexTax() {
    const t = S.tax, by = {};
    t.sectors.forEach((s) => { by["sec:" + s.key] = { type: "sec", id: "sec:" + s.key, name: s.name, desc: s.desc, l1: s.l1 }; });
    t.industries.forEach((i) => {
      by[i.id] = { type: "l1", id: i.id, name: i.name, desc: i.desc, sec: i.sec, subs: i.subs.map((x) => x.id) };
      i.subs.forEach((x) => {
        by[x.id] = { type: "l2", id: x.id, name: x.name, desc: x.desc, kw: x.kw, co: x.co, l1: i.id, sec: i.sec, l3: (x.l3 || []).map((y) => y.id) };
        (x.l3 || []).forEach((y) => { by[y.id] = { type: "l3", id: y.id, name: y.name, desc: y.desc, kw: y.kw, l2: x.id, l1: i.id, sec: i.sec }; });   // v183：三级细分
      });
    });
    t.tracks.forEach((x) => { by[x.id] = { type: "trk", id: x.id, name: x.name, desc: x.desc, kw: x.kw, rel: x.rel }; });
    t.models.forEach((x) => { by[x.id] = { type: "mdl", id: x.id, name: x.name, desc: x.desc }; });
    S.byId = by;
  }
  const nameOf = (id) => (S.byId[id] ? S.byId[id].name : String(id || "").split("/").pop());
  const secName = (key) => (S.byId["sec:" + key] || {}).name || "";
  const lvl = (n) => (!n ? 0 : n <= 2 ? 1 : n <= 5 ? 2 : n <= 12 ? 3 : n <= 30 ? 4 : 5);
  const curOv = () => (S.lens === "market" ? S.ovm : S.ov);
  const heatIn = (o, id) => {
    const d = S.byId[id];
    if (!o) return [0, 0];
    return (d && d.type === "l1" ? o.l1[id] : o.heat[id]) || [0, 0];
  };
  const heatOf = (id) => heatIn(curOv(), id);
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
  const LENS_SEG = () => seg("lens", [["market", "市场实时"], ["mine", "我关注的"]]).replace('class="bz-seg"', 'class="bz-seg lens"');
  const MDAYS_SEG = () => seg("mdays", [["-1", "这一轮"], ["0.0417", "1 小时"], ["1", "24 小时"], ["2", "2 天"], ["3", "3 天"], ["7", "7 天"], ["30", "1 个月"], ["365", "1 年"], ["0", "累计"]]);   // v178

  function buildShell() {
    root.innerHTML =
      '<header class="topbar"><span>商业</span></header>' +
      '<div class="bz-job" id="bzJob" hidden></div>' +
      '<div class="bz-scroll" id="bzScroll">' +

      // ===== 市场雷达 =====
      '<div class="bz-pane" data-pane="radar">' +
        '<section class="bz-guide" id="bzGuide"><div class="bz-guide-h"><h3>「商业」这一栏怎么用</h3>' +
          '<button type="button" class="bz-link" data-act="guide-hide">知道了，收起来</button></div><ol>' +
          "<li><b>市场雷达</b>：爬虫抓来的最新新闻，看市场上正在发生什么。</li>" +
          "<li><b>行业地图</b>：把新闻和你收进来的内容按行业摆开，看哪里热、哪些你还没关注。</li>" +
          "<li><b>真实市场</b>：看钱——统计局和上市公司财报里每个行业卖了多少、赚不赚钱，具体方向让 AI 核实规模、客户和购买力。</li>" +
          "<li><b>研究分析</b>：挑一件事，让 AI 深入研究、写成报告（商业模式、课题、趋势机会、简报）。</li>" +
          "<li><b>机会看板</b>：报告里找到的机会自动放这里，也能记自己的点子。</li>" +
          "<li><b>商业定制</b>：写下你的年龄、阅历、技能、兴趣和资金，小助按市场数据帮你挑行业和赚钱的做法。</li>" +
          "<li><b>爬虫管理</b>：爬虫盯哪些网站、用什么方法抓、每一轮抓到了什么。</li></ol></section>" +
        '<div class="bz-bar">' + MDAYS_SEG() +
          '<input type="search" class="bz-input" id="bzRq" placeholder="在新闻里搜：比如 比亚迪、降价、融资" aria-label="在新闻里搜">' +
          '<span class="sp"></span>' +
          '<button type="button" class="bz-big primary" id="bzUpdBtn" aria-haspopup="dialog"><span class="bz-big-t"><b id="bzUpdBtnT">现在更新</b><small id="bzUpdBtnS">让爬虫马上去抓最新新闻</small></span></button>' +
          '<button type="button" class="bz-big" id="bzBriefRun" aria-haspopup="dialog"><span class="bz-big-t"><b>生成简报</b><small id="bzBriefBtnS">AI 写一份文档，存在你电脑上</small></span></button></div>' +
        '<div class="bz-strip" id="bzStripR"></div>' +
        '<div class="bz-cols" id="bzCols">' +
          '<div class="bz-main"><section class="bz-card" id="bzFeedCard"><div class="bz-card-h">' +
            '<div class="bz-vtabs" role="tablist" aria-label="怎么看">' +
              '<button type="button" role="tab" data-rview="radar">雷达扫描</button><button type="button" role="tab" data-rview="list">新闻列表</button>' +
              '<button type="button" role="tab" data-rview="briefs">最近的简报</button></div>' +
            '<div class="bz-rad-bar" id="bzRadBar" aria-live="polite"></div>' +
            '<span class="bz-rgrp" id="bzRgrpWrap">' + seg("rgrp", [["all", "全部"], ["news", "财经媒体"], ["corp,corpkw,firm", "大公司"], ["media,indkw", "行业媒体"], ["policy", "政策数据"], ["govmedia", "各国官方"], ["global", "海外"], ["mine", "我加的"]]) + "</span></div>" +
            '<div class="bz-radar" id="bzRadar"></div>' +
            '<div class="bz-briefsv" id="bzBriefsView" hidden><div class="bz-briefsv-h"><p class="bz-hint">用「生成简报」把一段时间的新闻整理成文档。点一份打开看。</p>' +
              '<button type="button" class="bz-btn sm" data-act="brief-open">生成简报</button></div><div class="bz-reps" id="bzBriefsAll"></div></div>' +
            '<div id="bzListWrap"><p class="bz-filter" id="bzFeedFilter" hidden></p><div class="bz-feed" id="bzFeed"></div>' +
            '<nav class="bz-pager" id="bzPager" aria-label="翻页" hidden></nav></div></section></div>' +
          '<aside class="bz-side">' +
            '<section class="bz-card bz-scan-card" id="bzScanCard"><div class="bz-card-h"><h3>扫描结果</h3></div><p class="bz-hint" id="bzScanHint"></p><div id="bzScanList"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>正在升温</h3></div><p class="bz-hint" id="bzRisingHint"></p><div class="bz-terms" id="bzRising"></div></section>' +
            '<section class="bz-card" id="bzHotCard"><div class="bz-card-h"><h3>提得最多</h3></div><div class="bz-chips" id="bzHot"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>最近的简报</h3></div><div class="bz-reps" id="bzBriefs"></div></section>' +
            '<p class="bz-note" id="bzCounts"></p>' +
          "</aside>" +
          '<section class="bz-readp" id="bzReadP" aria-label="新闻内容" hidden></section>' +
        "</div>" +
      "</div>" +

      // ===== 行业地图 =====
      '<div class="bz-pane" data-pane="industry">' +
        '<div class="bz-bar">' + LENS_SEG() + seg("indview", [["map", "地图"], ["list", "列表"]]) +
          '<input type="search" class="bz-input" id="bzIndQ" placeholder="找行业：芯片、餐饮、储能、宠物…" aria-label="找行业">' + MDAYS_SEG() +
          '<span class="sp"></span><span class="bz-legend" aria-hidden="true"><i class="h1"></i><i class="h2"></i><i class="h3"></i><i class="h4"></i><i class="h5"></i></span>' +
          '<span class="bz-note" id="bzLegendTxt"></span></div>' +
        '<div class="bz-strip" id="bzStripI"></div>' +
        '<p class="bz-source" id="bzIndSource"></p>' +
        '<div class="bz-ind"><div class="bz-mlive" id="bzMapLive"></div><div class="bz-ind-main" id="bzIndMain"></div><aside class="bz-ind-detail" id="bzIndDetail"></aside></div>' +
      "</div>" +

      // ===== v191：真实市场 =====
      rmPaneHTML() +

      // ===== 研究分析 =====
      '<div class="bz-pane" data-pane="analysis">' +
        '<section class="bz-hero"><h2>研究分析</h2>' +
          "<p>挑一件事，让 AI 帮你写成报告。小助会先从你收进来的内容和爬虫抓到的新闻里挑相关的，勾了「联网」还会自己上网搜、读网页，再交给 AI 写。" +
          "写好的报告都在下面的报告库；报告里找到的机会会放进「机会看板」。</p>" +
          '<div class="bz-tasks" role="group" aria-label="要做什么">' + TASKS.map(([k, t, d]) =>
            '<button type="button" class="bz-task" data-task="' + k + '" aria-pressed="false"><b>' + t + "</b><span>" + d + "</span></button>").join("") + "</div>" +
          '<div class="bz-taskform" id="bzTaskForm"></div></section>' +
        '<section class="bz-card"><div class="bz-card-h"><h3>报告库</h3>' +
          seg("repkind", [["all", "全部"], ["model", "商业模式"], ["research", "课题研究"], ["industry", "行业研究"], ["trend", "趋势与机会"], ["market", "市场动向简报"], ["custom", "商业定制"], ["real", "真实市场"]]) +
          '<input type="search" class="bz-input" id="bzRepQ" placeholder="搜报告" aria-label="搜报告"></div>' +
          '<div class="bz-reps wide" id="bzReports"></div></section>' +
        '<details class="bz-card bz-cases"><summary>你笔记里的商业模式案例（按赚钱方式分）</summary>' +
          '<div class="bz-chips" id="bzMdTypes"></div><div class="bz-feed" id="bzMdCases"></div></details>' +
      "</div>" +

      // ===== 机会看板 =====
      '<div class="bz-pane" data-pane="opps">' +
        '<div class="bz-bar"><p class="bz-hint bz-flat">在「研究分析」里做「找趋势和机会」「研究课题」「市场动向简报」，报告里写到的机会会自动放到这里。你也可以自己记点子，再标上进展。</p>' +
          '<span class="sp"></span><button type="button" class="bz-btn ghost" data-goto-task="trend">去找新机会</button>' +
          '<button type="button" class="bz-btn ghost" id="bzOpAddBtn">记下我的点子</button></div>' +
        '<section class="bz-card bz-opadd" id="bzOpAdd" hidden><div class="bz-card-h"><h3>记下一个点子</h3></div>' +
          '<div class="bz-grid2"><label>这个机会是什么<input class="bz-input" id="bzOaTitle" maxlength="140" placeholder="一句话说清做什么"></label>' +
          '<label>适合谁<input class="bz-input" id="bzOaWho" maxlength="120" placeholder="比如：有本地资源的宝妈"></label>' +
          '<label>怎么切入<input class="bz-input" id="bzOaHow" maxlength="200" placeholder="第一步打算怎么做"></label>' +
          '<label>启动成本<select class="bz-select" id="bzOaCost"><option value="">不确定</option><option>低</option><option>中</option><option>高</option></select></label></div>' +
          '<div class="bz-btns"><button type="button" class="bz-btn" data-act="oppadd-save">保存</button><button type="button" class="bz-btn ghost" data-act="oppadd-cancel">取消</button></div></section>' +
        '<div class="bz-opbar">' + seg("oppst", [["all", "全部"]].concat(OPP_ST)) + "</div>" +
        '<div class="bz-opps" id="bzOpps"></div>' +
      "</div>" +

      // ===== v187：商业定制 =====
      cuPaneHTML() +

      // ===== 爬虫管理 =====
      '<div class="bz-pane" data-pane="crawler">' +
        '<section class="bz-hero"><h2>爬虫管理</h2>' +
          "<p>爬虫按下面的信息源清单，定时去网上抓最新的新闻、大公司发布的文章和行业媒体的报道。抓到的就是「市场雷达」和「行业地图 · 市场实时」的依据。" +
          "这里能看到它用的是什么方法、现在在干什么、每一轮抓到了什么。</p>" +
          '<div class="bz-rd-status"><div class="bz-rd-line" id="bzRdLine"></div><div class="bz-rd-prog" id="bzRdProg" hidden></div>' +
          '<div class="bz-rd-ctl" id="bzRdCtl"></div><p class="bz-note" id="bzRdNote"></p></div></section>' +
        '<section class="bz-card"><div class="bz-card-h"><h3>用的是哪些爬虫</h3></div><p class="bz-hint" id="bzEnginesOrder"></p><div class="bz-engines" id="bzEngines"></div></section>' +
        '<div class="bz-cols">' +
          '<div class="bz-main">' +
            '<section class="bz-card"><div class="bz-card-h"><h3>抓取记录</h3><span class="bz-dim">点一行，看这一轮的结果报告</span></div><div class="bz-tablewrap" id="bzRuns"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>信息源清单</h3><span class="bz-dim" id="bzRdCount"></span></div><div id="bzRdMine"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>推荐的信息源</h3></div>' +
              '<p class="bz-hint">按类别挑。「大公司官网」抓的是公司自己发的新闻稿；「大公司动态」「行业热词」是拿名字去新闻搜索里找各家媒体的最新报道。</p>' +
              '<div id="bzRdCatalog"></div></section>' +
          "</div>" +
          '<aside class="bz-side">' +
            '<section class="bz-card"><div class="bz-card-h"><h3>运行日志</h3></div><div class="bz-log" id="bzRdLog"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>自己加一个</h3>' + seg("rdkind", [["site", "网站"], ["kw", "关键词"]]) + "</div>" +
              '<div class="bz-rd-form"><input class="bz-input" id="bzRdTarget" maxlength="200" aria-label="网址或关键词">' +
              '<input class="bz-input" id="bzRdName" maxlength="30" placeholder="名字（可以不填）" aria-label="名字">' +
              '<select class="bz-select" id="bzRdHint" aria-label="属于哪个行业"><option value="">属于哪个行业（可以不选）</option></select>' +
              '<button type="button" class="bz-btn" id="bzRdAdd">加进清单</button></div>' +
              '<p class="bz-note" id="bzRdFormNote"></p></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3 id="bzRdLatestT">刚抓到的</h3></div><div class="bz-feed compact" id="bzRdLatest"></div></section>' +
          "</aside>" +
        "</div>" +
      "</div>" +

      "</div>" +   // bz-scroll

      '<div class="bz-reader" id="bzReader" hidden>' +
        '<div class="bz-reader-bar"><button type="button" class="bz-back" data-act="back" title="回到刚才的位置（也可以按 Esc）">← 返回</button>' +
          '<span class="bz-reader-title"></span><span class="bz-reader-acts"></span></div>' +
        '<div class="bz-reader-body"><div class="bz-reader-inner"><div class="bz-reader-meta"></div><div class="bz-reader-content"></div></div></div>' +
      "</div>" +
      '<div class="bz-modal" id="bzUpd" hidden><div class="bz-dlg" role="dialog" aria-modal="true" aria-labelledby="bzUpdT"><div id="bzUpdBody"></div></div></div>' +
      '<div class="bz-modal" id="bzBrief" hidden><div class="bz-dlg" role="dialog" aria-modal="true" aria-labelledby="bzBriefT"><div id="bzBriefBody"></div></div></div>' +
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

  function scopeOptions(keep) {
    if (!S.tax) return '<option value="">全部行业</option>';
    const o = (v, t) => '<option value="' + esc(v) + '"' + (v === keep ? " selected" : "") + ">" + esc(t) + "</option>";
    return o("", "全部行业") + '<optgroup label="新兴赛道">' + S.tax.tracks.map((t) => o(t.id, t.name)).join("") + "</optgroup>" +
      S.tax.sectors.map((s) => '<optgroup label="' + esc(s.name) + '">' + o("sec:" + s.key, "整个" + s.name + "板块") +
        s.l1.map((n) => o(n, n)).join("") + "</optgroup>").join("");
  }
  function fillTax() {
    if (!S.tax) return;
    $("bzRdHint").innerHTML = '<option value="">属于哪个行业（可以不选）</option><optgroup label="新兴赛道">' +
      S.tax.tracks.map((t) => '<option value="' + esc(t.id) + '">' + esc(t.name) + "</option>").join("") + "</optgroup>" +
      S.tax.industries.map((i) => '<optgroup label="' + esc(i.name) + '">' + i.subs.map((x) => '<option value="' + esc(x.id) + '">' + esc(x.name) + "</option>").join("") + "</optgroup>").join("");
    $("bzIndSource").innerHTML = "分类参考：" + esc(S.tax.source) + "。共 " + S.tax.counts.l1 + " 个一级行业、" + S.tax.counts.l2 +
      " 个二级行业、" + S.tax.counts.tracks + " 个新兴赛道。" + '<a href="https://www.baidu.com/s?wd=' + enc("申万行业分类 2021版 一级 二级") +
      '" target="_blank" rel="noopener">在网上看分类原文</a>';
  }

  // ───────── 公共小块 ─────────
  function itemRow(it) {
    const tags = it.ind.concat(it.trk).slice(0, 3).map((id) => '<span class="bz-tag">' + esc(nameOf(id)) + "</span>").join("");
    const sel = S.artSel === it.id;
    if (it.url && it.src !== "note") S.artItems[it.id] = it;
    const zh = S.trTitle[it.title];
    // v160/v161：点标题在右边的阅读栏里看正文（不跳网页）；外文标题显示中文译名，原文写在下面
    const t = it.src === "note"
      ? '<button type="button" class="bz-item-t" data-note="' + esc(it.id) + '">' + esc(it.title) + "</button>"
      : (it.url ? '<button type="button" class="bz-item-t bz-art-t" data-art="' + esc(it.id) + '"' + (sel ? ' aria-current="true"' : "") + ' title="点一下在右边看内容">' +
          esc(zh || it.title) + "</button>" + (zh ? '<span class="bz-orig">' + esc(it.title) + "</span>" : "")
        : '<span class="bz-item-t">' + esc(it.title) + "</span>");
    const isR = it.src === "radar";
    // v164：写出发布时间；不知道发布时间的，写什么时候抓到的
    const when = isR ? (it.approx ? "发布时间不详" + (it.seen ? " · " + ago(it.seen) + "抓到" : "") : fmtPub(it.ts) + " 发布 · " + ago(it.ts)) : it.date;
    const read = it.url && S.read.has(it.id);
    const fresh = isR && !read && it.seen && S.newCut && it.seen >= S.newCut;
    return '<div class="bz-item' + (fresh ? " fresh" : "") + (sel ? " sel" : "") + (read ? " read" : "") + (it.url && it.src !== "note" ? " clickable" : "") + '" data-row="' + esc(it.id) + '"><span class="bz-src s-' + it.src + '">' + (isR ? (GRP[it.grp] || SRC.radar) : SRC[it.src]) + "</span>" +
      '<div class="bz-item-b">' + (fresh ? '<span class="bz-new" title="上一轮更新时新抓到的">新</span>' : "") + t +
      (it.text && !zh ? "<p>" + esc(it.text) + "</p>" : "") +
      '<div class="bz-item-m">' + (it.who ? "<span>" + esc(it.who) + (isR && it.from && it.from !== it.who ? "·" + esc(it.from) : "") + "</span>" : "") + (when ? "<span>" + esc(when) + "</span>" : "") +
      (it.todo ? '<span class="bz-warn">还没加工</span>' : "") + tags + "</div></div></div>";
  }


  // ───────── v165：雷达扫描——按行业把新闻分好类，点哪个看哪个 ─────────
  function applyRview() {
    const v = S.rview === "list" || S.rview === "briefs" ? S.rview : "radar";
    root.querySelectorAll("[data-rview]").forEach((b) => { b.setAttribute("aria-selected", String(b.dataset.rview === v)); b.classList.toggle("on", b.dataset.rview === v); });
    const rd = $("bzRadar"), lw = $("bzListWrap"), gw = $("bzRgrpWrap");
    if (rd) rd.hidden = v !== "radar";
    if (lw) lw.hidden = v !== "list";
    const bv = $("bzBriefsView");
    if (bv) { bv.hidden = v !== "briefs"; if (v === "briefs") renderRepList("bzBriefsAll", "market", "还没有简报。点上面的「生成简报」。", 60); }
    renderRadBar();
    if (gw) gw.hidden = v !== "list";
    const cols = $("bzCols");
    if (cols) cols.classList.toggle("wide", v !== "list");
    const scard = $("bzScanCard");
    if (scard) scard.hidden = true;                // v174：扫描结果放到雷达右边了     // v168：雷达模式下右边栏挪到下面，雷达能放大
    if (v === "radar") renderRadarScan();
  }
  function setRview(v, ind) {
    S.rview = v;
    store.set("rview", v);
    if (v === "list") {
      const changed = (ind || "") !== S.rind;
      S.rind = ind || "";
      if (changed || !S.rfeed) loadRadarFeed();
    }
    applyRview();
    const card = $("bzFeedCard");
    if (card && ind) card.scrollIntoView({ block: "start" });
  }
  // v178：时间范围：-1＝这一轮扫描，0＝累计（从开始到现在），其它＝最近几天
  const MWIN = { "-1": "这一轮扫描", "0.0417": "最近 1 小时", "1": "最近 24 小时", "2": "最近 2 天", "3": "最近 3 天", "7": "最近 7 天", "30": "最近 1 个月", "365": "最近 1 年" };
  function winText() {
    if (S.mdays === 0) {
      const t = S.ovm && S.ovm.since ? new Date(S.ovm.since * 1000) : null;
      return "累计" + (t ? "（" + t.getFullYear() + "年" + (t.getMonth() + 1) + "月" + t.getDate() + "日起）" : "（从开始到现在）");
    }
    return MWIN[String(S.mdays)] || "最近 " + S.mdays + " 天";
  }
  const show24 = () => S.mdays > 1 || S.mdays === 0;
  function dataStamp() {                                       // v182：雷达和行业地图用的是同一份统计，写上统计时间
    const t = S.ovm && S.ovm.now ? new Date(S.ovm.now * 1000) : null;
    return t ? "数据 " + [t.getHours(), t.getMinutes(), t.getSeconds()].map((x) => String(x).padStart(2, "0")).join(":") + " 更新（市场雷达和行业地图是同一份数据）" : "";
  }          // 要不要另外写「最近 24 小时 N 条」
  // v176：雷达上的字用深一点（深色模式下浅一点）的同色，和浅色底拉开对比
  function ink(hex, k) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return hex;
    const n = parseInt(m[1], 16), dark = document.body.classList.contains("dark");
    const tgt = dark ? 255 : 18, f = dark ? (k || 0.55) : (k || 0.42);
    const mix = (c) => Math.round(c + (tgt - c) * f);
    return "rgb(" + mix((n >> 16) & 255) + "," + mix((n >> 8) & 255) + "," + mix(n & 255) + ")";
  }
  const RAD_SEC = { "科技": "#3b6fd1", "消费": "#c4613a", "医药": "#2f8f5b", "制造": "#7a5cc2", "周期资源": "#a0711a", "金融地产": "#c23b6a", "公用交运": "#2a8a9a" };
  // v168：新兴赛道按方向分成 5 块；v169：去掉「赛道·」
  const TRK_GROUPS = [
    ["智能科技", "#0f8fb3", ["t:ai", "t:compute", "t:chip", "t:data", "t:robot", "t:future"]],
    ["新能源与出行", "#3a9a3a", ["t:ev", "t:energy", "t:autodrive", "t:lowalt", "t:space"]],
    ["新消费", "#d9822b", ["t:newcons", "t:discount", "t:tea", "t:pet"]],
    ["内容与电商", "#b5508f", ["t:livecom", "t:crossborder", "t:creator", "t:edu", "t:local"]],
    ["健康养老", "#5a8f7b", ["t:biotech", "t:silver"]],
  ];
  // v169：细分到底——大块是板块，里面每个一级行业（或赛道）一小格，圆点是二级行业
  function radarModel() {
    const ov = S.ovm, t = S.tax;
    if (!ov || !t) return null;
    const d = ov.span != null ? ov.span : S.mdays, l1 = ov.l1 || {}, hh = ov.heat || {};
    const hv = (id) => hh[id] || l1[id] || [0, 0];
    const isHot = (n, h) => d > 1 && h >= 3 && h >= (n * 2) / d;          // 最近 24 小时的量明显高于这段时间的日均
    const items = [];
    const mk = (id, name, parent, sec, color) => {
      const it = { id, name, parent, sec, color, n: hv(id)[0], t: hv(id)[1] };
      it.hot = isHot(it.n, it.t);
      items.push(it);
      return it;
    };
    const wedges = t.sectors.map((sec) => {
      const color = RAD_SEC[sec.name] || "#888";
      return { name: sec.name, key: sec.key, color, cells: sec.l1.map((l) => ({ id: l, name: nameOf(l), items: ((S.byId[l] || {}).subs || []).map((x) => mk(x, nameOf(x), nameOf(l), sec.name, color)) })) };
    });
    const known = new Set(t.tracks.map((x) => x.id)), used = new Set();
    const trkW = TRK_GROUPS.map(([name, color, ids]) => ({ name, color, trk: true,
      cells: ids.filter((id) => known.has(id)).map((id) => { used.add(id); return { id, name: nameOf(id), items: [mk(id, nameOf(id), name, name, color)] }; }) }));
    const rest = t.tracks.filter((x) => !used.has(x.id));
    if (rest.length) trkW.push({ name: "其他新方向", color: "#9a8a6a", trk: true, cells: rest.map((x) => ({ id: x.id, name: x.name, items: [mk(x.id, x.name, "其他新方向", "其他新方向", "#9a8a6a")] })) });
    const all = wedges.concat(trkW.filter((w) => w.cells.length));
    let max = 1;
    items.forEach((it) => { max = Math.max(max, it.n); });
    all.forEach((w) => {
      w.n = 0;
      w.cells.forEach((c) => {
        const own = !w.trk && l1[c.id];                                   // v177：行业用它自己的条数（一条新闻只算一次）
        c.n = own ? own[0] : c.items.reduce((a, x) => a + x.n, 0);
        c.t = own ? own[1] : c.items.reduce((a, x) => a + x.t, 0);
        c.hot = isHot(c.n, c.t);
        c.single = c.items.length === 1 && c.items[0].id === c.id;          // 赛道：这一圈就是这一个点
        w.n += c.n;
      });
    });
    return { wedges: all, items, max };
  }

  // ───────── v177：饼按真实像素画——字一直是同样大小、不跟着饼缩小；整张饼按窗口剩下的高度放得下；字和圆点互不压 ─────────
  const RF = 12.5, SF = 16, SNF = 12.5, POP = 10, PANEL_MIN = 290, PANEL_MAX = 440, COLGAP = 26;
  let twCtx = null, twFam = "";
  function tw(s, px, wt) {                                    // 量一段字有多宽（按软件真实用的字体量）
    if (!twCtx) twCtx = document.createElement("canvas").getContext("2d");
    if (!twFam) twFam = getComputedStyle(root).fontFamily || "sans-serif";
    twCtx.font = (wt || 400) + " " + px + "px " + twFam;
    return twCtx.measureText(String(s)).width;
  }
  const rpt = (r, a) => [r * Math.cos(a), r * Math.sin(a)];
  function rarc(r1, r2, x, y) {                               // 一块环形扇面（半径 r1~r2，角度 x~y）
    const f = (v) => v.toFixed(1), [p1x, p1y] = rpt(r2, x), [p2x, p2y] = rpt(r2, y), [p3x, p3y] = rpt(r1, y), [p4x, p4y] = rpt(r1, x), lg = y - x > Math.PI ? 1 : 0;
    return "M" + f(p1x) + "," + f(p1y) + " A" + f(r2) + "," + f(r2) + " 0 " + lg + " 1 " + f(p2x) + "," + f(p2y) +
      " L" + f(p3x) + "," + f(p3y) + " A" + f(r1) + "," + f(r1) + " 0 " + lg + " 0 " + f(p4x) + "," + f(p4y) + " Z";
  }
  function radSpans(M) {                                      // 每一片的角度：新闻多的片大；冷门的也留够地方放字
    const GAP = 0.022, MIN = 0.17;
    const raw = M.wedges.map((w) => Math.pow(w.n + 2, 0.82)), rsum = raw.reduce((a, b) => a + b, 0) || 1;
    const free = Math.PI * 2 - GAP * M.wedges.length;
    let sp = raw.map((v) => Math.max(MIN, (v / rsum) * free));
    const ssum = sp.reduce((a, b) => a + b, 0);
    sp = sp.map((v) => (v / ssum) * free);
    let a0 = -Math.PI / 2 + GAP / 2;
    return sp.map((s) => { const r = { a0, a1: a0 + s, am: a0 + s / 2, span: s }; a0 += s + GAP; return r; });
  }
  // 外圈的大类名字：先放在自己那一片正中间的外面；挤在一起的沿着圆周往两边推开（推远了用一小段弧线连回自己那片）
  function radSecLabels(M, A, R) {
    const RL = R + 18, wrap = (x) => Math.atan2(Math.sin(x), Math.cos(x));
    const L = M.wedges.map((w, i) => ({ i, a: A[i].am, w: tw(w.name, SF, 600) + 5 + tw(String(w.n), SNF), h: SF + 5 }));
    const put = (b) => { const c = Math.cos(b.a), s = Math.sin(b.a), D = RL + (b.w / 2) * Math.abs(c) + (b.h / 2) * Math.abs(s); b.x = D * c; b.y = D * s; };
    for (let k = 0; k < 600; k++) {
      L.forEach(put);
      let moved = false;
      for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) {
        const p = L[i], q = L[j];
        if (Math.abs(p.x - q.x) < (p.w + q.w) / 2 + 14 && Math.abs(p.y - q.y) < (p.h + q.h) / 2 + 5) {
          const s = wrap(q.a - p.a) >= 0 ? 1 : -1;
          p.a -= 0.004 * s; q.a += 0.004 * s; moved = true;
        }
      }
      if (!moved) break;
    }
    L.forEach(put);
    return L;
  }
  function radBox(L, R) {                                     // 饼 + 外圈名字一共占多大
    const e = R + 12, b = { x0: -e, y0: -e, x1: e, y1: e };
    L.forEach((l) => { b.x0 = Math.min(b.x0, l.x - l.w / 2); b.x1 = Math.max(b.x1, l.x + l.w / 2); b.y0 = Math.min(b.y0, l.y - l.h / 2); b.y1 = Math.max(b.y1, l.y + l.h / 2); });
    const p = 6;
    return { x: Math.floor(b.x0 - p), y: Math.floor(b.y0 - p), w: Math.ceil(b.x1 - b.x0 + 2 * p), h: Math.ceil(b.y1 - b.y0 + 2 * p) };
  }
  function radFit(M, A, aw, ah) {                             // 找能放下的最大的饼（连外圈名字一起放进 aw × ah）
    let R = Math.max(136, Math.min((ah - 110) / 2, (aw - 260) / 2)), L = null, vb = null;
    for (let k = 0; k < 6; k++) {
      L = radSecLabels(M, A, R); vb = radBox(L, R);
      const R2 = Math.max(136, Math.min((aw - (vb.w - 2 * R)) / 2, (ah - (vb.h - 2 * R)) / 2));
      if (Math.abs(R2 - R) < 1) break;
      R = R2;
    }
    return { R, L, vb };
  }
  // 一片里的一圈圈：冷门的在里、热门的在外，热门的圈厚
  function radBands(w, A, R, R0, M) {
    const cells = w.cells.slice().sort((p, q) => p.n - q.n || p.items.length - q.items.length);
    const k = cells.length, MINT = RF + 5;
    const heat = cells.map((c) => Math.pow(c.n + 1, 0.7)), hsum = heat.reduce((x, y) => x + y, 0) || 1;
    const spare = Math.max(0, R - R0 - MINT * k);
    const wt = heat.map((h) => MINT + (spare * h) / hsum), wsum = wt.reduce((x, y) => x + y, 0);
    let r1 = R0;
    return cells.map((c, ci) => {
      const r2 = ci === k - 1 ? R : r1 + ((R - R0) * wt[ci]) / wsum;
      const b = radBand(c, r1, r2, A.a0, A.a1, M);
      r1 = r2;
      return b;
    });
  }
  function radHitsLab(lab, rm, am, r, a, s) {                 // 半径 s 的圆点放在 (r, a) 会不会压到这一圈的名字
    if (lab.radial) return Math.abs(r - rm) < lab.w / 2 + 4 + s && Math.abs(a - am) * r < RF / 2 + 3 + s;
    return Math.abs(r - rm) < RF / 2 + 2 + s && Math.abs(a - am) < (lab.w / 2 + 5) / rm + (s + 1) / r;
  }
  // 一圈（一个行业）里怎么放：先定名字（沿弧横着写 → 只写名字 → 竖着写 → 截短），再把圆点排在名字两边，保证不压字
  function radBand(c, r1, r2, a0, a1, M) {
    const th = r2 - r1, rm = (r1 + r2) / 2, span = a1 - a0, am = (a0 + a1) / 2, E = 5;
    const roomT = rm * span - 2 * E;
    const fitT = (s) => th >= RF + 4 && tw(s, RF) + 6 <= roomT;
    const fitR = (s) => { const L = tw(s, RF); return th - 8 >= L && (rm - L / 2) * span >= RF + 7; };
    const mk = (nm, num, radial) => ({ nm, num, radial, w: tw(nm + (num ? " " + num : ""), RF) });
    const num = c.n ? String(c.n) : "";
    let lab = num && fitT(c.name + " " + num) ? mk(c.name, num, false) : fitT(c.name) ? mk(c.name, "", false) : fitR(c.name) ? mk(c.name, "", true) : null;
    for (let k = c.name.length - 1; !lab && k >= 2; k--) {
      const s = c.name.slice(0, k) + "…";
      if (fitT(s)) lab = mk(s, "", false); else if (fitR(s)) lab = mk(s, "", true);
    }
    const act = c.items.filter((x) => x.n).sort((p, q) => q.n - p.n);
    const smax = Math.max(2.2, Math.min(10, (th - 5) / 2));
    const base = act.map((x) => Math.min(smax, 2.5 + 8 * Math.sqrt(x.n / M.max)));
    const TRY = [[1, 4], [0.85, 3], [0.72, 2], [0.6, 1], [0.6, -1.5]];
    const pack = (lb) => { for (const [k, g] of TRY) { const p = radPack(act, base.map((s) => Math.max(2.2, s * k)), g, lb, r1, r2, rm, a0, a1, am); if (p) return p; } return null; };
    let dots = act.length ? pack(lab) : [];
    if (!dots && lab) { lab = null; dots = pack(null); }              // 实在太挤：这一圈不写名字（鼠标移上去、右边列表里都能看到）
    if (!dots) dots = radPack(act, act.map(() => 2.2), -2.5, null, r1, r2, rm, a0, a1, am, true);
    // 没新闻的小灰点：排在这一圈的内边上，避开名字和圆点
    const quiet = c.items.filter((x) => !x.n), qd = [];
    if (quiet.length) {
      const rq = r1 + 3.5, q0 = a0 + 7 / rq, q1 = a1 - 7 / rq, cand = [];
      for (let a = q0; a <= q1 + 1e-9; a += 6.5 / rq) {
        if (lab && radHitsLab(lab, rm, am, rq, a, 1.5)) continue;
        const x = rq * Math.cos(a), y = rq * Math.sin(a);
        if (dots.some((d) => Math.hypot(d.r * Math.cos(d.a) - x, d.r * Math.sin(d.a) - y) < d.s + 4)) continue;
        cand.push(a);
      }
      const m = Math.min(quiet.length, cand.length);
      for (let j = 0; j < m; j++) qd.push({ it: quiet[j], r: rq, a: cand[Math.floor(((j + 0.5) * cand.length) / m)], s: 1.5 });
    }
    return { c, r1, r2, rm, am, lab, dots, quiet: qd };
  }
  // 把圆点一行一行排进这一圈：名字那一行优先；每行在名字左右两边均匀分开，大的靠近名字。放不下就返回 null（换小一号再试）
  function radPack(act, sz, gap, lab, r1, r2, rm, a0, a1, am, force) {
    const E = 5, n = act.length, out = [];
    if (!n) return out;
    const s0 = sz[0], lo = r1 + s0 + 2, hi = r2 - s0 - 2, step = 2 * s0 + Math.max(2.5, gap + 1.5), rows = [];
    if (hi <= lo) rows.push(rm);
    else {
      rows.push(Math.min(hi, Math.max(lo, rm)));
      for (let j = 1; j < 60; j++) {
        const u = rm + j * step, v = rm - j * step;
        if (u > hi && v < lo) break;
        if (u <= hi) rows.push(u);
        if (v >= lo) rows.push(v);
      }
    }
    let i = 0;
    for (let ri = 0; ri < rows.length && i < n; ri++) {
      const r = rows[ri], sm = sz[i], A0 = a0 + (E + sm) / r, A1 = a1 - (E + sm) / r;
      if (A1 <= A0) continue;
      let ivs = [[A0, A1, 0]];
      if (lab && (lab.radial ? Math.abs(r - rm) < lab.w / 2 + 4 + sm : Math.abs(r - rm) < RF / 2 + 2 + sm)) {
        const b = lab.radial ? (RF / 2 + 3 + sm) / r : (lab.w / 2 + 5) / rm + (sm + 1) / r;
        ivs = [[A0, am - b, -1], [am + b, A1, 1]].filter((v) => v[1] > v[0]);
      }
      const used = ivs.map(() => Math.max(0, gap)), take = ivs.map(() => []);
      while (i < n) {
        const w = 2 * sz[i] + gap;
        let best = -1, room = -1e9;
        ivs.forEach((v, j) => { const left = (v[1] - v[0]) * r - used[j]; if (left >= w && left > room) { best = j; room = left; } });
        if (best < 0) break;
        take[best].push(i); used[best] += w; i++;
      }
      ivs.forEach((v, j) => {
        const ids = take[j];
        if (!ids.length) return;
        const len = (v[1] - v[0]) * r, need = ids.reduce((x, q) => x + 2 * sz[q], 0), sp = (len - need) / (ids.length + 1);
        let order = ids.slice();
        if (v[2] < 0) order.reverse();                                       // 名字左边：大的放右头（挨着名字）
        else if (v[2] === 0) { order = []; ids.forEach((q, t) => (t % 2 ? order.push(q) : order.unshift(q))); }   // 没名字挡着：大的放中间
        let pos = sp;
        order.forEach((q) => { pos += sz[q]; out.push({ it: act[q], r, a: v[0] + pos / r, s: sz[q] }); pos += sz[q] + sp; });
      });
    }
    return i < n && !force ? null : out;
  }
  function blipSvg(it, x, y, s, quiet) {
    const X = x.toFixed(1), Y = y.toFixed(1);
    return '<g class="blip fx' + (quiet ? " quiet" : "") + (it.hot && !quiet ? " hot" : "") + '" data-rad="' + esc(it.id) + '" tabindex="' + (quiet ? -1 : 0) + '" role="button" aria-label="' +
      esc(it.name + "（" + it.parent + "），" + it.n + " 条新闻" + (it.hot ? "，正在升温" : "")) + '">' +
      (quiet ? "" : '<circle cx="' + X + '" cy="' + Y + '" r="' + (s + 3.5).toFixed(1) + '" class="hit"/>') +
      (it.hot && !quiet ? '<circle cx="' + X + '" cy="' + Y + '" r="' + (s + 3.5).toFixed(1) + '" class="ring" stroke="' + it.color + '"/>' : "") +
      '<circle cx="' + X + '" cy="' + Y + '" r="' + s.toFixed(1) + '" fill="' + it.color + '" class="dot"/></g>';
  }
  // 雷达在这个窗口里能用多大：宽 = 白板宽减去右边栏；高 = 滚动区可见高度减去雷达上面的东西和下面的图例
  function radAvail() {
    const rd = $("bzRadar"), sc = $("bzScroll");
    if (!rd || !sc || rd.hidden || !rd.offsetParent || !rd.clientWidth || !sc.clientHeight) return null;
    const px = (v) => parseFloat(v) || 0, cs = getComputedStyle(rd);
    const W = Math.floor(rd.clientWidth - px(cs.paddingLeft) - px(cs.paddingRight));
    const cols = $("bzCols"), one = window.matchMedia("(max-width: 1100px)").matches || !!(cols && cols.classList.contains("reading"));
    const sr = sc.getBoundingClientRect(), rr = rd.getBoundingClientRect();
    const top = rr.top - sr.top + sc.scrollTop + px(cs.paddingTop);                     // 饼的顶边在整页里的位置
    const pane = rd.closest(".bz-pane"), pr = pane ? pane.getBoundingClientRect() : rr;
    const below = px(cs.paddingBottom) + (pr.bottom - rr.bottom) + (pane ? px(getComputedStyle(pane).marginBottom) : 0) + px(getComputedStyle(sc).paddingBottom);
    const lg = rd.querySelector(".bz-rad-legend");
    const lgH = lg && lg.offsetParent ? lg.offsetHeight + px(getComputedStyle(lg).marginTop) + px(getComputedStyle(lg).marginBottom) : 56;
    const h = Math.floor(sc.clientHeight - top - lgH - below - 7);
    return { W, one, w: Math.max(300, one ? W : W - PANEL_MIN - COLGAP), h: Math.max(300, h) };
  }
  // 窗口大小变了、上面的说明收起来了 → 重新算一次饼的大小
  let radRO = null, radROt = 0, radFitN = 0, radFitKey = "";
  function radWatch() {
    if (radRO || typeof ResizeObserver !== "function") return;
    radRO = new ResizeObserver(() => { clearTimeout(radROt); radROt = setTimeout(radFitCheck, 90); });
    const pane = root.querySelector('.bz-pane[data-pane="radar"]'), card = $("bzFeedCard");
    [$("bzScroll"), $("bzRadar"), $("bzGuide"), $("bzStripR"), pane && pane.querySelector(".bz-bar"), card && card.querySelector(".bz-card-h")].forEach((e) => { if (e) radRO.observe(e); });
  }
  function radFitCheck() {
    if (S.pane !== "radar" || S.rview !== "radar") return;
    const a = radAvail(), d = S.radDim;
    if (!a) return;
    if (d && d.one === a.one && Math.abs(d.w - a.w) <= 6 && Math.abs(d.h - a.h) <= 6 && Math.abs(d.W - a.W) <= 6) return;
    const key = innerWidth + "x" + innerHeight;
    if (key !== radFitKey) { radFitKey = key; radFitN = 0; }
    if (++radFitN > 6) return;                                // 同一个窗口大小下最多调 6 次，防止来回抖
    renderRadarScan();
  }
  function renderRadarScan() {
    const el = $("bzRadar");
    if (!el || el.hidden) return;
    const M = radarModel();
    if (!M) { el.innerHTML = loading(S.ovmErr ? "读不到：" + S.ovmErr : "正在扫描…"); return; }
    if (!(S.ovm.counts && S.ovm.counts.radar)) { el.innerHTML = empty('爬虫还没抓到东西。点上面的<button type="button" class="bz-link" data-act="upd-open">现在更新</button>马上抓一次。'); return; }
    radWatch();
    const av = radAvail() || S.radDim || { W: 1180, w: 860, h: 640, one: false };
    S.radDim = av;
    // v171：先按大类切成一片片的饼（片的大小跟新闻多少走），每一片里再按行业一圈一圈切（热门的在外、圈厚）；圆点是细分行业
    const A = radSpans(M), fit = radFit(M, A, av.w, av.h), R = fit.R, vb = fit.vb;
    const R0 = Math.max(30, Math.round(R * 0.15));
    const G = { sec: {}, cellSec: {}, itemCell: {}, single: {}, R, R0 };
    S.radPos = {}; S.radCellPos = {};
    let defs = "", body = "";
    M.wedges.forEach((w, wi) => {
      const a = A[wi], lab = fit.L[wi], bands = radBands(w, a, R, R0, M);
      G.sec[w.name] = { key: w.key || "", color: w.color, trk: !!w.trk };
      const f1 = (v) => v.toFixed(1);
      let g = "";
      bands.forEach((b, ci) => {
        const c = b.c;
        G.cellSec[c.id] = w.name; G.single[c.id] = !!c.single;
        c.items.forEach((it) => { G.itemCell[it.id] = c.id; });
        const [lx, ly] = rpt(b.rm, a.am);
        S.radCellPos[c.id] = { x: lx, y: ly, color: w.color };
        g += '<g class="cell" data-cell="' + esc(c.id) + '" color="' + w.color + '" style="--cx:' + f1(POP * 0.8 * Math.cos(a.am)) + "px;--cy:" + f1(POP * 0.8 * Math.sin(a.am)) + "px;--ox:" + f1(lx) + "px;--oy:" + f1(ly) + 'px">' +
          '<path d="' + rarc(b.r1, b.r2, a.a0, a.a1) + '" class="band-c fx' + (ci % 2 ? " alt" : "") + '" fill="' + w.color + '"/>';
        if (b.lab) {                                                   // 名字：放在这一圈正中间；沿弧写（下半圈反过来写免得倒着），放不下的竖着写
          const inner = esc(b.lab.nm) + (b.lab.num ? '<tspan class="rn"> ' + b.lab.num + "</tspan>" : "");
          const cls = '<text class="rim fx' + (c.n ? "" : " q") + '" fill="' + ink(w.color) + '"';
          if (b.lab.radial) {
            const deg = (a.am * 180) / Math.PI, flip = Math.cos(a.am) < 0;
            g += cls + ' x="' + f1(lx) + '" y="' + f1(ly) + '" text-anchor="middle" dominant-baseline="central" transform="rotate(' + f1(flip ? deg + 180 : deg) + " " + f1(lx) + " " + f1(ly) + ')">' + inner + "</text>";
          } else {
            const low = Math.sin(a.am) > 0.15, pid = "bzArc" + wi + "_" + ci;
            const [sx, sy] = rpt(b.rm, low ? a.a1 : a.a0), [ex, ey] = rpt(b.rm, low ? a.a0 : a.a1);
            defs += '<path id="' + pid + '" d="M' + f1(sx) + "," + f1(sy) + " A" + f1(b.rm) + "," + f1(b.rm) + " 0 " + (a.span > Math.PI ? 1 : 0) + " " + (low ? 0 : 1) + " " + f1(ex) + "," + f1(ey) + '"/>';
            g += cls + ' dominant-baseline="central"><textPath href="#' + pid + '" startOffset="50%" text-anchor="middle">' + inner + "</textPath></text>";
          }
        }
        b.dots.forEach((d) => { const [x, y] = rpt(d.r, d.a); S.radPos[d.it.id] = { x, y, color: d.it.color, s: d.s }; g += blipSvg(d.it, x, y, d.s, false); });
        b.quiet.forEach((d) => { const [x, y] = rpt(d.r, d.a); S.radPos[d.it.id] = { x, y, color: d.it.color, s: d.s }; g += blipSvg(d.it, x, y, d.s, true); });
        g += "</g>";
      });
      // 大类：外面一条彩色的弧 + 名字；点中时整片描边、往外弹
      g += '<path class="sec-ol" d="' + rarc(R0 - 3, R + 11, a.a0, a.a1) + '"/>' +
        '<path d="' + rarc(R + 3, R + 11, a.a0, a.a1) + '" fill="' + w.color + '" class="band fx sec-pick"/>';
      const ac = Math.min(a.a1 - 0.015, Math.max(a.a0 + 0.015, lab.a));
      if (Math.abs(ac - lab.a) > 0.004) {                             // 名字被挤开了：用一小段弧线连回自己那片
        const [p0x, p0y] = rpt(R + 12, ac), [p1x, p1y] = rpt(R + 15, ac), [p2x, p2y] = rpt(R + 15, lab.a);
        g += '<path class="lead fx" d="M' + f1(p0x) + "," + f1(p0y) + " L" + f1(p1x) + "," + f1(p1y) + " A" + f1(R + 15) + "," + f1(R + 15) + " 0 0 " + (lab.a > ac ? 1 : 0) + " " + f1(p2x) + "," + f1(p2y) + '"/>';
      }
      g += '<text class="secl fx sec-pick" x="' + f1(lab.x) + '" y="' + f1(lab.y) + '" text-anchor="middle" dominant-baseline="central" fill="' + ink(w.color, 0.25) + '">' + esc(w.name) +
        '<tspan class="secn" dx="5">' + w.n + "</tspan></text>";
      body += '<g class="wsec" data-sec="' + esc(w.name) + '" color="' + w.color + '" style="--px:' + f1(POP * Math.cos(a.am)) + "px;--py:" + f1(POP * Math.sin(a.am)) + 'px">' + g + "</g>";
    });
    S.radGeo = G;
    S.radVB = { x: vb.x, y: vb.y, w: vb.w, h: vb.h, C: 0, R };
    const [swx, swy] = rpt(R, -0.55);
    const svg = '<svg class="bz-rad-svg" width="' + vb.w + '" height="' + vb.h + '" viewBox="' + vb.x + " " + vb.y + " " + vb.w + " " + vb.h + '" role="img" aria-label="市场雷达：一片是一个大类，片里一圈是一个行业，圆点是细分行业">' +
      "<defs>" + defs + '<linearGradient id="bzSweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="var(--accent)" stop-opacity="0"/><stop offset="1" stop-color="var(--accent)" stop-opacity=".28"/></linearGradient></defs>' +
      '<g class="sweep" style="transform-origin:0px 0px"><path d="M0,0 L' + R.toFixed(1) + ",0 A" + R.toFixed(1) + "," + R.toFixed(1) + " 0 0 0 " + swx.toFixed(1) + "," + swy.toFixed(1) + ' Z" fill="url(#bzSweep)"/>' +
        '<line x1="0" y1="0" x2="' + R.toFixed(1) + '" y2="0" class="sw-l"/></g>' +
      body + '<circle r="' + (R0 - 5) + '" class="hub"/><circle r="4" class="ctr"/><g class="bz-rad-hl" id="bzRadHl"></g></svg>';
    const pw = Math.max(PANEL_MIN, Math.min(PANEL_MAX, av.W - vb.w - COLGAP));
    el.classList.toggle("one", !!av.one);
    el.style.gridTemplateColumns = av.one ? "minmax(0, 1fr)" : vb.w + "px " + pw + "px";
    const oldLive = $("bzRadLive");                         // 重画雷达时，正在亮的那几条留着接着演
    el.innerHTML = '<div class="bz-rad-l"><div class="bz-rad-stage" style="width:' + vb.w + 'px">' + svg + '<div class="bz-rad-live" id="bzRadLive"></div><div class="bz-rad-tip" id="bzRadTip" hidden></div></div></div>' +
      '<div class="bz-rad-r" id="bzRadPanel" style="height:' + (av.one ? 460 : vb.h) + 'px"></div>' +
      '<p class="bz-rad-legend"><span><i class="lg-near"></i>一片是一个大类（新闻越多片越大），片里一圈是一个行业（越热门越靠外、圈越厚），圆点是细分行业（越大新闻越多）</span>' +
      (show24() ? '<span><i class="lg-hot"></i>带圈的：最近 24 小时明显变多</span>' : "") +
      '<span><i class="lg-quiet"></i>边上的小灰点：这段时间没新闻</span>' +
      '<span class="lg-time">' + esc(dataStamp()) + "</span>" +
      '<span class="lg-how">点一片 → 再点片里的一圈 → 再点圆点，一层层看；点饼外面的空白处或按 Esc 退回一层</span></p>';
    if (oldLive && oldLive.children.length) { const nl = $("bzRadLive"); nl.replaceWith(oldLive); }
    applyRadSel(false);
    renderRadPanel(M);
    renderRadBar();
  }
  // ───────── v177：点哪个突出哪个——一次只突出一个：大类（整片往外弹）/ 行业（这一圈往外弹）/ 细分（圆点放大、标名字），别的都淡下去 ─────────
  function radSelInfo() {
    const v = S.radSel || "", G = S.radGeo;
    if (!v || !G) return null;
    if (v.startsWith("s:")) { const sec = v.slice(2); return G.sec[sec] ? { kind: "sec", sec } : null; }
    if (v.startsWith("c:")) { const cell = v.slice(2), sec = G.cellSec[cell]; return sec ? { kind: "cell", cell, sec, single: !!G.single[cell] } : null; }
    const cell = G.itemCell[v];
    return cell ? { kind: "item", item: v, cell, sec: G.cellSec[cell], single: !!G.single[cell] } : null;
  }
  function applyRadSel(anim) {
    const svg = root.querySelector("#bzRadar svg.bz-rad-svg");
    if (!svg) return;
    const s = radSelInfo();
    svg.classList.toggle("foc", !!s);
    svg.querySelectorAll(".hl").forEach((e) => e.classList.remove("hl"));
    svg.querySelectorAll(".pop, .cpop, .sel, .in").forEach((e) => e.classList.remove("pop", "cpop", "sel", "in"));
    const hl = svg.querySelector("#bzRadHl");
    if (hl) hl.innerHTML = "";
    if (!s) return;
    const sg = svg.querySelector('g.wsec[data-sec="' + CSS.escape(s.sec) + '"]');
    if (!sg) return;
    sg.classList.add("in");                                    // 鼠标在这一片里移动时，提示点的是哪一圈
    const lift = (g, cls, before) => {                         // 先挪到最上层（不被旁边盖住），再弹出来
      g.parentNode.insertBefore(g, before || null);
      if (anim) void getComputedStyle(g).transform;
      g.classList.add(cls);
    };
    if (s.kind === "sec") {
      lift(sg, "pop", svg.querySelector(".hub"));
      sg.querySelectorAll(".fx").forEach((e) => e.classList.add("hl"));
    } else if (s.kind === "cell") {
      const cg = sg.querySelector('g.cell[data-cell="' + CSS.escape(s.cell) + '"]');
      if (!cg) return;
      lift(cg, "cpop", null);
      cg.querySelectorAll(".fx").forEach((e) => e.classList.add("hl"));
    } else {
      const b = sg.querySelector('g.blip[data-rad="' + CSS.escape(s.item) + '"]'), p = S.radPos[s.item], vb = S.radVB;
      if (!b || !p) return;
      b.classList.add("sel", "hl");
      const M = radarModel(), it = M && M.items.find((x) => x.id === s.item);
      if (hl && it && vb) {                                    // 圆点上面标出名字，外面一圈在闪
        const r = p.s * 1.45, nm = it.name, lw = tw(nm, 13, 600) + 18, up = p.y - r - 30 > vb.y;
        const ly = up ? p.y - r - 17 : p.y + r + 17, lx = Math.max(vb.x + lw / 2 + 2, Math.min(vb.x + vb.w - lw / 2 - 2, p.x));
        hl.setAttribute("color", it.color);
        hl.innerHTML = '<circle class="hl-halo" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + (r + 5).toFixed(1) + '" stroke="' + it.color + '"/>' +
          '<rect x="' + (lx - lw / 2).toFixed(1) + '" y="' + (ly - 11).toFixed(1) + '" width="' + lw.toFixed(1) + '" height="22" rx="11"/>' +
          '<text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" text-anchor="middle" dominant-baseline="central">' + esc(nm) + "</text>";
      }
    }
  }
  function radSet(v) {
    S.radSel = v || "";
    radTip("", false);
    applyRadSel(true);
    renderRadPanel();
  }
  function radUp() {                                           // 退回一层：细分 → 行业 → 大类 → 全部
    const s = radSelInfo();
    if (!s) return radSet("");
    radSet(s.kind === "item" ? (s.single ? "s:" + s.sec : "c:" + s.cell) : s.kind === "cell" ? "s:" + s.sec : "");
  }
  function radPickCell(cell) {                                 // 点饼里的一圈：这一片还没选中时先选中这一片，选中了再点才是这一圈
    const s = radSelInfo(), sec = S.radGeo && S.radGeo.cellSec[cell];
    if (!sec) return;
    if (!s || s.sec !== sec) return radSet("s:" + sec);
    if (S.radSel === "c:" + cell) return radUp();
    radSet("c:" + cell);
  }
  function radPickSec(sec) { radSet(S.radSel === "s:" + sec ? "" : "s:" + sec); }
  function radClick(t) {
    const bl = t.closest("g.blip[data-rad]");
    if (bl && !bl.classList.contains("quiet")) return selectRad(bl.dataset.rad);
    const sg = t.closest("g.wsec[data-sec]");
    if (sg && t.closest(".sec-pick")) return radPickSec(sg.dataset.sec);
    const cg = t.closest("g.cell[data-cell]");
    if (cg) return radPickCell(cg.dataset.cell);
    if (S.radSel) radSet("");                                  // 点饼外面的空白：回到全部
  }
  function radPeek(id) {                                       // 鼠标移到右边列表的某一行：饼上把它标一下
    if ((S.radPeekId || "") === (id || "")) return;
    S.radPeekId = id || "";
    root.querySelectorAll("#bzRadar .peek").forEach((e) => e.classList.remove("peek"));
    if (!id) return;
    const e = root.querySelector("#bzRadar " + (id.startsWith("c:") ? 'g.cell[data-cell="' + CSS.escape(id.slice(2)) + '"]' : 'g.blip[data-rad="' + CSS.escape(id) + '"]'));
    if (e) e.classList.add("peek");
  }

  // ───────── v167：雷达真的在扫——只在爬虫抓的时候转；抓到的新闻在雷达上亮 5 秒，再归进它的行业 ─────────
  const FREQ = [[1, "实时（一轮抓完接着下一轮）"], [5, "每 5 分钟"], [10, "每 10 分钟"], [20, "每 20 分钟"], [30, "每 30 分钟"], [60, "每 1 小时"], [120, "每 2 小时"], [240, "每 4 小时"]];
  function renderRadBar() {
    const el = $("bzRadBar"), r = S.radar, rd = $("bzRadar");
    if (rd) rd.classList.toggle("scanning", !!(r && r.running));
    if (!el) return;
    if (!r) { el.innerHTML = ""; return; }
    const val = r.auto ? String(r.every) : "off";
    const opts = FREQ.map(([v, t]) => [String(v), t]);
    if (r.auto && !FREQ.some(([v]) => v === r.every)) opts.push([String(r.every), "每 " + everyText(r.every)]);
    opts.push(["off", "不自动扫（只手动）"]);
    const sel = '<label class="bz-rad-freq">扫描频率 <select class="bz-select sm" id="bzRadFreq">' +
      opts.map(([v, t]) => '<option value="' + v + '"' + (v === val ? " selected" : "") + ">" + esc(t) + "</option>").join("") + "</select></label>";
    if (r.running) {
      const pct = r.total ? Math.round((r.done / r.total) * 100) : 0;
      el.innerHTML = '<span class="bz-rad-st on"><i></i>' + (r.resumes ? "接着上次扫" : "正在扫描") + '</span><span class="bz-rad-pg"><b>' + r.done + " / " + r.total + "</b> 个信息源 · 这一轮新发现 <b>" + r.new + "</b> 条</span>" +
        '<span class="bz-prog sm" aria-hidden="true"><i style="width:' + pct + '%"></i></span><span class="sp"></span>' + sel +
        '<button type="button" class="bz-link" data-act="rd-stop">停止</button>';
    } else if (r.resume) {                                 // v177：上次没扫完（关了软件、异常退出、点了停止）→ 接着扫
      const z = r.resume;
      el.innerHTML = '<span class="bz-rad-st warn"><i></i>没扫完</span><span class="bz-rad-pg">上次扫到 <b>' + z.done + " / " + z.total + "</b> 个信息源</span>" +
        '<span class="sp"></span>' + sel + '<button type="button" class="bz-link" data-act="rd-run">接着扫（剩 ' + z.left + " 个）</button>";
    } else {
      const nx = r.next_run;
      el.innerHTML = '<span class="bz-rad-st"><i></i>待机</span><span class="bz-rad-pg">' +
        (r.auto ? (r.every <= 1 ? "实时扫描：马上开始下一轮" : "下次扫描 " + (nx ? (nx <= Date.now() / 1000 + 30 ? "马上" : hhmm(nx).slice(0, 5)) : "—")) : "自动扫描关着") +
        (r.last_run ? " · 上次 " + ago(r.last_run) : "") + '</span><span class="sp"></span>' + sel +
        '<button type="button" class="bz-link" data-act="rd-run">现在扫一次</button>';
    }
  }
  async function setFreq(v) {
    const body = v === "off" ? { auto: false } : { auto: true, every: +v };
    const r = await api("/biz/radar/config", body).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) { toast(r.error || "没存上"); return; }
    const f = FREQ.find((x) => String(x[0]) === v);
    toast(v === "off" ? "自动扫描关了，要扫时点「现在扫一次」。" : +v <= 1 ? "改成实时扫描了：一轮抓完接着下一轮。" : "改好了：" + (f ? f[1] : "每 " + v + " 分钟") + "扫一次，从现在开始计时。");
    pollRadar();
  }
  const LIVE = { rid: "", since: 0, seen: new Set(), queue: [], active: 0, last: 0, timer: 0, busy: false };
  async function liveTick(r, force) {
    const onRadar = S.pane === "radar" && S.rview === "radar" && $("bzRadLive"), onMap = S.pane === "industry" && S.indView === "map" && $("bzIndMain");
    if (!onRadar && !onMap) return;                         // v186：行业地图上也演
    if (force) { LIVE.last = 0; LIVE.busy = false; }
    if (LIVE.rid !== r.rid) { LIVE.rid = r.rid; LIVE.since = r.started || Math.floor(Date.now() / 1000); LIVE.seen = new Set(); LIVE.queue = []; }
    if (LIVE.busy || Date.now() - LIVE.last < 2000) return;
    LIVE.busy = true; LIVE.last = Date.now();
    let d = null;
    try { d = await api("/biz/items?lens=market&days=0&since=" + LIVE.since + "&limit=60"); } catch (e) {}
    LIVE.busy = false;
    ((d && d.items) || []).slice().reverse().forEach((it) => {
      if (LIVE.seen.has(it.id)) return;
      LIVE.seen.add(it.id);
      LIVE.queue.push(it);
    });
    if (LIVE.queue.length > 24) LIVE.queue = LIVE.queue.slice(-24);    // 一下子抓到太多，只演最新的
    pumpLive();
  }
  function pumpLive() {
    clearTimeout(LIVE.timer);
    if (!LIVE.queue.length) return;
    if (LIVE.active < 4) {
      if (S.pane === "industry" && S.indView === "map" && $("bzIndMain")) showMapLive(LIVE.queue.shift());   // v186
      else if ($("bzRadLive")) showLive(LIVE.queue.shift());
    }
    LIVE.timer = setTimeout(pumpLive, 900);
  }
  // v186：雷达扫到一条新闻：行业地图上它所在的那一小格闪一下、数字加 1，标题在旁边冒出来，3 秒后消失
  function showMapLive(it) {
    const main = $("bzIndMain"), layer = $("bzMapLive");
    if (!it || !main || !layer) return;
    const ids = [...(it.l3 || []), ...(it.ind || []), ...(it.trk || [])];
    const tiles = ids.map((id) => main.querySelector('.bz-tile[data-ind="' + CSS.escape(id) + '"]')).filter(Boolean);
    if (!tiles.length) return;                                  // 没归到行业的新闻：地图上没有它的格子
    S.gotUntil = S.gotUntil || {};                              // 3 秒里地图重画了，闪的格子接着闪
    tiles.slice(0, 3).forEach((t) => { S.gotUntil[t.dataset.ind] = Date.now() + 3000; });
    if (it.url) S.artItems[it.id] = it;
    tiles.slice(0, 3).forEach((t) => {
      t.classList.remove("got"); void t.offsetWidth; t.classList.add("got");
      const c = t.querySelector(".ct");
      if (c && c.firstChild && c.firstChild.nodeType === 3) c.firstChild.nodeValue = String((parseInt(c.firstChild.nodeValue, 10) || 0) + 1);
      setTimeout(() => t.classList.remove("got"), 3000);
    });
    const sc = $("bzScroll"), sr = sc ? sc.getBoundingClientRect() : { top: 0, bottom: innerHeight };
    const vis = (el) => { const r = el.getBoundingClientRect(); return r.bottom > sr.top + 4 && r.top < sr.bottom - 4; };
    const t = tiles.find(vis) || tiles[0];                     // 标题放在屏幕上看得到的那一格旁边（最细的优先）
    const mr = layer.getBoundingClientRect(), tr = t.getBoundingClientRect(), id = t.dataset.ind;   // 标题放在不会被重画的那一层上
    const zh = S.trTitle[it.title] || it.title || "";
    const bub = document.createElement("button");
    bub.type = "button"; bub.className = "bz-got"; bub.dataset.art = it.id; bub.title = "点一下看这条新闻";
    bub.innerHTML = '<span class="t">' + esc(zh.length > 42 ? zh.slice(0, 42) + "…" : zh) + "</span>" +
      '<span class="g"><i style="background:' + colorOf(id) + '"></i>' + esc(nameOf(id)) + (it.who ? " · " + esc(it.who) : "") + "</span>";
    const w = Math.min(270, mr.width - 8);
    bub.style.maxWidth = w + "px";
    bub.style.left = Math.max(4, Math.min(tr.left - mr.left, mr.width - w - 4)) + "px";
    bub.style.top = (tr.top - 50 < sr.top ? tr.bottom - mr.top + 4 : tr.top - mr.top - 48) + "px";   // 上面放不下就放到下面
    layer.appendChild(bub);
    LIVE.active++;
    setTimeout(() => { bub.classList.add("out"); setTimeout(() => { bub.remove(); LIVE.active = Math.max(0, LIVE.active - 1); }, 400); }, 3000);
  }
  function showLive(it) {
    const box = $("bzRadLive"), vb = S.radVB;
    if (!box || !vb) return;
    const tgt = (it.ind && it.ind[0]) || (it.trk && it.trk[0]) || "";
    const ps = S.radPos[tgt] || (S.radCellPos && S.radCellPos[String(tgt).split("/")[0]]) || { x: vb.C, y: vb.C, color: "var(--accent)" };
    const lx = ((ps.x - vb.x) / vb.w) * 100, ly = ((ps.y - vb.y) / vb.h) * 100;
    if (it.url) S.artItems[it.id] = it;
    const zh = S.trTitle[it.title] || it.title;
    const el = document.createElement("div");
    el.className = "bz-live" + (lx > 58 ? " left" : "");
    el.style.left = lx + "%"; el.style.top = ly + "%";
    el.innerHTML = '<i class="ping" style="border-color:' + ps.color + '"></i>' +
      '<button type="button" class="card" data-art="' + esc(it.id) + '" title="点一下看这条新闻">' +
      '<span class="t">' + esc(zh.length > 30 ? zh.slice(0, 30) + "…" : zh) + "</span>" +
      '<span class="g" style="color:' + ps.color + '">→ ' + esc(tgt ? nameOf(tgt) : "还没归类") + "</span></button>";
    box.appendChild(el);
    LIVE.active++;
    setTimeout(() => {
      el.classList.add("into");                              // 5 秒后收进它的行业
      const g = root.querySelector('#bzRadar g.blip[data-rad="' + CSS.escape(tgt) + '"]');
      if (g) { g.classList.add("flash"); setTimeout(() => g.classList.remove("flash"), 1200); }
      setTimeout(() => { el.remove(); LIVE.active = Math.max(0, LIVE.active - 1); }, 700);
    }, 5000);
  }

  function radHover(cg) {                     // v178：鼠标放在哪一圈，那一圈（连里面的点和字）变大一点、浮在最上面
    const svg = root.querySelector("#bzRadar svg.bz-rad-svg");
    if (!svg) return;
    const cur = svg.querySelector("g.cell.hov");
    if (cur === cg) return;
    if (cur) cur.classList.remove("hov");
    if (!cg) return;
    const sg = cg.parentNode, hub = svg.querySelector(".hub");
    if (sg.lastElementChild !== cg) sg.appendChild(cg);
    if (hub && sg.nextElementSibling !== hub) svg.insertBefore(sg, hub);
    void getComputedStyle(cg).transform;
    cg.classList.add("hov");
  }
  // v177：右边栏和饼一样高，里面的列表自己往下滑；点了饼上的一片 / 一圈 / 一个点，就换成它的详情
  function renderRadPanel(M) {
    const el = $("bzRadPanel");
    M = M || radarModel();
    renderScanCard(M);
    if (!el || !M) return;
    S.radKeep = S.radKeep || {};
    const old = el.querySelector(".bz-rp-scroll[data-keep]");
    if (old) S.radKeep[old.dataset.keep] = old.scrollTop;          // 记住列表滑到哪了，回来接着看
    const win = winText();
    const s = radSelInfo(), ov = S.ovm || {};
    const row = (attr, color, name, sub, hot, n, mx) => '<li><button type="button" ' + attr + '><i style="background:' + color + '"></i><span class="nm">' + esc(name) + "</span>" +
      '<span class="sc">' + esc(sub) + '</span><span class="hotc">' + (hot ? '<span class="hot">升温</span>' : "") + "</span>" +
      '<span class="bar"><b style="width:' + Math.max(4, Math.round((n / (mx || 1)) * 100)) + "%;background:" + color + '"></b></span><span class="n">' + n + "</span></button></li>";
    if (!s) {
      // v175：右边三个标签：扫描结果 / 正在升温 / 提得最多；v177：全部列出来，往下滑看
      const tab = S.radTab || "scan", tabs = [["scan", "扫描结果"], ["rising", "正在升温"], ["hot", "提得最多"]];
      let body = "";
      if (tab === "scan") {
        const all = M.items.filter((x) => x.n).sort((a, b) => b.n - a.n);
        body = '<p class="bz-hint">' + win + "，" + all.length + " 个细分有新闻，按条数排。往下滑看全部；点一个，饼上会把它标出来。</p>" +
          '<ol class="bz-rad-rank sm">' + all.map((x) => row('data-rad="' + esc(x.id) + '"', x.color, x.name, x.parent, x.hot, x.n, M.max)).join("") + "</ol>";
      } else if (tab === "rising") {
        const w2 = S.mdays === 1 || S.mdays === -1 ? "最近 6 小时" : "最近 24 小时";
        body = '<p class="bz-hint">' + w2 + "提到它的比例，明显高于这段时间的平均。点一下看相关新闻。</p>" +
          '<div class="bz-terms">' + ((ov.rising || []).length ? ov.rising.slice(0, 40).map((x) =>
            '<button type="button" class="bz-term" data-term="' + esc(x.k) + '" title="' + esc(w2 + " " + x.r + " 条，这段时间一共 " + x.n + " 条，来自 " + x.src + " 个信息源") + '">' +
            '<span class="k">' + esc(x.k) + '</span><span class="bar"><i style="width:' + Math.max(6, Math.round((x.r / x.n) * 100)) + '%"></i></span>' +
            '<span class="n">' + x.r + "<small> / " + x.n + "</small></span></button>").join("") : empty("还看不出哪个话题在升温。")) + "</div>";
      } else {
        body = '<p class="bz-hint">这段时间新闻里提得最多的词。点一下看相关新闻。</p><div class="bz-chips">' +
          ((ov.hot || []).length ? ov.hot.slice(0, 60).map((x) => '<button type="button" class="bz-chip" data-term="' + esc(x.k) + '">' + esc(x.k) + " <b>" + x.n + "</b></button>").join("") : empty("还没有。")) + "</div>";
      }
      el.innerHTML = '<div class="bz-ptabs" role="tablist">' + tabs.map(([k, n]) => '<button type="button" role="tab" data-radtab="' + k + '" aria-selected="' + (k === tab) + '">' + n + "</button>").join("") + "</div>" +
        '<div class="bz-rp-scroll" data-keep="' + tab + '">' + body + "</div>";
      const sc = el.querySelector(".bz-rp-scroll");
      if (sc && S.radKeep[tab]) sc.scrollTop = S.radKeep[tab];
      return;
    }
    const W = M.wedges.find((w) => w.name === s.sec);
    if (!W) { S.radSel = ""; return renderRadPanel(M); }
    const nav = (up) => '<div class="bz-rad-nav"><button type="button" class="bz-link" data-act="rad-up">‹ ' + esc(up) + "</button>" +
      (s.kind !== "sec" ? '<button type="button" class="bz-link dim" data-act="rad-top">回到全部</button>' : "") + "</div>";
    const head = (color, name, small, n, t, hot) => '<h4 class="bz-rad-h"><i style="background:' + color + '"></i>' + esc(name) + "<small>" + esc(small) + "</small></h4>" +
      '<p class="bz-rad-num"><b>' + n + "</b> 条新闻（" + win + "）" + (show24() ? "，最近 24 小时 " + t + " 条" : "") + (hot ? ' <span class="hot">正在升温</span>' : "") + "</p>";
    const tops = S.radTops && S.radTops.days === S.mdays ? S.radTops.tops : null;
    const newsOf = (id) => { const v = tops ? (tops[id] || []) : S.radNews[id + "|" + S.mdays]; if (!v) loadRadNews(id); return v; };
    const newsHTML = (v) => '<h5 class="bz-rad-sub">最新的几条</h5><div class="bz-feed compact">' + (v ? (v.length ? v.map(itemRow).join("") : empty("没读到。")) : loading()) + "</div>";
    let top = "", body = "";
    if (s.kind === "sec") {
      const cells = W.cells.slice().sort((a, b) => b.n - a.n), mx = Math.max(1, ...cells.map((c) => c.n)), what = W.trk ? "方向" : "行业";
      top = nav("回到全部") + head(W.color, W.name, (W.trk ? "新方向" : "大类") + " · " + W.cells.length + " 个" + what, W.n, W.cells.reduce((a, c) => a + c.t, 0), false);
      body = '<p class="bz-hint">这一片里的' + what + "，按条数排（饼上越靠外越热门）。点一个看里面的细分和新闻：</p>" +
        '<ol class="bz-rad-rank sm">' + cells.map((c) => row('data-radcell="' + esc(c.id) + '"', W.color, c.name, c.single ? "" : c.items.filter((x) => x.n).length + " 个细分", c.hot, c.n, mx)).join("") + "</ol>" +
        (W.key ? '<button type="button" class="bz-btn" data-rad-list="sec:' + esc(W.key) + '">看「' + esc(W.name) + "」的全部新闻</button>" : "");
    } else if (s.kind === "cell" && !s.single) {
      const c = W.cells.find((x) => x.id === s.cell);
      if (!c) { S.radSel = ""; return renderRadPanel(M); }
      const act = c.items.filter((x) => x.n).sort((a, b) => b.n - a.n), quiet = c.items.filter((x) => !x.n);
      top = nav("回到「" + W.name + "」") + head(W.color, c.name, W.name, c.n, c.t, c.hot);
      body = (act.length ? '<p class="bz-hint">里面的细分（饼上这一圈里的圆点），点一个看详情：</p><ol class="bz-rad-rank sm">' +
          act.map((x) => row('data-rad="' + esc(x.id) + '"', x.color, x.name, "", x.hot, x.n, M.max)).join("") + "</ol>" : "") +
        (quiet.length ? '<p class="bz-rad-quiet">这段时间没新闻的：' + quiet.map((x) => esc(x.name)).join("、") + "</p>" : "") +
        newsHTML(newsOf(c.id)) +
        '<button type="button" class="bz-btn" data-rad-list="' + esc(c.id) + '">看「' + esc(c.name) + "」的全部新闻</button>";
    } else {
      const id = s.kind === "item" ? s.item : s.cell, it = M.items.find((x) => x.id === id), c = W.cells.find((x) => x.id === s.cell);
      if (!it || !c) { S.radSel = ""; return renderRadPanel(M); }
      const sibs = s.single ? [] : c.items.filter((x) => x.id !== id && x.n).sort((a, b) => b.n - a.n);
      const l1 = !s.single && id.includes("/") ? id.split("/")[0] : "";
      top = nav(s.single ? "回到「" + W.name + "」" : "回到「" + c.name + "」") + head(it.color, it.name, it.sec + (it.parent !== it.sec ? " · " + it.parent : ""), it.n, it.t, it.hot);
      body = (sibs.length ? '<p class="bz-hint">同一圈「' + esc(c.name) + "」里的其他细分：</p><div class=\"bz-chips\">" + sibs.slice(0, 12).map((x) =>
          '<button type="button" class="bz-chip" data-rad="' + esc(x.id) + '">' + esc(x.name) + " <b>" + x.n + "</b></button>").join("") + "</div>" : "") +
        newsHTML(newsOf(id)) +
        '<button type="button" class="bz-btn" data-rad-list="' + esc(id) + '">看「' + esc(it.name) + "」的新闻列表</button>" +
        (l1 ? '<button type="button" class="bz-link bz-rad-l1" data-rad-list="' + esc(l1) + '">看整个「' + esc(c.name) + "」的新闻</button>" : "");
    }
    el.innerHTML = '<div class="bz-rad-sel"><div class="bz-rad-selh">' + top + '</div><div class="bz-rp-scroll">' + body + "</div></div>";
  }
  function renderScanCard(M) {                 // v169：「扫描结果」挪到雷达下面，和「正在升温」并排
    const el = $("bzScanList"), hd = $("bzScanHint");
    if (!el) return;
    if (!M) { el.innerHTML = ""; return; }
    const win = winText();
    const all = M.items.filter((x) => x.n).sort((a, b) => b.n - a.n);
    if (hd) hd.textContent = win + "，" + all.length + " 个细分行业和新方向有新闻，按条数排。点名字在雷达上看。";
    el.innerHTML = '<ol class="bz-rad-rank">' + all.slice(0, 20).map((x) =>
      '<li><button type="button" data-rad="' + esc(x.id) + '"' + (x.id === S.radSel ? ' class="on"' : "") + '><i style="background:' + x.color + '"></i><span class="nm">' + esc(x.name) + "</span>" +
      '<span class="sc">' + esc(x.parent) + "</span>" + '<span class="hotc">' + (x.hot ? '<span class="hot">升温</span>' : "") + "</span>" +
      '<span class="bar"><b style="width:' + Math.max(4, Math.round((x.n / M.max) * 100)) + "%;background:" + x.color + '"></b></span><span class="n">' + x.n + "</span></button></li>").join("") + "</ol>";
  }
  async function loadRadTops() {                // v168：每个行业最新几条一次读好，点圆点马上就有
    const d = S.mdays;
    let r;
    try { r = await api("/biz/radar_tops?days=" + d); } catch (e) { return; }
    if (!r || !r.tops || d !== S.mdays) return;
    S.radTops = { days: d, tops: r.tops };
    if (S.radSel) renderRadPanel();
  }
  function radTip(id, show) {                  // v168：鼠标移到圆点上马上出提示；v177：移到一圈上也有，告诉你点了会怎样
    const tip = $("bzRadTip"), vb = S.radVB;
    if (!tip) return;
    if (!show || !id || !vb) { tip.hidden = true; return; }
    const M = radarModel();
    if (!M) { tip.hidden = true; return; }
    let ps = null, html = "";
    if (id.startsWith("c:")) {
      const key = id.slice(2), secn = S.radGeo && S.radGeo.cellSec[key], W = M.wedges.find((w) => w.name === secn), c = W && W.cells.find((x) => x.id === key);
      ps = S.radCellPos && S.radCellPos[key];
      if (!c || !ps) { tip.hidden = true; return; }
      const s = radSelInfo(), inSec = s && s.sec === W.name;
      html = '<b style="color:' + W.color + '">' + esc(c.name) + "</b><small>" + esc(W.name) + "</small>" +
        "<p>" + (c.n ? c.n + " 条新闻" + (show24() ? "，最近 24 小时 " + c.t + " 条" : "") + (c.hot ? ' <span class="hot">升温</span>' : "") : "这段时间没有新闻") + "</p>" +
        '<p class="h">' + (!inSec ? "点一下选中「" + esc(W.name) + "」这一片" : S.radSel === "c:" + key ? "再点一下回到「" + esc(W.name) + "」" : "点一下看「" + esc(c.name) + "」") + "</p>";
    } else {
      const it = M.items.find((x) => x.id === id);
      ps = S.radPos && S.radPos[id];
      if (!it || !ps) { tip.hidden = true; return; }
      const tops = S.radTops && S.radTops.days === S.mdays ? (S.radTops.tops[id] || []) : [];
      html = '<b style="color:' + it.color + '">' + esc(it.name) + "</b><small>" + esc(it.sec + (it.parent !== it.sec ? " · " + it.parent : "")) + "</small>" +
        "<p>" + (it.n ? it.n + " 条新闻" + (show24() ? "，最近 24 小时 " + it.t + " 条" : "") + (it.hot ? ' <span class="hot">升温</span>' : "") : "这段时间没有新闻") + "</p>" +
        (tops[0] ? '<p class="t">最新：' + esc(S.trTitle[tops[0].title] || tops[0].title) + "</p>" : "") + (it.n ? '<p class="h">' + (S.radSel === id ? "再点一下退回上一层" : "点一下看详情") + "</p>" : "");
    }
    tip.innerHTML = html;
    const lx = ((ps.x - vb.x) / vb.w) * 100, ly = ((ps.y - vb.y) / vb.h) * 100;
    tip.style.left = lx + "%"; tip.style.top = ly + "%";
    tip.classList.toggle("left", lx > 55);
    tip.classList.toggle("up", ly > 60);
    tip.hidden = false;
  }
  async function loadRadNews(id) {
    const key = id + "|" + S.mdays;
    if (S.radNews[key] === null) return;                     // 正在读
    S.radNews[key] = null;
    let r;
    try { r = await api("/biz/items?lens=market&days=" + S.mdays + (id.startsWith("t:") ? "&trk=" : "&ind=") + enc(id) + "&limit=6"); } catch (e) { r = null; }
    S.radNews[key] = (r && r.items) || [];
    const s = radSelInfo();
    if (s && (s.item === id || s.cell === id)) renderRadPanel();
  }
  function selectRad(id) {                     // 点圆点、点右边列表里的名字；再点一下同一个就退回一层
    if (S.radSel === id) return radUp();
    radSet(id);
  }

  // ───────── v161：右边的阅读栏（正文 + 翻译） ─────────
  const isForeign = (t) => {
    t = String(t || "").replace(/\s+/g, "").slice(0, 3000);
    if (t.length < 6) return false;
    if (/[\u3040-\u30ff\uac00-\ud7af]/.test(t)) return true;
    const han = (t.match(/[\u4e00-\u9fff]/g) || []).length, all = (t.match(/\p{L}/gu) || []).length;
    return all - han >= 6 && han < (all - han) * 0.1;
  };
  async function translateTitles(list) {
    const todo = Array.from(new Set((list || []).map((x) => x.title).filter((t) => t && !(t in S.trTitle) && isForeign(t))));
    if (!todo.length) return;
    todo.forEach((t) => { S.trTitle[t] = ""; });              // 正在翻，别重复请求
    let r;
    try { r = await api("/biz/translate", { lines: todo }); } catch (e) { r = null; }
    if (!r || !r.items) { todo.forEach((t) => { delete S.trTitle[t]; }); return; }
    todo.forEach((t, i) => { S.trTitle[t] = r.items[i] || ""; });
    if (r.items.some(Boolean)) { renderFeed(); if (S.artSel) renderReadP(); }
  }
  function readBodyHTML(it) {
    const a = S.art[it.url], tr = S.artTr[it.url];
    const useZh = a && a.foreign && S.artLang === "zh" && tr && tr.ok;
    const src = useZh ? tr : a;
    if (!a || a.loading) {
      return (it.text ? '<p class="bz-art-sum">' + esc(it.text) + "</p>" : "") + '<p class="bz-art-wait">正在读取正文…</p>';
    }
    let h = "";
    if (a.foreign && S.artLang === "zh" && !(tr && tr.ok)) {
      h += '<p class="bz-art-tip">' + (tr && tr.error ? "翻译没成功：" + esc(tr.error) + ' <button type="button" class="bz-link" data-act="art-retr">再试一次</button>' : "正在翻译成中文…先显示原文。") + "</p>";
    }
    if (src.paras && src.paras.length) h += src.paras.map((x) => "<p>" + esc(x) + "</p>").join("");
    else {
      const sum = src.desc || a.summary || it.text || "";
      h += (sum ? '<p class="bz-art-sum">' + esc(sum) + "</p>" : "") +
        (a.orig || a.video ? "" : '<p class="bz-art-miss">没读出正文' + (a.error ? "：" + esc(a.error) : "") + "。想看全文，可以点上面的原文链接。</p>");
    }
    return h + artVideoHTML(it, a) + artOrigHTML(a);
  }
  // v179：原文链接放在最上面；跳转后真正的文章、「阅读原文」指向的文章也一起列出来
  function readLinksHTML(it) {
    const a = S.art[it.url] || {};
    const lk = (u) => '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + "</a>";
    const KIND = { google: "真正的文章", orig: "「阅读原文」指向", jump: "跳转到" };
    let h = '<div class="bz-art-src top"><span class="k">原文链接</span>' + lk(it.url) + "</div>";
    (a.hops || []).forEach((x) => {
      h += '<div class="bz-art-src top"><span class="k">' + (KIND[x.kind] || "跳转到") + "</span>" + lk(x.url) +
        (x.kind === "google" ? "<small>上面那个是 Google 新闻的跳转链接，已经自动找到原文，下面显示的就是原文</small>" : "") + "</div>";
    });
    if (a.note) h += '<p class="bz-art-tip">' + esc(a.note) + "</p>";
    return '<div class="bz-art-links">' + h + "</div>";
  }
  // v179：新闻里的视频 → 视频里说的话（语音转文字）
  function artVideoHTML(it, a) {
    if (!a || !a.video) return "";
    const m = S.artMedia[it.url] || {}, st = m.state || "none";
    let b = '<section class="bz-art-sec"><h4>视频里说的话<small>把视频的声音转成文字</small></h4>';
    if (st === "done") {
      b += (m.paras || []).map((x) => "<p>" + esc(x) + "</p>").join("") +
        '<p class="bz-art-note">约 ' + (m.chars || 0) + " 字" + (m.via === "local_whisper" ? "，本机语音识别" : m.via ? "，用的是视频自带字幕" : "") +
        (m.src ? '。视频：<a href="' + esc(m.src) + '" target="_blank" rel="noopener">' + esc(m.src.length > 70 ? m.src.slice(0, 70) + "…" : m.src) + "</a>" : "") + "</p>";
    } else if (st === "fail") {
      b += '<p class="bz-art-miss">没转成：' + esc(m.error || "原因不明") + ' <button type="button" class="bz-link" data-act="art-media">再试一次</button></p>';
    } else if (st === "queued" || st === "running") {
      b += '<p class="bz-art-wait">' + esc(m.stage || "排队") + (m.detail ? "：" + esc(m.detail) : "") + (st === "queued" && m.pos > 1 ? "（前面还有 " + (m.pos - 1) + " 个）" : "") + "</p>";
    } else {
      b += '<p class="bz-art-note">这条新闻里有视频。</p><button type="button" class="bz-btn sm" data-act="art-media">把视频里的话转成文字</button>';
    }
    return b + "</section>";
  }
  // v179：只有几句话的新闻，跟着「阅读原文」读出来的原文全文
  function artOrigHTML(a) {
    const o = a && a.orig;
    if (!o || !(o.paras && o.paras.length)) return "";
    return '<section class="bz-art-sec"><h4>原文全文<small>这条新闻写着「阅读原文」，跟过去从 ' + esc(o.site) + " 读出来的，约 " + o.chars + " 字</small></h4>" +
      (o.title ? '<p class="bz-art-ot">' + esc(o.title) + "</p>" : "") + o.paras.map((x) => "<p>" + esc(x) + "</p>").join("") + "</section>";
  }
  function readMetaHTML(it) {
    const a = S.art[it.url] || {}, tr = S.artTr[it.url];
    return [it.who ? "来源：" + esc(it.who) + (it.from && it.from !== it.who ? "·" + esc(it.from) : "") : "",
      a.pub ? "发布：" + esc(a.pub.replace("T", " ").slice(0, 16)) : (it.ts && !it.approx ? "发布：" + esc(fmtTime(it.ts)) : ""),
      a.chars ? "原文约 " + a.chars + " 字" : "",
      a.foreign && tr && tr.ok && S.artLang === "zh" ? "翻译：" + esc(tr.via) : ""].filter(Boolean).map((x) => "<span>" + x + "</span>").join("");
  }
  function readTitle(it) {
    const tr = S.artTr[it.url], a = S.art[it.url] || {};
    const zh = (a.foreign && tr && tr.ok && tr.title) || S.trTitle[it.title] || "";
    return S.artLang === "zh" && zh && zh !== it.title ? { main: zh, orig: it.title } : { main: it.title, orig: "" };
  }
  function renderReadP() {
    const el = $("bzReadP"), cols = $("bzCols");
    if (!el) return;
    const it = S.artItems[S.artSel];
    cols.classList.toggle("reading", !!it);
    el.hidden = !it;
    if (!it) { el.innerHTML = ""; return; }
    const a = S.art[it.url] || {}, ti = readTitle(it);
    const list = S.rfeed || [], i = list.findIndex((x) => x.id === it.id);
    const prev = i > 0 ? list[i - 1].id : "", next = i >= 0 && i < list.length - 1 ? list[i + 1].id : "";
    const isR = it.src === "radar";
    const keepTop = el.dataset.id === it.id ? (el.querySelector(".bz-rp-body") || {}).scrollTop || 0 : 0;
    el.dataset.id = it.id;
    el.innerHTML =
      '<div class="bz-rp-h"><span class="bz-src s-' + it.src + '">' + esc(isR ? (GRP[it.grp] || SRC.radar) : SRC[it.src]) + "</span>" +
        (a.foreign ? '<div class="bz-tog" role="group" aria-label="看译文还是原文">' +
          '<button type="button" data-act="art-lang" data-v="zh" aria-pressed="' + (S.artLang === "zh") + '">中文</button>' +
          '<button type="button" data-act="art-lang" data-v="orig" aria-pressed="' + (S.artLang !== "zh") + '">原文</button></div>' : "") +
        '<span class="sp"></span>' +
        (S.kbSent[it.url] ? '<span class="bz-kb-ok" title="在左栏「知识库 → 整理记录」里能看到收录进度">✓ 已排进知识库</span>'
          : '<button type="button" class="bz-rp-nav kb" data-act="art-kb" title="让 AI 把这条新闻整理进知识库的主题页"' + (a.loading || !S.art[it.url] ? " disabled" : "") + ">收进知识库</button>") +
        '<button type="button" class="bz-rp-nav" data-art="' + esc(prev) + '"' + (prev ? "" : " disabled") + ' aria-label="上一条">‹ 上一条</button>' +
        '<button type="button" class="bz-rp-nav" data-art="' + esc(next) + '"' + (next ? "" : " disabled") + ' aria-label="下一条">下一条 ›</button>' +
        '<button type="button" class="bz-x" data-act="art-close" aria-label="关闭阅读栏（Esc）" title="关闭（Esc）">×</button></div>' +
      '<div class="bz-rp-body" tabindex="-1"><h2 class="bz-rp-t">' + esc(ti.main) + "</h2>" + (ti.orig ? '<p class="bz-rp-orig">' + esc(ti.orig) + "</p>" : "") +
        '<div class="bz-rp-m">' + readMetaHTML(it) + "</div>" + readLinksHTML(it) +
        '<div class="bz-art-body">' + readBodyHTML(it) + "</div>" +
      "</div>";
    if (keepTop) el.querySelector(".bz-rp-body").scrollTop = keepTop;
  }
  function closeArt() {
    const id = S.artSel;
    S.artSel = "";
    renderReadP();
    if (id) {
      root.querySelectorAll(".bz-item.sel").forEach((e) => { e.classList.remove("sel"); const b = e.querySelector("[aria-current]"); if (b) b.removeAttribute("aria-current"); });
      const b = root.querySelector('#bzFeed [data-art="' + CSS.escape(id) + '"]');
      if (b) b.focus();
    }
  }
  async function loadArt(it) {
    const url = it.url;
    if (!S.art[url] || (S.art[url].failed && !S.art[url].loading)) {
      S.art[url] = { loading: true };
      let r;
      try { r = await api("/biz/article?url=" + enc(url)); } catch (e) { r = { ok: false, error: "连不上后台" }; }
      if (!r || r.ok === false) r = { paras: [], error: (r && r.error) || "读取失败", failed: true };
      else if (!(r.paras && r.paras.length) && !r.desc) r.failed = true;
      if (!r.foreign && isForeign(it.title) && !(r.paras && r.paras.length)) r.foreign = true;
      S.art[url] = r;
      if (r.pub && it.approx) {                    // v164：网页里读到了发布时间，列表这一行也补上
        const t = Date.parse(r.pub);
        if (t && t / 1000 > 946684800 && t / 1000 < Date.now() / 1000 + 86400) {
          it.ts = Math.round(t / 1000); it.approx = false;
          root.querySelectorAll('.bz-item[data-row="' + CSS.escape(it.id) + '"]').forEach((e) => { e.outerHTML = itemRow(it); });
        }
      }
      refreshArt(it);
    }
    const a = S.art[url];
    const md = S.artMedia[url];                     // v179：有视频：查转文字的进度，第一次点开就自动开始
    if (a.video && (!md || md.state === "none" || md.state === "queued" || md.state === "running")) loadMedia(it, !!a.video.auto && (!md || md.state === "none"));
    if (a.foreign && !S.artTr[url]) await loadTr(it);
  }
  async function loadMedia(it, start) {
    const url = it.url;
    let r = null;
    try { r = await api("/biz/article_media?url=" + enc(url) + (start ? "&start=1" : "")); } catch (e) {}
    if (r && r.state) S.artMedia[url] = r;
    refreshArt(it);
    clearTimeout(S.mediaT);
    const m = S.artMedia[url] || {}, cur = curArt();
    if (cur && cur.url === url && (m.state === "queued" || m.state === "running")) {
      S.mediaT = setTimeout(() => { const c = curArt(); if (c && c.url === url) loadMedia(c, false); }, 2000);
    }
  }
  async function loadTr(it) {
    S.artTr[it.url] = { loading: true };
    refreshArt(it);
    let r;
    try { r = await api("/biz/article_tr?url=" + enc(it.url)); } catch (e) { r = { ok: false, error: "连不上后台" }; }
    S.artTr[it.url] = r && r.ok ? r : { ok: false, error: (r && r.error) || "翻译失败" };
    refreshArt(it);
  }
  function refreshArt(it) {
    const pg = S.artItems[S.readerArt];
    if (pg && pg.url === it.url && !$("bzReader").hidden) openArtPage(pg);
    const cur = S.artItems[S.artSel];
    if (cur && cur.url === it.url) renderReadP();
  }
  const curArt = () => S.artItems[!$("bzReader").hidden && S.readerArt ? S.readerArt : S.artSel];
  function markRead(id) {
    if (S.read.has(id)) return;
    S.read.add(id);
    const arr = Array.from(S.read);
    if (arr.length > 4000) S.read = new Set(arr.slice(-3000));
    store.set("read", Array.from(S.read));
    root.querySelectorAll('.bz-item[data-row="' + CSS.escape(id) + '"]').forEach((e) => {
      e.classList.add("read"); e.classList.remove("fresh");
      const n = e.querySelector(".bz-new"); if (n) n.remove();
    });
  }
  function openArt(id, inFeed) {
    const it = S.artItems[id];
    if (!it) return;
    markRead(id);
    if (!inFeed) { S.readerArt = id; openArtPage(it); loadArt(it); return; }
    S.artSel = id;
    root.querySelectorAll("#bzFeed .bz-item").forEach((e) => {
      const on = e.dataset.row === id;
      e.classList.toggle("sel", on);
      const b = e.querySelector(".bz-art-t");
      if (b) { if (on) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current"); }
    });
    renderReadP();
    const row = root.querySelector('#bzFeed .bz-item[data-row="' + CSS.escape(id) + '"]');
    if (row) row.scrollIntoView({ block: "nearest" });
    loadArt(it);
  }
  function openArtPage(it) {                 // 不在新闻列表里（行业地图、爬虫管理）点的：用整页阅读
    const ti = readTitle(it), a = S.art[it.url] || {};
    openReader(ti.main, readMetaHTML(it) + (a.foreign ? '<button type="button" class="bz-link" data-act="art-lang" data-v="' + (S.artLang === "zh" ? "orig" : "zh") + '">' + (S.artLang === "zh" ? "看原文" : "看中文") + "</button>" : ""),
      (ti.orig ? '<p class="bz-rp-orig">' + esc(ti.orig) + "</p>" : "") + readLinksHTML(it) + '<div class="bz-art-body">' + readBodyHTML(it) + "</div>", "");
  }
  function repRow(r) {
    return '<button type="button" class="bz-rep" data-rep="' + esc(r.id) + '"><span class="bz-rep-top"><span class="bz-kind k-' + esc(r.kind) + '">' +
      esc(KIND[r.kind] || r.kind) + '</span><span class="bz-rep-time">' + esc(fmtTime(r.created)) + "</span></span>" +
      '<span class="bz-rep-t">' + esc(r.title) + "</span>" + (r.summary ? '<span class="bz-rep-s">' + esc(r.summary) + "</span>" : "") + "</button>";
  }
  function renderRepList(elId, kind, emptyText, n) {
    const el = $(elId);
    if (!el) return;
    const list = S.reports.filter((r) => r.kind === kind).slice(0, n || 8);
    el.innerHTML = list.length ? list.map(repRow).join("") : empty(emptyText);
  }
  function autoText(r) {
    if (!r) return "";
    if (!r.auto) return "自动更新已关，要更新时点「现在更新」";
    const ev = r.every >= 60 ? (r.every / 60).toFixed(1).replace(/\.0$/, "") + " 小时" : r.every + " 分钟";
    return "每 " + ev + "自动更新一次" + (r.next_run ? "，下一次在 " + until(r.next_run) : "");
  }
  function stripHTML(withBtn) {
    const r = S.radar;
    if (!r) return "<span>爬虫：正在读取…</span>";
    if (r.running) {
      const pct = r.total ? Math.round((r.done / r.total) * 100) : 0;
      return '<span class="bz-prog sm" aria-hidden="true"><i style="width:' + pct + '%"></i></span><span>正在更新' + (r.resumes ? "（接着上次）" : "") + "：" + r.done + " / " + r.total +
        " 个信息源，这一轮新抓到 " + r.new + " 条</span>" + '<button type="button" class="bz-link" data-act="upd-open">看进度</button>';
    }
    if (r.resume) {                                         // v177：上次没扫完
      const z = r.resume;
      return "<span>上次扫描没扫完：扫到 " + z.done + " / " + z.total + " 个信息源就停了" + (z.new ? "（已经新抓到 " + z.new + " 条）" : "") + "。点「接着扫」把剩下的 " + z.left + " 个扫完，不用从头来。</span>" +
        '<button type="button" class="bz-link" data-act="rd-run">接着扫</button>';
    }
    const txt = r.last_run ? "爬虫盯着 " + r.enabled + " 个信息源，" + ago(r.last_run) + "更新过；最近 24 小时抓到 " + r.items_24h + " 条。" + (r.archive && r.archive.n ? "存档库里另有 " + r.archive.n + " 条（" + r.archive.files + " 个存档库）。" : "") + autoText(r) + "。"
      : "爬虫还没抓过：打开软件两三分钟后会自动抓第一轮，也可以点「现在更新」马上抓。";
    return "<span>" + esc(txt) + "</span>" + (withBtn ? '<button type="button" class="bz-link" data-act="upd-open">现在更新</button>' : "");
  }
  function renderStrips() {
    const r = $("bzStripR");
    if (r) r.innerHTML = stripHTML(false);
    const i = $("bzStripI");
    if (i) { i.hidden = S.lens !== "market"; if (!i.hidden) i.innerHTML = stripHTML(true); }
    renderBigBtns();
    renderRadBar();
  }
  function lensVis() {
    segSync("lens", S.lens);
    segSync("mdays", String(S.mdays));
    const m = S.lens === "market";
    root.querySelectorAll('.bz-pane[data-pane="industry"] .bz-seg[data-seg="mdays"]').forEach((e) => { e.hidden = !m; });
    renderStrips();
  }

  // ───────── 市场雷达 ─────────
  function renderRadarPane() {
    segSync("mdays", String(S.mdays));
    segSync("rgrp", S.rgrp);
    applyRview();
    renderStrips();
    $("bzGuide").hidden = !!store.get("guideHidden", false);
    const ov = S.ovm;
    renderRepList("bzBriefs", "market", "还没有简报。点上面的「生成简报」。", 4);
    if (!ov) {
      $("bzRising").innerHTML = empty(S.ovmErr ? "读不到：" + esc(S.ovmErr) : "正在读爬虫抓到的新闻…");
      $("bzHot").innerHTML = ""; $("bzRisingHint").textContent = ""; $("bzCounts").textContent = "";
      renderFeed();
      return;
    }
    const d = S.mdays, win = d === 1 || d === -1 ? "最近 6 小时" : "最近 24 小时";
    $("bzRisingHint").textContent = "按爬虫抓到的新闻算：" + win + "提到它的比例，明显高于" + winText().replace(/^最近 /, "这 ") + "的平均。点一下只看相关新闻。";
    const none = !(ov.counts && ov.counts.radar);
    $("bzRising").innerHTML = none ? empty("爬虫还没抓到东西。")
      : (ov.rising.length ? ov.rising.slice(0, 10).map((x) =>
        '<button type="button" class="bz-term" data-term="' + esc(x.k) + '" title="' + esc(win + " " + x.r + " 条，这段时间一共 " + x.n + " 条，来自 " + x.src + " 个信息源") + '">' +
        '<span class="k">' + esc(x.k) + '</span><span class="bar"><i style="width:' + Math.max(6, Math.round((x.r / x.n) * 100)) + '%"></i></span>' +
        '<span class="n">' + x.r + "<small> / " + x.n + "</small></span></button>").join("")
        : empty("还看不出哪个话题在升温：这段时间的新闻太少，或者都差不多。"));
    $("bzHot").innerHTML = ov.hot.length ? ov.hot.slice(0, 18).map((x) => '<button type="button" class="bz-chip" data-term="' + esc(x.k) + '">' + esc(x.k) + " <b>" + x.n + "</b></button>").join("")
      : empty("这段时间还没抓到新闻。");
    const c = ov.counts;
    $("bzCounts").textContent = "这段时间抓到 " + c.window + " 条（最近 24 小时 " + c.today + " 条），归到行业或赛道的 " + c.classified + " 条；爬虫一共存着 " + c.radar + " 条。";
    renderFeed();
  }
  function renderFeed() {
    const f = $("bzFeedFilter");
    f.hidden = !S.rq;
    f.innerHTML = S.rq ? "只看提到「" + esc(S.rq) + "」的 " + '<button type="button" class="bz-link" data-act="clearq">看全部</button>' : "";
    if (S.rind) {                               // v165：从雷达点进来的，只看某个行业
      f.hidden = false;
      f.innerHTML = "只看「" + esc(nameOf(S.rind)) + "」的新闻" + (S.rq ? "、提到「" + esc(S.rq) + "」的" : "") +
        ' <button type="button" class="bz-link" data-act="rad-back">回到雷达</button> <button type="button" class="bz-link" data-act="clearind">看全部新闻</button>';
    }
    if (S.rsince) {
      f.hidden = false;
      f.innerHTML = "只看最近一轮更新新抓到的" + (S.rq ? "、提到「" + esc(S.rq) + "」的" : "") + ' <button type="button" class="bz-link" data-act="clearsince">看全部</button>';
    }
    const el = $("bzFeed");
    if (!S.rfeed) { el.innerHTML = loading(); $("bzPager").hidden = true; return; }
    const noData = S.ovm && S.ovm.counts && !S.ovm.counts.radar;
    el.innerHTML = S.rfeed.length ? S.rfeed.map(itemRow).join("")
      : (noData ? empty('爬虫还没抓到东西。点上面的<button type="button" class="bz-link" data-act="upd-open">现在更新</button>马上抓一次。')
        : empty("这段时间没有符合的新闻。"));
    renderPager();
  }
  function renderPager() {
    const el = $("bzPager"), n = S.rtotal, size = S.rsize, pages = Math.max(1, Math.ceil(n / size)), cur = Math.min(S.rpage, pages);
    el.hidden = !n;
    if (!n) return;
    const nums = [];
    const add = (p) => nums.push('<button type="button" class="bz-pg' + (p === cur ? " on" : "") + '" data-page="' + p + '"' + (p === cur ? ' aria-current="page"' : "") + ">" + p + "</button>");
    const lo = Math.max(2, cur - 2), hi = Math.min(pages - 1, cur + 2);
    add(1);
    if (lo > 2) nums.push('<span class="bz-pg-gap">…</span>');
    for (let p = lo; p <= hi; p++) add(p);
    if (hi < pages - 1) nums.push('<span class="bz-pg-gap">…</span>');
    if (pages > 1) add(pages);
    const from = (cur - 1) * size + 1, to = Math.min(n, cur * size);
    el.innerHTML = '<span class="bz-pg-info">共 ' + n + " 条 · 第 " + from + "–" + to + " 条</span>" +
      '<span class="bz-pg-nums"><button type="button" class="bz-pg nav" data-page="' + (cur - 1) + '"' + (cur <= 1 ? " disabled" : "") + ">上一页</button>" + nums.join("") +
      '<button type="button" class="bz-pg nav" data-page="' + (cur + 1) + '"' + (cur >= pages ? " disabled" : "") + ">下一页</button></span>" +
      '<label class="bz-pg-size">每页 <select class="bz-select sm" id="bzPgSize">' + [20, 50, 100].map((v) => '<option value="' + v + '"' + (v === size ? " selected" : "") + ">" + v + "</option>").join("") + "</select> 条</label>";
  }
  async function loadRadarFeed(keepPage) {
    if (!keepPage) S.rpage = 1;
    const seq = ++S.rseq;
    S.rfeed = null; renderFeed();
    let r = null;
    try {
      r = await api("/biz/items?lens=market&days=" + S.mdays + "&grp=" + enc(S.rgrp === "all" ? "" : S.rgrp) + "&q=" + enc(S.rq) +
        "&limit=" + S.rsize + "&offset=" + (S.rpage - 1) * S.rsize + (S.rsince ? "&since=" + S.rsince : "") +
        (S.rind ? (S.rind.startsWith("t:") ? "&trk=" : "&ind=") + enc(S.rind) : ""));
    } catch (e) {}
    if (seq !== S.rseq) return;
    S.rfeed = (r && r.items) || [];
    S.rtotal = (r && r.total) || 0;
    translateTitles(S.rfeed);
    if (!S.rfeed.length && S.rtotal && S.rpage > 1) { S.rpage = Math.ceil(S.rtotal / S.rsize); return loadRadarFeed(true); }
    renderFeed();
    renderBigBtns();
  }
  function goPage(p) {
    const pages = Math.max(1, Math.ceil(S.rtotal / S.rsize));
    p = Math.max(1, Math.min(pages, p));
    if (p === S.rpage) return;
    S.rpage = p;
    loadRadarFeed(true);
    const card = $("bzFeedCard");
    if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  // ───────── 行业地图 ─────────
  function tile(id) {
    const d = S.byId[id];
    if (!d) return "";
    const h = heatOf(id), m = S.lens === "market";
    const mine = heatIn(S.ov, id);
    const gap = m && h[0] >= 3 && S.ov && !mine[0];
    const tip = d.name + "：" + d.desc + (d.co ? "\n代表企业：" + d.co : "") +
      (m ? "\n" + winText() + "的市场新闻：" + (h[0] || 0) + " 条（最近 24 小时 " + (h[1] || 0) + " 条）" +
        (S.ov ? "\n你收进来的相关内容：" + (mine[0] || 0) + " 条" : "")
        : "\n你收进来的相关内容：" + (h[0] || 0) + " 条");
    const mx = (S.mapMax && S.mapMax[d.type]) || 0;
    const lv = !h[0] ? 0 : !mx ? lvl(h[0]) : ((r) => (r < 0.2 ? 1 : r < 0.4 ? 2 : r < 0.6 ? 3 : r < 0.8 ? 4 : 5))(Math.sqrt(h[0] / mx));   // v183：深浅按这一屏里最多的那个分
    return '<button type="button" class="bz-tile' + (d.type === "l3" ? " l3" : d.type === "l2" ? " l2" : "") + (S.gotUntil && S.gotUntil[id] > Date.now() ? " got" : "") + " h" + lv + (S.indSel === id ? " sel" : "") + (matchQ(d) ? "" : " dim") +
      '" style="--c:' + colorOf(id) + '" data-ind="' + esc(id) + '" title="' + esc(tip) + '"><span class="nm">' + esc(d.name) + "</span>" +
      (h[0] ? '<span class="ct">' + h[0] + (m && show24() && h[1] && d.type !== "l3" ? '<small> 24 小时 +' + h[1] + "</small>" : "") + "</span>" : "") +
      (gap ? '<i class="gap" aria-hidden="true"></i>' : "") + "</button>";
  }
  // v184：不同板块不同颜色（和市场雷达的饼一样）；每个板块里新闻多的排前面
  function cntOf(id) { return heatOf(id)[0] || 0; }
  function byCnt(a, b) { return cntOf(b) - cntOf(a) || String(nameOf(a)).localeCompare(String(nameOf(b)), "zh"); }
  function secTotal(sec) { return sec.l1.reduce((a, n) => a + cntOf(n), 0); }
  function secsSorted() { return S.tax.sectors.slice().sort((a, b) => secTotal(b) - secTotal(a)); }   // v186：新闻多、热门的板块放前面
  function colorOf(id) {
    const d = S.byId[id];
    if (!d) return "#888";
    if (d.type === "trk") { const g = TRK_GROUPS.find((x) => x[2].includes(id)); return g ? g[1] : "#9a8a6a"; }
    return RAD_SEC[secName(d.sec)] || "#888";
  }
  function mapHTML() {
    const mx = { trk: 0, l2: 0, l3: 0 };                       // v183：每种格子里最多的是多少（分深浅用）
    Object.values(S.byId).forEach((d) => { if (mx[d.type] != null) mx[d.type] = Math.max(mx[d.type], heatOf(d.id)[0] || 0); });
    S.mapMax = mx;
    const l2b = (x) => {                                         // 一个二级行业：它的格子 + 下面的三级细分小格子
      const d2 = S.byId[x], kids = (d2 && d2.l3) || [];
      return '<div class="bz-l2b">' + tile(x) + (kids.length >= 2 ? '<div class="bz-l3s">' + kids.slice().sort(byCnt).map((y) => tile(y)).join("") + "</div>" : "") + "</div>";
    };
    let html = '<section class="bz-band trk"><header><h4>新兴赛道</h4><span>横跨好几个行业的热门方向</span></header><div class="bz-tiles">' +
      S.tax.tracks.map((t) => t.id).sort(byCnt).map((x) => tile(x)).join("") + "</div></section>";
    secsSorted().forEach((sec) => {
      html += '<section class="bz-band" style="--c:' + (RAD_SEC[sec.name] || "#888") + '"><header><h4>' + esc(sec.name) + "</h4>" +
        (secTotal(sec) ? '<em class="bz-band-n">' + secTotal(sec) + " 条</em>" : "") + "<span>" + esc(sec.desc) + '</span></header><div class="bz-l1s">' +
        sec.l1.slice().sort(byCnt).map((n) => {
          const d = S.byId[n], h = heatOf(n);
          const hit = matchQ(d) || d.subs.some((x) => matchQ(S.byId[x]) || (S.byId[x].l3 || []).some((y) => matchQ(S.byId[y])));
          const w = d.subs.reduce((a, x) => a + 1 + ((S.byId[x].l3 || []).length >= 2 ? S.byId[x].l3.length * 0.5 : 0), 0);
          return '<div class="bz-l1' + (hit ? "" : " dim") + '" style="flex-grow:' + Math.round(w) + ";--c:" + colorOf(n) + '"><button type="button" class="bz-l1-h' + (S.indSel === n ? " sel" : "") +
            '" data-ind="' + esc(n) + '" title="' + esc(d.name + "：" + d.desc) + '"><span>' + esc(n) + "</span>" + (h[0] ? "<em>" + h[0] + "</em>" : "") + "</button>" +
            '<div class="bz-tiles">' + d.subs.slice().sort(byCnt).map(l2b).join("") + "</div></div>";
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
    const trs = S.tax.tracks.filter((t) => matchQ(S.byId[t.id])).sort((a, b) => byCnt(a.id, b.id));
    if (trs.length) html += '<section class="bz-lsec"><h4>新兴赛道</h4><table class="bz-ltab">' + head + "<tbody>" + trs.map((t) => lrow(t.id)).join("") + "</tbody></table></section>";
    secsSorted().forEach((sec) => {
      const l1s = sec.l1.map((n) => S.byId[n]).filter((d) => matchQ(d) || d.subs.some((x) => matchQ(S.byId[x]))).sort((a, b) => byCnt(a.id, b.id));
      if (!l1s.length) return;
      html += '<section class="bz-lsec"><h4>' + esc(sec.name) + "</h4>" + l1s.map((d) => {
        const subs = d.subs.filter((x) => matchQ(d) || matchQ(S.byId[x])).sort(byCnt);
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
    lensVis();
    $("bzLegendTxt").textContent = S.lens === "market"
      ? "不同板块用不同颜色（和市场雷达的饼一样）；同一种颜色越深，" + winText() + "市场上的相关新闻越多，多的排在前面；带小圆点的是你还没关注的。" + dataStamp()
      : "不同板块用不同颜色；颜色越深，你收进来的相关内容越多，多的排在前面";
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
    const wrap = el && el.closest(".bz-ind");
    if (!d || !["l1", "l2", "l3", "trk"].includes(d.type)) {           // v183：没点格子的时候，右边这一栏不出来
      el.hidden = true; el.innerHTML = "";
      if (wrap) wrap.classList.add("nodet");
      return;
    }
    el.hidden = false;
    if (wrap) wrap.classList.remove("nodet");
    if (false) {
      const hotL2 = S.ov ? Object.keys(S.ov.heat).filter((k) => S.byId[k]).sort((a, b) => S.ov.heat[b][0] - S.ov.heat[a][0]).slice(0, 8) : [];
      el.innerHTML = '<div class="bz-dt"><h3>选一个行业</h3><p class="bz-dim">点地图上的任意一格（或列表里的名字），右边会显示这个行业做什么、代表企业、你收进来的相关内容，还能让小助联网研究它、分析它的趋势和机会。</p>' +
        (hotL2.length ? '<h4>你最常看的</h4><div class="bz-chips">' + hotL2.map((k) => '<button type="button" class="bz-chip" data-ind="' + esc(k) + '">' + esc(nameOf(k)) + " <b>" + S.ov.heat[k][0] + "</b></button>").join("") + "</div>" : "") + "</div>";
      return;
    }
    const h = heatOf(d.id);
    const path = d.type === "l3" ? secName(d.sec) + " › " + d.l1 + " › " + nameOf(d.l2) : d.type === "l2" ? secName(d.sec) + " › " + d.l1 : d.type === "l1" ? secName(d.sec) + "板块" : "新兴赛道";
    let rel = [];
    if (d.type === "l1") rel = d.subs;
    else if (d.type === "trk") rel = d.rel || [];
    else if (d.type === "l3") rel = (S.byId[d.l2].l3 || []).filter((x) => x !== d.id);
    else rel = (d.l3 || []).length >= 2 ? d.l3 : relatedTracks(d.id);
    const relT = d.type === "l1" ? "下面的二级行业" : d.type === "trk" ? "主要涉及的行业" : d.type === "l3" ? "同一个二级行业里的其他细分" : (d.l3 || []).length >= 2 ? "下面的三级细分" : "相关的新兴赛道";
    const items = S.indItems && S.indItems._id === d.id + "|" + S.lens ? S.indItems : null;
    const m = S.lens === "market", mine = heatIn(S.ov, d.id), mkt = heatIn(S.ovm, d.id);
    const win = winText();
    const stat = m
      ? '<p class="bz-dt-stat"><b>' + (h[0] || 0) + "</b> 条市场新闻（" + win + "）" + (h[1] && S.mdays !== 1 ? "，最近 24 小时 " + h[1] + " 条" : "") + "</p>" +
        '<p class="bz-dim">' + (S.ov ? (mine[0] ? "你收进来的相关内容 " + mine[0] + " 条" : "你收进来的内容里还没有它" + (h[0] >= 3 ? "，市场上却有动静：可能是个盲区" : "")) : "") + "</p>"
      : '<p class="bz-dt-stat"><b>' + (h[0] || 0) + "</b> 条相关内容" + (S.days && h[1] ? "，最近 " + S.days + " 天 " + h[1] + " 条" : "") + "</p>" +
        (S.ovm ? '<p class="bz-dim">市场上最近 ' + win + "的相关新闻 " + (mkt[0] || 0) + " 条</p>" : "");
    const reps = S.reports.filter((r) => r.target === d.id || r.scope === d.id).slice(0, 5);
    el.innerHTML = '<div class="bz-dt">' +
      '<div class="bz-dt-top"><p class="bz-dt-path">' + esc(path) + '</p><button type="button" class="bz-x" data-act="ind-close" aria-label="关掉这一栏（Esc）" title="关掉（Esc）">×</button></div>' +
      "<h3>" + esc(d.name) + "</h3><p>" + esc(d.desc) + "</p>" +
      (d.co ? '<p class="bz-dt-co"><span>代表企业（举例）</span>' + esc(d.co) + "</p>" : "") +
      stat +
      '<div class="bz-btns">' +
        '<button type="button" class="bz-btn" data-act="ind-research">联网研究这个行业</button>' +
        '<button type="button" class="bz-btn ghost" data-act="ind-trend">分析趋势和机会</button>' +
        '<a class="bz-btn ghost" href="https://www.baidu.com/s?wd=' + enc(searchWords(d.id)) + '" target="_blank" rel="noopener">网上查看</a>' +
      "</div>" +
      '<button type="button" class="bz-link" data-act="ind-watch">让爬虫盯着它（加进爬虫清单）</button>' +
      (rel.length ? "<h4>" + relT + '</h4><div class="bz-chips">' + rel.filter((x) => S.byId[x]).map((x) => '<button type="button" class="bz-chip" data-ind="' + esc(x) + '">' + esc(nameOf(x)) + (heatOf(x)[0] ? " <b>" + heatOf(x)[0] + "</b>" : "") + "</button>").join("") + "</div>" : "") +
      (items && items.top_kw && items.top_kw.length ? '<h4>相关内容里提得多的</h4><div class="bz-chips">' + items.top_kw.slice(0, 12).map((k) => '<span class="bz-chip static">' + esc(k) + "</span>").join("") + "</div>" : "") +
      (reps.length ? '<h4>这个行业的报告</h4><div class="bz-reps">' + reps.map(repRow).join("") + "</div>" : "") +
      "<h4>" + (m ? "市场新闻" : "相关内容") + (items ? "（" + items.total + "）" : "") + "</h4>" +
      (m && items && items.total < (h[0] || 0) ? '<p class="bz-hint">统计是 ' + h[0] + " 条；这里列的是还存着的 " + items.total + " 条，更早的新闻腾出了位置，只留了统计。</p>" : "") +
      '<div class="bz-feed compact">' +
      (items ? (items.items.length ? items.items.map(itemRow).join("") : empty(m ? "市场雷达这段时间还没抓到它的新闻。可以在「市场雷达」里加这个行业的信息源或关键词。" : "你收进来的内容里还没有和它相关的。可以点「联网研究这个行业」，让小助上网查。")) : loading()) +
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
      const lens = S.lens;
      const r = await api("/biz/items?" + (d.type === "trk" ? "trk=" : "ind=") + enc(id) + "&limit=40&lens=" + lens + (lens === "market" ? "&days=" + S.mdays : ""));
      r._id = id + "|" + lens;
      if (S.indSel === id && S.lens === lens) { S.indItems = r; renderIndDetail(); }
    } catch (e) { /* 读不到就算了 */ }
  }

  // ───────── 研究分析 ─────────
  function taskFormHTML(t) {
    const depth = seg("depth", [["quick", "快速"], ["deep", "深入"]]);
    const scope = '<select class="bz-select" id="bzTaskScope" aria-label="范围">' + scopeOptions(store.get("taskScope", "")) + "</select>";
    if (t === "model") {
      return '<p class="bz-tdesc">会拆：客户、价值、收入、成本、上下游产业链（画成图）、护城河、可借鉴的地方。</p>' +
        '<div class="bz-form"><input class="bz-input big" id="bzTaskTarget" maxlength="60" placeholder="公司、产品或生意：比如 蜜雪冰城、胖东来、一家社区面包店" aria-label="要拆解的公司、产品或生意">' +
        depth + '<label class="bz-chk"><input type="checkbox" id="bzTaskWeb" checked>联网查资料</label><button type="button" class="bz-btn" id="bzTaskRun">开始拆解</button></div>' +
        '<div class="bz-eg">试试：' + EG_MODEL.map((x) => '<button type="button" class="bz-link" data-fill="' + esc(x) + '">' + esc(x) + "</button>").join("") + "</div>";
    }
    if (t === "research") {
      return '<p class="bz-tdesc">会写：现状、产业链、主要玩家、商业模式、趋势、机会、风险。小助会自己上网搜、读网页。</p>' +
        '<div class="bz-form"><input class="bz-input big" id="bzTaskTarget" maxlength="60" placeholder="课题：比如 低空经济、AI 一人公司、宠物殡葬" aria-label="研究课题">' +
        depth + '<button type="button" class="bz-btn" id="bzTaskRun">开始研究</button><button type="button" class="bz-link" id="bzTaskSave">存成常用课题</button></div>' +
        '<div class="bz-eg" id="bzTopics"></div>';
    }
    if (t === "trend") {
      return '<p class="bz-tdesc">会写：现在的格局、未来 1～3 年的趋势（每条带依据和确定性）、普通人能动手的机会、不建议碰的方向。找到的机会会放进「机会看板」。</p>' +
        '<div class="bz-form">' + scope + '<label class="bz-chk"><input type="checkbox" id="bzTaskWeb" checked>联网补充</label><button type="button" class="bz-btn" id="bzTaskRun">开始分析</button></div>';
    }
    return '<p class="bz-tdesc">把爬虫这段时间抓到的新闻整理成一份简报：本期要点、主要动向、值得注意的信号、机会、风险。</p>' +
      '<div class="bz-form">' + scope + MDAYS_SEG() + '<label class="bz-chk"><input type="checkbox" id="bzTaskWeb">联网补充</label><button type="button" class="bz-btn" id="bzTaskRun">生成简报</button></div>';
  }
  function renderTopics() {
    const tp = $("bzTopics");
    if (!tp) return;
    tp.innerHTML = S.topics.length
      ? "常用课题：" + S.topics.map((t) => '<span class="bz-topic"><button type="button" class="bz-link" data-fill="' + esc(t) + '">' + esc(t) + '</button><button type="button" class="bz-x" data-topic-del="' + esc(t) + '" aria-label="删掉常用课题 ' + esc(t) + '">×</button></span>').join("")
      : "试试：" + EG_RESEARCH.map((t) => '<button type="button" class="bz-link" data-fill="' + esc(t) + '">' + esc(t) + "</button>").join("");
  }
  function renderCases() {
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
      el.innerHTML = '<p class="bz-hint">' + esc(m ? m.name + "：" + m.desc : "") + "</p>" + (S.mdCases.length ? S.mdCases.map(itemRow).join("") : empty("你的笔记里还没有讲这种模式的。"));
    }
  }
  const renderModel = renderCases;
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
  function renderAnalysis() {
    root.querySelectorAll(".bz-task").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.task === S.task)));
    const form = $("bzTaskForm");
    const sig = S.task + "|" + (S.tax ? 1 : 0);
    if (form.dataset.sig !== sig) {
      const keep = $("bzTaskTarget") && form.dataset.sig && form.dataset.sig.split("|")[0] === S.task ? $("bzTaskTarget").value : "";
      form.innerHTML = taskFormHTML(S.task);
      form.dataset.sig = sig;
      if (keep && $("bzTaskTarget")) $("bzTaskTarget").value = keep;
    }
    segSync("depth", S.depth);
    segSync("mdays", String(S.mdays));
    renderTopics();
    segSync("repkind", S.repKind);
    const q = S.repQ.trim().toLowerCase();
    const list = S.reports.filter((r) => (S.repKind === "all" || r.kind === S.repKind) && (!q || (r.title + " " + (r.summary || "")).toLowerCase().includes(q)));
    $("bzReports").innerHTML = list.length ? list.map(repRow).join("")
      : empty(S.reports.length ? "没有符合的报告。" : "报告库还是空的。在上面挑一件事开始，或者在「行业地图」里点一个行业让小助联网研究。");
    renderCases();
  }

  // ───────── 机会看板 ─────────
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
    if (!list) { el.innerHTML = loading(); return; }
    const show = list.filter((o) => S.oppSt === "all" || o.status === S.oppSt);
    el.innerHTML = show.length ? show.map(oppCard).join("")
      : empty(list.length ? "这一栏还没有。" : "看板还是空的。点上面的「去找新机会」，让小助分析一个行业的趋势和机会；也可以「记下我的点子」。");
  }

  // ───────── v187：商业定制——你的情况 × 市场雷达 → 适合你的行业和赚钱的做法 ─────────
  const CU_SEL = {
    status: [["", "请选择"], ["job", "上班，想做副业"], ["free", "自由职业、接活"], ["switch", "没在上班，想换个行当"], ["boss", "已经在做生意"], ["retired", "退休了"], ["student", "还在上学"]],
    money: [["", "不确定"], ["1", "1 万以内"], ["5", "1～5 万"], ["20", "5～20 万"], ["50", "20～50 万"], ["100", "50～100 万"], ["999", "100 万以上"]],
    time: [["", "不确定"], ["side", "每周 10 小时以内"], ["part", "每周 10～30 小时"], ["full", "全职投入"]],
    risk: [["", "不确定"], ["safe", "不能亏，要稳"], ["mid", "亏一部分能接受"], ["bold", "全亏了也不影响生活"]],
    goal: [["", "不确定"], ["extra", "每月多赚几千"], ["replace", "替代工资（月入 1～3 万）"], ["big", "做成一门生意、开公司"]],
  };
  const CU_TR = { up: "升温", down: "降温" };
  // v188：每一栏要填字的地方都有一个选项面板（选项从后台 /biz/fit_options 来，和配对表放在一起），可以展开看全部、收起只看常用的
  const cuF = (key, label, ctrl, cls) => '<div class="bz-cu-f' + (cls ? " " + cls : "") + '" data-cu-f="' + key + '"><div class="bz-cu-fh"><label for="bzCu-' + key + '">' + label + "</label>" +
    '<span class="bz-cu-cnt" data-cu-cnt="' + key + '"></span><button type="button" class="bz-cu-open" data-cu-open="' + key + '" aria-expanded="false" hidden></button></div>' +
    ctrl + '<div class="bz-cu-pick" data-cu-pick="' + key + '"></div></div>';
  const cuIn = (key, ph, max, num) => '<input class="bz-input" id="bzCu-' + key + '" data-cu="' + key + '"' +
    (num ? ' type="number" min="14" max="99" inputmode="numeric"' : ' maxlength="' + max + '"') + ' placeholder="' + esc(ph) + '">';
  const cuTa = (key, ph, max, rows) => '<textarea class="bz-input" id="bzCu-' + key + '" data-cu="' + key + '" rows="' + rows + '" maxlength="' + max + '" placeholder="' + esc(ph) + '"></textarea>';
  const cuSel = (key) => '<select class="bz-select" id="bzCu-' + key + '" data-cu="' + key + '">' + CU_SEL[key].map(([v, t]) => '<option value="' + v + '">' + esc(t) + "</option>").join("") + "</select>";
  const cuSplit = (v) => String(v || "").split(/[、，,；;\n]+/).map((s) => s.trim()).filter(Boolean);

  function cuPaneHTML() {
    return '<div class="bz-pane" data-pane="custom">' +
      '<section class="bz-hero bz-cu-hero"><h2>商业定制</h2><p>写下你的情况，小助拿它去对照市场雷达里每个行业的热度和机会看板，马上配出适合你的方向；' +
        "再让 AI 上网查资料，帮你定一个行业和赚钱的做法，写成一份能照着做的方案。</p></section>" +
      '<div class="bz-cu">' +
        '<form class="bz-card bz-cu-form" id="bzCuForm" autocomplete="off" novalidate>' +
          '<div class="bz-card-h"><h3>我的情况</h3><span class="bz-dim" id="bzCuSaved" aria-live="polite"></span></div>' +
          '<p class="bz-hint">写得越具体，配得越准。每一栏都可以点右上角从列表里选，没有的自己写。填的内容只存在你自己的电脑上，改完会自动保存。</p>' +
          '<div class="bz-cu-grid">' +
            cuF("age", "年龄", cuIn("age", "比如 35", 2, true)) + cuF("city", "所在城市", cuIn("city", "比如 广州", 20)) +
            cuF("status", "现在的状态", cuSel("status"), "w2") +
            cuF("exp", "阅历", cuTa("exp", "做过什么工作、在什么行业待了几年、管过人没有、做过什么生意。不知道怎么写，点右上角「帮我写」从列表里选", 800, 3), "w2") +
            cuF("skills", "技能", cuTa("skills", "会什么，用顿号隔开；也可以从下面选", 800, 2), "w2") +
            cuF("likes", "兴趣", cuTa("likes", "平时喜欢什么；也可以从下面选", 600, 2), "w2") +
            cuF("money", "能拿出来的资金", cuSel("money")) + cuF("time", "每周能投入的时间", cuSel("time")) +
            cuF("risk", "能承受的亏损", cuSel("risk")) + cuF("goal", "想要的结果", cuSel("goal")) +
            cuF("res", "手上的资源", cuTa("res", "人脉、渠道、货源、场地、粉丝、证书……没有就不填", 600, 2), "w2") +
            cuF("avoid", "不想做的", cuIn("avoid", "比如：不想露脸、不想压货、不碰加盟", 400), "w2") +
            cuF("more", "其他想让 AI 知道的", cuTa("more", "学历、家庭、身体、以后的打算……可以不填", 600, 2), "w2") +
          "</div>" +
          '<div class="bz-cu-foot"><button type="button" class="bz-btn sm" data-act="cu-save" title="马上保存，并存一份，以后能从「存过的」里找回">保存</button>' +
            '<span class="bz-cu-fst" id="bzCuFst" aria-live="polite"></span><span class="sp"></span>' +
            '<button type="button" class="bz-link" data-act="cu-saved" id="bzCuSavedBtn" aria-expanded="false">存过的</button>' +
            '<button type="button" class="bz-link danger" data-act="cu-clear">清空重填</button></div>' +
          '<div class="bz-cu-undo" id="bzCuUndo" hidden></div>' +
          '<div class="bz-cu-saved" id="bzCuSavedList" hidden></div>' +
        "</form>" +
        '<div class="bz-cu-main">' +
          '<section class="bz-card bz-cu-go" id="bzCuGo"></section>' +
          '<section class="bz-card bz-cu-plancard" id="bzCuPlans" hidden></section>' +
          '<section class="bz-card" id="bzCuPrev"><div class="bz-card-h"><h3>先配一遍</h3><span class="bz-dim" id="bzCuPrevMeta"></span></div>' +
            '<div id="bzCuPrevBody">' + loading("正在读你的情况和市场数据…") + "</div></section>" +
        "</div>" +
      "</div></div>";
  }

  // ── 表单：读、填、存 ──
  function cuRead() {
    const p = {};
    root.querySelectorAll("#bzCuForm [data-cu]").forEach((el) => { p[el.dataset.cu] = el.value.trim(); });
    return p;
  }
  function cuFill(p, onlyEmpty) {                                  // onlyEmpty：读回来之前你已经动手填了的，只补空着的格子
    root.querySelectorAll("#bzCuForm [data-cu]").forEach((el) => {
      const v = (p || {})[el.dataset.cu];
      if (onlyEmpty && el.value.trim()) return;
      el.value = v == null || v === 0 ? "" : String(v);
    });
    cuSyncChips();
    cuStat(S.cu.updated ? "上次保存：" + fmtTime(S.cu.updated) : "");
  }
  function cuStat(t) { ["bzCuSaved", "bzCuFst"].forEach((id) => { const x = $(id); if (x) x.textContent = t || ""; }); }   // v189：上面、下面都写
  // ── v188：选项面板 ──
  function cuLoadOptions() {
    if (S.cu.optLoading || S.cu.pick) return;
    S.cu.optLoading = true;
    api("/biz/fit_options").then((r) => {
      S.cu.optLoading = false;
      if (r && r.ok && r.pick) { S.cu.pick = r.pick; cuRenderPickers(); }
    }).catch(() => { S.cu.optLoading = false; });
  }
  const cuChipB = (key, w) => '<button type="button" class="bz-cu-chip" data-cu-c="' + key + '" data-w="' + esc(w) + '" aria-pressed="false">' + esc(w) + "</button>";
  function cuPickInner(key, P) {
    if (P.mode === "build") return cuBuildHTML(P);
    const top = (P.top || []).length ? '<div class="bz-cu-chips bz-cu-top" role="group" aria-label="常用的，点一下加进去">' + P.top.map((w) => cuChipB(key, w)).join("") + "</div>" : "";
    return top + '<div class="bz-cu-all" role="group" aria-label="全部选项">' + P.groups.map(([g, items]) =>
      '<div class="bz-cu-grp"><span class="bz-cu-gn">' + esc(g) + '</span><div class="bz-cu-chips">' + items.map((w) => cuChipB(key, w)).join("") + "</div></div>").join("") + "</div>";
  }
  function cuOpenLabel(P, open) {
    if (open) return "收起";
    if (P.mode === "build") return "帮我写：从列表里选";
    if (P.mode === "single") return "从列表里选";
    return "展开全部 " + P.groups.reduce((n, g) => n + g[1].length, 0) + " 个";
  }
  function cuApplyOpen(key) {                                      // 展开 / 收起：只切显示，不重画
    const P = (S.cu.pick || {})[key], f = root.querySelector('[data-cu-f="' + key + '"]');
    if (!P || !f) return;
    const open = !!S.cu.open[key], btn = f.querySelector("[data-cu-open]");
    f.classList.toggle("open", open);
    f.querySelectorAll(".bz-cu-all").forEach((e) => { e.hidden = !open; });
    f.querySelectorAll(".bz-cu-top").forEach((e) => { e.hidden = open; });
    if (btn) { btn.hidden = false; btn.textContent = cuOpenLabel(P, open); btn.setAttribute("aria-expanded", String(open)); }
  }
  function cuRenderPickers() {
    const P = S.cu.pick || {};
    Object.keys(P).forEach((key) => {
      const box = root.querySelector('[data-cu-pick="' + key + '"]');
      if (!box) return;
      box.innerHTML = cuPickInner(key, P[key]);
      cuApplyOpen(key);
    });
    cuBuildSync();
    cuSyncChips();
  }
  function cuToggleOpen(key) {
    S.cu.open[key] = !S.cu.open[key];
    store.set("cuOpen", S.cu.open);
    cuApplyOpen(key);
  }
  const cuField = (key) => root.querySelector('#bzCuForm [data-cu="' + key + '"]');
  // 阅历是一句一句的：整句加在后面（「；」隔开），已经有了就去掉
  const cuTidy = (v) => String(v || "").replace(/[；;]\s*([；;]\s*)+/g, "；").replace(/^[；;，,、\s]+|[；;，,、\s]+$/g, "");
  function cuPhrase(v, w) {
    v = String(v || "");
    if (v.includes(w)) return cuTidy(v.replace(w, ""));
    v = cuTidy(v);
    return v ? v + "；" + w : w;
  }
  function cuPick(key, w) {                                        // 点一个选项：单选的换掉；多选的加上或去掉；阅历里的整句加上或去掉
    const el = cuField(key), P = (S.cu.pick || {})[key];
    if (!el || !P) return;
    if (P.mode === "single") el.value = el.value.trim() === w ? "" : w;
    else if (P.mode === "build") el.value = cuPhrase(el.value, w);
    else {
      const parts = cuSplit(el.value), i = parts.indexOf(w);
      if (i >= 0) parts.splice(i, 1); else parts.push(w);
      el.value = parts.join("、");
    }
    cuSyncChips();
    cuQueueSave(300);
  }
  // 阅历「帮我写」：选行业、做什么、干了多久、带过人吗，拼成一句话
  function cuBuildHTML(P) {
    const chips = (k, items) => '<div class="bz-cu-chips">' + items.map((w) =>
      '<button type="button" class="bz-cu-chip" data-cu-b="' + k + '" data-w="' + esc(w) + '" aria-pressed="false">' + esc(w) + "</button>").join("") + "</div>";
    const step = (n, t, body) => '<div class="bz-cu-step"><span class="bz-cu-gn"><b>' + n + "</b>" + t + "</span>" + body + "</div>";
    return '<div class="bz-cu-all bz-cu-build" role="group" aria-label="帮我写阅历">' +
      step("1", "在什么行业", P.ind.map(([g, items]) => '<div class="bz-cu-sub"><i>' + esc(g) + "</i>" + chips("ind", items) + "</div>").join("")) +
      step("2", "做什么（可以不选）", chips("role", P.role)) +
      step("3", "干了多久", chips("years", P.years)) +
      step("4", "带过人吗", chips("lead", P.lead)) +
      '<div class="bz-cu-bl"><span class="bz-cu-bp" id="bzCuBp" aria-live="polite"></span>' +
        '<button type="button" class="bz-btn sm" data-act="cu-build-add" id="bzCuBadd">加进阅历</button></div>' +
      '<div class="bz-cu-grp"><span class="bz-cu-gn">做过的生意，点一下直接加进去</span><div class="bz-cu-chips">' + P.biz.map((w) => cuChipB("exp", w)).join("") + "</div></div>" +
      "</div>";
  }
  function cuBuildText() {
    const B = S.cu.b, P = (S.cu.pick || {}).exp;
    if (!P || (!B.ind && !B.role)) return "";
    const yrs = B.years ? (/^\d/.test(B.years) ? " " : "") + B.years : "";
    let s;
    if (B.ind) {
      s = "在" + ((P.phrase || {})[B.ind] || B.ind + "行业");
      if (B.role) s += "做" + B.role + (yrs ? "，干了" + yrs : "");
      else s += yrs ? "干了" + yrs : "工作过";
    } else s = "做过" + B.role + (yrs ? "，干了" + yrs : "");
    if (B.lead) s += "，" + B.lead;
    return s;
  }
  function cuBuildSync() {
    root.querySelectorAll("[data-cu-b]").forEach((b) => b.setAttribute("aria-pressed", String(S.cu.b[b.dataset.cuB] === b.dataset.w)));
    const t = cuBuildText(), bp = $("bzCuBp"), add = $("bzCuBadd");
    if (bp) { bp.textContent = t || "选一个行业或做过什么，这里会拼成一句话"; bp.classList.toggle("empty", !t); }
    if (add) add.disabled = !t;
  }
  function cuBuildPick(k, w) { S.cu.b[k] = S.cu.b[k] === w ? "" : w; cuBuildSync(); }
  function cuBuildAdd() {
    const t = cuBuildText(), el = cuField("exp");
    if (!t || !el) return;
    const v = cuTidy(el.value);
    el.value = v ? v + "；" + t : t;
    S.cu.b = { ind: "", role: "", years: "", lead: "" };
    cuBuildSync();
    cuSyncChips();
    cuQueueSave(300);
    toast("加进阅历了：" + t);
  }
  function cuSyncChips() {                                         // 选项的亮暗跟着框里写的走（自己打字也算）
    const vals = {}, raw = {}, P = S.cu.pick || {};
    root.querySelectorAll("#bzCuForm [data-cu]").forEach((el) => { raw[el.dataset.cu] = el.value.trim(); vals[el.dataset.cu] = cuSplit(el.value); });
    root.querySelectorAll("[data-cu-c]").forEach((b) => {
      const k = b.dataset.cuC, mode = (P[k] || {}).mode, w = b.dataset.w;
      const on = mode === "single" ? raw[k] === w : mode === "build" ? (raw[k] || "").includes(w) : (vals[k] || []).includes(w);
      b.setAttribute("aria-pressed", String(on));
    });
    root.querySelectorAll("[data-cu-cnt]").forEach((x) => {
      const k = x.dataset.cuCnt, n = (P[k] || {}).mode === "multi" ? (vals[k] || []).length : 0;
      x.textContent = n ? "写了 " + n + " 项" : "";
    });
  }
  function cuQueueSave(ms) {
    S.cu.dirty = true;
    clearTimeout(S.cu.timer);
    cuStat("正在保存…");
    S.cu.timer = setTimeout(() => { S.cu.timer = null; cuSave(); }, ms);
  }
  async function cuSave() {
    if (!S.cu.ready && !S.cu.dirty) return;                         // 存着的情况还没读回来、你也没动过：不能拿空表单去盖掉它
    const seq = ++S.cu.seq, prof = cuRead();
    let r;
    try { r = await api("/biz/fit", { profile: prof, save: true }); } catch (e) { r = { ok: false, error: "连不上后台（" + e.message + "）" }; }
    if (seq !== S.cu.seq) return;                                  // 后面又改了，以最后一次为准
    if (!r || !r.ok) { cuStat("没存上：" + ((r && r.error) || "连不上后台")); return; }
    S.cu.pv = r.preview; S.cu.updated = r.updated || S.cu.updated; S.cu.at = Date.now(); S.cu.err = "";
    cuStat("已保存 " + hhmm(r.updated || Date.now() / 1000));
    renderCuGo();
    renderCuPrev();
  }
  async function cuLoad() {
    S.cu.loaded = true;
    let r;
    try { r = await api("/biz/fit"); } catch (e) { r = { ok: false, error: "连不上后台（" + e.message + "）" }; }
    if (!r || !r.ok) { S.cu.loaded = false; S.cu.err = (r && r.error) || "读不到"; renderCuPrev(); return; }
    S.cu.err = ""; S.cu.updated = r.updated; S.cu.at = Date.now(); S.cu.saved = r.saved || [];
    const typed = S.cu.dirty;
    cuFill(r.profile, typed);
    S.cu.ready = true;
    if (typed) cuQueueSave(200);                                     // 读回来之前你已经改了：合在一起再存、再配
    else S.cu.pv = r.preview;
    renderCustom();
  }
  async function cuRefresh() {                                     // 只按表单上的情况重新配一遍（市场数据更新了），不存
    const seq = ++S.cu.seq;
    let r;
    try { r = await api("/biz/fit", { profile: cuRead(), save: false }); } catch (e) { return; }
    if (seq !== S.cu.seq || !r || !r.ok) return;
    S.cu.pv = r.preview; S.cu.at = Date.now();
    renderCuGo();
    renderCuPrev();
  }
  function cuEnsure() {                                            // 切到这一页：第一次读存着的情况；隔了一分钟以上，按表单重新配一遍（不存）
    if (!S.cu.pick) cuLoadOptions();                                // v188：选项面板（不用等配对，马上出来）
    if (!S.cu.loaded) cuLoad();
    else if (S.cu.ready && !S.cu.timer && Date.now() - (S.cu.at || 0) > 60000) cuRefresh();
  }
  function cuStart() {
    if (!S.cu.ready && !S.cu.dirty) { toast("还在读你上次填的情况，稍等一下再点。"); return; }
    clearTimeout(S.cu.timer);
    S.cu.timer = null;
    runJob("custom", { profile: cuRead(), web: S.cu.web, depth: S.cu.depth });   // 后台会顺便把这份情况存下来
  }
  function cuMap(id) {                                             // 在行业地图上看这个方向
    if (!S.byId[id]) { toast("行业地图上没有这个方向。"); return; }
    if (S.lens !== "market") { S.lens = "market"; store.set("lens", "market"); }
    S.indQ = "";
    const q = $("bzIndQ");
    if (q) q.value = "";
    goPane("industry");
    setTimeout(() => {
      selectInd(id);
      const el = root.querySelector('#bzIndMain [data-ind="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
      if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 150);
  }

  // ── 画 ──
  // ── v189：保存、存过的、清空前自动存一份、撤销清空 ──
  const cuHas = (p) => Object.values(p || {}).some((v) => String(v || "").trim());
  function renderCuSaved() {
    const btn = $("bzCuSavedBtn"), box = $("bzCuSavedList");
    if (!btn || !box) return;
    const lst = S.cu.saved || [];
    btn.textContent = "存过的" + (lst.length ? "（" + lst.length + "）" : "");
    btn.setAttribute("aria-expanded", String(!!S.cu.savedOpen));
    box.hidden = !S.cu.savedOpen;
    if (!S.cu.savedOpen) return;
    box.innerHTML = lst.length ? lst.map((x) => '<div class="bz-cu-si"><div class="bz-cu-sit"><b>' + esc(fmtTime(x.at)) + "</b>" +
        (x.auto ? "<em>" + esc(x.label || "自动存的") + "</em>" : "") + "<span>" + esc(x.brief) + "</span></div>" +
        '<button type="button" class="bz-link" data-cu-restore="' + esc(x.id) + '">用这份</button>' +
        '<button type="button" class="bz-link danger" data-cu-drop="' + esc(x.id) + '">删掉</button></div>').join("")
      : '<p class="bz-note">还没有存过。点「保存」存一份，以后不小心清空了也能从这里找回来。</p>';
  }
  async function cuSaveNow() {
    if (!S.cu.ready && !S.cu.dirty) { toast("还在读你上次填的情况，稍等一下再点。"); return; }
    const prof = cuRead();
    if (!cuHas(prof)) { toast("表格是空的，先填一点再保存。"); return; }
    clearTimeout(S.cu.timer); S.cu.timer = null;
    const seq = ++S.cu.seq;
    cuStat("正在保存…");
    let r;
    try { r = await api("/biz/fit", { action: "snapshot", profile: prof }); } catch (e) { r = { ok: false, error: "连不上后台（" + e.message + "）" }; }
    if (!r || !r.ok) { cuStat("没存上：" + ((r && r.error) || "连不上后台")); return; }
    S.cu.saved = r.saved || S.cu.saved; S.cu.updated = r.updated; S.cu.dirty = false;
    if (seq === S.cu.seq && r.preview) { S.cu.pv = r.preview; S.cu.at = Date.now(); renderCuGo(); renderCuPrev(); }
    cuStat("已保存 " + hhmm(r.updated) + "，也存了一份");
    renderCuSaved();
    toast("存好了。以后点「存过的」，随时能找回这一份。");
  }
  async function cuClear() {
    const prof = cuRead();
    if (!cuHas(prof)) { toast("表格已经是空的。"); return; }
    if (!confirm("把「我的情况」全部清空？\n清空前会自动存一份，点「撤销清空」或在「存过的」里都能找回来。")) return;
    clearTimeout(S.cu.timer); S.cu.timer = null;
    let r;
    try { r = await api("/biz/fit", { action: "snapshot", profile: prof, auto: true, label: "清空前自动存的" }); } catch (e) { r = { ok: false, error: e.message }; }
    if (!r || !r.ok || !r.id) { toast("没能先存一份，这次先不清空（" + ((r && r.error) || "连不上后台") + "）。"); return; }
    S.cu.saved = r.saved || S.cu.saved;
    S.cu.undoId = r.id;
    root.querySelectorAll("#bzCuForm [data-cu]").forEach((el) => { el.value = ""; });
    S.cu.b = { ind: "", role: "", years: "", lead: "" };
    cuBuildSync(); cuSyncChips(); cuQueueSave(50);
    renderCuSaved();
    cuShowUndo();
  }
  function cuShowUndo() {
    const u = $("bzCuUndo");
    if (!u) return;
    clearTimeout(S.cu.undoT);
    u.hidden = !S.cu.undoId;
    if (!S.cu.undoId) return;
    u.innerHTML = '<span>已经清空了，清空前的情况自动存了一份。</span><button type="button" class="bz-btn sm" data-act="cu-undo">撤销清空</button>';
    S.cu.undoT = setTimeout(() => { S.cu.undoId = ""; u.hidden = true; }, 120000);
  }
  async function cuRestore(id, done) {
    const had = cuHas(cuRead());
    clearTimeout(S.cu.timer); S.cu.timer = null;
    const seq = ++S.cu.seq;
    let r;
    try { r = await api("/biz/fit", { action: "restore", id: id }); } catch (e) { r = { ok: false, error: "连不上后台（" + e.message + "）" }; }
    if (!r || !r.ok) { toast((r && r.error) || "没换成"); return; }
    S.cu.saved = r.saved || S.cu.saved; S.cu.updated = r.updated; S.cu.dirty = false; S.cu.ready = true;
    S.cu.b = { ind: "", role: "", years: "", lead: "" };
    cuFill(r.profile);
    cuBuildSync();
    if (seq === S.cu.seq) { S.cu.pv = r.preview; S.cu.at = Date.now(); }
    cuStat("已保存 " + hhmm(r.updated));
    renderCuGo(); renderCuPrev(); renderCuSaved();
    toast(done || ("换好了。" + (had ? "换之前填的情况也自动存了一份，在「存过的」里。" : "")));
  }

  function renderCustom() {
    renderCuSaved();
    renderCuGo();
    renderCuPlans();
    renderCuPrev();
  }
  function renderCuGo() {
    const el = $("bzCuGo");
    if (!el) return;
    const pv = S.cu.pv, j = S.job, busy = !!(j && j.running), mine = busy && j.kind === "custom";
    const ok = !!(pv && pv.enough), miss = (pv && pv.missing) || [];   // 还没读到你的情况之前，按钮先不能点
    let note = "";
    if (mine) note = '<button type="button" class="bz-cu-busy cx-ail-tg" data-ail-toggle="biz">正在写：' + esc(j.stage || "…") +
      '<span class="cx-ail-caret">' + (window.cxAiLive ? window.cxAiLive.caret("biz") : "") + "</span></button>";   // v190：点它在下面展开实时画面
    else if (busy) note = '<span class="bz-warn">「' + esc(j.title) + "」还在写，等它写完再开始。</span>";
    else if (pv && !ok) note = '<span class="bz-warn">先在左边写写阅历、技能或兴趣（至少一样），才能开始。</span>';
    else if (miss.length) note = "还没填：" + esc(miss.join("、")) + "。填上会更准，不填也能写。";
    const sig = [mine ? j.stage : "", busy, ok, note, S.cu.web, S.cu.depth].join("|");
    if (el.dataset.sig === sig) return;                           // 没变就不重画（不抢焦点）
    el.dataset.sig = sig;
    el.innerHTML = '<div class="bz-cu-go-t"><h3>让 AI 给你定制方案</h3><p>按左边填的情况，用上市场雷达的数据和机会看板，再上网查资料，挑出最适合你的 3 个方向：' +
        "做什么行业、怎么赚钱、要投多少钱、前 90 天怎么做。一般要 3～8 分钟，可以先去做别的。</p></div>" +
      '<div class="bz-cu-go-b">' + seg("cudepth", [["quick", "快速"], ["deep", "深入"]]) +
        '<label class="bz-chk"><input type="checkbox" id="bzCuWeb"' + (S.cu.web ? " checked" : "") + ">联网查资料</label>" +
        '<button type="button" class="bz-btn" id="bzCuRun"' + (busy || !ok ? " disabled" : "") + ">" + (mine ? "正在写方案…" : "生成我的定制方案") + "</button></div>" +
      (note ? '<p class="bz-note bz-cu-gonote">' + note + "</p>" : "") +
      '<div class="cx-ail-slot" id="bzCuLive" hidden></div>';
    segSync("cudepth", S.cu.depth);
    bzLivePlace();
  }
  function cuPlansHTML(plans) {
    return '<div class="bz-cu-plans">' + plans.map((p, i) =>
      '<article class="bz-cu-p' + (i === 0 ? " top" : "") + '"><span class="rk">' + esc(p.rank || "方向" + (i + 1)) + (i === 0 ? " · 最推荐" : "") + "</span>" +
        "<h4>" + esc(p.ind || p.model) + "</h4>" + (p.ind && p.model ? '<p class="mdl">' + esc(p.model) + "</p>" : "") +
        (p.match != null ? '<div class="bz-cu-meter"><span>匹配度</span><i><b style="width:' + p.match + '%"></b></i><em>' + p.match + "</em></div>" : "") +
        "<dl>" + [["启动资金", p.money], ["回本", p.payback], ["风险", p.risk]].filter((x) => x[1]).map((x) =>
          "<dt>" + x[0] + "</dt><dd" + (x[0] === "风险" ? ' class="rk-' + (x[1] === "高" ? "hi" : x[1] === "低" ? "lo" : "mid") + '"' : "") + ">" + esc(x[1]) + "</dd>").join("") + "</dl>" +
        (p.why ? '<p class="why">' + esc(p.why) + "</p>" : "") + "</article>").join("") + "</div>";
  }
  function renderCuPlans() {
    const el = $("bzCuPlans");
    if (!el) return;
    const reps = S.reports.filter((r) => r.kind === "custom");
    if (!reps.length) { el.hidden = true; return; }
    el.hidden = false;
    const r = reps[0], plans = r.plans || [];
    const sig = reps.map((x) => x.id).join(",");
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    el.innerHTML = '<div class="bz-card-h"><h3>我的定制方案</h3><span class="bz-dim">' + esc(fmtTime(r.created)) + "，" + esc(r.engine || "AI") + "写的</span></div>" +
      (r.who ? '<p class="bz-note bz-cu-who">按当时的情况：' + esc(r.who) + "</p>" : "") +
      (r.summary ? '<p class="bz-cu-sum">' + esc(r.summary) + "</p>" : "") +
      (plans.length ? cuPlansHTML(plans) : '<p class="bz-hint">这份方案没按约定的格式列出方向，打开看全文。</p>') +
      '<div class="bz-btns"><button type="button" class="bz-btn sm" data-rep="' + esc(r.id) + '">打开完整方案</button>' +
        (r.opps ? '<button type="button" class="bz-btn ghost sm" data-goto="opps">方案里的 ' + r.opps + " 个机会已放进机会看板</button>" : "") + "</div>" +
      (reps.length > 1 ? '<details class="bz-cu-old"><summary>以前的方案（' + (reps.length - 1) + ' 份）</summary><div class="bz-reps">' + reps.slice(1, 13).map(repRow).join("") + "</div></details>" : "");
  }
  function cuColor(c) {
    if (c.kind === "trk") { const g = TRK_GROUPS.find((x) => x[2].includes(c.id)); return g ? g[1] : "#9a8a6a"; }
    return RAD_SEC[c.sec] || "#888888";
  }
  function cuGroup(c) {
    return c.kind === "trk" ? ((TRK_GROUPS.find((x) => x[2].includes(c.id)) || [])[0] || "新兴赛道") : c.l1;
  }
  function cuCandHTML(c, i) {
    const col = cuColor(c);
    const why = c.fill ? "你写的情况里没直接对上；它现在很热，一个人也能起步，可以看看。"
      : c.why.map((x) => esc(x[0]) + "「" + esc(x[1]) + "」").join("、");
    const mods = c.models.map((m) => '<span class="bz-cu-mod' + (m.money ? " " + m.money : "") + '" title="' + esc(m.desc) + '">' + esc(m.name) + "<small>" + esc(m.need) + "</small></span>").join("");
    const news = (c.news || []).map((it) => '<li><button type="button" class="bz-link" data-cu-art="' + esc(it.id) + '" title="' + esc(it.title) + '">' +
      esc(S.trTitle[it.title] || it.title) + "</button><span>" + esc(ago(it.ts)) + "</span></li>").join("");
    return '<article class="bz-cu-c" data-cu-id="' + esc(c.id) + '">' +
      '<span class="bz-cu-rk' + (c.fill ? " fill" : "") + '" style="' + (c.fill ? "color:" + col + ";border-color:" + col : "background:" + col) + '">' + (i + 1) + "</span>" +
      '<div class="bz-cu-cb"><header><h4>' + esc(c.name) + '</h4><span class="bz-dim">' + esc(cuGroup(c)) + "</span>" +
        (CU_TR[c.trend] ? '<span class="bz-cu-tr ' + c.trend + '" title="最近 24 小时，它在新闻里的占比比 7 天平均' + (c.trend === "up" ? "高" : "低") + '不少">' + CU_TR[c.trend] + "</span>" : "") + "</header>" +
        '<div class="bz-cu-meter"><span>跟你的匹配</span><i><b style="width:' + c.fit + "%;background:" + col + '"></b></i><em>' + (c.fill ? "没对上" : c.fit) + "</em></div>" +
        '<div class="bz-cu-meter"><span>市场热度</span><i><b class="h" style="width:' + c.heat + '%"></b></i><em>7 天 ' + c.n7 + " 条</em></div>" +
        '<p class="bz-cu-row"><b>' + (c.fill ? "为什么列它" : "对上的地方") + "</b>" + why + "</p>" +
        '<p class="bz-cu-row"><b>适合的做法</b>' + mods + (c.money_txt ? '<span class="bz-cu-money ' + c.money + '">' + esc(c.money_txt) + "</span>" : "") + "</p>" +
        (news ? '<ul class="bz-cu-news" aria-label="最近的新闻">' + news + "</ul>" : "") +
        (c.opps && c.opps.length ? '<p class="bz-cu-row"><b>机会看板</b>' + c.opps.map((o) => '<button type="button" class="bz-link" data-goto="opps">' + esc(o.title) + "</button>").join("；") + "</p>" : "") +
        '<footer><button type="button" class="bz-link" data-cu-map="' + esc(c.id) + '">在行业地图上看</button>' +
          '<button type="button" class="bz-link" data-cu-research="' + esc(c.name + (c.models[0] ? " " + c.models[0].name : "")) + '">深入研究这个方向</button></footer>' +
      "</div></article>";
  }
  let cuCanvas = null;
  function cuTextW(t, size, weight) {
    if (!cuCanvas) cuCanvas = document.createElement("canvas");
    const ctx = cuCanvas.getContext("2d");
    ctx.font = (weight || 400) + " " + size + "px " + (getComputedStyle(root).fontFamily || "sans-serif");
    return ctx.measureText(t).width;
  }
  // 横着是「跟你的匹配度」，竖着是「市场热度」（7 天新闻条数，对数刻度）：越靠右上，越是又适合你、市场又热
  function cuChartSVG(cands, W) {
    const H = 320, L = 54, R = 14, T = 12, B = 40, pw = W - L - R, ph = H - T - B, r = 11;
    const mk = (S.cu.pv && S.cu.pv.market) || {};
    const lg = (n) => Math.log10(1 + Math.max(0, n));
    const ns = cands.map((c) => c.n7);
    let hi = lg(Math.max(mk.max || 0, 9, ...ns)) + 0.06, lo = Math.max(0, lg(Math.min(...ns)) - 0.3);
    if (hi - lo < 1.2) lo = Math.max(0, hi - 1.2);
    const X = (f) => L + (pw * Math.max(0, Math.min(100, f))) / 100;
    const Y = (n) => T + ph * (1 - (lg(n) - lo) / (hi - lo));
    const midX = X(50), midY = mk.mid ? Math.max(T + 16, Math.min(T + ph - 16, Y(mk.mid))) : T + ph / 2;
    const pts = cands.map((c, i) => ({ c, i, x: X(c.fit), y: Y(c.n7), col: cuColor(c) }));
    for (let it = 0; it < 60; it++) {                             // 挤在一起的圆点互相推开一点，数字不被盖住
      let moved = false;
      for (let a = 0; a < pts.length; a++) {
        for (let b = a + 1; b < pts.length; b++) {
          const p = pts[a], q = pts[b];
          let dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy);
          if (d < 2 * r + 3) {
            if (d < 0.01) { dx = 0.6; dy = 0.8; d = 1; }
            const push = (2 * r + 3 - d) / 2 + 0.2;
            p.x -= (dx / d) * push; p.y -= (dy / d) * push; q.x += (dx / d) * push; q.y += (dy / d) * push;
            moved = true;
          }
        }
      }
      pts.forEach((p) => { p.x = Math.max(L + r + 1, Math.min(L + pw - r - 1, p.x)); p.y = Math.max(T + r + 1, Math.min(T + ph - r - 1, p.y)); });
      if (!moved) break;
    }
    const f1 = (v) => v.toFixed(1);
    const boxes = [];
    const hit = (bx) => bx.x0 < L + 1 || bx.x1 > W - 2 || bx.y0 < 1 || bx.y1 > T + ph - 1 ||
      pts.some((p) => bx.x0 < p.x + r + 2 && bx.x1 > p.x - r - 2 && bx.y0 < p.y + r + 2 && bx.y1 > p.y - r - 2) ||
      boxes.some((o) => bx.x0 < o.x1 && bx.x1 > o.x0 && bx.y0 < o.y1 && bx.y1 > o.y0);
    const caps = [];
    // 名字：先挨着圆点试右、左、上、下、四个斜角；都被占了，再往外一圈试，用一根细线连回圆点（v188）；还不行就不写（圆点里的数字对得上下面的列表）
    const near = [[r + 5, 4, "start"], [-(r + 5), 4, "end"], [0, -(r + 6), "middle"], [0, r + 15, "middle"],
      [r + 2, -(r + 3), "start"], [r + 2, r + 13, "start"], [-(r + 2), -(r + 3), "end"], [-(r + 2), r + 13, "end"]];
    const far = [[r + 30, 4, "start"], [-(r + 30), 4, "end"], [0, -(r + 26), "middle"], [0, r + 36, "middle"],
      [r + 22, -(r + 20), "start"], [r + 22, r + 30, "start"], [-(r + 22), -(r + 20), "end"], [-(r + 22), r + 30, "end"],
      [r + 52, 4, "start"], [-(r + 52), 4, "end"]];
    const labels = pts.map((p) => {
      const t = p.c.name, w = cuTextW(t, 12, 600), h = 14;
      for (const [dx, dy, anc, isFar] of near.map((x) => x.concat(false)).concat(far.map((x) => x.concat(true)))) {
        const x = p.x + dx, y = p.y + dy, x0 = anc === "start" ? x : anc === "end" ? x - w : x - w / 2;
        const bx = { x0: x0 - 1, x1: x0 + w + 1, y0: y - h + 3, y1: y + 3 };
        if (hit(bx)) continue;
        boxes.push(bx);
        let line = null;
        if (isFar) {                                                // 细线：从圆点边上连到名字最近的那一点
          const lx = Math.max(bx.x0, Math.min(bx.x1, p.x)), ly = Math.max(bx.y0, Math.min(bx.y1, p.y)), d = Math.hypot(lx - p.x, ly - p.y) || 1;
          line = [p.x + ((lx - p.x) / d) * (r + 1), p.y + ((ly - p.y) / d) * (r + 1), lx, ly];
        }
        return { x, y, anc, line };
      }
      return null;
    });
    // 角上的说明（名字先放，说明再找空地）：「又适合你、市场又热」最要紧，右上角被占了就换到这一块的其他角上
    const qh = midY - T > 34;
    [["又适合你、市场又热", "good", 600, [[W - R - 6, T + 15, "end"], [midX + 8, T + 15, "start"]].concat(qh ? [[W - R - 6, midY - 7, "end"], [midX + 8, midY - 7, "start"]] : [])],
      ["市场热，但和你沾边少", "", 400, [[L + 8, T + 15, "start"]]],
      ["适合你，市场还不太热", "", 400, [[W - R - 6, T + ph - 8, "end"]]]].forEach(([t, cls, wt, spots]) => {
      const w = cuTextW(t, 11.5, wt);
      for (const [x, y, anc] of spots) {
        const x0 = anc === "end" ? x - w : x;
        const bx = { x0: x0 - 2, x1: x0 + w + 2, y0: y - 12, y1: y + 4 };
        if (!hit(bx)) { boxes.push(bx); caps.push('<text class="cap' + (cls ? " " + cls : "") + '" x="' + f1(x) + '" y="' + f1(y) + '" text-anchor="' + anc + '">' + t + "</text>"); break; }
      }
    });
    let s = '<svg class="bz-cu-svg" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="group" aria-label="跟你的匹配度和市场热度">' +
      '<rect class="q-good" x="' + f1(midX) + '" y="' + T + '" width="' + f1(L + pw - midX) + '" height="' + f1(midY - T) + '"/>' +
      '<line class="grid" x1="' + f1(midX) + '" y1="' + T + '" x2="' + f1(midX) + '" y2="' + (T + ph) + '"/>' +
      '<line class="grid" x1="' + L + '" y1="' + f1(midY) + '" x2="' + (L + pw) + '" y2="' + f1(midY) + '"/>' +
      '<line class="axis" x1="' + L + '" y1="' + (T + ph) + '" x2="' + (L + pw) + '" y2="' + (T + ph) + '"/>' +
      '<line class="axis" x1="' + L + '" y1="' + T + '" x2="' + L + '" y2="' + (T + ph) + '"/>';
    [10, 100, 1000, 10000].filter((n) => lg(n) > lo + 0.04 && lg(n) < hi - 0.02).forEach((n) => {
      s += '<text class="tk" x="' + (L - 6) + '" y="' + f1(Y(n) + 4) + '" text-anchor="end">' + n + "</text>";
    });
    [0, 50, 100].forEach((f) => { s += '<text class="tk" x="' + f1(X(f)) + '" y="' + (T + ph + 15) + '" text-anchor="' + (f === 0 ? "start" : f === 100 ? "end" : "middle") + '">' + f + "</text>"; });
    s += '<text class="ax" x="' + f1(L + pw / 2) + '" y="' + (H - 5) + '" text-anchor="middle">跟你的匹配度（越往右越配你）</text>' +
      '<text class="ax" transform="translate(12 ' + f1(T + ph / 2) + ') rotate(-90)" text-anchor="middle">市场热度：最近 7 天新闻条数</text>' + caps.join("");
    pts.forEach((p, k) => {
      const lb = labels[k];
      s += '<g class="dot' + (p.c.fill ? " fill" : "") + '" data-cu-dot="' + esc(p.c.id) + '" tabindex="0" role="button" aria-label="' +
        esc(k + 1 + "，" + p.c.name + "，匹配度 " + p.c.fit + "，最近 7 天 " + p.c.n7 + " 条新闻") + '">' +
        '<circle cx="' + f1(p.x) + '" cy="' + f1(p.y) + '" r="' + r + '" style="' + (p.c.fill ? "stroke:" + p.col : "fill:" + p.col) + '"/>' +
        '<text class="num" x="' + f1(p.x) + '" y="' + f1(p.y + 4) + '" text-anchor="middle"' + (p.c.fill ? ' style="fill:' + p.col + '"' : "") + ">" + (k + 1) + "</text>" +
        (lb && lb.line ? '<line class="lead" x1="' + f1(lb.line[0]) + '" y1="' + f1(lb.line[1]) + '" x2="' + f1(lb.line[2]) + '" y2="' + f1(lb.line[3]) + '"/>' : "") +
        (lb ? '<text class="lbl" x="' + f1(lb.x) + '" y="' + f1(lb.y) + '" text-anchor="' + lb.anc + '">' + esc(p.c.name) + "</text>" : "") + "</g>";
    });
    return s + "</svg>";
  }
  function renderCuChart() {
    const fig = $("bzCuChart"), pv = S.cu.pv;
    if (!fig || !pv || !pv.cands || !pv.cands.length) return;
    fig.innerHTML = cuChartSVG(pv.cands, Math.max(420, Math.round(fig.clientWidth || 700)));
  }
  function renderCuPrev() {
    const body = $("bzCuPrevBody"), meta = $("bzCuPrevMeta");
    if (!body) return;
    const pv = S.cu.pv;
    if (!pv) { body.innerHTML = S.cu.err ? empty(esc(S.cu.err)) : loading("正在读你的情况和市场数据…"); return; }
    const mk = pv.market || {};
    if (meta) meta.textContent = "不用 AI，按市场雷达最近 7 天的数据" + (mk.at ? "（" + hhmm(mk.at) + " 更新）" : "");
    const hot = (pv.hot || []).slice(0, 8);
    const hotHTML = hot.length ? '<div class="bz-cu-hot"><span>雷达上最近 7 天最热：</span>' + hot.map((h) =>
      '<button type="button" class="bz-chip" data-cu-map="' + esc(h.id) + '">' + esc(h.name) + " <b>" + h.n7 + "</b></button>").join("") + "</div>" : "";
    if (!pv.enough) {
      body.innerHTML = '<p class="bz-empty bz-cu-start">先在左边写写你的阅历、技能或兴趣，这里会马上配出适合你的方向，越靠前越配你。</p>' + hotHTML;
      return;
    }
    const cands = pv.cands || [];
    if (!cands.length) { body.innerHTML = empty("没配出来。多写几句阅历和技能试试。") + hotHTML; return; }
    S.cu.news = {};
    cands.forEach((c) => (c.news || []).forEach((it) => { S.cu.news[it.id] = it; }));
    const nFill = cands.filter((c) => c.fill).length;
    body.innerHTML = '<p class="bz-hint">' + (mk.window
      ? "把你写的对上行业分类，再看市场雷达最近 7 天每个方向抓到多少新闻。越靠右上角，越是又适合你、市场又热；圆点上的数字和下面的排名对得上。"
      : "市场雷达还没抓到新闻，现在只按你的情况配。去「市场雷达」点「现在更新」，这里就会有热度。") +
      (nFill ? "空心的圆点是你的情况里没对上、但市场热、一个人也能做的方向。" : "") + "</p>" +
      '<figure class="bz-cu-chart" id="bzCuChart"></figure>' +
      '<div class="bz-cu-list">' + cands.map(cuCandHTML).join("") + "</div>" +
      (pv.opps_you && pv.opps_you.length ? '<div class="bz-cu-oppy"><h4>机会看板里跟你沾边的</h4>' + pv.opps_you.map((o) =>
        '<p><button type="button" class="bz-link" data-goto="opps">' + esc(o.title) + "</button><span>里面提到你写的「" + esc(o.words.slice(0, 3).join("」「")) + "」</span></p>").join("") + "</div>" : "") +
      hotHTML;
    renderCuChart();
  }
  function cuPeek(id) {                                            // 鼠标在列表的哪一行 / 图上的哪个点，两边一起标出来
    if (S.cu.peek === id) return;
    S.cu.peek = id;
    root.querySelectorAll(".bz-cu-c.on, .bz-cu-svg .dot.on").forEach((e) => e.classList.remove("on"));
    if (!id) return;
    root.querySelectorAll('.bz-cu-c[data-cu-id="' + id + '"], .bz-cu-svg .dot[data-cu-dot="' + id + '"]').forEach((e) => e.classList.add("on"));
  }
  function cuJump(id) {                                            // 点图上的点：滚到下面那一张卡片
    const el = root.querySelector('.bz-cu-c[data-cu-id="' + id + '"]');
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
  }
  // 方案全文里「推荐方向一览」那几行画成卡片
  function customBody(text, plans) {
    const t = String(text || "").replace(/^\s*#\s+[^\n]*\n/, "");
    const lines = t.split("\n");
    const a = plans && plans.length ? lines.findIndex((l) => /^\s*#{1,4}\s*.*推荐方向一览/.test(l)) : -1;
    if (a < 0) return '<div class="md bz-md">' + md(t) + "</div>";
    let b = lines.length;
    for (let j = a + 1; j < lines.length; j++) { if (/^\s*#{1,4}\s/.test(lines[j])) { b = j; break; } }
    return '<div class="md bz-md">' + md(lines.slice(0, a + 1).join("\n")) + "</div>" + cuPlansHTML(plans) +
      '<div class="md bz-md">' + md(lines.slice(b).join("\n")) + "</div>";
  }

  // ───────── 爬虫管理 ─────────
  function renderCrawlerStatus() {
    const r = S.radar;
    if (!r) { $("bzRdLine").innerHTML = loading(); return; }
    let line;
    if (r.running) line = "<b>正在抓：" + r.done + " / " + r.total + "</b><span>这一轮新抓到 " + r.new + " 条" + (r.fail ? "，" + r.fail + " 个没抓成" : "") + "</span>";
    else if (r.last_run) line = "<b>" + esc(ago(r.last_run)) + "抓过一轮</b>" + (r.ended ? "<span>那一轮新抓到 " + r.new + " 条" + (r.fail ? "，" + r.fail + " 个没抓成" : "") + "</span>" : "") +
      (r.auto && r.next_run ? "<span>下一轮大约 " + esc(until(r.next_run)) + "</span>" : "<span>自动更新关着</span>");
    else line = "<b>还没开始抓</b><span>" + (r.auto ? "打开软件两三分钟后会自动抓第一轮，也可以现在就抓" : "自动更新关着，点「现在就抓一次」") + "</span>";
    $("bzRdLine").innerHTML = line;
    const pg = $("bzRdProg");
    pg.hidden = !r.running;
    if (r.running) {
      pg.innerHTML = '<div class="bz-prog"><i style="width:' + Math.round((r.done / Math.max(1, r.total)) * 100) + '%"></i></div>' +
        '<span class="bz-dim">' + ((r.current || []).length ? "正在抓：" + esc(r.current.join("、")) : "收尾中…") + "</span>";
    }
    $("bzRdNote").textContent = "盯着 " + r.enabled + " 个信息源" + (r.failing ? "（" + r.failing + " 个上次没抓成，看清单里的原因）" : "") +
      "；一共存着 " + r.items + " 条，最近 24 小时抓到 " + r.items_24h + " 条、7 天 " + r.items_7d + " 条。";
    const key = (r.running ? 1 : 0) + "|" + r.auto + "|" + r.every;
    const ctl = $("bzRdCtl");
    if (ctl.dataset.k !== key) {
      ctl.dataset.k = key;
      ctl.innerHTML = (r.running ? '<button type="button" class="bz-btn ghost sm" data-act="rd-stop">停止</button>' : '<button type="button" class="bz-btn sm" data-act="rd-run">现在就抓一次</button>') +
        '<label class="bz-chk"><input type="checkbox" id="bzRdAuto"' + (r.auto ? " checked" : "") + ">自动更新</label>" +
        '<select class="bz-select sm" id="bzRdEvery" aria-label="多久抓一次">' + EVERY.map(([v, t]) => '<option value="' + v + '"' + (+r.every === v ? " selected" : "") + ">每 " + t + "</option>").join("") +
          (EVERY.some(([v]) => v === +r.every) ? "" : '<option value="' + r.every + '" selected>每 ' + everyText(+r.every) + "</option>") + "</select>";
    }
    const lg = $("bzRdLog");
    const log = r.log || [];
    lg.innerHTML = log.length ? log.slice().reverse().map((x) => '<div><time>' + hhmm(x[0]) + "</time>" + esc(x[1]) + "</div>").join("")
      : empty("还没有日志。抓一轮就有了。");
  }
  function renderEngines() {
    const e = S.engines;
    $("bzEnginesOrder").textContent = e ? e.order : "";
    $("bzEngines").innerHTML = !e ? loading() : e.engines.map((x) =>
      '<div class="bz-eng' + (x.ok ? "" : " off") + '"><div class="bz-eng-h"><b>' + esc(x.name) + '</b><span class="bz-eng-st ' + (x.ok ? "ok" : "bad") + '">' + (x.ok ? "能用" : "不能用") + "</span></div>" +
      "<p>" + esc(x.desc) + '</p><p class="bz-eng-state">' + esc(x.state) + "</p>" +
      '<p class="bz-eng-use">现在有 <b>' + x.now + "</b> 个信息源靠它" + (e.last_run ? "，上一轮用它抓成 " + x.last + " 个" : "") + "</p></div>").join("");
  }
  function renderRuns() {
    const runs = S.runs, r = S.radar;
    if (!runs) { $("bzRuns").innerHTML = loading(); return; }
    let rows = "";
    if (r && r.running && r.rid) {
      rows += '<tr class="live" data-run="' + esc(r.rid) + '" tabindex="0"><td>' + esc(fmtTime(r.started)) + "</td><td>" + esc(TRIG[r.trigger] || "") + "</td><td>进行中</td><td>" + r.done + " / " + r.total + '</td><td class="num">' + r.new + "</td><td>—</td></tr>";
    }
    rows += runs.filter((x) => !(r && r.running && x.id === r.rid)).map((x) => '<tr data-run="' + esc(x.id) + '" tabindex="0"><td>' + esc(fmtTime(x.started)) + "</td><td>" + esc(TRIG[x.trigger] || x.trigger || "") + (x.stopped ? "（中途停止）" : "") +
      "</td><td>" + esc(dur((x.ended || 0) - (x.started || 0))) + "</td><td>" + x.ok + " 成功" + (x.fail ? '，<span class="bad">' + x.fail + " 失败</span>" : "") +
      '</td><td class="num">' + x.new + "</td><td>" + esc(viaText(x.via) || "—") + "</td></tr>").join("");
    $("bzRuns").innerHTML = rows ? '<table class="bz-runs"><thead><tr><th>开始时间</th><th>怎么开始的</th><th>用时</th><th>信息源</th><th class="num">新内容</th><th>用到的爬虫</th></tr></thead><tbody>' + rows + "</tbody></table>"
      : empty("还没有抓取记录。点上面的「现在就抓一次」，或者等自动更新。");
  }
  function rdRow(s) {
    const st = s.err ? '<span class="bz-rd-st err">没抓成：' + esc(s.err) + "</span>"
      : s.ok_at ? '<span class="bz-rd-st ok">' + esc(ago(s.ok_at)) + "抓到 " + (s.n || 0) + " 条" + (s.new ? "，新的 " + s.new + " 条" : "") + (s.via ? "（" + esc(s.via) + "）" : "") + "</span>"
        : '<span class="bz-rd-st">还没抓过</span>';
    const tgt = s.kind === "kw" ? "关键词：" + (s.kw || s.name) : String(s.url || "").replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
    const hints = (s.hint || []).slice(0, 2).map((h) => '<span class="bz-tag">' + esc(nameOf(h)) + "</span>").join("");
    return '<div class="bz-rd-src' + (s.enabled ? "" : " off") + '">' +
      '<label class="bz-sw" title="打开 / 关掉"><input type="checkbox" data-rd-toggle="' + esc(s.id) + '"' + (s.enabled ? " checked" : "") + ' aria-label="盯不盯 ' + esc(s.name) + '"><i></i></label>' +
      '<div class="bz-rd-main"><div class="bz-rd-name"><b>' + esc(s.name) + "</b>" + hints + (s.n7 ? '<span class="bz-dim">近 7 天 ' + s.n7 + " 条</span>" : "") + "</div>" +
      '<div class="bz-rd-url">' + esc(tgt) + "</div>" + st + (s.off_why && !s.enabled ? '<span class="bz-rd-st err">' + esc(s.off_why) + "</span>" : "") + "</div>" +
      '<div class="bz-rd-acts"><select class="bz-select sm bz-rd-w w' + (s.w || 3) + '" data-rd-w="' + esc(s.id) + '" title="权重：越高抓得越勤（5、4 每轮都抓；3 隔 3 轮；2 隔 8 轮；1 隔 24 轮）" aria-label="权重">' +
        [5, 4, 3, 2, 1].map((v) => '<option value="' + v + '"' + (v === (s.w || 3) ? " selected" : "") + ">权重 " + v + "</option>").join("") + "</select>" +
        '<button type="button" class="bz-link" data-rd-items="' + esc(s.id) + '">看抓到的</button>' +
      '<button type="button" class="bz-link" data-rd-one="' + esc(s.id) + '">抓一次</button>' +
      '<button type="button" class="bz-link danger" data-rd-del="' + esc(s.id) + '">删除</button></div></div>';
  }
  function renderSources() {
    segSync("rdkind", S.rdKind);
    const kw = S.rdKind === "kw";
    $("bzRdTarget").placeholder = kw ? "关键词：比如 比亚迪、预制菜、低空经济" : "网址：比如 https://www.example.com/news";
    $("bzRdFormNote").textContent = kw
      ? "公司名、行业、话题都行。爬虫会定时去新闻搜索里找这个词最新的报道（有代理用 Google 新闻，没有用必应新闻，再不行用百度资讯）。"
      : "填网站的新闻页、博客页最好。有 RSS 会自动用 RSS；打不开或者是动态网页，会用 Scrapling 打开。";
    const d = S.radarSrc;
    if (!d) { $("bzRdMine").innerHTML = loading(); $("bzRdCatalog").innerHTML = ""; }
    else {
      $("bzRdCount").textContent = d.sources.length + " 个，打开的 " + d.sources.filter((x) => x.enabled).length + " 个";
      let html = "";
      S.rdShowAll = S.rdShowAll || {};
      d.groups.forEach((g) => {                     // v170：每组按权重从高到低；太多的先显示前 50 个
        const rows = d.sources.filter((x) => (x.group || "mine") === g.key);
        if (!rows.length) return;
        const on = rows.filter((x) => x.enabled).length, all = S.rdShowAll[g.key], shown = all ? rows : rows.slice(0, 50);
        html += '<div class="bz-rd-grp"><h4>' + esc(g.name) + ' <small class="bz-dim">' + rows.length + " 个，打开 " + on + " 个</small></h4>" + shown.map(rdRow).join("") +
          (rows.length > 50 ? '<button type="button" class="bz-link bz-rd-more" data-rd-more="' + esc(g.key) + '">' + (all ? "收起" : "显示全部 " + rows.length + " 个") + "</button>" : "") + "</div>";
      });
      $("bzRdMine").innerHTML = html || empty("清单是空的。从下面推荐的里挑几个，或者在右边自己加。");
      $("bzRdCatalog").innerHTML = d.catalog.map((g) => {
        const left = g.items.filter((x) => !x.added).length;
        return '<details class="bz-rd-cat" data-grp="' + esc(g.key) + '"' + (S.rdOpen[g.key] ? " open" : "") + "><summary><b>" + esc(g.name) + "</b><span>" + esc(g.desc) + "</span>" +
          '<span class="bz-dim">' + (g.items.length - left) + " / " + g.items.length + " 个已在清单</span>" +
          (left ? '<button type="button" class="bz-link" data-rd-addgrp="' + esc(g.key) + '">这一组全加进去</button>' : "") + "</summary>" +
          '<div class="bz-rd-catlist">' + g.items.map((x) => '<div class="bz-rd-ci' + (x.added ? " on" : "") + '"><div><b>' + esc(x.name) + "</b>" +
            (x.kind === "kw" ? '<span class="bz-tag">关键词</span>' : "") + "<span>" + esc(x.desc || (x.kind === "kw" ? "搜「" + x.target + "」的最新新闻" : x.target.replace(/^https?:\/\//, ""))) + "</span></div>" +
            (x.added ? '<span class="bz-dim">已在清单</span>' : '<button type="button" class="bz-btn ghost sm" data-rd-add="' + esc(x.id) + '">加入</button>') + "</div>").join("") +
          "</div></details>";
      }).join("");
    }
    const src = S.rdSid && d ? d.sources.find((x) => x.id === S.rdSid) : null;
    $("bzRdLatestT").innerHTML = src ? "「" + esc(src.name) + '」抓到的 <button type="button" class="bz-link" data-act="rd-allitems">看全部</button>' : "刚抓到的";
    const list = S.rdSid ? S.rdItems : (S.ovm ? S.ovm.latest : null);
    $("bzRdLatest").innerHTML = !list ? loading() : (list.length ? list.slice(0, 40).map(itemRow).join("") : empty(S.rdSid ? "这个信息源还没抓到东西。" : "还没抓到东西。"));
  }
  function renderCrawler() {
    renderCrawlerStatus();
    renderEngines();
    renderRuns();
    renderSources();
  }
  function stepHTML(x) {
    return '<span class="bz-step ' + (x.ok ? "ok" : "bad") + '" title="' + esc(x.m + "：" + (x.ok ? "抓到 " + x.n + " 条" : x.why) + "（" + (x.ms / 1000).toFixed(1) + " 秒）") + '">' +
      esc(x.m) + "：" + esc(x.ok ? x.n + " 条" : x.why) + "</span>";
  }
  async function openRunReport(rid) {
    openReader("读取中…", "", loading(), "");
    let r;
    try { r = await api("/biz/radar/report?id=" + enc(rid)); } catch (e) { r = { ok: false, error: e.message }; }
    if (!r.ok) { openReader("打不开", "", empty(esc(r.error || "读取失败")), ""); return; }
    S.readerRun = rid;
    const run = r.run;
    const stats = [["用时", run.running ? "进行中（" + run.done + " / " + run.total + "）" : dur((run.ended || 0) - (run.started || 0))],
      ["信息源", run.ok + " 个成功，" + run.fail + " 个失败"], ["新抓到", r.n_items + " 条"], ["怎么开始的", TRIG[run.trigger] || run.trigger || ""]];
    const via = Object.entries(run.via || {}).sort((a, b) => b[1] - a[1]);
    const srcs = (run.sources || []).slice().sort((a, b) => (a.ok === b.ok ? 0 : a.ok ? 1 : -1));
    let html = '<div class="bz-rr"><div class="bz-rr-stats">' + stats.map(([k, v]) => "<div><span>" + k + "</span><b>" + esc(v) + "</b></div>").join("") + "</div>" +
      "<h3>用到的爬虫</h3>" + (via.length ? '<div class="bz-chips">' + via.map(([k, v]) => '<span class="bz-chip static">' + esc(k) + " <b>" + v + " 个</b></span>").join("") + "</div>" : empty("这一轮还没有抓成功的。")) +
      "<h3>新内容按行业</h3>" + (r.by_ind.length ? '<div class="bz-chips">' + r.by_ind.map(([g, n]) => '<span class="bz-chip static">' + esc(nameOf(g)) + " <b>" + n + "</b></span>").join("") + "</div>" : empty("这一轮没有新内容，或者都没归到行业。")) +
      "<h3>每个信息源是怎么抓的</h3>" +
      '<div class="bz-tablewrap"><table class="bz-rrtab"><thead><tr><th>信息源</th><th>结果</th><th>过程（一步一步试）</th><th class="num">用时</th></tr></thead><tbody>' +
      srcs.map((x) => "<tr><td><b>" + esc(x.name) + "</b><span>" + esc(x.kind === "kw" ? "关键词：" + (x.target || "") : String(x.target || "").replace(/^https?:\/\/(www\.)?/, "")) + "</span></td>" +
        "<td>" + (x.ok ? '<span class="ok">用「' + esc(x.via) + "」抓到 " + x.n + " 条，新的 " + x.new + " 条</span>" : '<span class="bad">没抓成：' + esc(x.err || "") + "</span>") + "</td>" +
        '<td class="steps">' + ((x.trace || []).map(stepHTML).join('<i aria-hidden="true">→</i>') || "—") + "</td>" +
        '<td class="num">' + ((x.ms || 0) / 1000).toFixed(1) + " 秒</td></tr>").join("") + "</tbody></table></div>" +
      "<h3>这一轮新抓到的（" + r.n_items + "）</h3>" + '<div class="bz-feed">' + (r.items.length ? r.items.slice(0, 120).map(itemRow).join("") : empty("没有新内容。")) + "</div>" +
      (r.n_items > 120 ? '<p class="bz-note">只列了最新的 120 条，全部都能在「市场雷达」里看到。</p>' : "") +
      "<h3>运行日志</h3>" + '<div class="bz-log big">' + (run.log || []).map((x) => "<div><time>" + hhmm(x[0]) + "</time>" + esc(x[1]) + "</div>").join("") + "</div></div>";
    openReader("抓取报告 · " + fmtTime(run.started), '<span>这一轮是' + esc(TRIG[run.trigger] || "") + "开始的</span>", html,
      run.running ? '<button type="button" class="bz-btn ghost sm" data-act="run-refresh">刷新</button>' : "");
  }

  function renderPane(p) {
    if (p === "radar") renderRadarPane();
    else if (p === "industry") renderIndustry();
    else if (p === "real") renderReal();                            // v191
    else if (p === "analysis") renderAnalysis();
    else if (p === "opps") renderOpps();
    else if (p === "custom") renderCustom();
    else if (p === "crawler") renderCrawler();
  }


  // ───────── v191：真实市场（钱在哪里）─────────
  // 市场雷达看「新闻多不多」；这里看「钱」：统计局 + 上市公司财报（自动），具体方向让 AI 联网核实（电商、交易平台、招投标、报告）。
  const RM_METRIC = [["size", "规模"], ["verified", "AI 核实的规模"], ["growth", "增长"], ["margin", "利润率"], ["quad", "热度 × 真钱"]];   // v197：加「AI 核实的规模」
  const RM_PLAT = { ccgp: "政府采购网", b2b: "1688", ywg: "义乌购", jd: "京东", sn: "苏宁易购", smzdm: "什么值得买", zbj: "猪八戒",
    amazon: "亚马逊", ebay: "eBay", aliexpress: "速卖通", alibaba: "阿里巴巴国际站" };
  // v200：平台名字以后端为准（v199 新加的国外平台以前会显示成 amz_de 这种代号）
  const rmPlatName = (p) => {
    const src = ((S.rm.data && S.rm.data.sources) || []).find((x) => x.key === "tp_" + p);
    return RM_PLAT[p] || (src ? src.name.replace(/（.*?）/g, "").trim() : p);
  };
  const rmNeedLogin = (p) => {                                        // 要登录、现在没登录 → 给一个「登录」按钮
    const L = (S.rm.data && S.rm.data.logins && S.rm.data.logins.sites) || {};
    return !!L[p] && !L[p].logged && !L[p].waiting;
  };
  const rmLoginBtn = (p, cls) => '<button type="button" class="bz-btn sm ' + (cls || "") + '" data-rm-login="' + esc(p) + '">登录' +
    esc(((S.rm.data && S.rm.data.logins && S.rm.data.logins.sites) || {})[p] ? S.rm.data.logins.sites[p].name : "") + "</button>";
  const RM_BASIS_CLS = { "统计局": "gov", "上市公司": "co", "电商平台": "ec", "交易平台": "ec", "招投标": "ec", "行业报告": "rp", "媒体报道": "rp", "估算": "es" };
  function rmPaneHTML() {                                          // v195：更新数据 / AI 核实 / 交易平台抓取 做成三个标签，不用拉到下面
    return '<div class="bz-pane" data-pane="real">' +
      '<section class="bz-hero bz-rm-hero"><h2>真实市场：钱在哪里</h2>' +
        "<p>市场雷达看新闻多不多（大家在说什么），这里看钱：一年卖了多少、谁在买、肯花多少、赚不赚钱。</p>" +
        '<div class="bz-rm-kpi" id="bzRmKpi"></div></section>' +
      '<div class="bz-rm-tabs" id="bzRmTabs" role="tablist" aria-label="要做什么">' +
        '<button type="button" role="tab" data-rmtab="map"><b>行业地图</b><span class="bz-rm-tabs-s" data-rmts="map"></span></button>' +
        '<button type="button" role="tab" data-rmtab="data"><b>更新数据</b><span class="bz-rm-tabs-s" data-rmts="data"></span></button>' +
        '<button type="button" role="tab" data-rmtab="check"><b>AI 核实</b><span class="bz-rm-tabs-s" data-rmts="check"></span></button>' +
        '<button type="button" role="tab" data-rmtab="trade"><b>交易平台抓取</b><span class="bz-rm-tabs-s" data-rmts="trade"></span></button></div>' +
      '<section class="bz-rm-tp" data-rmtp="data" hidden>' +
        '<div class="bz-rm-tp-h"><p class="bz-hint">统计局（社零、工业利润、居民收支）、上市公司财报和概念板块（新兴赛道）的数字，自动更新；超过 12 小时没更新，打开这一页会自己更新。想马上取最新的，点右边。</p>' +
          '<button type="button" class="bz-btn" data-act="rm-update" id="bzRmUpdBtn">现在更新数据</button></div>' +
        '<p class="bz-note" id="bzRmUpd"></p><div class="bz-rm-report" id="bzRmReport" hidden></div>' +
        '<div class="bz-tablewrap" id="bzRmSrcAuto"></div></section>' +
      '<section class="bz-rm-tp" data-rmtp="check" hidden>' +
        '<div class="bz-rm-run" id="bzRmRun"></div>' +
        '<p class="bz-hint">市场雷达发现机会，这里核实真钱。从下拉框选一个行业（软件里所有的行业、细分和新兴赛道都在），或者自己写一个更细的方向；也可以点「全部核实」排队一个个来。' +
          '每个方向会先让爬虫去交易平台抓真实的公告、价格和成交，再联网查报告，最后让 AI 整理成体检卡。正在核实的那一个会在最上面，点它的标题就能看 AI 实时画面。</p>' +
        '<div class="bz-rm-form"><select class="bz-select" id="bzRmPick" aria-label="选一个行业"><option value="">选一个行业…</option></select>' +
          '<span class="bz-dim">或者</span><input class="bz-input" id="bzRmTarget" maxlength="40" placeholder="自己写：外贸企业英文资料制作、宠物殡葬…" aria-label="自己写要核实的方向">' +
          seg("rmdepth", [["quick", "快速"], ["deep", "深入"]]) +
          '<button type="button" class="bz-btn" data-act="rm-check">AI 联网核实</button>' +
          '<button type="button" class="bz-btn ghost" data-act="rm-batch-open">全部核实…</button></div>' +
        '<div class="bz-rm-batch" id="bzRmBatch"></div>' +
        '<div class="bz-rm-checks" id="bzRmChecks"></div></section>' +
      '<section class="bz-rm-tp" data-rmtp="trade" hidden>' +
        '<div class="bz-rm-tact"><div><div id="bzRmTAct"></div>' +                                // v201：整页只有一张全世界平台总表
          '<details class="bz-rm-unlock"><summary>更强的抓取（可选，要花钱）<span id="bzRmApifySt"></span><span id="bzRmUnlockSt"></span></summary>' +       // v202 / v203
          '<div class="in sec"><b>① Apify 现成爬虫（推荐）</b><p class="bz-dim" id="bzRmApifyNote"></p>' +
          '<div class="row"><input class="bz-input" id="bzRmApifyT" type="password" autocomplete="off" placeholder="粘贴 Apify 令牌（API token）" aria-label="Apify 令牌">' +
          '<button type="button" class="bz-btn sm" data-act="rm-apify-save">保存</button><button type="button" class="bz-link" data-act="rm-apify-off">不用了</button></div></div>' +
          '<div class="in sec"><b>② 付费解锁服务</b><p class="bz-dim">国外平台（亚马逊、Jumia、Lazada 这类）用免费办法都抓不到时，才交给它：它用真人家里的网络 IP、自动过验证去打开网页。' +
          "要你自己去它网站注册、拿一个钥匙（API Key）填在这里；钥匙加密存在你电脑上，不会传到 GitHub。每天最多用 100 次。</p>" +
          '<div class="row"><select class="bz-select" id="bzRmUnlockP" aria-label="用哪家"></select>' +
          '<input class="bz-input" id="bzRmUnlockK" type="password" autocomplete="off" placeholder="粘贴钥匙（API Key）" aria-label="钥匙">' +
          '<button type="button" class="bz-btn sm" data-act="rm-unlock-save">保存</button><button type="button" class="bz-link" data-act="rm-unlock-off">不用了</button></div>' +
          '<p class="bz-dim" id="bzRmUnlockNote"></p></div></details></div>' +
          '<label class="bz-rm-tkw">试抓用的词<input class="bz-input" id="bzRmTryKw" maxlength="30" value="宠物" aria-label="试抓用的词"></label></div>' +
        '<div id="bzRmTLive"></div><div class="bz-tablewrap" id="bzRmTTable"></div></section>' +
      '<section class="bz-rm-tp bz-rm-tp-map" data-rmtp="map">' +                    // v196：地图也是一个标签（以前放在三个标签下面共用，看着像每个标签里都有）
        '<div class="bz-bar bz-rm-mapbar">' + seg("rmmetric", RM_METRIC) + seg("rmview", [["map", "地图"], ["list", "列表"]]) +
          '<input type="search" class="bz-input" id="bzRmQ" placeholder="找行业：白酒、化妆品、教育…" aria-label="找行业"></div>' +
        '<p class="bz-source" id="bzRmLegend"></p>' +
        '<div class="bz-ind nodet" id="bzRmWrap"><div class="bz-ind-main" id="bzRmMain"></div><aside class="bz-ind-detail" id="bzRmDetail" hidden></aside></div></section>' +
    "</div>";
  }
  // v195：三个标签——切换、标签上显示正在做的事
  function rmTabsRender() {
    const tabs = $("bzRmTabs");
    if (!tabs) return;
    const t = S.rm.tab, d = S.rm.data || {}, j = S.job, bt = d.batch, tb = d.tbatch;
    tabs.querySelectorAll("[data-rmtab]").forEach((b) => { const on = b.dataset.rmtab === t; b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); });
    root.querySelectorAll(".bz-rm-tp").forEach((x) => { x.hidden = x.dataset.rmtp !== t; });
    const spin = '<span class="bz-spin" aria-hidden="true"></span>';
    const L = d.listed || {};
    const st = {
      map: (L.companies ? L.companies + " 家公司" : "") + (Object.values(d.by || {}).filter((b) => b.chk).length ? " · " + Object.values(d.by || {}).filter((b) => b.chk).length + " 个核实过" : (L.companies ? " · 点格子看体检卡" : "")),
      data: d.updating && d.updating.running || S.rm.updWait ? spin + "正在更新" : d.updated ? ago(d.updated) + "更新过" : "",
      check: j && j.running && j.kind === "real" ? spin + (bt && bt.running ? "核实中 " + Math.min(bt.n, bt.i + 1) + "/" + bt.n : "正在核实") :
        bt && bt.running ? spin + "排队中 " + bt.i + "/" + bt.n : bt && bt.paused ? "暂停了 " + bt.i + "/" + bt.n : ((d.checks || []).length ? (d.checks || []).length + " 个核实过" : ""),
      trade: tb && tb.running ? spin + "抓取中 " + tb.i + "/" + tb.n : Object.values((d.logins && d.logins.sites) || {}).some((x) => x.waiting) ? spin + "等你登录" : "",
    };
    tabs.querySelectorAll("[data-rmts]").forEach((x) => { x.innerHTML = st[x.dataset.rmts] || ""; });
  }
  function rmSetTab(t) {
    S.rm.tab = ["map", "data", "check", "trade"].includes(t) ? t : "map";
    store.set("rmTab", S.rm.tab);
    rmTabsRender();
    bzLivePlace();
    const tabs = $("bzRmTabs"), sc = $("bzScroll"), tp = root.querySelector('.bz-rm-tp[data-rmtp="' + S.rm.tab + '"]');
    if (tabs && sc && tp) {                                          // v196：切过去时，这个标签的内容要在眼前（往下拉了的话滚回标签下面）
      const gap = tp.getBoundingClientRect().top - tabs.getBoundingClientRect().bottom;
      if (gap < -1) sc.scrollTop += gap;
    }
  }
  const rmYi = (v) => (v == null ? "–" : Math.abs(v) >= 10000 ? (v / 10000).toFixed(Math.abs(v) >= 100000 ? 1 : 2).replace(/\.?0+$/, "") + " 万亿" : (Math.abs(v) >= 100 ? Math.round(v) : v.toFixed(1).replace(/\.0$/, "")) + " 亿");
  const rmPct = (v) => (v == null ? "–" : (v > 0 ? "+" : "") + v.toFixed(1).replace(/\.0$/, "") + "%");
  const rmNum = (v) => (v == null ? "–" : Math.round(v).toLocaleString("zh-CN"));
  const rmBy = (id) => (S.rm.data && S.rm.data.by[id]) || {};
  function rmVal(id) {
    const b = rmBy(id), m = S.rm.metric;
    if (m === "growth") return b.q_yoy != null ? b.q_yoy : b.rev_yoy;
    if (m === "margin") return b.nm;
    if (m === "verified") return b.v_size;                           // v197：AI 核实出来的市场规模（亿元）
    return b.rev;
  }
  // v197：核实过的数字在格子上怎么写
  const rmVTxt = (b) => (b.v_size != null ? "核实 " + rmYi(b.v_size) + (b.v_size_ok ? "" : "?") : "核实过");
  function rmLvl(id, mx) {
    const v = rmVal(id), m = S.rm.metric;
    if (v == null) return 0;
    if (m === "growth") return v < -10 ? 1 : v < 0 ? 2 : v < 10 ? 3 : v < 25 ? 4 : 5;
    if (m === "margin") return v < 0 ? 1 : v < 5 ? 2 : v < 10 ? 3 : v < 20 ? 4 : 5;
    const r = mx ? Math.sqrt(Math.max(0, v) / mx) : 0;
    return r < 0.2 ? 1 : r < 0.4 ? 2 : r < 0.6 ? 3 : r < 0.8 ? 4 : 5;
  }
  function rmValText(id) {
    const v = rmVal(id), m = S.rm.metric;
    if (v == null) return "";
    return m === "growth" ? rmPct(v) : m === "margin" ? "净利 " + v.toFixed(1).replace(/\.0$/, "") + "%" : m === "verified" ? rmYi(v) + (rmBy(id).v_size_ok ? "" : "?") : rmYi(v);
  }
  function rmTip(id) {
    const d = S.byId[id], b = rmBy(id), L = (S.rm.data && S.rm.data.listed) || {};
    let t = d.name + "：" + d.desc;
    if (b.n && d.type === "trk") t += "\n概念板块里的相关上市公司 " + b.n + " 家（不一定全靠这块赚钱）";
    if (b.n) t += "\n上市公司 " + b.n + " 家，" + (L.annual_name || "") + "营收合计 " + rmYi(b.rev) + "（" + rmPct(b.rev_yoy) + "），净利率 " + (b.nm == null ? "–" : b.nm + "%") +
      (b.q_yoy != null ? "\n" + (L.latest_name || "最新一期") + "营收同比 " + rmPct(b.q_yoy) : "");
    else t += "\n没有直接对上的上市公司数据";
    if (b.nbs) t += "\n统计局有 " + b.nbs + " 项相关数字";
    if (b.chk) {
      t += "\n— AI 核实（" + fmtTime(b.v_at) + "，" + b.v_n + " 个数字，" + b.v_ok + " 个对上原文）—";
      if (b.v_size != null) t += "\n规模：" + b.v_size_txt + "（" + (b.v_size_m || "") + "，" + (b.v_size_b || "") + (b.v_size_when ? "，" + b.v_size_when : "") + (b.v_size_ok ? "，原文有" : "，没对上原文") + "）";
      [["客户", b.v_cust], ["购买力", b.v_buy], ["利润", b.v_prof]].forEach(([k, x]) => { if (x) t += "\n" + k + "：" + x.value + "（" + x.metric + "）"; });
    } else t += "\n还没 AI 核实";
    return t + "\n点一下看体检卡";
  }
  function rmTile(id, mx) {
    const d = S.byId[id];
    if (!d) return "";
    const b = rmBy(id), q = S.rm.q.trim().toLowerCase();
    const hit = !q || [d.name, d.desc, d.kw, d.co].some((x) => x && String(x).toLowerCase().includes(q));
    const v = rmVal(id);
    return '<button type="button" class="bz-tile' + (d.type === "l2" ? " l2" : "") + " h" + rmLvl(id, mx) + (S.rm.sel === id ? " sel" : "") + (hit ? "" : " dim") +
      (v != null && v < 0 ? " neg" : "") + '" style="--c:' + colorOf(id) + '" data-rm="' + esc(id) + '" title="' + esc(rmTip(id)) + '"><span class="nm">' + esc(d.name) + "</span>" +
      '<span class="ct">' + (rmValText(id) || (S.rm.metric === "verified" ? (b.chk ? "核实过，没查到规模" : "还没核实") : b.nbs ? "统计 " + b.nbs + " 项" : "")) + "</span>" +
      (b.chk && S.rm.metric !== "verified" ? '<span class="vf' + (b.v_size_ok ? " ok" : "") + '">✓ ' + esc(rmVTxt(b)) + "</span>" : "") +       // v197：核实过的，格子里多一行核实出来的规模
      (b.chk ? '<i class="gap chk" aria-hidden="true"></i>' : "") + "</button>";
  }
  const rmSort = (a, b) => ((rmVal(b) == null ? -1e15 : rmVal(b)) - (rmVal(a) == null ? -1e15 : rmVal(a)));
  function rmMapHTML() {
    const t = S.tax, mx = { l2: 0, trk: 0 };
    const mv = (id) => (S.rm.metric === "verified" ? rmBy(id).v_size : rmBy(id).rev) || 0;     // v197：「AI 核实的规模」按核实出来的数分深浅
    t.industries.forEach((i) => i.subs.forEach((x) => { mx.l2 = Math.max(mx.l2, mv(x.id)); }));
    t.tracks.forEach((x) => { mx.trk = Math.max(mx.trk, mv(x.id)); });          // v194：新兴赛道按概念板块的相关公司算
    if (S.rm.metric === "verified") mx.l2 = mx.trk = Math.max(mx.l2, mx.trk);
    const secV = (sec) => sec.l1.reduce((a, n) => a + (rmBy(n).rev || 0), 0);
    let html = '<section class="bz-band trk"><header><h4>新兴赛道</h4>' +
      "<span>没有单独的行业分类，按东方财富概念板块里的相关上市公司算（这些公司不一定全靠这块赚钱，几个赛道之间也有重叠）</span></header><div class=\"bz-tiles\">" +
      t.tracks.slice().sort((a, b) => rmSort(a.id, b.id)).map((x) => rmTile(x.id, mx.trk)).join("") + "</div></section>";
    t.sectors.slice().sort((a, b) => secV(b) - secV(a)).forEach((sec) => {
      html += '<section class="bz-band" style="--c:' + (RAD_SEC[sec.name] || "#888") + '"><header><h4>' + esc(sec.name) + "</h4>" +
        (S.rm.metric === "verified" ? ((n) => (n ? '<em class="bz-band-n">核实过 ' + n + " 个</em>" : ""))(sec.l1.reduce((a, n1) => a + S.byId[n1].subs.filter((x) => rmBy(x).chk).length, 0)) :
          secV(sec) ? '<em class="bz-band-n">上市公司营收 ' + rmYi(secV(sec)) + "</em>" : "") + "<span>" + esc(sec.desc) + '</span></header><div class="bz-l1s">' +
        sec.l1.slice().sort(rmSort).map((n) => {
          const d = S.byId[n];
          return '<div class="bz-l1" style="flex-grow:' + d.subs.length + ";--c:" + colorOf(n) + '"><button type="button" class="bz-l1-h' + (S.rm.sel === n ? " sel" : "") +
            '" data-rm="' + esc(n) + '" title="' + esc(rmTip(n)) + '"><span>' + esc(n) + "</span>" + (rmValText(n) ? "<em>" + rmValText(n) + "</em>" : "") + "</button>" +
            '<div class="bz-tiles">' + d.subs.slice().sort(rmSort).map((x) => rmTile(x, mx.l2)).join("") + "</div></div>";
        }).join("") + "</div></section>";
    });
    return '<div class="bz-map">' + html + "</div>";
  }
  function rmListHTML() {
    const q = S.rm.q.trim().toLowerCase(), L = (S.rm.data && S.rm.data.listed) || {};
    const ids = [];
    S.tax.industries.forEach((i) => i.subs.forEach((x) => ids.push(x.id)));
    const rows = ids.filter((id) => { const d = S.byId[id]; return !q || [d.name, d.desc, d.kw, d.l1].some((x) => x && String(x).toLowerCase().includes(q)); }).sort(rmSort);
    if (!rows.length) return empty("没有找到「" + esc(q) + "」。换个说法试试。");
    return '<div class="bz-tablewrap"><table class="bz-ltab bz-rm-tab"><thead><tr><th>行业</th><th class="num">上市公司营收（' + esc(L.annual_name || "年报") + '）</th><th class="num">' + esc(L.latest_name || "最新") +
      ' 营收增长</th><th class="num">净利率</th><th class="num">毛利率</th><th class="num">公司数</th><th class="num">统计局</th><th class="num">AI 核实的规模</th></tr></thead><tbody>' +
      rows.map((id) => {
        const d = S.byId[id], b = rmBy(id);
        return '<tr data-row="' + esc(id) + '"' + (S.rm.sel === id ? ' class="sel"' : "") + '><td class="nm"><button type="button" class="bz-link strong" data-rm="' + esc(id) + '">' + esc(d.name) +
          '</button><span class="co">' + esc(d.l1) + "</span></td><td class=\"num\">" + rmYi(b.rev) + '</td><td class="num' + ((b.q_yoy != null ? b.q_yoy : b.rev_yoy) < 0 ? " neg" : "") + '">' +
          rmPct(b.q_yoy != null ? b.q_yoy : b.rev_yoy) + '</td><td class="num">' + (b.nm == null ? "–" : b.nm + "%") + '</td><td class="num">' + (b.gm == null ? "–" : b.gm + "%") +
          '</td><td class="num">' + (b.n || "–") + '</td><td class="num">' + (b.nbs ? b.nbs + " 项" : "–") + '</td><td class="num">' +
          (b.chk ? '<span title="' + esc(b.v_size_txt ? b.v_size_txt + "（" + (b.v_size_m || "") + "）" : "核实过，没查到规模") + '">' + esc(b.v_size != null ? rmYi(b.v_size) + (b.v_size_ok ? " ✓" : " ?") : "✓") + "</span>" : "–") + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }
  // 热度 × 真钱：横轴是市场雷达的新闻条数，纵轴是上市公司营收；两条中位线分出四块
  function rmQuadPts() {
    const pts = [];
    S.tax.industries.forEach((i) => i.subs.forEach((x) => {
      const b = rmBy(x.id);
      if (b.rev > 0) pts.push({ id: x.id, name: x.name, rev: b.rev, heat: heatIn(S.ovm, x.id)[0] || 0, c: colorOf(x.id) });
    }));
    return pts;
  }
  const rmMedian = (a) => { const s = a.slice().sort((x, y) => x - y); return s.length ? s[(s.length - 1) >> 1] : 0; };
  function rmQuadrant(p, mh, mr) { return p.heat >= mh ? (p.rev >= mr ? "both" : "hot") : (p.rev >= mr ? "rich" : "cold"); }
  const RM_Q = { both: ["又热又大", "主流大市场，钱多人也多，竞争最激烈"], hot: ["话多钱少", "大家都在说，真钱还不多：小心炒作，或者还早"],
    rich: ["钱多话少", "没什么人在说，钱却很多：闷声赚钱的地方"], cold: ["又冷又小", "说的人少、钱也少"] };
  function rmQuadHTML() {
    const pts = rmQuadPts();
    if (!pts.length) return empty("还没有上市公司数据，画不出来。点上面「现在更新数据」。");
    if (!S.ovm) return loading("正在读市场雷达的热度…");
    const W = 900, H = 520, pl = 64, pr = 24, pt = 30, pb = 52, lx = (x) => x > W - pr - 110;
    const mh = rmMedian(pts.map((p) => p.heat)), mr = rmMedian(pts.map((p) => p.rev));
    const hx = Math.max(1, ...pts.map((p) => p.heat)), rmin = Math.max(1, Math.min(...pts.map((p) => p.rev))), rmax = Math.max(...pts.map((p) => p.rev));
    const X = (h) => pl + (Math.log1p(h) / Math.log1p(hx)) * (W - pl - pr);
    const Y = (r) => H - pb - ((Math.log10(Math.max(r, rmin)) - Math.log10(rmin)) / Math.max(0.01, Math.log10(rmax) - Math.log10(rmin))) * (H - pt - pb);
    const q = S.rm.q.trim();
    const lab = new Set(pts.slice().sort((a, b) => b.rev - a.rev).slice(0, 6).concat(pts.slice().sort((a, b) => b.heat - a.heat).slice(0, 6))
      .concat(pts.filter((p) => rmQuadrant(p, mh, mr) === "rich").sort((a, b) => b.rev - a.rev).slice(0, 5)).map((p) => p.id));
    if (S.rm.sel) lab.add(S.rm.sel);
    let s = '<svg class="bz-rm-quad" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="热度和真钱四象限图">';
    const cx = X(mh), cy = Y(mr);
    s += '<line class="ax" x1="' + pl + '" y1="' + (H - pb) + '" x2="' + (W - pr) + '" y2="' + (H - pb) + '"/><line class="ax" x1="' + pl + '" y1="' + pt + '" x2="' + pl + '" y2="' + (H - pb) + '"/>' +
      '<line class="mid" x1="' + cx + '" y1="' + pt + '" x2="' + cx + '" y2="' + (H - pb) + '"/><line class="mid" x1="' + pl + '" y1="' + cy + '" x2="' + (W - pr) + '" y2="' + cy + '"/>';
    [["rich", pl + 8, pt + 14, "start"], ["both", W - pr - 8, pt + 14, "end"], ["cold", pl + 8, H - pb - 10, "start"], ["hot", W - pr - 8, H - pb - 10, "end"]].forEach(([k, x, y, a]) => {
      s += '<text class="qt q-' + k + '" x="' + x + '" y="' + y + '" text-anchor="' + a + '">' + RM_Q[k][0] + "</text>";
    });
    s += '<text class="axt" x="' + ((pl + W - pr) / 2) + '" y="' + (H - 14) + '" text-anchor="middle">市场雷达的新闻条数（' + esc(winText()) + '）→ 越右边说的人越多</text>' +
      '<text class="axt" transform="translate(16 ' + ((pt + H - pb) / 2) + ') rotate(-90)" text-anchor="middle">上市公司营收（对数）→ 越上面钱越多</text>';
    pts.sort((a, b) => b.rev - a.rev).forEach((p) => {
      const on = S.rm.sel === p.id, dim = q && !p.name.includes(q);
      s += '<g class="pt' + (on ? " sel" : "") + (dim ? " dim" : "") + '" data-rm="' + esc(p.id) + '"><title>' + esc(p.name + "（" + RM_Q[rmQuadrant(p, mh, mr)][0] + "）\n上市公司营收 " + rmYi(p.rev) + "\n新闻 " + p.heat + " 条") + "</title>" +
        '<circle cx="' + X(p.heat).toFixed(1) + '" cy="' + Y(p.rev).toFixed(1) + '" r="' + (on ? 8 : 5.5) + '" style="--c:' + p.c + '"/>' +
        (lab.has(p.id) && !dim ? '<text x="' + (lx(X(p.heat)) ? X(p.heat) - 9 : X(p.heat) + 9).toFixed(1) + '" y="' + (Y(p.rev) + 4).toFixed(1) + '"' + (lx(X(p.heat)) ? ' text-anchor="end"' : "") + ">" + esc(p.name) + "</text>" : "") + "</g>";
    });
    s += "</svg>";
    const cnt = { both: 0, hot: 0, rich: 0, cold: 0 };
    pts.forEach((p) => { cnt[rmQuadrant(p, mh, mr)]++; });
    return '<div class="bz-rm-quadwrap">' + s + '<div class="bz-rm-qleg">' + ["rich", "hot", "both", "cold"].map((k) =>
      '<p><b class="q-' + k + '">' + RM_Q[k][0] + "</b>（" + cnt[k] + " 个）：" + RM_Q[k][1] + "</p>").join("") +
      '<p class="bz-dim">中间两条线是所有行业的中位数。点一个圆点看它的体检卡。</p></div></div>';
  }
  function rmVerdict(id) {
    const pts = rmQuadPts(), p = pts.find((x) => x.id === id);
    if (!p || !S.ovm) return "";
    const k = rmQuadrant(p, rmMedian(pts.map((x) => x.heat)), rmMedian(pts.map((x) => x.rev)));
    return '<p class="bz-rm-verdict q-' + k + '"><b>' + RM_Q[k][0] + "</b>：" + RM_Q[k][1] + "（市场雷达" + esc(winText()) + " " + p.heat + " 条新闻）</p>";
  }
  function rmKpiHTML() {
    const d = S.rm.data;
    if (!d) return "";
    if (!d.kpi.length) return '<p class="bz-dim">统计局的数字还没取到。' + (d.updating && d.updating.running ? "正在取…" : "点下面「现在更新数据」。") + "</p>";
    return d.kpi.map((k) => '<div class="bz-rm-k"><span>' + esc(k.k) + "</span><b>" + (k.unit === "亿元" ? rmYi(k.v) + "元" : rmNum(k.v) + " " + esc(k.unit)) + "</b><small>" +
      esc(k.period) + " · 同比 " + rmPct(k.yoy) + (k.extra ? " · " + esc(k.extra) : "") + "</small></div>").join("");
  }
  function rmSrcHTML(kind) {
    const d = S.rm.data;
    if (!d) return "";
    const rows = d.sources.filter((s) => (kind === "auto" ? s.auto : !s.auto));
    let grp = null;                                                  // v199：交易平台按地区分组
    return '<table class="bz-ltab bz-rm-src"><thead><tr><th>信息源</th><th>看什么</th><th>怎么取</th><th>状态</th></tr></thead><tbody>' + rows.map((s) =>
      (s.crawl && s.rname && s.rname !== grp ? ((grp = s.rname), '<tr class="bz-rm-grp"><td colspan="4">' + esc(s.rname === "国内" ? "国内平台" : "国外 · " + s.rname) + "</td></tr>") : "") +
      "<tr><td class=\"nm\">" + (s.url ? '<a class="bz-link strong" href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.name) + "</a>" : "<b>" + esc(s.name) + "</b>") +
      '</td><td class="ds">' + esc(s.what) + '</td><td class="ds">' + esc(s.how) + "</td><td>" +
      (s.crawl ? '<small class="bz-dim">适用 ' + (s.fit || 0) + " 个行业，已抓 " + (s.done || 0) + " 个</small><br>" + (s.n_ok || s.n_bad ? '<span class="' + (s.last_ok ? "bz-rm-ok" : "bz-rm-bad") + '">' + (s.last_ok ? "✓ 抓到过 " + s.n_ok + " 次" : "还没抓到过") + "</span>" +
          (s.n_bad ? '<small class="bz-dim">，没抓到 ' + s.n_bad + " 次</small>" : "") + (s.via ? '<br><small class="bz-dim">管用的：' + esc(s.via) + "</small>" : "") +
          (s.login && rmNeedLogin(s.key.replace(/^tp_/, "")) ? "<br>" + rmLoginBtn(s.key.replace(/^tp_/, "")) : "") +
          (s.skip ? '<br><small class="bz-rm-bad">' + esc(s.skip) + "</small>" : s.err ? '<br><small class="bz-dim" title="' + esc(s.err) + '">上次：' + esc(s.err.slice(0, 40)) + "</small>" : "") : ('<span class="bz-dim">还没抓过：核实一个适用的行业，或点上面「交易平台全部抓一遍」</span>' + (s.login && rmNeedLogin(s.key.replace(/^tp_/, "")) ? "<br>" + rmLoginBtn(s.key.replace(/^tp_/, "")) : ""))) :
        !s.auto ? '<span class="bz-dim">核实时用</span>' : s.ok ? '<span class="bz-rm-ok">✓ ' + esc(s.period || "") + (s.n ? "，" + s.n + (s.key === "listed" ? " 家公司" : s.key === "concept" ? " 个赛道对上了" : " 项") : "") + '</span><br><small class="bz-dim">' + esc(ago(s.at)) + "查过</small>"
        + (s.warn ? '<br><small class="bz-rm-bad">⚠ ' + esc(s.warn) + "</small>" : "") + (s.key === "listed" && s.n_ind ? '<br><small class="bz-dim">归到 ' + s.n_ind + " 个二级行业</small>" : "") +
          (s.key === "concept" && s.miss && s.miss.length ? '<br><small class="bz-dim">没对上板块的赛道：' + esc(s.miss.map((x) => nameOf(x)).join("、")) + "</small>" : "")
        : s.at ? '<span class="bz-rm-bad">没取到</span><br><small class="bz-dim">' + esc(s.err || "") + "</small>" : '<span class="bz-dim">还没取</span>') + "</td></tr>").join("") + "</tbody></table>";
  }
  // v192：下拉框——软件里所有的行业（新兴赛道、一级、二级、三级细分），核实过的打勾
  function rmPickOptions() {
    if (!S.tax) return '<option value="">选一个行业…</option>';
    const done = {};
    ((S.rm.data && S.rm.data.checks) || []).forEach((c) => { if (c.gid) done[c.gid] = 1; });
    const o = (id, label) => '<option value="' + esc(id) + '"' + (S.rm.pick === id ? " selected" : "") + ">" + esc(label) + (done[id] ? " ✓" : "") +
      (rmBy(id).rev ? "　" + rmYi(rmBy(id).rev) : "") + "</option>";
    let h = '<option value="">选一个行业…（共 ' + (S.tax.counts ? S.tax.counts.l2 + S.tax.counts.l1 + S.tax.counts.tracks + (S.tax.counts.l3 || 0) : "") + " 个，✓ 是核实过的）</option>";
    h += '<optgroup label="新兴赛道">' + S.tax.tracks.map((t) => o(t.id, t.name)).join("") + "</optgroup>";
    S.tax.sectors.forEach((sec) => sec.l1.forEach((n) => {
      const d = S.byId[n];
      h += '<optgroup label="' + esc(sec.name + " · " + n) + '">' + o(n, "整个" + n) +
        d.subs.map((x) => o(x, nameOf(x)) + (S.byId[x].l3 || []).map((y) => o(y, "　└ " + nameOf(y))).join("")).join("") + "</optgroup>";
    }));
    return h;
  }
  function rmBatchScopes() {
    const t = S.tax, cut = Date.now() / 1000 - 30 * 86400, done = {};
    ((S.rm.data && S.rm.data.checks) || []).forEach((c) => { if (c.gid && c.created >= cut) done[c.gid] = 1; });
    const l2 = [];
    t.industries.forEach((i) => i.subs.forEach((x) => l2.push(x.id)));
    const trk = t.tracks.map((x) => x.id);
    const sc = [["all", "全部：新兴赛道 + 二级行业", trk.concat(l2)], ["trk", "只核实新兴赛道", trk], ["l2", "只核实二级行业", l2]];
    t.sectors.forEach((sec) => sc.push(["sec:" + sec.key, sec.name + "板块", l2.filter((x) => sec.l1.includes(S.byId[x].l1))]));
    return sc.map(([k, n, ids]) => ({ k: k, n: n, all: ids.length, todo: ids.filter((x) => !done[x]).length }));
  }
  function rmBatchHTML() {
    const b = S.rm.data && S.rm.data.batch;
    const hrs = (sec) => (sec >= 3600 ? (sec / 3600).toFixed(1).replace(/\.0$/, "") + " 小时" : Math.max(1, Math.round(sec / 60)) + " 分钟");
    let h = "";
    if (b && (b.running || b.stopping || b.paused)) {
      const pct = b.n ? Math.round((b.i / b.n) * 100) : 0;
      h += '<div class="bz-rm-bprog"><div class="bz-rm-bprog-h"><b>' + (b.running ? "正在一个个核实" : b.stopping ? "正在停…" : "暂停了") + "：" + esc(b.name) + "</b>" +
        '<span class="bz-dim">' + b.i + " / " + b.n + " · 成功 " + b.ok + (b.bad ? " · 没做成 " + b.bad : "") + (b.running ? " · 预计还要 " + hrs(b.eta) : "") + "</span></div>" +
        '<div class="bz-rm-bar"><i style="width:' + pct + '%"></i></div>' +
        (b.running && b.waiting ? '<p class="bz-dim">' + esc(b.waiting) + "</p>" : "") +
        (b.errs && b.errs.length ? '<p class="bz-dim">最近没做成的：' + b.errs.map((e) => esc(nameOf(e[0])) + "（" + esc(e[1]) + "）").join("；") + "</p>" : "") +
        '<div class="bz-btns">' + (b.running ? '<button type="button" class="bz-btn sm ghost" data-act="rm-batch-stop">停止</button>' :
          b.paused ? '<button type="button" class="bz-btn sm" data-act="rm-batch-resume">接着做（还剩 ' + (b.n - b.i) + " 个）</button>" +
            '<button type="button" class="bz-btn sm ghost" data-act="rm-batch-clear">不做了</button>' : "") + "</div></div>";
      return h;
    }
    if (b && b.done) h += '<p class="bz-rm-ok">上一次「' + esc(b.name) + "」做完了：成功 " + b.ok + " 个" + (b.bad ? "，没做成 " + b.bad + " 个" : "") + "。</p>";
    if (!S.rm.batchOpen || !S.tax) return h;
    const scs = rmBatchScopes(), cur = scs.find((x) => x.k === S.rm.bscope) || scs[0];
    const n = S.rm.btodo ? cur.todo : cur.all, per = S.rm.depth === "deep" ? 420 : 240;
    return h + '<div class="bz-rm-bset"><label>核实哪些<select class="bz-select" id="bzRmBScope">' + scs.map((x) =>
      '<option value="' + x.k + '"' + (x.k === cur.k ? " selected" : "") + ">" + esc(x.n) + "（" + x.all + " 个，还没核实的 " + x.todo + " 个）</option>").join("") + "</select></label>" +
      '<label class="bz-rm-chkbox"><input type="checkbox" id="bzRmBTodo"' + (S.rm.btodo ? " checked" : "") + "> 跳过 30 天内核实过的</label>" +
      '<p>要核实 <b>' + n + "</b> 个，按「" + (S.rm.depth === "deep" ? "深入" : "快速") + "」大约要 <b>" + hrs(n * per) + "</b>。会排队一个个来，一次只占一份 AI 池；" +
      "期间可以关掉这一页、做别的；关了软件会暂停，下次打开点「接着做」。</p>" +
      '<div class="bz-btns"><button type="button" class="bz-btn" data-act="rm-batch-start"' + (n ? "" : " disabled") + ">开始核实 " + n + " 个</button>" +
      '<button type="button" class="bz-btn ghost" data-act="rm-batch-close">取消</button></div></div>';
  }
  function rmChecksHTML() {
    const all = (S.rm.data && S.rm.data.checks) || [];
    if (!all.length) return '<p class="bz-dim">还没核实过。</p>';
    const cs = S.rm.allChecks ? all : all.slice(0, 9);
    return cs.map((c) => '<div class="bz-rm-chk"><div class="bz-rm-chk-h"><b>' + esc(c.name) + '</b><span class="bz-dim">' + esc(fmtTime(c.created)) + "</span>" +
      (c.gid ? '<button type="button" class="bz-link" data-rm="' + esc(c.gid) + '">在地图上看</button>' : "") + "</div>" +
      (c.summary ? "<p>" + esc(c.summary) + "</p>" : "") +
      '<p class="bz-dim">' + c.n + " 个数字，" + c.ok + " 个在原文里对上了" + (c.dims.length ? " · 有：" + c.dims.join("、") : "") + "</p>" +
      '<div class="bz-btns"><button type="button" class="bz-btn sm" data-rm-chk="' + esc(c.id) + '">看体检卡</button>' +
      (c.report ? '<button type="button" class="bz-btn sm ghost" data-rep="' + esc(c.report) + '">完整报告</button>' : "") +
      '<button type="button" class="bz-btn sm ghost" data-rm-redo="' + esc(c.gid || c.name) + '">重新核实</button>' +
      '<button type="button" class="bz-link" data-rm-del="' + esc(c.id) + '">删除</button></div></div>').join("") +
      (all.length > 9 ? '<p class="bz-rm-more"><button type="button" class="bz-link" data-act="rm-allchecks">' + (S.rm.allChecks ? "收起" : "显示全部 " + all.length + " 个") + "</button></p>" : "");
  }
  function rmFactsHTML(c) {
    if (!c || !c.facts || !c.facts.length) return "";
    return '<div class="bz-tablewrap"><table class="bz-ltab bz-rm-facts"><thead><tr><th>尺子</th><th>指标</th><th class="num">数值</th><th>时间</th><th>口径</th><th>核对</th></tr></thead><tbody>' +
      c.facts.map((f) => '<tr><td><span class="bz-rm-dim">' + esc(f.dim) + '</span></td><td class="ds">' + esc(f.metric) + (f.src ? '<span class="co">' +
        (f.url ? '<a class="bz-link" href="' + esc(f.url) + '" target="_blank" rel="noopener">' + esc(f.src || "出处") + "</a>" : esc(f.src)) + "</span>" : "") +
        '</td><td class="num"><b>' + esc(f.value) + "</b></td><td>" + esc(f.when) + '</td><td><span class="bz-rm-basis b-' + (RM_BASIS_CLS[f.basis] || "es") + '">' + esc(f.basis || "?") + "</span></td>" +
        '<td><span class="' + (f.ok ? "bz-rm-ok" : "bz-rm-bad") + '" title="' + (f.ok ? "这个数字在 AI 读到的网页或统计数据里找得到" : "原文里没找到这个数字：可能是 AI 换算的、记错的，用之前自己点出处核对") + '">' +
        esc(f.chk || (f.ok ? "原文有" : "没对上")) + "</span></td></tr>").join("") + "</tbody></table></div>";
  }
  function rmLine(label, html) { return '<div class="bz-rm-row"><span class="bz-rm-lab">' + label + '</span><div class="bz-rm-val">' + html + "</div></div>"; }
  function rmDetailHTML() {
    const id = S.rm.sel, d = S.byId[id];
    if (!d) return "";
    const it = S.rm.item && S.rm.item.id === id ? S.rm.item : null;
    const path = d.type === "l2" ? secName(d.sec) + " › " + d.l1 : d.type === "l1" ? secName(d.sec) + "板块" : "新兴赛道";
    let h = '<div class="bz-dt"><div class="bz-dt-top"><p class="bz-dt-path">' + esc(path) + '</p><button type="button" class="bz-x" data-act="rm-close" aria-label="关掉这一栏（Esc）" title="关掉（Esc）">×</button></div>' +
      "<h3>" + esc(d.name) + "</h3><p>" + esc(d.desc) + "</p>" + rmVerdict(id);
    if (!it) return h + loading() + "</div>";
    const a = it.listed, q = it.listed_q, chk = it.check;
    const facts = (dim) => ((chk && chk.facts) || []).filter((f) => f.dim === dim && f.chk !== "待核实");
    const factLine = (f) => "<p><b>" + esc(f.value) + "</b> " + esc(f.metric) + ' <span class="bz-rm-basis b-' + (RM_BASIS_CLS[f.basis] || "es") + '">' + esc(f.basis || "?") + "</span>" +
      '<small class="bz-dim">' + esc(f.when) + (f.ok ? " · 原文有" : " · 没对上原文") + "</small></p>";
    const nb = (src) => it.nbs.filter((x) => x.src === src);
    const nbLine = (x) => "<p>" + (x.unit === "亿元" ? "<b>" + rmYi(x.v) + "元</b>" : "<b>" + rmNum(x.v) + " 元</b>/人") + " " + esc(x.txt) + '<small class="bz-dim">统计局 · ' + esc(x.period) +
      " · 同比 " + rmPct(x.yoy) + (x.share != null ? " · 占消费支出 " + x.share + "%" : "") + (x.up ? " · 所在一级行业的" : "") + "</small></p>";
    let size = "";
    if (a) size += "<p><b>" + rmYi(a.rev) + "元</b> " + a.n + (d.type === "trk" ? " 家相关上市公司" : " 家 A 股公司") + esc(it.annual_name) + '营收合计<small class="bz-dim">' +
      (d.type === "trk" && a.boards ? "东方财富概念板块「" + esc(a.boards.join("」「")) + "」的成分股；这些公司不一定全靠这块赚钱，当作「这条赛道上的玩家有多大」看" : "上市公司") +
      " · 同比 " + rmPct(a.rev_yoy) + "</small></p>";
    nb("retail").concat(nb("ind")).forEach((x) => { size += nbLine(x); });
    facts("规模").concat(facts("交易")).forEach((f) => { size += factLine(f); });
    h += rmLine("规模", size || '<p class="bz-dim">没有直接对上的数字</p>');
    if (q || a) h += rmLine("增长", (q ? "<p>" + esc(it.latest_name) + "营收 <b>" + rmPct(q.rev_yoy) + "</b>，净利润 <b>" + rmPct(q.np_yoy) + "</b></p>" : "") +
      (a ? '<p class="bz-dim">' + esc(it.annual_name) + "营收 " + rmPct(a.rev_yoy) + "，净利润 " + rmPct(a.np_yoy) + "</p>" : ""));
    let prof = "";
    if (a) prof += "<p>净利率 <b>" + (a.nm == null ? "–" : a.nm + "%") + "</b>" + (a.gm != null ? "，毛利率中位数 <b>" + a.gm + "%</b>" : "") + '<small class="bz-dim">上市公司 · ' + esc(it.annual_name) + "</small></p>";
    nb("ind").forEach((x) => { if (x.margin != null) prof += "<p>营收利润率 <b>" + x.margin + "%</b> " + esc(x.name) + '<small class="bz-dim">统计局 · ' + esc(x.period) + "</small></p>"; });
    facts("利润").forEach((f) => { prof += factLine(f); });
    h += rmLine("利润", prof || '<p class="bz-dim">待核实</p>');
    let buy = "";
    nb("income").forEach((x) => { buy += nbLine(x); });
    facts("购买力").forEach((f) => { buy += factLine(f); });
    if (!buy && it.income && it.income.income) buy = "<p>全国居民人均可支配收入 <b>" + rmNum(it.income.income) + ' 元</b><small class="bz-dim">统计局 · ' + esc(it.income.period || "") + "（这个行业没有单独的消费类目）</small></p>";
    h += rmLine("购买力", buy || '<p class="bz-dim">待核实</p>');
    const tr = it.trade, tp = it.trade_plan || {};
    let trade = "";
    if (tr) trade = tr.lines.map((x) => "<p" + (x.ok ? "" : ' class="bz-dim"') + ">" + esc(x.txt) + (!x.ok && rmNeedLogin(x.p) ? " " + rmLoginBtn(x.p, "ghost") : "") + (x.ok ? '<small class="bz-dim">爬虫 · ' + esc(x.via || "") + " · " + esc(ago(tr.at)) +
      (x.url ? ' · <a class="bz-link" href="' + esc(x.url) + '" target="_blank" rel="noopener">去平台看</a>' : "") + "</small>" : "") + "</p>").join("") +
      (tr.ccgp && tr.ccgp.length ? '<details class="bz-rm-cg"><summary>政府采购网最近的公告</summary>' + tr.ccgp.map((c) => '<p><a class="bz-link" href="' + esc(c.u) + '" target="_blank" rel="noopener">' + esc(c.t) +
        "</a><small class=\"bz-dim\">" + esc([c.d, c.buyer, c.amt ? (c.amt_k || "金额") + " " + c.amt + " 万元" : ""].filter(Boolean).join(" · ")) + "</small></p>").join("") + "</details>" : "");
    trade += it.trade_running ? '<p class="bz-dim">爬虫正在抓「' + esc(tp.kw || "") + "」…</p>" :
      '<p><button type="button" class="bz-link" data-act="rm-trade">' + (tr ? "重新抓一遍" : "去平台抓「" + esc(tp.kw || d.name) + "」") + "</button>" +
      '<small class="bz-dim">会去：' + esc((tp.plats || []).map(rmPlatName).join("、")) + "（不用 AI，几分钟）</small></p>" +
      ((tp.plats || []).filter(rmNeedLogin).length ? '<p class="bz-rm-needlogin"><small class="bz-dim">这几个要登录才会去抓：</small>' + (tp.plats || []).filter(rmNeedLogin).map((p) => rmLoginBtn(p, "ghost")).join("") + "</p>" : "");
    h += rmLine("交易", trade);
    const cust = facts("客户").map(factLine).join("");
    h += rmLine("客户", cust || '<p class="bz-dim">待核实：统计局和财报里没有「多少人在买」，点下面「AI 联网核实」去查。</p>');
    h += '<div class="bz-btns"><button type="button" class="bz-btn" data-act="rm-check-sel">' + (chk ? "重新核实" : "AI 联网核实") + "</button>" +
      '<button type="button" class="bz-btn ghost" data-act="rm-map">在行业地图上看</button>' +
      (d.type !== "trk" ? '<button type="button" class="bz-btn ghost" data-run-ind="' + esc(id) + '">联网研究</button>' : "") + "</div>";
    if (chk) h += "<h4>AI 核实（" + esc(fmtTime(chk.created)) + "）</h4>" + (chk.summary ? "<p>" + esc(chk.summary) + "</p>" : "") +
      '<p class="bz-dim">' + chk.facts.length + " 个数字，" + chk.facts.filter((f) => f.ok).length + " 个在原文里对上了（上面四行里标着）</p>" +
      '<div class="bz-btns"><button type="button" class="bz-btn sm" data-rm-chk="' + esc(chk.id) + '">看体检卡和出处</button>' +
      (chk.report ? '<button type="button" class="bz-btn sm ghost" data-rep="' + esc(chk.report) + '">完整报告</button>' : "") + "</div>";
    if (a && a.top && a.top.length) h += "<h4>营收最多的上市公司（" + esc(it.annual_name) + '）</h4><ol class="bz-rm-top">' + a.top.map((t) =>
      "<li><span>" + esc(t[0]) + "</span><b>" + rmYi(t[1]) + '</b><small class="bz-dim">净利 ' + rmYi(t[2]) + "</small></li>").join("") + "</ol>";
    if (d.type === "trk") h += "<h4>相关行业</h4>" + '<div class="bz-chips">' + (d.rel || []).filter((x) => S.byId[x]).map((x) => '<button type="button" class="bz-chip" data-rm="' + esc(x) + '">' + esc(nameOf(x)) +
      (rmBy(x).rev ? " <b>" + rmYi(rmBy(x).rev) + "</b>" : "") + "</button>").join("") + "</div>";
    h += '<p class="bz-hint">上市公司的数字只是头部玩家的盘子，不等于整个市场；统计局的数字是一整个统计大类的合计，可能比这个行业宽。</p>';
    return h + "</div>";
  }
  function rmLegend() {
    const m = S.rm.metric, L = (S.rm.data && S.rm.data.listed) || {};
    if (m === "verified") {
      const n = Object.values((S.rm.data && S.rm.data.by) || {}).filter((b) => b.chk).length;
      return "格子里是 AI 联网核实出来的市场规模（行业报告、统计局、交易平台的数字，" + n + " 个核实过）；颜色越深越大，「?」是这个数字在原文里没对上、要自己核对；灰的是还没核实。" +
        "这个数和「规模」（上市公司营收）口径不同：一个是整个市场，一个是头部公司的盘子。";
    }
    if (m === "quad") return "四块：钱多话少、又热又大、话多钱少、又冷又小。热度用的是市场雷达「" + winText() + "」的新闻条数（在市场雷达那边换时间段）。";
    return (m === "size" ? "颜色越深，上市公司" + (L.annual_name || "") + "营收合计越多（不同板块不同颜色）。" : m === "growth" ? "颜色越深，营收增长越快（" + (L.latest_name || "最新一期") + "同比；红字是下降）。" :
      "颜色越深，净利率越高（净利润 ÷ 营收，" + (L.annual_name || "") + "）。") + " 带小圆圈、下面写着「✓ 核实」的是 AI 核实过的（核实出来的市场规模；带「?」的没对上原文）。";
  }
  function renderReal() {
    segSync("rmmetric", S.rm.metric); segSync("rmview", S.rm.view); segSync("rmdepth", S.rm.depth);
    const d = S.rm.data;
    $("bzRmKpi").innerHTML = rmKpiHTML();
    const up = d && d.updating && d.updating.running;
    const ub = $("bzRmUpdBtn");
    if (ub) {
      const running = !!(up || S.rm.updWait);
      ub.disabled = running;
      ub.classList.toggle("busy", running);
      ub.innerHTML = running ? '<span class="bz-spin" aria-hidden="true"></span>正在更新…' + (up && d.updating.stage ? "（" + esc(d.updating.stage.replace(/^正在/, "").replace(/…$/, "")) + "）" : "") : "现在更新数据";
    }
    rmReportRender();
    rmRunRender();
    rmTradeRender();
    $("bzRmUpd").textContent = !d ? (S.rm.err ? "读不到：" + S.rm.err : "正在读…") : up ? "正在更新：" + (d.updating.stage || "…") :
      d.updated ? "数据" + ago(d.updated) + "更新过；超过 12 小时没更新，打开这一页会自动更新。" : "还没取过数据。";
    const vb = root.querySelector('.bz-seg[data-seg="rmview"]');
    if (vb) vb.hidden = S.rm.metric === "quad";
    $("bzRmLegend").textContent = rmLegend();
    const main = $("bzRmMain");
    if (!S.tax || !d) main.innerHTML = loading(S.taxErr || S.rm.err ? "读不到：" + (S.taxErr || S.rm.err) : "");
    else {
      const sc = $("bzScroll").scrollTop;
      main.innerHTML = S.rm.metric === "quad" ? rmQuadHTML() : S.rm.view === "list" ? rmListHTML() : rmMapHTML();
      $("bzScroll").scrollTop = sc;
    }
    rmRenderDetail();
    $("bzRmChecks").innerHTML = rmChecksHTML();
    $("bzRmBatch").innerHTML = rmBatchHTML();
    const pk = $("bzRmPick");
    if (pk && document.activeElement !== pk) pk.innerHTML = rmPickOptions();
    $("bzRmSrcAuto").innerHTML = rmSrcHTML("auto");
    rmTabsRender();
  }
  function rmRenderDetail() {
    const el = $("bzRmDetail"), wrap = $("bzRmWrap");
    if (!el) return;
    const on = !!(S.rm.sel && S.byId[S.rm.sel]);
    el.hidden = !on; wrap.classList.toggle("nodet", !on);
    el.innerHTML = on ? rmDetailHTML() : "";
  }
  async function rmLoad(force) {
    const wasUpd = !!(S.rm.data && S.rm.data.updating && S.rm.data.updating.running);
    try {
      S.rm.data = await api("/biz/real"); S.rm.err = ""; S.rm.at = Date.now();
    } catch (e) { S.rm.err = e.message; }
    const nowUpd = !!(S.rm.data && S.rm.data.updating && S.rm.data.updating.running);
    const ls = (S.rm.data && S.rm.data.logins && S.rm.data.logins.sites) || {};          // v198：登录好了提示一下
    const tt = (S.rm.data && S.rm.data.ttry) || {};                                          // v201：试抓做完了提示一下
    Object.keys(S.rm.tryWait || {}).forEach((k) => { if (tt[k] && !tt[k].running && tt[k].at) { delete S.rm.tryWait[k]; toast((tt[k].ok ? "✓ 试抓成功：" : "✗ 试抓没成功：") + (tt[k].txt || "").slice(0, 70)); } });
    Object.keys(ls).forEach((k) => { if (S.rm.lwait && S.rm.lwait[k] && !ls[k].waiting) { delete S.rm.lwait[k]; toast(ls[k].logged ? ls[k].name + " 登录好了，窗口已经收起来；之后爬虫抓" + ls[k].name + "会用它。" : ls[k].name + " 的登录窗口等太久，先收起来了，需要的话再点一次登录。"); } });
    if (S.rm.updWait && !nowUpd && (wasUpd || (S.rm.data && S.rm.data.report && S.rm.data.report.at * 1000 > Date.now() - 120000))) {
      S.rm.updWait = false; S.rm.showReport = true;                     // v193：更新做完了 → 出汇报
      const rp = S.rm.data.report;
      toast(rp ? "更新完了：" + rp.n_ok + " / " + rp.n + " 个信息源取到了，汇报在页面上方。" : "更新完了。");
    }
    if (S.pane === "real") renderReal();
    clearTimeout(S.rm.timer);
    const bt = S.rm.data && S.rm.data.batch;
    if (bt && (bt.running || bt.stopping) && !(S.job && S.job.running)) pollJob();   // v195：全部核实是后台自己开的任务，界面要自己去问进度（不然看不到「正在核实」和实时画面）
    if (S.rm.data && S.rm.data.updating && S.rm.data.updating.running) S.rm.timer = setTimeout(() => rmLoad(), 3000);
    else if (S.rm.updWait) S.rm.timer = setTimeout(() => rmLoad(), 1500);
    else if (Object.values((S.rm.data && S.rm.data.logins && S.rm.data.logins.sites) || {}).some((x) => x.waiting) || Object.keys(S.rm.lwait || {}).length) S.rm.timer = setTimeout(() => rmLoad(), 3000);   // v198
    else if (rmTBusy() && S.pane === "real") S.rm.timer = setTimeout(() => rmLoad(), 2500);   // v201：抓取 / 试抓时 2.5 秒刷一次，看得到进度
    else if (((bt && (bt.running || bt.stopping)) || (S.rm.data && S.rm.data.tbatch && S.rm.data.tbatch.running)) && S.pane === "real") S.rm.timer = setTimeout(() => rmLoad(), 8000);   // v192
    else if (S.pane === "real") S.rm.timer = setTimeout(() => { if (S.pane === "real") rmLoad(); }, 30000);   // v195：开着这一页就隔半分钟看一眼（后台自己开始的任务也能看到）
    else if (force && S.rm.sel) rmSelect(S.rm.sel, true);
  }
  async function rmSelect(id, keep) {
    if (!S.byId[id]) return;
    if (S.rm.sel === id && !keep) { S.rm.sel = ""; rmRenderDetail(); root.querySelectorAll("#bzRmMain .sel").forEach((e) => e.classList.remove("sel")); return; }
    S.rm.sel = id; store.set("rmSel", id);
    root.querySelectorAll("#bzRmMain .sel").forEach((e) => e.classList.remove("sel"));
    root.querySelectorAll('#bzRmMain [data-rm="' + CSS.escape(id) + '"], #bzRmMain tr[data-row="' + CSS.escape(id) + '"]').forEach((e) => e.classList.add("sel"));
    if (S.rm.metric === "quad") renderReal(); else rmRenderDetail();
    const det = $("bzRmDetail");
    if (det && window.innerWidth < 1100) det.scrollIntoView({ block: "start", behavior: "smooth" });
    try {
      const r = await api("/biz/real/item?id=" + enc(id));
      if (S.rm.sel === id) {
        S.rm.item = r; rmRenderDetail();
        clearTimeout(S.rm.ttimer);
        if (r.trade_running) S.rm.ttimer = setTimeout(() => { if (S.rm.sel === id && S.pane === "real") rmSelect(id, true); }, 5000);   // v192：爬虫在抓，抓完自动显示
      }
    } catch (e) { /* 读不到就算了 */ }
  }
  function rmEnsure() {
    pollJob();                                                     // v195
    if (!S.rm.data || Date.now() - S.rm.at > 60000) rmLoad();
    if (!S.ovm) refreshOverview("market");
    if (S.rm.sel && !(S.rm.item && S.rm.item.id === S.rm.sel)) rmSelect(S.rm.sel, true);
  }
  // v193：更新完的汇报
  function rmReportRender() {
    const el = $("bzRmReport"), rp = S.rm.data && S.rm.data.report;
    if (!el) return;
    if (!S.rm.showReport || !rp) { el.hidden = true; el.innerHTML = ""; return; }
    el.hidden = false;
    el.innerHTML = '<div class="bz-rm-report-h"><b>' + (rp.n_ok === rp.n ? "✓ 更新完了" : "更新完了，有 " + (rp.n - rp.n_ok) + " 个没取到") + "</b>" +
      '<span class="bz-dim">' + esc(fmtTime(rp.at)) + " · 用了 " + dur(rp.secs) + "</span>" +
      '<button type="button" class="bz-x" data-act="rm-report-close" aria-label="关掉汇报" title="关掉">×</button></div>' +
      rp.lines.map((x) => '<p class="' + (x.ok ? (x.new ? "bz-rm-ok" : "") : "bz-rm-bad") + '">' + (x.ok ? (x.new ? "● " : "○ ") : "✗ ") + esc(x.txt) + "</p>" +
        (x.warn ? '<p class="bz-rm-bad">　⚠ ' + esc(x.warn) + "（把这一行截图发给开发的人，好按真实数据修）</p>" : "")).join("") +
      '<p class="bz-dim">● 有新数据　○ 和上次一样（统计局每月、财报每季度才出新的一期）</p>';
  }
  // v193：正在核实的那一个：标题点一下在下面展开 AI 实时画面
  function rmRunRender() {
    const el = $("bzRmRun");
    if (!el) return;
    rmTabsRender();
    const j = S.job, mine = !!(j && j.running && j.kind === "real"), bt = S.rm.data && S.rm.data.batch;
    if (!mine) {
      if (el.dataset.on) { el.innerHTML = ""; el.dataset.on = ""; bzLivePlace(); }
      return;
    }
    const step = (j.steps || [])[Math.max(0, (j.step || 1) - 1)] || "";
    const sub = (bt && bt.running ? "全部核实 第 " + Math.min(bt.n, bt.i + 1) + " / " + bt.n + " 个 · " : "") + (step ? "第 " + j.step + " 步「" + step + "」 · " : "") + (j.stage || "…");
    const ttl = (j.title || "").replace(/^真实市场核实：/, "");
    if (el.dataset.on === ttl) {                                       // 同一个任务：只改文字，实时画面不动
      const s1 = el.querySelector(".bz-rm-run-s");
      if (s1) s1.textContent = sub;
      return;
    }
    el.dataset.on = ttl;
    rmTabsRender();
    el.innerHTML = '<button type="button" class="bz-rm-run-t cx-ail-tg" data-ail-toggle="biz"><span class="bz-spin" aria-hidden="true"></span>' +
      "<b>正在核实：" + esc(ttl) + '</b><span class="cx-ail-caret">' + (window.cxAiLive ? window.cxAiLive.caret("biz") : "") + "</span></button>" +
      '<p class="bz-rm-run-s">' + esc(sub) + "</p>" +
      '<div class="cx-ail-slot" id="bzRmLive" hidden></div>';
    bzLivePlace();
  }
  // v198：京东 / 1688 登录、国外平台开关
  // v201：交易平台抓取——一个操作栏 + 实时进度 + 一张全世界平台总表
  const RM_TF = [["", "全部"], ["sw", "软件会抓"], ["login", "要登录的"], ["ok", "抓到过"], ["bad", "还没抓到"], ["self", "只能自己看"], ["ch", "还有别的拿数据办法"]];
  const RM_CHK = { "官方接口": "gov", "联盟接口": "aff", "现成爬虫": "act", "数据服务": "paid", "卖家后台": "sel" };
  function rmChHTML(x) {                                              // v203：这个平台还能从哪拿数据（官方接口、联盟接口、现成爬虫、数据服务、卖家后台）
    if (!x.ch || !x.ch.length) return "";
    const ap = !!(S.rm.data && S.rm.data.trade_cfg && S.rm.data.trade_cfg.apify && S.rm.data.trade_cfg.apify.on);
    return '<details class="bz-rm-ch"><summary>还能从哪拿（' + x.ch.length + "）</summary><ul>" + x.ch.map((c) =>
      '<li><span class="bz-rm-chk k-' + (RM_CHK[c.k] || "x") + '">' + esc(c.k) + '</span><a class="bz-link" href="' + esc(c.u) + '" target="_blank" rel="noopener">' + esc(c.n) + "</a>" +
      '<small class="bz-dim">' + esc(c.w) + "</small>" + (c.f === "done" ? '<small class="bz-rm-ok">✓ 软件在用</small>' :
        c.f === "apify" ? (ap ? '<small class="bz-rm-ok">✓ 软件在用（Apify）</small>' : '<small class="bz-dim">（填了 Apify 令牌，软件就会用）</small>') : "") + "</li>").join("") + "</ul></details>";
  }
  const rmSpin = '<span class="bz-spin" aria-hidden="true"></span>';
  const rmShort = (n) => String(n || "").replace(/（.*?）/g, "").trim();
  function rmTBusy() {
    const d = S.rm.data || {};
    return !!((d.tbatch && d.tbatch.running) || (d.tlive && d.tlive.now && d.tlive.now.length) ||
      Object.values(d.ttry || {}).some((x) => x.running) || Object.keys(S.rm.tryWait || {}).length);
  }
  function rmTData() {
    const d = S.rm.data || {}, src = {}, now = {}, nowUrl = {};
    (d.sources || []).forEach((x) => { if (x.crawl) src[x.key.replace(/^tp_/, "")] = x; });
    ((d.tlive && d.tlive.now) || []).forEach((n) => n.plats.forEach((q) => { if (q[1] === "run") { now[q[0]] = n.kw; nowUrl[q[0]] = q[3] || ""; } }));
    return { d: d, L: (d.logins && d.logins.sites) || {}, vf: (d.logins && d.logins.verify) || {}, src: src, now: now, nowUrl: nowUrl, tr: d.ttry || {},
      off: new Set((d.trade_cfg || {}).off || []) };
  }
  function rmTMatch(x, T, F) {
    const s = x.key && T.src[x.key];
    if (F === "sw") return !!s;
    if (F === "login") return x.a === "login";
    if (F === "ok") return !!(s && s.n_ok);
    if (F === "bad") return !!(s && !s.n_ok);
    if (F === "self") return !s;
    if (F === "ch") return !!(x.ch && x.ch.length);
    return true;
  }
  function rmTRows(T) {
    const c = S.rm.cat, R = S.rm.catR || "", K = S.rm.catK || "", F = S.rm.tf || "";
    return c ? c.rows.filter((x) => (!R || x.r === R) && (!K || x.k === K) && rmTMatch(x, T, F)) : [];
  }
  function rmTActHTML() {
    const d = S.rm.data || {}, LG = d.logins || {}, L = LG.sites || {}, tb = d.tbatch, B = LG.batch;
    const notIn = (LG.order || []).filter((k) => !(L[k] || {}).logged);
    let h = '<div class="bz-rm-tbtns">';
    h += S.rm.tallBusy ? '<button type="button" class="bz-btn" disabled>' + rmSpin + "正在启动…</button>" :
      tb && tb.running ? '<button type="button" class="bz-btn ghost" data-act="rm-tstop"' + (tb.stop ? " disabled" : "") + ">" + (tb.stop ? "正在停…" : "■ 停止抓取") + "</button>" :
      '<button type="button" class="bz-btn" data-act="rm-tall">▶ 所有行业抓一遍</button>';
    if (!(B && B.left && B.left.length)) h += notIn.length ? '<button type="button" class="bz-btn ghost" data-act="rm-login-all">一键登录全部（' + notIn.length + " 个没登录）</button>" :
      '<span class="bz-rm-ok">✓ 要登录的平台都登录了</span><button type="button" class="bz-link" data-act="rm-login-all" data-force="1">全部重新登录</button>';
    return h + '</div><p class="bz-dim bz-rm-thelp">下面每个平台：<b>勾上</b>就会去抓（「所有行业抓一遍」和 AI 核实时用）；点<b>「试抓」</b>马上用右边的词抓一下，几十秒出结果；要登录的点<b>「登录」</b>，扫码一次一直能用。' +
      (LG.proxy === false ? "　<b>注意：</b>软件设置里没配代理，国外平台可能打不开。" : "") + "</p>";
  }
  function rmTLiveHTML() {
    const d = S.rm.data || {}, LG = d.logins || {}, tb = d.tbatch, B = LG.batch, lv = d.tlive || {};
    const hrs = (sec) => (sec >= 3600 ? (sec / 3600).toFixed(1).replace(/\.0$/, "") + " 小时" : Math.max(1, Math.round(sec / 60)) + " 分钟");
    let h = "";
    if (B && B.left && B.left.length) h += '<div class="bz-rm-lbatch">' + rmSpin + "<b>一键登录进行中（" + B.done + "/" + B.n + "）</b>：弹出来的 Chrome 里开了 " + B.n +
      " 个标签页，现在在前面的是 <b>" + esc(B.cur) + "</b>，登录好会自动跳到下一个" + (B.left.length > 1 ? "（后面还有：" + esc(B.left_names.slice(1).join("、")) + "）" : "") + "。不想登的直接关掉那个标签页。</div>";
    const running = tb && tb.running, m = S.rm.tallMsg;
    if (m && !running && Date.now() - m.at < 10 * 60000) h += '<div class="bz-rm-tmsg"><span>' + esc(m.txt) + "</span>" +
      (m.zero ? '<button type="button" class="bz-btn sm" data-act="rm-tall" data-fresh="0">全部重新抓（不跳过）</button>' : "") + '<button type="button" class="bz-link" data-act="rm-tmsg-x">知道了</button></div>';
    if (running) h += '<div class="bz-rm-tlive"><p>' + rmSpin + "<b>正在抓：" + esc(tb.cur_name || "…") + "</b>　第 " + Math.min(tb.n, tb.i + 1) + " / " + tb.n + " 个行业 · 抓到 " + tb.ok +
      (tb.bad ? " · 没抓到 " + tb.bad : "") + " · 还要约 " + hrs(tb.eta) + '</p><div class="bz-rm-bar"><i style="width:' + (tb.n ? Math.round((tb.i / tb.n) * 100) : 0) + '%"></i></div></div>';
    else if (tb && tb.ended && Date.now() / 1000 - tb.ended < 86400) h += '<p class="bz-dim bz-rm-tlast">上次「' + esc(tb.name) + "」" + esc(ago(tb.ended)) + "抓完了：抓到 " + tb.ok + " 个行业，没抓到 " + tb.bad + " 个" + (tb.skipped ? "，跳过 " + tb.skipped + " 个 3 天内抓过的" : "") + "。</p>";
    (lv.now || []).forEach((n) => {
      h += '<div class="bz-rm-pchips"><span class="lab">「' + esc(n.kw) + "」正在各个平台上搜（点一下打开它的搜索页）：</span>" + n.plats.map((q) =>
        (q[3] ? '<a class="pc ' + q[1] + '" href="' + esc(q[3]) + '" target="_blank" rel="noopener" data-open="1" title="打开' + esc(rmShort(q[2])) + '搜「' + esc(n.kw) + '」的页面">' : '<span class="pc ' + q[1] + '">') +
        (q[1] === "run" ? rmSpin : q[1] === "ok" ? "✓ " : q[1] === "bad" ? "✗ " : q[1] === "skip" ? "– " : "") + esc(rmShort(q[2])) + (q[3] ? "</a>" : "</span>")).join("") + "</div>";
    });
    const feed = (lv.feed || []).filter((f) => running || (lv.now || []).length || Date.now() / 1000 - f.at < 600);
    if (feed.length) h += '<div class="bz-rm-feed"><b>刚抓到的</b>' + feed.slice(0, 8).map((f) => '<p class="' + (f.ok ? "" : "bad") + '"><span>' + hhmm(f.at).slice(0, 5) + "</span>" +
      (f.ok ? "✓ " : "✗ ") + esc(f.txt) + (f.url ? ' <a class="bz-link" href="' + esc(f.url) + '" target="_blank" rel="noopener" data-open="1">打开看看</a>' : "") + "</p>").join("") + "</div>";
    return h;
  }
  function rmTStatus(x, T) {
    const s = x.key && T.src[x.key];
    if (!s) return '<span class="bz-rm-acc a-' + esc(x.a) + '">' + esc(x.an) + '</span><br><small class="bz-dim">' + esc(x.why || "") + "</small>";
    const tr = T.tr[x.key], k = esc(x.key), apf = T.d.trade_cfg && T.d.trade_cfg.apify;
    let lg = T.L[x.key], h = "";
    if (lg && !lg.logged && !lg.waiting && apf && apf.on && (apf.keys || []).includes(x.key)) {          // v203：Apify 能抓的，不登录也行
      h += '<span class="bz-rm-ok">不用登录：交给 Apify 抓</span> <button type="button" class="bz-link" data-rm-login="' + k + '">（也可以登录）</button>';
      lg = null;
    } else if (lg) {
      h += lg.waiting ? '<span class="bz-rm-bad">' + rmSpin + (lg.mode === "verify" ? "验证窗口开着，过一下验证…" : "登录窗口开着，等你登录…") + "</span>" :
        lg.verify ? '<span class="bz-rm-bad">要过一下验证</span> <button type="button" class="bz-btn sm" data-rm-verify="' + k + '">去验证</button>' :
        lg.logged ? '<span class="bz-rm-ok">✓ 已登录</span>' + (lg.today ? ' <small class="bz-dim">今天搜了 ' + lg.today + "/" + (lg.cap || 100) + "</small>" : "") + ' <button type="button" class="bz-link" data-rm-logout="' + k + '">退出</button>' :
        (lg.expired ? '<span class="bz-rm-bad">登录过期了</span> ' : '<span class="bz-dim">要登录才抓</span> ') + '<button type="button" class="bz-btn sm" data-rm-login="' + k + '">登录' + esc(lg.name) + "</button>" +
          (lg.hint ? '<br><small class="bz-dim">' + esc(lg.hint) + "</small>" : "");
    } else if (!h) h += '<span class="bz-rm-acc a-' + esc(x.a) + '">' + esc(x.an) + "</span>";
    const vf = !lg && T.vf[x.key];                                                               // v202：不用登录的平台弹了验证
    if (vf) h += vf.waiting ? '<div class="bz-rm-bad">' + rmSpin + "验证窗口开着，在弹出的 Chrome 里过一下验证…</div>" :
      '<div><span class="bz-rm-bad">弹了滑块 / 验证码</span> <button type="button" class="bz-btn sm" data-rm-verify="' + k + '">去验证</button></div>';
    const lnk = (u, t) => (u ? ' <a class="bz-link" href="' + esc(u) + '" target="_blank" rel="noopener" data-open="1">' + t + "</a>" : "");
    if (T.now[x.key]) h += '<div class="bz-rm-now">' + rmSpin + "正在抓「" + esc(T.now[x.key]) + "」…" + lnk(T.nowUrl[x.key], "打开看看") + "</div>";
    if (tr && tr.running) h += '<div class="bz-rm-now">' + rmSpin + "正在试抓「" + esc(tr.kw) + "」…（几十秒）" + lnk(tr.url, "打开看看") + "</div>";
    else if (tr && tr.at) h += '<div class="bz-rm-tryres ' + (tr.ok ? "bz-rm-ok" : "bz-rm-bad") + '" title="' + esc((tr.steps || []).join("\n")) + '">' + (tr.ok ? "✓ 试抓「" : "✗ 试抓「") +
      esc(tr.kw) + "」" + (tr.ok ? "成功：" : "没成功：") + esc((tr.txt || "").replace(/^[^：]+：/, "").slice(0, 110)) + "</div>" + (tr.url ? '<div>' + lnk(tr.url, "打开它的搜索页看看 ↗") + "</div>" : "");
    else if (s.n_ok || s.n_bad) h += '<div><small class="' + (s.n_ok ? "bz-dim" : "bz-rm-bad") + '">' + (s.n_ok ? "抓到过 " + s.n_ok + " 次" : "还没抓到过") + (s.n_bad ? "，没抓到 " + s.n_bad + " 次" : "") +
      (s.n_ok && s.via ? "（管用的：" + esc(s.via) + "）" : "") + "</small>" + (!s.n_ok && s.err ? '<br><small class="bz-dim" title="' + esc(s.err) + '">原因：' + esc(s.err.slice(0, 60)) + "</small>" : "") + "</div>";
    else h += '<div><small class="bz-dim">还没抓过</small></div>';
    if (s.skip && !/要先登录/.test(s.skip)) h += '<div><small class="bz-rm-bad">' + esc(s.skip) + "</small></div>";
    if (!(lg && !lg.logged) && !(tr && tr.running)) h += '<button type="button" class="bz-btn sm ghost bz-rm-trybtn" data-rm-try="' + k + '">试抓</button>';
    return h;
  }
  function rmTTableHTML() {
    const c = S.rm.cat;
    if (!c) return loading(S.rm.catErr ? "读不到平台表：" + S.rm.catErr : "正在读平台表…");
    const T = rmTData(), rows = rmTRows(T), R = S.rm.catR || "", K = S.rm.catK || "", F = S.rm.tf || "";
    const chip = (attr, v, label, on) => '<button type="button" class="' + (on ? "on" : "") + '" data-' + attr + '="' + esc(v) + '">' + esc(label) + "</button>";
    return '<div class="bz-rm-thead">' + rmTHeadHTML(T, rows) + "</div>" +
      (rows.length ? '<table class="bz-ltab bz-rm-catt"><thead><tr><th class="on">抓</th><th>平台</th><th>国家 / 地区</th><th>类型</th><th>能看到什么</th><th class="st">状态</th></tr></thead><tbody>' +
        rows.map((x) => {
          const s = x.key && T.src[x.key];
          return '<tr class="' + (s ? (T.off.has(x.key) ? "off" : "") : "self") + '"><td class="on">' + (s ? '<input type="checkbox" data-rm-on="' + esc(x.key) + '"' + (T.off.has(x.key) ? "" : " checked") +
            ' aria-label="抓不抓' + esc(x.n) + '">' : "") + '</td><td class="nm"><a class="bz-link strong" href="' + esc(x.u) + '" target="_blank" rel="noopener">' + esc(x.n) + "</a></td><td>" +
            esc(x.c || x.rn) + '</td><td class="ds">' + esc(x.k) + '</td><td class="ds">' + esc(x.w) + rmChHTML(x) + '</td><td class="st">' + rmTStatus(x, T) + "</td></tr>";
        }).join("") + "</tbody></table>" : empty("这个筛选下没有平台。"));
  }
  function rmTHeadHTML(T, rows) {
    const c = S.rm.cat, R = S.rm.catR || "", K = S.rm.catK || "", F = S.rm.tf || "";
    const chip = (attr, v, label, on) => '<button type="button" class="' + (on ? "on" : "") + '" data-' + attr + '="' + esc(v) + '">' + esc(label) + "</button>";
    const sw = rows.filter((x) => x.key && T.src[x.key]);
    return '<div class="bz-rm-tfilt"><div class="bz-rm-chips"><span class="lab">看哪些</span>' +
      RM_TF.map((f) => chip("rm-tf", f[0], f[1] + " " + c.rows.filter((x) => rmTMatch(x, T, f[0])).length, F === f[0])).join("") + "</div>" +
      '<div class="bz-rm-chips"><span class="lab">地区</span>' + chip("rm-catr", "", "全部", !R) + c.regions.map((g) => chip("rm-catr", g.k, g.n, R === g.k)).join("") + "</div>" +
      '<div class="bz-rm-chips"><span class="lab">类型</span>' + chip("rm-catk", "", "全部", !K) + c.kinds.map((k) => chip("rm-catk", k, k, K === k)).join("") + "</div></div>" +
      '<p class="bz-dim bz-rm-tbulk">列出 ' + rows.length + " 个平台" + (sw.length ? "，其中软件会抓的 " + sw.length + ' 个：<button type="button" class="bz-link" data-act="rm-ton">这些都抓</button> · <button type="button" class="bz-link" data-act="rm-toff">这些都不抓</button>' : "") + "</p>";
  }
  async function rmCatLoad() {
    S.rm.catLoading = true;
    const r = await api("/biz/real/catalog").catch((e) => ({ ok: false, error: e.message }));
    S.rm.catLoading = false;
    if (r.ok) S.rm.cat = r; else S.rm.catErr = r.error || "读不到";
    rmCatRender();
  }
  // 实时刷新时只改变了的地方（整张表重画的话，正好点在按钮上时会点空）
  function rmSetHTML(el, html) { if (el && el.__h !== html) { el.innerHTML = html; el.__h = html; } }
  function rmCatRender() {
    const t = $("bzRmTTable");
    if (!t) return;
    if (!S.rm.cat) { t.innerHTML = rmTTableHTML(); t.__sig = ""; return; }
    const T = rmTData(), rows = rmTRows(T);
    const sig = [S.rm.catR || "", S.rm.catK || "", S.rm.tf || "", Object.keys(T.src).length, rows.map((x) => x.n).join("|")].join("#");   // 平台状态还没到时画的表，到了要整张重画
    const trs = t.querySelectorAll("tbody tr");
    if (t.__sig !== sig || trs.length !== rows.length) {
      t.innerHTML = rmTTableHTML(); t.__sig = sig;
      const h = t.querySelector(".bz-rm-thead");
      if (h) h.__h = rmTHeadHTML(T, rows);
      t.querySelectorAll("tbody tr").forEach((tr, i) => { const st = tr.querySelector("td.st"); if (st) st.__h = rmTStatus(rows[i], T); });
      return;
    }
    rmSetHTML(t.querySelector(".bz-rm-thead"), rmTHeadHTML(T, rows));
    rows.forEach((x, i) => {
      const tr = trs[i], s = x.key && T.src[x.key], cls = s ? (T.off.has(x.key) ? "off" : "") : "self";
      if (tr.className !== cls) tr.className = cls;
      const cb = tr.querySelector("[data-rm-on]");
      if (cb && cb.checked === T.off.has(x.key)) cb.checked = !T.off.has(x.key);
      rmSetHTML(tr.querySelector("td.st"), rmTStatus(x, T));
    });
  }
  function rmApifyRender() {                                          // v203：Apify 的状态
    const a = (S.rm.data && S.rm.data.trade_cfg && S.rm.data.trade_cfg.apify) || null;
    if (!a) return;
    rmSetHTML($("bzRmApifySt"), a.on ? ' <span class="bz-rm-ok">✓ Apify 在用（令牌 …' + esc(a.tail) + "，今天跑了 " + a.today + "/" + a.cap + " 次）</span>" : ' <span class="bz-dim">Apify 没开</span>');
    rmSetHTML($("bzRmApifyNote"), "别人写好、一直在维护的爬虫，被封和改版都由他们处理；只按拿到的商品付钱，抓不到不收钱，免费套餐每月送 5 美元额度。" +
      "现在接了：" + esc(a.plats.join("、")) + "（免费办法抓不到时自动用；Shopee 用它就不用你登录）。" +
      '先去 <a class="bz-link" href="' + esc(a.site) + '" target="_blank" rel="noopener">Apify 注册</a>，再到 <a class="bz-link" href="' + esc(a.token_url) +
      '" target="_blank" rel="noopener">设置 → API &amp; Integrations</a> 复制令牌（API token）填在下面。令牌加密存在你电脑上，不会传到 GitHub。每天最多跑 ' + a.cap + " 次。");
  }
  function rmUnlockRender() {                                         // v202：付费解锁服务的状态
    rmApifyRender();
    const u = (S.rm.data && S.rm.data.trade_cfg && S.rm.data.trade_cfg.unlock) || null, sel = $("bzRmUnlockP");
    if (!u || !sel) return;
    if (!sel.options.length) {
      sel.innerHTML = u.list.map((x) => '<option value="' + esc(x.k) + '">' + esc(x.name) + "</option>").join("");
      sel.value = u.provider || "scrapfly";
    }
    rmSetHTML($("bzRmUnlockSt"), u.provider ? ' <span class="bz-rm-ok">✓ 解锁服务在用 ' + esc((u.list.find((x) => x.k === u.provider) || {}).name || "") + "（钥匙 …" + esc(u.tail) + "），今天用了 " + u.today + "/" + u.cap + " 次</span>" :
      ' <span class="bz-dim">· 解锁服务没开</span>');
    const cur = u.list.find((x) => x.k === sel.value) || u.list[0];
    rmSetHTML($("bzRmUnlockNote"), cur ? '去 <a class="bz-link" href="' + esc(cur.site) + '" target="_blank" rel="noopener">' + esc(cur.name) + "</a> 注册拿钥匙：" + esc(cur.free) + "。" +
      "各家的测试结果出入很大（每家自己测都说自己最好），建议先用免费额度在「试抓」里试试抓不到的那几个平台。" : "");
  }
  function rmTradeRender() {
    const a = $("bzRmTAct");
    if (!a) return;
    rmUnlockRender();
    rmSetHTML(a, rmTActHTML());
    rmSetHTML($("bzRmTLive"), rmTLiveHTML());
    if (!S.rm.cat && !S.rm.catLoading && !S.rm.catErr) rmCatLoad();
    rmCatRender();
  }
  async function rmTSetOff(off, msg) {
    const r = await api("/biz/real/trade_cfg", { off: Array.from(off) }).catch(() => null);
    if (r && r.cfg && S.rm.data) S.rm.data.trade_cfg = r.cfg;
    if (msg) toast(msg);
    rmTradeRender();
  }
  function rmLoginHTML() {                                          // v198：京东 / 1688 登录；v199：加淘宝、拼多多、过验证、按地区选国外平台
    const d = S.rm.data || {}, LG = d.logins || {}, L = LG.sites || {}, c = d.trade_cfg || {}, regs = d.trade_regions || [];
    const spin = '<span class="bz-spin" aria-hidden="true"></span>';
    const row = (k) => {
      const x = L[k] || { name: k };
      const today = x.today ? '<small class="bz-dim">今天搜了 ' + x.today + "/" + (x.cap || 100) + " 次</small>" : "";
      const st = x.waiting ? '<span class="bz-rm-bad">' + spin + (x.mode === "verify" ? "验证窗口开着，在弹出来的 Chrome 里拖一下滑块 / 输一下验证码…" : "登录窗口开着，等你登录…（屏幕上弹出来的那个 Chrome）") + "</span>" :
        x.verify ? '<span class="bz-rm-bad">要过一下验证</span><small class="bz-dim">（平台弹了滑块 / 验证码，点右边「去验证」，在弹出的窗口里自己过一下）</small>' :
        x.logged ? '<span class="bz-rm-ok">✓ 已登录</span><small class="bz-dim">（' + esc(ago(x.at)) + "登录的）</small>" + today :
        x.expired ? '<span class="bz-rm-bad">登录过期了</span><small class="bz-dim">（抓的时候又被要求登录）</small>' : '<span class="bz-dim">没登录（不登录就不去抓它）</span>';
      const btn = x.waiting ? "" : (x.verify ? '<button type="button" class="bz-btn sm" data-rm-verify="' + k + '">去验证</button>' : "") +
        (x.logged ? '<button type="button" class="bz-btn sm ghost" data-rm-login="' + k + '">重新登录</button><button type="button" class="bz-link" data-rm-logout="' + k + '">退出</button>' :
          '<button type="button" class="bz-btn sm" data-rm-login="' + k + '">登录' + esc(x.name) + "</button>");
      return '<div class="bz-rm-lrow"><b>' + esc(x.name) + "</b>" + st + '<span class="sp"></span>' + btn + "</div>";
    };
    const fo = c.foreign !== false;
    const order = LG.order || ["jd", "tb", "pdd", "b2b"], B = LG.batch;
    const notIn = order.filter((k) => !(L[k] || {}).logged);
    const head = '<div class="bz-rm-lhead"><b>要登录才给看的平台</b><span class="sp"></span>' +
      (B && B.left && B.left.length ? "" : notIn.length ? '<button type="button" class="bz-btn" data-act="rm-login-all">一键登录全部（' + notIn.length + " 个没登录）</button>" :
        '<span class="bz-rm-ok">✓ 全部登录了</span><button type="button" class="bz-btn sm ghost" data-act="rm-login-all" data-force="1">全部重新登录</button>') + "</div>" +
      (B && B.left && B.left.length ? '<div class="bz-rm-lbatch">' + spin + "<b>一键登录进行中（" + B.done + "/" + B.n + "）</b>：弹出来的 Chrome 里开了 " + B.n +
        " 个标签页，现在在前面的是 <b>" + esc(B.cur) + "</b>，扫码登录就行；登好一个会自动关掉、跳到下一个" + (B.left.length > 1 ? "（后面还有：" + esc(B.left_names.slice(1).join("、")) + "）" : "") + "。不想登的直接关掉那个标签页。</div>" : "");
    return '<div class="bz-rm-login-in"><div>' + head + '<p class="bz-dim">京东、淘宝 / 天猫、拼多多、1688 搜东西要登录。点「登录」会弹出一个专门给爬虫用的 Chrome（和你自己的 Chrome、AI 池都分开），' +
      "扫码登录就行，软件看到登录好了会自动把窗口收到屏幕外。登录信息加密存在你电脑上（不会跟着提交传到 GitHub），浏览器关了再开也还在。" +
      "为了不让账号被风控，同一个平台两次搜索隔 15 秒以上、一天最多 100 次；平台弹滑块时这里会提示你自己过一下。<b>建议用小号登录。</b></p>" +
      order.map(row).join("") +
      '<p class="bz-dim bz-rm-eng">爬虫浏览器：' + esc(LG.engine === "Patchright" ? "Patchright（防检测版）" : "普通 Playwright（防检测版 Patchright 正在后台装，装好后自动换）") + "</p>" +
      (LG.err ? '<p class="bz-rm-bad">' + esc(LG.err) + "</p>" : "") + "</div>" +
      '<div><b>国外平台</b><label class="bz-rm-chkbox"><input type="checkbox" id="bzRmForeign"' + (fo ? " checked" : "") + "> 也抓国外的平台</label>" +
      '<div class="bz-rm-regs"' + (fo ? "" : " hidden") + ">" + regs.map((r) => '<label class="bz-rm-reg"><input type="checkbox" data-rm-reg="' + esc(r.key) + '"' + (r.on ? " checked" : "") +
        "><span><b>" + esc(r.name) + "</b><small>" + esc(r.plats) + "</small></span></label>").join("") + "</div>" +
      '<p class="bz-dim">要能上外网：走软件设置里的代理。搜索词用内置词表翻成当地语言（翻不了再联网翻）；价格按当天汇率换算成人民币。政府采购、App、接单、众筹走官方公开接口，不用登录。地区勾得越多，「全部抓一遍」越久。</p></div></div>';
  }
  // v193：交易平台「全部抓一遍」
  function rmTBarHTML() {
    const tb = S.rm.data && S.rm.data.tbatch;
    const hrs = (sec) => (sec >= 3600 ? (sec / 3600).toFixed(1).replace(/\.0$/, "") + " 小时" : Math.max(1, Math.round(sec / 60)) + " 分钟");
    let h = '<div class="bz-rm-tbar-in"><div><b>爬虫什么时候去抓交易平台？</b>' +
      '<p class="bz-dim">① 核实任何一个方向（下拉框选的、自己写的、「全部核实」排队的）时，会先自动抓；② 体检卡里点「去平台抓」；③ 点右边按钮，把全部行业抓一遍（不用 AI）。' +
      "不是每个平台都适合每个行业：电商和批发平台只在卖货的行业（吃穿用、电子、医药、宠物…）去抓；猪八戒、Freelancer 只在卖服务的行业去抓；应用商店只在软件、游戏、教育、AI 这类去查；" +
      "政府采购（国内、美国、欧盟）几乎每个都查。表格里「适用」就是会去抓的行业数。几个平台同时抓，同一个平台一个一个来。" +
      "京东、淘宝、拼多多、1688 要先在上面登录，不登录就不去抓（不硬闯）。连着 6 次被拦的平台先跳过 1 天。</p></div>";
    if (tb && tb.running) {
      const pct = tb.n ? Math.round((tb.i / tb.n) * 100) : 0;
      h += '<div class="bz-rm-tprog"><p><span class="bz-spin" aria-hidden="true"></span><b>正在抓：' + esc(tb.cur_name || "…") + "</b>　" + tb.i + " / " + tb.n +
        " · 抓到 " + tb.ok + (tb.bad ? " · 没抓到 " + tb.bad : "") + " · 还要约 " + hrs(tb.eta) + '</p><div class="bz-rm-bar"><i style="width:' + pct + '%"></i></div>' +
        '<button type="button" class="bz-btn sm ghost" data-act="rm-tstop"' + (tb.stop ? " disabled" : "") + ">" + (tb.stop ? "正在停…" : "停止") + "</button></div>";
    } else {
      h += '<div class="bz-rm-tprog">' + (tb && tb.ended ? '<p class="bz-dim">上次「' + esc(tb.name) + "」抓完了：抓到 " + tb.ok + " 个，没抓到 " + tb.bad + " 个" + (tb.skipped ? "，跳过 " + tb.skipped + " 个刚抓过的" : "") + "。</p>" : "") +
        '<button type="button" class="bz-btn" data-act="rm-tall">交易平台全部抓一遍</button><p class="bz-dim">155 个行业，不用 AI，国外地区全开约 3～4 小时（适合晚上挂着）；3 天内抓过的跳过</p></div>';
    }
    return h + "</div>";
  }
  async function rmBatch(action, extra) {
    const r = await api("/biz/real/batch", Object.assign({ action: action }, extra || {})).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) toast(r.error || "没成");
    else if (action === "start") { S.rm.batchOpen = false; toast("开始一个个核实了，进度在这里和页面顶上。"); }
    rmLoad();
  }
  function rmCheck(target, scope) {
    runJob("real", { target: target || "", scope: scope || "", web: true, depth: S.rm.depth });
  }
  async function rmOpenCheck(cid) {
    const r = await api("/biz/real/check?id=" + enc(cid)).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) { toast(r.error || "打不开"); return; }
    const c = r.check;
    openReader("真实市场核实：" + c.name, '<p class="bz-dim">' + esc(fmtTime(c.created)) + " · " + esc(c.engine || "AI") + " · 查了 " + (c.web || 0) + " 个网页 · " +
      c.facts.filter((f) => f.ok).length + "/" + c.facts.length + " 个数字在原文里对上了</p>",
      (c.summary ? "<p><b>" + esc(c.summary) + "</b></p>" : "") + rmFactsHTML(c) +
      '<p class="bz-hint">「原文有」：这个数字在 AI 读到的网页或统计数据里找得到。「没对上」：原文里没找到，可能是换算的或记错的，用之前点出处自己核对。</p>',
      c.report ? '<button type="button" class="bz-btn sm" data-rep="' + esc(c.report) + '">打开完整报告</button>' : "");
  }

  // ───────── 后台任务（写报告）─────────
  const mmss = (s) => { s = Math.max(0, s | 0); return pad((s / 60) | 0) + ":" + pad(s % 60); };
  function renderJob() {
    const j = S.job, el = $("bzJob");
    if (!j || (!j.running && (!j.ended || store.get("jobSeen", 0) >= j.id))) { el.hidden = true; bzLivePlace(); return; }
    el.hidden = false;
    if (j.running) {
      el.className = "bz-job running";
      const cr = window.cxAiLive ? window.cxAiLive.caret("biz") : "";            // v190：点标题在下面展开 AI 实时画面
      el.innerHTML = '<button type="button" class="bz-job-t cx-ail-tg" data-ail-toggle="biz"><b><span class="bz-job-tt">' + esc(j.title) + '</span><span class="cx-ail-caret">' + cr + "</span></b><span>" + esc(j.stage || "") + "</span></button>" +
        '<ol class="bz-steps">' + (j.steps || []).map((s, i) => {
          const n = i + 1, cls = n < j.step ? "done" : n === j.step ? "on" : "";
          return '<li class="' + cls + (n === 2 && !j.web ? " skip" : "") + '">' + esc(s) + "</li>";
        }).join("") + "</ol>" +
        '<span class="bz-job-time" title="已经用了多久">' + mmss(j.now - j.started) + "</span>" +
        '<button type="button" class="bz-btn ghost sm" data-act="stopjob">停止</button>' +
        '<div class="cx-ail-slot" id="bzJobLive" hidden></div>';
    } else if (j.ok) {
      el.className = "bz-job done";
      el.innerHTML = '<div class="bz-job-t"><b>写好了：' + esc(j.title) + "</b><span>" +
        (j.opps ? (j.kind === "custom" ? "方案" : "报告") + "里的 " + j.opps + " 个机会已经放进「机会看板」" : "用了 " + mmss(j.ended - j.started)) + "</span></div>" +
        '<button type="button" class="bz-btn sm" data-rep="' + esc(j.report) + '">' + (j.kind === "custom" ? "打开方案" : "打开报告") + "</button>" +
        '<button type="button" class="bz-btn ghost sm" data-openfolder="' + esc(j.report) + '">打开所在文件夹</button>' +
        '<button type="button" class="bz-link" data-act="jobseen">知道了</button>';
    } else {
      el.className = "bz-job fail";
      el.innerHTML = '<div class="bz-job-t"><b>没写完：' + esc(j.title) + "</b><span>" + esc(j.error || "") + "</span></div>" +
        '<button type="button" class="bz-link" data-act="jobseen">知道了</button>';
    }
    bzLivePlace();
  }
  // v190：商业的 AI 实时画面放哪：在商业定制页、写的是定制方案 →「正在写：…」下面；别的 → 顶上进度条下面；没在写 → 收走
  function bzLivePlace() {
    if (!window.cxAiLive) return;
    const j = S.job, run = !!(j && j.running);
    const cu = $("bzCuLive"), top = $("bzJobLive"), rm = $("bzRmLive");
    const slot = !run ? null : (S.pane === "custom" && j.kind === "custom" && cu) ? cu : (S.pane === "real" && j.kind === "real" && rm && S.rm.tab === "check") ? rm : top;   // v193/v195：在「AI 核实」标签里就放在「正在核实」下面
    [cu, top, rm].forEach((x) => { if (x && x !== slot) x.hidden = true; });
    window.cxAiLive.place("biz", slot || null);
  }
  async function pollJob() {
    clearTimeout(S.jobTimer);
    try {
      const j = await api("/biz/job");
      const was = S.job && S.job.running;
      S.job = j;
      renderJob();
      renderBigBtns();
      if (S.pane === "custom") renderCuGo();                         // v187：商业定制页上也显示写到哪一步了
      if (S.pane === "real") rmRunRender();                          // v193
      if (was && !j.running) {
        refreshReports(); refreshOpps(); refreshOverview();
        if (j.kind === "real") { rmLoad(true); if (j.ok) toast("核实完：" + String(j.title || "").replace(/^真实市场核实：/, "") + "，数字已经同步到「行业地图」。"); }   // v197
      }
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


  // ───────── v158：两个大按钮 ─────────
  function renderBigBtns() {
    const r = S.radar, t = $("bzUpdBtnT"), sub = $("bzUpdBtnS"), btn = $("bzUpdBtn");
    if (!t) return;
    if (r && r.running) {
      btn.classList.add("busy");
      t.textContent = "正在更新 " + r.done + " / " + r.total;
      sub.textContent = "新抓到 " + r.new + " 条 · 点开看进度";
    } else {
      btn.classList.remove("busy");
      t.textContent = r && r.resume ? "接着更新" : "现在更新";
      sub.textContent = r && r.resume ? "上次扫到 " + r.resume.done + " / " + r.resume.total + "，点开接着扫" : r && r.last_run ? "上次 " + ago(r.last_run) + (r.auto ? " · 每 " + (r.every >= 60 ? (r.every / 60).toFixed(1).replace(/\.0$/, "") + " 小时" : r.every + " 分钟") + "自动更新" : " · 自动更新已关")
        : "让爬虫马上去抓最新新闻";
    }
    const bs = $("bzBriefBtnS");
    if (bs) {
      const j = S.job;
      bs.textContent = j && j.running && j.kind === "market" ? "正在写：" + (j.stage || "…")
        : (S.rtotal ? "用这 " + S.rtotal + " 条新闻写一份文档" : "AI 写一份文档，存在你电脑上");
    }
  }

  // ───────── v158：「现在更新」面板 ─────────
  const EVERY = [[1, "实时"], [5, "5 分钟"], [10, "10 分钟"], [20, "20 分钟"], [30, "30 分钟"], [60, "1 小时"], [120, "2 小时"], [240, "4 小时"], [480, "8 小时"]];
  const everyText = (m) => (m <= 1 ? "实时" : m >= 60 && m % 60 === 0 ? m / 60 + " 小时" : m + " 分钟");
  const sw = (id, on, label, hint) => '<label class="bz-set"><span class="bz-sw"><input type="checkbox" id="' + id + '"' + (on ? " checked" : "") + '><i></i></span>' +
    '<span class="bz-set-t"><b>' + label + "</b>" + (hint ? "<small>" + hint + "</small>" : "") + "</span></label>";
  function openModal(id) {
    const m = $(id);
    m.hidden = false;
    document.body.classList.add("bz-modal-open");
    setTimeout(() => { const f = m.querySelector("[data-autofocus]") || m.querySelector("button, input, select"); if (f) f.focus(); }, 30);
  }
  function closeModal(id) {
    const m = $(id);
    if (!m || m.hidden) return;
    m.hidden = true;
    if ($("bzUpd").hidden && $("bzBrief").hidden) document.body.classList.remove("bz-modal-open");
    if (id === "bzUpd") { S.updOpen = false; const b = $("bzUpdBtn"); if (b) b.focus(); }
    if (id === "bzBrief") { S.briefOpen = false; const b = $("bzBriefRun"); if (b) b.focus(); }
  }
  async function openUpd() {
    S.updOpen = true;
    S.updCustom = false;
    if (!(S.radar && S.radar.running) && !S.updDone) S.plan = null;
    renderUpd();
    openModal("bzUpd");
    if (!S.plan) { try { S.plan = await api("/biz/radar/plan"); } catch (e) { S.plan = { ok: false, error: e.message }; } renderUpd(); }
  }
  const dlgHead = (id, title, sub) => '<div class="bz-dlg-h"><div><h2 id="' + id + '">' + title + "</h2>" + (sub ? "<p>" + sub + "</p>" : "") + "</div>" +
    '<button type="button" class="bz-x" data-close aria-label="关闭">×</button></div>';
  function renderUpd() {
    const el = $("bzUpdBody");
    if (!el || !S.updOpen) return;
    const r = S.radar || {};
    if (r.running) { el.innerHTML = updRunning(r); return; }
    if (S.updDone) { el.innerHTML = updDoneHTML(); return; }
    const p = S.plan;
    if (!p) { el.innerHTML = dlgHead("bzUpdT", "现在更新") + '<div class="bz-dlg-b">' + loading() + "</div>"; return; }
    if (p.ok === false) { el.innerHTML = dlgHead("bzUpdT", "现在更新") + '<div class="bz-dlg-b">' + empty("读不到爬虫的设置：" + esc(p.error || "")) + "</div>"; return; }
    const keepTop = (el.querySelector(".bz-dlg-b") || {}).scrollTop || 0;
    const c = p.config, nFail = p.failing.length;
    const sc = c.scope === "failed" && !nFail ? "all" : (c.scope || "all");
    // v166：勾了哪几类。「全部」就是每类都勾上；只重抓没抓成的时候，保留之前勾的（只是先不用）
    const gsel = new Set(sc === "groups" ? (c.groups || []) : sc === "all" ? p.groups.map((g) => g.key) : (c.groups && c.groups.length ? c.groups : p.groups.map((g) => g.key)));
    const failOnly = sc === "failed";
    const selGroups = p.groups.filter((g) => gsel.has(g.key));
    const force = !!S.updForce;                // v170：这次全部都抓（不按权重轮流）
    const resuming = !!(p.resume && !S.updFresh);   // v177：上次没扫完 → 默认接着扫
    const nScope = failOnly ? nFail : selGroups.reduce((a, g) => a + (force ? g.n : (g.due != null ? g.due : g.n)), 0);
    const nAllSel = selGroups.reduce((a, g) => a + g.n, 0);
    const last = p.last;
    const lastDur = last && last.ended ? last.ended - last.started : 0;
    const est = lastDur && last.total ? Math.max(20, Math.round((lastDur / last.total) * nScope)) : 0;
    const gdesc = {};
    (p.group_names || []).forEach(([k, n, d]) => { gdesc[k] = d; });
    const cats = p.groups.map((g) => {
      const on = gsel.has(g.key);
      const what = [g.site ? g.site + " 个网站" : "", g.kw ? g.kw + " 个关键词" : ""].filter(Boolean).join(" + ") +
        (!force && g.due != null && g.due < g.n ? " · 这次轮到 " + g.due + " 个" : "");
      return '<label class="bz-cat' + (on ? " on" : "") + (failOnly ? " off" : "") + '" title="' + esc(gdesc[g.key] || "") + '"><input type="checkbox" data-upd-grp="' + esc(g.key) + '"' + (on ? " checked" : "") + (failOnly ? " disabled" : "") + ">" +
        '<span class="bz-cat-b"><b>' + esc(g.name) + "</b><small>" + esc(what) + (g.failing ? ' · <em class="bad">' + g.failing + " 个上次没抓成</em>" : "") + "</small></span></label>";
    }).join("");
    const allOn = selGroups.length === p.groups.length;
    const A = S.updAdd || (S.updAdd = { mode: "one", group: "mine", msg: "" });
    const grpOpts = [["mine", "我自己加的"]].concat((p.group_names || []).filter(([k]) => k !== "mine").map(([k, n]) => [k, n]));
    // v167：说明文字都收进「怎么抓的」，点了才看
    const info = S.updInfo ? '<div class="bz-upd-info"><ol class="bz-flow">' +
        "<li><b>抓哪些</b>：信息源按类型分成几类，勾上的这次就抓。一般全选；只想快点看某一类才取消别的。自动更新那一轮总是抓全部。</li>" +
        "<li><b>同时开 " + c.workers + " 个</b>，把勾上的信息源轮流抓一遍。</li>" +
        "<li><b>网站</b>：先找 RSS 订阅 → 没有就从网页里挑文章链接" + (c.sc_fast || c.sc_browser ? " → 被拦或是动态网页，换 Scrapling" + (c.sc_fast ? "快速模式" : "") + (c.sc_fast && c.sc_browser ? " → 还不行用" : "") + (c.sc_browser ? "真浏览器打开" : "") : "") +
          "。哪种方法管用会记住。" + (p.scrapling ? "" : '<span class="bz-warn">Scrapling 还没装好，动态网页可能抓不到。</span>') + "</li>" +
        "<li><b>关键词</b>：去 Google 新闻（要开代理）、必应新闻、百度资讯找最新报道。</li>" +
        "<li><b>去重、归类</b>：抓过的不再算；按关键词把新闻归到行业和赛道（不用 AI）。</li>" +
        "<li><b>抓完</b>：新的出现在「最新新闻」，雷达上会亮一下再归进它的行业；详细记录在「爬虫管理」的抓取记录里。</li></ol>" +
        '<p class="bz-note">' + (last ? "上一轮：" + esc(fmtTime(last.started)) + "（" + (TRIG[last.trigger] || "手动") + "），" + last.total + " 个用了 " + dur(lastDur) +
          "，成功 " + last.ok + "、没抓成 " + last.fail + "，新抓到 " + last.new + " 条。" : "还没抓过。") + "</p></div>" : "";
    el.innerHTML = '<div class="bz-dlg-h"><div><h2 id="bzUpdT">现在更新</h2><p>不用 AI，随时可以停' + (est ? "，这次大约 " + dur(est) : "") + "</p></div>" +
        '<button type="button" class="bz-info-btn" data-act="upd-info" aria-expanded="' + !!S.updInfo + '" title="怎么抓的、上一轮情况"><span aria-hidden="true">i</span>怎么抓的</button>' +
        '<button type="button" class="bz-x" data-close aria-label="关闭">×</button></div>' +
      '<div class="bz-dlg-b">' + info +
      (p.resume ? '<section class="bz-sec bz-resume"><h3>上次没扫完</h3><p>' + esc(fmtTime(p.resume.started)) + " 开始的那一轮，扫到 <b>" + p.resume.done + " / " + p.resume.total +
        "</b> 个信息源就停了（软件关了、异常退出，或点了停止）" + (p.resume.new ? "，已经新抓到 " + p.resume.new + " 条" : "") + "。点下面的「接着扫」把剩下的 <b>" + p.resume.left + " 个</b>扫完，不用从头来。</p>" +
        '<label class="bz-sw-inline"><span class="bz-sw"><input type="checkbox" id="bzUpdFresh"' + (S.updFresh ? " checked" : "") + '><i></i></span>不接着了，按下面的设置从头扫</label></section>' : "") +
      '<section class="bz-sec' + (resuming ? " bz-sec-off" : "") + '"><h3>这次抓哪些</h3>' + (resuming ? '<p class="bz-note">接着扫时按上次的清单扫；勾了上面的「从头扫」才按这里的设置。</p>' : "") +
        '<div class="bz-upd-sum"><span>' + (failOnly ? "只重抓上次没抓成的 <b>" + nFail + " 个</b>"
          : "<b>" + (allOn ? "全部 " : "") + selGroups.length + " 类</b>，这次抓 <b>" + nScope + " 个</b>信息源" + (nScope < nAllSel ? '<small>（一共 ' + nAllSel + " 个：权重高的每次都抓，低的轮着抓）</small>" : "")) + "</span>" +
          (failOnly ? "" : '<span class="sp"></span><button type="button" class="bz-link" data-act="upd-all"' + (allOn ? " disabled" : "") + '>全选</button><button type="button" class="bz-link" data-act="upd-none">全不选</button>') + "</div>" +
        '<div class="bz-cats" role="group" aria-label="要抓的分类">' + cats + "</div>" +
        (!failOnly && nAllSel > nScope || force ? '<label class="bz-sw-inline bz-force"><span class="bz-sw"><input type="checkbox" id="bzUpdForce"' + (force ? " checked" : "") + '><i></i></span>这次全部都抓（' + nAllSel + " 个，会慢不少）</label>" : "") +
        (nFail ? '<div class="bz-failrow"><label class="bz-sw-inline"><span class="bz-sw"><input type="checkbox" id="bzUpdFailOnly"' + (failOnly ? " checked" : "") + '><i></i></span>只重抓上次没抓成的 ' + nFail + " 个</label>" +
          '<details class="bz-fails"><summary>看原因</summary><ul>' + p.failing.map((f) => "<li><b>" + esc(f.name) + "</b>：" + esc(f.err) + "</li>").join("") + "</ul></details></div>" : "") +
      "</section>" +
      (p.lib && p.lib.ok && p.lib.new ? '<section class="bz-sec bz-lib"><h3>扩充信息源</h3>' +
        '<p>推荐库里还有 <b>' + p.lib.new + " 个</b>权威信息源没加：<b>" + p.lib.sites + "</b> 个网站（部委、交易所、行业协会、主流和行业媒体、海外机构、各省市政府），<b>" + p.lib.kws +
        "</b> 个搜索关键词（行业地图里的代表公司、细分行业、产品和技术）。加进来后按权重轮流抓，不会每次都全抓。</p>" +
        '<div class="bz-lib-acts"><button type="button" class="bz-btn" data-lib="1">全部加进来（' + p.lib.new + " 个）</button>" +
        '<button type="button" class="bz-btn ghost" data-lib="3">只加权重中以上的（' + ["s5", "s4", "s3", "k5", "k4", "k3"].reduce((a, k) => a + (p.lib.by[k] || 0), 0) + " 个）</button>" +
        '<button type="button" class="bz-btn ghost" data-lib="site">只加网站（' + p.lib.sites + " 个）</button></div></section>" : "") +
      '<section class="bz-sec"><h3>添加扫描对象</h3>' +
        '<div class="bz-add-bar"><div class="bz-tog2" role="tablist">' +
          '<button type="button" role="tab" data-addmode="one" aria-selected="' + (A.mode === "one") + '">一个</button>' +
          '<button type="button" role="tab" data-addmode="batch" aria-selected="' + (A.mode === "batch") + '">一批</button></div>' +
          '<label class="bz-add-grp">放进 <select class="bz-select sm" id="bzAddGrp">' + grpOpts.map(([k, n]) => '<option value="' + esc(k) + '"' + (k === A.group ? " selected" : "") + ">" + esc(n) + "</option>").join("") + "</select></label></div>" +
        (A.mode === "one"
          ? '<div class="bz-add-one"><input class="bz-input" id="bzAddOne" placeholder="网址或关键词，比如 https://www.cls.cn/telegraph 或 宁德时代" aria-label="网址或关键词">' +
            '<button type="button" class="bz-btn" data-act="add-one">添加</button></div>'
          : '<textarea class="bz-input bz-add-many" id="bzAddMany" rows="5" placeholder="每行一个，网址和关键词可以混着写：&#10;https://www.cls.cn/telegraph&#10;36kr.com/newsflashes&#10;宁德时代&#10;固态电池" aria-label="一批网址或关键词"></textarea>' +
            '<div class="bz-add-one"><span class="bz-note">网址按网站抓，其他的按关键词去新闻搜索</span><span class="sp"></span><button type="button" class="bz-btn" data-act="add-batch">全部添加</button></div>') +
        (A.msg ? '<p class="bz-add-msg" role="status">' + A.msg + "</p>" : "") +
      "</section>" +
      '<section class="bz-sec"><h3>设置</h3><div class="bz-sets">' +
        autoSetHTML(p) +
        '<div class="bz-set"><span class="bz-set-t"><b>同时抓几个</b></span>' +
          '<select class="bz-select sm" id="bzUpdWorkers" aria-label="同时抓几个" title="越多越快，但太多容易被网站拦">' + [2, 4, 6, 8].map((v) => '<option value="' + v + '"' + (v === c.workers ? " selected" : "") + ">" + v + " 个</option>").join("") + "</select></div>" +
        sw("bzUpdScFast", c.sc_fast, "被拦时用 Scrapling 快速模式补救", "") +
        sw("bzUpdScBrowser", c.sc_browser, "还不行就用真浏览器打开（慢）", "") +
      "</div></section>" +
      "</div>" +
      '<div class="bz-dlg-f"><span class="bz-note" id="bzUpdSaved"></span><span class="sp"></span>' +
        '<button type="button" class="bz-btn ghost" data-close>取消</button>' +
        '<button type="button" class="bz-btn lg" data-act="upd-start" data-autofocus' + (nScope || resuming ? "" : " disabled") + ">" + (resuming ? "接着扫（剩 " + p.resume.left + " 个）" : "开始更新（" + nScope + " 个信息源）") + "</button></div>";
    if (keepTop) el.querySelector(".bz-dlg-b").scrollTop = keepTop;
  }
  async function addSources(text) {
    const A = S.updAdd;
    A.group = ($("bzAddGrp") || {}).value || A.group;
    const r = await api("/biz/radar/source", { action: "add_batch", text: text, group: A.group }).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) { A.msg = '<span class="bad">' + esc(r.error || "没加上") + "</span>"; renderUpd(); return; }
    A.msg = (r.added ? '<span class="ok">加好了 ' + r.added + " 个：" + esc(r.names.slice(0, 6).join("、")) + (r.added > 6 ? " 等" : "") + "。下次扫描就会抓。</span>" : "") +
      (r.bad.length ? ' <span class="bad">' + r.bad.length + " 个没加：" + esc(r.bad.slice(0, 4).map((x) => x[0] + "（" + x[1] + "）").join("、")) + (r.bad.length > 4 ? " 等" : "") + "</span>" : "");
    try { S.plan = await api("/biz/radar/plan"); } catch (e) {}
    renderUpd();
    if (S.pane === "crawler") loadRadarSources();
  }
  function autoSetHTML(p) {
    const c = p.config, custom = S.updCustom || !EVERY.some(([v]) => v === c.every);
    const nx = p.next_run, now = p.now || Date.now() / 1000;
    const st = c.auto
      ? (c.every <= 1 ? "实时：一轮抓完接着下一轮。" : "每 " + everyText(c.every) + "一轮，下一次 " + (nx ? (nx <= now + 30 ? "马上" : hhmm(nx).slice(0, 5) + "（" + until(nx) + "）") : "—") + "。")
      : "关着：只有手动点才会抓。";
    return '<div class="bz-set bz-set-auto"><span class="bz-sw"><input type="checkbox" id="bzUpdAuto"' + (c.auto ? " checked" : "") + ' aria-describedby="bzUpdAutoSt"><i></i></span>' +
      '<span class="bz-set-t"><b>自动更新</b></span>' +
      '<span class="bz-every"><select class="bz-select sm" id="bzUpdEvery" aria-label="多久自动更新一次"' + (c.auto ? "" : " disabled") + ">" +
        EVERY.map(([v, t]) => '<option value="' + v + '"' + (!custom && v === c.every ? " selected" : "") + ">" + (v <= 1 ? "实时（抓完接着抓）" : "每 " + t) + "</option>").join("") +
        '<option value="custom"' + (custom ? " selected" : "") + ">自己填…</option></select>" +
      (custom ? '<label class="bz-every-n">每 <input type="number" class="bz-input" id="bzUpdEveryN" min="1" max="1440" step="1" value="' + c.every + '"' + (c.auto ? "" : " disabled") +
        ' aria-label="每隔几分钟"> 分钟</label>' : "") + "</span></div>" +
      '<p class="bz-autost' + (c.auto ? " on" : "") + '" id="bzUpdAutoSt" aria-live="polite">' + esc(st) + "</p>";
  }
  function updRunning(r) {
    const pct = r.total ? Math.round((r.done / r.total) * 100) : 0;
    const el = (r.now || Date.now() / 1000) - (r.started || 0);
    return dlgHead("bzUpdT", "正在更新", "关掉这个窗口也会继续抓，抓完会提醒你。") +
      '<div class="bz-dlg-b">' +
      '<div class="bz-rr-stats"><div><span>进度</span><b>' + r.done + " / " + r.total + "</b></div><div><span>新抓到</span><b>" + r.new + " 条</b></div>" +
        "<div><span>没抓成</span><b>" + (r.fail || 0) + " 个</b></div><div><span>用了</span><b>" + mmss(el) + "</b></div></div>" +
      '<div class="bz-prog big" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pct + '"><i style="width:' + pct + '%"></i></div>' +
      '<p class="bz-note">正在抓：' + ((r.current || []).length ? (r.current || []).map(esc).join("、") : "准备中…") + "</p>" +
      '<h3 class="bz-sub">运行日志</h3><div class="bz-log big">' + (r.log || []).slice().reverse().map((x) => "<div><time>" + hhmm(x[0]) + "</time>" + esc(x[1]) + "</div>").join("") + "</div>" +
      "</div>" +
      '<div class="bz-dlg-f"><span class="sp"></span><button type="button" class="bz-btn ghost danger" data-act="rd-stop">停止</button>' +
        '<button type="button" class="bz-btn" data-close data-autofocus>放到后台，继续看新闻</button></div>';
  }
  function updDoneHTML() {
    const d = S.updRes;
    if (!d) return dlgHead("bzUpdT", "这一轮抓完了") + '<div class="bz-dlg-b">' + loading("正在读这一轮的结果…") + "</div>";
    if (!d.ok) return dlgHead("bzUpdT", "这一轮抓完了") + '<div class="bz-dlg-b">' + empty(esc(d.error || "读不到结果")) + "</div>" +
      '<div class="bz-dlg-f"><span class="sp"></span><button type="button" class="bz-btn" data-close>关闭</button></div>';
    const r = d.run, bad = (r.sources || []).filter((x) => !x.ok);
    return dlgHead("bzUpdT", r.stopped ? "这一轮中途停了" : "这一轮抓完了", esc(fmtTime(r.started)) + " 开始，用了 " + dur(r.ended - r.started)) +
      '<div class="bz-dlg-b">' +
      '<div class="bz-rr-stats"><div><span>新抓到</span><b>' + r.new + " 条</b></div><div><span>抓成的信息源</span><b>" + r.ok + " / " + r.total + "</b></div>" +
        "<div><span>没抓成</span><b" + (r.fail ? ' class="bad"' : "") + ">" + r.fail + " 个</b></div><div><span>用到的方法</span><b class=\"sm\">" + (esc(viaText(r.via)) || "—") + "</b></div></div>" +
      (d.by_ind && d.by_ind.length ? '<h3 class="bz-sub">新内容主要在</h3><div class="bz-chips">' + d.by_ind.slice(0, 12).map(([g, n]) => '<span class="bz-chip">' + esc(nameOf(g)) + " <b>" + n + "</b></span>").join("") + "</div>" : "") +
      (bad.length ? '<h3 class="bz-sub">没抓成的 ' + bad.length + " 个</h3><ul class=\"bz-badlist\">" + bad.map((x) => "<li><b>" + esc(x.name) + "</b>：" + esc(x.err || "") + "</li>").join("") + "</ul>" +
        '<p class="bz-note">下次点「现在更新」时可以选「只重抓上次没抓成的」；老是抓不成的，可以在「爬虫管理」里关掉或换网址。</p>' : "") +
      "</div>" +
      '<div class="bz-dlg-f"><span class="sp"></span><button type="button" class="bz-btn ghost" data-close>关闭</button>' +
        (r.new ? '<button type="button" class="bz-btn" data-act="upd-shownew" data-autofocus>只看这次新抓到的 ' + r.new + " 条</button>" : "") + "</div>";
  }
  function everyVal() {
    const sel = $("bzUpdEvery").value;
    if (sel !== "custom") return +sel;
    const n = $("bzUpdEveryN");
    let v = n ? Math.round(+n.value) : 0;
    if (!v || v < 1) { v = 1; }
    return Math.min(v, 1440);
  }
  function updScope() {                       // v166：从界面上读出「抓哪些」
    const boxes = Array.from(root.querySelectorAll("[data-upd-grp]"));
    const groups = boxes.filter((x) => x.checked).map((x) => x.dataset.updGrp);
    const fo = $("bzUpdFailOnly");
    if (fo && fo.checked) return { scope: "failed", groups: groups };
    return groups.length === boxes.length ? { scope: "all", groups: [] } : { scope: "groups", groups: groups };
  }
  async function updSave(extra) {
    const sc = updScope();
    const body = Object.assign({
      auto: $("bzUpdAuto").checked, every: everyVal(), workers: +$("bzUpdWorkers").value,
      sc_fast: $("bzUpdScFast").checked, sc_browser: $("bzUpdScBrowser").checked,
      scope: sc.scope, groups: sc.groups,
    }, extra || {});
    const r = await api("/biz/radar/config", body).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) { toast(r.error || "没存上"); return; }
    if (S.plan) { S.plan.config = r.config; S.plan.next_run = r.next_run; S.plan.now = r.now; }
    renderUpd();
    const n = $("bzUpdSaved");
    if (n) n.textContent = "设置已保存";
    pollRadar();
  }
  async function updStart() {
    const { scope, groups } = updScope();
    const fresh = !!(S.plan && S.plan.resume && S.updFresh);          // v177：上次没扫完时默认接着扫；勾了「从头扫」才从头来
    if ((fresh || !(S.plan && S.plan.resume)) && scope === "groups" && !groups.length) { toast("至少勾上一类。"); return; }
    await updSave();
    S.updDone = ""; S.updRes = null;
    await radarRun(null, { scope: scope, groups: groups, force: !!S.updForce && scope !== "failed", fresh: fresh });
    S.updForce = false; S.updFresh = false;
    renderUpd();
  }

  // ───────── v158：「整理成简报」面板 ─────────
  const BF_SIZE = { short: ["简短", "800 字以内，最重要的几条", 40], normal: ["标准", "1500～2500 字", 60], detail: ["详细", "3000～5000 字，每条讲清来龙去脉", 90] };
  async function openBrief() {
    const prev = store.get("bf", {});
    S.bf = { days: S.mdays >= 1 ? Math.min(30, S.mdays) : S.mdays === 0 ? 30 : 1, grp: S.rgrp, q: S.rq, size: prev.size || "normal", notes: prev.notes !== false, web: !!prev.web, focus: "", count: null };
    S.briefOpen = true;
    renderBrief();
    openModal("bzBrief");
    briefCount();
    if (!S.briefInfo) { try { S.briefInfo = await api("/biz/brief_info"); } catch (e) { S.briefInfo = null; } renderBrief(); }
  }
  let bfSeq = 0;
  async function briefCount() {
    const f = S.bf, seq = ++bfSeq;
    f.count = null;
    const n = $("bzBfCount");
    if (n) n.textContent = "正在数…";
    let r = null;
    try { r = await api("/biz/items?lens=market&limit=1&days=" + f.days + "&grp=" + enc(f.grp === "all" ? "" : f.grp) + "&q=" + enc(f.q)); } catch (e) {}
    if (seq !== bfSeq) return;
    f.count = r ? r.total || 0 : 0;
    renderBriefCount();
  }
  function renderBriefCount() {
    const f = S.bf, n = $("bzBfCount");
    if (!n || f.count == null) return;
    const m = BF_SIZE[f.size][2];
    n.innerHTML = f.count ? "符合的新闻 <b>" + f.count + "</b> 条。" + (f.count > m ? "AI 会从里面挑最新、最相关的 " + m + " 条来写。" : "全部交给 AI。")
      : '<span class="bz-warn">这个范围里没有新闻，换个时间或来源试试。</span>';
    const go = $("bzBfGo");
    if (go) go.disabled = !f.count || !!(S.job && S.job.running);
  }
  function bfTitle() {
    const f = S.bf, gname = { news: "财经媒体", "corp,corpkw": "大公司", "media,indkw": "行业媒体", policy: "政策数据", global: "海外", mine: "我加的" }[f.grp];
    return "市场动向简报（实时）· " + [gname || "全部行业", f.q ? "「" + f.q + "」" : ""].filter(Boolean).join(" ") + " · " + (f.days <= 1 ? "最近 24 小时" : "最近 " + f.days + " 天");
  }
  function renderBrief() {
    const el = $("bzBriefBody");
    if (!el || !S.briefOpen) return;
    const f = S.bf, info = S.briefInfo, busy = S.job && S.job.running;
    const now = new Date(), stamp = now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate()) + "-" + pad(now.getHours()) + pad(now.getMinutes()) + "00";
    const fname = stamp + "-market-" + bfTitle().replace(/[\\/:*?"<>|\s·：]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40) + ".md";
    const grpOpts = [["all", "全部来源"], ["news", "财经媒体"], ["corp,corpkw,firm", "大公司"], ["media,indkw", "行业媒体"], ["policy", "政策数据"], ["govmedia", "各国官方"], ["global", "海外"], ["mine", "我加的"]];
    const parts = (info && info.parts) || [];
    const segB = (name, opts, cur) => '<div class="bz-seg" role="group" data-seg="' + name + '">' + opts.map(([v, t]) => '<button type="button" data-v="' + v + '" aria-pressed="' + (String(v) === String(cur)) + '">' + t + "</button>").join("") + "</div>";
    el.innerHTML = dlgHead("bzBriefT", "生成简报", "AI 读完你选的新闻，写成一份「市场动向简报」文档，存在你电脑上。") +
      '<div class="bz-dlg-b">' +
      '<section class="bz-sec"><h3><span class="bz-no">1</span>用哪些新闻</h3>' +
        '<p class="bz-note bz-flat">默认就是「最新新闻」里现在筛出来的那些，可以在这里改。</p>' +
        '<div class="bz-form">' +
          "<div><span class=\"bz-lbl\">时间</span>" + segB("bfdays", [[1, "24 小时"], [3, "3 天"], [7, "7 天"], [30, "30 天"]], f.days) + "</div>" +
          '<label><span class="bz-lbl">来源</span><select class="bz-select" id="bzBfGrp">' + grpOpts.map(([v, t]) => '<option value="' + v + '"' + (v === f.grp ? " selected" : "") + ">" + t + "</option>").join("") + "</select></label>" +
          '<label><span class="bz-lbl">只要提到</span><input class="bz-input" id="bzBfQ" value="' + esc(f.q) + '" placeholder="不填就是全部，比如 比亚迪、降价" maxlength="40"></label>' +
        "</div>" +
        '<p class="bz-count" id="bzBfCount" aria-live="polite">正在数…</p>' +
        '<label class="bz-chk"><input type="checkbox" id="bzBfNotes"' + (f.notes ? " checked" : "") + "> 加上你收进来的笔记和动态（让 AI 对照你关注的方向）</label>" +
        '<label class="bz-chk"><input type="checkbox" id="bzBfWeb"' + (f.web ? " checked" : "") + "> 联网补充查资料（会多花 1～2 分钟）</label>" +
      "</section>" +
      '<section class="bz-sec"><h3><span class="bz-no">2</span>写成什么样</h3>' +
        '<div class="bz-form"><div><span class="bz-lbl">篇幅</span>' + segB("bfsize", Object.keys(BF_SIZE).map((k) => [k, BF_SIZE[k][0]]), f.size) +
          '<span class="bz-note">' + esc(BF_SIZE[f.size][1]) + "</span></div>" +
          '<label class="wide"><span class="bz-lbl">特别想知道</span><input class="bz-input" id="bzBfFocus" value="' + esc(f.focus) + '" placeholder="可以不填。比如：哪些行业在降价打价格战" maxlength="80"></label></div>' +
      "</section>" +
      '<section class="bz-sec"><h3><span class="bz-no">3</span>会得到什么</h3>' +
        "<p>一份 <b>Markdown 文档（.md）</b>，标题是「" + esc(bfTitle()) + "」，里面按顺序有：</p>" +
        (parts.length ? '<ol class="bz-parts">' + parts.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ol>" : loading()) +
        '<p class="bz-note">文末会列出这份简报用了哪些资料。「机会清单」里的机会会自动放进「机会看板」。</p>' +
      "</section>" +
      '<section class="bz-sec"><h3><span class="bz-no">4</span>存在哪</h3>' +
        '<div class="bz-where"><code>' + esc(info && info.dir ? info.dir : "（正在读…）") + "</code>" +
          '<button type="button" class="bz-btn ghost sm" data-openfolder="">打开这个文件夹</button></div>' +
        '<p class="bz-note">文件名像这样：<code>' + esc(fname) + "</code><br>在软件里：本页右边「最近的简报」，或者「研究分析」→ 报告库，点开就能看、复制全文。文件也可以直接用记事本、Typora 打开。</p>" +
      "</section>" +
      '<section class="bz-sec"><h3><span class="bz-no">5</span>要多久</h3><p>一般 2～6 分钟。交给 AI 池排队写（AI 池在忙就先等），页面顶上会有进度条，可以随时停；写好会提醒你，点「打开报告」就能看。</p></section>' +
      "</div>" +
      '<div class="bz-dlg-f">' + (busy ? '<span class="bz-warn">「' + esc(S.job.title) + "」还在写，等它写完再开始。</span>" : "") + '<span class="sp"></span>' +
        '<button type="button" class="bz-btn ghost" data-close>取消</button>' +
        '<button type="button" class="bz-btn lg" id="bzBfGo" data-act="brief-start" data-autofocus disabled>开始整理</button></div>';
    renderBriefCount();
  }
  function briefStart() {
    const f = S.bf;
    f.notes = $("bzBfNotes").checked; f.web = $("bzBfWeb").checked; f.focus = $("bzBfFocus").value.trim();
    store.set("bf", { size: f.size, notes: f.notes, web: f.web });
    closeModal("bzBrief");
    runJob("market", { scope: "", days: f.days, web: f.web, lens: "market", grp: f.grp === "all" ? "" : f.grp, q: f.q, size: f.size, notes: f.notes, focus: f.focus });
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
      "<span>" + esc(m.engine || "AI") + "写的</span><span>用了你的笔记 " + (m.notes || 0) + " 篇" + (m.radar ? "、市场新闻 " + m.radar + " 条" : "") + (m.web ? "、网页 " + m.web + " 个" : "") + "</span>" +
      (m.opps ? '<button type="button" class="bz-link" data-goto="opps">新增 ' + m.opps + " 个机会，去看板</button>" : "") +
      (r.path ? '<span class="bz-path" title="这份报告在你电脑上的位置">文件：' + esc(r.path) + "</span>" : "");
    let body = m.kind === "custom" ? customBody(r.content, r.plans) : reportBody(r.content, r.chain);   // v187
    if (m.note_ids && m.note_ids.length) {
      body += '<section class="bz-used"><h4>用到的笔记</h4><div class="bz-chips">' + m.note_ids.map((n) =>
        '<button type="button" class="bz-chip" data-note="' + esc(n) + '">' + esc(n.replace(/^\d{8}-\d{6}-/, "").replace(/\.md$/, "").slice(0, 24)) + "</button>").join("") + "</div></section>";
    }
    openReader(m.title, meta, body,
      '<button type="button" class="bz-btn ghost sm" data-openfolder="' + esc(m.id) + '">打开所在文件夹</button>' +
      '<button type="button" class="bz-btn ghost sm" data-kbrep="' + esc(m.id) + '" title="让 AI 把这份报告整理进知识库的主题页">收进知识库</button>' +
      '<button type="button" class="bz-btn ghost sm" data-act="copyrep">复制全文</button>' +
      (m.kind === "custom" ? '<button type="button" class="bz-btn ghost sm" data-goto="custom">改改情况再写</button>' : "") +
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
  async function refreshOverview(which) {
    which = which || "market";
    const m = which === "market";
    try {
      const o = await api("/biz/overview?lens=" + which + "&days=" + (m ? S.mdays : S.days));
      if (o && o.ok === false) throw new Error(o.error || "出错");
      if (m) { S.ovm = o; S.ovmErr = ""; S.ovmAt = Date.now(); if (o.radar && o.radar.ok !== false) S.radar = o.radar; loadRadTops(); }
      else { S.ov = o; S.ovErr = ""; }
    } catch (e) {
      if (m) { S.ovm = null; S.ovmErr = "连不上后台（" + e.message + "）"; } else { S.ov = null; S.ovErr = "连不上后台（" + e.message + "）"; }
    }
    if (m && !S.rfeed) loadRadarFeed(true);
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
    renderTopics();
  }
  async function loadRadarSources() {
    try { S.radarSrc = await api("/biz/radar/sources"); if (S.radarSrc.status) S.radar = S.radarSrc.status; } catch (e) {}
    if (S.pane === "crawler") renderCrawler();
    renderStrips();
  }
  async function loadEngines() {
    try { S.engines = await api("/biz/radar/engines"); } catch (e) {}
    if (S.pane === "crawler") renderEngines();
  }
  async function loadRuns() {
    try { const r = await api("/biz/radar/runs"); S.runs = r.runs || []; } catch (e) { S.runs = S.runs || []; }
    if (S.pane === "crawler") renderRuns();
  }
  async function loadRdItems() {
    if (!S.rdSid) { S.rdItems = null; renderSources(); return; }
    S.rdItems = null; renderSources();
    try { const r = await api("/biz/items?lens=market&sid=" + enc(S.rdSid) + "&limit=40"); S.rdItems = r.items || []; } catch (e) { S.rdItems = []; }
    renderSources();
  }
  async function pollRadar() {
    clearTimeout(S.radarTimer);
    let r = null;
    try { r = await api("/biz/radar/status"); } catch (e) {}
    if (r && r.ok !== false) {
      const was = S.radar && S.radar.running;
      const wasRid = S.radar && S.radar.rid;
      S.radar = r;
      if (!r.running) S.newCut = r.started || r.last_run || 0;
      renderStrips();
      if (S.updOpen && r.running) renderUpd();
      if (r.running) liveTick(r);
      if (r.running && (S.pane === "radar" || S.pane === "industry") && Date.now() - (S.ovmAt || 0) > (S.mdays === -1 ? 20000 : 30000)) {   // v182：扫描时雷达、行业地图一起每 30 秒刷新
        S.ovmAt = Date.now(); refreshOverview("market");
      }
      if (S.pane === "crawler") { renderCrawlerStatus(); renderRuns(); }
      if (was && !r.running) {
        if (LIVE.rid === wasRid) liveTick({ rid: wasRid, started: LIVE.since }, true);   // 最后一批也亮一下
        refreshOverview("market"); loadRadarSources(); loadEngines(); loadRuns();
        if (S.rdSid) loadRdItems();
        if (S.readerRun && S.readerRun === wasRid && !$("bzReader").hidden) openRunReport(wasRid);
        loadRadarFeed(true);
        if (S.updOpen && wasRid) { S.updDone = wasRid; S.updRes = null; renderUpd(); openUpdResult(wasRid); }
        else if (r.trigger !== "auto") toast("爬虫这一轮抓完了，新抓到 " + r.new + " 条。");
      } else if (!was && r.running && S.pane === "crawler") loadRuns();
    }
    const active = root.classList.contains("active");
    if (r && r.running) S.radarTimer = setTimeout(pollRadar, 2500);
    else if (active) S.radarTimer = setTimeout(pollRadar, r && r.auto && r.every <= 5 ? 5000 : 15000);
  }
  async function openUpdResult(rid) {
    let d;
    try { d = await api("/biz/radar/report?id=" + enc(rid)); } catch (e) { d = { ok: false, error: e.message }; }
    if (S.updDone !== rid) return;
    S.updRes = d;
    renderUpd();
  }
  async function radarRun(id, opts) {
    const r = await api("/biz/radar/run", id ? { id: id } : (opts || {})).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) { toast(r.error || "没开始"); return; }
    S.radar = Object.assign({}, S.radar || {}, { running: true, rid: r.rid, done: r.done || 0, total: r.total, new: r.new || 0, current: [], resume: null, resumes: r.resumed ? 1 : 0 });   // 抓得很快时也能认出「抓完了」
    if (id) toast("开始抓这一个了，过程在「爬虫管理」的运行日志里。");
    else if (!S.updOpen) toast(r.resumed ? "接着上次扫：上次扫到 " + r.done + " / " + r.total + "，还剩 " + r.left + " 个。" : "开始抓了：" + r.total + " 个信息源，一般一两分钟抓完。");
    renderBigBtns();
    setTimeout(pollRadar, 500);
  }

  let lastLoad = 0;
  async function load() {
    if (!S.tax) {
      try { S.tax = await api("/biz/taxonomy"); indexTax(); fillTax(); S.taxErr = ""; }
      catch (e) { S.tax = null; S.taxErr = e.message; }
    }
    const now = Date.now();
    if (now - lastLoad > 15000) {
      lastLoad = now;
      refreshOverview("market"); refreshOverview("mine"); refreshReports(); refreshOpps(); refreshTopics();
      loadRadarSources();
      if (S.pane === "crawler") { loadEngines(); loadRuns(); }
      if (S.indSel && S.byId[S.indSel] && !(S.indItems && S.indItems._id === S.indSel + "|" + S.lens)) selectInd(S.indSel);
    }
    pollJob();
    pollRadar();
    renderPane(S.pane);
  }

  function showPane(p) {
    if (!PANES.includes(p)) p = OLD_PANE[p] || "radar";
    S.pane = p;
    store.set("pane", p);
    root.dataset.pane = p;
    root.querySelectorAll(".bz-pane").forEach((el) => { el.hidden = el.dataset.pane !== p; });
    closeReader();
    renderPane(p);
    if ((p === "radar" || p === "industry") && S.ovm && Date.now() - (S.ovmAt || 0) > 30000) refreshOverview("market");   // v182：切过来时数据旧了就刷新
    if (p === "crawler") { loadEngines(); loadRuns(); if (!S.radarSrc) loadRadarSources(); }
    if (p === "custom") cuEnsure();                                 // v187
    if (p === "real") rmEnsure();                                   // v191
    bzLivePlace();                                                  // v190：实时画面跟着放到这一页看得见的地方
  }
  function goPane(p) {
    if (typeof navOpenGroup === "function") navOpenGroup("biz", p);
    else showPane(p);
  }

  // ───────── 事件 ─────────
  function onSeg(name, v) {
    if (name === "mdays") {
      S.mdays = +v; store.set("mdays", S.mdays); S.ovm = null; S.rfeed = null;
      renderPane(S.pane); refreshOverview("market");
      loadRadarFeed();
      if (S.pane === "industry" && S.indSel && S.lens === "market") selectInd(S.indSel);
    }
    else if (name === "rgrp") { S.rgrp = v; segSync("rgrp", v); loadRadarFeed(); }
    else if (name === "bfdays") { S.bf.days = +v; renderBrief(); briefCount(); }
    else if (name === "bfsize") { S.bf.size = v; renderBrief(); }
    else if (name === "lens") {
      S.lens = v === "mine" ? "mine" : "market"; store.set("lens", S.lens);
      if (!curOv()) refreshOverview(S.lens);
      renderPane(S.pane);
      if (S.indSel) selectInd(S.indSel);
    }
    else if (name === "indview") { S.indView = v; store.set("indView", v); renderIndustry(); }
    else if (name === "depth") { S.depth = v; segSync(name, v); }
    else if (name === "cudepth") { S.cu.depth = v === "deep" ? "deep" : "quick"; store.set("cuDepth", S.cu.depth); segSync(name, S.cu.depth); }   // v187
    else if (name === "oppst") { S.oppSt = v; renderOpps(); }
    else if (name === "rmmetric") { S.rm.metric = v; store.set("rmMetric", v); if (v === "quad" && !S.ovm) refreshOverview("market"); renderReal(); }   // v191
    else if (name === "rmview") { S.rm.view = v; store.set("rmView", v); renderReal(); }
    else if (name === "rmdepth") { S.rm.depth = v === "deep" ? "deep" : "quick"; store.set("rmDepth", S.rm.depth); segSync(name, S.rm.depth);  if (S.rm.batchOpen) $("bzRmBatch").innerHTML = rmBatchHTML(); }
    else if (name === "repkind") { S.repKind = v; renderAnalysis(); }
    else if (name === "rdkind") { S.rdKind = v; renderSources(); }
  }
  function startTask() {
    const t = S.task, web = $("bzTaskWeb") ? $("bzTaskWeb").checked : true;
    if (t === "model" || t === "research") {
      const v = ($("bzTaskTarget") || {}).value || "";
      if (v.trim().length < 2) { toast(t === "model" ? "先写上要拆解的公司、产品或生意。" : "先写上要研究的课题。"); if ($("bzTaskTarget")) $("bzTaskTarget").focus(); return; }
      runJob(t, { target: v.trim(), web: t === "research" ? true : web, depth: S.depth });
    } else if (t === "trend") {
      runJob("trend", { scope: $("bzTaskScope").value, web: web });
    } else {
      runJob("market", { scope: $("bzTaskScope").value, days: S.mdays >= 1 ? S.mdays : S.mdays === 0 ? 365 : 1, web: web, lens: "market" });
    }
  }

  function bind() {
    root.addEventListener("click", async (e) => {
      const t = e.target;
      let b;
      if (t.classList && t.classList.contains("bz-modal")) { closeModal(t.id); return; }        // 点窗口外面的灰色部分
      if ((b = t.closest("[data-close]"))) { const m = b.closest(".bz-modal"); if (m) closeModal(m.id); return; }
      if ((b = t.closest("[data-kbrep]"))) {               // v162：把报告收进知识库
        b.disabled = true;
        const r = await api("/kb/enqueue", { sids: ["report:" + b.dataset.kbrep], top: true }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error || "没排进去"); b.disabled = false; return; }
        b.textContent = "✓ 已排进知识库";
        toast(r.added ? "排进知识库的队列了，在左栏「知识库 → 整理记录」能看进度。" : "这份报告之前已经收过或已在队列里。");
        return;
      }
      if ((b = t.closest("[data-openfolder]"))) {
        const r = await api("/biz/open_folder", { id: b.dataset.openfolder || "" }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) toast(r.error || "打不开文件夹"); else toast("已在资源管理器里打开。");
        return;
      }
      if ((b = t.closest(".bz-seg button[data-v]"))) { onSeg(b.parentNode.dataset.seg, b.dataset.v); return; }
      if ((b = t.closest("[data-rmtab]"))) { rmSetTab(b.dataset.rmtab); return; }              // v195：三个标签
      if ((b = t.closest("[data-rm-login]"))) {                                                  // v198：打开登录窗口
        const site = b.dataset.rmLogin;
        if (S.rm.tab !== "trade") rmSetTab("trade");                                            // v200：从体检卡 / 目录点的，切到登录所在的标签
        b.disabled = true; b.textContent = "正在打开…";
        const r = await api("/biz/real/login", { site: site }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error || "登录窗口没打开"); b.disabled = false; }
        else { S.rm.lwait = Object.assign(S.rm.lwait || {}, { [site]: 1 }); toast("登录窗口已经弹出来了（一个新的 Chrome），在里面扫码或输密码登录。"); }
        rmLoad(); return;
      }
      if ((b = t.closest("[data-rm-verify]"))) {                                                 // v199：平台弹了验证，打开窗口自己过
        b.disabled = true; b.textContent = "正在打开…";
        const r = await api("/biz/real/login", { site: b.dataset.rmVerify, action: "verify" }).catch((e) => ({ ok: false, error: e.message }));
        toast(r.ok ? "验证窗口弹出来了：在里面拖一下滑块或输验证码，过了软件会自动收起窗口。" : r.error || "窗口没打开");
        rmLoad(); return;
      }
      if ((b = t.closest("[data-rm-tf]"))) { S.rm.tf = b.dataset.rmTf; rmCatRender(); return; }                  // v201：总表筛选
      if ((b = t.closest("[data-rm-try]"))) {                                                    // v201：试抓一个平台
        const k = b.dataset.rmTry, kw = (($("bzRmTryKw") || {}).value || "").trim() || "宠物";
        const nm = rmShort(((S.rm.data && S.rm.data.sources) || []).find((x) => x.key === "tp_" + k)?.name || k);
        b.disabled = true; b.innerHTML = rmSpin + "开始试抓…";
        const r = await api("/biz/real/trade", { action: "try", key: k, kw: kw }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error || "没开始"); b.disabled = false; b.textContent = "试抓"; return; }
        S.rm.tryWait = Object.assign(S.rm.tryWait || {}, { [k]: 1 });
        if (S.rm.data) { S.rm.data.ttry = S.rm.data.ttry || {}; S.rm.data.ttry[k] = { running: true, kw: r.kw }; }
        toast("开始试抓：用「" + r.kw + "」去" + nm + "搜一下，几十秒后结果出现在这一行。");
        rmTradeRender(); rmLoad(); return;
      }
      if ((b = t.closest("[data-rm-catr]"))) { S.rm.catR = b.dataset.rmCatr; rmCatRender(); return; }          // v199：目录筛选
      if ((b = t.closest("[data-rm-catk]"))) { S.rm.catK = b.dataset.rmCatk; rmCatRender(); return; }
      if ((b = t.closest("[data-rm-logout]"))) {
        if (!confirm("退出登录？之后爬虫抓这个平台会又被要求登录。")) return;
        await api("/biz/real/login", { site: b.dataset.rmLogout, action: "logout" }).catch(() => null);
        rmLoad(); return;
      }
      if ((b = t.closest("[data-rm-chk]"))) { rmOpenCheck(b.dataset.rmChk); return; }            // v191：真实市场
      if ((b = t.closest("[data-rm-redo]"))) { const v = b.dataset.rmRedo; if (S.byId[v]) rmCheck("", v); else rmCheck(v, ""); return; }
      if ((b = t.closest("[data-rm-del]"))) {
        if (!confirm("删掉这条核实记录？（完整报告还在报告库里）")) return;
        await api("/biz/real/check_delete", { id: b.dataset.rmDel }).catch(() => null);
        rmLoad(); return;
      }
      if ((b = t.closest('[data-act^="rm-"]'))) {
        const a = b.dataset.act;
        if (a === "rm-update") {                                   // v193：点了马上变「正在更新…」，做完给一份汇报
          S.rm.updWait = true; S.rm.showReport = false;
          b.disabled = true; b.textContent = "正在更新…";
          const r = await api("/biz/real/update", { force: true }).catch((e) => ({ ok: false, error: e.message }));
          if (!r || r.ok === false) { S.rm.updWait = false; toast("没开始：" + ((r && r.error) || "连不上后台")); }
          rmLoad();
        }
        else if (a === "rm-report-close") { S.rm.showReport = false; renderReal(); }
        else if (a === "rm-apify-save" || a === "rm-apify-off") {                                // v203：Apify 令牌
          const off = a === "rm-apify-off";
          if (off && !confirm("不用 Apify 了？（会删掉存在电脑上的令牌）")) return;
          const tok = off ? "" : $("bzRmApifyT").value.trim();
          if (!off && !tok) { toast("先粘贴 Apify 令牌"); return; }
          const r = await api("/biz/real/trade_cfg", { apify: { token: tok } }).catch((e) => ({ ok: false, error: e.message }));
          if (!r.ok) { toast(r.error || "没存上"); return; }
          $("bzRmApifyT").value = "";
          if (S.rm.data && S.rm.data.trade_cfg) S.rm.data.trade_cfg.apify = r.apify;
          toast(off ? "不用 Apify 了，令牌已删掉。" : "存好了：" + r.apify.plats.join("、") + " 免费办法抓不到时会交给 Apify。在表里点「试抓」试试。");
          rmUnlockRender(); if ($("bzRmTTable")) $("bzRmTTable").__sig = ""; rmCatRender();     // 「还能从哪拿」里的标记跟着变
        }
        else if (a === "rm-unlock-save" || a === "rm-unlock-off") {                            // v202：付费解锁服务
          const off = a === "rm-unlock-off";
          if (off && !confirm("不用付费解锁服务了？（会删掉存在电脑上的钥匙）")) return;
          const body = off ? { provider: "" } : { provider: $("bzRmUnlockP").value, key: $("bzRmUnlockK").value };
          const r = await api("/biz/real/trade_cfg", { unlock: body }).catch((e) => ({ ok: false, error: e.message }));
          if (!r.ok) { toast(r.error || "没存上"); return; }
          $("bzRmUnlockK").value = "";
          if (S.rm.data && S.rm.data.trade_cfg) S.rm.data.trade_cfg.unlock = r.unlock;
          toast(off ? "不用付费解锁服务了，钥匙已删掉。" : "存好了：国外平台免费办法都抓不到时，会交给 " + ((r.unlock.list.find((x) => x.k === r.unlock.provider) || {}).name || "") + "。在表里点「试抓」试试。");
          rmUnlockRender();
        }
        else if (a === "rm-ton" || a === "rm-toff") {                                           // v201：当前筛选的都抓 / 都不抓
          const T = rmTData(), keys = rmTRows(T).filter((x) => x.key && T.src[x.key]).map((x) => x.key), off = new Set(T.off);
          keys.forEach((k) => (a === "rm-ton" ? off.delete(k) : off.add(k)));
          rmTSetOff(off, (a === "rm-ton" ? "这 " : "这 ") + keys.length + " 个平台之后" + (a === "rm-ton" ? "都会抓。" : "都不抓了。"));
        }
        else if (a === "rm-tall") {                                                              // v201：点了马上有反应，结果留在页面上
          const fresh = b.dataset.fresh === "0" ? 0 : 3;
          S.rm.tallBusy = true; S.rm.tallMsg = null; rmTradeRender();
          const r = await api("/biz/real/trade", { action: "all", scope: "all", fresh: fresh }).catch((e) => ({ ok: false, error: e.message }));
          S.rm.tallBusy = false;
          if (!r.ok) S.rm.tallMsg = { at: Date.now(), txt: "没开始：" + (r.error || "") };
          else if (!r.n) S.rm.tallMsg = { at: Date.now(), zero: true, txt: "这 " + r.skipped + " 个行业 3 天内都抓过了，表里勾上的平台也都抓过，这次没有要抓的。想马上全部重新抓一遍，点右边。" };
          else S.rm.tallMsg = { at: Date.now(), txt: "开始抓了：" + r.n + " 个行业" + (r.fill ? "（其中 " + r.fill + " 个以前抓过，这次只补新加的 / 之前没登录的平台）" : "") + (r.skipped ? "，" + r.skipped + " 个 3 天内全抓过的跳过" : "") + "。" };
          toast(S.rm.tallMsg.txt.slice(0, 60));
          rmLoad();
        }
        else if (a === "rm-tmsg-x") { S.rm.tallMsg = null; rmTradeRender(); }
        else if (a === "rm-cat") { rmCatToggle(); }
        else if (a === "rm-login-all") {                                                         // v200：一键登录全部
          const force = b.dataset.force === "1";
          if (force && !confirm("全部重新登录？会先清掉这几个平台现在的登录信息。")) return;
          b.disabled = true; b.innerHTML = '<span class="bz-spin" aria-hidden="true"></span>正在打开登录页…';
          const r = await api("/biz/real/login", { action: "all", force: force }).catch((e) => ({ ok: false, error: e.message }));
          if (!r.ok) toast(r.error || "登录窗口没打开");
          else if (!r.n) toast("都已经登录了。");
          else { (r.sites || []).forEach((k) => { S.rm.lwait = Object.assign(S.rm.lwait || {}, { [k]: 1 }); }); toast("弹出来的 Chrome 里开了 " + r.n + " 个登录页（" + r.names.join("、") + "），一个一个扫码就行，登好一个会自动跳到下一个。"); }
          rmLoad();
        }
        else if (a === "rm-tstop") { await api("/biz/real/trade", { action: "stop" }).catch(() => null); toast("抓完手上这一个就停。"); rmLoad(); }
        else if (a === "rm-close") { S.rm.sel = ""; store.set("rmSel", ""); root.querySelectorAll("#bzRmMain .sel").forEach((e) => e.classList.remove("sel")); rmRenderDetail(); }
        else if (a === "rm-check-sel") rmCheck("", S.rm.sel);
        else if (a === "rm-map") { const id = S.rm.sel; goPane("industry"); if (id) selectInd(id); }
        else if (a === "rm-check") {
          const v = ($("bzRmTarget").value || "").trim(), pk = ($("bzRmPick").value || "").trim();
          if (v.length >= 2) rmCheck(v, "");                     // 自己写了就按写的
          else if (pk) rmCheck("", pk);                          // 否则按下拉框选的
          else { toast("从下拉框选一个行业，或者自己写一个方向；想全核实一遍，点「全部核实」。"); $("bzRmPick").focus(); }
        }
        else if (a === "rm-batch-open") { S.rm.batchOpen = !S.rm.batchOpen; $("bzRmBatch").innerHTML = rmBatchHTML(); }
        else if (a === "rm-batch-close") { S.rm.batchOpen = false; $("bzRmBatch").innerHTML = rmBatchHTML(); }
        else if (a === "rm-batch-start") { b.disabled = true; rmBatch("start", { scope: S.rm.bscope, depth: S.rm.depth, todo: S.rm.btodo }); }
        else if (a === "rm-batch-stop") { if (confirm("停止一个个核实？正在写的这一个会停掉，下次可以接着做。")) rmBatch("stop"); }
        else if (a === "rm-batch-resume") rmBatch("resume");
        else if (a === "rm-batch-clear") rmBatch("clear");
        else if (a === "rm-allchecks") { S.rm.allChecks = !S.rm.allChecks; $("bzRmChecks").innerHTML = rmChecksHTML(); }
        else if (a === "rm-trade") {
          const id = S.rm.sel;
          b.disabled = true;
          await api("/biz/real/trade", { target: id }).catch(() => null);
          setTimeout(() => rmSelect(id, true), 600);
        }
        return;
      }
      if ((b = t.closest("[data-rm]"))) { if (S.rm.tab !== "map") rmSetTab("map"); rmSelect(b.dataset.rm); return; }   // v196：在别的标签里点「在地图上看」→ 回到地图
      if ((b = t.closest("[data-act]"))) {
        const act = b.dataset.act;
        if (act === "back") closeReader();
        else if (act === "guide-hide") { store.set("guideHidden", true); $("bzGuide").hidden = true; }
        else if (act === "clearq") { S.rq = ""; $("bzRq").value = ""; loadRadarFeed(); }
        else if (act === "clearsince") { S.rsince = 0; loadRadarFeed(); }
        else if (act === "rd-run") radarRun();
        else if (act === "upd-open") openUpd();
        else if (act === "rad-back") setRview("radar");
        else if (act === "brief-open") openBrief();
        else if (act === "clearind") { S.rind = ""; loadRadarFeed(); }
        else if (act === "rad-clear" || act === "rad-top") radSet("");
        else if (act === "rad-up") radUp();
        else if (act === "ind-close") { S.indSel = ""; root.querySelectorAll("#bzIndMain .sel").forEach((e) => e.classList.remove("sel")); renderIndDetail(); }   // v183
        else if (act === "art-close") closeArt();
        else if (act === "art-lang") { S.artLang = b.dataset.v === "orig" ? "orig" : "zh"; const it = curArt(); if (it) refreshArt(it); }
        else if (act === "art-retr") { const it = curArt(); if (it) loadTr(it); }
        else if (act === "art-media") { const it = curArt(); if (it) loadMedia(it, true); }
        else if (act === "art-kb") {                      // v162：把这条新闻收进知识库
          const it = curArt();
          if (!it) return;
          const a = S.art[it.url] || {}, tr = S.artTr[it.url], useTr = a.foreign && tr && tr.ok;
          const paras = (useTr ? tr.paras : a.paras) || [];
          let text = paras.length ? paras.join("\n\n") : (a.desc || a.summary || it.text || "");
          if (a.orig && a.orig.paras && a.orig.paras.length) text += "\n\n【原文全文（" + a.orig.site + "）】\n" + a.orig.paras.join("\n\n");   // v179
          const md = S.artMedia[it.url];
          if (md && md.state === "done" && md.paras && md.paras.length) text += "\n\n【视频里说的话】\n" + md.paras.join("\n\n");
          if (a.real) text = "原文：" + a.real + "\n\n" + text;
          const title = (useTr && tr.title ? tr.title + "（" + it.title + "）" : it.title);
          b.disabled = true;
          const r = await api("/kb/enqueue", { kind: "news", title: title, url: it.url, text: (it.who ? "来源：" + it.who + "\n\n" : "") + text, top: true })
            .catch((e) => ({ ok: false, error: e.message }));
          if (!r.ok) { toast(r.error || "没排进去"); b.disabled = false; return; }
          S.kbSent[it.url] = true;
          refreshArt(it);
          toast(r.added ? "排进知识库的队列了，AI 池空了就整理。在左栏「知识库 → 整理记录」能看进度。" : "这条之前已经收过了。");
        }
        else if (act === "upd-start") { b.disabled = true; updStart(); }
        else if (act === "upd-info") { S.updInfo = !S.updInfo; renderUpd(); }
        else if (act === "add-one" || act === "add-batch") {
          const t = act === "add-one" ? ($("bzAddOne").value || "").trim() : ($("bzAddMany").value || "").trim();
          if (!t) { toast(act === "add-one" ? "先填网址或关键词。" : "先填要加的，每行一个。"); return; }
          b.disabled = true;
          await addSources(t);
        }
        else if (act === "upd-all" || act === "upd-none") {
          root.querySelectorAll("[data-upd-grp]").forEach((x) => { x.checked = act === "upd-all"; });
          updSave();
        }
        else if (act === "upd-shownew") {
          const run = S.updRes && S.updRes.run;
          S.rsince = run ? run.started : 0; S.rq = ""; $("bzRq").value = ""; S.rgrp = "all"; segSync("rgrp", "all");
          S.updDone = ""; closeModal("bzUpd"); loadRadarFeed();
          const card = $("bzFeedCard"); if (card) card.scrollIntoView({ block: "start" });
        }
        else if (act === "brief-start") briefStart();
        else if (act === "rd-stop") { b.disabled = true; await api("/biz/radar/stop", {}).catch(() => {}); toast("正在抓的这几个抓完就停。"); pollRadar(); }
        else if (act === "rd-allitems") { S.rdSid = ""; S.rdItems = null; renderSources(); }
        else if (act === "run-refresh" && S.readerRun) openRunReport(S.readerRun);
        else if (act === "stopjob") { b.disabled = true; await api("/biz/stop", {}).catch(() => {}); toast("正在停下…"); pollJob(); }
        else if (act === "jobseen") { store.set("jobSeen", S.job ? S.job.id : 0); renderJob(); }
        else if (act === "ind-research") runJob("industry", { target: S.indSel, web: true, depth: "quick" });
        else if (act === "ind-trend") runJob("trend", { scope: S.indSel, web: true });
        else if (act === "ind-watch") {
          const d = S.byId[S.indSel];
          if (!d) return;
          const kw = d.type === "trk" ? d.name : d.name + " 行业";
          const r = await api("/biz/radar/source", { action: "add", kind: "kw", kw: kw, name: d.name, hint: [d.id] });
          if (r.ok) { toast("已加进爬虫清单：「" + kw + "」，先抓一次给你看。"); loadRadarSources(); radarRun(r.id); }
          else toast(r.error || "没加上");
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
          try { await navigator.clipboard.writeText(S.readerRep.content || ""); toast("已复制全文（Markdown 格式）。"); }
          catch (err) { toast("复制没成功，可以在报告里选中文字手动复制。"); }
        }
        else if (act === "delrep" && S.readerRep) {
          if (!confirm("删掉这份报告？删了找不回来（从它收进看板的机会会留着）。")) return;
          const r = await api("/biz/report_delete", { id: S.readerRep.meta.id });
          if (r.ok) { closeReader(); refreshReports(); toast("删掉了。"); } else toast(r.error || "没删掉");
        }
        else if (act === "rerun" && S.readerRep) {
          const m = S.readerRep.meta;
          if (m.kind === "custom") runJob("custom", { profile: m.profile, web: m.web_on !== false, depth: m.depth || "quick" });   // v187：按当时的情况再写一份
          else runJob(m.kind, { target: m.target, scope: m.scope, days: m.days || 30, web: m.web_on !== false, depth: m.depth || "quick", lens: m.lens || "mine" });
        }
        else if (act === "cu-clear") cuClear();                         // v189：清空前先自动存一份，能撤销
        else if (act === "cu-save") cuSaveNow();                        // v189：保存（也存一份）
        else if (act === "cu-undo") { const id = S.cu.undoId; S.cu.undoId = ""; cuShowUndo(); if (id) cuRestore(id, "撤销了，清空前的情况都回来了。"); }
        else if (act === "cu-saved") { S.cu.savedOpen = !S.cu.savedOpen; renderCuSaved(); }
        else if (act === "ailive") { if (window.cxAiLive) window.cxAiLive.open("biz"); }   // v190：展开标题下面的实时画面
        else if (act === "cu-build-add") cuBuildAdd();                 // v188：阅历「帮我写」拼好的那句加进去
        else if (act === "opennote") {
          const name = b.dataset.name;
          const nb = document.querySelector('.nav-item[data-view="video"][data-video-mode="notes"]');
          if (nb) nb.click();
          setTimeout(() => { if (typeof openVideoNote === "function") openVideoNote(name); }, 80);
        }
        return;
      }
      if ((b = t.closest("[data-cu-restore]"))) { cuRestore(b.dataset.cuRestore); return; }             // v189：换成存过的那一份
      if ((b = t.closest("[data-cu-drop]"))) {
        if (!confirm("删掉存过的这一份？")) return;
        const r = await api("/biz/fit", { action: "drop", id: b.dataset.cuDrop }).catch((e) => ({ ok: false, error: e.message }));
        if (r.ok) { S.cu.saved = r.saved || []; renderCuSaved(); } else toast(r.error || "没删掉");
        return;
      }
      if ((b = t.closest("[data-cu-c]"))) { cuPick(b.dataset.cuC, b.dataset.w); return; }           // v187/v188：商业定制的选项
      if ((b = t.closest("[data-cu-b]"))) { cuBuildPick(b.dataset.cuB, b.dataset.w); return; }
      if ((b = t.closest("[data-cu-open]"))) { cuToggleOpen(b.dataset.cuOpen); return; }
      if (t.closest("#bzCuRun")) { cuStart(); return; }
      if ((b = t.closest("[data-cu-map]"))) { cuMap(b.dataset.cuMap); return; }
      if ((b = t.closest("[data-cu-research]"))) { runJob("research", { target: b.dataset.cuResearch.slice(0, 60), web: true, depth: "quick" }); return; }
      if ((b = t.closest("[data-cu-art]"))) { const it = S.cu.news[b.dataset.cuArt]; if (it) openArtPage(it); return; }
      if ((b = t.closest("[data-cu-dot]"))) { cuJump(b.dataset.cuDot); return; }
      if ((b = t.closest("[data-rep]"))) {
        if (b.closest("#bzJob")) store.set("jobSeen", S.job ? S.job.id : 0);
        openReport(b.dataset.rep);
        if (b.closest("#bzJob")) renderJob();
        return;
      }
      if ((b = t.closest("tr[data-run]"))) { openRunReport(b.dataset.run); return; }
      if ((b = t.closest("[data-note]"))) { openNote(b.dataset.note); return; }
      if ((b = t.closest("[data-goto-task]"))) { S.task = b.dataset.gotoTask; store.set("task", S.task); goPane("analysis"); return; }
      if ((b = t.closest("[data-goto]"))) { goPane(b.dataset.goto); return; }
      if ((b = t.closest("[data-task]"))) { S.task = b.dataset.task; store.set("task", S.task); renderAnalysis(); const i = $("bzTaskTarget"); if (i) i.focus(); return; }
      if ((b = t.closest("[data-term]"))) {
        S.rq = b.dataset.term; $("bzRq").value = S.rq; S.rlimit = 80;
        if (S.pane === "radar" && S.rview === "radar") setRview("list", "");      // v174：在雷达里点词，切到列表看
        loadRadarFeed();
        const card = $("bzFeedCard");
        if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
        return;
      }
      if ((b = t.closest("[data-run-ind]"))) { runJob("industry", { target: b.dataset.runInd, web: true, depth: "quick" }); return; }
      if ((b = t.closest("[data-ind]"))) { if (b.closest("summary")) e.preventDefault(); selectInd(b.dataset.ind); return; }
      if ((b = t.closest("tr[data-row]")) && !t.closest("a,button")) { selectInd(b.dataset.row); return; }
      if ((b = t.closest("[data-mdl]"))) { loadCases(b.dataset.mdl); return; }
      if ((b = t.closest("[data-fill]"))) { const i = $("bzTaskTarget"); if (i) { i.value = b.dataset.fill; i.focus(); } return; }
      if ((b = t.closest("[data-topic-del]"))) {
        const r = await api("/biz/topics", { topics: S.topics.filter((x) => x !== b.dataset.topicDel) });
        S.topics = r.topics || []; renderTopics(); return;
      }
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
      if ((b = t.closest("[data-rd-one]"))) { radarRun(b.dataset.rdOne); return; }
      if ((b = t.closest("[data-rd-items]"))) { S.rdSid = b.dataset.rdItems; loadRdItems(); const c = $("bzRdLatest"); if (c) c.scrollIntoView({ block: "nearest", behavior: "smooth" }); return; }
      if ((b = t.closest("[data-rd-del]"))) {
        if (!confirm("从清单里删掉这个信息源？（已经抓到的内容会留着）")) return;
        const r = await api("/biz/radar/source", { action: "delete", id: b.dataset.rdDel });
        if (r.ok) loadRadarSources(); else toast(r.error || "没删掉");
        return;
      }
      if ((b = t.closest("[data-rd-add]"))) {
        b.disabled = true;
        const r = await api("/biz/radar/source", { action: "add_catalog", ids: [b.dataset.rdAdd] });
        if (r.ok) { toast("加进去了，下一轮就会抓它。"); loadRadarSources(); } else toast(r.error || "没加上");
        return;
      }
      if ((b = t.closest("[data-rd-addgrp]"))) {
        e.preventDefault();
        const g = ((S.radarSrc && S.radarSrc.catalog) || []).find((x) => x.key === b.dataset.rdAddgrp);
        const ids = g ? g.items.filter((x) => !x.added).map((x) => x.id) : [];
        if (!ids.length) return;
        const r = await api("/biz/radar/source", { action: "add_catalog", ids: ids });
        if (r.ok) { toast("加进去 " + r.added + " 个，下一轮就会抓。"); loadRadarSources(); } else toast(r.error || "没加上");
        return;
      }
      if ((b = t.closest("[data-addmode]"))) { S.updAdd.mode = b.dataset.addmode; S.updAdd.msg = ""; renderUpd(); const f = $(b.dataset.addmode === "one" ? "bzAddOne" : "bzAddMany"); if (f) f.focus(); return; }
      if ((b = t.closest("[data-rd-more]"))) { S.rdShowAll[b.dataset.rdMore] = !S.rdShowAll[b.dataset.rdMore]; renderSources(); return; }
      if ((b = t.closest("[data-lib]"))) {                 // v170：从推荐库加信息源
        const v = b.dataset.lib;
        b.disabled = true;
        const body = v === "site" ? { min_w: 1, kinds: ["site"] } : { min_w: +v };
        const r = await api("/biz/radar/library", body).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { toast(r.error || "没加成"); b.disabled = false; return; }
        toast("加进来 " + r.added + " 个信息源，清单里现在一共 " + r.total + " 个。");
        S.radarSrc = null;
        if (typeof loadRadarSources === "function") loadRadarSources();
        try { S.plan = await api("/biz/radar/plan"); } catch (e) {}
        renderUpd(); pollRadar();
        return;
      }
      if (t.closest("#bzRadar svg.bz-rad-svg")) { radClick(t); return; }               // v177：点饼上的一片 / 一圈 / 一个点
      if ((b = t.closest("[data-radcell]"))) { radSet("c:" + b.dataset.radcell); return; }
      if ((b = t.closest("[data-rview]"))) { setRview(b.dataset.rview, b.dataset.rview === "list" ? S.rind : ""); return; }
      if ((b = t.closest("[data-rad-list]"))) { setRview("list", b.dataset.radList); return; }
      if ((b = t.closest("[data-rad]"))) { selectRad(b.dataset.rad); return; }
      if ((b = t.closest("[data-art]"))) { if (b.dataset.art && !b.disabled) openArt(b.dataset.art, !!b.closest("#bzFeed, #bzReadP, #bzRadar")); return; }
      // v164：点新闻这一行的任何地方（除了链接、按钮）都能打开
      if (!t.closest("a, button, input, select, textarea, label") && (b = t.closest(".bz-item.clickable[data-row]")) && S.artItems[b.dataset.row]) {
        if (window.getSelection && String(window.getSelection()).length) return;      // 在选文字，不算点击
        openArt(b.dataset.row, !!b.closest("#bzFeed, #bzRadar"));
        return;
      }
      if ((b = t.closest("[data-page]"))) { if (!b.disabled) goPage(+b.dataset.page); return; }
      if (t.closest("#bzUpdBtn")) { openUpd(); return; }
      if (t.closest("#bzBriefRun")) { openBrief(); return; }
      if ((b = t.closest("[data-radtab]"))) { S.radTab = b.dataset.radtab; renderRadPanel(); return; }
      if (t.closest("#bzTaskRun")) { startTask(); return; }
      if (t.closest("#bzTaskSave")) {
        const v = (($("bzTaskTarget") || {}).value || "").trim();
        if (v.length < 2) { toast("先在输入框里写上课题。"); return; }
        const r = await api("/biz/topics", { topics: [v].concat(S.topics) });
        S.topics = r.topics || []; renderTopics(); toast("存好了，以后点一下就能填进去。"); return;
      }
      if (t.closest("#bzOpAddBtn")) { $("bzOpAdd").hidden = !$("bzOpAdd").hidden; if (!$("bzOpAdd").hidden) $("bzOaTitle").focus(); return; }
      if (t.closest("#bzRdAdd")) {
        const v = $("bzRdTarget").value.trim();
        if (v.length < 2) { toast(S.rdKind === "kw" ? "先写上关键词。" : "先填网址。"); $("bzRdTarget").focus(); return; }
        const hint = $("bzRdHint").value;
        const body = { action: "add", kind: S.rdKind, name: $("bzRdName").value.trim(), hint: hint ? [hint] : [] };
        if (S.rdKind === "kw") body.kw = v; else body.url = v;
        const r = await api("/biz/radar/source", body);
        if (r.ok) { $("bzRdTarget").value = ""; $("bzRdName").value = ""; $("bzRdHint").value = ""; toast("加进清单了，现在先抓它一次。"); await loadRadarSources(); radarRun(r.id); }
        else toast(r.error || "没加上");
        return;
      }
    });
    root.addEventListener("mousedown", (e) => {                                                   // v202：点平台 → 打开它的搜索页
      const a = e.button === 0 && e.target.closest("a[data-open]");
      if (a) { window.open(a.href, "_blank", "noopener"); a.dataset.opened = String(Date.now()); }
    });
    root.addEventListener("click", (e) => {
      const a = e.target.closest("a[data-open]");
      if (!a) return;
      e.preventDefault();                                                                         // mousedown 已经打开过了
      if (!a.dataset.opened || Date.now() - Number(a.dataset.opened) > 1500) window.open(a.href, "_blank", "noopener");   // 键盘回车这种没有 mousedown 的
    }, true);
    root.addEventListener("change", async (e) => {
      const t = e.target;
      if (t.matches("#bzCuForm select[data-cu]")) { cuQueueSave(120); return; }        // v187：商业定制
      if (t.id === "bzRmUnlockP") { rmUnlockRender(); return; }                                  // v202
      if (t.matches("[data-rm-on]")) {                                                          // v201：每个平台单独勾选抓不抓
        const off = new Set(rmTData().off), k = t.dataset.rmOn;
        if (t.checked) off.delete(k); else off.add(k);
        const nm = rmShort(((S.rm.data && S.rm.data.sources) || []).find((x) => x.key === "tp_" + k)?.name || k);
        rmTSetOff(off, (t.checked ? "之后会抓：" : "之后不抓：") + nm); return;
      }
      if (t.matches("[data-rm-reg]")) {                                                          // v199：按地区开关国外平台
        const regions = {};
        root.querySelectorAll("[data-rm-reg]").forEach((x) => { regions[x.dataset.rmReg] = x.checked; });
        await api("/biz/real/trade_cfg", { regions: regions }).catch(() => null);
        toast((t.checked ? "之后会抓：" : "之后不抓：") + (t.closest("label").querySelector("b") || {}).textContent); rmLoad(); return;
      }
      if (t.id === "bzRmForeign") { await api("/biz/real/trade_cfg", { foreign: t.checked }).catch(() => null); toast(t.checked ? "之后会顺便抓国外平台。" : "之后不抓国外平台了。"); rmLoad(); return; }   // v198
      if (t.id === "bzRmPick") { S.rm.pick = t.value; if (t.value) $("bzRmTarget").value = ""; return; }        // v192：真实市场下拉框
      if (t.id === "bzRmBScope") { S.rm.bscope = t.value; $("bzRmBatch").innerHTML = rmBatchHTML(); return; }
      if (t.id === "bzRmBTodo") { S.rm.btodo = t.checked; $("bzRmBatch").innerHTML = rmBatchHTML(); return; }
      if (t.id === "bzCuWeb") { S.cu.web = t.checked; store.set("cuWeb", t.checked); return; }
      if (t.matches("[data-opp-st]")) {
        const r = await api("/biz/opp", { action: "update", id: t.dataset.oppSt, status: t.value });
        if (r.ok) { S.opps = r.items; renderOpps(); }
      } else if (t.id === "bzTaskScope") store.set("taskScope", t.value);
      else if (t.id === "bzPgSize") { S.rsize = +t.value; store.set("rsize", S.rsize); loadRadarFeed(); }
      else if (t.id === "bzRadFreq") setFreq(t.value);
      else if (t.id === "bzAddGrp") { if (S.updAdd) S.updAdd.group = t.value; }
      else if (t.id === "bzUpdEvery" && t.value === "custom") { S.updCustom = true; renderUpd(); const n = $("bzUpdEveryN"); if (n) { n.focus(); n.select(); } }
      else if (t.id === "bzUpdEvery") { S.updCustom = false; updSave(); }
      else if (["bzUpdAuto", "bzUpdEveryN", "bzUpdWorkers", "bzUpdScFast", "bzUpdScBrowser"].includes(t.id) || t.id === "bzUpdFailOnly" || t.matches("[data-upd-grp]")) updSave();
      else if (t.id === "bzUpdForce") { S.updForce = t.checked; renderUpd(); }
      else if (t.id === "bzUpdFresh") { S.updFresh = t.checked; renderUpd(); }
      else if (t.id === "bzBfGrp") { S.bf.grp = t.value; briefCount(); }
      else if (t.id === "bzBfNotes") S.bf.notes = t.checked;
      else if (t.id === "bzBfWeb") S.bf.web = t.checked;
      else if (t.matches("[data-rd-w]")) {               // v170：改权重
        const r = await api("/biz/radar/source", { action: "set_w", id: t.dataset.rdW, w: +t.value }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) toast(r.error || "没改成"); else { const x = S.radarSrc && S.radarSrc.sources.find((y) => y.id === t.dataset.rdW); if (x) x.w = r.w; t.className = "bz-select sm bz-rd-w w" + r.w; }
      }
      else if (t.matches("[data-rd-toggle]")) {
        const r = await api("/biz/radar/source", { action: "toggle", id: t.dataset.rdToggle, enabled: t.checked });
        if (r.ok) loadRadarSources(); else toast(r.error || "没改成");
      } else if (t.id === "bzRdAuto" || t.id === "bzRdEvery") {
        const r = await api("/biz/radar/config", { auto: $("bzRdAuto").checked, every: +$("bzRdEvery").value });
        if (r.ok) { toast($("bzRdAuto").checked ? "好的，会按时自动抓。" : "自动更新关了，要抓时点「现在就抓一次」。"); pollRadar(); }
      }
    });
    let qTimer = null;
    root.addEventListener("input", (e) => {
      const t = e.target;
      if (t.id === "bzIndQ") { S.indQ = t.value; clearTimeout(qTimer); qTimer = setTimeout(renderIndustry, 160); }
      else if (t.id === "bzRmTarget") { if (t.value.trim() && $("bzRmPick").value) { $("bzRmPick").value = ""; S.rm.pick = ""; } }
      else if (t.id === "bzRmQ") { S.rm.q = t.value; clearTimeout(qTimer); qTimer = setTimeout(renderReal, 160); }   // v191
      else if (t.id === "bzRq") { clearTimeout(qTimer); qTimer = setTimeout(() => { S.rq = t.value.trim(); loadRadarFeed(); }, 350); }
      else if (t.id === "bzBfQ") { S.bf.q = t.value.trim(); clearTimeout(qTimer); qTimer = setTimeout(briefCount, 350); }
      else if (t.id === "bzBfFocus") S.bf.focus = t.value;
      else if (t.id === "bzRepQ") { S.repQ = t.value; renderAnalysis(); }
      else if (t.matches && t.matches("#bzCuForm [data-cu]")) { cuSyncChips(); cuQueueSave(700); }   // v187：停手 0.7 秒就保存、重新配
    });
    root.addEventListener("mouseover", (e) => {                       // v187：商业定制——列表和图上的点一起标出来
      const t = e.target;
      if (!t.closest || S.pane !== "custom") return;
      const c = t.closest(".bz-cu-c[data-cu-id], .bz-cu-svg .dot[data-cu-dot]");
      cuPeek(c ? c.dataset.cuId || c.dataset.cuDot : "");
    });
    root.addEventListener("focusin", (e) => { if (e.target.matches && e.target.matches(".bz-cu-svg .dot[data-cu-dot]")) cuPeek(e.target.dataset.cuDot); });
    let cuRz = null;
    window.addEventListener("resize", () => { if (S.pane !== "custom") return; clearTimeout(cuRz); cuRz = setTimeout(renderCuChart, 160); });
    root.addEventListener("mouseover", (e) => {
      const t = e.target;
      if (!t.closest) return;
      if (t.closest("#bzRadar svg.bz-rad-svg")) {                 // v177：圆点、一圈上都有提示
        const g = t.closest("g.blip[data-rad]"), c = t.closest("g.cell[data-cell]");
        radHover(c);                                              // v178：鼠标放在哪一圈，那一圈变大一点
        if (g) radTip(g.dataset.rad, true);
        else if (c && t.classList.contains("band-c")) radTip("c:" + c.dataset.cell, true);
        else radTip("", false);
        return;
      }
      const lr = t.closest("#bzRadPanel [data-rad], #bzRadPanel [data-radcell]");   // 右边列表移到哪一行，饼上标出来
      radPeek(lr ? (lr.dataset.rad || "c:" + lr.dataset.radcell) : "");
    });
    root.addEventListener("mouseout", (e) => {
      const t = e.target, to = e.relatedTarget;
      if (!t.closest) return;
      const svg = t.closest("#bzRadar svg.bz-rad-svg");
      if (svg && !(to && svg.contains(to))) { radTip("", false); radHover(null); }
      if (t.closest("#bzRadPanel") && !(to && to.closest && to.closest("#bzRadPanel [data-rad], #bzRadPanel [data-radcell]"))) radPeek("");
    });
    root.addEventListener("focusin", (e) => { if (e.target.matches && e.target.matches("#bzRadar g.blip[data-rad]")) radTip(e.target.dataset.rad, true); });
    root.addEventListener("focusout", (e) => { if (e.target.matches && e.target.matches("#bzRadar g.blip[data-rad]")) radTip("", false); });
    root.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.isComposing) {
        if (e.target.id === "bzTaskTarget") { e.preventDefault(); startTask(); }
        else if (e.target.id === "bzRmTarget") { e.preventDefault(); const b = root.querySelector('[data-act="rm-check"]'); if (b) b.click(); }   // v191
        else if (e.target.id === "bzAddOne") { e.preventDefault(); const b = root.querySelector('[data-act="add-one"]'); if (b) b.click(); }
        else if (e.target.matches && e.target.matches("tr[data-run]")) { e.preventDefault(); openRunReport(e.target.dataset.run); }
      }
      if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches("#bzRadar g.blip[data-rad]")) { e.preventDefault(); selectRad(e.target.dataset.rad); }
      if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches(".bz-cu-svg .dot[data-cu-dot]")) { e.preventDefault(); cuJump(e.target.dataset.cuDot); }
    });
    root.addEventListener("toggle", (e) => {
      const d = e.target;
      if (d && d.matches && d.matches("details[data-l1]")) S.openL1[d.dataset.l1] = d.open;
      if (d && d.matches && d.matches("details[data-grp]")) S.rdOpen[d.dataset.grp] = d.open;
    }, true);
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || !root.classList.contains("active")) return;
      if (!$("bzBrief").hidden) closeModal("bzBrief");
      else if (S.artSel && $("bzReader").hidden && !$("bzReadP").hidden) closeArt();
      else if (!$("bzUpd").hidden) closeModal("bzUpd");
      else if (!$("bzReader").hidden) closeReader();
      else if (S.radSel && S.pane === "radar" && S.rview === "radar") radUp();     // v177：雷达上一层层退回
      else if (S.pane === "real" && S.rm.sel) { S.rm.sel = ""; store.set("rmSel", ""); rmRenderDetail(); renderReal(); }   // v191
      else if (S.pane === "industry" && S.indSel) { S.indSel = ""; root.querySelectorAll("#bzIndMain .sel").forEach((e) => e.classList.remove("sel")); renderIndDetail(); }   // v183
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
