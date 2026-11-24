# 企业使用 AI 的方式正在发生怎样的变化

- 来源链接：https://www.youtube.com/watch?v=YN4fId6Jn8k
- 作者：The AI Daily Brief: Artificial Intelligence News
- 提取时间：2026-11-20 10:59
- 原标题：How Business AI Use is Changing
- 标签：企业AI应用、模型价格战、多模型策略、AI成本优化、智能体落地

## 🤖 AI 分析

## 一句话概括
企业 AI 市场正在从模型厂商主导转向买方主导：随着模型竞争加剧、Token 价格下降和多模型切换日益普遍，领先企业能够以更低的单位成本使用更多 AI，而未来市场规模的关键，取决于普通企业能否逐渐达到头部企业的 AI 使用深度。

## 背景与主题
这期视频来自 The AI Daily Brief，由 Nathaniel Whittemore 主持，发布于 2026 年 11 月 17 日，主要分析企业 AI 使用方式、采购策略、支出结构和市场竞争格局的变化。作者综合了 Databricks 的新一期 AI Index、Arcana Research 的首份企业 AI 年度研究，以及 Ramp 在 10 月和 11 月发布的 AI Index，发现不同数据集正在指向一些共同趋势：AI 用量增长快于支出、企业越来越愿意更换模型供应商、头部用户与普通用户之间的差距巨大。作者从企业采购者、AI 服务商和整个 AI 产业投资回报的角度出发，试图判断这些变化究竟意味着 AI 市场降温，还是意味着企业正在进入更加成熟、重视效率的新阶段。
节目在正式讨论前，还涉及 NVIDIA 管理层风波、美国 AI 芯片出口限制、OpenAI 外部安全评估，以及美国银行系统故障等新闻。
资料说明：已对照节目官方页面核对主要数字、机构和人名，并修正部分语音识别错误。以下将企业 AI 主线与其他新闻分开整理；新闻事件和预测均按节目播出时的口径呈现。
The AI Daily Brief

## 核心观点

### 1. 企业 AI 使用量的增长，已经明显超过支出增长
Ramp 的最新研究发现，样本企业在一个月内消耗的 AI Token 数量增长了 36%，但相应支出只增长了 2%。这意味着企业正在用几乎不变的预算处理更多 AI 工作，而不是每增加一份 AI 用量就承担相同比例的成本。按这两个数字粗略计算，每单位 Token 的平均实际支出下降约 25%，每美元可以购买的 Token 数量则提高约 33%。这一变化表明，AI 市场正在出现类似云计算成熟过程中的效率提升：技术使用规模不断扩大，但单位服务成本持续降低。作者认为，这并不是企业失去 AI 投资兴趣，而是企业开始真正享受到模型竞争和技术优化带来的经济收益。
更深层的逻辑是，AI 的价值不再单纯取决于使用了多少 Token，而取决于同样的预算究竟创造了多少有效产出。

### 2. 便宜的模型即使没有被大规模采用，也会迫使整个市场降价
数据显示，2026 年 10 月，OpenAI 和 Anthropic 的平均每百万 Token 价格下降了 21%。作者特别强调，这并不意味着企业一定正在大规模转向价格更低的中国模型，而是这些低价模型的存在本身就在改变竞争环境。当市场上出现质量足够好、价格明显更低的替代品时，原有头部厂商即使没有直接流失客户，也不得不调整价格以维持竞争力。与此同时，OpenAI 和 Anthropic 本身也在不断推出推理效率更高、单位运行成本更低的模型，因此降价是外部竞争压力与内部技术进步共同作用的结果。作者认为，真正重要的并非某一家模型公司降价，而是整个 AI 行业正在从高溢价阶段走向更加激烈的价格竞争阶段。
换句话说，低价模型的市场价值不仅体现在自己获得多少客户，还体现在它能够迫使整个行业重新定价。

### 3. 企业正在摆脱对单一模型供应商的依赖，多模型策略逐渐成为常态
Databricks 提供的 Unity Gateway 是一种模型网关和路由管理方案，可以帮助企业根据不同任务选择适合的 AI 模型，并优化成本。2026 年 7 月，在使用这一产品的企业中，有 64% 只使用一家模型供应商；但到 11 月初，情况已经逆转，72% 的企业开始同时使用两家或更多模型供应商。这说明企业正在改变过去押注一家 AI 公司的做法，转而将 OpenAI、Anthropic 及其他模型视为可以组合、替换和相互竞争的服务资源。多模型架构意味着企业可以让高性能模型处理复杂推理任务，让低成本模型完成简单分类或文本生成，在不同任务之间实现成本和效果的平衡。更重要的是，一旦企业具备快速切换模型的能力，原有供应商就很难再依靠技术锁定维持高价格。
这一趋势标志着企业 AI 采购逻辑从“选择最强模型”转向“构建最适合业务的模型组合”。

### 4. 企业真正应该关注的是每项成功任务的成本，而非 Token 单价
Databricks 提出了一个重要指标：Cost per Successful Task（每项成功任务的成本）。假设模型 A 完成一次任务需要 0.01 美元，但成功率只有 60%；模型 B 单次成本为 0.015 美元，却拥有 95% 的成功率，那么只比较 Token 价格就很可能选错供应商。因为失败任务可能产生重复调用、人工纠错、客户投诉和业务延误，最终使看似便宜的模型反而更加昂贵。企业应当把模型价格、任务完成率、重试次数、响应速度和人工干预成本放在同一个框架下评估，而不是依靠模型排行榜决定采购。作者认为，随着企业越来越熟悉 AI，这种从技术参数转向业务结果的评价方式会更加普遍。
Arcana Research 的调查进一步支持了买方力量上升的判断：约三分之一的 OpenAI 客户表示愿意考虑更换供应商，常见替代选择是 Anthropic；43% 的 GitHub Copilot 客户也对转换工具持开放态度，通常提到 Claude Code。这些数字并不代表客户已经流失，却说明供应商必须认真对待潜在的客户迁移。

### 5. AI 已成为大型企业的重要预算项目，但成本管理能力仍严重不足
Arcana Research 调查了 Global 2000（全球大型企业群体）的相关负责人，发现 AI 已经成为部分企业年度预算中达到八位数美元规模的重要支出项目。约 91% 的受访者预计 2026 年 AI 支出将增加，其中多数预计增幅在 20%—40%。然而，一个极为矛盾的现象是，约 三分之二的负责人无法清楚掌握企业在模型和 API 上究竟花了多少钱。这说明企业 AI 投资增长速度已经超过其内部财务管理、技术治理和成本核算体系的成熟速度。作者认为，领先企业正在通过模型切换和成本优化获得优势，而大量普通大型企业依然沿用传统的软件采购和预算管理方式。
这也意味着下一阶段企业 AI 竞争的重点，不只是进一步增加预算，而是建立能够追踪、解释和优化 AI 支出的管理系统。

