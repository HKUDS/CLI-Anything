"""PyPI setup for cli-anything-nslogger."""
from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-nslogger",
    version="0.1.0",
    description="CLI harness for NSLogger — read, filter, export, and monitor NSLogger log files",
    long_description=open("cli_anything/nslogger/README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="cli-anything",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.nslogger": ["helpers/*.swift"],
    },
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "zeroconf>=0.38.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-nslogger=cli_anything.nslogger.nslogger_cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
    ],
)
