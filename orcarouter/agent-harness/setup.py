#!/usr/bin/env python3
"""
setup.py for cli-anything-orcarouter

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/orcarouter/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-orcarouter",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description=(
        "OrcaRouter CLI — OpenAI-compatible AI gateway with two authentication "
        "choices: an existing API key, or OAuth 2.0 + PKCE sign-in."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "License :: OSI Approved :: Apache Software License",
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
            "cli-anything-orcarouter=cli_anything.orcarouter.orcarouter_cli:main",
        ],
    },
    package_data={
        "cli_anything.orcarouter": [
            "skills/*.md",
            "ui/*.html",
            "ui/*.css",
            "ui/*.js",
            "ui/*.png",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
