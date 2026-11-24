# AI 行业增长依然强劲，但增速正在放缓

- 来源链接：https://the-decoder.com/ai-industry-growth-remains-strong-but-the-pace-is-slowing/
- 作者：Matthias Bastian
- 提取时间：2026-11-20 10:10
- 类型：网页文章
- 发布时间：2026-11-19 19:28
- 原标题：AI industry growth remains strong, but the pace is slowing
- 标签：AI行业增长、Token价格战、企业AI支出、收入增速、算力投资

## 🤖 AI 分析

## 一句话概括
AI 行业仍在高速增长，但正在出现“Token 使用量暴涨、单位价格持续下降、企业实际支出增速放缓、收入向头部公司集中”的新趋势；未来能否通过更强大的模型和更深入的企业应用维持增长，将决定 AI 公司能否收回巨额算力基础设施投资。

## 背景与主题
2026 年 11 月，两家支付数据公司 Ramp 和 Stripe 分别发布 AI 行业相关数据，从企业购买 AI 服务的支出端，以及 AI 公司获得客户付款的收入端，观察整个行业的增长情况。
数据显示，AI 使用规模仍在迅速扩大，越来越多的企业开始购买 AI 产品，部分 AI 公司的收入增长超过 100%，但 Token 价格下降、API 支出见顶回落、短期收入增速降低等现象也同时出现。
文章重点分析了 OpenAI、Anthropic、Google、xAI 等 AI 服务提供商的竞争格局，以及 OpenRouter 所记录的 API 调用趋势，并对美国、英国、欧盟等市场进行了比较。
作者的核心判断是：AI 并没有停止增长，更谈不上已经衰退，但行业正在从“需求和收入同步爆发”的阶段，逐渐进入“使用量继续扩张、价格竞争加剧、收入增长更难”的阶段。 这对计划投入巨资建设算力基础设施的 AI 公司尤其重要。

## 核心观点

### 1. AI Token 使用量增长明显快于实际支出，行业正在出现“量增价降”
根据 Ramp AI Index，在截至 2026 年 11 月 15 日的一周，企业购买 AI API 所产生的 Token 总支出，比两周前的高点下降了 6.3%。但如果与截至 10 月 18 日的一周比较，Token 支出仍增长了 12%，说明行业需求并没有消失，只是支出增速正在放缓。与此同时，同一时期的 Token 使用量却增长了 27.2%，远远快于支出的增长。换句话说，企业使用的 AI 服务越来越多，但为每单位 AI 使用量支付的金额却在下降。AI 的使用规模和商业收入正在逐渐脱钩，Token 消耗量已经不能直接代表 AI 公司的收入增长。
这里最值得注意的，是两个增长率之间的差距：
- Token 使用量增长：27.2%
- Token 支出增长：12%
- 两者相差：15.2 个百分点

如果仅根据这两组总量数据进行计算，可以推导出同期每 Token 的平均支出约下降了 11.95%。这一计算反映的是该统计口径下的平均支出变化，不能直接等同于某家 AI 公司官方 API 定价的降幅。
背后的商业逻辑是：AI 使用量增长，不等于 AI 服务商能够按同样速度增加收入。

### 2. OpenAI、Anthropic 与中国 AI 厂商之间的价格战，正在持续压低 Token 单价
Ramp 数据显示，2026 年 11 月中旬，OpenAI 和 Anthropic 合计统计的每百万 Token 平均价格已经下降到 0.45 美元，较上个月下降 11.2%。其中，OpenAI 的平均价格为每百万 Token 0.38 美元，Anthropic 则为 0.50 美元，后者比前者高约 31.6%。文章认为，这种价格下降与 OpenAI、Anthropic 以及中国 AI 模型供应商之间的竞争直接相关。随着模型提供商不断降低价格，企业可以用相同预算调用更多 Token，进而刺激 AI 应用的使用规模。但对模型供应商而言，降价也意味着必须依靠更大的使用量、更低的成本或更高价值的服务，才能维持收入和盈利能力。
需要强调，文章使用的是 Ramp 观察到的平均价格，并不是所有模型、所有客户、所有输入输出 Token 都统一执行这一价格。实际价格还会受到模型选择、使用结构、缓存和折扣等因素影响，因此不能简单认为 OpenAI 所有产品都比 Anthropic 便宜。
这也揭示出 AI 行业的一项长期变化：基础模型的通用推理能力可能越来越便宜，企业之间的竞争将逐渐从单纯的模型价格，延伸到模型效果、可靠性和商业应用价值。

