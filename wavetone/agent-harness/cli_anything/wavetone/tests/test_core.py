from __future__ import annotations

import json
import subprocess
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from cli_anything.wavetone import wavetone_cli as cli_module
from cli_anything.wavetone.core import audio as audio_core
from cli_anything.wavetone.core.audio import probe_audio
from cli_anything.wavetone.core.project import (
    DEFAULT_ANALYSIS_SETTINGS,
    add_label,
    create_project,
    load_project,
    save_project,
    set_tempo,
    update_analysis,
)
from cli_anything.wavetone.core.session import append_event, load_events
from cli_anything.wavetone.tests.helpers import make_wav
from cli_anything.wavetone.utils import wavetone_backend
from cli_anything.wavetone.utils.repl_skin import ReplSkin
from cli_anything.wavetone.wavetone_cli import _split_repl_args, cli


def test_create_project_manifest(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav, name="Tone Test")

    assert project["schema_version"] == "wavetone-project/v1"
    assert project["project"]["name"] == "Tone Test"
    assert project["audio"]["path"] == str(wav.resolve())
    assert project["analysis"] == DEFAULT_ANALYSIS_SETTINGS


def test_rejects_unsupported_audio(tmp_path: Path) -> None:
    txt = tmp_path / "not-audio.txt"
    txt.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        create_project(txt)


