# 🔎 主动研究：AI Agent长期记忆与权限隔离：VPS部署、沙箱执行、技能清理的实战架构

> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；下次洞察会读到它。生成时间：2026-06-22 13:34

## 调研主题：AI Agent长期记忆与权限隔离：VPS部署、沙箱执行、技能清理的实战架构

### 来源1：...mini卖爆了!创始人爆料:一人开发、100% AI 写代码,全开源却留...
http://www.baidu.com/link?url=GrcysjhGQWBtE7NiJMOIc2WvyjbEePnMIrS8WTNhwgY2lUS8Y2AZAFgcsYuyRFjCLGZbNXghhWCvElIv-x7DUK
硅谷刷屏的ClawdBot，让Mac mini卖爆了！创始人爆料：一人开发、100% AI 写代码，全开源却留 0.00001% 给全网来 hack_腾讯新闻 

 硅谷刷屏的ClawdBot，让Mac mini卖爆了！创始人爆料：一人开发、100% AI 写代码，全开源却留 0.00001% 给全网来 hack

 InfoQ
 2026-01-26 15:29 发布于 北京 InfoQ官方账号 

 问AI  ·  保留soul文件如何测试AI安全极限？ 

 整理 | 褚杏娟 这两天，个人 AI 助手 ClawdBot 席卷硅谷，国内外社交平台上全是关于它的讨论。 
 在试用后，网友们纷纷给出了很高的评价。“它是迄今为止最伟大的 AI 应用，相当于你 24 小时全天候专属 AI 员工。”Creator Buddy 创始人兼 CEO Alex Finn 盛赞道，“这就是他们 (Anthropic) 希望 Claude Cowork 呈现的样子。” 
 当前，ClawdBot 项目已经开源，现在已经斩获了 20.8k stars： https://github.com/clawdbot/clawdbot 
 Alex 展示了给他的 Clawdbot 发信息，让它帮其预订下周六在一家餐厅的座位。当 OpenTable 预订失败时，Clawdbot 利用 ElevenLabs 的技术致电餐厅并完成了预订。 
 但 ClawdBot 真正让技术圈兴奋的，并不只是“能干活” ，而是其协作方式极其激进：不会写代码的人，也能直接提 PR。原因很简单：它几乎是 100% 用 AI 写出来的，PR 在这里更像是“我遇到了这个问题”，而不是“我写了一段多漂亮的代码”。 
 更有意思的是，这个看似“全开源”的项目，偏偏故意留了一点不开源。创始人 Peter Steinberger 保留了一个名为“soul”的文件只占项目的 0.00001%。他说得很直白：这既是他的"秘密资产"，也是一个刻意留下来的安全靶子。大家真的在试着 hack 它，他就等着看模型到底守不守得住。到目前为止，“soul”还没被偷出来。 
 作为忠实粉丝，Alex 表示这是自 Claude Code 发布以来，自己第一次连续两天没有用它。但是他的 ClawdBot Henry 已经连续 48 小时不停地 Vibe Coding 。“我这辈子都没写过这么多代码。Vibe Coding 已死， Vibe Orchestration 已来。” 
 现在，Alex 想要退掉 Mac Mini，换一台价值 1 万美元的 Mac Studio。“我的 ClawdBot Henry 将控制一台人工智能超级计算机。Henry 将使用 Opus 作为大脑，并使用多个本地模型作为员工集群。” 
 Clawbot 并不是传统意义上只能回答问题的聊天机器人，它本质上是一个持续运行、可以执行任务的个人 AI 智能体。 
 你可以把它安装在自己的设备上，如 Mac、Windows、Linux，它可以长期在线，不停地接收指令、处理任务、记住你的偏好和历史对话，随着时间积累变得更懂你、更有“记忆”。总的来说，Clawbot 最令人震撼的地方有三点： 
 第一， 它几乎可以完全控制你的电脑。  它没有传统意义上的“护栏”，不局限在某几个功能里，而是可以像一个真正坐在电脑前的人一样，操作你电脑上的一切。 
 第二， 它拥有近乎无限的长期记忆。 Clawbot 内置了一套非常复杂的记忆系统。说过的话、做过的事，都会不断被记录下来。每次对话结束后，它都会自动总结聊过的内容，并把关键信息提取出来，存进长期记忆中。 
 第三， 它完全通过聊天应用来交互。  你平时用哪些聊天工具，Clawbot 就能在哪儿跟你对话，这意味着，只要打开一个聊天软件，就可以通过一条消息把任务交给 Clawbot 去做。现在 Clawbot 支持 WhatsApp、Telegram、Slack、Discord、Google Chat、Signal、iMessage、Microsoft Teams、WebChat 等，还有 BlueBubbles、Matrix、Zalo 以及 Zalo Personal。 
 不过，如此放开的权限让其几乎没有护栏，这带来很大的安全隐患，现在 GitHub 上有 500 多个安全的问题，这也让部分网友望而却步。对此，很多使用过的用户几乎都表示，不建议一开始就把 Clawbot 装在主力电脑上。“在你还不熟悉它之前，把它放在一个独立环境里是最安全的选择。” 
 不过大家没有想到，这个 AI 员工首先带火的竟然是 Mac Mini。 
 很多人为了运行 Clawdbot 会专门买一台电脑，而大部分选择了 Mac Mini，原因是它便宜、兼容好、功率低、安静、占地小。谷歌 DeepMind 产品经理 Logan Kilpatrick 都忍不住订了台 Mac Mini。 
 更有网友晒出自己一口气买了 40 台 Mac mini 来运行 Clawdbot。 
 但也有网友称可以用一台免费的服务器运行着完全一样的程序，Alex 也称没必要花 600 美元买 Mac mini，有其他便宜得多的方式来运行 Clawbot。买 Mac mini 更多是个人偏好，而不是技术上的必要条件。你完全可以不买任何硬件，只需要一个 VPS。 
 随着项目的火爆，其背后的开发者 Peter Steinberger 也开始走到前台。Peter 在“Open Source Friday”上分享了他一手打造 ClawdBot 的经过，从创建、创始到维护，全由他独自完成。有意思的是，此前甚至有传言称，Peter 可能是一个 bot、Agent，甚至本身就是 AI。而 Peter 的出现也让项目成员和关注者们确认了他是个“真人”。 
 Peter 一度已经退休了，后来又从退休状态里出来开始折腾 AI。从外表来看，Peter 年轻有活力，完全不像已到退休年龄、可领取养老金的人。 
 Peter 的职业生涯也颇具亮点，他曾独立运营一家 B2B 公司长达十三年。这家公司打造出了当时全球领先的 PDF 框架，团队规模最高发展到约七十人。在公司发展步入稳定阶段后，Peter 收到了一份极具吸引力、令人无法拒绝的收购邀约，这也为他这段创业历程画上了一个圆满的句号。 
 不过，Peter 口中的“退休”更像是一种玩笑式的表述。在十三年的创业生涯中，他几乎倾注了所有精力，就连周末也大多用于工作，长期的高强度投入最终让他陷入了严重的 burnout（心力交瘁）状态。之后，Peter 花了不少时间调整身心，弥补生活中的遗憾，体验了许多有趣的事情。但他知道自己是那种热爱“创造”和“构建”的人，迟早还会回来。 
 直到去年年初，Peter 的创作想法再度燃起。正好，那时候 AI 从“这玩意儿不太行”，突然变成了“等等，这有点意思”。从那以后，Peter 基本上就把身边无数人一起拉进了 AI 的坑里。 
 下面是 Peter 在节目上的对话，除了分享经历，他也谈到了大家的各种意想不到的应用和最关心的安全问题，安全正是他当前最优先的工作。我们在不改变原意基础上进行了删减和翻译，以飨读者。 
 1 “本来想等大厂做的” 主持人：这个项目现在太火了，GitHub 星数涨得飞快。你似乎正好击中了一个大家憋了很久的需求：一个人，也能把很多事情搞定。我甚至觉得你在无形中拉升了 Apple 的股价，大家都跑去买 Mac mini 来自己跑实例了。能不能讲讲，这个想法最初是怎么冒出来的？ Peter：  我刚回来的时候，其实特别想要一个“生活助理”，四月份就已经在想这个事了，也试过一些想法，但当时模型还不够好。我后来就把这个念头放下了，因为我觉得这种东西，肯定是各大厂都会做的，那我做还有什么意义呢？于是我又去做了很多别的项目。直到十一月，我突然意识到，居然还没有人真的把这件事做出来。我心想，难道还真是什么都得我自己来？ 
 也不知道哪根弦被拨动了，那个月我用一个小时拼了点非常糙的代码，用 WhatsApp 发消息，转到 Claude Code，再把结果发回来。本质上就是把几样东西“粘”在一起，说实话并不难，但效果还挺好。 
 后来我意识到，我还需要图片输入。我自己在提示时经常用图片，因为它能给 Agent 很多上下文，而且非常快。这个

