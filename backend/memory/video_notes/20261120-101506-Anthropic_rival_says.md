# Anthropic 竞争对手称：企业大多数情况下可以不使用昂贵的前沿 AI 模型

- 来源链接：https://techcrunch.com/2026/11/19/anthropic-rival-says-companies-can-mostly-skip-the-pricey-models/
- 作者：Connie Loizos
- 提取时间：2026-11-20 10:15
- 类型：网页文章
- 发布时间：2026-11-20 00:26
- 原标题：Anthropic rival says companies can (mostly) skip the pricey models | TechCrunch
- 标签：开放模型、AI基础设施、模型成本、企业AI、数据安全

## 🤖 AI 分析

## 一句话概括
AI 基础设施公司 Fireworks AI 联合创始人 Chenyu Zhao 认为，随着 DeepSeek 等开放权重模型与顶级闭源模型的能力差距迅速缩小，企业不必为所有 AI 任务支付高昂的前沿模型费用，而应通过开源模型、私有数据定制、智能模型路由和按任务计算成本，建立更便宜、更高效、更自主的 AI 系统；但 Fireworks 自身遭遇的数据泄露事件也说明，成本优势必须与数据安全和客户信任一起考量。

## 背景与主题
文章来自 TechCrunch，围绕 Fireworks AI 联合创始人 Chenyu Zhao 在芬兰赫尔辛基 Slush 创业大会上的现场访谈展开，讨论企业是否真的需要长期依赖 OpenAI、Anthropic 等公司的昂贵前沿模型，以及开放权重模型能否成为更经济、更可控的替代方案。
按照文章的叙述，访谈发生在 Anthropic 完成创纪录 IPO 的同一天：一边是投资者对顶级 AI 实验室的热情持续高涨，另一边是创业者们讨论如何利用开源技术减少对这些巨头的依赖，两者形成鲜明对照。
Fireworks 的核心业务是帮助 Uber、Shopify、Notion 等企业运行、优化和定制 AI 模型，让企业能够利用自己的数据打造专用 AI 能力，而不只是直接购买通用模型的 API 服务；Zhao 认为，这种模式具有成本、性能和商业差异化优势。
不过，文章并非单纯宣传开源模型，也详细追问了 Fireworks 最近发生的两起安全事件、Notion 终止合作、约 15 万名 Uber 司机信息泄露等问题，并将其放在 AI 基础设施行业融资火热、竞争加剧的大背景中考察。

## 核心观点

### 1. 企业大多数 AI 任务不需要最昂贵的前沿模型，专用模型可能才是更合理的选择
Chenyu Zhao 的核心判断是：最先进的通用智能，不等于每一个企业任务的最佳解决方案。 OpenAI 和 Anthropic 致力于构建能力广泛的通用智能模型（General Intelligence），这些模型需要在推理、写作、编码、复杂规划等不同场景中保持高水平表现，因此训练和运行成本都很高。Fireworks 则采取另一条路线：使用通常更小、更便宜、更快速的开放权重模型，再结合企业自己的业务数据进行专门优化，让模型在特定任务上达到足够好的表现。企业如果只是执行简单计算、标准化信息处理、重复性问答等工作，就没必要每次都调用最昂贵的模型。背后的商业逻辑是，企业应该为任务所需要的能力付费，而不是无差别地为模型的最高能力上限付费，否则很多开支实际上是为根本没有使用到的能力买单。

### 2. 真正的竞争优势来自企业专属 AI，而不是所有人都能购买的同一个模型
Zhao 将 Fireworks 定义为一个 specialized intelligence platform（专业化智能平台），强调企业不应该只依赖外部 AI 巨头提供的标准化能力。他特别指出，如果一家公司的 AI 产品只是调用 Anthropic 的 Opus 或 Sonnet，那么这种模型能力并不能构成真正的差异化，因为竞争对手也可以购买同样的服务。Fireworks 希望企业利用自身的数据、流程和专业知识，对开放模型进行定制，使 AI 系统能够更准确地理解具体业务，也让竞争对手更难直接复制。这不仅是技术选择，也涉及商业控制权：企业究竟是拥有一个经过自己训练和优化的 AI 系统，还是始终依赖少数大型供应商提供的能力。Zhao 用一句话概括这种理念：企业应当拥有自己的 AI，而不是被大型 AI 集团牵制，其深层含义是把 AI 从可以随时采购的通用工具，逐渐变成企业内部的专有竞争能力。

### 3. DeepSeek 改变了开放模型的竞争格局，开源与闭源模型的差距已经显著缩短
Zhao 表示，如果是在几年前，他会认为开放模型的能力相比最前沿的闭源模型落后约一年到一年半。然而，DeepSeek 的出现以及随后大量优秀开放模型的涌现，迅速改变了这一判断。按照他的估计，目前开放模型与顶级前沿模型之间的时间差距最多约六个月，更可能接近三个月。这意味着一家企业即便不使用最新发布的顶尖闭源模型，也可能获得几个月前只有领先 AI 实验室才能提供的能力，而对大量普通业务而言，这种能力已经足够使用。其背后的变化是，先进模型能力的扩散速度越来越快，曾经需要付出高额溢价才能获得的能力，可能很快就会被价格更低、部署方式更灵活的开放模型追赶。需要注意的是，三到六个月属于 Zhao 的行业判断，不是文章提供独立评测得出的普遍结论，不同模型和任务之间的差距仍可能很大。

