"""
biz_sources_lib.py — 市场雷达的「信息源推荐库」（v170 新增）

两部分：
  1. 人工挑的权威网站（约 300 个）：国务院和各部委、交易所、监管机构、各行业协会、
     中央和财经主流媒体、行业头部媒体、大公司官网新闻页、海外权威媒体和机构、各省市政府网站。
     网址按 2026 年整理；爬虫第一次抓时会验证，连续抓不成的会自动先关掉（不删，可以再打开）。
  2. 按行业地图自动生成的搜索关键词（约 1,400 个）：行业地图里的代表公司、每个细分行业、
     新兴赛道，以及每个细分行业的关键词（产品、技术、品牌）。去新闻搜索引擎搜最新报道。

权重 1～5（5 最高）：决定多久抓一次。5、4 每轮都抓；3 隔几轮抓一次；2、1 更少（见 biz_crawler._due）。
  5：国家级权威发布（国务院、部委、央行、交易所）和最快的财经快讯
  4：主流财经媒体、行业协会、重要监管机构、头部公司官网
  3：行业头部媒体、海外权威媒体、代表公司的新闻搜索、新兴赛道
  2：细分行业搜索、地方政府网站、次一级媒体
  1：细分关键词（产品、技术、品牌）搜索
"""
import hashlib
import re

