"""超能小助 · 真实市场 · 全世界的交易平台目录（v199 新增）

「真实市场」要看的是钱：谁在买、买多少、什么价。这里把全世界能看到真实成交、报价、采购、下载、众筹的平台列出来，
按地区和类型分好，写清楚软件能不能自动抓：
  auto   软件已经会自动抓（交易平台抓取里有它这一行）
  login  你登录后软件会自动抓
  key    要去平台申请一个免费的钥匙（API Key）才能取，软件以后可以接
  paid   要付费的数据服务（数字最准，但要钱）
  manual 反爬很严或只能在 App 里看：先自己打开看，软件暂时不抓
"""

R = {"cn": "中国", "na": "北美", "eu": "欧洲", "ru": "俄罗斯 / 中亚", "jk": "日本 / 韩国", "sea": "东南亚", "sa": "南亚", "latam": "拉美",
     "mea": "中东 / 非洲", "oc": "大洋洲", "global": "全球 / 跨境"}
A = {"auto": "自动抓", "login": "登录后自动抓", "key": "要申请免费钥匙", "paid": "付费数据", "manual": "只能自己看"}
WHY = {"key": "平台有免费的官方接口，要你去申请一个钥匙，软件以后可以接上", "paid": "数据要付费才能看",
       "manual": "反爬很严、数字被加密，或者只能在手机 App 里看：点名字自己去看"}
CAT_REGION = {"cn": "cn", "na": "na", "eu": "eu", "jp": "jk", "sa": "sa", "sea": "sea", "latam": "latam", "mea": "mea", "b2b": "global", "svc": "global", "gov": "global"}