### 4. 企业采用前沿模型与开放模型的最佳时机不同，规模化是重要转折点
Zhao 并不认为企业在产品开发初期就应该完全放弃顶级闭源模型，因为 OpenAI、Anthropic 等品牌具有较高知名度，而直接使用能力最强的模型可以降低早期产品开发的不确定性。在尚未找到产品市场契合点（Product-Market Fit，PMF）时，创业公司的首要问题通常是验证用户是否需要产品，而不是把每一次模型调用成本压到最低。一旦用户量增长到 1 万或 10 万量级，并且每月 Token 支出达到 1 万至 10 万美元，模型成本就会从不太重要的技术费用转变成影响经营利润的核心变量。这个阶段，企业已经有较稳定的使用场景、真实用户数据和任务分布，更有条件通过开放模型、定制优化以及基础设施调整来降低成本。因此，Zhao 提出的是一种分阶段策略：先用最可靠的模型找到市场，再在业务规模化后优化模型经济性，而不是一开始就追求最低成本。

### 5. 未来更可能是前沿模型与开放模型并存，而不是某一方彻底取代另一方
Zhao 认为，AI 市场未来会形成一个 two-model world（双模型并存的世界），前沿闭源模型与开放模型会长期同时存在，各自承担不同类型的工作。复杂的高层规划、需要高度通用推理能力的任务，可以使用能力最强的前沿模型；基础计算、常规处理和明确限定的工作，则可以交给更小、更便宜的模型。这种分工推动了 Routing（模型路由） 技术的发展，即根据不同请求的难度、价值和准确率要求，自动选择合适的模型。Zhao 特别强调，企业正在从关注 cost per token（每 Token 成本），转向关注 cost per task（每项任务成本），因为真正重要的不是单次调用有多便宜，而是完成整个业务任务最终需要花多少钱。一个价格便宜但经常答错、需要多次重试的模型，最终未必比昂贵但一次成功的模型经济，因此模型选择应综合考虑准确率、调用次数、延迟和任务完成效果。

### 6. 使用专有模型可能让企业支付双重成本：既付费，也可能暴露自己的商业知识
文章提到，Microsoft CEO Satya Nadella 曾在 7 月警告，企业使用专有 AI 模型时可能承担两种代价：第一是直接支付模型服务费用，第二是在使用过程中暴露自己的知识和经验（Know-how）。后者并不一定意味着模型供应商直接获得企业全部数据库，而是企业为了得到准确答案，可能需要在 Prompt 中输入商业流程、内部判断标准、技术细节、客户信息或其他有价值的背景知识。大量这样的交互可能涉及企业独特的经营方法，因此数据控制权和知识保护逐渐成为企业选型时的重要因素。Fireworks 提供的模式是让企业在开放权重模型上加入自己的数据，并对模型及其运行方式拥有更大的控制权，从而降低对单一大型模型供应商的依赖。不过，使用开放模型并不自动等于数据完全安全，是否真正掌握数据仍取决于部署地点、云基础设施、存储策略和安全管理方式，Fireworks 后续的安全问题恰好证明了这一点。

### 7. Fireworks 的两起安全事件暴露了 AI 基础设施供应商的重大风险
虽然 Fireworks 主张企业使用更自主、更安全可控的 AI 系统，但公司在文章所述当年秋季披露了两起安全事件，给这一主张带来了明显压力。第一起事件中，攻击者获取了部分客户账户以 Secret 形式存储的 API Keys 和 Tokens，这类凭证一旦被盗，可能被用于未经授权的模型调用和算力消耗。第二起事件涉及攻击者突破 Fireworks 的云服务提供商环境，进一步进入开发系统，并窃取部分客户数据，包括账单记录和某些数据集。Zhao 表示，这类攻击的一项重要动机是 LLM Jacking（大语言模型资源盗用），即黑客寻找 AI 服务中的 API 凭证，再通过非法市场转卖模型调用额度或算力资源。事件说明，AI 基础设施公司不仅需要保护模型本身，还必须保护云环境、开发系统、身份凭证以及客户数据，否则其技术和成本优势很容易被安全事件抵消。

### 8. “零数据留存”并非覆盖所有 AI 服务，推理与批量处理之间存在关键区别
Fireworks 宣称，其在线推理流量实行 Zero Data Retention（零数据留存） 政策，即不会长期保存用于即时推理的请求数据，而 Zhao 表示目前没有证据显示这项承诺遭到破坏。但 Notion 的数据泄露引发了一个重要疑问：既然公司承诺不保留数据，为什么攻击者还能获得部分 AI 聊天记录？Zhao 解释，Notion 使用的是 Batch Prediction（批量预测） 服务，客户需要主动上传数据集，而这些数据会以静态存储（Data at Rest）的形式保存在系统中，因此批量服务从性质上就不属于零留存服务。换句话说，实时推理服务是否留存输入数据，与批量任务是否需要存储上传数据，是两个不同的安全问题。Fireworks 表示正在把有关服务迁移到在线处理流程，以便只在必要时间内保存数据，这也提示企业：不能只看供应商宣传的安全口号，必须逐个确认不同产品、不同数据流和不同存储阶段的实际政策。

