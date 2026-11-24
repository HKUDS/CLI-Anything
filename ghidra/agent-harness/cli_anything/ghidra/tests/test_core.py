"""Unit tests for cli-anything-ghidra. No Ghidra, no Java and no real binary needed."""

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.ghidra.core import analysis, queries
from cli_anything.ghidra.ghidra_cli import cli, main, split_line
from cli_anything.ghidra.utils import ghidra_backend as backend
from cli_anything.ghidra.utils.ghidra_backend import (
    GhidraBackend, check, file_key, find_analyze_headless, work_home,
    _ADDRESS, _LOADER, _PROCESSOR, _TARGET,
)

LAUNCHER_NAME = "analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless"


@pytest.fixture(autouse=True)
def windows_path_rules(monkeypatch):
    monkeypatch.setattr(backend, "IS_WINDOWS", True)


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

    def __init__(self, cmd, kwargs, payload, stdout, returncode, hang, interrupt=False):
        self.cmd, self.kwargs, self.payload, self.stdout = cmd, kwargs, payload, stdout
        self.returncode, self.hang, self.pid, self.timed_out = returncode, hang, 4242, False
        self.interrupt = interrupt

    def communicate(self, timeout=None):
        if timeout is not None:
            self.kwargs["timeout"] = timeout
        if self.interrupt and not self.timed_out:
            self.timed_out = True
            raise KeyboardInterrupt
        if self.hang and not self.timed_out:
            self.timed_out = True
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        if self.payload is not None:
            i = self.cmd.index("-postScript")
            Path(self.cmd[i + 3]).write_text(
                self.payload if isinstance(self.payload, str) else json.dumps(self.payload), encoding="utf-8")
        return self.stdout, ""


def fake_popen(payload, calls, stdout="", returncode=0, hang=False, interrupt=False):
    """Popen factory that records every launch in `calls` and keeps the created procs in `.procs`."""
    def popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        proc = FakeProc(cmd, kwargs, payload, stdout, returncode, hang, interrupt)
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
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    c.write_bytes(b"diff")
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
    (be.projects / f"{file_key(sample)}.analyzed").write_text("")


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
    assert cmd[-2:] == ["main", "270"] and cmd[cmd.index("-postScript") + 2] == "decompile"
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
    if os.name == "nt":
        assert "creationflags" in kwargs and "start_new_session" not in kwargs
    else:
        assert kwargs["start_new_session"] is True and "creationflags" not in kwargs


def _alive(pid):
    if os.name == "nt":
        # bytes: the output is localized
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True).stdout
        return str(pid).encode() in out
    try:  # a zombie (an unreaped child in a minimal container) is dead for our purposes
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        pass
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


@pytest.mark.parametrize("bad", list("&|<>^%!()") + ['"', chr(10), chr(13)])
def test_check_path_rejects_cmd_metacharacters(bad):
    with pytest.raises(RuntimeError, match="cannot take"):
        backend.check_path("C:/work" + bad + "x", "work folder")


@pytest.mark.parametrize("bad", list("&%^!"))  # the characters that are legal in Windows folder names
def test_unsafe_work_folder_is_refused_before_launch(install, tmp_path, sample, bad):
    be = GhidraBackend(home=tmp_path / "home")
    be.projects = tmp_path / f"work{bad}x"
    be.projects.mkdir(parents=True)
    (be.projects / f"{file_key(sample)}.analyzed").write_text("")
    with patch.object(backend.subprocess, "Popen") as popen:
        with pytest.raises(RuntimeError, match="cannot take"):
            be.query(str(sample), "info")
    popen.assert_not_called()


