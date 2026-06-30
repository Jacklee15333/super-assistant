# 下一个训练范式会是什么样子？

- 来源链接：https://www.youtube.com/watch?v=20p5-kQXF_Q
- 作者：Dwarkesh Patel
- 提取时间：2026-06-29 13:31
- 原标题：What does the next training paradigm look like?
- 标签：AI、机器学习、强化学习

## 🤖 AI 分析

## 一句话概括

这段视频讨论了当前 AI 实验室押注的下一代训练范式：通过在大量可验证、可重复、可并行刷题式的 RL 环境中训练模型，试图把 AI 推向通用智能；但作者强调，这一路线可能会被真实世界任务的稀缺反馈、不可重置环境、低样本效率和缺乏持续学习能力卡住。

## 背景与主题

视频的核心话题是：AI 实验室正在把未来 AGI 的希望押在一种强化学习训练范式上，尤其是围绕大量可验证任务的 RL 训练，也就是文中反复提到的 **RLVR**。作者先承认这个方向的吸引力：如果 AI 能在数百万个可验证任务、数千个不同 RL 环境里持续试错、规划和解决问题，它确实可能形成某种“通用问题解决智能体”。但作者随后提出关键质疑：真实世界中很多重要能力，并不能像数学、代码、容器化任务那样被无限并行、重置、复现和快速验证。作者的立场不是简单否定 RLVR，而是强调：**“可验证”还不够，训练目标还必须“可刷、可重放、可并行、可压缩进权重”**，否则 AI 很难获得人类在商业、政治、法律、交易、组织管理等领域的复杂能力。

## 核心观点

### 1. 当前 AI 实验室的大赌注：用海量可验证 RL 任务训练出 AGI

作者开头直接点出“大研究赌注”：所有实验室都在押注，如果让 AI 在数百万个可验证任务、数千个多样化 RL 环境中训练，那么基本上就等于建出了 AGI。这里的逻辑是，RL 训练不是只教模型回答问题，而是训练它成为一种能持续推进任务的 **problem-solving agent（问题解决智能体）**。这种智能体需要能在错误、失败、歧义和长时间任务中继续前进，甚至能连续几周处理开放式任务。乐观派认为，目前训练范式中的缺陷，比如数据效率低、缺乏持续学习能力，都可以通过继续扩大训练规模来“碾过去”。作者把这种乐观态度类比为 NLP 领域的历史经验：很多曾被认为是基础研究难题的问题，后来在 LLM 时代被海量算力和数据规模压平了。

### 2. “训练时低效”不一定致命，因为训练成本可以被海量使用摊薄

作者回顾自己上一篇文章提到的观点：这些模型在训练阶段的样本效率大约只有人类的 **百万分之一**。但支持当前范式的人会反驳说，这种低样本效率只发生在训练阶段，而训练是一次性成本。只要模型训练出来以后被用于数十亿次 session，这个训练成本就可以被摊销掉。真正重要的不是训练时花了多少样本，而是模型在一次具体使用中是否足够聪明、通用、样本高效。作者承认，在 RL 训练增强后，AI agents 确实已经能解决越来越复杂、时间跨度越来越长的问题，尤其是写代码的人会明显感受到这一点。

### 3. 持续学习可能被“超长上下文”部分替代，但这只是乐观假设

作者提到自己一直强调的一个能力：**continual learning（持续学习）**，也就是模型在部署过程中，根据真实使用经验更新自身权重。乐观派可能会说，这种能力并非绝对必要，因为如果 **in-context learning（上下文内学习）** 足够强、上下文窗口足够长，模型就不必把每次工作中学到的东西蒸馏回权重里。作者用一个职场例子说明：很多员工刚入职前六个月甚至更久都不是净产出者，因为他们要学习组织、业务和上下文；但如果 AI 的上下文窗口大到能装下“六个月的工作经验”，那么它或许能在一次 session 内完成类似学习。近年来确实有很多架构创新，显著提高了 transformer 能存储的信息量和上下文长度。问题在于，这种“无限上下文窗口”的设想能否真正替代权重层面的学习，仍然非常可疑。

### 4. 电脑使用能力进步慢，暴露了“可验证 ≠ 可训练”的问题

