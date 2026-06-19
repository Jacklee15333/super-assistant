"""
skills_store.py — 技能（Skills）存取与管理

「技能」就是一篇有固定开头的 Markdown：开头用 --- 包一段说明（name / description），
正文是一套「遇到某类任务时该怎么做」的方法论。模型平时只看 name+description（很轻），
真要用时才把正文整篇读进来（靠 load_skill 工具）。这就是所谓「渐进式披露」。

目录结构（每个技能一个文件夹，兼容开源 agent-skills 格式，用户可直接把别处下载的技能文件夹拷进来）：
    backend/skills/<slug>/SKILL.md
    backend/skills/_state.json        # 记录哪些技能被启用（不在里面的默认启用）

首次运行会把内置的 4 课中文技能写到磁盘，之后用户可在界面里编辑/删除/新建。
本模块不依赖任何第三方库（自己解析 frontmatter），保持依赖最小。
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"
STATE_PATH = SKILLS_DIR / "_state.json"

# slug 只允许字母数字和连字符，避免路径注入
_SLUG_RE = re.compile(r"[^a-z0-9\-]+")


def _slugify(name: str) -> str:
    """把技能名转成安全的文件夹名。中文等非 ascii 会被去掉，所以建议新建技能时另给一个英文 slug。"""
    s = (name or "").strip().lower().replace(" ", "-")
    s = _SLUG_RE.sub("", s)
    s = s.strip("-")
    return s or "skill"


def _safe_slug(slug: str) -> str:
    """对外部传入的 slug 做一次清洗，杜绝 ../ 之类。"""
    s = (slug or "").strip().lower()
    s = _SLUG_RE.sub("", s.replace(" ", "-"))
    return s.strip("-")


def _parse_frontmatter(text: str):
    """从 SKILL.md 文本里解析出 name / description。返回 (name, description, body)。
    frontmatter 是开头两行 --- 之间的部分；解析失败也不报错，尽量给出能用的结果。"""
    name, desc = "", ""
    body = text
    if text.lstrip().startswith("---"):
        # 去掉可能的 BOM/前导空白后定位两个 ---
        t = text.lstrip("\ufeff")
        parts = t.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].lstrip("\n")
            for line in fm.splitlines():
                line = line.strip()
                if line.lower().startswith("name:"):
                    name = line[5:].strip().strip("'\"")
                elif line.lower().startswith("description:"):
                    desc = line[12:].strip().strip("'\"")
    # frontmatter 里没写 name，就退而用正文第一个标题
    if not name:
        m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if m:
            name = m.group(1).strip()
    return name, desc, body


def _load_state() -> dict:
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"disabled": []}  # 默认全部启用；只记录被关掉的


def _save_state(state: dict):
    try:
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _skill_md_path(slug: str) -> Path:
    return SKILLS_DIR / slug / "SKILL.md"


# ---------- 对外 API ----------

def ensure_seeded():
    """首次运行：把内置技能写到磁盘。已存在则不覆盖（保护用户改过的内容）。"""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for slug, content in BUILTIN_SKILLS.items():
        p = _skill_md_path(slug)
        if not p.exists():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            except Exception:
                pass


def list_skills(include_disabled: bool = True):
    """列出所有技能（含元信息）。返回 list[dict]：slug/name/description/enabled/builtin。"""
    ensure_seeded()
    state = _load_state()
    disabled = set(state.get("disabled", []))
    out = []
    if not SKILLS_DIR.exists():
        return out
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if not md.exists():
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        name, desc, _ = _parse_frontmatter(text)
        enabled = d.name not in disabled
        if (not enabled) and (not include_disabled):
            continue
        out.append({
            "slug": d.name,
            "name": name or d.name,
            "description": desc,
            "enabled": enabled,
            "builtin": d.name in BUILTIN_SKILLS,
        })
    return out


def get_skill(slug: str):
    """读取某个技能的完整内容。返回 dict 或 None。"""
    slug = _safe_slug(slug)
    md = _skill_md_path(slug)
    if not md.exists():
        return None
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    name, desc, body = _parse_frontmatter(text)
    state = _load_state()
    return {
        "slug": slug,
        "name": name or slug,
        "description": desc,
        "content": text,
        "body": body,
        "enabled": slug not in set(state.get("disabled", [])),
        "builtin": slug in BUILTIN_SKILLS,
    }


def load_skill_body(slug_or_name: str) -> str:
    """给 load_skill 工具用：按 slug 或名字找到技能，返回完整正文。找不到给出清单提示。"""
    ensure_seeded()
    key = _safe_slug(slug_or_name)
    s = get_skill(key)
    if not s:
        # 再按显示名模糊找一次（用户/模型可能传的是中文名）
        for item in list_skills():
            if slug_or_name and (slug_or_name.strip() == item["name"] or slug_or_name.strip() == item["slug"]):
                s = get_skill(item["slug"])
                break
    if not s:
        names = "、".join(f"{i['name']}({i['slug']})" for i in list_skills() if i["enabled"]) or "（暂无）"
        return f"没有找到名为「{slug_or_name}」的技能。当前可用技能：{names}。请用其中一个的名字或 slug 再试。"
    if not s["enabled"]:
        return f"技能「{s['name']}」当前处于关闭状态，未启用。"
    return f"=== 技能：{s['name']} ===\n{s['body']}"


def save_skill(slug: str, content: str, name: str = "", description: str = ""):
    """新建或覆盖一个技能。若没传 slug，则按 name 生成。返回保存后的 slug。
    若 content 没有 frontmatter，会用 name/description 自动补一个头。"""
    slug = _safe_slug(slug) or _slugify(name)
    content = content or ""
    has_fm = content.lstrip().lstrip("\ufeff").startswith("---")
    if not has_fm:
        nm = name or slug
        ds = description or ""
        content = f"---\nname: {nm}\ndescription: {ds}\n---\n\n{content.strip()}\n"
    md = _skill_md_path(slug)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(content, encoding="utf-8")
    return slug


def delete_skill(slug: str) -> bool:
    """删除一个技能（连同它的文件夹）。返回是否成功。"""
    slug = _safe_slug(slug)
    d = SKILLS_DIR / slug
    if not d.exists() or not d.is_dir():
        return False
    try:
        for p in sorted(d.rglob("*"), reverse=True):
            try:
                p.unlink()
            except Exception:
                try:
                    p.rmdir()
                except Exception:
                    pass
        d.rmdir()
    except Exception:
        return False
    # 从 disabled 列表里也清掉
    state = _load_state()
    if slug in state.get("disabled", []):
        state["disabled"].remove(slug)
        _save_state(state)
    return True


def set_enabled(slug: str, enabled: bool):
    """启用/停用一个技能（停用后不进系统提示、load_skill 也会拒绝）。"""
    slug = _safe_slug(slug)
    state = _load_state()
    dis = set(state.get("disabled", []))
    if enabled:
        dis.discard(slug)
    else:
        dis.add(slug)
    state["disabled"] = sorted(dis)
    _save_state(state)
    return True


def build_skills_index() -> str:
    """给系统提示用：把所有【已启用】技能的 名字+用途 拼成一段清单。
    只放轻量元信息，正文不放（要用时模型自己调 load_skill 取）。无启用技能时返回空串。"""
    try:
        items = [i for i in list_skills() if i["enabled"]]
    except Exception:
        return ""
    if not items:
        return ""
    lines = [
        "=== 你的技能库（Skills）===",
        "下面是你掌握的「技能」。每个技能是一套针对特定任务的做事方法。",
        "**当用户的任务匹配某个技能的「适用场景」时，先调用 load_skill 工具把该技能的完整步骤读进来，再按它的方法去做**——不要凭记忆瞎做。",
        "一次只加载真正用得上的那一个；任务不匹配任何技能时，正常处理即可，不用强行套。",
        "",
    ]
    for it in items:
        desc = (it.get("description") or "").strip()
        lines.append(f"- 「{it['name']}」(slug: {it['slug']})：{desc}")
    lines.append("")
    lines.append("（要加载某技能时：load_skill，参数 name 填上面的技能名或 slug。）")
    return "\n".join(lines)


# ====================================================================
# 内置技能（首次运行写入磁盘）。改写自开源 agent-skills，翻成中文并做了通用化。
# 用户可在界面里编辑、停用或删除；删了想要回来，删掉对应文件夹再重启即可重新生成。
# ====================================================================

_SKILL_INTERVIEW = """---
name: 问清需求
description: 用户的需求说得含糊、缺少关键信息时，用「一次只问一个问题」的方式把真实意图问清楚，问到八九不离十再动手。适用场景：用户说「帮我做个X」却没说给谁用、为什么要、做成什么样算成功；或用户直接说「帮我理清楚」「我没想好」「先别急着做」。不适用：需求本身已经很明确，或只是查个事实、改个错别字这种一步到位的小事。
---

