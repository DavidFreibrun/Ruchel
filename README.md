# Video transcription

Offline speech-to-text for video and audio files. Decodes with ffmpeg, splits
speech with Silero VAD, transcribes with Whisper via
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). No API keys, no network
access at transcription time.

## Setup

```bash
pip install -r requirements.txt
./tools/fetch_models.sh small      # or: medium, turbo, tiny.en, small.en ...
```

`fetch_models.sh` pulls the Whisper and VAD models from sherpa-onnx's GitHub
release assets into `models/`.

## Use

```bash
python3 tools/transcribe.py "Museu of Make Believe.MOV" --out-dir transcripts/
```

Writes three files per input, named after the source:

| File | Contents |
| --- | --- |
| `NAME.txt` | plain transcript, one line per speech segment |
| `NAME.srt` | subtitles with timestamps |
| `NAME.json` | segments with `start`/`end` seconds, plus source metadata |

Useful flags:

- `--model medium` / `--model turbo` — more accurate, slower. `turbo`
  (large-v3-turbo) is the best quality that still runs at a sane speed on CPU.
- `--language pt` — skip auto-detection and force a language (ISO code). The
  multilingual models (`small`, `medium`, `turbo`) auto-detect by default; the
  `.en` models are English-only and faster.
- `--fp32` — full-precision weights instead of int8. Marginally more accurate,
  roughly 2x slower.
- `--threads N` — defaults to the CPU count.

## Notes

- Any format ffmpeg can read works — `.MOV`, `.mp4`, `.mkv`, `.m4a`, `.wav`.
- Video is never decoded; only the audio track is touched, so file size matters
  far less than duration.
- Silence is skipped by the VAD, so runtime tracks speech time, not wall time.
- Speed, measured on 4 CPU cores with `small` int8: 199 s of continuous speech
  transcribed in 133 s, i.e. about 1.5x faster than realtime. A one-hour
  recording takes roughly 40 minutes of that, less when there are pauses.
