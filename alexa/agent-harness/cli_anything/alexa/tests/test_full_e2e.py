"""End-to-end tests for cli-anything-alexa.

Two layers:

1. Subprocess tests (always run) invoke the installed `cli-anything-alexa`
   command and check help, JSON contracts, error codes, dry-run and that the
   local sign-in proxy really serves HTTP.
2. Live Amazon tests (opt-in) talk to a real Amazon account and real Echo
   devices. They run only when ALEXA_E2E=1 and you are logged in
   (`cli-anything-alexa auth login`). ALEXA_E2E_DEVICE names the Echo to use;
   ALEXA_E2E_SPEAK=1 additionally makes it speak out loud.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import pytest


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.alexa.alexa_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


CLI = _resolve_cli("cli-anything-alexa")


def _run(args, env=None, check=False, timeout=60):
    return subprocess.run(CLI + args, capture_output=True, text=True, env=env, check=check, timeout=timeout)


@pytest.fixture
def iso_env(tmp_path):
    env = dict(os.environ, ALEXA_CLI_HOME=str(tmp_path))
    return env, tmp_path


class TestCLISubprocess:
    def test_help_lists_command_groups(self):
        r = _run(["--help"], check=True)
        for cmd in ["auth", "device", "speak", "announce", "command", "routine", "music", "volume", "smarthome"]:
            assert cmd in r.stdout

    def test_version(self):
        r = _run(["--version"], check=True)
        assert "cli-anything-alexa" in r.stdout

    def test_status_logged_out_json(self, iso_env):
        env, _ = iso_env
        r = _run(["--json", "auth", "status"], env=env, check=True)
        assert json.loads(r.stdout) == {"logged_in": False}

    def test_logged_out_action_fails_with_code(self, iso_env):
        env, _ = iso_env
        r = _run(["--json", "speak", "kitchen", "hi"], env=env)
        assert r.returncode == 1
        assert json.loads(r.stdout)["error"] == "not_logged_in"

    def test_dry_run_from_cached_devices(self, iso_env):
        env, home = iso_env
        (home / "devices.json").write_text(json.dumps([
            {"name": "Kitchen Echo", "serial": "G0911", "type": "T", "family": "ECHO",
             "online": True, "is_speaker": True, "cluster_members": []}]))
        r = _run(["--json", "--dry-run", "announce", "Dinner", "-d", "kitchen"], env=env, check=True)
        data = json.loads(r.stdout)
        assert data["dry_run"] is True
        assert data["action"]["devices"] == [{"name": "Kitchen Echo", "serial": "G0911"}]
        print(f"\n  dry-run action: {data['action']}")

    def test_login_proxy_serves_http(self, iso_env):
        """auth login picks a free port, prints it, and the proxy answers there."""
        import re
        env, _ = iso_env
        proc = subprocess.Popen(CLI + ["auth", "login", "--email", "e2e@example.com", "--timeout", "20"],
                                env=dict(env, BROWSER="true"), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        try:
            port = None
            for _ in range(20):
                line = proc.stderr.readline()
                m = re.search(r"http://127\.0\.0\.1:(\d+)", line or "")
                if m:
                    port = int(m.group(1))
                    break
            assert port, "auth login did not print its local sign-in URL"
            status = None
            for _ in range(40):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=15) as resp:
                        status = resp.status
                    break
                except Exception:
                    time.sleep(0.5)
            assert status == 200, "login proxy did not answer on 127.0.0.1"
            print(f"\n  login proxy answered HTTP {status} on auto-selected port {port}")
        finally:
            proc.terminate()
            proc.wait(timeout=10)


LIVE = os.environ.get("ALEXA_E2E") == "1"
live = pytest.mark.skipif(not LIVE, reason="set ALEXA_E2E=1 and run `auth login` to test against Amazon")


@live
class TestLiveAmazon:
    def test_session_verifies(self):
        r = _run(["--json", "auth", "status", "--verify"], check=True)
        data = json.loads(r.stdout)
        assert data["logged_in"] is True and data["customer_id"]

    def test_device_list_has_speakers(self):
        r = _run(["--json", "device", "list"], check=True)
        devices = json.loads(r.stdout)
        assert devices, "account has no Echo devices"
        assert all(d["serial"] for d in devices)
        print("\n  devices:", ", ".join(d["name"] for d in devices))

    def test_routine_list(self):
        r = _run(["--json", "routine", "list"], check=True)
        assert isinstance(json.loads(r.stdout), list)

    def test_smarthome_list(self):
        r = _run(["--json", "smarthome", "list"], check=True)
        assert isinstance(json.loads(r.stdout), list)

    @pytest.mark.skipif(os.environ.get("ALEXA_E2E_SPEAK") != "1", reason="set ALEXA_E2E_SPEAK=1 to hear it")
    def test_speak_out_loud(self):
        device = os.environ.get("ALEXA_E2E_DEVICE")
        assert device, "set ALEXA_E2E_DEVICE to an Echo name"
        r = _run(["--json", "speak", device, "CLI Anything end to end test"], check=True)
        assert json.loads(r.stdout)["sent"] is True
