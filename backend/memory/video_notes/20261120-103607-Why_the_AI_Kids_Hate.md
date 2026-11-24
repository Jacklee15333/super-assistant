# 为什么 AI 圈的年轻人讨厌 Astra 6.2

- 来源链接：https://www.youtube.com/watch?v=uSzew8QPRX0
- 作者：The AI Daily Brief: Artificial Intelligence News
- 提取时间：2026-11-20 10:36
- 原标题：Why the AI Kids Hate Astra 6.2
- 标签：模型评测、成本效率、编程智能体、企业AI、模型竞争

## 🤖 AI 分析

## 一句话概括
OpenAI 发布的 GPT-6.2 Astra 和 Sol 在成本、速度及 Token 效率上取得明显进步，却因编程、写作和复杂任务执行体验不佳而遭到核心 AI 用户批评；这场争议揭示了 OpenAI 正在优先追求企业级 AI 的成本效率与实际生产力，而部分开发者更重视模型能力上限和自主完成复杂任务的体验，两种评价标准正在发生分化。

## 背景与主题
本期《AI Daily Brief（AI 每日简报）》由主持人围绕 OpenAI 新模型 GPT-6.2 Astra 和 GPT-6.2 Sol 的发布展开分析，核心问题是：为什么模型在客观评测中有所进步，却遭遇如此严重的负面口碑？
节目首先介绍了美国多个关键机构的系统故障，以及 NVIDIA（英伟达）围绕 Jensen Huang（黄仁勋）是否重返 CEO 职位的争议，随后将重点转向 OpenAI 新模型发布、Artificial Analysis（AI 模型评测机构）的数据，以及 Matt Schumer、Theo、Dan Shipper 等 AI 开发者和评论者的实际使用反馈。
视频尤其关注一个战略问题：在 Anthropic 准备 IPO、竞争模型 Fable 5.2 获得较高评价的背景下，OpenAI 是否正在主动放弃部分高端编程体验，转而争夺更大规模的企业办公、智能体和低成本任务执行市场？
主持人的总体立场并不是断言 GPT-6.2 是失败产品，而是认为这次升级幅度有限、优化方向明确，不同用户对同一模型的评价可能完全相反，最终仍应根据自身工作流验证其价值。
整理说明：以下内容依据提供的语音文字稿归纳，并非独立新闻核验。部分模型名称、评测项目、人物身份及 NVIDIA 人事事件可能存在转写或来源问题；尤其是重大人事、财报与产品发布信息，均作为视频中的陈述记录，不直接视为已经核实的事实。

## 核心观点

### 1. 美国关键系统接连故障，AI 带来的风险可能不是网络攻击，而是自动化更新本身
视频开头提到，Microsoft Outlook、美国联邦航空管理局 FAA、多家美国银行、JPMorgan（摩根大通）、Apple（苹果）、United Airlines（美国联合航空）等机构和企业接连出现系统异常，甚至连美国国家安全局 NSA 的内部网络 NSAnet 也受到影响。根据视频转述的 CNN 报道，NSA 的部分办公区域在周末夜间关闭，仅保留必要人员继续工作，以便进行网络维护，但重要的国家安全任务仍保持运行。由于故障集中发生在关键基础设施和大型企业系统，一部分人猜测，美国是否正在遭遇一场持续但尚未公开的 AI 驱动网络攻击；然而主持人强调，当时没有证据证明这些故障属于网络攻击。a16z 的 Martin Casado（马丁·卡萨多）将其与 Y2K（千年虫）时期由软件升级引发的大规模服务中断相比较，而美国国家网络总监办公室 ONCD 的 Shawn Cairncross 则提醒，今后可能会看到更多由软件更新、系统升级与部署引起的故障。由此产生的深层判断是：AI 不一定需要被攻击者恶意使用才能造成系统性风险，它也可能通过加快代码生成、更新部署与自动化运维，使企业在更短时间内引入更多变更，进而放大软件质量与兼容性问题。

### 2. NVIDIA 的 CEO 争议说明，AI 巨头的公司治理和地缘政治风险同样影响市场信心
视频描述了一场围绕 NVIDIA 创始人 Jensen Huang（黄仁勋）是否应该重返 CEO 岗位的重大争议：黄仁勋在社交平台上发表长文，承认自己犯过严重错误，同时表达愿意在董事会认为合适时重新担任 CEO 的意愿。他强调自己在 53 年前来到美国，成为美国公民是人生中最重要、最自豪的经历之一，而 NVIDIA 是他毕生事业的核心成果。部分科技界人物公开支持其回归，例如 Y Combinator 创始人 Paul Graham（保罗·格雷厄姆）认为，董事会很难令人信服地证明其他候选人会比黄仁勋做得更好；市场也对这一可能性作出积极反应，视频称其发帖后的五分钟内 NVIDIA 股价上涨约 2%。但董事会主席 Harvey Jones 和临时 CEO Colette Kress 对外表示，董事会已经接受黄仁勋的辞职，并且没有重新任命他的计划，而 Semafor 的内幕报道又称，董事会内部对其回归存在不同意见，其中三名董事强烈反对，其余七人的立场尚不明确。主持人借此说明，即使 AI 公司拥有极强的业绩增长和技术优势，CEO 继任、董事会治理、国家安全政策以及国际市场准入仍可能成为影响估值和企业发展的核心变量。

### 3. GPT-6.2 的发布不只是模型升级，也可能是 OpenAI 在 Anthropic IPO 前的一次战略表态
视频提到，在 Anthropic 即将进行 IPO 的背景下，外界曾猜测 OpenAI 会不会推出一款所谓的 spoiler model（搅局模型），通过新产品发布转移市场和媒体的关注。随后 OpenAI 确实在周二发布了 GPT-6.2 Astra 和 GPT-6.2 Sol 两款模型，但主持人并不认为它们足以抢走 Anthropic 的风头，因为新模型并没有展现压倒性的能力提升，反而引发大量负面评价。OpenAI 官方宣传强调的是“super efficient and built to perform where it counts, the real world（效率极高，专为现实世界中真正重要的任务而构建）”，这与过去一年新模型发布时普遍强调编程能力、复杂推理与排行榜名次的风格存在明显差异。官方发布材料将 Agents Last Exam、Terminal-Bench Science 等偏向智能体和实际任务表现的评测放在更靠前的位置，而在谈到代码能力时，突出的卖点仍然是成本优势。主持人由此推测，OpenAI 可能正在有意把自己的定位从“谁拥有最强编程模型”转向“谁能以更低成本完成最多实际工作”，这既可能是一种企业市场战略，也可能是在 Anthropic 上市前保持市场存在感的防御性动作。

### 4. 客观评测显示 GPT-6.2 的综合能力有所提升，但提升幅度不足以支撑颠覆性发布
根据 Artificial Analysis 的 Intelligence Index（智能水平指数），GPT-6.2 Sol 的得分从上一代的 55 分提高至 57 分，增加 2 分，与 GPT-6 Astra 达到相同水平，但仍落后于 Opus 5.5、Gemini 4 Carbon 和 Fable 5.2。GPT-6.2 Astra 则提高了 5 分，达到 62 分，在这一榜单中升至第二位，仅次于 Fable 5.2。这样的数据说明，OpenAI 并非完全没有提升模型能力，而是取得了一定幅度的增量改进，尤其是 Astra 的综合能力仍然处于领先梯队。Artificial Analysis 还指出，OpenAI 的产品覆盖了 Pareto frontier（帕累托前沿）上的多个价格与性能区间，既有竞争力较强的中等价位模型，也有能力更高的高级模型。问题在于，排行榜的综合得分并不等于真实工作流的完成质量：一个模型可能在多数测评中得分更高，却因为遗漏关键信息、提前终止任务或交互方式变化，让特定用户感觉它比上一代更难用。

