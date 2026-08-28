"""Blender CLI - Generate Blender Python (bpy) scripts from scene JSON.

This module translates a scene JSON into a complete bpy script that can be
run with: blender --background --python script.py
"""

import json
import math
import os
import re
from typing import Dict, Any, Optional, List

# Blender's FFmpegSettings.format defaults to Matroska, which rewrites the
# movie extension the user asked for; pinning the container keeps the written
# file aligned with the requested output path.
FFMPEG_CONTAINER_FORMATS = {
    ".mp4": "MPEG4", ".mpg": "MPEG4", ".mpeg": "MPEG4",
    ".mov": "QUICKTIME",
    ".avi": "AVI", ".mkv": "MKV", ".webm": "WEBM",
}
FFMPEG_DEFAULT_FORMAT = "MPEG4"

# Extensions Blender's FFMPEG writer accepts as "already the container's"
# (the movie writer's get_file_extensions): a target ending in one of these is
# written verbatim; anything else gains the frame range plus the first entry.
FFMPEG_CONTAINER_EXTENSIONS = {
    "MPEG4": (".mp4", ".mpg", ".mpeg"),
    "QUICKTIME": (".mov",),
    "AVI": (".avi",),
    "MKV": (".mkv",),
    "WEBM": (".webm",),
    "OGG": (".ogv", ".ogg"),
}

# First extension Blender writes per image format (image_path_ext_from_imformat_impl).
IMAGE_FORMAT_EXTENSIONS = {
    "PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp",
    "TIFF": ".tif", "OPEN_EXR": ".exr", "HDR": ".hdr",
}

# imb_ext_image: suffixes Blender treats as an existing image extension, so a
# configured format replaces them instead of appending its own.
KNOWN_IMAGE_EXTENSIONS = {
    ".png", ".tga", ".bmp", ".jpg", ".jpeg", ".sgi", ".rgb", ".rgba",
    ".tif", ".tiff", ".tx", ".avif", ".jp2", ".j2c", ".hdr", ".dds",
    ".dpx", ".cin", ".exr", ".psd", ".pdd", ".psb", ".webp",
}

_FRAME_PLACEHOLDER = re.compile(r"#+")
_FRAME_DIGITS = 4


def _ensure_image_extension(path: str, ext: str) -> str:
    """Mirror Blender's do_ensure_image_extension for a configured format."""
    if path.lower().endswith(ext):
        return path
    root, current = os.path.splitext(path)
    if current and current.lower() in KNOWN_IMAGE_EXTENSIONS:
        return root + ext
    return path + ext


def _expand_frame_digits(path: str, frame: int) -> str:
    """Mirror BLI_path_frame: replace a '#' run or append digits to the name."""
    directory, name = os.path.split(path)
    match = None
    for found in _FRAME_PLACEHOLDER.finditer(name):
        match = found  # Blender keeps scanning and uses the last run
    if match:
        width = match.end() - match.start()
        name = name[:match.start()] + f"{frame:0{width}d}" + name[match.end():]
    else:
        name = name + f"{frame:0{_FRAME_DIGITS}d}"
    return os.path.join(directory, name)


def blender_still_path(output_path: str, output_format: str) -> Optional[str]:
    """The exact file Blender writes for a write_still render."""
    ext = IMAGE_FORMAT_EXTENSIONS.get(output_format)
    if ext is None:
        return None
    return _ensure_image_extension(output_path, ext)


def blender_frame_path(output_path: str, output_format: str, frame: int) -> Optional[str]:
    """The exact file Blender writes for one frame of an image animation."""
    ext = IMAGE_FORMAT_EXTENSIONS.get(output_format)
    if ext is None:
        return None
    return _ensure_image_extension(_expand_frame_digits(output_path, frame), ext)


