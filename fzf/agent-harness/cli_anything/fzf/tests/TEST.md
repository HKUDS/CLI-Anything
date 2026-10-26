# fzf CLI-Anything Harness Test Plan

## Compatibility tuple

- Harness package: `cli-anything-fzf` 1.0.0
- Backend: real `fzf 0.74.5 (c0a193e0)`
- Python: 3.10+
- Platform under test: Linux, terminal/PTY support, Unix-domain sockets
- Network requirement: none; TCP tests bind loopback only

## Test inventory plan

- `test_core.py`: 106 unit and CLI-isolation test cases.
- `test_full_e2e.py`: 79 tests against the real backend,
  installed console script, PTYs, and owned listener fixtures.
- `test_option_coverage.py`: 12 schema and live help/man
  completeness tests.

The suite will record pass, fail, skip, and not-run separately. A backend, PTY,
or listener prerequisite is a hard requirement for the release run; it will not
be reported as passed when absent.

## Unit test plan

### `core.capabilities`

- Load and schema-check the machine-readable option/action/event inventory.
- Validate the packaged Draft 2020-12 schemas, then validate real success,
  error, plan, profile, byte-result, backend, and listener payloads.
- Require unique canonical names and aliases.
- Cover every category and every effect class.
- Extract option headings from representative help/man text.
- Detect missing live options and distinguish documented aliases.

Expected: 8 tests.

### `core.validation`

- Validate enums, integers, dimensions, margins/padding, field/range
  expressions, tiebreak ordering, walker options, socket/TCP addresses,
  duration, binding keys/events/actions, and composed action delimiters.
- Reject NULs, malformed ranges/delimiters/colors/layouts, unknown actions,
  duplicate non-repeatable options, positional expert arguments, and option
  injection through values.
- Identify every command-executing option/action, including transform and
  background-transform families.

Expected: 20 tests.

### `core.planner` and `core.input`

- Compose typed options and multiple profiles deterministically.
- Verify exact argv arrays, effect union, hazards, policy grants, refusal
  reasons, expected output mode, backend identity, and environment deltas.
- Default-deny preview/execute/reload/become/transform/with-shell, ambient
  defaults, history writes, implicit walker, listener flags, broad traversal,
  unsafe addresses, and unknown options.
- Redact `FZF_API_KEY` and other credential-shaped values.
- Bound stdin/file/item input by bytes and item count while preserving
  newlines, NUL records, Unicode, ANSI, and invalid UTF-8.
- Decode only canonical base64 when an agent needs to supply exact bytes
  without relying on transport stdin framing.

Expected: 20 tests.

### `core.profiles`, `core.results`, and `core.listener`

- Validate profile schemas and deterministic precedence/append rules.
- Enforce safe overwrite and file permissions.
- Decode newline/NUL output without losing exact bytes; separate query and
  expect prefixes; map all documented fzf exits.
- Validate listener containment, ownership tokens, PID start-time checks,
  HTTP response parsing, and secret-free state serialization.

Expected: 17 tests.

## End-to-end test plan

All backend tests invoke `/var/home/louranicas/.local/bin/fzf` or the exact
override supplied by `CLI_ANYTHING_FZF_BACKEND`; they do not mock matching.

### Backend and inventory workflow

1. Probe version/path/realpath/digest in human and JSON modes.
2. Retrieve live help and man output.
3. Compare every live option heading with `capabilities.json`.
4. Verify package import and run the installed console script from a temporary
   directory outside the checkout.

Verified: exact version, immutable identity, schema stability, no CWD reliance.

### Deterministic filtering workflow

1. Plan, dry-run, then execute default/exact/case/path/history-scheme searches.
2. Exercise nth/delimiter/with-nth/accept-nth, no-sort/tiebreak, ANSI, read0,
   print0, print-query, tail, sync, benchmark output, and multi-stage composed
   options.
