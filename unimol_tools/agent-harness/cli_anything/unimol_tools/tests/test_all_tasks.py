"""End-to-end tests for all task types"""

import pytest
import os
import json
from pathlib import Path


class TestBinaryClassification:
    """Test binary classification workflow"""

    def test_binary_classification_project(self, tmp_dir, binary_classification_data):
        """Test complete binary classification workflow"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create project
        result = project_mod.create_project(
            name="binary_test",
            task="classification",
            output_dir=tmp_dir,
            model_name="unimolv1"
        )

        assert result["status"] == "created"
        assert os.path.exists(result["project_path"])

        project_path = result["project_path"]

        # Load and verify project
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        assert project["project_type"] == "classification"
        assert project["config"]["task"] == "classification"
        assert project["config"]["metrics"] == "auc"

        # Set training dataset
        set_result = project_mod.set_dataset(
            project,
            "train",
            binary_classification_data["train"]
        )

        assert set_result["status"] == "updated"
        assert set_result["dataset_type"] == "train"

        # Save project
        project_mod.save_project(project_path, project)

        # Verify datasets are set
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]
        assert project["datasets"]["train"] is not None


class TestRegression:
    """Test regression workflow"""

    def test_regression_project(self, tmp_dir, regression_data):
        """Test complete regression workflow"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create regression project
        result = project_mod.create_project(
            name="regression_test",
            task="regression",
            output_dir=tmp_dir,
            model_name="unimolv1"
        )

        assert result["status"] == "created"
        project_path = result["project_path"]

        # Load project
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        assert project["project_type"] == "regression"
        assert project["config"]["task"] == "regression"
        assert project["config"]["metrics"] == "mae"

        # Set datasets
        set_result = project_mod.set_dataset(
            project,
            "train",
            regression_data["train"]
        )

        assert set_result["status"] == "updated"
        project_mod.save_project(project_path, project)

        # Set test dataset
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        set_result = project_mod.set_dataset(
            project,
            "test",
            regression_data["test"]
        )

        assert set_result["status"] == "updated"
        project_mod.save_project(project_path, project)

        # Verify both datasets are set
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]
        assert project["datasets"]["train"] is not None
        assert project["datasets"]["test"] is not None


class TestMulticlass:
    """Test multiclass classification"""

    def test_multiclass_project(self, tmp_dir, multiclass_data):
        """Test multiclass classification workflow"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create multiclass project
        result = project_mod.create_project(
            name="multiclass_test",
            task="classification",
            output_dir=tmp_dir,
            model_name="unimolv1"
        )

        assert result["status"] == "created"
        project_path = result["project_path"]

        # Load and verify
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        assert project["project_type"] == "classification"
        assert project["config"]["metrics"] == "auc"

        # Set dataset
        set_result = project_mod.set_dataset(
            project,
            "train",
            multiclass_data["train"]
        )

        assert set_result["status"] == "updated"
        project_mod.save_project(project_path, project)


class TestMultilabelClassification:
    """Test multilabel classification"""

    def test_multilabel_classification_project(self, tmp_dir, multilabel_classification_data):
        """Test multilabel classification workflow"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create multilabel classification project
        result = project_mod.create_project(
            name="multilabel_class_test",
            task="classification",
            output_dir=tmp_dir,
            model_name="unimolv1"
        )

        assert result["status"] == "created"
        project_path = result["project_path"]

        # Load and verify
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        assert project["project_type"] == "classification"

        # Set datasets
        set_result = project_mod.set_dataset(
            project,
            "train",
            multilabel_classification_data["train"]
        )

        assert set_result["status"] == "updated"
        project_mod.save_project(project_path, project)


