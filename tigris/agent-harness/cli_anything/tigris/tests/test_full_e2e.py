"""End-to-end tests against a real Tigris account.

These tests are SKIPPED by default. To run them, set:

    TIGRIS_STORAGE_ACCESS_KEY_ID=...
    TIGRIS_STORAGE_SECRET_ACCESS_KEY=...
    CLI_ANYTHING_TIGRIS_TEST_BUCKET=<a writable bucket you own>
    CLI_ANYTHING_TIGRIS_RUN_E2E=1

Then run:

    pytest cli_anything/tigris/tests/test_full_e2e.py -v

The test object lives under a per-run UUID prefix and is cleaned up in
teardown, so concurrent runs do not collide.
"""

import os
import uuid

import pytest

from cli_anything.tigris.utils.tigris_backend import TigrisBackend

RUN_E2E = os.environ.get("CLI_ANYTHING_TIGRIS_RUN_E2E") == "1"
TEST_BUCKET = os.environ.get("CLI_ANYTHING_TIGRIS_TEST_BUCKET")

pytestmark = pytest.mark.skipif(
    not (RUN_E2E and TEST_BUCKET),
    reason=(
        "Set CLI_ANYTHING_TIGRIS_RUN_E2E=1 and "
        "CLI_ANYTHING_TIGRIS_TEST_BUCKET=<bucket> with valid credentials"
    ),
)


@pytest.fixture(scope="module")
def backend():
    """Real TigrisBackend against the configured endpoint + credentials."""
    return TigrisBackend()


@pytest.fixture
def test_key():
    """Unique key per test so concurrent runs don't collide."""
    return f"cli-anything-e2e/{uuid.uuid4()}.txt"


def test_put_get_delete_round_trip(backend, test_key):
    """Upload, head, get, then delete a small text object."""
    body = b"hello from cli-anything-tigris e2e"

    # PUT
    put_result = backend.put_object(
        TEST_BUCKET, test_key, body, content_type="text/plain"
    )
    assert put_result["bucket"] == TEST_BUCKET
    assert put_result["key"] == test_key
    assert put_result["etag"]

    try:
        # HEAD
        head = backend.head_object(TEST_BUCKET, test_key)
        assert head["size"] == len(body)
        assert head["content_type"] == "text/plain"

        # GET
        got = backend.get_object(TEST_BUCKET, test_key)
        assert got == body

        # LIST (with prefix narrowing)
        listing = backend.list_objects(TEST_BUCKET, prefix=test_key, limit=10)
        assert any(o["key"] == test_key for o in listing)
    finally:
        # DELETE (always, even on assert failure)
        backend.delete_object(TEST_BUCKET, test_key)


def test_server_side_copy(backend, test_key):
    """Server-side copy_object should duplicate without round-tripping bytes."""
    body = b"copy-test"
    src_key = test_key
    dst_key = f"{test_key}.copy"

    backend.put_object(TEST_BUCKET, src_key, body)
    try:
        backend.copy_object(TEST_BUCKET, src_key, TEST_BUCKET, dst_key)
        try:
            assert backend.get_object(TEST_BUCKET, dst_key) == body
        finally:
            backend.delete_object(TEST_BUCKET, dst_key)
    finally:
        backend.delete_object(TEST_BUCKET, src_key)


def test_presigned_url_shape(backend, test_key):
    """Presigned URLs should resolve to the right endpoint + key."""
    url = backend.presign_get(TEST_BUCKET, test_key, expires_in=60)
    assert backend.endpoint in url
    assert test_key.split("/")[-1] in url  # last path segment appears
    assert "X-Amz-Signature" in url or "Signature=" in url


def test_list_buckets(backend):
    """list_buckets must include the configured test bucket."""
    buckets = backend.list_buckets()
    names = {b["name"] for b in buckets}
    assert TEST_BUCKET in names, f"{TEST_BUCKET} not in {names}"
