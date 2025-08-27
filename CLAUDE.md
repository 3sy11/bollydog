# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Installation

To install the project and its dependencies, use `uv`:

```shell
uv sync
uv sync --dev
```

### Build

To build the project, run:

```shell
uv build --all
```

Then, to install the built wheel:

```shell
uv run uv pip install dist/bollydog-*.whl
```

### Testing

The tests are located in the `tests/` directory. Based on the file names, it seems like `pytest` is used. To run the tests:

```shell
pytest
```

## Architecture

This project is a Python application that uses an event-driven architecture. 

- **Core Concepts**: The main concepts are `Command`, `Event`, `Handler`, `UnitOfWork`, `Service`, `Protocol`, and `Session`.
- **Entrypoints**: The application has multiple entrypoints, including a CLI, HTTP, and WebSocket.
- **Microservice Orchestration**: The system uses a configuration file for microservice orchestration, which allows for load balancing and system decomposition.
- **Asynchronous Operations**: The codebase extensively uses coroutines and an asynchronous generator mechanism.
- **DDD and TDD**: The project follows Domain-Driven Design (DDD) and Test-Driven Design (TDD) principles.
- **Adapters**: The `bollydog/adapters/` directory contains adapters for different services like Elasticsearch, Neo4j, and relational databases.
- **Models**: The `bollydog/models/` directory defines the data structures used in the application, including `BaseMessage` for event specification and `Session` for global context.
- **Services**: The `bollydog/service/` directory contains the core application logic, including services and handlers.
- **Entrypoints**: The `bollydog/entrypoint/` directory defines the different entrypoints for the application.
- **Configuration**: The application is configured using a YAML file, as shown in the `example/` directory.

## Document dev

### context7

https://context7.com/faust-streaming/mode/llms.txt

./docs/llms/mode.txt