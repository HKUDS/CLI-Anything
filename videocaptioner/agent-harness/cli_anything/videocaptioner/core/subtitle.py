"""Subtitle processing — optimize and translate subtitle files."""

from cli_anything.videocaptioner.utils.vc_backend import run_quiet


def process_subtitle(
    input_path: str,
    output_path: str | None = None,
    translator: str | None = None,
    target_language: str | None = None,
    format: str = "srt",
    layout: str | None = None,
    no_optimize: bool = False,
    no_translate: bool = False,
    no_split: bool = False,
    reflect: bool = False,
    prompt: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
) -> str:
    """Optimize and/or translate a subtitle file.

    Args:
        input_path: Subtitle file (.srt, .ass, .vtt).
        output_path: Output file or directory path.
        translator: Translation service (llm, bing, google).
        target_language: Target language BCP 47 code.
        format: Output format (srt, ass, txt, json).
        layout: Bilingual layout (target-above, source-above, target-only, source-only).
        no_optimize: Skip LLM optimization.
        no_translate: Skip translation.
        no_split: Skip re-segmentation.
        reflect: Enable reflective translation (LLM only).
        prompt: Custom LLM prompt.
        api_key: LLM API key.
        api_base: LLM API base URL.
        model: LLM model name.

    Returns:
        Output file path.
    """
    args = ["subtitle", input_path, "--format", format]
    if output_path:
        args += ["-o", output_path]
    if translator:
        args += ["--translator", translator]
    if target_language:
        args += ["--target-language", target_language]
    if layout:
        args += ["--layout", layout]
    if no_optimize:
        args.append("--no-optimize")
    if no_translate:
        args.append("--no-translate")
    if no_split:
        args.append("--no-split")
    if reflect:
        args.append("--reflect")
    if prompt:
        args += ["--prompt", prompt]
    if api_key:
        args += ["--api-key", api_key]
    if api_base:
        args += ["--api-base", api_base]
    if model:
        args += ["--model", model]
    return run_quiet(args)