# (名字, 地区, 国家 / 地方, 类型, 网址, 能看到什么, 软件能不能抓, 软件里的平台 key)
L = [
    # ── 中国 ──
    ("淘宝 / 天猫", "cn", "中国", "零售电商", "https://www.taobao.com/", "全国最大的网购平台：价格带、「多少人付款」", "login", "tb"),
    ("京东", "cn", "中国", "零售电商", "https://www.jd.com/", "零售价、评价数（≈ 销量）", "login", "jd"),
    ("拼多多", "cn", "中国", "零售电商", "https://www.pinduoduo.com/", "下沉市场价格带、「已拼多少件」", "login", "pdd"),
    ("1688", "cn", "中国", "批发 / B2B", "https://www.1688.com/", "工厂批发价、成交件数", "login", "b2b"),
    ("义乌购", "cn", "中国", "批发 / B2B", "https://www.yiwugo.com/", "义乌商贸城商户的批发价", "auto", "ywg"),
    ("苏宁易购", "cn", "中国", "零售电商", "https://www.suning.com/", "家电数码的标价、评价数", "auto", "sn"),
    ("什么值得买", "cn", "中国", "比价 / 到手价", "https://www.smzdm.com/", "消费者真实下单的到手价", "auto", "smzdm"),
    ("猪八戒网", "cn", "中国", "服务接单", "https://www.zbj.com/", "服务报价、成交笔数", "auto", "zbj"),
    ("中国政府采购网", "cn", "中国", "政府采购", "http://www.ccgp.gov.cn/", "政府、学校、医院的采购和中标金额", "auto", "ccgp"),
    ("苹果应用商店（中国区）", "cn", "中国", "应用商店", "https://apps.apple.com/cn/", "同类 App 多少、收费多少、评价人数", "auto", "appstore_cn"),
    ("抖音电商（抖店）", "cn", "中国", "直播 / 内容电商", "https://www.jinritemai.com/", "直播带货的销量（看数要用蝉妈妈、飞瓜这类工具）", "manual", ""),
    ("快手小店", "cn", "中国", "直播 / 内容电商", "https://www.kwaixiaodian.com/", "快手直播带货", "manual", ""),
    ("小红书", "cn", "中国", "直播 / 内容电商", "https://www.xiaohongshu.com/", "种草笔记多不多（热度，不是销量）", "manual", ""),
    ("唯品会", "cn", "中国", "零售电商", "https://www.vip.com/", "品牌特卖价", "manual", ""),
    ("得物", "cn", "中国", "二手 / 成交价", "https://www.dewu.com/", "球鞋、潮玩的真实成交价（App 里看）", "manual", ""),
    ("闲鱼", "cn", "中国", "二手 / 成交价", "https://www.goofish.com/", "二手价、「多少人想要」：东西卖不卖得掉", "login", "xy"),
    ("转转", "cn", "中国", "二手 / 成交价", "https://www.zhuanzhuan.com/", "二手手机数码的回收价和成交价", "manual", ""),
    ("当当", "cn", "中国", "零售电商", "https://www.dangdang.com/", "图书、文具的价格和评论数", "manual", ""),
    ("美团 / 大众点评", "cn", "中国", "本地生活", "https://www.dianping.com/", "一个城市有多少家店、人均消费、评价数（反爬很严）", "manual", ""),
    ("饿了么", "cn", "中国", "本地生活", "https://www.ele.me/", "外卖店铺数、月售", "manual", ""),
    ("携程 / 飞猪", "cn", "中国", "本地生活", "https://www.ctrip.com/", "酒店、门票、旅游线路的价格和点评", "manual", ""),
    ("一品威客", "cn", "中国", "服务接单", "https://www.epwk.com/", "设计、开发、文案的悬赏金额", "manual", ""),
    ("程序员客栈", "cn", "中国", "服务接单", "https://www.proginn.com/", "软件外包项目的预算", "manual", ""),
    ("中国招标投标公共服务平台", "cn", "中国", "政府采购", "http://www.cebpubservice.com/", "全国招标公告（含国企）", "manual", ""),
    ("全国公共资源交易平台", "cn", "中国", "政府采购", "http://www.ggzy.gov.cn/", "工程、土地、政府采购的交易公告", "manual", ""),
    ("千里马 / 剑鱼标讯", "cn", "中国", "政府采购", "https://www.jianyu360.cn/", "全网招投标聚合（详细的要付费）", "paid", ""),
    ("慧聪网", "cn", "中国", "批发 / B2B", "https://www.hc360.com/", "工业品、电子的供应报价", "manual", ""),
    ("百度爱采购", "cn", "中国", "批发 / B2B", "https://b2b.baidu.com/", "全网 B2B 商品报价聚合", "manual", ""),
    ("震坤行 / 西域", "cn", "中国", "批发 / B2B", "https://www.zkh.com/", "工业用品（MRO）的标准价", "manual", ""),
    ("华强电子网 / 立创商城", "cn", "中国", "批发 / B2B", "https://www.szlcsc.com/", "电子元器件实时报价、库存", "manual", ""),
    ("找钢网", "cn", "中国", "大宗商品价格", "https://www.zhaogang.com/", "钢材现货成交价", "manual", ""),
    ("生意社", "cn", "中国", "大宗商品价格", "https://www.100ppi.com/", "化工、有色、钢铁、农产品的每日价格", "manual", ""),
    ("我的钢铁网 Mysteel", "cn", "中国", "大宗商品价格", "https://www.mysteel.com/", "钢铁、矿石、煤焦的权威价格", "paid", ""),
    ("卓创资讯 / 隆众资讯", "cn", "中国", "大宗商品价格", "https://www.sci99.com/", "化工、能源、塑料的价格和开工率", "paid", ""),
    ("上海有色网 SMM", "cn", "中国", "大宗商品价格", "https://www.smm.cn/", "铜铝锂钴等有色金属价格", "paid", ""),
    ("惠农网", "cn", "中国", "大宗商品价格", "https://www.cnhnb.com/", "农产品产地价、采购需求", "manual", ""),
    ("新发地价格行情", "cn", "中国", "大宗商品价格", "http://www.xinfadi.com.cn/", "北京新发地蔬菜水果肉蛋每日批发价", "manual", ""),
    ("汽车之家 / 懂车帝", "cn", "中国", "行业销量", "https://www.dongchedi.com/", "每款车的月销量榜、成交价", "manual", ""),
    ("乘联会 CPCA", "cn", "中国", "行业销量", "http://www.cpcaauto.com/", "乘用车月度零售 / 批发 / 出口", "manual", ""),
    ("贝壳 / 链家", "cn", "中国", "行业销量", "https://www.ke.com/", "二手房成交价、挂牌量", "manual", ""),
    ("BOSS 直聘 / 智联招聘", "cn", "中国", "招聘需求", "https://www.zhipin.com/", "行业在不在招人、工资多少（扩张的信号）", "manual", ""),
    ("七麦数据", "cn", "中国", "应用商店", "https://www.qimai.cn/", "App 排名、下载量估算", "paid", ""),
    ("蝉妈妈 / 飞瓜", "cn", "中国", "电商数据服务", "https://www.chanmama.com/", "抖音、快手直播和商品销量", "paid", ""),
    ("魔镜洞察", "cn", "中国", "电商数据服务", "https://www.mktindex.com/", "淘宝 / 京东 / 抖音各品类的销售额", "paid", ""),
    ("生意参谋 / 京东商智", "cn", "中国", "电商数据服务", "https://sycm.taobao.com/", "平台商家后台的行业大盘（要开店）", "paid", ""),
    ("星图数据", "cn", "中国", "电商数据服务", "http://www.syntun.com.cn/", "双 11、618 全网销售额", "manual", ""),
    ("海关统计数据在线查询", "cn", "中国", "进出口数据", "http://stats.customs.gov.cn/", "按商品编码查进出口金额和数量", "manual", ""),
    ("企查查 / 天眼查", "cn", "中国", "企业数量", "https://www.qcc.com/", "一个行业有多少家公司、每年新开多少", "paid", ""),
    ("摩点", "cn", "中国", "众筹", "https://www.modian.com/", "桌游、文创众筹金额", "manual", ""),
    # ── 北美 ──
    ("亚马逊 美国站", "na", "美国", "零售电商", "https://www.amazon.com/", "零售价、「上个月卖了多少」", "auto", "amazon"),
    ("沃尔玛 Walmart", "na", "美国", "零售电商", "https://www.walmart.com/", "零售价、评价数", "auto", "walmart"),
    ("eBay（已成交）", "na", "美国 / 全球", "二手 / 成交价", "https://www.ebay.com/", "已经卖出去的真实成交价", "auto", "ebay"),
    ("Target", "na", "美国", "零售电商", "https://www.target.com/", "大众百货零售价", "manual", ""),
    ("Best Buy", "na", "美国", "零售电商", "https://www.bestbuy.com/", "电子产品价格、评价（有官方接口）", "key", ""),
    ("Etsy", "na", "美国 / 全球", "零售电商", "https://www.etsy.com/", "手工、定制、文创的价格（有官方接口）", "key", ""),
    ("Costco", "na", "美国", "零售电商", "https://www.costco.com/", "会员店大包装价格", "manual", ""),
    ("Home Depot", "na", "美国", "零售电商", "https://www.homedepot.com/", "家装建材、工具的价格", "manual", ""),
    ("Wayfair", "na", "美国", "零售电商", "https://www.wayfair.com/", "家具家居价格", "manual", ""),
    ("Newegg", "na", "美国", "零售电商", "https://www.newegg.com/", "电脑硬件价格", "manual", ""),
    ("TikTok Shop 美国", "na", "美国", "直播 / 内容电商", "https://shop.tiktok.com/", "短视频带货（看数用 Kalodata、FastMoss）", "manual", ""),
    ("Facebook Marketplace / Craigslist", "na", "美国", "二手 / 成交价", "https://www.facebook.com/marketplace/", "本地二手挂牌价", "manual", ""),
    ("Mercari 美国", "na", "美国", "二手 / 成交价", "https://www.mercari.com/", "二手已售价格", "manual", ""),
    ("StockX", "na", "美国 / 全球", "二手 / 成交价", "https://stockx.com/", "球鞋、潮玩、显卡的真实成交价", "manual", ""),
    ("Upwork", "global", "全球", "服务接单", "https://www.upwork.com/", "全球最大的自由职业平台：正在招人的项目预算（要登录）", "login", "upwork"),
    ("Fiverr", "na", "全球", "服务接单", "https://www.fiverr.com/", "各类服务的标价", "manual", ""),
    ("Thumbtack", "na", "美国", "本地生活", "https://www.thumbtack.com/", "装修、搬家、家教等本地服务报价", "manual", ""),
    ("美国联邦政府采购 USAspending", "na", "美国", "政府采购", "https://www.usaspending.gov/", "联邦合同的份数、金额、买方", "auto", "usaspending"),
    ("SAM.gov", "na", "美国", "政府采购", "https://sam.gov/", "联邦政府正在招标的项目", "key", ""),
    ("Kickstarter", "na", "美国 / 全球", "众筹", "https://www.kickstarter.com/", "新产品众筹金额、支持人数", "auto", "kickstarter"),
    ("Indiegogo", "na", "美国 / 全球", "众筹", "https://www.indiegogo.com/", "科技硬件众筹", "manual", ""),
    ("苹果应用商店（美国区）", "na", "美国", "应用商店", "https://apps.apple.com/us/", "同类 App、收费、评价人数", "auto", "appstore_us"),
    ("Google Play", "na", "全球", "应用商店", "https://play.google.com/", "安卓 App 下载量区间", "manual", ""),
    ("Product Hunt", "na", "全球", "应用商店", "https://www.producthunt.com/", "新软件、AI 工具的热度", "key", ""),
    ("Keepa", "na", "美国 / 全球", "电商数据服务", "https://keepa.com/", "亚马逊价格历史、销量排名", "paid", ""),
    ("Jungle Scout / Helium 10", "na", "美国 / 全球", "电商数据服务", "https://www.junglescout.com/", "亚马逊每个商品的月销量估算", "paid", ""),
    ("Zillow", "na", "美国", "行业销量", "https://www.zillow.com/", "房价、租金", "manual", ""),
    ("Indeed", "na", "全球", "招聘需求", "https://www.indeed.com/", "招聘需求和工资", "manual", ""),
    ("Yelp / Google 地图", "na", "全球", "本地生活", "https://www.yelp.com/", "一个城市有多少家店、评价数（有官方接口）", "key", ""),
    ("美国人口普查局 进出口", "na", "美国", "进出口数据", "https://www.census.gov/foreign-trade/", "美国按商品的进出口额（有免费接口）", "key", ""),
    ("美国农业部 Market News", "na", "美国", "大宗商品价格", "https://www.ams.usda.gov/market-news", "农产品批发价", "manual", ""),
    # ── 欧洲 ──
    ("亚马逊 英国站", "eu", "英国", "零售电商", "https://www.amazon.co.uk/", "零售价、「上个月卖了多少」", "auto", "amz_uk"),
    ("亚马逊 德国站", "eu", "德国", "零售电商", "https://www.amazon.de/", "零售价、「上个月卖了多少」", "auto", "amz_de"),
    ("亚马逊 法国站", "eu", "法国", "零售电商", "https://www.amazon.fr/", "零售价、「上个月卖了多少」", "auto", "amz_fr"),
    ("亚马逊 意大利 / 西班牙站", "eu", "意大利、西班牙", "零售电商", "https://www.amazon.it/", "零售价", "manual", ""),
    ("Allegro", "eu", "波兰", "零售电商", "https://allegro.pl/", "波兰第一的电商", "manual", ""),
    ("Zalando", "eu", "德国 / 全欧", "零售电商", "https://www.zalando.com/", "服装鞋包价格", "manual", ""),
    ("Otto", "eu", "德国", "零售电商", "https://www.otto.de/", "德国本土综合电商", "manual", ""),
    ("bol", "eu", "荷兰 / 比利时", "零售电商", "https://www.bol.com/", "荷兰第一的电商（有官方接口）", "key", ""),
    ("Cdiscount", "eu", "法国", "零售电商", "https://www.cdiscount.com/", "法国本土电商", "manual", ""),
    ("Kaufland", "eu", "德国 / 中东欧", "零售电商", "https://www.kaufland.de/", "综合电商", "manual", ""),
    ("eMAG", "eu", "罗马尼亚等", "零售电商", "https://www.emag.ro/", "东南欧最大的电商", "manual", ""),
    ("Trendyol", "eu", "土耳其", "零售电商", "https://www.trendyol.com/", "土耳其第一的电商", "manual", ""),
    ("Hepsiburada", "eu", "土耳其", "零售电商", "https://www.hepsiburada.com/", "土耳其综合电商", "manual", ""),
    ("Alza / Digitec Galaxus", "eu", "捷克、瑞士", "零售电商", "https://www.galaxus.ch/", "当地第一的电子电商", "manual", ""),
    ("idealo / Geizhals", "eu", "德国、奥地利", "比价 / 到手价", "https://www.idealo.de/", "全网最低价、价格历史", "manual", ""),
    ("PriceRunner", "eu", "英国、北欧", "比价 / 到手价", "https://www.pricerunner.com/", "比价、价格历史", "manual", ""),
    ("Vinted", "eu", "全欧", "二手 / 成交价", "https://www.vinted.com/", "二手服装价格", "manual", ""),
    ("leboncoin / Kleinanzeigen", "eu", "法国、德国", "二手 / 成交价", "https://www.leboncoin.fr/", "本地二手挂牌价", "manual", ""),
    ("欧盟招标 TED", "eu", "欧盟各国", "政府采购", "https://ted.europa.eu/", "欧盟政府、医院、学校的招标", "auto", "ted"),
    ("英国政府合同 Contracts Finder", "eu", "英国", "政府采购", "https://www.contractsfinder.service.gov.uk/", "英国公共部门合同和金额", "manual", ""),
    ("欧盟统计局 Comext", "eu", "欧盟", "进出口数据", "https://ec.europa.eu/eurostat/comext/", "欧盟按商品的进出口", "manual", ""),
    # ── 俄罗斯 / 中亚 ──
    ("Wildberries", "ru", "俄罗斯等", "零售电商", "https://www.wildberries.ru/", "俄罗斯第一的电商：价格、评价数", "manual", ""),
    ("Ozon", "ru", "俄罗斯", "零售电商", "https://www.ozon.ru/", "俄罗斯第二的电商", "manual", ""),
    ("Yandex Market", "ru", "俄罗斯", "比价 / 到手价", "https://market.yandex.ru/", "比价和零售", "manual", ""),
    ("Avito", "ru", "俄罗斯", "二手 / 成交价", "https://www.avito.ru/", "二手和本地服务", "manual", ""),
    ("Kaspi", "ru", "哈萨克斯坦", "零售电商", "https://kaspi.kz/", "中亚第一的电商", "manual", ""),
    # ── 日本 / 韩国 ──
    ("亚马逊 日本站", "jk", "日本", "零售电商", "https://www.amazon.co.jp/", "零售价、「上个月卖了多少」", "auto", "amz_jp"),
    ("乐天市场 Rakuten", "jk", "日本", "零售电商", "https://www.rakuten.co.jp/", "日本最大的综合网购：价格、评价数", "auto", "rakuten"),
    ("雅虎拍卖（已成交）", "jk", "日本", "二手 / 成交价", "https://auctions.yahoo.co.jp/", "已经拍出去的真实成交价", "auto", "yja"),
    ("雅虎购物", "jk", "日本", "零售电商", "https://shopping.yahoo.co.jp/", "零售价（有免费官方接口）", "key", ""),
    ("价格.com Kakaku", "jk", "日本", "比价 / 到手价", "https://kakaku.com/", "电子家电全网最低价、价格历史", "manual", ""),
    ("Mercari 日本", "jk", "日本", "二手 / 成交价", "https://jp.mercari.com/", "二手已售价格", "manual", ""),
    ("Coupang", "jk", "韩国", "零售电商", "https://www.coupang.com/", "韩国第一的电商", "manual", ""),
    ("Naver 购物", "jk", "韩国", "比价 / 到手价", "https://shopping.naver.com/", "韩国全网比价（有免费官方接口）", "key", ""),
    ("Gmarket / 11 街", "jk", "韩国", "零售电商", "https://www.gmarket.co.kr/", "韩国综合电商", "manual", ""),
    ("Danawa", "jk", "韩国", "比价 / 到手价", "https://www.danawa.com/", "韩国电子比价", "manual", ""),
    ("Coconala / Lancers", "jk", "日本", "服务接单", "https://coconala.com/", "日本的服务报价", "manual", ""),
    ("Makuake", "jk", "日本", "众筹", "https://www.makuake.com/", "日本新品众筹金额", "manual", ""),
    # ── 东南亚 ──
    ("Shopee", "sea", "东南亚 + 巴西", "零售电商", "https://shopee.sg/", "东南亚第一：价格、「已售多少」（搜索要登录）", "login", "shopee"),
    ("Lazada", "sea", "东南亚六国", "零售电商", "https://www.lazada.sg/", "价格、「已售多少」", "auto", "lazada"),
    ("TikTok Shop 东南亚", "sea", "东南亚", "直播 / 内容电商", "https://shop.tiktok.com/", "短视频带货", "manual", ""),
    ("Tokopedia", "sea", "印尼", "零售电商", "https://www.tokopedia.com/", "印尼本土电商（已并入 TikTok Shop）", "manual", ""),
    ("Tiki", "sea", "越南", "零售电商", "https://tiki.vn/", "越南本土电商", "manual", ""),
    ("Carousell", "sea", "新加坡、马来西亚等", "二手 / 成交价", "https://www.carousell.sg/", "二手挂牌价", "manual", ""),
    ("iPrice", "sea", "东南亚", "比价 / 到手价", "https://iprice.my/", "东南亚比价", "manual", ""),
    # ── 南亚 ──
    ("亚马逊 印度站", "sa", "印度", "零售电商", "https://www.amazon.in/", "零售价、「上个月卖了多少」", "auto", "amz_in"),
    ("Flipkart", "sa", "印度", "零售电商", "https://www.flipkart.com/", "印度第一的本土电商：价格、评分人数", "auto", "flipkart"),
    ("Meesho", "sa", "印度", "零售电商", "https://www.meesho.com/", "印度下沉市场电商", "manual", ""),
    ("IndiaMART", "sa", "印度", "批发 / B2B", "https://www.indiamart.com/", "印度工厂和批发商报价", "auto", "indiamart"),
    ("TradeIndia", "sa", "印度", "批发 / B2B", "https://www.tradeindia.com/", "印度 B2B 报价", "manual", ""),
    ("Daraz", "sa", "巴基斯坦、孟加拉等", "零售电商", "https://www.daraz.pk/", "南亚电商（阿里旗下）", "manual", ""),
    ("印度政府采购 GeM", "sa", "印度", "政府采购", "https://gem.gov.in/", "印度政府采购的商品和价格", "manual", ""),
    # ── 拉美 ──
    ("美客多 Mercado Libre（墨西哥）", "latam", "墨西哥", "零售电商", "https://www.mercadolibre.com.mx/", "拉美第一：价格、「卖出多少」", "auto", "meli_mx"),
    ("美客多 Mercado Livre（巴西）", "latam", "巴西", "零售电商", "https://www.mercadolivre.com.br/", "巴西的价格、「卖出多少」", "auto", "meli_br"),
    ("美客多（阿根廷等）", "latam", "阿根廷、智利、哥伦比亚", "零售电商", "https://www.mercadolibre.com.ar/", "当地价格", "manual", ""),
    ("亚马逊 巴西站", "latam", "巴西", "零售电商", "https://www.amazon.com.br/", "零售价、「上个月卖了多少」", "auto", "amz_br"),
    ("亚马逊 墨西哥站", "latam", "墨西哥", "零售电商", "https://www.amazon.com.mx/", "零售价", "manual", ""),
    ("Shopee 巴西", "latam", "巴西", "零售电商", "https://shopee.com.br/", "巴西用户最多的电商（搜索要登录）", "manual", ""),
    ("Magazine Luiza / Americanas", "latam", "巴西", "零售电商", "https://www.magazineluiza.com.br/", "巴西本土电商", "manual", ""),
    ("Falabella", "latam", "智利、哥伦比亚、秘鲁", "零售电商", "https://www.falabella.com/", "南美百货电商", "manual", ""),
    ("Workana", "latam", "拉美", "服务接单", "https://www.workana.com/", "拉美自由职业项目预算", "manual", ""),
    ("OLX 巴西", "latam", "巴西", "二手 / 成交价", "https://www.olx.com.br/", "二手挂牌价", "manual", ""),
    # ── 中东 / 非洲 ──
    ("亚马逊 阿联酋站", "mea", "阿联酋", "零售电商", "https://www.amazon.ae/", "零售价、「上个月卖了多少」", "auto", "amz_ae"),
    ("亚马逊 沙特站", "mea", "沙特", "零售电商", "https://www.amazon.sa/", "零售价", "manual", ""),
    ("noon", "mea", "沙特、阿联酋、埃及", "零售电商", "https://www.noon.com/", "中东本土第一的电商", "manual", ""),
    ("Jumia", "mea", "尼日利亚等非洲多国", "零售电商", "https://www.jumia.com.ng/", "非洲最大的电商：价格", "auto", "jumia"),
    ("Takealot", "mea", "南非", "零售电商", "https://www.takealot.com/", "南非第一的电商", "manual", ""),
    ("Konga", "mea", "尼日利亚", "零售电商", "https://www.konga.com/", "尼日利亚本土电商", "manual", ""),
    ("Dubizzle / Jiji", "mea", "中东、非洲", "二手 / 成交价", "https://www.dubizzle.com/", "二手和本地分类信息", "manual", ""),
    # ── 大洋洲 ──
    ("亚马逊 澳洲站", "oc", "澳大利亚", "零售电商", "https://www.amazon.com.au/", "零售价", "manual", ""),
    ("Kogan", "oc", "澳大利亚", "零售电商", "https://www.kogan.com/", "澳洲本土电商", "manual", ""),
    ("Trade Me", "oc", "新西兰", "二手 / 成交价", "https://www.trademe.co.nz/", "新西兰第一的交易平台", "manual", ""),
    ("澳洲政府采购 AusTender", "oc", "澳大利亚", "政府采购", "https://www.tenders.gov.au/", "澳洲联邦政府合同", "manual", ""),
    # ── 全球 / 跨境 ──
    ("速卖通 AliExpress", "global", "全球", "零售电商", "https://www.aliexpress.com/", "中国卖家卖到国外的零售价、销量", "auto", "aliexpress"),
    ("阿里巴巴国际站", "global", "全球", "批发 / B2B", "https://www.alibaba.com/", "外贸批发价、起订量", "auto", "alibaba"),
    ("中国制造网 Made-in-China", "global", "全球", "批发 / B2B", "https://www.made-in-china.com/", "中国工厂给国外买家的报价", "auto", "mic"),
    ("敦煌网 DHgate", "global", "全球", "批发 / B2B", "https://www.dhgate.com/", "跨境小额批发价、卖出多少", "auto", "dhgate"),
    ("环球资源 Global Sources", "global", "全球", "批发 / B2B", "https://www.globalsources.com/", "电子、礼品的外贸报价", "manual", ""),
    ("Temu / Shein", "global", "全球", "零售电商", "https://www.temu.com/", "超低价跨境（反爬很严）", "manual", ""),
    ("Freelancer", "global", "全球", "服务接单", "https://www.freelancer.com/", "全世界正在花钱找人做的项目：预算、竞标人数", "auto", "freelancer"),
    ("Google 购物", "global", "全球", "比价 / 到手价", "https://shopping.google.com/", "全网比价", "manual", ""),
    ("Similarweb", "global", "全球", "电商数据服务", "https://www.similarweb.com/", "各个网站的访问量（看平台和品牌大小）", "paid", ""),
    ("联合国 UN Comtrade", "global", "全球", "进出口数据", "https://comtradeplus.un.org/", "全球各国按商品的进出口额（有免费接口）", "key", ""),
    ("ITC Trade Map", "global", "全球", "进出口数据", "https://www.trademap.org/", "按 HS 编码看谁进口最多（免费注册）", "manual", ""),
    ("ImportYeti / Panjiva", "global", "美国 / 全球", "进出口数据", "https://www.importyeti.com/", "美国海关提单：谁从中国进了什么货", "manual", ""),
    ("Kalodata / FastMoss", "global", "全球", "电商数据服务", "https://www.kalodata.com/", "TikTok Shop 商品和达人销量", "paid", ""),
    ("Statista / Euromonitor", "global", "全球", "电商数据服务", "https://www.statista.com/", "各国各品类的市场规模报告", "paid", ""),
    ("世界银行商品价格 / FAO 粮价", "global", "全球", "大宗商品价格", "https://www.worldbank.org/en/research/commodity-markets", "能源、金属、粮食的国际价格", "manual", ""),
    ("Marketplace Pulse", "global", "全球", "电商数据服务", "https://www.marketplacepulse.com/", "各大电商平台的卖家数、GMV 新闻", "manual", ""),
]


