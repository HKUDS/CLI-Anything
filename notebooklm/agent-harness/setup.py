#!/usr/bin/env python3
"""
setup.py for cli-anything-notebooklm

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/notebooklm/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-notebooklm",
    version="0.1.0",
    author="cli-anything contributors",
    author_email="",
    description="Experimental CLI harness for NotebookLM via an installed notebooklm CLI. Unofficial and community-maintained.",
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
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-notebooklm=cli_anything.notebooklm.notebooklm_cli:main",
        ],
    },
    package_data={
        "cli_anything.notebooklm": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
