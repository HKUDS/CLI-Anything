---
name: cli-hub-matrix-video-creation
description: >-
  Curated multi-CLI matrix for generating, editing, captioning, and packaging
  videos across CLI-Anything harnesses, public CLIs, Python libraries, and cloud APIs.
---

# Video Creation Matrix

This matrix covers end-to-end video production. Each stage lists a **primary goal**, **CLI tools** from the matrix, and **alternative approaches** (Python libraries, cloud APIs, native commands). Pick the approach that fits your current environment and constraints.

## Install

```bash
# Install the whole matrix
cli-hub matrix install video-creation

# Inspect what it includes
cli-hub matrix info video-creation
```

## Stages

### 1. AI Video Generation
**Goal:** Generate video clips from text prompts or reference images

| Approach | Options |
|----------|---------|
| CLI tools | `generate-veo-video` (Google Veo 3.1), `jimeng` (ByteDance Dreamina) |
| Python libs | `replicate` (Runway, Kling), `diffusers` |
| Cloud APIs | Runway API, Kling API, Pika API |

### 2. Screen/Cam Capture
**Goal:** Record screen activity, webcam, or application windows to video files

| Approach | Options |
|----------|---------|
| CLI tools | `cli-anything-openscreen` |
| Python libs | `pyautogui` + `cv2`, `mss` |
| Native cmds | `ffmpeg -f x11grab` (Linux), `screencapture` (macOS) |

### 3. Audio Capture/Edit
**Goal:** Record, clean, trim, normalize, and process audio tracks

| Approach | Options |
|----------|---------|
| CLI tools | `cli-anything-audacity` |
| Python libs | `pydub`, `soundfile`, `librosa`, `noisereduce` |
| Native cmds | `sox`, `ffmpeg` |

### 4. Voice/TTS
**Goal:** Generate speech audio from text for narration or voiceover

| Approach | Options |
|----------|---------|
| CLI tools | `minimax-cli`, `elevenlabs` |
| Python libs | `TTS` (coqui-ai), `pyttsx3`, `edge-tts` |
| Cloud APIs | Google Cloud TTS, Amazon Polly, Azure Speech |

### 5. Music/BGM Generation
**Goal:** Generate background music or sound effects from prompts

| Approach | Options |
|----------|---------|
| CLI tools | `minimax-cli`, `suno` |
| Python libs | `audiocraft` (Meta MusicGen), `stable-audio-tools` |
| Cloud APIs | Suno API, Udio API |

### 6. NLE Editing
**Goal:** Assemble video/audio clips on a timeline, add transitions, and export the final cut

| Approach | Options |
|----------|---------|
| CLI tools | `cli-anything-kdenlive`, `cli-anything-shotcut` |
| Python libs | `moviepy`, `ffmpeg-python` |
| Native cmds | `ffmpeg concat/filter_complex` |

### 7. Captions/Subtitles
**Goal:** Transcribe speech, generate subtitles (SRT/ASS), optionally translate, and burn into video

| Approach | Options |
|----------|---------|
| CLI tools | `cli-anything-videocaptioner` |
| Python libs | `whisper` (openai-whisper), `pysrt`, `stable-ts` |
| Cloud APIs | Google Speech-to-Text, AssemblyAI, Deepgram |
| Native cmds | `ffmpeg -vf subtitles=subs.srt` |

### 8. Thumbnail
**Goal:** Create a thumbnail image or social card for the video

| Approach | Options |
|----------|---------|
| CLI tools | `cli-anything-gimp` |
| Python libs | `Pillow`, `cairosvg`, `html2image` |
| Cloud APIs | Google Nano Banana, OpenAI GPT-Image-1, Ideogram API, Stability AI image generation |
| Native cmds | `ffmpeg -ss 00:01:00 -frames:v 1 thumb.png`, ImageMagick `convert` |

## Discovering Additional Tools

Before starting a stage, search for skills and tools that may already be available:

```bash
# Search for Claude Code skills by keyword
npx skills search "subtitle"
npx skills search "video editing"
npx skills search "text-to-speech"

# Check what CLI-Hub has available
cli-hub search caption
cli-hub search audio
cli-hub search video

# Check for Python packages already installed
pip list 2>/dev/null | grep -iE "whisper|moviepy|pydub|Pillow"

# Check for native tools on PATH
which ffmpeg sox convert magick 2>/dev/null
```

When a stage's CLI tool is not installed and installing it is impractical, fall back to:
1. A Python library you can `pip install` in seconds
2. A native command already on the system (`ffmpeg`, `sox`, `ImageMagick`)
3. A cloud API if credentials are available in the environment

## Operating Pattern

1. The controller agent drafts the script, shot list, and prompt variants.
2. For each stage, check what tools are available (installed CLIs, Python libs on PATH, API keys in env).
3. Pick the simplest adequate tool for each stage -- a full CLI harness is not always needed.
4. Generate/capture media, assemble the edit, add captions, and create the thumbnail.
5. Keep all intermediate assets under a single workspace directory so sources stay linkable across tools.

## Example Flow

```bash
# 1) Discover what is available
cli-hub matrix info video-creation
npx skills search "video"
which ffmpeg && echo "ffmpeg available"

# 2) Generate hero clips
cli-hub launch generate-veo-video --help
# or: python -c "import replicate; ..."

# 3) Generate narration
cli-hub launch elevenlabs --help
# or: pip install edge-tts && edge-tts --text "Hello" --write-media narration.mp3

# 4) Assemble edit
cli-anything-kdenlive --json project new -o edit.json
cli-anything-kdenlive --json --project edit.json timeline add-track --type video
# or: python -c "from moviepy.editor import *; ..."

# 5) Add subtitles
cli-anything-videocaptioner process cut.mp4 --asr bijian --subtitle-mode hard -o captioned.mp4
# or: pip install openai-whisper && python -c "import whisper; model = whisper.load_model('base'); ..."

# 6) Create thumbnail
cli-anything-gimp --json project new -o thumb.json
# or: python -c "from PIL import Image, ImageDraw, ImageFont; ..."
```

## Agent Guidance

- **Check before installing**: If `whisper` is already pip-installed, use it directly instead of installing `cli-anything-videocaptioner` for a simple transcription task.
- **Match complexity to task**: A one-line `ffmpeg` command may beat a full CLI harness for simple operations like extracting a thumbnail or concatenating two clips.
- **Search for skills first**: Before each stage, run `npx skills search "<keyword>"` with the stage's topic to discover relevant skills you may not know about.
- **Prefer `--json` for harness CLIs**: When chaining harness CLI outputs to the next tool, use `--json` for structured data.
- **Use env vars for API routing**: Check for `GOOGLE_CLOUD_PROJECT`, `ELEVENLABS_API_KEY`, `MINIMAX_API_KEY`, etc. before choosing between CLI and direct API approaches.
- The matrix assumes a controller agent (Claude Code, Codex, OpenClaw, etc.) is doing the planning and orchestration.
