"""大肥鱼翻唱与本地找歌。

用法：
- 发一段带伴奏的整首或清唱，配一句“翻唱”，默认用本机 RVC 大肥鱼模型
  跟着原唱的音高/旋律转换；RVC 不可用时回退 SoulX-SVC。
- 发音频时写“存歌 歌名”，会存进本地歌曲库，之后说“唱 歌名”即可直接翻唱。
- “找歌 歌名”：先找本地歌曲库，再查 iTunes 元数据（只查信息，不下载版权歌曲）。
- “唱 歌名”：只从本地歌曲库找，找到就翻唱。

外部版权歌曲不会自动下载；想翻唱哪首，把音频/清唱发进来。
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import aiohttp

import astrbot.api.message_components as Comp
from astrbot import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig

LIBRARY = Path(r"D:\大肥鱼\歌曲库")
TEMP = Path(r"D:\大肥鱼\temp\cover")
OUT = Path(r"D:\dafeiyu\sing\out")
RUNNER = Path(r"D:\大肥鱼\tools\run_svc_cover.ps1")
AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".amr", ".silk"}
KEYWORDS = ("翻唱", "cover", "唱这首", "唱一下这首")
SAVE_KEYWORDS = ("存歌", "入库", "保存歌曲")


class DafeiyuCover(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.conf = config or {}
        self._lock = asyncio.Lock()
        LIBRARY.mkdir(parents=True, exist_ok=True)
        TEMP.mkdir(parents=True, exist_ok=True)

    def _audio_components(self, event: AstrMessageEvent):
        comps = getattr(getattr(event, "message_obj", None), "message", None) or []
        out = []
        for c in comps:
            if isinstance(c, (Comp.Record, Comp.File)):
                out.append(c)
        return out

    async def _download_attachment(self, comp) -> Path | None:
        # Record: file / url / path; File: url / file_ / file property.
        raw = ""
        name = "audio"
        if isinstance(comp, Comp.Record):
            raw = str(getattr(comp, "url", "") or getattr(comp, "file", "") or "")
            name = str(getattr(comp, "path", "") or "voice")
        else:
            raw = str(getattr(comp, "url", "") or getattr(comp, "file_", "") or "")
            name = str(getattr(comp, "name", "") or "file")
        local = str(getattr(comp, "path", "") or "") if isinstance(comp, Comp.Record) else str(getattr(comp, "file_", "") or "")
        if local and os.path.isfile(local):
            return Path(local)
        if raw.startswith("file://"):
            from urllib.parse import unquote, urlparse

            path_text = unquote(urlparse(raw).path)
            if re.match(r"^/[A-Za-z]:/", path_text):
                path_text = path_text[1:]
            p = Path(path_text)
            return p if p.is_file() else None
        if raw.startswith("base64://"):
            data = base64.b64decode(raw[9:])
            suffix = Path(name).suffix or ".audio"
            out = TEMP / f"input-{int(time.time())}{suffix}"
            out.write_bytes(data)
            return out
        if raw.startswith("http://") or raw.startswith("https://"):
            suffix = Path(name).suffix
            if suffix.lower() not in AUDIO_EXT:
                suffix = ".audio"
            out = TEMP / f"input-{int(time.time())}{suffix}"
            timeout = aiohttp.ClientTimeout(total=90)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(raw) as resp:
                    if resp.status != 200:
                        return None
                    size = 0
                    with out.open("wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 256):
                            size += len(chunk)
                            if size > 80 * 1024 * 1024:
                                return None
                            f.write(chunk)
            return out
        if raw and os.path.isfile(raw):
            return Path(raw)
        return None

    def _local_matches(self, query: str) -> list[Path]:
        q = (query or "").strip().lower()
        if not q:
            return []
        files = [p for p in LIBRARY.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT]
        exact = [p for p in files if q == p.stem.lower() or q in p.name.lower()]
        return sorted(exact, key=lambda p: len(p.name))[:8]

    async def _itunes(self, query: str) -> list[str]:
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://itunes.apple.com/search",
                    params={"term": query, "entity": "song", "limit": 5, "country": "CN"},
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)
            out = []
            for item in (data.get("results") or [])[:5]:
                title = str(item.get("trackName") or "").strip()
                artist = str(item.get("artistName") or "").strip()
                if title:
                    out.append(f"{title} - {artist}" if artist else title)
            return out
        except Exception as exc:
            logger.info(f"[cover] iTunes 搜索失败: {exc}")
            return []

    async def _reply(self, event: AstrMessageEvent, text: str):
        await event.send(MessageChain([Comp.Plain(text=text)]))

    async def _save_song(self, event: AstrMessageEvent, target: Path, title: str):
        title = (title or "").strip()
        if not title:
            await self._reply(event, "要存哪首？发音频时写「存歌 歌名」，比如「存歌 雨爱」。")
            return
        safe = re.sub(r'[\\/:*?"<>|]', "_", title).strip()[:80] or "未命名"
        suffix = target.suffix.lower()
        if suffix not in AUDIO_EXT:
            suffix = ".wav"
        dest = LIBRARY / f"{safe}{suffix}"
        if dest.exists():
            dest = LIBRARY / f"{safe}-{int(time.time())}{suffix}"
        shutil.copy2(target, dest)
        await self._reply(event, f"存好了：{dest.stem}。以后说「唱 {safe}」就能直接翻唱。")

    async def _cover(self, event: AstrMessageEvent, target: Path):
        if self._lock.locked():
            await self._reply(event, "上一首还在开嗓，等我唱完这首。")
            return
        async with self._lock:
            out = OUT / f"cover-{int(time.time())}.wav"
            await self._reply(event, "收到，等我开嗓，这首要几十秒。")
            cmd = [
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RUNNER),
                "-Target",
                str(target),
                "-Out",
                str(out),
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    creationflags=0x08000000,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
                log = (stdout or b"").decode("utf-8", "replace")[-500:]
                if proc.returncode != 0 or not out.exists():
                    logger.warning(f"[cover] 失败: {log}")
                    await self._reply(event, "这次没唱出来，可能音频不是干净人声，或者模型没加载成功。")
                    return
            except asyncio.TimeoutError:
                await self._reply(event, "这次唱太久了，先放弃。")
                return
            except Exception as exc:
                logger.warning(f"[cover] 异常: {exc}")
                await self._reply(event, "翻唱出错了，等会儿再试。")
                return
            await event.send(MessageChain([Comp.Record(file=str(out))]))
            await self._reply(event, "唱完啦，听听像不像我。")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        if not event.is_private_chat():
            return
        text = (event.message_str or "").strip()
        audio = self._audio_components(event)

        if audio and text.startswith(SAVE_KEYWORDS):
            event.stop_event()
            target = await self._download_attachment(audio[0])
            if not target:
                await self._reply(event, "音频没下载下来，换一个文件再存。")
                return
            title = re.sub(r"^(存歌|入库|保存歌曲)\s*", "", text).strip()
            if not title:
                title = target.stem
            await self._save_song(event, target, title)
            return

        if audio and any(k in text.lower() for k in KEYWORDS):
            event.stop_event()
            target = await self._download_attachment(audio[0])
            if not target:
                await self._reply(event, "音频没下载下来，换一个文件或者发清唱再试。")
                return
            await self._cover(event, target)
            return

        if text.startswith(("找歌", "搜歌")):
            event.stop_event()
            query = re.sub(r"^(找歌|搜歌)\s*", "", text).strip()
            if not query:
                await self._reply(event, "想找哪首？说「找歌 歌名」。")
                return
            local = self._local_matches(query)
            if local:
                names = "、".join(p.stem for p in local[:5])
                await self._reply(event, f"本地歌曲库里有：{names}。说「唱 {local[0].stem}」就可以翻唱。")
                return
            found = await self._itunes(query)
            if found:
                await self._reply(
                    event,
                    "网上查到这些：" + "；".join(found) +
                    "。我不能直接下载版权歌曲，你把这首歌的音频或清唱发我，我就能翻唱。",
                )
            else:
                await self._reply(event, "没找到。把歌名说清楚一点，或者直接把音频发我。")
            return

        if text.startswith(("唱 ", "翻唱 ")):
            event.stop_event()
            query = re.sub(r"^(唱|翻唱)\s*", "", text).strip()
            local = self._local_matches(query)
            if not local:
                found = await self._itunes(query)
                hint = "；".join(found[:3]) if found else "没查到"
                await self._reply(
                    event,
                    f"本地歌曲库没有这首。查到的信息：{hint}。我不会下载版权歌曲，你把音频或清唱发我，配一句「翻唱」。",
                )
                return
            await self._cover(event, local[0])
            return
