"""Framework-neutral media download models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DownloadRequest:
    source_url: str
    output_path: Path
    overwrite: bool = False


@dataclass(frozen=True)
class ResolvedMedia:
    source_url: str
    media_url: str
    platform: str
    media_type: str = "video"


@dataclass(frozen=True)
class DownloadResult:
    source_url: str
    output_path: Path
    platform: str
    media_type: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_url": self.source_url,
            "output_path": str(self.output_path),
            "platform": self.platform,
            "media_type": self.media_type,
        }
