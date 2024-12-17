from typing import Any, AsyncGenerator,List
from contextlib import asynccontextmanager
from neo4j import GraphDatabase
from bollydog.models.protocol import UnitOfWork, Protocol

class Neo4jUnitOfWork(UnitOfWork):
    adapter: Any

    def __init__(self, url:str, auth:tuple[str,str],*args, **kwargs):
        super().__init__()
        self.url=url
        self.auth=tuple(auth)

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        with self.adapter as driver:
            yield driver

    def create(self) -> Any:
        return GraphDatabase.driver(self.url, auth=self.auth)


class Neo4jProtocol(Protocol):

    async def execute(self,sql,**kwargs):
        async with self.unit_of_work.connect() as driver:
            result = driver.execute_query(sql,**kwargs)
            return result