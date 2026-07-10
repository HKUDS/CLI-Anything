---
name: cli-hub-matrix-video-creation
description: >-
  Capability-based multi-tool matrix for video production. Agents pick providers
  (CLI-Anything harnesses, public CLIs, Python libs, native binaries, cloud APIs)
  per capability rather than marching through fixed stages, including storyboard
  planning, story/audio direction, source triage, internet video/music
  search/download, capture/generation, analysis, sound design, high-end caption
  design, NLE/render doctor investigation, review, and packaging.
---

# Video Creation Matrix (v3 — capability-based)

This matrix describes **capabilities** the agent can compose on demand — not a fixed pipeline. A "video creation" workflow picks a *recipe* (which capabilities it needs) and, per capability, picks a *provider* from the task requirements and preflight facts below.

Schema: [`docs/cli-matrix/matrix_registry.schema.md`](../../docs/cli-matrix/matrix_registry.schema.md).

## Install (installable portion)

```bash
cli-hub matrix install video-creation   # installs registered matrix CLIs only
cli-hub matrix info    video-creation   # inspect providers & recipes
cli-hub matrix preflight video-creation # check available providers in this environment
```

Not everything in this matrix is installed by `cli-hub matrix install`. Cloud APIs, Python packages, native binaries, third-party public CLIs, and external skills are first-class providers too, but install them only after the task actually needs that provider.
Do not hand-write `pip install ...#subdirectory=...` for CLI-Anything matrix members; install the supported harnesses through `cli-hub matrix install video-creation`, then use preflight to see what else is already available.

---

## Provider selection constraints (agent: evaluate per capability)

1. Use preflight as an availability report, not as a provider selector.
2. Choose providers from the user's goal, quality bar, budget, offline needs, credential state, install cost, and requested workflow.
3. Treat registry/provider order as documentation order only; do not assume the first provider is the correct one.
4. Install Python libs, native binaries, harness CLIs, public CLIs, or agent skills only when they fit the task constraints.
5. Escalate to paid or metered APIs only when the user has supplied credentials or explicitly consents. Never silently call a paid API.
6. If a task falls into a genre with a mandatory provider rule, the provider is not optional. Do not substitute a cheaper/easier fallback just because it is locally convenient.

Offline context? Filter to `offline: true` providers only.

---

## Preflight (run once per session, cache the result)

Run the built-in matrix preflight first:

```bash
cli-hub matrix preflight video-creation --json
cli-hub matrix preflight video-creation --capability composite.assemble
cli-hub matrix preflight video-creation --offline
```

If you need raw checks or are running without the latest `cli-hub`, use the manual block:

```bash
cli-hub list --json
python - <<'PY'
import importlib.util
for m in ("moviepy","whisper","pydub","PIL","edge_tts","pysrt","pysubs2","yt_dlp","spotdl","scenedetect","paddleocr","twelvelabs"):
    print(m, importlib.util.find_spec(m) is not None)
PY
for b in ffmpeg ffprobe sox convert magick screencapture yt-dlp spotdl scdl bandcamp-dl you-get lux BBDown scenedetect mediainfo ffmpeg-quality-metrics paddleocr hyperframes; do command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"; done
for e in RUNWAY_API_KEY KLING_API_KEY PIKA_API_KEY SEEDANCE_API_KEY \
         ELEVENLABS_API_KEY MINIMAX_API_KEY OPENAI_API_KEY GOOGLE_CLOUD_PROJECT \
         ASSEMBLYAI_API_KEY DEEPGRAM_API_KEY \
         SUNO_API_KEY UDIO_API_KEY IDEOGRAM_API_KEY STABILITY_API_KEY \
         TWELVELABS_API_KEY GOOGLE_APPLICATION_CREDENTIALS; do
  [ -n "${!e}" ] && echo "$e: set" || echo "$e: unset"
done
```

---

## Suggest-to-user template (agent uses verbatim when escalating)

```
To enable <capability> via <provider>, please set <ENV_VAR>.
  Cost: <cost notes>
  Quality: <quality tier>
Reply 'skip' to fall back to <next provider>.
```

Examples:

- *To enable cinematic AI video via Runway Gen-4, please set `RUNWAY_API_KEY`. Cost: ~$0.05/sec as of 2026-04. Quality: sota. Reply 'skip' to fall back to `generate-veo-video` or `jimeng` if configured.*
- *To enable ByteDance Seedance video generation, please set `SEEDANCE_API_KEY`. Cost: metered per-clip. Quality: sota for realistic motion. Reply 'skip' to fall back to `jimeng` (Dreamina) which shares the ByteDance model family.*

---

## Capabilities

### `script.storyboard` — brief to creative direction, script, shot list, timing, and asset plan

Use this before generation, search, capture, or assembly when the user gives a vague concept or asks for a complete video. By default, do the planning directly as agent work: produce a structured brief, global creative direction, narrative/emotional arc, audio arc, script/narration, shot list, timing map, asset requirements, and reviewable storyboard before spending time on downloads or generation.

For any non-trivial video, read [`references/story-structure-audio.md`](references/story-structure-audio.md) and save `creative_direction.md` before final assembly. This is mandatory for trailers, sports/music montages, film commentary, found-footage edits, product launch videos, and any output where flat random clips or boring music would fail the brief.