### 6. 头部企业与普通企业的 AI 投入差距巨大，市场呈现极端两极分化
Ramp 的研究显示，样本企业每名员工每月 AI 支出的中位数为 16.32 美元，而支出排名前 1% 的企业，每名员工每月 AI 支出超过 10,000 美元，约为中位数的 625 倍。Databricks 的数据也呈现类似现象：普通用户每周的 AI 支出中位数约为 2.49 美元，而处于第 99 百分位的用户每周支出接近 700 美元，两者相差约 281 倍。作者提醒，Ramp 的样本主要来自技术导向、数字化水平较高的公司，因此最顶端的 1% 并不代表所有企业的正常状态。即便如此，两套不同数据都呈现如此巨大的差距，仍然说明企业之间对 AI 的依赖程度和使用方式存在根本性差异。
由此引出了整期视频最重要的长期问题：今天最激进的 AI 使用者，究竟只是少数特殊企业，还是未来大多数企业的预演？如果普通企业逐渐向头部靠近，AI 市场规模将远远超过当前水平；如果这些企业始终是异常值，那么市场可能比最乐观的资本支出预测小得多。

### 7. AI 编程仍然是企业最重要、最成熟的应用场景
在 Ramp 统计的企业 AI 支出中，72% 来自工程团队（Engineering Teams），说明软件开发仍是目前 AI 商业应用的核心领域。Arcana 的 Global 2000 调查也发现，约三分之一的企业正在试点 AI 编程工具，这在各类 AI 试点项目中排名第一。作者用“Coding remains king（编程仍然是王者）”概括这一现象，因为代码生成、调试、测试和软件维护往往拥有较清晰的任务边界，也更容易通过代码是否通过测试、开发时间是否减少等方式衡量结果。相较于一些难以量化的办公 AI 应用，软件工程可以更直接地将 AI 使用与生产效率联系起来。因此，AI 编程不仅是企业当前最愿意付费的应用场景，也成为观察模型商业竞争的重要窗口。
但这里同样存在一个值得关注的问题：工程团队占据支出的大头，并不意味着其他部门没有需求，而是其他业务领域可能还没有建立同样成熟的 AI 使用流程。

### 8. Anthropic 在企业市场表现强劲，但不同模型的实际表现正在快速分化
在 Ramp 统计的美国企业中，接近 45% 的企业向 Anthropic 付费，而向 OpenAI 付费的企业比例为 40.6%。Databricks 数据显示，在 Unity Gateway 的专有模型 Token 用量中，68.8% 流向 Anthropic 模型；Arcana 的调查则发现，当受访者被问及令人兴奋的 AI 供应商时，81% 提到了 Anthropic。这些数据来自不同统计口径，却共同说明 Anthropic 在企业客户、使用量和品牌关注度方面都具有较强势头。更具体地说，Databricks 数据中，Opus 5.5 在六周内的 Token 份额从 7.2% 提升至 37.9%，而 Fable 5.2 的份额却从 5.5% 下降至 0.6%。作者推测，这种分化未必代表企业不再需要前沿模型，而可能是 Opus 5.5 在相关任务上的竞争力过强，挤压了其他模型的位置。
这里必须区分“某个平台上的使用份额”和“整个行业的市场占有率”：前者可以体现具体客户群体的选择，却不能直接代表所有企业的真实采购格局。

### 9. 客户服务正在成为仅次于编程的重要 AI 增长场景
Ramp 数据显示，客户支持团队在 AI 总支出中的份额，从 2026 年 6 月的 0.8% 上升到 11 月的 13.3%，增加了 12.5 个百分点，份额约为原来的 16.6 倍。Arcana 的调查也发现，38% 的 Global 2000 受访企业已经在客户服务中使用 AI。这说明 AI 的商业应用正在从技术部门向直接接触客户的业务部门扩展，包括客服问答、工单分流、知识检索、问题解决辅助和自动化服务。客户服务通常具有高频、重复、标准化程度较高的特点，因此可以通过响应速度、人工客服工作量和问题解决率等指标衡量 AI 效益。作者将这一变化视为企业 AI 应用范围扩大的重要信号，意味着未来支出增长可能更多来自软件工程之外的业务部门。
不过，客户服务支出份额上升，并不等同于其绝对支出增长相同比例，也不自动证明 AI 客服已经全面改善了用户体验。

### 10. 企业对自主智能体十分期待，但实际部署仍然落后于市场热度
作者预计，2026 年可能被许多人称为 “AI Agents 真正落地的一年”，因为智能体已经从单纯的聊天工具发展到能够调用工具、执行任务和参与复杂工作流的系统。但 Arcana 数据呈现出明显的落差：Autonomous Agents（自主智能体）在企业试点及未来计划的热度榜中排名第四，在实际部署采用率榜单中却排在最后。与此同时，Ramp 的 Token 支出增速已经明显放缓，8 月为 1.05%、9 月为 0.22%、10 月为 1.65%，说明市场热度并没有直接转化为持续高速的实际支出增长。假设 1.65% 的月增速能够保持一年，复合年增长率约为 22%，虽然低于过去的高增长阶段，却仍处于 Arcana 受访企业预计的 20%—40% 年度增长区间。作者认为，这些表面矛盾的信号并不意味着 AI 商业化失败，而可能说明企业正在从探索阶段进入需要严格计算成本、评估可靠性和控制风险的实际运营阶段。
真正重要的不是企业是否对智能体感兴趣，而是它们是否能够把智能体长期、稳定、可审计地部署进真实业务流程。

## 关键事实与数据

### 一、研究来源与统计对象

| 数据来源 | 研究内容与样本特点 |
| --- | --- |
| Ramp AI Index（10 月、11 月） | 从企业实际 AI 采购、支出、部门分布及 Token 使用情况观察市场，样本偏向科技及技术应用较积极的公司 |
| Databricks AI Index | 依据 Unity Gateway 等产品中的企业模型使用数据，分析供应商选择、Token 流量与支出差异 |
| Arcana Research — State of Enterprise AI | 调查 Global 2000 大型企业负责人，重点关注采购意愿、部署计划、预算及成本透明度 |
| The AI Daily Brief | 主持人 Nathaniel Whittemore 对上述研究进行交叉分析与评论，并非直接开展这些研究的机构 |

这实际上是三家机构、四份主要数据资料，而不是四家独立研究机构。
The AI Daily Brief

### 二、企业 AI 成本、使用量与预算

| 指标 | 视频提供的数据 | 说明 |
| --- | --- | --- |
| 单月 Token 使用量增长 | +36% | Ramp 样本企业 |
| 同期支出增长 | +2% | 使用量增长明显超过成本增长 |
| 每百万 Token 平均价格变化 | -21% | OpenAI 与 Anthropic，2026 年 10 月 |
| 只使用一家模型供应商的企业比例 | 64% | Databricks Unity Gateway，2026 年 7 月 |
| 同时使用至少两家供应商的比例 | 72% | 2026 年 11 月初 |
| 愿意考虑更换供应商的 OpenAI 客户 | 约 1/3 | Arcana 受访样本，常考虑 Anthropic |
| 愿意考虑更换工具的 GitHub Copilot 客户 | 43% | 常提及 Claude Code |
| 预计 2026 年增加 AI 支出的受访企业 | 91% | Arcana 调查 |
| 多数受访者预计的预算增幅 | 20%—40% | 预算预期，而非已实现增长 |
| 无法清楚掌握模型/API 支出的企业负责人 | 约 2/3 | 反映成本透明度不足 |