def blender_movie_path(output_path: str, start: int, end: int) -> str:
    """The exact file Blender's FFmpeg writer produces for an animation.

    A target already ending in the pinned container's extension is written
    verbatim; any other target keeps its name and gains the frame range plus
    the container's extension.
    """
    exts = FFMPEG_CONTAINER_EXTENSIONS[_ffmpeg_container(output_path)]
    if any(output_path.lower().endswith(ext) for ext in exts):
        return output_path
    return f"{output_path}{start:04d}-{end:04d}{exts[0]}"


def _ffmpeg_container(output_path: str) -> str:
    """Blender FFmpegSettings.format value matching the requested extension."""
    ext = os.path.splitext(output_path)[1].lower()
    return FFMPEG_CONTAINER_FORMATS.get(ext, FFMPEG_DEFAULT_FORMAT)


def generate_full_script(
    project: Dict[str, Any],
    output_path: str,
    frame: Optional[int] = None,
    animation: bool = False,
) -> str:
    """Generate a complete bpy script from scene JSON.

    Args:
        project: The scene dict
        output_path: Render output path
        frame: Specific frame to render
        animation: Render full animation

    Returns:
        Complete Python script string
    """
    lines = []
    lines.append("#!/usr/bin/env python3")
    lines.append('"""Auto-generated Blender Python script from blender-cli."""')
    lines.append("")
    lines.append("import bpy")
    lines.append("import math")
    lines.append("import os")
    lines.append("")
    lines.append("# ── Clear Default Scene ──────────────────────────────────────")
    lines.append("bpy.ops.object.select_all(action='SELECT')")
    lines.append("bpy.ops.object.delete(use_global=False)")
    lines.append("")

    # Scene settings
    lines.extend(_gen_scene_settings(project))
    lines.append("")

    # Render settings
    lines.extend(_gen_render_settings(project))
    lines.append("")

    # World settings
    lines.extend(_gen_world_settings(project))
    lines.append("")

    # Materials
    lines.extend(_gen_materials(project))
    lines.append("")

    # Objects
    lines.extend(_gen_objects(project))
    lines.append("")

    # Object parenting
    lines.extend(_gen_object_parenting(project))
    lines.append("")

    # Cameras
    lines.extend(_gen_cameras(project))
    lines.append("")

    # Lights
    lines.extend(_gen_lights(project))
    lines.append("")

    # Keyframes
    lines.extend(_gen_keyframes(project))
    lines.append("")

    # Render output
    lines.extend(_gen_render_output(project, output_path, frame, animation))

    return "\n".join(lines)


def _gen_scene_settings(project: Dict[str, Any]) -> List[str]:
    """Generate scene settings code."""
    scene = project.get("scene", {})
    lines = [
        "# ── Scene Settings ──────────────────────────────────────────",
        "scene = bpy.context.scene",
        f"scene.unit_settings.system = {scene.get('unit_system', 'METRIC').upper()!r}",
        f"scene.unit_settings.scale_length = {scene.get('unit_scale', 1.0)}",
        f"scene.frame_start = {scene.get('frame_start', 1)}",
        f"scene.frame_end = {scene.get('frame_end', 250)}",
        f"scene.frame_current = {scene.get('frame_current', 1)}",
        f"scene.render.fps = {scene.get('fps', 24)}",
    ]
    return lines


def _gen_render_settings(project: Dict[str, Any]) -> List[str]:
    """Generate render settings code."""
    render = project.get("render", {})
    engine = render.get("engine", "CYCLES")

    lines = [
        "# ── Render Settings ─────────────────────────────────────────",
        f"scene.render.engine = {_engine_to_bpy(engine)!r}",
        f"scene.render.resolution_x = {render.get('resolution_x', 1920)}",
        f"scene.render.resolution_y = {render.get('resolution_y', 1080)}",
        f"scene.render.resolution_percentage = {render.get('resolution_percentage', 100)}",
        f"scene.render.film_transparent = {render.get('film_transparent', False)}",
    ]

    if engine == "CYCLES":
        lines.append(f"scene.cycles.samples = {render.get('samples', 128)}")
        lines.append(f"scene.cycles.use_denoising = {render.get('use_denoising', True)}")
    elif engine == "EEVEE":
        lines.append(f"scene.eevee.taa_render_samples = {render.get('samples', 64)}")

    return lines


