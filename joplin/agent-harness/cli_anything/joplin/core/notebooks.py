from cli_anything.joplin.core.notes import _supports_permanent
from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command, run_joplin_json


def list_notebooks(
    config: BackendConfig,
    limit: int | None = None,
    sort: str | None = None,
    reverse: bool = False,
    long: bool = False,
) -> dict:
    args = ["ls", "/", "--format", "json"]
    if limit:
        args += ["--limit", str(limit)]
    if sort:
        args += ["--sort", sort]
    if reverse:
        args.append("--reverse")
    if long:
        args.append("--long")
    return run_joplin_json(args, config)


def create_notebook(config: BackendConfig, title: str, parent: str | None = None) -> dict:
    args = ["mkbook", title]
    if parent:
        args += ["-p", parent]
    return run_joplin_command(args, config)


def use_notebook(config: BackendConfig, notebook: str) -> dict:
    return run_joplin_command(["use", notebook], config)


def remove_notebook(config: BackendConfig, notebook: str, force: bool = True, permanent: bool = False) -> dict:
    """Delete a notebook.

    ``--permanent`` requires Joplin terminal CLI >= 3.0.  Joplin silently
    ignores unknown options, so we probe ``joplin help rmbook`` first and
    refuse rather than silently turn a permanent delete into a trash move.
    """
    args = ["rmbook", notebook]
    if force:
        args.append("--force")
    if permanent:
        if not _supports_permanent(config, "rmbook"):
            raise RuntimeError(
                "Joplin CLI `rmbook` does not advertise `--permanent` "
                "(requires Joplin terminal CLI >= 3.0). Refusing to send the "
                "flag because Joplin would silently ignore it and move the "
                "notebook to the trash instead of deleting it permanently. "
                "Upgrade Joplin or omit `--permanent` to use a soft delete."
            )
        args.append("--permanent")
    return run_joplin_command(args, config)
