# 大肥鱼一键导入包

这个包只负责把**人格、插件、语音/记忆设置、表情包配置**导入一个已经能正常聊天的 AstrBot。

它**不会**代替你安装 AstrBot、NapCat 或 QQ。第一次用请先按 `SETUP.md` 把基础环境装好。

## 前提

1. Windows 10/11
2. AstrBot 已安装并启动，浏览器能打开后台（默认 `http://127.0.0.1:6218`）
3. NapCat 已接上 AstrBot，QQ 能正常收发
4. 知道 AstrBot 后台账号和密码
5. 知道自己的 QQ 号（只把这个号当主人）

## 使用

1. 下载 `dafeiyu-config-pack-v1.0.0.zip` 并解压
2. 双击 `安装大肥鱼.bat`
3. 按提示输入：
   - AstrBot 后台地址（直接回车用默认值）
   - 后台账号
   - 后台密码
   - 你的 QQ 号
   - 记忆：`0` 不装、`1` 本机 Ollama、`2` 硅基流动
   - 语音：`4` 本机 Breeze、`3` 豆包、`0` 不开
4. 等导入完成，去 QQ 发一句「在吗」

如果之前聊过，先发 `/reset` 清掉旧对话。

## 导入失败

脚本会把错误留在窗口里。常见原因：

- AstrBot 后台没开：先启动 AstrBot
- 后台地址不对：默认是 `6218`，你的实例可能是 `6185`，在 AstrBot 启动日志里看
- 账号/密码不对：就是登录 AstrBot 网页用的那个
- 找不到 Python：用 `-AstrBotPath` 指定 AstrBot 目录，或用 `-PythonPath` 指定 AstrBot 的 `python.exe`

高级用法：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\安装大肥鱼.ps1 `
  -BaseUrl http://127.0.0.1:6218 `
  -AstrBotPath D:\大肥鱼\AstrBot `
  -Memory 0 -Voice 4
```

只检查环境、不写入：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\安装大肥鱼.ps1 -DryRun
```

## 可选模型包

主包不含大模型和 RVC 声音模型。需要本机唱歌/翻唱时，另外下载：

- `dafeiyu-rvc-model-v1.1.0.zip`：RVC 翻唱模型（约 170MB）
- Breeze：`装Breeze语音.bat` 自动下载
- SoulX：按 `plugins/astrbot_plugin_dafeiyu_sing/README.md` 安装
- ComfyUI/NoobAI：按 `plugins/astrbot_plugin_dafeiyu_imagegen/README.md`

## 安全

- 安装包不含任何人的 API Key、QQ 号、后台密码、聊天记录、识海数据
- 密码只在导入时通过临时 `回答.json` 传给本机导入工具，完成后立即删除
- 每个用户用自己的 QQ 小号、自己的 API Key
- 公开仓库不包含 `后台.txt`、`大号QQ.txt`、`deepseek-key.txt`、`图片API.txt`、`豆包语音.txt`
