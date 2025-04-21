from setuptools import setup, find_packages

setup(
    name="workflow-graph",
    version="0.3.0",
    description="A lightweight package for managing workflow graphs",
    author="Dexter Awoyemi",
    author_email="dexter@dextersjab.xyz",
    url="https://github.com/dextersjab/workflow-graph",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
    license="MIT",
)