def test_spaces_in_paths_are_fine(be, sample, tmp_path):
    odd = tmp_path / "Program Files" / "my work"
    odd.mkdir(parents=True)
    be.projects = odd
    (odd / f"{file_key(sample)}.analyzed").write_text("")
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_tool_folders_are_private_but_the_chosen_base_is_left_alone(install, tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    home = tmp_path / "work"
    home.mkdir()
    os.chmod(home, 0o755)
    (home / "projects").mkdir()
    os.chmod(home / "projects", 0o755)  # left over from an older run, umask-independent
    be = GhidraBackend(home=home)
    be._scratch().cleanup()
    assert stat.S_IMODE(home.stat().st_mode) == 0o755
    for name in ("projects", "tmp"):
        assert stat.S_IMODE((home / name).stat().st_mode) == 0o700


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


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks and owners")
def test_own_dir_refuses_a_symlink_and_does_not_chmod_its_target(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    target = tmp_path / "shared"
    target.mkdir()
    os.chmod(target, 0o1777)
    (tmp_path / "projects").symlink_to(target)
    with pytest.raises(RuntimeError, match="not a folder of this user"):
        backend._own_dir(tmp_path / "projects")
    assert stat.S_IMODE(target.stat().st_mode) == 0o1777


def test_heap_defaults_to_most_of_the_ram_unless_the_user_sets_one(be, monkeypatch):
    monkeypatch.delenv("GHIDRA_MAXMEM", raising=False)
    monkeypatch.delenv("GHIDRA_HEADLESS_MAXMEM", raising=False)
    monkeypatch.setattr(backend, "_ram_mb", lambda: 8000)
    assert be._env()["GHIDRA_HEADLESS_MAXMEM"] == "6000M"
    monkeypatch.setenv("GHIDRA_MAXMEM", "1G")
    assert "GHIDRA_HEADLESS_MAXMEM" not in be._env()


def test_imports_limit_and_lists_beyond_100000_are_not_cut():
    data = [{"library": "l", "name": str(i)} for i in range(100001)]
    assert len(queries.list_imports(fake_backend(data), "x")) == 100001
    assert len(queries.list_imports(fake_backend(data), "x", limit=2)) == 2


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
    cls.return_value.analyze.assert_called_once_with("x.bin", "BinaryLoader", "x86:LE:64:default", "0", 30, False)


def test_cli_timeout_bounds():
    assert run_cli(["analyze", "x.bin", "--timeout", "1"], {}).exit_code == 2


def test_cli_help_lists_commands():
    out = CliRunner().invoke(cli, ["--help"]).output
    for word in ("analyze", "info", "functions", "decompile", "strings", "imports", "xrefs"):
        assert word in out


# --- REPL line splitting --------------------------------------------------

@pytest.mark.parametrize("line,expected", [
    (r"info C:\Users\alice\sample.exe", ["info", r"C:\Users\alice\sample.exe"]),
    (r'analyze "C:\Program Files\app\a.exe" --timeout 30',
     ["analyze", r"C:\Program Files\app\a.exe", "--timeout", "30"]),
    ("decompile /tmp/a.bin 'FUN_1000'", ["decompile", "/tmp/a.bin", "FUN_1000"]),
    ("functions x.bin --filter main", ["functions", "x.bin", "--filter", "main"]),
])
def test_repl_line_keeps_windows_backslashes(line, expected):
    assert split_line(line) == expected


def test_repl_split_line_reaches_the_command_with_the_unmangled_path():
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value.query.return_value = {"functions": 1}
        res = CliRunner().invoke(cli, ["--json", *split_line(r"info C:\Users\alice\sample.exe")], obj={})
    assert res.exit_code == 0
    cls.return_value.query.assert_called_with(r"C:\Users\alice\sample.exe", "info")


# --- error contract of main() --------------------------------------------

def run_main(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["cli-anything-ghidra", *argv])
    with pytest.raises(SystemExit) as exc:
        main()
    out = capsys.readouterr()
    return exc.value.code, out.out, out.err


def test_usage_error_in_json_mode_is_json_with_exit_2(monkeypatch, capsys):
    code, out, err = run_main(monkeypatch, capsys, "--json", "analyze")
    assert code == 2 and err == ""
    assert "BINARY" in json.loads(out)["error"]


def test_unknown_option_in_json_mode_is_json(monkeypatch, capsys):
    code, out, _ = run_main(monkeypatch, capsys, "--json", "info", "x.bin", "--bogus")
    assert code == 2 and "--bogus" in json.loads(out)["error"]


def test_usage_error_without_json_stays_click_text_on_stderr(monkeypatch, capsys):
    code, out, err = run_main(monkeypatch, capsys, "analyze")
    assert code == 2 and out == "" and "Usage:" in err and "BINARY" in err


def test_help_exits_zero_with_text(monkeypatch, capsys):
    code, out, _ = run_main(monkeypatch, capsys, "--help")
    assert code == 0 and "analyze" in out


def test_backend_runtime_error_is_json_with_exit_1(monkeypatch, capsys):
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend", side_effect=RuntimeError("no ghidra here")):
        code, out, _ = run_main(monkeypatch, capsys, "--json", "info", "x.bin")
    assert code == 1 and json.loads(out) == {"error": "no ghidra here"}


@pytest.mark.parametrize("flag", [["--json"], []])
def test_unexpected_exception_is_a_message_not_a_traceback(monkeypatch, capsys, flag):
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value.query.side_effect = KeyError("c")
        code, out, err = run_main(monkeypatch, capsys, *flag, "info", "x.bin")
    text = json.loads(out)["error"] if flag else err
    assert code == 1 and "Unexpected error (KeyError)" in text and "Traceback" not in out + err


# --- query timeout option -------------------------------------------------

def test_query_timeout_option_reaches_the_backend():
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value.query.return_value = {}
        CliRunner().invoke(cli, ["--json", "--query-timeout", "900", "info", "x.bin"], obj={})
    cls.assert_called_once_with(query_timeout=900)


def test_query_timeout_default_and_bounds():
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value.query.return_value = {}
        CliRunner().invoke(cli, ["--json", "info", "x.bin"], obj={})
    cls.assert_called_once_with(query_timeout=300)
    assert CliRunner().invoke(cli, ["--query-timeout", "1", "info", "x.bin"], obj={}).exit_code == 2


def test_backend_uses_its_query_timeout_unless_one_is_given(install, tmp_path, sample):
    be = GhidraBackend(home=tmp_path / "work", query_timeout=777)
    analyzed(be, sample)
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({}, calls)):
        be.query(str(sample), "info")
        be.query(str(sample), "info", timeout=5)
    assert [c[1]["timeout"] for c in calls] == [777, 5]


@pytest.mark.parametrize("path", ["C:/a(b)/c", "C:/Program Files (x86)/work", "C:/my (old) dir/home", "/tmp/(x)"])
def test_parentheses_are_refused_with_or_without_spaces(path):
    # Found with the real launcher: the Ghidra .bat exits 255 on parentheses even when the path is quoted.
    with pytest.raises(RuntimeError, match="cannot take"):
        backend.check_path(path, "work folder")


@pytest.mark.parametrize("path", ["C:/Program Files/work", "C:/plain/home", "C:/my dir/home"])
def test_plain_and_space_paths_are_accepted(path):
    assert backend.check_path(path, "work folder") == path


# --- review round: Ctrl-C, analyzed marker, timeouts, hints, platform rules ---

def test_ctrl_c_stops_the_launcher_tree_and_propagates(be, sample):
    analyzed(be, sample)
    fake = fake_popen(None, [], interrupt=True)
    with patch.object(backend.subprocess, "Popen", side_effect=fake), patch.object(backend, "_kill_tree") as kill:
        with pytest.raises(KeyboardInterrupt):
            be.query(str(sample), "info")
    kill.assert_called_once_with(fake.procs[0])


def test_stubborn_child_is_killed_instead_of_waiting_forever():
    proc = MagicMock()
    proc.communicate.side_effect = [subprocess.TimeoutExpired("x", 10), ("", "")]
    with patch.object(backend, "_kill_tree"):
        GhidraBackend._stop(proc)
    proc.kill.assert_called_once()


def test_project_file_alone_does_not_count_as_analyzed(be, sample):
    be.projects.mkdir(parents=True, exist_ok=True)
    (be.projects / f"{file_key(sample)}.gpr").write_text("")  # what a failed import leaves behind
    with pytest.raises(RuntimeError, match="not been analyzed"):
        be.query(str(sample), "info")


def test_analyze_writes_the_marker_and_a_failed_one_removes_it(be, sample):
    marker = be.projects / f"{file_key(sample)}.analyzed"
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({"functions": 1}, [])):
        result = be.analyze(str(sample))
    assert marker.is_file() and result["analysis_timed_out"] is False
    failing = fake_popen(None, [], stdout="ERROR REPORT: Import failed")
    with patch.object(backend.subprocess, "Popen", side_effect=failing):
        with pytest.raises(RuntimeError):
            be.analyze(str(sample), force=True)  # force: the cached result would otherwise be returned
    assert not marker.exists()  # the stale claim is gone


