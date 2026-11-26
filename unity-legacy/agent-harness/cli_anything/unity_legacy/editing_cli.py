"""Editing commands for the Unity 2020.3 CLI.

Adds the mutating ``scene``, ``gameobject``, ``component``, ``prefab`` and
``asset`` subcommands to groups created by :mod:`unity_legacy_cli`. Every command
requires Edit Mode, refuses to touch dirty scenes or assets unless the caller
opts in, and relies on the C# side for Undo registration and validation.

Deferred here: prefab contents editing without a prefab stage, asset deletion
and creation, scene templates beyond ``empty``/``default``, moving GameObjects
between scenes, and object-reference component property values.
"""

import json

import click

ENTITY_TARGET_HELP = "GameObject instance ID."


def _payload(**values):
    """Drop unset options so the C# side sees only explicit arguments."""
    return {name: value for name, value in values.items() if value is not None}


def _target(object_id, path, scene_path=None):
    return _payload(ObjectId=object_id, Path=path, ScenePath=scene_path)


def _vector(text, length, label):
    """Parse ``x,y,z``, ``x y z`` or a JSON array into a list of floats."""
    if isinstance(text, (list, tuple)):
        values = list(text)
    else:
        stripped = text.strip()
        if stripped.startswith("["):
            try:
                values = json.loads(stripped)
            except ValueError as error:
                raise click.BadParameter(
                    "expected a JSON array or " + str(length) + " numbers: " + str(error))
        else:
            parts = stripped.replace(",", " ").split()
            try:
                values = [float(part) for part in parts]
            except ValueError:
                raise click.BadParameter("expected " + str(length) + " numbers, got: " + text)
    if not isinstance(values, (list, tuple)) or len(values) != length:
        raise click.BadParameter(
            label + " requires exactly " + str(length) + " numbers in order X Y" +
            (" Z" if length == 3 else "") + (" W" if length == 4 else "") + ".")
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError):
        raise click.BadParameter(label + " requires numeric values.")


def _position(text):
    return _vector(text, 3, "--position")


def _rotation(text):
    return _vector(text, 3, "--rotation")


def _scale(text):
    return _vector(text, 3, "--scale")


def _offset(text):
    return _vector(text, 3, "--offset")


