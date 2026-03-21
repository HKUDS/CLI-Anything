import subprocess, os
from typing import Optional


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def convert(
    input_file: str,
    output_file: str,
    from_fmt: Optional[str] = None,
    to_fmt: Optional[str] = None,
) -> dict:
    cmd = ["pandoc", input_file, "-o", output_file]
    if from_fmt:
        cmd += ["-f", from_fmt]
    if to_fmt:
        cmd += ["-t", to_fmt]
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "output": output_file,
        "stderr": result.stderr,
    }


def info(file: str) -> dict:
    result = run(["pandoc", "--version"])
    lines = result.stdout.strip().split("\n")
    ver = lines[0] if lines else "unknown"
    return {
        "file": file,
        "exists": os.path.exists(file),
        "pandoc_version": ver,
        "size": os.path.getsize(file) if os.path.exists(file) else 0,
    }


def formats() -> list[str]:
    result = run(["pandoc", "--list-input-formats"])
    return result.stdout.strip().split("\n")


def metadata(file: str) -> dict:
    result = run(["pandoc", "-s", "--to", "plain", file])
    return {
        "file": file,
        "body_preview": result.stdout[:500]
        if result.returncode == 0
        else result.stderr,
    }


def toc(file: str) -> list[str]:
    result = run(["pandoc", "--toc", "--to", "plain", file])
    if result.returncode != 0:
        return [f"Error: {result.stderr}"]
    return result.stdout.strip().split("\n")[:30]