### 3. OpenRouter 数据进一步证明：AI 使用规模爆炸，但对应收入增长远远跟不上
除了 Ramp，文章还引用了 API 路由平台 OpenRouter 的数据，作为独立的观察角度。根据 Peter Walker 在 X 上发布的分析，自 2026 年年初以来，OpenRouter 平台上来自 OpenAI、Anthropic 和 Google 的闭源权重模型（closed-weight models），每周 Token 使用量增长了 1,215%，但每周支出仅增长 455%。换成倍数来看，Token 使用规模达到年初的约 13.15 倍，而支出规模只有年初的约 5.55 倍，两者出现极大差距。OpenRouter 的支出数据在 2026 年 10 月 5 日当周达到峰值，随后持续下降，而文章展示的数据截至 11 月 9 日当周。这表明即便是在高速增长的 AI API 使用场景中，越来越多的 Token 也不一定能够转化成相同比例的收入。
根据上述倍数进一步推算，OpenRouter 这一样本中的平均每 Token 支出，相比年初约下降 57.8%。
不过，这属于根据总量变化计算出的综合结果，不能直接解释为所有模型都降价了 57.8%。模型使用结构变化、不同模型的定价差异等因素，也可能影响平均值。
作者特别提醒，OpenRouter 只覆盖通过该平台路由 API 的特定用户群体，而且这里的图表仅涵盖三家公司的闭源权重模型，因此不能把它直接当成全球 AI 市场的完整数据。

### 4. Anthropic 在企业 Token 市场占据领先位置，但领先不等于增速最快
根据 Ramp AI Index，截至 2026 年 11 月 15 日当周，Anthropic 占所统计 Token 总支出的 58.7%，比上个月提高 1.7 个百分点，其 Token 使用量份额更达到 59.4%。相比之下，OpenAI 的 Token 支出份额为 37.2%，使用量份额为 37.7%，明显落后于 Anthropic。Google 和 xAI 的对应市场存在感较小，文章列出的份额分别为 1.4% 和 2.4%，但没有进一步解释具体业务结构。这说明在 Ramp 所覆盖的企业客户样本里，Anthropic 已经在 Token 消费和实际支出两个维度占据优势。不过，市场份额高与当前增长速度快并不是一回事：2026 年 10 月，Anthropic 的 Token 支出环比仅增长 0.5%，OpenAI 却增长了 2.1%。
这组数据揭示了两个不同层面的竞争指标：
- 市场份额反映当前谁占据了更多业务规模。
- 增长速度反映谁正在更快地扩大业务。

因此，不能因为 Anthropic 的份额领先，就直接判断 OpenAI 的商业需求正在减弱。
文章的小标题使用了“Anthropic 在 IPO 当日主导 Token 市场”的说法，并提到 Kharazian 在 X 上作出相关表述，但原文没有交代 IPO 的具体日期、上市交易信息或相关公告。这一说法应作为原文中的引用性表述保留，不宜仅凭本文就认定 Anthropic 已完成 IPO。

### 5. 企业采用 AI 的比例持续上升，说明需求基础仍然在扩大
Ramp 数据显示，2026 年 10 月，在其追踪的美国企业中，已经有 56.8% 的企业为 AI 产品或服务付过费。这一比例比 9 月提高了 1 个百分点，比一年前提高了 13.3 个百分点，意味着 AI 付费使用已逐渐成为企业经营活动中常见的一部分。在具体供应商方面，Anthropic 的企业采用率为 44.8%，OpenAI 为 40.6%，两家公司都覆盖了相当可观的企业客户群。这些数据表明，即使 API 单价持续下降、短期 Token 支出出现回落，企业付费使用 AI 的覆盖范围仍然在扩张。因此，文章强调的是增长动能放缓，而不是 AI 需求整体萎缩。
这里需要区分两个容易混淆的指标：
- 采用率（Adoption Rate）：有多少被追踪的企业购买了某家公司的 AI 服务。
- Token 支出份额（Spending Share）：在被统计的 Token 支出总额里，某家公司占了多大比例。

例如，Anthropic 的企业采用率为 44.8%，Token 支出份额却高达 58.7%，这两个数字并不矛盾。
此外，同一家企业可能同时使用 Anthropic 和 OpenAI，因此两家公司的企业采用率不能直接相加，也不是互斥的市场份额。

