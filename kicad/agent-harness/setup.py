from pathlib import Path

from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-kicad",
    version="1.0.0",
    description="Run KiCad electrical checks and export fabrication files",
    long_description=Path("cli_anything/kicad/README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    packages=find_namespace_packages(include=["cli_anything.kicad", "cli_anything.kicad.*"]),
    package_data={"cli_anything.kicad": ["README.md", "skills/*.md", "tests/fixtures/*.kicad_*"]},
    python_requires=">=3.10",
    install_requires=["click>=8", "prompt-toolkit>=3"],
    extras_require={"dev": ["pytest>=7"]},
    entry_points={"console_scripts": ["cli-anything-kicad=cli_anything.kicad.kicad_cli:main"]},
)
