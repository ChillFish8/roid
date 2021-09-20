import re
from setuptools import setup

requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

with open("roid/__version__.py") as f:
    version = re.search(
        r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE
    ).group(1)

if not version:
    raise RuntimeError("version is not set")

with open("README.md") as f:
    readme = f.read()

extras_require = {
    "speedups": [
        "orjson>=3.5.4",
    ]
}

packages = ["roid", "roid.state"]

# This call to setup() does all the work
setup(
    name="roid",
    version=version,
    description="A fast, stateless http slash commands framework for scale. Built by the Crunchy bot team.",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/ChillFish8/roid",
    author="ChillFish8",
    packages=packages,
    install_requires=requirements,
    extras_require=extras_require,
    include_package_data=True,
    python_requires=">=3.8.0",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
