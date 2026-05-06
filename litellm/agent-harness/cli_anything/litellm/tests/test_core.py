import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.litellm.core.execution import execute_task
from cli_anything.litellm.core.patches import build_patch, ensure_workspace_path, rollback_patch
from cli_anything.litellm.core.session import SessionStore
from cli_anything.litellm.core.taskdefs import load_task, validate_definition
from cli_anything.litellm.litellm_cli import cli
from cli_anything.litellm.utils.litellm_backend import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    bootstrap_workspace,
    chat_completion,
    list_models,
    resolve_host,
    resolve_model,
)


@pytest.fixture
def runner():
    return CliRunner()


class TestConfig:
    def test_default_host(self):
        assert resolve_host(None) == DEFAULT_HOST

    def test_default_host_is_user_proxy(self):
        assert DEFAULT_HOST == "https://litellm.nuriy.com/v1"

    def test_default_model_is_user_preference(self):
        assert DEFAULT_MODEL == "gpt-5.4"
        assert resolve_model(None) == "gpt-5.4"

    def test_session_store_roundtrip(self, tmp_path):
        store = SessionStore(tmp_path / "session.json")
        store.record("task run", {"task_file": "x.yaml"}, {"status": "completed"})
        assert store.status()["history_count"] == 1

    def test_bootstrap_workspace(self, tmp_path):
        result = bootstrap_workspace(tmp_path, host=DEFAULT_HOST, model=DEFAULT_MODEL)
        assert Path(result["config"]).exists()
        assert Path(result["ignore"]).exists()
        assert Path(result["tasks_dir"]).exists()

    @patch("cli_anything.litellm.utils.litellm_backend.requests.get")
    def test_list_models_uses_single_v1_prefix(self, mock_get):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": []}
        mock_get.return_value = response
        list_models("https://litellm.nuriy.com/v1")
        assert mock_get.call_args[0][0] == "https://litellm.nuriy.com/v1/models"

    @patch("cli_anything.litellm.utils.litellm_backend.requests.post")
    def test_chat_completion_uses_single_v1_prefix(self, mock_post):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
        mock_post.return_value = response
        chat_completion(
            "https://litellm.nuriy.com/v1",
            api_key=None,
            model="gpt-5.4",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert mock_post.call_args[0][0] == "https://litellm.nuriy.com/v1/chat/completions"


class TestTaskDefs:
    def test_load_task(self, tmp_path):
        path = tmp_path / "task.yaml"
        path.write_text("name: demo\ngoal: fix the app\n")
        task = load_task(path)
        assert task["name"] == "demo"
        assert task["max_iterations"] == 3
        assert task["defaults"]["loop_mode"] == "auto_loop"
        assert task["patch_policy"]["auto_apply"] is True

    def test_validate_definition(self, tmp_path):
        path = tmp_path / "flow.yaml"
        path.write_text("name: demo\nsteps:\n  - prompt: fix it\n")
        result = validate_definition(path)
        assert result["valid"] is True


class TestPatches:
    def test_workspace_escape_blocked(self, tmp_path):
        with pytest.raises(RuntimeError, match="escapes workspace"):
            ensure_workspace_path(tmp_path, "../outside.txt")

    def test_build_and_rollback(self, tmp_path):
        file_path = tmp_path / "app.py"
        file_path.write_text("print('old')\n")
        actions = [{"op": "replace", "path": "app.py", "content": "print('new')\n"}]
        patch = build_patch(actions, tmp_path)
        assert "app.py" in patch["diff"]
        file_path.write_text("print('new')\n")
        restored = rollback_patch(patch, tmp_path)
        assert restored == ["app.py"]
        assert file_path.read_text() == "print('old')\n"


class TestExecution:
    @patch("cli_anything.litellm.core.execution.chat_completion")
    @patch("cli_anything.litellm.core.execution.run_verify")
    def test_execute_task(self, mock_verify, mock_chat, tmp_path):
        target = tmp_path / "engine.py"
        target.write_text("print('old')\n")
        mock_chat.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "updated file",
                                "goal_met": True,
                                "actions": [{"op": "replace", "path": "engine.py", "content": "print('new')\n"}],
                            }
                        )
                    }
                }
            ]
        }
        mock_verify.return_value = {"status": "passed", "command": "pytest", "returncode": 0}
        task = {
            "name": "demo",
            "goal": "update file",
            "target": {"include": ["engine.py"]},
            "steps": [{"prompt": "patch engine.py"}],
            "success_criteria": [],
            "max_iterations": 2,
            "patch_policy": {"auto_apply": True},
            "verify": {"command": "pytest"},
        }
        result = execute_task(task, workspace=tmp_path, host="http://localhost:4000", api_key=None, model="demo")
        assert result["status"] == "completed"
        assert target.read_text() == "print('new')\n"

    @patch("cli_anything.litellm.core.execution.chat_completion")
    @patch("cli_anything.litellm.core.execution.run_verify")
    def test_execute_task_uses_default_verify(self, mock_verify, mock_chat, tmp_path):
        target = tmp_path / "engine.py"
        target.write_text("print('old')\n")
        mock_chat.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "updated file",
                                "goal_met": True,
                                "actions": [{"op": "replace", "path": "engine.py", "content": "print('new')\n"}],
                            }
                        )
                    }
                }
            ]
        }
        mock_verify.return_value = {"status": "passed", "command": "python -m py_compile engine.py", "returncode": 0}
        task = {
            "name": "demo",
            "goal": "update file",
            "target": {"include": ["engine.py"]},
            "steps": [{"prompt": "patch engine.py"}],
            "patch_policy": {"auto_apply": True},
        }
        result = execute_task(task, workspace=tmp_path, host="http://localhost:4000", api_key=None, model="demo")
        assert result["status"] == "completed"
        assert mock_verify.call_args[0][0] == "python -m py_compile engine.py"


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "task" in result.output
        assert "flow" in result.output

    def test_config_bootstrap(self, runner, tmp_path):
        result = runner.invoke(cli, ["--workspace", str(tmp_path), "config", "bootstrap"])
        assert result.exit_code == 0
        assert (tmp_path / ".litellm" / "config.json").exists()

    @patch("cli_anything.litellm.utils.litellm_backend.api_get")
    def test_health_json(self, mock_get, runner):
        mock_get.return_value = {"status": "ok"}
        result = runner.invoke(cli, ["--json", "health"])
        assert result.exit_code == 0
        assert json.loads(result.output)["status"] == "ok"

    @patch("cli_anything.litellm.litellm_cli.ask_model")
    def test_ask_command(self, mock_ask, runner, tmp_path):
        mock_ask.return_value = {"content": "Check Activity Monitor.", "model": "gpt-5.4", "workspace": str(tmp_path)}
        result = runner.invoke(cli, ["--workspace", str(tmp_path), "ask", "review", "my", "battery"])
        assert result.exit_code == 0
        assert "Check Activity Monitor." in result.output

    @patch("cli_anything.litellm.litellm_cli.ask_model")
    def test_repl_plain_language_routes_to_ask(self, mock_ask, runner, tmp_path):
        mock_ask.return_value = {"content": "Top consumers are likely browser tabs.", "model": "gpt-5.4", "workspace": str(tmp_path)}
        result = runner.invoke(cli, ["--workspace", str(tmp_path)], input="review my battery usage\nquit\n")
        assert result.exit_code == 0
        assert "Top consumers are likely browser tabs." in result.output
