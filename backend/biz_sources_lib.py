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
        rk = "、".join(r.replace("#", "第 ") + " 名" for r in (f.get("ranks") or [])[:2])
        out.append({"id": f["id"], "name": f["name"], "kind": "site", "url": f["url"], "home": f["url"], "portal": True,
                    "group": "firm", "w": int(f.get("w") or 1), "country": f.get("country", ""),
                    "desc": " · ".join(x for x in (sub.split("/")[-1], f.get("country", ""), f.get("tier", ""), rk) if x),
                    "hint": f.get("hint") or [], "lib": True})
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
    for f in firms()[1]:                                  # v180：全球企业官网
        if f["url"].rstrip("/").lower() not in seen_url:
            seen_url.add(f["url"].rstrip("/").lower())
            out.append(f)
    out.sort(key=lambda s: (0 if s["kind"] == "site" else 1, -s["w"]))
    return out
