"""HTTP video download adapter."""

from pathlib import Path
from urllib.request import Request, urlopen


class HttpVideoDownloader:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    def download(self, source: str, destination: Path) -> Path:
        request = Request(source, headers={"User-Agent": "cli-anything-shotcut"})
        with urlopen(request, timeout=self._timeout_seconds) as response:
            destination.write_bytes(response.read())
        return destination
