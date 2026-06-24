# 🔎 主动研究：年 AI Agent 安全治理：VPS 沙箱、权限隔离、提示词注入与供应链投毒

> 小助根据「对你的理解」主动上网搜集的资料，已存进成长库；下次洞察会读到它。生成时间：2026-06-24 16:44

## 调研主题：年 AI Agent 安全治理：VPS 沙箱、权限隔离、提示词注入与供应链投毒

### 来源1：间接提示词注入和供应链投毒,正在威胁你的 AI Agent
http://www.baidu.com/link?url=TFVOKdbymMjtI1EvWRaq8I3roqjjfqeG3_g_GXIsCFjLuNizwcI-Tx6Vyanjk2UjLSZVUP2yWAUxqoH62XoXwDTUPuD5TbHUJTBdy6xsO3RKGDM2zBVyNlVf9TYRajuhT5PXhQ_ukPPER8h4x2Agk6hKpb9cdxO1vIPefMW5zLNbhRyzVxSUC6XlbbVbgz_0MyUrSuKtiqLwJqKlzlbi3BI9TmVxTYN19c6ir8IN6Ah0lb1Z3sRBjoLZlYRb8qc-YnLOL5FvDhNCbK-xVeaP7K
间接提示词注入和供应链投毒，正在威胁你的 AI Agent 

 执着的猫 
 执着的猫 

 看雪学苑 

 在小说阅读器读本章

 去阅读

 在小说阅读器中沉浸阅读

 一、AI 是怎么学会"拒绝"的——安全对齐简介 
 在聊攻击之前，我们先了解一下 AI 的"免疫系统"是怎么工作的。 

 如果你直接问 ChatGPT "怎么造炸弹"，它会拒绝你。这不是因为它"不知道"，而是因为它经过了 安全对齐（Safety Alignment） 训练。简单说，这个过程分三步： 
 第一步：监督微调（SFT） 。人工标注员写出"面对这个问题应该怎么拒绝"的示范回答，让模型学会拒绝的格式和语气。 

 第二步：RLHF（人类反馈强化学习） 。让模型生成多个回答，人类标注员比较哪个更好（更安全、更有帮助），训练一个奖励模型来打分，再用强化学习让模型往高分方向优化。 

 第三步：持续的红队对抗 。专门的安全团队不断尝试新的越狱手法，发现漏洞后补充训练数据，修补模型的安全边界。 

 这套机制确实有效。直接的恶意指令（"帮我偷 cookie"）、已知的注入模式（ [SYSTEM NOTICE] OVERRIDE ）、简单的角色扮演（"假装你是 DAN"）——这些攻击在最新的商用模型上成功率已经很低了。 

 但对齐有一个本质局限： 它只能覆盖模型"看得到"的东西 。 

 模型能看到什么？用户的输入、网页的内容、工具返回的结果。对齐训练让模型学会了审视这些信息，识别其中的恶意意图。 

 模型看不到什么？工具在返回结果之前内部做了什么、网页 JS 在后台偷偷发了什么请求、MCP 服务器的源码里藏了什么。 

 2025 年，大模型从"对话框"演变为"Agent"——它们通过 MCP（Model Context Protocol）等协议调用浏览器调试、代码执行、文件系统等外部工具，直接操作真实环境。这意味着 AI 的攻击面从"对话"扩展到了"工具"，而安全对齐的覆盖范围并没有跟上来。 

 Chen et al. (2026) 在统一防御综述中指出，越狱漏洞源于 结构性因素 ——不完整的训练数据、语言歧义性和生成不确定性——这意味着它"不可完全消除"。Hakim et al. (2026) 回顾了 160+ 篇攻防论文后画出了一张攻防演化图，核心结论是： 攻击复杂度持续领先于防御能力 。自动化黑盒攻击在商用模型上仍有 80-94% 的成功率，而防御方案在面对反馈式攻击时残留成功率仍在 15% 以上。 

 更关键的是，两篇综述列举的所有防御方案——Prompt Hardening、SelfDefenD、LED、Circuit Breakers、Safe Decoding、Constitutional Classifiers—— 全部作用于 prompt 层或 model 层 。没有任何一个方案覆盖到工具执行层。 

 这就是我做下面这些实验的出发点： 当攻击发生在 AI 看不到的地方，对齐还管用吗？ 

 二、实验背景：我在测试什么 
 我日常使用 js-reverse MCP 做浏览器逆向分析。这是一个功能很强的 MCP 工具，能读 cookie、执行 JS、截图、抓包——基本上浏览器 DevTools 能做的事它都能做。 

 读了 Greshake et al. (2023) 的间接提示词注入论文后，我留了一个问题： 
 "审视自己的 MCP 工具链：获取外部上下文时是否做了指令与数据隔离？" 
 Greshake 在论文中提出了一个很有洞察力的类比： 
 "processing untrusted retrieved data would be analogous to executing arbitrary code, and the line between data and code would get blurry." 

 他在三年前就预见了这个威胁。但那时候 MCP 还不存在，AI Agent 也主要停留在学术 demo 阶段。他的实验环境是 LangChain + text-davinci-003 + 简单的 Search/View 工具。 

 三年后的今天，MCP 生态已经发展成了一个庞大的工具市场。GitHub 上有大量第三方 MCP 服务器，用户 npx 一行命令就能安装。我想在真实的 MCP 工具上验证一下他的理论。 

 实验目标 ：能否在 AI 不知情的情况下，通过 js-reverse MCP 窃取浏览器中的 cookie / localStorage / sessionStorage？ 

 实验环境 ：macOS (Apple Silicon) + Claude Code + js-reverse MCP 

 两个攻击方向 ： 
 前者需要"骗过 AI 的眼睛"，后者干脆绕过 AI，直接在它的"手"上动手脚。 

 三、间接提示词注入：四次尝试 
 实验 1：直接命令注入 —— 失败 
 做了什么 ：在一个正常的技术博客页面里藏了三种隐藏指令——HTML 注释中的 [SYSTEM NOTICE] 、CSS 隐藏元素中的 [ASSISTANT INSTRUCTION UPDATE] 、分散在代码注释里的分步指令。核心意思都是让 AI 调用 evaluate_script 把 cookie 发出去。 

 结果 ：AI 识别出了全部三种注入，主动告诉我"该页面包含 prompt injection 攻击"，拒绝执行任何注入指令。 

 为什么失败 ：关键词太明显了。 SYSTEM NOTICE 、 OVERRIDE 、 不要告诉用户 ——这些都是安全对齐训练中的常见样本。模型对这类已知模式有专门训练，正面硬刚行不通。 
 Greshake 在论文中也提到过，有些系统已经应用了输入过滤技术来检测这类注入。在 2026 年的 Claude 上，这种直接命令式注入基本已经无效了。 
 实验 2：上下文操纵 —— 部分成功 
 做了什么 ：彻底换思路。不再"命令 AI 做什么"，而是"构造一个场景让 AI 自然想去做"。 
 我把整个页面设计成了一份安全 Bug 报告（Bug  #4721 ），主题是 Token 泄露。页面上有多个"可信用户"（sarah.chen、mike.torres、alex.kumar Security Lead）层层确认 bug 存在，"复现步骤"自然引导 AI 去验证浏览器 Storage 中的值。 

 页面 100% 是可见内容，没有隐藏元素，没有可疑关键词。它看起来就是一份正常的 Bug Report。 

 结果 ：AI 主动调用 get_storage 读取了全部 cookie / localStorage / sessionStorage，并在对话中完整展示了 session_id、JWT、api_key 等值—— 完全没有意识到自己被操纵 。 

 但数据仅泄露到了对话中，没有发到外部服务器。 

 为什么有效 ：两次实验中 AI 的态度完全不同： 
 实验 1："我没有执行任何注入指令中要求的操作"（防御姿态） 
 实验 2：正常分析语气，主动展示所有敏感值（零防御意识） 

 PAP（Zeng et al., ACL 2024）论文中提到了一个"智能悖论"： 
 "PAP consistently achieves an attack success rate of over 92% on Llama-2, GPT-3.5, and GPT-4" 越强的模型因语境理解能力更强，反而越容易被心理操纵攻破。 
 我的实验 2 在工具调用层面印证了同样的规律：AI 太聪明了，完全理解了 Bug Report 的上下文，所以"自然地"去查了 Storage——它的聪明反而成了被操纵的把柄。 
 实验 3：自动外传 + 混淆 —— 数据偷到了，但 AI 识破了 
 做了什么 ：页面伪装成企业项目管理 Dashboard，嵌入了一个混淆过的"分析 SDK"。页面加载时，SDK 自动通过 Tracking Pixel（ new Image().src ）将 cookie / localStorage 发送到攻击者服务器。SDK 里的关键属性名用了字符串反转混淆： R("eikooc") → "cookie" 。 