# 分组|权重|名字|网址|一句话
SITES = """
policy|5|国务院·政策|https://www.gov.cn/zhengce/|国务院文件、政策解读
policy|5|财政部|https://www.mof.gov.cn/|财政政策、预算、国债
policy|5|国家金融监督管理总局|https://www.nfra.gov.cn/|银行保险监管政策
policy|5|海关总署|http://www.customs.gov.cn/|进出口数据和海关政策
policy|5|国家外汇管理局|https://www.safe.gov.cn/|外汇政策和国际收支数据
policy|5|国务院国资委|http://www.sasac.gov.cn/|央企动态和国企改革
policy|5|国家市场监督管理总局|https://www.samr.gov.cn/|市场监管、反垄断、质量
policy|5|科学技术部|https://www.most.gov.cn/|科技政策和重大项目
policy|5|国家能源局|https://www.nea.gov.cn/|能源政策和电力、油气数据
policy|5|国家税务总局|https://www.chinatax.gov.cn/|税收政策
policy|5|上海证券交易所|https://www.sse.com.cn/|上交所公告、规则、上市动态
policy|5|深圳证券交易所|https://www.szse.cn/|深交所公告、规则、上市动态
policy|5|北京证券交易所|https://www.bse.cn/|北交所公告和动态
policy|4|农业农村部|http://www.moa.gov.cn/|农业政策、农产品价格
policy|4|交通运输部|https://www.mot.gov.cn/|交通政策和运输数据
policy|4|住房和城乡建设部|https://www.mohurd.gov.cn/|楼市和城建政策
policy|4|生态环境部|https://www.mee.gov.cn/|环保政策、双碳
policy|4|自然资源部|https://www.mnr.gov.cn/|土地、矿产资源政策
policy|4|人力资源和社会保障部|http://www.mohrss.gov.cn/|就业、社保政策
policy|4|教育部|http://www.moe.gov.cn/|教育政策
policy|4|国家卫生健康委|http://www.nhc.gov.cn/|卫生健康政策
policy|4|国家药品监督管理局|https://www.nmpa.gov.cn/|药品、器械审批
policy|4|国家医疗保障局|http://www.nhsa.gov.cn/|医保目录、集采
policy|4|国家网信办|http://www.cac.gov.cn/|互联网、数据、AI 监管
policy|4|国家知识产权局|https://www.cnipa.gov.cn/|专利和知识产权
policy|4|中国民用航空局|http://www.caac.gov.cn/|民航和低空政策
policy|4|国家铁路局|https://www.nra.gov.cn/|铁路政策
policy|4|国家邮政局|https://www.spb.gov.cn/|快递物流数据
policy|4|文化和旅游部|https://www.mct.gov.cn/|文旅政策和数据
policy|4|国家数据局|https://www.nda.gov.cn/|数据要素政策
policy|4|国家广播电视总局|https://www.nrta.gov.cn/|广电、网络视听、短剧
policy|4|应急管理部|https://www.mem.gov.cn/|安全生产
policy|4|国家粮食和物资储备局|http://www.lswz.gov.cn/|粮食和储备
policy|4|水利部|http://www.mwr.gov.cn/|水利建设
policy|4|民政部|https://www.mca.gov.cn/|养老和社会服务
policy|4|国家航天局|https://www.cnsa.gov.cn/|航天政策和任务
policy|4|中国人大网|http://www.npc.gov.cn/|法律法规
policy|4|上海期货交易所|https://www.shfe.com.cn/|期货规则和行情动态
policy|4|大连商品交易所|http://www.dce.com.cn/|期货规则和动态
policy|4|郑州商品交易所|http://www.czce.com.cn/|期货规则和动态
policy|4|中国金融期货交易所|http://www.cffex.com.cn/|股指、国债期货
policy|4|广州期货交易所|http://www.gfex.com.cn/|新能源金属期货
policy|4|香港交易所|https://www.hkex.com.hk/|港股上市和规则
policy|4|中国证券业协会|https://www.sac.net.cn/|券商行业数据
policy|4|中国证券投资基金业协会|https://www.amac.org.cn/|基金行业数据
policy|4|中国银行业协会|https://www.china-cba.net/|银行业动态
policy|4|中国保险行业协会|http://www.iachina.cn/|保险业动态
policy|4|中国外汇交易中心|https://www.chinamoney.com.cn/|利率、汇率、债券市场
policy|4|中国信息通信研究院|http://www.caict.ac.cn/|ICT 行业研究和白皮书
policy|4|国务院发展研究中心|https://www.drc.gov.cn/|宏观经济研究
policy|4|中国物流与采购联合会|http://www.chinawuliu.com.cn/|PMI 和物流数据
policy|4|中国汽车工业协会|http://www.caam.org.cn/|汽车产销数据
policy|4|乘用车市场信息联席会|http://www.cpcaauto.com/|乘用车零售数据
policy|4|中国钢铁工业协会|http://www.chinaisa.org.cn/|钢铁产量和价格
policy|4|中国有色金属工业协会|https://www.chinania.org.cn/|有色金属行业
policy|4|中国石油和化学工业联合会|http://www.cpcif.org.cn/|化工行业
policy|4|中国半导体行业协会|https://web.csia.net.cn/|半导体行业
policy|4|中国光伏行业协会|http://www.chinapv.org.cn/|光伏行业
policy|4|中国电力企业联合会|https://www.cec.org.cn/|电力供需数据
policy|4|中国连锁经营协会|http://www.ccfa.org.cn/|零售连锁
policy|3|中国社会科学院|http://www.cass.cn/|经济社会研究
policy|3|中国家用电器协会|http://www.cheaa.org/|家电行业
policy|2|北京市政府|https://www.beijing.gov.cn/|北京政策
policy|2|上海市政府|https://www.shanghai.gov.cn/|上海政策
policy|2|天津市政府|https://www.tj.gov.cn/|天津政策
policy|2|重庆市政府|https://www.cq.gov.cn/|重庆政策
policy|2|河北省政府|http://www.hebei.gov.cn/|河北政策
policy|2|山西省政府|http://www.shanxi.gov.cn/|山西政策
policy|2|内蒙古自治区政府|https://www.nmg.gov.cn/|内蒙古政策
policy|2|辽宁省政府|https://www.ln.gov.cn/|辽宁政策
policy|2|吉林省政府|http://www.jl.gov.cn/|吉林政策
policy|2|黑龙江省政府|https://www.hlj.gov.cn/|黑龙江政策
policy|2|江苏省政府|http://www.jiangsu.gov.cn/|江苏政策
policy|2|浙江省政府|https://www.zj.gov.cn/|浙江政策
policy|2|安徽省政府|https://www.ah.gov.cn/|安徽政策
policy|2|福建省政府|http://www.fujian.gov.cn/|福建政策
policy|2|江西省政府|http://www.jiangxi.gov.cn/|江西政策
policy|2|山东省政府|http://www.shandong.gov.cn/|山东政策
policy|2|河南省政府|https://www.henan.gov.cn/|河南政策
policy|2|湖北省政府|https://www.hubei.gov.cn/|湖北政策
policy|2|湖南省政府|http://www.hunan.gov.cn/|湖南政策
policy|2|广东省政府|http://www.gd.gov.cn/|广东政策
policy|2|广西壮族自治区政府|http://www.gxzf.gov.cn/|广西政策
policy|2|海南省政府|https://www.hainan.gov.cn/|海南政策（自贸港）
policy|2|四川省政府|https://www.sc.gov.cn/|四川政策
policy|2|贵州省政府|https://www.guizhou.gov.cn/|贵州政策
policy|2|云南省政府|https://www.yn.gov.cn/|云南政策
policy|2|西藏自治区政府|http://www.xizang.gov.cn/|西藏政策
policy|2|陕西省政府|http://www.shaanxi.gov.cn/|陕西政策
policy|2|甘肃省政府|http://www.gansu.gov.cn/|甘肃政策
policy|2|青海省政府|http://www.qinghai.gov.cn/|青海政策
policy|2|宁夏回族自治区政府|https://www.nx.gov.cn/|宁夏政策
policy|2|新疆维吾尔自治区政府|http://www.xinjiang.gov.cn/|新疆政策
policy|2|深圳市政府|http://www.sz.gov.cn/|深圳政策
policy|2|广州市政府|https://www.gz.gov.cn/|广州政策
policy|2|杭州市政府|https://www.hangzhou.gov.cn/|杭州政策
policy|2|成都市政府|https://www.chengdu.gov.cn/|成都政策
policy|2|武汉市政府|https://www.wuhan.gov.cn/|武汉政策
policy|2|苏州市政府|https://www.suzhou.gov.cn/|苏州政策
policy|2|南京市政府|https://www.nanjing.gov.cn/|南京政策
policy|2|西安市政府|http://www.xa.gov.cn/|西安政策
policy|2|合肥市政府|https://www.hefei.gov.cn/|合肥政策
policy|2|青岛市政府|http://www.qingdao.gov.cn/|青岛政策
policy|2|宁波市政府|http://www.ningbo.gov.cn/|宁波政策
policy|2|厦门市政府|https://www.xm.gov.cn/|厦门政策
news|5|新华网·财经|http://www.news.cn/fortune/|新华社财经报道
news|5|人民网·财经|http://finance.people.com.cn/|人民日报财经
news|5|央视网·经济|https://jingji.cctv.com/|央视经济新闻
news|5|中国经济网|http://www.ce.cn/|经济日报社
news|5|上海证券报|https://www.cnstock.com/|证券市场权威报道
news|5|证券日报|http://www.zqrb.cn/|证券市场报道
news|5|财新网|https://www.caixin.com/|深度财经调查
news|4|中国新闻网·财经|https://www.chinanews.com.cn/cj/|中新社财经
news|4|光明网·经济|https://economy.gmw.cn/|光明日报经济
news|4|中国网·财经|http://finance.china.com.cn/|中国网财经
news|4|中国日报·财经|https://caijing.chinadaily.com.cn/|中国日报财经
news|4|环球网·财经|https://finance.huanqiu.com/|环球时报财经
news|4|中国金融新闻网|https://www.financialnews.com.cn/|金融时报（人民银行主管）
news|4|中国基金报|https://www.chnfund.com/|基金和资本市场
news|4|中国经营报|http://www.cb.com.cn/|企业经营报道
news|4|华夏时报|https://www.chinatimes.net.cn/|财经和产业报道
news|4|财经网|https://www.caijing.com.cn/|《财经》杂志
news|4|凤凰网·财经|https://finance.ifeng.com/|综合财经
news|4|网易·财经|https://money.163.com/|综合财经
news|4|东方财富网|https://finance.eastmoney.com/|市场资讯和公司公告
news|4|和讯网|https://news.hexun.com/|财经资讯
news|4|金融界|https://finance.jrj.com.cn/|财经资讯
news|4|格隆汇|https://www.gelonghui.com/|港美股和公司快讯
news|4|智通财经|https://www.zhitongcaijing.com/|港股和公司快讯
news|4|新京报·财经|https://www.bjnews.com.cn/financial|新京报财经
news|4|北京商报|https://www.bbtnews.com.cn/|商业和消费报道
news|4|南方财经全媒体|https://www.sfccn.com/|南方财经
news|3|中金在线|https://news.cnfol.com/|财经资讯
news|3|证券之星|https://www.stockstar.com/|股市资讯
news|3|时代财经|https://www.tfcaijing.com/|公司和产业报道
news|3|蓝鲸财经|https://www.lanjinger.com/|公司和产业报道
news|3|中国银行保险报|http://www.cbimc.cn/|银行保险业
news|3|亿欧|https://www.iyiou.com/|产业科技
news|3|创业邦|https://www.cyzone.cn/|创投
news|3|品玩|https://www.pingwest.com/|科技公司
news|3|极客公园|https://www.geekpark.net/|科技产品
news|3|爱范儿|https://www.ifanr.com/|科技消费
news|3|DoNews|https://www.donews.com/|互联网公司
news|3|新浪科技|https://tech.sina.com.cn/|科技新闻
news|3|网易科技|https://tech.163.com/|科技新闻
news|3|凤凰网科技|https://tech.ifeng.com/|科技新闻
news|3|快科技（驱动之家）|https://news.mydrivers.com/|科技硬件
news|3|cnBeta|https://www.cnbeta.com.tw/|科技快讯
corp|4|宁德时代|https://www.catl.com/news/|宁德时代官方新闻
corp|4|比亚迪|https://www.byd.com/cn/news|比亚迪官方新闻
corp|4|腾讯|https://www.tencent.com/zh-cn/media/news.html|腾讯官方新闻
corp|4|阿里巴巴集团|https://www.alibabagroup.com/news|阿里巴巴官方新闻
corp|4|台积电|https://pr.tsmc.com/|台积电新闻稿
corp|4|英特尔|https://www.intel.com/content/www/us/en/newsroom/home.html|Intel Newsroom
corp|4|AMD|https://www.amd.com/en/newsroom.html|AMD Newsroom
corp|4|特斯拉|https://www.tesla.com/blog|Tesla 博客
corp|4|Google DeepMind|https://deepmind.google/discover/blog/|DeepMind 博客
corp|3|百度|https://home.baidu.com/home/index/news|百度新闻中心
corp|3|中兴通讯|https://www.zte.com.cn/china/about/news.html|中兴新闻
corp|3|联想|https://news.lenovo.com/|联想新闻
corp|3|中国移动|https://www.10086.cn/aboutus/news/|中国移动新闻
corp|3|国家电网|http://www.sgcc.com.cn/|国家电网新闻
corp|3|中国石油|http://www.cnpc.com.cn/|中石油新闻
corp|3|中国石化|http://www.sinopecgroup.com/|中石化新闻
corp|3|中国中车|https://www.crrcgc.cc/|中车新闻
corp|3|中国商飞|http://www.comac.cc/|商飞新闻
corp|3|中国航天科技集团|http://www.spacechina.com/|航天科技新闻
corp|3|中芯国际|https://www.smics.com/|中芯国际公告和新闻
corp|3|高通|https://www.qualcomm.com/news|Qualcomm 新闻
corp|3|Arm|https://newsroom.arm.com/|Arm 新闻
corp|3|IBM|https://newsroom.ibm.com/|IBM 新闻
corp|3|索尼|https://www.sony.com/en/SonyInfo/News/|Sony 新闻
corp|3|丰田|https://global.toyota/en/newsroom/|Toyota 新闻
corp|3|Hugging Face|https://huggingface.co/blog|开源 AI 动态
media|4|半导体行业观察|http://www.semiinsights.com/|半导体产业
media|4|我的钢铁网|https://news.mysteel.com/|钢铁和大宗商品
media|4|上海有色网|https://news.smm.cn/|有色金属和新能源材料
media|4|中国汽车报|http://www.cnautonews.com/|汽车产业
media|4|中国电子报|http://www.cena.com.cn/|电子信息产业
media|4|C114 通信网|http://www.c114.com.cn/|通信产业
media|4|金十数据|https://www.jin10.com/|全球市场快讯
media|3|芯智讯|https://www.icsmart.cn/|芯片产业
media|3|电子发烧友|https://www.elecfans.com/|电子产业
media|3|OFweek 维科网|https://www.ofweek.com/|高科技产业
media|3|OFweek 机器人|https://robot.ofweek.com/|机器人产业
media|3|高工锂电|https://www.gg-lb.com/|锂电产业
media|3|索比光伏网|https://news.solarbe.com/|光伏产业
media|3|中国能源网|https://www.china5e.com/|能源产业
media|3|中国储能网|http://www.escn.com.cn/|储能产业
media|3|北极星环保网|https://huanbao.bjx.com.cn/|环保产业
media|3|中国有色网|https://www.cnmn.com.cn/|有色金属
media|3|中国煤炭网|http://www.ccoalnews.com/|煤炭行业
media|3|汽车之家·资讯|https://www.autohome.com.cn/news/|汽车新闻
media|3|新浪汽车|https://auto.sina.com.cn/|汽车新闻
media|3|中国民航网|http://www.caacnews.com.cn/|民航产业
media|3|民航资源网|http://news.carnoc.com/|航空产业
media|3|米内网|https://www.menet.com.cn/|医药市场
media|3|生物谷|https://news.bioon.com/|生物医药
media|3|药智网|https://news.yaozh.com/|医药研发和审批
media|3|丁香园|https://www.dxy.cn/|医疗健康
media|3|中国房地产网|http://www.china-crb.cn/|房地产
media|3|乐居财经|https://news.leju.com/|房地产
media|3|中国水泥网|https://www.ccement.com/|建材
media|3|农民日报|https://www.farmer.com.cn/|农业农村
media|3|食品伙伴网|https://news.foodmate.net/|食品行业
media|3|糖酒快讯|https://www.tjkx.com/|酒类和食品流通
media|3|环球旅讯|https://www.traveldaily.cn/|旅游产业
media|3|GameLook|http://www.gamelook.com.cn/|游戏产业
media|3|芥末堆|https://www.jiemodui.com/|教育产业
media|3|电商报|https://www.dsb.cn/|电商
media|3|网经社|http://www.100ec.cn/|电商和数字经济
media|3|通信世界网|http://www.cww.net.cn/|通信产业
media|3|InfoQ|https://www.infoq.cn/|软件和云
media|3|中国军网|http://www.81.cn/|国防军工
media|3|红餐网|https://www.canyin88.com/|餐饮
media|3|中国家电网|http://www.cheaa.com/|家电
global|4|Reuters 商业|https://www.reuters.com/business/|路透社商业新闻
global|4|Bloomberg|https://www.bloomberg.com/|彭博
global|4|Financial Times|https://www.ft.com/|金融时报
global|4|The Wall Street Journal|https://www.wsj.com/|华尔街日报
global|4|CNBC 国际|https://www.cnbc.com/world/|CNBC 国际
global|4|美联储|https://www.federalreserve.gov/newsevents.htm|美联储新闻和讲话
global|4|欧洲央行|https://www.ecb.europa.eu/press/html/index.en.html|欧央行新闻
global|4|IMF|https://www.imf.org/en/News|国际货币基金组织
global|4|美国证监会|https://www.sec.gov/newsroom/press-releases|SEC 新闻稿
global|3|The Economist|https://www.economist.com/|经济学人
global|3|BBC 商业|https://www.bbc.com/business|BBC 商业
global|3|日经亚洲|https://asia.nikkei.com/|Nikkei Asia
global|3|南华早报·商业|https://www.scmp.com/business|SCMP 商业
global|3|财新国际|https://www.caixinglobal.com/|Caixin Global
global|3|Wired|https://www.wired.com/|科技
global|3|MIT 科技评论|https://www.technologyreview.com/|前沿科技
global|3|VentureBeat|https://venturebeat.com/|AI 和企业科技
global|3|Axios|https://www.axios.com/|商业和科技快讯
global|3|Fortune|https://fortune.com/|商业
global|3|Forbes|https://www.forbes.com/|商业
global|3|Business Insider|https://www.businessinsider.com/|商业
global|3|Electrek|https://electrek.co/|电动车和能源
global|3|InsideEVs|https://insideevs.com/|电动车
global|3|Tom's Hardware|https://www.tomshardware.com/|硬件和芯片
global|3|EE Times|https://www.eetimes.com/|电子产业
global|3|DigiTimes|https://www.digitimes.com/|台湾供应链
global|3|SpaceNews|https://spacenews.com/|航天产业
global|3|Space.com|https://www.space.com/|航天
global|3|Fierce Biotech|https://www.fiercebiotech.com/|生物科技
global|3|Endpoints News|https://endpts.com/|生物医药
global|3|STAT|https://www.statnews.com/|医疗健康
global|3|pv magazine|https://www.pv-magazine.com/|光伏
global|3|Energy-Storage.news|https://www.energy-storage.news/|储能
global|3|Mining.com|https://www.mining.com/|矿业
global|3|OilPrice|https://oilprice.com/|石油
global|3|世界银行|https://www.worldbank.org/en/news|World Bank
global|3|WTO|https://www.wto.org/english/news_e/news_e.htm|世界贸易组织
global|3|美国劳工统计局|https://www.bls.gov/|就业和通胀数据
global|3|韩联社英文|https://en.yna.co.kr/|韩国新闻
global|3|Rest of World|https://restofworld.org/|新兴市场科技
global|3|The Register|https://www.theregister.com/|企业 IT
global|3|Engadget|https://www.engadget.com/|消费科技
global|3|ZDNET|https://www.zdnet.com/|企业科技
global|2|9to5Mac|https://9to5mac.com/|苹果生态
global|2|MacRumors|https://www.macrumors.com/|苹果生态
"""