3. Cover empty input, no match, one match, multiple matches, duplicate lines,
   spaces, embedded newlines in NUL mode, Unicode, ANSI, invalid UTF-8, and a
   large bounded input.

Verified: exact bytes, record ordering, prefixes, backend/process versus
semantic status, and absence of filesystem/network side effects.

### Interactive PTY workflow

1. Spawn the installed harness under a PTY with candidate items supplied by
   argv/file rather than terminal stdin.
2. Type a query, accept a result, and verify exact output.
3. Exercise multi-select and expect-key prefixes.
4. Exercise timeout and interrupt paths and verify no descendant remains.
5. Run a deliberately broken preview command only with explicit subprocess
   authorization and verify bounded failure/cancellation behavior.
6. Execute the real fzf walker from an explicit temporary root and verify an
   authorized history write in a temporary file.

Verified: real TTY operation, selection semantics, cancellation, cleanup.

### Profile/config/shell workflow

1. Create and compose temporary profiles, then filter with the composition.
2. Inspect isolated ambient defaults and an explicit temporary opts file.
3. Retrieve Bash/Zsh/Fish/Nushell scripts from the real backend in raw and
   JSON modes.

Verified: no host config mutation, deterministic composition, secret redaction,
non-empty backend-authored integration output.

### Listener workflow

1. Start an owned Unix-socket listener in a temporary state directory.
2. Re-probe status and GET state, POST safe actions, stop, then verify the
   worker/backend PIDs and socket are gone.
3. Accept a selection through the listener, retrieve the exact query prefix
   and NUL-framed result artifact, then verify stale cleanup removes it.
4. Exercise collision, startup failure, stale state, authentication failure and
   success, loopback TCP authorization, unsafe-listener refusal, and command
   action refusal.
5. Start an authenticated unsafe Unix listener with every required grant,
   execute one bounded command action, and verify its temporary artifact.
6. Force startup timeout with a TERM-resistant fake backend and prove both
   worker and backend identities are gone and every disposable artifact was
   cleaned.

Verified: address containment, explicit ownership, authentication, bounded
lifecycle, and no orphan process/socket.

## Security and adversarial matrix

| Case | Expected result |
|---|---|
| shell metacharacters in item/query/labels | remain one argv/input value; never interpreted by Python |
| command-bearing binding without policy | deterministic refusal |
| `--with-shell` or preview without policy | deterministic refusal |
| inherited `FZF_DEFAULT_COMMAND`/opts file | absent from constructed environment |
| raw `FZF_API_KEY` request/output | refused/redacted |
| broad walker without root and grant (`/`, home, or any resolved ancestor of home such as `/var/home`, `/home`, `/var`) | refused |
| history without filesystem-write grant | refused |
| non-loopback or unsafe listener without grants/key | refused |
| injected listener mode/address from defaults or generic options | refused; managed start retains ownership |
| socket collision/symlink target | refused without unlinking foreign path |
| missing backend/wrong version | deterministic typed error |
| malformed profile/option/binding/color/layout | exit 2 JSON error envelope |
| timeout/interrupt | child group terminated and owned files cleaned |

## Documentation and packaging checks

- README, FZF SOP, TEST results, packaged skill, and canonical root skill agree.
- Skill pipeline generation and root-skill mirror validation pass.
- `setup.py` uses PEP 420 namespace discovery and packages JSON/Markdown data.
- `CLI_ANYTHING_FORCE_INSTALLED=1` confirms subprocess tests use the installed
  entry point from outside the checkout.
- No registry entry or floating remote install command is added before an
  immutable release/full commit reference exists. Local installation from the
  checked-out `fzf/agent-harness` path is documented and tested.

## Test results

### Current release run (2026-10-27, source head `f47dd7a`)

