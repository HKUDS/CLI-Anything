"""Unit tests for Blender CLI core modules.

Tests use synthetic data only — no real 3D files or Blender installation.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.blender.core.scene import create_scene, open_scene, save_scene, get_scene_info, list_profiles
from cli_anything.blender.core.objects import (
    add_object, remove_object, duplicate_object, transform_object,
    set_object_property, get_object, list_objects, MESH_PRIMITIVES,
)
from cli_anything.blender.core.materials import (
    create_material, assign_material, set_material_property,
    list_materials, get_material, MATERIAL_PROPS,
)
from cli_anything.blender.core.modifiers import (
    list_available, get_modifier_info, validate_params, add_modifier,
    remove_modifier, set_modifier_param, list_modifiers, MODIFIER_REGISTRY,
)
from cli_anything.blender.core.lighting import (
    add_camera, set_camera, set_active_camera, list_cameras, get_camera,
    add_light, set_light, list_lights, get_light,
    CAMERA_TYPES, LIGHT_TYPES,
)
from cli_anything.blender.core.animation import (
    add_keyframe, remove_keyframe, set_frame_range, set_fps,
    set_current_frame, list_keyframes, ANIMATABLE_PROPERTIES,
)
from cli_anything.blender.core.render import (
    set_render_settings, get_render_settings, list_render_presets,
    render_scene, RENDER_PRESETS, VALID_ENGINES,
)
from cli_anything.blender.core.session import Session


# ── Scene Tests ─────────────────────────────────────────────────

class TestScene:
    def test_create_default(self):
        proj = create_scene()
        assert proj["render"]["resolution_x"] == 1920
        assert proj["render"]["resolution_y"] == 1080
        assert proj["render"]["engine"] == "CYCLES"
        assert proj["version"] == "1.0"
        assert proj["scene"]["fps"] == 24

    def test_create_with_dimensions(self):
        proj = create_scene(resolution_x=800, resolution_y=600, samples=64)
        assert proj["render"]["resolution_x"] == 800
        assert proj["render"]["resolution_y"] == 600
        assert proj["render"]["samples"] == 64

    def test_create_with_profile(self):
        proj = create_scene(profile="hd720p")
        assert proj["render"]["resolution_x"] == 1280
        assert proj["render"]["resolution_y"] == 720

    def test_create_with_4k_profile(self):
        proj = create_scene(profile="4k")
        assert proj["render"]["resolution_x"] == 3840
        assert proj["render"]["resolution_y"] == 2160

    def test_create_invalid_engine(self):
        with pytest.raises(ValueError, match="Invalid render engine"):
            create_scene(engine="INVALID")

    def test_create_invalid_resolution(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_scene(resolution_x=0, resolution_y=100)

    def test_create_invalid_samples(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_scene(samples=0)

    def test_create_invalid_fps(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_scene(fps=0)

    def test_create_invalid_frame_range(self):
        with pytest.raises(ValueError, match="must be >= frame start"):
            create_scene(frame_start=100, frame_end=50)

    def test_save_and_open(self):
        proj = create_scene(name="test_scene")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_scene(proj, path)
            loaded = open_scene(path)
            assert loaded["name"] == "test_scene"
            assert loaded["render"]["resolution_x"] == 1920
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_scene("/nonexistent/path.json")

    def test_get_info(self):
        proj = create_scene(name="info_test")
        info = get_scene_info(proj)
        assert info["name"] == "info_test"
        assert info["counts"]["objects"] == 0
        assert "render" in info

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) > 0
        names = [p["name"] for p in profiles]
        assert "hd1080p" in names
        assert "4k" in names
        assert "default" in names

    def test_scene_has_collections(self):
        proj = create_scene()
        assert len(proj["collections"]) == 1
        assert proj["collections"][0]["name"] == "Collection"

    def test_scene_has_world(self):
        proj = create_scene()
        assert "world" in proj
        assert "background_color" in proj["world"]

    def test_eevee_engine(self):
        proj = create_scene(engine="EEVEE")
        assert proj["render"]["engine"] == "EEVEE"


# ── Object Tests ────────────────────────────────────────────────

class TestObjects:
    def _make_scene(self):
        return create_scene()

    def test_add_cube(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="cube", name="TestCube")
        assert obj["name"] == "TestCube"
        assert obj["type"] == "MESH"
        assert obj["mesh_type"] == "cube"
        assert len(proj["objects"]) == 1

    def test_add_sphere(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="sphere")
        assert obj["mesh_type"] == "sphere"
        assert obj["mesh_params"]["radius"] == 1.0
        assert obj["mesh_params"]["segments"] == 32

    def test_add_all_primitives(self):
        proj = self._make_scene()
        for prim in MESH_PRIMITIVES:
            obj = add_object(proj, mesh_type=prim)
            assert obj["mesh_type"] == prim
        assert len(proj["objects"]) == len(MESH_PRIMITIVES)

    def test_add_with_location(self):
        proj = self._make_scene()
        obj = add_object(proj, location=[1.0, 2.0, 3.0])
        assert obj["location"] == [1.0, 2.0, 3.0]

    def test_add_with_rotation_and_scale(self):
        proj = self._make_scene()
        obj = add_object(proj, rotation=[90.0, 0.0, 45.0], scale=[2.0, 2.0, 2.0])
        assert obj["rotation"] == [90.0, 0.0, 45.0]
        assert obj["scale"] == [2.0, 2.0, 2.0]

    def test_add_with_custom_params(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="sphere", mesh_params={"radius": 2.5, "segments": 64})
        assert obj["mesh_params"]["radius"] == 2.5
        assert obj["mesh_params"]["segments"] == 64

    def test_add_invalid_mesh_type(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Unknown mesh type"):
            add_object(proj, mesh_type="octahedron")

    def test_add_invalid_location(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="3 components"):
            add_object(proj, location=[1.0, 2.0])

    def test_unique_names(self):
        proj = self._make_scene()
        obj1 = add_object(proj, name="Cube")
        obj2 = add_object(proj, name="Cube")
        assert obj1["name"] != obj2["name"]

    def test_unique_ids(self):
        proj = self._make_scene()
        obj1 = add_object(proj, name="A")
        obj2 = add_object(proj, name="B")
        assert obj1["id"] != obj2["id"]

    def test_remove_object(self):
        proj = self._make_scene()
        add_object(proj, name="A")
        add_object(proj, name="B")
        removed = remove_object(proj, 0)
        assert removed["name"] == "A"
        assert len(proj["objects"]) == 1

    def test_remove_object_empty(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="No objects"):
            remove_object(proj, 0)

    def test_remove_object_invalid_index(self):
        proj = self._make_scene()
        add_object(proj)
        with pytest.raises(IndexError):
            remove_object(proj, 5)

    def test_duplicate_object(self):
        proj = self._make_scene()
        add_object(proj, name="Original")
        dup = duplicate_object(proj, 0)
        assert "copy" in dup["name"].lower() or "Original" in dup["name"]
        assert len(proj["objects"]) == 2
        assert dup["id"] != proj["objects"][0]["id"]

    def test_transform_translate(self):
        proj = self._make_scene()
        add_object(proj, location=[0, 0, 0])
        obj = transform_object(proj, 0, translate=[1.0, 2.0, 3.0])
        assert obj["location"] == [1.0, 2.0, 3.0]

    def test_transform_rotate(self):
        proj = self._make_scene()
        add_object(proj, rotation=[0, 0, 0])
        obj = transform_object(proj, 0, rotate=[90.0, 0.0, 0.0])
        assert obj["rotation"] == [90.0, 0.0, 0.0]

    def test_transform_scale(self):
        proj = self._make_scene()
        add_object(proj, scale=[1, 1, 1])
        obj = transform_object(proj, 0, scale=[2.0, 3.0, 4.0])
        assert obj["scale"] == [2.0, 3.0, 4.0]

    def test_transform_compound(self):
        proj = self._make_scene()
        add_object(proj, location=[1, 0, 0])
        obj = transform_object(proj, 0, translate=[1, 0, 0], scale=[2, 2, 2])
        assert obj["location"] == [2.0, 0.0, 0.0]
        assert obj["scale"] == [2.0, 2.0, 2.0]

    def test_set_property_name(self):
        proj = self._make_scene()
        add_object(proj, name="Old")
        set_object_property(proj, 0, "name", "New")
        assert proj["objects"][0]["name"] == "New"

    def test_set_property_visible(self):
        proj = self._make_scene()
        add_object(proj)
        set_object_property(proj, 0, "visible", "false")
        assert proj["objects"][0]["visible"] is False

    def test_set_property_invalid(self):
        proj = self._make_scene()
        add_object(proj)
        with pytest.raises(ValueError, match="Unknown property"):
            set_object_property(proj, 0, "bogus", "value")

    def test_get_object(self):
        proj = self._make_scene()
        add_object(proj, name="Test")
        obj = get_object(proj, 0)
        assert obj["name"] == "Test"

    def test_list_objects(self):
        proj = self._make_scene()
        add_object(proj, name="A")
        add_object(proj, name="B")
        result = list_objects(proj)
        assert len(result) == 2

    def test_object_added_to_collection(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="cube")
        assert obj["id"] in proj["collections"][0]["objects"]

    def test_empty_object(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="empty")
        assert obj["type"] == "EMPTY"

    def test_add_monkey(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="monkey")
        assert obj["mesh_type"] == "monkey"

    def test_add_torus_with_params(self):
        proj = self._make_scene()
        obj = add_object(proj, mesh_type="torus",
                         mesh_params={"major_radius": 2.0, "minor_radius": 0.5})
        assert obj["mesh_params"]["major_radius"] == 2.0
        assert obj["mesh_params"]["minor_radius"] == 0.5


# ── Material Tests ──────────────────────────────────────────────

class TestMaterials:
    def _make_scene(self):
        return create_scene()

    def test_create_material(self):
        proj = self._make_scene()
        mat = create_material(proj, name="Red")
        assert mat["name"] == "Red"
        assert mat["type"] == "principled"
        assert len(proj["materials"]) == 1

    def test_create_material_with_color(self):
        proj = self._make_scene()
        mat = create_material(proj, color=[1.0, 0.0, 0.0, 1.0])
        assert mat["color"] == [1.0, 0.0, 0.0, 1.0]

    def test_create_material_3_component_color(self):
        proj = self._make_scene()
        mat = create_material(proj, color=[1.0, 0.0, 0.0])
        assert mat["color"] == [1.0, 0.0, 0.0, 1.0]

    def test_create_material_invalid_color(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="must be 0.0-1.0"):
            create_material(proj, color=[2.0, 0.0, 0.0, 1.0])

    def test_create_material_invalid_metallic(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Metallic must be"):
            create_material(proj, metallic=1.5)

    def test_create_material_invalid_roughness(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Roughness must be"):
            create_material(proj, roughness=-0.1)

    def test_unique_material_names(self):
        proj = self._make_scene()
        m1 = create_material(proj, name="Mat")
        m2 = create_material(proj, name="Mat")
        assert m1["name"] != m2["name"]

    def test_assign_material(self):
        proj = self._make_scene()
        mat = create_material(proj, name="Metal")
        add_object(proj, name="Cube")
        result = assign_material(proj, 0, 0)
        assert result["material"] == "Metal"
        assert proj["objects"][0]["material"] == mat["id"]

    def test_assign_material_invalid_indices(self):
        proj = self._make_scene()
        with pytest.raises(IndexError):
            assign_material(proj, 0, 0)

    def test_set_material_property_metallic(self):
        proj = self._make_scene()
        create_material(proj)
        set_material_property(proj, 0, "metallic", 1.0)
        assert proj["materials"][0]["metallic"] == 1.0

    def test_set_material_property_roughness(self):
        proj = self._make_scene()
        create_material(proj)
        set_material_property(proj, 0, "roughness", 0.1)
        assert proj["materials"][0]["roughness"] == 0.1

    def test_set_material_property_color(self):
        proj = self._make_scene()
        create_material(proj)
        set_material_property(proj, 0, "color", [1.0, 0.0, 0.0, 1.0])
        assert proj["materials"][0]["color"] == [1.0, 0.0, 0.0, 1.0]

    def test_set_material_property_invalid(self):
        proj = self._make_scene()
        create_material(proj)
        with pytest.raises(ValueError, match="Unknown material property"):
            set_material_property(proj, 0, "bogus", 1.0)

    def test_set_material_property_out_of_range(self):
        proj = self._make_scene()
        create_material(proj)
        with pytest.raises(ValueError, match="maximum"):
            set_material_property(proj, 0, "metallic", 2.0)

    def test_list_materials(self):
        proj = self._make_scene()
        create_material(proj, name="A")
        create_material(proj, name="B")
        result = list_materials(proj)
        assert len(result) == 2

    def test_get_material(self):
        proj = self._make_scene()
        create_material(proj, name="Test")
        mat = get_material(proj, 0)
        assert mat["name"] == "Test"


# ── Modifier Tests ──────────────────────────────────────────────

class TestModifiers:
    def _make_scene_with_object(self):
        proj = create_scene()
        add_object(proj, name="Cube")
        return proj

    def test_list_available(self):
        mods = list_available()
        assert len(mods) >= 8
        names = [m["name"] for m in mods]
        assert "subdivision_surface" in names
        assert "mirror" in names
        assert "array" in names

    def test_list_by_category(self):
        gen = list_available(category="generate")
        assert all(m["category"] == "generate" for m in gen)
        assert len(gen) >= 5

    def test_get_modifier_info(self):
        info = get_modifier_info("subdivision_surface")
        assert info["name"] == "subdivision_surface"
        assert "levels" in info["params"]

    def test_get_modifier_info_unknown(self):
        with pytest.raises(ValueError, match="Unknown modifier"):
            get_modifier_info("nonexistent")

    def test_validate_params(self):
        params = validate_params("subdivision_surface", {"levels": 3})
        assert params["levels"] == 3
        assert params["render_levels"] == 2  # default

    def test_validate_params_defaults(self):
        params = validate_params("subdivision_surface", {})
        assert params["levels"] == 1

    def test_validate_params_out_of_range(self):
        with pytest.raises(ValueError, match="maximum"):
            validate_params("subdivision_surface", {"levels": 10})

    def test_validate_params_unknown(self):
        with pytest.raises(ValueError, match="Unknown parameters"):
            validate_params("subdivision_surface", {"bogus": 1})

    def test_add_modifier(self):
        proj = self._make_scene_with_object()
        result = add_modifier(proj, "subdivision_surface", 0, params={"levels": 2})
        assert result["type"] == "subdivision_surface"
        assert result["params"]["levels"] == 2
        assert len(proj["objects"][0]["modifiers"]) == 1

    def test_add_modifier_invalid_object(self):
        proj = self._make_scene_with_object()
        with pytest.raises(IndexError):
            add_modifier(proj, "subdivision_surface", 5)

    def test_add_modifier_unknown(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="Unknown modifier"):
            add_modifier(proj, "nonexistent", 0)

    def test_remove_modifier(self):
        proj = self._make_scene_with_object()
        add_modifier(proj, "subdivision_surface", 0)
        removed = remove_modifier(proj, 0, 0)
        assert removed["type"] == "subdivision_surface"
        assert len(proj["objects"][0]["modifiers"]) == 0

    def test_set_modifier_param(self):
        proj = self._make_scene_with_object()
        add_modifier(proj, "subdivision_surface", 0, params={"levels": 1})
        set_modifier_param(proj, 0, "levels", 3, 0)
        assert proj["objects"][0]["modifiers"][0]["params"]["levels"] == 3

    def test_set_modifier_param_invalid(self):
        proj = self._make_scene_with_object()
        add_modifier(proj, "subdivision_surface", 0)
        with pytest.raises(ValueError, match="Unknown parameter"):
            set_modifier_param(proj, 0, "bogus", 1, 0)

    def test_list_modifiers(self):
        proj = self._make_scene_with_object()
        add_modifier(proj, "subdivision_surface", 0)
        add_modifier(proj, "mirror", 0)
        result = list_modifiers(proj, 0)
        assert len(result) == 2
        assert result[0]["type"] == "subdivision_surface"
        assert result[1]["type"] == "mirror"

    def test_all_modifiers_have_valid_bpy_type(self):
        for name, spec in MODIFIER_REGISTRY.items():
            assert "bpy_type" in spec, f"Modifier '{name}' missing bpy_type"
            assert spec["bpy_type"], f"Modifier '{name}' has empty bpy_type"

    def test_array_modifier(self):
        proj = self._make_scene_with_object()
        result = add_modifier(proj, "array", 0, params={"count": 5})
        assert result["params"]["count"] == 5

    def test_bevel_modifier(self):
        proj = self._make_scene_with_object()
        result = add_modifier(proj, "bevel", 0, params={"width": 0.5, "segments": 3})
        assert result["params"]["width"] == 0.5
        assert result["params"]["segments"] == 3

    def test_solidify_modifier(self):
        proj = self._make_scene_with_object()
        result = add_modifier(proj, "solidify", 0, params={"thickness": 0.1})
        assert result["params"]["thickness"] == 0.1

    def test_boolean_modifier(self):
        proj = self._make_scene_with_object()
        result = add_modifier(proj, "boolean", 0, params={"operation": "UNION"})
        assert result["params"]["operation"] == "UNION"


# ── Lighting Tests ──────────────────────────────────────────────

class TestLighting:
    def _make_scene(self):
        return create_scene()

    # Camera tests
    def test_add_camera(self):
        proj = self._make_scene()
        cam = add_camera(proj, name="Main Camera")
        assert cam["name"] == "Main Camera"
        assert cam["type"] == "PERSP"
        assert len(proj["cameras"]) == 1

    def test_add_camera_auto_active(self):
        proj = self._make_scene()
        cam = add_camera(proj)
        assert cam["is_active"] is True

    def test_add_camera_with_position(self):
        proj = self._make_scene()
        cam = add_camera(proj, location=[5, -5, 3], rotation=[60, 0, 45])
        assert cam["location"] == [5, -5, 3]
        assert cam["rotation"] == [60, 0, 45]

    def test_add_camera_invalid_type(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Invalid camera type"):
            add_camera(proj, camera_type="INVALID")

    def test_add_camera_invalid_focal_length(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Focal length must be positive"):
            add_camera(proj, focal_length=-1)

    def test_set_camera_property(self):
        proj = self._make_scene()
        add_camera(proj)
        set_camera(proj, 0, "focal_length", 85)
        assert proj["cameras"][0]["focal_length"] == 85.0

    def test_set_camera_location(self):
        proj = self._make_scene()
        add_camera(proj)
        set_camera(proj, 0, "location", [1.0, 2.0, 3.0])
        assert proj["cameras"][0]["location"] == [1.0, 2.0, 3.0]

    def test_set_camera_invalid_prop(self):
        proj = self._make_scene()
        add_camera(proj)
        with pytest.raises(ValueError, match="Unknown camera property"):
            set_camera(proj, 0, "bogus", 1)

    def test_set_active_camera(self):
        proj = self._make_scene()
        add_camera(proj, name="Cam1")
        add_camera(proj, name="Cam2")
        result = set_active_camera(proj, 1)
        assert result["active_camera"] == "Cam2"
        assert proj["cameras"][0]["is_active"] is False
        assert proj["cameras"][1]["is_active"] is True

    def test_list_cameras(self):
        proj = self._make_scene()
        add_camera(proj, name="A")
        add_camera(proj, name="B")
        result = list_cameras(proj)
        assert len(result) == 2

    def test_get_camera(self):
        proj = self._make_scene()
        add_camera(proj, name="Test")
        cam = get_camera(proj, 0)
        assert cam["name"] == "Test"

    # Light tests
    def test_add_point_light(self):
        proj = self._make_scene()
        light = add_light(proj, light_type="POINT")
        assert light["type"] == "POINT"
        assert "radius" in light
        assert len(proj["lights"]) == 1

    def test_add_sun_light(self):
        proj = self._make_scene()
        light = add_light(proj, light_type="SUN")
        assert light["type"] == "SUN"
        assert "angle" in light

    def test_add_spot_light(self):
        proj = self._make_scene()
        light = add_light(proj, light_type="SPOT")
        assert light["type"] == "SPOT"
        assert "spot_size" in light
        assert "spot_blend" in light

    def test_add_area_light(self):
        proj = self._make_scene()
        light = add_light(proj, light_type="AREA")
        assert light["type"] == "AREA"
        assert "size" in light
        assert "shape" in light

    def test_add_light_with_properties(self):
        proj = self._make_scene()
        light = add_light(proj, light_type="POINT", location=[1, 2, 3],
                          color=[1.0, 0.5, 0.0], power=500)
        assert light["location"] == [1, 2, 3]
        assert light["color"] == [1.0, 0.5, 0.0]
        assert light["power"] == 500

    def test_add_light_invalid_type(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Invalid light type"):
            add_light(proj, light_type="INVALID")

    def test_add_light_invalid_color(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="must be 0.0-1.0"):
            add_light(proj, color=[2.0, 0.0, 0.0])

    def test_set_light_property(self):
        proj = self._make_scene()
        add_light(proj)
        set_light(proj, 0, "power", 2000)
        assert proj["lights"][0]["power"] == 2000.0

    def test_set_light_color(self):
        proj = self._make_scene()
        add_light(proj)
        set_light(proj, 0, "color", [0.5, 0.5, 1.0])
        assert proj["lights"][0]["color"] == [0.5, 0.5, 1.0]

    def test_set_light_invalid_prop(self):
        proj = self._make_scene()
        add_light(proj)
        with pytest.raises(ValueError, match="Unknown light property"):
            set_light(proj, 0, "bogus", 1)

    def test_list_lights(self):
        proj = self._make_scene()
        add_light(proj, light_type="POINT", name="A")
        add_light(proj, light_type="SUN", name="B")
        result = list_lights(proj)
        assert len(result) == 2

    def test_get_light(self):
        proj = self._make_scene()
        add_light(proj, name="Test")
        light = get_light(proj, 0)
        assert light["name"] == "Test"


# ── Animation Tests ─────────────────────────────────────────────

class TestAnimation:
    def _make_scene_with_object(self):
        proj = create_scene()
        add_object(proj, name="Cube")
        return proj

    def test_add_keyframe_location(self):
        proj = self._make_scene_with_object()
        kf = add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        assert kf["frame"] == 1
        assert kf["property"] == "location"
        assert kf["value"] == [0.0, 0.0, 0.0]

    def test_add_keyframe_rotation(self):
        proj = self._make_scene_with_object()
        kf = add_keyframe(proj, 0, 10, "rotation", [0, 0, 90])
        assert kf["value"] == [0.0, 0.0, 90.0]

    def test_add_keyframe_scale(self):
        proj = self._make_scene_with_object()
        kf = add_keyframe(proj, 0, 10, "scale", [2, 2, 2])
        assert kf["value"] == [2.0, 2.0, 2.0]

    def test_add_keyframe_visible(self):
        proj = self._make_scene_with_object()
        kf = add_keyframe(proj, 0, 10, "visible", "true")
        assert kf["value"] is True

    def test_add_keyframe_invalid_property(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="Cannot animate"):
            add_keyframe(proj, 0, 1, "bogus", 1)

    def test_add_keyframe_invalid_interpolation(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="Invalid interpolation"):
            add_keyframe(proj, 0, 1, "location", [0, 0, 0], "INVALID")

    def test_add_keyframe_replaces_existing(self):
        proj = self._make_scene_with_object()
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        add_keyframe(proj, 0, 1, "location", [1, 1, 1])
        assert len(proj["objects"][0]["keyframes"]) == 1
        assert proj["objects"][0]["keyframes"][0]["value"] == [1.0, 1.0, 1.0]

    def test_remove_keyframe(self):
        proj = self._make_scene_with_object()
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        removed = remove_keyframe(proj, 0, 1)
        assert len(removed) == 1
        assert len(proj["objects"][0]["keyframes"]) == 0

    def test_remove_keyframe_by_property(self):
        proj = self._make_scene_with_object()
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        add_keyframe(proj, 0, 1, "rotation", [0, 0, 0])
        removed = remove_keyframe(proj, 0, 1, "location")
        assert len(removed) == 1
        assert len(proj["objects"][0]["keyframes"]) == 1

    def test_remove_keyframe_not_found(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="No keyframe found"):
            remove_keyframe(proj, 0, 999)

    def test_set_frame_range(self):
        proj = self._make_scene_with_object()
        result = set_frame_range(proj, 1, 500)
        assert proj["scene"]["frame_start"] == 1
        assert proj["scene"]["frame_end"] == 500
        assert "old_range" in result

    def test_set_frame_range_invalid(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="must be >="):
            set_frame_range(proj, 100, 50)

    def test_set_fps(self):
        proj = self._make_scene_with_object()
        result = set_fps(proj, 30)
        assert proj["scene"]["fps"] == 30
        assert result["old_fps"] == 24

    def test_set_fps_invalid(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="must be positive"):
            set_fps(proj, 0)

    def test_set_current_frame(self):
        proj = self._make_scene_with_object()
        result = set_current_frame(proj, 100)
        assert proj["scene"]["frame_current"] == 100

    def test_set_current_frame_out_of_range(self):
        proj = self._make_scene_with_object()
        with pytest.raises(ValueError, match="outside range"):
            set_current_frame(proj, 9999)

    def test_list_keyframes(self):
        proj = self._make_scene_with_object()
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        add_keyframe(proj, 0, 10, "location", [5, 5, 5])
        add_keyframe(proj, 0, 10, "rotation", [0, 0, 90])
        result = list_keyframes(proj, 0)
        assert len(result) == 3

    def test_list_keyframes_filtered(self):
        proj = self._make_scene_with_object()
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        add_keyframe(proj, 0, 10, "rotation", [0, 0, 90])
        result = list_keyframes(proj, 0, prop="location")
        assert len(result) == 1

    def test_keyframes_sorted(self):
        proj = self._make_scene_with_object()
        add_keyframe(proj, 0, 50, "location", [5, 5, 5])
        add_keyframe(proj, 0, 1, "location", [0, 0, 0])
        kfs = proj["objects"][0]["keyframes"]
        assert kfs[0]["frame"] <= kfs[1]["frame"]


# ── Render Tests ────────────────────────────────────────────────

class TestRender:
    def _make_scene(self):
        return create_scene()

    def test_set_render_settings_engine(self):
        proj = self._make_scene()
        result = set_render_settings(proj, engine="EEVEE")
        assert proj["render"]["engine"] == "EEVEE"

    def test_set_render_settings_resolution(self):
        proj = self._make_scene()
        set_render_settings(proj, resolution_x=3840, resolution_y=2160)
        assert proj["render"]["resolution_x"] == 3840
        assert proj["render"]["resolution_y"] == 2160

    def test_set_render_settings_samples(self):
        proj = self._make_scene()
        set_render_settings(proj, samples=512)
        assert proj["render"]["samples"] == 512

    def test_set_render_settings_invalid_engine(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Invalid engine"):
            set_render_settings(proj, engine="INVALID")

    def test_set_render_settings_invalid_resolution(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="must be positive"):
            set_render_settings(proj, resolution_x=0)

    def test_set_render_settings_with_preset(self):
        proj = self._make_scene()
        result = set_render_settings(proj, preset="cycles_high")
        assert proj["render"]["samples"] == 512

    def test_set_render_settings_invalid_preset(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Unknown render preset"):
            set_render_settings(proj, preset="nonexistent")

    def test_get_render_settings(self):
        proj = self._make_scene()
        info = get_render_settings(proj)
        assert info["engine"] == "CYCLES"
        assert "resolution" in info
        assert "effective_resolution" in info

    def test_list_render_presets(self):
        presets = list_render_presets()
        assert len(presets) >= 5
        names = [p["name"] for p in presets]
        assert "cycles_default" in names
        assert "eevee_default" in names

    def test_render_scene_generates_script(self):
        proj = self._make_scene()
        add_object(proj, name="Cube")
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "render.png")
            result = render_scene(proj, output_path, overwrite=True)
            assert os.path.exists(result["script_path"])
            assert "blender" in result["command"]
            assert result["engine"] == "CYCLES"

    def test_render_scene_overwrite_protection(self):
        proj = self._make_scene()
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "render.png")
            # Create the file first
            with open(output_path, "w") as f:
                f.write("existing")
            with pytest.raises(FileExistsError):
                render_scene(proj, output_path, overwrite=False)

    def test_all_engines_valid(self):
        assert "CYCLES" in VALID_ENGINES
        assert "EEVEE" in VALID_ENGINES
        assert "WORKBENCH" in VALID_ENGINES

    def test_render_settings_denoising(self):
        proj = self._make_scene()
        set_render_settings(proj, use_denoising=False)
        assert proj["render"]["use_denoising"] is False

    def test_render_settings_transparent(self):
        proj = self._make_scene()
        set_render_settings(proj, film_transparent=True)
        assert proj["render"]["film_transparent"] is True

    def test_render_settings_format(self):
        proj = self._make_scene()
        set_render_settings(proj, output_format="JPEG")
        assert proj["render"]["output_format"] == "JPEG"

    def test_render_settings_invalid_format(self):
        proj = self._make_scene()
        with pytest.raises(ValueError, match="Invalid format"):
            set_render_settings(proj, output_format="INVALID")


# ── Session Tests ───────────────────────────────────────────────

class TestSession:
    def test_create_session(self):
        sess = Session()
        assert not sess.has_project()

    def test_set_project(self):
        sess = Session()
        proj = create_scene()
        sess.set_project(proj)
        assert sess.has_project()

    def test_get_project_no_project(self):
        sess = Session()
        with pytest.raises(RuntimeError, match="No scene loaded"):
            sess.get_project()

    def test_undo_redo(self):
        sess = Session()
        proj = create_scene(name="original")
        sess.set_project(proj)

        sess.snapshot("change name")
        proj["name"] = "modified"

        assert proj["name"] == "modified"
        sess.undo()
        assert sess.get_project()["name"] == "original"
        sess.redo()
        assert sess.get_project()["name"] == "modified"

    def test_undo_empty(self):
        sess = Session()
        sess.set_project(create_scene())
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            sess.undo()

    def test_redo_empty(self):
        sess = Session()
        sess.set_project(create_scene())
        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_snapshot_clears_redo(self):
        sess = Session()
        proj = create_scene(name="v1")
        sess.set_project(proj)

        sess.snapshot("v2")
        proj["name"] = "v2"

        sess.undo()
        assert sess.get_project()["name"] == "v1"

        # New snapshot should clear redo stack
        sess.snapshot("v3")
        sess.get_project()["name"] = "v3"

        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_status(self):
        sess = Session()
        proj = create_scene(name="test")
        sess.set_project(proj, "/tmp/test.json")
        status = sess.status()
        assert status["has_project"] is True
        assert status["project_path"] == "/tmp/test.json"
        assert status["undo_count"] == 0

    def test_save_session(self):
        sess = Session()
        proj = create_scene(name="save_test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            sess.set_project(proj, path)
            saved = sess.save_session()
            assert os.path.exists(saved)
            with open(saved) as f:
                loaded = json.load(f)
            assert loaded["name"] == "save_test"
        finally:
            os.unlink(path)

    def test_list_history(self):
        sess = Session()
        proj = create_scene()
        sess.set_project(proj)
        sess.snapshot("action 1")
        sess.snapshot("action 2")
        history = sess.list_history()
        assert len(history) == 2
        assert history[0]["description"] == "action 2"

    def test_max_undo(self):
        sess = Session()
        sess.MAX_UNDO = 5
        proj = create_scene()
        sess.set_project(proj)
        for i in range(10):
            sess.snapshot(f"action {i}")
        assert len(sess._undo_stack) == 5

    def test_undo_object_add(self):
        sess = Session()
        proj = create_scene()
        sess.set_project(proj)

        sess.snapshot("add object")
        add_object(proj, name="Cube")
        assert len(proj["objects"]) == 1

        sess.undo()
        assert len(sess.get_project()["objects"]) == 0

    def test_undo_modifier_add(self):
        sess = Session()
        proj = create_scene()
        add_object(proj, name="Cube")
        sess.set_project(proj)

        sess.snapshot("add modifier")
        add_modifier(proj, "subdivision_surface", 0)
        assert len(proj["objects"][0]["modifiers"]) == 1

        sess.undo()
        assert len(sess.get_project()["objects"][0]["modifiers"]) == 0
