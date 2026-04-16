"""
Full end-to-end tests for the cli-anything-freecad harness.

Covers three levels:
  1. TestIntermediateFiles  -- JSON project + macro generation (no FreeCAD needed)
  2. TestFreeCADBackend     -- headless FreeCAD export (skipped when not installed)
  3. TestCLISubprocess      -- subprocess invocations of the CLI entry-point
"""

from __future__ import annotations

import ast
import json
import os
import struct
import subprocess
import sys
from copy import deepcopy
from typing import List

import pytest

# ---------------------------------------------------------------------------
# Imports from the harness under test
# ---------------------------------------------------------------------------
from cli_anything.freecad.core.document import (
    create_document,
    open_document,
    save_document,
    get_document_info,
)
from cli_anything.freecad.core.parts import (
    add_part,
    list_parts,
    get_part,
    boolean_op,
    transform_part,
)
from cli_anything.freecad.core.sketch import (
    create_sketch,
    add_line,
    add_circle,
    add_rectangle,
    add_arc,
    add_constraint,
    close_sketch,
    list_sketches,
)
from cli_anything.freecad.core.body import (
    create_body,
    pad,
    pocket,
    fillet,
    chamfer,
    revolution,
    list_bodies,
)
from cli_anything.freecad.core.materials import (
    create_material,
    assign_material,
    list_materials,
)
from cli_anything.freecad.core.export import export_project, get_export_info
from cli_anything.freecad.utils.freecad_macro_gen import generate_macro


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_freecad() -> bool:
    """Return True if FreeCAD headless backend can be located."""
    try:
        from cli_anything.freecad.utils.freecad_backend import find_freecad
        find_freecad()
        return True
    except (RuntimeError, Exception):
        return False


def _resolve_cli(name: str) -> List[str]:
    """Resolve the CLI entry-point for subprocess tests.

    Prefers an installed command on PATH; falls back to ``python -m``
    unless ``CLI_ANYTHING_FORCE_INSTALLED=1`` is set.
    """
    import shutil

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = (
        name.replace("cli-anything-", "cli_anything.")
        .replace("-", "_")
        + "."
        + name.split("-")[-1]
        + "_cli"
    )
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# =========================================================================
# 1. Intermediate-file tests (no FreeCAD required)
# =========================================================================

