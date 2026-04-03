# Tasks: Intel Agent Skills Control Plane

**Input**: Design documents from `/Users/lixun/Documents/codex /specs/002-intel-agent-skills/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are required for this feature because the constitution demands
spec-and-test gated delivery and the feature adds a new agent-facing contract
surface over live operational tooling.

**Organization**: Tasks are grouped by user story so each skill can be
implemented and validated independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Lock the cross-workspace scope, file locations, and shared contract
surfaces before building any skill.

- [ ] T001 Confirm target implementation paths under `/Users/lixun/Documents/codex /.agents/skills/`, `/Users/lixun/.openclaw/skills/deep-scavenger/`, and `/Users/lixun/.openclaw/skills/clawfeed/`
- [ ] T002 [P] Add or refresh shared skill contract fixtures under `/Users/lixun/.openclaw/skills/deep-scavenger/scripts/` and `/Users/lixun/.openclaw/skills/clawfeed/test/`
- [ ] T003 [P] Add or update operator-facing validation notes in `/Users/lixun/Documents/codex /specs/002-intel-agent-skills/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared read-only tool layer and output envelope used
by all three skills.

**⚠️ CRITICAL**: No user story work should be considered complete until this
phase is done.

- [ ] T004 [P] Add contract coverage for the shared output envelope against `/Users/lixun/Documents/codex /specs/002-intel-agent-skills/contracts/skill-output-envelope.schema.json`
- [ ] T005 [P] Add route or helper coverage for required runtime-backed tool surfaces in `/Users/lixun/.openclaw/skills/clawfeed/test/source-health-route.test.mjs`
- [ ] T006 Implement or tighten shared read-only tool helpers over `/api/health`, `/api/ops_overview`, and briefing routes in `/Users/lixun/.openclaw/skills/clawfeed/src/server.mjs`
- [ ] T007 Implement shared skill output normalization helpers in the chosen skill host layer under `/Users/lixun/Documents/codex /.agents/skills/`
- [ ] T008 Expose or normalize bounded source-health inputs needed by triage in `/Users/lixun/.openclaw/skills/deep-scavenger/scripts/`

**Checkpoint**: Shared tool contracts and output envelope are stable.

---

## Phase 3: User Story 1 - Duty Officer Snapshot (Priority: P1) 🎯 MVP

**Goal**: Provide one runtime-grounded operator summary from the current control
plane.

**Independent Test**: Invoke only `intel-duty-officer` against healthy and
degraded fixture/live states and verify that it returns a valid structured
summary without mutation.

### Tests for User Story 1

- [ ] T009 [P] [US1] Add contract tests for duty-officer output shape under `/Users/lixun/Documents/codex /.agents/skills/intel-duty-officer/`
- [ ] T010 [P] [US1] Add fixture-backed degraded-state tests for ops/health summary composition in `/Users/lixun/.openclaw/skills/deep-scavenger/scripts/`

### Implementation for User Story 1

- [ ] T011 [US1] Create `/Users/lixun/Documents/codex /.agents/skills/intel-duty-officer/SKILL.md`
- [ ] T012 [US1] Implement duty-officer helper or adapter code in the chosen skill host layer
- [ ] T013 [US1] Map duty-officer evidence citations to runtime snapshots from `/api/health` and `/api/ops_overview`
- [ ] T014 [US1] Validate duty-officer against the quickstart scenarios in `/Users/lixun/Documents/codex /specs/002-intel-agent-skills/quickstart.md`

**Checkpoint**: One operator-facing skill can summarize live system state from runtime truth.

---

## Phase 4: User Story 2 - Source Health Triage (Priority: P2)

**Goal**: Diagnose stale or degraded source state with bounded, evidence-backed explanations.

**Independent Test**: Invoke only `source-health-triage` against source
freshness failures, scoring backlog, harness degradation, and watchdog staleness
fixtures and verify that it distinguishes those classes.

### Tests for User Story 2

- [ ] T015 [P] [US2] Add triage-classification coverage for source freshness, scoring backlog, harness, and watchdog states
- [ ] T016 [P] [US2] Add bounded-target contract tests for source key/lane/pipeline invocation inputs

### Implementation for User Story 2

- [ ] T017 [US2] Create `/Users/lixun/Documents/codex /.agents/skills/source-health-triage/SKILL.md`
- [ ] T018 [US2] Implement bounded source-health snapshot resolution over runtime tool surfaces
- [ ] T019 [US2] Implement triage reasoning that preserves uncertainty and competing explanations when evidence conflicts
- [ ] T020 [US2] Validate source-health-triage against quickstart degraded-state scenarios

**Checkpoint**: Operators can move from a red state to a bounded diagnosis without raw log digging.

---

## Phase 5: User Story 3 - Briefing Evidence Review (Priority: P3)

**Goal**: Explain the latest briefing verdict, confidence, action bias, and evidence matrix in a stable operator-facing contract.

**Independent Test**: Invoke only `briefing-analyst` against protocol,
legacy-only, and no-briefing states and verify that it never fabricates missing
protocol data.

### Tests for User Story 3

- [ ] T021 [P] [US3] Add briefing snapshot contract tests for protocol, legacy, and empty states
- [ ] T022 [P] [US3] Add evidence-matrix interpretation tests covering support and conflict scenarios

### Implementation for User Story 3

- [ ] T023 [US3] Create `/Users/lixun/Documents/codex /.agents/skills/briefing-analyst/SKILL.md`
- [ ] T024 [US3] Implement briefing-analysis helpers over latest briefing and briefing protocol surfaces
- [ ] T025 [US3] Preserve evidence citations and explicit confidence/action-bias reasoning in the skill output envelope
- [ ] T026 [US3] Validate briefing-analyst against quickstart scenarios and latest live briefing availability

**Checkpoint**: Operators can inspect briefing judgment without opening raw traces.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation sync, and forward-compatible boundaries.

- [ ] T027 [P] Run end-to-end quickstart validation and record evidence in `/Users/lixun/Documents/codex /specs/002-intel-agent-skills/quickstart.md`
- [ ] T028 [P] Sync skill-surface documentation into `/Users/lixun/Documents/codex /AGENTS.md` and `/Users/lixun/Documents/codex /CLAUDE.md` if operator behavior changes
- [ ] T029 Verify that all three skills remain read-only and do not bypass runtime authority with direct SQL or uncontrolled file reads

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion and should
  build on the shared tool layer
- **User Story 3 (Phase 5)**: Depends on Foundational completion and the
  currently shipped briefing protocol surfaces
- **Polish (Phase 6)**: Depends on the desired user stories being complete

### User Story Dependencies

- **US1** is the MVP and proves the skill layer can summarize runtime truth.
- **US2** depends on the shared tool layer but is independently testable as a
  bounded diagnosis path.
- **US3** depends on the shared tool layer and existing briefing protocol
  surfaces but remains independently testable.

### Parallel Opportunities

- Setup tasks marked `[P]` can run together.
- Foundational contract tasks marked `[P]` can run together.
- Within each user story, fixture and contract tasks marked `[P]` can run in
  parallel before implementation.

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational
3. Complete User Story 1
4. Validate duty-officer independently
5. Stop and review before adding diagnosis and briefing analysis

### Incremental Delivery

1. Ship shared contracts and duty-officer
2. Add source-health triage
3. Add briefing analysis
4. Finish with docs and read-only boundary verification
