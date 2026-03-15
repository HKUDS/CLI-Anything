#!/usr/bin/env python3
"""
Setup configuration for cli-anything-anygen.

Install (editable):
    pip install -e .

Build package:
    python -m build

Upload to PyPI:
    twine upload dist/*
"""

from pathlib import Path
from setuptools import setup, find_namespace_packages

BASE_DIR = Path(__file__).parent

def read_readme():
    readme_path = BASE_DIR / "cli_anything/anygen/README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return ""

setup(
    name="cli-anything-anygen",
    version="1.0.0",
    description="CLI harness for AnyGen OpenAPI - Generate docs, slides, websites and more via AnyGen cloud API.",
    long_description=read_readme(),
    long_description_content_type="text/markdown",

    author="cli-anything contributors",
    author_email="",

    url="https://github.com/HKUDS/CLI-Anything",

    packages=find_namespace_packages(include=("cli_anything.*",)),

    python_requires=">=3.10",

    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "prompt-toolkit>=3.0",
    ],

    extras_require={
        "dev": [
            "pytest>=7",
            "pytest-cov>=4",
        ],
    },

    entry_points={
        "console_scripts": [
            "cli-anything-anygen=cli_anything.anygen.anygen_cli:main",
        ],
    },

    include_package_data=True,
    zip_safe=False,

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",

        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
