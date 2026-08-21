---
name: cli-anything-generator
description: >-
  Build, refine, test, validate, or list CLI-Anything harnesses for GUI
  applications in Cursor. Prefer slash commands /cli-anything,
  /cli-anything-refine, /cli-anything-test, /cli-anything-validate, and
  /cli-anything-list when available. This skill supports natural-language
  discovery of the generator; it does not replace those commands. Discovering
  already-published CLIs from CLI-Hub is a separate consumer skill
  (cli-hub-meta-skill).
---

# CLI-Anything Generator (Cursor Plugin Skill)

This skill is packaged **inside the Cursor plugin** as a supporting entry point.
The primary generator UX is the plugin slash commands.

## Prefer Slash Commands

| Goal | Command |
|------|---------|
| Full 7-phase build | `/cli-anything <path-or-repo>` |
| Expand coverage | `/cli-anything-refine <path> [focus]` |
| Run tests | `/cli-anything-test <path>` |
| Validate checklist | `/cli-anything-validate <path>` |
| List tools | `/cli-anything-list` |

If the user speaks naturally ("build a CLI for ./gimp"), run the same workflow as the matching command.

## Consumer Path (Separate)

This skill is **not** the Hub consumer. For finding/installing published CLIs:

```bash
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y
```

Per-app skills live under the repo `skills/` tree and install via `npx skills add`.

## PLUGIN_ROOT and Methodology

1. Resolve `PLUGIN_ROOT` via discovery pointer then stamp:
   - `~/.cursor/cli-anything-generator.root` / `%USERPROFILE%\.cursor\cli-anything-generator.root`
   - `{install}/PLUGIN_ROOT.txt`
   - default `~/.cursor/plugins/local/cli-anything` if `references/HARNESS.md` exists there
2. Read `{PLUGIN_ROOT}/references/HARNESS.md` with an absolute path.
3. Read the matching file under `{PLUGIN_ROOT}/references/commands/`.
4. Use guides under `{PLUGIN_ROOT}/references/guides/` on demand.
5. Helper scripts: `{PLUGIN_ROOT}/scripts/repl_skin.py`, `preview_bundle.py`,
   `skill_generator.py`, `templates/`.

### Path remapping (from HARNESS / plugin docs)

| Document reference | Installed plugin path |
|--------------------|----------------------|
| `guides/...` | `references/guides/...` |
| `cli-anything-plugin/repl_skin.py` | `scripts/repl_skin.py` |
| `cli-anything-plugin/preview_bundle.py` | `scripts/preview_bundle.py` |
| `cli-anything-plugin/skill_generator.py` | `scripts/skill_generator.py` |
| `templates/SKILL.md.template` | `scripts/templates/SKILL.md.template` |
| `docs/PREVIEW_PROTOCOL.md` | `references/docs/PREVIEW_PROTOCOL.md` |

## Cursor Tool Bindings

| Cursor tool | Role |
|-------------|------|
| Read | Methodology and source analysis |
| Grep / Glob | API and file discovery |
| Shell | Clone, pytest, pip, CLI invocation |
| Write / StrReplace | Harness implementation |
| Task | Optional parallel subtasks |

## Phase Gates

For build/refine/test/validate, maintain
`{software-root}/agent-harness/.cli-anything-progress.json`.
Create `agent-harness/` when tracking starts. Do not advance without completing
the previous phase. Resume non-terminal runs.

## Quality Bar

Match Claude Code plugin / Codex skill output: same harness layout, namespace
packaging, `--json`, tests, and skill generation. Do not invent a different
harness format.