### 9. 安全事故已经影响客户信任，技术优势并不能保证企业客户持续合作
这次安全事件已经造成了具体后果：Notion 表示，受到影响的是不到 1% 工作区的 AI 聊天记录，但公司仍然选择切断与 Fireworks 的连接。Uber 则确认，约 15 万名司机的姓名、地址、出生日期及驾驶执照号码通过某个供应商遭到窃取，TechCrunch 将该供应商识别为 Fireworks。访谈中 Zhao 还提到，Notion 和 Cursor 等客户已经公开谈及相关影响，但他没有进一步披露所有受影响客户，也没有详细回答是否因此流失了其他客户。Zhao 强调受数据影响的只是客户中的一小部分，但对于企业客户而言，受影响比例小并不必然意味着风险小，尤其是涉及身份信息、内部聊天和业务数据时。Fireworks 接下来不仅需要修复漏洞，还必须重新建立客户对于其安全能力、风险透明度和服务可靠性的信任，说明 AI 基础设施市场最终比拼的不只是模型速度和价格，也包括长期交付能力与信任成本。

### 10. AI 基础设施赛道正吸引大量资本，但开源与前沿模型生态并非完全对立
文章提到，Fireworks 在当年夏天获得投资者给予的 175 亿美元估值，并据报道正在初步讨论新一轮融资，不过 Zhao 拒绝评论。其竞争对手 Together AI 和 Baseten 也在此前几个月宣布了大型融资，表明资本正在追逐帮助企业训练、定制和运行 AI 模型的基础设施公司。另外，Palo Alto Networks 宣布将以 45 亿美元的全股票交易收购 Applied Compute，这家创业公司由前 OpenAI 研究人员创立，成立仅约一年，主要帮助企业基于自己的数据训练和运行定制 AI 模型。与此同时，Zhao 对 Anthropic 上市保持乐观，甚至表示自己可能当天晚上就买入一些股票，因为他相信十年后 AI 的使用规模将远超现在，而这需要巨额资本支撑。文章还提到 Nvidia 自 2024 年起投资 Fireworks，Zhao 预计 Nvidia 将继续支持开源及 Nemotron 模型，说明其商业判断不是“闭源必然失败”，而是认为 通用前沿模型、开放模型、算力厂商和企业定制平台将共同构成一个多层次的 AI 产业生态。

## 关键事实与数据

### 一、核心公司、人物及定位

| 名称 | 身份或业务定位 | 文章中的关键信息 |
| --- | --- | --- |
| Fireworks AI | 企业 AI 模型运行与定制平台 | 重点支持开放权重模型，帮助企业降低成本、优化性能并利用自有数据定制 AI |
| Chenyu Zhao | Fireworks 联合创始人 | 本次 TechCrunch 访谈对象，曾在 Google 工作约十年 |
| Lin Qiao | Fireworks 联合创始人 | Zhao 提到的创业伙伴之一 |
| Dima Dzhulgakov | Fireworks 联合创始人 | Zhao 提到的创业伙伴之一 |
| Anthropic | 前沿 AI 模型开发公司 | 旗下有 Opus、Sonnet 等模型；文章叙述其在访谈当天完成创纪录 IPO |
| OpenAI | 前沿 AI 模型开发公司 | 与 Anthropic 一同被视为通用智能模型的主要开发者 |
| DeepSeek | 开放模型领域的重要参与者 | Zhao 认为其出现显著加快了开放模型追赶前沿模型的速度 |
| Microsoft | 科技公司 | CEO Satya Nadella 警告企业使用专有模型可能付出资金和知识两种成本 |
| Nvidia | AI 算力与模型生态企业 | 自 2024 年起投资 Fireworks，并支持开放模型生态 |
| Together AI、Baseten | AI 基础设施公司 | Fireworks 的竞争对手，均有大型融资动态 |
| Applied Compute | 定制 AI 模型基础设施公司 | 由前 OpenAI 研究人员创建，成立约一年即出现巨额收购交易 |
| Palo Alto Networks | 网络安全公司 | 宣布以股票交易方式收购 Applied Compute |

### 二、关键数字、时间与金额

