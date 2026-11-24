# Gemini 与通往通用人工智能之路：对话 Koray Kavukcuoglu

- 来源链接：https://www.youtube.com/watch?v=FORdPIWOH5k
- 作者：Google DeepMind
- 提取时间：2026-11-20 10:15
- 原标题：Gemini and the path to AGI with Koray Kavukcuoglu
- 标签：Gemini研发、通用人工智能、模型泛化、AI智能体、递归自我改进

## 🤖 AI 分析

## 一句话概括
Google DeepMind 核心研究者 Koray Kavukcuoglu 深入阐述了 Gemini 如何通过统一基础模型、真实产品应用、泛化能力、世界模型、架构创新和 AI 递归自我改进，逐步走向通用人工智能（AGI），并提出一个贯穿全篇的判断：AGI 不应该由某个考试分数或技术标签来定义，而应该由 AI 能否在现实世界中持续解决问题、获得人类信任并承担越来越多的实际工作来衡量。
本笔记只覆盖视频前 63% 的内容。

## 背景与主题
这期节目来自 Google DeepMind 官方播客 Google DeepMind: The Podcast，由数学教授、科学传播者 Hannah Fry 主持，嘉宾是长期从事深度学习与人工智能研究、如今负责推动 Gemini 技术发展的 Koray Kavukcuoglu。主持人回忆，2019 年第一次参观 Google DeepMind 伦敦办公室时，AlphaGo、AlphaStar、AlphaFold 等团队还相对独立，研究人员分别探索围棋、游戏、蛋白质和科学控制等不同方向；而现在，Google DeepMind 的研发规模已大幅扩大，越来越多研究围绕 Gemini 这样的通用模型展开。
Koray 也从伦敦转至美国加利福尼亚，参与推动 Gemini 的持续迭代，以及 AI 技术进入数十亿用户使用的产品生态。访谈并不只是介绍 Gemini 的功能，而是围绕几个更根本的问题展开：什么才算真正的智能？为什么产品是通往 AGI 的重要路径？当前大模型缺少什么能力？AI 能否最终自主设计比自己更聪明的 AI？
Koray 的整体立场偏向积极但并非毫无保留：他坚信当前技术正在沿着 AGI 的方向前进，也相信未来模型可能实现更强的物理理解、架构创新和自我改进；但他同时承认，当前模型仍存在明显的能力缺陷，完整递归自我改进尚未实现，许多关于未来技术突破的问题也没有确定答案。

## 核心观点

### 1. AI 研发范式正在改变：从解决大量独立问题，转向训练一个能解决大量问题的通用模型
2019 年的 Google DeepMind 更像由多个专业研究团队组成的实验室：AlphaGo 负责围棋，AlphaStar 负责《星际争霸》，AlphaFold 探索蛋白质结构，其他团队还研究核聚变控制等具体科学问题。这些项目往往需要针对特定任务设计算法、环境和训练流程，例如在核聚变研究中使用强化学习（Reinforcement Learning，RL）和控制方法。Koray 认为，过去这些研究都非常有价值，因为它们帮助团队理解了学习、规划、控制以及智能决策的不同组成部分，但如今更大的机会是把这些能力整合进同一种可训练的通用技术中。研发目标因此发生了根本变化：过去是针对某个科学问题训练一个求解器，现在是训练一个能够进入该科学领域、理解任务并解决许多相关问题的模型。 前一种模式主要产出具体问题的解决方案，后一种模式则希望产出可以反复迁移和复用的能力。如果这一方向成功，新增科学问题就不一定需要从零开始研发全新的专用 AI，而可以建立在同一个不断积累能力的基础模型之上。
这一转变可以理解为从“为每一把锁制造一把专用钥匙”，逐步转向“培养一个能够理解锁具原理、面对新锁也能寻找开锁方法的系统”。它并不意味着专项研究不再重要，而是专项研究越来越需要为通用模型提供能力、训练经验与验证场景。

### 2. 通往 AGI 需要三个共同驱动力：AI 研究、真实产品和科学探索
Koray 解释，Google DeepMind 选择研究方向时，主要考虑三个相互联系的因素：人工智能研究本身的技术目标、真实产品中的用户需求，以及科学研究能够提供的重大问题和能力挑战。 AI 研究者需要判断模型应该具备哪些能力、哪些算法方向值得探索，但单纯依赖实验室内部设想，无法充分理解真实世界到底需要什么样的智能。产品能够暴露这些需求，例如普通消费者会让 AI 处理哪些日常事务，开发者会用它解决哪些编程问题，企业会把它嵌入哪些业务流程。科学研究则提供另一类具有长期价值的挑战：模型不仅要回答已有知识，还应该帮助研究人员分析问题、提出假设，最终参与不同科学领域的研究过程。三个方向之间存在相互促进的关系：研究提升模型能力，产品检验能力是否有用，科学问题推动模型突破既有能力边界。 Koray 因此认为，完全脱离真实产品反馈、只在封闭实验室里追求 AGI，并不是一条可靠的发展道路。
这里隐含了一个重要的研发逻辑：产品不仅是模型训练完成后的商业出口，也可能是决定下一阶段研究重点的信息来源。例如，用户真正需要 AI 帮忙安排日程、执行任务，而不仅仅是回答百科知识，那么研究团队就需要更加重视规划、工具调用、权限管理和多步骤执行，而不能只优化知识问答能力。

### 3. AGI 不是通过一次考试获得的资格，而是 AI 逐渐变得有用、可靠、值得信任的过程
Koray 提出了整段访谈中最重要、也最有争议性的主张之一：不存在一个足以最终判定 AGI 是否实现的单一测试，他也不认为未来会有这样一个决定性的测试。 他的理由是，人类过去十几二十年不断设计新的 AI 测试，希望只要机器通过某个指标，就可以认为它拥有某种智能；但随着模型不断突破这些指标，人们又发现测试无法覆盖现实智能的全部内涵。与其执着于宣布某一天 AGI 正式诞生，他更关注人们是否愿意让 AI 参与工作、共同制定决策，乃至把一部分决策责任交给 AI。如果模型能在越来越多真实场景中表现可靠，用户就会像信任一位有能力的合作者那样，逐步把更多工作委托给它，而这种可以跨场景使用的可信能力，本身就体现了通用智能的进步。因此他把 AGI 看作一个 North Star（北极星式的长期目标），而把真实产品看作通往目标的一块块踏脚石：宏大目标告诉研究者要去哪里，具体产品则不断回答下一步应该解决什么。
这也解释了为什么 Koray 非常强调“有用性”。在他看来，一套系统即使能够完成很多令人惊叹的测试，如果不能有效帮助人类处理实际问题，那么把它称为智能也缺少现实意义。不过应注意，他讨论的是一种以实际用途和可信度为中心的 AGI 观念，并不是说科学界已经就 AGI 的定义达成了共识。

### 4. AI 能力的真正问题是“高低不均”：能解决高难度问题，却可能办不好普通人的小事
访谈中，主持人列举了用户希望 AI Agent（智能体）完成的典型任务：自动订机票、预订餐厅、处理日历、与旅行代理沟通，以及在不同服务之间协调工作。这些看似简单的日常任务，其实会遇到网络安全、Agent 通信协议、外部系统接入和实际执行流程中的复杂问题。主持人担心，Google 如果花费大量精力解决这类产品落地障碍，是否会偏离真正的智能研究；Koray 的回答非常明确：恰恰相反，解决这些问题就是研究通用智能的重要组成部分。 如果一个 AI 可以完成很难的数学或科学任务，却连帮用户预订一家餐厅都做不到，那么这种明显的能力落差本身就说明它还不够通用。他用 spikiness（能力表现的尖峰性、不均衡性）描述当前 AI 的特点：有些领域异常出色，有些领域又明显薄弱，而走向 AGI 的过程就是不断填平这些能力低谷。
这种观点把“产品工程问题”和“智能能力问题”联系在一起。真正有用的智能不仅要知道答案，还必须能够理解模糊需求、跨系统规划、处理权限和异常、执行操作、确认结果，并在失败时纠正自己的行为。复杂任务上的高分不等于普遍的现实可靠性，减少能力短板可能比继续刷新单项纪录更重要。

### 5. 真正的智能不是大量专用能力的简单叠加，而是能够迁移到未知任务的泛化能力
Koray 认为，机器学习已经基本证明了一件事：如果某个狭窄任务有充分的数据、合适的模型以及有效的训练流程，神经网络通常可以学会解决这个任务。早期 Atari 游戏研究、深度学习中的分类与预测任务，都说明模型可以利用数据学会特定规律；但把很多专项模型组合起来，并不自动意味着获得了通用智能。Generalization（泛化）和 Transfer（迁移）才是关键：模型能否把在已有任务中学到的知识，用在开发者没有专门训练、甚至没有预想到的新任务上。 这也是大型语言模型（Large Language Models，LLMs）令研究人员兴奋的原因——训练时主要输入大量通用知识和数据，发布后却可能在一些没有针对性优化的任务上表现出意想不到的能力。Koray 特别喜欢观察用户拿模型去测试研究团队原本没有专门优化的领域，因为这些表现更可能反映模型的泛化潜力，而不只是专项训练的成果。他同时谨慎地承认，当前模型距离真正跨越非常陌生的领域、实现强大的未知任务迁移仍然很远，现有成功不应该被夸大为无限泛化。
这一观点对应了两种不同的优化思路：一种是把已有考试做到极致，另一种是培养面对新问题时仍然有效的能力。Koray 更看重后者，因为 AGI 的核心挑战并不是预先穷举所有可能任务，而是让系统能够处理训练时尚未明确规定的问题。

