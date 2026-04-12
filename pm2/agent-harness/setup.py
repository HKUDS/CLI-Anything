"""Setup for cli-anything-pm2 — CLI harness for PM2 process management."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-pm2",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI-Anything harness for PM2 process management",
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
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-pm2=cli_anything.pm2.pm2_cli:main",
        ],
    },
    package_data={
        "cli_anything.pm2": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
