"""Project-level validation: broken asset refs, GUID collisions, missing inputs."""

import json
import os
from typing import Any, Dict, List, Set, Tuple

from cli_anything.sbox.core import scene as scene_mod
from cli_anything.sbox.core import prefab as prefab_mod
from cli_anything.sbox.core import export as export_mod
from cli_anything.sbox.core import input_config as input_mod


# Asset categories to refs and the file extensions that satisfy them.
# References without extensions (e.g. "models/dev/box") fall back to the .stem
# match against assets of the corresponding type.
_CATEGORY_TO_TYPE: Dict[str, str] = {
    "models": "model",
    "materials": "material",
    "sounds": "sound",
    "textures": "texture",
    "prefabs": "prefab",
    "scenes": "scene",
}


def _build_asset_index( project_dir: str ) -> Tuple[Set[str], Set[str]]:
    """Index project assets by normalized path and by extension-less stem.

    Returns (full_paths, stems) - both sets of normalized strings.
    """
    full_paths: Set[str] = set()
    stems: Set[str] = set()
    for asset in export_mod.list_assets( project_dir, asset_type="all" ):
        rel = asset["path"].replace( "\\", "/" ).lower()
        full_paths.add( rel )
        stem, _ = os.path.splitext( rel )
        if stem:
            stems.add( stem )
    return full_paths, stems


def _is_engine_builtin( ref: str ) -> bool:
    """Whether a ref points to an engine-shipped asset (not in the project's Assets/).

    Heuristic: refs starting with these prefixes ship with s&box itself.
    """
    lower = ref.lower().lstrip( "/" )
    builtins = (
        "models/dev/",
        "materials/dev/",
        "materials/default",
        "materials/skybox/",
        "textures/dev/",
        "textures/cubemaps/",
        "fonts/",
        "particles/dev/",
        "sounds/ui/",
    )
    return any( lower.startswith( prefix ) for prefix in builtins )


def _check_refs_against_index(
    refs_by_category: Dict[str, List[str]],
    full_paths: Set[str],
    stems: Set[str],
) -> List[str]:
    """Return broken refs (those missing from the project asset index)."""
    broken: List[str] = []
    for category, paths in refs_by_category.items():
        for ref in paths:
            norm = ref.replace( "\\", "/" ).lower()
            if norm.startswith( "assets/" ):
                norm = norm[len( "assets/" ):]
            if norm in full_paths or norm in stems:
                continue
            if _is_engine_builtin( ref ):
                continue
            broken.append( ref )
    return broken


def _collect_guids( objects: List[Dict[str, Any]], collected: Dict[str, List[str]], context: str ) -> None:
    """Walk objects collecting all __guid values mapped to source contexts."""
    for obj in objects:
        guid = obj.get( "__guid" )
        if guid:
            collected.setdefault( guid, [] ).append( f"{context}:GameObject:{obj.get( 'Name', '?' )}" )
        for comp in obj.get( "Components", [] ):
            cguid = comp.get( "__guid" )
            if cguid:
                collected.setdefault( cguid, [] ).append( f"{context}:Component:{comp.get( '__type', '?' )}" )
        children = obj.get( "Children", [] )
        if children:
            _collect_guids( children, collected, context )


def validate_project(
    project_dir: str,
    check_refs: bool = True,
    check_guids: bool = True,
    check_inputs: bool = True,
) -> Dict[str, Any]:
    """Validate a project's scenes and prefabs.

    Checks performed (each can be disabled):
      * **broken_refs** - asset references in scenes/prefabs that don't resolve
        to a project file or known engine built-in.
      * **duplicate_guids** - the same __guid appearing more than once within a
        single scene or prefab (cross-file collisions are expected and not flagged).
      * **invalid_inputs** - issues in Input.config: empty action names or
        unknown groups.

    Args:
        project_dir: Root directory of the s&box project.
        check_refs: Run the broken-reference check.
        check_guids: Run the duplicate-GUID check.
        check_inputs: Run the Input.config sanity check.

    Returns:
        Dict with 'ok' (bool), 'issue_count' (int), and per-check result lists.
    """
    issues: Dict[str, Any] = {
        "broken_refs": [],
        "duplicate_guids": [],
        "invalid_inputs": [],
    }

    assets_dir = os.path.join( project_dir, "Assets" )
    if not os.path.isdir( assets_dir ):
        return {
            "ok": False,
            "issue_count": 1,
            "broken_refs": [],
            "duplicate_guids": [],
            "invalid_inputs": [],
            "error": f"No Assets/ directory found in {project_dir}",
        }

    full_paths, stems = _build_asset_index( project_dir ) if check_refs else (set(), set())

    for dirpath, _dirs, files in os.walk( assets_dir ):
        for fname in files:
            full = os.path.join( dirpath, fname )
            rel = os.path.relpath( full, project_dir ).replace( "\\", "/" )
            ext = os.path.splitext( fname )[1].lower()

            if ext not in (".scene", ".prefab"):
                continue

            try:
                if ext == ".scene":
                    refs = scene_mod.extract_asset_refs( full ) if check_refs else {}
                    if check_guids:
                        data = scene_mod.load_scene( full )
                        roots = data.get( "GameObjects", [] )
                else:
                    refs = prefab_mod.extract_asset_refs( full ) if check_refs else {}
                    if check_guids:
                        data = prefab_mod.load_prefab( full )
                        root = data.get( "RootObject" )
                        roots = [root] if root else []
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                issues["broken_refs"].append( {
                    "file": rel,
                    "ref": "<parse error>",
                    "category": "parse",
                    "detail": str( exc ),
                } )
                continue

            if check_refs:
                broken = _check_refs_against_index( refs, full_paths, stems )
                for ref in broken:
                    category = scene_mod._category_for_ref( ref )
                    issues["broken_refs"].append( {
                        "file": rel,
                        "ref": ref,
                        "category": category,
                    } )

            if check_guids and roots:
                guid_map: Dict[str, List[str]] = {}
                _collect_guids( roots, guid_map, rel )
                for guid, sources in guid_map.items():
                    if len( sources ) > 1:
                        issues["duplicate_guids"].append( {
                            "file": rel,
                            "guid": guid,
                            "occurrences": sources,
                        } )

    if check_inputs:
        input_path = os.path.join( project_dir, "ProjectSettings", "Input.config" )
        if os.path.isfile( input_path ):
            try:
                actions = input_mod.list_actions( input_path )
                seen_names: Set[str] = set()
                for action in actions:
                    name = action.get( "Name", "" ).strip()
                    if not name:
                        issues["invalid_inputs"].append( {
                            "file": "ProjectSettings/Input.config",
                            "issue": "empty_name",
                            "action": action,
                        } )
                        continue
                    if name in seen_names:
                        issues["invalid_inputs"].append( {
                            "file": "ProjectSettings/Input.config",
                            "issue": "duplicate_name",
                            "action": name,
                        } )
                    seen_names.add( name )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                issues["invalid_inputs"].append( {
                    "file": "ProjectSettings/Input.config",
                    "issue": "parse_error",
                    "detail": str( exc ),
                } )

    issue_count = sum( len( v ) for v in issues.values() if isinstance( v, list ) )
    return {
        "ok": issue_count == 0,
        "issue_count": issue_count,
        **issues,
    }
