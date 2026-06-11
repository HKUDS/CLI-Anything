---
name: cli-anything
description: Use when the user wants Reasonix to build, refine, test, or validate a CLI-Anything harness for a GUI application or source repository. Adapts the CLI-Anything methodology to Reasonix without changing the generated Python harness format.
runAs: subagent
---

# CLI-Anything for Reasonix

Use this skill when the user wants Reasonix to act like the `CLI-Anything` builder.

Before implementation, use the full methodology source of truth when available:

1. If the current workspace is the `CLI-Anything` repository, read `cli-anything-plugin/HARNESS.md`.
2. If Reasonix is running from this adapter directory, also check `../cli-anything-plugin/HARNESS.md`.
3. If neither local file is available, clone or download `cli-anything-plugin` from `https://github.com/HKUDS/CLI-Anything/tree/main/cli-anything-plugin`, then use `HARNESS.md` and the resources around it from that folder.
4. Only if local and network retrieval both fail, follow the condensed rules below.

## Inputs

Accept either:

- A local source path such as `./gimp` or `/path/to/software`
- A GitHub repository URL

Derive the software name from the local directory name after cloning if needed.

## Reasonix Tool Bindings

Reasonix agents build harnesses by combining these built-in tools:

| Reasonix Tool | Role in Harness Workflow |
|---------------|--------------------------|
| `bash` | Run shell commands, install packages, execute CLI tools, run tests, clone repos |
| `write_file` | Generate Python files (Click CLI, backend modules, tests, setup.py) |
| `edit_file` | Make targeted edits to generated code (single replacement) |
| `multi_edit` | Apply multiple atomic edits to a single file in one pass |
| `read_file` | Read target software source files, existing harness code, test results |
| `grep` | Search for patterns across the target software codebase (APIs, CLI tools, data models) |
| `glob` | Find files matching patterns in the source tree (*.py, *.xml, *.json, etc.) |
| `ls` | List directory contents to understand project structure |
| `mcp__codegraph__search` / `mcp__codegraph__context` | Optional code graph analysis when CodeGraph is enabled (Reasonix strips the `codegraph_` raw prefix, so the model-visible names omit it) |
| `web_fetch` | Fetch documentation, API references, or remote files from the web |

### Recommended Workflow with Reasonix Tools

**Phase 1 (Analysis)** — Use `ls` + `glob` to survey the source tree, `grep` to find API surfaces and CLI entry points, and `read_file` to inspect key files. When CodeGraph is enabled and its tools are available, use `mcp__codegraph__search` and `mcp__codegraph__context` for deeper symbol and architecture analysis.

**Phase 2-3 (Design & Implementation)** — Use `write_file` to create new harness files, `edit_file` / `multi_edit` to refine generated code, and `bash` to run `pip install -e .` for installation.

**Phase 4-6 (Testing)** — Use `bash` to run `pytest` and capture results, `read_file` to inspect test output, and `write_file` to update TEST.md.

**Phase 7 (Packaging)** — Use `write_file` for setup.py, `bash` for `pip install -e .` and `which cli-anything-<software>` verification.

## Step Budget

A full harness build typically requires 25–40 tool-call rounds (architecture inspection, 10+ file writes, installation, and multiple test runs). When invoked via `run_skill`, the subagent inherits a step budget derived from the parent agent's `agent.max_steps` setting in `reasonix.toml`:

- If `max_steps = 0` (the default, meaning unlimited), the subagent also runs with no step cap — this is the recommended configuration for the CLI-Anything workflow.
- If `max_steps` is set to a finite value, the subagent receives half that budget (minimum 5), which may truncate a complex build before completion.

Users who have configured a finite `max_steps` should ensure it is set to 0 or a sufficiently high value (e.g., 64 or more) before running a CLI-Anything build, so the subagent has enough rounds to complete all seven phases.

## Modes

### Build

Use when the user wants a new harness.

Produce this structure:

```text
<repo-root>/
├── skills/
│   └── cli-anything-<software>/
│       └── SKILL.md
└── <software>/
    └── agent-harness/
        ├── <SOFTWARE>.md
        ├── setup.py
        └── cli_anything/
            └── <software>/
                ├── README.md
                ├── __init__.py
                ├── __main__.py
                ├── <software>_cli.py
                ├── core/
                ├── utils/
                ├── tests/
                └── skills/
                    └── SKILL.md
```

Implement a stateful Click CLI with:

- one-shot subcommands
- REPL mode as the default when no subcommand is given
- `--json` machine-readable output
- session state with undo/redo where the target software supports it

### Refine

Use when the harness already exists.

First inventory current commands and tests, then do gap analysis against the target software. Prefer:

- high-impact missing features
- easy wrappers around existing backend APIs or CLIs
- additions that compose well with existing commands

Do not remove existing commands unless the user explicitly asks for a breaking change.

### Test

Plan tests before writing them. Keep both:

- `test_core.py` for unit coverage
- `test_full_e2e.py` for workflow and backend validation

When possible, test the installed command via subprocess using `cli-anything-<software>` rather than only module imports.

### Validate

Check that the harness:

- uses the `cli_anything.<software>` namespace package layout
- has an installable `setup.py` entry point
- supports JSON output
- has a REPL default path
- has matching canonical and package-local `SKILL.md` files
- documents usage and tests

## Backend Rules

Prefer the real software backend over reimplementation. Wrap the actual executable or scripting interface in `utils/<software>_backend.py` when possible. Use synthetic reimplementation only when the project explicitly requires it or no viable native backend exists.

## Packaging Rules

- Use `find_namespace_packages(include=["cli_anything.*"])`
- Keep `cli_anything/` as a namespace package without a top-level `__init__.py`
- Expose `cli-anything-<software>` through `console_scripts`
- Include `cli_anything.<software>/skills/SKILL.md` in package data

## Workflow

1. Acquire the source tree locally (clone or use existing path).
2. Analyze architecture, data model, existing CLIs, and GUI-to-API mappings.
3. Design command groups and state model.
4. Implement the harness.
5. Write `TEST.md`, then tests, then run them.
6. Update README usage docs and generate both `skills/cli-anything-<software>/SKILL.md` and `cli_anything/<software>/skills/SKILL.md`.
7. Verify local installation with `pip install -e .`

## Existing Harnesses (Reference)

For an up-to-date list of supported harnesses and their backend patterns, locate `registry.json` at the `CLI-Anything` repository root when it is available.

## Output Expectations

When reporting progress or final results, include:

- target software and source path
- files added or changed
- validation commands run
- open risks or backend limitations
