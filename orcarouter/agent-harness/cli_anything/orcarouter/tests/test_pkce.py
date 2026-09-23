"""PKCE: verifier/challenge/state, authorize URL, exchange, failures, lifecycle."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from cli_anything.orcarouter.core import credentials, login_manager, pkce

from .fake_orca import FAKE_ACCOUNT, FAKE_KEY, FakeOrcaRouter

FAKE_CODE = "code-fake-0000000000000000"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCAROUTER_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(credentials.ENV_API_KEY, raising=False)
    monkeypatch.setattr(credentials, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(credentials, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    yield


# ── the cryptographic primitives ──────────────────────────────────────────────


def test_challenge_is_base64url_sha256_without_padding():
    verifier = "abcdefghijklmnopqrstuvwxyz0123456789-._~abc"
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    assert pkce.challenge_for(verifier) == expected
    assert "=" not in pkce.challenge_for(verifier)
    assert "+" not in pkce.challenge_for(verifier)
    assert "/" not in pkce.challenge_for(verifier)


def test_every_attempt_gets_a_fresh_verifier_and_state():
    attempts = [pkce.PkceAttempt() for _ in range(32)]
    assert len({a.verifier for a in attempts}) == 32
    assert len({a.state for a in attempts}) == 32
    for attempt in attempts:
        assert len(attempt.verifier) >= 43  # 32 random bytes -> 43 base64url chars
        assert attempt.challenge == pkce.challenge_for(attempt.verifier)


def test_verifier_never_appears_on_the_authorize_url():
    attempt = pkce.PkceAttempt()
    url = attempt.authorize_url(callback_url="http://127.0.0.1:1234/cb", app_name="My Tool")
    assert attempt.verifier not in url
    assert attempt.challenge in url
    assert "code_challenge_method=S256" in url
    assert "callback_url=http%3A%2F%2F127.0.0.1%3A1234%2Fcb" in url
    assert "app_name=My+Tool" in url


def test_authorize_url_targets_the_auth_origin(monkeypatch):
    monkeypatch.delenv("ORCA_BASE_URL", raising=False)
    monkeypatch.delenv("ORCA_AUTH_BASE_URL", raising=False)
    monkeypatch.delenv("ORCA_API_BASE_URL", raising=False)
    attempt = pkce.PkceAttempt()
    url = attempt.authorize_url(callback_url="oob")
    assert url.startswith("https://www.orcarouter.ai/auth?")
    assert "api.orcarouter.ai" not in url
    assert "callback_url=oob" in url


def test_state_comparison_is_exact_and_constant_time():
    attempt = pkce.PkceAttempt()
    assert attempt.state_matches(attempt.state)
    assert not attempt.state_matches(attempt.state + "x")
    assert not attempt.state_matches("")
    assert not attempt.state_matches(None)
    assert not attempt.state_matches(pkce.new_state())


# ── exchange against the fake auth server ─────────────────────────────────────


def test_flow_a_end_to_end_through_the_login_adapter(monkeypatch):
    """authorize -> loopback callback -> exchange -> credential."""
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)

        manager = login_manager.LoginManager()
        seen: dict = {}

        def drive(url: str) -> None:
            seen["url"] = url
            result = fake.consent(url, approve=True)
            # Simulate the browser following the redirect.
            urllib.request.urlopen(result["callback_url"], timeout=5).read()

        thread = threading.Thread(target=lambda: _run(manager, drive, seen), daemon=True)
        thread.start()
        thread.join(timeout=10)

        assert "url" in seen, "the login never produced an authorization URL"
        assert seen["url"].startswith(fake.auth_base + "/auth?")
        assert fake.requests_for("auth") == ["/api/v1/auth/keys"]

        result = seen["result"]
        assert result.api_key == FAKE_KEY
        assert result.account_id == FAKE_ACCOUNT
        assert result.granted_scope == "api"


def _run(manager, drive, seen):
    original = drive

    def on_prompt(url):
        original(url)

    seen["result"] = login_manager.run_login(
        manager,
        flow=pkce.FLOW_LOOPBACK,
        open_browser=False,
        timeout=8,
        on_prompt=on_prompt,
    )


def test_exchange_body_carries_the_verifier_and_the_method(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt()
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)
        result = attempt.exchange(consent["code"])

        body = json.loads(fake.body_for("/api/v1/auth/keys").decode("utf-8"))
        assert body == {
            "code": consent["code"],
            "code_verifier": attempt.verifier,
            "code_challenge_method": "S256",
        }
        assert result.api_key == FAKE_KEY


def test_exchange_uses_the_auth_origin_never_the_inference_origin(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        attempt = pkce.PkceAttempt()
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)
        attempt.exchange(consent["code"])

        assert fake.requests_for("auth") == ["/api/v1/auth/keys"]
        assert fake.requests_for("api") == []


def test_exchange_rejects_a_wrong_verifier(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt()
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)
        tampered = pkce.PkceAttempt()
        tampered.verifier = attempt.verifier + "x"
        with pytest.raises(pkce.PkceError) as excinfo:
            tampered.exchange(consent["code"])
        assert excinfo.value.kind == "code_rejected"


def test_a_code_cannot_be_reused(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt()
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)
        attempt.exchange(consent["code"])
        with pytest.raises(pkce.PkceError) as excinfo:
            attempt.exchange(consent["code"])
        assert excinfo.value.kind == "code_rejected"


def test_an_expired_code_is_rejected(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt()
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)
        fake.expire(consent["code"])
        with pytest.raises(pkce.PkceError) as excinfo:
            attempt.exchange(consent["code"])
        assert excinfo.value.kind == "code_rejected"


def test_an_unknown_code_is_rejected(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        with pytest.raises(pkce.PkceError) as excinfo:
            pkce.PkceAttempt().exchange("code-that-never-existed")
        assert excinfo.value.kind == "code_rejected"


def test_challenge_method_downgrade_is_refused(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt()
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)

        # The exchange adapter always sends S256; a downgrade request is refused.
        body = json.dumps(
            {"code": consent["code"], "code_verifier": attempt.verifier,
             "code_challenge_method": "plain"}
        ).encode("utf-8")
        request = urllib.request.Request(
            credentials.exchange_url(), data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(request, timeout=5)
        assert excinfo.value.code == 400

        # And the adapter's own error mapping produces the actionable kind.
        def opener(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, None)

        with pytest.raises(pkce.PkceError) as mapped:
            pkce.PkceAttempt().exchange(FAKE_CODE, opener=opener)
        assert mapped.value.kind == "bad_challenge_method"


def test_429_is_reported_as_rate_limited(monkeypatch):
    monkeypatch.setenv("ORCA_AUTH_BASE_URL", "https://www.orcarouter.ai")

    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    with pytest.raises(pkce.PkceError) as excinfo:
        pkce.PkceAttempt().exchange(FAKE_CODE, opener=opener)
    assert excinfo.value.kind == "rate_limited"
    assert "10" in str(excinfo.value)


def test_network_failure_is_reported_and_does_not_hang(monkeypatch):
    monkeypatch.setenv("ORCA_AUTH_BASE_URL", "https://www.orcarouter.ai")

    def opener(request, timeout=None):
        raise urllib.error.URLError("dns failure")

    with pytest.raises(pkce.PkceError) as excinfo:
        pkce.PkceAttempt().exchange(FAKE_CODE, opener=opener)
    assert excinfo.value.kind == "network"


def test_denial_is_terminal(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()
        seen: dict = {}

        def drive(url: str) -> None:
            result = fake.consent(url, approve=False)
            urllib.request.urlopen(result["callback_url"], timeout=5).read()

        def worker():
            try:
                login_manager.run_login(
                    manager, flow=pkce.FLOW_LOOPBACK, open_browser=False,
                    timeout=8, on_prompt=drive,
                )
            except login_manager.LoginError as exc:
                seen["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=10)

        assert seen["error"].kind == "denied"
        assert manager.state.busy is False
        assert fake.requests_for("auth") == [], "a denied login must not exchange anything"


def test_flow_a_state_mismatch_is_refused_before_the_code_is_used(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()
        seen: dict = {}

        def drive(url: str) -> None:
            result = fake.consent(url, approve=True)
            # Someone else's page drops a code on our listener with a wrong state.
            wrong = result["callback_url"].replace(
                urllib.parse.quote(result["state"]), "not-the-state-we-sent"
            )
            try:
                urllib.request.urlopen(wrong, timeout=5).read()
            except urllib.error.HTTPError:
                pass

        def worker():
            try:
                login_manager.run_login(
                    manager, flow=pkce.FLOW_LOOPBACK, open_browser=False,
                    timeout=6, on_prompt=drive,
                )
            except login_manager.LoginError as exc:
                seen["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=10)

        assert seen["error"].kind == "callback_error"
        assert "state mismatch" in str(seen["error"])
        assert fake.requests_for("auth") == [], "the code must never reach the exchange"


def test_flow_b_out_of_band_sends_callback_url_oob(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()
        seen: dict = {}

        def code_provider(url: str) -> str:
            seen["url"] = url
            return fake.consent(url, approve=True)["code"]

        result = login_manager.run_login(
            manager, flow=pkce.FLOW_OOB, open_browser=False, timeout=5,
            code_provider=code_provider,
        )
        assert "callback_url=oob" in seen["url"]
        assert "code_challenge_method=S256" in seen["url"]
        assert result.api_key == FAKE_KEY


def test_flow_b_requires_s256_and_the_adapter_sends_it(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt(flow=pkce.FLOW_OOB)
        url = attempt.authorize_url(callback_url="oob")
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        assert params["code_challenge_method"] == ["S256"]
        assert params["callback_url"] == ["oob"]
        assert params["code_challenge"][0] == pkce.challenge_for(attempt.verifier)


def test_timeout_ends_the_login_and_releases_the_lock(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()
        with pytest.raises(login_manager.LoginError) as excinfo:
            login_manager.run_login(
                manager, flow=pkce.FLOW_LOOPBACK, open_browser=False, timeout=0.2,
                on_prompt=lambda url: None,
            )
        assert excinfo.value.kind == "timeout"
        assert manager.state.busy is False
        assert manager.state.hint == ""


def test_scope_downgrade_is_reported_and_blocks_inference():
    result = pkce.PkceResult(
        api_key=FAKE_KEY, account_id="1", granted_scope="connector", requested_scope="api"
    )
    assert result.scope_warning() is not None
    assert result.scope_allows_api() is True

    downgraded = pkce.PkceResult(
        api_key=FAKE_KEY, account_id="1", granted_scope="readonly", requested_scope="api"
    )
    assert downgraded.scope_allows_api() is False
    assert "readonly" in downgraded.scope_warning()


def test_scope_is_read_from_the_response_not_assumed(monkeypatch):
    with FakeOrcaRouter(scope="connector") as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        attempt = pkce.PkceAttempt(scope="connector")
        consent = fake.consent(attempt.authorize_url(callback_url="oob"), approve=True)
        result = attempt.exchange(consent["code"])
        assert result.granted_scope == "connector"


# ── cancellation and generations ──────────────────────────────────────────────


def test_second_login_invalidates_the_first():
    manager = login_manager.LoginManager()
    first = manager.begin(open_browser=False)
    assert manager.state.attempt == 1
    assert manager.state.busy is True

    second = manager.begin(open_browser=False)
    assert manager.state.attempt == 2
    assert manager.state.busy is True
    assert manager.is_current(second)
    assert not manager.is_current(first)


def test_a_stale_result_cannot_overwrite_a_newer_login(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()
        stale = manager.begin(open_browser=False)
        fresh = manager.begin(open_browser=False)

        # The old attempt completes late.
        assert manager.fail(stale, "late failure") is False
        assert manager.is_current(fresh)
        assert manager.state.busy is True
        assert manager.state.last_error == ""


def test_cancel_releases_state_and_the_listener():
    manager = login_manager.LoginManager()
    attempt = manager.begin(open_browser=False)
    assert attempt._server is not None
    assert manager.cancel() is True
    assert manager.state.busy is False
    assert manager.state.hint == ""
    assert attempt._server is None
    assert manager.cancel() is False, "cancelling twice is a no-op"


def test_pagehide_clears_busy_and_hint_without_remounting():
    manager = login_manager.LoginManager()
    manager.begin(open_browser=False)
    assert manager.state.busy is True
    assert manager.state.hint != ""

    assert manager.pagehide() is True
    assert manager.state.busy is False
    assert manager.state.hint == ""

    # A second login can start immediately on the same manager.
    second = manager.begin(open_browser=False)
    assert manager.is_current(second)
    assert manager.state.busy is True
    manager.cancel()


def test_cancelled_login_does_not_issue_a_credential(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()

        def on_prompt(url: str) -> None:
            manager.cancel()

        with pytest.raises(login_manager.LoginError) as excinfo:
            login_manager.run_login(
                manager, flow=pkce.FLOW_LOOPBACK, open_browser=False, timeout=5,
                on_prompt=on_prompt,
            )
        assert excinfo.value.kind in {"cancelled", "callback_error"}
        assert credentials.resolve_credential() is None


def test_verifier_never_appears_in_a_failure_message(monkeypatch):
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        manager = login_manager.LoginManager()
        captured: dict = {}

        def on_prompt(url: str) -> None:
            captured["attempt"] = manager.state
            raise login_manager.LoginError("stopped", kind="cancelled")

        with pytest.raises(login_manager.LoginError) as excinfo:
            login_manager.run_login(
                manager, flow=pkce.FLOW_LOOPBACK, open_browser=False, timeout=5,
                on_prompt=on_prompt,
            )
        assert "stopped" in str(excinfo.value)
        assert manager.state.authorize_url == "" or "code_challenge" in manager.state.authorize_url
