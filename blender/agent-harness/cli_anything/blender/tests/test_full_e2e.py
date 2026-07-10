"""End-to-end tests for Blender CLI.

These tests verify full workflows: scene creation, manipulation, bpy script
generation, scene roundtrips, and CLI subprocess invocation.
No actual Blender installation is required.
"""

import json
import os
import sys
import tempfile
import subprocess
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.blender.core.scene import create_scene, save_scene, open_scene, get_scene_info
from cli_anything.blender.core.objects import add_object, remove_object, duplicate_object, transform_object, list_objects
from cli_anything.blender.core.materials import create_material, assign_material, set_material_property, list_materials
from cli_anything.blender.core.modifiers import add_modifier, list_modifiers
from cli_anything.blender.core.lighting import add_camera, add_light, set_camera, set_light, list_cameras, list_lights
from cli_anything.blender.core.animation import add_keyframe, set_frame_range, set_fps, list_keyframes
from cli_anything.blender.core.render import set_render_settings, render_scene, generate_bpy_script, get_render_settings
from cli_anything.blender.core import preview as preview_mod
from cli_anything.blender.core.session import Session
from cli_anything.blender.utils.bpy_gen import generate_full_script


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _artifact_path(manifest, artifact_id):
    for artifact in manifest["artifacts"]:
        if artifact["artifact_id"] == artifact_id:
            return os.path.join(manifest["_bundle_dir"], artifact["path"])
    raise KeyError(f"Artifact not found: {artifact_id}")


def _assert_png(path):
    assert os.path.isfile(path), f"Missing PNG artifact: {path}"
    with open(path, "rb") as fh:
        assert fh.read(8) == PNG_MAGIC, f"Invalid PNG header: {path}"
    assert os.path.getsize(path) > 0, f"Empty PNG artifact: {path}"


def _wait_for_live_bundle_count(session_path, expected_count, timeout_s=30.0):
    deadline = time.time() + timeout_s
    latest = None
    while time.time() < deadline:
        with open(session_path, "r", encoding="utf-8") as fh:
            latest = json.load(fh)
        if latest.get("bundle_count", 0) >= expected_count:
            return latest
        time.sleep(0.5)
    raise AssertionError(f"Timed out waiting for bundle_count >= {expected_count}: {latest}")


# ── Scene Lifecycle ─────────────────────────────────────────────

class TestSceneLifecycle:
    def test_create_save_open_roundtrip(self, tmp_dir):
        proj = create_scene(name="roundtrip")
        path = os.path.join(tmp_dir, "scene.blend-cli.json")
        save_scene(proj, path)
        loaded = open_scene(path)
        assert loaded["name"] == "roundtrip"
        assert loaded["render"]["resolution_x"] == 1920

    def test_scene_with_objects_roundtrip(self, tmp_dir):
        proj = create_scene(name="with_objects")
        add_object(proj, mesh_type="cube", name="MyCube")
        add_object(proj, mesh_type="sphere", name="MySphere")
        add_modifier(proj, "subdivision_surface", 0, params={"levels": 2})
        path = os.path.join(tmp_dir, "scene.json")
        save_scene(proj, path)
        loaded = open_scene(path)
        assert len(loaded["objects"]) == 2
        assert loaded["objects"][0]["modifiers"][0]["type"] == "subdivision_surface"

    def test_scene_with_materials_roundtrip(self, tmp_dir):
        proj = create_scene(name="with_materials")
        create_material(proj, name="Red", color=[1, 0, 0, 1])
        add_object(proj, name="Cube")
        assign_material(proj, 0, 0)
        path = os.path.join(tmp_dir, "scene.json")
        save_scene(proj, path)
        loaded = open_scene(path)
        assert len(loaded["materials"]) == 1
        assert loaded["objects"][0]["material"] == loaded["materials"][0]["id"]

    def test_scene_with_cameras_lights_roundtrip(self, tmp_dir):
        proj = create_scene(name="full_scene")
        add_camera(proj, name="MainCam", location=[7, -6, 5], rotation=[63, 0, 46])
        add_light(proj, light_type="SUN", name="Sun", rotation=[-30, 0, 0])
        add_light(proj, light_type="POINT", name="Fill", location=[3, 3, 3], power=500)
        path = os.path.join(tmp_dir, "scene.json")
        save_scene(proj, path)
        loaded = open_scene(path)
        assert len(loaded["cameras"]) == 1
        assert len(loaded["lights"]) == 2
        assert loaded["cameras"][0]["name"] == "MainCam"

    def test_scene_info_complete(self):
        proj = create_scene(name="info_test")
        add_object(proj, mesh_type="cube")
        add_object(proj, mesh_type="sphere")
        create_material(proj, name="Metal")
        add_camera(proj)
        add_light(proj)
        info = get_scene_info(proj)
        assert info["counts"]["objects"] == 2
        assert info["counts"]["materials"] == 1
        assert info["counts"]["cameras"] == 1
        assert info["counts"]["lights"] == 1

    def test_complex_scene_roundtrip(self, tmp_dir):
        """Create a complex scene, save, reload, verify integrity."""
        proj = create_scene(name="complex", engine="CYCLES", samples=256)

        # Add objects
        add_object(proj, mesh_type="plane", name="Ground", scale=[10, 10, 1])
        add_object(proj, mesh_type="cube", name="Box", location=[0, 0, 1])
        add_object(proj, mesh_type="sphere", name="Ball", location=[3, 0, 1.5])
        add_object(proj, mesh_type="monkey", name="Suzanne", location=[-3, 0, 1.5])

        # Add modifiers
        add_modifier(proj, "subdivision_surface", 1, params={"levels": 2})
        add_modifier(proj, "bevel", 1, params={"width": 0.1, "segments": 2})
        add_modifier(proj, "subdivision_surface", 2, params={"levels": 3})

        # Add materials
        create_material(proj, name="Ground", color=[0.3, 0.3, 0.3, 1], roughness=0.9)
        create_material(proj, name="Red Plastic", color=[0.8, 0.1, 0.1, 1], roughness=0.3)
        create_material(proj, name="Chrome", color=[0.9, 0.9, 0.9, 1], metallic=1.0, roughness=0.05)
        create_material(proj, name="Gold", color=[1.0, 0.8, 0.2, 1], metallic=1.0, roughness=0.2)

        # Assign materials
        assign_material(proj, 0, 0)  # Ground -> Ground mat
        assign_material(proj, 1, 1)  # Box -> Red Plastic
        assign_material(proj, 2, 2)  # Ball -> Chrome
        assign_material(proj, 3, 3)  # Suzanne -> Gold

        # Camera and lights
        add_camera(proj, name="Main", location=[7, -6, 5], rotation=[63, 0, 46], focal_length=50)
        add_light(proj, light_type="SUN", name="KeyLight", rotation=[-45, 0, 30])
        add_light(proj, light_type="AREA", name="FillLight", location=[4, 4, 3], power=500)

        # Animation
        add_keyframe(proj, 3, 1, "location", [-3, 0, 1.5])
        add_keyframe(proj, 3, 120, "location", [-3, 0, 3.0])
        add_keyframe(proj, 3, 1, "rotation", [0, 0, 0])
        add_keyframe(proj, 3, 120, "rotation", [0, 0, 360])

        # Frame range
        set_frame_range(proj, 1, 120)
        set_fps(proj, 30)

        # Save and reload
        path = os.path.join(tmp_dir, "complex.json")
        save_scene(proj, path)
        loaded = open_scene(path)

        assert len(loaded["objects"]) == 4
        assert len(loaded["materials"]) == 4
        assert len(loaded["cameras"]) == 1
        assert len(loaded["lights"]) == 2
        assert loaded["objects"][1]["modifiers"][0]["type"] == "subdivision_surface"
        assert loaded["objects"][1]["modifiers"][1]["type"] == "bevel"
        assert loaded["scene"]["fps"] == 30
        assert loaded["scene"]["frame_end"] == 120

        # Verify keyframes survived roundtrip
        suzanne = loaded["objects"][3]
        assert len(suzanne["keyframes"]) == 4


