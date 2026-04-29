# Contributing to CLI-Anything

Thank you for your interest in contributing to CLI-Anything! This guide will help you get started.

## Types of Contributions

We welcome three main categories of contributions:

### A) CLIs for New Software

Adding a new CLI harness is the most impactful contribution. You can either add the harness **inside this monorepo** or host it in your own **standalone repository** — both are first-class citizens on the CLI-Hub.

#### Option 1: In-repo harness

Place your code under `<software>/agent-harness/` and ensure the following:

1. **`<SOFTWARE>.md`** — the SOP document exists at `<software>/agent-harness/<SOFTWARE>.md` describing the harness architecture.
2. **`SKILL.md`** — the canonical AI-discoverable skill definition exists at `skills/cli-anything-<software>/SKILL.md`, and the packaged compatibility copy exists at `cli_anything/<software>/skills/SKILL.md`.
3. **Tests** — unit tests (`test_core.py`, passable without backend) and E2E tests (`test_full_e2e.py`) are present and passing.
4. **`README.md`** — the project README includes the new software with a link to its harness directory.
5. **`registry.json`** — add an entry for the new software (see [Registry fields](#registry-fields) below).
6. **`repl_skin.py`** — an unmodified copy from the plugin exists in `utils/`.

#### Option 2: Standalone repository (external)

Host your CLI in your own repo and submit a **registry-only PR** to this repo. Your PR only needs to add an entry to `registry.json` — no code in this monorepo is required. This is ideal if you want full control over releases, CI, and versioning.

Requirements for standalone CLIs:

1. **Published package** — your CLI must be installable via `pip install <package-name>` (PyPI) or a `pip install git+https://...` URL.
2. **`SKILL.md`** — an AI-discoverable skill definition exists somewhere in your repo.
3. **Tests** — your repo should have its own test suite.
4. **`registry.json`** — add an entry with `source_url` pointing to your repo and `skill_md` pointing to the raw URL of your SKILL.md (see [Registry fields](#registry-fields) below).

### B) New Features

Feature contributions improve existing harnesses or the plugin framework. Examples include new CLI commands, output formats, backend improvements, or cross-platform fixes.

- Open an issue first to discuss the feature before starting work.
- Follow existing code patterns and conventions in the target harness.
- Include tests for any new functionality.

### C) Bug Fixes

Bug fixes resolve incorrect behavior in existing harnesses or the plugin.

- Reference the related issue in your PR (e.g., `Fixes #123`).
- Include a test that reproduces the bug and verifies the fix.
- Ensure all existing tests for the affected harness still pass.

## CLI-Hub & Registry

All available CLIs are listed in `registry.json` at the repo root and displayed on the [CLI-Hub](https://hkuds.github.io/CLI-Anything/hub/). The hub reads `registry.json` directly from `main`, so it updates immediately when a PR is merged.

### Registry fields

Include an entry in `registry.json` as part of your PR. Each field is described below:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Lowercase identifier (e.g. `"my-software"`). Must be unique. |
| `display_name` | Yes | Human-readable name shown on the hub (e.g. `"My Software"`). |
| `version` | Yes | Semantic version string (e.g. `"1.0.0"`). |
| `description` | Yes | One-line description of what the CLI does. |
| `requires` | Yes | Runtime dependencies the user needs (e.g. `"Docker"`) or `null`. |
| `homepage` | Yes | Official homepage of the **target software** (not your repo). |
| `source_url` | Yes | For standalone repos: URL to your repo (e.g. `"https://github.com/user/repo"`). For in-repo harnesses: `null` (the hub auto-links to `<name>/agent-harness/`). |
| `install_cmd` | Yes | Full pip install command. PyPI: `"pip install cli-anything-my-software"`. In-repo: `"pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=my-software/agent-harness"`. |
| `entry_point` | Yes | CLI command name (e.g. `"cli-anything-my-software"`). |
| `skill_md` | Yes | Path to canonical SKILL.md. For standalone repos: full URL (e.g. `"https://github.com/user/repo/blob/main/.../SKILL.md"`). For in-repo: relative path under the repo-root `skills/` tree (e.g. `"skills/cli-anything-my-software/SKILL.md"`). Set to `null` if not yet available. |
| `category` | Yes | One of the existing categories (check `registry.json` for examples). |
| `contributors` | Yes | Array of `{"name": "...", "url": "..."}` objects listing all contributors. |

**In-repo example:**

```json
{
  "name": "my-software",
  "display_name": "My Software",
  "version": "1.0.0",
  "description": "Short description of what the CLI does",
  "requires": "backend software or null",
  "homepage": "https://my-software.org",
  "source_url": null,
  "install_cmd": "pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=my-software/agent-harness",
  "entry_point": "cli-anything-my-software",
  "skill_md": "skills/cli-anything-my-software/SKILL.md",
  "category": "category-name",
  "contributors": [
    {"name": "your-github-username", "url": "https://github.com/your-github-username"}
  ]
}
```

**Standalone repo example (multiple contributors):**

```json
{
  "name": "my-software",
  "display_name": "My Software",
  "version": "2.0.0",
  "description": "Short description of what the CLI does",
  "requires": "backend software or null",
  "homepage": "https://my-software.org",
  "source_url": "https://github.com/your-username/cli-anything-my-software",
  "install_cmd": "pip install cli-anything-my-software",
  "entry_point": "cli-anything-my-software",
  "skill_md": "https://github.com/your-username/cli-anything-my-software/blob/main/cli_anything/my_software/skills/SKILL.md",
  "category": "category-name",
  "contributors": [
    {"name": "original-author", "url": "https://github.com/original-author"},
    {"name": "current-maintainer", "url": "https://github.com/current-maintainer"}
  ]
}
```

### Updating an existing CLI on the Hub

When you modify an existing harness, update its `registry.json` entry in the same PR:

- Bump the `version` field to reflect the change.
- Update `description`, `requires`, or `category` if they changed.
- The hub will reflect the update as soon as the PR is merged to `main`.

## Development Setup

Each generated CLI lives in `<software>/agent-harness/` and is an independent Python package:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything

# Install a harness in editable mode
cd <software>/agent-harness
pip install -e .

# Run tests
python3 -m pytest cli_anything/<software>/tests/ -v
```

### Requirements

- Python 3.10+
- Click 8.0+
- pytest 7.0+

## Code Style

- Follow PEP 8 conventions.
- Use type hints where practical.
- All CLI commands must support the `--json` flag for machine-readable output.

## Commit Messages

Use clear, descriptive commit messages following the conventional format:

```
feat: add Krita CLI harness
fix: resolve Blender backend path on macOS
docs: update README with new software entry
test: add unit tests for Inkscape layer commands
```

## Running Tests

```bash
# Unit tests (no backend software needed)
python3 -m pytest cli_anything/<software>/tests/test_core.py -v

# E2E tests (requires real backend installed)
python3 -m pytest cli_anything/<software>/tests/test_full_e2e.py -v

# All tests for a harness
python3 -m pytest cli_anything/<software>/tests/ -v
```

## Submitting a Pull Request

1. Fork the repository and create a feature branch from `main`.
2. Make your changes following the guidelines above.
3. Ensure all tests pass for any harnesses you modified.
4. Push your branch and open a Pull Request against `main`.
5. Fill out the PR template completely.

## Questions?

If you have questions, feel free to open a [Discussion](https://github.com/HKUDS/CLI-Anything/discussions) or an issue tagged with `type: question`.
