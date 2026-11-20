from pathlib import Path
from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-parallel",
    version="1.0.0",
    description="Web search and page extraction through Parallel's free Search MCP",
    long_description=Path(__file__).with_name("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["*.tests"]),
    python_requires=">=3.11",
    install_requires=[
        "click>=8",
        "mcp>=1.26,<2",
        "httpx>=0.27,<1",
        "prompt-toolkit>=3",
    ],
    extras_require={"dev": ["pytest>=7"]},
    entry_points={
        "console_scripts": [
            "cli-anything-parallel=cli_anything.parallel.parallel_cli:main"
        ]
    },
    package_data={"cli_anything.parallel": ["skills/*.md"]},
)
