import subprocess, os
from typing import Optional, List


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ocr(image: str, lang: Optional[str] = None, output: Optional[str] = None) -> dict:
    cmd = ["tesseract", image, output or "stdout"]
    if lang:
        cmd += ["-l", lang]
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "text": result.stdout.strip(),
        "stderr": result.stderr,
    }


def langs() -> list[str]:
    result = run(["tesseract", "--list-langs"])
    if result.returncode != 0:
        return [f"Error: {result.stderr}"]
    return [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]


def pdf(image: str, lang: Optional[str] = None) -> dict:
    out = os.path.splitext(image)[0]
    cmd = ["tesseract", image, out, "pdf"]
    if lang:
        cmd += ["-l", lang]
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "output": f"{out}.pdf",
        "stderr": result.stderr,
    }


def batch(images: list[str], output_dir: str, lang: Optional[str] = None) -> list[dict]:
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for img in images:
        name = os.path.splitext(os.path.basename(img))[0]
        out = os.path.join(output_dir, name)
        cmd = ["tesseract", img, out]
        if lang:
            cmd += ["-l", lang]
        r = run(cmd)
        results.append(
            {"image": img, "success": r.returncode == 0, "output": f"{out}.txt"}
        )
    return results
