"""KiCad CLI - PCB operations via kicad-cli."""

import json
import os
import subprocess
from typing import Dict, Any, Optional, List


def _run_kicad_cli(args: list, timeout: int = 300) -> tuple:
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
    file: str, output: str, layers: str = None, fmt: str = "svg"
) -> Dict[str, Any]:
    """Export PCB to SVG/Gerber/PDF.

    Args:
        file: Path to .kicad_pcb file.
        output: Output file path.
        layers: Comma-separated layer names (F.Cu,B.Cu,etc.).
        fmt: Output format (svg, pdf, gerber).

    Returns:
        Dict with export results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    args = ["pcb", "export", fmt, file, "--output", output]
    if layers:
        args.extend(["--layers", layers])

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"PCB export failed: {stderr.strip()}")

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output": os.path.abspath(output),
        "format": fmt,
        "layers": layers or "all",
        "size_bytes": os.path.getsize(output) if os.path.exists(output) else 0,
    }


def drc(file: str) -> Dict[str, Any]:
    """Run Design Rule Check on a PCB.

    Args:
        file: Path to .kicad_pcb file.

    Returns:
        Dict with DRC results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    args = ["pcb", "drc", file, "--output", "-"]

    stdout, stderr, rc = _run_kicad_cli(args)

    errors = []
    warnings = []

    for line in (stdout + stderr).split("\n"):
        line = line.strip()
        if not line:
            continue
        if "error" in line.lower():
            errors.append(line)
        elif "warning" in line.lower():
            warnings.append(line)

    return {
        "status": "pass" if rc == 0 else "fail",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:50],
        "warnings": warnings[:50],
    }


def drill(file: str, output_dir: str) -> Dict[str, Any]:
    """Generate drill files from PCB.

    Args:
        file: Path to .kicad_pcb file.
        output_dir: Output directory for drill files.

    Returns:
        Dict with drill generation results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    os.makedirs(output_dir, exist_ok=True)

    args = ["pcb", "export", "drill", file, "--output", output_dir]

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"Drill generation failed: {stderr.strip()}")

    generated = []
    for f in os.listdir(output_dir):
        fpath = os.path.join(output_dir, f)
        if os.path.isfile(fpath):
            generated.append(f)

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output_dir": os.path.abspath(output_dir),
        "files": generated,
        "file_count": len(generated),
    }


def gerber(file: str, output_dir: str) -> Dict[str, Any]:
    """Generate Gerber files from PCB (all layers).

    Args:
        file: Path to .kicad_pcb file.
        output_dir: Output directory for Gerber files.

    Returns:
        Dict with Gerber generation results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    os.makedirs(output_dir, exist_ok=True)

    args = ["pcb", "export", "gerbers", file, "--output", output_dir]

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"Gerber generation failed: {stderr.strip()}")

    generated = []
    for f in os.listdir(output_dir):
        fpath = os.path.join(output_dir, f)
        if os.path.isfile(fpath):
            generated.append(f)

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output_dir": os.path.abspath(output_dir),
        "files": sorted(generated),
        "file_count": len(generated),
    }


def export_3d(file: str, output: str) -> Dict[str, Any]:
    """Export 3D model from PCB (STEP/VRML).

    Args:
        file: Path to .kicad_pcb file.
        output: Output file path (.step or .wrl).

    Returns:
        Dict with 3D export results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    ext = os.path.splitext(output)[1].lower()
    fmt = "step" if ext == ".step" else "vrml"

    args = ["pcb", "export", "step", file, "--output", output]

    stdout, stderr, rc = _run_kicad_cli(args)

    if rc != 0:
        raise RuntimeError(f"3D export failed: {stderr.strip()}")

    return {
        "status": "success",
        "input": os.path.abspath(file),
        "output": os.path.abspath(output),
        "format": fmt,
        "size_bytes": os.path.getsize(output) if os.path.exists(output) else 0,
    }


def stats(file: str) -> Dict[str, Any]:
    """Get PCB statistics (tracks, vias, components).

    Args:
        file: Path to .kicad_pcb file.

    Returns:
        Dict with PCB statistics.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    info = {
        "path": os.path.abspath(file),
        "filename": os.path.basename(file),
        "size_bytes": os.path.getsize(file),
    }

    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        import re

        info["tracks"] = len(re.findall(r"\(segment\b", content))
        info["vias"] = len(re.findall(r"\(via\b", content))
        info["pads"] = len(re.findall(r"\(pad\b", content))
        info["zones"] = len(re.findall(r"\(zone\b", content))
        info["footprints"] = len(re.findall(r"\(footprint\b", content))

        size_match = re.search(r'\(page\s+"([^"]+)"', content)
        if size_match:
            info["page_size"] = size_match.group(1)

        layers = re.findall(r'\((\d+)\s+"([^"]+)"', content)
        if layers:
            info["layer_count"] = len(layers)
            info["layers"] = [name for _, name in layers[:10]]

    except Exception:
        pass

    return info


def list_layers(file: str) -> List[str]:
    """List layers in a PCB file.

    Args:
        file: Path to .kicad_pcb file.

    Returns:
        List of layer names.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        import re

        layers = re.findall(r'\(\d+\s+"([^"]+)"', content)
        return layers
    except Exception:
        return []


def list_footprints(file: str) -> List[Dict[str, str]]:
    """List footprints used in a PCB.

    Args:
        file: Path to .kicad_pcb file.

    Returns:
        List of footprint dicts.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"PCB not found: {file}")

    footprints = []
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        import re

        for match in re.finditer(r'\(footprint\s+"([^"]+)"', content):
            footprints.append({"name": match.group(1)})

    except Exception:
        pass

    return footprints
