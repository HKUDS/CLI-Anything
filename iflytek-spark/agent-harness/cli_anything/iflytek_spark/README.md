# cli-anything-iflytek-spark

CLI harness for [iFlytek Spark-X2.5](https://github.com/XHToken/Spark-X2.5), the open
4B / 1.7B on-device model series with 1M-token context. It talks to any
OpenAI-compatible server hosting the model and gives agents a stable,
`--json`-friendly interface on top of it.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=iflytek-spark/agent-harness
```

**Prerequisites:** Python 3.10+ and a running Spark-X2.5 server. Any of these work:

| Backend | How to start it | Default base URL | Default model |
|---------|-----------------|------------------|---------------|
| `sglang` (default) | Official SGLang command in the Spark-X2.5 README | `http://localhost:30000/v1` | `spark2.5` |
| `vllm` | Official vLLM command in the Spark-X2.5 README | `http://localhost:30000/v1` | `spark25` |
| `ollama` | `ollama run SparkLLM/Spark-X2.5-1.7B` (Ollama v0.34.1+) | `http://localhost:11434/v1` | `SparkLLM/Spark-X2.5-1.7B` |
| `llamacpp` | `llama-server -m Spark-X2.5-1.7B-Q4_K_M.gguf --jinja` | `http://localhost:8080/v1` | first model from `/models` |
| `maas` | iFlytek Astron MaaS (hosted), needs an API key | `https://maas-api.cn-huabei-1.xf-yun.com/v2` | set with `--model` / `config` |

## Quick start

```bash
# Check the server answers
cli-anything-iflytek-spark test

# One-shot question (multi-turn context is kept in the session)
cli-anything-iflytek-spark chat "安徽的省会在哪里？"

# Show the reasoning too, as JSON for agents
cli-anything-iflytek-spark --json chat --show-reasoning "Is 1001 prime?"

# Answer without thinking (SGLang / vLLM / llama.cpp)
cli-anything-iflytek-spark chat --no-think "Translate to English: 你好"

# Stream the answer
cli-anything-iflytek-spark stream "Write a haiku about rivers"

# Pick another backend
cli-anything-iflytek-spark --backend ollama chat "hello"
cli-anything-iflytek-spark --base-url http://gpu-box:30000/v1 models

# Interactive REPL
cli-anything-iflytek-spark
```

## Configuration

Each setting resolves in this order: command-line option > environment
variable > config file > backend preset.

| Setting | Option | Environment variable | `config set` key |
|---------|--------|----------------------|------------------|
| Backend preset | `--backend` | `IFLYTEK_SPARK_BACKEND` | `backend` |
| Base URL | `--base-url` | `IFLYTEK_SPARK_BASE_URL` | `base_url` |
| API key (MaaS) | `--api-key` | `IFLYTEK_SPARK_API_KEY` | `api_key` |
| Model id | `--model` | `IFLYTEK_SPARK_MODEL` | `default_model` |

Config and session files live in `~/.cli-anything-iflytek-spark/`
(override with `IFLYTEK_SPARK_HOME`).

## Reasoning output

Spark-X2.5 thinks by default, and its chat template pre-fills `<think>` into the
prompt. How the reasoning comes back depends on the server:

- With a reasoning parser (SGLang `--reasoning-parser qwen3`, llama.cpp's
  default), it arrives in `reasoning_content`.
- Without one, it is inline in `content`: `<think>reasoning</think>answer`
  (llama.cpp `--reasoning-format none`) or just `reasoning</think>answer`
  (e.g. the official vLLM command, which has no `--reasoning-parser`).

The CLI handles both. `content` is always only the final answer, and
`--show-reasoning` adds the reasoning separately. Only final answers are kept
in the multi-turn session.

## Commands

| Command | Description |
|---------|-------------|
| `chat [PROMPT]` | Ask a question (`-p`, positional text, or stdin) |
| `stream [PROMPT]` | Same as `chat`, streaming tokens |
| `models` | List models served by the backend |
| `backends` | Show built-in backend presets |
| `test` | Connectivity check with a short non-thinking request |
| `session status/clear/history` | Manage the multi-turn conversation |
| `config set/get/delete/path` | Persistent configuration |

`chat` / `stream` options: `--system`, `--model`, `--temperature`, `--top-p`,
`--max-tokens`, `--no-think`, `--show-reasoning`, `--no-session`.
Spark-X2.5 recommends `temperature=1.0`, `top_p=0.95`.

## Tests

```bash
cd iflytek-spark/agent-harness
pip install -e .
python -m pytest cli_anything/iflytek_spark/tests/test_core.py -v      # no server needed
python -m pytest cli_anything/iflytek_spark/tests/test_full_e2e.py -v  # needs a live server
```
