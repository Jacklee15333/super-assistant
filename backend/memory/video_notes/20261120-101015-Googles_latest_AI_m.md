# 谷歌最新 AI 模型比几周前发布的旗舰前代更快、更便宜、更智能

- 来源链接：https://the-decoder.com/googles-latest-ai-model-is-faster-cheaper-and-smarter-than-its-flagship-predecessor-from-just-weeks-ago/
- 作者：Maximilian Schreiner
- 提取时间：2026-11-20 10:10
- 类型：网页文章
- 发布时间：2026-11-19 11:18
- 原标题：Google's latest AI model is faster, cheaper and smarter than its flagship predecessor from just weeks ago
- 标签：模型迭代、性能评测、Token成本、编程智能体、多模态能力

## 🤖 AI 分析

## 一句话概括
Google DeepMind（谷歌 DeepMind 团队）在短短七周内推出第四款 AI 模型 Gemini 4 Neon，凭借接近翻倍的生成速度、更低的标准定价、更强的编程智能体和视觉处理能力，在多项测试中超越此前的旗舰模型 Gemini 4 Carbon，但评测也揭示出一个重要事实：Neon 的成本优势主要来自更低的 Token 单价，而不是更高的 Token 使用效率，并且其优势会随推理档位、应用场景和促销价格而变化。

## 背景与主题
Google DeepMind 在七周内连续发布四款 AI 模型，最新推出的 Gemini 4 Neon 被定位于 Gemini 4 Hydrogen 和 Gemini 4 Carbon 之间，却在绝大多数基准测试中超越了定位更高的 Carbon，体现出谷歌极快的模型迭代速度。
根据第三方评测机构 Artificial Analysis（人工智能分析机构）的数据，Neon 在最高推理档位下以 61 分的智能指数位列全球第三，仅次于 OpenAI 的 GPT-6.2 Astra 和 Anthropic 的 Claude Fable 5.2，同时具有明显的速度和标准价格优势。
文章重点分析了 Neon 的智能水平、Token 定价、单任务成本、代码智能体能力、文档与视觉处理、自动化、科研推理以及网络安全表现，并将其与 Carbon 及竞争对手的模型进行对比。
作者整体肯定谷歌的产品迭代速度和 Neon 的综合竞争力，但也对谷歌官方选择性展示竞争对手、Neon 的 Token 消耗效率以及不同推理档位下的异常表现提出了值得关注的细节。

## 核心观点

### 1. 谷歌七周发布四款模型，AI 竞争已进入极高频率的产品迭代阶段
Google DeepMind 在短短七周内接连推出四款 AI 模型，Gemini 4 Neon 是其中最新的一款，这意味着谷歌正在以非常高的频率更新其模型产品线。按照谷歌的官方定位，Neon 处于 Hydrogen 和 Carbon 之间，并非简单地作为最顶级旗舰推出，但实际测试结果显示，它在几乎所有基准测试中都能击败 Carbon。**这意味着模型的产品档位、发布时间和实际能力之间，已经不再存在简单的一一对应关系。**几周前刚刚处于旗舰位置的模型，可能很快就被新发布、定位更低、成本也更低的产品超越。文章最后强调，谷歌仍在以惊人的速度推出模型，这种持续迭代正在重塑 AI 模型之间的竞争方式。
Neon 还提供高达 100 万 Token 的上下文窗口（Context Window），支持文本、图像、音频和视频等多种模态。大上下文窗口意味着它在设计上能够处理更长的文档、更多的代码和更复杂的多模态输入，而不仅限于普通的文字问答。不过，100 万 Token 是上下文容量上限，并不代表模型在所有超长输入任务中都能保持完全一致的理解质量。文章所展示的竞争重点，已经从单纯的模型参数或能力排名，转向了模型能力、速度、成本和应用场景的综合比较。

### 2. Neon 的综合智能水平超越 Carbon，但全球排名第三，而不是第一
根据 Artificial Analysis Index（Artificial Analysis 综合智能评测指数），Gemini 4 Neon 在最高推理档位 xhigh（超高推理强度） 下获得了 61 分，而前代 Gemini 4 Carbon 为 60 分。虽然两者仅相差 1 分，但 Neon 因此在该指数中超过了 Carbon，排名升至全球第三。排在 Neon 前面的分别是 OpenAI 的 GPT-6.2 Astra 和 Anthropic 的 Claude Fable 5.2，说明 Neon 虽然进入第一梯队，却并没有拿下整体智能评测的第一名。值得注意的是，谷歌官方发布的对比表没有纳入这两个排名领先的模型，而是选择将 Neon 与 Claude Opus 5.5 和 GPT-6.2 Sol 进行比较。作者特意指出这一点，实际上是在提醒读者：厂商展示的评测对手，不一定覆盖市场上最强的竞争产品。
这一细节非常重要，因为 AI 公司经常通过精心选择的基准测试、比较对象和推理配置来展示自家模型的优势。单看谷歌官方比较表，读者可能会觉得 Neon 已经全面领先主要竞争对手，但引入第三方榜单后，才能看到它在整体市场中的相对位置。因此，文章虽然肯定 Neon 的进步，却没有直接将它定义为最聪明的 AI 模型，而是强调它在智能、速度与价格之间形成了很强的综合竞争力。

