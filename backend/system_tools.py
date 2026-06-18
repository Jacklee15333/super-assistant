"""
system_tools.py — 电脑操作能力（受「电脑操作权限」总开关控制）

总开关存在：backend/memory/system_access.json   ->  {"enabled": true/false}
  · 关闭（默认）：本文件里所有工具一律拒绝执行；同时 tools.py 的文件读写被锁回沙箱。
  · 开启：可操作真实文件系统、系统设置、GUI、看屏幕。开关由界面右上角的按钮控制。

二级安全（保留你原有的设计）：
  · 破坏性操作标 "danger"，每次执行前界面会弹窗让你逐个确认/拒绝。
  · 只读类操作标 "safe"，但权限关着时同样被冻结。

可选依赖（缺了不会崩，只会提示你装哪个包）：
  pip install psutil pyautogui pillow mss pytesseract pycaw comtypes send2trash
"""

import os
import sys
import json
import shutil
import platform
import subprocess
import datetime
from pathlib import Path

try:
    from agent_core import MEMORY_DIR
except Exception:
    MEMORY_DIR = Path(__file__).parent / "memory"
    MEMORY_DIR.mkdir(exist_ok=True)

IS_WIN = platform.system() == "Windows"
FLAG_PATH = MEMORY_DIR / "system_access.json"
SHOT_DIR = MEMORY_DIR / "screenshots"


# ══════════════════════════ 总开关 ══════════════════════════
def is_enabled() -> bool:
    """读「电脑操作权限」开关。默认关闭。每次调用都现读文件，保证和界面同步。"""
    try:
        if FLAG_PATH.exists():
            data = json.loads(FLAG_PATH.read_text(encoding="utf-8"))
            return bool(data.get("enabled", False))
    except Exception:
        pass
    return False


