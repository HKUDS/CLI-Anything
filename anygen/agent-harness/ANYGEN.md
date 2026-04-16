# AnyGen: Project-Specific Analysis & SOP

## Architecture Summary

AnyGen is a cloud-based asynchronous content generation platform that produces
professional slides (PPT), documents (DOCX), websites, storybooks, diagrams
(SmartDraw), and data analysis reports via a REST API. Unlike local GUI targets,
AnyGen runs entirely server-side — the CLI submits tasks, polls for completion,
and downloads generated files.

```
┌──────────────────────────────────────────────────┐
│               AnyGen Cloud Service               │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  Slide   │ │  Doc     │ │  SmartDraw       │  │
│  │  Engine  │ │  Engine  │ │  Engine          │  │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│  ┌────┘  ┌─────────┘  ┌─────────────┘            │
│  │  ┌────┴────┐ ┌─────┴─────┐ ┌───────────────┐  │
│  │  │ Website │ │ Storybook │ │ Data Analysis │  │
│  │  │ Engine  │ │ Engine    │ │ Engine        │  │
│  │  └────┬────┘ └─────┬─────┘ └───────┬───────┘  │
│  │       │             │               │          │
│  ┌───────┴─────────────┴───────────────┴───────┐  │
│  │         Task Orchestration Layer             │  │
│  │  Async queue · status tracking · file store  │  │
│  └──────────────────┬──────────────────────────┘  │
│                     │                             │
│  ┌──────────────────┴──────────────────────────┐  │
│  │          REST API  (OpenAPI 3.1)            │  │
│  │  POST /v1/openapi/tasks                     │  │
│  │  GET  /v1/openapi/tasks/:id                 │  │
│  │  POST /v1/openapi/files/upload              │  │
│  │  POST /v1/openapi/tasks/prepare             │  │
│  └──────────────────┬──────────────────────────┘  │
└─────────────────────┼────────────────────────────┘
                      │  HTTPS + Bearer sk-…
         ┌────────────┴─────────────┐
         │  cli-anything-anygen     │
         │  Click CLI + REPL        │
         │  JSON / human output     │
         └──────────────────────────┘
```

## CLI Strategy: HTTP API Client

AnyGen differs from local GUI targets — there is no local software to invoke.
The CLI acts as a structured HTTP client wrapping the AnyGen OpenAPI:

1. **requests** — Python HTTP library for all API calls.
2. **Polling loop** — After task creation the CLI polls `GET /v1/openapi/tasks/:id`
   at a configurable interval (default 3 s, max 20 min) until `completed` or `failed`.
3. **File download** — On completion the CLI downloads the generated file
   (PPTX, DOCX, HTML, SVG, PDF, etc.) to a local path.
4. **File upload** — Reference files can be uploaded via `POST /v1/openapi/files/upload`
   to get a `file_token` for use in task creation.
5. **Prepare (multi-turn)** — `POST /v1/openapi/tasks/prepare` enables multi-turn
   requirement analysis before creating a task.

### Why a CLI Wrapper?

- Agents cannot directly compose multi-step HTTP workflows (auth → upload → prepare → create → poll → download).
- The CLI provides a single `task run` command that orchestrates the full lifecycle.
- Structured `--json` output lets agents parse task IDs, statuses, and file paths.
- The REPL enables interactive exploration of task types and parameters.

## API Details

**Base URL:** `https://www.anygen.io`
**Auth:** Bearer token (`sk-…`) via `Authorization` header.

### Endpoints

| Method | Endpoint                        | Description                                  |
|--------|---------------------------------|----------------------------------------------|
| POST   | `/v1/openapi/tasks`             | Create a new generation task                 |
| GET    | `/v1/openapi/tasks/:id`         | Query task status and metadata               |
| POST   | `/v1/openapi/files/upload`      | Upload a reference file → `file_token`       |
| POST   | `/v1/openapi/tasks/prepare`     | Multi-turn requirement analysis              |

### Create Task Request Body

```json
{
  "auth_token": "Bearer sk-xxx",
  "operation": "slide",
  "prompt": "Create a quarterly business review presentation",
  "language": "en-US",
  "slide_count": 10,
  "template": "business",
  "ratio": "16:9",
  "export_format": "pptx",
  "file_tokens": ["tk_abc123"],
  "files": []
}
```

### Task Status Response

```json
{
  "task_id": "task_xxx",
  "status": "completed",
  "progress": 100,
  "output": {
    "file_url": "https://...",
    "file_name": "presentation.pptx",
    "thumbnail_url": "https://...",
    "task_url": "https://www.anygen.io/task/task_xxx",
    "slide_count": 10,
    "word_count": 2500
  }
}
```

## The Task Format (.anygen-task.json)

The CLI persists task metadata locally for history and replay:

