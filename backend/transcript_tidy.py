"""超能小助 · 整理原文（v88）

语音识别出来的文字常常没标点、不分段，一大块看着累。这里让 AI 做两件事：
  1. 加标点、断句；
  2. 按意思分成自然段（每段讲一件事）。
只许加标点和换行，明显的同音错字可以改，其它字一个不许删、不许加、不许改写、不许总结。

AI 交回来的结果会被**核对**：去掉标点和空白后，和原文逐字比对，差太多（被总结 / 删减 / 改写）
就不用这一块，保留原文。所以最坏情况也只是「没整理」，绝不会丢内容。

长文字分块整理（每块约 1500 字，在原有段落 / 句子边界上切），一块失败不影响别的块。
设置存在 memory/transcript_tidy.json：auto（提取后自动整理，默认开）。
"""

import difflib
import json
import os
import re
import threading

_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_DIR, "memory", "transcript_tidy.json")
_lock = threading.Lock()
_cfg = None

CHUNK = 1500

PROMPT = (
    "下面是一段语音识别出来的中文文字，没有标点、也没分段，读起来很累。请你帮我整理：\n"
    "1. 加上合适的标点符号（，。？！：“”等），把句子断开；\n"
    "2. 按意思分成自然段：每段讲一件事或一个意思，段与段之间空一行；一段一般 2 到 6 句话；\n"
    "3. 只能加标点和换行。原文的字一个都不要删、不要加、不要调换顺序、不要改写成书面语、不要总结；"
    "口语、语气词、重复的话也都原样保留；\n"
    "4. 明显是语音识别听错的同音字可以改成正确的字（比如「AA盛程」→「AI生成」、「尺字」→「尺子」），"
    "拿不准的就别改；\n"
    "5. 直接输出整理好的文字，不要加标题，不要加任何说明，不要用 Markdown 符号。\n\n"
    "=== 原文 ===\n"
)


# ════════════════ 设置 ════════════════

def _load():
    global _cfg
    if _cfg is None:
        try:
            with open(_CFG_PATH, "r", encoding="utf-8") as f:
                _cfg = json.load(f) or {}
        except Exception:
            _cfg = {}
        _cfg.setdefault("auto", True)
    return _cfg


def config():
    with _lock:
        return {"auto": bool(_load()["auto"])}


def set_config(auto=None):
    with _lock:
        cfg = _load()
        if auto is not None:
            cfg["auto"] = bool(auto)
        try:
            os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return {"auto": bool(cfg["auto"])}


def auto_on():
    return config()["auto"]


# ════════════════ 判断 / 切块 / 核对 ════════════════

_PUN = "，。！？；：、,.!?;:…—“”\"'‘’（）()《》【】「」"


def _bare(s):
    """去掉标点、空白、Markdown 记号，只留字——用来逐字比对。"""
    return re.sub(r"[\s%s#*>`\-_~|]" % re.escape(_PUN), "", s or "")


def needs_tidy(text):
    """没标点 / 标点很少、或者是一整块没分段的，才值得整理。"""
    t = (text or "").strip()
    if len(_bare(t)) < 40:
        return False
    marks = len(re.findall(r"[，。！？；,.!?;]", t))
    paras = len([p for p in re.split(r"\n\s*\n", t) if p.strip()])
    per = len(t) / max(1, marks)
    return per > 25 or (len(t) > 300 and len(t) / max(1, paras) > 260)


def _chunks(text, size=CHUNK):
    """按原有段落 / 句子边界切成约 size 字的块；实在没边界就硬切。"""
    t = (text or "").strip()
    units = [u for u in re.split(r"(\n\s*\n)", t) if u and not u.isspace()]
    out, cur = [], ""
    for u in units:
        if len(u) > size:                                  # 一段太长：再按句子 / 硬切
            pieces = re.findall(r"[^。！？!?]*[。！？!?]+|[^。！？!?]+$", u) or [u]
            for pc in pieces:
                while len(pc) > size:
                    if cur:
                        out.append(cur)
                        cur = ""
                    out.append(pc[:size])
                    pc = pc[size:]
                if len(cur) + len(pc) > size and cur:
                    out.append(cur)
                    cur = ""
                cur += pc
            continue
        if len(cur) + len(u) > size and cur:
            out.append(cur)
            cur = ""
        cur += u
    if cur.strip():
        out.append(cur)
    out = [c.strip() for c in out if c.strip()]
    if len(out) >= 2 and len(out[-1]) < 300:        # 最后一小截并进上一块，别单独问一次
        out[-2] = out[-2] + out[-1]
        out.pop()
    return out


def _clean_reply(s):
    s = (s or "").strip()
    s = re.sub(r"^```[a-z]*\s*|\s*```$", "", s)
    s = re.sub(r"^(好的|以下是|整理(好|后)的?(文字|内容|结果)?)[^\n]{0,30}[:：]\s*\n", "", s)
    s = re.sub(r"^#+\s.*\n", "", s)
    s = s.replace("\r\n", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    # 只隔一个换行的也当成分段
    s = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", s)
    return s.strip()


def check(src, out):
    """整理结果靠不靠谱：去掉标点后和原文的相似度够高、长度差不多。返回 (ok, 相似度)。"""
    a, b = _bare(src), _bare(out)
    if not a or not b:
        return False, 0.0
    if not (0.9 * len(a) <= len(b) <= 1.1 * len(a)):
        return False, 0.0
    r = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    return r >= 0.9, r


# ════════════════ 主函数 ════════════════

def tidy(text, llm, progress=None):
    """整理一段文字。llm(prompt) -> 回复文字（出错抛异常）。
    返回 (整理后的文字, 说明)。哪一块没整理成功，就保留那一块原文。"""
    chunks = _chunks(text)
    if not chunks:
        return text, "没有文字"
    outs, ok_n = [], 0
    last_err = ""
    for i, c in enumerate(chunks):
        if progress:
            try:
                progress("整理第 %d / %d 块…" % (i + 1, len(chunks)) if len(chunks) > 1 else "AI 正在加标点、分段…")
            except Exception:
                pass
        good = None
        for _try in range(2):
            try:
                reply = _clean_reply(llm(PROMPT + c))
                ok, r = check(c, reply)
                if ok:
                    good = reply
                    break
                last_err = "AI 改动太多（相似度 %.0f%%），没采用" % (r * 100)
            except Exception as e:
                last_err = str(e)[:120]
                break
        if good is None:
            outs.append(c)
        else:
            outs.append(good)
            ok_n += 1
    result = "\n\n".join(outs)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    if ok_n == len(chunks):
        return result, "整理好了（%d 块）" % len(chunks)
    if ok_n:
        return result, "整理了 %d / %d 块，其余保留原文（%s）" % (ok_n, len(chunks), last_err)
    return text, "没整理成：%s" % (last_err or "AI 没回复")
