"""Queue management — submit prompts, check status, clear queue, get history.

Covers the ComfyUI prompt queue lifecycle:
- POST /prompt  — submit a workflow for generation
- GET  /queue   — inspect pending and running items
- DELETE /queue — clear the queue
- GET  /history — completed prompt history
- POST /interrupt — stop the current generation
"""

import uuid

from cli_anything.comfyui.utils.comfyui_backend import api_get, api_post, api_delete


def queue_prompt(
    base_url: str,
    workflow: dict,
    client_id: str | None = None,
) -> dict:
    """Submit a workflow to the ComfyUI generation queue.

    Args:
        base_url: ComfyUI server base URL.
        workflow: Workflow node graph dict (API format).
        client_id: Optional client identifier for tracking. Auto-generated if None.

    Returns:
        Dict with 'prompt_id', 'number' (queue position), and 'node_errors'.

    Raises:
        RuntimeError: If the workflow is empty or the server rejects it.
    """
    if not workflow:
        raise RuntimeError("Cannot queue an empty workflow.")

    if client_id is None:
        client_id = str(uuid.uuid4())

    body = {
        "prompt": workflow,
        "client_id": client_id,
    }

    result = api_post(base_url, "/prompt", body)

    if "error" in result:
        detail = result.get("error", {})
        msg = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
        raise RuntimeError(f"ComfyUI rejected the workflow: {msg}")

    return {
        "prompt_id": result.get("prompt_id", ""),
        "number": result.get("number", 0),
        "node_errors": result.get("node_errors", {}),
        "client_id": client_id,
    }


def get_queue_status(base_url: str) -> dict:
    """Get the current queue status (pending and running items).

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Dict with 'queue_running' (list) and 'queue_pending' (list),
        plus 'running_count' and 'pending_count' summaries.
    """
    result = api_get(base_url, "/queue")

    running = result.get("queue_running", [])
    pending = result.get("queue_pending", [])

    return {
        "queue_running": running,
        "queue_pending": pending,
        "running_count": len(running),
        "pending_count": len(pending),
    }


def clear_queue(base_url: str) -> dict:
    """Clear all pending items from the queue.

    Note: This does not stop the currently running generation.
    Use interrupt() to stop the active generation.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Dict with status confirmation.
    """
    api_delete(base_url, "/queue", data={"clear": True})
    return {"status": "cleared"}


def get_history(base_url: str, max_items: int | None = None) -> dict:
    """Get the history of completed prompts.

    Args:
        base_url: ComfyUI server base URL.
        max_items: Maximum number of history entries to return (most recent first).
                   None returns all available history.

    Returns:
        Dict mapping prompt_id to output info, plus a 'total' count.
    """
    params = {}
    if max_items is not None:
        params["max_items"] = max_items

    result = api_get(base_url, "/history", params=params if params else None)

    formatted = {}
    for prompt_id, entry in result.items():
        outputs = entry.get("outputs", {})
        status = entry.get("status", {})
        formatted[prompt_id] = {
            "prompt_id": prompt_id,
            "status": status.get("status_str", "unknown"),
            "completed": status.get("completed", False),
            "outputs": _format_outputs(outputs),
        }

    return {
        "history": formatted,
        "total": len(formatted),
    }


def get_prompt_history(base_url: str, prompt_id: str) -> dict:
    """Get the history and output files for a specific prompt.

    Args:
        base_url: ComfyUI server base URL.
        prompt_id: The prompt ID returned from queue_prompt().

    Returns:
        Dict with prompt status, outputs, and image file references.

    Raises:
        RuntimeError: If the prompt ID is not found in history.
    """
    result = api_get(base_url, f"/history/{prompt_id}")

    if not result:
        raise RuntimeError(f"Prompt ID not found in history: {prompt_id}")

    entry = result.get(prompt_id, result)
    outputs = entry.get("outputs", {})
    status = entry.get("status", {})

    return {
        "prompt_id": prompt_id,
        "status": status.get("status_str", "unknown"),
        "completed": status.get("completed", False),
        "outputs": _format_outputs(outputs),
    }


def interrupt(base_url: str) -> dict:
    """Interrupt (stop) the currently running generation.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Dict with status confirmation.
    """
    api_post(base_url, "/interrupt")
    return {"status": "interrupted"}


def _format_outputs(outputs: dict) -> list[dict]:
    """Extract image file references from prompt outputs.

    Args:
        outputs: Raw outputs dict from ComfyUI history response.

    Returns:
        List of image file dicts with filename, subfolder, and type.
    """
    images = []
    for node_id, node_output in outputs.items():
        for img in node_output.get("images", []):
            images.append({
                "node_id": node_id,
                "filename": img.get("filename", ""),
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
    return images