def set_enabled(flag: bool) -> bool:
    """写开关（界面/IPC 调用）。返回写入后的状态。"""
    try:
        FLAG_PATH.write_text(
            json.dumps({"enabled": bool(flag),
                        "updated": datetime.datetime.now().isoformat(timespec="seconds")},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass
    return bool(flag)


_DENIED = ("拒绝：电脑操作权限未开启。请点界面右上角的「电脑操作权限」开关打开后再试。"
           "（关着时我只能在沙箱目录里活动，不能动你真实的桌面/下载/系统。）")


def _guard():
    """权限闸门：开着返回 None，关着返回拒绝文案。"""
    return None if is_enabled() else _DENIED


# ══════════════════════════ 小工具 ══════════════════════════
def _resolve(path: str) -> Path:
    """把用户给的路径解析成绝对路径（支持 ~、环境变量、相对当前目录）。"""
    path = os.path.expandvars(os.path.expanduser((path or "").strip()))
    p = Path(path)
    if not p.is_absolute():
        p = Path.home() / path
    return p


def _human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


def _decode_bytes(b):
    """解码命令输出。Windows 上：PowerShell 已被上层强制 UTF-8 输出，
    传统 cmd 工具（tasklist 等）多为 GBK —— 先按 UTF-8 严格解，失败再回退 GBK，
    两边都能正确显示中文，根治“UTF-8 当 GBK 解”的乱码。"""
    if not b:
        return ""
    if IS_WIN:
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return b.decode("gbk", "replace")
    return b.decode("utf-8", "replace")


def _clean_clixml(s):
    """去掉 PowerShell 在重定向输出时混进来的 CLIXML/进度噪音，
    并把其中的报错/警告抽成可读中文，方便模型据此修正、也不污染界面。"""
    if not s or ("CLIXML" not in s and "<Objs" not in s and "Preparing modules" not in s):
        return s
    import re as _re

    def _unesc(t):
        t = (t.replace("_x000D__x000A_", "\n").replace("_x000A_", "\n")
             .replace("_x000D_", ""))
        return _re.sub(r"_x([0-9A-Fa-f]{4})_",
                       lambda m: chr(int(m.group(1), 16)), t)

    # 先抽出 Error / Warning 文本
    msgs = _re.findall(r'<S\s+S="(?:Error|Warning)">(.*?)</S>', s, _re.DOTALL)
    err = "".join(_unesc(m) for m in msgs).strip()
    # 去掉所有 CLIXML 块与进度对象、以及 "Preparing modules..." 噪音
    s = _re.sub(r"<Objs[\s\S]*?</Objs>", "", s)
    s = _re.sub(r"#<\s*CLIXML[^\n]*", "", s)
    s = _re.sub(r"Preparing modules for first use\.?", "", s)
    s = _re.sub(r"\n{3,}", "\n\n", s).strip()
    if err:
        s = (s + "\n" if s else "") + "（PowerShell 报错）" + err
    return s.strip()


def _run(cmd, timeout=30, cwd=None):
    """跑命令，统一捕获输出。UTF-8 优先解码 + 清理 CLIXML 噪音。cmd 可为字符串或列表。"""
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd,
                           capture_output=True, timeout=timeout)
        out = _decode_bytes(r.stdout) + _decode_bytes(r.stderr)
        out = _clean_clixml(out.strip())
        # 去掉每行尾部空格：表格对齐会留一大片尾随空格，白占长度、易触发截断
        out = "\n".join(ln.rstrip() for ln in out.split("\n"))
        return out.strip()
    except subprocess.TimeoutExpired:
        return "（命令执行超时，已中止；如果是在统计很大的目录，换更小的范围再试）"
    except Exception as e:
        return f"（命令执行出错：{e}）"


def _need(mod, pkg=None):
    """返回 (模块, 错误文案)。缺失时模块为 None。"""
    try:
        return __import__(mod), None
    except Exception:
        return None, f"需要先安装 {pkg or mod}：在 backend 目录执行  pip install {pkg or mod}"


# ══════════════════════════ 一、真实文件系统 ══════════════════════════
def tool_fs_list(args):
    d = _guard()
    if d:
        return d
    try:
        base = _resolve(args.get("path", str(Path.home())))
        if not base.exists():
            return f"目录不存在：{base}"
        if base.is_file():
            return f"{base} 是文件（{_human(base.stat().st_size)}）。"
        rows = []
        for p in sorted(base.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            try:
                if p.is_dir():
                    rows.append(f"[目录] {p.name}/")
                else:
                    rows.append(f"       {p.name}  ({_human(p.stat().st_size)})")
            except Exception:
                rows.append(f"       {p.name}")
            if len(rows) >= 300:
                rows.append("…（超过 300 项，已截断）")
                break
        return f"{base}\n" + ("\n".join(rows) if rows else "（空目录）")
    except Exception as e:
        return f"列目录出错：{e}"


def tool_fs_read(args):
    d = _guard()
    if d:
        return d
    try:
        p = _resolve(args.get("path", ""))
        if not p.exists():
            return f"文件不存在：{p}"
        if p.is_dir():
            return "这是目录，请用 fs_list。"
        if p.stat().st_size > 2_000_000:
            return f"文件太大（{_human(p.stat().st_size)}，上限 2MB），不读。"
        return p.read_text(encoding="utf-8", errors="replace")[:12000]
    except Exception as e:
        return f"读取出错：{e}"


def tool_fs_search(args):
    d = _guard()
    if d:
        return d
    try:
        root = _resolve(args.get("path", str(Path.home())))
        kw = (args.get("keyword", "") or "").strip().lower()
        if not kw:
            return "拒绝：关键词为空。"
        hits = []
        for p in root.rglob("*"):
            try:
                if kw in p.name.lower():
                    hits.append(str(p))
                    if len(hits) >= 80:
                        hits.append("…（结果过多，已截断）")
                        break
            except Exception:
                continue
        return "\n".join(hits) if hits else f"在 {root} 下没找到含“{kw}”的文件/目录。"
    except Exception as e:
        return f"搜索出错：{e}"


def tool_fs_open(args):
    d = _guard()
    if d:
        return d
    try:
        p = _resolve(args.get("path", ""))
        if not p.exists():
            return f"路径不存在：{p}"
        if IS_WIN:
            os.startfile(str(p))  # 用系统默认程序打开文件/文件夹
        elif platform.system() == "Darwin":
            _run(["open", str(p)])
        else:
            _run(["xdg-open", str(p)])
        return f"已用默认程序打开：{p}"
    except Exception as e:
        return f"打开出错：{e}"


def tool_fs_move(args):
    d = _guard()
    if d:
        return d
    try:
        src = _resolve(args.get("src", ""))
        dst = _resolve(args.get("dst", ""))
        if not src.exists():
            return f"源不存在：{src}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"已移动/重命名：{src} → {dst}"
    except Exception as e:
        return f"移动出错：{e}"


def tool_fs_copy(args):
    d = _guard()
    if d:
        return d
    try:
        src = _resolve(args.get("src", ""))
        dst = _resolve(args.get("dst", ""))
        if not src.exists():
            return f"源不存在：{src}"
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
        return f"已复制：{src} → {dst}"
    except Exception as e:
        return f"复制出错：{e}"


def tool_fs_mkdir(args):
    d = _guard()
    if d:
        return d
    try:
        p = _resolve(args.get("path", ""))
        p.mkdir(parents=True, exist_ok=True)
        return f"已创建目录：{p}"
    except Exception as e:
        return f"创建出错：{e}"


def tool_fs_trash(args):
    """删到回收站（不直接抹掉，可恢复）。需要 send2trash。"""
    d = _guard()
    if d:
        return d
    try:
        p = _resolve(args.get("path", ""))
        if not p.exists():
            return f"路径不存在：{p}"
        s2t, err = _need("send2trash")
        if s2t is None:
            return (f"为安全起见我不直接硬删除。{err}。"
                    "装好后我就能把它移到回收站（可恢复）。")
        s2t.send2trash(str(p))
        return f"已移到回收站（可在回收站恢复）：{p}"
    except Exception as e:
        return f"删除出错：{e}"


def tool_fs_organize(args):
    """把一个文件夹（如桌面）按文件类型归类到子文件夹。"""
    d = _guard()
    if d:
        return d
    try:
        folder = _resolve(args.get("path", str(Path.home() / "Desktop")))
        if not folder.is_dir():
            return f"不是有效目录：{folder}"
        cats = {
            "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"},
            "文档": {".doc", ".docx", ".pdf", ".txt", ".md", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"},
            "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz"},
            "音视频": {".mp3", ".wav", ".flac", ".mp4", ".mov", ".avi", ".mkv"},
            "安装包": {".exe", ".msi", ".dmg", ".apk"},
            "代码": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".html", ".css", ".json"},
        }
        moved, logs = 0, []
        for p in list(folder.iterdir()):
            if p.is_dir():
                continue
            ext = p.suffix.lower()
            cat = next((c for c, s in cats.items() if ext in s), "其他")
            target = folder / cat
            target.mkdir(exist_ok=True)
            try:
                shutil.move(str(p), str(target / p.name))
                moved += 1
            except Exception as e:
                logs.append(f"跳过 {p.name}：{e}")
        msg = f"已整理 {folder}，归类移动了 {moved} 个文件。"
        if logs:
            msg += "\n" + "\n".join(logs[:10])
        return msg
    except Exception as e:
        return f"整理出错：{e}"


