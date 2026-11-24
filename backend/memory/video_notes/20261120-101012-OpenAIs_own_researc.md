# OpenAI 自家研究人员如今认为，AI 工具比近一半的同事更有价值

- 来源链接：https://the-decoder.com/openais-own-researchers-now-say-they-value-their-ai-tools-more-than-nearly-half-their-colleagues/
- 作者：Maximilian Schreiner
- 提取时间：2026-11-20 10:10
- 类型：网页文章
- 发布时间：2026-11-19 13:08
- 原标题：OpenAI's own researchers now say they value their AI tools more than nearly half their colleagues
- 标签：人工智能、研发、效率

## 🤖 AI 分析

## 一句话概括
OpenAI 的内部研究数据显示，Codex 等 AI 智能体正在大幅改变 AI 研发的工作方式：其使用量、任务完成率和研究人员对它们的依赖程度快速上升，甚至有研究人员宁愿失去 40% 的团队人手，也不愿在三个月内失去现有的编程智能体；但 AI 目前仍缺乏研究判断力和工程质量意识，距离真正自主推动前沿科研还有明显差距。

## 背景与主题
OpenAI 近期披露了一份关于内部研究人员如何使用 AI 工具、以及 AI 如何加速科研工作的报告，重点考察了 Codex、Dots 等内部工具的使用量、经济价值、任务完成率及实际研究效果。报告揭示了一个引人注目的现象：OpenAI 的研究人员已经越来越依赖 AI 智能体，部分员工甚至认为，失去 AI 工具造成的损失可能大于失去相当比例的同事或计算资源。与此同时，内部访谈显示，AI 虽然擅长执行具体任务，却仍然缺少判断什么研究值得做、什么代码足够好、什么结果真正可靠的能力。
文章从研究效率、算力消耗、员工主观评价、技术局限和安全风险等多个角度分析这一变化，并结合竞争对手 Anthropic 的研究加速情况，讨论 AI 从科研辅助工具逐渐走向自主科研系统的可能性。

## 核心观点

### 1. OpenAI 内部 AI 工具的使用量正在爆发式增长，AI 已成为科研工作的基础设施
OpenAI 的内部工具，包括 Codex 和 Dots，最近出现了非常明显的使用量增长。按照常规 API 公开标价计算，2026 年 10 月，一名处于使用量中位数的研究人员每天消耗的 Token，理论价格相当于 2,400 美元，比前一个月增长 62%。使用量最高的前 10% 研究人员，每天的理论 Token 消耗价值甚至达到 23,000 美元，约为普通中位数研究人员的 9.6 倍，而且这一群体的理论消耗价值较前月翻倍。这里的数字并不代表 OpenAI 真正需要每天向外部支付这么多钱，而是把内部模型使用量换算成公开 API 价格，用于衡量资源消耗规模。其真正意义在于：AI 已经不再只是研究人员偶尔调用的辅助工具，而是越来越接近一种持续运行、深度嵌入日常科研流程的生产基础设施。
这一变化还意味着，研究人员之间的 AI 使用能力可能出现显著分化：高频用户正在把更多工作交给智能体，而这种使用差异可能进一步影响个人的工作方式与产出效率。不过，原文并没有提供个人产出与 Token 消耗量之间的直接关系，因此不能简单认为使用越多的人科研能力就越强。

### 2. AI 智能体通过并行工作，让一名研究人员能够同时调动多个“数字劳动力”
报告将 AI 智能体运行时间统一折算成每天八小时的工作日，发现每名研究人员在一个自然日内，平均能够调动相当于 5.7 个八小时工作日的智能体运行时间。对于 Pretraining（预训练）和 Post-training（后训练）团队，这一数字更高，约为 8 个工作日。换算成小时，前者相当于每日约 45.6 小时的智能体运行时间，后者相当于约 64 小时，明显超过一名人类研究人员一天能实际工作的时间。更重要的是，超过三分之二被追踪的研究人员，在使用高峰时同时运行过至少 4 个 AI 智能体，说明并行执行任务已经成为相当普遍的工作方式。AI 给科研带来的变化因此不只是让某项任务执行得更快，而是让研究人员能够同时安排多个任务，使工作流程从传统的人工串行推进转向人机协作下的并行推进。
但需要区分：这些数字衡量的是智能体运行时间，而不是经过质量折算的人类有效劳动时间。一个智能体运行八小时，并不意味着它一定完成了相当于一名人类工程师八小时的有效工作，因为其中可能包含无效探索、错误尝试和重复计算。

