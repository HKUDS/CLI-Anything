"""End-to-end tests against a real Tigris CLI and a real bucket.

These tests are SKIPPED by default. To run them locally:

    npm install -g @tigrisdata/cli     # or: brew install tigrisdata/tap/tigris
    tigris login                       # one-time OAuth setup

    export CLI_ANYTHING_TIGRIS_TEST_BUCKET=<a bucket you can write to>
    export CLI_ANYTHING_TIGRIS_RUN_E2E=1

    pytest cli_anything/tigris/tests/test_full_e2e.py -v

Test objects live under a per-run UUID prefix and are cleaned up in
teardown so concurrent runs do not collide.
"""

import os
import shutil
import uuid

import pytest

from cli_anything.tigris.utils.tigris_backend import TigrisBackend

RUN_E2E = os.environ.get("CLI_ANYTHING_TIGRIS_RUN_E2E") == "1"
TEST_BUCKET = os.environ.get("CLI_ANYTHING_TIGRIS_TEST_BUCKET")
HAS_TIGRIS_CLI = shutil.which("tigris") is not None

pytestmark = pytest.mark.skipif(
    not (RUN_E2E and TEST_BUCKET and HAS_TIGRIS_CLI),
    reason=(
        "Set CLI_ANYTHING_TIGRIS_RUN_E2E=1 + "
        "CLI_ANYTHING_TIGRIS_TEST_BUCKET=<bucket>, install the `tigris` CLI "
        "(npm install -g @tigrisdata/cli), and run `tigris login`."
    ),
)


@pytest.fixture(scope="module")
def backend():
    return TigrisBackend()


@pytest.fixture
def test_key():
    return f"cli-anything-e2e/{uuid.uuid4()}.txt"


def test_whoami_returns_user(backend):
    info = backend.whoami()
    # whoami output shape varies — just check it returned something truthy
    assert info, f"whoami returned empty: {info!r}"


def test_list_buckets_includes_test_bucket(backend):
    buckets = backend.list_buckets()
    if isinstance(buckets, list):
        names = {
            b.get("name") or b.get("Name")
            for b in buckets if isinstance(b, dict)
        }
        assert TEST_BUCKET in names, f"{TEST_BUCKET} not in {names}"


def test_put_get_delete_round_trip(backend, test_key, tmp_path):
    body = "hello from cli-anything-tigris e2e\n"

    # PUT via inline-text path
    backend.put_object_inline(TEST_BUCKET, test_key, body)

    try:
        # GET to a local file and verify contents
        out = tmp_path / "downloaded.txt"
        backend.get_object_to_file(TEST_BUCKET, test_key, str(out))
        assert out.read_text() == body

        # HEAD / stat — returns *some* metadata
        info = backend.head_object(TEST_BUCKET, test_key)
        assert info, f"head_object returned empty: {info!r}"

        # LIST narrowed by prefix should include our key
        prefix = test_key.rsplit("/", 1)[0]
        listing = backend.list_objects(TEST_BUCKET, prefix=prefix, limit=50)
        if isinstance(listing, list):
            found = any(
                (o.get("key") or o.get("Key") or "") == test_key
                for o in listing if isinstance(o, dict)
            )
            assert found, f"{test_key} not in {listing}"
    finally:
        backend.delete_object(TEST_BUCKET, test_key)


def test_presigned_url_includes_key(backend, test_key):
    backend.put_object_inline(TEST_BUCKET, test_key, "presign-test")
    try:
        url = backend.presign(TEST_BUCKET, test_key, method="get", expires_in=60)
        assert isinstance(url, str) and url.startswith("http"), url
        # Last path segment should appear in the URL
        leaf = test_key.split("/")[-1]
        assert leaf in url, f"{leaf} not in {url}"
    finally:
        backend.delete_object(TEST_BUCKET, test_key)


def test_snapshot_list_works(backend):
    snaps = backend.list_snapshots(TEST_BUCKET)
    # We don't assert on count — just that the call succeeded and returned
    # something parseable (list, dict, or string).
    assert snaps is not None or snaps == []
