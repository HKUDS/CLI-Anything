from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command


def config_get(config: BackendConfig, key: str, verbose: bool = False) -> dict:
    args = ["config", key]
    if verbose:
        args.append("--verbose")
    return run_joplin_command(args, config)


def config_set(config: BackendConfig, key: str, value: str) -> dict:
    return run_joplin_command(["config", key, value], config)


def config_list(config: BackendConfig, verbose: bool = False) -> dict:
    args = ["config"]
    if verbose:
        args.append("--verbose")
    return run_joplin_command(args, config)


def config_export(config: BackendConfig, verbose: bool = False) -> dict:
    args = ["config", "--export"]
    if verbose:
        args.append("--verbose")
    return run_joplin_command(args, config)


def config_import_file(config: BackendConfig, file_path: str) -> dict:
    return run_joplin_command(["config", "--import-file", file_path], config)