### 3. AI 的计算资源消耗已经具有很高的经济规模，但在 OpenAI 整体算力预算中仍只占很小比例
按照常规 API 价格折算，2026 年 9 月，内部 AI 智能体运行量对应的理论成本已经达到研究人员常规工资成本的 两倍。这一数字很容易让人产生“AI 的成本已经超过人类研究人员”的印象，但文章明确指出，该比较没有纳入股权薪酬，而股权通常占 OpenAI 员工总薪酬的 70%—80%。因此，如果按照完整薪酬计算，AI 与人类研究人员之间的成本关系就不能直接用“两倍”来描述。另一方面，内部智能体使用量只占 OpenAI 总研究算力的 2%，说明尽管个人层面的 AI 使用看起来非常密集，但相对于整个公司的模型训练和研究计算规模，这部分资源仍然很小。这个对比揭示出一个重要特点：科研智能体可能以相对有限的总算力占比，改变大量日常研发活动，但究竟能创造多少净经济价值，还需要结合实际工作成果、质量和机会成本进行评估。
从经营和资源配置角度看，这意味着 AI 辅助科研可能是一种值得持续增加投入的方向，因为它有机会提高研究人员对现有计算资源的利用效率。但目前文章没有给出严格的投入产出比，也没有证明增加智能体算力就一定能获得同比例的研发效率增长。

### 4. AI 自主完成长时间任务的能力明显提升，但任务越复杂，成功率仍然越低
OpenAI 统计了 2026 年 3 月至 10 月期间，AI 智能体在无需人工干预情况下完成不同长度任务的能力变化。对于预计需要 2—4 小时的任务，AI 的自主成功率从 23% 增长到 46%，提高了 23 个百分点，约为原来的两倍。对于预计需要 4—8 小时的任务，成功率从 13% 增长到 35%，提高了 22 个百分点，相对提升更为明显。这表明，AI 不仅在完成简单、短时间任务方面变强，也开始能够承担更长、更连续的工作流程。但即使到 10 月，四到八小时任务的成功率依然只有 35%，意味着在这一评估条件下，大多数较长任务仍然无法一次自主完成。
这里最重要的区别是：AI 能够连续运行很长时间，不等于它能够可靠地完成同等复杂度的工作。 任务时间越长，往往需要处理的中间状态、依赖关系、判断节点和潜在错误就越多，而这些因素都会增加智能体失败的概率。AI 的能力边界正在向外扩张，但距离完全独立承担复杂科研工程任务仍有距离。

### 5. AI 擅长执行规则明确的日常工作，却不擅长复杂工程系统的搭建
OpenAI 使用 Epoch AI 的任务分类体系（Epoch AI taxonomy）分析了智能体在不同科研任务上的表现，发现各类任务之间存在明显差距。在训练运行监控（Training-run monitoring）方面，智能体的成功率达到 79%；在独立回答技术问题方面，成功率达到 72%，说明其处理相对明确、目标清晰的任务已经比较可靠。但是，在构建评估环境和强化学习环境方面，成功率只有 29%；在为模型推理和服务系统编写代码方面，成功率更低，只有 25%。这些复杂任务通常涉及架构设计、系统约束、代码质量、性能要求和多个组件之间的协同，远不只是根据已有知识生成一段代码。由此可以看出，AI 的主要优势仍然集中在执行、监控、查询和局部问题处理，而不是独立完成要求较高整体判断能力的工程建设。
这也解释了为什么 AI 工具使用量可以迅速增长，而科研人员却仍然不可替代：大量日常工作可以交给 AI，但系统设计、复杂工程把关及重要技术路线决策仍需要经验丰富的人类研究人员参与。

