"""Live checks for the OrcaRouter provider, run through the harness's own code path.

Unlike a bare ``curl``, every assertion here goes through the modules the
harness ships: ``core.credentials`` resolves the credential,
``core.catalog`` fetches and filters the model catalog, and
``core.provider`` performs the inference request. If the provider wiring is
broken, this test fails.

It proves four things:

1. The real credential resolves and the live catalog is reachable at
   ``https://api.orcarouter.ai/v1/models`` (not a seed, not a fallback).
2. The text selector (``capability=chat``) is non-empty and contains only chat
   models — no image-generation, video, rerank or embedding-only entries.
3. The multimodal selector (``capability=chat``, ``required_modalities=image``)
   contains only chat models whose catalog metadata explicitly declares image
   input, and is a strict subset of the text selector.
4. One real chat completion succeeds through ``provider.chat_completion`` and
   returns non-empty content.

The API key is read from ``ORCAROUTER_API_KEY`` and is never printed. Run from
the repository root:

    ORCAROUTER_API_KEY=sk-orca-… python3 -m pytest orcarouter/agent-harness/tools/test_live_provider.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = REPO_ROOT / "orcarouter" / "agent-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from cli_anything.orcarouter.core import catalog, credentials, provider  # noqa: E402

LIVE_KEY = __import__("os").environ.get("ORCAROUTER_API_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not LIVE_KEY,
    reason="ORCAROUTER_API_KEY is required for the live provider checks",
)


def test_credential_and_origins():
    credential = credentials.resolve_credential()
    assert credential is not None, "no credential — set ORCAROUTER_API_KEY"
    assert credential.method == credentials.METHOD_API_KEY
    assert credentials.api_base_url().startswith("https://")
    assert "www.orcarouter.ai" not in credentials.api_base_url()
    assert credentials.auth_base_url() != credentials.api_base_url()


def test_live_catalog_reaches_the_inference_origin():
    credential = credentials.require_credential()
    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)
    assert live.source == catalog.CATALOG_SOURCE_LIVE
    assert live.models, "the live catalog returned no models"


def test_text_selector_only_offers_chat_models():
    credential = credentials.require_credential()
    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)
    options = catalog.selectable_models(live, catalog.CAPABILITY_CHAT)
    assert options, "the text selector is empty"
    assert all(m.supports_endpoint(catalog.CHAT_ENDPOINT_TYPES) for m in options)
    assert all(
        not m.supports_endpoint(catalog.NON_CHAT_ENDPOINT_TYPES)
        or m.supports_endpoint(catalog.CHAT_ENDPOINT_TYPES)
        for m in options
    )


def test_multimodal_selector_is_a_strict_fail_closed_subset():
    credential = credentials.require_credential()
    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)
    text_options = catalog.selectable_models(live, catalog.CAPABILITY_CHAT)
    image_options = catalog.selectable_models(
        live, catalog.CAPABILITY_CHAT, required_modalities=("image",)
    )
    assert image_options, "the multimodal selector is empty"
    assert all("image" in m.input_modalities for m in image_options)
    assert {m.id for m in image_options} <= {m.id for m in text_options}
    assert len(image_options) < len(text_options)


def test_real_chat_completion_through_the_provider():
    credential = credentials.require_credential()
    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)
    options = catalog.selectable_models(live, catalog.CAPABILITY_CHAT)
    assert options

    # A gateway key is entitled to a subset of the routed models; `orcarouter/*`
    # router aliases may be restricted per key. Use the verified seed model,
    # which is a plain routed vendor model, and fall back to the first option.
    preferred = next(
        (m for m in options if m.id == "deepseek/deepseek-v4-pro"),
        next((m for m in options if not m.id.startswith("orcarouter/")), options[0]),
    )
    result = provider.chat_completion(
        credential,
        model=preferred.id,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=16,
    )
    assert result.content.strip()
    assert credential.api_key not in result.content
