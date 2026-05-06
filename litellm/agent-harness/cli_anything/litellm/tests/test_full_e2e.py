import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli_anything.litellm.litellm_cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def task_file(tmp_path):
    path = tmp_path / "task.yaml"
    path.write_text(
        "\n".join(
            [
                "name: fix-engine",
                "goal: Update engine behavior",
                "target:",
                "  include:",
                "    - engine.py",
                "verify:",
                "  command: python -m py_compile engine.py",
                "steps:",
                "  - prompt: Replace file contents with a valid update.",
            ]
        )
    )
    return path


class TestTaskAndPatchFlow:
    @patch("cli_anything.litellm.core.execution.chat_completion")
    @patch("cli_anything.litellm.core.execution.run_verify")
    def test_task_run_and_patch_show(self, mock_verify, mock_chat, runner, tmp_path, task_file):
        (tmp_path / "engine.py").write_text("print('old')\n")
        mock_chat.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "updated engine",
                                "goal_met": True,
                                "actions": [{"op": "replace", "path": "engine.py", "content": "print('new')\n"}],
                                "notes": [],
                            }
                        )
                    }
                }
            ]
        }
        mock_verify.return_value = {"status": "passed", "command": "python -m py_compile engine.py", "returncode": 0}

        result = runner.invoke(
            cli,
            [
                "--model",
                "demo-model",
                "--workspace",
                str(tmp_path),
                "task",
                "run",
                str(task_file),
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "engine.py").read_text() == "print('new')\n"

        patch_result = runner.invoke(cli, ["--workspace", str(tmp_path), "patch", "show"])
        assert patch_result.exit_code == 0
        assert "engine.py" in patch_result.output

    @patch("cli_anything.litellm.core.execution.chat_completion")
    @patch("cli_anything.litellm.core.execution.run_verify")
    def test_patch_rollback(self, mock_verify, mock_chat, runner, tmp_path, task_file):
        engine = tmp_path / "engine.py"
        engine.write_text("print('old')\n")
        mock_chat.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "updated engine",
                                "goal_met": True,
                                "actions": [{"op": "replace", "path": "engine.py", "content": "print('new')\n"}],
                            }
                        )
                    }
                }
            ]
        }
        mock_verify.return_value = {"status": "passed", "command": "python -m py_compile engine.py", "returncode": 0}

        runner.invoke(
            cli,
            ["--model", "demo-model", "--workspace", str(tmp_path), "task", "run", str(task_file)],
        )
        rollback = runner.invoke(cli, ["--workspace", str(tmp_path), "patch", "rollback"])
        assert rollback.exit_code == 0
        assert engine.read_text() == "print('old')\n"
