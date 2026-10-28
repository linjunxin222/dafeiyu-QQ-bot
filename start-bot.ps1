$ErrorActionPreference = "SilentlyContinue"
$base = $PSScriptRoot
$logs = Join-Path $base "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$logFile = Join-Path $logs "launcher.log"

function Log-Message([string]$message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    Write-Output $message
}

Log-Message "=== launcher start ==="

$env:ASTRBOT_ROOT = Join-Path $base "AstrBot"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Test-AstrBotHttp {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:6218/" -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

$httpOk = Test-AstrBotHttp
if (-not $httpOk) {
    $running = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -like (Join-Path $base "AstrBot\*") -and $_.CommandLine -match "main\.py"
    }
    if (-not $running) {
        $py = Join-Path $base "AstrBot\venv\Scripts\python.exe"
        $app = Join-Path $base "AstrBot\app"
        $outLog = Join-Path $logs "astrbot.out.log"
        $errLog = Join-Path $logs "astrbot.err.log"
        Start-Process -FilePath $py -ArgumentList "main.py" -WorkingDirectory $app `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog -WindowStyle Hidden | Out-Null
        Log-Message "AstrBot starting..."
    } else {
        Log-Message "AstrBot process exists, waiting..."
    }
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        if (Test-AstrBotHttp) { $httpOk = $true; break }
    }
}

if ($httpOk) {
    Log-Message "AstrBot is online."
} else {
    Log-Message "AstrBot did not become ready. Check logs\astrbot.err.log."
}

$ws = Get-NetTCPConnection -State Established -LocalPort 6219 -ErrorAction SilentlyContinue
if (-not $ws) {
    $napcat = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -like (Join-Path $base "NapCat\*") -and $_.Name -eq "NapCatWinBootMain.exe"
    }
    if (-not $napcat) {
        $napcatDir = Join-Path $base "NapCat\NapCat.52230.Shell"
        Start-Process -FilePath (Join-Path $napcatDir "NapCatWinBootMain.exe") `
            -WorkingDirectory $napcatDir -WindowStyle Hidden | Out-Null
        Log-Message "NapCat starting..."
    } else {
        Log-Message "NapCat process exists, waiting..."
    }
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 2
        $ws = Get-NetTCPConnection -State Established -LocalPort 6219 -ErrorAction SilentlyContinue
        if ($ws) { break }
    }
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

$watcherRunning = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "watch-bot\.ps1"
}
if (-not $watcherRunning) {
    $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    Start-Process -FilePath $psExe -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $base "watch-bot.ps1")
    ) -WindowStyle Hidden | Out-Null
    Log-Message "Watchdog starting..."
}

Start-Sleep -Seconds 2
