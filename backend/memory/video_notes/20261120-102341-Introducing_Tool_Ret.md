# 在 Gemini API 中引入工具检索

- 来源链接：https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-tool-retrieval/
- 作者：
- 提取时间：2026-11-20 10:23
- 类型：网页文章
- 发布时间：2026-11-19
- 页面视频：https://storage.googleapis.com/gweb-uniblog-publish-prod/media/tts_audio_87052_umbriel_2026_11_19_18_31_23.mp3
- 原标题：Introducing Tool Retrieval in the Gemini API
- 标签：工具检索、AI Agent、Function Calling、MCP协议、上下文优化

## 🤖 AI 分析

## 一句话概括
Google 在 Gemini API 中推出 Tool Retrieval（工具检索）机制，允许模型根据对话需求动态搜索和加载工具定义，而不是在每次请求开始时把所有工具的 Schema 都塞进 Prompt，从而降低上下文负担、改善 Prefix Caching 缓存效果，并支持大规模工具集、远程 MCP 服务以及客户端自定义检索。

## 背景与主题
随着 AI Agent 和 Function Calling 应用的发展，一个应用可能需要向 Gemini 提供大量可调用工具，例如退款、查询订单、搜索数据、操作第三方服务等。当工具数量越来越多时，如果每次都把所有工具的定义（Schema）提前放进 Prompt，就会增加上下文开销，也可能影响 Prefix Caching 的缓存效率。Google 推出的 Tool Retrieval 正是为了解决这个问题：让 Gemini 按需搜索工具，只在需要时加载对应的工具定义。文章主要介绍了两种实现方式：由 Gemini 在服务器端执行工具检索，以及由开发者在客户端执行自定义检索。文章还特别介绍了它与 Function Calling、Prefix Caching 和远程 MCP Server 的配合方式。

## 核心观点

### 1. Tool Retrieval 的核心价值是从「预先加载所有工具」转向「按需检索工具」
传统 Function Calling 的一种常见做法，是在每次向模型发送请求时，把应用支持的所有工具定义都放进请求中，让模型从中选择需要调用的工具。
但当工具数量很大时，这种方式会产生额外负担：即使当前对话根本不需要某些工具，它们的 Schema 仍然需要出现在 Prompt 中。
Tool Retrieval 改变了这一工作方式。开发者可以将部分工具标记为延迟加载（Deferred Loading），模型在需要时再搜索这些工具，而不是一开始就加载全部定义。
这意味着工具系统可以采用分层结构：最常用的工具始终提前加载，使用频率较低、数量较多的工具则放在检索层中。
本质上，这是将工具管理从「静态工具列表」升级为「动态工具发现与加载」，使 Gemini 应用能够更自然地扩展到拥有大量工具的场景。

### 2. Gemini 服务端检索可以省去开发者自己建设工具索引的工作
文章介绍的一个重要优势是：使用 Gemini API 提供的服务端 Tool Retrieval 时，开发者不需要自行构建或托管工具索引。
原文明确指出：
There's no index to build or host.

即开发者不需要额外搭建一个专门用于搜索工具的索引系统，也不必自己维护相关的检索基础设施。
在这种模式下，Gemini 会在服务器端完成工具搜索。开发者只需要在原有工具配置中增加新的工具检索定义，并对希望延迟加载的工具设置 `defer_loading` 标记。
这使得接入成本相对较低：不需要大规模重构原有 Function Calling 代码，也不需要额外部署 Embedding 检索服务。
对于已经拥有一批工具、但不希望自己维护工具检索系统的开发者来说，这种方式尤其有吸引力。

### 3. 最合理的工具配置方式是「高频工具预加载，低频工具延迟加载」
文章并没有建议把所有工具都改成延迟加载，而是明确提出一种混合式工具管理策略：
- 最常用的工具（Most-used tools）： 提前加载，直接放在模型初始可见的工具列表中。
- 长尾工具（Long tail）： 设置延迟加载，需要时再通过检索发现。

例如，一个电商 AI Agent 可能有以下工具：
- 高频工具：查询订单、查询物流、查看商品信息。
- 低频工具：申请退款、修改会员资料、查询历史优惠活动、处理特殊售后问题。

