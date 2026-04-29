"""
End-to-End tests for Uni-Mol Tools CLI
Requires the full Uni-Mol Tools backend to be installed.
"""
import subprocess
import json
import pytest
import tempfile
import os
from pathlib import Path


def run_cli_command(args, json_output=True):
    """Run CLI command and return result."""
    cmd = ["python3", "-m", "cli_anything.unimol_tools"]
    if json_output:
        cmd.append("--json")
    cmd.extend(args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60
    )

    if json_output:
        return json.loads(result.stdout)
    return result.stdout


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file with sample data."""
    content = """SMILES,target
CCO,1
CCCO,0
CC(C)O,1
CCCCO,0
CC(C)CO,1
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def test_project():
    """Create a test project and clean up after."""
    project_name = "test_e2e_project"

    # Create project
    result = run_cli_command(["project", "create", "--name", project_name])
    assert result["status"] == "success"

    yield project_name

    # Cleanup: Delete project (if implemented)
    try:
        run_cli_command(["project", "delete", "--name", project_name])
    except:
        pass


class TestProjectManagement:
    """Test project management commands."""

    def test_create_project(self):
        """Test creating a new project."""
        result = run_cli_command(["project", "create", "--name", "test_create"])
        assert result["status"] == "success"
        assert "created" in result["message"].lower()

    def test_list_projects(self):
        """Test listing all projects."""
        result = run_cli_command(["project", "list"])
        assert result["status"] == "success"
        assert isinstance(result["data"], list)

    def test_switch_project(self, test_project):
        """Test switching to a project."""
        result = run_cli_command(["project", "switch", "--name", test_project])
        assert result["status"] == "success"


class TestModelTraining:
    """Test model training functionality."""

    @pytest.mark.slow
    def test_train_classification(self, test_project, temp_csv_file):
        """Test training a classification model."""
        result = run_cli_command([
            "train",
            "--data-path", temp_csv_file,
            "--target-col", "target",
            "--task-type", "classification",
            "--epochs", "2",  # Small for testing
            "--learning-rate", "0.0001"
        ])

        assert result["status"] == "success"
        assert "model_id" in result["data"]
        assert "performance" in result["data"]

    @pytest.mark.slow
    def test_train_regression(self, test_project, temp_csv_file):
        """Test training a regression model."""
        result = run_cli_command([
            "train",
            "--data-path", temp_csv_file,
            "--target-col", "target",
            "--task-type", "regression",
            "--epochs", "2",
            "--learning-rate", "0.0001"
        ])

        assert result["status"] == "success"
        assert "model_id" in result["data"]


class TestModelManagement:
    """Test model management commands."""

    def test_list_models(self, test_project):
        """Test listing all models."""
        result = run_cli_command(["models", "list"])
        assert result["status"] == "success"
        assert isinstance(result["data"], list)

    def test_rank_models(self, test_project):
        """Test ranking models by performance."""
        result = run_cli_command(["models", "rank"])
        assert result["status"] == "success"
        assert isinstance(result["data"], list)


class TestStorageManagement:
    """Test storage management commands."""

    def test_storage_analyze(self, test_project):
        """Test storage analysis."""
        result = run_cli_command(["storage", "analyze"])
        assert result["status"] == "success"
        assert "total_size" in result["data"]
        assert "model_count" in result["data"]


class TestPrediction:
    """Test prediction functionality."""

    @pytest.mark.slow
    def test_predict(self, test_project, temp_csv_file):
        """Test making predictions with a trained model."""
        # First train a model
        train_result = run_cli_command([
            "train",
            "--data-path", temp_csv_file,
            "--target-col", "target",
            "--task-type", "classification",
            "--epochs", "2"
        ])

        assert train_result["status"] == "success"
        model_id = train_result["data"]["model_id"]

        # Now make predictions
        pred_result = run_cli_command([
            "predict",
            "--model-id", model_id,
            "--data-path", temp_csv_file
        ])

        assert pred_result["status"] == "success"
        assert "predictions" in pred_result["data"]
        assert len(pred_result["data"]["predictions"]) > 0


class TestCleanup:
    """Test cleanup functionality."""

    def test_cleanup_auto(self, test_project):
        """Test automatic cleanup."""
        result = run_cli_command(["cleanup", "auto"])
        assert result["status"] == "success"
        assert "deleted_count" in result["data"]


class TestJSONMode:
    """Test JSON output mode for all commands."""

    def test_json_project_list(self):
        """Test JSON output for project list."""
        result = run_cli_command(["project", "list"], json_output=True)
        assert "status" in result
        assert "data" in result
        assert result["status"] in ["success", "error"]

    def test_json_models_list(self):
        """Test JSON output for models list."""
        result = run_cli_command(["models", "list"], json_output=True)
        assert "status" in result
        assert "data" in result


class TestErrorHandling:
    """Test error handling and validation."""

    def test_invalid_task_type(self, temp_csv_file):
        """Test error handling for invalid task type."""
        result = run_cli_command([
            "train",
            "--data-path", temp_csv_file,
            "--target-col", "target",
            "--task-type", "invalid_type",
            "--epochs", "2"
        ])
        assert result["status"] == "error"

    def test_missing_data_file(self):
        """Test error handling for missing data file."""
        result = run_cli_command([
            "train",
            "--data-path", "/nonexistent/file.csv",
            "--target-col", "target",
            "--task-type", "classification",
            "--epochs", "2"
        ])
        assert result["status"] == "error"

    def test_invalid_model_id(self):
        """Test error handling for invalid model ID."""
        result = run_cli_command([
            "models", "show",
            "--model-id", "nonexistent_id"
        ])
        assert result["status"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
