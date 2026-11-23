"""Unit tests for cli-anything-ghidra. No Ghidra, no Java and no real binary needed."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.ghidra.core import analysis, queries
from cli_anything.ghidra.ghidra_cli import cli
from cli_anything.ghidra.utils import ghidra_backend as backend
from cli_anything.ghidra.utils.ghidra_backend import (
    GhidraBackend, check, file_key, find_analyze_headless, work_home,
    _ADDRESS, _LOADER, _PROCESSOR, _TARGET,
)

LAUNCHER_NAME = "analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless"


@pytest.fixture
def install(tmp_path, monkeypatch):
    support = tmp_path / "ghidra" / "support"
    support.mkdir(parents=True)
    (support / LAUNCHER_NAME).write_text("")
    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(tmp_path / "ghidra"))
    monkeypatch.delenv("GHIDRA_JAVA_HOME", raising=False)
    return tmp_path / "ghidra"


@pytest.fixture
def be(install, tmp_path):
    return GhidraBackend(home=tmp_path / "work")


@pytest.fixture
def sample(tmp_path):
    p = tmp_path / "sample.bin"
    p.write_bytes(bytes.fromhex("b82a000000c3"))
    return p


class FakeProc:
    """subprocess.Popen stand-in: writes the post-script's JSON output when communicate() is called."""

    def __init__(self, cmd, kwargs, payload, stdout, returncode, hang):
        self.cmd, self.kwargs, self.payload, self.stdout = cmd, kwargs, payload, stdout
        self.returncode, self.hang, self.pid, self.timed_out = returncode, hang, 4242, False

    def communicate(self, timeout=None):
        if timeout is not None:
            self.kwargs["timeout"] = timeout
        if self.hang and not self.timed_out:
            self.timed_out = True
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        if self.payload is not None:
            i = self.cmd.index("-postScript")
            Path(self.cmd[i + 3]).write_text(
                self.payload if isinstance(self.payload, str) else json.dumps(self.payload), encoding="utf-8")
        return self.stdout, ""


def fake_popen(payload, calls, stdout="", returncode=0, hang=False):
    """Popen factory that records every launch in `calls` and keeps the created procs in `.procs`."""
    def popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        proc = FakeProc(cmd, kwargs, payload, stdout, returncode, hang)
        popen.procs.append(proc)
        return proc
    popen.procs = []
    return popen


# --- locating Ghidra ------------------------------------------------------

def test_find_launcher_from_env(install):
    assert find_analyze_headless().name == LAUNCHER_NAME


def test_missing_install_dir_explains_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(tmp_path / "nope"))
    with pytest.raises(RuntimeError, match="GHIDRA_INSTALL_DIR"):
        find_analyze_headless()


def test_no_env_and_not_on_path(monkeypatch):
    monkeypatch.delenv("GHIDRA_INSTALL_DIR", raising=False)
    with patch.object(backend.shutil, "which", return_value=None):
        with pytest.raises(RuntimeError, match="JDK 25"):
            find_analyze_headless()


def test_work_home_rejects_dot_folders(monkeypatch, tmp_path):
    monkeypatch.setenv("CLI_ANYTHING_GHIDRA_HOME", str(tmp_path / ".hidden" / "x"))
    with pytest.raises(RuntimeError, match="starting with '.'"):
        work_home()


def test_work_home_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CLI_ANYTHING_GHIDRA_HOME", str(tmp_path / "w"))
    assert work_home() == (tmp_path / "w").resolve()


# --- allowlists (BatBadBut / option injection) ----------------------------

@pytest.mark.parametrize("bad", [
    "a&b", "a|b", "a%PATH%", "a^b", 'a"b', "a<b", "a>b", "a;b", "a b", "", "-flag", "a\nb", "a(b)", "a!b", "a`b",
])
def test_target_rejects_shell_metacharacters(bad):
    with pytest.raises(RuntimeError, match="not allowed"):
        check(bad, _TARGET, "target")


