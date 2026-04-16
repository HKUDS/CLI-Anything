"""Setup for cli-anything-renderdoc package."""

from pathlib import Path

from setuptools import setup, find_namespace_packages

_README = Path(__file__).parent / "cli_anything" / "renderdoc" / "README.md"
_long_desc = _README.read_text(encoding="utf-8") if _README.is_file() else ""

setup(
    name="cli-anything-renderdoc",
    version="0.1.0",
    description="CLI harness for RenderDoc graphics debugger",
    long_description=_long_desc,
    long_description_content_type="text/markdown",
    author="cli-anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "prompt-toolkit>=3.0",
    ],
    extras_require={
        "test": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-renderdoc=cli_anything.renderdoc.renderdoc_cli:main",
        ],
    },
    package_data={
        "cli_anything.renderdoc": ["skills/*.md", "README.md"],
    },
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Debuggers",
    ],
)
