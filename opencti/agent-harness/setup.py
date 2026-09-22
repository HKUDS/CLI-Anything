#!/usr/bin/env python3
"""
Setup script for cli-anything-opencti

Install (dev mode):
    pip install -e .

Build:
    python -m build

Publish:
    twine upload dist/*
"""

from pathlib import Path
from setuptools import setup, find_namespace_packages

ROOT = Path(__file__).parent
README = ROOT / "cli_anything/opencti/README.md"

long_description = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="cli-anything-opencti",
    version="1.0.0",
    description="CLI harness for OpenCTI threat intelligence platform GraphQL API v7",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="CLI-Anything contributors",
    url="https://github.com/HKUDS/CLI-Anything",
    license="Apache-2.0",

    python_requires=">=3.10",
    packages=find_namespace_packages(include=("cli_anything.*",)),
    include_package_data=True,
    package_data={
        "cli_anything.opencti": ["skills/*.md", "README.md"],
    },
    install_requires=[
        "click>=8.0",
        "prompt-toolkit>=3.0",
        "requests>=2.28",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-opencti=cli_anything.opencti.opencti_cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Terminals",
    ],
)
