# PyPI Publishing and Installation (Phase 7)

After building and testing the CLI, make it installable and discoverable.

All cli-anything CLIs use **PEP 420 namespace packages** under the shared
`cli_anything` namespace. This allows multiple CLI packages to be installed
side-by-side in the same Python environment without conflicts.

## 1. Package Structure

```
agent-harness/
├── setup.py
└── cli_anything/           # NO __init__.py here (namespace package)
    └── <software>/         # e.g., gimp, blender, audacity
        ├── __init__.py     # HAS __init__.py (regular sub-package)
        ├── <software>_cli.py
        ├── core/
        ├── utils/
        └── tests/
```

The key rule: `cli_anything/` has **no** `__init__.py`. Each sub-package
(`gimp/`, `blender/`, etc.) **does** have `__init__.py`. This is what
enables multiple packages to contribute to the same namespace.

## 2. setup.py Template

Create `setup.py` in the `agent-harness/` directory:

```python
from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-<software>",
    version="1.0.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        # Add Python library dependencies here
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-<software>=cli_anything.<software>.<software>_cli:main",
        ],
    },
    python_requires=">=3.10",
)
```

**Important details:**
- Use `find_namespace_packages`, NOT `find_packages`
- Use `include=["cli_anything.*"]` to scope discovery
- Entry point format: `cli_anything.<software>.<software>_cli:main`
- The **system package** (LibreOffice, Blender, etc.) is a **hard dependency**
  that cannot be expressed in `install_requires`. Document it in README.md and
  have the backend module raise a clear error with install instructions:
  ```python
  # In utils/<software>_backend.py
  def find_<software>():
      path = shutil.which("<software>")
      if path:
          return path
      raise RuntimeError(
          "<Software> is not installed. Install it with:\n"
          "  apt install <software>   # Debian/Ubuntu\n"
          "  brew install <software>  # macOS"
      )
  ```

## 3. Import Convention

All imports use the `cli_anything.<software>` prefix:

```python
from cli_anything.gimp.core.project import create_project
from cli_anything.gimp.core.session import Session
from cli_anything.blender.core.scene import create_scene
```

## 4. Verification Steps

**Test local installation:**
```bash
cd /root/cli-anything/<software>/agent-harness
pip install -e .
```

**Verify PATH installation:**
```bash
which cli-anything-<software>
cli-anything-<software> --help
```

**Run tests against the installed command:**
```bash
cd /root/cli-anything/<software>/agent-harness
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s
```
The output must show `[_resolve_cli] Using installed command: /path/to/cli-anything-<software>`
confirming subprocess tests ran against the real installed binary, not a module fallback.

**Verify namespace works across packages** (when multiple CLIs installed):
```python
import cli_anything.gimp
import cli_anything.blender
# Both resolve to their respective source directories
```

## Why Namespace Packages

- Multiple CLIs coexist in the same Python environment without conflicts
- Clean, organized imports under a single `cli_anything` namespace
- Each CLI is independently installable/uninstallable via pip
- Agents can discover all installed CLIs via `cli_anything.*`
- Standard Python packaging — no hacks or workarounds
