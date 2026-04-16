from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_NAME = "cli-anything-zotero"
PACKAGE_VERSION = "0.1.0"


def _handle_metadata_query(argv: list[str]) -> bool:
    if len(argv) != 2:
        return False
    if argv[1] == "--name":
        print(PACKAGE_NAME)
        return True
    if argv[1] == "--version":
        print(PACKAGE_VERSION)
        return True
    return False


if __name__ == "__main__" and _handle_metadata_query(sys.argv):
    raise SystemExit(0)

from setuptools import find_namespace_packages, setup


ROOT = Path(__file__).parent
README = ROOT / "cli_anything" / "zotero" / "README.md"
LONG_DESCRIPTION = README.read_text(encoding="utf-8") if README.exists() else ""


setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    author="cli-anything contributors",
    author_email="",
    description="Agent-native CLI harness for Zotero using SQLite, connector, and Local API backends",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-zotero=cli_anything.zotero.zotero_cli:entrypoint",
        ],
    },
    package_data={
        "cli_anything.zotero": [
            "README.md",
            "skills/SKILL.md",
            "tests/TEST.md",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
