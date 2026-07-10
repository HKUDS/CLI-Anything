from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-firefly-iii",
    version="1.0.0",
    description="Firefly III CLI - Personal finance management via CLI-Anything",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="CLI-Anything Community",
    author_email="community@cli-anything.cc",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    entry_points={
        "console_scripts": [
            "cli-anything-firefly-iii=cli_anything.firefly_iii.firefly_iii_cli:main",
        ],
    },
    package_data={
        "cli_anything.firefly_iii": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0",
        "prompt_toolkit>=3.0",
        "requests>=2.25",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=22.0",
            "flake8>=5.0",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial",
    ],
    keywords="firefly-iii cli finance personal-finance cli-anything",
    license="MIT",
)
