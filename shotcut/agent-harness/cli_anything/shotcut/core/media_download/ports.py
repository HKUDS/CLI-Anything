"""Dependency-injection ports for media downloading."""

from pathlib import Path
from typing import Protocol

from .models import ResolvedMedia


class MediaResolver(Protocol):
    platform: str

    def can_resolve(self, source_url: str) -> bool:
        """Return whether this resolver supports the source URL."""

    def resolve(self, source_url: str) -> ResolvedMedia:
        """Resolve a platform URL to a direct media URL."""


class FileDownloader(Protocol):
    def download(self, source_url: str, output_path: Path, overwrite: bool = False) -> Path:
        """Download a direct media URL to a local file."""


class BrightDataApi(Protocol):
    def trigger(self, dataset_id: str, source_url: str) -> str:
        """Start a BrightData dataset job and return its snapshot ID."""

    def wait_for_snapshot(self, snapshot_id: str) -> list[dict[str, object]]:
        """Wait for and return BrightData snapshot records."""