# v181：GDP 前 100 的国家（世界银行 2023 年数据，按 GDP 从高到低）和它们的官方媒体
GDP_RANK = ['USA', 'CHN', 'DEU', 'JPN', 'IND', 'GBR', 'FRA', 'ITA', 'BRA', 'CAN', 'RUS', 'MEX', 'AUS', 'KOR', 'ESP', 'IDN', 'NLD', 'TUR', 'SAU', 'CHE', 'POL', 'ARG', 'BEL', 'SWE', 'IRL', 'AUT', 'THA', 'ISR', 'ARE', 'SGP', 'NOR', 'BGD', 'PHL', 'VNM', 'DNK', 'IRN', 'MYS', 'EGY', 'HKG', 'ZAF', 'COL', 'NGA', 'ROU', 'PAK', 'CHL', 'CZE', 'FIN', 'PRT', 'PER', 'KAZ', 'NZL', 'IRQ', 'DZA', 'GRC', 'QAT', 'HUN', 'UKR', 'ETH', 'KWT', 'MAR', 'SVK', 'DOM', 'ECU', 'PRI', 'SDN', 'OMN', 'KEN', 'GTM', 'BGR', 'UZB', 'CRI', 'LUX', 'AGO', 'LKA', 'PAN', 'HRV', 'TZA', 'CIV', 'LTU', 'URY', 'GHA', 'SRB', 'AZE', 'BLR', 'SVN', 'COD', 'MMR', 'TKM', 'JOR', 'LBY', 'UGA', 'TUN', 'CMR', 'MAC', 'BOL', 'LVA', 'BHR', 'PRY', 'NPL', 'EST']