| 指标 | 具体数据 | 说明 |
| --- | --- | --- |
| Zhao 在 Google 的工作时间 | 约 10 年 | 创业之前长期从事 Google 相关业务 |
| 曾管理的工程团队 | 50 人 | 位于 Google Cloud Vertex AI 相关业务 |
| 几年前开放模型的落后幅度 | 12—18 个月 | Zhao 对过去技术差距的估计 |
| 目前开放模型的落后幅度 | 最多约 6 个月，可能接近 3 个月 | Zhao 的个人判断 |
| 企业开始考虑开放模型的用户规模 | 10,000 或 100,000 用户 | Zhao 举出的规模化阶段例子 |
| 每月 Token 支出参考范围 | 10,000—100,000 美元 | Zhao 认为值得重新评估模型成本的区间 |
| Fireworks 估值 | 175 亿美元 | 文章称投资者在当年夏季给予的估值 |
| Applied Compute 收购金额 | 45 亿美元 | 由 Palo Alto Networks 宣布 |
| 收购支付方式 | 100% 股票 | 并非现金收购 |
| Applied Compute 创立时间 | 约 1 年前 | 相对于文章时间 |
| Nvidia 投资 Fireworks 的起始时间 | 2024 年 | 文章明确提及 |
| Notion 受影响工作区比例 | 不到 1% | 涉及部分工作区的 AI 聊天记录 |
| Uber 受影响司机数量 | 约 150,000 人 | 身份信息通过供应商泄露 |
| Fireworks 已披露安全事件 | 2 起 | 发生在文章所述当年秋季 |
| Zhao 对 AI 行业的展望周期 | 10 年 | 认为未来 AI 使用规模将发生巨大变化 |

关于数字的两点说明：
第一，1 万至 10 万用户、每月 1 万至 10 万美元成本，是 Zhao 在访谈中举出的参考情境，不是经过统计验证的行业统一转换门槛。
第二，175 亿美元是投资者给予的估值，45 亿美元是拟议收购交易价值，两者不能直接等同于企业收入、利润或实际支付现金。

### 三、Fireworks 的具体客户及事件
**1. Uber**
- 曾使用 Fireworks 提供的 AI 基础设施服务。
- Uber 表示，约 15 万名司机的信息通过某个供应商泄露。
- 被盗信息包括：姓名、地址、出生日期和驾驶执照号码。
- TechCrunch 将相关供应商识别为 Fireworks。
- 文章未披露具体攻击持续时间、全部后续损失或每名受影响司机的实际损害情况。

**2. Notion**
- 是 Fireworks 已知的企业客户之一。
- 公司表示，不到 1% 工作区的 AI 聊天记录受到数据泄露影响。
- Notion 使用过 Fireworks 的批量预测服务，需要上传并存储数据集。
- 事件发生后，Notion 已断开与 Fireworks 的连接。
- 文章没有说明 Notion 是否将来会恢复合作。

**3. Shopify**
- 被列为 Fireworks 的客户之一。
- 原文没有披露其具体使用方式、合同金额或是否受到安全事件影响。
- 不能因为 Shopify 出现在客户名单中，就推断它也是此次数据泄露的受害者。

**4. Cursor**
- Zhao 在谈到受影响客户时提到 Cursor。
- 他表示 Notion 和 Cursor 已经公开谈及相关情况。
- 原文没有给出 Cursor 的受影响数据规模、具体损失及合作状态。

### 四、两起网络安全事件的区别

| 维度 | 第一起事件 | 第二起事件 |
| --- | --- | --- |
| 主要攻击对象 | 部分账户保存的 API Keys 和 Tokens | 云服务商环境及开发系统 |
| 进入方式 | 获取被保存为 Secrets 的访问凭证 | 突破云服务商后进一步进入开发系统 |
| 受影响资产 | API 调用密钥和令牌 | 客户账单记录、部分数据集等 |
| 主要风险 | 非授权调用模型、盗用计算资源 | 客户数据泄露、隐私和商业信息暴露 |
| 公司解释 | 攻击与 LLM Jacking 动机有关 | 强调部分批量服务需要静态存储数据 |

需要特别区分：访问凭证被盗和客户数据被盗，是性质不同但可能相互关联的两类风险。 前者主要涉及调用权限和资源滥用，后者可能直接触及隐私、商业秘密和合规责任。

### 五、文章提到的关键技术概念
- Open-weight Models（开放权重模型）：模型权重可以根据相应许可证获取和使用，企业有机会自行部署或优化。开放权重不必然意味着训练数据、训练代码和许可证全部开放，也不意味着没有使用限制。
- Frontier Models（前沿模型）：代表当前先进能力水平的模型，在复杂推理、通用任务等方面具有竞争力，通常成本较高。
- Specialized Intelligence（专业化智能）：通过特定行业、企业或任务的数据与优化方法，让模型更适合有限但有价值的业务场景。
- Product-Market Fit，PMF（产品市场契合）：证明产品能够满足明确的市场需求，是作者讨论模型选型时机的重要分界点。
- Model Routing（模型路由）：根据任务的不同要求，将请求发送给不同能力、成本或延迟等级的模型。
- Cost per Token（每 Token 成本）：衡量模型调用单位文本量的费用。
- Cost per Task（每任务成本）：衡量完成一项实际任务的总体成本，需要考虑重试、质量、延迟等因素。
- Zero Data Retention（零数据留存）：在规定的数据处理流程中不长期保存客户的请求数据，具体范围取决于服务类型和合同条款。
- Batch Prediction（批量预测）：客户一次上传一批数据，由服务平台异步执行模型处理，可能涉及数据静态存储。
- Data at Rest（静态存储数据）：位于数据库、文件系统或其他持久化存储中的数据。
- LLM Jacking（大模型资源盗用）：攻击者窃取或滥用模型 API 密钥、令牌及访问权限，以未经授权的方式消耗或转卖推理资源。
- Nemotron：Nvidia 的 AI 模型系列，文章将其作为 Nvidia 支持开放模型生态的例子。