### 6. Stripe 数据显示 AI 企业收入整体翻倍，但增长高度集中在少数头部公司
为了验证 AI 市场是否正在放缓，文章进一步引用支付处理公司 Stripe 发布的 Stripe AI Index。与 Ramp 主要观察企业为 AI 支付多少钱不同，Stripe 观察的是大约 20,000 家使用 Stripe 收款的 AI 公司所获得的付款，因而提供了供给端的另一种视角。数据显示，在截至 2026 年 11 月 8 日的 52 周里，AI 公司整体收入增长达到 103%，相当于总体规模比一年前扩大了一倍以上。然而，处于中位数位置的典型 AI 企业，收入增长率只有 41%，远低于整体增长水平。这种巨大差距说明，少数大型 AI 提供商对总体增长贡献非常大，行业看起来普遍高速增长，但普通 AI 公司的增长未必达到同样程度。
这一现象非常重要，因为媒体通常更容易报道行业整体增长率，而整体数据容易受到头部公司的影响。
假设一家行业中的大型公司收入规模远高于其他企业，那么即使大部分中小企业增长较慢，大公司的高速扩张也可能将行业总增长率拉得很高。
因此，评估 AI 创业环境，不能只看“AI 行业收入增长 103%”，还应该关注中位数企业的增长表现。
从本文数据来看，103% 代表行业整体增长，41% 更接近样本中一家典型 AI 公司的增长情况。但中位数也不能完整描述企业之间的差异，仍需要更多分布数据来判断不同规模公司的表现。

### 7. AI 企业短期增速从约 140% 回落到 80%，说明高速增长正在降温
Stripe 的短周期数据进一步强化了作者的判断。按照最近 13 周的增长表现进行年化计算，AI 企业的收入增长率约为 80%，而几个月前相同口径的年化增速还达到约 140%。这意味着短周期年化增长指标下降了约 60 个百分点，属于非常明显的减速。与此同时，AI 企业在过去 52 周里的整体同比增长仍达到 103%，显著高于 Stripe SaaS Index 中传统软件企业的 33%。也就是说，AI 仍然是一个增长速度明显高于传统软件行业的市场，但它自身的增长势头已不像前几个月那么强劲。
需要注意，13 周增长率年化与过去 52 周实际同比增长，使用的是不同的时间窗口和计算方法。
前者更适合捕捉近期趋势，后者则更适合描述过去一年的总体表现。
文章因此并没有因为短期增速回落，就断言 AI 行业陷入危机，而是指出：基数快速扩大以后，维持此前的爆发式增速正在变得更加困难。

### 8. AI 市场存在明显地区差异，美国增长最快，欧洲相对落后
Stripe 还按地区比较了 AI 企业的支付活动增长情况。在截至 2026 年 11 月 8 日的过去 52 周里，美国 AI 企业支付活动同比增长约 104%，是文章列出的地区中最高的。英国的增长率为 83%，其他地区合计为 76%，欧盟则为 67%，明显低于美国。美国与欧盟之间相差 37 个百分点，表明 AI 商业增长在不同市场之间并不均衡。对于 AI 创业公司和投资者而言，全球 AI 需求仍在增长，但不同地区的商业化速度、支付活跃度和市场环境可能存在明显差异。
不过，这些数字只反映 Stripe 所追踪的 AI 公司相关支付活动，不能直接代表各地区全部 AI 技术应用或经济贡献。
文章也没有具体分析欧洲为什么增长较慢，因此不能仅凭这组数字断言差异完全来自监管政策、资本投入或技术实力。
更稳妥的理解是：在 Stripe 的样本和统计口径下，美国的 AI 商业支付增长领先于其他地区。

### 9. AI 行业未来真正的挑战：能否创造足够收入，支撑巨额算力建设投资
文章最后把话题从短期 Token 价格变化，上升到整个 AI 行业的长期商业可持续性。作者认为，下一轮增长可能来自更强大、更可靠的模型，也可能来自将现有模型更深入地整合到企业工作流程中，让 AI 从辅助工具变成真正参与业务执行的生产力系统。文章特别提到，AI 已经在短短几个月内对整个编程市场产生巨大冲击，这说明一旦某个场景能够充分发挥模型能力，市场格局可能迅速改变。但另一方面，AI 行业正在规划规模庞大的算力基础设施建设，这些投资最终必须依靠持续的商业收入来回收。如果 Token 价格不断下降、收入增速持续放缓，而基础设施投入仍然快速扩大，AI 公司未来就可能面临商业收入增长与资本支出之间的压力。
这里存在一条非常重要的因果链：
模型竞争加剧 → Token 单价下降 → 企业使用成本降低 → AI 使用规模扩大 → 但单位使用量收入减少 → 供应商需要更大规模和更高价值的应用 → 才有可能支撑长期基础设施投资。
因此，AI 行业未来最核心的问题，不仅是谁能提供最多的 Token 或最便宜的 API。
更关键的是：谁能把 AI 能力转化成客户愿意持续付费的实际价值，并在持续降价的竞争环境中实现良好的单位经济效益。

