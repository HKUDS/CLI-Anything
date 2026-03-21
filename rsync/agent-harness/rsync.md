# cli-anything · Rsync

## Overview

This harness wraps **Rsync** (rsync) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install rsync

# Install the harness
cd /tmp/CLI-Anything/rsync/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-rsync

# Or use one-shot commands
cli-anything-rsync --json <command>
```

## Available Commands

- `sync <src> <dst>`
- `dry-run <src> <dst>`
- `mirror <src> <dst>`
- `stats <src> <dst>`

## Architecture

The harness uses subprocess to call rsync, providing
a session layer with undo/redo and structured output.

## License

MIT
