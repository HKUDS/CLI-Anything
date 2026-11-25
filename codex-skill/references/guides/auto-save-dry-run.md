# Auto-Save + --dry-run for One-Shot Commands

Session-based CLIs must auto-save after one-shot mutations and support `--dry-run` to suppress it.

## Problem

One-shot commands like `cli-anything-kdenlive --project p.json bin import video.mp4` mutate the in-memory project but never call `save_session()`. The project file on disk is unchanged when the process exits — changes are silently lost.

## Solution

Two additions to `<software>_cli.py`:

### 1. Add `--dry-run` to the main CLI group

```python
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to project file")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Run command without saving changes to disk")
@click.pass_context
def cli(ctx, use_json, project_path, dry_run):
    ...
```

### 2. Add `@cli.result_callback()` after the group

```python
@cli.result_callback()
def auto_save_on_exit(result, use_json, project_path, dry_run, **kwargs):
    """Auto-save project after one-shot commands if state was modified."""
    if _repl_mode:
        return
    if dry_run:
        return
    sess = get_session()
    if sess.has_project() and sess._modified and sess.project_path:
        try:
            sess.save_session()
        except Exception as e:
            click.echo(f"Warning: Auto-save failed: {e}", err=True)
```

**How it works:**
- `result_callback` fires once after the CLI group's command chain completes
- Checks `_repl_mode` (skip in REPL — user saves manually), `dry_run` (skip if set), and `sess._modified` (skip if nothing changed)
- Calls `sess.save_session()` which uses atomic `_locked_save_json` (see [`session-locking.md`](session-locking.md))
- Does NOT fire if `sys.exit(1)` was called in `handle_error` (error path) — correct behavior

### Alternative: `ctx.call_on_close` pattern

For harnesses that open the session inline (not via a global singleton), use a closure instead:

```python
def cli(ctx, use_json, project_path, dry_run):
    ...
    if project_path:
        sess = get_session()
        proj = proj_mod.open_project(project_path)
        sess.set_project(proj, project_path)

        def _auto_save():
            if dry_run:
                return
            if sess._modified and sess.project_path and not _repl_mode:
                sess.save_session()

        ctx.call_on_close(_auto_save)
```

## `--dry-run` semantics

| Mode | Behavior |
|------|----------|
| One-shot (default) | Command executes, output is printed, project is auto-saved |
| One-shot + `--dry-run` | Command executes, output is printed, project is **not** saved |
| REPL | `--dry-run` is accepted but ignored (REPL never auto-saves) |

## When this applies

**Required** for any harness where:
- `core/session.py` exists with `save_session()` and `_modified` tracking
- The CLI accepts a `--project` flag to load a file-backed project
- Commands call `sess.snapshot()` before mutations

**Does not apply** to stateless API clients, service wrappers, or harnesses without a persistent project file.
