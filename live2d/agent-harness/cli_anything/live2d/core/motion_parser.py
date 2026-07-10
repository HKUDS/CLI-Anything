"""Parse Live2D .motion3.json files."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class MotionSegment:
    """A single segment in a motion curve.

    Segment types (determined by point count):
    - 2 points (linear): [time, value]
    - 3 points (bezier): [time, cx1, cy1, cx2, cy2, value]
    - 5 points (stepped): [time, value]
    - 7 points (inverse stepped): [time, value]
    """
    points: list[float] = field(default_factory=list)

    @property
    def segment_type(self) -> str:
        n = len(self.points)
        if n <= 2:
            return "linear"
        elif n <= 3:
            return "bezier"
        elif n <= 5:
            return "stepped"
        else:
            return "inverse_stepped"


@dataclass
class MotionCurve:
    target: str  # "Parameter", "Model", "Part", "Opacity"
    id: str  # e.g. "ParamAngleX", "ParamBodyAngleX"
    segments: list[MotionSegment] = field(default_factory=list)

    @property
    def keyframe_count(self) -> int:
        return len(self.segments)


@dataclass
class MotionInfo:
    path: Path
    version: int = 0
    duration: float = 0.0
    fps: float = 0.0
    loop: bool = False
    curve_count: int = 0
    total_segment_count: int = 0
    total_point_count: int = 0
    curves: list[MotionCurve] = field(default_factory=list)

    @property
    def parameter_curves(self) -> list[MotionCurve]:
        return [c for c in self.curves if c.target == "Parameter"]

    @property
    def model_curves(self) -> list[MotionCurve]:
        return [c for c in self.curves if c.target == "Model"]

    @property
    def part_curves(self) -> list[MotionCurve]:
        return [c for c in self.curves if c.target == "Part"]

    @property
    def parameter_ids(self) -> list[str]:
        return [c.id for c in self.parameter_curves]

    def to_dict(self) -> dict:
        return {
            "file": str(self.path),
            "version": self.version,
            "duration": self.duration,
            "fps": self.fps,
            "loop": self.loop,
            "curve_count": self.curve_count,
            "total_segments": self.total_segment_count,
            "total_points": self.total_point_count,
            "parameters": self.parameter_ids,
            "parameter_count": len(self.parameter_curves),
            "model_curves": len(self.model_curves),
            "part_curves": len(self.part_curves),
            "curves": [
                {"target": c.target, "id": c.id, "keyframes": c.keyframe_count}
                for c in self.curves
            ],
        }


def load_motion(path: Path) -> MotionInfo:
    """Load and parse a .motion3.json file."""
    if not path.exists():
        raise FileNotFoundError(f"Motion file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("Meta", {})
    info = MotionInfo(
        path=path,
        version=data.get("Version", 0),
        duration=meta.get("Duration", 0),
        fps=meta.get("Fps", 0),
        loop=meta.get("Loop", False),
        curve_count=meta.get("CurveCount", 0),
        total_segment_count=meta.get("TotalSegmentCount", 0),
        total_point_count=meta.get("TotalPointCount", 0),
    )

    for curve_data in data.get("Curves", []):
        curve = MotionCurve(
            target=curve_data.get("Target", ""),
            id=curve_data.get("Id", ""),
        )
        segments_raw = curve_data.get("Segments", [])

        # Parse segments: first value is time, then groups of points
        i = 0
        while i < len(segments_raw):
            if i == 0:
                # First segment: [time, value]
                curve.segments.append(MotionSegment(points=segments_raw[i:i + 2]))
                i += 2
            else:
                # Subsequent: type indicator + points
                seg_type = segments_raw[i]
                if seg_type == 0:
                    # Linear: [0, time, value]
                    curve.segments.append(MotionSegment(points=segments_raw[i + 1:i + 3]))
                    i += 3
                elif seg_type == 1:
                    # Bezier: [1, time, cx1, cy1, cx2, cy2, value]
                    curve.segments.append(MotionSegment(points=segments_raw[i + 1:i + 7]))
                    i += 7
                elif seg_type == 2:
                    # Stepped: [2, time, value]
                    curve.segments.append(MotionSegment(points=segments_raw[i + 1:i + 3]))
                    i += 3
                elif seg_type == 3:
                    # Inverse stepped: [3, time, value]
                    curve.segments.append(MotionSegment(points=segments_raw[i + 1:i + 3]))
                    i += 3
                else:
                    # Unknown, skip
                    i += 1

        info.curves.append(curve)

    return info