### 6. Gemini 不是一个固定不变的架构，而是一条持续吸收新研究成果的技术演化路线
面对 Google DeepMind 是否过度押注 Gemini、从而可能错过下一次重大 AI 突破的质疑，Koray 强调：Gemini 不是永远固定在同一套网络架构上的产品，而是一个不断演变、以追求智能为目标的研发体系。 当前架构之所以被采用，是因为它在利用数据进行训练、计算梯度和更新模型方面具有当下需要的效率，但这并不代表未来一定继续使用相同架构。Google DeepMind 会持续探索其他算法、网络结构和研究方向，并把有价值的成果汇入主模型开发流程；Koray 将这套机制形容为一个 Funnel（漏斗），宽口负责广泛探索，窄口负责把成熟成果整合成可以部署的大规模模型。他表示，当前架构已经不同于六个月前的版本，而六个月前的架构也与更早的版本不同，并预计五年后的主流架构很可能再次发生明显变化。每一代 Gemini 都是研究人员结合上一代经验、手工设计和集成的一次独立工程，而不是按固定模板自动复制出来的产品。
这也解释了为什么大型 AI 实验室需要庞大的团队和多条并行研发线：有人正在完善当前版本，有人在准备下一代，还有人在探索更后续的版本。Koray 透露，当时用户看到的 Gemini 版本，其技术演化脉络至少已经持续一年，而在这一年中团队可能发布了大约六个不同模型，相关研发周期彼此重叠。看似一次模型发布，背后往往是持续数月乃至数年的探索、筛选、试验和系统集成。

### 7. 大模型已经具备一定“世界表征”，但距离真正理解物理世界还有明显差距
主持人问到 Koray 早年研究的 Learned Representations（学习得到的表征）：一个模型究竟在多大程度上真正理解了它看到的数据和世界。Koray 认为，生成式模型（Generative Models）的一个重要思想是，让系统通过学习数据建立内部世界表征，再观察它能否回答各种假设性问题、预测可能发生的情况，甚至组合出训练数据中没有直接出现过的事物。他用经典的 Pink Elephant（粉色大象） 例子说明：即使数据中未直接出现过粉色大象，模型仍然可能把“大象”和“粉色”的概念组合起来，生成合理的想象结果，这体现了一定的概念组合与泛化能力。但是，能够生成看起来正确的画面，并不等于真正掌握了物理定律；目前模型对物体碰撞、运动动力学、流体、气流和热传递等现象的理解，仍不能令人充分满意。Koray 特别区分了 Visually Correct（视觉上正确） 和 Numerically Correct（数值上正确）：前者只要求图像或现象看起来合理，后者则要求结果在工程计算和物理约束下也足够准确。只有从视觉合理性进一步走向可验证的物理预测与工程数值计算，AI 才可能成为真正可靠的科学和工程工具。
他对未来实现这种能力持强烈乐观态度，理由是 AI 系统本质上运行在能够执行计算的数字机器上，只要提供正确的训练方法、数据和环境，原则上就有机会学习完成更准确的数值预测。但这仍是一种对未来研究方向的判断，并非意味着现有生成模型已经拥有完整的物理世界模型。

### 8. AI 不必复制人脑：能源效率有差距，但未来架构可以不同于生物智能
主持人提出一个关于计算成本的问题：训练前沿 AI 模型需要大量算力，而人脑却能在极低的能耗下完成复杂认知活动，常见的类比是人脑运行所需功率甚至低于某些灯泡。Koray 承认，数字 AI 与生物智能之间确实存在显著的能效差距，也认为未来软件算法和硬件系统还有很大的效率提升空间。但他反对把“完全模仿人脑”设为必经路径，因为 Google DeepMind 的目标不是复制人类大脑的生物结构，也不是要求 AI 以与人脑完全相同的方式实现智能，而是创造能够帮助人类的智能系统。 当前数字系统虽然在某些方面耗能较高，却已经可以在部分计算任务中表现出超越人类的效率与规模优势，因此人脑与机器更值得关注的是互补性，而不是结构上的一一对应。谈到曾与自己在纽约大学（NYU）共事的 Yann LeCun 对 LLM 路线的批评时，Koray 也没有简单否定对方，而是承认未来五年完全可能出现不同于当前 LLM 的更优架构。
这一立场体现了一种技术上的开放态度：当前架构有效，不代表它是通向智能的唯一架构，更不代表它是最终架构。 因此，支持继续扩展现有模型与继续探索其他 AI 技术路线并不矛盾。Koray 认为，如果相信未来五到十年世界和 AI 的能力都会发生巨大变化，却假定模型架构始终保持不变，这本身就缺乏合理性。

### 9. AI 需要自主探索和生成新数据，但不应该因此彻底抛弃人类数据
主持人引用强化学习研究者 Richard Sutton 在 2019 年发表的 The Bitter Lesson（苦涩的教训），并联系 AlphaGo 与 AlphaZero 的差异，讨论人类知识是否反而可能限制 AI 的突破。在围棋这样的规则明确、环境可模拟、搜索空间相对受约束的任务中，AI 可以通过自我对弈探索人类没有尝试过的策略，而不是始终依赖人类棋谱或人类经验；AlphaZero 正是这一思路的重要例子。Koray 认可自主探索的价值：模型必须能够自行生成部分训练数据、主动尝试不同策略，否则就难以发现人类数据中根本不存在的解决方案。但他不赞成把这一趋势理解成未来应该完全远离人类数据，因为如果最终目标是创造服务人类的智能，那么模型仍然需要理解人类如何表达、如何思考、如何工作，以及人类真正需要什么。更合理的方向是同时保留两种能力：用人类数据建立对人类世界的理解，用自主探索突破人类已有经验的局限。 这种结合既可以避免模型被人类示范完全束缚，也可以降低 AI 在自我探索中偏离实际人类需求的风险。
由此可以看出，Koray 并不把“减少人类参与”本身视为 AI 进步的终点。对于围棋，最佳结果可以简单地用胜负衡量；但对于开放世界的智能系统，目标涉及人类偏好、实际用途、社会规范和现实任务，不能只靠一个封闭环境中的奖励指标来定义。

### 10. 递归自我改进正在局部发生，但完整的“AI 自己造下一代 AI”还远未实现
访谈后半部分讨论 Recursive Self-Improvement（RSI，递归自我改进），也就是 AI 参与改进自身，并用改进后的能力继续进行下一轮研究的过程。Koray 对这一概念的完整定义非常具体：系统不仅要生成代码或执行实验，还要能够自行发现数据、探索新架构、提出研究假设、运行并验证实验、训练候选模型、比较效果，并最终决定如何形成下一代模型。现阶段，包括 Google DeepMind 在内的前沿实验室已经能让 AI 负责上述研究流程中的一些局部环节，例如探索假设、构建实验、训练模型和分析结果，而 Gemini 也已经成为研发下一代 Gemini 所依赖的重要工具之一；但 Koray 明确表示，他们目前并不存在一个只需按下按钮，就可以全自动研发完整新一代 Gemini 的系统。主持人进一步提出一个关键的不确定性：RSI 是否必然产生越来越快的正反馈，还是可能很快遇到能力上限、最终只有边际改进；Koray 承认两种结果都有可能，没有人能够确定。当主持人把问题进一步推进到 AI 是否能自行完成类似从 RNN（循环神经网络）转向 Transformer 那样的重大架构创新时，Koray 表示他相信未来可能做到，但不能保证，而这种从已有技术路线跳向全新技术路线的能力，才会是一种真正值得重视的机器创造力。
这段讨论的重要性在于，它把公众想象中的“智能爆炸”还原成实际研究问题：自主改进不是简单重复训练，而是需要系统理解研究目标、构造有效实验、辨别结果、发现新知识，甚至重新设计算法本身。RSI 的价值不在于让 AI 无限生产新版本，而在于让 AI 更高效地创造真正对人类有帮助的新能力。

## 关键事实与数据
以下只整理文字稿中明确出现的信息。对于嘉宾的判断、预测或主持人的假设，单独标明，避免将其误认为已经验证的事实。

### 一、人物、机构与研究背景

| 名称 | 具体信息及在访谈中的作用 |
| --- | --- |
| Koray Kavukcuoglu | 本期主要嘉宾，长期从事深度学习研究，参与推动 Google DeepMind 的 Gemini 发展；曾在 NYU 与 Yann LeCun 共事 |
| Hannah Fry | 播客主持人、数学教授，负责从产品、智能定义、物理理解和自我改进等角度追问 |
| Google DeepMind | 讨论的核心研究机构，从过去多个相对独立的专项项目，逐渐发展出以 Gemini 为重要中心的通用模型研发体系 |
| Gemini | 访谈的核心 AI 模型系列；视频开场称其当时已发展至第四次迭代 |
| Yann LeCun | 深度学习研究者，对现有 LLM 路线的长期前景持批评态度；Koray 认为其对其他架构的探索很有价值 |
| Richard Sutton | 强化学习研究者，2019 年发表《The Bitter Lesson》，在访谈中被用来引出自主探索与人类经验的关系 |
| Nenad Tomašev | 主持人提到此前与其讨论 Agent 的实际落地困难，包括网络安全和协议问题 |