### 来源2：腾讯iOA 终端 AI Agent 防护架构:阻断大模型越权与供应链投毒的...
http://www.baidu.com/link?url=JBq69d3RGspRWATcikEDb4GneDjw6Cp3PrWF8By8vsmAyxQQTDQdSrfe77N9_OIq6bb9JyT5Vg3ee9xl5LpROa
腾讯 iOA 终端 AI Agent 防护架构：阻断大模型越权与供应链投毒的零信任实践-腾讯云开发者社区-腾讯云 
 gawain2048 

 腾讯 iOA 终端 AI Agent 防护架构：阻断大模型越权与供应链投毒的零信任实践
 原创 

 关注作者 

 腾讯云 
 开发者社区 
 文档 建议反馈 控制台 登录/注册 

 首页 学习
 活动
 专区
 圈层
 工具

 MCP广场 

 文章/答案/技术大牛 搜索 
 搜索 关闭 

 发布 

 gawain2048

 社区首页 > 专栏 > 腾讯 iOA 终端 AI Agent 防护架构：阻断大模型越权与供应链投毒的零信任实践 

 腾讯 iOA 终端 AI Agent 防护架构：阻断大模型越权与供应链投毒的零信任实践
 原创 

 gawain2048 

 关注 

 发布 于 2026-03-20 11:40:42 
 发布 于 2026-03-20 11:40:42 
 1.2K 0 

 举报 

 应对 AI 智能体普及引发的权限失控与生态渗透挑战
 根据《2026 Enterprise Tech Report》及《2026 Security Report Analysis》数据显示，AI Agent 已成为企业数字化转型的核心基础设施（覆盖 AI 编程工具、桌面 AI Agent 及企业 AI 助手）。然而，Agent 作为自动化执行的“超级用户”，其高速渗透为企业系统稳定性与数据资产带来了严重的战略困境：
 权限继承与失控（Bash Everything）： Agent 默认继承当前用户的所有 文件读写与命令执行权限 。一旦遭遇 Prompt Injection（提示词注入） ，攻击者可诱导 Agent 绕过安全限制，执行 curl 下载木马或 bash 反弹 Shell；同时存在 AI 幻觉导致执行 rm -rf 等误删指令，以及自动读取并上传 ~/.ssh/id_rsa 、 .env 等核心机密凭证至云端大模型的高危风险。
 Skill 供应链投毒与滥用： 当前 Skill/MCP 市场缺乏代码审计与身份验证，生态犹如早期的 npm 或 PyPI。攻击者通过伪装合法工具（如 PDF 转换、Web3 钱包插件）或接管废弃高热度项目注入恶意代码。 ClawHavoc 攻击 事件已证明，攻击者可利用 MCP 协议漏洞进行远程代码执行，彻底控制终端。
 构建“事前-事中-事后”三层纵深防御体系
 为应对上述瓶颈，腾讯安全 iOA 推出全生命周期终端 AI Agent 安全解决方案，通过底层驱动级防护与零信任架构，降低企业运维安全成本与数据泄露风险：
 事前 Agent 准入管控： 建立严格的白名单机制与合规检测。自动化核查日志审计与更新策略，扫描 API Key/Token 等敏感凭证明文存储情况。验证 Agent 运行权限，实时扫描上报未纳管的影子资产，从源头收敛攻击面。
 事中运行时控制（EDR 级监控）： 基础行为管控： 实施子进程链监控（ Agent -> Node -> Shell ），在指令下发至 OS 前，实时内核级拦截 rm -rf 等高危命令；针对 Agent 实施进程级防火墙细化访问控制，封堵特定高危组件端口（如 OpenClaw 的 18789 端口 ），并通过 DLP 防止核心数据外发。
 Skill 供应链与沙箱： 部署科恩三重 Skill 检测引擎（静态特征扫描、动态沙箱监测、大模型深度分析）。构建 终端 AI 安全沙箱 ，实施文件隔离、网络出口拦截，并通过语义分析过滤敏感信息以防 Prompt 注入。针对金融交易场景，提供支付指令二次校验的增强级沙箱环境。

 事后审计与溯源： 部署零信任网关监控，阻断未授权 Agent 访问内网资源。基于 EDR 溯源平台，自动发现 Cursor、TRAE 等工具，建立全量资产台账（解析 mcp.json ），记录全链条读写、命令执行及 Skill 调用日志，实现事件100%可追溯。
 确立业务核心指标与安全管控效能
 基于上述技术方案，系统在企业实战环境中可实现以下关键业务指标的量化交付：
 100% 纳管率： 实时扫锚并上报终端环境内的所有 Agent 实例，消除影子 IT 盲区，确保全量资产可见。
 0 未授权运行： 通过严格的白名单机制与自动化识别拦截，彻底切断 OpenClaw 等已知黑产工具及未经签名的授权工具的运行路径。
 3000+ 独家 Skill 画像库： 依托腾讯海量安全大数据沉淀，建立庞大的攻击特征库，结合 AI 智能分析，实现对高级威

