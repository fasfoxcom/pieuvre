import pathlib
from setuptools import setup, find_packages


HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()
VERSION = (HERE / "VERSION").read_text()


extras_require = {
    "doc": [
        "pycodestyle",
        "sphinx",
        "sphinx-rtd-theme",
        "sphinxcontrib-websupport",
    ],
    "test": ["pycodestyle", "pytest==5.3.5", "pytest-cov"],
}


setup(
    name="pieuvre",
    version=VERSION,
    description="Simple Workflow Engine Library",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Kosc Telecom",
    author_email="si@kosc-telecom.fr",
    url="http://github.com/kosctelecom/pieuvre.git",
    license="Apache",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    packages=find_packages(exclude=("tests", "docs")),
    install_requires=[],
    setup_requires=["wheel"],
    test_suite="tests",
    tests_require=extras_require["test"],
    extras_require=extras_require,
    python_requires=">=3.5",
)