### 3. Neon 的成本优势主要来自 Token 降价，而非模型本身更省 Token
Gemini 4 Neon 通过 Google AI Studio（谷歌 AI 开发平台）和 Gemini for Business（Gemini 企业服务）提供的标准价格为：每 100 万输入 Token 收费 3 美元，每 100 万输出 Token 收费 15 美元；如果输入内容命中缓存，输入价格可以降至每 100 万 Token 0.15 美元。相比 Carbon 的标准输入价格 4 美元、输出价格 20 美元，Neon 的输入和输出单价均降低了 25%。然而，Artificial Analysis 的测试发现，在 xhigh 档位下，Neon 完成同一类评测任务平均会消耗比 Carbon 多约 15% 的输出 Token。因此，Neon 并不是因为输出更简短、需要生成的 Token 更少而降低了成本，而是依靠更低的 Token 单价，使单任务费用从 Carbon 的 7.76 美元下降至 6.44 美元，降幅约为 17%。
这揭示了一个很容易被忽视的区别：**Token 单价降低，不等于模型处理同样任务时的 Token 消耗效率提高。**假如一个模型每个 Token 更便宜，却需要生成更多 Token 才能完成任务，那么最终节省下来的费用就会小于表面上的单价降幅。文章还指出，Carbon 在 11 月底之前仍然享有促销价格，而 Neon 的标准价格反而比 Carbon 的促销价高出 50%。所以，如果企业正在选择模型，不能只比较官方标准价，还要结合当期优惠、任务消耗量和实际完成成本进行判断。

### 4. Neon 接近翻倍的生成速度，可能比小幅智能分数提升更具实际价值
相比 Carbon，Neon 一个非常突出的优势是生成速度：Artificial Analysis 测得 Neon 每秒可以生成大约 110 个 Token，而 Carbon 只有约 57 个 Token，Neon 的输出速度接近 Carbon 的两倍。在文章所引用的基准测试中，整体处理时间从 Carbon 的约 36 分钟下降到 Neon 的约 21 分钟，缩短了约 15 分钟。这相当于测试处理耗时减少约 42%，说明更快的 Token 生成速度能明显改善实际任务执行时间。对于普通聊天而言，这可能表现为回答更迅速；对于软件开发智能体、长篇报告生成、复杂分析和批量自动化任务而言，节省的时间可能具有更高的业务价值。特别是在模型连续调用工具、反复修复错误、生成大量代码的场景中，速度优势可能不断累积。
文章还指出，在次高推理档位 high（高推理强度） 下，Neon 可以达到与 Carbon 相同的智能评分，同时使每项任务的成本降低约一半。这个结果比 xhigh 档位下仅高出 Carbon 1 分的智能指数更值得实际用户关注，因为它说明 Neon 可能无需调用最高计算强度，就能取得与 Carbon 相当的效果。如果能够用较低成本和更短时间完成同等质量的任务，模型的实际生产价值就会显著提高。

### 5. 编程智能体是 Neon 最有竞争力的领域之一，能力更强且成本接近主要对手的一半
在 Coding Agent Index（代码智能体评测指数）中，通过 Google Antigravity（谷歌智能体开发环境）运行的 Neon，在 xhigh 档位下获得了 59 分，超过 Carbon 的 55 分，也超过 Claude Fable 5.2 和 Claude Opus 5.5 各自的 58 分。这说明 Neon 不只是能够生成代码片段，在特定智能体环境中完成复杂编程任务的综合能力也很有竞争力。更重要的是，每个平均编程任务使用 Neon 的费用仅为 6.86 美元，而 Claude Opus 5.5 为 12.61 美元，Claude Fable 5.2 则达到 15.47 美元。以这些测试数据计算，Neon 相比 Opus 节省约 46% 的费用，相比 Fable 节省约 56%，形成了明显的性价比优势。对需要大量运行代码生成、调试、测试和修复任务的开发团队来说，这种单任务成本差异可能被大规模调用进一步放大。
谷歌还声称，在 SWE-sweep（软件工程任务测试） 中，使用 Antigravity 环境可以将 Neon 的命中率提高到原来的三倍，达到 39.0%。这一结果说明，AI 编程任务的最终成功率不仅取决于模型本身，还与模型所在的智能体环境密切相关。工具调用方式、任务执行流程、代码测试反馈、上下文组织等因素，都可能影响最终效果。不过，文章只给出了谷歌声称的三倍提升及最终命中率，并没有完整介绍测试任务组成或环境配置，因此不应将该结论直接推广到所有编程场景。

