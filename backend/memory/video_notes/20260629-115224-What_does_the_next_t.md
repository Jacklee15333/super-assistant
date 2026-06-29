# 下一代 AI 训练范式会是什么样？

- 来源链接：https://www.youtube.com/watch?v=20p5-kQXF_Q
- 作者：Dwarkesh Patel
- 提取时间：2026-06-29 11:52
- 原标题：What does the next training paradigm look like?
- 标签：AI、强化学习、通用智能

## 🤖 AI 分析

## 一句话概括

视频讨论了以 **RLVR（Reinforcement Learning with Verifiable Rewards，可验证奖励强化学习）**为核心的现有训练路线是否足以通向通用智能，并指出真正的下一代训练范式可能必须解决三个难题：在不可重复的真实环境中高效学习、把部署阶段获得的经验压缩回模型权重，以及针对不同用户和任务进行持续学习。

## 背景与主题

当前前沿 AI 实验室正在大量建设可验证、可重复运行的强化学习环境，希望模型在编程、数学和各类数字任务中反复试错，最终学会通用的问题解决能力。支持者认为，即使训练阶段消耗海量数据和计算，只要训练成本能够被数十亿次推理调用摊薄，模型在实际会话中足够聪明、高效即可。作者则追问：这种方法能否从容器化的编程任务，真正泛化到创业、诉讼、投资、政治等无法重置和并行复制的现实领域？

视频以计算机操作进展较慢为切入口，说明“结果可验证”还不够，训练目标还必须具备可大规模反复刷取的 **grindable（可刷取性）**。作者最终把问题指向 **continual learning（持续学习）**：模型在部署中接触了最有价值的真实信息，却无法像人一样把经验压缩成长期能力。文字稿在讨论“不同用户、公司和任务需要学习不同知识”时中断，因此结尾论证并不完整。

## 核心观点

### 1. 当前训练路线押注：大量可验证任务能够塑造出通用问题解决能力

一些研究者认为，只要让 AI 在成千上万种多轮交互环境中追求接近 100% 的任务成功率，就可能训练出通用智能的基础结构。模型在这些环境中需要制订计划、执行操作、观察失败、修正策略，并在越来越长的时间跨度内完成目标。这种训练并非只教会模型某一道数学题或某项编程任务，而是在反复强化一种跨任务的问题解决过程。其核心假设是：如果模型在足够多、足够复杂的可验证环境中掌握规划和纠错能力，这些能力就会迁移到训练时没有见过的问题上。

### 2. 训练阶段样本效率低，不一定意味着部署阶段的模型也低效

作者此前曾批评现代 AI 训练需要极其庞大的数据和试错次数，模型的训练样本效率远低于人类。支持现有路线的人会回应，这种低效率主要发生在一次性的训练阶段，而训练成本可以被模型未来经历的数十亿次会话摊销。真正重要的不是模型用了多少训练样本，而是模型进入单次会话后，能否快速理解任务、利用少量信息解决新问题。随着强化学习规模扩大，AI Agent 的确已经能够在更长时间内完成更复杂的编程任务，这一点使用过编码模型的人可以直观感受到。

### 3. 超长上下文可能暂时替代持续学习，但无法彻底解决问题

持续学习通常意味着，模型根据部署阶段获得的新经验更新自身权重。反对者认为，如果 **in-context learning（上下文学习）**足够强，模型未必需要把每一次工作经验重新蒸馏进参数，只需把相关信息放进越来越长的上下文窗口即可。视频举例说，企业员工可能入职六个月后才能真正产生净价值；假如模型能把相当于六个月工作的资料完整放入上下文，它也许能在一次会话中获得类似熟练度。

Transformer 架构已经通过多种创新显著提升可处理的上下文长度，因此有人期待未来出现近似“无限”的上下文窗口。但作者认为，这只能让模型临时携带经验，并不等于模型真正形成了新的长期能力。上下文会结束、缓存会被丢弃，而且不断积累所有历史信息在成本和规模上都不可持续。

### 4. 计算机操作进展较慢，说明“可以验证”不等于“容易训练”

计算机操作看起来是非常容易验证的领域：可以检查 Etsy 商品是否下单并送达、活动场地是否完成预订、税务申报是否提交。按理说，这些任务和代码测试一样，都存在相对明确的成功标准，但计算机使用 Agent 的进步却明显慢于编程和数学。作者认为，一个重要原因是模型在预训练阶段接触到的高质量多模态操作数据远少于代码和文本数据。

