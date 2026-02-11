from notion_client import AsyncClient
from bollydog.models.protocol import Protocol


class NotionProtocol(Protocol):

    def __init__(self, token, root_page_id=None, **kwargs):
        self.token = token
        self.root_page_id = root_page_id
        super().__init__(**kwargs)

    def create(self) -> AsyncClient:
        return AsyncClient(auth=self.token)

    async def create_page(self, **kwargs):
        res = await self.adapter.pages.create(**kwargs)
        return res

    async def update_page(self, page_id, **kwargs):
        res = await self.adapter.pages.update(page_id=page_id, **kwargs)
        return res

    async def query_database(self, database_id, **kwargs):
        res = await self.adapter.databases.query(database_id, **kwargs)
        return res
