---
name: hpt-voiceover
description: Generate Maya's narration VO for a Heritage Pinoy Talks (HPT) episode. Starts with a hard gate, where David picks Gemini TTS or ElevenLabs for that episode, then follows the chosen engine's method. Use whenever an HPT episode needs voiceover, a re-take, or a pronunciation fix.
---

# HPT voiceover

> **Paths: everything is on the D: drive.** G: (Google Drive for desktop) is retired. Old Ep 7–10 scripts on Drive still say `G:\My Drive\...`; never copy those paths.
>
> - HPT root: `D:\Freibrun Enterprises\Heritage Pinoy Talks` (David, 2026-09-26)
> - Pipeline `.env` (`ELEVENLABS_API_KEY`): `D:\Freibrun Enterprises\Heritage Pinoy Talks\heritage-pinoy-pipeline\.env`. This is assumed to keep the old layout; override it with `HPT_PIPELINE_ENV` if it moved.
> - This repo: `D:\Freibrun Enterprises\Heritage Pinoy Talks\Ruchel`, with episodes under `Ruchel\episodes\epNN-slug\`.

## Gate: which engine? (do this first, every episode)

1. Open `episodes/epNN-*/vo.config.json`. If it doesn't exist, copy it from the latest episode and reset `engine`, `decided_by` and `decided_on` to `null`.
2. **If `engine` is `null`, stop and ask David:** "Episode NN VO: Gemini TTS or ElevenLabs?" Don't pick a default, don't infer one from the last episode, and don't generate a test take first.
3. Record his answer in `engine` (`"gemini"` or `"elevenlabs"`), with `decided_by: "David"` and `decided_on` set to today's date. Commit it.
4. **One engine per episode.** Maya's timbre differs between engines, so never mix them inside an episode. The only exception is David explicitly approving a mix for specific parts; write that approval into the config next to the parts it covers.
5. Only then go to the matching section below.

`tools/gemini_tts.py` enforces this gate too: it exits unless `engine` is `"gemini"` and `gemini.model` and `gemini.voice` are both set.

## Rules for both engines

- **Generate from the script, never retype it.** The text comes from `script.md`, where `[SECTION]` markers split it into parts and are never spoken.
- **Skip undecided text.** Sections listed in `skip_sections` (e.g. `NEXT TIME` while the teaser is TBD) are not voiced.
- **Ship verbatim.** No pacing edits, gap surgery or trimming. That is David's standing ruling from Ep 8: "just accept the speech as it is given to you."
- **Check every take before David hears it:**
  - Transcribe it back with `python3 tools/transcribe.py vo/sNN.wav --out-dir vo/check` and compare it to the part text. The words must match, with numbers normalised.
  - Grep the transcript for words from the style prompt or tags. Any prompt text that got spoken aloud fails the take.
  - Write a listen checklist of every Filipino or Spanish name, with timestamps. A transcript can't hear a mispronunciation, so David has to listen.
- **Respelling policy:** generate with plain spelling first. Respell only words the check shows were misheard. Over-respelling is what turned "Maya" into "Em Aya" on Ep 8.
- **Log every call to the cost ledger:** model, characters, cost.

## Engine: ElevenLabs (the Ep 8–10 standing method)

- Model: `eleven_multilingual_v2`. `eleven_v3` is **rejected** for Maya because of her timbre.
- Voice: Maya, `TcZDZdbOYm8HPLDiDkn0`.
- Settings: stability 0.30, similarity 0.82, style 0.50, speaker boost on.
- Set `previous_text` / `next_text` to the real neighbouring spoken lines.
- Use `/with-timestamps` so block timing comes from the take's own word times.
- On-camera blocks: Veo native audio, then ElevenLabs speech-to-speech into the same voice ID. TTS and speech-to-speech run about 4 LU apart, so level-match per block.
- The generators live in the `heritage-pinoy-pipeline` folder on D: (e.g. Ep 9's `gen_sections_vo.py`).

## Engine: Gemini TTS (then converted to Maya)

David's ruling (2026-09-26, Ep 11): **Gemini performs, ElevenLabs converts it into Maya's voice.** Gemini gives the delivery. Speech-to-speech into `TcZDZdbOYm8HPLDiDkn0` keeps Maya sounding the same as Ep 6–10. Both steps are required. A raw Gemini take never ships.

```bash
EP=episodes/epNN-slug
# GEMINI_API_KEY is an environment variable on David's PC; nothing to pass.
# ELEVENLABS_API_KEY is read from D:\Freibrun Enterprises\Heritage Pinoy Talks\heritage-pinoy-pipeline\.env

