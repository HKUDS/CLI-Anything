"""Parse Live2D Cubism model3.json files."""

import json
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MotionRef:
    file: str
    fade_in: float = 0.0
    fade_out: float = 0.0
    extra: dict = field(default_factory=dict)  # preserve unknown fields (Sound, MetaInfo, etc.)


@dataclass
class ExpressionRef:
    name: str
    file: str


@dataclass
class ModelInfo:
    path: Path
    version: str = ""
    moc3: str = ""
    textures: list[str] = field(default_factory=list)
    physics: str = ""
    pose: str = ""
    userdata: str = ""
    display_info: str = ""
    expressions: list[ExpressionRef] = field(default_factory=list)
    motions: dict[str, list[MotionRef]] = field(default_factory=dict)
    groups: list[dict] = field(default_factory=list)

    @property
    def motion_count(self) -> int:
        return sum(len(v) for v in self.motions.values())

    @property
    def motion_group_count(self) -> int:
        return len(self.motions)

    @property
    def texture_count(self) -> int:
        return len(self.textures)

    @property
    def expression_count(self) -> int:
        return len(self.expressions)

    def to_dict(self) -> dict:
        return {
            "model_file": str(self.path),
            "version": self.version,
            "moc3": self.moc3,
            "textures": self.textures,
            "texture_count": self.texture_count,
            "motions": {
                g: [{"file": m.file, "fade_in": m.fade_in, "fade_out": m.fade_out} for m in ms]
                for g, ms in self.motions.items()
            },
            "motion_count": self.motion_count,
            "motion_groups": self.motion_group_count,
            "expressions": [{"name": e.name, "file": e.file} for e in self.expressions],
            "expression_count": self.expression_count,
            "physics": self.physics,
            "pose": self.pose,
            "userdata": self.userdata,
            "groups": self.groups,
        }


def load_model(path: Path) -> ModelInfo:
    """Load and parse a .model3.json file into a ModelInfo."""
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    if not path.suffix == ".json":
        raise ValueError(f"Expected .model3.json, got: {path.suffix}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    refs = data.get("FileReferences", {})
    info = ModelInfo(
        path=path,
        version=data.get("Version", ""),
        moc3=refs.get("Moc", ""),
        textures=refs.get("Textures", []),
        physics=refs.get("Physics", ""),
        pose=refs.get("Pose", ""),
        userdata=refs.get("UserData", ""),
        display_info=refs.get("DisplayInfo", ""),
    )

    # Expressions
    for expr in refs.get("Expressions", []):
        info.expressions.append(ExpressionRef(
            name=expr.get("Name", ""),
            file=expr.get("File", ""),
        ))

    # Motions
    for group_name, motions in refs.get("Motions", {}).items():
        info.motions[group_name] = []
        for m in motions:
            extra = {k: v for k, v in m.items() if k not in ("File", "FadeInTime", "FadeOutTime")}
            info.motions[group_name].append(MotionRef(
                file=m.get("File", ""),
                fade_in=m.get("FadeInTime", 0),
                fade_out=m.get("FadeOutTime", 0),
                extra=extra,
            ))

    # Groups
    info.groups = data.get("Groups", [])

    return info


def save_model(info: ModelInfo, path: Path | None = None) -> Path:
    """Write a ModelInfo back to a .model3.json file."""
    target = path or info.path
    if not target.exists():
        raise FileNotFoundError(f"Model file not found: {target}")

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    refs = data.setdefault("FileReferences", {})

    refs["Moc"] = info.moc3
    refs["Textures"] = info.textures
    refs["Physics"] = info.physics
    refs["Pose"] = info.pose
    refs["UserData"] = info.userdata
    refs["DisplayInfo"] = info.display_info

    # Expressions
    refs["Expressions"] = [
        {"Name": e.name, "File": e.file} for e in info.expressions
    ]

    # Motions
    motions_out = {}
    for group_name, motion_list in info.motions.items():
        entries = []
        for m in motion_list:
            entry = {"File": m.file, "FadeInTime": m.fade_in, "FadeOutTime": m.fade_out}
            entry.update(m.extra)  # preserve Sound, MetaInfo, etc.
            entries.append(entry)
        motions_out[group_name] = entries
    refs["Motions"] = motions_out

    # Groups
    if info.groups:
        data["Groups"] = info.groups

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        os.chmod(tmp_path, target.stat().st_mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return target
