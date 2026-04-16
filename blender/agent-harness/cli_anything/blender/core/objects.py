"""Blender CLI - 3D object management module."""

import copy
from typing import Dict, Any, List, Optional


# Valid mesh primitive types and their default parameters
MESH_PRIMITIVES = {
    "cube": {"size": 2.0},
    "sphere": {"radius": 1.0, "segments": 32, "rings": 16},
    "cylinder": {"radius": 1.0, "depth": 2.0, "vertices": 32},
    "cone": {"radius1": 1.0, "radius2": 0.0, "depth": 2.0, "vertices": 32},
    "plane": {"size": 2.0},
    "torus": {"major_radius": 1.0, "minor_radius": 0.25, "major_segments": 48, "minor_segments": 12},
    "monkey": {},
    "empty": {},
}

OBJECT_TYPES = ["MESH", "EMPTY", "ARMATURE", "CURVE", "LATTICE"]


def _next_id(project: Dict[str, Any], collection_key: str = "objects") -> int:
    """Generate the next unique ID for a collection."""
    items = project.get(collection_key, [])
    existing_ids = [item.get("id", 0) for item in items]
    return max(existing_ids, default=-1) + 1


def _unique_name(project: Dict[str, Any], base_name: str, collection_key: str = "objects") -> str:
    """Generate a unique name within a collection."""
    items = project.get(collection_key, [])
    existing_names = {item.get("name", "") for item in items}
    if base_name not in existing_names:
        return base_name
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


