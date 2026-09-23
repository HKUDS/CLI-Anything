"""CLI commands, end to end through the provider path against a fake service."""

from __future__ import annotations

import json
import threading
import time
import urllib.request

import pytest
from click.testing import CliRunner

from cli_anything.orcarouter import orcarouter_cli as cli_mod
from cli_anything.orcarouter.core import catalog, credentials, pkce

from .fake_orca import FAKE_ACCOUNT, FAKE_KEY, FakeOrcaRouter

FAKE_KEY_INPUT = "sk-orca-cli-00000000000000000000000000000000000000"


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
def live(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        yield fake


# ── both authentication choices are discoverable and independent ──────────────


def test_help_exposes_both_authentication_choices(runner):
    result = runner.invoke(cli_mod.cli, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.output

    auth_help = runner.invoke(cli_mod.cli, ["auth", "--help"])
    assert auth_help.exit_code == 0
    assert "api-key" in auth_help.output
    assert "login" in auth_help.output


def test_api_key_choice_works_without_any_login(runner, live):
    result = runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])
    assert result.exit_code == 0, result.output
    assert FAKE_KEY_INPUT not in result.output
    assert "sk-orca" in result.output

    status = runner.invoke(cli_mod.cli, ["--json", "auth", "status"])
    payload = json.loads(status.output)
    assert payload["authenticated"] is True
    assert payload["method"] == "api_key"
    assert payload["api_origin"] == live.api_base
    assert payload["auth_origin"] == live.auth_base
    # No PKCE login was started.
    assert live.requests_for("auth") == []


def test_pkce_choice_works_without_a_preexisting_key(runner, live):
    """auth login drives the real connect adapter end to end.

    The CLI blocks on its loopback listener, so the approval is driven from a
    watcher thread that reads the authorization URL the CLI publishes and then
    delivers the redirect to the port the adapter actually bound.
    """
    import cli_anything.orcarouter.core.login_manager as lm

    delivered: dict = {}
    original_begin = lm.LoginManager.begin

    def begin(self, **kwargs):
        attempt = original_begin(self, **kwargs)
        delivered["attempt"] = attempt
        return attempt

    def approve() -> None:
        deadline = time.time() + 8
        while "attempt" not in delivered and time.time() < deadline:
            time.sleep(0.02)
        attempt = delivered.get("attempt")
        if attempt is None:
            return
        consent = live.consent(attempt.authorize_url, approve=True)
        urllib.request.urlopen(consent["callback_url"], timeout=5).read()

    watcher = threading.Thread(target=approve, daemon=True)
    lm.LoginManager.begin = begin
    watcher.start()
    try:
        result = runner.invoke(
            cli_mod.cli, ["auth", "login", "--no-browser", "--timeout", "8"],
            catch_exceptions=False,
        )
    finally:
        lm.LoginManager.begin = original_begin
        watcher.join(timeout=5)

    assert result.exit_code == 0, result.output
    assert delivered["attempt"].authorize_url.startswith(live.auth_base + "/auth?")
    status = json.loads(runner.invoke(cli_mod.cli, ["--json", "auth", "status"]).output)
    assert status["method"] == "oauth_pkce"
    assert status["account_id"] == FAKE_ACCOUNT
    assert status["scope"] == "api"
    assert live.requests_for("auth") == ["/api/v1/auth/keys"]


def test_the_two_choices_are_independently_usable(runner, live):
    # API key only
    runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])
    assert json.loads(runner.invoke(cli_mod.cli, ["--json", "auth", "status"]).output)[
        "method"
    ] == "api_key"
    assert live.requests_for("auth") == []

    # Then switch to account sign-in
    stored = credentials.store_credential(
        pkce.PkceResult(api_key=FAKE_KEY, account_id=FAKE_ACCOUNT, granted_scope="api").to_credential()
    )
    status = json.loads(runner.invoke(cli_mod.cli, ["--json", "auth", "status"]).output)
    assert status["method"] == "oauth_pkce"
    assert status["generation"] == stored.generation


def test_auth_logout_clears_and_reports(runner, live):
    runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])
    result = runner.invoke(cli_mod.cli, ["--json", "auth", "logout"])
    assert json.loads(result.output)["removed"] is True
    assert credentials.resolve_credential() is None
    again = runner.invoke(cli_mod.cli, ["--json", "auth", "logout"])
    assert json.loads(again.output)["removed"] is False


def test_missing_credential_error_names_both_paths(runner):
    result = runner.invoke(cli_mod.cli, ["chat", "--prompt", "hi"])
    assert result.exit_code != 0
    assert "auth api-key" in result.output
    assert "auth login" in result.output


# ── inference through the provider path ───────────────────────────────────────


