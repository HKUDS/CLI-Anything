"""E2E tests — requires CloudAnalyzer and Open3D installed."""

import json

import pytest

from click.testing import CliRunner

from cli_anything.cloudanalyzer.cloudanalyzer_cli import cli
from cli_anything.cloudanalyzer.utils import ca_backend


requires_cloudanalyzer = pytest.mark.skipif (
    not ca_backend.is_available(),
    reason="CloudAnalyzer (import ca) is not installed",
)


@pytest.fixture
def runner():
    return CliRunner()


class TestInfoCommands:
    def test_version_json(self, runner):
        result = runner.invoke(cli, ["--json", "info", "version"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "cloudanalyzer_version" in data
        assert "harness_version" in data

    def test_version_human(self, runner):
        result = runner.invoke(cli, ["info", "version"])
        assert result.exit_code == 0
        assert "cloudanalyzer_version" in result.output


class TestSessionCommands:
    def test_create_project(self, runner, tmp_path):
        path = str(tmp_path / "project.json")
        result = runner.invoke(cli, ["session", "new", "-o", path, "-n", "test"])
        assert result.exit_code == 0

    def test_history_requires_project(self, runner):
        result = runner.invoke(cli, ["session", "history"])
        assert result.exit_code != 0


@requires_cloudanalyzer
class TestCheckCommands:
    def test_init_creates_config(self, runner, tmp_path):
        dest = str(tmp_path / "cloudanalyzer.yaml")
        result = runner.invoke(cli, ["check", "init", dest])
        assert result.exit_code == 0
        assert (tmp_path / "cloudanalyzer.yaml").exists()

    def test_init_refuses_overwrite(self, runner, tmp_path):
        dest = tmp_path / "cloudanalyzer.yaml"
        dest.write_text("existing", encoding="utf-8")
        result = runner.invoke(cli, ["check", "init", str(dest)])
        assert result.exit_code != 0


@requires_cloudanalyzer
class TestBaselineCommands:
    def test_save_and_list(self, runner, tmp_path):
        summary = tmp_path / "summary.json"
        summary.write_text(json.dumps({
            "config_path": "test",
            "project": "test",
            "summary": {"passed": True, "failed_check_ids": []},
            "checks": [],
        }), encoding="utf-8")
        history_dir = str(tmp_path / "history")

        result = runner.invoke(cli, ["baseline", "save", str(summary), "--history-dir", history_dir])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["--json", "baseline", "list", "--history-dir", history_dir])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
