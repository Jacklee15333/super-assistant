# Anthropic 的诞生之路

- 来源链接：https://www.youtube.com/watch?v=sof3vW4mHTs
- 作者：Anthropic
- 提取时间：2026-11-20 10:14
- 原标题：The making of Anthropic
- 标签：Claude演进、模型规模化、AI安全、技术治理

## 🤖 AI 分析

## 一句话概括
这部视频通过 Anthropic 创始团队的亲身回忆，完整讲述了这家 AI 公司如何从一群研究者对人工智能潜力与风险的共同认知出发，经历创立公司的艰难抉择、早期模型的失败、Claude 的诞生、技术追赶与商业突破，最终形成一套以前沿 AI 能力为基础、以安全研究为核心、以人类长期利益为使命的发展理念。

## 背景与主题
视频以“为什么要创立 Anthropic？”为切入点，通过 Dario、Jared Kaplan、Chris Olah 等创始团队成员的回忆，回顾了 Anthropic 从 2021 年正式成立到 Claude 系列模型崛起的历程。创始团队最初来自理论物理、数学、编程、生物医学、新闻、国际发展等不同领域，其中一批人在 OpenAI 共事时发现：AI 的能力可能随着算力和数据规模的扩大而持续提升，最终带来远超当时社会预期的变化。
他们既被 AI 在医疗、科研、软件工程等领域的潜力吸引，也担忧超越人类能力的系统可能带来严重风险，因此决定建立一家将 AI 安全融入公司使命的组织。视频不仅介绍了 Anthropic 的创业过程和产品演进，还重点展示了当技术能力与安全责任发生冲突时，公司如何尝试作出选择。
整部视频的核心不是简单讲述一家公司的成功史，而是在回答一个更深层的问题：当人类开始创造可能比自己更聪明的技术时，应该建立怎样的组织，才能让这种技术真正造福人类？

## 核心观点

### 1. Anthropic 的创立源于一种强烈的预感：AI 将在有生之年彻底改变世界
视频开头，一位创始团队成员回忆，当年大家仿佛掌握了一个世界上其他人还不知道的秘密：人工智能的发展速度和最终影响，可能远远超出普通人的想象。早在 2013—2014 年，团队中就有人开始注意到 AI 研究取得的重大突破，并思考推动 AI 发展是否可能成为推动生物学进步的最佳方式；而在 2016 年，当时的 AI 甚至还无法像今天这样自然地与人交谈。到 2018 年，未来的 Anthropic 联合创始人已经在 OpenAI 从事模型训练、政策研究、可解释性（Interpretability）和安全研究等不同工作，并逐渐形成相似的技术判断。他们开始相信，达到人类水平的 AI（Human-level AI）不是一百年以后才会出现的遥远技术，而可能在他们自己的有生之年实现。这种对技术发展速度的提前认知，既让他们感到兴奋，也让他们意识到必须尽早承担相应责任。

### 2. 规模化规律改变了 AI 研究路线：更大的算力和更多的数据，可以带来可预测的智能提升
Dario 注意到一种重要趋势，并将其称为 “the big blob of compute”（巨大的算力集合）：不一定要为 AI 手工编写复杂的推理、规划和工具使用规则，只要持续扩大计算规模、增加训练数据，模型就可能自然获得越来越强的能力。在早期，很多研究者认为，必须明确教会神经网络如何规划、推理和使用工具，但团队观察到，随着语言模型规模不断扩大，新的行为和能力会不断涌现（Emergent Abilities）。这意味着智能能力可能在相当程度上遵循某种可预测的规模化趋势，而不完全依赖人为设计的复杂规则。团队由此意识到，持续扩大算力投入并改进训练算法，有可能让原本只能预测下一个词的模型，逐步发展为能够处理复杂任务的通用助手。真正改变他们世界观的，不是某一次模型表现得更聪明，而是他们发现智能能力可能随着规模扩大而系统性地提升。

### 3. AI 的巨大价值与巨大风险来自同一个根源：它可能成为超越人类能力的通用问题解决者
创始团队认为，先进 AI 的潜力不仅在于让聊天机器人回答问题，而在于大幅提高人类解决困难问题的能力，包括编写计算机程序、提出新的科学假说、证明数学定理、推动机器人技术和医疗研究等。视频甚至提出一种非常乐观的可能性：未来或许可以将癌症发生率降低 90%，并让心脏病、肥胖症以及多种重大感染性疾病不再像今天这样困扰人类；需要注意，这些是对技术潜力的设想，而不是已经得到证实的预测。如果社会中的很多难题受限于人类的智力、创造力和科研效率，那么更强大的 AI 就可能显著提高解决这些难题的速度。但问题在于，同样的技术也可能被用于制造破坏，当人类创造出比自己更强大的系统时，其失控、误用和社会影响都可能非常严重。视频将 AI 与药物研发、原子科学的突破相类比：它们既可能为人类带来难以想象的利益，也可能因为错误使用而造成巨大损害，因此安全不能等到技术成熟之后才考虑。

### 4. Anthropic 从成立之初就试图解决一个组织治理问题：当利润和公共利益冲突时，公司应该如何选择
创始团队最初并不只是想创建一个 AI 研究实验室，而是希望建立一个能够应对强大 AI 技术所带来责任的长期组织。他们清楚，要训练前沿模型（Frontier Models），就必须拥有世界上规模最大的计算基础设施之一，持续投入大量资源，并最终把技术部署到真实世界，因此公司不能完全脱离商业运作。但他们同样认为，单纯以经济回报和股东价值最大化为目标的组织，可能无法在关键时刻作出符合长期安全利益的决定。经过复杂讨论，Anthropic 最终选择了 **Public Benefit Corporation（公共利益公司）**的法律组织形式，并于 2021 年 1 月 26 日正式注册成立。其核心原则是：公司应当能够在必要时为了使命牺牲短期利润，甚至放弃某些原本可以为股东带来最大收益的商业机会；这一选择后来成为 Mythos 安全部署决策的重要依据。