python3 tools/gemini_tts.py $EP --list             # parts and word counts, free
python3 tools/gemini_tts.py $EP --models           # confirm the model id exists
python3 tools/gemini_tts.py $EP --audition s01     # one take per audition voice
#   David picks a voice by ear, then write it into gemini.voice
python3 tools/gemini_tts.py $EP all                # vo/sNN.wav   (Gemini delivery)
python3 tools/eleven_sts.py $EP all                # vo/maya/sNN.wav  <- these ship
```

- **Settings** come from `vo.config.json`: `gemini` holds `model`, `voice`, `audition_voices`, `style_prompt`, `language_code` and `temperature`; `sts` holds the conversion settings. The tools refuse to guess: `voice` stays `null` until David has picked one.
- **Voice audition:** do it once per new setup, on the cold open. Judge each take on its delivery, since the timbre gets replaced later. If David wants to hear the takes as Maya, run each audition file through STS before he listens.
- **Style prompt:** it is sent in front of the text, so it can leak into the audio. The transcript grep is mandatory. Run it on the **converted** file, because that is what ships.
- **Model:** `gemini-3.8-flash-tts` was the newest model at setup (announced 2026-09-23). Confirm it with `--models` on the first run; if the ID differs, fix the config rather than the code.
- **Timing is per section.** David ruled on 2026-09-26 that section-level timing is enough, so no word-level alignment. Each `[SECTION]` is one file, and the manifest records its length.

### Speech-to-speech recipe (from Ep 7/8 `voice_swap.py`; don't change casually)

- Model `eleven_multilingual_sts_v2` into voice `TcZDZdbOYm8HPLDiDkn0`. Send only the model and `remove_background_noise`, **never `voice_settings`**: invented voice settings caused the pitch artifact David rejected on 2026-08-13. `eleven_sts.py` refuses to run if `voice_settings` is set.
- `remove_background_noise`: `false` for Gemini input, which is clean studio audio. Ep 7 used `true` on Veo audio.
- **Level policy:** STS returns about 4 LU quieter than TTS (Ep 8 measurement). Match level with **gain only** to −18.4 LUFS, plus a −1.5 dBTP true-peak limiter. **Never compress.** STS keeps a real performance (LRA 5–9), and compression ate that warmth on Ep 8. `eleven_sts.py` does this and logs the before and after figures in `vo/maya/manifest.json`.
- Keep audio mono end to end, with PCM intermediates. AAC is encoded **once**, at the final mux. Never downmix an intermediate with `-ac 2`: a stereo downmix phase-cancelled the Ep 7 mix.

## On-camera blocks (Seedance), whichever engine

- Seedance generates Maya speaking her line with its own native voice, and that voice drives the lip sync.
- The native audio is then converted into Maya's voice with the Ep 8 `voice_swap.py` (same STS recipe and level policy as above). STS changes the timbre without changing the timing, so the lips stay in sync.
- Never lay TTS over an on-camera clip: it won't stay in sync.
- The engine choice only governs the voice-only narration. On-camera blocks always go through Seedance and then `voice_swap.py`.

## Open decisions (ask David; update this file when answered)

- [ ] Which **voice** Maya uses in Gemini. Decided by the Ep 11 audition.

## Decision log

| Date | Episode | Decision |
| --- | --- | --- |
| 2026-09-26 | 11 | Engine: **Gemini**. Voice: pick fresh by audition, not Walt's Gray Matters settings. Convert to Maya with ElevenLabs STS. |
| 2026-09-26 | all | `GEMINI_API_KEY` comes from David's PC environment variables. `ELEVENLABS_API_KEY` comes from the pipeline `.env`. On-camera blocks are Seedance, then STS to Maya. Timing per section is enough. |
| 2026-09-26 | all | Everything lives on **D:**, under `D:\Freibrun Enterprises\Heritage Pinoy Talks`. G: is no longer used. |
