"""Parse Live2D .moc3 binary file header."""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class Moc3Info:
    path: Path
    valid: bool = False
    version: int = 0
    file_size: int = 0

    def to_dict(self) -> dict:
        return {
            "file": str(self.path),
            "valid": self.valid,
            "version": self.version,
            "file_size": self.file_size,
            "file_size_display": self._size_display(),
        }

    def _size_display(self) -> str:
        s = self.file_size
        if s < 1024:
            return f"{s}B"
        elif s < 1024 * 1024:
            return f"{s / 1024:.1f}KB"
        else:
            return f"{s / (1024*1024):.1f}MB"


def load_moc3(path: Path) -> Moc3Info:
    """Load and parse a .moc3 binary file header."""
    info = Moc3Info(path=path)

    if not path.exists():
        return info

    info.file_size = path.stat().st_size

    with open(path, "rb") as f:
        header = f.read(8)

        if len(header) < 8:
            return info

        # Magic: "MOC3"
        magic = header[:4]
        if magic != b"MOC3":
            return info

        info.valid = True
        info.version = int.from_bytes(header[4:8], "little")

    return info
