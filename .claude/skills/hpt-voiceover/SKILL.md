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

## Engine: Gemini TTS

```bash
python3 tools/gemini_tts.py episodes/epNN-slug --list        # parts and word counts, free
python3 tools/gemini_tts.py episodes/epNN-slug s01 --env "G:/My Drive/.../heritage-pinoy-pipeline/.env"
python3 tools/gemini_tts.py episodes/epNN-slug all --env ...
```

- Settings come from `vo.config.json` → `gemini`: `model`, `voice`, `style_prompt`, `language_code` and `temperature`. Leave anything not yet decided as `null`, because the tool refuses to guess.
- Output is `vo/sNN.wav` (24 kHz mono PCM) plus `vo/manifest.json`, which records the exact model, voice, prompt and text of every take.
- **Style prompt:** it is sent in front of the text, so it can leak into the audio. The transcript grep above is mandatory for Gemini.
- **No word timestamps.** Gemini returns audio only. Anything that needs word-cued timing (the Ep 9 `vo_block_timing.py` method) needs an alignment pass on the take. That is still open; see below.

## Open decisions (ask David; update this file when answered)

- [ ] The Gemini **model**, **voice** and **style prompt** Maya uses. Reuse the Gray Matters setup?
- [ ] **Voice continuity.** A Gemini voice won't sound like the ElevenLabs Maya from Ep 6–10. Is a new-sounding Maya acceptable, or does Gemini VO need a speech-to-speech pass into `TcZDZdbOYm8HPLDiDkn0`?
- [ ] **On-camera blocks** in a Gemini episode: keep ElevenLabs speech-to-speech for those, or use Gemini?
- [ ] **Word timing** for Gemini takes: forced alignment, or is section-level timing enough?
- [ ] **Where the API key lives.** Is it the same `.env` as ElevenLabs, and which Google Cloud project is billed?