### 6. OpenAI 内部研究人员对 AI 的主观估值极高，部分人宁愿失去同事或算力，也不愿失去编程智能体
在一项覆盖 101 名员工的内部调查中，研究人员在中位数水平上表示：相比连续三个月无法使用当前的编程智能体，他们宁愿失去团队 40% 的人员，或者失去 30% 的计算资源。在另一项只有 28 名员工参加的快速投票中，有 27 人更倾向于选择最新的内部 AI 模型，而不是一名处于职业中期的人类工程师，比例约为 96.4%。这些结果反映出，部分 OpenAI 研究人员已经对 AI 编程工具形成很强的依赖，并赋予其极高的主观工作价值。原因可能包括智能体能够全天候运行、同时处理多个任务、快速执行重复劳动，并让研究人员集中精力处理更高层次的问题。但原文特别指出，101 人调查不具代表性，28 人快速投票样本也很小，因此这些数字只能反映受访员工的偏好，不能证明 AI 已经客观具备取代 40% 人类研发岗位的能力。
尤其要注意，调查提出的是一种带有特定条件的取舍：三个月无法使用现有智能体，与失去一定比例的团队人员或算力，哪一种更难接受？ 这种主观偏好既不等于严格的生产率测算，也不等于现实中企业可以直接裁撤相同比例的人手。文章标题之所以引人注目，正是因为它将这种内部偏好概括为研究人员认为 AI 比接近一半的同事更有价值。

### 7. AI 最大的短板不是执行速度，而是缺乏“科研品味”、质量判断力和正确的问题意识
OpenAI 对 10 名研究人员进行的定性访谈，揭示了大规模使用 AI 智能体带来的负面影响。受访者指出，当前模型缺乏判断优秀研究想法、代码质量和数据质量的 “taste”（品味、鉴别力），也就是说，它们可能会执行任务，却未必清楚什么方向值得研究、什么结果真正具有价值。具体问题包括：智能体在不必要的步骤中兜圈子、在分析中作出错误假设、提交质量低劣的 **“AI slop”（AI 生成的低质内容）**代码修改，以及产出根本无法使用的数据文件或数据成果。这些失败不仅影响代码和研究质量，还可能白白消耗大量计算资源，让表面上很勤奋的智能体实际降低团队效率。因此，OpenAI 研究人员强调，密切的人类监督仍然不可缺少，不能仅凭智能体能够自主运行，就认为它能可靠管理整个科研任务。
这一点揭示了 AI 科研自动化中的重要矛盾：模型越能自主执行任务，它也就越有可能在缺乏监督时，把错误方向持续执行下去。AI 可以把正确方案放大成大量成果，也可能把一个错误假设放大成大量无效代码、数据和算力消耗。

### 8. 当前重大模型突破的核心想法仍主要来自人类，AI 尚未成为独立的科研思想来源
根据受访团队的说法，GPT-6 Astra 和 GPT-6.2 Astra 在后训练和安全研究领域的关键概念性想法，均由人类研究人员提出。这说明，尽管 AI 已经广泛参与实际研发工作，但在文章所调查的重要研究突破中，人类仍然承担了关键创新思想的提出者角色。与此同时，研究人员也提到一个值得关注的例外：在 GPT-6.2 Astra 的预训练工作中，有个别研究人员表示，通过与 Codex 对话获得了重要研究洞见。这个案例意味着 AI 的角色可能正在从单纯的任务执行者，逐渐扩展到研究讨论伙伴，甚至在某些情况下帮助人类发现新的思路。不过，文章并没有说明这些洞见是否直接构成最终的关键技术创新，也没有给出可量化的贡献比例，因此不能据此认定 AI 已经具备独立发现前沿科研方向的能力。
目前较清晰的分工是：人类负责决定什么问题值得研究、提出核心概念和作出关键判断，AI 负责加快实验、编码、监控、技术问答及部分探索工作。 未来最值得关注的变化，不只是 AI 能否写出更复杂的代码，而是它能否开始稳定提出有价值的新研究问题和技术方案。

### 9. AI 科研加速已经成为行业竞争焦点，但进步未必线性，自动化程度越高越需要安全治理
OpenAI 在报告结论中提醒，目前观察到的人机协作数据未必可以线性外推，也就是说，不能直接按照过去几个月的增长速度预测未来的科研效率。公司提到，AI 最近在数学领域取得了快速突破，因此类似的突变式进展，也可能随着模型自主性提高而发生在深度学习研究中。与此同时，独立评估机构 METR 在对竞争对手 Anthropic 进行为期 11 周的内部观察后估计，AI 的使用使该公司的研发速度接近翻倍；不过，这属于另一项研究，其衡量方法不能直接与 OpenAI 的任务成功率等指标混为一谈。OpenAI 则早在 2026 年 9 月初发布的首份研究加速报告中宣布，已达到自行设定的 **“自动化 AI 研究实习生”**目标，表明 AI 科研自动化正从愿景逐渐走向实际部署。然而，OpenAI 首席科学家 Jakub Pachocki 也曾在配套文章中警告失去控制的风险，因为审计发现监督系统存在许多缺口，这意味着研发加速与安全监管必须同步推进。
这一趋势包含两种可能同时发生的变化：一方面，模型能力不断增强，AI 可能参与更大比例的科研活动；另一方面，自动化越深入，错误决策和监督失败带来的后果就可能越严重。真正成熟的 AI 科研系统，不仅需要更强的自主研发能力，也需要更可靠的验证、审计和控制机制。

