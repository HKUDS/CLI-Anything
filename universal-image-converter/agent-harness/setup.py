#!/usr/bin/env python3
"""
setup.py for cli-anything-universal-image-converter

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/universal_image_converter/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-universal-image-converter",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Universal Image Converter — batch image format conversion via Pillow",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "Pillow>=10.0.0",
    ],
    extras_require={
        "repl": [
            "prompt-toolkit>=3.0.0",
        ],
        "heic": [
            "pillow-heif>=0.13.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "numpy>=1.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-universal-image-converter=cli_anything.universal_image_converter.uic_cli:main",
        ],
    },
    package_data={
        "cli_anything.universal_image_converter": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