@pytest.mark.parametrize("good", ["main", "FUN_00401000", "0x401000", "?foo@@YAXXZ", "_ZN3foo3barEv", "sub_401000.1"])
def test_target_accepts_symbols_and_addresses(good):
    assert check(good, _TARGET, "target") == good


@pytest.mark.parametrize("value,pattern", [
    ("BinaryLoader&x", _LOADER), ("Binary Loader", _LOADER),
    ("x86:LE:64:default&id", _PROCESSOR), ("x86", _PROCESSOR), ("x86:XX:64:default", _PROCESSOR),
    ("0xZZ", _ADDRESS), ("1" * 17, _ADDRESS), ("0x", _ADDRESS),
])
def test_other_allowlists_reject(value, pattern):
    with pytest.raises(RuntimeError, match="not allowed"):
        check(value, pattern, "value")


@pytest.mark.parametrize("value,pattern", [
    ("BinaryLoader", _LOADER), ("x86:LE:64:default", _PROCESSOR), ("ARM:LE:32:v8", _PROCESSOR),
    ("0x401000", _ADDRESS), ("0", _ADDRESS),
])
def test_other_allowlists_accept(value, pattern):
    assert check(value, pattern, "value") == value


# --- file key -------------------------------------------------------------

def test_file_key_is_content_based(tmp_path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    a.write_bytes(b"same"); b.write_bytes(b"same"); c.write_bytes(b"diff")
    assert file_key(a) == file_key(b) != file_key(c)
    assert len(file_key(a)) == 16


# --- analyze --------------------------------------------------------------

def test_analyze_builds_safe_command_and_cleans_up(be, tmp_path):
    evil = tmp_path / "evil&calc.bin"
    evil.write_bytes(bytes.fromhex("b82a000000c3"))
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({"functions": 1}, calls)):
        result = be.analyze(str(evil), loader="BinaryLoader", processor="x86:LE:64:default", entry="0", timeout=50)
    cmd, kwargs = calls[0]
    key = file_key(evil)
    assert result["key"] == key and result["functions"] == 1
    assert cmd[0].endswith(LAUNCHER_NAME) and cmd[1] == str(be.projects) and cmd[2] == key
    assert "-import" in cmd and cmd[cmd.index("-import") + 1].endswith(f"{key}.bin")
    assert "-loader" in cmd and "-processor" in cmd and cmd[-1] == "0"
    assert all("evil" not in part for part in cmd)  # the original filename never reaches the command line
    assert not kwargs.get("shell") and kwargs["stdin"] == subprocess.DEVNULL and kwargs["timeout"] == 170
    assert not any((be.home / "inputs").iterdir())  # private staging folder removed


def test_analyze_never_executes_target(be, sample):
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({}, calls)):
        be.analyze(str(sample))
    assert all(str(sample) not in part for part in calls[0][0])


@pytest.mark.parametrize("kwargs", [
    {"loader": "BinaryLoader&x"}, {"processor": "x86:LE:64:default|id"}, {"entry": "0x1;2"},
])
def test_analyze_rejects_bad_options_before_running(be, sample, kwargs):
    with patch.object(backend.subprocess, "Popen") as run:
        with pytest.raises(RuntimeError, match="not allowed"):
            be.analyze(str(sample), **kwargs)
    run.assert_not_called()


def test_analyze_missing_binary(be):
    with pytest.raises(RuntimeError, match="Binary not found"):
        be.analyze("/no/such/file")


# --- query ----------------------------------------------------------------

def analyzed(be, sample):
    be.projects.mkdir(parents=True, exist_ok=True)
    (be.projects / f"{file_key(sample)}.gpr").write_text("")


def test_query_requires_analysis(be, sample):
    with pytest.raises(RuntimeError, match="not been analyzed"):
        be.query(str(sample), "functions")


def test_query_command_is_read_only_and_no_reanalysis(be, sample):
    analyzed(be, sample)
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen([{"name": "f"}], calls)):
        assert be.query(str(sample), "decompile", "main") == [{"name": "f"}]
    cmd = calls[0][0]
    for flag in ("-noanalysis", "-readOnly"):
        assert flag in cmd
    assert cmd[cmd.index("-process") + 1] == f"{file_key(sample)}.bin"
    assert cmd[-1] == "main" and cmd[cmd.index("-postScript") + 2] == "decompile"
    assert not calls[0][1].get("shell")


