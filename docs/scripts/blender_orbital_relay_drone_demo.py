#!/usr/bin/env python3
"""Build a clear Blender orbital relay drone demo with live previews and motion.

Outputs:

- real staged preview bundles
- a persisted live `session.json`
- append-only `trajectory.json`
- `live.html` rendered through `cli-hub previews html`
- a final still render and turntable video
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
BLENDER_HARNESS_ROOT = REPO_ROOT / "blender" / "agent-harness"
sys.path.insert(0, str(BLENDER_HARNESS_ROOT))

from cli_anything.blender.core import preview as preview_mod
from cli_anything.blender.core.animation import add_keyframe, set_current_frame, set_frame_range, set_fps
from cli_anything.blender.core.lighting import add_camera, add_light
from cli_anything.blender.core.materials import assign_material, create_material, set_material_property
from cli_anything.blender.core.modifiers import add_modifier
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.render import render_scene, set_render_settings
from cli_anything.blender.core.scene import create_scene, save_scene
from cli_anything.blender.core.session import Session
from cli_anything.blender.utils import blender_backend


def _object_index(project: Dict, name: str) -> int:
    for index, obj in enumerate(project.get("objects", [])):
        if obj.get("name") == name:
            return index
    raise KeyError(f"Object not found: {name}")


def _material_index(project: Dict, name: str) -> int:
    for index, material in enumerate(project.get("materials", [])):
        if material.get("name") == name:
            return index
    raise KeyError(f"Material not found: {name}")


def _assign(project: Dict, material_name: str, object_name: str) -> None:
    assign_material(project, _material_index(project, material_name), _object_index(project, object_name))


def _set_parent(project: Dict, child_name: str, parent_name: str) -> None:
    child = project["objects"][_object_index(project, child_name)]
    parent = project["objects"][_object_index(project, parent_name)]
    child["parent"] = parent["id"]


def _render_via_script(project: Dict, output_path: Path, *, frame: int | None = None, animation: bool = False, timeout: int = 900) -> Dict:
    render_job = render_scene(project, str(output_path), frame=frame, animation=animation, overwrite=True)
    backend_result = blender_backend.render_script(render_job["script_path"], timeout=timeout)
    if backend_result["returncode"] != 0:
        raise RuntimeError(
            f"Blender render failed for {output_path} (exit {backend_result['returncode']}):\n"
            f"{backend_result['stderr'][-1000:]}"
        )
    payload = dict(render_job)
    payload["backend"] = backend_result
    return payload


def _encode_video(frames_dir: Path, video_path: Path, fps: int) -> Dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    pattern = str(frames_dir / "frame_%04d.png")
    command = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        pattern,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg encoding failed:\n{result.stderr[-1200:]}")
    return {
        "command": command,
        "video_path": str(video_path),
        "bytes": video_path.stat().st_size if video_path.exists() else 0,
    }


def _copy_motion_stills(frames: List[Path], output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    picks = {
        "start": frames[0],
        "mid": frames[len(frames) // 2],
        "final": frames[-1],
    }
    exported: Dict[str, str] = {}
    for label, source in picks.items():
        target = output_dir / f"{label}.png"
        shutil.copy2(source, target)
        exported[label] = str(target)
    return exported


def _render_live_html(session_dir: Path, output_path: Path) -> str | None:
    hub = shutil.which("cli-hub")
    if not hub:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [hub, "previews", "html", str(session_dir), "-o", str(output_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"cli-hub previews html failed:\n{result.stderr[-1200:]}")
    return str(output_path)


def _add_materials(project: Dict) -> None:
    create_material(project, name="DeckGraphite", color=[0.18, 0.2, 0.24, 1.0], metallic=0.12, roughness=0.74)
    create_material(project, name="DeckStripe", color=[0.9, 0.52, 0.14, 1.0], metallic=0.05, roughness=0.46)
    create_material(project, name="HullWhite", color=[0.88, 0.9, 0.93, 1.0], metallic=0.18, roughness=0.2)
    create_material(project, name="SignalOrange", color=[0.94, 0.44, 0.12, 1.0], metallic=0.12, roughness=0.3)
    create_material(project, name="PanelBlue", color=[0.12, 0.34, 0.72, 1.0], metallic=0.0, roughness=0.16)
    create_material(project, name="EngineDark", color=[0.07, 0.08, 0.11, 1.0], metallic=0.55, roughness=0.2)
    create_material(project, name="GlowCyan", color=[0.38, 0.86, 1.0, 1.0], metallic=0.0, roughness=0.06)
    set_material_property(project, _material_index(project, "GlowCyan"), "emission_color", [0.38, 0.86, 1.0, 1.0])
    set_material_property(project, _material_index(project, "GlowCyan"), "emission_strength", 7.2)


def _configure_scene(project: Dict) -> None:
    project["world"]["background_color"] = [0.08, 0.1, 0.16]
    set_render_settings(project, preset="eevee_preview")
    add_camera(
        project,
        name="HeroCam",
        location=[9.6, -7.6, 5.7],
        rotation=[71, 0, 52],
        focal_length=40,
        set_active=True,
    )
    add_light(project, light_type="SUN", name="SunKey", rotation=[-42, 0, 26], power=3.4)
    add_light(project, light_type="AREA", name="RimFill", location=[-5.6, 5.1, 5.0], rotation=[56, 0, -34], power=2600)
    add_light(project, light_type="POINT", name="FrontBounce", location=[2.8, -3.6, 3.9], power=620)
    add_light(project, light_type="POINT", name="BeaconBounce", location=[0.0, 0.0, 3.35], power=180)


def _build_stage_00_launch_platform(project: Dict) -> None:
    add_object(project, mesh_type="plane", name="DeckFloor", mesh_params={"size": 22.0}, location=[0, 0, 0])
    add_object(
        project,
        mesh_type="cylinder",
        name="DisplayBase",
        location=[0, 0, 0.22],
        mesh_params={"radius": 3.2, "depth": 0.44, "vertices": 56},
    )
    add_modifier(project, "bevel", _object_index(project, "DisplayBase"), params={"width": 0.06, "segments": 2})
    add_object(
        project,
        mesh_type="cylinder",
        name="LaunchPad",
        location=[0, 0, 0.5],
        mesh_params={"radius": 2.08, "depth": 0.16, "vertices": 56},
    )
    add_modifier(project, "bevel", _object_index(project, "LaunchPad"), params={"width": 0.025, "segments": 2})
    add_object(
        project,
        mesh_type="torus",
        name="PadStripeRing",
        location=[0, 0, 0.59],
        rotation=[90, 0, 0],
        mesh_params={"major_radius": 1.62, "minor_radius": 0.032, "major_segments": 64, "minor_segments": 12},
    )
    add_object(
        project,
        mesh_type="cylinder",
        name="LiftColumn",
        location=[0, 0, 1.32],
        mesh_params={"radius": 0.18, "depth": 1.42, "vertices": 32},
    )
    add_modifier(project, "bevel", _object_index(project, "LiftColumn"), params={"width": 0.02, "segments": 2})


def _build_stage_01_hull_blockout(project: Dict) -> None:
    add_object(project, mesh_type="empty", name="DroneRoot", location=[0, 0, 0], rotation=[0, 0, 18])
    add_object(
        project,
        mesh_type="cylinder",
        name="HullCore",
        location=[0.12, 0, 2.82],
        rotation=[0, 90, 0],
        mesh_params={"radius": 0.58, "depth": 3.4, "vertices": 40},
    )
    add_modifier(project, "bevel", _object_index(project, "HullCore"), params={"width": 0.04, "segments": 2})
    add_object(
        project,
        mesh_type="cone",
        name="NoseCone",
        location=[2.04, 0, 2.82],
        rotation=[0, 90, 0],
        mesh_params={"radius1": 0.58, "radius2": 0.08, "depth": 1.05, "vertices": 40},
    )
    add_modifier(project, "bevel", _object_index(project, "NoseCone"), params={"width": 0.018, "segments": 2})
    add_object(
        project,
        mesh_type="sphere",
        name="BridgePod",
        location=[1.26, 0, 3.2],
        scale=[0.66, 0.48, 0.38],
        mesh_params={"radius": 1.0, "segments": 28, "rings": 16},
    )
    add_modifier(project, "subdivision_surface", _object_index(project, "BridgePod"), params={"levels": 2, "render_levels": 2})
    add_object(
        project,
        mesh_type="torus",
        name="DockRing",
        location=[2.54, 0, 2.82],
        rotation=[0, 90, 0],
        mesh_params={"major_radius": 0.54, "minor_radius": 0.07, "major_segments": 56, "minor_segments": 14},
    )
    add_object(
        project,
        mesh_type="cube",
        name="ServiceCabin",
        location=[0.08, 0, 3.44],
        scale=[0.56, 0.42, 0.3],
    )
    add_modifier(project, "bevel", _object_index(project, "ServiceCabin"), params={"width": 0.03, "segments": 2})


def _build_stage_02_wing_structure(project: Dict) -> None:
    add_object(
        project,
        mesh_type="cube",
        name="WingSpar",
        location=[-0.28, 0, 2.8],
        scale=[0.16, 1.24, 0.1],
    )
    add_modifier(project, "bevel", _object_index(project, "WingSpar"), params={"width": 0.015, "segments": 2})
    add_object(
        project,
        mesh_type="cube",
        name="PanelArmLeft",
        location=[-0.08, 1.08, 2.84],
        rotation=[0, 0, 18],
        scale=[0.56, 0.08, 0.06],
    )
    add_object(
        project,
        mesh_type="cube",
        name="PanelArmRight",
        location=[-0.08, -1.08, 2.84],
        rotation=[0, 0, -18],
        scale=[0.56, 0.08, 0.06],
    )


def _build_stage_03_solar_arrays(project: Dict) -> None:
    add_object(
        project,
        mesh_type="cube",
        name="SolarPanelLeft",
        location=[-0.56, 2.26, 2.92],
        rotation=[0, 0, 16],
        scale=[1.22, 0.04, 0.68],
    )
    add_modifier(project, "bevel", _object_index(project, "SolarPanelLeft"), params={"width": 0.02, "segments": 2})
    add_object(
        project,
        mesh_type="cube",
        name="SolarPanelRight",
        location=[-0.56, -2.26, 2.92],
        rotation=[0, 0, -16],
        scale=[1.22, 0.04, 0.68],
    )
    add_modifier(project, "bevel", _object_index(project, "SolarPanelRight"), params={"width": 0.02, "segments": 2})
    add_object(
        project,
        mesh_type="cube",
        name="SolarRibLeft",
        location=[-1.52, 2.3, 2.92],
        rotation=[0, 0, 16],
        scale=[0.06, 0.012, 0.58],
    )
    add_modifier(
        project,
        "array",
        _object_index(project, "SolarRibLeft"),
        params={"count": 7, "relative_offset_x": 1.95, "relative_offset_y": 0.0, "relative_offset_z": 0.0},
    )
    add_object(
        project,
        mesh_type="cube",
        name="SolarRibRight",
        location=[-1.52, -2.3, 2.92],
        rotation=[0, 0, -16],
        scale=[0.06, 0.012, 0.58],
    )
    add_modifier(
        project,
        "array",
        _object_index(project, "SolarRibRight"),
        params={"count": 7, "relative_offset_x": 1.95, "relative_offset_y": 0.0, "relative_offset_z": 0.0},
    )


def _build_stage_04_propulsion(project: Dict) -> None:
    add_object(
        project,
        mesh_type="cube",
        name="EngineBlock",
        location=[-1.92, 0, 2.72],
        scale=[0.54, 0.68, 0.52],
    )
    add_modifier(project, "bevel", _object_index(project, "EngineBlock"), params={"width": 0.03, "segments": 2})

    thrusters = [
        ("ThrusterTopLeft", [-2.45, 0.34, 2.98]),
        ("ThrusterBottomLeft", [-2.45, 0.34, 2.36]),
        ("ThrusterTopRight", [-2.45, -0.34, 2.98]),
        ("ThrusterBottomRight", [-2.45, -0.34, 2.36]),
    ]
    for name, location in thrusters:
        add_object(
            project,
            mesh_type="cylinder",
            name=name,
            location=location,
            rotation=[0, 90, 0],
            mesh_params={"radius": 0.16, "depth": 0.28, "vertices": 28},
        )
    nozzles = [
        ("NozzleTopLeft", [-2.76, 0.34, 2.98]),
        ("NozzleBottomLeft", [-2.76, 0.34, 2.36]),
        ("NozzleTopRight", [-2.76, -0.34, 2.98]),
        ("NozzleBottomRight", [-2.76, -0.34, 2.36]),
    ]
    for name, location in nozzles:
        add_object(
            project,
            mesh_type="cone",
            name=name,
            location=location,
            rotation=[0, 90, 0],
            mesh_params={"radius1": 0.24, "radius2": 0.08, "depth": 0.42, "vertices": 24},
        )


def _build_stage_05_sensor_payload(project: Dict) -> None:
    add_object(project, mesh_type="empty", name="DishPivot", location=[0.62, 0, 4.18])
    add_object(
        project,
        mesh_type="cylinder",
        name="SensorMast",
        location=[0.46, 0, 3.72],
        mesh_params={"radius": 0.06, "depth": 0.92, "vertices": 18},
    )
    add_object(
        project,
        mesh_type="cone",
        name="RadarDish",
        location=[1.12, 0, 4.18],
        rotation=[0, 90, 0],
        mesh_params={"radius1": 0.58, "radius2": 0.06, "depth": 0.42, "vertices": 36},
    )
    add_modifier(project, "bevel", _object_index(project, "RadarDish"), params={"width": 0.015, "segments": 2})
    add_object(
        project,
        mesh_type="sphere",
        name="BeaconCore",
        location=[0.1, 0, 2.92],
        scale=[0.22, 0.22, 0.22],
        mesh_params={"radius": 1.0, "segments": 24, "rings": 12},
    )
    add_modifier(project, "subdivision_surface", _object_index(project, "BeaconCore"), params={"levels": 1, "render_levels": 2})
    add_object(
        project,
        mesh_type="sphere",
        name="NavLightLeft",
        location=[-0.14, 3.28, 2.98],
        scale=[0.11, 0.11, 0.11],
        mesh_params={"radius": 1.0, "segments": 18, "rings": 10},
    )
    add_object(
        project,
        mesh_type="sphere",
        name="NavLightRight",
        location=[-0.14, -3.28, 2.98],
        scale=[0.11, 0.11, 0.11],
        mesh_params={"radius": 1.0, "segments": 18, "rings": 10},
    )


def _build_stage_06_service_rig(project: Dict) -> None:
    add_object(
        project,
        mesh_type="cylinder",
        name="ServiceArmBase",
        location=[-0.2, -0.62, 2.18],
        rotation=[90, 0, 0],
        mesh_params={"radius": 0.07, "depth": 0.46, "vertices": 16},
    )
    add_object(
        project,
        mesh_type="cylinder",
        name="ServiceArmReach",
        location=[0.42, -0.92, 2.02],
        rotation=[0, 26, 42],
        mesh_params={"radius": 0.055, "depth": 1.15, "vertices": 16},
    )
    add_object(
        project,
        mesh_type="cone",
        name="ServiceTool",
        location=[0.92, -1.34, 1.88],
        rotation=[0, -65, 42],
        mesh_params={"radius1": 0.11, "radius2": 0.02, "depth": 0.36, "vertices": 18},
    )
    add_object(
        project,
        mesh_type="cube",
        name="CommFin",
        location=[-0.96, 0, 3.62],
        scale=[0.1, 0.62, 0.34],
    )
    add_modifier(project, "bevel", _object_index(project, "CommFin"), params={"width": 0.012, "segments": 2})


def _assign_materials(project: Dict) -> None:
    for object_name in ("DeckFloor", "DisplayBase", "LaunchPad", "LiftColumn"):
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "DeckGraphite", object_name)
    for object_name in ("PadStripeRing",):
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "DeckStripe", object_name)

    hull_white = ("HullCore", "NoseCone", "BridgePod", "ServiceCabin", "PanelArmLeft", "PanelArmRight", "SensorMast", "RadarDish")
    for object_name in hull_white:
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "HullWhite", object_name)

    orange_parts = ("DockRing", "CommFin", "WingSpar", "ServiceArmBase", "ServiceArmReach", "ServiceTool")
    for object_name in orange_parts:
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "SignalOrange", object_name)

    panel_parts = ("SolarPanelLeft", "SolarPanelRight", "SolarRibLeft", "SolarRibRight")
    for object_name in panel_parts:
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "PanelBlue", object_name)

    engine_parts = (
        "EngineBlock",
        "ThrusterTopLeft",
        "ThrusterBottomLeft",
        "ThrusterTopRight",
        "ThrusterBottomRight",
        "NozzleTopLeft",
        "NozzleBottomLeft",
        "NozzleTopRight",
        "NozzleBottomRight",
    )
    for object_name in engine_parts:
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "EngineDark", object_name)

    glow_parts = ("BeaconCore", "NavLightLeft", "NavLightRight")
    for object_name in glow_parts:
        if any(obj.get("name") == object_name for obj in project["objects"]):
            _assign(project, "GlowCyan", object_name)


def _rig_parents(project: Dict) -> None:
    root_children = [
        "HullCore",
        "NoseCone",
        "BridgePod",
        "DockRing",
        "ServiceCabin",
        "WingSpar",
        "PanelArmLeft",
        "PanelArmRight",
        "SolarPanelLeft",
        "SolarPanelRight",
        "SolarRibLeft",
        "SolarRibRight",
        "EngineBlock",
        "ThrusterTopLeft",
        "ThrusterBottomLeft",
        "ThrusterTopRight",
        "ThrusterBottomRight",
        "NozzleTopLeft",
        "NozzleBottomLeft",
        "NozzleTopRight",
        "NozzleBottomRight",
        "SensorMast",
        "BeaconCore",
        "NavLightLeft",
        "NavLightRight",
        "ServiceArmBase",
        "ServiceArmReach",
        "ServiceTool",
        "CommFin",
        "DishPivot",
    ]
    for child_name in root_children:
        if any(obj.get("name") == child_name for obj in project["objects"]):
            _set_parent(project, child_name, "DroneRoot")

    for child_name in ("RadarDish",):
        if any(obj.get("name") == child_name for obj in project["objects"]):
            _set_parent(project, child_name, "DishPivot")


def _add_motion(project: Dict) -> None:
    set_frame_range(project, 1, 36)
    set_fps(project, 12)

    add_keyframe(project, _object_index(project, "DroneRoot"), 1, "location", [0, 0, 0], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "DroneRoot"), 18, "location", [0, 0, 0.14], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "DroneRoot"), 36, "location", [0, 0, 0], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "DroneRoot"), 1, "rotation", [0, 0, 18], interpolation="LINEAR")
    add_keyframe(project, _object_index(project, "DroneRoot"), 36, "rotation", [0, 0, 378], interpolation="LINEAR")

    add_keyframe(project, _object_index(project, "DishPivot"), 1, "rotation", [0, 0, 0], interpolation="LINEAR")
    add_keyframe(project, _object_index(project, "DishPivot"), 36, "rotation", [0, 0, 540], interpolation="LINEAR")

    add_keyframe(project, _object_index(project, "DockRing"), 1, "rotation", [0, 90, 0], interpolation="LINEAR")
    add_keyframe(project, _object_index(project, "DockRing"), 36, "rotation", [0, 90, 360], interpolation="LINEAR")

    add_keyframe(project, _object_index(project, "BeaconCore"), 1, "scale", [0.22, 0.22, 0.22], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "BeaconCore"), 12, "scale", [0.33, 0.33, 0.33], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "BeaconCore"), 24, "scale", [0.22, 0.22, 0.22], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "BeaconCore"), 36, "scale", [0.31, 0.31, 0.31], interpolation="BEZIER")

    add_keyframe(project, _object_index(project, "NavLightLeft"), 1, "scale", [0.11, 0.11, 0.11], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "NavLightLeft"), 18, "scale", [0.16, 0.16, 0.16], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "NavLightLeft"), 36, "scale", [0.11, 0.11, 0.11], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "NavLightRight"), 1, "scale", [0.11, 0.11, 0.11], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "NavLightRight"), 18, "scale", [0.16, 0.16, 0.16], interpolation="BEZIER")
    add_keyframe(project, _object_index(project, "NavLightRight"), 36, "scale", [0.11, 0.11, 0.11], interpolation="BEZIER")

    set_current_frame(project, 1)


def _capture_stage(
    session: Session,
    stage_name: str,
    stage_log: List[Dict],
    preview_root: Path,
    started: bool,
    *,
    label: str,
    story: str,
    display_cmd: str,
    duration_s: float,
) -> bool:
    if not started:
        live_payload = preview_mod.live_start(
            session,
            recipe="quick",
            root_dir=str(preview_root),
            force=True,
            refresh_hint_ms=1000,
            live_mode="manual",
            publish_reason=f"stage:{stage_name}",
            command=f"blender_demo.py --stage {stage_name}",
        )
    else:
        live_payload = preview_mod.live_push(
            session,
            recipe="quick",
            root_dir=str(preview_root),
            force=True,
            refresh_hint_ms=1000,
            publish_reason=f"stage:{stage_name}",
            command=f"blender_demo.py --stage {stage_name}",
        )
    stage_log.append(
        {
            "stage": stage_name,
            "bundle_id": live_payload.get("current_bundle_id"),
            "bundle_count": live_payload.get("bundle_count"),
            "session_path": live_payload.get("_session_path"),
            "current_manifest_path": live_payload.get("current_manifest_path"),
            "current_bundle_dir": live_payload.get("current_bundle_dir"),
            "label": label,
            "story": story,
            "display_cmd": display_cmd,
            "duration_s": duration_s,
        }
    )
    return True


def build_demo(output_dir: Path, use_live_preview: bool = True) -> Dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_root = output_dir / "live-root"
    project_path = output_dir / "orbital_relay_drone.blend-cli.json"
    manifest_path = output_dir / "build_manifest.json"
    final_render_path = output_dir / "renders" / "orbital_relay_drone_final.png"
    frames_dir = output_dir / "motion" / "frames"
    video_path = output_dir / "motion" / "orbital_relay_drone_turntable.mp4"
    stills_dir = output_dir / "motion" / "stills"

    project = create_scene(name="orbital-relay-drone", profile="preview")
    _configure_scene(project)
    _add_materials(project)

    session = Session()
    stage_log: List[Dict] = []
    live_started = False

    _build_stage_00_launch_platform(project)
    _assign_materials(project)
    print("[demo] Stage 00: launch platform")
    save_scene(project, str(project_path))
    session.set_project(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "00_launch_platform",
            stage_log,
            preview_root,
            live_started,
            label="Build launch platform",
            story="Deck floor, display base, raised launch pad, stripe ring, and center lift column.",
            display_cmd="add DeckFloor / DisplayBase / LaunchPad / PadStripeRing / LiftColumn",
            duration_s=0.9,
        )

    _build_stage_01_hull_blockout(project)
    _assign_materials(project)
    print("[demo] Stage 01: hull blockout")
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "01_hull_blockout",
            stage_log,
            preview_root,
            live_started,
            label="Block out the hull and docking silhouette",
            story="Drone root, main hull cylinder, nose cone, bridge pod, docking ring, and service cabin.",
            display_cmd="add DroneRoot / HullCore / NoseCone / BridgePod / DockRing / ServiceCabin",
            duration_s=1.0,
        )

    _build_stage_02_wing_structure(project)
    _assign_materials(project)
    print("[demo] Stage 02: wing structure")
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "02_wing_structure",
            stage_log,
            preview_root,
            live_started,
            label="Add wing spar and panel arms",
            story="The drone starts reading as a spacecraft once the lateral wing spar and panel hinges appear.",
            display_cmd="add WingSpar / PanelArmLeft / PanelArmRight",
            duration_s=0.8,
        )

    _build_stage_03_solar_arrays(project)
    _assign_materials(project)
    print("[demo] Stage 03: solar arrays")
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "03_solar_arrays",
            stage_log,
            preview_root,
            live_started,
            label="Add solar panels and rib arrays",
            story="Blue panel slabs and rib arrays turn the side arms into readable power modules.",
            display_cmd="add SolarPanelLeft/Right / array SolarRibLeft/Right",
            duration_s=0.9,
        )

    _build_stage_04_propulsion(project)
    _assign_materials(project)
    print("[demo] Stage 04: propulsion")
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "04_propulsion",
            stage_log,
            preview_root,
            live_started,
            label="Add engine block and thruster pack",
            story="The rear engine block and clustered nozzles complete the propulsion silhouette.",
            display_cmd="add EngineBlock / thrusters / nozzle cones",
            duration_s=0.9,
        )

    _build_stage_05_sensor_payload(project)
    _assign_materials(project)
    print("[demo] Stage 05: sensor payload")
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "05_sensor_payload",
            stage_log,
            preview_root,
            live_started,
            label="Add radar dish and navigation payloads",
            story="Dish pivot, radar plate, beacon core, and nav lights add the recognizable inspection payloads.",
            display_cmd="add DishPivot / SensorMast / RadarDish / BeaconCore / NavLightLeft/Right",
            duration_s=0.9,
        )

    _build_stage_06_service_rig(project)
    _assign_materials(project)
    _rig_parents(project)
    print("[demo] Stage 06: service rig")
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "06_service_rig",
            stage_log,
            preview_root,
            live_started,
            label="Add service arm and parenting rig",
            story="Service arm, comm fin, and object parenting wire the drone into an assembled, animatable artifact.",
            display_cmd="add ServiceArmBase / ServiceArmReach / ServiceTool / CommFin / set parent hierarchy",
            duration_s=1.0,
        )

    _add_motion(project)
    print("[demo] Stage 07: motion ready")
    set_current_frame(project, 18)
    save_scene(project, str(project_path))
    if use_live_preview:
        live_started = _capture_stage(
            session,
            "07_motion_ready",
            stage_log,
            preview_root,
            live_started,
            label="Author hover, spin, and beacon motion",
            story="Hover motion, dish spin, ring rotation, and beacon pulses prepare the final presentation state.",
            display_cmd="add_keyframe DroneRoot / DishPivot / DockRing / BeaconCore / NavLights",
            duration_s=1.0,
        )
        set_current_frame(project, 1)
        save_scene(project, str(project_path))
        live_payload = preview_mod.live_stop(session, recipe="quick", root_dir=str(preview_root))
        live_html = _render_live_html(Path(live_payload["_session_dir"]), output_dir / "live.html")
    else:
        set_current_frame(project, 1)
        save_scene(project, str(project_path))
        live_payload = None
        live_html = None

    final_project = copy.deepcopy(project)
    set_render_settings(final_project, preset="eevee_high", resolution_x=1440, resolution_y=810, samples=48, output_format="PNG")
    set_current_frame(final_project, 1)
    print(f"[demo] Rendering final still -> {final_render_path}")
    final_render = _render_via_script(final_project, final_render_path, frame=1, animation=False, timeout=720)
    if not final_render_path.exists():
        raise RuntimeError(f"Final render missing: {final_render_path}")
    final_render["output"] = str(final_render_path)
    final_render["file_size"] = final_render_path.stat().st_size
    final_render["blender_version"] = blender_backend.get_version()

    motion_project = copy.deepcopy(project)
    set_render_settings(motion_project, preset="eevee_default", resolution_x=640, resolution_y=360, samples=8, output_format="PNG")
    print(f"[demo] Rendering motion frames -> {frames_dir}")
    motion_job = _render_via_script(motion_project, frames_dir / "frame_", animation=True, timeout=1200)
    frame_files = sorted(frames_dir.glob("frame_*.png"))
    if not frame_files:
        raise RuntimeError(f"Animation render produced no frames under {frames_dir}")
    print(f"[demo] Encoding motion video -> {video_path}")
    motion_video = _encode_video(frames_dir, video_path, fps=int(motion_project["scene"]["fps"]))
    motion_stills = _copy_motion_stills(frame_files, stills_dir)

    payload = {
        "project_path": str(project_path),
        "preview_root": str(preview_root),
        "stage_log": stage_log,
        "live_session": live_payload,
        "live_html": live_html,
        "final_render": final_render,
        "motion": {
            "frames_dir": str(frames_dir),
            "frame_count": len(frame_files),
            "first_frame": str(frame_files[0]),
            "last_frame": str(frame_files[-1]),
            "render_job": motion_job,
            "video": motion_video,
            "stills": motion_stills,
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="/root/preview-artifacts/20260422/blender-orbital-relay-drone-v6",
        help="Directory for the generated scene, preview bundles, live session, trajectory.json, final render, and motion video.",
    )
    parser.add_argument(
        "--no-live-preview",
        action="store_true",
        help="Skip stage-by-stage preview bundle capture.",
    )
    args = parser.parse_args()

    result = build_demo(Path(args.output_dir).expanduser().resolve(), use_live_preview=not args.no_live_preview)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
