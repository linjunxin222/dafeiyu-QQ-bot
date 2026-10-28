#!/usr/bin/env python3
"""Repository hygiene checks for the public sanitized repo.

Run from the repository root:
    python tools/check_repo.py
"""

from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_NAMES = {
    "图片API.txt",
    "后台.txt",
    "大号QQ.txt",
    "豆包语音.txt",
    "deepseek-key.txt",
    "回答.json",
}
FORBIDDEN_SUFFIXES = (
    ".log",
    ".wav",
    ".mp3",
    ".flac",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
)
FORBIDDEN_DIRS = {"logs", "语音试听", "__pycache__", "AstrBot", "NapCat", "Ollama"}

SECRET_PATTERNS = {
    "Cloudflare token": re.compile(r"cfut_[A-Za-z0-9_-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "Bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    "Cloudflare account_id": re.compile(r"account_id\s*=\s*[0-9a-fA-F]{20,}"),
    "Cloudflare api_token": re.compile(r"api_token\s*=\s*[A-Za-z0-9_-]{20,}"),
}


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / part.decode("utf-8") for part in raw.split(b"\0") if part]


def main() -> int:
    errors: list[str] = []
    files = tracked_files()
    if not files:
        errors.append("git ls-files returned no files")
        files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]

    python_files = 0
    json_files = 0
    for path in files:
        rel = path.relative_to(ROOT)
        parts = set(rel.parts)
        if rel.name in FORBIDDEN_NAMES or parts & FORBIDDEN_DIRS:
            errors.append(f"forbidden runtime/secret path is tracked: {rel}")
            continue
        if any(rel.name.lower().endswith(s) for s in FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden binary/runtime file is tracked: {rel}")
            continue
        if rel.name.startswith("cloudflare-") and rel.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            errors.append(f"generated image is tracked: {rel}")
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if rel.as_posix() != "tools/check_repo.py":
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"possible {label} in {rel}")

        if path.suffix == ".py":
            python_files += 1
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(f"Python syntax error in {rel}: {exc.msg}")
        elif path.suffix == ".json":
            json_files += 1
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {rel}: {exc}")

    for path in files:
        if path.name == "metadata.yaml":
            text = path.read_text(encoding="utf-8")
            if "name:" not in text or "version:" not in text:
                errors.append(f"plugin metadata missing name/version: {path.relative_to(ROOT)}")

    if errors:
        print("Repository checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Repository checks passed: {len(files)} tracked files, {python_files} Python files, {json_files} JSON files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
