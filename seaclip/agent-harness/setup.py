"""Setup for cli-anything-seaclip — CLI harness for SeaClip-Lite."""

from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-seaclip",
    version="1.0.0",
    author="cli-anything contributors",
    author_email="",
    description="CLI-Anything harness for SeaClip-Lite project management",
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
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-seaclip=cli_anything.seaclip.seaclip_cli:main",
        ],
    },
    package_data={
        "cli_anything.seaclip": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
