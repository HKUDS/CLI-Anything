"""Blender CLI - Camera and light management module."""

import copy
from typing import Dict, Any, List, Optional
import math


# Camera types
CAMERA_TYPES = ["PERSP", "ORTHO", "PANO"]

# Light types and their default properties
LIGHT_TYPES = {
    "POINT": {"power": 1000.0, "color": [1.0, 1.0, 1.0], "radius": 0.25},
    "SUN": {"power": 1.0, "color": [1.0, 1.0, 1.0], "angle": 0.00918},
    "SPOT": {"power": 1000.0, "color": [1.0, 1.0, 1.0], "radius": 0.25,
             "spot_size": 0.785398, "spot_blend": 0.15},
    "AREA": {"power": 1000.0, "color": [1.0, 1.0, 1.0], "size": 1.0, "size_y": 1.0,
             "shape": "RECTANGLE"},
}


def _next_camera_id(project: Dict[str, Any]) -> int:
    cameras = project.get("cameras", [])
    existing_ids = [c.get("id", 0) for c in cameras]
    return max(existing_ids, default=-1) + 1


def _next_light_id(project: Dict[str, Any]) -> int:
    lights = project.get("lights", [])
    existing_ids = [l.get("id", 0) for l in lights]
    return max(existing_ids, default=-1) + 1


def _unique_camera_name(project: Dict[str, Any], base_name: str) -> str:
    cameras = project.get("cameras", [])
    existing_names = {c.get("name", "") for c in cameras}
    if base_name not in existing_names:
        return base_name
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


def _unique_light_name(project: Dict[str, Any], base_name: str) -> str:
    lights = project.get("lights", [])
    existing_names = {l.get("name", "") for l in lights}
    if base_name not in existing_names:
        return base_name
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


# ── Camera Functions ─────────────────────────────────────────────

def add_camera(
    project: Dict[str, Any],
    name: Optional[str] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    camera_type: str = "PERSP",
    focal_length: float = 50.0,
    sensor_width: float = 36.0,
    clip_start: float = 0.1,
    clip_end: float = 1000.0,
    set_active: bool = False,
) -> Dict[str, Any]:
    """Add a camera to the scene.

    Args:
        project: The scene dict
        name: Camera name
        location: [x, y, z] position
        rotation: [x, y, z] rotation in degrees
        camera_type: PERSP, ORTHO, or PANO
        focal_length: Lens focal length in mm
        sensor_width: Camera sensor width in mm
        clip_start: Near clipping distance
        clip_end: Far clipping distance
        set_active: Whether to set this as the active camera

    Returns:
        The new camera dict
    """
    if camera_type not in CAMERA_TYPES:
        raise ValueError(f"Invalid camera type: {camera_type}. Valid: {CAMERA_TYPES}")
    if focal_length <= 0:
        raise ValueError(f"Focal length must be positive: {focal_length}")
    if clip_start <= 0:
        raise ValueError(f"Clip start must be positive: {clip_start}")
    if clip_end <= clip_start:
        raise ValueError(f"Clip end ({clip_end}) must be greater than clip start ({clip_start})")
    if location is not None and len(location) != 3:
        raise ValueError(f"Location must have 3 components, got {len(location)}")
    if rotation is not None and len(rotation) != 3:
        raise ValueError(f"Rotation must have 3 components, got {len(rotation)}")

    cam_name = _unique_camera_name(project, name or "Camera")

    camera = {
        "id": _next_camera_id(project),
        "name": cam_name,
        "type": camera_type,
        "location": list(location) if location else [0.0, 0.0, 5.0],
        "rotation": list(rotation) if rotation else [0.0, 0.0, 0.0],
        "focal_length": focal_length,
        "sensor_width": sensor_width,
        "clip_start": clip_start,
        "clip_end": clip_end,
        "dof_enabled": False,
        "dof_focus_distance": 10.0,
        "dof_aperture": 2.8,
        "is_active": False,
    }

    if "cameras" not in project:
        project["cameras"] = []
    project["cameras"].append(camera)

    if set_active or len(project["cameras"]) == 1:
        # Set as active camera (deactivate others)
        for cam in project["cameras"]:
            cam["is_active"] = False
        camera["is_active"] = True

    return camera


