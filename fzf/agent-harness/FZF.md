# fzf CLI-Anything Harness: Architecture and Operating Procedure

## Compatibility anchor

This harness targets the real `fzf 0.74.5 (c0a193e0)` backend. The development
binary was `/var/home/louranicas/.local/bin/fzf`, resolving into the local pinned
toolchain, with SHA-256
`c8d3ac08594f271a108528beb15338c42be113d392816b10bf5955cd139293e8`.
The installed path is not baked into the package: runtime discovery accepts an
explicit `--backend` and otherwise resolves `fzf` from `PATH`.

The option ledger was derived from live `fzf --help` and `fzf --man` output.
The captured help was 13,171 bytes with SHA-256
`944def5bbeff3f7450b69aec8519cf762091704ad52d49ee735fe4cd168867d0`;
the normalized rendered man page had SHA-256
`d246636f6baf06684abbc468a0cf60fcd9679144bae148ecabdc4a7b54e2a46b`.
`capabilities.json` is the shipped, machine-readable coverage contract;
`schemas.json` is the Draft 2020-12 contract for JSON envelopes, plans,
profiles, byte records/results, backend identities, and listener state.

## Backend and data model

fzf is already a command-line program, so this harness does not reimplement its
matcher or terminal interface. It adds a structured planning, policy, evidence,
and lifecycle layer around argv-array invocation of the real executable.

The backend consumes a byte stream of newline- or NUL-delimited candidates and
emits accepted candidates in the selected delimiter mode. Depending on options,
the output may begin with the query and/or an expected key. Process status is a
separate semantic channel: 0 is normal acceptance, 1 is no match, 2 is an error,
126/127 are `become` failures, and 130 is interruption.

The harness has no synthetic project format. Its persistent data is narrowly
scoped to:

- user-supplied JSON profiles containing declarative options and bindings;
- explicit fzf history files, owned by fzf;
- listener ownership records and disposable input/log files in a caller-selected
  state directory.

## Command map

| Group | Purpose | Backend use |
|---|---|---|
| `backend` | Resolve, identify, hash, version-check, show help/man, verify the option ledger | `fzf --version`, `--help`, `--man` |
| `capability` | Query/export options, events, actions, environment variables, policies, and effect classes | none unless `verify` is requested |
| `plan` | Compose profiles and structured options into an exact sanitized argv/environment/input plan | none |
| `filter` | Deterministic synchronous matching with exact byte/NUL result accounting | `fzf --filter ... --sync` |
| `session` | Bounded interactive selection with TTY checks and cancellation | interactive `fzf` |
| `profile` | Create, validate, inspect, and compose explicit profile files | none |
| `config` | Inspect ambient fzf variables with secrets redacted; optionally parse explicit config files | none |
| `shell` | Retrieve backend-emitted Bash, Zsh, Fish, or Nushell integration | `fzf --bash|--zsh|--fish|--nushell` |
| `listener` | Start/status/action/result/stop an owned Unix-socket or explicitly authorized TCP listener | interactive `fzf --listen...` |

All execution is through argv arrays. Python never invokes a shell. Strings that
fzf itself intentionally passes to its configured shell remain opaque argv values
and require an explicit hazardous-feature policy.

## Capability and option model

All 127 distinct explicit option headings from the 0.74.5 help/man surface are
represented in `capabilities.json`. The ledger has 131 explicit records because
the documented `--wrap-word`, `--no-expect`, `--no-header-lines-border`,
`--no-list-border`, and `--tty-default` forms have distinct semantics even
though they occur only in man prose rather than option headings. The backend
also accepts implicit `--no-*` forms for 59 listed base options. Ten already
have explicit records and 49 are safely materialized by the loader, producing
180 agent-addressable option records in total. These forms were probed one by
one against the pinned executable; unsupported guesses such as
`--no-disabled` are not admitted. Each entry
records arity, repeatability, category, validation type, effect classes, policy,
and availability through the harness. Events and all documented actions are also
inventoried. Background transform variants are represented by the documented
`bg-transform-*` family rule and classified as subprocess-capable. Footer
actions and click-derived environment variables mentioned outside the action
table are included as well.

The generic declarative layer accepts repeatable `--option NAME[=VALUE]` values.
Names must resolve through the ledger; values are grammar-checked before an argv
can be emitted. A forward-compatibility escape hatch accepts only one unknown
long option token at a time, never positional values or shell fragments, and is
disabled unless the caller explicitly authorizes unknown options. Dry-run output
always exposes it.

