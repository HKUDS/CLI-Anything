from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-wiremock",
    version="0.1.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=["click>=8.0", "requests>=2.28", "rich>=13.0"],
    entry_points={
        "console_scripts": [
            "cli-anything-wiremock=cli_anything.wiremock.wiremock_cli:cli"
        ]
    },
    python_requires=">=3.9",
)
