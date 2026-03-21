# cli-anything · Pandoc

## Overview

This harness wraps **Pandoc** (pandoc) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install pandoc

# Install the harness
cd /tmp/CLI-Anything/pandoc/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-pandoc

# Or use one-shot commands
cli-anything-pandoc --json <command>
```

## Available Commands

- `convert <input> <output>`
- `info <file>`
- `formats`
- `metadata <file>`
- `toc <file>`

## Architecture

The harness uses subprocess to call pandoc, providing
a session layer with undo/redo and structured output.

## License

MIT
