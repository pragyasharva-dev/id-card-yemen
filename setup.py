from setuptools import setup, find_packages

setup(
    name="id-card-yemen",
    version="0.1.0",
    packages=["api", "services", "utils", "models", "middleware"],
    # Dependencies are handled by pyproject.toml / pip
)
