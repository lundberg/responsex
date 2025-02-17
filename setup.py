#!/usr/bin/env python
from pathlib import Path

from setuptools import setup

exec(Path("respx", "__version__.py").read_text())  # Load __version__ into locals

setup(
    name="respx",
    version=locals()["__version__"],
    license="BSD-3-Clause",
    author="Jonas Lundberg",
    author_email="jonas@5monkeys.se",
    url="https://lundberg.github.io/respx/",
    keywords=["httpx", "httpcore", "mock", "responses", "requests", "async", "http"],
    description="A utility for mocking out the Python HTTPX and HTTP Core libraries.",
    long_description=Path("README.md").read_text("utf-8"),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    project_urls={
        "GitHub": "https://github.com/lundberg/respx",
        "Changelog": "https://github.com/lundberg/respx/blob/master/CHANGELOG.md",
        "Issues": "https://github.com/lundberg/respx/issues",
    },
    packages=["respx"],
    package_data={"respx": ["py.typed"]},
    entry_points={"pytest11": ["respx = respx.plugin"]},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.8",
    install_requires=["httpx>=0.25.0"],
)
