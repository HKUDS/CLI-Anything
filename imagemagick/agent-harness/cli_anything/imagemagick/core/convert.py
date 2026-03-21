"""ImageMagick convert/magick wrapper with structured JSON output."""

import json
import os
import subprocess
import shutil
from typing import Optional, List


def _get_magick_cmd():
    """Find the ImageMagick command (magick v7+ or convert v6)."""
    if shutil.which("magick"):
        return "magick"
    elif shutil.which("convert"):
        return "convert"
    raise RuntimeError("ImageMagick not found. Install with: apt install imagemagick")


def _run_magick(args: list[str], timeout: int = 60) -> dict:
    """Run an ImageMagick command and return structured output."""
    cmd = [_get_magick_cmd()] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "command": " ".join(cmd),
            "error": "Command timed out",
        }
    except Exception as e:
        return {"status": "error", "command": " ".join(cmd), "error": str(e)}


def _file_info(path: str) -> dict:
    """Get file stats."""
    if not os.path.exists(path):
        return {}
    st = os.stat(path)
    return {"path": path, "size": st.st_size, "modified": st.st_mtime}


def convert(
    input_path: str,
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: Optional[int] = None,
    format: Optional[str] = None,
    blur: Optional[float] = None,
    sharpen: Optional[float] = None,
    brightness: Optional[int] = None,
    contrast: Optional[int] = None,
    grayscale: bool = False,
    flip: bool = False,
    flop: bool = False,
    rotate: Optional[float] = None,
    crop: Optional[str] = None,
) -> dict:
    """Convert an image with various options."""
    args = [input_path]
    if width or height:
        w = str(width) if width else ""
        h = str(height) if height else ""
        args.extend(["-resize", f"{w}x{h}"])
    if quality:
        args.extend(["-quality", str(quality)])
    if blur:
        args.extend(["-blur", str(blur)])
    if sharpen:
        args.extend(["-sharpen", str(sharpen)])
    if brightness is not None:
        args.extend(["-brightness-contrast", f"{brightness}x{contrast or 0}"])
    if grayscale:
        args.extend(["-colorspace", "Gray"])
    if flip:
        args.append("-flip")
    if flop:
        args.append("-flop")
    if rotate:
        args.extend(["-rotate", str(rotate)])
    if crop:
        args.extend(["-crop", crop])
    args.append(output_path)
    result = _run_magick(args)
    result.update({"input": input_path, "output": output_path})
    result.update(_file_info(output_path))
    return result


def info(file_path: str) -> dict:
    """Get image info via ImageMagick format strings."""
    formats = "%w %h %[depth] %[colorspace] %[size]"
    args = [file_path, "-format", formats, "info:"]
    result = _run_magick(args)
    result["input"] = file_path
    if result["status"] == "success" and result["stdout"]:
        parts = result["stdout"].split()
        if len(parts) >= 4:
            result["info"] = {
                "width": int(parts[0]) if parts[0].isdigit() else parts[0],
                "height": int(parts[1]) if parts[1].isdigit() else parts[1],
                "depth": parts[2],
                "colorspace": parts[3],
                "filesize": parts[4] if len(parts) > 4 else "unknown",
            }
    return result


def resize(
    input_path: str,
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    mode: str = "fit",
) -> dict:
    """Resize an image."""
    resize_str = f"{width or ''}x{height or ''}"
    if mode == "fill":
        resize_str += "^"
    elif mode == "fit":
        resize_str += ">"
    args = [input_path, "-resize", resize_str, output_path]
    if mode == "fill":
        w = width or 100
        h = height or 100
        args.extend(["-gravity", "center", "-extent", f"{w}x{h}"])
    result = _run_magick(args)
    result.update(
        {
            "input": input_path,
            "output": output_path,
            "width": width,
            "height": height,
            "mode": mode,
        }
    )
    result.update(_file_info(output_path))
    return result


def crop_image(
    input_path: str, output_path: str, width: int, height: int, x: int, y: int
) -> dict:
    """Crop an image."""
    args = [input_path, "-crop", f"{width}x{height}+{x}+{y}", "+repage", output_path]
    result = _run_magick(args)
    result.update(
        {
            "input": input_path,
            "output": output_path,
            "crop": f"{width}x{height}+{x}+{y}",
        }
    )
    result.update(_file_info(output_path))
    return result