# ══════════════════════════ 二、系统级操作 ══════════════════════════
def tool_sys_info(_args=None):
    d = _guard()
    if d:
        return d
    lines = [f"系统：{platform.platform()}", f"主机名：{platform.node()}"]
    ps, _ = _need("psutil")
    if ps:
        try:
            lines.append(f"CPU 使用率：{ps.cpu_percent(interval=0.4)}%")
            vm = ps.virtual_memory()
            lines.append(f"内存：已用 {_human(vm.used)} / 共 {_human(vm.total)}（{vm.percent}%）")
            try:
                b = ps.sensors_battery()
                if b:
                    lines.append(f"电池：{b.percent}%（{'充电中' if b.power_plugged else '使用电池'}）")
            except Exception:
                pass
        except Exception:
            pass
    # 磁盘（标准库即可）
    for part in (["C:\\", "D:\\"] if IS_WIN else ["/"]):
        try:
            t, u, f = shutil.disk_usage(part)
            lines.append(f"磁盘 {part}：已用 {_human(u)} / 共 {_human(t)}，剩余 {_human(f)}")
        except Exception:
            pass
    return "\n".join(lines)


def tool_sys_processes(args):
    d = _guard()
    if d:
        return d
    top = int(args.get("top", 12) or 12)
    ps, err = _need("psutil")
    if ps is None:
        # 退化：用系统命令
        return _run("tasklist" if IS_WIN else "ps aux --sort=-%mem | head -15")[:3000] or err
    rows = []
    for p in ps.process_iter(["pid", "name", "memory_info"]):
        try:
            rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
            rows.append((rss, p.info["pid"], p.info["name"] or "?"))
        except Exception:
            continue
    rows.sort(reverse=True)
    out = [f"{'PID':>7}  {'内存':>9}  名称"]
    for rss, pid, name in rows[:top]:
        out.append(f"{pid:>7}  {_human(rss):>9}  {name}")
    return "\n".join(out)


