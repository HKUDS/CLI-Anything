#!/usr/bin/env python3
from pathlib import Path
from setuptools import setup, find_namespace_packages

ROOT = Path(__file__).parent
README = ROOT / "cli_anything/safari/README.md"


def read_readme():
    try:
        return README.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


setup(
    name="cli-anything-safari",
    version="1.0.0",

    author="CLI Anything Contributors",
    author_email="noreply@example.com",
    description="CLI harness for Safari browser automation via safari-mcp MCP server",
    long_description=read_readme(),
    long_description_content_type="text/markdown",

    url="https://github.com/HKUDS/CLI-Anything",
    project_urls={
        "Homepage": "https://github.com/HKUDS/CLI-Anything",
        "Issues": "https://github.com/HKUDS/CLI-Anything/issues",
        "Upstream": "https://github.com/achiya-automation/safari-mcp",
    },

    license="Apache-2.0",

    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",

    install_requires=[
        "click>=8.1,<9.0",
        "prompt-toolkit>=3.0,<4.0",
        "mcp>=1.0.0,<2.0.0",
    ],

    extras_require={
        "dev": [
            "pytest>=7",
            "pytest-cov>=4",
            "build",
            "twine",
        ],
    },

    entry_points={
        "console_scripts": [
            "cli-anything-safari=cli_anything.safari.safari_cli:main",
        ],
    },

    package_data={
        "cli_anything.safari": [
            "skills/*.md",
            "resources/*.json",
            "README.md",
        ],
    },

    include_package_data=True,
    zip_safe=False,

    keywords="cli browser automation mcp safari macos ai-agent",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS :: MacOS X",

        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
