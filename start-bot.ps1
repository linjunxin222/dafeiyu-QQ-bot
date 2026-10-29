$ErrorActionPreference = "SilentlyContinue"
$base = $PSScriptRoot
$logs = Join-Path $base "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$logFile = Join-Path $logs "launcher.log"

# 防止桌面快捷方式和开机启动同时点，重复拉起 AstrBot/NapCat。
$launcherLock = $null
try {
    $launcherLock = [IO.File]::Open((Join-Path $logs "launcher.lock"), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
} catch {
    exit
}

function Log-Message([string]$message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    Write-Output $message
}

function Test-AstrBotHttp {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:6218/" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-QQConnection {
    return (@(Get-NetTCPConnection -State Established -LocalPort 6219 -ErrorAction SilentlyContinue).Count -gt 0)
}

function Start-Watchdog {
    $running = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "powershell.exe" -and $_.CommandLine -match "-File .*watch-bot\.ps1"
    })
    if ($running.Count -gt 0) { return }
    $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    Start-Process -FilePath $psExe -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $base "watch-bot.ps1")
    ) -WindowStyle Hidden | Out-Null
    Log-Message "Watchdog starting..."
}

Log-Message "=== launcher start ==="
$sw = [Diagnostics.Stopwatch]::StartNew()

$env:ASTRBOT_ROOT = Join-Path $base "AstrBot"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# 1) 语音服务先拉起，不阻塞主流程。
$breezeCmd = "D:\breeze-tts\start-breeze.cmd"
if (Test-Path -LiteralPath $breezeCmd) {
    try {
        $breezeHttp = (Invoke-WebRequest -Uri "http://127.0.0.1:8137/v1/voices" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $breezeHttp = $false
    }
    if (-not $breezeHttp) {
        $breezeRunning = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "breeze-server.exe" })
        if ($breezeRunning.Count -gt 0) {
            $breezeRunning | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Start-Sleep -Milliseconds 800
        }
        Start-Process -FilePath $breezeCmd -WorkingDirectory "D:\breeze-tts" -WindowStyle Hidden | Out-Null
        Log-Message "Breeze TTS starting..."
    }
}

$singRoot = "D:\dafeiyu\sing"
$singPy = Join-Path $singRoot "venv\Scripts\python.exe"
$singScript = Join-Path $singRoot "sing_server.py"
$singModel = Join-Path $singRoot "models\SoulX-Singer\model.pt"
if ((Test-Path -LiteralPath $singPy) -and (Test-Path -LiteralPath $singScript) -and (Test-Path -LiteralPath $singModel)) {
    try {
        $singHealth = Invoke-RestMethod -Uri "http://127.0.0.1:18620/health" -TimeoutSec 2
        $singOk = [bool]($singHealth.ok -and ($singHealth.backends -contains "soulx"))
    } catch {
        $singOk = $false
    }
    $singRunning = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and $_.CommandLine -match "sing_server\.py"
    })
    if (-not $singOk -and $singRunning.Count -eq 0) {
        Start-Process -FilePath $singPy -ArgumentList @($singScript, "--soulx", (Join-Path $singRoot "SoulX-Singer"), "--model", $singModel) `
            -WorkingDirectory $singRoot -RedirectStandardOutput (Join-Path $logs "sing-server.out.log") `
            -RedirectStandardError (Join-Path $logs "sing-server.err.log") -WindowStyle Hidden | Out-Null
        Log-Message "SoulX singing service starting..."
    } elseif (-not $singOk) {
        Log-Message "SoulX singing process exists, waiting..."
    }
}

# 2) AstrBot 与 NapCat 并行启动，不再等 AstrBot 完全就绪才启动 QQ。
$httpOk = Test-AstrBotHttp
if (-not $httpOk) {
    $astrBotRunning = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -like (Join-Path $base "AstrBot\*") -and $_.CommandLine -match "main\.py"
    })
    if ($astrBotRunning.Count -eq 0) {
        $py = Join-Path $base "AstrBot\venv\Scripts\python.exe"
        $app = Join-Path $base "AstrBot\app"
        Start-Process -FilePath $py -ArgumentList @("-u", "main.py") -WorkingDirectory $app `
            -RedirectStandardOutput (Join-Path $logs "astrbot.out.log") `
            -RedirectStandardError (Join-Path $logs "astrbot.err.log") -WindowStyle Hidden | Out-Null
        Log-Message "AstrBot starting..."
    } else {
        Log-Message "AstrBot process exists, waiting..."
    }
}

