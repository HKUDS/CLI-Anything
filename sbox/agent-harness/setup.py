#!/usr/bin/env python3
"""
setup.py for cli-anything-sbox

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/sbox/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-sbox",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for s&box (Source 2): scenes, prefabs, materials, sounds, codegen, asset graph, project validation. Recommended: s&box installed via Steam.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Games/Entertainment",
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
        "Pillow>=10.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-sbox=cli_anything.sbox.sbox_cli:main",
        ],
    },
    package_data={
        "cli_anything.sbox": ["skills/*.md", "tests/*.md", "README.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
