from setuptools import setup, find_packages

long_description = """
bollydog.com
"""

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
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.11',
    install_requires=[
        "starlette==0.36.3",
        "uvicorn==0.21.1",
        "httptools==0.7.1",
        "starlette-authentication",
        "authlib==1.3.1",
        "itsdangerous==2.1.2",
        "sqlmodel",
        "databases==0.9.0",
        "mode-streaming==0.4.1",
        "websockets==12.0",
        "aiohttp",
        "fire==0.5.0",
        "pyyaml==6.0.1",
        "environs",
        "structlog",
        "ptpython",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
            "pydot",
            "pydot-ng",
            "graphviz",
            "aiomonitor",
            "aiosqlite",
            "pycli",
            "mycli",
            "iredis",
            "httpx",
        ],
        "data":[
            "duckdb",
            "elasticsearch==8.14.0",
            "redis",
            "aioredis",
        ]
    },

    entry_points={
        'console_scripts': [
            'bollydog=bollydog.cli:main',
        ],
    },
    include_package_data=False,  # 包含包中的所有非代码文件
    # package_data={
    #     '': ['*.txt', '*.rst'],
    #     'your_package': ['data/*.dat'],
    # },
    # data_files=[
    #     ('my_data', ['data/data_file']),
    # ],
)
