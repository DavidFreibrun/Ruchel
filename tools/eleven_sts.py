#!/usr/bin/env python3
"""Convert Gemini VO takes into Maya's voice with ElevenLabs speech-to-speech.

    python3 tools/eleven_sts.py episodes/ep11-stockton s03 --env path/to/pipeline/.env
    python3 tools/eleven_sts.py episodes/ep11-stockton all --env ...

Gemini supplies the delivery (pacing, emphasis, emotion). Speech-to-speech keeps that
performance and swaps the timbre to Maya's ElevenLabs voice, so an episode voiced with
Gemini still sounds like the Maya of earlier episodes.

Reads EPISODE/vo/<part>.wav (from gemini_tts.py) and writes EPISODE/vo/maya/<part>.mp3.
Settings come from vo.config.json -> "sts". It only runs when "sts.enabled" is true.
The ElevenLabs key is read from ELEVENLABS_API_KEY, or from the .env passed with --env
(the variable name can be changed with --key-var). The output is not post-processed.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://api.elevenlabs.io/v1/speech-to-speech/{voice}?output_format={fmt}"


def api_key(env_file: str | None, var: str) -> str:
    if os.environ.get(var):
        return os.environ[var]
    if env_file:
        for ln in open(env_file, encoding="utf-8"):
            if ln.strip().startswith(var + "="):
                return ln.split("=", 1)[1].strip().strip("\"'")
    sys.exit(f"{var} not set (export it, or pass --env path/to/.env).")


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
    fields = {"model_id": sts["model_id"]}
    if sts.get("voice_settings"):
        fields["voice_settings"] = json.dumps(sts["voice_settings"])
    if sts.get("remove_background_noise") is not None:
        fields["remove_background_noise"] = str(sts["remove_background_noise"]).lower()
    body, ctype = multipart(fields, "audio", src)
    url = API.format(voice=sts["voice_id"], fmt=sts.get("output_format", "mp3_44100_192"))
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
        dst = out / f"{pid}.mp3"
        dst.write_bytes(convert(key, sts, src))
        manifest[pid] = {
            "source": f"vo/{src.name}", "file": f"vo/maya/{dst.name}",
            "voice_id": sts["voice_id"], "model_id": sts["model_id"],
            "voice_settings": sts.get("voice_settings"),
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"  -> vo/maya/{dst.name}", flush=True)


if __name__ == "__main__":
    main()
