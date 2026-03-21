# cli-anything · Tesseract

## Overview

This harness wraps **Tesseract** (tesseract) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install tesseract

# Install the harness
cd /tmp/CLI-Anything/tesseract/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-tesseract

# Or use one-shot commands
cli-anything-tesseract --json <command>
```

## Available Commands

- `ocr <image>`
- `ocr <image> --lang L`
- `langs`
- `pdf <image>`
- `batch <images...> --output-dir D`

## Architecture

The harness uses subprocess to call tesseract, providing
a session layer with undo/redo and structured output.

## License

MIT
