# -*- coding: utf-8 -*-
"""超能小助 · v65：导入文档 / 网页文章（不是视频的东西也能变成笔记）

  · 本地文件：PDF、Word（.docx / .doc）、WPS 文字、Excel（.xlsx / .xls / .csv）、PPT（.pptx）、
    TXT、Markdown、网页文件（.html / .mhtml）、电子书（.epub）、RTF。
  · 网页链接：读出文章正文、标题、作者、发布时间；公众号文章特别照顾；只靠浏览器才显示的网页，
    在后台浏览器里打开再读；链接直接指向 PDF / Word 等文件的，下载下来读；
    页面里有视频的，列出来（软件里可以一键接着提取）。
读出来的结果和视频提取的结果长得一样（title / uploader / url / transcript …），
后面的 AI 分析、存笔记、最新提取、批量分析全都照常用。
读 PDF、老版 .xls、老版 .doc 要用到的小组件（pypdf / xlrd / olefile），第一次用时自动安装。
"""
import io
import os
import posixpath
import re
import struct
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
import html as _html
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

MAX_CHARS = 400000          # 一篇最多存这么多字（再多就截掉：笔记太大，列表会变慢）
MAX_TABLE_ROWS = 1500       # 表格最多导入多少行
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")

KINDS = {
    ".pdf": "PDF 文档", ".docx": "Word 文档", ".docm": "Word 文档", ".doc": "Word 文档", ".wps": "WPS 文字",
    ".xlsx": "Excel 表格", ".xlsm": "Excel 表格", ".xls": "Excel 表格", ".et": "WPS 表格",
    ".csv": "CSV 表格", ".tsv": "表格", ".pptx": "PPT 演示文稿",
    ".txt": "文本", ".text": "文本", ".md": "Markdown", ".markdown": "Markdown",
    ".html": "网页文件", ".htm": "网页文件", ".mhtml": "网页文件", ".mht": "网页文件",
    ".epub": "电子书", ".rtf": "RTF 文档", ".json": "文本", ".log": "文本",
}
# 选文件框 / 导入文件夹用（文件夹里不收 .json / .log，免得把程序文件当文章导进来）
PICK_EXTS = sorted(e[1:] for e in KINDS)
FOLDER_EXTS = sorted(e[1:] for e in KINDS if e not in (".json", ".log", ".text", ".tsv"))

VIDEO_HOSTS = ("douyin.com", "iesdouyin.com", "bilibili.com", "b23.tv", "youtube.com", "youtu.be",
               "x.com", "twitter.com", "kuaishou.com", "chenzhongtech.com", "gifshow.com", "ixigua.com",
               "tiktok.com", "vimeo.com", "instagram.com", "facebook.com", "fb.watch", "twitch.tv",
               "v.qq.com", "youku.com", "iqiyi.com", "mgtv.com", "acfun.cn", "haokan.baidu.com",
               "weishi.qq.com", "nicovideo.jp", "dailymotion.com", "video.weibo.com", "channels.weixin.qq.com")
MEDIA_EXTS = (".mp4", ".m3u8", ".mp3", ".m4a", ".flv", ".mov", ".webm", ".wav", ".aac", ".mkv", ".ogg")
_SHORTENERS = ("t.cn", "url.cn", "dwz.cn", "bit.ly", "t.co", "tinyurl.com", "goo.gl", "suo.im", "s.weibo.com")
_CN_HOSTS = (".cn", "qq.com", "zhihu.com", "baidu.com", "sohu.com", "163.com", "126.com", "toutiao.com",
             "jianshu.com", "csdn.net", "36kr.com", "ifeng.com", "douban.com", "bilibili.com", "weibo.com",
             "xiaohongshu.com", "xhslink.com", "huxiu.com", "sspai.com", "smzdm.com", "geekpark.net",
             "cnblogs.com", "juejin.cn", "oschina.net", "infoq.cn", "guancha.cn", "jiemian.com", "yicai.com",
             "caixin.com", "eastmoney.com", "xueqiu.com", "sina.com", "taobao.com", "jd.com", "aliyun.com")


class _Fail(Exception):
    """给用户看的出错原因（直接显示）。"""


def _step(cb, s, d=""):
    if cb:
        try:
            cb(s, d)
        except Exception:
            pass


def kind_of(path):
    return KINDS.get(os.path.splitext(path or "")[1].lower(), "")


def is_doc_path(path):
    return bool(kind_of(path))


def noun_of(kind):
    """笔记类型 → AI 提示词里怎么称呼它。"""
    kind = kind or ""
    if "GitHub" in kind:          # v112：加工里的 GitHub 项目、一段文字
        return "开源项目"
    if kind == "文字":
        return "文字"
    if "表格" in kind:
        return "表格"
    if "演示" in kind:
        return "演示文稿"
    if "文章" in kind or "网页" in kind:
        return "文章"
    if "电子书" in kind:
        return "书"
    return "文档"


# ════════════════ 链接：是不是该当文章读 ════════════════

def first_url(text):
    m = re.search(r"https?://[^\s<>\"'，。！？、；：（）()【】《》「」]+", text or "")
    if not m:
        return ""
    return m.group(0).rstrip(".,;:!?)]}>'\"")


def _host(url):
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _host_in(host, names):
    return any(host == h or host.endswith("." + h) for h in names)


def article_url(text):
    """贴进来的链接如果**不是**视频网站（抖音 / B站 / YouTube…），返回这个链接（先当文章读）；
    是视频网站或者直接是音视频文件，返回空串（照原来的视频流程走）。"""
    url = first_url(text)
    if not url:
        return ""
    host = _host(url)
    if not host:
        return ""
    path = (urllib.parse.urlparse(url).path or "").lower()
    if _host_in(host, VIDEO_HOSTS) or path.endswith(MEDIA_EXTS):
        return ""
    if _host_in(host, ("weibo.com",)) and "/tv/" in path:
        return ""
    if _host_in(host, ("toutiao.com",)) and path.startswith("/video"):
        return ""
    if _host_in(host, ("zhihu.com",)) and "/zvideo" in path:
        return ""
    return url


# ════════════════ 小工具 ════════════════

_inst_lock = threading.Lock()


def _need(mod, pkg, cb=None, what=""):
    """要用的小组件没装就自动装（清华 → 阿里 → 默认源），装好返回模块；装不上抛 _Fail。"""
    import importlib
    try:
        return importlib.import_module(mod)
    except ImportError:
        pass
    with _inst_lock:
        try:
            return importlib.import_module(mod)
        except ImportError:
            pass
        import video_transcribe as vt
        _step(cb, "安装组件", "第一次%s，先自动装一个小组件 %s（几秒到一分钟）…" % (what, pkg))
        last = ""
        for label, args in vt._PIP_SOURCES:
            try:
                code, out = vt._run_pip(vt._pip_base() + [pkg] + list(args), timeout=240)
            except Exception as e:
                code, out = 1, str(e)
            if code == 0:
                importlib.invalidate_caches()
                try:
                    return importlib.import_module(mod)
                except ImportError as e:
                    last = "%s：装好了但加载不了（%s）" % (label, e)
                    continue
            last = "%s：%s" % (label, vt._pip_last_line(out))
        raise _Fail("自动安装 %s 没成功（%s）。检查一下网络，过一会儿再导入试试。" % (pkg, last[:160]))


def _decode(b, hint=""):
    if not b:
        return ""
    if b.startswith(b"\xef\xbb\xbf"):
        return b[3:].decode("utf-8", "replace")
    if b.startswith((b"\xff\xfe", b"\xfe\xff")):
        return b.decode("utf-16", "replace")
    encs = []
    if hint:
        h = hint.lower().strip()
        encs.append({"gb2312": "gb18030", "gbk": "gb18030", "x-gbk": "gb18030"}.get(h, h))
    if b[:4000].count(b"\x00") > 200:
        encs.append("utf-16-le")
    encs += ["utf-8", "gb18030"]
    for e in encs:
        try:
            return b.decode(e)
        except (UnicodeDecodeError, LookupError):
            continue
    return b.decode("utf-8", "replace")


