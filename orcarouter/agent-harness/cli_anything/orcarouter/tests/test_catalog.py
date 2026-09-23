"""Model catalog: discovery, capability filters, fail-closed multimodal, fallback."""

from __future__ import annotations

import json
import urllib.error

import pytest

from cli_anything.orcarouter.core import catalog, credentials, provider

from .fake_orca import CATALOG_FIXTURE, FAKE_KEY, FakeOrcaRouter

CRED = credentials.Credential(
    api_key=FAKE_KEY, method=credentials.METHOD_API_KEY, source=credentials.SOURCE_CLI
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCAROUTER_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(credentials.ENV_API_KEY, raising=False)
    monkeypatch.setattr(credentials, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(credentials, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    yield


# ── live discovery ────────────────────────────────────────────────────────────


def test_options_come_from_the_api_not_a_hand_written_list(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        live = catalog.fetch_live_catalog(CRED)
        assert live.source == catalog.CATALOG_SOURCE_LIVE
        assert live.degraded is False
        assert live.ids() == [m["id"] for m in CATALOG_FIXTURE]
        assert fake.requests_for("api") == ["/v1/models"]


def test_vendor_namespace_is_preserved_verbatim(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        live = catalog.fetch_live_catalog(CRED)
        assert "deepseek/deepseek-v4-pro" in live.ids()
        assert "orcarouter/auto" in live.ids()
        assert all("/" in model_id for model_id in live.ids())


def test_discovery_sends_bearer_auth_and_targets_the_api_origin(monkeypatch):
    seen: dict = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, *args):
            return json.dumps({"data": CATALOG_FIXTURE}).encode("utf-8")

    def opener(request, timeout=None):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        return Response()

    monkeypatch.delenv("ORCA_API_BASE_URL", raising=False)
    monkeypatch.delenv("ORCA_BASE_URL", raising=False)
    catalog.fetch_live_catalog(CRED, opener=opener)
    assert seen["url"] == "https://api.orcarouter.ai/v1/models"
    assert seen["auth"] == f"Bearer {FAKE_KEY}"
    assert seen["timeout"] == catalog.CATALOG_TIMEOUT


def test_capability_query_parameter_is_forwarded(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        embedding = catalog.fetch_live_catalog(CRED, capability="embedding")
        assert embedding.ids() == ["openai/text-embedding-3-large"]


def test_metadata_is_preserved_including_the_reasoning_ladder(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        live = catalog.fetch_live_catalog(CRED)
        gpt = live.get("openai/gpt-5.5")
        assert gpt is not None
        assert gpt.context_length == 400000
        assert gpt.reasoning_efforts == ("low", "medium", "high", "xhigh")
        assert gpt.input_modalities == ("text",)


def test_discovery_is_bounded(monkeypatch):
    payload = json.dumps({"data": CATALOG_FIXTURE}).encode("utf-8")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, amount=None):
            return payload[: amount] if amount else payload

    def opener(request, timeout=None):
        return Response()

    monkeypatch.setenv("ORCA_API_BASE_URL", "https://api.orcarouter.ai/v1")
    live = catalog.fetch_live_catalog(CRED, opener=opener)
    assert len(live.models) <= catalog.MAX_ITEMS


def test_oversized_response_is_refused(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, amount=None):
            return b"x" * (catalog.MAX_RESPONSE_BYTES + 1)

    with pytest.raises(catalog.CatalogError):
        catalog.fetch_live_catalog(CRED, opener=lambda request, timeout=None: Response())


def test_malformed_records_are_dropped(monkeypatch):
    payload = {
        "data": [
            {"id": "vendor/ok", "supported_endpoint_types": ["openai"]},
            {"no_id": True},
            "not-a-dict",
            {"id": ""},
            {"id": "vendor/second", "context_length": "not-a-number"},
        ]
    }
    parsed = catalog.parse_catalog_payload(payload)
    assert [m.id for m in parsed] == ["vendor/ok", "vendor/second"]
    assert parsed[1].context_length == 0


# ── capability filters ────────────────────────────────────────────────────────


def _fixture_catalog() -> catalog.Catalog:
    return catalog.Catalog(models=catalog.parse_catalog_payload({"data": CATALOG_FIXTURE}))


def test_chat_filter_excludes_non_text_models():
    live = _fixture_catalog()
    ids = [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_CHAT)]
    assert "openai/gpt-image-1" not in ids
    assert "orcarouter/video-preview" not in ids
    assert "jina/jina-reranker-v3" not in ids
    assert "openai/text-embedding-3-large" not in ids
    assert "audio/whisper-large-v3" not in ids
    assert "openai/gpt-5.5" in ids


def test_chat_filter_accepts_every_supported_endpoint_type():
    live = _fixture_catalog()
    ids = [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_CHAT)]
    for expected in (
        "anthropic/claude-opus-4.8",  # anthropic
        "google/gemini-3.5-flash",    # gemini
        "deepseek/deepseek-v4-pro",   # openai
        "orcarouter/auto",            # openai-response
    ):
        assert expected in ids


def test_multimodal_filter_is_fail_closed():
    live = _fixture_catalog()
    text_only = [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_CHAT)]
    with_image = [
        m.id
        for m in catalog.selectable_models(
            live, catalog.CAPABILITY_CHAT, required_modalities=("image",)
        )
    ]
    assert with_image == ["google/gemini-3.5-flash"]
    assert set(with_image) < set(text_only), "adding an image must only remove options"
    assert "openai/gpt-5.5" not in with_image, "an undeclared modality must not be assumed"


def test_embedding_image_video_rerank_filters():
    live = _fixture_catalog()
    assert [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_EMBEDDING)] == [
        "openai/text-embedding-3-large"
    ]
    assert [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_IMAGE)] == [
        "openai/gpt-image-1"
    ]
    assert [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_VIDEO)] == [
        "orcarouter/video-preview"
    ]
    assert [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_RERANK)] == [
        "jina/jina-reranker-v3"
    ]