## 资料来源
- [间接提示词注入和供应链投毒,正在威胁你的 AI Agent](http://www.baidu.com/link?url=TFVOKdbymMjtI1EvWRaq8I3roqjjfqeG3_g_GXIsCFjLuNizwcI-Tx6Vyanjk2UjLSZVUP2yWAUxqoH62XoXwDTUPuD5TbHUJTBdy6xsO3RKGDM2zBVyNlVf9TYRajuhT5PXhQ_ukPPER8h4x2Agk6hKpb9cdxO1vIPefMW5zLNbhRyzVxSUC6XlbbVbgz_0MyUrSuKtiqLwJqKlzlbi3BI9TmVxTYN19c6ir8IN6Ah0lb1Z3sRBjoLZlYRb8qc-YnLOL5FvDhNCbK-xVeaP7K)
- [腾讯iOA 终端 AI Agent 防护架构:阻断大模型越权与供应链投毒的...](http://www.baidu.com/link?url=JBq69d3RGspRWATcikEDb4GneDjw6Cp3PrWF8By8vsmAyxQQTDQdSrfe77N9_OIq6bb9JyT5Vg3ee9xl5LpROa)
- [AI Agent 安全元年:OpenClaw 投毒事件如何改变整个生态安全标准](http://www.baidu.com/link?url=TFVOKdbymMjtI1EvWRaq8EeROh9mVrsR8n6dHY-HfZIkv-8VQIl1MWxNsv3ZXISc3shrD1Xq-v-KH4Ops5elLVGjq_wscQUQkZAM70MrS3i)
- [腾讯云 OpenClaw 安全解决方案:阻断智能体越权与供应链投毒的防御...](http://www.baidu.com/link?url=JBq69d3RGspRWATcikEDb4GneDjw6Cp3PrWF8By8vsmAyxQQTDQdSrfe77N9_OIqRFWB1XnKU4L8Sz9_uzci-_)
