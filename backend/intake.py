"""超能小助 · 加工：认出放进来的是什么，按种类用不同的办法处理（v112）

「加工」页（原来的「视频」页）的输入框什么都能放：
  · 视频链接、文章 / 网页链接、本地文件 → 照原来的流程（server.py 的提取队列）
  · GitHub 项目 → 读仓库信息和 README，摘出安装方法，整理成一条笔记，放进「GitHub 项目」文件夹
  · 一段文字（没有链接）→ 直接存成一条笔记，放进「随手记」文件夹
classify() 认种类；describe() 给输入框下面那行提示用；research_github_url() / text_note()
返回和其它提取一样的结果字典（ok / title / transcript / source / doc_kind …），后面的保存流程不用改。
"""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

GH_FOLDER = "GitHub 项目"
TEXT_FOLDER = "随手记"

# github.com 下面这些不是「用户名/项目名」
_GH_RESERVED = {
    "orgs", "topics", "settings", "marketplace", "explore", "features", "sponsors", "about", "login",
    "join", "notifications", "search", "trending", "collections", "apps", "pricing", "enterprise",
    "security", "site", "contact", "customer-stories", "readme", "issues", "pulls", "codespaces",
    "new", "organizations", "account", "dashboard", "events", "gist", "users",
}


class GhError(Exception):
    pass


_LIMIT_MSG = "GitHub 暂时不让查了（不登录每小时最多 60 次），过一会儿再试"


def _raw_readme(owner, repo):
    """GitHub 接口被限流时：直接下 README 文件（raw.githubusercontent.com 不算在那 60 次里）。"""
    px = _proxy()
    for name in ("README.md", "readme.md", "README.MD", "README.rst", "README.txt", "README"):
        url = "https://raw.githubusercontent.com/%s/%s/HEAD/%s" % (owner, repo, name)
        for p in ([px, ""] if px else [""]):
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p} if p else {}))
                with opener.open(urllib.request.Request(url, headers={"User-Agent": "super-assistant"}), timeout=20) as r:
                    return r.read(3 * 1024 * 1024).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break          # 没有这个文件名，换下一个
            except Exception:
                continue
    return ""


def _first_url(text):
    try:
        import doc_import
        return doc_import.first_url(text)
    except Exception:
        m = re.search(r"https?://[^\s<>\"'，。！？、；：（）()【】《》「」]+", text or "")
        return m.group(0).rstrip(".,;:!?)]}>'\"") if m else ""


def github_repo(text):
    """文字里第一个链接是 GitHub 项目 → (用户名, 项目名)；不是 → None。"""
    url = _first_url(text)
    if not url:
        return None
    try:
        p = urllib.parse.urlparse(url)
    except Exception:
        return None
    if (p.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    parts = [x for x in (p.path or "").split("/") if x]
    if len(parts) < 2 or parts[0].lower() in _GH_RESERVED:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    ok = re.compile(r"[A-Za-z0-9_.-]+")
    if not ok.fullmatch(owner) or not ok.fullmatch(repo):
        return None
    return owner, repo


def local_path(text):
    """放进来的是电脑上一个存在的文件 / 文件夹的完整路径 → 返回路径；不是 → 空串。"""
    t = (text or "").strip().strip('"').strip("'").strip()
    if not t or "\n" in t or len(t) > 400:
        return ""
    if re.match(r"^[A-Za-z]:[\\/]", t) or t.startswith("\\\\") or t.startswith("/"):
        try:
            if os.path.isfile(t):
                return t
        except Exception:
            return ""
    return ""


MEDIA_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv", ".webm", ".m4v", ".ts", ".mts", ".3gp", ".mpg",
              ".mpeg", ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".opus", ".flac", ".wma", ".amr"}


def _clean_path(line):
    return (line or "").strip().strip('"').strip("'").strip()


def paths_in(text):
    """v118：放进来的每一行都是电脑上存在的文件 / 文件夹 → 返回这些路径；不是 → []。"""
    lines = [_clean_path(x) for x in (text or "").splitlines() if x.strip()]
    if not lines or len(lines) > 200:
        return []
    out = []
    for p in lines:
        if not (re.match(r"^[A-Za-z]:[\\/]", p) or p.startswith("\\\\") or p.startswith("/")):
            return []
        try:
            if not os.path.exists(p):
                return []
        except Exception:
            return []
        out.append(p)
    return out


def _supported(path):
    if os.path.splitext(path)[1].lower() in MEDIA_EXTS:
        return True
    try:
        import doc_import
        return bool(doc_import.is_doc_path(path))
    except Exception:
        return False


