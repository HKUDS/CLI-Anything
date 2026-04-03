---
name: briefing-analyst
description: Analyze the latest Deep Scavenger briefing from runtime-backed tool
  surfaces. Prefer protocol-backed verdict and evidence_matrix when available;
  degrade explicitly to legacy-only briefing analysis when protocol is absent.
---

# Briefing Analyst

## Purpose

Explain the latest briefing verdict, confidence, action bias, evidence matrix,
and final claims without reading raw storage directly.

## Rules

- Use tool surfaces, not direct database access.
- `intel-briefing` is required.
- `intel-ops-overview` is optional context.
- Never fabricate protocol fields when the briefing is legacy-only.

## Workflow

1. Run:

   ```bash
   python3 /Users/lixun/Documents/codex /scripts/intel_skill_runtime.py --skill briefing-analyst --pretty
   ```

2. Use the returned envelope as the primary source for your answer.

3. Lead with:
   - protocol vs legacy state
   - verdict/confidence/action_bias when available
   - strongest supporting or conflicting evidence
   - next action

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