更深层的问题是，训练环境不仅需要可验证，还要能够大量并行、反复重置，并从完全相同的起点重新运行。编程任务可以复制一千份相同的软件仓库和容器，让一千个 Agent 同时尝试补全同一个功能；真实网站却无法承受一千个机器人反复执行相同结账流程。结果可检查，只解决了奖励信号问题，没有解决训练数据能否低成本、规模化生产的问题。

### 5. 可重复模拟器是 RLVR 成功的关键，也是它最明显的边界

作者用 **grindable** 描述适合强化学习的环境：可以从同一起点生成大量 rollout，稍微改变模型动作，再比较不同轨迹最终产生的结果。编码环境具有确定性、可回放性和低重置成本，因此实验室能让大量 Agent 并行探索，再用测试结果筛选成功轨迹。计算机操作也可以通过复制 Slack、Gmail 和常见网站来构建训练模拟器，但制作高保真克隆目前仍然劳动密集，难以扩展到整个互联网。

当 AI 编程能力进一步增强后，模型或许能自行重建这些应用，从而同时解决两件事：一方面生成计算机操作训练环境，另一方面把“从零复刻完整应用”本身变成高价值的编程强化学习任务。然而，即便计算机使用因此得到突破，这种方案仍主要适用于能够数字化和模拟的任务，不能自然覆盖所有现实能力。

### 6. 创业、诉讼、交易和政治等领域无法通过大规模平行 rollout 学会

如何训练 AI 从零创建一家成功企业、赢得一场诉讼、完成一个盈利交易日，或者帮助候选人赢得选举？这些任务的结果通常需要数月甚至数年才能显现，并且高度依赖客户、竞争者、监管者、市场和社会情绪等持续变化的外部环境。你无法复制一千个完全相同的现实世界，让一千个 Agent 从同一时点建立公司，再通过轻微扰动动作来精确识别哪项决策导致成功。

这类环境具有 **reset-free（不可重置）**和 **non-stationary（非平稳）**特征，本就是强化学习领域的已知开放问题。真实互动数量有限、反馈模糊、因果链漫长，因此模型必须从稀缺且不结构化的信息中提炼规律。作者认为，如果 AI 要掌握人类已有乃至尚未拥有的全部技能，就必须获得远高于当前训练体系的样本效率。

### 7. RLVR 能否从数字任务泛化到现实世界，是整个路线最关键的经验问题

前沿实验室正在押注：只要在足够多的容器化、可复现环境中进行 RLVR，模型就会形成一种高度通用的 Agent 能力。理想情况下，模型不仅能完成训练任务，还能在一次会话中根据新信息迅速学习陌生技能、规划长期行动。作者用两个极端思想实验说明这种预期：如果把模型放到 **1948年**，它能否比 **Lyndon B. Johnson（林登·约翰逊，LBJ）**更懂得如何赢得参议员席位；如果在 **2002年**给它 **1亿美元**，它能否建立一家类似 SpaceX 的公司？

问题在于，从白领数字任务中学到的策略，是否真能迁移到政治博弈、组织建设和长期商业竞争，尚未得到证明。即使把强化学习环境支出从数十亿美元提高到一万亿美元，也不能仅凭规模断言会在上下文窗口中产生完整的人类式通用智能。这最终是一个需要实验回答，而不能靠口号解决的问题。

### 8. 短时域训练未必能自然泛化为长时域能力

作者引用 **Dario**——结合语境很可能是 Anthropic CEO **Dario Amodei**——的一段话：“RLVR 的泛化能力不是无限强的。”Dario 在解释长上下文性能下降时指出，模型训练时使用的上下文长度和实际服务时使用的长度是两回事；如果只在短上下文上训练，却在超长上下文中运行，性能可能出现退化。作者由此推断，短时域强化学习也未必会自然产生长时域规划能力。

如果模型主要在几分钟或几小时可以完成的办公任务上训练，不能假设它会自动学会用数年建立企业。要获得长时域能力，可能必须直接在更长的任务轨迹、更复杂的记忆体系和更接近真实世界的反馈中训练。这进一步放大了训练环境构建、信用分配和样本效率问题。

### 9. 部署阶段产生了最有价值的数据，但现有模型无法真正吸收

作者称，实验室约有 **30%—50%** 的计算资源没有直接用于改善模型能力；该比例的具体口径在文字稿中没有进一步解释，需要谨慎引用。更大的浪费在于，模型已经广泛进入企业和社会，接触大量组织特有知识、真实工作流程以及自身在实际场景中犯下的错误。这些信息往往比实验室预先构造的基准测试更有价值，因为它们揭示了用户真正如何使用模型、此前采用什么方法，以及模型在哪些复杂环境中不可靠。

