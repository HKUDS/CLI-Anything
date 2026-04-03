# Feature Specification: Intel Agent Skills Control Plane

**Feature Branch**: `002-intel-agent-skills`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: User description: "Turn the Deep Scavenger intelligence stack into
agent-usable skills without moving system truth into prompts. Keep runtime as
the authority, expose stable tool contracts, and define focused skills for
operator duty, source-health triage, and briefing analysis."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Duty Officer Snapshot (Priority: P1)

As an operator, I want a single skill to read the current control plane and
return the most important system state, top intelligence signals, and next
actions so I can understand what matters now without manually checking `ops`,
`dashboard`, `terminal`, and raw health endpoints.

**Why this priority**: This is the thinnest useful slice. If the system cannot
produce one reliable operator snapshot from runtime truth, higher-order agent
workflows will be built on stale or hallucinated context.

**Independent Test**: Invoke only the duty-officer skill against a live or
fixture-backed runtime and verify that it returns a structured operator summary
grounded in runtime snapshots, with no direct database reads and no mutation.

**Acceptance Scenarios**:

1. **Given** the runtime exposes healthy `/api/ops_overview`,
   `/api/health`, and latest briefing snapshots, **When** the duty-officer
   skill runs, **Then** it returns a structured summary containing current
   system status, top alerts, top source states, and recommended next actions.
2. **Given** one or more control-plane surfaces are degraded or stale,
   **When** the duty-officer skill runs, **Then** it escalates those degradations
   explicitly instead of flattening them into a generic summary.
3. **Given** the latest briefing is unavailable, **When** the duty-officer
   skill runs, **Then** it still returns a valid operator snapshot and marks the
   briefing section as unavailable rather than failing the whole invocation.

---

### User Story 2 - Source Health Triage (Priority: P2)

As an operator, I want a focused triage skill that explains why a source or
pipeline is stale, degraded, or blocked so I can move from "something is red"
to an actionable diagnosis without manually correlating lane freshness, scoring
backlog, locks, harness state, and source-run history.

**Why this priority**: Once the system can summarize status, the next highest
value is diagnosing why status degraded. This keeps the control plane useful
under failure rather than only during healthy periods.

**Independent Test**: Invoke only the source-health-triage skill against
fixture-backed states representing freshness loss, scoring backlog, harness
failure, and stale watchdog data, and verify that the skill returns a bounded
diagnosis with evidence and next steps.

**Acceptance Scenarios**:

1. **Given** a source is marked stale in `/api/health`, **When** the
   source-health-triage skill runs for that source, **Then** it identifies the
   stale condition, includes the latest relevant run metadata, and recommends a
   concrete next step.
2. **Given** the scoring pipeline is blocked by backlog rather than upstream
   capture failure, **When** the triage skill runs, **Then** it distinguishes
   scoring backlog from source freshness failure.
3. **Given** multiple signals disagree about the root cause, **When** the
   triage skill runs, **Then** it reports competing explanations and marks the
   confidence as reduced rather than asserting a single cause as fact.

---

### User Story 3 - Briefing Evidence Review (Priority: P3)

As an operator, I want a briefing-analysis skill that reads the latest analyst
protocol and explains the verdict, confidence, action bias, evidence matrix,
and counter-signals so I can decide whether the current briefing deserves act,
track, or watch treatment.

**Why this priority**: Briefings are the highest-compression intelligence
surface. Once operator status and triage are reliable, the next leverage point
is making briefing judgment transparent and auditable.

**Independent Test**: Invoke only the briefing-analyst skill against a protocol
briefing, a legacy briefing, and a no-briefing state, and verify that it
returns structured reasoning consistent with available evidence without
inventing missing protocol fields.

**Acceptance Scenarios**:

1. **Given** a latest briefing includes `briefing_protocol`, **When** the
   briefing-analyst skill runs, **Then** it returns the protocol verdict,
   confidence, action bias, evidence strength, and counter-signals in a stable
   output envelope.
2. **Given** only a legacy briefing is available, **When** the
   briefing-analyst skill runs, **Then** it marks protocol availability as
   false and falls back to the available briefing fields without fabricating
   missing evidence data.
3. **Given** the evidence matrix shows cross-source conflict, **When** the
   briefing-analyst skill runs, **Then** it reduces conclusion confidence and
   explains the conflict in operator-facing terms.

### Edge Cases

- What happens when `/api/ops_overview` and `/api/health` disagree on a source
  state because one snapshot is fresher than the other?
- How does the system behave when the requested source key, lane, or briefing
  date does not exist?
- What happens when the latest briefing exists but has no `briefing_protocol`
  sidecar?
- How does the system behave when the evidence matrix shows only one source
  family but the model-generated verdict claims high confidence?
- What happens when a skill is invoked in read-only mode but the suggested next
  step would require a mutation tool?
- How does the system handle a stale `watchdog` snapshot while the rest of the
  control plane is healthy?
- What happens when runtime APIs are reachable but return partial payloads that
  omit optional sections such as `latest_briefing` or `harness_overview`?
- How does the system behave when a downstream manager agent attempts to call a
  skill without the required tool contract version?

## Assumptions

- Runtime truth remains in the shipped control plane and operational workspaces:
  `/Users/lixun/.openclaw/skills/deep-scavenger/`,
  `/Users/lixun/.openclaw/skills/x-scavenger/`, and
  `/Users/lixun/.openclaw/skills/clawfeed/`.