# ── BPY Script Generation ──────────────────────────────────────

class TestBPYScriptGeneration:
    def test_empty_scene_script(self):
        proj = create_scene(name="empty")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "import bpy" in script
        assert "bpy.ops.object.select_all" in script
        assert "scene.render.engine" in script

    def test_script_contains_objects(self):
        proj = create_scene()
        add_object(proj, mesh_type="cube", name="TestCube", location=[1, 2, 3])
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_cube_add" in script
        assert "TestCube" in script
        assert "1, 2, 3" in script

    def test_script_contains_sphere(self):
        proj = create_scene()
        add_object(proj, mesh_type="sphere", mesh_params={"radius": 2.0, "segments": 64})
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_uv_sphere_add" in script
        assert "radius=2.0" in script
        assert "segments=64" in script

    def test_script_contains_cylinder(self):
        proj = create_scene()
        add_object(proj, mesh_type="cylinder")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_cylinder_add" in script

    def test_script_contains_cone(self):
        proj = create_scene()
        add_object(proj, mesh_type="cone")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_cone_add" in script

    def test_script_contains_plane(self):
        proj = create_scene()
        add_object(proj, mesh_type="plane")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_plane_add" in script

    def test_script_contains_torus(self):
        proj = create_scene()
        add_object(proj, mesh_type="torus")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_torus_add" in script

    def test_script_contains_monkey(self):
        proj = create_scene()
        add_object(proj, mesh_type="monkey")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "primitive_monkey_add" in script

    def test_script_contains_materials(self):
        proj = create_scene()
        create_material(proj, name="TestMat", color=[1, 0, 0, 1], metallic=0.8)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "bpy.data.materials.new" in script
        assert "TestMat" in script
        assert "Metallic" in script

    def test_script_contains_modifiers(self):
        proj = create_scene()
        add_object(proj, name="Cube")
        add_modifier(proj, "subdivision_surface", 0, params={"levels": 2, "render_levels": 3})
        script = generate_full_script(proj, "/tmp/render.png")
        assert "modifiers.new" in script
        assert "SUBSURF" in script
        assert "mod.levels = 2" in script
        assert "mod.render_levels = 3" in script

    def test_script_contains_mirror_modifier(self):
        proj = create_scene()
        add_object(proj, name="Cube")
        add_modifier(proj, "mirror", 0)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "MIRROR" in script
        assert "use_axis" in script

    def test_script_contains_array_modifier(self):
        proj = create_scene()
        add_object(proj, name="Cube")
        add_modifier(proj, "array", 0, params={"count": 5})
        script = generate_full_script(proj, "/tmp/render.png")
        assert "ARRAY" in script
        assert "mod.count = 5" in script

    def test_script_contains_cameras(self):
        proj = create_scene()
        add_camera(proj, name="RenderCam", location=[7, -6, 5], focal_length=85)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "bpy.data.cameras.new" in script
        assert "RenderCam" in script
        assert "cam_data.lens = 85" in script

    def test_script_contains_lights(self):
        proj = create_scene()
        add_light(proj, light_type="SUN", name="Sun", power=2.0)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "bpy.data.lights.new" in script
        assert "SUN" in script
        assert "energy = 2.0" in script

    def test_script_contains_spot_light(self):
        proj = create_scene()
        add_light(proj, light_type="SPOT")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "SPOT" in script
        assert "spot_size" in script

    def test_script_contains_area_light(self):
        proj = create_scene()
        add_light(proj, light_type="AREA")
        script = generate_full_script(proj, "/tmp/render.png")
        assert "AREA" in script
        assert "light_data.size" in script

    def test_script_contains_keyframes(self):
        proj = create_scene()
        add_object(proj, name="Animated")
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        add_keyframe(proj, 0, 60, "location", [5, 0, 0])
        script = generate_full_script(proj, "/tmp/render.png")
        assert "keyframe_insert" in script
        assert "location" in script

    def test_script_render_settings_cycles(self):
        proj = create_scene(engine="CYCLES", samples=256)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "CYCLES" in script
        assert "scene.cycles.samples = 256" in script

    def test_script_render_settings_eevee(self):
        proj = create_scene(engine="EEVEE", samples=64)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "BLENDER_EEVEE_NEXT" in script
        assert "eevee.taa_render_samples" in script

    def test_script_world_settings(self):
        proj = create_scene()
        script = generate_full_script(proj, "/tmp/render.png")
        assert "bpy.data.worlds" in script
        assert "Background" in script

    def test_script_render_still(self):
        proj = create_scene()
        script = generate_full_script(proj, "/tmp/render.png", frame=10)
        assert "frame_set(10)" in script
        assert "render.render(write_still=True)" in script

    def test_script_render_animation(self):
        proj = create_scene()
        script = generate_full_script(proj, "/tmp/render_", animation=True)
        assert "render.render(animation=True)" in script

    def test_script_output_format(self):
        proj = create_scene()
        proj["render"]["output_format"] = "JPEG"
        script = generate_full_script(proj, "/tmp/render.jpg")
        assert "JPEG" in script

    def test_script_material_assignment(self):
        proj = create_scene()
        mat = create_material(proj, name="Red", color=[1, 0, 0, 1])
        add_object(proj, name="Cube")
        assign_material(proj, 0, 0)
        script = generate_full_script(proj, "/tmp/render.png")
        assert "materials.append" in script

    def test_script_contains_parenting(self):
        proj = create_scene()
        parent = add_object(proj, mesh_type="empty", name="RigRoot")
        add_object(proj, name="ChildCube")
        proj["objects"][1]["parent"] = parent["id"]
        script = generate_full_script(proj, "/tmp/render.png")
        assert "child_obj.parent = parent_obj" in script
        assert "matrix_parent_inverse" in script

    def test_render_scene_creates_script_file(self, tmp_dir):
        proj = create_scene()
        add_object(proj, name="Cube")
        output_path = os.path.join(tmp_dir, "render.png")
        result = render_scene(proj, output_path, overwrite=True)
        assert os.path.exists(result["script_path"])
        with open(result["script_path"]) as f:
            content = f.read()
        assert "import bpy" in content

    def test_script_handles_hidden_objects(self):
        proj = create_scene()
        obj = add_object(proj, name="Hidden")
        obj["visible"] = False
        script = generate_full_script(proj, "/tmp/render.png")
        assert "hide_render = True" in script

    def test_script_handles_dof(self):
        proj = create_scene()
        cam = add_camera(proj, name="DOFCam")
        cam["dof_enabled"] = True
        cam["dof_focus_distance"] = 5.0
        cam["dof_aperture"] = 1.4
        script = generate_full_script(proj, "/tmp/render.png")
        assert "dof.use_dof = True" in script
        assert "focus_distance = 5.0" in script


