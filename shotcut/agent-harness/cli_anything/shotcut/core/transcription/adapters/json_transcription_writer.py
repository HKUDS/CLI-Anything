"""JSON transcription artifact writer."""

import json
import os
from pathlib import Path

from ..models import TranscriptionResult


class JsonTranscriptionWriter:
    def write(self, result: TranscriptionResult, output_path: Path) -> Path:
        output_path = output_path.expanduser().resolve()
        if not output_path.parent.is_dir():
            raise FileNotFoundError(f"Transcript directory not found: {output_path.parent}")

        temporary_path = output_path.with_name(f".{output_path.name}.tmp")
        try:
            temporary_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": result.source,
                        "model": result.model,
                        "language": result.language,
                        "playback_speed": result.playback_speed,
                        "timestamps_are_original_video_seconds": True,
                        "text": result.text,
                        "segments": [segment.to_dict() for segment in result.segments],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.replace(temporary_path, output_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return output_path
