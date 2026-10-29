"""给大肥鱼加一个发送 QQ 原生小黄脸的工具。

本地表情包继续走 meme_manager 的 search_memes；这个插件只管 QQ 自带的小黄脸
（OneBot 的 face 段），不依赖图片文件，也不会把表情名当普通文字发出去。
"""

import astrbot.api.message_components as Comp
from astrbot import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig

FACE_MAP = {
    "微笑": 1,
    "撇嘴": 2,
    "色": 3,
    "发呆": 4,
    "得意": 5,
    "流泪": 6,
    "害羞": 7,
    "闭嘴": 8,
    "睡": 9,
    "大哭": 10,
    "尴尬": 11,
    "发怒": 12,
    "调皮": 13,
    "呲牙": 14,
    "惊讶": 15,
    "难过": 16,
    "酷": 17,
    "冷汗": 18,
    "抓狂": 19,
    "吐": 20,
    "偷笑": 21,
    "可爱": 22,
    "白眼": 23,
    "傲慢": 24,
    "饥饿": 25,
    "困": 26,
    "惊恐": 27,
    "流汗": 28,
    "憨笑": 29,
    "悠闲": 30,
    "奋斗": 31,
    "咒骂": 32,
    "疑问": 33,
    "嘘": 34,
    "晕": 35,
    "折磨": 36,
    "衰": 37,
    "骷髅": 38,
    "敲打": 39,
    "再见": 40,
    "擦汗": 41,
    "抠鼻": 42,
    "鼓掌": 43,
    "糗大了": 44,
    "坏笑": 45,
    "左哼哼": 46,
    "右哼哼": 47,
    "哈欠": 48,
    "鄙视": 49,
    "委屈": 50,
    "快哭了": 51,
    "阴险": 52,
    "亲亲": 53,
    "吓": 54,
    "可怜": 55,
    "菜刀": 56,
    "西瓜": 57,
    "啤酒": 58,
    "篮球": 59,
    "乒乓": 60,
    "咖啡": 61,
    "饭": 62,
    "猪头": 63,
    "玫瑰": 64,
    "凋谢": 65,
    "示爱": 66,
    "爱心": 67,
    "心碎": 68,
    "蛋糕": 69,
    "闪电": 70,
    "炸弹": 71,
    "刀": 72,
    "足球": 73,
    "瓢虫": 74,
    "便便": 75,
    "月亮": 76,
    "太阳": 77,
    "礼物": 78,
    "拥抱": 79,
    "强": 80,
    "弱": 81,
    "握手": 82,
    "胜利": 83,
    "抱拳": 84,
    "勾引": 85,
    "拳头": 86,
    "差劲": 87,
    "爱你": 88,
    "NO": 89,
    "OK": 90,
    "爱情": 91,
    "飞吻": 92,
    "跳跳": 93,
    "发抖": 94,
    "怄火": 95,
    "转圈": 96,
    "磕头": 97,
    "回头": 98,
    "跳绳": 99,
    "挥手": 100,
    "激动": 101,
    "街舞": 102,
    "献吻": 103,
    "左太极": 104,
    "右太极": 105,
}

ALIASES = {
    "笑": "微笑",
    "笑脸": "微笑",
    "开心": "微笑",
    "高兴": "微笑",
    "嘿嘿": "偷笑",
    "偷笑": "偷笑",
    "哭": "快哭了",
    "想哭": "快哭了",
    "委屈巴巴": "委屈",
    "生气": "发怒",
    "气鼓鼓": "发怒",
    "害羞脸": "害羞",
    "可爱脸": "可爱",
    "点赞": "强",
    "赞": "强",
    "加油": "奋斗",
    "晚安": "睡",
    "困困": "困",
    "比心": "爱心",
    "心": "爱心",
    "亲": "亲亲",
    "飞吻": "飞吻",
    "ok": "OK",
    "OK": "OK",
    "no": "NO",
    "收到": "OK",
    "好的": "OK",
    "再见": "再见",
    "拜拜": "再见",
}


class DafeiyuQQFace(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.conf = config

    @filter.llm_tool(name="send_qq_face")
    async def send_qq_face(
        self,
        event: AstrMessageEvent,
        face: str = "",
        face_id: str = "",
    ) -> str:
        """发送一个 QQ 原生小黄脸（OneBot face 段），不是普通文字。

        Args:
            face(string): 表情名称，例如「微笑」「调皮」「委屈」「快哭了」「OK」「强」「爱心」「飞吻」「再见」。
            face_id(string): 可选，直接指定 QQ 原生表情 ID（填数字字符串）；通常留空，用 face 名称即可。
        """
        raw = (face or "").strip()
        fid = 0
        if (face_id or "").strip().isdigit():
            fid = int((face_id or "").strip())
        if not fid and raw:
            key = ALIASES.get(raw, raw)
            if key.isdigit():
                fid = int(key)
            else:
                fid = FACE_MAP.get(key, 0)
        if not fid:
            names = "、".join(list(FACE_MAP.keys())[:30])
            return f"没有找到这个QQ原生表情。可以用这些名字：{names}"

        try:
            await event.send(MessageChain([Comp.Face(id=fid)]))
        except Exception as exc:
            logger.warning(f"发送QQ原生表情失败: {exc}")
            return "QQ表情没发出去，换个表情或者直接用文字回。"

        return "已发送QQ原生表情。只回一句很短的话，不要重复表情名，也不要再发一遍。"
