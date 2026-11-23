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

import pytest

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
