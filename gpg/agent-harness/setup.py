"""Setup for cli-anything gpg harness."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-gpg",
    version="1.0.0",
    description="GnuPG encryption, signing, and key management — CLI-Anything harness",
    author="CLI-Anything",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "gpg-cli=cli_anything.gpg.gpg_cli:main",
        ],
    },
)
