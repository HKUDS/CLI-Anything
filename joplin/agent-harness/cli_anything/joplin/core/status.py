from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def get_status(config: BackendConfig) -> dict:
    return run_joplin_command(["status"], config)


def restore_items(config: BackendConfig, pattern: str) -> dict:
    return run_joplin_command(["restore", pattern], config)