### 5. GPT-6.2 最大的优势是单位任务成本下降，而不仅是模型本身变得更聪明
Artificial Analysis 的成本测试显示，GPT-6.2 Astra 完成一项基准任务的平均成本约为 4 美元，而 GPT-6 Astra 为 6.24 美元，下降约 35%—36%；GPT-6.2 Sol 的对应成本约为 1.01 美元，而视频给出的对照值为 1.27 美元。主持人指出，这种改进同时来自两个方面：一是每个 Token 的定价降低，二是模型完成相同任务时可能消耗更少 Token，也就是 Token efficiency（Token 使用效率）提高。与 Anthropic 模型相比，视频称 Fable 5.2 即使使用 High 设置，成本仍超过 GPT-6.2 Astra 使用 Max 设置时的两倍，而 GPT-6.2 Sol 使用 Max 设置的成本不到 Opus 5.5 使用 High 设置的三分之一。一位测试者 Alex Finn 还表示，在自己的个人基准任务中，Astra 6.2 只用了三分之一的时间、三分之一的费用和四分之一的 Token 就完成了工作。这种优势对高调用量企业尤为重要：一次任务节约几美元看似不多，但当企业每天运行数万甚至数百万次调用时，成本差异可能改变整个应用的商业可行性。

### 6. 编程和复杂任务执行能力的退步，是开发者强烈反感 GPT-6.2 的直接原因
尽管综合智能指数上升，Artificial Analysis 的 Coding Agent Index（编程智能体指数）却给出了不太乐观的结果：GPT-6.2 Astra 的整体得分与排名基本没有进步，GPT-6.2 Sol 甚至下降 3 分，排名落到 Kimi 3.1 和 GPT-6.1 Terra 后面。评测方将 Sol 的退步部分归因于名为 Sui Atlas 的测试项目，称新版本在回答中更容易遗漏关键事实，说明模型的压缩与效率优化可能损害了信息完整性。在真实开发场景中，Every 的 Dan Shipper 表示 Astra 6.2 经常过早停止任务，尤其在需要端到端完成产品或项目构建时令人沮丧；在写作上，它被调校得过分简短和行动导向，反而让需要详细阐述的内容难以理解；在设计上，它虽然有不错的默认审美，却不容易跳出固定模板，输出存在明显的 house style（统一模板化风格）。开发者 Theo 的评价更加尖锐：模型非常聪明，但经常兜圈子、无法完成实际项目，甚至像是只按照自己的逻辑选择向用户呈现哪些信息。换言之，开发者并不只关心模型是否能写出正确的一段代码，而更关心它能不能持续理解上下文、完整执行任务、保持设计多样性，以及减少人工接管和返工。

### 7. 同一个模型出现两极分化的评价，是因为不同用户衡量的并不是同一种能力
对于 GPT-6.2，Matt Schumer 认为测试体验糟糕到几乎无法使用，Every 的约 30 人团队也没有表现出愿意转用新版本的积极反馈，而研究者 Ethan Mollick 将其描述为“very uneven and weird（表现极不均衡，而且很奇怪）”。但正面反馈同样存在：Ash 表示 Astra 6.2 在 Computer Use（计算机操作）工作流中表现很强，已经连续数周成为自己执行 Agentic Video Editing（智能体视频剪辑）任务的主力模型。Claire Vo 展示了自己制作的交互式故事书，并称 Astra 6.2 在图像生成与动画编程结合方面具有令人愉悦的表现；Josh Pertel 则表示，在自己认为信号质量最高的自动化研究测试中，Sol 和 Astra 都非常强大。Alex Finn 和 Zwen 的态度进一步表明，如果只衡量绝对质量，新模型可能不够令人满意，但如果将速度、成本、Token 消耗与输出质量放在一起评价，GPT-6.2 就可能成为一个性价比很高的选择。这说明 AI 产品的“好坏”越来越依赖具体任务：写作、交互式创作、长周期编程、自动研究、计算机操作与批量企业流程，对模型的能力结构有完全不同的要求。

### 8. 负面评价可能不完全来自基础模型，Harness 和测试版本差异也影响了使用体验
视频提出一个容易被忽略的技术问题：用户接触到的并不只是基础模型，而是 model + harness（模型加智能体执行框架） 组成的完整系统，其中 Harness 可能负责工具调用、上下文管理、执行循环、权限控制以及任务终止策略。Claire Vo 认为，一部分负面体验实际上来自模型与 Harness 的组合不好用，而 Pietro Sciorano 表示，在去掉原先的执行框架后，Astra 6.2 的表现明显改善，感觉模型终于能够顺畅运行。OpenAI 团队成员 Tibo 还指出，部分意见领袖提前几周拿到了测试权限，但官方在正式发布前的三到四天进行了大量修改，而部分测评视频可能在这些修改之前就已经制作完成。对此，Token Gremlin 批评 OpenAI 的发布组织方式：让测试者花费大量时间评估旧版本，最终却在临近发布时大幅修改产品，无异于主动制造负面舆论。Theo 随后根据这一情况重新测试，承认新版本比先前有所改善，但仍认为总体方向存在严重问题，因此不能简单把所有差评归因于 Harness 或旧测试版本。

### 9. OpenAI 和 Anthropic 的产品路线正在分化：前者突出协作和效率，后者突出复杂任务的自主完成
主持人回顾了两家公司长期存在的一种使用模式差异：Anthropic 的 Fable 系列更像一个能够独立承担完整项目的智能体，用户给出任务后，可以暂时离开，让模型持续工作直至交付；OpenAI 的模型则相对更强调人与模型之间密集的往返协作，需要用户通过多轮交互不断推进任务。这种差异可能解释为什么许多偏爱复杂编程智能体的早期用户对 Astra 6.2 感到失望，因为他们希望获得类似 Opus 5.5 那样能够一次性完成更多工作的能力，而不是一个便宜但需要频繁监督的助手。但从企业角度看，绝大多数工作并不是独立开发一个大型软件项目，而是整理会议、处理文档、生成报告、分析数据、自动操作办公软件或处理规模化重复任务，这些任务更加重视稳定交付、成本控制和员工参与。若 GPT-6.2 的优化方向确实集中在这些场景，那么它可能更适合企业级智能工作台，而非追求极致编程体验的个人开发者。主持人认为，这种差异可能是 OpenAI 有意选择的一条竞争路线，而不是单纯在模型能力竞赛中落后。

### 10. 发布广告引发的争议，暴露出 AI 企业生产力叙事与技术理想之间的冲突
OpenAI 随 GPT-6.2 发布了一部约两分钟的宣传短片，内容展示多名白领员工临时发现自己忘记完成老板安排的工作，于是利用 Astra 在不到一分钟的时间内迅速补救。部分科技圈人士认为，这种宣传方式将 AI 描绘成帮助低效员工应付工作的工具，而不是帮助人类突破原有能力边界的革命性技术；例如 Notion 的 Brian Levin 称其为“a profoundly sad vision of the future（一个令人深感悲哀的未来图景）”，Zack Trader 则将视频概括为“we help your incompetent people fake it（我们帮助你那些不称职的员工蒙混过关）”。但主持人也给出了两个反面解释：第一，广告可能只是借鉴经典办公室喜剧《Office Space》的风格，用 1990 年代的厚重电脑、笨拙老板和职场尴尬制造轻松幽默；第二，OpenAI 或许正在借此主动向普通白领和企业管理层传递价值主张。对员工来说，AI 可以快速完成琐碎、重复且令人厌烦的任务；对老板来说，AI 可以压缩人力时间和计算成本，提高组织运行效率。广告争议的本质在于，AI 究竟应该被讲述成“让人类创造以前不可能创造的东西”，还是“让现有工作更快、更便宜地完成”，而 OpenAI 可能正在优先选择第二种商业叙事。

