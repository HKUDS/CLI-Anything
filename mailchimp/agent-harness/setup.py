import os
from setuptools import setup, find_namespace_packages

_here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(_here, "cli_anything/mailchimp/README.md"), encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-mailchimp",
    version="0.1.0",
    description="cli-anything harness for the Mailchimp Marketing API v3.0",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="cli-anything contributors",
    license="Apache-2.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.mailchimp": ["skills/SKILL.md", "README.md"]},
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "prompt-toolkit>=3.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0", "pytest-cov", "responses>=0.23"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-mailchimp=cli_anything.mailchimp.mailchimp_cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