如果用户经常查询订单和物流，那么这类工具可以始终提前加载；而退款、会员资料修改等工具则可以在真正需要时再检索。
这种分层策略兼顾了响应效率与工具规模扩展能力。
其背后的逻辑是：工具是否需要提前加载，应该取决于它在实际交互中的使用频率，而不是简单地把所有工具一视同仁。
这也意味着开发者可以根据自己的业务场景，逐步调整工具的预加载与延迟加载策略。

### 4. Tool Retrieval 与 Prefix Caching 配合，可以改善 Prompt 缓存的稳定性
文章特别强调了 Tool Retrieval 与 Prefix Caching（前缀缓存）的兼容性，这是一个很重要的技术细节。
Prefix Caching 的基本思路是：如果连续多次请求中，Prompt 前面的部分内容保持不变，就有机会复用已经缓存的前缀内容，减少重复处理。
但如果每次请求都需要在 Prompt 开头放入大量工具 Schema，那么工具定义的变化就可能影响前缀内容的一致性，降低缓存复用的便利性。
Tool Retrieval 通过延迟加载解决了这个问题：
**1. 被延迟加载的工具 Schema 不会出现在 Prompt 的起始部分。**
**2. 模型真正检索到某个工具后，相应的 Schema 才会在对话后续部分加入。**
**3. 因为这些动态加载的工具定义不会改变初始前缀，所以不同轮次之间可以保持相同的缓存前缀。**

文章原文强调：
Deferred schemas stay out of the start of the prompt, and the schemas the model loads are added later in the conversation, so the cached prefix stays the same from turn to turn.

这意味着 Tool Retrieval 不只是减少初始 Prompt 中的工具定义数量，还能够帮助维持 Prompt 前缀的稳定性。
对于需要连续多轮交互、工具数量较多的 Agent 应用而言，这种设计尤其有价值。

### 5. Tool Retrieval 可以直接配合远程 MCP Server，避免逐个声明大量工具
文章还介绍了 Tool Retrieval 对远程 MCP Server 的支持。
MCP（Model Context Protocol）是一种用于连接 AI 模型与外部工具、服务和数据源的协议。一个 MCP Server 可能暴露很多不同的工具，如果全部提前列出并声明，工具管理会变得比较繁琐。
Gemini API 的 Tool Retrieval 可以直接与远程 MCP Server 配合使用。
具体方式是：开发者只需要在 `mcp_server` 工具上设置：
`defer_loading: true`
之后，该 MCP Server 所暴露的工具就可以按需加载。
这意味着开发者不必把 MCP Server 提供的每一个工具都逐一提前列出来。
例如，一个企业内部 MCP Server 可能同时提供客户查询、订单管理、财务数据访问、知识库搜索等多种能力。使用这种机制，开发者可以连接一个包含大量工具的远程服务，再由 Gemini 根据实际需求动态发现和加载相关工具。
其核心价值在于降低大型 MCP 工具集的接入与管理复杂度，使 AI Agent 能够连接更丰富的外部能力。

### 6. 如果开发者有自己的工具注册表或权限系统，可以选择客户端检索
文章并没有把所有开发者都限制在 Gemini 服务端检索模式中。
如果开发者已经维护了自己的工具注册表（Tool Registry）、Embedding Index（嵌入向量索引），或者需要针对不同用户进行权限过滤（Per-user Permission Filter），那么可以选择客户端检索模式。
具体来说，开发者需要将 `tool_search` 声明为：
`"execution": "client"`
同时定义自己的搜索参数（Search Parameters）。
与服务端检索不同，这种方式下真正执行工具查找的是开发者自己的应用程序，而不是 Gemini 服务器。
例如：
- 企业内部有一套自己的工具注册表，希望 Gemini 只使用注册表中存在的工具。
- 不同用户拥有不同权限，需要根据用户身份过滤可用工具。
- 开发者已经建立了 Embedding Index，希望使用自己的向量检索逻辑寻找最相关的工具。

这些场景都更适合客户端检索。
这种设计保留了开发者对工具发现过程的控制权，也使 Tool Retrieval 能够适配更复杂的企业级系统架构。

### 7. 客户端检索会增加一次网络往返，但换来了更高的灵活性
客户端检索并不是完全没有代价。
文章明确指出，客户端检索每发生一次搜索，就会增加一次额外的网络往返（Round Trip），因为工具查找需要由开发者自己的应用程序执行。
其基本流程可以理解为：
**1. Gemini 发现需要搜索某个工具。**
**2. Gemini 发起客户端工具搜索请求。**
**3. 开发者的应用程序执行自己的工具检索逻辑。**
**4. 应用程序将检索结果返回给 Gemini。**
**5. Gemini 根据返回的工具定义继续后续交互。**