### 二、时间、数量和重要数字

| 数字或时间 | 视频中的具体信息 | 应如何理解 |
| --- | --- | --- |
| 2019 年 | Hannah Fry 曾参观 Google DeepMind 伦敦办公室，当时 AlphaGo、AlphaStar 和 AlphaFold 等团队各自开展研究 | 用于对比研究机构的组织和技术方向变化 |
| 约 15～20 年前 | Koray 回顾当时对 AGI 的设想，以及研究界习惯通过测试定义智能的方式 | 历史回顾，不是精确的里程碑时间 |
| 第四次迭代 | 开场介绍 Gemini 当时的迭代阶段 | 访谈原话，并非对外部产品版本编号的独立核验 |
| 数十亿用户 | Gemini 相关 AI 能力正在面向超大规模产品生态部署 | 说明产品部署规模，不代表数十亿人都已主动使用 Gemini |
| 六个月 | Koray 表示 Gemini 目前使用的架构与六个月前已有区别 | 强调架构持续演化 |
| 五年后 | Koray 预计五年后的 AI 架构可能与当前显著不同 | 个人预测，而非已确定的研发路线 |
| 至少一年 | 用户当前看到的 Gemini，其研发演化脉络至少持续了一年 | 说明模型开发具有较长周期 |
| 一年约六个模型 | Koray 举例说，在一个模型的演化周期内，团队可能发布约六个不同模型 | 示例性数字，说明多个研发周期重叠 |
| 未来两三个月 | Koray 认为团队届时使用的实验模型可能与当前大不相同 | 强调前沿研究模型的快速变化 |
| 七年零一个月 | 主持人调侃地回忆 Koray 在 2019 年对 AGI 到来时间的回答 | 是节目中的回忆和玩笑，不能当作可靠预测 |
| Gemini 13、14、15 | 主持人想象未来按一下按钮自动产出多个后续版本 | 假设性举例，不是已经存在的模型版本或公布的路线图 |

特别值得注意的是，文字稿没有给出 Gemini 的训练成本、训练算力规模、参数量、真实能耗、AGI 实现概率或者 RSI 自动化比例。虽然访谈讨论了这些方向，但不能从中推导出具体数值。

### 三、Google DeepMind 提到的代表性项目
- AlphaGo：围棋 AI，代表早期针对特定游戏问题开展的先进智能研究，也是讨论人类棋谱与机器自主探索时的重要背景。
- AlphaStar：用于复杂实时策略游戏《星际争霸》的 AI 项目，体现早期研究的任务专业化。
- AlphaFold：蛋白质结构预测相关研究，代表 AI 在重大科学问题中的应用。
- AlphaZero：通过自主学习和自我对弈掌握棋类策略，被用于说明 AI 可以发现人类示范之外的新方法。
- 核聚变控制研究：Koray 回忆过去曾利用强化学习与控制技术处理高度专业化的科学问题，现在更强调训练能处理整个科学任务领域的模型。
- Atari 游戏研究：用于回顾深度学习和强化学习在具体任务上的早期进展，说明模型通过数据和训练获得专项能力已不是最核心的未知问题。
- Gemini：整合多种研究成果、面向通用智能发展的主线项目，同时也是辅助后续 AI 研发的重要工具。

### 四、真实产品场景和技术难点

| 场景 | 用户最终想要的能力 | 暴露出的关键问题 |
| --- | --- | --- |
| 预订餐厅 | 根据条件找到合适餐厅并完成预订 | 真实执行、信息确认、异常处理、权限管理 |
| 预订机票 | 查询并选择航班，处理旅行安排 | 多步骤规划、外部工具接入、结果验证 |
| 日历管理 | 读取和协调日程 | 用户意图、数据权限、跨服务协作 |
| 旅行代理沟通 | 与外部服务协调行程 | Agent 协议、网络安全、交互可靠性 |
| Google Maps | 提供与位置和出行有关的辅助服务 | 地理信息与真实场景任务的结合 |
| Google Docs | 支持文档类任务 | 长流程操作、上下文理解与工作流 |
| Gmail | 支持邮件类工作 | 意图理解、敏感信息处理、操作可信度 |
| 软件工程与编码 | 帮助开发者处理现实生产任务 | 代码正确性、真实环境中的执行能力 |
| 科学研究 | 支持不同学科的探索 | 科学推理、可验证性、数值与物理准确性 |

以上场景有些是主持人提出的用户期望或产品整合方向，不代表视频已经证实 Gemini 在所有这些任务上都能完整自主执行。

### 五、模型能力与缺陷的具体例子
粉色大象实验： 模型可能从已有概念中组合出训练数据没有直接展示的“粉色大象”，说明具备一定的概念组合和生成泛化能力，但不能由此证明模型掌握完整的现实世界规律。
物理理解差距： Koray 具体提到了物体碰撞、动力学、流体、空气流动和热传递。他认为现有模型可以在视觉上生成合理结果，但在数值预测和工程计算方面仍不够可靠。
未知任务泛化： 一些模型发布后在研究团队未专门优化的任务上获得良好表现。这类能力比单纯完成预先设定的 benchmark（基准测试）更能激发 Koray 的研究兴趣，但他没有因此声称模型已经解决真正的未知领域迁移。
研发自我改进： AI 已能够参与研究流程中的部分实验、假设探索、训练和结果分析，却尚不能完全自主完成整个下一代模型的研发周期。

### 六、访谈中的重要概念对照

| 英文术语 | 中文含义 | 本期讨论的重点 |
| --- | --- | --- |
| AGI — Artificial General Intelligence | 通用人工智能 | 能在多种真实任务中表现出可靠的通用能力 |
| Generalization | 泛化能力 | 将学到的规律应用到未被专项训练的问题 |
| Transfer | 迁移能力 | 把某领域的知识或技能用到其他领域 |
| Agent | 智能体 | 不只回答问题，还能规划、调用工具和执行任务 |
| Spikiness | 能力尖峰性、不均衡性 | 模型在不同任务上的表现存在明显落差 |
| Learned Representations | 学习表征 | 模型从数据中形成能够支持推理和预测的内部表示 |
| Generative Models | 生成式模型 | 通过学习数据规律生成内容、回答假设性问题 |
| World Model | 世界模型 | 可用于理解和预测环境状态及其变化的内部模型 |
| Benchmark | 基准测试 | 衡量特定任务表现的标准化测试 |
| Visually Correct | 视觉上正确 | 结果看起来合理，但未必满足精确物理约束 |
| Numerically Correct | 数值上正确 | 结果在定量计算意义上准确，可用于工程验证 |
| Funnel | 研发漏斗 | 从广泛探索中筛选、整合出能进入主模型的研究成果 |
| The Bitter Lesson | 苦涩的教训 | 讨论通用计算与学习方法相对人工编码经验的长期价值 |
| Self-Play | 自我对弈 | 系统通过与自己交互生成经验并改进策略 |
| RSI — Recursive Self-Improvement | 递归自我改进 | AI 参与改进 AI，并将进步用于进一步研究 |
| RNN — Recurrent Neural Network | 循环神经网络 | 主持人用来与 Transformer 对比，讨论架构级突破 |
| Transformer | Transformer 架构、变换器架构 | 代表可能改变技术发展路线的重大架构创新 |

## 金句摘录

### 1. 关于 AGI 的定义
“We don't have a test for AGI. We'll never have a test for AGI.”

中文翻译：“我们没有一个能够判定 AGI 的测试。我们也永远不会有这样一个测试。”
这句话是 Koray 整套思想的起点。他并不是否认测试指标的价值，而是反对把一个有限的考试结果等同于完整的通用智能。

### 2. 关于研究的最终目标
“We are not coming up with benchmarks that define intelligence. We are trying to build it.”

中文翻译：“我们不是在设计一些用来定义智能的基准测试。我们是在努力真正创造智能。”
这句话指出了“优化测量指标”与“实现真正目标”之间的区别。测试可以帮助评估研究进展，但测试本身不应成为研究的最终目的。

### 3. 关于智能的本质
“Intelligence is transfer from these into something that you haven't seen before.”

中文翻译：“智能意味着能够把从已有任务中学到的东西，迁移到此前没有见过的事物上。”
它解释了为什么 Koray 更重视模型在未专项优化领域中的表现。能够完成熟悉任务当然重要，但真正令人兴奋的是面对新问题时的知识迁移。

### 4. 关于真正理解世界
“Right now the models are visually correct. I'd like them to be numerically correct in the engineering sense of it.”

中文翻译：“现在的模型在视觉上是正确的，但我希望它们能够在工程意义上实现数值上的正确。”
这是对当前生成式 AI 能力边界非常精确的概括。能够生成符合直觉的结果，与能够用于严谨工程和科学计算之间，还有很大的技术距离。

### 5. 关于 AI 研发与人类的关系
“I think it is critical that we anchor ourselves on human data.”

中文翻译：“我认为，将我们的研究牢牢建立在人类数据的基础上，是至关重要的。”
Koray 并不反对 AI 自主探索，反而认为它不可或缺；他要强调的是，突破人类现有经验与理解人类真实需求，应当同时存在。