# 国家代码|国家|名字|网址|一句话：国家通讯社、公共广播电视、政府新闻；有中文版的也加了
MEDIA = """
USA|美国|美联社 AP|https://apnews.com/|美国最大的通讯社
USA|美国|美国之音|https://www.voanews.com/|美国官方国际广播
USA|美国|美国之音中文|https://www.voachinese.com/|美国之音中文网
USA|美国|NPR 新闻|https://www.npr.org/sections/news/|美国全国公共广播
USA|美国|PBS NewsHour|https://www.pbs.org/newshour/|美国公共电视新闻
CHN|中国|新华网|https://www.news.cn/|新华社
CHN|中国|新华社英文|https://english.news.cn/|新华社英文版
CHN|中国|人民网|http://www.people.com.cn/|人民日报
CHN|中国|央视新闻|https://news.cctv.com/|中央广播电视总台
CHN|中国|中国新闻网|https://www.chinanews.com.cn/|中国新闻社
CHN|中国|中国日报|https://www.chinadaily.com.cn/|中国日报英文版
CHN|中国|CGTN|https://www.cgtn.com/|中国国际电视台
DEU|德国|德国之声中文|https://www.dw.com/zh/|德国官方国际广播中文
DEU|德国|DW English|https://www.dw.com/en/|德国之声英文
DEU|德国|tagesschau|https://www.tagesschau.de/|德国公共广播 ARD 新闻
DEU|德国|ZDFheute|https://www.zdf.de/nachrichten|德国电视二台新闻
JPN|日本|NHK 中文|https://www3.nhk.or.jp/nhkworld/zh/news/|日本放送协会中文新闻
JPN|日本|NHK World|https://www3.nhk.or.jp/nhkworld/en/news/|日本放送协会英文新闻
JPN|日本|NHK ニュース|https://www3.nhk.or.jp/news/|日本放送协会日文新闻
JPN|日本|共同网中文|https://china.kyodonews.net/|日本共同社中文
JPN|日本|Kyodo News|https://english.kyodonews.net/|日本共同社英文
IND|印度|印度政府新闻局 PIB|https://pib.gov.in/|印度政府新闻发布
IND|印度|DD News|https://ddnews.gov.in/|印度国家电视台新闻
IND|印度|全印广播新闻|https://newsonair.gov.in/|印度国家广播
IND|印度|PTI|https://www.ptinews.com/|印度报业托拉斯（通讯社）
GBR|英国|BBC News|https://www.bbc.com/news|英国广播公司
GBR|英国|BBC 中文|https://www.bbc.com/zhongwen/simp|英国广播公司中文
GBR|英国|GOV.UK 新闻|https://www.gov.uk/search/news-and-communications|英国政府新闻
FRA|法国|法新社|https://www.afp.com/en|法国新闻社
FRA|法国|France 24|https://www.france24.com/en/|法国国际电视台
FRA|法国|法广中文|https://www.rfi.fr/cn/|法国国际广播电台中文
FRA|法国|franceinfo|https://www.francetvinfo.fr/|法国公共广播新闻
ITA|意大利|ANSA English|https://www.ansa.it/english/|意大利安莎社英文
ITA|意大利|ANSA|https://www.ansa.it/|意大利安莎社
ITA|意大利|RaiNews|https://www.rainews.it/|意大利广播电视公司新闻
BRA|巴西|Agência Brasil|https://agenciabrasil.ebc.com.br/|巴西国家通讯社
BRA|巴西|Agência Gov|https://agenciagov.ebc.com.br/|巴西政府新闻
CAN|加拿大|CBC News|https://www.cbc.ca/news|加拿大广播公司
CAN|加拿大|Radio-Canada Info|https://ici.radio-canada.ca/info|加拿大广播公司法语新闻
RUS|俄罗斯|塔斯社 TASS|https://tass.com/|俄罗斯塔斯社英文
RUS|俄罗斯|ТАСС|https://tass.ru/|俄罗斯塔斯社俄文
RUS|俄罗斯|卫星通讯社中文|https://sputniknews.cn/|俄罗斯卫星通讯社中文
RUS|俄罗斯|РИА Новости|https://ria.ru/|俄新社
MEX|墨西哥|Once Noticias|https://oncenoticias.digital/|墨西哥公共电视台新闻
MEX|墨西哥|墨西哥总统府新闻|https://www.gob.mx/presidencia/es/archivo/prensa|墨西哥政府新闻稿
AUS|澳大利亚|ABC News|https://www.abc.net.au/news|澳大利亚广播公司
AUS|澳大利亚|ABC 中文|https://www.abc.net.au/chinese|澳大利亚广播公司中文
AUS|澳大利亚|SBS News|https://www.sbs.com.au/news|澳大利亚特别广播服务公司
AUS|澳大利亚|SBS 中文|https://www.sbs.com.au/language/chinese/zh-hans|澳大利亚特别广播服务公司中文
KOR|韩国|韩联社中文|https://cn.yna.co.kr/|韩国联合通讯社中文
KOR|韩国|Yonhap News|https://en.yna.co.kr/|韩国联合通讯社英文
KOR|韩国|KBS 中文|https://world.kbs.co.kr/service/index.htm?lang=c|韩国放送公社中文
KOR|韩国|Korea.net|https://www.korea.net/|韩国政府网
ESP|西班牙|EFE|https://efe.com/|西班牙埃菲社
ESP|西班牙|RTVE Noticias|https://www.rtve.es/noticias/|西班牙广播电视台新闻
IDN|印尼|ANTARA English|https://en.antaranews.com/|印尼安塔拉通讯社英文
IDN|印尼|ANTARA|https://www.antaranews.com/|印尼安塔拉通讯社
NLD|荷兰|NOS|https://nos.nl/|荷兰公共广播新闻
NLD|荷兰|Government.nl|https://www.government.nl/latest/news|荷兰政府新闻
TUR|土耳其|阿纳多卢通讯社|https://www.aa.com.tr/en|土耳其官方通讯社
TUR|土耳其|TRT World|https://www.trtworld.com/|土耳其国际电视台
TUR|土耳其|TRT 中文|https://www.trt.net.tr/chinese/|土耳其广播电视台中文
SAU|沙特|沙特通讯社 SPA|https://www.spa.gov.sa/en|沙特官方通讯社
SAU|沙特|Al Arabiya|https://english.alarabiya.net/|阿拉伯卫视英文
CHE|瑞士|瑞士资讯中文|https://www.swissinfo.ch/chi/|瑞士广播公司国际部中文
CHE|瑞士|SWI swissinfo|https://www.swissinfo.ch/eng/|瑞士广播公司国际部英文
CHE|瑞士|SRF News|https://www.srf.ch/news|瑞士德语广播电视新闻
POL|波兰|PAP|https://www.pap.pl/en|波兰通讯社
POL|波兰|TVP Info|https://www.tvp.info/|波兰电视台新闻
ARG|阿根廷|Argentina.gob.ar|https://www.argentina.gob.ar/noticias|阿根廷政府新闻
BEL|比利时|Belga News Agency|https://www.belganewsagency.eu/|比利时通讯社
BEL|比利时|VRT NWS|https://www.vrt.be/vrtnws/nl/|比利时荷语公共广播
BEL|比利时|RTBF Info|https://www.rtbf.be/info|比利时法语公共广播
SWE|瑞典|SVT Nyheter|https://www.svt.se/nyheter/|瑞典电视台新闻
SWE|瑞典|Ekot|https://sverigesradio.se/ekot|瑞典广播电台新闻
IRL|爱尔兰|RTÉ News|https://www.rte.ie/news/|爱尔兰广播电视台
AUT|奥地利|ORF|https://orf.at/|奥地利广播公司
THA|泰国|泰国国家新闻局 NNT|https://thainews.prd.go.th/en/|泰国政府新闻
THA|泰国|Thai PBS World|https://www.thaipbsworld.com/|泰国公共电视英文
ISR|以色列|Kan|https://www.kan.org.il/|以色列公共广播
ARE|阿联酋|阿联酋通讯社 WAM|https://www.wam.ae/en|阿联酋官方通讯社
SGP|新加坡|CNA|https://www.channelnewsasia.com/|新加坡亚洲新闻台
SGP|新加坡|8视界|https://www.8world.com/|新加坡新传媒中文新闻
SGP|新加坡|联合早报|https://www.zaobao.com.sg/|新加坡中文大报
NOR|挪威|NRK|https://www.nrk.no/nyheter/|挪威广播公司
BGD|孟加拉国|BSS|https://www.bssnews.net/|孟加拉国家通讯社
PHL|菲律宾|PNA|https://www.pna.gov.ph/|菲律宾通讯社
PHL|菲律宾|PTV News|https://ptvnews.ph/|菲律宾国家电视台
VNM|越南|越通社中文|https://zh.vietnamplus.vn/|越南通讯社中文
VNM|越南|VietnamPlus|https://en.vietnamplus.vn/|越南通讯社英文
VNM|越南|VTV|https://vtv.vn/|越南国家电视台
DNK|丹麦|DR Nyheder|https://www.dr.dk/nyheder|丹麦广播公司
IRN|伊朗|IRNA English|https://en.irna.ir/|伊朗伊斯兰共和国通讯社
IRN|伊朗|Press TV|https://www.presstv.ir/|伊朗英语电视台
IRN|伊朗|今日伊朗中文|https://parstoday.ir/zh|伊朗广播电视中文
MYS|马来西亚|马新社|https://www.bernama.com/en/|马来西亚国家新闻社
MYS|马来西亚|马新社中文|https://www.bernama.com/zh/|马来西亚国家新闻社中文
EGY|埃及|Ahram Online|https://english.ahram.org.eg/|金字塔报英文
EGY|埃及|埃及国家信息服务处|https://www.sis.gov.eg/|埃及政府新闻
HKG|中国香港|香港电台新闻|https://news.rthk.hk/rthk/ch/|香港电台
HKG|中国香港|香港政府新闻网|https://www.news.gov.hk/chi/|香港特区政府新闻
HKG|中国香港|香港政府新闻公报|https://www.info.gov.hk/gia/|香港特区政府新闻稿
ZAF|南非|SABC News|https://www.sabcnews.com/|南非广播公司
ZAF|南非|SAnews|https://www.sanews.gov.za/|南非政府新闻社
COL|哥伦比亚|RTVC Noticias|https://www.rtvcnoticias.com/|哥伦比亚公共广播新闻
NGA|尼日利亚|尼日利亚通讯社 NAN|https://nannews.ng/|尼日利亚官方通讯社
NGA|尼日利亚|Voice of Nigeria|https://von.gov.ng/|尼日利亚之声
ROU|罗马尼亚|Agerpres|https://www.agerpres.ro/english|罗马尼亚国家通讯社
PAK|巴基斯坦|APP|https://www.app.com.pk/|巴基斯坦联合通讯社
PAK|巴基斯坦|Radio Pakistan|https://www.radio.gov.pk/|巴基斯坦国家广播
CHL|智利|24 Horas (TVN)|https://www.24horas.cl/|智利国家电视台新闻
CHL|智利|Gob.cl|https://www.gob.cl/noticias/|智利政府新闻
CZE|捷克|ČTK České noviny|https://www.ceskenoviny.cz/|捷克通讯社
CZE|捷克|ČT24|https://ct24.ceskatelevize.cz/|捷克电视台新闻
FIN|芬兰|Yle News|https://yle.fi/news|芬兰广播公司英文
FIN|芬兰|Yle Uutiset|https://yle.fi/uutiset|芬兰广播公司
PRT|葡萄牙|Lusa|https://www.lusa.pt/|葡萄牙通讯社
PRT|葡萄牙|RTP Notícias|https://www.rtp.pt/noticias/|葡萄牙广播电视台
PER|秘鲁|Andina|https://andina.pe/|秘鲁国家通讯社
PER|秘鲁|Andina English|https://andina.pe/ingles/|秘鲁国家通讯社英文
KAZ|哈萨克斯坦|Kazinform|https://en.inform.kz/|哈萨克斯坦国家通讯社
NZL|新西兰|RNZ|https://www.rnz.co.nz/news|新西兰广播电台
IRQ|伊拉克|INA|https://ina.iq/eng/|伊拉克通讯社
DZA|阿尔及利亚|APS|https://www.aps.dz/en/|阿尔及利亚通讯社
GRC|希腊|ERT News|https://www.ertnews.gr/|希腊广播电视台
GRC|希腊|AMNA|https://www.amna.gr/en|希腊雅典-马其顿通讯社
QAT|卡塔尔|卡塔尔通讯社 QNA|https://www.qna.org.qa/en|卡塔尔官方通讯社
QAT|卡塔尔|Al Jazeera|https://www.aljazeera.com/|半岛电视台英文
HUN|匈牙利|Híradó (MTI)|https://hirado.hu/|匈牙利通讯社和公共媒体
HUN|匈牙利|About Hungary|https://abouthungary.hu/|匈牙利政府新闻
UKR|乌克兰|Ukrinform|https://www.ukrinform.net/|乌克兰国家通讯社
UKR|乌克兰|Suspilne|https://suspilne.media/|乌克兰公共广播
ETH|埃塞俄比亚|ENA|https://www.ena.et/|埃塞俄比亚通讯社
KWT|科威特|科威特通讯社 KUNA|https://www.kuna.net.kw/|科威特官方通讯社
MAR|摩洛哥|MAP Express|https://www.mapexpress.ma/en/|摩洛哥通讯社
SVK|斯洛伐克|TASR|https://www.tasr.sk/|斯洛伐克通讯社
DOM|多米尼加|多米尼加总统府|https://presidencia.gob.do/noticias|多米尼加政府新闻
ECU|厄瓜多尔|厄瓜多尔政府传播|https://www.comunicacion.gob.ec/|厄瓜多尔政府新闻
PRI|波多黎各|波多黎各政府|https://www.pr.gov/|波多黎各政府
SDN|苏丹|SUNA|https://suna-sd.net/|苏丹通讯社
OMN|阿曼|阿曼通讯社 ONA|https://omannews.gov.om/|阿曼官方通讯社
KEN|肯尼亚|KBC|https://www.kbc.co.ke/|肯尼亚广播公司
KEN|肯尼亚|Kenya News Agency|https://www.kenyanews.go.ke/|肯尼亚通讯社
GTM|危地马拉|AGN|https://agn.gt/|危地马拉通讯社
BGR|保加利亚|BTA|https://www.bta.bg/en|保加利亚通讯社
BGR|保加利亚|BNT News|https://bntnews.bg/|保加利亚国家电视台
UZB|乌兹别克斯坦|UzA|https://uza.uz/en|乌兹别克斯坦国家通讯社
CRI|哥斯达黎加|哥斯达黎加总统府|https://www.presidencia.go.cr/|哥斯达黎加政府新闻
LUX|卢森堡|卢森堡政府新闻|https://gouvernement.lu/en/actualites.html|卢森堡政府
AGO|安哥拉|ANGOP|https://www.angop.ao/en/|安哥拉通讯社
LKA|斯里兰卡|Daily News|https://www.dailynews.lk/|斯里兰卡国营报纸
LKA|斯里兰卡|News.lk|https://www.news.lk/|斯里兰卡政府新闻
PAN|巴拿马|巴拿马总统府|https://www.presidencia.gob.pa/|巴拿马政府新闻
HRV|克罗地亚|HINA|https://www.hina.hr/|克罗地亚通讯社
HRV|克罗地亚|HRT Vijesti|https://vijesti.hrt.hr/|克罗地亚广播电视台
TZA|坦桑尼亚|Daily News Tanzania|https://dailynews.co.tz/|坦桑尼亚国营报纸
CIV|科特迪瓦|AIP|https://www.aip.ci/|科特迪瓦通讯社
CIV|科特迪瓦|RTI Info|https://www.rti.info/|科特迪瓦广播电视台
LTU|立陶宛|LRT English|https://www.lrt.lt/en|立陶宛广播电视台
LTU|立陶宛|ELTA|https://www.elta.lt/en|立陶宛通讯社
URY|乌拉圭|乌拉圭总统府|https://www.gub.uy/presidencia/comunicacion/noticias|乌拉圭政府新闻
GHA|加纳|GNA|https://gna.org.gh/|加纳通讯社
GHA|加纳|GBC|https://www.gbcghanaonline.com/|加纳广播公司
SRB|塞尔维亚|Tanjug|https://www.tanjug.rs/|塞尔维亚通讯社
SRB|塞尔维亚|RTS|https://www.rts.rs/|塞尔维亚广播电视台
AZE|阿塞拜疆|AZERTAC|https://azertag.az/en|阿塞拜疆国家通讯社
BLR|白俄罗斯|BelTA|https://eng.belta.by/|白俄罗斯通讯社英文
BLR|白俄罗斯|白俄通讯社中文|https://chn.belta.by/|白俄罗斯通讯社中文
SVN|斯洛文尼亚|STA|https://www.sta.si/|斯洛文尼亚通讯社
SVN|斯洛文尼亚|RTV SLO|https://www.rtvslo.si/|斯洛文尼亚广播电视台
COD|刚果（金）|ACP|https://acp.cd/|刚果（金）通讯社
COD|刚果（金）|Radio Okapi|https://www.radiookapi.net/|刚果（金）联合国电台
MMR|缅甸|Global New Light of Myanmar|https://www.gnlm.com.mm/|缅甸国营英文报纸
TKM|土库曼斯坦|TDH|https://tdh.gov.tm/en/|土库曼斯坦国家通讯社
JOR|约旦|Petra|https://petra.gov.jo/|约旦通讯社
JOR|约旦|Jordan Times|https://www.jordantimes.com/|约旦英文报纸
LBY|利比亚|LANA|https://lana.gov.ly/|利比亚通讯社
UGA|乌干达|New Vision|https://www.newvision.co.ug/|乌干达国营报纸
TUN|突尼斯|TAP|https://www.tap.info.tn/en|突尼斯通讯社
CMR|喀麦隆|CRTV|https://www.crtv.cm/|喀麦隆广播电视台
CMR|喀麦隆|Cameroon Tribune|https://www.cameroon-tribune.cm/|喀麦隆国营报纸
MAC|中国澳门|澳门新闻局|https://www.gcs.gov.mo/|澳门特区政府新闻局
MAC|中国澳门|澳广视新闻|https://www.tdm.com.mo/zh-hant/news-list|澳门广播电视
MAC|中国澳门|澳门日报|http://www.macaodaily.com/|澳门主流中文报纸
BOL|玻利维亚|ABI|https://abi.bo/|玻利维亚通讯社
LVA|拉脱维亚|LSM English|https://eng.lsm.lv/|拉脱维亚公共媒体
BHR|巴林|巴林通讯社 BNA|https://www.bna.bh/en/|巴林官方通讯社
PRY|巴拉圭|IP Paraguay|https://www.ip.gov.py/|巴拉圭通讯社
NPL|尼泊尔|RSS|https://rss.org.np/|尼泊尔国家通讯社
NPL|尼泊尔|The Rising Nepal|https://risingnepaldaily.com/|尼泊尔国营英文报纸
EST|爱沙尼亚|ERR News|https://news.err.ee/|爱沙尼亚公共广播
TWN|中国台湾|中央社|https://www.cna.com.tw/|台湾地区通讯社
"""