def _meta_charset(b):
    m = re.search(rb"<meta[^>]+charset=[\"']?\s*([a-zA-Z0-9_\-]+)", (b or b"")[:6000], re.I)
    return m.group(1).decode("ascii", "ignore") if m else ""


_ZW = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_CJK_GAP = re.compile(r"(?<=[\u4e00-\u9fff，。！？；：、）」』”])[ \t]+(?=[\u4e00-\u9fff，。！？；：、（「『“])")


def _tidy(t):
    t = _ZW.sub("", (t or "").replace("\r\n", "\n").replace("\r", "\n"))
    t = t.replace("\xa0", " ").replace("\u3000", " ")
    out, blank = [], 0
    for ln in t.split("\n"):
        s = _CJK_GAP.sub("", re.sub(r"[ \t\f\v]+", " ", ln).strip())
        if not s:
            blank += 1
            if blank == 1 and out:
                out.append("")
            continue
        blank = 0
        out.append(s)
    return "\n".join(out).strip()


def _cap(t):
    if len(t) > MAX_CHARS:
        return t[:MAX_CHARS] + "\n\n（原文太长，只导入了前 %d 字）" % MAX_CHARS, True
    return t, False


_JUNK_STEM = re.compile(r"^(?:(?:新建|未命名|未标题|无标题).*|(?:untitled|document|doc|文档|下载|download|image|scan"
                        r"|扫描|tmp|temp|副本|copy|file|文件)[\s_\-\d()（）.]*)$", re.I)


