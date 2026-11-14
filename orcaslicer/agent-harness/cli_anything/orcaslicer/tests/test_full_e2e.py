"""E2E tests for cli-anything-orcaslicer — they invoke the REAL OrcaSlicer binary.

No skipping and no mocking: if OrcaSlicer is not installed these tests fail.
Run against the installed command:
    CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/orcaslicer/tests/ -v -s
"""

import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

import pytest

from cli_anything.orcaslicer.core import config as config_mod
from cli_anything.orcaslicer.core import export as export_mod
from cli_anything.orcaslicer.core import preview as preview_mod
from cli_anything.orcaslicer.core import profiles as prof
from cli_anything.orcaslicer.core import project as P
from cli_anything.orcaslicer.core import slicer as S
from cli_anything.orcaslicer.core import transforms as T
from cli_anything.orcaslicer.utils import orcaslicer_backend as B


# ── Helpers ──────────────────────────────────────────────────────


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
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


def write_box(path, x=20, y=10, z=30):
    v = [(0, 0, 0), (x, 0, 0), (x, y, 0), (0, y, 0), (0, 0, z), (x, 0, z), (x, y, z), (0, y, z)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
         (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    with open(path, "wb") as o:
        o.write(b"\0" * 80 + struct.pack("<I", len(f)))
        for t in f:
            o.write(struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *v[i]) for i in t) + b"\0\0")
    return str(path)