### 6. 关于递归自我改进的不确定性
“I don't think anyone is sure, but I don't think we only do things that we are sure.”

中文翻译：“我不认为有任何人能确定答案，但我也不认为我们只应该去做那些已经确定能够成功的事情。”
这句话体现了一种研究态度：无法保证 RSI 一定带来智能爆炸，也不能因此否认探索潜在突破方向的价值。

## 值得记住的点 / 行动建议
以下主要是根据 Koray 的观点提炼的可操作方法，并非全部都是嘉宾逐字给出的建议。

### 1. 判断 AI 是否真正进步，不要只比较排行榜分数，要评估真实任务完成能力
关注 Gemini 或其他大模型的发展时，可以把评价标准从“最新版本在某个 benchmark 上提高了多少分”，扩展成“它现在能够可靠完成多少以前做不到的工作”。例如，如果一个模型数学推理能力提高了，但仍然无法正确完成一项涉及搜索、日程、沟通和实际确认的普通任务，那么它的通用能力仍有明显缺口。
可以为自己建立一套固定测试任务，覆盖知识理解、推理、工具使用、多步骤执行、失败恢复和结果验证等不同维度。每次有新模型发布，都尽量使用同一批任务进行对比，记录成功率、人工干预次数、错误类型以及最终结果，而不只是观察回答是否流畅。
尤其要区分三个层次：能解释怎样做、能演示怎样做、能在真实环境中可靠地做完。 这三个层次对应的能力差距，往往比单次聊天中的表现更大。

### 2. 做 AI 产品时，不要只从模型“能做什么”出发，还要从用户“为什么需要它”出发
Koray 强调产品是通往 AGI 的路径，对创业者、产品经理和 AI 开发者尤其有启发。真正值得开发的 AI 功能，不一定是技术演示中最令人惊叹的功能，而是能够减少用户工作量、降低出错成本、解决真实问题的能力。
例如，用户可能并不需要一个可以详细解释航空业历史的 AI，而是需要一个能根据预算和日程筛选航班、比较方案、确认限制条件并辅助完成预订的助手。对于产品团队而言，应该先理解这条任务链，再判断在哪些环节使用大模型、工具调用和人工确认机制。
一个实用的方法是：先记录用户任务的完整过程，拆分出信息获取、判断、决策、执行、反馈五个阶段，再分别评估 AI 在每一阶段能创造什么价值。让真实用户需求倒逼能力建设，比单纯堆叠功能更有机会形成具有长期价值的产品。

### 3. 优先解决能力短板，而不是无限优化已经表现优秀的环节
Koray 提到的 Spikiness 提供了一个很有价值的优化思路：如果 AI 在某些任务上已经非常强大，却在普通场景中频繁失败，那么继续强化优势未必是最有效的研发选择。
例如，一个 AI Agent 可能可以写出高质量旅行计划，但不能正确识别预订失败；能够生成代码，却不能在实际运行后定位错误；能够总结会议，却不能可靠提取下一步行动负责人和截止日期。这些弱点往往直接决定用户是否敢把完整工作交给 AI。
实际优化时，可以按任务流程建立失败清单，区分理解错误、规划错误、工具调用失败、权限不足、状态跟踪错误和缺乏结果验证等原因。先修复导致整条任务链中断的高频问题，再优化已经相当成熟的文本生成或推理环节。
对于真实产品来说，端到端成功率通常比某个单独步骤的优秀表现更有价值。

### 4. 构建可演化的 AI 系统，不要把当前最流行的模型架构视为永恒答案
Gemini 的研发方式说明，即使是规模庞大的前沿模型，也不是一次设计完成之后就长期不变。研究团队持续评估新架构、新训练方式和新能力，并通过并行研究与工程集成不断更新主线模型。
对于开发团队，这意味着系统设计应该尽可能降低对某一个模型版本、某一种模型接口或者某一套固定提示词的依赖。可以把业务规则、模型调用、检索、工具执行、结果验证等部分进行合理分层，保留替换底层模型以及独立评估不同组件的空间。
另外，可以建立类似研发漏斗的机制：允许团队探索多种技术方案，但要求每种方案经过可重复实验、真实任务测试和成本收益分析，才能进入生产系统。这样既可以利用当前成熟技术，也不会因为过早锁定某个方案而错失未来进展。

### 5. 在科研与工程中使用生成式 AI，必须区分“看起来合理”和“数值上正确”
这是整期访谈最值得科学研究者与工程师重视的观点之一。AI 能生成符合直觉的文字、图像、结构图或物理过程描述，并不能证明它完成了严谨计算。
例如，在流体力学问题中，一段动画可以看起来像真实水流，但如果质量守恒、动量守恒和边界条件没有得到满足，它仍然不能作为可靠的数值模拟。在热传递问题中，一张看似合理的温度分布图，也需要通过热传导方程、材料参数以及实验结果来验证。
因此，把 AI 引入科学工作流时，建议至少保留以下验证过程：
- 明确物理假设、变量定义和边界条件；
- 检查量纲、数量级和守恒关系；
- 对关键结果使用传统计算工具或数值模拟复核；
- 在有条件时使用实验数据验证预测；
- 区分模型给出的解释、推测和已经得到证实的结论。

更有价值的方向是让 AI 帮助科研人员提出假设、搭建模型、设计实验和分析结果，再与可信的科学计算、实验测量以及专家判断结合。这样才能真正提高研究效率，而不是只提高科研材料的生成速度。

### 6. 训练更强的 AI，需要把已有知识和自主探索结合起来
AlphaGo 与 AlphaZero 的例子表明，如果系统总是模仿现有的人类行为，就可能受到人类经验范围的限制。让模型通过自主对弈、模拟环境、自动生成测试案例或尝试不同策略积累经验，有机会发现训练数据没有直接提供的方法。
但 Koray 的提醒同样重要：自主探索不意味着完全放弃人类数据，尤其当 AI 需要在真实社会中服务人类时，理解人类意图、沟通习惯和实际需求仍然不可替代。
一个值得借鉴的研发框架是：
人类数据提供基础知识和目标约束 → AI 在可验证环境中自主探索 → 通过评估筛选有效经验 → 将新经验用于下一轮训练 → 回到真实人类任务验证。
在能够自动判断成功与失败的领域，例如某些数学推导、代码测试、规则明确的模拟任务中，这种方式尤其值得研究。对于难以定义唯一正确结果的开放任务，则需要更加谨慎地设计评价机制，避免模型只是不断优化某个不完整的代理指标。

### 7. 看待 AI 递归自我改进时，要关注研究流程的自动化程度，而不是“智能爆炸”的宣传
RSI 经常被描述成一个极具冲击力的过程：AI 设计出更强的 AI，后者又迅速设计出更强的下一代，最终能力指数级增长。但 Koray 明确指出，当前实际进展远没有实现完全自主的闭环。
因此，评价一家 AI 实验室的自我改进能力时，可以重点观察几个问题：AI 能否自己提出有价值的假设？能否设计实验并调用计算资源？能否判断实验结果是否可靠？能否基于结果修改算法？能否提出超出现有架构的研究方向？这些问题比“AI 是否已经能自己写 AI 代码”更能够反映研发自动化的真实深度。
尤其要注意，优化现有架构与创造全新架构并不是一回事。 前者类似在已有山坡上不断向高处攀登，后者则可能要求发现一座此前根本没有看到的新山。主持人用 RNN 向 Transformer 的架构转变作为例子，强调真正的机器科学创造力可能需要这种突破式探索。
此外，必须区分“AI 可以循环改进”和“AI 能够无限加速改进”。前者是一种技术机制，后者需要额外的实证支持；即使已经存在部分自动化研发流程，也不能据此推导出必然发生智能爆炸。

### 8. 研究 AI 的长期趋势，应同时关注模型能力、真实应用、架构创新和效率
整期访谈反复说明，单一指标很难描述 AI 技术发展的全貌。参数规模、基准测试分数、训练算力或模型发布频率，只能代表其中某个侧面。
如果希望长期判断 AI 是否接近 AGI，可以同时观察四类变化：第一，模型在陌生任务中的泛化与迁移能力是否提高；第二，真实产品中的任务完成率和可靠性是否提升；第三，世界建模、科学推理和自主科研是否出现结构性突破；第四，完成同等任务所需的计算资源、时间和能源是否持续下降。
这四类变化之间相互影响：模型效率提高可以支持更大规模的应用，真实应用提供新的研究反馈，科学任务暴露新的能力缺口，而新架构又可能显著改变模型能力和成本边界。
对普通 AI 用户来说，关注真正影响工作方式的能力变化，往往比追逐每一次模型版本号更有意义；对技术研究者来说，则需要特别关注那些能够扩大模型能力边界、而不仅仅是提高已有测试分数的新方法。