def _good_title(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    if not (2 <= len(s) <= 120):
        return ""
    if re.match(r"^(microsoft (word|excel|powerpoint) - |untitled|无标题|slide \d)", s, re.I):
        return ""
    return s


def _pick_title(stem, meta_title, text):
    st = (stem or "").strip()
    if st and not _JUNK_STEM.match(st) and not re.fullmatch(r"[\d\W_]+", st):
        return st[:120]
    t = _good_title(meta_title)
    if t:
        return t
    for ln in (text or "").split("\n")[:15]:
        ln = ln.strip().lstrip("#").strip()
        if 2 <= len(ln) <= 60:
            return ln
    return st or "导入的文档"


def _join_rel(base_dir, target):
    target = (target or "").split("#")[0]
    if target.startswith("/"):
        return target[1:]
    return posixpath.normpath(posixpath.join(base_dir, target)) if base_dir else posixpath.normpath(target)


def _md_table(rows, more=False):
    """rows：[{列号: 文字}]，第一行当表头 → Markdown 表格。"""
    cols = sorted({c for r in rows for c in r})[:40]
    if not cols:
        return ""

    def cell(v):
        return re.sub(r"\s*\n\s*", " ", str(v)).replace("|", "｜").strip()
    lines = ["| " + " | ".join(cell(rows[0].get(c, "")) for c in cols) + " |",
             "|" + "---|" * len(cols)]
    for r in rows[1:]:
        lines.append("| " + " | ".join(cell(r.get(c, "")) for c in cols) + " |")
    if more:
        lines.append("\n（表格太长，只导入了前 %d 行）" % len(rows))
    return "\n".join(lines)


def _num(v):
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return ("%.6f" % f).rstrip("0").rstrip(".")


# ════════════════ 各种文件 ════════════════

def _read_text(p, cb, meta):
    with open(p, "rb") as f:
        b = f.read(MAX_CHARS * 4)
    t = _decode(b)
    if p.lower().endswith((".md", ".markdown")):
        m = re.search(r"^#\s+(.+)$", t, re.M)
        if m:
            meta["title"] = m.group(1).strip()
    return t


def _reflow(t):
    """PDF 读出来每一行都断开 → 把同一段的行接起来（句子没结束、下一行也不像标题 / 列表，就接上）。"""
    out, buf = [], ""
    for ln in (t or "").split("\n"):
        s = ln.strip()
        if not s:
            if buf:
                out.append(buf)
                buf = ""
            continue
        if not buf:
            buf = s
            continue
        ends = re.search(r"[。！？!?：:；;…”」』）)】]$", buf)
        starts_item = re.match(r"^([-•·●▪*]|\d{1,3}[.、)）]|[一二三四五六七八九十]+[、.]|第[一二三四五六七八九十\d]+[章节条部分篇])", s)
        short = len(buf) < 14 and not re.search(r"[，,、]$", buf)      # 短行多半是标题（以逗号结尾的不算）
        if ends or starts_item or short:
            out.append(buf)
            buf = s
        else:
            cjk = re.match(r"[\u4e00-\u9fff，。]", buf[-1]) or re.match(r"[\u4e00-\u9fff，。]", s[0])
            if buf.endswith("-") and not cjk:
                buf = buf[:-1] + s
            else:
                buf = buf + ("" if cjk else " ") + s
    if buf:
        out.append(buf)
    return "\n\n".join(out)


def _read_pdf(p, cb, meta):
    try:
        import fitz            # 装了 PyMuPDF 就用它（读得更准），没装就用 pypdf
        doc = fitz.open(p)
        if doc.needs_pass:
            raise _Fail("这个 PDF 加了密码，打不开")
        pages, n = [], doc.page_count
        for i in range(n):
            if i % 10 == 0:
                _step(cb, "读取文档", "正在读 PDF 第 %d / %d 页…" % (i + 1, n))
            pages.append(doc.load_page(i).get_text("text") or "")
            if sum(map(len, pages)) > MAX_CHARS:
                break
        meta["title"] = (doc.metadata or {}).get("title") or ""
        doc.close()
    except ImportError:
        pypdf = _need("pypdf", "pypdf", cb, "读 PDF")
        try:
            r = pypdf.PdfReader(p)
        except Exception as e:
            raise _Fail("这个 PDF 打不开（%s）" % str(e)[:80])
        if r.is_encrypted:
            try:
                r.decrypt("")
            except Exception:
                raise _Fail("这个 PDF 加了密码，打不开")
        pages, n = [], len(r.pages)
        for i, pg in enumerate(r.pages):
            if i % 5 == 0:
                _step(cb, "读取文档", "正在读 PDF 第 %d / %d 页…" % (i + 1, n))
            try:
                pages.append(pg.extract_text() or "")
            except Exception:
                pages.append("")
            if sum(map(len, pages)) > MAX_CHARS:
                break
        try:
            meta["title"] = str((r.metadata or {}).get("/Title") or "")
        except Exception:
            pass
    text = "\n\n".join(_reflow(x) for x in pages if x.strip())
    solid = len(re.sub(r"\s", "", text))
    if solid < 30 * max(1, min(n, 5)):
        meta["why_empty"] = ("：这个 PDF 多半是扫描件或图片，里面没有文字层，暂时读不了。"
                             "可以找带文字的版本，或者把文字复制出来存成 txt 再导入")
        return ""
    bad = len(re.findall("[\ufffd\ue000-\uf8ff]", text))
    if bad > solid * 0.2:
        raise _Fail("这个 PDF 用的字体比较特殊，读出来是乱码。可以用 WPS / Adobe 打开后「另存为」Word 或 txt 再导入")
    return text


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _docx_par(p):
    parts = []

    def walk(el):
        for ch in el:
            tag = ch.tag
            if tag in (_MC_FALLBACK, _W + "delText", _W + "instrText"):
                continue
            if tag == _W + "t":
                parts.append(ch.text or "")
            elif tag == _W + "tab":
                parts.append(" ")
            elif tag in (_W + "br", _W + "cr"):
                parts.append("\n")
            else:
                walk(ch)
    walk(p)
    return "".join(parts)


def _read_docx(p, cb, meta):
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        if "word/document.xml" not in names:
            raise _Fail("这不是正常的 Word 文件（里面没有正文）")
        hmap, list_styles = {}, set()
        if "word/styles.xml" in names:
            try:
                for st in ET.fromstring(z.read("word/styles.xml")).iter(_W + "style"):
                    nm = st.find(_W + "name")
                    name = ((nm.get(_W + "val") if nm is not None else "") or "").strip()
                    mm = re.match(r"(?i)^(heading|标题)\s*(\d)$", name)
                    lvl = int(mm.group(2)) if mm else (1 if name.lower() in ("title", "标题") else None)
                    ol = st.find(_W + "pPr/" + _W + "outlineLvl")
                    if lvl is None and ol is not None:
                        try:
                            lvl = int(ol.get(_W + "val")) + 1
                        except Exception:
                            lvl = None
                    if lvl and 1 <= lvl <= 6:
                        hmap[st.get(_W + "styleId") or ""] = lvl
                    if st.find(_W + "pPr/" + _W + "numPr") is not None or re.match(r"(?i)^list (bullet|number)", name):
                        list_styles.add(st.get(_W + "styleId") or "")
            except Exception:
                pass
        if "docProps/core.xml" in names:
            try:
                for el in ET.fromstring(z.read("docProps/core.xml")):
                    if el.tag.endswith("}title") and (el.text or "").strip():
                        meta["title"] = el.text.strip()
            except Exception:
                pass
        root = ET.fromstring(z.read("word/document.xml"))
    out = []

    def block(el):
        for ch in el:
            if ch.tag == _W + "p":
                t = _docx_par(ch).strip()
                if not t:
                    continue
                ppr, pre = ch.find(_W + "pPr"), ""
                if ppr is not None:
                    ps = ppr.find(_W + "pStyle")
                    lvl = hmap.get(ps.get(_W + "val")) if ps is not None else None
                    if lvl:
                        pre = "#" * min(lvl + 1, 6) + " "      # 笔记自己有一级标题，正文里的标题往下降一级
                    elif ppr.find(_W + "numPr") is not None or (ps is not None and ps.get(_W + "val") in list_styles):
                        pre = "- "
                out.append(pre + t.replace("\n", "  \n"))
            elif ch.tag == _W + "tbl":
                rows = []
                for tr in ch.iter(_W + "tr"):
                    cells = {}
                    for i, tc in enumerate(tr.findall(_W + "tc")):
                        v = " ".join(_docx_par(pp).strip() for pp in tc.iter(_W + "p")).strip()
                        if v:
                            cells[i] = v
                    if cells:
                        rows.append(cells)
                if rows:
                    out.append(_md_table(rows))
            elif ch.tag in (_W + "sdt", _W + "sdtContent", _W + "customXml", _W + "smartTag", _W + "ins"):
                block(ch)
    body = root.find(_W + "body")
    if body is not None:
        block(body)
    return "\n\n".join(out)


def _strip_fields(t):
    out, stack = [], []
    for ch in t:
        if ch == "\x13":
            stack.append(False)
            continue
        if ch == "\x14":
            if stack:
                stack[-1] = True
            continue
        if ch == "\x15":
            if stack:
                stack.pop()
            continue
        if stack and not all(stack):
            continue                 # 域代码（比如 HYPERLINK "…"）不要，只留显示出来的结果
        out.append(ch)
    return "".join(out)


def _read_doc(p, cb, meta):
    with open(p, "rb") as f:
        head = f.read(8)
    if head.startswith(b"PK"):
        return _read_docx(p, cb, meta)          # 其实是 docx，只是后缀写成了 .doc
    if head.startswith(b"{\\rtf"):
        return _read_rtf(p, cb, meta)
    if head != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _read_html_file(p, cb, meta)     # Word 存的「网页格式」，后缀也是 .doc
    olefile = _need("olefile", "olefile", cb, "读老版 Word（.doc）")
    ole = olefile.OleFileIO(p)
    try:
        if not ole.exists("WordDocument"):
            raise _Fail("这不是 Word 文档（可能是别的软件的文件改了后缀）。可以用 WPS / Word 另存为 .docx 再导入")
        wd = ole.openstream("WordDocument").read()
        flags = struct.unpack_from("<H", wd, 0x0A)[0]
        if flags & 0x0100:
            raise _Fail("这个 Word 文件加了密码，打不开")
        tname = "1Table" if flags & 0x0200 else "0Table"
        if not ole.exists(tname):
            raise _Fail("这个 Word 文件格式太老，读不了。可以用 WPS / Word 另存为 .docx 再导入")
        tbl = ole.openstream(tname).read()
    finally:
        ole.close()
    ccp = struct.unpack_from("<i", wd, 0x4C)[0]
    fc_clx, lcb_clx = struct.unpack_from("<II", wd, 0x1A2)
    clx = tbl[fc_clx: fc_clx + lcb_clx]
    i = 0
    while i < len(clx) and clx[i] == 0x01:           # 先是格式信息（Prc），跳过
        i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
    if i + 5 > len(clx) or clx[i] != 0x02:
        raise _Fail("这个 Word 文件的结构读不懂（可能是很老的格式）。可以用 WPS / Word 另存为 .docx 再导入")
    lcb = struct.unpack_from("<I", clx, i + 1)[0]
    plc = clx[i + 5: i + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from("<%di" % (n + 1), plc, 0)
    parts = []
    for k in range(n):
        off = (n + 1) * 4 + k * 8
        fc = struct.unpack_from("<I", plc, off + 2)[0]
        cnt = cps[k + 1] - cps[k]
        if cnt <= 0:
            continue
        if fc & 0x40000000:                            # 压缩的：一个字节一个字（英文）
            pos = (fc & 0x3FFFFFFF) // 2
            parts.append(wd[pos: pos + cnt].decode("cp1252", "replace"))
        else:                                          # 没压缩的：UTF-16（中文都是这种）
            parts.append(wd[fc: fc + cnt * 2].decode("utf-16-le", "replace"))
    text = "".join(parts)
    if ccp > 0:
        text = text[:ccp]                              # 后面是页眉页脚、脚注等
    text = _strip_fields(text)
    text = text.replace("\r", "\n\n").replace("\x07", " ").replace("\x0b", "\n").replace("\x0c", "\n\n")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", "", text)


_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_DATE_FMT_IDS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _col_idx(ref):
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def _xl_date(v):
    import datetime as dt
    try:
        f = float(v)
    except Exception:
        return str(v)
    if not (0 < f < 2958466):
        return _num(v)
    d = dt.datetime(1899, 12, 30) + dt.timedelta(days=f)
    if f < 1:
        return d.strftime("%H:%M")
    if abs(f - round(f)) < 1e-6:
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d %H:%M")


def _read_xlsx(p, cb, meta):
    blocks = []
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        if "xl/workbook.xml" not in names:
            raise _Fail("这不是正常的 Excel 文件")
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_S + "si"):
                ts = [si.find(_S + "t")] + [r.find(_S + "t") for r in si.findall(_S + "r")]
                shared.append("".join((t.text or "") for t in ts if t is not None))
        date_styles = set()
        if "xl/styles.xml" in names:
            try:
                st = ET.fromstring(z.read("xl/styles.xml"))
                custom = {}
                nf = st.find(_S + "numFmts")
                for f in (nf.findall(_S + "numFmt") if nf is not None else []):
                    code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", f.get("formatCode") or "").lower()
                    custom[int(f.get("numFmtId") or 0)] = any(c in code for c in "ydh")
                xfs = st.find(_S + "cellXfs")
                for i, xf in enumerate(xfs.findall(_S + "xf") if xfs is not None else []):
                    fid = int(xf.get("numFmtId") or 0)
                    if fid in _DATE_FMT_IDS or custom.get(fid):
                        date_styles.add(i)
            except Exception:
                pass
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(_PR + "Relationship"):
                rels[r.get("Id")] = r.get("Target") or ""
        sheets = []
        for s in ET.fromstring(z.read("xl/workbook.xml")).iter(_S + "sheet"):
            if s.get("state") in ("hidden", "veryHidden"):
                continue
            sheets.append((s.get("name") or "", _join_rel("xl", rels.get(s.get(_R + "id")) or "")))
        for name, path in sheets:
            if path not in names:
                continue
            rows, more = [], False
            with z.open(path) as fh:
                for _ev, el in ET.iterparse(fh, events=("end",)):
                    if el.tag != _S + "row":
                        continue
                    cells = {}
                    for c in el.findall(_S + "c"):
                        ref, t = c.get("r") or "", c.get("t") or "n"
                        ci = _col_idx(ref) if ref else len(cells)
                        v = c.find(_S + "v")
                        val = ""
                        if t == "s" and v is not None:
                            try:
                                val = shared[int(v.text)]
                            except Exception:
                                val = ""
                        elif t == "inlineStr":
                            val = "".join((x.text or "") for x in c.iter(_S + "t"))
                        elif t == "b" and v is not None:
                            val = "是" if (v.text or "") == "1" else "否"
                        elif v is not None and v.text is not None:
                            if t in ("str", "e"):
                                val = v.text
                            elif int(c.get("s") or 0) in date_styles:
                                val = _xl_date(v.text)
                            else:
                                val = _num(v.text)
                        if str(val).strip() and 0 <= ci < 60:
                            cells[ci] = str(val)
                    el.clear()
                    if cells:
                        rows.append(cells)
                        if len(rows) >= MAX_TABLE_ROWS:
                            more = True
                            break
            if rows:
                head = ("## 工作表：%s\n\n" % name) if len(sheets) > 1 else ""
                blocks.append(head + _md_table(rows, more))
    return "\n\n".join(blocks)


def _read_xls(p, cb, meta):
    with open(p, "rb") as f:
        head = f.read(8)
    if head.startswith(b"PK"):
        return _read_xlsx(p, cb, meta)
    if head.lstrip()[:1] == b"<":
        return _read_html_file(p, cb, meta)        # 有的 .xls 其实是网页表格
    xlrd = _need("xlrd", "xlrd", cb, "读老版 Excel（.xls）")
    try:
        book = xlrd.open_workbook(p, on_demand=True)
    except Exception as e:
        raise _Fail("读不了这个 Excel 文件（%s）。可以用 Excel / WPS 另存为 .xlsx 再导入" % str(e)[:80])
    blocks = []
    sheets = book.sheets()
    for sh in sheets:
        rows = []
        for r in range(min(sh.nrows, MAX_TABLE_ROWS)):
            cells = {}
            for c in range(min(sh.ncols, 60)):
                cell = sh.cell(r, c)
                if cell.ctype in (0, 5, 6):          # 空 / 错误值 / 空白
                    continue
                if cell.ctype == 3:                  # 日期
                    try:
                        y, mo, d, hh, mi, _s = xlrd.xldate_as_tuple(cell.value, book.datemode)
                        val = ("%04d-%02d-%02d" % (y, mo, d)) if y else ""
                        if hh or mi:
                            val = (val + " " if val else "") + "%02d:%02d" % (hh, mi)
                    except Exception:
                        val = _num(cell.value)
                elif cell.ctype == 2:
                    val = _num(cell.value)
                elif cell.ctype == 4:
                    val = "是" if cell.value else "否"
                else:
                    val = str(cell.value)
                if val.strip():
                    cells[c] = val
            if cells:
                rows.append(cells)
        if rows:
            head = ("## 工作表：%s\n\n" % sh.name) if len(sheets) > 1 else ""
            blocks.append(head + _md_table(rows, sh.nrows > MAX_TABLE_ROWS))
    return "\n\n".join(blocks)


def _read_csv(p, cb, meta):
    import csv
    with open(p, "rb") as f:
        t = _decode(f.read(30 * 1024 * 1024))
    if p.lower().endswith(".tsv"):
        delim = "\t"
    else:
        try:
            delim = csv.Sniffer().sniff(t[:5000], delimiters=",;\t|").delimiter
        except Exception:
            delim = ","
    rows, more = [], False
    for row in csv.reader(io.StringIO(t), delimiter=delim):
        cells = {i: v.strip() for i, v in enumerate(row[:60]) if v.strip()}
        if cells:
            rows.append(cells)
            if len(rows) >= MAX_TABLE_ROWS:
                more = True
                break
    return _md_table(rows, more)


_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def _read_pptx(p, cb, meta):
    blocks = []
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        order = []
        try:
            rels = {r.get("Id"): r.get("Target") for r in
                    ET.fromstring(z.read("ppt/_rels/presentation.xml.rels")).iter(_PR + "Relationship")}
            for s in ET.fromstring(z.read("ppt/presentation.xml")).iter(_P + "sldId"):
                order.append(_join_rel("ppt", rels.get(s.get(_R + "id")) or ""))
        except Exception:
            order = []
        if not order:
            order = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                           key=lambda n: int(re.findall(r"\d+", n)[-1]))
        for i, path in enumerate(order, 1):
            if path not in names:
                continue
            paras = []
            for para in ET.fromstring(z.read(path)).iter(_A + "p"):
                t = "".join((x.text or "") for x in para.iter(_A + "t")).strip()
                if t:
                    paras.append(t)
            if paras:
                blocks.append("## 第 %d 页\n\n" % i + "\n\n".join(paras))
    return "\n\n".join(blocks)


