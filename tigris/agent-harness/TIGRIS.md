# Agent Harness: Tigris Object Storage CLI

## Purpose

This harness provides a standard operating procedure (SOP) and toolkit for coding
agents (Claude Code, Codex, etc.) to interact with Tigris — a globally distributed,
S3-compatible object storage service with no egress fees. The goal: let AI agents
push artifacts (model checkpoints, datasets, generated media, logs) to durable
global storage without needing a browser UI or AWS SDK boilerplate.

## Requirements

- **Python 3.10+** (uses PEP 604 union syntax and PEP 585 generic types). On
  macOS, the system Python is 3.9 — use `pyenv`, `uv`, or `brew install python@3.12`.

## Backend Description

**Tigris S3-compatible API** at `https://t3.storage.dev` (configurable via
`--endpoint`).

- Protocol: S3 REST over HTTPS, signature v4
- Client: `boto3` with `endpoint_url` set to the Tigris endpoint
- Credentials: standard AWS credential chain, with `TIGRIS_STORAGE_*` env vars
  taking precedence over `AWS_*` if both are set
- Stateless: no session or connection state between CLI invocations

Tigris is globally distributed — every bucket is automatically replicated and
served from the region closest to the reader. No region configuration is
required.

## Architecture

```
agent-harness/
├── setup.py                          # Package setup with click, prompt-toolkit, boto3
├── TIGRIS.md                         # This file -- SOP and architecture
└── cli_anything/
    └── tigris/
        ├── __init__.py
        ├── __main__.py               # python -m entry point
        ├── README.md                 # Usage docs
        ├── tigris_cli.py             # Click CLI + REPL dispatcher
        ├── core/
        │   ├── __init__.py
        │   ├── bucket.py             # list, create, delete, info
        │   ├── object.py             # list, put, get, delete, info, cp
        │   └── presign.py            # presigned URLs (get, put)
        ├── utils/
        │   ├── __init__.py
        │   ├── tigris_backend.py     # boto3 wrapper for Tigris S3 API
        │   └── repl_skin.py          # Unified REPL skin (unmodified copy)
        ├── skills/
        │   └── SKILL.md
        └── tests/
            ├── __init__.py
            ├── TEST.md               # Test plan and results
            └── test_core.py          # Unit tests (mocked boto3)
```

## Command Groups

### bucket
Bucket CRUD operations.

| Command | Description |
|---------|-------------|
| `bucket list` | List all buckets owned by the authenticated account |
| `bucket create --name NAME` | Create a new bucket |
| `bucket delete --name NAME` | Delete an empty bucket |
| `bucket info NAME` | Verify a bucket exists and report endpoint |

### object
Object CRUD plus a friendlier `cp` wrapper.

| Command | Description |
|---------|-------------|
| `object list --bucket B [--prefix P] [--limit N]` | List objects, optionally prefix-filtered |
| `object put --bucket B --key K --file F` | Upload a local file |
| `object put --bucket B --key K --text T` | Upload inline text content |
| `object get --bucket B --key K [--output F]` | Download to file or stdout (raw bytes) |
| `object delete --bucket B --key K` | Delete an object |
| `object info --bucket B --key K` | Get object metadata without downloading |
| `object cp SRC DST` | Copy between local paths and `tigris://bucket/key` |

### presign
Time-limited URLs for handing object access to external tools or users.

| Command | Description |
|---------|-------------|
| `presign get --bucket B --key K [--expires SEC]` | Presigned download URL |
| `presign put --bucket B --key K [--expires SEC]` | Presigned upload URL |

## Credentials

Credential resolution order:

1. Explicit `--access-key` / `--secret-key` CLI flags
2. `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY` env vars
3. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars (standard AWS chain)

Sign up at [storage.new](https://storage.new) to get keys.

## Output Modes

- **Human-readable** (default): tables, colors, formatted text via the REPL skin
- **Machine-readable** (`--json`): structured JSON suitable for agent consumption

## Agent Usage

When agents drive this CLI, they should:

1. Pass `--json` for parseable output.
2. Inspect process return codes (0 = success).
3. Read stderr for error messages.
4. Use `object cp tigris://src/key tigris://dst/key` for server-side copies — no
   data flows through the agent's network, no egress charges.
5. Use `presign get/put` to hand off object access to other tools or downstream
   agents without sharing the agent's own credentials.

## Testing

- `tests/test_core.py` — unit tests with `boto3` fully mocked; passable without
  a Tigris account or network access.
- See `tests/TEST.md` for the testing matrix and how to run real end-to-end
  tests against an actual Tigris account.
