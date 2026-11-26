"""超能小助 · 商业定制（v187 新增）

「商业 → 商业定制」的后台：
  · 你的情况（年龄、城市、阅历、技能、兴趣、资金、时间、能承受的亏损……）存在 memory/biz/profile.json。
  · 先配一遍（不用 AI，零点几秒）：把你写的阅历、技能、兴趣、资源对上行业分类表里的二级行业和新兴赛道，
    再看市场雷达最近 7 天每个方向的新闻条数、最近 24 小时的占比是升还是降，挑出最配你的方向；
    并按你的资金、时间、能承受的亏损，给每个方向挑两三种适合的赚钱做法（商业模式）。
  · 让 AI 定制方案：把上面配出来的方向、市场热度榜、这些方向的最新新闻、机会看板、你的笔记、网上搜到的资料
    一起交给 AI，写成「商业定制方案」（报告库里 kind=custom），方案里的机会自动放进机会看板。
写方案的后台任务走 biz_intel 的那一套（排队、进度、停止、存报告）；这里只管你的情况、配对、提示词和解析。
"""
from __future__ import annotations

import datetime
import math
import re
import threading
import time

import biz_intel as BZ
import biz_industries as BI

PROFILE_FILE = BZ.BIZ_DIR / "profile.json"

STATUS = {"job": "上班，想做副业", "free": "自由职业、接活", "switch": "没在上班，想换个行当", "boss": "已经在做生意",
          "retired": "退休了", "student": "还在上学"}
MONEY = {"1": ("1 万以内", 1), "5": ("1～5 万", 5), "20": ("5～20 万", 20), "50": ("20～50 万", 50),
         "100": ("50～100 万", 100), "999": ("100 万以上", 300)}          # 第二项：按多少万算
TIME = {"side": "每周 10 小时以内（下班和周末）", "part": "每周 10～30 小时", "full": "全职投入"}
RISK = {"safe": "不能亏，要稳", "mid": "亏一部分能接受", "bold": "全亏了也不影响生活"}
GOAL = {"extra": "每月多赚几千", "replace": "替代工资（月入 1～3 万）", "big": "做成一门生意、开公司"}
TEXT_LIMITS = {"city": 20, "exp": 800, "skills": 800, "likes": 600, "res": 600, "avoid": 400, "more": 600}   # v188：可以从面板里多选，放宽
# 你写的哪一栏更说明问题：干过的（阅历）> 手上有的（资源）> 会的（技能）> 喜欢的（兴趣）
PARTS = [("exp", "阅历", 3.0), ("res", "资源", 2.5), ("skills", "技能", 2.0), ("likes", "兴趣", 1.2), ("more", "其他", 1.0)]

# ───────────────────────── 选项面板（v188）─────────────────────────
# 「我的情况」里每一栏要填字的地方，都有一个可以展开的选项面板：点一下就加进去，没有的照样自己写。
# 选项和下面的配对表放在一起：测试会逐个检查，能点的选项（「其他」那一栏除外）都要能被配对认出来。
def _ages(a, b):
    return [str(i) for i in range(a, b + 1)]


PICK = {
    "age": {"mode": "single", "top": [], "groups": [
        ["18～29 岁", _ages(18, 29)], ["30～39 岁", _ages(30, 39)], ["40～49 岁", _ages(40, 49)],
        ["50～59 岁", _ages(50, 59)], ["60 岁以上", _ages(60, 75)]]},
    "city": {"mode": "single", "top": ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "县城"], "groups": [
        ["一线城市", ["北京", "上海", "广州", "深圳"]],
        ["华北", ["天津", "石家庄", "太原", "呼和浩特", "保定", "唐山", "廊坊", "邯郸"]],
        ["东北", ["沈阳", "大连", "长春", "哈尔滨"]],
        ["华东", ["南京", "苏州", "无锡", "常州", "南通", "徐州", "扬州", "杭州", "宁波", "温州", "金华", "嘉兴", "绍兴", "台州",
                "合肥", "芜湖", "福州", "厦门", "泉州", "南昌", "赣州", "济南", "青岛", "烟台", "潍坊", "临沂"]],
        ["华中", ["郑州", "洛阳", "武汉", "宜昌", "襄阳", "长沙", "株洲"]],
        ["华南", ["东莞", "佛山", "珠海", "中山", "惠州", "汕头", "南宁", "柳州", "桂林", "海口", "三亚"]],
        ["西南", ["成都", "绵阳", "重庆", "昆明", "贵阳", "遵义", "拉萨"]],
        ["西北", ["西安", "兰州", "西宁", "银川", "乌鲁木齐"]],
        ["小地方", ["地级市", "县城", "乡镇", "农村"]],
        ["港澳台和海外", ["香港", "澳门", "台湾", "海外"]]]},
    "exp": {"mode": "build",
            "ind": [["吃喝与消费", ["餐饮", "食品加工", "超市零售", "服装", "美容美发", "母婴", "珠宝首饰", "家居建材"]],
                    ["互联网与传媒", ["互联网", "软件开发", "电商", "新媒体", "广告营销", "影视娱乐", "游戏", "出版印刷"]],
                    ["服务业", ["教育培训", "医疗健康", "养老护理", "家政保洁", "酒店旅游", "物业", "房产中介", "法律", "财务会计",
                             "人力资源", "体育健身", "婚庆", "宠物"]],
                    ["制造与技术", ["工厂制造", "机械设备", "电子电器", "汽车汽修", "新能源", "化工", "建筑工程", "装修", "电力能源"]],
                    ["贸易与物流", ["外贸", "批发", "采购供应链", "物流快递", "交通运输"]],
                    ["金融", ["银行", "保险", "证券基金", "贷款"]],
                    ["农业", ["种植", "养殖", "农产品"]],
                    ["体制内", ["政府机关", "事业单位", "国企", "部队"]]],
            "phrase": {"工厂制造": "工厂", "政府机关": "政府机关", "事业单位": "事业单位", "国企": "国企", "部队": "部队",
                       "银行": "银行", "互联网": "互联网公司"},
            "role": ["普通员工", "学徒或助理", "技术工人", "技术员或工程师", "销售或业务", "客服", "运营", "设计", "财务",
                     "行政或人事", "采购", "厨师", "司机", "老师", "店长或主管", "经理", "总监或高管", "老板或合伙人", "个体户"],
            "years": ["不到 1 年", "1～3 年", "3～5 年", "5～10 年", "10 年以上"],
            "lead": ["没带过人", "带过几个人", "管过 10～50 人", "管过 50 人以上"],
            "biz": ["开过实体店", "摆过摊", "开过网店", "做过微商或社群团购", "做过直播带货", "开过公司", "开过加盟店", "做过外贸生意",
                    "包过工程", "搞过种植养殖", "做过批发", "做过代理", "做过自媒体"]},
    "skills": {"mode": "multi", "top": ["销售", "写文案", "拍剪视频", "直播", "编程", "平面设计", "做饭", "带团队", "会计", "英语", "开车",
                                       "装修", "教书", "护理", "美容", "健身教练", "摄影", "电商运营", "采购", "AI 工具"], "groups": [
        ["销售与客户", ["销售", "谈客户", "电话销售", "门店导购", "地推", "大客户销售", "招商加盟", "商务谈判", "客户维护", "客服", "直播带货"]],
        ["营销与运营", ["电商运营", "店铺运营", "选品", "新媒体运营", "社群运营", "私域运营", "用户运营", "活动策划", "品牌策划", "市场营销",
                   "投放广告", "SEO"]],
        ["内容与创作", ["写文案", "写文章", "写小说", "写剧本", "拍剪视频", "拍视频", "剪视频", "摄影", "修图", "直播", "配音", "主持", "做 PPT"]],
        ["设计与美术", ["平面设计", "UI 设计", "插画", "画画", "海报设计", "室内设计", "服装设计", "3D 建模"]],
        ["技术与编程", ["编程", "Python", "Java", "前端开发", "后端开发", "小程序开发", "App 开发", "数据分析", "Excel", "AI 工具", "办公自动化",
                   "网站搭建", "网络运维", "电脑维修"]],
        ["管理", ["带团队", "门店管理", "项目管理", "生产管理", "供应链管理", "人事招聘", "培训新人", "财务管理"]],
        ["财务与法律", ["会计", "记账报税", "出纳", "审计", "法律", "合同", "知识产权"]],
        ["语言", ["英语", "日语", "韩语", "小语种", "翻译"]],
        ["吃喝手艺", ["做饭", "烘焙", "面点", "卤味", "调酒", "咖啡", "茶艺"]],
        ["技工与维修", ["电工", "水电", "木工", "瓦工", "装修", "家电维修", "汽修", "焊接", "数控", "裁缝"]],
        ["美业与健康", ["美容", "美发", "美甲", "化妆", "皮肤管理", "按摩推拿", "针灸", "护理", "康复理疗", "营养搭配"]],
        ["教育与照护", ["教书", "辅导作业", "早教", "带娃", "照顾老人", "心理咨询", "健身教练", "瑜伽", "舞蹈", "乐器"]],
        ["采购与物流", ["采购", "品控", "质检", "仓储", "物流", "外贸", "报关", "跨境电商"]],
        ["农业", ["种植", "养殖", "种菜", "果园管理", "农机"]],
        ["交通", ["开车", "开货车", "跑网约车", "送外卖"]]]},
    "likes": {"mode": "multi", "top": ["美食", "宠物", "健身", "旅行", "数码", "母婴育儿", "穿搭", "养生", "游戏", "动漫", "户外露营", "钓鱼",
                                      "喝茶", "汽车", "读书", "手工", "花草", "AI 新工具"], "groups": [
        ["吃喝", ["美食", "做饭", "烘焙", "甜品", "咖啡", "喝茶", "品酒", "探店"]],
        ["运动户外", ["健身", "跑步", "瑜伽", "游泳", "篮球", "足球", "羽毛球", "骑行", "登山", "徒步", "户外露营", "钓鱼", "滑雪", "自驾"]],
        ["宠物与花草", ["宠物", "养猫", "养狗", "水族", "花草", "园艺", "种菜"]],
        ["文娱", ["游戏", "电竞", "动漫", "二次元", "追剧", "看电影", "音乐", "唱歌", "乐器", "舞蹈", "读书", "写作", "画画", "书法", "手工", "摄影"]],
        ["科技数码", ["数码", "手机", "电脑", "AI 新工具", "智能家居", "汽车", "新能源车", "无人机"]],
        ["生活方式", ["旅行", "穿搭", "美妆护肤", "家居收纳", "母婴育儿", "亲子", "二手闲置", "收藏文玩", "珠宝首饰", "养生", "减脂"]],
        ["学习思考", ["投资理财", "心理学", "历史", "外语", "考证"]]]},
    "res": {"mode": "multi", "top": ["有老客户", "认识供应商", "有工厂资源", "有抖音账号", "有几千粉丝", "有闲置铺面", "有一手货源", "家人能帮忙"],
            "groups": [
        ["人脉", ["有老客户", "认识供应商", "有工厂资源", "认识开店的朋友", "行业里认识人多", "认识企业老板", "认识学校和家长", "有海外客户",
                "有亲戚在做生意"]],
        ["渠道和流量", ["有抖音账号", "有小红书账号", "有视频号", "有几千粉丝", "有上万粉丝", "有微信群社群", "朋友圈好友多", "有网店", "有线下门店"]],
        ["场地和设备", ["有闲置房子", "有闲置铺面", "有仓库", "有货车或面包车", "有厨房设备", "有电脑设备", "有拍摄设备", "老家有地"]],
        ["货源", ["有一手货源", "能拿到工厂价", "有农产品货源", "有进口货渠道", "有二手货渠道"]],
        ["证书资质", ["有教师资格证", "有会计证书", "有健康证", "有驾照", "有电工证", "有营业执照", "有公司", "有专利", "有医护执业证"]],
        ["其他", ["家人能帮忙", "时间比较自由", "能经常出差", "会用 AI 工具"]]]},
    "avoid": {"mode": "multi", "top": ["不想露脸", "不想压货", "不碰加盟", "不想开实体店", "不想借钱贷款", "不想做销售", "不想熬夜"], "groups": [
        ["做法上", ["不想露脸", "不想直播", "不想压货", "不碰加盟", "不想开实体店", "不想借钱贷款", "不想做销售", "不想求人拉关系", "不想卖课",
                 "不想做微商", "不想写代码", "不想干重活", "不想熬夜", "不想出差", "不想坐班", "不想全职"]],
        ["行业上", ["不碰餐饮", "不碰教育培训", "不碰金融理财", "不碰房地产", "不碰医疗", "不碰医美", "不碰电商", "不碰外贸", "不碰自媒体",
                 "不碰农业养殖", "不碰工厂制造", "不碰物流运输", "不碰游戏", "不碰酒类", "不碰保健品"]]]},
    "more": {"mode": "multi", "top": ["大专", "本科", "有小孩要照顾", "家里人支持", "想先试试水", "外向爱社交", "内向喜欢独处"], "groups": [
        ["学历", ["初中及以下", "高中或中专", "大专", "本科", "硕士及以上"]],
        ["家庭", ["单身", "已婚", "有小孩要照顾", "有老人要照顾", "家里人支持", "家里人不太支持", "是家里主要收入来源"]],
        ["身体和作息", ["身体好能吃苦", "不能久站", "不能干重活", "白天有空", "晚上有空", "周末有空"]],
        ["打算", ["想留在本地", "想回老家发展", "愿意去外地", "想先试试水", "一两年后想全职做", "想做长期稳定的", "想快点回本"]],
        ["性格", ["外向爱社交", "内向喜欢独处", "喜欢稳定", "喜欢挑战", "执行力强", "容易拖延"]],
        ["钱的情况", ["有房贷车贷", "有存款当后路", "现在收入不稳定", "手上有负债"]]]},
}