### 来源2：深入理解OpenClaw技术架构与实现原理(下)_腾讯新闻
http://www.baidu.com/link?url=GrcysjhGQWBtE7NiJMOIc2WvyjbEePnMIrS8WTNhwgY2lUS8Y2AZAFgcsYuyRFjCZ7QOFeXlPhJmbEHu1bpDfq
深入理解OpenClaw技术架构与实现原理（下）_腾讯新闻 

 深入理解OpenClaw技术架构与实现原理（下）

 阿里技术
 2026-03-26 08:32 发布于 浙江 阿里技术官方账号 

 阿里妹导读 

 本文是《 深入理解OpenClaw技术架构与实现原理（上） 》的续篇，主要讲述从沙箱隔离到企业级智能体演进。 
 三、各系统模块讲解 
 3.8 SandBox 沙箱系统 
 Sandbox 是 OpenClaw 的 Docker 隔离层，用于在容器中执行 AI Agent 的工具操作，而非直接在主机上运行。 
 3.8.1 核心目的 
 限制工具执行（exec、read、write、edit 等）的安全边界 
 减少模型执行意外操作时的" 爆炸半径 " 
 提供可配置的隔离级别 
 3.8.2 关键文件结构 

 src/agents/sandbox/ ├── types.ts           # 核心类型定义 ├── config.ts          # 配置合并逻辑 ├── context.ts         # 入口点 - 解析沙箱上下文 ├── docker.ts          # Docker 容器管理 ├── browser.ts         # 隔离浏览器容器 ├── tool-policy.ts     # 工具允许/拒绝策略 ├── validate-sandbox-security.ts   # 安全验证 ├── fs-bridge.ts       # 文件系统操作桥接 └── prune.ts           # 容器自动清理 3.8.3 沙箱模式 
 模式 行为 
 "off" 不隔离，所有工具直接在主机运行 
 "non-main" 仅隔离非主会话（默认） 
 "all" 所有会话都隔离 

 3.8.4 容器作用域 
 作用域 容器数量 
 "session" 每个会话一个容器（默认） 
 "agent" 每个 Agent 一个容器 
 "shared" 所有会话共享一个容器 

 3.8.5 工作区访问权限 
 权限 挂载行为 
 "none" 完全隔离的工作区  ~/.openclaw/sandboxes 
 "ro" 只读挂载 Agent 工作区到  /agent 
 "rw" 读写挂载到  /workspace 

 3.8.6 安全限制 
 禁止的绑定挂载： 
 系统路径： /etc 、 /proc 、 /sys 、 /dev 、 /root 、 /boot 、 /run 
 Docker socket： /var/run/docker.sock 
 根文件系统： / 
 禁止的网络模式： 
 host （绕过网络隔离） 
 con taine r:<id> 
 默认安全配置： 
 只读根文件系统 ( readOnlyRoot: true ) 
 无网络 ( network: "none" ) 
 丢弃所有能力 ( capDrop: ["ALL"] ) 
 3.8.7 工具策略层级 
 隔离时工具过滤顺序： 
 全局工具策略 
 Agent 特定策略 
 Sandbox 工具策略 （只能进一步限制） 
 子 Agent 策略 
 默认允许的工具： exec 、 read 、 write 、 edit 、 apply_patch 、 image  等 默认禁止的工具： browser 、 canvas 、 nodes 、 cron 、 gateway  及所有消息通道 
 3.8.8 配置示例 

 {   "agents": {     "defaults": {       "sandbox": {         "mode":  "non-main" ,          "scope" :  "session" ,          "workspaceAccess" :  "none" ,          "docker" : {           " image ":  "openclaw-sandbox:bookworm-slim" ,            "network" :  "none" ,            "memory" :  "512m" ,            "cpus" :  1         },         "prune": {           "idleHours":  24 ,            "maxAgeDays" :  7         }       }     }   } } 3.8.9 CLI 命令 
 openclaw sandbox list  - 列出沙箱容器 
 openclaw sandbox recreate  - 强制重建容器 
 openclaw sandbox explain  - 调试当前配置 
 3.9 记忆管理 
 3.9.1 核心设计理念 
 OpenClaw 的记忆系统采用 " 文件

