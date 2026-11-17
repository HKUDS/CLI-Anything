# Hermes tooling notes for CLI-Anything

Operational detail behind `SKILL.md`. Read when a build stalls on the host, on
approvals, on delegation, or on making the finished CLI visible to the agent.

## Where the skill and its output live

| Thing | Path |
|---|---|
| Installed skill | `$HERMES_HOME/skills/cli-anything-hermes` (default `~/.hermes/skills/...`) |
| Profile install | `$HERMES_HOME/profiles/<profile>/skills/cli-anything-hermes` |
| External skill dirs | whatever `skills.external_dirs` lists in `~/.hermes/config.yaml` |
| Generated harness | `<software>/agent-harness/` in the user's working tree |
| Generated CLI skill | `agent-harness/cli_anything/<module>/skills/SKILL.md` and the repo-root mirror |

Re-install with `--force` after pulling a new CLI-Anything release; the installer
vendors the methodology, so a stale copy is the usual cause of "the skill still quotes
an old phase list".

## Host prerequisites

- `python3` on PATH must be >= 3.10 for most harnesses and for `cli-hub`
  (`requires_python >= 3.10`). macOS system python is often 3.9; prefer a Homebrew
  interpreter and a venv:

  ```bash
  /opt/homebrew/bin/python3.13 -m venv .venv-harness
  . .venv-harness/bin/activate
  pip install -e <software>/agent-harness
  ```

- The target application must actually be installed. A CLI wrapper around an absent
  binary is five lines of nothing. Check `/Applications` and `~/Applications` on macOS
  before promising a working harness.
- Codex/Hermes/Claude-style skills and `cli-hub` are separate layers: installing a
  harness does not install its upstream application.

## Approvals and shell policy

- `terminal` may pause for approval on recursive deletes, downloads, and installer
  scripts. Prefer commands that are obviously scoped: `rm -rf` only inside a venv or a
  temp dir, never a bare wildcard.
- Never write credentials into a harness, a test, or `TEST.md`. Pass secrets through the
  environment and record the variable name only.
- Long installs and test suites should set an explicit timeout instead of relying on the
  default; a build that runs past it looks like a hang.

## Delegation recipe

Use `delegate_task` when a harness has more than roughly three independent command
groups. Each child needs its own context — it cannot see this conversation:

1. Parent: analyze the backend, design the command tree, write `setup.py`, the session
   layer, and the shared `utils/` modules. Commit those decisions to files first.
2. Child per command group: "Implement commands `foo list|get|create` in
   `cli_anything/<software>/core/foo.py` plus `tests/test_foo.py`. Do not edit any other
   file. Run `pytest tests/test_foo.py` and report the counts."
3. Child for E2E: given the finished surface, write `test_full_e2e.py` and `TEST.md`.
4. Parent: install into a fresh venv, run the full suite, run `verify_harness.py`, and
   report. Verification never delegates.

One file, one owner. Two children editing the same module produce a merge you cannot
review.

## Making the finished CLI reachable by the agent

A harness is not usable until its skill is in a skill directory the running session
knows about:

- For a repo contribution, place the canonical copy at
  `skills/cli-anything-<software>/SKILL.md` and the packaged copy at
  `cli_anything/<module>/skills/SKILL.md`. The root-skill mirror is a CI gate.
- For local use, copy the packaged `SKILL.md` to
  `$HERMES_HOME/skills/cli-anything-<software>/SKILL.md`.
- Hermes's index is built at session start. Tell the user to start a new session; the
  running one will not see the new skill.
- Keep the description short and trigger-shaped. Hermes clips long descriptions in the
  skill index, and the repo's generator truncates mid-sentence with `...` when the
  harness intro is long — rewrite the description rather than shipping the ellipsis.

## Verifier reference

```bash
python3 scripts/verify_harness.py <path>            # human output
python3 scripts/verify_harness.py <path> --json     # {"ok": bool, "harnesses": [...]}
python3 scripts/verify_harness.py --all --json      # full checkout audit
python3 scripts/verify_harness.py <path> --strict   # warnings fail the run
```

`<path>` may be `<software>/` or `<software>/agent-harness/`. Errors are contract
breaks (missing entry point, no `--json`, missing tests, missing root skill mirror).
Warnings are drift the method tolerates but flags (`repl_skin.py` differs from the
canonical copy, no `--dry-run`, no results section in `TEST.md`, truncated skill
description).

## Failure playbook

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: cli_anything` | installed as a normal package instead of a namespace layout | rebuild with `find_namespace_packages`, no top-level `__init__.py` |
| `pip` cannot find a distribution | interpreter below the package's `requires_python` | rebuild the venv on a newer interpreter |
| Tests pass, `--help` fails | imports resolve only inside the source tree | install with `pip install -e .` and run the console script |
| Verifier says root skill missing | new harness with no mirror | add `skills/cli-anything-<software>/SKILL.md` |
| Verifier says `repl_skin.py` differs | edited the copy instead of the canonical file | copy `cli-anything-plugin/repl_skin.py` verbatim |
| E2E tests skip silently | backend not installed | install the application or document the skip in `TEST.md` |
