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

function Find-NapCatDir {
    $root = Join-Path $PSScriptRoot "NapCat"
    $candidates = @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter "NapCatWinBootMain.exe" -ErrorAction SilentlyContinue)
    $withConfig = $candidates | Where-Object {
        @(Get-ChildItem -LiteralPath $_.DirectoryName -Recurse -File -Filter "onebot11_*.json" -ErrorAction SilentlyContinue).Count -gt 0
    } | Select-Object -First 1
    if ($withConfig) { return $withConfig.DirectoryName }
    $withVersions = $candidates | Where-Object { Test-Path (Join-Path $_.DirectoryName "versions") } | Select-Object -First 1
    if ($withVersions) { return $withVersions.DirectoryName }
    if ($candidates.Count -gt 0) { return $candidates[0].DirectoryName }
    return $null
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
    Start-Process -FilePath $py -ArgumentList @("-u", "main.py") -WorkingDirectory $app `
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
    $dir = Find-NapCatDir
    if (-not $dir) { Log-Message "watchdog: NapCat not installed"; return }
    $quickAccount = Get-ChildItem -LiteralPath $dir -Recurse -File -Filter "onebot11_*.json" -ErrorAction SilentlyContinue | Select-Object -First 1
    $quickLogin = if ($quickAccount) { $quickAccount.BaseName -replace '^onebot11_', '' } else { "" }
    if ($quickLogin) {
        Start-Process -FilePath (Join-Path $dir "NapCatWinBootMain.exe") -ArgumentList @($quickLogin) `
            -WorkingDirectory $dir -WindowStyle Hidden | Out-Null
        Log-Message "watchdog started NapCat with saved quick login"
    } else {
        Start-Process -FilePath (Join-Path $dir "NapCatWinBootMain.exe") `
            -WorkingDirectory $dir -WindowStyle Hidden | Out-Null
        Log-Message "watchdog started NapCat; QR may be required"
    }
}

function Start-Ollama {
    $app = Join-Path $base "Ollama\ollama app.exe"
    if (Test-Path -LiteralPath $app) {
        Start-Process -FilePath $app -WindowStyle Hidden | Out-Null
        Log-Message "watchdog started Ollama"
    }
}

function Start-Breeze {
    $cmd = "D:\breeze-tts\start-breeze.cmd"
    if (-not (Test-Path -LiteralPath $cmd)) { return }
    if (Test-Http "http://127.0.0.1:8137/v1/voices") {
        $script:breezeFailures = 0
        return
    }
    $running = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "breeze-server.exe" })
    if (-not $running) {
        Start-Process -FilePath $cmd -WorkingDirectory "D:\breeze-tts" -WindowStyle Hidden | Out-Null
        Log-Message "watchdog started Breeze"
        $script:breezeFailures = 0
        return
    }
    $script:breezeFailures++
    if ($script:breezeFailures -ge 3) {
        $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
        Start-Process -FilePath $cmd -WorkingDirectory "D:\breeze-tts" -WindowStyle Hidden | Out-Null
        Log-Message "watchdog restarted unresponsive Breeze"
        $script:breezeFailures = 0
    }
}

function Test-Sing {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:18620/health" -TimeoutSec 4
        return [bool]($h.ok -and ($h.backends -contains "soulx"))
    } catch {
        return $false
    }
}

function Start-Sing {
    $root = "D:\dafeiyu\sing"
    $py = Join-Path $root "venv\Scripts\python.exe"
    $serverScript = Join-Path $root "sing_server.py"
    $model = Join-Path $root "models\SoulX-Singer\model.pt"
    if (-not ((Test-Path -LiteralPath $py) -and (Test-Path -LiteralPath $serverScript) -and (Test-Path -LiteralPath $model))) { return }
    if (Test-Sing) {
        $script:singFailures = 0
        return
    }
    $running = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and $_.CommandLine -match "sing_server\.py"
    })
    if (-not $running) {
        Start-Process -FilePath $py -ArgumentList @($serverScript, "--soulx", (Join-Path $root "SoulX-Singer"), "--model", $model) `
            -WorkingDirectory $root -RedirectStandardOutput (Join-Path $logs "sing-server.out.log") `
            -RedirectStandardError (Join-Path $logs "sing-server.err.log") -WindowStyle Hidden | Out-Null
        Log-Message "watchdog started SoulX singing service"
        $script:singFailures = 0
        return
    }
    $script:singFailures++
    if ($script:singFailures -ge 3) {
        $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
        Start-Process -FilePath $py -ArgumentList @($serverScript, "--soulx", (Join-Path $root "SoulX-Singer"), "--model", $model) `
            -WorkingDirectory $root -RedirectStandardOutput (Join-Path $logs "sing-server.out.log") `
            -RedirectStandardError (Join-Path $logs "sing-server.err.log") -WindowStyle Hidden | Out-Null
        Log-Message "watchdog restarted unresponsive SoulX singing service"
        $script:singFailures = 0
    }
}

function Remove-DuplicateNapCat {
    $napcat = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -like (Join-Path $base "NapCat\*") -and $_.Name -eq "NapCatWinBootMain.exe"
    })
    if ($napcat.Count -le 1) { return }
    $keep = $napcat | Sort-Object CreationDate | Select-Object -First 1
    $napcat | Where-Object { $_.ProcessId -ne $keep.ProcessId } | ForEach-Object {
        & "$env:SystemRoot\System32\taskkill.exe" /PID $_.ProcessId /T /F 2>$null | Out-Null
    }
    Log-Message "watchdog removed duplicate NapCat processes"
}

$mutex = New-Object System.Threading.Mutex($false, "Local\dafeiyu_bot_watchdog")
if (-not $mutex.WaitOne(0)) {
    exit
}

Log-Message "watchdog started"
$astrBotFailures = 0
$breezeFailures = 0
$singFailures = 0

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

        Start-Breeze
        Start-Sing
        Remove-DuplicateNapCat

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
