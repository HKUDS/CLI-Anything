# cli-anything-tigris

CLI-Anything harness for [Tigris](https://www.tigrisdata.com) — a globally
distributed, S3-compatible object storage service with no egress fees.

This harness **wraps the official `tigris` CLI**, so every Tigris primitive
(snapshots, IAM, scoped access keys, OAuth login) is reachable through one
agent-friendly entry point with `--json` everywhere.

It is Tigris CLI-only tooling, not a generic S3/MinIO/R2/AWS endpoint
manager.

## Install

```bash
# 1. Install the underlying Tigris CLI
npm install -g @tigrisdata/cli      # or: brew install tigrisdata/tap/tigris

# 2. Authenticate (browser OAuth)
tigris login

# 3. Install this harness
pip install cli-anything-tigris
```

## Quick start

```bash
# Interactive REPL
cli-anything-tigris

# Or drive directly
cli-anything-tigris --json auth whoami
cli-anything-tigris --json bucket list
cli-anything-tigris --json object cp ./local.bin t3://my-bucket/remote.bin
cli-anything-tigris --json snapshot take my-bucket --name baseline-v1
cli-anything-tigris --json access-key create agent-run-42
cli-anything-tigris --json access-key rotate tid_AaBb --yes
cli-anything-tigris --json presign get --bucket my-bucket --key hello.txt
```

Bucket deletion, access-key deletion, and access-key rotation require
explicit `--yes`.

See [SKILL.md](skills/SKILL.md) for the full command reference and
agent-usage guidance.
