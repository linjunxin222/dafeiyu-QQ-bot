"""Extract a small keyframe montage from a video for multimodal LLMs."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

_FFMPEG_FALLBACKS = (
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
)


def _find_ffmpeg() -> str | None:
    configured = os.environ.get("FFMPEG_PATH")
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in _FFMPEG_FALLBACKS:
        if Path(candidate).is_file():
            return candidate
    return None


async def _run_ffmpeg(ffmpeg: str, args: list[str], timeout: float = 30.0) -> bool:
    process = await asyncio.create_subprocess_exec(
        ffmpeg,
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        code = await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return False
    return code == 0


async def make_video_montage(video_path: str, max_frames: int = 6) -> str | None:
    """Return a JPEG montage of up to six chronological video frames."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None

    cache_root = Path(tempfile.gettempdir()) / "astrbot_video_frames"
    cache_root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 86400
    for old_montage in cache_root.glob("video_*.jpg"):
        try:
            if old_montage.stat().st_mtime < cutoff:
                old_montage.unlink(missing_ok=True)
        except OSError:
            pass
    work = cache_root / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=True)

    frame_pattern = str(work / "frame_%02d.jpg")
    args = [
        "-y",
        "-i",
        video_path,
        "-vf",
        "fps=1,scale=640:-2",
        "-frames:v",
        str(max_frames),
        "-q:v",
        "3",
        frame_pattern,
    ]
    ok = await _run_ffmpeg(ffmpeg, args)

    frames = sorted(work.glob("frame_*.jpg"))
    if not frames:
        # Very short clips can miss the one-second sampling interval.
        ok = await _run_ffmpeg(
            ffmpeg,
            [
                "-y",
                "-ss",
                "0",
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                "-q:v",
                "3",
                str(work / "frame_01.jpg"),
            ],
        )
        frames = sorted(work.glob("frame_*.jpg"))

    if not frames:
        shutil.rmtree(work, ignore_errors=True)
        return None

    try:
        from PIL import Image, ImageDraw

        images = []
        for frame in frames[:max_frames]:
            with Image.open(frame) as image:
                images.append(image.convert("RGB"))
        if not images:
            return None

        cell_w, cell_h = 320, 180
        cols = 3 if len(images) > 1 else 1
        rows = (len(images) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        for index, image in enumerate(images):
            image.thumbnail((cell_w, cell_h))
            x = (index % cols) * cell_w + (cell_w - image.width) // 2
            y = (index // cols) * cell_h + (cell_h - image.height) // 2
            canvas.paste(image, (x, y))
            draw.text(
                ((index % cols) * cell_w + 8, (index // cols) * cell_h + 6),
                str(index + 1),
                fill="red",
            )
        montage_path = cache_root / f"video_{uuid.uuid4().hex}.jpg"
        canvas.save(montage_path, "JPEG", quality=85)
        return str(montage_path)
    except Exception:
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
