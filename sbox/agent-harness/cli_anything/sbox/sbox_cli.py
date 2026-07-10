"""cli-anything-sbox - Click-based CLI harness for the s&box game engine.

Provides commands for managing s&box projects, scenes, prefabs, code generation,
input/collision configuration, and more. Supports both single-command invocation
and an interactive REPL mode.
"""

import click
import json
import os
import shlex
import sys
from typing import Any, Optional

from cli_anything.sbox.core import (
    project as project_mod,
    scene as scene_mod,
    prefab as prefab_mod,
    codegen as codegen_mod,
    input_config as input_config_mod,
    collision_config as collision_config_mod,
    session as session_mod,
    export as export_mod,
)
from cli_anything.sbox.core import material as material_mod
from cli_anything.sbox.core import sound as sound_mod
from cli_anything.sbox.core import localization as localization_mod
from cli_anything.sbox.core import validate as validate_mod
from cli_anything.sbox.utils import sbox_backend
from cli_anything.sbox.core import test_orchestrator as test_mod


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _output(ctx: click.Context, data: Any, human_fn=None) -> None:
    """Output data as JSON or human-readable text.

    Args:
        ctx: Click context with obj["json"] flag.
        data: Data to output (must be JSON-serializable for --json mode).
        human_fn: Optional callable that returns a human-readable string.
                  If None, falls back to a pretty-printed representation.
    """
    if ctx.obj.get( "json" ):
        click.echo( json.dumps( data, indent=2, default=str ) )
    elif human_fn:
        click.echo( human_fn( data ) )
    else:
        click.echo( json.dumps( data, indent=2, default=str ) )


def _output_error(ctx: click.Context, message: str) -> None:
    """Output an error message and signal failure to scripts and agents.

    In one-shot mode, exits the process with code 1 after printing so callers
    observe a non-zero exit on failure. In REPL mode (``ctx.obj["repl"]`` is
    truthy), prints and returns so the REPL loop continues. Centralising the
    exit-on-error here keeps per-command try/except blocks simple while still
    propagating failures correctly.
    """
    if ctx.obj.get( "json" ):
        click.echo( json.dumps( {"error": message} ) )
    else:
        click.echo( f"Error: {message}", err=True )
    if not ctx.obj.get( "repl" ):
        sys.exit( 1 )


def _format_table(rows: list, headers: list) -> str:
    """Format a list of dicts/tuples as a simple aligned table."""
    if not rows:
        return "(empty)"

    # Calculate column widths
    col_widths = [len( h ) for h in headers]
    str_rows = []
    for row in rows:
        if isinstance( row, dict ):
            cells = [str( row.get( h, "" ) ) for h in headers]
        else:
            cells = [str( c ) for c in row]
        str_rows.append( cells )
        for i, cell in enumerate( cells ):
            if i < len( col_widths ):
                col_widths[i] = max( col_widths[i], len( cell ) )

    lines = []
    # Header
    header_line = "  ".join( h.ljust( col_widths[i] ) for i, h in enumerate( headers ) )
    lines.append( header_line )
    lines.append( "  ".join( "-" * w for w in col_widths ) )
    # Rows
    for cells in str_rows:
        line = "  ".join( cells[i].ljust( col_widths[i] ) if i < len( col_widths ) else cells[i] for i in range( len( cells ) ) )
        lines.append( line )

    return "\n".join( lines )


def _format_status_block(data: dict, title: str = "") -> str:
    """Format a dict as a key-value status block."""
    lines = []
    if title:
        lines.append( title )
        lines.append( "=" * len( title ) )
    max_key = max( (len( str( k ) ) for k in data), default=0 )
    for key, value in data.items():
        lines.append( f"  {str( key ).ljust( max_key )}  {value}" )
    return "\n".join( lines )


def _resolve_project_path(ctx: click.Context) -> Optional[str]:
    """Resolve the project directory from --project or cwd.

    Returns the .sbproj file path, or None if not found.
    """
    project_path = ctx.obj.get( "project_path" )
    if project_path:
        # If it is a directory, find the .sbproj inside
        if os.path.isdir( project_path ):
            return project_mod.find_sbproj( project_path )
        # If it is a file, assume it is the .sbproj
        if os.path.isfile( project_path ):
            return project_path
        return None
    # Auto-detect from cwd
    proj_dir = export_mod.find_project_dir( os.getcwd() )
    if proj_dir:
        return project_mod.find_sbproj( proj_dir )
    return None


def _resolve_project_dir(ctx: click.Context) -> Optional[str]:
    """Resolve the project directory from --project or cwd."""
    project_path = ctx.obj.get( "project_path" )
    if project_path:
        if os.path.isdir( project_path ):
            return project_path
        if os.path.isfile( project_path ):
            return os.path.dirname( project_path )
        return None
    return export_mod.find_project_dir( os.getcwd() )


def _resolve_input_config(ctx: click.Context, config_path: Optional[str] = None) -> str:
    """Resolve the Input.config path from explicit arg, --project, or cwd."""
    if config_path:
        return config_path
    proj_dir = _resolve_project_dir( ctx )
    if proj_dir:
        return os.path.join( proj_dir, "ProjectSettings", "Input.config" )
    raise click.ClickException( "No project found. Use --project or run from a project directory." )


def _resolve_collision_config(ctx: click.Context, config_path: Optional[str] = None) -> str:
    """Resolve the Collision.config path from explicit arg, --project, or cwd."""
    if config_path:
        return config_path
    proj_dir = _resolve_project_dir( ctx )
    if proj_dir:
        return os.path.join( proj_dir, "ProjectSettings", "Collision.config" )
    raise click.ClickException( "No project found. Use --project or run from a project directory." )


# ---------------------------------------------------------------------------
# Root CLI group
# ---------------------------------------------------------------------------


@click.group( invoke_without_command=True )
@click.option( "--json", "json_output", is_flag=True, help="Output in JSON format" )
@click.option( "--project", "project_path", default=None, help="Project directory path" )
@click.pass_context
def cli( ctx, json_output, project_path ):
    """cli-anything-sbox - CLI harness for the s&box game engine."""
    ctx.ensure_object( dict )
    ctx.obj["json"] = json_output
    ctx.obj["project_path"] = project_path
    if ctx.invoked_subcommand is None:
        ctx.invoke( repl )


# ---------------------------------------------------------------------------
# project group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def project( ctx ):
    """Manage s&box projects."""
    pass