def options():
    """选项面板用的数据（不算配对，马上返回）。"""
    return {"ok": True, "pick": PICK, "status": STATUS, "money": {k: v[0] for k, v in MONEY.items()}, "time": TIME,
            "risk": RISK, "goal": GOAL}


# ───────────────────────── 你写的词 → 方向、做法 ─────────────────────────
# (关键词, 对上的方向（二级行业 / t:赛道）, 这类本事适合的做法（biz_industries.MODELS 的编号）)
# 行业分类表的关键词是给新闻归类用的，「做饭」「剪视频」「带团队」这类说人的词对不上，所以单独列一张。
SKILL_MAP = [
    ("做饭 烹饪 厨艺 厨师 烘焙 做菜 下厨 美食 餐饮 饭店 餐厅 小吃 卤味 面点 西点 私房菜 开饭馆 甜品 厨房 健康证",
     ["社会服务/酒店餐饮", "食品饮料/休闲食品", "食品饮料/调味发酵品"], ["franchise", "private", "ip", "retail"]),
    ("咖啡 奶茶 茶饮 咖啡师 调饮", ["t:tea", "社会服务/酒店餐饮"], ["franchise", "private", "retail"]),
    ("茶叶 喝茶 茶艺 品茶", ["食品饮料/饮料乳品", "t:tea"], ["retail", "private", "ip"]),
    ("剪辑 剪视频 拍视频 拍剪视频 视频剪辑 短视频 抖音 快手 视频号 B站 小红书 做账号 自媒体 博主 网红 vlog 探店 拍摄 新媒体",
     ["t:creator", "传媒/数字媒体", "传媒/广告营销"], ["ip", "service", "ads"]),
    ("直播 主播 带货 直播间 选品", ["t:livecom", "商贸零售/互联网电商"], ["live", "private", "retail"]),
    ("写作 写文章 写文案 文案 公众号 写小说 写剧本 编剧 码字", ["t:creator", "传媒/广告营销", "传媒/出版"],
     ["ip", "service", "knowledge"]),
    ("编程 程序员 写代码 软件开发 前端 后端 Python Java JavaScript 全栈 算法 网站开发 网站搭建 建站 小程序 App开发 运维 开发",
     ["计算机/软件开发", "t:ai", "计算机/IT服务", "t:data"], ["software", "service", "opc", "subscription"]),
    ("AI AI工具 人工智能 大模型 ChatGPT 提示词 AIGC 智能体 Agent DeepSeek Cursor 办公自动化",
     ["t:ai", "计算机/软件开发"], ["service", "software", "knowledge", "opc"]),
    ("设计 平面设计 UI 美工 PS 插画 画画 绘画 3D 建模 海报 logo", ["传媒/广告营销", "t:newcons", "传媒/数字媒体"],
     ["service", "ip", "opc"]),
    ("室内设计 软装 装修设计", ["建筑装饰/装修装饰"], ["service", "private"]),
    ("销售 卖货 业务员 谈客户 跑业务 地推 推销 客户经理 销冠 招商 导购 谈判 客户维护 代理", ["商贸零售/一般零售", "商贸零售/互联网电商", "t:livecom", "商贸零售/贸易"],
     ["retail", "private", "platform", "live"]),
    ("带团队 管理 店长 经理 主管 总监 高管 开过店 实体店 加盟 当过老板 创过业 合伙", [], ["franchise", "platform", "service", "private"]),
    ("营业执照 有公司 开过公司 注册公司 个体户", [], ["opc", "service", "platform"]),
    ("客服 售后 接待", ["商贸零售/互联网电商"], ["service", "private"]),
    ("数据分析 Excel 表格 数据可视化 PPT 做PPT 汇报材料", ["t:data", "计算机/IT服务", "社会服务/专业服务"], ["service", "knowledge", "opc"]),
    ("互联网公司 互联网 大厂", ["传媒/数字媒体", "计算机/软件开发", "计算机/IT服务"], ["service", "opc", "software"]),
    ("摆摊 摆过摊 地摊 夜市 早餐摊", ["社会服务/酒店餐饮", "商贸零售/一般零售"], ["retail", "private"]),
    ("婚庆 婚礼", ["社会服务/本地生活服务", "t:local"], ["service", "private"]),
    ("追剧 影视 电影 短剧", ["传媒/影视院线", "t:creator"], ["ip", "service"]),
    ("书法 练字 国画 围棋 象棋", ["社会服务/教育", "t:edu"], ["knowledge", "ip", "private"]),
    ("二手 闲置 闲鱼 回收", ["商贸零售/互联网电商", "t:discount"], ["arbitrage", "retail"]),
    ("历史 人文 国学", ["传媒/出版", "t:creator", "t:edu"], ["ip", "knowledge"]),
    ("电子电器 电器 电子厂 电子产品 家电", ["电子/消费电子", "家用电器/小家电", "家用电器/白色家电"], ["service", "retail", "supply"]),
    ("家人 家里人 夫妻", [], ["franchise", "retail", "private"]),
    ("财务 会计 记账 税务 报税 出纳 审计 CPA", ["社会服务/专业服务", "非银金融/多元金融"], ["service", "knowledge", "opc"]),
    ("英语 外语 日语 韩语 小语种 翻译 留学", ["t:crossborder", "商贸零售/贸易", "t:edu", "社会服务/教育"],
     ["service", "knowledge", "arbitrage"]),
    ("外贸 跨境 亚马逊 Amazon 独立站 Temu SHEIN TikTok Shopee 速卖通 进出口 报关 海外客户", ["t:crossborder", "商贸零售/贸易"],
     ["retail", "service", "supply"]),
    ("电商 淘宝 天猫 京东 拼多多 网店 开网店 电商运营 店铺运营", ["商贸零售/互联网电商", "t:livecom"], ["retail", "service", "private"]),
    ("运营 新媒体运营 社群 私域 用户运营 活动策划 品牌策划 市场营销 营销 推广 投放 SEO 增长", ["传媒/广告营销", "t:creator", "商贸零售/互联网电商"],
     ["service", "private", "ads"]),
    ("开车 司机 驾驶 驾照 驾驶证 货车 网约车 快递 物流 配送 骑手 跑腿 仓库 货运 冷链 交通运输 运输", ["交通运输/物流", "t:local", "社会服务/本地生活服务"],
     ["service", "platform"]),
    ("装修 维修 修理 电工 水电 木工 瓦工 家电维修 安装 空调 家政 保洁 搬家", ["建筑装饰/装修装饰", "社会服务/本地生活服务", "t:local"],
     ["service", "private", "franchise"]),
    ("老师 教师 教书 辅导 家教 培训 讲课 讲师 带学生 教学", ["社会服务/教育", "t:edu"], ["knowledge", "private", "ip", "subscription"]),
    ("医生 护士 医护 护理 康复 理疗 药剂 药师 中医 推拿 按摩 针灸 医疗 医院 诊所", ["医药生物/医疗服务", "t:silver", "医药生物/中药"],
     ["service", "knowledge", "private", "franchise"]),
    ("美容 美发 美甲 化妆 皮肤管理 护肤 美妆 发型 纹绣 美睫", ["美容护理/化妆品", "美容护理/医疗美容", "美容护理/个护用品", "t:newcons"],
     ["franchise", "private", "retail", "ip"]),
    ("健身 运动 瑜伽 普拉提 跑步 游泳 篮球 足球 羽毛球 私教 教练 户外 登山 骑行 露营 滑雪 钓鱼", ["社会服务/体育", "轻工制造/文娱用品"],
     ["knowledge", "private", "ip", "franchise"]),
    ("摄影 拍照 修图 跟拍 航拍 无人机", ["t:creator", "传媒/数字媒体", "t:lowalt"], ["service", "ip"]),
    ("采购 供应链 进货 货源 批发 源头 厂家 供应商", ["商贸零售/贸易", "商贸零售/一般零售"], ["supply", "retail", "arbitrage"]),
    ("工厂 生产 品控 质检 车间", [], ["supply", "arbitrage", "service"]),
    ("宠物 养猫 养狗 猫咪 狗狗 撸猫 铲屎 宠物店 宠物医院 兽医 水族 观赏鱼", ["t:pet", "农林牧渔/动物保健"], ["retail", "private", "service", "ip"]),
    ("母婴 带娃 育儿 宝宝 宝妈 早教 亲子 孕产 月嫂 育婴", ["社会服务/本地生活服务", "社会服务/教育", "t:newcons"],
     ["private", "service", "knowledge", "retail"]),
    ("穿搭 服装 衣服 搭配 时尚 女装 男装 童装 汉服 裁缝 面料", ["纺织服饰/服装家纺", "t:newcons", "t:livecom"], ["retail", "live", "ip", "supply"]),
    ("养生 药膳 保健 健康管理 营养师 减肥 减脂", ["医药生物/中药", "t:silver", "社会服务/体育"], ["knowledge", "private", "retail"]),
    ("游戏 电竞 打游戏 手游 Steam 原神", ["传媒/游戏", "t:creator"], ["ip", "service", "software"]),
    ("动漫 二次元 cos 谷子 手办 盲盒 潮玩 漫画 Coser", ["t:newcons", "轻工制造/文娱用品", "传媒/数字媒体"], ["retail", "ip", "live"]),
    ("旅行 旅游 自驾 导游 民宿 景区 徒步", ["社会服务/旅游及景区", "社会服务/酒店餐饮"], ["service", "ip", "private", "franchise"]),
    ("数码 手机 电脑 耳机 相机 3C 测评 装机", ["电子/消费电子", "t:creator"], ["retail", "ip", "service"]),
    ("汽车 修车 汽修 洗车 二手车 新能源车 电动车 改装 充电桩", ["汽车/汽车服务", "t:ev"], ["service", "franchise", "arbitrage"]),
    ("读书 阅读 写书 考证 考试 知识", ["t:edu", "传媒/出版"], ["knowledge", "ip"]),
    ("手工 DIY 编织 陶艺 木作 皮具 刺绣 香薰 蜡烛", ["轻工制造/家居用品", "t:newcons", "轻工制造/文娱用品"], ["retail", "ip", "knowledge"]),
    ("园艺 花草 养花 花艺 花店 多肉 绿植", ["农林牧渔/种植业", "商贸零售/专业连锁"], ["retail", "private", "ip"]),
    ("种菜 种地 农业 种植 果园 农场 养殖 养鸡 养鱼 养猪 农村 老家 农产品 土特产",
     ["农林牧渔/种植业", "农林牧渔/养殖业", "农林牧渔/农产品加工"], ["live", "retail", "supply", "private"]),
    ("房产 房地产 中介 卖房 租房 物业 二房东 置业顾问", ["房地产/房地产服务"], ["service", "platform", "arbitrage"]),
    ("保险 理财 证券 股票 基金 投资 银行 信贷 贷款行业 助贷 贷款中介", ["非银金融/保险", "非银金融/证券", "非银金融/多元金融"], ["service", "knowledge", "private"]),
    ("法律 律师 法务 合同 知识产权 专利 商标", ["社会服务/专业服务"], ["service", "knowledge", "opc"]),
    ("心理 咨询师 心理咨询 情感 婚恋 陪伴", ["社会服务/专业服务", "t:silver"], ["knowledge", "private", "ip", "service"]),
    ("养老 老人 照护 护工 陪诊 适老", ["t:silver", "医药生物/医疗服务"], ["service", "private", "franchise"]),
    ("人力资源 HR 招聘 猎头 人事", ["社会服务/专业服务"], ["service", "platform", "knowledge"]),
    ("机械 机床 数控 CNC 模具 焊接 钳工 电气 PLC 自动化设备 工业机器人", ["机械设备/通用设备", "机械设备/自动化设备", "t:robot"],
     ["service", "supply", "arbitrage", "knowledge"]),
    ("芯片 半导体 电路 硬件 嵌入式 单片机 PCB", ["电子/半导体", "电子/元件", "t:chip"], ["service", "knowledge", "arbitrage", "software"]),
    ("光伏 储能 新能源 电池 电网 风电", ["t:energy", "电力设备/电池", "电力设备/光伏设备"], ["service", "supply", "arbitrage"]),
    ("建筑 工地 施工 造价 预算员 监理 土建 包工程 包过工程 工程队 包工头", ["建筑装饰/房屋建设", "建筑装饰/工程咨询服务", "建筑装饰/装修装饰"], ["service", "knowledge"]),
    ("化工 化学 实验室 检测", ["基础化工/化学制品", "社会服务/专业服务"], ["service", "knowledge", "arbitrage"]),
    ("外卖 团购 同城 社区 小区 社区团购", ["t:local", "社会服务/本地生活服务", "商贸零售/一般零售"], ["private", "platform", "service", "franchise"]),
    ("零食 折扣 量贩 临期 超市 便利店 小卖部", ["t:discount", "商贸零售/一般零售", "食品饮料/休闲食品"], ["franchise", "retail"]),
    ("音乐 唱歌 乐器 钢琴 吉他 声乐 配音 播音 主持", ["传媒/数字媒体", "社会服务/教育", "t:creator"], ["knowledge", "ip", "service"]),
    ("舞蹈 跳舞 街舞", ["社会服务/体育", "社会服务/教育", "t:creator"], ["knowledge", "ip", "franchise"]),
    ("珠宝 首饰 黄金 玉石 翡翠 文玩 古董 收藏 手串", ["纺织服饰/饰品", "有色金属/贵金属"], ["retail", "live", "arbitrage"]),
    ("白酒 葡萄酒 啤酒 精酿 调酒 品酒 酒水", ["食品饮料/白酒", "食品饮料/非白酒", "社会服务/酒店餐饮"], ["retail", "private", "franchise"]),
    ("家居 收纳 整理 家具 床品 家纺", ["轻工制造/家居用品", "纺织服饰/服装家纺"], ["service", "retail", "ip"]),
    ("人脉 圈子 客户资源 老客户 门路 渠道 认识 亲戚", [], ["private", "platform", "arbitrage", "service"]),
    ("场地 店面 门面 商铺 铺面 厂房 闲置房 空房 门店 线下店", [], ["franchise", "retail", "service"]),
    ("粉丝 流量 微信群 朋友圈 好友", ["t:creator"], ["ip", "private", "live"]),
]

