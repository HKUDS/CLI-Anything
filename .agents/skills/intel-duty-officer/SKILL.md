---
name: intel-duty-officer
description: Read the live Deep Scavenger control plane and return a single
  operator snapshot grounded in runtime truth. Use when the user wants the
  current intel system state, top alerts, source freshness, scoring posture, or
  briefing availability.
---

# Intel Duty Officer

## Purpose

Produce one bounded, read-only operator snapshot from the shipped Deep
Scavenger control plane.

## Rules

- Treat runtime APIs as authoritative.
- Do not read SQLite directly.
- Do not mutate runtime state.
- If required runtime contracts are unavailable, report contract failure instead
  of improvising from memory.

## Workflow

1. Run:

   ```bash
   python3 scripts/intel_skill_runtime.py --skill intel-duty-officer --pretty
   ```

2. Use the returned JSON envelope as the primary source for your answer.

3. Lead with:
   - overall status
   - top degraded signals
   - next actions

4. If the envelope status is `failed`, tell the user the control-plane contract
   read failed and cite the returned error.

## Output Contract

The adapter returns:

- `skill_name`
- `contract_version`
- `status`
- `summary`
- `findings`
- `evidence`
- `confidence`
- `next_actions`
- `errors`
