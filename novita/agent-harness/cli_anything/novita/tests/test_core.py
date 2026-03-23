"""Unit tests for Novita backend - no API key required (mock HTTP)."""

import json
import requests
from unittest.mock import patch, MagicMock

from cli_anything.novita.utils.novita_backend import (
    get_api_key,
    load_config,
    save_config,
    list_models,
    chat_completion,
    chat_completion_stream,
    run_full_workflow,
)


def test_get_api_key_priority():
    """Test API key resolution order: CLI arg > env > config."""
    with patch.dict("os.environ", {}, clear=True):
        # No env, no config, no CLI arg
        assert get_api_key(None) is None

    # CLI arg takes priority
    assert get_api_key("cli-key-123") == "cli-key-123"

    with patch.dict("os.environ", {"NOVITA_API_KEY": "env-key-456"}):
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
        import cli_anything.novita.utils.novita_backend as backend

        original_file = backend.CONFIG_FILE
        backend.CONFIG_FILE = config_file

        try:
            # Save config
            save_config(
                {"api_key": "test-key-123", "default_model": "deepseek/deepseek-v3.2"}
            )

            # Load config
            loaded = load_config()
            assert loaded["api_key"] == "test-key-123"
            assert loaded["default_model"] == "deepseek/deepseek-v3.2"
        finally:
            backend.CONFIG_FILE = original_file


def test_list_models_success():
    """Test listing models with mock response."""
    mock_response = {
        "data": [
            {"id": "deepseek/deepseek-v3.2", "name": "DeepSeek V3.2"},
            {"id": "zai-org/glm-5", "name": "GLM-5"},
        ]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        models = list_models("fake-key")
        assert len(models) == 2
        assert models[0]["id"] == "deepseek/deepseek-v3.2"


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
            model="deepseek/deepseek-v3.2",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert (
            result["choices"][0]["message"]["content"]
            == "Hello! How can I help you today?"
        )
        assert result["usage"]["total_tokens"] == 22


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