### 6. Neon 在文档理解和演示文稿质量上进步明显，但最高推理档位不一定表现最好
在视觉处理和文档理解方面，Artificial Analysis 测得 Neon 有明显进步。在名为 GDP.pdf 的文档处理测试中，Neon 使用 high 档位时取得 33.4% 的得分，位居该项测试第一，比 Carbon 高出约 5 个百分点。然而，一个非常有意思的现象是，当 Neon 切换到计算强度更高的 xhigh 档位后，该测试得分反而下降到了 28.0%。这说明更高的推理预算并不保证所有任务都会得到更好的结果，尤其是在涉及文档结构、图表识别、视觉信息提取等不同能力组合的任务中。
另一项重要测试是 AA-Briefcase（演示文稿质量评测），Neon 获得了 1771 Elo 的评分，在演示文稿质量方面取得领先，并超过 Claude Opus 5.5。Elo 是一种用于衡量相对表现的评分体系，因此 1771 反映的是该测试中的竞争表现，并不能直接理解为绝对正确率或质量百分比。对于经常需要分析 PDF、整理报告、理解多模态材料、生成演示文稿的用户，这些结果表明 Neon 可能是一个值得重点测试的模型。与此同时，high 超过 xhigh 的反常结果，也提醒使用者应当根据任务类别选择推理配置，而不是机械地认为档位越高越好。

### 7. 自动化与科学推理能力表现突出，Neon 不只是一个更便宜的通用聊天模型
在谷歌自己的评测中，Neon 还在多种专业任务中取得了很强的成绩，包括 Vals Index（Vals 评测指数） 中的个别类别、Zapier 的 AutomationBench（自动化任务基准测试），以及科学类测试 RiemannBench（黎曼数学相关基准测试）。其中，Neon 在 AutomationBench 上获得了 56.3% 的成绩，在 RiemannBench 上取得了 84.0% 的成绩。这些结果表明，谷歌并不只是希望 Neon 成为一个聊天、写作和搜索辅助模型，还希望它在自动化工作流与复杂科学问题上具有竞争力。尤其是 Zapier 所代表的自动化生态，其核心场景往往涉及连接不同应用、执行跨系统任务，以及根据任务结果完成后续操作。
这类能力的商业意义在于：AI 的价值可能从单次文本生成逐步转移到复杂工作流程的完成能力。模型如果可以更好地理解任务、生成合适的操作步骤，并在工具环境中完成任务，就可能减少人工在重复性操作上的投入。但需要注意，文章只提供了测试分数，没有详细解释每项基准的评分机制、样本规模和错误类型。因此，这些成绩能够说明 Neon 在相应测试中表现较强，却不能直接证明它已经能够稳定地自动执行各种真实业务流程。

### 8. 谷歌开始推出网络安全专用模型，但基准测试高分不等于现实环境中的全面安全
除了通用版 Neon，谷歌还计划通过 Fairwind Program（Fairwind 计划） 推出面向网络安全专业人士的专用变体。根据谷歌的数据，该版本在 SEC-bench Pro（网络安全能力测试） 中取得 90.5% 的成绩，在 WebExploitBench v1.2（Web 漏洞利用能力测试） 中取得 51.26% 的成绩，并声称以竞争模型约一半的价格达到领先表现。这里体现了一个重要趋势：模型厂商不仅在竞争通用智能，也开始针对安全、编程、科研等专业领域推出优化版本。对于网络安全团队来说，如果专业模型能够以较低成本完成漏洞研究、风险分析和辅助验证等任务，就可能带来更好的投入产出比。
文章还提到，Neon 的 Model Card（模型说明卡）虽然非常简短，但其中声称模型在 Gray-Swan（Gray Swan 安全评测） 的间接提示词注入测试中，能够阻止 100% 的攻击。所谓间接提示词注入（Indirect Prompt Injection），通常是指攻击者把恶意指令放入模型读取的外部资料或工具返回内容中，试图诱导模型偏离原本的任务。这种攻击与 AI 智能体的实际应用安全密切相关，因此该指标具有重要意义。但 100% 仅表示它在所报告的特定测试中实现了全部拦截，不能推断模型在所有真实环境下都绝对安全。

### 9. 评价 AI 模型必须综合能力、成本、速度和运行环境，而不是只看排行榜
这篇文章最深层的结论并不是“Neon 是最强模型”，而是新一代 AI 模型竞争已经高度多维化。Neon 的整体智能得分只是比 Carbon 高 1 分，但其生成速度接近翻倍，并且在编程任务、视觉处理及多项专业测试中取得更明显的优势。与此同时，Neon 的单任务成本虽然下降，但 Token 消耗反而增加，而且 Carbon 的促销价格还可能在短期内改变价格比较的结论。再加上不同推理档位可能出现高档位不如低档位的情况、智能体环境可能使任务成功率明显提升，单独比较模型名字或排行榜分数显然不够。
真正有价值的模型比较，应该建立在相同任务、相同质量要求、相近运行环境和可比较的价格条件之上。对于企业，最终需要关注的是每个成功任务的综合成本，而不是仅仅关注每百万 Token 的报价。对于开发者，应重点测试模型在真实代码库和实际工具链中的表现，而不是直接将公开榜单成绩等同于自己的项目结果。对于一般用户，则应关注模型在自己最常做的任务中是否更快、更好、更稳定，以及是否值得为更高档位支付额外成本。

