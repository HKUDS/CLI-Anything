---
name: cli-anything
description: Build, refine, test, validate, or inventory agent-usable CLI harnesses for software codebases with the CLI-Anything methodology. Use this skill when a request involves turning a GUI app, desktop tool, web service SDK, or existing codebase into a stateful CLI under agent-harness/, or when extending an existing cli-anything-* harness.
---

# CLI-Anything

## Overview

Use this skill when your agent runtime supports local skills and you want to apply the CLI-Anything methodology without relying on slash-command plugins. It complements the existing plugin flow and uses the same source of truth: [`references/HARNESS.md`](references/HARNESS.md).

## Core Workflow

1. Choose the task mode first:
   - Build a new harness from a source tree or repository: [`references/commands/cli-anything.md`](references/commands/cli-anything.md)
   - Expand coverage of an existing harness: [`references/commands/refine.md`](references/commands/refine.md)
   - Run or update tests for an existing harness: [`references/commands/test.md`](references/commands/test.md)
   - Validate an implementation against the standard: [`references/commands/validate.md`](references/commands/validate.md)
   - Inventory generated or installed harnesses: [`references/commands/list.md`](references/commands/list.md)
2. Read [`references/HARNESS.md`](references/HARNESS.md) before changing code. It defines the architecture, testing, packaging, and backend integration rules.
3. Preserve the generated layout `<software>/agent-harness/cli_anything/<software>/...` and package name `cli-anything-<software>`.
4. Use the real software backend for rendering and export. Do not replace the target application with toy Python reimplementations.
5. Reuse existing harnesses in this repository as examples before inventing a new structure.

## Repository Examples

- `anygen/agent-harness/` for cloud API backed workflows.
- `gimp/agent-harness/`, `blender/agent-harness/`, and `inkscape/agent-harness/` for GUI-to-CLI mappings.
- `libreoffice/agent-harness/` for document generation and real headless export.
- `cli-anything-plugin/repl_skin.py` as the shared REPL presentation layer that generated harnesses can copy into `utils/repl_skin.py`.

## Notes

- The repository supports both the original plugin flow and the repo-local skill flow.
- Do not assume slash commands such as `/cli-anything` exist in the current runtime. Translate the command references into normal agent execution steps.
- If the request is only about using an already-generated CLI, prefer the installed `cli-anything-<software>` command instead of regenerating the harness.