def tool_sys_kill(args):
    d = _guard()
    if d:
        return d
    target = str(args.get("target", "")).strip()
    if not target:
        return "拒绝：需要进程名或 PID。"
    if target.isdigit():
        if IS_WIN:
            return _run(f'taskkill /PID {target} /F') or "已尝试结束。"
        return _run(f"kill -9 {target}") or "已尝试结束。"
    if IS_WIN:
        name = target if target.lower().endswith(".exe") else target + ".exe"
        return _run(f'taskkill /IM "{name}" /F') or "已尝试结束。"
    return _run(f"pkill -9 -f {target}") or "已尝试结束。"


def tool_sys_clean_temp(_args=None):
    d = _guard()
    if d:
        return d
    targets = []
    if IS_WIN:
        for v in ("TEMP", "TMP"):
            if os.environ.get(v):
                targets.append(Path(os.environ[v]))
        targets.append(Path(os.environ.get("WINDIR", "C:\\Windows")) / "Temp")
    else:
        targets.append(Path("/tmp"))
    seen, freed, removed, skipped = set(), 0, 0, 0
    for t in targets:
        if not t.exists() or str(t) in seen:
            continue
        seen.add(str(t))
        try:
            entries = list(t.iterdir())
        except Exception:
            continue
        for p in entries:
            try:
                sz = p.stat().st_size if p.is_file() else 0
                if p.is_file():
                    p.unlink()
                else:
                    shutil.rmtree(p, ignore_errors=True)
                freed += sz
                removed += 1
            except (PermissionError, OSError):
                # 正被占用、或系统保护的文件——跳过，属正常，不是失败
                skipped += 1
                continue
            except Exception:
                skipped += 1
                continue
    # 顺手清空回收站（Windows）
    recycle_note = ""
    if IS_WIN:
        try:
            r = _run('powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"')
            recycle_note = "，并已尝试清空回收站"
        except Exception:
            pass
    msg = (f"已清理临时目录 {len(seen)} 处，删除约 {removed} 项，"
           f"释放约 {_human(freed)}{recycle_note}。")
    if skipped:
        msg += f"（有 {skipped} 项正被占用或受系统保护，已自动跳过——这是正常现象，不影响清理结果。）"
    return msg


