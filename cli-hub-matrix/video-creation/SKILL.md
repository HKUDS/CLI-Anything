---
name: cli-hub-matrix-video-creation
description: >-
  Capability-based multi-tool matrix for video production. Agents pick providers
  (CLI-Anything harnesses, public CLIs, Python libs, native binaries, cloud APIs)
  per capability rather than marching through fixed stages.
---

# Video Creation Matrix (v3 — capability-based)

This matrix describes **capabilities** the agent can compose on demand — not a fixed pipeline. A "video creation" workflow picks a *recipe* (which capabilities it needs) and, per capability, picks a *provider* using the decision rubric below.

Schema: [`docs/cli-matrix/matrix_registry.schema.md`](../../docs/cli-matrix/matrix_registry.schema.md).

## Install (installable portion)

```bash
cli-hub matrix install video-creation   # installs the harness + public CLIs
cli-hub matrix info    video-creation   # inspect providers & recipes
```

Not everything in this matrix is a CLI. Cloud APIs, Python packages, and native binaries are first-class providers too.

---

## Decision rubric (agent: apply per capability)

1. **Available & adequate** — prefer providers whose `requires` is already satisfied, ranked by `quality_tier` then inverse `cost_tier`.
2. **Free-to-install** — next prefer Python libs or native binaries that install in seconds without credentials.
3. **Harness / public CLI install** — install a first-party or public CLI when the task warrants it.
4. **Paid API escalation** — only when lower tiers can't meet quality, env already holds the key, **or** the user explicitly consents. Never silently call a paid API.

Offline context? Filter to `offline: true` providers only.

---

## Preflight (run once per session, cache the result)

```bash
cli-hub list --json
python - <<'PY'
import importlib.util
for m in ("moviepy","whisper","pydub","PIL","replicate","edge_tts","audiocraft","pysrt","TTS"):
    print(m, importlib.util.find_spec(m) is not None)
PY
for b in ffmpeg sox convert magick screencapture; do command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"; done
for e in RUNWAY_API_KEY KLING_API_KEY SEEDANCE_API_KEY ELEVENLABS_API_KEY MINIMAX_API_KEY \
         OPENAI_API_KEY GOOGLE_CLOUD_PROJECT ASSEMBLYAI_API_KEY DEEPGRAM_API_KEY \
         SUNO_API_KEY UDIO_API_KEY IDEOGRAM_API_KEY STABILITY_API_KEY; do
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

- *To enable cinematic AI video via Runway Gen-4, please set `RUNWAY_API_KEY`. Cost: ~$0.05/sec. Quality: sota. Reply 'skip' to fall back to `generate-veo-video` or local `diffusers`.*
- *To enable ByteDance Seedance video generation, please set `SEEDANCE_API_KEY`. Cost: metered per-clip. Quality: sota for realistic motion. Reply 'skip' to fall back to `jimeng` (Dreamina) which shares the ByteDance model family.*

---

## Capabilities

### `visual.generate` — produce a video clip from prompt/reference

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `generate-veo-video` | public-cli | `generate-veo` bin + Google creds | metered | high | no |
| `jimeng` | public-cli | `dreamina` bin + Dreamina login | metered | high | no |
| Runway Gen-4 | api | `RUNWAY_API_KEY` | paid | sota | no |
| Kling | api | `KLING_API_KEY` | paid | high | no |
| Pika | api | `PIKA_API_KEY` | paid | good | no |
| Seedance | api | `SEEDANCE_API_KEY` | paid | sota | no |
| `replicate` | python | `REPLICATE_API_TOKEN` | metered | varies | no |
| `diffusers` (SVD/AnimateDiff) | python | GPU + weights | free | basic-good | yes |

### `visual.capture` — record screen / webcam / window

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-openscreen` | harness-cli | harness installed | free | high | yes |
| `cli-anything-obs-studio` | harness-cli | OBS installed | free | high | yes |
| `ffmpeg -f x11grab` / `avfoundation` | native | `ffmpeg` | free | high | yes |
| `screencapture` | native | macOS | free | high | yes |
| `mss` / `pyautogui` + `cv2` | python | pkgs | free | good | yes |

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
| Amazon Polly / Azure Speech | api | AWS/Azure creds | metered | good | no |
| `edge-tts` | python | pkg | free | good | no |
| `TTS` (coqui) | python | pkg + weights | free | good | yes |
| `pyttsx3` | python | pkg | free | basic | yes |

