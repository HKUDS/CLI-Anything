"""Unit tests for Live2D CLI core modules (no backend needed)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from cli_anything.live2d.core.parser import load_model, ModelInfo, MotionRef, ExpressionRef
from cli_anything.live2d.core.validator import validate_model, ValidationResult
from cli_anything.live2d.core.scanner import scan_directory, find_model_files


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
