"""End-to-end tests: both authentication choices through the real provider path.

Unlike the unit tests, these drive the whole harness over real loopback HTTP
against ``fake_orca.FakeOrcaRouter`` — a real consent screen, a real PKCE
exchange, a real relay — so a break anywhere between the CLI, the credential
seam, the catalog and the provider shows up here.

When ``ORCAROUTER_API_KEY`` is present, one test additionally performs a real
request against the live OrcaRouter service through the same code path. Without
it, that test is skipped rather than faked.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request

import pytest
from click.testing import CliRunner

from cli_anything.orcarouter import orcarouter_cli as cli_mod
from cli_anything.orcarouter.core import catalog, credentials, login_manager, pkce, provider

from .fake_orca import FAKE_ACCOUNT, FAKE_KEY, FakeOrcaRouter

# Captured before any fixture can clear the environment, so the live check can
# use a real credential without weakening the isolation the other tests rely on.
LIVE_KEY = os.environ.get("ORCAROUTER_API_KEY", "").strip()

FAKE_KEY_INPUT = "sk-orca-e2e-00000000000000000000000000000000000000"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCAROUTER_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(credentials.ENV_API_KEY, raising=False)
    monkeypatch.setattr(credentials, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(credentials, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    yield


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def service(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        yield fake


# ── API-key choice, end to end ────────────────────────────────────────────────


def test_api_key_sign_in_then_chat_and_models(runner, monkeypatch):
    """Store a key, then use it for discovery and inference over real HTTP."""
    with FakeOrcaRouter(issue_key=FAKE_KEY_INPUT) as service:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", service.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", service.api_base)

        saved = runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])
        assert saved.exit_code == 0, saved.output
        assert FAKE_KEY_INPUT not in saved.output

        credential = credentials.require_credential()
        assert credential.method == credentials.METHOD_API_KEY
        assert credential.source == credentials.SOURCE_STORED

        models = runner.invoke(cli_mod.cli, ["--json", "models"])
        assert models.exit_code == 0, models.output
        payload = json.loads(models.output)
        assert payload["catalog_source"] == catalog.CATALOG_SOURCE_LIVE
        assert payload["count"] > 0

        chat = runner.invoke(
            cli_mod.cli, ["--json", "chat", "-p", "hi", "--model", "openai/gpt-5.5"]
        )
        assert chat.exit_code == 0, chat.output
        assert json.loads(chat.output)["content"] == "ok"
        assert service.requests_for("api").count("/v1/chat/completions") == 1
        # The API-key choice never touches the authorization origin.
        assert service.requests_for("auth") == []


# ── PKCE choice, end to end ───────────────────────────────────────────────────


def test_pkce_sign_in_then_chat_uses_the_same_provider_path(runner, service, monkeypatch):
    """authorize -> loopback callback -> exchange -> stored key -> chat."""
    manager = login_manager.LoginManager()
    seen: dict = {}

    def drive(url: str) -> None:
        seen["url"] = url
        result = service.consent(url, approve=True)
        urllib.request.urlopen(result["callback_url"], timeout=5).read()

    def run() -> None:
        seen["result"] = login_manager.run_login(
            manager, timeout=10, open_browser=False, on_prompt=drive
        )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=15)

    assert "url" in seen, "the login never produced an authorization URL"
    assert seen["url"].startswith(service.auth_base + "/auth?")
    assert seen["result"].api_key == FAKE_KEY
    assert seen["result"].account_id == FAKE_ACCOUNT

    # The PKCE result persists through the same seam the pasted key uses.
    credentials.store_credential(seen["result"].to_credential())
    credential = credentials.require_credential()
    assert credential.method == credentials.METHOD_OAUTH_PKCE
    assert credential.api_key == FAKE_KEY

    chat = runner.invoke(cli_mod.cli, ["--json", "chat", "-p", "hi", "--model", "openai/gpt-5.5"])
    assert chat.exit_code == 0, chat.output
    assert json.loads(chat.output)["content"] == "ok"


def test_both_choices_produce_a_credential_the_provider_cannot_tell_apart(runner, service):
    """The provider path is identical whichever choice produced the key."""
    pasted = credentials.Credential(
        api_key=FAKE_KEY, method=credentials.METHOD_API_KEY, source=credentials.SOURCE_STORED
    )
    connected = pkce.PkceResult(
        api_key=FAKE_KEY, account_id=FAKE_ACCOUNT, granted_scope="api", requested_scope="api"
    ).to_credential()

    assert pasted.method != connected.method
    first = provider.chat_completion(
        pasted, model="openai/gpt-5.5", messages=[{"role": "user", "content": "hi"}]
    )
    second = provider.chat_completion(
        connected, model="openai/gpt-5.5", messages=[{"role": "user", "content": "hi"}]
    )
    assert first.content == second.content == "ok"


# ── capability filtering over the wire ────────────────────────────────────────


def test_multimodal_selector_over_the_wire_keeps_only_image_models(service):
    credential = credentials.require_credential(cli_key=FAKE_KEY_INPUT)
    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)

    text_ids = [m.id for m in catalog.selectable_models(live, catalog.CAPABILITY_CHAT)]
    image_ids = [
        m.id
        for m in catalog.selectable_models(
            live, catalog.CAPABILITY_CHAT, required_modalities=("image",)
        )
    ]
    assert "openai/gpt-5.5" in text_ids
    assert "google/gemini-3.5-flash" in text_ids
    assert image_ids == ["google/gemini-3.5-flash"]


def test_unknown_credential_is_rejected_by_the_relay(service):
    credential = credentials.Credential(
        api_key="sk-orca-e2e-wrong-0000000000000000000000000000000",
        method=credentials.METHOD_API_KEY,
        source=credentials.SOURCE_CLI,
    )
    with pytest.raises(provider.ProviderError) as excinfo:
        provider.chat_completion(
            credential, model="openai/gpt-5.5", messages=[{"role": "user", "content": "hi"}]
        )
    assert excinfo.value.status == 401
    assert credential.api_key not in str(excinfo.value)


# ── live service (opt-in) ─────────────────────────────────────────────────────


@pytest.mark.skipif(
    not LIVE_KEY,
    reason="ORCAROUTER_API_KEY is required for the live end-to-end check",
)
def test_live_catalog_and_inference_through_the_provider_path(monkeypatch):
    """A real request through the shipped code path, when a key is configured."""
    monkeypatch.setenv(credentials.ENV_API_KEY, LIVE_KEY)
    credential = credentials.resolve_credential()
    assert credential is not None

    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)
    assert live.source == catalog.CATALOG_SOURCE_LIVE
    options = catalog.selectable_models(live, catalog.CAPABILITY_CHAT)
    assert options, "the live catalog returned no chat models"

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
