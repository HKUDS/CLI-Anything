#!/usr/bin/env python3
"""
setup.py for cli-anything-godot

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/godot/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-godot",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Godot Engine - Game project management, scene editing, export and GDScript execution. Recommended: Godot 4.x on PATH",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
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
            "cli-anything-godot=cli_anything.godot.godot_cli:main",
        ],
    },
    package_data={
        "cli_anything.godot": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
