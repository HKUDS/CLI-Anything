#!/usr/bin/env python3
from setuptools import setup, find_namespace_packages

with open("cli_anything/git/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-git",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Git. Requires: git",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=["click>=8.0.0","prompt-toolkit>=3.0.0"],
    extras_require={"dev":["pytest>=7.0.0","pytest-cov>=4.0.0"]},
    entry_points={"console_scripts":["cli-anything-git=cli_anything/git.git_cli:main"]},
    package_data={"cli_anything/git":["skills/*.md"]},
    include_package_data=True,
    zip_safe=False,
)