## 关键事实与数据

### 一、GPT-6.2 产品发布与评测表现

| 项目 | 视频给出的信息 | 意义 |
| --- | --- | --- |
| 发布时间 | 周二发布（未提供明确日期） | 处于 Anthropic IPO 讨论期间 |
| 新模型 | GPT-6.2 Astra、GPT-6.2 Sol | 两款不同定位的模型 |
| 官方定位 | Super efficient、real-world performance | 强调效率与实际应用 |
| GPT-6.2 Sol 智能指数 | 55 → 57，提升 2 分 | 小幅提高综合能力 |
| GPT-6.2 Astra 智能指数 | 约 57 → 62，提升 5 分 | 进入评测榜第二名 |
| Astra 排名 | 第二，仅次于 Fable 5.2 | 仍处于高端模型梯队 |
| Astra 编程智能体指数 | 分数及排名基本不变 | 编程性能缺少明显升级 |
| Sol 编程智能体指数 | 下降 3 分 | 出现明确的测试退步 |
| Sol 编程排名 | 落后于 Kimi 3.1、GPT-6.1 Terra | 编程场景的竞争力受到影响 |
| 评测机构 | Artificial Analysis，简称 AA | 提供第三方性能和成本比较 |

视频出现的其他模型还包括 GPT-6 Astra、Opus 5.5、Gemini 4 Carbon、Fable 5.2。评测名称包括 Intelligence Index、Coding Agent Index、Agents Last Exam、Terminal-Bench Science 和 Sui Atlas；其中部分名称来自不够清楚的语音识别，正式引用前应确认其标准写法。

### 二、模型成本与效率数据
Artificial Analysis 每任务成本：GPT-6 Astra 对比 GPT-6.2 Astra
GPT-6 Astra

# $6.24
旧版本

GPT-6.2 Astra

# $4.00
新版本

视频中的单任务成本对比
单位：美元/任务；Sol 的 1.27 美元为视频中的对照值，具体对应版本不清楚。

其他值得保留的效率数据：
- Astra 任务成本下降约 35.9%：由 6.24 美元下降到 4 美元，节省 2.24 美元。
- Sol 的任务成本约下降 20.5%：根据视频中 1.27 美元与 1.01 美元的对照值计算，但前者对应的具体版本未说清。
- Fable 5.2 与 Astra 的成本差距：视频称 Fable 5.2 在 High 设置下，成本超过 Astra 6.2 在 Max 设置下的两倍。
- Opus 5.5 与 Sol 的成本差距：视频称 Sol 6.2 在 Max 设置下的成本，不到 Opus 5.5 在 High 设置下的三分之一。
- Alex Finn 的个人测试：Astra 6.2 使用约 1/3 的运行时间、1/3 的费用、1/4 的 Token 完成基准任务。
- 总体趋势：模型的竞争指标正从单纯的智能分数，扩展到每任务成本、完成时间、Token 使用量和实际交付质量。

需要注意，第三方评测和个人基准测试采用的任务、执行设置可能不同，以上数据不能直接理解为所有场景都会获得同样幅度的效率收益。

### 三、主要开发者和研究者的反馈

| 人物或团队 | 评价 | 主要依据 |
| --- | --- | --- |
| Matt Schumer | 强烈负面 | 认为模型几乎无法使用，不推荐 |
| Spawn 创始人 Jacob | 负面 | 简短表示“Same, not good” |
| Dan Shipper / Every | 负面 | 30 人团队测试写作、编程、设计、知识工作 |
| Theo | 强烈负面 | 复杂项目中循环、提前停止、缺乏连贯执行 |
| Ethan Mollick | 谨慎负面 | 表现不稳定，不是明确的代际进步 |
| Ash | 正面 | Computer Use 和智能体视频剪辑表现良好 |
| Claire Vo | 正面但有保留 | 交互式故事、图像与动画代码表现较好，也批评 Harness |
| Josh Pertel | 正面 | 自动化研究基准测试表现强劲 |
| Alex Finn | 正面 | 极高的速度、价格和 Token 效率 |
| Zwen | 混合偏正面 | 绝对质量有问题，但性价比值得肯定 |
| Pietro Sciorano | 正面 | 移除原有 Harness 后体验明显改善 |
| Token Gremlin | 批评发布流程 | 认为提前测试与临近发布修改造成混乱 |

Every 团队反馈中的三项具体问题：
- 写作：过于追求简洁和可执行性，导致复杂信息解释不足、文章可读性下降。
- 编程：在端到端开发任务中频繁过早停止，需要用户反复推动。
- 设计：默认设计能力不错，但风格变化不足，容易呈现固定的视觉模板。

### 四、关于模型版本与 Harness 的关键细节
- 部分早期测试者在模型正式发布前数周便获得访问权限。
- OpenAI 团队成员表示，正式上线前的最后三到四天进行了较多调整。
- 一些负面评测视频可能使用的是更早的版本。
- Pietro Sciorano 认为，测试问题主要发生在执行框架，而不是基础模型。
- Theo 在了解版本更新后重新进行了较长时间的测试。
- Theo 的复测结论是：新版比先前有所改善，但整体方向仍令他不满意。
- 因此，仅凭首发当天的口碑，无法充分判断基础模型与实际产品系统各自的问题。

### 五、美国关键系统故障事件
视频涉及的机构或企业：
- Microsoft Outlook（微软邮件服务）
- FAA（美国联邦航空管理局）
- 美国多家银行，包括 JPMorgan
- NSA（美国国家安全局）的内部网络 NSAnet
- Apple
- United Airlines

相关人物及观点：
- Martin Casado，a16z：认为这类更新相关故障令人联想到 Y2K。
- Shawn Cairncross，ONCD：提醒公众关注由软件更新与部署造成的服务中断。
- 一位文字稿中识别为 Backenzie Arnold 的评论者：提出 AI 自动化可能使软件更新更频繁，因而间接增加故障风险；姓名需进一步核对。

事实与推测的区别：视频描述了多起系统中断事件，但没有提供这些事件同属一次攻击、由 AI 直接导致，或具有共同技术根因的证据。

### 六、NVIDIA 人事、业绩和中国市场信息
以下均为视频中的报道性陈述，其中重大人事内容需要独立核实。

| 项目 | 视频中的数字或信息 |
| --- | --- |
| 黄仁勋移居美国 | 53 年前 |
| 黄仁勋的公开态度 | 承认重大错误，表示愿意按董事会决定重返 CEO 职位 |
| 发帖后股价变动 | 五分钟内上涨约 2% |
| 董事会正式态度 | 接受辞职，不打算重新任命 |
| 董事会内部分歧 | 三人强烈反对，其余七人立场尚不明确 |
| 营收增长 | 视频称 103% annualized growth（年化增长率口径） |
| 第四季度营收预期 | 1300 亿美元 |
| 长期增长预期 | 从 70% 上调至 75%，预测延伸到 2028 年 |
| 财报电话会后股价表现 | 盘后上涨约 4.5% |
| 中国 AI 芯片业务 | 视频称停止向中国供应获许可的 Hopper 数据中心产品 |
| 涉及芯片 | H200 |
| 监管背景 | 视频提及特朗普政府此前批准相关出口 |
| 后续财务影响 | 视频称尚无法确定近期相关政策变化造成的营收损失 |

