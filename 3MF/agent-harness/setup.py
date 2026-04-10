#!/usr/bin/env python3
"""
setup.py for cli-anything-3mf

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/threemf/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-3mf",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for 3MF — Detect and resize cylindrical holes, repair meshes, compare 3D printing files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "trimesh>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-3mf=cli_anything.threemf.threemf_cli:main",
        ],
    },
    package_data={
        "cli_anything.threemf": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
