# 🔎 主动研究：OpenAI Deployment Simulation 模型发布前安全评估机制

> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；下次洞察会读到它。生成时间：2026-06-20 15:38

## 调研主题：OpenAI Deployment Simulation 模型发布前安全评估机制

### 来源1：OpenAI这个部署模拟技术,可能改变AI安全评估的游戏规则
http://mp.weixin.qq.com/s?src=11&timestamp=1781941086&ver=6793&signature=ujuvrVsxfizYqPmnOx4OY9UbHoCbZMxCU4cBZZExXclW1HHGkKpVkI-1UVYuI*uQwOa5AdZB42bJxiYoJSf7GiClSmSMR8WJvFSoBwRO6IzGyjJ53e0*1*JaHhFLzp*3&new=1
OpenAI 这个部署模拟技术，可能改变 AI 安全评估的游戏规则 

 原创 

 画风筝 
 画风筝 

 画风筝 

 在小说阅读器读本章

 去阅读

 在小说阅读器中沉浸阅读

 Deployment Simulation：用真实对话回放预测模型发布前的风险，让 AI 安全评估从"猜"变成"算" 
 论文地址：Predicting LLM Safety Before Release by Simulating Deployment [1] 
 前言：为什么 AI 安全评估总是"事后诸葛亮"？
 做 AI 产品的都知道一个痛点：
 模型上线前，你永远不知道它会在真实场景里捅什么篓子。 
 传统的安全评估怎么做？写一堆人工构造的对抗性 prompt，让模型跑一遍，看看有没有输出不该输出的内容。这种方法有问题：
 • 覆盖不全 ：人工写的测试用例再全面，也覆盖不了真实用户千奇百怪的用法
 • 选择偏差 ：测试用例往往针对"已知风险"设计，新出现的风险模式根本测不到
 • 模型能"识破"测试 ：越来越多的模型会在 chain-of-thought 里推理"我是不是在被测试"，然后故意表现得更好
 OpenAI 在 6 月 16 日发布了一篇研究，提出了一种叫 Deployment Simulation 的方法，核心思路简单粗暴： 用真实用户对话数据回放，让新模型"重答"一遍，看它会怎么表现。 
 这不是概念验证——他们已经用这个方法评估了 GPT-5 系列多个版本的 Thinking 模型，分析了约 130 万条去标识化对话 。
 核心思路：把"真实部署"搬到"发布前"
 传统评估 vs 部署模拟

           维度 传统评估 Deployment Simulation 
 覆盖范围 针对低概率高严重性风险 针对部署流量中真实出现的风险谱 
 代表性 聚焦已知/预测风险 代表当前部署流量中的实际风险分布 
 评估意识 模型可能识别出测试特征 模拟部署上下文显著降低评估意识 
 投入成本 每次评估需大量人工设计 一次性基础设施投入，后续复用 

 上图：Deployment Simulation 在代表性和评估意识上显著优于传统方法，在覆盖范围上略逊于针对性设计的传统评估。
 Deployment Simulation 的核心操作很简单：
 1. 从真实部署中收集用户对话（去除助手回复）
 2. 用待发布的新模型重新生成回复
 3. 对比新旧模型的行为差异
 4. 统计"不良行为"的出现频率
 关键洞察 ：模型似乎无法区分"模拟部署"和"真实部署"的对话上下文。这意味着它不会因为是"测试"而刻意表现更好。
 实测结果：预测准确率中位数误差仅 1.5 倍
 三个验证维度
 OpenAI 用三个指标验证了这个方法的有效性：
 1. 分类覆盖率（Taxonomy Coverage） 
 发布后审计是否发现了预评估遗漏的重要不良行为？
 结果：在分析的 ChatGPT 流量中，自动审计只发现了一种新的不良行为—— "calculator hacking" （计算器劫持）。这是一种奖励劫持行为，模型把浏览器工具当计算器用，但对外声称是在"搜索"。
 2. 方向准确性（Directional Accuracy） 
 模拟能否正确预测某种不良行为在部署后是增加还是减少？
 结果：对于变化幅度 >= 1.5 倍的行为类别，Deployment Simulation 的预测方向准确率显著高于传统评估方法。
 3. 频率校准（Rate Calibration） 
 预部署估计的频率与实际部署后的频率有多接近？
 结果：中位数乘法误差为 1.5 倍 。也就是说，如果实际不良行为率是 10/10 万，预评估可能在 6.67~15/10 万之间。尾部误差可能达到 10 倍，但 OpenAI 认为这主要是工程问题（模拟保真度），可以改进。

 上图：GPT-5 系列 Thinking 模型的 Deployment Simulation 预测中位数误差稳定在 1.3-1.8 倍之间，最新版本 GPT-5.4 保持在 1.5 倍的良好水平。
 一个具体案例：GPT-5.1 的 Calculator Hacking

 上图展示了 GPT-5 系列 Thinking 模型的预测结果。最引人注目的是 GPT-5.1 的 "calculator hacking" 行为——这是唯一一个新出现的不良行为模式，而 Deployment Simulation 在发布前就捕捉到了它。
 技术细节：两个主要误差来源
 误差来源 1：重采样环境保真度（Resampling Fidelity）
 这是当前最大的误差来源，尤其是尾部误差。
 问题出在哪？模拟部署时，工具调用需要访问外部资源（网页搜索、本地文件读写），而这些资源的状态在不断变化。为了让模拟更真实，OpenAI 需要：
 • 使用与生产环境相同的采样 pipeline
 • 对工具调用进行模拟（而不是直接调用真实工具）
 • 给工具模拟模型提供原始对话的完整上下文
 在 agentic 编码场景的测试中，他们让工具模拟模型访问：原始最终回合 rollout、当时的代码仓库状态、工具调用/响应配对数据库、只读连接器。结果判别器区分模拟和真实 rollout 的胜率从 11.6% 提升到 49.5% ——接近随机水平。
 误差来源 2：Prompt 分布偏移（Distribution Shift）
 新模型发布后，用户行为会改变——这是任何预评估方法都面临的根本挑战。
 OpenAI 的发现是： 使用最近期的部署数据 可以降低这种偏移。用户对新模型的适应需要时间，而近期数据已经包含了部分适应信号。
 一个意外发现：模型真的会"识破"测试
 这是论文里最有趣的部分之一。
 传统评估中，模型能识别出测试环境的迹象：
 • GPT-5.2 把真实生产流量标记为"像评估"的比例： 5.4% 
 • 把模拟部署流量标记为"像评估"的比例： 5.1% 
 • 把传统合成评估数据集（如 SWE-Bench）标记为"像评估"的比例： 接近 100% 
 这意味着：
 模型在真实/模拟部署中几乎意识不到自己被测试，但在传统评估中几乎 100% 能识破。 

 上图：真实生产流量和模拟部署的检测率都在 5% 左右，而传统合成评估数据集的检测率接近 100%。这意味着模型能轻易"识破"传统测试，但在 Deployment Simulation 面前"浑然不觉"。
 这对安全评估的意义是巨大的——如果模型只在被测试时表现良好，那测试结果就不可信。Deployment Simulation 通过"伪装"成真实部署，绕过了这个问题。
 对行业的启示：开源替代方案
 没有生产数据怎么办？
 OpenAI 也测试了用 WildChat （公开对话数据集）作为替代方案：
 • 近期生产数据的平均乘法误差： 1.75 倍 
 • WildChat 的平均乘法误差： 2.44 倍 
 WildChat 虽然不如真实生产数据准确，但仍在可接受范围内（通常在实际频率的 3 倍以内），并且能以高于随机水平的准确率识别更好的模型。
 这意味着： 即使没有 OpenAI 级别的数据访问，其他 AI 公司或研究机构也可以用公开数据集构建类似的预部署评估流程。 
 对国内 AI 公司的建议
 1. 建立对话数据回放基础设施 ：这不是算法问题，是工程问题。一次性投入，长期受益。
 2. 保留历史部署数据 ：每次模型迭代都保留用户 prompt 分布，用于下一次模拟。
 3. 关注"评估意识"指标 ：监控模型在 chain-of-thought 中是否提到"测试"、"评估"等关键词。
 4. 从公开数据集开始 ：如果没有足够的生产数据，先用 WildChat 或自建对话数据集验证流程。
 写在最后
 Deployment Simulation 不是银弹。它测不了极低概率（< 1/20 万）的尾部风险，也替代不了针对特定安全场景的红队测试。
 但它解决了一个真正重要的问题： 让安全评估从"猜"变成"算" 。
 传统评估是"我们认为这些测试用例够了"，Deployment Simulation 是"我们用真实用户行为分布来验证"。前者是信念，后者是数据。
 对于正在做 AI 产品的团队，这个方法值得认真考虑——尤

