"""File operations for RMS API."""
from __future__ import annotations
import os
import requests
from cli_anything.rms.utils.rms_backend import (
    api_get, api_post, api_delete,
    API_BASE, _require_api_token, _make_auth_headers, _handle_response,
)


def list_files(token, limit=25, offset=0):
    return api_get("/files", params={"limit": limit, "offset": offset}, token=token)


def get_file(token, file_id):
    return api_get(f"/files/{file_id}", token=token)


def upload_file(token, file_path, data=None):
    """Upload a file. Uses multipart form data."""
    token = _require_api_token(token)
    headers = _make_auth_headers(token)
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        resp = requests.post(f"{API_BASE}/files", files=files, data=data, headers=headers, timeout=60)
    return _handle_response(resp)


def delete_file(token, file_id):
    return api_delete(f"/files/{file_id}", token=token)
