# Dify Workflow Harness Architecture

## Overview

This harness adds `cli-anything-dify-workflow`, a CLI-Anything wrapper around the
existing `dify-workflow` CLI from the open-source
`dify-ai-workflow-tools` project.

The upstream CLI already provides the real workflow authoring engine for Dify DSL
files. This harness focuses on:

- CLI-Anything packaging under the shared `cli_anything` namespace
- AI-discoverable `SKILL.md`
- unified REPL skin
- registry integration for CLI-Hub
- tests that verify wrapper discovery and forwarding behavior

## Interaction Model

```text
AI Agent
  -> cli-anything-dify-workflow
     -> installed dify-workflow CLI / dify_workflow Python package
        -> local Dify YAML/JSON DSL files
```

## Why a Wrapper Harness

The upstream project is already a mature CLI and does not need to be rewritten
inside CLI-Anything. Following existing wrapper patterns in this repository,
this harness exposes the upstream CLI through a CLI-Anything package so agents
can discover it from CLI-Hub and load its skill metadata.

## Requirements

- Python 3.10+
- Upstream Dify workflow CLI installed separately:
  - recommended: install from GitHub
  - optional: install from PyPI if published later

## Command Surface

The wrapper exposes the upstream command groups:

- `guide`
- `list-node-types`
- `create`
- `inspect`
- `validate`
- `checklist`
- `edit <subcommand>`
- `config <subcommand>`
- `export`
- `import`
- `diff`
- `layout`

## Testing Strategy

- `test_core.py`: backend discovery, command building, wrapper metadata
- `test_full_e2e.py`: wrapper subprocess smoke tests and workflow lifecycle
  forwarding when the upstream CLI is installed
