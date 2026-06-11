# Agent Harness: Tigris Object Storage CLI

## Purpose

This harness provides a standard operating procedure (SOP) and toolkit for
coding agents (Claude Code, Codex, etc.) to interact with
[Tigris](https://www.tigrisdata.com) — a globally distributed, S3-compatible
object storage service with no egress fees.

The harness **wraps the official `tigris` CLI** rather than reimplementing
the S3 protocol. This means agents get access to every Tigris primitive
(snapshots, IAM, scoped access keys, organizations, OAuth) — not just
generic S3 ops — and the harness inherits new commands as the upstream CLI
ships them.

This is intentionally Tigris CLI-only tooling. Do not use this harness as a
generic S3 endpoint wrapper, and do not treat it as MinIO, Cloudflare R2, AWS
S3, or arbitrary S3-compatible endpoint management. It shells out to the
official `tigris` binary and follows that CLI's auth and command model.

## Requirements

- **Python 3.10+** (uses PEP 604 union syntax and PEP 585 generic types).
  On macOS the system Python is 3.9 — use `pyenv`, `uv`, or
  `brew install python@3.12`.
- **The Tigris CLI on PATH.** Install with one of:

  ```bash
  npm install -g @tigrisdata/cli
  brew install tigrisdata/tap/tigris
  ```

  Then `tigris login` once to authenticate (browser OAuth).

## Backend Description

Each command in this harness builds a `tigris <args> --format json`
invocation, runs it via `subprocess.run`, and parses the JSON output.
Commands the upstream CLI does not JSON-format (e.g. `login`, `cp`) are
streamed directly to the caller's TTY or captured as text.

Credentials are normally resolved by the `tigris` CLI itself (via the OAuth
session created by `tigris login`). Explicit `--access-key` / `--secret-key`
flags export `TIGRIS_STORAGE_*` and `AWS_*` env vars into the child process
for setups that rely on env-based auth.

## Architecture

```
agent-harness/
├── .gitignore
├── setup.py                           # cli, prompt-toolkit; no boto3
├── TIGRIS.md                          # this file
└── cli_anything/
    └── tigris/
        ├── __init__.py
        ├── __main__.py                # python -m entry point
        ├── README.md                  # usage docs
        ├── tigris_cli.py              # click CLI + REPL dispatcher
        ├── core/
        │   ├── auth.py                # login, logout, whoami
        │   ├── bucket.py              # list, create, delete, info
        │   ├── object.py              # list, put, get, delete, info, cp
        │   ├── presign.py             # presign get/put
        │   ├── snapshot.py            # list, take
        │   ├── access_key.py          # list, create, get, delete, assign, rotate
        │   └── iam.py                 # policies + users
        ├── utils/
        │   ├── tigris_backend.py      # subprocess wrapper around `tigris`
        │   └── repl_skin.py           # unified REPL skin (unmodified copy)
        ├── skills/
        │   └── SKILL.md
        └── tests/
            ├── TEST.md
            ├── test_core.py           # subprocess.run mocked
            └── test_full_e2e.py       # real `tigris` CLI on PATH, env-gated
```

## Command Groups

| Group        | What it wraps                          | Operations |
|--------------|----------------------------------------|------------|
| `auth`       | `tigris login/logout/whoami`           | login, logout, whoami |
| `bucket`     | `tigris buckets ...`                   | list, create, delete --yes, info |
| `object`     | `tigris ls/cp/rm/stat`                 | list, put, get, delete, info, cp |
| `presign`    | `tigris presign`                       | get, put |
| `snapshot`   | `tigris snapshots ...`                 | list, take |
| `access-key` | `tigris access-keys ...`               | list, create, get, delete --yes, assign, rotate --yes |
| `iam`        | `tigris iam policies / users ...`      | policy list/create, user list/invite |

## Output Modes

- **Human-readable** (default): tables, colors, formatted text via the REPL skin
- **Machine-readable** (`--json`): the upstream CLI's `--format json` output,
  echoed verbatim (with a thin envelope for commands that don't natively
  support JSON, like `cp`).

## Agent Usage

When agents drive this CLI:

1. Pass `--json` for parseable output.
2. Inspect return codes (0 = success).
3. Read stderr for error messages.
4. Use `object cp t3://src/key t3://dst/key` for server-side copies — no data
   flows through the agent, no egress charges.
5. Use `presign get/put` to hand off object access to other tools or
   downstream agents without sharing credentials.
6. Use `snapshot take` before destructive work to make a recovery point;
   `snapshot list` to find one to restore from.
7. Use `access-key create` + `access-key assign --bucket B --role Editor` to
   mint a scoped key for an agent run, then `access-key delete` to revoke.
8. Bucket deletion, access-key deletion, and access-key rotation require
   explicit `--yes`; without it, the harness refuses to call the backend.

## Testing

- `tests/test_core.py` — unit tests with `subprocess.run` fully mocked;
  passable without the `tigris` CLI installed or any network access.
- `tests/test_full_e2e.py` — real-bucket tests; gated on
  `CLI_ANYTHING_TIGRIS_RUN_E2E=1` plus `tigris` on PATH and an authenticated
  session.

See `tests/TEST.md` for run instructions.