def test_timed_out_analysis_is_flagged_not_reported_as_plain_success(be, sample):
    log = "ERROR REPORT: Analysis timed out at 3 seconds. Processing not completed for file: x"
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({"functions": 7}, [], stdout=log)):
        result = be.analyze(str(sample), timeout=3)
    assert result["analysis_timed_out"] is True and result["functions"] == 7


def test_unknown_format_gets_the_loader_hint(be, sample):
    log = "INFO  No load spec found for import file: x.bin (ProgramLoader)\nERROR REPORT: Import failed"
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(None, [], stdout=log)):
        with pytest.raises(RuntimeError, match="--loader BinaryLoader"):
            be.analyze(str(sample))


def test_busy_project_gets_a_retry_message(be, sample):
    analyzed(be, sample)
    log = "ERROR Unable to lock project! file:///x/projects"
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(None, [], stdout=log)):
        with pytest.raises(RuntimeError, match="busy"):
            be.query(str(sample), "info")


def test_decompile_gets_its_own_budget_from_the_query_timeout(be, sample):
    analyzed(be, sample)
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen({}, calls)):
        be.query(str(sample), "decompile", "main", timeout=300)
        be.query(str(sample), "functions", timeout=300)
    assert calls[0][0][-2:] == ["main", "270"]
    assert "functions" in calls[1][0] and "270" not in calls[1][0]


