from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def attach_file(config: BackendConfig, note_ref: str, file_path: str) -> dict:
    return run_joplin_command(["attach", note_ref, file_path], config, timeout=300)
