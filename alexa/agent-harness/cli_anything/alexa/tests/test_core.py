"""Unit tests for cli-anything-alexa (no network, no Amazon account).

The backend is monkeypatched so every CLI command is exercised end to end
through Click, including JSON output, error codes and dry-run.
"""

import json
import os
import stat

import pytest
from click.testing import CliRunner

from cli_anything.alexa import alexa_cli
from cli_anything.alexa.core import actions as act
from cli_anything.alexa.core import devices as dev
from cli_anything.alexa.core import smarthome as sh
from cli_anything.alexa.utils import alexa_backend as backend

RAW_DEVICES = [
    {"accountName": "Kitchen Echo", "serialNumber": "G0911", "deviceType": "A3S5BH2HU6VAYF",
     "deviceFamily": "ECHO", "online": True, "capabilities": ["VOLUME_SETTING"]},
    {"accountName": "Living Room Echo Show", "serialNumber": "G0922", "deviceType": "A4ZP7ZC4PI6TO",
     "deviceFamily": "KNIGHT", "online": True, "capabilities": []},
    {"accountName": "Bedroom Echo", "serialNumber": "G0933", "deviceType": "A3S5BH2HU6VAYF",
     "deviceFamily": "ECHO", "online": False, "capabilities": ["VOLUME_SETTING"]},
    {"accountName": "This Device", "serialNumber": "APP1", "deviceType": "A2IVLV5VM2W81",
     "deviceFamily": "VOX", "online": True, "capabilities": ["MICROPHONE", "AUDIO_PLAYER"]},
]


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEXA_CLI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_backend(home, monkeypatch):
    sent = []
    monkeypatch.setattr(backend, "fetch_devices", lambda: RAW_DEVICES)
    monkeypatch.setattr(backend, "execute", lambda action: sent.append(action) or {"sent": True})
    backend.save_account({"email": "a@b.c", "domain": "amazon.com", "oauth": {"refresh_token": "x"}})
    return sent


def run(*args):
    result = CliRunner().invoke(alexa_cli.cli, ["--json", *args])
    data = json.loads(result.output) if result.output.strip().startswith(("{", "[")) else None
    return result, data


# ── devices ──────────────────────────────────────────────────────────

class TestDevices:
    def setup_method(self):
        self.devices = [dev.normalize(d) for d in RAW_DEVICES]

    def test_normalize_fields(self):
        d = self.devices[0]
        assert d["name"] == "Kitchen Echo" and d["serial"] == "G0911"
        assert d["family"] == "ECHO" and d["online"] is True and d["is_speaker"] is True

    def test_app_is_not_speaker(self):
        assert self.devices[3]["is_speaker"] is False

    def test_filter_hides_non_speakers_and_sorts(self):
        names = [d["name"] for d in dev.filter_devices(self.devices)]
        assert names == ["Bedroom Echo", "Kitchen Echo", "Living Room Echo Show"]
        assert len(dev.filter_devices(self.devices, include_all=True)) == 4

    def test_resolve_exact_case_insensitive(self):
        assert dev.resolve(self.devices, "kitchen echo")["serial"] == "G0911"

    def test_resolve_by_serial(self):
        assert dev.resolve(self.devices, "g0933")["name"] == "Bedroom Echo"

    def test_resolve_unique_substring(self):
        assert dev.resolve(self.devices, "living")["serial"] == "G0922"

    def test_resolve_ambiguous(self):
        with pytest.raises(dev.AmbiguousDevice, match="Kitchen Echo"):
            dev.resolve(self.devices, "echo")

    def test_resolve_missing_lists_known(self):
        with pytest.raises(dev.DeviceNotFound, match="Known devices"):
            dev.resolve(self.devices, "garage")

    def test_resolve_empty(self):
        with pytest.raises(dev.DeviceNotFound):
            dev.resolve(self.devices, "  ")


# ── actions ──────────────────────────────────────────────────────────

