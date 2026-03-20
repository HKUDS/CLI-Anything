"""Setup for cli-anything-renderdoc package."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-renderdoc",
    version="0.1.0",
    description="CLI harness for RenderDoc graphics debugger",
    long_description=open("cli_anything/renderdoc/README.md").read(),
    long_description_content_type="text/markdown",
    author="cli-anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
    ],
    extras_require={
        "test": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-renderdoc=cli_anything.renderdoc.renderdoc_cli:main",
        ],
    },
    package_data={
        "cli_anything.renderdoc": ["skills/*.md", "README.md", "native/*.pyd", "native/*.dll"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Debuggers",
    ],
)