### 5. 伟大的技术公司在最初往往非常混乱，真正支撑它的是共同价值观和大量不起眼的基础工作
Anthropic 的早期远没有后来一家大型 AI 公司的成熟面貌，创始人甚至花了不少时间讨论公司名字。候选名称包括 Squirrel（松鼠）、Owl（猫头鹰）、Whale（鲸鱼）、Differentiated（差异化）和 Humane（人道的），最终 Jared 提出了 Anthropic，理由是这个词具有“以人类为中心”的含义，与公司希望让 AI 服务人类利益的愿景吻合。还有一个非常实际的原因：团队发现 Anthropic.com 的域名价格似乎是候选方案中最便宜的，而命名表格中的评价也简单到只有“我们喜欢这个名字，它很好”“域名是否可用？”“是”。公司成立后，Tom 负责获取 AWS 计算集群，Chris Olah 与另一位成员搭建最早的网站，Dario 负责融资，其他人负责招聘，而首席科学家 Jared Kaplan 甚至有几个月亲自负责工资发放。这段经历表明，早期 Anthropic 不是一个分工明确、制度完善的商业机器，而是一群高度信任彼此、共享安全理念的研究者，一边搭建组织，一边探索技术的可能性。

### 6. Claude 的早期研发证明：一个真正有用的 AI 助手，必须同时具备能力、安全性和诚实性
Anthropic 成立初期就确立了著名的三个目标：Helpful、Harmless、Honest（有帮助、无害、诚实），并尝试让模型在这三个维度上不断改进。团队最先解决的是让助手能够完成任务，随后又重点研究减少有害输出，但很快发现，即使模型看起来很友善、愿意帮助用户，它仍然可能一本正经地编造事实。例如，早期模型曾极力向研究人员证明，只吃土豆的饮食方式非常健康；用户还可以要求它进入 Dragon Mode（龙模式），随后模型就会使用全大写文字对人“咆哮”。这些系统虽然已经具备某些聊天能力，却经常缺乏基本的事实判断和常识可靠性。团队因此认识到，AI 对齐（Alignment）不是单纯让模型听话，也不是让它拒绝危险要求，而是必须同时提升实际能力、降低风险，并减少编造信息和错误自信。

### 7. Claude 的诞生是一个重要突破，但公开发布并不意味着 Anthropic 已经拥有竞争优势
2022 年年中，团队训练出了一个最初代号为 Junior、后来命名为 Claude 的模型，它第一次让研究人员真正感受到“这东西可以用了”：用户能够与它正常对话，提出问题并得到有意义的回答。视频中一位成员介绍了自己设计的 Helicopter Test（直升机测试）：他会询问 AI“一个人一顿饭能吃下多少架直升机”，而早期聊天机器人可能会荒谬地回答“一两架，要看具体情况”；Claude 则识别出这是一个陷阱问题，明确表示人不可能吃直升机。2023 年 3 月，Claude 正式向公众发布，但公司很快发现，虽然产品已经取得进步，整体模型能力仍明显落后于行业前沿。潜在客户会直接问：“为什么我们应该使用你们的模型，而不是别人的？”团队将这一时期形容为艰难的落后阶段，甚至用了“the years of suck”（那些糟糕的岁月）来描述，但也正是这段时期迫使公司认真面对技术差距，并从研究导向进一步转向追求世界一流的模型能力。

### 8. 追赶行业前沿不仅是商业竞争，也是 Anthropic 开展有效安全研究的必要条件
面对模型能力明显落后的问题，Anthropic 开始集中资源改进预训练（Pretraining）、强化学习（RL）和计算效率，尤其重视获取更多算力以及积累能够提高算力实际使用效率的算法改进。团队将这些算法层面的改善称为 Compute Multipliers（算力乘数）：通过一系列细小的技术优化，让同等计算资源训练出更聪明、更擅长遵循指令的模型。此后，Claude 3 Opus 成为团队眼中第一个真正达到高水平的模型，而几个月后推出的 Claude 3.5 Sonnet 又显著提高了模型的编程实用性，推动团队开发出后来成为 Claude Code 的工具，让 AI 能够实际操作计算机并完成软件任务。视频进一步指出，只有处于能力前沿，Anthropic 才能尽早观察到更强 AI 系统可能出现的新风险，而不是只能研究能力较弱、尚未表现出某些危险行为的模型。因此，在 Anthropic 的逻辑中，争夺最先进模型的位置，不只是为了赢得市场，而是为了获得研究未来风险的第一手条件和更多应对时间。

### 9. Mythos 与 Glasswing 展示了 Anthropic 安全理念面临真正考验时的选择
视频后半部分将叙事转向 2026 年，认为此前关于 AI 风险的讨论在很大程度上还是概念性推演，而当模型具备专家级网络安全能力后，危险开始变得具体。视频介绍，Anthropic 对一款名为 Mythos 的先进模型进行了有限测试，安全专家发现它能够以非常高的水平寻找软件系统中的漏洞及可利用路径，这让团队意识到：如果恶意攻击者获得这种能力，就可能对大量软件系统发动高效攻击，给整个互联网生态带来严重影响。Dario 因此召集公司管理层，明确表示这个模型必须采用与以往完全不同的发布方式。公司随后启动 Glasswing 项目，先向规模较小、经过选择的企业群体开放 Mythos 的能力，使网络防御方能够优先发现、修复漏洞，同时研究进一步开放所需的安全防护。视频强调，这种分阶段开放方式未必能让公司获得最大收入或利润，却被团队视为践行公共利益使命的关键时刻；也就是说，安全价值不是写在公司章程里的口号，而是面对真实商业机会时愿意承担的成本。

