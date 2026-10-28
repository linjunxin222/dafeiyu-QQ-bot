$ErrorActionPreference = "SilentlyContinue"
$base = $PSScriptRoot
$logs = Join-Path $base "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$logFile = Join-Path $logs "watchdog.log"

if (Test-Path -LiteralPath $logFile) {
    $logItem = Get-Item -LiteralPath $logFile
    if ($logItem.Length -gt 2MB) {
        Move-Item -LiteralPath $logFile -Destination "$logFile.old" -Force
    }
}

function Log-Message([string]$message) {
    Add-Content -LiteralPath $logFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message" -Encoding UTF8
}

function Test-Http([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-AstrBot {
    $py = Join-Path $base "AstrBot\venv\Scripts\python.exe"
    $app = Join-Path $base "AstrBot\app"
    $out = Join-Path $logs "astrbot.out.log"
    $err = Join-Path $logs "astrbot.err.log"
    $env:ASTRBOT_ROOT = Join-Path $base "AstrBot"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    Start-Process -FilePath $py -ArgumentList "main.py" -WorkingDirectory $app `
        -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden | Out-Null
    Log-Message "watchdog started AstrBot"
}

function Stop-AstrBot {
    $listener = Get-NetTCPConnection -State Listen -LocalPort 6218 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $child = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($child.ParentProcessId)"
        if ($child -and $child.CommandLine -match "main\.py") {
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }
        if ($parent -and $parent.CommandLine -match "main\.py") {
            Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -like (Join-Path $base "AstrBot\*") -and $_.CommandLine -match "main\.py"
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Log-Message "watchdog stopped unresponsive AstrBot"
}

function Start-NapCat {
    $dir = Join-Path $base "NapCat\NapCat.52230.Shell"
    Start-Process -FilePath (Join-Path $dir "NapCatWinBootMain.exe") `
        -WorkingDirectory $dir -WindowStyle Hidden | Out-Null
    Log-Message "watchdog started NapCat"
}

function Start-Ollama {
    $app = Join-Path $base "Ollama\ollama app.exe"
    if (Test-Path -LiteralPath $app) {
        Start-Process -FilePath $app -WindowStyle Hidden | Out-Null
        Log-Message "watchdog started Ollama"
    }
}

$mutex = New-Object System.Threading.Mutex($false, "Local\dafeiyu_bot_watchdog")
if (-not $mutex.WaitOne(0)) {
    exit
}

Log-Message "watchdog started"
$astrBotFailures = 0

try {
    while ($true) {
        $httpOk = Test-Http "http://127.0.0.1:6218/"
        if (-not $httpOk) {
            $astrBotFailures++
            $running = Get-CimInstance Win32_Process | Where-Object {
                $_.ExecutablePath -like (Join-Path $base "AstrBot\*") -and $_.CommandLine -match "main\.py"
            }
            if (-not $running) {
                Start-AstrBot
                $astrBotFailures = 0
                Start-Sleep -Seconds 20
            } elseif ($astrBotFailures -ge 4) {
                Stop-AstrBot
                Start-Sleep -Seconds 3
                Start-AstrBot
                $astrBotFailures = 0
                Start-Sleep -Seconds 20
            }
        } else {
            $astrBotFailures = 0
        }

        if (-not (Test-Http "http://127.0.0.1:11434/api/tags")) {
            $ollamaRunning = Get-CimInstance Win32_Process | Where-Object {
                $_.ExecutablePath -like (Join-Path $base "Ollama\*") -and $_.Name -eq "ollama app.exe"
            }
            if (-not $ollamaRunning) { Start-Ollama; Start-Sleep -Seconds 8 }
        }

        $ws = Get-NetTCPConnection -State Established -LocalPort 6219 -ErrorAction SilentlyContinue
        if (-not $ws) {
            $napcatRunning = Get-CimInstance Win32_Process | Where-Object {
                $_.ExecutablePath -like (Join-Path $base "NapCat\*") -and $_.Name -eq "NapCatWinBootMain.exe"
            }
            if (-not $napcatRunning) { Start-NapCat; Start-Sleep -Seconds 10 }
        }

        Start-Sleep -Seconds 20
    }
} finally {
    Log-Message "watchdog stopped"
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
