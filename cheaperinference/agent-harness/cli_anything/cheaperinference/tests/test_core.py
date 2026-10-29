"""Unit tests for Cheaper Inference backend - no API key required (mock HTTP)."""

import json
import requests
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from cli_anything.cheaperinference.utils.cheaperinference_backend import (
    get_api_key,
    load_config,
    save_config,
    list_models,
    chat_completion,
    chat_completion_stream,
    run_full_workflow,
    API_BASE,
    DEFAULT_MODEL,
)


def test_get_api_key_priority():
    """Test API key resolution order: CLI arg > env > config."""
    with patch.dict("os.environ", {}, clear=True):
        # No env, no config, no CLI arg
        assert get_api_key(None) is None

    # CLI arg takes priority
    assert get_api_key("cli-key-123") == "cli-key-123"

    with patch.dict("os.environ", {"CHEAPER_INFERENCE_API_KEY": "env-key-456"}):
        # Env takes priority over config
        assert get_api_key(None) == "env-key-456"


def test_save_and_load_config(tmp_path):
    """Test config save/load."""
    import tempfile
    from pathlib import Path

    # Use a temp config file
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"

        # Patch CONFIG_FILE
        import cli_anything.cheaperinference.utils.cheaperinference_backend as backend

        original_dir = backend.CONFIG_DIR
        original_file = backend.CONFIG_FILE
        backend.CONFIG_DIR = Path(tmpdir)
        backend.CONFIG_FILE = config_file

        try:
            # Save config
            save_config(
                {"api_key": "test-key-123", "default_model": "gpt-5.4-mini"}
            )

            # Load config
            loaded = load_config()
            assert loaded["api_key"] == "test-key-123"
            assert loaded["default_model"] == "gpt-5.4-mini"
        finally:
            backend.CONFIG_DIR = original_dir
            backend.CONFIG_FILE = original_file


def test_list_models_success():
    """Test listing models with mock response."""
    mock_response = {
        "data": [
            {"id": "gpt-5.4-mini", "name": "GPT-5.4 mini"},
            {"id": "glm-5.3", "name": "GLM-5.3"},
        ]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        models = list_models("fake-key")
        assert len(models) == 2
        assert models[0]["id"] == "gpt-5.4-mini"
        assert mock_get.call_args[0][0] == f"{API_BASE}/models"
        assert mock_get.call_args[1]["headers"]["Authorization"] == "Bearer fake-key"


def test_chat_completion_success():
    """Test chat completion with mock response."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = chat_completion(
            api_key="fake-key",
            model="gpt-5.4-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert (
            result["choices"][0]["message"]["content"]
            == "Hello! How can I help you today?"
        )
        assert result["usage"]["total_tokens"] == 22
        assert mock_post.call_args[0][0] == f"{API_BASE}/chat/completions"
        assert mock_post.call_args[1]["json"]["model"] == "gpt-5.4-mini"


def test_chat_completion_error():
    """Test chat completion with error response."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error": "Invalid API key"}'
        mock_resp.raise_for_status.side_effect = requests.HTTPError("HTTP 401 Error")
        mock_post.return_value = mock_resp

        try:
            chat_completion(api_key="invalid-key", messages=[])
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "API key" in str(e) or "error" in str(e).lower() or "401" in str(e)


def test_run_full_workflow():
    """Test full workflow with mock response."""
    mock_response = {
        "choices": [
            {"message": {"role": "assistant", "content": "Here is the response"}}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = run_full_workflow(
            api_key="fake-key",
            prompt="Test prompt",
            system_message="You are a helpful assistant",
        )

        assert result["content"] == "Here is the response"
        assert result["prompt_tokens"] == 10
        assert result["completion_tokens"] == 15
        assert result["total_tokens"] == 25


def test_default_api_base_and_model():
    """Test default endpoint and model."""
    assert API_BASE == "https://api.cheaperinference.com/v1"
    assert DEFAULT_MODEL == "gpt-5.4-mini"


def test_missing_api_key_error():
    """Test that a missing key gives a clear error."""
    try:
        chat_completion(api_key=None, messages=[])
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "CHEAPER_INFERENCE_API_KEY" in str(e)


def test_cli_chat_json(tmp_path):
    """Test the chat command with JSON output and a mocked API."""
    from cli_anything.cheaperinference import cheaperinference_cli as cli_mod
    from cli_anything.cheaperinference.core.session import ChatSession

    mock_response = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
    }

    with patch("requests.post") as mock_post, patch.object(
        cli_mod, "_session", ChatSession(session_file=str(tmp_path / "session.json"))
    ), patch.object(cli_mod, "load_config", return_value={}):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = CliRunner().invoke(
            cli_mod.cli, ["--json", "--api-key", "fake-key", "chat", "--prompt", "Hi"]
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["content"] == "ok"
        assert mock_post.call_args[1]["json"]["model"] == DEFAULT_MODEL
