#!/usr/bin/env python3
"""
Setup script for cli-anything-n8n

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
README = ROOT / "cli_anything/n8n/README.md"

long_description = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="cli-anything-n8n",
    version="2.4.7",
    description="CLI harness for n8n workflow automation — n8n REST API v1.1.1",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="Juan Jose Sanchez Bernal",
    author_email="info@webcomunica.solutions",
    url="https://github.com/HKUDS/CLI-Anything",

    project_urls={
        "Source": "https://github.com/HKUDS/CLI-Anything",
        "Tracker": "https://github.com/HKUDS/CLI-Anything/issues",
        "PyPI": "https://pypi.org/project/cli-anything-n8n/",
    },

    license="MIT",

    packages=find_namespace_packages(include=("cli_anything.*",)),

    python_requires=">=3.10",

    install_requires=[
        "click>=8.1",
        "prompt-toolkit>=3.0",
        "requests>=2.28",
    ],

    extras_require={
        "dev": [
            "pytest>=7",
            "pytest-cov>=4",
        ],
    },

    entry_points={
        "console_scripts": [
            "cli-anything-n8n=cli_anything.n8n.n8n_cli:main",
        ],
    },
    package_data={
        "cli_anything.n8n": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,

    keywords=[
        "cli",
        "n8n",
        "workflow",
        "automation",
        "cli-anything",
    ],

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",

        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
