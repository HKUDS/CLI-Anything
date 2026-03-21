# cli-anything · FFmpeg

## Overview

This harness wraps **FFmpeg** (ffmpeg) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install ffmpeg

# Install the harness
cd /tmp/CLI-Anything/ffmpeg/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-ffmpeg

# Or use one-shot commands
cli-anything-ffmpeg --json <command>
```

## Available Commands

- `convert <in> <out>`
- `extract-audio <in> <out>`
- `trim <in> <out> --start S --duration D`
- `concat <inputs...> --output O`
- `scale <in> <out> --width W --height H`
- `thumbnail <in> <out> --time T`
- `info <file>`

## Architecture

The harness uses subprocess to call ffmpeg, providing
a session layer with undo/redo and structured output.

## License

MIT