def scan_paths(paths, max_files=500, max_depth=4):
    """v118：把拖进来 / 粘进来的文件和文件夹展开成能提取的文件清单（文件夹往下找 4 层，最多 500 个）。"""
    files, dirs = [], []
    def walk(d, depth):
        if depth > max_depth or len(files) >= max_files:
            return
        try:
            ents = sorted(os.listdir(d))
        except Exception:
            return
        for n in ents:
            if n.startswith(".") or len(files) >= max_files:
                continue
            f = os.path.join(d, n)
            if os.path.isdir(f):
                walk(f, depth + 1)
            elif _supported(f):
                files.append(f)
    for p in paths or []:
        p = _clean_path(p)
        if not p:
            continue
        if os.path.isdir(p):
            dirs.append(p)
            walk(p, 0)
        elif os.path.isfile(p) and _supported(p) and len(files) < max_files:
            files.append(p)
    name = os.path.basename(dirs[0].rstrip("\\/")) if len(dirs) == 1 and len(paths or []) == 1 else ""
    return {"files": files, "name": name, "count": len(files), "dirs": len(dirs)}


_SEARCH = re.compile(r"^\s*(?:搜索|搜|查找|找)\s*[:：\s]\s*(\S.*)$", re.S)


def search_query(text):
    """v118：「搜：AI 芯片」「找：跨境电商」这样开头的 → 返回要搜的领域；不是 → 空串。"""
    m = _SEARCH.match(text or "")
    if not m or "\n" in m.group(1).strip() or len(m.group(1).strip()) > 60:
        return ""
    return m.group(1).strip()


_CHAT_START = re.compile(
    r"^(你好|您好|hi\b|hello|hey|嗨|哈喽|在吗|在不在|早上好|上午好|中午好|下午好|晚上好|早安|晚安|谢谢|多谢|感谢|"
    r"帮我|帮忙|请你|请帮|麻烦你|麻烦帮|给我|告诉我|你能|你会|你是|你觉得|能不能|能否|可不可以|可以帮|"
    r"怎么|怎样|如何|为什么|为啥|什么是|啥是|有没有|是不是|小助)", re.I)


def looks_chat(text):
    """v120：一句打招呼、提问、请小助帮忙的话 → 当聊天（发到对话里），不存成笔记。"""
    t = (text or "").strip()
    if not t or "\n" in t or len(t) > 60:
        return False
    if _CHAT_START.match(t):
        return True
    return bool(re.search(r"[?？]$", t) or re.search(r"(吗|呢|么)[?？!！。.~～]*$", t))


def classify(text):
    """'paths' | 'file' | 'search' | 'github' | 'article' | 'video' | 'text' | ''（空的）"""
    t = (text or "").strip()
    if not t:
        return ""
    ps = paths_in(t)
    if ps:
        return "file" if (len(ps) == 1 and os.path.isfile(ps[0])) else "paths"
    if search_query(t):
        return "search"
    if local_path(t):
        return "file"
    if github_repo(t):
        return "github"
    if _first_url(t):
        try:
            import doc_import
            return "article" if doc_import.article_url(t) else "video"
        except Exception:
            return "video"
    if looks_chat(t):
        return "chat"
    return "text" if len(t) >= 2 else ""


_DESC = {
    "video": ("视频", "提取文字稿（平台有字幕就直接用字幕），存成笔记，归到博主下面"),
    "article": ("文章 / 网页", "读出正文存成笔记；页面里有视频的，可以一键接着提取"),
    "github": ("GitHub 项目", "读项目信息和 README，整理出安装方法，放进「%s」文件夹；之后可以一键让小助帮你装" % GH_FOLDER),
    "text": ("一段文字", "直接存成一条笔记，放进「%s」文件夹；需要时再点「AI 分析」" % TEXT_FOLDER),
    "file": ("本地文件", "音视频提取文字稿；PDF、Word、Excel 等文档读出全文"),
    "paths": ("文件 / 文件夹", "找出里面所有音视频和文档（包括子文件夹），逐个提取"),
    "chat": ("聊天", "按回车就发到「对话」里和小助聊（不存成笔记）"),
    "search": ("搜索推荐", "让 AI 联网找这个领域最值得关注的博主和网站，挑好了一键加进嗅探"),
}


