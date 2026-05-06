# Repo-local LiteLLM Tasks

This directory stores repo-local task and flow definitions for the `cli` command.

Tracked files:
- `tasks/*.yaml` starter workflows

Ignored local runtime files:
- `config.json`
- `local.env`
- `session.json`

Typical usage:

```bash
cli config bootstrap --workspace .
cli task run .litellm/tasks/repair.yaml --workspace .
cli task run .litellm/tasks/flow-hardening.yaml --workspace .
```
