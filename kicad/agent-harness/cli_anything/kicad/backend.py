"""Run KiCad's native CLI and package its fabrication artifacts."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile


class KiCadError(RuntimeError):
    """A KiCad command or export failed."""


def find_binary(configured: str | None) -> str:
    binary = shutil.which(configured or "kicad-cli")
    if binary is None and configured is None and sys.platform == "darwin":
        binary = shutil.which("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
    if binary is None:
        raise KiCadError("Install KiCad 9 or set --binary to the installed kicad-cli executable.")
    return str(Path(binary).resolve())


def run_native(binary: str, args: list[str], source: Path, *, allowed=(0,)):
    source = source.resolve()
    try:
        result = subprocess.run(
            [binary, *args, str(source)],
            cwd=source.parent, capture_output=True, encoding="utf-8", errors="replace",
        )
    except OSError as error:
        raise KiCadError(f"Could not start kicad-cli: {error}") from error
    if result.returncode not in allowed:
        details = result.stderr.strip() or result.stdout.strip()
        command = " ".join(args[:3] if args[1] == "export" else args[:2])
        raise KiCadError(f"kicad-cli {command} exited with {result.returncode}. {details}".rstrip())
    return result


def electrical_rule_check(binary: str, schematic: Path) -> tuple[dict, int]:
    with TemporaryDirectory(prefix="kicad-erc-") as work:
        report = Path(work) / "erc.json"
        result = run_native(
            binary,
            ["sch", "erc", "--format", "json", "--exit-code-violations", "--output", str(report)],
            schematic,
            allowed=(0, 5),
        )
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise KiCadError("KiCad did not write a readable ERC JSON report.") from error
        if not isinstance(data, dict) or not isinstance(data.get("sheets"), list):
            raise KiCadError("KiCad did not return the expected ERC report.")
    return data, result.returncode


def _write_archive(output: Path, stage: Path, files: list[Path]) -> None:
    with TemporaryDirectory(prefix=".kicad-fab-", dir=output.parent) as work:
        complete = Path(work) / "fabrication.zip"
        with ZipFile(complete, "w", compression=ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, file.relative_to(stage).as_posix())
        try:
            if os.name == "nt":
                complete.rename(output)
            else:
                os.link(complete, output)
        except FileExistsError as error:
            raise KiCadError(f"Output already exists: {output}") from error


def export_fabrication(
    binary: str, board: Path, schematic: Path, output: Path, layers: str | None,
) -> list[str]:
    selected_layers = []
    if layers is not None:
        selected_layers = list(dict.fromkeys(layer.strip() for layer in layers.split(",")))
    if "" in selected_layers:
        raise KiCadError("Use a comma-separated list of non-empty Gerber layer names.")

    with TemporaryDirectory(prefix="kicad-fab-") as work:
        stage = Path(work)
        gerbers = stage / "gerbers"
        drills = stage / "drill"
        gerbers.mkdir()
        drills.mkdir()
        positions = stage / "positions.csv"
        bom = stage / "bom.csv"

        gerber_args = ["pcb", "export", "gerbers", "--no-protel-ext", "--output", str(gerbers) + os.sep]
        if selected_layers:
            gerber_args.extend(["--layers", ",".join(selected_layers)])
        run_native(binary, gerber_args, board)
        gerber_files = list(gerbers.glob("*.gbr"))
        if selected_layers and len(gerber_files) != len(selected_layers):
            raise KiCadError(
                f"KiCad wrote {len(gerber_files)} Gerbers for {len(selected_layers)} selected layers. "
                "Check that each named layer exists and is enabled on the board."
            )
        if not gerber_files:
            raise KiCadError("KiCad did not produce Gerber files.")

        run_native(binary, ["pcb", "export", "drill", "--format", "excellon",
                            "--output", str(drills) + os.sep], board)
        run_native(binary, ["pcb", "export", "pos", "--format", "csv", "--units", "mm",
                            "--side", "both", "--exclude-dnp", "--output", str(positions)], board)
        run_native(
            binary,
            ["sch", "export", "bom", "--format-preset", "CSV", "--exclude-dnp", "--output", str(bom)],
            schematic,
        )

        if not any(drills.glob("*.drl")):
            raise KiCadError("KiCad did not produce Excellon drill files.")
        if not positions.is_file() or not bom.is_file():
            raise KiCadError("KiCad did not produce the position file and bill of materials.")
        files = sorted(path for path in stage.rglob("*") if path.is_file())
        _write_archive(output, stage, files)
        return [file.relative_to(stage).as_posix() for file in files]
