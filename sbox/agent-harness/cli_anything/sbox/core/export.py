"""Asset listing and project export utilities for s&box projects."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Asset extension mapping
# ---------------------------------------------------------------------------

ASSET_EXTENSIONS: Dict[str, List[str]] = {
    "scene": [".scene"],
    "prefab": [".prefab"],
    "material": [".vmat"],
    "model": [".vmdl"],
    "sound": [".sound"],
    "texture": [".vtex", ".png", ".jpg", ".tga"],
    "shader": [".shader", ".shader_c"],
    "razor": [".razor"],
    "code": [".cs"],
}

# Build a reverse lookup: extension -> asset type
_EXT_TO_TYPE: Dict[str, str] = {}
for _type_name, _exts in ASSET_EXTENSIONS.items():
    for _ext in _exts:
        _EXT_TO_TYPE[_ext] = _type_name


def _classify_asset( file_path: str ) -> str:
    """Classify an asset file by its extension.

    Returns the asset type string (e.g. 'scene', 'model') or 'other'.
    """
    _, ext = os.path.splitext( file_path )
    return _EXT_TO_TYPE.get( ext.lower(), "other" )


def _get_extensions_for_type( asset_type: str ) -> Optional[List[str]]:
    """Return the list of extensions for a given asset type, or None if 'all'."""
    if asset_type == "all":
        return None
    return ASSET_EXTENSIONS.get( asset_type )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_assets(
    project_dir: str,
    asset_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all assets in a project's Assets/ directory.

    Args:
        project_dir: Root directory of the s&box project.
        asset_type: Filter by type - 'scene', 'prefab', 'material', 'model',
                    'sound', 'texture', 'shader', 'razor', 'code', or 'all'.
                    If None or 'all', returns every recognised asset.

    Returns:
        List of dicts, each with keys: path, type, name, size_bytes.
        Paths are relative to the project's Assets/ directory.
    """
    assets_dir = os.path.join( project_dir, "Assets" )
    if not os.path.isdir( assets_dir ):
        return []

    filter_type = asset_type or "all"
    allowed_extensions = _get_extensions_for_type( filter_type )

    results: List[Dict[str, Any]] = []

    for dirpath, _dirnames, filenames in os.walk( assets_dir ):
        for filename in filenames:
            full_path = os.path.join( dirpath, filename )
            _, ext = os.path.splitext( filename )
            ext_lower = ext.lower()

            # If filtering by type, skip files that don't match
            if allowed_extensions is not None and ext_lower not in allowed_extensions:
                continue

            # If showing all, skip files that aren't a recognised asset type
            classified = _EXT_TO_TYPE.get( ext_lower )
            if allowed_extensions is None and classified is None:
                continue

            rel_path = os.path.relpath( full_path, assets_dir )

            try:
                size = os.path.getsize( full_path )
            except OSError:
                size = 0

            results.append( {
                "path": rel_path,
                "type": classified or "other",
                "name": filename,
                "size_bytes": size,
            } )

    # Sort by relative path for stable ordering
    results.sort( key=lambda entry: entry["path"] )
    return results


def get_asset_info( asset_path: str ) -> Dict[str, Any]:
    """Get detailed info about a specific asset file.

    For JSON-based assets (.scene, .prefab, .sound), parses the file and
    returns structure information (top-level keys, counts, etc.).

    Args:
        asset_path: Absolute or relative path to the asset file.

    Returns:
        Dict with asset metadata:
        - name: filename
        - path: absolute path
        - type: classified asset type
        - size_bytes: file size
        - exists: whether the file exists
        - json_info: (optional) structure info for JSON-based assets
    """
    abs_path = os.path.abspath( asset_path )
    filename = os.path.basename( abs_path )
    classified = _classify_asset( abs_path )

    info: Dict[str, Any] = {
        "name": filename,
        "path": abs_path,
        "type": classified,
        "exists": os.path.isfile( abs_path ),
    }

    if not info["exists"]:
        info["size_bytes"] = 0
        return info

    try:
        info["size_bytes"] = os.path.getsize( abs_path )
    except OSError:
        info["size_bytes"] = 0

    # Attempt to parse JSON-based assets for structure info
    _, ext = os.path.splitext( filename )
    json_extensions = {".scene", ".prefab", ".sound"}
    if ext.lower() in json_extensions:
        info["json_info"] = _parse_json_asset( abs_path )

    return info


