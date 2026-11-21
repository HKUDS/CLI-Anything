"""Package configuration for cli-anything-fzf."""

from pathlib import Path

from setuptools import find_namespace_packages, setup


PACKAGE_ROOT = Path(__file__).parent
README = PACKAGE_ROOT / "cli_anything" / "fzf" / "README.md"


setup(
    name="cli-anything-fzf",
    version="1.0.0",
    description="Structured, policy-aware CLI-Anything harness for fzf 0.74.5",
    long_description=README.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="CLI-Anything Team",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=["click>=8.0", "prompt-toolkit>=3.0"],
    extras_require={"test": ["pytest>=7.0", "jsonschema>=4.0"]},
    entry_points={
        "console_scripts": [
            "cli-anything-fzf=cli_anything.fzf.fzf_cli:main",
        ]
    },
    package_data={
        "cli_anything.fzf": ["*.json", "README.md", "skills/*.md", "tests/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Environment :: Console",
        "Topic :: Utilities",
    ],
)
