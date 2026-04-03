# Research: Intel Agent Skills Control Plane

## Decision 1: Keep runtime truth in the shipped control plane

**Decision**: Skills will consume runtime-backed APIs and tool contracts rather
than direct SQLite access or prompt-maintained state.

**Rationale**: The current system already has authoritative control-plane
surfaces for health, ops overview, scoring backlog, briefing protocol, harness,
and local AI control-plane state. Re-deriving that truth inside prompts would
increase drift and make failure diagnosis weaker.

**Alternatives considered**:

- Direct database reads from skills: rejected because it couples skills to
  internal storage and bypasses existing runtime semantics.
- Prompt-only summaries: rejected because they are not authoritative or
  testable.

## Decision 2: Add a thin read-only tool layer before building any manager agent

**Decision**: The first delivery is a set of focused read-only skills backed by
  named tool contracts, not a general manager agent.

**Rationale**: Manager orchestration adds complexity before the boundaries are
  proven. Focused skills are easier to validate independently and map directly
  to existing operator workflows.

**Alternatives considered**:

- One large "deep-scavenger" skill: rejected because it mixes unrelated duties
  and weakens permission boundaries.
- Manager-first design: rejected because it creates orchestration before the
  underlying contracts are stable.

## Decision 3: Reuse existing HTTP control-plane surfaces first

**Decision**: Prefer existing `/api/health`, `/api/ops_overview`, `/api/briefing`,
`/api/deep_briefings`, and existing watchdog/runtime outputs. Add new runtime
  surfaces only when required fields are missing.

**Rationale**: This minimizes new runtime work and keeps the skill surface
  aligned with already shipped operator views.

**Alternatives considered**:

- Introduce a new parallel MCP server first: deferred until existing surfaces
  prove insufficient.
- Require every skill to compose raw files directly: rejected because it hides
  provenance and makes partial-state behavior inconsistent.

## Decision 4: Use one shared output envelope across all three skills

**Decision**: `intel-duty-officer`, `source-health-triage`, and
`briefing-analyst` will return the same top-level output shape with structured
status, findings, evidence, confidence, and next actions.

**Rationale**: This reduces downstream complexity for humans and future manager
  agents, and makes contract testing easier.

**Alternatives considered**:

- Free-form Markdown only: rejected because it is weak for contract testing and
  manager composition.
- Per-skill custom payload shapes: rejected because it creates avoidable
  routing and parsing drift.

## Decision 5: Read-only by default, mutation later

**Decision**: This feature exposes only read-only skill behavior. Any future
  actions that restart services, clear backlog, or change source state must use
  separate explicit mutation contracts.

**Rationale**: The user need today is reliable understanding, not autonomous
  remediation. Mixing them in the first cut raises risk without improving the
  quality of operator judgment.

**Alternatives considered**:

- Build restart/remediation into triage immediately: rejected because it
  conflates diagnosis with action authorization.

## Decision 6: Test degraded and partial states explicitly

**Decision**: Validation must cover healthy, stale, partial, conflicting, and
  no-briefing states.

**Rationale**: These skills exist to help operators under imperfect conditions.
  A healthy-only validation plan would miss the cases that matter most.

**Alternatives considered**:

- Live-health-only smoke tests: rejected because they do not exercise the main
  diagnostic value of the feature.
