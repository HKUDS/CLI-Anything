#!/usr/bin/env python3
"""
setup.py for cli-anything-dify-workflow

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from pathlib import Path
from setuptools import setup, find_namespace_packages

ROOT = Path(__file__).parent
README = ROOT / "cli_anything/dify_workflow/README.md"


def read_readme() -> str:
    try:
        return README.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "CLI-Anything wrapper for the Dify Workflow CLI."


setup(
    name="cli-anything-dify-workflow",
    version="0.1.0",
    author="Akabane71",
    description="CLI-Anything wrapper for the Dify Workflow CLI and DSL editor",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
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
            "cli-anything-dify-workflow=cli_anything.dify_workflow.dify_workflow_cli:main",
        ],
    },
    package_data={
        "cli_anything.dify_workflow": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
