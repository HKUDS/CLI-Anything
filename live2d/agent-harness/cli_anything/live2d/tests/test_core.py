"""Unit tests for Live2D CLI core modules (no backend needed)."""

import json
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from cli_anything.live2d.core.parser import load_model, save_model, ModelInfo, MotionRef, ExpressionRef
from cli_anything.live2d.core.validator import validate_model, ValidationResult
from cli_anything.live2d.core.scanner import scan_directory, find_model_files
from cli_anything.live2d.core.backup import snapshot, auto_backup, list_backups, _backup_dir_for
from click.testing import CliRunner


# ── Fixtures ────────────────────────────────────────────────────

SAMPLE_MODEL3 = {
    "Version": 3,
    "FileReferences": {
        "Moc": "model.moc3",
        "Textures": ["textures/texture_00.png", "textures/texture_01.png"],
        "Physics": "model.physics3.json",
        "Pose": "model.pose3.json",
        "UserData": "model userdata3.json",
        "Expressions": [
            {"Name": "happy", "File": "expressions/happy.exp3.json"},
            {"Name": "angry", "File": "expressions/angry.exp3.json"},
        ],
        "Motions": {
            "idle": [
                {"File": "motions/idle_01.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5},
                {"File": "motions/idle_02.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5},
            ],
            "tap_body": [
                {"File": "motions/tap_body.motion3.json", "FadeInTime": 0.2, "FadeOutTime": 0.2},
            ],
        },
    },
    "Groups": [
        {"Target": "Parameter", "Name": "EyeBlink", "Ids": "ParamEyeLOpen,ParamEyeROpen"},
    ],
}


@pytest.fixture
def sample_model3_file(tmp_path):
    """Create a temporary .model3.json file."""
    model_file = tmp_path / "test_model.model3.json"
    model_file.write_text(json.dumps(SAMPLE_MODEL3), encoding="utf-8")
    return model_file


@pytest.fixture
def sample_model_with_files(tmp_path):
    """Create a temporary model with all referenced files."""
    model_dir = tmp_path / "character"
    model_dir.mkdir()

    # Model file
    model_file = model_dir / "test_model.model3.json"
    model_file.write_text(json.dumps(SAMPLE_MODEL3), encoding="utf-8")

    # Create referenced files
    (model_dir / "model.moc3").touch()
    (model_dir / "textures").mkdir()
    (model_dir / "textures" / "texture_00.png").touch()
    (model_dir / "textures" / "texture_01.png").touch()
    (model_dir / "model.physics3.json").touch()
    (model_dir / "model.pose3.json").touch()
    (model_dir / "model userdata3.json").touch()
    (model_dir / "expressions").mkdir()
    (model_dir / "expressions" / "happy.exp3.json").touch()
    (model_dir / "expressions" / "angry.exp3.json").touch()
    (model_dir / "motions").mkdir()
    (model_dir / "motions" / "idle_01.motion3.json").touch()
    (model_dir / "motions" / "idle_02.motion3.json").touch()
    (model_dir / "motions" / "tap_body.motion3.json").touch()

    return model_file


# ── Parser Tests ────────────────────────────────────────────────

class TestParser:
    def test_load_model(self, sample_model3_file):
        info = load_model(sample_model3_file)
        assert isinstance(info, ModelInfo)
        assert info.version == 3
        assert info.moc3 == "model.moc3"
        assert info.texture_count == 2
        assert info.motion_count == 3
        assert info.motion_group_count == 2
        assert info.expression_count == 2
        assert info.physics == "model.physics3.json"
        assert info.pose == "model.pose3.json"

    def test_motions_parsed(self, sample_model3_file):
        info = load_model(sample_model3_file)
        assert "idle" in info.motions
        assert "tap_body" in info.motions
        assert len(info.motions["idle"]) == 2
        assert info.motions["idle"][0].fade_in == 0.5

    def test_expressions_parsed(self, sample_model3_file):
        info = load_model(sample_model3_file)
        names = [e.name for e in info.expressions]
        assert "happy" in names
        assert "angry" in names

    def test_groups_parsed(self, sample_model3_file):
        info = load_model(sample_model3_file)
        assert len(info.groups) == 1
        assert info.groups[0]["Name"] == "EyeBlink"

    def test_to_dict(self, sample_model3_file):
        info = load_model(sample_model3_file)
        d = info.to_dict()
        assert isinstance(d, dict)
        assert d["texture_count"] == 2
        assert d["motion_count"] == 3

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_model(tmp_path / "nonexistent.model3.json")

    def test_bad_extension(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("{}")
        with pytest.raises(ValueError):
            load_model(f)


# ── Validator Tests ─────────────────────────────────────────────

class TestValidator:
    def test_valid_model(self, sample_model_with_files):
        info = load_model(sample_model_with_files)
        result = validate_model(info)
        assert result.ok
        assert result.checked > 0
        assert len(result.errors) == 0

    def test_missing_files(self, sample_model3_file):
        """Model references files that don't exist -> errors."""
        info = load_model(sample_model3_file)
        result = validate_model(info)
        assert not result.ok
        assert len(result.errors) > 0
        assert any("Moc3" in e for e in result.errors)

    def test_result_to_dict(self, sample_model3_file):
        info = load_model(sample_model3_file)
        result = validate_model(info)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "ok" in d
        assert "errors" in d


# ── Scanner Tests ───────────────────────────────────────────────

class TestScanner:
    def test_scan_finds_models(self, sample_model_with_files):
        model_dir = sample_model_with_files.parent
        models = scan_directory(model_dir)
        assert len(models) == 1
        assert models[0].moc3 == "model.moc3"

    def test_scan_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        models = scan_directory(empty)
        assert len(models) == 0

    def test_scan_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            scan_directory(tmp_path / "nonexistent")

    def test_find_model_files(self, sample_model_with_files):
        model_dir = sample_model_with_files.parent
        files = find_model_files(model_dir)
        assert len(files) == 1
        assert files[0].suffix == ".json"


# ── Backup Tests ───────────────────────────────────────────────

class TestFlatten:
    def test_flatten_copies_sound_assets(self, tmp_path):
        """Regression: flatten must copy motion Sound files, not just reference them."""
        from cli_anything.live2d.live2d_cli import cli

        model_dir = tmp_path / "character"
        model_dir.mkdir()

        # Create model with Sound reference
        model_data = {
            "Version": 3,
            "FileReferences": {
                "Moc": "model.moc3",
                "Textures": ["textures/tex.png"],
                "Motions": {
                    "idle": [
                        {
                            "File": "motions/idle.motion3.json",
                            "FadeInTime": 0.5,
                            "FadeOutTime": 0.5,
                            "Sound": "sounds/effect.wav",
                        }
                    ]
                },
            },
        }
        model_file = model_dir / "test.model3.json"
        model_file.write_text(json.dumps(model_data), encoding="utf-8")

        # Create referenced files
        (model_dir / "model.moc3").touch()
        (model_dir / "textures").mkdir()
        (model_dir / "textures" / "tex.png").touch()
        (model_dir / "motions").mkdir()
        (model_dir / "motions" / "idle.motion3.json").write_text("{}", encoding="utf-8")
        (model_dir / "sounds").mkdir()
        sound_file = model_dir / "sounds" / "effect.wav"
        sound_file.write_bytes(b"RIFF....WAVE")

        out_dir = tmp_path / "flat_output"

        runner = CliRunner()
        result = runner.invoke(cli, ["flatten", str(model_file), "-o", str(out_dir)])

        assert result.exit_code == 0, f"flatten failed: {result.output}"

        # Verify sound file was copied
        assert (out_dir / "effect.wav").exists(), (
            f"Sound file 'effect.wav' was not copied to output dir. "
            f"Contents: {list(out_dir.iterdir()) if out_dir.exists() else 'dir missing'}"
        )

        # Verify model JSON references flat sound path
        flat_model = json.loads((out_dir / "test.model3.json").read_text(encoding="utf-8"))
        flat_motion = flat_model["FileReferences"]["Motions"]["idle"][0]
        assert flat_motion["Sound"] == "effect.wav", (
            f"Expected flat Sound path 'effect.wav', got '{flat_motion.get('Sound')}'"
        )


class TestBackup:
    def test_backup_clean_json_mode_deletes_files(self, sample_model3_file):
        """Regression: backup-clean --json must actually delete old backups, not just report."""
        from cli_anything.live2d.live2d_cli import cli
        from cli_anything.live2d.core.backup import _backup_dir_for

        # Create 5 backups with distinct content
        for i in range(5):
            sample_model3_file.write_text(
                json.dumps({"Version": i, "FileReferences": {}}), encoding="utf-8"
            )
            snapshot(sample_model3_file)

        bdir = _backup_dir_for(sample_model3_file)
        backups = sorted(bdir.glob("*.model3.json"), reverse=True)
        assert len(backups) == 5

        # Invoke backup-clean --keep 2 --json through the CLI
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--json", "backup-clean", str(sample_model3_file), "--keep", "2"
        ])

        assert result.exit_code == 0, f"backup-clean failed: {result.output}"

        # Verify only 2 backups remain on disk
        remaining = sorted(bdir.glob("*.model3.json"), reverse=True)
        assert len(remaining) == 2, f"Expected 2 backups after cleanup, got {len(remaining)}"

        # Verify JSON output reports the deletion
        out = json.loads(result.output)
        assert out["delete"] == 3
        assert out["total"] == 5
        assert len(out["deleted"]) == 3

    def test_auto_backup_skips_unchanged_content(self, sample_model3_file):
        """Regression: auto_backup skips when content is unchanged (not just <1s old)."""
        # First backup
        result1 = auto_backup(sample_model3_file)
        assert result1 is not None

        # Same content -> should skip
        result2 = auto_backup(sample_model3_file)
        assert result2 is None

        backups = list_backups(sample_model3_file)
        assert len(backups) == 1

    def test_auto_backup_saves_changed_content(self, sample_model3_file):
        """Regression: auto_backup creates new backup when content changes."""
        result1 = auto_backup(sample_model3_file)
        assert result1 is not None

        # Modify content
        data = json.loads(sample_model3_file.read_text(encoding="utf-8"))
        data["Version"] = 999
        sample_model3_file.write_text(json.dumps(data), encoding="utf-8")

        result2 = auto_backup(sample_model3_file)
        assert result2 is not None
        assert result2 != result1

        backups = list_backups(sample_model3_file)
        assert len(backups) == 2

    def test_save_model_atomic(self, sample_model3_file):
        """Regression: save_model writes atomically via temp file + os.replace."""
        info = load_model(sample_model3_file)
        info.moc3 = "updated_model.moc3"

        # Track os.replace calls to verify atomic write
        original_replace = os.replace
        replace_calls = []

        def tracking_replace(src, dst):
            replace_calls.append((str(src), str(dst)))
            # Verify the temp file exists before replace
            assert Path(src).exists(), f"Temp file {src} should exist before replace"
            return original_replace(src, dst)

        with patch("cli_anything.live2d.core.parser.os.replace", side_effect=tracking_replace):
            save_model(info)

        # Verify os.replace was called (atomic write)
        assert len(replace_calls) == 1, "save_model should call os.replace exactly once"
        src, dst = replace_calls[0]
        assert ".tmp" in src or ".model3.json" in src

        # Verify the file was actually updated
        reloaded = load_model(sample_model3_file)
        assert reloaded.moc3 == "updated_model.moc3"

    def test_save_model_cleanup_on_error(self, sample_model3_file):
        """Regression: save_model cleans up temp file on error."""
        info = load_model(sample_model3_file)
        info.moc3 = "should_not_persist.moc3"

        bdir = sample_model3_file.parent
        tmp_files_before = set(bdir.glob(".*.tmp"))

        # Force an error during write
        with patch("cli_anything.live2d.core.parser.os.fdopen", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                save_model(info)

        tmp_files_after = set(bdir.glob(".*.tmp"))
        new_tmps = tmp_files_after - tmp_files_before
        assert len(new_tmps) == 0, f"Temp files not cleaned up: {new_tmps}"

        # Original file should be unchanged
        reloaded = load_model(sample_model3_file)
        assert reloaded.moc3 != "should_not_persist.moc3"
