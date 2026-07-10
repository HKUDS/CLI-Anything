"""Smoke tests — verify package imports, CLI parsing, and write guards."""
import subprocess
import sys

import click
import pytest


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


def test_playlist_write_options_are_documented():
    r = subprocess.run([sys.executable, "-m", "cli_anything.rekordbox", "playlist", "create", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "--force" in r.stdout
    assert "--no-backup" in r.stdout


def test_write_guard_refuses_running_rekordbox_without_force(monkeypatch):
    import cli_anything.rekordbox.rekordbox_cli as rb

    monkeypatch.setattr(rb, "_is_rekordbox_running", lambda: True)
    monkeypatch.setattr(rb, "_open_db", lambda: pytest.fail("write DB should not open"))

    with pytest.raises(click.ClickException, match="Refusing"):
        rb._open_db_for_write(force=False, backup=True, operation="create playlist")


def test_write_guard_requires_backup_for_forced_running_write(monkeypatch):
    import cli_anything.rekordbox.rekordbox_cli as rb

    monkeypatch.setattr(rb, "_is_rekordbox_running", lambda: True)
    monkeypatch.setattr(rb, "_open_db", lambda: pytest.fail("write DB should not open"))

    with pytest.raises(click.ClickException, match="without a backup"):
        rb._open_db_for_write(force=True, backup=False, operation="create playlist")


def test_write_guard_creates_backup_before_write(monkeypatch, tmp_path):
    import cli_anything.rekordbox.rekordbox_cli as rb

    db_path = tmp_path / "master.db"
    db_path.write_bytes(b"synthetic sqlcipher bytes")

    class FakeUrl:
        database = str(db_path)

    class FakeEngine:
        url = FakeUrl()

    class FakeDb:
        engine = FakeEngine()

    monkeypatch.setattr(rb, "_is_rekordbox_running", lambda: False)
    monkeypatch.setattr(rb, "_open_db", lambda: FakeDb())

    db, safety = rb._open_db_for_write(force=False, backup=True, operation="create playlist")

    assert isinstance(db, FakeDb)
    assert safety["rekordbox_running"] is False
    assert safety["forced"] is False
    assert len(safety["backup"]) == 1
    backup_path = safety["backup"][0]
    assert backup_path.startswith(str(tmp_path / "cli-anything-backups"))
    assert open(backup_path, "rb").read() == b"synthetic sqlcipher bytes"


def test_data_file_present():
    """Bunker.midi.csv must ship with the package."""
    from pathlib import Path
    import cli_anything.rekordbox as pkg
    csv = Path(pkg.__file__).parent / "data" / "Bunker.midi.csv"
    assert csv.exists(), f"missing {csv}"
    head = csv.read_text(encoding="utf-8").splitlines()[0]
    assert head.startswith("@file,1,"), f"bad header: {head}"
