from setuptools import find_namespace_packages, setup


setup(
    name="cli-anything-openrefine",
    version="1.0.0",
    description="CLI-Anything harness for OpenRefine data wrangling workflows",
    long_description="Agent-native Click CLI for OpenRefine's local HTTP API, operation histories, exports, and sessions.",
    author="CLI-Anything-Team",
    author_email="",
    maintainer="CLI-Anything-Team",
    url="https://github.com/HKUDS/CLI-Anything",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "prompt-toolkit>=3.0",
    ],
    extras_require={"dev": ["pytest>=7.0"]},
    package_data={
        "cli_anything.openrefine": ["skills/*.md"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-openrefine=cli_anything.openrefine.openrefine_cli:main",
        ],
    },
)