# 不想做的 → 避开哪些做法
AVOID_MODELS = [
    ("露脸 出镜 镜头 抛头露面 当网红 拍视频", ["ip", "live"]),
    ("直播", ["live"]),
    ("压货 囤货 库存 积压", ["retail", "supply"]),
    ("加盟", ["franchise"]),
    ("开店 门店 店面 实体店", ["franchise"]),
    ("借钱 贷款 负债 借贷", ["franchise", "platform", "supply", "hardware"]),
    ("写代码 编程", ["software"]),
    ("卖课 知识付费", ["knowledge"]),
    ("销售 推销 求人 拉关系 拉客户", ["platform", "private", "live"]),     # v188
    ("微商 拉人头 传销", ["private"]),
    ("全职", ["franchise", "platform", "supply", "hardware"]),
    ("工厂 制造", ["supply", "hardware"]),
]
# 不想做的 → 避开哪些行业（v188：「不碰餐饮」这类）
AVOID_DIRS = [
    ("餐饮 饭店 饭馆", ["社会服务/酒店餐饮", "t:tea"]),
    ("教育 培训 教培", ["社会服务/教育", "t:edu"]),
    ("金融 理财 保险 证券 贷款", ["非银金融/保险", "非银金融/证券", "非银金融/多元金融"]),
    ("房地产 房产 中介", ["房地产/房地产服务", "房地产/房地产开发"]),
    ("医疗 医院 诊所", ["医药生物/医疗服务"]),
    ("医美", ["美容护理/医疗美容"]),
    ("电商 网店", ["商贸零售/互联网电商", "t:livecom"]),
    ("外贸 跨境", ["t:crossborder", "商贸零售/贸易"]),
    ("自媒体 做账号", ["t:creator", "传媒/数字媒体"]),
    ("农业 种地 养殖", ["农林牧渔/种植业", "农林牧渔/养殖业", "农林牧渔/农产品加工"]),
    ("物流 运输 快递", ["交通运输/物流", "交通运输/铁路公路"]),
    ("游戏", ["传媒/游戏"]),
    ("酒类 卖酒 白酒 啤酒 葡萄酒", ["食品饮料/白酒", "食品饮料/非白酒"]),
    ("保健品", ["医药生物/中药"]),
]

