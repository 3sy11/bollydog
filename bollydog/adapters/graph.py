import asyncio
import contextvars
from typing import Any, AsyncGenerator
from contextlib import asynccontextmanager
from bollydog.adapters._base import GraphProtocol, TransactionMixin


class Neo4jProtocol(GraphProtocol, TransactionMixin):

    _neo4j_ctx: contextvars.ContextVar = contextvars.ContextVar('neo4j_session')

    def __init__(self, url: str, auth: tuple[str, str], *args, **kwargs):
        self.url = url
        self.auth = tuple(auth)
        super().__init__(*args, **kwargs)

    async def on_start(self) -> None:
        from neo4j import GraphDatabase
        self.adapter = GraphDatabase.driver(self.url, auth=self.auth)

    async def __aenter__(self):
        session = self.adapter.session()
        self._neo4j_ctx.set(session)
        return session

    async def __aexit__(self, *exc_info):
        session = self._neo4j_ctx.get()
        session.close()

    async def execute(self, query: str, **params):
        return self.adapter.execute_query(query, **params)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        with self.adapter.session() as session:
            tx = session.begin_transaction()
            try:
                yield tx
                tx.commit()
            except BaseException:
                tx.rollback()
                raise

    async def on_stop(self) -> None:
        if self.adapter:
            self.adapter.close()
        await super().on_stop()


class NeuGProtocol(GraphProtocol):
    """GraphScope (alibaba/graphscope) standalone adapter."""

    def __init__(self, cluster_type: str = 'hosts', num_workers: int = 1, **kwargs):
        self.cluster_type = cluster_type
        self.num_workers = num_workers
        self._session = None
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        import graphscope
        self._session = graphscope.session(cluster_type=self.cluster_type, num_workers=self.num_workers)
        self.adapter = self._session

    async def execute(self, query: str, **params):
        graph = params.get('graph')
        if graph is None: raise ValueError('NeuGProtocol.execute requires graph=<loaded_graph> in params')
        interactive = self._session.gremlin(graph)
        return await asyncio.to_thread(lambda: interactive.execute(query).all())

    async def run_algorithm(self, algo_name: str, graph, **params):
        import graphscope
        algo_fn = getattr(graphscope, algo_name, None)
        if algo_fn is None: raise AttributeError(f'graphscope has no algorithm: {algo_name}')
        return await asyncio.to_thread(algo_fn, graph, **params)

    async def on_stop(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
        await super().on_stop()
