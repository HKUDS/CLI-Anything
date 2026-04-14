"""Setup configuration for cli-anything-unimol-tools"""
from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-unimol-tools",
    version="1.0.0",
    author="CLI-Anything Contributors",
    description="Molecular property prediction CLI for AI agents",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    extras_require={
        "backend": [
            "unimol_tools>=1.0.0",
            "huggingface_hub",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-unimol-tools=cli_anything.unimol_tools.unimol_tools_cli:main",
        ],
    },
    package_data={
        "cli_anything.unimol_tools": ["skills/*.md"],
    },
    python_requires=">=3.9",
)
