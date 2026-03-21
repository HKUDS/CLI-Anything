import subprocess, json
from typing import Optional, List


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ps() -> list[dict]:
    result = run(["docker", "ps", "--format", "{{json .}}"])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    items = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({"raw": line})
    return items


def run_image(image: str, name: Optional[str] = None, detach: bool = True) -> dict:
    cmd = ["docker", "run"]
    if detach:
        cmd.append("-d")
    if name:
        cmd += ["--name", name]
    cmd.append(image)
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "container_id": result.stdout.strip(),
        "stderr": result.stderr,
    }


def stop(container_id: str) -> dict:
    result = run(["docker", "stop", container_id])
    return {"success": result.returncode == 0, "output": result.stdout.strip()}


def logs(container_id: str, tail: int = 50) -> dict:
    result = run(["docker", "logs", "--tail", str(tail), container_id])
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def exec_cmd(container_id: str, cmd: str) -> dict:
    result = run(["docker", "exec", container_id, "sh", "-c", cmd])
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def images() -> list[dict]:
    result = run(["docker", "images", "--format", "{{json .}}"])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    items = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({"raw": line})
    return items


def pull(name: str) -> dict:
    result = run(["docker", "pull", name])
    return {"success": result.returncode == 0, "log": result.stdout[-500:]}


def build(path: str, tag: str) -> dict:
    result = run(["docker", "build", "-t", tag, path])
    return {"success": result.returncode == 0, "log": result.stdout[-500:]}


def rm(container_id: str) -> dict:
    result = run(["docker", "rm", container_id])
    return {"success": result.returncode == 0, "output": result.stdout.strip()}


def volumes() -> list[dict]:
    result = run(["docker", "volume", "ls", "--format", "{{json .}}"])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    items = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({"raw": line})
    return items


def networks() -> list[dict]:
    result = run(["docker", "network", "ls", "--format", "{{json .}}"])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    items = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({"raw": line})
    return items


def info() -> dict:
    result = run(["docker", "info", "--format", "{{json .}}"])
    if result.returncode != 0:
        return {"error": result.stderr}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout[:2000]}
