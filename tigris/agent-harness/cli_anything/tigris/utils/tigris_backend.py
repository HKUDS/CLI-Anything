"""Tigris S3-compatible API client.

Talks to Tigris via the S3 protocol using boto3. Tigris is a globally
distributed object storage service with no egress fees — see
https://www.tigrisdata.com.

Default endpoint: https://t3.storage.dev
Credentials: standard AWS credential chain (env vars, ~/.aws/credentials, etc.)
  - AWS_ACCESS_KEY_ID or TIGRIS_STORAGE_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY or TIGRIS_STORAGE_SECRET_ACCESS_KEY
"""

import os
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

import boto3
from botocore.client import Config

DEFAULT_ENDPOINT = "https://t3.storage.dev"


class TigrisBackend:
    """S3-compatible client for Tigris object storage."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "auto",
    ):
        self.endpoint = endpoint.rstrip("/")
        # Prefer explicit args, then TIGRIS_STORAGE_*, then standard AWS_*
        access_key = (
            access_key
            or os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
            or os.environ.get("AWS_ACCESS_KEY_ID")
        )
        secret_key = (
            secret_key
            or os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
            or os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    # ── Buckets ───────────────────────────────────────────────────────

    def list_buckets(self) -> list[dict]:
        """List all buckets owned by the authenticated account."""
        resp = self._client.list_buckets()
        return [
            {"name": b["Name"], "created": b["CreationDate"].isoformat()}
            for b in resp.get("Buckets", [])
        ]

    def create_bucket(self, name: str) -> dict:
        """Create a new bucket."""
        self._client.create_bucket(Bucket=name)
        return {"name": name, "status": "created"}

    def delete_bucket(self, name: str) -> dict:
        """Delete an empty bucket."""
        self._client.delete_bucket(Bucket=name)
        return {"name": name, "status": "deleted"}

    def head_bucket(self, name: str) -> dict:
        """Check bucket exists and return basic info."""
        self._client.head_bucket(Bucket=name)
        return {"name": name, "exists": True, "endpoint": self.endpoint}

    # ── Objects ───────────────────────────────────────────────────────

    def list_objects(
        self, bucket: str, prefix: str | None = None, limit: int = 100
    ) -> list[dict]:
        """List objects in a bucket. Returns at most `limit` results."""
        kwargs: dict[str, Any] = {"Bucket": bucket, "MaxKeys": limit}
        if prefix:
            kwargs["Prefix"] = prefix
        resp = self._client.list_objects_v2(**kwargs)
        return [
            {
                "key": o["Key"],
                "size": o["Size"],
                "modified": o["LastModified"].isoformat(),
                "etag": o.get("ETag", "").strip('"'),
            }
            for o in resp.get("Contents", [])
        ]

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes | BinaryIO,
        content_type: str | None = None,
    ) -> dict:
        """Upload an object."""
        kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": body}
        if content_type:
            kwargs["ContentType"] = content_type
        resp = self._client.put_object(**kwargs)
        return {
            "bucket": bucket,
            "key": key,
            "etag": resp.get("ETag", "").strip('"'),
        }

    def put_object_from_file(
        self, bucket: str, key: str, file_path: str
    ) -> dict:
        """Upload from a local file path."""
        with open(file_path, "rb") as f:
            return self.put_object(bucket, key, f)

    def get_object(self, bucket: str, key: str) -> bytes:
        """Download an object's body as bytes."""
        resp = self._client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def get_object_to_file(self, bucket: str, key: str, file_path: str) -> dict:
        """Download an object to a local file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(bucket, key, str(path))
        return {"bucket": bucket, "key": key, "path": str(path)}

    def delete_object(self, bucket: str, key: str) -> dict:
        """Delete an object."""
        self._client.delete_object(Bucket=bucket, Key=key)
        return {"bucket": bucket, "key": key, "status": "deleted"}

    def head_object(self, bucket: str, key: str) -> dict:
        """Get object metadata without downloading the body."""
        resp = self._client.head_object(Bucket=bucket, Key=key)
        return {
            "bucket": bucket,
            "key": key,
            "size": resp.get("ContentLength", 0),
            "content_type": resp.get("ContentType", ""),
            "etag": resp.get("ETag", "").strip('"'),
            "modified": resp["LastModified"].isoformat()
            if resp.get("LastModified")
            else None,
        }

    def copy_object(
        self,
        src_bucket: str,
        src_key: str,
        dst_bucket: str,
        dst_key: str,
    ) -> dict:
        """Server-side copy from one bucket/key to another (no egress)."""
        self._client.copy_object(
            CopySource={"Bucket": src_bucket, "Key": src_key},
            Bucket=dst_bucket,
            Key=dst_key,
        )
        return {
            "src": f"{src_bucket}/{src_key}",
            "dst": f"{dst_bucket}/{dst_key}",
            "status": "copied",
        }

    # ── Presigned URLs ────────────────────────────────────────────────

    def presign_get(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading an object."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def presign_put(
        self,
        bucket: str,
        key: str,
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> str:
        """Generate a presigned URL for uploading an object."""
        params: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        return self._client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
        )
