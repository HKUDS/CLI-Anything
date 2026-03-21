---
description: Validate a CLI harness against HARNESS.md standards and best practices
---

# cli-anything:validate Command

Validate a CLI harness against HARNESS.md standards and best practices.

## CRITICAL: Read HARNESS.md First

**Before validating, read `./HARNESS.md`.** It is the single source of truth for all validation checks below. Every check in this command maps to a requirement in HARNESS.md.

## Usage

```bash
/cli-anything:validate <software-path-or-repo>
```

## Arguments

- `<software-path-or-repo>` - **Required.** Either:
  - A **local path** to the software source code (e.g., `/home/user/gimp`, `./blender`)
  - A **GitHub repository URL** (e.g., `https://github.com/GNOME/gimp`, `github.com/blender/blender`)

  If a GitHub URL is provided, the agent clones the repo locally first, then works on the local copy.

  The software name is derived from the directory name. The agent locates the CLI harness at `/root/cli-anything/<software-name>/agent-harness/`.

## What This Command Validates

### 1. Directory Structure
- `agent-harness/cli_anything/<software>/` exists (namespace sub-package)
- `cli_anything/` has NO `__init__.py` (PEP 420 namespace package)
- `<software>/` HAS `__init__.py` (regular sub-package)
- `core/`, `utils/`, `tests/` subdirectories present
- `setup.py` in agent-harness/ uses `find_namespace_packages`

### 2. Required Files
- `README.md` - Installation and usage guide
- `<software>_cli.py` - Main CLI entry point
- `core/project.py` - Project management
- `core/session.py` - Undo/redo
- `core/export.py` - Rendering/export
- `tests/TEST.md` - Test plan and results
- `tests/test_core.py` - Unit tests
- `tests/test_full_e2e.py` - E2E tests
- `../<SOFTWARE>.md` - Software-specific SOP

### 3. CLI Implementation Standards
- Uses Click framework
- Has command groups (not flat commands)
- Implements `--json` flag for machine-readable output
- Implements `--project` flag for project file
- Has `handle_error` decorator for consistent error handling
- Has REPL mode
- Has global session state

### 4. Core Module Standards
- `project.py` has: create, open, save, info, list_profiles
- `session.py` has: Session class with undo/redo/snapshot
- `export.py` has: render function and EXPORT_PRESETS
- All modules have proper docstrings
- All functions have type hints

### 5. Test Standards
- `TEST.md` has both plan (Part 1) and results (Part 2)
- Unit tests use synthetic data only
- E2E tests use real files
- Workflow tests simulate real-world scenarios
- `test_full_e2e.py` has a `TestCLISubprocess` class
- `TestCLISubprocess` uses `_resolve_cli("cli-anything-<software>")` (no hardcoded paths)
- `_resolve_cli` prints which backend is used and supports `CLI_ANYTHING_FORCE_INSTALLED`
- Subprocess `_run` does NOT set `cwd` (installed commands work from any directory)
- All tests pass (100% pass rate)

### 6. Documentation Standards
- `README.md` has: installation, usage, command reference, examples
- `<SOFTWARE>.md` has: architecture analysis, command map, rendering gap assessment
- No duplicate `HARNESS.md` (should reference plugin's HARNESS.md)
- All commands documented with examples

### 7. PyPI Packaging Standards
- `setup.py` uses `find_namespace_packages(include=["cli_anything.*"])`
- Package name follows `cli-anything-<software>` convention
- Entry point: `cli-anything-<software>=cli_anything.<software>.<software>_cli:main`
- `cli_anything/` has NO `__init__.py` (namespace package rule)
- All imports use `cli_anything.<software>.*` prefix
- Dependencies listed in install_requires
- Python version requirement specified (>=3.10)

### 8. Code Quality
- No syntax errors
- No import errors
- Follows PEP 8 style
- No hardcoded paths (uses relative paths or config)
- Proper error handling (no bare `except:`)

## Validation Report

The command generates a detailed report:

```
CLI Harness Validation Report
Software: gimp
Path: /root/cli-anything/gimp/agent-harness/cli_anything/gimp

Directory Structure (5/5 checks passed)
Required Files (9/9 files present)
CLI Implementation (7/7 standards met)
Core Modules (5/5 standards met)
Test Standards (10/10 standards met)
Documentation (4/4 standards met)
PyPI Packaging (7/7 standards met)
Code Quality (5/5 checks passed)

Overall: PASS (52/52 checks)
```

## Example

```bash
# Validate GIMP CLI
/cli-anything:validate /home/user/gimp

# Validate from GitHub repo
/cli-anything:validate https://github.com/blender/blender
```
