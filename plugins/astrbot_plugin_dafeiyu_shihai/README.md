# 大肥鱼识海

给大肥鱼一层轻量的长期自我：

- `self.md`：她是谁、性格、底线
- `owner.md`：主人偏好、称呼、重要约定
- `timeline.md`：关系时间线
- `facts.json`：结构化事实，带时间、来源、可信度
- `canon.md`：口癖和语气样本
- `open_loops.json`：答应过、还没做完的事
- `backups/`：每日备份

每轮只注入一小段识海核心；重要内容用 `shihai_remember` 写入，问旧事用 `shihai_recall`。  
答应的事用 `shihai_open_loop` 记录，完成后用 `shihai_close_loop` 关闭。  
每天 04:00 做一次无 LLM 的整理：合并重复事实、去重时间线、刷新备份，不删除独特记忆。

默认目录：`D:\大肥鱼\识海`。识海只在本机，不上传。