def _read_epub(p, cb, meta):
    blocks = []
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        cont = ET.fromstring(z.read("META-INF/container.xml"))
        opf_path = next((e.get("full-path") for e in cont.iter() if e.tag.endswith("rootfile")), "")
        if opf_path not in names:
            raise _Fail("这本电子书的目录读不出来")
        opf = ET.fromstring(z.read(opf_path))
        base = posixpath.dirname(opf_path)
        for e in opf.iter():
            if e.tag.endswith("}title") and not meta.get("title") and (e.text or "").strip():
                meta["title"] = e.text.strip()
            if e.tag.endswith("}creator") and not meta.get("author") and (e.text or "").strip():
                meta["author"] = e.text.strip()
        manifest = {it.get("id"): it.get("href") for it in opf.iter() if it.tag.endswith("}item")}
        spine = [it.get("idref") for it in opf.iter() if it.tag.endswith("}itemref")]
        for i, idref in enumerate(spine):
            path = _join_rel(base, urllib.parse.unquote(manifest.get(idref) or ""))
            if path not in names:
                continue
            if i % 10 == 0:
                _step(cb, "读取文档", "正在读电子书第 %d / %d 章…" % (i + 1, len(spine)))
            b = z.read(path)
            blocks.append(html_to_text(_decode(b, _meta_charset(b))))
            if sum(map(len, blocks)) > MAX_CHARS:
                break
    return "\n\n".join(x for x in blocks if x.strip())