$napcatRunning = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -like (Join-Path $base "NapCat\*") -and $_.Name -eq "NapCatWinBootMain.exe"
})
if ($napcatRunning.Count -gt 1) {
    $keep = $napcatRunning | Sort-Object CreationDate | Select-Object -First 1
    $napcatRunning | Where-Object { $_.ProcessId -ne $keep.ProcessId } | ForEach-Object {
        & "$env:SystemRoot\System32\taskkill.exe" /PID $_.ProcessId /T /F 2>$null | Out-Null
    }
    Log-Message "Removed duplicate NapCat processes; keeping one."
    $napcatRunning = @($keep)
}

$ws = Test-QQConnection
if (-not $ws) {
    if ($napcatRunning.Count -eq 0) {
        $napcatDir = Join-Path $base "NapCat\NapCat.52230.Shell"
        $versionDir = Get-ChildItem -LiteralPath (Join-Path $napcatDir "versions") -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
        $quickAccount = if ($versionDir) {
            Get-ChildItem -LiteralPath (Join-Path $versionDir.FullName "resources\app\napcat\config") -File -Filter "onebot11_*.json" -ErrorAction SilentlyContinue | Select-Object -First 1
        }
        $quickLogin = if ($quickAccount) { $quickAccount.BaseName -replace '^onebot11_', '' } else { "" }
        if ($quickLogin) {
            Start-Process -FilePath (Join-Path $napcatDir "NapCatWinBootMain.exe") -ArgumentList @($quickLogin) `
                -WorkingDirectory $napcatDir -WindowStyle Hidden | Out-Null
            Log-Message "NapCat starting with saved quick login..."
        } else {
            Start-Process -FilePath (Join-Path $napcatDir "NapCatWinBootMain.exe") `
                -WorkingDirectory $napcatDir -WindowStyle Hidden | Out-Null
            Log-Message "NapCat starting; no saved account, QR may be required."
        }
    } else {
        Log-Message "NapCat process exists, waiting..."
    }
}

# 3) 看门狗尽早启动，后面的等待期间也能接手异常。
Start-Watchdog

# 4) 同时等待 AstrBot HTTP 和 QQ WebSocket，最多 50 秒。
while ($sw.Elapsed.TotalSeconds -lt 50 -and (-not $httpOk -or -not $ws)) {
    Start-Sleep -Milliseconds 500
    if (-not $httpOk) { $httpOk = Test-AstrBotHttp }
    if (-not $ws) { $ws = Test-QQConnection }
}

if ($httpOk) {
    Log-Message "AstrBot is online."
} else {
    Log-Message "AstrBot did not become ready. Check logs\astrbot.err.log."
}
if ($ws) {
    Log-Message "QQ connection is online."
} else {
    Log-Message "QQ is not online yet; opening login QR."
    $html = Join-Path $base "qr.html"
    if (Test-Path -LiteralPath $html) {
        $edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if (-not (Test-Path -LiteralPath $edge)) {
            $edge = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        }
        if (Test-Path -LiteralPath $edge) {
            $uri = ([System.Uri]::new($html)).AbsoluteUri
            Start-Process -FilePath $edge -ArgumentList @(
                "--app=$uri",
                "--user-data-dir=$(Join-Path $base '.qr-viewer')",
                "--no-first-run",
                "--window-size=760,900",
                "--window-position=500,80"
            ) | Out-Null
        }
    }
}

Log-Message ("=== launcher done in {0:N1}s (astrbot={1}, qq={2}) ===" -f $sw.Elapsed.TotalSeconds, $httpOk, $ws)
if ($launcherLock) { $launcherLock.Dispose() }
