"""Parse Live2D .physics3.json files."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class PhysicsInput:
    target: str  # "Parameter"
    id: str  # e.g. "ParamAngleX"
    type: str  # "X", "Y", "Angle"
    reflect: bool = False


@dataclass
class PhysicsOutput:
    target: str  # "Parameter"
    id: str  # e.g. "ParamHairFrontX"
    type: str  # "X", "Y", "Angle"
    reflect: bool = False
    scale: float = 1.0
    weight: float = 1.0


@dataclass
class PhysicsVertex:
    position: dict = field(default_factory=dict)  # {x, y}
    mobility: float = 0.0
    delay: float = 0.0
    acceleration: float = 0.0
    radius: float = 0.0


@dataclass
class PhysicsSetting:
    id: str = ""
    input: list[PhysicsInput] = field(default_factory=list)
    output: list[PhysicsOutput] = field(default_factory=list)
    vertices: list[PhysicsVertex] = field(default_factory=list)
    normalization: dict = field(default_factory=dict)

    @property
    def input_params(self) -> list[str]:
        return [i.id for i in self.input]

    @property
    def output_params(self) -> list[str]:
        return [o.id for o in self.output]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "input_count": len(self.input),
            "output_count": len(self.output),
            "vertex_count": len(self.vertices),
            "input_params": self.input_params,
            "output_params": self.output_params,
            "normalization": self.normalization,
        }


@dataclass
class PhysicsInfo:
    path: Path
    version: int = 0
    settings: list[PhysicsSetting] = field(default_factory=list)

    @property
    def setting_count(self) -> int:
        return len(self.settings)

    @property
    def all_input_params(self) -> list[str]:
        params = set()
        for s in self.settings:
            params.update(s.input_params)
        return sorted(params)

    @property
    def all_output_params(self) -> list[str]:
        params = set()
        for s in self.settings:
            params.update(s.output_params)
        return sorted(params)

    def to_dict(self) -> dict:
        return {
            "file": str(self.path),
            "version": self.version,
            "setting_count": self.setting_count,
            "settings": [s.to_dict() for s in self.settings],
            "all_input_params": self.all_input_params,
            "all_output_params": self.all_output_params,
        }


def load_physics(path: Path) -> PhysicsInfo:
    """Load and parse a .physics3.json file."""
    if not path.exists():
        raise FileNotFoundError(f"Physics file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = PhysicsInfo(path=path, version=data.get("Version", 0))

    for setting_data in data.get("PhysicsSettings", []):
        setting = PhysicsSetting(
            id=setting_data.get("Id", ""),
            normalization=setting_data.get("Normalization", {}),
        )

        for inp in setting_data.get("Input", []):
            setting.input.append(PhysicsInput(
                target=inp.get("Target", ""),
                id=inp.get("Id", ""),
                type=inp.get("Type", ""),
                reflect=inp.get("Reflect", False),
            ))

        for out in setting_data.get("Output", []):
            setting.output.append(PhysicsOutput(
                target=out.get("Target", ""),
                id=out.get("Id", ""),
                type=out.get("Type", ""),
                reflect=out.get("Reflect", False),
                scale=out.get("Scale", 1.0),
                weight=out.get("Weight", 1.0),
            ))

        for vert in setting_data.get("Vertices", setting_data.get("Vertex", [])):
            setting.vertices.append(PhysicsVertex(
                position=vert.get("Position", {}),
                mobility=vert.get("Mobility", 0),
                delay=vert.get("Delay", 0),
                acceleration=vert.get("Acceleration", 0),
                radius=vert.get("Radius", 0),
            ))

        info.settings.append(setting)

    return info
