"""Setup for cli-anything-freecad — CLI harness for FreeCAD."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-freecad",
    version="1.0.0",
    description="CLI harness for FreeCAD parametric 3D CAD modeler",
    long_description=open("cli_anything/freecad/README.md").read(),
    long_description_content_type="text/markdown",
    author="CLI-Anything Contributors",
    license="Apache-2.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-freecad=cli_anything.freecad.freecad_cli:main",
        ],
    },
    package_data={
        "cli_anything.freecad": ["skills/*.md"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
)