## 关键事实与数据

### 一、Ramp：Token 使用量、支出和价格

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| Token 总支出变化 | -6.3% | 11 月 15 日当周相较两周前峰值 |
| Token 支出月度变化 | +12% | 11 月 15 日当周对比 10 月 18 日当周 |
| Token 使用量同期变化 | +27.2% | 同一比较周期 |
| Token 支出与使用量增速差 | 15.2 个百分点 | 使用量增长更快 |
| OpenAI 与 Anthropic 平均价格 | 0.45 美元/百万 Token | 11 月中旬 |
| 平均价格月度变化 | -11.2% | 较前一个月 |
| OpenAI 平均价格 | 0.38 美元/百万 Token | Ramp 统计 |
| Anthropic 平均价格 | 0.50 美元/百万 Token | Ramp 统计 |
| Anthropic 相对 OpenAI 价格 | 高约 31.6% | 按文中价格推算 |

补充说明：
- Token Spending（Token 支出）：企业实际支付给 AI API 服务的金额。
- Token Volume（Token 使用量）：企业消耗的 Token 数量。
- 两个指标必须结合分析，单独的 Token 使用量增长不能直接说明 API 收入增长。
- 本文提到中国 AI 厂商参与价格竞争，但没有列出具体中国公司名称。

### 二、OpenRouter：2026 年初至 11 月的 API 趋势

| 指标 | 数值或时间 |
| --- | --- |
| Token 周使用量增长 | +1,215% |
| Token 周支出增长 | +455% |
| Token 使用量相对年初倍数 | 约 13.15 倍 |
| Token 支出相对年初倍数 | 约 5.55 倍 |
| 推算平均每 Token 支出变化 | 约 -57.8% |
| Token 支出高点 | 2026 年 10 月 5 日当周 |
| 数据覆盖截止 | 2026 年 11 月 9 日当周 |
| 涉及公司 | OpenAI、Anthropic、Google |
| 模型范围 | 闭源权重模型（closed-weight models） |

数据来源及限制：
- 数据来自 API 路由平台 OpenRouter。
- Peter Walker 在 X 上发表了相关分析。
- OpenRouter 只覆盖通过其平台路由的 API 流量。
- 文章使用的图表不包含所有模型厂商，也不包含这些厂商在所有其他渠道上的使用。
- 因此，这组数据适合观察特定市场趋势，但不能直接外推为整个 AI 行业的总收入变化。

### 三、Ramp：2026 年 11 月企业 Token 市场份额
截至 2026 年 11 月 15 日当周；支出份额
Anthropic

58.7%

OpenAI

37.2%

xAI

2.4%

Google

1.4%

图示依据文章所给份额整理；Google 与 xAI 的数字按上下文归入支出份额，原文未逐项展开口径。其他重要数据：

| 公司 | Token 支出份额 | Token 使用量份额 |
| --- | --- | --- |
| Anthropic | 58.7% | 59.4% |
| OpenAI | 37.2% | 37.7% |

- Anthropic Token 支出份额较前一个月提高 1.7 个百分点。
- 2026 年 10 月，Anthropic 的 Token 支出环比增长 0.5%。
- 同期 OpenAI 的 Token 支出环比增长 2.1%。
- Anthropic 当前规模领先，但 OpenAI 在上述月份的支出增速更高。

### 四、Ramp：美国企业 AI 付费采用情况

| 指标 | 数值 |
| --- | --- |
| 2026 年 10 月，美国样本企业 AI 付费采用率 | 56.8% |
| 相比 2026 年 9 月 | +1 个百分点 |
| 相比 2025 年同期 | +13.3 个百分点 |
| Anthropic 企业采用率 | 44.8% |
| OpenAI 企业采用率 | 40.6% |

由此可推算，2025 年同期 Ramp 样本中的 AI 付费采用率约为 43.5%。
需要注意，这些数字来自 Ramp 追踪的美国企业，不代表全体美国企业的精确普及率。

### 五、Stripe：AI 公司收入增长

| 指标 | 数值 |
| --- | --- |
| 被追踪 AI 公司数量 | 约 20,000 家 |
| 52 周整体收入增长 | +103% |
| 中位数 AI 公司增长 | +41% |
| 最近 13 周年化增速 | 约 80% |
| 几个月前的 13 周年化增速 | 约 140% |
| 短周期年化增速下降 | 约 60 个百分点 |
| Stripe SaaS Index 增长 | +33% |
| Stripe AI Index 指数水平 | 2026 年超过 600 点 |

