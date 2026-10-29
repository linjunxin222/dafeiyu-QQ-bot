# 唱歌服务一键安装（Windows + NVIDIA 显卡）。用法：右键「使用 PowerShell 运行」，或
#   powershell -ExecutionPolicy Bypass -File setup_windows.ps1 [-Root D:\dafeiyu\sing]
# 会装到 $Root：独立的 Python 环境、SoulX-Singer 源码、2.8 GB 模型。不改系统设置，不动 AstrBot 自己的环境。
param([string]$Root = "D:\dafeiyu\sing")
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $Root, "$Root\dl", "$Root\models\SoulX-Singer" | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { python -m pip install -U uv }

if (-not (Test-Path "$Root\SoulX-Singer")) {
    try {
        git clone --depth 1 https://github.com/Soul-AILab/SoulX-Singer "$Root\SoulX-Singer"
    } catch {
        Write-Host "git clone 失败，改用 codeload 下载源码"
        $zip = "$Root\SoulX-Singer-main.zip"
        curl.exe -L --retry 5 -o $zip https://codeload.github.com/Soul-AILab/SoulX-Singer/zip/refs/heads/main
        Expand-Archive -LiteralPath $zip -DestinationPath $Root -Force
        if (Test-Path "$Root\SoulX-Singer-main") { Move-Item "$Root\SoulX-Singer-main" "$Root\SoulX-Singer" -Force }
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
    }
}

$Model = "$Root\models\SoulX-Singer\model.pt"
if (-not (Test-Path $Model) -or (Get-Item $Model).Length -lt 2818092278) {
    # 国内用 hf-mirror；能直连 Hugging Face 的把域名换成 huggingface.co
    curl.exe -L -C - -o $Model https://hf-mirror.com/Soul-AILab/SoulX-Singer/resolve/main/model.pt
}

if (-not (Test-Path "$Root\venv\Scripts\python.exe")) {
    uv venv "$Root\venv" --python 3.12
}
$Py = "$Root\venv\Scripts\python.exe"
# RTX 50 / Blackwell 需要 CUDA 12.8；2.7.1 同时兼容 20/30/40 系
uv pip install --python $Py torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python $Py -r "$Here\requirements.txt"

Copy-Item -Force "$Here\sing_server.py", "$Here\melodies.py", "$Here\doubao_backend.py", "$Here\pitch_check.py" $Root
Copy-Item -Recurse -Force "$Here\voice" $Root
Write-Host "装好了。双击 start_sing_server.bat 启动唱歌服务。"