@pytest.fixture
def work():
    d = tempfile.mkdtemp(prefix="orca_e2e_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def box(work):
    return write_box(os.path.join(work, "box.stl"), 20, 10, 30)


def make_project(model, name="e2e", **kw):
    p = P.create_project(name, **kw)
    P.add_model(p, model)
    return p


def do_slice(proj, work, sub="out", **kw):
    res = S.slice_project(proj, outdir=os.path.join(work, sub), **kw)
    g = res["plates"][0]
    print(f"\n  G-code: {g['path']} ({g['bytes']:,} bytes, {g['layers']} layers, {g['print_time']}, "
          f"{g['filament_g']} g)")
    return res, g


def temps_in_gcode(path):
    with open(path, errors="replace") as fh:
        return {int(m) for m in re.findall(r"^M10[49] S(\d+)", fh.read(), re.M)}


# ── Backend against the real binary ──────────────────────────────


class TestBackendReal:
    def test_binary_found_and_version(self):
        info = B.backend_info()
        assert os.path.isfile(info["executable"])
        assert re.match(r"\d+\.\d+", info["version"])
        for flag in ("--slice", "--load-settings", "--load-filaments", "--outputdir",
                     "--export-3mf", "--export-statistics", "--export-settings", "--info"):
            assert flag in info["flags"], flag
        print(f"\n  OrcaSlicer {info['version']} at {info['executable']}")

    def test_missing_input_decodes_to_file_not_found(self, work):
        res = B.run(["--slice", "0", os.path.join(work, "nope.stl")], cwd=work)
        assert res["ok"] is False
        assert res["returncode"] == 253
        assert (res["code"], res["code_name"]) == (-3, "CLI_FILE_NOTFOUND")

    def test_run_check_raises_structured_error(self, work):
        with pytest.raises(B.OrcaSlicerError) as ei:
            B.run(["--slice", "0", os.path.join(work, "nope.stl")], cwd=work, check=True)
        assert ei.value.code_name == "CLI_FILE_NOTFOUND" and "does not exist" in str(ei.value)

    def test_default_settings_schema(self):
        schema = B.export_default_settings()
        assert len(schema) > 600
        for key in ("layer_height", "nozzle_temperature", "sparse_infill_density", "printable_area"):
            assert key in schema
        assert isinstance(schema["nozzle_temperature"], list)

    def test_category_table_covers_real_schema(self):
        schema = config_mod.get_schema()
        cats = config_mod.categories()
        preset_level = [k for k in schema if k in cats]
        assert len(preset_level) > 650
        # every categorised key that the binary knows must be settable
        proj = P.create_project("c")
        config_mod.set_override(proj, "layer_height", "0.16")

    def test_inspect_models_reports_real_geometry(self, box):
        r = B.inspect_models([box])
        info = r["info"]["box.stl"]
        assert (info["size_x"], info["size_y"], info["size_z"]) == (20.0, 10.0, 30.0)
        assert info["number_of_facets"] == 12 and info["manifold"] == "yes"
        assert abs(info["volume"] - 6000) < 1
        assert r["mesh"]["objects"][0]["bbox_object"]["size"] == [20.0, 10.0, 30.0]

    def test_inspect_missing_model(self, work):
        with pytest.raises(FileNotFoundError):
            B.inspect_models([os.path.join(work, "x.stl")])

    def test_unknown_key_is_silently_ignored_by_orca_so_harness_validates(self, work, box):
        """Documents why config.set_override validates keys itself."""
        proj = make_project(box)
        proj["overrides"]["process"]["definitely_not_a_key"] = "1"
        res, g = do_slice(proj, work)
        assert g["layers"] == 150  # slice still works — Orca ignored the unknown key
        with pytest.raises(ValueError, match="Unknown setting"):
            config_mod.set_override(P.create_project("x"), "definitely_not_a_key", "1")

    def test_invalid_value_fails_with_config_error(self, work, box):
        proj = make_project(box)
        proj["overrides"]["process"]["layer_height"] = "abc"   # bypass harness validation
        with pytest.raises(B.OrcaSlicerError) as ei:
            S.slice_project(proj, outdir=os.path.join(work, "bad"))
        assert ei.value.code_name == "CLI_CONFIG_FILE_ERROR"


# ── Intermediate files ───────────────────────────────────────────


class TestIntermediateFiles:
    def test_prepare_settings_files(self, work, box):
        proj = make_project(box)
        proj["overrides"]["process"]["layer_height"] = "0.1"
        proj["profiles"]["filaments"].append("Generic PETG")
        s = S.prepare_settings(proj, os.path.join(work, "settings"))
        m = json.load(open(s["machine"]))
        p = json.load(open(s["process"]))
        f2 = json.load(open(s["filaments"][1]))
        assert m["type"] == "machine" and m["inherits"] == "" and m["gcode_flavor"] == "marlin"
        assert p["layer_height"] == "0.1" and p["type"] == "process"
        assert f2["filament_type"] == ["PETG"] and f2["filament_diameter"] == ["1.75"]
        assert len(s["filaments"]) == 2

    def test_build_command_is_absolute_and_ordered(self, work, box):
        proj = make_project(box)
        T.add_transform(proj, "rotate_x", 90)
        s = S.prepare_settings(proj, os.path.join(work, "settings"))
        args = S.build_args(proj, s, os.path.join(work, "out"), 0, None, False, False)
        assert all(os.path.isabs(a) for a in args if a.endswith((".json", ".stl")))
        assert args.index("--rotate-x") < args.index("--ensure-on-bed")


# ── True-backend slicing workflows ───────────────────────────────


class TestSliceWorkflows:
    def test_basic_slice_produces_verified_gcode(self, work, box):
        proj = make_project(box)
        res, g = do_slice(proj, work)
        assert res["ok"] and os.path.isfile(g["path"]) and g["bytes"] > 10_000
        head = open(g["path"], errors="replace").read(200)
        assert head.startswith("; HEADER_BLOCK_START") and "generated by OrcaSlicer" in head
        assert g["layers"] == 150 and abs(g["max_z"] - 30.0) < 0.01
        assert g["extrusion_moves"] > 1000
        assert g["statistics"] and os.path.isfile(g["statistics"])
        assert g["orcaslicer_version"] if "orcaslicer_version" in g else res["orcaslicer_version"]

    def test_quality_sweep_layer_count_and_time(self, work, box):
        results = {}
        for lh_name, lh in (("0.28mm Extra Draft", 0.28), ("0.20mm Standard", 0.20), ("0.08mm Extra Fine", 0.08)):
            proj = make_project(box, process=lh_name)
            _, g = do_slice(proj, work, sub=f"q{lh}")
            assert abs(g["layers"] - 30 / lh) <= 3, (lh, g["layers"])
            results[lh] = g
        assert results[0.28]["print_time_s"] < results[0.20]["print_time_s"] < results[0.08]["print_time_s"]

    def test_override_layer_height_via_config(self, work, box):
        proj = make_project(box)
        config_mod.set_override(proj, "layer_height", "0.12")
        _, g = do_slice(proj, work)
        assert abs(g["layers"] - 250) <= 2

    def test_tilt_keeps_part_on_bed_and_height_drops(self, work, box):
        base = do_slice(make_project(box), work, "base")[1]
        proj = make_project(box)
        T.add_transform(proj, "rotate_x", 90)
        res, tilted = do_slice(proj, work, "tilt")
        assert abs(base["max_z"] - 30.0) < 0.01
        assert abs(tilted["max_z"] - 10.0) < 0.01          # 30 → 10 (box lies on its side)
        assert res["auto_ensure_on_bed"] is True

    def test_without_auto_guard_orca_silently_clips(self, work, box):
        """Proves the guard is needed: raw OrcaSlicer prints 5mm instead of 10mm."""
        proj = make_project(box)
        T.add_transform(proj, "rotate_x", 90)
        proj["slice"]["auto_ensure_on_bed"] = False
        res, clipped = do_slice(proj, work)
        assert abs(clipped["max_z"] - 5.0) < 0.01
        assert res["auto_ensure_on_bed"] is False

    def test_scale_up(self, work, box):
        base = do_slice(make_project(box), work, "b")[1]
        proj = make_project(box)
        T.add_transform(proj, "scale", 2)
        _, big = do_slice(proj, work, "s")
        assert abs(big["max_z"] - 60.0) < 0.01
        assert big["filament_g"] > 5 * base["filament_g"]

    def test_scale_down(self, work, box):
        proj = make_project(box)
        T.add_transform(proj, "scale", 0.5)
        _, g = do_slice(proj, work)
        assert abs(g["max_z"] - 15.0) < 0.01

    def test_ground_largest_face_lays_part_flat(self, work, box):
        proj = make_project(box)
        T.add_transform(proj, "ground_largest_face")
        _, g = do_slice(proj, work)
        assert abs(g["max_z"] - 10.0) < 0.01   # laid on its 20x30 face

    def test_strength_tuning_monotonic_filament(self, work, box):
        usage = {}
        for infill in ("10%", "60%"):
            proj = make_project(box)
            config_mod.set_override(proj, "sparse_infill_density", infill)
            usage[infill] = do_slice(proj, work, f"i{infill[:-1]}")[1]["filament_g"]
        assert usage["10%"] < usage["60%"]
        std = do_slice(make_project(box), work, "std")[1]["filament_g"]
        strong = do_slice(make_project(box, process="0.20mm Strength"), work, "strong")[1]["filament_g"]
        assert strong > std

    def test_wall_loops_override_adds_material(self, work, box):
        a = do_slice(make_project(box), work, "w2")[1]["filament_g"]
        proj = make_project(box)
        config_mod.set_override(proj, "wall_loops", "5")
        assert do_slice(proj, work, "w5")[1]["filament_g"] > a

    @pytest.mark.parametrize("name,temp", [("Generic PLA", 210), ("Generic PETG", 240), ("Generic ABS", 260)])
    def test_material_swap_temperatures_in_gcode(self, work, box, name, temp):
        proj = make_project(box, filament=name)
        _, g = do_slice(proj, work)
        temps = temps_in_gcode(g["path"])
        assert temp in temps and (temp + 5) in temps

    def test_filament_temperature_override(self, work, box):
        proj = make_project(box)
        config_mod.set_override(proj, "nozzle_temperature", "199")
        _, g = do_slice(proj, work)
        assert 199 in temps_in_gcode(g["path"])

    def test_density_changes_weight_not_length(self, work, box):
        a = do_slice(make_project(box), work, "d1")[1]
        proj = make_project(box)
        config_mod.set_override(proj, "filament_density", "2.48")  # 2x PLA
        b = do_slice(proj, work, "d2")[1]
        assert abs(a["filament_mm"] - b["filament_mm"]) < 1
        assert 1.9 < b["filament_g"] / a["filament_g"] < 2.1

    def test_nozzle_override_changes_extrusion_width(self, work, box):
        a = do_slice(make_project(box), work, "n4")[1]
        proj = make_project(box)
        config_mod.set_override(proj, "nozzle_diameter", "0.6")
        b = do_slice(proj, work, "n6")[1]
        assert b["extrusion_moves"] != a["extrusion_moves"]

    def test_repetitions_double_material(self, work, box):
        one = do_slice(make_project(box), work, "r1")[1]
        proj = make_project(box)
        T.add_transform(proj, "repetitions", 2)
        _, two = do_slice(proj, work, "r2")
        assert 1.8 < two["filament_g"] / one["filament_g"] < 2.2
        stats = S.load_statistics(two["statistics"])
        assert len(stats["objects"]) == 2

    def test_copies_are_arranged_without_overlap(self, work, box):
        proj = make_project(box)
        T.add_transform(proj, "repetitions", 3)
        info = export_mod.export_3mf(proj, os.path.join(work, "c.3mf"))
        with zipfile.ZipFile(info["path"]) as zf:
            boxes = [o["bbox"] for o in json.loads(zf.read("Metadata/plate_1.json"))["bbox_objects"]]
        assert len(boxes) == 3
        for i in range(3):
            for j in range(i + 1, 3):
                a, b = boxes[i], boxes[j]
                overlap = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                assert not overlap, (a, b)

    def test_native_repetitions_on_3mf_input(self, work, box):
        path = os.path.join(work, "in.3mf")
        export_mod.export_3mf(make_project(box), path)
        proj = P.create_project("r3")
        P.add_model(proj, path)
        T.add_transform(proj, "repetitions", 2)
        res, two = do_slice(proj, work, "r3")
        assert res["plate_adjusted"] is True          # --slice 0 is rejected by OrcaSlicer here
        one = do_slice(make_project(box), work, "r3b")[1]
        assert 1.8 < two["filament_g"] / one["filament_g"] < 2.2

    def test_two_models_on_one_plate(self, work, box):
        other = write_box(os.path.join(work, "cube.stl"), 15, 15, 15)
        proj = make_project(box)
        P.add_model(proj, other)
        _, g = do_slice(proj, work)
        stats = S.load_statistics(g["statistics"])
        assert sorted(o["name"] for o in stats["objects"]) == ["box.stl", "cube.stl"]

    def test_statistics_feature_breakdown(self, work, box):
        proj = make_project(box)
        res = S.slice_project(proj, outdir=os.path.join(work, "st"))
        stats = S.feature_stats(proj, 1)
        feats = stats["summary"]["features"]
        for expected in ("Outer wall", "Inner wall", "Sparse infill"):
            assert expected in feats, list(feats)
        assert stats["layer_count"] == 150 and stats["objects"][0]["name"] == "box.stl"
        assert abs(stats["summary"]["weight"] - res["plates"][0]["filament_g"]) < 0.1

    def test_history_recorded_and_last_slice(self, work, box):
        proj = make_project(box)
        S.slice_project(proj, outdir=os.path.join(work, "h"))
        last = S.last_slice(proj)
        assert last["plates"][0]["layers"] == 150 and last["fingerprint"] == P.fingerprint(proj)

    def test_stale_output_is_removed_before_slicing(self, work, box):
        out = os.path.join(work, "stale")
        os.makedirs(out)
        open(os.path.join(out, "plate_7.gcode"), "w").write("old")
        S.slice_project(make_project(box), outdir=out)
        assert not os.path.exists(os.path.join(out, "plate_7.gcode"))

    def test_nonexistent_plate_fails_loudly(self, work, box):
        with pytest.raises(RuntimeError, match="produced no G-code"):
            S.slice_project(make_project(box), outdir=os.path.join(work, "p9"), plate=9)

    def test_model_too_big_for_bed_fails_loudly(self, work, box):
        proj = make_project(box, machine="Generic FDM 220")
        T.add_transform(proj, "scale", 20)   # 400 x 200 x 600 mm
        with pytest.raises(B.OrcaSlicerError) as ei:
            S.slice_project(proj, outdir=os.path.join(work, "big"))
        assert ei.value.code_name in ("CLI_OBJECTS_PARTLY_INSIDE", "CLI_NO_SUITABLE_OBJECTS",
                                      "CLI_VALIDATE_ERROR", "CLI_SLICING_ERROR",
                                      "CLI_OBJECT_ARRANGE_FAILED") or ei.value.code is not None

    def test_machine_preset_sizes_work(self, work, box):
        for m in ("Generic FDM 220", "Generic FDM 256", "Generic FDM 350"):
            _, g = do_slice(make_project(box, machine=m), work, m.split()[-1])
            assert g["layers"] == 150

    def test_multi_material_two_filament_slots(self, work, box):
        """PLA + PETG on one plate: real tool changes (T1) must appear in the G-code."""
        other = write_box(os.path.join(work, "cube.stl"), 15, 15, 15)
        proj = make_project(box, filament="Generic PLA")
        proj["profiles"]["filaments"].append("Generic PETG")
        P.add_model(proj, other, filament=2)
        res, g = do_slice(proj, work, "mm")
        text = open(g["path"], errors="replace").read()
        assert len(re.findall(r"^T1\b", text, re.M)) > 0, "no tool change to filament 2"
        assert {210, 240} <= temps_in_gcode(g["path"])          # PLA and PETG temperatures both present
        stats = S.load_statistics(g["statistics"])
        assert sorted(o["name"] for o in stats["objects"]) == ["box.stl", "cube.stl"]
        assert "--load-filament-ids" in res["command"]
        single = do_slice(make_project(box), work, "mm_single")[1]
        assert g["filament_g"] > single["filament_g"]            # second object adds material

    def test_multi_material_filament_presets_are_completed(self, work, box):
        proj = make_project(box)
        proj["profiles"]["filaments"].append("Generic ABS")
        s = S.prepare_settings(proj, os.path.join(work, "settings"))
        schema = config_mod.get_schema()
        cats = config_mod.categories()
        for f in s["filaments"]:
            data = json.load(open(f))
            missing = [k for k in schema if cats.get(k) == "filament" and k not in data]
            assert missing == []
        assert json.load(open(s["filaments"][1]))["filament_type"] == ["ABS"]


# ── Exports ──────────────────────────────────────────────────────


class TestExports:
    def test_3mf_export_roundtrip(self, work, box):
        proj = make_project(box)
        path = os.path.join(work, "proj.3mf")
        info = export_mod.export_3mf(proj, path)
        print(f"\n  3MF: {info['path']} ({info['bytes']:,} bytes)")
        assert info["sliced"] and info["gcode_plates"] == 1
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            assert "Metadata/plate_1.gcode" in names and "3D/3dmodel.model" in names
            cfg = zf.read("Metadata/project_settings.config").decode()
            assert '"layer_height": "0.2"' in cfg
            assert b"generated by OrcaSlicer" in zf.read("Metadata/plate_1.gcode")[:400]
        # hand-off: import the 3MF into a fresh project and slice again
        proj2 = P.create_project("rt")
        P.add_model(proj2, path)
        _, g = do_slice(proj2, work, "rt")
        assert abs(g["max_z"] - 30.0) < 0.5

    def test_3mf_export_leaves_no_side_effect_directories(self, work, box, monkeypatch):
        cwd = os.path.join(work, "cwd")
        os.makedirs(cwd)
        monkeypatch.chdir(cwd)
        info = export_mod.export_3mf(make_project(box, name="sidefx"), os.path.join(work, "s.3mf"))
        assert info["gcode_plates"] == 1 and info["layers"] == 150
        assert os.listdir(cwd) == []          # no <project>_output directory dropped in the cwd

    def test_3mf_without_slice_has_no_gcode(self, work, box):
        info = export_mod.export_3mf(make_project(box), os.path.join(work, "u.3mf"), with_slice=False)
        assert info["sliced"] is False and info["gcode_plates"] == 0
        assert zipfile.is_zipfile(info["path"])

    def test_3mf_overwrite_protection(self, work, box):
        proj = make_project(box)
        path = os.path.join(work, "o.3mf")
        export_mod.export_3mf(proj, path, with_slice=False)
        with pytest.raises(FileExistsError):
            export_mod.export_3mf(proj, path, with_slice=False)
        export_mod.export_3mf(proj, path, with_slice=False, overwrite=True)

    def test_3mf_embeds_overrides(self, work, box):
        proj = make_project(box)
        config_mod.set_override(proj, "layer_height", "0.16")
        info = export_mod.export_3mf(proj, os.path.join(work, "ov.3mf"), with_slice=False)
        with zipfile.ZipFile(info["path"]) as zf:
            assert '"layer_height": "0.16"' in zf.read("Metadata/project_settings.config").decode()

    def test_3mf_thumbnails_are_pngs(self, work, box):
        info = export_mod.export_3mf(make_project(box), os.path.join(work, "t.3mf"))
        with zipfile.ZipFile(info["path"]) as zf:
            data = zf.read("Metadata/plate_1.png")
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_stl_export_applies_transforms(self, work, box):
        proj = make_project(box)
        T.add_transform(proj, "scale", 2)
        res = export_mod.export_stl(proj, os.path.join(work, "stl"))
        stl = res["files"][0]["path"]
        print(f"\n  STL: {stl} ({res['files'][0]['bytes']:,} bytes)")
        info = B.inspect_models([stl])["info"][os.path.basename(stl)]
        assert (info["size_x"], info["size_y"], info["size_z"]) == (40.0, 20.0, 60.0)

    def test_settings_export_reflects_overrides(self, work, box):
        proj = make_project(box)
        config_mod.set_override(proj, "layer_height", "0.14")
        config_mod.set_override(proj, "nozzle_temperature", "203")
        res = export_mod.export_settings(proj, os.path.join(work, "eff.json"))
        data = json.load(open(res["path"]))
        assert res["keys"] > 600
        assert data["layer_height"] == "0.14" and data["nozzle_temperature"] == ["203"]

    def test_gcode_export_copies_last_slice(self, work, box):
        proj = make_project(box)
        S.slice_project(proj, outdir=os.path.join(work, "g"))
        dest = os.path.join(work, "final", "part.gcode")
        info = export_mod.export_gcode(proj, dest)
        assert info["layers"] == 150 and S.gcode_info(dest)["extrusion_moves"] > 0


# ── Preset inheritance (vendor-style chains) ─────────────────────


class TestPresetInheritance:
    def test_synthetic_vendor_chain_slices(self, work, box):
        d = os.path.join(work, "profiles")
        os.makedirs(d)
        json.dump({"type": "machine", "name": "fdm_common", "gcode_flavor": "marlin",
                   "layer_change_gcode": "G92 E0", "extruder_clearance_radius": "60",
                   "extruder_clearance_height_to_rod": "40", "extruder_clearance_height_to_lid": "120",
                   "nozzle_diameter": ["0.4"]}, open(os.path.join(d, "common.json"), "w"))
        json.dump({"type": "machine", "name": "Acme X1 0.4", "inherits": "fdm_common",
                   "printable_area": ["0x0", "180x0", "180x180", "0x180"], "printable_height": "180"},
                  open(os.path.join(d, "acme.json"), "w"))
        json.dump({"type": "process", "name": "fdm_proc", "layer_height": "0.3"},
                  open(os.path.join(d, "proc_common.json"), "w"))
        json.dump({"type": "process", "name": "Acme chunky", "inherits": "fdm_proc",
                   "sparse_infill_density": "5%"}, open(os.path.join(d, "proc.json"), "w"))
        prof.clear_index_cache()
        proj = make_project(box, machine="Acme X1 0.4", process="Acme chunky", profile_dirs=[d])
        for kind, ref in (("machine", "Acme X1 0.4"), ("process", "Acme chunky")):
            prof.validate_ref(kind, ref, [d])
        res, g = do_slice(proj, work)
        assert abs(g["layers"] - 100) <= 2          # 30 / 0.3 inherited from the grandparent
        flat = json.load(open(res["settings"]["machine"]))
        assert flat["inherits"] == "" and flat["printable_height"] == "180"

    def test_vendor_parent_name_collision_slices_with_own_vendor_parent(self, work, box):
        """Regression: two vendors with the same parent name — the wrong one broke Bambu A1 mini presets."""
        root = os.path.join(work, "vendors")
        for vendor, height in (("AAA", "100"), ("ZZZ", "180")):
            d = os.path.join(root, vendor)
            os.makedirs(d)
            json.dump({"type": "machine", "name": "fdm_machine_common", "gcode_flavor": "marlin",
                       "layer_change_gcode": "G92 E0", "extruder_clearance_radius": "60",
                       "extruder_clearance_height_to_rod": "40", "extruder_clearance_height_to_lid": "120",
                       "nozzle_diameter": ["0.4"], "printable_height": height,
                       "printable_area": ["0x0", "180x0", "180x180", "0x180"]},
                      open(os.path.join(d, "common.json"), "w"))
            json.dump({"type": "machine", "name": f"{vendor} Mini", "inherits": "fdm_machine_common"},
                      open(os.path.join(d, "mini.json"), "w"))
        prof.clear_index_cache()
        # AAA's parent is only 100mm tall (30mm box fits); ZZZ's is 180mm. Both must slice with own parent.
        for vendor, height in (("AAA", "100"), ("ZZZ", "180")):
            proj = make_project(box, machine=f"{vendor} Mini", profile_dirs=[root])
            res, g = do_slice(proj, work, vendor)
            assert json.load(open(res["settings"]["machine"]))["printable_height"] == height

    def test_legacy_clearance_key_lets_newer_vendor_presets_validate(self, work, box):
        """Bambu-style preset: parent sets clearance radius 0, child sets the newer max_radius key."""
        d = os.path.join(work, "bbl")
        os.makedirs(d)
        json.dump({"type": "machine", "name": "base", "gcode_flavor": "marlin", "layer_change_gcode": "G92 E0",
                   "extruder_clearance_radius": "0", "extruder_clearance_height_to_rod": "25",
                   "extruder_clearance_height_to_lid": "180", "nozzle_diameter": ["0.4"],
                   "printable_area": ["0x0", "180x0", "180x180", "0x180"], "printable_height": "180"},
                  open(os.path.join(d, "base.json"), "w"))
        json.dump({"type": "machine", "name": "Bambu-like", "inherits": "base",
                   "extruder_clearance_max_radius": "73"}, open(os.path.join(d, "b.json"), "w"))
        prof.clear_index_cache()
        res, g = do_slice(make_project(box, machine="Bambu-like", profile_dirs=[d]), work)
        assert g["layers"] == 150
        assert json.load(open(res["settings"]["machine"]))["extruder_clearance_radius"] == "73"

    def test_vendor_profile_dir_from_env_is_searched(self, work, monkeypatch):
        d = os.path.join(work, "envprof")
        os.makedirs(d)
        json.dump({"type": "filament", "name": "Env Silk PLA", "filament_type": ["PLA"],
                   "filament_diameter": ["1.75"]}, open(os.path.join(d, "f.json"), "w"))
        monkeypatch.setenv("ORCASLICER_PROFILES_DIR", d)
        prof.clear_index_cache()
        assert prof.resolve("filament", "Env Silk PLA")["filament_type"] == ["PLA"]
        prof.clear_index_cache()


# ── Preview bundles (real OrcaSlicer renders) ────────────────────


class TestPreviewReal:
    def _png_dims(self, path):
        with open(path, "rb") as fh:
            head = fh.read(24)
        assert head[:8] == b"\x89PNG\r\n\x1a\n"
        return struct.unpack(">II", head[16:24])

    def test_capture_quick_bundle(self, work, box):
        proj = make_project(box)
        pp = os.path.join(work, "p.orca-cli.json")
        m = preview_mod.capture(proj, pp)
        print(f"\n  Preview bundle: {m['_bundle_dir']}")
        assert m["protocol_version"] == "preview-bundle/v1" and m["bundle_kind"] == "capture"
        assert m["status"] == "ok" and m["cached"] is False
        arts = {a["artifact_id"]: a for a in m["artifacts"]}
        assert {"hero", "top"} <= set(arts)
        for a in arts.values():
            f = os.path.join(m["_bundle_dir"], a["path"])
            assert os.path.getsize(f) == a["bytes"] > 500
            assert self._png_dims(f) == (512, 512)
        assert os.path.isfile(m["_summary_path"])
        summary = json.load(open(m["_summary_path"]))
        assert "150 layers" in summary["headline"]
        assert summary["facts"]["overrides"] == {}
        assert m["metrics"]["layers"] == 150 and m["metrics"]["models"] == 1
        assert not os.path.exists(os.path.join(m["_bundle_dir"], "_work"))

    def test_hero_render_shows_the_model(self, work, box):
        """Pixel check: the render must contain non-background pixels (the model)."""
        m = preview_mod.capture(make_project(box), os.path.join(work, "p.json"))
        hero = os.path.join(m["_bundle_dir"], "artifacts", "hero.png")
        import zlib
        data = open(hero, "rb").read()
        # decode IDAT chunks of an 8-bit RGBA, non-interlaced PNG
        pos, idat, w, h = 8, b"", 0, 0
        while pos < len(data):
            ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
            body = data[pos + 8:pos + 8 + ln]
            if typ == b"IHDR":
                w, h = struct.unpack(">II", body[:8])
            elif typ == b"IDAT":
                idat += body
            pos += 12 + ln
        raw = zlib.decompress(idat)
        stride = w * 4 + 1
        opaque = 0
        prev = bytearray(w * 4)
        for y in range(h):
            row = bytearray(raw[y * stride + 1:(y + 1) * stride])
            ft = raw[y * stride]
            bpp = 4
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if ft == 1:
                    row[i] = (row[i] + a) & 255
                elif ft == 2:
                    row[i] = (row[i] + b) & 255
                elif ft == 3:
                    row[i] = (row[i] + ((a + b) >> 1)) & 255
                elif ft == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    row[i] = (row[i] + pr) & 255
            prev = row
            opaque += sum(1 for x in range(0, len(row), 4) if row[x + 3] > 128)
        frac = opaque / (w * h)
        assert 0.15 < frac < 0.95, f"model covers {frac:.0%} of the render"

    def test_capture_is_cached_and_force_rebuilds(self, work, box):
        proj = make_project(box)
        pp = os.path.join(work, "p.orca-cli.json")
        first = preview_mod.capture(proj, pp)
        second = preview_mod.capture(proj, pp)
        assert second["cached"] is True and second["_bundle_dir"] == first["_bundle_dir"]
        forced = preview_mod.capture(proj, pp, force=True)
        assert forced["cached"] is False and forced["_bundle_dir"] != first["_bundle_dir"]

    def test_latest_does_not_render(self, work, box):
        pp = os.path.join(work, "p.orca-cli.json")
        with pytest.raises(FileNotFoundError):
            preview_mod.latest(pp)
        m = preview_mod.capture(make_project(box), pp)
        root = os.path.join(work, ".cli-anything", "previews", "orcaslicer", "quick")
        before = sorted(os.listdir(root))
        got = preview_mod.latest(pp, recipe="quick")
        assert got["_bundle_dir"] == m["_bundle_dir"] and sorted(os.listdir(root)) == before

    def test_full_recipe_has_statistics_and_3mf(self, work, box):
        m = preview_mod.capture(make_project(box), os.path.join(work, "p.json"), recipe="full")
        ids = {a["artifact_id"] for a in m["artifacts"]}
        assert {"hero", "top", "statistics", "project"} <= ids
        stats = json.load(open(os.path.join(m["_bundle_dir"], "artifacts", "statistics.json")))
        assert stats["summary"]["layer_count"] == 150
        assert zipfile.is_zipfile(os.path.join(m["_bundle_dir"], "artifacts", "project.3mf"))

    def test_summary_lists_active_overrides(self, work, box):
        proj = make_project(box)
        config_mod.set_override(proj, "layer_height", "0.16")
        m = preview_mod.capture(proj, os.path.join(work, "p.json"))
        facts = json.load(open(m["_summary_path"]))["facts"]
        assert facts["overrides"] == {"process.layer_height": "0.16"}

    def test_changed_project_gets_new_bundle(self, work, box):
        proj = make_project(box)
        pp = os.path.join(work, "p.json")
        a = preview_mod.capture(proj, pp)
        T.add_transform(proj, "scale", 0.5)
        b = preview_mod.capture(proj, pp)
        assert b["cached"] is False and b["_bundle_dir"] != a["_bundle_dir"]
        assert b["metrics"]["max_z_mm"] < a["metrics"]["max_z_mm"]

    def test_diff_reports_layer_change(self, work, box):
        proj = make_project(box)
        pp = os.path.join(work, "p.json")
        preview_mod.capture(proj, pp)
        config_mod.set_override(proj, "layer_height", "0.12")
        d = preview_mod.diff(proj, pp)
        print(f"\n  Diff bundle: {d['_bundle_dir']}")
        assert d["bundle_kind"] == "diff" and len(d["source_bundles"]) == 2
        assert d["deltas"]["layers"]["before"] == 150 and abs(d["deltas"]["layers"]["after"] - 250) <= 2
        assert "layers" in json.load(open(os.path.join(d["_bundle_dir"], "artifacts", "diff.json")))["changed"]
        ids = {a["artifact_id"] for a in d["artifacts"]}
        assert {"diff", "before_hero", "after_hero"} <= ids

    def test_diff_without_baseline_fails(self, work, box):
        with pytest.raises(FileNotFoundError, match="preview capture"):
            preview_mod.diff(make_project(box), os.path.join(work, "p.json"))


# ── Installed CLI via subprocess ─────────────────────────────────


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-orcaslicer")

    def _run(self, args, check=True, input=None):
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, check=check, input=input)

    def test_help(self):
        r = self._run(["--help"])
        assert r.returncode == 0 and "OrcaSlicer" in r.stdout
        for g in ("project", "slice", "preview", "transform"):
            assert g in r.stdout

    def test_version(self):
        assert "1.0.0" in self._run(["--version"]).stdout

    def test_backend_info_json(self):
        data = json.loads(self._run(["--json", "backend", "info"]).stdout)
        assert os.path.isfile(data["executable"]) and "--slice" in data["flags"]

    def test_project_new_json(self, work):
        out = os.path.join(work, "t.orca-cli.json")
        data = json.loads(self._run(["--json", "project", "new", "-n", "t", "-o", out]).stdout)
        assert data["name"] == "t" and os.path.isfile(out)

    def test_full_agent_workflow_to_gcode(self, work, box):
        proj = os.path.join(work, "job.orca-cli.json")
        out = os.path.join(work, "out")
        self._run(["project", "new", "-n", "job", "-o", proj])
        base = ["--json", "--project", proj]
        self._run(base + ["model", "add", box])
        self._run(base + ["profile", "use", "process", "0.12mm Fine"])
        self._run(base + ["profile", "use", "filament", "Generic PETG"])
        self._run(base + ["config", "set", "sparse_infill_density", "20%"])
        self._run(base + ["transform", "rotate", "90", "--axis", "x"])
        res = json.loads(self._run(base + ["slice", "run", "-o", out, "--export-3mf",
                                           os.path.join(work, "job.3mf")]).stdout)
        g = res["plates"][0]
        print(f"\n  CLI G-code: {g['path']} ({g['bytes']:,} bytes)")
        assert os.path.isfile(g["path"]) and open(g["path"], errors="replace").read(60).startswith("; HEADER")
        assert abs(g["max_z"] - 10.0) <= 0.12 and abs(g["layers"] - 83) <= 2   # within one layer height
        assert 240 in temps_in_gcode(g["path"])           # PETG
        assert zipfile.is_zipfile(res["export_3mf"])
        # state persisted by auto-save
        saved = json.load(open(proj))
        assert saved["profiles"]["process"] == "0.12mm Fine" and len(saved["history"]) == 1
        stats = json.loads(self._run(base + ["slice", "stats"]).stdout)
        assert stats["summary"]["layer_count"] == g["layers"]
        info = json.loads(self._run(["--json", "slice", "gcode-info", g["path"]]).stdout)
        assert info["layers"] == g["layers"]
        exp = json.loads(self._run(base + ["export", "gcode", os.path.join(work, "final.gcode")]).stdout)
        assert os.path.isfile(exp["path"])

    def test_autosave_and_dry_run(self, work, box):
        proj = os.path.join(work, "a.orca-cli.json")
        self._run(["project", "new", "-o", proj])
        self._run(["--project", proj, "model", "add", box])
        assert len(json.load(open(proj))["models"]) == 1
        self._run(["--dry-run", "--project", proj, "transform", "scale", "3"])
        assert json.load(open(proj))["transforms"] == []
        self._run(["--project", proj, "transform", "scale", "3"])
        assert json.load(open(proj))["transforms"][0]["value"] == 3.0

    def test_dry_run_slice_does_not_record_history(self, work, box):
        proj = os.path.join(work, "d.orca-cli.json")
        self._run(["project", "new", "-o", proj, "--model", box])
        self._run(["--dry-run", "--project", proj, "slice", "run", "-o", os.path.join(work, "o")])
        assert json.load(open(proj))["history"] == []

    def test_config_validation_errors(self, work, box):
        proj = os.path.join(work, "e.orca-cli.json")
        self._run(["project", "new", "-o", proj])
        r = self._run(["--json", "--project", proj, "config", "set", "layer_hight", "0.1"], check=False)
        assert r.returncode == 1 and "Did you mean" in json.loads(r.stdout)["error"]
        r = self._run(["--json", "--project", proj, "config", "set", "layer_height", "thick"], check=False)
        assert r.returncode == 1 and "expects a number" in json.loads(r.stdout)["error"]

    def test_unknown_preset_error(self, work):
        r = self._run(["--json", "project", "new", "--filament", "Unobtainium", "-o",
                       os.path.join(work, "x.json")], check=False)
        assert r.returncode == 1 and "Unknown filament preset" in json.loads(r.stdout)["error"]

    def test_missing_model_error(self, work):
        proj = os.path.join(work, "m.orca-cli.json")
        self._run(["project", "new", "-o", proj])
        r = self._run(["--json", "--project", proj, "model", "add", "/no/such.stl"], check=False)
        assert r.returncode == 1 and json.loads(r.stdout)["type"] == "file_not_found"

    def test_model_inspect_via_real_backend(self, work, box):
        proj = os.path.join(work, "i.orca-cli.json")
        self._run(["project", "new", "-o", proj, "--model", box])
        data = json.loads(self._run(["--json", "--project", proj, "model", "inspect"]).stdout)
        assert data["info"]["box.stl"]["size_z"] == 30.0

    def test_config_keys_from_real_schema(self):
        data = json.loads(self._run(["--json", "config", "keys", "--search", "sparse_infill"]).stdout)
        assert any(k["key"] == "sparse_infill_density" for k in data)

    def test_preview_via_cli(self, work, box):
        proj = os.path.join(work, "pv.orca-cli.json")
        self._run(["project", "new", "-o", proj, "--model", box])
        base = ["--json", "--project", proj]
        m = json.loads(self._run(base + ["preview", "capture"]).stdout)
        assert m["bundle_kind"] == "capture" and os.path.isfile(os.path.join(m["_bundle_dir"], "artifacts", "hero.png"))
        latest = json.loads(self._run(base + ["preview", "latest"]).stdout)
        assert latest["_bundle_dir"] == m["_bundle_dir"]
        recipes = json.loads(self._run(base + ["preview", "recipes"]).stdout)
        assert {r["name"] for r in recipes} == {"quick", "full"}

    def test_export_3mf_and_stl_via_cli(self, work, box):
        proj = os.path.join(work, "x.orca-cli.json")
        self._run(["project", "new", "-o", proj, "--model", box])
        base = ["--json", "--project", proj]
        self._run(base + ["transform", "scale", "2"])
        r = json.loads(self._run(base + ["export", "3mf", os.path.join(work, "x.3mf")]).stdout)
        assert r["sliced"] and zipfile.is_zipfile(r["path"])
        r = json.loads(self._run(base + ["export", "stl", os.path.join(work, "stls")]).stdout)
        assert os.path.getsize(r["files"][0]["path"]) > 84
        r = json.loads(self._run(base + ["export", "settings", os.path.join(work, "s.json")]).stdout)
        assert r["keys"] > 600

    def test_repl_session_over_stdin(self, work, box):
        proj = os.path.join(work, "r.orca-cli.json")
        script = "\n".join([f"project new -n repl -o {proj}", f"model add {box}", "transform scale 2",
                            "session undo", "project save", "quit"]) + "\n"
        r = self._run([], input=script)
        assert r.returncode == 0 and "Goodbye" in r.stdout
        saved = json.load(open(proj))
        assert len(saved["models"]) == 1 and saved["transforms"] == []   # scale was undone

    def test_slice_failure_is_structured_json(self, work, box):
        proj = os.path.join(work, "f.orca-cli.json")
        self._run(["project", "new", "-o", proj, "--model", box])
        os.remove(box)
        r = self._run(["--json", "--project", proj, "slice", "run", "-o", os.path.join(work, "o")], check=False)
        assert r.returncode == 1 and json.loads(r.stdout)["type"] == "file_not_found"
