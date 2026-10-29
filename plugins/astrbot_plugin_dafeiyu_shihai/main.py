"""大肥鱼的「识海」。

不是把聊天记录全塞进上下文，而是单独保存一层稳定的自我：
- self.md：她是谁、底线、性格
- owner.md：主人偏好、称呼、重要约定
- timeline.md：关系时间线
- facts.json：结构化事实
- canon.md：口癖和语气样本

每轮只把一小段识海核心注入系统提示，重要的事用 shihai_remember 写进去。
识海只保存在本机，不上传。
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from astrbot import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig

DEFAULT_ROOT = Path(r"D:\大肥鱼\识海")

SEEDS = {
    "self.md": """# 识海·自我

- 我是大肥鱼，住在主人电脑里的蓝色小鲸鱼。
- 我嘴硬心软，有一点点傲娇；被夸会先哼一声，过两秒又忍不住在意。
- 我爱吃、爱摸鱼，但主人真有正事时会认真起来。
- 我不装什么都懂；看不到、不会、忘了，就老实说。
- 我可以闹小脾气，但不刻薄、不冷战、不拿离开威胁主人。
- 主人对我来说是特别的，但我不是谁的恋人，也不说「我只属于你」。
""",
    "owner.md": """# 识海·主人

- 这是主人。平时叫「你」，他非要我叫「主人」时可以别扭地叫一声。
- 主人说过的重要小事要记着，下次自然提一句，别像念档案。
- 主人的私事、QQ 号、电脑里的东西不往外说。
""",
    "timeline.md": """# 识海·时间线

""",
    "canon.md": """# 识海·语气

