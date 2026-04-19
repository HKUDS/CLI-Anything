# VideoCaptioner CLI

AI-powered video captioning tool that mirrors the stable `videocaptioner`
backend surface.

## Architecture

- **Subprocess backend** delegates to the production `videocaptioner` CLI (`pip install videocaptioner`)
- **Click** provides the CLI framework with subcommand groups and REPL
- **JSON output mode** (`--json`) for agent consumption
- **Free features included**: bijian ASR (Chinese/English), Bing/Google translation

## Pipeline

```
Audio/Video → ASR Transcription → Subtitle Splitting → LLM Optimization → Translation → Video Synthesis
                  (bijian/whisper)      (semantic)         (fix errors)      (38 languages)  (video synthesis)
```

## Install

```bash
python3.12 -m pip install videocaptioner click prompt-toolkit
```

VideoCaptioner `1.4.1` currently declares `Requires-Python: >=3.10,<3.13`.
Use Python `3.10`-`3.12`; Python `3.13+` is not a safe default for this stack.

## Run

```bash
# One-shot: transcribe a Chinese video and add English subtitles
cli-anything-videocaptioner process video.mp4 --asr bijian --translator bing --target-language en --subtitle-mode hard

# Transcribe only
cli-anything-videocaptioner transcribe video.mp4 --asr bijian -o output.srt

# Translate existing subtitles
cli-anything-videocaptioner subtitle input.srt --translator google --target-language ja

# Burn subtitles into a video
cli-anything-videocaptioner synthesize video.mp4 -s sub.srt --subtitle-mode hard

# Block a hard-burn if the subtitle file drifted too far from the approved script
cli-anything-videocaptioner synthesize video.mp4 -s sub.srt \
  --subtitle-mode hard \
  --review-script approved_script.txt

# Review a subtitle file and render a single preview frame before final export
cli-anything-videocaptioner review sub.srt \
  --script approved_script.txt \
  --preview-video video.mp4 \
  --preview-output review_5s.png

# JSON output mode (for agent consumption)
cli-anything-videocaptioner --json transcribe video.mp4 --asr bijian

# Interactive REPL
cli-anything-videocaptioner
```

## Backend compatibility

The harness intentionally tracks the stable `videocaptioner` backend interface.
As of backend `1.4.x`, `synthesize` exposes subtitle mode, quality, and output
path controls, while styling is driven by the subtitle asset itself rather than
runtime style flags.

Use the `review` command, or `synthesize --review-script`, to catch subtitle
drift before hard-burning a permanent delivery.

## Coverage

| Feature | Commands |
|---------|----------|
| Transcription | 4 ASR engines, auto language detection, word timestamps |
| Subtitle Processing | Split + optimize + translate, 3 translators, 38 languages |
| Video Synthesis | Soft/hard subtitles, 4 quality levels |
| Styles | Backend-version dependent; the harness reports availability |
| Utilities | Config management, style listing, video download |
