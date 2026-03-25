from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-iterm2",
    version="1.0.0",
    description="A stateful CLI harness for iTerm2 — control a running iTerm2 instance programmatically.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="voidfreud",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.iterm2_ctl": ["skills/*.md", "skills/references/*.md"],
    },
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "iterm2>=2.7",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-iterm2=cli_anything.iterm2_ctl.iterm2_ctl_cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: MacOS",
        "Topic :: Terminals :: Terminal Emulators/X Terminals",
        "Intended Audience :: Developers",
    ],
    # NOTE: iTerm2.app itself is a hard dependency that cannot be expressed here.
    # Install it from https://iterm2.com/ and enable the Python API:
    # iTerm2 → Preferences → General → Magic → Enable Python API
)
