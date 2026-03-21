# cli-anything · Nmap

## Overview

This harness wraps **Nmap** (nmap) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install nmap

# Install the harness
cd /tmp/CLI-Anything/nmap/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-nmap

# Or use one-shot commands
cli-anything-nmap --json <command>
```

## Available Commands

- `scan <target>`
- `scan <target> --ports P`
- `scan <target> --top-ports N`
- `os-detect <target>`
- `service <target>`
- `ping <target>`

## Architecture

The harness uses subprocess to call nmap, providing
a session layer with undo/redo and structured output.

## License

MIT
