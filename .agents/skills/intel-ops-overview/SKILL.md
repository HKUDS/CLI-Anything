---
name: intel-ops-overview
description: Use this skill for Deep Scavenger ops overview reads, including
  alerts, scoring backlog, harness overview, latest briefing summary, and
  control-plane alert fanout context.
allowed-tools: Bash(python3:*) Read Grep
metadata: {"version":"1.0.0","openclaw":{"skillKey":"intel-ops-overview","homepage":"http://127.0.0.1:8767/api/ops_overview","requires":{"anyBins":["python3"]},"apiKeySource":"none"}} 
---

# Intel Ops Overview

## Overview

This skill reads the Deep Scavenger operator overview surface. Default behavior
is raw passthrough: return the runtime-backed ops payload as-is inside the tool
adapter response.

## Tool Permission Policy

Request runtime permission for `python3` only. Do not read SQLite directly. Do
not mutate any runtime state.

## API Surface

- Endpoint: `GET /api/ops_overview`
- Base URL: `http://127.0.0.1:8767`
- Relevant nested surface: `control_plane_alerts` may include `events[]`
  summaries and fanout state for current watchdog-dispatched alerts

## Usage Example

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_tool_runtime.py --tool intel-ops-overview --pretty
```

## Output Contract

Return:

- `endpoint_used`
- `request_payload`
- `raw_response`
- `error`

Do not summarize unless the user explicitly asks for analysis.

## Guardrails

- Do not infer missing alert types or harness states.
- Do not claim latest briefing protocol fields unless they exist upstream.
