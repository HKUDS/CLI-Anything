"""E2E tests for MiniMax CLI — uses real API when MINIMAX_API_KEY is set."""

import os
import json
from unittest.mock import patch, MagicMock

from cli_anything.minimax.utils.minimax_backend import (
    chat_completion,
    chat_completion_stream,
    tts_synthesize,
)

API_KEY = os.environ.get("MINIMAX_API_KEY")


# ── Chat ───────────────────────────────────────────────────────────────────────

def test_chat_completion_e2e():
    """Test chat completion — real API if key present, otherwise mock."""
    if not API_KEY:
        mock_response = {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            result = chat_completion(
                api_key="sk-mock",
                model="MiniMax-M2.7",
                messages=[{"role": "user", "content": "Say ok"}],
            )
            assert result["choices"][0]["message"]["content"] == "ok"
        return

    result = chat_completion(
        api_key=API_KEY,
        model="MiniMax-M2.7",
        messages=[{"role": "user", "content": "Say 'ok'"}],
        max_tokens=10,
    )
    assert "choices" in result
    assert result["choices"][0]["message"]["content"]


def test_chat_completion_highspeed_model_e2e():
    """Test MiniMax-M2.7-highspeed model."""
    if not API_KEY:
        mock_response = {
            "choices": [{"message": {"role": "assistant", "content": "done"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            result = chat_completion(
                api_key="sk-mock",
                model="MiniMax-M2.7-highspeed",
                messages=[{"role": "user", "content": "Say done"}],
            )
            body = mock_post.call_args[1]["json"]
            assert body["model"] == "MiniMax-M2.7-highspeed"
            assert result["choices"][0]["message"]["content"] == "done"
        return

    result = chat_completion(
        api_key=API_KEY,
        model="MiniMax-M2.7-highspeed",
        messages=[{"role": "user", "content": "Say 'done'"}],
        max_tokens=10,
    )
    assert "choices" in result
    assert result["choices"][0]["message"]["content"]


def test_chat_stream_e2e():
    """Test streaming chat."""
    if not API_KEY:
        mock_chunks = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b'data: {"choices": [{"delta": {"content": "!"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_lines.return_value = mock_chunks
            mock_post.return_value = mock_resp

            full = ""

            def on_chunk(c):
                nonlocal full
                full += c

            chat_completion_stream(
                api_key="sk-mock",
                model="MiniMax-M2.7",
                messages=[{"role": "user", "content": "Hello"}],
                on_chunk=on_chunk,
            )
            assert full == "Hello!"
        return

    # Real streaming test
    received = []
    chat_completion_stream(
        api_key=API_KEY,
        model="MiniMax-M2.7",
        messages=[{"role": "user", "content": "Say 'ok' only"}],
        max_tokens=5,
        on_chunk=lambda c: received.append(c),
    )
    assert len(received) > 0


# ── TTS ────────────────────────────────────────────────────────────────────────

def test_tts_e2e(tmp_path):
    """Test TTS synthesis."""
    if not API_KEY:
        hex_audio = bytes([0xFF, 0xFB, 0x00]).hex()
        sse_line = json.dumps({
            "data": {"audio": hex_audio, "status": 2},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_content.return_value = [f"data:{sse_line}\n\n".encode()]
            mock_post.return_value = mock_resp

            out = str(tmp_path / "test.mp3")
            audio = tts_synthesize(
                api_key="sk-mock",
                text="Hello world",
                model="speech-2.8-hd",
                voice="English_Graceful_Lady",
                output_path=out,
            )
            assert len(audio) == 3
        return

    out = str(tmp_path / "real.mp3")
    audio = tts_synthesize(
        api_key=API_KEY,
        text="Hello, this is a test.",
        model="speech-2.8-hd",
        voice="English_Graceful_Lady",
        output_path=out,
    )
    assert len(audio) > 100, "Expected non-trivial audio output"