def media():
    """v181：GDP 前 100 国家的官方媒体。返回 (版本, [信息源])。权重按 GDP 排名：前 10 每轮都抓，11~30 每小时，31~60 约 3 小时，其余约 8 小时。"""
    rank = {c: i + 1 for i, c in enumerate(GDP_RANK)}
    out, seen = [], set()
    for ln in MEDIA.strip().splitlines():
        parts = [x.strip() for x in ln.split("|")]
        if len(parts) != 5:
            continue
        iso, country, name, url, desc = parts
        if url.rstrip("/").lower() in seen:
            continue
        seen.add(url.rstrip("/").lower())
        r = rank.get(iso, 25)                              # 不在世界银行名单里的（中国台湾）按 25 名算
        w = 4 if r <= 10 else 3 if r <= 30 else 2 if r <= 60 else 1
        out.append({"id": _sid("M", url), "name": name, "kind": "site", "url": url, "group": "govmedia", "w": w, "country": country,
                    "desc": "%s · %s" % (country + ("（GDP 第 %d）" % r if iso in rank else ""), desc), "hint": [], "lib": True})
    return 1, out


def firms():
    """v180：各行业全球前 100 家企业的官网（biz_firms.json，从 FinanceDatabase 的全球上市公司数据生成）。返回 (版本, [信息源])。"""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "biz_firms.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return 0, []
    out = []
    for f in d.get("firms", []):
        sub = f.get("sub", "")
        rk = "、".join(r.replace("#", "第 ") + " 名" for r in (f.get("ranks") or [])[:2]) + ("（每天看一次）" if f.get("deep") else "")
        out.append({"id": f["id"], "name": f["name"], "kind": "site", "url": f["url"], "home": f["url"], "portal": True,
                    "group": "firm", "w": int(f.get("w") or 1), "country": f.get("country", ""),
                    "desc": " · ".join(x for x in (sub.split("/")[-1], f.get("country", ""), f.get("tier", ""), rk) if x),
                    "hint": f.get("hint") or [], "lib": True, **({"deep": True} if f.get("deep") else {})})
    return int(d.get("v") or 1), out