作者将当前模型比作一名天才研究生：已经接触大量理论，却从未被允许通过真正的实习积累经验。AI 每天参与无数任务、看到大量专业上下文，却不能把这些经历稳定转化为长期能力。除非经验能够回写到模型权重，否则绝大部分部署学习都会随着会话结束而消失。

### 10. 真正的持续学习需要“压缩经验”，而非无限扩大记忆缓存

模型不能随着用户数量增长，无限累积更大的 **KV cache（键值缓存）**，这在存储、计算和调用成本上都不可扩展。人类大脑也没有参数与激活值的整齐分界，更不会随着人生经验不断扩大头颅容量；人的学习包含某种压缩过程，把大量具体观察凝结成直觉、抽象和整体知识。作者提到，一些具有类似学者症候群记忆能力的人，可以高保真回忆随机数字表或无意义音节，但过量的细节记忆有时会妨碍抽象、隐喻和概念理解。

因此，持续学习的目标不应是让模型随时逐字回忆全部历史，而是把正确的直觉和高层规律“凿入权重”。问题在于，一旦进入权重更新，模型又会失去上下文学习那种单次样本效率：现有在线学习系统通常需要在数百万用户中反复观察同一个目标，才能形成稳定改进。如何像人一样从少量、各不相同的个人经验中学习，同时避免灾难性遗忘、隐私泄露和能力退化，仍是下一代训练范式的核心难题。

## 关键事实与数据

- 当前讨论的主要训练路线是 **RLVR：Reinforcement Learning with Verifiable Rewards（可验证奖励强化学习）**。
- 支持者认为，训练是一次性成本，可以被模型未来的 **数十亿次会话**摊销。
- AI Agent 在编程领域已经能够解决更复杂的问题，并在更长时间跨度内持续工作。
- 视频用“新员工可能工作 **6个月以上**才开始产生净价值”说明真实能力需要长期在岗学习。
- 超长上下文被部分研究者视为持续学习的替代方案：把数月经验全部放进 context window，而不更新权重。
- 计算机操作任务的成功通常可以被验证，例如：

- Etsy 商品是否完成购买并送达；
- 活动场地是否成功预订；
- 税务是否完成提交。
- 编程强化学习可以复制 **1,000份**相同容器，让一千个 Agent 从同一起点并行尝试。
- 真实 Amazon 等网站无法承受大量机器人重复相同结账流程，平台还可能识别并封禁自动化机器人。
- 可通过克隆 **Slack、Gmail** 等应用构造计算机操作环境，但当前成本高、扩展性有限。
- 适合 RL 的训练环境通常需要具备：

- 可验证；
- 可重复；
- 可重置；
- 确定性较强；
- 可并行运行大量 rollout。
- 难以模拟的现实能力包括：

- 从零创建企业；
- 赢得法院案件；
- 在市场交易中持续盈利；
- 帮助候选人赢得选举。
- 视频将现实世界环境描述为 **reset-free（不可重置）**和 **non-stationary（非平稳）**。
- 思想实验之一：把 AI 放到 **1948年**，判断其能否比 Lyndon B. Johnson 更擅长赢得参议院席位。
- 思想实验之二：在 **2002年**给 AI **1亿美元**，判断其能否建立类似 SpaceX 的企业。
- 视频设问：若把强化学习环境投入从数十亿美元提升至 **1万亿美元**，是否会产生上下文窗口内的完整人类式通用智能。
- Dario 被引述称：**“RLVR generalization is not infinitely strong.”**
- 视频称，实验室约有 **30%—50%** 的算力没有直接发挥改进模型的生产性作用，但没有说明统计来源和口径。
- AI 在部署阶段可以获得实验室难以预先制造的信息，包括组织内部流程、用户旧方法和模型真实错误。
- 持续学习不能依赖无限扩大的 KV cache，经验最终需要以某种形式被压缩进权重。
- **Cursor Tab** 模型被用作在线学习案例。
- 文字稿称 Cursor Tab 每天处理超过 **4亿次请求**，通过预测用户最终接受哪些编辑来学习。
- 当前成功上线的在线学习模型，通常针对大量用户反复出现的同一种学习目标，而不是为每个用户学习完全不同的知识。
- 文字稿在讨论“每个工作、公司和问题都不同”时中断，视频后续内容未被完整提供。
- 文字稿出现“Robert Einstein”，可能是语音识别错误；无法仅凭现有内容确认原视频所指人物。

## 金句摘录

“What if you could just fit those six months into the context window?”

“如果你能把那六个月的工作经验全部装进上下文窗口呢？”

“It is not enough for a domain to be verifiable. It also has to be very grindable.”

“一个领域仅仅能够验证结果还不够，它还必须能够被反复、大规模地刷取训练。”

