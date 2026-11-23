"""Core module unit tests"""

import pytest
import json
from cli_anything.unimol_tools.core import project


class TestProjectManagement:
    """Project management unit tests"""

    def test_create_project(self, tmp_dir):
        """Test project creation"""
        result = project.create_project(
            name="test_project",
            task="classification",
            output_dir=tmp_dir,
            model_name="unimolv1",
        )

        assert result["status"] == "created"
        assert result["project_path"].endswith("project.json")
        assert "test_project" in result["project_path"]

        # Verify file contents
        with open(result["project_path"]) as f:
            proj = json.load(f)

        assert proj["project_type"] == "classification"
        assert proj["config"]["model_name"] == "unimolv1"

    def test_load_nonexistent_project(self):
        """Test loading nonexistent project"""
        with pytest.raises(FileNotFoundError):
            project.load_project("/nonexistent/project.json")

    def test_set_dataset(self, tmp_dir):
        """Test setting dataset"""
        # Create project
        result = project.create_project(
            name="test", task="regression", output_dir=tmp_dir
        )
        proj = result["project"]

        # Create mock data file
        import os
        data_file = os.path.join(tmp_dir, "train.csv")
        with open(data_file, "w") as f:
            f.write("SMILES,TARGET\nCCO,0.5")

        # Set dataset
        update = project.set_dataset(proj, "train", data_file)

        assert update["status"] == "updated"
        assert proj["datasets"]["train"] == data_file

    def test_set_invalid_dataset_type(self, tmp_dir):
        """Test invalid dataset type"""
        result = project.create_project(
            name="test", task="classification", output_dir=tmp_dir
        )
        proj = result["project"]

        with pytest.raises(ValueError, match="Invalid dataset type"):
            project.set_dataset(proj, "invalid", "/fake/path")


class TestMetricFileFreshness:
    """metric.result is a pickle: only a file written during this run may be loaded"""

    def test_missing_file_is_not_fresh(self, tmp_dir):
        from cli_anything.unimol_tools.utils.unimol_backend import UniMolBackend
        import os, time
        assert not UniMolBackend._written_since(os.path.join(tmp_dir, "nope"), time.time())

    def test_stale_file_is_rejected(self, tmp_dir):
        from cli_anything.unimol_tools.utils.unimol_backend import UniMolBackend
        import os, time
        path = os.path.join(tmp_dir, "metric.result")
        open(path, "wb").write(b"x")
        old = time.time() - 3600
        os.utime(path, (old, old))
        assert not UniMolBackend._written_since(path, time.time())

    def test_file_with_a_future_timestamp_is_rejected(self, tmp_dir):
        from cli_anything.unimol_tools.utils.unimol_backend import UniMolBackend
        import os, time
        path = os.path.join(tmp_dir, "metric.result")
        open(path, "wb").write(b"x")
        future = time.time() + 3600
        os.utime(path, (future, future))
        assert not UniMolBackend._written_since(path, time.time() - 10)

    @pytest.mark.skipif(not hasattr(__import__("os"), "getuid"), reason="owner and permission bits are POSIX-only")
    def test_group_or_world_writable_file_is_rejected(self, tmp_dir):
        from cli_anything.unimol_tools.utils.unimol_backend import UniMolBackend
        import os, time
        start = time.time()
        path = os.path.join(tmp_dir, "metric.result")
        open(path, "wb").write(b"x")
        os.chmod(path, 0o666)
        assert not UniMolBackend._written_since(path, start)

    def test_file_written_during_run_is_accepted(self, tmp_dir):
        from cli_anything.unimol_tools.utils.unimol_backend import UniMolBackend
        import os, time
        start = time.time()
        path = os.path.join(tmp_dir, "metric.result")
        open(path, "wb").write(b"x")
        assert UniMolBackend._written_since(path, start)
