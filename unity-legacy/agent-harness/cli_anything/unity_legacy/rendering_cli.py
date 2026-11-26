"""Profiler, graphics, material, particle, animator and physics commands for the Unity 2020.3 CLI.

Owns the ``profiler.*``, ``graphics.*``, ``material.*``, ``particle.*``,
``animator.*``, ``physics.*`` and ``primitive.*`` command families. Everything
here is read-only except ``profiler start/stop``, ``material create/set`` and
``primitive create``, which are explicit invocations.
"""

import click


def _payload(**values):
    """Drop unset options so the C# side sees only explicit arguments."""
    return {name: value for name, value in values.items() if value is not None}


def _target(object_id, path, scene_path=None):
    return _payload(ObjectId=object_id, Path=path, ScenePath=scene_path)


def _parse_value(text):
    """Turn a CLI string into the JSON shape the C# typed setter expects."""
    raw = (text or "").strip()
    if raw == "":
        return ""
    if "," in raw:
        parts = [part.strip() for part in raw.split(",")]
        try:
            return [float(part) for part in parts]
        except ValueError:
            return raw
    try:
        return float(raw)
    except ValueError:
        return raw


def _properties(pairs):
    properties = {}
    for pair in pairs or ():
        if "=" not in pair:
            raise click.BadParameter(f"Use NAME=VALUE, got '{pair}'.")
        name, text = pair.split("=", 1)
        name = name.strip()
        if not name:
            raise click.BadParameter("Property name must not be empty.")
        properties[name] = _parse_value(text)
    return properties


def _layer_options(command):
    command = click.option("--layer", "layer_mask_name", help="Layer name or comma separated names.")(command)
    command = click.option("--layer-mask", type=int, help="Raw layer mask; omit for every layer.")(command)
    return command


def _target_options(command):
    command = click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")(command)
    command = click.option("--path", help="Hierarchy path, for example SampleScene/Main Camera.")(command)
    command = click.option("--id", "object_id", type=int, help="GameObject instance ID.")(command)
    return command


