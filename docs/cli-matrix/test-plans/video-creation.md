# S1 · Video Creation — End-to-End Test Plan

**Scenario**: `video-creation`  ·  **Matrix**: [`cli-hub-matrix/video-creation/SKILL.md`](../../../cli-hub-matrix/video-creation/SKILL.md)  ·  **Schema**: [`matrix_registry.schema.md`](../matrix_registry.schema.md)

Purpose: validate that the S1 capability matrix supports realistic, end-to-end agent workflows — not just single-capability demos. Each task below hits **3+ capabilities** and is written as a checkable todo list so an evaluator can step through it and mark progress.

**How to run a task**
1. Pick a task, read its *setup* and *intent*.
2. Run the preflight block from [`SKILL.md`](../../../cli-hub-matrix/video-creation/SKILL.md) to know what's available.
3. Walk the todo list, picking providers via the decision rubric. When a provider's `requires` is unmet, either fall back or escalate via the suggest-to-user template — **do not silently skip**.
4. At the end of each task, verify acceptance criteria and note which providers were actually chosen.

**Scoring** (optional, for evaluator): for each task, record per-capability the provider chosen, whether it succeeded, and whether the agent *suggested* rather than silently skipped when a paid API was the best fit.

---

## Task 1 — Product launch explainer (2-minute)

**Intent**: A SaaS startup wants a 90–120s launch video mixing generated hero shots, a real screen recording of the product, a scripted voiceover, light background music, burned captions, a thumbnail, and a social card. English only. Distribution is manual.

**Capabilities exercised**: `visual.generate`, `visual.capture`, `audio.synthesize`, `audio.music`, `composite.assemble`, `text.transcribe`, `composite.overlay`, `package.thumbnail`, `package.encode`. **Touches 9 capabilities.**
**Recipe alignment**: blend of `ai-short` + `screencast-tutorial`.

- [ ] Preflight: list `cli-hub list --json`, check `ffmpeg`, `whisper`, TTS keys, any image-gen keys
- [ ] Draft the 3-beat script (hook / demo / CTA), ~160 words total, save as `script.md`
- [ ] Decide per-capability providers using the decision rubric; record the plan in `plan.json`
- [ ] Generate 2 hero clips via `visual.generate` (veo or Seedance escalation or local diffusers fallback), 4–5s each
- [ ] Record the product demo via `cli-anything-openscreen` at 1080p for ~45s (hide cursor during dead moments)
- [ ] Generate narration via `audio.synthesize` (prefer `elevenlabs` if key present, else `edge-tts`)
- [ ] Generate a loopable background bed via `audio.music` (`suno` or `audiocraft`) ~2 minutes, mood = "uplifting neutral"
- [ ] Duck the music under narration (-12 dB) using `ffmpeg` sidechain or `pydub`
- [ ] Assemble the timeline via `composite.assemble` (`cli-anything-kdenlive` preferred), order: hero → demo → hero → CTA
- [ ] Transcribe the narration via `text.transcribe` (whisper locally) → `subs.srt`
- [ ] Burn captions via `composite.overlay` (`ffmpeg -vf subtitles`) with a readable font + stroke
- [ ] Create a 1280×720 thumbnail via `package.thumbnail` (`cli-anything-gimp` or Pillow) including product wordmark + tagline
- [ ] Export a 1920×1080 H.264 master via `package.encode` (`ffmpeg -c:v libx264 -crf 18`)
- [ ] Write `publish_notes.md` instructing the user how to upload to YouTube/LinkedIn (known gap)

**Acceptance criteria**
- [ ] Final file is 90–120s, 1080p, audible voiceover + ducked music
- [ ] Captions are legible and match the narration word-for-word (±5%)
- [ ] Thumbnail is 1280×720, under 2MB, contains the product name
- [ ] Every provider choice is recorded in `plan.json` with reason
- [ ] Agent either used or *explicitly suggested* a paid provider when quality mattered; no silent skips

---

## Task 2 — Multilingual developer tutorial (EN → ES/JA/ZH)

**Intent**: Record a real screen tutorial explaining a CLI tool, then ship four language variants. Voiceover can be re-synthesized per language; subtitles must exist in all four.

**Capabilities exercised**: `visual.capture`, `audio.capture`, `text.transcribe`, `text.translate`, `audio.synthesize`, `composite.overlay`, `composite.assemble`, `package.thumbnail`, `package.encode`. **Touches 9 capabilities × 4 locales.**
**Recipe alignment**: `screencast-tutorial` ×4.