### 六、文章涉及的资本与产业事件
Anthropic IPO
文章叙述 Anthropic 在访谈当天完成上市，并称其为有记录以来规模最大的 IPO。采访者追问，如果 Anthropic 继续保持少数巨头主导的优势，或者未来逐渐失去竞争力，其估值应当如何看待。
Zhao 的回答没有直接给出具体估值，也没有给出市盈率、收入倍数或其他估值方法，而是表示自己倾向于长期看好 AI 使用量增长，并可能购买少量 Anthropic 股票。
Fireworks 的融资前景
- 文章称公司在当年夏天获得 175 亿美元估值。
- 有报道称公司正在初步讨论新一轮融资。
- Zhao 拒绝评论融资传闻。
- 原文没有给出拟融资金额、正式完成时间或下一轮估值。

Applied Compute 的收购
- 买方为 Palo Alto Networks。
- 目标企业为 Applied Compute。
- 交易价值为 45 亿美元。
- 采用全股票支付方式。
- 目标公司成立仅约一年，由前 OpenAI 研究人员创立。
- 核心业务与 Fireworks 有相似之处，都是帮助企业基于自身数据训练和运行定制模型。

Nvidia 与 Fireworks 的关系
- Nvidia 从 2024 年起支持 Fireworks。
- 文章提到 Jensen Huang 在上周离开 Nvidia，并询问是否会影响双方关系。
- Zhao 表示这对行业是一个打击，但认为 Nvidia 长期支持开放技术的方向不会改变。
- 他预计 Nvidia 将继续投资 Nemotron，并希望继续维持双方合作。

资料边界：以上有关 IPO、人事变化、估值、融资和收购的内容均按所提供文章记录；其中未附具体日期或独立证明的重大事件，不应直接视为已经核实的现实事实。尤其是 Anthropic 上市及 Jensen Huang 离任等时效性很强的描述，正式对外引用前应单独查证。

## 金句摘录

### 1. AI 的控制权应该属于企业
“That way you own your AI rather than being beholden to giant AI conglomerates.”

中文翻译：“这样一来，你就真正拥有自己的 AI，而不是受制于大型 AI 集团。”
这句话体现了 Fireworks 最重要的商业主张：模型选型不只是价格问题，更是长期自主权和竞争壁垒的问题。

### 2. 调用同一个顶级模型，不构成竞争优势
“If you’re just using Opus or Sonnet, that’s not a differentiator.”

中文翻译：“如果你只是使用 Opus 或 Sonnet，那并不能成为你的差异化优势。”
背后的含义是，标准化模型能力可以被竞争对手轻易购买，真正难以复制的是企业数据、业务流程与模型之间的结合。

### 3. 开放模型正在迅速追赶
“These days it’s at most six months behind, probably closer to three.”

中文翻译：“如今，开放模型最多只落后六个月，实际可能更接近三个月。”
这是 Zhao 对开放模型竞争力最有代表性的判断，也支撑了他关于企业可以降低前沿模型依赖的论点。

### 4. 什么时候开始认真考虑开放模型
“But once you pass 10,000 or 100,000 users and you’re spending $10,000 to $100,000 a month on tokens, it’s time to think about open source.”

中文翻译：“但是，一旦你的用户规模超过 1 万或 10 万，并且每月在 Token 上花费 1 万到 10 万美元，就该开始考虑开源方案了。”
这句话提供了一个非常实用的商业判断框架：初期优先验证价值，规模化阶段再系统优化成本。

### 5. 衡量 AI 经济性的指标正在改变
“That’s why there’s so much interest in routing, and why people now think about cost per task, not just cost per token.”

中文翻译：“这就是为什么人们对模型路由如此感兴趣，以及为什么大家如今考虑的是每项任务的成本，而不只是每个 Token 的成本。”
这是全文最值得记住的方法论之一：模型的单位报价不等于实际业务成本，完成任务的整体效率才是真正的衡量标准。

### 6. 零数据留存承诺的具体范围
“Our promise is zero data retention for inference traffic, and there’s no indication that has been compromised.”

中文翻译：“我们承诺对推理流量实行零数据留存，目前没有迹象表明这一承诺遭到了破坏。”
这句话的关键在于 for inference traffic（针对推理流量）这一限定，说明安全承诺的适用范围必须精确理解，不能自动扩大到所有服务和全部客户数据。

## 值得记住的点 / 行动建议
以下结合 Zhao 的观点与文章披露的事件，整理为可以在 AI 产品、企业系统和创业实践中落地的行动建议；具体实施步骤属于对原文的延伸，不全部是采访者的直接建议。

