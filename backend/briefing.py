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

from agent_core import MEMORY_DIR, read_memory_file, make_client
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
    "你是市场情报分析助手。下面是专门针对关键词「{kw}」抓取到的网页资料。\n"
    "请**只围绕这个关键词**，提炼一段内容充实的中文情报：\n"
    "- 给出 5-8 条要点，覆盖最新动态、关键数据/事实、不同来源的说法、值得注意的细节；\n"
    "- 每条要点写 1-2 句，把事情说清楚，不要写空泛的一句话；\n"
    "- 如有潜在机会或风险信号，最后用一小段点出来。\n"
    "归纳、不要照抄原文。如果资料确实很少，就基于已有资料尽量写，并说明资料有限。\n"
    "直接输出要点正文，不要重复关键词标题（我会自己加），不用写来源链接（我会统一附上）。\n\n"
    "=== 资料 ===\n{material}\n"
)


def _summarize_keyword(client, model, kw, material):
    """让模型只针对一个关键词提炼。失败时返回友好占位文本。"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": KW_PROMPT.format(kw=kw, material=material)}],
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or "（这个关键词暂时没提炼出内容，可看下面的来源链接。）"
    except Exception as e:
        return f"（提炼出错：{e}）"


def generate_briefing(use_local=True, model="qwen2.5", verbose=False):
    """跑一次情报简报：对每个关键词分别 搜+读+提炼，逐块拼成简报。
    分开处理能保证每个关键词都有独立板块，不会被模型合并或漏掉。"""
    keywords = _load_watchlist()
    if not keywords:
        return "（watchlist.md 里还没有关键词。先去添加你关心的话题。）"

    try:
        client = make_client(use_local)
    except Exception as e:
        return f"连接模型出错：{e}"

    ts = datetime.datetime.now()
    sections = [f"# 情报简报 {ts.strftime('%Y-%m-%d %H:%M')}\n",
                f"关注：{', '.join(keywords)}\n"]

    for kw in keywords[:8]:  # 最多 8 个，控制时间和成本
        if verbose:
            print(f"  调研：{kw}")
        material, sources = W.gather(kw, read_count=4)
        summary = _summarize_keyword(client, model, kw, material)
        # 每个关键词一个独立板块：标题 + 提炼 + 该关键词的来源链接
        block = [f"## 🔎 {kw}", "", summary]
        if sources:
            block.append("")
            block.append("**信息来源（点链接可核对原文）：**")
            for t, u in sources:
                title = (t or u).strip()[:60]
                block.append(f"- [{title}]({u})")
        block.append("\n---")
        sections.append("\n".join(block))

    brief = "\n\n".join(sections).rstrip("-\n ")

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
