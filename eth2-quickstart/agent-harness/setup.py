from setuptools import find_namespace_packages, setup

with open("cli_anything/eth2_quickstart/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-eth2-quickstart",
    version="1.0.0",
    description="CLI harness for eth2-quickstart - hardened Ethereum node deployment and operations",
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
            "pytest>=7.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "cli-anything-eth2-quickstart=cli_anything.eth2_quickstart.eth2_quickstart_cli:main",
        ]
    },
    package_data={
        "cli_anything.eth2_quickstart": ["skills/*.md"],
    },
    include_package_data=True,
    python_requires=">=3.10",
)

