"""超能小助 · 内容标签（v140 新增）

「加工 → 已加工」里每篇文章除了「大类 · 子类」，再按内容贴 2～4 个标签，方便按话题归类、筛选。

  · 标签来自一张固定的标签表（VOCAB），同一个话题永远用同一个名字（比如都叫「一人公司」，
    不会一会儿「OPC」一会儿「单人公司」），这样点一个标签就能看到所有讲这件事的文章。
  · 怎么贴：看这篇的标题、AI 给的关键词、一句话概括、核心观点、原来的标签，再看正文里提到的次数，
    每个标签打分，分够的才贴，最多 4 个。不用问 AI，新加工好的文章打开「已加工」时自动贴。
  · v140 已加工的文章：标签是对着内容逐篇核对过的（tag_seed.json），第一次启动时导进来。
  · 你手动改过的（by=you），以后不会再被自动改。
  · 存在 memory/video_notes/_tags.json：{文件名: {t: [标签…], by: seed/rule/you, at: 时间}}，不改笔记文件。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

# ════════════════════ 标签表 ════════════════════
# 每项：(组, 标签, 强匹配, 正文最少次数, 选项)
#   强匹配：在标题、AI 关键词、一句话概括、核心观点、原标签里找；
#   正文最少次数：None = 不看正文；数字 = 正文里提到这么多次才加分（专有名词用）；
#   选项：cats = 只给这些大类的文章贴；xcats = 这些大类不贴；need = 标题/关键词/概括里还得提到这个。
# 组只是界面上分组显示用，标签本身不分大类（讲 AI 创业的商业文章也能贴「Agent智能体」）。
_AI_CTX = r"ai|人工智能|大模型|gpt|claude|智能体|agent|机器人|算法|模型"
VOCAB = [
    # ── AI ──
    ("AI", "Agent智能体", r"agent|智能体|智能代理|ai ?代理|openclaw|manus|多智能体|数字员工|hermes|computer ?use|操作电脑|计算机操作|电脑操作", 4, {}),
    ("AI", "GitHub开源", r"github|开源项目|开源工具|开源社区|涨星|star数|stars", 2, {}),
    ("AI", "Claude", r"claude|anthropic|克劳德", 3, {}),
    ("AI", "OpenAI", r"openai|chatgpt|gpt-?[3-6]|(?<![a-z])gpt(?![a-z])|奥特曼|altman|sora", 4, {}),
    ("AI", "Codex", r"codex", 3, {}),
    ("AI", "DeepSeek", r"deepseek|深度求索", 2, {}),
    ("AI", "Grok", r"grok|(?<![a-z])xai(?![a-z])", 2, {}),
    ("AI", "谷歌Gemini", r"gemini|deepmind|谷歌|google|哈萨比斯|hassabis", 3, {}),
    ("AI", "国产大模型", r"通义|千问|qwen|kimi|月之暗面|豆包|智谱|(?<![a-z])glm|文心一言|minimax|混元|元宝", 3, {}),
    ("AI", "英伟达", r"英伟达|nvidia|黄仁勋|老黄|cuda", 3, {}),
    ("AI", "芯片算力", r"芯片|半导体|算力|gpu|光刻|台积电|制程|数据中心|tpu|hbm", 4, {}),
    ("AI", "Vibe Coding", r"vibe ?coding|氛围编程|零代码|不会(?:写)?代码|没写过代码", 2, {}),
    ("AI", "程序员", r"程序员|码农|写代码|软件工程师|(?<![a-z])java(?![a-z])|python|前端|后端|编程", None, {}),
    ("AI", "AI知识库", r"rag(?![a-z])|向量数据库|向量检索|检索增强|ai ?知识库|知识库", 3, {"cats": ["AI"]}),
    ("AI", "提示词", r"提示词|prompt|咒语", 3, {}),
    ("AI", "工作流自动化", r"工作流|workflow|自动化工作|自动化流程|流程自动化|自动执行|自动化办公|n8n|coze|扣子|dify|zapier|rpa|(?<![a-z])skills?(?![a-z])", None, {"need": _AI_CTX + r"|coze|扣子|skill"}),
    ("AI", "AI做内容", r"aigc|数字人|ai ?(?:视频|绘画|画图|生图|配音|剪辑|写作|文案|做视频|生成视频|动画)|视频生成|图像生成|文生图|文生视频|可灵|即梦|midjourney|remotion|nano ?banana", 3, {}),
    ("AI", "本地部署", r"本地部署|本地模型|开源模型|开源大模型|ollama|私有化部署|离线运行|本地运行", 2, {}),
    ("AI", "大模型原理", r"transformer|预训练|微调|强化学习|rlhf|scaling|参数量|推理模型|思维链|注意力机制|蒸馏|上下文窗口|幻觉|涌现|token", 4, {}),
    ("AI", "AI安全", r"ai ?安全|对齐|alignment|越狱|网络安全|漏洞|黑客|安全风险|失控|红队|cyber|恶意", 4, {"cats": ["AI"]}),
    ("AI", "AI监管", r"监管|出口管制|管制|禁令|立法|法案|制裁|实体清单|禁售", 4, {"cats": ["AI", "科技", "社会", "财经"], "need": _AI_CTX + r"|芯片"}),
    ("AI", "AI冲击就业", r"失业|取代|替代|淘汰|就业|饭碗|裁员|岗位|被ai|没工作|抢工作", None, {"need": _AI_CTX}),
    ("AI", "AI创业", r"ai ?(?:创业|搞钱|赚钱|副业|变现|产品|公司)|用ai.{0,8}(?:赚|创业|变现|副业|做产品)|ai ?时代.{0,6}(?:机会|赚钱|创业)|ai ?应用", None, {}),
    ("AI", "AI科研", r"科研|科学家|科学发现|数学|定理|证明|蛋白|alphafold|新药|论文", None, {"cats": ["AI"]}),
    ("AI", "AI医疗", r"医疗|医生|诊断|病人|医院|看病", None, {"cats": ["AI"]}),
    ("AI", "AI辅助学习", r"ai ?(?:学习|教育|教学|辅导|老师|家教|学英语)|用ai.{0,6}学", None, {}),
    # ── 商业 ──
    ("商业", "一人公司", r"一人公司|(?<![a-z])opc(?![a-z])|超级个体|一个人(?:的)?公司|单人公司|solopreneur|一人企业|个人公司|自己就(?:可以)?是一家公司", 2, {}),
    ("商业", "用户需求", r"需求|痛点|刚需|用户画像", None, {"xcats": ["教育"]}),
    ("商业", "低成本试错", r"低成本|试错|零成本|0成本|小步快跑|最小可行|mvp|快速验证|先跑通|小成本", None, {}),
    ("商业", "副业", r"副业|兼职|业余时间|下班后|第二收入|斜杠|多份收入|主业之外", 3, {}),
    ("商业", "知识付费", r"知识付费|知识变现|卖课|训练营|付费社群|知识产品|咨询服务|陪跑|做课|课程变现|付费课", None, {"xcats": ["教育"]}),
    ("商业", "技能变现", r"技能变现|经验变现|接单|自由职业|技能赚钱|手艺|把技能|技能卖|技能换钱|经验卖", None, {}),
    ("商业", "信息差", r"信息差|认知差|套利|差价", None, {}),
    ("商业", "价值交换", r"价值交换|价值创造|创造价值|提供价值|交换价值|为别人创造|帮别人解决|解决别人", None, {}),
    ("商业", "商机风口", r"商机|风口|红利|机会识别|发现机会|抓住机会|创业机会|商业机会|蓝海|新机会", None, {}),
    ("商业", "营销获客", r"营销|获客|引流|私域|转化率|成交|销售|推广|投放|复购|卖货|种草|拉新", None, {}),
    ("商业", "品牌打造", r"(?<!个人)品牌", None, {"xcats": ["内容创作"]}),
    ("商业", "定价", r"定价|价格战|涨价|降价|高价|低价|溢价", None, {}),
    ("商业", "创业故事", r"创业经历|创业故事|创始人|白手起家|从零到|年入|年赚|负债|逆袭|翻身|起家|发家|第一桶金", None, {}),
    ("商业", "做产品", r"产品经理|产品思维|产品设计|用户体验|做产品|产品开发|产品迭代|用户反馈|pmf|打磨产品", None, {}),
    ("商业", "独立开发", r"独立开发|indie|上架|做了(?:一)?(?:个|款)(?:app|应用|网站|工具|插件|产品)|开发了(?:一)?(?:个|款)", None, {}),
    ("商业", "实体店", r"实体店|开店|餐饮|饭店|火锅|奶茶|咖啡店|门店|摆摊|加盟|小店|烧烤|面馆|超市|素食餐厅", 3, {}),
    ("商业", "电商", r"电商|淘宝|拼多多|抖店|带货|亚马逊|选品|闲鱼|网店", 3, {"xcats": ["AI", "科技"]}),
    ("商业", "出海", r"出海|海外市场|外贸|跨境|海外用户|全球化", None, {}),
    ("商业", "财税注册", r"注册公司|公司注册|报税|税务|营业执照|发票|财税|个税|公司架构|记账", None, {}),
    ("商业", "合伙股权", r"合伙|股权|股东|期权|分红|控制权", None, {}),
    ("商业", "消费品牌", r"胖东来|蜜雪|瑞幸|喜茶|海底捞|星巴克|麦当劳|名创优品|泡泡玛特|茅台|可口可乐|爱马仕|宜家|costco|沃尔玛|优衣库|李宁|安踏|爱奇艺", 3, {}),
    # ── 成长 ──
    ("成长", "知识管理", r"知识管理|知识卡片|卡片笔记|做笔记|记笔记|笔记法|笔记系统|第二大脑|obsidian|notion|flomo|知识资产|知识系统|知识库|知识框架|搭建知识", None, {}),
    ("成长", "读书阅读", r"读书|阅读(?!量)|看书|书单|好书|一本书|这本书|书籍|读完|教科书", None, {}),
    ("成长", "写作", r"写作|写文章|日更|每日写作|文笔|写东西|写书|写日记|输出文章", None, {}),
    ("成长", "刻意练习", r"刻意练习|一万小时|反馈循环|及时反馈|学习闭环|反复练习|练习方法", None, {}),
    ("成长", "自学能力", r"自学|主动学习|学习能力|终身学习|持续学习|学会学习|学习力|学以致用|实践学习|高效学习|学习方法", None, {"xcats": ["教育"]}),
    ("成长", "认知升级", r"认知升级|认知提升|认知觉醒|提升认知|认知边界|认知转变|认知水平|认知迭代|打破认知|认知差", None, {}),
    ("成长", "独立思考", r"独立思考|批判性思维|深度思考|思考能力|思辨|理性思考|逻辑思维|思考方式", None, {}),
    ("成长", "思维模型", r"思维模型|第一性原理|系统思维|逆向思维|二阶思维|复利思维|杠杆思维|飞轮|概率思维|贝叶斯|结构化思维|费曼|模型思维|杠杆", None, {}),
    ("成长", "认知偏差", r"认知偏差|损失厌恶|幸存者偏差|锚定效应|确认偏误|心理账户|卡尼曼|达克效应|邓宁|偏差", None, {}),
    ("成长", "长期主义", r"长期主义|复利|长期积累|时间的朋友|长期投入|长期价值|慢慢变富|长期坚持", None, {}),
    ("成长", "时间管理", r"时间管理|时间分配|番茄|日程|时间规划|管理时间|时间块|待办|时间安排", None, {}),
    ("成长", "习惯自律", r"习惯|自律|早起|戒掉|戒手机|打卡", None, {}),
    ("成长", "行动力", r"行动力|执行力|拖延|立刻行动|马上行动|行动起来|知行合一|空想|先做起来|去做|动手做", None, {}),
    ("成长", "目标管理", r"设定目标|目标设定|目标管理|目标拆解|拆解目标|定目标|小目标|目标感|明确目标|目标明确|okr|长期目标|实现目标|达成目标|完成目标|你的目标|朝着.{0,4}目标", None, {}),
    ("成长", "专注力", r"专注|注意力|心流|深度工作|分心|碎片化", None, {}),
    ("成长", "人生方向", r"迷茫|人生方向|找方向|方向感|选择比努力|人生规划|赛道选择|选赛道|人生选择|怎么选|人生的方向", None, {}),
    ("成长", "模仿学习", r"模仿|临摹|抄作业|先抄|对标学习|向高手学|向前辈学|拆解高手|高手模仿", None, {"xcats": ["教育"]}),
    ("成长", "公开输出", r"公开工作|公开学习|大庭广众|每日输出|输出倒逼|以输出|知识分享|公开分享|在公开", None, {}),
    ("成长", "复盘反思", r"复盘|反思|反省|根因分析|总结经验", None, {}),
    ("成长", "作品资产", r"作品思维|资产化|积累资产|个人资产|内容资产|知识资产|可积累|把工作变成资产|生产资料|数字资产", None, {}),
    ("成长", "决策", r"决策|做决定|判断力|权衡|取舍", None, {}),
    ("成长", "说话沟通", r"沟通|(?<!不)(?<!不会)说话|表达能力|口才|演讲|说服|情商|谈判", None, {}),
    # ── 财经 ──
    ("财经", "股票基金", r"股票|股市|a股|美股|港股|基金|指数(?!级|增长|型|爆炸)|etf|定投|炒股|大盘|牛市|熊市|涨停|纳斯达克|标普", 3, {}),
    ("财经", "价值投资", r"价值投资|巴菲特|芒格|长期投资|护城河|段永平|估值|安全边际|投基不投机", None, {}),
    ("财经", "理财规划", r"理财|资产配置|分散投资|家庭财务|保险|存款|储蓄|投资组合|财务规划|财务管理", None, {}),
    ("财经", "黄金", r"黄金|白银|金价|贵金属", 3, {}),
    ("财经", "加密货币", r"比特币|加密货币|币圈|区块链|web3|稳定币|以太坊|btc|虚拟货币|数字货币", 2, {}),
    ("财经", "经济形势", r"经济危机|金融危机|衰退|通胀|通缩|降息|加息|美联储|债务|gdp|经济周期|萧条|泡沫|内需|经济转型|经济繁荣|经济下行", None, {}),
    ("财经", "汇率美元", r"美元|汇率|人民币|升值|贬值|美债|去美元化", None, {}),
    ("财经", "关税贸易", r"关税|贸易战|贸易摩擦|贸易逆差|贸易顺差|出口(?!管制)|进口", None, {}),
    ("财经", "财富思维", r"财富思维|财商|富人|穷人|富爸爸|有钱人|财富自由|财务自由|阶层跃迁|致富|财富积累|财富增长|财富认知|变富|富人思维|穷人思维|财富", None, {}),
    ("财经", "现金流", r"现金流|被动收入|睡后收入|负债|资产负债|收入结构|资产积累|积累资本|积累资产", None, {}),
    ("财经", "时间价值", r"时间价值|时间换钱|买时间|购买时间|时间杠杆|出售时间|时间成本|单位时间|时薪|卖时间", None, {}),
    ("财经", "消费观", r"消费|省钱|攒钱|存钱|月光|买买买|花钱", None, {}),
    ("财经", "房产楼市", r"房价|买房|楼市|房贷|房地产|租房|卖房|二手房", 3, {}),
    ("财经", "银行信贷", r"银行|信用卡|贷款|网贷|征信|借钱|分期", None, {}),
    # ── 职场 ──
    ("职场", "求职面试", r"求职|面试|简历|招聘|校招|offer|找工作|应届|毕业生|实习|秋招|春招", None, {}),
    ("职场", "升职跳槽", r"跳槽|转行|职业转型|裸辞|离职|辞职|35岁|中年危机|职业规划|升职|加薪|晋升|职业发展", None, {}),
    ("职场", "团队管理", r"团队管理|带团队|管理者|领导力|下属|员工管理|管理思维|管人|授权|新经理|中层|管理团队", None, {}),
    ("职场", "职场人际", r"领导|同事|职场关系|向上管理|职场政治|背锅|甩锅|汇报", None, {"cats": ["职场", "成长", "心理"]}),
    ("职场", "体制内", r"体制内|考公|公务员|编制|事业单位|铁饭碗", None, {}),
    # ── 内容创作 ──
    ("内容创作", "选题爆款", r"选题|爆款|爆文|对标|蹭热点|标题", None, {"cats": ["内容创作", "商业", "AI"]}),
    ("内容创作", "口播出镜", r"口播|出镜|镜头|上镜|不露脸|露脸|表现力", None, {}),
    ("内容创作", "拍摄剪辑", r"拍摄|剪辑|剪映|运镜|分镜|配乐|拍视频|画面感", None, {}),
    ("内容创作", "涨粉流量", r"起号|涨粉|粉丝|流量|播放量|冷启动|推荐算法|算法推荐|推荐机制|限流|完播|互动率|dou\+|投流", None, {"xcats": ["社会"]}),
    ("内容创作", "个人IP", r"个人ip|ip打造|打造ip|个人品牌|人设|超级ip|ip化", None, {}),
    ("内容创作", "直播", r"直播", None, {"xcats": ["社会"]}),
    ("内容创作", "内容变现", r"接广告|商单|星图|恰饭|橱窗|内容变现|流量变现|短视频变现|自媒体变现|变现路径", None, {}),
    # ── 科技 ──
    ("科技", "马斯克", r"马斯克|musk|(?<![a-z])elon", 3, {}),
    ("科技", "电动车智驾", r"特斯拉|tesla|电动车|新能源车|比亚迪|小米汽车|蔚来|理想汽车|小鹏|自动驾驶|(?<![a-z])fsd|智驾|无人驾驶|汽车", 3, {}),
    ("科技", "航天太空", r"spacex|星舰|星链|(?<!三级)(?<!坐)火箭(?!般|式)|航天|卫星|太空|nasa|登月|火星|宇航|空间站|starship|starlink", 3, {}),
    ("科技", "低空飞行", r"飞行汽车|低空|evtol|无人机|飞行器", 2, {}),
    ("科技", "机器人", r"机器人|人形|具身|宇树|optimus|擎天柱|机械臂|gr00t|灵巧手", 3, {}),
    ("科技", "苹果", r"苹果|apple|iphone|(?<![a-z])ios(?![a-z])|库克|乔布斯|vision ?pro", 3, {"cats": ["科技", "AI", "商业"]}),
    ("科技", "华为", r"华为|鸿蒙|麒麟|余承东|任正非", 2, {}),
    ("科技", "互联网大厂", r"大厂|字节|腾讯|阿里|百度|美团|京东|拼多多|互联网公司|网易", None, {}),
    ("科技", "科学知识", r"量子|物理|天文|宇宙|黑洞|化学|生物学|进化论|基因|科普|物质三态|自然现象", None, {}),
    # ── 社会 ──
    ("社会", "美国政治", r"特朗普|川普|拜登|白宫|共和党|民主党|中期选举|中期考试|大选|左派|右派|万斯|国会", 3, {}),
    ("社会", "中美博弈", r"中美|大国博弈|脱钩|东大|老美|美方|中国.{0,6}美国|美国.{0,6}中国", None, {}),
    ("社会", "日本", r"日本|日方|东京|高市|日元", 3, {}),
    ("社会", "台海两岸", r"台湾|台海|两岸|台独", 2, {}),
    ("社会", "俄乌欧洲", r"俄罗斯|乌克兰|普京|泽连斯基|欧盟|塞尔维亚|北约|俄乌", 3, {}),
    ("社会", "中东", r"以色列|伊朗|中东|加沙|巴勒斯坦|哈马斯|沙特", 3, {}),
    ("社会", "性别话题", r"性别|女权|男女平等|男女对立|厌女|男权|女性主义|女拳|女留学生|精致女生", None, {}),
    ("社会", "婚恋生育", r"彩礼|结婚|婚姻|离婚|恋爱|相亲|婚恋|不婚|生育|生孩子|催婚|剩女|夫妻", None, {}),
    ("社会", "爱国与认同", r"爱国|民族|国家认同|崇洋|美吹|殖人|汉奸|民族自信|文化自信|祖国", None, {}),
    ("社会", "反诈防骗", r"诈骗|骗局|骗子|电诈|洗钱|跑分|黑产|杀猪盘|割韭菜|防骗|被骗|传销|水房", None, {}),
    ("社会", "网红主播", r"网红|主播|塌房|明星|顶流|饭圈|偶像|热搜", None, {}),
    ("社会", "舆论媒体", r"新闻|(?<!自)媒体|谣言|假新闻|信息茧房|舆论|舆情|公知|标题党|带节奏", None, {"cats": ["社会", "法律", "科技", "财经", "人文"]}),
    ("社会", "阶层内卷", r"内卷|阶层|躺平|中产|打工人|年轻人|00后|90后|代际|啃老|鄙视链|消费主义", None, {}),
    ("社会", "民生就业", r"就业|失业|养老|医保|社保|退休|补贴|发钱|低保|民生", None, {"xcats": ["AI"]}),
    ("社会", "辩论逻辑", r"辩论|辩手|诡辩|逻辑谬误|偷换概念|怼人|吵架|反驳|逻辑漏洞|逻辑混乱|讲逻辑|逻辑能力|论证", None, {"cats": ["社会", "法律", "科技"]}),
    ("社会", "体育赛事", r"世界杯|足球|篮球|nba|奥运|国足|球赛|球员|日本队|梅西", 3, {}),
    ("社会", "农村县城", r"农村|乡村|县城|老家|返乡|种地|农民", None, {}),
    # ── 法律 ──
    ("法律", "维权诉讼", r"维权|起诉|官司|诉讼|赔偿|仲裁|法院|判决|胜诉|败诉|索赔", None, {}),
    ("法律", "刑事犯罪", r"犯罪|刑事|判刑|坐牢|洗钱罪|寻衅滋事|拘留|立案|刑法", None, {}),
    ("法律", "劳动法", r"劳动法|劳动合同|加班费|加班|调休|辞退|赔偿金|n\+1|试用期|欠薪", None, {"cats": ["法律", "职场", "社会"]}),
    ("法律", "版权侵权", r"版权|侵权|商标|专利|盗版|抄袭|知识产权|著作权", None, {}),
    ("法律", "网暴隐私", r"网暴|诽谤|名誉|隐私|个人信息|偷拍|造谣|诬告", None, {}),
    # ── 教育 ──
    ("教育", "英语语法", r"语法|时态|句型|从句|主谓|复数|代词|动词|介词|冠词|疑问句|问句|进行时|过去式|形容词|副词|连词|被动语态|句子结构|串联", None, {"cats": ["教育"]}),
    ("教育", "英语词汇", r"词汇|单词|背单词|词根|词缀|身体部位|称谓|词组|短语|搭配", None, {"cats": ["教育"]}),
    ("教育", "英语口语", r"口语|发音|听力|对话|地道表达|日常用语|情景|场景|音标|描写|叙事", None, {"cats": ["教育"]}),
    ("教育", "高考志愿", r"高考|志愿|填报|专业选择|选专业|分数线|大学专业|985|211|双一流", None, {}),
    ("教育", "考研留学", r"考研|留学|留学生|出国|雅思|托福|海归|研究生", None, {}),
    ("教育", "家庭教育", r"家庭教育|亲子|育儿|教育孩子|孩子|小学|中学|鸡娃|家长|儿子|女儿", None, {}),
    # ── 心理 ──
    ("心理", "情绪内耗", r"情绪(?!价值|表达|共鸣)|焦虑|抑郁|内耗|崩溃|(?<![a-z])emo(?![a-z])|心累|抗压|心理压力|精神压力", None, {"xcats": ["内容创作"]}),
    ("心理", "自信自卑", r"自信|自卑|自尊|讨好|自我价值|配得感|自我认同|被认可|在意别人|别人的看法|批评", None, {}),
    ("心理", "原生家庭", r"原生家庭|童年|父母的爱|和父母", None, {}),
    ("心理", "人际关系", r"人际|社交(?!媒体|平台)|圈子|边界感|人脉|人情世故|饭局|贵人|合群|交朋友|结交|交往", None, {}),
    ("心理", "心理学效应", r"效应|心理学|弗洛伊德|荣格|马斯洛|阿德勒|认知失调|习得性无助", None, {}),
    # ── 人文 ──
    ("人文", "历史", r"历史(?!上|性|最|新高|记录|遗留|包袱|数据|版本|消息|对话)|朝代|皇帝|古代|秦朝|汉朝|唐朝|宋朝|明朝|清朝|二战|一战|三国|民国|史记|帝国", None, {}),
    ("人文", "哲学思想", r"哲学|尼采|叔本华|苏格拉底|柏拉图|老子|庄子|王阳明|心学|佛学|道家|存在主义|斯多葛", None, {}),
    ("人文", "国学经典", r"国学|论语|孔子|道德经|易经|百家讲坛|孟子|儒家|传统文化|诗词|红楼梦|西游记|水浒", None, {}),
    ("人文", "文明比较", r"文明|东西方|西方文明|中华文明", None, {}),
    # ── 健康 · 生活 ──
    ("生活", "身体健康", r"健康|睡眠|失眠|饮食|减肥|健身|养生|医生|医院|疾病|癌|体检|营养|跑步|多巴胺", None, {"xcats": ["AI"]}),
    ("生活", "影视", r"电影|电视剧|剧情|综艺|观影|影评|导演|演员|纪录片|动漫", None, {}),
    ("生活", "游戏", r"玩游戏|游戏机|steam|电竞|手游|网游|单机游戏|原神|黑神话|ps5", None, {}),
    ("生活", "旅行美食", r"旅游|旅行|美食|景点|吃播|探店", None, {}),
]
GROUPS = ["AI", "商业", "成长", "财经", "职场", "内容创作", "科技", "社会", "法律", "教育", "心理", "人文", "生活"]
MAX_TAGS = 4
_PASS = 3.0              # 分够这么多才贴
# 平台活动、系列名、作者口头禅这类话题标签不算内容（比如「#抖音前沿科技首发计划」里有「科技」两个字）
_SKIP_HASH = re.compile(r"计划|征稿|大赏|扶持|精选|新星|首发|创作者|抖来|dou来|上热门|热门|dou\+|看法|宝藏|万粉|知识体系|姜胡说|芬钛|"
                        r"标记我的|观影报告|大课堂|真实生活|记录|日常|涨知识|看世界|分享|干货|热点|话题|挑战|合集|系列|vlog|律师|老师|讲师|胖子|"
                        r"抖音|小助手|共享大脑|甜甜圈|大头鹰|ai新星", re.I)
_W = {"title": 3.0, "kw": 2.5, "sum": 2.0, "pts": 1.5, "hash": 1.5, "head": 1.5}

_lock = threading.RLock()
_cache = {}
_hooks = {"log": None, "labels": None}
_RX = []                 # [(组, 标签, 强匹配, 正文匹配, 最少次数, cats, xcats, need)]


def _compile():
    if _RX:
        return _RX
    for g, t, pat, minb, opt in VOCAB:
        rx = re.compile(pat, re.I)
        need = re.compile(opt["need"], re.I) if opt.get("need") else None
        _RX.append((g, t, rx, minb, set(opt.get("cats") or ()), set(opt.get("xcats") or ()), need))
    return _RX


def configure(log=None, labels=None):
    """server.py 传进来：log(标签, 人话)；labels = labels 模块（读大类、子类、AI 关键词）。"""
    if log:
        _hooks["log"] = log
    if labels:
        _hooks["labels"] = labels


def _log(msg):
    f = _hooks.get("log")
    if f:
        try:
            f("贴标签", msg)
        except Exception:
            pass


# ════════════════════ 存取 ════════════════════

def _mem():
    import agent_core
    return agent_core.MEMORY_DIR


def _note_dir():
    return _mem() / "video_notes"


def _tags_file():
    return _note_dir() / "_tags.json"


def _seed_file():
    return Path(__file__).resolve().parent / "tag_seed.json"


def _read(path):
    try:
        mt = path.stat().st_mtime
    except Exception:
        return {}
    c = _cache.get(str(path))
    if c and c[0] == mt:
        return c[1]
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            d = {}
    except Exception:
        d = {}
    _cache[str(path)] = (mt, d)
    return d


def _write(path, d):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(str(tmp), str(path))
    _cache.pop(str(path), None)


def clean_tag(s):
    s = re.sub(r"[\s#＃“”\"'《》「」【】\[\]()（）:：。,，、!！?？;；/|｜]+", "", str(s or ""))
    return s[:12]


def all_tags():
    """{文件名: [标签…]}（只给有标签的）。"""
    with _lock:
        d = _read(_tags_file())
    return {k: list(v.get("t") or []) for k, v in d.items() if isinstance(v, dict) and v.get("t")}


def entry(name):
    with _lock:
        e = _read(_tags_file()).get(name)
    return dict(e) if isinstance(e, dict) else None


def groups():
    """给界面用：[{name: 组, tags: [标签…]}]，按标签表的顺序；你自己加的、表里没有的放「我加的」。"""
    known, out = set(), []
    for g in GROUPS:
        ts = [t for gg, t, *_r in VOCAB if gg == g]
        known.update(ts)
        out.append({"name": g, "tags": ts})
    extra = []
    for v in all_tags().values():
        for t in v:
            if t not in known and t not in extra:
                extra.append(t)
    if extra:
        out.append({"name": "我加的", "tags": extra})
    return out


def set_tags(name, tags):
    """你手动改了这篇的标签（可以清空）。以后自动贴不会再动它。返回存下的标签。"""
    name = (name or "").strip()
    out = []
    for t in tags or []:
        t = clean_tag(t)
        if t and t not in out:
            out.append(t)
    out = out[:8]
    with _lock:
        d = dict(_read(_tags_file()))
        d[name] = {"t": out, "by": "you", "at": int(time.time())}
        _write(_tags_file(), d)
    return out


def forget(name):
    """这篇重新加工了：自动贴的标签作废（下次打开「已加工」按新内容重新贴）；你手动改过的不动。"""
    with _lock:
        d = _read(_tags_file())
        e = d.get(name)
        if not isinstance(e, dict) or e.get("by") == "you":
            return False
        d = dict(d)
        d.pop(name, None)
        _write(_tags_file(), d)
    return True


# ════════════════════ 按内容贴 ════════════════════

def _fields(txt, lab=None):
    """从笔记全文拿出：标题、话题标签、原标签、一句话概括、核心观点、正文；lab = 这篇的分类 {cat, sub, kw}。"""
    txt = (txt or "").replace("\r\n", "\n")
    lines = txt.split("\n")
    title = lines[0].lstrip("# ").strip() if lines else ""
    hashes = [h for h in re.findall(r"#\s*([^#\s]{2,16})", title) if not _SKIP_HASH.search(h)]
    main = re.sub(r"#\s*[^#\s]+", " ", title)
    head = []
    for ln in lines[1:60]:
        s = ln.strip().lstrip("-").strip()
        if s.startswith(("标签：", "标签:")):
            head = [t.strip() for t in re.split(r"[、,，]", s[3:]) if t.strip() and not _SKIP_HASH.search(t)]
            break
        if ln.startswith("## "):
            break
    lb = _hooks.get("labels")
    summary, points = "", []
    try:
        if lb:
            p = lb._parse_note("x.md", txt[:12000])
            summary, points = p.get("summary") or "", p.get("points") or []
    except Exception:
        pass
    i = txt.find("## 🤖 AI 分析")
    body = txt[i:] if i >= 0 else txt
    j = body.find("## 📝")
    if j > 0 and len(body) - j > 1500:          # 有像样的文字稿：正文只数文字稿（那是视频真正讲的）
        body = body[j:]
    # 加工结果开头偶尔混进网页 AI 侧边栏的对话标题（一行行很短的字）：不算正文
    body = "\n".join(l for l in body.split("\n") if len(l.strip()) > 16 or l.startswith("#"))
    body = body.replace("ChatGPT 说：", " ").replace("ChatGPT 说:", " ")
    lab = lab or {}
    return {"title": main, "hash": " ".join(hashes), "head": " ".join(head), "kw": " ".join(lab.get("kw") or []),
            "sum": summary, "pts": " ".join(points), "body": body[:60000],
            "cat": lab.get("cat") or "", "sub": lab.get("sub") or ""}


def score(f):
    """每个标签的分数 {标签: (总分, 标题/关键词/概括这些地方的分)}（只给有分的）。"""
    strong = " ".join((f["title"], f["kw"], f["sum"]))
    out = {}
    for g, t, rx, minb, cats, xcats, need in _compile():
        if cats and f["cat"] not in cats:
            continue
        if xcats and f["cat"] in xcats:
            continue
        s = 0.0
        for k, w in _W.items():
            if f[k] and rx.search(f[k]):
                s += w
        sb = 0.0
        if minb:
            n = len(rx.findall(f["body"]))
            sb = 3.0 if n >= minb * 4 else 2.0 if n >= minb * 2 else 1.0 if n >= minb else 0.0
        if (s or sb) and need and not need.search(strong):
            s = sb = 0.0
        if s or sb:
            out[t] = (s + sb, s)
    return out


def pick(sc):
    """分够的标签，按分数从高到低，最多 MAX_TAGS 个；一个都不够时，标题/关键词/概括里到 2 分的也算一个。"""
    order = {t: i for i, (_g, t, *_r) in enumerate(VOCAB)}
    ranked = sorted(sc.items(), key=lambda x: (-x[1][0], -x[1][1], order.get(x[0], 999)))
    got = [t for t, s in ranked if s[0] >= _PASS][:MAX_TAGS]
    if not got:                                 # 一个都不够：只靠正文提到几次不算，标题/关键词/概括里出现过的才兜底
        alt = [t for t, s in ranked if s[1] >= 2.0]
        got = alt[:1]
    return got


def compute(txt, lab=None):
    return pick(score(_fields(txt, lab)))


def _seed():
    try:
        d = json.loads(_seed_file().read_text(encoding="utf-8"))
        return d.get("notes") or {}, str(d.get("v") or "")
    except Exception:
        return {}, ""


_seeded = {"done": False}


def ensure(items, lab=None, limit=80):
    """打开「已加工」时调用：① 第一次先把核对过的标签（tag_seed.json）导进来；
    ② 加工好了、还没标签的，按内容自动贴（一次最多 limit 篇，剩下的下次接着贴）。
    items：[{name, analyzed}]；lab：labels.note_labels()。返回这次新贴了几篇。"""
    nd = _note_dir()
    with _lock:
        d = _read(_tags_file())
        new = dict(d)
        n_seed = n_rule = 0
        if not _seeded["done"]:
            _seeded["done"] = True
            seed, ver = _seed()
            for name, tg in seed.items():
                e = new.get(name)
                if isinstance(e, dict) and e.get("by") in ("you", "rule"):
                    continue                     # 你改过的、重新加工后自动贴的：不动
                if isinstance(e, dict) and e.get("t") == tg:
                    continue
                if not (nd / name).exists():
                    continue
                new[name] = {"t": list(tg), "by": "seed", "at": int(time.time())}
                n_seed += 1
            if n_seed:
                _log("导入了 %d 篇文章核对过的标签（%s）" % (n_seed, ver or "tag_seed.json"))
        lab = lab or {}
        todo = [it["name"] for it in items if it.get("analyzed") and it.get("name") and it["name"] not in new]
        for name in todo[:limit]:
            try:
                with open(nd / name, "rb") as fh:
                    txt = fh.read(200000).decode("utf-8", "ignore")
            except Exception:
                continue
            new[name] = {"t": compute(txt, lab.get(name)), "by": "rule", "at": int(time.time())}
            n_rule += 1
        if n_seed or n_rule:
            _write(_tags_file(), new)
    if n_rule:
        _log("按内容给 %d 篇新加工的文章贴了标签" % n_rule)
    return n_seed + n_rule
