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
    "sorryios.ai", "dakeai.cc", "deepseek.com", "moonshot.cn", "kimi.com", "doubao.com",
)


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


def proxy_for(url):
    """给这个网址用的代理地址；不需要代理返回空串。"""
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
    use_proxy=None（默认）：按网址自动判断；True：境外站走代理（国内站仍直连）；False：直连。
    直连时显式关掉系统代理，避免被 Clash 等「系统代理」接管。"""
    p = ""
    if use_proxy is not False:
        p = proxy_for(url) if url else (_read_proxy() if use_proxy else "")
    if p:
        return urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p})), p
    return urllib.request.build_opener(urllib.request.ProxyHandler({})), None


# ---------- 读网页正文 ----------
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
