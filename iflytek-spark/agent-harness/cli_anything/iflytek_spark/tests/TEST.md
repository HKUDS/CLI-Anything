# TEST.md — cli-anything-iflytek-spark

## Test plan

### Unit tests (`test_core.py`, no server needed)

HTTP is mocked with `unittest.mock`; config and session files go to a
temporary `IFLYTEK_SPARK_HOME`.

| Area | What is checked |
|------|-----------------|
| Settings | Backend presets, unknown backend, precedence (option > env > config > preset), trailing-slash handling, config round-trip, non-object JSON treated as empty config, secret masking |
| Reasoning split | `reasoning_content` field, Ollama `reasoning` field, pre-filled `<think>` (only `</think>` in content), full `<think>…</think>` block, no reasoning, `null` content |
| Stream splitter | `</think>` split across chunks, stream without a close tag, pass-through mode, server-side reasoning deltas releasing the buffer |
| Requests | `--no-think` → `chat_template_kwargs.enable_thinking=false`, sampling params, Bearer header only when a key is set, HTTP error and connection error mapping, model auto-detect from `/models` |
| Streaming | SSE with `reasoning_content` deltas, SSE with inline `</think>` even if a no-think request is ignored, direct no-think answers, final finish reason and empty-choices usage chunk |
| Session | Persistence of exchanges (UTF-8), turn count, clear, restrictive creation mode and tightening an existing session |
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

## Session and truncated-stream verification (2026-10-25)

Windows, Python 3.11.15, with mocked HTTP and no live model calls:

```text
Head ae7e03be with seven new regression cases: 7 failed, 51 passed, 2 skipped
Fixed code, complete unit suite:              58 passed, 2 skipped
Fixed code, CLI subprocess suite:              4 passed, 7 skipped
```

The regressions cover stale session objects, clear followed by a stale append,
three synchronized writer processes, split opening tags in truncated streams,
and text/JSON CLI output and saved history. The file lock covers reload, append
and save as one transaction; readers and clear use the same lock. The real
multi-process test ran on Windows; POSIX file-mode checks remain skipped there.
The four subprocess cases used the module entry point; the seven live cases
were skipped with the backend set to an unreachable loopback port.
A final run of both test files together passed 62 cases and skipped nine.
The interpreter version was captured in that run; 3.12.6 in the initial
follow-up note was a transcription error from the earlier review session.
No historical live-model result below validates this follow-up.

## Review-fix verification (2026-10-22)

Windows, Python 3.12.6; HTTP mocked for the unit suite. No model server or
service credentials were used. All dummy fixtures were retained locally.

```text
Original head 7a6d454, original unit tests: 41 passed
Original head, new regression suite:     11 failed, 40 passed, 2 skipped
Fixed code, complete unit suite:          51 passed, 2 skipped
Fixed code, CLI subprocess suite:         4 passed, 7 skipped
```

The two unit skips are actual POSIX mode assertions on Windows; the owner-only
creation/chmod calls are checked locally, but real POSIX permissions await a
POSIX run. The seven CLI skips require a live model server. The four passing
CLI tests used `python -m cli_anything.iflytek_spark`, not a newly installed
entry point. The old-head failures cover non-object configuration, terminal
stream metadata, ignored no-think normalization, session restrictions and JSON
stream metadata. These results do not rerun the historical model tests below
or validate every supported provider.

## Historical test results (before the review fixes)

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

## Review follow-up — 2026-10-26

On Windows with Python 3.11.15, the final offline suite passes 72 cases and skips 11 (four POSIX permissions cases and seven live-server cases). Ten new executable regressions fail on e2b18c46; two additional config-permission regressions require POSIX and were skipped locally.

The regressions cover unfinished non-streaming thinking blocks, HTTP-200 SSE error frames before and after partial output, JSON filesystem errors, preserving the previous config after a failed write, config-file permissions before writing, and resolved connection settings in isolated test subprocesses. Streaming failures leave session history unchanged and close the response. Config replacement uses a private temporary file in the same directory. No live model requests or POSIX execution were performed for this follow-up.

## Persistence follow-up — 2026-10-26

The final Windows / Python 3.11.15 suite passes 79 cases and skips 13: six POSIX permission cases and seven live-server cases. On c1a76d06, five new regressions fail, two completion-marker controls pass, and two new POSIX REPL-permission cases skip.

Session replacement now happens under a separate persistent lock file so failed writes preserve the previous conversation while concurrent processes keep sharing the same lock. The existing real three-process append regression still passes. REPL history is created/restricted before prompt-toolkit loads it, without changing the shared repl_skin.py copy. Streams require [DONE] or a terminal finish_reason before committing the exchange. Actual POSIX permissions, Windows ACL isolation and live models were not validated.
