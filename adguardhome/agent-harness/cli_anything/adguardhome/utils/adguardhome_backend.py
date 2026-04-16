"""AdGuardHome HTTP API client - wraps all REST calls to the real AdGuardHome service."""

from typing import Any

import requests


class AdGuardHomeClient:
    """HTTP client for the AdGuardHome REST API."""

    def __init__(self, host: str = "localhost", port: int = 3000,
                 username: str = "", password: str = "", https: bool = False):
        scheme = "https" if https else "http"
        # Auto-detect HTTPS for standard ports
        if port == 443:
            scheme = "https"
        self.base_url = f"{scheme}://{host}:{port}/control" if port not in (80, 443) else f"{scheme}://{host}/control"
        self.host = host
        self.port = port
        self.session = requests.Session()
        if username or password:
            self.session.auth = (username, password)
        self.session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _handle_response(self, resp: requests.Response) -> Any:
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def _connection_error(self, e: Exception) -> RuntimeError:
        return RuntimeError(
            f"Cannot connect to AdGuardHome at {self.base_url}.\n"
            f"Ensure AdGuardHome is running and accessible.\n"
            f"Install: curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sh -s -- -v\n"
            f"Or Docker: docker run --name adguardhome -p {self.port}:{self.port} adguard/adguardhome\n"
            f"Error: {e}"
        )

    def get(self, path: str, params: dict | None = None) -> Any:
        """GET request - returns deserialized JSON or raw text."""
        try:
            resp = self.session.get(self._url(path), params=params, timeout=10)
            resp.raise_for_status()
            return self._handle_response(resp)
        except requests.exceptions.ConnectionError as e:
            raise self._connection_error(e)

    def post(self, path: str, data: Any = None) -> Any:
        """POST request - sends JSON body, returns deserialized response."""
        try:
            if isinstance(data, (dict, list)):
                resp = self.session.post(self._url(path), json=data, timeout=10)
            elif isinstance(data, str):
                resp = self.session.post(
                    self._url(path), data=data.encode(),
                    headers={**dict(self.session.headers), "Content-Type": "text/plain"},
                    timeout=10,
                )
            else:
                resp = self.session.post(self._url(path), timeout=10)
            resp.raise_for_status()
            return self._handle_response(resp)
        except requests.exceptions.ConnectionError as e:
            raise self._connection_error(e)
