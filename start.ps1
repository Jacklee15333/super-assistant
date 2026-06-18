# =====================================================================
#  Chaoneng Xiaozhu  -  Launcher + Auto-Update (PowerShell)
# ---------------------------------------------------------------------
#  All output is ASCII English ON PURPOSE, so it never shows up as
#  garbled text in Windows PowerShell under any code page (GBK/UTF-8).
#
#  Double-click qidong.bat to run this. Steps:
#    1. Process files in updates\ : auto-route each to its correct place
#    2. Set Electron China mirror + shared cache (faster downloads)
#    3. Install Python deps (openai etc.) on first run
#    4. Install npm deps on first run
#    5. Start the app
#
#  Flags:
#    -y          skip the "apply updates?" prompt
#    -NoBackup   skip per-run backup
#    -SkipUpdate skip update processing, just launch
# =====================================================================

param(
    [switch]$y,
    [switch]$NoBackup,
    [switch]$SkipUpdate
)

$ErrorActionPreference = "Stop"
trap {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "[ERROR] at: $($_.InvocationInfo.PositionMessage)" -ForegroundColor Yellow
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 1
}

Set-Location -LiteralPath $PSScriptRoot
$projectRoot = $PSScriptRoot
$updatesDir  = Join-Path $projectRoot 'updates'
$backupRoot  = Join-Path $projectRoot 'updates-backup'
$historyLog  = Join-Path $projectRoot 'updates-history.log'

# Known-file map: a flat file in updates\ with this name goes to the mapped path.
$knownFileMap = @{
    'agent_core.py'          = 'backend\agent_core.py'
    'tools.py'               = 'backend\tools.py'
    'web_tools.py'           = 'backend\web_tools.py'
    'server.py'              = 'backend\server.py'
    'heartbeat.py'           = 'backend\heartbeat.py'
    'conversation_memory.py' = 'backend\conversation_memory.py'
    'briefing.py'            = 'backend\briefing.py'
    'competitor_watch.py'    = 'backend\competitor_watch.py'
    'dashboard.py'           = 'backend\dashboard.py'
    'tutor.py'               = 'backend\tutor.py'
    'ollama_helper.py'       = 'backend\ollama_helper.py'
    'telegram_bot.py'        = 'backend\telegram_bot.py'
    'wecom_bot.py'           = 'backend\wecom_bot.py'
    'feishu_bot.py'          = 'backend\feishu_bot.py'
    'push_serverchan.py'     = 'backend\push_serverchan.py'
    'video_tools.py'         = 'backend\video_tools.py'
    'requirements.txt'       = 'backend\requirements.txt'
    'main.js'                = 'electron\main.js'
    'preload.js'             = 'electron\preload.js'
    'package.json'           = 'electron\package.json'
    'index.html'             = 'electron\renderer\index.html'
    'renderer.js'            = 'electron\renderer\renderer.js'
    'styles.css'             = 'electron\renderer\styles.css'
    'icon.png'               = 'electron\assets\icon.png'
    'icon.ico'               = 'electron\assets\icon.ico'
    'start.ps1'              = 'start.ps1'
}

# Content routers for brand-new files not in the map.
$newFileRouters = @(
    @{ Dir = 'backend';           Signature = 'import agent_core|from agent_core|def tool_|TOOLS_SCHEMA|http\.server' }
    @{ Dir = 'electron\renderer'; Signature = 'document\.getElementById|addEventListener|renderMarkdown|window\.crayfish' }
    @{ Dir = 'electron';          Signature = 'require\(.electron.|BrowserWindow|ipcMain|app\.whenReady' }
)

# Health checks: after copy, file should contain this regex, else warn.
$healthChecks = @{
    'backend\server.py'             = 'class Handler|do_POST|do_GET'
    'backend\agent_core.py'         = 'def run_agent|build_system_prompt'
    'backend\tools.py'              = 'TOOL_REGISTRY|TOOLS_SCHEMA'
    'electron\main.js'              = 'BrowserWindow|startBackend'
    'electron\renderer\renderer.js' = 'function send|runChatLoop'
}

function Write-Info { param($m) Write-Host "[update] $m" }
function Write-Warn { param($m) Write-Host "[warn] $m" -ForegroundColor Yellow }
function Write-Err  { param($m) Write-Host "[error] $m" -ForegroundColor Red }
function Write-Ok   { param($m) Write-Host "[ok] $m" -ForegroundColor Green }

function Find-UniqueProjectFile {
    param([string]$filename)
    $hits = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -Filter $filename -ErrorAction SilentlyContinue |
        Where-Object {
            $p = $_.FullName
            ($p -notmatch '\\node_modules\\') -and
            ($p -notmatch '\\updates\\') -and
            ($p -notmatch '\\updates-backup\\') -and
            ($p -notmatch '\\__pycache__\\') -and
            ($p -notmatch '\\\.git\\')
        }
    if ($hits.Count -eq 1) { return $hits[0].FullName }
    return $null
}

function Get-FileHead {
    param([string]$filepath)
    try {
        $bytes = [System.IO.File]::ReadAllBytes($filepath)
        $take = [Math]::Min(51200, $bytes.Length)
        return [System.Text.Encoding]::UTF8.GetString($bytes, 0, $take)
    } catch { return $null }
}

