"""Unit tests for MiniMax backend — no API key required (mock HTTP)."""

import json
import requests
from unittest.mock import patch, MagicMock

from cli_anything.minimax.utils.minimax_backend import (
    get_api_key,
    load_config,
    save_config,
    chat_completion,
    chat_completion_stream,
    tts_synthesize,
    run_full_workflow,
    REGIONAL_ENDPOINTS,
    TEXT_MODEL_CONFIG,
    MULTIMODAL_CONFIG,
    CHAT_MODELS,
    TTS_MODELS,
    TTS_VOICES,
)


# ── API key resolution ─────────────────────────────────────────────────────────

def test_get_api_key_priority():
    """Test API key resolution order: CLI arg > env > config."""
    with patch.dict("os.environ", {}, clear=True):
        assert get_api_key(None) is None

    # CLI arg takes priority
    assert get_api_key("cli-key-123") == "cli-key-123"

    with patch.dict("os.environ", {"MINIMAX_API_KEY": "env-key-456"}):
        assert get_api_key(None) == "env-key-456"


def test_get_api_key_no_env_no_config():
    """No key available returns None."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("cli_anything.minimax.utils.minimax_backend.load_config", return_value={}):
            assert get_api_key(None) is None


# ── Config persistence ─────────────────────────────────────────────────────────

def test_save_and_load_config(tmp_path):
    """Test config save/load."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"
        import cli_anything.minimax.utils.minimax_backend as backend

        original_file = backend.CONFIG_FILE
        backend.CONFIG_FILE = config_file
        try:
            save_config({"api_key": "test-key-123", "default_model": "MiniMax-M3"})
            loaded = load_config()
            assert loaded["api_key"] == "test-key-123"
            assert loaded["default_model"] == "MiniMax-M3"
        finally:
            backend.CONFIG_FILE = original_file


# ── Chat models ────────────────────────────────────────────────────────────────

def test_text_model_catalog():
    """The text catalog must match the refreshed MiniMax target models."""
    assert TEXT_MODEL_CONFIG["model_id"] == "MiniMax-M3"
    assert TEXT_MODEL_CONFIG["model_ids"] == ["MiniMax-M3", "MiniMax-M2.7"]

    model_ids = [m["id"] for m in CHAT_MODELS]
    assert model_ids == ["MiniMax-M3", "MiniMax-M2.7"]
    assert len(CHAT_MODELS) == 2
    assert CHAT_MODELS[0]["id"] == "MiniMax-M3"
    assert CHAT_MODELS[0]["context_window"] == 1000000
    assert CHAT_MODELS[0]["pricing_usd_per_million_tokens"] == {
        "input": 0.6,
        "output": 2.4,
        "cache_read": 0.12,
        "cache_write": None,
    }
    assert CHAT_MODELS[0]["input_modalities"] == ["text", "image", "video"]
    assert CHAT_MODELS[0]["thinking"] == ["adaptive", "disabled"]
    assert CHAT_MODELS[1]["id"] == "MiniMax-M2.7"
    assert CHAT_MODELS[1]["context_window"] == 204800
    assert CHAT_MODELS[1]["pricing_usd_per_million_tokens"] == {
        "input": 0.3,
        "output": 1.2,
        "cache_read": 0.06,
        "cache_write": 0.375,
    }
    assert CHAT_MODELS[1]["input_modalities"] == ["text"]
    assert CHAT_MODELS[1]["thinking"] == ["always_on"]


def test_regional_endpoints_catalog():
    """The regional endpoint catalog must include global and CN entries."""
    assert REGIONAL_ENDPOINTS == [
        {
            "region": "global_en",
            "openai_base_url": "https://api.minimax.io/v1",
            "anthropic_base_url": "https://api.minimax.io/anthropic",
            "docs_root": "https://platform.minimax.io/docs",
        },
        {
            "region": "cn_zh",
            "openai_base_url": "https://api.minimaxi.com/v1",
            "anthropic_base_url": "https://api.minimaxi.com/anthropic",
            "docs_root": "https://platform.minimaxi.com/docs",
        },
    ]


def test_tts_models_list():
    """The TTS catalog must expose the full speech-2.x model set."""
    assert [m["id"] for m in TTS_MODELS] == MULTIMODAL_CONFIG["speech"]["models"]
    assert len(TTS_MODELS) == 8
    assert TTS_MODELS[0]["id"] == "speech-2.8-hd"
    assert TTS_MODELS[0]["description"] == "High-definition TTS (recommended default)"


def test_tts_voices_list():
    """Verify TTS voices are populated."""
    assert len(TTS_VOICES) > 0
    assert "English_Graceful_Lady" in TTS_VOICES


# ── Chat completion ────────────────────────────────────────────────────────────

