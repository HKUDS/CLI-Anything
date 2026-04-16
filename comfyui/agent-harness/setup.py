#!/usr/bin/env python3
"""
setup.py for cli-anything-comfyui

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-comfyui",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI harness for ComfyUI - AI image generation workflow management via ComfyUI REST API. Requires: ComfyUI running at http://localhost:8188",
    long_description=open("cli_anything/comfyui/README.md", "r", encoding="utf-8").read()
    if __import__("os").path.exists("cli_anything/comfyui/README.md")
    else "CLI harness for ComfyUI AI image generation.",
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Graphics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-comfyui=cli_anything.comfyui.comfyui_cli:main",
        ],
    },
    package_data={
        "cli_anything.comfyui": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
