"""Ghidra CLI - Decompilation via analyzeHeadless."""

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


def decompile(binary: str, function_name: str, output: str = None) -> Dict[str, Any]:
    """Decompile a specific function to C.

    Args:
        binary: Path to binary file.
        function_name: Name of function to decompile.
        output: Optional output file path.

    Returns:
        Dict with decompiled C code.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = f"""
import ghidra.app.decompiler.DecompInterface
import ghidra.program.model.listing.FunctionManager

funcMgr = currentProgram.getFunctionManager()
func = funcMgr.getFunction(True, toAddr(0))
if func is None:
    funcs = funcMgr.getFunctions(True)
    while funcs.hasNext():
        f = funcs.next()
        if f.getName() == "{function_name}":
            func = f
            break

if func is None:
    println("ERROR: Function '{function_name}' not found")
else:
    decomp = DecompInterface()
    decomp.openProgram(currentProgram)
    results = decomp.decompileFunction(func, 60, monitor)
    if results.decompileCompleted():
        decompFunc = results.getDecompiledFunction()
        println("Function: " + func.getName())
        println("Address: " + func.getEntryPoint().toString())
        println("---DECOMPILED_CODE---")
        println(decompFunc.getC())
    else:
        println("ERROR: Decompilation failed: " + results.getErrorMessage())
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_decomp_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_decomp"

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

        result = {
            "binary": os.path.abspath(binary),
            "function": function_name,
            "status": "success",
        }

        if "ERROR:" in stdout:
            error_msg = stdout.split("ERROR:", 1)[1].strip()
            result["status"] = "failed"
            result["error"] = error_msg
            return result

        if "---DECOMPILED_CODE---" in stdout:
            parts = stdout.split("---DECOMPILED_CODE---")
            code = parts[1].strip()
            result["c_code"] = code

            if output:
                os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
                with open(output, "w") as f:
                    f.write(code)
                result["output_file"] = os.path.abspath(output)
        else:
            result["status"] = "failed"
            result["error"] = "No decompiled code found in output"

        return result
    finally:
        os.unlink(script_path)


def decompile_all(binary: str, output_dir: str, timeout: int = 600) -> Dict[str, Any]:
    """Decompile all functions in a binary.

    Args:
        binary: Path to binary file.
        output_dir: Output directory for decompiled files.
        timeout: Timeout per function in seconds.

    Returns:
        Dict with decompilation results.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    os.makedirs(output_dir, exist_ok=True)

    script_content = f"""
import ghidra.app.decompiler.DecompInterface

decomp = DecompInterface()
decomp.openProgram(currentProgram)

funcMgr = currentProgram.getFunctionManager()
funcs = funcMgr.getFunctions(True)
count = 0
errors = 0

while funcs.hasNext():
    func = funcs.next()
    name = func.getName()
    addr = func.getEntryPoint().toString()

    results = decomp.decompileFunction(func, {timeout}, monitor)
    if results.decompileCompleted():
        decompFunc = results.getDecompiledFunction()
        c_code = decompFunc.getC()
        filename = addr.replace(":", "_") + "_" + name.replace("/", "_") + ".c"
        println(addr + "\\t" + name + "\\t" + filename)
        count += 1
    else:
        println(addr + "\\t" + name + "\\tERROR: " + results.getErrorMessage())
        errors += 1

println("---SUMMARY---")
println("Decompiled: " + str(count))
println("Errors: " + str(errors))
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_decomp_all_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_decomp_all"

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

        result = {
            "binary": os.path.abspath(binary),
            "output_dir": os.path.abspath(output_dir),
            "status": "success",
            "functions": [],
            "decompiled_count": 0,
            "error_count": 0,
        }

        for line in stdout.strip().split("\n"):
            if "---SUMMARY---" in line:
                break
            parts = line.split("\t")
            if len(parts) >= 3:
                if parts[2].startswith("ERROR:"):
                    result["error_count"] += 1
                    result["functions"].append(
                        {
                            "address": parts[0].strip(),
                            "name": parts[1].strip(),
                            "status": "failed",
                            "error": parts[2].replace("ERROR:", "").strip(),
                        }
                    )
                else:
                    result["decompiled_count"] += 1
                    result["functions"].append(
                        {
                            "address": parts[0].strip(),
                            "name": parts[1].strip(),
                            "file": parts[2].strip(),
                            "status": "success",
                        }
                    )

        return result
    finally:
        os.unlink(script_path)


def list_decompilable(binary: str) -> List[Dict[str, Any]]:
    """List functions that can be decompiled.

    Args:
        binary: Path to binary file.

    Returns:
        List of decompilable function dicts.
    """
    if not os.path.exists(binary):
        raise FileNotFoundError(f"Binary not found: {binary}")

    script_content = """
funcMgr = currentProgram.getFunctionManager()
funcs = funcMgr.getFunctions(True)
for func in funcs:
    name = func.getName()
    addr = func.getEntryPoint().toString()
    size = func.getBody().getNumAddresses()
    thunk = "THUNK" if func.isThunk() else ""
    println(addr + "\\t" + name + "\\t" + str(size) + "\\t" + thunk)
"""

    script_path = tempfile.mktemp(suffix=".py", prefix="ghidra_list_decomp_")
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        project_dir = tempfile.mkdtemp(prefix="ghidra_")
        project_name = "cli_ghidra_list_decomp"

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
                        "is_thunk": parts[3].strip() == "THUNK"
                        if len(parts) > 3
                        else False,
                    }
                )

        return results
    finally:
        os.unlink(script_path)