作者提出一个看似旁支、但其实很关键的问题：为什么 AI 在 **computer use（电脑使用 / 操作软件和网站）** 上的进步，比代码、数学等领域慢得多？电脑使用看起来也很容易验证，比如“我订的东西是否送达了”“活动场地是否预订成功”“税是否提交了”。如果一个领域只要可验证就能通过 RL 快速提升，那么电脑使用应该进展很快。作者认为，一个被低估的原因是：模型在预训练中接触到的高质量多模态数据较少，但这还不是全部。更深层原因是，电脑使用虽然可验证，却很难被大量并行、重置、复现地刷训练样本。

### 5. 一个领域不仅要“可验证”，还必须“可刷题化、可农场化”

作者提出一个核心概念：训练环境不仅要 verifiable（可验证），还要 **grindable / farmable（可刷、可大量重复采样）**。在代码任务中，这很容易实现：你可以定义一个容器，里面放着软件仓库和一个缺失功能，然后复制出一千个完全相同的容器，让一千个 AI agents 从同一个起点并行尝试解决问题。每个 agent 的尝试都可以被测试、回放、比较和奖励。但电脑使用就没这么简单，你不能让一千个 agent 同时去 Amazon 上跑同一个下单流程来学习网站操作，因为 Amazon CEO **Andy Jassy** 迟早会发现这些机器人并封掉它们。这个例子说明，真实互联网环境不是为 RL 训练准备的可重置模拟器，它有账号、风控、状态变化、真实金钱和真实用户影响。

### 6. 克隆 Slack、Gmail 等应用可以缓解问题，但目前昂贵且不可规模化

作者承认，有一种解决办法是做高保真的软件和网站克隆，比如克隆 **Slack**、**Gmail** 以及其他常见应用，让 AI 在模拟环境里练习电脑使用。这样做可以把现实网站变成可控、可重放、可并行的 RL 环境。但作者指出，至少在当前阶段，这种方法非常劳动密集，而且扩展性很差。只有当 AI 自己足够擅长写代码，能够高保真地从零重建整个应用时，电脑使用能力的训练才可能明显加速。作者还补充说，这其实是一石二鸟：让 AI 重建完整应用，本身也是一个非常好的代码 RL 目标。

### 7. 真实世界许多关键能力无法被容器化训练

作者从电脑使用进一步推广到更大的问题：很多我们真正希望 AI 拥有的能力，无法被做成确定性、可重置、可并行的模拟器。例如，如何训练 AI 从零开始建立一家公司？如何训练它赢得法庭案件？如何训练它在金融市场中长期盈利？如何训练它帮助候选人赢得选举？这些任务的反馈需要真实世界互动，外层验证可能要几小时、几个月，甚至更久才能显现。你也不能把现实世界复制成一千份，只微调模型的某个动作，然后观察哪个动作导致了成功。

### 8. 稀疏、非结构化、不可验证反馈要求模型必须具备高样本效率

作者强调，处理 **reset-free, non-stationary environments（不可重置、非平稳环境）** 是 RL 中已知的开放问题。真实世界大多数领域的数据都是零散的、特异的、反馈稀疏的，和代码测试或数学题完全不同。AI 如果要学会人类拥有的复杂技能，甚至发展出人类没有的新技能，就必须能从少量真实互动中学习。它必须能理解非结构化、不可验证、模糊和稀缺的信息，而不是只能依赖高频、明确、可自动评分的奖励信号。作者的关键判断是：在很多领域，真正有用的训练信息只存在于真实互动本身，无法提前在数据中心里合成出来。

### 9. RLVR 能否从“容器化任务”泛化到政治、商业和长期规划，是核心经验问题

作者提出一个尖锐问题：有没有一种 RL 环境，能训练出像 **Lyndon Johnson** 那样擅长政治，或者像 **Elon Musk** 那样擅长建立太空发射公司的人？实验室押注的是：RLVR 会泛化。也就是说，如果在足够多的容器化、可复现环境中训练 AI，它最终会形成一种通用能力：制定计划、执行计划、从新信息中快速学习、在单个 session 内掌握新技能。作者用两个假设场景说明这种愿景：如果把一个经过无尽 RLVR 训练的 AI 放到 **1948 年的 Texas politics（德州政治）** 中，它也许能给出比 **LBJ** 更好的参议员竞选建议；如果在 **2002 年** 给它 **1 亿美元**，让它去做太空发射业务，它也许能像 Musk 一样“let it cook（让它慢慢做出结果）”。但作者强调，这究竟能不能发生，是一个经验问题，而不是理论上说得通就一定成立。

### 10. 上下文学习的经验如果不能写回权重，就会变成昂贵而短暂的浪费

