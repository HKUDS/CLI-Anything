"""Image output management — download and list generated images.

Covers:
- Listing output images from a prompt's history
- Downloading images from ComfyUI's /view endpoint
- Saving images to local disk
"""

from pathlib import Path

from cli_anything.comfyui.utils.comfyui_backend import api_get_raw
from cli_anything.comfyui.core.queue import get_prompt_history


def list_output_images(base_url: str, prompt_id: str) -> list[dict]:
    """List all output images for a completed prompt.

    Args:
        base_url: ComfyUI server base URL.
        prompt_id: The prompt ID returned from queue_prompt().

    Returns:
        List of image dicts with 'filename', 'subfolder', 'type', and 'node_id'.

    Raises:
        RuntimeError: If the prompt is not found or not yet completed.
    """
    history = get_prompt_history(base_url, prompt_id)

    outputs = history.get("outputs", [])
    if not outputs:
        status = history.get("status", "unknown")
        if not history.get("completed", False):
            raise RuntimeError(
                f"Prompt {prompt_id} has not completed yet (status: {status}). "
                "Wait for generation to finish before listing images."
            )
        return []

    return outputs


def download_image(
    base_url: str,
    filename: str,
    output_path: str,
    subfolder: str = "",
    image_type: str = "output",
    overwrite: bool = False,
) -> dict:
    """Download a single output image from ComfyUI.

    Args:
        base_url: ComfyUI server base URL.
        filename: Image filename (e.g., 'ComfyUI_00001_.png').
        output_path: Local path to save the image.
        subfolder: Subfolder within ComfyUI's output directory (usually empty).
        image_type: Image type — 'output', 'input', or 'temp'.
        overwrite: If False, raise RuntimeError if output_path already exists.

    Returns:
        Dict with 'status', 'path', and 'size_bytes'.

    Raises:
        RuntimeError: If the file exists and overwrite is False, or download fails.
    """
    dest = Path(output_path)

    if dest.exists() and not overwrite:
        raise RuntimeError(
            f"Output file already exists: {output_path}. "
            "Use overwrite=True to replace it."
        )

    params = {
        "filename": filename,
        "type": image_type,
    }
    if subfolder:
        params["subfolder"] = subfolder

    image_bytes = api_get_raw(base_url, "/view", params=params)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(image_bytes)

    return {
        "status": "downloaded",
        "path": str(dest.resolve()),
        "filename": filename,
        "size_bytes": len(image_bytes),
    }


def download_prompt_images(
    base_url: str,
    prompt_id: str,
    output_dir: str,
    overwrite: bool = False,
) -> list[dict]:
    """Download all output images for a completed prompt to a directory.

    Args:
        base_url: ComfyUI server base URL.
        prompt_id: The prompt ID returned from queue_prompt().
        output_dir: Local directory to save images into.
        overwrite: If True, overwrite existing files.

    Returns:
        List of result dicts from download_image(), one per image.

    Raises:
        RuntimeError: If the prompt is not found or no images are available.
    """
    images = list_output_images(base_url, prompt_id)

    if not images:
        raise RuntimeError(f"No output images found for prompt: {prompt_id}")

    output_d = Path(output_dir)
    output_d.mkdir(parents=True, exist_ok=True)

    results = []
    for img in images:
        filename = img["filename"]
        dest = str(output_d / filename)
        result = download_image(
            base_url=base_url,
            filename=filename,
            output_path=dest,
            subfolder=img.get("subfolder", ""),
            image_type=img.get("type", "output"),
            overwrite=overwrite,
        )
        results.append(result)

    return results