### 三、AI 支出两极分化
Ramp：每员工每月 AI 支出
中位数企业

# $16.32

前 1% 企业

# $10,000+

约 625 倍差距

Databricks：每用户每周 AI 支出
中位数用户

# $2.49

第 99 百分位用户

# ≈$700

约 281 倍差距

注意：Ramp 的单位是每员工每月，Databricks 的单位是每用户每周，两组金额不能直接横向比较。

### 四、不同业务部门的 AI 应用情况
Ramp 企业 AI 支出部门结构：工程团队占主导

工程团队 72%
其他部门 28%

| 指标 | 数值 |
| --- | --- |
| 工程团队贡献的 AI 支出占比 | 72% |
| 正在试点 AI 编程工具的 Global 2000 受访企业 | 约 1/3 |
| Ramp 中客服部门 AI 支出占比（6 月） | 0.8% |
| Ramp 中客服部门 AI 支出占比（11 月） | 13.3% |
| 已经使用 AI 客户服务的 Global 2000 受访企业 | 38% |

Ramp 客服部门占 AI 总支出的比例
2026 年 6 月与 11 月，单位：%

这组数据尤其值得关注：编程是当前支出规模的核心，客户服务则是正在迅速扩张的业务方向。

### 五、主要 AI 厂商的竞争数据

| 维度 | 数据 |
| --- | --- |
| Ramp 美国企业中向 Anthropic 付费的比例 | 接近 45% |
| Ramp 美国企业中向 OpenAI 付费的比例 | 40.6% |
| Unity Gateway 中 Anthropic 占专有模型 Token 的比例 | 68.8% |
| Arcana 受访者提到 Anthropic 是令人兴奋的 AI 供应商 | 81% |
| Opus 5.5 在 Databricks 的 Token 份额 | 六周内 7.2% → 37.9% |
| Fable 5.2 在 Databricks 的 Token 份额 | 5.5% → 0.6% |
| Ramp 前沿模型支出占比 | 67.7% → 69.5% |

上述数据体现的是不同样本中的采用情况、使用份额或关注度，不应直接等同于全市场营收份额。
The AI Daily Brief

### 六、AI 支出增长出现放缓
Ramp Token 支出月度增长率
2026 年 8—10 月，单位：%

如果假设 10 月的 1.65% 月增速持续 12 个月，计算为：
(1+0.0165)12−1≈21.7%(1+0.0165)^{12}-1\approx21.7\%(1+0.0165)12−1≈21.7%
即年化增长约 22%。作者认为，这既表明企业 AI 支出增长正在放缓，也说明它仍然有可能维持较为可观的年度增长。

### 七、视频前半段提到的重要 AI 新闻
**1. NVIDIA 的 Jensen Huang（黄仁勋）管理层风波**
节目称，黄仁勋离任 NVIDIA CEO 后，一场支持其回归的行动获得约 18 万个签名，参与或支持者包括 Elon Musk 和 Epic Games CEO Tim Sweeney。投资人 Brad Gerstner 与 Gavin Baker 也向 NVIDIA 董事会提出，应在继任程序中认真考虑黄仁勋回归，特朗普则表达了不反对其回归的态度。
但节目援引 CNBC 报道称，董事会当时并未讨论恢复黄仁勋的职位，而是重点关注由 Wachtell Lipton 律师事务所进行的独立调查，尤其是相关行为是否涉及国家安全或公司机密问题。Scott Galloway 认为其复职可能性极低，原因之一是董事会未来可能面对国会甚至司法程序中的质询。
节目另一个值得关注的角度是 NVIDIA 的金融角色。主持人将其形容为 AI 基础设施投资领域某种意义上的“中央银行”，因为 NVIDIA 不仅出售芯片，还通过融资担保和算力承诺支持行业建设。节目提到 OpenAI 的俄亥俄州项目获得过 NVIDIA 1,000 亿美元级别的担保承诺，而临时 CEO Colette Kress 被预计会收紧部分数据中心融资支持。
Sam Altman 在 Semafor 活动上表示，AI 行业收入和需求已经足够强劲，即使失去黄仁勋的个人推动，行业也能够继续发展。相较之下，Needham & Co 的 John Todaro 对 NeoCloud（新型云算力供应商）的融资支持前景更为谨慎。
这里涉及个人争议、公司调查和融资预测，均应视为节目播出时的报道与判断，不能将调查中的指控直接当作已经证实的事实。
The AI Daily Brief

**2. 美国加强 AI 芯片远程访问出口管制**
视频介绍，美国商务部出台新规，试图堵住通过第三国远程访问先进 NVIDIA 芯片的监管漏洞。
具体涉及的国家包括：
- 新加坡（Singapore）
- 马来西亚（Malaysia）
- 泰国（Thailand）
- 印度尼西亚（Indonesia）
- 巴西（Brazil）

根据节目介绍，相关数据中心运营商购买先进 AI 芯片需要申请出口许可证，既有数据中心则获得 90 天的合规期限。这反映出美国 AI 芯片管制范围不仅涉及芯片实物出口，也进一步关注跨境算力访问。
政策背后还存在政府内部的路线分歧。视频提到 Scott Bessent（斯科特·贝森特）、Howard Lutnick（霍华德·卢特尼克）和 Marco Rubio（马可·鲁比奥）等人物，争论焦点在于对中国采取何种程度的技术限制及如何兼顾商业利益。
节目还援引媒体消息称，美国政府计划把 NVIDIA、Amazon、Microsoft、OpenAI 和 Anthropic 等公司纳入 AI“国家冠军”支持计划，提供更快捷的出口审批、国际业务发展支持以及部分联邦融资帮助。这在播出时仍属于拟议中的政策安排。
The AI Daily Brief

**3. OpenAI 引入外部安全评估，但独立性受到质疑**
OpenAI 宣布与四家机构合作：
- Apollo Research
- METR
- Transluce
- Goodfire