## 我的点评
这期访谈最有价值的地方，是 Koray 把 AGI 从一个抽象的技术终点，重新解释为泛化能力、实际用途、可信度和研究能力不断积累的过程，这种思路有助于纠正只看排行榜分数或模型宣传的片面评价方式。将产品应用纳入智能研究也很有说服力，因为真实任务往往会暴露实验室测试难以覆盖的问题，但“用户觉得有用、愿意信任”并不必然意味着系统真的具备充分可靠性，用户信任还可能受到界面设计、品牌和使用习惯影响，因此仍需要严谨的独立测评。Koray 对通用模型发展、物理世界理解和未来架构创新持乐观态度，但视频中提供的主要是研发判断与概念性论证，并没有充分的量化证据证明统一模型路线一定优于其他路线，或者未来一定能够实现数值精确的世界模型。对于递归自我改进，他承认目前只有局部自动化、加速效果也未确定，这种谨慎比简单预测智能爆炸更加可信；不过围绕自动研发的验证标准、算力瓶颈和错误累积风险，访谈还可以进一步深入。普通人最值得带走的不是 AGI 会在哪一年到来，而是学会用真实任务检验 AI，把它当作可以逐渐承担更多工作的工具，同时持续验证其输出，并保持对新技术路线的开放态度。

---

## 📝 完整文字稿

Welcome to Google DeepMind: The Podcast.，I'm Professor Hannah Fry.，Now the first time that I met our guest
on the podcast today,

he was dashing around
Google DeepMind's offices in London,scribbling equations on whiteboards,
directing blue sky projects

that would fundamentally alter
the trajectory of modern technology,all with the rather audacious goal
of creating intelligence.

if you're interested in AGI and at the end we need we need to work on agents.，And that is something
that we have been doing for a long while.

Quite a lot has changed since then.，These days, Koray Kavukcuoglu has swapped London for California，and those whiteboards for the even more monumental task

of driving one of the world's
most advanced generative AI ecosystems.，he is steering the development of Gemini, now in its fourth iteration,

and overseeing the rollout
of AI to billions of people at once.，But perhaps things still haven't changed all that much.

He is still pursuing that same goal
of creating intelligence.，Only now the technology
is finally catching up with his ambition.

And is he still dashing between projects?Well, let's find out.，Koray, a real pleasure
to welcome you to the podcast.

Thank you very much.，I don't know if you remember in 2019
when you gave me，a whistle-stop tour of of the Google
DeepMind offices in London.

Do you remember this? I do, I do.，And it was like over
there is the AlphaGo team,this is the AlphaStar team,
there's the AlphaFold team.

Yeah.，I mean, everyone was kind of
in their distinct groups.，Yeah. I mean, things have sort of
changed a bit since then, right?

a lot of things have changed since then.，Like we used to fit on a floor，and like we could walk around the floor.

I mean, it was a big floor,
but it's still a floor now things are，a lot bigger.，this is what happens when something starts
working, right?

Like we were exploring
many different things at the time,whereas now I think the biggest change is，we know that there is

the potential of building a sing-
single model, a single technology，that is going to deliver a lot of 
a lot of generalisation, a lot of results.

And that sort of brings
everything together and like，makes it bigger and bigger and bigger.，Because I remember
I was talking to you back then

about the work that you were doing
on fusion, for Mm-hmm.，example, which was like a very sort
of constrained, specific scientific

application.，Do you still see
those kind of things as important，or do you think that you can still get
there from this this one model approach?

at least for me, it's mostly the latter.，The reason for that is, yes,we did all those different things
and they all taught us something and like

when you look at even on the fusion side,
we were doing RL we were doing control，But the potential, the opportunity

that we have right now
is this single single algorithm，that can actually do all those things
and then more importantly actually

like being able to train
something that can do all those things.，So like we would still do
these kinds of science projects,

but like a big part of the aim
now is a bit different.，A big part of the aim
is to be able to train，the model that can actually execute
in that scientific domain,

for that scientific problem.，So like the idea that this comes
back to the model and you train the model，to be successful in that
rather than solving a single problem

there is the biggest difference
because once you actually train the model，then you can solve many problems there.

that's the big difference.，But then if you put those
two things together，that the team is much bigger than it
than it was before. Yes.

But that also you're all pursuing
this kind of common goal.，Presumably there's
there's all kinds of different avenues,

all kinds of different projects
that could combine to that end.，How do you decide what to pursue?there are several things
that combine there.

Like like one
is obviously as AI researchers，we have an idea of where AI should be
good.，The second one is products.

Products are critical.，Why? Because through those
we know what people need AI for.，Right?
Or you can explore where AI can be useful.

Like you can't do this in a black box.，You need to understand，either on the consumer side
or on the developer and enterprise side.

You need to understand how
you can actually embed this technology in.，And then third one is science.，As you said, like obviously we know that
like I mean, we all believe that science

is the biggest driver of progress
and making the models better and better，at different scientific domains
and then being able to take on

and help with research
in those different scientific domains，these three all combine together.，you mentioned products there.

I really want to ask you about this
because I know that you've argued，before that
that products are the route to AGI.

Just give give me the sort of
strongest version of that argument for me.，The strongest version of the argument is
we don't have a test for AGI.

We'll never have a test for AGI.，It's not like
we are going to have a benchmark，and then you are going to solve
that benchmark and then like I mean,

you are saying okay, like this is AGI
or not.，Right?Like AGI is something that
if people find it useful, if you trust it,

if you can work with it,the more you trust it to make decisions
for you or to make decisions with you,then it will start feeling like AGI
because with that trust you will offload

a lot of like just like you're
collaborating with the person,you offload a lot of decision
making there.，And that implies generality, generality to
be able to solve problems in real world.

Right?And that's
where you get with the products.，Like AGI to me
therefore is like this sort of，I explain it
as like the North Star, the goal.

Yes, but it doesn't give you as you ask
like what is the next step you should do.，products give you that.，Like they are sort of like the stones
that you go through

and each one of them like helps
you solve another thing.，Right?And through those
we really figure out like I mean, like

the idea that we can create chatbots,
but people just don't chat with it.，People actually start asking questions
and then we start getting into

oh okay, people actually like we can build
things that are like that，are useful in people's daily life.，We can build
things that are useful in people's work.

then we can get
into the economical usefulness,then we can look at okay,
what are the areas of economy，that actually an intelligence technology
should be impactful on.

Those are the ones that define of course
software engineering and coding,but they are different
areas of knowledge, right?

So trying to build AGI
without products in the loop,I don't think it's going to happen. Mm.，Almost like the usefulness of it

is part of the definition
of what makes it AGI.，Exactly.，Like otherwise why would you call it
intelligence if you know

that it's not it's
not useful to you at all?Like how is it intelligent then?Right, yeah.，Start with the application
essentially. Exactly.

Do you think when / if you get there，will will AGI just turn up as like a
a Gemini app on your phone?I mean, what what
what's it going to You know what I mean?

How how will people use it?This is another，thing that I have a little bit of a like a，little bit of a different perspective on.

Like again, I don't know
like what it means for it to like turn up，like like or we get there.，Like I think it is more about the journey
because go

back like decades,
go back 15 20 years ago.，there was always a definition of AGI.，We always try to quantify it

in terms of these benchmarks
or in terms of these tests.，And we always thought that if we do this,
then it will mean that

the models achieved some sort some kind of
intelligence and at least we have solved，some area of intelligence.

Right?We have always achieved those benchmarks.，We always thought we didn't actually
capture the gist of the intelligence.

And you can see that this is the regular
cycle that happens with research.，What is important is do we actually have
a technology that we trust more?

Every day,
every month new models coming up，and we see this, see models
becoming more useful in our lives.，We see us trusting these models
more in our work, in our daily life.

I think that's the progress, that's
the ladder that we should be climbing.，I am not sure about the threshold on
when we say it's AGI or not

because also certain things we do,
the models do really well.，Certain things they are really bad at.，And many of those things
that the models are really bad at slowly

they are getting better.，Like if they're a bit spiky at the moment
in terms of what they can do.，Yeah.，I mean, they are much less spiky than what
they were, but still they are spiky.

I guess what you're saying is that you're
sort of incrementally making it less Yes.，spiky as time goes on.，And that is by making the models
part of our life.

In terms of what people want though,
I mean they want an agent，that will book a flight for you,
that will sort out a restaurant for you,

that will interface with your calendar,
that will talk to travel agents.，but I know that when we spoke
to Nenad Tomašev about this,

it's really hard to do.，You have issues with cybersecurity,
with agent protocols.，I mean there's there's a lot of faff
basically in getting this stuff

to actually work.，So I guess my question is when when you're
building these commercial products,does that friction end up pulling you away
from advancing intelligence itself?

Not at all.，Like I mean, like because if we don't
then people get to ask the question，you can do all these things,
but you can't book a restaurant for me.

And that is the definition of spikiness.，And if we are talking
about a general intelligence，like if I can solve
all these like hard problems

I got to be able to book a restaurant.，Surely. Right? Surely.，So that's that's part of it.，I wouldn't make too much

of a differentiation between
all these kinds of tasks are important.，That is why，let's define intelligence as that and
these kinds of tasks are not important.

and that's the importance about products.，When you do those
you have to solve everything.，You don't get to choose

or I am going to solve this
or I am not going to solve this.，We are not coming up with benchmarks
that define intelligence.

We are trying to build it.，I really like that idea, but I also it
does make me wonder about whether you're，giving yourselves a a sort of bigger
challenge than anyone else

because you're trying to integrate Gemini
into maps and documents and，Yeah.，email and calendar and so on
which have like billions of users each.

Yeah.，that's much harder surely，than just saying here's this narrow
constrained version that we are building.

like conceptually harder, but also easier,
once you unlock that point，about generality I think that that
that sort of frees you up.

