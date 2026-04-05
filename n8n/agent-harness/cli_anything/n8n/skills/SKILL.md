---
name: cli-anything-n8n
description: >-
  Command-line interface for n8n workflow automation platform.
  Manages workflows, executions, credentials, variables, and tags.
  Based on n8n Public API v1.1.1 (n8n >= 1.0.0).
---

# cli-anything-n8n

CLI harness for n8n workflow automation — built with the CLI-Anything pattern.
Verified against n8n OpenAPI spec v1.1.1.

## Installation

```bash
pip install cli-anything-n8n
```

## Configuration

```bash
cli-anything-n8n config set base_url https://your-n8n-instance.com
cli-anything-n8n config set api_key your-api-key

# Or environment variables
export N8N_BASE_URL=https://your-n8n-instance.com
export N8N_API_KEY=your-api-key
export N8N_TIMEOUT=60  # optional, default 30s
```

## Command Groups

| Group | Commands |
|-------|----------|
| workflow | list, get, create, update, delete, activate, deactivate, tags, set-tags, transfer |
| execution | list, get, delete, retry |
| credential | create, delete, schema, transfer |
| variable | list, create, update, delete |
| tag | list, get, create, update, delete |
| config | show, set |

## For AI Agents

- Always use `--json` flag for structured output
- Use `@file.json` to pass complex JSON from files
- Check return codes: 0 = success, non-zero = error
- All IDs are strings, not integers
- API key is always masked in `config show` output
- Not available in public API: data tables, credential listing, execution stop
