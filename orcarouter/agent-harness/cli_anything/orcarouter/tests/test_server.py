"""The loopback settings server: both auth choices, catalog, and key hygiene."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from cli_anything.orcarouter.core import credentials, server as server_mod

from .fake_orca import FAKE_KEY, FakeOrcaRouter

FAKE_KEY_INPUT = "sk-orca-gui-00000000000000000000000000000000000000"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCAROUTER_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(credentials.ENV_API_KEY, raising=False)
    monkeypatch.setattr(credentials, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(credentials, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    yield


class Client:
    """Tiny HTTP client for the settings server."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.seen: list[bytes] = []

    def get(self, path: str) -> tuple[int, bytes, str]:
        request = urllib.request.Request(self.base + path)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
                self.seen.append(body)
                return response.status, body, response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            body = exc.read()
            self.seen.append(body)
            return exc.code, body, exc.headers.get("Content-Type", "")

    def post(self, path: str, payload: dict | None = None) -> tuple[int, bytes]:
        data = json.dumps(payload or {}).encode("utf-8")
        request = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
                self.seen.append(body)
                return response.status, body
        except urllib.error.HTTPError as exc:
            body = exc.read()
            self.seen.append(body)
            return exc.code, body

    def json(self, path: str) -> dict:
        status, body, _ = self.get(path)
        assert status == 200, body
        return json.loads(body)

    def post_json(self, path: str, payload: dict | None = None) -> dict:
        status, body = self.post(path, payload)
        assert status == 200, body
        return json.loads(body)


@pytest.fixture
def gui():
    server, url = server_mod.start_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Client(url), server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ── static page ───────────────────────────────────────────────────────────────


def test_page_and_assets_are_served(gui):
    client, _ = gui
    status, body, content_type = client.get("/")
    assert status == 200
    assert "text/html" in content_type
    html = body.decode("utf-8")
    assert "OrcaRouter - API" in html
    assert "OrcaRouter - Auth" in html
    assert "Connect with OrcaRouter" in html
    assert 'id="model-trigger"' in html

    for asset, kind in (("/static/app.js", "javascript"), ("/static/styles.css", "css")):
        status, body, content_type = client.get(asset)
        assert status == 200, asset
        assert kind in content_type or "text/" in content_type

    status, body, _ = client.get("/static/orca-logo-classic.png")
    assert status == 200
    assert body[:8] == b"\x89PNG\r\n\x1a\n", "the official OrcaRouter logo must be a real PNG"


def test_page_hides_the_key_input_and_masks_the_stored_secret(gui):
    client, _ = gui
    client.post_json("/api/auth/api-key", {"api_key": FAKE_KEY_INPUT})
    status, body, _ = client.get("/")
    assert status == 200
    html = body.decode("utf-8")
    assert FAKE_KEY_INPUT not in html
    assert 'type="password"' in html, "the key field must be a password input"
    assert 'id="auth-masked"' in html


# ── API-key choice ────────────────────────────────────────────────────────────


def test_api_key_choice_stores_reads_and_clears(gui):
    client, _ = gui
    status = client.json("/api/auth/status")
    assert status["authenticated"] is False
    assert status["masked_key"] == ""

    stored = client.post_json("/api/auth/api-key", {"api_key": FAKE_KEY_INPUT})
    assert stored["stored"] is True
    assert stored["credential"]["method"] == "api_key"

    status = client.json("/api/auth/status")
    assert status["authenticated"] is True
    assert status["credential"]["method"] == "api_key"
    assert status["masked_key"].startswith("sk-orca")
    assert status["masked_key"] != FAKE_KEY_INPUT

    cleared = client.post_json("/api/auth/clear")
    assert cleared["authenticated"] is False
    assert credentials.resolve_credential() is None


def test_api_key_choice_rejects_a_malformed_key(gui):
    client, _ = gui
    status, body = client.post("/api/auth/api-key", {"api_key": "sk-other-000000000000"})
    assert status == 400
    assert "sk-orca-" in json.loads(body)["error"]
    assert credentials.resolve_credential() is None


def test_status_endpoint_reports_both_origins(gui):
    client, _ = gui
    status = client.json("/api/auth/status")
    assert status["auth_origin"] == "https://www.orcarouter.ai"
    assert status["api_origin"] == "https://api.orcarouter.ai/v1"


