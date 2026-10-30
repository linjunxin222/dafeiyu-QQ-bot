[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:6218",
    [string]$AstrBotPath = "",
    [string]$PythonPath = "",
    [string]$Username = "",
    [string]$OwnerQQ = "",
    [ValidateSet("0", "1", "2")][string]$Memory = "0",
    [ValidateSet("0", "1", "2", "3", "4")][string]$Voice = "4",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$importScript = Join-Path $root "tools\import_dafeiyu.py"

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Find-Python {
    if ($PythonPath -and (Test-Path $PythonPath)) { return $PythonPath }
    $candidates = @()
    if ($AstrBotPath) {
        $candidates += (Join-Path $AstrBotPath "venv\Scripts\python.exe")
        $candidates += (Join-Path $AstrBotPath "app\venv\Scripts\python.exe")
    }
    $candidates += (Join-Path $root "AstrBot\venv\Scripts\python.exe")
    $candidates += (Join-Path $root "AstrBot\app\venv\Scripts\python.exe")
    $launcher = Join-Path $env:USERPROFILE ".astrbot_launcher\instances"
    if (Test-Path $launcher) {
        $candidates += Get-ChildItem -LiteralPath $launcher -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName "venv\Scripts\python.exe" }
    }
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

Write-Host "大肥鱼一键导入" -ForegroundColor Green
Write-Host "这个脚本只负责把人格、插件和设置导入一个已经能正常聊天的 AstrBot。"
Write-Host "AstrBot、NapCat 和 QQ 需要先按 docs/SETUP.md 装好。"

$python = Find-Python
if (-not $python) {
    Write-Host ""
    Write-Host "找不到 AstrBot 的 Python。" -ForegroundColor Yellow
    Write-Host "请确认 AstrBot 已经安装，或者用 -AstrBotPath 指定 AstrBot 目录。"
    exit 1
}
if (-not (Test-Path $importScript)) {
    Write-Host "找不到导入工具：$importScript" -ForegroundColor Red
    exit 1
}

Write-Step "检查 AstrBot 后台"
try {
    $resp = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 8
    Write-Host "后台可访问：$BaseUrl (HTTP $($resp.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "连不上 AstrBot 后台：$BaseUrl" -ForegroundColor Red
    Write-Host "先启动 AstrBot，确认浏览器能打开这个地址。"
    exit 1
}

if ($DryRun) {
    Write-Step "DryRun"
    Write-Host "Python: $python"
    Write-Host "导入工具: $importScript"
    Write-Host "后台: $BaseUrl"
    Write-Host "记忆: $Memory，语音: $Voice"
    exit 0
}

if (-not $Username) {
    $Username = Read-Host "AstrBot 后台账号"
}
if (-not $Password) {
    $secure = Read-Host "AstrBot 后台密码" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}
if (-not $OwnerQQ) {
    $OwnerQQ = Read-Host "你的 QQ 号（只把这个号当主人）"
}
$OwnerQQ = ($OwnerQQ -replace "\D", "")
if ($OwnerQQ.Length -lt 5) {
    Write-Host "QQ 号看起来不对。" -ForegroundColor Red
    exit 1
}

$answers = @{
    base_url = $BaseUrl
    username = $Username
    password = $Password
    owner_qq = $OwnerQQ
    memory = $Memory
    voice = $Voice
}
$temp = Join-Path ([IO.Path]::GetTempPath()) ("dafeiyu-answers-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    $answers | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temp -Encoding UTF8
    Write-Step "开始导入"
    & $python -X utf8 $importScript --answers $temp
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "导入没有完全成功，请按上面的提示处理后重跑。" -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
    Write-Host ""
    Write-Host "导入完成。去 QQ 发一句「在吗」试试。" -ForegroundColor Green
    Write-Host "如果之前聊过，先发 /reset 清掉旧对话。"
} finally {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}
