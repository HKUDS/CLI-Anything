from pathlib import Path

from setuptools import setup, find_namespace_packages

BASE_DIR = Path(__file__).parent
long_description = (BASE_DIR / "cli_anything" / "calibre" / "README.md").read_text(
    encoding="utf-8"
)

setup(
    name="cli-anything-calibre",
    version="1.0.0",
    description="CLI harness for Calibre e-book manager — part of the cli-anything toolkit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    package_data={"cli_anything.calibre": ["skills/*.md", "README.md"]},
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-calibre=cli_anything.calibre.calibre_cli:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Utilities",
    ],
)
