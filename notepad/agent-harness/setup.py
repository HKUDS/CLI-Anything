#!/usr/bin/env python3
"""setup.py for cli-anything-notepad."""

from setuptools import setup, find_namespace_packages

with open("cli_anything/notepad/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-notepad",
    version="0.1.0",
    author="Chris",
    description="Windows Notepad via UI Automation - tree, menus, invoke, set text",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.10",
    install_requires=["click>=8.0.0"],
    extras_require={"dev": ["pytest>=7.0.0"], "uia": ["uiautomation>=2.0"]},
    entry_points={"console_scripts": ["cli-anything-notepad=cli_anything.notepad.notepad_cli:main"]},
    package_data={"cli_anything.notepad": ["skills/*.md"]},
    include_package_data=True,
    zip_safe=False,
)