# ── Workflow Tests ──────────────────────────────────────────────

class TestWorkflows:
    def test_product_render_workflow(self, tmp_dir):
        """Simulate a product render: object + material + lighting + camera."""
        proj = create_scene(name="product", profile="product_render")

        # Ground plane
        add_object(proj, mesh_type="plane", name="Ground", scale=[5, 5, 1])
        create_material(proj, name="Floor", color=[0.9, 0.9, 0.9, 1], roughness=0.8)
        assign_material(proj, 0, 0)

        # Product object
        add_object(proj, mesh_type="monkey", name="Product", location=[0, 0, 0.8])
        add_modifier(proj, "subdivision_surface", 1, params={"levels": 2, "render_levels": 3})
        create_material(proj, name="ProductMat", color=[0.8, 0.2, 0.1, 1],
                        metallic=0.3, roughness=0.4)
        assign_material(proj, 1, 1)

        # Lighting
        add_light(proj, light_type="AREA", name="KeyLight", location=[3, -3, 5],
                  rotation=[-45, 0, 45], power=1000)
        add_light(proj, light_type="AREA", name="FillLight", location=[-3, 2, 4],
                  power=300)
        add_light(proj, light_type="AREA", name="RimLight", location=[0, 5, 3],
                  power=500)

        # Camera
        add_camera(proj, name="ProductCam", location=[5, -5, 3],
                   rotation=[63, 0, 46], focal_length=85, set_active=True)

        # Render settings
        set_render_settings(proj, engine="CYCLES", samples=256)

        # Generate script
        output_path = os.path.join(tmp_dir, "product.png")
        result = render_scene(proj, output_path, overwrite=True)
        assert os.path.exists(result["script_path"])
        assert result["engine"] == "CYCLES"

    def test_animation_workflow(self, tmp_dir):
        """Simulate an animation workflow with keyframes."""
        proj = create_scene(name="turntable", fps=30)

        # Object
        add_object(proj, mesh_type="monkey", name="Suzanne")
        add_modifier(proj, "subdivision_surface", 0, params={"levels": 2})
        create_material(proj, name="Gold", color=[1.0, 0.8, 0.2, 1],
                        metallic=1.0, roughness=0.2)
        assign_material(proj, 0, 0)

        # Keyframes: 360 turntable
        set_frame_range(proj, 1, 120)
        add_keyframe(proj, 0, 1, "rotation", [0, 0, 0])
        add_keyframe(proj, 0, 120, "rotation", [0, 0, 360])

        # Camera
        add_camera(proj, name="Turntable Cam", location=[5, 0, 2],
                   rotation=[75, 0, 90], set_active=True)

        # Light
        add_light(proj, light_type="SUN", name="Sun", rotation=[-45, 0, 30])

        # Generate animation render
        output_path = os.path.join(tmp_dir, "frame_")
        result = render_scene(proj, output_path, animation=True, overwrite=True)
        assert result["animation"] is True
        assert "1-120" in result["frame_range"]

    def test_architectural_workflow(self, tmp_dir):
        """Simulate an architectural visualization."""
        proj = create_scene(name="arch_viz", engine="CYCLES", samples=512)

        # Floor
        add_object(proj, mesh_type="plane", name="Floor", scale=[20, 20, 1])
        create_material(proj, name="Concrete", color=[0.6, 0.58, 0.55, 1], roughness=0.9)
        assign_material(proj, 0, 0)

        # Walls (cubes scaled flat)
        add_object(proj, mesh_type="cube", name="WallBack",
                   location=[0, 10, 1.5], scale=[10, 0.15, 1.5])
        add_object(proj, mesh_type="cube", name="WallLeft",
                   location=[-10, 0, 1.5], scale=[0.15, 10, 1.5])

        # Furniture
        add_object(proj, mesh_type="cube", name="Table",
                   location=[0, 0, 0.4], scale=[1.5, 0.8, 0.4])
        add_modifier(proj, "bevel", 3, params={"width": 0.02, "segments": 2})

        # Materials
        create_material(proj, name="White Wall", color=[0.95, 0.95, 0.95, 1])
        create_material(proj, name="Wood", color=[0.45, 0.3, 0.15, 1], roughness=0.7)
        assign_material(proj, 1, 1)
        assign_material(proj, 1, 2)
        assign_material(proj, 2, 3)

        # Lighting
        add_light(proj, light_type="AREA", name="WindowLight",
                  location=[10, 5, 2.5], rotation=[0, -90, 0], power=2000)

        # Camera
        add_camera(proj, name="Interior", location=[5, -5, 1.7],
                   rotation=[90, 0, 45], focal_length=24, set_active=True)

        path = os.path.join(tmp_dir, "arch.json")
        save_scene(proj, path)
        loaded = open_scene(path)
        assert len(loaded["objects"]) == 4
        assert len(loaded["materials"]) == 3

    def test_modifier_stack_workflow(self, tmp_dir):
        """Build a complex modifier stack and verify it survives roundtrip."""
        proj = create_scene()
        add_object(proj, mesh_type="cube", name="Complex")

        add_modifier(proj, "subdivision_surface", 0, params={"levels": 1})
        add_modifier(proj, "bevel", 0, params={"width": 0.05, "segments": 3})
        add_modifier(proj, "array", 0, params={"count": 3, "relative_offset_x": 1.2})
        add_modifier(proj, "solidify", 0, params={"thickness": 0.02})

        assert len(proj["objects"][0]["modifiers"]) == 4

        path = os.path.join(tmp_dir, "modstack.json")
        save_scene(proj, path)
        loaded = open_scene(path)
        mods = loaded["objects"][0]["modifiers"]
        assert len(mods) == 4
        assert mods[0]["type"] == "subdivision_surface"
        assert mods[1]["type"] == "bevel"
        assert mods[2]["type"] == "array"
        assert mods[3]["type"] == "solidify"

    def test_multi_material_workflow(self):
        """Assign different materials to multiple objects."""
        proj = create_scene()

        # Create objects
        for name in ["Cube", "Sphere", "Cone", "Cylinder"]:
            add_object(proj, mesh_type=name.lower(), name=name)

        # Create materials
        colors = {
            "Red": [1, 0, 0, 1],
            "Green": [0, 1, 0, 1],
            "Blue": [0, 0, 1, 1],
            "Yellow": [1, 1, 0, 1],
        }
        for name, color in colors.items():
            create_material(proj, name=name, color=color)

        # Assign
        for i in range(4):
            assign_material(proj, i, i)

        # Verify
        for i, obj in enumerate(proj["objects"]):
            mat_id = obj["material"]
            mat = proj["materials"][i]
            assert mat_id == mat["id"]

    def test_undo_redo_workflow(self):
        """Test undo/redo through a complex editing workflow."""
        sess = Session()
        proj = create_scene(name="undo_test")
        sess.set_project(proj)

        # Step 1: Add object
        sess.snapshot("add cube")
        add_object(proj, name="Cube")
        assert len(proj["objects"]) == 1

        # Step 2: Add material
        sess.snapshot("add material")
        create_material(proj, name="Red", color=[1, 0, 0, 1])
        assert len(proj["materials"]) == 1

        # Step 3: Modify object
        sess.snapshot("move cube")
        transform_object(proj, 0, translate=[0, 0, 3])
        assert proj["objects"][0]["location"][2] == 3.0

        # Undo step 3
        sess.undo()
        assert sess.get_project()["objects"][0]["location"][2] == 0.0

        # Undo step 2
        sess.undo()
        assert len(sess.get_project()["materials"]) == 0

        # Redo step 2
        sess.redo()
        assert len(sess.get_project()["materials"]) == 1

        # Redo step 3
        sess.redo()
        assert sess.get_project()["objects"][0]["location"][2] == 3.0