出现的人物和机构包括：
- Jensen Huang（黄仁勋）：NVIDIA 创始人。
- Colette Kress：视频中的临时 CEO。
- Harvey Jones：视频中的董事会主席。
- Paul Graham：Y Combinator 创始人。
- Balaji Srinivasan：科技投资者和思想评论者。
- Matt Bryson：Wedbush Securities 分析师。
- CNBC、Semafor：视频引用的报道来源。

这里存在需要特别注意的地方：文字稿对黄仁勋发帖时间的描述出现周日、周二等不一致口径，而 NVIDIA 高层人事变动、第四季度 1300 亿美元营收指引及中国市场业务调整均属于可能显著影响市场判断的信息，不能在未核实之前作为投资分析依据。

### 七、视频中涉及的 AI 产品和商业案例
这一部分来自节目的赞助商介绍，反映了当前企业 AI 的几个重点商业场景，但其中的效率数据属于厂商宣传口径。
KPMG（毕马威）
推广《You Can With AI》播客系列，讨论企业如何从 AI 战略走向真实执行。议题包括数据准备、管理机制、工作流改造以及实际业务价值。文字稿中出现的嘉宾包括 Surojit Chatterjee、Writer 的 May Habib，以及 McKesson CIO Ellery Fisher，部分身份与拼写需核对。
Granola（AI 会议笔记工具）
- 用户在会议中记录简要笔记，软件负责转录、整理和提取重要信息。
- 无需让额外的 AI 机器人加入会议。
- 支持会后提取 Action Items（行动项）、起草跟进邮件和准备沟通。
- 支持 Recipes（预设提示词模板），将会议记录转化为可重复使用的工作流。
- 视频中的促销条件：新用户使用代码 `ai daily`，可获得三个月 100% 折扣。

Gartner（高德纳）
重点宣传企业 AI 风险管理，包括 AI 驱动的网络威胁、物理资产安全、AI 供应商的数据保护，以及大量 AI Agents 同时工作的治理问题。
Blitzy（AI 代码现代化工具）
该公司主张，传统代码迁移失败的原因之一，是智能体只理解局部语法，无法掌握大型旧系统多年积累的设计决策、依赖关系和隐性知识。
其技术方案是先对整个系统进行逆向工程，构建 Persistent Knowledge Graph（持久化知识图谱），然后再执行编程语言迁移和端到端系统集成。
视频给出的客户案例：

| 指标 | 数值 |
| --- | --- |
| 原有保险单体系统价值 | 1000 万美元 |
| 传统项目基线周期 | 137 周 |
| 使用智能体后的周期 | 16 周 |
| 周期压缩倍数 | 约 9 倍 |

该案例说明，厂商正在从“AI 能生成多少代码”转向“AI 能否理解完整的遗留系统，并独立推进大规模工程交付”。但实际效果仍需考虑迁移范围、验收标准、运行风险与人工参与程度。

## 金句摘录

### 1. OpenAI 对新模型的官方定位
“Super efficient and built to perform where it counts, the real world.”

中文翻译：效率极高，专为现实世界中真正重要的任务而构建。
含义：OpenAI 正在将模型的核心价值从单纯追求评测能力，转向强调真实任务的投入产出比。

### 2. Matt Schumer 对新模型的强烈批评
“I had a terrible experience testing them. They were essentially unusable. I do not recommend these models.”

中文翻译：我在测试这些模型时的体验非常糟糕。它们基本上无法使用。我不推荐这些模型。
含义：这是视频中最具代表性的负面评价之一，说明新模型的真实体验并没有得到部分资深使用者的认可。

### 3. Theo 对模型能力与使用体验矛盾的总结
“This model is clearly super smart, it is insufferable to work with on real projects. It feels like it just lives in its own world and randomly decides what parts of its brain are shown to us.”

中文翻译：这个模型显然非常聪明，但在真实项目中与它合作简直令人无法忍受。感觉它生活在自己的世界里，还会随机决定向我们展示自己大脑中的哪些部分。
含义：AI 模型的能力高，并不意味着它必然容易协作。缺乏可预测性和任务连贯性，可能使高智能模型反而更难用于专业工作。

### 4. Alex Finn 对效率优势的总结
“Astra 6.2 finished the benchmark in a third of the time for a third of the price at a quarter of the tokens.”

中文翻译：Astra 6.2 只用了三分之一的时间、三分之一的费用，以及四分之一的 Token，就完成了整个基准测试。
含义：如果两个模型都能达到实际交付标准，计算成本、速度和 Token 效率就可能比排行榜上的几分差距更加重要。

### 5. 对 OpenAI 宣传广告最尖锐的讽刺
“We help your incompetent people fake it.”

中文翻译：我们帮助你那些不称职的员工蒙混过关。
含义：这句对广告的讽刺反映出一些技术人士的担忧：当 AI 的能力越来越强大，企业却可能把它宣传成掩盖职场低效、应付老板和赶工的工具，而不是释放人类创造力的基础设施。

### 6. 主持人对整个争议的最终总结
“Perception is in the eye of the beholder, and it is very much worth doing your own testing.”

中文翻译：每个人的看法都取决于自己的视角，而亲自测试这些模型非常值得。
含义：判断模型价值，不能只看社交媒体情绪或单一测试结果，而应该以个人及企业的实际工作流为标准。

## 值得记住的点 / 行动建议

### 1. 不要直接根据模型排行榜选工具，应先建立自己的任务评测集
视频最大的实践启示是：模型排行榜只能帮助筛选候选模型，不能代替实际业务验证。
可以从自己的工作中选取 10—20 个具有代表性的任务，组成一个小型私有评测集。例如设计师可以选择产品主图方案、广告文案、视觉风格分析、页面结构设计和图片优化需求；程序员可以选择 Bug 修复、跨文件重构、功能开发和项目部署；企业管理人员则可以选择会议纪要、报告撰写、数据分析和复杂资料整理。
建议每个任务都保持相同的输入、资料与验收标准，并让不同模型分别执行。
评分至少覆盖五个维度：结果正确性、交付完整度、人工修改量、完成时间、实际成本。对于需要调用工具的 Agent，还应该记录中途失败次数与人工接管次数，避免出现“任务看起来完成了，实际上关键步骤被省略”的情况。

### 2. 从“每 Token 成本”升级到“每个合格交付的总成本”
企业选择 AI 模型时，真正应该关注的是 Cost per Successful Task（每个成功任务的成本），而不是单纯的 Token 单价。
例如，A 模型每次运行成本 1 美元，但成功率只有 70%，失败后必须返工；B 模型每次运行成本 1.5 美元，但成功率达到 95%，并且人工修改更少。虽然 B 模型表面单价更贵，却有可能带来更低的总业务成本。
可以使用下面的简化公式建立评估：
成功任务成本=模型调用总费用+工具及人工返工成本合格完成的任务数量\text{成功任务成本}
=
\frac{\text{模型调用总费用}+\text{工具及人工返工成本}}
{\text{合格完成的任务数量}}成功任务成本=合格完成的任务数量模型调用总费用+工具及人工返工成本​
进一步还应评估任务耗时、人工干预次数以及失败结果带来的业务损失。
对于高频、低风险、输出容易验证的任务，便宜且快速的模型可能更合适；但对于关键代码、复杂分析和高责任决策，可靠性往往比单次调用价格更重要。