- [ ] Preflight; check for `DEEPL_API_KEY`, `ELEVENLABS_API_KEY`, and `whisper` locally
- [ ] Record screen + mic at 1440p via `cli-anything-openscreen` (~5–8 minutes)
- [ ] Denoise captured audio via `cli-anything-audacity` or `noisereduce`
- [ ] Transcribe EN via `text.transcribe` (whisper large-v3 or AssemblyAI if key) → `en.srt`
- [ ] Translate `en.srt` to `es.srt`, `ja.srt`, `zh.srt` via `text.translate` (DeepL preferred; fall back to `argos-translate`)
- [ ] Produce re-narrated voiceover for each language via `audio.synthesize` (ElevenLabs multilingual model or MiniMax)
- [ ] For each locale: swap audio track via `composite.assemble`, align to video length (time-stretch narration ±5% if needed)
- [ ] Burn captions for each locale via `composite.overlay` with appropriate font (CJK font for zh/ja)
- [ ] Create 4 thumbnails (flag + title in localized text) via `package.thumbnail`
- [ ] Encode H.264 MP4 per locale via `package.encode`
- [ ] Produce `upload_matrix.md` listing which locale goes where (YT, B站, niconico, etc.)

**Acceptance criteria**
- [ ] 4 final videos, synchronized visually to the same screen recording
- [ ] Captions in each locale present and synced; CJK glyphs render correctly
- [ ] Re-narrated audio is intelligible and roughly matches on-screen action
- [ ] If DeepL key missing, agent offered escalation with cost note; otherwise used `argos-translate`

---

## Task 3 — Long-form podcast-to-video (60-minute episode)

**Intent**: A 60-minute audio-only podcast needs a YouTube video version: static host image, animated waveform/spectrogram, chapter markers derived from topic shifts, burned captions, thumbnail, and a highlight reel for socials.

**Capabilities exercised**: `audio.capture`, `text.transcribe`, `composite.overlay`, `composite.assemble`, `package.thumbnail`, `package.encode`. **Touches 6 capabilities, long-form stress test.**
**Recipe alignment**: `podcast-to-video` + derived highlight reel.

- [ ] Preflight; verify disk space (≥20GB free for 60-min 1080p masters)
- [ ] Clean source audio via `audio.capture` providers (`noisereduce` + EQ in Audacity if needed)
- [ ] Transcribe full 60 min via `text.transcribe` (whisper large-v3 locally if GPU; else chunk into 10-min segments and stitch)
- [ ] Detect chapter boundaries: cluster transcript by topic via `knowledge.synthesize` (S2 overlap) or prompt a local LLM; produce `chapters.json` with timestamps
- [ ] Render animated waveform via `ffmpeg showwaves` or `moviepy`
- [ ] Composite waveform onto host still via `composite.overlay`
- [ ] Burn captions per chapter via `composite.overlay` (turn on/off per section if you prefer)
- [ ] Assemble final via `composite.assemble` (native `ffmpeg concat` is fine; `moviepy` if you want per-chapter crossfades)
- [ ] Encode 1080p master + 720p preview via `package.encode`
- [ ] Create thumbnail via `package.thumbnail`: host portrait + episode title + # number
- [ ] Extract 3× 60-second highlight clips based on `chapters.json` importance scores
- [ ] For each highlight: re-crop 9:16, add kinetic captions, export separately
- [ ] Produce `youtube_description.md` with timestamped chapter links from `chapters.json`

**Acceptance criteria**
- [ ] Main video is ≈60 min, in sync with source audio throughout
- [ ] Chapters in the YouTube description match visible chapter markers in the video
- [ ] Highlights are 55–65s each, vertical (1080×1920), with readable kinetic captions
- [ ] Transcription quality: spot-check at 5%/50%/95% marks — >95% word accuracy

---

## Task 4 — Talking-head YouTube essay with AI b-roll

**Intent**: A 6-minute personal essay: the creator on webcam delivering the script, cutaways of AI-generated b-roll illustrating key concepts, music bed under the voice, captions, thumbnail A/B variants.

**Capabilities exercised**: `visual.capture`, `visual.generate`, `audio.capture`, `text.transcribe`, `audio.music`, `composite.assemble`, `composite.overlay`, `package.thumbnail` (×2), `package.encode`. **Touches 9 capabilities, A/B variant testing.**
**Recipe alignment**: `talking-head-explainer`.

