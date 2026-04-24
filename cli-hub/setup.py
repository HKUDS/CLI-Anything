"""cli-hub — package manager for CLI-Anything harnesses."""

from setuptools import setup, find_packages

setup(
    name="cli-anything-hub",
    version="0.3.0",
    description="Package manager for CLI-Anything — browse, install, and manage 40+ agent-native CLI interfaces for GUI applications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="HKUDS",
    author_email="hkuds@connect.hku.hk",
    url="https://github.com/HKUDS/CLI-Anything",
    project_urls={
        "Homepage": "https://clianything.cc",
        "Repository": "https://github.com/HKUDS/CLI-Anything",
        "Bug Tracker": "https://github.com/HKUDS/CLI-Anything/issues",
        "Catalog": "https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md",
    },
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
    ],
    entry_points={
        "console_scripts": [
            "cli-hub=cli_hub.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: System :: Installation/Setup",
        "Topic :: Utilities",
    ],
    keywords="cli, agent, gui, automation, package-manager, cli-anything",
)