### 3. 把模型和 Harness 分开评估，避免把系统问题误判成模型能力问题
当 Agent 执行不稳定时，不要立即认定是基础模型不够强。
同一个模型在不同执行框架下，可能因为上下文截断、任务完成条件、工具返回结果处理、循环控制等因素，表现出完全不同的能力。
建议至少进行三组测试：第一组只使用模型本身完成独立推理和内容生成；第二组让模型在固定 Harness 中执行多步骤任务；第三组在调整或更换 Harness 后重新运行相同任务。
如果模型直接回答表现良好，但进入智能体框架后频繁提前停止，就应该优先检查任务终止逻辑、工具调用权限、上下文保留方式及错误重试机制。
这对复杂 AI 编程、Computer Use 和多智能体系统尤为重要，因为真实产品的性能是模型、工具、运行环境和编排策略共同作用的结果。

### 4. 根据任务是否需要长期自主执行，决定采用什么模型
视频提到，Anthropic 的一些模型更适合一次性接收复杂任务，然后长时间自主执行，而 OpenAI 的部分模型可能更适合与人持续互动。
这个差异可以直接转化为模型选择规则。
对于大型项目开发、持续研究、复杂工具链执行、跨文件重构等任务，应该重点考察模型是否能够长时间维持目标、自动纠错并完整交付。对于会议整理、文件处理、短周期数据分析、结构化内容生成等任务，则可以优先考虑成本更低、响应更快、交互体验更好的模型。
不要要求同一个模型承担所有任务，而是建立按任务类型选择模型的机制，必要时采用高能力模型负责规划和检查、低成本模型负责批量执行的组合方式。

### 5. 对视频、设计和内容生产任务，要分别测试创造力与执行效率
视频中的一个重要现象是：有些开发者不喜欢 Astra 6.2 的编程体验，但另一些用户却认为它特别适合交互式故事、动画生成和智能体视频剪辑。
这意味着创意工作不能简单套用通用编程排行榜。
对于电商视觉设计、AI 漫剧和批量内容生产等工作，可以重点测试：风格一致性、方案多样性、复杂指令遵循程度、细节保持能力、跨步骤协作能力以及单个合格成品的成本。
例如，让两个模型执行同一套完整任务：分析参考图、生成视觉方案、编写分镜与提示词、制作资产清单、生成修改建议。分别记录每一步是否需要重试，以及模型是否能在多轮修改后仍然遵守最初的产品、品牌和视觉约束。
这样测得的结果，比询问“哪个 AI 最强”更有直接价值。

### 6. 企业 AI 落地应优先选择高频、可验证、风险可控的业务流程
如果 OpenAI 正在加强面向普通白领和企业的产品定位，那么企业使用 AI 的机会也可能更多地出现在日常流程，而不是少数技术演示中。
最容易形成实际价值的任务通常具有三个特点：频率高、规则明确、输出容易检查。例如会议纪要、数据汇总、订单分类、标准化报告、内部知识检索和常规业务沟通。
实施时可以采用“单流程试点—衡量结果—完善权限与审核—逐步扩大规模”的路线，而不是一开始就建设庞大的全自动 Agent 系统。
对于涉及客户隐私、财务数据、生产系统和敏感业务决策的任务，应设置人工审批、最小权限、审计日志和明确的回滚机制。视频前半部分关于软件更新故障的讨论也提醒企业：自动化规模越大，越需要严格控制变更风险。

### 7. 关注模型发布的时间、版本和测试环境，不要被首发舆论过度影响
GPT-6.2 争议中一个值得记住的细节，是部分测试者使用的版本可能与最终发布版本不同。
今后在阅读 AI 测评时，应特别查看测试日期、模型具体版本、API 参数、推理强度设置、工具环境，以及是否开启了特殊的上下文压缩或智能体配置。
对于发生过重大版本更新的模型，最好使用完全相同的测试任务重新执行一遍，并与原始结果进行对照。
同时也不要把“重新测试后有所改善”自动理解成“之前所有批评都已失效”。如果某些问题在更新后仍然存在，例如代码任务提前停止或关键信息缺失，就应该继续将其视为真实缺陷。

### 8. 理解 AI 公司正在竞争的不只是技术能力，还有市场叙事与商业定位
这次视频的一个深层启示是，模型发布、产品定价、评测项目选择和广告宣传，其实可能共同服务于同一套商业战略。
如果一家公司的宣传重点从“最强编程模型”转向“最好的工作效率”，就应进一步观察它是否同步改变了 API 定价、企业功能、应用集成、销售渠道和产品默认行为。
判断这种战略是否成功，不能只看技术社区的反应，还应长期观察企业采用率、单位任务成本、续费率、真实部署规模与开发者留存。
一个模型可能不再是技术极客最喜欢的产品，却成为企业采购量最大的产品；反过来，一个在开发者社区评价极高的模型，也可能因为成本过高而难以实现大规模部署。
这两种成功方式并不相同，也不应该用单一排行榜来裁定。

## 我的点评
这期视频最有价值的地方，是把 模型能力、交互体验、系统工程和商业策略 放在同一个框架中讨论，指出 AI 竞争正在从“谁的模型更聪明”转向“谁能更可靠、更经济地完成真实任务”。主持人对早期负面评价保持审慎是合理的，因为综合评测、个人测试和 Agent 执行框架确实可能带来截然不同的结果；但把 OpenAI 的这些调整解释成主动转向企业市场，目前仍主要是一种战略推测，不能仅凭广告内容和成本变化就认定公司已经做出明确取舍。另一个需要保留的判断是：效率提升只有在输出达到合格标准时才有价值，如果模型虽然便宜却更容易遗漏事实或提前结束任务，企业可能会因为返工与人工审核支付更高的隐性成本。视频开头涉及 NSA 系统故障和 NVIDIA 高层人事的内容，尤其需要独立核实，而且不能因为多个事故在时间上集中发生，就直接推断它们具有共同的 AI 技术原因。对普通用户和企业而言，最实用的做法不是追逐每次模型发布时的舆论情绪，而是建立自己的任务测试、成本核算与质量验收体系。最终值得衡量的不是 AI 在排行榜上赢了多少分，而是它在真实场景中稳定创造了多少可验证的价值。

---

## 📝 完整文字稿

OpenAI 刚刚下载了他们最新的模特,反应不太好。但是这是关于模特的失败,还是更多关于OpenAI的策略前往的问题?《AI Daily Brief》是AI的每周节目和视频中最重要的消息和讨论。好,朋友们,我们先进一步的简介。首先,感谢今天的负责人,KPMG,Granola,Gartner和Blitzy。为了获得该节目的免费版本,请到patreon.com.aidailybrief,或者您可以订阅Apple Podcasts。如果您想要更多关注该节目,请在AIDailyBrief.ai的负责人中发布信息。

一个人认为AI的故事并不是实际上是AI的故事,而是过去周末所引起的讨论,当然是这个奇妙的门槛关闭,经过了Microsoft Outlook和FAA,一大群美国银行,现在,周末,NSA的内部信息中心。是NSA.net。NSA.net是一种安装信息系统，设计对内部识别识别的信息。有消息说,CNN说,NSA的办公室周末晚上被关闭,只与重要人员连续工作,作为维修网络。正如这里每次都说的一样,有消息说,目前,没有证据出有性暴力攻击。周末的报告中,公司说,国际保安公司，经历了连续维修,尽管有些内部系统受到影响,mission critical capabilities。

