from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def list_tags(config: BackendConfig) -> dict:
    return run_joplin_command(["tag", "list"], config)


def add_tag(config: BackendConfig, tag: str, note: str) -> dict:
    return run_joplin_command(["tag", "add", tag, note], config)


def remove_tag(config: BackendConfig, tag: str, note: str) -> dict:
    return run_joplin_command(["tag", "remove", tag, note], config)


def note_tags(config: BackendConfig, note: str) -> dict:
    return run_joplin_command(["tag", "notetags", note], config)


def tag_notes(config: BackendConfig, tag: str) -> dict:
    return run_joplin_command(["tag", "list", tag], config)
