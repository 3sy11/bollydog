import uuid
from pydantic import Field
from bollydog.service.config import DOMAIN, HOSTNAME
from bollydog.models.base import BaseService


class Session(BaseService):
    alias = [DOMAIN]
    uid: str = Field(default_factory=lambda: uuid.uuid4().hex)
    username: str = Field(default=HOSTNAME)
    collection: dict = Field(default_factory=dict)