@pytest.mark.parametrize("good", ["ram:00401000", "CODE:0040", "Foo::bar", "mem:0x10"])
def test_targets_may_name_an_address_space(good):
    assert backend.check(good, backend._TARGET, "target") == good


def test_posix_launcher_only_refuses_control_characters(monkeypatch):
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    assert backend.check_path("/home/me/Projects (old)/a&b/%x!", "work folder")
    with pytest.raises(RuntimeError, match="newline or NUL"):
        backend.check_path("/tmp/a" + chr(10) + "b", "work folder")


def test_non_ascii_output_never_crashes_on_a_legacy_console(monkeypatch):
    import io
    from cli_anything.ghidra import ghidra_cli
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    ghidra_cli._safe_streams()
    print("int \u4e2d\u6587 = 1; // caf\u00e9")
    stream.flush()
    assert (chr(92) + "u4e2d").encode() in raw.getvalue() and "caf".encode() in raw.getvalue()


def test_plain_xrefs_output_is_json_not_a_python_repr(capsys):
    from cli_anything.ghidra import ghidra_cli
    ghidra_cli.output({"target": "0", "references": [{"from": "1", "function": None}]}, False)
    out = capsys.readouterr().out
    assert 'null' in out and "None" not in out and out.startswith("target: 0")


