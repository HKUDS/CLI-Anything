from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def run_sync(
    config: BackendConfig,
    target: str | None = None,
    upgrade: bool = False,
    use_lock: str | None = None,
) -> dict:
    args = ["sync"]
    if target:
        args += ["--target", target]
    if upgrade:
        args.append("--upgrade")
    if use_lock is not None:
        args += ["--use-lock", use_lock]
    return run_joplin_command(args, config, timeout=600)
