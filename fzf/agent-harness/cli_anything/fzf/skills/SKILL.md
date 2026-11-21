---
name: "cli-anything-fzf"
description: "Plan and run structured fzf 0.74.5 filtering, terminal selection, profiles, shell-integration retrieval, and owned HTTP/Unix-socket listeners. Use when an agent needs fzf matching or automation with exact JSON/byte evidence and explicit safety policy."
---

# cli-anything-fzf

Use the real fzf matcher and terminal UI through validated argv-only operations.
The harness pins its verified behavior to `fzf 0.74.5 (c0a193e0)`, inventories
the complete shipped option/action/event surface, and defaults to an isolated
environment.

## Prerequisites

- Python 3.10 or later.
- fzf 0.74.5 on `PATH`, in `CLI_ANYTHING_FZF_BACKEND`, or supplied with
  `--backend PATH`.
- Install from a local CLI-Anything checkout with
  `python -m pip install /path/to/CLI-Anything/fzf/agent-harness`.

Put global controls before the command group. Use `--json` for agent calls:

```bash
cli-anything-fzf --json --backend /path/to/fzf backend inspect
```

## Choose the operation

- Inspect compatibility or the live source contract: `backend inspect`,
  `backend help`, `backend man`, or `backend verify-spec`.
- Discover exact option, event, action, and safety metadata: `capability list`,
  `capability show`, `capability actions`, `capability events`, or
  `capability export`; retrieve formal output contracts with
  `capability schemas`.
- Construct evidence without starting fzf: `plan build` or root `--dry-run`.
- Perform deterministic synchronous matching: `filter run`.
- Drive one bounded terminal interaction: `session select`.
- Create or compose explicit JSON option profiles: `profile`.
- Inspect ambient fzf configuration without applying it: `config inspect`.
- Retrieve, but never evaluate or install, integration text: `shell integration`.
- Own an explicit listener lifecycle: `listener start/status/action/result/stop`.

Read the packaged `cli_anything/fzf/README.md` for the full command reference
and `cli_anything/fzf/capabilities.json` for the machine-readable contract when
composing unfamiliar fzf grammar.

## Plan before execution

For non-trivial or hazardous work, inspect the exact plan first:

```bash
cli-anything-fzf --json --dry-run plan build --mode filter --query ready \
  --item '1:alpha:ready' --item '2:beta:waiting' \
  --option 'delimiter=:' --option 'nth=2..3' --option 'accept-nth={1}:{2}'
```

A plan reports the exact argv array, backend identity, input framing and digest,
environment delta, effect classes, grants, hazards, refusals, output mode, and
stable plan ID. A dry-run does not consume stdin, start fzf, create a listener,
or write a profile/history file.

Use repeatable structured fields rather than a shell command string:

```text
--option NAME[=VALUE]
--bind KEY[,KEY...]:ACTION
--profile /absolute/profile.json
--item TEXT
--input-file /absolute/input
--input-base64 BASE64
--stdin
```

An unknown future long option requires both `--allow-unknown-options` and
`--expert-option=--long-name=value`. It remains one argv token, is classified
as subprocess-capable, and cannot express known options, short bundles,
positional arguments, or listener flags.

## Deterministic filtering

```bash
printf '%s\n' alpha alphabet beta | \
  cli-anything-fzf --json filter run --stdin --query alp
```

Human mode writes fzf's exact result bytes to stdout. JSON separates optional
query/expect prefixes from selection records and includes UTF-8 text when valid,
base64 for every record, the complete output bytes as base64, length, and digest.
Use `--option read0 --option print0` for NUL-delimited multi-line records.

Exit 0 means fzf completed with a match/accept; exit 1 is a completed no-match,
not a transport failure. Inspect `process_exit_code`, `backend_completed`,
`semantic_success`, `no_match`, and `interrupted` in the result.

## Interactive selection

`session select` requires a TTY on stderr and always has a bounded global
`--timeout`. Candidate input comes from `--item`, `--input-file`,
`--input-base64`, or `--stdin`; with `--allow-walker` and no explicit source,
an explicit `--option walker-root=DIR` selects fzf's real walker:

```bash
cli-anything-fzf --json --timeout 120 session select \
  --item alpha --item beta --item gamma --query be
```

Multi-selection, `--expect`, layouts, headers, previews, and event bindings use
the same declarative inputs. Do not claim an interactive result passed unless a
real PTY operation ran.

## Safety grants

The following are denied until the matching global grant is explicit:

- Preview/info commands, `--with-shell`, execute/reload/become/change-preview,
  transform/background-transform, and trigger actions:
  `--allow-command-actions`.
- Profile/history writes: `--allow-filesystem-write`.
- Directory walking with an explicit `walker-root`: `--allow-walker`; `/` or any
  root containing the home directory additionally requires `--allow-broad-walker`.
- Full environment inheritance: `--allow-env-inherit`.
- An explicit `FZF_DEFAULT_OPTS_FILE`: `--allow-default-opts-file`.
- TCP and unsafe listeners: see the listener policy below.

Never pass an API key through `--set-env`, command text, or logs. Listener keys
come from a mode-0600 `--api-key-file`; results store only a fingerprint. Plans
list inherited environment names but never inherited values.

Authorizing a command-bearing fzf feature means fzf itself will intentionally
interpret that option/action with its configured shell. The Python harness
never uses `shell=True` and never concatenates an argv command.

## Profiles and configuration

Profiles are explicit, validated JSON and are never auto-discovered:

```bash
cli-anything-fzf --allow-filesystem-write profile create /tmp/paths.json \
  --name paths --option scheme=path --option layout=reverse
cli-anything-fzf --json profile inspect /tmp/paths.json
cli-anything-fzf --json profile compose /tmp/base.json /tmp/paths.json
```

Later profiles override non-repeatable options; repeatable bindings append.
Writes are locked, atomic, mode 0600, and do not overwrite without
`--overwrite`.

## Owned listeners

Prefer the default Unix socket contained inside a dedicated state directory:

```bash
state_dir=$(mktemp -d)
cli-anything-fzf --json listener start --state-dir "$state_dir" \
  --item alpha --item beta
cli-anything-fzf --json listener action --state-dir "$state_dir" \
  --action 'change-query(be)'
cli-anything-fzf --json listener status --state-dir "$state_dir"
cli-anything-fzf --json listener result --state-dir "$state_dir"
cli-anything-fzf --json listener stop --state-dir "$state_dir" --remove-state
```

Always close a listener you start. Lifecycle state records PID start-time ticks,
so stop signals only proven owned processes and verifies cleanup. Existing
socket/file/symlink collisions are preserved and refused.
After an accepting action exits fzf, use `listener result` to retrieve exact
query/expect prefixes and newline/NUL selection records before stale cleanup.

TCP requires `--allow-network-listener` and a non-zero port. A non-loopback
address also requires `--api-key-file`. `--unsafe` additionally requires
`--allow-unsafe-listener --allow-command-actions` plus the key file. A
command-capable POST action separately requires `--allow-command-actions`.

## JSON errors

Errors use one stable stdout envelope when `--json` is active:

```json
{"ok": false, "error": {"code": "plan_refused", "message": "...", "details": {}}}
```

Do not parse terminal text or infer success from JSON validity alone. Check the
process exit code, top-level `ok`, and the backend semantic fields.
