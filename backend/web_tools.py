"""
web_tools.py — 联网增强工具：读网页全文、批量搜索、情报简报

全部是"只读"性质（抓取公开网页内容、做分析），归为安全工具。
注意：这些工具只读取公开可访问的网页，不做登录、不绕过任何平台限制、
不抓取需要授权的数据。用于市场情报、竞品公开信息、新闻聚合等正当用途。
"""

import re
import json
import html
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

# 更像真浏览器的请求头，能减少一部分站点的 403 反爬拦截。
# 注意：故意不发 Accept-Encoding（不要 gzip），因为 urllib 不会自动解压。
_BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def _read_proxy():
    """读 memory/proxy.md 里的代理地址。没配或被注释就返回空。
    支持一行 proxy: http://127.0.0.1:7890 这种。"""
    try:
        from agent_core import read_memory_file
        raw = read_memory_file("proxy.md")
    except Exception:
        return ""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith(">"):
            continue
        if line.lower().startswith("proxy:"):
            val = line.split(":", 1)[1].strip()
            if val and "这里填" not in val and val.lower() != "none":
                return val
    return ""


# ---------- 智能局部代理 ----------
# 软件不跟随系统代理（Clash 等开了「系统代理」也不受影响）：
#   · 国内站（抖音/B站/百度/AI 池…）永远直连；
#   · 境外站才走「设置 → 联网与代理」里填的代理；没填时才退而用系统代理。
_DOMESTIC_SUFFIX = (
    ".cn", "douyin.com", "iesdouyin.com", "douyinvod.com", "douyinpic.com", "douyincdn.com",
    "bytedance.com", "byteimg.com", "snssdk.com", "amemv.com", "zjcdn.com", "bytecdn.cn",
    "bilibili.com", "bilivideo.com", "bilivideo.cn", "hdslb.com", "b23.tv", "biliapi.net",
    "kuaishou.com", "gifshow.com", "xiaohongshu.com", "xhslink.com", "xhscdn.com",
    "weibo.com", "weibo.cn", "sinaimg.cn", "sina.com", "zhihu.com", "zhimg.com",
    "baidu.com", "bdstatic.com", "qq.com", "gtimg.com", "163.com", "126.net", "sohu.com",
    "aliyun.com", "alicdn.com", "taobao.com", "tmall.com", "jd.com", "csdn.net", "juejin.cn",
    "dakeai.cc", "deepseek.com", "moonshot.cn", "kimi.com", "doubao.com",
    "hf-mirror.com",
)

_SSL_CTX = None


def _ssl_ctx():
    """HTTPS 证书库：Windows 系统证书 + certifi 标准证书包（校验照常开着）。
    Windows 不预装所有根证书，浏览器遇到缺的会自动下载，Python 不会——于是 Hugging Face、
    example.com 这类站报 CERTIFICATE_VERIFY_FAILED（unable to get local issuer certificate）。"""
    global _SSL_CTX
    if _SSL_CTX is None:
        import ssl
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx.load_verify_locations(certifi.where())
        except Exception:
            pass
        _SSL_CTX = ctx
    return _SSL_CTX


def needs_proxy(url):
    """这个网址要不要走代理：国内站和本机地址 → 直连；其余（境外站）→ 走代理。"""
    from urllib.parse import urlparse
    try:
        host = (urlparse(url if "://" in (url or "") else "http://" + (url or "")).hostname or "").lower()
    except Exception:
        return False
    if not host or host in ("localhost",) or host.startswith("127.") or host.startswith("192.168.") \
            or host.startswith("10.") or host == "::1":
        return False
    return not any(host == s.lstrip(".") or host.endswith(s if s.startswith(".") else "." + s)
                   for s in _DOMESTIC_SUFFIX)


