"""Tests for matrix skill distribution (P1-4): co-installed assets and the
content lookup chain in cli_hub/matrix_skill.py."""

from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import click.testing

from cli_hub import matrix_skill
from cli_hub.matrix_skill import (
    get_rendered_matrix_skill_path,
    render_matrix_skill_file,
)
from cli_hub.cli import main


def _make_content_dir(root, name="demo", with_pycache=False):
    """Create a fake repo checkout with cli-hub-matrix/<name>/ content."""
    content = root / "cli-hub-matrix" / name
    (content / "references").mkdir(parents=True)
    (content / "scripts").mkdir(parents=True)
    (content / "SKILL.md").write_text(
        "# Demo Matrix\n\nRead [`references/guide.md`](references/guide.md) "
        "and run `scripts/doctor.py`.\n",
        encoding="utf-8",
    )
    (content / "references" / "guide.md").write_text("guide", encoding="utf-8")
    (content / "scripts" / "doctor.py").write_text("print('ok')", encoding="utf-8")
    if with_pycache:
        pycache = content / "scripts" / "__pycache__"
        pycache.mkdir()
        (pycache / "doctor.cpython-310.pyc").write_bytes(b"\x00")
        (content / "scripts" / "stray.pyc").write_bytes(b"\x00")
    return content


def _demo_matrix(name="demo"):
    return {
        "name": name,
        "display_name": "Demo Matrix",
        "description": "A demo matrix.",
        "skill_md": f"cli-hub-matrix/{name}/SKILL.md",
        "clis": [],
    }


class TestAssetCoInstall:
    """references/ and scripts/ land beside the rendered SKILL.md."""

    def test_references_and_scripts_copied_beside_skill(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        _make_content_dir(repo)
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: repo)

        rendered = render_matrix_skill_file(_demo_matrix(), installed={})

        assert rendered == skill_dir / "demo" / "SKILL.md"
        assert rendered.exists()
        # Relative links in the skill resolve in the installed layout.
        assert (rendered.parent / "references" / "guide.md").exists()
        assert (rendered.parent / "scripts" / "doctor.py").exists()
        content = rendered.read_text(encoding="utf-8")
        assert "references/guide.md" in content
        assert "MATRIX_SKILL_PATHS:START" in content
        # Assets were found locally, so no remote-fallback note is injected.
        assert "will not resolve locally" not in content

    def test_pycache_and_pyc_excluded(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        _make_content_dir(repo, with_pycache=True)
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: repo)

        rendered = render_matrix_skill_file(_demo_matrix(), installed={})

        installed_files = [p.name for p in rendered.parent.rglob("*")]
        assert "doctor.py" in installed_files
        assert "__pycache__" not in installed_files
        assert not any(name.endswith(".pyc") for name in installed_files)

    def test_reinstall_is_idempotent_and_removes_stale_files(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        content = _make_content_dir(repo)
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: repo)

        first = render_matrix_skill_file(_demo_matrix(), installed={})
        # Simulate drift: stale file in the installed copy, updated source.
        (first.parent / "references" / "stale.md").write_text("old", encoding="utf-8")
        (content / "references" / "guide.md").write_text("guide v2", encoding="utf-8")

        second = render_matrix_skill_file(_demo_matrix(), installed={})

        assert second == first
        assert not (second.parent / "references" / "stale.md").exists()
        assert (second.parent / "references" / "guide.md").read_text(encoding="utf-8") == "guide v2"


