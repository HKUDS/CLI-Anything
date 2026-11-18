from setuptools import setup, find_namespace_packages

with open("cli_anything/controlplane/README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cli-anything-controlplane",
    version="1.0.0",
    description="Compose-based infrastructure repo CLI - stacks, services, Caddy routing, preflight",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="cli-anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.controlplane": ["skills/*.md"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "PyYAML>=6.0",
    ],
    extras_require={
        "test": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-controlplane=cli_anything.controlplane.cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