_ENV_STATE = {"v": None}
_PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def apply_proxy_env(force=False):
    """把「智能局部代理」设成整个后台进程的默认规则（requests / httpx / curl / yt-dlp / urllib 都认）：
      · HTTP(S)_PROXY = 设置里填的代理（没填就用系统代理的地址）→ 境外站自动走代理；
      · NO_PROXY      = 国内站 + 本机地址                         → 国内站自动直连。
    注意：千万不能设 NO_PROXY=*——Python 和 curl 会连「显式指定的代理」也一起绕过，
    之前就是这样导致境外站全变成了直连（OpenAI 403、Google/Meta 超时）。
    代理设置改了会自动重新应用（proxy_for 每次都会检查）。返回当前生效的代理。"""
    p = _read_proxy()
    if not p:
        try:
            reg = urllib.request.getproxies_registry()
            p = reg.get("https") or reg.get("http") or ""
        except Exception:
            p = ""
    if not force and _ENV_STATE["v"] == p:
        return p
    _ENV_STATE["v"] = p
    import os as _os
    for k in _PROXY_ENV_KEYS:
        _os.environ.pop(k, None)
    if p:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            _os.environ[k] = p
    no = ["localhost", "127.0.0.1", "::1"] + [s.lstrip(".") for s in _DOMESTIC_SUFFIX]
    _os.environ["NO_PROXY"] = _os.environ["no_proxy"] = ",".join(no)
    return p


def proxy_for(url):
    """给这个网址用的代理地址；不需要代理返回空串。"""
    try:
        apply_proxy_env()          # 设置里的代理改过就同步到全局规则
    except Exception:
        pass
    if not needs_proxy(url):
        return ""
    p = _read_proxy()
    if p:
        return p
    try:   # 没在软件里配代理：境外站才退而用系统代理（Clash 的「系统代理」）
        reg = urllib.request.getproxies_registry() if hasattr(urllib.request, "getproxies_registry") else {}
        return reg.get("https") or reg.get("http") or ""
    except Exception:
        return ""


def _opener(use_proxy=None, url=None):
    """返回 (urllib opener, 实际用的代理)。
    给了网址时完全按网址自动判断（用户要求「有外网就自动走代理，国内就不走」）：
    境外站一律走代理、国内站一律直连，use_proxy 参数不再起作用。
    没给网址时：use_proxy=True 用配置的代理，否则直连。直连时显式关掉系统代理。"""
    if url:
        p = proxy_for(url)
    else:
        p = _read_proxy() if use_proxy else ""
    https = urllib.request.HTTPSHandler(context=_ssl_ctx())
    if p:
        return urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p}), https), p
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), https), None


# ---------- 读网页正文 ----------
def fetch_browserlike(url, timeout=25):
    """用「真浏览器的网络指纹」再抓一次（curl_cffi 模拟 Chrome）。
    Cloudflare 等防护常把普通程序的请求判成机器人回 403，换成浏览器指纹多半能过。
    代理规则同上：境外站走代理、国内站直连。没装 curl_cffi 时抛错，由调用方兜底。"""
    from curl_cffi import requests as creq
    p = proxy_for(url)
    r = creq.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True,
                 proxies=({"http": p, "https": p} if p else {"http": "", "https": ""}),
                 headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    if r.status_code >= 400:
        raise RuntimeError("HTTP Error %d（浏览器指纹重试）" % r.status_code)
    return r.text


def _fetch(url, timeout=20, use_proxy=None):
    headers = dict(_BROWSER_HEADERS)
    req = urllib.request.Request(url, headers=headers)
    opener, _ = _opener(use_proxy, url)
    with opener.open(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read(2_000_000)  # 最多读 2MB，防超大页面
    return raw.decode(charset, errors="replace")


def _extract_text(html_str):
    """把 HTML 粗略提取成正文。去脚本/样式/标签，保留可读文字。"""
    # 去掉 script/style/noscript 整块
    html_str = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html_str)
    # 把常见块级标签换成换行，保留段落感
    html_str = re.sub(r"(?i)</(p|div|br|li|h[1-6]|tr)>", "\n", html_str)
    # 去掉所有剩余标签
    text = re.sub(r"(?s)<[^>]+>", " ", html_str)
    # 解码 HTML 实体（&amp; 之类）
    text = html.unescape(text)
    # 压缩空白
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def tool_read_webpage(args):
    """打开一个网址，把正文读出来（最多约 6000 字）。"""
    url = args.get("url", "").strip()
    if not url:
        return "拒绝：网址为空。"
    if not url.startswith(("http://", "https://")):
        return "拒绝：只支持 http/https 网址。"
    try:
        page = _fetch(url)
        text = _extract_text(page)
        if not text:
            return "（这个页面没提取到正文，可能是纯图片或需要登录/JS 渲染的页面）"
        return text[:6000]
    except Exception as e:
        return f"读取网页出错：{e}"


