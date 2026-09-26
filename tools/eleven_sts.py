#!/usr/bin/env python3
"""Convert Gemini VO takes into Maya's voice with ElevenLabs speech-to-speech.

    python3 tools/eleven_sts.py episodes/ep11-stockton s03 --env path/to/pipeline/.env
    python3 tools/eleven_sts.py episodes/ep11-stockton all --env ...

Gemini supplies the delivery (pacing, emphasis, emotion). Speech-to-speech keeps that
performance and swaps the timbre to Maya's ElevenLabs voice, so an episode voiced with
Gemini still sounds like the Maya of earlier episodes.

Reads EPISODE/vo/<part>.wav (from gemini_tts.py) and writes:
    EPISODE/vo/maya/<part>_raw.mp3   exactly what ElevenLabs returned
    EPISODE/vo/maya/<part>.wav       level-matched, mono 48 kHz PCM  <- this is what ships

Settings come from vo.config.json -> "sts". It only runs when "sts.enabled" is true.

Carried over from the Ep 7/8 voice_swap.py, not to be changed casually:
  * model + remove_background_noise ONLY, no voice_settings. Invented voice_settings caused the
    pitch artifact David rejected on 2026-08-13.
  * STS comes back ~4 LU quieter than TTS (Ep 8, measured). Level-match with GAIN ONLY to
    sts.target_lufs, plus a true-peak limiter at sts.ceiling_dbtp. Never compress: STS keeps a
    real performance (LRA 5-9), and compression ate that warmth on Ep 8.
  * Mono end to end, PCM intermediates. AAC is encoded once, at the final mux.

The ElevenLabs key is ELEVENLABS_API_KEY, read from the environment, then --env, then the
pipeline .env named by HPT_PIPELINE_ENV (on D:, since the Sept 2026 move off G:).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://api.elevenlabs.io/v1/speech-to-speech/{voice}?output_format={fmt}"
# Everything moved from G: (Google Drive) to D: in Sept 2026. Point this at the pipeline .env
# with the HPT_PIPELINE_ENV environment variable; nothing on G: is read any more.
PIPELINE_ENV = os.environ.get("HPT_PIPELINE_ENV", "")


def api_key(env_file: str | None, var: str) -> str:
    if os.environ.get(var):
        return os.environ[var]
    env_file = env_file or (PIPELINE_ENV if PIPELINE_ENV and os.path.exists(PIPELINE_ENV) else None)
    if env_file:
        for ln in open(env_file, encoding="utf-8"):
            if ln.strip().startswith(var + "="):
                return ln.split("=", 1)[1].strip().strip("\"'")
    sys.exit(f"{var} not set: export it, pass --env D:\\...\\heritage-pinoy-pipeline\\.env, "
             "or set HPT_PIPELINE_ENV to that file.")


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def loudness(path: Path) -> tuple[float, float, float]:
    """Integrated loudness, true peak and loudness range, from loudnorm's analysis pass."""
    r = subprocess.run(
        [ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    d = json.loads(re.findall(r"\{[^{}]*\}", r.stderr)[-1])
    return float(d["input_i"]), float(d["input_tp"]), float(d["input_lra"])


def level_match(src: Path, dst: Path, target: float, ceiling_db: float) -> dict:
    """Gain only to `target` LUFS plus a true-peak safety limiter. No compression."""
    i0, tp0, lra0 = loudness(src)
    gain = target - i0
    ceil = 10 ** (ceiling_db / 20.0)
    subprocess.run(
        [ffmpeg(), "-v", "error", "-nostdin", "-y", "-i", str(src), "-af",
         f"volume={gain:.2f}dB,alimiter=limit={ceil:.4f}:level=disabled,aresample=48000",
         "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )
    i1, tp1, lra1 = loudness(dst)
    print(f"  level {i0:.2f} LUFS / LRA {lra0:.1f} -> gain {gain:+.2f} dB -> {i1:.2f} LUFS / {tp1:.2f} dBTP / LRA {lra1:.1f}")
    if abs(i1 - target) > 1.0:
        print(f"  ** WARNING: landed {i1 - target:+.2f} LU off target, check the limiter **")
    return {"in_lufs": i0, "gain_db": round(gain, 2), "out_lufs": i1, "out_dbtp": tp1, "lra_in": lra0, "lra_out": lra1}


def multipart(fields: dict, file_field: str, path: Path) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    out.append(
        f'--{b}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
        "Content-Type: audio/wav\r\n\r\n".encode()
    )
    out.append(path.read_bytes())
    out.append(f"\r\n--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


def convert(key: str, sts: dict, src: Path) -> bytes:
    if sts.get("voice_settings"):
        sys.exit("sts.voice_settings must stay unset: it caused the 2026-08-13 pitch artifact.")
    fields = {"model_id": sts["model_id"]}
    if sts.get("remove_background_noise") is not None:
        fields["remove_background_noise"] = str(sts["remove_background_noise"]).lower()
    body, ctype = multipart(fields, "audio", src)
    url = API.format(voice=sts["voice_id"], fmt=sts.get("output_format", "mp3_44100_128"))
    req = urllib.request.Request(url, data=body, headers={"xi-api-key": key, "Content-Type": ctype})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 4:
                wait = 2 ** (attempt + 1)
                print(f"  HTTP {e.code}, retrying in {wait}s", flush=True)
                time.sleep(wait)
                continue
            sys.exit(f"ElevenLabs error {e.code}: {e.read().decode(errors='replace')[:800]}")
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", type=Path)
    ap.add_argument("part", help="part id (s03) or 'all'")
    ap.add_argument("--env", help=".env file holding the ElevenLabs key")
    ap.add_argument("--key-var", default="ELEVENLABS_API_KEY")
    args = ap.parse_args()

    ep = args.episode
    cfg = json.loads((ep / "vo.config.json").read_text(encoding="utf-8"))
    sts = cfg.get("sts") or {}
    if not sts.get("enabled"):
        sys.exit("vo.config.json sts.enabled is not true for this episode.")

    vo = ep / "vo"
    srcs = sorted(vo.glob("s[0-9][0-9].wav")) if args.part == "all" else [vo / f"{args.part}.wav"]
    srcs = [s for s in srcs if s.exists()]
    if not srcs:
        sys.exit(f"No Gemini takes found for {args.part!r} in {vo}. Run gemini_tts.py first.")

    key = api_key(args.env, args.key_var)
    out = vo / "maya"
    out.mkdir(exist_ok=True)
    man_path = out / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}

    for src in srcs:
        pid = src.stem
        print(f"{pid} -> Maya ...", flush=True)
        raw = out / f"{pid}_raw.mp3"
        raw.write_bytes(convert(key, sts, src))
        dst = out / f"{pid}.wav"
        level = level_match(raw, dst, sts.get("target_lufs", -18.4), sts.get("ceiling_dbtp", -1.5))
        manifest[pid] = {
            "source": f"vo/{src.name}", "raw": f"vo/maya/{raw.name}", "file": f"vo/maya/{dst.name}",
            "voice_id": sts["voice_id"], "model_id": sts["model_id"],
            "remove_background_noise": sts.get("remove_background_noise"), "level": level,
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"  -> vo/maya/{dst.name}", flush=True)


if __name__ == "__main__":
    main()