# ── PKCE choice ───────────────────────────────────────────────────────────────


def test_pkce_choice_authorizes_through_the_page(monkeypatch, gui):
    client, server = gui
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)

        login = client.post_json("/api/auth/login", {"flow": "loopback"})
        assert login["busy"] is True
        assert login["authorize_url"].startswith(fake.auth_base + "/auth?")
        assert "code_challenge_method=S256" in login["authorize_url"]

        # The user approves in the browser.
        consent = fake.consent(login["authorize_url"], approve=True)
        urllib.request.urlopen(consent["callback_url"], timeout=5).read()

        deadline = time.time() + 10
        while time.time() < deadline:
            state = client.json("/api/auth/login")
            if not state["busy"]:
                break
            time.sleep(0.1)

        assert state["busy"] is False
        assert state["completed"] is True
        status = client.json("/api/auth/status")
        assert status["authenticated"] is True
        assert status["credential"]["method"] == "oauth_pkce"
        assert status["credential"]["scope"] == "api"


def test_pkce_out_of_band_accepts_a_pasted_code(monkeypatch, gui):
    client, server = gui
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)

        login = client.post_json("/api/auth/login", {"flow": "oob"})
        assert "callback_url=oob" in login["authorize_url"]

        code = fake.consent(login["authorize_url"], approve=True)["code"]
        client.post_json("/api/auth/login/code", {"code": code})

        deadline = time.time() + 10
        while time.time() < deadline:
            if not client.json("/api/auth/login")["busy"]:
                break
            time.sleep(0.1)
        assert client.json("/api/auth/status")["authenticated"] is True


def test_cancel_releases_the_login_lock(gui):
    client, server = gui
    client.post_json("/api/auth/login", {"flow": "loopback"})
    assert client.json("/api/auth/login")["busy"] is True

    state = client.post_json("/api/auth/login/cancel")
    assert state["busy"] is False
    assert state["hint"] == ""

    # A second login starts immediately, without remounting anything.
    second = client.post_json("/api/auth/login", {"flow": "loopback"})
    assert second["busy"] is True
    assert second["attempt"] > state["attempt"]
    client.post_json("/api/auth/login/cancel")


def test_pagehide_cancels_server_side_work_and_a_new_login_can_start(gui):
    """The pagehide handler posts the same cancel the UI uses, with keepalive."""
    client, server = gui
    client.post_json("/api/auth/login", {"flow": "loopback"})
    assert server.logins.state.busy is True

    # pagehide: synchronous local clear, then the keepalive cancel request.
    state = client.post_json("/api/auth/login/cancel")
    assert state["busy"] is False

    third = client.post_json("/api/auth/login", {"flow": "loopback"})
    assert third["busy"] is True
    client.post_json("/api/auth/login/cancel")


def test_pagehide_handler_is_present_in_the_client_and_clears_state():
    source = (server_mod.UI_DIR / "app.js").read_text(encoding="utf-8")
    assert 'addEventListener("pagehide"' in source
    assert "keepalive: true" in source
    # It must clear busy/hint synchronously rather than rely on the guarded finally.
    handler = source.split('addEventListener("pagehide"')[1]
    assert "loginBusy = false" in handler
    assert "auth-pkce-hint" in handler


def test_hidden_attribute_actually_hides_flex_rows():
    """`display: flex` on .row beats the UA [hidden] rule unless it is overridden.

    Without this the code field of a cancelled sign-in stayed on screen even
    though the client had set `hidden`.
    """
    css = (server_mod.UI_DIR / "styles.css").read_text(encoding="utf-8")
    assert "[hidden]" in css and "display: none !important" in css


def test_a_stale_status_response_cannot_reopen_a_cancelled_login(monkeypatch, gui):
    """The client must drop a status response issued before the cancel."""
    client, server = gui
    client.post_json("/api/auth/login", {"flow": "oob"})
    before = client.json("/api/auth/login")
    assert before["busy"] is True

    cancelled = client.post_json("/api/auth/login/cancel")
    assert cancelled["busy"] is False
    assert cancelled["generation"] > before["generation"]

    source = (server_mod.UI_DIR / "app.js").read_text(encoding="utf-8")
    assert "isStale" in source
    assert "loginGeneration += 1" in source


