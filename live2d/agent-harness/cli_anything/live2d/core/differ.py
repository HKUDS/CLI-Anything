"""Detailed diff between two Live2D models."""

from dataclasses import dataclass, field
from pathlib import Path

from cli_anything.live2d.core.parser import ModelInfo


@dataclass
class DiffItem:
    category: str  # "texture", "motion", "expression", "field", "param"
    name: str
    detail: str
    value_a: object = None
    value_b: object = None


@dataclass
class DetailedDiff:
    model_a: Path
    model_b: Path
    items: list[DiffItem] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return len(self.items) > 0

    def to_dict(self) -> dict:
        return {
            "model_a": str(self.model_a),
            "model_b": str(self.model_b),
            "has_changes": self.has_changes,
            "changes": len(self.items),
            "items": [
                {"category": i.category, "name": i.name, "detail": i.detail,
                 "value_a": i.value_a, "value_b": i.value_b}
                for i in self.items
            ],
        }


def diff_models(a: ModelInfo, b: ModelInfo) -> DetailedDiff:
    """Compute a detailed diff between two models."""
    d = DetailedDiff(model_a=a.path, model_b=b.path)

    # ── Top-level fields ───────────────────────────────────

    for field_name in ("moc3", "physics", "pose", "userdata", "version"):
        va = getattr(a, field_name)
        vb = getattr(b, field_name)
        if va != vb:
            d.items.append(DiffItem(
                category="field", name=field_name,
                detail=f"{va!r} → {vb!r}",
                value_a=va, value_b=vb,
            ))

    # ── Textures ───────────────────────────────────────────

    tex_a = set(a.textures)
    tex_b = set(b.textures)
    for t in sorted(tex_b - tex_a):
        d.items.append(DiffItem(category="texture", name=t, detail="added"))
    for t in sorted(tex_a - tex_b):
        d.items.append(DiffItem(category="texture", name=t, detail="removed"))

    # ── Expressions ────────────────────────────────────────

    expr_a = {e.name: e for e in a.expressions}
    expr_b = {e.name: e for e in b.expressions}

    for name in sorted(set(expr_b) - set(expr_a)):
        d.items.append(DiffItem(
            category="expression", name=name,
            detail=f"added → {expr_b[name].file}",
            value_b=expr_b[name].file,
        ))
    for name in sorted(set(expr_a) - set(expr_b)):
        d.items.append(DiffItem(
            category="expression", name=name,
            detail=f"removed (was → {expr_a[name].file})",
            value_a=expr_a[name].file,
        ))
    for name in sorted(set(expr_a) & set(expr_b)):
        ea, eb = expr_a[name], expr_b[name]
        if ea.file != eb.file:
            d.items.append(DiffItem(
                category="expression", name=name,
                detail=f"file: {ea.file} → {eb.file}",
                value_a=ea.file, value_b=eb.file,
            ))

    # ── Motions ────────────────────────────────────────────

    groups_a = set(a.motions.keys())
    groups_b = set(b.motions.keys())

    for g in sorted(groups_b - groups_a):
        for i, m in enumerate(b.motions[g]):
            d.items.append(DiffItem(
                category="motion", name=f"[{g}][{i}] {m.file}",
                detail="added",
            ))
    for g in sorted(groups_a - groups_b):
        for i, m in enumerate(a.motions[g]):
            d.items.append(DiffItem(
                category="motion", name=f"[{g}][{i}] {m.file}",
                detail="removed",
            ))

    for g in sorted(groups_a & groups_b):
        ma = a.motions[g]
        mb = b.motions[g]

        # Compare by index
        max_len = max(len(ma), len(mb))
        for i in range(max_len):
            if i >= len(ma):
                m = mb[i]
                d.items.append(DiffItem(
                    category="motion", name=f"[{g}][{i}] {m.file}",
                    detail="added",
                ))
            elif i >= len(mb):
                m = ma[i]
                d.items.append(DiffItem(
                    category="motion", name=f"[{g}][{i}] {m.file}",
                    detail="removed",
                ))
            else:
                m1, m2 = ma[i], mb[i]
                changes = []
                if m1.file != m2.file:
                    changes.append(f"file: {m1.file} → {m2.file}")
                if m1.fade_in != m2.fade_in:
                    changes.append(f"fade_in: {m1.fade_in} → {m2.fade_in}")
                if m1.fade_out != m2.fade_out:
                    changes.append(f"fade_out: {m1.fade_out} → {m2.fade_out}")
                if changes:
                    d.items.append(DiffItem(
                        category="motion", name=f"[{g}][{i}]",
                        detail="; ".join(changes),
                        value_a={"file": m1.file, "fade_in": m1.fade_in, "fade_out": m1.fade_out},
                        value_b={"file": m2.file, "fade_in": m2.fade_in, "fade_out": m2.fade_out},
                    ))

    return d