def tool_empty_recycle_bin(_args=None):
    """清空回收站（彻底删除回收站里的内容）。这是「清空回收站」的专用工具，
    和 fs_trash（把文件移进回收站）正好相反，不要混用。"""
    d = _guard()
    if d:
        return d
    if IS_WIN:
        try:
            # PowerShell 的 Clear-RecycleBin 是清空回收站的官方方式
            out = _run('powershell -NoProfile -Command '
                       '"Clear-RecycleBin -Force -ErrorAction SilentlyContinue; '
                       'Write-Output OK"')
            if out is not None:
                return "已清空回收站。（如果原本就是空的，也算完成。）"
            return "已尝试清空回收站。"
        except Exception as e:
            return f"清空回收站时出错：{e}"
    else:
        # macOS / Linux：尝试清空用户回收站目录
        candidates = [
            Path.home() / ".local/share/Trash/files",
            Path.home() / ".Trash",
        ]
        removed = 0
        for trash in candidates:
            if trash.exists():
                for p in list(trash.iterdir()):
                    try:
                        if p.is_file() or p.is_symlink():
                            p.unlink()
                        else:
                            shutil.rmtree(p, ignore_errors=True)
                        removed += 1
                    except Exception:
                        continue
        return f"已清空回收站，删除约 {removed} 项。" if removed else "回收站已经是空的。"


def tool_sys_volume(args):
    d = _guard()
    if d:
        return d
    val = str(args.get("level", "")).strip()
    if not IS_WIN:
        return "当前只在 Windows 上支持调音量。"
    if val.lower() in ("mute", "静音"):
        return _run('powershell -c "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"') or "已切换静音。"
    try:
        level = max(0, min(100, int(val)))
    except Exception:
        return "请给 0-100 的音量值，或 mute 静音。"
    # 优先 pycaw（精确）
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        spk = AudioUtilities.GetSpeakers()
        iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"已把音量设为 {level}%。"
    except Exception:
        return ("已尝试，但精确调音量需要 pycaw：pip install pycaw comtypes。"
                "装好后我就能把音量设成你要的百分比。")


def tool_sys_brightness(args):
    d = _guard()
    if d:
        return d
    if not IS_WIN:
        return "当前只在 Windows 上支持调亮度。"
    try:
        level = max(0, min(100, int(args.get("level", 50))))
    except Exception:
        return "请给 0-100 的亮度值。"
    cmd = ('powershell -c "(Get-WmiObject -Namespace root/WMI '
           '-Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,%d)"' % level)
    out = _run(cmd)
    return f"已尝试把亮度设为 {level}%。{('（' + out + '）') if out else ''}"


_SETTINGS_MAP = {
    "wifi": "ms-settings:network-wifi", "网络": "ms-settings:network",
    "蓝牙": "ms-settings:bluetooth", "显示": "ms-settings:display",
    "声音": "ms-settings:sound", "电池": "ms-settings:batterysaver",
    "更新": "ms-settings:windowsupdate", "存储": "ms-settings:storagesense",
    "应用": "ms-settings:appsfeatures", "个性化": "ms-settings:personalization",
    "首页": "ms-settings:",
}


def tool_sys_open_settings(args):
    d = _guard()
    if d:
        return d
    if not IS_WIN:
        return "当前只在 Windows 上支持打开系统设置。"
    which = str(args.get("which", "首页")).strip()
    uri = _SETTINGS_MAP.get(which, which if which.startswith("ms-settings:") else "ms-settings:")
    _run(f'start {uri}')
    return f"已打开系统设置：{which}"


def tool_sys_run(args):
    """在指定目录跑一条命令（比沙箱 shell 更自由，仍需逐次确认）。"""
    d = _guard()
    if d:
        return d
    cmd = args.get("command", "")
    cwd = args.get("cwd", "")
    cwd_path = str(_resolve(cwd)) if cwd else None
    out = _run(cmd, timeout=60, cwd=cwd_path)
    return out[:12000] or "（无输出）"


# ══════════════════════════ 三、看屏幕 + GUI 自动化 ══════════════════════════
def _grab_screenshot():
    """返回 (PIL.Image, 错误文案)。优先 mss，其次 PIL.ImageGrab，再 pyautogui。"""
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            mon = sct.monitors[0]
            raw = sct.grab(mon)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return img, None
    except Exception:
        pass
    try:
        from PIL import ImageGrab
        return ImageGrab.grab(), None
    except Exception:
        pass
    try:
        import pyautogui
        return pyautogui.screenshot(), None
    except Exception:
        pass
    return None, "截屏需要安装其一：pip install mss pillow（推荐），或 pyautogui。"


