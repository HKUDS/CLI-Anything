# Intel Skill Tool Contracts

## Scope

This document defines the minimum read-only runtime-backed surfaces required to
support the first three Deep Scavenger agent skills.

## Shared Contract Rules

- All tools are read-only in this feature.
- All tools must expose a versionable contract, even if implemented on top of an
  existing HTTP route.
- Concrete tool descriptors live in `agent_skills/intel_tool_registry.json`.
- The registry schema lives in
  `specs/002-intel-agent-skills/contracts/intel-tool-registry.schema.json`.
- All skill conclusions must cite one or more tool outputs.
- Missing required tools must produce explicit contract failure, not silent
  fallback to prompt-only reasoning.

## Concrete Tool Registry

The current implementation exposes three raw read-only tools:

- `intel-health`
- `intel-ops-overview`
- `intel-briefing`

These concrete tool names are the runtime-facing truth. The abstract `get_*`
names below remain useful as design aliases, but agents and registries should
bind to the concrete `intel-*` descriptors.

The current MCP-facing wrapper is:

- `scripts/intel_mcp_server.py`
- Local plugin entry: `deep-scavenger-intel-plugin/.claude-plugin/plugin.json`

It currently exposes `initialize`, `prompts/list`, `prompts/get`,
`resources/list`, `resources/read`, `tools/list`, `tools/call`, and `ping`
over stdio JSON-RPC for the three concrete read-only tools above.

The current MCP resources are intentionally narrow:

- tool registry JSON
- skill/tool contract markdown
- quickstart markdown
- plugin README
- the three operator skill instruction files

The current MCP prompts mirror the three operator workflows:

- `intel-duty-officer`
- `source-health-triage`
- `briefing-analyst`

## Required Tool Surfaces

### `get_ops_overview`

**Concrete tool**: `intel-ops-overview`

**Purpose**: Return the current operator control-plane overview.

**Preferred backing surface**: `/api/ops_overview`

**Required fields**:
- `summary`
- `alerts`
- `scoring_pipeline`
- `harness_overview`
- `latest_briefing`
- `control_plane_alerts`

**Used by**:
- `intel-duty-officer`
- `source-health-triage`
- `briefing-analyst`

### `get_health_snapshot`

**Concrete tool**: `intel-health`

**Purpose**: Return machine-readable runtime health.

**Preferred backing surface**: `/api/health`

**Required fields**:
- `status`
- `source_health`
- `local_ai_control_plane`
- `scoring_pipeline`
- `control_plane_alerts`

**Used by**:
- `intel-duty-officer`
- `source-health-triage`

### `get_source_health`

**Purpose**: Return a bounded health snapshot for one source, lane, or pipeline
target.

**Implementation note**: There is no standalone raw runtime tool for this
surface in the current feature. It is a bounded derived view synthesized by
`source-health-triage` from `intel-health`, `intel-ops-overview`, and source-run
metadata already exposed through those surfaces.

**Required fields**:
- `source_key`
- `state`
- `last_success_at`
- `latest_run`
- `stale_age_minutes`
- `related_backlog`
- `related_lock_state`

**Used by**:
- `source-health-triage`

### `get_latest_briefing`

**Concrete tool**: `intel-briefing`

**Purpose**: Return the latest available briefing, including protocol sidecar
when present.

**Preferred backing surface**: `/api/briefing` or `/api/deep_briefings`

**Required fields**:
- `date`
- `protocol_available`
- `briefing_protocol`
- `final_claims`
- `trace_generated_at`

**Used by**:
- `intel-duty-officer`
- `briefing-analyst`

### `get_briefing_snapshot`

**Concrete tool**: `intel-briefing`

**Purpose**: Return a briefing snapshot for a requested date or latest date.

**Preferred backing surface**: `/api/deep_briefings` detail view or latest
briefing route

**Required fields**:
- Same as `get_latest_briefing`
- Optional target date support

**Used by**:
- `briefing-analyst`

## Skill-to-Tool Mapping

### `intel-duty-officer`

**Required tools**:
- `intel-ops-overview`
- `intel-health`

**Optional tools**:
- `intel-briefing`

### `source-health-triage`

**Required tools**:
- `intel-health`

**Optional tools**:
- `intel-ops-overview`

### `briefing-analyst`

**Required tools**:
- `intel-briefing`

**Optional tools**:
- `intel-ops-overview`

## Output Contract

All skills must emit the shared output envelope defined in
`specs/002-intel-agent-skills/contracts/skill-output-envelope.schema.json`.
