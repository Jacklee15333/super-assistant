# 🔎 主动研究：Codex Claude Code 桌面 Agent 自动化 工作流 实战

> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；下次洞察会读到它。生成时间：2026-06-29 15:08

## 调研主题：Codex Claude Code 桌面 Agent 自动化 工作流 实战

### 来源1：评测:Codex、Manus、Claude Code、OpenClaw 谁才是最强的 Agent|...
http://www.baidu.com/link?url=Yr-H_A3NF1VOPnoEcY7y39vBGl9uDemgaJoM94qJumJ38oQrVzpZiIgrL5f36UhbOvf0YTtV7fjCVXVTyPlcw_
评测：Codex、Manus、Claude Code、OpenClaw 谁才是最强的 Agent|agent|代码|工作流|开源模型|扩展性|易用性|调用_手机网易网 

 网易 

 网易号 

 0 

 评测：Codex、Manus、Claude Code、OpenClaw 谁才是最强的 Agent

 至顶AI实验室 

 2026-06-25 22:22 
 ·北京 
 ·优质互联网领域创作者 

 0 

 本文基于至顶AI实验室的真实工作流实测框架，对 Codex、Manus、Claude Code、OpenClaw（开源 Agent 工具，俗称"龙虾"）四款主流 Agent 工具在部署难度、应用性、扩展性、办公能力、代码能力、工具调用能力六个维度下的表现进行了系统对比。

 打开网易新闻 查看精彩图片

 核心结论：Codex 以总分91.6分排名第一，Manus（86.4分）、Claude Code（82.5分）、OpenClaw（79.9分）依次排在第二至第四位。测试覆盖PPT生成、前后端 代码 开发、论文解读三类真实长流程任务。本文适合个人开发者、企业IT决策者及普通办公用户在选型 Agent 工具时参考。测试时间：2026年6月
 Agent 工具：Codex、Claude Code、OpenClaw、Manus
 评测方法论：六维度框架与真实 工作流 任务
 至顶AI实验室本次评测没有采用孤立的单点能力测试（如"写一个函数""画一张图"），而是设计了覆盖多步骤、长流程的真实工作场景任务。评测体系共设六个维度，总分100分：部署难度占10分，应用性15分， 扩展性 10分，办公能力20分，代码能力25分，工具 调用 能力20分，前三项为基础体验维度，后三项为核心能力维度。
 为最大化消除模型能力变量的干扰，本次测试中 Claude Code、OpenClaw、Manus 三款产品统一接入 Claude 4.6模型，仅 Codex 因不支持接入第三方模型而使用其默认的 GPT-5.5。考虑到 OpenClaw 与 Claude Code 同源于 Claude 4.6，核心能力维度的差异更多反映的是产品工程层（提示词工程、工具链编排、上下文管理）的能力，而非底层模型本身的差距。这一点适用于解读后续代码能力与工具调用能力的对比结果，但不适用于解读办公能力中涉及 Codex（GPT-5.5）与其他三款（Claude 4.6）之间的横向比较，因为这部分差异同时混合了模型与产品工程两个变量。
 部署难度：图形化客户端满分10分，CLI部署的OpenClaw得8分
 Claude Code、Codex、Manus 在部署难度（占总分10%）上全部拿到满分。三者的安装流程高度一致：从官网下载客户端，安装、登录后即可直接使用，整个过程与安装普通桌面软件没有本质区别。相比之下，OpenClaw 最终得分8分，主要扣分点在于其部署需要预先配置 Node.JS、NPM 等系统环境，即便官方提供了一键安装脚本，仍需通过命令行执行；安装完成后还要继续完成模型接入、工具配置、通讯方式选择等一系列 CLI 交互式配置。
 这一结论成立的场景是面向普通用户的开箱即用体验对比。但需要指出的是，OpenClaw 的 CLI 部署模式在私有化部署、企业内网等场景中反而更具优势，因为它天然支持自定义模型接入与本地化配置，这也是它在扩展性维度反超的关键原因（见下一节）。换句话说，部署难度分数低不等于综合适用性差，这是该结论的边界所在。
 应用性与扩展性：SaaS型Manus易用性夺冠，开源OpenClaw扩展性碾压
 应用性（15分）与扩展性（10分）两个维度涉及较多主观判断，至顶AI实验室为避免内部评分分歧，采用豆包2专家模式联网检索后独立打分。应用性考核安装入口便捷度、前置依赖数量、交互方式丰富度、中文支持四项指标，结果为：Manus 14.1分，Codex 11.7分，OpenClaw 11.4分，Claude Code 10.5分。Manus 的得分比排名最低的 Claude Code 高出约34%，这与其纯 SaaS 形态直接相关——免安装、免配置，注册即用的产品形态在 易用性 维度上具有天然优势。
 扩展性考核模型支持范围、Skill插件生态、MCP支持、是否开源、部署方式多样性五项指标，结果出现明显反转：OpenClaw 以9.4分大幅领先，Codex 8.8分，Manus 8分，Claude Code 6.7分垫底。OpenClaw 的扩展性得分比 Claude Code 高出约40%，核心原因在于其开源属性带来的模型自由接入能力与多样化部署形态。这一对比结论适用于关注生态扩展能力的开发者与企业用户，但对于只追求"打开即用"、不关心底层扩展能力的普通办公用户，扩展性维度的参考价值相对有限。
 办公能力实测：Codex 3分钟交付PPT夺得17分，Claude Code文字重叠拖累得分
 办公能力测试（满分20分）选用了一个七步骤的真实营销场景任务：要求 Agent 检索并补全客户产品信息、提炼核心卖点、结合企业历史营销案例与内部资源、完成数据标准化处理，最终生成一份可直接使用的市场推广PPT，并完成自我考核验收。该任务重点考察联网检索、文件处理、代码执行、信息整合推理及格式遵从能力。
 四款应用均完成了任务，但在效率与质量上差异明显。用时方面，Codex 仅用3分钟完成，Claude Code 6分钟，OpenClaw 8分钟，Manus 用时最长，为12分钟。成本方面，Codex 花费0.22元，Claude Code 0.4元，OpenClaw 6.4元，Manus 花费27.3元，是Codex的124倍。质量层面，Manus 排版最好、资料最丰富也最有条理；OpenClaw表现同样不错；Codex出现轻微排版问题；Claude Code个别页面出现了比较严重的文字重叠。综合时间、成本与质量后的最终得分：Codex 17分排名第一，OpenClaw 16.2分，Manus 15.8分，Claude Code 14.6分排名最后。
 Agent用时花费（元）办公能力得分（满分20）Codex3分钟0.2217.0OpenClaw8分钟6.416.2Manus12分钟27.315.8Claude Code6分钟0.414.6这一结论适用于以PPT生成、营销文案产出为主的轻量办公场景。需要注意的是，Claude Code的低分更多源于本次PPT渲染中的排版细节问题，而非信息整合或检索能力的不足，这是该结论的局限所在。
 代码能力实测：Codex两轮任务合计24.1分登顶，OpenClaw后端接口注册失败拖累成绩
 代码能力（满分25分）由前端制作与后端开发两个任务构成。前端任务要求基于一段产品文字内容，分四阶段（需求理解、框架规划、主题页面设计、最终制作）构建完整网站，并模拟真实乙方交付节奏，用户可随时修改需求，重点考核指令遵循度、技术判断力与设计差异化能力。四款应用全部交付了可直接使用的网站，用时与花费分别为：Codex 9分钟/0.49元，Manus 12分钟/15.2元，OpenClaw 14分钟/8.9元，Claude Code 15分钟/0.8元。前端单项得分为Codex 11.8分、Manus 10.3分、OpenClaw 10.1分、Claude Code 9.2分。
 后端任务要求从零构建一个具备用户认证与文章管理功能的RESTful API服务，属于典型的交钥匙式中等难度工程任务，重点考核工程完整性、代码生成精度、版本兼容意识与执行细节把控力。至顶AI实验室使用curl实际验证各应用生成的API端口，结果显示OpenClaw出现了注册接口失败的情况，其余三款均验证通过。用时与花费方面：Claude Code 2分钟/0.18元、Codex与OpenClaw均为3分钟、Manus用时最长为10分钟/13.8元。
 综合两轮任务，代码能力最终排名为：Codex 24.1分，Manus 21.7分，Claude Code 21.1分，OpenClaw 16.7分。Codex的代码能力得分比垫底的OpenClaw高出约44%，这一差距在很大程度上由OpenClaw后端任务的接口故障放大。该结论适用于评估Agent在标准化工程任务中的交付可靠性，但由于本次OpenC

