# cli-anything-ghidra

A stateful command-line interface for binary analysis, built on Ghidra. Designed for AI agents and security researchers who need to analyze binaries, decompile functions, and extract symbols without a GUI.

## Features

- **Auto-Analysis** — Run Ghidra's auto-analysis on binaries
- **Decompilation** — Decompile specific functions or all functions to C
- **String Extraction** — Extract strings with addresses
- **Import/Export Listing** — List imported and exported functions
- **Function Listing** — List all functions with addresses and sizes
- **Cross-References** — Show cross-references to any address
- **Symbol Listing** — List all symbols
- **Header Info** — Show PE/ELF header information
- **Script Execution** — Run custom Ghidra scripts
- **Project Management** — Create/import Ghidra projects
- **JSON output** — Machine-readable output with `--json` flag
- **REPL** — Interactive session with undo/redo history

## Installation

```bash
cd agent-harness
pip install -e .
```

## Quick Start

```bash
# Analyze a binary
cli-anything-ghidra analyze binary.exe --project /tmp/ghidra_proj

# Decompile main function
cli-anything-ghidra decompile binary.exe --function main

# Decompile all functions
cli-anything-ghidra decompile-all binary.exe --output decompiled/

# Extract strings
cli-anything-ghidra strings binary.exe

# List functions
cli-anything-ghidra functions binary.exe

# Show headers
cli-anything-ghidra headers binary.exe
```
