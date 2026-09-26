# Episode 11 handoff: cloud session → local (2026-09-26)

David is moving Ep 11 back to a local Claude Code session on his PC, the way Ep 10 was made. The cloud container couldn't reach D:, his keys, or ElevenLabs.

## Where things are

- HPT root: `D:\Freibrun Enterprises\Heritage Pinoy Talks`. G: is retired; never use G: paths from old scripts.
- This repo: `D:\Freibrun Enterprises\Heritage Pinoy Talks\Ruchel-repo`, branch `claude/quirky-wozniak-6i2155`. **Not** `...\Ruchel`, which is a separate, non-git folder of David's; never touch it.
- Skill: `.claude/skills/hpt-voiceover/SKILL.md`. Read it first. Its engine gate is already answered for Ep 11.

## Done

- `script.md`: Little Manila, Stockton. About 2,060 words, 14–15 min. David wants it kept short.
- `titles-thumbnail.md`: top pick is "They Bulldozed America's Biggest Filipino Town — Here's What They Built Instead".
- `fact-check.md`: rows marked **Verify** still need checking:
  - whether Pablo Mabalon was Dawn Mabalon's grandfather
  - the 1999 founding year
  - the Seattle/LA line
- `vo.config.json`: engine is **Gemini**, decided by David. Takes are converted to Maya (`TcZDZdbOYm8HPLDiDkn0`) with ElevenLabs STS, using the Ep 7/8 recipe: no voice_settings, gain-only level match to −18.4 LUFS.
- `tools/gemini_tts.py` and `tools/eleven_sts.py`: tested only against mocked APIs. **No real call has been made yet.**

## Next steps

1. `py tools\gemini_tts.py episodes\ep11-stockton --models`: confirm `gemini-3.8-flash-tts` exists. `GEMINI_API_KEY` is a Windows environment variable.
2. `py tools\gemini_tts.py episodes\ep11-stockton --audition s01`: four cold-open takes in `vo\audition\`. David picks a voice, then set `gemini.voice`.
3. `py tools\gemini_tts.py episodes\ep11-stockton all`, then `py tools\eleven_sts.py episodes\ep11-stockton all`. The ElevenLabs key is in `...\heritage-pinoy-pipeline\.env`; confirm that path still exists on D:.
4. QA per the skill: transcribe each take back, grep for leaked style-prompt words, write a pronunciation listen list.
5. On-camera blocks: Seedance, then the Ep 8 `voice_swap.py`.

## Open

- The next-episode teaser is **TBD**. The `[NEXT TIME]` section is skipped from VO until David decides.
- Maya's Gemini voice, chosen from the audition.
