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
RVC_ROOT = Path(r"D:\大肥鱼\Applio")
RVC_ENV = RVC_ROOT / "env" / "Scripts" / "python.exe"
RVC_INFER = RVC_ROOT / "rvc" / "infer" / "infer.py"
RVC_MODEL_DIR = Path(r"D:\rvc-model")
RVC_PTH = RVC_MODEL_DIR / "dafeiyu.pth"
DEFAULT_OUT = Path(r"D:\dafeiyu\sing\out\cover-last.wav")
DEFAULT_MAX_SECONDS = 60.0


def f0_for(path: Path, out_npy: Path, max_seconds: float = DEFAULT_MAX_SECONDS):
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


def to_wav(source: Path, target: Path, max_seconds: float = DEFAULT_MAX_SECONDS):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-t",
        str(max_seconds),
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


def rvc_convert(source_wav: Path, out_wav: Path) -> None:
    """Convert a dry vocal with the trained dafeiyu RVC model."""
    if not RVC_PTH.exists():
        raise RuntimeError(f"RVC 模型不存在: {RVC_PTH}")
    if not RVC_ENV.exists() or not RVC_INFER.exists():
        raise RuntimeError("Applio RVC 环境不完整")
    indices = sorted(RVC_MODEL_DIR.glob("*.index"))
    index = str(indices[-1]) if indices else ""
    cmd = [
        str(RVC_ENV),
        str(RVC_INFER),
        "--input-path", str(source_wav),
        "--output-path", str(out_wav),
        "--pth-path", str(RVC_PTH),
        "--index-path", index,
        "--f0-method", "rmvpe",
        "--index-rate", "0.75",
        "--protect", "0.5",
        "--resample-sr", "40000",
        "--export-format", "WAV",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(RVC_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if proc.returncode != 0 or not out_wav.exists():
        raise RuntimeError(f"RVC 转换失败: {(proc.stderr or proc.stdout or '')[-800:]}")
    print(f"OK RVC converted {source_wav.name} -> {out_wav.name}")


def separate_vocals(mix_wav: Path, vocal_wav: Path, inst_wav: Path):
    """Extract lead vocals and accompaniment; frees the separator before SVC loads."""
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
        vocal_source = getattr(result, "vocals_dereverbed", None)
        if vocal_source is None or getattr(vocal_source, "size", 0) == 0:
            vocal_source = result.vocals
        for array, dest in (
            (vocal_source, vocal_wav),
            (result.accompaniment, inst_wav),
        ):
            if getattr(array, "ndim", 0) == 2:
                array = array.T
            sf.write(str(dest), array, result.sample_rate)
    finally:
        del separator
        gc.collect()
        torch.cuda.empty_cache()
    if not vocal_wav.exists():
        raise RuntimeError("人声分离没有输出")
    if not inst_wav.exists():
        raise RuntimeError("伴奏分离没有输出")
    return result.sample_rate


def _ffmpeg(inputs: list[str], filter_complex: str, out: Path):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-y"]
    for item in inputs:
        cmd += ["-i", item]
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"混音/后处理失败: {(proc.stderr or '')[-700:]}")


def master_vocal(vocal_wav: Path, out: Path):
    """EQ + compression + light space + loudness for a dry SVC vocal."""
    flt = (
        "[0:a]aresample=44100,highpass=f=70,"
        "acompressor=threshold=-20dB:ratio=2.5:attack=12:release=180,"
        "equalizer=f=2500:t=q:w=1.2:g=1,"
        "equalizer=f=6500:t=q:w=1.2:g=1,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    )
    _ffmpeg([str(vocal_wav)], flt, out)


def mix_with_inst(vocal_wav: Path, inst_wav: Path, out: Path):
    """Blend the SVC vocal with the original accompaniment, then master."""
    flt = (
        "[0:a]aresample=44100,highpass=f=70,"
        "acompressor=threshold=-20dB:ratio=2.5:attack=12:release=180,"
        "equalizer=f=2500:t=q:w=1.2:g=1,"
        "equalizer=f=6500:t=q:w=1.2:g=1[voice];"
        "[1:a]aresample=44100,highpass=f=35,volume=0.42[inst];"
        "[voice][inst]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    )
    _ffmpeg([str(vocal_wav), str(inst_wav)], flt, out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--n-steps", type=int, default=24)
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    parser.add_argument("--auto-shift", action="store_true", help="自动移到 prompt 音域；默认保持原调")
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
        vocal_wav = td / "vocal.wav"
        inst_wav = td / "inst.wav"
        has_inst = False
        to_wav(target, raw_wav, args.max_seconds)

        if not args.no_separate:
            try:
                separate_vocals(raw_wav, vocal_wav, inst_wav)
                to_wav(vocal_wav, target_wav, args.max_seconds)
                has_inst = True
                print("OK separated vocal + accompaniment")
            except Exception as exc:
                print(f"WARN 人声分离失败，改用原音轨: {exc}")
                shutil.copy2(raw_wav, target_wav)
        else:
            shutil.copy2(raw_wav, target_wav)

        if RVC_PTH.exists():
            generated = td / "generated.wav"
            rvc_convert(target_wav, generated)
            frames = None
        else:
            frames = f0_for(target_wav, target_f0, args.max_seconds)
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
                auto_shift=bool(args.auto_shift),
                pitch_shift=0,
                n_steps=max(8, int(args.n_steps)),
                cfg=3.0,
                use_fp16=True,
            )
            process(run_args, config, model)
            generated = save_dir / "generated.wav"
            if not generated.exists():
                raise SystemExit("SVC 没有生成音频")

        if has_inst:
            # RVC/SVC 都跟原唱的音高；保持原调后直接和原伴奏混音。
            mix_with_inst(generated, inst_wav, out)
            print("OK mixed converted vocal with original accompaniment")
        else:
            master_vocal(generated, out)
            print("OK mastered converted vocal (no accompaniment)")
        print(f"OK out={out} target_frames={frames} bytes={out.stat().st_size}")


if __name__ == "__main__":
    main()
