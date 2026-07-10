---
name: "cli-anything-openrefine"
description: "Use OpenRefine through an agent-native CLI for importing messy data, applying JSON operation histories, inspecting rows, exporting cleaned data, and managing session undo/redo."
contributor: "CLI-Anything-Team"
---

# CLI-Anything OpenRefine

Use this skill when a task needs OpenRefine data cleaning, transformation, reusable operation histories, or CSV/TSV export from an automated agent workflow.

## Prerequisites

Install the harness:

```bash
cd openrefine/agent-harness
python -m pip install -e .
```

Start OpenRefine before backend commands:

```bash
openrefine -i 127.0.0.1 -p 3333
```

Set a custom server with `OPENREFINE_URL=http://127.0.0.1:3333` or pass `--base-url`.

## Command Rules For Agents

- Prefer `--json` on every one-shot command.
- Use `--session <path>` for isolated task state.
- Import or open a project before row, apply, export, undo, or redo commands.
- Existing OpenRefine operation-history JSON can be passed directly to `data apply`.
- Generated files are normal OpenRefine operation JSON and exported CSV/TSV data.

## Common Commands

```bash
cli-anything-openrefine --json server ping
cli-anything-openrefine --json project list
cli-anything-openrefine --json --session run/session.json project import messy.csv --name cleanup
cli-anything-openrefine --json --session run/session.json data rows --limit 10
cli-anything-openrefine --json ops text-transform run/trim.json --column Name --expression 'value.trim()'
cli-anything-openrefine --json --session run/session.json data apply run/trim.json
cli-anything-openrefine --json --session run/session.json data export run/clean.csv --format csv
cli-anything-openrefine --json --session run/session.json session undo
cli-anything-openrefine --json --session run/session.json session redo
```

## REPL

Run `cli-anything-openrefine` with no subcommand to enter the REPL.

## Error Handling

When `--json` is set, command failures write a JSON object to stderr with `ok: false`.
