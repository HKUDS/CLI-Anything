"""Unit tests for cli-anything-eth2-quickstart."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli_anything.eth2_quickstart.core import project
from cli_anything.eth2_quickstart.core.commands import validator_plan
from cli_anything.eth2_quickstart.eth2_quickstart_cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    repo = tmp_path / "eth2-quickstart"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "eth2qs.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (repo / "config").mkdir()
    return repo


class TestProjectHelpers:
    def test_find_repo_root_from_explicit_path(self, repo_root: Path):
        resolved = project.find_repo_root(str(repo_root))
        assert resolved == repo_root

    def test_find_repo_root_from_env(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ETH2QS_REPO_ROOT", str(repo_root))
        resolved = project.find_repo_root()
        assert resolved == repo_root

    def test_upsert_user_config(self, repo_root: Path):
        config_path = project.upsert_user_config(
            repo_root,
            {
                "ETH_NETWORK": "holesky",
                "EXEC_CLIENT": "geth",
            },
        )
        content = config_path.read_text(encoding="utf-8")
        assert "export ETH_NETWORK='holesky'" in content
        assert "export EXEC_CLIENT='geth'" in content

        project.upsert_user_config(repo_root, {"ETH_NETWORK": "mainnet"})
        updated = config_path.read_text(encoding="utf-8")
        assert "export ETH_NETWORK='mainnet'" in updated
        assert "export ETH_NETWORK='holesky'" not in updated


class TestValidatorPlan:
    def test_prysm_plan(self):
        plan = validator_plan(
            consensus_client="prysm",
            fee_recipient="0xabc",
            graffiti="hello",
            wallet_password_file="~/secrets/pass.txt",
        )
        assert plan["config_updates"]["FEE_RECIPIENT"] == "0xabc"
        assert "validator accounts import" in plan["import_command"]
        assert "wallet-password-file" in plan["post_import_commands"][0]

    def test_invalid_client(self):
        with pytest.raises(ValueError, match="Unsupported consensus client"):
            validator_plan(consensus_client="bad-client")


class TestCLI:
    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "setup-node" in result.output
        assert "health-check" in result.output

    @patch("cli_anything.eth2_quickstart.eth2_quickstart_cli.Eth2QuickStartBackend")
    def test_health_check_json(self, backend_cls, runner: CliRunner, repo_root: Path):
        backend = backend_cls.return_value
        backend.repo_root = repo_root
        backend.run_wrapper.return_value = {
            "command": ["doctor", "--json"],
            "cwd": str(repo_root),
            "exit_code": 0,
            "stdout": json.dumps({"summary": {"status": "pass"}}),
            "stderr": "",
            "ok": True,
        }
        result = runner.invoke(
            cli,
            ["--repo-root", str(repo_root), "--json", "health-check"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["doctor"]["summary"]["status"] == "pass"

    @patch("cli_anything.eth2_quickstart.eth2_quickstart_cli.Eth2QuickStartBackend")
    def test_install_clients_json(self, backend_cls, runner: CliRunner, repo_root: Path):
        backend = backend_cls.return_value
        backend.repo_root = repo_root
        backend.run_wrapper.return_value = {
            "command": ["phase2"],
            "cwd": str(repo_root),
            "exit_code": 0,
            "stdout": "installed",
            "stderr": "",
            "ok": True,
        }
        result = runner.invoke(
            cli,
            [
                "--repo-root",
                str(repo_root),
                "--json",
                "install-clients",
                "--network",
                "mainnet",
                "--execution-client",
                "geth",
                "--consensus-client",
                "lighthouse",
                "--mev",
                "mev-boost",
                "--confirm",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["requested"]["execution_client"] == "geth"
        assert payload["requested"]["consensus_client"] == "lighthouse"

    @patch("cli_anything.eth2_quickstart.eth2_quickstart_cli.Eth2QuickStartBackend")
    def test_start_rpc_requires_confirm(self, backend_cls, runner: CliRunner, repo_root: Path):
        backend = backend_cls.return_value
        backend.repo_root = repo_root
        result = runner.invoke(
            cli,
            [
                "--repo-root",
                str(repo_root),
                "start-rpc",
                "--web-stack",
                "nginx",
            ],
        )
        assert result.exit_code == 1
        assert "requires --confirm" in result.output

    @patch("cli_anything.eth2_quickstart.eth2_quickstart_cli.Eth2QuickStartBackend")
    def test_configure_validator_json(self, backend_cls, runner: CliRunner, repo_root: Path):
        backend = backend_cls.return_value
        backend.repo_root = repo_root
        result = runner.invoke(
            cli,
            [
                "--repo-root",
                str(repo_root),
                "--json",
                "configure-validator",
                "--consensus-client",
                "prysm",
                "--fee-recipient",
                "0x1111111111111111111111111111111111111111",
                "--graffiti",
                "test",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["plan"]["consensus_client"] == "prysm"
        assert payload["plan"]["config_updates"]["GRAFITTI"] == "test"

    @patch("cli_anything.eth2_quickstart.eth2_quickstart_cli.Eth2QuickStartBackend")
    def test_status_json(self, backend_cls, runner: CliRunner, repo_root: Path):
        backend = backend_cls.return_value
        backend.repo_root = repo_root
        backend.run_wrapper.side_effect = [
            {
                "command": ["doctor", "--json"],
                "cwd": str(repo_root),
                "exit_code": 0,
                "stdout": json.dumps({"summary": {"status": "warn"}}),
                "stderr": "",
                "ok": True,
            },
            {
                "command": ["plan", "--json"],
                "cwd": str(repo_root),
                "exit_code": 0,
                "stdout": json.dumps({"next_action": "phase2"}),
                "stderr": "",
                "ok": True,
            },
            {
                "command": ["stats"],
                "cwd": str(repo_root),
                "exit_code": 0,
                "stdout": "service status",
                "stderr": "",
                "ok": True,
            },
        ]
        result = runner.invoke(
            cli,
            ["--repo-root", str(repo_root), "--json", "status"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["doctor"]["summary"]["status"] == "warn"
        assert payload["plan"]["next_action"] == "phase2"

