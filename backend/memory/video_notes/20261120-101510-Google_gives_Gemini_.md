# Google 赋予 Gemini 操控 Mac 的能力，让 AI 替你完成电脑任务｜TechCrunch

- 来源链接：https://techcrunch.com/2026/11/19/google-gives-gemini-the-ability-to-use-your-mac-for-you/
- 作者：Sarah Perez
- 提取时间：2026-11-20 10:15
- 类型：网页文章
- 发布时间：2026-11-19 18:09
- 原标题：Google gives Gemini the ability to use your Mac for you | TechCrunch
- 标签：电脑自动化、AI智能体、Gemini、跨应用操作、办公效率

## 🤖 AI 分析

## 一句话概括
Google 正式为 macOS 版 Gemini 桌面应用引入 **Computer Use（计算机操作）**能力，让 AI 不再局限于聊天和生成内容，而是能够直接操作 Mac 原生应用、处理本地文件、浏览网站，并在后台自主执行跨应用、多步骤的任务；这既是 Google 对 OpenAI、Anthropic、Meta 等竞争对手的追赶，也是 AI 从聊天助手向真正能替人干活的智能体（AI Agent）演进的重要一步。

## 背景与主题
Google 宣布，将 Computer Use（计算机操作）能力整合进 macOS 版 Gemini 桌面应用，使 Gemini 能够根据用户的自然语言指令，直接在电脑上操作应用程序、访问网站并完成实际工作，而不仅仅是提供操作建议。
不过，Google 在这一领域并不是先行者。文章指出，OpenAI、Anthropic 和 Meta 等领先 AI 厂商此前已经在各自的桌面产品中提供了智能体功能，而 Google 近期才开始加快相关产品的推出，包括 Gemini 的 **Tasks（任务）**功能和面向家庭事务管理的 CC AI Agent。
这次更新最重要的变化，是 Gemini 可以在后台执行跨文件、跨应用、跨网页的复杂任务，同时提供实时执行预览，并保留用户暂停、停止和审批操作的权利。
文章由科技媒体 TechCrunch 从产品发布、行业竞争、实际使用场景和开放条件等角度进行报道，重点介绍 Google 此次更新的能力、用途及限制，并没有提供独立的实测性能数据。

## 核心观点

### 1. Gemini 从回答问题的聊天助手，升级为能够直接操作电脑的 AI Agent
此次更新最大的意义，是 Gemini 开始具备直接在用户 Mac 上执行操作的能力，而不再只是告诉用户应该怎样完成某项任务。传统聊天式 AI 主要负责理解问题、生成文字、编写代码或提供操作步骤，真正点击软件、整理文件、填写表格的工作仍然需要人类亲自完成。引入 Computer Use 后，用户可以直接用自然语言描述最终目标，由 Gemini 在 Mac 原生应用和网页之间执行相应步骤。文章明确提到，Gemini 可以代替用户导航 Mac 应用程序、浏览网站，并处理涉及本地文件和多个应用的复杂任务。这意味着 AI 的角色正从提供答案的顾问转向执行任务的助手，其价值不再只取决于回答质量，还取决于能否真正完成工作。
这一变化可以用一个典型场景理解：过去，用户可能让 Gemini 解释如何将一批文件分类整理；现在，则有机会直接要求它根据指定条件把文件放进对应文件夹。前者交付的是操作方法，后者交付的是操作结果。

### 2. Computer Use 的核心价值，是打通本地文件、桌面应用与网页之间的操作流程
Google 强调，这项能力支持涉及本地文件、应用程序和互联网的多步骤任务，而不是只能在某一个网站或应用内部操作。现实工作中的大量任务都不是单一动作，例如制作一份汇报材料，可能需要先查看本地文件，再读取在线仪表盘中的数据，最后在演示软件里制作幻灯片。传统 AI 助手即使能生成一份精彩的汇报提纲，也可能无法替用户完成文件提取、软件切换和内容整理等实际操作。Computer Use 的意义，就是让 AI 有机会处理这些原本需要人工在不同软件之间反复切换的环节。任务执行的单位从单次问答变成了完整工作流程，这也是智能体区别于普通聊天助手的重要特征。
但需要注意，文章并没有证明 Gemini 已经能够可靠处理任意复杂流程，也没有说明它支持哪些具体的第三方 Mac 应用。因此，跨应用执行是此次发布明确提出的能力方向，不应直接理解为所有软件和操作都已经得到完整支持。

