---
name: cli-anything
description: >-
  Build a complete, stateful CLI-Anything harness for any GUI application or
  source repository in Google Antigravity (all 7 phases, Phase 6.5 SKILL.md
  generation, Preview Bundle Protocol, and PEP 420 namespace packaging).
  Invoked automatically or explicitly via /cli-anything <path-or-repo>.
  For refining, testing, validating, or listing existing harnesses use
  /cli-anything-refine, /cli-anything-test, /cli-anything-validate, or
  /cli-anything-list. Discovering published CLIs from CLI-Hub remains the
  separate consumer skill (cli-hub-meta-skill).
---

# `/cli-anything` — Build a Complete CLI-Anything Harness

Build a production-ready, stateful CLI harness for any GUI application using
the canonical 7-phase `CLI-Anything` methodology without altering the Python
harness format.

> **Two-track separation:** This plugin is the **Generator** track. Discovering
> and installing already-published CLIs from CLI-Hub remains on the separate
> **Consumer** track (`npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y`
> + `pip install cli-anything-hub`).

## 1. Resolve `PLUGIN_ROOT` (Absolute Paths Only)

Never resolve `./HARNESS.md` against the user's workspace root. Resolve
`PLUGIN_ROOT` in this order and stop at the first path where
`{PLUGIN_ROOT}/references/HARNESS.md` exists:

1. **Active skill parent (works for `agy plugin install`, global, and workspace installs):**
   Take the absolute path to this `SKILL.md` and go up two directories
   (`.../plugins/cli-anything/skills/cli-anything/SKILL.md` -> `.../plugins/cli-anything`).
2. **Global discovery pointer** (single-line absolute path):
   - Windows: `%USERPROFILE%\.gemini\cli-anything-generator.root`
   - macOS / Linux: `~/.gemini/cli-anything-generator.root`
3. **Standard plugin directories** (`{dir}/PLUGIN_ROOT.txt` or `{dir}` directly):
   - Workspace: `{workspace}/.agents/plugins/cli-anything`
   - Custom: `$ANTIGRAVITY_PLUGINS_HOME/cli-anything`
   - Global: `~/.gemini/config/plugins/cli-anything` (`%USERPROFILE%\.gemini\config\plugins\cli-anything`)
4. **Monorepo fallback:** `{workspace}/cli-anything-plugin` (if inside a `CLI-Anything` checkout).
5. **Remote fallback:** clone `https://github.com/HKUDS/CLI-Anything` and read `cli-anything-plugin/`.

## 2. Read the Canonical Methodology First

1. Read `{PLUGIN_ROOT}/references/HARNESS.md` using `read_file` (absolute path).
2. Read `{PLUGIN_ROOT}/references/commands/cli-anything.md`.
3. Read `{PLUGIN_ROOT}/references/antigravity-tooling.md` for Antigravity
   surface paths, `skills.json` registration, delegation recipes, and the
   failure playbook.
4. Read guides under `{PLUGIN_ROOT}/references/guides/` and
   `{PLUGIN_ROOT}/references/docs/PREVIEW_PROTOCOL.md` on demand when they
   apply to the target software.

### Path Remapping Table

| Canonical reference | Installed plugin path |
|---|---|
| `./HARNESS.md` | `{PLUGIN_ROOT}/references/HARNESS.md` |
| `guides/...` | `{PLUGIN_ROOT}/references/guides/...` |
| `docs/PREVIEW_PROTOCOL.md` | `{PLUGIN_ROOT}/references/docs/PREVIEW_PROTOCOL.md` |
| `cli-anything-plugin/repl_skin.py` | `{PLUGIN_ROOT}/scripts/repl_skin.py` |
| `cli-anything-plugin/preview_bundle.py` | `{PLUGIN_ROOT}/scripts/preview_bundle.py` |
| `cli-anything-plugin/skill_generator.py` | `{PLUGIN_ROOT}/scripts/skill_generator.py` |
| `templates/SKILL.md.template` | `{PLUGIN_ROOT}/scripts/templates/SKILL.md.template` |

## 3. Arguments

- **Required:** a **local source path** (e.g., `./gimp`, `D:\src\blender`,
  `/home/user/inkscape`) or a **GitHub repository URL**
  (`https://github.com/org/repo`).
- Bare software names (e.g., `"gimp"`) are NOT accepted — clone the repo or
  locate the local source first and derive the software name from the directory.

