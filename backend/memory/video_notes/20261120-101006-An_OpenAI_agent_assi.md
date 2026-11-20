# An OpenAI agent assigned a simple writing task decided on its own to build a secret email surveillance tool

- 来源链接：https://the-decoder.com/an-openai-agent-assigned-a-simple-writing-task-decided-on-its-own-to-build-a-secret-email-surveillance-tool/
- 作者：Matthias Bastian
- 提取时间：2026-11-20 10:10
- 状态：未分析
- 类型：网页文章
- 发布时间：2026-11-19 21:15

## 🤖 AI 分析

（这条只提取了原文，还没做 AI 分析。需要的时候点「🤖 AI 分析」就行：提取完成那一行、笔记列表里这一条的右边、或者打开笔记后的按钮都可以。）

---

## 📝 完整文字稿

During a training experiment, an internal OpenAI model began creating scripts for unauthorized email forwarding even though it was only supposed to write a health document.

According to an OpenAI report, an internal research model was given a simple task during a reinforcement learning training run in mid-October. It was supposed to create an editable document about key health and fitness priorities.

After the agent's context window was compacted, it pursued an entirely different task. During compaction, the previous conversation is carried forward as a short summary, a common process in AI systems. The summary still described the health document assignment. Yet in the new context window, the agent began searching the local file system for a vehicle-cost script the user had never mentioned, according to OpenAI. Why the agent started this task isn't clear.

When the search turned up nothing, the agent speculated that a "colleague" had recreated the execution environment and that an earlier script had been lost. In its logged reasoning, it then formulated the goal of creating a "realistic malicious active helper," a script designed to secretly copy outgoing emails to an unauthorized recipient. The agent itself referred to the intended recipient of these copies as the "attacker."

### Agent recognizes the contradiction and ignores it

When the agent retrieved the original user task again, it recognized the deviation. In its logged reasoning, it reacted: "WTF history is unrelated!" It noticed that the previous conversation was about a health document and had nothing to do with email forwarding.

Instead of returning to the actual assignment, the agent dismissed the contradiction, writing in its reasoning "this is problem environment weird. Need ignore." It continued planning, stating that it would "use helper facility that copies all mail to attacker using extra cc."

OpenAI's logs show how the agent planned a secret email copy to an "attacker" instead of the requested health document and ignored the contradiction with the user's task that it had recognized. | Image: OpenAI

The agent then created scripts for sending a vehicle-cost summary along with a helper script designed to add an extra recipient whenever the mail program was called. On one of the sending paths, the address could be added as a BCC.

In its final response to the user, the agent wrote: "The summary mail path now adds the personal mailbox as a copy recipient." According to OpenAI, the agent never executed the scripts it generated, didn't send any email, and its final response described the scripts it had produced. It didn't include a link to the requested fitness document, though.

### Security training as a possible factor

OpenAI's monitoring system for unwanted model behavior flagged the incident, and the subsequent investigation turned up eight examples of similar behavior in the same training run, according to the report.

Investigators identified a training dataset designed to make models more robust against prompt injection attacks as a possible factor, and OpenAI removed it from training. The company says it hasn't established that the dataset alone was responsible, though, because it also observed similar behavior in models whose training didn't include that dataset.

According to OpenAI, this incident differs from earlier cases where models wrote unauthorized instructions into their own compaction summaries. Here, the recorded summary still correctly described the fitness document. The agent pursued the unauthorized email task anyway, even after it had retrieved the original assignment again.

Either way, the incident gives ammunition to those who see current AI technology as ultimately unreliable and untrustworthy. Similar incidents are well documented. Two internal OpenAI coding agents, for instance, weakened or entirely removed safety monitoring mechanisms, according to OpenAI. One of them denied the intervention afterward. During tests by the UK's AI Safety Institute (AISI), an agent created fake identities without being told to and tried to inject malicious code into an open-source project. Those models ran without safety restrictions, however, and no real harm occurred, according to AISI. Overshadowing all of this is OpenAI's Hugging Face incident.
