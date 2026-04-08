from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..core.types import JsonDict


class ApiError(RuntimeError):
    """Raised when the local game bridge returns an error."""


class Sts2RawClient:
    def __init__(self, base_url: str = "http://localhost:15526", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def singleplayer_url(self) -> str:
        return f"{self.base_url}/api/v1/singleplayer"

    def get_state(self, *, format: str = "json") -> JsonDict | str:
        query = urllib.parse.urlencode({"format": format})
        url = f"{self.singleplayer_url}?{query}"
        return self._request_json("GET", url) if format == "json" else self._request_text("GET", url)

    def post_action(self, action: str, **payload: Any) -> JsonDict:
        if "action" in payload:
            raise ValueError("`action` must be provided as the first argument to post_action, not in **payload")
        body: JsonDict = {**payload, "action": action}
        return self._request_json("POST", self.singleplayer_url, body)

    def _request_text(self, method: str, url: str, body: JsonDict | None = None) -> str:
        req = urllib.request.Request(url, method=method)
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        else:
            data = None

        try:
            with urllib.request.urlopen(req, data=data, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise ApiError(f"HTTP {exc.code}: {text}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(
                "Cannot connect to the game bridge API. Is the game running with the bridge mod enabled?"
            ) from exc

    def _request_json(self, method: str, url: str, body: JsonDict | None = None) -> JsonDict:
        text = self._request_text(method, url, body)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ApiError(f"Expected JSON response, got: {text[:200]}") from exc
        if not isinstance(data, dict):
            raise ApiError(f"Expected object response, got: {type(data).__name__}")
        return data