```json
{
  "version": "1.0",
  "task_id": "task_xxx",
  "operation": "slide",
  "prompt": "Create a quarterly business review presentation",
  "status": "completed",
  "created_at": "2026-03-09T12:00:00Z",
  "completed_at": "2026-03-09T12:01:23Z",
  "output": {
    "file_url": "https://...",
    "file_name": "presentation.pptx",
    "task_url": "https://www.anygen.io/task/task_xxx"
  },
  "local_file": "./output/presentation.pptx",
  "metadata": {
    "file_size": 2048576
  }
}
```

## Supported Operation Types

| Operation        | API Value        | Output Format | Downloadable File |
|------------------|------------------|---------------|-------------------|
| Slides / PPT     | `slide`          | PPTX          | Yes               |
| Documents / DOCX | `doc`            | DOCX          | Yes               |
| SmartDraw        | `smart_draw`     | drawio / excalidraw | Yes          |
| General / Chat   | `chat`           | —             | No (task URL)     |
| Storybook        | `storybook`      | —             | No (task URL)     |
| Data Analysis    | `data_analysis`  | —             | No (task URL)     |
| Website          | `website`        | —             | No (task URL)     |

## Command Map: Agent Action → CLI Command

| Agent Action                         | CLI Command                                                       |
|--------------------------------------|-------------------------------------------------------------------|
| Create a slide deck                  | `task create --operation slide --prompt "..." -o task.json`       |
| Create a document                    | `task create --operation doc --prompt "..." -o task.json`         |
| Draw a diagram                       | `task create --operation smart_draw --prompt "..." -o task.json`  |
| Full workflow (create→poll→download) | `task run --operation slide --prompt "..." --output ./`           |
| Check task status                    | `task status <task-id>`                                           |
| Poll until completion                | `task poll <task-id> [--output ./]`                               |
| Download result file                 | `task download <task-id> --output ./`                             |
| Download thumbnail                   | `task thumbnail <task-id> --output ./`                            |
| Upload a reference file              | `file upload <path>`                                              |
| Multi-turn requirement analysis      | `task prepare --message "..." [--save conv.json]`                 |
| Configure API key                    | `config set api_key sk-xxx`                                       |
| View configuration                   | `config get [key]`                                                |
| View task history                    | `session history`                                                 |
| Undo last operation                  | `session undo`                                                    |

## Create Task Parameters

| Parameter      | Short | Description                                        | Required |
|----------------|-------|----------------------------------------------------|----------|
| --operation    | -o    | Operation type (slide/doc/smart_draw/chat/...)     | Yes      |
| --prompt       | -p    | Content description                                | Yes      |
| --language     | -l    | zh-CN / en-US                                      | No       |
| --slide-count  | -c    | Number of PPT pages (slide only)                   | No       |
| --template     | -t    | PPT template (slide only)                          | No       |
| --ratio        | -r    | 16:9 / 4:3 (slide only)                           | No       |
| --export-format| -f    | pptx/image/thumbnail/docx/drawio/excalidraw        | No       |
| --file-token   |       | File token from upload (repeatable)                | No       |
| --style        | -s    | Style preference                                   | No       |

## Authentication

The CLI reads the API key from (in priority order):
1. `--api-key` CLI option
2. `ANYGEN_API_KEY` environment variable
3. `~/.config/anygen/config.json` file

## Rendering Pipeline

For AnyGen CLI, "rendering" is server-side generation. The CLI orchestrates:

### Pipeline Steps:
1. Validate operation type and prompt
2. POST task to AnyGen API with auth header
3. Poll GET /v1/openapi/tasks/:id at 3 s interval (max 20 min)
4. On completion, download file via output `file_url`
5. Save to local path and verify file integrity (size > 0, correct format)

### Rendering Gap Assessment: **Low**
- All rendering happens server-side — the CLI is a thin orchestration layer
- No local filter translation or format conversion needed
- Risk limited to network issues and API availability
- SmartDraw diagrams may require local Chromium rendering (drawio/excalidraw → PNG)

## Test Coverage Plan

1. **Unit tests** (`test_core.py`): Mock HTTP responses, no real API calls
   - Task create/status/poll parameter construction
   - Config loading (API key from env, file, CLI option)
   - Polling logic (timeout, retry, status transitions)
   - JSON output formatting
   - Session undo/redo with task history
   - Error handling (auth failure, rate limit, server error)
   - File upload parameter validation

2. **E2E tests** (`test_full_e2e.py`): Real API calls (require `ANYGEN_API_KEY`)
   - Full workflow: create task → poll → download → verify file
   - slide and doc operations produce downloadable output
   - File format verification (PPTX is valid ZIP, DOCX is valid OOXML)
   - CLI subprocess invocation via `_resolve_cli`
   - Error scenarios (invalid operation, empty prompt, bad API key)
