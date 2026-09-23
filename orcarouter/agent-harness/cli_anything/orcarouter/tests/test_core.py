"""Credential seam: both authentication adapters, storage, redaction, 401 recovery."""

from __future__ import annotations

import io
import json
import os
import stat
import urllib.error

import pytest

from cli_anything.orcarouter.core import catalog, credentials, provider, pkce


FAKE_KEY = "sk-orca-unit-00000000000000000000000000000000000000"
FAKE_KEY_2 = "sk-orca-unit-11111111111111111111111111111111111111"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets its own config dir; no environment leaks between tests."""
    monkeypatch.setenv("ORCAROUTER_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(credentials.ENV_API_KEY, raising=False)
    monkeypatch.setattr(
        credentials, "CONFIG_DIR", tmp_path / "cfg"
    )
    monkeypatch.setattr(
        credentials, "CONFIG_FILE", tmp_path / "cfg" / "config.json"
    )
    yield


# ── the seam ──────────────────────────────────────────────────────────────────


def test_api_key_adapter_and_pkce_adapter_produce_the_same_credential_shape():
    """Both adapters end at one credential type, differing only in `method`."""
    from_api_key = credentials.Credential(
        api_key=FAKE_KEY, method=credentials.METHOD_API_KEY, source=credentials.SOURCE_STORED
    )
    from_pkce = pkce.PkceResult(
        api_key=FAKE_KEY_2, account_id="12345", granted_scope="api"
    ).to_credential()

    assert from_api_key.method == credentials.METHOD_API_KEY
    assert from_pkce.method == credentials.METHOD_OAUTH_PKCE
    assert type(from_api_key) is type(from_pkce)
    assert set(from_api_key.public_dict()) == set(from_pkce.public_dict())
    # The downstream provider takes the same object type and never branches on method.
    assert from_api_key.api_key != from_pkce.api_key


def test_provider_does_not_care_which_adapter_produced_the_credential():
    api_key_cred = credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                                          source=credentials.SOURCE_STORED)
    pkce_cred = credentials.Credential(api_key=FAKE_KEY_2, method=credentials.METHOD_OAUTH_PKCE,
                                       source=credentials.SOURCE_STORED)

    def headers_for(credential):
        request = provider._request_for(credential, "/chat/completions", b"{}")
        return request.get_header("Authorization")

    # Same shape, same code path; only the secret differs.
    assert headers_for(api_key_cred) == f"Bearer {FAKE_KEY}"
    assert headers_for(pkce_cred) == f"Bearer {FAKE_KEY_2}"
    assert provider.chat_completion.__code__.co_names.count("method") == 0


# ── storage, read, clear, masking ─────────────────────────────────────────────


def test_store_read_clear_roundtrip():
    assert credentials.resolve_credential() is None

    stored = credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    assert stored.generation == 1

    resolved = credentials.resolve_credential()
    assert resolved is not None
    assert resolved.api_key == FAKE_KEY
    assert resolved.method == credentials.METHOD_API_KEY
    assert resolved.source == credentials.SOURCE_STORED

    assert credentials.clear_credential() is True
    assert credentials.resolve_credential() is None
    assert credentials.clear_credential() is False


def test_config_file_is_not_world_readable():
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    mode = stat.S_IMODE(os.stat(credentials.CONFIG_FILE).st_mode)
    assert mode == 0o600, oct(mode)


def test_resolution_priority_cli_then_env_then_stored(monkeypatch):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    assert credentials.resolve_credential().source == credentials.SOURCE_STORED

    monkeypatch.setenv(credentials.ENV_API_KEY, FAKE_KEY_2)
    assert credentials.resolve_credential().source == credentials.SOURCE_ENV

    assert credentials.resolve_credential(FAKE_KEY).source == credentials.SOURCE_CLI


def test_masking_never_reveals_the_whole_secret():
    masked = credentials.mask_secret(FAKE_KEY)
    assert masked != FAKE_KEY
    assert FAKE_KEY not in masked
    assert masked.startswith("sk-orca")
    assert credentials.mask_secret("short") == "*****"
    assert credentials.mask_secret("") == ""


def test_stored_key_is_never_exposed_by_the_public_view():
    stored = credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    assert FAKE_KEY not in json.dumps(stored.public_dict())


def test_format_check_rejects_obvious_mistakes():
    credentials.validate_api_key_format(FAKE_KEY)
    with pytest.raises(ValueError):
        credentials.validate_api_key_format("")
    with pytest.raises(ValueError):
        credentials.validate_api_key_format("sk-other-provider-0000000000000000")
    with pytest.raises(ValueError):
        credentials.validate_api_key_format("sk-orca-")


# ── origins ───────────────────────────────────────────────────────────────────


def test_default_origins_are_the_two_public_hosts(monkeypatch):
    for var in ("ORCA_BASE_URL", "ORCA_AUTH_BASE_URL", "ORCA_API_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    assert credentials.auth_base_url() == "https://www.orcarouter.ai"
    assert credentials.api_base_url() == "https://api.orcarouter.ai/v1"
    assert credentials.authorize_url() == "https://www.orcarouter.ai/auth"
    assert credentials.exchange_url() == "https://www.orcarouter.ai/api/v1/auth/keys"
    # The auth API is not under the relay's /v1 prefix.
    assert not credentials.exchange_url().startswith("https://api.orcarouter.ai")


def test_shared_base_url_override(monkeypatch):
    monkeypatch.setenv("ORCA_BASE_URL", "https://orca.internal.example")
    assert credentials.auth_base_url() == "https://orca.internal.example"
    assert credentials.api_base_url() == "https://orca.internal.example/v1"


def test_explicit_overrides_win_over_the_shared_base(monkeypatch):
    monkeypatch.setenv("ORCA_BASE_URL", "https://shared.example")
    monkeypatch.setenv("ORCA_AUTH_BASE_URL", "https://auth.example")
    monkeypatch.setenv("ORCA_API_BASE_URL", "https://relay.example/v1")
    assert credentials.auth_base_url() == "https://auth.example"
    assert credentials.api_base_url() == "https://relay.example/v1"


def test_non_loopback_http_is_refused(monkeypatch):
    monkeypatch.setenv("ORCA_AUTH_BASE_URL", "http://auth.example")
    with pytest.raises(ValueError):
        credentials.auth_base_url()
    monkeypatch.setenv("ORCA_API_BASE_URL", "http://relay.example/v1")
    with pytest.raises(ValueError):
        credentials.api_base_url()


def test_loopback_http_is_allowed_for_development(monkeypatch):
    monkeypatch.setenv("ORCA_AUTH_BASE_URL", "http://127.0.0.1:9000")
    assert credentials.auth_base_url() == "http://127.0.0.1:9000"


# ── 401 -> terminal reauthentication, generation safe ─────────────────────────


class _FakeHTTPError(Exception):
    def __init__(self, code: int, body: bytes = b"") -> None:
        self.code = code
        self._body = body

    def read(self) -> bytes:
        return self._body


def test_401_marks_the_exact_account_and_never_retries(monkeypatch):
    stored = credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_OAUTH_PKCE,
                               source=credentials.SOURCE_STORED, account_id="12345")
    )
    calls = {"n": 0}

    def opener(request, timeout=None):
        calls["n"] += 1
        raise _FakeHTTPError(401, b'{"error":"revoked"}')

    import urllib.error

    monkeypatch.setattr(urllib.error, "HTTPError", _FakeHTTPError)
    with pytest.raises(provider.ProviderError) as excinfo:
        provider.chat_completion(
            credentials.resolve_credential(), model="orcarouter/auto",
            messages=[{"role": "user", "content": "hi"}], opener=opener,
        )
    assert excinfo.value.kind == "needs_reauth"
    assert calls["n"] == 1, "a revoked durable key must not be retried"
    assert credentials.resolve_credential().status == credentials.STATUS_NEEDS_REAUTH
    assert stored.generation == credentials.resolve_credential().generation


def test_stale_401_does_not_poison_a_newer_credential(monkeypatch):
    old = credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_OAUTH_PKCE,
                               source=credentials.SOURCE_STORED)
    )
    new = credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY_2, method=credentials.METHOD_OAUTH_PKCE,
                               source=credentials.SOURCE_STORED)
    )
    assert new.generation == old.generation + 1

    # The old request fails late, after re-authentication.
    assert credentials.mark_needs_reauth(old) is False
    current = credentials.resolve_credential()
    assert current.api_key == FAKE_KEY_2
    assert current.status == credentials.STATUS_OK
    assert current.generation == new.generation


def test_401_from_an_environment_key_does_not_write_a_stored_secret(monkeypatch):
    monkeypatch.setenv(credentials.ENV_API_KEY, FAKE_KEY)
    credential = credentials.resolve_credential()
    assert credentials.mark_needs_reauth(credential) is False
    assert credentials.load_config().get("credential") is None


def test_403_and_429_are_reported_without_marking_reauth(monkeypatch):
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    for status, kind in ((403, "forbidden"), (429, "rate_limited")):
        with pytest.raises(provider.ProviderError) as excinfo:
            provider.chat_completion(
                credentials.resolve_credential(), model="orcarouter/auto",
                messages=[{"role": "user", "content": "hi"}],
                opener=_raising_opener(status),
            )
        assert excinfo.value.kind == kind
        assert excinfo.value.status == status
        assert credentials.resolve_credential().status == credentials.STATUS_OK


def _raising_opener(status: int):
    """An opener that always fails with a real urllib HTTPError."""

    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(b""))

    return opener


def test_error_messages_never_contain_the_key():
    credentials.store_credential(
        credentials.Credential(api_key=FAKE_KEY, method=credentials.METHOD_API_KEY,
                               source=credentials.SOURCE_STORED)
    )
    with pytest.raises(provider.ProviderError) as excinfo:
        provider.chat_completion(
            credentials.resolve_credential(), model="orcarouter/auto",
            messages=[{"role": "user", "content": "hi"}], opener=_raising_opener(500),
        )
    assert FAKE_KEY not in str(excinfo.value)


def test_auth_required_error_lists_both_choices():
    with pytest.raises(credentials.AuthRequiredError) as excinfo:
        credentials.require_credential()
    message = str(excinfo.value)
    assert "auth api-key" in message
    assert "auth login" in message