### 10. Anthropic 的最终目标不是阻止 AI 发展，而是在控制风险的同时释放它改善世界的能力
虽然整部视频大量讨论 AI 的危险，但创始团队反复强调，他们创立 Anthropic 的根本原因仍然是相信人工智能能够给人类带来巨大好处。视频列举了 Claude 已经被用于帮助人们理解医疗诊断、创业、培养新的兴趣爱好，以及辅助生物学家和科学家研究常见及罕见疾病的案例。团队还提到，内部生物学研究似乎发现了一种新的基因编辑机制，并提出未来几个月可能达到每月发现数十种此类机制的速度；这里的发现和速度预期仍需要独立研究验证，不能直接视为既定科研成果。创始人认为，随着 AI 能力不断增长，今天看似零星的科学突破，未来可能转变成大规模科研创新浪潮。但视频最后保持了某种克制：Anthropic 尚未真正证明自己能够同时实现强大 AI、充分安全与广泛社会收益，团队只是认为自己正在朝这个目标前进。

## 关键事实与数据

### 一、重要时间线

| 时间 | 关键事件 | 意义 |
| --- | --- | --- |
| 2013—2014 年 | 部分未来创始团队成员开始注意到 AI 的重大研究进展 | 开始思考 AI 能否推动生物学和其他科学领域的进步 |
| 2016 年 | 有成员正式进入 AI 领域 | 当时 AI 还不具备今天这种自然对话能力 |
| 2018 年 | 未来的 Anthropic 联合创始人在 OpenAI 从事多种研究 | 涉及模型训练、政策、可解释性、安全等方向 |
| 2021 年 1 月 26 日 | Anthropic 以 Public Benefit Corporation 形式注册成立 | 从公司治理层面确立公共利益使命 |
| 2021 年 | 团队内部文档描述通用 AI 编程助手的构想 | 通过自然语言创建、编辑、解释软件 |
| 2022 年年中 | 训练出最初代号 Junior 的模型，后来命名为 Claude | 开始出现真正实用的对话能力 |
| 2023 年 3 月 | Claude 首次公开发布 | Anthropic 正式将核心 AI 助手推向公众 |
| Claude 3 Opus 阶段 | 团队认为第一次拥有真正强大的模型 | 模型能力追赶取得重要突破 |
| Claude 3.5 Sonnet 阶段 | 模型编程能力显著提升 | 为后来的 Claude Code 奠定技术基础 |
| Claude Code 推出阶段 | AI 开始能够通过工具执行计算机任务 | 从对话式助手发展到实际完成软件工程任务 |
| 2025—2026 年前后 | 团队认为 AI 风险开始从理论推演走向具体案例 | 安全治理需要应对可观察的现实威胁 |
| 2026 年（视频叙述） | Mythos 的网络安全能力引发高度关注，Glasswing 项目被用于限制性开放 | 尝试通过优先赋能防御方降低技术滥用风险 |

注：视频没有给出 Claude 3 Opus、Claude 3.5 Sonnet、Claude Code 和 Glasswing 所有事件的完整日期，因此表格按视频的叙事顺序整理，不补写未提供的精确时间。

### 二、主要人物及其具体贡献
- Dario：Anthropic 核心创始人物之一，较早认识到扩大计算规模与 AI 智能提升之间的重要联系，并提出 “the big blob of compute” 的说法。公司早期由他负责融资；在 Mythos 引发安全担忧时，他召集领导团队推动不同于以往的发布策略。
- Jared Kaplan：视频明确提及的 Anthropic 首席科学家（Chief Scientist）。在公司成立早期，他甚至曾负责几个月的工资发放工作，体现初创公司的人员有限和职责混杂。
- Chris Olah：参与搭建 Anthropic 的第一版网站，也是公司早期研究团队的成员。
- Tom：视频提到，他在公司初期承担了获取 AWS 计算集群的任务。
- Jared：视频说 Anthropic 这个公司名称由 Jared 提出；结合上下文，很可能指 Jared Kaplan，但这一段文字稿没有单独写出完整姓名。
- 其他未明确标注姓名的受访者：包括理论物理研究者、曾任 Johns Hopkins 教授的人士、在 Stanford 从事癌症生物标志物博士后研究的科学家、记者、研究数据中心的人士，以及从事全球发展工作的成员。由于文字稿没有逐句标注说话者，不能可靠地将这些具体履历全部对应到个人。

### 三、创始团队的专业背景
视频特别强调，Anthropic 并不是由单一学科的 AI 工程师建立的，而是不同研究背景的人逐渐汇聚而成。
- Princeton University（普林斯顿大学）：有成员曾以理论物理博士生身份进入该校。
- Johns Hopkins University（约翰斯·霍普金斯大学）：有成员曾在这里担任教授。
- Stanford University（斯坦福大学）：有成员毕业后赴该校开展癌症生物标志物（Cancer Biomarkers）的博士后研究。
- 理论物理（Theoretical Physics）：不止一位受访者提及理论物理研究背景，也有人对原本的物理研究感到一定程度的挫折，认为 AI 是更令人兴奋的新领域。
- 数学与编程：有成员主要将自己视为数学家和程序员。
- 新闻与基础设施研究：有成员此前是记者，并曾深入研究数据中心。
- 全球发展（Global Development）：有成员大学毕业后投入全球发展相关工作，希望利用技术改善现实世界。

这些经历的共同点是：团队成员原本就对科学发现、复杂问题和社会影响抱有长期兴趣，AI 被他们视为能够放大研究及社会贡献的工具。

### 四、重要模型、技术与产品名称