def test_starting_a_second_login_while_the_first_is_in_flight(gui):
    client, server = gui
    first = client.post_json("/api/auth/login", {"flow": "loopback"})
    second = client.post_json("/api/auth/login", {"flow": "loopback"})
    assert second["attempt"] == first["attempt"] + 1
    assert server.logins.state.busy is True
    client.post_json("/api/auth/login/cancel")


def test_login_code_without_a_pending_attempt_is_refused(gui):
    client, _ = gui
    status, body = client.post("/api/auth/login/code", {"code": "abc"})
    assert status == 400
    assert "sign-in" in json.loads(body)["error"]


# ── catalog through the page ──────────────────────────────────────────────────


def test_model_endpoint_filters_by_capability_and_modality(monkeypatch, gui):
    client, _ = gui
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        # Discovery uses the user's own credential, so a workspace-scoped answer
        # is what comes back. Without one the endpoint reports the seed instead.
        client.post_json("/api/auth/api-key", {"api_key": FAKE_KEY_INPUT})

        chat = client.json("/api/models?capability=chat")
        assert chat["source"] == "live"
        ids = [m["id"] for m in chat["models"]]
        assert "openai/gpt-image-1" not in ids
        assert "openai/text-embedding-3-large" not in ids

        with_image = client.json("/api/models?capability=chat&modalities=image")
        assert [m["id"] for m in with_image["models"]] == ["google/gemini-3.5-flash"]

        embedding = client.json("/api/models?capability=embedding")
        assert [m["id"] for m in embedding["models"]] == ["openai/text-embedding-3-large"]


def test_model_endpoint_reports_degraded_when_discovery_fails(monkeypatch, gui):
    client, _ = gui
    monkeypatch.setenv("ORCA_API_BASE_URL", "https://127.0.0.1:1/v1")
    payload = client.json("/api/models?capability=chat")
    assert payload["source"] == "seed"
    assert payload["degraded"] is True
    assert "orcarouter/auto" in [m["id"] for m in payload["models"]]


def test_model_endpoint_returns_minimal_metadata(monkeypatch, gui):
    client, _ = gui
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)
        client.post_json("/api/auth/api-key", {"api_key": FAKE_KEY_INPUT})
        payload = client.json("/api/models?capability=chat")
        serialized = json.dumps(payload)
        assert "pricing" not in serialized
        assert FAKE_KEY not in serialized
        gpt = [m for m in payload["models"] if m["id"] == "openai/gpt-5.5"][0]
        assert gpt["reasoning_efforts"] == ["low", "medium", "high", "xhigh"]
        assert gpt["context_length"] == 400000
        assert gpt["input_modalities"] == ["text"]


# ── key hygiene across every response ─────────────────────────────────────────


def test_no_response_body_ever_contains_the_api_key(monkeypatch, gui):
    client, _ = gui
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        monkeypatch.setenv("ORCA_API_BASE_URL", fake.api_base)

        client.post_json("/api/auth/api-key", {"api_key": FAKE_KEY_INPUT})
        client.get("/api/auth/status")
        client.get("/api/models?capability=chat")
        client.get("/")
        client.get("/static/app.js")

        login = client.post_json("/api/auth/login", {"flow": "loopback"})
        consent = fake.consent(login["authorize_url"], approve=True)
        urllib.request.urlopen(consent["callback_url"], timeout=5).read()
        deadline = time.time() + 10
        while time.time() < deadline and client.json("/api/auth/login")["busy"]:
            time.sleep(0.1)
        client.get("/api/auth/status")

    for body in client.seen:
        assert FAKE_KEY_INPUT.encode() not in body
        assert fake.issue_key.encode() not in body


def test_login_state_never_contains_the_verifier(monkeypatch, gui):
    client, server = gui
    with FakeOrcaRouter() as fake:
        monkeypatch.setenv("ORCA_AUTH_BASE_URL", fake.auth_base)
        login = client.post_json("/api/auth/login", {"flow": "loopback"})
        verifier = server.logins._current.pkce.verifier
        assert verifier not in json.dumps(login)
        assert verifier not in login["authorize_url"]
        client.post_json("/api/auth/login/cancel")


def test_server_only_binds_loopback():
    server, url = server_mod.start_server()
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert url.startswith("http://127.0.0.1:")
    finally:
        server.server_close()