@project.command( "new" )
@click.option( "--name", required=True, help="Project name" )
@click.option( "--type", "project_type", type=click.Choice( ["game", "addon", "library"] ), default="game", help="Project type" )
@click.option( "-o", "--output-dir", default=None, help="Output directory" )
@click.option( "--max-players", type=int, default=64, help="Maximum player count" )
@click.option( "--tick-rate", type=int, default=50, help="Server tick rate" )
@click.pass_context
def project_new( ctx, name, project_type, output_dir, max_players, tick_rate ):
    """Create a new s&box project."""
    try:
        result = project_mod.create_project(
            name=name,
            project_type=project_type,
            output_dir=output_dir,
            max_players=max_players,
            tick_rate=tick_rate,
        )
        _output( ctx, result, lambda d: _format_status_block( d, f"Project '{d['name']}' created" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@project.command( "info" )
@click.pass_context
def project_info( ctx ):
    """Show project info."""
    try:
        sbproj = _resolve_project_path( ctx )
        if not sbproj:
            raise click.ClickException( "No .sbproj found. Use --project or run from a project directory." )
        result = project_mod.get_project_info( sbproj )
        _output( ctx, result, lambda d: _format_status_block( d, f"Project: {d.get( 'title', '' )}" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@project.command( "config" )
@click.option( "--title", default=None, help="Project title" )
@click.option( "--max-players", type=int, default=None, help="Maximum player count" )
@click.option( "--tick-rate", type=int, default=None, help="Server tick rate" )
@click.option( "--network-type", default=None, help="Network type (e.g. Multiplayer)" )
@click.option( "--startup-scene", default=None, help="Startup scene path" )
@click.pass_context
def project_config( ctx, title, max_players, tick_rate, network_type, startup_scene ):
    """Update project settings."""
    try:
        sbproj = _resolve_project_path( ctx )
        if not sbproj:
            raise click.ClickException( "No .sbproj found. Use --project or run from a project directory." )

        kwargs = {}
        if title is not None:
            kwargs["title"] = title
        if max_players is not None:
            kwargs["max_players"] = max_players
        if tick_rate is not None:
            kwargs["tick_rate"] = tick_rate
        if network_type is not None:
            kwargs["network_type"] = network_type
        if startup_scene is not None:
            kwargs["startup_scene"] = startup_scene

        if not kwargs:
            _output_error( ctx, "No settings specified. Use --title, --max-players, etc." )
            return

        result = project_mod.configure_project( sbproj, **kwargs )
        _output( ctx, result, lambda d: _format_status_block( d, "Project updated" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@project.command( "add-package" )
@click.argument( "package_ref" )
@click.pass_context
def project_add_package( ctx, package_ref ):
    """Add a package reference to the project."""
    try:
        sbproj = _resolve_project_path( ctx )
        if not sbproj:
            _output_error( ctx, "No project found" )
            return
        result = project_mod.add_package( sbproj, package_ref )
        _output( ctx, result, lambda d: f"Added package '{package_ref}'" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@project.command( "remove-package" )
@click.argument( "package_ref" )
@click.pass_context
def project_remove_package( ctx, package_ref ):
    """Remove a package reference from the project."""
    try:
        sbproj = _resolve_project_path( ctx )
        if not sbproj:
            _output_error( ctx, "No project found" )
            return
        result = project_mod.remove_package( sbproj, package_ref )
        _output( ctx, result, lambda d: f"Removed package '{package_ref}'" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@project.command( "validate" )
@click.option( "--no-refs", is_flag=True, help="Skip broken-reference detection" )
@click.option( "--no-guids", is_flag=True, help="Skip duplicate-GUID detection" )
@click.option( "--no-inputs", is_flag=True, help="Skip Input.config sanity checks" )
@click.pass_context
def project_validate( ctx, no_refs, no_guids, no_inputs ):
    """Validate project: broken asset refs, duplicate GUIDs, malformed inputs."""
    try:
        proj_dir = _resolve_project_dir( ctx )
        if not proj_dir:
            _output_error( ctx, "No project found" )
            return
        result = validate_mod.validate_project(
            proj_dir,
            check_refs=not no_refs,
            check_guids=not no_guids,
            check_inputs=not no_inputs,
        )

        def human( d ):
            lines = [f"Project validation: {'OK' if d['ok'] else 'FAIL'} ({d['issue_count']} issue(s))"]
            for ref in d.get( "broken_refs", [] ):
                lines.append( f"  [broken-ref] {ref['file']} -> {ref['ref']} ({ref['category']})" )
            for guid in d.get( "duplicate_guids", [] ):
                lines.append( f"  [duplicate-guid] {guid['file']} -> {guid['guid']}" )
                for occ in guid.get( "occurrences", [] ):
                    lines.append( f"      {occ}" )
            for inp in d.get( "invalid_inputs", [] ):
                lines.append( f"  [input] {inp.get( 'file', '?' )}: {inp.get( 'issue', '?' )}" )
            return "\n".join( lines )

        _output( ctx, result, human )
        # Validation failure must exit non-zero so CI can gate on this command.
        if not result.get( "ok", True ) and not ctx.obj.get( "repl" ):
            sys.exit( 1 )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# scene group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def scene( ctx ):
    """Manage s&box scenes."""
    pass


@scene.command( "new" )
@click.option( "--name", default="minimal", help="Scene name" )
@click.option( "-o", "--output", "output_path", default=None, help="Output file path" )
@click.option( "--no-defaults", is_flag=True, help="Skip default objects (Sun, Skybox, Plane, Camera)" )
@click.pass_context
def scene_new( ctx, name, output_path, no_defaults ):
    """Create a new scene."""
    try:
        if not output_path:
            output_path = f"{name}.scene"
        result = scene_mod.create_scene(
            name=name,
            output_path=output_path,
            include_defaults=not no_defaults,
        )
        info = {
            "name": name,
            "path": os.path.abspath( output_path ),
            "objects": len( result.get( "GameObjects", [] ) ),
            "defaults_included": not no_defaults,
        }
        _output( ctx, info, lambda d: _format_status_block( d, f"Scene '{d['name']}' created" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "info" )
@click.argument( "scene_path" )
@click.pass_context
def scene_info( ctx, scene_path ):
    """Show scene info."""
    try:
        result = scene_mod.get_scene_info( scene_path )
        _output( ctx, result, lambda d: _format_status_block( d, f"Scene: {d.get( 'title', '' )}" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "list" )
@click.argument( "scene_path" )
@click.pass_context
def scene_list( ctx, scene_path ):
    """List GameObjects in a scene."""
    try:
        objects = scene_mod.list_objects( scene_path )
        if ctx.obj.get( "json" ):
            _output( ctx, objects )
        else:
            rows = []
            for obj in objects:
                rows.append( {
                    "guid": obj["guid"][:12] + "...",
                    "name": obj["name"],
                    "position": obj["position"],
                    "components": ", ".join( t.split( "." )[-1] for t in obj["component_types"] ),
                } )
            click.echo( _format_table( rows, ["guid", "name", "position", "components"] ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "add-object" )
@click.argument( "scene_path" )
@click.argument( "name" )
@click.option( "--position", default="0,0,0", help="Position as x,y,z" )
@click.option( "--rotation", default="0,0,0,1", help="Rotation as x,y,z,w quaternion" )
@click.option( "--scale", default="1,1,1", help="Scale as x,y,z" )
@click.option( "--tags", default="", help="Space-separated tags" )
@click.option( "--components", default=None, help="Comma-separated preset names (e.g. model,box_collider,rigidbody)" )
@click.option( "--parent", default=None, help="Parent object GUID" )
@click.pass_context
def scene_add_object( ctx, scene_path, name, position, rotation, scale, tags, components, parent ):
    """Add a GameObject to a scene."""
    try:
        comp_list = None
        if components:
            comp_list = [c.strip() for c in components.split( "," )]

        new_guid = scene_mod.add_object(
            scene_path=scene_path,
            name=name,
            position=position,
            rotation=rotation,
            scale=scale,
            tags=tags,
            components=comp_list,
            parent_guid=parent,
        )
        result = {"guid": new_guid, "name": name, "scene": scene_path}
        _output( ctx, result, lambda d: f"Added '{d['name']}' ({d['guid']}) to {d['scene']}" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "remove-object" )
@click.argument( "scene_path" )
@click.option( "--name", default=None, help="Object name to remove" )
@click.option( "--guid", default=None, help="Object GUID to remove" )
@click.pass_context
def scene_remove_object( ctx, scene_path, name, guid ):
    """Remove a GameObject from a scene."""
    try:
        if not name and not guid:
            raise click.ClickException( "Must specify --name or --guid" )
        removed = scene_mod.remove_object( scene_path, name=name, guid=guid )
        result = {"removed": removed, "name": name, "guid": guid}
        if removed:
            _output( ctx, result, lambda d: f"Removed object from {scene_path}" )
        else:
            _output( ctx, result, lambda d: f"Object not found in {scene_path}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "add-component" )
@click.argument( "scene_path" )
@click.argument( "object_guid" )
@click.argument( "component_type" )
@click.option( "--properties", default=None, help="Component properties as JSON string" )
@click.pass_context
def scene_add_component( ctx, scene_path, object_guid, component_type, properties ):
    """Add a component to a GameObject."""
    try:
        props = None
        if properties:
            props = json.loads( properties )
        comp_guid = scene_mod.add_component(
            scene_path=scene_path,
            object_guid=object_guid,
            component_type=component_type,
            properties=props,
        )
        result = {"component_guid": comp_guid, "type": component_type, "object_guid": object_guid}
        _output( ctx, result, lambda d: f"Added {d['type']} ({d['component_guid']}) to object {d['object_guid']}" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "remove-component" )
@click.argument( "scene_path" )
@click.argument( "object_guid" )
@click.option( "--component-guid", default=None, help="Component GUID to remove" )
@click.option( "--component-type", default=None, help="Component type to remove (e.g. Sandbox.Rigidbody)" )
@click.pass_context
def scene_remove_component( ctx, scene_path, object_guid, component_guid, component_type ):
    """Remove a component from a GameObject."""
    try:
        if not component_guid and not component_type:
            _output_error( ctx, "Must provide --component-guid or --component-type" )
            return
        removed = scene_mod.remove_component( scene_path, object_guid, component_guid=component_guid, component_type=component_type )
        result = {"removed": removed, "object_guid": object_guid}
        _output( ctx, result, lambda d: f"Component {'removed' if d['removed'] else 'not found'}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "modify-object" )
@click.argument( "scene_path" )
@click.option( "--guid", default=None, help="Object GUID to modify" )
@click.option( "--name-match", default=None, help="Object name to match" )
@click.option( "--name", "new_name", default=None, help="New name for the object" )
@click.option( "--position", default=None, help="New position (x,y,z)" )
@click.option( "--rotation", default=None, help="New rotation (x,y,z,w)" )
@click.option( "--scale", default=None, help="New scale (x,y,z)" )
@click.option( "--tags", default=None, help="New tags (comma-separated)" )
@click.option( "--enabled/--disabled", default=None, help="Enable or disable object" )
@click.pass_context
def scene_modify_object( ctx, scene_path, guid, name_match, new_name, position, rotation, scale, tags, enabled ):
    """Modify an existing GameObject in a scene."""
    try:
        result = scene_mod.modify_object(
            scene_path,
            guid=guid,
            name_match=name_match,
            new_name=new_name,
            position=position,
            rotation=rotation,
            scale=scale,
            tags=tags,
            enabled=enabled,
        )
        _output( ctx, result, lambda d: f"Modified {d['name']} ({d['guid']}): {', '.join( d['modified_fields'] )}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "set-property" )
@click.argument( "scene_path" )
@click.option( "--fixed-update-freq", type=int, default=None, help="Fixed update frequency (Hz)" )
@click.option( "--network-freq", type=int, default=None, help="Network update frequency (Hz)" )
@click.option( "--timescale", type=float, default=None, help="Time scale (1.0 = normal)" )
@click.option( "--network-interpolation/--no-network-interpolation", default=None )
@click.option( "--physics-sub-steps", type=int, default=None )
@click.pass_context
def scene_set_property( ctx, scene_path, fixed_update_freq, network_freq, timescale, network_interpolation, physics_sub_steps ):
    """Modify SceneProperties of a scene."""
    try:
        kwargs = {}
        if fixed_update_freq is not None:
            kwargs["fixed_update_freq"] = fixed_update_freq
        if network_freq is not None:
            kwargs["network_freq"] = network_freq
        if timescale is not None:
            kwargs["timescale"] = timescale
        if network_interpolation is not None:
            kwargs["network_interpolation"] = network_interpolation
        if physics_sub_steps is not None:
            kwargs["physics_sub_steps"] = physics_sub_steps

        if not kwargs:
            _output_error( ctx, "No properties specified to change" )
            return

        result = scene_mod.set_scene_properties( scene_path, **kwargs )
        _output( ctx, result, lambda d: _format_status_block( d, "Scene Properties" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "clone-object" )
@click.argument( "scene_path" )
@click.option( "--guid", default=None, help="GUID of object to clone" )
@click.option( "--name-match", default=None, help="Name of object to clone" )
@click.option( "--new-name", default=None, help="Name for the clone" )
@click.option( "--position", default=None, help="Position for the clone (x,y,z)" )
@click.pass_context
def scene_clone_object( ctx, scene_path, guid, name_match, new_name, position ):
    """Clone (duplicate) a GameObject with new GUIDs."""
    try:
        result = scene_mod.clone_object(
            scene_path, guid=guid, name=name_match,
            new_name=new_name, position=position,
        )
        _output( ctx, result, lambda d: f"Cloned '{d['original_name']}' -> '{d['name']}' ({d['guid']})" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "get-object" )
@click.argument( "scene_path" )
@click.option( "--guid", default=None, help="Object GUID" )
@click.option( "--name", "name_match", default=None, help="Object name" )
@click.pass_context
def scene_get_object( ctx, scene_path, guid, name_match ):
    """Get full details of a single GameObject."""
    try:
        result = scene_mod.get_object( scene_path, guid=guid, name=name_match )
        _output( ctx, result, lambda d: _format_status_block( d, f"Object: {d['name']}" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "set-navmesh" )
@click.argument( "scene_path" )
@click.option( "--enabled/--disabled", "navmesh_enabled", default=None, help="Enable/disable NavMesh" )
@click.option( "--agent-height", type=float, default=None, help="Agent height" )
@click.option( "--agent-radius", type=float, default=None, help="Agent radius" )
@click.option( "--agent-step-size", type=float, default=None, help="Agent step size" )
@click.option( "--agent-max-slope", type=float, default=None, help="Agent max slope (degrees)" )
@click.pass_context
def scene_set_navmesh( ctx, scene_path, navmesh_enabled, agent_height, agent_radius, agent_step_size, agent_max_slope ):
    """Configure NavMesh properties for a scene."""
    try:
        kwargs = {}
        if navmesh_enabled is not None:
            kwargs["navmesh_enabled"] = navmesh_enabled
        if agent_height is not None:
            kwargs["navmesh_agent_height"] = agent_height
        if agent_radius is not None:
            kwargs["navmesh_agent_radius"] = agent_radius
        if agent_step_size is not None:
            kwargs["navmesh_agent_step_size"] = agent_step_size
        if agent_max_slope is not None:
            kwargs["navmesh_agent_max_slope"] = agent_max_slope

        if not kwargs:
            _output_error( ctx, "No NavMesh properties specified" )
            return

        result = scene_mod.set_navmesh_properties( scene_path, **kwargs )
        _output( ctx, result, lambda d: _format_status_block( d, "NavMesh Properties" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "list-presets" )
@click.pass_context
def scene_list_presets( ctx ):
    """List available component preset names."""
    try:
        from cli_anything.sbox.core.scene import COMPONENT_PRESETS
        presets = [{"name": k, "type": v["__type"]} for k, v in COMPONENT_PRESETS.items()]
        _output( ctx, presets )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "modify-component" )
@click.argument( "scene_path" )
@click.argument( "object_guid" )
@click.option( "--component-guid", default=None, help="Component GUID" )
@click.option( "--component-type", default=None, help="Component type (e.g. Sandbox.Rigidbody)" )
@click.option( "--properties", required=True, help="Properties to set as JSON" )
@click.pass_context
def scene_modify_component( ctx, scene_path, object_guid, component_guid, component_type, properties ):
    """Modify properties of an existing component."""
    try:
        import json as json_mod
        props = json_mod.loads( properties )
        result = scene_mod.modify_component(
            scene_path, object_guid,
            component_guid=component_guid,
            component_type=component_type,
            properties=props,
        )
        _output( ctx, result, lambda d: f"Modified {d['component_type']} on {d['object_guid']}: {', '.join( d['updated_keys'] )}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "query" )
@click.argument( "scene_path" )
@click.option( "--has-component", default=None, help="Filter by component (preset or full type)" )
@click.option( "--has-tag", default=None, help="Filter by tag (single token in Tags string)" )
@click.option( "--name-match", default=None, help="Filter by Name substring" )
@click.option( "--name-regex", default=None, help="Filter by Name regex pattern" )
@click.option( "--in-bounds", default=None, help="AABB filter: x_min,y_min,z_min,x_max,y_max,z_max" )
@click.option( "--enabled/--disabled", "enabled", default=None, help="Filter by Enabled state" )
@click.pass_context
def scene_query( ctx, scene_path, has_component, has_tag, name_match, name_regex, in_bounds, enabled ):
    """Find GameObjects matching one or more filters (AND-combined)."""
    try:
        results = scene_mod.query_objects(
            scene_path,
            has_component=has_component,
            has_tag=has_tag,
            name_match=name_match,
            name_regex=name_regex,
            in_bounds=in_bounds,
            enabled=enabled,
        )

        def human( rows ):
            if not rows:
                return "(no matches)"
            return _format_table(
                [{"name": r["name"], "guid": r["guid"][:8], "position": r["position"], "components": ",".join( r["component_types"] )[:60]} for r in rows],
                ["name", "guid", "position", "components"],
            )

        _output( ctx, results, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "refs" )
@click.argument( "scene_path" )
@click.pass_context
def scene_refs( ctx, scene_path ):
    """Extract every asset reference from a scene, grouped by category."""
    try:
        result = scene_mod.extract_asset_refs( scene_path )

        def human( d ):
            if not d:
                return "(no asset references)"
            lines = []
            for category in sorted( d.keys() ):
                lines.append( f"{category} ({len( d[category] )}):" )
                for ref in d[category]:
                    lines.append( f"  {ref}" )
            return "\n".join( lines )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "bulk-modify" )
@click.argument( "scene_path" )
@click.option( "--has-component", default=None, help="Filter: object has this component" )
@click.option( "--has-tag", default=None, help="Filter: object has this tag" )
@click.option( "--name-match", default=None, help="Filter: Name contains substring" )
@click.option( "--name-regex", default=None, help="Filter: Name matches regex" )
@click.option( "--in-bounds", default=None, help="Filter: position inside AABB" )
@click.option( "--filter-enabled/--filter-disabled", "filter_enabled", default=None, help="Filter by Enabled state" )
@click.option( "--position", "new_position", default=None, help="New Position 'x,y,z'" )
@click.option( "--rotation", "new_rotation", default=None, help="New Rotation 'x,y,z,w'" )
@click.option( "--scale", "new_scale", default=None, help="New Scale 'x,y,z'" )
@click.option( "--tags", "new_tags", default=None, help="New Tags string" )
@click.option( "--enable/--disable", "new_enabled", default=None, help="Set Enabled state" )
@click.pass_context
def scene_bulk_modify( ctx, scene_path, has_component, has_tag, name_match, name_regex, in_bounds, filter_enabled, new_position, new_rotation, new_scale, new_tags, new_enabled ):
    """Apply the same modification to every object matching the filters."""
    try:
        result = scene_mod.bulk_modify_objects(
            scene_path,
            has_component=has_component,
            has_tag=has_tag,
            name_match=name_match,
            name_regex=name_regex,
            in_bounds=in_bounds,
            enabled_filter=filter_enabled,
            new_position=new_position,
            new_rotation=new_rotation,
            new_scale=new_scale,
            new_tags=new_tags,
            new_enabled=new_enabled,
        )
        _output( ctx, result, lambda d: f"Modified {d['modified_count']} object(s); fields: {', '.join( d['modified_fields'] )}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "diff" )
@click.argument( "scene_a" )
@click.argument( "scene_b" )
@click.pass_context
def scene_diff( ctx, scene_a, scene_b ):
    """Structural diff between two scenes (objects added/removed/modified by Name)."""
    try:
        result = scene_mod.diff_scenes( scene_a, scene_b )

        def human( d ):
            if d["identical"]:
                return f"Scenes are identical: {d['scene_a']} == {d['scene_b']}"
            lines = [f"Diff: {d['scene_a']} -> {d['scene_b']}"]
            if d["added"]:
                lines.append( f"  Added ({len( d['added'] )}): {', '.join( d['added'] )}" )
            if d["removed"]:
                lines.append( f"  Removed ({len( d['removed'] )}): {', '.join( d['removed'] )}" )
            if d["modified"]:
                lines.append( f"  Modified ({len( d['modified'] )}):" )
                for m in d["modified"]:
                    keys = list( m["changes"].keys() )
                    lines.append( f"    {m['name']}: {', '.join( keys )}" )
            if d.get( "scene_property_changes" ):
                lines.append( f"  SceneProperties changes: {', '.join( d['scene_property_changes'].keys() )}" )
            return "\n".join( lines )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@scene.command( "instantiate-prefab" )
@click.argument( "scene_path" )
@click.argument( "prefab_path" )
@click.option( "--name", default=None, help="Override the GameObject name (defaults to prefab root name)" )
@click.option( "--position", default="0,0,0", help="Position 'x,y,z'" )
@click.option( "--rotation", default="0,0,0,1", help="Rotation 'x,y,z,w'" )
@click.option( "--scale", default="1,1,1", help="Scale 'x,y,z'" )
@click.option( "--parent-guid", default=None, help="Optional parent GameObject GUID" )
@click.pass_context
def scene_instantiate_prefab( ctx, scene_path, prefab_path, name, position, rotation, scale, parent_guid ):
    """Insert a prefab reference into a scene as a new GameObject (PrefabSource)."""
    try:
        new_guid = scene_mod.instantiate_prefab(
            scene_path, prefab_path,
            name=name, position=position, rotation=rotation, scale=scale,
            parent_guid=parent_guid,
        )
        result = {"guid": new_guid, "scene": scene_path, "prefab": prefab_path}
        _output( ctx, result, lambda d: f"Instantiated prefab as GameObject {d['guid']}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# prefab group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def prefab( ctx ):
    """Manage s&box prefabs."""
    pass


@prefab.command( "new" )
@click.option( "--name", required=True, help="Prefab name" )
@click.option( "-o", "--output", "output_path", default=None, help="Output file path" )
@click.option( "--components", default=None, help="Comma-separated preset names" )
@click.pass_context
def prefab_new( ctx, name, output_path, components ):
    """Create a new prefab."""
    try:
        if not output_path:
            output_path = f"{name}.prefab"

        comp_list = None
        if components:
            comp_list = [c.strip() for c in components.split( "," )]

        result = prefab_mod.create_prefab(
            name=name,
            output_path=output_path,
            components=comp_list,
        )
        info = {
            "name": name,
            "path": os.path.abspath( output_path ),
            "root_guid": result.get( "RootObject", {} ).get( "__guid", "" ),
        }
        _output( ctx, info, lambda d: _format_status_block( d, f"Prefab '{d['name']}' created" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "info" )
@click.argument( "prefab_path" )
@click.pass_context
def prefab_info( ctx, prefab_path ):
    """Show prefab info."""
    try:
        result = prefab_mod.get_prefab_info( prefab_path )
        _output( ctx, result, lambda d: _format_status_block( d, f"Prefab: {d.get( 'name', '' )}" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "from-scene" )
@click.argument( "scene_path" )
@click.argument( "object_guid" )
@click.option( "-o", "--output", "output_path", default=None, help="Output prefab file path" )
@click.pass_context
def prefab_from_scene( ctx, scene_path, object_guid, output_path ):
    """Extract a GameObject from a scene as a prefab."""
    try:
        if not output_path:
            output_path = f"{object_guid}.prefab"
        result = prefab_mod.from_scene_object(
            scene_path=scene_path,
            object_guid=object_guid,
            output_path=output_path,
        )
        info = {
            "name": result.get( "RootObject", {} ).get( "Name", "" ),
            "path": os.path.abspath( output_path ),
            "guid": result.get( "RootObject", {} ).get( "__guid", "" ),
        }
        _output( ctx, info, lambda d: _format_status_block( d, f"Prefab extracted: {d.get( 'name', '' )}" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "add-component" )
@click.argument( "prefab_path" )
@click.argument( "component_type" )
@click.option( "--properties", default=None, help="Component properties as JSON" )
@click.pass_context
def prefab_add_component( ctx, prefab_path, component_type, properties ):
    """Add a component to a prefab's root object."""
    try:
        import json as json_mod
        import uuid as uuid_mod
        import copy as copy_mod
        props = json_mod.loads( properties ) if properties else {}
        data = prefab_mod.load_prefab( prefab_path )
        root = data.get( "RootObject", {} )
        comps = root.get( "Components", [] )
        from cli_anything.sbox.core.scene import COMPONENT_PRESETS
        if component_type in COMPONENT_PRESETS:
            comp = copy_mod.deepcopy( COMPONENT_PRESETS[component_type] )
        else:
            comp = {"__type": component_type}
        comp["__guid"] = str( uuid_mod.uuid4() )
        comp.update( props )
        comps.append( comp )
        root["Components"] = comps
        data["RootObject"] = root
        prefab_mod.save_prefab( prefab_path, data )
        _output( ctx, {"guid": comp["__guid"], "type": comp["__type"], "prefab": prefab_path},
                 lambda d: f"Added {d['type']} ({d['guid']}) to prefab" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "remove-component" )
@click.argument( "prefab_path" )
@click.option( "--component-guid", default=None, help="Component GUID to remove" )
@click.option( "--component-type", default=None, help="Component type to remove" )
@click.pass_context
def prefab_remove_component( ctx, prefab_path, component_guid, component_type ):
    """Remove a component from a prefab's root object."""
    try:
        if not component_guid and not component_type:
            _output_error( ctx, "Must provide --component-guid or --component-type" )
            return
        data = prefab_mod.load_prefab( prefab_path )
        root = data.get( "RootObject", {} )
        comps = root.get( "Components", [] )
        original_count = len( comps )
        if component_guid:
            comps = [c for c in comps if c.get( "__guid" ) != component_guid]
        elif component_type:
            comps = [c for c in comps if c.get( "__type" ) != component_type]
        removed = original_count > len( comps )
        root["Components"] = comps
        data["RootObject"] = root
        prefab_mod.save_prefab( prefab_path, data )
        _output( ctx, {"removed": removed}, lambda d: f"Component {'removed' if d['removed'] else 'not found'}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "list" )
@click.pass_context
def prefab_list( ctx ):
    """List prefabs in the project."""
    try:
        project_dir = _resolve_project_dir( ctx )
        if not project_dir:
            _output_error( ctx, "No project found" )
            return
        from cli_anything.sbox.core import export as export_mod_local
        assets = export_mod_local.list_assets( project_dir, asset_type="prefab" )
        _output( ctx, assets )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "refs" )
@click.argument( "prefab_path" )
@click.pass_context
def prefab_refs( ctx, prefab_path ):
    """Extract every asset reference from a prefab, grouped by category."""
    try:
        result = prefab_mod.extract_asset_refs( prefab_path )

        def human( d ):
            if not d:
                return "(no asset references)"
            lines = []
            for category in sorted( d.keys() ):
                lines.append( f"{category} ({len( d[category] )}):" )
                for ref in d[category]:
                    lines.append( f"  {ref}" )
            return "\n".join( lines )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "modify-component" )
@click.argument( "prefab_path" )
@click.option( "--component-guid", default=None, help="Component GUID" )
@click.option( "--component-type", default=None, help="Component type (e.g. Sandbox.Rigidbody)" )
@click.option( "--object-guid", default=None, help="Restrict search to a single object" )
@click.option( "--properties", required=True, help="Properties to set as JSON" )
@click.pass_context
def prefab_modify_component( ctx, prefab_path, component_guid, component_type, object_guid, properties ):
    """Modify properties of a component within a prefab."""
    try:
        import json as json_mod
        props = json_mod.loads( properties )
        result = prefab_mod.modify_component(
            prefab_path,
            component_guid=component_guid,
            component_type=component_type,
            object_guid=object_guid,
            properties=props,
        )
        _output( ctx, result, lambda d: f"Modified {d['component_type']}: {', '.join( d['updated_keys'] )}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@prefab.command( "diff" )
@click.argument( "prefab_a" )
@click.argument( "prefab_b" )
@click.pass_context
def prefab_diff( ctx, prefab_a, prefab_b ):
    """Structural diff between two prefabs (root + children by Name)."""
    try:
        result = prefab_mod.diff_prefabs( prefab_a, prefab_b )

        def human( d ):
            if d["identical"]:
                return f"Prefabs are identical: {d['prefab_a']} == {d['prefab_b']}"
            lines = [f"Diff: {d['prefab_a']} -> {d['prefab_b']}"]
            if d.get( "root_changes" ):
                keys = list( d["root_changes"]["changes"].keys() )
                lines.append( f"  Root changed: {', '.join( keys )}" )
            if d["children_added"]:
                lines.append( f"  Children added ({len( d['children_added'] )}): {', '.join( d['children_added'] )}" )
            if d["children_removed"]:
                lines.append( f"  Children removed ({len( d['children_removed'] )}): {', '.join( d['children_removed'] )}" )
            if d["children_modified"]:
                lines.append( f"  Children modified ({len( d['children_modified'] )}):" )
                for m in d["children_modified"]:
                    keys = list( m["changes"].keys() )
                    lines.append( f"    {m['name']}: {', '.join( keys )}" )
            return "\n".join( lines )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# codegen group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def codegen( ctx ):
    """Generate s&box C# code."""
    pass


@codegen.command( "component" )
@click.option( "--name", required=True, help="Component class name (PascalCase)" )
@click.option( "-o", "--output", "output_path", default=None, help="Output file path" )
@click.option( "--properties", default=None, help="Properties as JSON array of {name, type, default?, category?}" )
@click.option( "--methods", default=None, help="Comma-separated lifecycle methods (OnUpdate, OnFixedUpdate, OnStart)" )
@click.option( "--networked", is_flag=True, help="Generate networked component (partial class, [Sync] attributes)" )
@click.option( "--interfaces", default=None, help="Comma-separated interface names" )
@click.option( "--rpc-methods", default=None, help="RPC methods as Name:Type pairs (e.g. Fire:Broadcast,Die:Host)" )
@click.pass_context
def codegen_component( ctx, name, output_path, properties, methods, networked, interfaces, rpc_methods ):
    """Generate a C# component class."""
    try:
        props = None
        if properties:
            props = json.loads( properties )

        method_list = None
        if methods:
            method_list = [m.strip() for m in methods.split( "," )]

        iface_list = None
        if interfaces:
            iface_list = [i.strip() for i in interfaces.split( "," )]

        rpc_list = None
        if rpc_methods:
            rpc_list = []
            for pair in rpc_methods.split(","):
                parts = pair.strip().split(":")
                rpc_list.append({"name": parts[0].strip(), "type": parts[1].strip() if len(parts) > 1 else "Broadcast"})

        result = codegen_mod.generate_component(
            class_name=name,
            properties=props,
            lifecycle_methods=method_list,
            interfaces=iface_list,
            is_networked=networked,
            rpc_methods=rpc_list,
        )

        if output_path:
            os.makedirs( os.path.dirname( output_path ) if os.path.dirname( output_path ) else ".", exist_ok=True )
            with open( output_path, "w", encoding="utf-8", newline="\r\n" ) as f:
                f.write( result["content"] )
            result["path"] = os.path.abspath( output_path )
        else:
            result["path"] = result["filename"]

        if ctx.obj.get( "json" ):
            _output( ctx, result )
        else:
            if output_path:
                click.echo( f"Generated {result['filename']} at {result['path']}" )
            else:
                click.echo( f"--- {result['filename']} ---" )
                click.echo( result["content"] )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@codegen.command( "gameresource" )
@click.option( "--name", required=True, help="GameResource class name" )
@click.option( "--display-name", default=None, help="Display name in editor" )
@click.option( "--extension", default=None, help="File extension for the resource" )
@click.option( "-o", "--output", "output_path", default=None, help="Output file path" )
@click.option( "--properties", default=None, help="Properties as JSON array of {name, type, default?, category?}" )
@click.pass_context
def codegen_gameresource( ctx, name, display_name, extension, output_path, properties ):
    """Generate a GameResource class."""
    try:
        props = None
        if properties:
            props = json.loads( properties )

        result = codegen_mod.generate_gameresource(
            class_name=name,
            display_name=display_name or name,
            extension=extension or name.lower(),
            properties=props,
        )

        if output_path:
            os.makedirs( os.path.dirname( output_path ) if os.path.dirname( output_path ) else ".", exist_ok=True )
            with open( output_path, "w", encoding="utf-8", newline="\r\n" ) as f:
                f.write( result["content"] )
            result["path"] = os.path.abspath( output_path )
        else:
            result["path"] = result["filename"]

        if ctx.obj.get( "json" ):
            _output( ctx, result )
        else:
            if output_path:
                click.echo( f"Generated {result['filename']} at {result['path']}" )
            else:
                click.echo( f"--- {result['filename']} ---" )
                click.echo( result["content"] )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@codegen.command( "editor-menu" )
@click.option( "--name", required=True, help="Editor menu class name" )
@click.option( "--menu-path", default=None, help="Menu path (e.g. Tools/My Tool)" )
@click.option( "-o", "--output", "output_path", default=None, help="Output file path" )
@click.pass_context
def codegen_editor_menu( ctx, name, menu_path, output_path ):
    """Generate an editor menu class."""
    try:
        result = codegen_mod.generate_editor_menu(
            class_name=name,
            menu_path=menu_path or f"Tools/{name}",
        )

        if output_path:
            os.makedirs( os.path.dirname( output_path ) if os.path.dirname( output_path ) else ".", exist_ok=True )
            with open( output_path, "w", encoding="utf-8", newline="\r\n" ) as f:
                f.write( result["content"] )
            result["path"] = os.path.abspath( output_path )
        else:
            result["path"] = result["filename"]

        if ctx.obj.get( "json" ):
            _output( ctx, result )
        else:
            if output_path:
                click.echo( f"Generated {result['filename']} at {result['path']}" )
            else:
                click.echo( f"--- {result['filename']} ---" )
                click.echo( result["content"] )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@codegen.command( "razor" )
@click.option( "--name", required=True, help="Component class name (PascalCase)" )
@click.option( "--inherits", default="PanelComponent", help="Base class" )
@click.option( "--properties", default=None, help="Properties as JSON array" )
@click.option( "--root-class", default=None, help="CSS class for root element" )
@click.option( "-o", "--output", "output_path", default=None, help="Output .razor file path" )
@click.pass_context
def codegen_razor( ctx, name, inherits, properties, root_class, output_path ):
    """Generate a Razor UI component."""
    try:
        props = json.loads( properties ) if properties else None
        result = codegen_mod.generate_razor( name, inherits=inherits, properties=props, root_class=root_class )

        if output_path:
            os.makedirs( os.path.dirname( output_path ) or ".", exist_ok=True )
            with open( output_path, "w", encoding="utf-8" ) as f:
                f.write( result["content"] )
            # Also write scss
            if output_path.endswith( ".razor" ):
                scss_path = output_path + ".scss"
            elif output_path.endswith( ".scss" ):
                scss_path = output_path
            else:
                scss_path = output_path + ".scss"
            with open( scss_path, "w", encoding="utf-8" ) as f:
                f.write( result["scss_content"] )
            result["path"] = os.path.abspath( output_path )
            result["scss_path"] = os.path.abspath( scss_path )

        _output( ctx, result, lambda d: f"Razor component '{d['class_name']}' generated" + (f" at {d.get('path', '')}" if d.get('path') else "") )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@codegen.command( "class" )
@click.option( "--name", required=True, help="Class name (PascalCase)" )
@click.option( "--base-class", default=None, help="Base class to inherit from" )
@click.option( "--static", "is_static", is_flag=True, help="Generate a static class" )
@click.option( "--properties", default=None, help="Properties as JSON array" )
@click.option( "--methods", default=None, help="Methods as JSON array" )
@click.option( "-o", "--output", "output_path", default=None, help="Output .cs file path" )
@click.pass_context
def codegen_class( ctx, name, base_class, is_static, properties, methods, output_path ):
    """Generate a plain C# class."""
    try:
        props = json.loads( properties ) if properties else None
        meths = json.loads( methods ) if methods else None
        result = codegen_mod.generate_class( name, base_class=base_class, is_static=is_static, properties=props, methods=meths )

        if output_path:
            os.makedirs( os.path.dirname( output_path ) or ".", exist_ok=True )
            with open( output_path, "w", encoding="utf-8" ) as f:
                f.write( result["content"] )
            result["path"] = os.path.abspath( output_path )

        _output( ctx, result, lambda d: f"Class '{d['class_name']}' generated" + ( f" at {d.get( 'path', '' )}" if d.get( 'path' ) else "" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@codegen.command( "panel-component" )
@click.option( "--name", required=True, help="PanelComponent class name (PascalCase)" )
@click.option( "--namespace", default=None, help="Optional C# namespace" )
@click.option( "--properties", default=None, help="Properties as JSON array (same format as razor)" )
@click.option( "--root-class", default=None, help="CSS root class (default: kebab-case of name)" )
@click.option( "--z-index", "z_index", type=int, default=100, help="ScreenPanel ZIndex (default 100)" )
@click.option( "--opacity", type=float, default=1.0, help="ScreenPanel Opacity (default 1.0)" )
@click.option( "-o", "--output", "output_path", default=None, help="Output .razor file path (also writes .razor.scss)" )
@click.option( "--scene", "scene_path", default=None, help="Optional scene to append the GameObject snippet to" )
@click.pass_context
def codegen_panel_component( ctx, name, namespace, properties, root_class, z_index, opacity, output_path, scene_path ):
    """Scaffold a PanelComponent + sibling ScreenPanel on the same GameObject.

    Handles the s&box quirk where PanelComponent input requires both components
    on the same GameObject. Emits .razor + .razor.scss + a paste-ready GameObject
    JSON snippet, and can optionally append the GameObject directly to a scene.
    """
    try:
        props = json.loads( properties ) if properties else None
        result = codegen_mod.generate_panel_component(
            name,
            properties=props,
            namespace=namespace,
            z_index=z_index,
            opacity=opacity,
            root_class=root_class,
        )

        if output_path:
            os.makedirs( os.path.dirname( output_path ) or ".", exist_ok=True )
            with open( output_path, "w", encoding="utf-8" ) as f:
                f.write( result["content"] )
            scss_path = os.path.join( os.path.dirname( output_path ), result["scss_filename"] )
            with open( scss_path, "w", encoding="utf-8" ) as f:
                f.write( result["scss_content"] )
            result["razor_path"] = os.path.abspath( output_path )
            result["scss_path"] = os.path.abspath( scss_path )

        if scene_path:
            scene_data = scene_mod.load_scene( scene_path )
            snippet_obj = json.loads( result["scene_snippet"] )
            scene_data.setdefault( "GameObjects", [] ).append( snippet_obj )
            scene_mod.save_scene( scene_path, scene_data )
            result["scene_appended_to"] = os.path.abspath( scene_path )

        def human( d ):
            lines = [f"PanelComponent '{d['class_name']}' generated"]
            if d.get( "razor_path" ):
                lines.append( f"  razor: {d['razor_path']}" )
                lines.append( f"  scss:  {d['scss_path']}" )
            if d.get( "scene_appended_to" ):
                lines.append( f"  scene: appended to {d['scene_appended_to']} (object_guid={d['object_guid']})" )
            else:
                lines.append( "  Paste the snippet under GameObjects in your .scene to wire it up." )
            return "\n".join( lines )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# input group
# ---------------------------------------------------------------------------


@cli.group( "input" )
@click.pass_context
def input_group( ctx ):
    """Manage s&box input action bindings."""
    pass


@input_group.command( "list" )
@click.argument( "config_path", required=False, default=None )
@click.pass_context
def input_list( ctx, config_path ):
    """List input actions."""
    try:
        resolved = _resolve_input_config( ctx, config_path )
        actions = input_config_mod.list_actions( resolved )
        if ctx.obj.get( "json" ):
            _output( ctx, actions )
        else:
            rows = []
            for a in actions:
                rows.append( {
                    "name": a.get( "Name", "" ),
                    "group": a.get( "GroupName", "" ),
                    "keyboard": a.get( "KeyboardCode", "" ),
                    "gamepad": a.get( "GamepadCode", "" ),
                } )
            click.echo( _format_table( rows, ["name", "group", "keyboard", "gamepad"] ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@input_group.command( "add" )
@click.option( "--name", required=True, help="Action name" )
@click.option( "--group", default="Other", help="Group name" )
@click.option( "--keyboard", default="None", help="Keyboard binding" )
@click.option( "--gamepad", default="None", help="Gamepad binding" )
@click.option( "--title", default=None, help="Display title" )
@click.pass_context
def input_add( ctx, name, group, keyboard, gamepad, title ):
    """Add an input action."""
    try:
        resolved = _resolve_input_config( ctx )
        result = input_config_mod.add_action(
            config_path=resolved,
            name=name,
            group=group,
            keyboard_code=keyboard,
            gamepad_code=gamepad,
            title=title,
        )
        _output( ctx, result, lambda d: f"Added action '{d.get( 'Name', '' )}' in group '{d.get( 'GroupName', '' )}'" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@input_group.command( "remove" )
@click.option( "--name", required=True, help="Action name to remove" )
@click.pass_context
def input_remove( ctx, name ):
    """Remove an input action."""
    try:
        resolved = _resolve_input_config( ctx )
        removed = input_config_mod.remove_action( resolved, name )
        result = {"removed": removed, "name": name}
        if removed:
            _output( ctx, result, lambda d: f"Removed action '{d['name']}'" )
        else:
            _output( ctx, result, lambda d: f"Action '{d['name']}' not found" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@input_group.command( "set" )
@click.option( "--name", required=True, help="Action name to modify" )
@click.option( "--keyboard", default=None, help="New keyboard binding" )
@click.option( "--gamepad", default=None, help="New gamepad binding" )
@click.option( "--group", default=None, help="New group name" )
@click.pass_context
def input_set( ctx, name, keyboard, gamepad, group ):
    """Modify an input action."""
    try:
        resolved = _resolve_input_config( ctx )
        result = input_config_mod.set_action(
            config_path=resolved,
            name=name,
            keyboard_code=keyboard,
            gamepad_code=gamepad,
            group=group,
        )
        _output( ctx, result, lambda d: f"Updated action '{d.get( 'Name', '' )}'" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# collision group
# ---------------------------------------------------------------------------


@cli.group( "collision" )
@click.pass_context
def collision_group( ctx ):
    """Manage s&box collision layers and rules."""
    pass


@collision_group.command( "list" )
@click.pass_context
def collision_list( ctx ):
    """List collision layers and rules."""
    try:
        resolved = _resolve_collision_config( ctx )
        result = collision_config_mod.list_layers( resolved )
        if ctx.obj.get( "json" ):
            _output( ctx, result )
        else:
            click.echo( "Layers:" )
            defaults = result.get( "defaults", {} )
            for layer_name, default_val in defaults.items():
                click.echo( f"  {layer_name}: {default_val}" )

            click.echo( "" )
            click.echo( "Pair Rules:" )
            pairs = result.get( "pairs", [] )
            if pairs:
                rows = []
                for p in pairs:
                    rows.append( {
                        "layer_a": p.get( "a", p.get( "A", "" ) ),
                        "layer_b": p.get( "b", p.get( "B", "" ) ),
                        "result": p.get( "r", p.get( "Collide", "" ) ),
                    } )
                click.echo( _format_table( rows, ["layer_a", "layer_b", "result"] ) )
            else:
                click.echo( "  (none)" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@collision_group.command( "add-layer" )
@click.option( "--name", required=True, help="Layer name" )
@click.option( "--default", "default_val", type=click.Choice( ["Collide", "Trigger", "Ignore"] ), default="Collide", help="Default collision behavior" )
@click.pass_context
def collision_add_layer( ctx, name, default_val ):
    """Add a collision layer."""
    try:
        resolved = _resolve_collision_config( ctx )
        result = collision_config_mod.add_layer( resolved, name, default=default_val )
        _output( ctx, result, lambda d: f"Added layer '{name}' with default '{default_val}'" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@collision_group.command( "add-rule" )
@click.option( "--layer-a", required=True, help="First layer" )
@click.option( "--layer-b", required=True, help="Second layer" )
@click.option( "--result", type=click.Choice( ["Collide", "Trigger", "Ignore"] ), default="Collide", help="Collision result" )
@click.pass_context
def collision_add_rule( ctx, layer_a, layer_b, result ):
    """Add a collision pair rule."""
    try:
        resolved = _resolve_collision_config( ctx )
        rule = collision_config_mod.add_rule( resolved, layer_a, layer_b, result=result )
        _output( ctx, rule, lambda d: f"Rule: {layer_a} <-> {layer_b} = {result}" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@collision_group.command( "remove-rule" )
@click.option( "--layer-a", required=True, help="First collision layer" )
@click.option( "--layer-b", required=True, help="Second collision layer" )
@click.pass_context
def collision_remove_rule( ctx, layer_a, layer_b ):
    """Remove a collision pair rule."""
    try:
        config_path = _resolve_collision_config( ctx )
        removed = collision_config_mod.remove_rule( config_path, layer_a, layer_b )
        result = {"removed": removed, "layer_a": layer_a, "layer_b": layer_b}
        _output( ctx, result, lambda d: f"Rule {d['layer_a']}-{d['layer_b']} {'removed' if d['removed'] else 'not found'}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@collision_group.command( "remove-layer" )
@click.option( "--name", required=True, help="Layer name to remove" )
@click.pass_context
def collision_remove_layer( ctx, name ):
    """Remove a custom collision layer."""
    try:
        config_path = _resolve_collision_config( ctx )
        removed = collision_config_mod.remove_layer( config_path, name )
        result = {"removed": removed, "layer": name}
        _output( ctx, result, lambda d: f"Layer '{d['layer']}' {'removed' if d['removed'] else 'not found'}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# server group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def server( ctx ):
    """Manage s&box dedicated server."""
    pass


@server.command( "start" )
@click.option( "--game", required=True, help="Game identifier (e.g. org.gamename)" )
@click.option( "--map", "map_ident", default=None, help="Map identifier" )
@click.pass_context
def server_start( ctx, game, map_ident ):
    """Launch a dedicated server."""
    try:
        proc = sbox_backend.launch_server( game, map_ident=map_ident )
        result = {"pid": proc.pid, "game": game, "map": map_ident, "status": "launched"}
        _output( ctx, result, lambda d: f"Server launched (PID {d['pid']}) - game: {d['game']}" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@server.command( "info" )
@click.pass_context
def server_info( ctx ):
    """Show server executable path and version."""
    try:
        exe = sbox_backend.find_executable( "sbox-server" )
        version = sbox_backend.get_sbox_version()
        # get_sbox_version is documented to return {"error": ...} on failure
        # rather than raising, so check explicitly to propagate exit code.
        if isinstance( version, dict ) and version.get( "error" ):
            _output_error( ctx, f"Failed to read s&box version: {version['error']}" )
            return
        result = {"executable": exe, "version": version}
        _output( ctx, result, lambda d: _format_status_block( {
            "executable": d["executable"],
            "version": d["version"].get( "version", "unknown" ),
            "sbox_path": d["version"].get( "sbox_path", "unknown" ),
        }, "Server Info" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# asset group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def asset( ctx ):
    """Manage project assets."""
    pass


@asset.command( "list" )
@click.option( "--type", "asset_type", default=None, help="Filter by asset type (scene, prefab, material, model, etc.)" )
@click.pass_context
def asset_list( ctx, asset_type ):
    """List project assets."""
    try:
        proj_dir = _resolve_project_dir( ctx )
        if not proj_dir:
            raise click.ClickException( "No project found. Use --project or run from a project directory." )

        assets = export_mod.list_assets( proj_dir, asset_type=asset_type )
        if ctx.obj.get( "json" ):
            _output( ctx, assets )
        else:
            if not assets:
                click.echo( "No assets found." )
                return
            rows = []
            for a in assets:
                size_kb = a["size_bytes"] / 1024
                rows.append( {
                    "name": a["name"],
                    "type": a["type"],
                    "path": a["path"],
                    "size": f"{size_kb:.1f} KB",
                } )
            click.echo( _format_table( rows, ["name", "type", "path", "size"] ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@asset.command( "info" )
@click.argument( "asset_path" )
@click.pass_context
def asset_info( ctx, asset_path ):
    """Show asset details."""
    try:
        result = export_mod.get_asset_info( asset_path )
        # _parse_json_asset embeds parse failures as json_info.error; surface
        # those so a malformed scene/prefab yields a non-zero exit code.
        json_info_error = result.get( "json_info", {} ).get( "error" ) if isinstance( result.get( "json_info" ), dict ) else None
        if json_info_error:
            _output_error( ctx, f"{result.get( 'name', asset_path )}: {json_info_error}" )
            return
        _output( ctx, result, lambda d: _format_status_block( d, f"Asset: {d.get( 'name', '' )}" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@asset.command( "compile" )
@click.argument( "asset_path" )
@click.pass_context
def asset_compile( ctx, asset_path ):
    """Compile an asset using s&box resource compiler."""
    try:
        from cli_anything.sbox.utils import sbox_backend
        result = sbox_backend.run_resource_compiler( asset_path )
        if not result.get( "success", False ):
            rc = result.get( "return_code", "?" )
            stderr = ( result.get( "stderr" ) or "" ).strip()
            detail = f": {stderr}" if stderr else ""
            _output_error( ctx, f"Resource compilation failed (return code {rc}){detail}" )
            return
        _output( ctx, result, lambda d: f"Compiled: {d.get( 'asset_path', asset_path )}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@asset.command( "find-refs" )
@click.argument( "asset_path" )
@click.pass_context
def asset_find_refs( ctx, asset_path ):
    """Find every scene/prefab in the project that references the given asset."""
    try:
        proj_dir = _resolve_project_dir( ctx )
        if not proj_dir:
            _output_error( ctx, "No project found" )
            return
        result = export_mod.find_asset_refs( proj_dir, asset_path )

        def human( rows ):
            if not rows:
                return f"(no references to {asset_path})"
            lines = [f"Found {len( rows )} reference(s) to {asset_path}:"]
            for row in rows:
                lines.append( f"  {row['file']} ({row['category']}) -> {row['original_ref']}" )
            return "\n".join( lines )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@asset.command( "find-unused" )
@click.option( "--type", "asset_types", multiple=True, help="Asset types to check (model, material, sound, texture, prefab). Repeatable." )
@click.pass_context
def asset_find_unused( ctx, asset_types ):
    """Find project assets that aren't referenced by any scene or prefab."""
    try:
        proj_dir = _resolve_project_dir( ctx )
        if not proj_dir:
            _output_error( ctx, "No project found" )
            return
        types_list = list( asset_types ) if asset_types else None
        result = export_mod.find_unused_assets( proj_dir, asset_types=types_list )

        def human( rows ):
            if not rows:
                return "(no unused assets found)"
            return _format_table(
                [{"path": r["path"], "type": r["type"], "size_bytes": r["size_bytes"]} for r in rows],
                ["path", "type", "size_bytes"],
            )

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@asset.command( "rename" )
@click.argument( "old_path" )
@click.argument( "new_name" )
@click.option( "--dry-run", is_flag=True, help="Report what would change without touching files" )
@click.pass_context
def asset_rename( ctx, old_path, new_name, dry_run ):
    """Rename an asset (in same directory) and update every reference in scenes/prefabs."""
    try:
        proj_dir = _resolve_project_dir( ctx )
        if not proj_dir:
            _output_error( ctx, "No project found" )
            return
        result = export_mod.rename_asset( proj_dir, old_path, new_name, dry_run=dry_run )

        def human( d ):
            if d.get( "dry_run" ):
                return f"[dry-run] Would rename {d['old_path']} -> {d['new_path']} and update {d['references_would_update']} reference(s)"
            n = sum( r["replacements"] for r in d["references_updated"] )
            return f"Renamed {d['old_path']} -> {d['new_path']}, updated {n} reference(s) in {len( d['references_updated'] )} file(s)"

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@asset.command( "move" )
@click.argument( "old_path" )
@click.argument( "new_path" )
@click.option( "--dry-run", is_flag=True, help="Report what would change without touching files" )
@click.pass_context
def asset_move( ctx, old_path, new_path, dry_run ):
    """Move an asset to a new path (different directory) and update every reference."""
    try:
        proj_dir = _resolve_project_dir( ctx )
        if not proj_dir:
            _output_error( ctx, "No project found" )
            return
        result = export_mod.move_asset( proj_dir, old_path, new_path, dry_run=dry_run )

        def human( d ):
            if d.get( "dry_run" ):
                return f"[dry-run] Would move {d['old_path']} -> {d['new_path']} and update {d['references_would_update']} reference(s)"
            n = sum( r["replacements"] for r in d["references_updated"] )
            return f"Moved {d['old_path']} -> {d['new_path']}, updated {n} reference(s) in {len( d['references_updated'] )} file(s)"

        _output( ctx, result, human )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# material group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def material( ctx ):
    """Manage s&box materials."""
    pass


@material.command( "new" )
@click.option( "--name", required=True, help="Material name" )
@click.option( "--shader", default="complex", help="Shader (complex, simple, unlit, glass)" )
@click.option( "--color-texture", default=None, help="Color/albedo texture path" )
@click.option( "--normal-texture", default=None, help="Normal map texture path" )
@click.option( "--roughness-texture", default=None, help="Roughness texture path" )
@click.option( "--metalness", type=float, default=0.0, help="Metalness (0-1)" )
@click.option( "--tint", default="1 1 1 0", help="Color tint (r g b a)" )
@click.option( "-o", "--output", "output_path", default=None, help="Output .vmat file path" )
@click.pass_context
def material_new( ctx, name, shader, color_texture, normal_texture, roughness_texture, metalness, tint, output_path ):
    """Create a new material."""
    try:
        result = material_mod.create_material(
            name, shader=shader, color_texture=color_texture,
            normal_texture=normal_texture, roughness_texture=roughness_texture,
            metalness=metalness, tint=tint, output_path=output_path,
        )
        _output( ctx, result, lambda d: f"Material '{d['name']}' created" + (f" at {d.get('path', 'stdout')}" if d.get('path') else "") )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@material.command( "info" )
@click.argument( "material_path" )
@click.pass_context
def material_info( ctx, material_path ):
    """Show material properties."""
    try:
        result = material_mod.parse_material( material_path )
        _output( ctx, result, lambda d: _format_status_block( d, f"Material: {d['name']}" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@material.command( "list" )
@click.pass_context
def material_list( ctx ):
    """List materials in the project."""
    try:
        project_dir = _resolve_project_dir( ctx )
        if not project_dir:
            _output_error( ctx, "No project found" )
            return
        result = material_mod.list_materials( project_dir )
        _output( ctx, result )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@material.command( "set" )
@click.argument( "material_path" )
@click.option( "--shader", default=None, help="New shader" )
@click.option( "--color-texture", default=None, help="New color texture path" )
@click.option( "--normal-texture", default=None, help="New normal texture path" )
@click.option( "--metalness", type=float, default=None, help="New metalness (0-1)" )
@click.option( "--tint", default=None, help="New tint (r g b a)" )
@click.pass_context
def material_set( ctx, material_path, shader, color_texture, normal_texture, metalness, tint ):
    """Update properties of an existing material."""
    try:
        result = material_mod.update_material(
            material_path, shader=shader, color_texture=color_texture,
            normal_texture=normal_texture, metalness=metalness, tint=tint,
        )
        _output( ctx, result, lambda d: f"Material '{d['name']}' updated" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# sound group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def sound( ctx ):
    """Manage s&box sound events."""
    pass


@sound.command( "new" )
@click.option( "--name", required=True, help="Sound event name" )
@click.option( "--sounds", default=None, help="Comma-separated .vsnd paths" )
@click.option( "--volume", default="1", help="Volume (0-1)" )
@click.option( "--pitch", default="1", help="Pitch multiplier" )
@click.option( "--decibels", type=int, default=70, help="Loudness in dB" )
@click.option( "--ui/--no-ui", default=False, help="UI sound (no spatialization)" )
@click.option( "-o", "--output", "output_path", default=None, help="Output .sound file path" )
@click.pass_context
def sound_new( ctx, name, sounds, volume, pitch, decibels, ui, output_path ):
    """Create a new sound event."""
    try:
        sound_list = [s.strip() for s in sounds.split(",")] if sounds else []
        result = sound_mod.create_sound_event(
            name, sounds=sound_list, volume=volume, pitch=pitch,
            decibels=decibels, is_ui=ui, output_path=output_path,
        )
        _output( ctx, result, lambda d: f"Sound '{d['name']}' created" + (f" at {d.get('path', '')}" if d.get('path') else "") )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@sound.command( "info" )
@click.argument( "sound_path" )
@click.pass_context
def sound_info( ctx, sound_path ):
    """Show sound event details."""
    try:
        result = sound_mod.parse_sound_event( sound_path )
        _output( ctx, result, lambda d: _format_status_block( d, f"Sound: {d['name']}" ) )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@sound.command( "list" )
@click.pass_context
def sound_list( ctx ):
    """List sound events in the project."""
    try:
        project_dir = _resolve_project_dir( ctx )
        if not project_dir:
            _output_error( ctx, "No project found" )
            return
        from cli_anything.sbox.core import export as export_mod_local
        assets = export_mod_local.list_assets( project_dir, asset_type="sound" )
        _output( ctx, assets )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@sound.command( "set" )
@click.argument( "sound_path" )
@click.option( "--sounds", default=None, help="Comma-separated .vsnd paths (replaces all)" )
@click.option( "--volume", default=None, help="Volume (0-1)" )
@click.option( "--pitch", default=None, help="Pitch multiplier" )
@click.option( "--decibels", type=int, default=None, help="Loudness in dB" )
@click.option( "--is-ui/--no-is-ui", "is_ui", default=None, help="Mark sound as UI (skips occlusion/positional audio)" )
@click.option( "--occlusion/--no-occlusion", "occlusion", default=None, help="Enable occlusion calculations" )
@click.pass_context
def sound_set( ctx, sound_path, sounds, volume, pitch, decibels, is_ui, occlusion ):
    """Update properties of an existing sound event."""
    try:
        sound_list_parsed = [s.strip() for s in sounds.split( "," )] if sounds is not None else None
        result = sound_mod.update_sound_event(
            sound_path, sounds=sound_list_parsed, volume=volume,
            pitch=pitch, decibels=decibels, is_ui=is_ui, occlusion=occlusion,
        )
        _output( ctx, result, lambda d: f"Sound '{d['name']}' updated" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# localization group
# ---------------------------------------------------------------------------


@cli.group()
@click.pass_context
def localization( ctx ):
    """Manage translation files."""
    pass


@localization.command( "new" )
@click.option( "--lang", default="en", help="Language code" )
@click.option( "-o", "--output", "output_path", default=None, help="Output .json file path" )
@click.pass_context
def localization_new( ctx, lang, output_path ):
    """Create a new translation file."""
    try:
        result = localization_mod.create_translation_file( lang=lang, output_path=output_path )
        _output( ctx, result, lambda d: f"Translation file ({d['lang']}) created" + (f" at {d.get('path', '')}" if d.get('path') else "") )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@localization.command( "list" )
@click.argument( "file_path" )
@click.pass_context
def localization_list( ctx, file_path ):
    """List translation keys."""
    try:
        keys = localization_mod.list_keys( file_path )
        _output( ctx, keys )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@localization.command( "set" )
@click.argument( "file_path" )
@click.option( "--key", required=True, help="Translation key" )
@click.option( "--value", required=True, help="Translation value" )
@click.pass_context
def localization_set( ctx, file_path, key, value ):
    """Set a translation key-value pair."""
    try:
        result = localization_mod.set_key( file_path, key, value )
        _output( ctx, {"key": key, "value": value, "total_keys": len( result )}, lambda d: f"Set '{d['key']}' = '{d['value']}' ({d['total_keys']} keys total)" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@localization.command( "get" )
@click.argument( "file_path" )
@click.option( "--key", required=True, help="Translation key" )
@click.pass_context
def localization_get( ctx, file_path, key ):
    """Get a translation value by key."""
    try:
        value = localization_mod.get_key( file_path, key )
        if value is None:
            _output_error( ctx, f"Key '{key}' not found" )
            return
        _output( ctx, {"key": key, "value": value}, lambda d: f"{d['key']} = {d['value']}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@localization.command( "remove" )
@click.argument( "file_path" )
@click.option( "--key", required=True, help="Translation key to remove" )
@click.pass_context
def localization_remove( ctx, file_path, key ):
    """Remove a translation key."""
    try:
        removed = localization_mod.remove_key( file_path, key )
        result = {"key": key, "removed": removed}
        _output( ctx, result, lambda d: f"Key '{d['key']}' {'removed' if d['removed'] else 'not found'}" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@localization.command( "bulk-set" )
@click.argument( "file_path" )
@click.option( "--keys", required=True, help="Key-value pairs as JSON object" )
@click.pass_context
def localization_bulk_set( ctx, file_path, keys ):
    """Set multiple translation keys at once."""
    try:
        keys_dict = json.loads( keys )
        result = localization_mod.bulk_set( file_path, keys_dict )
        _output( ctx, {"total_keys": len( result ), "added": len( keys_dict )}, lambda d: f"Set {d['added']} keys ({d['total_keys']} total)" )
    except click.ClickException:
        raise
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# launch command
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def launch( ctx ):
    """Open project in the s&box editor."""
    try:
        sbproj = _resolve_project_path( ctx )
        project_arg = sbproj if sbproj else None
        proc = sbox_backend.launch_editor( project_path=project_arg )
        result = {"pid": proc.pid, "project": project_arg, "status": "launched"}
        _output( ctx, result, lambda d: f"s&box editor launched (PID {d['pid']})" )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# session group
# ---------------------------------------------------------------------------


@cli.group( "session" )
@click.pass_context
def session_group( ctx ):
    """Manage CLI session state."""
    pass


@session_group.command( "status" )
@click.pass_context
def session_status( ctx ):
    """Show session state."""
    try:
        sess = session_mod.Session()
        result = sess.get_status()
        _output( ctx, result, lambda d: _format_status_block( d, "Session Status" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@session_group.command( "undo" )
@click.pass_context
def session_undo( ctx ):
    """Undo last operation."""
    try:
        sess = session_mod.Session()
        result = sess.undo()
        if result:
            _output( ctx, result, lambda d: f"Undone: {d.get( 'description', '(no description)' )}" )
        else:
            msg = {"message": "Nothing to undo"}
            _output( ctx, msg, lambda d: d["message"] )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@session_group.command( "redo" )
@click.pass_context
def session_redo( ctx ):
    """Redo last undone operation."""
    try:
        sess = session_mod.Session()
        result = sess.redo()
        if result:
            _output( ctx, result, lambda d: f"Redone: {d.get( 'description', '(no description)' )}" )
        else:
            msg = {"message": "Nothing to redo"}
            _output( ctx, msg, lambda d: d["message"] )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# test group
# ---------------------------------------------------------------------------


@cli.group( "test" )
@click.pass_context
def test_group( ctx ):
    """Run automated map generation tests."""
    pass


@test_group.command( "setup" )
@click.pass_context
def test_setup( ctx ):
    """First-run setup: verify paths, create test scene."""
    try:
        sbox_install = sbox_backend.find_sbox_installation()
        sbproj = _resolve_project_path( ctx )
        if not sbproj:
            raise click.ClickException( "No .sbproj found." )

        info = project_mod.get_project_info( sbproj )
        ident = info.get( "ident", "hold_the_line" )

        data_path = test_mod.resolve_data_path( sbox_install, ident )

        result = {
            "sbox_install": sbox_install,
            "data_path": data_path,
            "sbproj": sbproj,
            "ident": ident,
            "status": "ready",
        }
        _output( ctx, result, lambda d: _format_status_block( d, "Test Setup" ) )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


@test_group.command( "run" )
@click.option( "--strategies", default=None, help="Comma-separated strategies (default: all)" )
@click.option( "--sizes", default=None, help="Comma-separated sizes (default: all)" )
@click.option( "--seeds", default=None, help="Comma-separated seed values" )
@click.option( "--seed-count", type=int, default=1, help="Number of random seeds per combo" )
@click.option( "--timeout", type=float, default=60.0, help="Timeout per combo in seconds" )
@click.pass_context
def test_run( ctx, strategies, sizes, seeds, seed_count, timeout ):
    """Run map generation tests across strategy/size/seed combos."""
    try:
        sbox_install = sbox_backend.find_sbox_installation()
        sbproj = _resolve_project_path( ctx )
        if not sbproj:
            raise click.ClickException( "No .sbproj found." )

        info = project_mod.get_project_info( sbproj )
        ident = info.get( "ident", "hold_the_line" )
        data_path = test_mod.resolve_data_path( sbox_install, ident )

        project_dir = os.path.dirname( sbproj )
        output_dir = os.path.join( project_dir, "test-results" )
        os.makedirs( os.path.join( output_dir, "screenshots" ), exist_ok=True )
        os.makedirs( os.path.join( output_dir, "reports" ), exist_ok=True )

        parsed_strategies = strategies.split( "," ) if strategies else None
        parsed_sizes = sizes.split( "," ) if sizes else None
        parsed_seeds = [int( s ) for s in seeds.split( "," )] if seeds else None

        results = test_mod.run_test_pipeline(
            sbproj_path=sbproj,
            data_path=data_path,
            output_dir=output_dir,
            strategies=parsed_strategies,
            sizes=parsed_sizes,
            seeds=parsed_seeds,
            seed_count=seed_count,
            timeout=timeout,
        )

        succeeded = sum( 1 for r in results if r["success"] )
        failed = sum( 1 for r in results if not r["success"] )

        summary = {
            "total": len( results ),
            "succeeded": succeeded,
            "failed": failed,
            "screenshots": [r["png_path"] for r in results if r.get( "png_path" )],
            "failures": [
                {"combo": r["combo"], "error": r["error"]}
                for r in results if not r["success"]
            ],
        }

        _output( ctx, summary, lambda d: _format_status_block( d, "Test Run Complete" ) )
        # Partial-failure: scripts/agents need a non-zero exit when any combo
        # fails, otherwise the summary is misleading (printed N failures, exit 0).
        if failed > 0 and not ctx.obj.get( "repl" ):
            sys.exit( 1 )
    except Exception as exc:
        _output_error( ctx, str( exc ) )


# ---------------------------------------------------------------------------
# repl command
# ---------------------------------------------------------------------------


_REPL_BANNER = """
  ___  _  _____  __  __  ___ _    ___
 / __|| |/ _ \\ \\/ / / _|| | |_ _|
 \\__ \\| | (_) >  < | (__ | |_ | |
 |___/|_|\\___/_/\\_\\ \\___||___|___|

 cli-anything-sbox - interactive REPL
 Type 'help' for commands, 'quit' to exit.
"""

_REPL_HELP = """Available command groups:
  project      - Manage s&box projects (new, info, config, add-package, remove-package, validate)
  scene        - Manage scenes (new, info, list, add-object, remove-object, add-component,
                   remove-component, modify-object, set-property, clone-object, get-object,
                   set-navmesh, list-presets, modify-component, query, refs, bulk-modify,
                   diff, instantiate-prefab)
  prefab       - Manage prefabs (new, info, from-scene, add-component, remove-component, list,
                   refs, modify-component, diff)
  codegen      - Generate C# code (component, gameresource, editor-menu, razor, class,
                   panel-component)
  input        - Manage input bindings (list, add, remove, set)
  collision    - Manage collision layers (list, add-layer, add-rule, remove-rule, remove-layer)
  material     - Manage materials (new, info, list, set)
  sound        - Manage sound events (new, info, list, set)
  localization - Manage translation files (new, list, set, get, remove, bulk-set)
  server       - Server management (start, info)
  asset        - Asset management (list, info, compile, find-refs, find-unused, rename, move)
  session      - Session state (status, undo, redo)
  test         - Run automated map generation tests (setup, run)
  launch       - Open project in s&box editor

  help         - Show this help
  quit/exit    - Exit the REPL

Example: project info
         scene list Assets/scenes/minimal.scene
         codegen component --name PlayerMovement --methods OnUpdate,OnStart
"""


@cli.command()
@click.pass_context
def repl( ctx ):
    """Enter interactive REPL mode."""
    # Mark REPL mode so _output_error prints + returns instead of sys.exit(1).
    # Shared via obj=ctx.obj on the inner cli invocation below so child
    # commands see the same flag.
    ctx.obj["repl"] = True

    try:
        from cli_anything.sbox.utils.repl_skin import ReplSkin
        skin = ReplSkin( "sbox", version="1.0.0" )
    except (ImportError, TypeError):
        skin = None

    def echo( msg ):
        if skin and hasattr( skin, "info" ):
            skin.info( msg )
        else:
            click.echo( msg )

    def echo_error( msg ):
        if skin and hasattr( skin, "error" ):
            skin.error( msg )
        else:
            click.echo( f"Error: {msg}", err=True )

    echo( _REPL_BANNER )

    while True:
        try:
            line = click.prompt( "sbox", prompt_suffix="> ", default="", show_default=False )
        except (EOFError, KeyboardInterrupt):
            echo( "\nBye!" )
            break

        line = line.strip()
        if not line:
            continue

        if line in ( "quit", "exit" ):
            echo( "Bye!" )
            break

        if line == "help":
            echo( _REPL_HELP )
            continue

        # Parse the line and dispatch to Click
        try:
            args = shlex.split( line )
        except ValueError as exc:
            echo_error( f"Invalid input: {exc}" )
            continue

        # Carry forward the global context options
        extra_args = []
        if ctx.obj.get( "json" ):
            extra_args.append( "--json" )
        project_path = ctx.obj.get( "project_path" )
        if project_path:
            extra_args.extend( ["--project", project_path] )

        try:
            cli( extra_args + args, standalone_mode=False, obj=ctx.obj )
        except SystemExit:
            # Click may raise SystemExit on --help or errors; absorb it in REPL mode
            pass
        except click.ClickException as exc:
            echo_error( exc.format_message() )
        except click.Abort:
            echo_error( "Command aborted." )
        except Exception as exc:
            echo_error( str( exc ) )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
