"""Setup configuration for ngen-j package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""


setup(
    packages=["ngen_japi"],
    package_dir={"ngen_japi": "ngen_japi"},
)