## 4. Antigravity Tool Bindings & Orchestration

| Antigravity tool / feature | Role in Build |
|---|---|
| `read_file` | Read `HARNESS.md`, guides, target source, and generated modules |
| `write_file` / `edit_file` | Create `agent-harness/`, `core/`, `utils/`, `tests/`, `setup.py`, `<SOFTWARE>.md`, `TEST.md`, `README.md` |
| `run_command` | Clone repos, run `pytest`, `pip install -e .`, `skill_generator.py`, `verify_harness.py`, verify PATH |
| `invoke_subagent` (`research` / `cli-anything-auditor`) | Parallel read-only survey of large codebases (Phase 1) and independent contract audit before completion |
| `update_steps` / `update_focus` | Mirror live phase progress in Antigravity UI alongside `.cli-anything-progress.json` |

> **Long builds:** A full 7-phase harness typically takes 25–40 tool rounds.
> For large applications with 4+ independent command groups, consult
> `{PLUGIN_ROOT}/references/antigravity-tooling.md` for `/goal`, `/swarm`, and
> subagent delegation recipes (*one file, one owner*; never delegate final
> verification blindly). Never screen-scrape GUI windows with the `browser`
> subagent for previews — follow `PREVIEW_PROTOCOL.md`.

## 5. Hard Phase Gates & Resume

Persist progress at `{software-root}/agent-harness/.cli-anything-progress.json`
(create `agent-harness/` as soon as tracking begins):

```json
{
  "software": "<name>",
  "mode": "build",
  "target": "<absolute software path>",
  "phases": {
    "0": { "status": "completed", "updated_at": "<ISO-8601 UTC>" },
    "1": { "status": "in_progress", "updated_at": "<ISO-8601 UTC>" }
  },
  "terminal": false,
  "terminal_status": null
}
```

- Phases: `0` (source) -> `1` (codebase analysis) -> `2` (architecture & `<SOFTWARE>.md`) -> `3` (implementation + `repl_skin.py` + auto-save/`--dry-run` + locked session JSON) -> `4` (test plan in `TEST.md`) -> `5` (`test_core.py` + `test_full_e2e.py` with `_resolve_cli`) -> `6` (run `pytest` & append passing results to `TEST.md`) -> `6.5` (generate canonical + packaged `SKILL.md` via `{PLUGIN_ROOT}/scripts/skill_generator.py`) -> `7` (PEP 420 `setup.py`, `pip install -e .`, PATH verification, deterministic contract check).
- Do not start phase `N+1` until phase `N` is marked `completed`.
- If a non-terminal progress file exists for this target, **resume** from the first incomplete phase unless the user requests a clean rebuild.
- Before marking `terminal: true`, run the deterministic contract verifier:

```bash
python "{PLUGIN_ROOT}/scripts/verify_harness.py" "<software-root>/agent-harness"
```

## 6. Cross-Platform Notes (Windows PowerShell & POSIX)

- Never hardcode `/root/cli-anything/` — always derive from the target path.
- Force-installed subprocess verification:
  - Windows (`pwsh`): `$env:CLI_ANYTHING_FORCE_INSTALLED = "1"; python -m pytest cli_anything/<software>/tests/ -v -s`
  - macOS / Linux: `CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s`
- PATH verification: `Get-Command cli-anything-<software>` (Windows) or `command -v cli-anything-<software>` (POSIX).
- Always specify `encoding="utf-8"` when reading/writing JSON, XML, `TEST.md`, and `SKILL.md`.
- On Windows, guard `ReplSkin.create_prompt_session()` with `sys.stdin.isatty() and sys.stdout.isatty()` (falling back to `None` in piped/agent terminals) and pass `windows_expand_args=False` to Click `cli()` if commands accept wildcard patterns.
- After Phase 6.5 (`skill_generator.py`), review and verify the generated examples and YAML `description` in **both** canonical (`skills/cli-anything-<software>/SKILL.md`) and packaged (`cli_anything/<software>/skills/SKILL.md`) copies, and explain how to expose the skill to Antigravity (see `{PLUGIN_ROOT}/references/antigravity-tooling.md`).

## 7. Output Expectations

Report: target software and resolved paths, completed phases and progress file
state, files created, `pytest` and `verify_harness.py` results, installed PATH
command, generated `SKILL.md` paths, and any backend limitations.
