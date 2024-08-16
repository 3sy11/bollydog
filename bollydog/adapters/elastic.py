import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Union, List

from bollydog.models.protocol import UnitOfWork, Protocol
from elasticsearch import AsyncElasticsearch
from pydantic import AnyUrl

logger = logging.getLogger(__name__)


class ElasticUnitOfWork(UnitOfWork):
    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        try:
            yield self.client
        except Exception as e:
            logger.error(e)

    async def create(self):
        ...

    def __init__(self,
                 url: Union[AnyUrl | str | List[AnyUrl] | List[str]],
                 api_key: str,
                 *args, **kwargs):
        if isinstance(url, str):  # < cluster
            url = AnyUrl(url)
        super().__init__(url=url, *args, **kwargs)
        self.api_key = api_key
        self.client = AsyncElasticsearch(hosts=[self.url.unicode_string()], api_key=self.api_key)

    async def create_index(self, index: str):
        return await self.client.indices.create(index=index)


class ElasticProtocol(Protocol):
    unit_of_work: ElasticUnitOfWork

    async def add(self, item: dict, index: str):
        result = await self.unit_of_work.client.create(
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
        result = await self.unit_of_work.client.update(
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
        result = await self.unit_of_work.client.search(index=index, **kwargs)  # < scroll
        return result.body

    async def delete(self, index: str, item_id):
        result = await self.unit_of_work.client.delete(index=index, id=item_id)  # < update sign=0
        return result.body

    async def list(self, index: str, **kwargs):
        result = await self.unit_of_work.client.search(index=index, **kwargs)  # < scroll
        return result.body

    async def scroll(self, scroll, scroll_id, **kwargs):
        if not scroll_id:
            res = await self.unit_of_work.client.search(index=kwargs['index'], scroll=scroll, body=kwargs['body'])
            yield res.body
            while len(res.body['hits']['hits']):
                res = await self.unit_of_work.client.scroll(scroll=scroll, scroll_id=res['_scroll_id'])
                yield res.body
        else:
            res = await self.unit_of_work.client.scroll(scroll=scroll, scroll_id=scroll_id)
            yield res.body