def test_abort_in_json_mode_is_json(monkeypatch, capsys):
    with patch("cli_anything.ghidra.ghidra_cli.cli", side_effect=click_abort()):
        code, out, _ = run_main(monkeypatch, capsys, "--json", "info", "x.bin")
    assert code == 1 and json.loads(out) == {"error": "Aborted."}


def click_abort():
    import click
    return click.Abort()


@pytest.mark.parametrize("line,expected", [
    ('functions x.bin --filter="my func"', ["functions", "x.bin", "--filter=my func"]),
    ("functions x.bin --filter=main", ["functions", "x.bin", "--filter=main"]),
    (r"info C:\Users\O'Brien\a.exe", ["info", r"C:\Users\O'Brien\a.exe"]),
    ('xrefs "x y.bin" ""', ["xrefs", "x y.bin", ""]),
    ("  info   x.bin  ", ["info", "x.bin"]),
])
def test_repl_split_handles_quoted_option_values(line, expected):
    assert split_line(line) == expected


def test_repl_split_reports_an_unbalanced_quote():
    with pytest.raises(ValueError):
        split_line('info "C:/a b/x.exe')


# --- caching of analyze (same bytes, same options) ----------------------

INFO = {"format": "Raw Binary", "language": "x86:LE:64:default", "functions": 1}


def test_second_analyze_of_the_same_bytes_reuses_the_result_without_ghidra(be, sample):
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, [])):
        first = be.analyze(str(sample))
    assert first["cached"] is False
    with patch.object(backend.subprocess, "Popen") as popen:
        second = be.analyze(str(sample))
    popen.assert_not_called()
    assert second["cached"] is True and second["functions"] == 1 and second["key"] == first["key"]
    assert second["analysis_timed_out"] is False


def test_force_reanalyzes_even_when_cached(be, sample):
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, [])):
        be.analyze(str(sample))
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, calls)):
        result = be.analyze(str(sample), force=True)
    assert len(calls) == 1 and result["cached"] is False


def test_different_options_reanalyze_the_same_bytes(be, sample):
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, [])):
        be.analyze(str(sample), loader="BinaryLoader", processor="x86:LE:64:default", entry="0")
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, calls)):
        be.analyze(str(sample), loader="BinaryLoader", processor="x86:LE:64:default", entry="10")
    assert len(calls) == 1


def test_a_timed_out_analysis_is_not_reused(be, sample):
    log = "ERROR REPORT: Analysis timed out at 3 seconds."
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, [], stdout=log)):
        assert be.analyze(str(sample), timeout=3)["analysis_timed_out"] is True
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, calls)):
        again = be.analyze(str(sample), timeout=600)
    assert len(calls) == 1 and again["analysis_timed_out"] is False


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"options": {}}'])
def test_unusable_marker_means_analyze_runs_again(be, sample, content):
    be.projects.mkdir(parents=True, exist_ok=True)
    (be.projects / f"{file_key(sample)}.analyzed").write_text(content)
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, calls)):
        assert be.analyze(str(sample))["cached"] is False
    assert len(calls) == 1


def test_cli_force_flag_reaches_the_backend():
    with patch("cli_anything.ghidra.ghidra_cli.GhidraBackend") as cls:
        cls.return_value.analyze.return_value = {"key": "k"}
        CliRunner().invoke(cli, ["--json", "analyze", "x.bin", "--force"], obj={})
    cls.return_value.analyze.assert_called_once_with("x.bin", None, None, None, 600, True)


# --- per-binary lock: REAL file locks and threads, no mocks -----------------

def test_second_run_on_the_same_binary_waits_for_the_first(be):
    order = []

    def holder():
        with be._locked("key1", 10):
            order.append("first-start")
            time.sleep(1.0)
            order.append("first-end")

    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.3)
    with be._locked("key1", 10):
        order.append("second")
    t.join()
    assert order == ["first-start", "first-end", "second"]