def tool_gui_screenshot(_args=None):
    d = _guard()
    if d:
        return d
    img, err = _grab_screenshot()
    if img is None:
        return err
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = SHOT_DIR / f"shot-{ts}.png"
    try:
        img.save(out)
    except Exception as e:
        return f"截屏成功但保存失败：{e}"
    return f"已截屏：{out}（{img.size[0]}x{img.size[1]}）。可用 screen_read 提取屏幕文字。"


def tool_screen_read(_args=None):
    """截屏 + OCR，把屏幕上的文字读出来给模型理解（看得到屏幕的闭环）。"""
    d = _guard()
    if d:
        return d
    img, err = _grab_screenshot()
    if img is None:
        return err
    try:
        import pytesseract
    except Exception:
        return ("已截到屏，但要把画面里的文字读出来需要 OCR：pip install pytesseract，"
                "并安装 Tesseract-OCR（含中文语言包 chi_sim）。装好后我就能看懂屏幕内容。")
    try:
        txt = pytesseract.image_to_string(img, lang="chi_sim+eng")
    except Exception:
        txt = pytesseract.image_to_string(img)  # 没装中文包时退英文
    txt = (txt or "").strip()
    return ("屏幕上识别到的文字：\n" + txt[:4000]) if txt else "屏幕上没识别到明显文字。"


def _pyautogui():
    pg, err = _need("pyautogui")
    if pg is not None:
        try:
            pg.FAILSAFE = True  # 鼠标甩到左上角可急停
        except Exception:
            pass
    return pg, err


