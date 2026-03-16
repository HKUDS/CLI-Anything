# CLI-Anything Implementation Patterns

## 1. Backend Integration (utils/<software>_backend.py)
```python
import shutil
import subprocess
import os

def find_software():
    path = shutil.which("software-cmd")
    if path:
        return path
    raise RuntimeError(
        "Software is not installed. Install it with:\n"
        "  apt install software-package   # Debian/Ubuntu\n"
        "  brew install software-package  # macOS"
    )

def run_operation(input_path, output_path):
    cmd = find_software()
    result = subprocess.run(
        [cmd, "--headless", "--input", input_path, "--output", output_path],
        capture_output=True, text=True, check=True
    )
    return {"status": "success", "output": output_path}
```

## 2. CLI Entry Point with REPL ( <software>_cli.py )
```python
import click
from .utils.repl_skin import ReplSkin

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)

@cli.command()
def repl():
    skin = ReplSkin("SoftwareName", version="1.0.0")
    skin.print_banner()
    # ... REPL loop using prompt_toolkit
```

## 3. Subprocess Test Helper (_resolve_cli)
Put this in `tests/test_full_e2e.py`:
```python
import shutil
import os
import sys
import subprocess

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    return [sys.executable, "-m", module]

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-<software>")

    def _run(self, args):
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True)
```

## 4. Output Verification (E2E Tests)
```python
def test_export_verification(tmp_dir):
    # ... run export ...
    assert os.path.exists(output_file)
    assert os.path.getsize(output_file) > 1000
    with open(output_file, "rb") as f:
        # Check PDF Magic Bytes
        assert f.read(5) == b"%PDF-" 
```
