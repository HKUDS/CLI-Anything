"""Model discovery — list checkpoints, LoRAs, VAEs, and ControlNet models.

Uses ComfyUI's /object_info endpoint to enumerate available models.
No file system access is required — all model lists come from the running server.
"""

from cli_anything.comfyui.utils.comfyui_backend import api_get


def list_checkpoints(base_url: str) -> list[str]:
    """List all available checkpoint models.

    Queries CheckpointLoaderSimple to find installed checkpoint files.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Sorted list of checkpoint filenames/paths.

    Raises:
        RuntimeError: If the server is unreachable or returns unexpected data.
    """
    result = api_get(base_url, "/object_info/CheckpointLoaderSimple")

    try:
        ckpt_input = result["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
        models = ckpt_input[0]
        if not isinstance(models, list):
            raise ValueError("Expected list of checkpoint names")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"Could not parse checkpoint list from ComfyUI response: {e}"
        ) from e

    return sorted(models)


def list_loras(base_url: str) -> list[str]:
    """List all available LoRA models.

    Queries LoraLoader to find installed LoRA files.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Sorted list of LoRA filenames/paths.

    Raises:
        RuntimeError: If the server is unreachable or returns unexpected data.
    """
    result = api_get(base_url, "/object_info/LoraLoader")

    try:
        lora_input = result["LoraLoader"]["input"]["required"]["lora_name"]
        models = lora_input[0]
        if not isinstance(models, list):
            raise ValueError("Expected list of LoRA names")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"Could not parse LoRA list from ComfyUI response: {e}"
        ) from e

    return sorted(models)


def list_vaes(base_url: str) -> list[str]:
    """List all available VAE models.

    Queries VAELoader to find installed VAE files.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Sorted list of VAE filenames/paths.

    Raises:
        RuntimeError: If the server is unreachable or returns unexpected data.
    """
    result = api_get(base_url, "/object_info/VAELoader")

    try:
        vae_input = result["VAELoader"]["input"]["required"]["vae_name"]
        models = vae_input[0]
        if not isinstance(models, list):
            raise ValueError("Expected list of VAE names")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"Could not parse VAE list from ComfyUI response: {e}"
        ) from e

    return sorted(models)


def list_controlnets(base_url: str) -> list[str]:
    """List all available ControlNet models.

    Queries ControlNetLoader to find installed ControlNet files.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Sorted list of ControlNet filenames/paths. Empty list if none installed.

    Raises:
        RuntimeError: If the server is unreachable or returns unexpected data.
    """
    result = api_get(base_url, "/object_info/ControlNetLoader")

    try:
        cn_input = result["ControlNetLoader"]["input"]["required"]["control_net_name"]
        models = cn_input[0]
        if not isinstance(models, list):
            raise ValueError("Expected list of ControlNet names")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"Could not parse ControlNet list from ComfyUI response: {e}"
        ) from e

    return sorted(models)


def get_node_info(base_url: str, node_class: str) -> dict:
    """Get detailed input/output info for a specific node class.

    Args:
        base_url: ComfyUI server base URL.
        node_class: ComfyUI node class name (e.g., 'KSampler', 'CLIPTextEncode').

    Returns:
        Dict with node input/output schema.

    Raises:
        RuntimeError: If the node class is not found.
    """
    result = api_get(base_url, f"/object_info/{node_class}")

    if node_class not in result:
        raise RuntimeError(
            f"Node class '{node_class}' not found. "
            "Check spelling or use 'models list-nodes' to see all classes."
        )

    node = result[node_class]
    return {
        "class_type": node_class,
        "display_name": node.get("display_name", node_class),
        "description": node.get("description", ""),
        "category": node.get("category", ""),
        "input": node.get("input", {}),
        "output": node.get("output", []),
        "output_name": node.get("output_name", []),
    }


def list_all_node_classes(base_url: str) -> list[str]:
    """List all available node class names.

    Args:
        base_url: ComfyUI server base URL.

    Returns:
        Sorted list of all node class names.
    """
    result = api_get(base_url, "/object_info")
    return sorted(result.keys())