# 做法（商业模式）→ (起步大概要多少万, 要投入的时间 side/part/full, 风险 low/mid/high)
MODEL_NEED = {
    "service": (0.3, "side", "low"), "opc": (0.5, "part", "low"), "ip": (0.3, "side", "low"),
    "knowledge": (0.3, "side", "low"), "software": (0.5, "part", "low"), "private": (0.5, "side", "low"),
    "live": (1, "part", "mid"), "arbitrage": (1, "side", "mid"), "freemium": (1, "part", "mid"),
    "subscription": (1, "part", "mid"), "ads": (0.5, "part", "mid"), "retail": (3, "part", "mid"),
    "franchise": (20, "full", "high"), "platform": (10, "full", "high"), "hardware": (30, "full", "high"),
    "supply": (50, "full", "high"),
}                                   # 「资金与金融」（资金池、杠杆）不推荐给个人，不在这里
MODEL_NAME = {i: n for i, n, _d, _k in BI.MODELS}
MODEL_DESC = {i: d for i, _n, d, _k in BI.MODELS}

# 每个方向一般用哪些做法赚钱（小团队、个人能做的）。先看具体的二级行业 / 赛道，再看一级行业，都没有就是重资产行业的默认做法
DIR_MODELS = {
    "社会服务/酒店餐饮": ["franchise", "private", "ip", "retail"], "社会服务/教育": ["knowledge", "private", "ip", "subscription"],
    "社会服务/本地生活服务": ["service", "private", "platform"], "社会服务/专业服务": ["service", "knowledge", "opc"],
    "社会服务/体育": ["knowledge", "private", "ip", "franchise"], "社会服务/旅游及景区": ["service", "ip", "private"],
    "商贸零售/互联网电商": ["retail", "live", "private", "service"], "商贸零售/贸易": ["arbitrage", "retail", "supply", "service"],
    "计算机/IT服务": ["service", "opc", "subscription"], "传媒/游戏": ["ip", "service", "software"],
    "汽车/汽车服务": ["service", "franchise", "arbitrage"], "电子/消费电子": ["retail", "ip", "service"],
    "t:ai": ["service", "software", "knowledge", "opc"], "t:compute": ["service", "arbitrage", "knowledge"],
    "t:data": ["service", "software", "knowledge"], "t:chip": ["service", "knowledge", "arbitrage"],
    "t:robot": ["service", "arbitrage", "knowledge"], "t:creator": ["ip", "service", "ads", "knowledge"],
    "t:livecom": ["live", "private", "retail", "service"], "t:crossborder": ["retail", "service", "arbitrage"],
    "t:edu": ["knowledge", "ip", "subscription", "private"], "t:local": ["service", "private", "platform"],
    "t:pet": ["retail", "private", "service", "ip"], "t:silver": ["service", "private", "franchise", "knowledge"],
    "t:newcons": ["retail", "ip", "live"], "t:discount": ["franchise", "retail"], "t:tea": ["franchise", "private", "retail"],
    "t:ev": ["service", "arbitrage", "franchise"], "t:energy": ["service", "supply", "arbitrage"],
    "t:lowalt": ["service", "knowledge"], "t:space": ["knowledge", "service"], "t:autodrive": ["service", "knowledge"],
    "t:biotech": ["knowledge", "service"], "t:future": ["knowledge", "service"],
}
L1_MODELS = {
    "计算机": ["software", "service", "opc", "knowledge"], "传媒": ["ip", "ads", "service", "knowledge"],
    "商贸零售": ["retail", "live", "private", "service"], "社会服务": ["service", "private", "knowledge", "franchise"],
    "美容护理": ["private", "franchise", "retail", "ip"], "食品饮料": ["retail", "private", "live", "supply"],
    "农林牧渔": ["live", "retail", "private", "supply"], "纺织服饰": ["retail", "live", "ip", "supply"],
    "轻工制造": ["retail", "live", "ip", "supply"], "家用电器": ["service", "retail", "live"],
    "汽车": ["service", "arbitrage", "franchise"], "医药生物": ["service", "knowledge", "private"],
    "房地产": ["service", "platform", "arbitrage"], "建筑装饰": ["service", "private", "knowledge"],
    "交通运输": ["service", "platform"], "非银金融": ["service", "knowledge", "private"],
}
DEFAULT_MODELS = ["service", "knowledge", "arbitrage"]     # 重资产行业：个人能做的是技术服务、培训咨询、贸易
# 你的情况里没对上几个方向时，拿「市场热、一个人也能做」的方向补上
LIGHT_L1 = {"商贸零售", "社会服务", "美容护理", "食品饮料", "纺织服饰", "轻工制造", "农林牧渔"}      # 不用专门本事也能起步的
LIGHT_TRK = {"t:ai", "t:creator", "t:livecom", "t:crossborder", "t:edu", "t:local", "t:pet", "t:silver", "t:newcons",
             "t:discount", "t:tea"}
