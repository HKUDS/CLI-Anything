from setuptools import setup, find_namespace_packages

with open("cli_anything/jumpserver/README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-jumpserver",
    version="0.1.0",
    description="Stateful CLI harness for JumpServer bastion host management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="cli-anything",
    url="https://github.com/cli-anything/cli-anything-jumpserver",
    project_urls={
        "Source": "https://github.com/cli-anything/cli-anything-jumpserver",
        "Tracker": "https://github.com/cli-anything/cli-anything-jumpserver/issues",
    },
    python_requires=">=3.11",
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-mock>=3.10",
        ],
    },
    packages=find_namespace_packages(include=["cli_anything.*"]),
    entry_points={
        "console_scripts": [
            "cli-anything-jumpserver=cli_anything.jumpserver.jumpserver_cli:cli_main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Systems Administration",
        "Topic :: Security",
    ],
    keywords="jumpserver bastion pam cli security ssh",
)