与服务端检索相比，这多出了一次由客户端参与的检索流程，因此会带来额外的通信开销和一定的延迟。
但换来的好处是，开发者可以完全按照自己的业务规则决定工具如何搜索、哪些工具可以被发现，以及如何控制用户权限。
因此，两种模式并不是简单的优劣关系，而是针对不同需求的架构选择：追求接入简单、减少自建基础设施，可以选择服务端检索；需要自定义检索、权限控制或已有索引系统，则可以选择客户端检索。

## 关键事实与数据

### 一、核心产品与技术名称

| 名称 | 含义及作用 |
| --- | --- |
| Gemini API | Google 提供的模型 API，本文介绍的 Tool Retrieval 功能所依托的平台 |
| Tool Retrieval | 工具检索机制，让模型根据需要动态搜索和加载工具定义 |
| Function Calling | 函数调用机制，模型选择工具后，由应用程序执行对应函数并返回结果 |
| function_result | 函数执行完成后，应用程序返回给模型的执行结果 |
| defer_loading | 延迟加载配置，用于指定哪些工具不需要提前加载 |
| Prefix Caching | 前缀缓存机制，复用不同请求中保持一致的 Prompt 前缀 |
| MCP | Model Context Protocol，用于连接模型与外部工具及服务的协议 |
| Remote MCP Server | 远程 MCP 服务端，可以向 Gemini 提供多个工具 |
| mcp_server | Gemini API 中用于连接 MCP Server 的工具类型 |
| tool_search | 工具检索定义，用于触发工具搜索 |
| "execution": "client" | 指定工具检索由客户端应用程序执行 |
| Tool Registry | 工具注册表，记录应用程序可以使用的工具 |
| Embedding Index | 嵌入向量索引，可用于根据语义搜索相关工具 |
| Per-user Permission Filter | 用户级权限过滤机制，根据用户权限控制可用工具 |

### 二、文章提到的具体技术事实
**1. 不需要自建索引： 使用 Gemini 服务端 Tool Retrieval 时，开发者不需要构建或托管工具搜索索引。**
**2. 代码改动相对有限： 主要需要增加新的工具检索定义，并为希望延迟加载的工具增加 `defer_loading` 标记。**
**3. 支持混合加载： 高频工具可以提前加载，长尾工具可以延迟加载。**
**4. 支持 Prefix Caching： 延迟加载的 Schema 不进入 Prompt 初始前缀，而是在后续对话中动态加入，有助于维持缓存前缀的一致性。**
**5. 支持远程 MCP Server： 在 `mcp_server` 上设置 `defer_loading: true`，即可让该服务器暴露的工具按需加载。**
**6. 支持客户端检索： 使用 `tool_search` 并指定 `"execution": "client"`，由开发者自己的应用程序完成工具查找。**
**7. 客户端检索需要额外网络往返： 每次执行客户端工具搜索，都会增加一次 Round Trip。**
**8. 支持动态接入工具： 工具不必全部在对话开始前声明，用户连接新的集成服务时，应用程序可以在对话过程中动态提供新工具。**

### 三、文章中的具体业务案例
案例 1：退款操作
文章开头给出了一个退款场景：
当 Gemini 检索到需要的退款工具后，后续流程就回到常规 Function Calling：
- 模型选择退款函数。
- 应用程序执行实际退款操作。
- 应用程序将执行结果通过 `function_result` 返回给模型。

这说明 Tool Retrieval 负责的是工具发现和加载，并不取代实际的业务函数执行机制。
案例 2：大量工具的远程 MCP Server
如果某个远程 MCP Server 暴露了大量工具，开发者不必逐一声明这些工具，可以在 `mcp_server` 上设置 `defer_loading: true`，由 Gemini 按需加载服务器提供的工具。
案例 3：用户连接新的集成服务
当用户在对话过程中连接一个新的 Integration 时，开发者可以通过客户端检索机制，在对话进行期间动态暴露新的工具，而不必要求所有工具在对话开始之前就完成声明。
案例 4：企业级权限控制
如果应用程序需要根据不同用户的身份决定可以使用哪些工具，可以在客户端检索过程中使用 Per-user Permission Filter，而不必完全依赖统一的工具列表。

