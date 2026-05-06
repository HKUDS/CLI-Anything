# cli

Agent execution CLI for LiteLLM proxy-backed app and workflow editing.

## Install

```bash
pip install cli-anything-litellm
```

## Core workflows

```bash
cli health
cli models list
cli config bootstrap --workspace .
cli task run .litellm/tasks/repair.yaml --workspace .
cli patch show
cli patch rollback
```

## Notes

- Reuses an existing LiteLLM proxy.
- Defaults to `https://litellm.nuriy.com/v1` and model alias `gpt-5.4`.
- `config bootstrap` writes repo-local `.litellm/config.json` and a safe `.litellm/.gitignore`.
- Expects tasks and flows as repo-local YAML files.
- Produces both unified diff and action JSON for each patch loop.
- Defaults to app/workflow editing with auto-apply, repo-scoped safety, and verification after each patch.