def _parse_json_asset( file_path: str ) -> Dict[str, Any]:
    """Parse a JSON asset file and return structure information.

    Returns a dict with:
    - top_level_keys: list of keys in the root object
    - For .scene files: game_object_count, scene_properties
    - For .prefab files: game_object_count
    """
    try:
        with open( file_path, "r", encoding="utf-8" ) as f:
            data = json.load( f )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"error": f"Failed to parse JSON: {exc}"}

    if not isinstance( data, dict ):
        return {"top_level_keys": [], "note": "Root element is not an object"}

    result: Dict[str, Any] = {
        "top_level_keys": list( data.keys() ),
    }

    # Scene-specific info
    game_objects = data.get( "GameObjects" )
    if isinstance( game_objects, list ):
        result["game_object_count"] = len( game_objects )
        result["game_object_names"] = [
            obj.get( "Name", "<unnamed>" )
            for obj in game_objects
            if isinstance( obj, dict )
        ]

    scene_props = data.get( "SceneProperties" )
    if isinstance( scene_props, dict ):
        result["scene_properties"] = scene_props

    # Version info if present
    if "__version" in data:
        result["version"] = data["__version"]

    return result


def _normalize_ref( ref: str ) -> str:
    """Normalize a ref for comparison: lowercase, forward slashes, strip 'assets/' prefix."""
    if not ref:
        return ""
    n = ref.replace( "\\", "/" ).strip().lower()
    if n.startswith( "assets/" ):
        n = n[len( "assets/" ):]
    return n


def _scan_project_refs( project_dir: str ) -> Dict[str, List[Dict[str, str]]]:
    """Walk every scene/prefab in a project and return a map: ref -> [sources].

    Each source is a dict with 'file' (relative path) and 'category' (model/material/...).
    Returns the inverted index: normalized_ref -> list of {file, category, original_ref}.
    """
    from cli_anything.sbox.core import scene as scene_mod
    from cli_anything.sbox.core import prefab as prefab_mod

    assets_dir = os.path.join( project_dir, "Assets" )
    if not os.path.isdir( assets_dir ):
        return {}

    inverted: Dict[str, List[Dict[str, str]]] = {}

    for dirpath, _dirs, files in os.walk( assets_dir ):
        for fname in files:
            full = os.path.join( dirpath, fname )
            rel = os.path.relpath( full, project_dir ).replace( "\\", "/" )
            ext = os.path.splitext( fname )[1].lower()

            try:
                if ext == ".scene":
                    refs = scene_mod.extract_asset_refs( full )
                elif ext == ".prefab":
                    refs = prefab_mod.extract_asset_refs( full )
                else:
                    continue
            except (OSError, json.JSONDecodeError, ValueError):
                continue

            for category, paths in refs.items():
                for ref in paths:
                    norm = _normalize_ref( ref )
                    inverted.setdefault( norm, [] ).append( {
                        "file": rel,
                        "category": category,
                        "original_ref": ref,
                    } )

    return inverted


def find_asset_refs( project_dir: str, asset_path: str ) -> List[Dict[str, str]]:
    """Find every scene/prefab in a project that references *asset_path*.

    Args:
        project_dir: Root directory of the s&box project.
        asset_path: The asset path to look for (e.g. "models/dev/box.vmdl").
                    Matching is case-insensitive, slash-normalized, and the
                    "Assets/" prefix is optional.

    Returns:
        List of dicts with 'file' (referrer path), 'category' (asset category),
        and 'original_ref' (the exact string found in the file).  Empty list if
        no references are found.
    """
    inverted = _scan_project_refs( project_dir )
    target = _normalize_ref( asset_path )
    return inverted.get( target, [] )