时间口径：52 周指标截至 2026 年 11 月 8 日。
Stripe AI Index 自 2022 年开始的图表显示 AI 企业收款规模持续提高，并在 2025 年开始明显加速。
需要注意，Stripe 的统计基于通过其支付系统完成的收款活动，不必然等同于企业财报确认收入，更不代表净利润。

### 六、Stripe：不同地区 AI 商业增长
AI 企业支付活动同比增长
截至 2026 年 11 月 8 日的过去 52 周，Stripe 样本，单位：%

要点：
- 美国增长最快，达到 104%。
- 英国为 83%，低于美国 21 个百分点。
- 其他地区合计为 76%。
- 欧盟为 67%，低于美国 37 个百分点。
- 地区差异说明不能将全球 AI 行业视为一个增长速度完全一致的市场。

### 七、重要人物、公司、平台和概念

| 名称 | 在文章中的角色 |
| --- | --- |
| Ramp | 提供企业 AI 采购与 API 支出数据 |
| Ramp AI Index | 衡量企业 AI 支出、采用率及 Token 相关指标 |
| Stripe | 支付处理公司，提供 AI 企业收款数据 |
| Stripe AI Index | 追踪通过 Stripe 收款的 AI 企业支付活动 |
| Stripe SaaS Index | 用于与传统软件行业增长速度进行比较 |
| OpenRouter | API 路由平台，提供特定模型的 Token 流量和支出数据 |
| OpenAI | 主要 AI 模型服务供应商 |
| Anthropic | 在 Ramp 样本中占据领先 Token 支出份额 |
| Google | OpenRouter 所分析的主要模型供应商之一 |
| xAI（SpaceXAI） | Ramp 市场份额比较中出现的供应商 |
| Peter Walker | 在 X 上发布 OpenRouter 数据分析的人 |
| Kharazian | 在 X 上评论 Anthropic 市场份额的人 |
| Chinese providers（中国供应商） | 参与 AI API 价格竞争的厂商群体 |

## 金句摘录

### 1. AI 使用量与收入正在脱钩
"The gap between usage and revenue keeps widening."

中文翻译： 使用量与收入之间的差距正在不断扩大。
值得记住的原因： 这是全文最重要的商业信号。AI 使用量可能呈爆炸式增长，但服务商的变现能力不一定同步提高。

### 2. 不同数据来源共同验证降温趋势
"The fact that both sources show a spending peak in October followed by declining outlays and rising volume reinforces the trend, though neither service is representative of the overall market."

中文翻译： 两个数据来源都显示，支出在 10 月达到峰值，随后支出下降、使用量上升，这强化了趋势判断；不过，两者都不能代表整个市场。
值得记住的原因： 多个来源出现相似趋势，会提高观察的可信度，但数据样本的覆盖范围仍然决定了结论能够推广到什么程度。

### 3. 头部公司拉高了整个行业的增长率
"The typical (median) AI company grew only 41 percent, though, suggesting that a few large providers are skewing the overall picture."

中文翻译： 然而，一家典型的（中位数）AI 公司仅增长了 41%，这表明少数大型服务商正在显著影响行业整体表现。
值得记住的原因： 行业整体增长率可能掩盖公司之间的巨大差异，不能直接当作普通企业的发展水平。

### 4. 全文最核心的结论
"AI is still growing fast, but momentum is cooling."

中文翻译： AI 仍在快速增长，但增长势头正在降温。
值得记住的原因： 增速下降不等于行业衰退。评价一个行业时，必须区分增长速度、增长加速度和规模是否真正下降。

### 5. AI 下一阶段增长的主要来源
"New growth could emerge from more capable or more reliable models, or simply from better integration of current models into business workflows."

中文翻译： 新一轮增长可能来自能力更强、可靠性更高的模型，也可能仅仅来自把现有模型更好地整合进企业工作流程。
值得记住的原因： AI 商业化未必只能等待下一代模型突破，把已有模型真正用进业务流程，同样可能创造新的增长空间。

### 6. AI 基础设施投资必须靠收入回收
"The AI industry still depends on extraordinarily strong growth, though, if it wants to recoup the massive capacity buildout it has planned."

中文翻译： 不过，如果 AI 行业想收回其规划中的庞大算力基础设施建设投资，就仍然必须依靠极其强劲的增长。
值得记住的原因： 这是全文最重要的长期风险提示。AI 的技术前景和 AI 公司的投资回报，是两个需要分别评估的问题。

## 值得记住的点 / 行动建议
原文主要是行业数据分析，而非具体操作教程。以下建议是在保留作者判断的基础上，进一步推导出的可执行做法。