Hard gate: do not begin final assembly for a non-trivial video until `creative_direction.md` exists. `plan.md` is not a substitute. The file must include target duration or requested duration range, output language, a shot-role table with time, beat, source/shot role, audio event, caption/title role, and failure risk; reject plans where the ending/final act has no payoff, climax, reveal, useful recap, or deliberate unresolved hook appropriate to the genre. Language rule: if the user specifies an output language, use it for all agent-authored viewer-facing content; otherwise use the language the user is using in the conversation.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| Agent-native planning | agent-native | none | free | high | yes |
| `storyboard-creation` skill | agent-skill | installed skill | free | high | yes |
| `remotion-best-practices` skill | agent-skill | installed skill | free | high for code-driven motion video | yes |

Selection:

- Start with agent-native planning for normal scripts, shot lists, timing maps, and asset plans.
- Include `creative_direction.md` with the one-sentence promise, story arc, emotional curve, audio arc, cut-density curve, visual motif, source roles, and no-flatness guardrails.
- Use `storyboard-creation` only when you need explicit storyboard-panel conventions, camera-angle grammar, continuity checks, or animatic planning.
- Use `remotion-best-practices` only when the storyboard will be implemented as Remotion/React motion-video code.

### `video.search` — discover candidate internet footage

Use this before `video.download` when the user asks for found footage, B-roll, public-domain clips, stock footage, YouTube/Bilibili material, or named movie/TV/game/anime moments. Prefer free/open sources first and record source URL, license, creator, and attribution requirement before editing.

For found-footage deliverables or platform-origin claims, read [`references/source-triage.md`](references/source-triage.md) and classify each candidate as direct platform source, verified platform-origin transport, or weak mirror.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| Web search + source filters | web-search | online search access | free | good | no |

Search discipline:

- For reusable/commercial-safe B-roll, start with Wikimedia Commons, YouTube Creative Commons, or other browser-searchable stock/public-domain pages and keep attribution metadata beside every downloaded file.
- For Bilibili/YouTube reference or fan-edit workflows, search specific scene names rather than generic terms. Add quality modifiers such as `1080p`, `4K`, `HD`, `BD`, `蓝光`, or `高清`.
- For Bilibili, use targeted web search such as `site:bilibili.com "Game of Thrones" S3E09 BV`; standalone `/video/BV...` uploads are usually easier to process than geo-restricted bangumi URLs.
- Do not treat downloadability as permission. If license or user authorization is unclear, ask before using the footage in a deliverable.

### `video.download` — download/import web video into the workspace

Use this after `video.search` identifies candidate URLs, or directly when the user gives URLs. Keep all raw downloads in one `sources/` directory, save `sources.json` with URL/license/creator/provenance, and normalize filenames before downstream editing.

For internet footage, `sources.json` must record the platform URL, transport URL if different, command, cookie-file path if used, local file, probe summary, selected ranges, source role, license/rights notes, and quality caveats.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `yt-dlp` | public-cli | `yt-dlp` + `ffmpeg` | free | high | no |
| `you-get` | public-cli | `you-get` bin | free | good | no |
| `lux` | public-cli | `lux` + `ffmpeg` | free | good | no |
| `BBDown` | public-cli | `BBDown` + `ffmpeg` | free | high for Bilibili | no |

Operational notes:

- Prefer `yt-dlp -f "bestvideo[height>=1080]+bestaudio/best" --merge-output-format mp4` for YouTube/Bilibili URLs when quality matters. Use cookies only when the user has authorized access to the content.
- For Bilibili audio-only extraction, avoid `yt-dlp -x --audio-format mp3`; download the raw m4a and convert with `ffmpeg`, then verify volume before using it.
- Use `BBDown` when Bilibili-specific metadata, subtitles, danmaku, playlists, or high-quality member streams are central to the task.

### `music.search` — discover existing songs, BGM, or clean audio sources

Use this before `music.download` when the user wants an existing song, soundtrack cue, royalty-free track, platform audio, or a specific cover/version. Keep the search about the requested music, not just any available audio. Record title, artist, platform URL, uploader, source type, version notes, rights/licensing, and attribution in `music_sources.json`.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| Web search + source filters | web-search | online search access | free | good | no |
| `yt-dlp` search extractors | public-cli | `yt-dlp` | free | good | no |
| `spotdl` metadata/search | public-cli | `spotdl` | free | good for Spotify-linked songs | no |

Search discipline:

- For clean audio, look for the artist's official upload, label upload, official audio/MV, verified lyric video, or a standalone audio upload with no extra descriptors.
- If the user asks for a specific version such as `女生版`, duet, piano, acoustic, live, DJ, karaoke, or instrumental, verify the title/uploader/metadata names that exact version before committing.
- Reject candidate titles that imply the wrong source: `remix`, `cover`, `fan edit`, `AMV`, `MAD`, `mashup`, compilation, trailer mix, or unrelated soundtrack/OST unless the user explicitly asked for that variant.
- For tie-in songs and promo tracks, assume dialogue/voiceover/SFX bleed is possible. Search alternatives with `{artist} {song} 纯音乐`, `{song} 无对白`, `{song} 歌词版`, `official audio`, or `lyric video` before asking the user to accept a risky source.
- Do not treat downloadability as permission. If rights, license, or user authorization is unclear, ask before using the music in a deliverable.

### `music.download` — download/import existing music into the workspace

Use this after `music.search` identifies a candidate or directly when the user supplies a music URL/local file. Keep raw downloads in `sources/music/`, save `music_sources.json`, and create a normalized working file for editing.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `yt-dlp` audio download | public-cli | `yt-dlp` + `ffmpeg` | free | high | no |
| `spotdl` | public-cli | `spotdl` + `ffmpeg` | free | good for Spotify-linked metadata | no |
| `scdl` | public-cli | `scdl` | free | good for SoundCloud | no |
| `bandcamp-dl` | public-cli | `bandcamp-dl` | free | good for Bandcamp | no |
| local file import + `ffmpeg` | native | `ffmpeg` | free | high | yes |