_RTF_DEST = set(("aftncn aftnsep aftnsepc annotation atnauthor atndate atnicn atnid atnparent atnref atntime "
                 "atrfend atrfstart author background bkmkend bkmkstart blipuid buptim category colorschememapping "
                 "colortbl comment company creatim datafield datastore defchp defpap do doccomm docvar dptxbxtext "
                 "ebcend ebcstart factoidname falt fchars ffdeftext ffentrymcr ffexitmcr ffformat ffhelptext ffl "
                 "ffname ffstattext file filetbl fldinst fldtype fname fontemb fontfile fonttbl footer footerf "
                 "footerl footerr footnote formfield ftncn ftnsep ftnsepc g generator gridtbl header headerf "
                 "headerl headerr hl hlfr hlinkbase hlloc hlsrc hsv htmltag info keycode keywords latentstyles "
                 "lchars levelnumbers leveltext lfolevel linkval list listlevel listname listoverride "
                 "listoverridetable listpicture liststylename listtable listtext lsdlockedexcept macc maccpr "
                 "mailmerge manager mmath mmathpict mmathpr nesttableprops nextfile nonesttables objalias "
                 "objclass objdata object objname objsect objtime oldcprops oldpprops oldsprops oldtprops "
                 "oleclsid operator panose password passwordhash pgp pgptbl picprop pict pn pnseclvl pntext "
                 "pntxta pntxtb printim private propname protend protstart protusertbl pxe revtbl revtim "
                 "rsidtbl rxe shp shpgrp shpinst shppict shprslt shptxt sn sp staticval stylesheet subject sv "
                 "svb tc template themedata title txe ud upr userprops wgrffmtfilter windowcaption "
                 "writereservation writereservhash xe xform xmlattrname xmlattrvalue xmlclose xmlname "
                 "xmlnstbl xmlopen").split())
_RTF_PAT = re.compile(r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)", re.I)
_RTF_SPECIAL = {"emdash": "—", "endash": "–", "bullet": "•", "lquote": "‘", "rquote": "’",
                "ldblquote": "“", "rdblquote": "”"}


def rtf_to_text(text):
    m_cp = re.search(r"\\ansicpg(\d+)", text[:5000])
    cp = "cp" + m_cp.group(1) if m_cp else "cp1252"
    try:
        "".encode(cp)
    except LookupError:
        cp = "cp1252"
    stack, ignorable, ucskip, curskip = [], False, 1, 0
    out, pend = [], bytearray()

    def flush():
        if pend:
            out.append(bytes(pend).decode(cp, "replace"))
            pend.clear()
    for m in _RTF_PAT.finditer(text):
        word, arg, hexv, char, brace, tchar = m.groups()
        if hexv:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                pend.append(int(hexv, 16))
            continue
        flush()
        if brace:
            curskip = 0
            if brace == "{":
                stack.append((ucskip, ignorable))
            elif stack:
                ucskip, ignorable = stack.pop()
        elif char:
            curskip = 0
            if char == "~" and not ignorable:
                out.append(" ")
            elif char in "{}\\" and not ignorable:
                out.append(char)
            elif char == "*":
                ignorable = True
        elif word:
            curskip = 0
            w = word.lower()
            if w in _RTF_DEST:
                ignorable = True
            elif ignorable:
                pass
            elif w in ("par", "line", "sect", "page", "row"):
                out.append("\n")
            elif w in ("tab", "cell"):
                out.append(" ")
            elif w == "uc":
                ucskip = int(arg or 1)
            elif w == "u":
                c = int(arg or 0)
                out.append(chr(c + 0x10000 if c < 0 else c))
                curskip = ucskip
            elif w in _RTF_SPECIAL:
                out.append(_RTF_SPECIAL[w])
        elif tchar:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                out.append(tchar)
    flush()
    return "".join(out)


def _read_rtf(p, cb, meta):
    with open(p, "rb") as f:
        return rtf_to_text(f.read(50 * 1024 * 1024).decode("latin-1"))


def _read_html_file(p, cb, meta):
    with open(p, "rb") as f:
        b = f.read(30 * 1024 * 1024)
    art = parse_article(_decode(b, _meta_charset(b)), "")
    meta["title"], meta["author"] = art.get("title") or "", art.get("author") or ""
    return art.get("text") or ""


def _read_mhtml(p, cb, meta):
    import email
    from email import policy
    with open(p, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True) or b""
            art = parse_article(_decode(payload, part.get_content_charset() or _meta_charset(payload)),
                                part.get("Content-Location", "") or "")
            meta["title"], meta["author"] = art.get("title") or "", art.get("author") or ""
            return art.get("text") or ""
    raise _Fail("这个网页文件里没找到正文")


_READERS = {".pdf": _read_pdf, ".docx": _read_docx, ".docm": _read_docx, ".doc": _read_doc, ".wps": _read_doc,
            ".xlsx": _read_xlsx, ".xlsm": _read_xlsx, ".xls": _read_xls, ".et": _read_xls,
            ".csv": _read_csv, ".tsv": _read_csv, ".pptx": _read_pptx, ".epub": _read_epub, ".rtf": _read_rtf,
            ".html": _read_html_file, ".htm": _read_html_file, ".mhtml": _read_mhtml, ".mht": _read_mhtml}


def extract_file(path, progress_cb=None):
    """读一个本地文档 → 和视频提取一样的结果（ok / title / uploader / url / transcript …）。"""
    p = (path or "").strip().strip('"').strip("'")
    ext = os.path.splitext(p)[1].lower()
    kind = KINDS.get(ext)
    base = os.path.basename(p)
    if not kind:
        return {"ok": False, "error": "不支持这种文件：%s" % (ext or base)}
    if not os.path.isfile(p):
        return {"ok": False, "error": "找不到这个文件（可能被移动或删除了）"}
    if os.path.getsize(p) > 300 * 1024 * 1024:
        return {"ok": False, "error": "文件太大了（超过 300MB）"}
    _step(progress_cb, "读取文档", "正在读「%s」…" % base[:40])
    meta = {}
    try:
        text = _READERS.get(ext, _read_text)(p, progress_cb, meta)
    except _Fail as e:
        return {"ok": False, "error": str(e)}
    except (zipfile.BadZipFile, ET.ParseError, KeyError, StopIteration):
        return {"ok": False, "error": "文件打不开：不是正常的%s（可能已损坏，或者其实是别的格式）。"
                                      "可以用 WPS / Office 打开后另存一份再导入" % kind}
    except Exception as e:
        return {"ok": False, "error": "读取出错：%s" % (str(e)[:200] or type(e).__name__)}
    text = _tidy(text)
    if len(re.sub(r"\s", "", text)) < 5:
        return {"ok": False, "error": "这个文件里没读到文字" + (meta.get("why_empty") or "")}
    text, cut = _cap(text)
    title = _pick_title(os.path.splitext(base)[0], meta.get("title"), text)
    author = (meta.get("author") or "") if ext in (".epub", ".html", ".htm", ".mhtml", ".mht") else ""
    return {"ok": True, "title": title, "uploader": re.sub(r"\s+", " ", author).strip()[:40],
            "url": "（本地文件）" + base, "transcript": text, "segments": [], "local_path": p,
            "source": "doc", "doc_kind": kind, "src_noun": noun_of(kind), "truncated": cut}


# ════════════════ 网页 → 正文 ════════════════

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
         "track", "wbr", "keygen", "command"}
_SKIP = {"script", "style", "noscript", "template", "svg", "canvas", "object", "head", "select", "textarea",
         "button", "math", "iframe"}
_BLOCK = {"p", "div", "section", "article", "main", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol",
          "blockquote", "pre", "table", "thead", "tbody", "tr", "td", "th", "dl", "dt", "dd", "figure",
          "figcaption", "header", "footer", "aside", "nav", "form", "address", "details", "summary", "center"}
_HEADS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_NOISE_TAGS = {"nav", "aside", "footer", "form", "header"}
_POS = re.compile(r"article|content|post|entry|main|text|body|story|detail|rich_media|blog|news|markdown|prose"
                  r"|essay|正文", re.I)
