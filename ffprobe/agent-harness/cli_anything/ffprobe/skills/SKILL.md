# FFprobe Skill

## Category
media

## Description
Structured media file analysis via ffprobe (part of FFmpeg). Provides JSON-based probing of media files for format, streams, codecs, chapters, packets, and frames.

## Requirements
- `ffmpeg` must be installed (`apt install ffmpeg`)

## Commands

### Analyze
- `analyze info <file>` — Full probe with JSON output
- `analyze streams <file>` — List streams only
- `analyze format <file>` — Show container format info
- `analyze codec <file>` — Show codec details for all streams
- `analyze chapters <file>` — List chapters
- `analyze packets <file> [--count N]` — Show packet info
- `analyze frames <file> [--count N]` — Show frame info
- `analyze thumbnails <file>` — Extract thumbnail keyframe timestamps

### Batch
- `batch analyze <files...>` — Analyze multiple files

### Compare
- `compare <file1> <file2>` — Compare two media files side by side

## Usage
```bash
python -m cli_anything.ffprobe analyze info video.mp4
python -m cli_anything.ffprobe analyze streams video.mp4
python -m cli_anything.ffprobe analyze codec video.mp4
python -m cli_anything.ffprobe analyze chapters video.mkv
python -m cli_anything.ffprobe analyze packets video.mp4 --count 100
python -m cli_anything.ffprobe analyze frames video.mp4 --count 25
python -m cli_anything.ffprobe analyze thumbnails video.mp4
python -m cli_anything.ffprobe batch analyze *.mp4
python -m cli_anything.ffprobe compare video1.mp4 video2.mp4
```

## Architecture
- Core analysis functions in `core/analyze.py` call ffprobe via subprocess
- All output uses `-print_format json` for structured parsing
- Session management with undo/redo in `core/session.py`
- REPL with prompt-toolkit for interactive use
