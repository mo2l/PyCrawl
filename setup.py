from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()
    # Filter out comments and empty lines
    requirements = [r for r in requirements if r and not r.startswith("#")]

setup(
    name="pycrawl",
    version="0.1.0",
    description="A web crawler for detecting broken links and resources",
    author="PyCrawl Team",
    author_email="info@pycrawl.example.com",
    packages=find_packages(),
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.8",
)