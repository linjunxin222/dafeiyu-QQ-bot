# 大肥鱼生图插件

给大肥鱼加一个 `generate_image` 工具，生成后直接把图片发到 QQ。

- 主接口：Cloudflare Workers AI `FLUX.1 schnell`，1024px，8 步，默认二次元动漫风
- 备用：Cloudflare 失败时自动回退 Pollinations
- 冷却：同一会话 18 秒
- 兜底命令：`/生图 一只蓝鲸女仆`

## 配置

在项目根目录创建 `图片API.txt`（已在 `.gitignore` 中排除），内容：

```text
account_id=你的 Cloudflare Account ID
api_token=你的 Workers AI API Token
```

Token 权限只需要 `Workers AI:Read`（或 Edit）。不要把这个文件提交到仓库。

如果暂时没有 Cloudflare 凭证，插件会自动只用 Pollinations。
