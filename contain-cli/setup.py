from setuptools import setup, find_packages

setup(
    name="contain-cli",
    version="1.0.0",
    description="CLI-оркестратор контейнеров на Python с health checks, auto-restart и Prometheus метриками",
    long_description=open("README.md").read() if open("README.md") else "",
    long_description_content_type="text/markdown",
    author="FilyaL",
    url="https://github.com/FilyaL/contain-cli-project",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.1.0",
        "docker>=6.1.0",
        "pyyaml>=6.0",
        "flask>=2.0",
        "prometheus-client>=0.17.0",
        "requests>=2.28.0",
        "psutil>=5.9.0",
    ],
    entry_points={
        "console_scripts": [
            "contain=contain.cli:cli",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
    ],
)
