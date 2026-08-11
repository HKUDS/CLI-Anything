"""Local Coqui XTTS v2 text-to-speech adapter."""

import tempfile
from pathlib import Path


class XTTSVoiceProvider:
    """Generate speech locally from a reference speaker recording."""

    MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, device: str = "auto", model: str = MODEL) -> None:
        self._device = self._resolve_device(device)
        self.model = model

    def synthesize(
        self,
        text: str,
        voice_id: str | None,
        model: str,
        output_format: str,
        voice_sample: Path | None,
        language: str,
    ) -> bytes:
        if voice_sample is None:
            raise ValueError("Local XTTS requires --voice-sample")
        sample = voice_sample.expanduser().resolve()
        if not sample.is_file():
            raise FileNotFoundError(f"Voice sample not found: {sample}")
        if output_format != "wav":
            raise ValueError("Local XTTS currently supports only --format wav")

        try:
            from TTS.api import TTS
        except ImportError as error:
            raise RuntimeError(
                "Local XTTS requires Coqui TTS. Install it with: "
                "pip install coqui-tts"
            ) from error

        synthesizer = TTS(model_name=model, progress_bar=False).to(self._device)
        with tempfile.TemporaryDirectory(prefix="shotcut-xtts-") as directory:
            output_path = Path(directory) / "speech.wav"
            synthesizer.tts_to_file(
                text=text,
                speaker_wav=[str(sample)],
                language=language,
                file_path=str(output_path),
            )
            return output_path.read_bytes()

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device not in {"auto", "cpu", "mps"}:
            raise ValueError("XTTS device must be auto, cpu, or mps")
        if device != "auto":
            return device
        try:
            import torch
        except ImportError:
            return "cpu"
        return "mps" if torch.backends.mps.is_available() else "cpu"
