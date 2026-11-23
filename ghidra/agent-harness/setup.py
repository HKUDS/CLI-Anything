from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-ghidra",
    version="1.0.0",
    description="CLI harness for Ghidra - analyze, list, decompile and cross-reference binaries headlessly",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-ghidra=cli_anything.ghidra.ghidra_cli:main",
        ],
    },
    package_data={
        "cli_anything.ghidra": ["skills/*.md", "scripts/*.java"],
    },
    include_package_data=True,
    python_requires=">=3.10",
)