### 1. 分析 AI 行业时，必须把使用量、价格、收入三个指标分开
很多人判断 AI 行业是否繁荣，会先看 API 请求量、Token 消耗量或用户数量。
但本文最重要的教训是：使用量快速增加，并不必然带来同等比例的收入增长。
建议建立一套至少包含三个指标的观察框架：
- 使用量：Token 消耗量、API 请求量、活跃客户数是否增长？
- 单位价格：每百万 Token 的实际收入是否降低？
- 总收入：企业真实收入是否以足够快的速度增长？

在分析 AI 模型供应商时，还应进一步加入推理成本和毛利率。
例如，当 Token 使用量增长 27.2%、支出只增长 12% 时，就需要判断价格下降带来的使用量扩张，能否弥补单位收入的下降。
这比简单地说“AI 使用量又创新高了”更能反映商业现实。

### 2. 不要只看 AI 行业平均增速，还要看中位数和头部集中度
Stripe 的数据提供了一个非常有用的分析方法：
行业整体增长 103%，但中位数企业只增长 41%。
这意味着评价 AI 行业时，不能把行业总体数字当作每家 AI 公司的真实表现。
如果正在分析 AI 创业机会、投资标的或行业竞争，建议同时关注：
- 行业总体收入增长率。
- 中位数企业的收入增长率。
- 头部企业占据多少收入与客户支出。
- 中小企业是否拥有持续增长的客户群。
- 增长是否主要依赖少数大型客户或少数领先产品。

这些指标能帮助区分“行业整体扩张”和“普通公司同样容易成功”这两个完全不同的命题。

### 3. 做 AI 产品，不要只依赖模型调用量，应该尽量建立价值导向的收入模式
如果一家 AI 应用公司主要依靠转售 API、包装基础模型能力，或者按 Token 消耗量收取固定比例的费用，那么上游价格持续下降可能对它形成压力。
本文显示，OpenAI、Anthropic 和中国模型供应商之间的价格竞争，已经使 Token 单价持续降低。
对 AI 创业者而言，更值得思考的是如何提供客户愿意长期付费、而且不能轻易用基础模型直接替代的服务。
可以从三个方向寻找机会：
**1. 深入具体工作场景：例如合同审核、客服工单处理、销售线索筛选、软件测试和企业知识检索。**
**2. 提供完整业务结果：不仅回答问题，还完成信息整理、系统操作、结果验证和任务交付。**
**3. 围绕交付价值定价：除了按 Token 或调用次数收费，还可以探索按完成任务、席位、工作流或可衡量的业务成果收费。**

这些属于从原文价格竞争趋势推导出的产品策略，不代表所有 AI 企业都必须采用同一种收费模式。
真正的目标是把收入与客户得到的价值建立更稳定的联系，而不是完全依赖底层 Token 的价格。

### 4. 企业引入 AI 时，应优先评估工作流整合效果，而不是一味追求最新模型
文章结尾明确提出，AI 下一轮增长未必只能依靠更强大的模型。
现有模型如果能够更可靠地进入企业工作流程，同样可能产生巨大的商业价值。
对于准备部署 AI 的企业，建议优先选择一个业务流程，做完整的投入产出评估。
具体可以这样实施：
- 选定重复性高、数据相对规范、结果可验证的工作。
- 记录人工处理的时间、成本和错误率。
- 将 AI 接入现有系统，而非只提供独立聊天窗口。
- 建立必要的人工复核和异常处理机制。
- 比较部署前后的单位任务成本、完成时间和质量。
- 确认收益后再扩大使用范围。

例如，在软件开发中，真正有价值的不只是让 AI 生成更多代码，而是提高从需求分析、代码编写到测试和交付的整体效率。
企业应该购买的是可验证的生产力提升，而不仅仅是更多 Token。

### 5. 选择 AI 模型时，价格很重要，但不能只比较每百万 Token 报价
Ramp 数据显示，OpenAI 的平均 Token 价格低于 Anthropic。
但对具体企业而言，价格低不一定意味着完成任务的总成本更低。
如果一个更便宜的模型需要更多轮调用，或者错误率较高、需要额外人工审核，最终成本可能反而更高。
建议在同一类真实任务上，同时比较：
- 单次任务的总 Token 成本。
- 一次性完成任务的成功率。
- 工具调用与复杂工作流的稳定性。
- 输出质量及人工返工成本。
- 延迟、吞吐量和运行可靠性。

