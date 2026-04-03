---
name: intel-health
description: Use this skill for Deep Scavenger runtime health reads, including
  source freshness, local AI control-plane status, scoring pipeline state, and
  control-plane alert fanout state.
allowed-tools: Bash(python3:*) Read Grep
metadata: {"version":"1.0.0","openclaw":{"skillKey":"intel-health","homepage":"http://127.0.0.1:8767/api/health","requires":{"anyBins":["python3"]},"apiKeySource":"none"}} 
---

# Intel Health

## Overview

This skill reads the Deep Scavenger runtime health surface. Default behavior is
raw passthrough: return the runtime-backed health payload as-is inside the tool
adapter response.

## Tool Permission Policy

Request runtime permission for `python3` only. Do not read SQLite directly. Do
not mutate any runtime state.

## API Surface

- Endpoint: `GET /api/health`
- Base URL: `http://127.0.0.1:8767`
- Relevant nested surface: `control_plane_alerts` may include `events[]`
  summaries from watchdog fanout state

## Usage Example

```bash
python3 scripts/intel_tool_runtime.py --tool intel-health --pretty
```

## Output Contract

Return:

- `endpoint_used`
- `request_payload`
- `raw_response`
- `error`

Do not summarize unless the user explicitly asks for analysis.

## Guardrails

- Do not fabricate health fields missing from `/api/health`.
- Do not treat this output as permission to restart services or clear state.
