# The data black hole at the center of AI

- 来源链接：https://www.youtube.com/watch?v=4pG3SJQPAwk
- 作者：Dwarkesh Patel
- 提取时间：2026-06-24 20:25
- 标签：AI、数据科学、样本效率

## 🤖 AI 分析

**专有名词校正说明：**文字稿中的“McCore”应为 **Mercor**，这是一家为前沿 AI 训练、评测和后训练提供专业人才与数据的平台；“EPOC”应为研究机构 **Epoch AI**。Mercor 当前公开岗位确实包括法律专家、管理与战略咨询顾问等专业角色；Epoch AI 于 2026 年 5 月发布的分析称，2026 年以来最强开放权重模型平均落后闭源前沿模型约四个月。[Mercor
+2
Mercor
+2](https://www.mercor.com/?utm_source=chatgpt.com)

## 一句话概括

视频认为，当前 AI 能力快速提升的核心并非模型已经像人类一样高效学习，而是行业投入了规模惊人的数据、算力和专家示范；模型看似璀璨的能力背后，隐藏着一个由海量训练数据构成的“黑洞”。

## 背景与主题

视频围绕一个经常被忽视的问题展开：AI 在掌握新知识和新技能时，究竟需要多少训练样本，也就是它的**样本效率（sample efficiency）**如何。作者认为，近几年 AI 的能力虽然显著增强，但训练样本效率未必取得了同等程度的进步，行业更多是通过扩大数据分布、提高数据质量以及增加计算量来换取能力。作者由此分析强化学习、专家数据产业、开源模型追赶前沿模型、人类与机器学习效率差异等现象，并逐一回应“人类经过进化预训练”“人类还有多模态数据”“模型再扩大就能解决”等反驳。视频最后插入了一段 **Mercury Command** 的商业推广，与前面的 AI 样本效率讨论没有直接的论证关系。

## 核心观点

### 1. 衡量智能的重要标准之一，是掌握新领域所需的数据量

作者首先给出一种关于智能的定义：智能可以体现为**样本效率**，即一个系统需要接触多少数据，才能在某一领域中流畅、可靠地完成任务。按照这个标准，能力强不只是“最终能不能完成任务”，还包括“为了获得这种能力，需要训练多少次”。一个人看过几个示例就能迁移到新问题，与一个模型必须看过数百万个相似示例才学会，虽然最终输出可能相近，但学习机制和智能效率存在巨大差别。因此，作者提醒观众，不应仅通过模型最终展示出的能力判断它是否已经接近人类智能，还要观察这种能力背后的训练成本。

### 2. 近年 AI 的进步主要来自更多、更好的数据，而非样本效率的根本突破

作者认为，过去几年 AI 进步的主要原因，是训练数据的覆盖面被大幅拓宽，数据质量得到改善，同时训练和筛选数据所投入的计算量显著增加。换言之，模型变强并不一定意味着它学得更快，也可能只是因为行业向它提供了更多教材、更多标准答案和更多反复练习的机会。模型原本无法完成的任务，在获得大量针对性示范、评判规则和强化学习轨迹后，才逐渐表现得像是“理解了”该任务。这种进步当然真实存在，但作者认为它更接近资源规模的扩张，而非人类式快速学习机制的出现。

### 3. 强化学习本质上可以看作一种高成本的合成数据生产过程

在作者的框架中，**强化学习（Reinforcement Learning，RL）**不仅是一种优化方法，也是一套寻找优质训练数据的机制。系统先让模型针对同一任务生成大量候选答案或行动轨迹，再利用验证器、评分标准，或者由另一个大语言模型充当裁判，对这些结果进行评价。经过筛选后，正确或高质量的轨迹就成为新的训练材料，模型随后被训练去复现这些成功轨迹，就像预训练阶段学习预测互联网文本的下一个词一样。也就是说，强化学习并没有消除数据需求，而是用大量计算主动“挖掘”出可供模型模仿的好数据。

### 4. 强化学习必须建立在模型已经有一定成功概率的基础上

作者强调，强化学习不是从绝对空白中凭空创造能力；模型必须对正确答案至少保留某种非零的先验概率，才可能在大量尝试中偶然生成正确轨迹。如果模型从未见过相关知识、完全不知道任务结构，那么无论生成多少次，都可能无法产生可供验证器筛选的优质答案。因此，训练者必须事先为每一个目标领域准备大量人类专家示范，让模型先具备基本的动作、表达和推理空间。强化学习更像是在已有能力分布中扩大正确路径的概率，而不是无需示范便能自动发明任意新技能。

### 5. 高质量 AI 数据极其专业化，而且需要大量专家共同生产

作者建议查看 **Mercor** 和 **Surge AI** 等平台上的岗位说明，以理解训练数据究竟有多具体。例如，有人负责把老旧文档转化为排版规范的 Microsoft Word 文件，有法律专家负责撰写逼真的并购尽职调查材料或证券申报文件，还有管理咨询顾问负责制作标准化市场研究报告。这些任务不是普通网络文本能够直接替代的，因为模型需要学习真实职业环境中的格式、判断标准、工作流程和质量边界。Mercor 的公开信息也显示，其专家岗位覆盖公司法、交易业务、管理咨询、投行和医疗等高度专业化领域。[Mercor
+2
Mercor
+2](https://www.mercor.com/?utm_source=chatgpt.com)

### 6. 每项模型能力背后，可能都站着数百名专家和庞大的数据产业

作者进一步指出，训练某一项技能通常不只是请一名专家写几个案例，而是需要数百名专家持续提供样例答案、评分规则、错误解释和推理过程。这些材料还需要被整理成强化学习环境，使模型可以反复生成答案、接受评分并更新参数。因此，专业数据标注、专家反馈和强化学习环境已经发展成一个年收入数十亿美元，并可能继续增长至数百亿美元规模的产业。作者借此反驳“模型只是自行阅读互联网便自然获得所有能力”的直觉：很多看似自然的职业能力，实际上是大量人类知识劳动被精细拆解、标注和重新注入模型的结果。

### 7. 模型不是像人一样学会了许多技能，而更像由无数示例缝合而成的“科学怪人”

作者用 **Frankenstein’s monster（弗兰肯斯坦式的科学怪人）**作比喻：当前模型不像一个真正理解世界、然后自然迁移到不同任务的人，而更像由“十亿张精心构造的示例图纸”缝合起来的复合系统。它能够处理 Word 排版、法律文件、市场研究、编程和推理，是因为每个能力区域都被大量针对性数据反复塑造。外部观察者只看到模型在许多领域表现流畅，容易误以为其内部存在一个与人类相似的通用学习者。作者认为，更准确的理解是：模型展现出的能力星座，是由中心处巨大但不可见的数据质量和数据规模维系的。

### 8. 开放模型能迅速追赶闭源前沿模型，说明数据可能比秘密架构更重要

视频引用 **Epoch AI** 的分析称，最强开放权重模型平均只落后闭源前沿模型约四个月。作者据此推断，如果前沿优势主要来自难以复制的架构发明、训练超参数或内部优化技巧，那么落后者通常不应该在短短几个月内追上。相比之下，前沿模型的输出可以通过公开 API 被大量采集，再经过蒸馏转化为新模型的训练数据，这使能力扩散速度明显加快。Epoch AI 的原始分析确实称，自 2026 年初以来，最强开放权重模型在其综合能力指数上平均落后闭源前沿约四个月，但这一数据本身只能证明能力差距较小，作者关于“数据是主要原因”的结论仍属于进一步推断。[Epoch AI
+1](https://epoch.ai/data-insights/open-closed-eci-gap?utm_source=chatgpt.com)

### 9. 人类与模型之间存在数千倍到近百万倍的学习数据差距

作者估算，一个人如果平均每小时接触约 2000 个词，从出生到成年大约接触 **2亿个语言 token**；而前沿模型可能接受数十万亿至数百万亿 token 的训练，两者接近几十万倍乃至约百万倍的差距。机器人和自动驾驶也存在类似现象：人类可以在数小时内适应新的机械控制任务，青少年大约练习 20 小时就能初步学会驾驶，但机器人模型和自动驾驶系统仍需要数百万小时示范及更庞大的传感数据。作者认为，这些比较表明当前模型虽然最终能力很强，但学习过程远比人类低效。需要注意的是，这些数字属于数量级估算，不同 token 计算方式、年龄范围和感官数据折算方法都会改变最终倍数。

### 10. 单纯扩大模型规模，可能无法弥补人与 AI 的样本效率鸿沟

一种常见观点认为，人脑约有 **100万亿个突触**，而某些前沿模型约有 **5万亿个参数**，所以只要再把模型扩大一到两个数量级，就可能达到人类的学习效率。作者借助 **Chinchilla scaling law（Chinchilla 缩放定律）**反驳称，在相关缩放公式中，参数规模和数据规模分别影响损失，即使无限增加参数，也无法无限替代数据需求。按照作者对该公式常数的解读，把参数量推向极端，所需数据最多也只能下降约一个数量级，而人类与模型的样本效率差距可能达到数千至数百万倍。因此，他认为人类可能并非处于现有大模型缩放曲线的更远端，而是处于一条性质不同的学习效率曲线上；不过，Chinchilla 定律是经验模型，其外推范围和具体系数仍存在研究争议。[ZeroEntropy
+2
arXiv
+2](https://zeroentropy.dev/concepts/scaling-laws/?utm_source=chatgpt.com)

## 关键事实与数据

- **样本效率（sample efficiency）**：完成或熟练掌握某一领域任务所需要的数据量。
- 作者认为，近年 AI 进步主要来自：

- 更大规模的数据；
- 更高质量的数据；
- 更广的数据分布；
- 用于生产和筛选数据的更多计算资源。
- 强化学习流程可被概括为：

**1. 模型针对任务生成大量候选轨迹；**
**2. 验证器、评分规则或 LLM 裁判对轨迹评分；**
**3. 筛选正确、高质量轨迹；**
**4. 继续训练模型，使其更可能生成这些轨迹。**
- 视频称，使用 **GRPO** 等方法时，一个任务可能需要生成**数百至数千条 rollout（完整作答或行动轨迹）**。
- 专家数据生产涉及的任务包括：

- 将旧文档转换为精致、规范的 Word 文件；
- 撰写真实感较强的并购尽职调查材料；
- 撰写证券申报文件；
- 编写模板化市场研究报告。
- 文字稿中的“McCore”应为 **Mercor**；Mercor 公开岗位包括交易与公司法律专家、管理与战略咨询顾问等。[Mercor
+1](https://www.mercor.com/?utm_source=chatgpt.com)
- **Surge AI** 公开介绍的专家工作包括审查模型论证、撰写示范性法律分析以及构建结构化论证数据集。[surgehq.ai
+1](https://surgehq.ai/workforce?utm_source=chatgpt.com)
- 作者称，每一项细分技能都可能需要：

- 数百名人类专家；
- 示例答案；
- 评分标准或 rubric；
- 推理解释；
- 专门的强化学习环境。
- 作者将当前模型比作由海量专业示例缝合而成的 **Frankenstein’s monster（弗兰肯斯坦式科学怪人）**。
- Epoch AI 于 **2026年5月29日**发布的分析称，2026 年以来最强开放权重模型平均落后闭源前沿模型约：

- **4个月**；
- 或其能力指数上的 **8分**。[Epoch AI
+1](https://epoch.ai/data-insights/open-closed-eci-gap?utm_source=chatgpt.com)
- 人类语言输入的粗略估计：

- 每小时接触约 **2000个词**；
- 从出生到成年约接触 **2亿个语言 token**。
- 前沿模型训练数据的估计：

- 数十万亿至数百万亿 token；
- 作者称其与人类语言输入相差接近百万倍。
- 机器人学习对比：

- 人类可能在数小时内学会操作一种随机的人形机器人或机械臂；
- 当前 AI 即使获得数百万小时示范，仍难以稳定执行复杂、开放式任务。
- 视频提到的机器人名称应为 **Unitree G1（宇树 G1）**，文字稿中的“unitary G1”属于语音识别误差。
- 驾驶学习对比：

- 青少年大约经过 **20小时**练习即可初步学习驾驶；
- 即使把出生后约 16 年的常识和物理经验计算在内，作者仍认为其数据量比 Waymo、Tesla 自动驾驶模型使用的数据少 **3—4个数量级**。
- 人类基因组约包含 **30.5亿个碱基对**，蛋白质编码部分约占 **1%—2%**；不过“3 GB”是把碱基字符按特定数字编码方式换算后的通俗说法，并非基因组天然具有固定文件大小。[PMC
+2
国家生物技术信息中心
+2](https://pmc.ncbi.nlm.nih.gov/articles/9186530/?utm_source=chatgpt.com)
- 视频使用的规模比较：

- 人脑约 **100万亿个突触**；
- 某些前沿模型约 **5万亿个参数**。
- 作者根据 Chinchilla 缩放公式声称：

- 即使极端增加参数量；
- 在保持相同损失的情况下；
- 所需数据最多大约只下降 **10倍**。
- 片尾商业推广涉及 **Mercury Command**：

- 它是嵌入 Mercury 账户的 AI 财务工具；
- 可查询余额、交易、发票和预定付款；
- 可起草资金转账，最终由用户批准；
- Mercury 官方将其描述为能够通过对话完成付款、发票、财务洞察等工作的 AI。[Mercury
+1](https://mercury.com/command?utm_source=chatgpt.com)
- 广告案例中提到一笔计划在 **7月支付的12,000美元承包商款项**。
- Mercury 是金融科技公司，不是银行；视频结尾的免责声明被语音识别为不完整句子。

## 金句摘录

“One definition of intelligence is sample efficiency.”

“关于智能的一种定义，就是样本效率。”

“The main way that AIs have been getting better is from adding more and better data.”

“AI 变得更强的主要方式，是加入更多、更好的数据。”

“The correct way to think about these models is not like a human who has learned all these different skills.”

“理解这些模型的正确方式，不是把它们看成一个真正学会了所有不同技能的人。”

“It’s more like a Frankenstein’s monster which has been built out of a billion graphs of carefully constructed examples, all sewn together.”

“它更像一个弗兰肯斯坦式的科学怪人，由十亿张精心构造的示例图纸缝合而成。”

“We see these AIs as the galaxy glittering with capabilities.”

“我们看到的 AI，就像一个闪耀着各种能力的星系。”

“At their center, invisible to the naked eye, holding all the constellations together, is an unimaginably massive black hole of data.”

“而在它的中心，有一个肉眼不可见、维系着所有能力星座的、规模难以想象的数据黑洞。”

## 值得记住的点 / 行动建议

### 1. 评价 AI 时，不要只看结果，要追问它用了多少数据

看到模型完成法律分析、编程、文档处理或机器人控制时，应同时询问它接受过多少相关示范、生成过多少次候选答案，以及是否针对测试任务进行过专门强化训练。最终能力相同，并不代表学习能力相同。模型依靠一百万个训练案例解决问题，与人类通过几个示例掌握规则，在智能机制上并不是同一件事。判断“AI 是否接近人类”时，样本数量、训练计算量和迁移能力都应纳入比较。

### 2. 区分“更聪明”与“覆盖了更多训练分布”

当模型突然在某个专业领域表现更好时，不应立即断言其推理机制发生了根本突破。更合理的检查顺序是：是否新增了领域数据，是否进行了专家标注，是否建立了更强的验证器，以及推理阶段是否投入了更多计算。很多表面上的智能提升，可能源于训练分布扩大或测试时搜索增强。只有在少量新样本下仍能迅速掌握真正陌生的任务，才更能说明样本效率有所提高。

### 3. 分析强化学习时，要看到隐藏的数据生产链

强化学习并不是摆脱人工数据，而是把数据生产过程从“人直接写答案”部分转化为“模型生成、系统筛选、人制定规则”。验证器、rubric 和奖励模型本身都需要专业人员设计，模型也必须先拥有一定领域知识，才有机会生成正确轨迹。因此，在讨论强化学习带来的能力时，应同时计算候选轨迹数量、专家评分成本、验证器开发成本和总计算投入。否则容易把高成本搜索误认为模型凭少量信息自行领悟。

### 4. 企业采用 AI 时，应把数据资产视为核心竞争力

模型供应商提供的是通用能力，企业真正难以复制的部分往往是内部流程、专业案例、错误记录、质量标准和专家反馈。若企业希望 AI 完成并购审查、财务分析、市场研究或复杂文档工作，就需要将优秀员工的判断方式转化为可训练、可评测的数据。与其只追逐最新模型，不如同步建设高质量案例库、评测集和任务反馈机制。视频的核心商业启示是：模型可以快速普及，但真正可靠的专业数据不会自动出现。

### 5. 对“开源模型只落后几个月”的结论保持双重理解

一方面，开放模型快速追赶说明能力正在迅速扩散，前沿实验室的长期垄断未必稳固。另一方面，这种追赶可能高度依赖闭源模型 API 所产生的合成数据和蒸馏数据，因此不能简单解释为开放团队独立发现了全部训练方法。分析开源与闭源差距时，应区分公开基准、私有基准、模型权重开放程度以及训练数据来源。Epoch AI 的“四个月”是特定指数和特定时期的平均值，不意味着所有任务都只有四个月差距。[Epoch AI
+1](https://epoch.ai/data-insights/open-closed-eci-gap?utm_source=chatgpt.com)

### 6. 不要把参数数量直接等同于人脑突触数量

神经网络参数与生物突触只是功能上的粗略类比，二者的结构、动态变化、能耗、可塑性和学习机制都不相同。用“100万亿突触对5万亿参数”得出只需再扩大 20 倍模型的结论，缺少足够理论依据。即使扩大参数能改善损失，也不意味着会自动产生人类式因果学习、抽象迁移和快速适应。规模可能仍然重要，但规模并不是解释全部差距的充分条件。

### 7. 把视频中的数量级比较视为思想实验，而不是精确测量

“2亿 token”“接近百万倍”“20小时学会驾驶”“少3—4个数量级”等数据，主要用于展示人类与模型学习效率可能存在巨大差距。实际比较受到 token 定义、人类睡眠时间、视觉和触觉信息折算、先验知识以及训练数据重复率等因素影响。阅读时应保留其方向性结论，即当前模型的数据需求远大于人类，而不要把每个倍数都当作严格实验结果。尤其是不同模态之间不存在公认的统一 token 换算方式。

### 8. 判断下一阶段 AI 是否出现质变，可以重点观察少样本学习

比单纯关注基准分数更有意义的指标，是模型面对一个训练中几乎未出现的新任务时，需要多少示例才能掌握。可以测试模型能否在一两个演示后理解新的软件界面、新游戏规则、新机器人动作或企业流程，并稳定迁移到变化后的情境。如果模型仍需要数百名专家、数百万条轨迹和大量任务定制，说明其通用学习效率尚未发生根本改变。真正值得关注的突破，可能不是参数再次翻倍，而是模型学习新技能的数据需求下降几个数量级。

## 我的点评

视频抓住了一个容易被基准成绩掩盖的重要问题：**最终能力与学习效率不是同一个概念**，当前 AI 的成功确实高度依赖数据、算力和人类专家知识。用“数据黑洞”解释模型能力背后的隐形投入，能够纠正“模型读完互联网后便自行获得通用智能”的简单叙事。不过，视频把近期进步较强地归因于数据，对架构改进、推理计算、工具使用和训练算法的作用讨论不足，部分倍数比较也属于粗略估算。人类拥有身体、社会互动、内在动机和高度结构化的先验机制，语言 token 与人类全部学习经验并不能直接等价比较。更稳妥的结论是：当前模型已通过超大规模数据取得强大能力，但其是否具备接近人类的快速、持续和可迁移学习能力，仍然没有得到证明。

---

## 📝 完整文字稿

So one definition of intelligence is sample efficiency.That is to say how much data do you need in a given domainto operate fluently and competently.And it's actually not clear that we've made that much progressin training sample efficiency over the last few years.It seems like more so we've just dramatically widenedand improved the data distribution.The main way that AI's have been getting betteris from adding more and better dataand scaling the compute requiredto develop that data in the first place.Obviously RL is the main way that this has happened.You can think of RL as basically a kind of synthetic data generationwhere you dump a ton of compute against a verifieror a rubric if you have an LLM as a judgeand you do this in order to find outwhat the good data is in the first place.And then you train your model to predict thesecorrect rollouts much in the same waythat you might train that model to predictthe next word in internet text.For this process to work,the model must haveat least some prior probabilityto anticipate the correct solution in the first placewhich is why you need mind stretching amountsof human-expert trajectoriesin every single field and skillthat you want the model to eventually be competent in.It's hard to overstate how task-specificand bespoke this human-expert data is.If you want some intuition,I recommend checking outthe job descriptions on McCore or Surge's websites.There are listings for word specialistswho will convert legacy documentsinto polished word filesand legal experts who will writerealistic M&A deligencesor securities filingsand management consultantswho will write up template market research.And it is not only that the datahave to be so domain-specificbut there has to be so much of it.Each skill correspondsto at least hundreds of human-expertswho are generatingexample completions,writing rubrics,and explainingtheir chain of thought.There's a reason that the data industrythat is producing theseexpert labelsand the RL environmentsin which thesemeticulously catalog skills can congealis earning billions a year in revenuesoon to be decambillions.Now imagine if it tooka couple decades'worth of courseswith hundreds of concurrent professorsand millions of practice tasksfor you to learn how to polish a word file.Even the task count difference hereunderstates the gapbecause the models have to grindtheir far more numerous taskseach far harderwhereas a human student might practicea textual problem once or twice.With GRPO these models are generatinghundreds to thousands of rolloutsper taskand they need toto solve the credit assignment problem.The correct way to think about these modelsis not like a human who has learnedall these different skillsthat you see these models displaying.It's more like a Frankenstein's monsterwhich has been built out of a billion graphsof carefully constructed examplesall sewn together.EPOCrecently reported that open models lagstate-of-the-art frontier modelsby four months.I think the reason it is relatively easyfor open source and previous laggardsto catch up to within months of the frontieris that data is the real driver of progress.And data can be easily distilledfrom public APIswhereas hyperparametersand training tricksand architectural optimizationscannot.And if the latterwe're driving most of the progressthen catching up would be far harderthan we are observing it to be.It is easy to forgethow much data these models are trained onand how much moreit is than what wehuman see in our lifetimes.We see these AIs as the galaxyglittering with capabilities.But at their center,invisible to the naked eye,holding all the constellationstogether is an unimaginablymassive black hole of data.Just a couple of points of comparisonto help drive homehow big this difference is.Here's one.If a person sees and hears on averagelet's say generouslytwo thousand words an hourthen between the time they're boredand the time they're an adult,they'll see about 200 million tokens.Now,by contrast,these frontier modelsare trained on somewhere betweentens to hundreds of trillions of tokens.That is close to a millionfold difference.Here's another point of comparison.If you wanted to,you could learn tototally operate any random humanoidor robot arm within hours.And if you could get AIs to learnjust as fast,robotics would bea decade trillion dollar industryand you'd have an endless armyof unitary G1sdoing all kinds of useful work in the world.But the reason we can't do thisis that our AIs learn much less efficientlythan we doand even with the millions of hoursof demonstrations that we collectedthis is not enough to allow themto perform complex open-ended tasks.And a final point of comparisona teenager can learn to drive a carwith about 20 hours of practiceand even if we include their 16 yearsof growing up and understandinghow the world worksand building physical intuition.There's still three to four ordersof magnitude less data thanwaymo and Tesla are usingto train their self-driving car models.Now,I want to deal with a coupleof common responsesand objectionsthat people haveto these kinds of comparisons.One thing people will sayand I think our product saidthiswhen it came on my podcastis that for humans,many billions of yearsof evolution had to go intobasically pre-training us.And so we're being unfairwhen we're comparing how littledata we see within our lifetimesto what these cold-startedLLMs were just starting offwith a totally random initializationhave to learn from.I think this is not the right wayto think about it.Our genome is only three gigabytes bigand only one to two percentof itis protein coding.And that is simply not enough spaceto store the parametersofthis network that supposedlyevolution has pre-trained.I think the closer analogyis more that evolution foundthe right hyperparametersand the right loss functionsand that within our lifetimewe are stillfrom scratchbuilding upthe connectomein our brain.That is to say,the analogous thingto the weights and parametersof the neural net itself.And even if you granted this comparison,you saidyes,the hundreds of trillions of tokensthat these models seeto get pre-trainedis similar to justcatching up to evolution,that still doesn't explainwhy any new marginal capabilitythat you want to give these modelstakes so much data.So once you haven't educated,again,you don't need a hundreddifferent professors to teach youhow to learn a new programming language.But these AIs,even once they'repre-trained,still requireenormous amounts of datato learn the next marginal skilland the next marginal skill after that.Another objection to this kind of comparisonis that we're not includingmultimodal datathat we're seeing in our lifetimes.So we include all thissensor informationthat we see from birthto adulthood.That's probably tens to hundredsof billions of tokens of data.And my response to this objectionis simply thatblind and deaf peoplewho have been cut offfrom all this sensor informationstill have general intelligence.And that suggests to methat all of these billionsof sensory tokensare not really the thingthat is making humans smart.And in fact,deaf peoplewho don't have the abilityto hear any tokenswho just have to consume themvia sign language and readingare probably ingesting far lessthan the 200 million language tokensthat we ballparked earlierwhich suggests thateven the millionfold differencethat we calculated earliermight be an understatement.Ok,the third common objectionpeople makeis that we just haven't scaled enough.We have these scaling laws.They tell us that bigger modelsare more sample efficient.The human brain we knowis about 100 trillion synapses.And we have frontier modelsthat are currentlyaround 5 trillion parameters.And so maybe we could justachieve human-level sample efficiencyif we made these modelsone to two ordersof magnitude bigger.The reason this objectionis off-markis actually quite interesting.So if you look at the waythe scaling laws equations workthey tell you thatthe parameter and data termsare added to the laws independently.So suppose you have a modeland you've trained itcompute optimallyand you sayI want to be sample efficient.I want to use as little dataas possibleand I'll throw inas many parametersas is necessaryto make that happen.So take the constantsfrom the Chinchillascaling law paper.Even if you increasethe number of parametersby infinitythat would only decreaseby a factor of 10the amount of datathat you needin order tokeep the same loss.Humans are somewherebetweenthousands to millionsof times more sampleefficient than these models.So scalingthe sizeof current modelssimply can'tmake up for that discrepancy.And this really does suggestthathumans are in adifferent scaling curveall together.As soon as I earn moneyI want to put it to work.But I also need to savefor things likeupcoming expensesand estimated taxes.So to figure out exactlyhow much I need to set asideI ask command.Command is AIthat is builtinto Mercurywhich is my baking platform.And since I alreadyuse Mercuryto run my entire businesscommand has accessto all the informationit needs to get worked on.I just tell commandthe date I'm interested inand it does the rest.It takes my current balanceand adds whateverinvoices will we doby the cutoff.Then it reviews mylast six monthsof transaction history.So it can subtract outmy monthly average expensesalongwith anyscheduled payments.And if there'sanything irrelevantcoming upthat's not in Mercury yetI can just fly it.Things likeheads upthere's a $12,000contractor paymentthat's slated for July.And that gets includedBecause this is allhappening in chatand every answerhas links to theunderlying dataI can easilydoublecheck command's work.And once I'm convincedI can just tell commandalright that looks goodjust transfer the surplusto my personal account.And you willimmediately draftthe transferfor me to approve.Command is live now.visitmercury.comslash commandto learn more.Mercury is a fintech companynot an FDIC in short bank.Banking services providedthrough Choice Financial Groupand ColumnNAmembers FDIC.AI-generated responsesand suggested actionsmay varyand are not guaranteed.Okay,all thesenerdy comparisonsyou might askwhy do we even careabout sample efficiency?

Is this actually necessaryfor the labs to achievethe two overarchingobjectives they havewhich areone,automate white color workand two,automate AI researchitself.The best of the labsare making withwhite color workis that the common tasksthat our software engineeror analystor accountant needs to doare common.And as a resultyou can bring theminto the trainingdistributionquite easily.If you look at therevenue curvesof these labsor the last few monthsit does suggestthat there's an enormousamount of valuefrom bringinginto distributionthese kinds of common taskseven if we can'treplicate whateveris makinghuman learningso special.And it might be moreinefficient to trainAI to do these kindsof tasksthan it is to train humans.But so what?

Human lifespansimply does not allowfor the quantityand the breadthof trainingthat these modelsexperience.If you,as a human,had some weirdlearning disabilitywhere you needed to readthrough every publicrepository on GitHubbefore you could be acompetent software engineer,then it would simply notmake senseto train you up.You'd be on socialsecurityby the early stagesof your educationand even onceyou were trainedyou would only beable to workon one projectat a time.But AIs can learnthese skillsby firehosingGigawats of trainingat a time.And what they learncan be amortizedacross billionsof sessionsat once.So we can beludicrously inefficientin training them upand still bewildly in the green.And then there's aquestion ofwell,how muchout of distributionthinkingdo white-collaremployees need to do,that you simplycan'train forin advance.This is morea question aboutthe natureof different jobsthan it isa question aboutAI research.And it alsodepends onwhich jobyou're talking about.Some jobsare so mechanicaland predictablethat we wereable to automatethem longbefore themodern eraof AI.For example,Bank tellersor travel agents.But there are otherjobswhich requiredealingon a dailybasiswith problemsthat arequite distantfrom thedatage distribution.I thinksoftwareengineeringis probablyone such.This is the jobthat AIsare supposedto take first,butI would be willingto betthat there'soverall moredemandfor humansoftwareengineersin2027than there isright now,largelydueto thecomplementaryinputof AI.Thelapsplansfor thisladdercategoryof jobsis firstto automateAI researchand thenhavethe automatedAI researcherssolvethe sampleefficiencyproblem.So thenthe questioniscan AIswhichdo nothavehumanlevelsampleefficiency.Nunthelesssolvethe remainingresearchproblemsthat standon the wayof human-likeintelligenceand learning.This is a very complicated questionand I'll have to address it in a much longerfutureblockpost.But just to tease it a bit,I think that the way that peoplecurrently think about anintelligence solutionis very clumsybecause either people dismissthe possibility of AIspeeding up AI progressall togetheror they assume that some kindof God pops out the other end.They don't reason carefullyabout what it looks liketo have a period where AIprogress is much faster thanusualbut have that happenatopatelapseand the particular kindsofintelligencesthat LOMs are.But I'll save that for next time.In the meanwhile,if you want to read thisblockpostor all the otherblockposts I writeor be alertedwhen I write a futureblockpost,go site enoughfor my newsletterat my websitethuarkash.com.Alright,I'll see you later.
