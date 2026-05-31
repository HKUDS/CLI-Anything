from cli_anything.joplin.utils.joplin_backend import BackendConfig, run_joplin_command, run_joplin_json

# Cache feature support per (binary, command) pair.  Joplin's CLI silently
# ignores unknown options instead of erroring out, so we must probe `help`
# before emitting --permanent, otherwise a stale binary would happily report
# success while only moving the item to trash.
_PERMANENT_FLAG_SUPPORT_CACHE: dict[str, bool] = {}


def _supports_permanent(config: BackendConfig, command_name: str) -> bool:
    """Return True if the installed Joplin CLI advertises ``--permanent`` for
    ``command_name`` (`rmnote` / `rmbook`).  Joplin >=3.0 supports it; older
    builds do not list it in ``joplin help <command>``.

    Result is cached per (binary, command) so we only probe once per process.
    """
    key = f"{config.binary or 'joplin'}:{command_name}"
    if key in _PERMANENT_FLAG_SUPPORT_CACHE:
        return _PERMANENT_FLAG_SUPPORT_CACHE[key]
    try:
        result = run_joplin_command(["help", command_name], config, timeout=30)
        supported = "--permanent" in (result.get("stdout") or "")
    except Exception:
        supported = False
    _PERMANENT_FLAG_SUPPORT_CACHE[key] = supported
    return supported


def list_notes(
    config: BackendConfig,
    pattern: str | None = None,
    limit: int | None = None,
    sort: str | None = None,
    reverse: bool = False,
    item_type: str | None = None,
    long: bool = False,
) -> dict:
    args = ["ls"]
    if pattern:
        args.append(pattern)
    if limit:
        args += ["-n", str(limit)]
    if sort:
        args += ["--sort", sort]
    if reverse:
        args.append("--reverse")
    if item_type:
        args += ["--type", item_type]
    if long:
        args.append("--long")
    args += ["--format", "json"]
    return run_joplin_json(args, config)


def create_note(config: BackendConfig, title: str) -> dict:
    return run_joplin_command(["mknote", title], config)


def set_note_field(config: BackendConfig, note_ref: str, field: str, value: str) -> dict:
    return run_joplin_command(["set", note_ref, field, value], config)


def get_note(config: BackendConfig, note_ref: str, verbose: bool = False) -> dict:
    args = ["cat", note_ref]
    if verbose:
        args.append("-v")
    return run_joplin_command(args, config)


def remove_note(config: BackendConfig, note_ref: str, force: bool = True, permanent: bool = False) -> dict:
    """Delete a note.

    ``--permanent`` requires Joplin terminal CLI >= 3.0.  Because the Joplin
    CLI silently ignores unknown options, we explicitly probe ``joplin help
    rmnote`` first when the caller opts into ``permanent=True``; if the flag
    is not advertised we raise rather than silently letting the note merely
    go to the trash.
    """
    args = ["rmnote", note_ref]
    if force:
        args.append("--force")
    if permanent:
        if not _supports_permanent(config, "rmnote"):
            raise RuntimeError(
                "Joplin CLI `rmnote` does not advertise `--permanent` "
                "(requires Joplin terminal CLI >= 3.0). Refusing to send the "
                "flag because Joplin would silently ignore it and move the "
                "note to the trash instead of deleting it permanently. "
                "Upgrade Joplin or omit `--permanent` to use a soft delete."
            )
        args.append("--permanent")
    return run_joplin_command(args, config)


def copy_note(config: BackendConfig, note_ref: str, notebook: str | None = None) -> dict:
    args = ["cp", note_ref]
    if notebook:
        args.append(notebook)
    return run_joplin_command(args, config)


def move_note(config: BackendConfig, item: str, notebook: str) -> dict:
    return run_joplin_command(["mv", item, notebook], config)


def rename_note(config: BackendConfig, item: str, new_name: str) -> dict:
    return run_joplin_command(["ren", item, new_name], config)


def duplicate_note(config: BackendConfig, note_ref: str, notebook: str | None = None) -> dict:
    return copy_note(config, note_ref, notebook=notebook)