class TestActions:
    d = {"name": "Kitchen Echo", "serial": "G0911", "type": "T"}

    def test_speak_strips_text(self):
        assert act.speak(self.d, "  hi  ")["text"] == "hi"

    def test_empty_text_rejected(self):
        with pytest.raises(act.ActionError):
            act.speak(self.d, "   ")

    def test_long_text_rejected(self):
        with pytest.raises(act.ActionError, match="limit"):
            act.speak(self.d, "x" * (act.MAX_TEXT + 1))

    def test_sequence_maps_to_amazon_name(self):
        assert act.sequence(self.d, "Weather")["sequence"] == "Alexa.Weather.Play"

    def test_sequence_unknown(self):
        with pytest.raises(act.ActionError, match="Choose from"):
            act.sequence(self.d, "dance")

    def test_music_provider_mapping(self):
        a = act.music(self.d, "jazz", "spotify", 60)
        assert a["provider"] == "SPOTIFY" and a["timer"] == 60

    def test_music_bad_timer(self):
        with pytest.raises(act.ActionError):
            act.music(self.d, "jazz", "amazon", 0)

    @pytest.mark.parametrize("level", [-1, 101, 5.5])
    def test_volume_range(self, level):
        with pytest.raises(act.ActionError):
            act.volume(self.d, level)

    def test_announce_needs_targets(self):
        with pytest.raises(act.ActionError):
            act.announce([], "hello")

    def test_light_validation(self):
        with pytest.raises(act.ActionError):
            act.light("", True)
        with pytest.raises(act.ActionError):
            act.light("e1", True, brightness=150)
        assert act.light(" e1 ", False)["entity_id"] == "e1"

    def test_describe_reduces_devices(self):
        out = act.describe(act.announce([self.d, self.d], "hi"))
        assert out["devices"] == [{"name": "Kitchen Echo", "serial": "G0911"}] * 2


# ── smart home ───────────────────────────────────────────────────────

def test_flatten_network_nested():
    payload = {"locationDetails": {"Default_Location": {"amazonBridgeDetails": {"amazonBridgeDetails": {
        "LambdaBridge_1": {"applianceDetails": {"applianceDetails": {
            "A1": {"applianceId": "A1", "friendlyName": "Desk Lamp", "entityId": "ent-1",
                   "applianceTypes": ["LIGHT"], "manufacturerName": "Philips", "isReachable": True},
            "A2": {"applianceId": "A2", "friendlyName": "Fan Plug", "entityId": "ent-2",
                   "applianceTypes": ["SMARTPLUG"], "connectivity": {"value": "UNREACHABLE"}},
        }}}}}}}}
    items = sh.flatten_network(payload)
    assert [i["name"] for i in items] == ["Desk Lamp", "Fan Plug"]
    assert items[0]["entity_id"] == "ent-1" and items[0]["reachable"] is True
    assert items[1]["reachable"] is False


# ── account storage ──────────────────────────────────────────────────

def test_account_saved_owner_only(home):
    backend.save_account({"email": "a@b.c", "domain": "amazon.com", "oauth": {}})
    mode = stat.S_IMODE(os.stat(home / "account.json").st_mode)
    assert mode == 0o600
    assert backend.load_account()["email"] == "a@b.c"
    assert backend.delete_account() is True
    assert backend.load_account() is None


# ── CLI (backend mocked) ─────────────────────────────────────────────

