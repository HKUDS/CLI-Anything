"""Real SDK HTTP fixture; opt-in live smoke uses the installed CLI."""

import asyncio
import json
import os
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cli_anything.parallel.utils import parallel_backend as backend


@pytest.fixture
def server(monkeypatch):
    state = {"calls": [], "mode": "success"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(405)
            self.end_headers()

        def do_DELETE(self):
            self.send_response(200)
            self.end_headers()

        def do_POST(self):
            message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["calls"].append((dict(self.headers), message, self.path))
            method = message["method"]
            if method == "tools/call" and "release_call" in state:
                state["call_started"].set()
                state["release_call"].wait(5)
            if method.startswith("notifications/"):
                self.send_response(202)
                self.end_headers()
                return
            response = {"jsonrpc": "2.0", "id": message["id"]}
            if method == "initialize":
                response["result"] = {
                    "protocolVersion": message["params"]["protocolVersion"],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fixture", "version": "1"},
                }
            elif method == "tools/list":
                response["result"] = {
                    "tools": [
                        {"name": name, "inputSchema": {"type": "object"}}
                        for name in ("web_search", "web_fetch")
                    ]
                }
            elif state["mode"] == "http":
                self.send_response(429)
                self.end_headers()
                return
            elif state["mode"] == "redirect":
                self.send_response(307)
                self.send_header("Location", state["redirect"])
                self.end_headers()
                return
            elif state["mode"] == "rpc":
                response["error"] = {"code": -32000, "message": "quota exceeded"}
            else:
                payload = {
                    "results": [
                        {
                            "url": "https://example.org",
                            "title": "Example",
                            "excerpts": ["public text"],
                        }
                    ],
                    "session_id": message["params"]["arguments"]["session_id"],
                }
                if message["params"]["name"] == "web_fetch":
                    payload["errors"] = [
                        {"url": "https://bad.example", "error_type": "timeout"}
                    ]
                if state["mode"] == "malformed":
                    payload = {"not_results": []}
                if state["mode"] == "oversize":
                    payload["padding"] = "a" * (backend.MAX_RESPONSE_BYTES + 1)
                response["result"] = {
                    "content": [{"type": "text", "text": json.dumps(payload)}],
                    "structuredContent": payload,
                    "isError": state["mode"] == "tool",
                }
            data = json.dumps(response).encode()
            content_type = "application/json"
            if state.get("sse"):
                data = b"event: message\ndata: " + data + b"\n\n"
                content_type = "text/event-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if state.get("compressed"):
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}/mcp"
    monkeypatch.setattr(backend, "ENDPOINT", state["url"])
    yield state
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def call(tool="web_search"):
    args = {"session_id": "fixture-task"}
    if tool == "web_search":
        args.update(objective="Find public text", search_queries=["example"])
    else:
        args["urls"] = ["https://example.org"]
    return asyncio.run(backend.request(tool, args))


def test_discovery_search_fetch_and_wire_identity(server):
    assert asyncio.run(backend.request("tools", {}))["tools"] == [
        "web_search",
        "web_fetch",
    ]
    assert call()["results"][0]["excerpts"] == ["public text"]
    assert call("web_fetch")["errors"][0]["error_type"] == "timeout"
    requests = [
        (headers, body)
        for headers, body, _ in server["calls"]
        if body["method"] == "tools/call"
    ]
    assert len(requests) == 2
    for headers, body in requests:
        assert "cli-anything-parallel/1.0.0" in headers["User-Agent"]
        assert "python-httpx/" in headers["User-Agent"]
        assert "Authorization" not in headers and "x-api-key" not in headers
        assert (
            "text/event-stream" in {k.lower(): v for k, v in headers.items()}["accept"]
        )
        assert body["params"]["arguments"]["session_id"] == "fixture-task"


@pytest.mark.parametrize("mode", ["http", "rpc", "tool", "malformed", "oversize"])
def test_failures_are_not_empty_success(server, mode):
    server["mode"] = mode
    with pytest.raises(backend.BackendError):
        call()


def test_redirect_is_not_followed(server):
    server["mode"] = "redirect"
    server["redirect"] = server["url"].replace("/mcp", "/must-not-receive-query")
    with pytest.raises(backend.BackendError):
        call()
    assert all(path == "/mcp" for _, _, path in server["calls"])


def test_deadline_is_enforced(server, monkeypatch):
    monkeypatch.setattr(backend, "DEADLINE_SECONDS", 0.000001)
    with pytest.raises(backend.BackendError):
        call()


@pytest.mark.parametrize("sse", [False, True])
def test_response_limit_reports_the_limit_before_deadline(server, monkeypatch, sse):
    server["sse"] = sse
    server["mode"] = "oversize"
    monkeypatch.setattr(backend, "DEADLINE_SECONDS", 2)
    with pytest.raises(backend.BackendError, match="response exceeds the 2 MiB limit"):
        call()


def test_sse_search_preserves_result(server):
    server["sse"] = True
    assert call()["results"][0]["excerpts"] == ["public text"]


def test_compressed_response_is_rejected(server):
    server["compressed"] = True
    with pytest.raises(backend.BackendError, match="Unexpected compressed MCP response"):
        call()


def test_deadline_cancels_an_inflight_call(server, monkeypatch):
    server["call_started"] = threading.Event()
    server["release_call"] = threading.Event()
    monkeypatch.setattr(backend, "DEADLINE_SECONDS", 1)
    try:
        with pytest.raises(backend.BackendError, match="deadline"):
            call()
        assert server["call_started"].is_set()
    finally:
        server["release_call"].set()


@pytest.mark.skipif(
    os.environ.get("CLI_ANYTHING_PARALLEL_LIVE") != "1",
    reason="set CLI_ANYTHING_PARALLEL_LIVE=1 for real requests",
)
def test_live_installed_cli():
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT")
    }
    commands = [
        ["tools"],
        [
            "search",
            "--objective",
            "Find the official Python documentation",
            "Python documentation",
        ],
        [
            "fetch",
            "https://docs.python.org/3/",
            "--objective",
            "Find the tutorial link",
        ],
    ]
    task_id = str(uuid.uuid4())
    for command in commands:
        result = subprocess.run(
            ["cli-anything-parallel", "--session-id", task_id, "--json", *command],
            env=env,
            capture_output=True,
            text=True,
            timeout=70,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        data = json.loads(result.stdout)
        if command[0] == "tools":
            assert {"web_search", "web_fetch"} <= set(data["tools"])
        else:
            assert data["results"]
            assert any(
                item["url"].startswith("https://docs.python.org")
                for item in data["results"]
            )
            assert any(item["excerpts"] for item in data["results"])