_NEG = re.compile(r"comment|footer|footnote|sidebar|side-bar|sponsor|\bads?\b|ad-|advert|banner|share|social"
                  r"|related|recommend|\bhot\b|rank|\bnav|menu|breadcrumb|copyright|login|signin|subscribe"
                  r"|popup|modal|toolbar|widget|qrcode|download-app|reward|pagination|pager|\btags?\b", re.I)
_PUNCT = re.compile(r"[，。！？；,.!?;]")


class _N:
    __slots__ = ("tag", "attrs", "kids", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, attrs, [], parent


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _N("#root", {}, None)
        self.cur = self.root
        self.skip_tag, self.skip = "", 0
        self.meta, self.title, self._in_title = {}, "", False
        self.iframes, self.videos = [], []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs if k}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"]
            return
        if tag == "title":
            self._in_title = True
        if tag == "iframe" and (a.get("src") or a.get("data-src")):
            self.iframes.append(a.get("src") or a.get("data-src"))
        if tag in ("video", "source", "embed") and (a.get("src") or a.get("data-src")):
            self.videos.append(a.get("src") or a.get("data-src"))
        if self.skip:
            if tag == self.skip_tag:
                self.skip += 1
            return
        if tag in _SKIP:
            self.skip_tag, self.skip = tag, 1
            return
        if tag in _VOID:
            if tag in ("br", "hr"):
                self.cur.kids.append(_N(tag, a, self.cur))
            return
        if tag in ("p", "li", "dt", "dd", "option") and self.cur.tag == tag:
            self.cur = self.cur.parent or self.root
        elif tag in _BLOCK and self.cur.tag == "p":
            self.cur = self.cur.parent or self.root
        n = _N(tag, a, self.cur)
        self.cur.kids.append(n)
        self.cur = n

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if self.skip:
            if tag == self.skip_tag:
                self.skip -= 1
            return
        n, k = self.cur, 0
        while n is not None and n is not self.root and k < 60:
            if n.tag == tag:
                self.cur = n.parent or self.root
                return
            n, k = n.parent, k + 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if not self.skip and data:
            self.cur.kids.append(data)


def _walk(root):
    """先序遍历（不递归，网页嵌套再深也不会出错）。"""
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(k for k in reversed(n.kids) if isinstance(k, _N))


def _stats(root):
    """每个节点：(字数, 链接里的字数, 标点数, 自己直接带的字数)。后序计算，不递归。"""
    st, order, stack = {}, [], [(root, False)]
    while stack:
        n, done = stack.pop()
        if not done:
            stack.append((n, True))
            stack.extend((k, False) for k in n.kids if isinstance(k, _N))
            continue
        tl = ll = cc = own = 0
        for k in n.kids:
            if isinstance(k, str):
                s = re.sub(r"\s+", "", k)
                if s:
                    tl += len(s)
                    own += len(s)
                    cc += len(_PUNCT.findall(s))
            else:
                a, b, c, _ = st[id(k)]
                tl, ll, cc = tl + a, ll + b, cc + c
        if n.tag == "a":
            ll = tl
        st[id(n)] = (tl, ll, cc, own)
        order.append(n)
    return st, order


def _cls(n):
    return (n.attrs.get("class", "") + " " + n.attrs.get("id", "")).strip()


def _weight(n):
    w, c = 0, _cls(n)
    if c:
        if _NEG.search(c):
            w -= 25
        if _POS.search(c):
            w += 25
    return w