### 3. Gemini 可以在后台执行任务，用户不必让出自己的屏幕和鼠标
此次发布中一个非常值得关注的设计，是 Gemini 能够在后台工作，同时让用户继续使用自己的电脑。根据文章描述，当用户向 Gemini 下达任务后，可以在聊天界面中看到智能体执行任务的实时预览（Live Preview）。与此同时，用户的主屏幕和光标仍然可以用于其他工作，而不会因为 Gemini 正在操作电脑，就必须停止自己的活动。这样的设计意味着，人和 AI 有机会在同一台电脑上并行处理不同任务，而不是轮流占用操作界面。
这里体现了重要的产品思路：AI 应该替用户承担工作负担，而不是让用户为了使用 AI 被迫中断原有工作。
例如，用户可以安排 Gemini 整理某个文件夹，自己继续撰写邮件或处理其他事务；通过聊天中的执行预览了解任务进度。文章确认了这一类并行工作的产品设计，但没有进一步说明后台操作的技术实现、资源占用或对其他应用的兼容性，因此暂时无法判断它在复杂真实环境中的稳定程度。

### 4. Google 在桌面 AI Agent 竞争中起步较晚，此次更新具有明显的追赶意味
TechCrunch 特别指出，Google 推出这项能力的时间相对较晚。文章点名的竞争对手包括 OpenAI、Anthropic 和 Meta，这些公司此前已经在桌面应用中提供了不同形式的 Agentic Features（智能体功能）。这种竞争的重点不只是比较底层 AI 模型有多聪明，还在于谁能让模型更有效地参与用户的日常工作。Google 这次推出 Computer Use，可以被理解为试图补上 Gemini 在桌面任务执行方面的一块能力拼图。对于 AI 厂商而言，如果用户逐渐习惯让助手直接完成任务，那么计算机操作能力就可能成为影响桌面 AI 产品竞争力的重要因素。
文章没有提供不同厂商之间的成功率、执行速度、支持软件范围或用户规模数据，因此不能据此判断哪家产品最强。可以明确的是，作者将 Google 此次发布放在了整个 AI Agent 行业加速竞争的背景之中。

### 5. Computer Use 并不是 Google 唯一的 Agent 产品，而是其智能体布局的一部分
文章提到了 Google 近期推进的另外两项智能体相关产品：Gemini Tasks 和 CC AI Agent。Tasks 是 Gemini 应用内部的一项功能，可以让 AI 以更接近智能体的方式协助用户，例如登录网站、在线购买商品或者预约服务。CC 则是 Google 在此前的 9 月宣布的一款经过重新设计的 AI Agent，主要面向家庭事务管理，帮助家庭成员协调电子邮件、日历、聊天记录和待办任务。Google 最近才开始邀请早期测试者体验 CC，而文章同时指出，Tasks 的更广泛推出也是近期才宣布的。
把这三项能力放在一起，可以看到 Google 正在从不同方向扩展智能体的应用范围：Tasks 负责应用内任务执行，CC 面向家庭信息和日程协调，Computer Use 则让 Gemini 直接参与桌面环境中的操作。它们的目标有一定关联，但目前不能仅凭文章就认定三者已经形成完全整合的统一系统。

### 6. 首批应用场景主要集中在重复、烦琐、规则明确的工作
Google 列举的实际使用场景非常具体，包括填写表单、对一批文件反复执行同样的任务、根据特定标准将文件分类到不同文件夹，以及利用本地文件或在线仪表盘的信息制作幻灯片。这些工作通常不是高度创造性的活动，而是步骤较多、重复程度较高、需要持续注意细节的日常操作。它们的共同特点是：用户往往知道最终想得到什么结果，但实际完成过程中需要进行大量点击、查找、复制、粘贴和整理。
例如，用户有几十个需要分类的项目文件，可以先定义分类规则，再让 Gemini 尝试执行相同的整理流程；又或者需要定期根据在线数据制作演示材料，可以让智能体完成其中的资料整理和幻灯片生成环节。**这种场景的真正价值，是减少人类在机械性操作上投入的时间，把注意力留给判断、决策和内容审核。**不过，这些都是 Google 提出的适用场景，文章并未展示真实用户的批量测试结果，也没有给出实际节省多少时间的数字。

