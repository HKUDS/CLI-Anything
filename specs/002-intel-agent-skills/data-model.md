# Data Model: Intel Agent Skills Control Plane

## Entities

### Skill Invocation

| Field | Type | Description |
| --- | --- | --- |
| `skill_name` | enum | One of `intel-duty-officer`, `source-health-triage`, `briefing-analyst` |
| `contract_version` | string | Version of the skill/tool contract expected by the caller |
| `mode` | enum | Invocation mode such as `summary`, `triage`, or `analysis` |
| `target` | object/null | Optional bounded target such as source key, lane, or briefing date |
| `read_only` | boolean | Must be `true` for this feature |
| `requested_at` | datetime | Invocation start time |

**Validation rules**:
- `skill_name` is required.
- `read_only` must default to `true`.
- `target` is optional for `intel-duty-officer` and required for bounded triage
  use cases.

### Tool Contract

| Field | Type | Description |
| --- | --- | --- |
| `tool_name` | string | Named runtime-backed tool surface |
| `contract_version` | string | Version string used to detect payload drift |
| `required` | boolean | Whether a skill must have this tool to execute |
| `input_shape` | object | Declared input schema or parameter set |
| `output_shape` | object | Declared result schema or payload contract |

**Relationships**:
- A `Skill Invocation` depends on one or more `Tool Contract` entries.

### Ops Snapshot

| Field | Type | Description |
| --- | --- | --- |
| `status` | enum | Overall control-plane state such as `healthy`, `degraded`, `failed` |
| `pipeline_alerts` | array | Active pipeline or freshness alerts |
| `source_health` | object | Current per-source state summary |
| `scoring_pipeline` | object | Scoring backlog/stall summary |
| `harness_overview` | object/null | Latest harness summary if available |
| `latest_briefing` | object/null | Latest briefing snapshot if available |
| `local_ai_control_plane` | object/null | Gateway/Ollama/watchdog status |
| `snapshot_time` | datetime | When the snapshot was generated |

### Source Health Snapshot

| Field | Type | Description |
| --- | --- | --- |
| `source_key` | string | Logical source identifier |
| `lane` | string/null | Optional lane or sub-lane identifier |
| `state` | enum | `ok`, `stale`, `degraded`, `failed`, or similar |
| `last_success_at` | datetime/null | Most recent successful run timestamp |
| `latest_run` | object/null | Latest relevant source run metadata |
| `stale_age_minutes` | number/null | Derived freshness delay |
| `related_backlog` | object/null | Related scoring or queue pressure |
| `related_lock_state` | object/null | Related run/scoring lock state |

### Briefing Snapshot

| Field | Type | Description |
| --- | --- | --- |
| `date` | string | Briefing date identifier |
| `protocol_available` | boolean | Whether `briefing_protocol` exists |
| `briefing_protocol` | object/null | Structured verdict/evidence object when present |
| `final_claims` | array | Final claims rendered to the operator |
| `trace_generated_at` | datetime/null | Trace generation timestamp |
| `legacy_fields` | object | Legacy fallback briefing fields |

### Evidence Matrix

| Field | Type | Description |
| --- | --- | --- |
| `supporting_source_families` | number | Count of source families supporting the conclusion |
| `conflicting_source_families` | number | Count of source families pushing against the conclusion |
| `supporting_signals` | array | Key supporting evidence items |
| `conflicting_signals` | array | Key conflicting evidence items |
| `effective_confidence` | enum | Confidence after matrix guardrails |
| `effective_action_bias` | enum | Action bias after matrix guardrails |

### Skill Output Envelope

| Field | Type | Description |
| --- | --- | --- |
| `skill_name` | string | Skill that produced the output |
| `contract_version` | string | Output schema version |
| `status` | enum | `ok`, `degraded`, `failed`, `partial` |
| `summary` | string | Short operator-facing headline |
| `findings` | array | Primary findings or diagnosis bullets |
| `evidence` | array | Runtime-grounded evidence items with citations |
| `confidence` | enum | `high`, `medium`, `low`, `unknown` |
| `next_actions` | array | Recommended next actions |
| `errors` | array | Explicit dependency or contract failures |

## Relationships

- `Skill Invocation` → consumes one or more `Tool Contract` outputs.
- `intel-duty-officer` → primarily uses `Ops Snapshot`.
- `source-health-triage` → primarily uses `Source Health Snapshot` plus related
  queue/lock/watchdog evidence.
- `briefing-analyst` → primarily uses `Briefing Snapshot` and `Evidence Matrix`.
- `Skill Output Envelope` is the normalized return shape for all three skills.

## State Considerations

- A skill can be `ok` while one optional dependency is unavailable, as long as
  the missing dependency is reported in `errors` and the result remains usable.
- A skill becomes `partial` when required outputs are present but incomplete or
  stale enough to lower confidence.
- A skill becomes `failed` when a required tool contract is missing or violates
  the declared contract version.
