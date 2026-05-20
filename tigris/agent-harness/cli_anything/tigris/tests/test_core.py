"""Unit tests for the Tigris CLI harness.

These tests fully mock boto3 so they can run without a Tigris account or
network access. End-to-end tests against a real Tigris bucket live in
test_full_e2e.py (not included in MVP; see TEST.md).
"""

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.tigris.tigris_cli import cli
from cli_anything.tigris.utils.tigris_backend import TigrisBackend


# ── Backend unit tests (boto3 mocked) ────────────────────────────────


@pytest.fixture
def mock_boto3_client():
    with patch("cli_anything.tigris.utils.tigris_backend.boto3") as mock_boto:
        client = MagicMock()
        mock_boto.client.return_value = client
        yield client


def _now_iso():
    return datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


def test_list_buckets(mock_boto3_client):
    mock_boto3_client.list_buckets.return_value = {
        "Buckets": [
            {"Name": "alpha", "CreationDate": _now_iso()},
            {"Name": "beta", "CreationDate": _now_iso()},
        ]
    }
    backend = TigrisBackend()
    result = backend.list_buckets()
    assert len(result) == 2
    assert result[0]["name"] == "alpha"
    assert "created" in result[0]


def test_create_bucket(mock_boto3_client):
    backend = TigrisBackend()
    result = backend.create_bucket("new-bucket")
    assert result == {"name": "new-bucket", "status": "created"}
    mock_boto3_client.create_bucket.assert_called_once_with(Bucket="new-bucket")


def test_delete_bucket(mock_boto3_client):
    backend = TigrisBackend()
    result = backend.delete_bucket("gone")
    assert result == {"name": "gone", "status": "deleted"}
    mock_boto3_client.delete_bucket.assert_called_once_with(Bucket="gone")


def test_head_bucket(mock_boto3_client):
    backend = TigrisBackend(endpoint="https://example.test")
    result = backend.head_bucket("my-bucket")
    assert result["name"] == "my-bucket"
    assert result["exists"] is True
    assert result["endpoint"] == "https://example.test"


def test_list_objects(mock_boto3_client):
    mock_boto3_client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "foo.txt",
                "Size": 12,
                "LastModified": _now_iso(),
                "ETag": '"abc123"',
            }
        ]
    }
    backend = TigrisBackend()
    result = backend.list_objects("b", prefix="foo", limit=10)
    assert len(result) == 1
    assert result[0]["key"] == "foo.txt"
    assert result[0]["size"] == 12
    assert result[0]["etag"] == "abc123"  # quotes stripped


def test_put_object_inline(mock_boto3_client):
    mock_boto3_client.put_object.return_value = {"ETag": '"deadbeef"'}
    backend = TigrisBackend()
    result = backend.put_object("b", "k", b"hello", content_type="text/plain")
    assert result == {"bucket": "b", "key": "k", "etag": "deadbeef"}


def test_get_object(mock_boto3_client):
    body = MagicMock()
    body.read.return_value = b"contents"
    mock_boto3_client.get_object.return_value = {"Body": body}
    backend = TigrisBackend()
    assert backend.get_object("b", "k") == b"contents"


def test_head_object(mock_boto3_client):
    mock_boto3_client.head_object.return_value = {
        "ContentLength": 42,
        "ContentType": "application/json",
        "ETag": '"xyz"',
        "LastModified": _now_iso(),
    }
    backend = TigrisBackend()
    result = backend.head_object("b", "k")
    assert result["size"] == 42
    assert result["content_type"] == "application/json"
    assert result["etag"] == "xyz"


def test_copy_object(mock_boto3_client):
    backend = TigrisBackend()
    result = backend.copy_object("src-b", "src-k", "dst-b", "dst-k")
    assert result["src"] == "src-b/src-k"
    assert result["dst"] == "dst-b/dst-k"
    mock_boto3_client.copy_object.assert_called_once_with(
        CopySource={"Bucket": "src-b", "Key": "src-k"},
        Bucket="dst-b",
        Key="dst-k",
    )


def test_presign_get(mock_boto3_client):
    mock_boto3_client.generate_presigned_url.return_value = "https://signed/url"
    backend = TigrisBackend()
    url = backend.presign_get("b", "k", expires_in=600)
    assert url == "https://signed/url"
    mock_boto3_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "b", "Key": "k"},
        ExpiresIn=600,
    )


def test_presign_put_with_content_type(mock_boto3_client):
    mock_boto3_client.generate_presigned_url.return_value = "https://put/url"
    backend = TigrisBackend()
    url = backend.presign_put("b", "k", expires_in=300, content_type="image/png")
    assert url == "https://put/url"
    args, kwargs = mock_boto3_client.generate_presigned_url.call_args
    assert kwargs["Params"]["ContentType"] == "image/png"


# ── CLI integration tests (backend mocked end-to-end) ────────────────


def _make_ctx_obj(backend_mock):
    skin = MagicMock()
    return {"backend": backend_mock, "skin": skin, "json": True}


def test_cli_bucket_list_json(mock_boto3_client):
    mock_boto3_client.list_buckets.return_value = {
        "Buckets": [{"Name": "demo", "CreationDate": _now_iso()}]
    }
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "bucket", "list"])
    assert result.exit_code == 0
    assert "demo" in result.output


def test_cli_object_put_requires_file_or_text():
    runner = CliRunner()
    # Neither --file nor --text — must error
    result = runner.invoke(
        cli, ["--json", "object", "put", "--bucket", "b", "--key", "k"]
    )
    assert result.exit_code != 0


def test_cli_presign_get_json(mock_boto3_client):
    mock_boto3_client.generate_presigned_url.return_value = "https://signed"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "presign", "get", "--bucket", "b", "--key", "k"],
    )
    assert result.exit_code == 0
    assert "https://signed" in result.output


# ── tigris:// URI parsing ────────────────────────────────────────────


def test_tigris_uri_parsing_round_trip():
    from cli_anything.tigris.core.object import _parse_tigris_uri

    bucket, key = _parse_tigris_uri("tigris://my-bucket/path/to/file.txt")
    assert bucket == "my-bucket"
    assert key == "path/to/file.txt"


def test_tigris_uri_parsing_rejects_bad_input():
    from cli_anything.tigris.core.object import _parse_tigris_uri
    import click

    for bad in ("s3://b/k", "tigris://nokey", "tigris:///nobucket", "plainpath"):
        with pytest.raises(click.UsageError):
            _parse_tigris_uri(bad)
