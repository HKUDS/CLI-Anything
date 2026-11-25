import json
import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest


pytestmark = pytest.mark.skipif(os.getenv("KICAD_E2E") != "1", reason="Requires installed KiCad")
FIXTURES = Path(__file__).with_name("fixtures")


def run_cli(*args):
    executable = shutil.which("cli-anything-kicad")
    assert executable, "Install the KiCad harness before running E2E tests"
    completed = subprocess.run([executable, "--json", *map(str, args)],
                               text=True, capture_output=True, timeout=30)
    return completed, json.loads(completed.stdout)


def test_erc_returns_native_reports_and_rule_status():
    result, data = run_cli("sch", "lint", FIXTURES / "fixture.kicad_sch")
    assert result.returncode == data["exit_code"] == 5, result.stdout
    assert any(
        violation["type"] == "pin_not_connected"
        for sheet in data["report"]["sheets"] for violation in sheet["violations"]
    )

    result, data = run_cli("sch", "lint", FIXTURES / "clean.kicad_sch")
    assert result.returncode == data["exit_code"] == 0, result.stdout
    assert not any(sheet["violations"] for sheet in data["report"]["sheets"])


def test_export_fab_contains_real_outputs_and_keeps_source_files(tmp_path):
    board = FIXTURES / "fixture.kicad_pcb"
    schematic = FIXTURES / "fixture.kicad_sch"
    originals = [board.read_bytes(), schematic.read_bytes()]
    output = tmp_path / "fab.zip"
    result, data = run_cli(
        "pcb", "export-fab", board, "--schematic", schematic, "--output", output,
        "--layers", "F.Cu,Edge.Cuts",
    )
    assert result.returncode == 0, result.stdout
    with ZipFile(output) as archive:
        assert archive.namelist() == data["files"]
        assert archive.read("gerbers/fixture-F_Cu.gbr").rstrip().endswith(b"M02*")
        assert "gerbers/fixture-Edge_Cuts.gbr" in data["files"]
        assert any(archive.read(name).startswith(b"M48") for name in data["files"] if name.endswith(".drl"))
        positions = archive.read("positions.csv")
        bom = archive.read("bom.csv")
        assert b"R1" in positions and b"R2" not in positions
        assert b"10k" in bom and b"22k" not in bom
    assert [board.read_bytes(), schematic.read_bytes()] == originals


def test_failed_bom_export_publishes_no_archive(tmp_path):
    bad_schematic = tmp_path / "bad.kicad_sch"
    bad_schematic.write_text("Invalid schematic")
    output = tmp_path / "fab.zip"
    result, data = run_cli(
        "pcb", "export-fab", FIXTURES / "fixture.kicad_pcb", "--schematic", bad_schematic,
        "--output", output, "--layers", "F.Cu,Edge.Cuts",
    )
    assert result.returncode == 1
    assert "sch export bom" in data["error"]
    assert not output.exists()


def test_partial_layer_export_publishes_no_archive(tmp_path):
    output = tmp_path / "fab.zip"
    result, data = run_cli(
        "pcb", "export-fab", FIXTURES / "fixture.kicad_pcb",
        "--schematic", FIXTURES / "fixture.kicad_sch", "--output", output,
        "--layers", "F.Cu,UnknownLayer",
    )
    assert result.returncode == 1
    assert "layer" in data["error"]
    assert not output.exists()