### 1. 不要一开始就追求最低模型成本：先验证需求，再优化经济性
对于正在做 AI 产品的创业团队，首先要明确当前处于哪个阶段。如果还在寻找 PMF、用户规模很小、产品需求不断变化，那么直接使用能力较强的成熟模型通常更容易快速迭代。
这一阶段可以先确保三个问题得到验证：用户是否真的需要产品、模型输出是否满足核心需求、用户是否愿意持续使用或付费。
当产品开始拥有稳定的任务类型、增长中的用户规模，以及可预测的模型调用量时，再对成本结构进行系统分析。
可以参考 Zhao 举出的情境——用户达到 1 万至 10 万量级、每月 Token 开支达到 1 万至 10 万美元时，考虑开放模型的收益可能明显增加；但这不是硬门槛，实际仍要结合毛利、人员成本和迁移成本决定。
实操原则：早期用能力换速度，后期用优化换利润。

### 2. 按任务拆分 AI 需求，避免所有请求都调用最强模型
企业不应该把整个 AI 产品视为一个不可分割的任务，而应该把具体工作拆解出来，建立任务清单。
例如：

| 任务类型 | 优先考虑的模型策略 | 判断依据 |
| --- | --- | --- |
| 复杂战略规划 | 高能力前沿模型 | 需要综合推理和多步骤判断 |
| 高难度代码开发 | 优先测试高能力模型 | 质量错误可能产生较大代价 |
| 普通文档分类 | 较小的开放模型 | 任务边界相对清晰 |
| 标准化信息提取 | 小模型或专用模型 | 输出格式明确、可验证 |
| 简单计算 | 传统程序或工具，必要时结合小模型 | 不必为确定性运算支付高额推理费用 |
| 重复性客服问答 | 专用模型或混合模型 | 任务高频、答案范围相对可控 |
| 多阶段复杂工作流 | 多模型路由 | 不同阶段的能力需求不同 |

其中一个重要延伸是：并非每个问题都应该交给 LLM。 对于能够由传统代码、搜索系统、规则引擎或数据库查询准确解决的任务，使用这些工具可能比调用任何语言模型都更经济可靠。

### 3. 从计算 Token 价格升级为计算每项任务的真实成本
模型选型不应只比较供应商每百万 Token 的报价，因为低价模型可能需要更多次重试，也可能产生更多人工审核成本。
企业可以建立一个简单的任务级成本指标：
单任务成本=模型调用费+基础设施费+重试费+人工复核费成功完成的任务数\text{单任务成本} =
\frac{\text{模型调用费}+\text{基础设施费}+\text{重试费}+\text{人工复核费}}{\text{成功完成的任务数}}单任务成本=成功完成的任务数模型调用费+基础设施费+重试费+人工复核费​
例如，下面是一个用于理解方法的假设性计算，并非原文中的真实业务数据：
- 模型 A 每次调用成本 0.02 美元，任务一次成功率 70%。
- 模型 B 每次调用成本 0.05 美元，任务一次成功率 98%。
- 如果允许独立重试且每次成功率不变，仅按模型调用费用估算，A 的平均成功成本约为 0.0286 美元，B 约为 0.0510 美元。
- 在这个例子中，A 在纯调用成本上仍更便宜，但如果 A 带来更高延迟、人工复核或错误损失，结果可能逆转。

因此，完整评估应同时记录成功率、重试次数、平均延迟、人工处理量和用户满意度。
最终应该优化的是单位成功结果的综合成本，而不是孤立的单位 Token 价格。

### 4. 建立模型路由机制，把昂贵模型留给真正困难的任务
企业可以为不同任务设置模型能力等级，让系统根据问题难度、风险和预期价值自动选择模型。
一种实用的三层结构是：
第一层：简单任务
低成本

小型开放模型、传统规则、数据库查询或确定性工具，处理分类、提取、格式化、简单计算等任务。

第二层：普通复杂度任务
平衡成本与效果

中等能力模型或企业定制模型，处理多数常规问答、文本生成、业务分析和日常辅助工作。

第三层：高难度任务
优先能力

高能力前沿模型，处理复杂规划、疑难推理及前两层模型无法可靠解决的工作。
任务可直接进入适合的一层；也可以在质量检测未通过时逐级升级。高风险结果仍应设置独立校验或人工审批。
对于存在明显难度差异的业务，模型路由可能比单纯替换供应商产生更大收益，因为它可以保留关键任务所需的高能力，同时降低简单任务的成本。

### 5. 把企业自己的数据变成模型的竞争壁垒
如果企业所有 AI 能力都来自同一个公共 API，那么竞争对手通常很容易复制产品的核心模型能力。
要形成真正的差异化，需要找到企业特有且对业务结果有帮助的数据和知识，例如内部业务流程、经过许可的行业资料、专业决策规则、历史服务经验或经过严格处理的反馈数据。
可以通过模型微调（Fine-tuning）、检索增强生成（RAG）、工具调用和业务流程集成等方式，把这些信息转化成模型的专用能力。
同时要设计评测集，验证模型定制之后是否真正提升了准确率、业务效率或客户体验，而不只是让回答看起来更贴近企业风格。
应当注意，拥有数据并不必然形成竞争壁垒：数据是否高质量、是否合法可用、是否能持续更新，以及能否真正改善结果，才决定其商业价值。

