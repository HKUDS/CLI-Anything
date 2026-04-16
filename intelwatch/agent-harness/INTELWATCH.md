# Intelwatch CLI Harness

This harness integrates the Node.js `intelwatch` CLI tool with the CLI-Anything framework. 
Because `intelwatch` is an `npx` (Node.js) tool, this harness acts as a thin wrapper that relays command-line arguments to `npx intelwatch`.

## Architecture
- **Language**: Python (`cli-anything-intelwatch`) wrapping Node.js (`npx intelwatch`).
- **Dependencies**: Requires `click` (Python) and `node`/`npx` (System).

## Setup
Install the python harness:
```bash
pip install -e .
```

Run:
```bash
cli-anything-intelwatch profile kpmg.fr --ai
```