“Unless you can build a very replayable training target for a domain, the models will struggle to make much progress.”

“除非能为某个领域构建高度可回放的训练目标，否则模型很难取得巨大进展。”

“RLVR generalization is not infinitely strong.”

“RLVR 的泛化能力并不是无限强的。”

“It is only in deployment that the most valuable bits of information, which your model could learn from, are actually revealed.”

“模型最值得学习的那些信息，实际上只有在部署阶段才会真正显现。”

“Human continual learning is less about having all your observations at the tip of your tongue and more about chiseling the right intuitions and big-picture knowledge back into the weights.”

“人类的持续学习，并不是随时逐字复述所有观察，而是把正确的直觉和整体知识凿回自己的‘权重’之中。”

## 值得记住的点 / 行动建议

### 1. 判断一个任务是否适合强化学习，不能只看结果能否评分

设计 AI 训练任务时，应同时检查五个条件：成功标准是否清楚、环境能否重置、初始状态能否复制、结果能否回放，以及是否可以低成本并行运行。很多任务虽然最终结果明确，却因为反馈周期过长或环境不可复制，不适合传统 RLVR。比如“是否成功注册账号”容易训练，“是否把公司经营成功”则很难。产品团队应避免把“可验证”误认为“可规模化训练”。

### 2. 优先寻找能够被容器化和模拟的任务

对编程、数据处理、浏览器操作和企业软件 Agent，可先建设确定性较高的沙箱环境。将代码仓库、数据库、权限、测试集和外部接口固定下来，使每次训练都能从同一状态开始。对于 Slack、Gmail、CRM 或电商操作，可建立简化但行为一致的克隆系统，而不是直接在生产网站上进行海量试错。训练环境本身可能成为重要基础设施和竞争壁垒。

### 3. 不要把超长上下文等同于真正学习

上下文窗口可以提供临时记忆和即时适应，却不能自动形成长期、可迁移的能力。评估 Agent 时，应区分“因为提示词中提供了全部资料而表现良好”与“即使资料不再出现，模型仍掌握了规律”。可以在任务结束后更换上下文、改变表述和迁移领域，测试模型是否真正抽象出知识。企业也不应把不断堆积历史对话当作唯一的个性化策略。

### 4. 评估长时域 Agent 时，要直接测试长任务，而不是从短任务成绩推断

模型能连续完成十分钟的网页操作，并不证明它能经营一个月的项目；能修复单个代码缺陷，也不等于能维护数年的软件系统。长时域评估应加入目标漂移、人员变动、信息冲突、延迟反馈和不可逆决策。还要测试模型能否保存阶段性经验、重新规划并识别早期错误。没有这类测试，短时域 RL 得分很容易被误读为通用自主能力。

### 5. 把部署数据看作训练资产，但先解决隐私与权限问题

真实用户交互能够揭示实验室模拟环境无法覆盖的失败模式、组织知识和工作习惯。企业可记录任务类型、模型建议、用户修改、最终接受结果和错误原因，用于改进检索、提示词、路由器或专用模型。但不能未经授权将企业机密和个人数据直接用于参数训练。需要建立数据分级、匿名化、用户同意、保留期限和可删除机制，避免“持续学习”变成持续收集敏感信息。

### 6. 在线学习应先从高频、单一、可量化目标开始

Cursor Tab 的案例说明，现有在线学习更适合每天重复数亿次、反馈标准明确的任务，例如预测哪项代码修改会被接受。企业部署在线学习时，可以先选择“用户是否采纳建议”“是否完成纠错”“是否点击推荐”等稳定信号。不要一开始就要求模型同时学习不同用户的行业知识、个人偏好和长期目标。目标越多样，错误归因、模型漂移和相互干扰越难控制。

### 7. 为不同层次的“记忆”建立分工

并不是所有新信息都需要写入基础模型权重。短期任务状态可放在上下文中，用户事实可进入外部记忆或数据库，组织知识可通过 RAG 检索，反复出现的通用规律才值得通过后训练或权重更新固化。这样的分层可以降低训练成本，也减少模型因个别错误经验而永久改变的风险。下一代系统更可能是参数、上下文、检索和外部记忆共同组成，而非单纯依赖某一个无限大的模型。

### 8. 关注经验压缩质量，而不是只追求记忆容量

持续学习的价值不在于保存全部细节，而在于提取能跨任务复用的直觉和抽象。训练系统应尝试把大量工作轨迹总结为策略、原则、失败模式和因果假设，再通过新任务验证这些压缩结果。若模型只记住具体路径，环境稍有变化就会失效；若抽象过度，又可能丢失关键条件。如何在细节与泛化之间形成有效压缩，可能是下一阶段研究的核心指标。

