"""Package a Live2D model into a zip archive."""

import zipfile
from pathlib import Path
from dataclasses import dataclass

from .parser import ModelInfo


@dataclass
class PackageResult:
    output_path: Path
    files_count: int = 0
    total_size: int = 0
    missing_files: list[str] = None

    def __post_init__(self):
        if self.missing_files is None:
            self.missing_files = []

    def to_dict(self) -> dict:
        return {
            "output": str(self.output_path),
            "files_count": self.files_count,
            "total_size": self.total_size,
            "total_size_display": self._size_display(),
            "missing_files": self.missing_files,
        }

    def _size_display(self) -> str:
        s = self.total_size
        if s < 1024:
            return f"{s}B"
        elif s < 1024 * 1024:
            return f"{s / 1024:.1f}KB"
        else:
            return f"{s / (1024*1024):.1f}MB"


def package_model(info: ModelInfo, output_path: Path, include_motions: bool = True,
                   include_expressions: bool = True) -> PackageResult:
    """Package a model and all its dependencies into a zip."""
    model_dir = info.path.parent
    result = PackageResult(output_path=output_path)

    # Collect all files to include
    files = set()

    # Model file itself
    files.add(info.path)

    # Moc3
    if info.moc3:
        moc3_path = model_dir / info.moc3
        if moc3_path.exists():
            files.add(moc3_path)
        else:
            result.missing_files.append(info.moc3)

    # Textures
    for tex in info.textures:
        tex_path = model_dir / tex
        if tex_path.exists():
            files.add(tex_path)
        else:
            result.missing_files.append(tex)

    # Physics
    if info.physics:
        phys_path = model_dir / info.physics
        if phys_path.exists():
            files.add(phys_path)
        else:
            result.missing_files.append(info.physics)

    # Pose
    if info.pose:
        pose_path = model_dir / info.pose
        if pose_path.exists():
            files.add(pose_path)
        else:
            result.missing_files.append(info.pose)

    # UserData
    if info.userdata:
        ud_path = model_dir / info.userdata
        if ud_path.exists():
            files.add(ud_path)
        else:
            result.missing_files.append(info.userdata)

    # DisplayInfo
    if info.display_info:
        di_path = model_dir / info.display_info
        if di_path.exists():
            files.add(di_path)
        else:
            result.missing_files.append(info.display_info)

    # Motions
    if include_motions:
        for group, motions in info.motions.items():
            for m in motions:
                m_path = model_dir / m.file
                if m_path.exists():
                    files.add(m_path)
                else:
                    result.missing_files.append(m.file)
                # Include Sound files referenced in motions
                sound = m.extra.get("Sound") if hasattr(m, 'extra') else None
                if sound:
                    s_path = model_dir / sound
                    if s_path.exists():
                        files.add(s_path)
                    else:
                        result.missing_files.append(sound)

    # Expressions
    if include_expressions:
        for expr in info.expressions:
            e_path = model_dir / expr.file
            if e_path.exists():
                files.add(e_path)
            else:
                result.missing_files.append(expr.file)

    # Create zip
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(files):
            arcname = f.relative_to(model_dir)
            zf.write(f, arcname)
            result.files_count += 1
            result.total_size += f.stat().st_size

    return result
