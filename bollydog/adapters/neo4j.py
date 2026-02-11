from typing import Any, AsyncGenerator
from contextlib import asynccontextmanager
from neo4j import GraphDatabase
from bollydog.models.protocol import Protocol


class Neo4jProtocol(Protocol):
    adapter: Any

    def __init__(self, url: str, auth: tuple[str, str], *args, **kwargs):
        self.url = url
        self.auth = tuple(auth)
        super().__init__(*args, **kwargs)

    def create(self) -> Any:
        return GraphDatabase.driver(self.url, auth=self.auth)

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        with self.adapter as driver:
            yield driver

    async def execute(self, sql, **kwargs):
        async with self.connect() as driver:
            result = driver.execute_query(sql, **kwargs)
            return result
