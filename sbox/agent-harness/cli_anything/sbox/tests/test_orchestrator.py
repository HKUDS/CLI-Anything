"""Tests for the map test orchestrator."""

import json
import os
import pytest

from cli_anything.sbox.core import test_orchestrator


class TestDataPathResolution:
    def test_computes_data_path_from_sbox_install_and_ident(self, tmp_path):
        sbox_install = str(tmp_path / "sbox")
        data_dir = tmp_path / "sbox" / "data" / "local" / "hold_the_line#local"
        data_dir.mkdir(parents=True)

        result = test_orchestrator.resolve_data_path(sbox_install, "hold_the_line")
        assert result == str(data_dir)

    def test_raises_if_data_dir_missing(self, tmp_path):
        sbox_install = str(tmp_path / "sbox")
        (tmp_path / "sbox").mkdir()

        with pytest.raises(FileNotFoundError):
            test_orchestrator.resolve_data_path(sbox_install, "hold_the_line")


class TestComboMatrix:
    def test_default_matrix_has_12_combos(self):
        combos = test_orchestrator.build_combo_matrix()
        assert len(combos) == 12

    def test_all_strategies_present(self):
        combos = test_orchestrator.build_combo_matrix()
        strategies = {c["strategy"] for c in combos}
        assert strategies == {"Serpentine", "Gilbert", "SpanningTree", "Backbite"}

    def test_all_sizes_present(self):
        combos = test_orchestrator.build_combo_matrix()
        sizes = {c["size"] for c in combos}
        assert sizes == {"Small", "Medium", "Large"}

    def test_explicit_seeds(self):
        combos = test_orchestrator.build_combo_matrix(seeds=[42, 99])
        assert len(combos) == 24
        assert all(c["seed"] in [42, 99] for c in combos)

    def test_seed_count(self):
        combos = test_orchestrator.build_combo_matrix(seed_count=3)
        assert len(combos) == 36
        assert all(isinstance(c["seed"], int) for c in combos)

    def test_filter_strategies(self):
        combos = test_orchestrator.build_combo_matrix(
            strategies=["Gilbert", "Backbite"]
        )
        assert len(combos) == 6
        strategies = {c["strategy"] for c in combos}
        assert strategies == {"Gilbert", "Backbite"}

    def test_filter_sizes(self):
        combos = test_orchestrator.build_combo_matrix(sizes=["Small"])
        assert len(combos) == 4


class TestConfigIO:
    def test_write_config(self, tmp_path):
        test_orchestrator.write_test_config(
            str(tmp_path), "Gilbert", "Large", 42
        )
        with open(os.path.join(str(tmp_path), "test_config.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"Strategy": "Gilbert", "Size": "Large", "Seed": 42}

    def test_cleanup_files(self, tmp_path):
        for name in ["test_config.json", "screenshot.rgba", "metadata.json", "test_complete.json"]:
            (tmp_path / name).write_text("x")

        test_orchestrator.cleanup_data_files(str(tmp_path))

        for name in ["test_config.json", "screenshot.rgba", "metadata.json", "test_complete.json"]:
            assert not (tmp_path / name).exists()

    def test_cleanup_ignores_missing(self, tmp_path):
        test_orchestrator.cleanup_data_files(str(tmp_path))


class TestSentinelPolling:
    def test_returns_dict_when_sentinel_exists(self, tmp_path):
        sentinel = {"success": True}
        (tmp_path / "test_complete.json").write_text(json.dumps(sentinel))

        result = test_orchestrator.check_sentinel(str(tmp_path))
        assert result == {"success": True}

    def test_returns_none_when_no_sentinel(self, tmp_path):
        result = test_orchestrator.check_sentinel(str(tmp_path))
        assert result is None

    def test_returns_error_dict_on_failure(self, tmp_path):
        sentinel = {"success": False, "error": "generation failed"}
        (tmp_path / "test_complete.json").write_text(json.dumps(sentinel))

        result = test_orchestrator.check_sentinel(str(tmp_path))
        assert result["success"] is False
        assert result["error"] == "generation failed"


class TestRgbaConversion:
    def test_converts_rgba_bytes_to_png(self, tmp_path):
        Image = pytest.importorskip("PIL.Image")
        width, height = 2, 2
        red_pixel = bytes([255, 0, 0, 255])
        rgba_bytes = red_pixel * (width * height)

        rgba_path = str(tmp_path / "screenshot.rgba")
        with open(rgba_path, "wb") as f:
            f.write(rgba_bytes)

        png_path = str(tmp_path / "output.png")
        test_orchestrator.rgba_to_png(rgba_path, png_path, width, height)

        assert os.path.exists(png_path)
        img = Image.open(png_path)
        assert img.size == (2, 2)
        assert img.getpixel((0, 0)) == (255, 0, 0, 255)

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            test_orchestrator.rgba_to_png(
                str(tmp_path / "missing.rgba"),
                str(tmp_path / "out.png"),
                2, 2
            )
