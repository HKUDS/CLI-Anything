"""Compare two Live2D models."""

from dataclasses import dataclass, field
from .parser import ModelInfo


@dataclass
class DiffItem:
    category: str  # "texture", "motion", "expression", "physics", etc.
    type: str  # "added", "removed", "changed"
    name: str
    detail: str = ""


@dataclass
class ModelDiff:
    model_a: str
    model_b: str
    items: list[DiffItem] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return len(self.items) > 0

    @property
    def added(self) -> list[DiffItem]:
        return [i for i in self.items if i.type == "added"]

    @property
    def removed(self) -> list[DiffItem]:
        return [i for i in self.items if i.type == "removed"]

    @property
    def changed(self) -> list[DiffItem]:
        return [i for i in self.items if i.type == "changed"]

    def to_dict(self) -> dict:
        return {
            "model_a": self.model_a,
            "model_b": self.model_b,
            "has_changes": self.has_changes,
            "summary": {
                "added": len(self.added),
                "removed": len(self.removed),
                "changed": len(self.changed),
            },
            "items": [
                {"category": i.category, "type": i.type, "name": i.name, "detail": i.detail}
                for i in self.items
            ],
        }


def compare_models(a: ModelInfo, b: ModelInfo) -> ModelDiff:
    """Compare two models and return differences."""
    diff = ModelDiff(model_a=str(a.path), model_b=str(b.path))

    # Compare textures
    tex_a = set(a.textures)
    tex_b = set(b.textures)
    for t in tex_b - tex_a:
        diff.items.append(DiffItem("texture", "added", t))
    for t in tex_a - tex_b:
        diff.items.append(DiffItem("texture", "removed", t))

    # Compare expressions
    expr_a = {e.name: e for e in a.expressions}
    expr_b = {e.name: e for e in b.expressions}
    for name in set(expr_b) - set(expr_a):
        diff.items.append(DiffItem("expression", "added", name))
    for name in set(expr_a) - set(expr_b):
        diff.items.append(DiffItem("expression", "removed", name))
    for name in set(expr_a) & set(expr_b):
        if expr_a[name].file != expr_b[name].file:
            diff.items.append(DiffItem("expression", "changed", name,
                                       f"{expr_a[name].file} → {expr_b[name].file}"))

    # Compare motion groups
    groups_a = set(a.motions.keys())
    groups_b = set(b.motions.keys())
    for g in groups_b - groups_a:
        diff.items.append(DiffItem("motion_group", "added", g, f"{len(b.motions[g])} motions"))
    for g in groups_a - groups_b:
        diff.items.append(DiffItem("motion_group", "removed", g, f"{len(a.motions[g])} motions"))

    # Compare motions within shared groups
    for g in groups_a & groups_b:
        files_a = {m.file for m in a.motions[g]}
        files_b = {m.file for m in b.motions[g]}
        for f in files_b - files_a:
            diff.items.append(DiffItem("motion", "added", f"[{g}] {f}"))
        for f in files_a - files_b:
            diff.items.append(DiffItem("motion", "removed", f"[{g}] {f}"))

    # Compare moc3
    if a.moc3 != b.moc3:
        diff.items.append(DiffItem("moc3", "changed", "moc3", f"{a.moc3} → {b.moc3}"))

    # Compare physics
    if bool(a.physics) != bool(b.physics):
        if b.physics:
            diff.items.append(DiffItem("physics", "added", b.physics))
        else:
            diff.items.append(DiffItem("physics", "removed", a.physics))

    # Compare groups
    groups_ids_a = {g.get("Name", ""): g.get("Ids", "") for g in a.groups}
    groups_ids_b = {g.get("Name", ""): g.get("Ids", "") for g in b.groups}
    for name in set(groups_ids_b) - set(groups_ids_a):
        diff.items.append(DiffItem("param_group", "added", name))
    for name in set(groups_ids_a) - set(groups_ids_b):
        diff.items.append(DiffItem("param_group", "removed", name))
    for name in set(groups_ids_a) & set(groups_ids_b):
        if groups_ids_a[name] != groups_ids_b[name]:
            diff.items.append(DiffItem("param_group", "changed", name,
                                       f"{groups_ids_a[name]} → {groups_ids_b[name]}"))

    return diff
