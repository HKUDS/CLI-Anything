from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command, run_joplin_json


def create_todo(config: BackendConfig, title: str) -> dict:
    return run_joplin_command(["mktodo", title], config)


def toggle_todo(config: BackendConfig, pattern: str) -> dict:
    return run_joplin_command(["todo", "toggle", pattern], config)


def clear_todo(config: BackendConfig, pattern: str) -> dict:
    return run_joplin_command(["todo", "clear", pattern], config)


def mark_done(config: BackendConfig, note_ref: str) -> dict:
    return run_joplin_command(["done", note_ref], config)


def mark_undone(config: BackendConfig, note_ref: str) -> dict:
    return run_joplin_command(["undone", note_ref], config)


def list_todos(
    config: BackendConfig,
    limit: int | None = None,
    sort: str | None = None,
    reverse: bool = False,
    long: bool = False,
) -> dict:
    args = ["ls", "--type", "t", "--format", "json"]
    if limit:
        args += ["-n", str(limit)]
    if sort:
        args += ["--sort", sort]
    if reverse:
        args.append("--reverse")
    if long:
        args.append("--long")
    return run_joplin_json(args, config)
