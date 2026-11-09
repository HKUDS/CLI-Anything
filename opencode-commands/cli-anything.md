---
description: Build a complete CLI harness for a GUI application or public API service (all 7 phases)
subtask: true
---
# cli-anything Command

Build a complete, stateful CLI harness for a GUI application or public API service.

**Target software**: $1

## CRITICAL: Read HARNESS.md First

**Before doing anything else, you MUST read `./HARNESS.md` (located alongside this command).** It defines the complete methodology, architecture standards, and implementation patterns. Every phase below follows HARNESS.md. Do not improvise — follow the harness specification.

## Arguments

- `$1` is the **software path or repo URL**. Either:
  - A **local path** to the software source code (e.g., `/home/user/gimp`, `./blender`)
  - A **GitHub repository URL** (e.g., `https://github.com/GNOME/gimp`, `github.com/blender/blender`)
  - With `--api`, an **official API documentation URL or OpenAPI spec** (local JSON/YAML file or vendor URL)

  For source-backed targets, clone GitHub repositories locally first.

  **Note:** Source-backed targets require a source path or repo URL. For a named
  closed-source/SaaS target, offer public API mode and request official docs.
  An explicit `--api` request already selects that route; do not reconfirm it.

## What This Command Does

This command implements the complete cli-anything methodology to build a production-ready CLI harness for any GUI application. **All phases follow the standards defined in HARNESS.md.**

### Phase 0: Source Acquisition
- Select local source, MCP, or API mode. For `--api`, use official OpenAPI/endpoint
  docs as the analysis source and follow `guides/api-backend.md`. Record the
  service name/spec version and create `<software>/agent-harness/` locally.
  Do not clone API docs URLs or require a local vendor binary.
- For source-backed targets, clone GitHub repositories if needed, verify the
  local source path, and derive the software name from its directory
  (e.g., `/home/user/gimp` -> `gimp`).

### Phase 1: Codebase Analysis
- For API targets: map schemas, authentication, pagination, async jobs, artifacts,
  and write effects from the official contract instead of local source.
- Analyzes local source code for source-backed targets
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
- Declare backend requirements in `agent-harness/harness.json` and generate the
  skill with `skill_generator.py`; verify command paths against actual CLI help.

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
