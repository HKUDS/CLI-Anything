#!/usr/bin/env python3
"""
setup.py for cli-anything-baota

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/baota/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-baota",
    version="1.0.0",
    author="cli-anything-contributors",
    author_email="",
    description="CLI harness for 宝塔面板 (Baota Panel) - Linux server management panel",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.7",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-baota=cli_anything.baota.baota_cli:main",
        ],
    },
    package_data={
        "cli_anything.baota": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
