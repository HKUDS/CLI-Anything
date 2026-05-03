"""Setup for cli-anything-lldb package."""

from pathlib import Path

from setuptools import find_namespace_packages, setup

_README = Path(__file__).parent / "cli_anything" / "lldb" / "README.md"
_long_desc = _README.read_text(encoding="utf-8") if _README.is_file() else ""

setup(
    name="cli-anything-lldb",
    version="1.0.0",
    description="CLI harness for LLDB debugger via Python API",
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
            "cli-anything-lldb=cli_anything.lldb.lldb_cli:main",
            "cli-anything-lldb-dap=cli_anything.lldb.dap:main",
        ],
    },
    package_data={
        "cli_anything.lldb": ["skills/*.md", "README.md"],
    },
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Debuggers",
    ],
)
