from setuptools import find_namespace_packages, setup

setup(
    name="unity-legacy-cli",
    version="0.3.1",
    description="Unity Legacy CLI: local command-line control of the Unity Editor",
    license="Apache-2.0",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["*.tests", "*.bridge", "*.bridge.*", "*.skills"]),
    package_data={"cli_anything.unity2020": [
        "README.md", "skills/*.md", "bridge/*.json", "bridge/*.meta",
        "bridge/Editor/*.cs", "bridge/Editor/*.asmdef", "bridge/Editor/*.meta",
    ]},
    python_requires=">=3.10",
    install_requires=["click>=8", "prompt-toolkit>=3,<4"],
    entry_points={"console_scripts": ["unity-legacy-cli=cli_anything.unity2020.unity2020_cli:cli"]},
)