def tool_gui_open_app(args):
    d = _guard()
    if d:
        return d
    name = str(args.get("name", "")).strip()
    if not name:
        return "拒绝：需要应用名或可执行文件路径。"
    try:
        if IS_WIN:
            # 既支持 "notepad" 这种名字，也支持完整 exe 路径
            _run(f'start "" "{name}"' if (":" in name or name.endswith(".exe")) else f'start {name}')
        elif platform.system() == "Darwin":
            _run(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return f"已尝试打开应用：{name}"
    except Exception as e:
        return f"打开应用出错：{e}"


def tool_gui_click(args):
    d = _guard()
    if d:
        return d
    pg, err = _pyautogui()
    if pg is None:
        return err
    try:
        x = int(args.get("x")); y = int(args.get("y"))
    except Exception:
        return "需要坐标 x、y（整数像素）。可先用 screen_read/gui_locate 找位置。"
    clicks = 2 if str(args.get("double", "")).lower() in ("1", "true", "yes") else 1
    button = args.get("button", "left")
    pg.click(x=x, y=y, clicks=clicks, button=button)
    return f"已在 ({x},{y}) {'双击' if clicks == 2 else '单击'}（{button}）。"


def tool_gui_type(args):
    d = _guard()
    if d:
        return d
    pg, err = _pyautogui()
    if pg is None:
        return err
    text = str(args.get("text", ""))
    if not text:
        return "拒绝：要输入的文本为空。"
    # pyautogui 对中文直接 typewrite 不稳，走剪贴板粘贴更稳
    try:
        import pyperclip
        pyperclip.copy(text)
        pg.hotkey("ctrl", "v")
        return f"已通过粘贴输入 {len(text)} 个字符。"
    except Exception:
        pg.typewrite(text, interval=0.02)
        return f"已逐字输入 {len(text)} 个字符（建议装 pyperclip 让中文输入更稳）。"


def tool_gui_press(args):
    d = _guard()
    if d:
        return d
    pg, err = _pyautogui()
    if pg is None:
        return err
    keys = str(args.get("keys", "")).replace("，", ",")
    parts = [k.strip() for k in keys.split(",") if k.strip()]
    if not parts:
        return "拒绝：需要按键，如 enter 或 ctrl,s。"
    if len(parts) == 1:
        pg.press(parts[0])
    else:
        pg.hotkey(*parts)
    return f"已按键：{'+'.join(parts)}"


def tool_gui_scroll(args):
    d = _guard()
    if d:
        return d
    pg, err = _pyautogui()
    if pg is None:
        return err
    try:
        amount = int(args.get("amount", -400))
    except Exception:
        amount = -400
    pg.scroll(amount)
    return f"已滚动 {amount}（正上负下）。"


def tool_gui_locate(args):
    """在屏幕上找一张模板小图的位置，返回中心坐标。需要 opencv。"""
    d = _guard()
    if d:
        return d
    pg, err = _pyautogui()
    if pg is None:
        return err
    img = args.get("image", "")
    p = _resolve(img)
    if not p.exists():
        return f"模板图不存在：{p}"
    try:
        box = pg.locateCenterOnScreen(str(p), confidence=float(args.get("confidence", 0.8)))
    except TypeError:
        box = pg.locateCenterOnScreen(str(p))  # 没装 opencv 时不支持 confidence
    except Exception as e:
        return f"查找出错：{e}（图像匹配需要 pip install opencv-python）"
    if not box:
        return "没在当前屏幕上找到这张图。"
    return f"找到了，中心坐标：x={int(box.x)}, y={int(box.y)}。可用 gui_click 点它。"


# ══════════════════════════ 注册表 + schema ══════════════════════════
# 名称 -> (函数, 危险等级)。危险的会在界面逐次弹窗确认。
SYSTEM_TOOLS = {
    # 真实文件系统（只读 safe）
    "fs_list": (tool_fs_list, "safe"),
    "fs_read": (tool_fs_read, "safe"),
    "fs_search": (tool_fs_search, "safe"),
    # 真实文件系统（有副作用 danger）
    "fs_open": (tool_fs_open, "danger"),
    "fs_move": (tool_fs_move, "danger"),
    "fs_copy": (tool_fs_copy, "danger"),
    "fs_mkdir": (tool_fs_mkdir, "danger"),
    "fs_trash": (tool_fs_trash, "danger"),
    "fs_organize": (tool_fs_organize, "danger"),
    # 系统级
    "sys_info": (tool_sys_info, "safe"),
    "sys_processes": (tool_sys_processes, "safe"),
    "sys_kill": (tool_sys_kill, "danger"),
    "sys_clean_temp": (tool_sys_clean_temp, "danger"),
    "empty_recycle_bin": (tool_empty_recycle_bin, "danger"),
    "sys_volume": (tool_sys_volume, "danger"),
    "sys_brightness": (tool_sys_brightness, "danger"),
    "sys_open_settings": (tool_sys_open_settings, "danger"),
    "sys_run": (tool_sys_run, "danger"),
    # 看屏幕 + GUI
    "gui_screenshot": (tool_gui_screenshot, "safe"),
    "screen_read": (tool_screen_read, "safe"),
    "gui_locate": (tool_gui_locate, "safe"),
    "gui_open_app": (tool_gui_open_app, "danger"),
    "gui_click": (tool_gui_click, "danger"),
    "gui_type": (tool_gui_type, "danger"),
    "gui_press": (tool_gui_press, "danger"),
    "gui_scroll": (tool_gui_scroll, "danger"),
}


def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object",
                       "properties": props or {},
                       **({"required": required} if required else {})}}}

_S = {"type": "string"}
_I = {"type": "integer"}