LOCAL_DIRS = {"社会服务/酒店餐饮", "社会服务/本地生活服务", "社会服务/体育", "社会服务/教育", "社会服务/旅游及景区", "t:local", "t:tea",
              "t:discount", "t:silver", "t:pet", "商贸零售/一般零售", "商贸零售/专业连锁", "美容护理/医疗美容", "建筑装饰/装修装饰",
              "汽车/汽车服务", "房地产/房地产服务"}
SKIP_DIRS = {"综合/综合"}
_NEG = re.compile(r"(不会|不懂|不太会|不擅长|没有|没|不想|不喜欢|讨厌|不碰|不做)\s*\S{0,3}$")


# ───────────────────────── 你的情况 ─────────────────────────
def normalize(p):
    p = p if isinstance(p, dict) else {}
    out = {}
    try:
        age = int(float(str(p.get("age") or 0).strip() or 0))
    except Exception:
        age = 0
    out["age"] = age if 14 <= age <= 99 else 0
    for k, lim in TEXT_LIMITS.items():
        out[k] = re.sub(r"[ \t\u3000]+", " ", str(p.get(k) or "")).strip()[:lim]
    for k, table in (("status", STATUS), ("money", MONEY), ("time", TIME), ("risk", RISK), ("goal", GOAL)):
        v = str(p.get(k) or "")
        out[k] = v if v in table else ""
    return out


_LOCK = threading.Lock()


def load():
    d = BZ._read_json(PROFILE_FILE, {})
    d = d if isinstance(d, dict) else {}
    return normalize(d.get("profile")), int(d.get("updated") or 0)


def save(p):
    prof = normalize(p)
    now = int(time.time())
    with _LOCK:
        BZ._write_json(PROFILE_FILE, {"profile": prof, "updated": now})
    return prof, now


def enough(prof):
    """能不能开始写方案：阅历、技能、兴趣至少写了一样。"""
    if any(len(prof.get(k) or "") >= 2 for k in ("exp", "skills", "likes")):
        return True, ""
    return False, "先写写你的阅历、技能或兴趣（至少一样），小助才知道往哪个方向帮你挑"


def missing(prof):
    """要紧但还没填的几项（界面上提醒）。"""
    out = []
    if not prof.get("age"):
        out.append("年龄")
    if not any(prof.get(k) for k in ("exp", "skills", "likes")):
        out.append("阅历、技能或兴趣")
    if not prof.get("money"):
        out.append("能拿出来的资金")
    if not prof.get("time"):
        out.append("每周能投入的时间")
    return out


def _first_bit(s, n=14):
    s = re.split(r"[，,。；;、\n]", s or "", 1)[0].strip()
    return s[:n]


def brief(prof):
    """一句话说这个人：35 岁 · 做过 8 年餐饮店长 · 资金 5～20 万。"""
    bits = []
    if prof.get("age"):
        bits.append("%d 岁" % prof["age"])
    who = _first_bit(prof.get("exp")) or ("会" + _first_bit(prof.get("skills"), 10) if prof.get("skills") else "") or \
        ("喜欢" + _first_bit(prof.get("likes"), 10) if prof.get("likes") else "")
    if who:
        bits.append(who)
    if prof.get("money"):
        bits.append("资金 " + MONEY[prof["money"]][0])
    return " · ".join(bits) or "我的情况"


def title(prof):
    return "商业定制方案：" + brief(prof)


def profile_text(prof):
    rows = [("年龄", "%d 岁" % prof["age"] if prof.get("age") else ""), ("所在城市", prof.get("city")),
            ("现在的状态", STATUS.get(prof.get("status"), "")), ("阅历", prof.get("exp")), ("技能", prof.get("skills")),
            ("兴趣", prof.get("likes")), ("能拿出来的资金", MONEY[prof["money"]][0] if prof.get("money") else ""),
            ("每周能投入的时间", TIME.get(prof.get("time"), "")), ("能承受的亏损", RISK.get(prof.get("risk"), "")),
            ("想要的结果", GOAL.get(prof.get("goal"), "")), ("手上的资源", prof.get("res")), ("不想做的", prof.get("avoid")),
            ("其他情况", prof.get("more"))]
    return "\n".join("%s：%s" % (k, v or "（没填）") for k, v in rows)


# ───────────────────────── 配对 ─────────────────────────
_M = {}
_M_LOCK = threading.Lock()


def _matchers():
    if _M:
        return _M
    with _M_LOCK:
        if not _M:
            tx = BZ._tx()
            known = set(tx["l2"]) | set(tx["trk"])
            for _kw, dirs, _mods in SKILL_MAP:              # 表里写错的方向编号直接丢掉，不让它出错
                dirs[:] = [d for d in dirs if d in known]
            for _kw, dirs in AVOID_DIRS:
                dirs[:] = [d for d in dirs if d in known]
            _M.update(skill=BZ._Matcher([(i, kw.split()) for i, (kw, _d, _m) in enumerate(SKILL_MAP)]),
                      avoid=BZ._Matcher([(i, kw.split()) for i, (kw, _m) in enumerate(AVOID_MODELS)]),
                      avoid_d=BZ._Matcher([(i, kw.split()) for i, (kw, _d) in enumerate(AVOID_DIRS)]))
    return _M


def _keep(text, word):
    """「不会编程」「不想做餐饮」里的词不算你会的、喜欢的。"""
    t, w = text.lower(), word.lower()
    pos, any_pos = 0, False
    while True:
        i = t.find(w, pos)
        if i < 0:
            return not any_pos               # 一处都没找到（英文整词匹配大小写不同等）：算数
        any_pos = True
        if not _NEG.search(t[max(0, i - 6):i]):
            return True
        pos = i + len(w)


def _hits(text):
    """一段文字 → ({方向: {词}}, {做法: 次数})，两张表都查。"""
    if not text:
        return {}, {}
    tx, m = BZ._tx(), _matchers()
    dirs, mods = {}, {}
    for idx, words in m["skill"].hits(text).items():
        words = {w for w in words if _keep(text, w)}
        if not words:
            continue
        _kw, ds, ms = SKILL_MAP[idx]
        for d in ds:
            dirs.setdefault(d, {}).setdefault("s", set()).update(words)
        for mm in ms:
            mods[mm] = mods.get(mm, 0) + 1
    for mt in (tx["mi"], tx["mt"]):
        for gid, words in mt.hits(text).items():
            words = {w for w in words if _keep(text, w)}
            if words and gid not in SKIP_DIRS:
                dirs.setdefault(gid, {}).setdefault("t", set()).update(words)
    return dirs, mods


def terms(prof):
    """写方案时挑笔记用的词：你写的里头对上了行业的词，加上技能里的几个词。"""
    out = []
    for k, _n, _w in PARTS:
        d, _m = _hits(prof.get(k) or "")
        for v in d.values():
            out.extend(v.get("s", set()) | v.get("t", set()))
    out += [w.strip() for w in re.split(r"[，,。；;、/\s]+", prof.get("skills") or "")
            if 2 <= len(w.strip()) <= 8 and not re.match(r"^(不|没|别)", w.strip())]
    seen, res = set(), []
    for w in out:
        if w.lower() not in seen and len(w) >= 2:
            seen.add(w.lower())
            res.append(w)
    return res[:24]


_MKT = {"at": 0, "data": None}
_MKT_LOCK = threading.Lock()


