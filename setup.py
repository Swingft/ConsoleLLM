#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="console-llm",
    version="1.0.0",
    description="Swift Code Analysis System with LLM",
    author="inl3lack",
    author_email="ark182818@gmail.com",
    packages=find_packages(),
    install_requires=[
        "llama-cpp-python>=0.2.20",
    ],
    extras_require={
        "cuda": ["llama-cpp-python[cuda]>=0.2.20"],
        "metal": ["llama-cpp-python[metal]>=0.2.20"],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "console-llm=console_llm.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "console_llm": ["ast_analyzers/**/*"],
    },
)