# 问清需求

## 这个技能解决什么

人嘴上要的，和心里真正想要的，常常是两回事。他说「做个看板」，是因为大家都这么说，不一定是看板能解决他的问题。在你动手之前把这个差距问清楚，是最便宜的时刻——一旦开始做了，再返工代价就大了。

## 什么时候用

需求里缺了下面任何一样，就该用这个技能：**给谁用**、**为什么现在要**、**做成什么样算成功**、**最硬的限制是什么**。或者用户的说法很「套话」（「做个X」「弄快一点」），你不问就只能靠猜。

## 怎么做

**第一步：先写下你的猜测和把握度。**
动手问之前，先用一句话写下「我觉得用户其实想要的是……」，再给一个诚实的把握度（0–100%）。
> 猜测：你想要的其实是「随时知道现在进展如何」，「看板」只是顺口说的。
> 把握：约 30% —— 还不知道给谁看、「进展」具体指什么、做到什么算成功。
把握度低于 70% 时，顺手写一句「还缺什么」。这能逼你诚实，也告诉用户该补什么。

**第二步：一次只问一个问题，每个问题都附上你的猜测。**
格式：
> 问：（一个具体的问题）
> 我猜：（你对答案的猜测 + 为什么这么猜）
问完**停下等用户反应**，再问下一个。
- 为什么一次一个：一堆问题用户只会扫一眼、给敷衍答案；而且第三个问题往往取决于第一个的答案。
- 为什么附猜测：纠正一个错猜，比从零想一个答案快得多；也逼你把自己的假设亮出来。