# ───────────────────────── v203：同一个平台的「还能从哪拿数据」放在一起 ─────────────────────────
# 这些原来单独一行的数据工具，挪进它们服务的那个平台下面
MERGED = {"千里马 / 剑鱼标讯", "七麦数据", "蝉妈妈 / 飞瓜", "魔镜洞察", "生意参谋 / 京东商智", "星图数据", "Keepa", "Jungle Scout / Helium 10", "Kalodata / FastMoss"}
L = [x for x in L if x[0] not in MERGED]

# 各地的统计机构：真实市场规模最可靠的来源（类型「统计机构」）
L += [
    ("国家统计局", "cn", "中国", "统计机构", "https://www.stats.gov.cn/", "社零、网上零售、工业营收利润、居民收支（软件已在用）", "auto", ""),
    ("商务部 商务数据中心", "cn", "中国", "统计机构", "http://data.mofcom.gov.cn/", "网络零售、重点商品、外贸数据", "manual", ""),
    ("国家邮政局", "cn", "中国", "统计机构", "https://www.spb.gov.cn/", "每月快递业务量（网购活跃度）", "manual", ""),
    ("中国汽车工业协会", "cn", "中国", "统计机构", "http://www.caam.org.cn/", "汽车、新能源车月度产销", "manual", ""),
    ("中国物流与采购联合会", "cn", "中国", "统计机构", "http://www.chinawuliu.com.cn/", "采购经理指数 PMI、物流数据", "manual", ""),
    ("工业和信息化部", "cn", "中国", "统计机构", "https://www.miit.gov.cn/", "电子信息、通信、软件业运行数据", "manual", ""),
    ("国家药监局", "cn", "中国", "统计机构", "https://www.nmpa.gov.cn/", "药品、医疗器械审批数量（新产品供给）", "manual", ""),
    ("中国连锁经营协会", "cn", "中国", "统计机构", "http://www.ccfa.org.cn/", "连锁百强、便利店、茶饮咖啡行业报告", "manual", ""),
    ("美国人口普查局 零售与电商", "na", "美国", "统计机构", "https://www.census.gov/retail/index.html", "月度零售、季度网购销售额（分品类）", "manual", ""),
    ("美国劳工统计局 BLS", "na", "美国", "统计机构", "https://www.bls.gov/", "物价 CPI、各行业就业和工资", "manual", ""),
    ("美国经济分析局 BEA", "na", "美国", "统计机构", "https://www.bea.gov/", "居民消费支出 PCE（分品类）", "manual", ""),
    ("加拿大统计局", "na", "加拿大", "统计机构", "https://www.statcan.gc.ca/", "零售、电商销售额", "manual", ""),
    ("欧盟统计局 Eurostat", "eu", "欧盟", "统计机构", "https://ec.europa.eu/eurostat", "零售、网购普及率、各国消费", "manual", ""),
    ("英国国家统计局 ONS", "eu", "英国", "统计机构", "https://www.ons.gov.uk/", "月度零售、网购占比", "manual", ""),
    ("德国联邦统计局 Destatis", "eu", "德国", "统计机构", "https://www.destatis.de/", "零售、工业数据", "manual", ""),
    ("日本经济产业省 商业动态统计", "jk", "日本", "统计机构", "https://www.meti.go.jp/statistics/", "零售销售额、每年的电商市场调查", "manual", ""),
    ("韩国统计厅 KOSIS", "jk", "韩国", "统计机构", "https://kosis.kr/", "网购交易额（分品类，每月）", "manual", ""),
    ("e-Conomy SEA 报告", "sea", "东南亚", "统计机构", "https://economysea.withgoogle.com/", "谷歌、淡马锡、贝恩每年出的东南亚电商规模", "manual", ""),
    ("印度统计部 MOSPI / IBEF", "sa", "印度", "统计机构", "https://www.ibef.org/", "印度各行业规模报告", "manual", ""),
    ("巴西统计局 IBGE", "latam", "巴西", "统计机构", "https://www.ibge.gov.br/", "零售、消费数据", "manual", ""),
    ("墨西哥统计局 INEGI", "latam", "墨西哥", "统计机构", "https://www.inegi.org.mx/", "零售、消费数据", "manual", ""),
    ("世界银行 / 国际货币基金组织", "global", "全球", "统计机构", "https://data.worldbank.org/", "各国 GDP、人口、消费支出（免费接口）", "key", ""),
    ("联合国贸发会议 UNCTAD", "global", "全球", "统计机构", "https://unctad.org/", "全球电商规模、跨境电商报告", "manual", ""),
    ("世界贸易组织 WTO 统计", "global", "全球", "统计机构", "https://stats.wto.org/", "各国各品类贸易额", "manual", ""),
]

