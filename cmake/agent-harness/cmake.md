# cli-anything · CMake

## Overview

This harness wraps **CMake** (cmake) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install cmake

# Install the harness
cd /tmp/CLI-Anything/cmake/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-cmake

# Or use one-shot commands
cli-anything-cmake --json <command>
```

## Available Commands

- `configure <src> --build-dir D`
- `build <dir>`
- `install <dir>`
- `clean <dir>`
- `variables <dir>`
- `targets <dir>`

## Architecture

The harness uses subprocess to call cmake, providing
a session layer with undo/redo and structured output.

## License

MIT