**第三步：警惕「该想要」而非「真想要」的答案。**
最危险的回答是听起来很正确、其实是套话的那种：「我要它可扩展」「要现代化」「按标准做法」。听到这种，问一句：
> 「如果不用跟任何人交代，你自己到底想要什么样的？」
这一句往往比前面五个问题都管用。

**第四步：用用户自己的话复述意图。**
把握够了，就把你现在理解的写回去，尽量用他的词，让他逐行确认：
> 目标：……｜给谁用：……｜为什么现在：……｜怎样算成功：……｜硬限制：……｜不做什么：……
> 对吗？/ 要改哪条？
「不做什么」这一行**不能省**——一半的误会都来自双方对「不做哪些」的沉默分歧。

**第五步：要一个明确的「对」，不是「你看着办」。**
「你看着办」=他自己也没想清楚，换两个具体选项让他选。「听起来不错」「行，开始吧」往往是客气，不是确认，追一句「有要改的吗？」。

## 什么时候算问完

当你能预测「接下来我要问的三个问题，用户会怎么答」时，就说明你们想到一块儿了，停止提问，给出复述。如果问了好几轮还预测不了，那是这件事本身有更深的东西没说清——直接告诉用户「我问了好几轮还摸不准，是不是有个更根本的东西没讲？」

## 容易自我欺骗的地方

| 借口 | 实际 |
|---|---|
| 「需求够清楚了」 | 你现在能用一句话写出他想要的结果吗？写不出就是不清楚。 |
| 「问太多浪费他时间」 | 4–6 个准问题花的时间很少；做错东西返工花的时间巨大，而且是用户在买单。 |
| 「边做边搞清楚」 | 代码写出来之后再改，代价是现在的十倍。 |
| 「他说你看着办，那我定吧」 | 那是甩锅不是决定。换成两个具体选项让他选。 |
"""

_SKILL_IDEA = """---
name: 点子打磨
description: 把一个还很模糊的想法，通过「先发散、再收敛」打磨成清晰、能落地的方案。适用场景：用户有个粗略的点子但没想透；想在动手前先把假设捶打一遍；或想多探索几种可能再选一个。触发词：「帮我想想」「这个点子怎么打磨」「帮我把方案捶一捶」。不适用：方案已经很明确、只等执行的时候。
---

# 点子打磨