I always worry about，over optimizing for a single task Mm.，because，with machine learning
we already solved that.

We know how to do it.，The parameters of
that is very very simple.，Right?Like we know
that we have a class of models

that if you have a narrow task
and if you have data，that model will learn how to solve
that task.，I mean, this is what you were doing
with the Atari, Yeah.

right? All those years ago.，I mean, like even before that,
with deep learning we basically verified，that you can train a neural network
on data and if you have enough data

and if you have a model
you'll get the result, right?That is that I don't think
anyone questions that anymore.

There were times we were questioning that.，Like we are not questioning that anymore.，So then
like when we think about intelligence it's

not about a collection of these narrow
things,the intelligence
is the generalization over these.，Intelligence is transfer from these into
something that you haven't seen before.

That's the capability.，That's what amazes people with the LLMs.，because we are just
inputting the knowledge there

it actually generalizes
into all sorts of things，that you didn't think before, that
you didn't think that you build a model

for that kind of task,
but it actually does that.，That's the kind of generality
that you want, that like that is why

we think about scaling these
with more data and more capabilities，is the main route to intelligence
Like one of the nice things that happens

is you train a model
and then of course a lot of people take it，and then they try different kinds of tasks
and benchmarks that they like that

they have been working on.，And there are some domains and tasks
that no one thought about and people，try and say that okay, look this model
is doing this well on this kind of thing.

And to me those are the ones that are，that I really like because all of a sudden
okay, this is exciting.，Like we definitely did not optimize
for it.

Cuz it's the generality as you said.，Because it's the generality. I'm
not claiming，that these models generalize
and transfer to very unknown things.

I think on that part
we are still very very early.，But the goal of building intelligence,
the goal of building AGI

has always been the only single goal
and we are trying to find ways on，how to do that
in the best way that we can.

there's nothing else that is like
that is a goal for Gemini other than that.，There is this perception
that that Google DeepMind now

has a lot of eggs in in the Gemini basket
as it were.，how confident are you，that that you would notice
the next big thing,

the next big advance and be able
to implement it in your models?100% I think that's a good question,
but then that comes down to

Gemini is not a single architecture
that stays static.，It's not like that.，Right?Like it's
the it's the pursuit of intelligence.

And right now we have architectures，that give us the most efficiency in terms，of getting gradients from the data
that we have and update that model

And we keep exploring and researching，for different architectures
that will enable us to do that.，pretty sure 5 years from now we would be
looking at different architectures.

My goal is to make sure
that it's like a funnel.，Right now we have a particular
architecture that we are using.

It's different from what
we used 6 months ago, which is different，from what we used 6 months ago
and it has been evolving

and it has been evolving by taking ideas
and new developments from this funnel.，So when you say this funnel is

is the idea
that sort of the wider edge of the funnel，Yeah.，you're experimenting,
you're trying out different things but

actually putting it in a position
where it can reach a billion users is a，Yeah. different game altogether. Exactly.

because once something ends up in products
and such maybe a lot of people，have the idea that it's pretty much fixed
and it doesn't change much.

Whereas the way I look at every
generation of Gemini is a custom job.，It is，put together by hand，and there's no other version of it because
the next one is going to be different.

We go and put together the next one
by hand as well looking at everything that，what you learned from the previous one.

That's why we need the large teams
because while you are working，on the current version，there's a whole team
working on the next version

and there's a whole team
working on the next next version，so that like people build ideas slowly，and they go into they go into
what is right now.

the current Gemini that you see
it has a lineage of at least a year.，Right.，Like during the year maybe we released
like six different models.

So they all overlap,
So how different then is，the Gemini that I could have access to
and the ones that you're playing with?

the ones that I'm playing，with or we are playing with,
we have a lot more options.，And depending on the time, it might be
very different or it might be close.

It really depends on
what is on the pipeline.，if you ask me this question
before we released Argon, I would say

very different.，Now that we have Argon out,and we have other models in the pipeline,
it's closer.，But like if you ask me what are the models
you are going to play with in the next

like two, three months, obviously it's
going to drastically change.，So then with the things that you've been
playing with, do you think that you're

starting to see sparks of AGI?I mean maybe more than sparks actually.，Do you think that that we're there?Again, like I I I love this question.

Is it AGI?Is it AGI or not?Or when do we get to AGI?I think I asked you this in 2019. Right.，I don't know. I don't know what I said
like at that time.

You said seven years and one month.，Seven years and one month.，Here's what I would say.，like when I look at the progression
of things that are happening,

This,
I believe, is definitely the path to AGI.，But like to me it really does not matter
if we call something AGI or not.

You go back to 20 20 years ago, like
you would definitely call this an AGI.，Right.，But then like you live in this world
and you see those spikes

and the lows and the highs
and then you can say okay，like there are still these things
that it doesn't do.，Once it can book restaurants, Koray,
that's the last thing.

And just talking about 20 years ago,
I mean when you did your your PhD,I mean you you've been researching
in this area for for decades, right?

I know that some of your Sorry.，You don't look it.，I know，I know some of your，your early research was on
was on learned representations, right?

So so this idea of of how a system
kind of builds its own picture of the data，that it that it sees.，In terms of the models
that that you get to see,

Sort of how much conceptual understanding
do you think that there is?Okay, let me ask you a question back.，Like how do you
how would you know the difference?

I don't know. You're the researcher.，So that's the whole purpose
of doing the generative models, right?Like because you don't know exactly,
by building a generative model,

what you try to hope
is that as you can query the model，and as you can ask more questions
about hypothetical situations

and if the model is giving you realistic
answers, then you believe that it has，produced
accurate representation of the world.

Whatever the data that you put in
is the definition of the world by the way.，And like we can always argue the gap
between that world and the real world.

But at the end of the day, that's
what we believe the understanding，and the intelligence comes from
and that's the predictive power.

Right?Because if you have a model, if you have
an understanding that you can predict，things that can happen
hypothetical situations that can happen

even the ones that you haven't seen before
or the model hasn't seen before.，Like the canonical example would be
in the earlier days, pink elephant.

There's no pink elephant in my data.，Can I make my model
imagine a pink elephant?Yes, the models can now
imagine pink elephants now.

Does it mean that they，they can actually they've learned
the whole world and they understand?Oh, they they understood a lot of things,
but like I don't think that like

we are there,
that they understand the physics，and the dynamics and the collisions
well enough.，I don't think that they understand
the fluids well enough.

I don't think that they understand
the the air flow，or the heat transfer
and all those kinds of things well enough.

Right now the models are visually correct.，I'd like them to be numerically correct
in the engineering sense of it.

Right.，And and correct in the sort of physics
sense of it.，Exactly.
Okay. Do you think that's still to come?Do you think we'll get there? 100% Right.

Yeah, we'll get there.，Like because
these are computational machines，that can do any kind of computation.，if we actually train them in the right way
with the right data

in the right environment to predict
the right things, they should be able to，do accurate numerical computations

that can be part of that engineering flow.，And to me that is important because again，engineering
is the thing that makes the world work.

Right.，Because otherwise you don't end up，with this full representation
of, of the world that we are living in.

Exactly. Yeah.，I know one of the other things that you're
working on in in the early days，was about the efficiency
of of your systems.

you know more than anybody
how much it takes to train a frontier，model now, right?And and I sort of wonder about

Do you think that that is
just what intelligence costs?I mean when you compare it
to sort of a biological system,

the the sort of famous line
is that human brain，requires less energy
than a than a light bulb.，Do you think that we maybe missing
something fundamental

that takes so much more energy
to use these kind of，this version of intelligence than the one
that you see in biological creatures?

I mean clearly there's a difference.，Clearly there is，a system that requires much less power.，So hence there is a lot more
that we need to achieve

to get to that human level，efficiency from that point of view.，At the same time,
we are not building biological systems.

We are building digital systems.，And yes, they consume more power
and there's a gap there.，like the way I would think about it is

there are definitely systems,
both software and hardware,That can be more efficient，and more powerful than what we have today.

Will it actually lead us in the exact path
as the human brain?I don't think so
and I don't think that's our goal.

Like we are not here to necessarily
replicate the human intelligence，either in the wetware
or the software form.

As I said, our goal is to build
intelligence that is helpful to us.，And with the current technology
that we have, we are building algorithms

that can be efficient.，There are some things that we can do
a lot more efficiently than human brain，with our current systems.

And I think that complementarity
is critical.，Because there are some people who say that
that this isn't the right track.

I mean I'm thinking about Yann LeCun here
for example，who I know that you worked with closely
when you were at NYU.

he sort of says
that LLMs are a bit of a dead end，and that actually we should be thinking
about something different altogether.

you see it differently.，What do you think that he's missing?I think that the general idea
that we need to understand our world

and we need to build a generative model
for our world, I think that is a，That's a shared goal.，But obviously like in Yann's case,
like he has a specific idea

and he's someone who has proven
that he has good ideas.，Right? Like
I mean like I work it chose you，I a work with him. you as a PhD student

Right. was a good idea.，So like But he says this,
he doesn't think，LLMs is a neural network
architecture is the successful one.

That's great.，Like I mean right now I feel like，they are a successful architecture,
but as I said, 5 years from now

it might be a different architecture that
we are using and that's perfectly fine.，That's the research he's doing.

That's the research we are doing as well.，That's the funnel
that we need to continue doing.，we can't get stuck on what works right now
and imagine that 5 10 years from now

