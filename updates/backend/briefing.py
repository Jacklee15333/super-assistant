"""
briefing.py — 市场情报简报

定时搜一组你关心的关键词、读取网页内容、让模型提炼成一份简报，
存档到 memory/briefings/，并可推送到你的手机（Server酱）。

关键词配置在 memory/watchlist.md，一行一个，比如：
  预制菜 行业趋势
  竞品A 新品
  社区团购 政策

用途：市场情报、竞品公开动态、行业新闻聚合等正当用途。
只读取公开网页，不抓取需登录或授权的数据。
"""

import datetime
from pathlib import Path

from agent_core import (MEMORY_DIR, read_memory_file, make_client,
                        make_client_for, is_web_model)
import web_tools as W

BRIEF_DIR = MEMORY_DIR / "briefings"
BRIEF_DIR.mkdir(exist_ok=True)


def _load_watchlist():
    """读关注的关键词清单，跳过空行和注释。"""
    raw = read_memory_file("watchlist.md")
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if line:
            items.append(line)
    return items


KW_PROMPT = (
    "你是市场情报分析助手。今天是 {today}。下面是专门针对关键词「{kw}」抓取到的网页资料。\n"
    "请**只围绕这个关键词**，提炼一段内容充实的中文情报：\n"
    "- 给出 5-8 条要点，覆盖最新动态、关键数据/事实、不同来源的说法、值得注意的细节；\n"
    "- 每条要点写 1-2 句，把事情说清楚，不要写空泛的一句话；\n"
    "- 如有潜在机会或风险信号，最后用一小段点出来。\n"
    "归纳、不要照抄原文。如果资料确实很少，就基于已有资料尽量写，并说明资料有限。\n"
    "直接输出要点正文，不要重复关键词标题（我会自己加），不用写来源链接（我会统一附上）。\n\n"
    "=== 资料 ===\n{material}\n"
)

# 网页大模型专用：让 ChatGPT 自己联网搜索这个关键词的最新消息再总结，
# 不需要软件去喂网页材料（那样又脏又旧）。
KW_SEARCH_PROMPT = (
    "今天是 {today}。请帮我整理「{kw}」的最新情报（重点看最近一两周，旧闻不算新）。**如果你现在能联网，请先联网搜索最新、权威的信息**，"
    "再用中文给出一份简明情报。\n"
    "【信息源】优先权威、官方、专业来源：政府或监管机构官网、官方/权威媒体、公司官方公告、"
    "知名研究机构等；尽量不用内容农场、自媒体二次转载。\n"
    "【正文】\n"
    "- 列出 5-8 条要点，每条 1-2 句，说清楚发生了什么、关键数据或事实、大致时间；\n"
    "- 不同来源说法不一致时简要点出；\n"
    "- 最后用一两句话总结值得注意的机会或风险。\n"
    "【来源】正文之后另起一段，标题写「来源：」，用 Markdown 列表给出来源，"
    "尽量写成**可点击的超链接**，格式 `- [来源名称](完整网址)`，网址以 http 开头、指向官方或原文页面。\n"
    "【重要】如果此刻你**确实无法联网搜索**，不要拒绝、也不要空着——就基于你已掌握的可靠信息尽力整理，"
    "并在开头用一句话注明「（注：本次未能联网，以下为已知信息，时效性请以官方为准）」；"
    "来源处给出你确定的**官方网站主页**链接即可（拿不准的具体文章链接就别编造）。"
    "开头不用重复关键词标题（我会自己加）。"
)


def _summarize_keyword(client, model, kw, material):
    """让模型只针对一个关键词提炼（喂入已抓取的网页材料）。失败时返回友好占位文本。"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": KW_PROMPT.format(
                           kw=kw, material=material,
                           today=__import__("datetime").date.today().isoformat())}],
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or "（这个关键词暂时没提炼出内容，可看下面的来源链接。）"
    except Exception as e:
        return f"（提炼出错：{e}）"


def _clean_summary(t):
    """去掉残留的引用角标杂质：独立成行或跟在文字/链接后的 "+1"/"+2"
    （兼容全角＋、全角数字、不间断空格），以及重复的来源名。"""
    import re
    t = (t or "").replace("\u00a0", " ")
    # ① 独立成行的 "+1"/"+2"（含全角＋﹢、全角数字、可能带空格）
    t = re.sub(r"(?m)^[ \t]*[+＋﹢][ \t]*[\d０-９]+[ \t]*$", "", t)
    # ② 跟在文字/链接/标点后面的 " +1"
    t = re.sub(r"[ \t]*[+＋﹢][ \t]*[\d０-９]+(?=[\s，。；、,\.\)\]）】]|$)", "", t)
    # ③ 折叠重复来源名（去掉+N后可能留下 "Anthropic Anthropic"）
    t = re.sub(r"\b(\w[\w\.\-]{1,30})(?:\s+\1\b){1,}", r"\1", t)
    # ④ 清理多余空行/空格
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def _search_keyword_web(client, model, kw):
    """让网页 ChatGPT 自己联网搜索这个关键词并总结（自带来源）。"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": KW_SEARCH_PROMPT.format(
                           kw=kw, today=__import__("datetime").date.today().isoformat())}],
        )
        txt = (resp.choices[0].message.content or "").strip()
        return _clean_summary(txt) or "（这个关键词暂时没查到内容。）"
    except Exception as e:
        return f"（查询出错：{e}）"