Run by the outer release executor from a `git archive` snapshot of source head
`f47dd7ab32a9c47acf80383b029679530403119e`, after the broad-walker
ancestor-of-home fix. Python 3.12.15, real backend
`/var/home/louranicas/.local/bin/fzf` `0.74.5 (c0a193e0)` (SHA-256
`c8d3ac08594f271a108528beb15338c42be113d392816b10bf5955cd139293e8`). The
tests ran against the installed wheel `cli_anything_fzf-1.0.0-py3-none-any.whl`
(SHA-256
`6f650d17ace4adb0f0aa0b57dacb055953ed12844fcd211f700b2d8eab9e3a7c`), built
with offline `uv build` and installed with `uv pip install --offline` into a
fresh virtual environment. Evidence report:
`/var/mnt/storage/firstmate-lab/repos/firstmate/data/fzf-cli-harness-tmux/release-evidence-walker.C744b1/RELEASE-EVIDENCE.txt`.

| Suite | Pass | Fail | Skip | Not run |
|---|---:|---:|---:|---:|
| `test_core.py` | 106 | 0 | 0 | 0 |
| `test_option_coverage.py` | 12 | 0 | 0 | 0 |
| `test_full_e2e.py` | 79 | 0 | 0 | 0 |
| **Total** | **197** | **0** | **0** | **0** |

```bash
CLI_ANYTHING_FZF_BACKEND=/var/home/louranicas/.local/bin/fzf \
CLI_ANYTHING_FORCE_INSTALLED=1 \
<release-venv>/bin/python \
  -m pytest fzf/agent-harness/cli_anything/fzf/tests -q --tb=short
# 197 passed in 16.76s  (exit 0)
```

All 16 collected listener cases in `test_full_e2e.py` ran and passed within
that suite, so the ad hoc listener failure noted below was not reproduced.

### Previous release run (2026-10-27, source head `45aa3ba`, before the broad-walker fix)

Run by the outer release executor from a `git archive` snapshot of source head
`45aa3bac77cfde4018e66caec35ef41a0099daef`, after the expert-option surface
fix (commit `83fed65`). Python 3.12.15, real backend
`/var/home/louranicas/.local/bin/fzf` `0.74.5 (c0a193e0)` (SHA-256
`c8d3ac08594f271a108528beb15338c42be113d392816b10bf5955cd139293e8`). The
tests ran against the installed wheel `cli_anything_fzf-1.0.0-py3-none-any.whl`
(SHA-256
`bb72abcdd44c6682416220f1d4953307eb01d2688d48be047ed7303bcd8c4148`), built
with offline `uv build` and installed with `uv pip install --offline` into a
fresh virtual environment.

| Suite | Pass | Fail | Skip | Not run |
|---|---:|---:|---:|---:|
| `test_core.py` | 97 | 0 | 0 | 0 |
| `test_option_coverage.py` | 12 | 0 | 0 | 0 |
| `test_full_e2e.py` | 79 | 0 | 0 | 0 |
| **Total** | **188** | **0** | **0** | **0** |

```bash
CLI_ANYTHING_FZF_BACKEND=/var/home/louranicas/.local/bin/fzf \
CLI_ANYTHING_FORCE_INSTALLED=1 \
<release-venv>/bin/python \
  -m pytest fzf/agent-harness/cli_anything/fzf/tests -q --tb=short
# 188 passed in 16.99s  (exit 0)
```

All 16 collected listener cases in `test_full_e2e.py` ran and passed within
that suite. This run predates the broad-walker ancestor-of-home fix and its 9
added `test_core.py` cases.

### Pipeline test-phase scenarios observed on 2026-10-27

The no-mistakes test phase for this change exercised targeted scenarios against
the real backend. These are partial evidence, not a full-suite pass:

- Expert-option regressions: 11 selected tests (from 176 collected in
  `test_core.py` and `test_full_e2e.py`) passed, including
  `test_granted_expert_option_reaches_real_backend` and
  `test_expert_option_is_accepted_on_execution_surfaces_only_with_grant` for
  the declarative and listener surfaces.
