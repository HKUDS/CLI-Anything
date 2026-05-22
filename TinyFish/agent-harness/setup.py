from setuptools import setup, find_packages

setup(
    name="cli-anything-tinyfish",
    version="1.0.0",
    description="CLI harness for TinyFish web automation - search, fetch, browser control",
    author="Marius MC12",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "click>=8.1.0"
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-tinyfish=cli_anything.tinyfish.__main__:cli"
        ]
    }
)
