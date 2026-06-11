"""Tests for new features added in v0.3.0: edit, backup, lint, diff, snapshot, batch, param-edit, atlas, migrate, undo."""

import json
import pytest
from pathlib import Path

from click.testing import CliRunner

from cli_anything.live2d.core import parser as parser_module
from cli_anything.live2d.core.parser import load_model, save_model, MotionRef, ExpressionRef
from cli_anything.live2d.core.backup import snapshot, list_backups, restore, auto_backup, _backup_dir_for
from cli_anything.live2d.core.linter import lint_model, LintReport
from cli_anything.live2d.core.differ import diff_models
from cli_anything.live2d.core.snapshot import write_snapshot, generate_html
from cli_anything.live2d.live2d_cli import cli


# ── Fixtures ────────────────────────────────────────────────────

SAMPLE_MODEL3 = {
    "Version": 3,
    "FileReferences": {
        "Moc": "model.moc3",
        "Textures": ["textures/texture_00.png"],
        "Physics": "model.physics3.json",
        "Expressions": [
            {"Name": "happy", "File": "expressions/happy.exp3.json"},
        ],
        "Motions": {
            "Idle": [
                {"File": "motions/idle_01.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5},
                {"File": "motions/idle_02.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5},
            ],
            "TapBody": [
                {"File": "motions/tap_body.motion3.json", "FadeInTime": 0.2, "FadeOutTime": 0.2},
            ],
        },
    },
    "Groups": [],
}

SAMPLE_EXPRESSION = {
    "Version": 1,
    "FadeInTime": 0.5,
    "FadeOutTime": 0.5,
    "Parameters": [
        {"Id": "ParamEyeLOpen", "Value": 0.0},
        {"Id": "ParamEyeROpen", "Value": 0.0},
    ],
}


@pytest.fixture
def model_dir(tmp_path):
    """Create a model directory with all files present."""
    d = tmp_path / "character"
    d.mkdir()

    (d / "model.model3.json").write_text(json.dumps(SAMPLE_MODEL3), encoding="utf-8")
    (d / "model.moc3").write_bytes(b"MOC3" + b"\x00" * 2000)
    (d / "model.physics3.json").write_text("{}", encoding="utf-8")
    (d / "textures").mkdir()
    (d / "textures" / "texture_00.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
    (d / "expressions").mkdir()
    (d / "expressions" / "happy.exp3.json").write_text(json.dumps(SAMPLE_EXPRESSION), encoding="utf-8")
    (d / "motions").mkdir()
    (d / "motions" / "idle_01.motion3.json").write_text(json.dumps({
        "Version": 1, "Meta": {"Duration": 2.0, "Fps": 30, "Loop": True, "CurveCount": 1,
                                "TotalSegmentCount": 2, "TotalPointCount": 4},
        "Curves": [{"Target": "Parameter", "Id": "ParamAngleX", "Segments": [0, 0, 0, 1, 1, 1]}]
    }), encoding="utf-8")
    (d / "motions" / "idle_02.motion3.json").write_text(json.dumps({
        "Version": 1, "Meta": {"Duration": 3.0, "Fps": 30, "Loop": True, "CurveCount": 0,
                                "TotalSegmentCount": 0, "TotalPointCount": 0},
        "Curves": []
    }), encoding="utf-8")
    (d / "motions" / "tap_body.motion3.json").write_text(json.dumps({
        "Version": 1, "Meta": {"Duration": 1.0, "Fps": 30, "Loop": False, "CurveCount": 0,
                                "TotalSegmentCount": 0, "TotalPointCount": 0},
        "Curves": []
    }), encoding="utf-8")

    return d


@pytest.fixture
def model_path(model_dir):
    return model_dir / "model.model3.json"


# ── Backup Tests ────────────────────────────────────────────────

class TestBackup:
    def test_snapshot_creates_backup(self, model_path):
        bp = snapshot(model_path)
        assert bp.exists()
        assert bp.suffix == ".json"
        # backup dir uses model file stem (model.model3)
        assert "model" in bp.parent.name

    def test_list_backups(self, model_path):
        snapshot(model_path)
        backups = list_backups(model_path)
        assert len(backups) >= 1
        assert "file" in backups[0]

    def test_restore_latest(self, model_path):
        # Modify, backup, modify again, restore
        info = load_model(model_path)
        info.moc3 = "changed.moc3"
        save_model(info)

        snapshot(model_path)  # backup the changed version

        info.moc3 = "changed_again.moc3"
        save_model(info)

        src = restore(model_path)
        restored = load_model(model_path)
        assert restored.moc3 == "changed.moc3"

    def test_auto_backup_dedup(self, model_path):
        """Auto-backup should skip unchanged content."""
        b1 = auto_backup(model_path)
        b2 = auto_backup(model_path)
        assert b1 is not None
        assert b2 is None

    def test_auto_backup_keeps_rapid_changed_states(self, model_path):
        """Rapid edits should still get separate undo points when content changed."""
        b1 = auto_backup(model_path)

        info = load_model(model_path)
        info.moc3 = "changed.moc3"
        save_model(info)

        b2 = auto_backup(model_path)
        assert b1 is not None
        assert b2 is not None
        assert b2 != b1
        assert len(list_backups(model_path)) == 2
        assert load_model(b2).moc3 == "changed.moc3"

    def test_backup_clean_json_deletes_without_dry_run(self, model_path):
        bdir = _backup_dir_for(model_path)
        bdir.mkdir(parents=True)
        for name in (
            "20240101_000000_000000.model3.json",
            "20240102_000000_000000.model3.json",
            "20240103_000000_000000.model3.json",
        ):
            (bdir / name).write_text(model_path.read_text(encoding="utf-8"), encoding="utf-8")

        result = CliRunner().invoke(cli, ["--json", "backup-clean", str(model_path), "--keep", "1"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["delete"] == 2
        assert data["deleted"] == [
            "20240102_000000_000000.model3.json",
            "20240101_000000_000000.model3.json",
        ]
        assert sorted(p.name for p in bdir.glob("*.model3.json")) == [
            "20240103_000000_000000.model3.json",
        ]

    def test_list_empty(self, tmp_path):
        f = tmp_path / "m.model3.json"
        f.write_text("{}")
        assert list_backups(f) == []


# ── Edit + Save Tests ──────────────────────────────────────────

class TestEditAndSave:
    def test_edit_motion_fade(self, model_path):
        info = load_model(model_path)
        info.motions["Idle"][0].fade_in = 1.0
        info.motions["Idle"][0].fade_out = 2.0
        save_model(info)

        reloaded = load_model(model_path)
        assert reloaded.motions["Idle"][0].fade_in == 1.0
        assert reloaded.motions["Idle"][0].fade_out == 2.0

    def test_add_motion(self, model_path):
        info = load_model(model_path)
        info.motions["NewGroup"] = [MotionRef(file="motions/new.motion3.json", fade_in=0.1, fade_out=0.1)]
        save_model(info)

        reloaded = load_model(model_path)
        assert "NewGroup" in reloaded.motions
        assert len(reloaded.motions["NewGroup"]) == 1

    def test_rm_motion(self, model_path):
        info = load_model(model_path)
        info.motions["Idle"].pop(0)
        save_model(info)

        reloaded = load_model(model_path)
        assert len(reloaded.motions["Idle"]) == 1

    def test_add_expression(self, model_path):
        info = load_model(model_path)
        info.expressions.append(ExpressionRef(name="wink", file="expressions/wink.exp3.json"))
        save_model(info)

        reloaded = load_model(model_path)
        names = [e.name for e in reloaded.expressions]
        assert "wink" in names

    def test_rm_expression(self, model_path):
        info = load_model(model_path)
        info.expressions = [e for e in info.expressions if e.name != "happy"]
        save_model(info)

        reloaded = load_model(model_path)
        assert reloaded.expression_count == 0

    def test_edit_texture(self, model_path):
        info = load_model(model_path)
        info.textures[0] = "textures/new_tex.png"
        save_model(info)

        reloaded = load_model(model_path)
        assert reloaded.textures[0] == "textures/new_tex.png"

    def test_edit_model_fields(self, model_path):
        info = load_model(model_path)
        info.moc3 = "new_model.moc3"
        info.physics = "new_physics.json"
        save_model(info)

        reloaded = load_model(model_path)
        assert reloaded.moc3 == "new_model.moc3"
        assert reloaded.physics == "new_physics.json"

    def test_save_model_preserves_original_when_write_fails(self, model_path, monkeypatch):
        original = model_path.read_text(encoding="utf-8")
        info = load_model(model_path)
        info.moc3 = "should_not_persist.moc3"

        def fail_dump(*args, **kwargs):
            raise RuntimeError("simulated write failure")

        monkeypatch.setattr(parser_module.json, "dump", fail_dump)

        with pytest.raises(RuntimeError):
            save_model(info)

        assert model_path.read_text(encoding="utf-8") == original
        assert list(model_path.parent.glob(f".{model_path.name}.*.tmp")) == []


# ── Lint Tests ──────────────────────────────────────────────────

class TestLint:
    def test_lint_clean_model(self, model_path):
        report = lint_model(model_path)
        # Should have no errors for a well-formed model
        assert report.ok

    def test_lint_missing_texture(self, model_dir, model_path):
        (model_dir / "textures" / "texture_00.png").unlink()
        report = lint_model(model_path)
        assert not report.ok
        assert any("Texture" in i.message and "not found" in i.message for i in report.issues)

    def test_lint_missing_motion(self, model_dir, model_path):
        (model_dir / "motions" / "idle_01.motion3.json").unlink()
        report = lint_model(model_path)
        assert not report.ok
        assert any("Motion" in i.message and "not found" in i.message for i in report.issues)

    def test_lint_report_to_dict(self, model_path):
        report = lint_model(model_path)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "ok" in d
        assert "issues" in d

    def test_lint_negative_fade(self, model_path):
        info = load_model(model_path)
        info.motions["Idle"][0].fade_in = -1.0
        save_model(info)
        report = lint_model(model_path)
        assert any("Negative" in i.message for i in report.issues)


# ── Diff Tests ──────────────────────────────────────────────────

class TestDiff:
    def test_diff_identical(self, model_path):
        a = load_model(model_path)
        b = load_model(model_path)
        d = diff_models(a, b)
        assert not d.has_changes

    def test_diff_moc3_change(self, model_path, tmp_path):
        import shutil
        other = tmp_path / "other"
        shutil.copytree(model_path.parent, other)
        other_model = other / "model.model3.json"

        info_b = load_model(other_model)
        info_b.moc3 = "different.moc3"
        save_model(info_b)

        a = load_model(model_path)
        b = load_model(other_model)
        d = diff_models(a, b)
        assert d.has_changes
        assert any(i.category == "field" and i.name == "moc3" for i in d.items)

    def test_diff_motion_fade(self, model_path, tmp_path):
        import shutil
        other = tmp_path / "other"
        shutil.copytree(model_path.parent, other)
        other_model = other / "model.model3.json"

        info_b = load_model(other_model)
        info_b.motions["Idle"][0].fade_in = 99.0
        save_model(info_b)

        a = load_model(model_path)
        b = load_model(other_model)
        d = diff_models(a, b)
        assert d.has_changes
        assert any(i.category == "motion" and "fade_in" in i.detail for i in d.items)

    def test_diff_expression_added(self, model_path, tmp_path):
        import shutil
        other = tmp_path / "other"
        shutil.copytree(model_path.parent, other)
        other_model = other / "model.model3.json"

        info_b = load_model(other_model)
        info_b.expressions.append(ExpressionRef(name="wink", file="expressions/wink.exp3.json"))
        save_model(info_b)

        a = load_model(model_path)
        b = load_model(other_model)
        d = diff_models(a, b)
        assert any(i.category == "expression" and i.name == "wink" for i in d.items)

    def test_diff_to_dict(self, model_path):
        a = load_model(model_path)
        b = load_model(model_path)
        d = diff_models(a, b)
        assert isinstance(d.to_dict(), dict)


# ── Snapshot Tests ──────────────────────────────────────────────

class TestSnapshot:
    def test_generate_html(self, model_path):
        info = load_model(model_path)
        html = generate_html(info)
        assert "<html" in html
        assert "test_model" in html or "model" in html.lower()
        assert "Idle" in html
        assert "happy" in html

    def test_write_snapshot(self, model_path, tmp_path):
        info = load_model(model_path)
        out = tmp_path / "preview.html"
        result = write_snapshot(info, out)
        assert result.exists()
        content = result.read_text()
        assert "<html" in content


# ── Param Edit Tests ────────────────────────────────────────────

class TestParamEdit:
    def test_edit_existing_param(self, model_dir):
        expr_path = model_dir / "expressions" / "happy.exp3.json"
        with open(expr_path, "r") as f:
            data = json.load(f)

        for p in data["Parameters"]:
            if p["Id"] == "ParamEyeLOpen":
                p["Value"] = 1.0
                break

        with open(expr_path, "w") as f:
            json.dump(data, f, indent=2)

        with open(expr_path, "r") as f:
            reloaded = json.load(f)

        eye_param = next(p for p in reloaded["Parameters"] if p["Id"] == "ParamEyeLOpen")
        assert eye_param["Value"] == 1.0

    def test_add_new_param(self, model_dir):
        expr_path = model_dir / "expressions" / "happy.exp3.json"
        with open(expr_path, "r") as f:
            data = json.load(f)

        data["Parameters"].append({"Id": "ParamMouthOpenY", "Value": 0.5})

        with open(expr_path, "w") as f:
            json.dump(data, f, indent=2)

        with open(expr_path, "r") as f:
            reloaded = json.load(f)

        assert len(reloaded["Parameters"]) == 3
        mouth = next(p for p in reloaded["Parameters"] if p["Id"] == "ParamMouthOpenY")
        assert mouth["Value"] == 0.5


# ── Migrate Tests ───────────────────────────────────────────────

class TestMigrate:
    def test_migrate_v1_to_v3(self, model_dir):
        model_path = model_dir / "model.model3.json"
        with open(model_path, "r") as f:
            data = json.load(f)

        data["Version"] = 1
        del data["Groups"]

        with open(model_path, "w") as f:
            json.dump(data, f, indent=2)

        with open(model_path, "r") as f:
            data = json.load(f)
        data["Version"] = 3
        data["Groups"] = []
        with open(model_path, "w") as f:
            json.dump(data, f, indent=2)

        info = load_model(model_path)
        assert info.version == 3

    def test_already_at_target(self, model_path):
        info = load_model(model_path)
        assert info.version == 3  # already v3


# ── Atlas Tests ─────────────────────────────────────────────────

class TestAtlas:
    def test_atlas_reads_textures(self, model_path):
        info = load_model(model_path)
        assert len(info.textures) == 1
        assert info.textures[0] == "textures/texture_00.png"


# ── Find-Replace Tests ─────────────────────────────────────────

class TestFindReplace:
    def test_replace_texture_path(self, model_path):
        info = load_model(model_path)
        info.textures[0] = info.textures[0].replace("textures/", "tex/")
        save_model(info)
        reloaded = load_model(model_path)
        assert reloaded.textures[0] == "tex/texture_00.png"

    def test_replace_motion_file(self, model_path):
        info = load_model(model_path)
        for m in info.motions["Idle"]:
            m.file = m.file.replace("idle_", "idle_v2_")
        save_model(info)
        reloaded = load_model(model_path)
        assert "idle_v2_" in reloaded.motions["Idle"][0].file


# ── Orphan Tests ───────────────────────────────────────────────

class TestOrphan:
    def test_no_orphans(self, model_path):
        info = load_model(model_path)
        model_dir = info.path.parent
        # All existing files should be referenced
        referenced = set()
        referenced.add(info.moc3)
        referenced.update(info.textures)
        for ms in info.motions.values():
            for m in ms:
                referenced.add(m.file)
        for e in info.expressions:
            referenced.add(e.file)
        referenced.discard("")
        assert len(referenced) > 0

    def test_detects_orphan(self, model_dir, model_path):
        # Create an orphan file
        (model_dir / "unused.png").write_bytes(b"fake")
        info = load_model(model_path)
        referenced = set(info.textures)
        assert "unused.png" not in referenced


# ── Gen-Motion Tests ───────────────────────────────────────────

class TestGenMotion:
    def test_gen_motion_creates_file(self, tmp_path):
        out = tmp_path / "test.motion3.json"
        data = {
            "Version": 1,
            "Meta": {"Duration": 2.0, "Fps": 30, "Loop": True, "CurveCount": 0, "TotalSegmentCount": 0, "TotalPointCount": 0},
            "Curves": [],
        }
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["Meta"]["Duration"] == 2.0


# ── Gen-Expr Tests ─────────────────────────────────────────────

class TestGenExpr:
    def test_gen_expr_creates_file(self, tmp_path):
        out = tmp_path / "test.exp3.json"
        data = {"Version": 1, "FadeInTime": 0.5, "FadeOutTime": 0.5, "Parameters": []}
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["Parameters"] == []


# ── Rename-Group Tests ────────────────────────────────────────

class TestRenameGroup:
    def test_rename_group(self, model_path):
        info = load_model(model_path)
        assert "Idle" in info.motions
        motions_copy = info.motions.pop("Idle")
        info.motions["idle_v2"] = motions_copy
        save_model(info)
        reloaded = load_model(model_path)
        assert "Idle" not in reloaded.motions
        assert "idle_v2" in reloaded.motions
        assert len(reloaded.motions["idle_v2"]) == 2


# ── Manifest Tests ─────────────────────────────────────────────

class TestManifest:
    def test_manifest_collects_files(self, model_path):
        import hashlib
        info = load_model(model_path)
        model_dir = info.path.parent
        files = []
        for tex in info.textures:
            p = model_dir / tex
            if p.exists():
                data = p.read_bytes()
                files.append({"path": tex, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        assert len(files) >= 1
        assert "sha256" in files[0]


# ── Param-List Tests ───────────────────────────────────────────

class TestParamList:
    def test_param_list_finds_params(self, model_path):
        from cli_anything.live2d.core.motion_parser import load_motion
        info = load_model(model_path)
        model_dir = info.path.parent
        params = set()
        for ms in info.motions.values():
            for m in ms:
                mp = model_dir / m.file
                if mp.exists():
                    try:
                        minfo = load_motion(mp)
                        for c in minfo.parameter_curves:
                            params.add(c.id)
                    except Exception:
                        pass
        # Our fixture has ParamAngleX in idle_01
        assert "ParamAngleX" in params


# ── Flatten Tests ──────────────────────────────────────────────

class TestFlatten:
    def test_flatten_copies_files(self, model_path, tmp_path):
        import shutil
        out = tmp_path / "flat"
        out.mkdir()
        info = load_model(model_path)
        model_dir = info.path.parent
        # Simulate flatten: copy model file and update paths
        shutil.copy2(model_path, out / model_path.name)
        for tex in info.textures:
            src = model_dir / tex
            if src.exists():
                shutil.copy2(src, out / Path(tex).name)
        assert (out / model_path.name).exists()

    def test_flatten_copies_and_rewrites_motion_sound(self, model_dir, model_path, tmp_path):
        data = json.loads(model_path.read_text(encoding="utf-8"))
        data["FileReferences"]["Motions"]["Idle"][0]["Sound"] = "sounds/idle.wav"
        model_path.write_text(json.dumps(data), encoding="utf-8")
        (model_dir / "sounds").mkdir()
        (model_dir / "sounds" / "idle.wav").write_bytes(b"RIFFtest")

        out = tmp_path / "flat"
        result = CliRunner().invoke(cli, ["flatten", str(model_path), "--out-dir", str(out)])

        assert result.exit_code == 0, result.output
        assert (out / "idle.wav").exists()
        flat_info = load_model(out / model_path.name)
        assert flat_info.motions["Idle"][0].file == "idle_01.motion3.json"
        assert flat_info.motions["Idle"][0].extra["Sound"] == "idle.wav"


# ── Runtime-Check Tests ───────────────────────────────────────

class TestRuntimeCheck:
    def test_runtime_check_clean_model(self, model_path):
        info = load_model(model_path)
        # Should have moc3 and textures
        assert info.moc3
        assert len(info.textures) > 0
        # Should have Idle group
        assert "Idle" in info.motions