### 7. AI 获得操作权限的同时，用户仍然保有关键控制权
当一个 AI 系统能够直接操作电脑时，它所产生的影响就不再停留在文字输出层面，而可能真正改变文件状态、操作应用程序或触发网页行为。因此，文章特别强调，Gemini 和其他提供 Computer Use 能力的智能体一样，允许用户暂停、停止执行，并在操作发生前进行审批。这意味着 Google 并不是把电脑的所有控制权无条件交给 AI，而是在自动执行与人工监督之间设置了交互机制。实时预览进一步帮助用户了解智能体正在进行什么操作，从而在必要时进行干预。
这一设计尤其适合存在潜在风险的工作场景，例如修改重要文件、提交在线表单，或者涉及购买行为的流程。需要准确区分的是：文章说明用户可以审批操作，但没有说所有操作都必然要求逐项审批，也没有详细介绍权限管理、误操作恢复、数据隐私保护或安全隔离机制。
因此，能暂停、能停止、能审批是已经披露的产品能力；是否足以覆盖实际使用中的全部安全风险，还需要更多验证。

### 8. 首发仅支持美国、英语和付费订阅用户，说明产品仍处于有限开放阶段
Google 此次没有立即向所有 Gemini 用户开放 Computer Use，而是设置了明确的地域、语言、平台和订阅门槛。首批使用者需要位于美国、使用英语，并安装 Gemini for Mac 应用，同时拥有 Google AI Plus、Pro 或 Ultra 订阅。这意味着，免费用户、其他国家或地区的用户，以及不符合当前平台要求的用户，都不在文章所述的首发支持范围内。
Google 也没有宣布什么时候将这项能力扩展到其他市场或平台，包括是否以及何时支持 Windows。这样的有限开放方式，至少说明产品目前尚未实现全面覆盖，也给 Google 留出了观察实际使用情况、完善体验的空间。不过，文章并没有透露 Google 限制开放范围的具体原因，因此不能把地区和订阅门槛直接归因于安全问题、算力成本或某种商业策略。
从产品使用者的角度来看，这意味着它是一项值得关注的新能力，但并不等于所有 Gemini 用户现在都能立即使用。

### 9. 此次更新揭示了 AI 产品竞争的一个重要变化：从模型能力转向任务完成能力
综合文章中的产品设计和竞争背景，可以提炼出一个更深层的行业变化：AI 助手正在从以生成内容为中心，转向以完成任务为中心。过去，用户评判 AI 的重要标准可能是回答是否准确、写作是否流畅、推理是否合理；而在 Computer Use 场景下，还需要考虑它能否正确理解任务目标、选择适当操作、跨应用执行、处理异常并交付结果。Google 选择文件整理、表单填写和演示文稿制作等场景，正是因为这些任务能够直接体现 AI 对日常工作流程的实际帮助。实时预览、后台运行以及人工审批等设计，则说明成熟的 AI Agent 产品需要同时解决执行效率、用户体验和控制权问题。
但模型具有操作能力，不代表它已经具备稳定、可靠的自主完成能力。真正决定这类产品是否有长期价值的，仍然是任务成功率、出错成本、可控性，以及与人工操作相比是否能够显著节省时间。

## 关键事实与数据

### 一、产品发布与功能信息

| 项目 | 文章明确提供的信息 |
| --- | --- |
| 发布公司 | Google |
| 产品名称 | Gemini |
| 新增能力 | Computer Use（计算机操作） |
| 首发平台 | macOS |
| 使用入口 | Gemini for Mac 桌面应用 |
| 发布时点 | 文章称 Google 于周四宣布，未给出具体年月日 |
| 操作对象 | Mac 原生应用、本地文件、网页 |
| 执行模式 | 可在后台执行多步骤任务 |
| 过程查看 | 用户可通过聊天界面中的 Live Preview 查看实时执行过程 |
| 并行工作 | 用户仍可使用自己的屏幕和鼠标 |
| 用户控制 | 支持暂停、停止，以及操作发生前的审批 |
| 初始支持语言 | 英语 |
| 初始支持地区 | 美国 |
| 订阅要求 | Google AI Plus、Google AI Pro 或 Google AI Ultra |
| 其他平台上线时间 | 未公布 |
| 其他地区开放时间 | 未公布 |

