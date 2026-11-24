"""E2E tests: subprocess tests run the installed `cli-anything-ghidra` command.

Live tests drive the real Ghidra and are skipped unless GHIDRA_INSTALL_DIR points at an unzipped
Ghidra 12.x. They need a JDK 25+ (JAVA_HOME or GHIDRA_JAVA_HOME). The test binary is six raw bytes
written at test time (mov eax, 0x2a; ret), so nothing is committed or executed.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from cli_anything.ghidra.utils.ghidra_backend import find_analyze_headless

LIVE = bool(os.environ.get("GHIDRA_INSTALL_DIR"))
live = pytest.mark.skipif(not LIVE, reason="needs GHIDRA_INSTALL_DIR (Ghidra 12.x + JDK 25+)")
RAW_ARGS = ["--loader", "BinaryLoader", "--processor", "x86:LE:64:default", "--entry", "0"]


def _resolve_cli(name="cli-anything-ghidra"):
    """Installed command if on PATH (or CLI_ANYTHING_FORCE_INSTALLED=1), else python -m."""
    exe = shutil.which(name)
    if exe:
        return [exe]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED"):
        raise RuntimeError(f"{name} not found on PATH")
    return [sys.executable, "-m", "cli_anything.ghidra"]


def run_cli(*args, env_extra=None, timeout=600):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(_resolve_cli() + list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=timeout)


def test_help():
    res = run_cli("--help")
    assert res.returncode == 0 and "decompile" in res.stdout


def test_missing_ghidra_json_error(tmp_path):
    res = run_cli("--json", "info", str(tmp_path / "x.bin"),
                  env_extra={"GHIDRA_INSTALL_DIR": str(tmp_path / "missing")})
    assert res.returncode == 1
    assert "GHIDRA_INSTALL_DIR" in json.loads(res.stdout)["error"]


def test_shell_metacharacters_rejected_before_ghidra(tmp_path):
    support = tmp_path / "g" / "support"
    support.mkdir(parents=True)
    (support / ("analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless")).write_text("")
    blob = tmp_path / "b.bin"
    blob.write_bytes(b"x")
    res = run_cli("--json", "analyze", str(blob), "--processor", "x86:LE:64:default&calc",
                  env_extra={"GHIDRA_INSTALL_DIR": str(support.parent),
                             "CLI_ANYTHING_GHIDRA_HOME": str(tmp_path / "home")})
    assert res.returncode == 1
    assert "not allowed" in json.loads(res.stdout)["error"]


@pytest.fixture(scope="module")
def analyzed(tmp_path_factory):
    root = tmp_path_factory.mktemp("ghidra_e2e")
    blob = root / "answer.bin"
    blob.write_bytes(bytes.fromhex("b82a000000c3"))
    env = {"CLI_ANYTHING_GHIDRA_HOME": str(root / "home")}
    res = run_cli("--json", "analyze", str(blob), *RAW_ARGS, env_extra=env)
    assert res.returncode == 0, res.stdout + res.stderr
    return blob, env, json.loads(res.stdout)


@live
def test_live_analyze_reports_real_program(analyzed):
    _, _, info = analyzed
    assert info["format"] == "Raw Binary" and info["language"] == "x86:LE:64:default"
    assert info["functions"] == 1


@live
def test_live_functions_and_decompile_show_constant(analyzed):
    blob, env, _ = analyzed
    funcs = json.loads(run_cli("--json", "functions", str(blob), env_extra=env).stdout)
    assert funcs[0]["size"] == 6
    dec = json.loads(run_cli("--json", "decompile", str(blob), funcs[0]["name"], env_extra=env).stdout)
    assert "return 0x2a;" in dec["c"]


@live
def test_live_decompile_by_address_and_unknown_target(analyzed):
    blob, env, _ = analyzed
    assert "0x2a" in run_cli("decompile", str(blob), "0", env_extra=env).stdout
    res = run_cli("--json", "decompile", str(blob), "NoSuchFunction", env_extra=env)
    assert res.returncode == 1 and "error" in json.loads(res.stdout)


@live
def test_live_strings_imports_xrefs_are_well_formed(analyzed):
    blob, env, _ = analyzed
    assert json.loads(run_cli("--json", "strings", str(blob), env_extra=env).stdout) == []
    assert json.loads(run_cli("--json", "imports", str(blob), env_extra=env).stdout) == []
    refs = json.loads(run_cli("--json", "xrefs", str(blob), "0", env_extra=env).stdout)
    assert refs["target"] == "00000000" and refs["references"] == []


@live
def test_live_query_before_analyze_fails_clearly(tmp_path):
    blob = tmp_path / "other.bin"
    blob.write_bytes(b"\x90\x90")
    res = run_cli("--json", "info", str(blob), env_extra={"CLI_ANYTHING_GHIDRA_HOME": str(tmp_path / "home")})
    assert res.returncode == 1 and "not been analyzed" in json.loads(res.stdout)["error"]


def test_usage_error_in_json_mode_is_json_on_stdout():
    res = run_cli("--json", "analyze")
    assert res.returncode == 2
    assert "BINARY" in json.loads(res.stdout)["error"]


def _real_binary():
    """CLI_ANYTHING_GHIDRA_TEST_BINARY (any size, any OS), else a small binary every machine has:
    find.exe on Windows, `true` elsewhere."""
    if os.environ.get("CLI_ANYTHING_GHIDRA_TEST_BINARY"):
        return Path(os.environ["CLI_ANYTHING_GHIDRA_TEST_BINARY"])
    if sys.platform == "win32":
        return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "find.exe"
    return Path(shutil.which("true") or "/bin/true")


@pytest.fixture(scope="module")
def real_analyzed(tmp_path_factory):
    binary = _real_binary()
    if not binary.is_file():
        pytest.skip("no small system binary found")
    env = {"CLI_ANYTHING_GHIDRA_HOME": str(tmp_path_factory.mktemp("ghidra_real") / "home")}
    res = run_cli("--json", "analyze", str(binary), "--timeout", "600", env_extra=env, timeout=900)
    assert res.returncode == 0, res.stdout + res.stderr
    return binary, env, json.loads(res.stdout)


@live
def test_live_real_binary_is_recognized_and_analyzed(real_analyzed):
    _, _, info = real_analyzed
    assert info["format"] in ("Portable Executable (PE)", "Executable and Linking Format (ELF)")
    assert info["functions"] > 5


@live
def test_live_real_binary_queries_return_real_data(real_analyzed):
    binary, env, info = real_analyzed
    funcs = json.loads(run_cli("--json", "functions", str(binary), env_extra=env).stdout)
    assert len(funcs) == info["functions"] and all(f["size"] > 0 for f in funcs)
    dec = json.loads(run_cli("--json", "decompile", str(binary), funcs[0]["name"], env_extra=env).stdout)
    assert "(" in dec["c"] and dec["name"] == funcs[0]["name"]
    imports = json.loads(run_cli("--json", "imports", str(binary), env_extra=env).stdout)
    assert isinstance(imports, list) and (sys.platform != "win32" or imports)
    strings = json.loads(run_cli("--json", "strings", str(binary), "--limit", "5", env_extra=env).stdout)
    assert isinstance(strings, list) and len(strings) <= 5


@live
def test_live_filter_and_limit_are_applied_inside_ghidra(real_analyzed):
    binary, env, _ = real_analyzed
    funcs = json.loads(run_cli("--json", "functions", str(binary), env_extra=env).stdout)
    word = funcs[0]["name"][:3].upper()  # case-insensitive substring
    hits = json.loads(run_cli("--json", "functions", str(binary), "--filter", word, env_extra=env).stdout)
    assert hits and all(word.lower() in f["name"].lower() for f in hits)
    assert len(json.loads(run_cli("--json", "functions", str(binary), "--limit", "1", env_extra=env).stdout)) == 1
    nothing = json.loads(run_cli("--json", "functions", str(binary), "--filter", "no such \\ name\"", env_extra=env).stdout)
    assert nothing == []
    assert len(json.loads(run_cli("--json", "strings", str(binary), "--limit", "2", env_extra=env).stdout)) <= 2


@live
def test_live_biggest_function_decompiles_and_xrefs_work(real_analyzed):
    binary, env, _ = real_analyzed
    funcs = json.loads(run_cli("--json", "functions", str(binary), env_extra=env).stdout)
    big = max(funcs, key=lambda f: f["size"])
    dec = run_cli("--json", "decompile", str(binary), big["address"], env_extra=env, timeout=900)
    assert dec.returncode == 0, dec.stdout
    assert "{" in json.loads(dec.stdout)["c"]
    by_name = run_cli("--json", "decompile", str(binary), big["name"], env_extra=env, timeout=900)  # also namespaced names
    assert by_name.returncode == 0, by_name.stdout
    refs = json.loads(run_cli("--json", "xrefs", str(binary), big["address"], env_extra=env).stdout)
    assert refs["truncated"] is False and isinstance(refs["references"], list)


@live
def test_live_second_analyze_is_cached_and_force_reanalyzes(analyzed):
    blob, env, _ = analyzed
    again = json.loads(run_cli("--json", "analyze", str(blob), *RAW_ARGS, env_extra=env).stdout)
    assert again["cached"] is True and again["functions"] == 1
    forced = json.loads(run_cli("--json", "analyze", str(blob), *RAW_ARGS, "--force", env_extra=env).stdout)
    assert forced["cached"] is False and forced["functions"] == 1


# --- real exit codes and failure modes of the real launcher ------------------

@live
def test_live_parallel_queries_on_one_binary_all_succeed(analyzed):
    """Ghidra locks the project even for read-only runs; the harness queues parallel calls instead of failing."""
    blob, env, _ = analyzed
    results = []
    threads = [threading.Thread(target=lambda: results.append(run_cli("--json", "functions", str(blob), env_extra=env)))
               for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [r.returncode for r in results] == [0, 0, 0], [r.stdout for r in results]
    assert all(len(json.loads(r.stdout)) == 1 for r in results)


@live
def test_live_query_during_forced_reanalysis_waits_and_then_succeeds(analyzed):
    blob, env, _ = analyzed
    forced = []
    t = threading.Thread(target=lambda: forced.append(
        run_cli("--json", "analyze", str(blob), *RAW_ARGS, "--force", env_extra=env)))
    t.start()
    time.sleep(4)  # the re-analysis is running and holds the project
    during = run_cli("--json", "functions", str(blob), env_extra=env)
    t.join()
    assert forced[0].returncode == 0 and during.returncode == 0, during.stdout
    assert len(json.loads(during.stdout)) == 1


@live
def test_live_unknown_format_without_loader_explains_what_to_do(tmp_path):
    blob = tmp_path / "raw.bin"
    blob.write_bytes(bytes.fromhex("b82a000000c3"))
    res = run_cli("--json", "analyze", str(blob), env_extra={"CLI_ANYTHING_GHIDRA_HOME": str(tmp_path / "home")})
    assert res.returncode == 1
    assert "--loader BinaryLoader" in json.loads(res.stdout)["error"]


def _run_real_launcher(project_dir):
    env = dict(os.environ)
    if os.environ.get("GHIDRA_JAVA_HOME"):
        env["JAVA_HOME"] = os.environ["GHIDRA_JAVA_HOME"]
    cmd = [str(find_analyze_headless()), str(project_dir), "p", "-process", "x.bin", "-noanalysis", "-readOnly"]
    return subprocess.run(cmd,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env, timeout=120)


@pytest.mark.skipif(sys.platform != "win32", reason="the launcher is a .bat run by cmd.exe only on Windows")
@live
def test_live_launcher_exits_255_when_a_parenthesis_is_followed_by_more_path(tmp_path):
    """Why the harness refuses parentheses: our work folder is <home>/projects, so a parenthesis in <home> is
    followed by more path, and the real launcher dies in cmd.exe with exit 255 before Java starts."""
    project_dir = tmp_path / "paren(x)" / "projects"
    project_dir.mkdir(parents=True)
    proc = _run_real_launcher(project_dir)
    log = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 255
    assert "ERROR" not in log and "Exception" not in log  # one cmd.exe line, which is why the message used to be empty


@pytest.mark.skipif(sys.platform != "win32", reason="the launcher is a .bat run by cmd.exe only on Windows")
@live
def test_live_launcher_fails_with_a_java_parse_error_when_a_parenthesis_ends_the_path(tmp_path):
    project_dir = tmp_path / "paren(x)"
    project_dir.mkdir()
    proc = _run_real_launcher(project_dir)
    assert proc.returncode == 1 and "parseOptions" in (proc.stdout or "") + (proc.stderr or "")


def test_parentheses_in_the_work_folder_are_refused_with_the_reason(tmp_path):
    if sys.platform != "win32":
        pytest.skip("the rule applies to the Windows launcher")
    fake_install = tmp_path / "g" / "support"
    fake_install.mkdir(parents=True)
    (fake_install / "analyzeHeadless.bat").write_text("")
    blob = tmp_path / "b.bin"
    blob.write_bytes(b"x")
    res = run_cli("--json", "analyze", str(blob), env_extra={
        "GHIDRA_INSTALL_DIR": str(fake_install.parent), "CLI_ANYTHING_GHIDRA_HOME": str(tmp_path / "paren(x)")})
    assert res.returncode == 1 and "character '('" in json.loads(res.stdout)["error"]


@live
def test_live_real_binary_strings_min_length_is_applied_before_the_cap(real_analyzed):
    binary, env, _ = real_analyzed
    short = json.loads(run_cli("--json", "strings", str(binary), "--min-length", "1", env_extra=env).stdout)
    long_only = json.loads(run_cli("--json", "strings", str(binary), "--min-length", "12", env_extra=env).stdout)
    assert 0 < len(long_only) < len(short) and all(s["length"] >= 12 for s in long_only)


@live
def test_live_cache_records_the_real_ghidra_build(analyzed):
    from cli_anything.ghidra.utils.ghidra_backend import ghidra_version
    assert ghidra_version(find_analyze_headless()) not in ("", "unknown")


@live
@pytest.mark.parametrize("name", ["Max Mustermann", "Jürgen Müller", "O'Neil", "name#1", "名前"])
def test_live_works_for_any_user_name(tmp_path, name):
    """The default work folder comes from the profile; names Ghidra cannot take must fall back, not fail."""
    profile = tmp_path / name
    profile.mkdir()
    blob = tmp_path / "answer.bin"
    blob.write_bytes(bytes.fromhex("b82a000000c3"))
    if sys.platform == "win32" and name in ("O'Neil", "name#1", "名前"):
        from cli_anything.ghidra.utils.ghidra_backend import _short_path, ghidra_path_problem
        short = _short_path(profile)
        if short is None or ghidra_path_problem(str(short)) is not None:
            pytest.skip("8.3 short names are disabled on this volume")
    env = {"USERPROFILE": str(profile), "HOME": str(profile), "CLI_ANYTHING_GHIDRA_HOME": ""}
    res = run_cli("--json", "analyze", str(blob), *RAW_ARGS, env_extra=env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["functions"] == 1
    dec = run_cli("decompile", str(blob), "0", env_extra=env)
    assert dec.returncode == 0 and "0x2a" in dec.stdout