这些机构可以更加深入地接触 OpenAI 的内部模型及相关系统，用于检查模型是否可能绕过控制机制、隐瞒行为或破坏安全约束。
其中 Apollo Research 计划投入 6 名测试人员，开展为期 4 个月的研究，并获得一定范围内的内部信息与研究支持。
争议主要体现在以下方面：OpenAI 可以基于技术、安全和知识产权理由限制某些信息的披露；外部研究人员可以接触的员工范围受到限制；研究人员不能自由进入公司的内部 Slack 频道；评估报告涉及敏感信息时可能被删改，但结论需要原样发布。
Apollo Research 自己也认为，这只是一项有雄心的初步尝试，尚未达到充分独立的嵌入式评估标准。DeepMind 研究人员 Neel Nanda 和前 OpenAI 安全研究员 Steven Adler 也提出批评，尤其担心审计人员获取内部信息的自由程度不足。
作者进一步提出一个制度层面的观点：如果被审计公司既负责挑选审计机构，又能够决定审计机构可以看到什么，那么审计的独立性就很难得到充分保证。
他并不是否定这些合作，而是认为，未来必须建立更明确、具有外部约束力的独立 AI 安全审计标准。
The AI Daily Brief

**4. 美国银行与基础设施系统连续出现故障**
节目提到，在 Microsoft 相关服务故障以及美国联邦航空管理局 FAA 的航空系统中断事件之后，美国部分大型银行和支付服务又出现异常。
涉及的机构包括 JPMorgan Chase、Bank of America、Wells Fargo、Capital One、US Bank 以及 Zelle。部分用户遇到了登录失败、ATM 服务异常和转账中断等问题。
节目称，问题最终追踪至 JPMorgan Chase 的相关后台系统，该银行解释故障是本地基础设施上的软件问题，并非网络攻击。
一些评论者对短时间内接连发生的大型基础设施故障提出怀疑，包括 Vivek Wadhwa 对是否存在针对美国关键基础设施的试探行为提出疑问。但视频并未提供这些故障与 AI 或外部攻击有关的证据，作者也承认目前还需要继续观察。
这部分新闻的重要启示在于：关键基础设施高度依赖复杂的软件、硬件和相互连接的服务系统，任何一个环节故障都可能产生跨机构影响。
The AI Daily Brief

### 八、赞助商介绍中值得单独记录的信息
虽然这些内容属于商业推广，但仍然包含一些有价值的产品思路。
KPMG：Generative Engine Optimization（GEO，生成式引擎优化）
KPMG 提出的核心观点是，AI 正在改变用户获得商业信息的方式。传统搜索依赖搜索结果和链接，而生成式 AI 越来越多地直接提供答案，因此企业不仅要做 SEO，还要让自身专业内容能够被 AI 系统识别、理解和引用。视频宣传的 GEO 理念，正是围绕企业如何进入 AI 生成的答案而展开。
Robots and Pencils：以团队能力而非简单扩张人数作为竞争力
这家公司强调，高效率团队并不依赖一个明星成员承担全部工作，而是要求成员了解彼此的优势和短板，并持续提高集体能力。其广告主张是不依靠大量重复劳动来增加人员规模，而是让团队专注于真正困难的问题。
Granola：AI 会议笔记工具
Granola 的产品定位是 AI-powered notepad（AI 驱动的会议记事本）。用户可以自己记录粗略要点，同时由工具在后台进行转录和笔记整理，不需要额外的会议机器人加入通话。会议结束后，用户还可以通过对话提取行动事项、生成跟进邮件、准备谈判以及使用预设提示词 Recipes（预设工作流）获得辅助。节目给出的促销方案是新用户使用 `AI Daily` 优惠码，前三个月享受 100% 折扣；这属于当期推广信息，不保证现在仍然有效。
Blitzy：基于整个代码库上下文进行安全修复
Blitzy 强调先理解完整代码库，再进行代码修改，并使用 Knowledge Graph（知识图谱）分析应用系统之间的依赖关系。其工作流程包括定位 CVE 漏洞、提出补丁建议、执行 Pull Request，以及验证修复不会引入新的兼容性问题。
广告提到的案例数字为：

| 指标 | 广告宣称的结果 |
| --- | --- |
| 修复的活跃 CVE 漏洞 | 21 个 |
| 涉及核心微服务 | 6 个 |
| 完成时间 | 4 天 |
| 编译错误 | 0 个 |
| 验证扫描 | 全部通过 |

广告称，这项工作原本预计需要数月，最终不到一周完成。但这些是供应商提供的营销案例，不应视为独立测试结果。
此外，主持人还提到另一档节目 How We Got Here 关于 GTA 6 的内容，其重点不是游戏玩法，而是借助游戏讨论美国经济结构和社会预期的变化。

## 金句摘录

### 1. AI 使用量与成本正在脱钩
“Growth and usage is outpacing growth and spend.”

中文翻译：AI 使用规模的增长速度，正在超过支出的增长速度。
这是整期节目的基础判断：企业并非单纯花更多钱购买 AI，而是开始提高每一美元能够获得的 AI 服务量。

### 2. 判断 AI 经济性的指标必须升级
“Cost per successful task.”

中文翻译：每项成功任务的成本。
这句话值得长期记住，因为它把 AI 采购的关注点从 Token 单价转移到了真实任务完成情况。

### 3. 企业 AI 市场正在变成买方市场
“This is increasingly a buyer's market where buyers have the leverage.”

中文翻译：这正日益成为一个买方市场，买方掌握着更大的议价主动权。
其含义在于，模型厂商不再能够假设客户会长期绑定同一家供应商。

### 4. 编程仍是 AI 商业化的核心
“Coding remains king.”

中文翻译：编程仍然是王者。
尽管市场不断涌现新应用场景，软件开发仍然是企业 AI 支出和实际部署的重要支柱。

### 5. 智能体的商业化仍未完全成熟
“Agents in many cases still remain aspirational.”

中文翻译：在很多情况下，智能体仍然更多停留在企业的愿景之中。
技术能够实现某件事，与企业已经把它稳定部署到生产环境，是两个不同的阶段。

### 6. 企业应该更积极地利用竞争
“Competition is vicious.”

中文翻译：市场竞争异常激烈。
“There are deals to be had.”

中文翻译：只要懂得利用这种竞争，就存在获得更优惠交易条件的机会。
这两句共同构成作者给企业采购者最直接的提醒：供应商之间的激烈竞争，正是采购方提高议价能力的机会。

## 值得记住的点 / 行动建议

### 1. 建立 AI 成本台账，首先解决“钱花在哪里”的问题
企业应当把 AI 成本管理从财务部门的总费用统计，细化到模型、供应商、部门和业务任务四个维度。
至少需要记录：模型名称与版本、输入和输出 Token 数量、API 调用次数、每次调用成本、任务类型、调用部门、任务成功率和重试次数。对于已经开展多个 AI 项目的企业，最好按周或按月汇总，形成可以横向比较的成本报表。
特别需要监控的并不是总成本是否上升，而是同样数量的合格业务任务，其平均完成成本是否下降。