SYSTEM_SCHEMA = [
    _fn("fs_list", "【需电脑操作权限】列出任意目录下的文件/子目录（桌面、下载、D盘项目等）。path 可写绝对路径或 ~/Desktop",
        {"path": {**_S, "description": "目录绝对路径，留空为用户主目录"}}),
    _fn("fs_read", "【需电脑操作权限】读取任意路径的文本文件内容", {"path": _S}, ["path"]),
    _fn("fs_search", "【需电脑操作权限】在某个目录下按文件名关键词递归搜索",
        {"path": {**_S, "description": "搜索起点目录"}, "keyword": _S}, ["keyword"]),
    _fn("fs_open", "【需电脑操作权限·危险】用系统默认程序打开一个文件或文件夹", {"path": _S}, ["path"]),
    _fn("fs_move", "【需电脑操作权限·危险】移动或重命名文件/文件夹", {"src": _S, "dst": _S}, ["src", "dst"]),
    _fn("fs_copy", "【需电脑操作权限·危险】复制文件/文件夹", {"src": _S, "dst": _S}, ["src", "dst"]),
    _fn("fs_mkdir", "【需电脑操作权限·危险】新建目录", {"path": _S}, ["path"]),
    _fn("fs_trash", "【需电脑操作权限·危险】把指定的文件/文件夹移到回收站（可恢复，不硬删）。"
        "注意：这是\"删某个文件\"用的；若用户要\"清空回收站\"，请用 empty_recycle_bin，不要用本工具。",
        {"path": _S}, ["path"]),
    _fn("fs_organize", "【需电脑操作权限·危险】把一个文件夹（如桌面）里的文件按类型归类到子文件夹，整理乱桌面用",
        {"path": {**_S, "description": "要整理的文件夹，默认桌面"}}),
    _fn("sys_info", "【需电脑操作权限】查看系统信息：CPU/内存/磁盘剩余/电池"),
    _fn("sys_processes", "【需电脑操作权限】列出占内存最多的进程", {"top": {**_I, "description": "前几名，默认12"}}),
    _fn("sys_kill", "【需电脑操作权限·危险】结束一个进程（按 PID 或进程名）", {"target": _S}, ["target"]),
    _fn("sys_clean_temp", "【需电脑操作权限·危险】清理系统临时文件并清空回收站，释放磁盘空间。"
        "清理 C 盘垃圾/临时文件就用这个工具，不要用 sys_run 跑 PowerShell 删除命令。"
        "正被占用或受系统保护的文件会自动跳过，属正常，不算失败。"),
    _fn("empty_recycle_bin", "【需电脑操作权限·危险】清空回收站（彻底删除回收站里的所有内容）。"
        "用户说「清空回收站」「把回收站清空/清掉」就用这个工具。"
        "注意：它和 fs_trash 相反——fs_trash 是把文件\"移进\"回收站，这个是把回收站\"倒空\"。"),
    _fn("sys_volume", "【需电脑操作权限·危险】设置系统音量（0-100，或 mute 静音）", {"level": _S}, ["level"]),
    _fn("sys_brightness", "【需电脑操作权限·危险】设置屏幕亮度（0-100）", {"level": _I}, ["level"]),
    _fn("sys_open_settings", "【需电脑操作权限·危险】打开 Windows 系统设置页（如 wifi/蓝牙/显示/声音/更新/存储）",
        {"which": _S}),
    _fn("sys_run", "【需电脑操作权限·危险】在指定目录执行一条命令（比沙箱更自由）",
        {"command": _S, "cwd": {**_S, "description": "工作目录，可留空"}}, ["command"]),
    _fn("gui_screenshot", "【需电脑操作权限】给当前屏幕截图并保存"),
    _fn("screen_read", "【需电脑操作权限】截屏并识别屏幕上的文字（让你看得到屏幕在显示什么）"),
    _fn("gui_locate", "【需电脑操作权限】在屏幕上找一张模板小图，返回它的中心坐标，便于点击",
        {"image": {**_S, "description": "模板图片路径"}, "confidence": {"type": "number"}}, ["image"]),
    _fn("gui_open_app", "【需电脑操作权限·危险】打开一个应用程序（名字或 exe 路径）", {"name": _S}, ["name"]),
    _fn("gui_click", "【需电脑操作权限·危险】在屏幕坐标点击鼠标",
        {"x": _I, "y": _I, "double": {**_S, "description": "true 为双击"},
         "button": {**_S, "description": "left/right"}}, ["x", "y"]),
    _fn("gui_type", "【需电脑操作权限·危险】在当前焦点处输入文本（自动走剪贴板，中文也稳）", {"text": _S}, ["text"]),
    _fn("gui_press", "【需电脑操作权限·危险】按下按键或组合键，如 enter 或 ctrl,s", {"keys": _S}, ["keys"]),
    _fn("gui_scroll", "【需电脑操作权限·危险】滚动鼠标滚轮（正数上滚，负数下滚）", {"amount": _I}),
]
