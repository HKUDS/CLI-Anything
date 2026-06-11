---
name: "cli-anything-tigris"
description: >-
  Command-line interface for Tigris object storage — wraps the official `tigris` CLI to expose buckets, objects, presigned URLs, snapshots, IAM, and scoped access keys to AI agents. Globally distributed, S3-compatible, no egress fees.
---

# cli-anything-tigris

A stateless command-line interface for [Tigris](https://www.tigrisdata.com)
object storage. Wraps the official `tigris` CLI so every Tigris primitive
(snapshots, IAM, scoped credentials, OAuth) is reachable through a single
agent-friendly entry point with `--json` everywhere.

## Scope

This harness is for the official Tigris CLI only. It shells out to the
`tigris` binary and assumes Tigris auth through `tigris login` or Tigris
access keys. It is not a generic S3 endpoint tool, and it does not manage
MinIO, Cloudflare R2, AWS S3, or arbitrary S3-compatible endpoints.

## Installation

```bash
# 1. Install the underlying Tigris CLI
npm install -g @tigrisdata/cli
# or:
brew install tigrisdata/tap/tigris

# 2. Authenticate (browser OAuth)
tigris login

# 3. Install this harness
pip install cli-anything-tigris
```

**Prerequisites:**
- Python 3.10+
- `tigris` CLI on PATH (the binary's alias is `t3`)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-tigris --help

# Start interactive REPL
cli-anything-tigris

# Whoami (JSON output for agents)
cli-anything-tigris --json auth whoami

# List buckets
cli-anything-tigris --json bucket list

# Upload a local file
cli-anything-tigris --json object put --bucket my-bucket --key path/to/file.txt --file ./local.txt

# Download an object
cli-anything-tigris --json object get --bucket my-bucket --key path/to/file.txt --output ./out.txt

# Server-side copy
cli-anything-tigris --json object cp t3://my-bucket/src.txt t3://my-bucket/dst.txt

# Take a snapshot
cli-anything-tigris --json snapshot take my-bucket --name baseline-v1

# Delete a bucket; --yes is required
cli-anything-tigris --json bucket delete --name old-bucket --yes

# Create a scoped access key for an agent run
cli-anything-tigris --json access-key create my-agent-key
cli-anything-tigris --json access-key assign tid_AaBb --bucket my-bucket --role Editor

# Rotate or delete access keys; --yes is required
cli-anything-tigris --json access-key rotate tid_AaBb --yes
cli-anything-tigris --json access-key delete tid_AaBb --yes

# Presigned download URL (1 hour)
cli-anything-tigris --json presign get --bucket my-bucket --key path/to/file.txt --expires 3600
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL with
tab-completion and history.

## Command Groups

### auth
OAuth-based authentication.

| Command | Description |
|---------|-------------|
| `login` | Browser OAuth login (`tigris login`) |
| `logout` | Log out of current session |
| `whoami` | Print authenticated user / org |

### bucket
Bucket CRUD.

| Command | Description |
|---------|-------------|
| `list` | List all buckets |
| `create --name NAME` | Create a bucket |
| `delete --name NAME --yes` | Delete an empty bucket (`--yes` required) |
| `info NAME` | Get bucket info |

### object
Object operations (wraps `tigris ls/cp/rm/stat`).

| Command | Description |
|---------|-------------|
| `list --bucket B [--prefix P] [--limit N]` | List objects |
| `put --bucket B --key K (--file F \| --text T)` | Upload an object |
| `get --bucket B --key K --output F` | Download an object |
| `delete --bucket B --key K` | Delete an object |
| `info --bucket B --key K` | Object metadata (HEAD / stat) |
| `cp SRC DST [-r]` | Copy. Accepts `t3://` or `tigris://` URIs. |

### presign
Time-limited URLs.

| Command | Description |
|---------|-------------|
| `get --bucket B --key K [--expires SEC]` | Presigned download URL |
| `put --bucket B --key K [--expires SEC]` | Presigned upload URL |

### snapshot
Point-in-time bucket snapshots — a Tigris-specific primitive.

| Command | Description |
|---------|-------------|
| `list BUCKET` | List snapshots for a bucket |
| `take BUCKET [--name N]` | Take a snapshot |

### access-key
Scoped programmatic credentials — combine with `snapshot` for per-agent isolation.

| Command | Description |
|---------|-------------|
| `list` | List all access keys |
| `create NAME` | Create a new access key (secret shown ONCE) |
| `get KEY_ID` | Show key details |
| `delete KEY_ID --yes` | Permanently delete a key (`--yes` required) |
| `assign KEY_ID --bucket B --role R` | Scope a key to a bucket + role |
| `rotate KEY_ID --yes` | Rotate a key's secret (`--yes` required) |

### iam
Policies and organization users.

| Command | Description |
|---------|-------------|
| `policy list` | List IAM policies |
| `policy create NAME --document FILE` | Create a policy from a JSON file |
| `user list` | List org users |
| `user invite EMAIL [--role R]` | Invite a user |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): tables, colors, formatted text
- **Machine-readable** (`--json`): JSON envelope (or upstream CLI's
  `--format json` output, echoed verbatim)

## For AI Agents

When using this CLI programmatically:

1. Always pass `--json` for parseable output.
2. Check return codes — 0 for success, non-zero for errors.
3. Read stderr for error messages.
4. `object cp` accepts `t3://bucket/key` or `tigris://bucket/key` URIs;
   server-side copies (t3 → t3) skip the round trip entirely.
5. `presign` returns a URL on stdout in human mode; in JSON mode it's the
   `url` field.
6. **For destructive work**: bucket deletion, access-key deletion, and
   access-key rotation require explicit `--yes`; take a `snapshot` of the
   target bucket first, then do the work, then either keep the snapshot or
   discard.
7. **For per-agent isolation**: `access-key create` + `access-key assign
   --bucket B --role Editor` to mint a key scoped to one bucket; revoke with
   `access-key delete` when the agent run ends.

## Why Tigris

- **Globally distributed.** Data placed close to wherever it's read.
- **No egress fees.** Agents pulling artifacts from anywhere don't incur
  per-region bandwidth charges.
- **Snapshots + scoped credentials.** Primitives generic S3-compatible
  providers don't ship — the foundation for per-agent isolation.
- **S3-compatible.** Useful alongside S3-aware tools, but this harness
  itself is not a generic S3/MinIO/R2/AWS endpoint manager.

## Version

1.0.0