### 四、重要参数与配置

| 配置 | 作用 |
| --- | --- |
| defer_loading: true | 将相应工具设置为延迟加载 |
| mcp_server + defer_loading: true | 让远程 MCP Server 提供的工具按需加载 |
| tool_search | 声明工具检索能力 |
| "execution": "client" | 将工具检索交给客户端应用程序执行 |
| Search Parameters | 定义客户端工具搜索所使用的参数 |

### 五、原文没有提供的信息
需要注意，这份原文属于文章的一个节选，并不是完整文章。以下信息在当前提供的内容中没有出现：
- Tool Retrieval 的正式发布时间及具体版本要求。
- Gemini API 的具体代码示例、请求格式和完整参数 Schema。
- 服务端检索的具体算法、Embedding 模型或排序机制。
- 单次检索的实际延迟和性能测试数据。
- 与传统 Function Calling 相比，实际节省了多少 Token 或费用。
- 客户端检索的具体实现代码及错误处理方式。
- Tool Retrieval 的具体使用限制、调用配额和收费规则。

因此，不能仅凭这段原文判断其实际性能提升幅度，也不能把「前缀更稳定」直接等同于「缓存命中率一定提高了某个百分比」。

## 金句摘录

### 1. 关于不需要自己建设工具索引
"There's no index to build or host."

中文翻译：不需要构建或托管任何索引。
价值： 体现了 Gemini 服务端 Tool Retrieval 的核心优势：将工具搜索基础设施交给平台处理，开发者不必额外建设一套检索系统。

### 2. 关于高频工具与长尾工具的管理
"You can keep your most-used tools loaded up front and defer the long tail."

中文翻译：你可以让最常用的工具提前加载，而将长尾工具延迟加载。
价值： 这是整篇文章最值得记住的架构设计思想。工具不应该全部采用相同的加载策略，而应该根据使用频率进行分层管理。

### 3. 关于 Prefix Caching 的稳定性
"Deferred schemas stay out of the start of the prompt, and the schemas the model loads are added later in the conversation, so the cached prefix stays the same from turn to turn."

中文翻译：延迟加载的 Schema 不会出现在 Prompt 的开头，而模型加载的 Schema 会在对话后续阶段加入，因此缓存前缀在不同轮次之间能够保持一致。
价值： Tool Retrieval 不只是减少初始工具定义的负担，还考虑到了多轮对话中的缓存复用问题。

### 4. 关于远程 MCP Server
"Set defer_loading: true on an mcp_server tool and every tool that server exposes is loaded on demand, so you can connect a large server without listing its tools one by one."

中文翻译：在一个 `mcp_server` 工具上设置 `defer_loading: true`，该服务器暴露的每一个工具都可以按需加载，因此你可以连接一个大型服务器，而不需要逐一列出它提供的工具。
价值： 这使大型 MCP 工具集的接入更加简单，降低了逐个声明和维护工具的负担。

### 5. 关于客户端检索的灵活性
"Tools do not need to be declared upfront, so you can also expose new tools mid-conversation when a user connects an integration."

中文翻译：工具不需要提前全部声明，因此当用户连接一个集成服务时，你也可以在对话过程中动态暴露新的工具。
价值： 这意味着 Agent 的工具能力不必在对话开始时就完全固定，而是可以随着用户连接新的服务而动态扩展。

## 值得记住的点 / 行动建议

### 1. 设计 Agent 工具体系时，优先采用「高频预加载 + 长尾延迟加载」
不要因为工具数量增加，就简单地把所有工具全部放入初始请求。
可以先根据实际使用情况，把工具划分成两层：
- 核心工具层： 高频使用、对主要业务流程至关重要的工具，提前加载。
- 扩展工具层： 使用频率较低、数量较多、只在特定场景下使用的工具，采用延迟加载。

例如，企业客服 Agent 可以把查询订单、查询物流作为核心工具，把退款、发票处理、会员权益调整等作为按需检索的工具。
这样可以避免每次对话都携带大量暂时用不到的工具定义。

