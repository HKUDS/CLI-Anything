---
name: cli-anything-hermes
description: Build, refine, and verify agent-native CLI harnesses.
---

# CLI-Anything for Hermes

Use this skill when the user wants Hermes to build, refine, test, validate, or list a
CLI-Anything harness for a GUI application, a codebase, or a service with an API.

The output is unchanged from every other CLI-Anything surface: a Python package at
`<software>/agent-harness/` with a stateful Click CLI, a default REPL, `--json` output,
a generated `SKILL.md`, and tests. This skill only changes how Hermes drives the work and
how the result is verified.

## Read the Full Methodology First

1. Read `references/HARNESS.md` — the complete seven-phase method and quality rules.
2. Read the mode specification under `references/commands/` before that mode.
3. Read a file under `references/guides/` only when it applies to the target
   (session locking, auto-save and dry-run, preview, MCP backends, timecode precision).
4. If the installed references are missing and this skill is being used from a
   CLI-Anything checkout, read `../cli-anything-plugin/HARNESS.md` and the resources
   around it.
5. If neither is reachable, clone `https://github.com/HKUDS/CLI-Anything` and use
   `cli-anything-plugin/HARNESS.md`.
6. Only if every source above fails, follow [Condensed Fallback Rules](#condensed-fallback-rules).

The installer vendors these resources into the skill, so a normal install is
self-contained. Apply this path remapping instead of resolving plugin paths against the
current directory:

| Document says | Installed path |
|---|---|
| `guides/...` | `references/guides/...` |
| `cli-anything-plugin/repl_skin.py` | `scripts/repl_skin.py` |
| `cli-anything-plugin/preview_bundle.py` | `scripts/preview_bundle.py` |
| `cli-anything-plugin/skill_generator.py` | `scripts/skill_generator.py` |
| `templates/SKILL.md.template` | `scripts/templates/SKILL.md.template` |
| `docs/PREVIEW_PROTOCOL.md` | `references/docs/PREVIEW_PROTOCOL.md` |

`references/hermes-tooling.md` covers Hermes-specific execution: approvals, timeouts,
profiles, delegation, and how the generated CLI skill reaches the user's skill index.

## When to Use

- "Build a CLI for `./gimp`" / "make `<product>` agent-operable".
- Refining an existing harness for missing capabilities, or validating one against the
  contract before a PR.
- Auditing a harness tree (`--all`) to find which harnesses break the published rules.

Don't use for: writing a thin wrapper around a tool that already ships a good JSON CLI
(say so instead), or for operating a published harness — that is
`cli-anything-<software>` plus its own `SKILL.md`.

## Hermes Tool Bindings

| Tool | Role | Rule |
|---|---|---|
| `terminal` | Clone, install, run tests, run the built CLI | Long builds need an explicit `timeout`; `pip install -e .` into a venv, never system python |
| `read_file` / `write_file` | Read source, write harness modules | Write the smallest file that satisfies the phase; no placeholder modules |
| `patch` | Iterative fixes after a failing test | One logical fix per call, then re-run the failing test |
| `execute_code` | Multi-file generation and AST/schema extraction | Prefer it over a long chain of single writes |
| `delegate_task` | Parallel per-command-group implementation or review | One subagent per file set; never two editing the same file |
| `search_files` | Find existing CLI entry points and backend hooks | Use before inventing a new module |
| `clarify` | Only when the target itself is ambiguous | Never for a detail you can read from the source |

## Modes

Each mode ends at a checkable completion criterion, not at "implemented".

### Build

Read `references/commands/cli-anything.md`. Run all seven phases: analyze the backend,
design command groups and state, implement, plan tests, write tests, document results,
publish.

Complete when: `pip install -e .` works in a fresh venv, `cli-anything-<software> --help`
shows the command groups, the test suite passes, and `verify_harness.py` reports zero
errors for the target.

### Refine

Read `references/commands/refine.md`. Inventory current commands and tests, diff against
the target's capabilities, then add the highest-impact missing commands. Never remove an
existing command without an explicit request.

Complete when: the new commands have tests, the old suite still passes, and the gap list
in the report is either implemented or explicitly deferred.

### Test

Read `references/commands/test.md`. Keep `test_core.py` runnable without the backend and
`test_full_e2e.py` for real workflows. Update `TEST.md` only with results that actually
ran.

Complete when: both suites pass from a clean shell and `TEST.md` records the counts.

### Validate

Read `references/commands/validate.md`, then run the mechanical contract check:

```bash
python3 scripts/verify_harness.py <software-dir> --json
```

Complete when: the verifier exits 0 with no errors, and every warning is either fixed or
explained in one line.

### List

Read `references/commands/list.md`. Report installed harnesses with their entry points;
support `--json` when the caller is an agent.

## Verify Before Claiming Done

`scripts/verify_harness.py` is the executable form of the harness contract. It checks the
namespace layout, `setup.py` entry point, `--json`, the REPL default, the vendored
`repl_skin.py`, the SOP doc, both test suites, `TEST.md`, and the root and packaged
`SKILL.md` mirrors.

```bash
python3 scripts/verify_harness.py mysoftware --json      # one harness, machine-readable
python3 scripts/verify_harness.py --all                  # whole checkout audit
python3 scripts/verify_harness.py mysoftware --strict    # warnings fail too
```

Exit code 1 means at least one error. Never report a harness as complete without its
verifier output; paste the summary line into the final report.

## Parallel Work With delegate_task

A harness build parallelizes by capability, not by file:

- One subagent per command group (project, import/export, session, domain verbs), each
  told to touch only its own modules and tests.
- A separate subagent for E2E tests, given the finished command surface.
- The parent runs `verify_harness.py`, the full test suite, and the install check —
  never a subagent, so the result is verified by the process that reports it.

## Condensed Fallback Rules

Use only when no methodology source is reachable.

- Prefer wrapping the real backend over reimplementing it.
- One-shot subcommands plus a REPL as the default when no subcommand is given.
- `--json` on the root group; `--dry-run` on every mutation; `--project` for state.
- Session state with undo/redo where the target supports it, saved with a lock.
- Copy the canonical `repl_skin.py` verbatim.
- `TEST.md` before test code; `test_core.py` plus `test_full_e2e.py`; verify artifacts,
  not exit codes.
- `find_namespace_packages(include=["cli_anything.*"])`, no top-level
  `cli_anything/__init__.py`, `console_scripts` entry point.

## Pitfalls

- **Hermes's skill index is built at session start.** A newly generated CLI skill is not
  visible to the running session; tell the user to start a new session.
- **Do not hand-edit the installed skill directory.** Re-run the installer with `--force`;
  edits there are lost.
- **System python is often older than the harness requires.** Create a venv on a
  >= 3.10 interpreter before `pip install -e .`.
- **The verifier resolves the repo root by walking upward.** Run it from inside the
  checkout when auditing mirrors; running it on a copy reports root-skill and canonical
  `repl_skin.py` as warnings.
- **A generated harness can pass its own tests and still violate the contract.**
  `verify_harness.py` exists because tests check behavior, not packaging.

## Output Expectations

Report: target and source path; files added or changed; the verifier summary; the test
counts that ran; anything deferred or blocked on a backend the machine does not have.
