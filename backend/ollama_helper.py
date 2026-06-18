"""
ollama_helper.py — Ollama 模型列表 / 连接检查 / 自动启动

给三件事用：
1. 列出本地已装的模型（界面下拉选择用）
2. 检查 Ollama 服务是否在运行
3. 没运行就尝试自动拉起 ollama serve

只管本地 Ollama；云端模型不需要这些。
"""

import json
import time
import shutil
import subprocess
import urllib.request

OLLAMA_API = "http://localhost:11434"


def is_running():
    """Ollama 服务是否在跑。"""
    try:
        with urllib.request.urlopen(OLLAMA_API + "/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_models():
    """列出可用的模型名（本地已装 + 已登录的云端模型）。
    /api/tags 给出本地已装的；再用 `ollama list` CLI 兜底，能多抓到
    一些云端（:cloud）模型。两者合并去重。连不上就返回 []。"""
    names = []

    # 1) HTTP /api/tags（本地已装，含已 pull 的云端模型）
    try:
        with urllib.request.urlopen(OLLAMA_API + "/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for m in data.get("models", []):
            n = m.get("name")
            if n:
                names.append(n)
    except Exception:
        pass

    # 2) CLI `ollama list` 兜底（有时能列出 API 没返回的云端模型）
    try:
        if ollama_installed():
            r = subprocess.run(["ollama", "list"], capture_output=True,
                               text=True, timeout=8)
            for line in (r.stdout or "").splitlines()[1:]:  # 跳过表头
                parts = line.split()
                if parts and "/" not in parts[0]:
                    names.append(parts[0])
    except Exception:
        pass

    # 去重保序
    seen = set()
    out = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def known_cloud_models():
    """常见的 Ollama 云端模型名（带 :cloud / -cloud 后缀）。
    云端模型不出现在本地 /api/tags 里，这里给一份常用清单，
    用户登录 Ollama（ollama signin）后即可直接选用。"""
    return [
        "gpt-oss:120b-cloud",
        "gpt-oss:20b-cloud",
        "qwen3.5:397b-cloud",
        "kimi-k2.5:cloud",
        "glm-5:cloud",
        "minimax-m2.7:cloud",
        "gemma4:31b-cloud",
        "deepseek-v3.1:671b-cloud",
    ]


def ollama_installed():
    """系统里有没有装 ollama 命令。"""
    return shutil.which("ollama") is not None


def try_start():
    """尝试后台拉起 ollama serve。返回是否最终连上。"""
    if is_running():
        return True
    if not ollama_installed():
        return False
    try:
        # 后台启动，不阻塞
        creationflags = 0
        kwargs = {}
        import sys
        if sys.platform == "win32":
            # Windows 下不弹窗
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            kwargs["creationflags"] = creationflags
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         **kwargs)
    except Exception:
        return False
    # 等它起来，最多等 ~10 秒
    for _ in range(20):
        if is_running():
            return True
        time.sleep(0.5)
    return False


def environment_check(use_local=True, model="qwen2.5"):
    """
    检查运行环境，返回一份结构化结果给界面显示。
    """
    result = {"items": [], "ok": True}

    def add(name, ok, detail):
        result["items"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            result["ok"] = False

    # ★ 网页模型：它不走 Ollama 也不走 OPENAI_API_KEY，
    #   所以单独检查它的依赖（Playwright）和账号配置，检查通过就算「环境就绪」。
    #   （否则会去 Ollama 里找名为 'web' 的模型，永远找不到 → 右上角一直红点。）
    is_web = False
    try:
        import agent_core
        is_web = agent_core.is_web_model(model)
    except Exception:
        is_web = (model == "web")
    if is_web:
        try:
            import web_model
            if web_model.is_available():
                add("Playwright（网页模型依赖）", True, "已安装")
            else:
                err = ""
                try:
                    err = str(web_model.playwright_import_error() or "")
                except Exception:
                    pass
                add("Playwright（网页模型依赖）", False,
                    "未安装：pip install playwright && python -m playwright install chromium"
                    + (("（%s）" % err) if err else ""))
            cfg = web_model.load_config()
            if cfg.get("aiUsername") and cfg.get("aiPassword"):
                add("网页模型账号", True, "已配置（%s）" % cfg.get("aiUsername"))
            else:
                add("网页模型账号", False,
                    "请在「设置 → 网页模型」里填写 sorryios 账号和密码")
        except Exception as e:
            add("网页模型", False, "检查出错：%s" % e)
        # 记忆/提醒/笔记等本机动作仍用本地模型，但即使没装也只是这些功能受影响，
        # 不影响网页模型本身，所以这里不因为 Ollama 没装而判整体「环境有问题」。
        return result

    # ★ Claude 模型（claude / claude::N）：走 Claude API，不依赖 Ollama 也不依赖 OPENAI_API_KEY。
    #   只检查它自己的配置（是否填了 key、SDK 是否装好），不要去启动 Ollama（会卡 UI），
    #   也不要因为没装 Ollama 就判红灯。
    is_claude = (model == "claude") or (str(model).startswith("claude::"))
    if is_claude:
        try:
            import claude_client
            # 解析具体配置
            idx = None
            if str(model).startswith("claude::"):
                try:
                    idx = int(str(model).split("::")[1])
                except (ValueError, IndexError):
                    idx = None
            profiles = claude_client.load_profiles()
            prof = None
            if idx is not None and 0 <= idx < len(profiles):
                prof = profiles[idx]
            elif profiles:
                prof = profiles[0]
            if prof and prof.get("api_key"):
                add("Claude 配置「%s」" % (prof.get("name") or "未命名"), True,
                    "已配置 key，模型：%s" % prof.get("model", "?"))
            else:
                add("Claude 配置", False, "还没填 API Key，请到「设置 → Claude 模型管理」添加")
            # 检查对应的 SDK 是否装好
            base_url = (prof or {}).get("base_url", "")
            official = claude_client._is_official(base_url)
            if official:
                if claude_client.sdk_available():
                    add("anthropic 库", True, "已安装")
                else:
                    add("anthropic 库", False, "未安装：pip install anthropic")
            else:
                if claude_client.openai_sdk_available():
                    add("openai 库", True, "已安装")
                else:
                    add("openai 库", False, "未安装：pip install openai")
        except Exception as e:
            add("Claude", False, "检查出错：%s" % e)
        return result

    # openai 库（本地/云端模型才需要）
    try:
        import openai  # noqa
        add("Python openai 库", True, "已安装")
    except Exception:
        add("Python openai 库", False, "未安装，请运行 pip install openai")

    if use_local:
        # Ollama 是否装了
        if ollama_installed():
            add("Ollama 程序", True, "已安装")
        else:
            add("Ollama 程序", False, "未安装，去 ollama.com 下载")

        # Ollama 是否在跑（没跑就尝试启动）
        running = is_running()
        if not running:
            running = try_start()
        if running:
            add("Ollama 服务", True, "运行中")
        else:
            add("Ollama 服务", False, "未运行，且自动启动失败")

        # 模型是否存在
        if running:
            models = list_models()
            # ollama 的模型名可能带 :latest，做个宽松匹配
            base = model.split(":")[0]
            found = any(m == model or m.split(":")[0] == base for m in models)
            if found:
                add(f"模型 {model}", True, "已就绪")
            else:
                add(f"模型 {model}", False,
                    f"本地没有，已装的是：{', '.join(models) or '无'}")
    else:
        import os
        if os.environ.get("OPENAI_API_KEY"):
            add("OPENAI_API_KEY", True, "已设置")
        else:
            add("OPENAI_API_KEY", False, "云端模式需要设置此环境变量")

    return result