def describe(text):
    k = classify(text)
    if not k:
        return {"kind": ""}
    label, hint = _DESC[k]
    out = {"kind": k, "label": label, "hint": hint}
    if k == "search":
        out["query"] = search_query(text)
    return out


def text_title(text):
    first = next((ln.strip() for ln in (text or "").split("\n") if ln.strip()), "")
    first = re.sub(r"[#*>`_~|]", "", first).strip()
    return first[:40] or "一段文字"


def _demote(md):
    """把 Markdown 标题（代码块外的 # 开头行）改成加粗行：笔记自己的结构靠「## 」分段，别被搅乱。"""
    out, fence = [], False
    for ln in (md or "").split("\n"):
        if ln.lstrip().startswith("```"):
            fence = not fence
            out.append(ln)
            continue
        if not fence:
            m = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", ln)
            if m:
                out.append("**%s**" % m.group(1))
                continue
        out.append(ln)
    return "\n".join(out)


def text_note(text):
    t = (text or "").strip()
    if not t:
        return {"ok": False, "error": "放进来的文字是空的"}
    return {"ok": True, "source": "doc", "doc_kind": "文字", "title": text_title(t), "uploader": "",
            "url": "（粘贴的文字）", "transcript": _demote(t)}


# ════════════════ GitHub 项目 ════════════════

def _proxy():
    try:
        import doc_import
        return doc_import._proxy() or ""
    except Exception:
        return ""


def _api(path, timeout=20):
    """GET api.github.com；设了代理先走代理，不通再直连。404 → None。"""
    url = "https://api.github.com" + path
    headers = {"User-Agent": "super-assistant", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    tok = (os.environ.get("GITHUB_TOKEN") or "").strip()   # 可选：设了就不受每小时 60 次的限制
    if tok:
        headers["Authorization"] = "Bearer " + tok
    px = _proxy()
    last = None
    for p in ([px, ""] if px else [""]):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p} if p else {}))
            with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429):
                raise GhError(_LIMIT_MSG)
            last = e
        except Exception as e:
            last = e
    msg = str(last) or type(last).__name__
    if not px:
        msg += "（打不开 GitHub 的话，在「设置 → 联网与代理」里填上代理）"
    raise GhError("连不上 GitHub：" + msg[:200])


_INSTALL_HEAD = re.compile(
    r"install|setup|getting\s*started|quick\s*-?\s*start|usage|build|deploy|"
    r"安装|部署|快速开始|快速上手|开始使用|使用方法|使用说明|编译|运行", re.I)
_CMD = re.compile(
    r"^\s*(\$\s*)?(pip3?|pipx|uv|conda|npm|npx|pnpm|yarn|bun|git\s+clone|docker(-compose)?|brew|cargo|"
    r"go\s+(install|get|run)|apt(-get)?|make|cmake|python3?|winget|choco|scoop)\b", re.I | re.M)


def install_sections(md, limit=6000):
    """从 README 里摘出「安装 / 快速开始 / 使用」这几节；没有这些小节就挑像安装命令的代码块。"""
    lines = (md or "").split("\n")
    heads, fence = [], False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", ln)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    picked = []
    for n, (i, lv, txt) in enumerate(heads):
        if not _INSTALL_HEAD.search(txt):
            continue
        if any(a <= i < b for a, b in picked):   # 已经在前面摘过的大节里
            continue
        end = len(lines)
        for j, lv2, _ in heads[n + 1:]:
            if lv2 <= lv:
                end = j
                break
        picked.append((i, end))
        if sum(b - a for a, b in picked) > 400:
            break
    text = "\n\n".join("\n".join(lines[a:b]).strip() for a, b in picked).strip()
    if not text:
        blocks = re.findall(r"```[^\n]*\n(.*?)```", md or "", re.S)
        cmds = [b.strip() for b in blocks if _CMD.search(b)][:4]
        text = "\n\n".join("```\n%s\n```" % b for b in cmds)
    return text[:limit]


_TYPES = [("package.json", "Node.js"), ("requirements.txt", "Python"), ("pyproject.toml", "Python"),
          ("setup.py", "Python"), ("Cargo.toml", "Rust"), ("go.mod", "Go"), ("pom.xml", "Java（Maven）"),
          ("build.gradle", "Java / Kotlin（Gradle）"), ("CMakeLists.txt", "C / C++（CMake）"),
          ("Gemfile", "Ruby"), ("composer.json", "PHP"), ("Dockerfile", "能用 Docker 跑"),
          ("docker-compose.yml", "带 docker-compose"), ("compose.yaml", "带 docker-compose")]