## 关键事实与数据

### 一、AI 工具使用量和经济价值

| 指标 | 具体数字或事实 | 含义 |
| --- | --- | --- |
| 主要内部工具 | Codex、Dots | 用于辅助编程、科研等活动 |
| 统计月份 | 2026 年 10 月 | Token 消耗规模的主要观察月份 |
| 研究人员每日 Token 理论价值中位数 | 2,400 美元 | 按常规 API 标价换算 |
| 中位数月度增长率 | 62% | 相比前一个月 |
| 前 10% 高频用户每日理论价值 | 23,000 美元 | 约为中位数的 9.6 倍 |
| 高频用户月度变化 | 翻倍 | 相比前一个月 |
| 每人每日平均智能体运行量 | 5.7 个八小时工作日 | 约等于 45.6 小时智能体运行时间 |
| 预训练与后训练团队 | 约 8 个八小时工作日 | 约等于 64 小时智能体运行时间 |
| 高峰期并行使用情况 | 超过三分之二研究人员至少同时运行 4 个智能体 | 说明并行使用相当普遍 |
| 2026 年 9 月理论 AI 运行成本 | 相当于常规工资成本的 2 倍 | 未计入股权薪酬 |
| 股权占 OpenAI 总薪酬比例 | 70%—80% | 不能忽略这一主要薪酬部分 |
| 内部智能体占总研究算力 | 2% | 说明对整体研究计算预算的占比仍较小 |

重要口径说明： 2,400 美元和 23,000 美元是根据公开 API 价格计算的理论使用价值，不代表企业实际对外支出，也不代表员工创造的净收益。5.7 个工作日、8 个工作日则是智能体运行时间的换算值，不是已经证明的等效人类劳动产出。

### 二、AI 自主任务完成率的变化
2026 年 3 月 → 10 月，成功率变化

3 月

10 月

单位：%；由原文数据整理。成功率为无需人工干预下的估计值。

| 任务类型 | 3 月成功率 | 10 月成功率 | 提高幅度 |
| --- | --- | --- | --- |
| 2—4 小时任务 | 23% | 46% | +23 个百分点 |
| 4—8 小时任务 | 13% | 35% | +22 个百分点 |

这组数据体现出两点：一是仅仅七个月左右，智能体自主完成任务的能力已有明显进步；二是较长任务的成功率仍然偏低，说明真正的端到端自动化还有很大改进空间。

### 三、不同科研任务的 AI 成功率
按 Epoch AI 任务分类体系划分

单位：%；原文披露的各类任务成功率。

从这些数字可以看出，最高成功率和最低成功率之间相差 54 个百分点。
相对成熟的任务包括训练运行监控、技术问答；困难的任务则集中在环境搭建、推理服务代码等复杂工程环节。这说明评价 AI 的研发能力时，必须区分任务类型，不能只说“AI 写代码成功率有多高”。

### 四、OpenAI 内部员工调查结果

| 调查项目 | 样本规模 | 关键结果 |
| --- | --- | --- |
| 内部主观价值调查 | 101 人 | 中位数受访者宁愿失去 40% 的团队人员，也不愿三个月不用现有编程智能体 |
| 同一调查中的计算资源比较 | 101 人 | 中位数受访者宁愿失去 30% 的算力，也不愿三个月不用现有编程智能体 |
| AI 与人类工程师偏好快速投票 | 28 人 | 27 人选择最新内部 AI 模型 |
| AI 偏好比例 | 27/28 | 约 96.4% |
| 定性访谈 | 10 人 | 讨论 AI 研发工具的实际缺陷和风险 |

原文明确说明，101 人调查不具有代表性。所有主观偏好结果均应与真实的工作效率、实际招聘和裁员决策区分开来。

### 五、涉及的公司、机构、人物与模型

