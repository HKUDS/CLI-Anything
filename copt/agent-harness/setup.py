from pathlib import Path

from setuptools import find_namespace_packages, setup


setup(
    name="cli-anything-copt",
    version="1.0.0",
    description="Structured command line harness for the Cardinal Optimizer COPT solver",
    long_description=Path(__file__).with_name("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.copt": ["README.md", "skills/*.md", "tests/TEST.md", "tests/data/*.lp"]},
    install_requires=["click>=8.0", "prompt-toolkit>=3.0"],
    entry_points={"console_scripts": ["cli-anything-copt=cli_anything.copt.copt_cli:main"]},
    python_requires=">=3.10",
)
