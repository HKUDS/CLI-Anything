"""Setup script for CC Switch CLI harness."""
from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-ccswitch",
    version="1.0.0",
    description="CLI interface for CC Switch — manage AI coding tool configurations",
    author="cli-anything contributors",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.ccswitch": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0",
        "prompt_toolkit>=3.0",
        "tomlkit>=0.12",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-ccswitch=cli_anything.ccswitch.ccswitch_cli:main",
        ],
    },
)