### 9. 研究真实世界能力时，应设计“近现实代理指标”

创业成功或赢得选举无法被快速复制，但可拆成一些反馈周期更短的子能力，例如客户访谈质量、销售邮件回复率、单位经济模型、谈判结果和资源配置。法院诉讼可拆成证据检索、论点一致性、判例匹配和对手策略预测。虽然这些代理指标不能等同于最终成功，却能为模型提供更频繁的训练反馈。设计时必须防止模型只优化代理指标，而损害真正的长期目标。

### 10. 对“规模必然产生 AGI”的判断保持经验主义

扩大算力、数据和强化学习环境已产生显著进步，但不能据此直接证明所有现实能力都会自然出现。应持续观察三类证据：短任务能力能否迁移到长任务，数字环境能力能否迁移到现实环境，以及会话内学习能否稳定转化为长期能力。若这些迁移始终存在明显断层，就需要新的架构、学习规则或训练目标。下一代范式可能仍会使用大规模 RL，但它很可能还需要更强的持续学习、世界建模和经验压缩机制。

## 我的点评

这段视频最有价值的地方，是清楚地区分了 **“可验证”与“可规模化训练”**：现实任务即使有明确成败，也未必能提供可复制、可重置的强化学习环境。作者对持续学习的重视也很有道理，因为部署阶段确实包含比人工基准更丰富的真实错误和组织知识。需要保留的是，超长上下文、外部记忆、RAG 与权重更新未必是非此即彼，未来系统更可能采用多层记忆协同，而不是让所有经验都直接进入模型参数。

视频使用创业、政治和 SpaceX 等宏大案例增强了论证力度，但这些思想实验很难直接转化为可测试结论，对 RLVR 泛化上限仍需更多实证。所谓实验室有 30%—50% 算力“没有生产性作用”、Cursor 每日4亿请求等数字也应在找到原始来源后再正式引用。总体而言，这段内容没有给出下一代训练范式的完整答案，却准确指出了问题中心：AI 必须从“在可重复游戏里反复刷题”，走向“在不可重复的世界中用少量经验真正成长”。

---

## 📝 完整文字稿

所以,現在我們在學校的研究要做的他們認為如果我們訓練AI去獲得百分百的目標在千多種多交流環境中我們會有基本建築AI因為這種訓練會有一種問題解決的方式一種可以進行進行進行進行的進程在前一陣子的錯誤和悲劇中作出了一種進行進程這些人們會說我們會說的是,我們在現代的運動中會說到的東西,例如,資料不足的模式,或是,資料不足的學習,這些東西可以只是用來調整如果我們只能調整更多的運動同樣的,我們在自然化的研究中,我們只能把足夠的研究進行LLM的進行作用。

所以,在之前的解釋中,我提到的,這些模式是1萬1千萬的研究成員而,人們 who are in favorof the current training paradigm will saylook, that might be true,but this is only true during training.training is this one-time costthat is amortized across billions of sessionsthat a model will experience.what really matters is how smartand general and sample efficientthe model is during a session.And this has clearly been improvingas we have been doing more RL training.AI agents are able to solvemore and more ambitious problemsover longer and longer time spans.Anybody who has used these modelsfor coding knows that.Similarly, people would saylook, continue learningthis capability I keep harping aboutwhere the model's weights get updatedbased on what is learning from deploymentmay simply not be necessarybecause if in context learninggets so good across longer and longertime horizons, then you don't needto distill back everything the modelis learning on the job into the weights.People often say that their employeesare not net productive until six monthsor more of them working on the job.So clearly online learningis necessary for competence.But what if you could just fit thosesix months into the context window?

There's been tons of architectural innovationsthat dramatically increasedthe amount of informationor the amount of contextthat a transformer can storeand why not think with a couple moreyears of progress you might havewhat feels like infinitely largecontext windows.Okay, so before we discussthis research a bit further,I want to step back and I want to askcompletely tentential questionwhich I find actually veryinteresting and confusingabout the nature of current AI progress.Why has progress on computeruse been so much slowerthan other domains?

Computer use is soclearly verifiable.You could ask a question likedid the desired Etsy item I orderedget delivered?

Is the venue for an event I'mtrying to organizebooked?Have my taxes been submitted?So isn't it weird that computer use has beenlower progress than coding and mathand these other verifiable domains?

