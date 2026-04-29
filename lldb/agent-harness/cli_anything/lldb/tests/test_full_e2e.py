"""
End-to-end tests for the LLDB CLI harness.

These tests exercise the persistent session behavior added for non-REPL
workflows, plus core debugger operations on a tiny compiled helper program.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS_ROOT = str(Path(__file__).resolve().parents[3])
TEST_CORE = os.environ.get("LLDB_TEST_CORE", "").strip()

HELPER_SOURCE = r"""
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
static void pause_ms(int ms) { Sleep(ms); }
#else
#include <unistd.h>
static void pause_ms(int ms) { usleep((useconds_t)ms * 1000); }
#endif

char GLOBAL_BUFFER[] = "agent-native-lldb";

int probe(int a, int b) {
    int total = a + b;
    pause_ms(50);
    return GLOBAL_BUFFER[0] + total;
}

int run_attach_mode(void) {
    pause_ms(4000);
    return 0;
}

int main(int argc, char** argv) {
    if (argc > 1 && strcmp(argv[1], "sleep") == 0) {
        return run_attach_mode();
    }

    int value = probe(2, 40);
    printf("value=%d\n", value);
    fflush(stdout);
    pause_ms(50);
    return 0;
}
"""

try:
    import lldb  # noqa: F401

    HAS_LLDB_MODULE = True
except Exception:
    HAS_LLDB_MODULE = False

skip_no_lldb = pytest.mark.skipif(not HAS_LLDB_MODULE, reason="lldb module not importable")


def _find_compiler() -> str | None:
    for name in ("clang", "gcc", "cc"):
        path = shutil.which(name)
        if path:
            return path
    return None


@pytest.fixture(scope="session")
def lldb_test_exe(tmp_path_factory) -> str:
    compiler = _find_compiler()
    if not compiler:
        pytest.skip("No C compiler found for LLDB E2E helper build")

    build_dir = tmp_path_factory.mktemp("lldb-e2e")
    src = build_dir / "lldb_helper.c"
    src.write_text(HELPER_SOURCE, encoding="utf-8")

    exe_name = "lldb_helper.exe" if os.name == "nt" else "lldb_helper"
    exe_path = build_dir / exe_name

    cmd = [compiler, "-g", "-O0", str(src), "-o", str(exe_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip(f"Failed to build LLDB E2E helper: {result.stderr.strip()}")

    return str(exe_path)


@pytest.fixture()
def session_file(tmp_path) -> Path:
    return tmp_path / "lldb-session.json"


@pytest.fixture()
def core_file(tmp_path) -> str:
    if TEST_CORE and os.path.isfile(TEST_CORE):
        return TEST_CORE

    placeholder = tmp_path / "placeholder.core"
    placeholder.write_bytes(b"lldb-core-placeholder")
    return str(placeholder)


def _run_cli(*args, session_file: Path, input_text: str | None = None, timeout: int = 90) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "cli_anything.lldb.lldb_cli",
        "--json",
        "--session-file",
        str(session_file),
    ]
    cmd.extend(args)
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=HARNESS_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed ({' '.join(args)}): {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def _close_session(session_file: Path):
    cmd = [
        sys.executable,
        "-m",
        "cli_anything.lldb.lldb_cli",
        "--json",
        "--session-file",
        str(session_file),
        "session",
        "close",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=HARNESS_ROOT)


def _extract_address(payload: dict) -> str:
    for key in ("value", "summary"):
        value = payload.get(key)
        if isinstance(value, str):
            match = re.search(r"0x[0-9a-fA-F]+", value)
            if match:
                return match.group(0)
    raise AssertionError(f"Could not extract address from payload: {payload}")


@skip_no_lldb
class TestLLDBE2E:
    def test_persistent_target_info(self, lldb_test_exe: str, session_file: Path):
        try:
            create = _run_cli("target", "create", "--exe", lldb_test_exe, session_file=session_file)
            info = _run_cli("target", "info", session_file=session_file)
        finally:
            _close_session(session_file)

        assert create["executable"] == lldb_test_exe
        assert info["executable"]
        assert info["num_breakpoints"] == 0

    def test_breakpoint_step_expr_and_memory_workflow(self, lldb_test_exe: str, session_file: Path):
        try:
            _run_cli("target", "create", "--exe", lldb_test_exe, session_file=session_file)
            bp = _run_cli("breakpoint", "set", "--function", "probe", session_file=session_file)
            launched = _run_cli("process", "launch", session_file=session_file)
            threads = _run_cli("thread", "list", session_file=session_file)
            backtrace = _run_cli("thread", "backtrace", session_file=session_file)
            locals_payload = _run_cli("frame", "locals", session_file=session_file)
            expr_payload = _run_cli("expr", "a + b", session_file=session_file)
            address_payload = _run_cli("expr", "(char*)&GLOBAL_BUFFER[0]", session_file=session_file)
            addr = _extract_address(address_payload)
            memory = _run_cli("memory", "read", "--address", addr, "--size", "32", session_file=session_file)
            found = _run_cli(
                "memory",
                "find",
                "agent-native-lldb",
                "--start",
                addr,
                "--size",
                "32",
                session_file=session_file,
            )
            stepped = _run_cli("step", "over", session_file=session_file)
            _run_cli("breakpoint", "delete", "--id", str(bp["id"]), session_file=session_file)
            finished = _run_cli("process", "continue", session_file=session_file)
        finally:
            _close_session(session_file)

        assert launched["state"] == "stopped"
        assert bp["locations"] >= 1
        assert threads["threads"]
        assert backtrace["frames"]
        local_names = {item["name"] for item in locals_payload["variables"]}
        assert {"a", "b"} <= local_names
        assert expr_payload["error"] is None
        assert expr_payload["value"] in {"42", "0x2a"}
        assert len(memory["hex"]) >= 32
        assert found["found"] is True
        assert stepped["address"].startswith("0x")
        assert finished["state"] in {"exited", "stopped"}

    def test_attach_cleanup_does_not_kill_process(self, lldb_test_exe: str, session_file: Path):
        proc = subprocess.Popen([lldb_test_exe, "sleep"], cwd=Path(lldb_test_exe).parent)
        try:
            _run_cli("target", "create", "--exe", lldb_test_exe, session_file=session_file)
            attached = _run_cli("process", "attach", "--pid", str(proc.pid), session_file=session_file)
            assert attached["pid"] == proc.pid

            _close_session(session_file)

            assert proc.poll() is None
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


@skip_no_lldb
class TestCoreE2E:
    def test_core_load_requires_target(self, session_file: Path, core_file: str):
        cmd = [
            sys.executable,
            "-m",
            "cli_anything.lldb.lldb_cli",
            "--json",
            "--session-file",
            str(session_file),
            "core",
            "load",
            "--path",
            core_file,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=HARNESS_ROOT)
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert "error" in data
