---
name: "cli-anything-paperclip"
description: "CLI harness for Paperclip — orchestrate AI agent companies via a stateful REPL or one-shot commands"
---

# Paperclip CLI — AI Agent Company Orchestration

A stateful CLI and interactive REPL for managing AI-agent companies via the Paperclip control plane API.

## Installation

```bash
# Install from PyPI
pip install cli-anything-paperclip

# Or from source
pip install git+https://github.com/paperclipai/paperclip.git#subdirectory=cli-anything/agent-harness
```

## Commands

### Session Management

```bash
pc session new --name my-session --api-base http://localhost:3100
pc session load --name my-session
pc session save
pc session list
pc session show
```

### Company

```bash
pc company list
pc company list --status active
pc company create --name "Acme Corp"
pc company get cmp_xxx
pc company export --out backup.json --company-id cmp_xxx
pc company import backup.json --target new
pc company delete cmp_xxx --yes
```

### Project

```bash
pc project list --company-id cmp_xxx
pc project create --name "Backend API" --company-id cmp_xxx
pc project get proj_xxx
```

### Issue

```bash
pc issue list --status open
pc issue list --assignee-agent-id age_xxx
pc issue create --title "Fix login bug" --priority high --company-id cmp_xxx
pc issue get iss_xxx
pc issue update iss_xxx --status done
pc issue checkout iss_xxx --agent-id age_xxx
pc issue comment iss_xxx --body "Fixed in PR #42"
```

### Agent

```bash
pc agent list
pc agent create --name "Backend Dev" --adapter claude_local --company-id cmp_xxx
pc agent get age_xxx
pc agent delete age_xxx --yes
```

### Approval

```bash
pc approval list --status pending
pc approval approve apr_xxx
pc approval reject apr_xxx
```

### Routine

```bash
pc routine list
pc routine trigger rtn_xxx
pc routine logs rtn_xxx --limit 50
```

### Heartbeat

```bash
pc heartbeat run --agent-id age_xxx --source on_demand --trigger manual
pc heartbeat run --agent-id age_xxx --json --debug
```

### Preview

```bash
pc preview status run_xxx
pc preview live run_xxx --poll-ms 500
```

### Context

```bash
pc context get
pc context set --company-id cmp_xxx --api-key sk-xxx
```

## REPL Mode

Running `cli-anything-paperclip` with no arguments starts an interactive REPL:

```bash
cli-anything-paperclip
# or
cli-anything-paperclip repl
```

```
◆ Paperclip REPL v1.0.0
  Type "help" for commands, "exit" to quit.

paperclip> company list
✓ 2 companies
id=cmp_abc name=Acme status=active
id=cmp_def name=DevCo status=active

paperclip> issue list --status open
✓ 5 open issues
...
```

## JSON Output

All commands support `--json` for machine-readable output:

```bash
pc company list --json
```

```json
{
  "ok": true,
  "data": [...],
  "count": 3
}
```

## Session Files

Sessions are stored as JSON at `~/.paperclip/sessions/<name>.json`:

```json
{
  "name": "my-session",
  "api_base": "http://localhost:3100",
  "api_key": "sk-...",
  "company_id": "cmp_xxx",
  "profile": "default"
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PAPERCLIP_API_URL` | API base URL (default: http://localhost:3100) |
| `PAPERCLIP_API_KEY` | API bearer token |
| `PAPERCLIP_COMPANY_ID` | Default company ID |

## Error Handling

Agents should check for `"ok": true` in responses and handle errors:

```python
import requests

resp = requests.post(f"{api_base}/api/issues", json={"title": "..."}, headers=headers)
data = resp.json()
if not data.get("ok"):
    raise RuntimeError(f"API error: {data}")
```