### 2. 如果没有特殊检索需求，优先考虑 Gemini 服务端检索
如果你的应用没有复杂的工具搜索逻辑，也没有必须自建的索引系统，可以优先考虑服务端 Tool Retrieval。
原因有三个：
- 不需要自己建设和维护工具索引。
- 不需要额外运行客户端检索服务。
- 对现有代码的改造相对有限，主要是增加检索工具和延迟加载配置。

对于希望快速构建 Gemini Agent、同时管理较多工具的开发者来说，这是一条比较直接的接入路径。

### 3. 如果涉及用户权限或私有工具库，采用客户端检索
当工具的可用性与用户身份、组织权限或企业内部系统有关时，不应该只考虑工具检索的便利性，还要考虑权限边界。
例如：
- 普通员工只能查询订单，不能执行退款。
- 财务人员可以访问财务工具，普通客服不能访问。
- 不同企业客户只能调用各自租户下的工具。
- 某些工具只能在用户连接指定第三方服务后才能使用。

这类需求可以通过客户端检索与自己的 Tool Registry、Embedding Index 和 Permission Filter 配合实现。
需要注意，工具检索本身不等于权限安全机制。实际执行退款、修改数据等敏感操作时，仍然应该由后端进行独立的权限校验，不能仅仅依赖模型是否检索到了某个工具。

### 4. 大型 MCP Server 可以优先考虑整体接入与按需加载
如果一个 MCP Server 已经暴露了大量工具，不必急着把每个工具都手动复制到 Gemini API 的工具列表中。
可以考虑直接使用远程 MCP Server，并设置：
`defer_loading: true`
让 Gemini 在需要时加载对应工具。
这种设计特别适合企业内部已经建设了多个 MCP Server 的情况，可以减少工具声明和维护工作。
但仍然需要关注 MCP Server 本身的访问权限、工具执行权限和服务可用性。

### 5. 设计多轮 Agent 时，同时考虑工具加载与 Prompt 缓存
开发者在优化 Agent 时，不能只关注单次请求的 Token 数量，还应该考虑多轮交互中的 Prompt 结构是否稳定。
可以重点检查：
- 哪些内容每轮请求都会重复出现？
- 哪些工具 Schema 实际上没有必要放在初始 Prompt 中？
- 动态加载的内容是否会影响 Prompt 前缀？
- 高频工具是否值得提前加载？
- 工具定义变化是否会导致缓存前缀发生变化？

Tool Retrieval 的设计提供了一个值得借鉴的方向：把稳定的内容留在前缀，把动态变化的工具定义放到后续加载阶段。
这样可以同时从工具管理和缓存结构两个角度优化 Agent。

## 我的点评
这篇文章虽然篇幅不长，但介绍的是 AI Agent 工具架构中一个非常实际的问题：随着工具数量增长，如何避免每次请求都携带庞大的工具定义。Tool Retrieval 的价值不只是减少初始 Prompt 的负担，还在于将工具发现、动态加载、MCP 集成和 Prefix Caching 结合起来，提供了更灵活的工具管理方式。其中「高频工具预加载、长尾工具按需加载」尤其值得认同，是一种具有普遍参考价值的架构思路。不过，服务端检索虽然降低了开发者的基础设施负担，但客户端检索在权限控制和自定义搜索方面仍然有不可替代的价值，而且客户端模式需要承担额外的网络往返开销。对于普通开发者，最重要的是根据工具规模、调用频率、权限要求和延迟预算选择合适的模式，而不是为了使用新功能而把所有工具都改成延迟加载。

---

## 📝 完整文字稿

From here it's normal function calling: your code runs the refund and sends back a function_result.

There's no index to build or host. Gemini runs the search on the server, so the only changes to your code are the new tool and a flag on the tools you want to defer. You can keep your most-used tools loaded up front and defer the long tail.

Tool Retrieval also plays well with prefix caching. Deferred schemas stay out of the start of the prompt, and the schemas the model loads are added later in the conversation, so the cached prefix stays the same from turn to turn.

Tool Retrieval also works with remote MCP servers in the Gemini API. Set defer_loading: true on an mcp_server tool and every tool that server exposes is loaded on demand, so you can connect a large server without listing its tools one by one.

### How client-side retrieval works

If you maintain your own tool registry, embedding index, or per-user permission filter, declare the tool_search with "execution": "client" and define your search parameters. Client-side retrieval adds one round trip per search, because your app runs the lookup. Tools do not need to be declared upfront, so you can also expose new tools mid-conversation when a user connects an integration:
