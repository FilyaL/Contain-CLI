from setuptools import setup, find_packages

setup(
    name="contain-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "docker>=6.1.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
        "psutil>=5.9.0",
        "prometheus-client>=0.17.0",
    ],
    entry_points={
        "console_scripts": [
            "contain=contain.cli:cli",
        ],
    },
)
