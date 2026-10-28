# AstrBot 媒体识别补丁说明

这个仓库不包含 AstrBot 的完整源码。若要让图片、QQ 表情包和视频关键帧真正进入模型，需要对 AstrBot 4.29.3 做以下三处小改动。

## 1. 启用图片输入

在 AstrBot 的模型提供商配置中，把主模型的 `modalities` 加上 `image`：

```json
"modalities": ["text", "tool_use", "image"]
```

DeepSeek 的 `deepseek-flash` 已实测可以接收图片。

## 2. 视频关键帧

新增 `astrbot/core/utils/video_frames.py`，用 ffmpeg 抽取最多 6 帧并拼成一张图。

然后在 `astrbot/core/astr_main_agent.py` 的 `_append_video_attachment()` 中：

- 把视频转成本地路径
- 调用 `make_video_montage(video_path)`
- 把返回的图片路径加入 `req.image_urls`
- 同时加一段文字说明这是视频关键帧拼图

本目录下的 `video_frames.py` 是可用的通用版本。它优先使用环境变量 `FFMPEG_PATH`，其次使用 PATH 中的 `ffmpeg`。

## 3. QQ 表情包兜底

NapCat 通常会把商城表情转成 `image` 段。若某些客户端仍发送 `mface` 段，`aiocqhttp_platform_adapter.py` 原来的逻辑会直接丢弃。

把 `mface` 分支改成：

- 有 `url` 时添加 `Image(file=url)`
- 有 `summary` 时添加 `Plain(text=summary)`
- 把 `summary` 拼进 `message_str`

## 注意

- 没有 `image` modality 时，图片会被跳过或只能走 caption 提供商。
- 视频只识别画面，不识别声音。
- 图片和视频关键帧会发送给所配置的视觉模型服务。
