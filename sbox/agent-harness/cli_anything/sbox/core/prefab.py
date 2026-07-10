"""Manages s&box .prefab files - creation, loading, saving, and extraction from scenes."""

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from . import scene as scene_mod


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _new_guid() -> str:
    """Generate a new UUID v4 string."""
    return str(uuid.uuid4())


def _write_json(path: str, data: Dict[str, Any]) -> None:
    """Write data as formatted JSON to path."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _build_root_object(
    name: str,
    components: Optional[List[Dict[str, Any]]] = None,
    children: Optional[List[Dict[str, Any]]] = None,
    network_mode: int = 0,
    network_transmit: bool = True,
    flags: int = 0,
) -> Dict[str, Any]:
    """Build a RootObject dict for a prefab."""
    resolved_components: List[Dict[str, Any]] = []
    if components:
        for comp in components:
            if isinstance(comp, str):
                # Treat as a preset name
                resolved_components.append(scene_mod._make_component(comp))
            elif isinstance(comp, dict):
                c = dict(comp)
                if "__guid" not in c:
                    c["__guid"] = _new_guid()
                resolved_components.append(c)

    resolved_children: List[Dict[str, Any]] = []
    if children:
        for child in children:
            if isinstance(child, dict):
                c = dict(child)
                if "__guid" not in c:
                    c["__guid"] = _new_guid()
                resolved_children.append(c)

    root: Dict[str, Any] = {
        "__guid": _new_guid(),
        "Flags": flags,
        "Name": name,
        "Enabled": True,
        "NetworkMode": network_mode,
        "NetworkInterpolation": True,
        "GizmoPersistence": 0,
        "RenderDirty": False,
        "Components": resolved_components,
        "Children": resolved_children,
    }

    if network_transmit:
        root["NetworkOrphaned"] = 1

    return root


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_prefab(
    name: str,
    output_path: Optional[str] = None,
    components: Optional[List[Dict[str, Any]]] = None,
    children: Optional[List[Dict[str, Any]]] = None,
    network_mode: int = 0,
    network_transmit: bool = True,
) -> Dict[str, Any]:
    """Create a new .prefab file with given components and children.

    *components* can be a list of component dicts (with ``__type``) or
    preset name strings (resolved via ``scene.COMPONENT_PRESETS``).

    *children* is a list of child GameObject dicts.

    Returns the full prefab data dict.
    """
    root_object = _build_root_object(
        name=name,
        components=components,
        children=children,
        network_mode=network_mode,
        network_transmit=network_transmit,
    )

    prefab: Dict[str, Any] = {
        "RootObject": root_object,
        "SceneProperties": {},
        "ResourceVersion": 1,
        "__references": [],
        "__version": 1,
    }

    if output_path:
        _write_json(output_path, prefab)

    return prefab


def load_prefab(prefab_path: str) -> Dict[str, Any]:
    """Load and return parsed prefab JSON."""
    with open(prefab_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prefab(prefab_path: str, data: Dict[str, Any]) -> None:
    """Save prefab JSON."""
    _write_json(prefab_path, data)


def get_prefab_info(prefab_path: str) -> Dict[str, Any]:
    """Return dict with prefab metadata."""
    data = load_prefab(prefab_path)
    root = data.get("RootObject", {})
    components = root.get("Components", [])
    children = root.get("Children", [])

    # Gather all component types from root and children (flat)
    all_objects = [root]
    flat_children = scene_mod._flatten_objects(children)
    all_objects.extend(flat_children)

    component_types: set = set()
    total_components = 0
    for obj in all_objects:
        for comp in obj.get("Components", []):
            ctype = comp.get("__type", "")
            if ctype:
                component_types.add(ctype)
            total_components += 1

    return {
        "name": root.get("Name", ""),
        "guid": root.get("__guid", ""),
        "path": prefab_path,
        "component_count": total_components,
        "component_types": sorted(component_types),
        "children_count": len(flat_children),
        "network_mode": root.get("NetworkMode", 0),
    }


def from_scene_object(
    scene_path: str,
    object_guid: str,
    output_path: str,
) -> Dict[str, Any]:
    """Extract a GameObject from a scene and save as .prefab file.

    The GameObject (including its Components and Children) is copied into
    the prefab RootObject structure.  GUIDs are preserved from the scene.

    Returns the prefab data dict.
    """
    scene_data = scene_mod.load_scene(scene_path)
    obj = scene_mod.find_object(scene_data, guid=object_guid)
    if obj is None:
        raise ValueError(f"GameObject with guid '{object_guid}' not found in scene")

    # Build prefab from the scene object - copy it to avoid mutating the scene
    import copy
    root_object = copy.deepcopy(obj)

    # Ensure the root has the fields expected by the prefab format
    root_object.setdefault("Flags", 0)
    root_object.setdefault("Enabled", True)

    prefab: Dict[str, Any] = {
        "RootObject": root_object,
        "SceneProperties": {},
        "ResourceVersion": 1,
        "__references": [],
        "__version": 1,
    }

    _write_json(output_path, prefab)
    return prefab


def diff_prefabs( prefab_a_path: str, prefab_b_path: str ) -> Dict[str, Any]:
    """Structural diff between two prefab files.

    Compares the RootObject summary plus the flat list of children (by Name)
    using the same logic as scene diff. Symmetric with scene.diff_scenes.

    Returns:
        Dict with 'root_changes' (or None if identical),
        'children_added' (list of names), 'children_removed' (list of names),
        'children_modified' (list of {name, changes}), and 'identical' (bool).
    """
    data_a = load_prefab( prefab_a_path )
    data_b = load_prefab( prefab_b_path )

    root_a = data_a.get( "RootObject", {} ) or {}
    root_b = data_b.get( "RootObject", {} ) or {}

    summary_root_a = scene_mod._object_summary( root_a )
    summary_root_b = scene_mod._object_summary( root_b )
    root_changes = scene_mod._diff_two_objects( "<root>", summary_root_a, summary_root_b )

    children_a = scene_mod._flatten_objects( root_a.get( "Children", [] ) )
    children_b = scene_mod._flatten_objects( root_b.get( "Children", [] ) )
    summary_a = {obj.get( "Name", f"<unnamed:{i}>" ): scene_mod._object_summary( obj ) for i, obj in enumerate( children_a )}
    summary_b = {obj.get( "Name", f"<unnamed:{i}>" ): scene_mod._object_summary( obj ) for i, obj in enumerate( children_b )}

    names_a = set( summary_a.keys() )
    names_b = set( summary_b.keys() )
    added = sorted( names_b - names_a )
    removed = sorted( names_a - names_b )
    modified: List[Dict[str, Any]] = []
    for name in sorted( names_a & names_b ):
        d = scene_mod._diff_two_objects( name, summary_a[name], summary_b[name] )
        if d:
            modified.append( d )

    identical = (root_changes is None) and not (added or removed or modified)
    return {
        "prefab_a": prefab_a_path,
        "prefab_b": prefab_b_path,
        "root_changes": root_changes,
        "children_added": added,
        "children_removed": removed,
        "children_modified": modified,
        "identical": identical,
    }


def extract_asset_refs( prefab_path: str ) -> Dict[str, List[str]]:
    """Extract every asset reference from a prefab file.

    Same categorization as scene.extract_asset_refs.
    """
    data = load_prefab( prefab_path )
    refs: Dict[str, List[str]] = {}
    if "RootObject" in data:
        scene_mod._walk_for_refs( data["RootObject"], refs, ["RootObject"] )
    return {cat: sorted( set( paths ) ) for cat, paths in refs.items()}


def modify_component(
    prefab_path: str,
    component_guid: Optional[str] = None,
    component_type: Optional[str] = None,
    object_guid: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Modify properties on a component within a prefab.

    Searches the RootObject and all children for a matching component. If
    *object_guid* is provided, the search is restricted to that GameObject;
    otherwise the first matching component anywhere in the tree wins.

    Returns dict with object_guid, component_guid, component_type, updated_keys.
    """
    if component_guid is None and component_type is None:
        raise ValueError( "Must provide either component_guid or component_type" )
    if not properties:
        raise ValueError( "No properties specified to modify" )

    data = load_prefab( prefab_path )
    root = data.get( "RootObject" )
    if root is None:
        raise ValueError( "Prefab has no RootObject" )

    all_objects: List[Dict[str, Any]] = [root]
    children = root.get( "Children", [] )
    if children:
        all_objects.extend( scene_mod._flatten_objects( children ) )

    # Optionally restrict to a single object
    if object_guid:
        all_objects = [o for o in all_objects if o.get( "__guid" ) == object_guid]
        if not all_objects:
            raise ValueError( f"Object '{object_guid}' not found in prefab" )

    target_obj = None
    target_comp = None
    for obj in all_objects:
        for comp in obj.get( "Components", [] ):
            if component_guid and comp.get( "__guid" ) == component_guid:
                target_obj, target_comp = obj, comp
                break
            if component_type and comp.get( "__type" ) == component_type:
                target_obj, target_comp = obj, comp
                break
        if target_comp is not None:
            break

    if target_comp is None:
        identifier = component_guid or component_type
        raise ValueError( f"Component '{identifier}' not found in prefab" )

    updated_keys = []
    for key, value in properties.items():
        target_comp[key] = value
        updated_keys.append( key )

    save_prefab( prefab_path, data )

    return {
        "object_guid": target_obj.get( "__guid", "" ),
        "component_guid": target_comp.get( "__guid", "" ),
        "component_type": target_comp.get( "__type", "" ),
        "updated_keys": updated_keys,
    }