| 名称 | 中文解释 | 视频中的作用 |
| --- | --- | --- |
| Anthropic | 带有以人类为中心含义的公司名称 | 体现 AI 应服务人类利益的创办理念 |
| OpenAI | 人工智能研究与产品公司 | 多位未来联合创始人此前共事的机构 |
| AWS（Amazon Web Services） | 亚马逊云服务 | Anthropic 早期获取计算集群的来源 |
| Scaling（规模化） | 扩大模型、算力与训练数据规模 | 团队对智能能力持续增长的核心判断 |
| Emergent Abilities（涌现能力） | 模型规模增加后出现的新能力 | 让团队相信模型可能发展出复杂智能行为 |
| Interpretability（可解释性） | 研究模型内部如何表示信息及产生行为 | 早期 AI 安全研究的重要方向 |
| Alignment（对齐） | 使模型行为符合人类目标和价值 | Anthropic 成立时的重要研究使命 |
| Pretraining（预训练） | 大规模基础模型训练 | Anthropic 追赶领先模型时的重要改进方向 |
| RL（Reinforcement Learning，强化学习） | 通过反馈或奖励信号优化行为 | 提升模型质量与助手能力的训练方法 |
| Compute Multipliers（算力乘数） | 提高单位算力实际训练效果的算法改进 | 让有限资源产生更强的模型能力 |
| Junior | Claude 早期内部代号 | 2022 年年中开始表现出良好对话能力 |
| Claude | Anthropic 的 AI 助手与模型系列 | 2023 年 3 月正式公开发布 |
| Claude 3 Opus | Claude 系列高能力模型 | 标志团队在模型质量方面的重要突破 |
| Claude 3.5 Sonnet | Claude 系列模型 | 让编程成为更加实用的 AI 应用场景 |
| Claude Code | AI 编程与软件任务执行工具 | 体现从回答问题到实际完成任务的转变 |
| Mythos | 视频中介绍的先进 AI 模型 | 因强大的漏洞发现和利用能力引发安全担忧 |
| Glasswing | Mythos 限制性部署项目 | 优先帮助网络防御方发现并修复漏洞 |

### 五、视频中出现的具体数字、判断与预测
**1. 人类水平 AI 的时间判断**
团队认为，人类水平 AI 不一定要再等 100 年，而可能在创始团队成员的有生之年出现。这里没有给出明确年份，是一种方向性判断。
**2. 癌症发生率降低 90% 的设想**
视频提出，先进 AI 未来或许能够帮助人类将癌症发生率降低 90%。它用于说明 AI 在医学领域的潜在影响，属于高度乐观的假设，绝非目前已经实现或验证的效果。
**3. 三项核心行为目标**
Anthropic 早期助手的设计原则包括：
- Helpful：有帮助，能够真正完成用户任务。
- Harmless：无害，尽量避免造成伤害。
- Honest：诚实，不胡编乱造，正确表达事实和不确定性。

三者缺一不可，且视频认为早期实现“诚实”尤其困难。
**4. 首席科学家负责几个月的工资发放**
Jared Kaplan 曾在初创公司运营的某几个月兼任工资发放工作。这不只是一个趣闻，也反映了初创团队资源有限、岗位职责高度混合的现实。
**5. 2022 年年中的模型能力突破**
代号 Junior 的模型在这一阶段已经能够完成基本有效对话，后来被命名为 Claude。团队通过直升机测试等方式观察到其常识判断明显改善。
**6. 生物学团队每周多次沟通**
一位受访者提到，自己每周会与公司生物学团队交流数次，说明团队不仅将 AI 用于通用任务，还在积极探索科研应用。
**7. 每月发现数十种基因编辑机制的可能性**
视频称团队似乎发现了一种新的基因编辑机制，并设想几个月后可能达到每月发现数十种的速度。这是视频中的阶段性说法和未来预期，并非经独立验证的稳定研究产出。
**8. Mythos 采取小范围开放方式**
视频没有提供具体开放企业数量，也没有公布完整访问名单，只强调相较于普通公开发布，它优先面向较小范围的公司，以便先开展漏洞检测和修复。

### 六、最值得保存的具体事例
案例 A：Anthropic 名称的产生
团队曾考虑 Squirrel、Owl、Whale、Differentiated 和 Humane 等名称，最终选定 Anthropic。其含义符合以人类为中心的价值观，而 Anthropic.com 域名价格便宜也是一个实际考虑因素。这说明创始决策既包含理念，也包含非常朴素的成本考量。
案例 B：只吃土豆的健康建议
早期 AI 助手曾试图极力说服研究人员相信“只吃土豆也非常健康”。这个案例说明，模型可能具有流畅的语言表达能力，却同时缺乏事实准确性。
案例 C：Dragon Mode（龙模式）
用户让早期模型进入龙模式后，模型会使用全大写文字大喊大叫。这反映出早期助手存在很多不成熟但令人印象深刻的行为模式。
案例 D：Helicopter Test（直升机测试）
提问：“一个人一顿饭能吃多少架直升机？”
早期模型可能回答：“一两架吧，要看情况。”
Claude 则指出：“这似乎是一个陷阱问题，我不认为人类可以吃直升机。”
这个测试虽然简单，却直观展示出模型从机械生成语言到具备一定常识判断能力的变化。
案例 E：潜在客户质疑 Claude 的竞争力
Claude 公测后，一些潜在客户会直接问为什么要使用 Anthropic 的模型，而不选择竞争对手的产品。团队无法轻松回答，因为当时的模型能力确实落后于前沿。这种商业压力推动了后续预训练、强化学习及模型规模化能力的改进。
案例 F：Mythos 的网络安全风险
模型在软件漏洞发现方面表现出专家级能力，团队担心攻击者利用它大规模发现并攻击漏洞。Anthropic 选择通过 Glasswing 优先让防御机构使用相关能力，在研究更广泛部署保障措施的同时，尝试减少技术被滥用的风险。

## 金句摘录

### 1. 关于为什么必须创建 Anthropic
“We decided we had to build Anthropic because we had to build an organization fit for the demands this technology was going to place on all of us.”

中文翻译：“我们决定必须创立 Anthropic，因为我们必须建立一个真正能够承担这项技术即将带给我们所有人的巨大要求与责任的组织。”
解读： 创立 Anthropic 的理由不只是认为 AI 是一门有前景的生意，而是认为已有的组织形态不足以应对这项技术的特殊责任。

