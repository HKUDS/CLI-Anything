"""Thin wrapper around requests for WireMock admin API calls."""
import requests
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WireMockClient:
    host: str = "localhost"
    port: int = 8080
    scheme: str = "http"
    admin_prefix: str = "/__admin"
    auth: Optional[tuple] = None
    timeout: int = 30

    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}{self.admin_prefix}"

    def get(self, path: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        return requests.get(
            f"{self.base_url()}{path}", auth=self.auth, timeout=timeout, **kwargs
        )

    def post(self, path: str, json=None, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        return requests.post(
            f"{self.base_url()}{path}",
            json=json,
            auth=self.auth,
            timeout=timeout,
            **kwargs,
        )

    def put(self, path: str, json=None, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        return requests.put(
            f"{self.base_url()}{path}",
            json=json,
            auth=self.auth,
            timeout=timeout,
            **kwargs,
        )

    def delete(self, path: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        return requests.delete(
            f"{self.base_url()}{path}", auth=self.auth, timeout=timeout, **kwargs
        )

    def patch(self, path: str, json=None, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        return requests.patch(
            f"{self.base_url()}{path}",
            json=json,
            auth=self.auth,
            timeout=timeout,
            **kwargs,
        )

    def is_alive(self) -> bool:
        try:
            r = self.get("/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False
