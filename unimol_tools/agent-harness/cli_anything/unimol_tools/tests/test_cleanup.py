"""
Tests for cleanup module (simplified - core deletion only)
"""

import pytest
import os
from pathlib import Path
from cli_anything.unimol_tools.core.cleanup import (
    delete_model,
    batch_cleanup,
    list_archives
)


@pytest.fixture
def mock_project_with_models(tmp_path):
    """Create mock project with model directories"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    models_dir = project_dir / "models"
    models_dir.mkdir()

    # Create run directories with files
    for i in range(1, 4):
        run_dir = models_dir / f"run_{i:03d}"
        run_dir.mkdir()

        # Create checkpoint file
        checkpoint = run_dir / "checkpoint.pth"
        checkpoint.write_bytes(b"0" * (10 * 1024 * 1024))  # 10MB

        # Create config
        (run_dir / "config.json").write_text('{"epochs": 10}')

        # Create metrics
        (run_dir / "metric.result").write_bytes(b"metrics")

    project = {
        "project_name": "test_project",
        "project_root": str(project_dir),
        "runs": [
            {
                "run_id": f"run_{i:03d}",
                "save_path": str(models_dir / f"run_{i:03d}"),
                "metrics": {"auc": 0.70 + i * 0.05}
            }
            for i in range(1, 4)
        ]
    }

    return project, project_dir


class TestDeleteModel:
    """Test model deletion"""

    def test_delete_existing_model(self, mock_project_with_models):
        """Test deleting an existing model"""
        project, project_dir = mock_project_with_models

        run_id = "run_001"
        run_path = project_dir / "models" / run_id

        # Verify model exists
        assert run_path.exists()

        # Delete model (skip confirmation for test)
        result = delete_model(project, run_id, confirm=False)

        assert result is True
        assert not run_path.exists()

    def test_delete_nonexistent_model(self, mock_project_with_models):
        """Test deleting nonexistent model"""
        project, _ = mock_project_with_models

        # Should return False for nonexistent model
        result = delete_model(project, "run_999", confirm=False)
        assert result is False

    def test_delete_updates_project(self, mock_project_with_models):
        """Test that deletion updates project runs"""
        project, _ = mock_project_with_models

        initial_runs = len(project["runs"])

        delete_model(project, "run_001", confirm=False)

        # Runs should be updated
        assert len(project["runs"]) == initial_runs - 1
        assert not any(r["run_id"] == "run_001" for r in project["runs"])


class TestBatchCleanup:
    """Test batch cleanup operations"""

    def test_batch_delete(self, mock_project_with_models):
        """Test batch deletion"""
        project, project_dir = mock_project_with_models

        delete_ids = ["run_001", "run_002"]

        result = batch_cleanup(
            project,
            delete_ids=delete_ids,
            archive_ids=[],
            confirm=False
        )

        assert "deleted" in result
        assert len(result["deleted"]) == 2

        # Verify directories deleted
        for run_id in delete_ids:
            run_path = project_dir / "models" / run_id
            assert not run_path.exists()

    def test_batch_with_failures(self, mock_project_with_models):
        """Test batch cleanup with some failures"""
        project, _ = mock_project_with_models

        # Include nonexistent model
        result = batch_cleanup(
            project,
            delete_ids=["run_001", "run_999"],
            archive_ids=[],
            confirm=False
        )

        assert "failed" in result
        assert len(result["failed"]) > 0
        assert "run_999" in result["failed"]

    def test_batch_space_freed_calculation(self, mock_project_with_models):
        """Test space freed calculation"""
        project, _ = mock_project_with_models

        result = batch_cleanup(
            project,
            delete_ids=["run_001"],
            archive_ids=[],
            confirm=False
        )

        assert "space_freed_mb" in result
        assert result["space_freed_mb"] > 0


class TestListArchives:
    """Test listing archives (simplified)"""

    def test_list_nonexistent_archive_dir(self):
        """Test listing nonexistent archive directory"""
        archives = list_archives(archive_dir="/nonexistent/path")

        # Should return empty list or handle gracefully
        assert archives == []

    def test_list_empty_archive_dir(self, tmp_path):
        """Test listing empty archive directory"""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        archives = list_archives(archive_dir=str(archive_dir))

        assert archives == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
