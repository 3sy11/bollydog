import pytest
import json
import asyncio
from bollydog.adapters.elastic import ElasticProtocol, ElasticUnitOfWork
from pydantic import Field

from bollydog.models.base import BaseDomain


class Point(BaseDomain):
    x: int = Field(alias='x')
    y: int = Field(alias='y')
    title: str = Field(alias='title', max_length=50, default='title')


@pytest.mark.asyncio
async def test_adapter_orm():
    unit_of_work = ElasticUnitOfWork(url='http://172.27.0.2:9200/',
                                     api_key='SGxvMUpKQUJ2eFFMR3ZTOWFBYjk6WExycVZhNThTUGlMSDlkb2I3bEVZUQ==')
    protocol = ElasticProtocol(unit_of_work=unit_of_work)
    p1 = Point(x=1, y=2, title='p1').model_dump()
    p2 = Point(x=3, y=4, title='p2').model_dump()
    p3 = Point(x=5, y=6, title='p3').model_dump()
    p4 = Point(x=7, y=8, title='p4').model_dump()
    p5 = Point(x=9, y=10, title='p5').model_dump()
    p6 = Point(x=11, y=12, title='p6').model_dump()
    p7 = Point(x=13, y=14, title='p7').model_dump()
    p8 = Point(x=15, y=16, title='p8').model_dump()
    p9 = Point(x=17, y=18, title='p9').model_dump()
    p0 = Point(x=19, y=20, title='p10').model_dump()
    await protocol.add_all([p1, p2, p3, p4, p5, p6, p7, p8, p9, p0], index='point2')
    result = []
    gt = p2['created_time']
    await asyncio.sleep(1)  # ? wait for writing
    res = await protocol.get(index='point2', scroll='1m',
                             body={
                                 "query": {
                                     "range": {
                                         "created_time": {
                                             "gt": gt
                                         }
                                     }
                                 },
                                 "size": 2
                             }
                             )
    result.extend(res['hits']['hits'])
    while len(res['hits']['hits']):
        res = await protocol.scroll(scroll='1m', scroll_id=res['_scroll_id'])
        result.extend(res['hits']['hits'])
    await unit_of_work.client.delete()
    # assert len(result) == 8
