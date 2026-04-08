"""Transcription — speech to subtitles via ASR engines."""

from cli_anything.videocaptioner.utils.vc_backend import run_quiet


def transcribe(
    input_path: str,
    output_path: str | None = None,
    asr: str = "bijian",
    language: str = "auto",
    format: str = "srt",
    word_timestamps: bool = False,
    whisper_api_key: str | None = None,
    whisper_api_base: str | None = None,
    whisper_model: str | None = None,
) -> str:
    """Transcribe audio/video to subtitles.

    Args:
        input_path: Audio or video file path.
        output_path: Output file or directory path.
        asr: ASR engine (bijian, jianying, whisper-api, whisper-cpp).
        language: Source language ISO 639-1 code, or 'auto'.
        format: Output format (srt, ass, txt, json).
        word_timestamps: Include word-level timestamps.
        whisper_api_key: Whisper API key (for whisper-api engine).
        whisper_api_base: Whisper API base URL.
        whisper_model: Whisper model name.

    Returns:
        Output file path.
    """
    args = ["transcribe", input_path, "--asr", asr, "--language", language, "--format", format]
    if output_path:
        args += ["-o", output_path]
    if word_timestamps:
        args.append("--word-timestamps")
    if whisper_api_key:
        args += ["--whisper-api-key", whisper_api_key]
    if whisper_api_base:
        args += ["--whisper-api-base", whisper_api_base]
    if whisper_model:
        args += ["--whisper-model", whisper_model]
    return run_quiet(args)