# ── CLI Subprocess Tests ────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-blender")

    def _run(self, args, check=True, timeout=30):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            timeout=timeout,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Blender CLI" in result.stdout

    def test_scene_new(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["scene", "new", "-o", out])
        assert result.returncode == 0
        assert os.path.exists(out)

    def test_scene_new_json(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["--json", "scene", "new", "-o", out])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["render"]["resolution"] == "1920x1080"

    def test_scene_profiles(self):
        result = self._run(["scene", "profiles"])
        assert result.returncode == 0
        assert "hd1080p" in result.stdout

    def test_modifier_list_available(self):
        result = self._run(["modifier", "list-available"])
        assert result.returncode == 0
        assert "subdivision_surface" in result.stdout

    def test_render_presets(self):
        result = self._run(["render", "presets"])
        assert result.returncode == 0
        assert "cycles_default" in result.stdout

    def test_full_workflow_json(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "workflow.json")

        # Create scene
        self._run(["--json", "scene", "new", "-o", proj_path, "-n", "workflow"])

        # Add object and save (each subprocess is a separate session)
        self._run(["--json", "--project", proj_path,
                    "object", "add", "cube", "--name", "Box"])

        # Since each subprocess is a separate session, the object add above
        # loads the project, adds the object, but doesn't auto-save.
        # We need to verify the CLI works correctly in a single invocation.
        # Instead, verify the project file was created correctly and test
        # direct API roundtrip.
        assert os.path.exists(proj_path)
        with open(proj_path) as f:
            data = json.load(f)
        assert data["name"] == "workflow"

        # Test that the scene file is valid
        loaded_result = self._run(["--json", "--project", proj_path, "scene", "info"])
        assert loaded_result.returncode == 0
        info = json.loads(loaded_result.stdout)
        assert info["name"] == "workflow"

    def test_cli_error_handling(self):
        result = self._run(["scene", "open", "/nonexistent/file.json"], check=False)
        assert result.returncode != 0

    def test_cli_preview_capture(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "preview_scene.json")

        proj = create_scene(name="cli-preview", profile="preview")
        add_object(proj, mesh_type="plane", name="Ground", scale=[4, 4, 1])
        add_object(proj, mesh_type="cube", name="Product", location=[0, 0, 1])
        create_material(proj, name="Clay", color=[0.82, 0.5, 0.28, 1.0], roughness=0.35)
        assign_material(proj, 0, 1)
        add_camera(
            proj,
            name="PreviewCam",
            location=[6.5, -6.0, 4.5],
            rotation=[63, 0, 46],
            set_active=True,
        )
        add_light(proj, light_type="SUN", name="Sun", rotation=[-42, 0, 30], power=2.4)
        save_scene(proj, proj_path)

        result = self._run(
            ["--json", "--project", proj_path, "preview", "capture", "--root-dir", tmp_dir],
            check=False,
            timeout=240,
        )
        assert result.returncode == 0, result.stderr
        manifest = json.loads(result.stdout)
        assert manifest["software"] == "blender"
        hero_path = _artifact_path(manifest, "hero")
        workbench_path = _artifact_path(manifest, "workbench")
        _assert_png(hero_path)
        _assert_png(workbench_path)

        latest = self._run(
            ["--json", "preview", "latest", "--recipe", "quick", "--root-dir", tmp_dir],
            check=False,
            timeout=60,
        )
        assert latest.returncode == 0, latest.stderr
        latest_manifest = json.loads(latest.stdout)
        assert latest_manifest["bundle_id"] == manifest["bundle_id"]

        print(f"\n  Blender preview bundle: {manifest['_bundle_dir']}")
        print(f"  Blender preview hero: {hero_path}")
        print(f"  Blender preview workbench: {workbench_path}")

    def test_cli_preview_live_manual_session(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "preview_live_manual.json")
        live_root = os.path.join(tmp_dir, "live-root")

        proj = create_scene(name="cli-live-manual", profile="preview")
        add_object(proj, mesh_type="plane", name="Ground", scale=[5, 5, 1])
        add_object(proj, mesh_type="torus", name="RingA", location=[0, 0, 1.3], rotation=[90, 0, 0])
        add_object(proj, mesh_type="sphere", name="Core", location=[0, 0, 1.3], scale=[0.55, 0.55, 0.55])
        create_material(proj, name="Brass", color=[0.83, 0.7, 0.28, 1.0], metallic=0.85, roughness=0.25)
        create_material(proj, name="CoreGlow", color=[0.2, 0.85, 1.0, 1.0], metallic=0.0, roughness=0.1)
        set_material_property(proj, 1, "emission_color", [0.2, 0.85, 1.0, 1.0])
        set_material_property(proj, 1, "emission_strength", 3.5)
        assign_material(proj, 0, 1)
        assign_material(proj, 1, 2)
        add_camera(proj, name="MainCam", location=[7, -7, 5], rotation=[63, 0, 46], set_active=True)
        add_light(proj, light_type="SUN", name="Sun", rotation=[-42, 0, 30], power=2.4)
        save_scene(proj, proj_path)

        started = self._run(
            [
                "--json",
                "--project",
                proj_path,
                "preview",
                "live",
                "start",
                "--recipe",
                "quick",
                "--mode",
                "manual",
                "--root-dir",
                live_root,
            ],
            check=False,
            timeout=240,
        )
        assert started.returncode == 0, started.stderr
        started_payload = json.loads(started.stdout)
        assert started_payload["live_mode"] == "manual"
        assert started_payload["bundle_count"] == 1
        session_path = started_payload["_session_path"]
        assert os.path.isfile(session_path)

        status = self._run(
            [
                "--json",
                "--project",
                proj_path,
                "preview",
                "live",
                "status",
                "--recipe",
                "quick",
                "--root-dir",
                live_root,
            ],
            check=False,
            timeout=60,
        )
        assert status.returncode == 0, status.stderr
        status_payload = json.loads(status.stdout)
        assert status_payload["current_bundle_id"] == started_payload["current_bundle_id"]

        pushed = self._run(
            [
                "--json",
                "--project",
                proj_path,
                "preview",
                "live",
                "push",
                "--recipe",
                "quick",
                "--force",
                "--root-dir",
                live_root,
            ],
            check=False,
            timeout=240,
        )
        assert pushed.returncode == 0, pushed.stderr
        pushed_payload = json.loads(pushed.stdout)
        assert pushed_payload["bundle_count"] >= 2

        stopped = self._run(
            [
                "--json",
                "--project",
                proj_path,
                "preview",
                "live",
                "stop",
                "--recipe",
                "quick",
                "--root-dir",
                live_root,
            ],
            check=False,
            timeout=60,
        )
        assert stopped.returncode == 0, stopped.stderr
        stopped_payload = json.loads(stopped.stdout)
        assert stopped_payload["status"] == "stopped"