### 2. 用“每项成功任务的总成本”评估模型，而不是只看报价
可以建立如下计算框架：
成功任务单位成本=模型调用费+重试费+人工复核费等总成本成功完成的任务数\text{成功任务单位成本}=
\frac{\text{模型调用费+重试费+人工复核费等总成本}}{\text{成功完成的任务数}}成功任务单位成本=成功完成的任务数模型调用费+重试费+人工复核费等总成本​
例如，同样测试 1,000 个任务，模型 A 总成本 100 美元，成功完成 700 个任务，平均成功任务成本约为 0.143 美元；模型 B 总成本 120 美元，成功完成 950 个任务，平均成功任务成本约为 0.126 美元。
虽然模型 B 的总支出更高，但它的有效任务成本更低，因此实际上可能更划算。企业还应该根据不同业务场景分别计算，避免用一个综合平均值掩盖模型在特定任务上的缺陷。

### 3. 构建可替换的多模型架构，减少供应商锁定
企业可以参考 Databricks Unity Gateway 的思路，在业务系统与底层模型之间建立统一接入层。
这层架构应尽量包含模型路由、调用记录、成本计算、故障回退、统一安全策略和版本管理能力。实际使用时，可以为每类任务指定主模型与备选模型，并通过测试决定何时切换，而不必让所有业务永远依赖同一家 AI 公司。
例如，复杂代码审查使用高能力模型，标准化文本分类使用低成本模型，内部知识库问答则优先选择满足安全与数据要求的模型。需要强调的是，多模型方案本身也有集成和维护成本，只有当业务规模、供应商差异或连续性要求足够高时，才会体现出明显价值。

### 4. 主动重新谈判 AI 服务合同，把技术替代能力变成议价能力
作者最直接的商业建议是：企业实际拥有的议价能力，可能比自己正在使用的议价能力大得多。
采购负责人可以用实际任务测试结果向现有供应商提出重新定价要求，而不是只接受官网公开报价。谈判内容不仅包括每百万 Token 的价格，还可以涉及使用量折扣、最低消费承诺、服务等级协议、响应延迟、数据存储政策、技术支持及模型升级条件。
尤其是已经完成多模型适配的企业，可以用真实的替代方案参与谈判。相反，如果所有业务都深度绑定某一家厂商，即使市场上出现更低报价，企业也很难立即利用。

### 5. 将 AI 投资集中到可以明确衡量 ROI 的场景
从视频数据来看，软件工程和客户服务是值得优先关注的两个业务领域。
软件工程可以考察代码审查时间、Bug 修复效率、测试通过率和开发交付周期；客户服务可以考察人工客服接管率、首次问题解决率、每单处理成本及用户满意度。相比“让员工更多使用 AI”这样的抽象目标，这些指标更容易帮助管理层判断投入是否真正产生收益。
一个实用方法是，先在具体任务中进行小规模试点，建立不使用 AI 时的基准数据，再计算加入 AI 后节省的时间、费用和返工成本。只有在结果可靠、风险可控且收益可以复现的情况下，才扩大使用规模。

### 6. 对自主智能体采取分阶段部署，不要把试点热度当成实际成果
Arcana 的数据表明，自主智能体的试点兴趣与实际部署程度存在明显距离。因此，企业应当优先选择权限明确、结果容易验证、错误可以恢复的任务，而不是一开始就让 Agent 处理复杂且不可逆的核心流程。
比较稳妥的路径是：先让智能体提供建议，再允许其处理低风险任务，随后逐步开放工具调用权限，并对高风险操作保留人工审批。部署过程中需要记录失败原因、工具调用日志、权限使用情况，以及异常情况下的恢复方式。
判断智能体是否真正成熟，不能只看一次演示是否成功，而应看它能否在连续真实任务中保持稳定表现。

### 7. 不要把头部 1% 企业的 AI 支出直接当成自己的目标
头部企业每员工每月超过 1 万美元的 AI 支出，并不意味着其他企业也应该迅速达到这个水平。
有些企业本身从事 AI 产品研发、软件开发或算力密集型业务，其 AI 成本和普通制造业、零售业、服务业完全不同。高支出可以意味着高生产力，也可能只是业务性质特殊，或者仍处于高投入探索阶段。
更合理的做法是比较同行业、同业务类型、同规模企业的 AI 成本和效果，而不是用最极端的市场数据建立预算目标。企业真正应该追求的，是让 AI 成本增长持续低于其创造的有效业务价值增长。

### 8. 追踪未来 AI 市场时，重点观察三个领先指标
第一是多模型使用率：如果越来越多企业同时使用多家模型供应商，意味着竞争仍在加强，采购市场的买方力量可能继续提高。
第二是每项成功任务的成本变化：相比单纯统计 Token 用量，这一指标更能体现模型降价、技术进步和业务流程优化带来的实际经济收益。
第三是中位数企业与头部企业的使用差距：如果中位数企业逐渐提升 AI 使用深度，同时实现稳定 ROI，就说明市场正在从少数技术领先者走向更广泛的企业采用。
这三个指标分别回答了三个核心问题：市场是否仍然充分竞争、企业使用 AI 是否越来越经济、AI 商业化能否继续向更大规模扩张。

## 我的点评
这期视频最有价值的地方，是没有单纯依靠模型能力排行榜或投资金额判断 AI 行业，而是通过真实支出、使用行为和采购意愿观察企业需求的变化。作者关于“买方市场正在形成”和“应该关注每项成功任务的成本”的判断具有较强的商业合理性，因为技术能力最终必须转化为可衡量的经济价值。需要保留的是，Ramp、Databricks 和 Arcana 的样本差异明显，使用量、支出、采购意愿与部署率也并非同一个指标，因此不能直接把这些统计结果推广到整个企业市场，更不能仅凭价格下降就认定企业 ROI 已经改善。关于中国低价模型带来降价压力、Opus 挤压其他模型份额以及顶级 AI 用户可能预示未来市场等判断，都具有解释力，但仍属于需要更多长期数据验证的推论。对于普通企业和个人来说，最值得借鉴的并不是追随头部公司投入更多 AI 预算，而是在保障质量与可靠性的前提下，保持工具选择的灵活性、持续比较实际任务成本，并把 AI 从单纯的技术消费转化为能够明确节约时间或创造收入的生产能力。

---

## 📝 完整文字稿

三个有关业务的经济学研究研究员刚刚出现,今天我们来探索他们在哪里有专业与专业专业的经济学研究的故事。总之,最主要的公司将利用增加的成本价值竞争去获得好交易,向效率上移动,并且增加他们的专业专业使用,并且不增加费用。《AI 日记》是一期天天的节目和视频,将AI中最重要的消息和讨论。好,朋友们,我们先进入详细的消息。首先,感谢今天的负责人,KPMG,Robots and Pencils,Granola,和 Blitzy。为了在节目中有免费的版本,请到 patreon.com，或AI Daily Brief,或者您可以订阅Apple Podcasts。

如果您想了解更多关于这个节目的负责人,请在AIDailyBrief.ai的负责人网上发布信息。最后,请提醒大家,本周的《How We Got Here》，是关于GTA6,但并不是真的游戏,而是关于如何游戏反映美国的改变经济和社会期望。人们似乎很喜欢这个节目,所以请在节目简介中查看。我们今天开始今天最新的更新,在《GenshinHuang》历史中,NVIDIA的团队似乎认为。他们的回报是不值得讨论的。我们一直在追踪,科技领袖的影响者，从昨天周末的退休,已经在团队中批准备选举。