def _best(root, st, order):
    scores = {}
    base = {"div": 5, "article": 10, "main": 5, "section": 3, "pre": 3, "td": 3, "blockquote": 3,
            "form": -3, "ol": -3, "ul": -3, "dl": -3, "li": -3, "address": -3, "th": -5,
            "h1": -5, "h2": -5, "h3": -5, "h4": -5, "h5": -5, "h6": -5}

    def add(n, v):
        if n is None or n.tag == "#root":
            return
        if id(n) not in scores:
            scores[id(n)] = [n, base.get(n.tag, 0) + _weight(n)]
        scores[id(n)][1] += v
    for n in order:
        tl, ll, cc, own = st[id(n)]
        para = n.tag in ("p", "pre", "td", "blockquote") or (
            n.tag in ("div", "section", "span", "font", "li", "article") and own >= 25)
        if not para or tl < 25:
            continue
        sc = 1 + cc + min(tl // 100, 3)
        p1 = n.parent
        add(p1, sc)
        if p1 is not None:
            add(p1.parent, sc / 2)
            if p1.parent is not None:
                add(p1.parent.parent, sc / 3)
    best, best_s = None, 0
    for n, s in scores.values():
        tl, ll, _cc, _own = st[id(n)]
        s = s * (1 - (ll / tl if tl else 1))
        if s > best_s:
            best, best_s = n, s
    return best


def _noise(n, st):
    if n.tag in _NOISE_TAGS:
        return True
    c = _cls(n)
    if c and _NEG.search(c) and not _POS.search(c):
        return True
    tl, ll, _cc, _own = st.get(id(n), (0, 0, 0, 0))
    return tl > 0 and tl < 300 and ll / tl > 0.6 and n.tag not in ("p", "h1", "h2", "h3", "li", "a")


def _flat(n):
    if n is None:
        return ""
    parts = []

    def rec(x, depth=0):
        for k in x.kids:
            if isinstance(k, str):
                parts.append(k)
            elif depth < 200:
                if k.tag == "br":
                    parts.append(" ")
                rec(k, depth + 1)
    rec(n)
    return _CJK_GAP.sub("", re.sub(r"\s+", " ", "".join(parts))).strip()


def _render(root, st):
    """正文节点 → 带简单 Markdown 的文字（标题、列表、表格、代码块）。不递归。"""
    out = []
    stack = [("node", root)]
    while stack:
        kind, x = stack.pop()
        if kind == "text":
            out.append(x)
            continue
        if isinstance(x, str):
            out.append(re.sub(r"\s+", " ", x))
            continue
        t = x.tag
        if x is not root:
            if t == "br":
                out.append("\n")
                continue
            if t == "hr":
                out.append("\n\n")
                continue
            if _noise(x, st):
                continue
            if t in _HEADS:
                s = _flat(x)
                if s:
                    out.append("\n\n" + "#" * min(_HEADS[t] + 1, 6) + " " + s + "\n\n")
                continue
            if t == "li":
                s = _flat(x)
                if s:
                    out.append("\n- " + s + "\n")
                continue
            if t == "pre":
                s = "".join(_texts_in_order(x))
                if s.strip():
                    out.append("\n\n```\n" + s.strip("\n") + "\n```\n\n")
                continue
            if t == "table":
                rows = []
                for tr in (y for y in _walk(x) if y.tag == "tr"):
                    cells = {i: _flat(td) for i, td in enumerate(k for k in tr.kids
                                                                  if isinstance(k, _N) and k.tag in ("td", "th"))}
                    cells = {i: v for i, v in cells.items() if v}
                    if cells:
                        rows.append(cells)
                if rows:
                    out.append("\n\n" + _md_table(rows) + "\n\n")
                continue
        block = t in _BLOCK
        if block:
            stack.append(("text", "\n\n"))
        for k in reversed(x.kids):
            stack.append(("node", k))
        if block:
            out.append("\n\n")
    text = "".join(out)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _texts_in_order(n):
    out = []

    def rec(x, depth=0):
        for k in x.kids:
            if isinstance(k, str):
                out.append(k)
            elif depth < 200:
                if k.tag == "br":
                    out.append("\n")
                rec(k, depth + 1)
    rec(n)
    return out


def _all_paragraphs(root, st):
    """兜底：整页所有段落（跳过导航、评论这些）。"""
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n is not root and _noise(n, st):
            continue
        if n.tag in ("p", "h1", "h2", "h3", "h4", "li", "pre", "blockquote"):
            s = _flat(n)
            if len(s) >= 8:
                out.append(s)
            continue
        if n.tag in ("div", "section", "td", "span") and st.get(id(n), (0, 0, 0, 0))[3] >= 40:
            s = _flat(n)
            if s:
                out.append(s)
            continue
        stack.extend(k for k in reversed(n.kids) if isinstance(k, _N))
    return "\n\n".join(out)


def _by_id(root, ident):
    for n in _walk(root):
        if n.attrs.get("id") == ident:
            return n
    return None


def _first(root, tag):
    for n in _walk(root):
        if n.tag == tag:
            return n
    return None


def _site_title(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    parts = [x.strip() for x in re.split(r"\s+[-|–—_]\s+|_|\|", t) if x.strip()]
    if len(parts) > 1:
        return parts[0] if len(parts[0]) >= 6 else max(parts, key=len)
    return t


def _fmt_date(v):
    v = (v or "").strip()
    if re.fullmatch(r"\d{10}", v):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(v)))
    m = re.match(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?(?:[T\s]+(\d{1,2}):(\d{2}))?", v)
    if not m:
        return ""
    s = "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    return s + (" %02d:%s" % (int(m.group(4)), m.group(5)) if m.group(4) else "")


_EMBEDS = [
    (re.compile(r"player\.bilibili\.com/.*?[?&]bvid=(BV\w+)"), "https://www.bilibili.com/video/%s"),
    (re.compile(r"player\.bilibili\.com/.*?[?&]aid=(\d+)"), "https://www.bilibili.com/video/av%s"),
    (re.compile(r"youtube(?:-nocookie)?\.com/embed/([\w-]{6,})"), "https://www.youtube.com/watch?v=%s"),
    (re.compile(r"v\.qq\.com/(?:txp/iframe/player\.html|iframe/player\.html).*?[?&]vid=(\w+)"),
     "https://v.qq.com/x/page/%s.html"),
    (re.compile(r"player\.youku\.com/embed/([\w=]+)"), "https://v.youku.com/v_show/id_%s.html"),
    (re.compile(r"player\.vimeo\.com/video/(\d+)"), "https://vimeo.com/%s"),
    (re.compile(r"ixigua\.com/iframe/(\d+)"), "https://www.ixigua.com/%s"),
    (re.compile(r"open\.douyin\.com/player/video\?vid=(\d+)"), "https://www.douyin.com/video/%s"),
]


def _video_link(u):
    for rx, fmt in _EMBEDS:
        m = rx.search(u)
        if m:
            return fmt % m.group(1)
    return u


def _page_videos(tree, base):
    out = []

    def add(u, need_host=False):
        u = (u or "").strip()
        if not u or u.startswith(("blob:", "data:", "javascript:", "about:")):
            return
        u = _video_link(urllib.parse.urljoin(base or "", u))
        if not u.startswith("http"):
            return
        h, path = _host(u), urllib.parse.urlparse(u).path.lower()
        if need_host and not (_host_in(h, VIDEO_HOSTS) or path.endswith(MEDIA_EXTS)):
            return
        if u not in out:
            out.append(u)
    for k in ("og:video", "og:video:url", "og:video:secure_url", "twitter:player:stream"):
        add(tree.meta.get(k))
    for s in tree.videos:
        add(s)
    for s in tree.iframes:
        add(s, need_host=True)
    return out[:8]


def parse_article(html_text, url=""):
    """网页 HTML → {title, author, published, site, text, videos, wechat, blocked?, gone?}"""
    tree = _Tree()
    try:
        tree.feed(html_text or "")
        tree.close()
    except Exception:
        pass
    raw, meta = html_text or "", tree.meta
    host = _host(url)
    wechat = host == "mp.weixin.qq.com" or ('id="js_content"' in raw and "rich_media" in raw)
    res = {"title": "", "author": "", "published": "", "site": meta.get("og:site_name", ""), "text": "",
           "videos": [], "wechat": wechat, "video_page": (meta.get("og:type") or "").startswith("video")}
    if wechat:
        if "环境异常" in raw and ("去验证" in raw or "完成验证" in raw):
            res["blocked"] = "公众号要先做人机验证才给看"
        for w in ("该内容已被发布者删除", "此内容因违规无法查看", "该内容因违规无法查看", "此内容被投诉且经审核涉嫌侵权",
                  "该公众号已迁移", "此帐号已被屏蔽"):
            if w in raw:
                res["gone"] = "这篇公众号文章看不了了（%s）" % w
    st, order = _stats(tree.root)
    node = _by_id(tree.root, "js_content") if wechat else None
    if node is None:
        node = _best(tree.root, st, order)
    text = _render(node, st) if node is not None else ""
    if len(text) < 150:
        alt = _all_paragraphs(tree.root, st)
        if len(alt) > len(text) * 1.5:
            text = alt
    res["text"] = text
    title = ""
    if wechat:
        m = re.search(r"var\s+msg_title\s*=\s*(['\"])(.*?)\1", raw)
        title = _html.unescape(m.group(2)) if m else ""
        title = title or _flat(_by_id(tree.root, "activity-name"))
    title = title or meta.get("og:title") or meta.get("twitter:title") or ""
    if not title:
        h1 = (_first(node, "h1") if node is not None else None) or _first(tree.root, "h1")
        title = _flat(h1)
    res["title"] = re.sub(r"\s+", " ", title or _site_title(tree.title)).strip()[:120]
    author = ""
    if wechat:
        m = re.search(r"var\s+nickname\s*=\s*(?:htmlDecode\()?\s*(['\"])(.*?)\1", raw)
        author = _html.unescape(m.group(2)) if m else ""
        author = author or _flat(_by_id(tree.root, "js_name"))
    if not author:
        for k in ("author", "article:author", "og:article:author", "byl", "dc.creator", "sailthru.author"):
            v = (meta.get(k) or "").strip()
            if v and not v.startswith("http") and len(v) <= 40:
                author = v
                break
    res["author"] = re.sub(r"\s+", " ", author).strip()[:40]
    pub = ""
    if wechat:
        m = re.search(r"var\s+ct\s*=\s*[\"']?(\d{10})", raw)
        pub = _fmt_date(m.group(1)) if m else ""
    for k in ("article:published_time", "og:release_date", "pubdate", "publishdate", "publish_date",
              "datepublished", "article:published", "date"):
        if pub:
            break
        pub = _fmt_date(meta.get(k) or "")
    res["published"] = pub
    res["videos"] = _page_videos(tree, url)
    return res


def html_to_text(html_text):
    """整页文字（电子书章节用）：不挑正文，全部按顺序转成文字。"""
    tree = _Tree()
    try:
        tree.feed(html_text or "")
        tree.close()
    except Exception:
        pass
    return _render(tree.root, {})


# ════════════════ 网页 → 下载 ════════════════

def _proxy():
    try:
        import creator_watch
        return creator_watch._proxy() or ""
    except Exception:
        return ""


def _cn_host(host):
    return bool(re.fullmatch(r"[\d.]+|localhost", host or "")) or any(
        host.endswith(h) for h in _CN_HOSTS)


def _get(url, proxy, timeout, limit):
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    try:
        from curl_cffi import requests as creq
        kw = {"headers": h, "timeout": timeout, "impersonate": "chrome", "allow_redirects": True}
        if proxy:
            kw["proxies"] = {"http": proxy, "https": proxy}
        r = creq.get(url, **kw)
        if r.status_code >= 400:
            raise RuntimeError("网站返回 HTTP %s" % r.status_code)
        return r.content[:limit], str(r.url), r.headers.get("content-type", "") or ""
    except ImportError:
        pass
    import gzip
    import zlib
    h["Accept-Encoding"] = "gzip, deflate"
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    req = urllib.request.Request(url, headers=h)
    with urllib.request.build_opener(*handlers).open(req, timeout=timeout) as r:
        data = r.read(limit)
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            data = gzip.decompress(data)
        elif enc == "deflate":
            try:
                data = zlib.decompress(data)
            except zlib.error:
                data = zlib.decompress(data, -zlib.MAX_WBITS)
        return data, r.geturl(), r.headers.get("Content-Type", "") or ""


def _fetch(url, timeout=20, limit=60 * 1024 * 1024):
    """下载网页 / 文件：国内网站先直连，国外网站先走软件里设置的代理；不通就换另一种再试。"""
    px = _proxy()
    order = [""] if not px else (["", px] if _cn_host(_host(url)) else [px, ""])
    last = None
    for p in order:
        try:
            return _get(url, p, timeout, limit)
        except Exception as e:
            last = e
    msg = str(last) or type(last).__name__
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        msg = "连接超时" + ("" if px else "（国外网站要在「设置 → 联网与代理」里设好代理）")
    raise _Fail("网页打不开：%s" % msg[:160])


_CTYPE_EXT = {"application/pdf": ".pdf", "application/msword": ".doc", "application/vnd.ms-excel": ".xls",
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
              "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
              "application/epub+zip": ".epub", "text/csv": ".csv", "text/markdown": ".md",
              "application/rtf": ".rtf", "text/rtf": ".rtf"}


def _file_ext(url, ctype, data):
    ct = (ctype or "").split(";")[0].strip().lower()
    if ct in _CTYPE_EXT:
        return _CTYPE_EXT[ct]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if ext in KINDS and ext not in (".html", ".htm") and not (data or b"").lstrip()[:15].lower().startswith(
            (b"<!doctype", b"<html")):
        return ext
    if (data or b"")[:5] == b"%PDF-":
        return ".pdf"
    return ""


def _looks_mojibake(s):
    """UTF-8 的中文被当成西文解码后的样子（满屏 æ ä ç è…）。"""
    sample = re.sub(r"<[^>]*>|\s", "", (s or "")[:200000])[:20000]
    if len(sample) < 20:
        return False
    bad = len(re.findall("[\u00c0-\u00ff\u0080-\u009f]", sample))
    return bad > len(sample) * 0.08 and not re.search("[\u4e00-\u9fff]{4}", sample)


def _fix_mojibake(s):
    if not _looks_mojibake(s):
        return s
    try:
        b = bytearray()
        for ch in s.replace("&nbsp;", "\u00a0"):       # 浏览器把 0xA0 这个字节写成了 &nbsp;，先还原
            o = ord(ch)
            if o < 256:
                b.append(o)
            else:
                b += ch.encode("cp1252", "ignore")
        t = b.decode("utf-8", "replace")
    except Exception:
        return s
    cjk = len(re.findall("[\u4e00-\u9fff]", t))
    return t if cjk >= 10 and t.count("\ufffd") <= max(3, len(t) // 200) else s


def _browser_html(url, cb):
    """有的网页要浏览器跑完脚本才有正文：在后台开一个看不见的浏览器打开，拿到页面再读。"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None, "没装浏览器组件"
    _step(cb, "读取网页", "这个网页要在浏览器里才显示正文，正在后台打开…（十几秒）")
    pw = browser = None
    px = "" if _cn_host(_host(url)) else _proxy()
    try:
        pw = sync_playwright().start()
        for ch in ("chrome", "msedge", None):
            try:
                kw = dict(headless=True, args=["--disable-blink-features=AutomationControlled", "--mute-audio"])
                if ch:
                    kw["channel"] = ch
                if px:
                    kw["proxy"] = {"server": px}
                browser = pw.chromium.launch(**kw)
                break
            except Exception:
                continue
        if browser is None:
            return None, "没有可用的浏览器（Chrome / Edge）"
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        try:
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1200)
        except Exception:
            pass
        return _fix_mojibake(page.content()), page.url
    except Exception as e:
        return None, "后台浏览器打开网页失败：%s" % str(e).split("\n")[0][:120]
    finally:
        for obj, m in ((browser, "close"), (pw, "stop")):
            try:
                if obj is not None:
                    getattr(obj, m)()
            except Exception:
                pass


def extract_url(text, progress_cb=None):
    """网页链接 → 和视频提取一样的结果。读不到正文时 try_video=True（让上层再当视频试一次）。"""
    url = first_url(text)
    if not url:
        return {"ok": False, "error": "没找到链接"}
    _step(progress_cb, "读取网页", "正在打开网页…")
    data = final = ctype = None
    err = ""
    try:
        data, final, ctype = _fetch(url)
    except _Fail as e:
        err = str(e)
    final = final or url
    src = final if _host_in(_host(url), _SHORTENERS) else url
    if data is not None:
        ext = _file_ext(final, ctype, data)
        if ext:                                       # 链接直接是文件（PDF / Word / Excel…）
            _step(progress_cb, "读取文档", "链接是一个%s，下载好了，正在读…" % KINDS.get(ext, "文件"))
            fd, tmp = tempfile.mkstemp(suffix=ext)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                res = extract_file(tmp, progress_cb)
            finally:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            if res.get("ok"):
                name = urllib.parse.unquote(os.path.splitext(os.path.basename(urllib.parse.urlparse(final).path))[0])
                if res["title"] in ("导入的文档",) or re.fullmatch(r"tmp\w*", res["title"] or ""):
                    res["title"] = name or res["title"]
                res.update(url=src, local_path="")
            return res
    art = None
    if data is not None:
        html_text = _decode(data, (re.search(r"charset=([\w-]+)", ctype or "", re.I) or [None, ""])[1]
                            or _meta_charset(data))
        art = parse_article(html_text, final)
        if art.get("blocked"):
            err = art["blocked"]
    if art is not None and art.get("gone"):
        return {"ok": False, "error": art["gone"]}
    t1 = len((art or {}).get("text") or "")
    wx_ok = bool(art) and art.get("wechat") and t1 >= 50 and not art.get("blocked")   # 公众号正文是直接写在页面里的
    if art is None or art.get("blocked") or (t1 < 200 and not wx_ok):
        h2, f2 = _browser_html(url, progress_cb)
        if h2:
            art2 = parse_article(h2, f2 or final)
            if art2.get("gone"):
                return {"ok": False, "error": art2["gone"]}
            t2 = len(art2.get("text") or "")
            if not art2.get("blocked") and (art is None or art.get("blocked") or t1 < 80 or t2 > max(t1 * 1.3, t1 + 100)):
                art = art2                       # 浏览器读到的明显更多，才用它的
            elif art2.get("blocked"):
                err = art2["blocked"]
        elif not err and art is None:
            err = f2
    text = _tidy((art or {}).get("text") or "")
    if len(text) < 80:
        why = err or "这个网页没读到正文（可能要登录才能看，或者主要是图片 / 视频）"
        return {"ok": False, "error": why, "try_video": True, "page_videos": (art or {}).get("videos") or []}
    text, cut = _cap(text)
    kind = "公众号文章" if art.get("wechat") else "网页文章"
    return {"ok": True, "title": art.get("title") or "（无标题）", "uploader": art.get("author") or "",
            "url": src, "transcript": text, "segments": [], "source": "article", "doc_kind": kind,
            "src_noun": "文章", "published": art.get("published") or "", "site": art.get("site") or "",
            "page_videos": [v for v in (art.get("videos") or []) if v != src], "truncated": cut}
