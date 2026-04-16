"""LibreOffice backend — invoke LibreOffice headless for format conversions.

This module is the bridge between the CLI and the real LibreOffice installation.
Instead of reimplementing document rendering, we generate valid ODF files and
then use `libreoffice --headless --convert-to` to produce PDF, DOCX, XLSX, PPTX,
and other formats that require the full LibreOffice engine.

Requires: libreoffice (system package)
    apt install libreoffice   # Debian/Ubuntu
    brew install --cask libreoffice   # macOS
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


def find_libreoffice() -> str:
    """Find the LibreOffice executable.

    Returns the absolute path to the libreoffice/soffice binary.
    Searches PATH first, then common installation directories on each platform.
    Raises RuntimeError if not found.
    """
    # 1) Check PATH
    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path

    # 2) Check common installation paths (Windows)
    import sys
    if sys.platform == "win32" or os.name == "nt" or "MSYS" in os.environ.get("MSYSTEM", "") or "msys" in sys.platform or os.path.exists("C:/"):
        win_candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                         "LibreOffice", "program", "soffice.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                         "LibreOffice", "program", "soffice.exe"),
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for candidate in win_candidates:
            if os.path.isfile(candidate):
                return candidate

    # 3) Check common installation paths (macOS)
    mac_candidate = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.isfile(mac_candidate):
        return mac_candidate

    raise RuntimeError(
        "LibreOffice is not installed. Install it with:\n"
        "  apt install libreoffice          # Debian/Ubuntu\n"
        "  brew install --cask libreoffice   # macOS\n"
        "  winget install TheDocumentFoundation.LibreOffice  # Windows"
    )


def get_version() -> str:
    """Get the installed LibreOffice version string."""
    lo = find_libreoffice()
    try:
        result = subprocess.run(
            [lo, "--headless", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        version = result.stdout.strip()
        if version:
            return version
        # Some Windows builds print to stderr
        if result.stderr.strip():
            return result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return f"LibreOffice (path: {lo})"


def convert(
    input_path: str,
    output_format: str,
    output_dir: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """Convert a file using LibreOffice headless.

    Args:
        input_path: Path to the input file (ODF, HTML, etc.)
        output_format: Target format (pdf, docx, xlsx, pptx, txt, html, png, etc.)
        output_dir: Directory for the output file. Defaults to same dir as input.
        timeout: Maximum seconds to wait for conversion.

    Returns:
        Absolute path to the converted output file.

    Raises:
        RuntimeError: If LibreOffice is not installed or conversion fails.
        FileNotFoundError: If the input file doesn't exist.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    lo = find_libreoffice()
    input_path = os.path.abspath(input_path)

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        lo,
        "--headless",
        "--convert-to", output_format,
        "--outdir", output_dir,
        input_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (exit {result.returncode}):\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )

    # Determine the output filename
    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base}.{output_format}")

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"LibreOffice conversion produced no output file.\n"
            f"  Expected: {output_path}\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )

    return os.path.abspath(output_path)


def convert_odf_to(
    odf_path: str,
    output_format: str,
    output_path: Optional[str] = None,
    overwrite: bool = False,
    timeout: int = 120,
) -> dict:
    """Convert an ODF file to another format via LibreOffice headless.

    This is the high-level function used by the CLI export pipeline.

    Args:
        odf_path: Path to the ODF file (.odt, .ods, .odp).
        output_format: Target format (pdf, docx, xlsx, pptx, etc.).
        output_path: Desired output path. If None, uses same dir as input.
        overwrite: Allow overwriting existing output files.
        timeout: Maximum seconds for conversion.

    Returns:
        Dict with output path, format, and file size.
    """
    if output_path and os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file exists: {output_path}. Use --overwrite."
        )

    # Convert to a temp dir first, then move to desired location
    with tempfile.TemporaryDirectory() as tmpdir:
        converted = convert(odf_path, output_format, output_dir=tmpdir, timeout=timeout)

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            shutil.move(converted, output_path)
            final_path = os.path.abspath(output_path)
        else:
            # Move to same directory as input
            dest_dir = os.path.dirname(os.path.abspath(odf_path))
            dest = os.path.join(dest_dir, os.path.basename(converted))
            if os.path.exists(dest) and not overwrite:
                raise FileExistsError(f"Output file exists: {dest}. Use --overwrite.")
            shutil.move(converted, dest)
            final_path = os.path.abspath(dest)

    return {
        "action": "convert",
        "output": final_path,
        "format": output_format,
        "method": "libreoffice-headless",
        "libreoffice_version": get_version(),
        "file_size": os.path.getsize(final_path),
    }
