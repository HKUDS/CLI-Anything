from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def search(config: BackendConfig, pattern: str, notebook: str | None = None) -> dict:
    args = ["search", pattern]
    if notebook:
        args.append(notebook)
    return run_joplin_command(args, config)
