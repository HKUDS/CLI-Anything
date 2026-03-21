"""Ghidra CLI - Binary analysis via analyzeHeadless."""

import json
import os
import subprocess
import tempfile
from typing import Dict, Any, Optional, List


def _run_ghidra(args: list, timeout: int = 300) -> tuple:
    """Run analyzeHeadless and return (stdout, stderr, returncode)."""
    cmd = ["analyzeHeadless"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        raise RuntimeError(
            "analyzeHeadless not found. Install Ghidra from ghidra-sre.org"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"analyzeHeadless timed out after {timeout}s")


def analyze(
    binary: str, project_dir: str = None, script: str = None, timeout: int = 300
) -> Dict[str, Any]:
    """Run auto-analysis on a binary.

    Args:
        binary: Path to binary file.
        project_dir: Ghidra project directory.
        script: Post-analysis script path.
        timeout: Analysis timeout in seconds.

    Returns:
        Dict with analysis results.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    if project_dir is None:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")

    os.makedirs(project_dir, exist_ok=True)
    project_name = "cli_ghidra_tmp"

    args = [
        project_dir,
        project_name,
        "-import",
        os.path.abspath(binary),
        "-analysisTimeoutPerFile",
        str(timeout),
    ]
    if script:
        args.extend(["-postScript", script])
    args.append("-deleteProject")

    stdout, stderr, rc = _run_ghidra(args, timeout=timeout + 60)

    info = {
        "status": "success" if rc == 0 else "failed",
        "binary": os.path.abspath(binary),
        "project_dir": project_dir,
    }

    if rc != 0:
        info["error"] = stderr.strip()[:500]
    else:
        info["analysis_complete"] = True

    return info


def strings(binary: str, min_length: int = 4) -> List[Dict[str, Any]]:
    """Extract strings with addresses from binary.

    Args:
        binary: Path to binary file.
        min_length: Minimum string length.

    Returns:
        List of string dicts with address and value.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = f"""
import ghidra.app.script.GhidraScript
import ghidra.program.model.data.StringDataType

listing = currentProgram.getListing()
memory = currentProgram.getMemory()
strings = []

iter = listing.getData(memory.getMinAddress(), True)
while iter.hasNext():
    data = iter.next()
    if isinstance(data.getDataType(), StringDataType):
        s = data.getValue()
        if s and len(s) >= {min_length}:
            addr = data.getAddress()
            strings.append(str(addr) + "\\t" + s)

println("\\n".join(strings))
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_strings_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_strings"

        args = [
            project_dir,
            project_name,
            "-import",
            os.path.abspath(binary),
            "-postScript",
            script_path,
            "-deleteProject",
        ]

        stdout, stderr, rc = _run_ghidra(args)

        results = []
        for line in stdout.strip().split("\n"):
            if "\t" in line:
                addr, value = line.split("\t", 1)
                results.append({"address": addr.strip(), "value": value.strip()})

        return results
    finally:
        os.unlink(script_path)


def imports(binary: str) -> List[Dict[str, str]]:
    """List imported functions from binary.

    Args:
        binary: Path to binary file.

    Returns:
        List of import dicts with name and library.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = """
import ghidra.program.model.symbol.SourceType

extRefTable = currentProgram.getExternalManager().getExternalReferences()
for ref in extRefTable:
    func = currentProgram.getFunctionManager().getFunctionAt(ref.getFromAddress())
    name = func.getName() if func else ref.getLabel()
    library = ref.getExternalLocation().getLibraryName() if ref.getExternalLocation() else ""
    println(ref.getFromAddress().toString() + "\\t" + name + "\\t" + library)
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_imports_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_imports"

        args = [
            project_dir,
            project_name,
            "-import",
            os.path.abspath(binary),
            "-postScript",
            script_path,
            "-deleteProject",
        ]

        stdout, stderr, rc = _run_ghidra(args)

        results = []
        for line in stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                results.append(
                    {
                        "address": parts[0].strip(),
                        "name": parts[1].strip(),
                        "library": parts[2].strip() if len(parts) > 2 else "",
                    }
                )

        return results
    finally:
        os.unlink(script_path)


def exports(binary: str) -> List[Dict[str, str]]:
    """List exported functions from binary.

    Args:
        binary: Path to binary file.

    Returns:
        List of export dicts with name and address.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = """
import ghidra.program.model.symbol.SymbolType

symTable = currentProgram.getSymbolTable()
for sym in symTable.getSymbolIterator():
    if sym.getSymbolType() == SymbolType.FUNCTION:
        entryPoints = sym.getProgram().getMemory().getExecuteSet()
        if entryPoints.contains(sym.getAddress()):
            println(sym.getAddress().toString() + "\\t" + sym.getName())
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_exports_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_exports"

        args = [
            project_dir,
            project_name,
            "-import",
            os.path.abspath(binary),
            "-postScript",
            script_path,
            "-deleteProject",
        ]

        stdout, stderr, rc = _run_ghidra(args)

        results = []
        for line in stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                results.append({"address": parts[0].strip(), "name": parts[1].strip()})

        return results
    finally:
        os.unlink(script_path)


def functions(binary: str) -> List[Dict[str, Any]]:
    """List all functions with addresses.

    Args:
        binary: Path to binary file.

    Returns:
        List of function dicts.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = """
funcMgr = currentProgram.getFunctionManager()
for func in funcMgr.getFunctions(True):
    addr = func.getEntryPoint().toString()
    name = func.getName()
    size = func.getBody().getNumAddresses()
    println(addr + "\\t" + name + "\\t" + str(size))
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_functions_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_functions"

        args = [
            project_dir,
            project_name,
            "-import",
            os.path.abspath(binary),
            "-postScript",
            script_path,
            "-deleteProject",
        ]

        stdout, stderr, rc = _run_ghidra(args)

        results = []
        for line in stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                results.append(
                    {
                        "address": parts[0].strip(),
                        "name": parts[1].strip(),
                        "size": int(parts[2]) if len(parts) > 2 else 0,
                    }
                )

        return results
    finally:
        os.unlink(script_path)


def xrefs(binary: str, address: str) -> List[Dict[str, str]]:
    """Show cross-references to an address.

    Args:
        binary: Path to binary file.
        address: Target address (hex).

    Returns:
        List of xref dicts.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = f"""
import ghidra.program.model.symbol.RefType

addr = toAddr("{address}")
refs = currentProgram.getReferenceManager().getReferencesTo(addr)
for ref in refs:
    fromAddr = ref.getFromAddress()
    refType = str(ref.getReferenceType())
    println(fromAddr.toString() + "\\t" + refType)
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_xrefs_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_xrefs"

        args = [
            project_dir,
            project_name,
            "-import",
            os.path.abspath(binary),
            "-postScript",
            script_path,
            "-deleteProject",
        ]

        stdout, stderr, rc = _run_ghidra(args)

        results = []
        for line in stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 1:
                results.append(
                    {
                        "from_address": parts[0].strip(),
                        "type": parts[1].strip() if len(parts) > 1 else "",
                    }
                )

        return results
    finally:
        os.unlink(script_path)


def symbols(binary: str) -> List[Dict[str, str]]:
    """List all symbols in binary.

    Args:
        binary: Path to binary file.

    Returns:
        List of symbol dicts.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = """
symTable = currentProgram.getSymbolTable()
for sym in symTable.getSymbolIterator(True):
    println(sym.getAddress().toString() + "\\t" + sym.getName() + "\\t" + str(sym.getSymbolType()))
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_symbols_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_symbols"

        args = [
            project_dir,
            project_name,
            "-import",
            os.path.abspath(binary),
            "-postScript",
            script_path,
            "-deleteProject",
        ]

        stdout, stderr, rc = _run_ghidra(args)

        results = []
        for line in stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                results.append(
                    {
                        "address": parts[0].strip(),
                        "name": parts[1].strip(),
                        "type": parts[2].strip() if len(parts) > 2 else "",
                    }
                )

        return results
    finally:
        os.unlink(script_path)


def headers(binary: str) -> Dict[str, Any]:
    """Show PE/ELF header info.

    Args:
        binary: Path to binary file.

    Returns:
        Dict with header information.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    info = {
        "path": os.path.abspath(binary),
        "filename": os.path.basename(binary),
        "size_bytes": os.path.getsize(binary),
    }

    try:
        with open(binary, "rb") as f:
            magic = f.read(4)

        if magic[:2] == b"MZ":
            info["format"] = "PE"
        elif magic[:4] == b"\x7fELF":
            info["format"] = "ELF"
            with open(binary, "rb") as f:
                f.read(5)
                ei_class = f.read(1)
                info["arch"] = "64-bit" if ei_class == b"\x02" else "32-bit"
                ei_data = f.read(1)
                info["endianness"] = "little" if ei_data == b"\x01" else "big"
                ei_osabi = f.read(1)
                osabi_map = {
                    b"\x00": "UNIX System V",
                    b"\x03": "Linux",
                    b"\x06": "Solaris",
                    b"\x09": "FreeBSD",
                }
                info["os"] = osabi_map.get(ei_osabi, f"Unknown ({ord(ei_osabi)})")
        elif magic[:2] == b"\xfe\xed" or magic[:4] in (
            b"\xce\xfa\xed\xfe",
            b"\xcf\xfa\xed\xfe",
        ):
            info["format"] = "Mach-O"
        else:
            info["format"] = "Unknown"
            info["magic"] = magic.hex()

    except Exception:
        pass

    return info


def run_script(binary: str, project_dir: str, script: str) -> Dict[str, Any]:
    """Run a custom Ghidra script on a binary.

    Args:
        binary: Path to binary file.
        project_dir: Ghidra project directory.
        script: Path to Ghidra script.

    Returns:
        Dict with script output.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")
    if not os.path.exists(script):
        raise FileNotFoundError(f"Script not found: {script}")

    os.makedirs(project_dir, exist_ok=True)
    project_name = "cli_ghidra_script"

    args = [
        project_dir,
        project_name,
        "-import",
        os.path.abspath(binary),
        "-postScript",
        os.path.abspath(script),
        "-deleteProject",
    ]

    stdout, stderr, rc = _run_ghidra(args)

    return {
        "status": "success" if rc == 0 else "failed",
        "binary": os.path.abspath(binary),
        "script": os.path.abspath(script),
        "stdout": stdout.strip()[:2000],
        "stderr": stderr.strip()[:2000],
    }


def project_create(name: str, project_dir: str) -> Dict[str, Any]:
    """Create a Ghidra project.

    Args:
        name: Project name.
        project_dir: Project directory.

    Returns:
        Dict with project info.
    """
    os.makedirs(project_dir, exist_ok=True)

    args = [project_dir, name, "-noanalysis"]

    stdout, stderr, rc = _run_ghidra(args)

    return {
        "status": "success" if rc == 0 else "failed",
        "project_name": name,
        "project_dir": os.path.abspath(project_dir),
    }


def project_import(project_dir: str, binary: str) -> Dict[str, Any]:
    """Import a binary into a Ghidra project.

    Args:
        project_dir: Ghidra project directory.
        binary: Binary to import.

    Returns:
        Dict with import results.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    project_name = "cli_ghidra_import"

    args = [project_dir, project_name, "-import", os.path.abspath(binary)]

    stdout, stderr, rc = _run_ghidra(args)

    return {
        "status": "success" if rc == 0 else "failed",
        "binary": os.path.abspath(binary),
        "project_dir": os.path.abspath(project_dir),
    }
