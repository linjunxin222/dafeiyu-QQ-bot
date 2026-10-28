# 安全策略

## 不要提交的内容

这个仓库是公开的。请不要在 Issue、PR、日志或提交里放入：

- DeepSeek、豆包、Cloudflare 或其他 API Key / Token
- QQ 号、AstrBot 后台账号密码、OneBot Token
- 聊天记录、长期记忆数据库、二维码、Cookie
- 个人语音样本、生成的私密图片

`图片API.txt`、`后台.txt`、`大号QQ.txt`、`deepseek-key.txt`、`豆包语音.txt`、`回答.json` 都已被 `.gitignore` 排除。

## 密钥泄露了怎么办

1. 立刻到对应平台撤销/轮换该密钥。
2. 如果是 Cloudflare Token，到 **My Profile → API Tokens** 删除旧 Token，重新生成。
3. 检查仓库历史，必要时重写历史；不要只删除当前文件。
4. 不要在新的 Issue/PR 里重复贴出泄露的密钥。

## 报告安全问题

请不要公开贴出可利用细节或密钥。可以在 GitHub 仓库的 **Security → Report a vulnerability** 中私下报告；如果该入口不可用，请开一个只说明“需要私下联系”的 Issue，不要包含敏感内容。

## 支持范围

当前只维护 `main` 分支。旧提交和第三方插件（AstrBot、NapCat、Ollama、Breeze、表情包等）的问题请同时参考各自上游项目。
