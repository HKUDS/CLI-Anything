---
name: >-
  cli-anything-ghidra
description: >-
  Command-line interface for Ghidra - Binary analysis, decompilation, symbol extraction,
  string extraction, and cross-reference analysis via analyzeHeadless...
---

# cli-anything-ghidra

A stateful command-line interface for binary analysis, built on Ghidra. Designed for AI agents and security researchers who need to analyze binaries, decompile functions, and extract symbols.

## Installation

```bash
pip install cli-anything-ghidra
```

**Prerequisites:**
- Python 3.10+
- Ghidra must be installed (from ghidra-sre.org)
- `analyzeHeadless` must be in PATH

## Command Groups

### Analysis

| Command | Description |
|---------|-------------|
| `analyze` | Run auto-analysis on a binary |
| `strings` | Extract strings with addresses |
| `imports` | List imported functions |
| `exports` | List exported functions |
| `functions` | List all functions with addresses |
| `xrefs` | Show cross-references to address |
| `symbols` | List all symbols |
| `headers` | Show PE/ELF header info |

### Decompilation

| Command | Description |
|---------|-------------|
| `decompile` | Decompile a specific function to C |
| `decompile-all` | Decompile all functions to C |

### Scripts & Projects

| Command | Description |
|---------|-------------|
| `script run` | Run a Ghidra script |
| `project create` | Create a Ghidra project |
| `project import` | Import binary into project |

### Session

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo last operation |
| `redo` | Redo last undone operation |
| `history` | Show undo history |

## Examples

```bash
# Analyze a binary
cli-anything-ghidra --json analyze binary.exe --project /tmp/ghidra_proj

# Decompile main function
cli-anything-ghidra decompile binary.exe --function main --output main.c

# Extract strings
cli-anything-ghidra strings binary.exe

# List imported functions
cli-anything-ghidra imports binary.exe

# Show cross-references
cli-anything-ghidra xrefs binary.exe --address 0x00401000

# Show PE/ELF headers
cli-anything-ghidra headers binary.exe

# Run a custom script
cli-anything-ghidra script run my_script.py --binary binary.exe --project /tmp/proj
```

## Version

1.0.0
