import json

import pytest
from click.testing import CliRunner
from mcp.types import CallToolResult, TextContent

from cli_anything.parallel.parallel_cli import main
from cli_anything.parallel.utils import parallel_backend as backend


@pytest.fixture
def calls(monkeypatch):
    calls = []

    async def request(tool, args):
        calls.append((tool, args))
        return {
            "results": [],
            "session_id": args.get("session_id"),
            "warnings": ["sample warning"],
        }

    monkeypatch.setattr(backend, "request", request)
    return calls


def test_search_and_fetch_share_explicit_task(calls):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--session-id",
            "task-1",
            "search",
            "--objective",
            "Find docs",
            "Python docs",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["warnings"] == ["sample warning"]
    assert calls[-1] == (
        "web_search",
        {
            "objective": "Find docs",
            "search_queries": ["Python docs"],
            "session_id": "task-1",
        },
    )
    result = runner.invoke(
        main,
        [
            "--json",
            "--session-id",
            "task-1",
            "fetch",
            "https://example.org",
            "--query",
            "docs",
            "--full-content",
        ],
    )
    assert result.exit_code == 0
    assert calls[-1] == (
        "web_fetch",
        {
            "urls": ["https://example.org"],
            "search_queries": ["docs"],
            "full_content": True,
            "session_id": "task-1",
        },
    )


@pytest.mark.parametrize(
    "args",
    [
        ["search", "--objective", " ", "query"],
        ["search", "--objective", "docs", " "],
        ["search", "--objective", "docs", "q" * 201],
        ["search", "--objective", "docs", *["q"] * 6],
        ["fetch", *["https://example.org"] * 21],
        ["fetch", "https://user:secret@example.org"],
        ["fetch", "file:///tmp/private"],
        ["fetch", "https://[invalid"],
        ["fetch", "https://example.org", "--objective", "x" * 201],
        ["fetch", "https://example.org", "--query", " "],
        ["--session-id", " ", "tools"],
        ["--session-id", "s" * 101, "tools"],
    ],
)
def test_invalid_inputs_make_no_requests(calls, args):
    assert CliRunner().invoke(main, args).exit_code == 2
    assert calls == []


def test_help_makes_no_request(calls):
    assert CliRunner().invoke(main, []).exit_code == 0
    assert CliRunner().invoke(main, ["--help"]).exit_code == 0
    assert calls == []


def test_repl_reuses_task_across_commands(calls):
    result = CliRunner().invoke(
        main,
        ["repl", "--json"],
        input='search --objective docs "Python docs"\nfetch https://example.org\nexit\n',
    )
    assert result.exit_code == 0, result.output
    assert len(calls) == 2
    assert calls[0][1]["session_id"] == calls[1][1]["session_id"]
    for line in result.output.splitlines():
        json.loads(line)


def test_tool_failure_is_nonzero_json(monkeypatch):
    async def fail(*args):
        raise backend.BackendError("quota exceeded")

    monkeypatch.setattr(backend, "request", fail)
    result = CliRunner().invoke(
        main, ["search", "--objective", "docs", "Python docs", "--json"]
    )
    assert result.exit_code == 1
    assert json.loads(result.output) == {"error": "quota exceeded"}


def test_structured_result_preserves_partial_errors_without_duplicate_text():
    payload = {
        "results": [
            {"url": "https://example.org", "excerpts": ["Text"], "title": "Example"}
        ],
        "errors": [{"url": "https://bad.example", "error_type": "timeout"}],
        "warnings": ["partial"],
    }
    result = CallToolResult(
        content=[TextContent(type="text", text="unused duplicate")],
        structuredContent=payload,
    )
    assert backend._decode(result) == payload


def test_text_result_and_empty_success():
    assert backend._decode(
        CallToolResult(content=[TextContent(type="text", text='{"results": []}')])
    ) == {"results": []}


@pytest.mark.parametrize(
    "payload",
    [{}, {"results": None}, {"results": [{}]}, {"results": [], "errors": "bad"}],
)
def test_malformed_payload_is_error(payload):
    with pytest.raises(backend.BackendError):
        backend._decode(CallToolResult(content=[], structuredContent=payload))


def test_tool_error_precedes_success_payload():
    with pytest.raises(backend.BackendError, match="MCP tool error"):
        backend._decode(
            CallToolResult(isError=True, content=[], structuredContent={"results": []})
        )


def test_output_limit_fails_without_truncating(monkeypatch):
    monkeypatch.setattr(backend, "MAX_OUTPUT_BYTES", 10)
    with pytest.raises(backend.BackendError, match="output limit"):
        backend._decode(CallToolResult(content=[], structuredContent={"results": []}))


@pytest.mark.parametrize("compact", [False, True])
def test_rendered_output_limit_includes_formatting(monkeypatch, compact):
    payload = {
        "results": [{"url": "https://example.org", "excerpts": ["a"] * 100000}]
    }

    async def request(*args):
        return backend._decode(CallToolResult(content=[], structuredContent=payload))

    monkeypatch.setattr(backend, "request", request)
    result = CliRunner().invoke(
        main, ["fetch", "https://example.org", *(["--json"] if compact else [])]
    )
    assert len(result.output.encode("utf-8")) <= backend.MAX_OUTPUT_BYTES
    if compact:
        assert result.exit_code == 0
        assert json.loads(result.output) == payload
    else:
        assert result.exit_code == 1
        assert "Output exceeds" in result.output


def test_tools_output_is_bounded(monkeypatch):
    async def request(*args):
        return {"tools": ["t" * backend.MAX_OUTPUT_BYTES]}

    monkeypatch.setattr(backend, "request", request)
    result = CliRunner().invoke(main, ["tools", "--json"])
    assert result.exit_code == 1
    assert "Output exceeds" in json.loads(result.output)["error"]


@pytest.mark.parametrize("compact", [False, True])
def test_repl_needs_no_writable_home(monkeypatch, tmp_path, compact):
    home = tmp_path / "unavailable-home"
    home.write_text("not a directory")
    monkeypatch.setenv("HOME", str(home))
    result = CliRunner().invoke(
        main, ["repl", *(["--json"] if compact else [])], input="exit\n"
    )
    assert result.exit_code == 0, result.exception
    assert home.read_text() == "not a directory"