| 名称 | 类型 | 在文章中的作用 |
| --- | --- | --- |
| OpenAI | AI 公司 | 发布内部 AI 科研加速相关数据的主体 |
| Codex | AI 编程工具 | 研究人员主要使用的编程与科研辅助工具之一 |
| Dots | 内部 AI 工具 | 使用量增长的内部工具之一 |
| GPT-6 Astra | AI 模型 | 其后训练与安全领域关键概念据受访团队称来自人类 |
| GPT-6.2 Astra | AI 模型 | 后训练、安全领域的关键想法来自人类；预训练中出现 Codex 提供重要洞见的案例 |
| Epoch AI | AI 研究与评估机构 | 其任务分类体系被用于分析 AI 的任务能力 |
| METR | AI 能力评估机构 | 对 Anthropic 内部 AI 使用对研发速度的影响进行研究 |
| Anthropic | AI 公司 | OpenAI 的竞争对手，METR 研究的观察对象 |
| Jakub Pachocki | OpenAI 首席科学家 | 警告 AI 自主化可能引发失控风险，强调监督缺口 |

### 六、重要时间节点
- 2026 年 3 月： OpenAI 自主智能体在 2—4 小时任务上的估计成功率为 23%，在 4—8 小时任务上的估计成功率为 13%。
- 2026 年 9 月初： OpenAI 发布首份研究加速报告，宣布达到自设的“自动化 AI 研究实习生”目标。Jakub Pachocki 同时就监督系统的缺口提出风险警告。
- 2026 年 9 月： 按常规 API 价格换算的内部智能体运行成本，相当于研究人员常规工资成本的两倍。
- 2026 年 10 月： 每名研究人员每日 Token 消耗理论价值中位数达到 2,400 美元，前 10% 高频用户达到 23,000 美元；2—4 小时和 4—8 小时任务成功率分别提高至 46% 和 35%。
- 文章所述近期： METR 对 Anthropic 进行为期 11 周的内部观察，估计 AI 使用使研发速度接近翻倍。原文未明确给出这项观察的具体起止日期。

## 金句摘录

### 1. AI 的价值已经开始挑战传统团队人员配置
“In an internal, non-representative survey of 101 employees, researchers said at the median that they would rather give up 40 percent of their team's staff or 30 percent of their compute capacity than go three months without current coding agents.”

中文翻译： 在一项覆盖 101 名员工、不具有代表性的内部调查中，研究人员的回答中位数表明，他们宁愿放弃团队 40% 的人员，或者放弃 30% 的计算资源，也不愿连续三个月无法使用当前的编程智能体。
理解： 这是整篇文章最具冲击力的发现。它反映出 AI 工具对部分研究人员的主观价值已经非常高，但这种选择并不直接等同于 AI 能够取代 40% 的员工。

### 2. 几乎所有受访者都更愿意选择最新 AI 模型
“In a separate quick poll of 28 employees, 27 preferred the latest internal model over a mid-career human engineer.”

中文翻译： 在另一项针对 28 名员工的快速投票中，27 人更倾向于选择最新的内部 AI 模型，而不是一名处于职业中期的人类工程师。
理解： 这一结果体现出特定受访群体对 AI 的极高评价，同时也提醒我们，主观偏好和经过验证的工程能力是两回事。

### 3. AI 真正缺少的是对好研究与高质量成果的鉴别力
“The models lack any "taste" for good research ideas and for code and data quality, according to the interviewees.”

中文翻译： 根据受访研究人员的说法，这些模型缺乏辨别优秀研究想法、代码质量和数据质量的“品味”或鉴别力。
理解： “taste” 是理解当前 AI 科研局限的关键概念。AI 可以生成大量内容，却不一定知道哪些内容真正值得保留、信任或继续研究。

### 4. 没有人类监督，AI 可能浪费大量计算资源
“Close human oversight is essential to avoid wasted compute cycles.”

中文翻译： 为了避免浪费计算周期，密切的人类监督至关重要。
理解： AI 越是能够大规模并行运行，错误方向造成的资源浪费就越值得警惕。自主执行能力必须与验证能力相匹配。

### 5. 关键研究思想仍然来自人类
“The key conceptual ideas for GPT-6 Astra and GPT-6.2 Astra came exclusively from humans in the post-training and safety areas, according to the teams interviewed.”

中文翻译： 根据受访团队的说法，GPT-6 Astra 和 GPT-6.2 Astra 在后训练及安全领域的关键概念性想法，完全来自人类研究人员。
理解： 这句话明确划出了当前 AI 科研能力的一条重要边界：执行大量科研任务，不等于已经具备独立提出核心科研思想的能力。

