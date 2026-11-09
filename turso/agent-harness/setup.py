from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-turso",
    version="0.1.0",
    description="CLI-Anything harness for the local native Turso database engine",
    author="CLI-Anything contributors",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    python_requires=">=3.10",
    install_requires=["click>=8.0", "prompt-toolkit>=3.0", "pyturso==0.8.3"],
    extras_require={"dev": ["pytest>=7.0"]},
    package_data={"cli_anything.turso": ["skills/*.md", "README.md"]},
    entry_points={"console_scripts": [
        "cli-anything-turso=cli_anything.turso.turso_cli:main",
    ]},
)