作者后半段的核心担忧是：即使 AI 在一次长上下文 session 中学到了很多东西，如果这些学习不能写回模型权重，那么它们就是短暂的、用完即消失的。作者提到，实验室大约 **30%-50% 的算力** 用在 inference（推理 / 部署使用）上，但这些算力目前并没有有效地帮助改进模型本身。更糟的是，部署过程中其实暴露了极其珍贵的信息：真实组织里正在发生什么、用户到底拿模型做什么、模型在真实世界中经常犯什么错误。这些知识往往是组织特定的、领域特定的 tacit knowledge（默会知识），比课堂式 RL 环境更接近真实智能所需的经验。作者用一个比喻说，现在的 AI 像一个“从来没被允许真正实习的天才研究生”，只能不断拿到更多课堂案例，而不能把真实工作经验沉淀为长期能力。

## 关键事实与数据

- 当前 AI 实验室押注的训练方向：在 **millions of verifiable tasks（数百万可验证任务）** 和 **thousands of diverse RL environments（数千个多样化 RL 环境）** 中训练 AI。
- 作者上一篇文章中的说法：当前模型训练阶段的样本效率大约只有人类的 **one-one millionth / one-millionth（百万分之一）**。
- 支持者的反驳逻辑：训练是一次性成本，可以被模型未来经历的 **billions of sessions（数十亿次会话）** 摊销。
- 电脑使用任务的例子：确认购买的东西是否送达、活动场地是否预订、税务是否提交。
- 电脑使用进展慢的原因之一：模型在预训练阶段接触的高质量多模态数据相对较少。
- 更核心的原因：电脑使用虽然可验证，但不够 **grindable / farmable（可大量并行刷训练）**。
- 代码 RL 的典型环境：一个包含软件 repo 的容器，里面有一个缺失功能，让大量 agent 从同一初始状态并行尝试。
- 作者举的并行规模例子：可以让 **a thousand parallel agents（一千个并行智能体）** 在完全相同的容器副本中尝试解决代码问题。
- 电脑使用的反例：不能让一千个 agent 同时去 **Amazon** 跑同一个 checkout flow，否则 **Andy Jassy** 会发现并封掉这些机器人。
- 可替代方案：克隆 **Slack**、**Gmail** 和其他常用应用或网站，构建可重放模拟环境。
- 作者认为该方案当前的问题：劳动密集、不可规模化，除非 AI 已经能高保真地自动重建应用。
- 无法轻易模拟的真实世界能力：从零建立公司、赢得法庭案件、在市场中盈利交易、帮助候选人赢得选举。
- 真实世界任务的反馈周期：可能需要 **months（数月）** 或 **hours of real world actions（数小时真实行动）** 才能验证。
- RL 中已知难题：**reset-free, non-stationary environments（不可重置、非平稳环境）**。
- 政治能力例子：像 **Lyndon Johnson / LBJ** 一样理解政治，尤其是 **1948 年 Texas politics** 中赢得参议员席位。
- 商业能力例子：像 **Elon Musk** 一样建立 space launch business（太空发射业务）。
- 另一个商业能力参照：像 **Sam Walton** 一样从现实商业中建立零售帝国式能力。
- 作者提到的假设资金规模：**a hundred million dollars in 2002（2002 年的一亿美元）**。
- 作者提到的 RL 环境投资假设：如果实验室从花 **billions of dollars（数十亿美元）** 建 RL 环境，提升到 **a trillion dollars（一万亿美元）**，是否能得到真正人类级通用智能？
- Dario 的关键区分：有训练时的上下文长度，也有部署服务时的上下文长度；短上下文训练后直接长上下文服务，可能出现性能退化。
- 作者推断：短时域 RL 训练不一定能泛化到长时域 RL 表现。
- 推理算力占比：约 **30%-50% of a lab’s compute（实验室 30%-50% 的算力）** 用在 inference。
- 部署阶段可学习的信息：用户真实使用模型做什么、组织内部发生什么、模型在真实世界中倾向犯什么错误。
- 作者认为只靠越来越大的 cache / context 不可扩展，真正的持续学习需要把经验压缩回 **weights（权重）**。
- 但一旦回到权重更新，就会遇到梯度更新的样本效率问题：**gradient updates are super-sample inefficient（梯度更新极其样本低效）**。

## 金句摘录

“They think that if we train AIs to accomplish millions of verifiable tasks across thousands of diverse RL environments, then we will have basically built AGI.”

