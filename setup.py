from setuptools import setup, find_packages

long_description = """
bollydog.com
"""

INSTALL_REQUIRES = [
    "aiohttp==3.13.2",
    "authlib==1.6.6",
    "databases==0.9.0",
    "pydantic==2.12.5",
    "environs==14.5.0",
    "fire==0.7.1",
    "httptools==0.7.1",
    "itsdangerous==2.2.0",
    "mode-streaming==0.4.1",
    "ptpython==3.0.32",
    "pyyaml==6.0.3",
    "sqlmodel==0.0.31",
    "starlette==0.50.0",
    "starlette-authentication==0.1",
    "structlog==25.5.0",
    "uvicorn[standard]==0.40.0",
    "websockets==16.0",
]

setup(
    name="bollydog",
    version="0.1.5",
    author="3sy11",
    author_email="sorcerer0001@hotmail.com",
    description="bollydog framework - Async microservice framework with command-as-executable architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/3sy11/bollydog",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires="==3.12.13",
    install_requires=INSTALL_REQUIRES,
    extras_require={
        "dev": [
            "pytest==9.0.2",
            "pytest-asyncio==1.3.0",
            "pytest-cov==7.0.0",
            "pydot==4.0.1",
            "pydot-ng==2.0.0",
            "graphviz==0.21",
            "aiomonitor==0.7.0",
            "aiosqlite==0.22.0",
            "pycli==2.0.3",
            "mycli==1.67.1",
            "iredis==1.16.1",
            "httpx==0.28.1",
        ],
        "data": [
            "duckdb==1.5.1",
            "elasticsearch==8.14.0",
            "redis==7.4.0",
            "aioredis==2.0.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "bollydog=bollydog.cli:main",
        ],
    },
    include_package_data=False,
)