## 关键事实与数据
以下数据均来自文章原文，包括第三方 Artificial Analysis 的评测结果和谷歌官方披露的数据；不同测试来源不应视为完全相同条件下的直接比较。

### 1. 模型发布与定位

| 项目 | 具体信息 |
| --- | --- |
| 发布公司 | Google DeepMind |
| 最新模型 | Gemini 4 Neon |
| 发布节奏 | 7 周内发布第 4 款 AI 模型 |
| 同系列参照模型 | Gemini 4 Hydrogen、Gemini 4 Carbon |
| 官方产品定位 | Neon 位于 Hydrogen 与 Carbon 之间 |
| 上下文窗口 | 100 万 Token |
| 支持的输入模态 | 文本、图像、音频、视频 |
| 主要服务渠道 | Google AI Studio、Gemini for Business |
| 最高推理档位 | xhigh |
| 次高推理档位 | high |

### 2. 综合智能评测与排名

| 模型 | Intelligence Index（智能指数） | 文章中所述地位 |
| --- | --- | --- |
| GPT-6.2 Astra | 未提供 | 排在 Neon 之前 |
| Claude Fable 5.2 | 未提供 | 排在 Neon 之前 |
| Gemini 4 Neon（xhigh） | 61 分 | 第 3 名 |
| Gemini 4 Carbon（xhigh） | 60 分 | 落后 Neon 1 分 |

- 第三方评测机构：Artificial Analysis。
- Google 官方比较对象：Claude Opus 5.5、GPT-6.2 Sol。
- 官方比较表未纳入的领先模型：GPT-6.2 Astra、Claude Fable 5.2。
- Neon 的综合智能得分较 Carbon 提高 1 分，不能简单等同于所有任务能力都有相同比例的提升。

### 3. API Token 标准定价
单位：美元 / 100 万 Token

| 价格项目 | Gemini 4 Neon | Gemini 4 Carbon |
| --- | --- | --- |
| 输入 Token | $3.00 | $4.00 |
| 缓存命中的输入 Token | $0.15 | 原文未提供 |
| 输出 Token | $15.00 | $20.00 |
| 标准单价降幅 | 比 Carbon 低 25% | 基准 |
| 与 Carbon 促销价比较 | Neon 标准价高 50% | 促销至 11 月底 |

这里最容易误读的是价格对比：Neon 的输入和输出标准单价确实均比 Carbon 低 25%，但如果按 Carbon 的优惠价格计算，Neon 反而更贵。
原文没有给出 Carbon 的具体促销价格数字，也没有说明促销期之后是否还存在新的优惠安排。

### 4. 综合任务成本与生成速度
Neon xhigh 单任务成本

# $6.44
Carbon 为 $7.76，降低约 17%

Neon 生成速度

# 110
Token/秒，Carbon 约为 57

测试处理时间

# 21 分钟
Carbon 约 36 分钟

每任务输出 Token 消耗

# +15%
Neon 相比 Carbon 反而更多

文章中的关键因果关系是：
- Token 单价下降 25%。
- 同类评测任务的输出 Token 消耗增加约 15%。
- 两个因素相互抵消一部分，最终使 xhigh 档位的单任务费用降低约 17%。
- 生成速度从 57 Token/秒提升至约 110 Token/秒。
- 对应基准测试处理时间从约 36 分钟降至约 21 分钟。
- high 档位能够与 Carbon 的智能评分持平，同时将任务成本降低约一半。

需要特别区分：生成速度接近翻倍，不等于整个任务耗时直接减半，因为完整任务还可能涉及思考、工具调用和其他非输出阶段。

### 5. 编程智能体能力与成本
Coding Agent Index：代码智能体评分

文章所引的 Coding Agent Index；Neon 使用 Antigravity 环境。

平均编程任务成本（美元）

成本越低越好；不同模型的价格来自文章引用的评测。

另外，谷歌披露的 SWE-sweep 测试数据包括：
- 测试环境：Google Antigravity。
- 测试对象：Gemini 4 Neon。
- 优化结果：命中率提高至原来的 3 倍。
- 最终命中率：39.0%。
- 文章没有披露足够信息来单独量化模型能力和环境优化对该结果的贡献。

### 6. 文档理解与演示文稿评测

| 基准测试 | 模型及档位 | 结果 |
| --- | --- | --- |
| GDP.pdf | Neon high | 33.4%，该测试领先 |
| GDP.pdf | Neon xhigh | 28.0% |
| GDP.pdf | Carbon | 比 Neon high 低约 5 个百分点 |
| AA-Briefcase | Neon | 1771 Elo，演示文稿质量领先 |
| AA-Briefcase | Claude Opus 5.5 | 排名低于 Neon，未提供具体 Elo |

最值得记录的反常数据：GDP.pdf 测试中，Neon 的 xhigh 档位比 high 档位低 5.4 个百分点。这不是可以忽略的微小差异，说明在该测试上提高推理强度没有带来正向效果。

### 7. 自动化、科学与安全领域