- Manual CLI transcripts: `backend inspect`/`verify-spec` (180 addressable
  options, complete), filter matching, field options, no-match exit 1, NUL-safe
  bytes, and dry-run plans behaved as documented. Without
  `--allow-unknown-options`, an expert option is refused. With the grant it
  executes, and fzf itself rejects the unknown flag. Known options, `--listen`,
  and non-`--long` forms stay refused. Command actions without grants still
  get `plan_refused`.
- Profile creation needs `--allow-filesystem-write` and writes mode 0600. The
  REPL refuses non-TTY stdin with `tty_required`.
- An ad hoc `listener start` in that environment failed with
  `listener_start_failed` (worker exit 1). `listener stop` then reported
  verified cleanup. This was not counted as a listener pass; the release
  runs above cover the listener cases.

### Historical release run (before the expert-option fix)

Observed on 2026-10-26, before commit `83fed65`, in the isolated task worktree
with Python 3.12.15 and the real `/var/home/louranicas/.local/bin/fzf` backend.
These counts are the 185-test inventory of that time, not the current code:

| Suite | Pass | Fail | Skip | Not run |
|---|---:|---:|---:|---:|
| `test_core.py` | 95 | 0 | 0 | 0 |
| `test_option_coverage.py` | 12 | 0 | 0 | 0 |
| `test_full_e2e.py` | 78 | 0 | 0 | 0 |
| **Total** | **185** | **0** | **0** | **0** |

Historical release command and result:

```bash
CLI_ANYTHING_FZF_BACKEND=/var/home/louranicas/.local/bin/fzf \
CLI_ANYTHING_FORCE_INSTALLED=1 \
/var/mnt/storage/firstmate-lab/repos/firstmate/data/fzf-cli-harness-tmux/venv312/bin/python \
  -m pytest fzf/agent-harness/cli_anything/fzf/tests -q --tb=short
# 185 passed in 16.48s
```

Verified backend evidence:

- Version/revision: `0.74.5 (c0a193e0)`.
- Executable SHA-256:
  `c8d3ac08594f271a108528beb15338c42be113d392816b10bf5955cd139293e8`.
- Live headings: 113 help, 125 man, 127 distinct; 0 missing from the
  131-record explicit ledger. The 59 live-probed implicit-negation bases add
  49 non-duplicate records for 180 addressable options.
- Help SHA-256:
  `944def5bbeff3f7450b69aec8519cf762091704ad52d49ee735fe4cd168867d0`.
- Normalized man SHA-256:
  `d246636f6baf06684abbc468a0cf60fcd9679144bae148ecabdc4a7b54e2a46b`.

The release run executed real PTY single/multi selection, walker traversal,
history writing, expect-prefix, timeout, interrupt, command-descendant cleanup,
and broken-preview cases. It also executed Unix listener GET/POST/status/stop,
mode-0600 API-key authentication, an authorized unsafe command action, loopback
TCP, forced startup failure, collision preservation, action refusal, stale
cleanup, and post-stop PID/socket checks. None of those cases was inferred or
reported as a pass from a missing prerequisite.

Packaging was independently exercised with an offline `uv build` (sdist and
wheel), then the wheel was installed into a fresh virtual environment. From
`/tmp`, the installed console script verified the live backend/spec, exported
all 180 options, preserved exact filter bytes, and Python loaded the packaged
capability/schema JSON, skill, and `tests/TEST.md` resources. The
repository-level plugin, GitHub script, skill-generation, and Codex-skill
regression suites also passed: 129 passed, 0 failed, 0 skipped.

Skill pipeline evidence:

```text
cli-anything-plugin/skill_generator.py: generated canonical + packaged copies
.github/scripts/validate_root_skills.py: Root skills validation passed.
skill-creator quick_validate.py (canonical): Skill is valid!
skill-creator quick_validate.py (packaged): Skill is valid!
```
