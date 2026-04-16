"""Inkscape CLI - Layer/group management module.

Layers in Inkscape are SVG <g> elements with inkscape:groupmode="layer".
This module manages layers in the JSON project format.
"""

from typing import Dict, Any, List, Optional

from cli_anything.inkscape.utils.svg_utils import generate_id


def add_layer(
    project: Dict[str, Any],
    name: str = "New Layer",
    visible: bool = True,
    locked: bool = False,
    opacity: float = 1.0,
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a new layer to the document.

    Args:
        position: Stack position (0 = bottom). None = top.
    """
    if opacity < 0 or opacity > 1:
        raise ValueError(f"Opacity must be 0.0-1.0: {opacity}")

    # Ensure unique name
    existing_names = {l.get("name", "") for l in project.get("layers", [])}
    final_name = name
    counter = 1
    while final_name in existing_names:
        counter += 1
        final_name = f"{name} {counter}"

    layer_id = generate_id("layer")
    layer = {
        "id": layer_id,
        "name": final_name,
        "visible": visible,
        "locked": locked,
        "opacity": opacity,
        "objects": [],
    }

    layers = project.setdefault("layers", [])
    if position is not None:
        position = max(0, min(position, len(layers)))
        layers.insert(position, layer)
    else:
        layers.append(layer)

    return layer


def remove_layer(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove a layer by index.

    Objects in the removed layer are moved to the first remaining layer,
    or orphaned if no layers remain.
    """
    layers = project.get("layers", [])
    if not layers:
        raise ValueError("No layers in document")
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range (0-{len(layers)-1})")
    if len(layers) <= 1:
        raise ValueError("Cannot remove the last layer")

    removed = layers.pop(index)

    # Move orphaned objects to the first remaining layer
    orphaned_ids = removed.get("objects", [])
    if orphaned_ids and layers:
        target = layers[0]
        target.setdefault("objects", []).extend(orphaned_ids)
        # Update object layer references
        for obj in project.get("objects", []):
            if obj.get("id") in orphaned_ids:
                obj["layer"] = target["id"]

    return removed


def move_to_layer(
    project: Dict[str, Any],
    object_index: int,
    layer_index: int,
) -> Dict[str, Any]:
    """Move an object from its current layer to another layer."""
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range (0-{len(objects)-1})")

    layers = project.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range (0-{len(layers)-1})")

    obj = objects[object_index]
    obj_id = obj.get("id", "")
    target_layer = layers[layer_index]

    # Remove from current layer
    for layer in layers:
        if obj_id in layer.get("objects", []):
            layer["objects"].remove(obj_id)

    # Add to target layer
    target_layer.setdefault("objects", []).append(obj_id)
    obj["layer"] = target_layer["id"]

    return {
        "object": obj.get("name", obj_id),
        "target_layer": target_layer.get("name", target_layer.get("id", "")),
    }


def set_layer_property(
    project: Dict[str, Any],
    index: int,
    prop: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a property on a layer."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range (0-{len(layers)-1})")

    layer = layers[index]

    valid_props = {"name", "visible", "locked", "opacity"}
    if prop not in valid_props:
        raise ValueError(f"Unknown layer property: {prop}. Valid: {', '.join(sorted(valid_props))}")

    if prop == "visible":
        if isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")
        layer["visible"] = bool(value)
    elif prop == "locked":
        if isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")
        layer["locked"] = bool(value)
    elif prop == "opacity":
        value = float(value)
        if value < 0 or value > 1:
            raise ValueError(f"Opacity must be 0.0-1.0: {value}")
        layer["opacity"] = value
    elif prop == "name":
        layer["name"] = str(value)

    return layer


def list_layers(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all layers in the document."""
    result = []
    for i, layer in enumerate(project.get("layers", [])):
        result.append({
            "index": i,
            "id": layer.get("id", ""),
            "name": layer.get("name", ""),
            "visible": layer.get("visible", True),
            "locked": layer.get("locked", False),
            "opacity": layer.get("opacity", 1.0),
            "object_count": len(layer.get("objects", [])),
        })
    return result


def reorder_layers(project: Dict[str, Any], from_index: int, to_index: int) -> Dict[str, Any]:
    """Move a layer from one position to another in the stack."""
    layers = project.get("layers", [])
    if from_index < 0 or from_index >= len(layers):
        raise IndexError(f"From index {from_index} out of range (0-{len(layers)-1})")
    if to_index < 0 or to_index >= len(layers):
        raise IndexError(f"To index {to_index} out of range (0-{len(layers)-1})")

    layer = layers.pop(from_index)
    layers.insert(to_index, layer)

    return {
        "layer": layer.get("name", layer.get("id", "")),
        "from": from_index,
        "to": to_index,
    }


def get_layer(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get detailed info about a layer."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range (0-{len(layers)-1})")

    layer = layers[index]

    # Get objects in this layer
    layer_obj_ids = set(layer.get("objects", []))
    layer_objects = []
    for i, obj in enumerate(project.get("objects", [])):
        if obj.get("id") in layer_obj_ids:
            layer_objects.append({
                "index": i,
                "id": obj.get("id", ""),
                "name": obj.get("name", ""),
                "type": obj.get("type", "unknown"),
            })

    return {
        "id": layer.get("id", ""),
        "name": layer.get("name", ""),
        "visible": layer.get("visible", True),
        "locked": layer.get("locked", False),
        "opacity": layer.get("opacity", 1.0),
        "objects": layer_objects,
    }
