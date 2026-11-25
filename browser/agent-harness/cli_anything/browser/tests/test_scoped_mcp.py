"""Exercise session reuse through a real MCP stdio child process."""

import asyncio
import os
import signal
import sys

import pytest
from click.testing import CliRunner

from cli_anything.browser.browser_cli import cli
from cli_anything.browser.core.session import Session
from cli_anything.browser.utils import domshell_backend as backend


@pytest.fixture
def stdio_backend(monkeypatch, tmp_path):
    child_script = tmp_path / "stdio_backend.py"
    child_script.write_text(
        """
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("scoped-browser-test")
cwd = "/"
dir_path = Path(__file__).parent
if "helper" in sys.argv:
    def stop_helper(*args):
        (dir_path / "helper-stopped").touch()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop_helper)
    (dir_path / "helper-ready").touch()
    time.sleep(25)
    sys.exit(0)
if "descendant" in sys.argv:
    helper = subprocess.Popen(
        [sys.executable, __file__, "helper"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    (dir_path / "helper-pid").write_text(str(helper.pid))
with (dir_path / "processes").open("a") as processes:
    processes.write(str(os.getpid()) + "\\n")
if "stall" in sys.argv:
    (dir_path / "startup-stalled").touch()
    time.sleep(15)
if "hold-startup" in sys.argv:
    (dir_path / "startup-stalled").touch()
    while not (dir_path / "release").exists():
        time.sleep(0.01)

@server.list_tools()
async def tools():
    return [Tool(name="domshell_execute", description="Test persistent cwd", inputSchema={
        "type": "object",
        "properties": {"command": {"type": "string"}, "group_id": {"type": "string"}},
        "required": ["command", "group_id"],
    })]

@server.call_tool()
async def execute(name, arguments):
    global cwd
    command = arguments["command"]
    if command == "die":
        with (dir_path / "attempts").open("a") as attempts:
            attempts.write("die\\n")
        os._exit(1)
    if command == "wait":
        (dir_path / "waiting").touch()
        while not (dir_path / "release").exists():
            await asyncio.sleep(0.01)
    lane = arguments["group_id"]
    if lane not in ("new", "5"):
        raise ValueError("Unexpected lane")
    with (dir_path / "lanes").open("a") as lanes:
        lanes.write(lane + "\\n")
    if command == "cd main":
        cwd = "/main"
    return [TextContent(type="text", text=f"{cwd}\\n[lane: 5]")]

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

asyncio.run(main())
if "descendant" in sys.argv:
    time.sleep(8)
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "DEFAULT_SERVER_CMD", sys.executable)
    monkeypatch.setattr(backend, "_build_server_args", lambda: [str(child_script)])
    return tmp_path


def assert_process_exited(pid: int):
    if os.name == "posix":
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


async def wait_for_marker(path):
    while not path.exists():
        await asyncio.sleep(0.01)


def test_ten_calls_reuse_process_and_lane(stdio_backend):
    with Session() as session:
        assert "error" not in backend.cd("main", session=session)
        for _ in range(9):
            assert backend.ls("", session=session)["raw"] == "/main"
            assert session.domshell_lane_id == "5"

    pids = (stdio_backend / "processes").read_text().splitlines()
    assert len(pids) == 1
    assert_process_exited(int(pids[0]))


def test_concurrent_first_calls_mint_one_lane(stdio_backend):
    async def first_calls(session):
        await asyncio.gather(
            backend._call_execute("ls", session=session),
            backend._call_execute("ls", session=session),
        )

    with Session() as session:
        asyncio.run(first_calls(session))

    assert (stdio_backend / "lanes").read_text().splitlines() == ["new", "5"]


def test_connection_failure_waits_for_next_command(stdio_backend):
    with Session() as session:
        assert backend.ls("", session=session)["raw"] == "/"
        with pytest.raises(RuntimeError, match="DOMShell MCP call failed"):
            asyncio.run(backend._call_execute("die", session=session))
        assert session.domshell_lane_id == "5"
        assert backend.ls("", session=session)["raw"] == "/"

    pids = (stdio_backend / "processes").read_text().splitlines()
    assert len(pids) == 2
    assert (stdio_backend / "attempts").read_text() == "die\n"
    for pid in pids:
        assert_process_exited(int(pid))


def test_cancelling_startup_stops_the_child(stdio_backend, monkeypatch):
    script = stdio_backend / "stdio_backend.py"
    monkeypatch.setattr(backend, "_build_server_args", lambda: [str(script), "stall"])

    async def cancel_startup(session):
        task = asyncio.create_task(backend._call_execute("ls", session=session))
        await asyncio.wait_for(wait_for_marker(stdio_backend / "startup-stalled"), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)

    with Session() as session:
        asyncio.run(cancel_startup(session))
        assert_process_exited(int((stdio_backend / "processes").read_text()))


def test_cancelling_queued_request_keeps_the_active_call(stdio_backend):
    async def cancel_queued_request(session):
        running = asyncio.create_task(backend._call_execute("wait", session=session))
        await asyncio.wait_for(wait_for_marker(stdio_backend / "waiting"), timeout=5)
        queued = asyncio.create_task(backend._call_execute("ls", session=session))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        (stdio_backend / "release").touch()
        await asyncio.wait_for(running, timeout=5)

    with Session() as session:
        asyncio.run(cancel_queued_request(session))
        assert backend.ls("", session=session)["raw"] == "/"
    assert len((stdio_backend / "processes").read_text().splitlines()) == 1


def test_cancelling_one_startup_waiter_preserves_the_other(stdio_backend, monkeypatch):
    script = stdio_backend / "stdio_backend.py"
    monkeypatch.setattr(backend, "_build_server_args", lambda: [str(script), "hold-startup"])

    async def run(session):
        pending = asyncio.create_task(backend._call_execute("ls", session=session))
        await asyncio.wait_for(wait_for_marker(stdio_backend / "startup-stalled"), timeout=5)
        cancel_me = asyncio.create_task(backend._call_execute("ls", session=session))
        await asyncio.sleep(0)
        cancel_me.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancel_me
        (stdio_backend / "release").touch()
        await asyncio.wait_for(pending, timeout=5)

    with Session() as session:
        asyncio.run(run(session))
        assert session.domshell_lane_id == "5"
    assert len((stdio_backend / "processes").read_text().splitlines()) == 1


@pytest.mark.skipif(os.name != "posix", reason="Checks POSIX process-group teardown")
@pytest.mark.parametrize("stall", [False, True])
def test_stopping_proxy_reaps_its_child_process(stdio_backend, monkeypatch, stall):
    args = [str(stdio_backend / "stdio_backend.py"), "descendant"]
    if stall:
        args.append("stall")
    monkeypatch.setattr(backend, "_build_server_args", lambda: args)

    async def run(session):
        request = asyncio.create_task(backend._call_execute("ls", session=session))
        await asyncio.wait_for(wait_for_marker(stdio_backend / "helper-ready"), timeout=5)
        if stall:
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(request, timeout=5)
        else:
            await asyncio.wait_for(request, timeout=5)

    try:
        with Session() as session:
            asyncio.run(run(session))
        asyncio.run(asyncio.wait_for(wait_for_marker(stdio_backend / "helper-stopped"), timeout=3))
        assert_process_exited(int((stdio_backend / "processes").read_text()))
    finally:
        pid_file = stdio_backend / "helper-pid"
        if pid_file.exists() and not (stdio_backend / "helper-stopped").exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_cli_and_repl_close_their_session(stdio_backend, monkeypatch):
    from cli_anything.browser import browser_cli
    from cli_anything.browser.utils.repl_skin import ReplSkin

    monkeypatch.setattr(backend, "is_available", lambda: (True, ""))
    monkeypatch.setattr(browser_cli, "_availability_cached", None)
    monkeypatch.setattr(browser_cli, "_session", None)
    monkeypatch.setattr(ReplSkin, "__init__", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(ReplSkin, "print_banner", lambda self: None)
    monkeypatch.setattr(ReplSkin, "print_goodbye", lambda self: None)
    monkeypatch.setattr(ReplSkin, "create_prompt_session", lambda self: None)
    commands = iter(["fs cd main", "repl", "quit", "fs ls", "fs ls", "quit"])
    monkeypatch.setattr(ReplSkin, "get_input", lambda self, *args, **kwargs: next(commands))

    runner = CliRunner()
    one_shot = runner.invoke(cli, ["fs", "ls"])
    assert one_shot.exit_code == 0, one_shot.output
    repl = runner.invoke(cli, [])
    assert repl.exit_code == 0, repl.output
    assert "/main" in repl.output

    pids = (stdio_backend / "processes").read_text().splitlines()
    assert len(pids) == 2
    for pid in pids:
        assert_process_exited(int(pid))