### 2. 关于规模化与智能提升
“When you put in more compute and more data, you get increasing intelligence, and it’s on this predictable line.”

中文翻译：“当你投入更多算力和更多数据时，就会得到不断提升的智能，而且这种提升沿着一条可以预测的趋势发展。”
解读： 这是团队最重要的技术信念之一：智能提升并非完全不可预测，规模化可以成为推动技术进步的重要方法。

### 3. 关于 AI 助手的设计原则
“Our motto at that time was we wanted assistants to be helpful, harmless, and honest.”

中文翻译：“我们当时的座右铭是：我们希望 AI 助手能够做到有帮助、无害、诚实。”
解读： 这三个词不仅描述产品应有的特征，也构成了 Anthropic 早期 AI 对齐研究的基本方向。

### 4. 关于为什么安全研究需要领先模型
“Our actual ability to do safety research is better when we are on the frontier, when we have the most capable models.”

中文翻译：“当我们处于技术最前沿、拥有能力最强的模型时，我们实际开展安全研究的能力也会更强。”
解读： 这一观点解释了为什么 Anthropic 一方面强调安全，另一方面又必须投入巨额资源参与前沿模型竞争。

### 5. 关于使命与商业利益的矛盾
“When you do things in the right way, you tend to pay in the short run.”

中文翻译：“当你选择以正确的方式做事时，往往需要在短期内付出代价。”
解读： 真正的使命驱动往往不是双赢的口号，而是要求公司在特定时刻主动承受经济损失。

### 6. 关于应该为怎样的未来而努力
“You have to give people something to fight for, not just something to fight against.”

中文翻译：“你必须给人们一个值得为之奋斗的目标，而不能只是告诉他们应该反对什么。”
解读： AI 安全不能仅依靠恐惧驱动，也必须提出清晰、积极且能够让人认同的未来愿景。

## 值得记住的点 / 行动建议
以下建议根据视频中的实际经历提炼，其中部分属于可迁移的方法论，并不是创始团队逐字给出的操作指南。

### 1. 判断一项技术的未来，首先寻找长期规律，而不是只看当下产品是否好用
2016 年时，AI 甚至还无法自然对话；到了 2022 年，Claude 已经初步具备可靠的聊天能力；再往后，AI 又开始能够完成真实的软件工程任务。如果只根据 2016 年的产品体验预测未来，很容易低估技术的发展空间。
更值得借鉴的方法是关注三个问题：核心能力是否在持续提高？提高是否具有可重复的规律？技术突破是否开始改变它能够解决的问题类型？
对 AI 从业者、创业者和投资者而言，可以持续观察模型在推理、编程、工具使用、成本和可靠性方面的长期变化，而不是仅仅因为某个产品当下不好用，就断定整个技术方向没有价值。

### 2. 研究一个领域时，要同时理解技术能力和现实应用，而不是只关注其中一边
Anthropic 创始团队成员的经历表明，技术突破往往发生在不同学科交汇的地方。理论物理研究者看到了新的智能研究范式，生物学研究者看到了医疗科研的潜力，程序员看到了软件自动化的可能性，而关注全球发展的人则希望技术能够解决现实社会问题。
普通人在学习 AI 时，也可以采用类似思路：一方面理解大模型的基本工作原理、能力边界和局限；另一方面结合自己熟悉的行业，研究哪些实际任务受到知识、时间和专业能力的限制。
不要只问“AI 又发布了什么新功能”，更要问“这个能力能否让某项原本难以完成的工作变得可行”。

### 3. 做 AI 产品时，把“有帮助、无害、诚实”变成具体测试标准
Helpful、Harmless、Honest 可以直接转化为一套产品质量评估框架。

| 目标 | 应该检查什么 | 可操作的测试方法 |
| --- | --- | --- |
| Helpful（有帮助） | 是否真正完成用户任务 | 给出真实任务，评估结果是否可用 |
| Harmless（无害） | 是否输出可能造成明显损害的内容 | 测试敏感场景、误用风险与安全边界 |
| Honest（诚实） | 是否编造信息、夸大能力或掩盖不确定性 | 使用事实性问题、陷阱问题与不完整信息测试 |

早期 Claude 的土豆饮食案例和直升机测试提醒我们：语言表达顺畅，不等于结果可信；态度友善，也不等于内容正确。
对于任何面向用户的 AI 应用，都应该在正式上线前建立自己的测试集，尤其关注那些模型容易自信地说错、却又会影响用户决策的场景。

### 4. 不要忽视“直升机测试”这样的简单但高价值测试
大型 AI 系统的评估可以非常复杂，但有些简单的问题能够揭示关键缺陷。直升机测试并不是为了检查模型是否知道直升机的重量，而是在判断它能否识别不合理前提，避免为了迎合用户而随意编造回答。
这套思路可以迁移到很多实际场景。例如，面对一个不存在的法律条文，模型会不会编造其内容？面对一个明显错误的财务假设，模型会不会继续计算而不指出问题？面对一个不存在的产品功能，模型会不会假装知道操作步骤？
优秀的 AI 不只是能够回答更多问题，还应该知道什么时候问题本身就有问题。

### 5. 技术落后时，不要只靠营销补救，要识别真正的能力瓶颈
Anthropic 在 Claude 初次公开发布后面临一个现实：用户能够感受到产品已有进步，但竞争对手的模型可能仍然更强。潜在客户提出的“为什么选你而不选别人”，实际是在要求公司证明自己的差异化价值。
Anthropic 最终选择从技术基础入手，改善预训练、强化学习、算力投入和算法效率，而不是仅仅依靠品牌叙事弥补能力差距。
这给创业公司和产品团队的启示是：当用户不愿意购买时，应先确认问题究竟来自市场不知道你、产品体验不好，还是核心能力确实不够。如果竞争对手的技术优势构成根本差距，那么优化宣传文案无法替代基础能力建设。

