#!/usr/bin/env python3
from pathlib import Path
from setuptools import setup, find_namespace_packages

ROOT = Path(__file__).parent
README = ROOT / "cli_anything/blender/README.md"

def read_readme():
    try:
        return README.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

setup(
    name="cli-anything-blender",
    version="1.0.0",
    description="CLI harness for Blender (automation for 3D modeling, animation, rendering)",
    long_description=read_readme(),
    long_description_content_type="text/markdown",

    author="CLI Anything Contributors",
    url="https://github.com/HKUDS/CLI-Anything",

    project_urls={
        "Homepage": "https://github.com/HKUDS/CLI-Anything",
        "Issues": "https://github.com/HKUDS/CLI-Anything/issues",
    },

    license="MIT",

    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",

    install_requires=[
        "click>=8.1,<9.0",
        "prompt-toolkit>=3.0,<4.0",
    ],

    extras_require={
        "dev": [
            "pytest>=7",
            "pytest-cov>=4",
            "build",
            "twine",
        ],
    },

    entry_points={
        "console_scripts": [
            "cli-anything-blender=cli_anything.blender.blender_cli:main",
        ],
    },

    include_package_data=True,
    zip_safe=False,

    keywords="cli blender 3d rendering automation",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Graphics :: 3D Modeling",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",

        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
