import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Union, List

from bollydog.models.protocol import UnitOfWork, Protocol
from elasticsearch import AsyncElasticsearch

logger = logging.getLogger(__name__)


class ElasticUnitOfWork(UnitOfWork):

    def create(self) -> AsyncElasticsearch:
        return AsyncElasticsearch(hosts=[self.url], api_key=self.api_key)

    def __init__(self,
                 url: Union[str | List[str]],  # <
                 api_key: str,
                 *args, **kwargs):
        self.api_key = api_key
        self.url = url
        super().__init__(*args, **kwargs)

    async def create_index(self, index: str):
        return await self.adapter.indices.create(index=index)


class ElasticProtocol(Protocol):

    async def add(self, item: dict, index: str):
        result = await self.adapter.create(
            index=index,
            id=uuid.uuid4().hex,
            body=item,
        )
        return result.body

    async def add_all(self, items: list[dict], index: str):
        result = []
        for item in items:
            result.append(await self.add(item, index))
        return result

    async def update(self, item: dict, index: str):
        result = await self.adapter.update(
            index=index,
            id=item['iid'],
            body={
                "doc": item,
                "doc_as_upsert": True,
            },
        )
        return result.body

    async def update_all(self, items: list[dict], index: str):
        result = []
        for item in items:
            result.append(await self.update(item=item, index=index))
        return result

    async def get(self, index: str, **kwargs):
        result = await self.adapter.search(index=index, **kwargs)  # < scroll
        return result.body

    async def delete(self, index: str, item_id):
        result = await self.adapter.delete(index=index, id=item_id)  # < update sign=0
        return result.body

    async def list(self, index: str, **kwargs):
        result = await self.adapter.search(index=index, **kwargs)  # < scroll
        return result.body

    async def scroll(self, scroll, scroll_id, **kwargs):
        if not scroll_id:
            res = await self.adapter.search(index=kwargs['index'], scroll=scroll, body=kwargs['body'])
            yield res.body
            while len(res.body['hits']['hits']):
                res = await self.adapter.scroll(scroll=scroll, scroll_id=res['_scroll_id'])
                yield res.body
        else:
            res = await self.adapter.scroll(scroll=scroll, scroll_id=scroll_id)
            yield res.body
