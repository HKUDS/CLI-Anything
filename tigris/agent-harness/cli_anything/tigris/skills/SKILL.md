---
name: >-
  cli-anything-tigris
description: >-
  Command-line interface for Tigris object storage — a globally distributed, S3-compatible blob store with no egress fees. Manage buckets, upload/download objects, generate presigned URLs. Designed for AI agents and automation via the S3 API.
---

# cli-anything-tigris

A stateless command-line interface for [Tigris](https://www.tigrisdata.com) object storage, built on the S3-compatible API via boto3. Designed for AI agents and power users who need to push artifacts to durable global storage without a browser UI.

## Installation

```bash
pip install cli-anything-tigris
```

**Prerequisites:**
- Python 3.10+
- A Tigris account and access key — sign up at [storage.new](https://storage.new)

## Credentials

The CLI reads credentials from environment variables in this order:

1. `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY` (Tigris-specific)
2. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (standard AWS chain)

You can also pass `--access-key` / `--secret-key` directly on the command line.

The default endpoint is `https://t3.storage.dev`. Override with `--endpoint` if you're on a regional URL.

## Usage

### Basic Commands

```bash
# Show help
cli-anything-tigris --help

# Start interactive REPL
cli-anything-tigris

# List buckets (JSON output for agents)
cli-anything-tigris --json bucket list

# Upload a local file
cli-anything-tigris --json object put --bucket my-bucket --key path/to/file.txt --file ./local.txt

# Download an object to a local path
cli-anything-tigris --json object get --bucket my-bucket --key path/to/file.txt --output ./out.txt

# Generate a presigned download URL (1 hour)
cli-anything-tigris --json presign get --bucket my-bucket --key path/to/file.txt --expires 3600
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL with tab-completion and history.

## Command Groups

### bucket
Manage Tigris buckets.

| Command | Description |
|---------|-------------|
| `list` | List all buckets |
| `create --name NAME` | Create a new bucket |
| `delete --name NAME` | Delete an empty bucket |
| `info NAME` | Get bucket info |

### object
Manage objects within buckets.

| Command | Description |
|---------|-------------|
| `list --bucket B [--prefix P] [--limit N]` | List objects in a bucket |
| `put --bucket B --key K (--file F \| --text T)` | Upload an object |
| `get --bucket B --key K [--output F]` | Download an object |
| `delete --bucket B --key K` | Delete an object |
| `info --bucket B --key K` | Get object metadata (HEAD) |
| `cp SRC DST` | Copy between local paths and `tigris://bucket/key` |

### presign
Generate presigned URLs for time-limited object access.

| Command | Description |
|---------|-------------|
| `get --bucket B --key K [--expires SEC]` | Presigned download URL |
| `put --bucket B --key K [--expires SEC]` | Presigned upload URL |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): tables, colors, formatted text
- **Machine-readable** (`--json` flag): structured JSON for agent consumption

```bash
# Human output
cli-anything-tigris bucket list

# JSON for agents
cli-anything-tigris --json bucket list
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json`** for parseable output.
2. **Check return codes** — 0 for success, non-zero for errors.
3. **Parse stderr** for error messages on failure.
4. **`object cp` accepts `tigris://bucket/key` URIs** — server-side copies (tigris → tigris) skip the round-trip entirely.
5. **`presign get/put` returns a URL on stdout** in human mode; in JSON mode it's the `url` field.

## Why Tigris

- **Globally distributed.** Data is automatically placed close to wherever it's read; no manual region configuration.
- **No egress fees.** Agents pulling artifacts from anywhere in the world don't incur per-region bandwidth charges.
- **S3-compatible.** Drops in alongside boto3, `mountpoint-s3`, and any other S3-aware tool.

## Version

1.0.0
