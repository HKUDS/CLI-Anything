"""Python backend selection, argv translation, and ownership regression tests."""

import json
import subprocess
import sys
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from cli_hub import installer, python_tools
from cli_hub.cli import main
from cli_hub.python_tools import pip_install_args, select_backend, uv_install_args


CLI = {
    "name": "demo", "display_name": "Demo", "version": "1.0.0",
    "entry_point": "demo-cli", "_source": "harness",
    "install_cmd": "pip install git+https://example.org/demo.git#subdirectory=tools/cli",
}
UV = "/tools with spaces/uv"


def result(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.fixture
def managed(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "INSTALLED_FILE", tmp_path / "installed.json")
    monkeypatch.setattr(installer, "get_cli", lambda name, **kwargs: dict(CLI))
    monkeypatch.setattr(installer, "_find_uv", lambda: UV)
    return tmp_path / "installed.json"


@pytest.mark.parametrize("requested,recorded,uv,expected", [
    ("auto", None, UV, "uv"), ("auto", None, None, "pip"),
    ("pip", None, UV, "pip"), ("uv", None, None, "uv"),
    ("auto", {"version": "1"}, UV, "pip"),
    ("auto", {}, UV, "pip"),
    ("auto", {"strategy": "pip"}, UV, "pip"),
    ("auto", {"python_backend": "pip"}, UV, "pip"),
    ("auto", {"python_backend": "uv"}, None, "uv"),
])
def test_backend_selection(requested, recorded, uv, expected):
    assert select_backend(requested, recorded, uv) == expected


@pytest.mark.parametrize("requested,recorded", [
    ("npm", None), ("uv", {"strategy": "pip"}),
    ("pip", {"python_backend": "uv"}), ("auto", {"python_backend": "bogus"}),
])
def test_invalid_or_conflicting_backend(requested, recorded):
    with pytest.raises(ValueError):
        select_backend(requested, recorded, UV)


@pytest.mark.parametrize("prefix", ["pip", "pip3", "pip3.12", "python -m pip", "python3.12 -m pip", "py.exe -m pip"])
def test_parse_pip_spellings(prefix):
    assert pip_install_args(f'{prefix} install "demo[extra]>=1"') == ["demo[extra]>=1"]


def test_preserve_quoted_paths_and_git_fragments():
    command = 'python -m pip install "file:///tmp/my wheels/demo.whl"'
    assert pip_install_args(command) == ["file:///tmp/my wheels/demo.whl"]
    assert pip_install_args(CLI["install_cmd"])[0].endswith("#subdirectory=tools/cli")
    assert pip_install_args('pip install "demo @ https://example.org/demo.whl"') == [
        "demo @ https://example.org/demo.whl",
    ]


@pytest.mark.parametrize("command", [None, "", "pip uninstall demo", "pip install", "npm install demo", "pip install demo && touch file", "pip install 'unterminated"])
def test_reject_invalid_pip_commands(command):
    with pytest.raises(ValueError):
        pip_install_args(command)


def test_translate_uv_options_without_shell_or_lost_arguments():
    args = pip_install_args('pip install --pre --upgrade --force-reinstall --no-cache-dir '
                            '--index-url=https://index.example/simple --find-links "/tmp/my wheels" '
                            '--no-build-isolation --no-index -e "/tmp/my project"')
    assert uv_install_args(args) == [
        "--prerelease", "allow", "--upgrade", "--reinstall", "--no-cache",
        "--index-url", "https://index.example/simple", "--find-links", "/tmp/my wheels",
        "--no-build-isolation", "--no-index", "--editable", "/tmp/my project",
    ]


@pytest.mark.parametrize("args", [[], ["a", "b"], ["--user", "demo"], ["-r", "deps.txt"], ["--target=/tmp", "demo"], ["--index-url"], ["--index-url=", "demo"], ["--index-url", "--upgrade", "demo"]])
def test_reject_unsupported_uv_translations(args):
    with pytest.raises(ValueError):
        uv_install_args(args)


def test_auto_uv_install_records_real_distribution_not_registry_slug(managed, monkeypatch):
    run = Mock(side_effect=[result(), result("actual-dist v1.2.3\n- demo-cli\nother v2\n- other-cli\n")])
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, message = installer.install_cli("Demo")
    assert ok, message
    assert "via uv" in message
    assert run.call_args_list[0].args[0] == [UV, "tool", "install", CLI["install_cmd"].split()[-1]]
    assert run.call_args_list[1].args[0] == [UV, "tool", "list", "--color", "never"]
    assert all(not call.kwargs.get("shell") for call in run.call_args_list)
    stored = json.loads(managed.read_text())["demo"]
    assert stored["python_backend"] == "uv"
    assert stored["python_package"] == "actual-dist"
    assert stored["version"] == "1.2.3"
    assert "python_executable" not in stored


@pytest.mark.parametrize("listing", [
    "actual-dist v1.0\n- demo-cli.exe\n",
    "other v2\n- not-demo-cli\nactual-dist v1.0+local\n- demo-cli\n- second-cli\n",
])
def test_uv_listing_accepts_exact_executables_and_windows_suffix(managed, monkeypatch, listing):
    monkeypatch.setattr(python_tools.subprocess, "run", Mock(side_effect=[result(), result(listing)]))
    assert installer.install_cli("demo")[0]
    assert json.loads(managed.read_text())["demo"]["python_package"] == "actual-dist"


@pytest.mark.parametrize("listing", ["", "other v1\n- demo-cli-other\n", "bad header\n- demo-cli\n", "one v1\n- demo-cli\ntwo v2\n- demo-cli\n"])
def test_unverified_uv_install_does_not_claim_success(managed, monkeypatch, listing):
    monkeypatch.setattr(python_tools.subprocess, "run", Mock(side_effect=[result(), result(listing)]))
    ok, message = installer.install_cli("demo")
    assert not ok
    assert "ownership verification failed" in message
    assert not managed.exists()


@pytest.mark.parametrize("backend,available", [("auto", None), ("pip", UV)])
def test_pip_fallback_and_explicit_override(managed, monkeypatch, backend, available):
    monkeypatch.setattr(installer, "_find_uv", lambda: available)
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, message = installer.install_cli("demo", backend=backend)
    assert ok, message
    assert run.call_args.args[0][:4] == [sys.executable, "-m", "pip", "install"]
    stored = json.loads(managed.read_text())["demo"]
    assert stored["python_backend"] == "pip"
    assert stored["python_executable"] == sys.executable


def test_pip_preserves_options_not_supported_by_uv(managed, monkeypatch):
    cli = {**CLI, "install_cmd": 'python -m pip install --target "/tmp/a b" demo other'}
    monkeypatch.setattr(installer, "get_cli", lambda *a, **kw: cli)
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert installer.install_cli("demo", backend="pip")[0]
    assert run.call_args.args[0][-4:] == ["--target", "/tmp/a b", "demo", "other"]


def test_uv_failure_does_not_fallback_or_change_installed_state(managed, monkeypatch):
    managed.write_text('{"other": {"version": "keep"}}')
    before = managed.read_bytes()
    run = Mock(return_value=result(stderr="resolution failed", code=1))
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, message = installer.install_cli("demo")
    assert not ok and "resolution failed" in message
    run.assert_called_once()
    assert managed.read_bytes() == before


@pytest.mark.parametrize("action", ["install", "update", "uninstall"])
def test_recorded_uv_missing_fails_without_pip_fallback(managed, monkeypatch, action):
    managed.write_text(json.dumps({"demo": {"python_backend": "uv", "python_package": "actual-dist"}}))
    before = managed.read_bytes()
    monkeypatch.setattr(installer, "_find_uv", lambda: None)
    run = Mock()
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, message = getattr(installer, f"{action}_cli")("demo")
    assert not ok and "uv is not installed" in message
    run.assert_not_called()
    assert managed.read_bytes() == before


def test_uv_update_uses_receipt_and_keeps_original_source(managed, monkeypatch):
    managed.write_text(json.dumps({"demo": {"python_backend": "uv", "python_package": "actual-dist", "install_cmd": "pip install actual-dist==1.0"}}))
    run = Mock(side_effect=[result(), result("actual-dist v1.0\n- demo-cli\n")])
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert installer.update_cli("demo")[0]
    assert run.call_args_list[0].args[0] == [UV, "tool", "upgrade", "--reinstall", "actual-dist"]
    assert json.loads(managed.read_text())["demo"]["install_cmd"] == "pip install actual-dist==1.0"
    assert json.loads(managed.read_text())["demo"]["version"] == "1.0"


def test_uv_uninstall_uses_recorded_name_and_preserves_other_entries(managed, monkeypatch):
    managed.write_text(json.dumps({"demo": {"python_backend": "uv", "python_package": "actual-dist"}, "other": {"version": "keep"}}))
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert installer.uninstall_cli("demo")[0]
    assert run.call_args.args[0] == [UV, "tool", "uninstall", "actual-dist"]
    assert json.loads(managed.read_text()) == {"other": {"version": "keep"}}


@pytest.mark.parametrize("action", ["install", "update", "uninstall"])
def test_pip_ownership_does_not_migrate_when_uv_appears(managed, monkeypatch, action):
    managed.write_text(json.dumps({"demo": {"python_backend": "pip", "python_package": "actual-dist", "python_executable": "/old venv/bin/python"}}))
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert getattr(installer, f"{action}_cli")("demo")[0]
    assert run.call_args.args[0][:3] == ["/old venv/bin/python", "-m", "pip"]


def test_legacy_pip_record_stays_pip(managed, monkeypatch):
    managed.write_text(json.dumps({"demo": {"version": "1", "strategy": "pip"}}))
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert installer.update_cli("demo")[0]
    assert run.call_args.args[0][1:4] == ["-m", "pip", "install"]


@pytest.mark.parametrize("action", ["update", "uninstall"])
def test_untracked_legacy_actions_default_to_pip(managed, monkeypatch, action):
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert getattr(installer, f"{action}_cli")("demo")[0]
    assert run.call_args.args[0][1:3] == ["-m", "pip"]


def test_explicit_uv_removal_discovers_untracked_distribution(managed, monkeypatch):
    run = Mock(side_effect=[result("actual-dist v1\n- demo-cli\n"), result()])
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert installer.uninstall_cli("demo", backend="uv")[0]
    assert run.call_args.args[0] == [UV, "tool", "uninstall", "actual-dist"]


def test_conflicting_backend_does_not_execute_or_modify_state(managed, monkeypatch):
    managed.write_text('{"demo": {"python_backend": "pip"}}')
    before = managed.read_bytes()
    run = Mock()
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, message = installer.install_cli("demo", backend="uv")
    assert not ok and "Uninstall it before switching" in message
    run.assert_not_called()
    assert managed.read_bytes() == before


def test_failed_uninstall_preserves_state(managed, monkeypatch):
    managed.write_text('{"demo": {"python_backend": "uv", "python_package": "actual-dist"}}')
    before = managed.read_bytes()
    monkeypatch.setattr(python_tools.subprocess, "run", Mock(return_value=result(code=1, stderr="busy")))
    assert not installer.uninstall_cli("demo")[0]
    assert managed.read_bytes() == before


def test_missing_pip_interpreter_does_not_claim_success(managed, monkeypatch):
    monkeypatch.setattr(python_tools.subprocess, "run", Mock(side_effect=FileNotFoundError("old python is missing")))
    ok, message = installer.install_cli("demo", backend="pip")
    assert not ok and "old python is missing" in message
    assert not managed.exists()


def test_non_python_backend_override_rejected(managed, monkeypatch):
    monkeypatch.setattr(installer, "get_cli", lambda *a, **kw: {**CLI, "install_strategy": "npm"})
    run = Mock()
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert not installer.install_cli("demo", backend="uv")[0]
    run.assert_not_called()


@pytest.fixture
def cli_runner(monkeypatch):
    monkeypatch.setenv("CLI_HUB_NO_ANALYTICS", "1")
    monkeypatch.setattr("cli_hub.cli.track_first_run", lambda: None)
    monkeypatch.setattr("cli_hub.cli.track_visit", lambda **kwargs: None)
    return CliRunner()


def test_cli_json_success_and_backend_metadata(managed, monkeypatch, cli_runner):
    monkeypatch.setattr(python_tools.subprocess, "run", Mock(side_effect=[result(), result("actual-dist v1\n- demo-cli\n")]))
    response = cli_runner.invoke(main, ["install", "demo", "--backend", "uv", "--json"])
    assert response.exit_code == 0, response.output
    payload = json.loads(response.output)
    assert payload["success"] is True
    assert payload["installation"]["python_backend"] == "uv"
    assert payload["installation"]["python_package"] == "actual-dist"
    assert "install_cmd" not in payload["installation"]


@pytest.mark.parametrize("action", ["install", "update", "uninstall"])
def test_cli_json_failure_and_exit_status(managed, monkeypatch, cli_runner, action):
    monkeypatch.setattr(python_tools.subprocess, "run", Mock(return_value=result(stderr="backend error", code=1)))
    response = cli_runner.invoke(main, [action, "demo", "--backend=pip", "--json"])
    assert response.exit_code == 1
    payload = json.loads(response.output)
    assert payload["success"] is False and "backend error" in payload["message"]


def test_cli_rejects_invalid_backend_before_install(managed, monkeypatch, cli_runner):
    run = Mock()
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    assert cli_runner.invoke(main, ["install", "demo", "--backend=npm"]).exit_code == 2
    run.assert_not_called()


def test_cli_registry_failure_remains_json(managed, monkeypatch, cli_runner):
    monkeypatch.setattr(installer, "get_cli", Mock(side_effect=OSError("registry unavailable")))
    response = cli_runner.invoke(main, ["install", "demo", "--json"])
    assert response.exit_code == 1
    assert json.loads(response.output)["message"] == "registry unavailable"


@pytest.mark.parametrize("contents", ["broken json", "[]", '{"demo": "broken"}'])
def test_corrupt_state_cannot_switch_backend_or_be_overwritten(managed, monkeypatch, cli_runner, contents):
    managed.write_text(contents)
    run = Mock()
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    response = cli_runner.invoke(main, ["install", "demo", "--json"])
    assert response.exit_code == 1
    assert "installed.json" in json.loads(response.output)["message"]
    assert managed.read_text() == contents
    run.assert_not_called()


def test_matrix_dry_run_selects_actual_backend_without_install(managed, monkeypatch, cli_runner):
    monkeypatch.setattr(installer, "get_matrix", lambda name: {"name": "demo-matrix", "clis": ["demo"]})
    run = Mock()
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    for backend in ["pip", "uv"]:
        response = cli_runner.invoke(main, ["matrix", "install", "demo-matrix", "--dry-run", "--backend", backend, "--json"])
        assert response.exit_code == 0, response.output
        assert json.loads(response.output)["plan"][0]["via"] == backend
    run.assert_not_called()
    assert not managed.exists()


def test_matrix_install_uses_override_and_records_backend(managed, monkeypatch):
    monkeypatch.setattr(installer, "MATRIX_STATE_FILE", managed.parent / "matrix-state.json")
    monkeypatch.setattr(installer, "get_matrix", lambda name: {"name": "demo-matrix", "clis": ["demo"]})
    monkeypatch.setattr(installer, "render_matrix_skill_file", lambda *a, **kw: managed.parent / "SKILL.md")
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, payload = installer.install_matrix("demo-matrix", backend="pip")
    assert ok, payload
    assert payload["results"][0]["via"] == "pip"
    assert json.loads(managed.read_text())["demo"]["python_backend"] == "pip"


def test_matrix_resume_retains_explicit_backend(managed, monkeypatch):
    state = managed.parent / "matrix-state.json"
    state.write_text(json.dumps({"demo-matrix": {
        "python_backend": "pip", "scope": {"type": "all"},
        "results": [{"name": "demo", "status": "failed"}],
    }}))
    monkeypatch.setattr(installer, "MATRIX_STATE_FILE", state)
    monkeypatch.setattr(installer, "get_matrix", lambda name: {"name": name, "clis": ["demo"]})
    monkeypatch.setattr(installer, "render_matrix_skill_file", lambda *a, **kw: managed.parent / "SKILL.md")
    run = Mock(return_value=result())
    monkeypatch.setattr(python_tools.subprocess, "run", run)
    ok, payload = installer.install_matrix("demo-matrix", resume=True)
    assert ok, payload
    assert payload["results"][0]["via"] == "pip"
    assert run.call_args.args[0][1:4] == ["-m", "pip", "install"]
    assert json.loads(state.read_text())["demo-matrix"]["python_backend"] == "pip"


def test_matrix_dry_run_hint_preserves_backend(managed, monkeypatch, cli_runner):
    monkeypatch.setattr(installer, "get_matrix", lambda name: {"name": name, "clis": ["demo"]})
    response = cli_runner.invoke(main, ["matrix", "install", "demo-matrix", "--dry-run", "--backend=pip"])
    assert response.exit_code == 0, response.output
    assert "Run: cli-hub matrix install demo-matrix --backend pip" in response.output
