#!/usr/bin/env python3
"""setup.py for cli-anything-videocaptioner"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/videocaptioner/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-videocaptioner",
    version="1.0.0",
    author="Weifeng",
    author_email="",
    description="CLI harness for VideoCaptioner — AI-powered video captioning with beautiful subtitle styles. Requires: videocaptioner (pip install videocaptioner), ffmpeg",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/WEIFENG2333/VideoCaptioner",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10,<3.13",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "videocaptioner",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-videocaptioner=cli_anything.videocaptioner.videocaptioner_cli:main",
        ],
    },
    package_data={
        "cli_anything.videocaptioner": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