I'msure there's many reasons for thisand one of them of course is the factthatthe modelers are exposed to farless high quality multimodal dataduring free training.But one reason that I think isactually quite underrated by peopleand which I think reveals thecanyon walls against which thisriver of AI progress will onlyslowly chip away at is thatit is not enough for a domainto be verifiable.It also has tobe verygrindable in the sense thatyou have to be able to runlotsofparallel rollouts against adeterministic andreplayable simulatorand you're going to run thoserollouts from the same startingpoint.If you're trying to make amodel better at coding,you candefine somecontainer that hasthesoftwarerepo,it's a missingfeature that you have taskedtheaiswithcreating.And then you havea thousandparallel agents that go atthe problem,each of which has anidentical copy of the container.Buta thousand agentsgo try the samecheckoutflowonamazon to getbetter atusing websites becauseAndyChassi will find your botsand shut your ass down.You cansolve this by making clones ofslack and gmail and all the othercommon applications and websites.Butat least currently this is a verylaborintensive and unscalableway to build environments.Of courseonce AIs get good enough at codingthemselves to build these cloneswith extremely high fidelity,thenyou're also killing two birds with one stonewith this kind of procedure becausegetting AIs to rebuild wholeapplications from scratch is alsoa great RL objective for coding.Sowhile computer use itself may soon besolved,it's current lethargy istelling us the following.That unlessyou can build a very replayabletraining target for a domain,themodels will struggle to make much progress.Andthe reason this is true,of course,themodels are incredibly sample inefficientduring training.This is the pointof the last video essay.So forcomputer use,you might be able to make upfor the sample efficiency deficit bybuilding these farmable deterministicsimulators.But for so many otherdifferent kinds of skills that we needAIs to have,we simply can't dothis.How do we train an AI to getreally good at building a businessfrom scratch?

How about winningcourt cases?Or having a profitableday of trading in the markets?Orhelping a candidate win an election?

Therollout here requires interacting withthe data center.The outer loopverification here may take monthsor even years of real worldactions to elicit.And you can'treobserve it by perturbing themodels actions slightly inthousands of parallel rolloutsto isolate exactly what the modeldid that actually worked.Now dealingwith such reset free non-stationaryenvironments is a known openproblem in RL.I'm not pointing outanything new.But I really do wantto emphasize that because of theculture of data in most domains inthe world,you need sampleefficiency in order to get proficient.IfAIs are to develop all theskills that humans have,and evenskills that humans don't have,thenthey need to be able to learn frominformation revealed in unstructuredunverifiable and ambiguousways from scarce amountsof real world interaction.Becausein many domains,the relevanttraining information simply doesn'texist in any other way.Whatis the RL environment to make an AIthat is as good at politics as LyndonJohnson?

Or as good at building aspace launch business as Elon Musk?Thelabs are betting that RLVR willgeneralize.That is,that if you trainon enough containerizedreproducible environments,you willdevelop a very general agentthat can make and execute plansand learn rapidly from newinformation and even pick up newskills all within a singlesession.If you drop thisin 1948,it couldgive you better advice than LBJabout winning the senate seat.And if yougave it $100 million in 2002 and let itcook,it would build SpaceX for you.Nowwhether RLVR can generalize thiswell is an empirical question.If thelabs went for spending billions ofdollars on RL environments to atrillion dollars,would you get thekind of thing that is a fullyhuman-like general intelligence withinthe context window?

Dario gave atelling quote during our podcastRLVR generalization is not infinitelystrong,but he was explainingwhy model performance tends to degradeat long context.He said,there's twothings.There's the context length you trainat,and there's the context length thatyou serve at.If you train at asmall context length and then try toserve at a long context length likemaybe you get these declarations.Nowmaybe I'm reading too much into this,but it seemslike he's saying that short horizonRL training doesn't necessarily generalizeto long horizon RL performance.And ifyou train from short horizon to longhorizon,then how are agents supposedto generalize from getting trained ata bunch of white collar tasks to sayhaving the ability to be dropped inthe real world and build a businessfrom scratch as well as Sam Walton.Andeven if after enough in contextexperience,the AI's can become likeHenry Ford or Robert Einstein,allthat would be ephemeral and wastedif you couldn't get those learningsback into the weights.Around 30-50%of a lab's compute goes tonot playing any productive role inhelping improve the model.Thisseems like a huge waste.And it's even worsethan it sounds because it is onlyin deployment that the most valuable bitsof information,which your model couldlearn from,are actually revealed.Thingslikewhat's actually happening in theorganizations where I'm being used.Andwhat are they using before?