仍然完全在行动中,我们的能力，保护国家安全继续继续继续。NSA的设计，是设计以多层线的弱化,以保持行动，在计划维修或不期待的情况下。然而,对于那些在FAA和JP Morgan，都经历了巨大的凶凶,已经被警告,NSA的凶凶。可能会感觉到严重的升级,尤其是与Apple和United Airlines。的其他凶凶,这也在周末发生了。对于某些人来说,最有意义的答案，是我们正处于，一个连续的，未公开的，智能攻击，使用了传输智能技术。然而,在这种情况下,有一个答案，是关于智能,但并不是智能攻击。

A16Z的，马丁·科萨托，在他发布的文章中提到,所有这些凶凶，让我记起Y2K，当时的主要服务。是由于升级。当报告人Ashley Gold，问ONCD的，Shawn Cairncross。是否能成为，智能攻击时,他说,我们正在看到的,并且坦白说,我将期待看到更多的,是服务破坏。来自更新，和更新传输系统。这是一件事，在现实时间中发生的事,而在最后一天之内,我们将必须，通过这件事，来找到必须的系统。企业已经知道这件事，一段时间了,只是它正在发生。

Backenzie Arnold，重新发布了这件事,并提出,也许智能攻击，实际上是在智能攻击中的,但在一个比较有关系的方式。真正的关系，关于自动智能攻击，可能会引起，大量的更新,更新的更新，就是更新的失败。并提出,智能攻击，也将使得，许多这些更新，充足和允许，第一次,而且有很多，新智能组织的。试验,人们绝对可以认为，这并不是个 coincidence,即使这并不是，未公开的。智能状况。基本上,我们一直在，继续继续，继续继续，继续继续，继续继续，继续继续，每年, soul company。

将在，更新中，开始，闯入，前夕 classmates，事件任务。我们应该，可能会遇到几百次的资产攻击,但这是我预期会发生的那种东西,在那种后果中的硬化中的过程中。我当然会留意这些,看看如果这些证据改变,但目前我们继续进入我们的正常的日常NVIDIA。报告,在上星期四,陈森黄说了第一次,他在周日早上发表了一篇文章,他写,在过去一周,我受到爱和支持的朋友,业务同事和人我从未见过,谢谢大家对我和我的家人和我。和我的家人和我,这对我的世界有意义。我来到美国53年前,而成为美国人是我人生中最大的优秀和最高兴的时刻。

NVIDIA是我人生的工作,建立它成为今天的公司,与我的同事一起,是一个尊重和尊重的事。在美国,哪里不可能有一个公司像NVIDIA?我爱我们的国家,我爱NVIDIA。我没有在NVIDIA的每个人都，预料到的标准上生活,我做了我人生中的严重错误。我深恶心中犯了团队的问题。我完全拥有自己的错误,我愿意与团队合作。我愿意与团队合作,我愿意与团队合作,我愿意与团队合作。自我离开,我看到NVIDIA的工作人员、投资人、商务伙伴和客户，我看到NVIDIA的工作人员、投资人、商务伙伴和客户。

我看到NVIDIA的工作人员、投资人、商务伙伴和客户，向我提供回报,让我成为CEO。许多人继续向我提供回报,当企业选择严重的技术、市场、竞争性和，inclusion paved with villagers and internal aspects and。verbal and geopolitical dynamics.NVIDIA is a once-in-a-generation company.If the Board of Directors decides that my return is in the best。

interest of our shareholders, our employees, the company, and America,I would be honored to answer these calls and return as CEO."。The tech world was out and forced to support Jensen's return,Y Combinator founder Paul Graham did not envy the situation the Board is in,commenting,Imagine being a board member at NVIDIA considering potential。

candidates for CEO and，trying to claim with a straight face that one of the others would do a better job.The market also seemed to be voting to bring Jensen back,NVIDIA stock up by 2% in the 5 minutes after Jensen posted。

Last week, former tech executive and tech philosopher Balaji Srinivasan wrote。All Jensen Huang had to do is tweet that he wants to be reinstated as CEO and gears will start moving。Well, Jensen has now tweeted，But in the evening during the earnings call, the NVIDIA board made it clear that the gears are not turning。

The call opened with an announcement from newly appointed board chair Harvey Jones who said。The board unanimously accepted Jensen's resignation and does not intend to reinstate Jensen as CEO。Prior to the call, interim CEO Colette Kress had also shut down the idea。

saying in a CNBC interview，Jensen resigned from his position with NVIDIA and the board accepted his resignation。The board has determined that they will not reinstate Jensen。And that is our statement and what the board has decided to do。

We want to think right now about growing our business。We want to grow in terms of everything that we need to do with our employees, our customers, our shareholders。And that is where we are going to focus moving forward。And yet, later in the evening, Semaphore delivered a scoop from inside the boardroom。

Reporting that a faction of NVIDIA is going to be reinstated as CEO。The board members are pushing for Jensen's return。Jensen has also reportedly spoken with at least one board member about returning。Doing so prior to his Tuesday morning post。

According to people familiar with the matter。Three board members are vehemently opposed to Jensen's return。But where the other seven stand isn't as clear。Now, as to the substance of the earnings report。NVIDIA delivered another extremely strong quarter。

They beat revenue estimates with 103% annualized growth。And raised projections for the fourth quarter to $130 billion in revenue。CEO Kress also raised forecasts out to 2028。Adjusting growth expectations from 70 to 75%。Kress projected an air of confidence。

Ending the call by stating，Our supply is growing。Our customers and our partners are with us。And employees are committed，We've got this。The stock was up 4.5% in after-hours trading。To reach a new high for the post-Jensen period。

Wedbush securities analyst Matt Bryson was satisfied with what he heard, commenting。Colette is exuding the same confidence that you heard from them last quarter。However, he acknowledged the skeptics, saying。I don't know if it changes people's opinions。

NVIDIA themselves seem to be changing their opinions, but they don't change people's opinions。NVIDIA themselves seem to be changing their opinions, but they don't change people's opinions。On China for some pretty understandable reason。

During the call，Kress announced that NVIDIA would no longer be selling。AI chips to China，Even the ones that have government approval。It's unclear how many H-200s have actually。Shipped, since they were approved by the Trump Administration earlier in the year。

but Kress said。Our guidance does not have any licensed。Hopper data center products included。And we are no longer shipping licensed。Hopper data center products to China。Important to note that this earnings report。Does not cover the events of the past few weeks。

So we don't know yet how much revenue will be lost。From shutting down smuggling routes into China。From shutting down smuggling routes into China。From shutting down smuggling routes into China。So we don't know yet how much revenue will be lost from shutting down smuggling routes into China。

他们还没有完成他们的公开的SEC签署,这也跟着收益电话的关系,表明它将在未来的周期中签署,而主席Harvey Jones也承认了。NVIDIA现在正在生活在一个世界中,在我们的市场中,国际安全动力正在进行巨大的改变。下一个总裁将必须非常小心地，游过这些水域。这件事,无论如何,继续感觉不太完善。不过,目前,这将是，主题的主题。接下来,是主题的主题,也许是我从来没有看到过，如果您是在一家企业中的AI,您已经知道现在的缺点。不是能力,而是执行。

这就是为什么KPMG's You Can With AI，在新一季的《You Can With AI》中。举行与领导人,例如，Emma的Sorojit Chatterjee,Mahabeeb of Writer,McKesson CIO Ellery Fisher,以及其他专注于实际执行。什么是正在行动的,什么不是,以及它实际需要从飞机，到实际的执行影响,包括策略,数据准备,管理,工作,和价值。www.kpmg.us，slash AI podcasts，That's www.kpmg.us。

