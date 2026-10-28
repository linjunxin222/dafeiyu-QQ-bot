# 整条回复合成一条语音

AstrBot 4.29.3 默认先做分段回复，再对每个 `Plain` 段分别调用 TTS，所以一次回复会变成好几条语音，听起来一段一段的。

这个仓库对应的本机改法：

- 文件：`astrbot/core/pipeline/result_decorate/stage.py`
- 位置：`if should_tts and tts_provider:` 分支

改法：

1. 先把 `result.chain` 里所有要朗读的 `Plain.text` 按原顺序拼成一个完整字符串。
2. 只调用一次 `tts_provider.get_audio(combined_text)`。
3. 把原来所有可朗读的 `Plain` 段替换成一个 `Record`，放在第一个文本段的位置。
4. 保留图片、表情等非文本组件。
5. `dual_output` 开启时，文字也只输出合并后的一份。
6. TTS 失败时保留原来的分段文本，不会丢消息。

这样分段回复仍然保留，但命中语音的那一次只发一条完整语音。

完整 unified diff：[tts_whole_reply.diff](tts_whole_reply.diff)

在 AstrBot 源码根目录可以检查/应用：

```powershell
git apply --check patches/tts_whole_reply.diff
git apply patches/tts_whole_reply.diff
```

修改前建议备份 `stage.py`。AstrBot 升级后这个文件可能被覆盖，升级后要重新检查。