Operational notes:

- Use only music the user is authorized to use or that is clearly licensed for the deliverable. Do not bypass DRM, paywalls, or access controls.
- For general audio URLs, download source audio first, then convert explicitly:

```bash
yt-dlp -f "bestaudio[ext=m4a]/bestaudio" -o "sources/music/audio_raw.%(ext)s" "URL"
ffmpeg -i sources/music/audio_raw.m4a -vn -c:a libmp3lame -q:a 0 sources/music/audio.mp3
```

- For Bilibili audio-only downloads, do **not** use `yt-dlp -x --audio-format mp3`; it can produce a valid-looking but nearly silent MP3. Download the raw m4a, convert with `ffmpeg`, then verify volume:

```bash
yt-dlp -f 30280 -o "sources/music/audio_raw.%(ext)s" "BILIBILI_URL"
ffmpeg -i sources/music/audio_raw.m4a -c:a libmp3lame -q:a 0 sources/music/audio.mp3
ffmpeg -i sources/music/audio.mp3 -af volumedetect -f null - 2>&1 | grep mean_volume
```

Reject files with mean volume below roughly `-40dB` unless silence is expected.

- Sample-listen at least three points before editing, especially for promo/OST/tie-in songs:

```bash
ffplay -ss 30 -t 5 -autoexit sources/music/audio.mp3
ffplay -ss 90 -t 5 -autoexit sources/music/audio.mp3
ffplay -ss 150 -t 5 -autoexit sources/music/audio.mp3
```

- Normalize or loudness-match only after verifying the source is the right song/version and has no dialogue/SFX bleed.

### `visual.capture` — record screen / webcam / window

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-openscreen` | harness-cli | harness installed | free | high | yes |
| `cli-anything-obs-studio` | harness-cli | OBS installed | free | high | yes |
| `ffmpeg -f x11grab` / `avfoundation` | native | `ffmpeg` | free | high | yes |
| `screencapture` | native | macOS | free | high | yes |
| `mss` / `pyautogui` + `cv2` | python | pkgs | free | good | yes |

### `visual.generate` — produce a video clip from prompt/reference

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `generate-veo-video` | public-cli | `generate-veo` bin + Google creds | metered | high | no |
| `jimeng` | public-cli | `dreamina` bin + Dreamina login | metered | high | no |
| Runway Gen-4 | api | `RUNWAY_API_KEY` | paid | sota | no |
| Kling | api | `KLING_API_KEY` | paid | high | no |
| Pika | api | `PIKA_API_KEY` | paid | good | no |
| Seedance | api | `SEEDANCE_API_KEY` | paid | sota | no |

### `audio.capture` — record and clean audio tracks

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-audacity` | harness-cli | Audacity installed | free | high | yes |
| `sox` / `ffmpeg` | native | binary | free | high | yes |
| `pydub` / `soundfile` / `librosa` / `noisereduce` | python | pkgs | free | good | yes |

### `audio.synthesize` — text-to-speech / voice

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `minimax-cli` | public-cli | bin + MiniMax key | metered | high | no |
| `elevenlabs` | public-cli | bin + `ELEVENLABS_API_KEY` | paid | sota | no |
| OpenAI TTS | api | `OPENAI_API_KEY` | metered | high | no |
| Google Cloud TTS | api | `GOOGLE_CLOUD_PROJECT` | metered | high | no |
| `edge-tts` | python | pkg | free | good | no |

### `music.generate` — generated music / BGM

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `suno` | public-cli | bin + Suno account | metered | sota | no |
| `minimax-cli` | public-cli | bin + MiniMax key | metered | high | no |
| Udio | api | `UDIO_API_KEY` | paid | sota | no |

Use `music.search` + `music.download` instead when the user asks for an existing song, official upload, platform audio, soundtrack cue, royalty-free track, or a specific cover/version.

Music and SFX must follow the story/audio arc in `creative_direction.md`. For polished 60+ second videos, choose a real main music strategy first: either AI-generated music from a music provider, downloaded relevant/authorized music via `music.search` + `music.download`, or strong source ambience when the genre is documentary/ambient. Avoid one flat loop from start to finish; plan section changes such as intro, buildup, drop, dip, final lift, source-audio reveal, or final resolve.

### `sound.design` — hits, risers, score sections, mix dynamics, and final audio arc

Use this when a video needs trailer hits, whooshes, risers, drones, heartbeat gaps, sub drops, crowd/source accents, or locally generated score elements. Do not hide sound design inside `music.generate`; a music bed is not a designed mix.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| Agent-native sound plan | agent-native | `references/sound-design.md` | free | high | yes |
| `ffmpeg` / `sox` procedural stems | native | binary | free | good | yes |
| `pydub` / `numpy` procedural stems | python | pkgs | free | good | yes |
| Generated music provider | public-cli/api | chosen `music.generate` provider | metered/paid | high | no |
| Downloaded/authorized music | public-cli/skill | `music.search` + `music.download` or `music-downloader` skill | varies | high when relevant | no |

Deliverables for polished edits: `sound_design.md` with stems, cue times, story function, ducking notes, and section loudness targets; separate WAV stems when generated locally; and per-section loudness checks. The ending/final act should have intentional audio shape such as escalation, silence/hold, hit/drop, source-audio reveal, or resolve when the genre calls for it. Read [`references/sound-design.md`](references/sound-design.md) for sports, commentary, trailer, and final-act patterns.