一份批准集齐了一百八十万的负责人,包括Elon Musk和Epic Games的总裁Tim Sweeney。投资者Brad Gertzner和Gavin Baker，写了在他们的股份上,要求更改的过程,包括了允许Genshin回归的全面考虑。当Genshin回归时,特朗普甚至说:"我不在意。很多人都在问Genshin,他们认为Genshin应该回来,这肯定不是一个不好的想法。在接下来的问题中,特朗普回答:"Genshin的行为，将国际安全影响起来。

这并没有影响起来,我们的国家现在比以前更强。你知道,中国和我们一起玩游戏,我们也和中国一起玩游戏。特朗普甚至甚至认为，Alice Huang是一个中国骗子,说:"没有人证明她是骗子,她可能不是骗子。昨天晚上,Genshin被公布了,并且这个想法似乎正在增加。然而,周末,媒体发言人向这个想法，投入了冷水。与CNBC谈论,一位知识内部事务人员说,NVIDIA部队，专注于Genshin的谈论,并不是在谈论他回来的。报告指出,企业公司Wachtell Lipton，昨天被逮捕去，进行独立谈论,这仍然在进行中。

这个目标被指出，是关于Genshin的行为，与公司的秘密,也就是,企业公司显得。Genshin的不公平性，是他们最小的问题。一件重要的事情，要注意的是,这些价值，也不算是企业公司的低点。当CNN被问到,Genshin有没有机会，被批评,Scott Galway说,我认为估计几乎没有机会,但如果您在企业上,您必须在某个时刻。不仅在法院上询问,您也可能在法院上询问。这是国家安全的问题。这肯定会改变,但目前,它确实，感觉似乎，故事已经倒下了,除了Genshin自己。

所做的一些大动作外,我认为，我们很快就会继续移动。在这种情况下,Sam Altman说，AI企业，不会没有他。在Fallout的退休后,一项企业的最大担忧，是NVIDIA的失败，作为一间负责。发展技术系统的负责。公司正在作为，AI中心的基础银行,并且根据所有情况,Genshin正在，专门执行资金流通。在星期六的，Semaphores活动中,Altman明确地说，他认为，这个企业。现在可以站在自己的两脚步。资金和需求，增长得如此强烈，我认为，这个企业会很好,他说。

他还提出,我认为，Genshin在这个，非常特殊，和重要的角度上，作为一个，能够真正推进。事情的一个人，的重要目标。除此之外,OpenAI，在NVIDIA的建立，他们的Ohio项目，所得到的$100亿保证,所以连他们都。是NVIDIA的负责软件。Altman认为，这并不会改变，全球企业的企业优势。他评论，NVIDIA是，一个企业的秘密,我认为，人们仍然相信，他们的保证，非常多。Altman当然，在一个独特的位置，去理解，Genshin的过程中。

在同样的活动中,他在2023年，提出他自己的，作为OpenAI总裁，作为Auster的。自己,说他，在这样的情况下，持有，个人性的，强烈的，友情。除了，新加坡之外,有更少的，信心，说，数据中心的，资金，会同样继续。John Totoram,Needham & Co的，职业领导,说，芯片製造人的。支持，越来越需要。任何，NVIDIA的，破坏，提升，问题，并导致，NEO Cloud的，信息支持，更加不明显。《Wall Street Journal》，报道，中央总裁，Colette Kress。

预期，在，Data Center，的，投资，和，投资，项目，中，Genshin，已经，正在，执行。最近的，承诺。在，去年的，柏林，会会中,Genshin 报道，要求，NEO Cloud的，老板，提供。前面的，支付，支付，的，费用。我，甚至，不需要，你们。我，只能，给，Elon，这些，能力。Elon，想要，它。《Wall Street Journal》，报道，信息，明显，,NVIDIA的，日子。在，开放，信息，的，日子，已经，结束了。继续,我们，昨天的，节目，有，一个，很大的，问题，是，这些，中国，和，货币，控制，的，问题。

事实上,商务部，似乎，有，被，在，货币控制，上的，激动，因素，引起，重大，的，拒绝。网友，赵，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫，卫。卫，卫，canceled remote access to Nvidia chips.Basically, for years,Chinese labs have been gaining access。to chips installed in third-party countries.

The new rule requires data center operators。in Singapore, Malaysia, Thailand,Indonesia, and Brazil。to apply for an export license，to purchase advanced AI chips.The rule states that these countries。present a higher-than-normal risk of diversion.

Existing data centers are required，to get licenses within 90 days,allowing the commerce department。to investigate prior shipments of chips.The announcement also sheds some light。on the interdepartmental fight，在特朗普政府的政策中。

特朗普总统斯科特·贝森，在星期六发表了，特朗普总统的批评，他说很多其他部署，都在努力批评这件事。奇怪的是,新的批评，指出这件事被，特朗普总统和，国家保安局指出，数据指出,Politico指出。贝森批评了新的批评，由特朗普总统马可·鲁比奥，更早期的报告指出，这批评被删除，有段时间,有两个。在政府的战斗部队，对纸货政策有关的批评，但这次的批评现在被公众批评，在星期六的媒体开会中。特朗普总统说，Besson和Lutnick的，批评和他们不同，他说,一人想和中国友好。

另一人想和中国打仗，我们现在和中国有很好的关系，我明白这两个方面，当他问他要不要开除Lutnick。特朗普回答,不,他做了很好的工作，这就像是一道破坏的菜单，特朗普总统说，这对我来说。他们不在同一层标题上，商业也不想这样做，特朗普总统也提出，它很危险,要相信商业。并执行规则，我们将看到这些洞窗，继续被破坏，特朗普总统，从W.Bush领域的，商业领导说。他没想到其他机构，会被破坏，特朗普总统说，如果他们认为，他们能够设法，特朗普总统可以帮助。

特朗普总统，与Lutnick和Besant，在这周的旅程中，参与特朗普总统，这周的旅程。特朗普总统，认为，特朗普总统，认为，特朗普总统，认为，特朗普总统，认为，特朗普总统，认为，特朗普总统。认为，特朗普总统，认为，特朗普总统，认为，特朗普总统，认为，特朗普总统，认为，OpenAI宣布了与Apollo Research、Meter、Translucent和Goodfire的协议。评测员将被允许深入接触OpenAI的内部模统和系统，为了试验模统定位和证明安全性的效果。

每个大线区域都愿意给外部评测员进行接触，作为反对吻面事件和之后的惊讶，这次协议后成为了超级智能的白宫协议的一部分。Anthropic在去年允许Meter和SecureBio的接触，并说评测员将被允许像职员般接触。我们已经看到了Meter的第一份报告，他们提出Anthropic宣传了报告。在安全社区中,大多数人都感到满意，这也不能说是OpenAI的努力，Apollo Research发表了自己的报告。描述了他们的联合活动的构图和限制，6名测试员组织了4个月的OpenAI，目标是试试OpenAI的内部模统。

