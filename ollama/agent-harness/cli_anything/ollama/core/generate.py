"""Ollama text generation and chat — streaming and non-streaming inference."""

import sys
from cli_anything.ollama.utils.ollama_backend import api_post, api_post_stream


def generate(base_url: str, model: str, prompt: str,
             system: str | None = None, template: str | None = None,
             context: list | None = None, options: dict | None = None,
             stream: bool = True):
    """Generate a text completion.

    Args:
        base_url: Ollama server URL.
        model: Model name.
        prompt: Input prompt.
        system: Optional system message.
        template: Optional prompt template override.
        context: Optional context from previous generate call.
        options: Optional model parameters (temperature, top_p, etc.).
        stream: If True, yields response chunks. If False, returns complete response.

    Returns/Yields:
        Response dicts with 'response' text and metadata.
    """
    data = {"model": model, "prompt": prompt, "stream": stream}
    if system is not None:
        data["system"] = system
    if template is not None:
        data["template"] = template
    if context is not None:
        data["context"] = context
    if options is not None:
        data["options"] = options

    if stream:
        return api_post_stream(base_url, "/api/generate", data)
    else:
        return api_post(base_url, "/api/generate", data, timeout=300)


def chat(base_url: str, model: str, messages: list[dict],
         options: dict | None = None, stream: bool = True):
    """Send a chat completion request.

    Args:
        base_url: Ollama server URL.
        model: Model name.
        messages: List of message dicts with 'role' and 'content' keys.
        options: Optional model parameters.
        stream: If True, yields response chunks. If False, returns complete response.

    Returns/Yields:
        Response dicts with 'message' containing assistant reply.
    """
    data = {"model": model, "messages": messages, "stream": stream}
    if options is not None:
        data["options"] = options

    if stream:
        return api_post_stream(base_url, "/api/chat", data)
    else:
        return api_post(base_url, "/api/chat", data, timeout=300)


def stream_to_stdout(chunks) -> dict:
    """Print streaming tokens to stdout and return the final response.

    Args:
        chunks: Generator of response chunks from generate() or chat().

    Returns:
        The final chunk (contains metadata like total_duration, etc.).
    """
    final = {}
    for chunk in chunks:
        # generate endpoint uses 'response', chat endpoint uses 'message.content'
        if "response" in chunk:
            sys.stdout.write(chunk["response"])
            sys.stdout.flush()
        elif "message" in chunk and "content" in chunk["message"]:
            sys.stdout.write(chunk["message"]["content"])
            sys.stdout.flush()
        if chunk.get("done", False):
            final = chunk
    sys.stdout.write("\n")
    sys.stdout.flush()
    return final
