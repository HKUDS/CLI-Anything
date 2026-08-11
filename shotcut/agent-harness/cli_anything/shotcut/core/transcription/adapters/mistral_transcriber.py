"""Mistral Voxtral transcription adapter."""

from pathlib import Path

from ..models import ProviderTranscription, TranscriptSegment, TranscriptWord


class MistralTranscriber:
    def __init__(
        self,
        api_key: str,
        model: str = "voxtral-mini-latest",
        timeout_ms: int = 60_000,
    ) -> None:
        if not api_key.strip():
            raise ValueError("MISTRAL_API_KEY is required for transcription")
        self._api_key = api_key
        self.model = model
        self._timeout_ms = timeout_ms

    def transcribe(self, audio_path: Path) -> ProviderTranscription:
        try:
            from mistralai.client import Mistral
            from mistralai.client.models import File
        except ImportError as error:
            raise RuntimeError(
                "Mistral transcription requires the transcription extra: "
                "pip install cli-anything-shotcut[transcription]"
            ) from error

        with audio_path.open("rb") as audio_file:
            with Mistral(api_key=self._api_key, timeout_ms=self._timeout_ms) as client:
                response = client.audio.transcriptions.complete(
                    model=self.model,
                    file=File(content=audio_file.read(), fileName=audio_path.name),
                    timestamp_granularities=["segment", "word"],
                )

        text = getattr(response, "text", None)
        if not text and isinstance(response, dict):
            text = response.get("text")
        if not isinstance(text, str):
            raise RuntimeError("Mistral returned no transcript text")
        segments = []
        for segment in getattr(response, "segments", None) or []:
            segments.append(
                TranscriptSegment(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=str(segment.text),
                    score=self._optional_float(getattr(segment, "score", None)),
                    speaker_id=getattr(segment, "speaker_id", None),
                )
            )
        words = []
        for word in getattr(response, "words", None) or []:
            word_text = self._field(word, "word")
            if word_text is None:
                word_text = self._field(word, "text")
            start = self._field(word, "start")
            end = self._field(word, "end")
            if word_text is None or start is None or end is None:
                continue
            words.append(
                TranscriptWord(
                    word=str(word_text).strip(),
                    start_seconds=float(start),
                    end_seconds=float(end),
                )
            )
        return ProviderTranscription(
            text=text,
            segments=tuple(segments),
            words=tuple(words),
            language=getattr(response, "language", None),
        )

    @staticmethod
    def _field(value: object, name: str) -> object | None:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if isinstance(value, (float, int)) else None