中文翻译：他们认为，如果我们训练 AI 在数千个多样化 RL 环境中完成数百万个可验证任务，那么基本上就已经建出了 AGI。

“It is not enough for a domain to be verifiable. It also has to be very grindable.”

中文翻译：一个领域仅仅可验证是不够的，它还必须非常适合反复刷训练。

“You can’t just have a thousand agents go try the same checkout flow on Amazon to get better at using websites, because Andy Jassy will find your bots and shut your ass down.”

中文翻译：你不能让一千个 agent 去 Amazon 上反复跑同一个结账流程来提升网站使用能力，因为 Andy Jassy 会发现你的机器人并把它们封掉。

“The rollout here requires interacting with the real world, and you can’t recreate it from just within the data center.”

中文翻译：这些任务的 rollout 需要与真实世界互动，而你不能仅仅在数据中心里重建它。

“What if you could just fit those six months into the context window?”

中文翻译：如果你能把那六个月的学习过程直接塞进上下文窗口里呢？

“We’ve got some genius grad student who’s never been allowed to take a real internship, and we keep giving it more and more classroom case studies.”

中文翻译：我们手里有一个天才研究生，却从不允许它真正去实习，只是不断给它更多课堂案例。

## 值得记住的点 / 行动建议

### 1. 判断一个 AI 训练领域时，不要只问“能不能验证”，还要问“能不能大量重放”

视频最重要的方法论是：可验证只是第一步，真正适合 RL 规模化训练的任务必须能被大量并行 rollout、能从同一个起点重复运行、能在确定性或近似确定性的模拟器中比较不同策略。代码和数学之所以进展快，是因为它们天然具备这种特征：答案可以测试，环境可以复制，失败可以回放，奖励信号密集。电脑使用、商业、政治、法律和金融则困难得多，因为它们牵涉真实账户、真实组织、真实对手、真实时间和不可重置的环境。以后看某个 AI 能力是否会快速突破，可以先问：这个领域是否能被容器化？是否能构造足够多高质量模拟环境？是否能低成本地产生奖励信号？

### 2. 不要高估“超长上下文”对持续学习的替代能力

长上下文确实可以让模型在一次任务中记住更多信息，甚至可能让它在一个 session 内表现得像“已经入职学习了六个月”。但上下文中的学习是临时的，只要 session 结束，很多具体经验就会消失。真正的人类学习不只是记住材料，而是把大量经历压缩成直觉、判断力和可迁移的知识结构。作者提醒我们，不能把“上下文能装更多信息”误认为“模型已经完成了长期能力更新”。对企业和个人使用 AI 来说，这意味着：短期内，知识库、RAG、项目上下文和长期记忆系统仍然很重要，但它们不等于模型真正学会了你的业务。

### 3. 关注 inference 数据能否反哺训练，这是下一阶段 AI 能力跃迁的关键

作者特别强调，部署使用中产生的数据非常宝贵，因为它揭示了模型在真实组织、真实工作流和真实用户需求中的表现。当前大量算力用于 inference，但这些使用过程并没有充分转化为模型权重的改进。未来如果某家公司能安全、隐私合规、低风险地把真实使用反馈压缩回模型，它可能获得巨大优势。这里的难点不仅是技术，还有隐私、权限、数据污染、个性化与通用化之间的权衡。普通用户可以留意：哪些 AI 产品能真正记住长期偏好、吸收反馈、改进工作流，而不是每次都像新员工一样重新开始。

### 4. 真实世界智能的核心瓶颈，可能不是推理能力，而是低样本学习能力

很多重要工作无法提供数百万次试错机会，比如创业、诉讼、选举、并购、投资和组织管理。人类之所以能在这些领域学习，是因为我们能从少量模糊反馈中抽象出经验，而不是必须靠成千上万次可重置实验。AI 如果只能在高密度奖励环境中学习，它会在代码和数学上很强，却在真实世界长期策略上受限。判断 AI 是否接近人类级通用智能，不能只看它是否能刷题、写代码、解数学，还要看它能否从少量真实互动中快速形成可迁移判断。这个标准比 benchmark 分数更接近现实智能。

### 5. 对“RLVR 会自然泛化到所有领域”的说法保持审慎