class TestLookupChain:
    """Checkout -> bundled data -> published URL -> stub."""

    def test_bundled_data_used_when_no_checkout(self, tmp_path, monkeypatch):
        bundled_root = tmp_path / "bundled"
        _make_content_dir(bundled_root)
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: None)
        monkeypatch.setattr(
            matrix_skill, "BUNDLED_MATRIX_DATA_DIR", bundled_root / "cli-hub-matrix"
        )

        rendered = render_matrix_skill_file(_demo_matrix(), installed={})

        content = rendered.read_text(encoding="utf-8")
        assert "# Demo Matrix" in content
        assert (rendered.parent / "references" / "guide.md").exists()
        assert (rendered.parent / "scripts" / "doctor.py").exists()

    def test_published_url_used_when_no_local_content(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: None)
        monkeypatch.setattr(
            matrix_skill, "BUNDLED_MATRIX_DATA_DIR", tmp_path / "missing"
        )

        class FakeResponse:
            status_code = 200
            text = "# Demo Matrix (published)\n\npublished body\n"

        requested = {}

        def fake_get(url, timeout):
            requested["url"] = url
            return FakeResponse()

        monkeypatch.setattr(matrix_skill.requests, "get", fake_get)

        rendered = render_matrix_skill_file(_demo_matrix(), installed={})

        content = rendered.read_text(encoding="utf-8")
        assert "# Demo Matrix (published)" in content
        assert requested["url"] == (
            f"{matrix_skill.MATRIX_CONTENT_BASE_URL}/demo/SKILL.md"
        )
        # No local assets: the rendered skill points at the published copies.
        assert not (rendered.parent / "references").exists()
        assert "will not resolve locally" in content
        assert f"{matrix_skill.MATRIX_CONTENT_BASE_URL}/demo/" in content

    def test_stub_used_when_everything_else_fails(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: None)
        monkeypatch.setattr(
            matrix_skill, "BUNDLED_MATRIX_DATA_DIR", tmp_path / "missing"
        )

        def fake_get(url, timeout):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(matrix_skill.requests, "get", fake_get)

        rendered = render_matrix_skill_file(_demo_matrix(), installed={})

        content = rendered.read_text(encoding="utf-8")
        assert "# Demo Matrix" in content
        assert "A demo matrix." in content
        assert "Install with `cli-hub matrix install demo`." in content

    def test_published_url_non_200_falls_back_to_stub(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "home" / ".cli-hub" / "matrix"
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", skill_dir)
        monkeypatch.setattr(matrix_skill, "_find_repo_root", lambda: None)
        monkeypatch.setattr(
            matrix_skill, "BUNDLED_MATRIX_DATA_DIR", tmp_path / "missing"
        )

        class FakeResponse:
            status_code = 404
            text = "Not Found"

        monkeypatch.setattr(matrix_skill.requests, "get", lambda url, timeout: FakeResponse())

        rendered = render_matrix_skill_file(_demo_matrix(), installed={})
        assert "Install with `cli-hub matrix install demo`." in rendered.read_text(encoding="utf-8")


class TestRenderedPathCompat:
    """get_rendered_matrix_skill_path prefers the new layout, keeps legacy."""

    def test_prefers_directory_layout(self, tmp_path, monkeypatch):
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", tmp_path)
        new_path = tmp_path / "demo" / "SKILL.md"
        new_path.parent.mkdir(parents=True)
        new_path.write_text("new", encoding="utf-8")
        (tmp_path / "demo.SKILL.md").write_text("legacy", encoding="utf-8")

        assert get_rendered_matrix_skill_path("demo") == new_path

    def test_falls_back_to_legacy_flat_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", tmp_path)
        legacy = tmp_path / "demo.SKILL.md"
        legacy.write_text("legacy", encoding="utf-8")

        assert get_rendered_matrix_skill_path("demo") == legacy

    def test_defaults_to_directory_layout_when_nothing_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(matrix_skill, "MATRIX_SKILL_DIR", tmp_path)
        assert get_rendered_matrix_skill_path("demo") == tmp_path / "demo" / "SKILL.md"


class TestSkillOnlyInstall:
    """`cli-hub matrix install <name> --skill-only` renders without CLI installs."""

    def setup_method(self):
        self.runner = click.testing.CliRunner()
        self.human_detection = {
            "is_agent": False,
            "traffic_type": "human",
            "category": "human",
            "reason": "human",
            "signals": [],
            "stdin_tty": True,
            "is_interactive": True,
        }

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.render_matrix_skill_file")
    @patch("cli_hub.cli.get_installed", return_value={})
    @patch("cli_hub.cli.get_matrix")
    @patch("cli_hub.cli.install_matrix")
    def test_skill_only_renders_and_skips_cli_installs(
        self, mock_install_matrix, mock_get_matrix, mock_installed,
        mock_render, mock_detect, mock_visit, mock_first_run, tmp_path,
    ):
        mock_detect.return_value = self.human_detection
        mock_get_matrix.return_value = _demo_matrix()
        mock_render.return_value = tmp_path / "demo" / "SKILL.md"

        result = self.runner.invoke(main, ["matrix", "install", "demo", "--skill-only"])

        assert result.exit_code == 0
        assert "Local matrix skill:" in result.output
        mock_render.assert_called_once()
        mock_install_matrix.assert_not_called()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.get_matrix", return_value=None)
    def test_skill_only_unknown_matrix_fails(
        self, mock_get_matrix, mock_detect, mock_visit, mock_first_run,
    ):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "install", "missing", "--skill-only"])
        assert result.exit_code == 1
