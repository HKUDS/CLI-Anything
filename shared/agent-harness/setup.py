#!/usr/bin/env python3
from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-shared",
    version="1.0.0",
    author="cli-anything contributors",
    description="Shared utilities for CLI-Anything harnesses",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    zip_safe=False,
)
