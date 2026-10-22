"""Unit tests for the Bluesky backend. No network, no credentials.

Every HTTP call is mocked; the session file is redirected to a temp path.
"""

import json
import os

import pytest

from cli_anything.bluesky.core import backend


@pytest.fixture()
def session_file(tmp_path, monkeypatch):
    p = tmp_path / "session.json"
    monkeypatch.setattr(backend, "DEFAULT_SESSION", p)
    return p


@pytest.fixture()
def logged_in(session_file):
    session_file.write_text(
        json.dumps({"accessJwt": "test-jwt", "did": "did:plc:test123", "handle": "tester.bsky.social"})
    )
    return session_file


def test_login_saves_session(monkeypatch, session_file):
    captured = {}

    def fake_request(method, endpoint, body=None, auth=True, timeout=20.0):
        captured.update({"method": method, "endpoint": endpoint, "body": body, "auth": auth})
        return {
            "status": 200,
            "body": {"accessJwt": "jwt-abc", "did": "did:plc:xyz", "handle": "tester.bsky.social"},
        }

    monkeypatch.setattr(backend, "request", fake_request)
    out = backend.login("tester.bsky.social", "app-pw-1234")

    assert out["did"] == "did:plc:xyz"
    assert captured["auth"] is False  # login itself is unauthenticated
    assert captured["body"] == {"identifier": "tester.bsky.social", "appPassword": "app-pw-1234"}
    saved = json.loads(session_file.read_text())
    assert saved["accessJwt"] == "jwt-abc"


def test_login_uses_app_password_field():
    # the harness must only ever send the app-password field
    import inspect

    src = inspect.getsource(backend.login)
    assert "appPassword" in src


def test_post_builds_record(monkeypatch, logged_in):
    captured = {}

    def fake_request(method, endpoint, body=None, auth=True, timeout=20.0):
        captured.update({"method": method, "endpoint": endpoint, "body": body})
        return {"status": 200, "body": {"uri": "at://did:plc:test123/app.bsky.feed.post/abc"}}

    monkeypatch.setattr(backend, "request", fake_request)
    out = backend.post("hello from harness-forge")

    assert captured["method"] == "POST"
    assert captured["endpoint"] == "com.atproto.repo.createRecord"
    assert captured["body"]["repo"] == "did:plc:test123"
    assert captured["body"]["collection"] == "app.bsky.feed.post"
    assert captured["body"]["record"]["$type"] == "app.bsky.feed.post"
    assert captured["body"]["record"]["text"] == "hello from harness-forge"
    assert captured["body"]["record"]["createdAt"].endswith("Z")
    assert out["uri"].endswith("/abc")


def test_post_requires_session(monkeypatch, session_file):
    monkeypatch.setattr(backend, "request", lambda *a, **k: pytest.fail("should not call API"))
    with pytest.raises(backend.AuthError):
        backend.post("nope")


def test_request_attaches_bearer(monkeypatch, logged_in):
    seen = {}

    class FakeHTTPResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *args):
            return b'{"ok": true}'

    def fake_urlopen(req, timeout=20.0):
        seen["auth"] = req.headers.get("Authorization")
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        return FakeHTTPResponse()

    monkeypatch.setattr(backend.urllib.request, "urlopen", fake_urlopen)
    out = backend.request("GET", "app.bsky.feed.getTimeline?limit=5")
    assert seen["auth"] == "Bearer test-jwt"
    assert seen["url"] == "https://bsky.social/xrpc/app.bsky.feed.getTimeline?limit=5"
    assert out["body"] == {"ok": True}


def test_request_raises_on_http_error(monkeypatch, logged_in):
    import urllib.error

    def fake_urlopen(req, timeout=20.0):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(backend.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(backend.BackendError) as exc:
        backend.request("GET", "app.bsky.feed.getTimeline")
    assert "401" in str(exc.value)


def test_session_file_permissions(monkeypatch, tmp_path):
    p = tmp_path / "nested" / "session.json"
    monkeypatch.setattr(backend, "DEFAULT_SESSION", p)
    backend.save_session({"accessJwt": "x"})
    assert p.exists()
    if os.name == "posix":
        assert oct(p.stat().st_mode)[-3:] == "600"


def test_timeline_limit_clamped(monkeypatch, logged_in):
    seen = {}

    def fake_request(method, endpoint, body=None, auth=True, timeout=20.0):
        seen["endpoint"] = endpoint
        return {"status": 200, "body": {"feed": []}}

    monkeypatch.setattr(backend, "request", fake_request)
    backend.timeline(500)
    assert "limit=100" in seen["endpoint"]


def test_search_quotes_query(monkeypatch, logged_in):
    seen = {}

    def fake_request(method, endpoint, body=None, auth=True, timeout=20.0):
        seen["endpoint"] = endpoint
        return {"status": 200, "body": {"posts": []}}

    monkeypatch.setattr(backend, "request", fake_request)
    backend.search_posts("cli anything", 10)
    assert "q=cli%20anything" in seen["endpoint"]