把粗糙的想法打磨成「值得做、做得动」的清晰方案。三步：先发散、再收敛、最后落成一页纸。

## 信奉的几条

- 简单是终极的复杂。往「还能解决真问题的最简版本」去逼。
- 从用户体验倒推技术，不是反过来。
- 对一千件事说不。专注胜过铺开。
- 质疑每一个假设，「大家都这么做」不是理由。
- 别只给更快的马，给他没见过的未来。

## 三个阶段

### 阶段一：理解 + 发散
1. **把想法重述成一句「我们如何能……」的问题**，逼出「到底在解决什么」。
2. **问 3–5 个关键问题**（不要更多）：给谁用？怎样算成功？真正的限制（时间/技术/资源）？以前试过什么？为什么现在做？没搞清「给谁用」和「怎样算成功」之前不要往下走。
3. **生成 5–8 个变体**，换镜头看：
   - 反转：「反着来会怎样？」
   - 去限制：「如果预算/时间/技术都不是问题呢？」
   - 换受众：「如果是给另一类人用呢？」
   - 组合：「跟某个相邻的东西合起来呢？」
   - 极简：「砍到十倍简单是什么样？」
   - 放大：「做到极大规模会怎样？」
   推到用户最初没要求的地方去，但每个变体都要有「它为什么存在」的理由，别只是罗列。

### 阶段二：评估 + 收敛
1. **聚类**：把有感觉的点子归成 2–3 个真正不同的方向（不是同一主题的小变化）。
2. **捶打**每个方向：用户价值（是止痛药还是维生素？）、可行性（最难的部分是什么？）、差异化（凭什么让人从现在的方案换过来？）。
3. **挖出隐藏假设**：你在赌哪件事是真的（但还没验证）？什么会直接搞死这个想法？你故意先忽略了什么、为什么现在可以忽略？**这一步最常被跳过，恰恰最重要。**
   要诚实，不要做应声虫。点子弱就直说（带着善意）。

### 阶段三：磨利 + 交付
产出一页纸（Markdown），推动事情往前走：
```markdown
# 〔点子名〕
## 要解决的问题
〔一句「我们如何能……」〕
## 推荐方向
〔选哪个方向、为什么，2–3 段〕
## 待验证的关键假设
- [ ] 〔假设 1 —— 怎么验〕
- [ ] 〔假设 2 —— 怎么验〕
## 最小可行版本（MVP）
〔能验证核心假设的最小版本，什么做、什么不做〕
## 不做什么（及为什么）
- 〔某项〕 —— 〔原因〕
## 待解问题
- 〔动手前需要回答的问题〕
```
**「不做什么」这一段往往最有价值**——专注就是对好点子说不，把取舍摆明。
问用户要不要存成文件，确认了再存。

## 红线
- 一口气生成 20 个肤浅变体，而不是 5–8 个想清楚的。
- 跳过「给谁用」。
- 没挖假设就拍方向。
- 应声虫式地夸弱点子。
- 没有「不做什么」清单。
"""

_SKILL_PLAN = """---
name: 任务拆解
description: 有了明确目标后，把一件大事拆成有序、可验证、能一步步落地的小任务。适用场景：手上有个需求/方案要拆成能执行的步骤；一件事大得无从下手；需要估工作量；或想把活儿安排出先后顺序。不适用：改一个文件就能搞定、范围很明显的小事。
---

# 任务拆解

把活儿拆成「小到能在一次专注里做完并验证」的任务。好的拆解，是「靠谱完成」和「搅成一团乱麻」之间的分界线。

## 怎么拆

### 第一步：先只看不动手
动笔之前先只读不写：看清现状、已有的做法和约定、各部分之间谁依赖谁、哪里有风险和未知。**这一步不要写任何实现**，产出的是一份计划，不是代码。

### 第二步：理清依赖关系
画出「谁依赖谁」。实现顺序顺着依赖自底向上：**先把地基打牢**。

### 第三步：竖着切，别横着切
不要「先把所有数据层做完，再做所有界面」。而是一次做通一条完整的功能路径。
- 横着切（不好）：任务1做完整个数据库 → 任务2做完所有接口 → 任务3做完所有界面 → 任务4连起来。
- 竖着切（好）：任务1「用户能注册」（这条路的数据+接口+界面）→ 任务2「用户能登录」→ ……
每一条竖切都交付一块能跑、能测的功能。

