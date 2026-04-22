import asyncio
from typing import Any, AsyncGenerator
from contextlib import asynccontextmanager
from bollydog.adapters._base import GraphProtocol, TransactionMixin


class Neo4jProtocol(GraphProtocol, TransactionMixin):
    adapter: Any

    def __init__(self, url: str, auth: tuple[str, str], *args, **kwargs):
        self.url = url
        self.auth = tuple(auth)
        super().__init__(*args, **kwargs)

    def create(self) -> Any:
        from neo4j import GraphDatabase
        return GraphDatabase.driver(self.url, auth=self.auth)

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        with self.adapter as driver:
            yield driver

    async def execute(self, query: str, **params):
        async with self.connect() as driver:
            return driver.execute_query(query, **params)

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


class NeuGProtocol(GraphProtocol):
    """GraphScope (alibaba/graphscope) standalone adapter.
    Sync C++ engine calls offloaded via asyncio.to_thread for large queries.
    """

    def __init__(self, cluster_type: str = 'hosts', num_workers: int = 1, **kwargs):
        self.cluster_type = cluster_type
        self.num_workers = num_workers
        self._session = None
        super().__init__(**kwargs)

    def create(self):
        import graphscope
        self._session = graphscope.session(cluster_type=self.cluster_type, num_workers=self.num_workers)
        return self._session

    async def execute(self, query: str, **params):
        graph = params.get('graph')
        if graph is None:
            raise ValueError('NeuGProtocol.execute requires graph=<loaded_graph> in params')
        interactive = self._session.gremlin(graph)
        def _exec():
            return interactive.execute(query).all()
        return await asyncio.to_thread(_exec)

    async def run_algorithm(self, algo_name: str, graph, **params):
        import graphscope
        algo_fn = getattr(graphscope, algo_name, None)
        if algo_fn is None:
            raise AttributeError(f'graphscope has no algorithm: {algo_name}')
        return await asyncio.to_thread(algo_fn, graph, **params)

    async def on_stop(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
        await super().on_stop()