def set_camera(
    project: Dict[str, Any],
    index: int,
    prop: str,
    value: Any,
) -> None:
    """Set a camera property.

    Args:
        project: The scene dict
        index: Camera index
        prop: Property name
        value: New value
    """
    cameras = project.get("cameras", [])
    if index < 0 or index >= len(cameras):
        raise IndexError(f"Camera index {index} out of range (0-{len(cameras)-1})")

    cam = cameras[index]
    valid_props = [
        "location", "rotation", "focal_length", "sensor_width",
        "clip_start", "clip_end", "type", "name",
        "dof_enabled", "dof_focus_distance", "dof_aperture",
    ]

    if prop not in valid_props:
        raise ValueError(f"Unknown camera property: {prop}. Valid: {valid_props}")

    if prop == "location":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Location must have 3 components")
        cam["location"] = [float(x) for x in value]
    elif prop == "rotation":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Rotation must have 3 components")
        cam["rotation"] = [float(x) for x in value]
    elif prop == "focal_length":
        val = float(value)
        if val <= 0:
            raise ValueError(f"Focal length must be positive: {val}")
        cam["focal_length"] = val
    elif prop == "sensor_width":
        val = float(value)
        if val <= 0:
            raise ValueError(f"Sensor width must be positive: {val}")
        cam["sensor_width"] = val
    elif prop == "clip_start":
        val = float(value)
        if val <= 0:
            raise ValueError(f"Clip start must be positive: {val}")
        cam["clip_start"] = val
    elif prop == "clip_end":
        cam["clip_end"] = float(value)
    elif prop == "type":
        if value not in CAMERA_TYPES:
            raise ValueError(f"Invalid camera type: {value}. Valid: {CAMERA_TYPES}")
        cam["type"] = value
    elif prop == "name":
        cam["name"] = str(value)
    elif prop == "dof_enabled":
        cam["dof_enabled"] = str(value).lower() in ("true", "1", "yes")
    elif prop == "dof_focus_distance":
        cam["dof_focus_distance"] = float(value)
    elif prop == "dof_aperture":
        cam["dof_aperture"] = float(value)


