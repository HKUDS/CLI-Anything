"""Ollama model management — list, pull, show, delete, copy, running models."""

from cli_anything.ollama.utils.ollama_backend import (
    api_get, api_post, api_post_stream, api_delete,
)


def list_models(base_url: str) -> dict:
    """List all locally available models.

    Returns:
        Dict with 'models' key containing list of model info dicts.
    """
    return api_get(base_url, "/api/tags")


def show_model(base_url: str, name: str) -> dict:
    """Show details about a model (parameters, template, license, etc.).

    Args:
        name: Model name (e.g., 'llama3.2', 'mistral:latest').

    Returns:
        Dict with model details.
    """
    return api_post(base_url, "/api/show", {"name": name})


def pull_model(base_url: str, name: str, stream: bool = True):
    """Download a model from the Ollama library.

    Args:
        name: Model name to pull.
        stream: If True, yields progress dicts. If False, returns final result.

    Returns/Yields:
        Progress dicts with 'status', 'digest', 'total', 'completed' keys.
    """
    data = {"name": name, "stream": stream}
    if stream:
        return api_post_stream(base_url, "/api/pull", data)
    else:
        return api_post(base_url, "/api/pull", data, timeout=600)


def delete_model(base_url: str, name: str) -> dict:
    """Delete a model from local storage.

    Args:
        name: Model name to delete.

    Returns:
        Status dict.
    """
    return api_delete(base_url, "/api/delete", {"name": name})


def copy_model(base_url: str, source: str, destination: str) -> dict:
    """Copy a model to a new name.

    Args:
        source: Source model name.
        destination: New model name.

    Returns:
        Status dict.
    """
    return api_post(base_url, "/api/copy", {
        "source": source,
        "destination": destination,
    })


def running_models(base_url: str) -> dict:
    """List models currently loaded in memory.

    Returns:
        Dict with 'models' key containing currently running model info.
    """
    return api_get(base_url, "/api/ps")