### 二、Google 明确提及的五类使用场景

| 场景 | 原文所述能力 | 实际用途 |
| --- | --- | --- |
| 表单处理 | Filling out forms | 减少重复填写表单的人工操作 |
| 批量处理 | Repeating the same task across a batch of files | 对多个文件依次执行相同操作 |
| 文件整理 | Organizing files into folders based on specific criteria | 按规则自动分类、归档 |
| 幻灯片制作 | Creating slideshows from files | 利用本地文件中的内容制作演示文稿 |
| 在线数据处理 | Creating slideshows from information in online dashboards | 从在线仪表盘提取信息，制作汇报材料 |

这些是文章列出的产品应用示例，不代表文章已经独立验证了所有场景的执行质量。

### 三、出现的公司、产品与项目

| 名称 | 类型 | 在文章中的作用 |
| --- | --- | --- |
| Google | 科技公司 | 发布 Gemini 的计算机操作功能 |
| Gemini | AI 助手 | 承载 Computer Use 能力的核心产品 |
| Gemini for Mac | 桌面应用 | 新功能的主要使用入口 |
| OpenAI | AI 公司 | 被文章列为已经提供桌面智能体功能的竞争对手 |
| Anthropic | AI 公司 | 同样属于提前布局桌面智能体的竞争对手 |
| Meta | 科技公司 | 被列入智能体桌面功能的竞争阵营 |
| Gemini Tasks | 应用内任务功能 | 协助登录网站、购物、预约 |
| CC AI Agent | 家庭管理智能体 | 帮助协调邮件、日历、聊天与任务 |
| Google AI Plus | 付费订阅 | 首发用户可使用的订阅层级之一 |
| Google AI Pro | 付费订阅 | 首发用户可使用的订阅层级之一 |
| Google AI Ultra | 付费订阅 | 首发用户可使用的订阅层级之一 |
| TechCrunch | 科技媒体 | 原文发布媒体 |

### 四、文章提及的重要时间信息
- 周四： Google 宣布将 Computer Use 引入 Gemini macOS 桌面应用。
- 同一周： Google 宣布更加广泛地推出 Gemini Tasks 功能。
- 此前的 9 月： Google 宣布重新设计的 CC AI Agent。
- 近期： Google 开始允许早期测试者体验 CC。
- 未来： Google 尚未公布 Computer Use 面向其他地区或平台的推广时间。

注意：所提供的正文没有包含具体发布日期和年份，无法仅凭“周四”“本周”“9 月”推导出准确的日历日期，不宜在后续引用时擅自补全。

### 五、文章没有提供、但值得继续关注的数据
这篇报道是一则产品发布新闻，而不是完整的功能评测，因此有一些关键指标尚未披露：
- 执行成功率： AI 能够独立完成多步骤任务的比例。
- 操作耗时： 相比人类手动操作能节省多少时间。
- 支持范围： 哪些 Mac 原生应用能够被完整操作。
- 任务复杂度： 一次任务最多可以处理多少步骤、文件或应用。
- 错误恢复： 误删、误改文件后能否撤销或恢复。
- 安全边界： 是否对敏感操作设置强制审批，以及具体的权限机制。
- 订阅价格及限制： 不同付费套餐是否存在 Computer Use 使用次数、执行时长或其他配额差异。
- 推广计划： 中文、其他地区和 Windows 版本的具体上线时间。

这些缺失信息十分重要，因为它们将直接影响 Computer Use 在真实工作环境中的实用性。

## 金句摘录

### 1. AI 的角色从回答问题转向替用户行动
“Google on Thursday announced that it is bringing computer use to its Gemini desktop application on macOS, allowing its AI to complete tasks on users’ behalf, navigating native Mac apps, and browsing websites in the background.”

