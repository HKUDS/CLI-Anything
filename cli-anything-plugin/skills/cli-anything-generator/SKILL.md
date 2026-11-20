---
name: cli-anything-generator
description: >-
  Use when the user wants to build, refine, test, validate, or list CLI-Anything
  harnesses for GUI applications or source repositories. Points Codex at the
  generator workflow already defined in this plugin's HARNESS.md and commands/.
---

# CLI-Anything Generator (Codex Plugin Skill)

This skill is packaged inside the **cli-anything** generator plugin so selecting
`cli-anything@cli-anything` installs a Codex-readable entry point. It does not
replace the methodology docs — it routes you to them.

## Read the Methodology First

Resolve paths relative to this plugin root (the directory that contains
`HARNESS.md`, `commands/`, and `skills/`):

1. Read `HARNESS.md` — complete methodology, architecture, and quality rules.
2. Read the matching mode file under `commands/`.
3. Read files under `guides/` only when they apply to the target.
4. Use helper scripts at the plugin root: `skill_generator.py`, `repl_skin.py`,
   `preview_bundle.py`, and `templates/SKILL.md.template`.

Do not invent a different harness format. Follow HARNESS.md and the command
specs below.

## Modes

| Goal | Spec |
|------|------|
| Full 7-phase build | `commands/cli-anything.md` |
| Expand coverage | `commands/refine.md` |
| Run tests | `commands/test.md` |
| Validate checklist | `commands/validate.md` |
| List tools | `commands/list.md` |

If the user speaks naturally ("build a CLI for ./gimp"), run the same workflow
as the matching mode.

## Inputs

Accept either a local source path (`./gimp`, `/path/to/software`) or a GitHub
repository URL. Derive the software name from the local directory name after
cloning if needed.

## Phase Gates

For build/refine/test/validate, maintain
`{software-root}/agent-harness/.cli-anything-progress.json`. Create
`agent-harness/` when tracking starts. Do not advance without completing the
previous phase. Resume non-terminal runs.

## Quality Bar

Match the Claude Code plugin / standalone Codex skill output: same harness
layout, namespace packaging (`cli_anything.<software>`), `--json`, tests, and
skill generation into `skills/cli-anything-<software>/SKILL.md`.
