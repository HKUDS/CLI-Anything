#!/usr/bin/env python3
"""
setup.py for cli-anything-voxtype

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/voxtype/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-voxtype",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Voxtype - push-to-talk voice-to-text for Linux: config with undo, "
                "file transcription, meetings and daemon control. Requires: voxtype, ffmpeg",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
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
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-voxtype=cli_anything.voxtype.voxtype_cli:main",
        ],
    },
    package_data={
        "cli_anything.voxtype": ["skills/*.md", "tests/fixtures/*.wav", "tests/fixtures/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