def test_query_rejects_bad_target_before_running(be, sample):
    analyzed(be, sample)
    with patch.object(backend.subprocess, "Popen") as run:
        with pytest.raises(RuntimeError, match="not allowed"):
            be.query(str(sample), "xrefs", "x&calc")
    run.assert_not_called()


def test_java_hint_in_failure(be, sample):
    analyzed(be, sample)
    fake = fake_popen(None, [], stdout="JDK 25+ (64-bit) could not be found and must be manually chosen!", returncode=1)
    with patch.object(backend.subprocess, "Popen", side_effect=fake):
        with pytest.raises(RuntimeError, match="GHIDRA_JAVA_HOME"):
            be.query(str(sample), "info")


def test_script_error_surfaces_message(be, sample):
    analyzed(be, sample)
    fake = fake_popen(None, [], stdout="INFO x\nERROR REPORT SCRIPT ERROR: no function named or containing zz")
    with patch.object(backend.subprocess, "Popen", side_effect=fake):
        with pytest.raises(RuntimeError, match="no function named"):
            be.query(str(sample), "decompile", "zz")


def test_timeout_is_reported_and_kills_the_process_tree(be, sample):
    analyzed(be, sample)
    fake = fake_popen(None, [], hang=True)
    with patch.object(backend.subprocess, "Popen", side_effect=fake), patch.object(backend, "_kill_tree") as kill:
        with pytest.raises(RuntimeError, match="timed out"):
            be.query(str(sample), "info", timeout=1)
    kill.assert_called_once_with(fake.procs[0])


def test_unreadable_result_file_is_a_clean_error(be, sample):
    analyzed(be, sample)
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen("{not json", [])):
        with pytest.raises(RuntimeError, match="unreadable result file"):
            be.query(str(sample), "info")


def test_launcher_gets_its_own_process_group(be, sample):
    analyzed(be, sample)
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({}, calls)):
        be.query(str(sample), "info")
    kwargs = calls[0][1]
    assert kwargs.get("start_new_session") is True or "creationflags" in kwargs


def _alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True).stdout  # bytes: output is localized
        return str(pid).encode() in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_kill_tree_really_stops_grandchildren():
    """Real processes: killing only the parent would leave the grandchild (java behind the .bat) running."""
    code = ("import subprocess, sys, time\n"
            "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(c.pid, flush=True)\n"
            "time.sleep(60)\n")
    parent = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, **backend.popen_kwargs())
    child = int(parent.stdout.readline())
    try:
        assert _alive(child)
        backend._kill_tree(parent)
        parent.wait(timeout=20)
        for _ in range(50):
            if not _alive(child):
                break
            time.sleep(0.2)
        assert not _alive(child)
    finally:
        parent.kill()
        parent.stdout.close()
        subprocess.run(["taskkill", "/F", "/PID", str(child)], capture_output=True) if os.name == "nt" else None


@pytest.mark.parametrize("bad", list("&|<>^%!") + ['"', chr(10), chr(13)])
def test_check_path_rejects_cmd_metacharacters(bad):
    with pytest.raises(RuntimeError, match="cmd.exe interprets"):
        backend.check_path("C:/work" + bad + "x", "work folder")


@pytest.mark.parametrize("bad", list("&%^!"))  # the characters that are legal in Windows folder names
def test_unsafe_work_folder_is_refused_before_launch(install, tmp_path, sample, bad):
    be = GhidraBackend(home=tmp_path / "home")
    be.projects = tmp_path / f"work{bad}x"
    be.projects.mkdir(parents=True)
    (be.projects / f"{file_key(sample)}.gpr").write_text("")
    with patch.object(backend.subprocess, "Popen") as popen:
        with pytest.raises(RuntimeError, match="cmd.exe interprets"):
            be.query(str(sample), "info")
    popen.assert_not_called()


