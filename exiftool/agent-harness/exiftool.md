# cli-anything · ExifTool

## Overview

This harness wraps **ExifTool** (exiftool) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install exiftool

# Install the harness
cd /tmp/CLI-Anything/exiftool/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-exiftool

# Or use one-shot commands
cli-anything-exiftool --json <command>
```

## Available Commands

- `info <file>`
- `set <file> --tag T --value V`
- `remove <file>`
- `gps <file>`
- `dates <file>`
- `copy <src> <dst>`

## Architecture

The harness uses subprocess to call exiftool, providing
a session layer with undo/redo and structured output.

## License

MIT