class TestPreviewE2E:
    @staticmethod
    def _run_cli(args, check=False, timeout=240):
        return subprocess.run(
            TestCLISubprocess.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )

    def test_capture_preview_bundle(self, tmp_dir):
        proj = create_scene(name="preview-test", profile="preview")
        add_object(proj, mesh_type="plane", name="Ground", scale=[5, 5, 1])
        add_object(proj, mesh_type="cube", name="Body", location=[0, 0, 1], scale=[1.2, 1.2, 1.2])
        add_object(proj, mesh_type="sphere", name="Accent", location=[2.2, 0.3, 1.0], scale=[0.7, 0.7, 0.7])
        create_material(proj, name="OrangeClay", color=[0.84, 0.45, 0.19, 1.0], roughness=0.32)
        create_material(proj, name="BlueAccent", color=[0.18, 0.42, 0.82, 1.0], metallic=0.1, roughness=0.25)
        assign_material(proj, 0, 1)
        assign_material(proj, 1, 2)
        add_camera(
            proj,
            name="MainCam",
            location=[7, -6, 5],
            rotation=[63, 0, 46],
            focal_length=50,
            set_active=True,
        )
        add_light(proj, light_type="SUN", name="KeySun", rotation=[-45, 0, 30], power=2.3)

        proj_path = os.path.join(tmp_dir, "preview_scene.json")
        save_scene(proj, proj_path)

        sess = Session()
        sess.set_project(proj, path=proj_path)

        manifest = preview_mod.capture(sess, root_dir=tmp_dir, force=True)
        assert manifest["software"] == "blender"
        assert manifest["bundle_kind"] == "capture"
        assert manifest["status"] in ("ok", "partial")

        hero_path = _artifact_path(manifest, "hero")
        workbench_path = _artifact_path(manifest, "workbench")
        _assert_png(hero_path)
        _assert_png(workbench_path)

        latest = preview_mod.latest(project_path=proj_path, recipe="quick", root_dir=tmp_dir)
        assert latest["bundle_id"] == manifest["bundle_id"]

        print(f"\n  Blender preview bundle: {manifest['_bundle_dir']}")
        print(f"  Blender preview hero: {hero_path}")
        print(f"  Blender preview workbench: {workbench_path}")

    def test_preview_live_poll_auto_refresh(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "preview_live_poll.json")
        live_root = os.path.join(tmp_dir, "live-root")

        proj = create_scene(name="poll-live", profile="preview")
        add_object(proj, mesh_type="plane", name="Ground", scale=[6, 6, 1])
        add_object(proj, mesh_type="torus", name="RingA", location=[0, 0, 1.35], rotation=[90, 0, 0])
        add_object(proj, mesh_type="sphere", name="Core", location=[0, 0, 1.35], scale=[0.45, 0.45, 0.45])
        create_material(proj, name="Bronze", color=[0.79, 0.58, 0.24, 1.0], metallic=0.9, roughness=0.22)
        create_material(proj, name="AzureCore", color=[0.22, 0.7, 0.95, 1.0], metallic=0.0, roughness=0.12)
        set_material_property(proj, 1, "emission_color", [0.22, 0.7, 0.95, 1.0])
        set_material_property(proj, 1, "emission_strength", 4.2)
        assign_material(proj, 0, 1)
        assign_material(proj, 1, 2)
        add_camera(proj, name="MainCam", location=[7.5, -7.0, 5.5], rotation=[63, 0, 46], set_active=True)
        add_light(proj, light_type="SUN", name="Sun", rotation=[-42, 0, 30], power=2.5)
        save_scene(proj, proj_path)

        started = self._run_cli(
            [
                "--json",
                "--project",
                proj_path,
                "preview",
                "live",
                "start",
                "--recipe",
                "quick",
                "--mode",
                "poll",
                "--source-poll-ms",
                "500",
                "--poll-ms",
                "700",
                "--root-dir",
                live_root,
            ],
            check=False,
            timeout=240,
        )
        assert started.returncode == 0, started.stderr
        started_payload = json.loads(started.stdout)
        assert started_payload["bundle_count"] == 1
        assert started_payload["live_mode"] == "poll"
        session_path = started_payload["_session_path"]

        try:
            changed = self._run_cli(
                [
                    "--json",
                    "--project",
                    proj_path,
                    "object",
                    "add",
                    "torus",
                    "--name",
                    "RingB",
                    "--location",
                    "0,0,1.35",
                    "--rotation",
                    "0,90,0",
                    "--scale",
                    "0.7,0.7,0.7",
                ],
                check=False,
                timeout=90,
            )
            assert changed.returncode == 0, changed.stderr

            session_payload = _wait_for_live_bundle_count(session_path, 2, timeout_s=45.0)
            assert session_payload["bundle_count"] >= 2
            assert session_payload["source_state"]["last_publish_reason"] == "auto-poll"
            assert session_payload["poller"]["running"] is True

            current_manifest_path = session_payload["current_manifest_path"]
            assert os.path.isfile(current_manifest_path)
            with open(current_manifest_path, "r", encoding="utf-8") as fh:
                current_manifest = json.load(fh)
            current_manifest["_bundle_dir"] = os.path.dirname(current_manifest_path)
            hero_path = _artifact_path(current_manifest, "hero")
            _assert_png(hero_path)

            print(f"\n  Blender poll session: {os.path.dirname(session_path)}")
            print(f"  Blender live hero: {hero_path}")
        finally:
            stopped = self._run_cli(
                [
                    "--json",
                    "--project",
                    proj_path,
                    "preview",
                    "live",
                    "stop",
                    "--recipe",
                    "quick",
                    "--root-dir",
                    live_root,
                ],
                check=False,
                timeout=60,
            )
            assert stopped.returncode == 0, stopped.stderr


