---
name: hpt-voiceover
description: Generate Maya's narration VO for a Heritage Pinoy Talks (HPT) episode. Starts with a hard gate, where David picks Gemini TTS or ElevenLabs for that episode, then follows the chosen engine's method. Use whenever an HPT episode needs voiceover, a re-take, or a pronunciation fix.
---

# HPT voiceover

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
- The generators live in the Drive pipeline (`heritage-pinoy-pipeline`, e.g. Ep 9's `gen_sections_vo.py`).

## Engine: Gemini TTS (then converted to Maya)

David's ruling (2026-09-26, Ep 11): **Gemini performs, ElevenLabs converts it into Maya's voice.** Gemini gives the delivery. Speech-to-speech into `TcZDZdbOYm8HPLDiDkn0` keeps Maya sounding the same as Ep 6–10. Both steps are required. A raw Gemini take never ships.

```bash
EP=episodes/epNN-slug
GM_ENV="<Gray Matters .env>"                                   # GEMINI_API_KEY
HPT_ENV="G:/My Drive/.../heritage-pinoy-pipeline/.env"         # ElevenLabs key

python3 tools/gemini_tts.py $EP --list                            # parts and word counts, free
python3 tools/gemini_tts.py $EP --models --env "$GM_ENV"          # confirm the model id exists
python3 tools/gemini_tts.py $EP --audition s01 --env "$GM_ENV"    # one take per audition voice
#   David picks a voice by ear, then write it into gemini.voice
python3 tools/gemini_tts.py $EP all --env "$GM_ENV"               # vo/sNN.wav
python3 tools/eleven_sts.py $EP all --env "$HPT_ENV"              # vo/maya/sNN.mp3  <- these ship
```

- **Settings** come from `vo.config.json`: `gemini` holds `model`, `voice`, `audition_voices`, `style_prompt`, `language_code` and `temperature`; `sts` holds the voice ID, model and voice settings. The tools refuse to guess: `voice` stays `null` until David has picked one.
- **Voice audition:** do it once per new setup, on the cold open. Judge each take on its delivery, since the timbre gets replaced later. If David wants to hear the takes as Maya, run each audition file through STS before he listens.
- **Style prompt:** it is sent in front of the text, so it can leak into the audio. The transcript grep is mandatory. Run it on the **converted** file, because that is what ships.
- **Model:** `gemini-3.8-flash-tts` was the newest model at setup (announced 2026-09-23). Confirm it with `--models` on the first run; if the ID differs, fix the config rather than the code.
- **Levels:** Maya's STS output may sit at a different loudness from the Ep 8–10 TTS. Level-match in the mix, as was done for on-camera blocks.
- **No word timestamps.** Neither Gemini nor STS returns word times. If an episode needs word-cued timing (the Ep 9 `vo_block_timing.py` method), that needs an alignment pass on `vo/maya/sNN.mp3`. That is still an open question.

## Open decisions (ask David; update this file when answered)

- [ ] Which **voice** Maya uses in Gemini. Decided by the Ep 11 audition.
- [ ] The **path of the Gray Matters `.env`** that holds `GEMINI_API_KEY`.
- [ ] **On-camera blocks** in a Gemini episode: keep the Veo-native-audio → STS method, or use Gemini audio → STS?
- [ ] **Word timing** for Gemini takes: forced alignment, or is section-level timing enough?

## Decision log

| Date | Episode | Decision |
| --- | --- | --- |
| 2026-09-26 | 11 | Engine: **Gemini**. Voice: pick fresh by audition, not Walt's Gray Matters settings. Convert to Maya with ElevenLabs STS. Gemini key comes from the Gray Matters `.env`. |