### 6. 采购 AI 服务时，逐项确认数据留存政策，而不是只看“零留存”宣传
Notion 事件提供了一个非常具体的警示：同一 AI 供应商的不同产品，可能采用完全不同的数据处理方式。
采购或部署时，至少应该确认以下事项：
- 在线推理输入和输出是否被保存，保存多长时间。
- 批量上传的数据集是否会存储，以及默认保留周期。
- 数据是否会进入日志、缓存、备份或开发调试系统。
- 第三方云服务商及其子处理方能接触哪些信息。
- 是否允许使用客户数据进行模型训练或服务改进。
- 删除请求是否同时覆盖主存储、备份和日志。
- 安全事件发生时，供应商如何通知、协助调查与补救。

不能因为供应商声称“推理零留存”，就默认所有上传文件、批量处理数据和开发环境也实行零留存。
更可靠的做法是按具体服务、数据类别、流转环节和合同条款核对安全承诺。

### 7. 把 API 密钥管理视为 AI 系统的重要安全工程
Fireworks 的第一起安全事件说明，AI API Keys 和 Tokens 已经成为具有直接经济价值的攻击目标。
企业应避免把密钥硬编码在源代码、前端程序或公开仓库中，改用专门的 Secrets Manager（密钥管理系统）保存，并按照最小权限原则分配访问权。
还应设置密钥轮换机制、调用额度和支出上限，对异常调用频率、陌生来源以及突增的推理费用建立告警。
对于开发环境和生产环境，最好使用不同凭证，并限制开发系统对正式客户数据的访问权限。
这不仅能够减少数据泄露风险，也有助于降低 LLM Jacking 导致的经济损失。

### 8. 不要因为开放模型便宜，就忽略供应商集中风险和迁移风险
使用开放模型能够减少对某一家前沿实验室的依赖，但如果企业仍把推理、存储和所有模型部署集中在单一基础设施平台上，就可能形成新的供应商依赖。
Fireworks 的案例说明，哪怕一家平台具有明显的性能、成本或融资优势，也可能因安全事件让客户突然面临业务中断或迁移压力。
企业可以提前制定模型和平台切换方案，包括统一 API 抽象层、备选供应商、关键模型的离线评测数据，以及数据导出和恢复机制。
对于重要业务，应明确发生安全事件、不可用或重大服务变更时的切换标准。
最终目标不是简单地从“依赖一个模型巨头”变成“依赖一个开源模型平台”，而是建立可替换、可审计、可持续的 AI 架构。

### 9. 看待 AI 公司的长期价值，要区分模型能力、基础设施价值和资本市场预期
Zhao 同时看好开放模型的普及和 Anthropic 的长期前景，并不矛盾，因为二者可能从 AI 使用量增长中以不同方式受益。
前沿模型企业主要提供高能力模型和持续研发，企业 AI 基础设施公司则帮助客户部署、优化、路由和定制模型，算力公司又提供底层计算资源。
评估一家企业时，应分别考察其技术优势、客户使用量、实际收入、毛利率、客户留存、部署成本和安全记录，而不能只看估值或融资规模。
Applied Compute 成立约一年便出现 45 亿美元收购交易，反映了市场对这一领域的高度关注，但巨额交易价值不能直接证明所有同类企业都具有相应的盈利能力。
对于创业者和投资者，行业长期增长与某个公司的短期估值是否合理，是两个需要独立回答的问题。

## 我的点评
文章最有价值的地方，是把 AI 模型选择从“谁的模型最聪明”转变成“怎样以合理成本、质量和风险完成业务任务”，尤其是模型路由与每任务成本的思路，对已经进入规模化阶段的 AI 产品非常实用。
Zhao 对开放模型追赶速度的判断也有启发，但“三到六个月差距”属于特定企业高管的主观估计，不能直接推广到所有复杂推理、编码、长上下文或高可靠性任务，真正选型仍需要用自己的业务评测数据验证。
文章的另一个重要价值是揭示了“AI 自主可控”与“AI 数据安全”并不是一回事：企业即使使用开放权重模型，只要仍依赖外部推理平台、批量存储或云开发系统，就仍然可能遭遇供应链攻击和数据泄露。
此外，Zhao 本身是 Fireworks 联合创始人，具有推广开放模型和企业定制平台的商业动机，因此其成本、竞争优势和行业趋势判断应被理解为有利益立场的观点，而非完全中立的研究结论。
普通人、AI 创业者和企业技术负责人最值得学习的是一种更成熟的工程与商业思维：先确定任务需要什么能力，再选择成本合适的技术方案，用真实结果评估经济性，并把数据保护和供应商风险纳入整体决策。
全文真正的长期启示或许是：随着通用 AI 能力越来越普及，企业未来的竞争力未必来自能否购买最强模型，而会更多取决于能否把模型、专有数据、业务流程、安全治理和成本控制组合成别人难以复制的系统。

---

## 📝 完整文字稿

