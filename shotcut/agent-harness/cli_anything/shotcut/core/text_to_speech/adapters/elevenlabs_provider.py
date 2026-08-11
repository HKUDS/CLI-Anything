"""ElevenLabs text-to-speech HTTP adapter."""

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ElevenLabsTextToSpeech:
    """Synthesize speech through the ElevenLabs REST API."""

    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, api_key: str, timeout_seconds: float = 60.0) -> None:
        if not api_key.strip():
            raise ValueError("ELEVENLABS_API_KEY is required for text-to-speech")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def synthesize(
        self,
        text: str,
        voice_id: str | None,
        model: str,
        output_format: str,
        voice_sample: Path | None,
        language: str,
    ) -> bytes:
        if not voice_id or voice_sample is not None:
            raise ValueError("ElevenLabs requires a voice ID and no local voice sample")
        request = Request(
            f"{self.BASE_URL}/{voice_id}?output_format={output_format}",
            data=json.dumps({"text": text, "model_id": model}).encode("utf-8"),
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self._api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"ElevenLabs synthesis failed ({error.code}): {detail}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"ElevenLabs connection failed: {error.reason}") from error