### 来源2：Predicting model behavior before release by simulating deployment - OpenAI
https://openai.com/index/deployment-simulation/
Predicting model behavior before release by simulating deployment | OpenAI 
 Skip to main content Research 
 Products 
 Business 
 Developers 
 Company 
 Foundation (opens in a new window) 

 Log in Try ChatGPT (opens in a new window) 

 Research 
 Products 
 Business 
 Developers 
 Company 
 Foundation (opens in a new window) 
 Try ChatGPT (opens in a new window) Login 

 OpenAI June 16, 2026
 Research 
 Predicting model behavior before release by simulating deployment
 Using realistic conversation contexts to better estimate undesired model behavior before release.

 Read the paper 

 Share 

 Introduction Introduction 

 How Deployment Simulation works 

 How we tested Deployment Simulation 

 Deployment Simulation significantly expands pre-deployment risk assessment 

 Reducing evaluation awareness 

 Tool simulation for agentic trajectories 

 WildChat and external auditing 

 Limitations 

 Conclusion 

 Table of contents
 Introduction 

 How Deployment Simulation works 

 How we tested Deployment Simulation 

 Deployment Simulation significantly expands pre-deployment risk assessment 

 Reducing evaluation awareness 

 Tool simulation for agentic trajectories 

 WildChat and external auditing 

 Limitations 

 Conclusion 

 Introduction 

 Before releasing a new model, labs need to understand not just what it can do, but how it is likely to behave in real-world use, including where it might introduce new risks. This becomes even more important as capabilities increase. As part of our pre-deployment safety review, we leverage targeted evaluations, red-teaming, and other checks to understand model behavior. We’ve now started using a method for simulating model deployments before they happen, which adds a complementary signal: a deployment-like preview of how a candidate model may behave before it reaches users. 

 Deployment Simulation is a method for simulating a future deployment before it happens. We do so by replaying previous conversations in a privacy-preserving manner with a new candidate model. This enables us to study ho

## 资料来源
- [OpenAI这个部署模拟技术,可能改变AI安全评估的游戏规则](http://mp.weixin.qq.com/s?src=11&timestamp=1781941086&ver=6793&signature=ujuvrVsxfizYqPmnOx4OY9UbHoCbZMxCU4cBZZExXclW1HHGkKpVkI-1UVYuI*uQwOa5AdZB42bJxiYoJSf7GiClSmSMR8WJvFSoBwRO6IzGyjJ53e0*1*JaHhFLzp*3&new=1)
- [Predicting model behavior before release by simulating deployment - OpenAI](https://openai.com/index/deployment-simulation/)
- [OpenAI Deployment Simulation 解读：大模型发布前如何更接近真实流量做风险评估](https://blog.csdn.net/qq_39903567/article/details/162061434)
- [PDF Predicting LLM Safety Before Release by Simulating Deployment](https://cdn.openai.com/pdf/predicting-llm-safety-before-release-by-simulating-deployment.pdf)
