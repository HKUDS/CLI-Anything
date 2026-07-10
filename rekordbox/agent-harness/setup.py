#!/usr/bin/env python3
"""
setup.py for cli-anything-rekordbox

Install: pip install -e .
Publish: python -m build && twine upload dist/*
"""
from setuptools import setup, find_namespace_packages

with open("cli_anything/rekordbox/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-rekordbox",
    version="0.1.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for Pioneer Rekordbox - DJ library + live-deck control via SQLCipher direct DB access and virtual MIDI. Requires: rekordbox 6/7, optional virtual MIDI driver (loopMIDI / LoopBe / teVirtualMIDI on Windows).",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: MIDI",
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
        "mido>=1.3.0",
        "python-rtmidi>=1.5.0",
        "pyrekordbox>=0.4.0",
    ],
    extras_require={
        "windows": ["pyautogui>=0.9.54", "pygetwindow>=0.0.9", "pywin32>=306"],
        "dev": ["pytest>=7.0.0", "pytest-cov>=4.0.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-rekordbox=cli_anything.rekordbox.rekordbox_cli:main",
        ],
    },
    package_data={
        "cli_anything.rekordbox": ["skills/*.md", "data/*.csv"],
    },
    include_package_data=True,
    zip_safe=False,
)
