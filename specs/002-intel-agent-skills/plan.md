# Implementation Plan: Intel Agent Skills Control Plane

**Branch**: `002-intel-agent-skills` | **Date**: 2026-04-03 | **Spec**: [/Users/lixun/Documents/codex /specs/002-intel-agent-skills/spec.md](/Users/lixun/Documents/codex /specs/002-intel-agent-skills/spec.md)  
**Input**: Feature specification from `/Users/lixun/Documents/codex /specs/002-intel-agent-skills/spec.md`

## Summary

Expose the existing Deep Scavenger control plane as a focused, runtime-backed
agent skill surface rather than rebuilding intelligence logic inside prompts.
Keep `/Users/lixun/.openclaw/skills/deep-scavenger/`,
`/Users/lixun/.openclaw/skills/x-scavenger/`, and
`/Users/lixun/.openclaw/skills/clawfeed/` as the source of truth; add a thin
read-only tool layer plus three operator-facing skills:
`intel-duty-officer`, `source-health-triage`, and `briefing-analyst`.

## Technical Context

**Language/Version**: Python 3.10+ and Node.js 22+ in the shipped runtime;
skill wrappers may be Markdown workflow definitions plus Python/Node helper
scripts as needed  
**Primary Dependencies**: existing `/api/health`, `/api/ops_overview`,
`/api/briefing`, `/api/deep_briefings`, watchdog status files, runtime scoring
and briefing outputs, skill host contracts under `/Users/lixun/Documents/codex /.agents/skills/`  
**Storage**: Existing SQLite, JSON, and runtime sidecar files remain
authoritative; no new database or prompt-only source of truth  
**Testing**: Spec-level contract docs plus fixture-backed runtime tests, skill
contract tests, and live endpoint validation against the local control plane  
**Target Platform**: macOS operator workstation running the local Deep
Scavenger / ClawFeed stack and local skill host  
**Project Type**: Cross-workspace operator tooling with runtime/API and
skill-surface integration  
**Performance Goals**: Duty-officer summary under 5 seconds on a healthy local
runtime; source triage under 10 seconds for one target; briefing analysis under
10 seconds when a latest briefing snapshot is available  
**Constraints**: Runtime remains authoritative; skills are read-only by
default; no direct SQL from skills; explicit contract versioning; partial-data
and stale-data behavior must be observable; no branch or worktree manipulation
required to consume this plan  
**Scale/Scope**: Three first-party skills, one shared output envelope, one
shared tool-contract layer, and future compatibility with a manager agent that
delegates but does not bypass skill boundaries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Real Software Over Reimplementation**: PASS. The plan uses the shipped
  control plane and runtime outputs instead of recreating health, scoring, or
  briefing truth inside prompts.
- **II. Subproject Boundary First**: PASS. The plan explicitly splits work
  between the spec repo skill surface and the operational runtime under
  `/Users/lixun/.openclaw/skills/`.
- **III. Spec-and-Test Gated Delivery**: PASS. The feature is defined by spec,
  plan, contracts, tasks, and explicit validation paths before implementation.
- **IV. CLI and Machine-Readable Contracts**: PASS. The design centers on
  versioned tool contracts and a structured skill output envelope.
- **V. Minimal Context, Maximum Traceability**: PASS. The feature limits itself
  to three skills and the minimum runtime surfaces needed to support them.

**Post-Design Re-check**: PASS. Research, contracts, data model, and quickstart
all preserve runtime authority and read-only boundaries without introducing new
constitution violations.

## Project Structure

### Documentation (this feature)

```text
/Users/lixun/Documents/codex /specs/002-intel-agent-skills/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── checklists/
│   └── requirements.md
└── contracts/
    ├── intel-skill-tool-contracts.md
    └── skill-output-envelope.schema.json
```

### Source Code (planned implementation targets)

```text
/Users/lixun/Documents/codex /.agents/skills/
├── intel-duty-officer/
│   └── SKILL.md
├── source-health-triage/
│   └── SKILL.md
└── briefing-analyst/
    └── SKILL.md

/Users/lixun/.openclaw/skills/clawfeed/
├── src/server.mjs
└── test/

/Users/lixun/.openclaw/skills/deep-scavenger/
├── scripts/
└── data/

/Users/lixun/.openclaw/skills/x-scavenger/
└── scripts/
```

**Structure Decision**: Keep skills versioned in the spec repository under
`.agents/skills/`, while runtime truth and any minimal new read-only API
surfaces stay in the operational workspaces.

## Phase 0: Research & Decisions

- Runtime-backed tools are preferred over direct database or filesystem access
  from skills.
- Existing control-plane HTTP surfaces should be reused first; only missing
  read-only fields justify new API work.
- A single shared skill output envelope reduces prompt drift and makes manager
  delegation easier later.
- Read-only and mutation flows must be split at the contract level, not only in
  prompt wording.
- Fixture-backed degraded-state testing is required because healthy-live-only
  testing will not cover stale, partial, or conflicting states.

See: [/Users/lixun/Documents/codex /specs/002-intel-agent-skills/research.md](/Users/lixun/Documents/codex /specs/002-intel-agent-skills/research.md)

## Phase 1: Design & Contracts

- Data model defines skill invocation, tool contract, ops snapshot, source
  health snapshot, briefing snapshot, evidence matrix, and output envelope.
- Contracts define the shared skill output schema and the minimum read-only tool
  surfaces needed to back the three skills.
- Quickstart validates the stack at three levels: runtime health, tool contract
  behavior, and skill-level output behavior.

Artifacts:
- [/Users/lixun/Documents/codex /specs/002-intel-agent-skills/data-model.md](/Users/lixun/Documents/codex /specs/002-intel-agent-skills/data-model.md)
- [/Users/lixun/Documents/codex /specs/002-intel-agent-skills/contracts/intel-skill-tool-contracts.md](/Users/lixun/Documents/codex /specs/002-intel-agent-skills/contracts/intel-skill-tool-contracts.md)
- [/Users/lixun/Documents/codex /specs/002-intel-agent-skills/contracts/skill-output-envelope.schema.json](/Users/lixun/Documents/codex /specs/002-intel-agent-skills/contracts/skill-output-envelope.schema.json)
- [/Users/lixun/Documents/codex /specs/002-intel-agent-skills/quickstart.md](/Users/lixun/Documents/codex /specs/002-intel-agent-skills/quickstart.md)

## Implementation Strategy

1. **Stabilize read-only tool surfaces first**: Back each skill with a named
   contract over existing runtime endpoints before writing skill prompts or
   wrappers.
2. **Ship the duty-officer path first**: This is the MVP because it proves the
   system can summarize current reality from runtime truth.
3. **Add bounded triage second**: Source-health triage depends on the same
   control plane but adds diagnosis logic and degraded-state coverage.
4. **Add briefing analysis third**: This depends on the current analyst
   protocol and evidence-matrix surfaces already shipped into the control plane.
5. **Preserve manager compatibility without building the manager**: Keep skill
   outputs and contracts narrow enough that a future orchestrator can compose
   them safely.

## Complexity Tracking

No constitution violations currently require formal exceptions.

## Follow-up Architecture Plan

This feature deliberately stops at the first skill layer. Future work may add:

- a manager or handoff agent
- explicit mutation tools for remediation
- richer cross-skill delegation rules

Those are intentionally out of scope until the read-only skill contracts are
stable.