# ── Script Validity Tests ───────────────────────────────────────

class TestScriptValidity:
    """Verify generated bpy scripts are valid Python syntax."""

    def test_script_is_valid_python(self):
        """Ensure generated scripts parse as valid Python."""
        proj = create_scene()
        add_object(proj, mesh_type="cube", name="Test")
        add_camera(proj, name="Cam")
        add_light(proj, name="Light")
        create_material(proj, name="Mat")
        assign_material(proj, 0, 0)
        add_modifier(proj, "subdivision_surface", 0)
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])

        script = generate_full_script(proj, "/tmp/render.png")

        # Verify it parses as Python
        compile(script, "<bpy_script>", "exec")

    def test_complex_script_is_valid_python(self):
        """Ensure a complex scene generates valid Python."""
        proj = create_scene(engine="EEVEE")

        for prim in ["cube", "sphere", "cylinder", "cone", "plane", "torus", "monkey"]:
            add_object(proj, mesh_type=prim)

        for i in range(7):
            create_material(proj, name=f"Mat{i}", color=[i/7.0, 0.5, 1-i/7.0, 1.0])
            assign_material(proj, i, i)

        add_modifier(proj, "subdivision_surface", 0)
        add_modifier(proj, "mirror", 1)
        add_modifier(proj, "array", 2, params={"count": 3})
        add_modifier(proj, "bevel", 3, params={"width": 0.1})
        add_modifier(proj, "solidify", 4, params={"thickness": 0.02})
        add_modifier(proj, "boolean", 5, params={"operation": "UNION"})
        add_modifier(proj, "smooth", 6, params={"iterations": 5})

        add_camera(proj, name="Cam", set_active=True)
        add_light(proj, light_type="POINT")
        add_light(proj, light_type="SUN")
        add_light(proj, light_type="SPOT")
        add_light(proj, light_type="AREA")

        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        add_keyframe(proj, 0, 60, "location", [5, 0, 0])
        add_keyframe(proj, 0, 1, "rotation", [0, 0, 0])
        add_keyframe(proj, 0, 60, "rotation", [0, 0, 360])
        add_keyframe(proj, 0, 1, "scale", [1, 1, 1])
        add_keyframe(proj, 0, 60, "scale", [2, 2, 2])

        script = generate_full_script(proj, "/tmp/render.png", animation=True)
        compile(script, "<complex_bpy_script>", "exec")

    def test_animation_script_is_valid_python(self):
        proj = create_scene()
        add_object(proj, mesh_type="sphere", name="Ball")
        add_keyframe(proj, 0, 1, "location", [0, 0, 5])
        add_keyframe(proj, 0, 60, "location", [0, 0, 0])
        add_keyframe(proj, 0, 30, "visible", True)

        script = generate_full_script(proj, "/tmp/anim_", animation=True)
        compile(script, "<anim_script>", "exec")