- [ ] Preflight
- [ ] Record webcam + lav mic via `visual.capture` + `audio.capture` at 1080p60
- [ ] Transcribe raw take via `text.transcribe`; mark filler words / retakes in `edit_plan.json`
- [ ] Cut silences and retakes per `edit_plan.json` via `composite.assemble` (`moviepy` is fine here)
- [ ] Identify 6–10 "cutaway moments" from the transcript where b-roll should appear
- [ ] Generate b-roll clips via `visual.generate` (prefer local `diffusers` SVD for cost; escalate to Runway/Kling/Seedance if quality bar demands it — ask user)
- [ ] Add ducked music bed via `audio.music` (`audiocraft` local is fine for essay mood)
- [ ] Overlay captions via `composite.overlay` (styled like a premium video essay, not burn-in ASS)
- [ ] Create **two** thumbnail variants via `package.thumbnail`:
  - [ ] A: close-up face + bold question
  - [ ] B: abstract b-roll frame + short headline
- [ ] Encode master + a 720p preview via `package.encode`
- [ ] Write `ab_test_plan.md` describing which thumbnail to push first and how to swap after 48h

**Acceptance criteria**
- [ ] Cutaways land on conceptual beats, not mid-sentence
- [ ] Music never clashes with voice at crucial lines (check by RMS over the voiceover)
- [ ] Both thumbnails exported at 1280×720, < 2MB each
- [ ] Agent documented the cost/quality tradeoff if it escalated to a paid video API

---

## Task 5 — Beat-synced AI music video

**Intent**: Generate a 90-second song via AI music, then drive visual cuts to match the beat. Lyrics overlay. Thumbnail. No captions.

**Capabilities exercised**: `audio.music`, `visual.generate`, `composite.assemble`, `composite.overlay`, `package.thumbnail`, `package.encode`. **Touches 6 capabilities, timing-critical.**
**Recipe alignment**: extension of `ai-short`.

- [ ] Preflight; confirm `suno`/Udio/minimax availability
- [ ] Write lyrics (3 verses + chorus); save as `lyrics.txt`
- [ ] Generate 90s song via `audio.music` (Suno preferred; fall back to `audiocraft`)
- [ ] Beat-detect via `librosa.beat.beat_track` → `beats.json`
- [ ] Plan ~30 short clips (~3s each) across the song, bias cuts to beat timestamps
- [ ] Generate each clip via `visual.generate` (seed-locked per shot so re-rolls are deterministic)
- [ ] Assemble on the beat via `composite.assemble` using `ffmpeg concat` with exact frame trims from `beats.json`
- [ ] Overlay stylized lyrics via `composite.overlay` (word-by-word karaoke-style using ASS or ffmpeg drawtext+timecodes)
- [ ] Create a striking thumbnail via `package.thumbnail` (pick best frame + title treatment)
- [ ] Encode at 1080p60 via `package.encode`

**Acceptance criteria**
- [ ] Cuts land within ±1 frame of detected beats (check via `ffprobe` packet timestamps vs `beats.json`)
- [ ] Lyrics appear on the right word at the right time (sample 5 random lines)
- [ ] No audio desync at end (lengths match within 50ms)

---

## Task 6 — Reaction video (imported clip + webcam + commentary)

**Intent**: Creator watches a 4-minute news clip and reacts. Final video has PiP webcam, full-screen source, running captions of the creator's commentary, plus bleeped moments.

**Capabilities exercised**: `visual.capture`, `audio.capture`, `text.transcribe`, `composite.assemble`, `composite.overlay`, `audio.capture` (bleep edit), `package.thumbnail`, `package.encode`. **Touches 8 capabilities.**

- [ ] Preflight
- [ ] Load source clip (user-provided); verify copyright/fair-use notes with user before continuing
- [ ] Record webcam + mic via `visual.capture` + `audio.capture` synced with source playback
- [ ] Transcribe creator's reaction track via `text.transcribe` → `reaction.srt`
- [ ] Identify bleep candidates (profanity list) in `reaction.srt`; edit audio to bleep those windows (`ffmpeg` sine tone overlay)
- [ ] Composite: source full-screen, webcam PiP bottom-right, via `composite.assemble`
- [ ] Overlay captions from `reaction.srt` via `composite.overlay` (styled distinct from any source subs)
- [ ] Thumbnail via `package.thumbnail` with split-screen layout (source still + creator reaction still)
- [ ] Encode via `package.encode`