def _gen_world_settings(project: Dict[str, Any]) -> List[str]:
    """Generate world/environment settings code."""
    world = project.get("world", {})
    bg = world.get("background_color", [0.05, 0.05, 0.05])

    lines = [
        "# ── World Settings ──────────────────────────────────────────",
        "world = bpy.data.worlds.get('World')",
        "if world is None:",
        "    world = bpy.data.worlds.new('World')",
        "    scene.world = world",
        "world.use_nodes = True",
        "bg_node = world.node_tree.nodes.get('Background')",
        "if bg_node:",
        f"    bg_node.inputs[0].default_value = ({bg[0]}, {bg[1]}, {bg[2]}, 1.0)",
    ]

    if world.get("use_hdri") and world.get("hdri_path"):
        hdri_path = world["hdri_path"]
        strength = world.get("hdri_strength", 1.0)
        lines.extend([
            "",
            "# HDRI environment",
            "env_tex = world.node_tree.nodes.new('ShaderNodeTexEnvironment')",
            f"env_tex.image = bpy.data.images.load({hdri_path!r})",
            f"bg_node.inputs[1].default_value = {strength}",
            "world.node_tree.links.new(env_tex.outputs[0], bg_node.inputs[0])",
        ])

    return lines


def _gen_materials(project: Dict[str, Any]) -> List[str]:
    """Generate material creation code."""
    materials = project.get("materials", [])
    if not materials:
        return ["# ── Materials ───────────────────────────────────────────────", "# (none)"]

    lines = ["# ── Materials ───────────────────────────────────────────────"]

    for mat in materials:
        name = mat.get("name", "Material")
        color = mat.get("color", [0.8, 0.8, 0.8, 1.0])
        metallic = mat.get("metallic", 0.0)
        roughness = mat.get("roughness", 0.5)
        specular = mat.get("specular", 0.5)
        emission = mat.get("emission_color", [0, 0, 0, 1])
        emission_strength = mat.get("emission_strength", 0.0)
        alpha = mat.get("alpha", 1.0)

        var_name = _safe_var_name(name)
        lines.extend([
            f"mat_{var_name} = bpy.data.materials.new(name={name!r})",
            f"mat_{var_name}.use_nodes = True",
            f"bsdf_{var_name} = mat_{var_name}.node_tree.nodes.get('Principled BSDF')",
            f"if bsdf_{var_name}:",
            f"    bsdf_{var_name}.inputs['Base Color'].default_value = ({color[0]}, {color[1]}, {color[2]}, {color[3]})",
            f"    bsdf_{var_name}.inputs['Metallic'].default_value = {metallic}",
            f"    bsdf_{var_name}.inputs['Roughness'].default_value = {roughness}",
            f"    bsdf_{var_name}.inputs['Specular IOR Level'].default_value = {specular}",
            f"    bsdf_{var_name}.inputs['Alpha'].default_value = {alpha}",
        ])
        if emission_strength > 0:
            lines.extend([
                f"    bsdf_{var_name}.inputs['Emission Color'].default_value = ({emission[0]}, {emission[1]}, {emission[2]}, {emission[3]})",
                f"    bsdf_{var_name}.inputs['Emission Strength'].default_value = {emission_strength}",
            ])
        lines.append("")

    return lines


