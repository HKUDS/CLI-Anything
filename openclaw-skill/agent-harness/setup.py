#!/usr/bin/env python3
"""
setup.py for cli-anything-openclaw

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/openclaw/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-openclaw",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description=(
        "OpenClaw Macro System — A layered CLI that converts GUI workflows into "
        "parameterized, agent-callable macros. Requires: PyYAML, click, prompt-toolkit."
    ),
    long_description=long_description,
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
        "PyYAML>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-openclaw=cli_anything.openclaw.openclaw_cli:cli",
        ],
    },
    package_data={
        "cli_anything.openclaw": ["skills/*.md", "macro_definitions/*.yaml", "macro_definitions/examples/*.yaml"],
    },
    include_package_data=True,
    zip_safe=False,
)
