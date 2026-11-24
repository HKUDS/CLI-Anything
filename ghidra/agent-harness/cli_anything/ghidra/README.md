# cli-anything-ghidra

CLI harness for Ghidra - import and analyze binaries, list functions, decompile to C, and trace cross-references from the command line or via agents. The target binary is never executed.

## Prerequisites

1. **Ghidra 12.x**: download the zip from https://github.com/NationalSecurityAgency/ghidra/releases, unzip it, and point the harness at it:
   ```bash
   export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.2_PUBLIC     # PowerShell: $env:GHIDRA_INSTALL_DIR = "C:\path\ghidra_12.2_PUBLIC"
   ```
2. **JDK 25+** (Ghidra 12 requirement). If your default `JAVA_HOME` is older, set only for this tool:
   ```bash
   export GHIDRA_JAVA_HOME=/path/to/jdk-25
   ```

## Installation

```bash
cd ghidra/agent-harness
pip install -e .
cli-anything-ghidra --help
```

## Usage

```bash
cli-anything-ghidra                                   # interactive REPL
cli-anything-ghidra analyze ./target.exe              # once per binary (can take minutes); repeats are cached, --force redoes it
cli-anything-ghidra --json info ./target.exe
cli-anything-ghidra --json functions ./target.exe --filter main --limit 20
cli-anything-ghidra decompile ./target.exe FUN_140001010
cli-anything-ghidra --json strings ./target.exe --min-length 8
cli-anything-ghidra --json imports ./target.exe
cli-anything-ghidra --json xrefs ./target.exe 0x140001010

# raw firmware / shellcode: describe the format and where code starts
cli-anything-ghidra analyze ./blob.bin --loader BinaryLoader --processor x86:LE:64:default --entry 0
```

Projects live in `~/cli-anything-ghidra/` (override: `CLI_ANYTHING_GHIDRA_HOME`). Delete that folder to clear all analyses.

## Tests

```bash
python3 -m pytest cli_anything/ghidra/tests/ -v
```

Unit tests need neither Ghidra nor Java. The live tests (real Ghidra on six raw bytes) run only when `GHIDRA_INSTALL_DIR` is set.
