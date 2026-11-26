"""Camera and UI commands for the Unity 2020.3 CLI.

Owns the ``camera.*`` and ``ui.*`` command families. Every write path is an
explicit invocation: ``camera set`` mutates a scene camera, ``camera capture``
writes a PNG, ``ui canvas/element create`` and ``ui toolkit create`` create
scene objects or asset files.
"""

import click

PAIR = (float, float)


def _payload(**values):
    """Drop unset options so the C# side sees only explicit arguments."""
    return {name: value for name, value in values.items() if value is not None}


def _target(object_id, path, scene_path=None):
    return _payload(ObjectId=object_id, Path=path, ScenePath=scene_path)


def register(cli, run):
    @cli.group()
    def camera():
        """List, inspect, configure and capture scene cameras."""

    @camera.command("list")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @click.pass_context
    def camera_list(ctx, limit):
        """List cameras in the loaded scenes."""
        run(ctx, "camera.list", Limit=limit)

    @camera.command("inspect")
    @click.option("--id", "object_id", type=int, help="Camera GameObject instance ID.")
    @click.option("--path", help="Hierarchy path of the camera, for example Root/Child/Main Camera.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.pass_context
    def camera_inspect(ctx, object_id, path, scene_path):
        """Show camera settings, transform and Cinemachine presence."""
        run(ctx, "camera.inspect", **_target(object_id, path, scene_path))

    @camera.command("set")
    @click.option("--id", "object_id", type=int, help="Camera GameObject instance ID.")
    @click.option("--path", help="Hierarchy path of the camera.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--enable/--disable", "enabled", default=None, help="Toggle the Camera component.")
    @click.option("--depth", type=float, help="Camera depth in the render order.")
    @click.option("--fov", type=float, help="Perspective vertical field of view in degrees.")
    @click.option("--near", "near_clip", type=float, help="Near clip plane.")
    @click.option("--far", "far_clip", type=float, help="Far clip plane.")
    @click.option("--orthographic/--perspective", "orthographic", default=None)
    @click.option("--orthographic-size", type=float, help="Half height of the orthographic view.")
    @click.option("--clear-flags", type=click.Choice(["Skybox", "SolidColor", "Depth", "Nothing"]))
    @click.option("--background", help="Solid clear colour as RRGGBB or #RRGGBB.")
    @click.pass_context
    def camera_set(ctx, object_id, path, scene_path, enabled, depth, fov, near_clip, far_clip,
                   orthographic, orthographic_size, clear_flags, background):
        """Change camera settings in Edit Mode. Requires an explicit camera target."""
        run(ctx, "camera.set", **_target(object_id, path, scene_path), **_payload(
            Enabled=enabled,
            Depth=depth,
            FieldOfView=fov,
            NearClipPlane=near_clip,
            FarClipPlane=far_clip,
            Orthographic=orthographic,
            OrthographicSize=orthographic_size,
            ClearFlags=clear_flags,
            BackgroundColor=background,
        ))

    @camera.command("capture")
    @click.option("--id", "object_id", type=int, help="Camera GameObject instance ID.")
    @click.option("--path", help="Hierarchy path of the camera.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.option("--width", type=click.IntRange(1, 8192), help="Render width; defaults to the camera pixel width.")
    @click.option("--height", type=click.IntRange(1, 8192), help="Render height; defaults to the camera pixel height.")
    @click.option("--output", "output_path",
                  help="Project-relative PNG path under Assets/ or Temp/. "
                       "Defaults to Temp/UnityCli/captures/.")
    @click.pass_context
    def camera_capture(ctx, object_id, path, scene_path, width, height, output_path):
        """Render the given camera to a verified PNG file."""
        run(ctx, "camera.capture", **_target(object_id, path, scene_path), **_payload(
            Width=width, Height=height, OutputPath=output_path))

    @cli.group()
    def ui():
        """Create and inspect uGUI and UI Toolkit content."""

    @ui.group()
    def canvas():
        """Create uGUI canvases."""

    @canvas.command("create")
    @click.option("--name", default="Canvas", show_default=True)
    @click.option("--parent-id", type=int, help="Parent GameObject instance ID.")
    @click.option("--parent-path", help="Parent hierarchy path.")
    @click.option("--render-mode", type=click.Choice(
        ["ScreenSpaceOverlay", "ScreenSpaceCamera", "WorldSpace"]), default="ScreenSpaceOverlay", show_default=True)
    @click.option("--scaler", type=click.Choice(
        ["ConstantPixelSize", "ScaleWithScreenSize", "ConstantPhysicalSize"]),
        default="ScaleWithScreenSize", show_default=True)
    @click.option("--reference-resolution", type=(int, int), help="Reference resolution as WIDTH HEIGHT.")
    @click.option("--camera-id", type=int, help="World camera GameObject ID, required for ScreenSpaceCamera.")
    @click.option("--match", "match_width_or_height", type=click.FloatRange(0, 1),
                  help="Scale With Screen Size match between width (0) and height (1).")
    @click.option("--sorting-order", type=int)
    @click.pass_context
    def canvas_create(ctx, name, parent_id, parent_path, render_mode, camera_id, scaler,
                      reference_resolution, match_width_or_height, sorting_order):
        """Create a Canvas with CanvasScaler and GraphicRaycaster under Undo."""
        run(ctx, "ui.canvas.create", **_payload(
            Name=name,
            ParentId=parent_id,
            ParentPath=parent_path,
            RenderMode=render_mode,
            CameraId=camera_id,
            ScalerMode=scaler,
            ReferenceResolution=reference_resolution,
            MatchWidthOrHeight=match_width_or_height,
            SortingOrder=sorting_order,
        ))

    @ui.group()
    def element():
        """Create uGUI elements."""

    @element.command("create")
    @click.argument("element_type", type=click.Choice(["text", "button", "image", "panel"]))
    @click.option("--parent-id", type=int, help="Parent GameObject instance ID (Canvas or UI element).")
    @click.option("--parent-path", help="Parent hierarchy path.")
    @click.option("--name", help="GameObject name; defaults to the element type.")
    @click.option("--text", help="Text content for text and button elements.")
    @click.option("--font-size", type=click.IntRange(1, 300), help="Font size in pixels.")
    @click.option("--color", help="Tint or text colour as RRGGBB or #RRGGBB.")
    @click.option("--sprite", "sprite_path", help="Assets/... sprite asset for image and panel elements.")
    @click.option("--font", "font_path", help="Assets/... font asset; defaults to the built-in legacy font.")
    @click.option("--width", type=float, help="Size delta width.")
    @click.option("--height", type=float, help="Size delta height.")
    @click.option("--anchor-min", type=PAIR, help="Anchor min as X Y.")
    @click.option("--anchor-max", type=PAIR, help="Anchor max as X Y.")
    @click.option("--pivot", type=PAIR, help="Pivot as X Y.")
    @click.option("--position", "anchored_position", type=PAIR, help="Anchored position as X Y.")
    @click.option("--alignment", type=click.Choice(
        ["UpperLeft", "UpperCenter", "UpperRight", "MiddleLeft", "MiddleCenter",
         "MiddleRight", "LowerLeft", "LowerCenter", "LowerRight"]),
        help="Text alignment; defaults to MiddleCenter.")
    @click.option("--raycast/--no-raycast", "raycast_target", default=None,
                  help="Whether the graphic receives pointer events.")
    @click.pass_context
    def element_create(ctx, element_type, parent_id, parent_path, name, text, font_size, color,
                       sprite_path, font_path, width, height, anchor_min, anchor_max, pivot,
                       anchored_position, alignment, raycast_target):
        """Create a Text, Button, Image or Panel element under Undo."""
        run(ctx, "ui.element.create", **_payload(
            Type=element_type,
            ParentId=parent_id,
            ParentPath=parent_path,
            Name=name,
            Text=text,
            FontSize=font_size,
            Color=color,
            SpritePath=sprite_path,
            FontPath=font_path,
            Width=width,
            Height=height,
            AnchorMin=anchor_min,
            AnchorMax=anchor_max,
            Pivot=pivot,
            AnchoredPosition=anchored_position,
            Alignment=alignment,
            RaycastTarget=raycast_target,
        ))

    @ui.command("list")
    @click.option("--filter", help="Only elements whose name contains this text.")
    @click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
    @click.pass_context
    def ui_list(ctx, filter, limit):
        """List uGUI canvases and elements in the loaded scenes."""
        run(ctx, "ui.list", **_payload(Filter=filter, Limit=limit))

    @ui.command("inspect")
    @click.option("--id", "object_id", type=int, help="uGUI GameObject instance ID.")
    @click.option("--path", help="Hierarchy path of the element.")
    @click.option("--scene", "scene_path", help="Scene asset path used to disambiguate --path.")
    @click.pass_context
    def ui_inspect(ctx, object_id, path, scene_path):
        """Show rect, anchors, graphics and button state of one uGUI element."""
        run(ctx, "ui.inspect", **_target(object_id, path, scene_path))

    @ui.group()
    def toolkit():
        """Inspect and create UI Toolkit UXML and USS assets."""

    @toolkit.command("inspect")
    @click.argument("asset_path")
    @click.option("--limit", type=click.IntRange(1, 2000), default=200, show_default=True)
    @click.pass_context
    def toolkit_inspect(ctx, asset_path, limit):
        """Read an .uxml element tree, a .uss selector list, or a folder of both."""
        run(ctx, "ui.toolkit.inspect", AssetPath=asset_path, Limit=limit)

    @toolkit.command("create")
    @click.option("--uxml", "uxml_path", help="Assets/... .uxml path to create.")
    @click.option("--uss", "uss_path", help="Assets/... .uss path to create.")
    @click.option("--name", help="Root element name; defaults to the UXML file name.")
    @click.option("--label", help="Text of an optional Label added under the root.")
    @click.option("--force", is_flag=True, help="Overwrite existing files.")
    @click.pass_context
    def toolkit_create(ctx, uxml_path, uss_path, name, label, force):
        """Create UXML/USS assets. UI Toolkit runtime documents are unavailable in 2020.3."""
        run(ctx, "ui.toolkit.create", **_payload(
            UxmlPath=uxml_path, UssPath=uss_path, Name=name, Label=label, Force=force or None))
