"""End-to-end tests for Krita CLI."""

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
    CLI_BASE = _resolve_cli("cli-anything-krita")

    def _run(self, args, check=False):
        return subprocess.run(
            self.CLI_BASE + args, capture_output=True, text=True, check=check
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Krita" in result.stdout

    def test_create_canvas(self, tmp_dir):
        out = os.path.join(tmp_dir, "canvas.png")
        result = self._run(
            ["create", "--width", "100", "--height", "100", "--output", out]
        )
        assert result.returncode == 0
        assert os.path.exists(out)