中文翻译：
Google 周四宣布，将计算机操作能力引入 macOS 版 Gemini 桌面应用，使 AI 能够代表用户完成任务，包括操作 Mac 原生应用程序以及在后台浏览网站。
值得记住： “Complete tasks on users’ behalf”（代表用户完成任务）是整篇报道最核心的表述，强调 AI 从辅助建议走向直接执行。

### 2. Google 不是这一赛道的先行者
“The tech giant is a little late to the game with this launch, as other leading AI model makers like OpenAI, Anthropic, and Meta have already been offering agentic features in their desktop applications for some time.”

中文翻译：
这家科技巨头在此次功能发布上稍显迟到，因为 OpenAI、Anthropic 和 Meta 等其他领先 AI 模型厂商，早已在各自的桌面应用中提供智能体功能一段时间了。
值得记住： 作者并没有把这次更新描述成 Google 的独家突破，而是明确指出了它在行业竞争中的追赶位置。

### 3. 智能体真正的价值在于跨应用完成复杂任务
“This allows the AI to complete multistep tasks that involve getting things done across local files, apps, and the web.”

中文翻译：
这使 AI 能够完成涉及本地文件、应用程序以及互联网的多步骤任务。
值得记住： “Multistep tasks”（多步骤任务）和 “across local files, apps, and the web”（跨本地文件、应用与网页）是理解 Computer Use 价值的两个关键概念。

### 4. AI 工作时，人仍然可以继续使用电脑
“After the user instructs the AI what they want to do, they’ll see the agent working in a live preview in their chat, while still keeping their screen and cursor free to continue working on other things.”

中文翻译：
用户告诉 AI 想要完成什么任务后，就可以在聊天界面的实时预览中看到智能体的执行过程，同时仍然能够自由使用自己的屏幕和鼠标，继续处理其他工作。
值得记住： 这段话强调了后台执行和人机并行工作的体验优势，而不是单纯的自动点击功能。

### 5. 用户仍然需要拥有对 AI 操作的控制权
“As with other AI agents offering computer use, users can pause, stop, and approve Gemini’s actions before they happen.”

中文翻译：
与其他提供计算机操作能力的 AI 智能体一样，用户可以暂停、停止 Gemini 的操作，并在操作发生之前进行审批。
值得记住： AI 自动化不仅要能执行，更要允许用户监督、干预和控制。

### 6. Google 优先解决的是日常工作中的烦琐事务
“Google suggests the feature could be useful for tedious tasks and other workflows, like filling out forms, repeating the same task over and over across a batch of files, organizing files into folders based on specific criteria, creating slideshows from files or information in online dashboards, and more.”

中文翻译：
Google 认为，这项功能适用于烦琐任务及其他工作流程，例如填写表单、对一批文件重复执行相同任务、根据特定规则将文件整理到文件夹中，以及利用文件或在线数据仪表盘的信息制作幻灯片等。
值得记住： 真正容易形成日常使用价值的 AI 场景，往往不是最令人惊叹的演示，而是那些每天都要做、却消耗大量时间的重复劳动。

## 值得记住的点 / 行动建议
以下建议根据文章披露的产品能力整理，其中具体的操作方法属于实践建议，并非 Google 在报道中给出的完整官方教程。

### 1. 优先让 AI 处理高频、重复、规则清晰的任务
不要一开始就让 Computer Use 承担非常复杂、需要大量主观判断的工作，而应该先寻找那些每天或每周都要重复执行的流程。
可以优先考虑三类任务：
- 文件整理：根据名称、日期、项目类型等条件，将文件放入相应文件夹。
- 重复输入：把已有的信息填写到结构一致的表单中。
- 内容整理：从本地文档或在线仪表盘中收集资料，为报告和幻灯片准备内容。

例如，可以尝试类似的指令：
请检查指定文件夹中的项目文件，根据文件名里的项目代号进行分类。先向我展示分类规则和预计操作结果，得到确认后再移动文件。遇到不符合规则的文件，请不要自行猜测分类，单独列出让我处理。

这类任务既契合文章描述的应用场景，也便于用户通过检查结果来评估 AI 的执行效果。

### 2. 用“目标 + 范围 + 规则 + 限制 + 验收标准”描述任务
当 AI 真正能够操作电脑时，提示词的作用就不仅是影响回答质量，还会影响实际执行结果。
建议把任务描述成五个部分：