Source-audio gate: before mixing downloaded/captured clip audio with new music or narration, classify every used range as `silent_or_mute`, `ambience_keep`, `dialogue_keep`, `music_only`, `mixed_music_speech`, or `needs_separation`. Keep one foreground voice and one intentional music bed at a time. If source speech/music overlaps new narration/music, mute, duck, make the source foreground, run separation, or reject the range; do not hide the conflict behind "source texture."

Procedural-audio gate: locally generated audio is acceptable for short SFX, UI ticks, impacts, pulses, and risers, but it must not become the default main music bed for polished 60+ second videos. Prefer AI-generated music or downloaded relevant/authorized music for the main bed. Locally generated noise, risers, and whooshes must be filtered, enveloped, gain-staged, and sample-reviewed. Do not use raw Gaussian/full-band noise as a music bed or repeated transition effect; hiss/sizzle in the promoted final is a critical issue even if `silencedetect` looks normal.

### `media.analyze` — segment, label, OCR, and search footage

Use this after download/capture and before edit planning when there are many clips or when the edit depends on finding specific shots. Output should be a scene library with time ranges, keyframes, visible text, people/objects/actions where available, usability notes, and searchable tags.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| PySceneDetect `scenedetect` | public-cli | `scenedetect` + `ffmpeg` | free | high | yes |
| Google Cloud Video Intelligence | api | GCP creds | metered | sota | no |
| TwelveLabs video search/index | api | `TWELVELABS_API_KEY` + `twelvelabs` pkg | metered | sota | no |
| PaddleOCR on sampled keyframes | public-cli/python | `paddleocr` pkg or bin | free | good overall; high for visible text | yes |

Default path:

- Use PySceneDetect for general local cut detection and keyframe extraction.
- Use PaddleOCR only on sampled keyframes or subtitle regions; it complements scene detection rather than replacing it.
- Use Google Video Intelligence or TwelveLabs when you need high-quality object/person/action/text labels or semantic search over a larger footage library and the user accepts cloud processing/cost.

Found-footage gate:

- Build `scene_library.json` before cutting, with source file, start/end, resolution, visual description, shot role, motion level, faces/action/objects, source text/watermarks/subtitles, quality notes, and rejection reason when skipped.
- Create contact sheets for each source and selected ranges. Scan for countdown cards, credits, hardcoded captions, watermarks, large ranking numbers, and source title cards.
- Do not use a source just because it downloaded. Reject or crop/mask ranges that are low-resolution, static, duplicated, credit-card-heavy, subtitle-dominated, or off-theme. Use [`references/source-triage.md`](references/source-triage.md) for the rejection checklist.

### `text.transcribe` — speech → text / subtitles

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-videocaptioner` | harness-cli | harness installed | free | high | yes |
| `openai-whisper` | python | pkg + model download | free | high | yes |
| `stable-ts` / `faster-whisper` | python | pkg + model download | free | high | yes |
| AssemblyAI | api | `ASSEMBLYAI_API_KEY` | paid | sota | no |
| Deepgram | api | `DEEPGRAM_API_KEY` | paid | sota | no |
| Google Speech-to-Text | api | GCP creds | metered | high | no |

Local ASR notes:

- Preflight package checks do not prove Whisper model weights are already cached or that runtime will fit the task.
- Prefer small/base CPU models for quick local drafts; use larger models only when the user accepts the time/resource tradeoff or the machine is known to handle it.
- Use paid/cloud ASR when long recordings, diarization, timestamps, or quality requirements make local model setup a poor fit.
- Do not use Whisper `.en` models unless the user explicitly says the audio is English; `.en` models translate non-English speech into English.

### `text.caption` — design, time, render, and investigate visible captions

Use this after `text.transcribe` or agent-written script/narration timing, and before `composite.overlay` / `package.encode`. This is for viewer-facing subtitles, creator captions, trailer title hits, lyrics/karaoke, lower-third text, and other timed text that must look high-end. It is not just "burn SRT at the end."

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| Captions reference module | agent-native | `references/captions.md` | free | high | yes |
| ASS + `ffmpeg subtitles` | native | `ffmpeg` + fonts | free | high | yes |
| HyperFrames captions workflow | agent-skill | `npx skills add heygen-com/hyperframes --skill hyperframes`; Node.js + `ffmpeg` | free | high for kinetic/digital captions | yes |
| `pysubs2` ASS authoring | python | `pysubs2` pkg + `ffmpeg` | free | high | yes |
| MoviePy/Pillow transparent overlays | python | `moviepy` + `PIL` | free | good when custom layout is required | yes |

Caption discipline:

- Read [`references/captions.md`](references/captions.md) for any polished caption/subtitle/lyric/lower-third work. It defines the lifecycle, genre presets, typography, safe-zone rules, and caption doctor review.
- Keep transcription (`text.transcribe`) separate from caption design (`text.caption`). A raw SRT is source material, not a finished caption package.
- Keep caption roles separate: narration subtitle, story-beat label, chapter/title card, source translation, and lyric/karaoke. Do not turn every story beat into a narration subtitle.
- Produce `captions.source.json`, `captions_style.md`, `captions.ass` or equivalent render source, caption-heavy preview frames/contact sheet, and `captions_qc.md` for non-trivial videos.
- Prefer ASS + `ffmpeg` for deterministic subtitle burn-in on edited footage. Use the installed HyperFrames skill when captions are part of a mandatory HyperFrames workflow: digital product/site/app launch videos, UI-heavy presentations, HTML/CSS/GSAP motion compositions, karaoke, or audio-reactive typography.
- If captions are generated after an NLE master, burn them onto the exact final master and regenerate review frames from the exact promoted final path.
- Ban persistent debug-like widgets unless explicitly part of the design, such as `MISSION SUBTITLE`, `MISSION LOG`, or fixed label tags that appear on every caption.
- For voice captions, sync to voice/audio timing, not shot timing. If a narration track exists, derive subtitles from the narration transcript or ASR/forced alignment; manually timed summary captions are title cards, not voice subtitles. Verify narration duration versus voice-caption coverage.
- Honor the output-language rule across narration, subtitles, title cards, callouts, UI labels created by the agent, and CTA text. Source-language subtitles may be translated or avoided, but do not let source or instruction language leak into agent-authored viewer-facing text.
- For ASS burn-in, set `PlayResX`/`PlayResY` to the actual final render resolution or prove the scaling keeps text readable. A 1080p ASS design burned into 720p without resizing is a failure.
- If source footage has hardcoded captions, broadcast tickers, watermarks, or lower thirds, choose a safe zone, crop/mask, or replace the range. Do not stack authored subtitles over source subtitles.
- Fail the render if captions are clipped, stale, off-sync, too small, low-contrast, covering faces/action/source subtitles, missing CJK glyphs, visually mismatched to the genre, or if the video only makes sense by reading labels.

### `composite.assemble` — timeline, cuts, transitions, export

For non-trivial videos, do not assemble a final timeline until `script.storyboard` has produced `creative_direction.md`. Timeline order should follow the story/audio arc and source roles from [`references/story-structure-audio.md`](references/story-structure-audio.md), not source-file order or arbitrary clip variety.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-kdenlive` | harness-cli | Kdenlive installed | free | high | yes |
| `cli-anything-shotcut` | harness-cli | Shotcut installed | free | high | yes |
| `moviepy` | python | pkg + `ffmpeg` | free | good | yes |
| `ffmpeg-python` | python | pkg + `ffmpeg` | free | high | yes |
| `ffmpeg concat/filter_complex` | native | `ffmpeg` | free | high | yes |
| HyperFrames skill/CLI | agent-skill | installed `hyperframes` skill; Node.js + `ffmpeg` | free | high for digital/UI launch videos | yes |

