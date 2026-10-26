# cli-anything-fzf

`cli-anything-fzf` is a structured, security-conscious harness around the real
fzf executable. It keeps fzf's complete 0.74.5 option, binding, preview,
directory-walker, history, shell-integration, and listener surface available
without reducing it to an opaque shell command.

The matcher and terminal UI always come from fzf itself. The Python layer
provides validated declarative options, exact argv plans, bounded input and
timeouts, deterministic JSON, byte/NUL-aware results, default-deny hazardous
features, explicit listener ownership, and a machine-readable coverage ledger.

## Compatibility

| Component | Supported baseline |
|---|---|
| Harness | `cli-anything-fzf` 1.0.0 |
| Backend | `fzf 0.74.5 (c0a193e0)` |
| Python | 3.10+ |
| Core operations | Linux/POSIX (the released compatibility tuple) |
| Managed listener/PTY evidence | Linux; Unix sockets require `AF_UNIX` |

The release evidence used the locally installed backend at
`/var/home/louranicas/.local/bin/fzf`, SHA-256
`c8d3ac08594f271a108528beb15338c42be113d392816b10bf5955cd139293e8`.
Runtime discovery does not hard-code that path: pass `--backend PATH`, set
`CLI_ANYTHING_FZF_BACKEND`, or put `fzf` on `PATH`.

Version compatibility is strict by default. `--allow-version-mismatch` permits
another version but the JSON result says that it is outside the verified tuple.

## Install

Install fzf 0.74.5 using your platform's trusted package/toolchain process, then
install the harness from a trusted local checkout pinned to the revision you
intend to run:

```bash
python -m pip install /absolute/path/to/CLI-Anything/fzf/agent-harness
```

This source branch deliberately does not advertise a floating remote install
URL. A registry install command should be added only when an immutable release
or full commit reference exists.

For development in an isolated virtual environment:

```bash
python -m venv /tmp/cli-anything-fzf-venv
/tmp/cli-anything-fzf-venv/bin/python -m pip install -e './fzf/agent-harness[test]'
/tmp/cli-anything-fzf-venv/bin/cli-anything-fzf --help
```

## Fast start

Inspect the exact backend and the capability contract:

```bash
cli-anything-fzf --json backend inspect
cli-anything-fzf --json capability list --effect subprocess_capable
cli-anything-fzf --json backend verify-spec
```

Plan without reading stdin or starting fzf:

```bash
cli-anything-fzf --json --dry-run plan build --mode filter --query api \
  --item 'API server' --item 'worker' --option exact
```

Run deterministic matching:

```bash
printf '%s\n' alpha alphabet beta | \
  cli-anything-fzf --json filter run --stdin --query alp
```

In human mode, `filter run` writes the backend's exact bytes to stdout, so it
stays pipeline-friendly:

```bash
printf '%s\n' alpha alphabet beta | \
  cli-anything-fzf filter run --stdin --query alp > matches.txt
```

## Global controls

Global options precede the command group:

```text
--json                         stable JSON envelopes
--backend PATH                 explicit executable
--allow-version-mismatch       opt out of the pinned-version refusal
--timeout SECONDS              bounded backend execution (default 30)
--dry-run                      show a plan; never start fzf
--env-policy isolated|inherit  isolated is the default
--set-env NAME=VALUE           repeatable allowlisted environment delta
```

Security grants are also global and must appear before the group:

```text
--allow-command-actions
--allow-filesystem-write
--allow-walker
--allow-broad-walker
--allow-network-listener
--allow-unsafe-listener
--allow-env-inherit
--allow-default-opts-file
--allow-unknown-options
```

Grant names appear in every plan. Passing a grant does not activate a feature;
it only permits a validated request that actually needs it.

## Command reference

### `backend`

- `backend inspect` — path, resolved path, digest, size, version, revision, and
  compatibility. With `--dry-run`, hashes the executable without invoking it.
- `backend help` / `backend man` — exact backend-authored documentation. Human
  mode emits raw text; JSON includes text, byte count, and digest.
- `backend verify-spec` — extracts option headings from both live documents and
  fails if `capabilities.json` misses one.

