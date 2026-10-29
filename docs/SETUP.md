# 安装步骤

以下以 Windows 和 `D:\大肥鱼` 为例，你可以换到自己的目录。

## 1. AstrBot

- 安装 AstrBot 4.29.3 到 `AstrBot/app`
- 创建虚拟环境 `AstrBot/venv`
- 安装 `AstrBot/app/requirements.txt`
- 启动后确认后台地址：`http://127.0.0.1:6218`

后台账号和密码请自己设置，不要提交到仓库。

## 2. NapCat

- 把 NapCat 9.9.33-52230 放在 `NapCat/NapCat.52230.Shell`
- 从同版本 QQNT 安装目录复制 `QQEX.exe` 到 NapCat Shell 根目录
  - 这是扫码登录能正常生成二维码的关键
- OneBot v11 反向 WebSocket 地址设为 `ws://127.0.0.1:6219/ws`

## 3. Ollama 与记忆

- 安装 Ollama
- 把模型目录设置为本地目录，例如 `Ollama/models`
- 拉取 `bge-m3`
- CPU 环境可设置 `OLLAMA_LLM_LIBRARY=cpu`
- 建议设置 `OLLAMA_KEEP_ALIVE=24h`，减少记忆召回冷启动

## 4. 本机密钥文件

在项目根目录创建以下文件，内容只留在本机：

```text
后台.txt
  账号：你的 AstrBot 后台账号
  密码：你的 AstrBot 后台密码

大号QQ.txt
  你的 QQ 号

图片API.txt
  account_id=你的 Cloudflare Account ID
  api_token=你的 Workers AI API Token

deepseek-key.txt
  你的 DeepSeek API Key
```

如果语音选豆包（`voice` 为 `3`），再创建 `豆包语音.txt`。用默认的 Breeze（`voice` 为 `4`）不需要豆包凭证。

这些文件已被 `.gitignore` 排除。

## 5. 可选：本机唱歌

唱歌默认用 SoulX-Singer，在本机显卡上按谱唱，不花云端费用：

- 需要 NVIDIA 显卡，显存 6 GB 以上；RTX 50 系使用 CUDA 12.8 / torch 2.7.1
- 模型约 2.8 GB，独立环境约 5 GB
- 在 `plugins/astrbot_plugin_dafeiyu_sing/sing_server` 里运行 `setup_windows.ps1`
- 启动 `start_sing_server.bat`，看到 `http://127.0.0.1:18620` 即可
- 启动器和看门狗会自动拉起这个服务

没有本地唱歌服务时，插件会提示“嗓子哑了”，不会影响普通语音。

## 6. 导入配置

```powershell
Copy-Item .\回答.example.json .\回答.json
# 编辑 回答.json，把文件路径改成本机路径
python .\tools\import_dafeiyu.py
```

导入工具会通过 AstrBot 后台 API 写入人格、插件、记忆和语音配置。`回答.example.json` 默认 `voice` 是 `4`，也就是本机 Breeze；要先用 `PACK_README.md` 的「本机语音 Breeze」装好并做好 `dafeiyu` 音色。不要在没有确认的情况下重跑导入，否则可能覆盖本机配置。

## 7. 启动

双击 `启动机器人.bat`，或运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-bot.ps1
```

启动器会同时拉起 Breeze、SoulX、AstrBot 和 NapCat；AstrBot 与 NapCat 并行启动，控制台隐藏。桌面快捷方式和开机启动都指向同一个脚本，重复双击不会重复启动；看门狗会清理重复的 NapCat 进程，避免两个实例互相顶号。

如果 NapCat 登录态失效，启动器会打开 `qr.html` 对应的扫码页。只有登录态真正失效时才需要扫码，不要把机器人 QQ 同时登在别的设备上。

## 8. 验证

- `http://127.0.0.1:6218/` 返回 200
- 本机 6219 端口有已建立的 WebSocket 连接
- 用管理员 QQ 私聊机器人，确认能收到文字回复
- 发一张图片和一段短视频，确认视觉识别正常
- 发“画一张蓝鲸女仆”，确认能收到生图；没有 Cloudflare 凭证时会回退 Pollinations

## 媒体补丁

图片直传和视频关键帧需要 AstrBot 侧的小改动，见 `patches/README.md`。