### 6. AI 对科研的影响可能不是线性增长
“OpenAI cautions in its conclusion that the data gathered so far from human-AI collaboration may not extrapolate linearly.”

中文翻译： OpenAI 在结论中提醒，目前从人类与 AI 协作中收集的数据，可能无法用于简单的线性外推。
理解： 未来可能遇到能力瓶颈，也可能出现突然的技术突破。过去几个月的效率增长率，并不能直接代表未来几年一定会发生的变化。

## 值得记住的点 / 行动建议
以下结合原文披露的事实，提炼出可用于科研团队、工程团队和普通知识工作者的实践方法。其中一些是文章明确指出的方向，另一些是根据数据和案例归纳出的应用建议。

### 1. 不要只把 AI 当成问答工具，而要尝试把它变成能够执行任务的智能体
从 OpenAI 的使用方式来看，AI 的价值不仅来自快速回答问题，更来自能够持续执行、自动处理多步骤任务。研究人员可以在一天内调动相当于多个工作日的智能体运行时间，核心就在于把具体工作交给 AI，而不只是与模型进行单轮对话。
实际应用时，可以逐步将 AI 从问答用途扩展到任务执行，例如代码编写、测试用例生成、日志分析、文档整理、实验结果汇总和技术资料查询。
一个值得尝试的工作方式是：把一项复杂工作拆成若干相对独立的子任务，明确每项任务的输入、输出和验收条件，再交给 AI 分别处理。
但不要一开始就让 AI 完全接管复杂项目，应该从低风险、易验证的任务开始积累经验。

### 2. 优先自动化成功率高、目标清晰、结果容易验证的任务
OpenAI 的数据显示，AI 在训练运行监控和技术问答方面的成功率分别达到 79% 和 72%，明显高于复杂环境搭建和推理服务代码任务。
因此，为 AI 选择工作时，应该重点考虑三个条件：任务目标是否清楚、结果是否容易检查、失败后是否容易修复。
适合优先尝试的任务包括自动检查日志和指标异常、回答标准化技术问题、整理已有文档、生成基础测试代码以及识别重复性错误。
对于需要复杂架构设计、性能权衡或大量隐含业务知识的任务，则应采用更强的人工参与机制。
核心原则是：先让 AI 做它已经比较擅长的事情，再逐步扩大其自主权限。

### 3. 使用多个智能体并行执行任务，但要建立统一的验收流程
OpenAI 超过三分之二的被追踪研究人员，在高峰期至少同时运行过四个智能体。
对普通技术团队来说，可以借鉴这种并行思路。例如，一个智能体负责生成代码，第二个负责寻找潜在错误，第三个负责生成测试，第四个负责整理文档与变更摘要。
不过，真正提高效率的前提是这些任务彼此之间的依赖关系足够少，否则多个智能体可能重复工作、相互修改同一文件，甚至制造新的冲突。
实施时应明确任务边界、允许修改的内容、预期交付物和最终负责验收的人。
建议先用两个独立任务试验并行流程，再根据交付质量和人工检查成本决定是否增加智能体数量。

### 4. 把人的精力集中在问题定义、研究判断和质量控制上
文章最重要的启示之一，是人类与 AI 的优势并不完全重叠。
AI 能够快速生成代码、处理资料和执行实验，但对于研究方向的价值、代码设计的合理性以及结果是否可信，仍然需要人类判断。
因此，研究人员或工程师应尽量减少亲自处理重复性操作的时间，把更多精力用于定义问题、设计实验、建立评价标准以及分析异常结果。
例如，在开展一项机器学习实验时，可以由人类明确假设、关键指标、数据约束和停止条件，再由 AI 执行相关脚本和整理数据。
AI 负责扩大执行能力，人类负责保障方向正确，这比简单追求“所有任务都交给 AI”更符合文章呈现的真实情况。

### 5. 为 AI 建立明确的质量门槛，避免“AI slop”污染工作成果
研究人员明确提到，智能体可能提交低质量代码、错误分析和不可用的数据成果。
这意味着，AI 生成的内容不能因为看起来完整、格式规范或执行过程很长，就被默认视为可靠。
在工程实践中，至少需要建立代码测试、静态检查、数据校验和人工审核等质量关卡；在科研工作中，还应要求结论能够追溯到原始数据、实验配置和具体证据。
对于关键结果，可以采用独立复核，例如让另一套检查流程验证计算逻辑，或者要求 AI 列出假设、局限和可能出错的位置。
尤其应该避免让同一个智能体既负责执行，又在没有独立验证的情况下给自己的结果判定合格。