| 基准测试 / 项目 | 具体表现 | 数据来源 |
| --- | --- | --- |
| Vals Index | 在部分单项类别中领先 | Google |
| Zapier AutomationBench | 56.3% | Google |
| RiemannBench | 84.0% | Google |
| SEC-bench Pro | 90.5% | Google，网络安全变体 |
| WebExploitBench v1.2 | 51.26% | Google，网络安全变体 |
| Gray-Swan 间接提示词注入测试 | 阻止 100% 的测试攻击 | Neon Model Card |

其他值得保留的细节：
- Fairwind Program：谷歌用于推出网络安全专用 Neon 变体的项目。
- 网络安全专用版本：文章声称其价格约为竞争模型的一半，并在所列安全测试中达到领先水平。
- Model Card：原文评价 Neon 的模型说明卡非常简短，意味着公开材料中缺少足够丰富的背景信息来全面判断安全测试结果。
- 100% 拦截率：只对应 Gray-Swan 特定间接提示词注入评测，不等于全面安全保证。

### 8. 文章中出现的主要公司、产品与机构

| 名称 | 身份或作用 |
| --- | --- |
| Google DeepMind | 谷歌 AI 模型研发团队 |
| Gemini 4 Neon | 本文主角，新发布的 AI 模型 |
| Gemini 4 Carbon | 主要性能与成本比较对象 |
| Gemini 4 Hydrogen | 谷歌同系列模型，用于产品定位参照 |
| Artificial Analysis | 第三方 AI 模型评测机构 |
| OpenAI GPT-6.2 Astra | 智能指数排名高于 Neon 的模型 |
| OpenAI GPT-6.2 Sol | 谷歌官方选择的比较对象 |
| Anthropic Claude Fable 5.2 | 智能指数领先模型，也是编程任务的比较对象 |
| Anthropic Claude Opus 5.5 | 编程和演示文稿测试的比较对象 |
| Google Antigravity | 编程智能体测试与运行环境 |
| Google AI Studio | Neon 的开发者使用渠道 |
| Gemini for Business | Neon 的企业服务渠道 |
| Zapier | 自动化平台，提供 AutomationBench 相关测试 |
| Gray-Swan | 提示词注入安全评测名称 |
| Fairwind Program | 网络安全专用模型发布项目 |

原文没有提到具体个人姓名。

## 金句摘录

### 1. 关于谷歌的模型迭代速度
“Google DeepMind has released Gemini 4 Neon, its fourth model in seven weeks.”

中文翻译：“Google DeepMind 发布了 Gemini 4 Neon，这是它在短短七周内推出的第四款模型。”
为什么值得记住： 七周四款模型是整篇文章的重要背景，体现出头部 AI 公司正在以非常高的频率迭代产品。当前模型的领先地位可能很短暂，新模型甚至可能在几周内取代刚刚发布的旗舰产品。

### 2. 关于 Neon 的综合竞争力
“Neon is nearly twice as fast as its sibling Carbon, beats it on most benchmarks and costs significantly less.”

中文翻译：“Neon 的速度几乎是同系列 Carbon 的两倍，在大多数基准测试中超过后者，同时成本明显更低。”
为什么值得记住： 这句话概括了 Neon 的三项主要优势：更快、更强、更便宜。它强调的是多维度的竞争力，而不是单独的智能排行榜成绩。

### 3. 关于 Token 价格与真实效率的区别
“Neon actually uses about 15 percent more output tokens per task than Carbon, so the savings come entirely from the lower per-token list price.”

中文翻译：“实际上，Neon 在每项任务中消耗的输出 Token 比 Carbon 多约 15%，因此它节省的费用完全来自更低的 Token 标准单价。”
为什么值得记住： 这是文章中最有分析价值的观点之一。模型的 Token 单价低，并不意味着模型生成内容时的 Token 消耗效率更高；衡量真实使用成本，必须同时考虑单价和消耗量。

### 4. 关于速度和任务完成时间
“Processing time for the benchmark also drops from about 36 minutes to roughly 21 minutes because Neon generates around 110 tokens per second, nearly double Carbon's rate of 57 tokens per second.”

中文翻译：“由于 Neon 每秒可生成约 110 个 Token，几乎是 Carbon 每秒 57 个 Token 的两倍，因此基准测试处理时间也从约 36 分钟缩短到了约 21 分钟。”
为什么值得记住： 更快的推理与生成速度可以直接改善任务执行效率。对于需要连续调用 AI 的智能体系统，速度提升可能比小幅的智能评分变化更容易转化成实际生产力。

### 5. 关于智能体运行环境的重要性
“In the SWE-sweep test, the Antigravity environment triples Neon's hit rate to 39.0 percent, according to Google.”

中文翻译：“根据谷歌的数据，在 SWE-sweep 测试中，Antigravity 环境将 Neon 的命中率提高至原来的三倍，达到 39.0%。”
为什么值得记住： 同一个模型在不同环境下，最终任务成功率可能相差很大。未来 AI 产品的竞争，不只是模型本身的竞争，也包括智能体框架、工具链以及任务执行系统的竞争。