Some backend options have dedicated lifecycle surfaces rather than being allowed
in generic runs: `--listen`/`--listen-unsafe` belong to `listener`, shell emission
flags belong to `shell`, and help/version/man belong to `backend`.

## Security boundaries

Execution defaults to a small constructed environment. Ambient `FZF_*`, API
keys, shell defaults, and option files are not inherited. Full environment
inheritance is rejected unless explicitly authorized, and plans list inherited
variable names without leaking secret values.

Explicit `FZF_DEFAULT_OPTS` and `FZF_DEFAULT_OPTS_FILE` inputs are parsed into
the same typed option stream before input framing and policy evaluation. They
are mutually exclusive, and later explicit CLI/profile options may override a
non-repeatable default. Managed listener address/mode options cannot be supplied
through either source.

The following are hazardous and default-denied:

- `--preview`, `--info-command`, `--with-shell`, `FZF_DEFAULT_COMMAND`, and
  command-bearing bind actions (`execute`, `execute-silent`, `become`, `reload`,
  `reload-sync`, `preview`, `transform*`, and `bg-transform*`);
- filesystem-writing history and explicit config/profile output;
- an implicit directory walker or broad roots;
- TCP listeners, non-loopback listeners, and `--listen-unsafe`;
- environment inheritance and unknown future options.

Each requires the matching explicit policy flag and is recorded in
`effect_classes`, `hazards`, and `policy_grants` in the plan/result. API keys are
read only from an explicit file, passed to the backend through its environment,
and represented as `<redacted>` plus a fingerprint. They are never accepted as a
command-line value or written to listener metadata.

Unix sockets are the listener default. Listener metadata records the harness and
backend PIDs plus Linux process start times, so `stop` will not signal a recycled
PID. Startup is transactional: a failed readiness probe terminates the worker and
removes owned state. Normal exit and stop clean the socket and owned disposable
files; user-supplied input and key files are never deleted.

## Iteration and evidence procedure

For every new or changed workflow:

1. Probe exact executable, realpath, digest, and version.
2. Build a plan and inspect exact argv, input source, constructed environment,
   expected output mode, effects, hazards, and refusals.
3. Exercise dry-run or a disposable input/profile/state directory.
4. Execute one bounded operation.
5. Re-probe backend/listener/files and compare output bytes, order, delimiters,
   semantic status, and cleanup against the plan.
6. Refine implementation and rerun the old suite plus the new regression.

The backend exit code is never treated as the sole oracle. Filtering checks exact
selection bytes and ordering; shell emission checks non-empty backend-authored
scripts; listener checks include GET state, POST action behavior, authentication,
ownership, socket containment, and post-stop cleanup.

The release iteration closed discrepancies found only by execution: Click's
non-standalone dispatcher initially swallowed fzf's exit 1, the first Unix
listener probe used HTTP framing fzf rejected, and the initially authorized
directory walker still received an empty pipe rather than terminal input.
Regression tests now assert the outer no-match exit, real walker results, HTTP
GET/POST compatibility, PID start-time ownership, TERM/KILL fallback (including
a command-action descendant), and absence of owned sockets or processes after
cleanup.

Repository regression validation also exposed that the shared REPL template
auto-detected a packaged skill but no longer displayed that path. The template
and this harness copy now restore the `Skill:` banner line while retaining the
global installation hint; the repository skill-generation suite covers it.
Malformed UTF-8 is also tested explicitly: the harness preserves exact backend
output bytes, while documenting that fzf itself normalizes malformed input bytes
to U+FFFD.

## Rendering and preview gap assessment

The CLI-Anything media rendering gap does not apply: fzf is itself the authentic
terminal renderer and matching engine. Its `--preview` feature is command
execution inside the real backend, not a CLI-Anything preview-bundle producer.
The harness therefore does not generate synthetic screenshots or claim support
for the repository preview-bundle protocol. Preview commands are exposed only
behind the subprocess policy boundary.

## Rollback and uninstall

Filtering and inspection are read-only. A listener is rolled back with
`listener stop`; stale ownership state can be removed only after status proves
both recorded processes are gone. Profile creation refuses overwrite unless
requested. History files are caller-owned and are never deleted by uninstall.

Uninstall the Python package with `python -m pip uninstall cli-anything-fzf`.
This does not remove fzf, profile/history files, or caller-selected state
directories. Stop any owned listener before uninstalling.
