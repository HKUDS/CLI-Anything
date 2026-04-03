# Deep Scavenger Intel Tools Plugin

This local plugin packages the Deep Scavenger intel MCP wrapper for agent and
client discovery.

## Exposed MCP Tools

- `intel-health`
- `intel-ops-overview`
- `intel-briefing`

## Exposed MCP Prompts

- `intel-duty-officer`
- `source-health-triage`
- `briefing-analyst`

## Exposed MCP Resources

- `dsintel://registry/tools`
- `dsintel://contracts/intel-skill-tool-contracts`
- `dsintel://contracts/quickstart`
- `dsintel://docs/plugin-readme`
- `dsintel://skills/intel-duty-officer`
- `dsintel://skills/source-health-triage`
- `dsintel://skills/briefing-analyst`

## Transport

- `stdio`

## Entrypoint

```bash
./bin/run-intel-mcp.sh
```

The wrapper resolves the repository root and launches:

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_mcp_server.py
```

## Notes

- This plugin is read-only.
- Runtime truth still comes from `http://127.0.0.1:8767`.
- Tool descriptors remain machine-readable in
  [/Users/lixun/Documents/codex /agent_skills/intel_tool_registry.json](/Users/lixun/Documents/codex /agent_skills/intel_tool_registry.json).

## Local Client Registration

Current live client registration points at the wrapper from:

- Claude: `/Users/lixun/.claude.json` → `mcpServers.deep-scavenger-intel-tools`
- Codex: `/Users/lixun/.codex/config.toml` → `[mcp_servers.deep-scavenger-intel-tools]`

To install or repair both client registrations:

```bash
python3 /Users/lixun/Documents/codex /scripts/install_intel_mcp_clients.py --pretty
```

For one-command local bootstrap:

```bash
sh /Users/lixun/Documents/codex /scripts/bootstrap_intel_mcp_plugin.sh
```

To check client registration state without writing:

```bash
python3 /Users/lixun/Documents/codex /scripts/install_intel_mcp_clients.py --pretty --check
```

To verify wrapper, client config, MCP handshake, live prompt retrieval, and
live tool calls in one pass:

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_mcp_doctor.py --pretty
```

Use strict mode when you want a non-zero exit code on broken install state:

```bash
python3 /Users/lixun/Documents/codex /scripts/intel_mcp_doctor.py --pretty --strict
```

If the client was already open before registration, restart it so it reloads the
updated MCP config.

For one-command verification of the local MCP stack:

```bash
sh /Users/lixun/Documents/codex /scripts/test_intel_mcp_stack.sh
```

For an optional repo-local `pre-push` hook that runs the same gate:

```bash
sh /Users/lixun/Documents/codex /scripts/install_intel_mcp_pre_push_hook.sh
```

Check whether the hook is installed:

```bash
sh /Users/lixun/Documents/codex /scripts/install_intel_mcp_pre_push_hook.sh --check
```