### 6. 关于模型安全性的测试结果
“According to Neon's (very brief) Model Card, the model blocks 100 percent of indirect prompt-injection attacks on the Gray-Swan benchmark.”

中文翻译：“根据 Neon 那份非常简短的模型说明卡，该模型在 Gray-Swan 基准测试中成功阻止了 100% 的间接提示词注入攻击。”
为什么值得记住： 随着 AI 智能体更多地读取网页、文档和外部工具结果，抵御间接提示词注入的重要性越来越高。不过，特定测试中的 100% 成绩不能等同于现实世界中不存在安全风险。

## 值得记住的点 / 行动建议

### 1. 选择 AI 模型时，首先比较真实任务成本，不要只看 Token 单价
对开发者和企业来说，最应该建立的指标不是单纯的“每百万 Token 多少钱”，而是完成一个符合质量要求的任务实际要花多少钱。
可以使用一个简单的成本计算公式：
任务费用=输入 Token 数106×输入单价+输出 Token 数106×输出单价\text{任务费用}=
\frac{\text{输入 Token 数}}{10^6}\times\text{输入单价}
+
\frac{\text{输出 Token 数}}{10^6}\times\text{输出单价}任务费用=106输入 Token 数​×输入单价+106输出 Token 数​×输出单价
如果涉及缓存，还要将缓存命中的输入 Token 与普通输入 Token 分别计算。
以 Neon 为例，尽管它的标准 Token 价格比 Carbon 低 25%，但由于每个任务平均多生成约 15% 的输出 Token，最后节省的单任务费用只有约 17%。
因此，建议在选型时实际记录三项数据：
- 相同任务下的输入与输出 Token 数量。
- 相同质量要求下的总费用。
- 任务是否真正成功完成，是否需要额外重试。

对于有一定失败率的复杂任务，还可以进一步计算：
每个成功任务的成本=全部任务调用费用成功完成的任务数\text{每个成功任务的成本}
=
\frac{\text{全部任务调用费用}}{\text{成功完成的任务数}}每个成功任务的成本=成功完成的任务数全部任务调用费用​
这个指标通常比单纯的 Token 定价更接近业务价值，因为它把模型失败、重复运行等成本也考虑进去了。

### 2. 不要默认最高推理档位最好，先测试 high 是否已经足够
Neon 的一个非常值得关注的特征是，high 档位可以达到与 Carbon 相同的智能评分，同时把单任务成本降低约一半。
更有意思的是，在 GDP.pdf 文档测试中，Neon 的 high 档位获得 33.4%，而 xhigh 只有 28.0%。
这些数据说明，最高推理档位并不保证在所有任务中都表现最佳。
实际使用时，可以采用以下策略：
**1. 先使用 high 档位执行常见任务。**
**2. 对重要任务建立清晰的正确性和质量评估标准。**
**3. 只有当 high 的结果确实不够好时，再尝试 xhigh。**
**4. 比较两档的任务成功率、总成本与完成时间。**
**5. 为不同任务建立独立的默认配置，而不是全局固定为最高档。**

例如，对于常见的文档整理和演示文稿生成，可以先重点测试 high；对于确实需要复杂推理的任务，再判断是否需要提高推理强度。
核心原则：选择能稳定完成任务的最低必要推理档位，而不是盲目追求最高档位。

### 3. 编程任务要同时评估模型和智能体框架，而不是孤立比较模型
Google Antigravity 在 SWE-sweep 测试中使 Neon 的命中率达到 39.0%，并声称相对于基线提升三倍，这个结果值得开发者重视。
同一个 AI 模型，即使底层权重不变，在不同智能体框架下也可能表现出明显差异。
实际评估 AI 编程工具时，可以准备一组来自真实项目的任务，比如：
- 在现有代码库中定位并修复 Bug。
- 为旧功能添加测试用例。
- 完成一个跨多个文件的新功能。
- 识别并修复依赖变更造成的兼容性问题。
- 根据自动化测试反馈修复失败代码。

然后让不同模型在尽可能一致的工具和权限环境下完成测试，并记录成功率、耗时、代码修改质量与费用。
如果还要比较 Antigravity 等不同框架，最好把“模型变量”和“运行环境变量”分开测试，这样才能知道性能提升究竟来自模型本身，还是来自工具链。
对于有大量重复开发任务的团队，这种方式比直接参考公开 Coding Agent Index 更有意义。

### 4. 重视速度对 AI 智能体整体运行效率的影响
Neon 的生成速度约为 110 Token/秒，而 Carbon 为 57 Token/秒。
如果只进行简单问答，这种差距可能只是等待体验上的改善；但如果一个智能体需要重复生成代码、分析错误、执行工具，再根据反馈继续处理，速度差异就可能持续累积。
因此，在设计 AI 智能体工作流时，建议同时记录：
- 单次调用响应耗时。
- 整个任务完成耗时。
- 模型生成 Token 的速度。
- 工具调用与等待所占时间。
- 失败后需要重新执行的次数。

