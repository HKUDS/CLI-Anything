import json

import pytest
import requests
from click.testing import CliRunner

from cli_anything.flowise.backend import Flowise
from cli_anything.flowise.flowise_cli import Session, cli


FLOW_ID = "40cb1410-acc3-4ee0-9131-adb6c911a08f"


def test_create_serializes_graph_for_server(monkeypatch, tmp_path):
    graph = {"nodes": [{"id": "start"}], "edges": []}
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    monkeypatch.delenv("FLOWISE_URL", raising=False)
    monkeypatch.setenv("FLOWISE_API_KEY", "management-key")

    def request(method, url, *, headers, json, timeout, allow_redirects):
        assert method == "POST"
        assert url == "http://127.0.0.1:3000/api/v1/chatflows"
        assert headers["Authorization"] == "Bearer management-key"
        assert not allow_redirects
        response = requests.Response()
        response.status_code = 200
        response._content = ('{"id":"' + FLOW_ID + '"}').encode()
        requests_data.update(json)
        return response

    requests_data = {}
    monkeypatch.setattr(requests, "request", request)
    result = CliRunner().invoke(cli, ["--json", "flow", "create", "Example", str(path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"id": FLOW_ID}
    assert json.loads(requests_data["flowData"]) == graph
    assert requests_data["name"] == "Example"


def test_bad_graph_is_rejected_without_api_request(monkeypatch, tmp_path):
    path = tmp_path / "graph.json"
    path.write_text('{"nodes":[]}', encoding="utf-8")

    def unexpected(*args, **kwargs):
        raise AssertionError("Malformed input reached the API")

    monkeypatch.setattr(requests, "request", unexpected)
    result = CliRunner().invoke(cli, ["--json", "flow", "create", "Example", str(path)])
    assert result.exit_code == 1
    assert "nodes and edges" in json.loads(result.output)["error"]


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_graph_cannot_be_written_or_exported(monkeypatch, tmp_path, number):
    contents = '{"nodes":[{"data":' + number + '}],"edges":[]}'
    graph = tmp_path / "graph.json"
    graph.write_text(contents, encoding="utf-8")

    def request(method, url, **kwargs):
        assert method == "GET", "Invalid graph reached a write endpoint"
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"flowData": contents}).encode()
        return response

    monkeypatch.setattr(requests, "request", request)
    for args in [
        ["create", "Example", str(graph)],
        ["update", FLOW_ID, "--graph", str(graph)],
        ["export", FLOW_ID],
    ]:
        result = CliRunner().invoke(cli, ["--json", "flow", *args])
        assert result.exit_code == 1
        assert "must be finite" in json.loads(result.output)["error"]


def test_predict_uses_flow_specific_key(monkeypatch):
    monkeypatch.setenv("FLOWISE_API_KEY", "management-key")
    monkeypatch.setenv("FLOWISE_PREDICTION_KEY", "prediction-key")

    def request(method, url, *, headers, json, timeout, allow_redirects):
        assert method == "POST"
        assert url.endswith(f"/prediction/{FLOW_ID}")
        assert headers["Authorization"] == "Bearer prediction-key"
        assert json == {"question": "test", "streaming": False}
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"text":"answer"}'
        return response

    monkeypatch.setattr(requests, "request", request)
    result = CliRunner().invoke(cli, ["--json", "predict", FLOW_ID, "--question", "test"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["text"] == "answer"


def test_http_error_has_nonzero_status_and_json_diagnostic(monkeypatch):
    response = requests.Response()
    response.status_code = 403
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: response)
    result = CliRunner().invoke(cli, ["--json", "flow", "list"])
    assert result.exit_code == 1
    assert "HTTP 403" in json.loads(result.output)["error"]


@pytest.mark.parametrize(
    ("args", "diagnostic"),
    [
        (["--url", "http://[invalid", "flow", "list"], "server URL"),
        (["flow", "show", ".."], "UUID"),
    ],
)
def test_malformed_api_input_returns_diagnostic(monkeypatch, args, diagnostic):
    def unexpected(*args, **kwargs):
        raise AssertionError("Malformed input reached the API")

    monkeypatch.setattr(requests, "request", unexpected)
    result = CliRunner().invoke(cli, ["--json", *args])
    assert result.exit_code == 1
    assert diagnostic in json.loads(result.output)["error"]


def test_repl_url_override_cannot_mutate_the_original_server(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("A deploy reached the API after selecting another server")

    monkeypatch.setattr(requests, "request", unexpected)
    session = Session(Flowise("https://first.example", None, None), False)
    result = CliRunner().invoke(
        cli, ["--url", "https://second.example", "flow", "deploy", FLOW_ID],
        obj=session,
    )
    assert result.exit_code == 2
    assert "Set --url when starting the REPL" in result.output


def test_repl_command_can_request_compact_json(monkeypatch):
    def request(method, url, **kwargs):
        assert method == "GET"
        assert url == f"https://first.example/api/v1/chatflows/{FLOW_ID}"
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"id": FLOW_ID}).encode()
        return response

    monkeypatch.setattr(requests, "request", request)
    session = Session(Flowise("https://first.example", None, None), False)
    result = CliRunner().invoke(cli, ["--json", "flow", "show", FLOW_ID], obj=session)
    assert result.exit_code == 0, result.output
    assert result.output == json.dumps({"id": FLOW_ID}) + "\n"