# 每个平台还能从哪拿数据：(类型, 名字, 网址, 说明, 软件在用吗：done＝已在用 / apify＝填了 Apify 令牌就用)
_AMZ = [("官方接口", "Amazon Creators API", "https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction",
         "原来的商品接口已经停了，换成它；要亚马逊联盟会员、30 天内至少 10 笔有效销售", ""),
        ("现成爬虫", "Apify 亚马逊搜索爬虫", "https://apify.com/santamaria-automations/amazon-search-scraper", "20 个站点，按结果付费", "apify"),
        ("数据服务", "Keepa", "https://keepa.com/", "价格历史、销量排名，有接口（付费）", ""),
        ("数据服务", "Jungle Scout / Helium 10", "https://www.junglescout.com/", "每个商品的月销量估算（付费）", "")]
_TT = [("数据服务", "Kalodata", "https://www.kalodata.com/", "TikTok Shop 商品和达人销量（付费）", ""),
       ("数据服务", "FastMoss", "https://www.fastmoss.com/", "TikTok Shop 销量（付费）", "")]
_MP = [("数据服务", "MPStats", "https://mpstats.io/", "Wildberries / Ozon 商品销量分析（付费）", "")]
CH = {
    "tb": [("联盟接口", "淘宝联盟开放平台（淘宝客）", "https://open.taobao.com/", "商品搜索能拿价格和销量；要实名、媒体备案、申请推广者权限", ""),
           ("卖家后台", "生意参谋", "https://sycm.taobao.com/", "行业大盘、品类排行；要有淘宝 / 天猫店铺", ""),
           ("数据服务", "魔镜洞察", "https://www.mktindex.com/", "淘宝、京东、抖音各品类的销售额（付费）", ""),
           ("数据服务", "星图数据", "http://www.syntun.com.cn/", "双 11、618 全网销售额（公开报告免费）", ""),
           ("现成爬虫", "Apify 上的淘宝爬虫", "https://apify.com/store?search=taobao", "别人维护的爬虫，按结果付费", "")],
    "jd": [("联盟接口", "京东联盟开放平台", "https://union.jd.com/", "商品、价格、30 天引单量；关键词搜索接口要单独申请", ""),
           ("卖家后台", "京东商智", "https://sz.jd.com/", "行业数据；要有京东店铺", ""),
           ("现成爬虫", "Apify 京东爬虫", "https://apify.com/apimy/jd-products-scraper", "按结果付费", "")],
    "pdd": [("联盟接口", "多多进宝开放平台", "https://open.pinduoduo.com/", "商品搜索能拿价格和销量提示；要注册、推广位备案", "")],
    "b2b": [("官方接口", "1688 开放平台", "https://open.1688.com/", "要企业认证，适合采购商和 ERP", ""),
            ("现成爬虫", "Apify 上的 1688 爬虫", "https://apify.com/store?search=1688", "按结果付费", "")],
    "xy": [("现成爬虫", "Apify 上的闲鱼爬虫", "https://apify.com/store?search=xianyu", "按结果付费（先搜一下有没有好用的）", "")],
    "ccgp": [("官方接口", "全国公共资源交易平台", "http://www.ggzy.gov.cn/", "省市级的采购、工程、中标公告", ""),
             ("数据服务", "剑鱼标讯 / 千里马", "https://www.jianyu360.cn/", "全网招投标聚合、按行业订阅（付费）", "")],
    "appstore_cn": [("官方接口", "苹果 iTunes 搜索接口", "https://itunes.apple.com/", "免费、不用钥匙", "done"),
                    ("数据服务", "七麦数据", "https://www.qimai.cn/", "App 排名、下载量估算（部分免费）", ""),
                    ("数据服务", "点点数据", "https://www.diandian.com/", "App 下载和收入估算（付费）", "")],
    "appstore_us": [("官方接口", "iTunes Search API", "https://itunes.apple.com/", "免费、不用钥匙", "done"),
                    ("数据服务", "Sensor Tower", "https://sensortower.com/", "全球 App 下载和收入估算（付费）", "")],
    "ebay": [("官方接口", "eBay Browse API", "https://developer.ebay.com/", "免费注册开发者账号，能搜在售商品", ""),
             ("卖家后台", "Terapeak（eBay 卖家中心）", "https://www.ebay.com/sh/research", "已成交商品的价格和数量；要 eBay 账号", ""),
             ("现成爬虫", "Apify eBay 已成交爬虫", "https://apify.com/apimy/ebay-sold-listings-scraper", "按结果付费", "")],
    "walmart": [("联盟接口", "Walmart 联盟", "https://affiliates.walmart.com/", "联盟会员能用商品接口", ""),
                ("现成爬虫", "Apify 上的沃尔玛爬虫", "https://apify.com/store?search=walmart", "按结果付费", "")],
    "aliexpress": [("联盟接口", "速卖通联盟接口", "https://portals.aliexpress.com/", "联盟会员能搜商品、拿价格和销量", "")],
    "alibaba": [("现成爬虫", "Apify 上的阿里巴巴国际站爬虫", "https://apify.com/store?search=alibaba", "按结果付费", "")],
    "rakuten": [("官方接口", "乐天 Web Service 商品搜索", "https://webservice.rakuten.co.jp/", "免费注册拿 applicationId", "")],
    "yja": [("数据服务", "aucfan", "https://aucfan.com/", "日本拍卖、二手成交价历史（部分免费）", "")],
    "flipkart": [("联盟接口", "Flipkart 联盟", "https://affiliate.flipkart.com/", "联盟会员有商品接口", "")],
    "lazada": [("现成爬虫", "Apify Lazada 爬虫", "https://apify.com/lergassy/lazada-scraper", "6 个国家；约 2 美元 / 1000 个商品，免费套餐每月送 5 美元", "apify"),
               ("官方接口", "Lazada 开放平台", "https://open.lazada.com/", "主要给卖家和合作伙伴", "")],
    "shopee": [("现成爬虫", "Apify Shopee 爬虫", "https://apify.com/lergassy/shopee-scraper", "11 个市场，按结果付费；不用你登录", "apify"),
               ("联盟接口", "Shopee 联盟", "https://affiliate.shopee.sg/", "联盟会员能拿商品数据", "")],
    "meli_mx": [("官方接口", "Mercado Libre Developers", "https://developers.mercadolibre.com/", "官方接口，要注册应用", "")],
    "meli_br": [("官方接口", "Mercado Libre Developers", "https://developers.mercadolibre.com/", "官方接口，要注册应用", "")],
    "jumia": [("现成爬虫", "Apify 上的 Jumia 爬虫", "https://apify.com/store?search=jumia", "按结果付费", "")],
    "mic": [("现成爬虫", "Apify 上的中国制造网爬虫", "https://apify.com/store?search=made-in-china", "按结果付费", "")],
    "dhgate": [("现成爬虫", "Apify 上的敦煌网爬虫", "https://apify.com/store?search=dhgate", "按结果付费", "")],
    "usaspending": [("官方接口", "USAspending API", "https://api.usaspending.gov/", "免费、不用钥匙", "done"),
                    ("官方接口", "SAM.gov 招标接口", "https://open.gsa.gov/api/get-opportunities-public-api/", "正在招标的项目，免费钥匙", "")],
    "ted": [("官方接口", "TED Search API", "https://docs.ted.europa.eu/api/", "免费、不用钥匙", "done")],
    "freelancer": [("官方接口", "Freelancer API", "https://developers.freelancer.com/", "公开项目搜索", "done")],
    "upwork": [("官方接口", "Upwork API", "https://www.upwork.com/developer", "要申请", "")],
    "kickstarter": [("数据服务", "Kicktraq", "https://www.kicktraq.com/", "众筹项目每天的筹款曲线（免费）", "")],
    # 不是软件自己抓的平台，按名字挂
    "抖音电商（抖店）": [("联盟接口", "抖店开放平台 / 精选联盟", "https://op.jinritemai.com/", "给商家和达人机构", ""),
                   ("数据服务", "蝉妈妈", "https://www.chanmama.com/", "抖音直播和商品销量（付费）", ""),
                   ("数据服务", "飞瓜数据", "https://www.feigua.cn/", "抖音、快手带货数据（付费）", "")],
    "快手小店": [("数据服务", "飞瓜数据", "https://www.feigua.cn/", "快手带货数据（付费）", "")],
    "小红书": [("数据服务", "千瓜数据", "https://www.qian-gua.com/", "小红书笔记和品牌投放（付费）", "")],
    "TikTok Shop 美国": _TT, "TikTok Shop 东南亚": _TT,
    "美团 / 大众点评": [("官方接口", "高德地图地点搜索", "https://lbs.amap.com/", "按类别数一个城市有多少家店，免费钥匙", ""),
                   ("官方接口", "百度地图地点检索", "https://lbsyun.baidu.com/", "同上，免费钥匙", "")],
    "企查查 / 天眼查": [("官方接口", "国家企业信用信息公示系统", "https://www.gsxt.gov.cn/", "官方工商登记，一家一家查（免费）", "")],
    "Etsy": [("官方接口", "Etsy Open API", "https://developers.etsy.com/", "免费钥匙", "")],
    "Best Buy": [("官方接口", "Best Buy Developer API", "https://developer.bestbuy.com/", "免费钥匙", "")],
    "Naver 购物": [("官方接口", "Naver 搜索接口（购物）", "https://developers.naver.com/", "免费钥匙", "")],
    "雅虎购物": [("官方接口", "Yahoo!ショッピング Web API", "https://developer.yahoo.co.jp/", "免费注册拿 appid", "")],
    "Coupang": [("联盟接口", "Coupang Partners", "https://partners.coupang.com/", "联盟会员有接口", "")],
    "bol": [("联盟接口", "bol 联盟接口", "https://partner.bol.com/", "联盟会员能拿商品数据", "")],
    "Allegro": [("官方接口", "Allegro REST API", "https://developer.allegro.pl/", "要注册应用", "")],
    "Wildberries": _MP, "Ozon": _MP,
    "Yelp / Google 地图": [("官方接口", "Yelp Fusion API", "https://docs.developer.yelp.com/", "免费钥匙", ""),
                         ("官方接口", "Google Places API", "https://developers.google.com/maps/documentation/places/web-service", "按次收费，有免费额度", "")],
    "美国人口普查局 进出口": [("官方接口", "Census 国际贸易接口", "https://www.census.gov/data/developers/data-sets/international-trade.html", "免费钥匙", "")],
    "联合国 UN Comtrade": [("官方接口", "Comtrade API", "https://comtradedeveloper.un.org/", "免费钥匙", "")],
    "国家统计局": [("官方接口", "国家数据 data.stats.gov.cn", "https://data.stats.gov.cn/", "所有统计指标都能查（软件读的是发布页）", "done")],
}
for _k in ("amazon", "amz_uk", "amz_de", "amz_fr", "amz_jp", "amz_in", "amz_br", "amz_ae"):
    CH[_k] = _AMZ