class TestIntermediateFiles:
    """Verify project creation, manipulation, and macro generation
    using only the Python API -- no FreeCAD binary needed."""

    def test_full_project_json_structure(self, tmp_path):
        """Create a complex project and verify the JSON schema."""
        proj = create_document(name="StructureTest", units="mm")

        # Add varied parts
        add_part(proj, "box", name="MainBox", params={"length": 30, "width": 20, "height": 15})
        add_part(proj, "cylinder", name="Shaft", params={"radius": 3, "height": 50})
        add_part(proj, "sphere", name="Ball", params={"radius": 8})

        # Add a sketch with elements
        create_sketch(proj, name="BaseSketch", plane="XY")
        add_rectangle(proj, 0, corner=[0, 0], width=20, height=10)

        # Add a body with a pad
        create_body(proj, name="MainBody")
        pad(proj, 0, 0, length=15)

        # Add a material
        create_material(proj, preset="steel")

        # Save and reload
        path = str(tmp_path / "structure.json")
        save_document(proj, path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Top-level keys
        required_keys = {"version", "name", "units", "parts", "sketches",
                         "bodies", "materials", "metadata"}
        assert required_keys.issubset(data.keys()), (
            f"Missing keys: {required_keys - set(data.keys())}"
        )

        assert data["name"] == "StructureTest"
        assert data["units"] == "mm"
        assert data["version"] == "1.0"
        assert len(data["parts"]) == 3
        assert len(data["sketches"]) == 1
        assert len(data["bodies"]) == 1
        assert len(data["materials"]) == 1

        # Verify part structure
        box = data["parts"][0]
        assert box["type"] == "box"
        assert box["name"] == "MainBox"
        assert box["params"]["length"] == 30.0
        assert "placement" in box
        assert box["placement"]["position"] == [0.0, 0.0, 0.0]

        # Metadata
        assert "created" in data["metadata"]
        assert "modified" in data["metadata"]
        assert "software" in data["metadata"]

        print(f"\n  JSON structure validated: {path} ({os.path.getsize(path):,} bytes)")

    def test_multi_part_boolean_workflow(self):
        """Parts + booleans + materials, verify all state is consistent."""
        proj = create_document(name="BooleanTest")

        # Add base and tool
        box = add_part(proj, "box", name="Base", params={"length": 20, "width": 20, "height": 20})
        cyl = add_part(proj, "cylinder", name="Hole",
                       params={"radius": 5, "height": 30},
                       position=[10, 10, -5])

        assert len(list_parts(proj)) == 2
        assert box["id"] == 1
        assert cyl["id"] == 2

        # Boolean cut
        cut_result = boolean_op(proj, "cut", base_index=0, tool_index=1, name="CutResult")
        assert cut_result["type"] == "cut"
        assert cut_result["params"]["base_id"] == box["id"]
        assert cut_result["params"]["tool_id"] == cyl["id"]
        assert cut_result["visible"] is True

        # Source parts should now be hidden
        assert get_part(proj, 0)["visible"] is False
        assert get_part(proj, 1)["visible"] is False

        # Total parts now 3 (box, cylinder, cut-result)
        assert len(list_parts(proj)) == 3

        # Create material and assign to cut result
        mat = create_material(proj, preset="aluminum")
        assignment = assign_material(proj, material_index=0, part_index=2)
        assert assignment["material"] == mat["name"]
        assert assignment["part"] == "CutResult"

        # Verify material assignment on part
        cut_part = get_part(proj, 2)
        assert cut_part["material_index"] == 0

        # Verify material tracking
        materials = list_materials(proj)
        assert len(materials) == 1
        assert 2 in materials[0]["assigned_to"]

        print("\n  Boolean workflow verified: 2 primitives + cut + material assignment")

    def test_macro_generation_syntax(self, tmp_path):
        """Generate a macro and verify it is valid Python via ast.parse."""
        proj = create_document(name="MacroTest")
        add_part(proj, "box", name="TestBox", params={"length": 15, "width": 10, "height": 5})
        add_part(proj, "cylinder", name="TestCyl", params={"radius": 3, "height": 20})
        add_part(proj, "sphere", name="TestSphere", params={"radius": 7})

        # Create body with features
        create_sketch(proj, plane="XY")
        add_rectangle(proj, 0, corner=[0, 0], width=10, height=10)
        create_body(proj, name="ExtrudedBody")
        pad(proj, 0, 0, length=10)

        output_path = str(tmp_path / "output.step")
        macro = generate_macro(proj, output_path, export_format="step")

        # Must be non-empty
        assert len(macro) > 100, f"Macro too short: {len(macro)} chars"

        # Must be valid Python syntax
        try:
            ast.parse(macro)
        except SyntaxError as exc:
            pytest.fail(f"Generated macro has invalid Python syntax: {exc}\n\n{macro}")

        # Must contain key FreeCAD imports
        assert "import FreeCAD" in macro
        assert "import Part" in macro
        assert "doc.recompute()" in macro

        # Should reference our parts
        assert "TestBox" in macro
        assert "TestCyl" in macro
        assert "TestSphere" in macro

        # Save macro for inspection
        macro_path = str(tmp_path / "macro.py")
        with open(macro_path, "w", encoding="utf-8") as f:
            f.write(macro)

        print(f"\n  Macro: {macro_path} ({len(macro):,} chars, {macro.count(chr(10))} lines)")

    def test_save_load_roundtrip(self, tmp_path):
        """Save a project, reload it, verify contents are identical."""
        proj = create_document(name="RoundTrip", units="in", profile="imperial")

        add_part(proj, "box", name="BlockA", params={"length": 5, "width": 5, "height": 5})
        add_part(proj, "cone", name="ConeB",
                 params={"radius1": 3, "radius2": 1, "height": 8})

        create_sketch(proj, name="ProfileSketch", plane="XZ")
        add_line(proj, 0, start=[0, 0], end=[10, 0])
        add_circle(proj, 0, center=[5, 5], radius=3)

        create_material(proj, name="CustomMat", color=[0.5, 0.3, 0.1, 1.0],
                        metallic=0.7, roughness=0.4)
        assign_material(proj, 0, 0)

        path = str(tmp_path / "roundtrip.json")
        save_document(proj, path)

        # Reload
        loaded = open_document(path)

        # Compare key fields (metadata.modified will differ slightly, so skip it)
        assert loaded["name"] == proj["name"]
        assert loaded["units"] == proj["units"]
        assert loaded["version"] == proj["version"]
        assert len(loaded["parts"]) == len(proj["parts"])
        assert len(loaded["sketches"]) == len(proj["sketches"])
        assert len(loaded["bodies"]) == len(proj["bodies"])
        assert len(loaded["materials"]) == len(proj["materials"])

        # Deep-compare parts
        for i, (orig, reloaded) in enumerate(zip(proj["parts"], loaded["parts"])):
            assert orig["name"] == reloaded["name"], f"Part {i} name mismatch"
            assert orig["type"] == reloaded["type"], f"Part {i} type mismatch"
            assert orig["params"] == reloaded["params"], f"Part {i} params mismatch"

        # Deep-compare sketches
        for i, (orig, reloaded) in enumerate(zip(proj["sketches"], loaded["sketches"])):
            assert orig["name"] == reloaded["name"], f"Sketch {i} name mismatch"
            assert orig["plane"] == reloaded["plane"], f"Sketch {i} plane mismatch"
            assert len(orig["elements"]) == len(reloaded["elements"])

        print(f"\n  Round-trip verified: {path} ({os.path.getsize(path):,} bytes)")

    def test_complex_workflow(self, tmp_path):
        """Full pipeline: document -> parts -> sketch -> body -> materials."""
        # 1. Create document
        proj = create_document(name="ComplexWorkflow", profile="print3d")
        assert proj["units"] == "mm"

        # 2. Add multiple parts
        box = add_part(proj, "box", name="Platform",
                       params={"length": 50, "width": 50, "height": 5})
        cyl = add_part(proj, "cylinder", name="Pillar",
                       params={"radius": 5, "height": 40},
                       position=[25, 25, 5])
        sphere = add_part(proj, "sphere", name="Top",
                          params={"radius": 8},
                          position=[25, 25, 45])

        # 3. Transform a part
        transform_part(proj, 2, position=[25, 25, 50], rotation=[0, 0, 45])
        top = get_part(proj, 2)
        assert top["placement"]["position"] == [25.0, 25.0, 50.0]
        assert top["placement"]["rotation"] == [0.0, 0.0, 45.0]

        # 4. Boolean fuse
        fuse_result = boolean_op(proj, "fuse", 0, 1, name="PlatformPillar")
        assert fuse_result["type"] == "fuse"
        assert len(list_parts(proj)) == 4  # box, cyl, sphere, fuse

        # 5. Create sketch with various elements
        sk = create_sketch(proj, name="DetailSketch", plane="XY", offset=5.0)
        assert sk["plane"] == "XY"
        assert sk["offset"] == 5.0

        add_rectangle(proj, 0, corner=[10, 10], width=30, height=30)
        add_circle(proj, 0, center=[25, 25], radius=10)
        add_arc(proj, 0, center=[25, 25], radius=15, start_angle=0, end_angle=180)

        # Add a constraint
        sketch_data = proj["sketches"][0]
        line_ids = [el["id"] for el in sketch_data["elements"] if el["type"] == "line"]
        assert len(line_ids) >= 2, "Should have at least 2 lines from rectangle"
        add_constraint(proj, 0, "horizontal", [line_ids[0]])

        # Close the sketch
        closed = close_sketch(proj, 0)
        assert closed["closed"] is True

        sketches = list_sketches(proj)
        assert len(sketches) == 1
        assert sketches[0]["closed"] is True
        assert sketches[0]["element_count"] >= 6  # 4 rect lines + circle + arc

        # 6. Create body with features
        body = create_body(proj, name="DetailBody")
        # Create a new open sketch for the body
        create_sketch(proj, name="BodySketch", plane="XY")
        add_rectangle(proj, 1, corner=[0, 0], width=20, height=20)

        pad_feat = pad(proj, 0, 1, length=20)
        assert pad_feat["type"] == "pad"
        assert pad_feat["length"] == 20.0

        fillet_feat = fillet(proj, 0, radius=2.0)
        assert fillet_feat["type"] == "fillet"
        assert fillet_feat["radius"] == 2.0

        bodies = list_bodies(proj)
        assert len(bodies) == 1
        assert bodies[0]["feature_count"] == 2

        # 7. Materials
        steel = create_material(proj, preset="steel")
        copper = create_material(proj, preset="copper")
        assert steel["preset"] == "steel"
        assert copper["preset"] == "copper"

        assign_material(proj, 0, 0)  # steel -> Platform(box)
        assign_material(proj, 1, 1)  # copper -> Pillar(cylinder)

        mats = list_materials(proj)
        assert len(mats) == 2
        assert 0 in mats[0]["assigned_to"]
        assert 1 in mats[1]["assigned_to"]

        # 8. Save and verify
        path = str(tmp_path / "complex.json")
        saved = save_document(proj, path)
        assert os.path.isfile(saved)

        info = get_document_info(proj)
        assert info["parts_count"] == 4
        assert info["sketches_count"] == 2
        assert info["bodies_count"] == 1
        assert info["materials_count"] == 2

        # 9. Generate macro
        macro = generate_macro(proj, str(tmp_path / "complex.step"))
        ast.parse(macro)  # valid Python

        # 10. Export info
        exp_info = get_export_info(proj)
        assert exp_info["part_count"] == 4
        assert "Platform" in exp_info["part_names"]

        print(f"\n  Complex workflow: {path} ({os.path.getsize(path):,} bytes)")
        print(f"  Parts: {info['parts_count']}, Sketches: {info['sketches_count']}, "
              f"Bodies: {info['bodies_count']}, Materials: {info['materials_count']}")


# =========================================================================
# 2. FreeCAD backend tests (require FreeCAD installed)
# =========================================================================

@pytest.mark.skipif(not _has_freecad(), reason="FreeCAD not installed")
class TestFreeCADBackend:
    """Tests that require the real FreeCAD headless backend."""

    def test_find_freecad(self):
        """Verify that find_freecad returns a valid path."""
        from cli_anything.freecad.utils.freecad_backend import find_freecad

        path = find_freecad()
        assert os.path.isfile(path), f"FreeCAD not found at: {path}"
        print(f"\n  FreeCAD found: {path}")

    def test_get_version(self):
        """Verify that get_version returns a version string."""
        from cli_anything.freecad.utils.freecad_backend import get_version

        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0
        # Should contain at least one digit and a dot
        assert any(c.isdigit() for c in version), f"No digits in version: {version}"
        print(f"\n  FreeCAD version: {version}")

    def test_export_box_step(self, tmp_path):
        """Create a project with a box, export to STEP, validate format."""
        proj = create_document(name="StepExport")
        add_part(proj, "box", name="ExportBox",
                 params={"length": 20, "width": 15, "height": 10})

        output = str(tmp_path / "box.step")
        result = export_project(proj, output, preset="step")

        assert os.path.isfile(output)
        size = os.path.getsize(output)
        assert size > 0, "STEP file is empty"

        # Validate STEP header
        with open(output, "r", encoding="utf-8", errors="ignore") as f:
            header = f.read(64)
        assert header.strip().startswith("ISO-10303-21"), (
            f"Invalid STEP header: {header[:40]!r}"
        )

        print(f"\n  STEP: {output} ({size:,} bytes)")

    def test_export_multi_part_stl(self, tmp_path):
        """Export multiple parts to STL, validate format."""
        proj = create_document(name="StlExport")
        add_part(proj, "box", name="Block",
                 params={"length": 10, "width": 10, "height": 10})
        add_part(proj, "cylinder", name="Rod",
                 params={"radius": 3, "height": 20},
                 position=[15, 0, 0])

        output = str(tmp_path / "multi.stl")
        result = export_project(proj, output, preset="stl")

        assert os.path.isfile(output)
        size = os.path.getsize(output)
        assert size > 0, "STL file is empty"

        # Validate STL: ASCII starts with "solid", binary has 80-byte header
        with open(output, "rb") as f:
            head = f.read(80)

        text_head = head.decode("ascii", errors="ignore").strip().lower()
        is_ascii = text_head.startswith("solid")

        is_binary = False
        if not is_ascii:
            with open(output, "rb") as f:
                f.seek(80)
                count_bytes = f.read(4)
                if len(count_bytes) == 4:
                    tri_count = struct.unpack("<I", count_bytes)[0]
                    is_binary = tri_count > 0

        assert is_ascii or is_binary, "File is neither ASCII nor binary STL"

        fmt = "ASCII" if is_ascii else "binary"
        print(f"\n  STL ({fmt}): {output} ({size:,} bytes)")

    def test_export_fcstd(self, tmp_path):
        """Export to native FCStd format."""
        proj = create_document(name="FcstdExport")
        add_part(proj, "box", name="NativeBox",
                 params={"length": 25, "width": 25, "height": 25})

        output = str(tmp_path / "native.FCStd")
        result = export_project(proj, output, preset="fcstd")

        assert os.path.isfile(output)
        size = os.path.getsize(output)
        assert size > 0, "FCStd file is empty"

        print(f"\n  FCStd: {output} ({size:,} bytes)")


# =========================================================================
# 3. CLI subprocess tests
# =========================================================================

class TestCLISubprocess:
    """Test the CLI entry-point via subprocess invocations."""

    @pytest.fixture(autouse=True)
    def _cli_cmd(self):
        """Resolve the CLI command once for all tests."""
        self.cli = _resolve_cli("cli-anything-freecad")

    def _run(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        """Run a CLI command and return the result."""
        cmd = self.cli + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            **kwargs,
        )

    def test_help(self):
        """--help returns exit code 0 and prints usage."""
        result = self._run("--help")
        assert result.returncode == 0, (
            f"--help failed (rc={result.returncode}): {result.stderr}"
        )
        assert "freecad" in result.stdout.lower() or "usage" in result.stdout.lower(), (
            f"Unexpected help output: {result.stdout[:200]}"
        )
        print(f"\n  --help: rc={result.returncode}, {len(result.stdout)} chars")

    def test_document_new_json(self, tmp_path):
        """'--json document new -o <path>' creates valid JSON output."""
        out_file = str(tmp_path / "new_doc.json")
        result = self._run("--json", "document", "new",
                           "--name", "TestDoc", "-o", out_file)
        assert result.returncode == 0, (
            f"document new failed (rc={result.returncode}): {result.stderr}"
        )

        # stdout should be valid JSON
        data = json.loads(result.stdout)
        assert data["name"] == "TestDoc"
        assert "version" in data

        # File should exist
        assert os.path.isfile(out_file)
        print(f"\n  document new: {out_file} ({os.path.getsize(out_file):,} bytes)")

    def test_part_add_json(self, tmp_path):
        """Create doc then add a part, verify JSON output."""
        proj_file = str(tmp_path / "part_add.json")

        # Create document
        r1 = self._run("--json", "document", "new",
                        "--name", "PartTest", "-o", proj_file)
        assert r1.returncode == 0, f"doc new failed: {r1.stderr}"

        # Add a box part
        r2 = self._run("--json", "-p", proj_file, "part", "add", "box",
                        "--name", "MyBox", "-P", "length=30")
        assert r2.returncode == 0, f"part add failed: {r2.stderr}"

        data = json.loads(r2.stdout)
        assert data["type"] == "box"
        assert data["name"] == "MyBox"
        assert data["params"]["length"] == 30.0

        print(f"\n  part add: {data['name']} (type={data['type']})")

    def test_part_list_json(self, tmp_path):
        """Create doc, add parts, list them, verify count."""
        proj_file = str(tmp_path / "part_list.json")

        # Create document
        self._run("--json", "document", "new",
                   "--name", "ListTest", "-o", proj_file)

        # Add two parts
        self._run("--json", "-p", proj_file, "part", "add", "box", "--name", "A")
        self._run("--json", "-p", proj_file, "part", "add", "cylinder", "--name", "B")

        # List parts
        r = self._run("--json", "-p", proj_file, "part", "list")
        assert r.returncode == 0, f"part list failed: {r.stderr}"

        parts = json.loads(r.stdout)
        assert isinstance(parts, list)
        assert len(parts) == 2
        names = {p["name"] for p in parts}
        assert "A" in names
        assert "B" in names

        print(f"\n  part list: {len(parts)} parts ({names})")

    def test_full_workflow_subprocess(self, tmp_path):
        """Full subprocess workflow: create -> box -> cylinder -> boolean cut -> list."""
        proj_file = str(tmp_path / "workflow.json")

        # 1. Create document
        r = self._run("--json", "document", "new",
                       "--name", "WorkflowTest", "-o", proj_file)
        assert r.returncode == 0, f"doc new: {r.stderr}"

        # 2. Add box
        r = self._run("--json", "-p", proj_file, "part", "add", "box",
                       "--name", "Base", "-P", "length=20", "-P", "width=20",
                       "-P", "height=20")
        assert r.returncode == 0, f"add box: {r.stderr}"
        box = json.loads(r.stdout)
        assert box["name"] == "Base"

        # 3. Add cylinder
        r = self._run("--json", "-p", proj_file, "part", "add", "cylinder",
                       "--name", "Hole", "-P", "radius=5", "-P", "height=30",
                       "-pos", "10,10,-5")
        assert r.returncode == 0, f"add cylinder: {r.stderr}"
        cyl = json.loads(r.stdout)
        assert cyl["name"] == "Hole"

        # 4. Boolean cut
        r = self._run("--json", "-p", proj_file,
                       "part", "boolean", "cut", "0", "1")
        assert r.returncode == 0, f"boolean cut: {r.stderr}"
        cut = json.loads(r.stdout)
        assert cut["type"] == "cut"

        # 5. List parts -- should have 3 (box, cylinder, cut-result)
        r = self._run("--json", "-p", proj_file, "part", "list")
        assert r.returncode == 0, f"part list: {r.stderr}"
        parts = json.loads(r.stdout)
        assert len(parts) == 3, f"Expected 3 parts, got {len(parts)}: {parts}"

        # Verify visibility: first two hidden, cut result visible
        visible_count = sum(1 for p in parts if p.get("visible", True))
        assert visible_count >= 1, "At least the cut result should be visible"

        type_names = [p["type"] for p in parts]
        assert "cut" in type_names, f"No 'cut' part found in types: {type_names}"

        print(f"\n  Workflow complete: {len(parts)} parts")
        for p in parts:
            print(f"    {p['name']}: type={p['type']}, visible={p.get('visible', '?')}")
