---
name: cli-anything
description: Use when the user wants Codex to build, refine, test, or validate a CLI-Anything harness for a GUI application or source repository. This self-contained Codex edition vendors the official HARNESS, REPL skin, skill generator, and template so it remains usable even when the full CLI-Anything repository is unavailable.
---

# CLI-Anything for Codex

Act as the CLI-Anything builder for Codex.

This package is intentionally self-contained. Prefer repo-local official plugin files when they
exist in the target source tree; otherwise use the bundled files in this skill.

## Resource Map

- `references/HARNESS.md`
  - Canonical methodology and hard requirements for Codex usage.
  - Read this before substantial implementation work.
- `assets/cli_anything_plugin/repl_skin.py`
  - Copy into generated harnesses as `cli_anything/<software>/utils/repl_skin.py`.
- `assets/cli_anything_plugin/skill_generator.py`
  - Use to generate the installed `skills/SKILL.md` for the produced CLI package.
- `assets/cli_anything_plugin/templates/SKILL.md.template`
  - Template used by the skill generator.
- `scripts/sync_from_repo.ps1` / `scripts/sync_from_repo.sh`
  - Refresh bundled files from an official CLI-Anything repository clone.

## Source Selection

When the target path is itself a CLI-Anything repository or already contains the official plugin files,
prefer these repo-local sources:

- `cli-anything-plugin/HARNESS.md`
- `cli-anything-plugin/repl_skin.py`
- `cli-anything-plugin/skill_generator.py`
- `cli-anything-plugin/templates/SKILL.md.template`

Otherwise, use the bundled copies in this skill.

## Inputs

Accept either:

- A local source path such as `./gimp` or `/path/to/software`
- A GitHub repository URL

Derive the software name from the local directory name after cloning if needed.

## Always-Read Rules

Before substantial implementation, read `references/HARNESS.md` or the repo-local
`cli-anything-plugin/HARNESS.md`. Do not rely on this file alone for detailed build and test behavior.

At minimum, load the sections covering:

- Purpose and general SOP
- Relevant implementation phases
- Test planning and execution
- SKILL generation
- Summary requirements near the end of the file

## Hard Requirements

These rules are mandatory even if you do not reread the full HARNESS immediately:

- Prefer the real software backend over reimplementation.
- Build a stateful Click CLI with subcommands, `--json`, and REPL as the default path.
- Write `tests/TEST.md` before writing test code.
- E2E tests must invoke the real software and produce real output artifacts.
- Do not gracefully degrade to fallback libraries when the real software is missing.
- Subprocess tests must exercise the installed `cli-anything-<software>` command.
- Use `_resolve_cli()` in subprocess tests rather than hardcoding module execution.
- Copy and use `repl_skin.py` for the interactive REPL.
- Generate a package-local `skills/SKILL.md` using `skill_generator.py`.
- If session state is saved to JSON, use safe locked writes instead of bare truncating writes.
- Report whether bundled or repo-local official resources were used.

## Modes

### Build

Use when the user wants a new harness.

Read the HARNESS sections for:

- Phase 1: Codebase Analysis
- Phase 2: CLI Architecture Design
- Phase 3: Implementation
- Phase 4-6.5: Testing, documentation, and generated skill packaging

Target structure:

```text
<software>/
`-- agent-harness/
    |-- <SOFTWARE>.md
    |-- setup.py
    `-- cli_anything/
        `-- <software>/
            |-- README.md
            |-- __init__.py
            |-- __main__.py
            |-- <software>_cli.py
            |-- core/
            |-- utils/
            |-- tests/
            `-- skills/
                `-- SKILL.md
```

### Refine

Use when the harness already exists.

First inventory current commands, test coverage, backend wiring, REPL behavior, generated skill
files, and missing output verification. Then do gap analysis against the target software.

Prefer:

- High-impact missing features
- Easy wrappers around existing backend APIs or CLIs
- Additions that compose with the current command model
- Missing real-backend tests and output verification

Do not remove existing commands unless the user explicitly asks for a breaking change.

### Test

Use when the user wants to create or improve tests.

Required flow:

1. Write or update `tests/TEST.md` first.
2. Add `test_core.py`.
3. Add `test_full_e2e.py`.
4. Run tests against real software.
5. Append results back into `TEST.md`.

### Validate

Check that the harness:

- Uses the `cli_anything.<software>` namespace package layout
- Has an installable `setup.py` entry point
- Supports JSON output
- Enters REPL when invoked without a subcommand
- Uses the unified REPL skin
- Ships `tests/TEST.md`
- Ships a generated `skills/SKILL.md`
- Verifies real outputs rather than trusting exit codes

## Implementation Guidance

When building or refining a harness:

1. Acquire the source tree locally.
2. Analyze architecture, data model, existing CLIs, and GUI-to-API mappings.
3. Design command groups and the session state model.
4. Implement the harness.
5. Copy `assets/cli_anything_plugin/repl_skin.py` into `utils/repl_skin.py` if no repo-local source is available.
6. Use `assets/cli_anything_plugin/skill_generator.py` and `assets/cli_anything_plugin/templates/SKILL.md.template` to generate the package skill when no repo-local source is available.
7. Write `tests/TEST.md`, then tests, then run them.
8. Update README usage docs.
9. Verify local installation with `pip install -e .`.

## Output Expectations

When reporting progress or final results, include:

- Target software and source path
- Whether bundled or repo-local official resources were used
- Files added or changed
- Validation commands run
- Open risks, backend limitations, or missing dependencies

## Syncing Bundled Files

To refresh this skill from an official CLI-Anything clone, run one of:

- `scripts/sync_from_repo.ps1 -RepoRoot <path>`
- `scripts/sync_from_repo.sh <path>`

This updates the bundled HARNESS, REPL skin, skill generator, and template without changing
the Codex-specific `SKILL.md`.
