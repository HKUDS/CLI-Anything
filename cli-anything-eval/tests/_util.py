"""Helpers to build throwaway importable task packages for tests."""

import sys


def make_tasks_pkg(tmp_path, modules):
    """Write a package of task modules under tmp_path and make it importable.

    `modules` is a dict {module_name: python_source}. Returns the dotted package name.
    """
    pkg_name = f"sample_tasks_{abs(hash(str(sorted(modules.items())))) % 100000}"
    pkg = tmp_path / pkg_name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for name, src in modules.items():
        (pkg / f"{name}.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    return pkg_name
