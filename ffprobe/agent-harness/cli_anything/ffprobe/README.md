# cli-anything · FFprobe

Structured media file analysis via ffprobe (part of FFmpeg).

## Install
```bash
cd /tmp/CLI-Anything/ffprobe/agent-harness
pip install -e .
```

## Quick Start
```bash
# Interactive REPL
python -m cli_anything.ffprobe

# Single commands
python -m cli_anything.ffprobe analyze info video.mp4
python -m cli_anything.ffprobe analyze streams video.mp4
python -m cli_anything.ffprobe analyze codec video.mp4
python -m cli_anything.ffprobe analyze chapters video.mkv
python -m cli_anything.ffprobe analyze packets video.mp4 --count 100
python -m cli_anything.ffprobe analyze frames video.mp4 --count 25
python -m cli_anything.ffprobe analyze thumbnails video.mp4
python -m cli_anything.ffprobe batch analyze *.mp4
python -m cli_anything.ffprobe compare video1.mp4 video2.mp4

# JSON output
python -m cli_anything.ffprobe --json analyze info video.mp4
```

## Requirements
- Python >= 3.10
- ffmpeg (`apt install ffmpeg`)

## License
MIT
