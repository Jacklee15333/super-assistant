# 🔎 主动研究：Claude Code Skills MCP 知识库自动化

> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；下次洞察会读到它。生成时间：2026-07-03 06:05

## 调研主题：Claude Code Skills MCP 知识库自动化

### 来源1：一篇搞懂 Claude Code+MCP+Skills,看完直接上手|调用|插件|代码|...
http://www.baidu.com/link?url=twjYbW02zOmKphhoiZsoQUtgqptIyHb1XUGLlS5RA8bNzH8d0oyFQcOtaeDz1oD_rA8mF17R-WuDSM7GMs_Adq
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

### 来源2：MCP之后,Claude为何还要推出Skills?揭秘背后逻辑!_claude skills-CSDN...
http://www.baidu.com/link?url=qVTcqEv1YLTr4wLj6kvihNDZnauxg-Z-Ok3dtGkAnB330CPGTRTgj25wbQRzmPbpcq7b8fa7CwwOwtZvw2Vtg1WPmPwyuN-w58Hkf4cKU3W
MCP之后，Claude为何还要推出Skills？揭秘背后逻辑！_claude skills-CSDN博客 

 MCP之后，Claude为何还要推出Skills？揭秘背后逻辑！

 最新推荐文章于 2026-06-22 15:46:16 发布

 原创 

 最新推荐文章于 2026-06-22 15:46:16 发布 
 · 
 2.1k 阅读 

 · 

 19

 · 

 32

 · 

 本内容遵循CC 4.0 BY-SA版权协议 

 版权声明：本文为博主原创文章，遵循 CC 4.0 BY-SA 版权协议，转载请附上原文出处链接和本声明。

 GEO检测 

 · 

 收录于 

 当前文章被以下社区和专栏收录：

 该文章已生成可运行项目， 预览并下载项目源码 

 AI 时代程序员必备技能

 Codex、Claude Code、Cursor、Hermes Agent、OpenClaw等工程化实战专栏 ，讲透 AI 如何接管脏活累活

 一键订阅 

 这两天又被 Caude 推出的 Skills 刷屏了！

 看起来很强大，但跟 MCP 有啥区别？出这个是做啥的？

 Skills 是什么？

 要想知道区别，先知道是什么。

 根据官方介绍，Claude 的 Skills 是一种模块化的能力包，它以文件夹的形式组织，

 每个 Skill 包含：

 •  一个   SKILL.md   文件 ——描述该技能的详细用途和操作流程

 •  脚本与模板 ——自动化执行复杂任务，比如处理 Excel、生成 PowerPoint，或遵循品牌规范等。

 •  资源文件 ——辅助技能运行的必要材料（如代码片段、流程文档等）。

 Claude 只会在需要时，动态加载对应的 Skills。

 类似于给 AI 助手装上专业“技能包”，以便完成一些特定的复杂工作。

 有什么用？

 Skills 的核心特点：

 •  专业化任务执行：  Skills 让Claude 能够更准确、高效地执行特定领域的工作任务，比如办公文档的制作（Excel、PPT、PDF等）、品牌内容一致性保证、客户反馈分析等。

 •  可组合性：  多个 Skills 可以堆叠使用，Claude 会自动识别任务需要哪些 Skills 并协调使用它们，像搭积木一样灵活。

 •  可移植性：  一套 Skills 只需要构建一次，就可以在 Claude 各大平台（Claude 应用、Claude Code、API等）中通用。

 •  高效且强大：  只在需要时加载所需内容，也允许包含可执行代码，使得某些任务表现比单纯生成文字更可靠。

 举例：

 • 比如你有一个 PDF 制作 Skill，里面包含了制作专业PDF的指令和模板，Claude 在处理相关任务时自动调用它。

 • 又如多个 Skills 叠加使用：品牌规范 Skill 保证文档风格，报告生成 Skill 处理内容结构，数据分析 Skill 做数据处理，协同完成复杂工作。

 Skills 让用户不需要每次都从零写指令或程序， 
可以标准化、自动化复杂工作流程，提高效率，且便于分享和维护。

 有什么好处？

 根据官方描述，

 • 使用 Claude Skills 的任务效率提升近 40%，错误率下降超过 35%。

 • Skills 支持高效率的 token 使用，如 Sonnet 3.7 能在工具调用场景下节省14%到70%的输出 token。

 做到这两点，主要原因是： 

 • 技能包机制把常用任务封装成可复用模块，AI自动识别任务后不用重新推理、编写脚本，直接用“现成工具”处理。

 • 少了多轮思考与澄清。Skill 调用只需一句话，AI不用反复理解、解释或生成代码，“一键式产出”极大减少中间环节token消耗。

 传统方式（不使用 Skills），你可能要多轮澄清、脚本生成与纠错，每次交互都计入token，尤其复杂任务消耗更大。

 Skills 与 MCP 的区别

 用人类可以理解的话来说：

 •  Skills 主要聚焦于工具处理。  例如处理文件、设计、写文章。

 •  MCP 主要起到连接作用。  适合深度集成外部系统，自定义上传、下载、推送等流程。

 Skills 与 MCP 并不是竞争或替代的关系，而是结合关系。

 对于普通用户、日常工作，大部分时候只需要 Skills 就足够；

 对于复杂的企业场景、跨平台/自动分发等任务，使用 Skills + MCP 可以实现更加稳定和高效的输出。

 更直观的对比

 场景

 Claude Skills

 MCP

 提取 PDF 表格并转成 Excel

 安装 Skill 后一句话搞定，自动转换

 需开发 Skill 或直接用默认 Skill

 处理网盘里的20个 PDF

 需手动批量上传，Skill 单个处理

 可自动批量调用网盘接

## 资料来源
- [一篇搞懂 Claude Code+MCP+Skills,看完直接上手|调用|插件|代码|...](http://www.baidu.com/link?url=twjYbW02zOmKphhoiZsoQUtgqptIyHb1XUGLlS5RA8bNzH8d0oyFQcOtaeDz1oD_rA8mF17R-WuDSM7GMs_Adq)
- [MCP之后,Claude为何还要推出Skills?揭秘背后逻辑!_claude skills-CSDN...](http://www.baidu.com/link?url=qVTcqEv1YLTr4wLj6kvihNDZnauxg-Z-Ok3dtGkAnB330CPGTRTgj25wbQRzmPbpcq7b8fa7CwwOwtZvw2Vtg1WPmPwyuN-w58Hkf4cKU3W)
- [別再裸用 Claude Code 了!32 個親測 Skills + 7 個 MCP 完整指南 - Jason's Notes](https://shihyu.github.io/jason_note/ai_agent/Claude-Code-Skills%E8%88%87MCP%E5%AE%8C%E6%95%B4%E6%8C%87%E5%8D%97.html)
- [Claude Code 进阶：MCP、Skills 与自用习惯 | 老Z的博客](https://www.zhaofutao.cn/posts/claude-code-advanced-usage-guide)
