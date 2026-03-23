#!/usr/bin/env python3
"""
setup.py for cli-anything-browser

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/browser/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-browser",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Browser automation via DOMShell MCP server. Maps Chrome's Accessibility Tree to a virtual filesystem for agent-native browser automation.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Testing",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
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
        "mcp>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-browser=cli_anything.browser.browser_cli:main",
        ],
    },
    package_data={
        "cli_anything.browser": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
