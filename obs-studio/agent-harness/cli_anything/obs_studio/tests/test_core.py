"""Unit tests for the OBS Studio CLI harness."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cli_anything.obs_studio.core import filters as filter_mod
from cli_anything.obs_studio.core import output as output_mod
from cli_anything.obs_studio.core import project as project_mod
from cli_anything.obs_studio.core import scenes as scene_mod
from cli_anything.obs_studio.core import sources as source_mod
from cli_anything.obs_studio.core.session import Session
from cli_anything.obs_studio.obs_studio_cli import cli


class TestSession:
    def test_new_save_open_roundtrip(self, tmp_path: Path):
        session = Session()
        project_mod.new_project(session, "stream")
        save_path = tmp_path / "stream.json"
        session.save_project(str(save_path))

        reopened = Session()
        reopened.open_project(str(save_path))

        assert reopened.state is not None
        assert reopened.state["name"] == "stream"
        assert reopened.status()["project_open"] is True

    def test_undo_redo(self):
        session = Session()
        project_mod.new_project(session, "stream")
        scene_mod.add_scene(session, "Gameplay")
        assert session.undo() is True
        assert len(session.state["scenes"]) == 1
        assert session.redo() is True
        assert len(session.state["scenes"]) == 2


class TestCoreModules:
    def test_scene_source_filter_output_flow(self):
        session = Session()
        project_mod.new_project(session, "stream")
        scene_mod.add_scene(session, "Gameplay")
        scene_mod.select_scene(session, "Gameplay")

        add_source = source_mod.add_source(
            session,
            source_type="video_capture",
            name="Webcam",
            settings=("device=Logitech C920",),
        )
        assert add_source["source"]["settings"]["device"] == "Logitech C920"

        add_filter = filter_mod.add_filter(
            session,
            filter_type="chroma_key",
            source_name="Webcam",
            settings=("similarity=400",),
        )
        assert add_filter["filter"]["type"] == "chroma_key"

        output_mod.configure_streaming(session, service="twitch", key="abc123")
        output_mod.configure_recording(session, path="./captures", format_name="mp4", quality="high")
        output_mod.configure_output_settings(session, fps=60, encoder="nvenc")

        assert session.state["streaming"]["service"] == "twitch"
        assert session.state["recording"]["format"] == "mp4"
        assert session.state["settings"]["fps"] == 60


class TestCli:
    def test_project_new_and_info(self, tmp_path: Path):
        runner = CliRunner()
        project_path = tmp_path / "stream.json"

        create = runner.invoke(
            cli, ["project", "new", "--name", "stream", "-o", str(project_path)]
        )
        assert create.exit_code == 0
        assert project_path.exists()

        info = runner.invoke(cli, ["--project", str(project_path), "project", "info"])
        assert info.exit_code == 0
        assert '"name": "stream"' in info.output

    def test_cli_end_to_end(self, tmp_path: Path):
        runner = CliRunner()
        project_path = tmp_path / "stream.json"

        assert runner.invoke(
            cli, ["project", "new", "--name", "stream", "-o", str(project_path)]
        ).exit_code == 0
        assert runner.invoke(
            cli, ["--project", str(project_path), "scene", "add", "--name", "BRB"]
        ).exit_code == 0
        assert runner.invoke(
            cli,
            [
                "--project",
                str(project_path),
                "source",
                "add",
                "image",
                "--name",
                "Overlay",
                "--scene",
                "BRB",
                "-S",
                "file=/tmp/overlay.png",
            ],
        ).exit_code == 0
        assert runner.invoke(
            cli,
            [
                "--project",
                str(project_path),
                "filter",
                "add",
                "scroll",
                "-S",
                "Overlay",
                "--scene",
                "BRB",
                "-p",
                "speed_x=5",
            ],
        ).exit_code == 0
        assert runner.invoke(
            cli,
            [
                "--project",
                str(project_path),
                "output",
                "streaming",
                "--service",
                "twitch",
                "--key",
                "live_xxx",
            ],
        ).exit_code == 0

        state = json.loads(project_path.read_text(encoding="utf-8"))
        assert state["streaming"]["service"] == "twitch"
        brb_scene = next(scene for scene in state["scenes"] if scene["name"] == "BRB")
        assert brb_scene["sources"][0]["name"] == "Overlay"
        assert brb_scene["sources"][0]["filters"][0]["type"] == "scroll"
