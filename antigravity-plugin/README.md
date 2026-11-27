# CLI-Anything Google Antigravity Plugin

Native **Google Antigravity** plugin adapter delivering the complete
**CLI-Anything generator** across all Antigravity surfaces (Antigravity App,
Antigravity CLI `agy`, and Antigravity IDE) while keeping the **consumer**
track (CLI-Hub, `cli-hub-meta-skill`, and per-app skills) separate and intact.

This is a first-class **Antigravity plugin** (`plugin.json` v1 schema, 5
focused slash-command skills, glob-scoped rule, read-only auditor subagent,
optional PEP 420 lifecycle hook, and deterministic contract verifier) — not a
`.claude-plugin` or `.cursor-plugin` copy.

## Two Tracks

| Track | What you get | How |
|---|---|---|
| **Generator** (this plugin) | `/cli-anything`, `/cli-anything-refine`, `/cli-anything-test`, `/cli-anything-validate`, `/cli-anything-list` + `cli-anything-auditor` + `verify_harness.py` | Install this plugin |
| **Consumer** (unchanged) | Find, install, and invoke published CLIs & matrices from CLI-Hub | `npx skills` + `cli-hub` |

```bash
# Consumer (unchanged Hub path)
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y
pip install cli-anything-hub

# Generator — Option A: from the HKUDS/CLI-Anything monorepo
bash antigravity-plugin/scripts/install.sh
# Windows PowerShell:
#   .\antigravity-plugin\scripts\install.ps1

# Generator — Option B: direct install via Antigravity CLI (Community Edition mirror)
agy plugin install https://github.com/DIIIUA/cli-anything-antigravity
```

Antigravity auto-discovers installed plugins on the next turn (no full app
restart required).

## Slash Commands & Components

| Component | Path | Purpose |
|---|---|---|
| `/cli-anything` | `skills/cli-anything/SKILL.md` | Full 7-phase harness build + Phase 6.5 `SKILL.md` + Preview Bundle Protocol |
| `/cli-anything-refine` | `skills/cli-anything-refine/SKILL.md` | Incremental gap analysis & coverage expansion (optional `[focus]`) |
| `/cli-anything-test` | `skills/cli-anything-test/SKILL.md` | Unit + real-backend E2E + `CLI_ANYTHING_FORCE_INSTALLED=1` + `TEST.md` |
| `/cli-anything-validate` | `skills/cli-anything-validate/SKILL.md` | Mechanical `verify_harness.py` check + full 52-check `validate.md` audit |
| `/cli-anything-list` | `skills/cli-anything-list/SKILL.md` | Deterministic `list_harnesses.py` scan (`--path`, `--depth`, `--json`) |
| **Glob Rule** | `rules/cli-anything-generator.md` | `trigger: glob` on `**/agent-harness/**, **/.cli-anything-progress.json, **/cli_anything/**` (0 tokens in unrelated chats) |
| **Auditor Agent** | `agents/cli-anything-auditor.md` | Read-only Phase 1 codebase analyst & independent contract auditor (`subagent` + `mainAgent`) |
| **PEP 420 Hook** | `hooks.json` + `scripts/pep420_guard.py` | Opt-in (`"enabled": false` by default) `PreToolUse` guard blocking accidental `cli_anything/__init__.py` creation |
| **Tooling Runbook** | `references/antigravity-tooling.md` | Surface paths, `~/.gemini/config/skills.json` bridge for `cli-hub matrix` & new CLI skills, `/goal`/`/swarm` recipes, Failure Playbook |

### Deterministic Scripts

```bash
# Verify a harness mechanically (supports --strict, --json, --all)
python scripts/verify_harness.py ./gimp
python scripts/verify_harness.py --all --json

# List installed + locally generated harnesses
python scripts/list_harnesses.py --path . --depth 2 --json
```

## Install Options

- **Global install (default):** `~/.gemini/config/plugins/cli-anything`
  (override root via `ANTIGRAVITY_PLUGINS_HOME` pointing at a directory named
  `plugins`). Writes `{install}/PLUGIN_ROOT.txt` and
  `~/.gemini/cli-anything-generator.root`.
- **Workspace install:** `--workspace <repo>` / `-Workspace <repo>` installs to
  `<repo>/.agents/plugins/cli-anything` without touching the global discovery
  pointer.
- **Dry-run preview:** `--dry-run` / `-DryRun` validates prerequisites and
  prints the exact install plan without writing files.
- **Upgrade / Reinstall:** `--force` / `-Force` performs a locked, pre-verified
  (byte-equality + `py_compile`) atomic replacement with automatic rollback on
  failure.
- **Uninstall:**
  ```bash
  bash antigravity-plugin/scripts/uninstall.sh             # or --workspace <repo>
  # PowerShell:
  .\antigravity-plugin\scripts\uninstall.ps1               # or -Workspace <repo>
  ```

### Recovery from Interrupted Runs

- If a `--force` upgrade is killed mid-swap, look for `.cli-anything.bak.*`
  next to the install directory and rename it back to `cli-anything`.
- If an installer process is force-killed while holding the lock, remove the
  stale `.cli-anything.lock` directory/file inside the target `plugins/` folder.

## How Vendoring Works

Source of truth stays in `cli-anything-plugin/` and `docs/PREVIEW_PROTOCOL.md`
— canonical files are never duplicated in Git under `antigravity-plugin/`. At
install time, `install.sh` / `install.ps1` vendors:

- `references/HARNESS.md`, `references/commands/*.md`, `references/guides/*.md`, `references/docs/PREVIEW_PROTOCOL.md`
- `scripts/repl_skin.py`, `scripts/preview_bundle.py`, `scripts/skill_generator.py`, `scripts/templates/SKILL.md.template`

alongside Antigravity-native `references/antigravity-tooling.md` and
`scripts/{verify_harness.py, list_harnesses.py, pep420_guard.py}`.

## Tests

```bash
# Installer regression tests (Linux / macOS / Git Bash)
bash antigravity-plugin/tests/test_install.sh

# Installer regression tests (Windows PowerShell)
.\antigravity-plugin\tests\test_install.ps1

# Deterministic verifier, lister, PEP 420 guard & concurrent install race tests
python -m pytest antigravity-plugin/tests/test_verify_harness.py antigravity-plugin/tests/test_install_race.py -v
```

CI: `.github/workflows/check-antigravity-plugin.yml` (Ubuntu bash + Python +
Windows PowerShell + Python).
