import subprocess
from typing import Optional


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def scan(
    target: str, ports: Optional[str] = None, top_ports: Optional[int] = None
) -> dict:
    cmd = ["nmap"]
    if ports:
        cmd += ["-p", ports]
    if top_ports:
        cmd += ["--top-ports", str(top_ports)]
    cmd.append(target)
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "target": target,
        "output": result.stdout,
        "stderr": result.stderr,
    }


def os_detect(target: str) -> dict:
    result = run(["nmap", "-O", target])
    return {
        "success": result.returncode == 0,
        "target": target,
        "output": result.stdout,
    }


def service(target: str) -> dict:
    result = run(["nmap", "-sV", target])
    return {
        "success": result.returncode == 0,
        "target": target,
        "output": result.stdout,
    }


def ping(target: str) -> dict:
    result = run(["nmap", "-sn", target])
    return {
        "success": result.returncode == 0,
        "target": target,
        "output": result.stdout,
    }
