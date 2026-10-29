param(
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Continue"
$base = "D:\大肥鱼"
$logs = Join-Path $base "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null

# SVC 和 Breeze/SVS 不能同时塞进 8GB 显存：先停语音服务和看门狗，生成完再拉起。
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
    & "D:\dafeiyu\sing\venv\Scripts\python.exe" "D:\dafeiyu\sing\svc_cover.py" `
        --target $Target --out $Out 2>&1 | Tee-Object -FilePath (Join-Path $logs "svc-cover.log")
    $code = $LASTEXITCODE
} catch {
    Add-Content -LiteralPath (Join-Path $logs "svc-cover.log") -Value $_.Exception.Message -Encoding UTF8
    $code = 1
} finally {
    $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    Start-Process -FilePath $ps -ArgumentList @(
        "-WindowStyle", "Hidden",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $base "start-bot.ps1")
    ) -WindowStyle Hidden | Out-Null
}
exit $code
