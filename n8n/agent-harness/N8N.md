# N8N.md — Architecture

## Overview

`cli-anything-n8n` wraps the n8n Public API v1.1.1 into a Click-based CLI, following the CLI-Anything harness pattern by HKUDS. Only verified endpoints from the OpenAPI spec are exposed.

## n8n Compatibility

- **Minimum version**: n8n >= 1.0.0
- **API version**: Public API v1.1.1
- **Verified against**: n8n 2.43.0
- **OpenAPI spec**: fetched from `/api/v1/openapi.yml`

## Architecture

```
cli_anything/n8n/
├── n8n_cli.py              # Click CLI (groups, commands, REPL, error handling)
├── core/                   # Business logic (thin wrappers over backend)
│   ├── workflows.py        # 9 endpoints (CRUD, activate, tags, transfer)
│   ├── executions.py       # 4 endpoints (list, get, delete, retry)
│   ├── credentials.py      # 4 endpoints (create, delete, schema, transfer)
│   ├── variables.py        # 4 endpoints (CRUD)
│   ├── tags.py             # 5 endpoints (CRUD)
│   └── project.py          # Config load/save
├── utils/
│   ├── n8n_backend.py      # HTTP client (sole module making requests)
│   └── repl_skin.py        # Banner, colors, table formatting
├── skills/
│   └── SKILL.md            # AI agent discovery
└── tests/
    ├── test_core.py        # Unit tests (mocked)
    └── test_full_e2e.py    # E2E tests (live n8n)
```

## Data Flow

```
User/Agent -> n8n_cli.py (Click) -> core/*.py -> n8n_backend.py -> n8n REST API
```

## Authentication

Header-based: `X-N8N-API-KEY: <key>`

Resolution order: CLI `--api-key` > env `N8N_API_KEY` > config file

## What's NOT in the Public API

These n8n features are NOT available through the public REST API v1.1.1:
- **Data Tables**: no endpoints at all
- **Credential listing/updating**: only create, delete, schema, transfer
- **Execution stop**: only list, get, delete, retry
- **Workflow execute**: not in public API (use internal API or n8n UI)
- **Audit logs**: POST-only, not exposed in CLI

## Conventions

- All core functions accept `base_url` and `api_key` as keyword args
- All commands support `--json` for parseable output
- PEP 420 namespace: `cli_anything/` has NO `__init__.py`
- Entry point: `cli-anything-n8n` -> `cli_anything.n8n.n8n_cli:main`
- Timeout configurable via `N8N_TIMEOUT` env var (default: 30s)