class TestMultilabelRegression:
    """Test multilabel regression"""

    def test_multilabel_regression_project(self, tmp_dir, multilabel_regression_data):
        """Test multilabel regression workflow"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create multilabel regression project
        result = project_mod.create_project(
            name="multilabel_reg_test",
            task="regression",
            output_dir=tmp_dir,
            model_name="unimolv1"
        )

        assert result["status"] == "created"
        project_path = result["project_path"]

        # Load and verify
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        assert project["project_type"] == "regression"
        assert project["config"]["metrics"] == "mae"

        # Set datasets
        set_result = project_mod.set_dataset(
            project,
            "train",
            multilabel_regression_data["train"]
        )

        assert set_result["status"] == "updated"
        project_mod.save_project(project_path, project)


class TestProjectManagement:
    """Test project management operations"""

    def test_create_and_load_project(self, tmp_dir):
        """Test project creation and loading"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create project
        result = project_mod.create_project(
            name="test_project",
            task="classification",
            output_dir=tmp_dir
        )

        assert result["status"] == "created"
        assert "project_path" in result
        assert os.path.exists(result["project_path"])

        # Load project
        load_result = project_mod.load_project(result["project_path"])
        assert load_result["status"] == "loaded"
        assert "project" in load_result

        project = load_result["project"]
        assert project["metadata"]["name"] == "test_project"
        assert project["project_type"] == "classification"

    def test_get_project_info(self, tmp_dir):
        """Test getting project information"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create project
        result = project_mod.create_project(
            name="info_test",
            task="regression",
            output_dir=tmp_dir
        )

        load_result = project_mod.load_project(result["project_path"])
        project = load_result["project"]

        # Get project info
        info = project_mod.get_project_info(project)

        assert info["name"] == "info_test"
        assert info["task"] == "regression"
        assert "created" in info
        assert "modified" in info
        assert info["total_runs"] == 0
        assert info["total_predictions"] == 0

    def test_set_multiple_datasets(self, tmp_dir, binary_classification_data):
        """Test setting multiple datasets"""
        from cli_anything.unimol_tools.core import project as project_mod

        # Create project
        result = project_mod.create_project(
            name="multi_dataset_test",
            task="classification",
            output_dir=tmp_dir
        )

        project_path = result["project_path"]
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]

        # Set train dataset
        project_mod.set_dataset(project, "train", binary_classification_data["train"])
        project_mod.save_project(project_path, project)

        # Set test dataset
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]
        project_mod.set_dataset(project, "test", binary_classification_data["test"])
        project_mod.save_project(project_path, project)

        # Verify both are set
        load_result = project_mod.load_project(project_path)
        project = load_result["project"]
        assert project["datasets"]["train"] is not None
        assert project["datasets"]["test"] is not None


class TestJSONOutput:
    """Test JSON serialization"""

    def test_project_json_format(self, tmp_dir):
        """Test that project JSON is valid"""
        from cli_anything.unimol_tools.core import project as project_mod

        result = project_mod.create_project(
            name="json_test",
            task="classification",
            output_dir=tmp_dir
        )

        # Read the JSON file
        with open(result["project_path"], "r") as f:
            project_json = json.load(f)

        # Verify structure
        assert "version" in project_json
        assert "project_type" in project_json
        assert "metadata" in project_json
        assert "config" in project_json
        assert "datasets" in project_json
        assert "runs" in project_json
        assert "predictions" in project_json

        # Verify metadata
        assert "name" in project_json["metadata"]
        assert "created" in project_json["metadata"]
        assert "modified" in project_json["metadata"]

        # Verify config
        assert "task" in project_json["config"]
        assert "model_name" in project_json["config"]
        assert "epochs" in project_json["config"]
        assert "batch_size" in project_json["config"]


class TestErrorHandling:
    """Test error handling"""

    def test_invalid_task_type(self, tmp_dir):
        """Test creating project with invalid task type"""
        from cli_anything.unimol_tools.core import project as project_mod

        # This should work - no validation in create_project currently
        result = project_mod.create_project(
            name="invalid_test",
            task="invalid_task",
            output_dir=tmp_dir
        )

        assert result["status"] == "created"

    def test_load_nonexistent_project(self):
        """Test loading a non-existent project"""
        from cli_anything.unimol_tools.core import project as project_mod

        with pytest.raises(FileNotFoundError):
            project_mod.load_project("/nonexistent/path/project.json")

    def test_set_invalid_dataset_type(self, tmp_dir, binary_classification_data):
        """Test setting invalid dataset type"""
        from cli_anything.unimol_tools.core import project as project_mod

        result = project_mod.create_project(
            name="invalid_dataset_test",
            task="classification",
            output_dir=tmp_dir
        )

        load_result = project_mod.load_project(result["project_path"])
        project = load_result["project"]

        with pytest.raises(ValueError):
            project_mod.set_dataset(project, "invalid_type", binary_classification_data["train"])

    def test_set_nonexistent_dataset(self, tmp_dir):
        """Test setting a non-existent dataset file"""
        from cli_anything.unimol_tools.core import project as project_mod

        result = project_mod.create_project(
            name="nonexistent_dataset_test",
            task="classification",
            output_dir=tmp_dir
        )

        load_result = project_mod.load_project(result["project_path"])
        project = load_result["project"]

        with pytest.raises(FileNotFoundError):
            project_mod.set_dataset(project, "train", "/nonexistent/data.csv")
