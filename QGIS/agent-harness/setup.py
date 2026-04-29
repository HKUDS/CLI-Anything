#!/usr/bin/env python3
"""setup.py for cli-anything-qgis."""

from setuptools import find_namespace_packages, setup

with open("cli_anything/qgis/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-qgis",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for QGIS using PyQGIS for project authoring and qgis_process for exports and processing.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: GIS",
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
            "jinja2>=3.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-qgis=cli_anything.qgis.qgis_cli:main",
        ],
    },
    package_data={
        "cli_anything.qgis": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