### `audio.music` — music / BGM generation

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `suno` | public-cli | bin + Suno account | metered | sota | no |
| `minimax-cli` | public-cli | bin + MiniMax key | metered | high | no |
| Udio | api | `UDIO_API_KEY` | paid | sota | no |
| `audiocraft` (MusicGen) | python | pkg + weights | free | good | yes |
| `stable-audio-tools` | python | pkg + weights | free | good | yes |

### `text.transcribe` — speech → text / subtitles

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-videocaptioner` | harness-cli | harness installed | free-metered | high | partial |
| `openai-whisper` | python | pkg + weights | free | high | yes |
| `stable-ts` / `faster-whisper` | python | pkg | free | high | yes |
| AssemblyAI | api | `ASSEMBLYAI_API_KEY` | paid | sota | no |
| Deepgram | api | `DEEPGRAM_API_KEY` | paid | sota | no |
| Google Speech-to-Text | api | GCP creds | metered | high | no |

### `text.translate` — subtitle/caption translation

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| OpenAI / Claude | api | model key | metered | sota | no |
| DeepL | api | `DEEPL_API_KEY` | metered | sota | no |
| `argos-translate` | python | pkg + lang packs | free | good | yes |

### `composite.assemble` — timeline, cuts, transitions, export

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-kdenlive` | harness-cli | Kdenlive installed | free | high | yes |
| `cli-anything-shotcut` | harness-cli | Shotcut installed | free | high | yes |
| `moviepy` | python | pkg + `ffmpeg` | free | good | yes |
| `ffmpeg-python` | python | pkg + `ffmpeg` | free | high | yes |
| `ffmpeg concat/filter_complex` | native | `ffmpeg` | free | high | yes |

### `composite.overlay` — burn subs, watermark, picture-in-picture

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `ffmpeg -vf subtitles=...` | native | `ffmpeg` | free | high | yes |
| `moviepy` (CompositeVideoClip) | python | pkg | free | good | yes |
| NLE harnesses (via assemble) | harness-cli | installed | free | high | yes |

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
| NLE export (via `composite.assemble`) | harness-cli | installed | free | high | yes |

### `publish.upload` — deliver to a platform

Currently a **known gap** (see below). Agents should surface this to the user.

---

## Recipes

Recipes declare *which capabilities a workflow needs* — not the order. Apply the decision rubric per capability.

- **`ai-short`** — fully-generative social short.
  Uses: `visual.generate`, `audio.synthesize`, `audio.music`, `composite.assemble`, `composite.overlay`, `package.thumbnail`, `package.encode`.

- **`screencast-tutorial`** — walkthrough with narration + subs.
  Uses: `visual.capture`, `audio.capture`, `text.transcribe`, `composite.overlay`, `package.thumbnail`, `package.encode`.

- **`talking-head-explainer`** — webcam + b-roll + captions.
  Uses: `visual.capture`, `visual.generate` (b-roll), `audio.capture`, `text.transcribe`, `composite.assemble`, `composite.overlay`, `package.thumbnail`, `package.encode`.

- **`podcast-to-video`** — audio-first, visualize + caption.
  Uses: `audio.capture`, `text.transcribe`, `package.thumbnail`, `composite.overlay`, `composite.assemble`, `package.encode`.

---

## Known gaps

- **`publish.upload`** — no first-party or public CLI for YouTube/TikTok/Bilibili/Instagram yet. *Workaround:* instruct the user to upload manually via the web UI, or escalate to a custom script using each platform's v3 API with an OAuth token the user supplies.
- **`visual.generate` — top-tier "cinematic"** — available only via paid APIs (Runway, Kling, Seedance); local `diffusers` output is basic-to-good, not sota.

---

## Agent guidance

- **Run the preflight block once**, then consult the cached result when picking providers.
- **Search for skills per capability** before starting: `npx skills search "<capability hints>"` (hints are in `matrix_registry.json`).
- **Prefer `--json`** for harness CLI output when chaining tools.
- **Escalate explicitly.** When a paid API would materially improve quality, use the suggest-to-user template. Do not silently burn credits.
- **Recipes ≠ order.** A recipe says what's needed; pick a sensible order for the specific task. Most videos should transcribe *after* the final cut, not before; screencasts often capture audio + video simultaneously.
- **Workspace discipline.** Keep all intermediate assets under one directory so cross-tool references stay stable.
