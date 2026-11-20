"""
scrapling_worker.py — 在「Scrapling 独立环境」里运行的抓取小程序（v108）

由 scrapling_fetch.py 用独立环境里的 python 启动，一次抓一个网页：
  标准输入：JSON {"url": "...", "mode": "fast|browser", "proxy": "http://...", "timeout": 40}
  标准输出：一行 JSON {"ok": true, "status": 200, "url": "最终网址", "html": "...", "secs": 1.2}
            或 {"ok": false, "error": "原因"}
  --selftest：只检查 Scrapling 装好了没有，输出 {"ok": true, "version": "0.5.1"}

为什么单独一个进程、单独一个环境：Scrapling 需要较新的 playwright/patchright 等依赖，
装进软件自己的 Python 会把「AI 池」用的 playwright 一起升级，可能弄坏它；
放在独立环境里、每次单独起进程，互不影响，卡住了也能直接结束掉。
"""
import json
import sys
import time

MAX_HTML = 3_000_000


def _selftest():
    out = {"ok": True}
    try:
        import scrapling
        out["version"] = getattr(scrapling, "__version__", "")
        from scrapling.fetchers import Fetcher, StealthyFetcher  # noqa: F401（只检查能不能导入）
    except Exception as e:
        out = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    return out


def _fetch(req):
    url = req.get("url") or ""
    mode = req.get("mode") or "fast"
    proxy = req.get("proxy") or None
    timeout = float(req.get("timeout") or 40)
    t0 = time.time()
    if mode == "browser":
        from scrapling.fetchers import StealthyFetcher
        kw = dict(
            headless=True,
            real_chrome=bool(req.get("real_chrome", True)),   # 用电脑上装好的 Chrome，不用另外下载浏览器
            network_idle=True,          # 等页面加载完、网络安静下来再取内容（动态网页要这个）
            solve_cloudflare=True,      # 遇到 Cloudflare 验证页自动过
            disable_resources=True,     # 不加载图片、字体、视频，快很多
            block_ads=True,
            google_search=False,
            timeout=int(timeout * 1000),
            retries=1,
        )
        if proxy:
            kw["proxy"] = proxy
        page = StealthyFetcher.fetch(url, **kw)
    else:
        from scrapling.fetchers import Fetcher
        kw = dict(
            impersonate="chrome",       # 模拟真 Chrome 的网络指纹
            stealthy_headers=True,      # 生成真实浏览器的请求头
            timeout=timeout,
            retries=1,
            follow_redirects=True,
        )
        if proxy:
            kw["proxy"] = proxy
        page = Fetcher.get(url, **kw)
    status = int(getattr(page, "status", 0) or 0)
    html = str(getattr(page, "html_content", "") or "")
    return {
        "ok": 0 < status < 400,
        "status": status,
        "url": str(getattr(page, "url", "") or url),
        "html": html[:MAX_HTML],
        "secs": round(time.time() - t0, 1),
        "error": "" if 0 < status < 400 else "HTTP Error %d" % status,
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        print(json.dumps(_selftest(), ensure_ascii=False))
        return
    try:
        req = json.loads(sys.stdin.read() or "{}")
        out = _fetch(req)
    except Exception as e:
        out = {"ok": False, "error": ("%s: %s" % (type(e).__name__, e))[:600]}
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
