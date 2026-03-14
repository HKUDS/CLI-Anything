# cli-anything Plugin for Claude Code

Build powerful, stateful CLI interfaces for any GUI application using the cli-anything harness methodology.

## Overview

The cli-anything plugin automates the process of creating production-ready command-line interfaces for GUI applications. It follows a proven methodology that has successfully generated CLIs for GIMP, Blender, Inkscape, Audacity, LibreOffice, OBS Studio, and Kdenlive — with over 1,100 passing tests across all implementations.

## What It Does

This plugin transforms GUI applications into agent-usable CLIs by:

1. **Analyzing** the application's architecture and data model
2. **Designing** a CLI that mirrors the GUI's functionality
3. **Implementing** core modules with proper state management
4. **Testing** with comprehensive unit and E2E test suites
5. **Documenting** everything for maintainability

The result: A stateful CLI with REPL mode, JSON output, undo/redo, and full test coverage.

## Installation

### From Claude Code

```bash
/plugin install cli-anything@your-registry
```

### Manual Installation

1. Clone this repository to your Claude Code plugins directory:
   ```bash
   cd ~/.claude/plugins
   git clone https://github.com/yourusername/cli-anything-plugin.git
   ```

2. Reload plugins:
   ```bash
   /reload-plugins
   ```

## Prerequisites

- Python 3.10+
- `click` - CLI framework
- `pytest` - Testing framework
- HARNESS.md (included in this plugin at `~/.claude/plugins/cli-anything/HARNESS.md`)

**Windows note:** Claude Code runs shell commands via `bash`. On Windows, install Git for Windows (includes `bash` and
`cygpath`) or use WSL; otherwise commands may fail with `cygpath: command not found`.

Install Python dependencies:
```bash
pip install click pytest
```

## Commands

### `/cli-anything <software-path-or-repo>`

Build a complete CLI harness for any software application. Accepts a local path to the software source code or a GitHub repository URL.

**Examples:**
```bash
# Build from local source
/cli-anything /home/user/gimp

# Build from a GitHub repo
/cli-anything https://github.com/blender/blender
```

This runs all 7 phases:
1. Source Acquisition (clone if GitHub URL)
2. Codebase Analysis
3. CLI Architecture Design
4. Implementation
5. Test Planning
6. Test Implementation & Documentation
7. PyPI Publishing and Installation

### `/cli-anything:refine <software-path> [focus]`

Refine an existing CLI harness to expand coverage. Analyzes gaps between the software's full capabilities and what the current CLI covers, then iteratively adds new commands and tests.

**Examples:**
```bash
# Broad refinement — agent finds gaps across all capabilities
/cli-anything:refine /home/user/gimp

# Focused refinement — agent targets a specific functionality area
/cli-anything:refine /home/user/shotcut "vid-in-vid and picture-in-picture compositing"
/cli-anything:refine /home/user/blender "particle systems and physics simulation"
```

### `/cli-anything:test <software-path-or-repo>`

Run tests for a CLI harness and update TEST.md with results.

**Examples:**
```bash
# Run all tests for GIMP CLI
/cli-anything:test /home/user/gimp

# Run tests for Blender from GitHub
/cli-anything:test https://github.com/blender/blender
```

### `/cli-anything:validate <software-path-or-repo>`

Validate a CLI harness against HARNESS.md standards and best practices.

**Examples:**
```bash
# Validate GIMP CLI
/cli-anything:validate /home/user/gimp

# Validate from GitHub repo
/cli-anything:validate https://github.com/blender/blender
```

### `/cli-anything:list [--path <directory>] [--depth <n>] [--json]`

List all available CLI-Anything tools, including both installed packages and generated directories.

**Options:**
- `--path <directory>` - Directory to search (default: current directory)
- `--depth <n>` - Maximum recursion depth (default: unlimited). Scans depths 0 through N.
- `--json` - Output in JSON format

**Examples:**
```bash
# List all tools in current directory (unlimited depth)
/cli-anything:list

# List tools with depth limit
/cli-anything:list --depth 2

# List tools with JSON output
/cli-anything:list --json

# Search a specific directory with depth limit
/cli-anything:list --path /projects/my-tools --depth 3
```

**Output includes:**
- Tool name
- Status (installed/generated)
- Version
- Source path

## The cli-anything Methodology

### Phase 1: Codebase Analysis

Analyze the target application:
- Backend engine (e.g., MLT, GEGL, bpy)
- Data model (XML, JSON, binary)
- Existing CLI tools
- GUI-to-API mappings

