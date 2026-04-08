"""Ollama server info — status, version, running models."""

from cli_anything.ollama.utils.ollama_backend import api_get


def server_status(base_url: str) -> dict:
    """Check if Ollama server is running.

    Returns:
        Dict with server status message.
    """
    return api_get(base_url, "/")


def version(base_url: str) -> dict:
    """Get Ollama server version.

    Returns:
        Dict with 'version' key.
    """
    return api_get(base_url, "/api/version")
