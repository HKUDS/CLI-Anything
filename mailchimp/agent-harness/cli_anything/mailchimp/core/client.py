"""Mailchimp Marketing API v3.0 HTTP client."""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Any

import requests

_BASE = "https://{dc}.api.mailchimp.com/3.0"
_DEFAULT_TIMEOUT = 30


def _server_prefix(api_key: str) -> str:
    """Derive the data-centre prefix from the API key suffix (e.g. 'us8')."""
    if "-" not in api_key:
        raise ValueError(
            "MAILCHIMP_API_KEY must include the data-centre suffix, "
            "e.g. 'abc123-us8'."
        )
    return api_key.rsplit("-", 1)[-1]


def subscriber_hash(email: str) -> str:
    """MD5 hash of the lowercased email — Mailchimp's subscriber identifier."""
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


class MailchimpAuthError(Exception):
    """Raised when no API key is available."""


class MailchimpError(Exception):
    def __init__(self, status: int, title: str, detail: str, raw: dict):
        super().__init__(f"HTTP {status}: {title} — {detail}")
        self.status = status
        self.title = title
        self.detail = detail
        self.raw = raw


class MailchimpClient:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("MAILCHIMP_API_KEY", "")
        if not key:
            raise MailchimpAuthError(
                "MAILCHIMP_API_KEY is not set. "
                "Export it before use: export MAILCHIMP_API_KEY=<key>-<dc>"
            )
        self._key = key
        try:
            self._dc = _server_prefix(key)
        except ValueError as e:
            raise MailchimpAuthError(str(e)) from e
        self._base = _BASE.format(dc=self._dc)
        self._session = requests.Session()
        self._session.auth = ("anystring", key)
        self._session.headers.update({"User-Agent": "cli-anything-mailchimp/0.1.0"})

    # ── Low-level request helpers ──────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def _raise(self, resp: requests.Response) -> None:
        if resp.ok:
            return
        try:
            body = resp.json()
            raise MailchimpError(
                status=resp.status_code,
                title=body.get("title", resp.reason),
                detail=body.get("detail", ""),
                raw=body,
            )
        except ValueError:
            raise MailchimpError(
                status=resp.status_code,
                title=resp.reason,
                detail=resp.text[:200],
                raw={},
            )

    def get(self, path: str, params: dict | None = None) -> Any:
        resp = self._session.get(self._url(path), params=params, timeout=_DEFAULT_TIMEOUT)
        self._raise(resp)
        return resp.json()

    def post(self, path: str, json: dict | None = None, params: dict | None = None) -> Any:
        resp = self._session.post(
            self._url(path), json=json, params=params, timeout=_DEFAULT_TIMEOUT
        )
        self._raise(resp)
        if resp.status_code == 204:
            return {}
        return resp.json()

    def patch(self, path: str, json: dict | None = None, params: dict | None = None) -> Any:
        resp = self._session.patch(
            self._url(path), json=json, params=params, timeout=_DEFAULT_TIMEOUT
        )
        self._raise(resp)
        return resp.json()

    def put(self, path: str, json: dict | None = None, params: dict | None = None) -> Any:
        resp = self._session.put(
            self._url(path), json=json, params=params, timeout=_DEFAULT_TIMEOUT
        )
        self._raise(resp)
        return resp.json()

    def delete(self, path: str, params: dict | None = None) -> dict:
        resp = self._session.delete(
            self._url(path), params=params, timeout=_DEFAULT_TIMEOUT
        )
        self._raise(resp)
        return {"ok": True}


def get_client() -> MailchimpClient:
    """Return a client instance, printing an error and exiting if key is missing."""
    try:
        return MailchimpClient()
    except MailchimpAuthError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)