最终应该采用 Cost per Successful Task（每个成功任务的成本） 之类的综合指标，而不仅仅是单纯比较 API 价格。
这也是在模型价格持续下降的市场中，企业更容易做出合理采购决定的方法。

### 6. 投资 AI 公司时，要把收入增长与基础设施资本支出放在一起分析
文章最后指出，AI 行业仍然依赖异常强劲的增长，才能收回已经规划的庞大基础设施投资。
因此，评估一家 AI 公司时，不能仅因为收入同比增长 100%，就认为商业模式一定健康。
需要同时观察：
- 收入增长速度是否高于预期？
- 增速是否持续下降？
- Token 单位收入和单位成本如何变化？
- GPU、数据中心、能源等基础设施投入是否持续增加？
- 毛利率是否能够随着规模扩大而改善？
- 新增资本支出是否有足够的未来现金流支撑？

尤其要区分三个不同的概念：收入高速增长、利润持续增长、资本投入能够获得合理回报。
三者有联系，但并不等价。
本文没有提供具体 AI 公司的资本支出、利润或现金流数据，所以只能指出潜在的投资回收压力，不能据此直接判断某家公司会出现财务危机。

### 7. 判断 AI 是否进入“泡沫破裂”，不能只凭短期增速下降
Stripe 的 13 周年化增长率从约 140% 降到 80%，乍看之下是一个很大的下滑。
但这里下降的是增长率，而不是已经确认的收入规模。
如果一家企业去年收入为 100，今年增长 80%，那么收入依然达到 180，只是没有之前增长得那么快。
因此，分析行业周期时，至少需要区分：
- 增长率下降：收入还在增长，只是速度减慢。
- 增长停滞：收入不再明显增加。
- 负增长：收入规模开始下降。
- 盈利能力恶化：收入可能增长，但成本和投入上升更快。

本文真正提供的证据，主要支持第一种情况：AI 行业整体仍在增长，但增长动能减弱。
同时，Ramp 与 OpenRouter 的部分 Token 支出数据已经出现从峰值回落的迹象，值得继续观察，但尚不足以证明整个 AI 行业正在全面收缩。

### 8. 应持续观察企业付费采用率，而不只是单个模型的市场份额
Ramp 数据显示，美国样本企业的 AI 付费采用率已经达到 56.8%，而且较一年前提高 13.3 个百分点。
这表明行业存在一个重要的长期驱动力：越来越多企业正在从尝试 AI 转向实际为 AI 付费。
如果企业付费采用率持续上升，即便 Token 单价下跌，行业仍可能通过客户扩张和更深入的使用获得新的收入。
因此，观察 AI 商业化时，建议每隔一个季度检查企业付费采用率、客户留存、每客户支出和不同供应商的市场份额。
尤其值得关注的是：企业是否只是购买了 AI 产品，还是已经将 AI 纳入不可轻易取消的核心工作流程。
真正稳定的 AI 商业需求，不只是企业尝试购买，而是企业持续使用并持续获得价值。

### 9. 关注 AI 下一轮真正能创造增量需求的应用场景
作者提到 AI 对编程市场的迅速影响，是为了说明技术能力一旦与具体行业需求结合，可能在很短时间内形成重大变化。
这意味着未来 AI 增长的突破口不一定来自更多通用聊天机器人。
更可能的机会，是那些 AI 能明显提高生产效率、降低成本或完成过去无法经济化实现的任务的领域。
可以优先观察：
- AI 编程和软件工程自动化。
- 企业内部知识与流程自动化。
- 客服和业务运营自动化。
- 需要高可靠性推理的专业任务。
- 跨多个系统执行任务的 AI Agent（AI 智能体）。

这些是根据原文提出的“模型能力提升”和“工作流整合”两条增长路径延伸出的观察方向，并非文章已经验证了它们各自的市场规模或盈利前景。
最重要的筛选标准是：技术能力是否真正转化成客户愿意长期支付的业务价值。

## 我的点评
文章最有价值的地方，是同时使用 Ramp、OpenRouter 和 Stripe 的数据，从企业支出、Token 使用和供应商收款等不同维度观察 AI 行业，避免了只凭某一家公司的增长数字判断整个市场。其“使用量与收入脱钩”的判断尤其值得重视，因为 AI 模型价格下降可能让技术应用更加普及，却不一定让底层模型服务商获得同比例的收入。需要保留的是，Ramp、OpenRouter 和 Stripe 都有各自的样本偏差，而且文章没有提供足够的成本、利润和资本支出数据，因此不能直接从收入增速放缓推断行业整体盈利能力或投资回报正在恶化。另一个值得注意的问题是，文章既使用单周变化、月度对比，也使用 13 周年化与 52 周同比，阅读时必须区分口径，避免把不同时间尺度的数据混为一谈。对普通读者、AI 从业者和投资者来说，最有用的启发是：不要把 AI 技术的普及速度、AI 公司的收入增长和 AI 投资的盈利前景视为同一件事；真正决定长期价值的，是技术能否持续解决现实问题，并形成可持续的商业回报。

