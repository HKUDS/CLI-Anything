"""Setup for cli-anything ffprobe harness."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-ffprobe",
    version="1.0.0",
    description="Structured media file analysis via ffprobe — CLI-Anything harness",
    author="CLI-Anything",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ffprobe-cli=cli_anything.ffprobe.ffprobe_cli:main",
        ],
    },
)