def _gen_objects(project: Dict[str, Any]) -> List[str]:
    """Generate object creation code."""
    objects = project.get("objects", [])
    if not objects:
        return ["# ── Objects ─────────────────────────────────────────────────", "# (none)"]

    lines = ["# ── Objects ─────────────────────────────────────────────────"]
    materials = project.get("materials", [])
    mat_id_to_name = {m["id"]: m["name"] for m in materials}

    for i, obj in enumerate(objects):
        mesh_type = obj.get("mesh_type", "cube")
        name = obj.get("name", f"Object_{i}")
        loc = obj.get("location", [0, 0, 0])
        rot = obj.get("rotation", [0, 0, 0])
        scl = obj.get("scale", [1, 1, 1])
        params = obj.get("mesh_params", {})

        lines.append(f"# Object: {name!r}")

        # Create mesh primitive
        if mesh_type == "cube":
            size = params.get("size", 2.0)
            lines.append(f"bpy.ops.mesh.primitive_cube_add(size={size}, location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "sphere":
            radius = params.get("radius", 1.0)
            segments = params.get("segments", 32)
            rings = params.get("rings", 16)
            lines.append(f"bpy.ops.mesh.primitive_uv_sphere_add(radius={radius}, segments={segments}, ring_count={rings}, location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "cylinder":
            radius = params.get("radius", 1.0)
            depth = params.get("depth", 2.0)
            vertices = params.get("vertices", 32)
            lines.append(f"bpy.ops.mesh.primitive_cylinder_add(radius={radius}, depth={depth}, vertices={vertices}, location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "cone":
            r1 = params.get("radius1", 1.0)
            r2 = params.get("radius2", 0.0)
            depth = params.get("depth", 2.0)
            vertices = params.get("vertices", 32)
            lines.append(f"bpy.ops.mesh.primitive_cone_add(radius1={r1}, radius2={r2}, depth={depth}, vertices={vertices}, location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "plane":
            size = params.get("size", 2.0)
            lines.append(f"bpy.ops.mesh.primitive_plane_add(size={size}, location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "torus":
            major = params.get("major_radius", 1.0)
            minor = params.get("minor_radius", 0.25)
            maj_seg = params.get("major_segments", 48)
            min_seg = params.get("minor_segments", 12)
            lines.append(f"bpy.ops.mesh.primitive_torus_add(major_radius={major}, minor_radius={minor}, major_segments={maj_seg}, minor_segments={min_seg}, location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "monkey":
            lines.append(f"bpy.ops.mesh.primitive_monkey_add(location=({loc[0]}, {loc[1]}, {loc[2]}))")
        elif mesh_type == "empty":
            lines.append(f"bpy.ops.object.empty_add(location=({loc[0]}, {loc[1]}, {loc[2]}))")
        else:
            lines.append(f"# Unknown mesh type: {mesh_type!r}")
            continue

        lines.append("obj = bpy.context.active_object")
        lines.append(f"obj.name = {name!r}")
        lines.append(f"obj.rotation_euler = (math.radians({rot[0]}), math.radians({rot[1]}), math.radians({rot[2]}))")
        lines.append(f"obj.scale = ({scl[0]}, {scl[1]}, {scl[2]})")

        if not obj.get("visible", True):
            lines.append("obj.hide_render = True")
            lines.append("obj.hide_viewport = True")

        # Assign material
        mat_id = obj.get("material")
        if mat_id is not None and mat_id in mat_id_to_name:
            mat_name = mat_id_to_name[mat_id]
            var_name = _safe_var_name(mat_name)
            lines.append(f"if 'mat_{var_name}' in dir():")
            lines.append(f"    obj.data.materials.append(mat_{var_name})")

        # Add modifiers
        for mod in obj.get("modifiers", []):
            lines.extend(_gen_modifier(mod))

        lines.append("")

    return lines


def _gen_object_parenting(project: Dict[str, Any]) -> List[str]:
    """Generate object parenting relationships after all objects exist."""
    objects = project.get("objects", [])
    if not objects:
        return ["# ── Object Parenting ───────────────────────────────────────", "# (none)"]

    id_to_name = {
        obj.get("id", index): obj.get("name", f"Object_{index}")
        for index, obj in enumerate(objects)
    }
    parent_pairs = []
    for index, obj in enumerate(objects):
        parent_id = obj.get("parent")
        if parent_id is None:
            continue
        child_name = obj.get("name", f"Object_{index}")
        parent_name = id_to_name.get(parent_id)
        if not parent_name:
            continue
        parent_pairs.append((child_name, parent_name))

    if not parent_pairs:
        return ["# ── Object Parenting ───────────────────────────────────────", "# (none)"]

    lines = ["# ── Object Parenting ───────────────────────────────────────"]
    for child_name, parent_name in parent_pairs:
        lines.extend([
            f"child_obj = bpy.data.objects.get({child_name!r})",
            f"parent_obj = bpy.data.objects.get({parent_name!r})",
            "if child_obj and parent_obj:",
            "    child_obj.parent = parent_obj",
            "    child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()",
            "",
        ])
    return lines


def _gen_modifier(mod: Dict[str, Any]) -> List[str]:
    """Generate modifier code for an object."""
    mod_type = mod.get("type", "")
    bpy_type = mod.get("bpy_type", "")
    mod_name = mod.get("name", mod_type)
    params = mod.get("params", {})

    lines = [
        f"mod = obj.modifiers.new(name={mod_name!r}, type={bpy_type!r})",
    ]

    if mod_type == "subdivision_surface":
        lines.append(f"mod.levels = {params.get('levels', 1)}")
        lines.append(f"mod.render_levels = {params.get('render_levels', 2)}")
        if params.get("use_creases"):
            lines.append("mod.use_creases = True")
    elif mod_type == "mirror":
        lines.append(f"mod.use_axis[0] = {params.get('use_axis_x', True)}")
        lines.append(f"mod.use_axis[1] = {params.get('use_axis_y', False)}")
        lines.append(f"mod.use_axis[2] = {params.get('use_axis_z', False)}")
        lines.append(f"mod.use_clip = {params.get('use_clip', True)}")
        lines.append(f"mod.merge_threshold = {params.get('merge_threshold', 0.001)}")
    elif mod_type == "array":
        lines.append(f"mod.count = {params.get('count', 2)}")
        lines.append(f"mod.relative_offset_displace[0] = {params.get('relative_offset_x', 1.0)}")
        lines.append(f"mod.relative_offset_displace[1] = {params.get('relative_offset_y', 0.0)}")
        lines.append(f"mod.relative_offset_displace[2] = {params.get('relative_offset_z', 0.0)}")
    elif mod_type == "bevel":
        lines.append(f"mod.width = {params.get('width', 0.1)}")
        lines.append(f"mod.segments = {params.get('segments', 1)}")
        limit = params.get("limit_method", "NONE")
        lines.append(f"mod.limit_method = {limit!r}")
        if limit == "ANGLE":
            lines.append(f"mod.angle_limit = {params.get('angle_limit', 0.523599)}")
    elif mod_type == "solidify":
        lines.append(f"mod.thickness = {params.get('thickness', 0.01)}")
        lines.append(f"mod.offset = {params.get('offset', -1.0)}")
        lines.append(f"mod.use_even_offset = {params.get('use_even_offset', False)}")
    elif mod_type == "decimate":
        lines.append(f"mod.ratio = {params.get('ratio', 0.5)}")
        lines.append(f"mod.decimate_type = {params.get('decimate_type', 'COLLAPSE')!r}")
    elif mod_type == "boolean":
        op = params.get("operation", "DIFFERENCE")
        lines.append(f"mod.operation = {op!r}")
        operand = params.get("operand_object", "")
        if operand:
            lines.append(f"mod.object = bpy.data.objects.get({operand!r})")
        solver = params.get("solver", "EXACT")
        lines.append(f"mod.solver = {solver!r}")
    elif mod_type == "smooth":
        lines.append(f"mod.factor = {params.get('factor', 0.5)}")
        lines.append(f"mod.iterations = {params.get('iterations', 1)}")
        lines.append(f"mod.use_x = {params.get('use_x', True)}")
        lines.append(f"mod.use_y = {params.get('use_y', True)}")
        lines.append(f"mod.use_z = {params.get('use_z', True)}")

    return lines


def _gen_cameras(project: Dict[str, Any]) -> List[str]:
    """Generate camera creation code."""
    cameras = project.get("cameras", [])
    if not cameras:
        return ["# ── Cameras ─────────────────────────────────────────────────", "# (none)"]

    lines = ["# ── Cameras ─────────────────────────────────────────────────"]

    for cam in cameras:
        name = cam.get("name", "Camera")
        loc = cam.get("location", [0, 0, 5])
        rot = cam.get("rotation", [0, 0, 0])
        cam_type = cam.get("type", "PERSP")
        focal = cam.get("focal_length", 50.0)
        sensor = cam.get("sensor_width", 36.0)
        clip_s = cam.get("clip_start", 0.1)
        clip_e = cam.get("clip_end", 1000.0)

        lines.extend([
            f"cam_data = bpy.data.cameras.new(name={name!r})",
            f"cam_data.type = {cam_type!r}",
            f"cam_data.lens = {focal}",
            f"cam_data.sensor_width = {sensor}",
            f"cam_data.clip_start = {clip_s}",
            f"cam_data.clip_end = {clip_e}",
        ])

        if cam.get("dof_enabled"):
            lines.extend([
                "cam_data.dof.use_dof = True",
                f"cam_data.dof.focus_distance = {cam.get('dof_focus_distance', 10.0)}",
                f"cam_data.dof.aperture_fstop = {cam.get('dof_aperture', 2.8)}",
            ])

        lines.extend([
            f"cam_obj = bpy.data.objects.new({name!r}, cam_data)",
            "bpy.context.collection.objects.link(cam_obj)",
            f"cam_obj.location = ({loc[0]}, {loc[1]}, {loc[2]})",
            f"cam_obj.rotation_euler = (math.radians({rot[0]}), math.radians({rot[1]}), math.radians({rot[2]}))",
        ])

        if cam.get("is_active", False):
            lines.append("scene.camera = cam_obj")

        lines.append("")

    return lines


def _gen_lights(project: Dict[str, Any]) -> List[str]:
    """Generate light creation code."""
    lights = project.get("lights", [])
    if not lights:
        return ["# ── Lights ──────────────────────────────────────────────────", "# (none)"]

    lines = ["# ── Lights ──────────────────────────────────────────────────"]

    for light in lights:
        name = light.get("name", "Light")
        light_type = light.get("type", "POINT")
        loc = light.get("location", [0, 0, 3])
        rot = light.get("rotation", [0, 0, 0])
        color = light.get("color", [1, 1, 1])
        power = light.get("power", 1000)

        lines.extend([
            f"light_data = bpy.data.lights.new(name={name!r}, type={light_type!r})",
            f"light_data.energy = {power}",
            f"light_data.color = ({color[0]}, {color[1]}, {color[2]})",
        ])

        if light_type == "POINT":
            lines.append(f"light_data.shadow_soft_size = {light.get('radius', 0.25)}")
        elif light_type == "SUN":
            lines.append(f"light_data.angle = {light.get('angle', 0.00918)}")
        elif light_type == "SPOT":
            lines.append(f"light_data.shadow_soft_size = {light.get('radius', 0.25)}")
            lines.append(f"light_data.spot_size = {light.get('spot_size', 0.785398)}")
            lines.append(f"light_data.spot_blend = {light.get('spot_blend', 0.15)}")
        elif light_type == "AREA":
            lines.append(f"light_data.size = {light.get('size', 1.0)}")
            lines.append(f"light_data.size_y = {light.get('size_y', 1.0)}")
            lines.append(f"light_data.shape = {light.get('shape', 'RECTANGLE')!r}")

        lines.extend([
            f"light_obj = bpy.data.objects.new({name!r}, light_data)",
            "bpy.context.collection.objects.link(light_obj)",
            f"light_obj.location = ({loc[0]}, {loc[1]}, {loc[2]})",
            f"light_obj.rotation_euler = (math.radians({rot[0]}), math.radians({rot[1]}), math.radians({rot[2]}))",
            "",
        ])

    return lines


def _gen_keyframes(project: Dict[str, Any]) -> List[str]:
    """Generate keyframe animation code."""
    objects = project.get("objects", [])
    has_keyframes = any(obj.get("keyframes") for obj in objects)

    if not has_keyframes:
        return ["# ── Keyframes ───────────────────────────────────────────────", "# (none)"]

    lines = ["# ── Keyframes ───────────────────────────────────────────────"]

    for obj in objects:
        keyframes = obj.get("keyframes", [])
        if not keyframes:
            continue

        name = obj.get("name", "Object")
        lines.append(f"obj = bpy.data.objects.get({name!r})")
        lines.append("if obj:")

        for kf in keyframes:
            frame = kf["frame"]
            prop = kf["property"]
            value = kf["value"]
            interp = kf.get("interpolation", "BEZIER")

            if prop == "location":
                lines.append(f"    obj.location = ({value[0]}, {value[1]}, {value[2]})")
                lines.append(f"    obj.keyframe_insert(data_path='location', frame={frame})")
            elif prop == "rotation":
                lines.append(f"    obj.rotation_euler = (math.radians({value[0]}), math.radians({value[1]}), math.radians({value[2]}))")
                lines.append(f"    obj.keyframe_insert(data_path='rotation_euler', frame={frame})")
            elif prop == "scale":
                lines.append(f"    obj.scale = ({value[0]}, {value[1]}, {value[2]})")
                lines.append(f"    obj.keyframe_insert(data_path='scale', frame={frame})")
            elif prop == "visible":
                hide_val = "False" if value else "True"
                lines.append(f"    obj.hide_render = {hide_val}")
                lines.append(f"    obj.keyframe_insert(data_path='hide_render', frame={frame})")

        lines.append("")

    return lines


def _gen_render_output(
    project: Dict[str, Any],
    output_path: str,
    frame: Optional[int],
    animation: bool,
) -> List[str]:
    """Generate render execution code."""
    render = project.get("render", {})
    scene = project.get("scene", {})
    fmt = render.get("output_format", "PNG")

    # Map format names to Blender format strings
    format_map = {
        "PNG": "PNG", "JPEG": "JPEG", "BMP": "BMP",
        "TIFF": "TIFF", "OPEN_EXR": "OPEN_EXR",
        "HDR": "HDR", "FFMPEG": "FFMPEG",
    }
    bpy_format = format_map.get(fmt, "PNG")

    lines = [
        "# ── Render Output ───────────────────────────────────────────",
        f"scene.render.image_settings.file_format = {bpy_format!r}",
        f"scene.render.filepath = {output_path!r}",
    ]
    if bpy_format == "FFMPEG":
        container = _ffmpeg_container(output_path)
        lines.append(f"scene.render.ffmpeg.format = {container!r}")
        if container == "WEBM":
            lines.append("scene.render.ffmpeg.codec = 'WEBM'")

    if animation:
        lines.extend([
            "",
            "# Render animation",
            "bpy.ops.render.render(animation=True)",
        ])
    else:
        target_frame = frame or scene.get("frame_current", 1)
        lines.extend([
            f"scene.frame_set({target_frame})",
            "",
            "# Render single frame",
            "bpy.ops.render.render(write_still=True)",
        ])

    lines.extend([
        "",
        f"print('Render complete: ' + {output_path!r})",
    ])

    return lines


def _engine_to_bpy(engine: str) -> str:
    """Convert engine name to bpy enum value."""
    mapping = {
        "CYCLES": "CYCLES",
        "EEVEE": "BLENDER_EEVEE",
        "WORKBENCH": "BLENDER_WORKBENCH",
    }
    return mapping.get(engine, "CYCLES")


def _safe_var_name(name: str) -> str:
    """Convert a name to a safe Python variable name."""
    result = name.replace(" ", "_").replace(".", "_").replace("-", "_")
    result = "".join(c for c in result if c.isalnum() or c == "_")
    if result and result[0].isdigit():
        result = "_" + result
    return result or "unnamed"
