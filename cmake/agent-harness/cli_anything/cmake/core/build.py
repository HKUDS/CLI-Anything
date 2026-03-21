import subprocess, os
from typing import Optional


def run(cmd: list[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def configure(source_dir: str, build_dir: str = "build") -> dict:
    os.makedirs(build_dir, exist_ok=True)
    result = run(["cmake", source_dir], cwd=build_dir)
    return {
        "success": result.returncode == 0,
        "build_dir": build_dir,
        "output": result.stdout,
        "stderr": result.stderr,
    }


def build(build_dir: str = "build") -> dict:
    result = run(["cmake", "--build", build_dir])
    return {
        "success": result.returncode == 0,
        "build_dir": build_dir,
        "output": result.stdout[-2000:],
        "stderr": result.stderr,
    }


def install(build_dir: str = "build") -> dict:
    result = run(["cmake", "--install", build_dir])
    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "stderr": result.stderr,
    }


def clean(build_dir: str = "build") -> dict:
    result = run(["cmake", "--build", build_dir, "--target", "clean"])
    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "stderr": result.stderr,
    }


def variables(build_dir: str = "build") -> list[dict]:
    cache = os.path.join(build_dir, "CMakeCache.txt")
    if not os.path.exists(cache):
        return [{"error": f"No CMakeCache.txt in {build_dir}"}]
    items = []
    with open(cache) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                items.append({"name": key.split(":")[0], "value": val})
    return items[:100]


def targets(build_dir: str = "build") -> list[str]:
    result = run(["cmake", "--build", build_dir, "--target", "help"])
    if result.returncode != 0:
        return [f"Error: {result.stderr}"]
    targets = []
    for line in result.stdout.split("\n"):
        if "..." in line:
            targets.append(line.split("...")[0].strip())
    return targets
