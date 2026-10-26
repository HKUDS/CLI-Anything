---
name: "cli-anything-iflytek-spark"
description: >-
  Command-line interface for iFlytek Spark-X2.5 - chat with the open Spark-X2.5 models through SGLang, vLLM, Ollama, llama.cpp or iFlytek Astron MaaS, with reasoning split out of the answer.
---

# cli-anything-iflytek-spark

A CLI harness for **iFlytek Spark-X2.5**, the open 4B / 1.7B on-device model
series (1M-token context, 200+ languages, tool use and agentic workflows). It
talks to any OpenAI-compatible server that hosts the model.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=iflytek-spark/agent-harness
```

**Prerequisites:**
- Python 3.10+
- A running Spark-X2.5 server: SGLang or vLLM (official launch commands in
  https://github.com/XHToken/Spark-X2.5), `ollama run SparkLLM/Spark-X2.5-1.7B`,
  llama.cpp `llama-server` with the official GGUF, or an iFlytek Astron MaaS API key

## Usage

```bash
# Show help
cli-anything-iflytek-spark --help

# Start interactive REPL mode
cli-anything-iflytek-spark

# Check connectivity
cli-anything-iflytek-spark --json test

# Ask a question (positional text, -p, or stdin)
cli-anything-iflytek-spark --json chat "安徽的省会在哪里？"

# Include the reasoning in the output
cli-anything-iflytek-spark --json chat --show-reasoning "Is 1001 prime?"

# Skip thinking for fast, direct answers
cli-anything-iflytek-spark --json chat --no-think "Translate to English: 你好"

# One-off question that does not touch the conversation history
cli-anything-iflytek-spark --json chat --no-session "Summarize: ..."

# Use another backend or server
cli-anything-iflytek-spark --backend ollama --json chat "hello"
cli-anything-iflytek-spark --base-url http://gpu-box:30000/v1 --json models
```

## Command Groups

### Chat

| Command | Description |
|---------|-------------|
| `chat` | Ask a question; keeps multi-turn context unless `--no-session` |
| `stream` | Same as `chat`, streaming tokens |

Options: `--system`, `--model`, `--temperature`, `--top-p`, `--max-tokens`,
`--no-think`, `--show-reasoning`, `--no-session`.

### Session

| Command | Description |
|---------|-------------|
| `session status` | Message and turn counts |
| `session clear` | Forget the conversation |
| `session history` | Recent prompts |

### Config

| Command | Description |
|---------|-------------|
| `config set <key> <value>` | Keys: `backend`, `base_url`, `api_key`, `default_model` |
| `config get [key]` | Show configuration (API key masked) |
| `config delete <key>` | Remove a value |
| `config path` | Show the config file path |

### Utility

| Command | Description |
|---------|-------------|
| `test` | Short non-thinking request to verify the server |
| `models` | Models served by the backend |
| `backends` | Built-in presets (sglang, vllm, ollama, llamacpp, maas) |

## Backends

| Name | Base URL | Model |
|------|----------|-------|
| `sglang` (default) | `http://localhost:30000/v1` | `spark2.5` |
| `vllm` | `http://localhost:30000/v1` | `spark25` |
| `ollama` | `http://localhost:11434/v1` | `SparkLLM/Spark-X2.5-1.7B` |
| `llamacpp` | `http://localhost:8080/v1` | first model from `/models` |
| `maas` | `https://maas-api.cn-huabei-1.xf-yun.com/v2` | set with `--model` |

Settings resolve as: option > environment variable (`IFLYTEK_SPARK_BACKEND`,
`IFLYTEK_SPARK_BASE_URL`, `IFLYTEK_SPARK_API_KEY`, `IFLYTEK_SPARK_MODEL`) >
config file > preset.

## Output Formats

- **Human-readable** (default): the answer text only
- **Machine-readable** (`--json`): `{"backend", "model", "content", "finish_reason", "usage"}`,
  plus `"reasoning"` with `--show-reasoning`. Errors are `{"error", "type"}` with exit code 1.

`content` never contains `<think>` / `</think>` markup: reasoning is split out
whether the server returns it in `reasoning_content` or inline before `</think>`.

## For AI Agents

1. **Always use `--json`** for parseable output
2. **Use `--no-session`** for independent one-off calls
3. **Use `--no-think`** when latency matters more than reasoning quality
4. **Check the exit code**: 0 on success, 1 on error (message in `error`)
5. Run `test` first; a connection error means no server is running at the base URL

## Version

1.0.0