def test_save_load_project_roundtrip(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    add_label(project, "chorus", 12.5)
    set_tempo(project, 128, first_bar_time_seconds=0.2)
    output = save_project(project, tmp_path / "project.json")

    loaded = load_project(output)
    assert loaded["labels"][0]["name"] == "chorus"
    assert loaded["tempo"]["bpm"] == 128
    assert loaded["tempo"]["first_bar_time_seconds"] == 0.2


def test_labels_are_sorted(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    add_label(project, "late", 4.0)
    add_label(project, "early", 1.0)
    add_label(project, "middle", "2.5")

    assert [label["name"] for label in project["labels"]] == ["early", "middle", "late"]


def test_update_analysis_settings(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    update_analysis(project, channel="L+R", blocks_per_second=24, analyze_fundamental_frequency=False)

    assert project["analysis"]["channel"] == "L+R"
    assert project["analysis"]["blocks_per_second"] == 24
    assert project["analysis"]["analyze_fundamental_frequency"] is False


def test_cli_analysis_preserves_omitted_boolean_flags(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    project["analysis"]["analyze_fundamental_frequency"] = True
    project["analysis"]["skip_analysis_dialog"] = True
    project_path = save_project(project, tmp_path / "tone.wt.json")

    result = CliRunner().invoke(cli, ["--json", "project", "analysis", "--channel", "R", str(project_path)])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["analysis"]["channel"] == "R"
    assert data["analysis"]["analyze_fundamental_frequency"] is True
    assert data["analysis"]["skip_analysis_dialog"] is True

    loaded = load_project(project_path)
    assert loaded["analysis"]["channel"] == "R"
    assert loaded["analysis"]["analyze_fundamental_frequency"] is True
    assert loaded["analysis"]["skip_analysis_dialog"] is True


def test_cli_attach_wfd_requires_existing_wfd_file(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project_path = save_project(create_project(wav), tmp_path / "tone.wt.json")

    missing = tmp_path / "missing.wfd"
    result = CliRunner().invoke(cli, ["--project", str(project_path), "project", "attach-wfd", str(missing)])
    assert result.exit_code != 0
    assert "does not exist" in result.output

    wrong_suffix = tmp_path / "analysis.txt"
    wrong_suffix.write_text("wfd", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--project", str(project_path), "project", "attach-wfd", str(wrong_suffix)])
    assert result.exit_code == 1
    assert ".wfd" in result.output

    wfd_path = tmp_path / "analysis.wfd"
    wfd_path.write_text("wfd", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--project", str(project_path), "--json", "project", "attach-wfd", str(wfd_path)])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["wfd_path"] == str(wfd_path.resolve())


def test_rejects_non_finite_project_numbers(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)

    with pytest.raises(ValueError, match="BPM.*finite"):
        set_tempo(project, float("nan"))

    with pytest.raises(ValueError, match="reference_frequency_hz.*finite"):
        update_analysis(project, reference_frequency_hz=float("inf"))


def test_load_project_rejects_non_object_json(tmp_path: Path) -> None:
    project_path = tmp_path / "broken.wt.json"
    project_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_project(project_path)


def test_probe_wav_metadata(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav", duration=0.5, sample_rate=16000)
    info = probe_audio(wav)

    assert info["probe_method"] == "python-wave"
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert info["duration_seconds"] == 0.5
    assert info["size_bytes"] > 0


def test_probe_malformed_wav_falls_back_to_stat(tmp_path: Path) -> None:
    wav = tmp_path / "broken.wav"
    wav.write_bytes(b"")

    info = probe_audio(wav)

    assert info["probe_method"] == "stat"
    assert info["format"] == "wav"
    assert info["duration_seconds"] is None
    assert info["size_bytes"] == 0


def test_ffprobe_uses_single_show_entries_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "tone.mp3"
    audio.write_bytes(b"mp3")
    captured: dict[str, list[str]] = {}

    monkeypatch.setattr(audio_core.shutil, "which", lambda name: "ffprobe")

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "mp3",
                        "sample_rate": "44100",
                        "channels": "2",
                    }
                ],
                "format": {
                    "duration": "1.25",
                    "format_name": "mp3",
                    "bit_rate": "128000",
                    "size": "3",
                },
            }
        )
        return subprocess.CompletedProcess(args, 0, stdout=stdout)

    monkeypatch.setattr(audio_core.subprocess, "run", fake_run)

    info = audio_core._probe_ffprobe(audio)
    entries = captured["args"][captured["args"].index("-show_entries") + 1]

    assert captured["args"].count("-show_entries") == 1
    assert "stream=codec_type,codec_name,sample_rate,channels" in entries
    assert ":format=duration,format_name,bit_rate,size" in entries
    assert info["probe_method"] == "ffprobe"
    assert info["sample_rate"] == 44100
    assert info["channels"] == 2


def test_ffprobe_handles_non_numeric_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "tone.mp3"
    audio.write_bytes(b"mp3")

    monkeypatch.setattr(audio_core.shutil, "which", lambda name: "ffprobe")

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = json.dumps(
            {
                "streams": [{"codec_type": "audio", "sample_rate": "N/A"}],
                "format": {
                    "duration": "N/A",
                    "format_name": "mp3",
                    "bit_rate": "N/A",
                    "size": "N/A",
                },
            }
        )
        return subprocess.CompletedProcess(args, 0, stdout=stdout)

    monkeypatch.setattr(audio_core.subprocess, "run", fake_run)

    info = audio_core._probe_ffprobe(audio)

    assert info["duration_seconds"] is None
    assert info["sample_rate"] is None
    assert info["bit_rate"] is None
    assert info["size_bytes"] == audio.stat().st_size


def test_session_event_log(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    append_event(session_path, "created", {"project": "demo"})
    append_event(session_path, "launched", {"pid": 123})

    events = load_events(session_path)
    assert [event["event"] for event in events] == ["created", "launched"]


def test_session_rejects_invalid_schema(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        append_event(session_path, "created", {})

    session_path.write_text(json.dumps({"events": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="events.*list"):
        load_events(session_path)

    session_path.unlink()

    with pytest.raises(ValueError, match="finite"):
        append_event(session_path, "bad", {"value": float("nan")})

    assert not session_path.exists()


def test_find_wavetone_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "wavetone.exe"
    fake.write_bytes(b"MZ")
    monkeypatch.setenv("WAVETONE_EXE", str(fake))

    assert wavetone_backend.find_wavetone() == fake.resolve()


def test_doctor_rejects_required_data_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "wavetone"
    data_dir = root / "data"
    help_dir = root / "wthelp"
    data_dir.mkdir(parents=True)
    help_dir.mkdir()
    exe = root / "wavetone.exe"
    exe.write_bytes(b"MZ")

    directory_artifact = wavetone_backend.REQUIRED_DATA_FILES[0]
    for filename in wavetone_backend.REQUIRED_DATA_FILES:
        path = data_dir / filename
        if filename == directory_artifact:
            path.mkdir()
        else:
            path.write_bytes(b"x")

    monkeypatch.setenv("WAVETONE_EXE", str(exe))
    monkeypatch.setattr(wavetone_backend.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wavetone_backend.platform, "platform", lambda: "Windows-test")

    status = wavetone_backend.doctor()
    artifact = next(check for check in status["checks"] if check["name"] == f"data/{directory_artifact}")

    assert status["ready"] is False
    assert artifact["ok"] is False


def test_cli_preserves_inherited_project_and_json_context(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project_path = save_project(create_project(wav), tmp_path / "tone.wt.json")

    result = CliRunner().invoke(
        cli,
        ["audio", "probe"],
        obj={"project": str(project_path), "json": True},
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["audio"]["path"] == str(wav.resolve())


def test_wavetone_launch_fails_on_early_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_launch_wavetone(**kwargs: object) -> dict[str, object]:
        return {
            "backend": "wavetone.exe",
            "executable": "C:/fake/wavetone.exe",
            "running_after_wait": False,
            "terminated": False,
            "exit_code": 42,
        }

    monkeypatch.setattr(wavetone_backend, "launch_wavetone", fake_launch_wavetone)

    result = CliRunner().invoke(cli, ["--json", "wavetone", "launch", "--wait", "1"])

    assert result.exit_code == 42
    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["launch"]["exit_code"] == 42


def test_wavetone_launch_reports_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_launch_wavetone(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("WaveTone launch requires Windows")

    monkeypatch.setattr(wavetone_backend, "launch_wavetone", fake_launch_wavetone)

    result = CliRunner().invoke(cli, ["--json", "wavetone", "launch"])

    assert result.exit_code == 1
    assert "WaveTone launch requires Windows" in result.output
    assert "Traceback" not in result.output


def test_launch_requires_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wavetone_backend.platform, "system", lambda: "Linux")

    with pytest.raises(RuntimeError, match="requires Windows"):
        wavetone_backend.launch_wavetone()


def test_repl_split_strips_windows_quotes() -> None:
    line = 'project new "C:\\Users\\me\\My Music\\song.wav" -o "C:\\Users\\me\\song.wt.json"'

    assert _split_repl_args(line) == [
        "project",
        "new",
        "C:\\Users\\me\\My Music\\song.wav",
        "-o",
        "C:\\Users\\me\\song.wt.json",
    ]


def test_repl_skin_uses_wavetone_branding_and_local_skill_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# WaveTone", encoding="utf-8")
    skin = ReplSkin("WaveTone", version="test", history_file=str(tmp_path / "history"), skill_path=str(skill_path))

    skin.print_banner()
    output = capsys.readouterr().out

    assert skin.display_name == "WaveTone"
    assert "WaveTone" in output
    assert "Local skill:" in output
    assert "SKILL.md" in output


def test_repl_reports_click_exit_without_unexpected_error(monkeypatch: pytest.MonkeyPatch) -> None:
    errors: list[str] = []
    inputs = iter(["wavetone launch", "exit"])

    class FakeSkin:
        def __init__(self, name: str, version: str) -> None:
            self.name = name
            self.version = version

        def print_banner(self) -> None:
            return None

        def info(self, message: str) -> None:
            return None

        def create_prompt_session(self) -> object:
            return object()

        def get_input(self, prompt_session: object, project_name: str, modified: bool) -> str:
            return next(inputs)

        def error(self, message: str) -> None:
            errors.append(message)

        def print_goodbye(self) -> None:
            return None

    def fake_main(**kwargs: object) -> None:
        raise click.exceptions.Exit(1)

    monkeypatch.setattr(cli_module, "ReplSkin", FakeSkin)
    monkeypatch.setattr(cli_module.cli, "main", fake_main)

    result = CliRunner().invoke(cli_module.repl, [], obj={"json": False})

    assert result.exit_code == 0, result.output
    assert errors == ["Command exited with code 1"]
