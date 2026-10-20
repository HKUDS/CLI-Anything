"""Exercise model selection at the serialized HTTP transport boundary, offline."""

import io
import json

import pytest
import requests
from click.testing import CliRunner

from cli_anything.minimax import minimax_cli
from cli_anything.minimax.utils import minimax_backend as backend


@pytest.fixture
def transport(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(backend, "CONFIG_FILE", tmp_path / "config" / "config.json")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MINIMAX_API_KEY", "fixture-key")
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)
    monkeypatch.setattr(minimax_cli, "_session", None)
    seen = []

    def send(adapter, request, **kwargs):
        payload = json.loads(request.body)
        seen.append((request.url, payload, dict(request.headers)))
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        if payload.get("stream"):
            data = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
            response.raw = io.BytesIO(data)
        else:
            response._content = b'{"choices":[{"message":{"content":"ok"}}]}'
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return seen


@pytest.mark.parametrize("region,host", [
    ("global_en", "api.minimax.io"), ("cn_zh", "api.minimaxi.com"),
])
@pytest.mark.parametrize("command", ["chat", "stream", "test"])
@pytest.mark.parametrize("saved,root,explicit,expected", [
    (None, None, None, "MiniMax-M3.1-Flash"),
    ("MiniMax-M2.7", None, None, "MiniMax-M2.7"),
    ("custom-saved", None, None, "custom-saved"),
    ("custom-saved", "MiniMax-M3", None, "MiniMax-M3"),
    ("custom-saved", "MiniMax-M3", "custom-explicit", "custom-explicit"),
    (None, None, "MiniMax-M2.7-highspeed", "MiniMax-M2.7-highspeed"),
])
def test_cli_serialized_model_selection(
    transport, monkeypatch, region, host, command, saved, root, explicit, expected,
):
    monkeypatch.setenv("MINIMAX_REGION", region)
    if saved:
        backend.save_config({"default_model": saved, "custom_setting": "preserved"})
    config_before = backend.CONFIG_FILE.read_bytes() if saved else None
    session = minimax_cli.get_session()
    prior = {"role": "user", "content": [
        {"type": "text", "text": "Describe this"},
        {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
        {"type": "video_url", "video_url": {"url": "https://example.com/video.mp4"}},
    ]}
    session.messages = [prior]
    session.history = [{"command": "old", "result": {"model": "MiniMax-M2.7"}}]
    session._save()
    args = ["--json"]
    if root:
        args += ["--model", root]
    args += [command]
    if command != "test":
        args += ["--prompt", "hello"]
    if explicit:
        args += ["--model", explicit]
    result = CliRunner().invoke(minimax_cli.cli, args)
    assert result.exit_code == 0, result.output
    assert len(transport) == 1
    url, body, headers = transport[0]
    assert url == f"https://{host}/v1/chat/completions"
    assert headers["Authorization"] == "Bearer fixture-key"
    assert body["model"] == expected
    assert body["temperature"] == 1.0
    # Omission preserves the API's adaptive thinking and default Flash effort.
    for unsupported in ("thinking", "reasoning_effort", "reasoning_split", "service_tier"):
        assert unsupported not in body
    if command != "test":
        assert body["messages"] == [prior, {"role": "user", "content": "hello"}]
        assert session.messages[0] == prior
    assert session.history[0]["result"]["model"] == "MiniMax-M2.7"
    if saved:
        assert backend.CONFIG_FILE.read_bytes() == config_before
    else:
        assert not backend.CONFIG_FILE.exists()


@pytest.mark.parametrize("call", [
    backend.chat_completion, backend.chat_completion_stream, backend.run_full_workflow,
])
def test_backend_fresh_default_and_custom_endpoint(transport, monkeypatch, call):
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://example.com/custom/v1/")
    call(api_key="fixture-key")
    url, body, _ = transport[0]
    assert url == "https://example.com/custom/v1/chat/completions"
    assert body["model"] == "MiniMax-M3.1-Flash"


def test_streaming_workflow_default(transport):
    chunks = []
    assert backend.run_full_workflow(api_key="fixture-key", on_chunk=chunks.append) == {
        "content": "ok",
    }
    assert chunks == ["ok"]
    assert transport[0][1]["model"] == "MiniMax-M3.1-Flash"
