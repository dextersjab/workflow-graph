"""Setup script for the WorkflowGraph package."""

import tomli
from setuptools import find_packages, setup

with open("pyproject.toml", "rb") as f:
    pyproject = tomli.load(f)
    version = pyproject["project"]["version"]

setup(
    name="workflow-graph",
    version=version,
    description="A lightweight package for managing workflow graphs",
    author="Dexter Awoyemi",
    author_email="dexter@dextersjab.xyz",
    url="https://github.com/dextersjab/workflow-graph",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
    license="MIT",
)
