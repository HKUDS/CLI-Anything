# Google Antigravity Tooling Notes for CLI-Anything

Operational runbook behind the `/cli-anything*` skills. Read when coordinating
large builds, wiring newly generated CLI skills into Antigravity App/CLI/IDE,
bridging `cli-hub matrix` workflows, or troubleshooting host issues.

## 1. Where Things Live Across Antigravity Surfaces

| Surface | Global Plugins | Global Skills | Workspace Plugins / Skills |
|---|---|---|---|
| **Antigravity App** | `~/.gemini/config/plugins/` | `~/.gemini/config/skills/` | `<repo>/.agents/plugins/`, `<repo>/.agents/skills/` |
| **Antigravity CLI (`agy`)** | `~/.gemini/config/plugins/` | `~/.gemini/config/skills/` (+ `~/.gemini/skills/`) | `<repo>/.agents/plugins/`, `<repo>/.agents/skills/` |
| **Antigravity IDE** | `~/.gemini/config/plugins/` | `~/.gemini/config/skills/` | `<repo>/.agents/plugins/`, `<repo>/.agents/skills/` |

- **Official CLI install (standalone / Community Edition):**
  ```bash
  agy plugin install https://github.com/DIIIUA/cli-anything-antigravity
  agy plugin validate --strict ~/.gemini/config/plugins/cli-anything
  agy plugin list --json
  ```
- **Monorepo install (vendors canonical `cli-anything-plugin/` + `docs/PREVIEW_PROTOCOL.md`):**
  ```bash
  bash antigravity-plugin/scripts/install.sh            # or --workspace <repo>, --force, --dry-run
  # Windows PowerShell:
  .\antigravity-plugin\scripts\install.ps1              # or -Workspace <repo>, -Force, -DryRun
  ```
- Newly installed plugins are auto-discovered on the next turn without a full
  Antigravity App restart.

## 2. Making Generated Harness Skills & `cli-hub` Matrices Visible in Antigravity

A subtle path mismatch exists between upstream defaults and Antigravity App:

- `repl_skin.py` defaults `CLI_ANYTHING_GLOBAL_SKILLS_DIR` to `~/.agents/skills/`.
- `cli-hub matrix install <matrix>` renders matrix skills into `~/.cli-hub/matrix/<name>/SKILL.md`.
- **Antigravity App** discovers global skills under `~/.gemini/config/skills/` (and workspace skills under `<repo>/.agents/skills/`), not `~/.agents/skills/` or `~/.cli-hub/matrix/`.

To make your generated `cli-anything-<software>` skills and installed `cli-hub`
matrices immediately discoverable in Antigravity:

1. **For a single workspace (recommended for repo work):**
   Copy or keep `skills/cli-anything-<software>/SKILL.md` under `<repo>/.agents/skills/cli-anything-<software>/SKILL.md`, or register the repo's `skills/` directory in `<repo>/.agents/skills.json`.
2. **Globally across all Antigravity sessions via native `~/.gemini/config/skills.json`:**
   ```json
   {
     "entries": [
       { "path": "~/.cli-hub/matrix" },
       { "path": "~/.agents/skills" }
     ]
   }
   ```
   This zero-copy native Antigravity config automatically exposes every
   `cli-hub matrix install` workflow (`video-creation`, `3d-cad`, `image-design`,
   `game-development`, `knowledge-research`) and any skills installed via
   `npx skills add ... -g` inside Antigravity App, CLI, and IDE.
3. **Or copy directly to global skills:**
   `~/.gemini/config/skills/cli-anything-<software>/SKILL.md` (and set
   `CLI_ANYTHING_GLOBAL_SKILLS_DIR=~/.gemini/config/skills` if you want
   `ReplSkin` banners to point there).

## 3. Scaling & Delegation Recipes in Antigravity

A full 7-phase harness build typically requires 25–40 tool rounds:

- **Single focused app (1–3 command groups):** Run `/cli-anything <path>` directly
  in one session (use `/goal` if you want uninterrupted autonomous execution
  through Phase 7).
- **Large codebase analysis (Phase 1) or independent audit:** Delegate read-only
  exploration to the built-in `research` subagent or the bundled
  `cli-anything-auditor` agent so raw file reads do not bloat the main context.
