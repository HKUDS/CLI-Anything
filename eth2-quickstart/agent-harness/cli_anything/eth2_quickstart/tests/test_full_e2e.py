"""E2E tests for cli-anything-eth2-quickstart."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.eth2_quickstart.eth2_quickstart_cli import cli

E2E_REPO_ROOT = os.environ.get("ETH2QS_E2E_REPO_ROOT")
WRAPPER_EXISTS = bool(E2E_REPO_ROOT) and (Path(E2E_REPO_ROOT) / "scripts" / "eth2qs.sh").is_file()

pytestmark = pytest.mark.skipif(
    not WRAPPER_EXISTS,
    reason="Set ETH2QS_E2E_REPO_ROOT to a real eth2-quickstart checkout to run E2E tests",
)


@pytest.fixture
def runner():
    return CliRunner()


class TestRealCheckoutE2E:
    def test_help(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            ["--repo-root", E2E_REPO_ROOT, "--help"],
        )
        assert result.exit_code == 0

    def test_health_check_json(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            ["--repo-root", E2E_REPO_ROOT, "--json", "health-check"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "command_result" in payload
        assert payload["command_result"]["command"][-2:] == ["doctor", "--json"]

    def test_status_json(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            ["--repo-root", E2E_REPO_ROOT, "--json", "status"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "plan" in payload
        assert "stats_raw" in payload

