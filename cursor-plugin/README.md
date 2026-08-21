# CLI-Anything Cursor Plugin

Cursor Desktop adapter that delivers the **full generator** (slash commands + vendored `cli-anything-plugin` methodology) while keeping the **consumer** path (CLI-Hub / meta-skill / per-app skills) separate and intact.

This is a real **Cursor plugin** (`.cursor-plugin/plugin.json`), not a Claude Code `.claude-plugin` copy and not a skill-only substitute.

## Two tracks

| Track | What you get | How |
|-------|----------------|-----|
| **Generator** | `/cli-anything`, refine / test / validate / list | Install this plugin |
| **Consumer** | Find/install/use published CLIs | `npx skills` + `cli-hub` |

```bash
# Consumer (unchanged Hub path)
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y

# Generator (this plugin)
bash cursor-plugin/scripts/install.sh
# Windows:
#   .\cursor-plugin\scripts\install.ps1
```

Then **Developer: Reload Window** in Cursor and run:

```text
/cli-anything ./your-software
/cli-anything-refine ./your-software "focus area"
/cli-anything-test ./your-software
/cli-anything-validate ./your-software
/cli-anything-list
```

## Install details

Default destination:

```text
~/.cursor/plugins/local/cli-anything
```

`CURSOR_PLUGINS_HOME` must resolve to a directory **named** `plugins` (example: `~/.cursor/plugins`). The installer writes:

| File | Purpose |
|------|---------|
| `{install}/PLUGIN_ROOT.txt` | Absolute plugin root stamp |
| `~/.cursor/cli-anything-generator.root` | Discovery pointer for Cursor agents (always under the user `.cursor` dir) |

Upgrade / reinstall:

```bash
bash cursor-plugin/scripts/install.sh --force
# PowerShell: .\cursor-plugin\scripts\install.ps1 -Force
```

Uninstall (removes `.../plugins/local/cli-anything` and clears `~/.cursor/cli-anything-generator.root` when it points at that install):

```bash
bash cursor-plugin/scripts/uninstall.sh
# PowerShell: .\cursor-plugin\scripts\uninstall.ps1
```

If a `--force` upgrade is interrupted after the old install was moved aside, look for
`~/.cursor/plugins/local/.cli-anything.bak.*` and rename it back to `cli-anything`.

The installer vendors from repo `cli-anything-plugin/` + `docs/PREVIEW_PROTOCOL.md` into the installed plugin (`references/`, helper `scripts/`). Source of truth remains `cli-anything-plugin/`.

On Windows, `install.sh` (Git Bash) converts stamps to `C:\...` host paths via `cygpath` when available so Cursor tools can resolve them.

### Local plugin loading notes

- Ensure third-party / local plugins are allowed in Cursor settings.
- Prefer a physical copy (this installer); avoid symlinks.
- Enterprise orgs may need “Allow Local Plugin Imports”.

Repo also ships [`.cursor-plugin/marketplace.json`](../.cursor-plugin/marketplace.json) for marketplace-style discovery of `./cursor-plugin`.

## Quality bar

Same harness output as Claude Code / Codex: HARNESS-driven 7 phases, `cli_anything.<software>` namespace, `--json`, tests, packaging, skill generation.

Cursor-specific additions:

- Machine-discoverable `PLUGIN_ROOT` (stamp + discovery pointer)
- Explicit Cursor tool bindings
- Generator rule (on-demand via globs / description, not always-on) + progress at
  `{software}/agent-harness/.cli-anything-progress.json`
- `uninstall.sh` / `uninstall.ps1` to remove the local plugin and matching discovery pointer
- Shared `scripts/lib.sh` / `scripts/lib.ps1` for path validation and host-path conversion

Prefer the uninstall scripts over manually deleting folders so the discovery pointer
does not go stale.

## Tests

```bash
bash cursor-plugin/tests/test_install.sh
```

Windows:

```powershell
.\cursor-plugin\tests\test_install.ps1
```

CI: `.github/workflows/check-cursor-plugin.yml` (Ubuntu bash + Windows PowerShell).
