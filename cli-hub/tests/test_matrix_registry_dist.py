"""Built distributions retain matrix discovery during a first offline run."""

import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def test_sdist_built_wheel_discovers_matrices_without_network(tmp_path):
    source = Path(__file__).resolve().parents[1]
    checkout = tmp_path / "checkout"
    package = checkout / "cli-hub"
    shutil.copytree(
        source,
        package,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "build",
            "dist",
            "*.egg-info",
            "_matrix_data",
            "matrix_registry.json",
        ),
    )
    registry = {"matrices": [{"name": "offline-demo", "clis": []}]}
    (checkout / "matrix_registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    # Include skill content to exercise the existing package build path.
    content = checkout / "cli-hub-matrix" / "offline-demo"
    content.mkdir(parents=True)
    (content / "SKILL.md").write_text("# Offline demo\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "setup.py", "sdist"],
        cwd=package,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archive = next((package / "dist").glob("*.tar.gz"))
    sdist_root = tmp_path / "sdist"
    with tarfile.open(archive) as handle:
        handle.extractall(sdist_root)
    sdist = next(sdist_root.iterdir())
    result = subprocess.run(
        [sys.executable, "setup.py", "bdist_wheel"],
        cwd=sdist,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next((sdist / "dist").glob("*.whl"))
    extracted = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as handle:
        handle.extractall(extracted)
    script = """
import sys
from pathlib import Path
import requests
sys.path.insert(0, sys.argv[1])
Path.home = classmethod(lambda cls: Path(sys.argv[2]))
def offline(*a, **k):
    raise requests.ConnectionError('offline')
requests.get = offline
from cli_hub.matrix import fetch_all_matrices, get_matrix
assert fetch_all_matrices() == [{'name': 'offline-demo', 'clis': []}]
assert get_matrix('OFFLINE-DEMO')['name'] == 'offline-demo'
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(extracted), str(tmp_path / "home")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
