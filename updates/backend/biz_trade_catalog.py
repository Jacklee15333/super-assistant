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
A = {"auto": "✓ 自动抓", "login": "登录后自动抓", "key": "要申请免费钥匙", "paid": "付费数据", "manual": "先自己看"}

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
    ("闲鱼", "cn", "中国", "二手 / 成交价", "https://www.goofish.com/", "二手价、「多少人想要」", "manual", ""),
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
    ("Upwork", "na", "美国 / 全球", "服务接单", "https://www.upwork.com/", "全球自由职业项目预算（要登录）", "manual", ""),
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
    ("亚马逊 英国 / 德国 / 法国站", "eu", "英国、德国、法国", "零售电商", "https://www.amazon.de/", "零售价、「上个月卖了多少」", "auto", "amz_de"),
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
    ("Shopee", "sea", "东南亚 + 巴西", "零售电商", "https://shopee.sg/", "东南亚第一：价格、已售（搜索要登录）", "manual", ""),
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
    ("美客多 Mercado Libre（墨西哥 / 巴西）", "latam", "墨西哥、巴西", "零售电商", "https://www.mercadolibre.com.mx/", "拉美第一：价格、「卖出多少」", "auto", "meli_mx"),
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


def catalog():
    """目录 + 软件里自动抓的那些平台的状态（抓到过几次）。"""
    st = {}
    try:
        import biz_trade as BT
        st = {p["key"]: p for p in BT.status()}
    except Exception:
        pass
    rows = []
    for n, r, c, k, u, w, a, key in L:
        x = {"n": n, "r": r, "rn": R[r], "c": c, "k": k, "u": u, "w": w, "a": a, "an": A[a], "key": key}
        s = st.get(key) or {}
        if key and s:
            x.update(n_ok=s.get("n_ok", 0), n_bad=s.get("n_bad", 0), skip=s.get("skip", ""))
        rows.append(x)
    kinds = sorted({row["k"] for row in rows}, key=lambda k: [row["k"] for row in rows].index(k))
    return {"ok": True, "rows": rows, "regions": [{"k": k, "n": v, "c": sum(1 for x in rows if x["r"] == k)} for k, v in R.items()],
            "kinds": kinds, "access": A, "n": len(rows), "n_auto": sum(1 for x in rows if x["a"] in ("auto", "login"))}
