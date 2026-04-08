from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-intelwatch",
    version="1.0.0",
    description="CLI harness for Intelwatch - Competitive intelligence and OSINT directly from your terminal",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-intelwatch=cli_anything.intelwatch.intelwatch_cli:main",
        ],
    },
    package_data={
        "cli_anything.intelwatch": ["skills/*.md"],
    },
    include_package_data=True,
    python_requires=">=3.8",
)