HyperFrames hard gate: for digital product launches, website/product-page videos, SaaS/app demos, UI-heavy product presentations, animated feature reels, HTML/CSS/GSAP-driven motion videos, and product videos where interface motion is the main storytelling surface, load and use the installed `hyperframes` skill as the primary `composite.assemble` authoring workflow. A "HyperFrames-style" MoviePy/Pillow/ffmpeg/browser imitation is not an acceptable substitute when this gate applies.

When the HyperFrames gate applies:

- Read the installed HyperFrames skill before implementation and follow its workflow.
- Produce a real HyperFrames project/render artifact, not only a static HTML reference.
- Prove the video topic and value proposition in the first 5-8 seconds, then follow a product arc: user problem, real UI action, feature reveal, proof, outcome, and CTA/payoff.
- Use `ffmpeg`, MoviePy, or NLE tools only for source preparation, final muxing, caption burn-in when explicitly needed, or doctor investigation; they cannot replace HyperFrames as the main authoring surface.
- If HyperFrames cannot run, stop and report the blocker or ask the user to change the requirement. Do not silently fall back.

Use `remotion-best-practices` instead only when the user explicitly requires Remotion/React as the implementation surface.

For Shotcut/Kdenlive harness workflows, use the provider-boundary pattern in [`references/nle-shotcut-kdenlive.md`](references/nle-shotcut-kdenlive.md): `ffmpeg` for stable mezzanine clips, crops, speed ramps, and text-card segments when needed; the NLE harness for project/timeline/tracks/transitions/render; then `ffmpeg` for ASS burn-in if captions are post-NLE, fps/SAR/DAR/profile/color normalization, final muxing, and doctor investigation.

Assembly discipline:

- Every selected shot needs a job: setup, reveal, escalation, contrast, proof, impact, or payoff.
- For most edited pieces, introduce meaningful changes in tension, density, audio texture, title system, setting, character focus, or edit pattern often enough that the structure does not feel accidental or flat. Slow/ambient/real-time genres may justify longer holds.
- Chapter cards and title hits must advance the story beat; they cannot be decorative separators for random clips.
- Transitions and motion graphics need a story job. Repeated wipes, random kinetic text, and generic animations are failures when the viewer cannot tell the topic or why the transition happened.
- Do not assume a clean mezzanine segment contains captions, chapter cards, or later overlay stages. Choose and document one caption stage before render.
- For HyperFrames-gated genres, fail the assembly if the final render was produced by an imitation workflow instead of the installed HyperFrames skill.
- For data, UI, charts, maps, captions, and explainers, keep the frame stable unless camera motion has a documented visual purpose. Global sinusoidal crop drift, jitter, shake, or fake handheld motion over readable data/text is a critical issue requiring revision or a documented reason.
- After NLE render, check actual duration versus intended timeline duration, stream fps versus project fps, SAR/DAR, partial MP4 or missing moov, video coverage through the audio tail, and displayed content speed versus audio.
- If a render is technically valid but feels like flat montage, revise `creative_direction.md` and rebuild the timeline instead of adding more filters.

### `composite.overlay` — composite captions, watermark, picture-in-picture

Use this to apply already-designed caption/subtitle assets, watermarks, or picture-in-picture layers. For user-visible subtitles/captions, run `text.caption` first so the overlay step receives a deliberate ASS/HTML/PNG/NLE caption package instead of an ugly default SRT.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `ffmpeg -vf subtitles=...` | native | `ffmpeg` | free | high | yes |
| `moviepy` (CompositeVideoClip) | python | pkg | free | good | yes |