- Agent skills are orchestration surfaces, not replacements for the runtime’s
  scoring, analyst, health, or memory logic.
- Default skill operation is read-only. Any future mutation or remediation
  action is explicit, separately authorized, and tool-backed.
- Skills consume stable tool or API contracts, not raw database tables, ad-hoc
  SQL, or prompt-only memory.
- A later manager or handoff layer may orchestrate these skills, but that
  orchestration is out of scope for this feature.

## Non-Goals

- Replacing `deep-scavenger`, `x-scavenger`, or `clawfeed` with prompt-only
  agents.
- Allowing skills to write directly to SQLite, update source state, or mutate
  memory by default.
- Defining a full multi-agent planner or arbitration system in this feature.
- Reworking the current runtime collection, scoring, or briefing pipelines
  beyond the tool contracts required to expose them safely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a stable runtime-backed skill contract for
  `intel-duty-officer`, `source-health-triage`, and `briefing-analyst`.
- **FR-002**: The system MUST keep runtime APIs and tool outputs as the
  authority for system truth; skills MUST NOT treat prompt memory or free-form
  summaries as authoritative state.
- **FR-003**: Each skill MUST be independently invocable and independently
  testable without requiring a higher-level manager agent.
- **FR-004**: Each skill MUST declare the runtime snapshots or tools it depends
  on and MUST fail explicitly when required dependencies are unavailable.
- **FR-005**: `intel-duty-officer` MUST consume control-plane state sufficient
  to summarize current health, top alerts, source freshness, scoring state,
  harness state, and latest briefing availability.
- **FR-006**: `source-health-triage` MUST accept a bounded target such as a
  source key, lane, or pipeline concern and return a diagnosis grounded in
  observable runtime evidence.
- **FR-007**: `briefing-analyst` MUST consume the latest available briefing
  snapshot and, when present, the `briefing_protocol` fields including verdict,
  confidence, action bias, evidence matrix, and counter-signals.
- **FR-008**: Skills MUST return structured output envelopes with deterministic
  sections for status, evidence, confidence, and recommended next action rather
  than only free-form prose.
- **FR-009**: Skills MUST preserve uncertainty explicitly when snapshots are
  partial, conflicting, or stale.
- **FR-010**: Skills MUST surface source citations or snapshot provenance so an
  operator can trace each conclusion back to the runtime surface that produced
  it.
- **FR-011**: Skills MUST default to read-only operation and MUST NOT mutate
  databases, runtime state, or launchd jobs unless a separate explicit mutation
  contract is invoked.
- **FR-012**: The system MUST make it possible to distinguish skill-level
  failure from runtime-level failure in outputs and tests.
- **FR-013**: The system MUST support fixture-backed validation so each skill
  can be tested against healthy, degraded, stale, and partial-data conditions.
- **FR-014**: The duty-officer skill MUST summarize the latest known state even
  when one or more optional surfaces are unavailable, provided the minimum
  required control-plane contract is present.
- **FR-015**: The source-health-triage skill MUST distinguish at least the
  following failure classes when evidence exists: source freshness loss,
  scoring backlog, harness degradation, local AI control-plane degradation, and
  watchdog staleness.
- **FR-016**: The briefing-analyst skill MUST degrade gracefully between
  protocol, legacy, and empty-briefing states without fabricating missing
  fields.
- **FR-017**: The system MUST preserve versionable tool contracts so future
  changes to runtime payload shape do not silently break skills.
- **FR-018**: The feature MUST define handoff boundaries clearly enough that a
  future manager agent can delegate to these skills without requiring direct
  database access or implementation knowledge.

### Key Entities *(include if feature involves data)*

- **Skill Invocation**: One bounded request to a specific skill, including
  requested target, mode, read-only status, and tool contract version.
- **Tool Contract**: The stable input and output shape for a runtime-backed API
  or MCP-style tool that a skill depends on.
- **Ops Snapshot**: A structured view of current system status, alerts, source
  health, harness state, scoring state, and briefing availability.
- **Source Health Snapshot**: A bounded state bundle for one source, lane, or
  pipeline concern, including freshness, last run, failure signals, and related
  backlog or lock indicators.
- **Briefing Snapshot**: The latest available briefing state, including legacy
  briefing fields and optional `briefing_protocol`.
- **Evidence Matrix**: The structured cross-source support and conflict signals
  that constrain briefing confidence and action bias.
- **Skill Output Envelope**: The structured result returned to an operator or
  manager agent, including status, findings, confidence, evidence, and next
  actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can invoke `intel-duty-officer` and receive a
  structured summary of current system state without manually opening more than
  one control-plane surface.
- **SC-002**: In fixture-backed degraded scenarios, `source-health-triage`
  correctly distinguishes source freshness loss from scoring backlog and harness
  degradation without collapsing them into one generic failure class.
- **SC-003**: In protocol-backed briefing scenarios, `briefing-analyst`
  preserves verdict, confidence, action bias, and evidence signals without
  inventing missing data.
- **SC-004**: In no-briefing or legacy-only scenarios, the briefing-analysis
  path returns a valid structured response rather than failing or fabricating a
  protocol.
- **SC-005**: All three skills can be exercised against fixture-backed inputs
  and live runtime snapshots with read-only permissions only.
- **SC-006**: Operators can trace every major conclusion in a skill response
  back to a specific runtime snapshot or tool result.
- **SC-007**: Runtime payload drift causes an explicit contract failure in tests
  or invocation results rather than silent degradation of skill outputs.
