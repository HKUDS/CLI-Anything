"""KiCad CLI - Library operations via kicad-cli."""

import json
import os
import subprocess
from typing import Dict, Any, Optional, List


def _run_kicad_cli(args: list, timeout: int = 60) -> tuple:
    """Run kicad-cli and return (stdout, stderr, returncode)."""
    cmd = ["kicad-cli"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        raise RuntimeError("kicad-cli not found. Install with: apt install kicad")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"kicad-cli timed out after {timeout}s")


def list_symbols(lib: str) -> List[Dict[str, Any]]:
    """List symbols in a KiCad library.

    Args:
        lib: Path to library directory or .kicad_sym file.

    Returns:
        List of symbol dicts with name and description.
    """
    if not os.path.exists(lib):
        raise FileNotFoundError(f"Library not found: {lib}")

    symbols = []

    if os.path.isdir(lib):
        for f in sorted(os.listdir(lib)):
            if f.endswith(".kicad_sym"):
                fpath = os.path.join(lib, f)
                symbols.extend(_parse_sym_file(fpath))
    elif lib.endswith(".kicad_sym"):
        symbols = _parse_sym_file(lib)
    else:
        raise ValueError(f"Invalid library path: {lib}")

    return symbols


def _parse_sym_file(path: str) -> List[Dict[str, Any]]:
    """Parse a .kicad_sym file and extract symbol names."""
    symbols = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        import re

        for match in re.finditer(r'\(symbol\s+"([^"]+)"', content):
            symbols.append(
                {
                    "name": match.group(1),
                    "file": os.path.basename(path),
                }
            )
    except Exception:
        pass

    return symbols


def list_footprints(lib: str) -> List[Dict[str, Any]]:
    """List footprints in a KiCad footprint library.

    Args:
        lib: Path to footprint library directory.

    Returns:
        List of footprint dicts.
    """
    if not os.path.exists(lib):
        raise FileNotFoundError(f"Library not found: {lib}")

    footprints = []

    if os.path.isdir(lib):
        for f in sorted(os.listdir(lib)):
            if f.endswith(".kicad_mod"):
                footprints.append(
                    {
                        "name": os.path.splitext(f)[0],
                        "file": f,
                    }
                )

    return footprints


def export_symbol(lib: str, output_dir: str, symbol_name: str = None) -> Dict[str, Any]:
    """Export library symbols to SVG.

    Args:
        lib: Path to library directory or .kicad_sym file.
        output_dir: Output directory for SVG files.
        symbol_name: Specific symbol name to export (None = all).

    Returns:
        Dict with export results.
    """
    if not os.path.exists(lib):
        raise FileNotFoundError(f"Library not found: {lib}")

    os.makedirs(output_dir, exist_ok=True)

    if symbol_name:
        symbols = [symbol_name]
    else:
        all_symbols = list_symbols(lib)
        symbols = [s["name"] for s in all_symbols]

    exported = []
    errors = []

    for sym in symbols:
        output_file = os.path.join(output_dir, f"{sym}.svg")
        args = ["sym", "export", "svg", "--output", output_file, "--symbol", sym]

        if os.path.isdir(lib):
            args.extend(["--library", lib])
        else:
            args.append(lib)

        try:
            stdout, stderr, rc = _run_kicad_cli(args)
            if rc == 0 and os.path.exists(output_file):
                exported.append(sym)
            else:
                errors.append({"symbol": sym, "error": stderr.strip()})
        except Exception as e:
            errors.append({"symbol": sym, "error": str(e)})

    return {
        "status": "success" if not errors else "partial",
        "exported_count": len(exported),
        "error_count": len(errors),
        "output_dir": os.path.abspath(output_dir),
        "errors": errors[:10],
    }
