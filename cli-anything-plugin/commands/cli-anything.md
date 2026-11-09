# cli-anything Command

Build a complete, stateful CLI harness for a GUI application or public API service.

## CRITICAL: Read HARNESS.md First

**Before doing anything else, you MUST read `./HARNESS.md`.** It defines the complete methodology, architecture standards, and implementation patterns. Every phase below follows HARNESS.md. Do not improvise — follow the harness specification.

## Usage

```bash
/cli-anything <software-path-or-repo>
/cli-anything <official-api-docs-or-openapi-spec> --api
```

## Arguments

- `<software-path-or-repo>` - **Required.** Either:
  - A **local path** to the software source code (e.g., `/home/user/gimp`, `./blender`)
  - A **GitHub repository URL** (e.g., `https://github.com/GNOME/gimp`, `github.com/blender/blender`)
  - With `--api`, an **official public API documentation URL or OpenAPI spec**
    (local JSON/YAML file or vendor URL). A closed-source/SaaS target does not
    require a source repository or local application binary.

  For source-backed targets, the agent clones GitHub repositories locally first.

  **Note:** For source-backed targets, software names alone (e.g., "gimp") are
  NOT sufficient. If a named target is closed-source or SaaS, offer the public
  API route and request official API documentation instead of refusing the target.
  An explicit `--api` request already selects that route; do not reconfirm it.

## What This Command Does

This command implements the complete cli-anything methodology to build a production-ready CLI harness for any GUI application. **All phases follow the standards defined in HARNESS.md.**

### Phase 0: Source Acquisition
- First determine the backend: local source, MCP, or public REST API. Do not
  attempt to clone API documentation URLs as repositories.
- For source-backed targets, clone GitHub repositories if needed, verify the
  local source path, and derive the software name from its directory
  (e.g., `/home/user/gimp` -> `gimp`).
- For API targets, use the official OpenAPI spec (or public endpoint docs) as
  the analysis source. Record its URL/version and the selected service name in
  `<SOFTWARE>.md`; create `<software>/agent-harness/` in the working directory.
  Never require vendor source code or credentials just to analyze a public spec.

### Phase 1: Codebase Analysis
- For API targets, follow [API Backend Pattern](../guides/api-backend.md): map
  operations, schemas, authentication, pagination, asynchronous jobs, rate limits,
  artifact downloads, and read/write side effects from the official contract.
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

### Phase 6.5: SKILL.md Generation
- Declare backend requirements in `agent-harness/harness.json` (schema version 1;
  see [skill generation](../guides/skill-generation.md)). API metadata contains
  environment variable names, never credential values.
- Extracts CLI metadata using `skill_generator.py`
- Generates SKILL.md with YAML frontmatter and Markdown body
- Includes command groups, examples, and agent-specific guidance
- Outputs the canonical skill to `skills/cli-anything-<software>/SKILL.md` and refreshes the packaged compatibility copy at `cli_anything/<software>/skills/SKILL.md`
- Makes the CLI discoverable and usable by AI agents

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

Canonical repo-root skill output:

```
skills/
└── cli-anything-<software>/
    └── SKILL.md
```

## Example

```bash
# Build a CLI for GIMP from local source
/cli-anything /home/user/gimp

# Build from a GitHub repo
/cli-anything https://github.com/blender/blender

# Build against a vendor's documented public API
/cli-anything https://api.example.com/openapi.json --api
```

## Auto-Save + --dry-run (Required for Session-Based CLIs)

**Session-based CLIs must auto-save after one-shot mutations.** Without this, one-shot commands silently lose changes because `save_session()` is never called before the process exits. A `--dry-run` flag must also be provided to suppress the save.

See [`guides/auto-save-dry-run.md`](../guides/auto-save-dry-run.md) for the full pattern, code examples, and when it applies.

## Success Criteria

The command succeeds when:
1. All core modules are implemented and functional
2. CLI supports both one-shot commands and REPL mode
3. `--json` output mode works for all commands
4. All tests pass (100% pass rate)
5. Subprocess tests use `_resolve_cli()` and pass with `CLI_ANYTHING_FORCE_INSTALLED=1`
6. TEST.md contains both plan and results
7. README.md documents installation and usage
8. SKILL.md is generated with proper YAML frontmatter and command documentation
9. setup.py is created and local installation works
10. CLI is available in PATH as `cli-anything-<software>`
11. **Session-based CLIs implement auto-save + `--dry-run`** (see [guide](../guides/auto-save-dry-run.md))