### `package.thumbnail` — thumbnail / social card

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-gimp` / `krita` / `inkscape` | harness-cli | installed | free | high | yes |
| `Pillow` | python | pkg | free | good | yes |
| `cairosvg` / `html2image` | python | pkg | free | good | yes |
| OpenAI GPT-Image-1 | api | `OPENAI_API_KEY` | metered | sota | no |
| Google Nano Banana | api | GCP creds | metered | high | no |
| Ideogram | api | `IDEOGRAM_API_KEY` | metered | high | no |
| Stability AI | api | `STABILITY_API_KEY` | metered | high | no |
| `ffmpeg -ss ... -frames:v 1` | native | `ffmpeg` | free | basic | yes |
| `convert` / `magick` | native | ImageMagick | free | good | yes |

### `package.encode` — final mux, codec, container

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `ffmpeg` | native | binary | free | sota | yes |

### `quality.review` — technical and editorial investigation before delivery

Run this after every render and before presenting a final file. The goal is not a binary test suite; it is an evidence-gathering pass that helps the agent inspect the exact file, understand suspicious signals, and make a contextual editorial decision.

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `ffmpeg` / `ffprobe` investigation filters | native | `ffmpeg` + `ffprobe` | free | high | yes |
| MediaInfo CLI | native | `mediainfo` | free | high | yes |
| `ffmpeg-quality-metrics` / VMAF | public-cli | `ffmpeg-quality-metrics` + `ffmpeg` | free | high with reference | yes |
| Video doctor helper | bundled-script | `scripts/video_doctor.py` + `ffmpeg`/`ffprobe` | free | high for investigation | yes |

Investigation checks:

- Use `scripts/video_doctor.py` to produce probe, caption, source, frame, tail, audio, and lint reports. Doctor reports are evidence and investigation signals, not pass/fail verdicts.
- Compare final duration against the user brief and `creative_direction.md`; if it differs, inspect whether the plan or final render is wrong before promotion.
- Verify the final viewer-facing language against the output-language rule: narration, authored captions, title cards, charts, labels, and CTAs must use the requested language, or the conversation language when no language was specified.
- FFmpeg filters: `blackdetect`, `silencedetect`, `freezedetect`, `cropdetect`, `ebur128` / `loudnorm`.
- Extract first/mid/last frames, 2s contact sheets, subtitle-heavy frames, and final-10s tail sheets; inspect visually or via OCR for text overflow, watermarks, black frames, wrong crops, frozen tails, wrong-speed tails, and audio-only tails.
- For narration videos, run the caption doctor against the narration audio and media dimensions; inspect signals about caption role, voice alignment, planned language coverage, captions extending beyond narration, mismatched ASS PlayRes, small effective font size, generic styling, or source-subtitle collision risk.
- For generated or heavily processed audio, run `scripts/video_doctor.py audio` with `--scan-path` on the task directory, listen to exported snippets, and review high-frequency/low-frequency/loudness signals. `silencedetect` and `volumedetect` passing does not mean the mix is listenable.
- When source audio is used, also pass `--sources-manifest`, `--music-manifest`, and `--sound-design` to the audio doctor so it can flag missing audio roles and export snippets around source-audio/new-music/new-narration overlap windows.
- For data/UI/chart sections, inspect short frame strips around animation segments for unintended global shake or drifting crops.
- Use VMAF/SSIM/PSNR only when a reference video exists; they are not general no-reference quality checks.
- For non-trivial videos, run the story/audio review rubric in [`references/story-structure-audio.md`](references/story-structure-audio.md): premise clarity, escalation, turning point, high point, source roles, music sections, audio events, and final payoff.
- For polished videos, run the art-direction gates in [`references/art-direction-review.md`](references/art-direction-review.md): aesthetics, captions-muted readability, final-act payoff/hook/resolve, justified card time, sparse labels, synchronized audio hits, and intentional shot repetition.
- For HyperFrames or other linter-based motion workflows, run `scripts/video_doctor.py lint` on lint logs and record whether warnings were fixed, accepted with reason, or left as blockers.
- For every promoted final, follow [`references/render-doctor.md`](references/render-doctor.md): hash the candidate/default, regenerate frames from the promoted path, update reports, and scan reports for stale paths or superseded source names.

The bundled helper is `scripts/video_doctor.py`. It has subcommands for `probe`, `captions`, `sources`, `frames`, `tail`, `audio`, and `lint`; agents must read the generated signals and then inspect the referenced evidence.

### `publish.upload` — deliver to a platform

Currently a **known gap** (see below). Agents should surface this to the user.

---

## Recipes

Recipes declare *which capabilities a workflow needs* — not the order. Choose providers per capability from the task constraints and preflight facts.

- **`ai-short`** — fully-generative social short.
  Uses: `script.storyboard`, `visual.generate`, `audio.synthesize`, `music.generate` or `music.search` / `music.download`, `sound.design` for trailer/social impact edits, `text.caption` when captions/title hits are part of the brief, `composite.assemble`, `composite.overlay`, `package.thumbnail`, `quality.review`, `package.encode`.

- **`screencast-tutorial`** — walkthrough with narration + subs.
  Uses: `script.storyboard`, `visual.capture`, `audio.capture`, `text.transcribe`, `text.caption`, `composite.overlay`, `package.thumbnail`, `quality.review`, `package.encode`.

- **`talking-head-explainer`** — webcam + b-roll + captions.
  Uses: `script.storyboard`, `visual.capture`, `video.search` / `video.download` or `visual.generate` (b-roll), `music.search` / `music.download` or `music.generate`, `sound.design` when chapter changes or emphasis hits matter, `media.analyze`, `audio.capture`, `text.transcribe`, `text.caption`, `composite.assemble`, `composite.overlay`, `package.thumbnail`, `quality.review`, `package.encode`.

- **`podcast-to-video`** — audio-first, visualize + caption.
  Uses: `script.storyboard`, `audio.capture`, `text.transcribe`, `text.caption`, `package.thumbnail`, `composite.overlay`, `composite.assemble`, `quality.review`, `package.encode`.

- **`found-footage-montage`** — source internet clips, curate, then edit.
  Uses: `script.storyboard`, `video.search`, `video.download`, `media.analyze`, `sound.design`, `text.transcribe` (optional), `text.caption` when captions/title hits are part of the edit, `composite.assemble`, `composite.overlay`, `package.thumbnail`, `quality.review`, `package.encode`.

- **`existing-song-music-video`** — build an edit around a user-specified or discovered song.
  Uses: `music.search`, `music.download`, `script.storyboard`, `video.search`, `video.download`, `media.analyze`, `sound.design` for hits/source accents that do not fight the song, `text.caption` (optional lyrics/karaoke), `composite.assemble`, `composite.overlay`, `package.thumbnail`, `quality.review`, `package.encode`.

- **`digital-product-launch`** — product/site-driven launch video with animated UI, typography, and motion graphics.
  Uses: `script.storyboard`, `visual.capture`, `audio.synthesize` (optional), `music.generate` or `music.search` / `music.download`, `sound.design` for launches with cue hits or section shifts, `text.caption` for brand-safe kinetic captions/title hits, `composite.assemble` via mandatory installed HyperFrames skill, `composite.overlay`, `package.thumbnail`, `package.encode`, `quality.review`.

---

## Known gaps

- **`publish.upload`** — no first-party or public CLI for YouTube/TikTok/Bilibili/Instagram yet. *Workaround:* instruct the user to upload manually via the web UI, or escalate to a custom script using each platform's v3 API with an OAuth token the user supplies.
- **`visual.generate` — top-tier "cinematic"** — available only via paid APIs (Runway, Kling, Seedance); local GPU/weights deployment is intentionally not part of this matrix.
- **`rights.provenance`** — no automated license/TOS/provenance verifier. *Workaround:* save `sources.json` / `music_sources.json` with URL, creator, license, intended use, attribution text, transport evidence, and quality caveats; ask the user before using unclear or restricted media. Use [`references/source-triage.md`](references/source-triage.md) for evidence levels.
- **`agent-skill.preflight`** — external agent skills may appear in this matrix before they are installed locally. *Workaround:* use the source/install table below and load the external `SKILL.md` only when that workflow is actually needed.

---

## Reference modules, external skills, and tool sources

Consult these only when the task needs the focused workflow; keep this matrix as the router and load the reference, external skill, or tool only if its workflow matches.

| Reference/tool | Use when | Source or install |
|---|---|---|
| `advanced-video-downloader` | User supplies YouTube/Bilibili/TikTok/etc. URLs and needs download, playlist handling, music/audio extraction, cookies, or transcription | `npx skills add https://github.com/jst-well-dan/skill-box --skill advanced-video-downloader` |
| `music-downloader` | Need to find/download real music, BGM, soundtrack cues, platform audio, or authorized music rather than faking a full music bed procedurally | `npx skills add https://github.com/nymbo/skills --skill music-downloader` |
| `references/story-structure-audio.md` | Non-trivial video needs a global arc, internal logic, source roles, story ups/downs, music/audio sections, or flat-montage prevention | Local reference module: [`references/story-structure-audio.md`](references/story-structure-audio.md) |
| `references/captions.md` | Any polished visible captions, subtitles, lyrics, karaoke, lower thirds, trailer title hits, or caption investigation | Local reference module: [`references/captions.md`](references/captions.md) |
| `references/source-triage.md` | Found-footage source selection, platform-origin evidence, rights/provenance fields, source rejection, and contact-sheet requirements | Local reference module: [`references/source-triage.md`](references/source-triage.md) |
| `references/nle-shotcut-kdenlive.md` | Shotcut/Kdenlive timeline work, provider boundaries, mezzanine conventions, render resilience, and known NLE failure modes | Local reference module: [`references/nle-shotcut-kdenlive.md`](references/nle-shotcut-kdenlive.md) |
| `references/sound-design.md` | Trailer hits, risers, sports accents, commentary mix changes, final-act audio shape, and section loudness review | Local reference module: [`references/sound-design.md`](references/sound-design.md) |
| `references/art-direction-review.md` | Genre-specific naive-output traps, contact-sheet review, captions-muted review, and art gates before promotion | Local reference module: [`references/art-direction-review.md`](references/art-direction-review.md) |
| `references/render-doctor.md` | Final-path doctor workflow, probe/frame/tail/caption/source investigation, promotion discipline, and stale-report checks | Local reference module: [`references/render-doctor.md`](references/render-doctor.md) |
| `scripts/video_doctor.py` | Non-binary investigation helper for media facts, review frames, tail signals, sources, captions, audio listenability signals, and procedural-audio evidence | Local script: [`scripts/video_doctor.py`](scripts/video_doctor.py) |
| `storyboard-creation` | Need shot grammar, camera angles, storyboard panels, continuity, or animatic planning | `pnpm dlx add-skill https://github.com/inference-sh/skills/tree/HEAD/guides/video/storyboard-creation` |
| `remotion-best-practices` | Need to implement the storyboard as Remotion code | `npx skills add https://github.com/remotion-dev/skills --skill remotion-best-practices`; SKILL.md: <https://github.com/remotion-dev/skills/blob/main/skills/remotion/SKILL.md> |
| `hyperframes` | Mandatory for website/product-page videos, digital product launches, SaaS/app demos, UI-heavy product presentations, animated feature reels, and whole-video HTML/CSS/GSAP motion compositions | Installed local skill. If missing in a future environment, install it with `npx skills add heygen-com/hyperframes --skill hyperframes`; do not substitute another renderer when this skill is mandatory. Captions reference: <https://skills.sh/heygen-com/hyperframes/captions> |
| `ffmpeg-quality-metrics` | Need VMAF/SSIM/PSNR against a reference video | `pipx install ffmpeg-quality-metrics`; source: <https://github.com/slhck/ffmpeg-quality-metrics> |

