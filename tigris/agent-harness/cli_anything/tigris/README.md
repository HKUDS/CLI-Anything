# cli-anything-tigris

CLI-Anything harness for [Tigris](https://www.tigrisdata.com) — a globally
distributed, S3-compatible object storage service with no egress fees.

## Install

```bash
pip install cli-anything-tigris
```

## Quick start

```bash
# Set credentials (sign up at https://storage.new)
export TIGRIS_STORAGE_ACCESS_KEY_ID=tid_...
export TIGRIS_STORAGE_SECRET_ACCESS_KEY=tsec_...

# Interactive REPL
cli-anything-tigris

# Or use directly
cli-anything-tigris --json bucket list
cli-anything-tigris --json object put --bucket my-bucket --key hello.txt --text "hi"
cli-anything-tigris --json object cp ./local.bin tigris://my-bucket/remote.bin
cli-anything-tigris --json presign get --bucket my-bucket --key hello.txt
```

See [SKILL.md](skills/SKILL.md) for the full command reference and agent-usage
guidance.
