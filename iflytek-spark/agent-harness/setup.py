#!/usr/bin/env python3
"""
setup.py for cli-anything-iflytek-spark

Install with: pip install -e .
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/iflytek_spark/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-iflytek-spark",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description=(
        "CLI harness for iFlytek Spark-X2.5 - chat through SGLang, vLLM, Ollama, "
        "llama.cpp or iFlytek Astron MaaS. Requires: a running Spark-X2.5 server"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HKUDS/CLI-Anything",
    license="Apache-2.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
        "prompt-toolkit>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-iflytek-spark=cli_anything.iflytek_spark.spark_cli:main",
        ],
    },
    package_data={
        "cli_anything.iflytek_spark": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
