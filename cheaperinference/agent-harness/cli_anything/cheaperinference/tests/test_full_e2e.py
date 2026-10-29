"""E2E tests for Cheaper Inference CLI - requires CHEAPER_INFERENCE_API_KEY."""

import os

import pytest

from cli_anything.cheaperinference.utils.cheaperinference_backend import (
    DEFAULT_MODEL,
    chat_completion,
    chat_completion_stream,
    list_models,
)

API_KEY = os.environ.get("CHEAPER_INFERENCE_API_KEY")

pytestmark = pytest.mark.skipif(
    not API_KEY, reason="CHEAPER_INFERENCE_API_KEY is not set"
)


def test_chat_completion_e2e():
    """Test chat completion with the real API."""
    result = chat_completion(
        api_key=API_KEY,
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": "Say 'ok'"}],
        max_tokens=16,
    )

    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "content" in result["choices"][0]["message"]


def test_chat_stream_e2e():
    """Test streaming chat with the real API."""
    chunks = []

    full_response = chat_completion_stream(
        api_key=API_KEY,
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": "Say 'ok'"}],
        max_tokens=16,
        on_chunk=chunks.append,
    )

    assert full_response == "".join(chunks)


def test_list_models_e2e():
    """Test listing models with the real API."""
    models = list_models(API_KEY)

    assert len(models) > 0
    assert any(m.get("id") == DEFAULT_MODEL for m in models)
