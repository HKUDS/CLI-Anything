from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-adguardhome",
    version="1.0.0",
    description="CLI harness for AdGuardHome - control your ad blocker from the command line",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-adguardhome=cli_anything.adguardhome.adguardhome_cli:main",
        ],
    },
    python_requires=">=3.10",
)
