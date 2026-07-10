"""
End-to-end tests for the LLDB CLI harness.

These tests exercise the persistent session behavior added for non-REPL
workflows, plus core debugger operations on a tiny compiled helper program.
"""

from __future__ import annotations

import json
import base64
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
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

struct Pair {
    int left;
    int right;
};

int probe(int a, int b) {
    struct Pair pair = {a, b};
    int total = pair.left + pair.right;
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


class DAPClient:
    def __init__(self):
        from cli_anything.lldb.dap import read_message

        self._read_message = read_message
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "cli_anything.lldb.dap"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=HARNESS_ROOT,
        )
        self.seq = 1
        self.messages: queue.Queue = queue.Queue()
        self.reader = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader.start()

    def _reader_loop(self):
        assert self.proc.stdout is not None
        try:
            while True:
                msg = self._read_message(self.proc.stdout)
                if msg is None:
                    return
                self.messages.put(msg)
        except Exception as exc:
            self.messages.put(exc)

    def request(self, command: str, arguments: dict | None = None, timeout: int = 30):
        from cli_anything.lldb.dap import encode_message

        seq = self.seq
        self.seq += 1
        payload = {"seq": seq, "type": "request", "command": command}
        if arguments is not None:
            payload["arguments"] = arguments
        assert self.proc.stdin is not None
        self.proc.stdin.write(encode_message(payload))
        self.proc.stdin.flush()

        events = []
        while True:
            msg = self._next_message(timeout)
            if msg.get("type") == "response" and msg.get("request_seq") == seq:
                assert msg.get("success"), msg.get("message")
                return msg, events
            events.append(msg)

    def read_event(self, name: str, timeout: int = 30):
        while True:
            msg = self._next_message(timeout)
            if msg.get("type") == "event" and msg.get("event") == name:
                return msg

    def read_until_event(self, names: set[str], timeout: int = 30):
        while True:
            msg = self._next_message(timeout)
            if msg.get("type") == "event" and msg.get("event") in names:
                return msg

    def _next_message(self, timeout: int):
        item = self.messages.get(timeout=timeout)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        if self.proc.poll() is None:
            try:
                self.request("disconnect", {"terminateDebuggee": True}, timeout=10)
                self.read_until_event({"terminated"}, timeout=10)
            except Exception:
                self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()


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
class TestLLDBDAPE2E:
    def test_dap_source_line_breakpoint(self, lldb_test_exe: str):
        source_path = Path(lldb_test_exe).parent / "lldb_helper.c"
        lines = source_path.read_text(encoding="utf-8").splitlines()
        target_line = next(i for i, line in enumerate(lines, start=1) if "pause_ms(50);" in line)

        with DAPClient() as client:
            client.request("initialize", {"adapterID": "cli-anything-lldb"})
            client.read_event("initialized")
            client.request("launch", {"program": lldb_test_exe, "stopOnEntry": False})
            bps, _ = client.request(
                "setBreakpoints",
                {
                    "source": {"path": str(source_path)},
                    "breakpoints": [{"line": target_line}],
                },
            )
            breakpoint_payload = bps["body"]["breakpoints"][0]
            assert breakpoint_payload["verified"] is True
            assert breakpoint_payload["line"] == target_line

            client.request("configurationDone")
            stopped = client.read_until_event({"stopped"})

            assert stopped["body"]["reason"] == "breakpoint"
            threads, _ = client.request("threads")
            thread_id = threads["body"]["threads"][0]["id"]
            stack, _ = client.request("stackTrace", {"threadId": thread_id, "levels": 10})
            frame = stack["body"]["stackFrames"][0]
            scopes, _ = client.request("scopes", {"frameId": frame["id"]})
            variables_ref = scopes["body"]["scopes"][0]["variablesReference"]
            variables, _ = client.request("variables", {"variablesReference": variables_ref})
            variables_by_name = {item["name"]: item for item in variables["body"]["variables"]}
            assert variables_by_name["pair"]["variablesReference"] > 0

            pair_children, _ = client.request(
                "variables",
                {"variablesReference": variables_by_name["pair"]["variablesReference"]},
            )
            pair_values = {item["name"]: item["value"] for item in pair_children["body"]["variables"]}
            assert pair_values["left"] in {"2", "0x2"}
            assert pair_values["right"] in {"40", "0x28"}

            set_total, _ = client.request(
                "setVariable",
                {
                    "variablesReference": variables_ref,
                    "name": "total",
                    "value": "77",
                },
            )
            assert set_total["body"]["value"] in {"77", "0x4d"}
            total_eval, _ = client.request("evaluate", {"expression": "total", "frameId": frame["id"]})
            assert total_eval["body"]["result"] in {"77", "0x4d"}

    def test_dap_breakpoint_variables_source_disassemble_and_continue(self, lldb_test_exe: str):
        with DAPClient() as client:
            initialize, _ = client.request("initialize", {"adapterID": "cli-anything-lldb"})
            assert initialize["body"]["supportsConfigurationDoneRequest"] is True
            client.read_event("initialized")

            client.request("launch", {"program": lldb_test_exe, "stopOnEntry": False})
            bps, _ = client.request("setFunctionBreakpoints", {"breakpoints": [{"name": "probe"}]})
            assert bps["body"]["breakpoints"]
            client.request("configurationDone")
            stopped = client.read_until_event({"stopped"})
            assert stopped["body"]["reason"] == "breakpoint"

            threads, _ = client.request("threads")
            thread_id = threads["body"]["threads"][0]["id"]
            stack, _ = client.request("stackTrace", {"threadId": thread_id, "levels": 10})
            frame = stack["body"]["stackFrames"][0]
            assert frame["instructionPointerReference"].startswith("0x")
            assert stack["body"]["totalFrames"] >= len(stack["body"]["stackFrames"])

            scopes, _ = client.request("scopes", {"frameId": frame["id"]})
            variables_ref = scopes["body"]["scopes"][0]["variablesReference"]
            variables, _ = client.request("variables", {"variablesReference": variables_ref})
            variables_by_name = {item["name"]: item for item in variables["body"]["variables"]}
            names = set(variables_by_name)
            assert {"a", "b"} <= names

            evaluated, _ = client.request("evaluate", {"expression": "a + b", "frameId": frame["id"]})
            assert evaluated["body"]["result"] in {"42", "0x2a"}

            source_path = frame.get("source", {}).get("path")
            assert source_path
            source, _ = client.request("source", {"source": {"path": source_path}})
            assert "GLOBAL_BUFFER" in source["body"]["content"]

            loaded_sources, _ = client.request("loadedSources")
            loaded_paths = {Path(item["path"]).name for item in loaded_sources["body"]["sources"]}
            assert "lldb_helper.c" in loaded_paths

            modules, _ = client.request("modules")
            module_names = {item["name"] for item in modules["body"]["modules"]}
            assert Path(lldb_test_exe).name in module_names

            exception_info, _ = client.request("exceptionInfo", {"threadId": thread_id})
            assert exception_info["body"]["exceptionId"]

            address_eval, _ = client.request(
                "evaluate",
                {"expression": "(char*)&GLOBAL_BUFFER[0]", "frameId": frame["id"]},
            )
            addr = _extract_address({"value": address_eval["body"]["result"]})
            memory, _ = client.request("readMemory", {"memoryReference": addr, "count": 32})
            raw = base64.b64decode(memory["body"]["data"])
            assert b"agent-native-lldb" in raw

            disassembly, _ = client.request(
                "disassemble",
                {"memoryReference": frame["instructionPointerReference"], "instructionCount": 4},
            )
            assert disassembly["body"]["instructions"]

            client.request("next", {"threadId": thread_id})
            step_stop = client.read_until_event({"stopped", "terminated"})
            assert step_stop["event"] in {"stopped", "terminated"}

            if step_stop["event"] == "stopped":
                client.request("continue", {"threadId": thread_id})
                final_event = client.read_until_event({"exited", "terminated", "stopped"})
                assert final_event["event"] in {"exited", "terminated", "stopped"}

    def test_dap_stop_on_entry(self, lldb_test_exe: str):
        with DAPClient() as client:
            client.request("initialize", {"adapterID": "cli-anything-lldb"})
            client.read_event("initialized")
            client.request("launch", {"program": lldb_test_exe, "stopOnEntry": True})
            client.request("configurationDone")
            stopped = client.read_until_event({"stopped"})

            assert stopped["body"]["reason"] == "entry"


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
