# cli-anything Skill

Build powerful, stateful CLI interfaces for any GUI application using the cli-anything harness methodology.

## Overview

This skill enables AI agents to transform any software application into an agent-controllable CLI. It follows the proven cli-anything methodology that has successfully generated CLIs for GIMP, Blender, Inkscape, Audacity, LibreOffice, OBS Studio, and Kdenlive.

## Usage

```bash
# Build CLI for local source
cli-anything /path/to/software

# Build CLI from GitHub
cli-anything https://github.com/org/repo
```

## Prerequisites

- Python 3.10+
- click >= 8.0
- pytest

Install dependencies:
```bash
pip install click pytest pyyaml
```

## Methodology

This skill follows the 7-phase cli-anything methodology:

### Phase 0: Source Acquisition
- Clone GitHub repos or validate local paths
- Verify source code structure

### Phase 1: Codebase Analysis
- Analyze application architecture
- Map GUI actions to API calls
- Identify existing CLI tools

### Phase 2: CLI Architecture Design
- Design command groups matching app domains
- Plan state model and output formats
- Create software-specific SOP documents

### Phase 3: Implementation
- Create directory structure: `agent-harness/cli_anything/<software>/`
- Implement core modules with Click
- Add REPL support with JSON output mode

### Phase 4: Test Planning
- Design unit and E2E test coverage
- Plan validation scenarios

### Phase 5: Test Implementation
- Write comprehensive tests
- Ensure 100% pass rate

### Phase 6: Documentation & Publishing
- Document commands and usage
- Prepare for PyPI publishing

## Key Files

| File | Purpose |
|------|---------|
| `HARNESS.md` | Complete methodology specification |
| `commands/cli-anything.md` | Main build command |
| `commands/validate.md` | Validation command |
| `commands/test.md` | Testing command |
| `commands/refine.md` | Refinement command |

## Output

- Stateful CLI with REPL mode
- JSON output for agent consumption
- Undo/redo support
- Full test coverage

## Related

- Plugin workflow: See `../cli-anything-plugin/` for Claude Code plugin
- Examples: See `../blender/`, `../gimp/`, `../audacity/` for implemented CLIs