function Route-NewFile {
    param([string]$filepath)
    $head = Get-FileHead $filepath
    if (-not $head) { return $null }
    foreach ($r in $newFileRouters) {
        if ($head -match $r.Signature) { return $r.Dir }
    }
    return $null
}

function Process-Updates {
    if (-not (Test-Path -LiteralPath $updatesDir)) {
        New-Item -ItemType Directory -Path $updatesDir | Out-Null
        Write-Info "Created updates\ folder. Drop updated files there next time."
        return
    }

    $files = Get-ChildItem -LiteralPath $updatesDir -Recurse -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -notlike '*.txt' }
    if ($files.Count -eq 0) {
        Write-Info "updates\ is empty, nothing to apply."
        return
    }

    Write-Host ""
    Write-Info "Found $($files.Count) file(s) in updates\ :"
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($updatesDir.Length).TrimStart('\')
        Write-Host "    - $rel"
    }
    Write-Host ""

    $plan = @()
    foreach ($f in $files) {
        $name = $f.Name
        $relInUpdates = $f.FullName.Substring($updatesDir.Length).TrimStart('\')
        $target = $null
        $how = ''

        if ($relInUpdates -ne $name) {
            $target = Join-Path $projectRoot $relInUpdates
            $how = 'by-subfolder'
        }
        elseif ($knownFileMap.ContainsKey($name)) {
            $target = Join-Path $projectRoot $knownFileMap[$name]
            $how = 'known-map'
        }
        else {
            $existing = Find-UniqueProjectFile $name
            if ($existing) {
                $target = $existing
                $how = 'match-existing'
            }
            else {
                # Brand-new file. By extension first (most reliable here):
                # .py -> backend ; .js/.css/.html -> electron.
                $ext = [System.IO.Path]::GetExtension($name).ToLower()
                if ($ext -eq '.py') {
                    $target = Join-Path $projectRoot (Join-Path 'backend' $name)
                    $how = 'new-py-to-backend'
                }
                elseif ($ext -eq '.js' -or $ext -eq '.css' -or $ext -eq '.html') {
                    if ($name -eq 'main.js' -or $name -eq 'preload.js') {
                        $target = Join-Path $projectRoot (Join-Path 'electron' $name)
                    } else {
                        $target = Join-Path $projectRoot (Join-Path 'electron\renderer' $name)
                    }
                    $how = 'new-frontend'
                }
                else {
                    $dir = Route-NewFile $f.FullName
                    if ($dir) {
                        $target = Join-Path (Join-Path $projectRoot $dir) $name
                        $how = "new-file-to-$dir"
                    }
                }
            }
        }

        if ($target) {
            $plan += [PSCustomObject]@{ Source=$f.FullName; Target=$target; How=$how; Name=$relInUpdates }
        } else {
            Write-Warn "Cannot decide where $relInUpdates goes, skipped. Put it under updates\backend\ or updates\electron\."
        }
    }

    if ($plan.Count -eq 0) {
        Write-Info "Nothing to apply."
        return
    }

    Write-Host "Plan:"
    foreach ($p in $plan) {
        $relTarget = $p.Target
        if ($relTarget.StartsWith($projectRoot)) {
            $relTarget = $relTarget.Substring($projectRoot.Length).TrimStart('\')
        }
        $exists = if (Test-Path -LiteralPath $p.Target) { 'overwrite' } else { 'new' }
        Write-Host ("    {0,-26} -> {1,-38} [{2}, {3}]" -f $p.Name, $relTarget, $exists, $p.How)
    }
    Write-Host ""

    if (-not $y) {
        $ans = Read-Host "Apply these updates? (Y/N)"
        if ($ans -notmatch '^[Yy]') {
            Write-Info "Cancelled, no files changed."
            return
        }
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupDir = Join-Path $backupRoot $stamp

    foreach ($p in $plan) {
        $targetDir = Split-Path -Parent $p.Target
        if (-not (Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }
        if ((Test-Path -LiteralPath $p.Target) -and (-not $NoBackup)) {
            $relTarget = $p.Target.Substring($projectRoot.Length).TrimStart('\')
            $bkPath = Join-Path $backupDir $relTarget
            $bkDir = Split-Path -Parent $bkPath
            if (-not (Test-Path -LiteralPath $bkDir)) {
                New-Item -ItemType Directory -Path $bkDir -Force | Out-Null
            }
            Copy-Item -LiteralPath $p.Target -Destination $bkPath -Force
        }
        Copy-Item -LiteralPath $p.Source -Destination $p.Target -Force
        Write-Ok "updated $($p.Name)"

        $relTarget2 = $p.Target.Substring($projectRoot.Length).TrimStart('\')
        if ($healthChecks.ContainsKey($relTarget2)) {
            $head = Get-FileHead $p.Target
            if ($head -notmatch $healthChecks[$relTarget2]) {
                Write-Warn "  $relTarget2 missing expected keyword, maybe wrong/incomplete file."
            }
        }

        $logLine = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $($p.Name)  ->  $relTarget2  [$($p.How)]"
        Add-Content -LiteralPath $historyLog -Value $logLine -Encoding UTF8
    }

    if (-not $NoBackup) {
        Write-Info "Old files backed up to updates-backup\$stamp\"
    }

    if (-not $y) {
        $clear = Read-Host "Done. Clear the updates\ folder now? (Y/N)"
        if ($clear -match '^[Yy]') {
            Get-ChildItem -LiteralPath $updatesDir -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Write-Info "Cleared updates\ ."
        }
    } else {
        Get-ChildItem -LiteralPath $updatesDir -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host ""
}

function Check-Env {
    $ok = $true
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Err "Node.js not found. Install LTS from https://nodejs.org then retry."
        $ok = $false
    }
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        if (-not (Get-Command python3 -ErrorAction SilentlyContinue)) {
            Write-Warn "Python not found. Backend needs Python from https://python.org"
        }
    }
    return $ok
}

function Start-App {
    $electronDir = Join-Path $projectRoot 'electron'
    if (-not (Test-Path -LiteralPath (Join-Path $electronDir 'package.json'))) {
        Write-Err "electron\package.json not found, wrong folder layout."
        return
    }

    # Electron China mirror + shared cache (this process only)
    if (Test-Path -LiteralPath 'D:\') {
        $sharedCache = 'D:\electron-cache'
        if (-not (Test-Path -LiteralPath $sharedCache)) {
            try { New-Item -ItemType Directory -Path $sharedCache -Force | Out-Null } catch {}
        }
        if (-not $env:ELECTRON_CACHE) { $env:ELECTRON_CACHE = $sharedCache }
        if (-not $env:electron_config_cache) { $env:electron_config_cache = $sharedCache }
    }
    if (-not $env:ELECTRON_MIRROR) {
        $env:ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/'
    }

    Set-Location -LiteralPath $electronDir

    # Python deps (openai etc.) - only if openai missing
    $reqFile = Join-Path $projectRoot 'backend\requirements.txt'
    $pyExe = 'python'
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        if (Get-Command python3 -ErrorAction SilentlyContinue) { $pyExe = 'python3' }
    }
    if (Test-Path -LiteralPath $reqFile) {
        # IMPORTANT: probe must NOT throw. Under $ErrorActionPreference='Stop'
        # (set at top) a native command that exits non-zero terminates the
        # script in PowerShell 7.3+. The old probe used `python -c "import X"`
        # which is *meant* to fail when deps are missing -> that crashed the
        # launcher. We now (a) relax ErrorAction locally and (b) use
        # importlib find_spec so Python always exits 0 and just prints OK/MISSING.
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $needDeps = $true
            $probe = & $pyExe -c "import importlib.util as u; mods=['openai','psutil','edge_tts','mss','send2trash','pyperclip','PIL','anthropic']; print('OK' if all(u.find_spec(m) for m in mods) else 'MISSING')" 2>$null
            if ($probe -match 'OK') { $needDeps = $false }

            if ($needDeps) {
                Write-Info "Installing/updating Python deps (new features added: computer-control + voice). May be slow the first time..."
                # 1) canonical: install from requirements.txt if present
                & $pyExe -m pip install -r $reqFile 2>&1 | Out-Host
                # 2) safety net: install the new packages explicitly, so it works
                #    even if an older requirements.txt is still in place.
                & $pyExe -m pip install psutil pyautogui pillow mss pyperclip send2trash pytesseract opencv-python edge-tts anthropic pycaw comtypes 2>&1 | Out-Host
                # re-probe to report status (still never throws)
                $probe2 = & $pyExe -c "import importlib.util as u; mods=['openai','edge_tts','psutil','mss']; print('OK' if all(u.find_spec(m) for m in mods) else 'MISSING')" 2>$null
                if ($probe2 -match 'OK') {
                    Write-Ok "Python deps ready"
                } else {
                    Write-Warn "Some Python deps may still be missing. Core chat works; you can re-run the launcher, or run:  $pyExe -m pip install -r `"$reqFile`""
                }
            } else {
                Write-Info "Python deps already installed"
            }
        } catch {
            Write-Warn "Dep install step skipped due to: $($_.Exception.Message). You can run:  $pyExe -m pip install -r `"$reqFile`""
        } finally {
            $ErrorActionPreference = $oldEAP
        }
    }

    # npm deps (first run)
    if (-not (Test-Path -LiteralPath (Join-Path $electronDir 'node_modules'))) {
        Write-Info "First run, installing Electron deps (downloads, slow)..."
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Err "npm install failed. Check network, or run 'npm install' in electron folder."
            Set-Location -LiteralPath $projectRoot
            return
        }
    }

    Write-Info "Starting Chaoneng Xiaozhu..."
    npm start
    Set-Location -LiteralPath $projectRoot
}

Write-Host "==================================="
Write-Host "   Chaoneng Xiaozhu  Launcher"
Write-Host "==================================="

if (-not $SkipUpdate) {
    Process-Updates
}

if (Check-Env) {
    Start-App
} else {
    Write-Host ""
    Write-Host "Install the missing tools then retry. Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}