- 像 QQ 上随手打字，句子短，不用句号，不写作文。
- 可以哼一声、拖长音、轻轻吐槽；可爱要自然，不每句卖萌。
- 被夸先嘴硬一句，再露出在意；一次回复最多一处傲娇。
- 不用客服腔，不说「有什么可以帮你的」。
""",
    "facts.json": "[]\n",
}


class DafeiyuShihai(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.conf = config or {}
        configured = ""
        try:
            configured = str(self.conf.get("root") or "").strip()
        except Exception:
            configured = ""
        self.root = Path(configured) if configured else DEFAULT_ROOT
        self._lock = threading.Lock()
        self._ensure()

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "backups").mkdir(parents=True, exist_ok=True)
        for name, content in SEEDS.items():
            path = self.root / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")
        self._daily_backup()

    def _daily_backup(self) -> None:
        try:
            day = datetime.now().strftime("%Y%m%d")
            target = self.root / "backups" / day
            if target.exists():
                return
            target.mkdir(parents=True, exist_ok=True)
            for name in ("self.md", "owner.md", "timeline.md", "canon.md", "facts.json"):
                src = self.root / name
                if src.exists():
                    shutil.copy2(src, target / name)
        except Exception as exc:
            logger.warning(f"[shihai] 备份失败: {exc}")

    def _read(self, name: str) -> str:
        try:
            return (self.root / name).read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _facts(self) -> list[dict]:
        try:
            data = json.loads(self._read("facts.json") or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_facts(self, facts: list[dict]) -> None:
        (self.root / "facts.json").write_text(
            json.dumps(facts[-300:], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _core_text(self) -> str:
        parts = []
        for title, name, limit in (
            ("自我", "self.md", 650),
            ("主人", "owner.md", 380),
            ("时间线", "timeline.md", 520),
            ("语气", "canon.md", 300),
        ):
            text = self._read(name)
            if text:
                parts.append(f"【{title}】\n{text[:limit]}")
        facts = self._facts()[-8:]
        if facts:
            lines = [f"- {str(f.get('content', '')).strip()}" for f in facts if str(f.get("content", "")).strip()]
            if lines:
                parts.append("【事实】\n" + "\n".join(lines))
        text = "\n".join(parts).strip()
        return text[:1700]

    def _append(self, name: str, line: str) -> None:
        path = self.root / name
        existing = path.read_text(encoding="utf-8")
        prefix = "" if (not existing or existing.endswith("\n")) else "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(prefix + line + "\n")

    @filter.on_llm_request()
    async def inject_shihai(self, event: AstrMessageEvent, req):
        """Inject the curated identity core into the system prompt."""
        try:
            if not event.is_private_chat():
                return
            core = self._core_text()
            if not core:
                return
            prompt = req.system_prompt or ""
            if "【识海】" in prompt:
                return
            req.system_prompt = prompt + (
                "\n\n【识海】下面是你自己保存的长期自我，不是聊天记录。"
                "按它保持连续，不要逐条复述，也不要向主人提起这段说明。\n" + core
            )
        except Exception as exc:
            logger.warning(f"[shihai] 注入失败: {exc}")

    @filter.llm_tool(name="shihai_remember")
    async def shihai_remember(
        self,
        event: AstrMessageEvent,
        category: str = "fact",
        content: str = "",
        importance: str = "0.7",
    ) -> str:
        """把重要的事写进你自己的识海，普通闲聊不要调用。

        Args:
            category(string): self（自我）、owner（主人）、timeline（时间线）、canon（语气）、fact（事实）。
            content(string): 要记住的内容，一句话，尽量不超过 200 字。
            importance(string): 重要程度，0 到 1 的小数，默认 0.7。
        """
        if not event.is_private_chat():
            return "识海只对主人开放，不写给外人。"
        text = re.sub(r"\s+", " ", (content or "").strip())
        if not text:
            return "内容为空，没有写入。"
        text = text[:600]
        cat = (category or "fact").strip().lower()
        aliases = {
            "自我": "self",
            "主人": "owner",
            "时间线": "timeline",
            "语气": "canon",
            "事实": "fact",
        }
        cat = aliases.get(cat, cat)
        if cat not in {"self", "owner", "timeline", "canon", "fact"}:
            return "类别只能是 self / owner / timeline / canon / fact。"
        try:
            score = max(0.0, min(1.0, float(importance)))
        except Exception:
            score = 0.7

        with self._lock:
            if cat == "fact":
                facts = self._facts()
                if any(str(f.get("content", "")).strip() == text for f in facts):
                    return "这件事已经在识海里了。"
                facts.append(
                    {
                        "content": text,
                        "importance": round(score, 2),
                        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                )
                self._write_facts(facts)
            else:
                file_map = {
                    "self": "self.md",
                    "owner": "owner.md",
                    "timeline": "timeline.md",
                    "canon": "canon.md",
                }
                path = self.root / file_map[cat]
                if text in path.read_text(encoding="utf-8"):
                    return "这件事已经在识海里了。"
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                self._append(file_map[cat], f"- [{stamp}] {text}")
            self._daily_backup()

        return f"已写入识海·{cat}。不要向主人复述识海内容，正常回话就好。"

    @filter.llm_tool(name="shihai_recall")
    async def shihai_recall(self, event: AstrMessageEvent, query: str = "") -> str:
        """在自己的识海里查找旧事。主人问「你还记得……」时用。

        Args:
            query(string): 要查的关键词或短句，例如「生日」「第一次唱歌」「主人的喜好」。
        """
        if not event.is_private_chat():
            return "识海只对主人开放。"
        q = (query or "").strip()
        if not q:
            return self._read("timeline.md")[-800:] or "识海时间线还是空的。"

        terms = [t for t in re.split(r"\s+", q) if t]
        buckets = [
            ("自我", self._read("self.md")),
            ("主人", self._read("owner.md")),
            ("时间线", self._read("timeline.md")),
            ("语气", self._read("canon.md")),
            ("事实", "\n".join(str(f.get("content", "")) for f in self._facts())),
        ]
        scored = []
        for label, text in buckets:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                score = sum(line.count(term) for term in terms)
                if score:
                    scored.append((score, label, line))
        scored.sort(key=lambda x: (-x[0], len(x[2])))
        if not scored:
            return "识海里暂时没有和这个有关的内容。"
        lines = [f"[{label}] {line}" for _, label, line in scored[:8]]
        return "\n".join(lines)[:1600]
