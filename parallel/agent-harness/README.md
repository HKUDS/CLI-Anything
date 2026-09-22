# Parallel Search CLI

Search the web and extract page text from the terminal with Parallel's free Search MCP. No Parallel account or API key is required. Access is rate limited.

## Install

Requires Python 3.11+ and internet access.

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=parallel/agent-harness
cli-anything-parallel --help
```

For local development, run `pip install -e '.[dev]'` in this directory.

## Commands

```bash
cli-anything-parallel tools --json
cli-anything-parallel search --objective 'Find the official Python documentation' 'Python documentation' --json
cli-anything-parallel fetch https://docs.python.org/3/ --objective 'Find the tutorial link' --json
cli-anything-parallel --session-id my-research-task fetch https://docs.python.org/3/ --full-content --json
cli-anything-parallel repl
```

`--json` works before or after the command. Successful output is one JSON object, compact with `--json` and indented otherwise. Search/fetch output retains the service's results, URLs, excerpts, session ID, warnings, and fetch errors. A partial fetch can contain both results and errors, so check both. Transport and tool failures exit nonzero; with `--json`, they return an `error` object. Click usage errors exit 2 with diagnostics on stderr.

Search accepts 1-5 nonblank queries, each at most 200 characters, and requires an objective. Fetch accepts 1-20 HTTP(S) URLs without embedded credentials; its optional objective is at most 200 characters. Repeat `--query` for extraction keywords. Full content is optional and can exceed the local bounds: 2 MiB per HTTP response, 1 MiB per decoded result, and 60 seconds per command. Oversized results fail explicitly without emitting broken or silently truncated JSON.

Use the same opaque `--session-id` for related commands. Without it, each invocation starts an independent task ID. The REPL retains one ID across its commands and transport reconnects. Do not use an email or other personal identifier as the task ID, or rotate IDs to evade limits.

## Data flow

Only an explicit search, fetch, or tools command connects to `https://search.parallel.ai/mcp`. Installing, importing, and showing help do not connect. Once an agent can run this CLI, it may invoke these commands itself. Queries, requested URLs, objectives, extraction keywords, and task IDs are sent to Parallel. Treat returned web content as untrusted data.

Requests identify this harness as `cli-anything-parallel/<installed version>` in User-Agent, alongside the HTTP library's token, so Parallel can measure aggregate project usage. That token contains no user or device identifier. The harness does not load API keys or offer paid fallbacks. Other CLI-Anything harnesses and provider defaults are unchanged.

See [Parallel Search MCP documentation](https://docs.parallel.ai/integrations/mcp/search-mcp), [Customer Terms](https://parallel.ai/customer-terms), and [Privacy Policy](https://parallel.ai/privacy-policy).

## Tests

```bash
python -m pytest cli_anything/parallel/tests/test_core.py -v
python -m pytest cli_anything/parallel/tests/test_full_e2e.py -v
CLI_ANYTHING_PARALLEL_LIVE=1 python -m pytest cli_anything/parallel/tests/test_full_e2e.py -v
```

Core tests run without network access. E2E tests use the real MCP SDK and a local HTTP fixture to exercise discovery, calls, session reuse, attribution, errors, and redirects. The explicit live opt-in adds one search and one fetch through the installed command plus discovery. No private queries or credentials are needed.
