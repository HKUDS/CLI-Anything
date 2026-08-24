---
name: cli-anything-opencti
description: >-
  Command-line interface for the OpenCTI threat intelligence platform.
  Queries and creates observables, indicators, reports, cases, threat actors,
  malware, campaigns, tools, and relationships over GraphQL API v7.
---

# cli-anything-opencti

CLI harness for OpenCTI threat intelligence — built with the CLI-Anything
pattern. Verified against OpenCTI platform v7 (7.260824.0).

## Installation

```bash
pip install cli-anything-opencti
```

## Configuration

```bash
cli-anything-opencti config set --url https://your-opencti.example.com --token YOUR_API_TOKEN

# Or environment variables
export OPENCTI_BASE_URL=https://your-opencti.example.com
export OPENCTI_API_KEY=your-api-token
export OPENCTI_TIMEOUT=60  # optional, default 30s
```

## Command Groups

| Group | Commands |
|-------|----------|
| observable | search, get, add |
| indicator | list, get, search-pattern, add |
| report | list, get, add |
| relationship | list, add |
| case | list, get, add (--type incident\|rfi\|rft) |
| entity | list, get, add (threat-actor\|intrusion-set\|malware\|campaign\|tool) |
| config | set, test |
| top-level | status, whoami, search, export-stix, delete |

## For AI Agents

- Always pass `--json` before the subcommand: `cli-anything-opencti --json indicator list`
- Status messages go to stderr; stdout is always parseable
- Use `--all` to follow Relay pagination past the default page (`--limit` sets page size)
- Check return codes: 0 = success, non-zero = error
- All IDs are UUID strings; `standard_id` is the STIX 2.1 ID
- Writes: `observable add`, `indicator add`, `report add`, `case add --type ...`,
  `entity add TYPE NAME`, `relationship add FROM TO TYPE`
- Deletion requires `--force`: without it, `delete ID` is a dry-run
- `export-stix --id <id>` emits STIX 2.1 JSON for any object ID
- Global search spans every STIX core object; narrow it with `--types`
- Relationship types are validated server-side (e.g. actor->observable must be `related-to`, not `uses`)
- Not exposed: connector management, CSV/JSON feed ingestion, draft workspaces
