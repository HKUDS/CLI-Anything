#!/usr/bin/env python3
from setuptools import setup, find_namespace_packages

with open("cli_anything/scribus/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
setup(
    name="cli-anything-scribus",
    version="1.0.0",
    author="cli-anything contributors",
    description="CLI harness for Scribus — Desktop publishing via scribus --python-script. Requires: scribus (apt install scribus)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=["click>=8.0.0", "prompt-toolkit>=3.0.0"],
    entry_points={
        "console_scripts": [
            "cli-anything-scribus=cli_anything.scribus.scribus_cli:main"
        ]
    },
    package_data={"cli_anything.scribus": ["skills/*.md"]},
    include_package_data=True,
    zip_safe=False,
)
