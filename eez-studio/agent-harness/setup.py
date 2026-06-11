from pathlib import Path

from setuptools import find_namespace_packages, setup


README = Path("cli_anything/eez_studio/README.md")


setup(
    name="cli-anything-eez-studio",
    version="0.1.0",
    description="Agent-friendly CLI harness for EEZ Studio project, LVGL, and SCPI workflows",
    long_description=README.read_text(encoding="utf-8") if README.exists() else "",
    long_description_content_type="text/markdown",
    author="cli-anything contributors",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.eez_studio": ["skills/*.md"],
    },
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-eez-studio=cli_anything.eez_studio.eez_studio_cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Embedded Systems",
    ],
)
