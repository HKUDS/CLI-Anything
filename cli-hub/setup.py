"""cli-hub — package manager for CLI-Anything harnesses."""

import shutil
from pathlib import Path

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.sdist import sdist as _sdist

HERE = Path(__file__).resolve().parent

# Matrix skill content lives at the repo root (outside this package dir).
# It is vendored into cli_hub/_matrix_data/ at build time so wheels and
# sdists ship real matrix content for users without a repo checkout.
# Editable installs (`pip install -e`) do not need the vendored copy: the
# runtime lookup chain in cli_hub/matrix_skill.py finds the checkout first.
MATRIX_CONTENT_SOURCE = HERE.parent / "cli-hub-matrix"
MATRIX_DATA_DIR = HERE / "cli_hub" / "_matrix_data"


def _sync_matrix_data():
    """Vendor cli-hub-matrix/ into cli_hub/_matrix_data/ (build artifact).

    No-op when building from an sdist (the data is already vendored) or when
    the repo content is unavailable (runtime falls back to the published URL
    or a stub).
    """
    if not MATRIX_CONTENT_SOURCE.is_dir():
        return
    if MATRIX_DATA_DIR.exists():
        shutil.rmtree(MATRIX_DATA_DIR)
    shutil.copytree(
        MATRIX_CONTENT_SOURCE,
        MATRIX_DATA_DIR,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


class build_py(_build_py):
    def run(self):
        _sync_matrix_data()
        super().run()


class sdist(_sdist):
    def run(self):
        _sync_matrix_data()
        super().run()


setup(
    name="cli-anything-hub",
    version="0.4.0",
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
    cmdclass={"build_py": build_py, "sdist": sdist},
    include_package_data=True,
    package_data={
        "cli_hub": [
            "_matrix_data/*/SKILL.md",
            "_matrix_data/*/references/*",
            "_matrix_data/*/scripts/*",
        ],
    },
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
