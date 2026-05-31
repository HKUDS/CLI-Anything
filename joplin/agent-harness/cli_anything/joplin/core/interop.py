from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def import_data(
    config: BackendConfig,
    path: str,
    notebook: str | None = None,
    fmt: str | None = None,
    force: bool = False,
    output_format: str | None = None,
) -> dict:
    args = ["import", path]
    if notebook:
        args.append(notebook)
    if fmt:
        args += ["--format", fmt]
    if force:
        args.append("--force")
    if output_format:
        args += ["--output-format", output_format]
    return run_joplin_command(args, config, timeout=600)


def export_data(config: BackendConfig, path: str, fmt: str = "jex", note: str | None = None, notebook: str | None = None) -> dict:
    args = ["export", path, "--format", fmt]
    if note:
        args += ["--note", note]
    if notebook:
        args += ["--notebook", notebook]
    return run_joplin_command(args, config, timeout=600)