特别需要注意，实际任务整体耗时不仅由模型 Token 生成速度决定，还受到网络延迟、外部工具响应、推理阶段和任务重试次数的影响。
可以进一步将复杂任务分为多个阶段：让速度快、成本低的模型负责常规操作，仅在困难节点调用更高成本的模型。
这种分层调用策略可能有助于降低整个系统的延迟和费用，但最终收益应通过真实工作流测试确认。

### 5. 把 PDF 文档理解和演示文稿生成作为 Neon 的重点试用场景
文章给出的两个重要指标分别是 GDP.pdf 的 33.4% 和 AA-Briefcase 的 1771 Elo。
它们说明 Neon 在文档理解与演示文稿生成方面有较强竞争力，适合进入这类任务的候选模型名单。
如果日常工作涉及大量 PDF、研究报告或幻灯片，可以设计一组实际测试：
文档理解测试： 选择包含表格、图表、正文以及复杂页面布局的 PDF，让模型提取数据、总结重点，并指出信息所在的页面。
交叉验证测试： 要求模型同时解释图表与文字是否一致，检查它有没有误读数字、漏掉注释或者对图表含义进行过度推断。
演示文稿测试： 用同一份原始材料生成结构化演示文稿，从信息准确性、逻辑结构、重点突出程度、可读性和视觉呈现等方面进行人工评估。
需要注意，AA-Briefcase 的 1771 Elo 是特定测试中的相对质量评分，不能直接证明所有实际演示文稿都能达到同样水平。
对于需要稳定输出成品的工作流，还应测试文件格式、可编辑性、图表准确性和后续人工修改量。

### 6. 定价要区分标准价、促销价和缓存价，避免做出错误的经济判断
文章中的定价差异表明，同一组模型可能因为采用不同价格口径而得出完全不同的结论。
Neon 的标准 Token 单价比 Carbon 低 25%，但 Carbon 仍有持续到 11 月底的促销价格，而 Neon 的标准价格比 Carbon 的促销价高 50%。
此外，Neon 的缓存输入价格低至每百万 Token 0.15 美元，远低于其普通输入价格 3 美元。
这意味着，对于大量重复使用相同提示词、系统指令或上下文材料的应用，缓存命中率也可能影响成本。
建议企业建立动态模型定价表，至少区分标准输入、缓存输入、输出 Token、促销期限和实际账单价格。
尤其是在高频调用场景，应该根据真实使用结构计算每月总费用，而不是只比较宣传中的最低价格。

### 7. 对 AI 厂商官方发布的排行榜保持审慎，交叉核对第三方评测
谷歌官方比较表没有列入排名领先于 Neon 的 GPT-6.2 Astra 和 Claude Fable 5.2，而是选择了 GPT-6.2 Sol 和 Claude Opus 5.5。
这种选择说明，官方展示的模型对比可能并不是市场的完整横向排名。
在阅读模型发布文章时，可以按三个层次核对：
第一层是厂商自测，了解模型被重点优化的能力和所声称的优势。
第二层是第三方基准测试，确认模型在其他测试体系下是否仍能保持相似优势。
第三层是自己的实际任务测试，判断模型在真正的业务环境中能否稳定、经济地完成工作。
还要留意不同评测的配置是否一致，例如推理档位、工具权限、测试环境、上下文长度和定价时间点。
真正可靠的比较，应该尽可能保证测试条件一致，而不是把不同来源的分数直接放在一起下结论。

### 8. 在自动化和安全敏感场景中，不要把高分直接当成生产可用保证
Neon 在 AutomationBench、RiemannBench、SEC-bench Pro 和 Gray-Swan 等评测中取得了不错的成绩，但这些数据的含义各不相同。
特别是在网络安全和自动化任务中，成功率、错误率以及失败时的影响，比普通文本生成更加重要。
例如，在 Gray-Swan 测试中阻止 100% 的间接提示词注入攻击，并不意味着模型可以安全地读取所有不可信网页、邮件或外部文档。
如果要把 Neon 用于企业工作流，仍然需要配置工具权限、执行范围控制、敏感操作审批、日志记录和异常处理机制。
对网络安全专用变体也是如此，SEC-bench Pro 的 90.5% 和 WebExploitBench 的 51.26% 只是相应基准下的表现，不能替代实际环境中的安全测试。
模型安全应当被视为整个系统的属性，而不是模型说明卡上的某一个分数。

### 9. 面对快速迭代的 AI 市场，建立持续评估和可切换的模型使用策略
七周四款模型意味着，企业过去按季度或年度评估 AI 模型的方式，可能无法及时反映市场变化。
如果某个模型的性能、速度和价格在几周内就可能发生明显变化，那么将整个业务工作流深度绑定在单一模型上，可能带来机会成本。
更稳妥的办法是建立一套固定的评估任务集，并保留可切换模型的技术架构。
在有新模型发布时，不需要立即全量迁移，而是先针对实际场景进行小规模对比：看质量是否提高、成本是否下降、速度是否改善，以及安全性和稳定性是否满足要求。
对于已经运行良好的业务系统，迁移收益还需要覆盖提示词调整、代码兼容、测试和运维等额外成本。
因此，值得追求的不是始终使用排行榜上的最新模型，而是让模型选择可以随着实际业务收益的变化而灵活调整。

