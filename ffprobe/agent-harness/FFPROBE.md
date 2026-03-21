# FFprobe CLI-Anything Harness — Architecture SOP

## Overview
Structured media file analysis via ffprobe (part of FFmpeg suite).

## Directory Layout
```
ffprobe/agent-harness/
├── setup.py                          # Package setup
├── FFPROBE.md                        # This file
└── cli_anything/
    └── ffprobe/
        ├── __init__.py
        ├── __main__.py               # Entry point
        ├── ffprobe_cli.py            # Click CLI with REPL
        ├── README.md
        ├── core/
        │   ├── __init__.py
        │   ├── session.py            # Session with undo/redo
        │   └── analyze.py            # ffprobe subprocess wrappers
        ├── utils/
        │   ├── __init__.py
        │   └── repl_skin.py          # Terminal UI styling
        ├── skills/
        │   └── SKILL.md              # Skill documentation
        └── tests/
            ├── __init__.py
            └── test_core.py          # Unit tests
```

## Core Module: `analyze.py`
All analysis functions call `ffprobe` via `subprocess.run()` with `-print_format json` for structured output.

| Function | ffprobe args | Returns |
|----------|-------------|---------|
| `analyze_info(file)` | `-show_format -show_streams` | Full JSON dict |
| `analyze_streams(file)` | `-show_format -show_streams` | List of stream dicts |
| `analyze_format(file)` | `-show_format -show_streams` | Format dict |
| `analyze_codec(file)` | `-show_format -show_streams` | List of codec details |
| `analyze_chapters(file)` | `-show_format -show_streams -show_chapters` | List of chapter dicts |
| `analyze_packets(file, count)` | `-show_packets -read_intervals` | List of packet dicts |
| `analyze_frames(file, count)` | `-show_frames -read_intervals` | List of frame dicts |
| `analyze_thumbnails(file)` | `-show_frames -select_streams v:0` | List of keyframe dicts |
| `batch_analyze(files)` | Multiple calls | List of per-file results |
| `compare(f1, f2)` | Two info probes | Comparison dict |

## Session Model
- `Session` class tracks a JSON project with undo/redo stacks (max 50)
- `snapshot()` before mutations; `undo()`/`redo()` to navigate history
- `save_session()` writes JSON with file locking

## CLI Design
- Click groups: `analyze`, `batch`, `compare`, `status`, `repl`
- `--json` flag for machine-readable output
- REPL with prompt-toolkit, command history, auto-suggest
- `handle_error` decorator catches exceptions consistently

## Testing
```bash
cd /tmp/CLI-Anything/ffprobe/agent-harness
python3 -m pytest cli_anything/ffprobe/tests/ -v
```