And whatkind of mistakes do I tend to make inthe real world?We've got some geniusgrad student who's never beenallowed to take a real internship.Andit's so bizarre that we have AI'sthat are broadly deployed through theeconomy already and areparticipating in so many differentkindsof tasks and are privy to somuch domain and organizationspecific tasks at knowledge.Andthey're not able to make use ofit.But this kind of continuallearning requires going back tothe weights.AI's can't just keepbuilding up a bigger and biggerKV cache as they learn from moreand more users.That's just notscalable.And that's also not how humansdo it.There's no clean separation inour brain between parameters andactivations.And it's not like somepart of your skull keeps expanding asyoulearn more things through yourlifetime.When we learn stuffthere's clearly some kind ofcompression.And this aids ourgeneralization and groping.Thereare,in fact,some humans who havethisautisticsofant type abilityto recall random tables ofnumbers or nonsense syllablesand later,basically the kind offidelity information that modelshave in context.And such sheervolume cripples these humans'abilityto understand abstractionsand metaphors.Human continuallearning is less about having allyourobservations at the tip of yourtongue and more about chiselingthe right intuitions and big pictureknowledge back into the weights.Butthe moment you move into the weights,youhave to give upon in-contextlearning sample efficiency.Becauseall the successfully shipped onlinelearning models have had to learn theexact same thing across millions ofusers.For example,the cursor tabmodel online learns by predictingthe same exact objective forover 400 million requests a day.Theobjective here being which editsactually got accepted by the user.Atleast so far,we haven't seen modelsonline learn different kinds ofthings for different users.Becausewhile a single session may generatemore than enough data for a humanit's not enough to train a morecapable AI.Currentonline learning can work for a verylimited number of use cases.Butthe whole point of continuallearning is that the world is verycomplicated.An east job and companyand problem is different.Andyou need your intelligence to beable to learn the specificinformation related to aparticular deployment whichsimply can't be stuffed into someshare training run.These are all thethings we're talking about when we talk about on the job learning.Thingslike how does everything in your organizationwork and fit together.Andhow to cooperate with other infrastructureand other people around you to makeprogress on some larger project.Andwhat the common failure modes are.Andmany other things like this.As thepodcast has grown,I've had to deal withmore and more operational overhead.Takepaying bills.In the past,contractorswould just email me their invoices.Everyfewweeks,I'd dig through my inbox,I'dcreate a folder with all the bills,and I'dmanually pay each one.At this pointI'd send an email address that goes straighttomercury,which is my banking platform.Wheneveranybody sends an invoice to that addressmercury automatically downloads it,scansit,and extracts all the relevantinformation.Things like the contractorname,address,payment amount,invoicenumber,and due date.And then uses allthis to create a draft payment.Mercurythen stores a list of these drafts forme to review.I just go through this listand double check that I've been built correctly.Idon't have to track anything or enter any informationmyself.Mercury does all thematerial things for your business extremely welland it puts them all in one place.If youwant to learn more,go tomercury.com.Mercuryis a fintech company,not an FDICinsured bank.Banking services provided throughchoice financial group and columnNAmembers FDIC.In this way,sampleefficiency and continual learning are actuallydeeply connected problems.Relatively little datais available to the model on the job.Nowto learn from this data requires sampleefficiency.Models can do that in contextbut using the fast weights that are built onthe fly by attention,which allows for thesampleefficiency but skills very poorly interms of memory.So we needarchitectural innovations that allow forsome kind of intermediate representation.Italked before about how we already havemany different working ideas for thiskind of thing,from sparse attention toKVcash compaction.And every week somebodyreleases a new paper suggesting somekind of other architectural optimization.Itdoesn't seem to me that architecture isfundamentally what is bottleneckingcontinual learning.So perhaps the bottleneckis the loss function.How do we updatethe weights,aka how do we improve themodel itself,based on information thatwas learned from one particularsession.Even here naively it seemslike there are many ideas that oughtawork.Lot of people are talkingabout this technique called onPolicyself-disolation recently.If youwant to learn more about it,I recordeda little impromptu blackboard lecturea couple of weeks ago and it's in thelink in the description.But tosummarize the explanation,the ideais that we encourage the base modelto make the same predictions whentrying to solve some real-worldproblem as the model with all thecontext accumulated after a longsession would have made.The wholepoint of this procedure is todistill what the model learned in asession back into the weights themselves.Thisis better than RLVR for tworeasons.One,OPSD doesn'thave some outer loop verifiablereward.We just need a model thatcan learn the right things withinthe context window.As long as wehave that,we can train the basemodel to match our veteran teachermodel,which has built up all thisexperience during this session.Andtwo,OPSD provides a much densersupervision signal than naive RL.Insteadof projecting a single rewardthrough the whole trajectory,youcan train on the per-tokenprobability discrepancy between theteam.For continual learning,OPSDis also superior to supervised finetuning.The most naive version ofSFT for this application that youcan imagine,is just to train the basemodelto predict all the tokens that areobserved during this session.But this makes nosense if you think about it as alearning target.The way you getbetter at your job is not byrecalling the transcript of everysingle thing that happened everyday with perfect fidelity.Rather,it'sby consolidating the handful ofproperties that you canapply to your job.RL tradingdoesn't suffer from this failuremode.RL is great atconcentrating the update to onlywhat is relevant to getting theoutcome right.That's whyactually very few parameters arechanged during an RL trainingstep.And this is a veryimportant property for continuallearning.Because as you'relearning on the job,you don'twant to overwrite and forget allthing.But this may be a goodthing rather than a badthing.You onlychange the model as much as isabsolutely necessary to achievethe outcome and no more.OPSDpreserves this property ofsupervised learning,where instead ofslingshotting towards a teacherdistribution,as supervised learningwould have you do,you onlyextract the knowledge that isnecessary for you to achievethe same results of the teacher onactual real-world tasks.OPSDYou take the scarce real-worldexperience and you squeeze all thesignal into a tiny well-targetedupdate.But there's also anothermuch more speculative idea.Let'scall it dreaming.If the AIcan build a good simulation ofreality against which torehearse new skills or tryalternative strategies andreinforce what actually works,thenAIs could experience orders ofmagnitude more simulated samples inthe same wall clock time.Let's go看B-Mine release alpha zero.Agrouper researchers trained a model calledefficient zero.And the whole point ofthis model is to be very efficient withdata.So if this model and a humanboth got two hours to play againsta simulator of an Atari game thatthey hadn't seen before,thismodel would actually probably beat thenovice human.Does this mean that themodel was more sample efficient than thehumans?

