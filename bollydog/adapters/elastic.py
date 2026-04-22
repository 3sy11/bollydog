import uuid
from typing import Union, List, AsyncIterator
from bollydog.adapters._base import CRUDProtocol, BatchMixin, StreamMixin
from elasticsearch import AsyncElasticsearch


class ElasticProtocol(CRUDProtocol, BatchMixin, StreamMixin):

    def __init__(self, url: Union[str, List[str]], api_key: str, *args, **kwargs):
        self.api_key = api_key
        self.url = url
        super().__init__(*args, **kwargs)

    def create(self) -> AsyncElasticsearch:
        return AsyncElasticsearch(hosts=[self.url], api_key=self.api_key)

    async def create_index(self, index: str):
        return await self.adapter.indices.create(index=index)

    async def add(self, item, **ctx):
        index = ctx.get('index', 'default')
        result = await self.adapter.create(index=index, id=uuid.uuid4().hex, body=item)
        return result.body

    async def add_all(self, items: list, **ctx):
        return [await self.add(item, **ctx) for item in items]

    async def get(self, **query):
        index = query.pop('index', 'default')
        result = await self.adapter.search(index=index, **query)
        return result.body

    async def list(self, **query) -> list:
        index = query.pop('index', 'default')
        result = await self.adapter.search(index=index, **query)
        return result.body

    async def update(self, query: dict, data: dict):
        index = query.get('index', 'default')
        item_id = data.get('iid', '')
        result = await self.adapter.update(index=index, id=item_id, body={"doc": data, "doc_as_upsert": True})
        return result.body

    async def update_all(self, items: list, **ctx):
        return [await self.update(ctx, item) for item in items]

    async def delete(self, **query):
        index = query.get('index', 'default')
        item_id = query.get('id', '')
        result = await self.adapter.delete(index=index, id=item_id)
        return result.body

    async def stream(self, **query) -> AsyncIterator:
        index = query.pop('index', 'default')
        scroll = query.pop('scroll', '2m')
        body = query.pop('body', {})
        res = await self.adapter.search(index=index, scroll=scroll, body=body, **query)
        yield res.body
        scroll_id = res.body.get('_scroll_id')
        while scroll_id and res.body['hits']['hits']:
            res = await self.adapter.scroll(scroll=scroll, scroll_id=scroll_id)
            if not res.body['hits']['hits']:
                break
            yield res.body
            scroll_id = res.body.get('_scroll_id')