def _project_types(files):
    names = set(files or [])
    out = []
    for f, label in _TYPES:
        if f in names and label not in out:
            out.append(label)
    if any(n.endswith((".sln", ".csproj")) for n in names):
        out.append(".NET")
    return out


def _num(n):
    try:
        return "{:,}".format(int(n))
    except Exception:
        return str(n or 0)


def research_github_url(url, progress_cb=None):
    gr = github_repo(url)
    if not gr:
        return {"ok": False, "error": "这不是 GitHub 项目地址（要像 https://github.com/用户名/项目名 这样）"}
    return research_github(gr[0], gr[1], progress_cb)


def research_github(owner, repo, progress_cb=None):
    cb = progress_cb or (lambda *a: None)
    try:
        cb("读取项目", "读 GitHub 上 %s/%s 的项目信息…" % (owner, repo))
        try:
            info = _api("/repos/%s/%s" % (owner, repo))
        except GhError as e:
            if str(e) != _LIMIT_MSG:
                raise
            # 被限流：基本信息拿不到，README 照样能读
            cb("读取项目", "GitHub 接口限流了，直接读 README 文件…")
            readme = _raw_readme(owner, repo)
            if not readme:
                raise
            info = {"full_name": "%s/%s" % (owner, repo), "_limited": True}
        if not info:
            return {"ok": False, "error": "GitHub 上找不到 %s/%s（可能是私有项目，或者地址写错了）" % (owner, repo)}
        full = info.get("full_name") or "%s/%s" % (owner, repo)
        cb("读取项目", "读 README…")
        readme = readme if info.get("_limited") else ""
        rd = None if info.get("_limited") else _api("/repos/%s/readme" % full)
        if rd and rd.get("content"):
            try:
                readme = base64.b64decode(rd["content"]).decode("utf-8", "replace")
            except Exception:
                readme = ""
        rel, files = None, []
        try:
            if info.get("_limited"):
                raise GhError(_LIMIT_MSG)
            rel = _api("/repos/%s/releases/latest" % full)
            lst = _api("/repos/%s/contents" % full)
            if isinstance(lst, list):
                files = [x.get("name", "") for x in lst if isinstance(x, dict)]
        except GhError:
            pass
    except GhError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": "读 GitHub 项目出错：%s" % str(e)[:200]}

    cb("整理", "摘出安装方法…")
    desc = (info.get("description") or "").strip()
    topics = [t for t in (info.get("topics") or []) if t][:8]
    lic = ((info.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", "其它")
    if info.get("_limited"):
        meta = ["- 项目地址：https://github.com/%s" % full,
                "- 这次 GitHub 接口限流了，Star、语言、版本这些没取到；README 是直接下载的，内容完整"]
        info = dict(info, pushed_at="")
    else:
        meta = None
    meta = meta or ["- 项目地址：https://github.com/%s" % full,
            "- 主要语言：%s ｜ Star %s ｜ Fork %s%s" % (info.get("language") or "未标注", _num(info.get("stargazers_count")),
                                                   _num(info.get("forks_count")), (" ｜ 许可证：" + lic) if lic else "")]
    if not info.get("_limited"):
        upd = "- 最近更新：%s" % (info.get("pushed_at") or "")[:10]
        if rel and rel.get("tag_name"):
            upd += " ｜ 最新版本：%s（%s）" % (rel["tag_name"], (rel.get("published_at") or "")[:10])
        meta.append(upd)
    types = _project_types(files)
    if types:
        meta.append("- 项目类型：" + "、".join(types))
    if topics:
        meta.append("- 话题：" + "、".join(topics))
    if info.get("homepage"):
        meta.append("- 项目主页：%s" % info["homepage"])
    if info.get("archived"):
        meta.append("- 注意：这个项目已经归档，作者不再维护了")
    inst = install_sections(readme)
    parts = ["**一句话介绍**", "", desc or "（作者没写简介）", "", "**基本信息**", ""] + meta + [
        "", "**安装和使用（从 README 里摘的，原样照抄）**", "",
        _demote(inst) if inst else "README 里没找到写明的安装步骤，看下面的 README 原文。",
        "", "**README 原文**", "", _demote(readme) if readme else "（这个项目没有 README）"]
    title = full + ("：" + desc if desc else "")
    return {"ok": True, "source": "article", "doc_kind": "GitHub 项目", "title": title[:90],
            "uploader": owner, "url": "https://github.com/" + full, "transcript": "\n".join(parts),
            "platform_tags": topics[:5]}
