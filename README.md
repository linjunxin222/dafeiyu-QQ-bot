# 大肥鱼 QQ 机器人（脱敏公开版）

AstrBot + NapCat + DeepSeek 的 Windows QQ 机器人配置与脚本。

这个仓库是从本机运行目录整理出来的**脱敏版本**，只保留可分享的配置、人格、插件代码和启动脚本。

## 不包含的内容

为了安全，以下内容没有上传：

- DeepSeek / 豆包 API Key
- 机器人 QQ 号、主人 QQ 号
- AstrBot 后台账号和密码
- OneBot / NapCat 的 token
- 聊天记录、长期记忆数据库、日志
- 语音试听、声音参考等个人音频
- AstrBot 虚拟环境、NapCat/QQ 运行文件、Ollama 模型
- 表情包二进制资源

这些文件需要在使用者本机重新创建，或通过 AstrBot 后台配置。

## 功能

- DeepSeek 对话，支持文字和图片输入
- QQ 私聊，只允许指定主人
- 长期记忆（本机 Ollama + bge-m3）
- 豆包 Seed TTS 2.0 语音，甜美桃子音色，语速 -5%
- 表情包、QQ 空间、个性签名工具
- 视频消息抽取最多 6 帧关键画面后交给视觉模型
- 启动器 + 看门狗，异常退出自动恢复
- 电脑/文件/终端/浏览器能力默认关闭

## 目录

```text
.
├─ start-bot.ps1                 # 后台启动 AstrBot + NapCat，并启动看门狗
├─ watch-bot.ps1                 # 看门狗，自动恢复 AstrBot / NapCat / Ollama
├─ 启动机器人.bat                # 调用 start-bot.ps1 的入口
├─ 使用说明.txt
├─ qr.html                       # 本机 QQ 扫码登录页
├─ persona/大肥鱼.md            # 人设
├─ plugins/                      # 自定义 AstrBot 插件
├─ tools/import_dafeiyu.py       # 配置导入工具
├─ 回答.example.json             # 回答文件模板，复制为 回答.json 后填写
├─ docs/SETUP.md                 # 安装步骤
├─ patches/                      # 媒体识别所需的 AstrBot 侧改动说明
├─ PACK_README.md                # 原配置包说明
└─ LICENSE
```

## 快速开始

完整步骤见 [docs/SETUP.md](docs/SETUP.md)。最短流程：

1. 安装 AstrBot 4.29.3，放在 `AstrBot/app`，虚拟环境放在 `AstrBot/venv`。
2. 安装 NapCat 9.9.33-52230，放在 `NapCat/NapCat.52230.Shell`。
3. 从同版本 QQNT 安装目录复制 `QQEX.exe` 到 NapCat Shell 根目录。
4. 安装 Ollama，拉取 `bge-m3`，设置 `OLLAMA_MODELS` 和 CPU 模式。
5. 在本机创建密钥文件，不要把密钥提交到仓库。
6. 复制 `回答.example.json` 为 `回答.json`，填写本机文件路径。
7. 运行 `python tools/import_dafeiyu.py`。
8. 双击 `启动机器人.bat`，按提示扫码登录 QQ。

## 安全说明

- 这是公开仓库，**绝对不要**把真实 Key、QQ 号、后台密码、Cookie 或聊天记录提交上来。
- `start-bot.ps1` 和 `watch-bot.ps1` 使用相对路径，默认从脚本所在目录启动。
- 机器人默认只允许管理员私聊；群聊和其他 QQ 会被拦截。
- 电脑操作、文件、终端、浏览器工具仍然关闭。

## 媒体识别

图片和 QQ 表情包会作为图片输入交给视觉模型。视频会由 ffmpeg 抽取关键帧并拼成一张图，再交给视觉模型；不会上传完整视频，也不识别视频声音。

媒体支持需要 AstrBot 侧的两个小改动，见 [patches/README.md](patches/README.md)。

## 许可

配置包部分沿用原仓库的 MIT License，见 `LICENSE`。AstrBot、NapCat、QQ、Ollama 和豆包服务分别遵循它们自己的许可与服务条款。