def test_parentheses_and_spaces_in_paths_are_fine(be, sample, tmp_path):
    odd = tmp_path / "Program Files (x86)" / "work"
    odd.mkdir(parents=True)
    be.projects = odd
    (odd / f"{file_key(sample)}.gpr").write_text("")
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({}, [])):
        assert be.query(str(sample), "info") == {}


def test_stage_hashes_the_copy_and_uses_a_private_folder(be, sample):
    key1, staged1, folder1 = be._stage(str(sample))
    key2, staged2, folder2 = be._stage(str(sample))
    try:
        assert key1 == key2 == file_key(staged1) and staged1.name == f"{key1}.bin"
        assert folder1 != folder2 and staged1.exists() and staged2.exists()
        assert not folder1.name.startswith(".")
    finally:
        shutil.rmtree(folder1, ignore_errors=True)
        shutil.rmtree(folder2, ignore_errors=True)


def test_java_home_override_only_in_child_env(be, sample, monkeypatch):
    analyzed(be, sample)
    monkeypatch.setenv("GHIDRA_JAVA_HOME", "/jdk25")
    monkeypatch.setenv("JAVA_HOME", "/jdk21")
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({}, calls)):
        be.query(str(sample), "info")
    assert calls[0][1]["env"]["JAVA_HOME"] == "/jdk25"
    assert os.environ["JAVA_HOME"] == "/jdk21"


# --- core -----------------------------------------------------------------

def fake_backend(data):
    b = MagicMock()
    b.query.return_value = data
    return b


def test_functions_filter_and_limit():
    data = [{"name": "main"}, {"name": "Main2"}, {"name": "helper"}]
    assert [f["name"] for f in queries.list_functions(fake_backend(data), "x", "main")] == ["main", "Main2"]
    assert len(queries.list_functions(fake_backend(data), "x", limit=1)) == 1


def test_strings_min_length_and_limit():
    data = [{"length": 3, "value": "ab"}, {"length": 8, "value": "abcdefg"}, {"length": 9, "value": "abcdefgh"}]
    assert [s["length"] for s in queries.list_strings(fake_backend(data), "x", 4)] == [8, 9]
    assert len(queries.list_strings(fake_backend(data), "x", 4, limit=1)) == 1


def test_info_calls_query():
    b = fake_backend({"functions": 1})
    assert analysis.info(b, "x") == {"functions": 1}
    b.query.assert_called_with("x", "info")


# --- CLI ------------------------------------------------------------------

def run_cli(args, data):
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value = fake_backend(data)
        cls.return_value.analyze.return_value = data
        return CliRunner().invoke(cli, args, obj={})


def test_cli_functions_json():
    res = run_cli(["--json", "functions", "x.bin"], [{"name": "main", "address": "0", "size": 6}])
    assert json.loads(res.output)[0]["name"] == "main"


def test_cli_decompile_prints_c_or_json():
    data = {"name": "f", "address": "0", "c": "\nint f(void)\n{\n  return 42;\n}\n"}
    assert "return 42;" in run_cli(["decompile", "x.bin", "f"], data).output
    assert json.loads(run_cli(["--json", "decompile", "x.bin", "f"], data).output)["name"] == "f"


def test_cli_analyze_passes_options():
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value.analyze.return_value = {"key": "k"}
        res = CliRunner().invoke(cli, ["--json", "analyze", "x.bin", "--loader", "BinaryLoader",
                                       "--processor", "x86:LE:64:default", "--entry", "0", "--timeout", "30"], obj={})
    assert res.exit_code == 0
    cls.return_value.analyze.assert_called_once_with("x.bin", "BinaryLoader", "x86:LE:64:default", "0", 30)


def test_cli_timeout_bounds():
    assert run_cli(["analyze", "x.bin", "--timeout", "1"], {}).exit_code == 2


def test_cli_help_lists_commands():
    out = CliRunner().invoke(cli, ["--help"]).output
    for word in ("analyze", "info", "functions", "decompile", "strings", "imports", "xrefs"):
        assert word in out
