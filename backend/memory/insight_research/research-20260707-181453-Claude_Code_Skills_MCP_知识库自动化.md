# 🔎 主动研究：Claude Code Skills MCP 知识库自动化 最佳实践

> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；下次洞察会读到它。生成时间：2026-07-07 18:14

## 调研主题：Claude Code Skills MCP 知识库自动化 最佳实践

### 来源1：一篇搞懂 Claude Code+MCP+Skills,看完直接上手|调用|插件|代码|编辑...
http://www.baidu.com/link?url=QfnaIJxY5WWUjfyVlRJsBVpEgLhV8LEKNDG70XURVh9IB-2OGDw9gWD2cWwT5cK_Gi5wmtKJNzpBPLGc8IGrJa
一篇搞懂 Claude Code+MCP+Skills，看完直接上手|调用|插件|代码|编辑器|json|命令提示符_网易订阅 

 网易首页 

 应用

 网易新闻 

 网易公开课 

 网易红彩 

 网易严选 

 邮箱大师 

 网易云课堂 

 快速导航

 新闻 

 国内 

 国际 

 王三三 

 体育 

 NBA 

 CBA 

 综合 

 中超 

 国际足球 

 英超 

 西甲 

 意甲 

 娱乐 

 明星 

 电影 

 电视 

 音乐 

 封面故事 

 财经 

 股票 

 原创 

 智库 

 汽车 

 购车 

 车型库 

 科技 

 网易智能 

 原创 

 IT 

 互联网 

 通信 

 时尚 

 艺术 

 旅游 

 手机 
 / 
 数码 

 惊奇科技 

 易评机 

 家电 

 房产 
 / 
 家居 

 北京房产 

 上海房产 

 广州房产 

 楼盘库 

 设计师库 

 案例库 

 教育 

 留学 

 高考 

 查看网易地图 

 登录 

 注册免费邮箱

 注册VIP邮箱（特权邮箱，付费） 

 免费下载网易官方手机邮箱应用 

 安全退出 

 移动端 

 网易公开课 

 TED 

 中国大学视频公开课 

 国际名校公开课 

 赏课·纪录片 

 付费精品课程 

 北京大学公开课 

 英语课程学习 

 网易严选 

 新人特价 

 9.9专区 

 新品热卖 

 人气好物 

 居家生活 

 服饰鞋包 

 母婴亲子 

 美食酒水 

 支付 

 一卡通充值 

 一卡通购买 

 我的网易支付 

 网易跨境支付 

 邮箱 

 免费邮箱 

 VIP邮箱 

 企业邮箱 

 免费注册 

 客户端下载 

 网易首页 > 网易号 > 正文
 申请入驻 

 一篇搞懂 Claude Code+MCP+Skills，看完直接上手

 2026-03-18 08:09:13　来源: 新钛云服 
 上海

   举报 

 0 

 分享至 

 用微信扫码二维码

 分享至好友和朋友圈

 新钛云服已累计为您分享 889 篇技术干货

 本文脉络 
 新手从零上手Claude Code的最简流程。
 安装Node.js，完成Claude Code的安装与配置，解决地区限制问题。
 安装CC Switch，配置国内外模型，实现模型灵活切换。
 安装常用MCP工具（如chrome-devtools、Figma），拓展AI外部操作能力。
 下载或构建高频任务的Skills，实现同类任务的标准化复用。
 0 1 
 核心概念解析 
 Claude Code（简称CC）： 
 CC是由Anthropic开发的命令行式AI编程助手。相比那些嵌入在编辑器里的工具，它更能控制上下文，任务执行也更连贯。它支持切换不同的模型和调用外部工具，适合用于复杂的项目开发、代码重构和深度调试。
 MCP（Model Context Protocol）： 
 MCP是Anthropic在2024年11月推出的一个协议，可以让AI访问外部系统，比如浏览器、数据库、代码仓库和设计工具等。这样，AI就不再局限于处理本地内容，可以与更多外部工具无缝对接。
 Skills： 
 Skills是一种将特定任务的操作流程、规范、脚本和参考资料打包成结构化单元的方法。这样，同类任务就可以标准化并高效复用，减少重复沟通和操作的成本。
 0 2 
 Claude Code安装与配置 
 一、使用官方脚本安装 
 官方下载地址：
 https://code.claude.com/docs/en/quickstart#native-install-recommended
 claude --version 
 二、使用 npm 安装 
 claude --version 
 三、常见问题 
 如果遇到遇到地区不支持的错误信息。找到 .claude.json 文件
 MAC: /Users/用户名/.claude.json Windows：C:\Users\用户名\.claude.json 
 在配置文件中增加一个参数： "hasCompletedOnboarding": true

 重新启动，claude选择，信任文件

 完成使用

 0 3 
 模型管理工具：CC Switch安装与配置 
 为了优化使用成本并实现不同模型之间的灵活切换，我们建议安装模型管理工具CC Switch。该工具能够对国内外主流的大规模模型进行统一管理，并且还具备对Skills、MCP以及Prompt进行集中管理的功能。这样不仅提高了工作效率，也增强了系统配置的灵活性与可操作性。
 一、安装步骤 
 CC Switch下载地址：https://github.com/farion1231/cc-switch/releases

 二、模型配置建议 
 根据任务复杂度选择合适的模型，兼顾效率与成本：

 国内模型：推荐GLM-4.7、Kimi-K2.5

 国外模型：推荐Claude 4.6、GPT 5.2

 选择模型供应商

 前往官网获取 API key

 以智谱为例子：
 登录成功后，去往个人中心。

 创建API key。复制填写到CC Switch中。

 0 4 
 Claude Code指令与使用技巧 
 一、常见启动指令 
 查看Claude Code版本号：claude --version

 更新到最新版本：claude update

 直接启动命令行交互模式：claude

 带初始问题启动Claude Code：claude "今天星期几？"

 一次性执行并退出，单次命令模式，直接执行指令：claude -p "今天星期几？"

 管道输入：cat 123.py | claude -p "分析这段代码"

 启动进入会话历史：claude -r

 启动进入最近的会话：claude -c

 权限绿通模式（跳过权限检查）：claude --dangerously-skip-permissions

 二、常见内置斜杠命令 
 基础操作命令 
 命令 
 描述 
 /help
 查看所有可用命令及说明
 /cost
 查看token使用情况
 /exit
 退出当前交互式会话
 /clear
 清除当前对话历史

 会话管理命令 
 命令 
 描述 
 rename
 给当前会话起名字
 /resume [session]
 恢复历史会话（按名称/ID）
 /export [filename]
 导出对话到文件/剪贴板
 /rewind
 打开回溯菜单，恢复之前状态
 /checkpoints
 列出当前会话所有检查点 ID
 工具配置命令 
 命令 
 描述 
 /model
 切换 AI 模型（sonnet/opus 等）
 /theme
 更改终端颜色主题
 /vim
 启用 Vim 编辑模式
 实用功能命令 
 命令 
 描述 
 /review
 请求代码审查
 /rewind
 退回对话/代码修改
 /cost
 查看令牌使用统计
 自定义命令类型 
 命令 
 描述 
 项目命令
 .claude/commands/
 个人命令
 ~/.claude/commands/
 插件命令
 插件的 commands/ 目录
 MCP命令
 由MCP服务器提供
 三、键盘快捷键 
 通用控制 
 快捷键 
 描述 
 Ctrl+C
 取消当前输入或生成
 Ctrl+D
 退出Claude Code 会话
 Ctrl+L
 清除终端屏幕
 上/下箭头
 导航命令历史
 Esc + Esc 
 编辑上一条消息
 会话控制 
 快捷键 
 描述 
 Escape
 停止当前响应（非 Ctrl+C）
 Esc Esc（双击）
 打开回溯菜单，恢复历史状态
 Ctrl+R
 搜索历史命令
 浏览输入历史
 Tab
 切换「深度思考模式」（扩展推理）
 Ctrl+O
 切换详细输出（显示工具调用/思考过程）
 Ctrl+G
 打开外部编辑器输入多行内容
 0 5 
 MCP工具的安装与应用 
 一、MCP核心价值 
 MCP的主要功能就是消除AI与外部系统之间的障碍，让

