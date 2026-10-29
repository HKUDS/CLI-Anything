#!/usr/bin/env python3
"""setup.py for cli-anything-gatekeeper

Install with: pip install -e .
"""

from setuptools import find_namespace_packages, setup

with open("cli_anything/gatekeeper/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-gatekeeper",
    version="1.0.0",
    author="Ali Emadi",
    author_email="ali@gatekeeper.blog",
    description="Agent-native CLI for Gatekeeper AI — evaluate supplier bids against an RFP (compliance, pricing, risk, ranking)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.gatekeeper.blog",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Office/Business",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "pypdf>=4.0.0",
    ],
    extras_require={"dev": ["pytest>=7.0.0", "python-docx>=1.0", "openpyxl>=3.1", "reportlab>=4.0"]},
    entry_points={"console_scripts": ["cli-anything-gatekeeper=cli_anything.gatekeeper.gatekeeper_cli:main"]},
    package_data={"cli_anything.gatekeeper": ["skills/*.md", "README.md"]},
    include_package_data=True,
    zip_safe=False,
)
