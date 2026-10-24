#!/usr/bin/env python3
"""Setup for cli-anything-vlc agent harness.

PEP 420 namespace package: the top-level ``cli_anything`` directory intentionally has
NO ``__init__.py``; only sub-packages (``cli_anything.vlc``) do.
"""

from setuptools import setup, find_namespace_packages
from pathlib import Path

readme = Path(__file__).parent / "cli_anything" / "vlc" / "README.md"
long_description = readme.read_text(encoding="utf-8") if readme.exists() else ""

setup(
    name="cli-anything-vlc",
    version="1.0.0",
    author="cli-anything-vlc contributors",
    description=(
        "Agent-native CLI harness for VLC — define media jobs (transcode, stream, "
        "snapshot) as structured JSON, run them through the real VLC engine. JSON "
        "output, stateful REPL, undo/redo."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.videolan.org/vlc/",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Sound/Audio",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-vlc=cli_anything.vlc.vlc_cli:cli",
        ],
    },
    package_data={
        "cli_anything.vlc": ["skills/*.md"],
    },
    exclude_package_data={
        "cli_anything.vlc": ["tests/*"],
    },
    include_package_data=True,
    zip_safe=False,
)