# ── True Backend E2E Tests (requires Blender installed) ──────────

class TestBlenderBackend:
    """Tests that verify Blender is installed and accessible."""

    def test_blender_is_installed(self):
        from cli_anything.blender.utils.blender_backend import find_blender
        path = find_blender()
        assert os.path.exists(path)
        print(f"\n  Blender binary: {path}")

    def test_blender_version(self):
        from cli_anything.blender.utils.blender_backend import get_version
        version = get_version()
        assert "Blender" in version
        print(f"\n  Blender version: {version}")


class TestBlenderRenderE2E:
    """True E2E tests: generate scene → bpy script → blender --background → verify output."""

    def test_render_simple_cube(self, tmp_dir):
        """Render a simple cube scene with Blender."""
        from cli_anything.blender.utils.blender_backend import render_scene_headless

        proj = create_scene(name="simple_cube", engine="WORKBENCH", samples=1)
        set_render_settings(proj, resolution_x=320, resolution_y=240,
                           resolution_percentage=100, engine="WORKBENCH", samples=1)

        add_object(proj, mesh_type="cube", name="TestCube", location=[0, 0, 0])
        add_camera(proj, name="Cam", location=[5, -5, 3],
                   rotation=[63, 0, 46], set_active=True)
        add_light(proj, light_type="SUN", name="Sun", rotation=[-45, 0, 30])

        output_path = os.path.join(tmp_dir, "cube_render.png")
        script = generate_full_script(proj, output_path)

        result = render_scene_headless(script, output_path, timeout=120)

        assert os.path.exists(result["output"])
        assert result["file_size"] > 0
        assert result["method"] == "blender-headless"
        print(f"\n  Rendered cube: {result['output']} ({result['file_size']:,} bytes)")

    def test_render_sphere_with_material(self, tmp_dir):
        """Render a sphere with material."""
        from cli_anything.blender.utils.blender_backend import render_scene_headless

        proj = create_scene(name="material_sphere", engine="WORKBENCH", samples=1)
        set_render_settings(proj, resolution_x=320, resolution_y=240, engine="WORKBENCH", samples=1)

        add_object(proj, mesh_type="sphere", name="Ball", location=[0, 0, 0])
        create_material(proj, name="RedMetal", color=[0.8, 0.1, 0.1, 1.0],
                        metallic=0.9, roughness=0.2)
        assign_material(proj, 0, 0)

        add_camera(proj, name="Cam", location=[4, -4, 3],
                   rotation=[60, 0, 45], set_active=True)
        add_light(proj, light_type="POINT", name="Key", location=[3, -3, 5], power=500)

        output_path = os.path.join(tmp_dir, "sphere_render.png")
        script = generate_full_script(proj, output_path)

        result = render_scene_headless(script, output_path, timeout=120)

        assert os.path.exists(result["output"])
        assert result["file_size"] > 100  # Real PNG should be > 100 bytes
        print(f"\n  Rendered sphere: {result['output']} ({result['file_size']:,} bytes)")

    def test_render_complex_scene(self, tmp_dir):
        """Render a complex scene with multiple objects, materials, lights."""
        from cli_anything.blender.utils.blender_backend import render_scene_headless

        proj = create_scene(name="complex", engine="WORKBENCH", samples=1)
        set_render_settings(proj, resolution_x=320, resolution_y=240, engine="WORKBENCH", samples=1)

        # Ground plane
        add_object(proj, mesh_type="plane", name="Ground", scale=[5, 5, 1])
        create_material(proj, name="Floor", color=[0.3, 0.3, 0.3, 1], roughness=0.9)
        assign_material(proj, 0, 0)

        # Objects
        add_object(proj, mesh_type="monkey", name="Suzanne", location=[0, 0, 1])
        create_material(proj, name="Gold", color=[1.0, 0.8, 0.2, 1],
                        metallic=1.0, roughness=0.2)
        assign_material(proj, 1, 1)

        add_object(proj, mesh_type="cylinder", name="Pillar", location=[3, 0, 1])
        create_material(proj, name="Stone", color=[0.6, 0.6, 0.6, 1], roughness=0.8)
        assign_material(proj, 2, 2)

        # Camera and lights
        add_camera(proj, name="Cam", location=[7, -6, 5],
                   rotation=[63, 0, 46], focal_length=50, set_active=True)
        add_light(proj, light_type="SUN", name="Sun", rotation=[-45, 0, 30])
        add_light(proj, light_type="AREA", name="Fill", location=[-3, 3, 3], power=300)

        output_path = os.path.join(tmp_dir, "complex_render.png")
        script = generate_full_script(proj, output_path)

        result = render_scene_headless(script, output_path, timeout=180)

        assert os.path.exists(result["output"])
        assert result["file_size"] > 100
        print(f"\n  Rendered complex scene: {result['output']} ({result['file_size']:,} bytes)")

    def test_render_with_modifiers(self, tmp_dir):
        """Render an object with subdivision surface modifier."""
        from cli_anything.blender.utils.blender_backend import render_scene_headless

        proj = create_scene(name="modifiers", engine="WORKBENCH", samples=1)
        set_render_settings(proj, resolution_x=320, resolution_y=240, engine="WORKBENCH", samples=1)

        add_object(proj, mesh_type="cube", name="SmoothCube", location=[0, 0, 0])
        add_modifier(proj, "subdivision_surface", 0, params={"levels": 2, "render_levels": 2})
        create_material(proj, name="Blue", color=[0.1, 0.3, 0.8, 1])
        assign_material(proj, 0, 0)

        add_camera(proj, name="Cam", location=[4, -4, 3],
                   rotation=[60, 0, 45], set_active=True)
        add_light(proj, light_type="SUN", name="Sun")

        output_path = os.path.join(tmp_dir, "modifier_render.png")
        script = generate_full_script(proj, output_path)

        result = render_scene_headless(script, output_path, timeout=120)

        assert os.path.exists(result["output"])
        assert result["file_size"] > 100
        print(f"\n  Rendered with modifiers: {result['output']} ({result['file_size']:,} bytes)")

    def test_render_jpeg_format(self, tmp_dir):
        """Render to JPEG format."""
        from cli_anything.blender.utils.blender_backend import render_scene_headless

        proj = create_scene(name="jpeg_test", engine="WORKBENCH", samples=1)
        set_render_settings(proj, resolution_x=320, resolution_y=240,
                           engine="WORKBENCH", samples=1, output_format="JPEG")

        add_object(proj, mesh_type="sphere", name="Ball")
        add_camera(proj, name="Cam", location=[4, -4, 3],
                   rotation=[60, 0, 45], set_active=True)
        add_light(proj, light_type="SUN", name="Sun")

        output_path = os.path.join(tmp_dir, "render.jpg")
        script = generate_full_script(proj, output_path)

        result = render_scene_headless(script, output_path, timeout=120)

        assert os.path.exists(result["output"])
        assert result["file_size"] > 100
        print(f"\n  Rendered JPEG: {result['output']} ({result['file_size']:,} bytes)")


