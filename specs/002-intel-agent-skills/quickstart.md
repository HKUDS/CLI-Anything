# Quickstart: Intel Agent Skills Control Plane

## Purpose

Validate the future skill surface against the shipped Deep Scavenger runtime
without allowing skills to become a second source of truth.

## Preconditions

- Local ClawFeed API is available on `http://127.0.0.1:8767`
- Deep Scavenger runtime is running
- Local health surfaces are current enough to evaluate source freshness and
  latest briefing state

## Validation Flow

### 1. Confirm runtime truth is healthy enough to test

Run the existing runtime checks:

```bash
python3 /Users/lixun/.openclaw/skills/deep-scavenger/scripts/smoke_test.py
python3 /Users/lixun/.openclaw/skills/deep-scavenger/scripts/deep_scavenger_p0_reliability_test.py
curl -s http://127.0.0.1:8767/api/health | jq '.status, .scoring_pipeline, .local_ai_control_plane'
curl -s http://127.0.0.1:8767/api/ops_overview | jq '.status, .alerts, .latest_briefing'
```

Expected result:
- Runtime health endpoints return structured JSON
- Any degraded state is visible and does not require reading raw logs

### 2. Validate shared tool contracts

Check that the runtime surfaces required by the skill layer are present:

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_tool_runtime.py --list-tools --pretty
python3 /Users/lixun/Documents/codex /scripts/intel_tool_runtime.py --print-registry --pretty
curl -s http://127.0.0.1:8767/api/health > /tmp/intel-skill-health.json
curl -s http://127.0.0.1:8767/api/ops_overview > /tmp/intel-skill-ops.json
curl -s http://127.0.0.1:8767/api/briefing > /tmp/intel-skill-briefing.json
```

Expected result:
- The tool registry reports `intel-health`, `intel-ops-overview`, and
  `intel-briefing` as read-only descriptors.
- `health` includes source freshness and local AI control-plane state
- `ops_overview` includes alerts, scoring pipeline, harness overview, and latest
  briefing summary
- `briefing` or latest briefing detail includes protocol availability
- `intel-health` and `intel-ops-overview` descriptors expose
  `control_plane_alerts.events[*].kind/summary/dedupe_key/recommended_action`

### 2b. Validate MCP wrapper behavior

Run a minimal stdio handshake against the MCP wrapper:

```bash
printf '%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"quickstart","version":"1.0.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | python3 /Users/lixun/Documents/codex /scripts/intel_mcp_server.py
```

Expected result:
- The wrapper negotiates protocol `2025-06-18`
- `tools/list` returns `intel-health`, `intel-ops-overview`, and
  `intel-briefing`
- The wrapper does not expose mutation tools

Check prompt discovery as well:

```bash
printf '%s\n%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"quickstart","version":"1.0.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"prompts/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"prompts/get","params":{"name":"source-health-triage","arguments":{"target":"reddit"}}}' \
  | python3 /Users/lixun/Documents/codex /scripts/intel_mcp_server.py
```

Expected result:
- `prompts/list` returns `intel-duty-officer`, `source-health-triage`, and
  `briefing-analyst`
- `prompts/get` returns a concrete runtime-backed workflow message and validates
  required prompt arguments

Check resource discovery as well:

```bash
printf '%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"quickstart","version":"1.0.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"resources/list","params":{}}' \
  | python3 /Users/lixun/Documents/codex /scripts/intel_mcp_server.py
```

Expected result:
- `resources/list` includes `dsintel://registry/tools`
- `resources/list` includes the contract and skill markdown resources

### 2c. Validate local plugin discovery entry

Check that the local marketplace and plugin manifest include the MCP wrapper:

```bash
python3 - <<'PY'
import json
from pathlib import Path

repo = Path('/Users/lixun/Documents/codex ')
marketplace = json.loads((repo / '.claude-plugin/marketplace.json').read_text())
plugin = json.loads((repo / 'deep-scavenger-intel-plugin/.claude-plugin/plugin.json').read_text())
print([entry['name'] for entry in marketplace['plugins']])
print(plugin['metadata']['mcp'])
PY
```

Expected result:
- Marketplace includes `deep-scavenger-intel-tools`
- Plugin metadata declares `transport=stdio`
- Plugin entrypoint is `./bin/run-intel-mcp.sh`

### 2d. Validate installed client configuration

Install or repair client registration if needed:

```bash
python3 /Users/lixun/Documents/codex /scripts/install_intel_mcp_clients.py --pretty
```

For one-command local bootstrap of client config, repo-local release gate, and
full validation:

```bash
sh /Users/lixun/Documents/codex /scripts/bootstrap_intel_mcp_plugin.sh
```

Check registration state without writing:

```bash
python3 /Users/lixun/Documents/codex /scripts/install_intel_mcp_clients.py --pretty --check
```

Run the local doctor to verify wrapper, Claude config, Codex config, a live MCP
handshake, and real `tools/call` responses in one pass:

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_mcp_doctor.py --pretty
```

Use strict mode when you want a non-zero exit code for missing client
registration or a broken handshake:

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_mcp_doctor.py --pretty --strict
```

Expected result:
- `status` is `ok`
- `checks.wrapper`, `checks.claude`, `checks.codex`, and `checks.handshake` are
  all `true`
- `checks.live_prompts` is `true`
- `checks.live_tools` is `true`
- The handshake reports all three tools and the documented MCP resources
- The live prompt section validates discovery and retrieval of the three
  operator workflow prompts
- The live tool call section validates `intel-health`, `intel-ops-overview`,
  and `intel-briefing` against the runtime contract

For one-command validation of the current MCP stack:

```bash
sh /Users/lixun/Documents/codex /scripts/test_intel_mcp_stack.sh
```

Expected result:
- Core unittest coverage passes for skill runtime, MCP server, doctor, and
  plugin manifest
- The strict doctor returns `status=ok`

For an optional repo-local `pre-push` release gate:

```bash
sh /Users/lixun/Documents/codex /scripts/install_intel_mcp_pre_push_hook.sh
```

Expected result:
- `.git/hooks/pre-push` is installed from the repo-local template
- future pushes run the MCP stack validation before leaving the workstation
- existing custom hooks are not replaced unless `--force` is provided

### 3. Validate skill behavior once implemented

The first implementation should prove the following independent behaviors:

- `intel-duty-officer`
  - returns one operator snapshot from runtime truth
- `source-health-triage`
  - distinguishes stale source, scoring backlog, harness degradation, and
    watchdog staleness
- `briefing-analyst`
  - degrades correctly across protocol, legacy, and empty-briefing states

Expected result:
- All skills emit the shared output envelope
- No skill performs direct SQL or filesystem mutation
- All major conclusions cite runtime evidence

## Failure Interpretation

- If runtime health is broken, do not debug the skill layer first.
- If runtime health is correct but a skill output is malformed, treat that as a
  skill-contract defect.
- If a required field disappears from a runtime payload, treat that as contract
  drift and block the skill from silently degrading.
