"""Yoyo-specific Live2D export checks."""

from dataclasses import dataclass, field
from pathlib import Path

from .parser import ModelInfo, load_model
from .validator import ValidationResult, validate_model


DEFAULT_REQUIRED_MOTION_GROUPS = ("idle",)


@dataclass
class YoyoExportReport:
    model: ModelInfo
    validation: ValidationResult
    required_motion_groups: tuple[str, ...] = DEFAULT_REQUIRED_MOTION_GROUPS
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def summary(self) -> dict:
        return {
            "model_file": str(self.model.path),
            "moc3": self.model.moc3,
            "texture_count": self.model.texture_count,
            "motion_count": self.model.motion_count,
            "motion_groups": sorted(self.model.motions.keys()),
            "expression_count": self.model.expression_count,
        }

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "required_motion_groups": list(self.required_motion_groups),
            "errors": self.errors,
            "warnings": self.warnings,
            "validation": self.validation.to_dict(),
        }


def check_yoyo_export(
    model_path: Path,
    required_motion_groups: tuple[str, ...] = DEFAULT_REQUIRED_MOTION_GROUPS,
) -> YoyoExportReport:
    """Validate a Live2D export against the minimum Yoyo desktop-pet contract."""
    info = load_model(model_path)
    validation = validate_model(info, strict=True)
    errors = list(validation.errors)
    warnings = list(validation.warnings)

    available_groups = {name.strip().lower() for name in info.motions}
    for group in required_motion_groups:
        normalized = group.strip().lower()
        if normalized and normalized not in available_groups:
            errors.append(f"Missing required motion group: {normalized}")

    if info.expression_count == 0:
        warnings.append("No expressions found; Yoyo can run, but interactions will feel flat")

    return YoyoExportReport(
        model=info,
        validation=validation,
        required_motion_groups=required_motion_groups,
        errors=errors,
        warnings=warnings,
    )
