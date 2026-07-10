#!/usr/bin/env python3
from pathlib import Path
from setuptools import find_namespace_packages, setup

ROOT = Path(__file__).parent
README = ROOT / "README.md"


def read_readme():
    try:
        return README.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


setup(
    name="cli-anything-web-yu-pri",
    version="0.1.0",
    author="CLI Anything Contributors",
    description="CLI harness for Japan Post Web Yu-pri label workflows",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    project_urls={
        "Homepage": "https://github.com/HKUDS/CLI-Anything",
        "Issues": "https://github.com/HKUDS/CLI-Anything/issues",
    },
    license="MIT",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1,<9.0",
        "playwright>=1.45,<2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7",
            "build",
            "twine",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-web-yu-pri=cli_anything.web_yu_pri.web_yu_pri_cli:main",
        ],
    },
    package_data={
        "cli_anything.web_yu_pri": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="cli japan-post web-yu-pri shipping labels browser-automation ai-agent",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Office/Business",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
