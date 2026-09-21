# Video transcription

Offline speech-to-text for video and audio files. Decodes with ffmpeg, splits
speech with Silero VAD, transcribes with Whisper via
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). No API keys, no network
access at transcription time.

## Quick start

```bash
git clone https://github.com/DavidFreibrun/Ruchel.git
cd Ruchel
pip3 install -r requirements.txt
./tools/fetch_models.sh small          # ~1.3 GB, from GitHub release assets

python3 tools/transcribe.py "Museu of Make Believe.MOV"
```

That writes `transcripts/Museu of Make Believe.{txt,srt,json}`. Nothing leaves
your machine and no API key is involved — ffmpeg ships inside the
`imageio-ffmpeg` wheel, so there is nothing else to install.

Progress prints as it goes, one line per speech segment, so you can read the
transcript forming and stop early if the language or model choice looks wrong.

## Options

| Flag | Effect |
| --- | --- |
| `--model medium` / `--model turbo` | more accurate, slower; `turbo` (large-v3-turbo) is the best quality that still runs sanely on CPU. Fetch it first: `./tools/fetch_models.sh turbo` |
| `--language pt` | force a language (ISO code) instead of auto-detecting |
| `--fp32` | full-precision weights; marginally better, roughly 2x slower |
| `--threads N` | defaults to the CPU count |
| `--keep-wav` | keep the decoded 16 kHz wav so re-runs skip decoding |

The multilingual models (`small`, `medium`, `turbo`) auto-detect language per
segment. The `.en` variants are English-only and faster.

## Output

| File | Contents |
| --- | --- |
| `NAME.txt` | plain transcript, one line per speech segment |
| `NAME.srt` | subtitles with timestamps |
| `NAME.json` | segments with `start`/`end` seconds, plus source metadata |

## Notes

- Any format ffmpeg can read works — `.MOV`, `.mp4`, `.mkv`, `.m4a`, `.wav`.
- If a model is missing the script says which one and how to fetch it, rather
  than failing inside onnxruntime.
- Video is never decoded; only the audio track is touched, so file size matters
  far less than duration.
- Silence is skipped by the VAD, so runtime tracks speech time, not wall time.
- Speed, measured on 4 CPU cores with `small` int8: 199 s of continuous speech
  transcribed in 133 s, i.e. about 1.5x faster than realtime. A one-hour
  recording takes roughly 40 minutes of that, less when there are pauses.
