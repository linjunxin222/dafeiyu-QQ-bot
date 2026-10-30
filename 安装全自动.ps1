[CmdletBinding()]
param(
    [string]$InstallDir = "D:\大肥鱼",
    [string]$DashboardUser = "dafeiyu",
    [string]$DashboardPassword = "",
    [string]$OwnerQQ = "",
    [string]$DeepSeekKey = "",
    [ValidateSet("0", "1", "2")][string]$Memory = "0",
    [ValidateSet("0", "1", "2", "3", "4")][string]$Voice = "4",
    [switch]$SkipNapCat,
    [switch]$NoStart,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$logs = Join-Path $InstallDir "logs"
$astrbotRoot = Join-Path $InstallDir "AstrBot"
$astrbotApp = Join-Path $astrbotRoot "app"
$astrbotPy = Join-Path $astrbotRoot "venv\Scripts\python.exe"
$napcatRoot = Join-Path $InstallDir "NapCat"

function Say([string]$Text) { Write-Host $Text }
function Step([string]$Text) { Write-Host ""; Write-Host "== $Text ==" -ForegroundColor Cyan }
function Fail([string]$Text) { Write-Host $Text -ForegroundColor Red; exit 1 }

function Download([string]$Url, [string]$Out) {
    Say "下载 $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Out -UseBasicParsing -TimeoutSec 600
    if (-not (Test-Path $Out) -or (Get-Item $Out).Length -lt 1000) { throw "下载失败或文件为空：$Url" }
}

function Get-Python {
    $candidates = @()
    try { $p = & py -3.12 -c "import sys; print(sys.executable)" 2>$null; if ($p) { $candidates += $p.Trim() } } catch {}
    $candidates += "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe"
    $candidates += "C:\Python312\python.exe"
    foreach ($p in $candidates) { if ($p -and (Test-Path $p)) { return $p } }
    return $null
}

function Ensure-Python {
    $py = Get-Python
    if ($py) { return $py }
    Step "安装 Python 3.12"
    $installer = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
    Download "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" $installer
    $args = @("/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_test=0", "Include_launcher=0", "SimpleInstall=1")
    $p = Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
    if ($p.ExitCode -ne 0) { Fail "Python 安装失败，退出码 $($p.ExitCode)" }
    $py = Get-Python
    if (-not $py) { Fail "Python 已安装但找不到 python.exe" }
    return $py
}

function Ensure-AstrBot([string]$py) {
    if (Test-Path $astrbotPy) { return }
    Step "下载 AstrBot"
    New-Item -ItemType Directory -Path $astrbotRoot -Force | Out-Null
    $zip = Join-Path $env:TEMP "astrbot-src.zip"
    Download "https://api.github.com/repos/AstrBotDevs/AstrBot/zipball/v4.29.3" $zip
    $tmp = Join-Path $env:TEMP ("astrbot-src-" + [guid]::NewGuid().ToString("N"))
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
    if (-not $inner) { Fail "AstrBot 压缩包结构不对" }
    if (Test-Path $astrbotApp) { Remove-Item $astrbotApp -Recurse -Force }
    Move-Item -LiteralPath $inner.FullName -Destination $astrbotApp
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

    Step "创建 AstrBot 虚拟环境"
    & $py -m venv (Join-Path $astrbotRoot "venv")
    if ($LASTEXITCODE -ne 0) { Fail "创建 venv 失败" }
    & $astrbotPy -m pip install --upgrade pip --disable-pip-version-check
    $req = Join-Path $astrbotApp "requirements.txt"
    & $astrbotPy -m pip install -r $req --disable-pip-version-check -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    if ($LASTEXITCODE -ne 0) { Fail "AstrBot 依赖安装失败" }

    Step "安装 AstrBot 后台静态文件"
    $dist = Join-Path $astrbotRoot "data\dist"
    if (-not (Test-Path (Join-Path $dist "index.html"))) {
        $dzip = Join-Path $env:TEMP "astrbot-dashboard.zip"
        Download "https://api.github.com/repos/AstrBotDevs/AstrBot/releases/assets/672655283" $dzip
        New-Item -ItemType Directory -Path $dist -Force | Out-Null
        Expand-Archive -LiteralPath $dzip -DestinationPath $dist -Force
        $dinner = Get-ChildItem -LiteralPath $dist -Directory | Select-Object -First 1
        if ($dinner -and -not (Test-Path (Join-Path $dist "index.html"))) {
            Get-ChildItem -LiteralPath $dinner.FullName -Force | Move-Item -Destination $dist -Force
            Remove-Item $dinner.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Start-AstrBot([string]$password) {
    $env:ASTRBOT_DASHBOARD_INITIAL_PASSWORD = $password
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    Start-Process -FilePath $astrbotPy -ArgumentList @("-u", "main.py") -WorkingDirectory $astrbotApp `
        -RedirectStandardOutput (Join-Path $logs "astrbot.out.log") `
        -RedirectStandardError (Join-Path $logs "astrbot.err.log") -WindowStyle Hidden | Out-Null
}

function Wait-Http([string]$Url, [int]$Seconds = 120) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

function Stop-AstrBot {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and $_.CommandLine -match "main\.py" -and $_.ExecutablePath -like "$astrbotRoot\*"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Patch-Config([string]$deepseekKey, [string]$token) {
    $cfg = Join-Path $astrbotRoot "data\cmd_config.json"
    if (-not (Test-Path $cfg)) { Fail "AstrBot 首次启动没有生成 cmd_config.json" }
    $j = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
    $j.dashboard.port = 6218
    $j.dashboard.username = $DashboardUser
    $j.platform = @([pscustomobject]@{
        id = "qq-napcat"
        type = "aiocqhttp"
        enable = $true
        name = "QQ"
        ws_reverse_host = "127.0.0.1"
        ws_reverse_port = 6219
        ws_reverse_token = $token
    })
    $j.provider_sources = @([pscustomobject]@{
        id = "deepseek"
        provider = "deepseek"
        type = "openai_chat_completion"
        provider_type = "chat_completion"
        key = $deepseekKey
        api_base = "https://api.deepseek.com"
        timeout = 120
        proxy = ""
        custom_headers = @{}
        enable = $true
    })
    $j.provider = @([pscustomobject]@{
        id = "deepseek/deepseek-flash"
        provider_source_id = "deepseek"
        model = "deepseek-flash"
        enable = $true
        modalities = @("text", "tool_use", "image")
    })
    if (-not $j.agent_runner) {
        $j | Add-Member -NotePropertyName agent_runner -NotePropertyValue ([pscustomobject]@{
            runner_type = "local"
            config = [pscustomobject]@{ model = [pscustomobject]@{ provider_id = "deepseek/deepseek-flash" } }
        })
    } else {
        $j.agent_runner.config.model.provider_id = "deepseek/deepseek-flash"
    }
    $j | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $cfg -Encoding UTF8
}

function Install-ConfigPack {
    Step "复制大肥鱼配置包"
    Get-ChildItem -LiteralPath $root -Force | Where-Object {
        $_.Name -notin @("AstrBot", "NapCat", "logs", ".git", "release", "backups")
    } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $InstallDir -Recurse -Force
    }
}

function Run-Import([string]$password, [string]$qq) {
    Step "导入人格和插件"
    $answers = @{
        base_url = "http://127.0.0.1:6218"
        username = $DashboardUser
        password = $password
        owner_qq = $qq
        memory = $Memory
        voice = $Voice
    }
    $temp = Join-Path $env:TEMP ("dafeiyu-answers-" + [guid]::NewGuid().ToString("N") + ".json")
    try {
        $answers | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temp -Encoding UTF8
        & $astrbotPy -X utf8 (Join-Path $InstallDir "tools\import_dafeiyu.py") --answers $temp
        if ($LASTEXITCODE -ne 0) { Fail "配置导入失败，请查看上面的报错" }
    } finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
}

function Install-NapCat {
    if ($SkipNapCat) { return }
    Step "下载 NapCat"
    New-Item -ItemType Directory -Path $napcatRoot -Force | Out-Null
    $zip = Join-Path $env:TEMP "napcat-onekey.zip"
    Download "https://api.github.com/repos/NapNeko/NapCatQQ/releases/assets/691263450" $zip
    Expand-Archive -LiteralPath $zip -DestinationPath $napcatRoot -Force
    Say ""
    Say "NapCat 已解压到：$napcatRoot"
    Say "接下来需要："
    Say "1. 确认电脑已安装 QQNT（官方 QQ）"
    Say "2. 运行 $napcatRoot\NapCatInstaller.exe"
    Say "3. 按提示安装/启动 NapCat，扫码登录机器人 QQ"
    Say "4. 在 NapCat 的 OneBot 设置里确认反向 WebSocket：ws://127.0.0.1:6219/ws"
}

function Write-StartScript {
    $start = Join-Path $InstallDir "启动机器人.bat"
    @"
@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-bot.ps1"
pause
"@ | Set-Content -LiteralPath $start -Encoding UTF8
}

# ---------------- main ----------------
Say "大肥鱼全自动安装器（Beta）"
Say "安装目录：$InstallDir"
if ($DryRun) {
    $py = Get-Python
    Say "Python: $py"
    Say "AstrBot: $astrbotRoot"
    Say "NapCat: $napcatRoot"
    Say "后台: http://127.0.0.1:6218"
    exit 0
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
New-Item -ItemType Directory -Path $logs -Force | Out-Null

$py = Ensure-Python
if (-not $OwnerQQ) { $OwnerQQ = (Read-Host "主人 QQ 号").Trim() }
if (-not $DashboardPassword) {
    $secure = Read-Host "AstrBot 后台密码（直接回车自动生成）" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $DashboardPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if (-not $DashboardPassword) { $DashboardPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 18 | ForEach-Object { [char]$_ }) }
}
if (-not $DeepSeekKey) {
    $secure = Read-Host "DeepSeek API Key" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $DeepSeekKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
if (-not $OwnerQQ -or -not $DeepSeekKey) { Fail "主人 QQ 和 DeepSeek Key 不能为空" }

Ensure-AstrBot $py

Step "首次启动 AstrBot 并生成配置"
Start-AstrBot $DashboardPassword
if (-not (Wait-Http "http://127.0.0.1:6185/" 120)) {
    Stop-AstrBot
    Fail "AstrBot 首次启动失败，查看 $logs\astrbot.err.log"
}
Stop-AstrBot

$token = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
Patch-Config $DeepSeekKey $token
Install-ConfigPack
Write-StartScript

Step "重新启动 AstrBot"
Start-AstrBot $DashboardPassword
if (-not (Wait-Http "http://127.0.0.1:6218/" 120)) { Fail "AstrBot 没有在 6218 起来，查看日志" }

Run-Import $DashboardPassword $OwnerQQ
Install-NapCat

Write-Host ""
Write-Host "安装完成。" -ForegroundColor Green
Write-Host "后台：http://127.0.0.1:6218"
Write-Host "账号：$DashboardUser"
Write-Host "密码：$DashboardPassword"
Write-Host "启动：$InstallDir\启动机器人.bat"
if (-not $NoStart) {
    Start-Process -FilePath (Join-Path $InstallDir "启动机器人.bat") -WorkingDirectory $InstallDir | Out-Null
}
