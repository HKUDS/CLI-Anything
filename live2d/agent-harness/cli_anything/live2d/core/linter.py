"""Lint Live2D models for best practices."""

from dataclasses import dataclass, field
from pathlib import Path
import re

from cli_anything.live2d.core.parser import ModelInfo, load_model
from cli_anything.live2d.core.motion_parser import load_motion
from cli_anything.live2d.core.expression_parser import load_expression
from cli_anything.live2d.core.texture_info import get_texture_info


@dataclass
class LintIssue:
    level: str  # "error", "warning", "info"
    category: str  # "naming", "texture", "motion", "expression", "structure"
    message: str
    file: str = ""
    fix_hint: str = ""


@dataclass
class LintReport:
    model_path: Path
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def infos(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "info"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            "model": str(self.model_path),
            "ok": self.ok,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "infos": len(self.infos),
            "issues": [
                {"level": i.level, "category": i.category, "message": i.message, "file": i.file, "fix_hint": i.fix_hint}
                for i in self.issues
            ],
        }


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def lint_model(model_path: Path) -> LintReport:
    """Run all lint checks on a model."""
    info = load_model(model_path)
    report = LintReport(model_path=model_path)
    model_dir = model_path.parent

    # ── Naming checks ──────────────────────────────────────

    # Model file naming
    name = model_path.stem
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        report.issues.append(LintIssue(
            level="warning", category="naming",
            message=f"Model name '{name}' contains special characters",
            file=model_path.name,
            fix_hint="Use only letters, numbers, hyphens, underscores",
        ))

    # Motion file naming
    for group, motions in info.motions.items():
        for i, m in enumerate(motions):
            fname = Path(m.file).stem
            if not re.match(r'^[a-zA-Z0-9_-]+$', fname):
                report.issues.append(LintIssue(
                    level="info", category="naming",
                    message=f"Motion file '{fname}' in [{group}][{i}] has special characters",
                    file=m.file,
                ))

    # Expression naming
    for expr in info.expressions:
        if not re.match(r'^[a-zA-Z0-9_-]+$', expr.name):
            report.issues.append(LintIssue(
                level="info", category="naming",
                message=f"Expression name '{expr.name}' has special characters",
                file=expr.file,
            ))

    # ── Texture checks ─────────────────────────────────────

    for i, tex in enumerate(info.textures):
        tex_path = model_dir / tex
        if not tex_path.exists():
            report.issues.append(LintIssue(
                level="error", category="texture",
                message=f"Texture [{i}] not found: {tex}",
                file=tex,
            ))
            continue

        tinfo = get_texture_info(tex_path)

        # Size check
        if tinfo.width > 0:
            if not _is_power_of_two(tinfo.width) or not _is_power_of_two(tinfo.height):
                report.issues.append(LintIssue(
                    level="warning", category="texture",
                    message=f"Texture [{i}] dimensions {tinfo.width}×{tinfo.height} are not powers of 2",
                    file=tex,
                    fix_hint="Use 512×512, 1024×1024, 2048×2048, etc. for GPU efficiency",
                ))

            if tinfo.width > 4096 or tinfo.height > 4096:
                report.issues.append(LintIssue(
                    level="warning", category="texture",
                    message=f"Texture [{i}] is very large ({tinfo.width}×{tinfo.height})",
                    file=tex,
                    fix_hint="Consider reducing to 2048×2048 or smaller for better performance",
                ))

        # Format check
        if tinfo.format and tinfo.format not in ("png", "webp"):
            report.issues.append(LintIssue(
                level="warning", category="texture",
                message=f"Texture [{i}] uses {tinfo.format} format (png or webp recommended)",
                file=tex,
            ))

    # ── Motion checks ──────────────────────────────────────

    for group, motions in info.motions.items():
        for i, m in enumerate(motions):
            motion_path = model_dir / m.file
            if not motion_path.exists():
                report.issues.append(LintIssue(
                    level="error", category="motion",
                    message=f"Motion file not found: [{group}][{i}] {m.file}",
                    file=m.file,
                ))
                continue

            # Fade time check
            if m.fade_in < 0:
                report.issues.append(LintIssue(
                    level="error", category="motion",
                    message=f"Negative fade_in ({m.fade_in}s) in [{group}][{i}]",
                    file=m.file,
                ))
            if m.fade_out < 0:
                report.issues.append(LintIssue(
                    level="error", category="motion",
                    message=f"Negative fade_out ({m.fade_out}s) in [{group}][{i}]",
                    file=m.file,
                ))

            if m.fade_in > 2.0:
                report.issues.append(LintIssue(
                    level="warning", category="motion",
                    message=f"Very long fade_in ({m.fade_in}s) in [{group}][{i}]",
                    file=m.file,
                    fix_hint="Most motions use 0-1s fade times",
                ))

            # Try parsing the motion file for deeper checks
            try:
                minfo = load_motion(motion_path)
                if minfo.duration <= 0:
                    report.issues.append(LintIssue(
                        level="warning", category="motion",
                        message=f"Motion [{group}][{i}] has zero duration",
                        file=m.file,
                    ))
                if minfo.fps < 15:
                    report.issues.append(LintIssue(
                        level="info", category="motion",
                        message=f"Motion [{group}][{i}] has low FPS ({minfo.fps})",
                        file=m.file,
                    ))
            except Exception:
                pass  # parse failure already caught by validator

    # ── Expression checks ──────────────────────────────────

    expr_names = set()
    for expr in info.expressions:
        expr_path = model_dir / expr.file
        if not expr_path.exists():
            report.issues.append(LintIssue(
                level="error", category="expression",
                message=f"Expression file not found: {expr.name} → {expr.file}",
                file=expr.file,
            ))
            continue

        # Duplicate name check
        if expr.name in expr_names:
            report.issues.append(LintIssue(
                level="error", category="expression",
                message=f"Duplicate expression name: '{expr.name}'",
                file=expr.file,
            ))
        expr_names.add(expr.name)

    # ── Structure checks ───────────────────────────────────

    if not info.moc3:
        report.issues.append(LintIssue(
            level="error", category="structure",
            message="No moc3 file referenced",
        ))

    if not info.textures:
        report.issues.append(LintIssue(
            level="error", category="structure",
            message="No textures defined",
        ))

    if not info.motions:
        report.issues.append(LintIssue(
            level="warning", category="structure",
            message="No motions defined",
        ))

    # Common motion groups
    group_names = set(info.motions.keys())
    common_groups = {"Idle", "idle", "TapBody", "tap_body", "TapHead", "tap_head"}
    if not group_names & common_groups:
        report.issues.append(LintIssue(
            level="info", category="structure",
            message="No common motion groups found (Idle, TapBody, TapHead)",
            fix_hint="Most Live2D runtimes expect at least an Idle group",
        ))

    return report