---

## 📝 完整文字稿

Token spending, meaning what companies actually pay for AI APIs, fell 6.3 percent from its peak two weeks earlier. Month over month (the week ending November 15 vs. the week ending October 18), total token spending still rose 12 percent, but token volume jumped 27.2 percent over the same span. The gap between usage and revenue keeps widening.

The average price per million tokens for OpenAI and Anthropic combined fell to $0.45, according to Ramp, down 11.2 percent from the prior month. OpenAI is cheaper at $0.38 per million tokens compared with $0.50 for Anthropic.

The price war between OpenAI, Anthropic and Chinese providers is having an effect: tokens keep getting cheaper. In mid-November, the average price per million tokens sits at $0.45, with OpenAI at $0.38 and Anthropic at $0.50. | Image: Ramp AI Index

API routing platform OpenRouter shows a similar pattern. According to an analysis Peter Walker published on X, weekly token volume for closed-weight models from OpenAI, Anthropic and Google grew 1,215 percent since the start of 2026. Weekly spending rose 455 percent over the same period, far more slowly. The spending peak came in the week of October 5, according to the OpenRouter data, which runs through the week of November 9. Spending has been declining since then.

On OpenRouter, weekly token volume rose 1,215 percent since early 2026, while weekly spending grew 455 percent. Spending has fallen since its early-October peak. The chart covers only closed-weight models from OpenAI, Google and Anthropic. | Image: OpenRouter

Ramp's token metrics rely on usage and billing data imported from AI providers, while OpenRouter measures traffic through its API routing platform. The fact that both sources show a spending peak in October followed by declining outlays and rising volume reinforces the trend, though neither service is representative of the overall market. OpenRouter in particular offers only a narrow window into a very specific user base.

### Anthropic dominates the token market on IPO day

In the week ending November 15, 2026, Anthropic accounted for 58.7 percent of all token spending, according to the Ramp AI Index, up 1.7 percentage points from the prior month. Its share of token volume was even higher at 59.4 percent. OpenAI fell to 37.2 percent of spending and 37.7 percent of volume. Google came in at 1.4 percent and xAI (SpaceXAI) at 2.4 percent.

Kharazian wrote on X that Anthropic holds this share on IPO day. In October, however, Anthropic's token spending grew only 0.5 percent month over month, while OpenAI's grew 2.1 percent.

In October 2026, 56.8 percent of all tracked US companies paid for AI products or services, according to Ramp, up one percentage point from September and 13.3 percentage points more than a year earlier. Anthropic leads with an adoption rate of 44.8 percent, while OpenAI sits at 40.6 percent.

### Stripe data also shows strong AI growth and signs of cooling

The Ramp AI Index tracks the demand side, what companies spend on AI. Payment processor Stripe has published its own AI Index that measures the supply side: incoming payments at roughly 20,000 AI companies that use Stripe.

The Stripe AI Index shows rising incoming payments for AI companies since 2022. The increase steepens starting in 2025, and the index crosses 600 points in 2026. | Image: Stripe

According to the Stripe AI Index, revenue at AI companies grew 103 percent over the 52 weeks ending November 8. The typical (median) AI company grew only 41 percent, though, suggesting that a few large providers are skewing the overall picture.

The slowdown over shorter time frames is pronounced. Annualized over 13 weeks, growth stood at about 80 percent, down from 140 percent just a few months ago. The US leads with 104 percent year-over-year growth, while the EU sits at 67 percent. AI companies are growing far faster than traditional software firms, according to Stripe: 103 percent compared with 33 percent in the SaaS Index.

Payment activity among tracked AI companies rose about 104 percent in the US over the 52 weeks ending November 8, 2026. The UK followed at 83 percent, the rest of the world at 76 percent and the EU at 67 percent growth. | Image: Stripe

Both indexes paint a similar picture. AI is still growing fast, but momentum is cooling. At Ramp, that shows up through falling prices and concentrated demand. At Stripe, it shows up through slowing growth rates on the provider side.

New growth could emerge from more capable or more reliable models, or simply from better integration of current models into business workflows. The potential is there, considering how AI has upended the entire coding market in a matter of months. The AI industry still depends on extraordinarily strong growth, though, if it wants to recoup the massive capacity buildout it has planned.
