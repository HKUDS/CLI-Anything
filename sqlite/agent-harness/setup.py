"""Package the SQLite CLI harness."""

from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-sqlite",
    version="1.0.0",
    description="Structured SQLite inspection, queries, transactions, CSV workflows and backups",
    author="CLI-Anything contributors",
    license="Apache-2.0",
    url="https://github.com/HKUDS/CLI-Anything",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["*.tests"]),
    install_requires=["click>=8.0", "prompt-toolkit>=3.0"],
    extras_require={"dev": ["pytest>=7.0", "build"]},
    entry_points={"console_scripts": [
        "cli-anything-sqlite=cli_anything.sqlite.sqlite_cli:main",
    ]},
    package_data={"cli_anything.sqlite": ["skills/*.md", "README.md"]},
)
