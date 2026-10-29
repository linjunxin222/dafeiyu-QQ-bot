"""Minimal ComfyUI API client for NoobAI-XL SDXL generation."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import requests

COMFY = "http://127.0.0.1:8188"
CKPT = "NoobAI-XL-v1.1.safetensors"


def workflow(prompt: str, negative: str, width: int, height: int, seed: int, steps: int, cfg: float):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "dafeiyu_comfy", "images": ["6", 0]}},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative", default="lowres, bad anatomy, bad hands, extra fingers, text, watermark, logo, blurry, jpeg artifacts")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=28)
    parser.add_argument("--cfg", type=float, default=5.5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    seed = args.seed or int(time.time() * 1000) % 2_000_000_000
    client_id = uuid.uuid4().hex
    body = {"prompt": workflow(args.prompt, args.negative, args.width, args.height, seed, args.steps, args.cfg), "client_id": client_id}
    r = requests.post(f"{COMFY}/prompt", json=body, timeout=30)
    r.raise_for_status()
    prompt_id = r.json().get("prompt_id")
    if not prompt_id:
        raise SystemExit(f"ComfyUI did not return prompt_id: {r.text[:500]}")

    deadline = time.time() + 300
    image = None
    while time.time() < deadline:
        time.sleep(2)
        h = requests.get(f"{COMFY}/history/{prompt_id}", timeout=30).json()
        item = h.get(prompt_id)
        if not item:
            continue
        outputs = item.get("outputs") or {}
        for node in outputs.values():
            for img in node.get("images", []) or []:
                if img.get("type") == "output":
                    image = img
                    break
            if image:
                break
        if image:
            break
        status = item.get("status") or {}
        if status.get("status_str") == "error":
            raise SystemExit(f"ComfyUI error: {json.dumps(status)[:1000]}")
    if not image:
        raise SystemExit("ComfyUI generation timed out")

    params = {
        "filename": image.get("filename"),
        "subfolder": image.get("subfolder", ""),
        "type": image.get("type", "output"),
    }
    r = requests.get(f"{COMFY}/view", params=params, timeout=60)
    r.raise_for_status()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    print(f"OK out={out} bytes={out.stat().st_size} seed={seed}")


if __name__ == "__main__":
    main()
