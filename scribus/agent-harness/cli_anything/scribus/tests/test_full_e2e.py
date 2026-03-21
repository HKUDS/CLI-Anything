"""End-to-end tests for Scribus CLI."""

import json, os, sys, tempfile, subprocess, pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _resolve_cli(name):
    import shutil

    path = shutil.which(name)
    if path:
        return [path]
    module = (
        name.replace("cli-anything-", "cli_anything.")
        + "."
        + name.split("-")[-1]
        + "_cli"
    )
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-scribus")

    def _run(self, args, check=False):
        return subprocess.run(
            self.CLI_BASE + args, capture_output=True, text=True, check=check
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Scribus" in result.stdout

    def test_create_document(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.sla")
        result = self._run(["create", out, "--pages", "2"])
        assert result.returncode == 0
        assert os.path.exists(out)

    def test_info(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.sla")
        self._run(["create", out])
        result = self._run(["info", out])
        assert result.returncode == 0

    def test_page_list(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.sla")
        self._run(["create", out, "--pages", "3"])
        result = self._run(["page", "list", out])
        assert result.returncode == 0
        assert "3" in result.stdout or "2" in result.stdout

    def test_font_list(self):
        result = self._run(["font-list"])
        assert result.returncode == 0