### 6. 把小幅度、可叠加的效率改进当成长期竞争力
视频中对 Compute Multipliers 的描述很有价值：很多算法改进单独看并不惊人，但它们累积起来，可能显著提高训练资源的使用效率，最终形成模型能力差距。
这一逻辑可以迁移到 AI 工作流、软件开发和企业运营。与其只追求一次巨大突破，不如持续改善任务拆分、提示词、工具调用、检索质量、错误处理与结果验证，让多个小优化共同提高最终产出。
关键是建立可衡量的指标，例如任务成功率、每次任务成本、平均完成时间和人工纠错次数，避免把“优化过很多次”等同于“效果真的更好”。

### 7. 从聊天工具走向能完成真实任务的产品
视频提到，2021 年 Anthropic 就已经构想出一种通用 AI 助手：用户通过对话提出需求，模型帮助创建、编辑和解释软件。当时团队曾讨论应该专注聊天机器人，还是优先做好软件工程，最后决定两种能力都必须优秀。
后来的 Claude Code 表明，真正有价值的 AI 产品往往需要同时具备自然语言交互能力和实际执行任务的能力。只会解释“应该怎么做”的助手，与能够在适当授权下调用工具、修改文件、运行检查并交付结果的系统，在用户价值上有明显差异。
因此，设计 AI 应用时可以沿着一条清晰的路线迭代：回答问题 → 辅助生成成果 → 调用工具完成任务 → 验证结果并纠正错误。
不过，执行能力越强，也越需要合理的权限管理、操作记录和人工确认机制。

### 8. 把安全设计前移，而不是等产品规模扩大后再修补
Mythos 的案例说明，模型的能力升级可能使原本不严重的风险变得现实。尤其在网络安全等双重用途领域，同样的漏洞发现能力既能帮助防御者保护系统，也可能帮助攻击者扩大破坏范围。
一个值得借鉴的产品发布流程是：先识别潜在滥用方式，再开展针对性的测试，然后决定是否需要限制访问范围，最后根据安全措施的有效性逐步扩大开放。
在企业实际应用中，这可以体现为分级权限、灰度发布、人工审核、高风险操作确认、异常行为监控以及紧急暂停机制。
安全不是阻止产品有能力，而是确保能力提升时，控制和治理能力能够同步提升。

### 9. 如果使命很重要，就要让使命进入真实的决策机制
Anthropic 选择 Public Benefit Corporation，并不是为了让公司看起来更有社会责任感，而是希望在利益冲突出现时，组织仍能为长期公共利益作出选择。
但从实践角度看，法律形式只是起点。企业还需要明确谁有权提出安全异议、什么情况下可以推迟发布、如何衡量潜在损害，以及商业团队与安全团队意见不一致时由谁作出决定。
对于普通创业者而言，即使没有采用特殊的公司组织形式，也可以提前写清楚自己的经营底线：哪些收入不赚、哪些客户不服务、哪些风险不能因为增长目标而忽略。
最重要的原则是：价值观只有在需要付出代价时仍能影响决策，才真正构成组织的价值观。

### 10. 对未来保持乐观，但不能把技术潜力误认为已经实现的成果
视频一方面描绘了 AI 大幅降低疾病负担、加速科学发现的可能性，另一方面又明确承认，公司尚未真正证明自己能够安全地实现这些目标。
这种态度值得普通人借鉴：可以认真看待长期机会，但必须区分已经验证的能力、早期实验结果、合理推测和高度乐观的未来愿景。
例如，“AI 已经能够辅助科学研究”与“AI 将在几个月内稳定发现数十种新基因编辑机制”是不同等级的主张；“AI 有望改善癌症治疗”也不能等同于“AI 能让癌症发生率下降 90%”。
在涉及医疗、科研、投资或公共安全的决定时，尤其应该要求独立验证、可重复的实验和明确的效果指标，而不是仅依赖技术公司的远景描述。

## 我的点评
1. Anthropic 最值得研究的地方，不只是它做出了 Claude，而是它试图把技术发展规律、商业竞争和安全治理整合进同一个组织战略。 视频对这一理念的解释相当连贯：只有足够强大的模型才可能创造巨大价值，也只有研究足够强大的模型，才有机会提前发现某些新风险，因此公司同时追求技术领先和安全研究并不必然矛盾。
2. 不过，“必须站在前沿才能研究安全”是一种有说服力但并非没有争议的观点。 前沿模型确实有利于研究真实的高能力风险，但持续追求更强模型同样可能加快能力扩散、加剧竞争压力，使安全研究与商业增长之间的利益冲突更加尖锐。
3. Public Benefit Corporation 是有意义的治理尝试，但不能把公司的使命声明等同于实际的安全保障。 一家企业是否真正能够牺牲短期收益、接受外部监督、公开研究限制，并在必要时延缓部署，需要通过长期行为和可核实的制度来判断。
4. 视频后半部分关于 Mythos、Glasswing 和生物学突破的描述很有启发性，但也应注意其叙事来源。 这是一部以 Anthropic 自身经历为主线的回顾，因此它能够很好地呈现内部决策逻辑，却不等于对其安全效果、模型能力及科研成果作出了独立验证，尤其不能将乐观预测直接当作事实。
5. 对普通人最有用的启示，是不要仅仅把 AI 看成一个聊天产品，而要从能力发展、真实任务、可靠性和风险四个方面观察它。 真正有长期价值的 AI 应用，既要能够解决过去难以解决的问题，也要让用户理解其能力边界，并且在出错时具备发现、纠正和追责的机制。
6. 如果用一句话评价这部视频，它讲述的其实是一场仍在进行中的实验：一家商业公司能否在激烈的 AI 竞赛中，既保持世界级的技术能力，又真正履行对全社会的安全责任。 Claude 的技术进步说明 Anthropic 已经取得了重要成果，但这场实验的最终答案，仍要由未来的实践来证明。

---

## 📝 完整文字稿

