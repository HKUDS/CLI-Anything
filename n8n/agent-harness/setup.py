#!/usr/bin/env python3
"""setup.py for cli-anything-n8n"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/n8n/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-n8n",
    version="2.4.4",
    author="Juan Jose Sanchez Bernal",
    author_email="info@webcomunica.solutions",
    description="CLI harness for n8n workflow automation — 55+ commands, verified against n8n API v1.1.1. Requires: N8N_BASE_URL, N8N_API_KEY",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
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
            "cli-anything-n8n=cli_anything.n8n.n8n_cli:main",
        ],
    },
    package_data={
        "cli_anything.n8n": ["skills/*.md", "README.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
