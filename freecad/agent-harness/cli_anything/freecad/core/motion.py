"""Motion sequencing and real frame rendering for the FreeCAD CLI harness."""

from __future__ import annotations

import copy
import json
import math
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cli_anything.freecad.utils import freecad_backend
from cli_anything.freecad.utils import freecad_macro_gen as macro_gen

from .document import ensure_collection
from .parts import get_part


CAMERA_PRESETS: Dict[str, Dict[str, str]] = {
    "hero": {"method": "viewIsometric", "description": "Isometric overview"},
    "front": {"method": "viewFront", "description": "Front view"},
    "top": {"method": "viewTop", "description": "Top view"},
    "right": {"method": "viewRight", "description": "Right view"},
}

FIT_MODES = {"initial", "per-frame"}
TARGET_KINDS = {"part"}
_COLLECTION_KEY = "motions"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _next_id(project: Dict[str, Any]) -> int:
    items = ensure_collection(project, _COLLECTION_KEY)
    if not items:
        return 1
    return max(int(item["id"]) for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    items = ensure_collection(project, _COLLECTION_KEY)
    existing = {item["name"] for item in items}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _validate_vec3(value: Optional[List[float]], label: str) -> Optional[List[float]]:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be a list of 3 numbers")
    try:
        return [float(component) for component in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} elements must be numeric: {exc}") from exc


def _validate_time(value: float, duration: float) -> float:
    numeric = float(value)
    if numeric < 0.0 or numeric > float(duration):
        raise ValueError(f"time must be within [0, {duration}], got {numeric}")
    return numeric


def _validate_motion_index(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    items = ensure_collection(project, _COLLECTION_KEY)
    if not isinstance(index, int) or index < 0 or index >= len(items):
        raise IndexError(f"Motion index {index} out of range (0..{len(items) - 1})")
    return items[index]


def _track_summary(track: Dict[str, Any]) -> Dict[str, Any]:
    keyframes = track.get("keyframes", [])
    return {
        "target": dict(track.get("target", {})),
        "keyframe_count": len(keyframes),
        "time_range": [
            float(keyframes[0]["time"]) if keyframes else 0.0,
            float(keyframes[-1]["time"]) if keyframes else 0.0,
        ],
    }


def _normalize_target(project: Dict[str, Any], target_kind: str, target_index: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if target_kind not in TARGET_KINDS:
        raise ValueError(f"Unsupported target_kind '{target_kind}'. Valid: {', '.join(sorted(TARGET_KINDS))}")
    if target_kind == "part":
        part = get_part(project, target_index)
        return (
            {
                "kind": "part",
                "index": int(target_index),
                "part_id": int(part["id"]),
                "name": part["name"],
            },
            part,
        )
    raise ValueError(f"Unsupported target_kind '{target_kind}'")


def _resolve_target_part(project: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    if target.get("kind") != "part":
        raise ValueError(f"Unsupported motion target: {target}")
    parts = project.get("parts", [])
    index = int(target.get("index", -1))
    part_id = target.get("part_id")
    if 0 <= index < len(parts) and parts[index].get("id") == part_id:
        return parts[index]
    for part in parts:
        if part.get("id") == part_id:
            return part
    raise ValueError(f"Motion target part could not be resolved: {target}")


def _find_track(motion: Dict[str, Any], target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for track in motion.get("tracks", []):
        existing = track.get("target", {})
        if existing.get("kind") == target.get("kind") and existing.get("part_id") == target.get("part_id"):
            return track
    return None


def _sorted_keyframes(keyframes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(keyframes, key=lambda item: (float(item["time"]), json.dumps(item, sort_keys=True)))


def _interpolate_vec3(a: List[float], b: List[float], alpha: float) -> List[float]:
    return [
        float(a[i]) + (float(b[i]) - float(a[i])) * alpha
        for i in range(3)
    ]


def _track_state_at_time(track: Dict[str, Any], time_value: float) -> Dict[str, Any]:
    keyframes = _sorted_keyframes(track.get("keyframes", []))
    if not keyframes:
        raise ValueError(f"Track has no keyframes: {track.get('target')}")

    if time_value <= float(keyframes[0]["time"]):
        first = keyframes[0]
        return {
            "position": list(first["position"]),
            "rotation": list(first["rotation"]),
        }
    if time_value >= float(keyframes[-1]["time"]):
        last = keyframes[-1]
        return {
            "position": list(last["position"]),
            "rotation": list(last["rotation"]),
        }

    for left, right in zip(keyframes, keyframes[1:]):
        left_time = float(left["time"])
        right_time = float(right["time"])
        if left_time <= time_value <= right_time:
            if right_time == left_time:
                alpha = 0.0
            else:
                alpha = (time_value - left_time) / (right_time - left_time)
            return {
                "position": _interpolate_vec3(left["position"], right["position"], alpha),
                "rotation": _interpolate_vec3(left["rotation"], right["rotation"], alpha),
            }
    last = keyframes[-1]
    return {
        "position": list(last["position"]),
        "rotation": list(last["rotation"]),
    }


def _frame_times(duration: float, fps: int) -> List[float]:
    if fps <= 0:
        raise ValueError("fps must be positive")
    frame_count = max(2, int(round(float(duration) * int(fps))) + 1)
    return [min(float(duration), i / float(fps)) for i in range(frame_count)]


def _safe_path(path: str) -> str:
    return path.replace("\\", "/")


def _ensure_empty_dir(path: str, overwrite: bool) -> str:
    resolved = os.path.abspath(path)
    if os.path.isdir(resolved):
        if os.listdir(resolved):
            if not overwrite:
                raise FileExistsError(
                    f"Output directory already exists and is not empty: {resolved}. "
                    "Use overwrite=True to replace it."
                )
            shutil.rmtree(resolved)
    elif os.path.exists(resolved):
        raise FileExistsError(f"Output path exists and is not a directory: {resolved}")
    os.makedirs(resolved, exist_ok=True)
    return resolved


def _ffmpeg_path() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    raise RuntimeError("ffmpeg is required for motion video export but was not found on PATH")


def create_motion(
    project: Dict[str, Any],
    name: Optional[str] = None,
    *,
    duration: float = 2.0,
    fps: int = 24,
    camera: str = "hero",
    width: int = 1280,
    height: int = 960,
    background: str = "White",
    fit_mode: str = "initial",
) -> Dict[str, Any]:
    """Create a new motion sequence attached to the project."""
    items = ensure_collection(project, _COLLECTION_KEY)
    if float(duration) <= 0:
        raise ValueError("duration must be greater than 0")
    if int(fps) <= 0:
        raise ValueError("fps must be positive")
    if camera not in CAMERA_PRESETS:
        raise ValueError(f"Unknown camera '{camera}'. Valid: {', '.join(sorted(CAMERA_PRESETS))}")
    if fit_mode not in FIT_MODES:
        raise ValueError(f"Unknown fit_mode '{fit_mode}'. Valid: {', '.join(sorted(FIT_MODES))}")
    if int(width) <= 0 or int(height) <= 0:
        raise ValueError("width and height must be positive")

    motion = {
        "id": _next_id(project),
        "name": _unique_name(project, name or "Motion"),
        "duration": float(duration),
        "fps": int(fps),
        "camera": camera,
        "width": int(width),
        "height": int(height),
        "background": str(background),
        "fit_mode": fit_mode,
        "tracks": [],
        "metadata": {
            "created": _now_iso(),
            "modified": _now_iso(),
        },
    }
    items.append(motion)
    return motion


def list_motions(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return summary info for all motion sequences."""
    items = ensure_collection(project, _COLLECTION_KEY)
    result = []
    for index, motion in enumerate(items):
        keyframe_count = sum(len(track.get("keyframes", [])) for track in motion.get("tracks", []))
        result.append(
            {
                "index": index,
                "id": motion.get("id"),
                "name": motion.get("name"),
                "duration": motion.get("duration"),
                "fps": motion.get("fps"),
                "camera": motion.get("camera"),
                "track_count": len(motion.get("tracks", [])),
                "keyframe_count": keyframe_count,
            }
        )
    return result


def get_motion(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return a single motion sequence."""
    return _validate_motion_index(project, index)


def delete_motion(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Delete and return a motion sequence."""
    items = ensure_collection(project, _COLLECTION_KEY)
    _validate_motion_index(project, index)
    return items.pop(index)


def add_keyframe(
    project: Dict[str, Any],
    motion_index: int,
    *,
    target_kind: str,
    target_index: int,
    time_value: float,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Insert or replace a keyframe on a motion track."""
    motion = _validate_motion_index(project, motion_index)
    target, source_obj = _normalize_target(project, target_kind, target_index)
    placement = source_obj.get("placement", {})
    resolved_position = _validate_vec3(position, "position") or list(placement.get("position", [0.0, 0.0, 0.0]))
    resolved_rotation = _validate_vec3(rotation, "rotation") or list(placement.get("rotation", [0.0, 0.0, 0.0]))
    keyframe = {
        "time": _validate_time(time_value, float(motion["duration"])),
        "position": resolved_position,
        "rotation": resolved_rotation,
    }

    track = _find_track(motion, target)
    if track is None:
        track = {"target": target, "keyframes": []}
        motion["tracks"].append(track)

    replaced = False
    updated_keyframes: List[Dict[str, Any]] = []
    for existing in track["keyframes"]:
        if math.isclose(float(existing["time"]), keyframe["time"], abs_tol=1e-9):
            updated_keyframes.append(keyframe)
            replaced = True
        else:
            updated_keyframes.append(existing)
    if not replaced:
        updated_keyframes.append(keyframe)

    track["keyframes"] = _sorted_keyframes(updated_keyframes)
    motion["metadata"]["modified"] = _now_iso()
    return {
        "motion": motion["name"],
        "track": _track_summary(track),
        "keyframe": keyframe,
        "replaced": replaced,
    }


def sample_motion(project: Dict[str, Any], motion_index: int, time_value: float) -> Dict[str, Any]:
    """Evaluate a motion sequence at an arbitrary time."""
    motion = _validate_motion_index(project, motion_index)
    resolved_time = _validate_time(time_value, float(motion["duration"]))
    placements = []
    for track in motion.get("tracks", []):
        state = _track_state_at_time(track, resolved_time)
        placements.append(
            {
                "target": dict(track["target"]),
                "position": state["position"],
                "rotation": state["rotation"],
            }
        )
    return {
        "motion": motion["name"],
        "time": resolved_time,
        "camera": motion["camera"],
        "placements": placements,
    }


def apply_motion(project: Dict[str, Any], motion_index: int, time_value: float) -> Dict[str, Any]:
    """Return a deep-copied project with interpolated placements applied."""
    sampled = sample_motion(project, motion_index, time_value)
    project_copy = copy.deepcopy(project)
    for placement in sampled["placements"]:
        target = placement["target"]
        if target["kind"] != "part":
            continue
        part = _resolve_target_part(project_copy, target)
        part.setdefault("placement", {})
        part["placement"]["position"] = list(placement["position"])
        part["placement"]["rotation"] = list(placement["rotation"])
    return project_copy


def _motion_frames(project: Dict[str, Any], motion: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    frames: List[Dict[str, Any]] = []
    unsupported_targets: List[Dict[str, Any]] = []
    unsupported_seen = set()

    times = _frame_times(float(motion["duration"]), int(motion["fps"]))
    for frame_index, time_value in enumerate(times):
        placements: Dict[str, Dict[str, List[float]]] = {}
        for track in motion.get("tracks", []):
            target = dict(track["target"])
            part = _resolve_target_part(project, target)
            render_spec = macro_gen._render_spec_for_part(project, part)
            if render_spec is None:
                signature = (target.get("kind"), target.get("part_id"))
                if signature not in unsupported_seen:
                    unsupported_seen.add(signature)
                    unsupported_targets.append(target)
                continue
            state = _track_state_at_time(track, time_value)
            placements[str(target["part_id"])] = {
                "position": state["position"],
                "rotation": state["rotation"],
            }
        frame_path = os.path.join(output_dir, f"frame_{frame_index:05d}.png")
        frames.append(
            {
                "index": frame_index,
                "time": time_value,
                "path": frame_path,
                "placements": placements,
            }
        )
    return {
        "frames": frames,
        "unsupported_targets": unsupported_targets,
    }


def _generate_motion_macro(
    project: Dict[str, Any],
    *,
    frames: List[Dict[str, Any]],
    camera: str,
    width: int,
    height: int,
    background: str,
    fit_mode: str,
) -> str:
    if camera not in CAMERA_PRESETS:
        raise ValueError(f"Unknown camera '{camera}'")
    if fit_mode not in FIT_MODES:
        raise ValueError(f"Unknown fit_mode '{fit_mode}'")

    part_object_items = []
    for part in project.get("parts", []):
        render_spec = macro_gen._render_spec_for_part(project, part)
        if render_spec is None:
            continue
        safe_name = macro_gen._safe_name(part.get("name", f"Part_{part.get('id', 'unknown')}"))
        part_object_items.append(f"    '{int(part['id'])}': obj_{safe_name},")

    lines: List[str] = []
    lines.extend(macro_gen._gen_header())
    lines.extend(macro_gen._gen_parts(project))
    lines.extend(macro_gen._gen_boolean_ops(project))
    lines.extend(macro_gen._gen_bodies(project))
    lines.extend(macro_gen._gen_placements(project))
    lines.extend(
        [
            "doc.recompute()",
            "",
            "try:",
            "    import FreeCADGui",
            "except ImportError as exc:",
            "    raise RuntimeError('FreeCADGui is required for motion rendering') from exc",
            "",
            "try:",
            "    FreeCADGui.showMainWindow()",
            "except Exception:",
            "    pass",
            "",
            "gui_doc = FreeCADGui.getDocument(doc.Name)",
            "if gui_doc is None:",
            "    raise RuntimeError(f'Could not acquire GUI document for {doc.Name}')",
            "FreeCADGui.ActiveDocument = gui_doc",
            "view = getattr(FreeCADGui.ActiveDocument, 'ActiveView', None)",
            "if view is None:",
            "    view = FreeCADGui.ActiveDocument.activeView()",
            "if view is None:",
            "    raise RuntimeError('FreeCAD active view is not available')",
            "try:",
            "    view.setAnimationEnabled(False)",
            "except Exception:",
            "    pass",
            "",
            "part_objects = {",
            *part_object_items,
            "}",
            f"frames = {repr(frames)}",
            "",
            f"getattr(view, '{CAMERA_PRESETS[camera]['method']}')()",
            "try:",
            "    view.fitAll()",
            "except Exception:",
            "    pass",
            "try:",
            "    FreeCADGui.updateGui()",
            "except Exception:",
            "    pass",
            "",
            "for frame in frames:",
            "    for part_id, placement in frame['placements'].items():",
            "        obj = part_objects.get(str(part_id))",
            "        if obj is None:",
            "            continue",
            "        pos = placement['position']",
            "        rot = placement['rotation']",
            "        obj.Placement = FreeCAD.Placement(",
            "            FreeCAD.Vector(float(pos[0]), float(pos[1]), float(pos[2])),",
            "            FreeCAD.Rotation(float(rot[2]), float(rot[1]), float(rot[0])),",
            "        )",
            "    doc.recompute()",
            "    try:",
            "        FreeCADGui.updateGui()",
            "    except Exception:",
            "        pass",
        ]
    )
    if fit_mode == "per-frame":
        lines.extend(
            [
                "    try:",
                "        view.fitAll()",
                "    except Exception:",
                "        pass",
            ]
        )
    lines.extend(
        [
            f"    view.saveImage(frame['path'], {int(width)}, {int(height)}, '{background}')",
            "",
            "try:",
            "    FreeCAD.closeDocument(doc.Name)",
            "except Exception:",
            "    pass",
            "import os as _motion_os",
            "_motion_os._exit(0)",
            "",
        ]
    )
    return "\n".join(lines)


def render_frames(
    project: Dict[str, Any],
    motion_index: int,
    output_dir: str,
    *,
    overwrite: bool = False,
    camera: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    background: Optional[str] = None,
    fit_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Render a motion sequence to a real frame directory via FreeCAD GUI capture."""
    motion = _validate_motion_index(project, motion_index)
    resolved_camera = camera or motion.get("camera", "hero")
    resolved_width = int(width or motion.get("width", 1280))
    resolved_height = int(height or motion.get("height", 960))
    resolved_background = str(background or motion.get("background", "White"))
    resolved_fit_mode = fit_mode or motion.get("fit_mode", "initial")
    if resolved_camera not in CAMERA_PRESETS:
        raise ValueError(f"Unknown camera '{resolved_camera}'")
    if resolved_fit_mode not in FIT_MODES:
        raise ValueError(f"Unknown fit_mode '{resolved_fit_mode}'")

    resolved_output_dir = _ensure_empty_dir(output_dir, overwrite=overwrite)
    frame_payload = _motion_frames(project, motion, resolved_output_dir)
    frames = frame_payload["frames"]
    if not frames:
        raise RuntimeError("Motion sequence produced no frames")

    macro = _generate_motion_macro(
        project,
        frames=frames,
        camera=resolved_camera,
        width=resolved_width,
        height=resolved_height,
        background=resolved_background,
        fit_mode=resolved_fit_mode,
    )
    result = freecad_backend.run_macro_content(
        macro,
        timeout=max(240, len(frames) * 8),
        gui_required=True,
        env={"QT_QPA_PLATFORM": "offscreen"},
    )
    if result["returncode"] != 0:
        raise RuntimeError(
            f"FreeCAD motion render failed (exit code {result['returncode']}): {result['stderr']}"
        )

    missing = [frame["path"] for frame in frames if not os.path.isfile(frame["path"])]
    if missing:
        raise RuntimeError(f"Motion render completed but {len(missing)} frame(s) are missing: {missing[:3]}")

    sequence_path = os.path.join(resolved_output_dir, "sequence.json")
    sequence = {
        "motion_name": motion["name"],
        "motion_index": motion_index,
        "duration": motion["duration"],
        "fps": motion["fps"],
        "camera": resolved_camera,
        "width": resolved_width,
        "height": resolved_height,
        "background": resolved_background,
        "fit_mode": resolved_fit_mode,
        "frame_count": len(frames),
        "frames": [
            {
                "index": frame["index"],
                "time": frame["time"],
                "path": os.path.relpath(frame["path"], resolved_output_dir),
            }
            for frame in frames
        ],
        "unsupported_targets": frame_payload["unsupported_targets"],
        "method": "freecad-gui-sequence",
    }
    with open(sequence_path, "w", encoding="utf-8") as fh:
        json.dump(sequence, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return {
        "motion": motion["name"],
        "output_dir": resolved_output_dir,
        "sequence_path": sequence_path,
        "frame_count": len(frames),
        "first_frame": frames[0]["path"],
        "last_frame": frames[-1]["path"],
        "camera": resolved_camera,
        "fit_mode": resolved_fit_mode,
        "method": "freecad-gui-sequence",
        "unsupported_targets": frame_payload["unsupported_targets"],
    }


def render_video(
    project: Dict[str, Any],
    motion_index: int,
    output_path: str,
    *,
    overwrite: bool = False,
    frames_dir: Optional[str] = None,
    keep_frames: bool = False,
    camera: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    background: Optional[str] = None,
    fit_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Render a motion sequence to PNG frames and encode an MP4/WebM/GIF video."""
    resolved_output_path = os.path.abspath(output_path)
    output_dirname = os.path.dirname(resolved_output_path) or "."
    os.makedirs(output_dirname, exist_ok=True)
    if os.path.exists(resolved_output_path) and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {resolved_output_path}. Use overwrite=True to replace it."
        )
    ext = Path(resolved_output_path).suffix.lower()
    if ext not in {".mp4", ".webm", ".gif"}:
        raise ValueError("motion render-video currently supports .mp4, .webm, and .gif outputs")

    temp_dir: Optional[str] = None
    if frames_dir:
        resolved_frames_dir = os.path.abspath(frames_dir)
    elif keep_frames:
        stem = Path(resolved_output_path).stem
        resolved_frames_dir = os.path.join(output_dirname, f"{stem}_frames")
    else:
        temp_dir = tempfile.mkdtemp(prefix="freecad_motion_frames_")
        resolved_frames_dir = temp_dir

    frame_result = render_frames(
        project,
        motion_index,
        resolved_frames_dir,
        overwrite=True,
        camera=camera,
        width=width,
        height=height,
        background=background,
        fit_mode=fit_mode,
    )
    motion = _validate_motion_index(project, motion_index)
    ffmpeg = _ffmpeg_path()

    input_pattern = os.path.join(frame_result["output_dir"], "frame_%05d.png")
    command = [ffmpeg, "-y", "-framerate", str(int(motion["fps"])), "-i", input_pattern]
    if ext == ".mp4":
        command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", resolved_output_path])
    elif ext == ".webm":
        command.extend(["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", resolved_output_path])
    else:
        command.extend(["-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", resolved_output_path])

    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.isfile(resolved_output_path):
        raise RuntimeError(
            f"ffmpeg video encode failed (exit code {proc.returncode}): {proc.stderr.strip()}"
        )

    result = {
        "motion": motion["name"],
        "output": resolved_output_path,
        "format": ext.lstrip("."),
        "file_size": os.path.getsize(resolved_output_path),
        "frame_count": frame_result["frame_count"],
        "fps": motion["fps"],
        "frames_dir": frame_result["output_dir"],
        "sequence_path": frame_result["sequence_path"],
        "method": "freecad-gui-sequence+ffmpeg",
        "ffmpeg_command": command,
    }
    if temp_dir and not keep_frames:
        shutil.rmtree(temp_dir, ignore_errors=True)
        result["frames_dir"] = None
        result["sequence_path"] = None
    return result