class TestCLI:
    def test_status_logged_out(self, home):
        result, data = run("auth", "status")
        assert result.exit_code == 0 and data == {"logged_in": False}

    def test_device_list_json(self, fake_backend):
        result, data = run("device", "list")
        assert result.exit_code == 0
        assert [d["name"] for d in data] == ["Bedroom Echo", "Kitchen Echo", "Living Room Echo Show"]
        assert "capabilities" not in data[0]

    def test_speak_sends_action(self, fake_backend):
        result, data = run("speak", "kitchen", "Dinner is ready")
        assert result.exit_code == 0 and data["ok"] is True
        assert fake_backend[0]["op"] == "speak" and fake_backend[0]["device"]["serial"] == "G0911"

    def test_command_sends_text(self, fake_backend):
        run("command", "living", "turn off the lights")
        assert fake_backend[0] == {**fake_backend[0], "op": "command", "text": "turn off the lights"}

    def test_announce_defaults_to_online_speakers(self, fake_backend):
        result, data = run("announce", "Leaving now")
        serials = [d["serial"] for d in data["action"]["devices"]]
        assert serials == ["G0911", "G0922"]  # Bedroom is offline, app excluded

    def test_announce_explicit_targets(self, fake_backend):
        result, data = run("announce", "hi", "-d", "bedroom", "-d", "kitchen")
        assert [d["serial"] for d in data["action"]["devices"]] == ["G0933", "G0911"]

    def test_ambiguous_device_error_code(self, fake_backend):
        result, data = run("speak", "echo", "hi")
        assert result.exit_code == 1 and data["error"] == "ambiguous_device"
        assert fake_backend == []

    def test_not_logged_in_error_code(self, home):
        result, data = run("speak", "kitchen", "hi")
        assert result.exit_code == 1 and data["error"] == "not_logged_in"

    def test_volume_out_of_range_is_usage_error(self, fake_backend):
        result = CliRunner().invoke(alexa_cli.cli, ["volume", "kitchen", "150"])
        assert result.exit_code == 2 and fake_backend == []

    def test_music_resume_maps_to_play_op(self, fake_backend):
        run("music", "resume", "kitchen")
        assert fake_backend[0]["op"] == "media" and fake_backend[0]["media_op"] == "play"

    def test_sequence_choice(self, fake_backend):
        result, data = run("sequence", "kitchen", "joke")
        assert data["action"]["sequence"] == "Alexa.Joke.Play"

    def test_dry_run_uses_cache_and_sends_nothing(self, fake_backend, monkeypatch):
        run("device", "list")  # populates cache
        monkeypatch.setattr(backend, "fetch_devices", lambda: pytest.fail("network used in dry run"))
        result, data = run("--dry-run", "speak", "kitchen", "hi")
        assert result.exit_code == 0 and data["dry_run"] is True and data["action"]["device"]["serial"] == "G0911"
        assert fake_backend == []

    def test_dry_run_without_cache_fails_cleanly(self, home):
        result = CliRunner().invoke(alexa_cli.cli, ["--json", "--dry-run", "speak", "kitchen", "hi"])
        assert result.exit_code == 1 and json.loads(result.output)["error"] == "device_not_found"

    def test_logout(self, fake_backend, home):
        result, data = run("auth", "logout")
        assert data["removed"] is True and not (home / "account.json").exists()

    def test_locale(self, fake_backend):
        run("auth", "locale", "en-GB")
        assert backend.load_account()["locale"] == "en-GB"


# ── backend dispatch (fake alexapy, checks the real method names/args) ─

class _FakeAPI:
    calls = []

    def __init__(self, device, login):
        self.device = device

    def __getattr__(self, name):
        async def _call(*args, **kwargs):
            _FakeAPI.calls.append((name, self.device.device_serial_number, args, kwargs))
        return _call

    @staticmethod
    async def set_light_state(login, entity_id, **kwargs):
        _FakeAPI.calls.append(("set_light_state", None, (entity_id,), kwargs))
        return {"ok": True}


class _FakeAlexapy:
    AlexaAPI = _FakeAPI