slash AI podcasts，You're in back-to-back meetings all day,you're trying to stay present,but you're also worried you'll forget the decision,the action item, the important next step.This is a scenario that we absolutely live here。

at the AI Daily Brief,given how fast things move and change,and how quickly we're evolving everything that we do.That's where Granola comes in.Granola is an AI-powered notepad for meetings.You jot down rough notes like you always do,Granola transcribes and turns them into clear,useful notes when the meeting ends.

No bots joining your calls, no distractions,just a clean notepad that helps you focus.During or after the call, you can chat with your notes.Ask Granola to pull out action items,help you negotiate, write a follow-up email,or even coach you using recipes,which are pre-made prompts.

Once you try it on a first meeting,it is very hard to go without.Head to granola.ai slash ai daily，and use code ai daily。to get 100% off for 3 months for new users.That's granola.ai slash ai daily，and code ai daily。to get 100% off for new users for 3 months.

When it comes to AI risk,C-suite leaders have serious questions.Can your cybersecurity keep pace，with AI-powered threats?As threats expand beyond IT,are your physical assets safe?Do you trust your AI vendors to deliver value。

without taking your proprietary data?Are you prepared to handle swarms of AI agents?Find out how they can help.Visit them at gartner.com slash ai，to learn more.Here's why most legacy modernization projects fail.The AI doing the work，can't understand code bases at scale.

It sees a small slice of context,examines syntax,and misses years of decisions。distributed across the global application ecosystem.Blitzy solves this the way it solves everything.Grounded in your code before any migration begins,Blitzy's agents reverse-engineer。

the entire legacy system into a persistent knowledge graph.Every dependency, every constraint,every piece of tribal knowledge。that used to live in one engineer's head.From that understanding,Blitzy autonomously executes language migrations,and integrates it end-to-end.

One Blitzy customer modernized，a $10 million monolithic insurance stack。in 16 weeks against a 137-week baseline。with coding agents.That's 9x compression.Retire technical debt while accelerating your roadmap.See how at blitzy.com.

That's B-L-I-T-Z-Y dot com.Welcome back to the AI Daily Brief.Today we are doing one of my favorite types of episodes,although this one has a bit of a different flavor.One of the big questions for this week。was whether OpenAI，would actually try to drop some sort of。

spoiler model in advance of the Anthropic IPO.Now, spoiler model itself，might be an overstatement,in that even without any sort of desire。to spoil anything for Anthropic,OpenAI has felt due for an update for a while now.

Well, on Tuesday we did get a new model.Two, in fact.GPT-62 Astra and GPT-62 Sol.And unlike the usual excitement,we got some of the worst。first impressions that I have ever，seen from a model.And I'm not just talking about the GPT-5 era,when people were angry for other reasons,like GPT-40 being deprecated.

I'm talking about posts like this one。from Matt Schumer who wrote,I will not be writing a full review。of GPT-62 Astra and Sol.I had a terrible experience testing them.They were essentially unusable.I do not recommend these models.

So, what is going on here?Are these models as bad as the early testers say?Or, does this show an increasing，divide between what types of uses。OpenAI is trying to build for,relative to what the early adopter set cares about?

Now, in my estimation,OpenAI is telling a pretty clear story。of how they see these models.To quote their announcement post,super efficient and built to perform。where it counts, the real world.You can also see this sort of focus，in what they emphasize in the announcement post.

They lead with agents last exam，and terminal bench science,rather than the sort of coding benchmarks。that had been right at the top for pretty much。every release for the last year.And even when they get to code,the major selling point is still about cost.

On the artificial analysis intelligence index,both model releases。were a slight improvement.GPT 6.2 Sol increased its score，by 2 points from 55 to 57,pulling even with GPT-6 Astra,but still behind Opus 5-5,Gemini 4 Carbon, and Fable 5-2.

GPT 6.2 Astra added 5 points,rising to 62,which puts it in second place behind Fable 5.2.AA noted that OpenAI models，now have solid control。across most of the Pareto frontier.They offer an extremely competitive model。across the mid-range price points,offering a little more intelligence。

at the premium price point,and Meta outperforming with the cheapest group of models.AA's measurement of cost per task，confirmed that GPT-6-2 Astra。would be cheaper in the real world.The new version completed the benchmark run。

at $4 per task compared to $6.24，for GPT-6 Astra.That is a 35% cost reduction,implying that the model is a little more。token efficient as well as seeing，a price reduction on per token cost.GPT 6.2 Sol saw something similar,completing the run at $1.01 per task,and $1.27 per task.

And when it comes to cost efficiency,certainly OpenAI appears to be。opening a big gap with，anthropic models.Even only on high settings,Fable 5.2 is still more than twice。as expensive as GPT-6-2 Astra on max settings,and on high settings Astra's cost。

is closer to Opus.6-2 Sol on max settings is less than a third。of the cost of Opus 5.5 on high settings,meaning that even though these models。are in the same size category，and compete on the same workflows,A.A. also uncovered。

a huge red flag for the model release,which basically set the tone。for the narrative.Both Astra and Sol regressed，on the A.A. coding agent index.6.2 Astra kept the same overall score。and ranking,while 6.2 Sol dropped，three points to slip behind。

Kimi 3.1 and 6.1 Terra in the rankings.A.A. said that Sol's drop，was driven by a regression on。Sui Atlas,where the new version，is more likely to omit key facts。in its responses.A.A. also noted how much，these first set of negative takes。

were driven by the modelactually being bad。versus being worse at the only thing。that the early testers caredabout,which was coding.Now, when it came to those early testers,it was not just Matt Schumer。talking about their bad experience testing them.

Spawn founder Jacob said，same, not good.Dan Schipper from Every wrote,We've been testing them for the last few weeks,and unfortunately, these models aren't great.No one on our team loved Astro 6.2.We have a 30-person team at Every,and we put them through their paces。

on our real-world tasks,from coding to writing。to design to knowledge work.No one on our team who tried it，switched back to it.Specifically, Dan writes that they found that。6.2 Astro was a step back from Astro 6 on writing.

He adds,6.2 appears to have been trained。to be extremely concise and actionable,so much so that its writing is hard to understand,and it gives short answers。when long answers would be appropriate.On coding, while they found that its performance。

to Astro 6 in general,Dan added that,In real coding tasks,Astro 6.2。seemed to stop too early frequently,making it quite frustrating to use on end-to-end builds.And on design,they said while it has good default design instincts,it struggles to get out of those defaults。

and vary its designs,resulting, they said,in output that has a noticeable。house style.One of the longest negative reactions。came from developer and entrepreneur Theo,who titled it,Why I Hate GPT 6.2 Astra.And to be fair,to Theo,he won.

I do believe that he was not trying to be negative。for the sake of negativity,and was genuine。when he said that he hoped that OpenAI。would use the feedback to make better models.But he really did not like this model,giving entire sections of complaints。

to things like,it speaks in tongues，that only 6.2 Astra understands,it runs in loops and goes nowhere.His summary,this model is clearly super smart,it is insufferable to work with on real projects.It feels like it just lives in its own world。

and randomly decides what parts of its brain。are shown to us.Professor Ethan Mollick called the model。very uneven and weird,and said it was the first time。since GPT 4.5 that a frontier release。from OpenAI was not a clear step forward.

