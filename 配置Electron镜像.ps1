# =====================================================================
#  配置 npm / Electron 国内镜像 + 共享缓存（跑一次，一劳永逸）
# ---------------------------------------------------------------------
#  解决的问题：
#    1. Electron 默认从国外下载，慢、甚至下不动。
#    2. 每个项目重复下载同一个 Electron，浪费时间和硬盘。
#  做法：
#    - npm 包走国内镜像（淘宝镜像）
#    - Electron 二进制走国内镜像
#    - 所有项目共享同一个 Electron 缓存目录（D:\electron-cache）
#      下载过一次后，以后任何项目装 Electron 都直接复用，不再下载。
#
#  跑法：右键这个文件 -> 用 PowerShell 运行；或在 PowerShell 里执行它。
#  只需跑一次。之后新建的命令行窗口都会生效。
# =====================================================================

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    chcp 65001 > $null 2>&1
} catch {}

# 包一层错误捕获：任何一步出错都停住让你看清，不闪退
$ErrorActionPreference = "Continue"
trap {
    Write-Host ""
    Write-Host "[出错了] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "把上面这行红字截图发给开发者就能定位。" -ForegroundColor Yellow
    Write-Host "按任意键退出…"
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 1
}

Write-Host "==================================="
Write-Host "  配置 npm / Electron 国内镜像 + 共享缓存"
Write-Host "==================================="
Write-Host ""

# 1. 共享缓存目录（放 D 盘，所有项目共用）
$cacheDir = "D:\electron-cache"
if (-not (Test-Path -LiteralPath $cacheDir)) {
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
    Write-Host "[1/4] 已创建共享缓存目录：$cacheDir"
} else {
    Write-Host "[1/4] 共享缓存目录已存在：$cacheDir"
}

# 2. 设为用户级永久环境变量（新开的窗口都生效）
#    ELECTRON_CACHE / electron_config_cache 控制 Electron 二进制缓存位置
[Environment]::SetEnvironmentVariable("ELECTRON_CACHE", $cacheDir, "User")
[Environment]::SetEnvironmentVariable("electron_config_cache", $cacheDir, "User")
#    Electron 二进制走国内镜像
[Environment]::SetEnvironmentVariable("ELECTRON_MIRROR", "https://npmmirror.com/mirrors/electron/", "User")
[Environment]::SetEnvironmentVariable("ELECTRON_BUILDER_BINARIES_MIRROR", "https://npmmirror.com/mirrors/electron-builder-binaries/", "User")
Write-Host "[2/4] 已设置 Electron 缓存目录和国内镜像环境变量（用户级，永久生效）"

# 3. npm 包走国内镜像
npm config set registry https://registry.npmmirror.com
Write-Host "[3/4] 已把 npm 源设为淘宝镜像（registry.npmmirror.com）"

# 4. 当前窗口也立即生效（不用重开）
$env:ELECTRON_CACHE = $cacheDir
$env:electron_config_cache = $cacheDir
$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
Write-Host "[4/4] 当前窗口也已生效"

Write-Host ""
Write-Host "完成！以后任何项目装 Electron 都会：" -ForegroundColor Green
Write-Host "  - 走国内镜像（快）"
Write-Host "  - 复用 D:\electron-cache 里的缓存（下载过一次就不再下）"
Write-Host ""
Write-Host "如果你之前已经下载过 Electron 30，想直接把它放进共享缓存，"
Write-Host "看同目录的「如何复用已下载的Electron.md」说明。"
Write-Host ""
Write-Host "按任意键退出…"
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
