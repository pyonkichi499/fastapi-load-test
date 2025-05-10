from setuptools import setup, find_packages

setup(
    name="openapi_server",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pytz>=2023.3",
    ],
    python_requires=">=3.11",
)
