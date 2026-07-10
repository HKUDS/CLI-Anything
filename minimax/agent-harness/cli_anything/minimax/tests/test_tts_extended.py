"""Tests for the extended tts_synthesize parameters (speed / vol / pitch / audio settings).

The new params were previously hardcoded inside tts_synthesize and only the
backend payload used them. These tests guard the new public surface.
"""

import json
from unittest.mock import patch, MagicMock

from cli_anything.minimax.utils.minimax_backend import tts_synthesize


def _empty_sse_post():
    """Build a requests.post mock that returns an empty SSE stream."""
    mock_post = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = lambda: None
    mock_resp.iter_content.return_value = []
    mock_post.return_value = mock_resp
    return mock_post


def _captured_payload(mock_post):
    return mock_post.call_args.kwargs["json"]


def test_tts_default_voice_audio_settings():
    with patch("requests.post", _empty_sse_post()) as mock_post:
        tts_synthesize(api_key="key", text="hi")
        payload = _captured_payload(mock_post)

    assert payload["voice_setting"]["speed"] == 1.0
    assert payload["voice_setting"]["vol"] == 1.0
    assert payload["voice_setting"]["pitch"] == 0
    assert payload["audio_setting"]["sample_rate"] == 32000
    assert payload["audio_setting"]["bitrate"] == 128000
    assert payload["audio_setting"]["format"] == "mp3"
    assert payload["audio_setting"]["channel"] == 1


def test_tts_custom_voice_setting():
    with patch("requests.post", _empty_sse_post()) as mock_post:
        tts_synthesize(api_key="key", text="hi", speed=1.5, vol=3.0, pitch=4)
        payload = _captured_payload(mock_post)

    assert payload["voice_setting"]["speed"] == 1.5
    assert payload["voice_setting"]["vol"] == 3.0
    assert payload["voice_setting"]["pitch"] == 4


def test_tts_custom_audio_setting():
    with patch("requests.post", _empty_sse_post()) as mock_post:
        tts_synthesize(
            api_key="key",
            text="hi",
            sample_rate=44100,
            bitrate=256000,
            audio_format="flac",
            channel=2,
        )
        payload = _captured_payload(mock_post)

    assert payload["audio_setting"]["sample_rate"] == 44100
    assert payload["audio_setting"]["bitrate"] == 256000
    assert payload["audio_setting"]["format"] == "flac"
    assert payload["audio_setting"]["channel"] == 2


def test_tts_voice_id_propagates():
    with patch("requests.post", _empty_sse_post()) as mock_post:
        tts_synthesize(
            api_key="key", text="hi", voice="English_Lucky_Robot", speed=0.8
        )
        payload = _captured_payload(mock_post)

    assert payload["voice_setting"]["voice_id"] == "English_Lucky_Robot"
    assert payload["voice_setting"]["speed"] == 0.8
