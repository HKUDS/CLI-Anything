"""Video synthesis — burn subtitles into video with customizable styles."""

from cli_anything.videocaptioner.utils.vc_backend import run_quiet
from cli_anything.videocaptioner.core.review import ensure_subtitle_consistency


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
    review_script: str | None = None,
    max_script_diff_ratio: float = 0.12,
) -> str:
    """Burn subtitles into a video file.

    Args:
        video_path: Input video file.
        subtitle_path: Subtitle file (.srt, .ass).
        output_path: Output video file path.
        subtitle_mode: 'soft' (embedded track) or 'hard' (burned in).
        quality: Video quality (ultra, high, medium, low).
        layout: Deprecated compatibility arg; ignored because backend 1.4.x
            does not support synthesize-time layout control.
        render_mode: Deprecated compatibility arg; ignored because backend 1.4.x
            does not support synthesize-time style selection.
        style: Deprecated compatibility arg; ignored because backend 1.4.x does
            not support synthesize-time style presets.
        style_override: Deprecated compatibility arg; ignored because backend
            1.4.x does not support synthesize-time style overrides.
        font_file: Deprecated compatibility arg; ignored because backend 1.4.x
            does not support synthesize-time custom fonts.
        review_script: Optional reference script/transcript. When supplied, the
            harness checks subtitle/script drift before final synthesize.
        max_script_diff_ratio: Maximum allowed normalized subtitle/script drift.

    Returns:
        Output video file path.
    """
    if review_script:
        ensure_subtitle_consistency(
            subtitle_path,
            review_script,
            max_diff_ratio=max_script_diff_ratio,
        )
    args = ["synthesize", video_path, "-s", subtitle_path,
            "--subtitle-mode", subtitle_mode, "--quality", quality]
    if output_path:
        args += ["-o", output_path]
    return run_quiet(args)
