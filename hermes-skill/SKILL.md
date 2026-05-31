---
name: cli-anything-hermes
description: Use when the user wants Hermes Agent to build, refine, test, or validate a CLI-Anything harness for a GUI application or source repository. Adapts the CLI-Anything methodology to Hermes without changing the generated Python harness format.
---

# CLI-Anything for Hermes Agent

Use this skill when the user wants Hermes Agent to act like the `CLI-Anything` builder.

Before implementation, use the full methodology source of truth when available:

1. If this skill is being used from inside the `CLI-Anything` repository, read `../cli-anything-plugin/HARNESS.md` first.
2. If that local file is unavailable, clone or download `cli-anything-plugin` from `https://github.com/HKUDS/CLI-Anything/tree/main/cli-anything-plugin`, then use `HARNESS.md` and the resources around it from that folder.
3. Only if both local and network retrieval fail, follow the condensed rules below.

## Inputs

Accept either:

- A local source path such as `./gimp` or `/path/to/software`
- A GitHub repository URL

Derive the software name from the local directory name after cloning if needed.

## Hermes Tool Bindings

Hermes agents build harnesses by combining these built-in tools:

| Tool | Role in Harness Workflow |
|------|--------------------------|
| `terminal` | Run shell commands, install packages, execute CLI tools, run tests |
| `execute_code` | Generate and write Python files (Click CLI, backend modules, tests) |
| `delegate_task` | Parallelize analysis or generation subtasks |
| `read_file` / `write_file` | Read and write harness source files |
| `patch` | Make targeted edits to generated code |

Consult the [Hermes Agent documentation](https://github.com/NousResearch/hermes-agent) for the exact tool invocation syntax.

## Modes

### Build

Use when the user wants a new harness.

Produce this structure:

```text
<software>/
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
            └── tests/
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
- documents usage and tests

## Backend Rules

Prefer the real software backend over reimplementation. Wrap the actual executable or scripting interface in `utils/<software>_backend.py` when possible. Use synthetic reimplementation only when the project explicitly requires it or no viable native backend exists.

## Packaging Rules

- Use `find_namespace_packages(include=["cli_anything.*"])`
- Keep `cli_anything/` as a namespace package without a top-level `__init__.py`
- Expose `cli-anything-<software>` through `console_scripts`

## Workflow

1. Acquire the source tree locally (clone or use existing path).
2. Analyze architecture, data model, existing CLIs, and GUI-to-API mappings.
3. Design command groups and state model.
4. Implement the harness.
5. Write `TEST.md`, then tests, then run them.
6. Update README usage docs.
7. Verify local installation with `pip install -e .`

## Existing Harnesses (Reference)

For an up-to-date list of supported harnesses and their backend patterns, see [`registry.json`](../registry.json) at the repository root.

## Output Expectations

When reporting progress or final results, include:

- target software and source path
- files added or changed
- validation commands run
- open risks or backend limitations
