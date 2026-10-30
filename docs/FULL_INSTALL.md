# 大肥鱼全自动安装器（Beta）

这个版本会自动处理：

- 安装 Python 3.12（没有时）
- 下载 AstrBot 4.29.3 源码
- 创建 AstrBot 虚拟环境并安装依赖
- 下载 AstrBot 后台静态文件
- 生成 AstrBot 配置（后台 6218、OneBot 6219、DeepSeek provider）
- 下载并解压 NapCat
- 导入大肥鱼人格、插件、语音和记忆设置
- 生成启动脚本

## 仍需要人工的两步

1. 电脑上要先安装官方 QQNT（QQ）
2. 运行 `NapCat\NapCatInstaller.exe` 安装/启动 NapCat，并扫码登录机器人 QQ
3. 在 NapCat 里确认反向 WebSocket：`ws://127.0.0.1:6219/ws`

QQ 首次登录无法自动扫码，这是硬限制。

## 使用

双击 `安装全自动.bat`，按提示输入：

- 安装目录（默认 `D:\大肥鱼`）
- 主人 QQ
- AstrBot 后台密码（可直接回车自动生成）
- DeepSeek API Key

脚本会先启动 AstrBot 生成配置，再改成 6218 并重新启动，最后导入配置包。

## 失败怎么办

日志：

- `安装目录\logs\astrbot.out.log`
- `安装目录\logs\astrbot.err.log`

常见问题：

- Python 安装失败：手动装 Python 3.12，再重跑
- AstrBot 依赖安装失败：换网络/镜像重跑
- 6185 首次启动超时：看 `astrbot.err.log`，可能是后台静态文件没下载成功
- 6218 起不来：确认 6218 没被占用
- DeepSeek 验证失败：确认 Key 有权限，模型名是 `deepseek-flash`

这个安装器是 Beta；AstrBot 版本或 NapCat 版本更新后可能需要调整。