### 第四步：写任务
每个任务长这样：
```markdown
## 任务 N：〔简短标题〕
说明：一段话讲清这个任务要达成什么。
验收标准：
- [ ] 〔具体、可检验的条件〕
怎么验：
- [ ] 〔跑什么 / 看什么，能确认它成了〕
依赖：〔依赖哪几个任务，或「无」〕
预计规模：〔小：1–2 处｜中：3–5 处｜大：5 处以上〕
```

### 第五步：排序 + 设检查点
排任务时保证：依赖先满足；每做完一个系统都还是能跑的状态；每 2–3 个任务设一个检查点；高风险的任务尽量往前放（早暴露问题）。

## 任务大小参考
| 大小 | 范围 | 例子 |
|---|---|---|
| 极小 | 改一处 | 加一条校验规则 |
| 小 | 一个组件/接口 | 加一个接口 |
| 中 | 一条功能竖切 | 注册流程 |
| 大 | 多组件功能 | 带筛选和翻页的搜索 |
| 超大 | **太大了，继续拆** | — |

**什么时候要再拆**：一次专注做不完；验收标准写不进 3 条以内；标题里出现了「和」（通常是两个任务）。

## 容易自我欺骗的地方
| 借口 | 实际 |
|---|---|
| 「边做边想」 | 这就是搅成一团的来路。十分钟规划省几小时。 |
| 「任务很明显」 | 也写下来。写出来才会暴露隐藏依赖和忘掉的边界情况。 |
| 「规划是额外开销」 | 规划本身就是活儿的一部分。没计划的实现只是打字。 |

## 红线
- 没写任务清单就开干。
- 任务只写「实现这个功能」，没有验收标准。
- 计划里没有「怎么验」。
- 所有任务都是超大号。
- 任务之间没有检查点、没考虑依赖顺序。
"""

_SKILL_DEBUG = """---
name: 排查问题
description: 出问题时（报错、结果不对、原本好的突然坏了、某步失败）用系统化的方法找到根因再修，而不是瞎猜乱试。适用场景：跑出来不对、报错、装东西失败、某个操作半路挂了、之前能用现在不能用。不适用：一眼能看出原因的小笔误。
---

# 排查问题

系统化地查问题：出岔子时先停手、保住现场、按顺序排查、修根因、防复发。瞎猜最浪费时间。

## 停线规则
一旦出现意料之外的情况：
1. **停**：先别继续往下做、别再加新东西。
2. **保现场**：把报错原文、日志、复现步骤留好。
3. **诊断**：按下面的清单走。
4. **修根因**：不是修表面症状。
5. **设防**：加一道防线，避免再犯。
6. **验证通过后再继续。**
不要带着一个没修的错往下做——错误会滚雪球，前面一个没查清，后面全都建在错的基础上。

## 排查清单（按顺序，别跳步）

### 第一步：复现
让问题**稳定地**重现。复现不了就没法有把握地修。
- 复现不了时，分情况：
  - 跟时机有关？→ 在可疑位置打上带时间戳的日志；故意加点延迟把竞争窗口放大。
  - 跟环境有关？→ 比对版本、系统、配置、数据（空库 vs 有数据）。
  - 跟状态有关？→ 查是不是上一次操作留下的脏状态、共享缓存、全局变量。
  - 真随机？→ 在可疑点加防御性日志，给这个特定错误设个告警，记下观察到的条件，等它再犯。

### 第二步：定位
缩小问题**发生在哪一层**：界面？后端？数据？配置/依赖？外部服务？还是判断本身就错了（误报）？
对「之前好、现在坏」的回归问题，用二分法：在已知好和已知坏之间对半砍，逐步逼近是哪次改动引入的。

### 第三步：缩小
做出**最小的能复现的例子**：把无关的代码/配置一点点去掉，直到只剩 bug 本身；把输入简化到能触发问题的最小样子。最小复现一出来，根因往往就一目了然，也能避免「修了症状没修病根」。

### 第四步：找根因（别停在第一个看到的现象）
连问几个「为什么」，往下挖：
> 报错 → 为什么报这个错 → 因为某个值是空 → 为什么是空 → 因为上一步没赋值 → 为什么没赋值 → ……
挖到「改这里能让问题彻底不发生」的那一层，才是根因。

