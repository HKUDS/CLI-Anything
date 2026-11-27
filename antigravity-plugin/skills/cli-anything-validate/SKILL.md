---
name: cli-anything-validate
description: >-
  Validate a CLI-Anything harness against the full HARNESS.md and validate.md
  contract using the deterministic verify_harness.py script plus manual code
  and test audit. Invoked via /cli-anything-validate <path-or-repo>.
---

# `/cli-anything-validate` — Contract Verification & 52-Check Audit

Audit an existing CLI harness mechanically and thoroughly against `HARNESS.md`,
`commands/validate.md`, and `CONTRIBUTING.md` without lowering the quality bar.

## 1. Resolve `PLUGIN_ROOT` and Read Canonical Spec

Resolve `PLUGIN_ROOT` (two levels up from this `SKILL.md`, or discovery pointer
`~/.gemini/cli-anything-generator.root`, or `~/.gemini/config/plugins/cli-anything`
where `references/HARNESS.md` and `scripts/verify_harness.py` exist). In an
uninstalled `CLI-Anything` source checkout (`{REPO_ROOT}`), either bootstrap with
`{REPO_ROOT}/antigravity-plugin/scripts/install.{sh,ps1}` or read
`{REPO_ROOT}/cli-anything-plugin/HARNESS.md` and `{REPO_ROOT}/cli-anything-plugin/commands/validate.md`
while running `{REPO_ROOT}/antigravity-plugin/scripts/verify_harness.py`.

Read with absolute paths via `read_file`:
- `{PLUGIN_ROOT}/references/HARNESS.md`
- `{PLUGIN_ROOT}/references/commands/validate.md`

## 2. Deterministic Check First (Do Not Eyeball)

Run the bundled contract verifier first via `run_command`:

```bash
python "{PLUGIN_ROOT}/scripts/verify_harness.py" "<software-path>" --json
# Add --strict to fail on warnings (repl_skin drift, bare except, truncated skill description, etc.)
# Pass --all from a CLI-Anything checkout root to audit every harness.
```

## 3. Full Audit Workflow

Track in `{software-root}/agent-harness/.cli-anything-progress.json` with `"mode": "validate"`:

1. Run `verify_harness.py` and inspect every `fail` and `warn` check (PEP 420 namespace, `setup.py`, `console_scripts`, `package_data`, Click/`--json`/REPL/`--dry-run`, canonical `repl_skin.py` byte match, `TEST.md`, `test_core.py`, `test_full_e2e.py` + `_resolve_cli`, packaged & repo-root `SKILL.md` frontmatter, AST syntax & quality).
2. For deeper independent auditing of large harnesses, optionally delegate read-only inspection to the bundled `cli-anything-auditor` subagent.
3. Walk any remaining behavioral checks from `{PLUGIN_ROOT}/references/commands/validate.md` (real backend invocation vs reimplementation, output verification logic, `pip show` / PATH entry point).
4. Present a clear section-by-section PASS/WARN/FAIL report with exact file paths and concrete remediation items. Do not modify harness files unless the user asks to fix findings.
