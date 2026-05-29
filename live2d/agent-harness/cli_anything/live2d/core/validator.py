"""Validate Live2D model file integrity."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .parser import ModelInfo
from .moc3_parser import load_moc3


DEFAULT_MIN_MOC3_SIZE = 1024


@dataclass
class ValidationResult:
    model_path: Path
    checked: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            "model": str(self.model_path),
            "ok": self.ok,
            "checked": self.checked,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_model(
    info: ModelInfo,
    strict: bool = False,
    min_moc3_size: int = DEFAULT_MIN_MOC3_SIZE,
) -> ValidationResult:
    """Check that all referenced files exist.

    Strict mode adds production-export checks so template placeholders do not
    accidentally pass as usable Live2D runtime assets.
    """
    result = ValidationResult(model_path=info.path)
    model_dir = info.path.parent

    def check(rel_path: str, label: str) -> Optional[Path]:
        if not rel_path:
            return None
        result.checked += 1
        full = model_dir / rel_path
        if not full.exists():
            result.errors.append(f"Missing {label}: {rel_path}")
            return None
        return full

    # Moc3
    moc3_path = check(info.moc3, "Moc3")
    if moc3_path and strict:
        moc3 = load_moc3(moc3_path)
        if not moc3.valid:
            result.errors.append(f"Invalid Moc3 header: {info.moc3}")
        elif moc3.file_size < min_moc3_size:
            result.errors.append(
                f"Moc3 too small: {info.moc3} ({moc3.file_size}B, minimum {min_moc3_size}B)"
            )

    # Textures
    for tex in info.textures:
        tex_path = check(tex, "Texture")
        if strict and tex_path and tex_path.stat().st_size == 0:
            result.errors.append(f"Empty Texture: {tex}")

    # Physics / Pose / UserData
    check(info.physics, "Physics")
    check(info.pose, "Pose")
    check(info.userdata, "UserData")
    check(info.display_info, "DisplayInfo")

    # Expressions
    for expr in info.expressions:
        check(expr.file, f"Expression[{expr.name}]")

    # Motions
    for group, motions in info.motions.items():
        for m in motions:
            check(m.file, f"Motion[{group}]")

    # Warnings
    if not info.moc3:
        if strict:
            result.errors.append("No Moc3 file specified")
        else:
            result.warnings.append("No Moc3 file specified")
    if not info.textures:
        if strict:
            result.errors.append("No textures specified")
        else:
            result.warnings.append("No textures specified")

    return result


def validate_all(infos: list[ModelInfo], strict: bool = False) -> list[ValidationResult]:
    """Validate multiple models."""
    return [validate_model(info, strict=strict) for info in infos]
