# Changelog

## 2026-10-29

- 接入本机 SoulX-Singer 唱歌服务，支持三首儿歌，启动器/看门狗自动拉起
- 记忆速度优化：召回 6 条、最近 3 条、上下文 70 条、反思 8 轮；保留全部记忆并启用主动记忆工具
- 启动器合并 Breeze/SoulX/AstrBot/NapCat，并行启动、开机自启；增加启动互斥和 NapCat 单实例保护，修复重复实例互相顶号导致的频繁扫码
- 新增 `astrbot_plugin_dafeiyu_face`：`send_qq_face` 发送 QQ 原生小黄脸，本地梗图继续走 `search_memes`
- 语音触发频率从 0.2 降到 0.1；人格加入一点傲娇，被夸先嘴硬再露出在意，一次回复最多一处
- 新增 `astrbot_plugin_dafeiyu_shihai`：本机识海，保存自我、主人、时间线、事实和语气，每轮注入小段核心

## 2026-10-28

- 接入 Breeze TTS 2 本机语音，默认音色 `dafeiyu`，语音频率约五条回复一次
- 整条回复只合成一条语音，修复分段回复导致的“一段一段”语音
- 生图插件 `astrbot_plugin_dafeiyu_imagegen`：Cloudflare Workers AI FLUX 主接口、Pollinations 回退、默认二次元、`/生图` 兜底
- 图片识别最长边提高到 2048px
- 长期记忆召回 10 条、最近 5 条，关闭自动衰减和自动清理，上下文窗口 100 条
- 看门狗增加 Breeze 健康检查和自动重启
- 启动器/看门狗增加 NapCat 快速登录、AstrBot 无缓冲日志
- 补充脱敏的 `settings/pack.json`、Breeze 安装/做声音脚本、生图插件
- 增加仓库自检、CI、安全策略、贡献说明和 Issue/PR 模板

## 2026-10-27

- 初始脱敏公开版本：AstrBot + NapCat + DeepSeek + 长期记忆 + 表情包 + 视频关键帧