But of course,these weren't the only takes.Ash said,a bit confused by some of the negative reactions.When you experiment with the model for a while,it is very strong,especially around computer use workflows.It's been my main powerhouse，agentic video editing partner these past few weeks.

Claire Vo shared an example of an interactive。storybook that she built,and said，Astra 6.2 wins over Opus and Fable。on one thing,image generation and code。for animation.It's delightful.Josh Pertel wrote,Days like this,I genuinely feel like I live in。

a different universe from the rest of the world.Saw ubiquitous 6.2 hate,it's over for。OpenAI,yada yada.Ran the，highest signal auto research bench,and。6.2 Sol and Astra are absolute monsters.Responding to that post from Ash,Alex Finn wrote,I agree,I'm very confused about the negative response.

Have had Astra 6.2 on some，incredibly complex tasks,and it only used。like 2% usage.He also，was one of the folks who went out of his way to talk。about other dimensions rather than just raw。capability.Discussing its performance。

on his personal benchmark test,he said,Astra 6.2 finished the benchmark。in a third of the time for a third of。the price at a quarter of the tokens.The panicking influencers never seemed to。take into account efficiency and price.

This is a great model.Zwen on X wrote,Everyone's saying，OpenAI GPT 6.2 flops.Here's my honest feedback.If quality is all you care about,then yeah,it flopped bad.But for how efficient。it is and plus the quality,I'd say it's a。

win.He then went on to share some of the problems。that he had found,but overall,he landed on this。idea.In my opinion,he wrote,The future of AI should focus on。efficiency more than quality.I don't think it's。sustainable if the price just keeps going up just to get your。

job done better.Overall,I don't，think it flopped.With the price to output。ratio,I'll take this as a win.And Hayter thinks that this is a very specific。set of decisions from OpenAI.He，writes,The efficiency gain with Astra and。

Sol 6.2 is massive.I had said，before that this was OpenAI's real edge right now,and they seem to be doubling down on it.And I think it's worth remembering,that for some。time now,there has been this，subtle but clear distinction in。

the type of interaction pattern that OpenAI。models versus Anthropic models have been。pursuing.You might have heard me say things。before,like people finding that，Anthropic models in particular in the Fable class。were the types of things that they give an entire。

assignment to,and then just go off on。their merry way and wait for Fable to get it all done.Whereas OpenAI models，are still a little bit more tuned for the close。sort of back and forth collaboration.This。may just be an extension of that,but。

one that is perhaps a little bit worse by comparison。because of how good Opus 5.5，is on both of those dimensions of the。competition.There also is a question。of how much the negative experience was not。just about the model,but about the harness as well.

Claire Vo again writes,The negative Astra reviews are simply a result。of the model plus harness being frustrating to work。with,and not that impressive,especially on the。tail of Fable 5.2.Pietro Sciorano said,I've been testing。

Astra 6.2 and feel it's getting an unfair response.From my testing,most of the issues were with。the harness.Once I removed that,I would。feel it was flying.Tibo from the OpenAI。team even posted,One of the funny，reasons for the difference in vibes between the。

influencers and the crowd today on 6.2 Sol and Astra。is that we gave a few folks access a while。ago,and then made a lot of changes in the last。three to four days,and I'm pretty sure no。retesting was done within those days,and the videos。

were produced last week.Although Token。Gremlin pointed out,What's the point of giving。people early access to GPT-6.2 Astra,letting them spend hours testing it,and writing。hugenegative reviews,only for OpenAI。to literally change everything and improve the model。

just three to four days before launch? That was an。insane act of self-sabotage.Now,Theo did go retest it，with that in mind,saying,I took this。to heart and spent the last few hours doing another。deep dive,but where he landed was still,Things are better than when I tested,but in。

my opinion,still directionally very bad.I think for most of our purposes here,for the average person who's listening to this show,it's probably worth an extra grain of。salt.It is certainly the case，that under no circumstances does this seem to be。

a slam dunk,nor does it appear to，be anywhere near an error-defining release.Instead,it just feels like a very，incremental release,with some very。specific decisions,that either a，don't work in general,or b。tune the model in ways that made it less useful。

for certain people's use cases.Every time a new model comes out,I beat。the drum of needing to go test it yourselves,and。I think that is more the case than ever when it comes to。6.2.Now,in terms of，the strategy relative to Anthropix IPO,I'm not exactly sure what the thinking。

here is.It certainly wasn't the，case of,as some have claimed,OpenAI。trying to sabotage Anthropix.There's no way that they thought that this model was going to。steal all the thunder from Anthropix,especially。after they'd released Fable 5.2.

My instinct is that,if anything,it，was a little bit more defensive,feeling。that having released a model very recently,that。people were still trying to wrap their heads around,as everyone was talking about models again because of。

the IPO,was better than looking like they were。running scared by not having released anything。for such a big period of time.There is。one more possibility,though,that has。to do with more explicitly starting to draw。contrast between them and Anthropix，for the post-IPO period.

One final area of critique from the，launch is the video that launched alongside。it.It's a short two-minute，film that shows a bunch of people in white-collar。jobs having forgotten or not realized。that their dopey bosses had asked something。

specific of them,and with the pressure of having to。get something done in less than a minute,are able to use。Astra to do that important piece of work.Mo on X wrote,What a great mockery of humanity this video。makes.It's hard to overstate how，completely lost OpenAI is.

Notion's Brian Levin wrote,A profoundly sad vision of the future.With Zack Trader responding and summing up the video,we help your incompetent people fake it.Shawn Wang aka Swick，from Latent Space and AI Engineer Summit said,The fact that nobody with decision-making。

power saw this coming a mile away and。vetoed the 6-2 Astra ad is my primary。critique of the Astra launch.And basically what people are saying is that。really is the way that we want to promote this。incredibly powerful new tool,which，could be unlocking the power to do things that were never。

before imaginable,as a way to not，really work that hard,and get everything done for。your dumb white-collar job at the last minute?Is that really how we want to tell the story?And on the one hand,the highfalutin，part of me resonates with that critique.

But here's two counterpoints.First of all,we might be thinking too deeply.The team that produced this video might。have just been wanting to have some fun by taking。an office space style setting,which by the way。is reinforced with the fact that all of the computers。

in it are very 1990s,big chunky，laptops,and big thick classic。desktops,with the classic archetype，of the Lumberg-style boss,and that's all。there is to it.In other words,the job of the。ad was not to be a profound meditation on the nature。

of work,but to make people laugh for 90 seconds。before going on with the rest of their day.But there is a second possibility as well.If OpenAI is exploring，tuning down some of the emphasis。on coding,and tuning up some of the，emphasis on other types of professional tasks,while also coming hard at the sort。

of cost efficiency considerations that。enterprises are increasingly focused on,they might be trying to start to carve their own narrative。space in the overall enterprise AI market.In other words,rather than just，competing head-to-head with Anthropic on those。

coding and engineering style use cases,they're kind of saying with this ad and this launch,we've got something for you and for your boss.For you,it allows you，to do the dumb,annoying,busy work much faster,and for your boss,they get all。

the cost efficiency that all of these token cap。conversations are leading to.Now,once again,I think it's entirely possible that even with that。analysis,I'm wildly overthinking it,but if。there is any lesson and takeaway from this model,it's that perception is in the eye of the。

beholder,and it is very much worth doing。your own testing.For all of my workflows。that already take advantage of OpenAI models,I will。be switching over,and I will let you know what I find.For now,though,that is going to do it for today's。

AI Daily Brief.Appreciate you listening。or watching,as always,and until next time,Peace!
