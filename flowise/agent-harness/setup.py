from pathlib import Path

from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-flowise",
    version="1.0.0",
    description="Manage and run Flowise workflows from the command line",
    long_description=Path("cli_anything/flowise/README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    packages=find_namespace_packages(include=["cli_anything.flowise", "cli_anything.flowise.*"]),
    package_data={"cli_anything.flowise": ["README.md", "skills/*.md", "tests/fixtures/*.json"]},
    python_requires=">=3.10",
    install_requires=["click>=8", "prompt-toolkit>=3", "requests>=2.32"],
    extras_require={"dev": ["pytest>=7"]},
    entry_points={"console_scripts": ["cli-anything-flowise=cli_anything.flowise.flowise_cli:main"]},
)
