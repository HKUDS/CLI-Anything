"""Ollama embeddings — generate vector embeddings from text."""

from cli_anything.ollama.utils.ollama_backend import api_post


def embed(base_url: str, model: str, input_text: str | list[str]) -> dict:
    """Generate embeddings for input text.

    Args:
        base_url: Ollama server URL.
        model: Model name (must support embeddings, e.g., 'nomic-embed-text').
        input_text: Text string or list of strings to embed.

    Returns:
        Dict with 'embeddings' key containing list of embedding vectors.
    """
    data = {"model": model, "input": input_text}
    return api_post(base_url, "/api/embed", data, timeout=60)
