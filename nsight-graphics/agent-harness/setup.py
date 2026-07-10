"""Setup for cli-anything-nsight-graphics package."""

from pathlib import Path

from setuptools import find_namespace_packages, setup

_README = Path(__file__).parent / "cli_anything" / "nsight_graphics" / "README.md"
_LONG_DESC = _README.read_text(encoding="utf-8") if _README.is_file() else ""

setup(
    name="cli-anything-nsight-graphics",
    version="0.2.0",
    description="CLI harness for NVIDIA Nsight Graphics orchestration",
    long_description=_LONG_DESC,
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
            "cli-anything-nsight-graphics=cli_anything.nsight_graphics.nsight_graphics_cli:main",
        ],
    },
    package_data={
        "cli_anything.nsight_graphics": ["skills/*.md", "README.md"],
    },
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Debuggers",
    ],
)