---

## Agent guidance

- **Run the preflight block once**, then consult the cached result when picking providers.
- **For non-trivial videos, start with `creative_direction.md`.** Use the story/audio reference module to define the whole arc before acquisition and assembly: premise, emotional curve, audio arc, cut-density curve, source roles, turning point, climax, and payoff.
- **Language rule:** if the user specifies a video language, use it. Otherwise use the conversation language for all agent-authored narration, captions, titles, labels, and CTAs; source-language text must be translated, avoided, or explained when it matters.
- **For internet footage, run `video.search` before `video.download`** unless the user already supplied URLs. Keep provenance metadata with every source file.
- **For found-footage edits, build `scene_library.json` before cutting.** Use source triage and contact sheets to reject weak, static, card-heavy, subtitle-dominated, or off-theme footage.
- **For existing music, run `music.search` before `music.download`** unless the user already supplied a URL/local file. Verify the song version and listen for dialogue/SFX bleed before beat analysis or editing.
- **For polished music beds, prefer real music.** Use AI-generated music or downloaded relevant/authorized music as the main bed unless the brief calls for ambient/source-audio-led work. Procedural audio is for SFX/accent stems, not a cheap replacement for a full soundtrack.
- **For high-energy edits, run `sound.design` as a separate pass.** A music bed alone is not a designed mix; create cue times, stems, ducking notes, and section loudness targets.
- **For visible captions, use `text.caption` as its own design pass.** Do not hand off raw SRT to `composite.overlay` and call it done. Use the captions reference module for genre style, grouping, safe placement, font/glyph checks, hard exits, and caption-heavy preview frames.
- **For narrated work, captions must follow the voice.** Generate or align subtitles from the final narration/audio, then run `scripts/video_doctor.py captions` against the exact final dimensions and narration file. Read the doctor signals and inspect frames/audio before deciding what to revise. Summary captions belong in a separate title/callout style.
- **For subtitle/caption localization, translate directly as agent work** unless the user explicitly requires a specific translation service, offline translation, or human/legal review. Preserve timestamps, maintain names/terms consistently, and verify CJK glyph rendering in overlays.
- **For non-trivial work, do `script.storyboard` before acquisition/generation**, usually as agent-native planning. Load an external storyboard skill only when its focused format is worth the extra install/context. Do not replace the global story/audio plan with a list of clips.
- **For digital product/site/app launch videos, use HyperFrames under `composite.assemble`.** When the genre is a UI-heavy product launch, SaaS/app demo, product presentation, animated feature reel, or whole-video HTML/CSS/GSAP composition, HyperFrames is mandatory. Do not use MoviePy/Pillow/ffmpeg, a static HTML mock, or a "HyperFrames-style" imitation as the primary authoring surface.
- **Using the right tool is not enough.** The final must still satisfy brief compliance, topic clarity, duration, story arc, caption sync, audio listenability, and stable-motion review.
- **For final audio, listen and run the audio doctor.** Use `scripts/video_doctor.py audio <final> <qc/audio> --scan-path <task-dir>` for polished edits, then inspect the snippets. A technically valid track can still fail if it sounds like hiss, test tones, synthetic pulse wallpaper, or repeated boom hits.
- **Use Remotion guidance only for code-driven motion graphics.** Do not install it for ordinary cuts, overlays, or NLE work.
- **Choose Shotcut, Kdenlive, MoviePy, or raw `ffmpeg` by edit complexity and availability.** NLE harnesses fit timeline-heavy edits; MoviePy/ffmpeg fit deterministic programmatic cuts and overlays.
- **When using Shotcut/Kdenlive, keep provider boundaries explicit.** Preprocess stable mezzanine/source clips with `ffmpeg`, author the timeline in the NLE, then use `ffmpeg` for post-NLE captions, muxing, normalization, and doctor evidence as needed.
- **Prefer `--json`** for harness CLI output when chaining tools.
- **Promote only verified final paths.** Probe the exact file being delivered, regenerate review frames from it, hash it, and make reports refer to that same path.
- **Doctor helpers are not verdicts.** A clean doctor report can still hide an editorial failure, and a strong doctor signal can be acceptable with context. Read the evidence and document the judgment.
- **Independent review must seek defects.** A review that only repeats ffprobe/black/freeze/silence checks is incomplete; it must cite visual/caption/audio/story risks from exact-final evidence before giving a verdict.
- **Escalate explicitly.** When a paid API would materially improve quality, use the suggest-to-user template. Do not silently burn credits.
- **Recipes ≠ order.** A recipe says what's needed; pick a sensible order for the specific task. Most videos should transcribe *after* the final cut, not before; screencasts often capture audio + video simultaneously.
- **Workspace discipline.** Keep all intermediate assets under one directory so cross-tool references stay stable.