| 组成部分 | 应该告诉 AI 什么 |
| --- | --- |
| 目标 | 最终需要完成什么 |
| 范围 | 可以操作哪些文件、文件夹、网页和应用 |
| 规则 | 如何分类、筛选、填写或处理 |
| 限制 | 哪些行为不能自动执行 |
| 验收标准 | 怎样判断任务已经正确完成 |

例如，单纯说“帮我整理文件”，包含太多不确定性。
更合适的说法是：
请整理“项目资料”文件夹中的 PDF 和 Word 文件，按照文件名中的年份建立对应子文件夹。不要删除文件，不要覆盖同名文件，不要处理其他目录。先预览整理方案，确认后再执行，最后提供移动文件的清单。

这样做能够减少 AI 对模糊指令的自行猜测，也方便在任务结束后检查结果。

### 3. 对具有风险的操作，使用人工审批作为安全边界
文章特别提到了 Gemini 的暂停、停止和操作前审批能力，因此实际使用时应充分利用这些控制功能。
建议根据操作风险进行区分：

| 风险级别 | 任务例子 | 推荐做法 |
| --- | --- | --- |
| 低 | 查看文件、整理信息、准备内容草稿 | 可以考虑让 AI 执行，再检查结果 |
| 中 | 批量移动文件、修改文档、填写重要表单 | 先备份，明确范围，并在关键步骤审核 |
| 高 | 删除重要文件、提交订单、付款、发送敏感信息 | 对关键动作要求人工确认，必要时手动完成 |

尤其需要注意，文章中的“用户可以审批”不等同于“所有危险操作一定会自动触发人工审批”。
因此，在没有明确了解产品的安全机制前，不能因为 AI 提供了审批选项，就默认所有风险已经由系统处理。

### 4. 充分利用后台执行，让人和 AI 分工协作
Computer Use 的一个重要卖点，是智能体可以在后台执行任务，不必完全占据用户当前的工作界面。
可以尝试建立一种并行工作模式：用户专注于思考、决策、沟通和内容质量；Gemini 负责按明确规则执行文件整理、资料提取等机械性工作。
例如，在准备一份季度汇报时，可以考虑这样的流程：
**1. 用户明确汇报目标、数据来源以及输出格式。**
**2. Gemini 根据允许访问的数据源整理信息，制作幻灯片草稿。**
**3. 用户在此期间继续撰写核心观点或准备会议内容。**
**4. AI 完成后，用户检查数据、表述和演示文稿质量。**
**5. 对发现的问题进行修改，最终由用户确认交付。**

这只是基于文章所述能力设计的理想工作流，具体哪些步骤能够完全自动完成，仍需实际测试。

### 5. 衡量 AI Agent 的价值，不能只看能不能运行
一个智能体即使能完成任务，也不一定真的提高效率。
例如，人类花 5 分钟就能完成的操作，如果 AI 需要执行 4 分钟、用户另外花 3 分钟核对结果，那么从总耗时看，并没有产生真正的效率收益。
因此，试用 Computer Use 时，建议重点记录四项指标：
- 任务完成率：10 次执行中有多少次真正完成。
- 总耗时：包括下达指令、执行、等待审批和检查结果的时间。
- 错误与返工：出现了多少次错误，需要多少人工修复。
- 人工参与度：有多少步骤仍然需要用户主动操作。

最值得长期交给 AI 的任务，应当是成功率较高、人工干预较少、错误可恢复，而且能明显节省时间的流程。

### 6. 不要把 Gemini Tasks、CC 和 Computer Use 混为一谈
虽然三者都属于 Google 的智能体方向，但它们在文章中承担的角色不同。

Gemini Tasks
应用内任务执行：登录网站、购物、预约等

CC AI Agent
家庭事务协调：邮件、日历、聊天与任务管理

Gemini Computer Use
桌面计算机操作：跨本地文件、Mac 应用及网页执行任务

如果要研究 Google 的 Agent 战略，应该把这三条产品线放在一起观察，但如果只是想找一款可以直接整理 Mac 文件的软件，就需要重点关注 Computer Use 的实际能力和开放范围。

