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

$breezeCmd = "D:\breeze-tts\start-breeze.cmd"
if (Test-Path -LiteralPath $breezeCmd) {
    try {
        $breezeHttp = (Invoke-WebRequest -Uri "http://127.0.0.1:8137/v1/voices" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $breezeHttp = $false
    }
    if (-not $breezeHttp) {
        $breezeRunning = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "breeze-server.exe" })
        if ($breezeRunning) {
            $breezeRunning | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Start-Sleep -Seconds 2
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
        $singHealth = Invoke-RestMethod -Uri "http://127.0.0.1:18620/health" -TimeoutSec 3
        $singOk = [bool]($singHealth.ok -and ($singHealth.backends -contains "soulx"))
    } catch {
        $singOk = $false
    }
    if (-not $singOk) {
        Start-Process -FilePath $singPy -ArgumentList @($singScript, "--soulx", (Join-Path $singRoot "SoulX-Singer"), "--model", $singModel) `
            -WorkingDirectory $singRoot -RedirectStandardOutput (Join-Path $logs "sing-server.out.log") `
            -RedirectStandardError (Join-Path $logs "sing-server.err.log") -WindowStyle Hidden | Out-Null
        Log-Message "SoulX singing service starting..."
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
        Start-Process -FilePath $py -ArgumentList @("-u", "main.py") -WorkingDirectory $app `
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