def register(cli, run):
    @cli.group()
    def profiler():
        """Inspect the editor profiler, toggle capture and report Frame Debugger availability."""

    @profiler.command("status")
    @click.pass_context
    def profiler_status(ctx):
        """Report profiler state, packages and optional performance tools."""
        run(ctx, "profiler.status")

    @profiler.command("start")
    @click.pass_context
    def profiler_start(ctx):
        """Start editor profiling (Profiler window capture)."""
        run(ctx, "profiler.start")

    @profiler.command("stop")
    @click.pass_context
    def profiler_stop(ctx):
        """Stop editor profiling."""
        run(ctx, "profiler.stop")

    @profiler.command("frame-debugger")
    @click.option("--action", type=click.Choice(["status", "enable", "disable"]), default="status",
                  show_default=True, help="Toggle the Frame Debugger when the editor exposes a managed API.")
    @click.pass_context
    def profiler_frame_debugger(ctx, action):
        """Query or toggle the Frame Debugger."""
        run(ctx, "profiler.frame-debugger", Action=action)

    @cli.group()
    def graphics():
        """Inspect render pipeline, quality, device and lighting settings."""

    @graphics.command("settings")
    @click.pass_context
    def graphics_settings(ctx):
        """Report the render pipeline, quality level, device caps, render and shader settings."""
        run(ctx, "graphics.settings")

    @graphics.command("lighting")
    @click.pass_context
    def graphics_lighting(ctx):
        """Report lightmapping state, lighting settings, lights and probes."""
        run(ctx, "graphics.lighting")

    @cli.group()
    def material():
        """List, inspect, create and edit materials."""

    @material.command("list")
    @click.option("--filter", default="", help="Case-insensitive renderer name filter.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @click.pass_context
    def material_list(ctx, filter, limit):
        """List renderers with their material slots."""
        run(ctx, "material.list", **_payload(Filter=filter, Limit=limit))

    @material.command("inspect")
    @_target_options
    @click.option("--asset", "asset_path", help="Material asset path instead of a renderer target.")
    @click.option("--slot", type=click.IntRange(0, 63), default=0, show_default=True,
                  help="Renderer material slot used when a target is given.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=200, show_default=True,
                  help="Maximum shader properties returned.")
    @click.pass_context
    def material_inspect(ctx, object_id, path, scene_path, asset_path, slot, limit):
        """Inspect a material asset or one slot of a renderer."""
        run(ctx, "material.inspect", **_target(object_id, path, scene_path),
            **_payload(AssetPath=asset_path, Slot=slot, Limit=limit))

    @material.command("create")
    @click.argument("asset_path")
    @click.option("--shader", required=True, help="Shader name, for example Standard or Universal Render Pipeline/Lit.")
    @click.option("-p", "--property", "property_pairs", multiple=True, metavar="NAME=VALUE",
                  help="Shader property to apply; repeatable. Arrays use commas, e.g. -p _BaseColor=1,0,0,1.")
    @click.pass_context
    def material_create(ctx, asset_path, shader, property_pairs):
        """Create a .mat asset under Assets/. Requires Edit Mode."""
        run(ctx, "material.create", **_payload(AssetPath=asset_path, Shader=shader,
                                               Properties=_properties(property_pairs) or None))

    @material.command("set")
    @click.argument("asset_path")
    @click.option("--property", required=True, help="Shader property name, for example _BaseColor.")
    @click.option("--value", required=True,
                  help="Number for float/range, comma list for colour/vector, texture path, or empty for none.")
    @click.pass_context
    def material_set(ctx, asset_path, property, value):
        """Set one shader property on a material asset and save it."""
        run(ctx, "material.set", **_payload(AssetPath=asset_path, Property=property, Value=_parse_value(value)))

    @cli.group()
    def particle():
        """List and inspect particle systems, line renderers, trail renderers and VFX components."""

    @particle.command("list")
    @click.option("--filter", default="", help="Case-insensitive GameObject name filter.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @click.pass_context
    def particle_list(ctx, filter, limit):
        """List particle systems and count the other effect renderers."""
        run(ctx, "particle.list", **_payload(Filter=filter, Limit=limit))

    @particle.command("inspect")
    @_target_options
    @click.option("--component-index", type=click.IntRange(0, 63), default=0, show_default=True,
                  help="ParticleSystem component index when a GameObject has several.")
    @click.pass_context
    def particle_inspect(ctx, object_id, path, scene_path, component_index):
        """Show every particle module plus the renderer and linked line/trail renderers."""
        run(ctx, "particle.inspect", **_target(object_id, path, scene_path),
            **_payload(ComponentIndex=component_index))

    @cli.group()
    def animator():
        """List and inspect Animator controllers, parameters, layers and states."""

    @animator.command("list")
    @click.option("--filter", default="", help="Case-insensitive GameObject name filter.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @click.pass_context
    def animator_list(ctx, filter, limit):
        """List Animators and legacy Animation components in the loaded scenes."""
        run(ctx, "animator.list", **_payload(Filter=filter, Limit=limit))

    @animator.command("inspect")
    @_target_options
    @click.option("--component-index", type=click.IntRange(0, 63), default=0, show_default=True,
                  help="Animator component index when a GameObject has several.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=200, show_default=True,
                  help="Maximum controller states returned.")
    @click.pass_context
    def animator_inspect(ctx, object_id, path, scene_path, component_index, limit):
        """Show the Animator, avatar, controller layers, states, transitions and live values."""
        run(ctx, "animator.inspect", **_target(object_id, path, scene_path),
            **_payload(ComponentIndex=component_index, Limit=limit))

    @cli.group()
    def physics():
        """Inspect physics settings and query colliders with raycasts and overlaps."""

    @physics.command("settings")
    @click.pass_context
    def physics_settings(ctx):
        """Report Physics and Physics2D project settings and named layers."""
        run(ctx, "physics.settings")

    @physics.command("layers")
    @click.pass_context
    def physics_layers(ctx):
        """Report named layers and the disabled collision matrix pairs."""
        run(ctx, "physics.layers")

    @physics.command("stats")
    @click.pass_context
    def physics_stats(ctx):
        """Count rigidbodies, colliders, joints, controllers and terrains in the loaded scenes."""
        run(ctx, "physics.stats")

    @physics.command("raycast")
    @click.option("--origin", nargs=3, type=float, required=True, help="Ray origin X Y Z.")
    @click.option("--direction", nargs=3, type=float, required=True, help="Ray direction X Y Z.")
    @click.option("--max-distance", type=float, help="Maximum distance; defaults to infinity.")
    @click.option("--all", "all_hits", is_flag=True, default=None, help="Return every hit sorted by distance.")
    @_layer_options
    @click.option("--triggers", type=click.Choice(["Ignore", "Collide", "UseGlobal"]),
                  help="Trigger interaction; defaults to the project setting.")
    @click.pass_context
    def physics_raycast(ctx, origin, direction, max_distance, all_hits, layer_mask, layer_mask_name, triggers):
        """Cast a 3D ray and report the hit collider."""
        run(ctx, "physics.raycast", **_payload(Origin=list(origin), Direction=list(direction),
                                               MaxDistance=max_distance, All=all_hits,
                                               LayerMask=layer_mask, LayerMaskName=layer_mask_name,
                                               Triggers=triggers))

    @physics.command("raycast2d")
    @click.option("--origin", nargs=2, type=float, required=True, help="Ray origin X Y.")
    @click.option("--direction", nargs=2, type=float, required=True, help="Ray direction X Y.")
    @click.option("--max-distance", type=float, help="Maximum distance; defaults to infinity.")
    @click.option("--all", "all_hits", is_flag=True, default=None, help="Return every hit sorted by distance.")
    @_layer_options
    @click.pass_context
    def physics_raycast2d(ctx, origin, direction, max_distance, all_hits, layer_mask, layer_mask_name):
        """Cast a 2D ray and report the hit collider."""
        run(ctx, "physics.raycast2d", **_payload(Origin=list(origin), Direction=list(direction),
                                                 MaxDistance=max_distance, All=all_hits,
                                                 LayerMask=layer_mask, LayerMaskName=layer_mask_name))

    @physics.command("overlap")
    @click.option("--shape", type=click.Choice(["sphere", "box"]), default="sphere", show_default=True)
    @click.option("--position", nargs=3, type=float, required=True, help="Shape centre X Y Z.")
    @click.option("--radius", type=float, help="Sphere radius.")
    @click.option("--size", nargs=3, type=float, help="Box size X Y Z.")
    @click.option("--rotation", nargs=3, type=float, help="Box euler rotation X Y Z.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @_layer_options
    @click.option("--triggers", type=click.Choice(["Ignore", "Collide", "UseGlobal"]),
                  help="Trigger interaction; defaults to the project setting.")
    @click.pass_context
    def physics_overlap(ctx, shape, position, radius, size, rotation, limit, layer_mask, layer_mask_name, triggers):
        """Find colliders intersecting a sphere or box."""
        run(ctx, "physics.overlap", **_payload(Shape=shape, Position=list(position), Radius=radius,
                                               Size=list(size) if size else None,
                                               Rotation=list(rotation) if rotation else None,
                                               Limit=limit, LayerMask=layer_mask,
                                               LayerMaskName=layer_mask_name, Triggers=triggers))

    @physics.command("overlap2d")
    @click.option("--shape", type=click.Choice(["circle", "box"]), default="circle", show_default=True)
    @click.option("--position", nargs=2, type=float, required=True, help="Shape centre X Y.")
    @click.option("--radius", type=float, help="Circle radius.")
    @click.option("--size", nargs=2, type=float, help="Box size X Y.")
    @click.option("--angle", type=float, help="Box rotation in degrees.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @_layer_options
    @click.pass_context
    def physics_overlap2d(ctx, shape, position, radius, size, angle, limit, layer_mask, layer_mask_name):
        """Find 2D colliders intersecting a circle or box."""
        run(ctx, "physics.overlap2d", **_payload(Shape=shape, Position=list(position), Radius=radius,
                                                 Size=list(size) if size else None, Angle=angle,
                                                 Limit=limit, LayerMask=layer_mask,
                                                 LayerMaskName=layer_mask_name))

    @cli.group()
    def primitive():
        """Create built-in primitive GameObjects."""

    @primitive.command("create")
    @click.argument("primitive", type=click.Choice(["cube", "sphere", "capsule", "cylinder", "plane", "quad"],
                                                   case_sensitive=False))
    @click.option("--name", help="GameObject name; defaults to the primitive type.")
    @click.option("--position", nargs=3, type=float, help="World position X Y Z.")
    @click.option("--rotation", nargs=3, type=float, help="World euler rotation X Y Z.")
    @click.option("--scale", nargs=3, type=float, help="Local scale X Y Z.")
    @click.option("--parent-id", type=int, help="Parent GameObject instance ID.")
    @click.option("--parent-path", help="Parent hierarchy path.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --parent-path.")
    @click.pass_context
    def primitive_create(ctx, primitive, name, position, rotation, scale, parent_id, parent_path, scene_path):
        """Create a primitive with its default collider. Requires Edit Mode."""
        run(ctx, "primitive.create", **_payload(
            Type=primitive,
            Name=name,
            Position=list(position) if position else None,
            Rotation=list(rotation) if rotation else None,
            Scale=list(scale) if scale else None,
            ParentId=parent_id,
            ParentPath=parent_path,
            ScenePath=scene_path,
        ))