### 7. 把 AI Agent 当作可监督的执行者，而不是完全自主的决策者
这篇文章隐含的一个重要使用原则，是人类仍然保有对目标、权限和最终结果的控制。
更合理的工作分工是：
人类决定做什么、为什么做、什么结果才算正确；AI 负责按约定规则执行；人类在关键节点检查和确认。
这种工作方式适合从低风险任务逐步拓展到复杂流程，而不是一上来就把重要资料、业务系统和敏感操作全部交由智能体自主处理。
随着 AI 执行能力不断增强，用户真正需要提升的技能，也可能从“如何亲自完成每一个软件操作”，逐渐转向“如何定义任务、设置边界、检查结果和处理异常”。

### 8. 持续关注三个决定产品实用性的后续变化
对于目前无法使用这项功能的用户，不必仅因为新闻发布就急于更换设备或订阅套餐。
更有价值的是继续关注：
第一，覆盖范围。 Google 什么时候支持更多国家、中文及其他操作系统？
第二，真实能力。 它能否稳定处理高频任务？是否支持用户常用的软件？复杂任务的失败率和人工干预次数有多高？
第三，使用成本。 不同订阅套餐提供什么权限、额度和限制？付费成本能否通过节省的劳动时间得到合理回报？
相比单纯关注新功能是否上线，这些信息更加接近用户实际需要做出的购买和使用决策。

## 我的点评
这篇报道最值得关注的不是 Gemini 增加了一个新功能，而是它展现出 AI 产品正在从“给人建议”转向“替人执行”的发展方向，尤其是跨应用操作和后台并行工作，有机会减少大量重复性劳动。Google 选择表单填写、文件整理和幻灯片制作等常见办公场景，说明 Computer Use 的价值并不一定来自复杂推理，而可能来自对日常操作流程的持续自动化，这一点很有现实意义。不过，TechCrunch 的文章主要依据产品发布信息展开，没有提供独立测试、任务完成率、错误率或性能对比，因此现在还不能判断 Gemini 的计算机操作能力是否已经足够成熟，也不能据此断言它优于竞争对手。另一个值得注意的问题是，AI 一旦具备真正的执行权限，错误操作的影响将比普通聊天回答更直接，因此权限控制、关键操作审批和结果核对会变得更加重要。对于普通用户而言，最务实的做法并不是立即把所有工作交给 AI，而是从规则明确、风险可控、方便验收的重复任务开始，逐步找到真正能产生效率收益的使用场景。
最终值得记住的一句话：AI Agent 的竞争，正在从“谁更会回答问题”，走向“谁能更可靠、更安全、更省事地替用户完成任务”。 这是对文章的归纳判断，而非 Google 或 TechCrunch 的直接原话。

---

## 📝 完整文字稿

Google on Thursday announced that it is bringing computer use to its Gemini desktop application on macOS, allowing its AI to complete tasks on users’ behalf, navigating native Mac apps, and browsing websites in the background.

The tech giant is a little late to the game with this launch, as other leading AI model makers like OpenAI, Anthropic, and Meta have already been offering agentic features in their desktop applications for some time. Meanwhile, Google only this week announced the broader rollout of Gemini’s “Tasks,” the in-app feature that allows the AI to work more as an agent, helping users sign into websites, make online purchases, or book appointments.

Google also only recently began admitting early testers to try its revamped “CC” AI agent, announced in September, which is designed to help families stay organized across email, calendars, chats, and tasks.

Computer use is another type of agentic offering that allows an AI agent to take actions directly on the user’s computer — in Gemini’s case, a Mac. This allows the AI to complete multistep tasks that involve getting things done across local files, apps, and the web. After the user instructs the AI what they want to do, they’ll see the agent working in a live preview in their chat, while still keeping their screen and cursor free to continue working on other things.

As with other AI agents offering computer use, users can pause, stop, and approve Gemini’s actions before they happen.

Google suggests the feature could be useful for tedious tasks and other workflows, like filling out forms, repeating the same task over and over across a batch of files, organizing files into folders based on specific criteria, creating slideshows from files or information in online dashboards, and more.

The feature is initially available in English in the U.S. and requires the Gemini app for Mac and a Google AI Plus, Pro, or Ultra subscription. The company didn’t say when it would expand to other markets or platforms.