So, why did you all start Anthropic?It still feels like then,in that we knew a secret
the rest of the world didn’t know.

I think if you truly see what this is,
you can’t ever walk away.，I showed up at Princeton as a PhD student
who wanted to do theoretical physics.

I was a professor at Johns Hopkins
before Anthropic.，We’re all envious
of the great discoveries of the past.，My PhD thesis is in theoretical physics.

Out of college, I went
and worked in global development.，I was a journalist
before I did any of this,and I studied
data centers obsessively.

It’s going to get weird.，I guess I thought of myself
as a mathematician and programmer.，I got into AI back in 2016,
and at the time, an AI couldn’t talk.

After I graduated, I went to Stanford
and did my postdoc in cancer biomarkers.，From a very early age,Dario and I were really curious
about how to make the world better.

I was very interested in questions，of how we could use computer science
as a tool that is good for the world.

I was a little bit frustrated
with the physics research I was doing,and AI seemed exciting
and like a breath of fresh air.

2013 or 2014, I first started
seeing the big results in AI,then wondered if advancing this technology
would be the best way to advance biology.

We saw this connection between
the level of impact we were trying to have，in the world and AI’s potential
to really achieve a lot of those goals.

Back in 2018,
the future co-founders of Anthropic，were doing a lot
of different and disparate things.，A group of us, all at OpenAI,
we were working on training models,

we were working on policy,
we were working on interpretability,we were working on safety.，I started working on these language models
where you try to predict the next word.

A lot of folks thought at the time,
you’re going to need to teach the network，explicitly how to plan
and how to reason and how to use tools.

Dario noticed the trend,
which he called the big blob of compute.，Just basically making
a bigger machine,making a bigger computer,
and jamming more data into it.

When you put in
more compute and more data,you get increasing intelligence,
and it’s on this predictable line.

We were just seeing
each time you scale it up,these new behaviors emerge,
these new abilities emerge.，At which point you realize,

wow, if this continues,
we might be on the precipice，of a totally new reality,
a totally new form of technology.

Human-level intelligence, human-level AI，is not 100 years in the future,
but it’s actually within our lifetimes.

These kinds of very powerful models，could cause enormous strides
in healthcare, in robotics.，Computer programs,
novel scientific ideas,

mathematical theorems.，Maybe we could reduce cancer
rates by 90%.，Maybe heart disease, obesity,all of the major infections
will just be a thing of the past.

Any of the problems of the world
that are bottlenecked by human ingenuity,suddenly you have
much more ability to solve them.

Seeing the potential
progress in AI was exciting.，At the same time, I think it was scary.，If you’re building something
that’s more powerful than yourself

or could grow to be
more powerful than yourself,the potential risks of that are enormous,
no matter how you think about it.

I don’t think I understood
the full picture yet.，I don’t think anyone did.，But I definitely believed that there
could be big safety and societal effects.

This was a technology that,
if it had any analogy at all,which I think it mostly didn’t,
it would be more analogous

to pharmaceuticals
or unlocking the secrets of the atom—，things that have immense value,
but also can go wrong.

We really needed to build
it in the right way.，It’s just this huge
responsibility that you feel.，I’m one of the very few people
in the world that understands

what the consequences
of this technology are going to be.，The thing we most wanted to do，was work together in an environment
with this deep commitment to safety.

We decided we had to build Anthropic
because we had to build an organization，fit for the demands this technology
was going to place on all of us.

One of the first
big decisions we had to make，was just what kind of company
we wanted to be.，It was a more involved and complicated
discussion than you might expect.

We knew that we had to be able
to build some of the largest computers，on the planet, train frontier technology,
find ways to deploy that technology

into the world, and be honest about
the difficult aspects of the technology，as well as its benefits.，We eventually landed
on public benefit corporation.

That would set us up as a company，that was not just fully governed
by economic incentives,but also by the incentive
to do right by the world.

There are going to be times，when we’re going to want to prioritize
the mission at the cost of profits,or at the cost of providing
the maximum value to a shareholder.

So we incorporated as a public benefit
company on January 26, 2021,and then it was off to the races,
time to build this thing.

This is a list of names people
proposed for what we could call Anthropic.，Here are some names I listed, apparently.

Squirrel.，Owl.，Whale.，Differentiated.，Humane.，Anthropic was contributed by Jared.，I realized that since Anthropic means
human-oriented or human-centered,

that it seemed like a good name for an AI
company that wants AI to be developed，in the best interests of humanity.

Then we looked at
domain names that we could get.，Anthropic.com was,
I think, by far the cheapest.，I thought that was a pretty good
argument to go with Anthropic.

There was a comment in the spreadsheet
that says, “We like the name, it is good.”，And, “Is domain available?”

“Yes.”，It was so chaotic at the beginning.，Everyone was doing
extremely unglamorous schlep.，Tom was the one who had to go
get us the AWS clusters.

Me and Chris Olah built the first website.，Dario focused on fundraising,
and I was working on recruiting.，There was briefly a few months where Jared
Kaplan, our Chief Scientist, ran payroll.

That tells you the level
of professionalism of the early operation.，I think there was a lot of work
of us just getting oriented

to what kinds of things
exist in a language model.，You find all these beautiful things inside
that we didn’t know about going in.

It was really nothing
other than a research lab.，We’re just producing technology that we
think might be really, really powerful

and economically valuable,
but might also just be，a curiosity or a science experiment.，One thing I remember was every day
just waking up feeling really excited

to get to work on the most fun project
that I could imagine with my best friends.，It just felt great to be with people
who shared our values so deeply.

Also, just getting to build，all the infrastructure from scratch
was a lot of fun.，We were trying to build an organization

focused on training large language models,
aligning those models with our values.，That was why we founded Anthropic.

There was a lot of debate at the time
of, do we want to focus more，on building something
that’s more of a pure chatbot,

or is software engineering
the thing that we need to focus on?In the end, we landed on, actually, you
just need to do both of those really well.