作者并没有否认 RLVR 的潜力，而是提醒：从短时域、容器化、可复现任务中学到的能力，未必自动泛化到长时域、不可重置、战略性真实世界任务。Dario 关于训练上下文长度和服务上下文长度的说法，被作者用来说明一个可能的问题：如果模型短上下文训练后长上下文部署会退化，那么短期任务训练也未必能自然迁移到长期任务表现。比如，会修 bug 的 AI 不一定会建立公司；会赢模拟游戏的 AI 不一定会赢真实选举。对研究者和产品使用者来说，应该区分“在模拟环境中表现好”和“在真实复杂系统中可靠有效”。

### 6. 电脑使用能力的突破，很可能依赖“高保真应用模拟器”的规模化生产

视频对 computer use 的分析很有启发：这个领域不是因为不可验证而慢，而是因为很难低成本构建可训练环境。未来如果 AI 能自动生成 Slack、Gmail、Amazon、企业后台、CRM、ERP 等高保真交互环境，它就能在这些模拟器里大量练习。与此同时，构建这些环境本身又会提升 AI 的软件工程能力，因为重建完整应用是极好的代码训练目标。也就是说，AI 写代码能力和 AI 使用软件能力可能会形成互相促进的循环。观察未来进展时，可以关注是否出现大规模、高保真、可自动生成的交互式软件训练环境。

## 我的点评

这段视频的价值在于，它没有停留在“RL 能不能通向 AGI”的抽象争论，而是把问题具体化为训练环境是否可验证、可重放、可并行、可压缩。作者对电脑使用进展慢的解释很有洞察力：很多人只看到“这个任务能不能打分”，却忽略了“这个任务能不能被成千上万次廉价试错”。不过，作者的论证也有需要保留的地方：真实世界任务虽然难以完全模拟，但 AI 未来可能通过合成环境、世界模型、用户授权数据、企业内闭环反馈等方式获得部分替代路径。另一方面，作者对持续学习的担忧非常现实，因为如果模型无法把部署经验沉淀为长期能力，它就始终像一个聪明但健忘的顾问。普通人理解这段内容时，可以把它当作判断 AI 未来能力边界的一套框架：越是可测试、可复制、可大量试错的领域，AI 越可能快速进步；越是依赖稀缺真实反馈和长期组织经验的领域，进步就越慢、也越不确定。

---

## 📝 完整文字稿

So here's the big research bet that all the labs are making.They think that if we train AIs to accomplish millions of verifiable tasks across thousands of diverse RL environments,then we will have basically built AGI.Because this kind of training will have created a kind of problem-solving agent.The kind of thing that can make progress on opening the tasks for weeks on end in the face of errors and mistakes and ambiguity.And the people who are optimistic about this vision will say that all these things that we talk about asthe fundamental deficits in the current training paradigm,for example the data inefficiency of these models or the fact that they lack continual learning.These things can just be steamrolled if we just scale training more.And the same way that all the fundamental research problems in natural language processing collapsed when we just threw enough compute into LLMs.So in the previous essay I talked about how these models are one-one millionth a sample efficient as humans.And the people who are in favor of the current training paradigm will say,Look,that might be true,but this is only true during training.And training is this one-time cost that is amortized across billions of sessions that a model will experience.And what really matters is how smart and general and sample efficient the model is during a session.And this has clearly been improving as we've been doing more RL training.AI agents are able to solve more and more ambitious problems over longer and longer time spans.Anybody who has used these models for coding knows that.Similarly,people would say,look,continue learning.This capability I keep harping about,where the model's weights get updated based on what it's learning from deployment may simply not be necessary.Because if in context learning gets so good across longer and longer time horizons,then you don't need to distill back everything the model is learning on the job into the weights.People often say that their employees are not net productive until six months or more of them working on the job.So clearly online learning is necessary for competence.But what if you could just fit those six months into the context window?

There's been tons of architectural innovations that dramatically increase the amount of information or the amount of context that a transformer can store.And why not think with a couple more years of progress,you might have what feels like infinitely large context windows.Okay,so before we discuss this research a bit further,I want to step back and I want to ask a completely tangential question,which I find actually very interesting and confusing about the nature of current AI progress.Why has progress on computer use been so much slower than other domains?

Computer use is so clearly verifiable.You could ask a question like,did the desired STI that I ordered get delivered?

Is the venue for an event I'm trying to organize booked?Have my taxes been submitted?So isn't it weird that computer use has been making so much slower progressthan coding and math and these other verifiable domains?