- **Large app (4+ independent command groups):** Use `/swarm` (or parallel
  subagents) with strict **one file, one owner** discipline:
  1. Coordinator finishes Phases 0–2 and writes `setup.py`, `core/project.py`,
     `core/session.py`, and shared `utils/*` first.
  2. Each worker owns one independent command group module (`core/<domain>.py` +
     its unit tests) and reports back with passing `pytest` counts.
  3. Coordinator integrates `<software>_cli.py`, installs with `pip install -e .`,
     runs full E2E + `CLI_ANYTHING_FORCE_INSTALLED=1`, and runs `verify_harness.py`.
     **Never delegate final contract verification blindly.**

## 4. Permissions, Sandbox & Host Prerequisites

- **Python >= 3.10**, `click`, `pytest`, `jinja2` (for `skill_generator.py`),
  and optional `prompt_toolkit` (enhanced REPL history & prompt styling).
- **Real backend required:** Verify the target application binary is actually
  installed on the host before claiming E2E readiness (`Get-Command <app>` on
  Windows, `command -v <app>` on macOS/Linux).
- **Antigravity Sandbox / Non-Workspace Access:** Cloning an external repo or
  invoking an installed desktop binary outside the workspace may prompt for
  permission depending on your **Non-Workspace File Access** and **Terminal
  Sandbox** settings. Never store API keys or tokens in harness source, tests,
  or `TEST.md` — read credentials strictly from environment variables.

## 5. Bundled Deterministic Scripts Reference

```bash
# Verify one or more harnesses (human output, JSON, strict, or full monorepo)
python "{PLUGIN_ROOT}/scripts/verify_harness.py" ./gimp
python "{PLUGIN_ROOT}/scripts/verify_harness.py" ./gimp --strict --json
python "{PLUGIN_ROOT}/scripts/verify_harness.py" --all --json

# List installed + locally generated harnesses
python "{PLUGIN_ROOT}/scripts/list_harnesses.py" --path . --depth 2
python "{PLUGIN_ROOT}/scripts/list_harnesses.py" --json --include-hub
```

## 6. Failure Playbook (Windows & POSIX)

| Symptom | Root cause | Fix |
|---|---|---|
| `ModuleNotFoundError: cli_anything` | Top-level `cli_anything/__init__.py` exists or `setup.py` used `find_packages()` | Delete `cli_anything/__init__.py`; switch to `find_namespace_packages(include=["cli_anything.*"])` and reinstall with `pip install -e .` |
| `CLI_ANYTHING_FORCE_INSTALLED=1 python ...` fails in Windows PowerShell | POSIX inline env syntax is invalid in `pwsh` | Use `$env:CLI_ANYTHING_FORCE_INSTALLED = "1"; python -m pytest ...` |
| `UnicodeEncodeError` / garbled box-drawing chars on Windows | Default Windows console/file codepage (CP1251/CP1252/GBK) | Pass `encoding="utf-8"` to all file I/O and reconfigure stdio to UTF-8 |
| Tests pass, but `cli-anything-<app> --help` fails | Imports only worked from repo CWD, package not installed | Run `pip install -e .` and verify via `CLI_ANYTHING_FORCE_INSTALLED=1` from another directory |
| `verify_harness.py` flags `repl-skin` drift | Harness copy of `utils/repl_skin.py` was modified | Recopy `{PLUGIN_ROOT}/scripts/repl_skin.py` verbatim |
| `verify_harness.py` flags truncated `...` in `SKILL.md` description or template examples fail | `skill_generator.py` clipped a long README intro or emitted generic `-p project.json` examples | Review and rewrite the frontmatter `description`, real CLI flags (`--project`), REPL commands, and JSON error channel in **both** canonical and packaged `SKILL.md` |
| `prompt_toolkit` raises `NoConsoleScreenBufferError` on Windows REPL | Piped/non-TTY stdin in `run_command` has no Win32 console buffer | Guard `skin.create_prompt_session()` behind `sys.stdin.isatty() and sys.stdout.isatty()` with fallback to `pt_session = None` |
| Wildcard arguments like `"*.tmp"` expand to unrelated CWD files on Windows | Click defaults to `windows_expand_args=True` on Windows | Invoke `cli(windows_expand_args=False)` in `main()` (and `cli.main(..., windows_expand_args=False)` in REPL) when commands accept globs or exclusion patterns |
| Generated CLI skill does not appear in Antigravity App | Skill only sits in `agent-harness/...` or `~/.agents/skills/` | Copy to `~/.gemini/config/skills/cli-anything-<app>/SKILL.md` or add its root to `~/.gemini/config/skills.json` |
| E2E tests skip silently | Target backend binary missing or `pytest.skip` used | Install the real backend; remove silent skip guards per `HARNESS.md` |
