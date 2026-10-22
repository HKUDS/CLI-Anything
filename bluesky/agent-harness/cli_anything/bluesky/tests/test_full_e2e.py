"""E2E tests for the Bluesky harness. Require real credentials.

Skipped unless BSKY_HANDLE and BSKY_APP_PASSWORD are set - these tests hit
the live AT Protocol network and post real content.

    BSKY_HANDLE=you.bsky.social BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx \
        python -m pytest cli_anything/bluesky/tests/test_full_e2e.py -v
"""

import os

import pytest

from cli_anything.bluesky.core import backend

pytestmark = pytest.mark.skipif(
    not (os.environ.get("BSKY_HANDLE") and os.environ.get("BSKY_APP_PASSWORD")),
    reason="set BSKY_HANDLE and BSKY_APP_PASSWORD to run live E2E tests",
)


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    """Log in once per module against the live API."""
    session_file = tmp_path_factory.mktemp("e2e") / "session.json"
    original = backend.DEFAULT_SESSION
    backend.DEFAULT_SESSION = session_file
    backend.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
    yield session_file
    backend.DEFAULT_SESSION = original


def test_whoami_returns_handle(session):
    s = backend.load_session()
    assert s["handle"] == os.environ["BSKY_HANDLE"]
    assert s["did"].startswith("did:")


def test_live_profile(session):
    p = backend.profile(os.environ["BSKY_HANDLE"])
    assert p["handle"] == os.environ["BSKY_HANDLE"]


def test_live_timeline(session):
    feed = backend.timeline(limit=5)
    assert "feed" in feed


def test_live_post_and_delete(session):
    """Post then delete, so E2E runs leave no trace on the account."""
    created = backend.post("harness-forge E2E self-test (auto-deleted)")
    uri = created["uri"]
    rkey = uri.split("/")[-1]
    repo = uri.split("/")[2]
    backend.request(
        "POST",
        "com.atproto.repo.deleteRecord",
        body={"repo": repo, "collection": "app.bsky.feed.post", "rkey": rkey},
    )
    # a second delete must 404 - proves the first one worked
    with pytest.raises(backend.BackendError):
        backend.request(
            "POST",
            "com.atproto.repo.deleteRecord",
            body={"repo": repo, "collection": "app.bsky.feed.post", "rkey": rkey},
        )