### `capability`

- `capability list [--category C] [--effect E] [--coverage S]`
- `capability show NAME`
- `capability actions`
- `capability events`
- `capability export`
- `capability schemas`

The export is `cli-anything-fzf-capabilities/v1`. It inventories 131 explicit
help/man records plus the exact 59 base options whose implicit `--no-*` forms
were live-probed. `capability list` materializes the 49 non-duplicate forms for
180 addressable records. It also inventories documented aliases, events, named
actions, the background transform family, input/exported environment variables,
effect classes, policies, surfaces, and exit statuses.

`capability schemas` returns the packaged Draft 2020-12 schema bundle for
success/error envelopes, backend identities, execution plans, profiles, exact
byte records/results, and listener state. Release tests validate the schema
document itself and representative real CLI payloads against every definition.

Coverage states mean:

- `implemented` — usable in noninteractive and/or its named specialized group;
- `interactive-only` — valid for `session`/`listener`, while a filter plan may
  accept it even though fzf will not render a terminal UI in filter mode;
- `refused-with-rationale` — reserved for an unverified expert option, surfaced
  only with the explicit forward-compatibility grant.

### Declarative options

`plan`, `filter`, `session`, and `listener start` share these repeatable inputs:

```text
--option NAME[=VALUE]          known option from capabilities.json
--bind KEY[,KEY...]:ACTION    one validated binding expression
--profile PATH                explicit profile, later profiles take precedence
--expert-option --LONG[=VALUE]
--item TEXT                   UTF-8 candidate item
--input-file PATH             exact candidate byte stream
--input-base64 BASE64         exact bytes in canonical base64
--stdin                       bounded stdin byte stream
--max-input-bytes N
--max-items N
```

Option values use a single token (`--option delimiter=:`), so there is no
ambiguous separate value that could become another backend flag. Repeat `--bind`
instead of putting multiple top-level binding expressions in one string.

The expert escape hatch accepts only one unknown `--long-name` or
`--long-name=value` token, rejects known/listener/positional/short forms, never
invokes a shell, appears visibly in dry-run, and requires
`--allow-unknown-options`.

### `plan build`

Builds the same plan that execution uses. A plan includes:

- exact, sanitized argv array;
- binary identity without starting fzf;
- stdin source, delimiter, limits, size/count/digest when already available;
- constructed environment and ambient values removed;
- effect classes, hazards, explicit policy grants, and every refusal reason;
- expected output mode and timeout;
- option/profile provenance and deterministic `plan_id`.

Dry-run does not consume stdin or read an input file's contents. It may stat an
explicit input path and hash the backend binary, but it does not start fzf,
create a listener, or write history/profile/state.

### `filter run`

Adds `--filter=QUERY --sync` and invokes one bounded real-backend operation.
It handles exact/fuzzy/smart-case searches, schemes, algorithms, field
expressions/templates, delimiters, ANSI, NUL records, sorting/tiebreaks, tail,
query prefixes, and every other compatible declarative option.

Example with transformed fields:

```bash
printf '%s\n' '1:alpha:ready' '2:beta:waiting' | \
  cli-anything-fzf --json filter run --stdin --query ready \
  --option 'delimiter=:' --option 'nth=2..3' --option 'accept-nth=1,2'
```

NUL-safe example (human mode preserves NUL output exactly):

```bash
printf 'one\ntwo\0three\0' | \
  cli-anything-fzf filter run --stdin --query two \
  --option read0 --option print0 > result.bin
```

JSON represents every record as UTF-8 text when valid and always as base64,
plus the complete exact output as `output_base64` with length and SHA-256.
`--print-query` and `--expect` prefixes are separated from selections.
The harness preserves the backend's output bytes exactly. fzf itself replaces
malformed UTF-8 input bytes with U+FFFD; JSON reports that normalized backend
output rather than claiming a byte-for-byte input round trip.

`--option bench=DURATION` switches the declared output mode to
`benchmark-report`; JSON returns the exact report as text/base64 instead of
mislabeling the report line as a selected candidate.

### `session select`

