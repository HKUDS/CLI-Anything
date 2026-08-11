"""Generic HTTP file downloader."""

import os
from pathlib import Path
from urllib.request import Request, urlopen


class HttpFileDownloader:
    def __init__(self, timeout_seconds: float = 60.0) -> None:
        self._timeout_seconds = timeout_seconds

    def download(self, source_url: str, output_path: Path, overwrite: bool = False) -> Path:
        output_path = output_path.expanduser().resolve()
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Output file already exists: {output_path}")
        if not output_path.parent.is_dir():
            raise FileNotFoundError(f"Output directory not found: {output_path.parent}")

        partial_path = output_path.with_name(f".{output_path.name}.part")
        request = Request(source_url, headers={"User-Agent": "cli-anything-shotcut"})
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                with partial_path.open("wb") as output_file:
                    while chunk := response.read(1024 * 1024):
                        output_file.write(chunk)
            os.replace(partial_path, output_path)
        except Exception:
            partial_path.unlink(missing_ok=True)
            raise
        return output_path