def add_object(
    project: Dict[str, Any],
    mesh_type: str = "cube",
    name: Optional[str] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
    mesh_params: Optional[Dict[str, Any]] = None,
    collection: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a 3D primitive object to the scene.

    Args:
        project: The scene dict
        mesh_type: Primitive type (cube, sphere, cylinder, cone, plane, torus, monkey, empty)
        name: Object name (auto-generated if None)
        location: [x, y, z] location (default [0, 0, 0])
        rotation: [x, y, z] rotation in degrees (default [0, 0, 0])
        scale: [x, y, z] scale (default [1, 1, 1])
        mesh_params: Override mesh creation parameters
        collection: Target collection name (default: first collection)

    Returns:
        The new object dict
    """
    if mesh_type not in MESH_PRIMITIVES:
        raise ValueError(
            f"Unknown mesh type: {mesh_type}. Valid types: {list(MESH_PRIMITIVES.keys())}"
        )

    if location is not None and len(location) != 3:
        raise ValueError(f"Location must have 3 components [x, y, z], got {len(location)}")
    if rotation is not None and len(rotation) != 3:
        raise ValueError(f"Rotation must have 3 components [x, y, z], got {len(rotation)}")
    if scale is not None and len(scale) != 3:
        raise ValueError(f"Scale must have 3 components [x, y, z], got {len(scale)}")

    # Merge default params with overrides
    default_params = dict(MESH_PRIMITIVES[mesh_type])
    if mesh_params:
        for k, v in mesh_params.items():
            if k not in default_params and mesh_type != "empty":
                valid_keys = list(MESH_PRIMITIVES[mesh_type].keys())
                raise ValueError(
                    f"Unknown mesh param '{k}' for {mesh_type}. Valid: {valid_keys}"
                )
            default_params[k] = v

    base_name = name or mesh_type.capitalize()
    obj_name = _unique_name(project, base_name, "objects")
    obj_type = "EMPTY" if mesh_type == "empty" else "MESH"

    obj = {
        "id": _next_id(project, "objects"),
        "name": obj_name,
        "type": obj_type,
        "mesh_type": mesh_type,
        "location": list(location) if location else [0.0, 0.0, 0.0],
        "rotation": list(rotation) if rotation else [0.0, 0.0, 0.0],
        "scale": list(scale) if scale else [1.0, 1.0, 1.0],
        "visible": True,
        "material": None,
        "modifiers": [],
        "keyframes": [],
        "parent": None,
        "mesh_params": default_params,
    }

    if "objects" not in project:
        project["objects"] = []
    project["objects"].append(obj)

    # Add to collection
    if collection:
        collections = project.get("collections", [])
        target = None
        for c in collections:
            if c["name"] == collection:
                target = c
                break
        if target is None:
            raise ValueError(f"Collection not found: {collection}")
        target["objects"].append(obj["id"])
    else:
        # Add to first collection if it exists
        collections = project.get("collections", [])
        if collections:
            collections[0]["objects"].append(obj["id"])

    return obj


def remove_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove an object by index."""
    objects = project.get("objects", [])
    if not objects:
        raise ValueError("No objects to remove")
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    removed = objects.pop(index)

    # Remove from collections
    obj_id = removed.get("id")
    for c in project.get("collections", []):
        if obj_id in c.get("objects", []):
            c["objects"].remove(obj_id)

    # Remove material references that point to this object
    # (materials stand alone, we just clear the object's reference)

    return removed


def duplicate_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Duplicate an object."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    original = objects[index]
    dup = copy.deepcopy(original)
    dup["id"] = _next_id(project, "objects")
    dup["name"] = _unique_name(project, f"{original['name']}.copy", "objects")
    objects.append(dup)

    # Add to same collections as original
    orig_id = original.get("id")
    for c in project.get("collections", []):
        if orig_id in c.get("objects", []):
            c["objects"].append(dup["id"])

    return dup


def transform_object(
    project: Dict[str, Any],
    index: int,
    translate: Optional[List[float]] = None,
    rotate: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Apply a transform to an object.

    Args:
        project: The scene dict
        index: Object index
        translate: [dx, dy, dz] to add to current location
        rotate: [rx, ry, rz] in degrees to add to current rotation
        scale: [sx, sy, sz] to multiply with current scale
    """
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    obj = objects[index]

    if translate:
        if len(translate) != 3:
            raise ValueError(f"Translate must have 3 components, got {len(translate)}")
        obj["location"] = [
            obj["location"][i] + translate[i] for i in range(3)
        ]
    if rotate:
        if len(rotate) != 3:
            raise ValueError(f"Rotate must have 3 components, got {len(rotate)}")
        obj["rotation"] = [
            obj["rotation"][i] + rotate[i] for i in range(3)
        ]
    if scale:
        if len(scale) != 3:
            raise ValueError(f"Scale must have 3 components, got {len(scale)}")
        obj["scale"] = [
            obj["scale"][i] * scale[i] for i in range(3)
        ]

    return obj


def set_object_property(
    project: Dict[str, Any], index: int, prop: str, value: Any
) -> None:
    """Set an object property."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    obj = objects[index]

    if prop == "name":
        obj["name"] = str(value)
    elif prop == "visible":
        obj["visible"] = str(value).lower() in ("true", "1", "yes")
    elif prop == "location":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Location must have 3 components")
        obj["location"] = [float(x) for x in value]
    elif prop == "rotation":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Rotation must have 3 components")
        obj["rotation"] = [float(x) for x in value]
    elif prop == "scale":
        if isinstance(value, str):
            value = [float(x) for x in value.split(",")]
        if len(value) != 3:
            raise ValueError("Scale must have 3 components")
        obj["scale"] = [float(x) for x in value]
    elif prop == "parent":
        # Set parent by object index or None
        if value is None or str(value).lower() == "none":
            obj["parent"] = None
        else:
            parent_idx = int(value)
            if parent_idx < 0 or parent_idx >= len(objects):
                raise IndexError(f"Parent index {parent_idx} out of range")
            if parent_idx == index:
                raise ValueError("Object cannot be its own parent")
            obj["parent"] = objects[parent_idx]["id"]
    else:
        raise ValueError(
            f"Unknown property: {prop}. Valid: name, visible, location, rotation, scale, parent"
        )


def get_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get an object by index."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")
    return objects[index]


def list_objects(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all objects with summary info."""
    result = []
    for i, obj in enumerate(project.get("objects", [])):
        result.append({
            "index": i,
            "id": obj.get("id", i),
            "name": obj.get("name", f"Object {i}"),
            "type": obj.get("type", "MESH"),
            "mesh_type": obj.get("mesh_type", "unknown"),
            "location": obj.get("location", [0, 0, 0]),
            "rotation": obj.get("rotation", [0, 0, 0]),
            "scale": obj.get("scale", [1, 1, 1]),
            "visible": obj.get("visible", True),
            "material": obj.get("material"),
            "modifier_count": len(obj.get("modifiers", [])),
            "keyframe_count": len(obj.get("keyframes", [])),
        })
    return result
