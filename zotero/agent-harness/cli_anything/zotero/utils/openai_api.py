from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_RESPONSES_API_URL = "https://api.openai.com/v1/responses"


def _extract_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in response_payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts).strip()


def create_text_response(
    *,
    api_key: str,
    model: str,
    instructions: str,
    input_text: str,
    timeout: int = 60,
) -> dict[str, Any]:
    responses_url = os.environ.get("CLI_ANYTHING_ZOTERO_OPENAI_URL", "").strip() or DEFAULT_RESPONSES_API_URL
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
    }
    request = urllib.request.Request(
        responses_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Responses API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI Responses API request failed: {exc}") from exc

    answer = _extract_text(response_payload)
    if not answer:
        raise RuntimeError("OpenAI Responses API returned no text output")
    return {
        "response_id": response_payload.get("id"),
        "answer": answer,
        "raw": response_payload,
    }
