import subprocess
from typing import Optional


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def sync(src: str, dst: str, recursive: bool = True, verbose: bool = True) -> dict:
    cmd = ["rsync"]
    if recursive:
        cmd.append("-r")
    if verbose:
        cmd.append("-v")
    cmd += ["-a", src, dst]
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def dry_run(src: str, dst: str) -> dict:
    result = run(["rsync", "-avun", "--delete", src, dst])
    return {
        "success": result.returncode == 0,
        "would_do": result.stdout,
        "stderr": result.stderr,
    }


def mirror(src: str, dst: str) -> dict:
    result = run(["rsync", "-av", "--delete", src, dst])
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def stats(src: str, dst: str) -> dict:
    result = run(["rsync", "-avni", src, dst])
    lines = [l for l in result.stdout.split("\n") if l.strip()]
    return {
        "success": result.returncode == 0,
        "file_count": len(lines),
        "changes": lines[:50],
    }