On the same day that Anthropic went public in the largest IPO on record, with investor enthusiasm for the AI lab through the roof, far away at the Slush startup conference in Helsinki, the topic du jour was open source everything.

That’s the enormous opportunity being chased by companies like Fireworks AI, as enterprises seek ways to avoid paying frontier prices for their AI needs.

Fireworks runs AI models for other businesses. It specializes in open-weight models, which anyone can download, and helps customers tune them on their own data so they run faster and cheaper than the models of Anthropic, OpenAI, and other heavyweights, and are harder for rivals to copy. Customers have included Uber, Shopify, and Notion. Co-founder Chenyu Zhao and I spoke onstage toward the end of the day.

Zhao and many others believe companies are gravitating toward platforms like his because frontier models are pricey and, in most cases, he says, unnecessary unless you need the very latest and greatest generalized intelligence. There are also growing concerns that frontier labs absorb too much of their customers’ know-how, even if only through the prompts used to get answers, a worry Microsoft CEO Satya Nadella raised in July.

Fireworks has also gotten its first black eye, having disclosed two security incidents this fall. In one, hackers reached API keys and tokens stored as secrets for a limited number of accounts; in the other, attackers breached its cloud provider, made their way into a development system, and nabbed customer data, including billing records and some datasets.

Notion says AI chat transcripts from fewer than 1% of its workspaces were exposed, but it has disconnected from Fireworks. Uber says hackers stole the names, addresses, birth dates and driver’s license numbers of about 150,000 drivers through a vendor that TechCrunch identified as Fireworks. Fireworks will have to win back the confidence of customers like them.

Fireworks, assigned a $17.5 billion valuation by its investors in summer, is reportedly in “early talks” for yet another round, though Zhao declined to comment.

There’s money chasing everyone in the category, seems like. Rival companies Together AI and Baseten have announced massive rounds in recent months. On Wednesday, Palo Alto Networks said it will buy Applied Compute, which, like Fireworks, helps companies train and run custom AI models on their own data. The deal for the startup, founded just a year ago by former OpenAI researchers, is $4.5 billion, all of it in stock.

Here’s some of what Zhao had to say. This conversation has been edited for length and clarity.

You spent a decade at Google, including managing a 50-person engineering team on Google Cloud Vertex AI. Why leave when you did?

When you meet great co-founders, it’s obvious within five minutes that they’re really smart. I was sold after talking to Lin [Qiao] and Dima [Dzhulgakov]. It’s also important to find people who are genuinely nice, people you’ll enjoy working with.

How do you describe Fireworks to a CEO who has never heard of it?

I describe Fireworks as a specialized intelligence platform. OpenAI and Anthropic are building general intelligence. We use open models, which are often smaller, cheaper, and faster, and let companies add their own data to specialize them. That way you own your AI rather than being beholden to giant AI conglomerates. If you’re just using Opus or Sonnet, that’s not a differentiator.

How far behind are open models right now?

A few years ago I’d have said a year, a year and a half. Then came DeepSeek and a waterfall of fantastic open models. These days it’s at most six months behind, probably closer to three.

If the models are so close behind, why are businesses slow to switch?

Frontier models are a household brand, and before you find product-market fit, using the best model is low risk. But once you pass 10,000 or 100,000 users and you’re spending $10,000 to $100,000 a month on tokens, it’s time to think about open source.

In July, Microsoft CEO Satya Nadella warned that companies using proprietary AI models pay twice, once in money and again in know-how. Do you think that warning had a material effect?

We think we’ll live in a two-model world, with frontier and open models in parallel. You want the best intelligence for high-level planning, but you don’t need a frontier model for basic arithmetic. That’s why there’s so much interest in routing, and why people now think about cost per task, not just cost per token.

Anthropic went public today. What do you think of its valuation? There’s one scenario in which it just continues to cement its place in this sort of oligopoly; there’s another where it starts to lose traction.

On the record: I’ll probably call my broker tonight and buy a few shares. This is a long-term bet. In 10 years AI usage will be at a completely different scale, and that takes an incredible amount of capital, which is why these companies are going public.

Fireworks has had a couple of security breaches recently. What do you tell customers?

Every company is probably seeing an unprecedented frequency of attacks. For our incident, a lot of the motivation was LLM jacking: hunting through providers for API keys and secrets to sell tokens on illicit marketplaces. Our promise is zero data retention for inference traffic, and there’s no indication that has been compromised.

Notion has disconnected from Fireworks. Did you lose other customers?

I don’t think I can publicly name the specific customers that were impacted. Some, such as Notion and Cursor, have gone public already. It was a small subset of our customers that had this data impact.

How did that customer data get exposed, given your zero-retention promise?

Notion was using batch prediction, where you upload a dataset that’s stored at rest, so it’s not a zero-retention product by nature. We’re moving those services to an online flow so we keep data only as long as we need it.

Jensen Huang left Nvidia last week, and Nvidia has backed Fireworks since 2024. Does that affect you?

It’s been a blow to the industry, and we feel for Jensen and his family. But Nvidia has always been a strong supporter of open source, and I don’t see that changing. We expect it to keep investing in Nemotron, and we’re excited to keep partnering with them.