def set_active_camera(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Set the active camera by index."""
    cameras = project.get("cameras", [])
    if index < 0 or index >= len(cameras):
        raise IndexError(f"Camera index {index} out of range (0-{len(cameras)-1})")

    for cam in cameras:
        cam["is_active"] = False
    cameras[index]["is_active"] = True

    return {
        "active_camera": cameras[index]["name"],
        "index": index,
    }


def get_camera(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get a camera by index."""
    cameras = project.get("cameras", [])
    if index < 0 or index >= len(cameras):
        raise IndexError(f"Camera index {index} out of range (0-{len(cameras)-1})")
    return cameras[index]


def list_cameras(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all cameras with summary info."""
    result = []
    for i, cam in enumerate(project.get("cameras", [])):
        result.append({
            "index": i,
            "id": cam.get("id", i),
            "name": cam.get("name", f"Camera {i}"),
            "type": cam.get("type", "PERSP"),
            "location": cam.get("location", [0, 0, 5]),
            "rotation": cam.get("rotation", [0, 0, 0]),
            "focal_length": cam.get("focal_length", 50.0),
            "is_active": cam.get("is_active", False),
        })
    return result


# ── Light Functions ──────────────────────────────────────────────

def add_light(
    project: Dict[str, Any],
    light_type: str = "POINT",
    name: Optional[str] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    color: Optional[List[float]] = None,
    power: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a light to the scene.

    Args:
        project: The scene dict
        light_type: POINT, SUN, SPOT, or AREA
        name: Light name
        location: [x, y, z] position
        rotation: [x, y, z] rotation in degrees
        color: [R, G, B] color (0.0-1.0)
        power: Light power/energy (watts for point/spot/area, unitless for sun)

    Returns:
        The new light dict
    """
    light_type = light_type.upper()
    if light_type not in LIGHT_TYPES:
        raise ValueError(f"Invalid light type: {light_type}. Valid: {list(LIGHT_TYPES.keys())}")

    if location is not None and len(location) != 3:
        raise ValueError(f"Location must have 3 components, got {len(location)}")
    if rotation is not None and len(rotation) != 3:
        raise ValueError(f"Rotation must have 3 components, got {len(rotation)}")
    if color is not None:
        if len(color) != 3:
            raise ValueError(f"Color must have 3 components [R, G, B], got {len(color)}")
        for i, c in enumerate(color):
            if not 0.0 <= c <= 1.0:
                raise ValueError(f"Color component {i} must be 0.0-1.0, got {c}")
    if power is not None and power < 0:
        raise ValueError(f"Power must be non-negative: {power}")

    defaults = LIGHT_TYPES[light_type]
    light_name = _unique_light_name(project, name or light_type.capitalize())

    light = {
        "id": _next_light_id(project),
        "name": light_name,
        "type": light_type,
        "location": list(location) if location else [0.0, 0.0, 3.0],
        "rotation": list(rotation) if rotation else [0.0, 0.0, 0.0],
        "color": list(color) if color else list(defaults["color"]),
        "power": power if power is not None else defaults["power"],
    }

    # Add type-specific properties
    if light_type == "POINT":
        light["radius"] = defaults["radius"]
    elif light_type == "SUN":
        light["angle"] = defaults["angle"]
    elif light_type == "SPOT":
        light["radius"] = defaults["radius"]
        light["spot_size"] = defaults["spot_size"]
        light["spot_blend"] = defaults["spot_blend"]
    elif light_type == "AREA":
        light["size"] = defaults["size"]
        light["size_y"] = defaults["size_y"]
        light["shape"] = defaults["shape"]

    if "lights" not in project:
        project["lights"] = []
    project["lights"].append(light)

    return light


def set_light(
    project: Dict[str, Any],
    index: int,
    prop: str,
    value: Any,
) -> None:
    """Set a light property.

    Args:
        project: The scene dict
        index: Light index
        prop: Property name
        value: New value
    """
    lights = project.get("lights", [])
    if index < 0 or index >= len(lights):
        raise IndexError(f"Light index {index} out of range (0-{len(lights)-1})")

    light = lights[index]
    valid_props = [
        "location", "rotation", "color", "power", "name",
        "radius", "angle", "spot_size", "spot_blend",
        "size", "size_y", "shape",
    ]

    if prop not in valid_props:
        raise ValueError(f"Unknown light property: {prop}. Valid: {valid_props}")

    if prop == "location":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Location must have 3 components")
        light["location"] = [float(x) for x in value]
    elif prop == "rotation":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Rotation must have 3 components")
        light["rotation"] = [float(x) for x in value]
    elif prop == "color":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Color must have 3 components [R, G, B]")
        for i, c in enumerate(value):
            if not 0.0 <= float(c) <= 1.0:
                raise ValueError(f"Color component {i} must be 0.0-1.0, got {c}")
        light["color"] = [float(x) for x in value]
    elif prop == "power":
        val = float(value)
        if val < 0:
            raise ValueError(f"Power must be non-negative: {val}")
        light["power"] = val
    elif prop == "name":
        light["name"] = str(value)
    elif prop in ("radius", "angle", "spot_size", "spot_blend", "size", "size_y"):
        light[prop] = float(value)
    elif prop == "shape":
        if value not in ("RECTANGLE", "SQUARE", "DISK", "ELLIPSE"):
            raise ValueError(f"Invalid shape: {value}. Valid: RECTANGLE, SQUARE, DISK, ELLIPSE")
        light["shape"] = value


def get_light(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get a light by index."""
    lights = project.get("lights", [])
    if index < 0 or index >= len(lights):
        raise IndexError(f"Light index {index} out of range (0-{len(lights)-1})")
    return lights[index]


def list_lights(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all lights with summary info."""
    result = []
    for i, light in enumerate(project.get("lights", [])):
        result.append({
            "index": i,
            "id": light.get("id", i),
            "name": light.get("name", f"Light {i}"),
            "type": light.get("type", "POINT"),
            "location": light.get("location", [0, 0, 3]),
            "color": light.get("color", [1, 1, 1]),
            "power": light.get("power", 1000),
        })
    return result