def find_unused_assets(
    project_dir: str,
    asset_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Find assets in the project that aren't referenced by any scene/prefab.

    Note: only asset types whose references appear in scene/prefab JSON are
    detectable here (models, materials, sounds, textures, prefabs). Code,
    razor templates, and shaders are not analysed - they're excluded by
    default unless explicitly requested via *asset_types*.

    Args:
        project_dir: Root directory of the s&box project.
        asset_types: Optional list of asset types to consider (model, material,
                     sound, texture, prefab). Defaults to all referenceable types.

    Returns:
        List of dicts with 'path' (relative to Assets/), 'type', and 'size_bytes'.
    """
    referenceable = {"model", "material", "sound", "texture", "prefab"}
    if asset_types is None:
        wanted = referenceable
    else:
        wanted = set( asset_types ) & referenceable

    inverted = _scan_project_refs( project_dir )
    referenced_norms = set( inverted.keys() )

    all_assets = list_assets( project_dir, asset_type="all" )
    unused: List[Dict[str, Any]] = []

    for asset in all_assets:
        if asset["type"] not in wanted:
            continue
        rel = asset["path"].replace( "\\", "/" )
        # Compare: both with and without the extension (some refs omit .vmdl)
        candidates = {_normalize_ref( rel )}
        stem, _ = os.path.splitext( rel )
        if stem:
            candidates.add( _normalize_ref( stem ) )
        if not (candidates & referenced_norms):
            unused.append( asset )

    return unused


def _rewrite_string_refs(
    node: Any,
    old_norm: str,
    old_stem_norm: str,
    new_path: str,
    new_stem: str,
    counter: List[int],
) -> None:
    """Recursively rewrite asset reference strings in a JSON tree.

    Mutates *node* in place. Matches both full-path refs (with extension) and
    stem-only refs (no extension). *counter* is a single-element mutable list
    used to track replacement count from inside the recursion.
    """
    if isinstance( node, dict ):
        for key, value in list( node.items() ):
            if isinstance( value, str ) and value:
                norm = _normalize_ref( value )
                if norm == old_norm:
                    node[key] = new_path
                    counter[0] += 1
                elif norm == old_stem_norm and old_stem_norm:
                    node[key] = new_stem
                    counter[0] += 1
            else:
                _rewrite_string_refs( value, old_norm, old_stem_norm, new_path, new_stem, counter )
    elif isinstance( node, list ):
        for item in node:
            _rewrite_string_refs( item, old_norm, old_stem_norm, new_path, new_stem, counter )


def _rewrite_refs_in_project(
    project_dir: str,
    old_path: str,
    new_path: str,
) -> List[Dict[str, Any]]:
    """Rewrite every reference to *old_path* with *new_path* across all scenes/prefabs.

    Both arguments should be relative-to-Assets paths (e.g. "models/team/foo.vmdl").
    Returns a list of dicts {file, replacements} for each file actually modified.
    """
    from cli_anything.sbox.core import scene as scene_mod
    from cli_anything.sbox.core import prefab as prefab_mod

    assets_dir = os.path.join( project_dir, "Assets" )
    old_norm = _normalize_ref( old_path )
    old_stem_norm, _ = os.path.splitext( old_norm )
    # Preserve the new path's case but use forward slashes
    new_path_normslash = new_path.replace( "\\", "/" )
    new_stem, _ = os.path.splitext( new_path_normslash )

    modified: List[Dict[str, Any]] = []

    for dirpath, _dirs, files in os.walk( assets_dir ):
        for fname in files:
            full = os.path.join( dirpath, fname )
            rel = os.path.relpath( full, project_dir ).replace( "\\", "/" )
            ext = os.path.splitext( fname )[1].lower()
            if ext not in (".scene", ".prefab"):
                continue
            try:
                if ext == ".scene":
                    data = scene_mod.load_scene( full )
                else:
                    data = prefab_mod.load_prefab( full )
            except (OSError, json.JSONDecodeError, ValueError):
                continue

            counter = [0]
            _rewrite_string_refs( data, old_norm, old_stem_norm, new_path_normslash, new_stem, counter )
            if counter[0] > 0:
                if ext == ".scene":
                    scene_mod.save_scene( full, data )
                else:
                    prefab_mod.save_prefab( full, data )
                modified.append( {"file": rel, "replacements": counter[0]} )

    return modified


def rename_asset(
    project_dir: str,
    old_path: str,
    new_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Rename an asset file and update every scene/prefab reference.

    Args:
        project_dir: Project root directory.
        old_path: Current asset path (relative to Assets/, e.g. "models/team/foo.vmdl").
        new_name: New filename (no path), keeping the same parent directory.
                  Extension may be omitted - the existing extension is preserved.
        dry_run: If True, don't touch any files - just report what would change.

    Returns:
        Dict with old_path, new_path, file_renamed, references_updated (list).
    """
    assets_dir = os.path.join( project_dir, "Assets" )
    old_full = os.path.join( assets_dir, old_path.replace( "/", os.sep ) )
    if not os.path.isfile( old_full ):
        raise FileNotFoundError( f"Asset not found: {old_path}" )

    parent_rel = os.path.dirname( old_path.replace( "\\", "/" ) )
    old_ext = os.path.splitext( old_path )[1]
    # Preserve extension if caller omitted it
    if not os.path.splitext( new_name )[1]:
        new_filename = new_name + old_ext
    else:
        new_filename = new_name

    new_path = (parent_rel + "/" + new_filename).lstrip( "/" )
    new_full = os.path.join( assets_dir, new_path.replace( "/", os.sep ) )

    if os.path.exists( new_full ) and os.path.abspath( new_full ) != os.path.abspath( old_full ):
        raise FileExistsError( f"Target already exists: {new_path}" )

    if dry_run:
        # Count refs without writing
        refs = find_asset_refs( project_dir, old_path )
        return {
            "old_path": old_path,
            "new_path": new_path,
            "file_renamed": False,
            "references_updated": [],
            "references_would_update": len( refs ),
            "dry_run": True,
        }

    updated = _rewrite_refs_in_project( project_dir, old_path, new_path )
    os.rename( old_full, new_full )

    return {
        "old_path": old_path,
        "new_path": new_path,
        "file_renamed": True,
        "references_updated": updated,
        "dry_run": False,
    }


def move_asset(
    project_dir: str,
    old_path: str,
    new_path: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Move an asset to a new path (potentially different directory) and update refs.

    Args:
        project_dir: Project root directory.
        old_path: Current asset path relative to Assets/.
        new_path: Target path relative to Assets/. May change directory and/or filename.
                  Extension is preserved if the caller's new_path lacks one.
        dry_run: If True, don't touch any files - just report what would change.

    Returns:
        Dict with old_path, new_path, file_moved, references_updated (list).
    """
    assets_dir = os.path.join( project_dir, "Assets" )
    old_full = os.path.join( assets_dir, old_path.replace( "/", os.sep ) )
    if not os.path.isfile( old_full ):
        raise FileNotFoundError( f"Asset not found: {old_path}" )

    old_ext = os.path.splitext( old_path )[1]
    new_path_norm = new_path.replace( "\\", "/" )
    if not os.path.splitext( new_path_norm )[1]:
        new_path_norm = new_path_norm + old_ext

    new_full = os.path.join( assets_dir, new_path_norm.replace( "/", os.sep ) )

    if os.path.exists( new_full ) and os.path.abspath( new_full ) != os.path.abspath( old_full ):
        raise FileExistsError( f"Target already exists: {new_path_norm}" )

    if dry_run:
        refs = find_asset_refs( project_dir, old_path )
        return {
            "old_path": old_path,
            "new_path": new_path_norm,
            "file_moved": False,
            "references_updated": [],
            "references_would_update": len( refs ),
            "dry_run": True,
        }

    updated = _rewrite_refs_in_project( project_dir, old_path, new_path_norm )
    os.makedirs( os.path.dirname( new_full ) or assets_dir, exist_ok=True )
    os.rename( old_full, new_full )

    return {
        "old_path": old_path,
        "new_path": new_path_norm,
        "file_moved": True,
        "references_updated": updated,
        "dry_run": False,
    }


def find_project_dir( start_path: str ) -> Optional[str]:
    """Walk up from start_path to find the directory containing a .sbproj file.

    Starts from start_path (or its parent if start_path is a file) and
    checks each ancestor directory for a .sbproj file.

    Args:
        start_path: File or directory path to start searching from.

    Returns:
        The project directory path (containing the .sbproj), or None if
        no .sbproj file is found before reaching the filesystem root.
    """
    current = os.path.abspath( start_path )

    # If start_path is a file, begin from its parent directory
    if os.path.isfile( current ):
        current = os.path.dirname( current )

    while True:
        # Check for any .sbproj file in this directory
        try:
            entries = os.listdir( current )
        except OSError:
            return None

        for entry in entries:
            if entry.endswith( ".sbproj" ):
                return current

        # Move to parent
        parent = os.path.dirname( current )
        if parent == current:
            # Reached filesystem root
            return None
        current = parent