## 资料来源
- [...mini卖爆了!创始人爆料:一人开发、100% AI 写代码,全开源却留...](http://www.baidu.com/link?url=GrcysjhGQWBtE7NiJMOIc2WvyjbEePnMIrS8WTNhwgY2lUS8Y2AZAFgcsYuyRFjCLGZbNXghhWCvElIv-x7DUK)
- [深入理解OpenClaw技术架构与实现原理(下)_腾讯新闻](http://www.baidu.com/link?url=GrcysjhGQWBtE7NiJMOIc2WvyjbEePnMIrS8WTNhwgY2lUS8Y2AZAFgcsYuyRFjCZ7QOFeXlPhJmbEHu1bpDfq)
- [AI Agent 保姆级教程:从原理到实战_ai agent教程-CSDN博客](http://www.baidu.com/link?url=WUbV65l3-Pwh2e6tNUNkqwOgG_YIaj5hJyQnaDYziZ2bra6q9OdIbOkMG3WERdZ29M7qUz_zrPPubctSSUPoAmdG7ByAMcH0LCIvzQSGjc_)
- [腾讯技术工程官方号 - 个人中心 - 腾讯云开发者社区-腾讯云](http://www.baidu.com/link?url=WUbV65l3-Pwh2e6tNUNkq8GbhuRSSYv_-dq84iFXo0XR-SuZH46dWqGBPurxejCzYF_ZCrc26XfZV_OoP2uR_q)
