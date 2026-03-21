# cli-anything · Docker

## Overview

This harness wraps **Docker** (docker) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install docker

# Install the harness
cd /tmp/CLI-Anything/docker/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-docker

# Or use one-shot commands
cli-anything-docker --json <command>
```

## Available Commands

- `ps`
- `run <image>`
- `stop <id>`
- `logs <id>`
- `exec <id> --cmd C`
- `images`
- `pull <name>`
- `build --path P --tag T`
- `rm <id>`
- `volumes`
- `networks`
- `info`

## Architecture

The harness uses subprocess to call docker, providing
a session layer with undo/redo and structured output.

## License

MIT