@pytest.mark.parametrize("action,expected", [
    (act.speak({"serial": "S1", "type": "T"}, "hi"), ("send_tts", ("hi",))),
    (act.command({"serial": "S1", "type": "T"}, "lights off"), ("run_custom", ("lights off",))),
    (act.routine({"serial": "S1", "type": "T"}, "good night"), ("run_routine", ("good night",))),
    (act.sequence({"serial": "S1", "type": "T"}, "joke"), ("send_sequence", ("Alexa.Joke.Play",))),
    (act.music({"serial": "S1", "type": "T"}, "jazz", "spotify"), ("play_music", ("SPOTIFY", "jazz"))),
    (act.volume({"serial": "S1", "type": "T"}, 40), ("set_volume", (0.4,))),
    (act.media({"serial": "S1", "type": "T"}, "pause"), ("pause", ())),
    (act.media({"serial": "S1", "type": "T"}, "stop"), ("stop", ())),
])
def test_execute_dispatch(monkeypatch, action, expected):
    import asyncio
    import alexapy
    _FakeAPI.calls = []
    monkeypatch.setattr(backend, "_alexapy", lambda: _FakeAlexapy)
    asyncio.run(backend._execute(object(), {"locale": "en-GB"}, action))
    name, serial, args, kwargs = _FakeAPI.calls[0]
    assert (name, args) == expected and serial == "S1"
    assert hasattr(alexapy.AlexaAPI, name), f"alexapy has no AlexaAPI.{name}"


def test_execute_announce_targets_all(monkeypatch):
    import asyncio
    _FakeAPI.calls = []
    monkeypatch.setattr(backend, "_alexapy", lambda: _FakeAlexapy)
    devs = [{"serial": "S1", "type": "T"}, {"serial": "S2", "type": "T"}]
    asyncio.run(backend._execute(object(), {}, act.announce(devs, "hello", "Note")))
    name, serial, args, kwargs = _FakeAPI.calls[0]
    assert name == "send_announcement" and kwargs["targets"] == ["S1", "S2"] and kwargs["title"] == "Note"


def test_execute_light(monkeypatch):
    import asyncio
    _FakeAPI.calls = []
    monkeypatch.setattr(backend, "_alexapy", lambda: _FakeAlexapy)
    asyncio.run(backend._execute(object(), {}, act.light("ent-1", False, 30)))
    assert _FakeAPI.calls[0][0] == "set_light_state" and _FakeAPI.calls[0][3]["power_on"] is False


# ── login robustness: busy ports and missing CA certificates ──────────

def test_choose_port_picks_free_port_by_default():
    port = backend.choose_port(None)
    assert 1024 <= port <= 65535 and not backend.port_in_use(port)


def test_choose_port_rejects_port_used_by_another_app():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        busy = s.getsockname()[1]
        with pytest.raises(RuntimeError, match="already used by another app"):
            backend.choose_port(busy)


def test_certifi_bundle_used_when_unset(monkeypatch):
    import certifi
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    backend.use_certifi_bundle()
    assert os.environ["SSL_CERT_FILE"] == certifi.where()