def _property_value(text):
    """Accept JSON (numbers, arrays, booleans) or a plain string."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _exact_number_text(text):
    """Return the literal when the whole argument is one JSON number.

    ``json.loads`` turns a fractional literal into a binary double, which loses
    digits for wide types such as ``decimal``. The bridge prefers this literal
    over the parsed token when the target needs every typed digit.
    """
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except ValueError:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return stripped


def _require_target(object_id, path, command):
    if object_id is None and not path:
        raise click.BadParameter(
            "provide --id or --path for " + command + ".", param_hint="--id/--path")


def register(cli, run):
    """Attach editing subcommands to the groups created by ``unity_legacy_cli``."""
    scene = cli.commands["scene"]
    gameobject = cli.commands["gameobject"]
    component = cli.commands["component"]
    prefab = cli.commands["prefab"]
    asset = cli.commands["asset"]

    @scene.command("create")
    @click.argument("asset_path")
    @click.option("--template", type=click.Choice(["default", "empty"]), default="default",
                  show_default=True, help="Scene contents; default adds a camera and a light.")
    @click.option("--additive", is_flag=True,
                  help="Keep the open scenes loaded instead of closing clean ones after saving.")
    @click.pass_context
    def scene_create(ctx, asset_path, template, additive):
        """Create and save a scene, then make it active. Requires Edit Mode.

        Refuses to replace open scenes that have unsaved changes; the new scene
        is saved before any previous scene is closed, so a failed save changes nothing.
        """
        run(ctx, "scene.create", AssetPath=asset_path, Template=template, Additive=additive)

    @scene.command("close")
    @click.argument("scene_path")
    @click.option("--keep-loaded", is_flag=True,
                  help="Unload the scene but keep its entry in the hierarchy.")
    @click.pass_context
    def scene_close(ctx, scene_path, keep_loaded):
        """Close an open scene. Requires Edit Mode and a saved scene.

        Refuses dirty scenes and the only remaining scene. Closing is not undoable.
        """
        run(ctx, "scene.close", ScenePath=scene_path, RemoveScene=not keep_loaded)

    @scene.command("set-active")
    @click.argument("scene_path")
    @click.pass_context
    def scene_set_active(ctx, scene_path):
        """Make an already open scene the active scene for new objects."""
        run(ctx, "scene.set-active", ScenePath=scene_path)

    @gameobject.command("create")
    @click.argument("name", required=False)
    @click.option("--primitive", "primitive_type",
                  type=click.Choice(["Cube", "Sphere", "Capsule", "Cylinder", "Plane", "Quad"]),
                  help="Create a Unity primitive mesh instead of an empty GameObject.")
    @click.option("--prefab", "prefab_path", help="Assets/... prefab asset to instantiate.")
    @click.option("--parent-id", type=int, help="Parent GameObject instance ID.")
    @click.option("--parent-path", help="Parent hierarchy path.")
    @click.option("--position", callback=lambda ctx, param, value: None if value is None else _position(value),
                  help="World position as X Y Z.")
    @click.option("--rotation", callback=lambda ctx, param, value: None if value is None else _rotation(value),
                  help="World Euler rotation in degrees as X Y Z.")
    @click.option("--scale", callback=lambda ctx, param, value: None if value is None else _scale(value),
                  help="Local scale as X Y Z.")
    @click.option("--inactive", is_flag=True, help="Create the object inactive.")
    @click.pass_context
    def gameobject_create(ctx, name, primitive_type, prefab_path, parent_id, parent_path,
                          position, rotation, scale, inactive):
        """Create an empty GameObject, primitive or prefab instance under Undo.

        Requires Edit Mode. Provide NAME, --primitive or --prefab.
        """
        if not name and not primitive_type and not prefab_path:
            raise click.UsageError("provide NAME, --primitive or --prefab.")
        if primitive_type and prefab_path:
            raise click.UsageError("--primitive and --prefab are mutually exclusive.")
        run(ctx, "gameobject.create", **_payload(
            Name=name,
            PrimitiveType=primitive_type,
            PrefabPath=prefab_path,
            ParentId=parent_id,
            ParentPath=parent_path,
            Position=position,
            Rotation=rotation,
            Scale=scale,
            Active=False if inactive else None,
        ))

    @gameobject.command("rename")
    @click.argument("name")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.pass_context
    def gameobject_rename(ctx, name, object_id, path, scene_path):
        """Rename a scene object under Undo. Requires Edit Mode and --id or --path."""
        _require_target(object_id, path, "gameobject rename")
        run(ctx, "gameobject.rename", **_target(object_id, path, scene_path), Name=name)

    @gameobject.command("transform")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--position", callback=lambda ctx, param, value: None if value is None else _position(value),
                  help="World position as X Y Z.")
    @click.option("--rotation", callback=lambda ctx, param, value: None if value is None else _rotation(value),
                  help="World Euler rotation in degrees as X Y Z.")
    @click.option("--scale", callback=lambda ctx, param, value: None if value is None else _scale(value),
                  help="Local scale as X Y Z.")
    @click.option("--active/--inactive", "active", default=None,
                  help="Toggle the object's own active state.")
    @click.pass_context
    def gameobject_transform(ctx, object_id, path, scene_path, position, rotation, scale, active):
        """Change position, rotation, scale or active state under Undo.

        Requires Edit Mode and at least one change. Position is world space;
        rotation is world Euler degrees; scale is local.
        """
        _require_target(object_id, path, "gameobject transform")
        if position is None and rotation is None and scale is None and active is None:
            raise click.UsageError("provide --position, --rotation, --scale, --active or --inactive.")
        run(ctx, "gameobject.transform", **_target(object_id, path, scene_path), **_payload(
            Position=position,
            Rotation=rotation,
            Scale=scale,
            Active=active,
        ))

    @gameobject.command("duplicate")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--name", "new_name", help="Name for the copy; defaults to Unity's unique sibling name.")
    @click.option("--offset", callback=lambda ctx, param, value: None if value is None else _offset(value),
                  help="Local position offset as X Y Z.")
    @click.pass_context
    def gameobject_duplicate(ctx, object_id, path, scene_path, new_name, offset):
        """Duplicate a scene object with its children under Undo.

        Prefab instance roots are copied from their prefab asset, other objects
        are cloned. Requires Edit Mode and --id or --path.
        """
        _require_target(object_id, path, "gameobject duplicate")
        run(ctx, "gameobject.duplicate", **_target(object_id, path, scene_path), **_payload(
            NewName=new_name,
            Offset=offset,
        ))

    @gameobject.command("delete")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.confirmation_option(prompt="Delete this GameObject and all of its children?")
    @click.pass_context
    def gameobject_delete(ctx, object_id, path, scene_path):
        """Delete a scene object and its full hierarchy under Undo.

        Requires Edit Mode and an explicit --id or --path, plus confirmation.
        The whole hierarchy is restored by a single Undo.
        """
        _require_target(object_id, path, "gameobject delete")
        run(ctx, "gameobject.delete", **_target(object_id, path, scene_path))

    @component.command("add")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--component", "component_type", required=True,
                  help="Component short name or full type name, for example BoxCollider.")
    @click.pass_context
    def component_add(ctx, object_id, path, scene_path, component_type):
        """Add a component under Undo. Requires Edit Mode.

        Transform components are rejected because Unity owns them.
        """
        _require_target(object_id, path, "component add")
        run(ctx, "component.add", **_target(object_id, path, scene_path), ComponentType=component_type)

    @component.command("remove")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--component", "component_type", required=True,
                  help="Component short name or full type name.")
    @click.option("--index", type=click.IntRange(0), help="Which copy to remove when several exist.")
    @click.pass_context
    def component_remove(ctx, object_id, path, scene_path, component_type, index):
        """Remove a component under Undo. Requires Edit Mode.

        Refuses Transform and requires --index when the object has several
        components of the requested type.
        """
        _require_target(object_id, path, "component remove")
        run(ctx, "component.remove", **_target(object_id, path, scene_path), **_payload(
            ComponentType=component_type,
            Index=index,
        ))

    @component.command("set")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--component", "component_type", required=True,
                  help="Component short name or full type name.")
    @click.option("--property", "property_name", required=True,
                  help="Public writable property or field, for example m_Mass or localScale.")
    @click.option("--value", "value", required=True,
                  help="JSON scalar or array, or a plain string; vectors accept 'x,y,z'. "
                       "Object references and collections are rejected.")
    @click.option("--index", type=click.IntRange(0), help="Which copy to edit when several exist.")
    @click.pass_context
    def component_set(ctx, object_id, path, scene_path, component_type, property_name, value, index):
        """Set a primitive, enum, vector, colour or bounds property under Undo.

        Requires Edit Mode. Object references, arrays and collections are rejected
        with an explicit error rather than guessed.
        """
        _require_target(object_id, path, "component set")
        run(ctx, "component.set", **_target(object_id, path, scene_path), **_payload(
            ComponentType=component_type,
            Property=property_name,
            Value=_property_value(value),
            ValueText=_exact_number_text(value),
            Index=index,
        ))

    @prefab.command("create")
    @click.argument("asset_path")
    @click.option("--id", "object_id", type=int, help=ENTITY_TARGET_HELP)
    @click.option("--path", help="Hierarchy path of the object.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--overwrite", is_flag=True, help="Replace an existing prefab asset.")
    @click.pass_context
    def prefab_create(ctx, asset_path, object_id, path, scene_path, overwrite):
        """Save a scene object as a prefab and connect the scene instance.

        Requires Edit Mode and --id or --path. Refuses an existing asset unless
        --overwrite is passed; the save itself is not undoable.
        """
        _require_target(object_id, path, "prefab create")
        run(ctx, "prefab.create", **_target(object_id, path, scene_path), **_payload(
            AssetPath=asset_path,
            Overwrite=overwrite or None,
        ))

    @prefab.command("stage-open")
    @click.argument("asset_path")
    @click.pass_context
    def prefab_stage_open(ctx, asset_path):
        """Enter Prefab Mode for an Assets/... prefab. Requires Edit Mode.

        Refuses to replace a different prefab stage that has unsaved changes.
        """
        run(ctx, "prefab.stage-open", AssetPath=asset_path)

    @prefab.command("stage-save")
    @click.pass_context
    def prefab_stage_save(ctx):
        """Save the open prefab stage to its asset. Requires Edit Mode and an open stage."""
        run(ctx, "prefab.stage-save")

    @prefab.command("stage-close")
    @click.option("--discard", is_flag=True, help="Discard unsaved stage changes.")
    @click.pass_context
    def prefab_stage_close(ctx, discard):
        """Leave Prefab Mode. Requires Edit Mode and an open stage.

        Refuses unsaved changes unless --discard is passed.
        """
        run(ctx, "prefab.stage-close", **_payload(Discard=discard or None))

    @asset.command("import")
    @click.argument("asset_path")
    @click.option("--recursive", is_flag=True, help="Import a folder's contents as well.")
    @click.pass_context
    def asset_import(ctx, asset_path, recursive):
        """Force a synchronous reimport of one asset or folder."""
        run(ctx, "asset.import", **_payload(AssetPath=asset_path, Recursive=recursive or None))

    @asset.command("move")
    @click.argument("source_path")
    @click.argument("destination_path")
    @click.pass_context
    def asset_move(ctx, source_path, destination_path):
        """Move or rename an asset or folder, keeping its GUID.

        Refuses loaded scenes, the open prefab stage asset, missing sources,
        existing destinations and missing destination folders.
        """
        run(ctx, "asset.move", SourcePath=source_path, DestinationPath=destination_path)