### 来源2：刚刚,Anthropic 发布了 Claude Skills 最佳实践全解_the complete guide...
http://www.baidu.com/link?url=wb9xCqAPN47HXtaUy0kJpJ0dqWbrr4pXOiUTkzRVrGhOavLCNXM3ZENDFJJYwI57W7FRPbdF4KDWKpR-IcCQLja-pXaw68IIgrsNAsDI5mi
刚刚，Anthropic 发布了 Claude Skills 最佳实践全解_the complete guide to building skills for claude-CSDN博客 

 刚刚，Anthropic 发布了 Claude Skills 最佳实践全解

 最新推荐文章于 2026-06-22 11:32:18 发布

 原创 

 最新推荐文章于 2026-06-22 11:32:18 发布 
 · 
 956 阅读 

 · 

 11

 · 

 22

 · 

 本内容遵循CC 4.0 BY-SA版权协议 

 版权声明：本文为博主原创文章，遵循 CC 4.0 BY-SA 版权协议，转载请附上原文出处链接和本声明。

 GEO检测 

 · 

 收录于 

 当前文章被以下社区和专栏收录：

 AI 时代程序员必备技能

 Codex、Claude Code、Cursor、Hermes Agent、OpenClaw等工程化实战专栏 ，讲透 AI 如何接管脏活累活

 一键订阅 

 摘要：刚刚，Anthropic 发布了一份重磅技术文档：《构建 Claude Skills 终极指南》（The Complete Guide to Building Skills for Claude）。这份 33 页的文档不仅详细定义了 “Agent Skills” 的标准格式，更重要的是，它标志着我们在开发 AI 应用时，正在从单纯的 Prompt 工程向标准化的Agent 工程转变。

 什么是 Skills？它和我们要用的 MCP（Model Context Protocol）有什么关系？如何写出一个高质量的 Skills？本文为你深度拆解。

 01 什么是 Agent Skill？

 它是“可移植的智慧”。

 你是否遇到过这种情况：为了让 Claude 完成一个特定任务（比如“按照公司规范写代码”或“分析财报”），你需要每次都写一大段 Prompt，或者把这些规则硬编码在系统提示词里？

 Skills 解决了这个问题。

 最近两年，大家都可以看到AI的发展有多快，我国超10亿参数的大模型，在短短一年之内，已经超过了100个，现在还在不断的发掘中，时代在瞬息万变，我们又为何不给自己多一个选择，多一个出路，多一个可能呢？

 与其在传统行业里停滞不前，不如尝试一下新兴行业，而AI大模型恰恰是这两年的大风口，整体AI领域2025年预计缺口1000万人，其中算法、工程应用类人才需求最为紧迫！

 学习AI大模型是一项系统工程，需要时间和持续的努力。但随着技术的发展和在线资源的丰富，零基础的小白也有很好的机会逐步学习和掌握。【点击蓝字获取】 

 【2025最新】AI大模型全套学习籽料（可白嫖）：LLM面试题+AI大模型学习路线+大模型PDF书籍+640套AI大模型报告等等，从入门到进阶再到精通，超全面存下吧！ 

 Anthropic 定义的 Skills 是一个模块化的能力包。它不仅仅是一段 Prompt，而是一套包含指令、元数据和示例的标准文件结构。它让 Claude 能够“学会”一个特定的工作流，并且这个能力可以在不同的项目、甚至不同的 Agent 之间复用。

 一个标准的 Skill 结构非常简洁： my-skill-folder/ ├── SKILL.md # 核心：包含指令和元数据 ├── scripts/ # 可选：辅助脚本 └── templates/ # 可选：输出模板 其中，SKILL.md 是灵魂。它通过 YAML Frontmatter 定义元数据（我是谁，我什么时候被调用），通过 Markdown 正文定义具体的执行步骤。 02 核心最佳实践：官方避坑指南 在阅读了整份指南后，我总结了以下 4 条含金量最高的“反直觉”最佳实践：

 做“微服务”，不要做“单体应用” ❌错误做法：创建一个名为 general-helper 的巨大 Skill，试图包含代码审查、文档编写、邮件回复等所有功能。 ✅最佳实践：Micro-skills（微技能）。将大任务拆解为小而专的 Skills，例如 react-component-generator（React 组件生成器）或 pr-reviewer（代码合并审查器）。 理由：Claude 的上下文窗口虽然大，但并非无限。加载无关的 Skills 上下文会通过“噪声”降低模型智商。专才比全才更可靠。
 命名即路由（Naming is Routing） Claude 是根据 Skills 的 name 和 description 决定是否调用它的。 拒绝模糊：不要使用 utils, tools, helper 这种名字。 Bad: “Helps with coding.”

 精确描述：描述中必须包含 WHAT（做什么）和 WHEN（什么时候用）。 Good: “Generates React

## 资料来源
- [一篇搞懂 Claude Code+MCP+Skills,看完直接上手|调用|插件|代码|编辑...](http://www.baidu.com/link?url=QfnaIJxY5WWUjfyVlRJsBVpEgLhV8LEKNDG70XURVh9IB-2OGDw9gWD2cWwT5cK_Gi5wmtKJNzpBPLGc8IGrJa)
- [刚刚,Anthropic 发布了 Claude Skills 最佳实践全解_the complete guide...](http://www.baidu.com/link?url=wb9xCqAPN47HXtaUy0kJpJ0dqWbrr4pXOiUTkzRVrGhOavLCNXM3ZENDFJJYwI57W7FRPbdF4KDWKpR-IcCQLja-pXaw68IIgrsNAsDI5mi)
- [Claude Code 进阶：MCP、Skills 与自用习惯 | 老Z的博客](https://www.zhaofutao.cn/posts/claude-code-advanced-usage-guide)
- [別再裸用 Claude Code 了!32 個親測 Skills + 7 個 MCP 完整指南 - Jason's Notes](https://shihyu.github.io/jason_note/ai_agent/Claude-Code-Skills%E8%88%87MCP%E5%AE%8C%E6%95%B4%E6%8C%87%E5%8D%97.html)