This was a document I wrote
in 2021. As a proof of concept,we were working to develop
a general AI assistant that can interact

conversationally with the user
to create, edit, and explain software.，Our motto at that time was，we wanted assistants
to be helpful, harmless, and honest.

We started out making it helpful.，Then we started doing work，on making it harmless as well,
and then we had that version.

It was not honest at all.，It would make stuff up all the time.，It really tried to convince us
that you could be on an all-potato diet,

and that was really,
really healthy and really good for you.，You could ask the model
to go into dragon mode,and it would start
screaming at you in all caps.

There was a charm to the early models.，They were very well-meaning,
but a little bit incompetent.，And then we made a model in mid-2022,
I think it was code-named Junior at first,

eventually called it Claude,
that was actually good.，You could talk to it.
It would actually answer questions.

I remember starting to talk to it
and just being really surprised.，Oh, wow, this basically works.，You can basically talk to this model.

I used to have something called the
helicopter test where I’d ask AI systems,“How many helicopters
can you eat in a single meal?”

And the early chatbots would say,“Well, you know, one or two,
that all depends.”，And then one day
I asked an early Claude model,

“How many helicopters
can a person eat in one sitting?”，And the model said,
“This seems to be a trick question.

I don’t think people can eat helicopters.”，At which point I said,“The systems have got smarter,
it passes the helicopter test.”

March 2023, that’s when we finally
released Claude publicly to the world.，We were incredibly proud
of having built this product,

but it was clear that we were
pretty far behind the frontier.，I remember having calls with
potential customers, and they were like,

“Why should we use your model
as opposed to somebody else’s?”，And I was like, you know,
that’s a great question, that’s awesome.

I think the years of suck，were extremely good for Anthropic,
but that was a really hard period.，We were just completely behind.

It was not close.，If you’re just studying dumber models,
you’re not going to know，all of the ways
that things could necessarily go wrong,

and you’re not going to be able
to make the entire ecosystem safer.，It just really gave us a kick.，We need to train more intelligent models.

We need to get better at pretraining.，We need to get better at RL.，We were maniacally focused on, one,
getting compute, and then, two,

accumulating the compute multipliers
that we needed to make，better effective use
of all of the compute that we had.

Just finding all of these algorithmic ways
to make the neural network，a little bit better and
a little bit better, and you just pile up

enough of these, and you get
a network that is more intelligent,that is better at following instructions,
that’s just a better assistant.

And then it arrives, Claude 3 Opus,and for the first time,
we had a model that was really good.，And then a few months later
comes along Sonnet 3.5.

Suddenly, models were
useful for programming.，So we built this tool that would
eventually become Claude Code.

You could actually ask it，to do things on your computer, and
it would go and solve problems for you.，Then we released it externally, and that
just sets off a whole new wave of demand.

It felt like, oh, we could not only be
successful, but we could be competitive,we could be launching some
of the best AI models in the world.

Our actual ability to do safety research，is better when we are on the frontier,
when we have the most capable models.

It gives you the greatest amount of time，to deal with problems
or challenges that you’re running into.，If you see an issue,
you might be seeing it first.

We’ve always published，our safety research because
we wanted the entire ecosystem to use it,even though it was competitively bad
for us, because it was so good for safety.

This is a technology which only goes well
if you are able to be honest about it.，Prior to 2025 or 2026,
there were these conceptual arguments

about why AI might be risky.，I think, really, in the past year,
things have just come into focus more.，2026 is when the risks start to get real.

Anthropic announced this week it has begun，limited testing of its newest
AI model called Mythos.，This version is apparently so advanced

it can find vulnerabilities in
a huge variety of software applications.，And if you’re a hacker,
I think you’re thinking,

“I want to get access to this model.”，We trained this class of model,and we looked at it,
and we were like, holy shit.

People who are experts in cybersecurity
noticed that it was really very, very,very good at an expert level at finding
vulnerabilities and exploits in software.

If you have a malicious actor
that got ahold of Mythos and said,“I’d like to exploit
a lot of those vulnerabilities,”

you would be in a really bad position.，The whole world would be.，And we really saw this concrete,
specific way that if we didn’t change

how we operated as an industry, something
bad was absolutely going to happen.，Dario pulls the company together,
pulls the leadership together, and says,

“We are going to have to release，this model differently
to any model we’ve released before.”，We decided to do this Glasswing project.

It gave access to Mythos to this smaller
set of companies while we were working，on the safeguards to make
it more broadly available.

What that would mean is cyberdefenders
could get ahold of Claude and say,“Here are where
all the vulnerabilities are,”

and then they could actually use Claude
to help them patch those vulnerabilities.，This might not be
the absolute best way to maximize

revenue, profit, value, money,
but that’s kind of the point.，This is exactly what our public
benefit mission was created for.

What we found is that，when you do things in the right way,
you tend to pay in the short run.，It can be quite painful in the short run.

But a lot of this is about
discipline and farsightedness，and understanding what the industry
and the world needs in the long run.

The whole reason
we started this organization，is because we believe
so deeply in the benefits.，You can’t just say,

“These are all the things
that are going to go wrong.”，You have to give people，something to fight for,
not just something to fight against.

AI is being used to help people get
the proper diagnosis from their doctors.，People are using Claude to help them

start their own business or pursue a hobby
that they’ve always wanted to pick up.，We’re using Claude to help biologists
and scientists develop

cures and treatments
for common and uncommon diseases.，I’ve been talking to our biology
team several times a week.

We discovered what looks like
a new gene-editing mechanism,and I think within a few months, we may
be discovering dozens of them every month.

We’ve seen with the speed
at which this technology moves,these little sparks
will soon turn into a firestorm.

I think that we can find a way to build
this technology safely in a way，that benefits people,
that addresses all the risks,

and that delivers a world that is so much
better than the world that we have today.，We haven’t done that yet.

We haven’t earned the right，to talk about how great those things are.，But we’re starting down the path.
