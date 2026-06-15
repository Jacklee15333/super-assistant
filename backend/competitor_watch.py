"""
competitor_watch.py — 竞品监控（公开页面变化追踪）

做法：定时抓取你指定的网址，跟上次的快照对比，有实质变化就让模型
判断"变了什么、值不值得提醒"，值得就推送到你手机。

只监控公开可访问的页面（官网、公告页、公开商品页）。
局限：重度依赖 JS 动态加载的页面（很多电商商品页）可能抓不到关键内容，
这种情况会如实告知，不会假装在监控。

配置在 memory/competitors.md，一行一个网址，可加备注：
  https://example.com/products  | 竞品A 产品页
  https://example.com/news      | 竞品A 新闻
"""

import re
import json
import hashlib
import datetime
from pathlib import Path

from agent_core import MEMORY_DIR, read_memory_file, make_client
import web_tools as W

SNAP_DIR = MEMORY_DIR / "snapshots"
SNAP_DIR.mkdir(exist_ok=True)


def _load_targets():
    """读监控目标，返回 [(url, note)]。"""
    raw = read_memory_file("competitors.md")
    targets = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if "|" in line:
            url, note = line.split("|", 1)
            url, note = url.strip(), note.strip()
        else:
            url, note = line, ""
        if url.startswith(("http://", "https://")):
            targets.append((url, note))
    return targets


def _snap_path(url):
    """每个 url 用其哈希做快照文件名。"""
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
    return SNAP_DIR / f"snap-{h}.txt"


def _normalize(text):
    """归一化正文，减少无意义抖动（多空白、纯数字时间戳等）。"""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _diff_summary(old, new, max_len=1500):
    """粗略找出新增/变化的片段，给模型看。"""
    old_set = set(old.split("。"))
    new_lines = new.split("。")
    changed = [ln.strip() for ln in new_lines
               if ln.strip() and ln not in old_set]
    return "。".join(changed)[:max_len]


CHANGE_PROMPT = (
    "下面是某个网页这次抓取相比上次新增或变化的内容片段。\n"
    "请判断：这里有没有值得关注的实质变化（如新品、价格调整、活动、重要公告）？\n"
    "- 如果有，用一两句中文说清楚变了什么。\n"
    "- 如果只是无意义的变动（时间、随机推荐位、广告位），只回复一个词：无。\n\n"
    "网页备注：{note}\n=== 变化片段 ===\n{diff}\n"
)


def check_one(url, note, use_local, model):
    """检查单个网址，返回 (有无值得提醒的变化?, 说明文本)。"""
    try:
        page = W._fetch(url, timeout=20)
        text = _normalize(W._extract_text(page))
    except Exception as e:
        return False, f"[{note or url}] 抓取失败：{e}"

    if not text:
        return False, f"[{note or url}] 读不到正文（可能是动态页面或需登录），跳过。"

    snap = _snap_path(url)
    if not snap.exists():
        snap.write_text(text, encoding="utf-8")
        return False, f"[{note or url}] 首次记录快照，下次起对比。"

    old = snap.read_text(encoding="utf-8", errors="replace")
    if old == text:
        return False, f"[{note or url}] 无变化。"

    diff = _diff_summary(old, text)
    snap.write_text(text, encoding="utf-8")  # 更新快照
    if not diff:
        return False, f"[{note or url}] 有细微变动但无实质内容。"

    # 让模型判断变化是否值得提醒
    try:
        client = make_client(use_local)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": CHANGE_PROMPT.format(note=note or url, diff=diff)}],
        )
        verdict = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return True, f"[{note or url}] 页面有变化（模型判断出错：{e}），建议自己看看：{url}"

    if verdict.strip() == "无" or not verdict:
        return False, f"[{note or url}] 有变动但不重要。"
    return True, f"【{note or url}】{verdict}\n{url}"


def run_check(use_local=True, model="qwen2.5", verbose=False):
    """检查所有监控目标，返回 (值得提醒的变化列表, 全部日志)。"""
    targets = _load_targets()
    if not targets:
        return [], "（competitors.md 里还没有监控目标）"

    alerts, logs = [], []
    for url, note in targets[:10]:  # 最多 10 个
        if verbose:
            print(f"  检查：{note or url}")
        changed, msg = check_one(url, note, use_local, model)
        logs.append(msg)
        if changed:
            alerts.append(msg)

    # 有值得提醒的变化就推送
    if alerts:
        try:
            import push_serverchan
            push_serverchan.push("竞品有动静",
                                 "\n\n".join(alerts)[:2000])
        except Exception:
            pass

    return alerts, "\n".join(logs)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", action="store_true")
    ap.add_argument("--model", default="qwen2.5")
    args = ap.parse_args()
    alerts, logs = run_check(use_local=not args.cloud, model=args.model,
                             verbose=True)
    print("\n--- 日志 ---")
    print(logs)
    print(f"\n--- {len(alerts)} 条值得关注 ---")
    for a in alerts:
        print(a)