I'm sure there's many reasons for this,and one of them,of course,is the fact thatthe modelers are exposed to far less high quality multimodal data during pre-training.But one reason that I think is actually quite underrated by peopleand which I think reveals the canyon walls against which this river of AI progress will only slowly chip away atis that it is not enough for a domain to be verifiable.It also has to be very grindable.In the sense that you have to be able to runlots of parallel rolloutsagainst a deterministic and replayable simulatorand you're going to run those rollouts from the same starting point.If you're trying to make a model better at codingyou can define some container that has the software repoit's a missing feature that you've tasked the AIs with creatingand then you have a thousand parallel agents that go at the problemeach of which has an identical copy of the container.But this doesn't work with computer use,at least not trivially.You can't just have a thousand agentsgo try the same checkout flow on Amazonto get better at using websitesbecause Andy Jassy will find your bots and shut your ass down.You can solve this by making clones of Slack and Gmailand all the other common applications and websites.But at least currently this is a very labor intensiveand unscalable way to build environments.Of course once AIs get good enough at coding themselvesto build these clones with extremely high fidelitythen I'm sure the computer use will make quicker progress than it is right nowand you're also killing two birds with one stonewith this kind of procedurebecause getting AIs to rebuild whole applications from scratchis also a great RL objective for codingSo while computer use itself may soon be solvedit's current lethargy is telling us the followingthat unless you can build a very replayable training targetfor a domainthe models will struggle to make much progressand the reason this is true of coursethe models are incredibly sample inefficient during trainingthis is the point I was making in my last video essayso for computer use we might be able to make up for theby building these farmable deterministic simulatorsbut for so many other different kinds of skillsthat we need AIs to havewe simply can't do thishow do we train an AI to get really good atbuilding a business from scratchhow about winning court casesor having a profitable day of trading in the marketsor helping a candidate win an electionthe rollout here requires interacting with the real worldand you can't recreate it from just within the data centerthe outer loop verification here may take monthsor hours of real world actions to elicitand you can't re-observe itby perturbing the models actions slightlyin thousands of parallel rolloutsto isolate exactly what the model didthat actually workednow dealing with such reset freenon-stationary environmentsis a known open problem in RLI'm not pointing out anything newbut I really do want to emphasizethat because of the idiosyncraticand sparse nature of datain most domains in the worldyou need sample efficiencyif AIs are to developall the skills that humans haveand even skills that humans don't havethat they need to be able to learnfrom information revealed in unstructuredunverifiable and ambiguous waysfrom scarce amounts of real world interactionbecause in many domainsthe relevant training informationsimply doesn't exist in any other waywhat is the RL environment to make an AIthat is as good at politics as Lyndon Johnsonor as good at building a space launch businessas Elon Muskthe lives are betting that RLVRwill generalizethat is that if you trainon enough containerizedreproducible environmentsyou will develop a very generalagent that can makeand execute plansand learn rapidlyfrom new informationand even pick up new skillsall within a single sessionif you drop thisendlessly RLVRed AIinto Texas politicsin 1948it could give you betteradvice than LBJabout winning the senate seatand if you give ita hundred million dollarsin 2002and let it cooknow whether RLVRcan generalize this wellis an empirical questionif the labs went fromspending billions of dollarson RL environmentsto a trillion dollarswould you get the kind of thingthat is a fully human-likegeneral intelligencewithin the context windowDario gave a telling quoteduring our podcast togetherwhich I think hintsthat RLVR generalizationis not infinitely strongbut he was explainingwhy model performancesends to degrade at long contexthe saidthere's two thingsthere's the context lengthyou train atand there's a contextlength that you serve atif you trainat a small contextlengththen try to serveat a long contextlength like maybeyou get thesedegradationsnow maybeI'm reading too muchinto thisbut it seems likehe's sayingthat short-horizonrl trainingdoesn't necessarilygeneralizeto long-horizonrl performanceand if you can'tgeneralizefrom short-horizonto long-horizonthen how are agentssupposed to generalizefrom getting trainedin the real worldand build a businessfrom scratchas well as Sam Waltonand even if afterenough in contextexperiencethe AIs can becomelike Henry Fordor Robert Einsteinall that would be ephemeraland wastedif you couldn't getthose learningsback into the weightsaround 30-50%of a lab's computegoes to inferenceand that computeis currentlynot playingany productive rolein helpingimprove the modelthis seems like a hugewasteand it's even worsethan it soundsbecause it iswhich your modelcould learn fromare actually revealedthings likewhat's actuallyhappening in theorganizations whereim being usedand what are theyusing me forand what kinds ofmistakes do Itend to makein the real worldwe've got somegenius grad studentwho's never beenallowed to takea real internshipand we keep givingit moreand more classroomcase studiesin the formof rl trainingon environmentsit's so bizarrethat we haveaisto so muchdomainand organizationspecifictasit knowledgeand they'renot able tomake use of itbut this kindof continuallearningrequiresgoing backto the weightsais can'tjust keepbuildingup a biggerand biggercabie cashas theylearnfrom moreand moreusersthat's justnot scalableand that's alsonot howhumans do itwhen welearnstuffthere'sclearlysome kindof compressionand this aidsourgeneralizationandrockingthere arein factsome humanswhohave thisautisticsof ant typeabilitytorecallrandomtables ofnumbersornonsensecelliblesyearsandmoreaboutchiseling theright intuitionsand big pictureknowledgeback into theweightsbut themoment youmoveinto theweightsyou haveto giveuponin-contextlearningsampleefficiencybecausegradientupdates aresuper-sampleinefficientall of thesuccessfullyshippedifyourebeingwhicheditsactuallygotaccepted bythe user.atleastso farwe haven'tseen modelsonlinelearneddifferentkindsof thingsfor differentusersbecausewhile asingle sessionmay generatemore thanenoughdatafor ahuman tolearn fromdifferentand you needyour intelligenceto be able tolearn thespecific informationrelated toa particular deploymentwhich simplycan't be stuffedinto someshared training run.These are all thethings we're talkingabout when we talkabout on-the-joblearning.things likehow does everythingin our organizationwork andfit togetherand how tocooperate withall the infrastructureand the other peoplearound youto make progresson some largerandmoreoperationaloverhead.takepaying bills.in the pastcontractorswould justemail metheir invoices.Every few weeksI'd dig throughmy inbox.I'd createa folderwith all the billsand I'd manuallypay each one.at thispoint thoughI'd justgive everybodyan e-mail addressthat goes straightto Mercurywhich ismy banking platform.whenever anybodycreateddraft paymentMercurystoresa listof these draftsfor me to reviewI just go throughthis listand double-checkthat I'veinbuilt correctly.I don'thow to trackanythingor enterany informationmyself.Mercurydoes all thefundamental thingsfor your businessextremely welland it putsthem all in one place.if you want tolearn morego toamplificancyand continuelearningareactually deeply connectedproblems.relatively littledata is availableto the modelon the job.now to learnfrom this datarequiresampleefficiency.and modelscan do thatin contextbut usingthe fastweightsthat are builton the flybyattentionwhich allowsfor thesample efficiencybut skillsvery poorlyin terms ofmemory.作为这种东西从批评研究到KV Cash Compaction每周有人推出新的文章推荐一些另一种建议这不仅仅是建议是最主要的是继续学习继续学习所以可能继续学习是失败的我们如何更新继续学习我们如何改变组织研究根据设计从一个特别的设计甚至在这里纽约好像有很多想法要做很多人在说一些对形象还有做货货给你做得这种模式给我们很不错我们在这个一些传辑上像是嗯她刚才她来的我 durch她就好像到我们提供川普就是然后Session back into the way to themselves.This is better than RLVR for two reasons.One, OPSD doesn't require us to have some outer loopverifiable reward.We just need a model that can learn the right things withinthe context window.And as long as we have that, we can train the base modelto match our veteran teacher model, which has built up allthis experience during the session.And two, OPSD provides a much denser supervision signalthan naive RL, instead of projecting a single rewardthrough the whole trajectory, you can train on the pertoken probability discrepancy between the teacher and student.For continued learning, OPSD is also superior tosupervised fine tuning.The most naive version of SFT for this applicationthat you can imagine is just to train the base modelto predict all the tokens that are observedduring the session.But this makes no sense if you think about itas a learning target.The way you get better at your job is not byrecalling the transcript of every single thingthat happened every day with perfect fidelity.Rather, it's by consolidating the handfulof insights and pieces of knowledge that areactually relevant to you getting better at your job.RL trading doesn't suffer from this failure mode.RL is great at concentrating the update to onlywhat is relevant to getting the outcome right.That's why actually very few parameters arechanged during an RL training step.And this is a very important property forcontinual learning because as you're learningon the job, you don't want to overwriteand forget all the other things that the basemodel knows.I wrote a post a few months earlier arguingthat RL learns much less information persample than supervised learning.But this may be a good thing rather than a badthing.You only change the model as much asis absolutely necessary to achieve theoutcome and no more.OPSD preserves this property of supervisedlearning where instead of slingshottingtowards the teacher distribution assupervised learning would have you do,you only extract the knowledge that isnecessary for you to achieve the sameresults of the teacher on actual realworld tasks.OPSD is one way to attack the sampleefficiency problem.You take the scarce real world experienceand you squeeze all the signal into atiny well targeted update.But there's also another much morespeculative idea.Let's call it dreaming.If the AI can build a good simulationof reality against which to rehearsenew skills or try alternativestrategies and reinforce whatactually works,then AI's couldexperience orders of magnitude moresimulated samples in the same wallclock time.Let's go back in history a bit.A couple of years after DeepMindreleased AlphaZero,a group ofresearchers trained a model calledEfficientZero.And the whole point of this model isto be very efficient with data.So if this model and a humanboth got two hours to playagainst a simulator of an Atarigame that they hadn't seen before,this model would actuallyprobably beat the novice human.Does this mean that the model wasmore sample efficient than thehumans?