# ───────────────────────── v204：每条渠道「怎么用」 ─────────────────────────
TELL = "拿到后在软件里跟我说一声（把名字和钥匙类型告诉我，钥匙本身不用发），我在「更强的抓取」里加一个填它的地方，接上后软件自动用"
APIFY_STEPS = ["去 Apify 注册（免费套餐每月送 5 美元额度，不用绑卡就能试）",
               "登录 Apify 控制台，进「Settings（设置）」→「API & Integrations」，复制里面的 API token（令牌）",
               "回到软件：交易平台抓取 → 展开「更强的抓取」→ ① Apify 现成爬虫，粘贴令牌点「保存」",
               "之后免费办法抓不到时，软件自动交给它；可以在表里点这个平台的「试抓」马上试一下"]
KIND_STEPS = {
    "官方接口": lambda n: ["打开「%s」，注册一个开发者账号（一般免费）" % n,
                       "在后台新建一个「应用」，拿到它给的钥匙（叫 API Key、Client ID、AppKey 之类）", TELL],
    "联盟接口": lambda n: ["在「%s」注册成为推广者（联盟会员），一般要实名" % n,
                       "按它的要求完成备案、建推广位，再申请接口权限（有的要审核几天）",
                       "批下来后拿到 AppKey 和 Secret。" + TELL,
                       "注意：联盟接口给的是推广价和销量提示，和页面上的价格不一定完全一样"],
    "现成爬虫": lambda n: ["打开链接，在 Apify 商店的搜索结果里挑一个：看「Monthly users（每月用户）」多、评分高、最近更新过的",
                       "注册 Apify 后，点那个爬虫的「Try for free」，在网页上填个关键词先试一次，看结果对不对",
                       "好用的话，把它的名字（形如 作者/xxx-scraper）告诉我，我接进软件；令牌按上面 Apify 的办法填"],
    "数据服务": lambda n: ["打开「%s」注册；大多有免费试用或部分免费内容，深度数据要付费" % n,
                       "在它网站上按品类、关键词查，能导出表格的就导出来",
                       "软件暂时接不了（多数没有公开接口，或者只卖企业版）。查到的数字可以记下来，核实时对照着看"],
    "卖家后台": lambda n: ["要先在这个平台开店，用店铺账号才能登录「%s」" % n,
                       "登录后在「市场」「行业」「搜索分析」这类页面看行业大盘和品类排行",
                       "软件接不了：这些数据平台只给店主看"],
}
DONE_STEPS = ["软件已经在用，你不用做什么", "想自己看原始数据，点上面的名字打开它的网站"]
HOW = {
    "淘宝联盟开放平台（淘宝客）": ["打开 pub.alimama.com，用淘宝账号登录，完成实名认证和媒体备案",
                           "创建一个推广位，记下推广位 ID（adzone_id）",
                           "打开 open.taobao.com 创建应用，申请「淘宝客【推广者】」权限（里面有物料搜索接口），拿到 AppKey 和 AppSecret",
                           "三样都有了，" + TELL],
    "京东联盟开放平台": ["打开 union.jd.com，用京东账号登录，完成实名认证",
                  "在京东联盟的开放平台新建应用，拿到 AppKey 和 AppSecret",
                  "「关键词查商品」的接口要单独申请权限；批下来之前只能拿到京东挑好的精选商品",
                  TELL],
    "多多进宝开放平台": ["打开开放平台，注册「多多进宝」开发者，新建应用拿到 client_id 和 client_secret",
                  "建一个推广位，并做「授权备案」（拼多多要求的，不备案搜不到商品）", TELL],
    "1688 开放平台": ["要企业认证（营业执照），个人一般用不了", "认证后新建应用、申请商品类接口", TELL],
    "Amazon Creators API": ["先加入亚马逊联盟（Amazon Associates），而且 30 天内要有至少 10 笔有效销售，接口才开放",
                            "达到后登录 Associates Central →「Tools」→「Product Advertising API」→ 管理凭证，生成新的 Creators API 凭证",
                            "门槛对一般人太高。想要亚马逊数据，更现实的是用 Apify（下面那条）或 Keepa"],
    "Keepa": ["打开 keepa.com 注册；网页上免费就能看每个商品的价格历史曲线",
              "要「数据接口」得另外付费订阅 API（按用量计费）",
              "订阅后，" + TELL + "（能查价格历史、销量排名）"],
    "Jungle Scout / Helium 10": ["注册后付费订阅（有试用期），在网页上搜关键词看每个商品的月销量估算",
                                 "软件接不了，查到的月销量可以记下来对照看"],
    "eBay Browse API": ["打开 developer.ebay.com 注册开发者账号（免费）",
                        "新建应用，在「Production（正式）」那一栏拿到 Client ID 和 Client Secret", TELL + "（能搜 eBay 在售商品的价格）"],
    "Terapeak（eBay 卖家中心）": ["用 eBay 账号登录，打开 Seller Hub 里的「Research（Terapeak）」",
                              "输关键词，能看到过去一年卖出了多少件、成交均价（卖家免费用）", "软件接不了，只能在那里看"],
    "SAM.gov 招标接口": ["打开 sam.gov 注册账号", "登录后在个人账户（Workspace）里申请「Public API Key」（免费）",
                      TELL + "（能查美国联邦正在招标、还没定的项目）"],
    "乐天 Web Service 商品搜索": ["用乐天账号登录 webservice.rakuten.co.jp", "新建应用，拿到 applicationId（免费）",
                             TELL + "，接上后乐天改用官方接口抓，比抓网页稳"],
    "Yahoo!ショッピング Web API": ["用 Yahoo! JAPAN ID 登录 developer.yahoo.co.jp", "注册应用拿到 Client ID（就是 appid，免费）", TELL],
    "Naver 搜索接口（购物）": ["用 Naver 账号登录 developers.naver.com", "注册应用，接口选「搜索」，拿到 Client ID 和 Client Secret（免费）",
                         TELL + "（韩国全网比价的价格）"],
    "高德地图地点搜索": ["打开 lbs.amap.com 注册开发者（个人就行）", "进控制台新建应用，添加一个「Web 服务」类型的 Key（有免费额度）",
                 TELL + "：我可以加一个功能，数一个城市里某类店（宠物店、奶茶店……）有多少家"],
    "百度地图地点检索": ["打开 lbsyun.baidu.com 注册开发者", "控制台新建应用拿到 AK（有免费额度）", TELL],
    "Comtrade API": ["打开 comtradedeveloper.un.org 注册", "订阅免费的那个 API 产品，拿到 key", TELL + "（各国按商品的进出口额）"],
    "Census 国际贸易接口": ["在美国人口普查局的开发者页面申请 API Key（免费，填邮箱就行）", TELL + "（美国按商品的进口额，比如从中国进口了多少）"],
    "全国公共资源交易平台": ["直接打开网站，按关键词搜公告（不用注册）", "软件现在只自动抓中国政府采购网；要的话跟我说，我把它也加进抓取"],
    "国家企业信用信息公示系统": ["直接打开网站，按公司名查工商登记（免费）", "一家一家查，适合核实某个公司；数一个行业有多少家公司要用企查查这类付费工具"],
    "Upwork API": ["在 Upwork 开发者页面提交申请，说明用途，要人工审核", "批下来拿到 Key 和 Secret，" + TELL + "；在这之前用登录方式抓就行"],
    "抖店开放平台 / 精选联盟": ["要商家、达人或机构资质才能申请", "个人想看抖音带货数据，更现实的是用蝉妈妈、飞瓜这类工具（下面那几条）"],
    "国家数据 data.stats.gov.cn": DONE_STEPS[:1] + ["想查更多指标，打开网站按「月度 / 季度 / 年度」和行业找，可以下载表格"],
}
KIND_INFO = {"官方接口": "平台自己开放的数据通道：最稳、最准，一般要注册拿一个免费钥匙",
             "联盟接口": "给帮平台卖货的推广者用的接口：要先成为推广者、实名、有的要审核",
             "现成爬虫": "Apify 上别人写好、一直在维护的爬虫：按拿到的结果付费，抓不到不收钱",
             "数据服务": "专业数据公司长期跟踪算出来的数：最准但要付费，大多只能在他们网站上看",
             "卖家后台": "平台给店主看的行业数据：要先开店"}


