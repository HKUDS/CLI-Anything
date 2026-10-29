# Cheaper Inference: Project-Specific Analysis & SOP

## Architecture Summary

Cheaper Inference is a hosted, OpenAI-compatible LLM gateway.
One API key gives access to models from several labs.
The CLI talks to its REST API over HTTPS.

```
┌──────────────────────────────────────────────┐
│        cli-anything-cheaperinference         │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐   │
│  │  Chat /  │ │  Models  │ │   Session   │   │
│  │  Stream  │ │   List   │ │   + Config  │   │
│  └────┬─────┘ └────┬─────┘ └─────────────┘   │
└───────┼────────────┼─────────────────────────┘
        │            │   Authorization: Bearer <key>
┌───────┴────────────┴─────────────────────────┐
│   https://api.cheaperinference.com/v1        │
│   /chat/completions        /models           │
└──────────────────────────────────────────────┘
```

## CLI Strategy: REST API Wrapper

The API follows the OpenAI Chat Completions format. The CLI wraps it with:

1. **requests** — HTTP client for all API calls
2. **Server-sent events** — For streamed chat output (`stream`)
3. **Click CLI** — Command groups for chat, session, and config
4. **REPL** — Interactive mode for exploratory use

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | POST | Chat completion (optionally streamed) |
| `/v1/models` | GET | List available models (needs key) |

### Configuration

| Source | Key | Notes |
|--------|-----|-------|
| `--api-key` option | — | Highest priority |
| Environment | `CHEAPER_INFERENCE_API_KEY` | Used when no option is given |
| Config file | `api_key` | `~/.config/cli-anything-cheaperinference/config.json` |
| Config file | `default_model` | Default is `gpt-5.4-mini` |
| Environment | `CHEAPER_INFERENCE_API_BASE` | Overrides `https://api.cheaperinference.com/v1` |

## Command Map

| Command | API call |
|---------|----------|
| `chat --prompt "..."` | `POST /chat/completions` |
| `stream --prompt "..."` | `POST /chat/completions` with `stream: true` |
| `test [--model <id>]` | `POST /chat/completions` with a short prompt |
| `models` | `GET /models` |
| `session status / clear / history` | Local session file only |
| `config set / get / delete / path` | Local config file only |

## Test Coverage Plan

1. **Unit tests** (`test_core.py`): No API key needed
   - API key resolution order
   - Config save and load
   - Request URL, headers, and body (mocked HTTP)
   - Error handling paths
   - `chat` command with `--json` through the Click test runner

2. **E2E tests** (`test_full_e2e.py`): Requires `CHEAPER_INFERENCE_API_KEY`
   - Chat completion
   - Streamed chat completion
   - Model listing