Well,that was the goal of thetraining,but it depends on howyou measure sample efficiencybecause for each step in thereal game,EfficientZero isplaying dozens of simulatedgames in its head.In asimilar way,future LLMsmight be able to consume farless real world data whilepracticing endlessly againstenvironments that they buildfor themselves.The bigdifference,of course,is thatit will be much harder tobuild a simulation of thewhole world than it is toemulate the game of go.That'swhy I said this is a muchmore speculative idea.Ifit works,it would become afourth axis of scalingalongside pretraining,RLand inference time compute.Youcould call it test timetraining or dreaming.Themodel spends compute writingupRLenvironments and thentraining against them,andis rehearsing all theskills that will actually beused in production for aspecific user.So insteadof hitting forward slashcompact in codex or cursoror clod,which kindles asmall amount of compute towrite up a summary,andwhich gives you the simulacrumof continue learning,youhit forward slash dream.Andthis incinerates hugeamounts of compute tobuild and train againstthe video game versionof what themodel iswitnessing in the realworld.So what mycontinual learning looklike by 2027 or 2028,andhow do we get there?

Hereis one scenario.Allof thisRLVR training isproducing an agent thatcan get its bearings whenit's thrown at anunfamiliar problem,andit can try differentstrategies,and it caniterate when it hits aroadblock.This isthe crucial thing thatRLVR has given you.AnAI that is atleastcompted enough tostartgetting somerealworld experienceif you could learnfrom it.Andonce you have that,yousend it out into theworld to do realwork,even on projectsthat are off thetrading distribution.Nowlet's say at thispoint,the effectivecontext lengths haveexpanded,such thatAIs can jam andco-work with youfor a full weekof wall clock time.Atthe end of a week,yougive it a thumbs upor a thumbs down.Giveit a work review.Andif you give it athumbs up,thebase model distillseverything that the AIlearned during thesession.And it mayuse OPSD,it mayuse dreaming,andit mayuse some othertechnique that wearen't even aware of,orit'lluse a combinationto all of the above.Andonce it does so,theAI starts getting betterdomains that are adjacentto what it was explicitlytrained to beforehandwith RLVR training.Andin the next roundafter that,it can getbetter at things thatare adjacent to what ithad previously onlinelearned.In this way,thegamot of AI skills andknowledge and capabilitiescan expand far beyondthe verifiable domainsthat the model wasoriginally trainedagainstbefore itwas deployed.Just aspre-training createda base intelligencethat was smartenough to becomea competent agentwith enough RLVRon top,soRLVR has createdan agent thatis competent enoughto be actuallybroadly deployed inthe world,andfrom this broaddeployment tolearn on the job,oncethe training recipefor continual learningactually arrives.Bythis point,themainway that AIsget better,is notfrom the trainingthey have receivedbefore they arereleased to thepublic.Rather,it'sfrom all thisexperience thatthey'll be accumulatingfrom beingbroadly deployedin the economyand engagingin so manydifferent kindsof tasks.Everytime that youinteract in AI,it'llbe smarter.Notonly because it's beenlearning from yourprevious sessions,butalso because it'sbeenlearning fromall this interactionswith all the otherusers in the world.Andthat's very scaryand excitinganddifferent from the waythat AI improvesright now.Thiswas an aerationof a blog postthat I also releasedon my website atdwarcache.com.Gothereifyou wannareadall the footnotesor ifyou wannasign up so youcan find thatwhen I releasethe nextblog post.OtherwiseI'll see youon the nextepisode.
