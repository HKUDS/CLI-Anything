# SeaClip-Lite - Standard Operating Procedure

## Overview

SeaClip-Lite is a lightweight project management board built on FastAPI + SQLite.
It provides issue tracking, a 6-agent CI/CD pipeline, GitHub issue scheduling,
and an activity feed. This CLI harness provides programmatic control over
SeaClip-Lite via its HTTP API and direct SQLite reads.

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API server | FastAPI | Issue CRUD, pipeline control, scheduler sync |
| Database | SQLite | Persistent storage for issues, agents, schedules, activity |
| CLI transport | HTTP (`requests`) | JSON API calls for issues, pipeline, health |
| CLI transport | SQLite (read-only) | Direct DB reads for agents, schedules, activity |

The CLI is a thin Click application that delegates to `SeaClipBackend`, which
routes each call to either the FastAPI JSON endpoints or the SQLite database.
Some FastAPI endpoints return HTMX partials instead of JSON, so those are
served by direct SQLite queries instead.

## State Model

**Stateless.** The CLI holds no local state between invocations. Every command
reads from the API or database at call time. There is no project file, session,
or undo/redo stack.

## Backend

- **FastAPI** at `http://127.0.0.1:5200`
- **SQLite** at the path specified by the `SEACLIP_DB` environment variable

## Install

```bash
cd agent-harness
pip install -e .
```

## Usage

### One-shot commands

```bash
# Health check
cli-anything-seaclip --json server health

# Issue management
cli-anything-seaclip --json issue list
cli-anything-seaclip --json issue list --status backlog --priority high
cli-anything-seaclip --json issue create --title "Fix login bug" --priority high
cli-anything-seaclip --json issue move ISSUE_UUID --column done
cli-anything-seaclip --json issue status ISSUE_UUID --set in_progress
cli-anything-seaclip --json issue delete ISSUE_UUID

# Agent roster
cli-anything-seaclip --json agent list

# Pipeline control
cli-anything-seaclip --json pipeline start --issue UUID --mode auto
cli-anything-seaclip --json pipeline status --issue UUID
cli-anything-seaclip --json pipeline resume --issue UUID
cli-anything-seaclip --json pipeline stop --issue UUID

# Scheduler
cli-anything-seaclip --json scheduler list
cli-anything-seaclip --json scheduler add --name "nightly" --cron "0 2 * * *" --repo https://github.com/org/repo
cli-anything-seaclip --json scheduler sync SCHEDULE_ID

# Activity feed
cli-anything-seaclip --json activity list --limit 20
```

### Interactive REPL

```bash
cli-anything-seaclip
# Type help for commands, quit to exit
```

## Command Groups

| Group | Commands | Transport |
|-----------|--------------------------------|-----------|
| `issue` | list, create, move, status, delete | HTTP API |
| `agent` | list | SQLite |
| `pipeline` | start, status, resume, stop | HTTP API |
| `scheduler` | list, add, sync | SQLite (list), HTTP API (add, sync) |
| `activity` | list | SQLite |
| `server` | health | HTTP API |

## Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend health check |
| GET | `/api/issues` | List issues (query params: status, priority, search, limit) |
| POST | `/api/issues` | Create issue (JSON body: title, description, priority) |
| POST | `/api/issues/{id}/move` | Move issue to column |
| POST | `/api/issues/{id}/status` | Update issue status |
| DELETE | `/api/issues/{id}` | Delete issue |
| POST | `/api/pipeline/{id}/start` | Start pipeline |
| GET | `/api/pipeline/{id}/status` | Pipeline status |
| POST | `/api/pipeline/{id}/resume` | Resume pipeline |
| POST | `/api/pipeline/{id}/stop` | Stop pipeline |
| POST | `/api/scheduler/add` | Add schedule |
| POST | `/api/scheduler/{id}/sync` | Trigger sync |

## SQLite Tables (read-only access)

| Table | Columns used by CLI |
|-------|-------------------|
| `agents` | name, role, status, current_issue_id, last_completed_at, last_error, updated_at |
| `schedule_configs` | id, repo, enabled, interval_minutes, target_column, auto_pipeline, pipeline_mode, ai_mode, last_synced_at, issues_synced |
| `activity_log` | event_type, summary, created_at |

## Testing

```bash
cd agent-harness
pip install -e .
python -m pytest cli_anything/seaclip/tests/ -v
```

Unit tests run without a live backend (all HTTP/SQLite calls are mocked).
E2E tests require the SeaClip-Lite server running at localhost:5200.