where we predict，that the whole world is going to change,
that our model is not going to change.，I don't think so.

there's also this idea about human data.，And I'm thinking here about the
the Bitter Lesson which Richard Sutton

wrote actually wrote it
in the same in in 2019 the last time we，we properly spoke on camera.，It was the most
pivotal year in the history.

For for those two events alone.，So yes.，but but the argument that he makes in
that is，that you can end up constraining a system
by putting too much human data in it.

The difference
between AlphaGo and AlphaZero,once you take away that human data,
you can end up with a system

that can accelerate beyond
what what it was previously capable of.，I want to get your take on this.，Do you think that

do you think there will be a point，when we step away from human data
and really see things take off?up yes and no.

I wouldn't categorize it as step away.，But like there's a lot of data
that the model needs，to generate itself and explore by itself.

And through
that it can figure out strategies，that the like in the human
data that you don't have.，So that's real.

Right?And you can exactly see
this in an environment，which is like fully observable
and constrained like Go.，the model can explore things
that the humans did not because

still that search
space is a big search space.，It's small compared to like，the general language of exploration space.

but by enabling the model，to explore by itself,
you are giving it more opportunity.，But it I don't think it has anything to do
with moving away from human data.

Especially again
if our goal is to build intelligence,I think it is critical
that we anchor ourselves on human data

because we need models that are useful
for us in our world that we can use，as tools, that we can actually rely
on, that we can work together with.

And that relies understanding
how humans work and humans like to work.，I think it's a really persuasive argument
the way that you put it that

why would you possibly not want
to put the human at the center of it?This other thing
that everyone's getting excited

about at
the moment is recursive self-improvement.，How you How do you define that?when we think about recursive

self-improvement, we think about a system
that can train itself，which means that like if you think about
the whole loop of researching a model,

that whole loop that a model can do，by itself,
that it can like explore new data,that it can explore new architectures,
that it can run experiments to verify

if it is like going to do the research
in this domain or in that domain,that it will verify the success of those
and then train the model.

And then like ideally train
multiples of these models，so that then it reaches
okay this can be the，this can be the next generation of it
so that it's that self-improvement loop.

We are a bit far away from that.，Where we are is like more closer to like 
there are pockets of areas.，If you think about like we talked

about the whole pipeline of research
that needs to happen to build a model.，And there are pockets of that pipeline

that we can rely on models to do the work，by themselves，and like go over different hypotheses，and like build models and train models
and look at the results.

And as this gets more and more and more,
we keep，getting closer to RSI.，think I think you're right that sometimes
the way that it's spoken about is almost

as though you go in and you hit a button
and it says give me the new version of，Right.，Gemini like Gemini 13
then 14 and 15 and da da da… Yes.

Like that is sort of how it's how it's，I think that's how like a lot of people
imagine, but like like to get there,

first you need models
which will understand first of all like，what is the goal, second
like what is the data, then what it means

to do research, what it means
to actually come up with a better，algorithm, what it means to，do experiments
at least in our own space, right?

So there's a lot of exciting research
that happens there.，And there are like improvements
that are happening.

Of course like when you，when you talk to anyone in like frontier
labs, this is one of the areas that，all frontier labs
like obviously us included,

we are very like focused
on, we are investing in.，but I also
I don't want to give the impression，that at least for us
it's not like we have a full RSI loop that

like yes, we are pressing a button
and it does everything by itself.，But it is true
that Gemini is one of the most critical

things that we rely on
while building the next version of Gemini.，there is a percentage of compute
that runs in Gemini that is

that isn’t under the control of the agents
that like they run experiments.，And and I think
that is just going to happen more and more

Do you think there will be a point，then where you press a button
and it gives you Gemini 13 14?As long as like we are clear about what
we expect from that 13 14,

yes, there might be.，But like I mean the trick is about like 
like anyone who has built，something, it has always about like
what do you actually want?

Like what do you want that goal to be?Again,
the goal is not RSI for the sake of RSI.，The goal is to be able to build something
that is useful for us, that we can use.

And the definition of that is very hard.，there is no single benchmark
that tells you what that definition is.

Of what you're actually aiming for. Yeah.，There there's，one other thing about RSI that that I
I wonder about.

There's almost this
sort of implicit assumption within it，that that that there'll be a flywheel,
that the better it gets,

that then it can start to accelerate
and really take off.，How how can you be sure of that，and that you won't end up in a situation
where actually there's sort of a

a cap on its capability
and then you just get to a position，where there's marginal gains.，either is possible.

I don't think anyone is sure,but I don't think we only do things
that we are sure.，Like that's，the whole idea of research that we explore
things that we think are possible.

And if they are possible, then they work.，And that's where we are.，I mean agents are very good
at climbing hills that that already exist.

But then thinking
about the I mean we've spoken a little bit，about the change in different
architectures, different approaches.

The jump
from RNNs to Transformers for example，sort of like a completely different
hill altogether.，do you think an AI system
can make that sort of a jump?

At some point it will, yes.，That's what I believe.，You can ask me are you sure?No, I'm not sure,
but I believe it is possible.

So like that's that's
that's what we should explore.，Like And that would be a real test.，That would be a good test.
that would be a real creativity.

And yes, like it could be.，And I think it should be possible.，I don't think we are there.
At least I haven't seen.

but I think it is possible
that we will get there.，Do you think
then that RSI could end up being this，this genuine scientific phenomenon
as opposed to just I mean

I think at the moment it's sort of a story
that we're we're telling ourselves.，20 years ago the whole AGI was a story
we are telling.

Now we all take it for granted it's
part of our lives.，that's the journey that we should be in.，If you're a betting man.

No, if you are if you are researching
exploratory frontier seeking，person.，What what would you put the odds on
that RSI will happen?

Proper RSI.，I mean, look, I'm biased.，My biased sample is, like,
obviously, like, I'll sample from yes,it will happen all the time,
until I'm convinced that it won't.

Then, But that's the thing about research,
right?research to me is the most subjective
thing that anyone can do in the world.

the measurement of research
is very objective.，It has to be.，But why someone goes and researches
a topic that until you actually prove

that it is true, it is not
known, is a very subjective phenomenon.，And that is you your creativity
and your motivation as a researcher.

So I want to also talk to you about safety，with with Gemini,
because one of the things that you were，researching was was reinforcement
learning for for years.

and presumably, during that time,
you spotted, algorithms coming up，with all sorts of ingenious ways，to work their way around the constraints
that you try and place on them.

How do you mitigate against those
now that we're in a world of agents?the old and the
and the new doesn't matter, I think.

Like, as systems get more intelligent,of course, like, they will find ways
to accomplish the task.，Now, the question is,
and a big part of research,

is building the right environment.，Because in the right environment, like,
where, like,cheating or shortcuts are not rewarded,
then the model won't learn about those.

it is important
that we create the right environment.，That's number one.，It is important that we actually,very carefully monitor

the training if, like,the agent for some reason builds up
those cheating behaviours,And then, like,
obviously, like, in real world,

that is why you need to continue，monitoring the agents，and make sure that like that
monitoring is always on on real time,

such that if the agent deviates，from what you intended to do,
you can actually interject.，And, like,
one of the most important things

for this is designing architectures
that are monitorable.，like, right now
our systems have chain of thoughts, Mm.

right?
They're not visible to the end user.，These are, like,
I mean, literally the model's thoughts.，And those thoughts being pristine,

they are being untouched,
is very critical for safety.，We pay a lot of attention
not putting rewards on those thoughts

so that the agent's thoughts
are in a way unfiltered.，And at execution time,we can monitor those because every action
that the agent will take

will actually first manifest in its
in its thoughts.，Together with the actions, we monitor
the actions of the agent, the environment,

what it does, the，the side effects on the environment,
and the agent's thoughts to build，a detector of is the agent

still executing on what the user intended.，But it's not just agent,
I mean, agents as well.，I know I know a lot of your earlier
work was about, sort of,

creating teams of agents
to to achieve a particular objective.，And now we're really in an era
where we're seeing, know, teams of agents

working together to sort of do
slightly more underhand things. Yes.，How do you monitor those?the job gets more complex. Mm.

especially with multi-agents.，There's an explosion of intelligence
that you can expect to happen.，But as long as you keep the thoughts,

you keep the communication channels
observable, detectable,and understandable,then I think you can still
the same idea of monitoring.

Of course, like, at scale still works.，Hence, that is why always anchoring
on what I find really useful is, like,

sometimes people question, do the thoughts
need to be in natural language?Yes, it needs to be.，It has two effects.

One, regularisation.，Two, we can actually introspect.，We can actually study what is going on
both agent to agent.

But a human can study
I guess, A human can，study, So and and that is important,
But I I do sort of wonder how,

now that you've got these systems
with multi-agents that that, you know,are sometimes working together,
but also that you're creating products

that are going out there
to billions of people quite literally.，has how you think about safety
changed through that time?

Inevitably. In what ways?In every possible way.，Like, I mean, like, from the days
where first, like, building intelligence

was more of a, like, an academic research
exercise where we were, like,we were training these things on games
and, like,

that the capabilities that the
that the models and the agents had，did not expand beyond，that game, beyond that environment.

But especially with coding and tools,like, the capability that the agents have，in the digital world is like，being able to get out of that environment.