def _gen_briefing_title(client, model, body_text, keywords):
    """根据简报正文，起一个能体现当期重点的简短标题（不带日期）。
    ★优先用本地小模型来起标题：标题是很轻的任务，网页模型反而又慢又容易在
      「短回复」上卡死（实测会卡到超时）。本地失败再退回传入的 client。
    失败时返回 ''，调用方退回用关键词兜底。"""
    import re
    material = (body_text or "")[:2500]
    prompt = (
        "下面是一份刚生成的市场情报简报正文。请给它起一个能体现“本期重点”的"
        "简短中文标题，方便在列表里一眼看出这期讲了什么。\n"
        "要求：12-22 个字；概括最重要的 1-2 个动向；不要带日期、不要引号、"
        "不要“情报简报”这几个字、不要任何解释，只输出标题本身。\n\n"
        f"关注关键词：{', '.join(keywords)}\n\n简报正文：\n{material}\n\n标题：")

    raw = ""
    # 1) 先用本地小模型（快、稳，不走网页自动化）
    try:
        lc = make_client(True)
        resp = lc.chat.completions.create(
            model="qwen2.5", messages=[{"role": "user", "content": prompt}])
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:
        raw = ""
    # 2) 本地不行（比如没装 Ollama），再用传进来的 client 兜底
    if not raw:
        try:
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}])
            raw = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""

    raw = raw.splitlines()[0] if raw else ""
    raw = re.sub(r"^(标题|title)\s*[:：]\s*", "", raw, flags=re.I)
    raw = raw.strip().strip("“”\"'《》「」").strip()
    raw = re.sub(r"[。.!！?？,，、;；\s]+$", "", raw)
    return raw[:30]


def generate_briefing(use_local=True, model="qwen2.5", verbose=False,
                      on_step=None, on_detail=None):
    """跑一次情报简报：每个关键词单独一块，逐块拼成简报。
    · 网页大模型：让 ChatGPT 自己联网搜该关键词的最新消息并总结（干净、最新、自带来源）。
    · 本地/云端模型：它们不能上网，仍由软件先抓网页材料、再让模型提炼。
    on_step：关键词级里程碑（前端"详情"里一步一条）；on_detail：当前步实时明细。"""
    def _step(m):
        if on_step:
            try: on_step(m)
            except Exception: pass
    def _detail(m):
        if on_detail:
            try: on_detail(m)
            except Exception: pass

    keywords = _load_watchlist()
    if not keywords:
        return "（watchlist.md 里还没有关键词。先去添加你关心的话题。）"

    web = False
    try:
        web = is_web_model(model)
    except Exception:
        web = (model == "web")

    _step("读取关键词清单…")
    try:
        # ★ make_client_for：model=='web' → 网页大模型客户端（驱动网页 ChatGPT 卡片）。
        #   on_progress=_detail：把网页模型的实时活动（登录/选卡/思考中/接收回复N字）
        #   播报到"当前步明细"，这样前端展开"详情"能看到真实进度。
        client = make_client_for(model, use_local, on_progress=_detail)
    except Exception as e:
        return f"连接模型出错：{e}"

    ts = datetime.datetime.now()
    # 先攒正文各块（标题最后根据正文重点来起，所以这里先不放 H1）
    body_sections = []

    todo = keywords[:8]          # 最多 8 个，控制时间和成本
    n = len(todo)
    for i, kw in enumerate(todo, 1):
        if verbose:
            print(f"  调研：{kw}")
        _step(f"调研第 {i}/{n} 个关键词：{kw}")
        if web:
            # 网页大模型：直接让它联网搜+总结，来源由 AI 在文末自带
            summary = _search_keyword_web(client, model, kw)
            block = [f"## 🔎 {kw}", "", summary, "\n---"]
        else:
            # 本地/云端模型：软件抓材料，模型提炼，软件附来源链接
            _detail("抓取网页资料中…")
            material, sources = W.gather(kw, read_count=4)
            _detail("模型提炼中…")
            summary = _summarize_keyword(client, model, kw, material)
            block = [f"## 🔎 {kw}", "", summary]
            if sources:
                block.append("")
                block.append("**信息来源（点链接可核对原文）：**")
                for t, u in sources:
                    title = (t or u).strip()[:60]
                    block.append(f"- [{title}]({u})")
            block.append("\n---")
        body_sections.append("\n".join(block))

    _step("各关键词整理完成，正在拼合排版…")
    body_text = "\n\n".join(body_sections).rstrip("-\n ")

    # ★让模型根据正文重点起一个有信息量的标题，替代千篇一律的「情报简报 时间」
    _step("提炼本期标题…")
    smart_title = ""
    try:
        smart_title = _gen_briefing_title(client, model, body_text, keywords)
    except Exception:
        smart_title = ""
    if not smart_title:
        # 兜底：用前两个关键词拼一个，仍比纯时间戳有信息
        smart_title = "、".join(keywords[:2]) + " 等动向"

    # 标题行带重点 + 副标题保留时间和关注词，存档/列表都更好认
    head = [f"# {smart_title}",
            f"> 情报简报 · {ts.strftime('%Y-%m-%d %H:%M')}",
            f"关注：{', '.join(keywords)}\n"]
    brief = "\n".join(head) + "\n\n" + body_text

    # 存档
    fname = f"brief-{ts.strftime('%Y%m%d-%H%M')}.md"
    (BRIEF_DIR / fname).write_text(brief, encoding="utf-8")

    # 尝试推送到微信
    try:
        import push_serverchan
        push_serverchan.push("情报简报", brief[:2000])
    except Exception:
        pass

    return brief


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", action="store_true")
    ap.add_argument("--model", default="qwen2.5")
    args = ap.parse_args()
    print(generate_briefing(use_local=not args.cloud, model=args.model,
                            verbose=True))
