"""用 SoulX-Singer-SVC 把一段目标人声转换成大肥鱼音色。

只做本地推理；输入应当是干净人声/清唱，整首歌带伴奏会抓错音高。
"""

from __future__ import annotations

import argparse
import gc
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import librosa
import numpy as np
import soundfile as sf
import torch

ROOT = Path(r"D:\dafeiyu\sing\SoulX-Singer")
MODEL = Path(r"D:\dafeiyu\sing\models\SoulX-Singer\model-svc.pt")
PROMPT_WAV = Path(r"D:\dafeiyu\sing\out\1029-175115-1f43fa.wav")
PROMPT_F0 = Path(r"D:\dafeiyu\sing\voice\dafeiyu_song_f0.npy")
SEP_MODEL = Path(
    r"D:\dafeiyu\sing\models\SoulX-Singer-Preprocess\mel-band-roformer-karaoke"
    r"\mel_band_roformer_karaoke_becruily.ckpt"
)
SEP_CONFIG = Path(
    r"D:\dafeiyu\sing\models\SoulX-Singer-Preprocess\mel-band-roformer-karaoke"
    r"\config_karaoke_becruily.yaml"
)
DEFAULT_OUT = Path(r"D:\dafeiyu\sing\out\cover-last.wav")


def f0_for(path: Path, out_npy: Path, max_seconds: float = 30.0):
    y, sr = librosa.load(str(path), sr=24000, mono=True, duration=max_seconds)
    if len(y) == 0:
        raise RuntimeError("目标音频为空")
    f0, _, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=24000,
        frame_length=1920,
        hop_length=480,
    )
    f0 = np.nan_to_num(f0, nan=0.0).astype(np.float32)
    np.save(out_npy, f0)
    return f0.shape


def to_wav(source: Path, target: Path):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-t",
        "30",
        "-ar",
        "24000",
        "-ac",
        "1",
        "-f",
        "wav",
        str(target),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not target.exists():
        raise RuntimeError(f"音频转码失败: {(proc.stderr or '')[-500:]}")


def separate_vocals(mix_wav: Path, vocal_wav: Path):
    """Extract lead vocals from a full mix; frees the separator before SVC loads."""
    if not SEP_MODEL.exists() or not SEP_CONFIG.exists():
        raise RuntimeError("人声分离模型不存在")
    sys.path.insert(0, str(ROOT))
    from preprocess.tools.vocal_separation.model import VocalSeparator

    separator = VocalSeparator(
        sep_model_path=str(SEP_MODEL),
        sep_config_path=str(SEP_CONFIG),
        der_model_path=str(SEP_MODEL),
        der_config_path=str(SEP_CONFIG),
        use_der=False,
        device="cuda",
        chunk_length_sec=5,
        verbose=False,
    )
    try:
        result = separator.process(str(mix_wav))
        vocals = result.vocals
        if getattr(vocals, "ndim", 0) == 2:
            vocals = vocals.T
        sf.write(str(vocal_wav), vocals, result.sample_rate)
    finally:
        del separator
        gc.collect()
        torch.cuda.empty_cache()
    if not vocal_wav.exists():
        raise RuntimeError("人声分离没有输出")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--n-steps", type=int, default=16)
    parser.add_argument("--no-separate", action="store_true", help="目标已经是干净人声时跳过分离")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        raise SystemExit(f"目标音频不存在: {target}")
    if not MODEL.exists():
        raise SystemExit(f"SVC 模型不存在: {MODEL}")
    if not PROMPT_WAV.exists():
        raise SystemExit(f"音色 prompt 不存在: {PROMPT_WAV}")

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    sys.path.insert(0, str(ROOT))

    from cli.inference_svc import build_model, process
    from soulxsinger.utils.file_utils import load_config

    with tempfile.TemporaryDirectory(prefix="svc_") as td:
        td = Path(td)
        raw_wav = td / "raw.wav"
        target_wav = td / "target.wav"
        target_f0 = td / "target_f0.npy"
        save_dir = td / "save"
        to_wav(target, raw_wav)

        if not args.no_separate:
            try:
                vocal_wav = td / "vocal.wav"
                separate_vocals(raw_wav, vocal_wav)
                to_wav(vocal_wav, target_wav)
            except Exception as exc:
                print(f"WARN 人声分离失败，改用原音轨: {exc}")
                shutil.copy2(raw_wav, target_wav)
        else:
            shutil.copy2(raw_wav, target_wav)

        frames = f0_for(target_wav, target_f0)
        prompt_f0 = PROMPT_F0
        if not prompt_f0.exists():
            prompt_f0 = td / "prompt_f0.npy"
            f0_for(PROMPT_WAV, prompt_f0)

        config = load_config(str(ROOT / "soulxsinger" / "config" / "soulxsinger.yaml"))
        model = build_model(
            model_path=str(MODEL),
            config=config,
            device="cuda",
            use_fp16=True,
        )
        run_args = SimpleNamespace(
            device="cuda",
            model_path=str(MODEL),
            config=str(ROOT / "soulxsinger" / "config" / "soulxsinger.yaml"),
            prompt_wav_path=str(PROMPT_WAV),
            target_wav_path=str(target_wav),
            prompt_f0_path=str(prompt_f0),
            target_f0_path=str(target_f0),
            save_dir=str(save_dir),
            auto_shift=True,
            pitch_shift=0,
            n_steps=max(8, int(args.n_steps)),
            cfg=3.0,
            use_fp16=True,
        )
        process(run_args, config, model)
        generated = save_dir / "generated.wav"
        if not generated.exists():
            raise SystemExit("SVC 没有生成音频")
        shutil.copy2(generated, out)
        print(f"OK out={out} target_frames={frames} bytes={out.stat().st_size}")


if __name__ == "__main__":
    main()