def test_certifi_bundle_respects_user_setting(monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", "/custom/ca.pem")
    backend.use_certifi_bundle()
    assert os.environ["SSL_CERT_FILE"] == "/custom/ca.pem"


def test_cert_error_becomes_actionable_message():
    import ssl

    async def boom():
        try:
            raise ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer")
        except ssl.SSLCertVerificationError as inner:
            raise ConnectionError("Cannot connect to host api.amazon.com:443") from inner

    with pytest.raises(RuntimeError, match="Install Certificates.command"):
        backend.run(boom)


def test_cli_login_busy_port_is_clean_json_error(home):
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        busy = s.getsockname()[1]
        result = CliRunner().invoke(alexa_cli.cli, ["--json", "auth", "login", "--email", "a@b.c",
                                                    "--port", str(busy)])
    data = json.loads(result.output)
    assert result.exit_code == 1 and data["error"] == "runtime_error" and "already used" in data["message"]


# ── Amazon site (domain) handling ────────────────────────────────────

@pytest.mark.parametrize("domain,locale", [("amazon.co.uk", "en-GB"), ("amazon.de", "de-DE"),
                                           ("amazon.in", "en-IN"), ("amazon.com", "en-US"),
                                           ("amazon.example", "en-US")])
def test_locale_for_domain(domain, locale):
    assert backend.locale_for(domain) == locale


def test_domain_warning_only_on_mismatch():
    base = {"email": "a@b.c", "domain": "amazon.com"}
    assert backend.domain_warning(base) is None
    assert backend.domain_warning({**base, "reported_domain": "amazon.com"}) is None
    msg = backend.domain_warning({**base, "reported_domain": "amazon.co.uk"})
    assert "--domain amazon.co.uk" in msg and "auth logout" in msg


def test_cli_surfaces_domain_warning(fake_backend):
    account = backend.load_account()
    backend.save_account({**account, "reported_domain": "amazon.co.uk"})
    result, data = run("speak", "kitchen", "hi")
    assert data["ok"] is True and "--domain amazon.co.uk" in data["warning"]
    human = CliRunner().invoke(alexa_cli.cli, ["speak", "kitchen", "hi"])
    assert "Warning: Your Amazon account is on amazon.co.uk" in human.output


# ── fixes from the Codex review of HKUDS/CLI-Anything#649 ─────────────

GROUP = {"accountName": "Downstairs Speakers", "serialNumber": "GRP1", "deviceType": "A3C9PE6TNYLTCH",
         "deviceFamily": "WHA", "online": True, "capabilities": ["VOLUME_SETTING", "AUDIO_PLAYER"]}


@pytest.fixture
def fake_backend_with_group(fake_backend, monkeypatch):
    monkeypatch.setattr(backend, "fetch_devices", lambda: RAW_DEVICES + [GROUP])
    return fake_backend


def test_group_is_listed_but_not_a_speaker():
    g = dev.normalize(GROUP)
    assert g["is_group"] is True and g["is_speaker"] is False
    assert dev.filter_devices([g]) == [g]


def test_announce_default_skips_groups(fake_backend_with_group):
    result, data = run("announce", "hi")
    assert "GRP1" not in [d["serial"] for d in data["action"]["devices"]]


def test_music_can_target_group(fake_backend_with_group):
    result, data = run("music", "play", "downstairs", "jazz")
    assert data["ok"] is True and fake_backend_with_group[0]["device"]["serial"] == "GRP1"


def test_actions_ignore_alexa_apps(fake_backend):
    # "this device" only matches the Alexa app, which is not a valid target.
    result, data = run("speak", "this device", "hi")
    assert result.exit_code == 1 and data["error"] == "device_not_found"
    result, data = run("device", "info", "this device")
    assert data["family"] == "VOX"  # still inspectable


def test_cached_without_cache_does_not_call_amazon(home, monkeypatch):
    backend.save_account({"email": "a@b.c", "domain": "amazon.com", "oauth": {"refresh_token": "x"}})
    monkeypatch.setattr(backend, "fetch_devices", lambda: pytest.fail("--cached must not fetch"))
    result, data = run("device", "list", "--cached")
    assert result.exit_code == 1 and data["error"] == "device_not_found" and "--cached" in data["message"]


def test_unexpected_backend_error_is_json(fake_backend, monkeypatch):
    def boom(action):
        raise ConnectionResetError("connection reset by peer")
    monkeypatch.setattr(backend, "execute", boom)
    result, data = run("speak", "kitchen", "hi")
    assert result.exit_code == 1 and data["error"] == "backend_error" and "ConnectionResetError" in data["message"]


def test_logout_dry_run_keeps_credentials(fake_backend, home):
    result, data = run("--dry-run", "auth", "logout")
    assert data["dry_run"] is True and data["would_remove"] is True
    assert (home / "account.json").exists()


def test_login_dry_run_starts_nothing(home, monkeypatch):
    monkeypatch.setattr(backend, "login", lambda *a, **k: pytest.fail("login must not run in dry run"))
    result, data = run("--dry-run", "auth", "login", "--email", "a@b.c", "--domain", "amazon.de")
    assert data["dry_run"] is True and data["locale"] == "de-DE"


def test_repl_keeps_dry_run_and_json(fake_backend, monkeypatch):
    run("device", "list")  # cache for dry run
    from cli_anything.alexa.utils import repl_skin

    lines = iter(["speak kitchen hello", "quit"])
    monkeypatch.setattr(repl_skin.ReplSkin, "create_prompt_session", lambda self: None)
    monkeypatch.setattr(repl_skin.ReplSkin, "get_input", lambda self, *a, **k: next(lines))
    result = CliRunner().invoke(alexa_cli.cli, ["--json", "--dry-run", "repl"])
    assert '"dry_run": true' in result.output
    assert fake_backend == []  # nothing sent to Amazon from the REPL


# ── second Codex review round (commit 9a7f2fc) ────────────────────────

@pytest.mark.parametrize("domain,ok", [("amazon.com", True), ("amazon.co.uk", True), ("amazon.com.au", True),
                                       ("amazon.de", True), ("AMAZON.IN", True), ("evil.example", False),
                                       ("amazon.com.evil.io", False), ("", False)])
def test_valid_domain(domain, ok):
    assert backend.valid_domain(domain) is ok


def test_login_rejects_non_amazon_domain(home, monkeypatch):
    monkeypatch.setattr(backend, "login", lambda *a, **k: pytest.fail("must not start login"))
    result = CliRunner().invoke(alexa_cli.cli, ["auth", "login", "--email", "a@b.c", "--domain", "evil.example"])
    assert result.exit_code == 2 and "not an Amazon domain" in result.output


def test_locale_dry_run_does_not_write(fake_backend):
    result, data = run("--dry-run", "auth", "locale", "fr-FR")
    assert data["would_set_locale"] == "fr-FR" and backend.load_account().get("locale") != "fr-FR"


@pytest.mark.parametrize("args,fetcher", [(["routine", "list"], "fetch_routines"),
                                          (["smarthome", "list"], "fetch_network"),
                                          (["auth", "status", "--verify"], "verify")])
def test_read_commands_do_not_contact_amazon_in_dry_run(fake_backend, monkeypatch, args, fetcher):
    monkeypatch.setattr(backend, fetcher, lambda *a, **k: pytest.fail(f"{fetcher} called in dry run"))
    result, data = run("--dry-run", *args)
    assert result.exit_code == 0


# ── third Codex review round (commit 5392bed) ─────────────────────────

def test_config_dir_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ALEXA_CLI_HOME", "~/alexa-home")
    assert backend.config_dir() == tmp_path / "alexa-home"


def test_concurrent_account_saves_stay_valid(home):
    import threading
    errors = []

    def worker(i):
        try:
            for j in range(30):
                backend.save_account({"email": "a@b.c", "domain": "amazon.com", "n": i * 100 + j})
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert backend.load_account()["email"] == "a@b.c"  # file is complete JSON
    assert not list(home.glob(".account.*.tmp"))  # no temp files left behind
    assert stat.S_IMODE(os.stat(home / "account.json").st_mode) == 0o600


# ── fourth Codex review round (commit 3c47279) ────────────────────────

@pytest.mark.parametrize("args", [["speak", "downstairs", "hi"], ["command", "downstairs", "lights off"],
                                  ["sequence", "downstairs", "joke"], ["routine", "run", "downstairs", "bedtime"],
                                  ["announce", "hi", "-d", "downstairs"]])
def test_speech_commands_reject_speaker_groups(fake_backend_with_group, args):
    result, data = run(*args)
    assert result.exit_code == 1 and data["error"] == "device_not_found"
    assert fake_backend_with_group == []


@pytest.mark.parametrize("args", [["music", "pause", "downstairs"], ["volume", "downstairs", "20"]])
def test_media_commands_accept_speaker_groups(fake_backend_with_group, args):
    result, data = run(*args)
    assert data["ok"] is True and fake_backend_with_group[0]["device"]["serial"] == "GRP1"


def test_device_cache_written_atomically(home):
    import threading
    devices = [dev.normalize(d) for d in RAW_DEVICES]
    stop = threading.Event()
    bad = []

    def reader():
        while not stop.is_set():
            try:
                data = backend.cached_devices()
            except json.JSONDecodeError as exc:  # half-written file
                bad.append(exc)
                return
            assert data in (None, devices)

    t = threading.Thread(target=reader)
    t.start()
    for _ in range(200):
        backend.cache_devices(devices)
    stop.set()
    t.join()
    assert bad == [] and backend.cached_devices() == devices
    assert not list(home.glob(".devices.*.tmp"))


# ── fifth Codex review round (commit 56dbaed) ─────────────────────────

def test_failure_output_keeps_domain_warning(fake_backend):
    account = backend.load_account()
    backend.save_account({**account, "reported_domain": "amazon.co.uk"})
    result, data = run("speak", "garage", "hi")  # unknown device -> fail()
    assert result.exit_code == 1 and data["error"] == "device_not_found"
    assert "--domain amazon.co.uk" in data["warning"]
    human = CliRunner().invoke(alexa_cli.cli, ["speak", "garage", "hi"])
    assert "Warning: Your Amazon account is on amazon.co.uk" in human.output


# ── sixth Codex review round (commit 5585375) ─────────────────────────

def test_list_json_warning_goes_to_stderr(fake_backend):
    account = backend.load_account()
    backend.save_account({**account, "reported_domain": "amazon.co.uk"})
    result = CliRunner().invoke(alexa_cli.cli, ["--json", "device", "list"])
    stdout = result.stdout
    assert isinstance(json.loads(stdout), list)  # stdout stays a JSON list
    assert "--domain amazon.co.uk" in result.stderr


def test_empty_cache_is_valid(home, monkeypatch):
    backend.save_account({"email": "a@b.c", "domain": "amazon.com", "oauth": {"refresh_token": "x"}})
    backend.cache_devices([])
    monkeypatch.setattr(backend, "fetch_devices", lambda: pytest.fail("--cached must not fetch"))
    result, data = run("device", "list", "--cached")
    assert result.exit_code == 0 and data == []


def test_missing_cache_is_none(home):
    assert backend.cached_devices() is None


# ── seventh Codex review round (commit f493d03) ───────────────────────

def test_actions_act_as_device_owner(monkeypatch):
    import asyncio
    _FakeAPI.calls = []
    monkeypatch.setattr(backend, "_alexapy", lambda: _FakeAlexapy)
    shared = {"serial": "S9", "type": "T", "owner_customer_id": "OWNER2"}
    asyncio.run(backend._execute(object(), {}, act.speak(shared, "hi")))
    assert _FakeAPI.calls[0][3]["customer_id"] == "OWNER2"
    _FakeAPI.calls = []
    asyncio.run(backend._execute(object(), {}, act.speak({"serial": "S1", "type": "T"}, "hi")))
    assert _FakeAPI.calls[0][3]["customer_id"] is None  # alexapy falls back to the logged-in user


def test_session_closed_when_startup_raises(home, monkeypatch):
    import asyncio
    closed = []

    class FakeLogin:
        customer_id = "C"

        def __init__(self, **kw):
            pass

        async def load_cookie(self):
            return {}

        async def login(self, cookies=None):
            raise ConnectionError("network down")

        async def close(self):
            closed.append(True)

    class FakeAlexapy:
        AlexaLogin = FakeLogin

    monkeypatch.setattr(backend, "_alexapy", lambda: FakeAlexapy)
    backend.save_account({"email": "a@b.c", "domain": "amazon.com", "oauth": {"refresh_token": "x"}})
    with pytest.raises(ConnectionError):
        asyncio.run(backend._open_session())
    assert closed == [True]


# ── eighth Codex review round (commit 52aabb8) ────────────────────────

def test_device_cache_scoped_to_account(fake_backend):
    run("device", "list")  # cached for a@b.c
    assert backend.cached_devices()
    backend.save_account({"email": "other@b.c", "domain": "amazon.com", "oauth": {"refresh_token": "y"}})
    assert backend.cached_devices() is None  # other account's devices never reused
    result, data = run("--dry-run", "speak", "kitchen", "hi")
    assert result.exit_code == 1 and data["error"] == "device_not_found"


def test_logout_removes_device_cache(fake_backend, home):
    run("device", "list")
    run("auth", "logout")
    assert not (home / "devices.json").exists()


def test_session_start_does_not_resurrect_logged_out_account(home, monkeypatch):
    import asyncio

    class FakeLogin:
        customer_id = "C"
        access_token = refresh_token = mac_dms = expires_in = None
        saved = []

        def __init__(self, **kw):
            pass

        async def load_cookie(self):
            return {}

        async def login(self, cookies=None):
            backend.delete_account()  # `auth logout` runs meanwhile

        async def test_loggedin(self, rebuild_session=True):
            return True

        async def save_cookiefile(self):
            FakeLogin.saved.append(True)

        async def close(self):
            pass

    class FakeAlexapy:
        AlexaLogin = FakeLogin

    monkeypatch.setattr(backend, "_alexapy", lambda: FakeAlexapy)
    backend.save_account({"email": "a@b.c", "domain": "amazon.com", "oauth": {"refresh_token": "x"}})
    with pytest.raises(backend.NotLoggedIn, match="Logged out"):
        asyncio.run(backend._open_session())
    assert backend.load_account() is None and FakeLogin.saved == []


def test_json_repl_keeps_stdout_pure_json(fake_backend, monkeypatch):
    run("device", "list")
    from cli_anything.alexa.utils import repl_skin
    lines = iter(["help", "speak kitchen hello", "quit"])
    monkeypatch.setattr(repl_skin.ReplSkin, "create_prompt_session", lambda self: None)
    monkeypatch.setattr(repl_skin.ReplSkin, "get_input", lambda self, *a, **k: next(lines))
    result = CliRunner().invoke(alexa_cli.cli, ["--json", "--dry-run", "repl"])
    assert json.loads(result.stdout)["dry_run"] is True  # only the command's JSON on stdout
    assert result.stderr.strip()  # banner/help/goodbye went to stderr


# ── ninth Codex review round (commit 78b2af0) ─────────────────────────

def test_login_cleans_up_when_proxy_fails_to_start(home, monkeypatch):
    import asyncio
    closed = []

    class FakeLogin:
        def __init__(self, **kw):
            pass

        async def close(self):
            closed.append("login")

    class FakeProxy:
        active = False

        def __init__(self, login, url):
            pass

        async def start_proxy(self, host=None):
            raise OSError("address already in use")

        async def stop_proxy(self):
            closed.append("proxy")

    class FakeAlexapy:
        AlexaLogin = FakeLogin
        AlexaProxy = FakeProxy

    monkeypatch.setattr(backend, "_alexapy", lambda: FakeAlexapy)
    with pytest.raises(OSError):
        asyncio.run(backend._login_via_proxy("a@b.c", "amazon.com", 9, 5, lambda url: None))
    assert closed == ["login"]  # session closed; proxy that never started is not stopped


def test_json_repl_usage_errors_are_json(fake_backend, monkeypatch):
    from cli_anything.alexa.utils import repl_skin
    lines = iter(["volume kitchen 150", "quit"])
    monkeypatch.setattr(repl_skin.ReplSkin, "create_prompt_session", lambda self: None)
    monkeypatch.setattr(repl_skin.ReplSkin, "get_input", lambda self, *a, **k: next(lines))
    result = CliRunner().invoke(alexa_cli.cli, ["--json", "repl"])
    data = json.loads(result.stdout)
    assert data["ok"] is False and data["error"] == "usage_error"
    assert fake_backend == []