def test_unknown_capability_is_refused():
    with pytest.raises(ValueError):
        catalog.selectable_models(_fixture_catalog(), "telepathy")


def test_capability_is_never_inferred_from_the_model_name():
    """A model named like an image model but with no image endpoint is not offered."""
    payload = {
        "data": [
            {
                "id": "vendor/super-image-generator",
                "supported_endpoint_types": ["openai"],
                "architecture": {"input_modalities": ["text"]},
            }
        ]
    }
    live = catalog.Catalog(models=catalog.parse_catalog_payload(payload))
    assert [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_IMAGE)] == []
    assert [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_CHAT)] == [
        "vendor/super-image-generator"
    ]


# ── stale selection ───────────────────────────────────────────────────────────


def test_selected_model_is_cleared_when_it_stops_being_compatible():
    live = _fixture_catalog()
    selected = "openai/gpt-5.5"
    assert catalog.is_still_valid(live, selected, catalog.CAPABILITY_CHAT)
    assert not catalog.is_still_valid(
        live, selected, catalog.CAPABILITY_CHAT, required_modalities=("image",)
    )
    assert not catalog.is_still_valid(live, "", catalog.CAPABILITY_CHAT)


# ── fallback seed ─────────────────────────────────────────────────────────────


def test_live_failure_falls_back_to_the_verified_seed(monkeypatch):
    monkeypatch.setenv("ORCA_API_BASE_URL", "https://api.orcarouter.ai/v1")

    def opener(request, timeout=None):
        raise urllib.error.URLError("offline")

    result = catalog.load_catalog(CRED, opener=opener)
    assert result.source == catalog.CATALOG_SOURCE_SEED
    assert result.degraded is True
    assert result.ids() == [
        "openai/gpt-5.5",
        "anthropic/claude-opus-4.8",
        "google/gemini-3.5-flash",
        "deepseek/deepseek-v4-pro",
        "orcarouter/auto",
    ]


def test_seed_keeps_its_verified_metadata():
    seed = catalog.seed_catalog("offline")
    gpt = seed.get("openai/gpt-5.5")
    assert gpt.reasoning_efforts == ("low", "medium", "high", "xhigh")
    assert gpt.context_length == 400000
    assert gpt.input_modalities == ("text",)


def test_seed_is_never_mixed_into_a_successful_live_result(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        live = catalog.load_catalog(CRED)
        assert live.source == catalog.CATALOG_SOURCE_LIVE
        assert "openai/gpt-5.5" in live.ids()  # present in the fake live catalog
        # A seed-only model must not appear when the live catalog did not list it.
        assert "anthropic/claude-opus-4.8" in live.ids()


def test_seed_only_models_do_not_leak_into_a_partial_live_catalog(monkeypatch):
    payload = {"data": [{"id": "vendor/only-one", "supported_endpoint_types": ["openai"]}]}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, amount=None):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setenv("ORCA_API_BASE_URL", "https://api.orcarouter.ai/v1")
    live = catalog.load_catalog(CRED, opener=lambda request, timeout=None: Response())
    assert live.source == catalog.CATALOG_SOURCE_LIVE
    assert live.ids() == ["vendor/only-one"]


def test_no_credential_still_offers_the_verified_seed():
    result = catalog.load_catalog(None)
    assert result.source == catalog.CATALOG_SOURCE_SEED
    assert result.degraded is True
    assert "orcarouter/auto" in result.ids()


def test_public_view_never_contains_credentials():
    payload = catalog.seed_catalog("offline").to_public_dict()
    assert FAKE_KEY not in json.dumps(payload)
    assert "pricing" not in json.dumps(payload)


# ── provider integration ──────────────────────────────────────────────────────


def test_discover_selectable_filters_the_live_catalog(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        chat = provider.discover_selectable(CRED)
        assert "openai/gpt-image-1" not in chat.ids()

        with_image = provider.discover_selectable(CRED, required_modalities=("image",))
        assert with_image.ids() == ["google/gemini-3.5-flash"]


def test_modality_guard_blocks_an_incompatible_model():
    live = _fixture_catalog()
    provider.guard_model_for_modalities(live, "google/gemini-3.5-flash", ("image",))
    with pytest.raises(provider.ProviderError) as excinfo:
        provider.guard_model_for_modalities(live, "openai/gpt-5.5", ("image",))
    assert excinfo.value.kind == "unsupported_modality"


def test_modality_guard_rejects_a_model_outside_the_catalog():
    with pytest.raises(provider.ProviderError) as excinfo:
        provider.guard_model_for_modalities(_fixture_catalog(), "vendor/ghost", ("image",))
    assert excinfo.value.kind == "model_not_in_catalog"


def test_build_messages_reports_the_uploaded_modality(tmp_path):
    image = tmp_path / "shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    messages, required = provider.build_messages(prompt="what is this?", image_paths=[str(image)])
    assert required == ("image",)
    assert messages[0]["role"] == "user"
    parts = messages[0]["content"]
    assert parts[0]["type"] == "text"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")

    plain, none_required = provider.build_messages(prompt="hi")
    assert none_required == ()
    assert plain[0]["content"] == "hi"


def test_build_messages_rejects_a_missing_attachment():
    with pytest.raises(provider.ProviderError) as excinfo:
        provider.build_messages(prompt="hi", image_paths=["/nonexistent/shot.png"])
    assert excinfo.value.kind == "bad_attachment"