def thumbnail(input_path: str, output_path: str, size: int = 128) -> dict:
    """Create a thumbnail fitting within size x size."""
    args = [input_path, "-thumbnail", f"{size}x{size}", output_path]
    result = _run_magick(args)
    result.update({"input": input_path, "output": output_path, "size": size})
    result.update(_file_info(output_path))
    return result


def watermark(
    input_path: str, output_path: str, text: str, gravity: str = "southeast"
) -> dict:
    """Add text watermark to an image."""
    args = [
        input_path,
        "-gravity",
        gravity,
        "-fill",
        "white",
        "-stroke",
        "black",
        "-strokewidth",
        "1",
        "-pointsize",
        "24",
        "-annotate",
        "+10+10",
        text,
        output_path,
    ]
    result = _run_magick(args)
    result.update(
        {"input": input_path, "output": output_path, "text": text, "gravity": gravity}
    )
    result.update(_file_info(output_path))
    return result


def border(
    input_path: str, output_path: str, width: int = 5, color: str = "black"
) -> dict:
    """Add a border to an image."""
    args = [input_path, "-bordercolor", color, "-border", str(width), output_path]
    result = _run_magick(args)
    result.update(
        {"input": input_path, "output": output_path, "width": width, "color": color}
    )
    result.update(_file_info(output_path))
    return result


def montage(
    inputs: list[str],
    output_path: str,
    tile: str = "3x3",
    geometry: str = "200x200+5+5",
) -> dict:
    """Create a montage from multiple images."""
    if shutil.which("montage"):
        cmd = ["montage"] + inputs + ["-tile", tile, "-geometry", geometry, output_path]
    else:
        cmd = (
            [_get_magick_cmd(), "montage"]
            + inputs
            + ["-tile", tile, "-geometry", geometry, output_path]
        )
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = {
            "status": "success" if result.returncode == 0 else "error",
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as e:
        out = {"status": "error", "command": " ".join(cmd), "error": str(e)}
    out.update({"inputs": inputs, "output": output_path, "tile": tile})
    out.update(_file_info(output_path))
    return out


def animate_info(file_path: str) -> dict:
    """Get GIF animation info."""
    args = [file_path, "-format", "%n %[delay]x%[ticks]", "info:"]
    result = _run_magick(args)
    result["input"] = file_path
    if result["status"] == "success" and result["stdout"]:
        parts = result["stdout"].strip().split()
        if parts:
            result["animation"] = {
                "frames": parts[0] if parts[0].isdigit() else "unknown",
                "delay": parts[1] if len(parts) > 1 else "unknown",
            }
    return result


def compare(file1: str, file2: str) -> dict:
    """Compare two images using RMSE metric."""
    args = ["compare", "-metric", "RMSE", file1, file2, "null:"]
    cmd = [_get_magick_cmd()] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = {
            "status": "success" if result.returncode <= 1 else "error",
            "command": " ".join(cmd),
            "file1": file1,
            "file2": file2,
            "metric": "RMSE",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "different": result.returncode == 1,
        }
        if result.stderr:
            parts = result.stderr.strip().split()
            if len(parts) >= 2:
                output["raw_metric"] = parts[0]
                output["normalized_metric"] = parts[1]
    except Exception as e:
        output = {"status": "error", "command": " ".join(cmd), "error": str(e)}
    return output


def batch(
    inputs: list[str], output_dir: str, operation: str = "thumbnail", **kwargs
) -> dict:
    """Batch process multiple images."""
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for inp in inputs:
        base = os.path.splitext(os.path.basename(inp))[0]
        ext = os.path.splitext(inp)[1] or ".jpg"
        out_path = os.path.join(output_dir, f"{base}{ext}")
        if operation == "thumbnail":
            r = thumbnail(inp, out_path, kwargs.get("size", 128))
        elif operation == "resize":
            r = resize(inp, out_path, kwargs.get("width"), kwargs.get("height"))
        elif operation == "grayscale":
            r = convert(inp, out_path, grayscale=True)
        else:
            r = convert(inp, out_path, **kwargs)
        results.append(r)
    return {
        "status": "success",
        "operation": operation,
        "input_count": len(inputs),
        "output_dir": output_dir,
        "results": results,
    }