def test_chat_completion_success():
    """Test chat completion with mock response."""
    mock_response = {
        "choices": [
            {"message": {"role": "assistant", "content": "Hello! How can I help?"}}
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
            model="MiniMax-M3",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["choices"][0]["message"]["content"] == "Hello! How can I help?"
        assert result["usage"]["total_tokens"] == 22


def test_chat_completion_uses_global_region_base_url():
    """Verify chat completion calls the global OpenAI-compatible endpoint."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_post.return_value = mock_resp

        chat_completion(api_key="key", model="MiniMax-M3", messages=[])

        call_url = mock_post.call_args[0][0]
        assert call_url == "https://api.minimax.io/v1/chat/completions"


def test_chat_completion_uses_cn_region_base_url():
    """Verify chat completion switches to the CN region endpoint."""
    with patch.dict("os.environ", {"MINIMAX_REGION": "cn_zh"}, clear=True):
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            mock_post.return_value = mock_resp

            chat_completion(api_key="key", model="MiniMax-M3", messages=[])

            call_url = mock_post.call_args[0][0]
            assert call_url == "https://api.minimaxi.com/v1/chat/completions"


def test_chat_completion_default_temperature():
    """Temperature defaults to 1.0 (MiniMax requirement)."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_post.return_value = mock_resp

        chat_completion(api_key="key", model="MiniMax-M3", messages=[])

        body = mock_post.call_args[1]["json"]
        assert body["temperature"] == 1.0


def test_chat_completion_error():
    """Test chat completion with error response."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error": "Invalid API key"}'
        mock_resp.raise_for_status.side_effect = requests.HTTPError("HTTP 401")
        mock_post.return_value = mock_resp

        try:
            chat_completion(api_key="invalid-key", messages=[])
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "MiniMax API error" in str(e)


def test_chat_completion_missing_api_key():
    """Missing API key raises RuntimeError."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("cli_anything.minimax.utils.minimax_backend.load_config", return_value={}):
            try:
                chat_completion(api_key=None, messages=[])
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "API key" in str(e)


# ── Streaming ─────────────────────────────────────────────────────────────────

def test_chat_completion_stream_success():
    """Test streaming with mock SSE response."""
    mock_chunks = [
        b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
        b'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
        b"data: [DONE]\n\n",
    ]

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = mock_chunks
        mock_post.return_value = mock_resp

        received = []

        def on_chunk(c):
            received.append(c)

        result = chat_completion_stream(
            api_key="fake-key",
            model="MiniMax-M3",
            messages=[{"role": "user", "content": "Hi"}],
            on_chunk=on_chunk,
        )

        assert result == "Hello world"
        assert received == ["Hello", " world"]


# ── TTS ────────────────────────────────────────────────────────────────────────

def test_tts_synthesize_hex_decoding(tmp_path):
    """TTS audio is hex-encoded and must be decoded correctly."""
    # 'Hello' in hex-encoded fake MP3 bytes
    hex_audio = bytes([0xFF, 0xFB]).hex()  # minimal fake MP3 header

    sse_line = json.dumps(
        {
            "data": {"audio": hex_audio, "status": 2},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = [f"data:{sse_line}\n\n".encode()]
        mock_post.return_value = mock_resp

        out_file = str(tmp_path / "test.mp3")
        audio = tts_synthesize(
            api_key="fake-key",
            text="Hello",
            model="speech-2.8-hd",
            voice="English_Graceful_Lady",
            output_path=out_file,
        )

        assert len(audio) == 2
        assert audio == bytes.fromhex(hex_audio)


def test_tts_synthesize_uses_correct_endpoint():
    """TTS must call the global speech endpoint."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = []
        mock_post.return_value = mock_resp

        tts_synthesize(api_key="key", text="test")

        call_url = mock_post.call_args[0][0]
        assert call_url == "https://api.minimax.io/v1/t2a_v2"


def test_tts_synthesize_uses_cn_region_endpoint():
    """TTS must switch to the CN speech endpoint when requested."""
    with patch.dict("os.environ", {"MINIMAX_REGION": "cn_zh"}, clear=True):
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_content.return_value = []
            mock_post.return_value = mock_resp

            tts_synthesize(api_key="key", text="test")

            call_url = mock_post.call_args[0][0]
            assert call_url == "https://api.minimaxi.com/v1/t2a_v2"


def test_tts_synthesize_api_error():
    """TTS raises RuntimeError on API-level error response."""
    err_sse = json.dumps(
        {"base_resp": {"status_code": 2013, "status_msg": "invalid voice"}}
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = [f"data:{err_sse}\n\n".encode()]
        mock_post.return_value = mock_resp

        try:
            tts_synthesize(api_key="key", text="test")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "invalid voice" in str(e)


# ── Full workflow ──────────────────────────────────────────────────────────────

def test_run_full_workflow():
    """Test full workflow with mock response."""
    mock_response = {
        "choices": [{"message": {"role": "assistant", "content": "Here is the response"}}],
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
            system_message="You are helpful",
        )

        assert result["content"] == "Here is the response"
        assert result["prompt_tokens"] == 10
        assert result["total_tokens"] == 25
