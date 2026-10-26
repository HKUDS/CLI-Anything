# iFlytek Spark-X2.5 CLI Harness — SOP

## Target software

[Spark-X2.5](https://github.com/XHToken/Spark-X2.5) is iFlytek's open model
series for on-device use (Spark-X2.5-4B and Spark-X2.5-1.7B, Apache-2.0),
with a native context window of up to 1M tokens, 200+ languages, tool use and
agentic workflows. It is published on Hugging Face, ModelScope, Ollama and
other hubs, and is also offered as a hosted model on iFlytek Astron MaaS.

The "backend" for this harness is any running server that hosts the model and
exposes the OpenAI Chat Completions API. The Spark-X2.5 README documents:

| Runtime | Launch | Served model name |
|---------|--------|-------------------|
| SGLang | `python -m sglang.launch_server --served-model-name spark2.5 --reasoning-parser qwen3 --tool-call-parser spark25 --port 30000 ...` | `spark2.5` |
| vLLM | `vllm serve ... --served-model-name spark25 --port 30000` | `spark25` |
| Ollama | `ollama run SparkLLM/Spark-X2.5-1.7B` | `SparkLLM/Spark-X2.5-1.7B` |
| llama.cpp | `llama-server -m Spark-X2.5-1.7B-Q4_K_M.gguf --jinja` | GGUF file name |
| Astron MaaS | hosted, Bearer API key | from the MaaS model card |

## Architecture

```
spark_cli.py            Click group, REPL, --json output, error handling
core/session.py         Multi-turn history persisted to session.json
utils/spark_backend.py  Settings resolution, HTTP calls, reasoning split
utils/repl_skin.py      Shared REPL skin (unmodified copy)
```

### Settings

`resolve_settings()` merges four layers per field: CLI option > environment
variable (`IFLYTEK_SPARK_*`) > `~/.cli-anything-iflytek-spark/config.json` >
backend preset. If no model is set (llama.cpp, MaaS without a configured
model), the first id from `GET /models` is used.

### Reasoning handling

Spark-X2.5 thinks by default. Its chat template has
`enable_thinking | default(true)` and pre-fills `<think>` into the generation
prompt, so the model output starts inside the reasoning block. Depending on
the server this reaches the client as:

1. `message.reasoning_content` (SGLang with `--reasoning-parser qwen3`, vLLM
   with a reasoning parser, llama.cpp `llama-server` by default) or
   `message.reasoning` (Ollama), or
2. inline text in `content`: `<think>reasoning</think>answer` (llama.cpp with
   `--reasoning-format none`, which re-adds the pre-filled tag) or
   `reasoning</think>answer` with no opening tag (servers that pass the raw
   generation through, e.g. the official vLLM command without a reasoning
   parser).

`split_reasoning()` normalises both shapes for non-streaming calls.
`ThinkStreamSplitter` does the same for SSE streams: it buffers `content`
deltas until the first `</think>` (which may be split across chunks), emits
the buffer as reasoning, then passes the rest through. If the server sends
reasoning deltas itself, or `--no-think` was requested, it switches to
pass-through immediately.

`--no-think` sends `chat_template_kwargs: {"enable_thinking": false}`, which
SGLang, vLLM and llama.cpp forward to the chat template.

Only final answers are stored in the session, since the template drops
earlier turns' reasoning anyway.

## Command map

| CLI | HTTP |
|-----|------|
| `chat`, `test` | `POST {base_url}/chat/completions` |
| `stream` | `POST {base_url}/chat/completions` with `stream: true` (SSE) |
| `models` | `GET {base_url}/models` |
| `backends`, `config`, `session` | local only |

## Testing

- `test_core.py`: HTTP is mocked. Covers settings precedence, both reasoning
  shapes, stream splitting across chunk boundaries, request bodies, error
  mapping, session persistence and the Click commands.
- `test_full_e2e.py`: invokes the installed `cli-anything-iflytek-spark`
  command via subprocess. The server-independent tests always run; the live
  tests run against the configured server and are skipped when it is
  unreachable.