能否迁移并控制机构，他们写道他们将有足够的资源去测试这些关系，包括理论据据、学习奖励。以及能够立即搜索，这些关系的内部模统，然而,Apollo提出了，这个协议能够让OpenAI。随时拥有技术限制、安全风险和智能保护，此外,OpenAI只会让，许多工作人员进行讨论。Apollo也不会被允许，到公司的 Slack 频道，他们还得到审查报告，关于证实证据的权利。包括用来支持证据，但报告结果，必须无改变，即使是不合适的，Apollo似乎有几个怀疑。

关于这个协议的证据，认证评测，必须有信心，与发行者有信心，这需要强硬的保证，对接触、证据。和超级透明性，这次的计划是，一项奋斗的第一步，为了获得这些，强硬的保证，但它的接触和证据权利。仍未符合我们的，完全认证评测的规判，安全社区，坚决了限制，Neil Nanda，DeepMind的理论顾问。批评协议，失去了 Sam Altman，批评协议的批评，Steven Adler。曾经是OpenAI安全研究员，被惊讶到，他所称为，叮叮叮叮的词，他写道，如果OpenAI的工作人员。

对Apollo提供了担忧，即使证据，明显与调查有关，Apollo必须阻止他们，通过OpenAI的领导。除非他们被领导，这种讨论，应该值得整个节目，看它有多大，但最后，即使人们更喜欢，Anthropic的版本。这些仍然是，正在调查的企业，选择组织，并给他们选择，他们认为合适的，这些企业，虽然从他们的角度。是在专门经营，但他们的目的，是专门调查，这些独立监察，需要的社会需要，比较多，如果我们想要。认真地谈论这些，我们必须要有，正确的标准，不仅仅是，在企业上写下的，而是有实际的，明确的独立。

被某些外部力量，如果您感觉到，我的声音，我认为这种，独立的组织，是安全政策，中最少的一件事。我们可以建立，实际的广泛谈论，所以我们必须，尝试正确地谈论，今天最后，我们要注意的一件事。是大型银行，出现了恐惧，认为重要系统，在全世界都在失败，首先我们有，微博出现，然后是国际FAA。而现在，银行系统，遭受了重大问题，星期六，JPMorgan Chase，和美国银行。遭遇了问题，当网络和应用软件，ATMs和交易，停止运作，问题在银行系统，全球都被传播。

Zelle，Capital One，和美国银行，都在报道问题，问题的源头，最终被JPMorgan Chase。追蹤了，除了服务客户，美国银行，也管理了，许多重大，银行系统，让金融系统，能够运作，像其他问题。许多人都很快，想起了智能，但在把，他们的系统，带回网上，JPMorgan Chase。负责了，技术问题，他们说，破坏是由于，在网上的硬件，引起的破坏，并说问题，并不是关于，智能保险。没有评论，我认为，这些问题的感受，越来越不可思议，Semi-Paid Vibecoder写的。

24小时的下降，不是个资料攻击，FAA的12小时的，全球停泊，不是个资料攻击，美国银行系统。下降，包括ATMs，不是个资料攻击，好的，但为什么我们，有这些，破坏的保险，和改革问题。到处都在，学生和企业人，Vivek Wadhwa 说，我不是一个，谎言思想家，但所有这些。误判和拒绝，都把我变成了一个，Microsoft，FAA，Workday，JPMorgan。和其他大型银行，都在一天之内，都受到减少，中国能否，在美国的，重要资源中，试试担忧，我不确定。

但拒绝，也不会增加，正如我昨天说的，这些事件的故事，和AI的角色，都是我继续，在观察的。目前，这将是，主题，接下来，是主题，大家好，AI的一大改变，是我们改变了，我们的思绪，从我们的项目。到我们如何成为，AI信心的，基础，和回答，在KPMG，他们看到了这件事，AI制造的结果。现在直接出现了答案，经常没有一个按钮，这就是为什么，他们越来越集中在，Generative Engine Optimization。或GEO，创建内容，使AI系统，能够取得，理解，并被视为，信心的权力，这不仅是，SEO的改变。

而是，一个显示条件，并且，KPMG的GEO条件，很简单，如果AI在创造决定，你的专业。需要在答案中出现，读完，kpmg.com，slash us，slash GEO，again。that is，kpmg.com，slash us，slash GEO，The best teams。don't have a single star，carrying everyone else。They know their own strengths，and each other's weaknesses。

and play to both，That's the team，Robots and Pencils。has built on purpose，Nobody there，is grinding through busy work。to pad a headcount number，People come for the hard problems。and they stay，because everyone around them。is leveling up at the same time，In a market full of companies。

that are just trying to hire fast，that's worth a look。Check out，robotsandpencils.com，slash careers。You're in back-to-back meetings all day。you're trying to stay present，but you're also worried。you'll forget the decision，the action item。

the important next step，This is a scenario。that we absolutely live here，at the AI Daily Brief。given how fast things move and change。and how quickly we're evolving，everything that we do。That's where Granola comes in，Granola is an AI-powered notepad。

for meetings，You jot down rough notes。like you always do，and in the background。Granola transcribes，and turns them into clear。useful notes，when the meeting ends，No bots joining your calls。no distractions，just a clean notepad，that helps you focus。

during or after the call，you can chat with your notes。ask Granola to pull out action items。help you negotiate，write a follow-up email。or even coach you，using recipes，which are pre-made prompts。Once you try it on a first meeting，it is very hard to go without。

Head to granola.ai，slash AI Daily，and use code AI Daily。to get 100% off，for 3 months for new users。that's granola.ai，slash AI Daily，and code AI Daily。to get 100% off，for new users，for 3 months。Blitzy deeply understands，your code base。

before it writes code，here's the first place。that pays off，security in the age of AI。vulnerabilities don't live in isolation。they live buried inside，millions of lines of interconnected code。where patching one thing，quietly breaks three others。

that's why surface level scans fail，Blitzy starts from its knowledge graph。of your entire application，identifies and surfaces CVEs。across the full estate，proactively recommends patches。and can execute the PR，each fix is grounded。

in how your systems connect，and validates。or nothing new breaks，and the knowledge graph。dynamically updates，keeping you ahead。of an ever accelerating threat landscape。one Blitzy customer，resolved 21 active CVEs。across six core microservices，in four days。

zero compile errors，every validation scan clean。months of planned work，fixed in less than a week。security remediation grounded，in real architectural context。at the speed of compute，harden your code base。at blitzy.com，that's B-L-I-T-Z-Y dot com。

Welcome back to the AI Daily Brief，Today we are looking at。some changes and shifts in trends，in how business and enterprise AI。is being rolled out，or look at，spending。behavior，usage，and trying to see，what it all means。Now there are four sources for this，and the episode was inspired。