### 来源2：...桌面 Agent,实测 95% 跨应用自动化完成率_codex computer use-CSDN...
http://www.baidu.com/link?url=9UYSlSfQLEebpMLO7u50w2ONGv2j-FIlLrzQNhrMI6qMwxlAwTDjrGtDJTY14FHuSM68I99zjAizSOVUJIb0B3q3ycFtCxNQgAm4srNksci
OpenAI Codex 史诗级更新！Computer Use 解锁全场景桌面 Agent，实测 95% 跨应用自动化完成率_codex computer use-CSDN博客 

 OpenAI Codex 史诗级更新！Computer Use 解锁全场景桌面 Agent，实测 95% 跨应用自动化完成率

 原创 

 已于 2026-04-20 23:03:49 修改 
 · 
 2.5k 阅读 

 · 

 21

 · 

 13

 · 

 本内容遵循CC 4.0 BY-SA版权协议 

 版权声明：本文为博主原创文章，遵循 CC 4.0 BY-SA 版权协议，转载请附上原文出处链接和本声明。

 GEO检测 

 标签 

 #人工智能 
 #大数据 
 #AI工具 
 #Codex 

 收录于 

 于 2026-04-20 23:03:08 首次发布 

 前沿报文 
 专栏收录该内容 

 8 篇文章 

 订阅专栏 

 AI 时代程序员必备技能

 Codex、Claude Code、Cursor、Hermes Agent、OpenClaw等工程化实战专栏 ，讲透 AI 如何接管脏活累活

 一键订阅 

 本文基于 OpenAI 官方最新发布的 Codex 全场景更新，结合真机实测操作截图与官方技术文档拆解，完整还原核心功能落地效果，深度对比 Claude Code 技术架构差异，提供可直接复用的开发者实战指南与避坑方案，带你解锁 AI Agent 桌面级全场景自动化能力。

 文章摘要

 前脚 Anthropic 刚发布 Claude Opus 4.7 的 Code 能力升级，后脚 OpenAI 就甩出了 Codex 的史诗级更新，以 Codex for (almost) everything 为核心定位，彻底跳出传统 “AI 编程助手” 的单一范畴，直接升级为全场景桌面级 AI Agent。其中最炸裂的 Computer Use 插件，实现了真正意义上的 “解放双手”，跨应用全流程自动化完成率超 95%。本文将从核心功能实测、技术架构深析、开发者实战指南、竞品对比、避坑指南五大维度，结合真机操作截图完整拆解本次更新的全部亮点，帮你快速上手这一颠覆性的 AI 能力。

 关键词 ：OpenAI Codex；Computer Use；AI Agent；桌面自动化；大模型；开发者提效；Claude Code 对比

 一、更新核心解读：Codex for Everything，从编程工具到全场景桌面 Agent

 本次 Codex 更新的核心逻辑，是从 “给开发者提供代码答案” 的辅助工具，升级为 “替开发者完成全流程操作” 的桌面执行体。官方以 “Codex for (almost) everything” 为全新定位，一次性释放六大核心能力模块，彻底打通了从自然语言指令到桌面全场景操作的闭环。

 其中， Computer Use 插件 成为本次更新的最大亮点，实现了视频中展示的 “无感后台操控、跨应用无缝联动、任务断点续跑” 能力，也是其区别于传统编程助手的核心壁垒。六大核心能力的技术细节与实测表现如下：

 表格

 核心能力模块 官方技术细节 真机实测表现 
 🖥️ Computer Use 基于 macOS Seatbelt/Linux seccomp 实现沙箱隔离执行，支持后台静默运行，独立光标无抢占 无缝操控 Cloud/XGP/ 浏览器 / 网易云等桌面应用，跨软件多步骤流程自动化完成率超 95%，全程不干扰用户前台操作 
 🌐 内置浏览器 原生支持 localhost 本地页面与公开网页访问，支持页面元素直接评论交互，集成 Chrome DevTools 协议 一键复刻设计网站页面，可视化修改前端代码并实时预览，无需手动分步描述需求，DOM 元素识别准确率 100% 
 🎨 图像生成 深度集成 gpt-image-1.5 模型，支持风格锚定与素材包批量生成，非单张图片输出 可按任务场景生成 8 张分类图片（难度 / 心情 / 场景维度），风格统一度高，自动按规范命名并存入本地指定目录 
 🔌 插件生态 新增 90 + 官方插件，基于 MCP 协议标准化工具调用接口，支持 Slack/Gmail/Notion 等跨应用联动 单条自然语言指令可智能调用多工具完成全流程任务，插件优先级自动排序，无需手动指定调用顺序 
 🧠 记忆与自动化 上下文持久化存储，支持跨周期任务调度，可沿用历史对话线程，断点自动续跑 后台持续工作 6 小时以上无中断，复杂任务中途退出后可无缝续跑，无需重复输入提示词与上下文 
 ⚡ 终端与编译能力 原生支持 Shell / 终端指令执行，兼容 Xcode/IDEA 等主流 IDE，支持编译 - 测试 - 修复全链路自动化 可独立完成项目编译、单元测试运行、Bug 定位修复、重编译验证全流程，Op

