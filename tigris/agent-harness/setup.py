"""Setup for cli-anything-tigris — CLI harness for the Tigris object storage CLI.

This harness shells out to the official `tigris` CLI rather than reimplementing
the S3 protocol, so it surfaces every Tigris primitive (snapshots, IAM,
scoped access keys, OAuth login) — not just generic S3 ops.

Install the underlying CLI first with one of:

    npm install -g @tigrisdata/cli
    brew install tigrisdata/tap/tigris
"""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-tigris",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI-Anything harness wrapping the official Tigris CLI (object storage, snapshots, IAM, presign)",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        # NB: no boto3. This harness shells out to the `tigris` CLI, which is
        # an external runtime dependency installed via npm or brew.
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-tigris=cli_anything.tigris.tigris_cli:main",
        ],
    },
    package_data={
        "cli_anything.tigris": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