**Acceptance criteria**
- [ ] PiP never covers faces in the source clip (manual spot check)
- [ ] Bleeps are audible and exactly cover flagged words (±100ms)
- [ ] Agent asked the user about rights before proceeding

---

## Task 7 — Live-event recap with chapters and highlight grid

**Intent**: Concatenate footage from 3 camera angles of an event into a 7-minute recap with transitions, insert on-screen chapter titles, export a grid of thumbnails (one per chapter) as a single image.

**Capabilities exercised**: `composite.assemble`, `composite.overlay`, `text.transcribe` (for auto-chapter naming from any spoken words), `package.thumbnail`, `package.encode`. **Touches 5 capabilities, heavy on assembly.**

- [ ] Preflight
- [ ] Receive 3 input files; probe via `ffprobe` to verify frame rates / resolutions; transcode to a common intermediate if needed
- [ ] Detect scene cuts via `ffmpeg -vf "select='gt(scene,0.3)'"` per camera
- [ ] Assemble multi-cam edit via `composite.assemble` (manual cut list is fine; rotate angles every 8–15s)
- [ ] Transcribe any ambient speech via `text.transcribe` for chapter naming
- [ ] Overlay chapter title cards via `composite.overlay` at 6 chapter boundaries
- [ ] Generate chapter thumbnails (6 stills), compose into a 3×2 grid via `package.thumbnail` (Pillow or ImageMagick)
- [ ] Encode final recap via `package.encode`

**Acceptance criteria**
- [ ] Final duration = 7 min ±10s
- [ ] Chapter cards fade in/out cleanly (no single-frame flash)
- [ ] Grid image is 1920×1080, 6 panels evenly sized, labeled

---

## Task 8 — Offline-only documentary cut

**Intent**: Produce a 5-minute documentary-style piece without any cloud APIs (user is in a regulated / offline environment). All providers must have `offline: true`.

**Capabilities exercised**: `audio.capture`, `text.transcribe` (whisper local), `composite.assemble`, `composite.overlay`, `package.thumbnail`, `package.encode`. Explicitly **excludes** paid APIs and cloud TTS.

- [ ] Preflight; confirm network unreachable or flag "offline mode" for this task
- [ ] Enumerate offline providers per capability in `offline_plan.json`
- [ ] Record narration via `audio.capture` (mic) in Audacity
- [ ] Assemble existing footage via `composite.assemble` (`kdenlive` or `ffmpeg`)
- [ ] Transcribe via whisper local → `subs.srt`
- [ ] Burn captions via `composite.overlay` (ffmpeg subtitles filter)
- [ ] Generate thumbnail via `cli-anything-gimp` or Pillow (no cloud image gen)
- [ ] Encode master via `package.encode`
- [ ] If the agent at any point would benefit from an API, record *what* it would have escalated to in `escalations_declined.md`

**Acceptance criteria**
- [ ] Network trace (or declared offline) shows zero external API calls
- [ ] Final deliverable fully produced with offline providers
- [ ] `escalations_declined.md` lists at least 2 spots where the agent would have preferred an API (honesty check)

---

## Task 9 — Short-form vertical cross-platform (TikTok / Reels / Shorts)

**Intent**: Take one long horizontal clip (90s) and produce 3 platform-specific vertical variants with kinetic captions, platform-safe aspect, watermark, and correct encoding profiles.

**Capabilities exercised**: `composite.assemble`, `composite.overlay`, `text.transcribe`, `package.thumbnail` (×3), `package.encode` (×3). **Touches 5 capabilities, strict format matrix.**

- [ ] Preflight
- [ ] Transcribe source via `text.transcribe` with word-level timestamps
- [ ] Reframe source to 9:16 via `composite.assemble`, tracking the subject (ffmpeg + opencv face/object center or manual crops per segment)
- [ ] Generate kinetic captions (word-by-word pop) via `composite.overlay` with ASS karaoke or ffmpeg drawtext
- [ ] Add platform watermark via `composite.overlay` (TikTok: bottom-left username; Reels: none, rely on caption; Shorts: bottom-right)
- [ ] Thumbnail per platform via `package.thumbnail` (TikTok/Reels may auto-generate, still produce a cover still)
- [ ] Encode three variants per platform guidelines:
  - [ ] TikTok: 1080×1920, H.264 High, ~16 Mbps, ≤60s trimmed version
  - [ ] Reels: 1080×1920, H.264, ≤90s
  - [ ] Shorts: 1080×1920, H.264, ≤60s
