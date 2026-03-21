from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-krita",
    version="1.0.0",
    description="CLI harness for Krita digital painting application",
    long_description=open("cli_anything/krita/README.md").read(),
    long_description_content_type="text/markdown",
    author="cli-anything contributors",
    license="MIT",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.krita": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-krita=cli_anything.krita.krita_cli:main",
        ],
    },
    python_requires=">=3.10",
)