**Output:** Software-specific SOP document (e.g., `GIMP.md`)

### Phase 2: CLI Architecture Design

Design the CLI structure:
- Command groups matching app domains
- State model (JSON project format)
- Output formats (human + JSON)
- Rendering pipeline

**Output:** Architecture documented in SOP

### Phase 3: Implementation

Build the CLI:
- Core modules (project, session, export, etc.)
- Click-based CLI with command groups
- REPL mode as default with unified `ReplSkin` (copy `repl_skin.py` from plugin to `utils/`)
- `--json` flag for machine-readable output
- Global session state with undo/redo
- `invoke_without_command=True` so bare `cli-anything-<software>` enters REPL

**Output:** Working CLI at `agent-harness/cli_anything/<software>/`

### Phase 4: Test Planning

Plan comprehensive tests:
- Unit test plan (modules, functions, edge cases)
- E2E test plan (workflows, file types, validations)
- Realistic workflow scenarios

**Output:** `TEST.md` Part 1 (the plan)

### Phase 5: Test Implementation

Write the tests:
- `test_core.py` - Unit tests (synthetic data)
- `test_full_e2e.py` - E2E tests (real files)
- Workflow tests (multi-step scenarios)
- Output verification (pixel analysis, format validation)
- `TestCLISubprocess` class using `_resolve_cli("cli-anything-<software>")` to
  test the installed command via subprocess (falls back to `python -m` in dev)

**Output:** Complete test suite

### Phase 6: Test Documentation

Run and document:
- Execute `pytest -v --tb=no`
- Append full results to `TEST.md`
- Document coverage and gaps

**Output:** `TEST.md` Part 2 (the results)

### Phase 7: PyPI Publishing and Installation

Package and install:
- Create `setup.py` with `find_namespace_packages(include=["cli_anything.*"])`
- Structure as namespace package: `cli_anything/<software>/` (no `__init__.py` in `cli_anything/`)
- Configure console_scripts entry point for PATH installation
- Test local installation: `pip install -e .`
- Verify CLI is in PATH: `which cli-anything-<software>`

**Output:** Installable package ready for distribution

## Output Structure

```
<software>/
└── agent-harness/
    ├── <SOFTWARE>.md          # Software-specific SOP
    ├── setup.py               # PyPI config (find_namespace_packages)
    └── cli_anything/          # Namespace package (NO __init__.py)
        └── <software>/        # Sub-package (HAS __init__.py)
            ├── README.md          # Installation and usage
            ├── <software>_cli.py  # Main CLI entry point
            ├── __init__.py
            ├── __main__.py        # python -m cli_anything.<software>
            ├── core/              # Core modules
            │   ├── __init__.py
            │   ├── project.py     # Project management
            │   ├── session.py     # Undo/redo
            │   ├── export.py      # Rendering/export
            │   └── ...            # Domain-specific modules
            ├── utils/             # Utilities
            │   ├── __init__.py
            │   ├── repl_skin.py   # Unified REPL skin (copy from plugin)
            │   └── ...
            └── tests/
                ├── __init__.py
                ├── TEST.md        # Test plan + results
                ├── test_core.py   # Unit tests
                └── test_full_e2e.py # E2E tests
```

All CLIs use PEP 420 namespace packages under `cli_anything.*`. The `cli_anything/`
directory has NO `__init__.py`, allowing multiple separately-installed CLI packages
to coexist in the same Python environment without conflicts.

## Success Stories

The cli-anything methodology has successfully built CLIs for:

| Software | Tests | Description |
|----------|-------|-------------|
| GIMP | 103 | Raster image editor (Pillow-based) |
| Blender | 200 | 3D creation suite (bpy script generation) |
| Inkscape | 197 | Vector graphics editor (SVG manipulation) |
| Audacity | 154 | Audio editor (WAV processing) |
| LibreOffice | 143 | Office suite (ODF ZIP/XML) |
| OBS Studio | 153 | Streaming/recording (JSON scene collections) |
| Kdenlive | 151 | Video editor (MLT XML) |
| Shotcut | 144 | Video editor (MLT XML, ffmpeg) |
| **Total** | **1,245** | All tests passing |

## Key Features

### Stateful Session Management
- Undo/redo with deep-copy snapshots (50-level stack)
- Project state persistence
- History tracking

### Dual Output Modes
- Human-readable (tables, colors)
- Machine-readable (`--json` flag)