def test_waiting_for_a_busy_binary_gives_up_with_a_clear_error(be):
    with be._locked("key2", 5):
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="stayed busy"):
            with be._locked("key2", 0.5):
                pass
    assert 0.4 < time.monotonic() - started < 3


def test_different_binaries_do_not_block_each_other(be):
    with be._locked("keyA", 5):
        started = time.monotonic()
        with be._locked("keyB", 5):
            pass
    assert time.monotonic() - started < 1


def test_the_lock_is_released_after_an_error(be):
    with pytest.raises(ValueError):
        with be._locked("key3", 5):
            raise ValueError("boom")
    with be._locked("key3", 0.5):
        pass


def test_parallel_queries_run_one_after_another_and_all_succeed(be, sample):
    analyzed(be, sample)
    active, peak, results = [0], [0], []

    def fake(cmd, **kwargs):
        proc = FakeProc(cmd, kwargs, {"ok": True}, "", 0, False)
        real = proc.communicate

        def slow(timeout=None):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            time.sleep(0.3)
            active[0] -= 1
            return real(timeout)
        proc.communicate = slow
        return proc

    def call():
        results.append(be.query(str(sample), "info"))

    with patch.object(backend.subprocess, "Popen", side_effect=fake):
        threads = [threading.Thread(target=call) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert results == [{"ok": True}] * 4 and peak[0] == 1  # never two launcher runs at once


# --- diagnostics for exit codes ---------------------------------------------

def _proc(returncode, out="", err=""):
    return subprocess.CompletedProcess([], returncode, out, err)


def test_exit_255_on_windows_says_cmd_exe_could_not_parse_the_command_line(monkeypatch):
    monkeypatch.setattr(backend, "IS_WINDOWS", True)
    line = '"dir/home/projects" cannot be processed syntactically at this point.'
    text = GhidraBackend._failure(_proc(255, line))
    for expected in ("exit 255", "cmd.exe could not parse", "parenthesis", "syntactically"):
        assert expected in text


def test_unrecognized_failure_shows_the_last_log_lines_not_a_blank(monkeypatch):
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    text = GhidraBackend._failure(_proc(7, "line one\nline two\nline three\n"))
    assert "exit 7" in text and "line two | line three" in text and "line one" not in text


def test_silent_failure_says_so():
    assert "printed nothing" in GhidraBackend._failure(_proc(9))


def test_error_lines_win_over_the_tail():
    text = GhidraBackend._failure(_proc(1, "INFO x\nERROR Abort due to error: Directory not found: /nope\nINFO y"))
    assert "Directory not found" in text and "INFO y" not in text


def test_real_lock_exception_text_maps_to_the_retry_message():
    text = "ERROR Abort due to error: ghidra.framework.store.LockException: Unable to lock project! /x/projects/p"
    assert "busy" in GhidraBackend._failure(_proc(1, text))


# --- cache is tied to the Ghidra build; strings filter runs in the collector ---

def _set_version(install, version):
    props = install / "Ghidra"
    props.mkdir(exist_ok=True)
    (props / "application.properties").write_text(f"application.name=Ghidra\napplication.version={version}\n")


def test_ghidra_version_is_read_from_the_install(install):
    _set_version(install, "12.2")
    assert backend.ghidra_version(install / "support" / LAUNCHER_NAME) == "12.2"


def test_unreadable_version_is_unknown_not_an_error(install):
    assert backend.ghidra_version(install / "support" / LAUNCHER_NAME) == "unknown"


def test_switching_the_ghidra_build_invalidates_the_cached_analysis(install, tmp_path, sample):
    _set_version(install, "12.2")
    home = tmp_path / "work"
    first = GhidraBackend(home=home)
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, [])):
        first.analyze(str(sample))
    assert first.analyze(str(sample))["cached"] is True  # same build: reused
    _set_version(install, "12.3")
    second = GhidraBackend(home=home)
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, calls)):
        result = second.analyze(str(sample))
    assert len(calls) == 1 and result["cached"] is False  # another build: analyzed again