### 6. 衡量 AI 的价值，不能只看 Token、运行时间或生成数量
OpenAI 的数据提供了大量使用量指标，但文章也表明，使用规模和有效产出并不是同一回事。
每天运行 64 小时的智能体，不一定比运行 20 小时但任务选择更准确的智能体更有价值。
对于团队而言，建议同时记录四类指标：实际完成的任务数量、通过验收的任务比例、节省的人工时间，以及消耗的算力或费用。
如果智能体自动生成了大量代码，却需要人工长时间修复，那么真正的效率收益可能远低于表面数据。
评价 AI 工作流时，应该优先关注“每单位成本获得多少被验证的有效成果”，而不是单纯追求使用量增长。

### 7. 对 AI 能否替代员工的结论保持谨慎，避免直接用调查偏好推算裁员比例
“宁愿失去 40% 的团队人员，也不愿失去 AI”是非常有传播力的说法，但必须放回原本的调查条件中理解。
首先，101 人的内部调查不具代表性；其次，比较对象

---

## 📝 完整文字稿

Usage of internal tools like Codex and Dots has surged recently, according to the report. At regular API list prices, the median researcher would have consumed $2,400 worth of tokens per day in October, up 62 percent from the previous month. Among the top 10 percent of users, that theoretical value doubled to $23,000 per day.

Converted into eight-hour workdays, the agents reportedly run the equivalent of 5.7 workdays per researcher per calendar day, and about eight in the pre- and post-training teams. More than two-thirds of tracked researchers ran at least four agents in parallel at peak usage.

The theoretical API equivalent of that agent runtime was twice as high as researchers' regular salary costs in September, according to OpenAI. That calculation excludes equity packages, though, which make up 70 to 80 percent of total compensation at OpenAI. Measured against the company's total research compute, internal agent use accounted for just 2 percent.

A large share of AI usage goes toward communication and coding. | Image: OpenAI

### High success rates on routine tasks, weaknesses in code scaffolding

Between March and October, the estimated success rate of autonomous agents working without human intervention on two- to four-hour tasks rose from 23 to 46 percent, according to OpenAI. For four- to eight-hour tasks, the rate climbed from 13 to 35 percent. A breakdown using an Epoch AI taxonomy shows, however, that the systems mainly handle simple tasks.

Agents reportedly complete training-run monitoring 79 percent of the time and answer technical questions independently 72 percent of the time, but they frequently fail at more complex engineering work. The success rate for building evaluation and reinforcement-learning environments sits at 29 percent, and for writing code for inference and serving systems at 25 percent.

In an internal, non-representative survey of 101 employees, researchers said at the median that they would rather give up 40 percent of their team's staff or 30 percent of their compute capacity than go three months without current coding agents. In a separate quick poll of 28 employees, 27 preferred the latest internal model over a mid-career human engineer.

### Lack of research taste requires human oversight

Qualitative interviews with ten researchers revealed the downside of heavy usage. The models lack any "taste" for good research ideas and for code and data quality, according to the interviewees. Agents get lost in unnecessary steps, make wrong assumptions in analyses, and submit subpar "AI slop" code changes along with unusable data artifacts. Close human oversight is essential to avoid wasted compute cycles.

The key conceptual ideas for GPT-6 Astra and GPT-6.2 Astra came exclusively from humans in the post-training and safety areas, according to the teams interviewed. Only in pretraining for GPT-6.2 Astra did individual researchers say they gained important insights through dialogue with Codex.

OpenAI cautions in its conclusion that the data gathered so far from human-AI collaboration may not extrapolate linearly. The company points to recent, rapid AI breakthroughs in mathematics and considers it possible that similarly abrupt advances could occur in deep-learning research itself as models gain more autonomy.

The evaluation organization METR had recently estimated, after an eleven-week look inside competitor Anthropic, that AI use there had nearly doubled the pace of development. Before that, OpenAI had declared in its first research-acceleration report in early September that it had reached its self-imposed goal of an automated AI research intern. Chief scientist Jakub Pachocki warned of losing control in an accompanying post, after an audit revealed numerous gaps in the oversight system.