### REPL Mode
- Default behavior when CLI is invoked without a subcommand
- Unified `ReplSkin` with branded banner, colored prompts, and styled messages
- Persistent command history via `prompt_toolkit`
- Pre-built message helpers: `success()`, `error()`, `warning()`, `info()`, `status()`, `table()`, `progress()`
- Software-specific accent colors with consistent cli-anything branding

### Comprehensive Testing
- Unit tests (synthetic data, no external deps)
- E2E tests (real files, full pipeline)
- Workflow tests (multi-step scenarios)
- CLI subprocess tests via `_resolve_cli()` against the installed command
- Force-installed mode (`CLI_ANYTHING_FORCE_INSTALLED=1`) for release validation
- Output verification (pixel/audio analysis)

### Complete Documentation
- Installation guides
- Command reference
- Architecture analysis
- Test plans and results

### PyPI Distribution
- PEP 420 namespace packages under `cli_anything.*`
- Unified package naming: `cli-anything-<software>`
- Multiple CLIs coexist without conflicts in the same environment
- Automatic PATH installation via console_scripts
- Easy installation: `pip install cli-anything-<software>`
- Agent-discoverable via `which cli-anything-<software>`

## Best Practices

### When to Use cli-anything

✅ **Good for:**
- GUI applications with clear data models
- Apps with existing CLI tools or APIs
- Projects needing agent-usable interfaces
- Automation and scripting workflows

❌ **Not ideal for:**
- Apps with purely binary, undocumented formats
- Real-time interactive applications
- Apps requiring GPU/display access

### Tips for Success

1. **Start with analysis** - Understand the app's architecture before coding
2. **Follow the phases** - Don't skip test planning
3. **Test thoroughly** - Aim for 100% pass rate
4. **Document everything** - Future you will thank you
5. **Use the validation command** - Catch issues early
6. **Install to PATH** - Make CLIs discoverable by running Phase 7
7. **Publish to PyPI** - Share your CLI with the community

## Installation and Distribution

After building a CLI with this plugin, you can:

### Install Locally
```bash
cd ~/CLI-Anything/<software>/agent-harness
pip install -e .
cli-anything-<software> --help
```

### Publish to PyPI
```bash
pip install build twine
python -m build
twine upload dist/*
```

### Users Install from PyPI
```bash
pip install cli-anything-<software>
cli-anything-<software> --help  # Available in PATH
```

This makes CLIs discoverable by AI agents that can check `which cli-anything-<software>` to find available tools.

## Troubleshooting

### Tests fail after building

1. Check dependencies: `pip list | grep -E 'click|pytest'`
2. Verify Python version: `python3 --version` (need 3.10+)
3. Run validation: `/cli-anything:validate <software>`
4. Check TEST.md for specific failures

### CLI not found

- Verify output directory: `ls -la ~/CLI-Anything/<software>/agent-harness/cli_anything/<software>/`
- Check for errors in build phase
- Try rebuilding: `/cli-anything <software-path>`

### Import errors

- Ensure `__init__.py` files exist in all packages
- Check Python path: `echo $PYTHONPATH`
- Verify directory structure matches expected layout

### CLI not in PATH after installation

- Verify installation: `pip show cli-anything-<software>`
- Check entry points: `pip show -f cli-anything-<software> | grep console_scripts`
- Reinstall: `pip uninstall cli-anything-<software> && pip install cli-anything-<software>`
- Check PATH: `echo $PATH | grep -o '[^:]*bin'`

## Contributing

To add support for new software:

1. Clone the target application's repository
2. Run `/cli-anything <software-name>`
3. Review and refine the generated CLI
4. Submit a PR with the new harness

## License

MIT License - See LICENSE file for details

## Credits

Built on the cli-anything methodology developed through the creation of 8 production CLI harnesses with 1,245 passing tests.

Inspired by the ralph-loop plugin's iterative development approach.

## Support

- Documentation: See HARNESS.md in this plugin for the complete methodology
- Issues: Report bugs or request features on GitHub
- Examples: Check `~/CLI-Anything/` for reference implementations

## Version History

### 1.0.0 (2026-03-05)
- Initial release
- Support for 4 commands: cli-anything, refine, test, validate
- Complete 7-phase methodology implementation
- Comprehensive documentation
- PyPI publishing support with namespace isolation
- `_resolve_cli()` helper for subprocess tests against installed commands
- `CLI_ANYTHING_FORCE_INSTALLED=1` env var for release validation
- 8 reference implementations, 1,245 passing tests