def test_chat_goes_through_the_configured_api_origin(runner, live):
    runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    result = runner.invoke(cli_mod.cli, ["--json", "chat", "--prompt", "hi"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["content"] == "ok"
    assert "/v1/chat/completions" in live.requests_for("api")
    assert live.requests_for("auth") == [], "inference must never touch the auth origin"


def test_default_model_comes_from_the_catalog(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    result = runner.invoke(cli_mod.cli, ["--json", "chat", "--prompt", "hi"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["model"] in [m["id"] for m in __import__(
        "cli_anything.orcarouter.tests.fake_orca", fromlist=["CATALOG_FIXTURE"]
    ).CATALOG_FIXTURE]


def test_test_command_reports_the_origin_and_model(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    result = runner.invoke(cli_mod.cli, ["--json", "test"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["api_origin"] == live.api_base
    assert payload["response"] == "ok"


def test_chat_with_an_image_uses_a_model_that_declares_image_input(runner, live, tmp_path):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    image = tmp_path / "shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    result = runner.invoke(
        cli_mod.cli, ["--json", "chat", "--prompt", "what is this?", "--image", str(image)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["model"] == "google/gemini-3.5-flash"


def test_an_image_with_an_incompatible_model_is_refused_before_sending(runner, live, tmp_path):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    image = tmp_path / "shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    # (catalog discovery may run; the completion must not)
    result = runner.invoke(
        cli_mod.cli,
        ["--json", "chat", "--prompt", "what is this?", "--image", str(image),
         "--model", "openai/gpt-5.5"],
    )
    assert result.exit_code != 0
    assert "unsupported_modality" in result.output or "does not declare" in result.output
    # Catalog discovery is allowed; the completion itself must never be sent.
    assert not any(path.endswith("/chat/completions") for path in live.requests_for("api"))


# ── catalog commands ──────────────────────────────────────────────────────────


def test_models_command_lists_only_compatible_models(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    result = runner.invoke(cli_mod.cli, ["--json", "models"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["catalog_source"] == "live"
    ids = [m["id"] for m in payload["models"]]
    assert "openai/gpt-image-1" not in ids
    assert "orcarouter/auto" in ids


def test_models_command_multimodal_filter(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    result = runner.invoke(cli_mod.cli, ["--json", "models", "--modalities", "image"])
    payload = json.loads(result.output)
    assert [m["id"] for m in payload["models"]] == ["google/gemini-3.5-flash"]
    assert payload["required_modalities"] == ["image"]


def test_models_command_capability_filter(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    for capability, expected in (
        ("embedding", "openai/text-embedding-3-large"),
        ("image", "openai/gpt-image-1"),
        ("video", "orcarouter/video-preview"),
        ("rerank", "jina/jina-reranker-v3"),
    ):
        result = runner.invoke(cli_mod.cli, ["--json", "models", "--capability", capability])
        assert [m["id"] for m in json.loads(result.output)["models"]] == [expected]


def test_models_command_reports_degraded_without_credentials(runner):
    result = runner.invoke(cli_mod.cli, ["--json", "models"])
    payload = json.loads(result.output)
    assert payload["degraded"] is True
    assert payload["catalog_source"] == "seed"
    assert [m["id"] for m in payload["models"]] == [
        "openai/gpt-5.5",
        "anthropic/claude-opus-4.8",
        "google/gemini-3.5-flash",
        "deepseek/deepseek-v4-pro",
        "orcarouter/auto",
    ]


def test_catalog_command_shows_provenance_and_reasoning(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    result = runner.invoke(cli_mod.cli, ["--json", "catalog"])
    payload = json.loads(result.output)
    assert payload["source"] == "live"
    assert payload["catalog_url"] == f"{live.api_base}/models"
    assert payload["reasoning_efforts"]["openai/gpt-5.5"] == ["low", "medium", "high", "xhigh"]


# ── config ────────────────────────────────────────────────────────────────────


def test_config_show_masks_the_stored_key(runner, live):
    runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])
    result = runner.invoke(cli_mod.cli, ["--json", "config", "show"])
    assert FAKE_KEY_INPUT not in result.output
    assert "sk-orca" in result.output

    path = runner.invoke(cli_mod.cli, ["--json", "config", "path"])
    assert str(credentials.CONFIG_FILE) in path.output


def test_no_command_output_ever_contains_the_stored_key(runner, live, tmp_path):
    image = tmp_path / "shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    runner.invoke(cli_mod.cli, ["auth", "api-key", "--api-key", FAKE_KEY_INPUT])

    outputs = []
    for argv in (
        ["auth", "status"], ["config", "show"], ["config", "path"], ["models"], ["catalog"],
        ["test"], ["chat", "--prompt", "hi"], ["stream", "--prompt", "hi"],
        ["chat", "--prompt", "hi", "--image", str(image)],
    ):
        outputs.append(runner.invoke(cli_mod.cli, ["--json"] + argv).output)
        outputs.append(runner.invoke(cli_mod.cli, argv).output)
    for text in outputs:
        assert FAKE_KEY_INPUT not in text


# ── origin discipline ─────────────────────────────────────────────────────────


def test_auth_and_api_origins_are_independent(runner, live):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    runner.invoke(cli_mod.cli, ["--json", "chat", "--prompt", "hi"])
    assert live.requests_for("auth") == []
    assert any(path.endswith("/chat/completions") for path in live.requests_for("api"))


def test_default_origins_are_never_derived_from_each_other(monkeypatch):
    for var in ("ORCA_BASE_URL", "ORCA_AUTH_BASE_URL", "ORCA_API_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    assert credentials.auth_base_url() == "https://www.orcarouter.ai"
    assert credentials.api_base_url() == "https://api.orcarouter.ai/v1"
    assert "api.orcarouter.ai" not in credentials.exchange_url()
    assert "www.orcarouter.ai" not in credentials.api_base_url()
