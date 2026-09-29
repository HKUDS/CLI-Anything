# TEST.md — cli-anything-iflytek-spark

## Test plan

### Unit tests (`test_core.py`, no server needed)

HTTP is mocked with `unittest.mock`; config and session files go to a
temporary `IFLYTEK_SPARK_HOME`.

| Area | What is checked |
|------|-----------------|
| Settings | Backend presets, unknown backend, precedence (option > env > config > preset), trailing-slash handling, config round-trip, secret masking |
| Reasoning split | `reasoning_content` field, Ollama `reasoning` field, pre-filled `<think>` (only `</think>` in content), full `<think>…</think>` block, no reasoning, `null` content |
| Stream splitter | `</think>` split across chunks, stream without a close tag, pass-through mode, server-side reasoning deltas releasing the buffer |
| Requests | `--no-think` → `chat_template_kwargs.enable_thinking=false`, sampling params, Bearer header only when a key is set, HTTP error and connection error mapping, model auto-detect from `/models` |
| Streaming | SSE with `reasoning_content` deltas, SSE with inline `</think>`, pass-through with thinking disabled |
| Session | Persistence of exchanges (UTF-8), turn count, clear |
| CLI | `--help`, `backends --json`, `chat --json --show-reasoning`, multi-turn history sent to the server, `--no-session`, stdin prompt, empty prompt error, global options reaching the request, JSON error on connection failure, `models --json`, config masking and validation, `stream --json` |

### E2E tests (`test_full_e2e.py`)

All tests run the installed `cli-anything-iflytek-spark` command through
`subprocess` (`_resolve_cli`, honours `CLI_ANYTHING_FORCE_INSTALLED=1`).

- Always run: `--help`, `backends`, `config` round-trip, unreachable server
  error in JSON.
- Live (need a Spark-X2.5 server, skipped otherwise): `models`, `test`,
  `chat --show-reasoning` (arithmetic answer, reasoning present, no think tags
  in content), `chat --no-think`, `stream`, two-turn session (history reaches
  the server, checked via prompt token counts), stdin prompt.

Point the live tests at a server with the usual settings, e.g.
`IFLYTEK_SPARK_BACKEND=llamacpp` or `IFLYTEK_SPARK_BASE_URL=http://host:30000/v1`.

## Test results

Environment: Windows 11, Python 3.11, official `Spark-X2.5-1.7B-Q4_K_M.gguf`
(ModelScope, sha256 `902bde25…0503f4`) on llama.cpp `llama-server` b11256 (CPU).

```
$ python -m pytest cli_anything/iflytek_spark/tests/test_core.py -q
41 passed in 2.62s

# llama-server -m Spark-X2.5-1.7B-Q4_K_M.gguf --port 8080 --jinja
# (default reasoning parser: reasoning arrives in reasoning_content)
$ CLI_ANYTHING_FORCE_INSTALLED=1 IFLYTEK_SPARK_BACKEND=llamacpp     python -m pytest cli_anything/iflytek_spark/tests/test_full_e2e.py -v
test_help PASSED
test_backends_json PASSED
test_config_roundtrip PASSED
test_unreachable_server_reports_error PASSED
test_models PASSED                 models: ['Spark-X2.5-1.7B-Q4_K_M.gguf']
test_connectivity PASSED
test_chat_splits_reasoning PASSED  content: '391'
test_chat_no_think PASSED          content: 'Hello'
test_stream PASSED                 content: 'Paris'
test_multi_turn_session PASSED     prompt tokens: fresh=26 with history=42
test_stdin_prompt PASSED
11 passed in 88.63s

# llama-server ... --reasoning-format none
# (no parser: content is "<think>…</think>answer")
$ IFLYTEK_SPARK_BASE_URL=http://127.0.0.1:8081/v1 IFLYTEK_SPARK_BACKEND=llamacpp     python -m pytest cli_anything/iflytek_spark/tests/test_full_e2e.py -v
11 passed in 104.17s
```

Coverage notes: SGLang, vLLM, Ollama and MaaS were not run live here. They
share the same OpenAI-compatible code path, and their response shapes
(`reasoning_content`, `reasoning`, `…</think>answer` without an opening tag)
are covered by the unit tests.