## 我的点评
这篇文章最有价值的地方，是没有停留在“谷歌又发布了一个更强模型”的新闻层面，而是通过价格、Token 消耗、速度、任务成本和不同领域的测试结果，展示了 AI 模型之间真正的竞争维度。
尤其值得认同的是它对成本与效率的区分：Neon 单价降低 25%，却消耗更多输出 Token，使实际单任务成本仅下降约 17%；这个细节说明，企业使用 AI 时应该以完成任务的综合成本为中心，而不是以官方报价为中心。
文章的另一大亮点，是揭示了推理档位与最终效果并非简单的正相关关系，以及智能体运行环境可能显著影响模型表现，这两点对实际开发和选型都很有启发。
不过，文章也有局限：部分专业领域的数据直接来自谷歌官方，缺少完整测试方法与第三方复现信息；同时，不同测试的任务范围、运行环境和价格口径并不完全一致，因此不能据此断言 Neon 在所有现实场景中都优于竞争模型。
此外，Neon 虽然在第三方智能指数中排名第三，但这项排名本身也只是特定评测体系下的结果，不能完全代表模型在所有应用中的实际能力；而从 Carbon 促销价来看，Neon 的价格优势还存在明显的时间条件。
普通人最应该带走的结论是：AI 模型已经进入快速更新、不同能力各有优势的阶段，与其长期追逐“最强模型”，不如根据自己的真实任务持续比较质量、速度、费用和稳定性。 一个实用的下一步，是建立自己的固定测试任务清单，每次有重要新模型发布时用同样的任务进行对比，这比单纯关注新闻中的排名更有长期价值。

---

## 📝 完整文字稿

Google DeepMind has released Gemini 4 Neon, its fourth model in seven weeks. Neon is nearly twice as fast as its sibling Carbon, beats it on most benchmarks and costs significantly less. Google continues to ship at a remarkable pace.

Google DeepMind has released Gemini 4 Neon, already its fourth AI model in seven weeks. Neon offers a one-million-token context window for text, images, audio and video, and Google positions it between Carbon and Hydrogen.

Google's Gemini 4 Neon ranks third on the Artificial Analysis Index.

At its highest reasoning level, "xhigh," Neon scores 61 points on the Intelligence Index, edging past Gemini 4 Carbon at 60 points and landing in third place behind OpenAI's GPT-6.2 Astra and Anthropic's Claude Fable 5.2, both of which Google omits from its own comparison table.

In its own overview, Google only compares the new model against Claude Opus 5.5 and GPT-6.2 Sol. | Image: Google

### The Cost Advantage Comes from List Price, Not Token Efficiency

Through Google AI Studio and Gemini for Business, one million input tokens costs three dollars (or $0.15 when cached) and one million output tokens costs fifteen dollars. That is 25 percent below Carbon's regular price of four and twenty dollars, but 50 percent above Carbon's promotional price, which remains in effect through the end of November.

According to Artificial Analysis, per-task costs for Neon at xhigh come in at $6.44, roughly 17 percent below Carbon's undiscounted figure of $7.76. Neon actually uses about 15 percent more output tokens per task than Carbon, so the savings come entirely from the lower per-token list price. At the second-highest level, "high," Neon matches Carbon's intelligence score while cutting per-task costs in half. Processing time for the benchmark also drops from about 36 minutes to roughly 21 minutes because Neon generates around 110 tokens per second, nearly double Carbon's rate of 57 tokens per second.

### Half the Cost for Coding Agents and Strong Visual Analysis

The model is especially competitive on the Coding Agent Index. Inside Google Antigravity, Neon at xhigh scores 59 points, beating Carbon (55 points) as well as Claude Fable 5.2 and Claude Opus 5.5 (58 points each) at a fraction of the price. An average coding task costs $6.86 with Neon, compared to $12.61 for Opus and $15.47 for Fable. In the SWE-sweep test, the Antigravity environment triples Neon's hit rate to 39.0 percent, according to Google.

Neon slots in between Hydrogen and Carbon, though it beats Carbon on nearly every benchmark. | Image: Google

Artificial Analysis measured large gains in visual processing. On the document test GDP.pdf, Neon at "high" hits the top score of 33.4 percent, five points ahead of Carbon, though it oddly falls back to 28.0 percent at "xhigh." On the AA-Briefcase test, Neon takes the lead for best presentation quality with 1771 Elo points, ahead of Opus 5.5.

In Google's own evaluations, Neon also leads individual categories on the Vals Index, Zapier's AutomationBench (56.3 percent) and science tests such as RiemannBench (84.0 percent). For security professionals, Google is launching a cyber variant through the Fairwind Program that delivers top scores on SEC-bench Pro (90.5 percent) and WebExploitBench v1.2 (51.26 percent) at half the price of competing models. According to Neon's (very brief) Model Card, the model blocks 100 percent of indirect prompt-injection attacks on the Gray-Swan benchmark.