Well that was the goal ofthe training,but it depends on howyou measure sample efficiency.Becauseefficient zero is playing dozens ofsimulated games in its head.In asimilar way,future LLMs might beable to consume far less real worlddata while practicing endlessly againstenvironments that they build forthemselves.The big difference,ofcourse,is that it will be much harderto build a simulation of the wholeworld than it is to emulate the gameofgoal.That's why I said this is amuch more speculative idea.If itworks,it would become a fourth axisofscaling alongside pre-training,RLyou can call it test timetraining,or dreaming.The model spendscompute writing upRL environmentsand then training against them,andis rehearsing all the skills thatwill actually be used in productionfor a specific user.So insteadof hitting forward slash compact incodex or cursor or clod,whichkindles a small amount of computeto write up a summary,and whichgives you the simulacrum ofcontinue learning,you hit forward slashdream.And this incinerates hugecompute to build and train againstthe video game version of what the modelis witnessing in the real world.Sowhat might continual learning look likeby 2027 or 2028?

Andhow do we get there?Here's onescenario.All of thisRLVR trainingis producing an agent that canget its bearings when it's thrown at anunfamiliar problem,and it can trydifferent strategies,and it caniterate when it hits a roadblock.Thisis the crucial thing thatRLVR hasgiven you.An AI that is atleastcan start getting some real worldexperience if you can learn from it.And once you have that,you send it outinto the world to do real work,evenon projects that are off the tradingdistribution.Now let's say at this pointthe effective context lengths have expandedsuch that AIs can jam and co-workwith you for a full week of wallclock time.At the end of a weekyou give it a thumbs up or a thumbs down.Give it a work review.And if you giveit a thumbs up,the base model distillseverything that the AI learned duringit may use OPSD,it may usedreaming,it may use some other techniquethat we aren't even aware of,or it willuse a combination of all of the above.Andonce it does so,the AIstarts getting better domains that areadjacent to what it was explicitlytrained to beforehand,withRLVRtraining.And in the next round afterthat,it can get better at things thatare adjacent to what it had previouslyonline learned.In this way,the gamutof AI skills and knowledge andcapabilities can expand far beyondaimable domains that the model wasoriginally trained against before itwas deployed.Just as pre-trainingcreated a base intelligence that wassmarter enough to become a competentagent with enoughRLVR on top,soRLVR has created an agent thatis competent enough to beactually broadly deployed in theworld and from this broad deploymentto learn on the job,once thetraining recipe for continual learningactually arrives.By this point,themain way that AIs get better isnot from the trading they havereceived before they are released tothe public.Rather,it's from allthis experience that they'll beaccumulating from being broadlydeployed in the economy andengaging in so many differentkinds of tasks.Everytime that youinteract with an AI,it'll besmarter.Not only because it'sbeen learning from yourprevious sessions,but also becauseit's been learning from allit's interactions with all thearation of a blogpost that Ialsoreleased on my website atdvorkash.com.Go there ifyou want to read all the footnotesor if you want to signup so youcan find out when I release thenext blogpost.Otherwise,I'll seeyou on the next episode.
