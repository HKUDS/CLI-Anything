"""Setup for cli-anything-pdmaner — CLI harness for PDManer database modeling."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-pdmaner",
    version="0.1.0",
    description="CLI harness for PDManer database modeling tool (元数建模)",
    author="cli-anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0",
    ],
    extras_require={
        "repl": ["prompt_toolkit>=3.0"],
        "dev": ["pytest>=7.0", "prompt_toolkit>=3.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-pdmaner=cli_anything.pdmaner.pdmaner_cli:main",
        ],
    },
    package_data={
        "cli_anything.pdmaner": ["skills/*.md"],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
)
