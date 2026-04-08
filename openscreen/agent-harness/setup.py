#!/usr/bin/env python3
from setuptools import setup, find_namespace_packages

with open("cli_anything/openscreen/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-openscreen",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description=(
        "CLI harness for Openscreen — screen recording editor. "
        "Record, zoom, speed-ramp, annotate, crop, and export "
        "screen captures via CLI with full undo/redo."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Video :: Non-Linear Editor",
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
        "dev": ["pytest>=7.0.0", "pytest-cov>=4.0.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-openscreen=cli_anything.openscreen.openscreen_cli:cli",
        ],
    },
    package_data={
        "cli_anything.openscreen": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