- [ ] Produce `publish_checklist.md` with manual upload instructions + hashtags per platform (known gap)

**Acceptance criteria**
- [ ] All three files open in their respective platform specs without re-encode warnings
- [ ] Captions never cover the subject's face during close-ups
- [ ] Agent noted `publish.upload` as a known gap and produced manual instructions rather than pretending to upload

---

## Task 10 — Localization re-cut with voice swap (ZH → EN)

**Intent**: The user supplies a finished Chinese video (with Chinese burn-in captions) and wants an English re-cut: strip the burn-ins, add English narration that matches the original pacing, add English captions, keep the same music bed.

**Capabilities exercised**: `composite.overlay` (inverse — crop/mask captions), `text.transcribe`, `text.translate`, `audio.synthesize`, `audio.capture` (isolate music bed), `composite.assemble`, `composite.overlay`, `package.thumbnail`, `package.encode`. **Touches 9 capabilities, advanced audio routing.**

- [ ] Preflight; confirm DeepL / OpenAI translate availability, multilingual TTS
- [ ] Crop or blur the bottom-third caption band via `composite.overlay` (`ffmpeg` drawbox or delogo)
- [ ] Isolate music bed: attempt vocal removal via `demucs` or spectral subtraction; verify clean bed at representative timecodes
- [ ] Transcribe the original Chinese narration via `text.transcribe` (whisper zh)
- [ ] Translate `zh.srt` → `en.srt` via `text.translate` (DeepL preferred; confirm translations make sense via a quick LLM review)
- [ ] Generate English voiceover via `audio.synthesize` with pacing aligned to original SRT timecodes (time-stretch ±10% if needed)
- [ ] Mix new narration over the isolated music bed via `ffmpeg` (ducking)
- [ ] Rebuild final via `composite.assemble` (picture from masked source + new audio track)
- [ ] Burn English captions via `composite.overlay`
- [ ] Translate and rebuild thumbnail text via `package.thumbnail`
- [ ] Encode via `package.encode`

**Acceptance criteria**
- [ ] No Chinese text visible in final (spot-check 5 random frames)
- [ ] English narration is synced to visible action within ±500ms
- [ ] Music bed isn't noticeably degraded by vocal-removal artifacts
- [ ] Agent flagged any section where vocal isolation failed rather than shipping garbled audio

---

## Task 11 — Meeting recording → executive explainer

**Intent**: A 45-minute Zoom-style recording needs to become a 3-minute executive-audience explainer: extract the key decisions, re-narrate over curated screen captures, add chapter markers, branded opening/closing.

**Capabilities exercised**: `audio.capture`, `text.transcribe`, `audio.synthesize` (re-narration), `visual.capture` (if re-shooting), `composite.assemble`, `composite.overlay`, `package.thumbnail`, `package.encode`. Overlaps with S2 `knowledge.synthesize`. **Touches 8 capabilities.**

- [ ] Preflight; confirm TTS, synthesis LLM, and `ffmpeg`
- [ ] Transcribe full meeting via `text.transcribe`
- [ ] Summarize into 3–5 decisions via LLM (S2 `knowledge.synthesize`); produce `summary.md`
- [ ] Extract the original screen captures that best illustrate each decision (copy frames/segments from source video)
- [ ] Generate exec-tone re-narration via `audio.synthesize` matching the summary
- [ ] Assemble final via `composite.assemble`: branded intro (`visual.generate` or pre-made card), decision sections, closing CTA
- [ ] Overlay chapter titles + lower-third decision labels via `composite.overlay`
- [ ] Caption the new narration via `text.transcribe` + `composite.overlay`
- [ ] Thumbnail with title + company logo via `package.thumbnail`
- [ ] Encode 1080p via `package.encode`
- [ ] Write `distribution_suggestion.md` — where this should go (internal Slack? shared drive?)

**Acceptance criteria**
- [ ] Final is 2.5–3.5 min
- [ ] Each on-screen decision is traceable to a timestamp in the source recording (record mapping in `trace.json`)
- [ ] No PII from the meeting is surfaced that shouldn't be (agent flags risky moments)

