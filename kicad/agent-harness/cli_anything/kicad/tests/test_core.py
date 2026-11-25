import json
from zipfile import ZipFile

import pytest
from click.testing import CliRunner

from cli_anything.kicad.backend import KiCadError, _write_archive
from cli_anything.kicad.kicad_cli import cli


def test_fabrication_zip_contains_staged_files_and_cannot_overwrite(tmp_path, monkeypatch):
    gerber = tmp_path / "gerbers" / "controller-F_Cu.gbr"
    gerber.parent.mkdir()
    gerber.write_bytes(b"fixture Gerber")
    destination = tmp_path / "controller.zip"

    write = ZipFile.write

    def write_before_publish(archive, *args, **kwargs):
        assert not destination.exists()
        return write(archive, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(ZipFile, "write", write_before_publish)
        _write_archive(destination, tmp_path, [gerber])
    original = destination.read_bytes()
    with ZipFile(destination) as archive:
        assert archive.read("gerbers/controller-F_Cu.gbr") == b"fixture Gerber"

    gerber.write_bytes(b"new output")
    with pytest.raises(KiCadError, match="already exists"):
        _write_archive(destination, tmp_path, [gerber])
    assert destination.read_bytes() == original


def test_missing_kicad_has_a_json_diagnostic(tmp_path):
    schematic = tmp_path / "board.kicad_sch"
    schematic.touch()
    result = CliRunner().invoke(
        cli, ["--json", "--binary", str(tmp_path / "missing-kicad"), "sch", "lint", str(schematic)],
    )
    assert result.exit_code == 1
    assert "Install KiCad" in json.loads(result.output)["error"]