Runs fzf interactively with a bounded timeout and process-group cancellation.
Candidates come from `--item`, `--input-file`, `--input-base64`, or `--stdin`;
keyboard input stays on the terminal. `--input-base64` is useful to agents that
must preserve NULs or newlines without relying on their transport's stdin
framing. With `--allow-walker` and no candidate source, fzf receives terminal
stdin and runs only from an explicit `--option walker-root=DIR`. For supplied
candidates, the harness adds `--no-tty-default` so fzf uses its inherited
terminal stream even though candidate stdin is a pipe.

```bash
cli-anything-fzf --timeout 120 session select \
  --item alpha --item beta --item gamma --query be
```

Multi-selection, expect prefixes, layout/style, headers/footers, preview, and
bindings use the declarative layer. Preview and command actions require the
explicit command grant:

```bash
cli-anything-fzf --allow-command-actions session select \
  --input-file files.txt --option 'preview=sed -n 1,20p -- {}' \
  --option 'preview-window=right,60%,wrap'
```

The command is passed as the value of one fzf argv element. fzf intentionally
interprets it through its own shell; Python does not.

### `profile`

Profiles are explicit JSON files and never auto-loaded:

```bash
cli-anything-fzf --allow-filesystem-write profile create /tmp/path.json \
  --name paths --description 'Path matching defaults' \
  --option scheme=path --option layout=reverse --bind 'ctrl-j:accept'

cli-anything-fzf --json profile inspect /tmp/path.json
cli-anything-fzf --json profile compose base.json project.json
```

Schema:

```json
{
  "schema_version": "cli-anything-fzf-profile/v1",
  "name": "paths",
  "description": "Path matching defaults",
  "options": ["scheme=path", "layout=reverse"],
  "bindings": ["ctrl-j:accept"]
}
```

Later profiles override non-repeatable options; repeatable bindings/colors append.
Writes are locked, atomic, mode 0600, and refuse overwrite unless requested.

### `config inspect`

Reports whether fzf-related ambient variables exist but does not apply them.
`FZF_API_KEY` is always redacted and fingerprinted. An explicit options file can
be parsed only with `--allow-default-opts-file --include-contents`.

Execution defaults to a constructed environment with ambient `FZF_*` removed.
To opt into defaults explicitly, use validated `--set-env`:

```bash
cli-anything-fzf --set-env 'FZF_DEFAULT_OPTS=--layout=reverse --info=inline' \
  --json filter run --stdin --query foo
```

`FZF_DEFAULT_COMMAND` and `SHELL` require `--allow-command-actions`.
`FZF_DEFAULT_OPTS_FILE` requires `--allow-default-opts-file` and its contents are
parsed through the same option policy. `FZF_DEFAULT_OPTS` and
`FZF_DEFAULT_OPTS_FILE` are mutually exclusive so the effective option stream
is inspectable; explicit CLI/profile options may deliberately override a
non-repeatable environment default and are recorded as the later source in the
plan. Raw API-key values are refused.

### `shell integration`

Retrieves, but never evaluates or installs, scripts from the real backend:

```bash
cli-anything-fzf shell integration bash > /tmp/fzf.bash
cli-anything-fzf --json shell integration nushell
```

### `listener`

The lifecycle is explicit and ownership-bound:

```bash
state=$(mktemp -d)
cli-anything-fzf --json listener start --state-dir "$state" \
  --item alpha --item beta --item gamma
cli-anything-fzf --json listener status --state-dir "$state"
cli-anything-fzf --json listener action --state-dir "$state" \
  --action 'change-query(be)+wait+best'
cli-anything-fzf --json listener result --state-dir "$state"
cli-anything-fzf --json listener stop --state-dir "$state" --remove-state
```

The default address is a Unix socket contained in `state-dir`. Existing socket,
file, or symlink collisions are refused; fzf is never allowed to remove a foreign
path. State records harness/backend PIDs and Linux start-time ticks, so a recycled
PID is never signalled. Startup waits for a real GET response and rolls back on
failure. Stop performs TERM, bounded wait, verified KILL fallback, socket cleanup,
and optional state removal.