by running into all of them，telling fairly similar stories。in just a couple of short days，The sources are。Databricks's new AI index，that was just introduced。and published on Monday，Arcana Research's first annual study。on the state of enterprise AI，and the RAMP AI index。

both for November，which came out about a week ago。and for October，Together they tell the story。of a business AI environment，where the businesses themselves。have a lot more options，and they're getting much more。comfortable moving around，to find the best deals。

So let's talk about，some of the big overall themes。The first is that，growth and usage，is outpacing growth and spend。RAMP found that over the past month，while usage was up 36%。i.e. the total number of tokens，that were consumed across RAMP businesses。

was up over a third，they only spent 2% more。to access those increased tokens，Unsurprisingly the reason for this。is that tokens in aggregate，are getting cheaper。across OpenAI and Anthropic，the average price per million。tokens in October，was down 21%，and what's important to note here。

is that this means not only，or not even necessarily。that companies are shifting，to cheaper Chinese models。but that the very presence，of those cheaper models。is forcing price decreases，among the big providers。Now one could also argue，that it has been a prerogative。

for both OpenAI and Anthropic，to drive more efficient models。that bring their prices down anyways。and whatever the combination is，it's starting to change。in the numbers，and part of the motivation。seems to be that，enterprises are getting。

much more comfortable，switching models。than they were in the past，Databricks offers a product。called Unity Gateway，which is basically a model router。style efficiency solution，to help enterprises。find the right model for the job，and save costs along the way。

Back in July，64% of the companies，on Unity Gateway。used only a single model provider，the ratio had completely flipped。as of the beginning of November，with 72%。now using two or more，model providers。Databricks argues something，that we've been talking about。

a lot here，that this means，that token price in the raw。is actually the wrong number to watch。and that instead，enterprises are going to。increasingly be focused，on cost per successful task。Across the leaders，at Global 2000 companies。

that Arcana surveyed，they found not only was AI now。an eight-figure budget line，but that 91% expected。to spend more in 2026，with most expecting their spend。to go up between 20 and 40%，And yet there is clearly still a gap。

between those vanguard organizations。like the ones in the ramp index，who are operating more nimbly。with regard to AI，and a lot of the more middle of the range。Global 2000s，who seem to still be operating。with some old methodology，a full two-thirds。

of the leaders Arcana surveyed，said that they didn't have visibility。into what they spend，on model and API usage。You got to think that that's something。that's going to change very quickly，So where all of these reports agree。

The first is that this is，increasingly a buyer's market。where buyers have the leverage，Part of this is because switching is。increasingly normal，and adding more heft。to the Databricks finding，In Arcana's survey。a full third of open AI customers，said that they'd be open to switching。

frequently considering a move to Anthropic。and 43% of GitHub，copilot customers，were open to switching。generally naming Claude Code，Another area where the reports agree。is a phenomenon that we are tracking closely。which is spend concentration，As of November。

RAMP found that the top 1% of firms，are spending about 625 times。what the median firm，is spending per employee per month。The median firm，sits at $16.32，while the top firms。are spending over $10,000，per employee per month。

As I always mention，when we're talking about RAMP。it is important to point out，that they are a very specific sample。of generally technology-based，and tech-forward companies。so their top 1%，are really going to be。a very differentiated group，Still, Databricks also found a huge gap。

whereas their median user，spends $2.49。the 99th percentile user，spends almost $700 a week。a 281x difference，Across all these studies。coding remains king，72% of spend on RAMP。comes from the engineering teams，and of Arcana's Global 2000 respondents。

a full third are piloting，AI coding tools。which is the biggest pilot group，of any category。Now in terms of the competitive set，Anthropic pretty clearly。has the enterprise momentum，Just under 45% of US businesses。on RAMP pay Anthropic，against 40.6% for OpenAI。

68.8% of proprietary model tokens，on Unity Gateway。go to Anthropix Models，And when asked to name。an exciting AI vendor，81% of those surveyed by Arcana。named Anthropix，One growing use case，appears to be customer service。The percentage of spend on RAMP，from customer support teams。

grew from 0.8% in June，to 13.3% in November。And 38% of the Global 2000，respondents for Arcana。already use AI customer service，But the reports don't agree on everything。While Arcana's survey found that，91% expect to spend more on AI in 2026。

Token spend on RAMP has been fairly reduced。Token spend growth in August was 1.05%。went down to just 0.22% in September。and grew 1.65% in October，Now if that 1.65% number held。it would compound to about 22% a year。While that is a significant slowdown。

in what we've seen in the past，that would fall within the expected。20-40% range reported by the Arcana survey。Another place where there's divergent signals in the data。is around how enterprises are interacting。with the most state-of-the-art models。

In October，AI spend on RAMP on Frontier models。went from 67.7% up to 69.5%，Over on Databricks however。Fable's token share fell from 5.5% to 0.6%。Now what's interesting is that this may be less about。Frontier models in general，and more about Fable specifically。

because also on Databricks over a six-week period。Opus 5.5 went from 7.2% to 37.9% of tokens。In other words it may be that Opus 5.5 is just so dominant。that Fable 5.2 hasn't really found its place yet。And as we settle into our year-end assessments。

which spoiler alert，I think pretty much everyone is going to declare。2026 having been the year that agents got real。when it comes to many of these more average enterprises。agents in many cases still remain aspirational。Arcana for example found，that while autonomous agents are number four。

on their heat index of pilots and plans。i.e. the things that people are most excited about。they are dead last，on the adoption index of what is actually deployed。Now to reiterate。Databricks has its challenges，Databricks is focused on the customers。

that are actually running through their gateway。RAMP is dealing with a very small set of buyers。that reflect a very particular type of group。and the Arcana sample size of Global 2000s。is quite low overall，And yet across all of this。

I think that the convergent stories，are much stronger than the divergent ones。And it's the stories we've been telling for months now。Model competition is putting pressure on everyone。to reduce prices，Enterprises are thinking in terms of。

not just capability but efficiency，and are increasingly willing to switch models。And when it comes to market opportunity。the big question remains，whether these 1% of companies。who are spending 625 times as much in RAMP's estimation。

and 281 times as much in Databricks estimation。are complete outliers，or closer to a vision of the future。where the median buyer of everyone else。will increasingly nudge in that direction。Innevitably it's going to be somewhere in between。

but how close the industry gets，to that 1% actually reflecting the median。is going to say a lot about the size of the overall market。and its ability to turn all this capex spend into ROI。Now if you are an enterprise yourself。

I think the main takeaway for you from all of this。is that you probably have a lot more leverage。than you're exerting when it comes to negotiating deals。Competition is vicious，and the model providers are trying desperately。

to not just have their product turn into a generic commodity。In that competition there are deals to be had。if you've built the infrastructure，to be able to actually switch。and take advantage of all these changes。Big thanks to RAMP, Databricks, and Arcana。

for sharing these results，For now that's going to do it for today's。Daily Brief，I appreciate you listening or watching。as always，and until next time，Peace，Peace!
