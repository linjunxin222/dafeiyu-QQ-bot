param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [string]$Negative = "lowres, bad anatomy, bad hands, extra fingers, text, watermark, logo, blurry, jpeg artifacts, worst quality",
    [int]$Width = 1024,
    [int]$Height = 1024,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Continue"
$base = "D:\大肥鱼"
$comfy = Join-Path $base "ComfyUI"
$logs = Join-Path $base "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null

# ComfyUI and Breeze/SVS cannot share 8GB: stop voice services and watchdog, restore after.
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "powershell.exe" -and $_.CommandLine -match "-File .*watch-bot\.ps1"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -match "sing_server\.py"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-Process -Name "breeze-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

$code = 1
try {
    $health = $null
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 3 } catch {}
    if (-not $health) {
        Start-Process -FilePath "D:\dafeiyu\sing\venv\Scripts\python.exe" `
            -ArgumentList @("main.py", "--listen", "127.0.0.1", "--port", "8188", "--lowvram") `
            -WorkingDirectory $comfy `
            -RedirectStandardOutput (Join-Path $logs "comfyui.out.log") `
            -RedirectStandardError (Join-Path $logs "comfyui.err.log") -WindowStyle Hidden | Out-Null
        for ($i = 0; $i -lt 45; $i++) {
            Start-Sleep -Seconds 2
            try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 3; if ($h) { break } } catch {}
        }
    }

    & "D:\dafeiyu\sing\venv\Scripts\python.exe" "D:\大肥鱼\ComfyUI\comfy_generate.py" `
        --prompt $Prompt --negative $Negative --width $Width --height $Height --out $Out 2>&1 |
        Tee-Object -FilePath (Join-Path $logs "comfy-generate.log")
    $code = $LASTEXITCODE
} catch {
    Add-Content -LiteralPath (Join-Path $logs "comfy-generate.log") -Value $_.Exception.Message -Encoding UTF8
    $code = 1
} finally {
    # Stop ComfyUI so Breeze/SVS can reclaim the GPU.
    $conn = Get-NetTCPConnection -State Listen -LocalPort 8188 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    Start-Process -FilePath $ps -ArgumentList @(
        "-WindowStyle", "Hidden",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $base "start-bot.ps1")
    ) -WindowStyle Hidden | Out-Null
}
exit $code