def market(force=False):
    """市场雷达最近 7 天每个方向的热度（一分钟内重复用）：{id: (7 天条数, 24 小时条数, 升温/降温)}、热度榜、升温话题。"""
    now = time.time()
    with _MKT_LOCK:
        if not force and _MKT["data"] and now - _MKT["at"] < 60:
            return _MKT["data"]
    tx = BZ._tx()
    try:
        o = BZ._overview_market(7)
    except Exception as e:
        BZ._log("商业定制：读不到市场雷达的数据（%s），先只按你的情况配" % e)
        o = {}
    heat = o.get("heat") or {}
    c = o.get("counts") or {}
    W, T = int(c.get("window") or 0), int(c.get("today") or 0)
    uni = [d for d in list(tx["l2"]) + list(tx["trk"]) if d not in SKIP_DIRS]
    h = {}
    for d in uni:
        n7, n24 = (heat.get(d) or [0, 0])[:2]
        tr = ""
        if n7 >= 20 and T >= 50 and W >= T * 1.3:          # 窗口里不止一天的数据才比较：这一天的占比 ÷ 7 天的占比
            x = (n24 / T) / (n7 / W)
            tr = "up" if x >= 1.3 else "down" if x <= 0.7 else "flat"
        h[d] = (int(n7), int(n24), tr)
    mx = max([v[0] for v in h.values()] or [0])
    nz = sorted(v[0] for v in h.values() if v[0] > 0)
    mid = nz[len(nz) // 2] if nz else 0                  # 一半方向的新闻比它多、一半比它少：图上「热不热」的分界线
    hot = sorted((d for d in uni if h[d][0] > 0), key=lambda d: -h[d][0])[:12]
    data = {"heat": h, "max": mx, "mid": mid, "window": W, "today": T, "at": int(o.get("now") or now),
            "hot": [{"id": d, "name": _name(d), "n7": h[d][0], "n24": h[d][1], "trend": h[d][2]} for d in hot],
            "rising": [r.get("k") for r in (o.get("rising") or [])[:12] if r.get("k")]}
    with _MKT_LOCK:
        _MKT.update(at=now, data=data)
    return data


def _name(d):
    tx = BZ._tx()
    if d in tx["l2"]:
        return tx["l2"][d]["name"]
    if d in tx["trk"]:
        return tx["trk"][d]["name"]
    return d.split("/")[-1]


def _where(d):
    """方向属于哪儿：二级行业 → (一级行业, 板块)；赛道 → ("新兴赛道", "")。"""
    tx = BZ._tx()
    if d in tx["l2"]:
        l1 = tx["l2"][d]["l1"]
        sec = (tx["sec"].get("sec:" + tx["l1"][l1]["sec"]) or {}).get("name", "")
        return l1, sec
    return "新兴赛道", ""


def _need_txt(need):
    return "几千元起" if need < 1 else "约 %s 万起" % (("%g" % need))


def _pick_models(did, mb, prof, avoid_m):
    """给一个方向挑 3 种做法，按你的资金、时间、能承受的亏损排；返回 (做法列表, 可行度 0～1)。"""
    l1 = _where(did)[0]
    pref = DIR_MODELS.get(did) or L1_MODELS.get(l1) or DEFAULT_MODELS
    cap = MONEY[prof["money"]][1] if prof.get("money") else None
    tm, rk, goal = prof.get("time"), prof.get("risk"), prof.get("goal")
    cands = set(pref) | {m for m, v in mb.items() if v >= 1.5}
    rows = []
    for m in cands:
        if m not in MODEL_NEED:
            continue
        need, t_need, r_need = MODEL_NEED[m]
        s, money, bad = 0.0, "", 0
        if m in pref:
            s += 2.2 - 0.35 * pref.index(m)
        s += min(3.0, mb.get(m, 0))
        if cap is not None:
            if need > cap * 2:
                s -= 5
                money = "no"
            elif need > cap:
                s -= 1.5
                money = "tight"
            else:
                money = "ok"
        pen_t = {"side": {"full": 2.5, "part": 0.8}, "part": {"full": 1.0}}.get(tm, {}).get(t_need, 0)
        pen_r = {"safe": {"high": 2.5, "mid": 0.6}, "mid": {"high": 0.8}}.get(rk, {}).get(r_need, 0)
        s -= pen_t + pen_r
        bad += (pen_t >= 1) + (pen_r >= 1)
        if goal == "extra" and t_need == "side":
            s += 0.5
        if goal == "big" and m in ("platform", "franchise", "supply", "subscription", "software") and (cap or 0) >= 20:
            s += 1.0
        if m in avoid_m:
            s -= 6
            bad += 2
        rows.append((s, m, money, bad))
    rows.sort(key=lambda x: (-x[0], x[1]))
    keep = [r for r in rows if r[0] > -1][:3] or rows[:1]
    out = [{"id": "m:" + m, "key": m, "name": MODEL_NAME.get(m, m), "desc": MODEL_DESC.get(m, ""),
            "need": _need_txt(MODEL_NEED[m][0]), "money": money} for _s, m, money, _b in keep]
    if not keep:
        return out, 0.0
    _s, _m, money, bad = keep[0]
    feas = {"ok": 1.0, "": 0.85, "tight": 0.55, "no": 0.15}[money] - 0.25 * min(2, bad)
    return out, max(0.0, feas)


_SORTED = {"src": None, "list": []}
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _good_title(t):
    """像一条新闻的标题：至少 6 个汉字，或 5 个以上英文单词。企业官网上抓来的「Shipping」「CATEGORIES」这类导航文字不要。"""
    t = (t or "").strip()
    if len(_CJK.findall(t)) >= 6:
        return True
    return len(re.findall(r"[A-Za-z]{2,}", t)) >= 5 and len(t) >= 24


def _news(ids, per=2, days=7):
    """这几个方向最近的新闻，每个 per 条（新的在前）。先挑有发布日期的，不够再用日期不详的。"""
    try:
        items = BZ._radar_items()
    except Exception:
        return {}
    if _SORTED["src"] is not items:
        _SORTED.update(src=items, list=sorted(items, key=lambda x: -x["ts"]))
    cut = time.time() - days * 86400
    want, out = set(ids), {i: [] for i in ids}
    for undated in (False, True):
        for it in _SORTED["list"]:
            if it["ts"] < cut:
                break
            if bool(it.get("approx")) != undated or not _good_title(it["title"]):
                continue
            for k in want & (set(it["trk"]) | set(it["ind"])):
                lst = out[k]
                if len(lst) < per and all(x["title"] != it["title"] for x in lst):
                    lst.append(BZ._pub(it))
        if all(len(v) >= per for v in out.values()):
            break
    for k in out:                                        # 两轮挑的合在一起，还是新的在前
        out[k].sort(key=lambda x: -x["ts"])
    return out


def _opps(prof_words):
    """机会看板：每条机会对上了哪些方向；和你的情况沾边的（你写的词出现在机会里）。"""
    data = BZ._read_json(BZ.OPPS_FILE, [])
    data = data if isinstance(data, list) else []
    by_dir, yours = {}, []
    lw = [w for w in prof_words if len(w) >= 2]
    for o in data:
        if o.get("status") == "dropped":
            continue
        text = " ".join(str(o.get(k) or "") for k in ("title", "who", "how"))
        d, _m = _hits(text)
        brief_o = {"id": o.get("id"), "title": o.get("title", ""), "who": o.get("who", ""), "cost": o.get("cost", ""),
                   "status": o.get("status", "")}
        for gid in d:
            by_dir.setdefault(gid, []).append(brief_o)
        tl = text.lower()
        hit = list(dict.fromkeys(w for w in lw if w.lower() in tl))
        if hit:
            yours.append((len(hit), dict(brief_o, words=hit[:4])))
    yours.sort(key=lambda x: -x[0])
    return by_dir, [y for _n, y in yours[:4]], data


def preview(prof, n=8, news_per=2):
    """先配一遍（不用 AI）：你的情况 × 市场雷达热度 → 最配你的方向，每个带做法、资金够不够、最新新闻、机会看板里相关的。"""
    prof = normalize(prof)
    t0 = time.time()
    mk = market()
    tx = BZ._tx()
    raw, why, mb, words_all = {}, {}, {}, []
    for key, label, w in PARTS:
        text = prof.get(key) or ""
        if not text:
            continue
        dirs, mods = _hits(text)
        for d, v in dirs.items():
            s, t = v.get("s", set()), v.get("t", set()) - v.get("s", set())
            raw[d] = raw.get(d, 0.0) + w * (min(3, len(s)) * 1.0 + min(2, len(t)) * 0.7)
            for x in sorted(s) + sorted(t):
                why.setdefault(d, [])
                if all(x != y[1] for y in why[d]):
                    why[d].append((label, x))
            words_all.extend(s | t)
        for m, c in mods.items():
            mb[m] = mb.get(m, 0.0) + w * 0.4 * c
    av_text = prof.get("avoid") or ""
    avoid_m, avoid_d = set(), set()
    if av_text:
        for idx in _matchers()["avoid"].hits(av_text):
            avoid_m.update(AVOID_MODELS[idx][1])
        for idx in _matchers()["avoid_d"].hits(av_text):            # v188：「不碰餐饮」这类
            avoid_d.update(AVOID_DIRS[idx][1])
        for mt in (tx["mi"], tx["mt"]):
            avoid_d.update(mt.hits(av_text).keys())
    heat, mx = mk["heat"], mk["max"]
    rows = []

    def build(d, fill=False):
        if d not in heat:
            return None
        n7, n24, tr = heat[d]
        fit = 0 if fill else int(round(100 * (1 - math.exp(-raw.get(d, 0) / 5.0))))
        if d in avoid_d:
            fit = int(round(fit * 0.15))
        hp = int(round(100 * math.log1p(n7) / math.log1p(mx))) if mx else 0
        mods, feas = _pick_models(d, mb, prof, avoid_m)
        l1, sec = _where(d)
        money = mods[0]["money"] if mods else ""
        score = 0.6 * fit + 0.3 * hp + 10 * feas + {"up": 4, "down": -3}.get(tr, 0) - (40 if d in avoid_d else 0)
        return {"id": d, "name": _name(d), "kind": "trk" if d.startswith("t:") else "l2", "l1": l1, "sec": sec,
                "fit": fit, "heat": hp, "n7": n7, "n24": n24, "trend": tr, "score": round(score, 1),
                "why": [list(x) for x in why.get(d, [])[:4]], "models": mods, "feas": round(feas, 2),
                "money": money, "money_txt": {"ok": "资金够起步", "tight": "资金偏紧", "no": "资金不够，要换更轻的做法"}.get(money, ""),
                "avoid": d in avoid_d, "fill": fill, "local": d in LOCAL_DIRS}

    for d in raw:
        if d in SKIP_DIRS:
            continue
        r = build(d)
        if r and r["fit"] > 0:
            rows.append(r)
    rows.sort(key=lambda r: -r["score"])
    seen_why = {}
    for r in rows:                                       # 理由完全一样的方向（同一组词对上的几个行业），后面的每重复一次往后排一点
        sig = tuple(sorted(w for _p, w in r["why"]))
        k = seen_why.get(sig, 0)
        if sig and k:
            r["score"] -= 6 * k
        seen_why[sig] = k + 1
    rows.sort(key=lambda r: -r["score"])
    picked = [r for r in rows if not r["avoid"]][:n]
    if len(picked) < 4:                                  # 对上的太少：拿「市场热、一个人也能做」的补上
        have = {r["id"] for r in picked}
        pool = [d for d in heat if d not in have and d not in avoid_d and d not in SKIP_DIRS and
                (d in LIGHT_TRK or (not d.startswith("t:") and _where(d)[0] in LIGHT_L1))]
        pool.sort(key=lambda d: -heat[d][0])
        fill = [r for r in (build(d, fill=True) for d in pool[:max(0, 6 - len(picked))]) if r and r["n7"] > 0]
        picked += sorted(fill, key=lambda r: -r["score"])
    news = _news([r["id"] for r in picked], per=news_per) if news_per else {}
    by_dir, yours, all_opps = _opps(list(dict.fromkeys([w for w in words_all] + terms(prof)[:12])))
    for r in picked:
        r["news"] = news.get(r["id"], [])
        r["opps"] = by_dir.get(r["id"], [])[:2]
    return {"ok": True, "cands": picked, "hot": mk["hot"], "rising": mk["rising"], "opps_you": yours,
            "n_opps": len(all_opps), "market": {"window": mk["window"], "today": mk["today"], "at": mk["at"], "max": mx, "mid": mk.get("mid", 0)},
            "missing": missing(prof), "enough": enough(prof)[0], "brief": brief(prof), "avoid_models": sorted(avoid_m),
            "ms": int((time.time() - t0) * 1000)}


def get():
    prof, upd = load()
    return {"ok": True, "profile": prof, "updated": upd, "preview": preview(prof),
            "options": {"status": STATUS, "money": {k: v[0] for k, v in MONEY.items()}, "time": TIME, "risk": RISK, "goal": GOAL}}


def post(body):
    body = body if isinstance(body, dict) else {}
    prof = normalize(body.get("profile"))
    upd = 0
    if body.get("save", True):
        prof, upd = save(prof)
    return {"ok": True, "profile": prof, "updated": upd, "preview": preview(prof)}


# ───────────────────────── 写方案（提示词、联网查什么、解析） ─────────────────────────
STEPS = ["读软件里的数据", "上网查资料", "AI 定制方案", "存方案"]
STRUCT = [
    "一句话结论（最推荐你做什么、为什么，两三句话）",
    "你的情况（优势、短板和限制；资金、时间、年龄阶段分别意味着什么）",
    "市场上现在什么热（引用资料①②③里市场雷达的数据，说清楚这些热度和你有什么关系）",
    "推荐方向一览",
    "方向详解",
    "三个方向怎么选（先做哪个、能不能组合起来做）",
    "前 90 天行动计划",
    "不建议你碰的方向（2～4 个，每个写清楚为什么不适合你）",
    "机会清单",
    "接下来盯什么（在超能小助的市场雷达和行业地图上盯哪些行业、哪些信号）",
    "信息来源",
]
MARKERS = ["推荐方向一览", "行动计划", "机会清单"]

_HEAD = ("今天是 {today}。你是一位经验丰富的创业顾问和商业分析师，正在为一位具体的用户量身定制「适合他现在做的行业和赚钱方式」，"
         "方案写给他本人看，直接用「你」称呼他。\n"
         "写法：说人话、具体、少空话；每一条建议都要落到他这个人身上——他的年龄、阅历、技能、兴趣、资金、时间和能承受的亏损，"
         "说清楚为什么适合他；关键数字（市场规模、启动资金、价格、利润）写清楚是多少、出自哪里；拿不准的写「待核实」，"
         "不要编造数据和来源；引用下面的资料时，标上【雷达】【机会看板】【笔记N】或网页的名字。你如果能联网搜索，"
         "请再搜一搜，补充最新的数据和真实案例，并把网址写进「信息来源」。\n"
         "分寸：他的资金和阅历够不上的，不要推荐要大笔投入、专业牌照或重资产的方向；不要因为年龄给刻板的判断，"
         "只从精力、学新东西的速度、人脉和经验这些实际影响来分析；资料①是小助按关键词初步算的，可以不全采用，但要说明理由。\n"
         "格式：全文用 Markdown；第一行写「# {title}」；下面只用我列出的二级标题（「## 」开头，括号里的说明不要写进标题），"
         "按顺序写；不要开场白，不要寒暄，不要反问我。\n\n")
_PLAN_FMT = ("「## 推荐方向一览」下面严格按这个格式写 3 行，每行一个方向，按推荐程度从高到低，全角竖线「｜」分隔，八项都要有，不要写成表格：\n"
             "- 方向一｜行业：具体到细分行业或赛道｜做法：用什么方式赚钱（一句话）｜匹配度：0～100 的整数｜启动资金：约多少钱｜"
             "回本周期：大概多久｜风险：低/中/高｜一句话：为什么适合你\n"
             "「## 方向详解」里每个方向一个三级标题「### 方向一：行业 + 做法」，每个方向都写这几块：为什么适合你；"
             "市场依据（引用资料里的数据和新闻）；怎么赚钱（卖什么、卖给谁、怎么定价、客户从哪来）；钱怎么花（启动资金分成几块、各多少）；"
             "收入预估（保守 / 一般 / 乐观三种，写清楚假设）；第一步做什么；主要风险和应对办法。\n"
             "「## 前 90 天行动计划」分四段：第 1～2 周、第 3～4 周、第 2 个月、第 3 个月；每段写做什么、要验证哪个数字、"
             "到什么情况就该停下或换方向。\n\n")
_TREND = {"up": "，在升温", "down": "，在降温", "flat": "，平稳"}


def web_queries(prof, cands, deep):
    """联网查什么：排在前面的三个方向各查「怎么赚钱、要多少钱」；深入时再查真实案例和「这个年纪、这些本事能做什么」。"""
    y = datetime.date.today().year
    pool = [c for c in cands if not c.get("fill")] or list(cands)
    top, used = [], set()
    for c in pool:                                       # 三个方向尽量不在同一个一级行业里，查得更全
        g = c["l1"] if c.get("kind") == "l2" else c["id"]
        if g not in used:
            used.add(g)
            top.append(c)
        if len(top) == 3:
            break
    top += [c for c in pool if c not in top][:3 - len(top)]
    qs = []
    for c in top:
        m = (c.get("models") or [{}])[0].get("name", "")
        city = prof.get("city") if prof.get("city") and c["id"] in LOCAL_DIRS else ""
        qs.append(" ".join(x for x in (city, c["name"], m, "创业 启动资金 利润", str(y)) if x))
    if not deep:
        return qs[:3]
    for c in top[:2]:
        qs.append("%s 小成本 创业 真实案例 %d" % (c["name"], y))
    sk = _first_bit(prof.get("skills"), 8) or _first_bit(prof.get("exp"), 10)
    if prof.get("age") or sk:
        qs.append(" ".join(x for x in (("%d岁" % prof["age"]) if prof.get("age") else "", sk, "创业 副业 做什么", str(y)) if x))
    return qs[:6]


def _cands_text(pv):
    out = []
    for i, c in enumerate(pv.get("cands") or [], 1):
        heat = "最近 7 天 %d 条新闻、最近 24 小时 %d 条%s" % (c["n7"], c["n24"], _TREND.get(c["trend"], ""))
        why = "、".join("%s「%s」" % (p, w) for p, w in c["why"]) if c.get("why") else "你的情况里没直接对上，因为市场热、一个人也能做才列进来"
        mods = "、".join("%s（%s）" % (m["name"], m["need"]) for m in c.get("models") or [])
        line = "%d. %s（%s）｜匹配度 %d｜%s｜对上的地方：%s｜适合的做法：%s" % (
            i, c["name"], c["l1"], c["fit"], heat, why, mods or "待定")
        if c.get("money_txt"):
            line += "｜" + c["money_txt"]
        if c.get("opps"):
            line += "｜机会看板里相关的：" + "；".join(o["title"] for o in c["opps"])
        out.append(line)
    return "\n".join(out) or "（没配出来）"


def _market_text(pv):
    hot = "、".join("%s %d（%d%s）" % (h["name"], h["n7"], h["n24"], "↑" if h["trend"] == "up" else "↓" if h["trend"] == "down" else "")
                   for h in pv.get("hot") or [])
    m = pv.get("market") or {}
    s = "最近 7 天一共抓到 %d 条新闻，最近 24 小时 %d 条。\n" % (m.get("window", 0), m.get("today", 0))
    s += "新闻最多的方向：%s\n" % (hot or "（市场雷达还没抓到新闻）")
    if pv.get("rising"):
        s += "正在升温的话题：%s\n" % "、".join(pv["rising"])
    return s


def _news_text(pv, budget=6000):
    out, used = [], 0
    for c in (pv.get("cands") or [])[:6]:
        if not c.get("news"):
            continue
        block = "【%s】\n" % c["name"] + "".join("- [%s] %s：%s%s\n" % (
            "日期不详" if it.get("approx") else (it.get("date") or "日期不详"), it.get("from") or it.get("who") or "", it["title"],
            (" —— " + it["text"][:90]) if it.get("text") and it["title"][:12] not in it["text"] else "") for it in c["news"])
        if used + len(block) > budget:
            break
        out.append(block)
        used += len(block)
    return "".join(out) or "（这些方向最近 7 天没抓到新闻）"


def _opps_text(pv, opps):
    yours = {o["id"]: o.get("words") for o in pv.get("opps_you") or []}
    st = {"new": "新发现", "watch": "关注", "testing": "验证中", "doing": "在做", "dropped": "放弃"}
    out = []
    for o in [x for x in opps if x.get("status") != "dropped"][:12]:
        s = "- %s｜适合谁：%s｜怎么切入：%s｜启动成本：%s｜状态：%s" % (
            o.get("title", ""), o.get("who") or "没写", (o.get("how") or "没写")[:120], o.get("cost") or "没写", st.get(o.get("status"), ""))
        if yours.get(o.get("id")):
            s += "｜和他沾边：%s" % "、".join(yours[o["id"]])
        out.append(s)
    return "\n".join(out) or "（机会看板还是空的）"


def prompt(spec, pv, notes, web_txt):
    prof = spec["profile"]
    opps = BZ._read_json(BZ.OPPS_FILE, [])
    opps = opps if isinstance(opps, list) else []
    parts = [_HEAD.format(today=datetime.date.today().isoformat(), title=spec["title"]),
             "任务：根据这位用户的情况，结合超能小助市场雷达的实时数据、机会看板和网上的资料，给他挑出最适合他现在做的 3 个方向"
             "（每个方向 = 一个具体的行业 + 一种赚钱的做法），并写清楚怎么开始。\n\n",
             "=== 他的情况 ===\n" + profile_text(prof) + "\n\n",
             "二级标题（按顺序）：\n" + "\n".join("## " + s for s in STRUCT) + "\n\n",
             _PLAN_FMT, BZ._OPP.format(n="4～6"),
             "=== 资料①：超能小助按他的情况和市场数据先配出来的候选方向（匹配度＝和他的情况对得上多少，0～100；新闻条数来自市场雷达）===\n%s\n\n"
             % _cands_text(pv),
             "=== 资料②：市场雷达的整体热度（括号里是最近 24 小时的条数，↑ 表示这一天的占比明显升高，↓ 是明显降低）===\n%s\n" % _market_text(pv),
             "=== 资料③：候选方向最近的新闻（市场雷达抓到的，新的在前）===\n%s\n" % _news_text(pv),
             "=== 资料④：机会看板里已经记下的机会 ===\n%s\n\n" % _opps_text(pv, opps),
             "=== 资料⑤：他自己收藏、整理过的笔记里相关的（%d 篇）===\n%s\n" % (len(notes), BZ._fmt_notes(notes, 6000) or "（没有相关的笔记）"),
             "=== 资料⑥：小助刚从网上搜到的网页摘录 ===\n%s\n" % ((web_txt or "").strip() or "（这次没有联网或没搜到）"),
             "\n请开始写，第一行是「# %s」。" % spec["title"]]
    return "".join(parts)


_PLAN_KEYS = [("回本周期", "payback"), ("启动资金", "money"), ("匹配度", "match"), ("一句话", "why"), ("行业", "ind"),
              ("做法", "model"), ("风险", "risk"), ("回本", "payback")]
_PLAN_RX = re.compile(r"^\**\s*(行业|做法|匹配度|启动资金|回本周期|回本|风险|一句话)\s*\**\s*[：:]\s*\**\s*(.+?)\s*\**$")


def _plan_key(h):
    return next((v for k, v in _PLAN_KEYS if k in h), None)


def parse_plans(md):
    """方案里「## 推荐方向一览」→ [{rank, ind, model, match, money, payback, risk, why}]。
    按约定的「｜」格式写的、写成了表格的，都认。认不出返回 []（界面就只显示全文）。"""
    lines = (md or "").splitlines()
    a = next((i for i, ln in enumerate(lines) if re.match(r"^\s*#{1,4}\s*.*推荐方向一览", ln)), -1)
    if a < 0:
        return []
    out, header = [], None
    for ln in lines[a + 1:a + 40]:
        s = ln.strip()
        if re.match(r"^#{1,4}\s", s):
            break
        if not s or re.match(r"^\|?\s*:?-{2,}", s):
            continue
        cells = [c.strip() for c in re.split(r"\s*[｜|]\s*", s.strip().strip("|").strip())]
        if header is None and s.startswith("|") and sum(1 for c in cells if _plan_key(c)) >= 2 and not any(_PLAN_RX.match(c) for c in cells):
            header = cells                                       # 表格的表头
            continue
        d = {}
        first = re.sub(r"^(?:[-*•·]|\d+\s*[.、．)])\s*", "", cells[0]).strip().strip("*").strip()
        if header and not any(_PLAN_RX.match(c) for c in cells):
            for h, c in zip(header, cells):
                k = _plan_key(h)
                if k:
                    d[k] = c.strip("*").strip()
            if not _plan_key(header[0]):
                d["rank"] = first
        else:
            for i, p in enumerate([first] + cells[1:]):
                m = _PLAN_RX.match(p.strip())
                if m:
                    d[dict(_PLAN_KEYS)[m.group(1)]] = m.group(2).strip()
                elif i == 0 and p:
                    d["rank"] = p[:12]
        if not (d.get("ind") or d.get("model")):
            continue
        mm = re.search(r"\d{1,3}", d.get("match") or "")
        d["match"] = max(0, min(100, int(mm.group(0)))) if mm else None
        r = d.get("risk") or ""
        d["risk"] = "高" if "高" in r else "低" if "低" in r else "中" if "中" in r else r[:6]
        d["rank"] = d.get("rank") or "方向" + "一二三四五"[min(len(out), 4)]
        for k in ("ind", "model", "money", "payback", "why"):
            d[k] = (d.get(k) or "")[:120]
        out.append({k: d.get(k) for k in ("rank", "ind", "model", "match", "money", "payback", "risk", "why")})
        if len(out) >= 5:
            break
    return out