def test_marker_without_a_version_is_not_reused(be, sample):
    be.projects.mkdir(parents=True, exist_ok=True)
    options = {"loader": "", "processor": "", "entry": ""}
    (be.projects / f"{file_key(sample)}.analyzed").write_text(
        json.dumps({"options": options, "timed_out": False, "info": INFO}))  # written by an older harness
    calls = []
    with patch.object(backend.subprocess, "Popen", side_effect=fake_popen(INFO, calls)):
        assert be.analyze(str(sample))["cached"] is False
    assert len(calls) == 1


def test_strings_pass_the_min_length_to_the_collector():
    b = MagicMock()
    b.query.return_value = [{"length": 9, "value": "x" * 9}]
    assert len(queries.list_strings(b, "x.bin", 8)) == 1
    b.query.assert_called_once_with("x.bin", "strings", "8")


# --- the work folder must work for every user name, not only the author's ---

@pytest.fixture
def cp1252(monkeypatch):
    monkeypatch.setattr(backend.locale, "getpreferredencoding", lambda *a, **k: "cp1252")


@pytest.mark.parametrize("name", ["Max Mustermann", "Jürgen Müller", "José García", "Anne-Marie.Dupont",
                                  "ok~@+[1]", "ß", "Žofia"])
def test_ghidra_accepts_these_user_names(cp1252, name):
    assert backend.ghidra_path_problem("C:/Users/" + name + "/cli-anything-ghidra") is None


@pytest.mark.parametrize("name,char", [("O'Neil", "'"), ("name#1", "#"), ("a$b", "$"), ("a,b", ","), ("a=b", "="),
                                       ("a;b", ";"), ("a{b}", "{"), ("a`b", "`"), ("€uro", "€"), ("名前", "名")])
def test_ghidra_refuses_these_user_names(cp1252, name, char):
    assert backend.ghidra_path_problem("C:/Users/" + name + "/x") == char


def test_cjk_name_is_fine_where_the_code_page_can_hold_it(monkeypatch):
    monkeypatch.setattr(backend.locale, "getpreferredencoding", lambda *a, **k: "utf-8")
    assert backend.ghidra_path_problem("/home/名前/x") is None


def _as_profile(monkeypatch, tmp_path, name):
    profile = tmp_path / name
    profile.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: profile))
    monkeypatch.delenv("CLI_ANYTHING_GHIDRA_HOME", raising=False)
    return profile


def test_default_work_folder_is_inside_a_safe_profile(cp1252, monkeypatch, tmp_path):
    profile = _as_profile(monkeypatch, tmp_path, "Jürgen Müller")
    assert backend.work_home() == (profile / "cli-anything-ghidra").resolve()


@pytest.mark.skipif(os.name != "nt", reason="8.3 short names are a Windows feature")
@pytest.mark.parametrize("name", ["O'Neil", "name#1", "名前"])
def test_windows_falls_back_to_the_short_alias_of_the_profile(cp1252, monkeypatch, tmp_path, name):
    """Real Windows API, no mocks: the fallback stays inside the user's own profile and is ASCII-safe."""
    profile = _as_profile(monkeypatch, tmp_path, name)
    short = backend._short_path(profile)
    if short is None or backend.ghidra_path_problem(str(short)) is not None:
        pytest.skip("8.3 short names are disabled on this volume")
    home = backend.work_home()
    assert backend.ghidra_path_problem(str(home)) is None
    assert home.name == "cli-anything-ghidra"
    home.mkdir(parents=True)
    assert os.path.samefile(home.parent, profile)  # the same folder as the profile, not a shared location
    assert "ProgramData" not in str(home)


def test_windows_without_short_names_fails_closed_with_the_way_out(cp1252, monkeypatch, tmp_path):
    _as_profile(monkeypatch, tmp_path, "O'Neil")
    monkeypatch.setattr(backend, "IS_WINDOWS", True)
    monkeypatch.setattr(backend, "_short_path", lambda path: None)
    with pytest.raises(RuntimeError, match="CLI_ANYTHING_GHIDRA_HOME"):
        backend.work_home()


