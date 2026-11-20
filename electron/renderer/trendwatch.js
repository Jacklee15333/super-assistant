// ============================================================
// trendwatch.js —「趋势瞭望台」（v106 新增）：每天看清 AI 与产业的风向
//   · 今日观测：8 个每天扫一遍的源 + 8 个每周精读的源，可打勾（打开网站会自动打勾），每天一个思考问题
//   · 全部信息源：100 个源，按「一手信息 / 数据信号 / 研究分析 / 新闻讨论」四层金字塔筛选，
//     也能按分类、中英文、更新频率、收藏筛选；每个源可以一键「加入嗅探」，让小助定时盯它的更新
//   · 方法：怎么把每天的阅读变成判断趋势的能力
// 自己挂导航事件，不改 renderer.js（renderer.js 的通用切换逻辑负责显示 #view-trendwatch）。
// 「加入嗅探」复用后端已有接口：GET /sniff/sources、POST /sniff/source/add（类别「趋势瞭望台」）。
// 勾选、收藏、上次停在哪个标签，存在本机 localStorage。
// 复用全局：BACKEND（没有就用默认地址）
// ============================================================
(function () {
  "use strict";

  var root = document.getElementById("view-trendwatch");
  if (!root) return;

  var CATS = [
    ["cn-tech", "中文科技与AI媒体", "国内科技与AI动态的主阵地"],
    ["cn-biz", "中文财经与产业新闻", "宏观、市场与公司动向"],
    ["cn-gov", "中国政策与官方数据", "政策原文和统计数据，判断以它为准"],
    ["cn-research", "中文研究报告与数据", "白皮书、行业报告和用户数据"],
    ["global-news", "全球科技与商业新闻", "国际主流媒体怎么报道"],
    ["ai-deep", "AI深度分析与专业周报", "理解“为什么”和“意味着什么”"],
    ["labs", "AI实验室与模型追踪", "模型发布、论文、开源和价格"],
    ["think", "全球研究机构与智库", "年度报告和长期数据"],
    ["venture", "创业与投资动向", "钱和创业者正在流向哪里"],
    ["signals", "趋势信号、社区与判断力训练", "搜索、招聘、讨论和预测练习"]
  ];
  var LAYERS = [
    { k: "primary", name: "一手信息", hint: "最慢，最可靠：用来确认", w: 46 },
    { k: "data", name: "数据信号", hint: "常常领先新闻：用来验证", w: 64 },
    { k: "analysis", name: "研究分析", hint: "解释原因和影响：用来理解", w: 82 },
    { k: "news", name: "新闻讨论", hint: "最快，噪音最大：用来发现线索", w: 100 }
  ];
  var TYPE_LAYER = { "一手": "primary", "数据": "data", "工具": "data", "深度": "analysis", "研究": "analysis", "快讯": "news", "社区": "news" };
  var LAYER_NAME = { primary: "一手信息", data: "数据信号", analysis: "研究分析", news: "新闻讨论" };
  var FREQ_NAME = { d: "每天更新", w: "每周更新", m: "每月更新", x: "低频或按需查看" };
  var PAID = ["", "付费", "部分付费"];

  // [名称, 网址, 分类, 语言, 更新频率, 类型, 看什么, 付费(0无/1付费/2部分付费), 推荐(d每日/w每周)]
  var RAW = [
    ["36氪", "https://36kr.com", "cn-tech", "zh", "每天", "快讯", "创投快讯、融资消息和新经济公司报道，看国内的钱和公司往哪走", 0, "d"],
    ["虎嗅", "https://www.huxiu.com", "cn-tech", "zh", "每天", "深度", "商业科技评论和公司深度稿，适合看观点和争论", 0, ""],
    ["钛媒体", "https://www.tmtpost.com", "cn-tech", "zh", "每天", "快讯", "科技产业资讯，发布会和行业大会报道及时", 0, ""],
    ["机器之心", "https://www.jiqizhixin.com", "cn-tech", "zh", "每天", "深度", "AI技术与产业报道、论文解读，专业度高", 0, "d"],
    ["量子位", "https://www.qbitai.com", "cn-tech", "zh", "每天", "快讯", "AI新闻与前沿动态，更新快、覆盖广", 0, "d"],
    ["智东西", "https://zhidx.com", "cn-tech", "zh", "每天", "快讯", "AI、芯片和智能硬件产业链报道", 0, ""],
    ["雷峰网", "https://www.leiphone.com", "cn-tech", "zh", "每天", "深度", "AI、智能驾驶、硬科技与学术动态", 0, ""],
    ["极客公园", "https://www.geekpark.net", "cn-tech", "zh", "每天", "深度", "科技产品、创新者访谈和创业故事", 0, ""],
    ["品玩", "https://www.pingwest.com", "cn-tech", "zh", "每天", "快讯", "中美科技动态与AI产品报道", 0, ""],
    ["InfoQ中文", "https://www.infoq.cn", "cn-tech", "zh", "每周", "深度", "技术架构与AI工程落地案例，偏开发者视角", 0, ""],
    ["少数派", "https://sspai.com", "cn-tech", "zh", "每周", "深度", "效率工具和AI应用的一线使用体验", 0, ""],
    ["爱集微", "https://www.laoyaoba.com", "cn-tech", "zh", "每天", "快讯", "半导体与芯片产业新闻，跟踪国产算力链", 0, ""],
    ["华尔街见闻", "https://wallstreetcn.com", "cn-biz", "zh", "每天", "快讯", "全球市场与宏观快讯，重大财经事件第一时间", 0, "d"],
    ["财联社", "https://www.cls.cn", "cn-biz", "zh", "每天", "快讯", "财经电报和上市公司动态", 0, ""],
    ["第一财经", "https://www.yicai.com", "cn-biz", "zh", "每天", "深度", "宏观经济、产业和公司新闻", 0, ""],
    ["财新", "https://www.caixin.com", "cn-biz", "zh", "每天", "深度", "深度财经调查与政策解读", 2, ""],
    ["界面新闻", "https://www.jiemian.com", "cn-biz", "zh", "每天", "快讯", "商业与科技公司报道", 0, ""],
    ["澎湃新闻", "https://www.thepaper.cn", "cn-biz", "zh", "每天", "快讯", "时政与科技综合新闻", 0, ""],
    ["21世纪经济报道", "https://www.21jingji.com", "cn-biz", "zh", "每天", "深度", "产业、区域经济与公司报道", 0, ""],
    ["中国政府网", "https://www.gov.cn", "cn-gov", "zh", "每周", "一手", "国务院政策文件原文，判断政策方向以原文为准", 0, "w"],
    ["国家发展改革委", "https://www.ndrc.gov.cn", "cn-gov", "zh", "每周", "一手", "产业政策、发展规划与重大项目", 0, ""],
    ["工业和信息化部", "https://www.miit.gov.cn", "cn-gov", "zh", "每周", "一手", "制造业、信息化和人工智能产业政策", 0, ""],
    ["国家网信办", "https://www.cac.gov.cn", "cn-gov", "zh", "每周", "一手", "生成式AI备案、AI内容标识等监管规则", 0, ""],
    ["国家统计局", "https://www.stats.gov.cn", "cn-gov", "zh", "每月", "数据", "宏观经济、工业和消费的月度数据", 0, ""],
    ["国家能源局", "https://www.nea.gov.cn", "cn-gov", "zh", "每月", "数据", "能源与电力数据，AI的“上游”约束", 0, ""],
    ["科技日报", "https://www.stdaily.com", "cn-gov", "zh", "每天", "快讯", "科技政策与科研进展报道", 0, ""],
    ["巨潮资讯网", "https://www.cninfo.com.cn", "cn-gov", "zh", "按需", "一手", "上市公司公告和年报原文，核实公司说法的地方", 0, ""],
    ["中国信通院", "https://www.caict.ac.cn", "cn-research", "zh", "每月", "研究", "人工智能、数字经济白皮书与发展报告", 0, ""],
    ["腾讯研究院", "https://www.tisi.org", "cn-research", "zh", "每周", "研究", "科技与社会、AI治理与产业研究", 0, "w"],
    ["阿里研究院", "https://www.aliresearch.com", "cn-research", "zh", "每月", "研究", "数字经济与产业数字化研究", 0, ""],
    ["智源社区", "https://hub.baai.ac.cn", "cn-research", "zh", "每周", "研究", "北京智源人工智能研究院的AI前沿论文与学术活动", 0, ""],
    ["中国互联网络信息中心", "https://www.cnnic.net.cn", "cn-research", "zh", "每半年", "数据", "《中国互联网络发展状况统计报告》等权威数据", 0, ""],
    ["艾瑞咨询", "https://www.iresearch.com.cn", "cn-research", "zh", "每月", "研究", "互联网与消费行业研究报告", 0, ""],
    ["QuestMobile", "https://www.questmobile.com.cn", "cn-research", "zh", "每月", "数据", "移动互联网与AI应用的用户规模数据", 0, ""],
    ["发现报告", "https://www.fxbaogao.com", "cn-research", "zh", "每周", "研究", "券商研报与行业报告的聚合搜索", 2, ""],
    ["MIT Technology Review", "https://www.technologyreview.com", "global-news", "en", "每天", "深度", "新兴技术的深度报道，AI报道扎实", 2, "d"],
    ["The Verge", "https://www.theverge.com", "global-news", "en", "每天", "快讯", "科技产品与平台动态", 0, ""],
    ["TechCrunch", "https://techcrunch.com", "global-news", "en", "每天", "快讯", "创业融资与科技公司新闻", 0, ""],
    ["Ars Technica", "https://arstechnica.com", "global-news", "en", "每天", "深度", "技术细节扎实的科技新闻", 0, ""],
    ["The Information", "https://www.theinformation.com", "global-news", "en", "每天", "深度", "科技公司内幕与独家报道", 1, ""],
    ["路透社科技", "https://www.reuters.com/technology/", "global-news", "en", "每天", "快讯", "全球科技与监管要闻", 0, ""],
    ["Bloomberg Technology", "https://www.bloomberg.com/technology", "global-news", "en", "每天", "快讯", "科技公司与资本市场", 1, ""],
    ["Financial Times", "https://www.ft.com", "global-news", "en", "每天", "深度", "全球商业、科技与政策", 1, ""],
    ["The Economist", "https://www.economist.com", "global-news", "en", "每周", "深度", "全球趋势与政策分析", 1, ""],
    ["Rest of World", "https://restofworld.org", "global-news", "en", "每周", "深度", "科技在非西方国家的真实影响", 0, ""],
    ["Stratechery", "https://stratechery.com", "ai-deep", "en", "每周", "深度", "科技公司的商业模式与战略分析", 2, ""],
    ["Benedict Evans", "https://www.ben-evans.com", "ai-deep", "en", "每周", "深度", "科技趋势分析和年度宏观演示", 0, "w"],
    ["Exponential View", "https://www.exponentialview.co", "ai-deep", "en", "每周", "深度", "指数级技术对经济和社会的影响", 2, ""],
    ["One Useful Thing", "https://www.oneusefulthing.org", "ai-deep", "en", "每周", "深度", "沃顿商学院教授Ethan Mollick写AI如何改变工作与组织", 0, "w"],
    ["Import AI", "https://jack-clark.net", "ai-deep", "en", "每周", "深度", "AI研究与政策周报，信息密度高", 0, "w"],
    ["The Batch", "https://www.deeplearning.ai/the-batch/", "ai-deep", "en", "每周", "深度", "吴恩达团队的AI周报，适合入门跟踪", 0, "w"],
    ["Latent Space", "https://www.latent.space", "ai-deep", "en", "每周", "深度", "AI工程师视角的访谈与分析", 0, ""],
    ["Interconnects", "https://www.interconnects.ai", "ai-deep", "en", "每周", "深度", "模型训练、开源模型与行业格局", 0, ""],
    ["Simon Willison’s Weblog", "https://simonwillison.net", "ai-deep", "en", "每天", "深度", "大模型工具与新功能的一线实测", 0, ""],
    ["SemiAnalysis", "https://semianalysis.com", "ai-deep", "en", "每周", "深度", "芯片、算力与数据中心的产业分析", 2, ""],
    ["ChinaTalk", "https://www.chinatalk.media", "ai-deep", "en", "每周", "深度", "中美科技竞争与AI政策", 0, ""],
    ["Gary Marcus", "https://garymarcus.substack.com", "ai-deep", "en", "每周", "深度", "对AI炒作的批评视角，用来平衡乐观叙事", 0, ""],
    ["OpenAI 新闻", "https://openai.com/news/", "labs", "en", "不定期", "一手", "模型发布、产品与研究公告", 0, ""],
    ["Google DeepMind", "https://deepmind.google/discover/blog/", "labs", "en", "不定期", "一手", "Gemini等模型与科研突破", 0, ""],
    ["Anthropic 新闻", "https://www.anthropic.com/news", "labs", "en", "不定期", "一手", "Claude模型发布、研究与AI经济影响报告", 0, ""],
    ["Meta AI", "https://ai.meta.com/blog/", "labs", "en", "不定期", "一手", "Llama等开源模型与研究", 0, ""],
    ["NVIDIA 博客", "https://blogs.nvidia.com", "labs", "en", "每周", "一手", "GPU、数据中心与AI基础设施动态", 0, ""],
    ["DeepSeek", "https://www.deepseek.com", "labs", "zh", "不定期", "一手", "国产开源大模型的发布与技术报告", 0, ""],
    ["百度智能云", "https://cloud.baidu.com", "labs", "zh", "不定期", "一手", "千帆平台与文心模型的发布和价格", 0, ""],
    ["阿里云", "https://www.aliyun.com", "labs", "zh", "不定期", "一手", "通义千问模型与云服务的发布和价格", 0, ""],
    ["arXiv cs.AI", "https://arxiv.org/list/cs.AI/recent", "labs", "en", "每天", "一手", "最新AI论文预印本，研究风向的源头", 0, ""],
    ["Hugging Face Papers", "https://huggingface.co/papers", "labs", "en", "每天", "一手", "社区每日精选论文，比直接刷arXiv省力", 0, "d"],
    ["魔搭社区", "https://www.modelscope.cn", "labs", "zh", "每周", "一手", "国内开源模型的首发地之一", 0, ""],
    ["GitHub Trending", "https://github.com/trending", "labs", "en", "每天", "数据", "开发者最近在关注哪些项目", 0, "d"],
    ["Artificial Analysis", "https://artificialanalysis.ai", "labs", "en", "每周", "数据", "各模型能力、速度与价格对比，看“变便宜”的速度", 0, "w"],
    ["OpenRouter 排行", "https://openrouter.ai/rankings", "labs", "en", "每周", "数据", "各模型的真实调用量排名，看谁在被真正使用", 0, ""],
    ["斯坦福 AI Index", "https://hai.stanford.edu/ai-index", "think", "en", "每年", "研究", "最全面的AI年度数据报告，每年春季发布", 0, ""],
    ["麦肯锡洞见", "https://www.mckinsey.com/featured-insights", "think", "en", "每周", "研究", "含年度《The State of AI》企业调查", 0, ""],
    ["MIT Sloan Management Review", "https://sloanreview.mit.edu", "think", "en", "每周", "研究", "AI与组织管理研究", 2, ""],
    ["NBER 工作论文", "https://www.nber.org/papers", "think", "en", "每周", "研究", "经济学前沿，AI与生产率研究常先在这里发布", 0, ""],
    ["Epoch AI", "https://epoch.ai", "think", "en", "每周", "数据", "算力、训练成本和AI能力的趋势数据", 0, "w"],
    ["METR", "https://metr.org", "think", "en", "不定期", "研究", "评测AI能独立完成多长的任务", 0, ""],
    ["国际货币基金组织", "https://www.imf.org", "think", "en", "每季", "研究", "《世界经济展望》等宏观预测", 0, ""],
    ["世界经济论坛", "https://www.weforum.org", "think", "en", "不定期", "研究", "《未来就业报告》等职业趋势研究", 0, ""],
    ["国际能源署", "https://www.iea.org", "think", "en", "每月", "数据", "能源与数据中心用电，AI的能源约束", 0, ""],
    ["Microsoft WorkLab", "https://www.microsoft.com/en-us/worklab", "think", "en", "每年", "研究", "《Work Trend Index》职场AI调查", 0, ""],
    ["CSET", "https://cset.georgetown.edu", "think", "en", "每月", "研究", "AI与安全、中美科技竞争的数据研究", 0, ""],
    ["Our World in Data", "https://ourworldindata.org", "think", "en", "每月", "数据", "长期趋势数据与可视化，含AI专题", 0, ""],
    ["Y Combinator 公司库", "https://www.ycombinator.com/companies", "venture", "en", "每季", "数据", "每批新创业公司在做什么，最早的需求信号", 0, ""],
    ["a16z", "https://a16z.com", "venture", "en", "每周", "深度", "顶级风投机构的趋势文章与报告", 0, ""],
    ["Crunchbase News", "https://news.crunchbase.com", "venture", "en", "每天", "数据", "全球融资数据与趋势", 0, ""],
    ["CB Insights", "https://www.cbinsights.com", "venture", "en", "每周", "研究", "科技投资与行业研究", 2, ""],
    ["Product Hunt", "https://www.producthunt.com", "venture", "en", "每天", "社区", "每日新产品发布榜，看AI应用往哪个方向扎堆", 0, ""],
    ["IT桔子", "https://www.itjuzi.com", "venture", "zh", "每天", "数据", "国内创投数据库与融资事件", 2, ""],
    ["Indie Hackers", "https://www.indiehackers.com", "venture", "en", "每周", "社区", "独立开发者和一人公司的收入与案例", 0, ""],
    ["Google Trends", "https://trends.google.com", "signals", "en", "按需", "数据", "全球搜索热度，验证一个话题是否真在升温", 0, ""],
    ["百度指数", "https://index.baidu.com", "signals", "zh", "按需", "数据", "国内搜索热度与人群画像", 0, ""],
    ["Indeed Hiring Lab", "https://www.hiringlab.org", "signals", "en", "每月", "数据", "招聘需求趋势，含AI相关岗位的变化", 0, ""],
    ["Hacker News", "https://news.ycombinator.com", "signals", "en", "每天", "社区", "硅谷工程师和创业者在讨论什么", 0, "d"],
    ["即刻", "https://okjike.com", "signals", "zh", "每天", "社区", "国内AI从业者和产品人的讨论圈", 0, ""],
    ["小宇宙", "https://www.xiaoyuzhoufm.com", "signals", "zh", "每周", "社区", "中文播客平台，科技与商业访谈很多", 0, ""],
    ["Metaculus", "https://www.metaculus.com", "signals", "en", "每周", "工具", "社区对AI等问题的概率预测，也可以自己练习", 0, ""],
    ["Good Judgment Open", "https://www.gjopen.com", "signals", "en", "每周", "工具", "“超级预测”方法的公开练习平台", 0, ""],
    ["RSSHub", "https://docs.rsshub.app", "signals", "zh", "按需", "工具", "开源工具，把很多不提供RSS的网站转成订阅源", 0, ""],
    ["Farnam Street", "https://fs.blog", "signals", "en", "每周", "深度", "思维模型与决策方法，训练判断力", 0, ""]
  ];

  var QUESTIONS = [
    "今天看到的消息里，哪一条三个月后还重要？",
    "有没有哪条数据，和你之前的判断相矛盾？",
    "今天最热的那条新闻，是谁在说？他希望你相信什么？",
    "哪个价格或用量数字变了？变化有多大？",
    "如果今天的某条消息是真的，最先受影响的是哪类工作？",
    "这周有没有一个判断，可以写成带概率的预测？",
    "今天有没有哪家公司，说的和做的不一致？",
    "有什么事大家都在讨论，却还缺少数据支撑？",
    "今天的消息里，哪些是活动指标，哪些是结果指标？",
    "有没有一个趋势，正在从大公司走向中小企业？",
    "你所在的行业，今天有没有出现新的岗位名称或新工具？",
    "如果只能转发一条给同事，你会选哪条？为什么？"
  ];

  var SNIFF_CATEGORY = "趋势瞭望台";
  var SNIFF_MAX = 50;          // 和 backend/sniffer.py 的 MAX_SOURCES 一致
  var VIEWS = ["today", "all", "method"];

  // ---------------- 工具 ----------------
  function bucket(f) { return f === "每天" ? "d" : f === "每周" ? "w" : f === "每月" ? "m" : "x"; }
  function hostOf(u) {
    try { var x = new URL(u); var p = x.pathname.replace(/\/$/, ""); return x.hostname.replace(/^www\./, "") + (p && p !== "/" ? p : ""); }
    catch (e) { return u; }
  }
  function normUrl(u) {
    try { var x = new URL(u); return (x.hostname.replace(/^www\./, "") + x.pathname.replace(/\/+$/, "")).toLowerCase(); }
    catch (e) { return String(u || "").toLowerCase(); }
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function backend() { try { if (typeof BACKEND === "string" && BACKEND) return BACKEND; } catch (e) {} return "http://127.0.0.1:8756"; }
  function $(id) { return document.getElementById(id); }

  var SRC = RAW.map(function (r, i) {
    return { i: i, name: r[0], url: r[1], cat: r[2], lang: r[3], freq: r[4], fb: bucket(r[4]), type: r[5],
             layer: TYPE_LAYER[r[5]], desc: r[6], paid: r[7], core: r[8] || "", host: hostOf(r[1]) };
  });
  var BY_URL = {};
  SRC.forEach(function (s) { BY_URL[s.url] = s; });
  var DAILY = SRC.filter(function (s) { return s.core === "d"; });
  var WEEKLY = SRC.filter(function (s) { return s.core === "w"; });

  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var day = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - day);
    var y = t.getUTCFullYear();
    return [y, Math.ceil(((t - Date.UTC(y, 0, 1)) / 86400000 + 1) / 7)];
  }

  // 日期相关的键每次进页面都重新算（软件开着过了零点，勾选会自动换成新的一天）
  var K = {}, done = { d: new Set(), w: new Set() };
  function refreshDayKeys() {
    var now = new Date();
    var wk = isoWeek(now);
    var dayKey = "qushi.day." + now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
    var weekKey = "qushi.week." + wk[0] + "-" + wk[1];
    if (K.day !== dayKey) done.d = new Set(store.get(dayKey, []));
    if (K.week !== weekKey) done.w = new Set(store.get(weekKey, []));
    K = { now: now, wk: wk, day: dayKey, week: weekKey };
  }
  var favs = new Set(store.get("qushi.fav", []));
  var tab = store.get("qushi.tab", "today");
  if (VIEWS.indexOf(tab) < 0) tab = "today";
  var st = { q: "", lang: "all", freq: "all", layer: null, cat: null, fav: false };
  var sniff = { online: null, urls: new Set(), count: 0, busy: {} };

  var STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.6l2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/></svg>';
  function glyph(fb) { return '<span class="tw-fg ' + fb + '" role="img" aria-label="' + FREQ_NAME[fb] + '" title="' + FREQ_NAME[fb] + '"></span>'; }

  // ---------------- 页面骨架 ----------------
  function pyrHTML(counts, interactive) {
    return LAYERS.map(function (L, idx) {
      var cls = "tw-ly tw-ly" + (idx + 1);
      var inner = "<b>" + L.name + "</b><span class=\"n\">" + (counts ? counts[L.k] + " 个" : "") + "</span>";
      var bar = interactive
        ? '<button type="button" class="' + cls + '" data-layer="' + L.k + '" aria-pressed="' + (st.layer === L.k) + '" style="--w:' + L.w + '%">' + inner + "</button>"
        : '<div class="' + cls + '" style="--w:' + L.w + '%">' + inner + "</div>";
      return '<div class="tw-ly-row">' + bar + '<span class="tw-ly-hint">' + L.hint + "</span></div>";
    }).join("");
  }

  function buildShell() {
    root.innerHTML =
      '<header class="topbar"><span>趋势瞭望台</span><span class="topbar-hint">100个信息源，每天15分钟看清AI与产业的风向</span></header>' +
      '<div class="tw-scroll"><div class="tw-pane">' +
        '<div class="tw-tabs" role="tablist" aria-label="趋势瞭望台">' +
          '<button type="button" class="tw-tab" role="tab" data-tab="today">今日观测</button>' +
          '<button type="button" class="tw-tab" role="tab" data-tab="all">全部信息源</button>' +
          '<button type="button" class="tw-tab" role="tab" data-tab="method">方法</button>' +
        "</div>" +

        // ===== 今日观测 =====
        '<div class="tw-tabpane" data-pane="today">' +
          '<div class="tw-today">' +
            "<div>" +
              '<div class="tw-card">' +
                '<h2 class="tw-date" id="twDate"></h2>' +
                '<p class="tw-lede">每天15分钟：扫完下面8个信息源，只记下让你意外的1到3条。</p>' +
                '<div class="tw-progress"><div class="tw-pbar"><i id="twDFill"></i></div><span class="tw-ptext" id="twDText"></span></div>' +
                '<ul class="tw-check" id="twDaily"></ul>' +
                '<p class="tw-note">打开网站会自动打勾，也可以手动勾选；第二天会重新开始。网站会在你的浏览器里打开。</p>' +
              "</div>" +
              '<div class="tw-card">' +
                '<div class="tw-sec-h"><h3 class="tw-h">本周精读</h3><small id="twWeek"></small></div>' +
                '<p class="tw-lede">从下面挑2到3篇读透，把本周最重要的变化写进趋势笔记，每条附上出处。</p>' +
                '<div class="tw-progress"><div class="tw-pbar"><i id="twWFill"></i></div><span class="tw-ptext" id="twWText"></span></div>' +
                '<ul class="tw-check" id="twWeekly"></ul>' +
              "</div>" +
            "</div>" +
            "<aside>" +
              '<div class="tw-card accent">' +
                '<h3 class="tw-h">今天的一个问题</h3>' +
                '<p class="tw-q" id="twQ"></p>' +
                '<p class="tw-note">想清楚了，就把它写成一条预测。</p>' +
                '<div class="tw-btns"><button type="button" class="tw-btn ghost" data-go="method-tpl">看预测模板</button></div>' +
              "</div>" +
              '<div class="tw-card">' +
                '<h3 class="tw-h">让小助替你盯着</h3>' +
                '<p class="tw-lede" style="margin:0">把常看的网站加入「嗅探」，小助会抓取、对比更新，把新内容提炼成一条条动态；可以随时点「快速嗅探」，也可以打开「自动嗅探」让它定时跑。网站越多越慢，先从最常看的几个开始。</p>' +
                '<p class="tw-sniffstat" id="twSniffStat"></p>' +
                '<div class="tw-btns">' +
                  '<button type="button" class="tw-btn" id="twAddDaily">把今日观测的8个加入嗅探</button>' +
                  '<button type="button" class="tw-btn ghost" data-go="sniff">去嗅探看看</button>' +
                "</div>" +
              "</div>" +
              '<div class="tw-card">' +
                '<h3 class="tw-h">四个节奏</h3>' +
                '<ul class="tw-rhythm">' +
                  "<li>" + glyph("d") + "<span><b>每天15分钟</b>：扫完今日观测，记下意外的1到3条</span></li>" +
                  "<li>" + glyph("w") + "<span><b>每周1小时</b>：精读2到3篇，更新趋势笔记</span></li>" +
                  "<li>" + glyph("m") + "<span><b>每月半天</b>：看一次价格、用量、招聘、融资数据</span></li>" +
                  "<li>" + glyph("x") + "<span><b>每季度</b>：复盘预测，换掉没用的信息源</span></li>" +
                "</ul>" +
              "</div>" +
            "</aside>" +
          "</div>" +
        "</div>" +

        // ===== 全部信息源 =====
        '<div class="tw-tabpane" data-pane="all">' +
          '<div class="tw-card">' +
            '<p class="tw-lede">100个信息源按四个层级排列：越往上越慢、越可靠，越往下越快、噪音越大。点金字塔的某一层，只看这一层。</p>' +
            '<div class="tw-pyr" id="twPyr" role="group" aria-label="按信息层级筛选"></div>' +
          "</div>" +
          '<div class="tw-controls">' +
            '<input class="tw-search" id="twSearch" type="search" placeholder="搜索名称、网址或关键词" aria-label="搜索信息源">' +
            '<div class="tw-seg" data-seg="lang" role="group" aria-label="语言">' +
              '<button type="button" data-v="all" aria-pressed="true">全部</button><button type="button" data-v="zh" aria-pressed="false">中文</button><button type="button" data-v="en" aria-pressed="false">英文</button>' +
            "</div>" +
            '<div class="tw-seg" data-seg="freq" role="group" aria-label="更新频率">' +
              '<button type="button" data-v="all" aria-pressed="true">全部</button><button type="button" data-v="d" aria-pressed="false">每天</button><button type="button" data-v="w" aria-pressed="false">每周</button><button type="button" data-v="m" aria-pressed="false">每月</button><button type="button" data-v="x" aria-pressed="false">低频</button>' +
            "</div>" +
            '<button type="button" class="tw-toggle" id="twFavOnly" aria-pressed="false">' + STAR + "只看收藏</button>" +
          "</div>" +
          '<div class="tw-chips" id="twChips" role="group" aria-label="按分类筛选"></div>' +
          '<div class="tw-legend" aria-label="更新频率图例">' +
            "<span>" + glyph("d") + "每天更新</span><span>" + glyph("w") + "每周更新</span><span>" + glyph("m") + "每月更新</span><span>" + glyph("x") + "每季、每年、不定期或按需查</span>" +
          "</div>" +
          '<div class="tw-status"><span id="twCount"></span><span class="right"><span id="twSniffCount"></span><button type="button" class="tw-link" id="twClear" hidden>清除筛选</button></span></div>' +
          '<div id="twList"></div>' +
          '<p class="tw-note">整理于2026年11月。个别网站可能改版或更换地址，打不开时搜一下名称即可。英文网站可以用浏览器自带的翻译；标“付费”的大多有免费部分；部分海外网站在国内的访问情况会变化，可以先用同类中文源替代。</p>' +
        "</div>" +

        // ===== 方法 =====
        '<div class="tw-tabpane" data-pane="method">' + methodHTML() + "</div>" +
      "</div></div>" +
      '<div class="tw-toast" id="twToast" role="status" aria-live="polite" hidden></div>';
  }

  function methodHTML() {
    return '<div class="tw-method">' +
      '<div class="tw-card">' +
        '<h3 class="tw-h">怎样把每天的阅读，变成判断趋势的能力</h3>' +
        "<p>每天刷大量资讯，容易得到的是“知道很多事”，而不是“判断得准”。判断力来自三件事：分清信息的层级，盯住少数真正领先的指标，把判断写下来、过一段时间回头核对。</p>" +
      "</div>" +
      '<div class="tw-card">' +
        '<h3 class="tw-h">信息分四层，各有用处</h3>' +
        '<div class="tw-pyr" aria-hidden="true">' + pyrHTML(null, false) + "</div>" +
        "<p>一手信息是政策原文、公司公告和财报、论文、官方发布，最慢，但最可靠。数据信号是价格、调用量、招聘、融资、搜索热度和开源热度，常常比新闻更早反映变化。研究分析来自研究机构和专业周报，帮你理解原因和影响。新闻讨论最快，但噪音最大。</p>" +
        '<p class="tw-motto">用新闻发现线索，用数据验证，用一手信息确认，用分析理解。</p>' +
      "</div>" +
      '<div class="tw-card">' +
        '<h3 class="tw-h">四个节奏</h3>' +
        '<div class="tw-cad"><b>' + glyph("d") + "每天15分钟</b><p>打开“今日观测”的8个源，快速扫标题，只记下让你意外的1到3条。意外，说明它和你原来的判断不一样。</p></div>" +
        '<div class="tw-cad"><b>' + glyph("w") + "每周1小时</b><p>精读2到3篇深度文章，把本周最重要的变化写进趋势笔记，每条附上出处，并注明是一手信息、数据还是观点。</p></div>" +
        '<div class="tw-cad"><b>' + glyph("m") + "每月半天</b><p>集中看一次数据：模型价格、调用量、招聘、融资、统计数据。检查趋势笔记里的判断，有没有被数据支持。</p></div>" +
        '<div class="tw-cad"><b>' + glyph("x") + "每季度一次</b><p>复盘预测日志，算算自己判断对了多少；删掉一直没带来新判断的信息源，补上新的。</p></div>" +
      "</div>" +
      '<div class="tw-card">' +
        '<h3 class="tw-h">读到重要消息时，问三个问题</h3>' +
        '<ol class="tw-qs">' +
          "<li>谁说的？是一手信息还是转述？说话的人利益在哪里？发布会上的“大会口径”和第三方核实过的数据，分量完全不同。</li>" +
          "<li>有数据吗？是“用了多少”的活动指标，还是“省了多少、赚了多少”的结果指标？</li>" +
          "<li>如果是真的，三个月后和一年后，最先受影响的是谁？会不会影响到你的行业和你的工作？</li>" +
        "</ol>" +
      "</div>" +
      '<div class="tw-card">' +
        '<h3 class="tw-h">盯住六类领先指标</h3>' +
        "<p>新闻往往是变化发生之后的总结，下面这些数字常常更早动起来：</p>" +
        '<div class="tw-tbl"><table><thead><tr><th>指标</th><th>看什么</th><th>去哪里看</th></tr></thead><tbody>' +
          "<tr><td>价格</td><td>模型调用价、算力价格下降的速度</td><td>Artificial Analysis、百度智能云、阿里云</td></tr>" +
          "<tr><td>用量</td><td>token调用量、AI应用的用户规模</td><td>OpenRouter 排行、QuestMobile</td></tr>" +
          "<tr><td>招聘</td><td>新岗位的名称和数量，企业真金白银投向哪里</td><td>Indeed Hiring Lab、国内招聘网站搜索</td></tr>" +
          "<tr><td>资金</td><td>融资、并购、资本开支</td><td>IT桔子、Crunchbase News、巨潮资讯网</td></tr>" +
          "<tr><td>开源</td><td>项目关注度、模型下载量</td><td>GitHub Trending、Hugging Face、魔搭社区</td></tr>" +
          "<tr><td>政策</td><td>新规、备案、标准</td><td>中国政府网、国家网信办、工业和信息化部</td></tr>" +
        "</tbody></table></div>" +
      "</div>" +
      '<div class="tw-card" id="twTplCard">' +
        '<h3 class="tw-h">把判断写成预测，按时核对</h3>' +
        "<p>心理学家泰洛克等人的“超级预测”研究发现，预测能力可以通过练习和反馈提高。关键是把模糊的感觉写成具体、可验证、有期限、带概率的预测，到期再核对。可以照着这个格式写：</p>" +
        '<div class="tw-tpl"><pre id="twTpl">预测：到2027年6月30日，国内主流大模型每百万token的输出价格，比现在再降一半\n概率：60%\n依据：过去一年价格多次下调；开源模型持续发布；云厂商竞争加剧\n怎么验证：到期查看百度智能云、阿里云的官方价格页\n复盘日期：2027年6月30日\n复盘结果：到期再填：对还是错，原因是什么</pre>' +
        '<button type="button" class="tw-btn ghost" id="twCopy">复制模板</button></div>' +
        "<p>每个季度回头看一次。准确率本身不是重点，重点是发现自己在哪类问题上总是过于乐观或过于悲观。Metaculus 和 Good Judgment Open 上可以看到别人对同一问题的概率估计，适合对照练习。</p>" +
      "</div>" +
      '<div class="tw-card">' +
        '<h3 class="tw-h">在小助里怎么用</h3>' +
        "<p>常看的网站点「加入嗅探」，小助会抓取、对比更新，把新内容提炼出来。到「嗅探」的「网站新动态」里点「快速嗅探」看变化，想要成文报告点「深度嗅探」，也可以打开「自动嗅探」让它定时跑。嗅探清单最多50个网站，而且每个网站都要抓取和让模型提炼，先挑最常看的加。</p>" +
        "<p>这100个不需要每天都看。先从“今日观测”的8个和“本周精读”的8个开始，坚持四周，再按“有没有给我带来新判断”决定留下还是替换。收藏常用的源，用“只看收藏”就能得到自己的精简清单。很多优质中文内容在微信公众号里，可以挑5到10个与你行业相关的号固定阅读。</p>" +
      "</div>" +
    "</div>";
  }

  // ---------------- 今日观测 ----------------
  function ckRow(s, kind) {
    var on = done[kind].has(s.url);
    return '<li class="tw-ck' + (on ? " done" : "") + '" data-url="' + esc(s.url) + '">' +
      '<label class="tw-ckbox"><input type="checkbox" data-kind="' + kind + '" data-url="' + esc(s.url) + '"' + (on ? " checked" : "") +
      ' aria-label="标记已看：' + esc(s.name) + '"><span aria-hidden="true"></span></label>' +
      glyph(s.fb) +
      '<div class="tw-ck-main"><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer" data-kind="' + kind + '" data-url="' + esc(s.url) + '">' + esc(s.name) + "</a>" +
      '<span class="tw-ck-desc">' + esc(s.desc) + "</span></div></li>";
  }
  function renderToday() {
    var now = K.now;
    $("twDate").textContent = (now.getMonth() + 1) + "月" + now.getDate() + "日 星期" + "日一二三四五六".charAt(now.getDay());
    $("twWeek").textContent = K.wk[0] + "年第" + K.wk[1] + "周";
    var doy = Math.floor((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - Date.UTC(now.getFullYear(), 0, 0)) / 86400000);
    $("twQ").textContent = QUESTIONS[doy % QUESTIONS.length];
    $("twDaily").innerHTML = DAILY.map(function (s) { return ckRow(s, "d"); }).join("");
    $("twWeekly").innerHTML = WEEKLY.map(function (s) { return ckRow(s, "w"); }).join("");
    updateProgress();
    renderSniffStat();
  }
  function updateProgress() {
    [["d", DAILY, "twDFill", "twDText", "今天已看"], ["w", WEEKLY, "twWFill", "twWText", "本周已读"]].forEach(function (x) {
      var n = x[1].filter(function (s) { return done[x[0]].has(s.url); }).length;
      $(x[2]).style.width = (n / x[1].length * 100) + "%";
      $(x[3]).textContent = n === x[1].length
        ? (x[0] === "d" ? "今天的观测完成了，记下让你意外的1到3条" : "本周精读完成了，更新你的趋势笔记")
        : x[4] + " " + n + " / " + x[1].length;
    });
  }
  function setDone(kind, url, on) {
    if (on) done[kind].add(url); else done[kind].delete(url);
    store.set(kind === "d" ? K.day : K.week, Array.from(done[kind]));
    var list = $(kind === "d" ? "twDaily" : "twWeekly");
    Array.prototype.forEach.call(list.querySelectorAll("li.tw-ck"), function (li) {
      if (li.getAttribute("data-url") === url) {
        li.classList.toggle("done", on);
        var cb = li.querySelector("input"); if (cb) cb.checked = on;
      }
    });
    updateProgress();
  }

  // ---------------- 全部信息源 ----------------
  function ok(s, skip) {
    if (skip !== "lang" && st.lang !== "all" && s.lang !== st.lang) return false;
    if (skip !== "freq" && st.freq !== "all" && s.fb !== st.freq) return false;
    if (skip !== "layer" && st.layer && s.layer !== st.layer) return false;
    if (skip !== "cat" && st.cat && s.cat !== st.cat) return false;
    if (st.fav && !favs.has(s.url)) return false;
    if (st.q) {
      var q = st.q.toLowerCase();
      if (s.name.toLowerCase().indexOf(q) < 0 && s.desc.toLowerCase().indexOf(q) < 0 && s.host.toLowerCase().indexOf(q) < 0) return false;
    }
    return true;
  }
  function sniffSlotHTML(s) {
    if (sniff.urls.has(normUrl(s.url))) return '<span class="tw-sniffed" title="已经在嗅探清单里，小助会定时检查它的更新">已在嗅探</span>';
    if (sniff.busy[s.url]) return '<button type="button" class="tw-sniff" disabled>加入中…</button>';
    return '<button type="button" class="tw-sniff" data-sniff="' + esc(s.url) + '" title="让小助抓取这个网站、对比更新，有新内容就提炼出来">加入嗅探</button>';
  }
  function row(s) {
    var f = favs.has(s.url);
    return '<div class="tw-src">' + glyph(s.fb) +
      '<div class="tw-src-main"><div class="tw-src-top"><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' + esc(s.name) + "</a>" +
      (s.paid ? '<span class="tw-badge">' + PAID[s.paid] + "</span>" : "") +
      '<span class="tw-lang">' + (s.lang === "zh" ? "中文" : "英文") + "</span></div>" +
      '<p class="tw-src-desc">' + esc(s.desc) + "</p>" +
      '<p class="tw-src-meta"><span>' + esc(s.host) + "</span><span>" + esc(s.freq) + "</span><span>" + LAYER_NAME[s.layer] + "</span></p></div>" +
      '<div class="tw-acts">' +
        '<button type="button" class="tw-star' + (f ? " on" : "") + '" data-star="' + esc(s.url) + '" aria-pressed="' + f + '" aria-label="' + (f ? "取消收藏 " : "收藏 ") + esc(s.name) + '">' + STAR + "</button>" +
        '<span class="tw-sniff-slot" data-u="' + esc(s.url) + '">' + sniffSlotHTML(s) + "</span>" +
      "</div></div>";
  }
  function renderAll() {
    var base = SRC.filter(function (s) { return ok(s, "layer"); });
    var counts = {};
    LAYERS.forEach(function (L) { counts[L.k] = base.filter(function (s) { return s.layer === L.k; }).length; });
    var pyr = $("twPyr");
    pyr.innerHTML = pyrHTML(counts, true);
    pyr.classList.toggle("picked", !!st.layer);

    var cbase = SRC.filter(function (s) { return ok(s, "cat"); });
    $("twChips").innerHTML = '<button type="button" class="tw-chip" data-cat="" aria-pressed="' + (!st.cat) + '">全部分类<span class="n">' + cbase.length + "</span></button>" +
      CATS.map(function (c) {
        var n = cbase.filter(function (s) { return s.cat === c[0]; }).length;
        return '<button type="button" class="tw-chip" data-cat="' + c[0] + '" aria-pressed="' + (st.cat === c[0]) + '">' + c[1] + '<span class="n">' + n + "</span></button>";
      }).join("");

    var shown = SRC.filter(function (s) { return ok(s); });
    $("twCount").textContent = "显示 " + shown.length + " 个，共 " + SRC.length + " 个";
    $("twClear").hidden = !(st.q || st.lang !== "all" || st.freq !== "all" || st.layer || st.cat || st.fav);

    var html = "";
    CATS.forEach(function (c) {
      var items = shown.filter(function (s) { return s.cat === c[0]; });
      if (!items.length) return;
      html += '<section class="tw-card tw-grp"><div class="tw-grp-h"><h3 class="tw-h">' + c[1] + "</h3><p>" + c[2] + '</p><span class="n">' + items.length + " 个</span></div>" +
        '<div class="tw-rows">' + items.map(row).join("") + "</div></section>";
    });
    if (!html) {
      html = '<div class="tw-empty"><p>' + (st.fav && !favs.size ? "还没有收藏。点每个信息源右侧的星标，就能把它加进收藏。" : "没有符合条件的信息源。试试清空搜索词，或放宽筛选条件。") +
        '</p><button type="button" class="tw-btn ghost" data-clear="1">清除筛选</button></div>';
    }
    $("twList").innerHTML = html;
    renderSniffStat();
  }

  // ---------------- 嗅探联动 ----------------
  function renderSniffStat() {
    var txt = sniff.online === false
      ? "没连上小助后台，暂时不能加入嗅探"
      : sniff.online ? "嗅探清单里已有 " + sniff.count + " / " + SNIFF_MAX + " 个网站" : "";
    var a = $("twSniffStat"), b = $("twSniffCount");
    if (a) a.textContent = txt;
    if (b) b.textContent = txt;
    var btn = $("twAddDaily");
    if (btn) {
      var left = DAILY.filter(function (s) { return !sniff.urls.has(normUrl(s.url)); }).length;
      btn.disabled = sniff.online === false || left === 0 || !!sniff.bulk;
      btn.textContent = sniff.bulk ? "正在加入…" : left === 0 && sniff.online ? "今日观测的8个都在嗅探里了" : "把今日观测的" + (left === DAILY.length ? "8个" : "其余" + left + "个") + "加入嗅探";
    }
  }
  function updateSniffSlots(url) {
    var s = BY_URL[url];
    Array.prototype.forEach.call(root.querySelectorAll(".tw-sniff-slot"), function (el) {
      if (!url || el.getAttribute("data-u") === url) el.innerHTML = sniffSlotHTML(s || BY_URL[el.getAttribute("data-u")]);
    });
    renderSniffStat();
  }
  function refreshSniff() {
    return fetch(backend() + "/sniff/sources")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var list = (d && d.sources) || [];
        sniff.urls = new Set(list.map(function (x) { return normUrl(x.url); }));
        sniff.count = list.length;
        sniff.online = true;
      })
      .catch(function () { sniff.online = false; })
      .then(function () { updateSniffSlots(); });
  }
  function addOne(s) {
    sniff.busy[s.url] = true;
    updateSniffSlots(s.url);
    return fetch(backend() + "/sniff/source/add", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: s.name, url: s.url, category: SNIFF_CATEGORY })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok) { sniff.urls.add(normUrl(s.url)); sniff.count += 1; sniff.online = true; return { ok: true }; }
        var m = (d && d.message) || "没加进去";
        if (/已经在清单/.test(m)) { sniff.urls.add(normUrl(s.url)); return { ok: true, existed: true }; }
        return { ok: false, message: m };
      })
      .catch(function () { sniff.online = false; return { ok: false, message: "没连上小助后台，稍后再试" }; })
      .then(function (res) { delete sniff.busy[s.url]; updateSniffSlots(s.url); return res; });
  }
  function addToSniff(url) {
    var s = BY_URL[url];
    if (!s || sniff.busy[url]) return;
    addOne(s).then(function (res) {
      if (res.ok) toast(res.existed ? s.name + " 本来就在嗅探清单里。" : "已加入嗅探：" + s.name + "。到「嗅探」的「网站新动态」里点「快速嗅探」，或打开「自动嗅探」。");
      else toast(res.message, true);
    });
  }
  function addDailyToSniff() {
    var todo = DAILY.filter(function (s) { return !sniff.urls.has(normUrl(s.url)); });
    if (!todo.length || sniff.bulk) return;
    sniff.bulk = true; renderSniffStat();
    var added = 0, failMsg = "";
    var chain = Promise.resolve();
    todo.forEach(function (s) {
      chain = chain.then(function () {
        if (failMsg) return;
        return addOne(s).then(function (res) { if (res.ok && !res.existed) added += 1; if (!res.ok) failMsg = res.message; });
      });
    });
    chain.then(function () {
      sniff.bulk = false; renderSniffStat();
      if (failMsg) toast((added ? "已加入 " + added + " 个，" : "") + "后面的没加进去：" + failMsg, true);
      else toast("已加入 " + added + " 个网站到嗅探（类别「" + SNIFF_CATEGORY + "」）。到「嗅探」的「网站新动态」里点「快速嗅探」，或打开「自动嗅探」。");
    });
  }

  var toastTimer = null;
  function toast(msg, bad) {
    var el = $("twToast");
    if (!el) return;
    el.textContent = msg;
    el.className = "tw-toast" + (bad ? " bad" : "");
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, bad ? 6000 : 4200);
  }

  // ---------------- 标签切换 ----------------
  function showTab(t) {
    if (VIEWS.indexOf(t) < 0) t = "today";
    tab = t;
    store.set("qushi.tab", t);
    Array.prototype.forEach.call(root.querySelectorAll(".tw-tab"), function (b) {
      b.setAttribute("aria-selected", String(b.getAttribute("data-tab") === t));
    });
    Array.prototype.forEach.call(root.querySelectorAll(".tw-tabpane"), function (p) {
      p.hidden = p.getAttribute("data-pane") !== t;
    });
    var sc = root.querySelector(".tw-scroll");
    if (sc) sc.scrollTop = 0;
  }

  function clearFilters() {
    st = { q: "", lang: "all", freq: "all", layer: null, cat: null, fav: false };
    $("twSearch").value = "";
    $("twFavOnly").setAttribute("aria-pressed", "false");
    Array.prototype.forEach.call(root.querySelectorAll(".tw-seg button"), function (x) {
      x.setAttribute("aria-pressed", String(x.getAttribute("data-v") === "all"));
    });
    renderAll();
  }

  function copyTemplate(btn) {
    var text = $("twTpl").textContent;
    function say(m) { btn.textContent = m; setTimeout(function () { btn.textContent = "复制模板"; }, 2200); }
    function fallback() {
      try {
        var r = document.createRange(); r.selectNodeContents($("twTpl"));
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
        say("已选中，按 Ctrl+C 复制");
      } catch (e) { say("请手动选中复制"); }
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { say("已复制"); }, fallback);
      else fallback();
    } catch (e) { fallback(); }
  }

  // ---------------- 事件 ----------------
  function bind() {
    root.addEventListener("click", function (e) {
      var t = e.target;
      var b;
      if ((b = t.closest(".tw-tab"))) { showTab(b.getAttribute("data-tab")); return; }
      if ((b = t.closest("a[data-kind]"))) { setDone(b.getAttribute("data-kind"), b.getAttribute("data-url"), true); return; }
      if ((b = t.closest("button[data-star]"))) {
        var u = b.getAttribute("data-star");
        if (favs.has(u)) favs.delete(u); else favs.add(u);
        store.set("qushi.fav", Array.from(favs));
        if (st.fav) { renderAll(); return; }
        var on = favs.has(u);
        b.classList.toggle("on", on);
        b.setAttribute("aria-pressed", String(on));
        b.setAttribute("aria-label", (on ? "取消收藏 " : "收藏 ") + (BY_URL[u] ? BY_URL[u].name : ""));
        return;
      }
      if ((b = t.closest("button[data-sniff]"))) { addToSniff(b.getAttribute("data-sniff")); return; }
      if ((b = t.closest("button[data-layer]"))) { var k = b.getAttribute("data-layer"); st.layer = st.layer === k ? null : k; renderAll(); return; }
      if ((b = t.closest("button[data-cat]"))) { st.cat = b.getAttribute("data-cat") || null; renderAll(); return; }
      if ((b = t.closest(".tw-seg button"))) {
        var seg = b.parentNode;
        st[seg.getAttribute("data-seg")] = b.getAttribute("data-v");
        Array.prototype.forEach.call(seg.querySelectorAll("button"), function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        renderAll(); return;
      }
      if (t.closest("#twFavOnly")) { st.fav = !st.fav; $("twFavOnly").setAttribute("aria-pressed", String(st.fav)); renderAll(); return; }
      if (t.closest("#twClear") || t.closest("[data-clear]")) { clearFilters(); return; }
      if (t.closest("#twAddDaily")) { addDailyToSniff(); return; }
      if (t.closest("#twCopy")) { copyTemplate(t.closest("#twCopy")); return; }
      if ((b = t.closest("[data-go]"))) {
        var go = b.getAttribute("data-go");
        if (go === "sniff") {
          var nav = document.querySelector('.nav-item[data-view="sniff"]');
          if (nav) nav.click();
          // 网站清单在嗅探页的「网站新动态」标签里
          var webTab = document.querySelector('#view-sniff .sn-tab[data-sntab="web"]');
          if (webTab) webTab.click();
        } else if (go === "method-tpl") {
          showTab("method");
          var card = $("twTplCard");
          if (card && card.scrollIntoView) card.scrollIntoView({ block: "start" });
        }
      }
    });
    root.addEventListener("change", function (e) {
      var t = e.target;
      if (t && t.matches && t.matches('input[type="checkbox"][data-kind]')) setDone(t.getAttribute("data-kind"), t.getAttribute("data-url"), t.checked);
    });
    root.addEventListener("input", function (e) {
      if (e.target && e.target.id === "twSearch") { st.q = e.target.value.trim(); renderAll(); }
    });
  }

  // ---------------- 入口 ----------------
  var built = false;
  function load() {
    if (!built) { buildShell(); bind(); built = true; }
    refreshDayKeys();
    renderToday();
    renderAll();
    showTab(tab);
    refreshSniff();
  }
  window.loadTrendwatch = load;

  var navBtn = document.querySelector('.nav-item[data-view="trendwatch"]');
  if (navBtn) navBtn.addEventListener("click", load);
  // 先把骨架和内容画好（不连后台），点进来时再刷新日期和嗅探状态
  try { buildShell(); bind(); built = true; refreshDayKeys(); renderToday(); renderAll(); showTab(tab); } catch (e) { /* 出错也不影响软件其它部分 */ }
})();