TCP requires `--allow-network-listener` and an explicit non-zero port. A
non-loopback address requires a mode-0600 `--api-key-file`. Unsafe listening
additionally requires `--allow-unsafe-listener --allow-command-actions` and an
API key file. The key is passed only through the worker environment; state stores
only a SHA-256 fingerprint. Status/action require the matching key file.

Command-capable POST actions are denied unless command actions are authorized
and the owned listener was started in authenticated unsafe mode.
`listener result` reads a bounded snapshot of the owned output artifact and
decodes query/expect prefixes plus newline/NUL selections using the exact
framing recorded at start. A dry-run stats the artifact without reading it.
`listener clean-stale` removes state only after both recorded identities are
proven dead.

## Security model and limitations

- Python never uses `shell=True`, constructs a command string, or evaluates
  backend-emitted shell integration.
- Preview, info commands, `--with-shell`, execute/reload/become/change-preview,
  transform/background-transform, and dynamic trigger actions are command-capable.
- Unknown action/option grammar is rejected. The expert option escape hatch is
  deliberately visible and conservative but cannot predict future fzf semantics;
  it is therefore classified subprocess-capable.
- Explicit input files may read any path the invoking OS user can read. Broad
  implicit traversal is denied; walker roots that are `/` or contain the home
  directory need a second grant.
- Canonical base64 input is decoded directly to bounded candidate bytes; it is
  not interpreted as text or a command.
- History is both reading and writing and is limited to interactive modes.
- Full environment inheritance can expose credentials to fzf child commands and
  therefore requires a dedicated grant; plans list inherited variable names.
- fzf shell command grammar remains fzf's contract. Authorization means the
  caller accepts that selected text/placeholders can reach that shell command.
- Managed TCP port `0` is refused because it prevents deterministic cross-process
  ownership/status without adding a command side channel. Choose an explicit
  loopback port instead.
- Listener PTY lifecycle is release-tested on Linux. Other platforms retain
  no verified compatibility claim; process-group cancellation and the managed
  worker rely on POSIX facilities.

## JSON and exit semantics

Retrieve the formal contract with `cli-anything-fzf --json capability schemas`.

Success envelope:

```json
{"ok": true, "command": "filter.run", "data": {"plan": {}, "result": {}}}
```

Error envelope:

```json
{"ok": false, "error": {"code": "plan_refused", "message": "...", "details": {}}}
```

The wrapper preserves backend status for filter/session operations:

| Exit | Meaning | `backend_completed` | `semantic_success` |
|---:|---|---|---|
| 0 | accepted/completed | true | true |
| 1 | no match | true | false |
| 2 | backend error | false | false |
| 126 | `become` permission denied | false | false |
| 127 | `become` command not found | false | false |
| 130 | interrupted | false | false |

Harness validation errors use exit 2, missing executables 127, permission errors
126, and timeouts 124. JSON may therefore be valid and informative even when the
process exit is non-zero.

## Testing

From an isolated environment with the real backend:

```bash
python -m pip install -e './fzf/agent-harness[test]'
CLI_ANYTHING_FZF_BACKEND=/var/home/louranicas/.local/bin/fzf \
CLI_ANYTHING_FORCE_INSTALLED=1 \
python -m pytest fzf/agent-harness/cli_anything/fzf/tests -v -s --tb=no
```

See `tests/TEST.md` for the planned adversarial matrix and the exact observed
release result. Tests use temporary input/history/profile/socket paths, isolated
environments, loopback-only TCP, PTYs, and the real backend.

## Uninstall and rollback

Stop owned listeners before uninstalling:

```bash
cli-anything-fzf listener stop --state-dir /path/to/state --remove-state
python -m pip uninstall cli-anything-fzf
```

Uninstall does not remove fzf, user profiles, history, key files, or arbitrary
state directories. Filtering and inspection have no rollback step. Remove an
explicit profile only through your normal file-management process. `listener
stop` removes owned disposable input, configuration, selection, and socket
files; without `--remove-state`, it retains only the non-secret ownership state
record for audit or later `clean-stale` removal.
