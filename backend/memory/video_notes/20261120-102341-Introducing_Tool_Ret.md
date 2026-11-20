# Introducing Tool Retrieval in the Gemini API

- 来源链接：https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-tool-retrieval/
- 作者：
- 提取时间：2026-11-20 10:23
- 状态：未分析
- 类型：网页文章
- 发布时间：2026-11-19
- 页面视频：https://storage.googleapis.com/gweb-uniblog-publish-prod/media/tts_audio_87052_umbriel_2026_11_19_18_31_23.mp3

## 🤖 AI 分析

（这条只提取了原文，还没做 AI 分析。需要的时候点「🤖 AI 分析」就行：提取完成那一行、笔记列表里这一条的右边、或者打开笔记后的按钮都可以。）

---

## 📝 完整文字稿

From here it's normal function calling: your code runs the refund and sends back a function_result.

There's no index to build or host. Gemini runs the search on the server, so the only changes to your code are the new tool and a flag on the tools you want to defer. You can keep your most-used tools loaded up front and defer the long tail.

Tool Retrieval also plays well with prefix caching. Deferred schemas stay out of the start of the prompt, and the schemas the model loads are added later in the conversation, so the cached prefix stays the same from turn to turn.

Tool Retrieval also works with remote MCP servers in the Gemini API. Set defer_loading: true on an mcp_server tool and every tool that server exposes is loaded on demand, so you can connect a large server without listing its tools one by one.

### How client-side retrieval works

If you maintain your own tool registry, embedding index, or per-user permission filter, declare the tool_search with "execution": "client" and define your search parameters. Client-side retrieval adds one round trip per search, because your app runs the lookup. Tools do not need to be declared upfront, so you can also expose new tools mid-conversation when a user connects an integration:
