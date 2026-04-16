"""Blender CLI - Animation and keyframe management module."""

from typing import Dict, Any, List, Optional


# Valid keyframe properties that can be animated
ANIMATABLE_PROPERTIES = [
    "location", "rotation", "scale", "visible",
    "material.color", "material.metallic", "material.roughness",
    "material.alpha", "material.emission_strength",
]

# Keyframe interpolation types
INTERPOLATION_TYPES = ["CONSTANT", "LINEAR", "BEZIER"]


def add_keyframe(
    project: Dict[str, Any],
    object_index: int,
    frame: int,
    prop: str,
    value: Any,
    interpolation: str = "BEZIER",
) -> Dict[str, Any]:
    """Add a keyframe to an object.

    Args:
        project: The scene dict
        object_index: Index of the target object
        frame: Frame number for the keyframe
        prop: Property to animate (location, rotation, scale, visible)
        value: Value at this keyframe
        interpolation: Interpolation type (CONSTANT, LINEAR, BEZIER)

    Returns:
        The new keyframe entry dict
    """
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range (0-{len(objects)-1})")

    if prop not in ANIMATABLE_PROPERTIES:
        raise ValueError(
            f"Cannot animate property '{prop}'. Valid: {ANIMATABLE_PROPERTIES}"
        )

    interpolation = interpolation.upper()
    if interpolation not in INTERPOLATION_TYPES:
        raise ValueError(
            f"Invalid interpolation: {interpolation}. Valid: {INTERPOLATION_TYPES}"
        )

    scene = project.get("scene", {})
    if frame < scene.get("frame_start", 0):
        raise ValueError(
            f"Frame {frame} is before scene start ({scene.get('frame_start', 0)})"
        )

    # Parse the value based on property type
    if prop in ("location", "rotation", "scale"):
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError(f"Property '{prop}' requires 3 components [x, y, z]")
        value = [float(x) for x in value]
    elif prop == "visible":
        value = str(value).lower() in ("true", "1", "yes")
    elif prop.startswith("material."):
        value = float(value)

    obj = objects[object_index]
    if "keyframes" not in obj:
        obj["keyframes"] = []

    # Check if keyframe already exists at this frame for this property
    for kf in obj["keyframes"]:
        if kf["frame"] == frame and kf["property"] == prop:
            kf["value"] = value
            kf["interpolation"] = interpolation
            return kf

    keyframe = {
        "frame": frame,
        "property": prop,
        "value": value,
        "interpolation": interpolation,
    }

    obj["keyframes"].append(keyframe)
    # Keep keyframes sorted by frame
    obj["keyframes"].sort(key=lambda k: (k["property"], k["frame"]))

    return keyframe


def remove_keyframe(
    project: Dict[str, Any],
    object_index: int,
    frame: int,
    prop: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Remove keyframe(s) from an object.

    Args:
        project: The scene dict
        object_index: Index of the target object
        frame: Frame number
        prop: Property name (if None, removes all keyframes at this frame)

    Returns:
        List of removed keyframes
    """
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range (0-{len(objects)-1})")

    obj = objects[object_index]
    keyframes = obj.get("keyframes", [])

    removed = []
    remaining = []
    for kf in keyframes:
        if kf["frame"] == frame and (prop is None or kf["property"] == prop):
            removed.append(kf)
        else:
            remaining.append(kf)

    if not removed:
        raise ValueError(
            f"No keyframe found at frame {frame}"
            + (f" for property '{prop}'" if prop else "")
        )

    obj["keyframes"] = remaining
    return removed


def set_frame_range(
    project: Dict[str, Any],
    frame_start: int,
    frame_end: int,
) -> Dict[str, Any]:
    """Set the animation frame range.

    Args:
        project: The scene dict
        frame_start: First frame
        frame_end: Last frame

    Returns:
        Dict with old and new range
    """
    if frame_start < 0:
        raise ValueError(f"Frame start must be non-negative: {frame_start}")
    if frame_end < frame_start:
        raise ValueError(
            f"Frame end ({frame_end}) must be >= frame start ({frame_start})"
        )

    scene = project.get("scene", {})
    old_start = scene.get("frame_start", 1)
    old_end = scene.get("frame_end", 250)

    scene["frame_start"] = frame_start
    scene["frame_end"] = frame_end

    # Clamp current frame to new range
    current = scene.get("frame_current", frame_start)
    if current < frame_start:
        scene["frame_current"] = frame_start
    elif current > frame_end:
        scene["frame_current"] = frame_end

    return {
        "old_range": f"{old_start}-{old_end}",
        "new_range": f"{frame_start}-{frame_end}",
    }


def set_fps(project: Dict[str, Any], fps: int) -> Dict[str, Any]:
    """Set the animation FPS (frames per second).

    Args:
        project: The scene dict
        fps: Target FPS

    Returns:
        Dict with old and new FPS
    """
    if fps < 1:
        raise ValueError(f"FPS must be positive: {fps}")

    scene = project.get("scene", {})
    old_fps = scene.get("fps", 24)
    scene["fps"] = fps

    return {
        "old_fps": old_fps,
        "new_fps": fps,
    }


def set_current_frame(project: Dict[str, Any], frame: int) -> Dict[str, Any]:
    """Set the current frame.

    Args:
        project: The scene dict
        frame: Frame number

    Returns:
        Dict with old and new frame
    """
    scene = project.get("scene", {})
    old_frame = scene.get("frame_current", 1)
    frame_start = scene.get("frame_start", 0)
    frame_end = scene.get("frame_end", 250)

    if frame < frame_start or frame > frame_end:
        raise ValueError(
            f"Frame {frame} is outside range [{frame_start}, {frame_end}]"
        )

    scene["frame_current"] = frame

    return {
        "old_frame": old_frame,
        "new_frame": frame,
    }


def list_keyframes(
    project: Dict[str, Any],
    object_index: int,
    prop: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List keyframes for an object.

    Args:
        project: The scene dict
        object_index: Index of the target object
        prop: Filter by property name (optional)

    Returns:
        List of keyframe dicts
    """
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range (0-{len(objects)-1})")

    obj = objects[object_index]
    keyframes = obj.get("keyframes", [])

    result = []
    for kf in keyframes:
        if prop is None or kf["property"] == prop:
            result.append({
                "frame": kf["frame"],
                "property": kf["property"],
                "value": kf["value"],
                "interpolation": kf.get("interpolation", "BEZIER"),
            })

    return result
