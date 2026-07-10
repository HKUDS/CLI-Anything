"""Regression test for issue #278: cli-anything-n8n REPL must not TypeError on print_banner.

The bug: n8n_cli.py called print_banner(base_url or "(not configured)") but
print_banner takes no arguments, so invoking `cli-anything-n8n` with no
subcommand raised TypeError before the REPL prompt was ever reached.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from cli_anything.n8n import n8n_cli
from cli_anything.n8n.utils import repl_skin


def test_print_banner_takes_no_args():
    """The wrapper at repl_skin.print_banner accepts no positional args; callers
    must not pass any."""
    sig = inspect.signature(repl_skin.print_banner)
    assert len(sig.parameters) == 0, (
        f"repl_skin.print_banner() takes no positional args; callers must call "
        f"it with no arguments. Got params: {list(sig.parameters)}"
    )


def test_n8n_cli_repl_does_not_pass_args_to_print_banner():
    """The REPL invocation site in n8n_cli.py must call print_banner() with no
    arguments. Reading the source guards against the call signature drifting
    out of sync with the function definition again."""
    src = Path(n8n_cli.__file__).read_text()
    assert "print_banner(base_url" not in src, (
        "n8n_cli.py is passing base_url to print_banner(); the function takes "
        "no arguments. See issue #278."
    )
