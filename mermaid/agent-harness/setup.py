from setuptools import find_namespace_packages, setup

with open("cli_anything/mermaid/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-mermaid",
    version="1.0.0",
    description="CLI harness for Mermaid Live Editor state files and renderer URLs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=9.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "cli-anything-mermaid=cli_anything.mermaid.mermaid_cli:main",
        ]
    },
    python_requires=">=3.10",
)