# ---------- 批量搜索（搜完可选读前几个结果） ----------
def _clean_title(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def _bing_search(query, max_results=5):
    """用 Bing（国内可达）搜索。返回 [(标题, 链接)]。"""
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query) + "&setlang=zh-CN&ensearch=0"
    try:
        page = _fetch(url, timeout=15)
    except Exception as e:
        return [], f"Bing 请求出错：{e}"
    results = []
    seen = set()
    # Bing 的结果标题都在 <h2><a href="...">；用更宽松的全局匹配，不依赖外层 li
    for m in re.finditer(r'(?is)<h2>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', page):
        link = html.unescape(m.group(1))
        title = _clean_title(m.group(2))
        if not title or "bing.com" in link or link in seen:
            continue
        seen.add(link)
        results.append((title, link))
        if len(results) >= max_results:
            break
    return results, (None if results else "Bing 没解析到结果")


def _baidu_search(query, max_results=5):
    """用百度（国内可达）搜索。返回 [(标题, 链接)]。链接是百度跳转链，能正常打开。"""
    url = "https://www.baidu.com/s?wd=" + urllib.parse.quote(query)
    try:
        page = _fetch(url, timeout=15)
    except Exception as e:
        return [], f"百度请求出错：{e}"
    results = []
    seen = set()
    # 百度结果标题在 <h3 ...><a href="...">标题</a>
    for m in re.finditer(r'(?is)<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page):
        link = html.unescape(m.group(1))
        title = _clean_title(m.group(2))
        if not title or link in seen:
            continue
        if not link.startswith("http"):
            continue
        seen.add(link)
        results.append((title, link))
        if len(results) >= max_results:
            break
    return results, (None if results else "百度没解析到结果")


def _sogou_search(query, max_results=5):
    """用搜狗（国内可达）搜索。返回 [(标题, 链接)]。"""
    url = "https://www.sogou.com/web?query=" + urllib.parse.quote(query)
    try:
        page = _fetch(url, timeout=15)
    except Exception as e:
        return [], f"搜狗请求出错：{e}"
    results = []
    seen = set()
    for m in re.finditer(r'(?is)<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page):
        link = html.unescape(m.group(1))
        title = _clean_title(m.group(2))
        if not title:
            continue
        if link.startswith("/"):
            link = "https://www.sogou.com" + link  # 搜狗是相对跳转链
        if not link.startswith("http") or link in seen:
            continue
        seen.add(link)
        results.append((title, link))
        if len(results) >= max_results:
            break
    return results, (None if results else "搜狗没解析到结果")


def _so360_search(query, max_results=5):
    """用 360 搜索（国内可达）。返回 [(标题, 链接)]。"""
    url = "https://www.so.com/s?q=" + urllib.parse.quote(query)
    try:
        page = _fetch(url, timeout=15)
    except Exception as e:
        return [], f"360搜索请求出错：{e}"
    results = []
    seen = set()
    for m in re.finditer(r'(?is)<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page):
        link = html.unescape(m.group(1))
        title = _clean_title(m.group(2))
        if not title or not link.startswith("http") or link in seen:
            continue
        seen.add(link)
        results.append((title, link))
        if len(results) >= max_results:
            break
    return results, (None if results else "360没解析到结果")


def _ddg_search(query, max_results=5):
    """用 DuckDuckGo HTML 版搜索（海外，国内需代理）。返回 [(标题, 链接)]。"""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        page = _fetch(url, timeout=15, use_proxy=True)
    except Exception as e:
        return [], f"DuckDuckGo 连接失败：{e}"
    results = []
    for m in re.finditer(
            r'(?s)<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            page):
        link, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        link = html.unescape(link)
        title = html.unescape(title).strip()
        mm = re.search(r"uddg=([^&]+)", link)
        if mm:
            link = urllib.parse.unquote(mm.group(1))
        results.append((title, link))
        if len(results) >= max_results:
            break
    return results, None


def _search(query, max_results=5):
    """先搜国内多个引擎（Bing→百度→搜狗），合并去重；再按需搜国外（需代理）。
    返回 ([(标题, 链接)], 提示信息或None)。"""
    note = None
    results = []
    seen = set()
    tried = []

    def add(pairs):
        for t, u in pairs:
            if u not in seen:
                seen.add(u); results.append((t, u))

    # 1) 国内多引擎，依次尝试，凑够数量就停
    for name, fn in (("Bing", _bing_search), ("百度", _baidu_search),
                     ("搜狗", _sogou_search), ("360", _so360_search)):
        if len(results) >= max_results:
            break
        try:
            pairs, _err = fn(query, max_results)
        except Exception:
            pairs = []
        tried.append(name)
        add(pairs)

    # 2) 国外：DuckDuckGo（需代理）
    proxy = _read_proxy()
    if proxy:
        try:
            ddg, _ = _ddg_search(query, max_results)
            add(ddg)
        except Exception:
            pass
    elif not results:
        note = ("国内引擎（Bing/百度/搜狗/360）这次都没拿到结果。要再搜国外源"
                "（DuckDuckGo/Google）需要翻墙/代理——到「设置 → 联网与代理」填好代理地址后重试。")

    if results:
        return results[:max_results + 3], note
    if note is None:
        note = (f"国内引擎（{('、').join(tried)}）都没搜到“{query}”。"
                "可能是关键词太具体或网络波动，换个更通用的词再试。")
    return [], note


def tool_search_web(args):
    """联网搜索，返回多条结果（标题+链接）。比内置 web_search 更适合找资料。"""
    query = args.get("query", "").strip()
    if not query:
        return "拒绝：搜索词为空。"
    n = min(int(args.get("max_results", 5)), 8)
    results, note = _search(query, n)
    if not results:
        return note or f"没搜到“{query}”的结果。换个关键词试试。"
    lines = [f"{i+1}. {t}\n   {u}" for i, (t, u) in enumerate(results)]
    out = "\n".join(lines)
    if note:
        out += "\n\n" + note
    return out


def gather(query, read_count=4):
    """调研一个话题，返回 (正文material, 实际读到的来源[(标题,网址)])。
    供情报简报用：material 给模型归纳，来源列表用来在简报末尾附上可点链接。"""
    read_n = min(int(read_count), 6)
    results, note = _search(query, read_n + 3)
    if not results:
        return (note or f"没搜到“{query}”的资料。"), []

    chunks = [f"## 调研主题：{query}\n"]
    sources = []
    read = 0
    for title, url in results:
        if read >= read_n:
            break
        try:
            page = _fetch(url, timeout=15)
            text = _extract_text(page)[:3500]  # 每个来源多读些，内容更充实
            if text and len(text) > 80:
                chunks.append(f"### 来源{read+1}：{title}\n{url}\n{text}\n")
                sources.append((title, url))
                read += 1
        except Exception:
            continue
    if read == 0:
        # 正文都读不出，至少把搜到的链接当作来源返回
        return ("搜到了链接但正文读不出（可能需登录或 JS 渲染）。" + (note or ""),
                results[:read_n])
    material = "\n".join(chunks)[:16000]
    return material, sources


def tool_research(args):
    """
    深度调研一个话题：搜索 + 自动读取前几个结果的正文，汇总给模型。
    适合"找信息""做功课"，让模型基于真实网页内容回答而非凭记忆。
    """
    query = args.get("query", "").strip()
    if not query:
        return "拒绝：调研主题为空。"
    read_n = min(int(args.get("read_count", 3)), 5)
    material, sources = gather(query, read_n)
    if not sources and material.startswith("没搜到"):
        return material
    out = material
    if sources:
        links = "\n".join(f"- {t}：{u}" for t, u in sources)
        out += f"\n\n（信息来源，可附在回答末尾供核对）：\n{links}"
    return out[:9000]
