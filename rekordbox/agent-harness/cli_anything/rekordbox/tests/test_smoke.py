"""Smoke tests — verify package imports + Click CLI parses without error."""
import subprocess, sys


def test_import():
    import cli_anything.rekordbox  # noqa


def test_cli_help():
    """`--help` should exit 0."""
    r = subprocess.run([sys.executable, "-m", "cli_anything.rekordbox", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "Pioneer Rekordbox" in r.stdout or "rekordbox" in r.stdout.lower()


def test_subcommand_help():
    for sub in ["library", "playlist", "deck", "status", "install-mapping", "mix"]:
        r = subprocess.run([sys.executable, "-m", "cli_anything.rekordbox", sub, "--help"],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{sub} --help failed: {r.stderr}"


def test_data_file_present():
    """Bunker.midi.csv must ship with the package."""
    from pathlib import Path
    import cli_anything.rekordbox as pkg
    csv = Path(pkg.__file__).parent / "data" / "Bunker.midi.csv"
    assert csv.exists(), f"missing {csv}"
    head = csv.read_text(encoding="utf-8").splitlines()[0]
    assert head.startswith("@file,1,"), f"bad header: {head}"
