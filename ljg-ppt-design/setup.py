"""setup.py for ljg-ppt-design (HKUDS fork self-contained).

Install:
  pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=ljg-ppt-design

Provides:
  - ljg_ppt_design: 设计系统 (4 preset / 12 layout / 4 talk type / 5 维审查)
  - cli-anything-ljg-ppt-design: CLI 命令 (HKUDS hub style)
  - cli_anything_ljg_ppt_design: 桥接包 (重导出)
"""

from setuptools import setup, find_packages

with open("SKILL.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ljg-ppt-design",
    version="0.1.0",
    description="PPT design system — 4 presets × 12 layouts × 4 talk types × 5-dim quality review. Lighter alternative to cli-anything-libreoffice with built-in design system. Self-contained, Python-pptx default, LibreOffice optional.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ljg-ppt-design contributors",
    url="https://github.com/HKUDS/CLI-Anything",
    project_urls={
        "Upstream": "https://github.com/HKUDS/CLI-Anything",
    },
    python_requires=">=3.9",
    install_requires=[
        "click>=8.0",
    ],
    extras_require={
        "pptx": ["python-pptx>=1.0.0"],
        # libreoffice 后端:需要 HKUDS 原版 cli-anything-libreoffice + 系统装 LO
        # pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=libreoffice/agent-harness
        # brew install --cask libreoffice
        "dev": ["pytest>=7.0"],
    },
    packages=find_packages(include=["ljg_ppt_design", "ljg_ppt_design.*", "cli_anything_ljg_ppt_design", "cli_anything_ljg_ppt_design.*"]),
    package_data={
        "ljg_ppt_design": ["SKILL.md", "references/*.md"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-ljg-ppt-design=cli_anything_ljg_ppt_design.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Office Suites",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
