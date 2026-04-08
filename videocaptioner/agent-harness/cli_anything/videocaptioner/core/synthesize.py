"""Video synthesis — burn subtitles into video with customizable styles."""

from cli_anything.videocaptioner.utils.vc_backend import run_quiet


def synthesize(
    video_path: str,
    subtitle_path: str,
    output_path: str | None = None,
    subtitle_mode: str = "soft",
    quality: str = "medium",
    layout: str | None = None,
    render_mode: str | None = None,
    style: str | None = None,
    style_override: str | None = None,
    font_file: str | None = None,
) -> str:
    """Burn subtitles into a video file.

    Args:
        video_path: Input video file.
        subtitle_path: Subtitle file (.srt, .ass).
        output_path: Output video file path.
        subtitle_mode: 'soft' (embedded track) or 'hard' (burned in).
        quality: Video quality (ultra, high, medium, low).
        layout: Bilingual layout.
        render_mode: 'ass' (outline/shadow) or 'rounded' (background boxes).
        style: Style preset name (default, anime, vertical, rounded).
        style_override: Inline JSON to override style fields.
        font_file: Custom font file path (.ttf/.otf).

    Returns:
        Output video file path.
    """
    args = ["synthesize", video_path, "-s", subtitle_path,
            "--subtitle-mode", subtitle_mode, "--quality", quality]
    if output_path:
        args += ["-o", output_path]
    if layout:
        args += ["--layout", layout]
    if render_mode:
        args += ["--render-mode", render_mode]
    if style:
        args += ["--style", style]
    if style_override:
        args += ["--style-override", style_override]
    if font_file:
        args += ["--font-file", font_file]
    return run_quiet(args)