def _sid(prefix, text):
    return prefix + hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def library(tax=None):
    """返回推荐库：[{id, name, kind, url|kw, group, w, desc, hint, lib}]（网站在前，按权重从高到低）"""
    out, seen_url, seen_kw = [], set(), set()
    for ln in SITES.strip().splitlines():
        parts = ln.split("|")
        if len(parts) != 5:
            continue
        grp, w, name, url, desc = [p.strip() for p in parts]
        key = url.rstrip("/").lower()
        if key in seen_url:
            continue
        seen_url.add(key)
        out.append({"id": _sid("L", url), "name": name, "kind": "site", "url": url, "group": grp, "w": int(w),
                    "desc": desc, "hint": [], "lib": True})
    if tax is None:
        try:
            import biz_industries as BI
            tax = BI.taxonomy()
        except Exception:
            tax = None
    if tax:
        def kw(word, grp, w, desc, hint):
            k = re.sub(r"\s+", " ", word or "").strip()
            if len(k) < 2 or k.lower() in seen_kw:
                return
            seen_kw.add(k.lower())
            out.append({"id": _sid("K", k), "name": k, "kind": "kw", "kw": k, "group": grp, "w": w, "desc": desc,
                        "hint": hint, "lib": True})
        # 代表公司（权重 3）
        for ind in tax.get("industries", []):
            for x in ind.get("subs", []):
                for c in re.split(r"[、,，/]", x.get("co") or ""):
                    kw(c, "corpkw", 3, "%s 的代表公司" % x.get("name", ""), [x["id"]])
        # 新兴赛道（权重 3）
        for t in tax.get("tracks", []):
            kw(t.get("name"), "indkw", 3, "新兴赛道", [t["id"]])
        # 一级行业（权重 2）、细分行业（权重 2）
        for ind in tax.get("industries", []):
            kw(ind.get("name") + "行业" if not ind.get("name", "").endswith("业") else ind.get("name"), "indkw", 2, "一级行业", [])
            for x in ind.get("subs", []):
                kw(x.get("name"), "indkw", 2, "%s · 细分行业" % ind.get("name", ""), [x["id"]])
        # 细分行业 / 赛道的关键词（权重 1）
        for ind in tax.get("industries", []):
            for x in ind.get("subs", []):
                for k in (x.get("kw") or "").split():
                    kw(k, "indkw", 1, "%s 的关键词" % x.get("name", ""), [x["id"]])
        for t in tax.get("tracks", []):
            for k in (t.get("kw") or "").split():
                kw(k, "indkw", 1, "%s 的关键词" % t.get("name", ""), [t["id"]])
    for f in media()[1] + firms()[1]:                     # v181：各国官方媒体；v180：全球企业官网
        if f["url"].rstrip("/").lower() not in seen_url:
            seen_url.add(f["url"].rstrip("/").lower())
            out.append(f)
    out.sort(key=lambda s: (0 if s["kind"] == "site" else 1, -s["w"]))
    return out
