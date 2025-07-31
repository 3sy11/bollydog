from setuptools import setup, find_packages

long_description = """
bollydog.com
"""

setup(
    name="bollydog",
    version="0.1.3",
    author="3sy11",
    author_email="",
    description="bollydog framework",
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
        # "loguru==0.6.0",
        "uvicorn==0.21.1",
        "authlib==1.3.1",
        "starlette==0.36.3",
        # "starlette-authentication",
        "itsdangerous==2.1.2",
        "mode-streaming==0.4.1",
        "fire==0.5.0",
        "pyyaml==6.0.1",
        "websockets==12.0",
        "aiohttp",
        "environs",
        "ptpython",
        "sqlmodel",
        "structlog"
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
        "optional":[
            "duckdb",
            "notion_client",
            "elasticsearch==8.14.0",
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
