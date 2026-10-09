"""
Session management for JumpServer CLI.

Manages API connection state, authentication tokens, and session persistence.
"""
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SESSION_FILE = Path.home() / ".jumpserver-cli" / "session.json"


@dataclass
class Session:
    """JumpServer API session state."""

    base_url: str = ""
    username: str = ""
    token: str = ""
    token_expiry: float = 0.0
    refresh_token: str = ""
    org_id: str = ""
    org_name: str = ""
    verify_ssl: bool = True
    timeout: int = 60
    # "Signature" = permanent AccessKey (keyid+secret, HMAC http-signature;
    #                 the API auth JMS v4 offers end users);
    # "Token" = PrivateToken / legacy default; "Bearer" = v4 session JWT.
    auth_scheme: str = "Token"
    access_key_id: str = ""
    _current_user: dict[str, Any] | None = field(default=None, repr=False)

    def save(self) -> None:
        """Persist session to disk."""
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("_current_user", None)
        SESSION_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> "Session":
        """Load session from disk, returns empty session if not found."""
        if SESSION_FILE.exists():
            try:
                data = json.loads(SESSION_FILE.read_text())
                data.pop("_current_user", None)
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def clear(self) -> None:
        """Remove persisted session."""
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()

    def is_authenticated(self) -> bool:
        """Check if the session has a valid token."""
        if not self.token:
            return False
        if self.token_expiry and time.time() > self.token_expiry:
            return False
        return True

    def get_client(self) -> "JumpServerClient":
        """Get an API client configured with this session."""
        return JumpServerClient(self)


class JumpServerClient:
    """HTTP client for JumpServer REST API with retry support."""

    def __init__(self, session: Session):
        self.session = session
        self._http = requests.Session()
        self._http.verify = session.verify_ssl
        self._http.timeout = session.timeout

        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            # Return the final response instead of raising
            # MaxRetryError, so callers can show the server's real error
            # body (e.g. JMS returns 500 on unknown AccessKey keyId).
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._http.mount("http://", adapter)
        self._http.mount("https://", adapter)

    @property
    def headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.session.token:
            h["Authorization"] = f"{self.session.auth_scheme} {self.session.token}"
        if self.session.org_id:
            h["X-JMS-ORG"] = self.session.org_id
        return h

    def _url(self, path: str) -> str:
        base = self.session.base_url.rstrip("/")
        return f"{base}/api/v1/{path.lstrip('/')}"

    def request(
        self, method: str, path: str, **kwargs
    ) -> requests.Response:
        url = self._url(path)
        if self.session.auth_scheme == "Signature" and self.session.access_key_id:
            from urllib.parse import urlparse, urlencode
            from cli_anything.jumpserver.utils import httpsig_auth
            parts = urlparse(url)
            # Fold params into the URL BEFORE signing so the signed
            # (request-target) exactly matches what goes on the wire —
            # HeaderVerifier validates against the server's full path+query.
            params = kwargs.pop("params", None)
            query = parts.query
            if params:
                clean = {k: v for k, v in params.items() if v is not None}
                if clean:
                    q = urlencode(clean, doseq=True)
                    query = (query + "&" + q) if query else q
            path_with_query = parts.path + (("?" + query) if query else "")
            if query != parts.query:
                url = "%s://%s%s?%s" % (parts.scheme, parts.netloc,
                                        parts.path, query)
            sig_headers = httpsig_auth.sign(
                method=method,
                path_with_query=path_with_query,
                key_id=self.session.access_key_id,
                secret=self.session.token,
            )
            base = self.headers
            base.pop("Authorization", None)
            base.update(sig_headers)
            kwargs.setdefault("headers", base)
            return self._http.request(method, url, **kwargs)
        kwargs.setdefault("headers", self.headers)
        return self._http.request(method, url, **kwargs)

    def get(self, path: str, params: dict | None = None) -> requests.Response:
        return self.request("GET", path, params=params)

    def post(
        self, path: str, data: dict | None = None
    ) -> requests.Response:
        return self.request("POST", path, json=data)

    def put(
        self, path: str, data: dict | None = None
    ) -> requests.Response:
        return self.request("PUT", path, json=data)

    def patch(
        self, path: str, data: dict | None = None
    ) -> requests.Response:
        return self.request("PATCH", path, json=data)

    def delete(self, path: str) -> requests.Response:
        return self.request("DELETE", path)

    def login(
        self, username: str, password: str
    ) -> dict[str, Any]:
        """Authenticate and store token."""
        resp = self.post(
            "authentication/auth/",
            data={"username": username, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.session.token = data.get("token", "")
        self.session.username = username
        self.session.token_expiry = time.time() + 3600  # default 1h
        self.session.save()
        return data

    def logout(self) -> None:
        """Invalidate the session."""
        self.session.clear()

    def get_current_user(self) -> dict[str, Any]:
        """Get current authenticated user profile.

        If the configured auth scheme is rejected (401/403) and a token is
        present, retry once with Token<->Bearer fallback and persist the
        scheme that works. Signature mode tries Bearer fallback last.
        """
        resp = self.get("users/profile/")
        if resp.status_code in (401, 403) and self.session.token:
            order = (["Bearer", "Token"] if self.session.auth_scheme == "Signature"
                     else ["Token"] if self.session.auth_scheme == "Bearer"
                     else ["Bearer"])
            saved = self.session.auth_scheme
            for alt in order:
                self.session.auth_scheme = alt
                if alt == "Signature":
                    continue
                resp = self.get("users/profile/")
                if resp.status_code == 200:
                    self.session.auth_scheme = alt
                    self.session.save()
                    break
            else:
                self.session.auth_scheme = saved
                resp = self.get("users/profile/")
        if resp.status_code >= 400:
            body = (resp.text or "").strip()[:200]
            raise RuntimeError(
                "auth check failed HTTP %s (%s): %s"
                % (resp.status_code, self.session.auth_scheme, body))
        return resp.json()

    def paginate(
        self, path: str, params: dict | None = None, limit: int = 100
    ):
        """Generator that yields results across all pages."""
        params = (params or {}).copy()
        params.setdefault("limit", limit)
        params.setdefault("offset", 0)

        while True:
            resp = self.get(path, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data if isinstance(data, list) else [])
            if not results:
                break
            yield from results
            if len(results) < limit:
                break
            params["offset"] += len(results)
