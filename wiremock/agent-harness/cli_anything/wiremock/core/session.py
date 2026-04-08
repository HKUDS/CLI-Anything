"""Session state: stores connection parameters, loaded from env or CLI options."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Session:
    host: str = "localhost"
    port: int = 8080
    scheme: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Session":
        try:
            port = int(os.environ.get("WIREMOCK_PORT", "8080"))
        except ValueError:
            port = 8080
        return cls(
            host=os.environ.get("WIREMOCK_HOST", "localhost"),
            port=port,
            scheme=os.environ.get("WIREMOCK_SCHEME", "http"),
            username=os.environ.get("WIREMOCK_USER"),
            password=os.environ.get("WIREMOCK_PASSWORD"),
        )

    def auth(self):
        if self.username and self.password:
            return (self.username, self.password)
        return None
