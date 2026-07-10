"""Parse Live2D .exp3.json files."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ExpressionParam:
    id: str  # e.g. "ParamEyeLOpen"
    value: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0


@dataclass
class ExpressionInfo:
    path: Path
    version: int = 0
    fade_in: float = 0.0
    fade_out: float = 0.0
    params: list[ExpressionParam] = field(default_factory=list)

    @property
    def param_count(self) -> int:
        return len(self.params)

    @property
    def param_ids(self) -> list[str]:
        return [p.id for p in self.params]

    def to_dict(self) -> dict:
        return {
            "file": str(self.path),
            "version": self.version,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "param_count": self.param_count,
            "params": [{"id": p.id, "value": p.value} for p in self.params],
        }


def load_expression(path: Path) -> ExpressionInfo:
    """Load and parse a .exp3.json file."""
    if not path.exists():
        raise FileNotFoundError(f"Expression file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = ExpressionInfo(
        path=path,
        version=data.get("Version", 0),
        fade_in=data.get("FadeInTime", 0),
        fade_out=data.get("FadeOutTime", 0),
    )

    for param_data in data.get("Parameters", []):
        info.params.append(ExpressionParam(
            id=param_data.get("Id", ""),
            value=param_data.get("Value", 0),
            fade_in=param_data.get("FadeInTime", 0),
            fade_out=param_data.get("FadeOutTime", 0),
        ))

    return info