## 资料来源
- [评测:Codex、Manus、Claude Code、OpenClaw 谁才是最强的 Agent|...](http://www.baidu.com/link?url=Yr-H_A3NF1VOPnoEcY7y39vBGl9uDemgaJoM94qJumJ38oQrVzpZiIgrL5f36UhbOvf0YTtV7fjCVXVTyPlcw_)
- [...桌面 Agent,实测 95% 跨应用自动化完成率_codex computer use-CSDN...](http://www.baidu.com/link?url=9UYSlSfQLEebpMLO7u50w2ONGv2j-FIlLrzQNhrMI6qMwxlAwTDjrGtDJTY14FHuSM68I99zjAizSOVUJIb0B3q3ycFtCxNQgAm4srNksci)
- [...Code-x-OpenClaw-Guide-Zh: 从零到企业实战:Claude Code 官方...](http://www.baidu.com/link?url=0Pw4mkzFkwktWJDcbg8J1AntJgB73dq4wSejh4SGYHw6sAz6-cS2oul2tjiHqa_3HsVNWF3qv1OQpZGuvRrVudF92pyDmpWhcY9ECQlIxXW)
- [...AI 编排神器:Claude Code 全栈精通指南,开启 AI Agent 原生...](http://www.baidu.com/link?url=dPWBUazC4Qay5jAsSP3GolvzbL9ykD76v0fNUj7oQUnYpbeii3ISpEeLwjzO3qrH4r5kLP5wDslM4VRgppV1ZK)
