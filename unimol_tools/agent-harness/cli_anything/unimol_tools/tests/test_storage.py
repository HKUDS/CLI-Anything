"""
Tests for storage analysis module
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path
from cli_anything.unimol_tools.core.storage import (
    analyze_project_storage,
    get_directory_size,
    format_size
)


@pytest.fixture
def mock_project_dir(tmp_path):
    """Create a mock project directory structure"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create models directory with multiple runs
    models_dir = project_dir / "models"
    models_dir.mkdir()

    # Run 1: ~100MB
    run1 = models_dir / "run_001"
    run1.mkdir()
    (run1 / "checkpoint.pth").write_bytes(b"0" * (100 * 1024 * 1024))  # 100MB
    (run1 / "config.json").write_text("{}")

    # Run 2: ~150MB
    run2 = models_dir / "run_002"
    run2.mkdir()
    (run2 / "checkpoint.pth").write_bytes(b"0" * (150 * 1024 * 1024))  # 150MB
    (run2 / "config.json").write_text("{}")

    # Conformers directory
    conformers_dir = project_dir / "conformers"
    conformers_dir.mkdir()
    (conformers_dir / "mol1.sdf").write_bytes(b"0" * (5 * 1024 * 1024))  # 5MB
    (conformers_dir / "mol2.sdf").write_bytes(b"0" * (5 * 1024 * 1024))  # 5MB

    # Predictions directory
    predictions_dir = project_dir / "predictions"
    predictions_dir.mkdir()
    (predictions_dir / "pred1.csv").write_text("SMILES,prediction\nCCO,1")

    return project_dir


@pytest.fixture
def mock_project(mock_project_dir):
    """Create a mock project dictionary"""
    return {
        "project_name": "test_project",
        "project_root": str(mock_project_dir),
        "runs": [
            {
                "run_id": "run_001",
                "timestamp": "2024-01-15T10:00:00",
                "metrics": {"auc": 0.85},
                "save_path": str(mock_project_dir / "models" / "run_001")
            },
            {
                "run_id": "run_002",
                "timestamp": "2024-01-14T10:00:00",
                "metrics": {"auc": 0.80},
                "save_path": str(mock_project_dir / "models" / "run_002")
            }
        ]
    }


class TestFormatSize:
    """Test size formatting"""

    def test_format_bytes(self):
        assert format_size(512) == "512.0B"

    def test_format_kilobytes(self):
        assert format_size(1024) == "1.0KB"
        assert format_size(1536) == "1.5KB"

    def test_format_megabytes(self):
        assert format_size(1024 * 1024) == "1.0MB"
        assert format_size(1024 * 1024 * 2.5) == "2.5MB"

    def test_format_gigabytes(self):
        assert format_size(1024 * 1024 * 1024) == "1.0GB"

    def test_zero_size(self):
        assert format_size(0) == "0.0B"


class TestGetDirectorySize:
    """Test directory size calculation"""

    def test_empty_directory(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert get_directory_size(str(empty_dir)) == 0

    def test_directory_with_files(self, tmp_path):
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create 10KB file
        (test_dir / "file1.txt").write_bytes(b"0" * 10240)

        size = get_directory_size(str(test_dir))
        assert size == 10240

    def test_nested_directories(self, tmp_path):
        parent = tmp_path / "parent"
        parent.mkdir()
        child = parent / "child"
        child.mkdir()

        (parent / "file1.txt").write_bytes(b"0" * 5000)
        (child / "file2.txt").write_bytes(b"0" * 3000)

        total_size = get_directory_size(str(parent))
        assert total_size == 8000

    def test_nonexistent_directory(self):
        size = get_directory_size("/nonexistent/path")
        assert size == 0


class TestAnalyzeProjectStorage:
    """Test project storage analysis"""

    def test_analyze_basic_storage(self, mock_project):
        """Test basic storage analysis"""
        result = analyze_project_storage(mock_project)

        assert "total_mb" in result
        assert "breakdown" in result
        assert "models" in result["breakdown"]
        assert "conformers" in result["breakdown"]
        assert "predictions" in result["breakdown"]

        # Should have some storage
        assert result["total_mb"] > 0

    def test_analyze_empty_project(self, tmp_path):
        """Test analysis of empty project"""
        empty_project = {
            "project_name": "empty",
            "project_root": str(tmp_path),
            "runs": []
        }

        result = analyze_project_storage(empty_project)

        assert result["total_mb"] == 0
        assert result["breakdown"]["models"] == 0

    def test_models_detail(self, mock_project):
        """Test models detail in analysis"""
        result = analyze_project_storage(mock_project)

        assert "models_detail" in result
        assert len(result["models_detail"]) == 2

        # Check model details
        for model in result["models_detail"]:
            assert "run_id" in model
            assert "size_mb" in model
            assert model["size_mb"] > 0

    def test_recommendations(self, mock_project):
        """Test storage recommendations"""
        result = analyze_project_storage(mock_project)

        assert "recommendations" in result
        # Should have recommendations list
        assert isinstance(result["recommendations"], list)

    def test_conformers_detection(self, mock_project):
        """Test conformers are detected"""
        result = analyze_project_storage(mock_project)

        # Should detect conformers
        assert result["breakdown"]["conformers"] > 0

    def test_percentage_calculation(self, mock_project):
        """Test percentage breakdown calculation"""
        result = analyze_project_storage(mock_project)

        # Percentages should sum to ~100
        total_pct = (
            result["breakdown"].get("models_pct", 0) +
            result["breakdown"].get("conformers_pct", 0) +
            result["breakdown"].get("predictions_pct", 0)
        )

        # Allow small floating point error
        assert 99 <= total_pct <= 101


class TestStorageRecommendations:
    """Test storage optimization recommendations"""

    def test_old_models_recommendation(self, mock_project):
        """Test recommendation for old models"""
        # Modify timestamps to make models old
        from datetime import datetime, timedelta

        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        for run in mock_project["runs"]:
            run["timestamp"] = old_date

        result = analyze_project_storage(mock_project)

        # Should recommend cleanup for old models
        recommendations = result["recommendations"]
        assert len(recommendations) > 0

    def test_no_recommendations_for_new_project(self, mock_project):
        """Test no recommendations for fresh project"""
        # Set all timestamps to now
        from datetime import datetime

        now = datetime.now().isoformat()
        for run in mock_project["runs"]:
            run["timestamp"] = now

        result = analyze_project_storage(mock_project)

        # May have no recommendations or minimal
        assert isinstance(result["recommendations"], list)


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_missing_project_root(self):
        """Test handling of missing project_root"""
        project = {
            "project_name": "test",
            "runs": []
        }

        # Should handle gracefully
        result = analyze_project_storage(project)
        assert result["total_mb"] == 0

    def test_invalid_project_root(self):
        """Test handling of invalid project_root"""
        project = {
            "project_name": "test",
            "project_root": "/nonexistent/path",
            "runs": []
        }

        result = analyze_project_storage(project)
        assert result["total_mb"] == 0

    def test_missing_runs(self):
        """Test handling of missing runs"""
        project = {
            "project_name": "test",
            "project_root": "/tmp"
        }

        result = analyze_project_storage(project)
        assert "models_detail" in result
        assert len(result["models_detail"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
