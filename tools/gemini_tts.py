#!/usr/bin/env python3
"""Generate an HPT episode's narration VO with Gemini TTS, straight from its script.md.

    python3 tools/gemini_tts.py episodes/ep11-stockton --list        show the parts, no API calls
    python3 tools/gemini_tts.py episodes/ep11-stockton s03           generate one part
    python3 tools/gemini_tts.py episodes/ep11-stockton all           generate every part

Settings come from EPISODE/vo.config.json. The script refuses to run unless that file says
"engine": "gemini" -- the engine is David's call per episode (see .claude/skills/hpt-voiceover).

A PART is one `[SECTION]` marker and the paragraphs under it. Markers are never spoken.
Sections listed in "skip_sections" (matched by prefix) are left out, e.g. an undecided teaser.

Output: EPISODE/vo/<part>.wav (16-bit mono PCM at the rate Gemini returns, 24 kHz) and
EPISODE/vo/manifest.json recording the exact model, voice, prompt and text of every take.
Nothing is post-processed: what Gemini returns is what ships.

The API key is read from GEMINI_API_KEY, or from a .env file passed with --env.
Only the standard library is used, so it runs anywhere `python3` does.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_RATE = 24000
MARKER = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$")


def load_config(ep: Path) -> dict:
    path = ep / "vo.config.json"
    if not path.exists():
        sys.exit(f"{path} is missing. Create it and have David pick the engine first.")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    engine = cfg.get("engine")
    if engine != "gemini":
        sys.exit(
            f"vo.config.json says engine={engine!r}. This tool only runs for \"gemini\".\n"
            "The engine is David's decision per episode -- ask him, record it, then re-run."
        )
    g = cfg.get("gemini") or {}
    missing = [k for k in ("model", "voice") if not g.get(k)]
    if missing:
        sys.exit(f"vo.config.json gemini.{', gemini.'.join(missing)} not set yet.")
    return cfg


def parts(script: Path, skip: list[str]) -> list[tuple[str, str, str]]:
    """[(part_id, section_name, text)] in script order. Text keeps its paragraph breaks."""
    out, name, buf = [], None, []

    def flush():
        if name is None:
            return
        text = "\n\n".join(p for p in "\n".join(buf).split("\n\n") if p.strip()).strip()
        if text and not any(name.upper().startswith(s.upper()) for s in skip):
            out.append((f"s{len(out) + 1:02d}", name, text))

    started = False
    for line in script.read_text(encoding="utf-8").splitlines():
        m = MARKER.match(line.strip())
        if m:
            flush()
            name, buf, started = m["name"], [], True
        elif started:
            buf.append(line.strip())
    flush()
    return out


def api_key(env_file: str | None) -> str:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if env_file:
        for ln in open(env_file, encoding="utf-8"):
            if ln.strip().startswith("GEMINI_API_KEY="):
                return ln.split("=", 1)[1].strip().strip("\"'")
    sys.exit("GEMINI_API_KEY not set (export it, or pass --env path/to/.env).")


def synthesize(key: str, g: dict, text: str) -> tuple[bytes, int]:
    prompt = f"{g['style_prompt'].strip()}\n\n{text}" if g.get("style_prompt") else text
    speech = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": g["voice"]}}}
    if g.get("language_code"):
        speech["languageCode"] = g["language_code"]
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": speech},
    }
    if g.get("temperature") is not None:
        body["generationConfig"]["temperature"] = g["temperature"]
    req = urllib.request.Request(
        API.format(model=g["model"]),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 4:
                wait = 2 ** (attempt + 1)
                print(f"  HTTP {e.code}, retrying in {wait}s", flush=True)
                time.sleep(wait)
                continue
            sys.exit(f"Gemini API error {e.code}: {e.read().decode(errors='replace')[:800]}")
    inline = resp["candidates"][0]["content"]["parts"][0]["inlineData"]
    rate = DEFAULT_RATE
    m = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
    if m:
        rate = int(m.group(1))
    return base64.b64decode(inline["data"]), rate


def write_wav(path: Path, pcm: bytes, rate: int) -> float:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return len(pcm) / 2 / rate


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", type=Path, help="episode folder containing script.md and vo.config.json")
    ap.add_argument("part", nargs="?", help="part id (s03) or 'all'")
    ap.add_argument("--list", action="store_true", help="list the parts and exit, no API calls")
    ap.add_argument("--env", help=".env file holding GEMINI_API_KEY")
    args = ap.parse_args()

    ep = args.episode
    raw = json.loads((ep / "vo.config.json").read_text(encoding="utf-8")) if (ep / "vo.config.json").exists() else {}
    items = parts(ep / "script.md", raw.get("skip_sections", []))

    if args.list or not args.part:
        total = 0
        for pid, name, text in items:
            n = len(text.split())
            total += n
            print(f"{pid}  {n:5d} words  {name}")
        print(f"      {total:5d} words total")
        return

    cfg = load_config(ep)
    g = cfg["gemini"]
    todo = items if args.part == "all" else [p for p in items if p[0] == args.part]
    if not todo:
        sys.exit(f"No part {args.part!r}. Use --list to see them.")

    key = api_key(args.env)
    out = ep / "vo"
    out.mkdir(exist_ok=True)
    man_path = out / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}

    for pid, name, text in todo:
        print(f"{pid}  {name} ({len(text.split())} words) ...", flush=True)
        pcm, rate = synthesize(key, g, text)
        dur = write_wav(out / f"{pid}.wav", pcm, rate)
        manifest[pid] = {
            "section": name, "file": f"{pid}.wav", "seconds": round(dur, 2),
            "engine": "gemini", "model": g["model"], "voice": g["voice"],
            "style_prompt": g.get("style_prompt"), "language_code": g.get("language_code"),
            "text": text, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  -> vo/{pid}.wav  {dur:.1f}s", flush=True)


if __name__ == "__main__":
    main()
