---
name: "cli-anything-litellm"
description: >-
  Agent execution CLI for LiteLLM proxy-backed app and workflow editing.
  Runs repo-local YAML tasks and flows, generates patches, applies edits,
  and verifies results through iterative loops.
---

# cli

Use this CLI when the target work is codebase or workflow mutation driven by your
configured LiteLLM model aliases, especially for agent execution engines, flows, and loops.

## Installation

```bash
pip install cli-anything-litellm
```

## Recommended usage

```bash
cli --json health
cli models list
cli task run .litellm/tasks/fix-loop.yaml --workspace .
cli patch show
```

## For AI agents

- Prefer `--json` for structured automation.
- Store reusable definitions as repo-local YAML files.
- Use `health` and `models list` before the first task if connectivity is uncertain.
- `patch show` returns the last unified diff.
- `patch export` writes both diff and action JSON artifacts.
- Defaults auto-apply patches inside the workspace and runs verification after each iteration.
- This branch defaults the proxy to `https://litellm.nuriy.com/v1` and the model to `gpt-5.4`.