def test_fallback_is_not_created_when_the_profile_is_fine(cp1252, monkeypatch, tmp_path):
    _as_profile(monkeypatch, tmp_path, "Max Mustermann")
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    monkeypatch.setattr(backend, "POSIX_FALLBACK_BASE", tmp_path / "shared")
    backend.work_home()
    assert not (tmp_path / "shared").exists()


posix_only = pytest.mark.skipif(os.name == "nt", reason="owner and permission bits are POSIX")


@posix_only
def test_posix_fallback_is_a_private_per_user_folder(cp1252, monkeypatch, tmp_path):
    _as_profile(monkeypatch, tmp_path, "O'Neil")
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    monkeypatch.setattr(backend, "POSIX_FALLBACK_BASE", tmp_path / "shared")
    (tmp_path / "shared").mkdir()
    home = backend.work_home()
    assert home.parent == tmp_path / "shared" and stat.S_IMODE(home.stat().st_mode) == 0o700
    assert backend.work_home() == home  # stable on the second call


@posix_only
def test_posix_fallback_refuses_a_folder_others_can_write_to(cp1252, monkeypatch, tmp_path):
    _as_profile(monkeypatch, tmp_path, "O'Neil")
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    monkeypatch.setattr(backend, "POSIX_FALLBACK_BASE", tmp_path / "shared")
    (tmp_path / "shared").mkdir()
    first = backend.work_home()
    os.chmod(first, 0o777)  # someone widened the permissions, or created it with them
    with pytest.raises(RuntimeError, match="not a private folder"):
        backend.work_home()


@posix_only
def test_posix_fallback_refuses_a_symlink(cp1252, monkeypatch, tmp_path):
    profile = _as_profile(monkeypatch, tmp_path, "O'Neil")
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    shared = tmp_path / "shared"
    shared.mkdir()
    monkeypatch.setattr(backend, "POSIX_FALLBACK_BASE", shared)
    tag = backend.hashlib.sha256(str(profile).encode("utf-8", "replace")).hexdigest()[:8]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.symlink(elsewhere, shared / f"cli-anything-ghidra-{tag}")
    with pytest.raises(RuntimeError, match="not a private folder"):
        backend.work_home()


def test_fallback_differs_per_user_on_posix(cp1252, monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "IS_WINDOWS", False)
    monkeypatch.setattr(backend, "POSIX_FALLBACK_BASE", tmp_path / "shared")
    (tmp_path / "shared").mkdir()
    names = []
    for name in ("O'Neil", "O'Brien"):
        _as_profile(monkeypatch, tmp_path, name)
        names.append(backend._fallback_home().name)
    assert names[0] != names[1]


def test_explicit_work_folder_with_a_bad_character_is_an_error_not_a_fallback(cp1252, monkeypatch, tmp_path):
    monkeypatch.setenv("CLI_ANYTHING_GHIDRA_HOME", str(tmp_path / "it's mine"))
    with pytest.raises(RuntimeError, match="character \"'\".*CLI_ANYTHING_GHIDRA_HOME"):
        backend.work_home()


def test_no_machine_specific_paths_in_the_package():
    """Nothing may only work on the author's machine: no user names, home folders or drive paths in the code."""
    import re
    package = Path(backend.__file__).resolve().parents[1]
    parts = [r"[A-Za-z]:." + "Users", r"/home/[a-z]", r"/Users/[A-Za-z]", "domin", "Krinxy", "bechtold"]
    forbidden = re.compile("|".join(parts), re.IGNORECASE)
    offenders = []
    for path in package.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".java", ".md") and "tests" not in path.parts \
                and path.name != "repl_skin.py":
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if forbidden.search(line):
                    offenders.append(f"{path.name}:{number}")
    assert offenders == []
