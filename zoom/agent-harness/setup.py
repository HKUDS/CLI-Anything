#!/usr/bin/env python3
"""
setup.py for cli-anything-zoom

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-zoom",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Zoom - Meeting management via Zoom REST API (OAuth2). Requires: Zoom account + OAuth app credentials",
    long_description=open("cli_anything/zoom/README.md", "r", encoding="utf-8").read()
    if __import__("os").path.exists("cli_anything/zoom/README.md")
    else "CLI harness for Zoom meeting management.",
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Conferencing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
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
            "cli-anything-zoom=cli_anything.zoom.zoom_cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
