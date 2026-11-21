#!/usr/bin/env python3
"""
setup.py for cli-anything-alexa

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-alexa",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Amazon Alexa - control Echo devices (speak, announce, routines, music, smart home) via alexapy. Requires: Amazon account with Echo devices",
    long_description=open("cli_anything/alexa/README.md", "r", encoding="utf-8").read()
    if __import__("os").path.exists("cli_anything/alexa/README.md")
    else "CLI harness for Amazon Alexa.",
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Home Automation",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "alexapy>=1.36.0",
    ],
    extras_require={"dev": ["pytest>=7.0.0"]},
    entry_points={
        "console_scripts": [
            "cli-anything-alexa=cli_anything.alexa.alexa_cli:main",
        ],
    },
    package_data={"cli_anything.alexa": ["skills/*.md"]},
    include_package_data=True,
    zip_safe=False,
)
