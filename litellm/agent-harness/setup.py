#!/usr/bin/env python3
"""Setup script for cli-anything-litellm."""

from pathlib import Path

from setuptools import find_namespace_packages, setup

ROOT = Path(__file__).parent
README = ROOT / "cli_anything/litellm/README.md"

setup(
    name="cli-anything-litellm",
    version="1.0.0",
    description="Agent execution CLI for LiteLLM proxy-backed app and workflow editing",
    long_description=README.read_text(encoding="utf-8") if README.exists() else "",
    long_description_content_type="text/markdown",
    author="CLI-Anything-Team",
    author_email="opensource@cli-anything.dev",
    url="https://github.com/HKUDS/CLI-Anything",
    project_urls={
        "Source": "https://github.com/HKUDS/CLI-Anything",
        "Tracker": "https://github.com/HKUDS/CLI-Anything/issues",
    },
    license="MIT",
    packages=find_namespace_packages(include=("cli_anything.*",)),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1",
        "PyYAML>=6.0",
        "requests>=2.28",
    ],
    extras_require={"dev": ["pytest>=7", "pytest-cov>=4"]},
    entry_points={
        "console_scripts": [
            "cli=cli_anything.litellm.litellm_cli:main",
        ],
    },
    package_data={"cli_anything.litellm": ["skills/*.md"]},
    include_package_data=True,
    zip_safe=False,
    keywords=["cli", "litellm", "agents", "workflow", "automation", "cli-anything"],
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
