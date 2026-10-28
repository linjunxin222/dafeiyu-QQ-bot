import asyncio
import base64
import io
import json
import os
import random
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import aiohttp
from PIL import Image as PILImage
from PIL import ImageOps, ImageStat

import astrbot.api.message_components as Comp
from astrbot import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path

CF_FILE = Path(r"D:\大肥鱼\图片API.txt")
CF_MODEL = "@cf/black-forest-labs/flux-1-schnell"
ANIME_SUFFIX = (
    ", high-quality Japanese anime illustration, clean lineart, soft cel shading, "
    "beautiful detailed natural anime eyes, delicate face, no heavy makeup, "
    "masterpiece, best quality, ultra-detailed, harmonious colors, professional composition"
)
GENERIC_SUFFIX = (
    ", masterpiece, best quality, ultra-detailed, beautiful detailed eyes, "
    "clean lineart, soft cinematic lighting, harmonious colors, professional composition"
)


class DafeiyuImageGen(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.tasks = set()
        self.last_call = {}
        self.cooldown = 18

    @filter.llm_tool(name="generate_image")
    async def generate_image(
        self,
        event: AstrMessageEvent,
        prompt: str,
        aspect_ratio: str = "1:1",
    ) -> str:
        """Generate a high-quality anime image and send it to the user.

        Use this when the user asks you to draw, generate, or make a picture.
        The default style is clean Japanese anime / soft cel shading.
        If the user explicitly asks for 3D, realistic or photo style, put that
        requirement in the prompt; the plugin will not force anime then.
        Write the prompt as a detailed English description: subject, appearance,
        clothing, pose, background, lighting, camera/composition, style and mood.
        Keep the user's intent exactly; do not add unrelated concepts.

        Args:
            prompt(string): Detailed English image prompt.
            aspect_ratio(string): One of "1:1", "3:4", "4:3", "9:16", "16:9". Default 1:1.
        """
        text = (prompt or "").strip()
        if not text:
            return "没有画面描述，先问主人想画什么。"
        key = event.unified_msg_origin
        now = time.time()
        if now - self.last_call.get(key, 0) < self.cooldown:
            return "刚刚才画过一张，等十几秒再画；先跟主人说稍等一下。"
        self.last_call[key] = now
        task = asyncio.create_task(self._draw_and_send(event, text, aspect_ratio))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return (
            "开始画了，画好会直接把图发过去。"
            "你现在只回一句很短的话，比如「等我一下」，不要描述画面，也不要再调用工具。"
        )

    @filter.command("生图")
    async def image_command(self, event: AstrMessageEvent):
        """Manual fallback: /生图 <prompt>."""
        prompt = (event.message_str or "").strip()
        for prefix in ("/生图", "生图"):
            if prompt.startswith(prefix):
                prompt = prompt[len(prefix):].strip()
                break
        if not prompt:
            yield event.plain_result("想画什么？直接说「生图 一只蓝鲸女仆」。")
            return
        key = event.unified_msg_origin
        now = time.time()
        if now - self.last_call.get(key, 0) < self.cooldown:
            yield event.plain_result("刚画过一张，等我十几秒再画。")
            return
        self.last_call[key] = now
        task = asyncio.create_task(self._draw_and_send(event, prompt, "1:1"))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        yield event.plain_result("开始画了，画好直接发图。")

    @staticmethod
    def _prompt_with_style(prompt: str) -> str:
        base = prompt.strip().rstrip(",.")
        lower = base.lower()
        if any(k in lower for k in ("3d", "pixar", "realistic", "photorealistic", "photo", "写实", "真人")):
            return base + GENERIC_SUFFIX
        return base + ANIME_SUFFIX

    @staticmethod
    def _sizes(aspect_ratio: str) -> tuple[int, int]:
        sizes = {
            "1:1": (1024, 1024),
            "3:4": (896, 1152),
            "4:3": (1152, 896),
            "9:16": (768, 1344),
            "16:9": (1344, 768),
        }
        return sizes.get(str(aspect_ratio or "1:1"), (1024, 1024))

    @staticmethod
    def _cf_credentials() -> tuple[str, str]:
        if not CF_FILE.is_file():
            return "", ""
        account = token = ""
        for line in CF_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip().strip('"').strip("'")
            if key in ("account_id", "account", "id"):
                account = value
            elif key in ("api_token", "token", "api_key", "key"):
                token = value
        return account, token

    async def _send_image(self, event: AstrMessageEvent, data: bytes, width: int, height: int, trim_bottom: bool) -> None:
        image = PILImage.open(io.BytesIO(data)).convert("RGB")
        # FLUX sometimes letterboxes the actual scene with black bars.
        gray = image.convert("L")
        w, h = image.size
        top, bottom = 0, h
        while top < int(h * 0.08):
            stat = ImageStat.Stat(gray.crop((0, top, w, top + 1)))
            if stat.mean[0] > 8 or stat.stddev[0] > 4:
                break
            top += 1
        while bottom > h - int(h * 0.08):
            stat = ImageStat.Stat(gray.crop((0, bottom - 1, w, bottom)))
            if stat.mean[0] > 8 or stat.stddev[0] > 4:
                break
            bottom -= 1
        if top > 0 or bottom < h:
            image = image.crop((0, top, w, bottom))
        if trim_bottom:
            w, h = image.size
            image = image.crop((0, 0, w, max(1, h - int(h * 0.045))))
        image = ImageOps.fit(image, (width, height), method=PILImage.LANCZOS)
        path = os.path.join(get_astrbot_temp_path(), f"dafeiyu_image_{uuid.uuid4().hex}.jpg")
        image.save(path, "JPEG", quality=92, optimize=True)
        await event.send(MessageChain([Comp.Image.fromFileSystem(path)]))

    async def _cloudflare(self, event: AstrMessageEvent, prompt: str, width: int, height: int) -> bool:
        account, token = self._cf_credentials()
        if not account or not token:
            return False
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{CF_MODEL}"
        headers = {"Authorization": f"Bearer {token}"}
        body = {"prompt": self._prompt_with_style(prompt)[:2048], "steps": 8}
        try:
            timeout = aiohttp.ClientTimeout(total=150)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=body) as resp:
                    raw = await resp.read()
                    if resp.status != 200:
                        logger.warning("[dafeiyu_imagegen] Cloudflare HTTP %s: %s", resp.status, raw[:200])
                        return False
                    ctype = str(resp.headers.get("Content-Type") or "")
                    if ctype.startswith("image/"):
                        data = raw
                    else:
                        payload = json.loads(raw.decode("utf-8", "replace"))
                        result = payload.get("result") or {}
                        image_b64 = result.get("image") if isinstance(result, dict) else None
                        image_b64 = image_b64 or payload.get("image")
                        if not image_b64:
                            logger.warning("[dafeiyu_imagegen] Cloudflare response has no image")
                            return False
                        data = base64.b64decode(image_b64)
            if len(data) < 2000:
                return False
            await self._send_image(event, data, width, height, trim_bottom=False)
            logger.info("[dafeiyu_imagegen] generated %s bytes via Cloudflare", len(data))
            return True
        except Exception as exc:
            logger.warning("[dafeiyu_imagegen] Cloudflare failed: %s: %s", type(exc).__name__, exc)
            return False

    async def _pollinations(self, event: AstrMessageEvent, prompt: str, width: int, height: int) -> bool:
        encoded = quote(self._prompt_with_style(prompt), safe="")
        for model in ("flux", "turbo"):
            params = {
                "width": width,
                "height": height,
                "model": model,
                "nologo": "true",
                "enhance": "true",
                "seed": random.randint(1, 2_000_000_000),
            }
            url = f"https://image.pollinations.ai/prompt/{encoded}"
            try:
                timeout = aiohttp.ClientTimeout(total=150)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params) as resp:
                        data = await resp.read()
                        if resp.status == 200 and len(data) > 2000:
                            await self._send_image(event, data, width, height, trim_bottom=True)
                            logger.info("[dafeiyu_imagegen] generated %s bytes via Pollinations/%s", len(data), model)
                            return True
                        logger.warning("[dafeiyu_imagegen] Pollinations/%s HTTP %s", model, resp.status)
            except Exception as exc:
                logger.warning("[dafeiyu_imagegen] Pollinations/%s failed: %s", model, exc)
        return False

    async def _draw_and_send(self, event: AstrMessageEvent, prompt: str, aspect_ratio: str) -> None:
        width, height = self._sizes(aspect_ratio)
        if await self._cloudflare(event, prompt, width, height):
            return
        if await self._pollinations(event, prompt, width, height):
            return
        await event.send(MessageChain([Comp.Plain(text="这次图没画出来，晚点再试一次。")]))