---

## Task 12 — Gameplay "best moments" reel from raw footage

**Intent**: User provides 2 hours of raw gameplay recording. Produce a 5-minute "best moments" reel: auto-detect exciting moments (loud spikes, kill feed, chat excitement), add commentary via TTS using user-supplied notes, intro/outro, captions, thumbnail.

**Capabilities exercised**: `audio.capture` (analysis), `text.transcribe` (in-game voice/chat if present), `composite.assemble`, `audio.synthesize`, `composite.overlay`, `package.thumbnail`, `package.encode`. **Touches 7 capabilities, heavy on auto-detection.**

- [ ] Preflight; check disk space (2h raw ≈ 20–60GB)
- [ ] Analyze source audio with `librosa` to find peaks/spikes; emit `candidates.json` with timestamps
- [ ] Optionally OCR the kill feed via `tesseract` on sampled frames (not in matrix; document as cross-matrix use)
- [ ] Merge peak candidates within 10s windows; cap at ~20 moments of 10–20s each
- [ ] Generate commentary lines from user notes per moment via `audio.synthesize`
- [ ] Assemble final via `composite.assemble`: intro card + moments + transitions + outro
- [ ] Duck game audio under commentary
- [ ] Caption commentary via `composite.overlay`
- [ ] Thumbnail from best candidate frame via `package.thumbnail` (title + game logo)
- [ ] Encode 1080p60 via `package.encode`

**Acceptance criteria**
- [ ] Final duration 4.5–5.5 min
- [ ] Each selected moment is genuinely "exciting" on manual review (false-positive rate < 25%)
- [ ] Commentary is audible over game audio at every cut

---

## Task 13 — Ads variant generator (one brief → 5 creatives)

**Intent**: A brand brief and one stock clip should produce 5 ad creatives varying hook, CTA placement, and aspect ratio (16:9, 1:1, 9:16, 4:5, 9:16-short). Each includes AI-generated product shots, voiceover, music, captions.

**Capabilities exercised**: `visual.generate` (×many), `audio.synthesize`, `audio.music`, `composite.assemble` (×5), `composite.overlay` (×5), `package.thumbnail` (×5), `package.encode` (×5). **Touches 7 capabilities across 5 outputs — stress test for parallel execution.**

- [ ] Preflight
- [ ] Parse brief.md → produce `creative_plan.json` with 5 variants (hook, CTA, aspect, length)
- [ ] Generate shared music bed via `audio.music` (reuse across all 5)
- [ ] Generate per-variant voiceovers via `audio.synthesize` (different voices per variant to test)
- [ ] For each variant, generate 2 product shots via `visual.generate` (consistent seeds where useful)
- [ ] For each variant, assemble via `composite.assemble` in the target aspect
- [ ] For each variant, overlay headline/CTA + captions via `composite.overlay`
- [ ] For each variant, thumbnail via `package.thumbnail`
- [ ] Encode all 5 via `package.encode`
- [ ] Write `ab_matrix.md` describing which combinations to test first and what metric

**Acceptance criteria**
- [ ] 5 final videos in correct aspect ratios, lengths ≤ brief spec
- [ ] Brand visual identity consistent (color palette, type, logo placement) across variants
- [ ] Agent explicitly ranked providers by cost and gave the user an estimated total spend before generation

---

## Cross-task checks (run once per evaluation batch)

- [ ] No task left `publish.upload` as silently skipped; all 13 tasks either produced manual instructions or escalated with user-provided creds
- [ ] Agent ran the preflight block at task start and didn't re-run unnecessarily across tasks within the same session
- [ ] When paid APIs were used, the suggest-to-user template (capability / provider / env / cost / fallback) was used verbatim
- [ ] Workspace hygiene: each task produced a single top-level directory with intermediates preserved, not scattered
- [ ] Decision rubric order was followed: the agent didn't jump to paid APIs when a free provider would have been adequate (spot-audit 3 random tasks)

---

## Reporting template (per task)

```markdown
### Task N — <title>

- **Status**: pass / partial / fail
- **Providers chosen** (per capability):
  - visual.generate → <provider> (reason)
  - ...
- **Escalations proposed**: <list>
- **Escalations accepted by user**: <list>
- **Unexpected blockers**: <text>
- **Acceptance criteria met**: N of M
- **Workspace**: <path>
```
