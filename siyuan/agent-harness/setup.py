from setuptools import setup, find_namespace_packages

with open("cli_anything/siyuan/README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cli-anything-siyuan",
    version="1.0.0",
    description="SiYuan (思源笔记) CLI — manage notebooks, documents, blocks from the terminal",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="cli-anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.siyuan": ["skills/*.md"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
    ],
    extras_require={
        "repl": ["prompt_toolkit>=3.0"],
        "test": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-siyuan=cli_anything.siyuan.siyuan_cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