def how_for(kind, name, flag):
    if flag == "done":
        return HOW.get(name) or DONE_STEPS
    if flag == "apify":
        return APIFY_STEPS
    if name in HOW:
        return HOW[name]
    f = KIND_STEPS.get(kind)
    return f(name) if f else ["打开上面的链接看说明"]


INST_STEPS = ["打开网站，找「数据」「统计数据」「Statistics」「Data」这类栏目",
              "按行业或商品类别找最新一期，大多能下载表格（Excel / CSV）",
              "软件已经自动读国家统计局；其他机构想让软件自动取，跟我说是哪个、要哪张表"]


def catalog():
    """全世界的交易平台总表（v201：交易平台抓取整页就是这张表）。软件会抓的平台每个一行，状态由界面实时合上。"""
    st, plats = {}, []
    try:
        import biz_trade as BT
        st = {p["key"]: p for p in BT.status()}
        plats = BT.PLATFORMS
    except Exception:
        pass
    rows = []
    L2 = list(L)
    have = {x[7] for x in L2 if x[7]}
    for p in plats:                                     # 软件会抓、但上面没写的平台：自动补一行
        if p["key"] not in have:
            L2.append((p["name"], CAT_REGION.get(p.get("region", "cn"), "global"), "", p.get("kind", ""), p["url"], p["what"],
                       "login" if p.get("login") else "auto", p["key"]))
    for n, r, c, k, u, w, a, key in L2:
        x = {"n": n, "r": r, "rn": R[r], "c": c, "k": k, "u": u, "w": w, "a": a, "an": A[a], "key": key, "why": WHY.get(a, ""),
             "ch": [{"k": q[0], "n": q[1], "u": q[2], "w": q[3], "f": q[4], "h": how_for(q[0], q[1], q[4])} for q in (CH.get(key) or CH.get(n) or [])],
             "h": INST_STEPS if k == "统计机构" and n != "国家统计局" else []}
        s = st.get(key) or {}
        if key and s:
            x.update(n_ok=s.get("n_ok", 0), n_bad=s.get("n_bad", 0), skip=s.get("skip", ""))
        rows.append(x)
    kinds = sorted({row["k"] for row in rows}, key=lambda k: [row["k"] for row in rows].index(k))
    return {"ok": True, "rows": rows, "regions": [{"k": k, "n": v, "c": sum(1 for x in rows if x["r"] == k)} for k, v in R.items()],
            "kinds": kinds, "access": A, "kind_info": KIND_INFO, "n": len(rows), "n_auto": sum(1 for x in rows if x["a"] in ("auto", "login"))}
