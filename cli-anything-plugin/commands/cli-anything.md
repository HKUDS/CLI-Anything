# cli-anything Command

Build a complete, stateful CLI harness for any GUI application.

## CRITICAL: Read HARNESS.md First

**Before doing anything else, you MUST read `./HARNESS.md`.** It defines the complete methodology, architecture standards, and implementation patterns. Every phase below follows HARNESS.md. Do not improvise — follow the harness specification.

## Usage

```bash
/cli-anything:cli-anything <software-path-or-repo>
```

> Claude Code 2.x uses the namespaced command form above. On older releases, the legacy `/cli-anything` alias may still work.

## Arguments

- `<software-path-or-repo>` - **Required.** Either:
  - A **local path** to the software source code (e.g., `/home/user/gimp`, `./blender`)
  - A **GitHub repository URL** (e.g., `https://github.com/GNOME/gimp`, `github.com/blender/blender`)

  If a GitHub URL is provided, the agent clones the repo locally first, then works on the local copy.

  **Note:** Software names alone (e.g., "gimp") are NOT accepted. You must provide the actual source code path or repository URL so the agent can analyze the codebase.

## What This Command Does

This command implements the complete cli-anything methodology to build a production-ready CLI harness for any GUI application. **All phases follow the standards defined in HARNESS.md.**

### Phase 0: Source Acquisition
- If `<software-path-or-repo>` is a GitHub URL, clone it to a local working directory
- Verify the local path exists and contains source code
- Derive the software name from the directory name (e.g., `/home/user/gimp` -> `gimp`)

### Phase 1: Codebase Analysis
- Analyzes the local source code
- Analyzes the backend engine and data model
- Maps GUI actions to API calls
- Identifies existing CLI tools
- Documents the architecture

### Phase 2: CLI Architecture Design
- Designs command groups matching the app's domains
- Plans the state model and output formats
- Creates the software-specific SOP document (e.g., GIMP.md)

### Phase 3: Implementation
- Creates the directory structure: `agent-harness/cli_anything/<software>/core`, `utils`, `tests`
- Implements core modules (project, session, export, etc.)
- Builds the Click-based CLI with REPL support
- Implements `--json` output mode for agent consumption
- All imports use `cli_anything.<software>.*` namespace

### Phase 4: Test Planning
- Creates `TEST.md` with comprehensive test plan
- Plans unit tests for all core modules
- Plans E2E tests with real files
- Designs realistic workflow scenarios

### Phase 5: Test Implementation
- Writes unit tests (`test_core.py`) - synthetic data, no external deps
- Writes E2E tests (`test_full_e2e.py`) - real files, full pipeline
- Implements workflow tests simulating real-world usage
- Adds output verification (pixel analysis, format validation, etc.)
- Adds `TestCLISubprocess` class with `_resolve_cli("cli-anything-<software>")`
  that tests the installed command via subprocess (no hardcoded paths or CWD)

### Phase 6: Test Documentation
- Runs all tests with `pytest -v --tb=no`
- Appends full test results to `TEST.md`
- Documents test coverage and any gaps

### Phase 7: PyPI Publishing and Installation
- Creates `setup.py` with `find_namespace_packages(include=["cli_anything.*"])`
- Package name: `cli-anything-<software>`, namespace: `cli_anything.<software>`
- `cli_anything/` has NO `__init__.py` (PEP 420 namespace package)
- Configures console_scripts entry point for PATH installation
- Tests local installation with `pip install -e .`
- Verifies CLI is available in PATH: `which cli-anything-<software>`

## Output Structure

```
<software-name>/
└── agent-harness/
    ├── <SOFTWARE>.md          # Software-specific SOP
    ├── setup.py               # PyPI package config (find_namespace_packages)
    └── cli_anything/          # Namespace package (NO __init__.py)
        └── <software>/        # Sub-package (HAS __init__.py)
            ├── README.md          # Installation and usage guide
            ├── <software>_cli.py  # Main CLI entry point
            ├── core/              # Core modules
            │   ├── project.py
            │   ├── session.py
            │   ├── export.py
            │   └── ...
            ├── utils/             # Utilities
            └── tests/
                ├── TEST.md        # Test plan and results
                ├── test_core.py   # Unit tests
                └── test_full_e2e.py # E2E tests
```

## Example

```bash
# Build a CLI for GIMP from local source
/cli-anything:cli-anything /home/user/gimp

# Build from a GitHub repo
/cli-anything:cli-anything https://github.com/blender/blender
```

## Success Criteria

The command succeeds when:
1. All core modules are implemented and functional
2. CLI supports both one-shot commands and REPL mode
3. `--json` output mode works for all commands
4. All tests pass (100% pass rate)
5. Subprocess tests use `_resolve_cli()` and pass with `CLI_ANYTHING_FORCE_INSTALLED=1`
6. TEST.md contains both plan and results
7. README.md documents installation and usage
8. setup.py is created and local installation works
9. CLI is available in PATH as `cli-anything-<software>`
