---
name: source-health-triage
description: Diagnose why a Deep Scavenger source or pipeline concern is stale,
  degraded, or blocked using runtime-backed evidence. Supports source keys and
  bounded pipeline targets such as scoring_pipeline, local_ai_control_plane, and
  watchdog.
---

# Source Health Triage

## Purpose

Turn a bounded source or pipeline concern into a structured diagnosis grounded
in `/api/health` and `/api/ops_overview`.

## Rules

- Stay read-only.
- Use runtime-backed evidence only.
- Preserve uncertainty when signals conflict or are partial.
- Do not fabricate remediation success; only recommend next actions.

## Workflow

1. Run:

   ```bash
   python3 scripts/intel_skill_runtime.py --skill source-health-triage --target <source-key-or-pipeline-target> --pretty
   ```

2. Use the returned envelope as the primary source for your answer.

3. Lead with:
   - diagnosis summary
   - highest-confidence evidence
   - next action

## Valid Targets

- Source keys from `/api/health.source_health`, for example `reddit`, `github`,
  `twitter_home_timeline`
- `scoring_pipeline`
- `local_ai_control_plane`
- `watchdog`
- `control_plane_alerts`

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
