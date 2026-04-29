"""Full pipeline — transcribe → optimize → translate → synthesize in one command."""

from cli_anything.videocaptioner.utils.vc_backend import run_quiet


def process(
    input_path: str,
    output_path: str | None = None,
    asr: str = "bijian",
    language: str = "auto",
    translator: str | None = None,
    target_language: str | None = None,
    subtitle_mode: str = "soft",
    quality: str = "medium",
    layout: str | None = None,
    style: str | None = None,
    style_override: str | None = None,
    render_mode: str | None = None,
    no_optimize: bool = False,
    no_translate: bool = False,
    no_split: bool = False,
    no_synthesize: bool = False,
    reflect: bool = False,
    prompt: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
) -> str:
    """Run the complete captioning pipeline.

    Args:
        input_path: Video or audio file path.
        output_path: Output file or directory path.
        asr: ASR engine.
        language: Source language.
        translator: Translation service.
        target_language: Target language.
        subtitle_mode: soft or hard.
        quality: Video quality.
        layout: Bilingual layout.
        style: Style preset name.
        style_override: Inline JSON style override.
        render_mode: ass or rounded.
        no_optimize: Skip optimization.
        no_translate: Skip translation.
        no_split: Skip re-segmentation.
        no_synthesize: Skip video synthesis.
        reflect: Reflective translation.
        prompt: Custom LLM prompt.
        api_key: LLM API key.
        api_base: LLM API base URL.
        model: LLM model name.

    Returns:
        Output file path.
    """
    args = ["process", input_path, "--asr", asr, "--language", language,
            "--subtitle-mode", subtitle_mode, "--quality", quality]
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
    if no_synthesize:
        args.append("--no-synthesize")
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
