#!/usr/bin/env python3
"""Setup for cli-anything-wavetone."""

from pathlib import Path

from setuptools import find_namespace_packages, setup


readme = Path(__file__).parent / "cli_anything" / "wavetone" / "README.md"

setup(
    name="cli-anything-wavetone",
    version="1.0.0",
    author="cli-anything contributors",
    description=(
        "Agent-native CLI harness for WaveTone 2.61. Creates structured audio "
        "analysis manifests and launches the real WaveTone Windows executable."
    ),
    long_description=readme.read_text(encoding="utf-8") if readme.exists() else "",
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(
        include=["cli_anything.*"],
        exclude=["cli_anything.*.tests", "cli_anything.*.tests.*"],
    ),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
        "Topic :: Multimedia :: Sound/Audio :: Editors",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires=">=3.10",
    install_requires=["click>=8.0.0", "prompt-toolkit>=3.0.0"],
    extras_require={"dev": ["pytest>=7.0.0"]},
    entry_points={
        "console_scripts": [
            "cli-anything-wavetone=cli_anything.wavetone.wavetone_cli:main",
        ],
    },
    package_data={"cli_anything.wavetone": ["README.md", "skills/SKILL.md", "skills/*.md"]},
    include_package_data=True,
    zip_safe=False,
)
