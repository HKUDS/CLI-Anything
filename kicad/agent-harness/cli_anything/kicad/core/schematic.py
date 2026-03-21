"""KiCad CLI - Schematic operations via kicad-cli."""

import json
import os
import subprocess
from typing import Dict, Any, Optional, List


def _run_kicad_cli(args: list, timeout: int = 120) -> tuple:
    """Run kicad-cli and return (stdout, stderr, returncode)."""
    cmd = ["kicad-cli"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        raise RuntimeError("kicad-cli not found. Install with: apt install kicad")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"kicad-cli timed out after {timeout}s")


def export(
    file: str, output: str, page_size: str = None, no_background: bool = False
) -> Dict[str, Any]:
    """Export schematic to PDF/SVG/PNG.

    Args:
        file: Path to .kicad_sch file.
        output: Output file path.
        page_size: Page size (A4, A3, Letter, etc.).
        no_background: Transparent background.

    Returns:
        Dict with export results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Schematic not found: {file}")

    fmt = os.path.splitext(output)[1].lstrip(".").lower()
    if fmt not in ("pdf", "svg", "png"):
        raise ValueError(f"Unsupported format: {fmt}. Use pdf, svg, or png.")

    args = ["sch", "export", fmt, file, "--output", output]
    if page_size:
        args.extend(["--page-size", page_size])
    if no_background:
        args.append("--no-background")

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"Export failed: {stderr.strip()}")

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output": os.path.abspath(output),
        "format": fmt,
        "size_bytes": os.path.getsize(output) if os.path.exists(output) else 0,
    }


def bom(file: str, output: str, format: str = "csv") -> Dict[str, Any]:
    """Generate Bill of Materials from schematic.

    Args:
        file: Path to .kicad_sch file.
        output: Output BOM file path.
        format: Output format (csv, xml).

    Returns:
        Dict with BOM generation results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Schematic not found: {file}")

    fmt = os.path.splitext(output)[1].lstrip(".").lower()
    if fmt == "csv":
        bom_fmt = "csv"
    elif fmt == "xml":
        bom_fmt = "xml"
    else:
        bom_fmt = "csv"

    args = ["sch", "export", "bom", file, "--output", output]
    if bom_fmt != "csv":
        args.extend(["--format", bom_fmt])

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"BOM generation failed: {stderr.strip()}")

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output": os.path.abspath(output),
        "format": bom_fmt,
        "size_bytes": os.path.getsize(output) if os.path.exists(output) else 0,
    }


def netlist(file: str, output: str, fmt: str = "kicad") -> Dict[str, Any]:
    """Export netlist from schematic.

    Args:
        file: Path to .kicad_sch file.
        output: Output netlist file path.
        fmt: Netlist format (kicad, allegro, pads, spice).

    Returns:
        Dict with netlist results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Schematic not found: {file}")

    valid_formats = ("kicad", "allegro", "pads", "spice")
    if fmt not in valid_formats:
        raise ValueError(f"Invalid format: {fmt}. Choose from: {valid_formats}")

    args = ["sch", "export", "netlist", file, "--output", output, "--format", fmt]

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"Netlist export failed: {stderr.strip()}")

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output": os.path.abspath(output),
        "format": fmt,
        "size_bytes": os.path.getsize(output) if os.path.exists(output) else 0,
    }


def symbols_list(file: str) -> List[Dict[str, Any]]:
    """List symbols in a schematic file.

    Args:
        file: Path to .kicad_sch file.

    Returns:
        List of symbol dicts with name, reference, value.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Schematic not found: {file}")

    args = ["sch", "export", "symbol-list", file, "--output", "-"]

    stdout, stderr, rc = _run_kicad_cli(args)

    symbols = []
    for line in stdout.strip().split("\n"):
        if line.strip():
            parts = line.split("\t")
            if len(parts) >= 2:
                symbols.append(
                    {
                        "reference": parts[0] if len(parts) > 0 else "",
                        "value": parts[1] if len(parts) > 1 else "",
                        "footprint": parts[2] if len(parts) > 2 else "",
                        "datasheet": parts[3] if len(parts) > 3 else "",
                    }
                )

    return symbols


def parse_schematic(file: str) -> Dict[str, Any]:
    """Parse a schematic file and extract metadata.

    Args:
        file: Path to .kicad_sch file.

    Returns:
        Dict with schematic metadata.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Schematic not found: {file}")

    info = {
        "path": os.path.abspath(file),
        "filename": os.path.basename(file),
        "size_bytes": os.path.getsize(file),
    }

    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        import re

        title_match = re.search(r'\(title_block\s*\([^)]*?"([^"]+)"', content)
        if title_match:
            info["title"] = title_match.group(1)

        rev_match = re.search(r'\(rev\s+"?([^")\s]+)', content)
        if rev_match:
            info["revision"] = rev_match.group(1)

        sym_count = len(re.findall(r"\(symbol\b", content))
        info["symbol_count"] = sym_count

        wire_count = len(re.findall(r"\(wire\b", content))
        info["wire_count"] = wire_count

    except Exception:
        pass

    return info