class TestBlenderRenderScriptE2E:
    """Test the render_script function directly."""

    def test_run_minimal_bpy_script(self, tmp_dir):
        """Run a minimal bpy script through Blender."""
        from cli_anything.blender.utils.blender_backend import render_script

        script_path = os.path.join(tmp_dir, "test_script.py")
        output_path = os.path.join(tmp_dir, "minimal.png")

        script_content = f'''
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cam_data = bpy.data.cameras.new(name='Camera')
cam_obj = bpy.data.objects.new('Camera', cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (5, -5, 3)
cam_obj.rotation_euler = (1.1, 0, 0.8)
bpy.context.scene.camera = cam_obj
light_data = bpy.data.lights.new(name='Light', type='SUN')
light_obj = bpy.data.objects.new('Light', light_data)
bpy.context.collection.objects.link(light_obj)
bpy.context.scene.render.resolution_x = 160
bpy.context.scene.render.resolution_y = 120
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.filepath = r'{output_path}'
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print('Render complete')
'''
        with open(script_path, 'w') as f:
            f.write(script_content)

        result = render_script(script_path, timeout=120)
        assert result["returncode"] == 0, f"Blender failed: {result['stderr'][-500:]}"

        # Blender may append frame number
        actual_output = output_path
        if not os.path.exists(actual_output):
            base, ext = os.path.splitext(output_path)
            for suffix in ["0001", "0000"]:
                candidate = f"{base}{suffix}{ext}"
                if os.path.exists(candidate):
                    actual_output = candidate
                    break

        assert os.path.exists(actual_output), f"No output file found. stdout: {result['stdout'][-500:]}"
        size = os.path.getsize(actual_output)
        assert size > 0
        print(f"\n  Minimal render: {actual_output} ({size:,} bytes)")