So then the safety and security aspects
of both training the model，and deploying the model becomes
extremely important.

safety and development
should always go hand in hand.，Like, this is where I think we moved
from science of researching AGI

into building AGI, which is a lot
more of an engineering activity.，You don't imagine building
anything that is not safe.

And that's the mentality，that we should all have,
that we only build things that are safe.，but like I still, get comfort from knowing
that there are many different ways

we have found to develop technologies
that can be sensitive,you can create, like, air gaps or,
like, sandboxes around them and you can

you can develop that technology
and you can you can build something，that is safe to use in real world.，Do you think that that building things
that are used by so many people

simultaneously makes it easier，or harder to end up with something
that aligns with human values?Because they're going to stress test
it, right?

Oh, yes.，In in it I mean I，I mean, like, both ways, right?Like, it's easier because then you get
feedback from so many different

dimensions, so many different directions
But also at the same time,like, it is it is obviously harder
to get to that level.

This is, like, not any different
from the conversation we had about，building something narrow versus building
something general. Mm.

Right?If I were concerned with building
something that is only useful，for a particular task, I wouldn't
have too much of an alignment problem.

I know what task I'm solving.，But because I'm building
something that is useful in general,that is why we are talking
about the alignment problem

because the task comes in
real time from the user.，And you have to make sure that
the model follows what the user wants.

So like, yes, it is harder,
but the fact that I'm doing this across，a large population
means that I can actually understand

the true way that I can get the model，to tune for whatever user wants.，Like, and everyone wants something else.

There's been a lot of talk recently，about this idea that the labs
should slow down their research.，What's your take on all of it?

I think my take on it is，if on this path，we are having trouble
finding the next step,that is the step that we comfortable,
that we are safe with,

then obviously we shouldn't take and
like does it if it leads to a slow down，compared to whatever hypothetical criteria
that people have in mind

that should happen,
but I don't think that like,there is necessarily
a reason to slow down or，stop based on a criteria
that we don't know either.

every lab, I can speak for our lab,
that like we should be building，technologies that we know that like that
we can release to the world

and that it's a
it's a it's a safe technology to use.，We have to be clear about the,
the side effects of those.

We have to be clear
about the risks of using these.，That is why we are very careful about,
like, researching the mitigations

for the model that making sure
that the alignment is there, making sure，that the model doesn't do things
that we think are, like, clearly unsafe.

We work with experts
outside of the company，to give them the models
so that they understand the capabilities，and they can help research
both the safety aspects, but also use it

in their domains
to understand the impacts of the models.，So all these machinery
is there in a way like,if you go back two years ago
releasing the models,

did not involve anyone of these
anyone of these steps，because we knew that the impacts
of the downstream impacts of the models

were much more limited.，Because the thing is, I mean, I think that
you've proven over and over again，that safety is really genuinely something
that you care about very deeply. Yes.

I think that there's this fear,
I suppose, in the general public，that, more generally across the board,
it might get to a point

where it's difficult to make a sort of
independent safety decision，when ultimately the labs are in a race
with one another.

Are you getting that sense from people?I I am definitely getting that sense and，I think,we are，we are not doing a great enough job

to explain all the，all the mitigations
we are putting in the model，and all the risks that we foresee, but，also how we deal with those risks.

again, I can talk for myself,
the competition aspect，is not something that gets in the
way of doing the right thing.

And it shouldn't.，Right?I can understand the worry there,
but this is why we also work，with governments
before releasing a frontier model, we work

with the government
to, like, do the safety testing.，We are working in ourselves
to make sure that we build mitigations

that we think are going to produce a model
that is robust and safe enough，for people to use, like,
without unintended side effects.

All these things are there，because we care about the technology，and the technology
being safely in people's hands

I mean, I think that there is this
big conversation about competition. Mm.，Can can you even tell who's winning?

I I guess this is a really a question
about benchmarks, right?But but lots of these benchmarks
are becoming saturated,

they're becoming contaminated
by the training data.，I mean, it
everyone talking about it being a race.，But but can you even tell
who's in the lead?

I think like, we all have different
intuitions and notions about, like,what quality means and where we latch onto
in terms of quality.

But your question about benchmarks
is right and I think in the grand scheme，of developing intelligence, benchmarks
are serving a different purpose.

As I said, benchmarks are not there
to measure oh, did I reach AGI or not?Like, in a way, nowadays
benchmarks are there to either measure

the capabilities of
models in a particular domain，or if you are doing really，bad on a benchmark, like, there are, like,
you should think about, okay,

maybe there's an interesting question
there that people actually find useful.，And your model is not doing well there

So the example that I give is,
if I don't show，any math data to this model,
I don't expect it to to know about math.

you're not going to teach the model，to ride a bicycle and then expect
that it's going to ride a motorbike.，Like, like, that's not going to happen.

That's not the kind of generalisation
we are looking at.，So if if if a benchmark tells you
that you're not doing well, like,

these, like, like, 1
2% differences is a different story.，But like to me
the most important thing about benchmarks,

if if a model is doing really well
that there's something interesting there，because either
there's a bug or a mistake somewhere

or there's some interest
and if people find that，benchmark interesting,
there's something some interesting task

that we didn't think about.，And if we want models
to be useful in our world with people,then I need to train my model
to be good at that task.

Of course,
what I'm going to do is, like, I'm，going to figure out
how can I formulate that.，I'm going to create environments, I'm
going to collect data, and then I'm going

to train my model with the expectation
that it's going to do better on the test.，That's why gradually we see
all these benchmarks getting saturated

because the models are getting better
in many different areas.，That is what it should be.
That's what progress looks like.

And then, of course,
then we explore new benchmarks.，What has happened，in the history of machine learning over
years is playing out over weeks.

But then,
do you think this will keep going，that it's just，you saturate the benchmarks,
you have new benchmarks,

you saturate those benchmarks and so on
and so on and so on?That's how we train the models, don't we?Yeah. Yeah, I suppose.

Right?Like, I mean, I'm not very, like,
concerned about the benchmarks themselves.，Like, I mean, at the end of the day,

you we optimise the models to accomplish
some tasks.，It is more important to pick
those tasks right.，That is where products are useful As I
said, like, I know that as AI researchers,

there are some tasks that we want
the model to be more useful at.，And as scientists
in different areas of science,

we know that we need the models
to be better and useful in those areas.，But it's like the benchmarks
are a way for it to highlight

Exactly. maybe the gaps that exist
in the model Exactly.，And I guess the，the some billion users that you have
are also pretty useful for that, too.

Of course it is because as I said, like,
I mean, there are many things，that is very hard
to codify as a benchmark.

So the feedback that you get
from the users and that experimentation，is a big guiding point.，And this is even true on for things
like coding.

Coding is not just about writing
correct code, right?Like, like, 2 years ago, like,
all the models were reaching, like,

like, almost top human level
on competitive coding competitions.，But like it's not like the code
that we write day to day.

Of course.，You need the models to be able to work
with a software engineer，and the software engineer
should find the methodology of the way

the model works useful for them
so that they use it.，So even things like coding and scientific
research, you are going to work

with a mathematician, like,
you have to work with a mathematician.，You're going to work with a chemist,
you have to work with a chemist.

You need to understand
what they expect from a model.，Which is different
to just solving an Olympiad style problem.

Yeah. Exactly.，Okay, so let me ask you this then.，If I come back here in seven more years,
seven more years.，seven more years.

Okay.，Who's going to give the tour then?I don't know.，Maybe not probably not me.，Gemini.，That's possible.，Maybe we'll Wait, have not robots. you?
Where will you be?

I don't know.，Like, seven years is an eternity.，But like what I hope is that
we'll have robots here，that will hopefully,
like, help with a lot of things.

I mean, I hope that 7 years time
when you visit, yes,I will be here
and like we'll have the conversation.，But also at the same time, like,
genuinely,

the reason I I like
I said I hope not me is like I hope that，I enjoy, like, growing a team.，I hope that there will be many people here

who you would be excited
to have a chat with.，What do you think
AGI will look like by then?Will it Look like.

Well, be like act like.，Will it be able to book me a restaurant
finally?Finally, yes.，I think that's the that's the real test
That's the real benchmark.

the real benchmark.，my hope is and I think maybe naively,
I've been saying this for a long while,I expect that, like,
we will think that it is normal

that we have this really intelligent thing
that is like that，we can access through our phones
or our tablets.

but also，in our professional lives,
I think the opportunities will be much，much much bigger because any question
you have, the amount of progress

you can make in the minimum
amount of time will be very different.，Something to potentially look forward to.，Indeed.

Koray, thank you so much for joining me.
Thank Amazing.，very much for the conversation.
Thanks a lot.，There are plenty of people
who are out there

making these convincing arguments
that a focus on improving the current，generation of models
might be a distraction

from the next big breakthrough.，But I have to say I was very persuaded
by Koray's idea there about using people

as a compass because intelligence
doesn't exist in a vacuum.，And if AGI is ultimately about matching
or surpassing human capabilities,

then understanding
what people actually need from，these systems
doesn't just make commercial sense.，It might be one of our best routes to
making sure that they are aligned with us.

You have been watching Google DeepMind:
The Podcast with me, your host Professor，Hannah Fry.，As ever, we have plenty more episodes
coming up later in this series.

Make sure to subscribe
so you don't miss them.