### 第五步：修 + 设防
修根因。然后加一道防线让它不会再悄悄回来：补一个能覆盖这个情况的检查/测试、或加一个守卫条件。**先写一个能复现 bug 的检查，确认它「红」，再修到它「绿」**——这样你才知道是真修好了，也防止以后复发。

## 红线
- 不复现就开始改。
- 连续改好几处「碰运气」，每次都没验证。
- 修了表面症状（让报错消失）却没碰根因。
- 修完不补一道防线，下次照样犯。
"""

# ====================================================================
# 从对话提炼技能：读一段你和小助的对话，解析「这次做的事 + 怎么操作的」，
# 总结成一个可复用的技能（不直接保存，交给界面让你确认/编辑后再存）。
# ====================================================================

_EXTRACT_PROMPT = """下面是一段「我」和 AI 助手「超能小助」的对话。请你从中提炼出一个**可复用的技能**——
也就是把这次「我想做的事」「小助是怎么一步步操作/解决的」总结成一套以后遇到同类任务能照着做的方法。

要求：
1. 只提炼真正有方法、有步骤、值得复用的东西。如果这段对话只是闲聊、问答，没有可复用的做事流程，就只回复一行：无。
2. 用下面的**固定格式**输出，不要有多余的话、不要用代码块包起来：

名字：<给这个技能起一个简短的中文名，比如「视频转文案」「竞品调研」>
SLUG：<一个英文 slug，只用小写字母/数字/连字符，比如 video-to-copy>
适用场景：<一句话写清「遇到哪类任务就用它」，最好再补一句「不适用：...」。这句最关键，小助靠它判断何时用。>
正文：
<这个技能的具体步骤，用 Markdown。分「## 第一步 / ## 第二步」写成可执行的清单，把这次小助实际用到的做法、工具、注意点写进去。越具体越好。可以加一段「## 红线」列几个不要这么做。>

=== 对话开始 ===
{conv}
=== 对话结束 ===
"""


def _parse_extracted(text: str):
    """把模型按固定格式产出的技能解析成 dict。失败返回 None。"""
    t = (text or "").strip()
    if not t or t.strip() in ("无", "无。"):
        return None
    name, slug, desc = "", "", ""
    body_lines = []
    in_body = False
    for line in t.splitlines():
        if in_body:
            body_lines.append(line)
            continue
        s = line.strip()
        if s.startswith("名字："):
            name = s[3:].strip()
        elif s.lower().startswith("slug：") or s.upper().startswith("SLUG："):
            slug = s.split("：", 1)[1].strip() if "：" in s else ""
        elif s.startswith("适用场景："):
            desc = s[5:].strip()
        elif s.startswith("正文："):
            in_body = True
            tail = s[3:].strip()
            if tail:
                body_lines.append(tail)
    body = "\n".join(body_lines).strip()
    if not slug:
        slug = _slugify(name)
    slug = _safe_slug(slug) or _slugify(name)
    if not (name or body):
        return None
    return {"name": name or slug, "slug": slug, "description": desc, "body": body}


def extract_skill_from_conversation(client, model, messages):
    """用模型从对话里提炼一个技能草稿。返回 dict（name/slug/description/body）或 None。
    不保存——交给界面让用户确认编辑后再调 save_skill。"""
    # 复用 conversation_memory 的对话拼接（没有也能降级）
    try:
        import conversation_memory as cm
        conv = cm._conversation_text(messages)
    except Exception:
        parts = []
        for m in messages or []:
            role = m.get("role"); content = (m.get("content") or "").strip()
            if role == "user" and content:
                parts.append("用户：" + content)
            elif role == "assistant" and content:
                parts.append("助手：" + content)
        conv = "\n".join(parts)
    if not conv.strip():
        return None
    if len(conv) > 8000:
        conv = conv[-8000:]  # 太长只取后半段，省 token
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(conv=conv)}],
        )
        out = (resp.choices[0].message.content or "").strip()
    except Exception:
        return None
    return _parse_extracted(out)


BUILTIN_SKILLS = {
    "interview-me": _SKILL_INTERVIEW,
    "idea-refine": _SKILL_IDEA,
    "planning-task-breakdown": _SKILL_PLAN,
    "debugging": _SKILL_DEBUG,
}
