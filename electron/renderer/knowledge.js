/* knowledge.js — 🌌 知识云图
 *
 * 把 memory/conversations 里的每段对话渲染成一颗发光的星，相近主题用关键词聚成星团，
 * 点一颗星 = 回到那段对话。纯 Canvas 2D，离线、零依赖。
 *
 * 流程：
 *   1. 拉 /conversations/list（带正文）
 *   2. 本地中文关键词提取（停用词过滤 + 词频 + 二元组），每段对话取若干关键词
 *   3. 按「最强共享关键词」把对话分到星团；星团心 = 关键词
 *   4. 力导向布局：星团之间相斥、团内成员被团心吸住、星之间轻微相斥
 *   5. 渲染：星大小∝长度、亮度∝近期、金色=加星；悬停高亮同团连线 + tooltip；点击回到对话
 *
 * 对外暴露：window.loadKnowledge()（切到该视图时由 renderer.js 调）
 */

(function () {
  "use strict";

  var BACKEND_FALLBACK = "http://127.0.0.1:8756";
  function backend() {
    return (typeof BACKEND !== "undefined" && BACKEND) ? BACKEND : BACKEND_FALLBACK;
  }

  // ── 中文/英文停用词（聚类时忽略，否则全连一起）──
  var STOP = new Set((
    "的 了 和 是 我 你 他 她 它 们 在 也 都 就 不 有 这 那 与 及 或 而 但 把 被 让 给 对 从 向 " +
    "一个 一下 一些 怎么 什么 如何 可以 这个 那个 知道 觉得 没有 还是 已经 现在 然后 因为 所以 " +
    "需要 想要 帮我 帮忙 一下 一种 进行 通过 我们 你们 他们 自己 这样 那样 还有 就是 这种 那种 " +
    "请 谢谢 好的 嗯 哦 啊 吗 呢 吧 哈 嘛 呀 哇 个 把 之 其 此 该 等 很 太 更 最 " +
    "the a an and or but to of in on at for is are was were be been it this that you i we he she they " +
    "with as by from will can could would should do does did not no yes ok so then how what why " +
    "超能小助 助手 用户 对话 帮 看 想 做 用 说 问 答 点 个 条 次 现 在"
  ).split(/\s+/).filter(Boolean));

  var els = {};
  var state = {
    nodes: [],         // {id,title,when,when_human,turns,chars,starred,kw:[],cluster,x,y,vx,vy,r,recency,scope,open,ref,url}
    clusters: [],      // {key, label, x, y, color, members:[idx]}
    view: { ox: 0, oy: 0, scale: 1 },
    hover: -1,
    raf: 0,
    running: false,
    width: 0, height: 0, dpr: 1,
    loaded: false,
    filter: "",
    scope: "all",      // all | chat | sniff | video
    colorBySource: true, // 「全部」时按来源上色；单一范围时按主题星团上色
  };

  // 各来源的代表色（「全部」模式下用它给星上色，一眼看出来自哪个板块）
  var SOURCE_COLOR = {
    chat: "#7B68EE",     // 对话 紫
    video: "#ff8a4c",    // 视频 橘
    sniff: "#4cc9f0",    // 嗅探 青
    insight: "#52b788",  // 洞察 绿
  };
  var SOURCE_LABEL = { chat: "对话", video: "视频", sniff: "嗅探", insight: "洞察" };

  // 星团配色（柔和的星云色）
  var PALETTE = [
    "#7B68EE", "#4cc9f0", "#ff8a4c", "#f72585", "#52b788",
    "#ffd166", "#b5179e", "#4895ef", "#80ed99", "#f4a261",
    "#9b5de5", "#00bbf9", "#fb5607", "#06d6a0", "#e07a5f",
  ];

  // ───────────────────────── 关键词提取 ─────────────────────────
  // 返回该对话的「候选词 + 词频」表（不止 top5），聚类时靠全局共享词来连，
  // 单纯滑窗 bigram 跨文档对不齐，所以这里返回较多候选，由 buildClusters 选全局共享最强的。
  function extractKeywordTable(text) {
    var freq = {};
    var zhRuns = text.match(/[\u4e00-\u9fff]{2,}/g) || [];
    var enWords = (text.toLowerCase().match(/[a-z][a-z0-9+#.]{2,}/g) || []);
    zhRuns.forEach(function (run) {
      // 2 字和 3 字滑窗都收（3 字权重高），停用词丢弃
      for (var n = 2; n <= 3; n++) {
        for (var i = 0; i + n <= run.length; i++) {
          var w = run.slice(i, i + n);
          if (STOP.has(w)) continue;
          // 含高频停用字的二元组降权（如「的X」「了X」）——开头/结尾是停用字就跳
          if (n === 2 && (STOP.has(w[0]) || STOP.has(w[1]))) continue;
          freq[w] = (freq[w] || 0) + (n === 3 ? 1.5 : 1);
        }
      }
    });
    enWords.forEach(function (w) {
      if (STOP.has(w) || w.length < 3) return;
      freq[w] = (freq[w] || 0) + 1.3;
    });
    return freq;
  }

  // 给展示用：从候选表取干净的 top 关键词（含包含去重）
  function topKeywords(freq, max) {
    var arr = Object.keys(freq).map(function (k) { return [k, freq[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    var picked = [];
    for (var j = 0; j < arr.length && picked.length < (max || 5); j++) {
      var word = arr[j][0];
      var redundant = picked.some(function (p) { return (p.indexOf(word) >= 0 || word.indexOf(p) >= 0); });
      if (!redundant) picked.push(word);
    }
    return picked;
  }

  // ───────────────────────── 聚类（按全局共享关键词）─────────────────────────
  // 思路：先统计每个候选词出现在多少段对话里（文档频率 DF）。给每段对话挑一个
  // 「聚类词」——它的候选词里 DF≥2 且 (DF × 本地权重 × 词长加权) 最高的那个。
  // 这样跨文档能对齐的共享词才会把对话连成团；纯独有的滑窗碎片不会乱连。
  function buildClusters(nodes) {
    // 1) 文档频率：每个候选词出现在几段对话
    var df = {};
    nodes.forEach(function (n) {
      var seen = {};
      Object.keys(n.freq).forEach(function (w) {
        if (!seen[w]) { df[w] = (df[w] || 0) + 1; seen[w] = 1; }
      });
    });

    var clusterMap = {};
    var clusters = [];
    function clusterFor(key) {
      if (clusterMap[key] == null) {
        clusterMap[key] = clusters.length;
        clusters.push({ key: key, label: key, members: [],
                        color: PALETTE[clusters.length % PALETTE.length] });
      }
      return clusterMap[key];
    }

    nodes.forEach(function (n, idx) {
      var best = null, bestScore = 0;
      Object.keys(n.freq).forEach(function (w) {
        var d = df[w] || 0;
        if (d < 2) return;                       // 没人共享 → 不能当聚类词
        // 太普遍的词（几乎每段都有）反而没区分度，做个轻微惩罚
        var ubiquity = d / nodes.length;
        var lenW = (w.length >= 3 || /[a-z]/.test(w)) ? 1.3 : 1;  // 长词/英文更可信
        var score = d * (n.freq[w]) * lenW * (1 - 0.4 * ubiquity);
        if (score > bestScore) { bestScore = score; best = w; }
      });
      var key = best || "零散";
      var ci = clusterFor(key);
      n.cluster = ci;
      clusters[ci].members.push(idx);
    });

    // 单成员的非「零散」团并入「零散」，画面更干净
    var loose = clusterFor("零散");
    clusters.forEach(function (c, ci) {
      if (ci !== loose && c.members.length === 1) {
        var m = c.members[0];
        nodes[m].cluster = loose;
        clusters[loose].members.push(m);
        c.members = [];
      }
    });

    // 去空团 + 重排索引
    var compact = [];
    clusters.forEach(function (c) {
      if (c.members.length) {
        var ni = compact.length;
        c.members.forEach(function (m) { nodes[m].cluster = ni; });
        compact.push(c);
      }
    });
    return compact;
  }

  // ───────────────────────── 初始布局 ─────────────────────────
  function layout(nodes, clusters, W, H) {
    var cx = W / 2, cy = H / 2;
    var R = Math.min(W, H) * 0.34;
    var nC = Math.max(1, clusters.length);
    clusters.forEach(function (c, i) {
      // 星团心沿一个大圈分布（团多就铺开）
      var ang = (i / nC) * Math.PI * 2 - Math.PI / 2;
      var rr = (nC === 1) ? 0 : R * (0.55 + 0.45 * ((i % 3) / 2));
      c.x = cx + Math.cos(ang) * rr;
      c.y = cy + Math.sin(ang) * rr * 0.82;
    });
    nodes.forEach(function (n) {
      var c = clusters[n.cluster] || { x: cx, y: cy };
      var a = Math.random() * Math.PI * 2;
      var d = 18 + Math.random() * 60;
      n.x = c.x + Math.cos(a) * d;
      n.y = c.y + Math.sin(a) * d;
      n.vx = 0; n.vy = 0;
    });
  }

  // ───────────────────────── 力导向（跑若干帧后稳定）─────────────────────────
  var simTicks = 0;
  function simStep(nodes, clusters, W, H) {
    var cx = W / 2, cy = H / 2;
    // 团心之间互斥，避免重叠
    for (var i = 0; i < clusters.length; i++) {
      for (var j = i + 1; j < clusters.length; j++) {
        var a = clusters[i], b = clusters[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var dist = Math.sqrt(dx * dx + dy * dy) || 1;
        var minD = 180;
        if (dist < minD) {
          var push = (minD - dist) / dist * 0.5;
          a.x += dx * push; a.y += dy * push;
          b.x -= dx * push; b.y -= dy * push;
        }
      }
      // 团心被轻轻拉回画面中心，别飘出去
      clusters[i].x += (cx - clusters[i].x) * 0.004;
      clusters[i].y += (cy - clusters[i].y) * 0.004;
    }
    // 节点：被自己团心吸引 + 同屏节点间轻微相斥
    for (var k = 0; k < nodes.length; k++) {
      var n = nodes[k];
      var c = clusters[n.cluster] || { x: cx, y: cy };
      n.vx += (c.x - n.x) * 0.02;
      n.vy += (c.y - n.y) * 0.02;
    }
    // 节点互斥（O(n^2)，对话量不大没问题；上限保护）
    var cap = Math.min(nodes.length, 400);
    for (var p = 0; p < cap; p++) {
      for (var q = p + 1; q < cap; q++) {
        var A = nodes[p], B = nodes[q];
        var ddx = A.x - B.x, ddy = A.y - B.y;
        var dd = ddx * ddx + ddy * ddy;
        var min2 = 28 * 28;
        if (dd < min2 && dd > 0.01) {
          var dlen = Math.sqrt(dd);
          var f = (28 - dlen) / dlen * 0.5;
          A.vx += ddx * f; A.vy += ddy * f;
          B.vx -= ddx * f; B.vy -= ddy * f;
        }
      }
    }
    for (var m = 0; m < nodes.length; m++) {
      var nn = nodes[m];
      nn.vx *= 0.82; nn.vy *= 0.82;     // 阻尼
      nn.x += nn.vx; nn.y += nn.vy;
    }
    simTicks++;
  }

  // ───────────────────────── 坐标变换 ─────────────────────────
  function toScreen(x, y) {
    return { x: x * state.view.scale + state.view.ox, y: y * state.view.scale + state.view.oy };
  }
  function toWorld(sx, sy) {
    return { x: (sx - state.view.ox) / state.view.scale, y: (sy - state.view.oy) / state.view.scale };
  }

  // ───────────────────────── 渲染 ─────────────────────────
  function draw() {
    var ctx = els.ctx, W = state.width, H = state.height;
    ctx.clearRect(0, 0, W, H);

    // 背景星尘（固定点缀，营造星空）
    drawDust(ctx, W, H);

    var nodes = state.nodes, clusters = state.clusters;
    var hov = state.hover;
    var hoverNode = (hov >= 0) ? nodes[hov] : null;
    var filt = state.filter;

    // 1) 团内连线（hover 时只亮 hover 所在团；否则淡淡画每团一条主干）
    ctx.lineWidth = 1;
    if (hoverNode) {
      var ci = hoverNode.cluster;
      var cl = clusters[ci];
      if (cl) {
        var hs = toScreen(hoverNode.x, hoverNode.y);
        cl.members.forEach(function (mi) {
          if (mi === hov) return;
          var o = nodes[mi];
          var os = toScreen(o.x, o.y);
          ctx.strokeStyle = hexA(cl.color, 0.5);
          ctx.beginPath(); ctx.moveTo(hs.x, hs.y); ctx.lineTo(os.x, os.y); ctx.stroke();
        });
      }
    } else {
      // 静息态：每个团画成一张「蛛网」——成员连到团心，弱弱的
      clusters.forEach(function (cl) {
        var cs = toScreen(cl.x, cl.y);
        ctx.strokeStyle = hexA(cl.color, 0.12);
        cl.members.forEach(function (mi) {
          var o = nodes[mi];
          var os = toScreen(o.x, o.y);
          ctx.beginPath(); ctx.moveTo(cs.x, cs.y); ctx.lineTo(os.x, os.y); ctx.stroke();
        });
      });
    }

    // 2) 团标签（关键词）浮在团心
    clusters.forEach(function (cl) {
      if (cl.key === "零散") return;
      var cs = toScreen(cl.x, cl.y);
      ctx.font = (13 * Math.min(1.4, state.view.scale)).toFixed(0) + "px 'Microsoft YaHei', sans-serif";
      ctx.textAlign = "center";
      ctx.fillStyle = hexA(cl.color, 0.85);
      ctx.shadowColor = hexA(cl.color, 0.6); ctx.shadowBlur = 12;
      ctx.fillText(cl.label, cs.x, cs.y - 4);
      ctx.shadowBlur = 0;
    });

    // 3) 星
    nodes.forEach(function (n, idx) {
      var s = toScreen(n.x, n.y);
      var dim = filt && !nodeMatches(n, filt);
      var cl = clusters[n.cluster];
      // 「全部」模式：按来源板块上色（一眼看出来自对话/视频/嗅探/洞察）
      // 单一范围：按主题星团上色；加星的恒为金色
      var base;
      if (n.starred) base = "#ffd166";
      else if (state.scope === "all") base = SOURCE_COLOR[n.scope] || "#9aa0cc";
      else base = (cl ? cl.color : "#9aa0cc");
      var r = n.r * state.view.scale;
      var glow = 0.35 + 0.65 * n.recency;
      var alpha = dim ? 0.1 : 1;

      var halo = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r * 3.2);
      halo.addColorStop(0, hexA(base, 0.55 * glow * alpha));
      halo.addColorStop(1, hexA(base, 0));
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(s.x, s.y, r * 3.2, 0, Math.PI * 2); ctx.fill();

      ctx.fillStyle = hexA(base, alpha);
      ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, Math.PI * 2); ctx.fill();

      if (idx === state.hover) {
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(s.x, s.y, r + 3, 0, Math.PI * 2); ctx.stroke();
      } else if (n.starred && !dim) {
        ctx.strokeStyle = hexA("#fff3c4", 0.8); ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(s.x, s.y, r + 1.5, 0, Math.PI * 2); ctx.stroke();
      }
    });
  }

  var _dust = null;
  function drawDust(ctx, W, H) {
    if (!_dust || _dust.w !== W || _dust.h !== H) {
      _dust = { w: W, h: H, pts: [] };
      var n = Math.round((W * H) / 9000);
      for (var i = 0; i < n; i++) {
        _dust.pts.push({ x: Math.random() * W, y: Math.random() * H,
                         r: Math.random() * 1.1 + 0.2, a: Math.random() * 0.5 + 0.1 });
      }
    }
    _dust.pts.forEach(function (p) {
      ctx.fillStyle = "rgba(200,210,255," + p.a.toFixed(2) + ")";
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
    });
  }

  // ───────────────────────── 工具 ─────────────────────────
  function hexA(hex, a) {
    // 支持 #rgb / #rrggbb
    var h = hex.replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return "rgba(" + r + "," + g + "," + b + "," + a + ")";
  }
  function nodeMatches(n, q) {
    q = q.toLowerCase();
    if ((n.title || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((n.preview || "").toLowerCase().indexOf(q) >= 0) return true;
    return n.kw.some(function (k) { return k.toLowerCase().indexOf(q) >= 0; });
  }
  function nodeMatchesAny(n) { return !state.filter || nodeMatches(n, state.filter); }

  function pickNode(sx, sy) {
    // 命中测试：从上往下（后画的在上），取最近的
    var best = -1, bestD = 1e9;
    for (var i = state.nodes.length - 1; i >= 0; i--) {
      var n = state.nodes[i];
      if (state.filter && !nodeMatches(n, state.filter)) continue;
      var s = toScreen(n.x, n.y);
      var dx = sx - s.x, dy = sy - s.y;
      var d = dx * dx + dy * dy;
      var hitR = (n.r * state.view.scale + 6);
      if (d <= hitR * hitR && d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  // ───────────────────────── 主循环 ─────────────────────────
  function loop() {
    if (!state.running) return;
    if (simTicks < 240) {
      // 前 240 帧跑布局让它稳定下来，每帧重绘；稳定后停掉循环（交互时再单帧重绘）
      simStep(state.nodes, state.clusters, worldW(), worldH());
      draw();
      state.raf = requestAnimationFrame(loop);
    } else {
      draw();                 // 收尾画最后一帧
      state.running = false;  // 停！静止时不再空转，省 CPU
      state.raf = 0;
    }
  }
  function worldW() { return state.width; }
  function worldH() { return state.height; }

  function startLoop() {
    simTicks = 0;
    state.running = true;
    if (!state.raf) state.raf = requestAnimationFrame(loop);
  }
  function stopLoop() {
    state.running = false;
    if (state.raf) { cancelAnimationFrame(state.raf); state.raf = 0; }
  }

  // ───────────────────────── 数据加载 ─────────────────────────
  function loadData() {
    setStat("正在读取…");
    fetch(backend() + "/graph/nodes?scope=" + encodeURIComponent(state.scope))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var items = (d && d.items) || [];
        if (!items.length) {
          showEmpty(emptyMsgForScope(state.scope));
          // 仍然把范围数量更新一下
          updateScopeLegend(d && d.counts);
          return;
        }
        hideEmpty();
        buildFromItems(items);
        var topicN = state.clusters.filter(function (c) { return c.key !== "零散"; }).length;
        setStat("· " + items.length + " 条 · " + topicN + " 个主题星团");
        updateScopeLegend(d && d.counts);
      })
      .catch(function (e) {
        showEmpty("读取失败：" + (e && e.message ? e.message : e) +
          "<br><br>如果刚更新过文件，请完全退出并重开超能小助（后端要重启）。");
      });
  }

  function emptyMsgForScope(scope) {
    if (scope === "chat")
      return "这个范围还没有内容。<br>去「💬 对话」聊几句，聊过的就会变成星。";
    if (scope === "video")
      return "还没有视频笔记。<br>去「🎬 视频」提取几个视频，它们就会出现在这片星空。";
    if (scope === "sniff")
      return "还没有嗅探到的内容。<br>去「📡 嗅探」扫一遍关注的博主，扫到的视频会变成星。";
    return "还没有可显示的数据。<br>用「对话 / 嗅探 / 视频」积累一些内容，这里就会亮起来。";
  }

  // 范围图例：「全部」时显示各来源色块 + 数量；单范围时隐藏
  function updateScopeLegend(counts) {
    var box = els.scopeLegend;
    if (!box) return;
    if (state.scope !== "all") { box.innerHTML = ""; return; }
    var order = ["chat", "video", "sniff", "insight"];
    box.innerHTML = order.map(function (s) {
      var n = (counts && counts[s]) || 0;
      if (!n) return "";
      return '<span class="sl"><i style="background:' + SOURCE_COLOR[s] + '"></i>' +
        SOURCE_LABEL[s] + " " + n + "</span>";
    }).join("");
  }

  function buildFromItems(items) {
    // 时间用于 recency：最新=1，最老=0
    var times = items.map(function (it) { return parseTime(it.when) || 0; });
    var maxT = Math.max.apply(null, times.concat([1]));
    var minT = Math.min.apply(null, times.filter(function (t) { return t > 0; }).concat([maxT]));
    var span = Math.max(1, maxT - minT);

    state.nodes = items.map(function (it, i) {
      var freq = extractKeywordTable(it.text || it.preview || it.title || "");
      var kw = topKeywords(freq, 5);
      var t = times[i] || minT;
      var recency = (t - minT) / span;
      var chars = it.chars || 0;
      var r = 3.2 + Math.min(7, Math.sqrt(chars) / 7) + (it.turns ? Math.min(2, it.turns * 0.2) : 0);
      return {
        id: it.id, title: it.title || "未命名",
        when: it.when, when_human: it.when_human || "",
        turns: it.turns || 1, chars: chars, preview: (it.text || "").slice(0, 120),
        starred: !!it.starred, freq: freq, kw: kw, cluster: 0,
        recency: isFinite(recency) ? recency : 0.5,
        r: r, x: 0, y: 0, vx: 0, vy: 0,
        scope: it.scope || "chat", scope_label: it.scope_label || "",
        open: it.open || "none", ref: it.ref || "", url: it.url || "",
        creator: it.creator || "",
      };
    });
    state.clusters = buildClusters(state.nodes);
    layout(state.nodes, state.clusters, worldW(), worldH());
    simTicks = 0;
    // 复位视图
    state.view = { ox: 0, oy: 0, scale: 1 };
    state.loaded = true;
    startLoop();
  }

  function parseTime(iso) {
    if (!iso) return 0;
    var t = Date.parse(iso);
    return isNaN(t) ? 0 : t;
  }

  // ───────────────────────── tooltip / 交互 ─────────────────────────
  function showTip(node, sx, sy) {
    var tip = els.tip;
    var when = node.when_human ? ("🕐 " + node.when_human + " · ") : "";
    var src = node.scope_label ? ('<span style="color:' + (SOURCE_COLOR[node.scope] || "#9aa0cc") + '">● ' + node.scope_label + "</span> · ") : "";
    var kw = node.kw.length ? ("🏷 " + node.kw.slice(0, 4).join(" / ")) : "";
    var sub = node.creator ? ("👤 " + node.creator + " · ") : "";
    var hint = node.open === "conversation" ? "点击 → 回到这段对话"
             : node.open === "video_note" ? "点击 → 打开视频笔记"
             : node.open === "url" ? "点击 → 打开原链接"
             : "";
    tip.innerHTML =
      '<div class="kt-title">' + escapeHtmlK(node.title) + (node.starred ? " ⭐" : "") + "</div>" +
      '<div class="kt-meta">' + src + sub + when + (node.turns > 1 ? (node.turns + " 轮对话") : "") + "</div>" +
      (node.preview ? '<div class="kt-prev">' + escapeHtmlK(node.preview.slice(0, 90)) + "…</div>" : "") +
      (kw ? '<div class="kt-prev" style="margin-top:5px;color:#9aa0cc">' + escapeHtmlK(kw) + "</div>" : "") +
      (hint ? '<div class="kt-hint">' + hint + "</div>" : "");
    tip.style.display = "block";
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var x = sx + 16, y = sy + 16;
    if (x + tw > state.width - 8) x = sx - tw - 16;
    if (y + th > state.height - 8) y = sy - th - 16;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }
  function hideTip() { if (els.tip) els.tip.style.display = "none"; }

  function escapeHtmlK(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // 点击一颗星 → 按来源打开：对话回到对话 / 视频开笔记 / 其它开链接
  function openNode(node) {
    if (!node) return;
    if (node.open === "conversation") {
      fetch(backend() + "/conversations/get?id=" + encodeURIComponent(node.ref || node.id))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || !d.ok) { alert("打开失败：" + ((d && d.message) || "未知错误")); return; }
          if (typeof window.openConversationFromGraph === "function") window.openConversationFromGraph(d);
          else alert("已读取「" + (d.title || "对话") + "」。");
        })
        .catch(function (e) { alert("打开失败：" + e.message); });
    } else if (node.open === "video_note") {
      // 跳到「视频」板块并打开这条笔记
      if (typeof window.openVideoNoteFromGraph === "function") {
        window.openVideoNoteFromGraph(node.ref, node.title);
      } else {
        try { document.querySelector('.nav-item[data-view="video"]').click(); } catch (e) {}
      }
    } else if (node.open === "url" && node.url) {
      // 外部链接：交给系统浏览器（Electron 会拦截 http(s) 用外部浏览器开）
      try { window.open(node.url, "_blank"); } catch (e) {}
    } else {
      // 没有可打开目标：轻提示
      if (typeof window.kgToast === "function") window.kgToast(node.title);
    }
  }

  // ───────────────────────── 画布尺寸 / 事件绑定 ─────────────────────────
  function resize() {
    var wrap = els.wrap, cv = els.canvas;
    if (!wrap || !cv) return;
    var rect = wrap.getBoundingClientRect();
    state.dpr = window.devicePixelRatio || 1;
    state.width = rect.width; state.height = rect.height;
    cv.width = Math.round(rect.width * state.dpr);
    cv.height = Math.round(rect.height * state.dpr);
    cv.style.width = rect.width + "px";
    cv.style.height = rect.height + "px";
    els.ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
  }

  var drag = null;
  function bindEvents() {
    var cv = els.canvas;

    cv.addEventListener("mousedown", function (e) {
      drag = { sx: e.offsetX, sy: e.offsetY, ox: state.view.ox, oy: state.view.oy, moved: false };
      cv.classList.add("grabbing");
    });
    window.addEventListener("mousemove", function (e) {
      if (!isActive()) return;
      var rect = cv.getBoundingClientRect();
      var mx = e.clientX - rect.left, my = e.clientY - rect.top;
      if (drag) {
        var dx = mx - drag.sx, dy = my - drag.sy;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;
        state.view.ox = drag.ox + dx;
        state.view.oy = drag.oy + dy;
        hideTip();
        draw();
      } else {
        // hover 命中
        var hit = pickNode(mx, my);
        if (hit !== state.hover) {
          state.hover = hit;
          cv.style.cursor = hit >= 0 ? "pointer" : "grab";
          draw();
        }
        if (hit >= 0) showTip(state.nodes[hit], mx, my); else hideTip();
      }
    });
    window.addEventListener("mouseup", function (e) {
      if (drag && !drag.moved) {
        // 当成点击
        var rect = cv.getBoundingClientRect();
        var hit = pickNode(e.clientX - rect.left, e.clientY - rect.top);
        if (hit >= 0) openNode(state.nodes[hit]);
      }
      drag = null;
      cv.classList.remove("grabbing");
    });

    // 滚轮缩放（以光标为中心）
    cv.addEventListener("wheel", function (e) {
      e.preventDefault();
      var rect = cv.getBoundingClientRect();
      var mx = e.clientX - rect.left, my = e.clientY - rect.top;
      var before = toWorld(mx, my);
      var factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      state.view.scale = Math.max(0.3, Math.min(3.5, state.view.scale * factor));
      var after = toWorld(mx, my);
      // 保持光标下的世界点不动
      state.view.ox += (after.x - before.x) * state.view.scale;
      state.view.oy += (after.y - before.y) * state.view.scale;
      draw();
    }, { passive: false });

    // 搜索
    if (els.search) {
      els.search.addEventListener("input", function () {
        state.filter = els.search.value.trim();
        draw();
      });
    }
    if (els.reload) {
      els.reload.addEventListener("click", function () { loadData(); });
    }
    // 范围切换：对话/嗅探/视频/全部，切一下就换一张星图
    if (els.scopes) {
      els.scopes.querySelectorAll(".kg-scope").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var sc = btn.dataset.scope || "all";
          if (sc === state.scope) return;
          state.scope = sc;
          els.scopes.querySelectorAll(".kg-scope").forEach(function (b) {
            b.classList.toggle("active", b === btn);
          });
          state.filter = ""; if (els.search) els.search.value = "";
          state.hover = -1;
          loadData();
        });
      });
    }

    window.addEventListener("resize", function () {
      if (isActive()) { resize(); draw(); }
    });
  }

  function isActive() {
    var v = document.getElementById("view-knowledge");
    return v && v.classList.contains("active");
  }

  // ───────────────────────── 状态行 / 空态 ─────────────────────────
  function setStat(t) { if (els.stat) els.stat.textContent = t || ""; }
  function showEmpty(html) {
    if (els.empty) { els.empty.innerHTML = html; els.empty.style.display = "flex"; }
    setStat("");
  }
  function hideEmpty() { if (els.empty) els.empty.style.display = "none"; }

  // ───────────────────────── 入口 ─────────────────────────
  var inited = false;
  function init() {
    els.wrap = document.getElementById("kgWrap");
    els.canvas = document.getElementById("kgCanvas");
    els.tip = document.getElementById("kgTip");
    els.stat = document.getElementById("kgStat");
    els.empty = document.getElementById("kgEmpty");
    els.search = document.getElementById("kgSearch");
    els.reload = document.getElementById("kgReload");
    els.scopes = document.getElementById("kgScopes");
    els.scopeLegend = document.getElementById("kgScopeLegend");
    if (!els.canvas) return false;
    els.ctx = els.canvas.getContext("2d");
    bindEvents();
    inited = true;
    return true;
  }

  // renderer.js 在切到该视图时调用
  window.loadKnowledge = function () {
    if (!inited && !init()) return;
    resize();
    // 每次进来都重新读（对话会增长）；已加载过也刷新一遍保证最新
    loadData();
  };

  // 离开视图时停掉动画，省 CPU（renderer.js 切视图时可调；没调也无妨——loop 自带 isActive 守卫不强制）
  window.pauseKnowledge = function () { stopLoop(); };
})();
