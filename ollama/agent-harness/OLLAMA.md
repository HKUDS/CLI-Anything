# Ollama: Project-Specific Analysis & SOP

## Architecture Summary

Ollama is a local LLM runtime that serves models via a REST API on `localhost:11434`.
It handles model downloading, quantization, GPU/CPU inference, and memory management.

```
┌──────────────────────────────────────────────┐
│              Ollama Server                   │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │  Model    │ │ Generate │ │  Embeddings │  │
│  │  Manager  │ │  Engine  │ │   Engine    │  │
│  └────┬──────┘ └────┬─────┘ └──────┬──────┘  │
│       │             │              │          │
│  ┌────┴─────────────┴──────────────┴───────┐ │
│  │         REST API (port 11434)           │ │
│  │  /api/tags  /api/generate  /api/embed   │ │
│  │  /api/pull  /api/chat      /api/show    │ │
│  │  /api/delete /api/copy     /api/ps      │ │
│  └─────────────────┬───────────────────────┘ │
└────────────────────┼─────────────────────────┘
                     │
         ┌───────────┴──────────┐
         │  llama.cpp backend   │
         │  GGUF model format   │
         │  GPU/CPU inference   │
         └──────────────────────┘
```

## CLI Strategy: REST API Wrapper

Ollama already provides a clean REST API. Our CLI wraps it with:

1. **requests** — HTTP client for all API calls
2. **Streaming NDJSON** — For progressive output during generation and model pulls
3. **Click CLI** — Structured command groups matching the API surface
4. **REPL** — Interactive mode for exploratory use

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Server status check |
| `/api/tags` | GET | List local models |
| `/api/show` | POST | Model details |
| `/api/pull` | POST | Download model (streaming) |
| `/api/delete` | DELETE | Remove model |
| `/api/copy` | POST | Copy/rename model |
| `/api/ps` | GET | Running models |
| `/api/generate` | POST | Text generation (streaming) |
| `/api/chat` | POST | Chat completion (streaming) |
| `/api/embed` | POST | Generate embeddings |
| `/api/version` | GET | Server version |

## Command Map: Ollama Native CLI → CLI-Anything

| Ollama CLI | CLI-Anything |
|-----------|-------------|
| `ollama list` | `model list` |
| `ollama show <name>` | `model show <name>` |
| `ollama pull <name>` | `model pull <name>` |
| `ollama rm <name>` | `model rm <name>` |
| `ollama cp <src> <dst>` | `model copy <src> <dst>` |
| `ollama ps` | `model ps` |
| `ollama run <model> <prompt>` | `generate text --model <name> --prompt "..."` |
| (no equivalent) | `generate chat --model <name> --message "..."` |
| (no equivalent) | `embed text --model <name> --input "..." [--input "..."]` |
| `ollama serve` | (external — must be running) |

## Model Parameters (options)

| Parameter | Type | Description |
|-----------|------|-------------|
| `temperature` | float | Sampling temperature (0.0-2.0) |
| `top_p` | float | Nucleus sampling threshold |
| `top_k` | int | Top-k sampling |
| `num_predict` | int | Max tokens to generate |
| `repeat_penalty` | float | Repetition penalty |
| `seed` | int | Random seed for reproducibility |
| `stop` | list[str] | Stop sequences |

## Test Coverage Plan

1. **Unit tests** (`test_core.py`): No Ollama server needed
   - URL construction in backend
   - Output formatting
   - CLI argument parsing via Click test runner
   - Session state management
   - Error handling paths

2. **E2E tests** (`test_full_e2e.py`): Requires Ollama running
   - List models
   - Pull a small model
   - Generate text
   - Chat completion
   - Show model info
   - Embeddings
   - Delete model
