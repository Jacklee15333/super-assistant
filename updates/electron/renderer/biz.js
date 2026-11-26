// ============================================================
// biz.js —「商业」（v155 新增，v157 重新整理成五块；v158 新闻分页、「现在更新」「整理成简报」改成带说明和设置的面板；v159 去掉大按钮图标、改名「生成简报」、自动更新最短 5 分钟可自己填）
//   市场雷达：爬虫抓来的最新新闻——市场上正在发生什么（升温话题、提得最多、一键整理成简报）
//   行业地图：申万 31 个一级行业 + 二级行业 + 新兴赛道，「市场实时 / 我关注的」两种看法，地图和列表两种摆法
//   研究分析：挑一件事让 AI 写报告——拆解商业模式（含产业链图）、研究课题、找趋势和机会、市场动向简报；报告库
//   机会看板：报告里找到的机会 + 自己记的点子
//   爬虫管理：用的是哪些爬虫、现在在干什么、每一轮的抓取记录和结果报告、信息源清单
// 顶部五个标签由 renderer.js 的 NAV_GROUPS.biz 画，切换时调 window.cxPaneShow.biz(标签)。
// 复用全局：BACKEND、renderMarkdown、navOpenGroup、openVideoNote（都可能不存在，判断了再用）。
// ============================================================
(function () {
  "use strict";
  const root = document.getElementById("view-biz");
  if (!root) return;

  const PANES = ["radar", "industry", "analysis", "opps", "crawler"];
  const OLD_PANE = { market: "radar", model: "analysis", reports: "analysis" };
  const KIND = { market: "市场动向简报", industry: "行业研究", model: "商业模式", trend: "趋势与机会", research: "课题研究" };
  const SRC = { note: "笔记", sniff: "网站动态", creator: "博主新内容", radar: "市场新闻" };
  const GRP = { news: "财经媒体", corp: "大公司官网", corpkw: "大公司动态", media: "行业媒体", indkw: "行业热词", policy: "政策数据", global: "海外", mine: "我加的" };
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
    artSel: "", art: {}, artTr: {}, artLang: "zh", artItems: {}, trTitle: {}, kbSent: {},
    read: new Set(store.get("read", [])),       // v164：点开看过的新闻（标题变淡、不再标「新」）
    plan: null, updOpen: false, updDone: "", updRes: null, briefOpen: false, bf: null, briefInfo: null,
    lens: store.get("lens", "market") === "mine" ? "mine" : "market", days: 30,
    indView: store.get("indView", "map"), indSel: store.get("indSel", ""), indQ: "", indItems: null, openL1: {},
    task: store.get("task", "model"), depth: "quick",
    mdl: "", mdCases: null, opps: null, oppSt: "all", reports: [], repKind: "all", repQ: "", topics: [],
    job: null, jobTimer: null, readerRep: null, readerRun: "",
    radar: null, radarTimer: null, radarSrc: null, engines: null, runs: null,
    rdKind: "site", rdSid: "", rdItems: null, rdOpen: {},
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
  const MDAYS_SEG = () => seg("mdays", [["1", "24 小时"], ["3", "3 天"], ["7", "7 天"], ["30", "30 天"]]);

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
          "<li><b>研究分析</b>：挑一件事，让 AI 深入研究、写成报告（商业模式、课题、趋势机会、简报）。</li>" +
          "<li><b>机会看板</b>：报告里找到的机会自动放这里，也能记自己的点子。</li>" +
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
              '<button type="button" role="tab" data-rview="radar">雷达扫描</button><button type="button" role="tab" data-rview="list">新闻列表</button></div>' +
            '<span class="bz-rgrp" id="bzRgrpWrap">' + seg("rgrp", [["all", "全部"], ["news", "财经媒体"], ["corp,corpkw", "大公司"], ["media,indkw", "行业媒体"], ["policy", "政策数据"], ["global", "海外"], ["mine", "我加的"]]) + "</span></div>" +
            '<div class="bz-radar" id="bzRadar"></div>' +
            '<div id="bzListWrap"><p class="bz-filter" id="bzFeedFilter" hidden></p><div class="bz-feed" id="bzFeed"></div>' +
            '<nav class="bz-pager" id="bzPager" aria-label="翻页" hidden></nav></div></section></div>' +
          '<aside class="bz-side">' +
            '<section class="bz-card"><div class="bz-card-h"><h3>正在升温</h3></div><p class="bz-hint" id="bzRisingHint"></p><div class="bz-terms" id="bzRising"></div></section>' +
            '<section class="bz-card"><div class="bz-card-h"><h3>提得最多</h3></div><div class="bz-chips" id="bzHot"></div></section>' +
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
        '<div class="bz-ind"><div class="bz-ind-main" id="bzIndMain"></div><aside class="bz-ind-detail" id="bzIndDetail"></aside></div>' +
      "</div>" +

      // ===== 研究分析 =====
      '<div class="bz-pane" data-pane="analysis">' +
        '<section class="bz-hero"><h2>研究分析</h2>' +
          "<p>挑一件事，让 AI 帮你写成报告。小助会先从你收进来的内容和爬虫抓到的新闻里挑相关的，勾了「联网」还会自己上网搜、读网页，再交给 AI 写。" +
          "写好的报告都在下面的报告库；报告里找到的机会会放进「机会看板」。</p>" +
          '<div class="bz-tasks" role="group" aria-label="要做什么">' + TASKS.map(([k, t, d]) =>
            '<button type="button" class="bz-task" data-task="' + k + '" aria-pressed="false"><b>' + t + "</b><span>" + d + "</span></button>").join("") + "</div>" +
          '<div class="bz-taskform" id="bzTaskForm"></div></section>' +
        '<section class="bz-card"><div class="bz-card-h"><h3>报告库</h3>' +
          seg("repkind", [["all", "全部"], ["model", "商业模式"], ["research", "课题研究"], ["industry", "行业研究"], ["trend", "趋势与机会"], ["market", "市场动向简报"]]) +
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
    const v = S.rview === "list" ? "list" : "radar";
    root.querySelectorAll("[data-rview]").forEach((b) => { b.setAttribute("aria-selected", String(b.dataset.rview === v)); b.classList.toggle("on", b.dataset.rview === v); });
    const rd = $("bzRadar"), lw = $("bzListWrap"), gw = $("bzRgrpWrap");
    if (rd) rd.hidden = v !== "radar";
    if (lw) lw.hidden = v !== "list";
    if (gw) gw.hidden = v !== "list";
    const cols = $("bzCols");
    if (cols) cols.classList.toggle("wide", v === "radar");     // v168：雷达模式下右边栏挪到下面，雷达能放大
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
  const RAD_SEC = { "科技": "#3b6fd1", "消费": "#c4613a", "医药": "#2f8f5b", "制造": "#7a5cc2", "周期资源": "#a0711a", "金融地产": "#c23b6a", "公用交运": "#2a8a9a" };
  // v168：新兴赛道太笼统，按方向再分成 5 块，每块自己一种颜色
  const TRK_GROUPS = [
    ["赛道·智能科技", "#0f8fb3", ["t:ai", "t:compute", "t:chip", "t:data", "t:robot", "t:future"]],
    ["赛道·新能源与出行", "#3a9a3a", ["t:ev", "t:energy", "t:autodrive", "t:lowalt", "t:space"]],
    ["赛道·新消费", "#d9822b", ["t:newcons", "t:discount", "t:tea", "t:pet"]],
    ["赛道·内容与电商", "#b5508f", ["t:livecom", "t:crossborder", "t:creator", "t:edu", "t:local"]],
    ["赛道·健康养老", "#5a8f7b", ["t:biotech", "t:silver"]],
  ];
  function radarModel() {
    const ov = S.ovm, t = S.tax;
    if (!ov || !t) return null;
    const d = S.mdays, l1 = ov.l1 || {}, hh = ov.heat || {};
    const hv = (id) => l1[id] || hh[id] || [0, 0];       // 一级行业的条数在 l1 里，赛道在 heat 里
    const mk = (id, name, sec) => ({ id, name, n: hv(id)[0], t: hv(id)[1], sec });
    const groups = t.sectors.map((sec) => ({ key: sec.key, name: sec.name, color: RAD_SEC[sec.name] || "#888", items: sec.l1.map((id) => mk(id, nameOf(id), sec.name)) }));
    const known = new Set(t.tracks.map((x) => x.id)), used = new Set();
    TRK_GROUPS.forEach(([name, color, ids]) => {
      const its = ids.filter((id) => known.has(id)).map((id) => { used.add(id); return mk(id, nameOf(id), name); });
      if (its.length) groups.push({ key: name, name, color, items: its, trk: true });
    });
    const rest = t.tracks.filter((x) => !used.has(x.id));             // 以后新加的赛道，先放「赛道·其他」
    if (rest.length) groups.push({ key: "trk-other", name: "赛道·其他", color: "#9a8a6a", items: rest.map((x) => mk(x.id, x.name, "赛道·其他")), trk: true });
    let max = 1, total = 0;
    groups.forEach((g) => g.items.forEach((it) => {
      max = Math.max(max, it.n);
      it.hot = d > 1 && it.t >= 3 && it.t >= (it.n * 2) / d;          // 最近 24 小时的量明显高于这段时间的日均
      it.color = g.color;
    }));
    groups.forEach((g) => { g.n = g.items.reduce((a, x) => a + x.n, 0); total += g.n; });
    return { groups, max, total };
  }
  function renderRadarScan() {
    const el = $("bzRadar");
    if (!el || el.hidden) return;
    const M = radarModel();
    if (!M) { el.innerHTML = loading(S.ovmErr ? "读不到：" + S.ovmErr : "正在扫描…"); return; }
    if (!(S.ovm.counts && S.ovm.counts.radar)) { el.innerHTML = empty('爬虫还没抓到东西。点上面的<button type="button" class="bz-link" data-act="upd-open">现在更新</button>马上抓一次。'); return; }
    // v168：雷达放大；每一块扇形里的圆点按「一圈一圈」排，保证都在自己那块里、互不重叠；同一块里新闻多的排在里圈
    const W = 720, C = W / 2, R = 310, R0 = 70, GAP = 0.02;
    const weights = M.groups.map((g) => Math.max(2.4, g.items.length));
    const wsum = weights.reduce((a, b) => a + b, 0);
    let a0 = -Math.PI / 2;
    const pt = (r, a) => [C + r * Math.cos(a), C + r * Math.sin(a)];
    let wedges = "", labels = "", blips = "", spokes = "";
    const pos = [];
    const sizeOf = (n) => (n ? 5 + 13 * Math.sqrt(n / M.max) : 3);
    M.groups.forEach((g, gi) => {
      const span = (weights[gi] / wsum) * Math.PI * 2, a1 = a0 + span;
      const [x0, y0] = pt(R, a0), [x1, y1] = pt(R, a1), [i0x, i0y] = pt(R0, a0), [i1x, i1y] = pt(R0, a1);
      wedges += '<path d="M' + i0x.toFixed(1) + "," + i0y.toFixed(1) + " L" + x0.toFixed(1) + "," + y0.toFixed(1) + " A" + R + "," + R + " 0 " + (span > Math.PI ? 1 : 0) + " 1 " + x1.toFixed(1) + "," + y1.toFixed(1) +
        " L" + i1x.toFixed(1) + "," + i1y.toFixed(1) + " A" + R0 + "," + R0 + " 0 0 0 " + i0x.toFixed(1) + "," + i0y.toFixed(1) +
        ' Z" class="wedge' + (S.radSel && g.items.some((x) => x.id === S.radSel) ? " on" : "") + '" fill="' + g.color + '" fill-opacity="' + (gi % 2 ? 0.07 : 0.12) + '"/>';
      spokes += '<line x1="' + i0x.toFixed(1) + '" y1="' + i0y.toFixed(1) + '" x2="' + x0.toFixed(1) + '" y2="' + y0.toFixed(1) + '" class="sp"/>';
      // 块名写在外圈，跟着扇形中线
      const am = a0 + span / 2, [lx, ly] = pt(R + 20, am);
      const anchor = Math.abs(Math.cos(am)) < 0.3 ? "middle" : Math.cos(am) > 0 ? "start" : "end";
      const dy = Math.sin(am) > 0.3 ? 14 : Math.sin(am) < -0.3 ? -2 : 5;
      labels += '<text x="' + lx.toFixed(1) + '" y="' + (ly + dy).toFixed(1) + '" text-anchor="' + anchor + '" class="secl" fill="' + g.color + '">' + esc(g.name) +
        '<tspan class="secn"> ' + g.n + "</tspan></text>";
      // 圆点：有新闻的按条数从多到少，从里圈往外一圈圈排；没新闻的小灰点排在最外圈
      const act = g.items.filter((x) => x.n).sort((p, q) => q.n - p.n), quiet = g.items.filter((x) => !x.n);
      const aIn = a0 + GAP, aSpan = span - GAP * 2;
      let r = R0 + 32, k = 0;
      while (k < act.length) {
        const slots = Math.max(1, Math.floor((r * aSpan) / 66));
        const row = act.slice(k, k + slots);
        row.forEach((it, j) => {
          const a = aIn + aSpan * ((j + 0.5) / row.length);
          const [x, y] = pt(r, a);
          pos.push({ it, g, x, y, size: sizeOf(it.n), lab: k + j < 2 || (r > R0 + 120 && k + j < 4) });
        });
        k += row.length;
        r += 60;
        if (r > R - 36) r = R - 36;                          // 实在太多就挤在最外一圈
      }
      quiet.forEach((it, j) => {
        const a = aIn + aSpan * ((j + 0.5) / quiet.length), [x, y] = pt(R - 12, a);
        pos.push({ it, g, x, y, size: 3, lab: false });
      });
      a0 = a1;
    });
    // 名字互相压住的，条数少的那个不写（鼠标移上去能看到）
    const boxes = [];
    pos.filter((p) => p.lab && p.it.n).sort((p, q) => q.it.n - p.it.n).forEach((p) => {
      const nm = p.it.name.length > 6 ? 6 : p.it.name.length;
      const w = nm * 15 + 4, bx = p.x - w / 2, by = p.y + p.size + 2, h = 17;
      if (boxes.some((o) => bx < o[0] + o[2] && bx + w > o[0] && by < o[1] + o[3] && by + h > o[1])) { p.lab = false; return; }
      boxes.push([bx, by, w, h]);
    });
    S.radPos = {};
    S.radVB = { x: -170, y: -50, w: W + 340, h: W + 100, C: C, R: R };
    pos.forEach(({ it, g, x, y, size, lab }) => {
      S.radPos[it.id] = { x, y, color: g.color };
      const sel = S.radSel === it.id;
      const name = it.name.length > 6 ? it.name.slice(0, 5) + "…" : it.name;
      blips += '<g class="blip' + (it.n ? "" : " quiet") + (it.hot ? " hot" : "") + (sel ? " sel" : "") + '" data-rad="' + esc(it.id) + '" tabindex="' + (it.n ? 0 : -1) + '" role="button" aria-label="' +
        esc(it.name + "，" + it.n + " 条新闻" + (it.hot ? "，正在升温" : "")) + '">' +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (size + 8).toFixed(1) + '" class="hit"/>' +
        (it.hot ? '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (size + 4).toFixed(1) + '" class="ring" stroke="' + g.color + '"/>' : "") +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + size.toFixed(1) + '" fill="' + g.color + '" class="dot"/>' +
        ((lab || sel) && it.n ? '<text x="' + x.toFixed(1) + '" y="' + (y + size + 15).toFixed(1) + '" text-anchor="middle" class="bl">' + esc(name) + "</text>" : "") + "</g>";
    });
    const rings = [0.25, 0.5, 0.75, 1].map((k) => '<circle cx="' + C + '" cy="' + C + '" r="' + (R * k).toFixed(1) + '" class="rg"/>').join("");
    const svg = '<svg class="bz-rad-svg" viewBox="' + S.radVB.x + " " + S.radVB.y + " " + S.radVB.w + " " + S.radVB.h + '" role="img" aria-label="市场雷达：按行业分好类的新闻，越靠近中心新闻越多">' +
      '<defs><radialGradient id="bzRadBg"><stop offset="0" stop-color="var(--accent)" stop-opacity=".10"/><stop offset="1" stop-color="var(--accent)" stop-opacity=".02"/></radialGradient>' +
      '<linearGradient id="bzSweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="var(--accent)" stop-opacity="0"/><stop offset="1" stop-color="var(--accent)" stop-opacity=".28"/></linearGradient></defs>' +
      '<circle cx="' + C + '" cy="' + C + '" r="' + R + '" fill="url(#bzRadBg)"/>' + wedges + rings + spokes +
      '<g class="sweep" style="transform-origin:' + C + "px " + C + 'px"><path d="M' + C + "," + C + " L" + (C + R) + "," + C + " A" + R + "," + R + " 0 0 0 " + pt(R, -0.55)[0].toFixed(1) + "," + pt(R, -0.55)[1].toFixed(1) + ' Z" fill="url(#bzSweep)"/>' +
        '<line x1="' + C + '" y1="' + C + '" x2="' + (C + R) + '" y2="' + C + '" class="sw-l"/></g>' +
      '<circle cx="' + C + '" cy="' + C + '" r="' + (R0 - 4) + '" class="hub"/><circle cx="' + C + '" cy="' + C + '" r="4" class="ctr"/>' + labels + blips + "</svg>";
    const oldLive = $("bzRadLive");                         // 重画雷达时，正在亮的那几条留着接着演
    el.innerHTML = '<div class="bz-rad-l"><div class="bz-rad-bar" id="bzRadBar" aria-live="polite"></div>' +
      '<div class="bz-rad-stage">' + svg + '<div class="bz-rad-live" id="bzRadLive"></div><div class="bz-rad-tip" id="bzRadTip" hidden></div></div>' +
      '<p class="bz-rad-legend"><span><i class="lg-near"></i>每块里新闻越多越靠里、圆点越大</span>' + (S.mdays > 1 ? '<span><i class="lg-hot"></i>带圈的：最近 24 小时明显变多</span>' : "") +
      '<span><i class="lg-quiet"></i>边上的小灰点：这段时间没新闻</span></p></div>' +
      '<div class="bz-rad-r" id="bzRadPanel"></div>';
    if (oldLive && oldLive.children.length) { const nl = $("bzRadLive"); nl.replaceWith(oldLive); }
    renderRadPanel(M);
    renderRadBar();
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
      el.innerHTML = '<span class="bz-rad-st on"><i></i>正在扫描</span><span class="bz-rad-pg"><b>' + r.done + " / " + r.total + "</b> 个信息源 · 这一轮新发现 <b>" + r.new + "</b> 条</span>" +
        '<span class="bz-prog sm" aria-hidden="true"><i style="width:' + pct + '%"></i></span><span class="sp"></span>' + sel +
        '<button type="button" class="bz-link" data-act="rd-stop">停止</button>';
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
    if (S.pane !== "radar" || S.rview !== "radar" || !$("bzRadLive")) return;
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
    if (LIVE.active < 4 && $("bzRadLive")) showLive(LIVE.queue.shift());
    LIVE.timer = setTimeout(pumpLive, 900);
  }
  function showLive(it) {
    const box = $("bzRadLive"), vb = S.radVB;
    if (!box || !vb) return;
    const tgt = (it.ind && it.ind[0] ? it.ind[0].split("/")[0] : "") || (it.trk && it.trk[0]) || "";
    const ps = S.radPos[tgt] || { x: vb.C, y: vb.C, color: "var(--accent)" };
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

  function renderRadPanel(M) {
    const el = $("bzRadPanel");
    if (!el) return;
    M = M || radarModel();
    if (!M) return;
    const win = S.mdays <= 1 ? "最近 24 小时" : "最近 " + S.mdays + " 天";
    const all = [];
    M.groups.forEach((g) => g.items.forEach((it) => { if (it.n) all.push(Object.assign({ color: g.color }, it)); }));
    all.sort((a, b) => b.n - a.n);
    const sel = S.radSel && all.find((x) => x.id === S.radSel);
    if (!sel) {
      const quiet = M.groups.reduce((a, g) => a + g.items.filter((x) => !x.n).length, 0);
      el.innerHTML = '<h4 class="bz-rad-h">扫描结果<small>' + win + "，" + all.length + " 个行业和赛道有新闻" + (quiet ? "，" + quiet + " 个没动静" : "") + "</small></h4>" +
        '<p class="bz-hint">点雷达上的圆点，或者下面的名字，看那个行业的新闻。</p>' +
        '<ol class="bz-rad-rank">' + all.slice(0, 16).map((x) =>
          '<li><button type="button" data-rad="' + esc(x.id) + '"><i style="background:' + x.color + '"></i><span class="nm">' + esc(x.name) + "</span>" +
          '<span class="sc">' + esc(x.sec.replace("赛道·", "")) + "</span>" + '<span class="hotc">' + (x.hot ? '<span class="hot">升温</span>' : "") + "</span>" +
          '<span class="bar"><b style="width:' + Math.max(4, Math.round((x.n / M.max) * 100)) + "%;background:" + x.color + '"></b></span><span class="n">' + x.n + "</span></button></li>").join("") + "</ol>" +
        (all.length > 16 ? '<p class="bz-hint">还有 ' + (all.length - 16) + " 个，在雷达上点。</p>" : "");
      return;
    }
    const subs = (S.byId[sel.id] && S.byId[sel.id].subs) || [];
    const heat = S.ovm.heat || {};
    const subHtml = subs.map((x) => [x, (heat[x] || [0])[0]]).filter((x) => x[1]).sort((a, b) => b[1] - a[1]).map(([x, n]) =>
      '<button type="button" class="bz-chip" data-rad-list="' + esc(x) + '">' + esc(nameOf(x)) + " <b>" + n + "</b></button>").join("");
    const tops = S.radTops && S.radTops.days === S.mdays ? S.radTops.tops : null;
    const news = tops ? (tops[sel.id] || []) : S.radNews[sel.id + "|" + S.mdays];
    el.innerHTML = '<div class="bz-rad-sel"><button type="button" class="bz-link" data-act="rad-clear">‹ 全部行业</button>' +
      '<h4 class="bz-rad-h"><i style="background:' + sel.color + '"></i>' + esc(sel.name) + "<small>" + esc(sel.sec) + "</small></h4>" +
      '<p class="bz-rad-num"><b>' + sel.n + "</b> 条新闻（" + win + "）" + (S.mdays > 1 ? "，最近 24 小时 " + sel.t + " 条" : "") + (sel.hot ? ' <span class="hot">正在升温</span>' : "") + "</p>" +
      (subHtml ? '<p class="bz-hint">细分到：</p><div class="bz-chips">' + subHtml + "</div>" : "") +
      '<h5 class="bz-rad-sub">最新的几条</h5><div class="bz-feed compact">' + (news ? (news.length ? news.map(itemRow).join("") : empty("没读到。")) : loading()) + "</div>" +
      '<button type="button" class="bz-btn" data-rad-list="' + esc(sel.id) + '">看「' + esc(sel.name) + "」全部 " + sel.n + " 条新闻</button></div>";
    if (!news && !tops) loadRadNews(sel.id);
  }
  async function loadRadTops() {                // v168：每个行业最新几条一次读好，点圆点马上就有
    const d = S.mdays;
    let r;
    try { r = await api("/biz/radar_tops?days=" + d); } catch (e) { return; }
    if (!r || !r.tops || d !== S.mdays) return;
    S.radTops = { days: d, tops: r.tops };
    if (S.radSel) renderRadPanel();
  }
  function radTip(id, show) {                  // v168：鼠标移到圆点上马上出提示（不用等系统的慢提示）
    const tip = $("bzRadTip"), vb = S.radVB, ps = S.radPos && S.radPos[id];
    if (!tip) return;
    if (!show || !ps || !vb) { tip.hidden = true; return; }
    const M = radarModel();
    let it = null;
    if (M) M.groups.forEach((g) => g.items.forEach((x) => { if (x.id === id) it = x; }));
    if (!it) { tip.hidden = true; return; }
    const tops = S.radTops && S.radTops.days === S.mdays ? (S.radTops.tops[id] || []) : [];
    tip.innerHTML = '<b style="color:' + it.color + '">' + esc(it.name) + "</b><small>" + esc(it.sec) + "</small>" +
      "<p>" + (it.n ? it.n + " 条新闻" + (S.mdays > 1 ? "，最近 24 小时 " + it.t + " 条" : "") + (it.hot ? ' <span class="hot">升温</span>' : "") : "这段时间没有新闻") + "</p>" +
      (tops[0] ? '<p class="t">最新：' + esc(S.trTitle[tops[0].title] || tops[0].title) + "</p>" : "") + (it.n ? '<p class="h">点一下看详情</p>' : "");
    const lx = ((ps.x - vb.x) / vb.w) * 100, ly = ((ps.y - vb.y) / vb.h) * 100;
    tip.style.left = lx + "%"; tip.style.top = ly + "%";
    tip.classList.toggle("left", lx > 55);
    tip.classList.toggle("up", ly > 60);
    tip.hidden = false;
  }
  async function loadRadNews(id) {
    const key = id + "|" + S.mdays;
    let r;
    try { r = await api("/biz/items?lens=market&days=" + S.mdays + (id.startsWith("t:") ? "&trk=" : "&ind=") + enc(id) + "&limit=6"); } catch (e) { r = null; }
    S.radNews[key] = (r && r.items) || [];
    if (S.radSel === id) renderRadPanel();
  }
  function selectRad(id) {
    S.radSel = S.radSel === id ? "" : id;
    root.querySelectorAll("#bzRadar .blip").forEach((g) => g.classList.toggle("sel", g.dataset.rad === S.radSel));
    renderRadPanel();
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
        '<p class="bz-art-miss">没读出正文' + (a.error ? "：" + esc(a.error) : "") + "。想看全文，可以点下面的原文链接。</p>";
    }
    return h;
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
        '<div class="bz-rp-m">' + readMetaHTML(it) + "</div>" +
        '<div class="bz-art-body">' + readBodyHTML(it) + "</div>" +
        '<div class="bz-art-f"><div class="bz-art-src">原文链接：<a href="' + esc(it.url) + '" target="_blank" rel="noopener">' + esc(it.url) + "</a></div></div>" +
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
    if (a.foreign && !S.artTr[url]) await loadTr(it);
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
      (ti.orig ? '<p class="bz-rp-orig">' + esc(ti.orig) + "</p>" : "") + '<div class="bz-art-body">' + readBodyHTML(it) + "</div>" +
      '<div class="bz-art-f"><div class="bz-art-src">原文链接：<a href="' + esc(it.url) + '" target="_blank" rel="noopener">' + esc(it.url) + "</a></div></div>", "");
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
      return '<span class="bz-prog sm" aria-hidden="true"><i style="width:' + pct + '%"></i></span><span>正在更新：' + r.done + " / " + r.total +
        " 个信息源，这一轮新抓到 " + r.new + " 条</span>" + '<button type="button" class="bz-link" data-act="upd-open">看进度</button>';
    }
    const txt = r.last_run ? "爬虫盯着 " + r.enabled + " 个信息源，" + ago(r.last_run) + "更新过；最近 24 小时抓到 " + r.items_24h + " 条。" + autoText(r) + "。"
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
    const d = S.mdays, win = d <= 1 ? "最近 6 小时" : "最近 24 小时";
    $("bzRisingHint").textContent = "按爬虫抓到的新闻算：" + win + "提到它的比例，明显高于这 " + (d <= 1 ? "24 小时" : d + " 天") + "的平均。点一下只看相关新闻。";
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
      (m ? "\n最近 " + (S.mdays <= 1 ? "24 小时" : S.mdays + " 天") + "的市场新闻：" + (h[0] || 0) + " 条（今天 " + (h[1] || 0) + " 条）" +
        (S.ov ? "\n你收进来的相关内容：" + (mine[0] || 0) + " 条" : "")
        : "\n你收进来的相关内容：" + (h[0] || 0) + " 条");
    return '<button type="button" class="bz-tile h' + lvl(h[0]) + (S.indSel === id ? " sel" : "") + (matchQ(d) ? "" : " dim") +
      '" data-ind="' + esc(id) + '" title="' + esc(tip) + '"><span class="nm">' + esc(d.name) + "</span>" +
      (h[0] ? '<span class="ct">' + h[0] + (m && S.mdays > 1 && h[1] ? '<small> 今天 +' + h[1] + "</small>" : "") + "</span>" : "") +
      (gap ? '<i class="gap" aria-hidden="true"></i>' : "") + "</button>";
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
    lensVis();
    $("bzLegendTxt").textContent = S.lens === "market"
      ? "颜色越深，最近 " + (S.mdays <= 1 ? "24 小时" : S.mdays + " 天") + "市场上的相关新闻越多；带小圆点的是你还没关注的"
      : "颜色越深，你收进来的相关内容越多";
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
    const items = S.indItems && S.indItems._id === d.id + "|" + S.lens ? S.indItems : null;
    const m = S.lens === "market", mine = heatIn(S.ov, d.id), mkt = heatIn(S.ovm, d.id);
    const win = S.mdays <= 1 ? "24 小时" : S.mdays + " 天";
    const stat = m
      ? '<p class="bz-dt-stat"><b>' + (h[0] || 0) + "</b> 条市场新闻（最近 " + win + "）" + (h[1] ? "，今天 " + h[1] + " 条" : "") + "</p>" +
        '<p class="bz-dim">' + (S.ov ? (mine[0] ? "你收进来的相关内容 " + mine[0] + " 条" : "你收进来的内容里还没有它" + (h[0] >= 3 ? "，市场上却有动静：可能是个盲区" : "")) : "") + "</p>"
      : '<p class="bz-dt-stat"><b>' + (h[0] || 0) + "</b> 条相关内容" + (S.days && h[1] ? "，最近 " + S.days + " 天 " + h[1] + " 条" : "") + "</p>" +
        (S.ovm ? '<p class="bz-dim">市场上最近 ' + win + "的相关新闻 " + (mkt[0] || 0) + " 条</p>" : "");
    const reps = S.reports.filter((r) => r.target === d.id || r.scope === d.id).slice(0, 5);
    el.innerHTML = '<div class="bz-dt">' +
      '<p class="bz-dt-path">' + esc(path) + "</p><h3>" + esc(d.name) + "</h3><p>" + esc(d.desc) + "</p>" +
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
      "<h4>" + (m ? "市场新闻" : "相关内容") + (items ? "（" + items.total + "）" : "") + '</h4><div class="bz-feed compact">' +
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
      '<div class="bz-rd-url">' + esc(tgt) + "</div>" + st + "</div>" +
      '<div class="bz-rd-acts"><button type="button" class="bz-link" data-rd-items="' + esc(s.id) + '">看抓到的</button>' +
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
      d.groups.forEach((g) => {
        const rows = d.sources.filter((x) => (x.group || "mine") === g.key);
        if (rows.length) html += '<div class="bz-rd-grp"><h4>' + esc(g.name) + "</h4>" + rows.map(rdRow).join("") + "</div>";
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
    else if (p === "analysis") renderAnalysis();
    else if (p === "opps") renderOpps();
    else if (p === "crawler") renderCrawler();
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
        '<button type="button" class="bz-btn ghost sm" data-openfolder="' + esc(j.report) + '">打开所在文件夹</button>' +
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
      renderBigBtns();
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
      t.textContent = "现在更新";
      sub.textContent = r && r.last_run ? "上次 " + ago(r.last_run) + (r.auto ? " · 每 " + (r.every >= 60 ? (r.every / 60).toFixed(1).replace(/\.0$/, "") + " 小时" : r.every + " 分钟") + "自动更新" : " · 自动更新已关")
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
    const nScope = failOnly ? nFail : selGroups.reduce((a, g) => a + g.n, 0);
    const last = p.last;
    const lastDur = last && last.ended ? last.ended - last.started : 0;
    const est = lastDur && last.total ? Math.max(20, Math.round((lastDur / last.total) * nScope)) : 0;
    const gdesc = {};
    (p.group_names || []).forEach(([k, n, d]) => { gdesc[k] = d; });
    const cats = p.groups.map((g) => {
      const on = gsel.has(g.key);
      const what = [g.site ? g.site + " 个网站" : "", g.kw ? g.kw + " 个关键词" : ""].filter(Boolean).join(" + ");
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
      '<section class="bz-sec"><h3>这次抓哪些</h3>' +
        '<div class="bz-upd-sum"><span>' + (failOnly ? "只重抓上次没抓成的 <b>" + nFail + " 个</b>"
          : "<b>" + (allOn ? "全部 " : "") + selGroups.length + " 类</b>，共 <b>" + nScope + " 个</b>信息源") + "</span>" +
          (failOnly ? "" : '<span class="sp"></span><button type="button" class="bz-link" data-act="upd-all"' + (allOn ? " disabled" : "") + '>全选</button><button type="button" class="bz-link" data-act="upd-none">全不选</button>') + "</div>" +
        '<div class="bz-cats" role="group" aria-label="要抓的分类">' + cats + "</div>" +
        (nFail ? '<div class="bz-failrow"><label class="bz-sw-inline"><span class="bz-sw"><input type="checkbox" id="bzUpdFailOnly"' + (failOnly ? " checked" : "") + '><i></i></span>只重抓上次没抓成的 ' + nFail + " 个</label>" +
          '<details class="bz-fails"><summary>看原因</summary><ul>' + p.failing.map((f) => "<li><b>" + esc(f.name) + "</b>：" + esc(f.err) + "</li>").join("") + "</ul></details></div>" : "") +
      "</section>" +
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
        '<button type="button" class="bz-btn lg" data-act="upd-start" data-autofocus' + (nScope ? "" : " disabled") + ">开始更新（" + nScope + " 个信息源）</button></div>";
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
    if (scope === "groups" && !groups.length) { toast("至少勾上一类。"); return; }
    await updSave();
    S.updDone = ""; S.updRes = null;
    await radarRun(null, { scope: scope, groups: groups });
    renderUpd();
  }

  // ───────── v158：「整理成简报」面板 ─────────
  const BF_SIZE = { short: ["简短", "800 字以内，最重要的几条", 40], normal: ["标准", "1500～2500 字", 60], detail: ["详细", "3000～5000 字，每条讲清来龙去脉", 90] };
  async function openBrief() {
    const prev = store.get("bf", {});
    S.bf = { days: S.mdays, grp: S.rgrp, q: S.rq, size: prev.size || "normal", notes: prev.notes !== false, web: !!prev.web, focus: "", count: null };
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
    const grpOpts = [["all", "全部来源"], ["news", "财经媒体"], ["corp,corpkw", "大公司"], ["media,indkw", "行业媒体"], ["policy", "政策数据"], ["global", "海外"], ["mine", "我加的"]];
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
    let body = reportBody(r.content, r.chain);
    if (m.note_ids && m.note_ids.length) {
      body += '<section class="bz-used"><h4>用到的笔记</h4><div class="bz-chips">' + m.note_ids.map((n) =>
        '<button type="button" class="bz-chip" data-note="' + esc(n) + '">' + esc(n.replace(/^\d{8}-\d{6}-/, "").replace(/\.md$/, "").slice(0, 24)) + "</button>").join("") + "</div></section>";
    }
    openReader(m.title, meta, body,
      '<button type="button" class="bz-btn ghost sm" data-openfolder="' + esc(m.id) + '">打开所在文件夹</button>' +
      '<button type="button" class="bz-btn ghost sm" data-kbrep="' + esc(m.id) + '" title="让 AI 把这份报告整理进知识库的主题页">收进知识库</button>' +
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
  async function refreshOverview(which) {
    which = which || "market";
    const m = which === "market";
    try {
      const o = await api("/biz/overview?lens=" + which + "&days=" + (m ? S.mdays : S.days));
      if (o && o.ok === false) throw new Error(o.error || "出错");
      if (m) { S.ovm = o; S.ovmErr = ""; if (o.radar && o.radar.ok !== false) S.radar = o.radar; loadRadTops(); }
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
    S.radar = Object.assign({}, S.radar || {}, { running: true, rid: r.rid, done: 0, total: r.total, new: 0, current: [] });   // 抓得很快时也能认出「抓完了」
    if (id) toast("开始抓这一个了，过程在「爬虫管理」的运行日志里。");
    else if (!S.updOpen) toast("开始抓了：" + r.total + " 个信息源，一般一两分钟抓完。");
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
    if (p === "crawler") { loadEngines(); loadRuns(); if (!S.radarSrc) loadRadarSources(); }
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
    else if (name === "oppst") { S.oppSt = v; renderOpps(); }
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
      runJob("market", { scope: $("bzTaskScope").value, days: S.mdays, web: web, lens: "market" });
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
      if ((b = t.closest("[data-act]"))) {
        const act = b.dataset.act;
        if (act === "back") closeReader();
        else if (act === "guide-hide") { store.set("guideHidden", true); $("bzGuide").hidden = true; }
        else if (act === "clearq") { S.rq = ""; $("bzRq").value = ""; loadRadarFeed(); }
        else if (act === "clearsince") { S.rsince = 0; loadRadarFeed(); }
        else if (act === "rd-run") radarRun();
        else if (act === "upd-open") openUpd();
        else if (act === "rad-back") setRview("radar");
        else if (act === "clearind") { S.rind = ""; loadRadarFeed(); }
        else if (act === "rad-clear") selectRad(S.radSel);
        else if (act === "art-close") closeArt();
        else if (act === "art-lang") { S.artLang = b.dataset.v === "orig" ? "orig" : "zh"; const it = curArt(); if (it) refreshArt(it); }
        else if (act === "art-retr") { const it = curArt(); if (it) loadTr(it); }
        else if (act === "art-kb") {                      // v162：把这条新闻收进知识库
          const it = curArt();
          if (!it) return;
          const a = S.art[it.url] || {}, tr = S.artTr[it.url], useTr = a.foreign && tr && tr.ok;
          const paras = (useTr ? tr.paras : a.paras) || [];
          const text = paras.length ? paras.join("\n\n") : (a.desc || a.summary || it.text || "");
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
          runJob(m.kind, { target: m.target, scope: m.scope, days: m.days || 30, web: m.web_on !== false, depth: m.depth || "quick", lens: m.lens || "mine" });
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
      if ((b = t.closest("tr[data-run]"))) { openRunReport(b.dataset.run); return; }
      if ((b = t.closest("[data-note]"))) { openNote(b.dataset.note); return; }
      if ((b = t.closest("[data-goto-task]"))) { S.task = b.dataset.gotoTask; store.set("task", S.task); goPane("analysis"); return; }
      if ((b = t.closest("[data-goto]"))) { goPane(b.dataset.goto); return; }
      if ((b = t.closest("[data-task]"))) { S.task = b.dataset.task; store.set("task", S.task); renderAnalysis(); const i = $("bzTaskTarget"); if (i) i.focus(); return; }
      if ((b = t.closest("[data-term]"))) {
        S.rq = b.dataset.term; $("bzRq").value = S.rq; S.rlimit = 80; loadRadarFeed();
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
    root.addEventListener("change", async (e) => {
      const t = e.target;
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
      else if (t.id === "bzBfGrp") { S.bf.grp = t.value; briefCount(); }
      else if (t.id === "bzBfNotes") S.bf.notes = t.checked;
      else if (t.id === "bzBfWeb") S.bf.web = t.checked;
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
      else if (t.id === "bzRq") { clearTimeout(qTimer); qTimer = setTimeout(() => { S.rq = t.value.trim(); loadRadarFeed(); }, 350); }
      else if (t.id === "bzBfQ") { S.bf.q = t.value.trim(); clearTimeout(qTimer); qTimer = setTimeout(briefCount, 350); }
      else if (t.id === "bzBfFocus") S.bf.focus = t.value;
      else if (t.id === "bzRepQ") { S.repQ = t.value; renderAnalysis(); }
    });
    root.addEventListener("mouseover", (e) => {
      const g = e.target.closest && e.target.closest("#bzRadar g.blip[data-rad]");
      if (g) radTip(g.dataset.rad, true);
    });
    root.addEventListener("mouseout", (e) => {
      const g = e.target.closest && e.target.closest("#bzRadar g.blip[data-rad]");
      if (g && !(e.relatedTarget && g.contains(e.relatedTarget))) radTip("", false);
    });
    root.addEventListener("focusin", (e) => { if (e.target.matches && e.target.matches("#bzRadar g.blip[data-rad]")) radTip(e.target.dataset.rad, true); });
    root.addEventListener("focusout", (e) => { if (e.target.matches && e.target.matches("#bzRadar g.blip[data-rad]")) radTip("", false); });
    root.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.isComposing) {
        if (e.target.id === "bzTaskTarget") { e.preventDefault(); startTask(); }
        else if (e.target.id === "bzAddOne") { e.preventDefault(); const b = root.querySelector('[data-act="add-one"]'); if (b) b.click(); }
        else if (e.target.matches && e.target.matches("tr[data-run]")) { e.preventDefault(); openRunReport(e.target.dataset.run); }
      }
      if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches("#bzRadar g.blip[data-rad]")) { e.preventDefault(); selectRad(e.target.dataset.rad); }
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
