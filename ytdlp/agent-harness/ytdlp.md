# cli-anything · yt-dlp

## Overview

This harness wraps **yt-dlp** (yt-dlp) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install yt-dlp

# Install the harness
cd /tmp/CLI-Anything/ytdlp/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-ytdlp

# Or use one-shot commands
cli-anything-ytdlp --json <command>
```

## Available Commands

- `download <url>`
- `info <url>`
- `formats <url>`
- `search <query>`
- `playlist <url>`
- `subtitles <url>`

## Architecture

The harness uses subprocess to call yt-dlp, providing
a session layer with undo/redo and structured output.

## License

MIT
