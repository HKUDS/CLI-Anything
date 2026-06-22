#!/usr/bin/env python3
"""setup.py for cli-anything-eval."""

from setuptools import setup, find_namespace_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-eval",
    version="0.1.0",
    author="cli-anything contributors",
    description="Shared eval/benchmark framework for CLI-Anything harnesses.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=["click>=8.0.0"],
    extras_require={"dev": ["pytest>=7.0.0"]},
    entry_points={"console_scripts": ["cli-anything-eval=cli_anything.eval.cli:main"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
    zip_safe=False,
)
