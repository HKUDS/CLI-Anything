---
name: intel-briefing
description: Use this skill for Deep Scavenger latest briefing reads, including
  legacy briefing content and protocol availability when the runtime exposes it.
allowed-tools: Bash(python3:*) Read Grep
metadata: {"version":"1.0.0","openclaw":{"skillKey":"intel-briefing","homepage":"http://127.0.0.1:8767/api/briefing","requires":{"anyBins":["python3"]},"apiKeySource":"none"}} 
---

# Intel Briefing

## Overview

This skill reads the latest Deep Scavenger briefing surface. Default behavior
is raw passthrough: return the runtime-backed briefing payload as-is inside the
tool adapter response.

## Tool Permission Policy

Request runtime permission for `python3` only. Do not read SQLite directly. Do
not mutate any runtime state.

## API Surface

- Endpoint: `GET /api/briefing`
- Base URL: `http://127.0.0.1:8767`

## Usage Example

```bash
python3 scripts/intel_tool_runtime.py --tool intel-briefing --pretty
```

## Output Contract

Return:

- `endpoint_used`
- `request_payload`
- `raw_response`
- `error`

Do not summarize unless the user explicitly asks for analysis.

## Guardrails

- Do not fabricate `briefing_protocol`, `final_claims`, or `trace_generated_at`
  when the upstream payload is legacy-only.
- Do not treat briefing presence as proof of high confidence; that judgment
  belongs to higher-level analysis skills.
