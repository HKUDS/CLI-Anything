"""Unit tests for project and session management (no CloudAnalyzer needed)."""

import json
import os

import pytest

from cli_anything.cloudanalyzer.core.project import (
    create_project,
    load_project,
    save_project,
    project_info,
    record_operation,
    add_result,
)
from cli_anything.cloudanalyzer.core.session import Session


class TestProject:
    def test_create_and_load(self, tmp_path):
        path = str(tmp_path / "project.json")
        project = create_project(path, name="test-project")

        assert project["name"] == "test-project"
        assert project["version"] == "1.0"
        assert os.path.isfile(path)

        loaded = load_project(path)
        assert loaded["name"] == "test-project"

    def test_record_operation(self, tmp_path):
        path = str(tmp_path / "project.json")
        project = create_project(path)
        record_operation(project, "evaluate", {"source": "a.pcd"})

        assert len(project["history"]) == 1
        assert project["history"][0]["operation"] == "evaluate"

    def test_add_result(self, tmp_path):
        path = str(tmp_path / "project.json")
        project = create_project(path)
        add_result(project, "evaluation", {"auc": 0.95})

        assert len(project["results"]) == 1
        assert project["results"][0]["data"]["auc"] == 0.95

    def test_project_info(self, tmp_path):
        path = str(tmp_path / "project.json")
        project = create_project(path, name="info-test")
        info = project_info(project)

        assert info["name"] == "info-test"
        assert info["clouds"] == 0
        assert info["operations"] == 0

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_project(str(tmp_path / "nope.json"))


class TestSession:
    def test_undo_redo(self, tmp_path):
        path = str(tmp_path / "project.json")
        create_project(path, name="undo-test")
        sess = Session(path)

        sess.do("first-op", {"detail": "a"})
        sess.do("second-op", {"detail": "b"})
        assert len(sess.history) == 2

        assert sess.undo()
        assert len(sess.history) == 1

        assert sess.redo()
        assert len(sess.history) == 2

    def test_undo_empty_returns_false(self, tmp_path):
        path = str(tmp_path / "project.json")
        create_project(path)
        sess = Session(path)

        assert not sess.undo()
        assert not sess.redo()
