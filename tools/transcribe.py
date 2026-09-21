#!/usr/bin/env python3
"""Transcribe a video or audio file to text, SRT and JSON.

Runs fully offline: ffmpeg (from imageio-ffmpeg) decodes the media to 16 kHz
mono PCM, Silero VAD splits it into speech segments, and Whisper (via
sherpa-onnx) transcribes each segment.

    python3 tools/transcribe.py INPUT.mov --out-dir transcripts/

Models are expected under --models-dir (see tools/fetch_models.sh).
"""

import argparse
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx

SAMPLE_RATE = 16000


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def decode_to_wav(src: Path, dst: Path) -> None:
    """Decode any media file to 16 kHz mono 16-bit PCM."""
    cmd = [
        ffmpeg_exe(), "-nostdin", "-y", "-i", str(src),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-acodec", "pcm_s16le", "-f", "wav", str(dst),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == SAMPLE_RATE, w.getframerate()
        assert w.getnchannels() == 1, w.getnchannels()
        assert w.getsampwidth() == 2, w.getsampwidth()
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def build_vad(models_dir: Path, max_segment: float) -> sherpa_onnx.VoiceActivityDetector:
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(models_dir / "silero_vad.onnx")
    cfg.silero_vad.threshold = 0.5
    cfg.silero_vad.min_silence_duration = 0.35
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = max_segment
    cfg.sample_rate = SAMPLE_RATE
    return sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=120)


def build_recognizer(models_dir: Path, name: str, language: str, threads: int, int8: bool):
    model_dir = models_dir / f"sherpa-onnx-whisper-{name}"
    suffix = ".int8" if int8 else ""
    return sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(model_dir / f"{name}-encoder{suffix}.onnx"),
        decoder=str(model_dir / f"{name}-decoder{suffix}.onnx"),
        tokens=str(model_dir / f"{name}-tokens.txt"),
        language=language,
        task="transcribe",
        num_threads=threads,
    )


def segment(samples: np.ndarray, vad) -> list:
    """Yield (start_seconds, samples) speech chunks."""
    out, window = [], 512
    for i in range(0, len(samples), window):
        vad.accept_waveform(samples[i : i + window])
        while not vad.empty():
            out.append((vad.front.start / SAMPLE_RATE, vad.front.samples))
            vad.pop()
    vad.flush()
    while not vad.empty():
        out.append((vad.front.start / SAMPLE_RATE, vad.front.samples))
        vad.pop()
    return out


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help="video or audio file")
    p.add_argument("--out-dir", type=Path, default=Path("transcripts"))
    p.add_argument("--models-dir", type=Path,
                   default=Path(os.environ.get("ASR_MODELS_DIR", "models")))
    p.add_argument("--model", default="small", help="whisper model name, e.g. small, medium, turbo")
    p.add_argument("--language", default="", help="ISO code; empty = auto-detect")
    p.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    p.add_argument("--max-segment", type=float, default=25.0,
                   help="max seconds per speech chunk (whisper accepts 30)")
    p.add_argument("--fp32", action="store_true", help="use fp32 weights instead of int8")
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem
    wav = args.out_dir / f"{stem}.16k.wav"

    print(f"[1/3] decoding audio -> {wav}", flush=True)
    decode_to_wav(args.input, wav)
    samples = read_wav(wav)
    duration = len(samples) / SAMPLE_RATE
    print(f"      {duration/60:.1f} min of audio", flush=True)

    print("[2/3] detecting speech segments", flush=True)
    chunks = segment(samples, build_vad(args.models_dir, args.max_segment))
    speech = sum(len(c[1]) for c in chunks) / SAMPLE_RATE
    print(f"      {len(chunks)} segments, {speech/60:.1f} min of speech", flush=True)

    print(f"[3/3] transcribing with whisper-{args.model}", flush=True)
    rec = build_recognizer(args.models_dir, args.model, args.language,
                           args.threads, int8=not args.fp32)
    segments = []
    for i, (start, chunk) in enumerate(chunks, 1):
        s = rec.create_stream()
        s.accept_waveform(SAMPLE_RATE, chunk)
        rec.decode_stream(s)
        text = s.result.text.strip()
        if not text:
            continue
        segments.append({"index": len(segments) + 1, "start": start,
                         "end": start + len(chunk) / SAMPLE_RATE, "text": text})
        print(f"      [{i}/{len(chunks)}] {srt_time(start)} {text}", flush=True)

    txt = args.out_dir / f"{stem}.txt"
    srt = args.out_dir / f"{stem}.srt"
    jsn = args.out_dir / f"{stem}.json"
    txt.write_text("\n".join(s["text"] for s in segments) + "\n", encoding="utf-8")
    srt.write_text("".join(
        f"{s['index']}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n\n"
        for s in segments), encoding="utf-8")
    jsn.write_text(json.dumps({"source": str(args.input), "duration_seconds": duration,
                               "model": args.model, "segments": segments},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {txt}, {srt}, {jsn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
