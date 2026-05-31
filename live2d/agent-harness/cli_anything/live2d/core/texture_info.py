"""Get texture image dimensions and metadata."""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class TextureInfo:
    path: Path
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    format: str = ""

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000

    @property
    def size_display(self) -> str:
        s = self.size_bytes
        if s < 1024:
            return f"{s}B"
        elif s < 1024 * 1024:
            return f"{s / 1024:.1f}KB"
        else:
            return f"{s / (1024*1024):.1f}MB"

    def to_dict(self) -> dict:
        return {
            "file": str(self.path),
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "size_display": self.size_display,
            "format": self.format,
            "megapixels": round(self.megapixels, 2),
        }


def get_texture_info(path: Path) -> TextureInfo:
    """Get texture dimensions and metadata."""
    info = TextureInfo(path=path)

    if not path.exists():
        return info

    info.size_bytes = path.stat().st_size
    info.format = path.suffix.lower().lstrip(".")

    # Try PIL for dimensions
    try:
        from PIL import Image
        with Image.open(path) as img:
            info.width, info.height = img.size
    except ImportError:
        # Fallback: read PNG/JPEG headers directly
        _read_dimensions_fallback(path, info)
    except Exception:
        # Pillow found the file but can't identify it (corrupt/placeholder)
        _read_dimensions_fallback(path, info)

    return info


def _read_dimensions_fallback(path: Path, info: TextureInfo):
    """Read image dimensions from file headers without PIL."""
    try:
        with open(path, "rb") as f:
            header = f.read(32)

            # PNG
            if header[:8] == b'\x89PNG\r\n\x1a\n':
                info.width = int.from_bytes(header[16:20], 'big')
                info.height = int.from_bytes(header[20:24], 'big')
                info.format = "png"

            # JPEG
            elif header[:2] == b'\xff\xd8':
                f.seek(0)
                data = f.read()
                i = 2
                while i < len(data) - 1:
                    if data[i] == 0xFF:
                        marker = data[i + 1]
                        if marker in (0xC0, 0xC1, 0xC2):
                            info.height = int.from_bytes(data[i + 5:i + 7], 'big')
                            info.width = int.from_bytes(data[i + 7:i + 9], 'big')
                            info.format = "jpeg"
                            break
                        elif marker == 0xD9:
                            break
                        else:
                            length = int.from_bytes(data[i + 2:i + 4], 'big')
                            i += 2 + length
                    else:
                        i += 1

            # WebP
            elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                if header[12:16] == b'VP8 ':
                    f.seek(26)
                    dims = f.read(4)
                    info.width = int.from_bytes(dims[:2], 'little') & 0x3FFF
                    info.height = int.from_bytes(dims[2:4], 'little') & 0x3FFF
                    info.format = "webp"
                elif header[12:16] == b'VP8L':
                    f.seek(25)
                    bits = int.from_bytes(f.read(4), 'little')
                    info.width = (bits & 0x3FFF) + 1
                    info.height = ((bits >> 14) & 0x3FFF) + 1
                    info.format = "webp"

    except Exception:
        pass
